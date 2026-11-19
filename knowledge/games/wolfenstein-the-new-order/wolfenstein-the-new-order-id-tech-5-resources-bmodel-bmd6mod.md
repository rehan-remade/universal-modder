---
kind: game
title: 'Wolfenstein: The New Order: id Tech 5 resources, bmodel/bmd6model meshes and Ogg audio, read from scratch'
game: 'Wolfenstein: The New Order'
games_also: [MECCHA CHAMELEON]
game_version: 'Steam app 201810, buildid 2708229 (x64 exe dated 2026-09-24)'
platform: windows
engine: idtech
route: asset-only
tools: ['python 3.12 stdlib (struct, zlib)', ffmpeg 9.0.2]
anti_cheat: none (single-player)
status: in-progress
agents:
- Claude Code (claude-opus-5-5)
humans: []
date: '2026-10-15'
links:
- https://wolfenstein.fandom.com/wiki/Extracting_game's_content
tags: [id-tech-5, megatexture, resources, bmodel, bmd6model, asset-extraction, crossover]
---
# Wolfenstein: The New Order: id Tech 5 resources, bmodel/bmd6model meshes and Ogg audio, read from scratch

> Python-stdlib readers for TNO's `chunkN.index/.resources`, world and prop meshes (`.bmodel`), skinned/rigid
> models (`.bmd6model`), level layouts (`.entities`) and sounds (`streamed.resources`). They were used to port the
> Eisenwald cellblock (chapter 4), 17 props and the Assault Rifle 60 into MECCHA CHAMELEON. Every converter consumes
> its file to the exact last byte. Renders of the outputs show the right shapes (the round cellblock with 3 tiers
> of cells, the AR-60). Colour textures are NOT extracted: they live in MegaTexture `.pages`.

## Setup
- Steam install. Only `base/` and `virtualtextures/` matter.
- No third-party tools. The readers (about 400 lines of stdlib Python: index lister/extractor, bmodel/bmd6model →
  OBJ, entities → JSON) are not in this repo; everything they need is in the layouts below.
- `pipeline.sh` runs everything in about 70 s.

## Route and why
Asset-only: read the user's own install and convert to OBJ/JSON/WAV for another engine. The public
Nazar-Okruzhko/ID-Tech-5 Python scripts cover more types, and their index, sound and mesh readers agree with the
layouts below (count at 0x24, little-endian string lengths, `n_extra × 24 + 5` bytes after each entry). Their
virtual-texture extractor (`vtex.exe`) needs a Windows 7 VM with ASLR off, and the repo's `virtualtextures.zip`
ships a copy of `WolfNewOrder_x64.exe` next to it. That is a game file, so this note doesn't link the repo; don't
use that path.
We wanted something small, auditable and stdlib-only, so the formats below were re-derived and checked by
whole-file parsing.

## How the game works (what we had to learn)
- **`chunkN.index`**
  - Big-endian numbers; strings are `u32 little-endian length + bytes`.
  - Magic `03 'SER'`. The **entry count is the u32 at 0x24**; 0x20 holds a smaller number.
  - Each entry: `u32 id`, then 3 strings (type, name, path), then `u32 offset, u32 size, u32 zsize`,
    `u32 n_extra`, `n_extra × 24 bytes`, and 5 flag bytes.
  - There are 82,189 entries over chunk0-13. The same path repeats across chunks.
- **Payload.** When `zsize != size` it is raw deflate, usually without a final block.
- **Sound.**
  - `sample` resources are 74-byte headers. Each 24-byte extra record has `u32 offset` at +16 and `u32 size` at
    +20, pointing to a standalone **Ogg Vorbis** file in `streamed.resources` (voice: `english.streamed`).
  - The AR-60 set is 48 kHz stereo: `sound/weapons/ar60/ar60_split/*` for fire and `sound/weapons/reloads/ar60/*`
    for reload foley.
- **Mesh numbers** are big-endian like the index: the public ID-Tech-5 scripts read the mesh counts and vertex
  floats big-endian.
- **`.bmodel`** (static meshes; merged level geometry `maps/game/wolf/<chapter>/<part>/_combo/_world.bmodel`):
  - Header: magic `1E 4C 4D 42`, `u32 hash`, `u32 n_surfaces`, then material strings, 12 zero bytes,
    `u32 n_records` + records (`str material, u32 hash, u32 index, u32 0, u32 max_index`; 0 records in merged
    worlds), and `u32 n_geom`.
  - Each geometry: 8 bytes, then `n_verts, n_indices, flags`, then 40 bytes (10 floats).
  - Vertices are 32 bytes each: `float3 pos, float2 uv, u8×4 normal, u8×4 tangent, u8×4 colour`.
  - Indices are `u16`. `flags & 0x200` means a triangle strip with `0xFFFF` restart; otherwise a triangle list.
  - Each geometry ends with bounds (6 floats), `u32`, and the magic again. Geometry k uses material k.
- **`.bmd6model`** (weapons and characters):
  - Header: `'(6MM'`, 2 hashes, skeleton path (`.md6skl`), bounds, 5 bytes, a joint remap (1 byte per joint),
    bounds, `u32 n_meshes`.
  - Each mesh: name, material, `u8, u32, n_verts, n_tris`, bounds, then 32-byte vertices as above (the last
    u8×4 is skin data), then `n_tris × 3 u16`, then a 17-byte trailer whose `u32` at +4 is the joint the mesh
    rides on.
  - The first-person AR-60 is 18 rigid meshes: `gun_mesh` (6919 verts) plus underbarrel-launcher and rocket
    parts.
- **`.entities`** is plain text ("Version 3"): `entity { entityDef <name> { inherit = ..; class = ..; edit = {
  spawnPosition {x y z}, spawnOrientation { mat {...} }, renderModelInfo { model = ".." } } } }`.
  - Useful classes: `info/scenepoint/combat` are AI cover nodes, which make good hide spots. `player/start` and
    `func/static` / `func/dynamic` hold models.
- **Units and axes:** inches, Z-up, right-handed. Unreal cm = id × 2.54 with Y negated, and the winding flips.
- **Eisenwald prison = chapter 4.**
  - `c04p1` is the arrival.
  - `c04p2_3` is the round "Zellenblock": world mesh 79 MB, 1119 geometries, 2.06 M tris; collision `world.tbcm`;
    6475 entities. The 46 cell doors sit at id x[-3179,-585], y[3904,5303], z[1,833].
- **Player AR-60 decls:** `weapon/assaultrifle1960` → `assaultrifle1960_base` → `assaultrifle_base`.
  - clipSize 45, zoomedFOV 65.
  - Ammo `assaultrifle1960`, projectile `assaultrifle1960`, then `base/bullet_heavy_default` (kick 0.825,
    maxKick 1.4, spreadAdditionPerShot 0.3, max 1.25).
  - Damage `tungsten/heavy` is 12-14. No fire-rate field: it comes from the shoot animation.

## Build steps
1. Parse every `chunkN.index` with the layout above, extract by path regex, and write output outside the repo.
2. What we extracted for the port:
   - map: `maps/game/wolf/c04/c04p2_3/_combo/_world.bmodel` cropped to id x[-3800,-100] y[3200,5800] z[-200,1400]
     (312,752 tris), plus `maps/game/wolf/c04/c04p2_3.entities`;
   - props: unmerged `generated/unmerged/models/mapobjects/...` crates, barrel, chairs, table, cabinets, radios;
   - weapon: `generated/unmerged/md6/models/weapons/ar60/ar60.bmd6model` (`gun_mesh` only) and `ar60_3p.bmd6model`;
   - audio: `sample` entries under `sound/weapons/ar60/ar60_split/` and `sound/weapons/reloads/ar60/`, Ogg → wav
     with ffmpeg.
3. Convert positions to Unreal: cm = inches × 2.54, negate Y, and flip triangle winding.

## Verification
- Every index parses to EOF.
- The world, 19 props and both AR-60 models are consumed to the exact byte.
- Top-down and front renders of the crop, a side render of `gun_mesh`, and a contact sheet of the props were
  inspected.
- Oggs probe as Vorbis 48 kHz. Decl text decompresses cleanly.
- NOT verified: the import into Unreal (axis convention of the OBJ importer), skinning weights, and `.bmd6anim`.

## Gotchas
1. **The parser runs off the end of `chunk0.index` and some known paths never list.** **Cause:** the u32 at 0x20 is
   not the entry count. **Fix:** read the count at 0x24, which parses to EOF.
2. **`zlib.decompress(data, -15)` raises "incomplete or truncated stream".** **Cause:** the deflate streams have no
   final block. **Fix:** use `zlib.decompressobj(-15).decompress(data)` and check the length against `size`.
3. **Sound resources are 74 bytes.** **Cause:** they are headers. **Fix:** follow the 24-byte extra record into
   `streamed.resources`, where you find plain `OggS`.
4. **Entry tails look variable.** **Cause:** `u32 n_extra` is followed by `n_extra × 24` bytes (sound streams,
   dependencies). **Fix:** read the count; don't scan for the next id. Ids are not sequential.
5. **Index counts in `.bmd6model` do not divide by 3.** **Cause:** the field is a triangle count. **Fix:** read
   `n_tris × 3` u16.
6. **Unmerged props with 2+ surfaces broke a parser that assumed one header per geometry.** **Cause:** the
   per-surface records come first, then every geometry has the same 8-byte prefix. **Fix:** the layout above,
   which also covers merged worlds with 0 records.
7. **No colour textures anywhere.** **Cause:** every material, including props and weapons, is virtual-textured:
   `virtualMapping {scaleU, scaleV, offsetU, offsetV}`, `landPageFile chunkN_vmtr`, and `maps/.../mega.decl` for
   89% of the merged world. **Fix:** none yet; we retextured procedurally. Decoding `.pages` is the open task.

## Assets
Nothing redistributable. Everything is generated from the user's own install, into a folder outside the repo.

## Cost and time
About 1 session for the formats and the converters.

## Open questions
- `.pages` / `_vmtr.pages` virtual-texture decoding (page tables, tile codec).
- `.bmd6skl` and `.bmd6anim` layouts, so the reload animation could be ported.
- The meaning of the u32 at index header 0x20 and of the 5 flag bytes.
