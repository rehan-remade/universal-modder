---
kind: game
title: Reward multiplier for Exp, Gil and MRP via the difficulty DataTable (UE4SS Lua)
game: Final Fantasy Resonance
games_also: []
game_version: 'Steam 3259780, build 24250053, exe FileVersion 1.0.0.0, UE 5.6 (game module "mucha")'
platform: windows
engine: unreal
route: loader-api
tools:
- UE4SS experimental v3.0.1-1195-g1ceefac8 (2026-11-01)
anti_cheat: 'none (single player; Steamworks only, no EAC/BattlEye/EOS). Denuvo is on the exe and was left untouched: UE4SS loads through a proxy dwmapi.dll and patches no code.'
status: working
agents:
- Claude Code
humans:
- '@ATabor89'
date: '2026-11-01'
links:
- https://github.com/UE4SS-RE/RE-UE4SS
- https://github.com/UE4SS-RE/RE-UE4SS/blob/main/docs/lua-api/classes/udatatable.md
tags: [ue4ss, lua, datatable, reward-multiplier, exp, gold, grinding, runtime-umg, overlay, denuvo, hotkeys]
---
# Reward multiplier for Exp, Gil and MRP via the difficulty DataTable (UE4SS Lua)

> A UE4SS Lua mod that multiplies end-of-battle Exp, Gil and MRP by configurable amounts, so grinding goes
> faster without one reward outpacing the others. It scales the reward rates in the game's own difficulty
> DataTable in memory; no game file is changed. A small on-screen label shows the state, with hotkeys to
> toggle, cycle presets and hide it. Verified in the real game by the human at a grinding spot they knew well:
> rewards doubled at 2x.

## Setup
- **Game:** Steam build 24250053, Windows 11. Content is IoStore (`FFRS-Windows.utoc/.ucas` plus a `_0_P`
  patch), compressed and **not encrypted** (no AES key needed). The exe carries Denuvo (`dtdata.dll` /
  "DENUVO GmbH" strings, renamed high-entropy PE sections).
- **Loader:** UE4SS experimental-latest `v3.0.1-1195-g1ceefac8`. Put `dwmapi.dll` plus `ue4ss/` next to
  `FFRS/Binaries/Win64/FFRS-Win64-Shipping.exe`. The default settings work: the first PS scan logs "Failed to
  find EngineVersion", the second succeeds, and UE4SS settles on engine 5.6. No game config override needed.
- **Mods enabled:** only the mod and `Keybinds`. The stock CheatManager/Console/BPModLoader mods were turned
  off in both `mods.txt` and `mods.json`; they aren't needed.
- **Saves** are in `%LOCALAPPDATA%\FFRS\Steam\<steamid64>\GameSaveData{0,1,2}.sav`. Back them up
  (`um backup create ... --name ffrs-saves`) before the first modded launch.

## Route and why
- **Taken: UE4SS Lua, writing the DataTable rows in memory.** Every reward rate is in one table, the Lua
  `UDataTable` API can write rows by reference, and toggling just writes the shipped values back.
- **Not taken: UE4SS hooks on the rate getters.** They look perfect, but they never fire (Gotcha 1).
- **Not taken: a pak override of the table.** It would work (the IoStore isn't encrypted; `retoc` repacks it),
  but changing the multiplier means rebuilding the pak and restarting. A stale override also survives game
  updates silently.

## How the game works (what we had to learn)
- **Game module is `mucha`**, not `FFRS`: script paths look like `/Script/mucha.CPP_BFL_SaveDataPlayer`.
- **Difficulty table:** `/Game/Datatable/Difficulty/DT_GameDifficultyParam`, row struct
  `/Script/mucha.GAME_DIFFICULTY_PARAM` with the fields `difficulty`, `EnemyHpRate`, `EnemyBreakRate`,
  `EnemyAgilityRate`, `DamageTakenRate`, `DamageGivenRate`, `ExpRate`, `MoneyRate` and `MRPointRate`. There are
  three rows: Easy, Normal and Expert. Every reward rate is 1.0 except Expert's `MRPointRate`, which is 1.5.
- **Gil is "Money" internally** (`MoneyRate`, `AddCurrentMoney`, `GetCurrentMoney`).
- **Getters:** `CPP_BFL_SaveDataPlayer:GetCurDifficulty{Exp,Money,MRPoint}Rate` (static blueprint function
  library), plus `GetCurDifficulty{Hp,BreakPoint,Agility,DamageGiven,DamageTaken}Rate`.
- **The table is read at battle end**, so a change applies to the next fight with no reload. Battle bonuses
  ("No Damage Bonus" +20% Exp, "Stagger Finish Bonus" +30% MRP) are added on top of the scaled base.
- **Result UI:** `CPP_WBP_Btl_Result_PageListBase:SetVM_BattleResult` fires on the result screen's widgets.
  `OnBattleResultBegin/End` exist only on the debug class `CPP_MapDebug_AutoMove`.
- **The table loads early.** The mod finds it about 5 s after it starts.

## Build steps
1. Install UE4SS as in Setup, and set `EnableHotReloadSystem = 1` in `UE4SS-settings.ini` while iterating
   (Ctrl+R reloads all Lua mods in game).
2. Create `ue4ss/Mods/RewardMultiplier/` with an empty `enabled.txt`, add `RewardMultiplier : 1` to `mods.txt`,
   and put three files in `Scripts/`:
   - **`config.lua`** returns a table: `Enabled` (start state, `false` = opt-in), `Exp`, `Gil`, `MRP`,
     `Presets`, key names (`ToggleKey`, `CycleKey`, `ReloadKey`, `OverlayKey`) and the overlay options.
     Load it with `package.loaded["config"] = nil; require("config")`, so a hotkey can re-read it.
   - **`main.lua`**, the table part:
     - Every 5 s (`LoopAsync` → `ExecuteInGameThread`), look in `FindAllOf("DataTable")` for the object whose
       `GetFName()` is `DT_GameDifficultyParam`. Re-find it if `IsValid()` fails or `GetAddress()` changes.
     - The first time you find it, save each row's `ExpRate` / `MoneyRate` / `MRPointRate` from `ForEachRow`.
     - **Apply:** `ForEachRow(function(name, row) row.ExpRate = original * mult ... end)`. Rows are references, so
       the write lands in the live table. When the mod is off, write the originals back.
   - **`overlay.lua`**, the status label, built from stock UMG classes, in this order:
     - `StaticConstructObject` a `/Script/UMG.UserWidget` with the GameInstance as outer and a unique name.
     - Give it a `WidgetTree`, set a `CanvasPanel` as `RootWidget`, and add a `Border` with `AddChildToCanvas`.
       On the canvas slot call `SetAnchors`, `SetAlignment`, `SetPosition` and `SetAutoSize(true)`.
     - Put a `VerticalBox` in the border, holding two `TextBlock`s (status, and a smaller grey hotkey row).
     - Call `AddToViewport(1000)`, and use `SetVisibility(3)` (HitTestInvisible) / `1` (Collapsed) to show and hide.
3. **Keys** (`RegisterKeyBind`; the callbacks run off the game thread, so wrap table writes and widget calls in
   `ExecuteInGameThread`):
   - F7: on/off.
   - F8: cycle presets 1.5/2/3/5 (all three rates together).
   - F9: reload `config.lua`, keeping the current on/off state.
   - F6: show or hide the label.
4. **Uninstall:** delete `dwmapi.dll` and `ue4ss/`. To disable just the mod, set `RewardMultiplier : 0`.

## Verification
- **Log oracle:** with `Debug = true`, the mod logs each row's before and after values on apply (e.g.
  `row Expert: Exp 1.000->2.000 Gil 1.000->2.000 MRP 1.500->3.000`).
- **Human, in game:** at a grinding spot with known rewards, Exp, Gil and MRP doubled at 2x. The label
  showed "Rewards x2 ON" on the menu and the field, and it also appears in Steam F12 screenshots (it's a real
  UMG widget in the game's frame, not an external overlay).
- **First test (getter hooks):** a 2x battle gave unchanged rewards (560 Exp, 450 Gil, 20 MRP before
  bonuses), and none of the hooks fired. That's how Gotcha 1 was found.
- **Not verified:** what happens when the label is off for a whole map transition and then shown again (it is
  rebuilt on demand); whether quest or colosseum rewards also use these rates; and changing difficulty
  mid-session (all three rows are scaled, so it should hold).

## Gotchas
1. **Hooks on `GetCurDifficultyExpRate`/`MoneyRate`/`MRPointRate` register but never fire.** **Cause:** the
   battle code calls these static functions straight from C++, and UE4SS `RegisterHook` only sees UFunctions
   called through the script VM / ProcessEvent. **Fix:** change the data they read
   (`DT_GameDifficultyParam`) instead of their return values.
2. **`dt:GetRowStruct():ForEachProperty(...)` errors with "attempt to call a TrivialObject value".**
   **Cause:** `GetRowStruct()` returns a plain object wrapper without the UStruct methods. **Fix:** take its
   path from `GetFullName()` and look it up again with `StaticFindObject(path)`; that one has
   `ForEachProperty`. (Or just use the known field names.)
3. **Set the table variable only after capturing the originals.** If capture throws after `tbl` is set, the
   "already found" check skips every later retry and nothing is ever applied. Capture first, then cache.
4. **Hot reload (Ctrl+R) leaves the old label on screen.** **Cause:** the old widget stays in the viewport with
   no owner. **Fix:** name widgets with a fixed prefix plus a timestamp, and on start call `RemoveFromParent()`
   on every `UserWidget` with that prefix. Never reuse a name (constructing over an existing name is unsafe).
5. **Map loads clear viewport widgets.** **Fix:** a 1 s loop checks `IsValid()` and `IsInViewport()` and
   rebuilds the label if needed.
6. **An opt-in start needs care with config reload.** If `Enabled` in the config is the start state, a plain
   config reload turns the mod off mid-grind. Keep the runtime on/off state across reloads.

## Assets
None. The label is built from stock UMG classes at runtime.

## Cost and time
About an hour from first scan to a working mod with the overlay, plus a few test battles by the human.

## Open questions
- Quest rewards (`CPP_BFL_SaveDataQuestBoard:GetRewards`) and colosseum rewards probably don't go through
  these rates; untested.
- A `breakFinishBonusMoneyMultiplier` / `noDamageBonusExpMultiplier` pair exists in the exe's names (bonus
  tuning), probably in another table. Not explored.
