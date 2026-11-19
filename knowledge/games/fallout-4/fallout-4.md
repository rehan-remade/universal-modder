---
kind: game
title: 'Fallout 4 recon: F4SE for runtime 1.11.221 next to Address Library databases for 1.10.x only'
game: Fallout 4
games_also: []
game_version: 'Steam; F4SE build for runtime 1.11.221 installed; Fallout4.exe FileVersion not read (unverified)'
platform: windows
engine: creation
route: data
tools: ["F4SE (build for runtime 1.11.221)", "Address Library for F4SE Plugins", "Creation Kit", "FO4Edit (xEdit)", "Vortex"]
anti_cheat: 'none detected'
status: in-progress
agents:
- OpenCode (Muse Spark)
humans: [PatrickJnr]
date: '2026-10-08'
links: ["https://f4se.silverlock.org", "https://www.nexusmods.com/fallout4/mods/42147"]
tags: ["fallout-4", "creation", "f4se", "address-library", "commonlibf4", "esp", "esl", "vortex", "recon"]
---

# Fallout 4 recon: F4SE for runtime 1.11.221 next to Address Library databases for 1.10.x only

> Read-only recon of a modded Steam install of Fallout 4 (app 377160): Creation engine, x64, F4SE and the
> Creation Kit installed, and Vortex deploying into `Data/`. The useful finding is a mismatch. The game root has
> `f4se_1_11_221.dll`, but `Data/F4SE/Plugins/` only had `version-1-10-*.bin` Address Library databases, so any
> F4SE plugin built on Address Library would fail on 1.11.221 until a matching database is installed. Nothing was
> built or launched, and the game exe's own version wasn't read.

## Setup

- Steam install (app 377160), Windows, x64. `um scan` reports engine `creation` from the DLC `.esm` masters in
  `Data/`, and the Script Extender loader from `f4se_loader.exe`.
- Root exes: `Fallout4.exe`, `Fallout4Launcher.exe`, `CreationKit.exe`, `f4se_loader.exe`.
- F4SE in the game root: `f4se_1_11_221.dll`, `f4se_loader.exe`, `f4se_readme.txt`, `f4se_whatsnew.txt`. The DLL's
  name is the game runtime that F4SE build targets.
- `Data/F4SE/Plugins/` held F4SE plugin DLLs, a Vortex marker (`__folder_managed_by_vortex`) and Address Library
  databases named `version-1-10-*.bin`, with none for 1.11.x.
- Game build: not established. See Gotcha 2 for how not to read it.
- Current F4SE builds (f4se.silverlock.org, 2026-10-08): 0.7.9 for runtime 1.11.240, 0.7.2 for 1.10.984, 0.6.23
  for 1.10.163. Steam and GOG are supported but are on different versions; the Windows Store version isn't.
- No anti-cheat.

## Route and why

Data plugins first: `.esp`/`.esl` made in FO4Edit or the Creation Kit for items, records and quests. F4SE plugin
DLLs (`Data/F4SE/Plugins/*.dll`) only when the change needs engine code. Most are built on CommonLibF4 and
Address Library, which ties them to the game's runtime version. Install both through the mod manager that owns the
install (Vortex here). This is the `bethesda.md` playbook's route. Rejected: native hooks outside F4SE, since the
extender already provides a loader and a plugin API.

## How the game works (what we had to learn)

- Content is `.esm` masters plus `.ba2` archives. Mods add `.esp`/`.esl` plugins and loose files under `Data/`.
  Load order lives in `Plugins.txt` and the manager's profile, not in the game folder.
- Each F4SE build supports one game runtime, named in its DLL (`f4se_1_11_221.dll`). After a game update, F4SE
  needs the build for the new runtime.
- Address Library: CommonLibF4-based plugins don't hardcode addresses. They look up IDs in a per-runtime database.
  CommonLibF4's `IDDatabase::load` opens `Data/F4SE/Plugins/version-<runtime>.bin` (the runtime with dashes, e.g.
  `version-1-10-163-0.bin`) and fails hard if that file is missing. The databases present have to cover the
  runtime the game actually runs.
- `__folder_managed_by_vortex` in a folder means Vortex deploys into it. Add and remove mods through Vortex, not
  by hand, so its deployment stays consistent.

## Build steps

1. `um scan "Fallout 4" --json`: expect engine `creation` and the Script Extender loader flag.
2. Read the game's version: `(Get-Item "<install>\Fallout4.exe").VersionInfo.FileVersion` in PowerShell, or any
   other `GetFileVersionInfo` reader. Compare it with the `f4se_<runtime>.dll` in the game root.
3. Check `Data/F4SE/Plugins/` for `version-<that runtime>.bin`. If it's missing, install the Address Library
   release for that runtime through the manager before launching with F4SE plugins.
4. Data mods: `.esp`/`.esl` in FO4Edit or the Creation Kit. Engine mods: an F4SE plugin DLL against CommonLibF4.
   Install both through the manager.
5. Back up `Documents/My Games/Fallout4` (`um backup`) before the first modded launch.

## Verification

- Read directly on 2026-10-08: the root F4SE files, the `Data/F4SE/Plugins/` listing (plugin DLLs, Vortex marker,
  `version-1-10-*.bin`), `CreationKit.exe` in the root, and `um scan` output.
- The Address Library behaviour comes from CommonLibF4's `IDDatabase::load`, not from a launch on this install.
- Not verified: launching, F4SE loading, whether the installed plugins use Address Library, the game exe's
  FileVersion, load order.

## Gotchas

1. **Address Library databases for 1.10.x only, next to F4SE for 1.11.221.** `Data/F4SE/Plugins/` had
   `version-1-10-*.bin` files that look like leftovers from an older F4SE. **Cause:** they're Address Library
   databases, one per runtime. CommonLibF4-based plugins open `version-<runtime>.bin` for the running game and fail
   hard when it's missing, so on 1.11.221 they need `version-1-11-221-0.bin`. **Fix:** install the Address Library
   release that matches the game's runtime. Don't treat the 1.10.x files as junk from F4SE. Not reproduced here,
   since the game wasn't launched.
2. **No version string in the first 6 MB of `Fallout4.exe`.** A raw byte scan of the start of the exe found no
   version, so the game build was left unknown. **Cause:** the VERSIONINFO resource sits in the `.rsrc` section
   near the end of the file. **Fix:** read it through the Windows API, e.g.
   `(Get-Item Fallout4.exe).VersionInfo.FileVersion` in PowerShell. CommonLibF4 reads the same resource with
   `GetFileVersionInfo`. Not run on this install yet.

## Assets

None (recon only).

## Open questions

- The game's actual runtime (read `Fallout4.exe`'s FileVersion). If it's 1.11.240, the target of current F4SE
  0.7.9, the installed `f4se_1_11_221.dll` is out of date too. If it's 1.11.221, F4SE matches and only the Address
  Library database is missing.
- Which Address Library release covers 1.11.221 (not checked).
- Whether the installed F4SE plugins depend on Address Library (not checked).

## Sources and verification

- Local install, read-only, 2026-10-08: root F4SE files, `Data/F4SE/Plugins/` listing, `CreationKit.exe`,
  `um scan "Fallout 4" --json`.
- f4se.silverlock.org (fetched 2026-10-08): 0.7.9 for 1.11.240, 0.7.2 for 1.10.984, 0.6.23 for 1.10.163 (0.6.21 is
  VR only). Latest Steam and GOG supported, on different versions; no Windows Store support. Nexus mirror:
  nexusmods.com/fallout4/mods/42147.
- CommonLibF4 `IDDatabase::load`: opens `Data/F4SE/Plugins/version-<runtime>.bin` and fails if it's missing. Its
  runtime version comes from the exe's version resource via `GetFileVersionInfo`.
- creationkit.com (checked 2026-10-08): the official CK wiki served a backend-maintenance notice dated 2024-02-07.
  Until it's back, FO4Edit's docs and the installed Creation Kit's help are the working references.
