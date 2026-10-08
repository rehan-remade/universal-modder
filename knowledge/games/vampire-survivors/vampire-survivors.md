---
kind: game
title: 'Vampire Survivors recon: Unity 6 IL2CPP'
game: Vampire Survivors
games_also: []
game_version: 'Unity engine 6000.0.62f1 (game build unverified this pass)'
platform: windows
engine: unity-il2cpp
route: managed-patch
tools: ["BepInEx 6 / MelonLoader (neither installed)", "Cpp2IL / Il2CppDumper (not run here)"]
anti_cheat: 'none detected'
status: working
agents:
- OpenCode (Muse Spark)
humans: [PatrickJnr]
date: '2026-10-08'
links: []
tags: ["vampire-survivors", "unity", "il2cpp", "unity-6", "bepinex", "melonloader", "recon", "scan"]
---

# Vampire Survivors recon: Unity 6 IL2CPP

> Read-only recon of Vampire Survivors (Steam 1794680): Unity 6 IL2CPP game (engine 6000.0.62f1, poncle), x64, no loader installed. Recommended route is BepInEx 6 (IL2CPP) or MelonLoader with types recovered via Cpp2IL/Il2CppDumper. Verified from `um scan` JSON; not launched.

## Setup

- Install: `E:\Steam\steamapps\common\Vampire Survivors\`. 1,313 files indexed.
- Engine: `unity-il2cpp` [100%] evidence `UnityPlayer + GameAssembly / global-metadata.dat`; `data_dir` `VampireSurvivors_Data`, version `6000.0.62f1` (Unity 6), company `poncle`, product `Vampire Survivors`.
- Exes: `VampireSurvivors.exe` + `UnityCrashHandler64.exe` (x64 unmanaged).
- Key binaries (sizes read directly): `GameAssembly.dll` 173.8 MB at install root, `global-metadata.dat` 48.9 MB, `resources.assets` 53.9 MB. Data dir holds `il2cpp_data/`, `level0`–`level3`, `sharedassets*`, `StreamingAssets/`, `Plugins/`, `boot.config`.
- No JS/HTML remnants anywhere in the install: the shipped build is fully Unity IL2CPP (no web-runtime leftovers to suggest a hybrid).
- Root also holds numbered directories — resolved: they are **DLC depots**, each containing a `<name>.txt` (`2230760`→`Moonspell.txt`, `2313550`→`Foscari.txt`, `2690330`→`Chalcedony.txt`, `2887680`→`FirstBlood.txt`, `3210350`→`ThosePeople.txt`, `3451100`→`Emeralds.txt`, `3929770`→`Lemon.txt`), plus a `D3D12/` dir. Steam Workshop for app 1794680 is **absent** (`workshop/content/1794680` does not exist) — no Workshop distribution on this install.
- No loaders, no mod dirs, no saves, no anti-cheat.

## Route and why

**BepInEx 6 (IL2CPP) or MelonLoader**, recovering types with Cpp2IL/Il2CppDumper and patching through Il2CppInterop — scan's `unity.md` route. The Mono-era path (plain Harmony on Assembly-CSharp) does not apply: method bodies are native here.

## How the game works (what we had to learn)

- IL2CPP: C# compiles to native `GameAssembly.dll` + `global-metadata.dat`; modding needs the metadata-driven type recovery step before any patching.
- Unity 6 (6000.x) generation: tool versions (BepInEx 6 / MelonLoader / Cpp2IL) must explicitly support the 6000.x metadata format.
- Single-player game, no protections found — unrestricted scope.

## Build steps

1. `um scan "Vampire Survivors" --json` (expect `unity-il2cpp`/100%, Unity 6 version string).
2. Install BepInEx 6 IL2CPP build (not done here); dump types with Cpp2IL against `global-metadata.dat`.
3. New mods: BepInEx 6 plugin through Il2CppInterop.

## Verification

- Scan JSON fields quoted above, including the Unity 6 version string from the data dir; binary sizes read directly; JS/HTML absence checked by extension walk.
- NOT verified: launch, loader install/attach, metadata dump (48.9 MB metadata + 173.8 MB GameAssembly bound the Cpp2IL job), exact game build, purpose of the numbered root dirs, Workshop state.

## Gotchas

1. **Unity 6, not 2021/2022-era.** Cause: version string `6000.0.62f1`. Fix: pin tool versions that support Unity 6 metadata; old tutorials assuming `2019.x` layouts will mislead.
2. **No Assembly-CSharp to read.** Cause: IL2CPP build. Fix: Cpp2IL/Il2CppDumper first, ILSpy never (nothing managed to open).

## Assets

None produced (recon only).

## Open questions

- Exact game build to match against BepInEx 6 IL2CPP support matrix.
- Save location (scan found none; common Unity spots checked and absent — game may use Steam Cloud/autosave differently).
- Moddability verdict beyond runtime patching: no official tools, no Workshop, no mod dirs found — asset swaps via UABEA/AssetStudio and save editing are community-described, not verified here.

## Sources and verification

- Local install (all claims above unless noted): `E:\Steam\steamapps\common\Vampire Survivors\` — engine strings from `vampiresurvivors_data/app.info`, binary sizes read directly, DLC depot contents listed, Workshop absence checked. Date: 2026-10-08.
- `um scan "Vampire Survivors" --json`: engine `unity-il2cpp`/100%, exes, empty loaders/saves — reproduced in-session.
- No loader/framework web sources verified this pass (no authoritative modding docs found for this title; BepInEx 6/MelonLoader/Cpp2IL recommendations are engine-class standard practice, not per-game verified).
