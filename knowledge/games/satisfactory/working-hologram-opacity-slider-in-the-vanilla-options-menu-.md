---
kind: game
title: Working hologram opacity slider in the vanilla Options menu (SML 3.12 C++ mod)
game: Satisfactory
games_also: []
game_version: "1.2.5.0 (build/CL 517554, UE 5.6.1-CSS), Steam, SML 3.12.0"
platform: windows
engine: unreal
route: loader-api
tools:
- "SML 3.12 starter project (headers CL517554) + Alpakit"
- "Unreal Engine 5.6.1-CSS (satisfactorymodding/UnrealEngine 5.6.1-css-83)"
- "Visual Studio 2022 17.14 (MSVC 14.38)"
- "wwise-cli 0.2.4 (Wwise 2025.1.6.9117, integration 2025.1.6.4248)"
- "UE Python editor scripting (asset authoring)"
- "um win (shot/drive), um backup, um publish check"
anti_cheat: "none (single-player save; client-side visual mod, RequiredOnRemote false)"
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-11'
links: []
tags: [hologram, build-mode, options-menu, fgusersetting, game-features, post-process, custom-depth-stencil, translucency, dynamic-material-instance, smart-app-control]
---
# Working hologram opacity slider in the vanilla Options menu (SML 3.12 C++ mod)

> A C++ + content SML 3.12 mod for Satisfactory 1.2.5 that adds a "Hologram Opacity" slider (0-100%) to the game's
> own Options > User Interface > Holograms/Build Mode section and makes build mode holograms see-through. 100% is
> exactly vanilla; lower values crossfade the hologram to the real scene behind it. Verified in the real game: slider
> in the menu (main menu and pause menu), value persisted to GameUserSettings.ini, holograms screenshotted at
> 100/75/50/25/0% and after setting 48% through the real slider.

## Setup
- Satisfactory 1.2.5.0, CL 517554, UE 5.6.1 CSS fork, modular build with PDBs. SML 3.12.0 installed by SMM; mods live
  in `FactoryGame/Mods/GameFeatures/<Mod>` and must be Game Feature plugins.
- Official toolchain: VS 2022 17.14 from `SML.vsconfig` (`vs_community.exe --config SML.vsconfig --passive --wait`),
  UE 5.6.1-CSS from the satisfactorymodding/UnrealEngine release (needs GitHub linked to Epic + linker.ficsit.app;
  Inno Setup installer accepts `/SILENT /DIR=...`), starter project `master` at "Update headers to CL517554".
- Wwise: `wwise-cli download --sdk-version 2025.1.6.9117 ... ` + `integrate-ue --integration-version 2025.1.6.4248`
  exactly as SML's CI does (credentials via `WWISE_EMAIL`/`WWISE_PASSWORD` or its prompt; the human typed them).
  No soundbank generation was needed for building, the Python commandlet, cooking or packaging.

## Route and why
Loader API: SML C++ module + cooked content packaged with Alpakit's `PackagePlugin`. A pure data mod can't do it
(the effect needs runtime code), UE4SS isn't the community route here and would have to inject the setting by hand,
and a hand-rolled headerless module was considered but the official toolchain gives a maintainable project.

## How the game works (what we had to learn)
- **Options menu.** Entries are `UFGUserSetting` primary data assets (`StrId`, `DisplayName`, `WidgetsToCreate` =
  category/sub-category/priority, `ApplyType`, instanced `ValueSelector`, `ManagerTypeAvailability`,
  `ShowInBuilds`). The Holograms section is sub-category `USubC_UI_Holograms` (under `USC_UI`); vanilla entries sit at
  priority 3-8 (colours 3-6, High Contrast 7). Since 1.2, mods register their settings through an `FGGameFeatureData`
  "Primary Asset Types to Scan" rule (`FGUserSetting` in `/<Mod>/Settings`); the game then treats them like vanilla:
  same row widgets, tooltip, Apply/Confirm dialog, saved in `mFloatValues` of `GameUserSettings.ini` by StrId.
  Game features activate ~1.5 s before `LogUserSetting: Initializing user settings`, so timing is fine.
- **Slider semantics.** `FGUserSetting_Slider` stores `MinValue..MaxValue` (we used 0..1) and shows
  `MinDisplayValue..MaxDisplayValue` (0..100); `DefaultSliderValue` is in display units. With
  `FGUserSettingApplyType_UpdateInstantly` the value applies while dragging. `ShowInBuilds` must be `IIB_PublicBuilds`
  (the default hides it in shipping). Reading it: `UFGGameUserSettings::GetFGGameUserSettings()->FindUserSetting(id)
  ->GetDisplayValue()` returns an FVariant float.
- **Holograms in 1.2 do not use the hologram materials in `BP_FactorySettings`** (`HologramColor_Inst`,
  `Hologram_Blue_Inst`, `Hologram_Red_Inst` are still referenced but not on build holograms). A hologram renders the
  building's own materials, with custom depth on and a stencil value: 5 valid, 3 soft clearance (warning),
  6 invalid; guidelines use 1, connection arrows/guidelines/clearance boxes use materials from
  `/Game/FactoryGame/Equipment/BuildGun/Material/`.
- **The look is a post process.** `PPI_OutlineHologram` (parent `PPM_OutlineHologram`, BL_SceneColorAfterDOF) is a
  blendable on the main map's unbound `GlobalPostProcess` volume. It replaces stencil pixels with
  hologram colour (from `MPC_Hologram`, filled from the user's colour options) × emissive × scene detail + scan lines.
  Live tests with a dynamic instance: `Param` 0 or `EmisiveStrength` 0 → black, `LineOpacity` 0 → no lines,
  `Overlay` up → bolder lines. The result is opaque: translucency under it can't show the background.
- **What works:** below 100%, swap every material slot of hologram *body* meshes (custom depth on, stencil 3/5/6, no
  BuildGun-folder material) for a dynamic instance of a translucent unlit material (state colour from the user's
  build/soft clearance/invalid colours, screen-space scan lines, small fresnel), and switch custom depth off on those
  meshes so the post process skips them. Restore materials/custom depth exactly at 100%. Holograms are found each
  tick with `TActorIterator<AFGHologram>`; state via `GetHologramMaterialState()`.

- **Scan line toggle (v1.1).** A second setting, a `FGUserSetting_CheckBox` ("Show Scanlines", priority 6.75 so it
  sits under the slider), switches the body material's lines off (line intensity/opacity 0, base raised by the
  lines' average so the colour holds). Vanilla lines at 100% belong to the post process; zeroing its `LineOpacity`
  turns holograms nearly black and would also hit dismantle highlights, so with lines off the mod draws the bodies
  at 100% too (opaque, measured mean colour within a few levels of vanilla). Checkbox values persist as 0/1 in
  `mIntValues`, and `GetDisplayValue()` may return Bool or Int32.

## Build steps
1. Mod folder `Mods/GameFeatures/HologramOpacity` (uplugin with `BuiltInInitialFeatureState: Active`,
   `RequiredOnRemote: false`, deps SML ^3.12.0 and `GameFeatures` with `BasePlugin: true` because an editor helper
   uses the module).
2. `Build.bat FactoryEditor Win64 Development -Project=FactoryGame.uproject` (≈4 min first time on a 13900K).
3. Content by script: `UnrealEditor-Cmd FactoryGame.uproject -run=pythonscript -script=.../create_assets.py`
   creates the FGGameFeatureData (Alpakit's 7 scan rules), the FGUserSetting and the material graph
   (MaterialEditingLibrary). Instanced sub-object fields (`FGUserSetting_Slider`) and the protected `ShowInBuilds`
   are set by a tiny editor-only C++ UFUNCTION (Python can't set EditDefaultsOnly on sub-objects).
4. `RunUAT PackagePlugin -DLCName=<Mod> -clientconfig=Shipping -platform=Win64 -build -installed -nocompileeditor
   -merge -CopyToGameDirectory_Windows=<game>` (what Alpakit runs; ≈6 min).

## Verification
- Game log: module loaded, game feature Active, SML lists the mod, subsystem initialized.
- Screenshots (um win shot) of Options > User Interface showing the row after the colour pickers; slider click set
  32 then 48; `GameUserSettings.ini` gained `("HologramOpacity.Opacity", 0.320000)` / `0.48`.
- In-game console `HoloOpacity.Dump` (mod command) listed body meshes switched to the mod material with custom depth
  off and guidelines untouched; `HoloOpacity.Set <x>` overrides for side-by-side shots at 100/75/50/25/0%.
- Checked foundations (valid + soft clearance colours) and a conveyor splitter (machine mesh, arrows untouched).
  Not checked: blueprint holograms, zoop, wires/power poles, multiplayer client, performance with huge blueprints.

## Gotchas
1. **Settings asset never shows in the menu.** Since 1.2 auto-detection is gone. **Fix:** FGGameFeatureData scan rule
   for `FGUserSetting`, and set `ShowInBuilds=IIB_PublicBuilds` (defaults to development-only).
2. **Swapping the hologram materials from BP_FactorySettings does nothing.** **Cause:** 1.2 holograms render the
   building's own materials + stencil; the colour/lines come from `PPI_OutlineHologram`. **Fix:** change the body
   meshes' materials and custom depth as above. A dump of live hologram components settles this in one minute.
3. **Translucent body still looks opaque.** **Cause:** the post process replaces stencil pixels. **Fix:** custom
   depth off on translucent bodies (the outline post process then skips them).
4. **50% looks almost solid.** **Cause:** two-sided translucency shows front and back faces of closed meshes
   (~75% coverage at 50%). **Fix:** one-sided material; tune fresnel/line opacity boosts low (0.35 / 0.1).
5. **Launching `FactoryGameSteam.exe` directly exits** with `Game restarting within Steam client, exiting` and Steam
   relaunches without your args (so `-ini:...?loadgame=` quick-load args are lost). **Fix:** `steam://rungameid/526870`
   and the menu's Continue/Load, or a steam_appid.txt (not tried).
6. **um win `type` text doesn't reach the Unreal console** (VK_PACKET unicode is ignored). **Fix:** open the console
   with VK 0xC0 and send each character as a virtual-key press (`key 0x48` ...); console commands are
   case-insensitive.
7. **Windows Smart App Control (enforcing) kills the CSS editor** (`UnrealEditor-Cmd` exit 0xC0E90002,
   CodeIntegrity events 3033/3077). Game, SML and ficsit.app mod DLLs are also unsigned but pass on reputation; a
   freshly built mod DLL would not. Only the human can decide to turn it off.
8. **`um publish check` on the source plugin folder reports the mod's own DLL/PDB as "game files copied verbatim"**
   because Alpakit already copied that build into the game. **Fix:** lint the unzipped release zip instead (clean).
9. **`um scan` reports SML as "Fabric/Forge profile"**: it doesn't know SML/SMM yet.
10. **In a commandlet, `EditorAssetLibrary.load_asset` can miss assets** the registry hasn't scanned; use
    `unreal.load_asset`. The pythonscript commandlet also exits 1 when an unrelated startup error was logged
    (e.g. "GameFeatureData is missing" before the script creates it).
12. **Packaging while the human launches the game half-uninstalls the mod.** PackagePlugin's
    `-CopyToGameDirectory_Windows` deletes the old install first, then fails on the DLL the starting game has locked.
    **Fix:** package without the copy flag, wait until the game process is gone, then extract the release zip
    (the archive step runs before the copy, so the zip is complete).
11. **IoStore reading without third-party Oodle:** the game's Core DLL exports
    `FOodleDataCompression::Decompress`, usable from Python ctypes; zen package summary in UE 5.6 has 15 fields
    (Cell import/export offsets), export offsets are relative to the end of the zen header, and Satisfactory's cooked
    assets use tagged (versioned) properties, so they parse without mappings.

## Assets
No generated art. One material authored by script (translucent, unlit, one-sided, custom depth writes, all CSS mesh
usage flags incl. `bUsedWithInstancedSplineMeshes`).

## Cost and time
One long session: most wall-clock went to toolchain downloads/installs (VS, ~5 GB engine, ~9 GB Wwise SDK cache) and
two package/test loops (~15 min each).

## Open questions
- Keep the vanilla outline at low opacity (test an outline-only stencil value via `HoloOpacity.Stencil`).
- Blueprint holograms, zoop children, wires/poles and multiplayer clients not tested.
