---
kind: game
title: 'Four Shifts: a permadeath roster game mode with MelonLoader on Unity 6 IL2CPP'
game: The Precinct
games_also: []
game_version: 1.13.24987 (steam 490110)
platform: windows
engine: unity-il2cpp
route: managed-patch
tools:
- MelonLoader 0.7.3
- HarmonyX 2.10.2 and Il2CppInterop 1.5.1 (bundled with MelonLoader 0.7.3)
- ilspycmd 11.1
- AssetRipper 2.0.0
- Blender 4.5.15
anti_cheat: none found by um scan
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-25'
links:
- https://github.com/LavaGang/MelonLoader
- https://github.com/BepInEx/Il2CppInterop
- https://github.com/AssetRipper/AssetRipper
tags:
- unity6
- il2cpp
- melonloader
- game-mode
- permadeath
- title-menu
- character-swap
---
# Four Shifts: a permadeath roster game mode with MelonLoader on Unity 6 IL2CPP

> A new game mode for The Precinct, reached from its own entry in the title menu: a squad of four NPC-style
> officers with balanced random stats works four shifts a day, an officer who dies stays dead, and every day
> survived earns a rank that unlocks items from a custom list. Built as a MelonLoader plugin with Harmony
> patches; it runs in the real game on its own save folder, verified by the player and by an in-mod file bridge
> plus screenshots.

## Setup
- The Precinct 1.13.24987 (Steam 490110), Unity 6000.0.75f1, IL2CPP, x64, Windows 11. Single-player, no
  anti-cheat, no online modes (Steam lists it as single-player only; the one DLC is the soundtrack).
  Saves: `%USERPROFILE%\AppData\LocalLow\Fallen Tree Games Ltd\The Precinct\SaveGame_Steam\`
  (BSON, Steam Cloud). Back them up (`um backup`) before the first modded launch.
- MelonLoader 0.7.3 (`MelonLoader.x64.zip`: `version.dll` + `MelonLoader\` into the game folder). It bundles
  HarmonyX 2.10.2 and Il2CppInterop 1.5.1 (`1.5.1-ci.845` in its `MelonLoader.deps.json`). The community
  mods on Nexus for this game all use MelonLoader. First launch generates the interop assemblies in ~40 s.
- Plugin: .NET 6 class library (built with SDK 10, `CheckEolTargetFramework=false`) referencing
  `MelonLoader\net6\{MelonLoader,0Harmony,Il2CppInterop.Runtime,Il2CppInterop.Common}.dll` and
  `MelonLoader\Il2CppAssemblies\` (Assembly-CSharp, Il2Cppmscorlib, Il2CppSystem(.Core), UnityEngine.*Module,
  Unity.TextMeshPro, UnityEngine.UI).
- For reading the game: `ilspycmd` over the generated Assembly-CSharp gives signatures and fields only (no
  bodies), which was enough for everything here.

## Route and why
Managed patching through MelonLoader + Harmony: the game has rich, well-named managers (rank, unlocks, saves,
story progression, frontend menus), so a mode can be assembled from the game's own systems. Asset-only or
native hooking would not reach game rules. Officer portraits were rendered offline because in-game rendering
kept crashing (Gotchas).

## How the game works (what we had to learn)
- **Saves:** `PlatformManager_PC.GetSaveGameFolderPath()` builds the game-save folder
  (`SaveGame_Steam\SceneMap_default`). A postfix that returns a sibling folder while the mode is active gives the
  mode its own career; the profile folder (settings, bindings) stays shared.
- **Starting a career from code:** `FrontendMenuController.StartNewGame()` / `LoadScene(false)`. Clear the
  frontend's preloaded serialiser first (`SaveManager.SetPreloadedGameSerialiser(null)`), or it may reuse the
  real career it loaded at sign-in.
- **Skipping the story:** `ObjectiveProgressionManager.SetProgressionToMatchPendingStoryBeat_Debug(Act4_Shifts)`
  then `ApplyProgressionAndRestartShift_Debug()` from a postfix on `GameManager.StartGameAfterLoadingSession`
  turns a new career into post-story free patrol. Story beats run from `Act1_IntroFlyby` (0) to `Act4_Shifts` (105).
- **Shifts and death:** `ShiftStartScreen.Open/Close` (shift assignment), `ShiftCompleteScreen.Open` (shift
  survived), `GameManager.PlayerGameOver(GameOverReason)` (`Died` = 0; `UnauthorisedActions` also fires),
  `GameManager.OnGameOverPanelFinished`. `RankManager.HasUnlockedCustomShift` gates custom shifts.
- **Ranks and unlocks:** every unlockable derives from `PlayerUnlock` and carries
  `_levelRequirement._levelRequired` (a `RankManager.RankEnum`, 0-34), honoured when `_unlockRequirementModules`
  has `LevelRequirement` (1). The lists hang off `RankManager` (`_playerWeaponUnlocks`, `_playerVehicleUnlocks`,
  `_playerCustomisationUnlocks`, `_playerVehicleLiveryUnlocks`, `_playerPatrolVariantUnlocks`, plus single
  feature/shift unlock fields); 61 are rank-gated. All of them are earned in play: the Steam version sells no
  in-game items (one package, and the only DLC is the soundtrack). Rewriting those requirements and postfixing
  `GetPlayerRankIndex/GetPlayerRankEnum` (and holding `_playerRankIndex`) gives a custom rank ladder that XP can't
  move. `PlayerUnlock.GetName()` returns an I2 term; `Il2CppI2.Loc.LocalizationManager.GetTranslation(term)`
  gives the display name.
- **Perks:** `PlayerUpgradeManager._upgradeTypesPurchased` (an Il2Cpp `HashSet<UpgradeType>`) can be written
  directly. Health/stamina: `CharacterBase.GetHealthStaminaModule()` with `SetMaxHealth`, `SetMaxStamina`,
  `SetStaminaRecovery`; regen lives in the `CharacterHealthStaminaSettings` asset (`_healthRechargeRate`).
- **Characters:** the player model is `Models/POL_PoliceMale_Player` with two skinned parts, `CC_Clothes` and
  `CC_Skin` (head and hands), 64 `CC_Base_*` bones. NPC police are separate prefabs (`RPO_01..05_AI_Police*`,
  `sharedassets3.assets`) whose variants are head materials named `POL_AI_<body type>_Head_<skin/hair>` (13).
  `CharacterModelManager.SwitchToAppearance` / `PlayerManager.WearClothingUsingAppearance` only relabel the
  player; there are no NPC bodies on the player rig. In vehicles the player is reparented under
  `<vehicle>/Chassis/Player(Clone)`.
- **Title menu:** entries are pooled `Main Menu Button - BUTTON_nnn` objects (Button + FrontendOptionsButton +
  a TextMeshPro child with I2 `Localize`) moved from `ButtonsPool` into
  `Frontend Canvas/Side Panel/SidePanelOptions` (a VerticalLayoutGroup) for whichever panel is open.
  `FrontendOptionsButton._menu` tells which panel owns them.
- **Pause:** the game pauses itself when the window loses focus (`UIManager.IsPausedBecauseApplicationFocusLost`).

## Build steps
1. Install MelonLoader 0.7.3, launch once, back up saves.
2. Plugin pieces (one Harmony patch or MelonMod callback each): save-folder redirect + story skip + custom-shift
   unlock; a title-menu entry (copy the live first entry of `SidePanelOptions` while the main menu owns it,
   built under an inactive holder, `FrontendOptionsButton` and `Localize` destroyed, own `onClick`); an IMGUI
   select screen opened from `ShiftStartScreen.Open` that blocks the game's screen with a `CanvasGroup`
   (`interactable`/`blocksRaycasts` off); stats/perks at `ShiftStartScreen.Close`; death and shift tracking;
   rank rewards; a memorial from `OnGameOverPanelFinished`.
3. Officer body: instantiate the matching NPC character under an inactive holder, strip every `MonoBehaviour`,
   `Behaviour`, `Collider`, `Rigidbody` and every renderer except the officer's parts; each `OnLateUpdate` copy
   the player's `CC_Base_*` local rotations onto it and the hip's world pose; hide the player's renderers with
   `forceRenderingOff`, set the player's Animators to `AlwaysAnimate`, and mirror the player parts' `enabled`
   flag and shadow mode onto the proxy parts.
4. Portraits (local only, never shipped): AssetRipper 2.0 headless (`--headless --port N`, `POST /LoadFolder`,
   `/Assets/Json`, `/Assets/Model.glb?Path=` for Mesh assets, `/Assets/Image?Extension=png`), export the five
   police prefabs' meshes and the 27 police textures, render head-and-shoulders portraits in Blender
   (the exported meshes stand along -Y and face -Y once turned upright), store raw RGBA, and fill textures in game
   with `SetPixel` a few rows per frame.
5. A file bridge in the mod (commands in `UserData\<mod>\cmd.txt`, answers in `out.txt`: state dumps, UI text
   tree, perf timing, test actions such as "end shift" and "kill officer") made most checks possible without
   touching the player's input.

## Verification
- In the real game, by the player and by screenshots of the game window (`um win shot --title "^The Precinct$"`;
  `--exe` sometimes grabs the MelonLoader console, which belongs to the same process):
  - The title entry appears under Play Game and starts the mode.
  - A new career skips straight to a patrol shift.
  - The select screen with portraits blocks the game's shift screen.
  - Officer bodies follow the player on foot and sit in cars.
  - Death tracking works ("OFFICER KIA" after a real death).
- Through the bridge: a simulated day ended in "DAY 1 SURVIVED (3 alive)" and "RANK UP to 1" with the promotion
  banner, and the memorial and Start a New Run worked.
- The real career's files kept their old timestamps throughout (`um backup diff`).
- Performance: the mod costs about 0.09 ms per frame at 90-100 fps.
- Not verified: the select screen after a real (not simulated) shift end; the officer body in cutscenes and
  after a death restart; whether the overlays now hide under the in-game pause menu.

## Gotchas
1. **Harmony postfix on a method with an `out float` (`PlayerUpgradeManager.HasPurchasedUpgrade(..., out float)`)
   threw `NullReferenceException ... native->managed trampoline` on every call.** **Cause:** Il2CppInterop's
   trampolines and `out` primitives (Il2CppInterop 1.5.1, the build MelonLoader 0.7.3 ships; not narrowed down
   further). **Fix:** write the game's state instead (`_upgradeTypesPurchased`).
2. **An extra `Camera.Render()` for portraits hard-crashed the game (twice), leaving an unkillable 52-56 KB
   `Precinct.exe`.** **Cause:** likely the upscaler (DLSS/FSR) hooking cameras; a zombie process means a driver-level
   hang. **Fix:** no extra cameras; render portraits offline. Zombies hold the plugin DLL until reboot: rename the
   locked DLL to install a new one. The same kind of unkillable process, and how to plan launches around it, is
   in [the force-quit zombie note](../../techniques/a-force-quit-pc-game-relaunch-wedges-as-an-unkillable-zombie.md).
3. **`ImageConversion.EncodeToPNG` threw "Instances of abstract classes cannot be created"
   (`BlittableArrayWrapper.Unmarshal`), and `Texture2D.LoadRawTextureData(byte[])` crashed the game natively.**
   **Cause:** Unity 6 array bindings under Il2CppInterop. **Fix:** `Texture2D.SetPixel` in batches across frames.
4. **NPC meshes re-bound to the player's bones came out ~100x too big ("inside the head" from the top-down
   camera); swapped into the player's renderers they were culled ("invisible").** **Cause:** the NPC skeleton is
   centimetre-scaled and bindposes don't match the player's rig. **Fix:** keep the NPC's own skeleton (a stripped
   copy of the NPC) and copy the player's bone rotations onto it every frame.
5. **The officer stood upright beside the car door while the player drove.** **Cause:** with the player's
   renderers off (`forceRenderingOff`) its Animator culled and the skeleton froze standing. **Fix:**
   `Animator.cullingMode = AlwaysAnimate` while the look is on. Hiding the body in cars was wrong: the game shows
   the driver.
6. **The proxy officer carried the NPC's hand-held prop.** **Fix:** remove every renderer from the copy except
   the officer's body parts.
7. **World-space models placed in front of the camera never showed in the select screen.** **Cause:** the
   shift-assignment and pause screens draw a full-screen UI background over the world. **Fix:** 2D portraits.
8. **The title-menu entry didn't appear the first two tries.** **Cause:** the menu is built from a pool per panel;
   an option injected into `OptionsPanelContent._menuOptions` is never used for this menu, and a found button may
   be a pooled, inactive one. **Fix:** copy the live first entry of `SidePanelOptions` while `FrontendMainMenu`
   owns it, and hide the copy for other panels.
9. **The game got sluggish, and later the mode's load hung on the loading screen.** **Cause:** per-frame scene
   searches (`GameObject.Find` 5x/s in the city; `FindObjectsOfType` every frame during loading). **Fix:** run
   such searches only on the screens that need them, throttled.
10. **Clicks went through the overlay to the game's shift-assignment buttons.** **Cause:** a Harmony prefix on
    `ShiftStartScreen.UpdateByUIManager` only stops keys and pad; Unity UI buttons take clicks via the
    EventSystem. **Fix:** a `CanvasGroup` on the screen's GameObject with `interactable` and `blocksRaycasts` off.
11. **`Resources.FindObjectsOfTypeAll<T>().FirstOrDefault()` returned a never-active template copy**, so a
    "is the pause menu open" check never fired. **Fix:** check live scene objects (`FindObjectsOfType<T>()`), and
    only where needed (see 9).
12. **Unlock names came out as I2 terms ("Pickables/Weapons/Shotgun_Title").** **Fix:**
    `LocalizationManager.GetTranslation(term)`; keep the term as the stable key.
13. **Rosters drawn from the NPCs loaded nearby repeated looks (four identical female officers).** **Fix:** draw
    looks from the catalogue of variants, one body type per officer; the body is still copied from a loaded NPC of
    that type at shift start (riot officers left out: rarely loaded).

## Assets
Officer portraits: meshes and textures exported from the player's own install with AssetRipper, rendered with
Blender 4.5 (EEVEE, three area lights, 384x480, transparent background). They are derived game assets, so they
stay on the player's machine and are never committed or published; the mod ships only the scripts that make
them.

## Cost and time
About two evenings of interactive work with the player testing.

## Open questions
- Does the select screen reliably return after a real shift end and after a death restart?
- Officer body during cutscenes and on death restarts.
- Riot-officer looks would need a riot NPC loaded to copy the body from.
- The pause-menu check after the live-object fix is unconfirmed in game.
