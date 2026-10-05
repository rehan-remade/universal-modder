---
name: showcase-video
description: Record and cut a short showcase video of a game mod, or a compilation of clips, ready to post on X/YouTube. Records the game window with only the game's own audio, picks moments from contact sheets, and edits with one-line animated titles, creator credits, transitions, music, watermark and fade-out via an EDL JSON. Use when the user wants a demo video, trailer, clip or montage of a mod, or wants to combine existing clips into a styled video.
---

# Showcase video

A mod isn't finished until you can show it in 30 seconds. The toolchain is `um win record` (capture),
`um video contact` (look), `um video compile` (edit), all ffmpeg + Pillow.

## 1. Make the take repeatable
- **Script the action.** Use a mod-side timeline or command sequence (spawn enemies, fire the weapon, cue
  the boss), a scenario with triggers and camera moves, or a WinDrive command list. The first clean take
  should be reproducible exactly, so you can reshoot after a fix.
- **Restore the world before each take.** Explosions crater worlds; units die. Keep a pristine copy with
  `um backup` and restore it every take.
- **Clean frame.** Hide debug text, fix the camera zoom (the Terraria showcase used 1.5x so 1080p frames
  read like a 720p cut), run at full speed when unfocused, and hide the cursor (capture uses
  `capture_cursor=0`).

## 2. Record the window + the game's own audio
```bash
um win record --exe Game.exe --out C:\caps\take1 --seconds 40      # -> take1.mkv, take1.audio.raw, take1.json
um video first-frame C:/caps/take1.mkv                              # where gameplay starts (skips loading screens)
um video mux C:/caps/take1.mkv C:/caps/take1.audio.raw C:/caps/take1.json take1.mp4 [--offset 0.25]
```
- **Video:** ffmpeg gfxcapture of that window only (GPU frames, no desktop). It encodes with NVENC, AMF or
  QSV when available. NVENC H.264 maxes out at **4096 px wide**, so the recorder scales above that; for
  32:9 screens, crop to the centre 16:9 with `--crop`.
- **Audio:** WASAPI **process loopback** of the game's PID (`um/ps1/ProcLoopback.ps1`). Only the game is
  recorded; no Spotify, no notifications. It's timestamped so the file position is wall time. Muxing uses
  the recorded offset. Fine-tune with a visual/audio sync event (a flash vs its boom) and pass `--offset`.
- **Inside a mod (optional):** start and stop recording from the mod for frame-exact takes. Never block the
  game's main thread while stopping ffmpeg: send `q`, then wait off-thread. Write `.mkv` so a killed
  recorder still leaves a playable file (see `examples/terraria-tmodloader/reference/InModRecorder.cs`).

## 3. Look before you cut
```bash
um video probe clip.mp4
um video contact clip.mp4 sheet.png --every 1.5 --cols 6     # a timestamped grid; read it, pick in/out points
um video contact clip.mp4 zoom.png --start 20 --end 30 --every 0.5
```
Pick the peak moments: the explosion, the boss reveal, the unit in formation. Write in/out times into the
EDL.

## 4. Edit with an EDL
`um video compile edl.json out.mp4` (`--preview` renders half size and fast). The full format is in
`um video --help`.
```json
{
  "size": [1920, 1080], "fps": 30,
  "theme": {"accent": "#B6FF3B"},
  "transition": {"type": "fade", "duration": 0.3},
  "clip_volume": 0.8,
  "music": {"path": "music.mp3", "volume": 0.5},
  "watermark": {"path": "logo.png", "height": 54, "corner": "br"},
  "segments": [
    {"clip": "take1.mp4", "in": 9.0, "dur": 3.0, "hook": "Terraria, but with a tactical nuke."},
    {"clip": "take1.mp4", "in": 24.2, "dur": 4.5, "title": "Tactical Nuke", "transition": {"type": "pixelize"}},
    {"clip": "take2.mp4", "in": 3.0, "dur": 5.0, "title": "Drone Mothership boss"},
    {"card": {"title": "Fal Arsenal", "sub": "a Terraria mod"}, "dur": 2.5}
  ]
}
```
- **Transitions:** any ffmpeg xfade type (fade, pixelize, slideleft, smoothleft, circleopen, zoomin,
  radial...) or `cut`.
- **Fills:** for non-16:9 clips, `fill: blur` (blurred backdrop), `crop` or `pad`.
- **Per clip:** `speed` and `volume`, `zoom` to punch in past UI, `crop` [x, y, w, h] to reframe.
- **Music:** `um fal music "..." --seconds 60` makes a bed. Set `bpm` and use `beats` instead of `dur` to
  cut on the beat; `um video beats music.mp3` estimates tempo and first beat.

## Style that works (from real feedback)
- **Titles:** one line naming what's on screen ("Wonder: the Transamerica Pyramid", "Robotaxis and Delivery
  Drones"). No small explanatory captions about how it was made; that goes in the post text.
- **Pace:** get into gameplay within 2-3 s; menus and setup stay under 3 s. Clips run 3-5 s each. End on the
  mod name or URL and fade out.
- **Sound:** keep the game's audio. It sells impacts. Music under a compilation, clip audio around 0.5-0.8.
- **Compilations of other people's clips:** credit every creator on screen (`credit: "@handle"`) and in the
  post, and ask permission when it's promotional. Don't imply their clips were made with your tool. Download
  only public posts, and only what you'll use.
- **Last step:** look at a contact sheet of the finished video before sharing it.
