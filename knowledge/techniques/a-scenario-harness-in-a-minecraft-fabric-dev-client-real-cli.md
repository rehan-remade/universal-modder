---
kind: technique
title: 'A scenario harness in a Minecraft Fabric dev client: real clicks, natural worlds, two clients'
status: working
agents:
- Claude Code
humans: []
date: '2026-10-10'
links: []
tags: [minecraft, fabric, loom, testing, screenshots, harness, worldgen, multiplayer, verification]
---
# A scenario harness in a Minecraft Fabric dev client: real clicks, natural worlds, two clients

> GameTests run on a headless server and call mod code directly, so they miss what only a real client and real
> packets show: the click path, screens, rendering, natural world generation, a second player. A small client
> entrypoint that plays a scripted scenario, logs checks and saves screenshots closes that gap with one command.

## When to use it
- After GameTests pass, to check the same feature the way a player reaches it (a right click goes through
  `ClientPlayerInteractionManager`, a packet and the server's use path; a GameTest calling the item method does not).
- For anything visual (models, item display transforms, screens, particles) and for naturally generated content.
- For a cheap multiplayer smoke test with two real clients.
- On Minecraft 1.21.4 and later, look at Fabric API's own client game tests first: `fabric-client-gametest-api-v1`
  (entrypoint `fabric-client-gametest`) has simulated input, singleplayer and dedicated-server contexts and
  screenshot comparison. Fabric API 0.92 for 1.20.1 has only the server-side `fabric-gametest-api-v1`, hence this
  hand-made harness.
Verified on Minecraft 1.20.1, Fabric Loader 0.16.14, Loom 1.7.4, Windows 10 and Linux (Xvfb).

## How
- **Where it lives:** a `ClientModInitializer` in the test source set (never shipped), active only with a system
  property (`-D<mod>.screenshots=true`) set by its own Loom run config with `--quickPlaySingleplayer <world>`
  (or `--quickPlayMultiplayer host:port`). An environment variable picks the scenario.
- **The script:** a queue of steps `(waitTicks, action, screenshotName)` run from `END_CLIENT_TICK`, starting about
  100 ticks after joining. Server-side setup runs on the integrated server with
  `client.getServer().execute(...)`. Screenshots wait until `worldRenderer.isTerrainRenderComplete()` (bounded).
- **Cheats for setup, not for the thing under test:** give items, place blocks, set time, grant research by
  command; then switch to survival and click for real:
  `interactionManager.interactBlock(player, MAIN_HAND, new BlockHitResult(center, UP, pos, false))` or
  `interactItem(player, MAIN_HAND)`. Check results server-side and `client.currentScreen` client-side; log
  `[harness] <scenario> <check>: OK|FAIL` and a final count.
- **Prove the requirement, not only the effect:** do the action once without its requirement (expect refusal),
  grant it, do it again (expect success). Same tool, same spot, so the refusal cannot come from anything else.
- **Natural generation:** create the world once with the dedicated server (`level-type=minecraft:normal`, fixed
  seed, structures on), then copy it fresh for every run. Find jigsaw pieces by walking the structure set's
  `RandomSpreadStructurePlacement.getStartChunk(seed, rx * spacing, rz * spacing)` cells and loading chunks only to
  `ChunkStatus.STRUCTURE_STARTS`; find biomes with `ServerWorld.locateBiome`; find features by generating chunks
  outwards and scanning sections with `ChunkSection.hasAny(predicate)`. Log the seed, the generator class and every
  position used, and fail loudly when nothing is found instead of placing it by hand.
  - Scan `getStructureStarts()` children for `PoolStructurePiece`s and match a piece by its template id
    (`getPoolElement().toString()` contains it). Element identity maps break for starts read back from a saved
    chunk, where the elements are new instances. 81 placement cells took about 12 s.
- **Two clients:** a second Loom client run config with its own `runDir` and `--username`, started some seconds
  after the first, against a dedicated server run config whose stdin gets `op @a` every few seconds.
- **The wrapper script** fails when no new screenshot was written, so a crashed or never-compiled client is not
  mistaken for success. (A failed harness compile once still exited 0 and left the previous PNG on disk.) Compare
  each PNG's hash with the last run's before looking at it.
- **Load probe:** the same queue can spawn N entities / block entities and log `MinecraftServer.getTickTime()`
  before and after.

## Gotchas
1. **A check ran before the thing it checks.**
   - **Cause:** in a `(wait, action, shot)` step the action runs first and the wait comes after it. A log in the
     same step as a teleport saw `void_air` (the chunk was not there yet).
   - **Fix:** put the wait in its own step before the check, or let a check step re-queue itself until a flag
     set by the server action is true.
2. **The camera fell into the ocean.**
   - **Cause:** a creative player teleported into chunks the client has not loaded counts as on the ground, and the
     client switches flight off.
   - **Fix:** spectator mode for camera-only scenarios, set before long teleports (flight is locked, and no hand
     shows in the shot).
3. **Commands silently did nothing in the multiplayer run.**
   - **Cause:** the clients sent commands before the server's op loop had opped them ("Unknown or incomplete
     command" in the client log).
   - **Fix:** op from the first seconds and give the scenario a 10 s idle step before its first command.
4. **Gradle `--args` replaced the run config's program args** (the quick-play address was lost).
   - **Fix:** put per-client arguments such as `--username` in separate run configs.
5. **No `xvfb-run` on Windows.**
   - **Fix:** use it only when present; elsewhere the client opens a normal window.
6. **A hostile test mob disappeared mid-scenario or merged with a stranger.**
   - **Cause:** `checkDespawn`, or entities left over from other scenarios or tests nearby.
   - **Fix:** `setPersistent()` and clear same-type entities in range at the start.

7. **A short-lived effect is missing from its screenshot.**
   - **Cause:** the capture waits for the terrain to finish building; a beam or bolt has expired by then.
   - **Fix:** let the terrain build first (about 100 ticks after a teleport), then trigger the effect right before
     the capture.
8. **A scripted "throw the item in" step failed.**
   - **Cause:** the selected-slot change had not reached the server before the drop key was pressed, and a throw
     from the ground landed short.
   - **Fix:** change slots at least a tick before dropping, and throw from a block beside the target.
9. **A real-click scenario failed in one run of two.**
   - **Cause:** the original's own random failure path (infusion instability scattering the items).
   - **Fix:** build the original's stabilising setup in the scenario so the chance is 0, rather than changing the
     code under test.
10. **The dev runtime hid release-only problems.**
    - **Fix:** a production-style launch. Build the classpath as a launcher does: Mojang's client jar and libraries
      from the version JSON, Fabric Loader's production `KnotClient` from its loader profile, Loom's cached assets
      and the real dependency jars. Run it 80-90 s and fail on ERROR lines or missing models and textures.
    - Filter the expected offline profile-key 401. The server-side twin is the official Fabric server launcher
      with the remapped jar in `mods/`.
    - It found the atlas mip-level cap ("limits mip level from 4 to 1") that no dev run reported.
11. **Error dialogs on the user's screen.** Harness clients open real windows, so loader or Sodium error dialogs
    appear on the user's desktop. Run under `xvfb-run` where available. A Linux container with Xvfb and Mesa
    (software OpenGL) needs no physical display.
12. **Synthetic clicks on a screen did nothing, or hit the wrong element.**
    - **Cause:** screens that pick their hover target while rendering, from the real mouse position, ignore the
      coordinates passed to `mouseClicked`.
    - **Fix:** set `Mouse.x` / `Mouse.y` by reflection (window pixels = scaled point x window width / scaled width),
      let a frame render, then call `mouseClicked` / `mouseReleased` at the same scaled point. Small read-only hooks
      on the mod's screens that report element centres keep layout copies out of the harness.
    - To hold an item use, `useKey.setPressed(true)` plus `interactItem`: the client then re-uses every 4 ticks
      while the key is held, as a player's would.

## Seen in
- `games/minecraft/porting-thaumcraft-4-1-7-10-forge-to-minecraft-1-20-1-fabric.md`: natural villages, biomes and
  features on a seed-12345 world; 9 of 9 real-click checks and a 28 / 28 progression scenario; two clients; a
  100-node / 40-golem load probe.
  Its gotchas 28 and 29 are two more finds of this harness (aiming the camera at RNG-predicted positions, a refusal
  that was silent only in the port).
- `techniques/fabric-1-20-1-gametests-as-the-oracle-of-a-large-mod-port.md`: the server-side suite this harness
  complements.
- Other scripted dev-client autotests in this KB:
  - `games/halo-3-mcc/halo-3-weapons-covenant-vehicles-and-maps-ported-into-minecr.md`;
  - `games/fpv-logic/fpv-logic-drones-flight-model-rc-radio-and-3d-models-in-minecraft.md`;
  - `games/minecraft/bloons-td-6-in-minecraft.md`.
