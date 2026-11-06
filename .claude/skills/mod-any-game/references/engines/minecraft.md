# Minecraft

## Java Edition: code mods with Fabric (or NeoForge)
- **Fabric:** a light loader and Fabric API, with Mixin for bytecode patches. It updates fast to new
  versions.
  1. Get the template from https://fabricmc.net/develop/template/, or clone `FabricMC/fabric-example-mod`.
  2. Build with `./gradlew build`. The jar goes to `mods/`. `./gradlew runClient` launches a dev client with
     your mod (the perfect agent oracle: logs in `run/logs/latest.log`).
- **NeoForge:** the successor of Forge for modern versions (MDK template), with a bigger API surface
  (capabilities, events).
- **Forge (1.20.1, 47.x):** still the loader of many CurseForge instances. MDK with official mappings,
  JDK 17. `./gradlew runServer` / `runClient` are the oracles; gate any self-test behind a Gradle
  property (e.g. `-Pselftest`) so it is inert in a real world. Never run two Gradle builds at once.
- **Mappings:** Mojang publishes official obfuscation maps. Loom (Fabric) handles Yarn or Mojang mappings
  and produces readable sources: `./gradlew genSources`.
- **Content:** register items, blocks, entities and sounds through the registries. Assets go under
  `src/main/resources/assets/<modid>/` (textures 16x16 PNG, models JSON, lang JSON, sounds.json + ogg).
  Data (recipes, loot tables, tags) goes under `data/<modid>/`.
- **Server-side only:** plugins (Paper/Spigot) plus resource packs change a lot without client mods. The
  "Black Ops 2 inside vanilla Minecraft" demo was a plugin plus a resource pack.
- `minecraft-modding-mcp` gives an agent mappings, decompiled source and version diffs.

## Porting an old Forge mod (1.7.10 / 1.12) to modern Fabric
- Use the **port-a-mod** skill. It covers the original's license (which decides whether the port can be
  published) and the method: one pinned source version, a private remapped decompile, an adaptation matrix,
  data extracted by scripts, unit-by-unit GameTests, audits by layer, and resumable status docs.
- Its `references/minecraft-1-7-10-forge-to-1-20-fabric.md` maps Forge 1.7.10 concepts to Fabric 1.20.1. For
  example:
  - `onItemUseFirst` → `UseBlockCallback`;
  - metadata → flattened ids;
  - ISBRH → FRAPI;
  - `IItemRenderer` → builtin item renderers;
  - Baubles → Accessories;
  - DamageSource flags → damage-type tags.
- **Decompile and remap:** 1.7.10 jars use SRG names. Use Vineflower, CFR for the classes it fails on, and the
  MCP `stable_12` CSVs. Read the target's mapped jar with `javap` from the Loom cache.
- **Oracles:**
  - GameTests on the real test server:
    `knowledge/techniques/fabric-1-20-1-gametests-as-the-oracle-of-a-large-mod-port.md`;
  - a scripted real client:
    `knowledge/techniques/a-scenario-harness-in-a-minecraft-fabric-dev-client-real-cli.md`;
  - the release jar on a real server.
- **Rendering:** 1.7.10 GL11 states (alpha test, `GL_ADD`, brightness, `IItemRenderer` frames, `ModelBox`
  mirroring) are mapped in
  `knowledge/techniques/porting-1-7-10-gl11-render-states-and-iitemrenderer-frames-t.md`.
- **Worked example:** Thaumcraft 4.2.3.5 → 1.20.1 Fabric (323 GameTests). See
  `knowledge/games/minecraft/porting-thaumcraft-4-1-7-10-forge-to-minecraft-1-20-1-fabric.md`.
- **Cloud and sandboxed builds:** Loom needs `maven.fabricmc.net` and Mojang's `piston-meta`, `piston-data`,
  `libraries.minecraft.net` and `resources.download.minecraft.net`. A populated Loom cache builds offline. The
  test server's "Cannot contact authentication server" line is harmless.

## Bedrock Edition: add-ons
Behavior packs (JSON entities/items/blocks + Script API in JavaScript/TypeScript, `@minecraft/server`) and
resource packs. Develop in `com.mojang/development_*_packs` and turn on content-log output for errors.

## Pitfalls
- Match the exact game version + loader version + API version triple; mods are version-locked.
- **Minecraft 26.3 facts from the GTA passthrough project** (`knowledge/games/gta-v/minecraft-passthrough.md`):
  - A depth readback (`copyTextureToBuffer`) leaves the read buffer at `GL_NONE`, so later colour readbacks
    fail. Restore it in a mixin.
  - Fabric's `JOIN` event fires before the player is in the player list; delay setup commands by ~10 ticks.
  - An entity's Invisible flag resets on first sync unless it has an effect.
  - Invulnerable entities can't be targeted by mobs.
  - With `noPhysics`, `onGround` sticks, so elytra glides get cancelled.
- **Forge 1.20.1 facts from the Bloons TD 6 mashup** (`knowledge/games/minecraft/bloons-td-6-in-minecraft.md`):
  - Writing the TOML at runtime with `ConfigValue.set()` + `save()` can truncate it: the file is written
    in place while Forge's watcher (night-config 3.6.4) re-reads it. Keep the live value in memory and
    write a sibling temp file, then rename it over the original.
  - That watcher also misses many editor saves (it ignores aggregated modify events): poll the mtime.
  - Forge never rewrites a value already in the TOML, so a changed default never reaches existing users.
    Write floats as `1.0`, not `1`.
  - Buckets bypass `EntityPlaceEvent` (Forge does not capture their placement). To police fluids, listen
    to `NeighborNotifyEvent` and act in the same tick.
  - Any `MOVEMENT_SPEED` modifier widens the FOV; undo only your term in `ComputeFovModifierEvent`.
  - Chunks rebuilt server-side can stay invisible until the camera changes section (the client's
    visible-section graph is cached): call `LevelRenderer.needsUpdate()` a few seconds later.
  - Minecraft only attenuates and positions **mono** sounds; convert stereo sources to mono.
  - Dev runs use Mojang names, the shipped jar SRG names: anything matching methods by name passes the
    benches and fails in the real game. Have the human run the real jar in the real instance.
  - Give the network channel an explicit protocol version so a client with another jar is refused at
    login instead of crashing mid-game.
- **Fabric 1.20.1 facts from the Thaumcraft 4 port**
  (`knowledge/games/minecraft/porting-thaumcraft-4-1-7-10-forge-to-minecraft-1-20-1-fabric.md`):
  - The GameTest server has no datapack dimensions. Test dimension content in the overworld.
  - A flat generator whose layers are all air runs no features. Add one `structure_void` layer.
  - A datapack dimension marks worlds experimental through two checks; both are patched by one mixin.
  - `World.getBiome(pos)` is blended by seed. Read the stored cell with `getBiomeForNoiseGen` to match what
    you wrote.
  - 1.7.10 world generators wrote into neighbouring chunks, but 1.20 features may not. Split the writes, and
    shift ported `decorate(x, z)` frames by -8.
  - A Fabric `FakePlayer` is invulnerable. `createMockCreativeServerPlayerInWorld` leaks into the whole test
    batch.
  - Mod jars built with a newer Loom refuse to remap. Raise Loom (1.6 → 1.7.4 worked).
  - cloth-config's pom drags an old loader onto the classpath. Declare it `transitive = false`.
  - The Accessories Trinkets layer `provides` trinkets, so Fabric Loader silently drops real Trinkets.
- **A separate launcher profile keeps the user's worlds safe.** Add a Fabric profile with its own `gameDir`.
  `fabric-installer -launcher microsoft_store` fails for lack of `launcher_profiles_microsoft_store.json`,
  so edit `launcher_profiles.json` by hand, after a backup.
- Multiplayer: a server needs the mod too (or use plugins). Never ship client hacks for public servers.
- **Port fidelity:**
  - A 1.7.10 `Item.onItemUseFirst` ran before the block's `onBlockActivated`. In 1.20 the block's `onUse` runs
    first, so items that must win go through `UseBlockCallback`.
  - Many 1.7.10 mods checked on the client first and showed a chat message before asking the server. Port that
    pre-check too, or the port refuses silently.
- Mashups: the September 2026 "Minecraft inside X" projects either reimplemented Minecraft (Rust rewrites
  matching Java worldgen) or ran it side by side and exchanged state (passthrough). Minecraft's own assets
  were downloaded from Mojang at first run and never redistributed.
