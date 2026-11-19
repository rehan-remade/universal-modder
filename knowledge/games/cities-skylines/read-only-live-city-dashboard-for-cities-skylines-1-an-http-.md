---
kind: game
title: 'Read-only live city dashboard for Cities: Skylines 1: an HTTP server inside a C# mod, built on Linux with mcs'
game: 'Cities: Skylines'
games_also: []
game_version: '1.21.1-f9, Steam build 22724702, native Linux, Unity 5.6.7f1'
platform: linux
engine: unity-mono
route: loader-api
tools: ['Mono mcs 6.12', 'a .NET decompiler (reading only, output kept outside the repo)', 'Python 3 (page assembly, mock server)', 'Chromium DevTools Protocol (headless page tests)']
anti_cheat: 'none: single-player game with a supported mod API (IUserMod), nothing bypassed'
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-11'
links: ['https://github.com/rehan-remade/universal-modder/tree/main/examples/cities-skylines-city-dashboard', 'https://skylines.paradoxwikis.com/Modding_API', 'https://skylines.paradoxwikis.com/Tiles']
tags: [dashboard, http-server, read-only, telemetry, simulation-thread, linux, mcs, i18n, mock-server, crash-on-save]
---
# Read-only live city dashboard for Cities: Skylines 1: an HTTP server inside a C# mod, built on Linux with mcs

> A C# mod that opens `http://127.0.0.1:19680` from inside the running game and serves a browser dashboard:
> all the city statistics, a vector map drawn from the game's own data, rule-based advice, charts and a
> day/night budget comparison. Route: the supported `IUserMod` API, compiled on Linux with plain `mcs` against
> the game's assemblies. It runs in the real game (a 128,000-inhabitant city, loading, playing, saving). One
> abort on save happened on the owner's machine with the mod installed and was never reproduced or explained,
> which is why the status is `in-progress`. Code: `examples/cities-skylines-city-dashboard`.

## Setup
- Cities: Skylines **1.21.1-f9**, Steam build 22724702, **native Linux** binary (`Cities.x64`), Unity 5.6.7f1
  with its bundled old Mono (C# 6 at most, .NET 3.5 profile: no tuples, no `out var`).
- Arch Linux, kernel 7.2. Compiler: Mono `mcs` 6.12.0. No Unity editor, no Visual Studio, no MSBuild.
- Other mods present in the player's game: 81 Tiles 2, TM:PE, Intersection Marking Tool, Harmony.
- Paths on Linux:
  - local mods: `~/.local/share/Colossal Order/Cities_Skylines/Addons/Mods/<ModName>/` (one folder per mod);
  - saves: `.../Cities_Skylines/Saves/` (Steam Cloud saves live under Steam's `userdata/<id>/255710/remote/`);
  - game log: `~/.config/unity3d/Colossal Order/Cities_ Skylines/Player.log` (note the space in the folder name).

## Route and why
**loader-api.** A CS1 mod is any class library with a class implementing `ICities.IUserMod`; the game loads
every DLL in a mod folder. Nothing else is needed for a read-only tool: every manager is a public singleton.
- Not a save-file reader: the `.crp` container is only partly documented, and the point was live data.
- Not memory reading or a native hook: the managed API already exposes everything.
- Not Harmony: nothing is patched. The mod only reads.
- The browser is the UI on purpose. In-game UI means the game's own UI framework; a web page can be built and
  tested with no game running (see Verification).
- The editors, the `.crp`/`.locale` containers and CS2 are covered in
  [the API and containers note](cities-skylines-modding-api-and-container-formats.md).

## How the game works (what we had to learn)
### Mod loading
- `IUserMod` needs `Name` and `Description`. `OnEnabled()` and `OnDisabled()` are optional and found by reflection.
- **The mod class is instantiated even when the mod is disabled** (the plugin manager needs the name). A constructor
  can therefore bootstrap: create a `GameObject` with a `MonoBehaviour`, mark it `DontDestroyOnLoad`, and on the
  first `Update` set its own `PluginInfo.isEnabled = true`. That value is persisted by the game.
- `PluginManager.FindPluginInfo(assembly)` only returns **enabled** plugins. To find yourself while disabled,
  walk `GetPluginsInfo()` and test `ContainsAssembly`. `PluginInfo.modPath` is the mod's folder.
- Assemblies are loaded from bytes, not mapped from the file. Overwriting the DLL in place while the game ran
  changed nothing every time it was tried here (no reload, no log line); the new code ran only after a restart.
  The game does reload mods while running in other setups: see Gotcha 4.

### Threads
- The **main thread** renders and runs `MonoBehaviour.Update`. The **simulation thread** owns the city data.
  There are also water, path-finding and audio threads.
- `SimulationManager.AddAction(Action)` queues work for the simulation thread. Queued actions run at the top of
  every simulation step **even while the game is paused**. The official `ICities` equivalent is
  `IThreading.QueueSimulationThread(Action)` (and `QueueMainThread` for the other direction).
- Reading managers from the main thread works but costs frames. Collecting a 9,600-building, 4,300-segment map
  into 1.6 MB of JSON took about 80 ms on the simulation thread; on the main thread that is a visible hitch
  every refresh.
- Saving is itself a queued simulation task: the save panel starts a coroutine, which queues a task that
  serializes everything into `Saves/Temp/<guid>.ccs`; only afterwards is that file packed into the `.crp`.
  The log line `Saved simulation data to: ...` is written only on success. A 0-byte `.ccs` left behind means
  the process died before the first flush.

### Where the numbers are
- `DistrictManager.m_districts.m_buffer[0]` is **the whole city**; index 1 and up are painted districts with
  the same fields. It has population by age and education level (with eligible workers and unemployed per
  level), per-sector blocks (homes or jobs, empty, building count, abandoned, happiness, level shares),
  imports and exports by product, and getter methods for every utility and service capacity and load.
- Units: electricity values are kW (divide by 1000 for the MW the game shows); water and sewage are m³/week;
  garbage is the game's raw unit. Money values are in hundredths.
- `EconomyManager`: cash, income and expenses per service, tax rates, and `GetBudget(service, subService, night)`.
- `ZoneManager`: the three demand bars. Zone blocks are 4 cells deep and up to 8 wide, 8 m per cell, with bit
  masks for valid, shared and occupied cells and a block angle; cell centres follow from position and angle.
- `ImmaterialResourceManager.CheckLocalResource(resource, position, out value)` gives service **coverage at a
  point** (fire, police, healthcare, deathcare, the three school tiers, public transport, entertainment) plus
  land value, noise and crime. Zero means out of reach. This is what makes "which buildings no hearse can
  reach" a one-line query.
- `NaturalResourceManager` holds a 512×512 grid of 33.75 m cells: ore, oil, fertility, forest, tree density
  and ground pollution, one byte each.
- Buildings: position, angle, and `Width`/`Length` in 8 m cells give the footprint. `m_problems.ToString()`
  lists the problem names (`Garbage`, `Death`, `NoGoods`, …) plus `MajorProblem`/`FatalProblem`.
  `BuildingAI.GetLocalizedStats` returns the same text the building's info panel shows ("Students: 232 / 910").
- Roads: a segment has two nodes and `m_middlePosition`, a point **on** the curve. The dashboard draws each
  segment as the quadratic Bézier through that point, whose control point is `2·M − (A+B)/2`. That's an
  approximation: the game's own curve is a cubic `Bezier3` from the node positions, whose inner points
  `NetSegment.CalculateMiddlePoints` derives from the segment's `m_startDirection`/`m_endDirection` (TM:PE's
  `GeometryUtil` does exactly this). `m_trafficDensity` is 0–100. `NetInfo.m_halfWidth` gives the width.
- Service vehicles: each building keeps a linked list of its own vehicles; the AI class has a count field
  (ambulances, hearses, fire trucks, police cars, garbage trucks, maintenance trucks). Available vehicles are
  that count scaled by the building's production rate.
- Budget to capacity is not linear: below 100% the production rate is the budget squared over 100 (80% → 64%),
  from 100 to 150% the gain tapers (150% → 125%), and upkeep follows the budget linearly. Inverting this turns
  "peak usage was 71%" into "this budget can drop to 95%".
- Day and night: `SimulationManager.m_isNightTime`, `m_currentDayTimeHour`, `m_enableDayNight`. Night is before
  05:00 and after 20:00, so 9 of 24 hours. Every service has a day budget and a night budget. Those hours come
  from the static `SimulationManager.SUNRISE_HOUR` / `SUNSET_HOUR`, which time mods such as Real Time and Rush
  Hour change; read them (or `m_isNightTime`) rather than hard-coding the hours.
- Map geometry: 17.28 km across, 9×9 tiles of 1,920 m. The base game lets the player buy 9 of them (the
  official wiki's Tiles page); tile borders are drawn for the middle 5×5, and mods raise the limit to 25 or 81
  (81 Tiles 2 was installed here). `GameAreaManager.MaxAreaCount` gives the current limit.
- Engine limits are plain buffer sizes: 49,152 buildings, 36,864 net segments, 32,768 nodes, 16,384 active
  vehicles, 65,536 citizen instances, 262,144 trees, 256 transport lines, 128 districts. Each manager exposes
  the current count next to the buffer.

### Gameplay facts the advisor rules encode
These came from a 128,000-inhabitant city played the same day, then confirmed in the dashboard:
- A full landfill stops sending trucks, so its area goes uncollected even with spare incinerator capacity.
- Bodies pile up for lack of reach, not of crematoriums: about 75 crematoriums clustered together still left
  roughly a fifth of the buildings uncovered.
- Unemployment concentrates among university graduates when schools outgrow office zoning.
- Outside highway connections can belong to a road system the city never touches. A union-find over road
  nodes finds them; until they are linked, imports starve.
- A water tower on polluted ground contaminates the whole network.

## Build steps
1. Reference the game's `Cities_Data/Managed` assemblies; copy nothing:
   `mcs -target:library -nostdlib -noconfig -langversion:6 -r:mscorlib.dll -r:System.dll -r:System.Core.dll
   -r:Assembly-CSharp.dll -r:ColossalManaged.dll -r:ICities.dll -r:UnityEngine.dll -out:Mod.dll Mod.cs`
   (each `-r:` with the full path into `Managed`). `-nostdlib -noconfig` makes `mcs` use the game's own
   `mscorlib` instead of the system one.
2. Copy the DLL and the page into `Addons/Mods/<ModName>/`. Start the game.
3. In the example: `./build.sh` does both; `./build.sh --page` updates only the page, which the mod re-reads
   from disk on every request, so page work needs no game restart.
4. No game at hand: `python3 tools/mock_game.py` serves the page against a synthetic city in the same wire format.

## Verification
- **In the real game:** every route returned valid JSON for a loaded 128k city, paused and at speed 3; the
  day/night sampler crossed a dusk and filled both buckets; a brand-new empty map returned sane values.
- **Saving with the mod installed** worked in three scripted runs (loaded city, new city, and after swapping
  the DLL on disk), each with a client polling all routes every 2 s. Those runs started the game binary
  directly (`SteamAppId=255710 ./Cities.x64`), not through the launcher.
- **The page:** driven in headless Chromium over the DevTools Protocol (clicks, hover, console errors,
  screenshots) against the game and against the mock, in both languages, at 420, 1680 and 2560 px wide.
- **Not verified:** Windows, macOS, the Epic build. Districts and transport lines with a real city that has
  them (only injected data and the mock). A session longer than a few minutes of polling in a test run. The
  abort on save described in Gotcha 1.

## Gotchas
1. **The game aborted one second into a save, with the mod installed, and a city was lost.** The process got
   SIGABRT, the temp `.ccs` stayed at 0 bytes, and the city had never been saved before. **Cause:** unknown.
   Three scripted save runs with the same DLL and a run of the newer build did not reproduce it; those ran the
   binary directly while the crash happened in a session started through the Paradox launcher, so the mod is
   not cleared. The evidence was lost because the player reopened the game, which truncates `Player.log`.
   **Fix (what to do instead):** before installing any mod for someone, back up their saves and make them save
   the current city; test load, play, **save** and quit yourself, started the same way the player starts the
   game; and when a crash is reported, first run `coredumpctl list` and copy `Player.log` before anything
   relaunches the game.
2. **Starting a second city in the same session breaks the game.** Loading or creating another city without
   quitting threw `Argument is out of range` while deserializing game-area data, then the simulation logged a
   null-reference on every step, and quitting hung at `Waiting for simulation to quit...`. **Cause:** not this
   mod: it reproduces with this mod removed. Most likely stale state in other mods' patches across loads (81
   Tiles 2, which changes the game-area data, and TM:PE were loaded); a run without them wasn't tried.
   **Fix:** one city per process. When scripting tests, restart the game for every load.
3. **The mod's server never started on a fresh install.** **Cause:** the mod was disabled, and the self-enable
   code looked itself up with `FindPluginInfo`, which skips disabled plugins. **Fix:** iterate `GetPluginsInfo()`
   and match with `ContainsAssembly`.
4. **Overwriting the DLL in place while the game ran did nothing, silently.** **Cause:** not established. The
   game can reload mods while running: the official Modding API page says extensions' `OnCreated`/`OnReleased`
   also run "when recompiling a mod while the game is running", and TM:PE handles an in-game hot reload. Other
   mods' build scripts trigger it by deleting the DLL and then copying the new one (NetworkAnarchy's `.csproj`,
   "trigger hot reload"), and many give every build a new version (`[assembly: AssemblyVersion("1.0.*")]`).
   Here the DLL was overwritten in place, and with no `AssemblyVersion` every build is 0.0.0.0; whether either
   change makes the reload work wasn't tested. **Fix:** restart to test C# changes (given Gotcha 1, the safer
   choice anyway); keep anything you iterate on (here, the whole page) in files the mod reads at request time.
5. **Polling the map made the game stutter.** **Cause:** collection ran on the main thread through a
   `MonoBehaviour` queue. **Fix:** queue it with `SimulationManager.AddAction`, keep the main-thread queue only
   as a fallback after a timeout, and let the client stretch its interval to a multiple of the measured cost.
6. **`Player.log` from the crash was gone.** **Cause:** Unity truncates it on every start. **Fix:** copy it
   first. The example's author now keeps a watcher that copies the log every 15 s while the game runs.
7. **A custom window-close shortcut did not close the frozen game.** **Cause:** most likely the process had
   already aborted and systemd-coredump was writing a multi-gigabyte dump (about a minute, by its own log); the
   window stays on screen meanwhile. **Fix:** wait for the dump, then read `coredumpctl info <pid>`.
8. **Core dumps of the game were useless for a stack.** **Cause:** the game runs inside Steam's runtime
   container, so the library paths recorded in the dump do not exist on the host and gdb could not unwind it.
   **Fix:** rely on `Player.log`, which gets the managed stack when the runtime dies in the open.
9. **Translating the UI broke the script.** **Cause:** English text with apostrophes (`residents' health`) went
   into single-quoted strings. **Fix:** escape the quote character of the literal when substituting text.
10. **A word was both a JSON key and on-screen text**, so translating by text would have renamed the key.
    **Fix:** translate only whole string literals from an explicit table, and special-case the few literals
    where one word plays both roles.
11. **Headless screenshots of the canvas map came out blank.** **Cause:** `--screenshot` with a virtual time
    budget captures before the last animation frame. **Fix:** drive the browser over the DevTools Protocol and
    capture in real time.
12. **A shell `pkill -f <pattern>` killed the agent's own shell**, twice. **Cause:** the pattern text is part
    of the shell's own command line. **Fix:** kill by PID read from `/proc/<pid>/cmdline`.

## Assets
None from the game and none generated. The map is drawn in a `<canvas>` from numbers; icons are small inline
SVG paths written by hand; screenshots in the example come from the synthetic city.

## Cost and time
One long session (about 3 hours of work on the dashboard, after a day of agents playing the same game through
another mod). Roughly 15 game restarts for C# changes; page changes needed none.

## Open questions
- What aborted the game on save (Gotcha 1)? Is it reproducible when the game is started through the launcher,
  with a browser tab polling for an hour?
- Does a long session of large JSON strings (a megabyte every 2 s) fragment the old Boehm heap enough to matter?
  Streaming the response or reusing buffers would remove the question.
- A history with more than 14 columns (utilities, traffic, sick, dead) needs a CSV format that tolerates old rows.
- Windows and macOS: the code uses nothing Linux-specific, but nobody has run it there.
- Does deleting the DLL and copying the new one, or a new `AssemblyVersion` per build, make this build reload
  the mod while running (Gotcha 4)?
