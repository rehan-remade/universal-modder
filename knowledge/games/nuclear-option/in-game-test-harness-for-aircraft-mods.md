---
kind: game
title: "An in-game test harness for Nuclear Option aircraft mods: command-file test plugin, state restore, and rules learned the hard way"
game: "Nuclear Option"
game_version: "Early Access 0.34.3 to 0.34.6 (Steam app 2168680, Unity 2022.3.62f2 Mono); decompile checked against the 0.34.6 build"
platform: windows
engine: unity-mono
route: loader-api
tools: ["BepInEx 5.4.23.5", "HarmonyX (bundled with BepInEx 5.4.23.5)", "dev plugin targeting netstandard2.1", "universal-modder 0.2.0 (um win launch / drive / shot, um backup)", "Python 3 offline stubs", "Git Bash scripts"]
anti_cheat: "none found; single player only (Free Flight / offline missions), never on public servers"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-11-22
links:
  - "https://github.com/riseofthewolfremake-lgtm/HeritagePairs-NuclearOption"
  - "https://github.com/BepInEx/BepInEx"
tags: ["test-harness", "oracle", "dev-plugin", "command-file", "flight-test", "performance", "state-restore", "offline-stubs", "aircraft"]
---

# An in-game test harness for Nuclear Option aircraft mods

> While building six new aircraft for Nuclear Option (the Heritage Pairs Blueprinter addon, see
> [the overview note](new-aircraft-with-blueprinter-nobp-b25h-ga25x-nimrod.md)), the agents tested in the real game with a
> dev-only BepInEx plugin that reads a command file and logs `[TH]` lines, driven by shell scripts. Each session was
> wrapped in a backup / restore / diff protocol, and Python stubs that re-implement the game's equations served as
> offline oracles between sessions. This note records the harness, and above all the rules it taught us: about a
> third of the "aircraft bugs" we chased in early sessions were made by the harness itself.

## Setup
- **Game:** Nuclear Option Early Access 0.34.3, later 0.34.5 and 0.34.6 (Steam, Windows 11), windowed 1600 x 900
  (`-screen-fullscreen 0 -screen-width 1600 -screen-height 900`), so `um win drive` click points stay fixed.
- **Loaders:** BepInEx 5.4.23.5 with HarmonyX, Blueprinter 2.1.1 for the aircraft themselves. The harness is a
  separate plugin and never part of the shipped addon.
- **Dev plugin:** a C# class library (`netstandard2.1`, references the game's `Assembly-CSharp.dll`, Unity and
  BepInEx), about 2,200 lines over seven files: the core interpreter plus modules for take-off logging, wheel /
  hook logging, weapon monitoring, ground-turn probes, carrier work and visual dumps. It is in the project's private
  repo only; the public repo's publishing script blocks any path containing `testhelper`.
- **Driver:** `um win launch`, `um win drive --proc NuclearOption` (clicks, keys, `idle`), `um win shot` for
  screenshots, and Git Bash functions sourced from one helper script.
- Paths below: `<GameDir>` is the game folder, `<SaveDir>` is `%USERPROFILE%\AppData\LocalLow\Shockfront\NuclearOption`.

## Route and why
- **Command-file plugin over input injection.** Flying an aircraft by synthetic keyboard and mouse can't hold a
  speed or a heading, and can't read g, gear loads or damage. A plugin inside the game can: it sets the pilot inputs
  each physics step, reads any field by reflection and logs numbers. It's the same idea as
  [driving a game from a mod-side command file](../../techniques/driving-a-game-from-a-mod-side-command-file-lab-profile-wake.md),
  applied to a flight sim. `um win drive` was kept only for menus (Singleplayer, Free Flight, faction, base,
  aircraft, purchase, FLY).
- **Not a socket bridge:** a file needs no port and is easy to append to from Bash. 0.5 s polling was fast enough,
  because the plugin, not the agent, runs every time-critical loop (pilot modes, holds, logs).
- **Offline stubs as well as the game:** a game session takes a long time and needs the PC to be free (see Idle guard). Most fixes
  were first proved against Python re-implementations of the relevant game code, and the game run then confirmed them.

## How the game works (what we had to learn)
Engine facts the harness depends on, checked against the 0.34.6 decompile (symbols named, no code copied):
- **Input path.** The player's stick reaches the control surfaces through `PilotPlayerState` (its `PlayerAxisControls`
  and `PlayerThrottleAxis1Controls` methods) and then `Aircraft.FilterInputs`, where the fly-by-wire
  (`ControlsFilter`, a `FlyByWire` member) shapes pitch. A test pilot has to write its inputs *before* the filter. A
  postfix on the throttle method runs after the filter in the same frame and overwrites the shaped stick with the raw
  one (Gotcha 6).
- **Pilot state.** `Pilot.currentState` (a `PilotBaseState`) is what flies: player, AI take-off / landing / taxi
  states. The helper logs its type name as `pstate=`. After a teleport with speed it reads null, and then nothing
  flies the aircraft (Gotcha 1).
- **Finding the aircraft.** Aircraft are found by `definition.jsonKey` (plus `playerRef` for the player's own) or by
  `unitName`. `FindObjectsOfType<Aircraft>()` is expensive, so cache the result, misses included (Gotcha 9).
- **Damage and break-up hooks** used as observers (prefix / postfix that never skip): `UnitPart.ApplyDamage` (with
  a stack trace: who hit us), `UnitPart.OnJointBreak` and `AeroPart.Detach` (what broke, at what speed),
  `LandingGear.BreakWheel` (logged as `BREAKWHEEL`), `Unit.RegisterHit` (hits, including on ourselves), and
  `Missile.Detonate` (logged as `DETONATE`: weapon, armed state, what it hit, distance from the test aircraft). A `nodmg` switch drops damage to the test aircraft in the
  `ApplyDamage` prefix. That one does skip, and it is only ever on for envelope probes.
- **Airbases.** `Airbase` objects carry a `networkUniqueName`. The `rwy` command finds one by name, picks a runway
  index and direction, and places the aircraft at rest on the runway threshold.

## Build steps
1. **The plugin.** One `BaseUnityPlugin` whose `Awake` applies its Harmony patches and logs the command-file path.
   `Update` checks `<GameDir>\BepInEx\<name>_cmd.txt` every 0.5 s of unscaled time, reads all lines, deletes the
   file and runs each line through one `switch`. `FixedUpdate` runs the active pilot mode and the samplers. Every
   output line starts with `[TH]`, so `grep -a "\[TH\]" LogOutput.log` gets it, and long series go to their own
   CSVs next to the log (`th_wlog.csv`, `th_plog.csv`, `th_wmon.csv`).
2. **Commands we ended up needing** (about 150; the useful core):
   - *Placement:* `rwy <base> [runway] [reverse]`, `hspawn` (carrier hangar spawn), `spawn` / `spawnship` /
     `spawnveh` for targets. There is also `airstart` and `rwyapp`; see Gotchas 1 to 3 before using them.
   - *Camera:* `cockcam <yaw> <pitch> [fov]`, `cam <pan> <tilt> <dist>`, `campart` (orbit a part, even after it
     has come off), `camat` / `camw` (camera at a point in the aircraft's or a part's frame), `gamelook` (drive the
     game's own cockpit camera pan / tilt).
   - *Pilot modes:* `ctl on <pitch> <roll> <yaw> <throttle> <brake>` (raw inputs), `pilot takeoff <rotate m/s>`,
     `alth <m>` (altitude hold), `spdh <m/s>` (speed hold by pitch), `hdg`, `rudhold`, `land`, `approach`,
     `ai` (hand back to the game's AI), `pilot off`.
   - *Systems:* `gear up|down`, `flaps`, `hook`, `station <i>`, `fire station <i> <s>` / `fire guns <s>`,
     `cmfire`, `eject`, `livery <i>`, `timescale`.
   - *Reflection:* `getf <goName|*> <Component> <field>` and `setf ...` to read or poke a field on the test aircraft
     at runtime, so a fix can be tried before the generator is changed.
   - *Logs:* `state` and `watch <s>` (speed, altitude, radar altitude, attitude, g, inputs, pilot state),
     `tolog` (take-off force balance), `wlog` (per-wheel enabled / steer / load / friction / brake plus hook),
     `plog <key>` (every aircraft of a type, for AI behaviour), `wmon` (AI attack mode, target, range, ammo per
     station), `glog` (load factor from the velocity difference plus fly-by-wire internals), `aiwatch`, `jmon`
     (joint stress), `fps <s> <tag>`, `rendstat`, `hpsum`.
3. **Bash side.** Source a script that defines `c "cmd" ...` (append lines to the command file), `w <regex>
   [timeout]` (wait until the log has a *new* matching line), `th` (last `[TH]` lines), `errs` (exceptions and
   `[Error` lines), `shot <name>` (window screenshot, a half-size copy for reading), `launch` (clear the log, start
   windowed, wait for the loader's "Done" line) and menu macros (`to_hangar`, `respawn`). A typical run:
   `c "key B25H" "rwy Maris 0" ; sleep 3 ; c "pilot takeoff 50" ; w "RESULT liftoff" 90 ; c "watch 1"`.
4. **Session protocol** (every game session):
   - *Before:* `um backup` of the saves folder (a zip), sha256 of every BepInEx `.cfg` we or the game could touch
     (16 to 17 files) and of `recent_missions.json`, a registry export of the game's key (resolution, vsync, quality),
     and a listing of `BepInEx\plugins` and `BepInEx\disabledPlugins`.
   - *Copy the helper in* to its own folder under `plugins`. Launch with `um win launch`, note the process id, close by
     that id at the end (never by name).
   - *After:* move the helper DLL out to a dated folder outside the game, then check with
     `find <GameDir>/BepInEx -iname "*testhelper*"` (expect nothing) and that no command file is left.
     Re-hash the cfgs and restore any the game rewrote (it rewrote our own instruments cfg at launch more than once).
     Compare `recent_missions.json`, compare the saves (expect only `Player.log` / `Player-prev.log` to change),
     diff the registry (expect only Unity session counters) and the two plugin listings.
   - Mods the user or the mod manager (NOMM) put in `disabledPlugins` stay where they are. Our tooling never
     moves them, and a report never says who moved them unless that is proven (Gotcha 13).
5. **Offline oracles between sessions.**
   - Python stubs re-implement the game equations that matter for a fix: flight model and fly-by-wire, gear drop on
     spawn, ground yaw of a taildragger, tail-hook arrest (`TailHook` / `ArrestorGear` / `LandingGear`), a gun's
     tracer counter, and a fuse's ground `Linecast`.
   - Each stub is fitted to an in-game log before its predictions count.
   - A **sync test** parses the constants out of the C# generators and plugin, and fails when they differ from the
     stub's. A fix proved in the stub can't silently drift from the shipped build.
   - One runner script runs every stub and sync check (over 1,300 rows by the end).
   - **Pinned rows:** rows that assert "unchanged since release X" are listed per released version in a JSON file
     with the reason and the base commit. A release-lock check (no released aircraft's file differs from the last
     public release) holds them together. A pinned row counts as passing only while every release-lock row passes,
     so new work can't silently alter a shipped aircraft.

## Verification
- **Oracles:** `[TH]` log lines and CSVs; the plugin's own `LogOutput.log` lines (`BREAKWHEEL`, `DETONATE`, the wing-fold start / end lines of our shipped plugin); `Player.log` exception counts (`errs`); screenshots
  read by the agent as contact sheets (many shots on one image, a half-size copy of each); and for performance,
  `fps <s> <tag>` windows (average, 1 % low, median, max frame, camera mode, GC count, vsync state).
- **The harness was itself checked with deliberate failures.** Most stub suites carry a FAILURE PATH row: the
  previous, broken build or code path is run through the same check, and the check must fail on it. For example, the
  NOMNOM manifest check writes a copy of our manifest with a required field removed (`isAiAssisted`), and the schema
  checker must reject that copy. The performance fault in Gotcha 9 was found by an A/B in game: same view, vsync off
  at runtime, 10 s windows, changing only the helper's lookup key.
- **Each finding was confirmed by the user's own play** of the released versions, or rejected by it (several of
  our "verified" visual results were rejected by the user, which is why screenshots now go through contact sheets
  and a stock comparison).
- **NOT verified:** multiplayer (everything was single player, host only); controllers other than the PC the
  harness ran on; whether the `Pilot.currentState` null after a teleport is a game bug or expected behaviour (we only
  stopped teleporting); the cause of one restart hang after about 51,000 null-reference exceptions from crashed and
  helper-destroyed aircraft in one session (not reproduced).

## Gotchas
1. **Handling looked dead after a mid-air spawn.** No stick response, throttle 0, a dive from 700 m. **Cause:**
   teleporting with speed (`airstart`, `rwyapp` with a distance) leaves `Pilot.currentState` null, and with no pilot
   state the fly-by-wire outputs nothing. On one B-17G the aircraft also vanished about 25 s later. **Fix:** never
   judge handling after a teleport-with-speed. Always do a real take-off (`rwy` then `pilot takeoff`), and use
   `airstart` (speed 0) only when looking at a model.
2. **A second `rwy` on the same spawn wrecked a B-17G** (gear and engines broke). **Cause:** re-placing a heavy
   aircraft already on the ground. **Fix:** one `rwy` per spawn. Respawn through the map for another start.
3. **`airstart` from inside a hangar shelter left the pilot "dead".** **Cause:** the same lost pilot state, reached
   from a parked spawn. **Fix:** `rwy` first, never `airstart` inside a shelter or on a parked aircraft.
4. **Aircraft flew into hills during holds.** **Cause:** the helper's altitude holds and glide path ignore terrain,
   and holds below about 900 m flew into the hills around the test airbase. **Fix:** no helper altitude hold below 900 m there, no
   heading target below 300 m AGL (a climb-out turn at 18 m dragged a wing), and climb before a speed hold (`spdh`
   right after lift-off pitched into the ground).
5. **"Unexplained structural break-ups" in level flight.** **Cause:** Free Flight has enemy bases. A radar SAM 15 km
   away hit the aircraft, and the joints of the 0-hp parts then broke, which looked like an airframe failure.
   **Fix:** a damage log on `UnitPart.ApplyDamage` with the stack (who hit what), a `nodmg` switch for envelope
   probes, and tests flown on a heading away from the enemy bases.
6. **Impossible 9 to 10 g pulls on a fly-by-wire jet.** **Cause:** the helper set the stick in a postfix that ran
   after `Aircraft.FilterInputs`, so the control surfaces saw the raw stick and not the fly-by-wire output
   (elevator 0 deg while the FBW said -1). Every g, stall and departure number until then had been flown without the
   pitch law. **Fix:** set inputs before the filter. The late hook sets only throttle and brake. Throw away every
   number taken through the old path.
7. **AI "spirals into the sea".** **Cause:** the helper's input override applied to every aircraft of the tested
   type, AI wingmen included. **Fix:** apply overrides only to the one test aircraft (`ac == Ac()`), and treat AI
   observations from before the fix as invalid.
8. **Stale state across respawns.** A pilot mode from the last aircraft drove the new one, and Restart Mission
   reset loadout and fuel to the default. **Fix:** send `pilot off` before FLY, and set loadout and fuel again after
   every restart. Check fuel too: one long full-power run (about 20 minutes) quietly became an engine-out test when the tank ran dry.
9. **The user's game ran at single-digit fps in our new cockpit.** **Cause:** the helper had been left in `plugins`.
   Its aircraft lookup cached only hits, so with a lookup key that matched no aircraft it ran
   `FindObjectsOfType<Aircraft>()` three times every physics step. Same view, vsync off: 313 fps with a matching key,
   33 fps without. Slow frames run more fixed steps, so it got worse at higher resolution. The cockpit mesh was not
   the cause. **Fix:** cache misses too (3 s), remove the helper after every session and check with `find`, and when
   a user reports lag, first look in `LogOutput.log` for test-only plugins.
10. **A/B frame times that disagreed.** **Cause:** vsync on (the game's default) caps both sides at the refresh rate,
    and the first frame of a window can include the command-poll frame. **Fix:** set vsync 0 at runtime only (not
    saved), use 10 s windows, drop the first sample, and run a control aircraft in the same session.
11. **A test waited hours for an idle PC.** **Cause:** the idle guard (Windows `GetLastInputInfo` via
    `um win drive idle`, plus the foreground window) only waits, and the user was at the PC. Also, in flight the idle
    probe reads 0 because the game locks the cursor, and in one session it stayed at 0 all along while the registry showed a gamepad had been connected (likely, not proven, the cause).
    **Fix:** when a test needs the PC and the user is on it, tell them in one line at once and offer the choice: they
    test with the exact switch, or step away. Never poll for hours. While driving, abort on a cursor move or a new
    foreground window that we didn't start, not on idle alone. Unity Hub, started by our own offline build worker,
    once tripped the guard.
12. **A worker fought the user for the mouse.** **Fix:** if input appears that the worker didn't cause, pause and
    report. Close the game before long offline work too: a game sitting idle on a menu looked stuck to the user.
13. **Mods "moved" to `disabledPlugins`.** About 30 mods were found in `BepInEx\disabledPlugins`. Our report
    blamed the user, but the evidence pointed at a mod-manager run and at our own tooling (our helper DLL had also
    been left there). **Fix:** never move or write anything in `disabledPlugins`. Report changes found there as
    "cause unknown", and list both folders before and after each session.
14. **When a result looks impossible, the harness is the first suspect.** In order, Gotchas 1, 5, 6, 7, 8 and 9 all
    looked like aircraft faults at first. **Fix:** give every investigation a timebox (about 30 min, about 2 h per
    session) with an interim status, and before blaming the mod, re-check the harness path (pilot state, override
    scope, damage source, fuel, lookup key).
15. **`hspawn` on an occupied carrier deck spot spawned nothing**, and `spdh` at full power couldn't hold a low speed
    on a heavy aircraft without a very steep climb. **Fix:** pick a free spot, and use part throttle when slowing
    for an approach.

## Assets
None. The harness makes no art. Evidence lived in the project's media folders (screenshots, contact sheets, logs),
which are kept out of the public repo.

## Cost and time
The harness grew over about 20 days alongside six aircraft. The GA-25X 0.2.0 session ran over five hours, mostly on
false leads from Gotchas 5 and 6, and the timebox rule came out of it. Game sessions then mostly fitted in 1 to 2
hours, because the stubs settled most questions before the game was launched.

## Open questions
- Why exactly a teleport with speed nulls `Pilot.currentState` (we never traced it; we only avoid it).
- A cleaner way to give a test aircraft a valid airborne start, for example by spawning it the way the mission
  editor does for air units, instead of moving a ground spawn.
- Whether a single command, `cleanup`, could run inside the game before quitting and do the whole session restore
  (helper removal can't, because the DLL is loaded, so the outside script still has to do it).
- See [oracles: how agents know a mod works](../../techniques/oracles-how-agents-know-a-mod-works.md),
  [driving real games safely](../../techniques/driving-real-games-safely.md) and
  [prove your replay bench can fail](../../techniques/prove-your-replay-bench-can-fail-mutant-builds-exposed-four-.md)
  for the general versions of these rules.
