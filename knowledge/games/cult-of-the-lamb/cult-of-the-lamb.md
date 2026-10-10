---
kind: game
title: 'Cult of the Lamb recon: Unity Mono, and Doorstop files without a BepInEx folder (likely r2modman)'
game: Cult of the Lamb
games_also: []
game_version: 'Steam; Unity 2022.3.62f2 (per um scan); game build not read'
platform: windows
engine: unity-mono
route: loader-api
tools: ["BepInEx 5 (Thunderstore BepInExPack_CultOfTheLamb)", "r2modman / Thunderstore Mod Manager", "HarmonyX", "ILSpy"]
anti_cheat: 'none detected'
status: in-progress
agents:
- OpenCode (Muse Spark)
humans: [PatrickJnr]
date: '2026-10-08'
links: ["https://docs.bepinex.dev", "https://thunderstore.io/c/cult-of-the-lamb/"]
tags: ["cult-of-the-lamb", "unity", "mono", "bepinex", "doorstop", "r2modman", "thunderstore", "recon"]
---

# Cult of the Lamb recon: Unity Mono, and Doorstop files without a BepInEx folder (likely r2modman)

> Read-only recon of Cult of the Lamb (Steam app 1313140): Unity 2022.3.62f2 with Mono, so `Assembly-CSharp.dll`
> decompiles and BepInEx 5 + HarmonyX is the route. The game root has UnityDoorstop's `winhttp.dll`,
> `doorstop_config.ini` and `run_bepinex.sh` but no `BepInEx/` folder. That's what r2modman and Thunderstore Mod
> Manager leave behind, because they keep BepInEx in their profile, so the install is probably modded through a
> manager rather than broken. Nothing was built or launched, and no manager profile was looked for.

## Setup

- Steam, Windows, x64. `um scan` reports engine `unity-mono` from `UnityPlayer` + `Managed/Assembly-CSharp.dll`.
  `app.info` gives company `Massive Monster`, product `Cult Of The Lamb`, and the scan reads Unity `2022.3.62f2`.
- Exes: `Cult Of The Lamb.exe`, `UnityCrashHandler64.exe`.
- Game root: `winhttp.dll` (the UnityDoorstop proxy), `doorstop_config.ini` (`enabled=true`,
  `targetAssembly=BepInEx\core\BepInEx.Preloader.dll`, BepInEx 5's preloader) and `run_bepinex.sh` (BepInEx's
  launcher script for Linux and macOS). No `BepInEx/` folder.
- Thunderstore has a Cult of the Lamb community with `BepInExPack_CultOfTheLamb`, a preconfigured BepInEx 5.4 pack.
- No anti-cheat.

## Route and why

BepInEx 5 + HarmonyX: read `Managed/Assembly-CSharp.dll` with ILSpy, and use AssetRipper or UABEA for assets if
needed. This is the `unity.md` playbook's route. On an install like this one, use the existing manager profile
rather than installing BepInEx into the game folder by hand. If there's no profile, the Thunderstore pack is the
community's standard BepInEx for this game. Rejected: native hooks, which a Mono game doesn't need.

## How the game works (what we had to learn)

- Unity Mono: the game code is `Cult Of The Lamb_Data/Managed/Assembly-CSharp.dll`, which ILSpy decompiles.
  BepInEx plugins patch it at runtime with HarmonyX.
- UnityDoorstop: Windows loads the proxy `winhttp.dll` from the game folder, and it starts the assembly named in
  `doorstop_config.ini`, or by `--doorstop-target` on the command line, before the game's own code runs.
- r2modman and Thunderstore Mod Manager keep `BepInEx/` (core, plugins, config) inside their profile folder. They
  copy only the pack's root files into the game folder (`ModLinker.performLink` in r2modman) and launch the game
  with `--doorstop-enable true --doorstop-target <profile>\BepInEx\core\BepInEx.Preloader.dll`
  (`BepInExGameInstructions`). A game folder with Doorstop files and no `BepInEx/` is their normal footprint.
- r2modman profiles live in `%APPDATA%\r2modmanPlus-local\COTL\profiles\<name>\`. Thunderstore Mod Manager keeps
  its own data folder.

## Build steps

1. `um scan "Cult of the Lamb" --json`: expect `unity-mono` and a BepInEx loader flag from `doorstop_config.ini`.
2. If the root has Doorstop files but no `BepInEx/`, look for a manager profile
   (`%APPDATA%\r2modmanPlus-local\COTL\profiles\`, or Thunderstore Mod Manager's data folder) before changing
   anything. This wasn't done on this install.
3. New mod: a BepInEx 5 plugin in C# with HarmonyX, referencing `Assembly-CSharp.dll` and the Unity DLLs from
   `Managed/`.
4. Put the plugin DLL in the profile's `BepInEx/plugins/`, launch through the manager, and read the profile's
   `BepInEx/LogOutput.log`.

## Verification

- Read directly on 2026-10-08: `um scan` output, `app.info`, the contents of `doorstop_config.ini`, the presence of
  `winhttp.dll` and `run_bepinex.sh`, and the absence of `BepInEx/`.
- The r2modman behaviour comes from its source (`ModLinker.performLink`, `BepInExGameInstructions`). It wasn't
  observed on this machine.
- Not verified: launching, whether a manager profile exists here, save locations, the game build, and whether the
  Thunderstore pack works on this build.

## Gotchas

1. **Doorstop files in the game root but no `BepInEx/` folder.** It looks like a dead, half-removed BepInEx, and
   `um scan` still reports BepInEx. **Cause:** r2modman and Thunderstore Mod Manager keep BepInEx in their profile,
   copy only the root files (`winhttp.dll`, `doorstop_config.ini`, `run_bepinex.sh`) into the game folder, and
   point Doorstop at the profile with `--doorstop-target` at launch. **Fix:** look for a manager profile before
   calling the install broken. Don't delete `winhttp.dll` or the ini: that breaks every modded launch from the
   manager.

## Assets

None (recon only).

## Open questions

- Is there an r2modman or Thunderstore Mod Manager profile for Cult of the Lamb on this machine, and what's in it?
- What a plain Steam launch does with these files, since the ini's relative target
  `BepInEx\core\BepInEx.Preloader.dll` doesn't exist in the game folder. Not tested.
- Save and config location: scan found none. Unity's default would be
  `%USERPROFILE%\AppData\LocalLow\Massive Monster\Cult Of The Lamb` (company and product from `app.info`), but
  that wasn't checked.
- Which BepInEx 5.4 build the Thunderstore pack carries, and whether it runs on Unity 2022.3.62f2.

## Sources and verification

- Local install, read-only, 2026-10-08: `um scan "Cult of the Lamb" --json`, `app.info`, `doorstop_config.ini`,
  the root file listing.
- docs.bepinex.dev (fetched 2026-10-08): BepInEx is an MIT-licensed plugin and patcher framework for Unity Mono
  games, with runtime patching through Harmony and MonoMod and preloader patching through Cecil, started by
  UnityDoorstop.
- r2modman source: `ModLinker.performLink` (copies the profile's root files into the game folder) and
  `BepInExGameInstructions` (the Doorstop launch arguments).
- thunderstore.io/c/cult-of-the-lamb (checked 2026-10-09): `BepInExPack_CultOfTheLamb` by BepInEx, "Preconfigured
  and ready to use".
