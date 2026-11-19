---
kind: technique
title: "Recording real game footage with only the game's audio"
tags: [recording, gfxcapture, wasapi, process-loopback, nvenc, audio-sync, showcase]
date: 2026-10-10
agents: ["Claude Code (Opus 5.5)"]
humans: ["@rehan_shei", "DarkameMaster"]
links: []
---

# Recording real game footage with only the game's audio

> Capture one game window (GPU frames, not the desktop) and one process's sound (no Discord pings, no
> Spotify), synced, then cut. `um win record` + `um video mux` do this on Windows, including from WSL.

## When to use it
Showcase videos, bug evidence, and oracles that need to see motion.

## How
- **Video:** ffmpeg's `gfxcapture` source (Windows.Graphics.Capture) on the game's window
  (`window_exe=` or `hwnd=`). It gets the real frames even when the window is covered. Encode with
  NVENC/AMF/QSV and write **.mkv**.
- **Audio:** WASAPI **process loopback** of the game's PID (`um/ps1/ProcLoopback.ps1`). Write raw f32 stereo
  48 kHz, placed by QPC timestamps with gaps filled with silence, so file position = wall time.
- **Sync:** record both start times, then mux with the offset. Fine-tune with a visual/audio event (a flash
  vs its boom).
- **Pacing:** script the take (mod-side timeline or director), so a reshoot is one command.

## Gotchas
1. **Black frames.** GDI/`gdigrab` can't see GPU-rendered games. Use gfxcapture (or `ddagrab` for the whole
   monitor).
2. **Empty .mkv, and ffmpeg ignores 'q'.**
   - **Cause:** gfxcapture only delivers a frame when the window redraws. A paused game, static menu or
     minimized window produces nothing, and ffmpeg is stuck waiting.
   - **Fix:** record while the game is rendering. Stop from a background thread, with a kill after a
     timeout.
3. **Never stop ffmpeg from the game's main thread.** If the game blocks, gfxcapture stalls and the 'q' is
   never read. The tail of the take is lost.
4. **NVENC H.264 is limited to 4096 px wide.** Crop 32:9 screens to the centre 16:9, scale down, or use
   HEVC.
5. **Reading the back buffer from inside the game can leak.** FNA3D's D3D11 `ReadBackbuffer` allocated a
   staging texture per call (17 GB in one take). Capture from outside.
6. **The game's audio can't be redirected.** Many engines (FAudio, Unity, Unreal) talk to WASAPI directly,
   so SDL/driver tricks do nothing. Use process loopback.
7. **Audio a few hundred ms early.** ffmpeg + capture + encoder startup takes about 0.25-0.3 s before the
   first frame. Account for it in the mux, and measure once per machine.
8. **Process loopback captured exact silence.** **Symptom:** the take's audio track is tiny (about 2 kb/s of
   AAC), and every capture ever made from the game's process is exact zeros, while a capture of another program
   on the same machine is fine. **Cause:** Windows had that executable muted (volume 0 plus mute) in the
   per-application volume mixer of the default output device. A process-loopback capture follows that mixer, so it
   records silence even though the game is playing. The setting belongs to the executable, so every game started
   through the same host program is affected (here tModLoader's bundled `dotnet.exe`). It is the player's own
   preference. **Fix:** leave it alone, and detect it by measuring the capture (maximum absolute sample), not by
   ear. If you own the engine that makes the sound, dump its mix yourself: read the engine's audio after each step
   with a cursor of your own, write it to a raw file with each step's QPC time, place it on the take's timeline with
   a linear fit of step times against the recording's start time, and mux it only when the process capture is
   silent. Also expect no music from a window that is not active: Terraria pauses its music and ambience while
   the window is inactive.
9. **The emulator's own frame dump gave nothing usable.** **Symptom:** with Slippi's Dolphin 3.6.4, asking for a
   frame-and-audio dump did not produce a usable video (the cause was not investigated). **Fix:** film the emulator's
   window from outside with gfxcapture, showing it but not activating it (`SW_SHOWNOACTIVATE`), with audio from that
   process only. That produced a 101.6 s, 640x480 take of a CPU-versus-CPU match with the emulator's own sound.
10. **"Minimized, not activated" still ended up in the foreground.** **Symptom:** launched with
    `SW_SHOWMINNOACTIVE` while the user was away, the emulator was the foreground window in 214 of 225 samples.
    **Cause:** once the user has been idle long enough, Windows lets a process take the foreground, whatever show
    flag it was started with. **Fix:** launch it visible but not activated (`SW_SHOWNOACTIVATE`), sample the
    foreground window and the user's idle time on a thread, stop the run if the user returns, and report any
    foreground change. As a fallback, if a minimized instance delivers no game frame within 45 s, close it by its
    exact PID and relaunch it visible.

## Seen in
- [Fal Arsenal (Terraria)](../games/terraria/fal-arsenal-tmodloader.md)
- [San Franciscans (AoE2)](../games/age-of-empires-ii-de/san-franciscans-civ.md)
- [Minecraft inside GTA V](../games/gta-v/minecraft-passthrough.md)
