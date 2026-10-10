---
kind: game
title: Max Payne bullet time, shootdodge and voice in Halo Trial via Chimera Lua on macOS/Wine
game: Halo Trial
games_also: ["Max Payne (Demo)"]
game_version: "Halo Trial (Halo PC demo) halo.exe FileVersion 01.00.00.0578, 2,785,280 bytes; Chimera 1.0.0.r1307.1f292fc; Max Payne Demo (2001), x_demodatas.ras 97,939,389 bytes"
platform: macos
engine: native
route: loader-api
tools: ["Chimera r1307 (global Lua scripts)", "GameHub Wine build 10000073", "mtld3d (D3D9 -> Metal)", "x87sidecar", "zig cc via `uvx --from ziglang` (Windows SendInput helper)", "afplay"]
anti_cheat: "None. Campaign only here; keep the script off on servers you don't host (Chimera server_type 'dedicated'). Max Payne Demo is single-player."
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-07'
links: ["https://github.com/ernestask/libras", "https://github.com/SnowyMouse/chimera"]
tags: [mashup, bullet-time, chimera, lua, wine, macos, ras, sendinput, sidecar, blam]
---
# Max Payne bullet time, shootdodge and voice in Halo Trial via Chimera Lua on macOS/Wine

> A Chimera global Lua script gives Halo Trial Max Payne's bullet time (flashlight key, 0.3x game speed, 5 s
> meter) and shootdodge (crouch + jump dives along your movement in slow motion). A small macOS sidecar plays
> Max Payne's own sounds, extracted from the user's Max Payne Demo `.ras` archive: slow-mo start/loop/end,
> shootdodge, get-hit grunts, painkiller and death lines, and the theme. Verified in the running game, driven by
> a Wine-side SendInput helper: the game speed read back as 0.30, and events and `afplay` were seen for every
> sound.

## Setup
- macOS (Apple Silicon) with GameHub's Wine build. Halo Trial lives in its own prefix (`~/Games/Halo Trial/prefix`)
  with mtld3d (D3D9 -> Metal) and x87sidecar (fast x87 under Rosetta). It runs windowed at 1280x800.
- Chimera r1307 is installed as `strings.dll`. Global scripts go in
  `My Games/Halo Trial/chimera/lua/scripts/global/`, and `write_file` output lands in
  `chimera/lua/data/global/<script>/`.
- Max Payne Demo sits in a separate GameHub container. Only its `x_demodatas.ras` is read.

## Route and why
This is a content-and-mechanics port (pattern 1 in the mashup-mods skill) through Chimera's Lua API, with no
injection beyond Chimera:
- The guest's content (sounds) is extracted from the user's own install.
- The guest's mechanics (bullet time, shootdodge) are reimplemented in the host with Lua.

Ruled out:
- **Custom maps or tags** for Max's model and sounds: Halo Trial can't load custom maps, the HEK targets
  Custom Edition, and embedded Lua is unsupported on Trial.
- **In-game audio from Lua:** Chimera's Lua has no sound API.

So audio goes through a file-based event channel to a host-side player.

**Campaign and games you host only.** Global scripts also run in multiplayer, and Trial has Blood Gulch over LAN
and online. Slowing the game and pushing your own biped on someone else's server is a speed hack, so the script
should return early when Chimera's `server_type` global is `"dedicated"` (you're a client). `"none"` is the
campaign and `"local"` is a game you host. Chimera's own `chimera_tps`, `chimera_teleport` and
`chimera_block_damage` refuse on `SERVER_DEDICATED` the same way.

## How the game works (what we had to learn)
- **RAS archives (Max Payne 1/2)** ([libras](https://github.com/ernestask/libras) has the details):
  - Header: a 44-byte header with `RAS\0` at offset 0 and the seed at +4. Everything from +8 onward is
    encrypted per byte: `seed = seed*171 - (seed/177)*30269`, rotate left by `i%5`, XOR with `(i+3)*6`,
    then add `seed & 0xFF`.
  - File table: each entry is the name, `\0`, then 6 u32 (size, entry size, ?, parent dir, ?, compression
    1 = LZSS / 3 = stored), then a SYSTEMTIME.
  - Compression: Okumura LZSS (N = 4096, F = 18), with the payload prefixed by `RA->` + original size +
    compressed size.
  - The demo's files are all stored uncompressed: 2,339 files, 752 of them WAV (MS ADPCM / PCM, which `afplay`
    plays).
- **Game speed:** a float at `game_time_globals + 0x18`.
  - Chimera finds the pointer with `game_speed_sig`
    (`A1 ?? ?? ?? ?? 66 89 58 10 66 8B 0D ?? ?? ?? ?? 66 83 F9 01 74 1E 66 83 F9 02`).
  - In Trial's halo.exe (fixed base 0x400000) the signature is at VA 0x46FC25, and its pointer operand is
    0x6E900C. So `write_float(read_dword(0x6E900C) + 0x18, 0.3)` gives bullet time. Ticks slow down with it, so
    scale per-tick meter drain by 1/speed.
- **Biped (`get_dynamic_player()`) offsets**, verified on Trial:

  | Offset | Field |
  |---|---|
  | +0x5C | position |
  | +0x68 | velocity in world units per tick (running is about 0.074) |
  | +0x74 | facing (x, y) |
  | +0xE0 | health (1.0 = full) |
  | +0xE4 | shield (1.0 = full) |
  | +0x208 | action flags, u16: bit 0 crouch, bit 1 jump, bit 4 flashlight, bit 11 fire |
  | +0x278 | forward input (−1 to 1) |
  | +0x27C | strafe-left input (−1 to 1) |

  The left vector is `(-fy, fx)`. Writing velocity for 2 ticks plus a z lift makes a dive: speed 0.09 with lift
  0.035 covers about 1.7 wu (about 5 m).
- **Health:** Halo CE health doesn't regenerate, only shields do. So a health increase means a health pack,
  which triggers Max's painkiller line.

## Build steps
1. Extract the sounds from your own demo: `python3 tools/ras.py x_demodatas.ras sounds/characters/ extracted`
   (also `max_theme`).
2. Copy `maxpayne.lua` into `chimera/lua/scripts/global/`.
3. Run `python3 tools/sidecar.py`. It polls `chimera/lua/data/global/maxpayne/events.txt` and plays the WAVs
   with `afplay`.
4. Launch Halo Trial. Use Q for bullet time and Ctrl + Space (while moving) for the shootdodge.

## Verification
- **Oracle:** the script's `write_file` event and diagnostics file (flags, speed, health, position, velocity
  every 10 ticks), plus screenshots and `ps` showing which WAV `afplay` was playing.
- **Driving:** a Wine-side `send.exe` (SendInput with scancodes) runs menu → Campaign → Continue, then
  presses Q, chords W/A + Ctrl + Space, throws grenades (right click) for damage and death, and fires (click).
- **Results:**
  - Bullet time: speed 0.30 read back, and `slomo_end` came 5 s after `slomo_start`.
  - Shootdodge: forward and strafe-left dives went in the right direction and the right distance, with all four
    events heard.
  - Damage: a self-grenade gave `hit`, and a grenade death gave `death`, then `spawn` at the checkpoint.
- **Not verified:** a real health-pack pickup. The painkiller path was tested with a debug hook that halves and
  restores health.

## Gotchas
1. **Synthetic input from macOS doesn't reach Halo under Wine.** osascript and CGEvent arrows, Tab and mouse
   moves did nothing; only Return got through. **Cause:** Halo reads DirectInput, which Wine feeds from its own
   input queue. **Fix:** a tiny Windows exe (built with `uvx --from ziglang python -m ziglang cc -target
   x86_64-windows-gnu`), run in the same prefix and wineserver, that calls `SendInput` with
   `KEYEVENTF_SCANCODE`. Arrows are E048 and E050.
2. **`execute_script("game_speed ...")` segfaults Halo Trial,** at halo.exe pc 0x4ce130 when called from the
   `map load` callback. **Fix:** never call `execute_script`; write the game-speed float directly (above).
3. **halo.exe shows process state `TX` and you think it crashed.** **Cause:** x87sidecar traces it, so TX is
   normal. A real crash shows a "Segmentation fault" dialog and a `fault outside` line in `mtld3d-logs`. After
   a real crash, `kill -9` does nothing; kill the two x87sidecar tracer PIDs for that instance instead.
4. **Chimera's `map` global is empty on Trial,** and the `map load` callback doesn't fire for the `ui` map
   loaded before scripts start. Don't use either to detect the menu.
5. **`execute_script("map_name b30")` from the menu crashes Trial,** so you can't skip the menu that way.
   Drive Campaign → Continue with SendInput.
6. **`chimera_reload_lua` replies "cannot be executed now".** **Cause:** there's no such command. Chimera's reload
   command is `chimera_lua_reload_scripts`, and Halo answers any unregistered command with
   `Requested function "..." cannot be executed now`. **Fix:** use `chimera_lua_reload_scripts` (not re-tested in
   this setup; restarting Halo also works).
7. **Events go missing.** **Cause:** `write_file(path, text)` truncates the file by default, so two events in one
   tick (dive `land` plus `slomo_end`) keep only the last. **Fix:** this project keeps the last 8 events with
   sequence numbers in the file, and the sidecar replays the new ones and resets when the counter drops (Halo
   restarted). `write_file(path, text, true)` appends instead (supported at Chimera 1f292fc), which is simpler
   for a reader that tails the file.
8. **The first dive flew about 18 m.** **Cause:** with low gravity, horizontal velocity carries through a long
   airborne arc. **Fix:** a small lift (0.035) and only 2 ticks of push.
9. **HUD spam.** `hud_message` stacks lines, so only post the meter when it crosses 25% steps.

## Assets
Only the user's own Max Payne Demo sounds, extracted locally and never committed or shipped. No generated
assets.

## Cost and time
About 3 agent sessions over two days, no API spend.

## Open questions
- Max's model and textures (`.kf2`/`.skd` in the RAS) can't get into Trial without custom map support. Halo
  Custom Edition or MCC Halo CE (with the official mod tools) would allow a real biped swap.
- A real health-pack pickup test, and dive animations (Halo has no prone or dive animation for the biped).
