---
kind: game
title: In-game F1 cheat menu with BepInEx 6 IL2CPP and IMGUI
game: SiNiSistar 2
games_also: []
game_version: v1.3.1 (build v1.3.1-2b770f7, steam 4466620)
platform: windows
engine: unity-il2cpp
route: managed-patch
tools:
- BepInEx 6.0.0-be.788 (Unity.IL2CPP win-x64)
- HarmonyX (bundled with BepInEx)
- Cpp2IL 2022.1.0-pre-release.21
- .NET SDK 10.0.300 (targeting net6.0)
anti_cheat: 'none: single-player only, with no multiplayer, leaderboards or in-game purchases'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-14'
links:
- https://builds.bepinex.dev/projects/bepinex_be
- https://github.com/SamboyCoding/Cpp2IL/releases
tags:
- cheat-menu
- imgui
- il2cpp
- harmony
- single-player
---
# In-game F1 cheat menu with BepInEx 6 IL2CPP and IMGUI

> A BepInEx 6 IL2CPP plugin for SiNiSistar 2 (Unity 2022.3, IL2CPP) that draws an IMGUI window on F1. The window
> covers survival (god mode, infinite HP/MP/clothing durability, refill), relics (currency), giving items and
> wands, and combat (one-hit kills, damage multiplier, crit). Verified in a real save via screenshots, the HUD,
> the BepInEx log and the human playing through fights with it on.

## Setup
- SiNiSistar 2 v1.3.1 (Steam 4466620), Windows 11, fullscreen 1920x1080.
- Unity 2022.3.62f2, IL2CPP, `global-metadata.dat` **version 31**.
- BepInEx `6.0.0-be.788+5b766a3` IL2CPP win-x64 (bleeding-edge build server). Unzip into the game folder;
  the first launch generates interop in about 40 s (it reports roughly 8k of 9.3k method bodies unstripped).
- Cpp2IL `2022.1.0-pre-release.21` for type and field stubs (`--output-as diffable-cs`).
- Plugin: `net6.0` class library referencing `BepInEx/core/*` and `BepInEx/interop/*` (`SiNiSistar2.dll`,
  `Il2Cppmscorlib`, `UnityEngine.CoreModule`, `UnityEngine.IMGUIModule`, `Unity.InputSystem`) with
  `Private=false`. Built with the .NET 10 SDK, which needs `CheckEolTargetFramework=false`.

## Route and why
`managed-patch`: BepInEx 6 + Harmony through Il2CppInterop. There is no community loader or API for this game. The
game does ship an official `Mod\` folder, but it only covers sprite skins (`Mod\Player\<Skin>\Animation|Portrait`,
PNG frames) and localization JSON (`Mod\Localize\<Name>\LocalizeTable*.json`), so it can't change gameplay.
MelonLoader would work equally well; BepInEx was picked as the usual IL2CPP default.

## How the game works (what we had to learn)
- All game code is in the `SiNiSistar2` assembly. **`SiNiSistar2.Manager.ManagerList`** exposes static getters for
  every manager: `PlayerStatus`, `Debugger`, `Damage`, `Time`, `Map`, `Event`, `Gallery`, `SaveData`, `Input`,
  `UIList`, and others. `ManagerList.HasCompletedFirstInitialize` is false until the game has booted; check it
  before touching anything.
- **`SiNiSistar2.Obj.PlayerStatusManager`** holds the player state:
  - `HP`, `MP` and `Durability` (clothing) are all subclasses of `BattleMainParameter`, which has `Current`,
    `Max`, `SetCurrentValue(int, bool silent)`, `Sub(int, bool)`, `Recover` and `DontSub`.
  - `RecoverHP/RecoverMP/RecoverDurability(RecoverCalcType{Rate, DirectValue, Additive}, value, ...)`.
  - `Relics` is the currency. Its setter is private; use `AddRelics(int n, bool addGameOver, bool immediate)`
    or `SubRelics`.
  - `InventoryHandler.AddItem(ItemID, count)`, `GetItemCount`, `RemoveItem`; `EquipWand(ItemID)`.
  - `DamageInvincible` is a getter only (computed), so patch it with a Harmony postfix.
- `ItemID` is in the global namespace, with values 0–29 (for example `PortionHP`=0, `Elixir`=27, and wands
  `WeaponYew/WeaponAspen/WeaponSwordWand/WeaponTranquebar/WandIron/WeaponWeak`).
- Enemies are `EnemyObject : SiNiObject`, and `SiNiObject.HP` is the same `HP : BattleMainParameter` type, so a
  single prefix on `BattleMainParameter.Sub` can tell player and enemy apart by comparing the instance pointer with
  `PlayerStatus.HP/MP/Durability`.
- A developer **`Debugger`** manager ships in the build with flags such as `IsPlayerSuperTough`,
  `CriticalDamage`, `IsOverwriteDamage/OverwriteDamageValue` and `StopEnemyPoiseIncrementRecover`. It is not
  yet known whether it is instantiated in release builds or whether gameplay code reads these flags.
- Input uses the **new Input System**: read keys with `UnityEngine.InputSystem.Keyboard.current.f1Key`.
- The save folder is `%USERPROFILE%\AppData\LocalLow\Uu\SiNiSistar2\SaveData_S`.

## Build steps
1. Back up the save folder.
2. Unzip BepInEx 6 be.788 IL2CPP win-x64 into the game folder. Launch once and wait for
   `Chainloader startup complete` in `BepInEx/LogOutput.log`.
3. Create a `BasePlugin` and in `Load()` call `new Harmony(guid).PatchAll(typeof(Patches))` and
   `AddComponent<CheatMenu>()`. The MonoBehaviour needs the `(IntPtr)` constructor.
4. In the menu MonoBehaviour, `OnGUI` calls `GUI.Window(id, rect, (GUI.WindowFunction)Draw, title)`. Draw only with
   `GUI.Label`/`GUI.Button`/`GUI.DragWindow` and hand-computed `Rect`s (see Gotcha 1).
5. Patches:
   - a prefix on `BattleMainParameter.Sub` that returns false for the player's bars when the matching cheat is on,
     and raises `sub` for non-player `HP` (`TryCast<HP>()`) when one-hit or a multiplier is on;
   - a postfix on the `PlayerStatusManager.DamageInvincible` getter.
6. Every frame, top up the bars with `SetCurrentValue(Max)` while the infinite toggles are on.
7. `dotnet build -c Release` with a post-build Copy into `BepInEx/plugins`. Close the game first, because it locks
   the DLL.

## Verification
The oracle was the real game: load a save, press F1, click buttons, and check full-resolution screenshots
(`um win shot`) and the HUD, plus `BepInEx/LogOutput.log`.
- Verified: the menu opens and closes and shows live HP/MP/clothing values. Refill took clothing from 0 to 100, and
  the portrait changed. +1000 relics changed the HUD from 44 to 1,044. Give+equip of `WeaponAspen` worked, and the
  portrait wand changed. Items +1/+10 took `PortionHP` from 0 to 11 and `Elixir` from 0 to 10.
- God mode was verified by the human in real fights: with god mode on and infinite durability off, HP never drops,
  but clothing durability still takes damage. Player HP and clothing are separate `BattleMainParameter`s, so the
  toggles are independent. The log showed `BattleMainParameter.Sub hook active` with no errors, which confirms that
  `Sub` is the damage path. The human reported the rest of the menu working as intended; I did not separately
  measure the damage multiplier or crit.

## Gotchas
1. **IMGUI calls throw `NotSupportedException: Method unstripping failed`.** **Cause:** the game never used
   `GUILayout.Toolbar` (and probably other GUILayout helpers), so IL2CPP stripped them, and Il2CppInterop
   could not restore the body. `GUI.Window` still drew its frame, but the window function threw. **Fix:** build
   the UI only from `GUI.Label`, `GUI.Button` and `GUI.DragWindow` with manual `Rect` layout. Draw toggles as
   `[ON]/[off]` buttons and the slider as -/+ buttons, and use tabs instead of a scroll view.
2. **`GUILayout.X(..., null)` causes compiler error CS0121 (ambiguous call).** **Cause:** the interop generates
   both an `Il2CppReferenceArray<GUILayoutOption>` overload and a `params GUILayoutOption[]` overload. **Fix:**
   pass no options argument at all.
3. **Cpp2IL 2022.0.7 is too old.** **Cause:** metadata v31 (Unity 2022.3). **Fix:** use the
   `2022.1.0-pre-release.x` line.
4. **Mouse clicks do nothing on the title menu.** **Cause:** the game's own menus are keyboard/gamepad-driven.
   **Fix:** to automate, press Enter on splash, Enter on Continue (preselected), then wait about 15 s to load.
   IMGUI windows do receive mouse clicks normally.
5. **Building fails with MSB3027 "file is locked by SiNiSistar2.exe".** **Cause:** BepInEx keeps the plugin DLL
   open. **Fix:** kill the game by PID before building, or copy the DLL afterwards.
6. **Click coordinates computed from the IMGUI rect miss.** **Cause:** the IMGUI window position in the capture did
   not match the window rect in pixels (it rendered lower and further right than expected at 1920x1080 fullscreen).
   **Fix:** measure button positions from a screenshot and scale them back up, rather than computing them.
7. **`Plugin.Log` hides `BasePlugin.Log` (warning CS0108).** **Fix:** declare it as
   `internal static new ManualLogSource Log`.

## Assets
None.

## Cost and time
About 1 session (around 1.5 h wall-clock), including recon, dumping, two UI iterations and in-game checks.

## Open questions
- Is the `Debugger` manager non-null in release builds, and are its flags (`IsPlayerSuperTough`, `CriticalDamage`)
  read by gameplay code?
- Grab and instant-game-over events probably bypass HP entirely, so god mode won't stop them.
