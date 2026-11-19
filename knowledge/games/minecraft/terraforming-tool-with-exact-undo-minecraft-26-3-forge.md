---
kind: game
title: "A terraforming tool grown to 283 modes in Minecraft 26.3 Forge: exact undo for entities, effects, zones and animations, safe file input, regeneration from the seed, contained destructive modes"
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
links: ["https://github.com/MinecraftForge/MinecraftForge"]
tags: [terraforming, undo, world-editing, file-input, regeneration, saved-data, zones, gui, destruction, containment, interactions, self-test, dedicated-server, forge]
---
# A terraforming tool grown to 283 modes in Minecraft 26.3 Forge

> A Forge mod's World Warper item grew from 84 to 283 terrain, building, fluid, physics, ecology, utility, zone and
> destructive modes, plus a Custom mode that chains them, in three rounds. 150 modes: entity and effect undo, safe file
> input, regeneration from the seed. 222: two new categories, a full-screen mode browser, lasting zones saved with the
> world, exact undo for animated and timed modes. 283: 61 destructive modes in 11 subcategories, server-side
> containment of spreading modes, cross-mode interactions, real-time pacing. It uses no mixins: every mode is a plan
> that reads and writes through a recording "sink", which gives previews and undo for free. The hard parts were what
> happens *after* a write (leaves, falling blocks, flowing water, and modes that act after the warp: animations,
> falling things, traps) and keeping undo exact. It runs in the real game. Each mode is applied and undone in a fixed
> scene by a self-test, with block-by-block comparison, in single player (with and without two other mods) and on a
> dedicated server. The same mod's runtime dimensions, portals and world endings are in the
> [runtime dimensions note](runtime-dimensions-parallel-universe-portals-and-whole-dimen.md).

## Setup
- Minecraft Java 26.3, Forge 66.1.5, ForgeGradle 7, JDK 25, Windows 11. No mixins.
- Mojang names (26.3 uses `Identifier`). 26.x ships unobfuscated, so these are the names in the jar itself.
- Every API was checked against decompiled 26.3 sources kept outside the repository.
- Dev runs only. `runClient` with a scenario script (a mod-side `DevScenario` reads commands: `newworld`, wait,
  `shot`, `cmd`, Warper actions, a wait-for-self-test command), and `runServer` for a dev dedicated server with RCON.
  The user's own launcher instance and saves are untouched (backed up first anyway).
- Keep that server on this PC: an RCON password, and `server-ip=127.0.0.1` in `server.properties`. RCON listens on the
  same address as the game, which is every interface when `server-ip` is empty.
- **Multiplayer:** the mod does its work on the server, so it only runs where it's installed: single player, or a
  server you run, with players who agreed to it. Destructive modes hurt players and wreck builds in range, outside
  protected areas.

## Route and why
- **Loader API only.** Every write is a server-side `setBlock` through one sink. The sink checks protection, the
  mask and immune blocks, records undo data, and runs a little per tick. No mixins were needed.
- **Each round extended the plan / sink design rather than changing it**, and re-tested the existing modes unchanged
  (the same pass / known-limit list as before):
  - for 222 modes: a new sink method for zones, a "not undoable" flag on plans, an optional "before start" step on the
    shared disaster-event plan, and a "sight only" flag on an existing falling-rock entity;
  - for 283 modes: a `spreading()` and a `paced()` flag on plans, a hook in the recording sink for interactions, an
    in-memory store of block "conditions" (cracked, weakened) with expiry, and zone kinds for persistent objects.
- **Regeneration** reuses the mod's runtime-dimension code (the runtime dimensions note) rather than touching real
  chunks. See "How the game works".

## How the game works (what we had to learn)
### Undo has to cover more than your own writes
- **Entities and effects.**
  - Record spawned entities as NBT, and remove them on undo by UUID.
  - Record removed entities as NBT, and load them back on undo with `EntityType.loadEntityRecursive`.
  - Timed server effects (rain clouds, fog, whirlpool pull, glowing ore markers made of `block_display` entities with
    `Glowing` and `glow_color_override`) get ids; undo stops them.
- **Neighbour updates reshape blocks after placement** (fences, doors, leaves). Re-read the "after" states when a
  warp ends, or later undos warn "changed since".
- **What the game breaks next.** Removing a block also removes what depended on it: snow layers, plants, torches
  (broken by neighbour updates, not by your writes). Undo only knows your writes. Before removing a block, snapshot
  the attached neighbours (up and the four sides, non-full-cube) into the record.
- **Leaves remember their distance to a log.** Removing logs (termites, a castle clearing its footprint, a hail storm
  breaking leaves) changes the `distance` property of leaves up to 6 blocks away through neighbour updates, and so do
  new trees placed next to old ones. Undo only knows the blocks it wrote, so those leaves stay "wrong". Fix: before
  removing a log or leaves block, snapshot the leaves around it into the undo record (the record keeps the first
  "before" state of each position); 70 differing leaves became 0. Keep new trees about 5 blocks from existing logs and
  leaves.
- **Gravel and sand fall where nothing holds them.** A river bed or a cave lining laid over open air (the edge of a
  floating test platform; a cave in a real world) falls after the warp and is left behind by undo. Place gravel or
  sand only on something that stays solid (decide end states first, bottom up); else stone or clay.
- **Fluids keep going.**
  - Water you place flows up to 7 blocks (more down slopes) and forms new sources next to existing water.
  - Before placing fluid, snapshot its horizontal and downward neighbours. When undoing a record that touched fluids,
    breadth-first remove *non-source* fluid next to the changed positions (cap: 200k blocks).
  - For a flood: snapshot the band the water can reach before placing any, drain the whole band at the end, and keep
    fluid placement 8 blocks inside any radius cap so the flow stays inside it.
- **Disaster events finish after the warp.** A warp that starts a small disaster (acid rain, a tremor) returns at
  once; a test that counts changes 2 s later sees nothing. Wait out the event's duration.

### Timing
- **A job's `step()` can run many times per server tick.** The job runner hands a plan its block budget in 256-block
  slices, calling `step` once per slice. Plans that count *ticks* (a 15 s swarm, a swing, a wait between blasts) ran
  ~16x fast: a 15 s Locust Swarm ended in 19 ticks. Fix: a `paced()` plan gets one `step` per game tick with the whole
  budget. Older animated modes have the same effect; they were left as they were.

### Regeneration, structures and files
- **Regenerating from the seed: use a scratch dimension.**
  - A runtime dimension built with the overworld's own `ChunkGenerator` and seed generates the same terrain.
  - `getChunk(x, z)` on it, one chunk per tick. Then copy states, block-entity NBT (`saveWithFullMetadata`) and
    4x4x4 biome cells through the normal undoable sink.
  - Measured cost: about 170 ms per chunk the first time; 4 chunks in 679 ms.
- **Vanilla structure files.**
  - Write `size`, `palette`, `blocks` (with `pos`, `state` and `nbt`) and `DataVersion`.
  - When reading, run older files through `DataFixTypes.STRUCTURE.updateToCurrentVersion`.
- **Image input safety:** `ImageReader.getWidth(0)` / `getHeight(0)` read the header only. Check the dimensions
  before `read(0)`, so a tiny PNG claiming 100000 x 100000 pixels is refused without allocating anything.

### Mobs and the 26.3 API
- **Mob spawns are an environment attribute in 26.3**, not `Biome.getMobSettings()`. For biome-suited animals, read
  `level.environmentAttributes().getValue(EnvironmentAttributes.NATURAL_MOB_SPAWNS, pos).getMobsToSpawn(MobCategory.CREATURE)`
  and pick from the weighted list. Water categories give fish and squid.
- **26.3 API details:**
  - Dyed and copper blocks are collections, not one `Blocks` field per block. `Blocks.WHITE_CONCRETE` doesn't exist:
    `Blocks.CONCRETE` is a `ColorCollection` (`.white()`, or `.pick(DyeColor)`), and light blue stained glass is
    `Blocks.STAINED_GLASS.lightBlue()`. `Blocks.COPPER_BLOCK` and `LIGHTNING_ROD` are `WeatheringCopperCollection`s
    (`.weathering().unaffected()` is plain copper). `Blocks.CHAIN` is now `IRON_CHAIN`. Resolving them by id works
    too.
  - `PushReaction` has `PUSH_PULL`, not `NORMAL`.
  - `Entity.hurtMarked` is gone; set `needsSync = true` after changing a player's velocity.
  - `Player.drop(stack, bool)` now needs a `Prediction`; spawn an `ItemEntity` instead.
  - `BlockPos.getCenter()` doesn't exist; use `Vec3.atCenterOf(pos)`.
  - `ParticleTypes.FLASH` takes a `ColorParticleOption` (`ColorParticleOption.create(FLASH, argb)`).
  - `AreaEffectCloud(level, x, y, z)` with `setRadius`, `setDuration`, `setWaitTime`, `setRadiusPerTick`, `addEffect`
    (`MobEffects.POISON` is a `Holder`).
  - A skin's address is in the profile's `textures` property (`GameProfile.properties().get("textures")`, base64
    JSON); offline / dev profiles have none.
- **The mod's TNT-compat "volatile" tag** lists only the TNT mod's blocks, so chain reactions can't be tested without
  that mod.

## Build steps
### Plans and the sink
1. Every mode returns a plan (`estimate`, `step(sink, budget)`, `progress`, `bounds`).
   - Plans read and write only through the sink, and keep side effects behind `!sink.preview()`.
   - The client runs the same plan against a recording sink, which gives the preview.
2. Sink additions for entities and effects: `spawn`, `removeEntity`, `effect`.
   - The undo record stores spawned and removed entity NBT and effect ids.
3. File modes resolve names only inside one folder (`<game dir>/<mod>/<feature>/`):
   - Allow a plain-name regex (letters, digits, space and `_ - .`, at most 64 characters) with no `..`.
   - Refuse names ending in a dot or space, and Windows device names (`CON`, `NUL`, `COM1`, and so on, even with an
     extension).
   - Require the normalised path's parent to be the folder, and refuse links that point out of it.
   - Check sizes before parsing: 8 MB for images, 16 MB for NBT.
4. Custom chains can run any mode as a step: make a new context with that mode and the player's saved settings for
   it, and use the step's size as the radius-like setting.
   - Probe each step's plan up front. Plans that restore themselves, snapshot an area or start events are allowed
     only as a single step, and so are plans that aren't undoable (step 9).
5. Bump the network protocol when the set of mode ids changes.

### Zones and effects that outlast the warp
6. **Lasting zones as saved data.** One `SavedData` (`SavedDataType` with a `CompoundTag` codec, as the mod's other
   saved data) holds zones: kind, dimension, box, owner, expiry, parameters and a cell list. A server tick handler acts
   on each zone whose centre chunk is loaded (no chunk loading). Kinds: an aurora (dust particle curtains, `force` so
   they show far away), low gravity (jump boost + slow falling refreshed every 5 ticks: no client code needed, and no
   fall damage), cloud layer (its blocks; removing the zone clears them), lava crust and pitfall (blocks that crack /
   fall when an entity stands on them), acid pool (damage), an ice path that melts back at expiry, turning windmill
   sails (block displays moved round a hub) and a replay recording.
7. **Undo removes a zone.** Zone ids are negative and go into the same list in the undo record as timed effects; undo
   stops effects with positive ids and removes zones with negative ones (without clearing their blocks: the record
   puts those back).
8. **Effects after the warp, done inside the warp.** Falling meteors and stars reuse an existing falling-rock entity
   as a sight only (a new flag makes it just vanish on landing); the warp plan itself waits until each lands and
   writes its crater through the sink, so undo is exact. Spin and Reassemble do the same: show the blocks as
   displays, animate them for a few seconds inside the plan's steps, then write the result (animations from before
   the `paced()` flag run faster than their seconds setting: see "Timing"). Termites, rust and acid eat at a paced
   rate inside the plan.
9. **Not undoable on purpose.** Harvest puts produce in the player's inventory; undoing it would regrow the crops for
   another harvest. A plan flag keeps such a warp out of the history (and Custom chains only allow it as their only
   step).
10. **Client-only ghosts.** Replay and Compare send one player a list of (position, block state, colour) and the
    client draws translucent faces through the existing preview renderer; nothing is placed in the world.

### The menu
11. **A full-screen browser beside the radial menu.** At 222 modes a radial ring needs paging; a card grid with search
    and tag filters (destructive, building, cosmetic, zone, operator-only, new, favourites) finds things faster. Both
    write the same item data, so favourites, "new" badges and recent modes stay in step.
12. **Subcategories as data, not new categories.** The 11 destructive subcategories (explosive, thermal, cryogenic,
    kinetic, corrosive, energy, gravitational, sonic, natural forces, biological, exotic) are an enum (name, colour,
    icon, damage type id) and a map of mode id to subcategory; the browser groups Destruction under headings, and the
    radial menu shows a ring of 11 subcategory tiles first. Existing modes got tags only.

### Destructive modes
13. **Containment in the sink, not the modes.** For a plan marked spreading (a firestorm, a blight, a locust swarm),
    the job refuses writes farther than the cap from where it started, stops after a block cap and ends at a lifetime
    cap, whatever the mode's own settings say. `/jod stopall` ends spreading jobs (what they did stays undoable) and
    disarms persistent zones.
14. **Persistent objects are zones.** Mines, remote charges and a coil are saved zones (listed, removable, capped per
    player, undone with their warp). Their later detonations write through a per-zone record so undo can still
    restore.
15. **Hold to fire.** Two modes fire while right-click is held. The client sends a small "hold" packet every 2 ticks
    while use is held; the server warp keeps going while they arrive (an 8-tick gap = released), draining charge per
    second.
16. **Interactions in one place.** Seven switchable interactions let modes act on what other modes left (cracked,
    frozen, corroded, wet). The sink calls a hook after a write by one of the mod's 1.17 modes (the destructive ones):
    frozen neighbours shatter (kinetic, sonic, explosive), weakened neighbours give way (anything but corrosive), heat
    melts sand to glass and ice to water (thermal). One layer, never chained (a re-entry flag). Marks (cracked,
    weakened) live in memory with an expiry and a cap, so nothing is saved and stale marks vanish. Each interaction is
    a config switch.
17. **Damage types per subcategory** as data (`damage_type/*.json`, death messages in the lang file, explosive in
    `is_explosion`, thermal in `is_fire`).

## Verification
- **The self-test** (`/warper selftest`) builds a fixed scene, applies a mode, then counts changed blocks, mobs,
  running effects and zones. It then undoes the warp and compares every block, biome cell and entity count with the
  baseline. New modes get their extras (a river, a field, animals, metal blocks, a checkpoint to compare) built before
  the baseline, so the old modes' tests don't change.
- **150 modes:**
  - All 150 plus Custom, no other mods: 140 pass and 7 within known limits (falling-block or water leftovers). The 4
    failures were 3 test artefacts and 1 real issue; all fixed and passing on re-run.
  - With two other mods loaded (a TNT mod and an add-on): 145 pass, 6 within limits, 0 fail.
  - The 67 new modes as one-step Custom chains: 66 pass, 1 within limits.
  - File safety: 58 cases pass.
- **222 modes:**
  - The 72 new modes: first run 61 pass; the 11 failures were 9 test-setup problems (durations shorter than the
    settle time, targets with nothing to act on) and 2 real leaf-distance leftovers (fixed as above). Then 72 / 72.
  - All 222 + Custom, no other mods: 217 pass, 6 known limits (water or falling blocks the game moves: the same 6 as
    before the update), 0 fail.
  - With a TNT mod and an add-on loaded: the same plus one known limit; two new modes failed (falling gravel), fixed,
    re-run: pass. The 72 new modes as one-step Custom chains: pass.
- **283 modes:**
  - The 61 destructive modes: first full run 53 / 61; 8 fixed (falling gravel, leaves, flood water, snow layers, a
    crash on a null block, a plan that never advanced); then 61 / 61, and again after pacing.
  - All 283 + Custom: 277 pass + the same 6 known limits as before + one night-time refusal (the half-hour test let
    the clock run; now stopped at noon): no regression in the old modes.
  - Containment test: 12 spreading modes at radius 40 / 120 s against caps of radius 6 / 3 s / 300 blocks: every one
    stopped at 60 ticks, farthest change 6.4 blocks, undo exact.
  - Interactions (scenario): each of six pairs changed what it should (e.g. resonance shattered all 149 cracked
    bricks) and undoing all nine warps restored the counts exactly.
  - Custom chains: the 61 as one-step Custom warps 61 / 61; a two-step chain of new modes applied and undone exactly.
- **Dedicated server (scripted client):**
  - At 150 modes: 23 of 23 modes pass; a protected area is left alone; creative-only and op-only refusals work;
    history, undo and checkpoints survive a server restart.
  - At 222 modes: 19 / 19 as an operator; a protected area left alone (4 chunks); op-only modes refused for a
    non-operator, others allowed; zones, history, checkpoints and presets survive a restart; undo after the restart
    works.
  - At 283 modes, with a TNT mod and an add-on loaded: op / non-op, a protected area, and mines and charges surviving
    a restart were checked; the results are in the project's own status file and aren't written up here.
- **Server tick while a warp runs:** 1–8 ms at 150 modes; at most 11.3 ms at 222; 2.6 ms average and 10 ms worst for
  the destructive modes.
- **Not verified:** other operating systems (every run was on Windows 11), and the destructive round's
  dedicated-server results beyond the list above.

## Gotchas
1. A loop that steps by a setting (`x += spacing`) hangs the server thread when the setting is 0. Clamp the step to
   at least 1 even if the UI never allows 0, because a test harness or a hand-edited preset can.
2. Self-tests that compare the world before and after undo must ignore wanderers: bees from natural nests and bats
   from caves. They must also take the baseline *after* any per-test setup.
3. Painting a biome that is already there counts as "no change". Pick a test biome that no test world has.
4. Leaves' `distance` ("How the game works"): snapshot the leaves around any log or leaves you remove, and keep new
   trees about 5 blocks from existing logs and leaves, or undo leaves them wrong.
5. Snapshot attached neighbours (snow, plants, torches) before removing their support, or undo leaves them gone.
6. Gravel / sand over air falls after the warp; check support before placing them.
7. Water you place keeps flowing after the warp and outside any cap: snapshot first, drain everything, keep it inside.
8. Tick-counting plans and a job that steps per budget slice: pace them per game tick or they run many times too
   fast.
9. A returned `false` inside a `for` loop skips the loop's increment: a plan that never advances and never ends. Give
   self-tests a per-mode timeout so one stuck mode doesn't hang the run.
10. A self-test that counts "changes" after a settle delay misses timed things that already ended: give timed modes a
    test duration longer than the settle time, or lasting ones.
11. A long self-test in a world with a running clock reaches night; day-only modes then refuse. Stop the clock (the
    `advance_time` game rule in 26.3).
12. A random-tick world turns covered grass to dirt during a test; turn random ticks off when counting blocks
    (`random_tick_speed` 0).
13. Two `gradlew --no-daemon` runs in one project (`runServer`, then `runClient`) can block the second run until the
    first ends. Start the client first, make it wait at the title screen, then start the server.
14. A "wait until the server-side test is done" scenario command can't see a test running on a remote server. Use a
    fixed wait there, or the scenario's own actions run on top of the test and spoil it.
15. A dev scenario `join` right after the client starts can beat the dedicated server's startup; the connection is
    refused and not retried. Wait (here 2 minutes) before joining.
16. In a scripted screenshot run, a dev `fly on` did not keep the player up after `/tp`; the player fell 180 blocks
    in seconds. Stand the camera on an invisible barrier block instead.
17. A screenshot taken in the same tick as hiding the HUD still shows the HUD; wait a few ticks.
18. In a scenario script, a generic client command can swallow a screen-specific one with the same word
    (`settings`); give screen hooks their own names.
19. Scenario `fill` commands over 32,768 blocks fail silently in the log; split them, or sand placed above air falls
    away. The cap is the `max_block_modifications` game rule (32768 by default in 26.3), so raising it in the test
    world also works.
20. A dev client idling on the title screen invites a click from whoever is at the PC. Warn them beforehand.
21. Iterating a list that the same loop rebuilds (`layout()` inside a loop over the cards) throws
    `ConcurrentModificationException`; iterate a copy.
22. PowerShell has a built-in alias `R` (Invoke-History): a helper function named `R` silently never runs.
23. Bash heredocs passed through a tool wrapper can break on quotes in the payload; write patch scripts to a file.
24. Windows needs a privilege to create symlinks, so a "link out of the folder" test was skipped there, not run. With
    Developer Mode on (Windows 10 build 14972 or later), Java's `Files.createSymbolicLink` retries without the
    privilege, so the test can run.

## Assets
The modes place vanilla blocks and the menus use vanilla item ids as icons, so the game draws those from the
player's own copy; nothing of Mojang's is in the jar. The mod's own: a 5x7 font drawn for the 3D text, two block
textures (a cloud and a starry rock) drawn by a small script, and the damage types and death messages as data files.
No third-party art.

## Cost and time
- 150 modes: about one long working session for 67 modes, the menu, commands, the Custom editor and the tests. Full
  test runs take about 22 minutes for all 151 cases, at roughly 8.5 s per mode.
- 222 modes: one long working session for 72 modes, the browser, zones and the tests. Full test runs take about 21
  minutes for all 223 cases (about 5.5 s per mode) plus about 7 minutes for the new modes as Custom chains.
- 283 modes: one long session. The 61-mode self-test takes about 6 minutes, the full 284-mode run about 30 minutes,
  the containment test about 2 minutes.

## Open questions
- Why the dev `fly on` didn't stick after a server-side `/tp` in that scenario, while it did in a shorter one.
- Whether regenerated chunks in the scratch dimension should be pruned to save disk space.
- Redo puts back a warp's blocks but not its zone or effect; worth recording zone parameters for redo.
- Whether the aurora should use a real client renderer instead of particles for very large radii.
- Interactions don't fire inside Custom chains (the chain, not the mode, is the warp); worth passing the step's
  subcategory down.
- The older animated modes still run faster than their seconds setting (left unchanged on purpose).
