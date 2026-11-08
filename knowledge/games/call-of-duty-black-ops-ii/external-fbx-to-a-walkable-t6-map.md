---
kind: game
title: "Black Ops II: linking a walkable Zombies map from your own FBX files with the OpenAssetTools BSP linker"
game: "Call of Duty: Black Ops II"
game_version: "Black Ops II Zombies, Steam build 24784239, run through Plutonium T6 (launcher revision 5369 when written); tested 2026-10-20"
platform: windows
engine: iw
route: data
tools: ["OpenAssetTools T6 linker as vendored in B2W (commit 7d027e8f)", "our own Python FBX writer"]
anti_cheat: "Data only: a mod folder of linked zones, played solo. No client patching or injection in this route."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["AryaBlue"]
date: 2026-11-08
links:
  - https://github.com/Ticass/B2W
  - https://github.com/Laupetin/OpenAssetTools
  - https://github.com/AryaBlue/CoD-RE
tags: [zombies, t6, bsp, fbx, collision, linker, map-port, ipak, lighting]
---

# Black Ops II: a walkable map from your own FBX files

> The BSP linker in B2W's OpenAssetTools fork does not need a converted source map. Give it `BSP/map_gfx.fbx`,
> optional `BSP/map_col.fbx` and a few required files, and it builds the world, collision and zone itself. We used
> this to build a small test world that spawned, walked, lit correctly and ran Zombies rounds in the real game.

## Setup
- Black Ops II Zombies on Steam, Plutonium T6, Windows 11.
- B2W's vendored OpenAssetTools, 32-bit Release linker. Line references below are for commit 7d027e8f.
- Any tool that writes FBX. Ours was a small standalone Python writer.

## Credits
- [OpenAssetTools](https://github.com/Laupetin/OpenAssetTools) (Laupetin) and the [B2W](https://github.com/Ticass/B2W)
  BSP linker work. Everything here describes how to feed their code.

## Route and why
Data only. The Python side of B2W reads its own intermediate world format and writes `BSP/*`. The C++ linker only
reads `BSP/*`, so any importer that writes those files directly works.

## How the game works (what we had to learn)
### Required inputs
- `BSP/map_gfx.fbx` (`BSPCreator.cpp:307`).
- Scripts `maps/mp/<zone>.gsc`, `_amb.gsc`, `_fx.gsc`, the three matching `.csc` files, and rawfile
  `animtrees/fxanim_props.atr`.
- Every surface material under its T6 name. A missing one falls back to a placeholder.
- Images `reflection_probe0`, `$outdoor`, and `lightmap0_secondary` when there is no `lightmaps.json`.
- The zone file needs at least one asset line. The BSP step triggers on `BSP/map_gfx.fbx` being on the search path.

### FBX conventions
- Y-up. Game coordinates are stored as (x, z, -y).
- Put vertices in game units and set Lcl Scaling to 100, because the linker divides by 100 (`BSPCreator.cpp:55`).
  Scaling 1 shrinks the map 100 times.
- Only each mesh's own local transform is applied, so bake transforms into the mesh.
- Author counter-clockwise front faces. The linker reverses triangles.
- The material name is the T6 material asset name.
- UV0 is required. UV1 is the lightmap UV.

### Limits
- Any index over 65,535 skips the mesh, and triangle counts are 16-bit, so split large meshes. Our writer splits at
  1,536 triangles or vertices per mesh.
- Collision is triangle soup with a hard cap of 65,535 welded vertices for the whole map (`ClipMapLinker.cpp:855`).
  This is the main risk for a large map, so simplify collision. For voxel worlds, emit only exposed faces and merge
  coplanar ones.
- The linker builds one cell with no portals and an all-visible PVS, so there is no occlusion culling. We did not
  measure this at large-map scale.

### Optional inputs and their fallbacks
| File | Without it |
|---|---|
| `map_col.fbx` | gfx meshes become the collision |
| `collisionedges.bin` | every edge is walkable, including steep slopes |
| `clipmaterials.json` | contents and surface flags default to 1 |
| `lightmaps.json` | one `lightmap0_secondary` page |
| `lightgrid.bin` | flat constant grid |
| `primarylights.json` | default sun with direction (0,0,0), so no directional light |
| `submodels.json` | any `*N` brush model entity crashes |

## Build steps
1. Write `map_gfx.fbx` and a simplified `map_col.fbx` to the conventions above.
2. Provide materials. Cloning a stock lit opaque material and swapping its colour map is the quickest start.
3. Add the scripts, animtree and images.
4. In the zone, list every image as `image,<name>` after the `>ipak,<map>` line.
5. Link, install as a mod, launch solo.

## Verification
- **Link round trip:** a generated floor and block read back through the T6 dumpers with exact bounds and scale.
  Collision facing matched stock `mp_studio`.
- **In game:** a small world of 531 surfaces and about 21,000 vertices rendered with correct winding, spawned on the
  floor and was walkable. With a spawner added, zombies spawned, chased, attacked and a round completed.
- **Not verified:** performance on a large map, baked lightmaps through this route, and shadows.

## Gotchas
1. **Every surface is the same grey.** The images reached the zone only as material dependencies, with no pixel data.
   **Fix:** list them explicitly after `>ipak,<map>`. The log should say `Created ipak X with N entries` with N above 0.
2. **World is black.** The T6 materials are missing. **Fix:** supply them and put stock material sources on the
   linker search path.
3. **World is flat and dark.** No `primarylights.json`, so the sun has no direction. **Fix:** author a directional
   primary light and set `sundirection` in worldspawn.
4. **Dynamic models are black.** Light-grid cells are absolute: x and y cell = (pos + 131072) / 32, z cell =
   (pos + 131072) / 64. Placeholder bounds put the play area outside the grid. Our fix was built but not tested in game.
5. **Rounds start but no zombies appear.** The start-zone spawner structs are only locations. **Fix:** add an actor
   entity with `script_noteworthy` set to `zombie_spawner`.
6. **Map stalls on a missing start zone.** Without a start-zone volume, the stock zone manager's spawner list loop
   never ends. **Fix:** give the start zone a real volume.
7. **Five "dropped unstageable assets" at link.** These are the world assets the BSP step builds itself. It is harmless.

## Open questions
- How does the single-cell world perform at the size of a stock map?
