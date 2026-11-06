---
kind: game
title: Porting Thaumcraft 4 (1.7.10 Forge) to Minecraft 1.20.1 Fabric
game: Minecraft
games_also: []
game_version: "Minecraft Java 1.20.1, Fabric Loader 0.16.14, Fabric API 0.92.12+1.20.1, Yarn 1.20.1+build.10"
platform: linux
engine: java
route: loader-api
tools: ["Fabric Loom 1.6.12 / 1.7.4", "Gradle 8.8", "Java 17", "Fabric GameTest API", "Vineflower", "CFR", "javap", "Python data extractors", "Xvfb"]
anti_cheat: "none (single-player mod; nothing touches multiplayer anti-cheat)"
status: in-progress
agents:
- Claude Code
humans: []
date: '2026-10-10'
links: []
tags: [porting, legacy, 1.7.10, forge-to-fabric, gametest, worldgen, dimension, mixin, biome, rendering, accessories, baubles, fidelity]
---
# Porting Thaumcraft 4 (1.7.10 Forge) to Minecraft 1.20.1 Fabric

> An ongoing port of the Thaumcraft 4.2.3.5 mod (Minecraft 1.7.10, Forge) to Minecraft 1.20.1 on Fabric, keeping the
> original's behaviour, values and quirks. Each subsystem is checked by GameTests on a real dedicated test server
> (323 passing on 2026-10-10, from 859 decompiled original classes to about 77,000 lines of port code). Rendering,
> screens, the click path, natural world generation and the custom dimension are checked by screenshots from a real
> client driven by a scripted harness. This note collects the 1.20.1 engine facts that cost time. The method is the
> `port-a-mod` skill (`skills/port-a-mod/`); Forge 1.7.10 → Fabric 1.20.1 mappings are in its `references/` folder.
> The test traps that apply to any Fabric 1.20.1 mod have their own notes:
> `techniques/fabric-1-20-1-gametests-as-the-oracle-of-a-large-mod-port.md` (GameTests) and
> `techniques/a-scenario-harness-in-a-minecraft-fabric-dev-client-real-cli.md` (the client harness).

## Setup
- Minecraft Java 1.20.1, Fabric Loader 0.16.14, Fabric API 0.92.12+1.20.1, Yarn 1.20.1+build.10 (v2), Loom 1.6.12
  (1.7.4 since 2026-10-10, see gotcha 19), Gradle 8.8 wrapper, Java 17 (`release 17`; JDK 21 ran Gradle), on Linux
  cloud containers and on Windows 10 (Git Bash).
- The 1.7.10 reference: the Thaumcraft-1.7.10-4.2.3.5 jar (SHA-1 recorded), decompiled with Vineflower and remapped
  SRG → MCP `stable_12-1.7.10` with a token-replacing script (859 classes, 7 not decompilable). CFR was the fallback
  for the classes Vineflower could not decompile cleanly. The decompile and the original assets live in the port's
  **private** repository, so every fresh session can read them; they are never shipped.
- **Permission:** Thaumcraft is All Rights Reserved (Azanor). The port re-implements its code from the decompile and
  its build uses TC4's own textures and sounds (see Assets), so releasing the port would need Azanor's permission.
  The port's repository is private and this note links no release. Nothing from Thaumcraft (code, decompile,
  textures, sounds or data files) is in this repository; the note describes the original's logic in its own words.
- Target modpack pieces loaded in tests: Accessories 1.0.0-beta.48+1.20.1, cloth-config 11.1.118, Trinkets 3.7.2,
  accessories-tc-layer 3.8.1+beta.14, Cardinal Components.
- Builds ran offline from a populated Loom cache: `./gradlew build runGametest --no-daemon`. A fresh cloud container
  needs `maven.fabricmc.net`, `piston-meta.mojang.com`, `piston-data.mojang.com`, `libraries.minecraft.net`,
  `resources.download.minecraft.net` and each dependency's Maven allowed first.

## Route and why
- Route: Fabric loader API plus Mixin, with the original's behaviour re-implemented class by class against its
  decompiled source.
- Forge 1.20.1 was not chosen; the project targets Fabric.
- Data-driven features (dimension, biomes, worldgen, loot, tags) are datapack JSON; everything else is code.
- **How the port is organised** (details in the `port-a-mod` skill):
  - one source of truth: TC 4.2.3.5 only. The project had started from Thaumcraft 5 and switched; TC5 is never a
    reference (gotcha 24 shows what that cost);
  - an adaptation matrix (keep / adapt / replace / remove per area) and a status log with a section per unit:
    original classes, "quirks kept", deviations with their 1.20 reason, tests, "not ported";
  - the original's data (48 aspects, 457 object-aspect registrations, research tree, recipes) extracted from the
    decompiled `Config*` classes by Python tokenizers into JSON, never retyped;
  - one commit per unit; a handoff file for new sessions; completion graded by evidence level (implemented /
    GameTested / visually verified / unverified), not by commit count;
  - audits by layer (event handlers, packets, items, blocks, entities, GUIs, worldgen, loot, research, recipes,
    config, renderers) after the features existed.

## How the game works (what we had to learn)
- **GameTest server:** it builds its world from the flat preset with only the vanilla dimensions, so datapack
  dimensions do not exist in `runGametest`. The NeoForge 1.21.1 note in this KB reports the same. Test dimension
  content in the overworld, and the dimension itself in a client run.
- **Flat generator:** `FlatChunkGeneratorConfig.createGenerationSettings` treats an all-air layer list as "no
  terrain" (`hasNoTerrain`) and then copies none of the biome's features, unless the biome is `minecraft:the_void`.
  A void dimension whose own biome feature builds everything needs one non-air, non-colliding layer:
  `minecraft:structure_void`, height 1.
- **Experimental-settings warning:** a datapack dimension marks the world experimental in two places.
  `DimensionOptionsRegistryHolder.toConfig` compares the dimension count with vanilla's, and
  `getLifecycle(RegistryKey, DimensionOptions)` flags non-vanilla entries. One mixin patches both: a `@Redirect` on
  `List.size()` in `toConfig` that leaves out the mod's namespace, and a HEAD inject returning `Lifecycle.stable()`.
  Both checks feed one value: `toConfig` creates the dimension registry with the count check's lifecycle, and
  `SimpleRegistry.add` merges each entry's lifecycle into it, so either check alone keeps the world experimental
  (read in the 1.20.1 bytecode during review; patching only one was not tried).
- **Biome reads are blended:** `World.getBiome(BlockPos)` (`BiomeAccess.getBiome`) picks a neighbouring 4x4x4 cell
  by a seeded offset (`SeedMixer.mixSeed`). A block near a cell edge can therefore report another cell's biome than
  the one just written with `Chunk.populateBiomes`. Gameplay checks that must agree with a biome you set should read
  `world.getBiomeForNoiseGen(BiomeCoords.fromBlock(x), BiomeCoords.fromBlock(y), BiomeCoords.fromBlock(z))`.
- **Enchanting power per block:** 1.20.1 has `#minecraft:enchantment_power_provider` (one point each). The count is
  int local 4 of the lambda `EnchantmentScreenHandler.method_17411(ItemStack, World, BlockPos)`, and `Random.setSeed`
  is called once after counting. A `@ModifyVariable(ordinal = 0)` at that `setSeed` INVOKE adds extra points (e.g. a
  block worth 2 shelves, Forge's old `getEnchantPowerBonus`). Do not hook `calculateRequiredExperienceLevel`: it runs
  three times inside a loop.
- **Forge `onItemUseFirst`:** in 1.7.10 it ran before the block's `onBlockActivated`; in 1.20.1 the block's `onUse`
  runs first and `Item.useOnBlock` only after the block passes. Fabric's `UseBlockCallback` fires before the block on
  both sides, so items that must win over the block (keys, wands) go there.
- **Cancelling an entity spawn:** Forge's `EntityJoinWorldEvent` cancel maps to `ServerEntityEvents.ENTITY_LOAD`.
  Check `age == 0` so chunk reloads are skipped, and queue the discard with
  `server.send(new ServerTask(server.getTicks(), entity::discard))`. `MinecraftServer.execute` runs the task
  immediately when already on the server thread, so it defers nothing.
- **Note-block hook:** every note actually played goes through `NoteBlock.playNote` → `World.addSyncedBlockEvent`;
  inject at that INVOKE. Setting a note block's state directly does not recompute its `instrument`.

## Build steps
1. `./gradlew build runGametest --no-daemon` runs every GameTest on a headless server and writes
   `build/gametest/junit.xml`; parse it rather than trusting the console.
2. A client harness (a gametest-source-set client entrypoint with `--quickPlaySingleplayer` on a prebuilt world)
   places blocks, teleports the player and saves screenshots for visual checks.
3. Look up Yarn names on the mapped jar in the Loom cache with
   `javap -cp .../minecraftMaven/.../minecraft-merged/1.20.1-net.fabricmc.yarn...-v2/*.jar <class>`, and use
   `javap -c -p` to find lambda names and local indexes for mixins.

## Verification
- **Oracles:**
  - GameTests on the real server (`runGametest`), for logic.
  - Screenshots from a real 1.20.1 client, for rendering and for the dimension: portal → `outer_lands`, arrival
    point, generated maze.
- **Each fact above was verified by:**
  - a failing then passing GameTest: biome reads, enchanting power, entity cancel, note hook;
  - a client run: flat layer, experimental warning, dimension;
  - bytecode reading with `javap`: `BiomeAccess`, the `EnchantmentScreenHandler` lambda.
- **Gotchas 19-21** were verified the same day with GameTests on the real jars (and a client start).
- **Gotchas 15-18 were verified on 2026-10-10** on a seed-12345 normal world (Windows 10, client window, no Xvfb):
  the log line counts before and after each fix, inspected screenshots, and a GameTest for gotcha 15 (313 passing).
- **Verified later (2026-10-10):** the real-client click path. A screenshot-harness scenario drives
  `ClientPlayerInteractionManager.interactBlock` / `interactItem` in survival (packets, then the server's use path)
  for the wand triggers, the research table, three screens and the infusion altar (refused without its research,
  formed with it): 9 of 9 checks passed. GameTests alone call the item logic directly and cannot show this.
- **Gotchas 31-58** were each found by a failing GameTest, a harness screenshot, a log check of the production
  client, or an audit against the decompiled original, as recorded per unit in the project's migration log. The
  full suite stood at 323 / 323 on 2026-10-10. The real-client progression scenario passed 28 / 28 (Thaumonomicon,
  crucible, worktable, research table, research note solved by dragging aspects, infusion, a golem placed and
  cored by hand).
- **Not verified:**
  - patching only one of the two experimental-warning checks, in game (both were patched together; the bytecode
    says both are needed);
  - Sodium / Indium with the port's FRAPI models (the dev runtime cannot run Sodium, gotcha 52);
  - a full survival playthrough, a full modpack instance, and multiplayer beyond a two-client smoke test.

## Gotchas
Traps that apply to any Fabric 1.20.1 GameTest suite or client harness are written up once, in the GameTest note
(`techniques/fabric-1-20-1-gametests-as-the-oracle-of-a-large-mod-port.md`) and the harness note
(`techniques/a-scenario-harness-in-a-minecraft-fabric-dev-client-real-cli.md`). They keep their number here and
point there.
1. **A dimension GameTest finds no world.** The GameTest server has no datapack dimensions: GameTest note, gotcha 7.
2. **Void dimension, but the biome feature never runs.**
   - **Cause:** all-air flat layers count as "no terrain", so features are skipped.
   - **Fix:** one `structure_void` layer.
3. **Every world load stops on the experimental-settings screen.**
   - **Cause:** the dimension-count and lifecycle checks.
   - **Fix:** the two-part mixin above.
4. **Crash "asking a region for a chunk out of bound", or log "setBlock in a far chunk", from a feature.**
   - **Cause:** 1.7.10 world generation wrote into neighbouring chunks; 1.20.1 features only see their chunk and a
     small margin.
   - **Fix:** split the generator so each chunk writes only inside itself.
5. **A biome was just written but the check says it wasn't, at some positions only.**
   - **Cause:** `getBiome` blends neighbouring cells by seed.
   - **Fix:** read the stored cell with `getBiomeForNoiseGen`.
6. **Unrelated tests start failing after new tests are added.** Global state keyed by position leaks between tests:
   GameTest note, gotcha 2.
7. **A mob on a pressure plate never presses it.** It had `setAiDisabled(true)`: GameTest note, gotcha 8.
8. **Mobs in other tests act strangely.** The in-world mock player is seen by every test in the batch: GameTest
   note, gotcha 3.
9. **`ctx.createMockPlayer()` does not compile on 1.20.1.** 1.20.1 has only the three `createMock*Player*` methods:
   GameTest note, gotcha 3.
10. **Boss entities spawned in corner chunks are not found by `getEntitiesByClass`.** Those chunks were not
    entity-ticking: GameTest note, gotcha 6.
11. **Crop "growth" code does nothing.**
    - **Cause:** 1.20 crops grow in `randomTick`; 1.7.10 used `updateTick`.
    - **Fix:** call `randomTick`.
12. **A note-block test hears nothing.**
    - **Cause:** the instrument property is not recomputed when the state is set directly, and a per-tick "heard
      notes" list was never cleared.
    - **Fix:** set `instrument` in the test, and clear the list at `END_WORLD_TICK`.

13. **A 1.7.10 multiblock's faces changed with their neighbours (connected textures), and 1.20 models cannot read
    neighbours.**
    - **Cause:** 1.7.10 picked icons at render time (`getIcon(IBlockAccess, x, y, z, side)`).
    - **Fix:** inside a formed structure those inputs never change. Compute them once when it forms, store them as
      block-state properties, and generate one model per state with a script that ports `getIcon`. For TC4's
      infernal furnace that was 231 states, and it keeps vanilla culling and AO.
14. **A screenshot harness reported success, but the picture was from an older run.** The harness's compile had
    failed and the old PNG was still on disk: harness note, "The wrapper script".
15. **Log "Tried to load a block entity for block X but failed" right after world generation.**
    - **Cause:** a 1.7.10 block class covered several metas, only some with a tile entity (`hasTileEntity(meta)`). Ported as
      one `BlockWithEntity` per meta, every state counts as having a block entity. `ChunkRegion.setBlockState` then queues
      a dummy block entity for each placed block, and `createBlockEntity` returns null for the metas without one.
    - **Fix:** only the metas `hasTileEntity` lists implement `BlockEntityProvider` (a subclass); the rest extend `Block`.
      Seen with TC4's eldritch obelisk body; the warning went from 4 per new world to 0.
16. **"Detected setBlock in a far chunk ... currently generating: <your decorator feature>".**
    - **Cause:** a 1.7.10 `BiomeGenBase.decorate(world, rand, x, z)` port keeps populate's frame: it decorates
      x + 8 .. x + 23, the corner of the next chunks. A 1.20 feature may write only 16 blocks around its own chunk, so
      wide trees near the +x / +z edge are refused (clipped) and logged.
    - **Fix:** shift the frame by -8 (`x = chunkX * 16 - 8`): the same 16 x 16 square lands on the decorated chunk and
      trees get 16 blocks of margin on every side. Densities stay the same; positions move 8 blocks for a given seed.
17. **A scripted screenshot client lands underwater or on the ground after a long teleport, though it was flying.**
    Creative flight switches off in unloaded chunks; use spectator mode: harness note, gotcha 2.
18. **Finding a naturally generated jigsaw piece (a modded village house) in a test world.** Walk the structure
    set's placement cells to `STRUCTURE_STARTS` and match pieces by template id: harness note, "Natural generation".
19. **"Mod was built with a newer version of Loom (1.7.413), you are using Loom (1.6.12)" when adding a dependency.**
    - **Cause:** Loom refuses to remap a mod jar whose manifest `Fabric-Loom-Version` is newer than the build's Loom.
    - **Fix:** raise Loom to at least that minor (1.6.12 -> 1.7.4 worked on Gradle 8.8 with no other change; 314 tests
      unchanged). Patching the jar's manifest also works but leaves a modified third-party jar to maintain.
20. **`NoClassDefFoundError: net/fabricmc/mapping/tree/TinyMappingFactory` at launch after adding cloth-config.**
    Its pom pulled an old fabric-loader and Fabric API onto the dev runtime; use `{ transitive = false }`: GameTest
    note, gotcha 12.
21. **Trinkets and the Accessories "Trinkets compat layer" in one pack (1.20.1).**
    - **Fact:** accessories-tc-layer 3.8.1+beta.14 declares `"provides": ["trinkets"]` and ships the Trinkets API
      classes. With Trinkets 3.7.2 also installed, Fabric Loader 0.16.14 keeps the layer (higher version) as
      `trinkets` and silently drops real Trinkets: it is not in the loaded-mod list.
    - **Consequence:** an Accessories-based mod needs no Trinkets adapter; Trinkets-API mods see its items through the
      layer (`TrinketsApi.getTrinketComponent(player).isEquipped(item)` was true for items worn in Accessories slots).
      With real Trinkets and no layer, the two inventories are separate and that call returns false.
22. **"No data fixer registered for <modid>:<entity>" ERROR lines at every start, also on a production server.**
    - **Cause:** `EntityType.Builder.build(id)` calls `Util.getChoiceType` only to validate the id against vanilla's
      data fixer schema and drops the result; mod ids are never in it.
    - **Fix:** a `@Redirect` of that call in `EntityType.Builder.build` returning null for your namespace. Saving and
      loading do not depend on it; all 318 tests still passed. Fabric API's `FabricEntityTypeBuilder` avoids the line
      without a mixin: in Fabric API 0.92 (1.20.1) its `build()` constructs the `EntityType` directly and never makes
      that call.
23. **Testing the release jar, not the dev runtime.**
    - **How:** the official server launcher `https://meta.fabricmc.net/v2/versions/loader/<mc>/<loader>/<installer>/server/jar`,
      the remapped jar plus real dependency jars in `mods/`, `eula=true`, pipe `stop` once the log says `Done (`, then
      fail on `/ERROR]` lines or stack-trace lines. Do not fail on every line mentioning "Exception": Accessories logs a
      WARN with `ClassNotFoundException` for its client-only mixin target on servers.
24. **Code and assets still following the version the port was first based on.**
    - **Symptom:** the project had been switched from a Thaumcraft 5 base to Thaumcraft 4, and every audit
      compared gameplay with TC4, yet the wand was still drawn with TC5's OBJ mesh and TC5 textures, and
      several projectile and hole renderers, an input handler and a swing hook still did what TC5 did.
    - **Fix:** grep comments and identifiers for the old version's name ("TC5", "1.8.9") and audit each hit
      against the real reference; hash every texture and model and compare with the reference jar's assets
      (here 16 textures and a whole folder of OBJ meshes had no TC4 origin; 9 icons that looked new were exact
      crops of a TC4 sprite sheet). Removing an unused leftover is safe only after grepping for its path.
25. **A regression test that could not fail.** 40 ticks of key repeat on a mod-3 toggle gave the buggy code the
    right answer too: GameTest note, gotcha 1.
26. **Systematic renderer drift that per-feature tests never catch.**
    - **Symptom:** every gameplay test passed, yet the thaumometer was invisible, infused ores were solid tinted
      cubes, glows were cut into hard blobs and many item icons faced the wrong way.
    - **Fix:** a read-only audit per renderer group (tile, block / ISBRH, entity, item), each comparing the port's
      code with the original renderer line by line (GL state, matrix sequence, brightness, UVs) and returning
      findings ranked by visibility; then one harness scenario that places every flagged object and is re-run after
      each fix. About 60 differences surfaced in one pass; none was TC5-derived. Details of the GL11 to 1.20 mapping:
      `techniques/porting-1-7-10-gl11-render-states-and-iitemrenderer-frames-t.md`.
27. **Item icons of TESR-drawn blocks a quarter-turn off.**
    - **Symptom:** chests showed their back, tables and the bore base faced away; adding TC4's own
      renderInventoryBlock rotations did not help.
    - **Cause:** the shared `builtin/entity` item model used vanilla 1.20's GUI rotation (30, 225, 0); 1.7.10's
      INVENTORY_BLOCK frame works out to (30, -45, 0) (RenderItem's z flip, 210 X, 45 Y, -90 Y).
    - **Fix:** give the shared builtin model the 1.7.10 frame; then each item replays the original's own turns
      exactly.
28. **A visual check that "found nothing" because of the camera, not the code.**
    - **Symptom:** a 1-in-20 random overlay never appeared in screenshots; forcing it on every face showed it.
    - **Cause:** the creative player fell after the teleport, so the "overview" was a close-up containing none of
      the predicted positions. The positions were confirmed with jshell (java.util.Random), then in the game log.
    - **Fix:** for random decorations, compute the expected positions with the original RNG first and aim the
      camera at them (and remember a teleported creative player does not keep flying).
29. **A refusal that was silent only in the port.**
    - **Symptom:** holding the thaumometer on most things did nothing at all; server-side GameTests of scanning
      passed.
    - **Cause:** TC4 ran the scan's validity check on the client first and told the player why ("study <parent
      aspect>", "nothing can be learned"); the port kept only the server's re-check, which refuses quietly.
    - **Fix:** port the client-side pre-check with its message. Found only by driving the item through the real
      client (use key held) in a scripted scenario, not by server tests.
30. **Synthetic `mouseClicked` calls on the Thaumonomicon did nothing, or clicked the wrong node.** TC4's screens
    pick their hover target while rendering, from the real mouse position; move the mouse first, and add small
    read-only hooks for node, tab, hex and palette centres: harness note, gotcha 12.

31. **Every block in the game lost its mipmaps ("limits mip level from 4 to 1").**
    - **Cause:** a handful of 1.7.10 textures 6 or 8 px wide (animated strips, one leftover 8 x 8) in the block atlas
      cap the mip level of the whole atlas.
    - **Fix:** upscale them by whole factors with nearest-neighbour (8 → 16, 6 → 48 px); they look the same. Found
      only by checking the log of a production-style client launch.
32. **AI checks fire every 10 ticks instead of every 15.**
    - **Cause:** 1.20's `GoalSelector` tries to start goals every 2nd tick; 1.7.10's task list every 3rd. Delay counters
      inside a start condition scale with it.
    - **Fix:** documented as a platform deviation; scale the counter if exact timing matters.
33. **A mob sent to an exact block stops a block short.**
    - **Cause:** `startMovingTo` treats arriving within about a block as done; 1.7.10's pathfinder walked onto a solid
      target.
    - **Fix:** path to the exact point, or to the air above a solid target.
34. **Ported biomes appear but have no features, ores or spawns.**
    - **Cause:** Fabric API 0.92 (1.20.1) has no overworld biome injection, and `BiomeModifications`'
      `foundInOverworld()` is evaluated against the overworld biome source's list in the `MinecraftServer` constructor,
      before any lifecycle event.
    - **Fix:** a `MultiNoiseBiomeSource` mixin that rolls ~256-block regions at the original odds and adds the biomes to
      the source's list (entries from `DynamicRegistrySetupCallback`). TerraBlender is the library alternative.
35. **Ported biomes have no lakes, dungeons, geodes, ores or carvers.**
    - **Cause:** 1.7.10's shared `BiomeDecorator` gave every biome these; a 1.20 biome JSON has only what it lists. It
      also has no 1.7.10 default spawn list, `topBlock` or computed sky colour.
    - **Fix:** copy vanilla's carvers and non-vegetation features into each biome, write the default spawns in, store
      the sky colour from the 1.7.10 formula, sample the real surface instead of `topBlock`.
36. **Underground logic sees a cave biome.** 1.7.10 biomes were per column; 1.20 cells are 3D. Ported logic (node and
    infused-stone placement) should read the column's surface biome.
37. **A ported structure never generates (0 mounds in 4225 chunks).**
    - **Cause:** the original's site test (five points of a 19 x 19 area within one block of the corner height) almost
      never passes on 1.20 terrain; a third of the rolls also land in ocean.
    - **Fix:** count rolls against placements with a temporary counter before assuming generation is broken. Relaxing
      the check is a fidelity decision for the user.
38. **Ported trees have leaves that decay, or a tree test keeps 733 of 734 leaves.** Schedule a block tick for every
    leaf a generator places so 1.20 computes `DISTANCE`; checks must tolerate a cut-off leaf.
39. **1.7.10 village houses as jigsaw pieces.**
    - **How:** a script replays each `StructureVillagePieces` component's build code into structure templates (desert
      variants through the 1.7.10 block-swap functions). The templates go into the vanilla house pools at
      `SERVER_STARTING` with weights scaled to the pool. A `StructurePoolGenerator` mixin enforces the per-village
      limit.
    - **Check:** 150 villages gave 73 towers and 74 banker homes, never two of a kind.
    - **Gotcha:** profession villagers with 0 experience and no job site lose their profession
      (`LoseJobOnSiteLossTask`); give them 1 experience.
40. **A client with default config can't break a block on a server with another config.**
    - **Cause:** the original read the config inside `getBlockHardness`; 1.20 bakes hardness into
      `AbstractBlock.Settings`, so client mining prediction disagrees.
    - **Fix:** a mixin on the state's hardness returning the live config value (synced by a config packet sent last
      on join).
41. **Holding a toggle key toggles repeatedly.** `KeyBinding.wasPressed()` counts OS key repeats; drive toggles from
    press edges. 1.20 vanilla also owns F (swap hands), which 1.7.10 did not: swallow it while the mod's item is held.
42. **Special item entities shoot up in water and lava.**
    - **Cause:** in liquids 1.20 applies item buoyancy instead of gravity; the 1.7.10 counter-gravity lift adds to it.
    - **Fix:** add the lift only on ticks that apply gravity.
43. **A sneak-click with an item never reaches the block.** In 1.20 a sneaking player holding an item does not get to
    `Block.onUse`; the port documented it (the action needs an empty hand).
44. **Wand on a table: the screen of the new block did not open.** In 1.7.10 one click ran the item hook and then the
    activation of the block the hook had just placed; open the new block's screen explicitly after converting.
45. **Recipes changed shape or lost entries after conversion.**
    - **Causes:** 1.20 trims blank pattern rows and columns; in 1.7.10 registration a bare Block ingredient meant every
      variant and a bare Item meant meta 0; lookups were first-match in registration order; one research entry adds
      the same aspect twice (ESSENTIARESERVOIR: VOID twice = 8), which an extractor that overwrites map keys loses.
    - **Fix:** encode the rules in the extractor, keep the original order, accumulate instead of overwriting, and check
      every cross-reference resolves. An audit found 17 recipes silently skipped at load; logging the skip count drove
      it to 0.
46. **NBT outputs, strict NBT inputs, and smelting into two items** have no vanilla 1.20.1 JSON: custom serializers
    (`shaped_nbt`, `shapeless_nbt`, `smelting_count`) and Fabric's `fabric:nbt` ingredient.
47. **Assets from the 1.7.10 jar fail to load.** Paths were mixed case (`Bore.png`) and the jar held junk
    (`es_i_1 - Copy.png`); lower-case every path and reference, skip non-identifiers, namespace `sounds.json`, and
    convert `.lang` to JSON keeping the old keys.
48. **Additive particles turned black while a lightning bolt was alive.**
    - **Cause:** CUSTOM-sheet particles flushed just before render layers whose lightmap phase switches the lightmap
      off.
    - **Fix:** each custom particle sheet turns the lightmap back on in `begin()`.
49. **OBJ meshes from the original: textures on the wrong faces, seams at edges.** Forge 1.7.10's `WavefrontObject`
    read `vt u v` as (u, 1 - v) and inset each UV 0.0005 towards the face average. Flip V and apply the inset.
50. **1.7.10 post-effect shaders (warp screen effects).** Run them as `PostEffectProcessor`s at HUD time; port custom
    programs from GLSL 120 to 150 and move global-initialiser work into `main()`. The warp mist's `GL_EXP` fog became a
    linear fog ending at 3 / density.
51. **A 16-pass texgen "starfield" (end-portal style).** 1.20 has no texgen; one core shader computes all layers, and
    its formula was checked against a numeric emulation of the 1.7.10 GL pipeline (difference < 1e-11).
52. **Sodium cannot be tested in the dev runtime.** Sodium 0.5.11 refuses the dev LWJGL snapshot
    (`-Dsodium.checks.issue2561=false` gets past it), then fails with `NoSuchFieldError CommonVertexAttribute.COUNT`;
    2025 Sodium / Indium jars also need Loom 1.9. FRAPI block models need Indium under Sodium: check in a real pack.
53. **Zombie subclasses gained drowned conversion and reinforcements.** A 1.20 superclass adds behaviour 1.7.10 lacked;
    list it and switch off what the original did not have. The 1.7.10 zombie-villager variant was part of `EntityZombie`
    (inherited by subclasses); in 1.20 it is a separate entity, so the port reimplemented it in the subclass.
54. **Behaviour inherited from 1.7.10 vanilla changed.** Big-oak trees, slime hops, the old flight movement, the
    villager model and the zombie box (0.6 x 1.8) all differ in 1.20; port the 1.7.10 versions.
55. **Damage that ignored armour, magic, fire.** 1.7.10 `DamageSource` flags are 1.20 damage-type tags
    (`#bypasses_armor`, `#witch_resistant_to`, `#is_fire`...); custom sources are new damage types. Forge's
    `ISpecialArmor` was ported as is and runs from a mixin on `applyArmorToDamage` only for wearers of a special piece.
56. **Baubles on Fabric.** Accessories' default slots (`necklace` x1, `ring` x2, `belt` x1) are Baubles' AMULET, RING,
    RING, BELT. A thin `BaublesApi` facade keeps every reader unchanged; Accessories is a compile-only, `suggests`
    compat module; each wearable is registered with `AccessoriesAPI.registerAccessory` and
    `AccessoriesRendererRegistry.registerNoRenderer` (TC4 drew nothing worn).
57. **Ore-dictionary compat ("for each metal found").** Use `c:<metal>_ores` / `c:raw_<metal>_ores` /
    `c:<metal>_ingots`, rebuild lookups on `TAGS_LOADED`, gate recipes with `fabric:item_tags_populated`, and
    resolve "the first ingot" results from the tag when used (tags are synced to clients). 1.20 ores drop raw metal and
    have deepslate variants: extend ore-processing tables to both.
58. **Dead code in the original.** 7 FX classes were never called and 3 packets never sent in TC4 4.2.3.5; check call
    and send sites in the decompile before porting, and record what was skipped.

## Assets
The port's private build uses the original mod's own textures and sounds (Azanor's, All Rights Reserved; see
Setup). None of them are in this repository. No generated assets.

## Cost and time
Many sessions. One full `build runGametest` takes about 1–2 minutes from a warm Loom cache.

## Open questions
- Answered from the 1.20.1 bytecode during review: neither experimental-warning check is enough alone (How the game
  works), and AI-disabled mobs skip their block collisions because `Entity.move` never runs for them (GameTest note,
  gotcha 8).
- Does the port hold up under Sodium and Indium in a real modpack (gotcha 52)?
