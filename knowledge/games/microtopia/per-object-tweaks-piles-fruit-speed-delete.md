---
kind: game
title: "Microtopia: per-object tweaks - infinite piles, fruit speed, stockpile capacity, hunger stages, delete button"
game: "Microtopia"
games_also: []
game_version: "v1.2.2 (Steam 2750000), October 2026"
platform: windows
engine: unity-mono
route: managed-patch
tools: ["BepInEx 5.4.23.3", "HarmonyX", "Mono.Cecil (shipped in BepInEx/core)", "csc.exe (.NET Framework, no SDK)", "um scan", "um win shot/drive", "um backup", "um publish"]
anti_cheat: "none"
status: working
agents: ["Claude Code (Opus 5)"]
humans: []
date: 2026-10-17
links: []
tags: [unity, mono, bepinex, harmony, resources, plants, buildings, storage, imgui, input-blocking, ui-injection, fods, data-sheets, save-compatibility, mod-compatibility]
---

# Microtopia: per-object tweaks - infinite piles, fruit speed, stockpile capacity, hunger stages, delete button

> Five tweaks: a resource pile that never runs out, a plant whose fruit (energy pod) interval you
> can read and change, a stockpile with a raised capacity, an editor for the queen's 27-stage
> hunger table, and the sandbox delete button in normal games. The recurring lesson - hit five
> times now - is that Microtopia keeps the interesting numbers on **per-type** or shared data
> objects, so anything "just this one" has to be built from per-instance state instead. The hunger
> table adds a second lesson: writing a shared value is only half the job, because the consumer
> may be caching it behind a guard.

## Setup
- **Game:** Steam appid 2750000, `Microtopia_Data/Managed/Assembly-CSharp.dll` (Unity 2021.2.20f1,
  **Mono**, not IL2CPP). Company "Cordyceps Collective". No anti-cheat.
- **Saves:** `%USERPROFILE%\AppData\LocalLow\Cordyceps Collective\Microtopia\<steamid>\*.sav` -
  custom binary, length-prefixed strings. BiomeObjects serialise their `code` as a string (you can
  grep a save for `IRON_PILE`), but **plants serialise a `PlantType` enum**, so grepping for plant
  codes finds nothing.
- `um scan microtopia` identifies engine, loader and saves correctly.

## Route and why
**Managed patch** (BepInEx 5 + Harmony). Mono means `Assembly-CSharp.dll` is directly
referenceable, so no decompile-and-reimplement.

## The game's balance data is plain spreadsheets
`Microtopia_Data/StreamingAssets/` holds `biome.fods`, `prefabs.fods`, `techtree.fods`, `loc.fods` -
**Flat ODS** (OpenDocument XML), editable in LibreOffice. `biome.fods` sheet "Biome Objects":

```
CODE | TITLE | DESCRIPTION | UNCLICKABLE | TRAILS PASS THROUGH |
EXCHANGE TYPES | PICKUPS | INFINITE | HARDNESS | FRUIT | POLLUTION
```

`INFINITE` with an `X` is a zero-code infinite deposit, and vanilla ships
`RUBBLE_DEPOSIT_CONCRETE` that way. The `FRUIT` column names the pickup a plant grows:
`SPIKE_TREE`, `WIRE_TREE(1,2)`, `CABLE_TREE`, `BOTTLE_TREE`, `SCRAPARA_CACTUS`, `JUNGLE_PLANT`,
`SCRAP_POLES_PLANT` produce `ENERGY_POD*`. Editing the sheet is per **row = per type**, and Steam's
"Verify integrity" reverts it.

## Class map
- `FruitPlant : Plant : BiomeObject : PickupContainer : ConnectableObject : ClickableObject :
  MonoBehaviour`. Plants are BiomeObjects, so they have Contains pickups of their own (a
  `BOTTLE_TREE` holds 60 fiber) **and** fruit - both features apply to the same object.
- `BiomeObject.data` is a `BiomeObjectData` from a **static registry**
  (`BiomeObjectData.dicBobData_Codes`). Shared per type: `data.infinite = true` is not per
  instance.
- Per-instance pickup state is `startPickups` / `subtractedPickups`
  (`Dictionary<PickupType,int>`, internal).

## 1. Infinite piles, per instance
`BiomeObject.ExtractPickup` spawns a pickup of type `t` while `startPickups[t] - subtractedPickups[t]` is
above zero or `data.infinite` is set. Either way it then adds one to `subtractedPickups[t]` (even on an
infinite pile), sets `extractablePickupsChanged` and calls `SetSize()`.

Postfix it and reset `subtractedPickups[t] = 0`. Three things fall out:
1. per-instance, nothing leaks to other piles of the type;
2. the pile keeps its **full visual size**, because `SetSize()` is computed from
   `startPickups - subtractedPickups` (flipping `infinite` instead lets the mesh shrink to nothing
   while still producing);
3. it survives save/load with no custom serialisation, because `subtractedPickups` is what gets
   written - a marked pile is simply saved as untouched.

Marking an already-empty pile must zero the dictionary immediately, or `HasPickups()`/`CanExtract`
gate ants out and the postfix never runs.

**Free infinity glyph:** `BiomeObject.UpdateClickUi` already contains `ldstr "∞"` and writes it
into the Contains grid when `data.infinite` is set. Raise the flag in a **prefix**, let the game
render, restore it in a **`[HarmonyFinalizer]`** (runs even if the method throws). The UI is built
synchronously on the main thread, so nothing else observes it. No custom UI at all.

## 2. Fruit / energy-pod speed
`FruitPlant.UpdateGrowWilt(dt)` counts each spot's `growTime` down and spawns `data.fruit`, then
re-rolls from `GrowTimerRoll()`, which is just `Random.Range(growTimeRange.x, growTimeRange.y)`.
A postfix dividing `__result` by a per-instance multiplier is the whole mechanism. Rescale each
spot's in-flight `growTime` by `old/new` so a change is felt immediately.

**Do not display an interval computed from `growTimeRange`.** Other mods override the timer without
touching that field - with **ChangeGrowSpeed** installed a plant read 60s from the field while the
real roll was 5s. Sample `GrowTimerRoll()` instead (a pure `Random.Range`, so sampling is free of
side effects, and your own postfix is already inside it). Cache the sample per plant and re-sample
only when the multiplier changes; both mods postfix the same method and Harmony does not guarantee
ordering between unrelated plugins (unless one names the other in `[HarmonyAfter]`/`[HarmonyBefore]`).

`FindObjectsOfType<FruitPlant>()` returned **4841** components but only **1025** bore fruit: the
component also sits on fruitless plants (`WIRE_TREE_NO_FRUIT`) with a zero-length `fruitSpots`
array. Filter on `fruitSpots.Length > 0`.

## 3. Stockpile capacity, per instance

A stockpile has **two** limits, in different places, and both have to move or nothing happens.
`Stockpile.HasSpaceLeft` first compares the type's `data.storageCapacity` with `GetCollectedAmount`.
Only while there's room left does it fall through to the base `Storage.HasSpaceLeft`, which walks this
storage's own piles and sums `maxHeight - GetHeight()`.

1. **The soft cap** is `BuildingData.storageCapacity` - per type again, read by `HasSpaceLeft`,
   `CanInsert_Intake` and `CapacityInfo`. Raise it in a prefix and restore it in a
   `[HarmonyFinalizer]`, exactly like the infinity glyph. Use a **LIFO stack** of saved values
   rather than one field, because `CanInsert_Intake` calls on through to `HasSpaceLeft` and the
   patches nest. (HarmonyX's `__state` parameter does this for you: it's a local of each patched
   call, shared by the patch class's prefix and finalizer. Set the raised value from the vanilla
   number rather than multiplying whatever the field holds, or the nested prefix raises it twice.)
2. **The physical stacks** are `Pile.maxHeight`, and those really are per instance, so scale them
   directly. `Pile.Write` persists only the pickup list, never the heights, so the scaling lives
   for the session and never reaches the save.

Vanilla ships the two in parity - a `STOCKPILE2` has `storageCapacity` 160 and 25 piles whose
heights also sum to 160 - which is why raising one alone looks like it does nothing.

Re-apply the heights from `BuildingUpdate` rather than once at `Init`: `PileConfigurer` builds the
piles from the prefab, so a stockpile built later (or rebuilt) comes back at vanilla heights.

**The send mechanism needs no separate work.** "Send everything to another stockpile" is an assign
action (`Stockpile.Assign`) whose loop stops as soon as `target.CanInsert` fails, and
`Building.CanInsert` goes to `Stockpile.CanInsert_Intake`. So it passes through the same gate and
respects a boosted target automatically.

`Storage.GetSpaceInPiles` looks like it matters and does not: it caches a per-building-**code**
total in a static dictionary, and nothing calls it.

**Uninstall is safe even when over capacity.** `Pile.AddToPile` has no fullness check at all, and
`Storage.Init` replays every stored pickup through it, so a stockpile holding more than vanilla
allows loads over-full and simply drains. Nothing is lost and nothing throws.

## 4. The queen's hunger stages

`GlobalValues.standard.hungerTiers` is a list of 27 `HungerTier` rows:

```
name | ifBelow | larvaPerMinute | animationSpeed | maxPopulation | drain | color
```

and it decides nearly everything about colony growth. The player-facing meanings are not obvious
from the field names, and are worth writing down because a mod exposing them has to explain them:

- **`ifBelow`** is the stage's energy **ceiling**. `Hunger.GetTier(e)` returns the first row whose
  `ifBelow` exceeds the queen's energy.
- **`drain`** is energy lost **per second**: `Hunger.Process(dt)` counts a 1.0s timer down and
  subtracts `GetCurrentDrain()` once per tick. `GetCurrentDrain` interpolates linearly between the
  previous row's `drain` and this row's, by where the energy sits between the two `ifBelow` values -
  so the number in a row is what is reached at the **top** of that stage, not throughout it.
- **`maxPopulation`** is the HUD's "Max population".

**This is per world, not per queen.** `GameManager.allQueens` is a `List<Queen>` and
`GetQueenCount()` exists, which makes multiple queens look supported. They are not: the `QUEEN` row
of `prefabs.fods` has **`N BUILDS` = 1** and `NO DEMOLISH`, the tutorial sequence sets
`SET_PLACE_QUEEN_TRUE` once and completes on `N_QUEENS 1`, and gynes that fly out are only counted
(`Playthrough.gynesFlown`) - they never land as new queens.

`Hunger` is constructed per queen but assigns the static `Hunger.main = this` and takes the tier
list by **reference**: its `tiers` field is the `GlobalValues.standard.hungerTiers` list itself, not a
copy.

`GlobalValues.standard` outlives a world load, so capture the vanilla rows once per session and
rebuild every world's table from that baseline. Writing deltas on top of whatever is currently
there compounds across loads.

### The guard that makes edits look like no-ops

The obvious way to apply a change is `Hunger.EnergyChanged()`, and it is wrong. It looks up the
stage for the current energy with `GetTier`, calls `SetTier` only when that **index** differs from
`curTier`, and then calls `UpdateHungerUI`.

`SetTier` is the only thing that copies a row into `curLarvaRate` / `curMaxPopulation` /
`curDrain`. Editing the stage the queen is **already in** leaves the index unchanged, so nothing is
re-read and she keeps the old numbers until she happens to cross a boundary. Editing any *other*
stage appears to work, which makes it read as intermittent rather than broken. Call `SetTier`
unconditionally, asking `GetTier` first because an edited `ifBelow` can move her:

```csharp
int tier = GetTier(energy);
SetTier(tier);
EnergyChanged();      // for UpdateHungerUI
```

The community **AdvancedSettings** mod called `EnergyChanged` the same way and inherits the same
blind spot.

### Display the consumer's values, not the row

A readout built from the tier row will happily show the new number while the queen is still using
the old one - which is exactly the bug above, hidden. Read `Hunger.get_larvaRate()` and
`Hunger.get_maxPopulation()` instead, so the readout cannot disagree with behaviour.

### One setting silently stops the game's core loop

`Queen.BuildingUpdate` normally lays only while the colony is under the cap: it starts a new larva
(`larvaProductionStage = 1`) only when `GameManager.GetAntCount()` is below `hunger.maxPopulation`,
or when `FreeLarvae()` is true or `bonusLarva` is above zero.

So lowering `maxPopulation` below the current population - including by **resetting to defaults
after the colony has grown past them** - stops the queen completely, with nothing on screen to say
why. Any editor exposing this column should show the live ant count beside the cap and say so in
words; clamping the input is the wrong fix, because the value is legal.

A second effect compounds the confusion: ants live about three minutes, so a burst of larvae
creates a cohort that expires together. A sharp population drop some minutes after an experiment is
ordinary, and it recovers.

## An IMGUI window over a game that does its own input

A 27-row editable grid has no counterpart in the game's prefabs, so it is IMGUI - and IMGUI draws
over a Unity game without taking input from it.

1. `Screen.height` is the **render** resolution, so an unscaled window is unreadably small on a 4K
   display. Scale the whole GUI with `GUI.matrix` and work in scaled units.
2. The game's own mouse pass is `Gameplay.GameplayUpdate()`, called once from `GameManager.Update`.
   Prefix it to skip **while the cursor is inside the window rect** and the world stops hovering
   and reacting underneath. Scope it to the rect, not to "window is open", or the rest of the
   screen goes dead. The rect is in scaled GUI units while `Input.mousePosition` is render pixels
   with a bottom-left origin, so scale and flip before comparing.
3. The scroll wheel is read somewhere else entirely: `InputManager.InputUpdate` stores it into the
   static `InputManager.zoomDelta` and `CamController.CamUpdate` spends it. Zero `zoomDelta` in a
   postfix while blocking, or scrolling the table zooms the camera.
4. Side effect worth knowing: anything else riding on `GameplayUpdate` - the game's own click
   panels, hover tooltips, cursor changes - also pauses under the window.

## 5. Sandbox delete button in normal games
`DebugSettings.DeletableEverything()` returns true when the class's own `deletableEverything` flag,
`Player.cheatDeletableEverything` or `WorldSettings.sandbox` is set, and it gates the delete button on
`BiomeObject`, `Ant` and `Pickup` plus `Building.CanDemolish`.

Setting `Player.cheatDeletableEverything` is the obvious route and the wrong one:
`Player.CheatsToInt` / `FillCheatsFromInt` **serialise the cheat flags into the save**. Postfix the
method's return value instead and the whole thing stays runtime-only.

## UI injection notes (Microtopia specifics)
- Both piles and plants use `UIClickLayout_BiomeObject` (`UIClickType.BIOMEOBJECT`, or `_LARGE`
  for >4 pickups). `FruitPlant` **overrides** `SetClickUi`/`UpdateClickUi`, so patching only the
  `BiomeObject` versions misses plants unless the override calls base.
- The panel prefab has **zero checkbox slots**, so `SetCheckbox`/`UpdateCheckbox` are silent
  no-ops (both are bounds-safe - they fail invisibly rather than throwing).
- `UIClickLayout.SetButton(type, action, InputAction.None)` works, but the only slot present on
  this prefab is `Follow`, which renders its own icon and no text label - an eye icon that means
  nothing. `Generic1`/`Generic2` are not on this prefab.
- Cloning the panel's private `prefabExchangeType` (`UITextImageButton`) and calling
  `Init(text, onClick)` gives a control in the game's real font, but it lands in the "Collect from
  this with" column, which reads wrong.
- **Best result: make the existing blocks the controls.** Contains lives in `UIIconGrid`
  (`inventoryGrid`), fruit lives in slots (`UpdateSlots`, title `BIOME_FRUITS`, boxes in
  `spawnedSlotItems`, icons in `spawnedSlotItemIcons`).
- A `Button` on the container is **not enough**: the icon tiles handle their own pointer events
  (that is the "Scrap iron" / "Energy Pod" tooltip) and swallow the click. Attach a small
  `IPointerClickHandler` relay to each tile - Unity runs every handler on the GameObject, so the
  tooltip still works. For fruit slots, attach to **both** `spawnedSlotItems` and
  `spawnedSlotItemIcons`; the box alone does not receive it.
- Tiles are respawned as panels refresh, so re-attach from `UpdateClickUi`, guarded by
  `GetComponent` so components are not added twice.
- The slot label (`lbSlots`) is rewritten from its loc string every frame, so a suffix can be
  re-applied without accumulating - but it wraps past roughly 16 characters.

## Keying settings to a world
- **Do not** hook `Save.StartReading` / `StartWriting`. They also fire for blueprint files, the
  profile save (`main.psav`) and save-list previews, so browsing the load menu silently swaps
  state out.
- `GameManager.KStartLoadGame` / `KStartGame` / `SaveGame` are the real entry points; prefixing the
  coroutine *factory* is fine and runs before any `BiomeObject.Init`.
- Better still: key by **`WorldSettings.seed`** (static string). Settings then follow the world
  through autosaves, quicksaves and renamed saves with no hooks at all. Resolve it lazily - the
  seed is only correct after a save has been read.

## Build without a .NET SDK
Unity Mono games need no SDK: `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe` with
`-nostdlib+ -noconfig` and references into `Microtopia_Data/Managed` plus `BepInEx/core` is enough,
and it takes multiple source files in one call. That compiler only goes up to C# 5: no string
interpolation, `nameof`, `?.` or expression-bodied members.

For inspecting the assembly, **`Mono.Cecil.dll` already ships in `BepInEx/core`** - load it from
PowerShell (copy it locally and `Unblock-File` first, or `Add-Type` fails with 0x80131515) and you
can dump types, fields and IL, and scan every method body for callers of a member, without
installing Ghidra, ILSpy or dnSpy.

`HasPickups()`, `SetSize()`, `startPickups`, `subtractedPickups`, `fruitSpots`, `spawnedSlotItems`
and friends are `internal`, so they need `AccessTools` reflection even with a direct assembly
reference.

## Verification
Driving the real `BiomeObject.ExtractPickup` past capacity, unmarked pile as control:

| pile | capacity | attempted | extracted | subtracted after | HasPickups |
|------|---------:|----------:|----------:|-----------------:|------------|
| infinite | 32 | 47 | **47** | 0 | true |
| normal (control) | 46 | 61 | 46 | 46 | false |

Fruit speed, rolling the real generator 20x: base 5s (ChangeGrowSpeed active), 2.5s at 2x, 1.7s
at 3x.

Stockpile capacity, three stockpiles of one type in one world, read from the live objects:

| stockpile | multiplier | summed pile heights | holding |
|-----------|-----------:|--------------------:|--------:|
| control   | 1x | 160 | 160 (full) |
| B         | 3x | 480 | 160 |
| C         | 5x | 800 |  39 |

Sampling `data.storageCapacity` from outside the patched calls still read **160** on all three,
which is the check that matters: if the per-type value had leaked it would read the raised number.
Raising, lowering and sending between all three produced no errors over a session.

Hunger stages, read from the live `Hunger` object rather than from the row: editing the stage the
queen was **in** moved the HUD's "Max population" from 500 to 1234 and back immediately, with no
stage change - the case that silently did nothing before `SetTier` was called unconditionally.
Raising a cap above the colony size restarted larva production (44 -> 51 -> 60 ants), confirming
the queen had been gated rather than broken.

**Save compatibility** was checked by removing the DLL and loading a save created with the mod: it
loads clean and the pile reads its normal count again. Nothing mod-specific is written to the
`.sav`; settings live in `BepInEx/config/MicrotopiaTweaks/<seed>.txt`.

**Not verified:** anything outside v1.2.2; capacity on `StockpileLarge` / `StockpileColossal` (only
`STOCKPILE2` was driven); the `animationSpeed` and `color` columns of `HungerTier`, which the
editor deliberately leaves alone.

## Gotchas
1. **F9 is the game's quickload.** A diagnostic bound there fires your code *and* quickloads. F8
   is free.
2. `ClickableObject.linkId` is 0 for biome objects, so it is useless as an instance id; world
   position rounded to 0.1 works.
3. Unity's `Screen.width/height` is the **render** resolution (3840x2160 here) while the window
   client is 2560x1440 at 150% DPI. `Camera.main.WorldToScreenPoint` returns render pixels with a
   bottom-left origin; scale by client/render and flip Y before feeding `um win drive`.
4. `um win drive` re-focuses per invocation, which closes any open dropdown. Put open-then-select
   clicks in **one** `drive` call. It moves the real mouse, so ask the human first, and not while
   they're typing.
5. `um publish check` flags your own plugin DLL as "game file copied verbatim" once you have
   installed it into `BepInEx/plugins` - it compares against the game install. Lint a copy without
   the DLL to see the real result.
6. Two limits that ship equal look like one limit. A stockpile's soft cap and its summed pile
   heights are both 160 in vanilla, so a mod that raises only the cap appears to do nothing, and
   the symptom shows up somewhere unrelated - "sending between stockpiles only ever moves 160".
   Check for a second ceiling before concluding a number is being ignored.
7. A setter behind a guard is not a setter. `Hunger.EnergyChanged` only calls `SetTier` when the
   tier index changes, so editing the row the game is currently using does nothing until it
   happens to switch rows. Any tiered stat table is worth checking for this shape before
   concluding your write did not land.
8. A column that caps a live quantity can stop a core loop silently. Lowering `maxPopulation`
   below the current ant count - or resetting to defaults after growing past them - halts larva
   production with no feedback, and reads as a broken mod.
9. The community **AdvancedSettings** mod writes game values directly rather than patching:
   `ChangeStorageCapacity()` walks `GameManager.EStockpiles()` and assigns
   `s.data.storageCapacity` (per type) and each `Pile.maxHeight`. It only touches stockpiles that
   already exist, so one built afterwards keeps vanilla heights until it runs again. Its shipped
   `MaxHeight` is 20, which **is** the vanilla height, so out of the box it raises only the cap.

## Credits
- [BepInEx](https://github.com/BepInEx/BepInEx) 5 and [HarmonyX](https://github.com/BepInEx/HarmonyX), which
  ships with it as `0Harmony.dll`.
- The community mods compared above, both on Nexus Mods:
  [Advanced Settings](https://www.nexusmods.com/microtopia/mods/2) by Rianaid (it needs
  [CoreFramework](https://www.nexusmods.com/microtopia/mods/3)) and
  [ChangeGrowSpeed](https://www.nexusmods.com/microtopia/mods/4).
