---
kind: game
title: Runtime dimensions, parallel-universe portals and whole-dimension endings in Forge 26.3
game: Minecraft
games_also: []
game_version: Minecraft Java 26.3, Forge 66.1.5
platform: windows
engine: java
route: loader-api
tools: [ForgeGradle 7, JDK 25, Vineflower-decompiled reference sources (kept outside the repo)]
anti_cheat: none (single player, own dedicated server)
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: '2026-11-14'
links: ["https://github.com/MinecraftForge/MinecraftForge", "https://github.com/Vineflower/vineflower"]
tags: [dimensions, portals, shaders, saveddata, world-scale, respawn, forge-config, dedicated-server, forge]
---
# Runtime dimensions, parallel-universe portals and whole-dimension endings in Forge 26.3

> A Forge 26.3 mod (a disasters mod's 1.12.0 release, plus later portal and respawn fixes) that creates "parallel
> universes" as real dimensions while the server runs (pristine seed, variant seed, or an echo copy of the player's
> surroundings), portals into them with a charge and a point of no return tied to world-ending events, a world-ending
> event that rewrites a whole dimension including chunks generated later, and a procedural-shader sky (eyes, a planet).
> No mixins: loader API, reflection into the server's level map, and own core shaders. Verified in scripted dev clients
> and on a dedicated server with two clients.

## Setup
- Minecraft Java 26.3, Forge 66.1.5, ForgeGradle 7, JDK 25 (Windows 11). Dev runs with `runClient` / `runServer`.
- Decompiled 26.3 + Forge sources in a private folder outside the repo, used only to check API names and behaviour.
- Optional compatibility tested with TNT Expansion 4.7.1 (+ its two library mods) on the dev classpath only.
- **Multiplayer:** universes, portals and world-ending events change the world for everyone on the server, and an
  ending kills whoever stays behind. That's for single player, or a server you run with players who agreed to it.

## Route and why
Loader API plus a little reflection. A mixin into level creation was the alternative; it isn't needed because the
server's level map is a plain mutable map and the level constructor is public. Datapack-defined dimensions were
rejected: they are fixed at world creation and can't be made on demand (the
[NeoForge 1.21.1 dimension note](neoforge-1-21-1-custom-dimension-and-tool-tier.md) shows that route).

## How the game works (what we had to learn)
1. **Levels at runtime.** `MinecraftServer` keeps its levels in a `LinkedHashMap` keyed by dimension key; level creation
   at startup just constructs a `ServerLevel` (server, executor, storage access, a `DerivedLevelData`, key, a
   `LevelStem`, flags, seed hash, spawners, tick time) and puts it in. Reflection on the unobfuscated field names
   (`levels`, `executor`, `storageSource`) is enough. Add between ticks (command, packet handler or a queued server
   task), never during a level tick. Then set up the world border link and fire Forge's level-load event. Recreate
   saved ones at server start. The client needs nothing extra: the respawn/teleport packet names the dimension and its
   type (reuse the overworld type).
2. **A different seed** for a runtime level: chunk generation reads the level's seed from inside the chunk-map
   constructor, which runs during the `ServerLevel` super-constructor, before subclass fields exist. Hand the seed in
   through a ThreadLocal read by an overridden seed getter.
3. **Time and weather are server-wide in 26.3.** Day/night runs on world clocks per dimension *type*, and the vanilla
   timeline data binds them to the overworld; weather is one object on the server. Runtime dimensions of the overworld
   type therefore share time and weather; separating them would need copies of vanilla data files.
4. **Portals:** implement vanilla's `Portal` interface on a block (return a `TeleportTransition`); vanilla handles the
   wait, cooldown, passengers and nausea. The transition's post-teleport callback is the place to bring leashed /
   sitting pets and to build a return portal.
5. **Own shaders:** a `RenderPipeline` with own `core/*.vsh/.fsh` and the position/UV/colour/normal vertex format gives
   the fragment shader nine floats per vertex for procedural parameters. Sky objects: depth test "greater or equal",
   no depth write, drawn from a client-only anchor entity kept at the camera.
6. **Heights:** a chunk's height query returns the top block; the level's height query returns one above it.
7. **Tags changed:** `#minecraft:dirt` is only dirt, coarse dirt and rooted dirt in 26.3; grass, podzol and mycelium
   are `#minecraft:grass_blocks`; the umbrella for "ground" is `#minecraft:substrate_overworld` (dirt, mud, moss blocks
   and grass blocks).
8. **Event lists:** stopping (removing) one event from inside the manager's tick loop throws a concurrent-modification
   exception; mark it finished and let the manager remove it.
9. **Whole-dimension rewrite:** a per-dimension record that rewrites loaded chunks over several ticks (time-budgeted)
   and any other chunk the moment it loads or generates, with a saved "done" set, covers chunks that don't exist yet.
10. **Respawn points in other dimensions.** `ServerPlayer.setRespawnPosition(new RespawnConfig(RespawnData.of(dim, pos,
    yaw, pitch), forced=true), false)` works like `/spawnpoint`. If that spot is later blocked, vanilla *clears* the
    respawn config before `PlayerRespawnEvent` fires and puts the player at the world spawn (another dimension). A
    fallback that reads the config in the respawn event sees nothing; keep your own copy in the player's persisted data
    (`getPersistentData()` under `ServerPlayer.PERSISTED_NBT_TAG`, which Forge copies across death) and move the player
    there.

## Build steps
1. Create the level as in (1) from a command handler; keep a SavedData list of universes and recreate them on
   server-started.
2. Portal frame block + block entity (charge phases), portal block implementing `Portal`, a key item holding the target
   in custom data.
3. For world-ending events, compute "seconds until the end here"; portals collapse a configurable time before it
   (10 s by default before 1.15.1; from 1.15.1 the default is 0, so they stay open until the destruction starts, and
   gotcha 13 says how that default was changed).
4. `./gradlew build`; the jar contains only the mod's own classes and assets.

## Verification
- Scripted dev clients (a scenario runner inside the mod, dev only): create/visit universes (dimension read back from
  player data), echo copy checked at fixed coordinates (a chest's contents), portal charge, crossing with a leashed pig
  and a sitting wolf, return portal, point of no return logged before the end.
- Whole-dimension ending: block counts in the impact area and in a chunk first generated after the impact contained
  only end-state blocks; screenshots looked at.
- Save and reload mid-approach with a portal charging: both resumed.
- Dedicated server with two clients: one crossed before the end and survived in the universe, the portal collapsed
  10 s before, the other stayed and died at the impact; no errors in the server log.
- 37-scenario regression of earlier features compared line by line with the previous release's logs, with and
  without an optional compat mod.
- **Follow-up (1.15.1, the collapse default changed to 0):** a scripted dev client checked it with a 20 s countdown:
  the portal was open at 8.95, 1.9 and 0.35 s left, the player crossed at about 9 s, and the portal collapsed at 0 s.
- **Respawn fix:** dying in the universe crossed to respawns there; with the respawn spot walled in, the fallback moves
  the player to safe ground in that universe (log line), not back to the first world.
- Not verified: very large worlds (thousands of chunks) under the full-pass mode on low-memory machines.

## Gotchas
1. **NoAI mobs never move.** Used as physics probes, they ignored gravity and pushes. **Cause:** NoAI disables
   movement physics entirely. **Fix:** use armour stands as probes.
2. **Return portal built on the traveller.** **Cause:** the "frame here" helper used the arrival spot. **Fix:** place
   it 5-12 blocks away from the arrival point.
3. **Client sky effects followed the player into another dimension.** **Cause:** client state was only cleared on
   leaving the world. **Fix:** clear when the client level object changes.
4. **Erosion did nothing on flat ground, and grass wasn't treated as ground.** **Cause:** droplets need a slope; the
   26.3 dirt tag shrank. **Fix:** let droplets wander as sheet flow on flat ground; use the umbrella ground tag.
5. **Crash at the world-ending impact.** **Cause:** stopping child events inside the event loop. **Fix:** mark them
   finished.
6. **Respawning players died again and again** in a lava-sea end state. **Cause:** the spawn point itself was
   rewritten to lava. **Fix:** after a respawn in an ended dimension, wait until the chunks around the player are
   rewritten, then move them to standing ground (or a small platform).
7. **Breaking an activation object in the End didn't abort an event in another dimension.** **Cause:** the "object
   broken during the countdown" check looked in the event's dimension. **Fix:** store the object's dimension with the
   event. Remember the player's previous dimension on the changed-dimension event (persistent data) to know which world
   they mean. `canSeeSky` is always false in the End (no skylight): test "open above" with the WORLD_SURFACE heightmap.
8. **Sky screenshots came out white.** **Cause:** the effect's heavy bloom. **Fix:** photograph sky features with
   bloom at 0.
9. **Shipped OGGs showed as changed after re-running an audio generator.** **Cause:** the encoder isn't byte-stable.
   **Fix:** restore unchanged files from git.
10. **A reload test failed after a killed run.** **Cause:** the earlier half (which saves the world) had been stopped
    mid-way by a low-memory kill. **Fix:** re-run both halves.
11. **A copied log belonged to the previous run.** **Cause:** `latest.log` copied right after the client quit, before
    rotation. **Fix:** keep the console output as well.
12. **Test runs killed for low memory** (16 GB host, dev server + two clients). **Cause:** leftover game clients and
    Gradle daemons from earlier runs. **Fix:** close them by PID between runs; cap heaps (`-Xmx`) for multi-client
    tests.
13. **A new `ForgeConfigSpec` default didn't reach players who already had the config file.** **Cause:** the old value
    is written in the file, and Forge only uses a default when the key is missing or invalid. **Fix:** define the
    setting under a new key (here `pointOfNoReturn` = 10 became `collapseBeforeEnd` = 0). Forge then adds the new key
    with its default and removes the stale one from the file, logging both as "Incorrect key ... was corrected from
    ... to its default" (from null for the new key, to null for the old one).
14. **A "did the portal collapse after the end?" check still found the portal blocks** (single player, checked from
    the dimension the player had crossed into). **Cause:** block entities tick only while their chunk is loaded; most
    likely the old dimension's chunks had unloaded, so the portal's block entity never ticked (not confirmed). **Fix:**
    run that check with the player nearby; a second run with the player beside the portal saw it collapse.
15. **With the respawn spot walled in, players respawned in the first world.** **Cause:** vanilla clears a blocked
    forced respawn point before `PlayerRespawnEvent` fires. **Fix:** keep your own copy in persisted data (How the
    game works, 10).

## Assets
All textures and sounds generated by the mod's own Python scripts (pixel art drawn in code, synthesised audio); no
vanilla assets copied.

## Cost and time
About two days of agent sessions for the whole release, including regression runs.

## Open questions
- Separate time and weather per runtime dimension without copying vanilla timeline data.
- A cheaper full-pass rewrite for very large explored worlds.
