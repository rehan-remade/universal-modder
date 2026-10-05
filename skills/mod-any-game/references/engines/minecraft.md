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
- **A separate launcher profile keeps the user's worlds safe.** Add a Fabric profile with its own `gameDir`.
  `fabric-installer -launcher microsoft_store` fails for lack of `launcher_profiles_microsoft_store.json`,
  so edit `launcher_profiles.json` by hand, after a backup.
- Multiplayer: a server needs the mod too (or use plugins). Never ship client hacks for public servers.
- Mashups: the September 2026 "Minecraft inside X" projects either reimplemented Minecraft (Rust rewrites
  matching Java worldgen) or ran it side by side and exchanged state (passthrough). Minecraft's own assets
  were downloaded from Mojang at first run and never redistributed.
