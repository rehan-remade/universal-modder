---
kind: game
title: "The Dark Legions Reloaded: crash fixes, a D3D8 -> D3D9Ex renderer, widescreen and new menus in one d3d8.dll"
game: "The Dark Legions"
games_also: []
game_version: "1.1.0 (Mascot Entertainment, 2004), retail CD install, Windows 11 24H2"
platform: windows
engine: unknown
route: native-hook
tools: ["Rust 1.99 (i686-pc-windows-msvc, static CRT)", "Ghidra 12.1 (headless scripts)", "WinDbg / WER LocalDumps", "Process Monitor", "d3dcompiler_47 (runtime HLSL)", "dgVoodoo2 2.87.5 (studied, then replaced)"]
anti_cheat: "none (2004 single-player RTS; LAN multiplayer only, not touched)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["GR33N"]
date: 2026-10-09
links: []
tags: [d3d8, d3d9ex, proxy-dll, crash-fix, heap-corruption, widescreen, menus, fonts, fog, dgvoodoo, rts, 2004]
---

# The Dark Legions Reloaded: crash fixes, a D3D8 -> D3D9Ex renderer, widescreen and new menus in one d3d8.dll

> **The Dark Legions Reloaded is a mod by GR33N**, built with Claude Code.
> The Dark Legions (Mascot Entertainment, 2004; in-house "Strategy 3" engine, 32-bit C++, Direct3D 8) crashed
> randomly after minutes of play and drew blue blotches on modern GPUs. One Rust `d3d8.dll` dropped next to
> the exe now fixes the crashes, replaces Direct3D 8 with its own D3D9Ex renderer (supersampling + MSAA +
> Lanczos, sharper than dgVoodoo2), adds true widescreen, rebuilt Video/Advanced/Interface/Audio menus,
> sharper fonts with Cyrillic, faster loading and a working cfg file. Verified by playing: a save that
> crashed within 2-8 minutes ran 49 minutes; every change was checked on screenshots by the player.

## Setup
- Retail install, `Dark Legions.exe` 1.1.0 (credits screen). The exe carries Windows compatibility flags
  (WinXP SP2) in HKCU, so it asks for UAC; tools that inject must handle that.
- Game data in one archive `s3tdl.med`; settings in `s3tdl.cfg`; audio settings in `players.prf`.
- The mod: `d3d8.dll` only. It writes `reloaded.ini` (commented defaults) and `reloaded.log` itself.

## Route and why
Native hooks from a proxy `d3d8.dll`. First tried: a `wsock32.dll` proxy for the patches plus dgVoodoo2 for
graphics. That worked, but needed two files and a config, and dgVoodoo could not fix things inside the
game's rendering (2D layout, menus). Making `d3d8.dll` ours gave one file and full control of every
draw. Every byte patch checks the original bytes first and logs instead of patching if they differ.

## How the game works (what we had to learn)
- **The game logs everything to a disabled logger** (`#DEBUG:` lines through one function). Hooking it and
  writing the lines to our log was the single most useful source: texture names before each texture is
  created, screen names, load phases. We name textures by "Loading texture file:" / "Loading 2D Image:"
  lines and use the names to recognise screens (menus, HUD, splash) in the draw stream.
- **Crashes:** random heap corruption. Lists in the engine were re-initialised by setting their count to 0
  without clearing the nodes, so stale nodes kept pointers into freed memory. Calling the list's own Clear()
  before the reset (7 places) stopped it. A second crash was a dangling unit pointer after a tower is
  destroyed: a guard returns early. Objects with owner -1 read outside the players array: guarded.
- **Rendering:** projection with an infinite far plane (breaks table fog on today's drivers); the game turns
  D3DRS_CLIPPING off; asks for software vertex processing; rewrites managed vertex buffers hundreds of times
  per frame; the interface is XYZRHW quads in 1024x768 coordinates, big pictures cut into 256x256 tiles.
- **Menus** are widget containers built by one function per screen and driven by one click handler with
  the clicked widget's index; the same add-button / add-label / add-slider calls build our own screens, so
  new menus look exactly like the game's. Screen ids above the game's own are free to use.
- **Config bug:** the cfg reader accepts only CRLF lines, but the writer writes LF, so after the first
  save not one line is read again (63 "Invalid setting") and every option silently resets. Gamma and
  brightness are written as `int.(int - value)*100` ("1.-30"). Fixed by rewriting the file (CRLF, proper
  decimals) at start and right after the game saves it.
- **Audio:** one sound bank; a busy buffer skips a sound but keeps its volume, so the next play ignores the
  volume slider. Master volume is read as a constant 100 in five places.
- **File I/O:** the archive is read a few bytes at a time, each read with SetFilePointer + GetFileSize +
  ReadFile (1.4 million calls at start). A read-ahead buffer per read-only handle cut start-up from 5.2 s to
  1.7 s and a mission load from 8.4 s to under 1 s (with vsync off while loading).

## Build steps
1. `cargo build --release --target i686-pc-windows-msvc` (static CRT via `.cargo/config.toml`, version info
   from an `.rc`).
2. Copy `d3d8.dll` next to `Dark Legions.exe`. Remove dgVoodoo's `D3D8.dll` and any older proxy.
3. Start the game; edit `reloaded.ini` or use Options -> Video / Advanced graphics / Interface / Audio.

## Verification
- Crashes: WER LocalDumps + a triage script on every dump; long sessions on saves that crashed before.
- Graphics: frame-by-frame capture (every draw's state + picture after it, on a hotkey) to find which
  draw produced a bug; F11 screenshots at monitor resolution compared side by side with dgVoodoo.
- Performance: a sampling profiler on the main thread (1 ms) with phases from the game's log lines.
- Not verified: the Steam release (app 492530); multiplayer; hours-long AI-only soak tests; any PC but one
  (Windows 11, 2560x1600 monitor).

## Gotchas
1. **Blue blotches near the camera.** **Cause:** table fog + infinite-far projection. **Fix:** far plane 1e6.
2. **Wedges across the screen.** **Cause:** D3DRS_CLIPPING off. **Fix:** keep it on.
3. **Low FPS.** **Cause:** software vertex processing and managed-buffer rewrites. **Fix:** hardware VP and
   a range-only upload ring (see the D3D8 wrapper technique note).
4. **Leaves turned into blobs at 2x.** **Cause:** the tree textures rely on point filtering at 1x for their
   grain. **Fix:** per-texture filter by name (point / mixed / linear), anisotropic for everything else.
5. **The interface's first row/column shows the scene at 2x.** **Cause:** 2D corners at 0.5. **Fix:** map
   game x as (x - 0.5) * scale.
6. **Widescreen moved the mouse off the buttons.** **Cause:** centred menus. **Fix:** move the mouse back by
   the same offset; on stretched screens divide by the stretch.
7. **Small minimap icons from the menu folder dragged the whole HUD to the centre.** **Cause:** screens were
   recognised by texture folder. **Fix:** only pictures wider than 200 px mark a menu.
8. **Settings reset after every restart.** **Cause:** the LF/CRLF cfg bug above. **Fix:** rewrite the file.
9. **Splash and loading screens looked worse than under dgVoodoo.** **Cause:** linear filtering when
   stretching a 1024x768 picture. **Fix:** sharp-bilinear shader on those pictures, and stretch everything 2D
   in the same frame (progress bar, "Loading..."), or it drifts off the picture.
10. **The game kept running invisibly after Task Manager / Alt+F4.** **Fix:** terminate on WM_DESTROY after 3 s.
11. **Typed save names lost every non-ASCII letter.** **Cause:** a filter keeping only A-Z/0-9/_!.- .
    **Fix:** allow everything Windows allows in file names; Cyrillic glyphs drawn from a Windows font
    measured to the game's font metrics.

## Open questions
- Hours-long stability with AI-only games (the engine is full of "unreferenced pointer" warnings).
- A vector version of the game's fonts; an AI-upscaled texture pack.
