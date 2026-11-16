---
kind: game
title: "Extending a Minecraft 26.3 Forge terraforming tool to 222 modes: a full-screen mode browser, lasting zones saved with the world, exact undo for animated and timed modes"
game: Minecraft
games_also: []
game_version: "Minecraft Java 26.3, Forge 66.1.5 (ForgeGradle 7, Java 25)"
platform: windows
engine: java
route: loader-api
tools: ["Forge 66.1.5", "ForgeGradle 7", "decompiled 26.3 sources for API checks (kept out of the repo)", "scripted dev clients", "a dev dedicated server"]
anti_cheat: "none (single player and a dev dedicated server the user runs)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: '2026-11-16'
links: []
tags: [terraforming, undo, world-editing, saved-data, zones, gui, self-test, dedicated-server, forge]
---
# Extending a Minecraft 26.3 Forge terraforming tool to 222 modes

> A third round on a Forge mod's World Warper item (see the notes on 84 and 150 modes): 72 more modes (222 plus a Custom
> mode), two new categories, a full-screen mode browser next to the radial menu, and "lasting zones" (an aurora, a low
> gravity area, cloud layers, crusts and traps that give way) saved with the world. Every mode is still a plan writing
> through a recording sink, so previews and undo come for free; the hard parts were the modes that act *after* the warp
> (animations, falling things, traps) and keeping undo exact. Checked in the real game: each mode applied and undone by
> a self-test, with and without two other mods, and on a dedicated server.

## Setup
- Minecraft Java 26.3, Forge 66.1.5, ForgeGradle 7, JDK 25. No mixins.
- Dev runs only: `runClient` with a scenario script (a mod-side `DevScenario` reads commands: new world, wait, shot,
  `cmd`, Warper actions), `runServer` for the dedicated checks. The user's own launcher instance and saves are untouched
  (saves backed up anyway).

## Route and why
Loader API plus the mod's own plan / sink design, extended rather than changed: a new sink method for zones, a "not
undoable" flag on plans, an optional "before start" step on the shared disaster-event plan, and a "sight only" flag on an
existing falling-rock entity. Existing modes were re-tested unchanged.

## How the game works (what we had to learn)
- **Leaves remember their distance to a log.** Removing logs (termites, a castle clearing its footprint, a hail storm
  breaking leaves) changes the `distance` property of leaves up to 6 blocks away through neighbour updates. Undo only knows
  the blocks it wrote, so those leaves stay "wrong". Fix: before removing a log or leaves block, snapshot the leaves around
  it into the undo record (the record keeps the first "before" state of each position). 70 differing leaves became 0.
- **Gravel and sand fall where nothing holds them.** A river bed or a cave lining laid over open air (the edge of a
  floating test platform; a cave in a real world) falls after the warp and is left behind by undo. Place gravel or sand only
  where the block below is solid; else stone or clay.
- **Respawn points in other dimensions.** `ServerPlayer.setRespawnPosition(new RespawnConfig(RespawnData.of(dim, pos, yaw,
  pitch), forced=true), false)` works like `/spawnpoint`. If that spot is later blocked, vanilla *clears* the respawn
  config before `PlayerRespawnEvent` fires and puts the player at the world spawn (another dimension). A fallback that reads
  the config in the respawn event sees nothing; keep your own copy in the player's persisted data
  (`getPersistentData()` under `ServerPlayer.PERSISTED_NBT_TAG`, which Forge copies across death) and move the player there.
- **26.3 API details:** dyed and copper blocks are not `Blocks` fields (`Blocks.WHITE_CONCRETE`, `COPPER_BLOCK`,
  `LIGHTNING_ROD`, `CHAIN` don't exist; copper blocks are a `WeatheringCopperCollection`, the chain is `IRON_CHAIN`); resolve
  them by id. `PushReaction` has `PUSH_PULL`, not `NORMAL`. `Entity.hurtMarked` is gone; set `needsSync = true` after
  changing a player's velocity. `Player.drop(stack, bool)` now needs a `Prediction`; spawn an `ItemEntity` instead.
  `BlockPos.getCenter()` doesn't exist; `Vec3.atCenterOf(pos)`. A skin's address is in the profile's `textures` property
  (`GameProfile.properties().get("textures")`, base64 JSON); offline / dev profiles have none.

## Build steps
1. **Lasting zones as saved data.** One `SavedData` (`SavedDataType` with a `CompoundTag` codec, as the mod's other saved
   data) holds zones: kind, dimension, box, owner, expiry, parameters and a cell list. A server tick handler acts on each
   zone whose centre chunk is loaded (no chunk loading). Kinds: an aurora (dust particle curtains, `force` so they show far
   away), low gravity (jump boost + slow falling refreshed every 5 ticks: no client code needed, and no fall damage), cloud
   layer (its blocks; removing the zone clears them), lava crust and pitfall (blocks that crack / fall when an entity stands
   on them), acid pool (damage), an ice path that melts back at expiry, turning windmill sails (block displays moved round a
   hub) and a replay recording.
2. **Undo removes a zone.** Zone ids are negative and go into the same list in the undo record as timed effects; undo
   stops effects with positive ids and removes zones with negative ones (without clearing their blocks: the record puts
   those back).
3. **Effects after the warp, done inside the warp.** Falling meteors and stars reuse an existing falling-rock entity as a
   sight only (a new flag makes it just vanish on landing); the warp plan itself waits until each lands and writes its
   crater through the sink, so undo is exact. Spin and Reassemble do the same: show the blocks as displays, animate them for
   a few seconds inside the plan's steps, then write the result. Termites, rust and acid eat at a paced rate inside the plan.
4. **Not undoable on purpose.** Harvest puts produce in the player's inventory; undoing it would regrow the crops for
   another harvest. A plan flag keeps such a warp out of the history (and Custom chains only allow it as their only step).
5. **A full-screen browser beside the radial menu.** At 222 modes a radial ring needs paging; a card grid with search and
   tag filters (destructive, building, cosmetic, zone, operator-only, new, favourites) finds things faster. Both write the
   same item data, so favourites, "new" badges and recent modes stay in step.
6. **Client-only ghosts.** Replay and Compare send one player a list of (position, block state, colour) and the client draws
   translucent faces through the existing preview renderer; nothing is placed in the world.

## Verification
- `/warper selftest` (from the earlier notes): builds a fixed scene, applies a mode, counts changed blocks, mobs, effects
  and zones, undoes, compares. New modes get their extras (a river, a field, animals, metal blocks, a checkpoint to compare)
  built before the baseline, so the old modes' tests don't change.
- **72 new modes:** first run 61 pass; the 11 failures were 9 test-setup problems (durations shorter than the settle time,
  targets with nothing to act on) and 2 real leaf-distance leftovers (fixed as above). Then 72 / 72.
- **All 222 + Custom, no other mods:** 217 pass, 6 known limits (water or falling blocks the game moves: the same 6 as before
  the update), 0 fail. Highest server tick during a mode: 11.3 ms.
- **With a TNT mod and an add-on loaded:** the same plus one known limit; two new modes failed (falling gravel), fixed,
  re-run: pass. The 72 new modes as one-step Custom chains: pass.
- **Dedicated server:** 19 / 19 as an operator; a protected area left alone (4 chunks); op-only modes refused for a
  non-operator, others allowed; zones, history, checkpoints and presets survive a restart; undo after the restart works.
- **Respawn fix:** dying in the universe crossed to respawns there; with the respawn spot walled in, the fallback moves the
  player to safe ground in that universe (log line), not back to the first world.

## Gotchas
1. Leaves' `distance` (above): snapshot leaves around any log or leaves you remove, or undo leaves them wrong.
2. Gravel / sand over air falls after the warp; check support before placing them.
3. A self-test that counts "changes" after a settle delay misses timed things that already ended: give timed modes a test
   duration longer than the settle time, or lasting ones.
4. A dev scenario `join` right after the client starts can beat the dedicated server's startup; the connection is refused
   and not retried. Wait (here 2 minutes) before joining.
5. A "wait until the server-side self-test is done" command can't see a test on a remote server (noted before, repeated
   here): without a fixed wait the scenario's own actions run on top of the test and spoil it.
6. In a scenario script, a generic client command can swallow a screen-specific one with the same word (`settings`); give
   screen hooks their own names.
7. Iterating a list that the same loop rebuilds (`layout()` inside a loop over the cards) throws
   `ConcurrentModificationException`; iterate a copy.
8. PowerShell has a built-in alias `R` (Invoke-History): a helper function named `R` silently never runs.
9. Vanilla clears a blocked forced respawn point before `PlayerRespawnEvent`; keep your own copy in persisted data.

## Assets
Two block textures (a cloud and a starry rock) drawn by a small script; no third-party art.

## Cost and time
One long working session for 72 modes, the browser, zones and the tests. Full test runs take about 21 minutes for all 223
cases (about 5.5 s per mode) plus about 7 minutes for the new modes as Custom chains.

## Open questions
- Redo puts back a warp's blocks but not its zone or effect; worth recording zone parameters for redo.
- Whether the aurora should use a real client renderer instead of particles for very large radii.
