---
kind: game
title: "Black Ops III: a walkable Zombies usermap with a working navmesh from another map's geometry and clip brushes"
game: "Call of Duty: Black Ops III"
games_also: ["Call of Duty: Black Ops II"]
game_version: "Black Ops III Steam, version 100.2.2.7.109.0 when tested 2026-10-21; Mod Tools Steam build 5284267"
platform: windows
engine: iw
route: data
tools: ["Black Ops III Mod Tools (cod2map, linker, gdtdb)", "OpenAssetTools Unlinker", "Ghidra", "REA", "Python"]
anti_cheat: "None bypassed. Offline custom map through the official Mod Tools. Personal test; converted map content is not distributed."
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: ["AryaBlue"]
date: 2026-11-08
links:
  - https://github.com/AryaBlue/CoD-RE
  - https://github.com/Laupetin/OpenAssetTools
tags: [zombies, t6, t7, usermap, collision, navmesh, cod2map, map-port, plane-cap]
---

# Black Ops III: a walkable usermap from another map's geometry and clip brushes

> We rebuilt Black Ops II's Alcatraz world as a Black Ops III usermap, from our own install. In game it loads through
> Custom Games, shows textured walls, the player stands and walks, and zombies path on the generated navmesh. This
> note covers how to get collision and a navmesh through the official tools. Gameplay is not done, hence in-progress.

## Setup
- Official Black Ops III Mod Tools. T6 and T7 share inch units, so no rescale.
- The source world and clip were dumped from our own Black Ops II with the OpenAssetTools Unlinker.

## Credits
- [OpenAssetTools](https://github.com/Laupetin/OpenAssetTools) (Laupetin) for the dumps.
- Treyarch's Mod Tools do the compile. `cod2map64` limits were read with Ghidra and REA.

## Route and why
Data only, through the normal usermap build. Geometry goes in as `misc_model` chunks at origin, and collision goes in
as real brushes.

## How the game works (what we had to learn)
- **Model collision does not feed the navmesh.** A `cod2map` collmap is a legacy brush `.map` format, not a mesh.
  The navmesh is built from clip brushes.
- **Chunk limits:** we kept chunks to 60,000 vertices and 64 materials each.
- **T6 clip contents to keep:** solid `0x1`, player clip `0x10000`, monster clip `0x20000`. Those three become
  clip brushes. `0x2080` is bullet and missile clip, so emit it as `clip_weapon`.
- **Brush size:** Radiant asserts on brushes with more than 45 sides.
- **Plane cap:** `cod2map64` fails at 131,072 final map planes (`MAX_MAP_PLANES`). Its working cap is 655,360.
  Patch meshes spend no planes, only brushes do, so large flat ground is cheaper as patches.

## Build steps
1. Dump the source map's world, clip and entities.
2. Split the world into chunks, convert to `XMODEL_EXPORT`, register them in a GDT and place them at `0 0 0`.
3. Emit world clip brushes into the `.map`.
4. Seed `node_pathnode` entities from the source map.
5. Run `cod2map` and the linker.
6. Start from Zombies, Custom Games. `+devmap` dropped to the title screen on retail.

## Verification
- **In game:** the map loaded, textured walls showed, the player stood on the dock after the spawn fix and zombies
  pathed. 1,237 of 1,238 source nodes were valid.
- **Not verified:** static props and their collision in game, doors and gameplay, and whether the full port fits the
  plane budget on every map.

## Gotchas
1. **Instant fall through the world on spawn.** Template spawn structs sat inside props. **Fix:** use the source map's
   own initial spawn points, tagged for the start room.
2. **Navmesh is only a tiny region.** `cod2map` keeps only what is connected. **Fix:** seed the source map's path nodes.
3. **Navmesh is buried.** A 22,000-unit solid cube brush at origin swallowed it. **Fix:** skip brushes whose smallest
   extent is over 4,096.
4. **Random solid brushes at the origin.** The last 424 brushes were local-space door and trigger entities. **Fix:**
   keep only submodel 0 in the world and place movers from entities.
5. **Players stick on stairs.** `BulletCollisionLOD` High built a coarse collision model. **Fix:** set it to None.
6. **Invisible walls in front of real walls.** The clip includes collision for static props that were not placed yet.
   Do not shrink the clip. Place the props.
7. **Grey placeholder textures for DLC maps.** The Unlinker needs the DLC ipak on its path under the zone's name.
8. **Decals render as opaque quads.** Strip decal, blood, grunge and shadow caster surfaces from the staged world.
9. **`gdtdb` fails with a duplicate xmodel.** It scans every GDT, so two maps sharing a chunk prefix collide.
   **Fix:** give each map a unique prefix.
10. **`cod2map` hangs at the signature database step.** It happened while Black Ops 4 or Greyhound were running.
    **Fix:** close them.

## Open questions
- Does the cap count each unique plane once, or twice as directed pairs? Our measurements disagreed, so budget for two.
