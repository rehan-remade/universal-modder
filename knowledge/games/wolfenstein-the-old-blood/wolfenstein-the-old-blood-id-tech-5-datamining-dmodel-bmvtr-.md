---
kind: game
title: 'Wolfenstein: The Old Blood: id Tech 5 datamining (dmodel, bmvtr subtitles, chapter/challenge decls, Wolf3D nightmare
  levels, map export)'
game: 'Wolfenstein: The Old Blood'
games_also: []
game_version: 'Steam app 350080, buildid 616161, WolfOldBlood_x64.exe 28,457,040 bytes (shippingretail, OpenGL)'
platform: windows
engine: idtech
route: asset-only
tools: ['python 3.12 + numpy 2.x + Pillow', ffmpeg (H.264 re-encode), 'three.js 0.160.0 (offline viewer)']
anti_cheat: none (single-player, no online client)
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-02'
links: []
tags: [id-tech-5, datamining, unused-content, gltf, virtual-texture, subtitles, level-export]
---
# Wolfenstein: The Old Blood: id Tech 5 datamining (dmodel, bmvtr subtitles, chapter/challenge decls, Wolf3D nightmare levels, map export)

> Read-only datamining of The Old Blood (MachineGames, id Tech 5, with `tungsten` in its decl paths): every model,
> character, animation, texture, megatexture atlas, video, subtitle and map was exported to glTF/PNG/MP4/WebVTT/JSON and
> browsed in an offline three.js viewer. All of that stays private, on the machine it came from. Nothing ran in the real
> game (the game was never launched), so "used" means "referenced from shipped data", not "seen in game". Builds on the
> [Wolfenstein: The New Order note](../wolfenstein-the-new-order/wolfenstein-the-new-order-id-tech-5-resources-bmodel-bmd6mod.md)
> ("TNO" below): the layouts written down there are not repeated here.

## Setup
- Steam build 616161, Windows 11. No loader, nothing installed into the game folder; the folder's file list, sizes and
  dates were snapshotted before and compared after.
- Bink 2 videos were decoded by loading a copy of the game's `bink2w64.dll` from a temp folder, then ffmpeg → H.264.
  That copy and the decoded videos are private working files and never ship.

## Route and why
Asset-only: the exe's `.text` is SteamStub-encrypted, so the executable was used for `.rdata` strings only. Everything
else comes from `chunkN.index/.resources`, the virtual-texture `.pages` and the loose `.bik`/`.lang` files.

## How the game works (what we had to learn)
- **Same container and mesh formats as TNO** (`bmodel`, `bmd6model`, `bmd6anim`, `.bimage`). The TNO note has the
  `chunkN.index`, `bmodel` and `bmd6model` layouts; it still lists `bmd6anim` and `.pages` as open and doesn't cover
  `.bimage`, and this note doesn't write those layouts down either. The differences that matter are below.
- **Virtual textures:** TOB `.pages` use 4-byte child units (TNO's are 2-byte). Chapter atlases are 2048 pages wide, 12
  levels; the shared `_vmtr` is 1024/11. Model materials without `landPageFile` read `chunkN_vmtr.pages` where N is the
  chunk that holds the material decl (chunk0 → `_vmtr`).
- **`.dmodel` (pre-fractured breakables):** magic `\nLMD`; render surface = material string (u32le length), u32 0,
  u32 flags, u32 nv, u32 ni, nv × 32-byte vertices (bmodel layout), ni × u16 plain triangle list (not strips). Collision
  pieces are `textures/common/collision_*` + u32 1 + 3×4 matrix. The tail lists pieces: u32 n, then n × (string, u32
  hash, u32 0, u32 first vertex, u32 last vertex), then u8 0 or u8 1 + `<name>_base`. Convex hull blocks (SoA) were not
  decoded.
- **`.bmvtr` (voice tracks):** `#VTR`, u32be language count (4: english, french, italian, spanish; no Russian voice),
  per language char[16] name + u32 size + u32 offset; each track block starts and ends with `#RTV` and holds u32le
  strings (tags, `#str_empty`, the subtitle key, `vo/<lang>/...` path). The first byte looks like a version: TNO's files
  start `"VTR` and `"RTV` (0x22 instead of 0x23).
- **Video subtitles** are `.lang` keys `#str_video_<name>` with `[t]` second markers and `[eng]/[ger]` speech-language
  tags; location title cards are `_location<N>_title/_desc` with times in `_location_info`.
- **Locations:** `generated/decls/chapter/dlc1_cNN.decl` (map, layers, spawnSpot, `nextVariationId` = the next chapter),
  `challengeinfo/info/*.decl` (mapPart, mapSpawn, layers), `mapinfo/` (loading videos per layer). Map file numbering
  is shifted against chapters: the prologue (c00) and chapter 4 share `dlc1_c01_04`, chapter 1 is `dlc1_c02p1`, etc.
- **`_world.bmodel`** of a map uses only `maps/.../*.decl` megatexture materials; its UVs are atlas UVs (divide by the
  exported level's uv_scale). `dlc1_c01_04` has two atlases on one UV layout (`_s1` prologue/chapter 1, `_s4` chapter 4).
- **Per-area environment:** `generated/decls/env/maps/<map>/areaN.decl` → inherit a named look (fog, colour correction,
  cubemap); worldspawn has no envSettings.
- **Wolfenstein 3D "nightmare" levels** are ordinary geometry (`models/mapobjects/dlc1/oldgame/<chapter>/oldgame_geo`)
  placed far outside the playable area of the same map file; enter `*_gen_enternightmare`, start `*_gen_player_start`,
  exit `*_gen_player_exit`.
- **Entity transforms:** `spawnOrientation` rows are the entity axes; with P the (x,y,z)→(y,z,x) permutation, the glTF
  rotation is P·Mᵀ·Pᵀ. Positions in inches (× 0.0254 → metres).

## Build steps
Scripts are in the private datamining folder's `tools/` (unpublished), and their output stays outside any repo:
extract archives → `bimage_all.py` (textures) → `gather_materials.py` (material channels from VT pages) →
`export_models.py` (bmodel, dmodel, md6, md6def characters, anims) → `export_maps.py` → `locations.py` →
`build_catalog.py`; `serve.py` serves the viewer with HTTP Range and no-store caching on 127.0.0.1.

## Verification
- Round-trip checks: every `.bimage` decoded with byte-exact record sizes; every `.dmodel` and `.bmvtr` parsed to EOF.
- Visual: Helga's character GLB with an alias animation (55/55 bones matched); every location opened automatically in
  the viewer with no console errors, world inside the camera frustum, screenshots saved.
- NOT verified: anything in the running game (never launched), whether debug `idTarget_Print` entities print in retail.

## Gotchas
1. **Symptom:** all three mesh formats render inside-out. **Cause:** triangles are stored clockwise; the axis permutation
   is even, so it does not fix them. **Fix:** per surface, vote the face normal against the vertex normals and flip the
   whole surface when most disagree.
2. **Symptom:** `.bmvtr` parse fails on `#RTVS`. **Cause:** the `S` is the first hash byte; the magic is `#RTV` at both
   ends of the block. Also `#str_empty#` is not a token: `#` is the next string's length byte. **Fix:** match only the
   4-byte magic and read each string by its length.
3. **Symptom:** 20 md6def characters come out empty. **Cause:** they use a single `mesh "..."` in `init` (and
   `inherit "creatures/rat.md6"`), not `multimesh`. **Fix:** accept both.
4. **Symptom:** many mesh materials `_lg` have no decl. **Cause:** build region `ww` ships the high-gore `_hg` decls.
   **Fix:** fall back `_lg` → `_hg`.
5. **Symptom:** entity reference counts are zero. **Cause:** `targets` is kept as a decl block
   (`{num, item[0], item[1]...}`), not a list. **Fix:** flatten the dict values.
6. **Symptom:** the browser tab dies after a few maps. **Cause:** world GLBs reach 300 MB and the instance cache kept
   every map's models. **Fix:** dispose world, instances and atlases on map change.
7. **Symptom:** `.dct` images "broken data stream". **Cause:** JPEG scan stored without 0xFF00 byte stuffing. **Fix:**
   re-stuff FF bytes in the scan up to the final FFD9.

## Assets
None generated; everything is decoded game data, kept private on the author's machine, outside any repo and never
shared. Anyone else decodes it from their own install.

## Open questions
- `.baas` navigation, `.bcm` polygons (only the AABB at 0x21 and 17-byte vertex records are known), dmodel convex hulls.
- `.proc` `binaryModels` list (func_binarymodel_*) → which `_world` surfaces belong to which binary model.
- 44 static-pose animations whose constant block does not fit the TNO header layout.
