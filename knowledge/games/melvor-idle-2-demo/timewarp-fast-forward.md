---
kind: game
title: TimeWarp fast-forward via override.cfg autoload and physics ticks
game: Melvor Idle 2 Demo
games_also: []
game_version: 0.11.2-alpha.4 (steam 5373510)
platform: macos
engine: godot
route: other
tools:
- ilspycmd 11.1
- .NET SDK 10.0.402 (Homebrew)
anti_cheat: none found by um scan
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-21'
links: []
tags:
- godot-4
- dotnet
- csharp
- autoload
- override-cfg
- game-speed
- idle
---
# TimeWarp fast-forward via override.cfg autoload and physics ticks

> A hotkey that runs Melvor Idle 2's simulation 2-50x faster (gathering, crafting, combat). It is a single
> GDScript autoload that the game's own `user://` settings override loads, with no game files changed and no
> loader. It runs in the real game: the human saw mining speed up, and the mod's own tick counter logged
> exactly x2, x3 and x5 against the requested speeds.

## Setup
- Melvor Idle 2 **Demo**, Steam app 5373510, game version `0.11.2-alpha.4` (first lines of `godot.log`).
- macOS 27.0.1 on an Apple M5 (arm64). `Melvor2.app` is universal and ships both
  `data_GamesByMalcs.Melvor2_macos_arm64` and `..._x86_64`.
- Godot `4.7.2.stable.mono.official`. The `.pck` is format 4 with flags `0x2` (relative file base),
  and nothing is encrypted.
- Game logic is C# in `GamesByMalcs.Melvor2.dll` (net10.0), which `um scan` reports as "also: dotnet". The
  network layer is name-obfuscated (`A.U`, `A.W`); the gameplay code is not.
- For reading the code: `brew install dotnet` (SDK 10.0.402), then `dotnet tool install -g ilspycmd` (11.1),
  then `ilspycmd -p -o ~/melvor2-decomp GamesByMalcs.Melvor2.dll -r <data dir>`. Set
  `DOTNET_ROOT=/opt/homebrew/opt/dotnet/libexec`.
- User folder: `~/Library/Application Support/Games By Malcs/Melvor Idle 2/`. Saves are in
  `steam/<steamid>/saves/save_<uuid>.sav`, the log is `logs/godot.log` (the previous run's log is rotated to a
  timestamped name), and settings are in `device_settings/`.

## Route and why
`project.binary` sets `application/config/project_settings_override` to
`user://device_settings/override.cfg`, a file the game itself writes for window settings. Godot merges it
into the project settings before autoloads are created, so adding this registers our own node:
```ini
; timewarp
[autoload]
TimeWarp="*user://mods/timewarp.gd"
```
- GDScript loads from `user://` fine in this .NET export: the GDScript module ships in the mono templates,
  and the script is compiled from source at load.
- Not considered further: a Harmony or Cecil patch of the C# DLL (no loader exists, and it would change game
  files), and recovering the project with GDRE Tools (unnecessary for a one-script mod).
- Online check before building: the demo has a Nakama "N players doing this" presence counter, Steam rich
  presence and cloud saves. No hiscores, trading or shared economy appear in the DLL strings, so a local
  speed-up only affects the player's own save. The Steam page (app 3218350, which hosts the demo) agrees: it
  lists single-player, Steam Cloud, optional cloud profiles and presence, but no leaderboards or achievements,
  and says the game has "no microtransactions", so there is no paid time skip to undercut. If a later build adds
  hiscores or anything ranked, keep sped-up saves off it.

## How the game works (what we had to learn)
- **One tick per physics frame.** `GameDriver._PhysicsProcess` calls `Game.PropagateTick()` once and ignores
  `delta`. All action timers (`TickTimer`, `FillableTimer`, `QueuedTimer`) count ticks.
- **The tick length is cached.** `Constants.TickInterval` is `1000 / Engine.PhysicsTicksPerSecond`, computed
  in the static constructor. The project leaves physics at Godot's default of 60/s, so a tick is 16.67 ms. Only
  the `Constants.TicksPerSecond` setter recomputes it, and nothing calls that.
- So raising `Engine.physics_ticks_per_second` at runtime runs more 16.67 ms game ticks per real second:
  the whole simulation speeds up and its numbers stay consistent. `Engine.time_scale` only scales `delta`, which
  the game ignores, so it does nothing here.
- Godot runs at most `max_physics_steps_per_frame` physics frames per rendered frame (default 8). At the
  game's 60 fps cap that limits the speed to 8x unless the limit is raised too.
- **Offline progress** (`RunOfflineTicks`) loops `PropagateTick` on a background Task, using wall-clock time
  away, so it is unaffected by the mod.
- **Input:** the game's actions include `ZoomIn`/`ZoomOut` on Cmd+= and Cmd+-, plus `PauseResume`, `SaveData`
  and `SkipAnimation`. Autoloads are the first children of the root, and `_input` reaches nodes in reverse tree
  order, so the game's nodes see a key before an autoload does.
- Autosave ("Saving active save locally") runs every 10 s of real time regardless of the speed.

## Build steps
1. Back up the saves and settings: `um backup create ".../Melvor Idle 2/steam" --name melvor2-saves`, and the
   same for `device_settings`.
2. Write `timewarp.gd` (`extends Node`). On a key press it sets
   `Engine.physics_ticks_per_second = 60 * speed` and
   `Engine.max_physics_steps_per_frame = max(8, ceil(tps / 20))`, which leaves headroom down to about 20 fps,
   and keeps `time_scale` at 1. The keys are Option+] (faster), Option+[ (slower) and Option+\ (reset), and
   the speeds are 1, 2, 3, 5, 10, 25 and 50.
   - It counts its own `_physics_process` calls and logs `measured xN` every 2 s while sped up. A label shows
     the actual speed when it falls short of the target.
3. Copy the script to `user://mods/timewarp.gd` and append the `[autoload]` block above to
   `device_settings/override.cfg`. A small `install.sh` does both and has `--uninstall`, which strips only its
   own block. Restart the game.

## Verification
- **Load:** the log shows `[TimeWarp] loaded (base 60 ticks/s)` before the game's `Main` logs anything.
- **Speed:** the human mined copper at 2x, 3x and 5x and saw the progress bar speed up. Over about 30 s, the
  mod's per-physics-frame counter logged `measured x2.0`, `x3.0` and `x5.0`, matching each target at 120, 180
  and 300 ticks/s.
- **Uninstall:** `install.sh --uninstall` on a copy of `device_settings` produced a file byte-identical to the
  original.
- **Not verified:** 10x, 25x and 50x in game, which need 600-3000 ticks/s and up to 150 steps per frame; how
  much CPU one `PropagateTick` costs; saves written while sped up loaded in another session; behaviour during
  combat; the Windows build (same route, but the user path differs).

## Gotchas
1. **`Engine.time_scale` = 50 and nothing speeds up.** *Cause:* the game counts ticks per physics frame and
   ignores `delta`. *Fix:* scale `Engine.physics_ticks_per_second` and raise `max_physics_steps_per_frame`.
2. **Cmd+= / Cmd+- zoom the UI as well as triggering the mod.** *Cause:* those are the game's
   `ZoomIn`/`ZoomOut` actions, and the game's nodes receive `_input` before an autoload. *Fix:* use Option+]
   / [ / \, which nothing in the game binds.
3. **The `[autoload]` entry disappears after a settings change.** *Cause:* the game rewrites `override.cfg`
   when display settings change; it is not rewritten on a normal launch, as the file's mtime confirmed across
   sessions. *Fix:* run `install.sh` again.
4. **Reading `godot.log` right after relaunching shows the old session.** *Cause:* the log is rotated only once
   the new process starts. *Fix:* wait for the process and a line unique to the new build before grepping.
5. **`um kb new` crashes with `write_text() got an unexpected keyword argument 'newline'`.** *Cause:* without
   `uv`, `bin/um` falls back to the system `python3`, which is 3.9 on macOS. *Fix:* `brew install uv`.

## Assets
None.

## Cost and time
About one hour over three game launches. No API spend.

## Open questions
- What speed is the practical ceiling on a given CPU? The `measured` log line answers it per machine.
- Could a settings-page toggle replace the hotkeys? It would need the game's UI scenes from GDRE Tools.
- Does the full (non-demo) release keep the same `project_settings_override` path and tick model?
- Melvor Idle 1 has official mod support (mod.io, since October 2022). If Melvor Idle 2 gets the same, that may
  be a cleaner route than the settings override.
