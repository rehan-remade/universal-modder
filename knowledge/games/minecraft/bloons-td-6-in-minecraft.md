---
kind: game
title: "Bloons TD 6 inside Minecraft: the guest's rules as a headless 2D sim, Minecraft as the view"
game: "Minecraft"
games_also: ["Bloons TD 6"]
game_version: "Minecraft Java 1.20.1 + Forge 47.2.0 (dev and benches; also runs on Forge 47.4.10 in the user's modded instance), Java 17, official mappings. Guest: Bloons TD 6 v56.3, Epic Games Store build, Unity 6000.0.58f2, IL2CPP, Addressables 2.9.1"
platform: windows
engine: java
route: reimplementation
tools: ["Forge MDK 1.20.1-47.2.0 (Gradle, official mappings, JDK 17)", "javac + a plain-Java bench (engine tested without Minecraft or Gradle)", "Python 3.14 + UnityPy 1.25.4 + Pillow + numpy", "fmod_toolkit (FMOD decoding of AudioClips)", "ffmpeg (OGG Vorbis, mono)"]
anti_cheat: "none on the host side. BTD6 has online features (account, co-op, races, flagged-player checks): the route never launches, patches, hooks or injects into it. Only its asset files were read offline, read-only, from the user's own install"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["Ratman258"]
date: 2026-10-04
links: []
tags: [mashup, reimplementation, headless-sim, tower-defense, forge, unity6, unitypy, addressables, local-resource-pack, skinning, mirror-entities, client-side-projectiles, config-toml, benches]
---

# Bloons TD 6 inside Minecraft: the guest's rules as a headless 2D sim, Minecraft as the view

> A Forge 1.20.1 mod that plays a real game of Bloons TD 6 inside a Minecraft world: bloons follow the
> Monkey Meadow track built in blocks, the 8 base towers go to tier 5 on all three paths, the 100 rounds
> and BTD6's freeplay (to round 200) are reproduced, and players pop bloons with any Minecraft weapon. The
> guest's rules run as a pure-Java 2D simulation in BTD6 units; Minecraft is only the view and the input.
> Posed 3D models, sprites, icons, sounds, official strings and the map's ground are converted from the
> user's own BTD6 install into a local resource pack that never enters the jar or git. Verified by four
> automated benches, including a scripted real-world client run whose screenshots were read one by one; a
> real two-player session on two PCs has not been verified yet.

## Setup
- **Host:** Minecraft Java 1.20.1, Forge 47.2.0 MDK (official mappings, Java 17). The shipped jar was also
  run by the user on Forge 47.4.10 in a CurseForge instance with other mods (Essential, Identity, Easy NPC,
  WorldEdit).
- **Guest:** Bloons TD 6 **v56.3**, Epic Games Store install on Windows 10. Unity **6000.0.58f2**, IL2CPP,
  Addressables **2.9.1** with a binary `catalog.bin` (no `catalog.json`). Bundles are UnityFS v8, LZ4HC
  128 KB blocks, not encrypted, typetrees present. Each bundle exists twice: `Full` and `Half` (same meshes,
  same PathIDs, textures half size).
- **Converter:** Python 3.14 with **UnityPy 1.25.4**, Pillow, numpy; `fmod_toolkit` for audio and ffmpeg for
  OGG. A full extraction takes about 3.5 minutes and 1.7 GB of RAM at peak and writes ~1,560 files
  (~135 MB) into `resourcepacks/<local pack>/`, plus a ground grid into the mod's `config/` folder.
- **Size:** about 51,000 lines of Java (14,000 for the engine, which imports nothing from Minecraft) and
  7,600 lines of Python for the converter and the data checkers.

## Route and why
`route: reimplementation`. BTD6 is a 2D top-down game whose rules are numbers (ranges, rates, pierce,
immunities, layers, cash, rounds). Those rules were rewritten as a **headless simulation** that steps at
BTD6's own 60 steps per second, in BTD6 units, and Minecraft draws it. Against the four mashup patterns:
- **Port the content (pattern 1):** porting towers one by one as Minecraft entities with Minecraft AI and
  Minecraft projectiles would lose the exact numbers and cost one entity per dart (a tier 5 tack tower
  emits dozens of projectiles per second). The rules had to be one coherent engine, not 120 ports.
- **Passthrough (pattern 2):** running BTD6 next to Minecraft means injecting into an online-capable
  IL2CPP client. Ruled out on safety grounds, and pointless: nothing of BTD6's renderer was needed.
- **Embed a decomp (pattern 3):** there is no decomp of BTD6, and making one is out of bounds.
- **Reimplement (pattern 4, chosen):** the sim is the source of truth; Minecraft holds **mirror entities**
  for bloons and towers, and has no entity at all for projectiles. It is pattern 4 in reverse: the guest
  is reimplemented, the *host* stays real and becomes the renderer and controller.

What this buys: BTD6's numbers apply unchanged; the engine is tested in seconds without Minecraft; the
network cost is the bloons' positions, not the projectiles'; and any weapon, vanilla or modded, can hit a
bloon because the bloon is a real `LivingEntity` whose `hurt()` forwards into the sim.

## How the game works (what we had to learn)
**The bridge.**
- **Frame:** world.x = origin.x + u.x × S, world.z = origin.z − u.z × S (BTD6's map "up" is north, −Z),
  y = the ground. S = 0.6 blocks per unit by default: the 376 × 280 u Monkey Meadow becomes about
  226 × 168 blocks.
- **Time:** dt is always 1/60 s. Game speed multiplies the number of sim steps per server tick (3 at ×1,
  9 at ×3, 1.5 at ×0.5 with the remainder carried over), never dt.
- **Bloons** are `LivingEntity` mirrors: no AI, no physics, no gravity server-side, positions copied from
  the sim every tick; `hurt()` converts the hit (sword = sharp, pickaxe = normal and pops lead, arrows
  pierce, unknown modded weapons = vanilla damage ÷ 4) into a sim damage event. Synced data: type, flags
  (camo, regrow, fortified), a state byte (frozen, glued, stunned, damage state, burning), sim id, box size.
- **Towers** are immobile, invulnerable `Entity` mirrors; the saved state lives in the world's
  `SavedData`, the entity is recreated if it goes missing.
- **Projectiles have no entity.** The server batches "projectile created" records (id, visual id, motion
  type, position, velocity, lifetime, target) once per tick; the client advances them with **the same
  motion code** as the server. Removals and effects (pops, explosions, tracers, floating text) are
  batched the same way, with a small string dictionary at the head of each packet.
- **UI:** every screen button is a server command (`/btd ...`), so each action exists and is testable
  without the screen; screens only display a JSON snapshot sent by the server.
- **Language:** the server does not know each player's language, so everything is a translatable key;
  even the thousands separator and decimal mark travel as keys and are resolved per client.

**The guest's data.**
- Bloons, rounds 1-100, towers and their 120 upgrades are JSON data: each upgrade is a patch on the base
  tower. Behaviour the data cannot express (bouncing, orbiting glaives, sacrifices, teleport...) is
  hand-written Java per tower, each with its own bench. Numbers were researched from two community
  sources and checked by a validator (about 3,500 checks).
- **Freeplay (rounds 141+)** is a seeded random draw over a fixed list of 529 bloon groups. The rule is
  publicly documented (the community wiki's data module and an open-source freeplay explorer); it was
  reimplemented and matches reference rounds bit for bit. The group list and rounds 101-140 come from the
  game's own data files; a few constants were confirmed by a read-only look at the game binary. Nothing
  from the binary is reproduced here.

**The guest's files (Unity 6).**
- Towers live in the `generated_assets_all_<hash>.bundle`; bloons, MOAB-class 3D prefabs, effects and
  sounds in `asset_references_all_<hash>.bundle` (865 MB on disk, 4.3 GB decompressed, mostly `.resS`);
  simple bloons are sprites in a `SpriteAtlas` of `sprite_atlases_all_<hash>.bundle`; official strings in
  the localization bundle (one XML file per language, e.g. `French.xml`). Hashes change every update.
- **Which prefab is which tier:** each tower/bloon model in the game's sim-model `TextAsset` carries a
  display GUID; the Addressables catalog maps the GUID to the asset path, which is the bundle container
  key. Prefab file names contain typos, so names must never be built from a pattern.
- Tower prefabs are one skinned `Flat_*` mesh (450-2,300 vertices, 16-bit indices, Float16 UV0) on a
  hashed 2048² atlas **shared between towers**, an Animator on `LOD_1`, sometimes rigid props parented to
  bones. Root scale (0.8-1.3) is baked into the bind matrices.
- **The stored pose is the bind pose (arms out in a T).** The in-game pose is the first frame of the idle
  clip. Clips are Mecanim Generic: streamed curves (cubic segments per key), dense curves, constant
  curves; each binding addresses a Transform by CRC32 of its path relative to the Animator. UnityPy reads
  the clip objects but does not evaluate them, so the converter samples them itself, rebuilds world
  matrices and does linear skinning.
- **The map ground:** the converter classifies the map's ground texture per 0.5 u cell (HSV thresholds:
  grass shades, path slabs, pebble border, flowers, rocks) and writes a class grid; the Java side picks
  blocks through a configurable palette, so the file names no Minecraft block.
- **Map zones:** "no placement" areas are polygons and circles; circles are stored as (x, y) with y = −z;
  tree polygons are authored 100 units up in the scene (see Gotchas).

**The mod's own model format.** A small little-endian mesh file (header, bounds, vertices with UV and
normal, triangle indices, texture name, optional per-frame vertex positions for the attack animation) is
drawn by a custom renderer with `RenderType.entityCutoutNoCull`, not `forge:obj` (which needs block-atlas
textures and `usemtl`, and silently drops faces without them).

## Build steps
1. Build the mod jar with the Forge MDK (`./gradlew build`, JDK 17). One `btdmc` jar in `mods/`.
2. Run the converter against the user's own install, once per Minecraft instance:
   `python outils/extraire_btd6.py --instance "<instance folder>"` (finds the Epic install, or `--btd6`).
   Each module (strings, GUI, bloons, projectiles, items, sounds, models, extras, map) runs in its own
   Python process so memory goes back to the OS between modules. Activate the local pack in
   Options → Resource Packs.
3. Without the pack the mod is fully playable with placeholder cube models, no sound and a plain map.
4. In a creative world with cheats: `/btd carte construire` builds the map around the player (40 blocks of
   air cleared above, terrain snapshot kept), `/btd partie nouvelle`, then the tablet item to place towers.
   `/btd carte effacer` restores the previous terrain exactly, chests and contents included.
5. Two PCs: the same jar on both sides (the network channel carries a protocol version, so an old client
   is refused at login), and each player extracts their own pack from their own BTD6.

## Verification
Four oracles, each runnable by one command, plus data validators:

| Oracle | What it covers | Result |
|---|---|---|
| Headless engine (`javac`, no Minecraft, no Gradle) | rules, data loading, patches, 64 tier triplets × 8 towers, a 100-round game, freeplay draw vs reference rounds, per-round load measurements | 885 tests + 983 checks of the hand-written behaviours, 0 failures |
| Dedicated server self-test (`runServer -Pselftest`) | the bridge with real commands, entities, packets, saves (including damaged saves and restart), Forge events driven by fake players in survival, a real bucket emptied on the path then 80 ticks of world | 588 tests, 0 failures |
| Real client self-test (`runClient -Pselftest`, once per language) | screens opened with fabricated snapshots, numbers in each language, no truncated button label, screenshots | 333 tests × 2 languages, 0 failures |
| Scripted real-world bench (`runClient -Pmonde[=scenario]`) | a throwaway flat world: builds the map, places and upgrades towers, plays rounds via commands, opens screens, measures TPS, mspt and FPS, counts sounds actually played, takes screenshots | ~190 screenshots across scenarios, **each one opened and read**; the log separates measurements from remarks, 0 remarks |

Measured on the dev PC (flat world, render distance 12, client capped at 120 FPS):
- **Round 63** with 8 upgraded towers: 20.0 TPS, 1.4-1.5 ms per tick, up to 230 bloons at ×3, FPS 118.
- **Freeplay rounds 120, 150, 163, 180, 200** played in full with 16 tier-5 towers: 20.0 TPS throughout,
  mean 1.4-2.1 ms per tick, worst tick 10 ms (55-68 ms only on Minecraft's own 5-minute autosave), FPS
  minimum 60 when dozens of 3D blimps are on screen. Round 163 with no defence: 965 bloon entities, 118 FPS.
- A 400-bloon stress run in "bloons drawn as Minecraft mobs" mode: 93 FPS with a 4 ms render budget.
- A scripted RCON test on a server: 16 water sources poured on the path, 0 flow.

**Not verified:**
- a real session with two humans on two PCs (login refusal of an old jar, friendly fire between real
  players);
- performance in the user's real instance (Forge 47.4.10, other mods, render distance 16) and in a
  non-flat world under load;
- the shipped jar under production (SRG) names beyond the user's two short play sessions (0.2.0 to
  round 106, 0.5.0 rounds 1-14); the latest build 0.5.1 had not been launched yet;
- shaders, and any BTD6 version other than v56.3 (bundle hashes and typetrees may change).

## Gotchas
Minecraft / Forge 1.20.1:
1. **Chunks appear empty from above right after building the map.** **Cause:** not lighting and not chunk
   sending (a second send changed nothing): the client's visible-section graph is computed when the camera
   enters a section and is not rebuilt until it moves to another one. **Fix:** after the map-info packet,
   the client forces `LevelRenderer.needsUpdate()` 1 s, 4 s and 8 s later.
2. **A movement-speed bonus zooms the view.** **Cause:** any `MOVEMENT_SPEED` attribute modifier feeds the
   FOV modifier. **Fix:** in `ComputeFovModifierEvent`, recompute only the speed term without the mod's
   modifier (sprint, flying and bow zoom kept). Apply the modifier with a fixed UUID every 10 ticks inside
   the map box and remove it outside, on logout and on map erase.
3. **Writing the Forge TOML at runtime truncates it.** **Cause:** `ConfigValue.set()` then `save()` write
   the file in place, twice, while Forge's file watcher (night-config 3.6.4) re-reads it; it parsed a
   half-written file ("Table with path [...] has been declared twice"), the in-memory config was half
   emptied and written back: 37 lines out of 178. **Fix:** keep the live value in memory, replace the
   line in the text, write a sibling temp file and rename it over the original (snippet below).
4. **Hand edits to the TOML are often missed.** **Cause:** the same watcher ignores a "modified" event that
   aggregates several (`WatchEvent.count() > 1`), which is what an editor's truncate-then-write produces.
   **Fix:** poll the file's mtime once a second, compare the lines with what was last read, apply.
5. **A changed default never reaches existing users.** **Cause:** Forge adds new keys but never rewrites a
   value already in the file. **Fix:** migrate by hand or rename the key; document it. Also write floats
   as `1.0`, never `1`, or Forge reads an integer.
6. **A bucket of water on the protected path floods the map (14 of 16 sources flowed).** **Cause:** Forge
   captures block placements from `Item.useOn` to fire `EntityPlaceEvent`, except for buckets; the water
   flowed 5 ticks later, before the periodic scan. **Fix:** listen to `NeighborNotifyEvent` (fires for
   buckets, `/setblock`, flint and steel), track the block in the same tick, and freeze it by clearing its
   scheduled fluid/block ticks every tick; rescan the whole path at server start. Then 0 of 16 flowed.
7. **Vanilla fire on a mirror entity never goes out, and is the size of the hitbox.** **Cause:** the mirror's
   minimal server tick never counts fire ticks down. **Fix:** `displayFireAnimation()` returns false;
   anything that should burn a bloon applies a burn status in the sim, and the client draws scaled flames.
8. **Potions, knockback and golem hits move or change mirror entities.** **Cause:** they are real
   `LivingEntity`s. **Fix:** `isAffectedByPotions()` false, `addEffect` overridden to convert the effect
   into a sim status, `knockback()` empty, `setDeltaMovement` pinned to zero, `isPushable()` and
   `blocksBuilding` false.
9. **The `ice` block floods the map.** **Cause:** ice melts to water near light with no event. **Fix:** allow
   only `packed_ice` / `blue_ice` for the "frozen ground" effect; place it silently (no neighbour
   updates, no drops) and keep what was under it in `SavedData` to restore it, including after a crash.
10. **A held right-click fired the first shot 32 blocks ahead.** **Cause:** `use()` repeats every 4 ticks
    while held, and catch-up logic for the missed sim time treated the idle cooldown as lag. **Fix:**
    tell a fresh click from a held one; on a fresh click fire once from the player; when catching up, the
    last due shot starts at the player.
11. **A projectile that hits within the tick it is born is never drawn.** **Cause:** it is created and
    removed before the batch is sent. **Fix:** accepted as a limit (its explosion is drawn); benches fire
    from at least 14 units away.
12. **Hundreds of pop sounds per second.** **Cause:** a server-side `playSound` per pop is a packet per
    sound. **Fix:** sounds ride on the batched effects packet and the client plays them; caps on effects
    per tick (400) and on loud sounds. Minecraft's sound engine only reports sounds within earshot of the
    camera, so the bench counts "requested" and "actually played" separately.
13. **Mobs used as puppets glide.** **Cause:** `LivingEntityRenderer` clamps walk animation speed to 1, so a
    fast bloon slid 7 blocks per stride. **Fix:** derive the walk cadence from distance travelled and allow
    up to 4. Puppet entities are created once per kind, never added to the level (no AI, tick, sound or
    boss bar), and drawn by their real renderer on a separate pose stack.
14. **A key binding did nothing in the user's instance.** **Cause:** G was already bound by other installed
    mods. **Fix:** read the instance's `options.txt` before picking a default key (U here).
15. **Benches pass, the shipped jar does not.** **Cause:** dev runs use Mojang names, production uses SRG
    names; anything that matches methods by name (reflection, a fake-world probe) behaves differently. This
    cost a previous mod of the same workshop a whole pass. **Fix:** never match by name; have the human
    run the real jar in the real instance before calling it done.
16. **Two PCs, two jar versions, a crash mid-game.** **Fix:** create the network channel with an explicit
    protocol version string; a mismatched client is refused at login.

The mashup itself:
17. **Towers could be placed inside trees.** **Cause:** BTD6's tree polygons are authored 100 units up in the
    scene and seen through the game's tilted camera, so on the ground plane they sit away from the trees.
    **Fix:** shift them by 100 / tan 60° = 57.735 units in z; then they land on their circles.
18. **The map silently fell back to defaults.** **Cause:** our own JSON config helper built the `.bak` path
    by joining the relative folder twice, so a file in a subfolder was never regenerated; its test only
    used flat file names. **Fix:** build the backup as a sibling of the file; test nested paths.
19. **The friend's Minecraft arsenal emptied rounds on its own.** **Cause:** block burns (lava, campfire)
    were applied like a tower's burn, which passes to the layers below. **Fix:** route every Minecraft
    weapon, block, potion and golem through the sim's status and damage pipeline, with burns that stay on
    the hit layer; zones are centred on the track, not on the block (43% of path columns never touched a
    small bloon before).
20. **Translated text on a server that does not know the player's language.** **Fix:** send
    `Component.translatable` everywhere, and encode numbers as "@key:values" strings resolved client-side.

Unity 6 + UnityPy extraction:
21. **`UnityPy.load()` used 8.7 GB of RAM.** **Cause:** it decompresses the whole bundle; the big one is
    4.1 GB decompressed. **Fix:** decompress only the serialized files and expose `.resS` / `.resource`
    as lazy windows that decompress one 128 KB LZ4 block on demand; one Python process per module. Peak
    about 1.5-1.7 GB.
22. **"dictionary changed size during iteration" and slow loads.** **Cause:** a `UnityPy.Environment`
    without `path=""` searches the current directory recursively for every missing CAB dependency and
    can load a stray file mid-iteration. **Fix:** `UnityPy.Environment(path="")` and load the needed bundles
    together.
23. **Every tower stands in a T-pose.** **Cause:** skinned meshes are stored in bind pose; exporters (and
    a naive UnityPy export) give that. **Fix:** evaluate the first frame of the idle clip yourself (see
    How the game works) and skin. Prefabs can have several Animators (a cape): per Animator, take the clip
    that binds the most bones, or 0 of 52 bones match.
24. **Too many or wrong parts.** **Cause:** prefabs contain inactive GameObjects (5 capes, 1 active),
    eyelid meshes that close the eyes, ground shadow sprites, and preload tables list meshes that are not
    in the hierarchy. MOAB-class meshes carry 3 materials (diffuse, stencil, outline). **Fix:** walk the
    Transform tree from the container's root, skip inactive objects with their children, drop
    eyelids/shadows, keep material 0.
25. **Mirrored models.** **Cause:** Unity is left-handed. **Fix:** x → −x for positions and normals and
    reverse the winding; v → 1 − v for UVs; clamp the few UVs slightly outside [0, 1]. Check with a
    named bone (the right hand must end on the right).
26. **Prefab names cannot be guessed.** **Cause:** hashed bundle names change every update, and some
    prefab names have typos. **Fix:** find bundles by prefix; map tier codes through display GUIDs (sim
    model → binary Addressables catalog → container path).
27. **Silent sounds.** **Cause:** `AudioClip.samples` needs FMOD (Vorbis-in-FMOD). **Fix:** install
    `fmod_toolkit`; convert with ffmpeg to **mono** OGG, because Minecraft only attenuates and positions
    mono sounds (a stereo pop sounds the same everywhere).
28. **Huge textures.** **Cause:** tower atlases are 2048² and shared between towers. **Fix:** read the
    `Half` variant (same meshes, half-size textures) and crop each part's texture to its UV bounding box
    plus a few pixels, then remap UVs (a 16× memory saving for one tower).

The atomic write used for gotcha 3 (our code, identifiers translated):
```java
static void writeAtomic(Path p, String text) throws Exception {
    Path tmp = p.resolveSibling(p.getFileName() + ".writing");
    Files.writeString(tmp, text, StandardCharsets.UTF_8);
    for (int attempt = 0; ; attempt++) {
        try {
            try {
                Files.move(tmp, p, REPLACE_EXISTING, ATOMIC_MOVE);
            } catch (AtomicMoveNotSupportedException e) {
                Files.move(tmp, p, REPLACE_EXISTING);
            }
            break;
        } catch (AccessDeniedException busy) {   // Windows: the watcher holds the file
            if (attempt >= 4) throw busy;
            Thread.sleep(15L);
        }
    }
    Files.setLastModifiedTime(p, FileTime.fromMillis(System.currentTimeMillis()));
}
```

## Assets
Nothing generated. Everything visual or audible comes from the user's own BTD6 install through the
converter: about 500 posed 3D models (towers at every tier triplet, MOAB-class, 3D projectiles, a few
extras) with an optional sampled attack animation, bloon sprites with all variants, GUI icons and
portraits, 99 sounds, official FR/EN strings and the map's ground grid. The converter renders preview
sheets by **re-reading the files it wrote**, which checks the mesh format end to end, and the agent looked
at every sheet. The pack is private to each user: never in the jar, never in git, never sent to anyone.
Without it, placeholder cube models keep the mod playable.

## Cost and time
Two calendar days (version 0.1.0 on day one, 0.5.1 on day two), several waves of parallel agent sessions
(Claude Code, Opus 5.5) with an adversarial review pass (3 blocking, 9 important, 13 minor findings, all
fixed), one human directing and playing. Parallel work was prepared in a staging folder with `javac` only,
with a single integrator running Gradle, because two Gradle builds at once collide.

## Open questions
- A real two-player session on two PCs, and the cost in a heavily modded instance at render distance 16.
- Six more towers are prepared (data, behaviours, assets) but not merged.
- Distant bloons drawn as mobs fall back to BTD6 sprites; attached projectiles follow the bloon's box,
  not the mob's body.
- BC7 textures (a handful in the big bundle) were not needed and not exercised.
- After a BTD6 update, re-run the converter and the GUID map; typetrees may change.
