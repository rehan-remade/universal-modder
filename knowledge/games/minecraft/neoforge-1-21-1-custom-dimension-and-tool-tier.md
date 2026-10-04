---
kind: game
title: NeoForge 1.21.1 custom dimension and tool tier
game: Minecraft
games_also: []
game_version: 'Java 1.21.1, NeoForge 21.1.252'
platform: windows
engine: java
route: loader-api
tools: [NeoForge MDK (ModDevGradle), Parchment 2024.11.17, JDK 21, GameTest, RCON, Pillow]
anti_cheat: none
status: working
agents:
- Claude Code (claude-opus-5-5)
humans: []
date: '2026-10-03'
links:
- https://github.com/NeoForgeMDKs/MDK-1.21.1-ModDevGradle
tags: [minecraft, neoforge, dimension, worldgen, ore, tool-tier, gametest, rcon, headless-verification]
---
# NeoForge 1.21.1 custom dimension and tool tier

We added a floating-islands dimension called the Voidlands to Minecraft Java 1.21.1 through NeoForge. It has
its own stone, a rare ore, and a tool tier that beats netherite on every stat. A reusable "Rift Key" item
teleports the player between the Voidlands and the Overworld. GameTests on a headless dev server, driven over
RCON, verified the dimension, the ore and the teleport without a game window. The user then confirmed it
works in game.

## Setup
- **OS:** Windows 11. The game is owned through the Microsoft Store / Xbox Minecraft Launcher.
- **JDK:** JDK 21 (Oracle 21.0.11).
- **Template:** `git clone --depth 1 https://github.com/NeoForgeMDKs/MDK-1.21.1-ModDevGradle`, which pins
  `neo_version=21.1.252` and Parchment `2024.11.17`.
- **Rename:** set `mod_id`, `mod_name` and `mod_group_id` in `gradle.properties`, then delete the
  `com.example` package and `assets/examplemod`.
- **First run:** `gradlew compileJava` takes about 4 minutes (download, decompile, recompile). Later builds
  take about 10 seconds.

## Route and why
- **Taken: loader API.** NeoForge `DeferredRegister` handles the blocks and items. Datapack JSON handles the
  dimension, worldgen, loot, recipes and tags.
- **Not taken: a pure datapack.** A datapack could add the dimension but not new items with a custom tool
  tier.
- **Not taken: Fabric.** The user asked for NeoForge.
- **Not taken: a portal frame block.** It would be more work (a portal shape, POIs and a forcer). An item
  that calls `changeDimension` is one class.

## How the game works (what we had to learn)
- **Tiers:** `SimpleTier(incorrectForTag, uses, speed, attackDamageBonus, enchantability, repairIngredient)`.
  - Netherite is 2031 / 9 / 4 / 15.
  - Tool items take `XItem.createAttributes(tier, baseDmg, speed)` through `Item.Properties.attributes(...)`.
- **Mining level:** `incorrect_for_X_tool` is a block tag. Give it an empty tag to mine everything.
  - Ore hardness gating uses `minecraft:needs_diamond_tool`. 1.21 has no `needs_netherite_tool`.
- **Enchanting:** a tool only takes enchantments if it is in `minecraft:swords`, `pickaxes`, `axes`, `shovels`
  or `hoes`. The `enchantable/*` tags reference those tags.
- **Data folder names (1.21):** they are singular: `loot_table/`, `recipe/`, `structure/`, `tags/block/`,
  `tags/item/`. Recipe results use `{"id": ...}`.
- **A dimension is three JSON files:**
  - `dimension/<id>.json` sets a noise generator with a fixed biome source;
  - `dimension_type/<id>.json`, where `effects: minecraft:the_end` gives an End sky;
  - `worldgen/noise_settings/<id>.json`.
- **Terrain:** to get islands cheaply, copy vanilla `floating_islands.json` noise settings and change
  `default_block` and `default_fluid`.
  - Our resource generator reads the router from the user's own client jar at build time.
- **Biome features:** biome `features` is 11 step lists. Index 6 is `underground_ores` and index 2 is
  `local_modifications` (geodes).
- **Teleport:**
  `ServerPlayer.changeDimension(new DimensionTransition(level, pos, Vec3.ZERO, yRot, xRot, DimensionTransition.PLAY_PORTAL_SOUND.then(DimensionTransition.PLACE_PORTAL_TICKET)))`.
  - `ServerLevel.getHeight(Heightmap.Types..., x, z)` generates the target chunk synchronously, which is
    fine for a one-off teleport.
  - Floating islands leave many columns empty. Build a small platform when the heightmap returns the
    minimum build height.
- **EULA in dev:** in dev runs, `Eula` auto-agrees (`SharedConstants.IS_RUNNING_IN_IDE =
  !FMLLoader.isProduction()`), so `gradlew runServer` starts headless with no EULA file.

## Build steps
1. Clone the MDK and rename it (see Setup).
2. Write the Java registries (blocks, items, tier, creative tab, teleport item).
3. Generate the JSON and textures with a script, so you can iterate on numbers quickly.
4. Run `gradlew build`. The jar is in `build/libs/`.
5. For headless checks, put `enable-rcon=true`, `rcon.port` and `rcon.password` in `run/server.properties`.
   Run `gradlew runServer`, connect over RCON, then run `forceload add 0 0` and `test runall`.

## Verification
- **GameTests (in mod code, `@GameTestHolder(modid)` plus `@PrefixGameTestTemplate(false)`):**
  - the tier stats beat `Tiers.NETHERITE`;
  - an 8x8-chunk scan of the new dimension counts the stone and ore blocks;
  - a mock player (`helper.makeMockServerPlayerInLevel()`) uses the key, lands on a non-air block in the
    new dimension, and comes back.
- **Ore density probe:** over RCON, `execute in <dim> run fill <16x128x16> minecraft:air replace <ore>`
  returns "Successfully filled N", which is a cheap ore count.
- **Not verified headless:** client rendering (models, textures, sky). The user checked those in game.

## Gotchas
1. **Symptom:** `runGameTestServer` fails the dimension tests with "dimension is not loaded". **Cause:** the
   GameTest server only builds the overworld. Datapack dimensions are never created ("Preparing start region"
   lists only `minecraft:overworld`). **Fix:** run the same tests on `runServer` with `/test runall`, over RCON.
2. **Symptom:** there's no template for an empty GameTest. **Cause:** NeoForge 1.21.1 ships no
   `empty` structure. **Fix:** write a gzipped NBT `data/<modid>/structure/empty.nbt` by hand:
   `DataVersion` 3955, `size` [1,1,1], `palette` [{Name: air}], and empty `blocks` and `entities`.
3. **Symptom:** `"count": 16, "size": 5` ore made about 25 ores per chunk in floating islands. **Cause:**
   islands are dense (~40-50% solid in the sampled area), so most placements hit stone. **Fix:** count 6,
   size 3 and `discard_chance_on_air_exposure` 0.5 gave about 1 per chunk, close to ancient debris.
4. **Symptom:** `um scan "Minecraft Launcher"` reports "Unknown native engine 10%". **Cause:** it
   fingerprints the Xbox launcher's `gamelaunchhelper.exe`, not the Java game. **Fix:** ignore the engine
   line. The route list is still right (Fabric/NeoForge first).
5. **Symptom:** a Python NBT writer passed through a shell heredoc came out with raw control bytes and
   wouldn't parse. **Cause:** `\x..` escapes were expanded on the way through. **Fix:** build tags with
   `struct.pack` and named constants, and write files with an editor tool rather than a heredoc.

6. **Symptom:** the teleport item dropped the player into a dark 5x5 pocket inside an island; it was only
   noticed by a human watching a take. **Cause:** `Level.getHeight(type, x, z)` returns `getMinBuildHeight()`
   when the chunk isn't loaded, so "no ground" made us build a platform at a fixed Y inside terrain.
   **Fix:** `level.getChunk(x >> 4, z >> 4).getHeight(type, x & 15, z & 15) + 1`. Have the GameTest assert air
   at the feet and head plus `canSeeSky`, not just "not standing on air".
7. **Symptom:** `effects: the_end` with `has_skylight: false` and dark stone made the dimension nearly black on
   video. **Fix:** `has_skylight: true` + `fixed_time: 6000` keeps the End sky but lights the terrain.
8. **Symptom:** `advancement grant @s through <adv>` to pre-empt the "kill a mob" toast spammed toasts.
   **Cause:** `through` grants parents *and* children. **Fix:** grant `only` the root and the one advancement
   before recording.

## Showcase (repeatable take)
- A dev-only server-tick timeline (`-Dvoidrite.showcase=true`) plus `--quickPlaySingleplayer showcase`. Its
  camera moves with `ServerPlayer.connection.teleport(x, y, z, yaw, pitch)` each tick, orbiting the subject
  and climbing until the eye is in air. Item swaps go through `ClientboundSetCarriedItemPacket`, and actions
  through `ItemStack.use` / `player.attack`. No real input is needed.
- Generate the world headlessly with `runServer` (`level-name=saves/showcase`, fixed seed), snapshot it with
  `um backup create`, and restore it with `--clean` before each take. Set `pauseOnLostFocus:false` in
  `run/options.txt`.
- `um win record --title Singleplayer --pid <pid>` (two java.exe were running), then `um video mux`,
  `um video contact` and `um video compile edl.json`.

## Assets
16x16 pixel art made procedurally in Python with Pillow. Shapes are rasterised and shaded top-left lit, with
a 1-px outline pass. No fal spend and no vanilla textures copied. `um publish check` shows 0 failures; its
only warnings are absolute paths in Gradle's git-ignored `build/` cache.

## Cost and time
One session of about 45 minutes. Most of the wall-clock time was the first NeoForge decompile.

## Open questions
- An install guide for a NeoForge profile in the Microsoft Store launcher (separate `gameDir`).
