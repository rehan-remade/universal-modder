---
kind: game
title: '7 Days to Die recon: Unity Mono 2022.3, EAC warning'
game: 7 Days to Die
games_also: []
game_version: 'Unity engine 2022.3.62f2 (game build unverified this pass)'
platform: windows
engine: unity-mono
route: loader-api
tools: ["BepInEx 5 (not installed)", "official modding (Mods folder + XML)"]
anti_cheat: 'EasyAntiCheat detected — offline/single-player only, never inject into protected play; use official offline/EAC-off launch where provided. No bypasses.'
status: working
agents:
- OpenCode (Muse Spark)
humans: [PatrickJnr]
date: '2026-10-08'
links: []
tags: ["7-days-to-die", "unity", "mono", "bepinex", "eac", "recon", "scan"]
---

# 7 Days to Die recon: Unity Mono 2022.3, EAC warning

> Read-only recon of 7 Days to Die (Steam 251570): Unity Mono (engine 2022.3.62f2, The Fun Pimps), x64 binaries including a separate EAC launcher, and a **populated `Mods/` overhaul stack** (Darkness Falls core, SCore, TFP_Harmony, vehicles, UI tweaks). Recommended route is the game's own `Mods`/XML modding first, BepInEx 5 + HarmonyX for code. EAC is installed: mod work stays offline. Verified from `um scan` JSON, version strings, and directory listings; not launched.

## Setup

- Install: `E:\Steam\steamapps\common\7 Days To Die\`. 24,841 files indexed.
- Engine: `unity-mono` [100%] evidence `UnityPlayer + Managed/Assembly-CSharp.dll`; `data_dir` `7daystodie_data`, version `2022.3.62f2`, company `The Fun Pimps`, product `7 Days To Die`.
- Exes: `7daystodie.exe`, `7daystodie_eac.exe`, `7dlauncher.exe`, `unitycrashhandler64.exe` (all x64 unmanaged); the game binary carries Unity `2022.3.62` (build 7762112) version strings.
- Anti-cheat: **EasyAntiCheat** detected (`EasyAntiCheat/` dir present); scan emitted its standard offline-only warning.
- Mod dirs: `Mods/` present **and populated (16 entries)** — `0-DarknessFallsCore`, `0-Quartz`, `0-SCore`, `0_TFP_Harmony`, `1-CustomGameOptions`, `1-DF-BdubsVehicles`, `BiomePrefabExclusion`, `IDCAdvancedDewCollectorV3`, … (Darkness Falls overhaul stack). No standalone BepInEx/MelonLoader install (no BepInEx markers); Harmony arrives here via the `0_TFP_Harmony` modlet.

## Route and why

**Official `Mods/` + XML first** (the game loads overhauls/mods from `Mods/` natively), **BepInEx 5 + HarmonyX** for code-level changes (ILSpy on `Managed/Assembly-CSharp.dll`). This is scan's `unity.md` route. Strictly offline while EAC is in the picture; never touch protected multiplayer.

## How the game works (what we had to learn)

- Unity Mono game: managed `Assembly-CSharp.dll` is readable/decompilable; HarmonyX patching via BepInEx is the standard code route.
- Two launch paths exist (`7daystodie.exe` vs `7daystodie_eac.exe`); modded offline play uses the non-EAC path where the game provides it.
- `Mods/` folder ships with the install layout for data/XML overhauls — and this install proves the pattern at scale (Darkness Falls + SCore + companions all load as modlets; `0_TFP_Harmony` shows even Harmony bootstrapping rides the modlet system here).
- Moddability classification: officially tolerated (first-party `Mods/`+XML system) + community-established (BepInEx/HarmonyX, overhaul stacks). Dedicated-server modding and exact EAC-off behavior are docs-described, not verified on this install.

## Build steps

1. `um scan "7 Days to Die" --json` (expect `unity-mono`/100%, EAC flag + warning, `mods` dir).
2. Inventory `Mods/` for the active set; back up saves before modded launches.
3. New mods: `Mods/` package for content; BepInEx 5 plugin (HarmonyX) for code.

## Verification

- Scan JSON fields quoted above, including engine version/company/product strings from `app.info`; `Mods/` listing observed (Darkness Falls stack, not a clean install); `EasyAntiCheat/` dir confirmed; Unity build strings read from the game exe.
- NOT verified: launch, EAC-off launch option presence, standalone BepInEx install, save locations, exact game build (1.x/2.x).

## Gotchas

1. **EAC is installed — scope accordingly.** Cause: `EasyAntiCheat` markers in-install. Fix: single-player/offline modding only; official unprotected launch path if the game offers one; no bypasses, ever.
2. **No standalone loader — and none needed for this stack.** Cause: `Mods/`-only plus `0_TFP_Harmony` supplying Harmony. Fix: install BepInEx 5 (Mono build, Unity 2022.x-compatible) only if XML/modlet modding cannot reach the idea; otherwise work inside the modlet system the installed overhauls already use.

## Assets

None produced (recon only).

## Open questions

- Save/config locations on this install (scan found none — check `%APPDATA%/7DaystoDie` after first run).
- Exact game build (e.g. 1.x/2.x) to pin BepInEx compatibility.
- Dedicated-server mod story (no server install here; docs-only).

## Sources and verification

- Local install: engine version/company/product from `app.info`, Unity build strings from game exe (2022.3.62.7762112), `Mods/` listing (Darkness Falls stack), `EasyAntiCheat/` dir, exes list, saves absence (both `%APPDATA%` casings checked). Date: 2026-10-08.
- No loader/modding web sources verified this pass (BepInEx docs confirm the framework's Mono/Doorstop/Harmony architecture generally; per-game compatibility not established). EAC scoping follows scan's standard warning plus the installed EAC evidence.
- `um scan "7 Days to Die" --json`: engine `unity-mono`/100% + EAC flag + warning — reproduced in-session.
