---
kind: game
title: 'Map import toolkit: Shadow of War / Shadow of Mordor file formats and the tools we wrote'
game: 'Middle-earth: Shadow of War'
games_also: ['Middle-earth: Shadow of Mordor']
game_version: 'Shadow of War Steam build 3095001 (exe 1.0.8874.0), Windows 10 22H2; Shadow of Mordor Steam copy as the source'
platform: windows
engine: unknown
route: data
tools: ["Python 3.12 + numpy/Pillow", "C# 5 GADB reader-writer via PowerShell Add-Type", "Recast v1.6.0 core in an own CLI (w64devkit g++)", "TagTools (TAG0 reader/writer, Python 3 port)", "QuickBMS + aluigi shadow_of_mordor.bms 0.4", "texconv (DirectXTex)", "Ghidra 12.1.4 (analysis only)", "w64devkit GCC 16.2 (trace plugin)", "Blender 4.2.3 (headless previews)"]
anti_cheat: "none; single-player, offline. Tools only read the user's own game files and write a mod archive + database; the exe file is never modified."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["DeimozZarco"]
date: '2026-10-29'
links:
  - "knowledge/games/middle-earth-shadow-of-war/map-import-shadow-of-mordor-udun-as-a-new-region.md"
  - "knowledge/games/middle-earth-shadow-of-war/goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md"
  - "https://github.com/recastnavigation/recastnavigation"
  - "https://github.com/blueskythlikesclouds/TagTools"
tags: [toolkit, file-formats, ltar, bundles, objres, gadb, prfb, ltmi, texr, wdsc, terrain, havok, tag0, hknp, hkai, recast, cadb, volm, uiwd, uis, kit-copy, trace-plugin, map-import, lithtech, firebird]
---

# Map import toolkit: Shadow of War / Shadow of Mordor file formats and the tools we wrote

> The ~150 tools behind the [Udûn map import](map-import-shadow-of-mordor-udun-as-a-new-region.md), described so
> another agent can rebuild them: what each one does, the format facts it relies on, how it works and how it was
> checked. The tools themselves stay in the author's private project folder (they are tied to a private mod and its
> paths). Their behaviour is all written down here. Most are small Python scripts (numpy) with one job each,
> chained by a per-build script. Format layouts were read from the loaders in the Steam build's exe (Ghidra, function
> names given) and proven by byte-identical round trips on stock files.

## Disclaimers
- The mod these tools built is **personal** (the author's own install) and is **not shared**: its archives hold
  converted Shadow of Mordor and Shadow of War assets, so anyone else builds them from their own copies. The hope is
  that the framework helps others. **Only the Steam build 3095001 on Windows was tested.** Formats or exe addresses
  may differ on other stores, platforms or versions.
- No game files, extracted assets or decompiled code are here; layouts are described in our own words.

## Setup
- Python 3.12 with numpy (+ Pillow for images). C# 5 code compiled in Windows PowerShell 5.1 with `Add-Type` (no SDK
  needed) for the game database. w64devkit g++ for the Recast CLI and gcc for the trace plugin.
- Third party: Recast v1.6.0 core (zlib licence); TagTools' `TagTools.py` (MIT, Python 2) ported to Python 3;
  QuickBMS + `shadow_of_mordor.bms` 0.4 for listing / extracting stock `.arch06` (Oodle) archives; texconv for
  texture decode / encode; Ghidra for reading loaders. Credits and links are in the main note.
- Related notes: the [Goblins note](goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md) (game.gamedb), the
  [Packet Loader note](packet-loader-mods-without-packet-loader.md) (`.bndl` rewrites) and the
  [Havok HKX technique note](../../techniques/havok-hkx-chunked-packfile-family.md) (Havok versions, `SDKV`, the
  tagfile family). Public code for some of the same Havok structures: DSMapStudio's HKX2
  (`hknpCompressedMeshShapeData`, `hkcdStaticTreeCodec3Axis4`, and an `hkaiNavMeshBuilder` that turns Recast output
  into an `hkaiNavMesh` for Dark Souls III): <https://github.com/soulsmods/DSMapStudio>.
- Coordinates: game units are **centimetres**, y up. Havok data is in **metres**. SoM Udûn → our world offset is
  **(+8846, −16203, −888) cm**.

## Route and why
Principles that kept ~90 builds stable:
1. **Every writer round-trips first:** read a stock file, write it back unchanged, and compare bytes (or every value,
   for Havok tagfiles) before writing anything new.
2. **Append, don't reorder:** new objects, records, instances and strings go at the end, so stock indices keep their
   meaning.
3. **Same-length renames in place** (world paths, quest names, Lua conditions), so sizes and offsets don't move.
4. **Calibrate on stock data before applying a rule** (e.g. how high stock spawners sit, how stock compressed meshes
   lay out their trees).
5. **One build script per test build** that renames the previous build's tree (`uNN_arch`) and applies one change;
   an installer per build that refuses unless the installed state is the previous build.

## Formats at a glance
| file | SoM (Udûn) | SoW | our tools |
|---|---|---|---|
| archive `.arch05/.arch06` | LTAR v3 (zlib chunks) | LTAR v4 (Oodle; mods: stored) | `ltar3.py`, `ltar.py`, `ltar_list.py`, QuickBMS |
| bundle `.bndl` + `.embb` | `.bndlxml05` + BNDL v4 data | BNDL v6 index + EMBB v5 data | `som_bndl4.py`, `embb.py`, `bundle.py`, `patch_bndl_size.py`, `bndl_index.py` |
| object list `.objres` | OBJR v9 | OBJR v13 | `objl.py`, `objres_list.py`, `objres_add.py`, `add_worldmap_icons.py`, `kit_copy.py`, `som_world_objects.py` |
| embedded / game database | GADB v17 | GADB v17 (`game.gamedb`) | `gadb.py`, `GameDb.cs` + edit classes |
| prefab `.inst` | PRFB v5 | PRFB v8 | `prfb.py`, `prfb_geom.py`, `prfb_convert.py` |
| material `.mat` | LTMI v4 | LTMI v8 | `ltmi.py`, `mat_catalog.py`, `mat_convert.py` |
| texture `.tex` | TEXR v3 (+ `.tex0`) | TEXR v8 | `som_tex.py`, `tex_pipeline.py`, `tex_fix.py` |
| scene list `.wldclnt` | WDSC v5 | WDSC v9 | `wdsc.py`, `wdsc_add.py`, `scene_sink.py` |
| terrain `.terrain` + tiles | none (mesh ground) | TERR v9 + L16 TEXR tiles | `terrain*.py`, `ground_*.py` |
| collision | Havok 2012 binary tagfile in objres chunk 0xb9e81cf3 | Havok 2016 TAG0 (hknp) in objres WorldPhysics | `hk2012.py`, `som_collision.py`, `tag0.py`, `som_to_hknp.py`, `simd_tree.py`, `som_props_hknp.py`, `hknp_mesh.py`, `hkhf.py` |
| navmesh | `.path` PATH v21 (LithTech) | `.hkai` (HKAI + TAG0 hkaiNavMesh) | `navmesh_build.py` + `recast_cli.cpp`, `hkai_patch.py`, `hkai_winding.py` |
| parkour | CADB v1 + per-area `.cntx` | CADB v3 | `cadb.py` |
| volumes | VOLM v8 | VOLM v8 | `volm.py`, `lighting_patch.py` |
| clutter | chunk 0xc3685e5b v1 | same | `clutter.py` |
| map shapes `.uis` / `.uiwd` | | UISH v3 / UIWD v4 | `uiwd.py`, `minimap_build.py`, `zonemap_build.py` |
| world Lua `.scripts` | SCRL in objres | `SCRI` chunk + objres SCRB/ONLS | `patch_bg_scripts.py`, `kit_copy.py`, `quest_port.py` |

## How the game works (format reference)

### Hash
- **sowhash** (the Goblins note's AttrHash; exe FUN_140C6DA00): `h = h*0x397 + (signed byte)map[c]`, map = a
  256-byte case-fold table in the exe. It keys database attribute names, record lookups, object names (OBJL hash,
  VOLM lookup, SCRB, ONLS), Lua section names, bundle sections and surface tags. Recover unknown attribute names by
  hashing every NUL-terminated string in both exes and matching.
- **Surface tag** of a `Surfaces/Surfaces` record = `(v + (v >> 16)) & 0xFFFF`, v = sowhash(record name).

### LTAR archive (`ltar.py`)
- Header: `'LTAR'`, u32 version 4, u32 namesSize, u32 folders, u32 files, 28 zero bytes. Then the names blob (offset 0
  = empty string), then:
  - files: 30 B each = u32 nameOff, u64 offset, u64 zsize, u64 size, u8 0, u8 flags (0 = stored; aluigi's script
    reads these two bytes as 1 and "usually 9" on stock compressed entries, whose data is `[u32 zsize][u32 size]`
    Oodle chunks, each 4-byte aligned from the entry's start);
  - folders: 16 B each = u32 nameOff, i32 firstSubFolder, i32 nextSibling, u32 fileCount (DFS order; files in
    folder order);
  - data.
- The root holds `archivepatchloosefiles.txt` = u32 1, u32 namesSize, full paths, u32 count, then count ×
  (u32 sowhash(path), u32 nameOff), sorted by hash. That index is what lets an archive override bundle-only files.
- SoM's LTAR v3 has the same table; compressed data = chunks of `[u32 zsize][u32 size][zlib]`.

### Bundles (`bundle.py`, `embb.py`, `som_bndl4.py`)
- `.embb`: `'EMBB'`, u32 5, u32 namesSize, u32 count, names (NUL-terminated, padded to 4), u32 nameOff[count],
  then per file u32 size + data (unaligned).
- `.bndl`: `'BNDL'`, u32 6, u32 namesSize, u32 tableOff, u32 count, u32 size[count], names, bundle-type string
  (padded to 4), u32 nameOff[count]. A `.bndl` may list zero-size entries that the `.embb` doesn't hold (stock world
  sections list an empty `.wldmsh`): keep the original `.bndl` when sizes don't change.
- SoM BNDL v4 data: `'BNDL'`, u32 4, u32 namesBytes, u32 dataStart, 0, 0, u32 count, names, type string, then count
  × (u32 name offset, u32 size, data).

### OBJR object list (`add_worldmap_icons.py` is the reference reader / writer)
- `'OBJR'`, u32 13 (SoM 9), u32 hash, u32 chunkCount, then chunks `[u32 hash][u32 size][payload: 4cc, u32 version, …]`.
  Chunks: OBJL, GADB (ObjectDB), VOLM, CADB, SCRB, ONLS, KEYF, SFXS, CAWR, PFDG, clutter 0xc3685e5b, physics
  0xb9e81cf3 and more. Writing = header + chunks in order.
- **OBJL v5:** u32 1, u32 objCount, u32 classBytes, u32 nameBytes, u32 hierBytes, the three NUL-string blocks, u32 ?,
  u32 objCount, then 50-byte records: u32 classOff, u32 nameOff, **u16 parent** (= byte offset of a `hier` string =
  the kit's prefab instance name), u32 ObjectDB index, f32 pos[3], f32 quat[4] (x, y, z, w), u32 0, u32 sowhash(name).
- **ObjectDB** = an embedded GADB (category 0, `ObjectRec` records; one layout run per property set).

### GADB (`GameDb.cs`, `gadb.py`)
- Header: `'GADB'`, u32 0x11, u32 heapLen, u32 categoryCount, u32 namedCount, u32 unnamedCount, u32 valueWordCount,
  u32 layoutCount, u32 hash, u32 0, u32 0x2C, u16 len + path (embedded DBs: empty path, heap at 0x2E + pathLen). Then
  the heap (strings / blobs, values point at offsets), then layouts (15 B each: u32 nameHash, u32 hashOfSortedSlot,
  u8 attrIdx, u8 sortedIdx, u8 type, u16 valueCount, u16 firstValueIndex), u32 0, u32 categoryCount, then categories
  and records.
- Record: `[u32 name]`, header `u16 valueCount | u8 attrCount | u8 layoutLo`, type word `0x08000000 (named) | layoutHi`,
  then the values. Links = `categoryIndex << 20 | recordIndex`; FFFFFFFF = null. Heap kinds 0x04 / 0x44 = strings,
  0x07 / 0x08 = float blobs.
- **Bools (kind 0x01) are bits of the record's first value word, and the layout's `first` is a bit index.** Dumpers
  that read `values[first]` print garbage; repackers that re-lay bools as slots scramble them.
- Records must stay sorted the way the game binary-searches them (see the Goblins note).

### PRFB prefab (`prfb.py`, `prfb_geom.py`)
- Header 14 × u32: magic, version, hash (= sowhash of the prefab's own path), nA, s4, s5, nPiece, nB, blobSize, s9,
  s10 (decl counts), s11 (arena size), nStr, strBytes. Then nA records + nB records (v5 36 B / v8 44 B: key, (v8: u32
  −1), base, count, parent, f32 dist, (v8: f32 0), f14, s18, s1c, **b20** = leading shadow-pass-only submeshes, b21,
  b22), geometry (u32 g0, vbBytes, ibBytes, vb, ib, streams, submeshes 40 B v5 / 52 B v8), materials blob, nPiece ×
  80-byte render pieces (LOD key, bbox, draw distance), name strings.
- Vertex element = u32 `usageIndex << 24 | usage << 16 | type << 8 | stream` (type 2 float3, 0xC half4, 0xA half2,
  4 ubyte4; usage 0 pos, 1 normal, 2 tangent, 3 binormal, 4 texcoord, 5 colour). SoM interleaves each range; SoW stores
  per submesh range a block of stream-0 (positions) then a block of stream-1 (the rest) at the same byte offsets.
- A scene instance draws the record whose key = its `variant`.

### LTMI material (`ltmi.py`)
- v4: `'LTMI'`, u32 4, u32 dataBytes, u16 n1, u16 n2, u32 s1, u32 s2, u16 len + shader path, data, params.
  v8 adds a u32 per-shader hash after the version. Params to EOF: u32 type, u16 len + name, u32 offset into data
  (type 8 = SurfaceRecord string, 0x00010001 = texture path, others numeric).

### TEXR texture (`som_tex.py`)
- `'TEXR'`, u32 version, u8 log2 W, u8 log2 H, u8 0, u8 levels, u8 1, u8 fmt, u16 0, u16 pathLen, path, then v3: 3 bytes
  + DDS (a `.tex0` path = the top mip lives in `<name>.tex0`); v8: u8 3, u16 W, u16 H, u16 1, u8 levels, u8 1, u8 DXGI,
  7 × 0, u8 stream, u8 0, u8 sRGB, u8 stream, u8 x, u8 0 + DDS.
- fmt 0 BC1 (DXGI 71), 2 BC3 (77), 4 SoM / 5 SoW BGRA8 (87), 7 BC7 (98). Self-contained SoW textures: path = own path,
  stream 0, mips to 1×1.
- Channel conventions: SoW `_n` has B = 255 (X in A, Y in G); SoW `_s` R = reflectance class (170 dielectric,
  210–230 metal), G ≈ 255, B = roughness, A = blend height; SoM `_s` B = gloss.

### WDSC scene list (`wdsc.py`, `wdsc_add.py`)
- `'WDSC'`, u32 9 (SoM 5), 9 × u32: nSec, nA, nInst, nC, nGroups, nGroupMats, nPoly, nPolyPts, strBytes; string block;
  mesh groups (u32 nMat, u32 meshPathOff, u32 ?, nMat × u32 material offsets).
- Then nInst × 76 B: bbmin[3], bbmax[3] (world), pos[3], quat[4], scale, u32 flagB, u8 flagC + 3 pad, u32 **variant**
  (= LOD-set key), f32 lodScale (draw distance), u32 prefabPathOff.
- Then per sector: u32 nA, nPoly, nC, nA × 32 B bounds, polygons (u8 n + n × float3), nC index groups (u32 id, u32 count,
  indices), then a trailer copied unchanged.
- To add instances: append rows, append their indices to sector 0's first index group, append new paths to the
  string block.

### Terrain (`terrain.py`, `terrain_quadtree.py`, `terrain_write.py`)
- TERR v9: per block u32 gridX, gridZ, origin[3], quat, size, heightRange, …, material + base texture strings, cells
  (u32 flags, plus normMin / normMax / tile index when not empty), tile list.
- Cells are a pre-order walk of gridX × gridZ root quadtrees: 0x20 empty, 0x40 children only, low nibble = child mask
  (child k = quadrant u = k&1, v = k>>1). Tile 0 = coarse 260² (256 + borders), detail tiles 68² (64 + borders).
  Height = origin.y + raw/65535 × heightRange. Image column u = 0.5 + (x − origin.x)/size.x, row v likewise for z.
- **Collision is separate** (next section): edit both, and widen cell bounds so edited patches aren't culled.

### Havok collision
- **SoM (2012)** binary tagfile (`hk2012.py`): magic CAB00D1E D011FACE, version 4; LEB128 zigzag varints; items 1 file
  info, 2 class, 3/4 object, 5 back-reference, 6 null, 7 end; objects = class index + member-presence bitfield + present
  values; member types 0–10, 0x10 array, 0x20 tuple.
- SoM objres chunk 0xb9e81cf3 (`som_collision.py`): u32 nBodies, u32 nPrefabs, body ids (sowhash of object names), u16
  prefab index per body, 224 physics-prefab entries, then the tagfile. Root `hkpStaticCompoundShape` with 3,311
  instances already in world space (metres).
- Compressed mesh (`hkcdStaticMeshTree`, config `<u32, u64, 11, 21>`, **same in 2012 and 2016**): per section packed
  vertices u32 = x 11 | y 11 | z 10 bits, position = codec offset + q × codec scale; shared vertices u64 = 21 | 21 | 22
  bits over the tree domain; primitive index < numPackedVertices = packed, else shared; indices[2] == indices[3] →
  triangle, else quad (0,1,2)+(0,2,3); data runs value >> 8 = palette index → surface tag. Per-section BVH =
  Aabb4BytesCodec (per axis byte = min nibble << 4 | max nibble, child box = parent shrunk by nibble² × extent / 226;
  odd data = internal, even = leaf).
- **SoW (2016) TAG0** (`tag0.py` on TagTools): sections SDKV (20160200), DATA, TYPE (TNA1 / TBDY in SoW files; TagTools
  writes TNAM / TBOD), INDX (ITEM / PTCH). Every ITEM and PTCH type needs a THSH hash.
- hknp compressed mesh: same mesh tree + a **hkcdSimdTree** (`simd_tree.py`): 112-B nodes = four AABBs (lx, hx, ly, hy,
  lz, hz × 4 floats) + data[4]; node 0 empty sentinel, node 1 root; internal child = index << 1, leaf = (key << 1) | 1
  with the primitive's exact AABB; unused slots inverted boxes. Key = section << 8 | primitive << 1 (≤ 127 primitives
  per section).
- Compound (`hknpCompoundShape` + `hknpDynamicCompoundShapeData`, Codec32 tree): min.w bits = 0x3f000000 | parent,
  max.w bits = child1 << 16 | child0, leaf = instance << 16; instance transform col0.w bits 0x3f000062 (translated),
  col3.w bits 0x3f000000 | leaf node.
- `hknpConvexPolytopeShape` (props): vertices with w bits 0x3f000000 | index, padded to a multiple of 4; outward
  planes; faces (u16 first, u8 count, u8 minHalfAngle = floor(255 × θ/π)) + u8 indices CCW; connectivity
  (vertex → outgoing edge, per index slot the twin edge); convexRadius 0.01; `maxAllowedPenetration` as a half float;
  rotation and scale baked into vertices, instance translation only. Rel-arrays must sit right behind their shape in
  DATA.
- **Heightfield** (`hkhf.py`): `hknpHeightFieldShape` 513² u16 samples + min/max quadtree, int-to-float scale,
  heightScale, inside a compound instance. Read heights through the Havok fields (`true_grid`), never through a fit.

### Navmesh `.hkai` (`hkai_patch.py`)
- `'HKAI'`, u32 3, u32 0xFFFFD00D, u32 size, one TAG0, u32 0xFFFFDEAD. Root variants: `hkaiNavMesh` (faces 16 B:
  startEdgeIndex, startUserEdgeIndex, numEdges, numUserEdges, clusterIndex; edges 20 B: a, b, oppositeEdge,
  oppositeFace, flags, padding, userEdgeCost; vertices in metres; faceData / edgeData striding 1; aabb; clearance
  caches), generation settings, string table, user-edge array (AI context-action links).
- **Faces wind counter-clockwise seen from above.** New faces need the clearance caches extended (faces at or above
  `uncalculatedFacesLowerBound` are computed on demand).

### CADB parkour (`cadb.py`)
- `'CADB'`, u32 version (SoW reads 2 and 3; SoM writes 1), u32 nTypes, nEdges, nB, nC, nGroups; types = sowhash of
  `Character/Models/ContextActions` record names; edges 52 B (p0, p1, normal, v2: u32, 128-bit type mask); B 16 B; C 32 B;
  groups 52 B (u32 id = sowhash(object name), AABB, first edge, count, …). The world group is `WorldInitializer`
  0x6B9D05D0.

### VOLM volumes (`volm.py`)
- Header 68 B (`'VOLM'`, u32 8, sizes 68 / 72 / 48 / 40 / 12, counts, hash, nPlanes, nVerts, nFaces, volumeDbBytes).
  Then planes (n, d), per-face vertex counts (u8), vertices, types (u32 sowhash(name), u32 count, char[64] name),
  hulls (AABB + first plane / plane count / first face / first vertex), object volumes and world brushes (48 B: hull,
  type index, VolumeDB record, 0, pos, quat, scale), a lookup sorted by sowhash(object name) with a sentinel, and the
  VolumeDB (a small GADB: one record per brush, e.g. AreaBrush area name attr 0xF36A0E56).

### Clutter (`clutter.py`)
- Chunk 0xc3685e5b v1: header 20 B (version, strBytes, u16 nMesh, nInst, nElem, nVB, u32 geometry bytes), material
  paths, meshes (material, elements, vertex buffers, u16 indices), then nInst × 40 B kd-tree nodes (pos, quat, scale,
  u16 hi / lo children, u16 first mesh, u16 mesh count; split axis = depth % 3). An "empty" chunk (all counts 0) is valid.

### Map shapes (`uiwd.py`, `minimap_build.py`)
- `.uis` UISH v3: 36-B header (`'UISH'`, 3, nSections, dataBytes, nSections, bounds min x, min z, max x, max z),
  nSections × 28 B (u32 sowhash(MapCanvas object name), index, offsets, vertex count), triangle lists of (x, 0, z),
  trailer of canvas names.
- `.uiwd` UIWD v4: 40-B header (counts + bounds = the zone map's world ↔ map conversion), sections 24 B, entries 29 B
  (u8 type, 3 × u32, f32 w, x, y, z; type 1 = travel point icon), a blob of outline loops (f32 point count + points,
  closed), strings.

### World Lua and bindings (`kit_copy.py`)
- `.scripts` = `'SCRI'`, u32 1, u8 1, u32 len, plain Havok Script: prototypes, then `-- IMPLEMENTATION` and
  `local section_<hex(sowhash(.scripts path))> = { … }`, ending `_G.loadedresource = section_<hash>`.
- **SCRB** (`'SCRB'`, 1, strBytes, nE2, nE3): E3 = (sowhash(object name), first E2, count) sorted by hash; E2 16 B =
  (event hash, 0, section hash, offset of the Lua entry name). Events seen: 0x2f61ecd3 script / SO class, 0x18892991
  relay, 0xdc8b313f OnInitialize.
- **ONLS** (`'ONLS'`, 1, bodyBytes, tailBytes): name groups `[u32 n][n × (u16 len, name)]` + a sorted tail
  (sowhash(owner name), group offset).

## Build steps (the tools, by job)
Each entry: **tool**: what it does → how. "Lib" = imported by build scripts.

### A. Recon, archives, bundles
- **`ltar.py`** writes a stored LTAR v4 from a folder (DFS folder tree, patch index); `ltar_list.py` / **`ltar3.py`**
  read v4 / SoM v3 (zlib chunks). Check: list our archive with QuickBMS.
- **`embb.py` / `bundle.py`**: read / write `.bndl` + `.embb` pairs (layouts above). **`patch_bndl_size.py`**: set one
  entry's size in a newest `.bndl`. **`bndl_index.py`**: index the newest copy of every `.bndl` in archcfg order and find
  which bundles list a file. **`som_bndl4.py`**: unpack SoM BNDL v4. **`bndlxml.py`**: summarise SoM XML load lists.
- **`hdrs.py`**: magic / version / OBJR chunk list of many files, to compare format generations. **`u32dump.py`**,
  **`objr_chunks.py`**: raw views.
- **`som_world_objects.py`**: dump every object of a SoM v9 or SoW v13 objres (class, name, transform, ObjectDB
  properties; property names recovered by hashing strings of both exes) to TSV. **`objres_list.py`**: the same, quick.
- **`udun_overview.py`**: SoM's own map art (2048² `udunmap.tex`) aligned to world space (fit on 23k object positions:
  130,000 units centred on (−16000, 1000)) with landmarks, for planning.

### B. Regions, world map, fast travel, world
- **`MapImport.cs`** (C#, on `GameDb.cs`): region playable, zone-info nodes, a cloned legend row with every region link
  replaced, a cloned travel point. Database edits are classes run by small `.ps1` wrappers: load the db, apply, repack
  (sorted), write to a new folder.
- **`add_worldmap_icons.py`**: clone stock world-map objects into `worlduimenuws.objres` from a JSON spec (`clone`,
  `name`, `pos`, `prop`/`props`): append an OBJL record (class / parent / rotation from the clone) and a new ObjectDB
  record with the clone's layout and new values. Round-trips byte-identical when the spec is empty.
- **`objres_add.py`**: append objects with string properties (adds the class name and single-property layouts if
  missing), e.g. a `TravelPoint`.
- **`worldmap_region.py`**: paint a region slot into the cursor-sample texture: rasterize a polygon (world-map
  units → px with the fitted transform), repaint only listed old blue values, redraw the green border / red glow
  channels, re-encode the BC1 copy.
- **`clone_world.py`**: copy a world bundle + loose tiles to a same-length new path, renaming every internal path
  string in place and re-hashing prefab headers (fails if sizes don't match the load list).
- **`patch_bg_scripts.py`**: same-length Lua condition patch. **`UdunClimate.cs`**: own climate with a chosen default
  weather pattern.

### C. Scenery assets
- **`som_tex.py`**: TEXR v3 → v8: read the header, prepend the `.tex0` top mip if present, complete mips to 1×1
  (SoM chains stop at 4×4; every level below is one block-format block, a copy of the last block), write the v8
  header. **`tex_pipeline.py`** batches it and applies **`tex_fix.py`** ops via texconv: `normal` (B = 255),
  `somspec` (R 170, G 255, B = 255 − B, skipped when already stock-like), `fill`, `grade` (saturation / brightness /
  tint, for the Morgul stone). **`texhdr.py`**, **`texstats.py`**, **`texchan.py`**,
  **`texa_sheet.py`**: inspect headers, channel stats and texture arrays.
- **`mat_survey.py`** → **`mat_catalog.py`** (stock SoW materials grouped by shader: template file, hash, header
  fields, texture slots) → **`mat_convert.py`**: per SoM material, take the template of the same shader (or a mapped
  one), keep its numeric params and hash, set the SoM surface record, and put SoM textures into same-named slots.
  Unmatched slots keep the template's texture.
- **`prfb_convert.py`**: PRFB v5 → v8, per the format notes: widen A/B records (−1 and 0 inserted), move non-position
  elements to stream 1, re-lay each submesh range as stream-0 block + stream-1 block, widen submeshes (u16 used
  vertices + two LOD metrics estimated from the median triangle area), round vb + ib to 4, copy materials / pieces /
  names. Layouts without normals get generated normals / tangents (new decl appended; **update header s9 / s10 /
  s11**). `check()` re-parses every output. **`prfb_obj.py`** (OBJ export) + **`render_obj.py`** (Blender headless)
  give a visual check.
- **`prfb_transplant.py`**: put converted geometry into a stock prefab's structure (for in-game swap tests:
  **`build_swaptest.py`** ships it over a stock prop). **`variant_paths.py`**: path-renamed copies for A/B tests.
- **`wdsc.py`** (SoM v5 reader → `som_instances.tsv`), **`wdsc_add.py`** (append instances to v9),
  **`place_slice.py`** (an area slice for a first visual test).
- **`world_pieces.py`**: SoM's world prefab records (224 placed by SoM objects + 4 scene-list rows) → a converted
  prefab under a new path + instance rows (variant = record key), leaving out stamps, the skybox and nav-obstacle
  meshes.
- **`build_udun.py`**: the one-pass world builder (scene rows at the offset, `world_clear`, arrival, terrain,
  optional `--som-physics`, `--hkai`, `--som-cadb`, `--cave-light-off`). **`world_clear.py`**: move the cloned
  world's own scene rows / objects / collision instances 2 km down, except origin root objects and kept classes.

### D. Ground and terrain
- **`terrain.py`**, **`terrain_quadtree.py`** (cells → tile placement + a sampler), **`terrain_tiles.py`** (decode
  L16 tiles), **`terrain_orient.py`** / **`terrain_locate.py`** / **`terrain_probe.py`** (proved the axis mapping by
  sampling under stock scene instances and by an in-game pillar probe).
- **`terrain_write.py`**: edit heights at world positions in every tile covering a point (all LOD levels), widen cell
  bounds, write the collision heightfield samples, rebuild its min/max quadtree (all in place), re-base the height
  band (`set_height_range`), fill missing root quadrants (`fill_quadrants`), set sample shape tags.
- **`hkhf.py`**: find the heightfield TAG0 in an objres, report fields and array offsets; `true_grid()` = real heights.
- **`udun_ground.py`**: rasterize SoM ground meshes (LOD-0 record, instance transforms) into a max-height grid
  (barycentric point sampling finer than the cell). **`grid_fill.py`**: NaN-aware pyramid fill of holes.
- **`som_paint.py`**: rasterize a SoM terrain prefab's top surface with its blend weights (G = layer 1, B = layer 2)
  onto the 513 grid. **`ground_paint.py`**: map SoM's three layers to four stock terrain layers (constant indices,
  weights vary; slopes 30–45° blend to rock), `extend()` carries paint into holes.
- **`ground_surface.py`**: one surface on the depth-1 lattice that every tile samples bilinearly (no cracks):
  walking height from the collision heightfield; structure / cliff columns replaced by the surrounding walkable
  ground filled inwards; SoM terrain holes only lowered, under whatever SoM draws there; flat pads raised; never above
  collision. `raise_collision()` lifts collision under floating floors.
- **`structure_collision.py`** (superseded by real 3D collision), **`stamp_floor.py`**: earlier 2.5D experiments.
- **`hf_map.py`**, **`edge_gaps.py`**, **`floating_pieces.py`**, **`drawn_top.py`**: hillshades, open map edges,
  floating rows, top-down raster of what is actually drawn.

### E. Collision
- **`hk2012.py`**: generic Havok 2012 binary tagfile reader (classes, objects, back-references).
- **`som_collision.py`**: SoM chunk → world triangles (cm) with surface tag, instance and kind (mesh / convex / box),
  as `.npz`. Includes the **borrowed-vertex fix**: per vertex, try both readings of each axis (q and q − field size),
  keep the one inside the section's BVH leaf boxes; when a leaf spans the whole section, choose among valid readings
  the one with the fewest collapsed edges (< 3 quanta) and the least unused leaf extent.
- **`tag0.py`**: TagTools-based TAG0 read / modify / write that seeds the type table from the source file and copies its
  SDKV + TYPE sections verbatim (so the game sees its own types); only DATA and INDX are re-serialized.
  `unhashed(blob)` lists ITEM / PTCH types without THSH (must be empty). **`tag0_roundtrip.py`**: value-by-value test.
- **`som_to_hknp.py`**: each SoM compressed mesh → an hknp compressed mesh (tree copied, SIMD BVH built, key fields
  set, `triangleIsInterior` zeroed, data runs carry the tag), all in one compound built on a stock blob as template,
  with a fresh instance tree; `--skip` drops pieces (SoM's invisible helper layer 2593), `--extra` adds SoW-native
  pieces; `replace_blob()` swaps it into the world's WorldPhysics (marker 0xFFFFD00D + size) and widens the
  world-collision prefab bounds.
- **`simd_tree.py`**: top-down build (split at the median along the longest centroid axis, twice → 4 children per
  node). Self-test: 300 random box queries return the same leaves as stock trees.
- **`som_props_hknp.py`**: SoM convex hulls / boxes → `hknpConvexPolytopeShape`s (vertices transformed, coplanar faces
  merged, planes, minHalfAngle, connectivity, penetration as half), re-typed onto a stock blob's type table that has
  convex types, appended to the compound; verifies against `som_collision.npz` after writing.
- **`hknp_mesh.py`**: decode any hknp world-physics blob to triangles and check SIMD-tree leaves (each primitive once,
  exact AABB), key fields and the instance tree. Ours matched SoM's triangles to 0.008 cm.
- **`mark_walls.py`**, **`mark_surfaces.py`**, **`mark_column.py`**, **`mark_instances.py`**, **`prefab_coverage.py`**,
  **`invisible_collision.py`**: per F12 mark, which collision is around Talion (nearest walls, surfaces + tags, a
  vertical column, render instances), coverage per prefab, collision with nothing drawn on it.

### F. Parkour
- **`cadb.py`**: read CADB; `convert_som()` maps SoM v1 edges / groups / types to v3 (type list re-hashed, masks
  re-mapped, v2 field added); also merges SoM's streaming-area `.cntx` climb lines. **`hang_probe.py`** /
  **`cj_summary.py`** check a hang spot against the hang-exit rules / summarise the trace's CanJump lines per mark.

### G. Navmesh
- **`recast_cli.cpp`** (compiled with the vetted Recast core only): input `NMIN` (u32 nverts, ntris, float verts in
  metres, int tris), args cs ch slope height climb radius maxEdgeLen maxError minRegion mergeRegion nvp tileSize
  threads. Builds tiles in threads and writes `NMOT` (per tile: global-cell vertices + polygons, 0xFFFF padded).
- **`navmesh_build.py`**: gathers the in-game collision (SoM meshes + props at the offset, and heightfield quads whose 4
  samples have real collision, i.e. not `Air` or the edge seal), runs the CLI, **stitches tiles** (weld vertices per
  (x, z) within the step height on one global cell grid, split tile-border edges at the other side's vertices, pair
  half-edges (a, b) ↔ (b, a)), and writes polygons CCW from above to `.npz`. Final settings: cs 0.25, ch 0.05,
  slope 55°, height 2.0, **climb 0.5**, radius 0, tile 128, nvp 8.
- **`hkai_patch.py`**: `--replace` (whole navmesh from `.npz`), `--add-polys` / `--tris` (append to the stock mesh),
  `--info`; `orient_up()` fixes winding; clearance caches extended; aabb grown.
- **`hkai_winding.py`**: Newell normal per face + edge pairing check. **`navmesh_probe.py`**, **`navq_box_check.py`**:
  navmesh vs F12 marks and replays of the trace's logged query boxes. **`ruins_spots.py`**: navmesh island size under
  given spots. **`navheight.py`**: exact navmesh heights (point in triangle over a bucket grid, nearest to a hint).

### H. Region map and minimap
- **`zonemap_build.py`**: from a stock zone-map prefab bundle: a grid mesh of our ground (+ structures) in ±256 map
  units (UV = pos/512 + 0.5), an overlay texture with structure glow, material, objres (PFDG names the mesh + bounds),
  re-hashed stubs (`.inst` own-path hash, `.scripts` section id = hex(sowhash(path)), `.veggrid`, a zero-size
  `.wldmsh` entry), plus `interface\bundles\maps\<r>.bndl` with the world's `.uis` / `.uiwd` (bounds = the ground
  square, travel entries type 1). **`zonemap_hf.py`**: map collision = the world's heightfield TAG0 rescaled to map
  space (storage, heightScale, quadtree, int / float scales, instance transform, AABBs patched). **`zonemap_check.py`**,
  **`zonemap_refcheck.py`**, **`zonemap_collision.py`**: re-parse every entry, find leftover template references.
- **`MapZone.cs`**: the Region's three zone-map strings + scale / camera / canvas visibility from Minas Ithil.
- **`minimap_build.py`**: navmesh islands (≥ 40 faces) split into three height bands → fan triangles in the `.uis` and
  boundary loops in the `.uiwd` for the existing canvases (`Terrain_Low / _Med / _High`); round-trips byte-exact when
  unchanged. The world `MapRegion` object is moved / widened with an OBJL position + property edit.

### I. Army (database)
- **`GameDb.cs`**: GADB load / edit / repack / write (fixed bool handling). **`RepairBools.cs`** /
  **`FalmerBoolRepair.cs`**: restore bools scrambled by the older repack (compare with the stock record's bits).
  **`LinkScan.cs`** / `ItemRefs.cs`: who links to a record. **`describe.ps1`**, **`dbrec.ps1`**, **`walk.ps1`**: dumps.
- **`UdunArmy.cs`** + **`udun_army.ps1`** + a settings JSON (`warchiefs`, `captains`, `overlord`, `stage`, `quests`,
  `wild`, `location_quest_eval`, `open_predicate`, `spawn_limits`):
  - `Faction_Udun` and its rows cloned from Cirith Ungol's (ColumnMax from the JSON, HenchmenRows, locations);
  - `PromotionEventSetup` with `NumSimEvents` per row index sized from the slot counts, plus timed events;
  - the `Faction/World/Faction` + fort setup + fixed member positions (slot file);
  - locations / areas, quest records + lists, the captain row's sim-event generation;
  - spawn predicate `UdunOpen` (cloned predicate with new distance bands), `AI/Count:Udun` and a `ScenarioOverride`
    list with raised caps (new structs templated on an existing entry, category taken from the link).
  - Errors print the innermost exception and stack.

### J. AI population and missions (world objres)
- **`kit_copy.py`** (`KitCopier(src_objres, src_scripts, dst_objres, dst_scripts)`):
  - `.add(src_prefix, new_prefix, base, overrides, per_object, bools, single)` copies a kit: OBJL records (class names
    added, hier string for the new prefix, new name hashes), ObjectDB records (layout runs copied or reused, heap
    values re-added, string / value overrides), SCRB bindings (E2 / E3 rebuilt and sorted), ONLS groups, and the Lua
    entries + prototypes the bindings name;
  - `.set_strings()` / `.set_values()` edit existing records; `external_refs()` refuses kits that reference outside
    themselves; `.result()` → new objres + scripts. Round-trips byte-identical with nothing added.
- **`volm.py`**: read / write VOLM; `merge_brushes()` copies AreaBrush volumes (hull geometry at an offset + VolumeDB
  records) between worlds. **`area_check.py`**: which areas contain a point.
- **`ruins_outpost.py`**: choose open-air station kits (no `Space*` scenario category, no lair), place them on SoM's
  captain spots that sit on the main navmesh island, set locations, bake the Lua's predicate result (`AutoPredicate` →
  `AmbShort`), turn time-of-day off, copy each station's activity-spot kits (`node_kits`, cached per world).
  **`ruins_patrols.py`**: SoM route nodes → SoW `SP_NN` route kits (next / branch links) + one stock sentry per route
  + ranging packs. **`ruins_props.py`**: fire pits / grog buckets as scene rows + activity spots joined to the
  nearest station. **`ruins_more.py`**, **`west_camps.py`**, **`west_spawns.py`**, **`west_fix.py`**,
  **`west_more.py`**: extra stations at SoM's spawner clusters (min gap, big islands only), per-area locations, SoM
  route networks as patrols, slave / caragor / Ghûl kits + their stock forage-node kits, predicate repointing to
  `UdunOpen`, second stations and wider fill-orc distances.
- **`spawn_audit.py`**: audit + fix spawner heights. Per object: exact main-island navmesh surfaces at (x, z), sealed
  pocket surfaces (small islands), collision obstacles above the floor at the point and a shoulder ring (the local
  floor at each ring point is excluded so slopes don't count). Verdicts: OK / LOW / HIGH / POCKET / OFF / BLOCKED.
  The fix: real floor = up-facing collision surface nearest the navmesh (≥ navmesh − 0.35 m), + the stock class offset
  (calibrated on Cirith Ungol), clamped under ceilings; bad spots move to the nearest clear main-island point.
- **`quest_extract.py`**: the newest copy of every file of a stock quest section (patches ship newer `.scripts`).
  **`quest_port.py`**: rename a section to a new path (Lua table hash, SCRB hash, `.inst` hash, veggrid path),
  `MP_` → `UD_` strings in place, rigid move to a site with per-object height re-fit (source navmesh → ours), then
  copy the main-world Quest + trigger objects with `kit_copy` (`single=` mode) re-pointed at the new section.

### K. Diagnostics and safety
- **Trace plugin** (`trace.c`, gcc → `MapImportTrace.dll`, loaded by the Dll Loader from `x64\plugins`):
  - waits until the exe's code matches the expected prologue bytes;
  - allocates a trampoline page within ±2 GB of the exe;
  - patches each target with a 5-byte `E9` jump; the stolen 5–11 bytes (plain register / stack moves, no RIP-relative
    code) run in the trampoline, which jumps back;
  - logs arguments as GADB record names (name pointer at rec+0x20 when rec[1] & 2) plus the exe call stack as RVAs
    (`RtlCaptureStackBackTrace`), with per-hook caps and log-on-change.
  - Over 24 versions it covered:
    - world loads / SetRegion / fast-travel dialogs;
    - navmesh query mediator vtable slots (closest point, ray casts, AABB queries) in rings dumped on F12;
    - CanJump evaluations and acceptance;
    - **F12 position marks** (scan of the process's private pages for float triples near the arrival, re-read on F12;
      the group that moved together = the player);
    - the game's own **AI spawn debug messages** (stub loggers redirected, gate bytes set only with
      `[Debug] SpawnLog=1`).
  - Static targets were found with Ghidra headless on a memory dump (`XRefs`, `DecompRO`, `FindConst`).
- **`ss_sheets.py`**: 2×2 screenshot contact sheets labelled with the nearest F12 mark. **`ft_check.py`**: per session
  log, did fast travel to the region work, and which backed-up save is known good. **`save_restore.py`**: restore a
  save to both save files with md5 + decrypt checks (game closed, user's OK). **`minidump_info.py`**: crash dump
  summary.

### L. Visual clean-up
- **`lighting_patch.py`**: move named lighting objects and the VOLM atmosphere volume containing a point by dy, same
  size, as a loose override. **`clutter.py`**: decode / clear clutter. **`scene_sink.py`**: sink rows (by SoM row or by
  prefab + variant) under the world so they stop drawing but keep their indices.
- **`stamp_clip.py`** (keep one region of a stamp record, dedupe against detailed rows, sample points over faces),
  **`stamp_retexture.py`** (box-mapped tiling UVs per face, tangent frames, vertices split into free slots),
  **`stamp_vcol.py`** (re-lay a range in a declaration with a white colour stream, repoint submeshes, grow s11).
- **`paint_split.py`**: split a converted prefab by SoM's vertex paint into rock + soil prefabs (collapse faces to
  degenerate, swap a same-length material path); `collapse_where()` removes faces by world position.
- **`edge_mountains.py`**: place SoM mountain / rock pieces along open map edges and raise the heightfield under them.
  **`render_piece.py`**: orthographic renders of world-prefab pieces.

## Verification
- Every reader / writer: byte-identical round trip on stock files (objres, OBJL, GADB / ObjectDB, kit copier with
  nothing added, `.uis`, LTAR), or value-identical for TAG0 (742,627 values) and the convex props.
- Structural checkers: `hknp_mesh.py` (trees, keys), `hkai_winding.py`, `zonemap_check.py`, `prfb_convert.check()`,
  `tag0.unhashed()`, `simd_tree` self-test against stock trees, `som_props_hknp --verify`.
- Rules from stock data before use: spawner offsets, compressed-mesh section tightness, surface tag fold, terrain axis
  mapping (proved on two stock worlds and an in-game pillar probe).
- In game: each tool's output was tested in a user test build (see the main note), with the trace plugin's log.
- Not verified: other game builds / platforms; any SoM or SoW asset not used by Udûn (e.g. skinned characters, which
  use MMSH, not PRFB).

## Gotchas
1. **A converted file loads but crashes later.** **Cause:** header counters not updated (PRFB decl counts s9 / s10,
   arena size s11). **Fix:** recompute every counter from the written data, then re-parse in a check pass.
2. **A Havok blob crashes the loader.** **Cause:** types without THSH hashes (TagTools' writer only emits THSH for
   types that already carry a hash), or a TYPE section that lacks a type the data now uses (convex shapes on a
   mesh-only blob). **Fix:** keep the source's TYPE section; re-type onto a stock blob whose table is a superset; check
   `unhashed()`.
3. **TagTools writes the half-float `maxAllowedPenetration` as a 4-byte float over the next field.** **Fix:** give the
   float with the half in its low 16 bits, written before the overlapping field.
4. **TagTools places rel-arrays a breadth-first round later than stock.** **Fix:** write each shape's arrays right
   behind it (u16 relative offsets).
5. **Borrowed vertices** (SoM packer) and **sections that aren't tight**: see `som_collision.py`. Stock SoW sections
   are tight per axis; SoM's aren't.
6. **Bools in GADB are bits.** Any generic repacker must keep bit indices; dumpers must read bits.
7. **Surface tag fold is addition** (`(v + (v >> 16)) & 0xFFFF`).
8. **Recast tiles don't share vertices, and nothing links them.** Recast builds each tile on its own and only flags
   tile-border edges as portals (`0x8000 | side`); Detour links them at run time, but an `hkaiNavMesh` needs the links
   written into its edges (`oppositeEdge` / `oppositeFace`). Weld on a global cell grid and split border edges, or the
   navmesh is thousands of disconnected tiles. (Recast's own `rcMergePolyMeshes` welds identical vertices too, but its
   16-bit indices cap the result at 65,535 vertices and polygons.)
9. **Recast's polygon winding vs Havok's:** Havok needs CCW from above. Check every build.
10. **Heights from a calibration break after re-basing:** read Havok heightfield data with its own scale fields.
11. **Kit copies need everything that wires them:** ObjectDB values, SCRB, ONLS, Lua entries *and* the world's Lua
    section name; relative `#.` links survive a prefix rename; absolute links outside the kit don't.
12. **Polygon-mean heights are wrong on slopes:** always intersect the exact triangle; spawners go on the real floor +
    the stock offset (~2 m), never on the navmesh.
13. **The bundle writer rebuilds `.bndl` from `.embb`:** stock zero-size entries vanish; keep the original `.bndl`.
14. **Installer safety:** refuse unless the installed archcfg names the previous build; back up saves + archcfg first;
    md5-check the copied archive; CRLF byte-exact edits.
15. **Big bundles and RAM:** a 2.1 GB world bundle is read and written whole; with 16 GB RAM run one heavy job at a time.

## Assets
None generated; all data comes from the user's own installs at build time.

## Cost and time
Built incrementally over 8 days alongside the map import (~150 scripts, most of them small). The heaviest steps
are the full-map ones: collision conversion, the navmesh (Recast, 8 threads) and writing + packing the 2.1 GB world
bundle, each taking minutes rather than seconds.

## Open questions
- MMSH v9 (SoM skinned meshes) → v17 was not needed for Udûn and isn't written (a reader exists in SoW form only).
- SoM `.path` (LithTech navmesh) was never decoded; Recast replaced it.
- A generic "port any SoM map" driver (Núrn next) would mostly be the U-build scripts with the map's own paths and
  offset.
