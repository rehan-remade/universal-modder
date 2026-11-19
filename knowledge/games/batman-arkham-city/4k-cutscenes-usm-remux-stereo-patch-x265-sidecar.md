---
kind: game
title: "4K 60 fps pre-rendered cutscenes for Arkham City (CRI USM remux, stereo-check patch, x265 sidecar playback via BmSDK)"
game: "Batman: Arkham City"
games_also: []
game_version: "Game of the Year Edition, Steam, 32-bit DX11, BmSDK v0.21.0, CRI Movie PCx86 2.82rs1"
platform: windows
engine: unreal
route: native-hook
tools: ["BmSDK v0.21.0", "ffmpeg 7 (mpeg1video, libx265, hevc_nvenc)", "Python (own USM parser/muxer)", "capstone (Python)", "Frida 17", "fxc /dumpbin"]
anti_cheat: "none (single-player); the Steam exe's code is SteamStub-encrypted on disk, so it was read from the running process and patched in memory, never on disk"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-18
links: ["https://github.com/Team-BmSDK/BmSDK-AC", "knowledge/games/batman-arkham-city/split-screen-co-op-fixes-for-arkham-city-bmsdk-c-scripts-cam.md"]
tags: [cutscenes, fmv, video, 4k, cri, usm, sofdec, mpeg-1, scaleform, gfx-video, stereo-3d, side-by-side, x265, hevc, ffmpeg, bmsdk, detour, unreal-engine-3]
---

# 4K 60 fps pre-rendered cutscenes for Arkham City (CRI USM remux, stereo-check patch, x265 sidecar playback via BmSDK)

> Arkham City plays its story FMVs with CRI Movie (`.usm`), not Bink like Arkham Asylum, so "drop in 4K
> `.bik` files" doesn't work. Replacing them takes three things: a USM remuxer that swaps the video and keeps
> every audio language, the subtitles and the cue points; an in-memory patch of the game's "this video is
> side-by-side 3D" check, which crops anything 2560 px or wider to its left half; and, to avoid ~28 GB of
> MPEG-1, a BmSDK detour that paints frames from an x265 `.mkv` (decoded by an external ffmpeg) over a black
> stand-in video. A 60 fps `.mkv` plays at a true 59.94 fps (the mod writes the in-between frames into the
> video texture itself and caps the game at 59.94 fps during the movie). Verified in game with marked test
> videos at 3840x2160, 30 and 60 fps.

## Setup
- Batman: Arkham City GOTY, Steam, Windows 11, DX11 renderer, game at 3840x2160.
- BmSDK v0.21.0 (C# scripts in `BmGame\Mods\<mod>\scripts`, compiled by the SDK at launch). It runs on the Steam
  exe as installed: skip the old "compatibility patch" that replaces `BatmanAC.exe` (see the
  [split-screen note](split-screen-co-op-fixes-for-arkham-city-bmsdk-c-scripts-cam.md), Setup).
- ffmpeg 7.x (64-bit, on PATH) with libx265 / hevc_nvenc; Python 3 for the USM tools.
- Frida 17 in a venv for live tracing (optional; see Gotcha 7).

## Route and why
- **Asset-only (replace the `.usm`) is not enough:** the files are CRI USM with MPEG-1 video, and the game
  crops wide videos (below). Remuxing alone gives a stretched left half at 4K.
- **Patching the exe on disk** isn't possible cleanly: the Steam exe's `.text` is SteamStub-encrypted. The
  patch is applied in memory by a BmSDK script at startup (byte-signature search, so other builds are left
  alone).
- **Replacing CRI's decoder** with an in-process HEVC decoder was rejected: the game is 32-bit and runs out
  of address space with 4K textures. Instead the CRI player keeps running (timing, audio, cues, subtitles,
  skipping) on a black stand-in, and frames from a 64-bit ffmpeg process are copied over its output.

## How the game works (what we had to learn)
- **Files.** `BmGame\Movies\*.usm` holds mono videos (in-world TV screens at 640x360, logos, DLC bits).
  **Every story cutscene exists only in `BmGame\MoviesStereo`**, as 3840x1080 side-by-side stereo
  (two 1920x1080 eyes), 29.97 fps, ~19 Mbit/s MPEG-1 for both eyes together (~9.5 Mbit/s per eye, which is
  why they look soft and blocky). The game's movie file opener (Scaleform file callback, near the
  wide strings `Movies` / `MoviesStereo` / `USM`) rewrites `Movies` to `MoviesStereo`, so a mono copy put in
  `Movies\` is never played. 41.5 minutes of stereo cutscenes in total, 7.9 GB.
- **USM layout (CRI Movie 2.82).** Chunks `CRID`, `@SFV` (video), `@SFA` (audio; ch0 M&E + ch1 English
  6-ch 48 kHz, ch2-5 other languages 2-ch 22 kHz), `@SBT` (subtitles), `@CUE` (cue points the game uses as
  events). Chunk header: 4-byte signature, big-endian size, then a 0x18-byte block (header size, big-endian
  padding size, channel, type 0=data/1=header/2=marker/3=metadata, frame time, frame rate x100). Headers are
  `@UTF` tables. Each `@SFV` data chunk is one picture in decode order, frame time = index x 100. The `@SFV`
  metadata chunk is the seek index (`ofs_byte`, `ofs_frmid` per I-frame that carries a GOP header).
  `CRID` and the `@SFV` header carry sizes, bitrates and buffer sizes (`minbuf`/`ixsize` ~ the largest
  picture) that must be updated when the video changes.
- **Video codec.** `@SFV` is plain MPEG-1 video ("Sofdec Prime") with an extra user-data block after each
  sequence header (`TMPGEXS ... IDCPREC 3`, i.e. 11-bit intra DC; the header says `mpeg_dcprec` 11).
  ffmpeg decodes it correctly as `mpeg1video`. CRI's decoder also accepts ffmpeg's own `mpeg1video` output at
  3840x2160 if the header says `mpeg_dcprec` 8 and the user data says `IDCPREC 0` (32 slices per picture
  played fine; the originals use one slice per macroblock row). MPEG-1 caps at 4095 px per side, so 4K
  stereo (7680x2160) is impossible, but 3840x2160 mono is fine.
- **Playback path.** Fullscreen movies are a Scaleform movie, `FullScreenVideo.FullScreenVideo` (a `Video`
  object scaled to the 1280x720 stage; ActionScript only sets volume, tracks and subtitles). Scaleform Video
  wraps `CriMvEasyPlayer`; each frame `GetFrameOnTimeAsYUVBuffers(YuvBuffers*, FrameInfo*, int* ready)`
  (thiscall, `ret 0xC`) decodes into the mapped planes of a Scaleform YUV texture: Y is 4096x4096 R8,
  U and V are 2048x2048 R8, pitches 4096/2048. `FrameInfo` holds the frame number at +4 and width/height at
  +8/+0xC. `YuvBuffers` is (ptr, size, pitch) for Y, U, V. The game's renderer draws it with
  `GFx_PS_TextTextureYUV` and texture coordinates `0..w/4096, 0..h/4096` (correct for any size).
- **The crop.** In the game's Scaleform YUV texture setup (one copy for D3D9, one for D3D11) the texture is
  flagged "side-by-side stereo" when the video **width >= 2560 (0xA00)**. When drawing a stereo-flagged
  bitmap, the renderer takes the u midpoint and draws only the left half (the right half for the 3D Vision
  right eye). So any video 2560+ wide shows its left half stretched to the screen; 1920x1080 shows in full.
  The two checks share a 27-byte pattern: `cmp [esp+1C],1 / mov ebp,[esp+14] / sete al / cmp ebp,0A00 /
  mov [esi+1C],al / jl +4 / mov byte [esi+18],1`.
- **The fix.** Replace each `cmp ebp,0A00` (6 bytes) with `call cave; nop`, where the cave does
  `push eax / mov eax,[esp+20] (height) / add eax,eax / cmp ebp,eax / pop eax / ret`. The existing `jl`
  now means "width < 2 x height". The stock 3840x1080 files stay stereo; 3840x2160 is mono and shows in full.

## Build steps
1. **USM tools** (Python, about 300 lines): a demuxer (concatenate `@SFV` type-0 payloads, honouring the
   16-bit padding field) and a remuxer that (a) splits a new MPEG-1 stream into pictures (sequence/GOP/user
   data headers stay with the next picture), (b) requires the same picture count as the original, (c) puts
   picture *i* in the *i*-th `@SFV` data chunk (header copied, frame time i x 100, padding to 32-byte
   alignment), leaving every other chunk byte-identical and in place, (d) inserts the `IDCPREC 0` user data
   after each sequence header, (e) patches the `@SFV` header (width/height/mat/disp, total_frames, ixsize,
   mpeg_dcprec, metadata_size) and `CRID` (file size, bitrate, minbuf), and (f) rebuilds the seek table with
   real chunk offsets. Round-trip test: remux an original with its own video, then diff.
2. **BmSDK mod `Cutscenes4K`, script 1:** at `Main()`, find both 27-byte patterns in the executable sections,
   `VirtualAlloc` an RWX cave, write the 11-byte cave, patch each site to `E8 rel32 90`, restore protection,
   `FlushInstructionCache`. Log the number of sites patched (expect 2).
3. **Script 2 (sidecar video):** use `DetourUtil.NewDetour` on two functions found by wildcard signature:
   - the movie file opener, to learn which `.usm` is opening. If `MoviesStereo\<name>.mkv` exists, it starts
     `ffmpeg -v error -nostdin -hwaccel auto -i <mkv> -an -sn -map 0:v:0
     -vf scale=3840:2160,format=yuv420p -f rawvideo -` with stdout redirected.
   - `GetFrameOnTimeAsYUVBuffers`: call the original, and if it returned 1 and the frame is 3840x2160, copy
     frame `info[1]` from a 4-frame ring into the Y/U/V buffers using their pitches.
   - A reader thread fills the ring and never runs more than 4 frames ahead of the last frame requested
     (pipe backpressure throttles ffmpeg). The hook waits up to 250 ms for a frame that isn't ready yet. A
     watchdog kills ffmpeg 3 s after the last request, and on process exit.
4. **Per cutscene:** encode a black stand-in (`color=black:s=3840x2160:r=30000/1001`, the original's frame
   count, `mpeg1video -q:v 31 -g 13 -bf 2 -slices 32`), remux it into the original `.usm` (about 4 MB for
   8 s), and encode the real video to `<name>.mkv` (x265 10-bit CRF 16, or `hevc_nvenc -cq 16`) with the
   frame count forced to the original's. Put both in `MoviesStereo`. With no `.mkv`, the movie plays as
   normal; the plain-MPEG-1 route is the same remux with the real video at `-q:v 2`.
5. **60 fps:** keep the stand-in at 29.97 fps and make only the `.mkv` 59.94 fps (twice the frame count;
   the mod reads its rate with ffprobe). Two things are added:
   - Pace the sidecar off a smooth 59.94 fps clock that is re-anchored to frame 2k whenever CRI
     delivers stand-in frame k (if it drifted more than 1.5 frames) and capped at 2 stand-in frames
     ahead (so it stops when the game pauses).
   - On every game tick where CRI delivered nothing, detour Scaleform video's per-tick update
     (thiscall `(YUV texture, x, y)`, `ret 0xC`) and, if the clock moved on, write the clock's frame into
     the texture with its own vtable calls: `+0x10 Map(0, 4, planes, 0)` returns the plane count,
     `+0x14 Unmap(0, count, planes, 0)`. Each plane is 16 bytes: `{width, height, data, pitch}`.
   - From BmSDK `OnTick`, set `Engine.MaxSmoothedFrameRate = 59.94` (with `bSmoothFrameRate`) while a
     sidecar plays and restore it afterwards, so a 144 Hz G-Sync display shows exactly one video frame
     per refresh.

## Verification
- **Oracle:** marked test videos played in the real game through a throwaway BmSDK script that calls
  `RPlayerController.FSM_PlayMovie(FString)` on F7 (the game resolves the bare name, e.g. `2_02`). The
  markers were a coloured border, LEFT/CENTER/RIGHT labels, a magenta centre line and a `drawtext`
  frame counter. Each screenshot was read by eye and matched against source frames by normalised
  cross-correlation (0.95 on the left half, ~0 on the full frame before the fix).
- Live tracing with Frida found the textures (D3D11 `CreateTexture2D` hooked through a vtable of a device
  created in the target), the draw (the game's DrawBitmaps implementation, logging `TextureCoords`) and the
  CRI frame info. Exe code was read with capstone from a memory dump of the running game, kept private and
  outside any repo (never written into the game folder or run).
- **Verified:** 3840x2160 MPEG-1 inside the USM shows in full with the patch. The x265 sidecar plays in sync
  with a running frame counter (8 s test clip: 4 MB stand-in + 18 MB mkv vs 93 MB as 4K MPEG-1). The BmSDK
  log shows `patched 2 stereo video checks` and `2_02.usm uses 2_02.mkv`.
- **60 fps, run by the agent itself** (launch via Steam, F7 from the main menu, read the BmSDK log):
  453 distinct sidecar frames of the ~455 shown before the movie's last cue, 239 CRI deliveries,
  477 video ticks in ~8 s (the cap held at 59.94), 2 in-between frames not decoded in time, 0 Map
  failures. Each frame took about 1 ms to copy. CRI's own decode of the stand-in was 166 ms in total.
- **Not verified:** a full-length cutscene; pausing or skipping mid-sidecar; 3D Vision with the patch;
  the stock stereo cutscenes after the patch (they should be unchanged, since 3840 >= 2 x 1080); the
  D3D9 renderer; the Epic build (the signatures may differ).

## Gotchas
1. **A 4K `.usm` shows only its left half, stretched.** The cause is the stereo flag at width >= 2560, not
   the Flash movie, the shaders or the texture size (all three were checked). Patch the check (see above).
2. **A mono file in `BmGame\Movies` is ignored.** The opener rewrites the path to `MoviesStereo`; put
   replacements there.
3. **Extracted MPEG-1 has zeros between pictures.** The chunk padding field is 16-bit big-endian at +2 of
   the 0x18 block, not one byte.
4. **ffmpeg `mpeg1video` caps slices at 32** (`-slices 135` gives 32). CRI played 32-slice 4K anyway, so
   one slice per row isn't required.
5. **Screenshots look blown out or posterised.** That came from the user's HDR output, not the encode.
   Compare against the source frame before chasing decoder bugs.
6. **The game must be closed to replace a `.usm`.** `cp` fails with "Device or resource busy" while the game
   holds the file.
7. **Frida: "VirtualAllocEx returned 0x00000008" after a few attaches.** The 32-bit game is out of address
   space with 4K video textures. Restart the game between tracing sessions and keep the hooks minimal.
8. **BmSDK: `CS0104 'Debug' is ambiguous`** once `using System.Diagnostics;` is added (for `Process`).
   Alias `using Debug = BmSDK.Framework.Debug;`. One compile error disables the whole mod, including the
   other script, and the symptom in game was a black screen with sound.
9. **BmSDK: CS0120 when a static method uses `Mod.DirectoryPath`.** `Mod` is an instance member; make the
   method non-static.
10. **The sidecar must match the stand-in's frame count.** Audio, subtitles and cues are timed by the CRI
    player from the original USM, so force the frame count (`-frames:v N`, `tpad` to clone the last frame).
11. **A 59.94 fps 4K stand-in only reaches ~47 fps.** CRI decodes the stand-in in the background and
    can't do 4K MPEG-1 with B-frames at 60 (the game ticked at 133/s and CRI still delivered 47/s). Keep
    the stand-in at 29.97 and add the in-between frames yourself.
12. **A stand-in without B-frames freezes after ~3 s** (CRI stops delivering at frame ~140 while the
    audio goes on), with an I-frame every 13 frames or with only one. Keep `-g 13 -bf 2` like the originals.
13. **CRI hands out frames unevenly** (two on back-to-back ticks, then a gap). Showing "frame 2k+1 half a
    frame after 2k" only filled 147 of 239 gaps. A smooth clock re-anchored to CRI fills all of them.
14. **The Map plane layout is `{width, height, data, pitch}`.** Reading the game's own caller suggests
    `{rows, data, pitch}`, but it reads them relative to an esp that is 4 bytes higher after the
    callee pops its arguments. Getting it wrong makes `Buffer.MemoryCopy` write to address 2160, which
    surfaces in BmSDK as a NullReferenceException. Log `e.ToString()` once to see the line.
15. **A 4K MPEG-1 frame counter can't tell 30 from 60 fps.** The counter shows the frame for the current
    time either way. Count distinct frames copied in the mod instead.

## Assets
None generated. Test videos were ffmpeg `drawbox`/`drawtext` overlays on a lanczos upscale of the original
left eye. Real 4K sources have to come from an AI upscaler (Topaz/Video2X) fed the 1080p left eye; the
upscaling itself wasn't done here.

## Cost and time
One long session.

## Open questions
- Full-length cutscenes, skip/pause behaviour and memory use with the sidecar.
- Whether 59.94 vs the game's real tick cadence shows any judder over long scenes (two frames per refresh
  were missed in 8 s).
- Whether the PS3 / Return to Arkham releases (from your own copy) carry cleaner masters to upscale from (the
  PC files are ~9.5 Mbit/s MPEG-1 per eye).
- Epic build signatures; the D3D9 path.
