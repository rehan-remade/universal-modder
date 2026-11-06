---
kind: game
title: Runtime cheat menu for money, subscribers and needs via UE4SS Lua
game: 'WebCam: Behind The Screen'
games_also: []
game_version: Steam build 25089974 (app 4341260), UE 5.5, project WebCam_Girl_Sim
platform: windows
engine: unreal
route: loader-api
tools:
- UE4SS experimental v3.0.1-1168-g4e079ec4 (2026-10-13)
anti_cheat: 'none: single-player only, with no multiplayer, leaderboards or in-game purchases'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-13'
links:
- https://github.com/UE4SS-RE/RE-UE4SS
tags: [ue4ss, lua, cheat-menu, trainer, stats, gameplay-tags, runtime-umg, overlay, file-bridge]
---
# Runtime cheat menu for money, subscribers and needs via UE4SS Lua

> An F1 cheat panel for WebCam: Behind The Screen. It edits money, subscribers, donations, the four needs
> (Energy, Satiety, Hygiene, Bladder), Orgasm and the energy-drink counter, and can freeze needs at full.
> It's one UE4SS Lua file. The panel is a UMG widget built at runtime from engine classes, so there are no
> paks and no editor. The human verified every row in the real game.

## Setup
- **Game:** Steam app 4341260, build 25089974, Windows 11. UE 5.5, project `WebCam_Girl_Sim`.
  - IoStore paks (`WebCam_Girl_Sim-Windows.utoc/.ucas`). They were never opened.
- **Loader:** UE4SS experimental-latest `v3.0.1-1168-g4e079ec4`. Put `dwmapi.dll` plus `ue4ss/` next to
  `WebCam_Girl_Sim/Binaries/Win64/WebCam_Girl_Sim-Win64-Shipping.exe`.
  - The default settings work. The AOB scan finds GUObjectArray and FName, and no game config is needed.
  - It loads fine when the game is started from Steam (the outer `WebCam_BehindTheScreen.exe` is a launcher).
- **Saves:** none existed before the first run. Expect `%LOCALAPPDATA%\WebCam_Girl_Sim\Saved\SaveGames`
  (not checked).

## Route and why
- **Taken: UE4SS Lua (loader-api).** Every stat lives in one Blueprint component with a clean get/set API,
  all reachable at runtime.
- **Not taken:** pak or Blueprint mods. They'd need FModel, mappings and a UE 5.5 editor, which is a lot of
  work for a trainer.

## How the game works (what we had to learn)
- **Where the stats live:**
  - The player controller `BP_PlayerController_WCG_C` (on map `/Game/WebCam_Girl/Map/Map_HomeSolo`) owns about
    20 components: Stats, Bladder, Rent, Debt, Inventory, Quests, Selfie and more.
  - Every number the player cares about is in `BP_StatsComponent` (`BP_StatsComponent_C`).
- **`Stats`** is a `TMap<FGameplayTag, double>`. The tags seen were:
  - needs: `Stats.Energy`, `Stats.Satiety`, `Stats.Hygiene`, `Stats.Bladder`;
  - economy: `Stats.Money`, `Stats.Subscribers`, `Stats.Donations`;
  - other: `Stats.Orgasm`, `Stats.Calories.Earned/Burned`, `Stats.Subscribers.Stream`, `Stats.Member.Orgasm`,
    `Stats.Member.Donations`, `Stats.Used.EnergyDrink`.
- **`Limits`** is a `TMap<FGameplayTag, FFloatInterval>`:
  - Energy and Satiety: 0..100.
  - Hygiene, Bladder, Orgasm and Member.Orgasm: 0..1.
  - Used.EnergyDrink: 0..3.
  - Money, Subscribers and Donations have no limit entry.
  - Other fields: `LockedStats` (a set of tags), `ConsumeMultipliers`, and `InitialStats` (the DataTable
    `DT_InitialStats`).
- **Game rules (from the human, who plays it):**
  - `Stats.Donations` is the running donation total of the current stream. It's paid out as Money when the
    stream ends, so adding donations is an indirect money cheat.
  - `Stats.Used.EnergyDrink` counts the drinks used today and resets each day. The game allows only 2 per day,
    even though the `Limits` entry is 0..3, so the mod caps it at 2.
- **API (Blueprint functions, callable from Lua):** `GetStat(Stat, out Value)`, `SetStat(Stat, Value)`,
  `AddStat`, `ConsumeStat`, `ResetStat(Stat)`, `LockStat(bLock, Stat)`, `GetStatPercent`, `IsStatUnlocked`,
  plus an `OnStatChanged(Stat, Value)` delegate.
  - `SetStat` clamps to the limits and fires the delegate, so the HUD updates at once.
- **Every need is higher-is-better, Bladder included.** Bladder reads 1.0 right after using the toilet, and
  the HUD bar is full at 1.0 (it shows relief, not fullness).
- **The UI widgets** (`WG_WCG_Money_C`, `WG_WCG_Stat_Subscribers_C`, …) only display values. Don't write to
  them.

## Build steps
1. Install UE4SS as described in Setup.
2. Create `ue4ss/Mods/CheatMenu/Scripts/main.lua` and an empty `enabled.txt`.
3. **Find the component:** use `FindAllOf("BP_StatsComponent_C")`, skip `Default__`, and cache it, checking
   `IsValid()` every time.
4. **Read and write:**
   - Read: `local r = {}; sc:GetStat({TagName = FName("Stats.Money")}, r); r.Value`.
   - Write: `sc:SetStat({TagName = FName("Stats.Money")}, v)`.
   - To zero a stat, see Gotcha 1.
5. **Panel:**
   - `StaticConstructObject` a `/Script/UMG.UserWidget` with the game instance as outer.
   - Construct a `WidgetTree` with the widget as outer and assign it to `w.WidgetTree`.
   - Build `CanvasPanel` (as `tree.RootWidget`) → `Border` (`AddChildToCanvas`, slot `SetAutoSize(true)`,
     `SetPosition`) → `VerticalBox` → `TextBlock` rows, all with the tree as outer.
   - Change the font size by copying `t.Font`, setting `.Size`, then calling `t:SetFont(font)`.
   - Call `w:AddToViewport(1000)`.
   - Show it with `SetVisibility(3)` (HitTestInvisible, so it never takes the mouse). Hide it with `1`
     (Collapsed) instead of removing it.
6. **Input:**
   - `RegisterKeyBind(Key.F1, …)` toggles the panel; arrows navigate. Modifier variants:
     `RegisterKeyBind(Key.RIGHT_ARROW, {ModifierKey.SHIFT}, …)`.
   - Wrap every callback in `ExecuteInGameThread`.
7. **Freeze:** a `LoopAsync(500)` loop calls `SetStat(max)` on any need that has drifted.

## Verification
- **Oracle:** a dev "bridge" mod reads Lua from a file every 500 ms, runs it with `ExecuteInGameThread` and
  appends the output to a text file. It found the component, the tags, the limits and the write behaviour
  with no restarts while the human played. Every finding above came from it.
- **Human, in game:**
  - The panel shows.
  - Money and subscribers change and the HUD follows.
  - Needs fill and empty, and the Bladder direction was confirmed against the toilet.
  - Freeze holds the needs.
  - Donations, Orgasm and the energy-drink counter all work.
- **Bridge only:**
  - `SetStat` for Used.EnergyDrink (0 → 2) and `ResetStat` (→ 0).
  - A direct `Stats:Add(tag, 0.0)` write.
- **Human, game rules:** donations are paid out as money after a stream, and the energy-drink counter
  resets daily. This comes from normal play, not from tracing the Blueprint.
- **Not verified:** save/load persistence of edited values.

## Gotchas
1. **`SetStat(tag, 0)` silently does nothing.** Values like 0.0001 or 0.5 stick, but exactly 0 is ignored.
   That made "empty bladder" look broken. **Cause:** a check inside the Blueprint `SetStat`; the exact
   condition wasn't identified. **Fix:** call `SetStat(tag, 0.01)` so the HUD updates, then write the true
   zero straight into the map with `sc.Stats:Add(tag, 0.0)`. `ResetStat` also reaches 0, but it resets to
   the DataTable's initial value, so it isn't a general zero.
2. **A new Lua mod didn't start on auto-reload.** **Cause:** `EnableAutoReloadingLuaMods` only reloads mods
   that were already running at startup, and even those not every time. **Fix:** press Ctrl+R (hot reload
   all, with `EnableHotReloadSystem = 1`). Close a runtime panel before reloading, or the old widget stays
   on screen with no owner.
3. **`Set-Content -Encoding utf8` in Windows PowerShell 5 writes a BOM.** Lua `load()` then fails with
   `unexpected symbol near '<\239>'`. **Fix:** strip `^\239\187\191` before `load`, or write the file with
   `[IO.File]::WriteAllText`.
4. **`UClass:FindProperty` and `FMapProperty:GetValueProp` aren't exposed** in this UE4SS Lua build, and the UE4SS
   Lua API docs don't list them either (`UStruct` documents only `GetSuperStruct`, `ForEachFunction` and
   `ForEachProperty`). It errored with "attempt to call a TrivialObject value". **Fix:** to find a map's value
   struct, walk `ForEachFunction` → `ForEachProperty` on a Blueprint function that has a local of that type (here
   `SetStat`'s `CallFunc_Map_Find_Value`), then call `GetStruct()`.
5. **Don't trust the stat name for its direction.** We first assumed Bladder meant fullness, so low would be
   good. It's the other way round. Check against an in-game action (the toilet) and the HUD bar.

## Assets
None. The panel is built from stock UMG classes at runtime.

## Cost and time
One session of about 30 minutes, with no paid API calls.

## Open questions
- Which function pays `Stats.Donations` out as Money at stream end, and what is `Stats.Member.Donations` for?
- Does `LockStat(true, tag)` freeze a stat natively? It might be cleaner than the polling freeze loop.
- Rent and debt (`BP_RentComponent`, `BP_DebtComponent`) are obvious next cheat targets.
