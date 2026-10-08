---
kind: game
title: 'Cult of the Lamb recon: Doorstop remnant, no BepInEx payload, Unity Mono'
game: Cult of the Lamb
games_also: []
game_version: 'Unity engine 2022.3.62f2 (game build unverified this pass)'
platform: windows
engine: unity-mono
route: loader-api
tools: ["UnityDoorstop bootstrapper (payload missing)", "BepInEx 5 (recommended, not installed)"]
anti_cheat: 'none detected'
status: working
agents:
- OpenCode (Muse Spark)
humans: [PatrickJnr]
date: '2026-10-08'
links: ["https://docs.bepinex.dev"]
tags: ["cult-of-the-lamb", "unity", "mono", "bepinex", "recon", "scan"]
---

# Cult of the Lamb recon: Doorstop remnant, no BepInEx payload, Unity Mono

> Read-only recon of Cult of the Lamb (Steam 1313140): Unity Mono (engine 2022.3.62f2, Massive Monster) with a **non-functional loader remnant** — UnityDoorstop bootstrapper (`winhttp.dll` 25 KB + `doorstop_config.ini` targeting `BepInEx\core\BepInEx.Preloader.dll`) but **no `BepInEx/` payload directory**, so nothing loads. An earlier revision of this note overstated this as "BepInEx installed" on the strength of scan's loader flag alone; corrected after finding the missing payload. Recommended route is a fresh BepInEx 5 install with HarmonyX. Verified from `um scan` JSON plus file-level checks; not launched.

## Setup

- Install: `E:\Steam\steamapps\common\Cult of the Lamb\`. 3,840 files indexed.
- Engine: `unity-mono` [100%] evidence `UnityPlayer + Managed/Assembly-CSharp.dll`; `data_dir` `cult of the lamb_data`, version `2022.3.62f2`, company `Massive Monster`, product `Cult Of The Lamb`.
- Exes: `Cult Of The Lamb.exe` + `UnityCrashHandler64.exe` (x64 unmanaged).
- Loaders: **UnityDoorstop bootstrapper only, payload missing.** Present: `winhttp.dll` (25,088 bytes, Doorstop proxy) + `doorstop_config.ini` (`enabled=true`, `targetAssembly=BepInEx\core\BepInEx.Preloader.dll`) + `run_bepinex.sh` (Linux helper). Absent: the entire `BepInEx/` directory, so the configured preloader path resolves to nothing and no mods load. Scan still flags `BepInEx` from `doorstop_config.ini` alone — a true-positive for "Doorstop was here", a false-positive for "loader functional". No mod dirs, no saves found, no anti-cheat.

## Route and why

**BepInEx 5 + HarmonyX, freshly installed** (read `Managed/Assembly-CSharp.dll` with ILSpy; assets via AssetRipper/UABEA) — scan's `unity.md` route. First repair or remove the dead Doorstop remnant (`winhttp.dll` + `doorstop_config.ini` with no payload behind them), then install BepInEx 5 for Unity Mono; a stale proxy DLL can shadow a fresh install's own bootstrapper. Native hooks unnecessary.

### BepInEx facts (docs fetched 2026-10-08 from docs.bepinex.dev)

- BepInEx ("BepIn Injector Extensible") is an MIT-licensed patcher/plugin framework for Mono-backed Unity games: drop-in install, built-in config/logging, runtime patching via Harmony + MonoMod, in-memory assembly patching via Cecil behind UnityDoorstop — the exact stack whose Doorstop half is stranded on this install.
- Moddability classification: community-established (BepInEx/HarmonyX). No anti-cheat on this install. Version compatibility between BepInEx 5.x and this Unity 2022.3 build was not verified (no payload to test against).

## How the game works (what we had to learn)

- Unity Mono game: managed assembly is decompilable; BepInEx hosts C# plugins + Harmony patches.
- No anti-cheat on this install, so offline/online scope is unrestricted by protections (normal online etiquette still applies).

## Build steps

1. `um scan "Cult of the Lamb" --json` (expect `unity-mono`/100%, BepInEx loader).
2. Confirm BepInEx version + plugin list from its config/log after a launch (not done here).
3. New mods: BepInEx 5 plugin project against Unity 2022.3 / .NET Framework-era APIs as appropriate.

## Verification

- Scan JSON fields quoted above, including engine version/company/product from `app.info`; `doorstop_config.ini` contents read (target assembly path); `BepInEx/` absence + `winhttp.dll` presence/size checked; `run_bepinex.sh` noted.
- NOT verified: launch, whether the dead Doorstop proxy breaks a cold start, save locations, exact game build.

## Gotchas

1. **No mod dirs flagged, and no payload behind the loader flag.** Cause: plugins would live under `BepInEx/plugins`, which is not in scan's `MOD_DIRS` — and here the directory does not exist at all. Fix: inventory `BepInEx/` directly for the active set (same gap class as Kenshi's RE_Kenshi miss, milder).
2. **Scan's `BepInEx` flag overclaims.** Cause: `doorstop_config.ini` alone triggers the loader entry; the configured `targetAssembly` is never checked for existence. Fix for future agents: treat a Doorstop flag as "bootstrapper present" and verify `BepInEx/core/BepInEx.Preloader.dll` exists before calling the loader installed. Recommended UM improvement: only report BepInEx when the config's target assembly (or `BepInEx/core/`) exists on disk.

## Assets

None produced (recon only).

## Open questions

- Whether the dead Doorstop proxy breaks a cold start (launch test, not done).
- Save/config locations (scan found none).
- Exact game build vs BepInEx 5.x support (re-check at install time).

## Sources and verification

- Local install: `doorstop_config.ini` contents (target assembly path), `BepInEx/` absence, `winhttp.dll` presence/size (25,088 bytes), `run_bepinex.sh` name, engine version/company/product from `app.info`. Date: 2026-10-08.
- docs.bepinex.dev (fetched 2026-10-08): BepInEx is an MIT-licensed patcher/plugin framework for Mono-backed Unity games (drop-in install, config/logging, Harmony+MonoMod runtime patching, Cecil in-memory patching via UnityDoorstop).
- `um scan "Cult of the Lamb" --json`: engine `unity-mono`/100%; loader flag fires on `doorstop_config.ini` alone (overclaim documented in Gotchas) — reproduced in-session.
