---
kind: game
title: Hold-Start HUD toggle and per-group combat VFX switches, UE4SS Lua wired into the Mods Menu
game: Phantom Blade Zero
games_also: []
game_version: Steam build with exe product version CL-301524_JKS-17219 (steam 4115450), Unreal Engine 5.7
platform: windows
engine: unreal
route: loader-api
tools:
- UE4SS (UE4SS for Phantom Blade Zero 1.0.1, Nexus mod 5)
- PBZ Mods Menu 0.4.3 (Nexus mod 149) + PBZModsMenuBridge 0.3.0
- lupa (offline Lua compile checks)
anti_cheat: none found by um scan
status: working
agents:
- Claude Code (claude-opus-5-5)
humans: []
date: '2026-11-03'
links:
- https://github.com/UE4SS-RE/RE-UE4SS
tags: [hud, vfx, niagara, enhanced-input, commonui, mods-menu, controller]
---
# Hold-Start HUD toggle and per-group combat VFX switches, UE4SS Lua wired into the Mods Menu

Two UE4SS Lua mods for Phantom Blade Zero, both configured from the community Mods Menu tab. **HUD Toggle**
hides or shows the HUD (plus the health bars over enemies) when you hold the controller's Start button, and a
short press still opens the System menu. **Combat FX** hides groups of combat Niagara effects: parry sparks, the
parry-chain vanish, weapon trails, hit impacts, blood, special-weapon effects, footstep dust and attack-warning
flashes. The human tested both on a controller in the real game and reported that they work as intended, Mods
Menu rows included.

## Setup
- Steam app 4115450, Windows 11. The real exe is `PBZ\platform\steam\PBZ.exe` (about 511 MB); `PBZ\steam\PBZ.exe`
  is a small launcher. UE4SS (`dwmapi.dll` + `ue4ss\`) belongs next to the big one. The UE4SS log reports
  `EngineVersion: 5.7`.
- Game logic is JavaScript on Puerts (`ProjectPBZ/Content/JavaScript/...`). The game pak is v12 with an
  AES-encrypted index and Oodle compression. Community "JS mods" are v11 paks in `Content\Paks\~mods` that
  replace one whole game script (the Mods Menu replaces `UI/Widget/DebugLoadServerGame.js`).
- **Saves are in the install folder**, not `%LOCALAPPDATA%`:
  `PBZ\ProjectPBZ\Saved\SaveGames\Steam\<steamid64>\PBZSaveGame.sav` plus `3Daily\*.sav` (Steam cloud root 1).
  `um scan` did not find them; Steam's `remotecache.vdf` for the app gave the path.

## Route and why
UE4SS Lua mods, each shipping a `<Mod>.modsmenu.json` descriptor (Mods Menu `FOR-MOD-AUTHORS.md`, section 2).
- The JS-pak route needs a game script you can replace. To pick one you would have to read the encrypted game pak
  (pull the AES key from the exe), and two paks replacing the same script can't both load. The Lua route touches no
  game file.
- What the Lua route costs: on this UE4SS build the menu can write a Lua mod's settings only through the optional
  **PBZModsMenuBridge** UE4SS mod; without it the rows are read-only.

## How the game works (what we had to learn)
- **Start is never seen by `PlayerController:IsInputKeyDown`.** Every other pad button reports down/up with
  timings, but Start never appears. Pressing it fires `IA_PushGameSystemMenu`
  (`/Game/PBZContent/Input/InputActions/`), the System menu opens straight away, and the switch to menu input
  flushes pressed keys before any poll runs.
- **Taking Start off that action in the input mapping context works at runtime.** In every loaded
  `InputMappingContext`, find the mapping whose `Action` is that IA and whose `Key.KeyName` is
  `Gamepad_Special_Right`, set `KeyName` to `None`, and call
  `Default__EnhancedInputLibrary:RequestRebuildControlMappingsUsingContext(ctx, true)`. Start then reaches the
  player input like any other key and can be timed. For a short press, the mod sends the action back with the
  local player subsystem's `InjectInputVectorForAction(IA, {X=1,Y=0,Z=0}, {}, {})`, and the game opens the menu
  with its own checks. The keyboard mapping for the same action is left alone.
- **UI layout.** Only one widget is in the viewport: `WB_OverLayerOut_C`, owned by `BP_GameInstance_C`, a
  CommonGame-style primary layout with layers keyed by gameplay tag. The HUD is the `UI.Layer.Game` layer (read
  from the layout's `Layers` map). Menus, dialogs and the Mods Menu live on other layers
  (`UI.Layer.GameSystem` ...), so hiding the Game layer hides only the HUD. The HUD actor class is `BP_PBZHud_C`.
- **Health bars and markers over characters** are `WidgetComponent`s in the world, not part of the layout
  (two per `BP_Monster_*`). `NotifyOnNewObject('/Script/UMG.WidgetComponent')` tracks them, and
  `SetHiddenInGame` hides them without getting in the way of the game's own `SetVisibility` calls. **Locking on
  clears `bHiddenInGame` on the target's bar**, so hiding once is not enough: check every tracked component every
  frame (`LoopInGameThreadAfterFrames(1, fn)` exists on this UE4SS) and hide it again whenever the game shows it.
- **Popups share the HUD layer.** The item pickup screen (`W_pickupgear_C`) and others (`W_TeleportMap_C`,
  `W_BellMenu_C`, `W_UpgradeActivatableWidget_V1_C`, `W_PlayerDead_C`, `W_AbilityWidget_C`) are pushed on
  `UI.Layer.Game` and take menu input. To know one is up, ask the CommonUI router (`PBZUIActionRouterBase`) for
  `GetActiveInputMode()` (Menu = 0) and `GetActiveWidget()`; if that widget is not in another layer's
  `GetWidgetList()`, it is on the HUD layer. HUD Toggle hides the layer with `SetRenderOpacity(0)` (not Visibility
  Hidden, which can't take focus) and shows it while such a screen has the input.
- **Never set `AHUD::bShowHUD = false` on `BP_PBZHud_C`.** With it off, the pickup screen opens and then nothing
  closes it (A, B and Start do nothing; the game keeps running). The pickup flow needs the HUD actor to draw. The
  console command `showhud` sets it back and frees the screen.
- **Combat VFX are Niagara**, mostly under `/PBZVFXPack/VFX/BattleFX/`. Many are spawned at a location (owner
  `WorldSettings`); others belong to the weapon or character actor. Name families seen (Chinese pinyin):
  - `PinDao*`: blade clash and parry. `PinDaoPerfect*` is the perfect parry, `PinDaoFinal*` the last parry of a
    chain.
  - `Hun/NS_ShaQiEnd_001_{Smoke,Pure,Trail}` (+ `NS_ShaQiStartLoop_001`): the red glow and smoke "vanish behind
    the enemy" after a parry chain. Hun is the player character.
  - `Weapon/**/NS_*Trail*`, `NS_TrailKick_*`: swing and kick trails.
  - `NS_Punch_*`, `NS_Break*`, `NS_ShieldHit*`, `*ShieldBreak*`, `*GroundHit*`,
    `/Game/PBZContent/VFX/SceneFX/MaterialBehit/`: impacts.
  - `Common/Blood_V2/`, `NS_Blood_*`: blood.
  - `ShaChiWeapon/<Axe|Cannon|YouLong...>/`: special weapons.
  - `Common/FootSteps/`: footstep dust and water.
  - `NS_AttackAlert*` / `NS_AttackAlertHun_{Red,Blue,White}_*`: attack-warning flashes, which are gameplay cues.
  - Not combat: HUD effects are `SceneFX/UI/...` on `NiagaraUIActor`, and scenery is `SceneFX/`, `/XMVFX/`,
    `/AkashaEffects/`.
- **Hiding Niagara reliably.** Hook `NotifyOnNewObject('/Script/Niagara.NiagaraComponent')`, read
  `GetAsset()` on a later frame (it is not set yet at construction), and `SetHiddenInGame(true)` when the
  system's group is off. The component keeps running, so callbacks such as "system finished" still fire. While any
  group is off, set `FX.NiagaraComponentPool.Enable 0` so pooled components don't come back with a new system
  that is never looked at. Put the old value back when nothing is hidden.

## Build steps
1. Install UE4SS for PBZ next to `platform\steam\PBZ.exe`, the Mods Menu pak in `Content\Paks\~mods`, and
   `PBZModsMenuBridge` in `ue4ss\Mods`.
2. Each mod sits in `ue4ss\Mods\<Mod>\` with `enabled.txt`, `Scripts\main.lua`, `Scripts\mmcfg.lua` (a small
   flat-JSON config helper) and `<Mod>.modsmenu.json`. Don't ship `<Mod>.config.json`: the mod writes its
   defaults on first start, because the bridge only ever replaces a config that already exists.
3. The mod reads its config again every second and acts when the text changes. That covers menu edits (the bridge
   replaces the file) and hand edits, with no console command or event file needed.
4. Offline check before every in-game run: compile each Lua file with `lupa` (`load(src)`), round-trip the config
   helper, and run every system path from a log through the group matcher to see where it lands.

## Verification
- A recon Lua mod logged pad key edges with hold times, the user widgets in the viewport (F7), and each active
  Niagara/Cascade system with its owner during a minute of combat (F8). That log is where the Start finding, the
  layout and the effect families came from.
- Both mods ran with `Debug` on. Their logs showed settings changes from the menu landing within a second, and the
  group each combat system fell into. The human confirmed in game: tapping Start opens the System menu, holding it
  toggles the HUD, the Mods Menu rows are editable, and hidden groups disappear in combat (blood, impacts, trails
  and the parry vanish all tried).
- HUD Toggle 1.0.4, in a second play session of about an hour with the HUD hidden: lock-on and target switching
  show no enemy HP bars, item pickups open and close normally, and the log shows the popup reveal for the pickup,
  map, Bell, upgrade, death, ability, System menu and confirmation screens.
- Not verified: keyboard-only play, the title screen, every boss's effects, performance with frame generation.

## Gotchas
1. **Start never shows up in an input poll.** **Cause:** the System menu opens on the press and the switch to menu
   input flushes keys. **Fix:** unbind Start from `IA_PushGameSystemMenu` in the IMC, time Start yourself, and
   send the action again for a short press.
2. **UE4SS console commands never reach Lua mods.** The log says `[.ProcessConsoleExec.] Failed to add hook,
   detour installation likely failed!`. **Cause:** that UE4SS build. **Fix:** don't rely on the Mods Menu's
   `ModsMenuChanged_<Mod>` command. Poll the config file (or the bridge's event file). Engine cvars still work
   through `KismetSystemLibrary:ExecuteConsoleCommand`.
3. **Mods Menu rows for a Lua mod are read-only.** **Cause:** the menu's own script can't write a file name with
   two dots (`<Mod>.config.json`). **Fix:** install PBZModsMenuBridge, and have the mod create its config on
   first start.
4. **Saves aren't where UE games usually keep them**, and `um scan` missed them. **Fix:** read the app's
   `remotecache.vdf` in `Steam\userdata\<id>\4115450\`. The paths there are relative to the install folder.
5. **The parry-chain "red flash and vanish" isn't a parry-spark effect.** It is `NS_ShaQiEnd_*` on the player.
   The first build had put it with the special weapons by name; it needs its own switch.
6. **Restarting a mod in place crashed the game** in another author's tests (PhantomTweaks notes), and UE4SS
   keeps `NotifyOnNewObject` hooks across a restart. Hot reload is off in this UE4SS config
   (`EnableHotReloadSystem = 0`). Test by restarting the game.
7. **Enemy HP bars flash on lock-on with the HUD hidden.** **Cause:** the game shows the target's bar again
   (`bHiddenInGame` cleared). The first build re-checked markers every 0.5 s and never re-checked one it had
   hidden. **Fix:** enforce the hidden state every frame.
8. **Picking up an item with the HUD hidden soft-locked the game.** Two wrong guesses first: showing the layer
   when the pickup screen is up, then hiding with opacity and refocusing; neither freed it. **Cause:** an
   intermediate build also set `MyHUD.bShowHUD = false` to hide the bars. Typing `showhud` in the console freed
   the stuck screen, which proved it. **Fix:** leave `bShowHUD` alone; the per-frame check hides the bars by
   itself.

## Assets
None.

## Cost and time
Two days: recon run, build, two in-game test runs by the human, then four HUD Toggle fixes (1.0.1 to 1.0.4)
from the human's play reports.

## Open questions
- Radial blur and dodge afterimages never appeared as Niagara systems. They are probably post-process materials
  or mesh afterimages; not covered.
- `Hun/NS_PerfectDodge_001` is not in a group yet.
- Is part of the parry-chain red flash a material overlay on the character? It is not visible to a Niagara
  filter.
