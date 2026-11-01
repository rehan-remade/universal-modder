---
kind: game
title: "TES Arena in Daggerfall Unity: three-platform .dfmod builds, background tests, DOSBox reference"
game: "Daggerfall Unity"
games_also: ["The Elder Scrolls: Arena"]
game_version: "Daggerfall Unity 1.1.1 (portable), Unity 2019.4.40f1; Arena CD version (ACD.EXE) with its bundled DOSBox 0.74"
platform: windows
engine: unity-mono
route: loader-api
tools: ["Unity 2019.4.40f1", "Unity Hub 3.20 + Unity CLI 1.0.0-beta.13", "UnityPy 1.25", "DOSBox 0.74", "um publish check"]
anti_cheat: "none"
status: released
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-11-01
links: []
tags: [daggerfall-unity, dfmod, assetbundle, unity-2019, cross-platform, unity-cli, licensing, self-test, background-testing, dosbox, reference-oracle, bring-your-own-game]
---

# TES Arena in Daggerfall Unity: three-platform .dfmod builds, background tests, DOSBox reference

> A Daggerfall Unity mod that reads the player's own TES: Arena install at startup and adds Arena's towns, dungeons,
> wilderness sites, creatures and spells to DFU (no Arena files shipped). Built from the command line into Windows,
> macOS and Linux `.dfmod` bundles, tested by an in-game self-test that runs unattended behind the user's windows,
> and compared against the original Arena driven in DOSBox. Released as 1.1.2; Windows play-tested, macOS/Linux
> built and platform-checked but not play-tested.

## Setup
- Windows 10, Daggerfall Unity 1.1.1 portable build used only for tests, the DFU source fork opened in Unity
  2019.4.40f1 (on an external drive, registered with Hub for modules), Python 3.14 with Pillow/UnityPy, the
  player's own Arena CD install (free from Bethesda) with its bundled DOSBox 0.74.

## Route and why
- DFU's official mod system: a `.dfmod` is a Unity **AssetBundle** holding the mod manifest, `modsettings.json`,
  data files and the C# sources as `.cs.txt` TextAssets. DFU compiles the C# at load time (Mono), so the code is
  platform-neutral but the **bundle is not**: AssetBundles are per build target.
- Fork of the DFU Unity project with the mod under `Assets/Game/Mods/<Mod>`; an editor script mirrors DFU's Mod
  Builder (`Assets/Game/Addons/ModSupport/Editor/CreateModEditorWindow.cs`) without its dialogs.

## How the game works (what we had to learn)
- DFU loads every `.dfmod` in `StreamingAssets/Mods`, reads the bundled manifest, compiles the `.cs.txt` sources
  and calls the mod's `[Invoke]` init; save data goes through DFU's mod save interface; settings come from the
  bundled `modsettings.json` (write it with DFU's own `ModSettingsData` so the format matches the DFU version).
- Arena's data is read at runtime from the player's install (GLOBAL.BSA, .MIF/.INF maps, ACD.EXE tables after
  PKLITE unpacking); formats ported from OpenTESArena (MIT).

## Build steps
- **Build from the command line:** `Unity.exe -quit -projectPath <dfu fork> -executeMethod <Ns>.Builder.Build
  -logFile build.log` (windowed editor, *not* `-batchmode`: a Personal licence did not work in batch mode here).
  Copy each script to a temp folder as `<name>.cs.txt`, write a manifest copy whose `"Files"` list names every
  asset (text edit, not a JsonUtility round trip: DFU reads it with FullSerializer), then
  `BuildPipeline.BuildAssetBundles(dir, map, ChunkBasedCompression, target)` for each of
  `StandaloneWindows`, `StandaloneOSX`, `StandaloneLinux64` (DFU's own three).
- **Fail the build script on every target:** delete all three outputs first and require all three afterwards.
  A failed `BuildAssetBundles` only logs `Debug.LogError`; grepping for `error CS` alone misses it and a stale
  bundle from the previous build ships.
- **Check what you built:** UnityPy reads the target per bundle:
  `{o.assets_file.target_platform for o in UnityPy.load(p).objects}` gives 5 (StandaloneWindows), 2 (StandaloneOSX),
  24 (StandaloneLinux64).
- **Release zip:** `Windows/`, `macOS/`, `Linux/` folders each with the same-named `.dfmod`, a README naming the
  Mods folder per OS (macOS: `DaggerfallUnity.app/Contents/Resources/Data/StreamingAssets/Mods/`) and a checksum
  per file. `um publish check <unzipped release> --game "<Arena folder>"` confirms no original game file ships.
- **Unattended in-game tests:** the mod contains a `SelfTest` MonoBehaviour started by a flag file in
  `StreamingAssets/<Mod>/selftest-autorun.txt` (mode name on line 2). A bash runner backs up `settings.ini`, sets
  windowed 1280x720, `RunInBackground = True`, zero volumes, writes the flag, launches the portable DFU behind
  other windows, waits for exit, restores everything, and prints `SELFTEST PASS/FAIL` lines from the log. The
  launcher (PowerShell + user32) shows the Unity window at the bottom of the Z-order without activation, sets
  `WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW`, `EnableWindow(false)`, keeps the display awake with
  `SetThreadExecutionState` from a helper tied to that exact process, and kills the game if it ever becomes the
  foreground window. Focused modes (one feature each) instead of a whole-suite rerun per change.
- **Original Arena as a reference:** Arena's GOG/Steam/Bethesda install ships DOSBox 0.74, so the technique in
  [Driving DOSBox games from tests](../../techniques/driving-dosbox-games-from-tests-background-input-parallel-sa.md)
  applies unchanged: copy the install to a sandbox (Arena writes saves into its folder), rewrite only
  `fullscreen=false`, `autolock=false`, `nosound=true`, `mididevice=none`, `captures=<sandbox>` in the copied
  `DosBox.conf` (its `mount C "."` is relative, so launching with the sandbox as working directory needs no path
  rewrite), start it through WMI with `SDL_VIDEODRIVER=windib`, post keys/clicks and capture with posted Ctrl+F5.
  Esc x3 skips the intro to the main menu (hotkeys L/S/E); S starts the three-page story (Space/Enter page on).

## Verification
- Windows: focused self-test modes 0 failures on the release bundle (e.g. 694-check palace mode, 217-check NPC
  mode), both compiler orders of the runtime C# load (101 types), installed bundle hash = built bundle hash.
- macOS/Linux: bundles built from the same sources, UnityPy confirms targets 2 and 24; not play-tested.
- Arena reference: intro, main menu and story pages captured as exact 320x200 PNGs with the window behind other
  applications; no focus change.

## Gotchas
1. **`Failed to connect to local IPC` / channel `LicenseClient-...` and Unity quits at once.** (2026-11-01.) Unity
   2019.4 editors use the Unity Licensing Client; it failed on one PC in every shell. **Fix:** updating Unity Hub
   (3.20, which also installed the Unity CLI and an updated `UnityLicensingClient_V1`) and being signed in.
   `unity license list` / `unity auth status` (the CLI at `%LOCALAPPDATA%\Unity\bin\unity.exe`) confirm it.
2. **Linux/Mac Build Support "installed" but builds only Windows.** The modules belonged to another editor
   version (Hub's 2019.4.41f2); the project's 2019.4.40f1 lived on an external drive, not Hub-managed, with only
   `PlaybackEngines/windowsstandalonesupport`. **Fix:** `unity editors add <path>\Editor\Unity.exe`, then
   `unity install-modules -e 2019.4.40f1 -m linux-mono mac-mono --accept-eula` (use `--dry-run` first). Do not
   open the project in another patch version just for modules: it upgrades the project and reimports everything.
   The old Hub headless CLI (`"Unity Hub.exe" -- --headless`) has no such subcommand; the new CLI rejects `--add`.
3. **Case-sensitive file systems.** The loader matched Arena file names case-insensitively, but folder
   auto-detection used `File.Exists("GLOBAL.BSA")`, which fails on Linux (and case-sensitive macOS) with
   lower-case copies. **Fix:** enumerate the folder and compare with `StringComparer.OrdinalIgnoreCase`.
   Registry lookups (Steam, GOG) need a try/catch on non-Windows; add `~/.steam/steam`,
   `~/.local/share/Steam` and `~/Library/Application Support/Steam` as Steam roots.
4. **Python text-mode writes on Windows turn LF files into CRLF** (whole-file diffs). Edit with
   `open(p, newline='')` and keep each file's own line ending.
5. **Arena: typing a name on the main menu quits.** Letters are menu hotkeys; `E` is Exit, and the DOSBox
   autoexec ends with `exit`, so DOSBox closes. The test tool should report "DOSBox exited", not hang.
6. **One gate-movement check failed once and never again.** A check that moves the player 5 m/s x `deltaTime`
   under a 5 s real-time deadline can fail on slow background frames. Re-run it on the previous release before
   touching the code: it passed there and in 12 older logs.

## Assets
- None generated. Everything is converted at runtime from the player's Arena files; the release ships only code,
  data tables and one texture.

## Cost and time
- One session for the three-platform release: about 15 minutes of builds (three targets, ~5 minutes each on
  first run), a few minutes per focused in-game mode. No paid APIs.

## Open questions
- After the third story page Arena returned to the main menu with the inputs tried (Enter); the path into
  character creation by posted input is not worked out yet.
- macOS and Linux play-testing (left to players).
