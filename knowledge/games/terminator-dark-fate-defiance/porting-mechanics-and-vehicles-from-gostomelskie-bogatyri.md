---
kind: game
title: "Rebuilding mechanics of a sister engine branch as plugins: morale, stamina, towing, supply, vehicles"
game: "Terminator: Dark Fate - Defiance"
games_also: ["Gostomelskie bogatyri"]
game_version: "TDF 1.09.1223 (Steam) with DefianceLoader 1.9.0; Gostomelskie bogatyri build of 2026-09-10"
platform: windows
engine: unknown
route: reimplementation
tools: ["DefianceLoader 1.9.0", "MSVC (Visual Studio 2022)", "IDA", "Python 3", "Maya (mayapy)"]
anti_cheat: "none seen; single player only"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-31
links: ["https://github.com/DefianceLoader/DefianceLoader"]
tags: [frontedge, cats-who-play, sister-branch, morale, stamina, towing, trailers, supply, covers, skeletons, rtti-diff]
---

# Rebuilding mechanics of a sister engine branch as plugins: morale, stamina, towing, supply, vehicles

> Gostomelskie bogatyri («Гостомельские богатыри», GB here) and Terminator: Dark Fate - Defiance (TDF) are two branches
> of one engine. GB has morale, stamina, towing and more that TDF lacks. Swapping binaries is impossible, and machine code
> cannot be copied, so GB's `logic.dll` served as a specification and each mechanic was rewritten as a TDF plugin. GB's
> vehicles and buildings moved over as data. Morale, stamina, towing and supply ran in the real game. See the
> [TDF engine note](defianceloader-plugins-data-mods-and-engine-facts.md) first.

## Setup
- TDF as in the engine note. GB is a separate installed game, used read-only.
- Both databases in IDA, on copies of the DLLs. Decompiled output stayed private. This note describes logic in words.

## Route and why
`reimplementation` of one mechanic at a time, on top of `native-hook` plugins.
1. **Swap GB's binaries into TDF:** rejected. The branches diverged both ways: `logic.dll` has 1085 classes only in GB and
   664 only in TDF, and everything TDF-specific (global map, hunting, research) would go.
2. **Copy code:** impossible. Class layouts differ. An order object is 0x30 bytes with 19 slots in TDF, 0x1F8 with 23 slots
   in GB.
3. **Read GB, write it again on TDF's objects:** chosen. Each mechanic becomes one reverse-engineering project.

Scoping was cheap and worth doing first: an RTTI and facet-name diff of the two `logic.dll` files (621 facets in TDF, 739
in GB, 183 only in GB, 65 only in TDF) and a diff of table columns gave a feature table before any hook. Registration of
facets is the same in both, and source paths in the binaries (`code\trm\src\...`, `code\frontedge\src\...`) pair up
classes.

## How the game works (what we had to learn)

### Morale in GB
Compared line by line with GB when preparing the release. An early version that treated morale as a level with fixed
thresholds was wrong in several ways:
- **States are events.** Hits go into a queue, read every 0.1 s (`processingMoraleRequestsTimeout`). After an event starts,
  new ones are ignored for 5 s (`ignoreMoraleEventsTimeout`).
- **The band of remaining morale picks the state:** above 0.75 stunned (2 s, speed x1.5), above 0.5 suppressed (10 s), above
  0.2 pinned (15 s), otherwise panic (25 s). Panic hit again is escape (45 s). When time is up the squad is ready, at any
  morale. Nothing starts while inspired or sprinting.
- **Auras** sit around the commander (`SquadAuraFacet`). They are positive, absent when pinned, negative in panic or
  escape. Negative ones count x2 from a panicking squad and x3 from a fleeing one.
- **Recovery:** regeneration x1.5 out of combat, x the stamina multiplier, x the share alive, plus positive auras scaled by
  that share, minus negative ones. Bounds are 1 and the ceiling.
- **"In combat"** means 10 s (`stayBeforeHealTime`) after the squad's gunner last had a target, not 10 s after losing morale.
- Stamina had three values per preset level and matched GB from the start.

In TDF the squad update `sub_1804548C0` is reached by two callers: cell 10 of `SquadAiFacet`'s vtable (`0x744040`) and a
call in `sub_18044D7B0` at `+0x44D7C3`, which is the path for squads in combat. Hooking only one misses them (Gotcha 1).

### Towing
- The hitch is defined by lbox boxes: a tractor has `linktrailer*`, a trailer has `linktractor*`, and their `type` must
  match (`usual` hook or `saddle`). TDF vehicles have hooks and no eyes, so eyes were added to their lbox files.
- TDF already has `AiAttachTrailerOrder/State`, `AiDetachTrailerOrder/State` and `SetTrailer`. The order's slot 6
  (`sub_180096780`) is where GB's recovery check goes. `sub_18010CFD0` makes the order.
- Chassis slots: `setTrailer` is slot 67 (`sub_180135170`), `setTractor` is slot 74 (`sub_180134B60`), and slot 73
  (`sub_180134680`) picks the hook and eye pair: the first eye of the trailer with a matching hook type.
- GB's `AiTowVehicleState` on the towed vehicle silences its guns and refuses orders other than detach. TDF has no such
  state, so the plugin does it.
- **Heading of the towed vehicle:** TDF's follow mode (chassis slot 70, `sub_180131300`) sets the trailer's heading from
  its centre to the hook, which assumes the eye is at the front. GB's version (`sub_180158600`) multiplies by a sign,
  `+0x460`, set from the eye offset times the heading (`sub_1801565B0`), so a vehicle with its eye at the rear follows
  tail first.
- **Cursor:** the stock `SmartCursorCmdAttachTrailer` (`game.dll` vtable `0x53C9F0`) is reused. Slot 14 gives the picture
  (23 allowed, 24 refused, 25 no target), slot 15 the click, which calls logic interface slot 18. `sub_18036DF80` chooses
  on hover and `sub_18036E750` creates the cursor. X is the stock detach key, so no new buttons are needed.
- `recoveryvehicle` in `perks` marks the tractor. In GB no mission or shop offers a recovery vehicle to the player, so its
  in-game behaviour could not be watched there: only the code was the reference.

### Supply and repair
- `support` and `repair` rows make `SparesRechargerFacet` and `RepairerFacet`, and then no `AmmoRechargerFacet` is created
  (`sub_180520BD0`, `sub_180526340`). F4 turns on the first recharger facet, so a truck cannot have them all by data alone.
- The answer: keep `ammunition_recharge`, tag with unknown perks (`supply_spares`, `supply_repair`), and hook
  `AmmoRechargerFacet` (vtable `0x715908`; slot 10 update `sub_180120C20`, slot 17 `canRecharge` `sub_180120990`,
  zone targets in `sub_180120500`).
- Spare parts and module health are in `DamageableModulesFacet` (vtable `0x728188`). `incHealth` (`sub_180226420`) takes
  parts from the vehicle itself, so a plugin has to give them back.
- Relations: `sub_180546060` then slot 22 gives 0 own, 2 enemy, 4 neutral. An abandoned vehicle is neutral (4).

### Data differences
- GB's tables have `*_fmod` columns and `openHatch` that TDF lacks. GB has FMOD, and TDF has the older sound system.
- GB effects with `ParticleLight` and lbox boxes `light_source_*` have no counterpart in TDF: effects without it were
  rebuilt with TDF's `Luac.exe`, and the boxes dropped.
- GB covers are `pyramid` boxes with a `sector`. They become TDF `box` covers with `max_soldiers=1`.
- **Skeletons:** GB has two human skeletons, an old 28-node Biped with bones along +X and a new 49-bone one along +Y, with
  twist bones and weapon helpers. Animation binds to a model by bone name in local axes, so a soldier on the wrong
  skeleton collapses into a ball. GB's own rows do this for 62 models, apparently unused in its missions. Reskinning the
  old models on the new skeleton in Maya fixed it, checked in the game with engineers and assault squads.
- **Cover placement in GB** (useful numbers for a generator): 0.6 m from the obstacle, 1.8 m step, four points crosswise
  around trees. Posture by obstacle height: 0.9-2 m standing, otherwise crouching. A quaternion in the map is `w x y z`,
  and points face their obstacle.

## Build steps
1. Diff RTTI, facets and table columns of the two binaries and pick a mechanic.
2. Decompile the GB classes involved and write the logic down in your own words, with timers and thresholds from tables.
3. Find the same-named TDF classes, or the nearest hook (update functions, vtable cells, order execution).
4. Write the plugin with its numbers read from tables through the game's table store, not from disk.
5. Put new rows in `.patch.xml` patches and new boxes in `.patch.lbox` patches (engine note).
6. Compare with GB once more before a release. Then test in a scenario with a real fight, not an empty map.

## Verification
- **Towing:** scenario on a test map with tractors, targets and enemies. The log shows `goes for`, `takes ... in tow:
  hitched`, `takes a path`. A `trace` setting prints the trailer physics once a second, which caught the heading bug
  below: after the fix the towed vehicle's heading stays opposite the tractor's on the move. Detaching with X and a
  point worked, and the released vehicle drove off under its own orders.
- **Morale and stamina:** log lines and the squad panel in real battles, with a side-by-side reading of GB's functions.
- **Supply:** vehicles repaired in the zone, abandoned ones as well, relation 4 read from the log.
- **Not verified:** the `SupportVehicles` release bundle, which merges towing and supply into one plugin and adds a data
  mod, has never been run. The earlier separate plugins were. Drones from GB were studied and are not covered here.
- **Not comparable:** towing against GB in play, since GB gives the player no recovery vehicle.

## Gotchas
1. **First run of the morale plugin: no squad lines in the log.** **Cause:** one vtable cell is not enough, because squads
   in combat are updated through the direct call. **Fix:** hook both callers.
2. **Towing: hitched, then both vehicles stood still, on one run.** **Cause not found:** the next runs drove. The `trace`
   added to chase it did show that `sub_18012F530` (chassis slot 41) refuses the tractor a path until the trailer's `+1089`
   is 0. Add a trace like this before the first test, not after.
3. **The towed tank swings round nose to the hook in the first second of the move.** **Cause:** it hitches tail to tail,
   and TDF's follow mode assumes the eye is at the front (see Heading above). **Fix:** at the hitch, note that the
   trailer's `usual` eye lies behind its centre, then hook chassis slots 70 and 79 (`sub_180131D10`, which applies the
   heading) and flip the heading while that trailer's physics runs. Save and restore around nested physics.
4. **A recovery vehicle has to drive round a wreck to reach its rear eye.** GB has one eye at the rear of each vehicle.
   **Fix (ours, not GB's):** a second eye `linktractor02` at the front and the nearest end picked. Put it after the rear
   eye, so stock tractors still pick the first.
5. **Eyes must be on every vehicle.** Only 18 GB rows had an eye and no TDF vehicle did. **Fix:** a script that places eyes
   by the hull's real bounds: at the rear of the hull, 0.7 m above the bottom, or at the hook if it is not buried.
6. **Trucks lose ammunition supply when given `repair`.** See Supply above. **Fix:** tag with perks and hook.
7. **A flag column vanishes in a port.** A rule "drop effects that exist in neither game" also caught `is_special_hit_effect`,
   a yes/no flag. **Fix:** type columns by name before a generic rule, and review what a rule removes.
8. **Soldiers "crumpled" into a ball.** See Skeletons. A wrong table of animations gives no error at all.
9. **Plugin was right against its own memory of GB, not against GB.** The first morale plugin looked fine in play and
   disagreed with GB on states, auras and the meaning of "in combat". **Fix:** before a release, go through the functions
   again one by one, and write down each difference.

## Assets
The vehicles' models and textures come from GB and are not in this repository. A public mod built this way must credit
GB and have the right to use them.

## Cost and time
About three weeks of sessions together with the sibling notes. Each mechanic took several hours to a night.

## Open questions
- GB's drones, new cover system and dynamic lights were studied. Native versions in TDF would need new facets.
- Whether `defiance.support-vehicles` behaves like its two parents in the game.
