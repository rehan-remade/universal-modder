---
kind: technique
title: Disrupt XBG/GLM mesh format (Watch Dogs 1/2/Legion)
game: Watch Dogs 2
games_also: ["Watch Dogs", "Watch Dogs: Legion"]
game_version: "WD2 (mesh header version 70.137 = 0x00460089)"
platform: windows
engine: Disrupt (Dunia 2 fork)
route: asset-only
tools: [XbgLab, GlmCompilerToXBG, io_scene_WD2, Blender, Ghidra]
anti_cheat: unknown
status: working
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links: []
tags: [disrupt, watch-dogs, mesh, xbg, glm, geometry, vertex-format, hashing, dunia2]
---

# Disrupt XBG/GLM mesh format (Watch Dogs 1/2/Legion)

> Watch Dogs geometry ships as `.xbg` files that begin with the reversed magic
> `MOEG` ("GEOM"). The format is a small binary header plus LOD/write blocks
> plus material, skin and skeleton tables, and its name lookups are a mix of
> plain CRC32 and a masked 64-bit FNV. This note records the layout, the vertex
> stream decoding, and the hashing rules needed to round-trip a mesh.
> Disrupt is a Dunia 2 fork; the same family of containers feeds WD1, WD2 and
> Legion.

## When to use it

- Porting or replacing a character/weapon/prop mesh already present in the game.
- Writing a `.xbg` from scratch or converting a Blender mesh to/from `.xbg`.
- Decoding a mesh to inspect bones, materials or LODs without reimplementing the
  whole engine.
- You need to hash a resource path the way the engine does (e.g. building a
  material reference hash, matching a file to its record).

Not the tool for: hashed-name lookup of gameplay objects (see the FCB note) or
texture replacement (see the materials/textures note).

## How

### File header (little-endian)

Verified against `rifle.xbg` and cross-checked with the `CGeometryResource`
parser in the PC `Disrupt_64.dll` (PE32+); the magic compare sits at DLL
address `0x0C002BD0`.

| Offset | Size | Meaning |
|--------|------|---------|
| 0x00 | 4 | magic `MOEG` (bytes `4D 4F 45 47`) |
| 0x04 | 2 | version minor = 137 (0x89) |
| 0x06 | 2 | version major = 70 (0x46) |
| 0x08 | 16 | content hash (algorithm unresolved; may be zero) |
| 0x18 | 4 | LOD count |
| 0x20–0x6B | | bounding / bind data |
| 0x70 | 4×N | LOD distances (f32), e.g. `[4, 12, 20, 75, 150]` |
| 0x84 | 4 | max LOD distance (f32) |
| 0x88 | 4 | flags, seen `0x00FF0101` |
| 0xA4 | 4 | material count |
| 0xA8 | | material block |
| 0x164 | | mesh-state list |
| 0x19C | | bone/node list |

Whole-file version word as a u32 is `(70 << 16) | 137 = 0x00460089`, i.e.
major in the high half. Note that two independent tool authors named the two
u16 halves opposite ways (one calls `0x89` major, the other minor) — always key
off the u32 rather than the label.

### Material block

Each material entry is name-hashed, not stored as plain text:

1. `+0x00` u32 — low 32 bits of `FNV1_64(path)`
2. `+0x04` u32 — high 32 bits of a transformed `FNV1_64(path)` (see hashing)
3. `+0x08` u32 — path string length
4. `+0x0C` — ASCII path, padded to 4 bytes
5. u32 — `CRC32(shader_name)`, then length, then lowercase shader name padded to 4

Example: path `graphics\_materials\fboivin2-m-2013112041431277.material.bin`
hashes to `0xB84994D4` / `0xBDD81664` and shader `wd2generic` CRCs to
`0x3A5B0C92`. Paths use backslashes, not forward slashes.

### Mesh-state and bone tables

- Mesh-state list (`@0x164`): u32 count, then per entry `CRC32(name)`, length,
  name+padded4, flags, and a LOD mask / bone count. Examples: `LOD_Swatch`
  (`0x025ED1A5`, flags 1), `Weapon_LMG_U100` (`0x4FE68483`, flags 0,
  bone_count 3).
- Bone/node list (`@0x19C`): u32 count, then per bone `CRC32(name)`, length,
  name+padded4, flags, transform floats. A rifle root is `Rifle`
  (`0x7A15D5D1`) with children such as `Clip` (`0x0D12BB59`), `Frame`
  (`0x743913C9`) and `Slide` (`0xB32EC166`).

### Vertex stream decoding

A reader/writer (`XbgLab.XbgReader`) gives an exact vertex decoding recipe.
Per LOD draw (`MeshPart`), after 10 bounding floats come: primitive type
(must be 0 = triangle list), material index, vertex format (FVF), vertex
stride, flags, buffer offset, primitive count, index count, first index,
vertex count, min/max vertex index, draw-group count and named draw ranges.

The FVF, with `f` the u16 and unused bits ignored (`~0x97cf`), builds a stride
`k` that must equal the stored stride:

```
k  = ((f & 1) ? 12 : 8)        # position: 3x f32 or 3x i16
   + ((f & 4) ? 8 : 0)         # UV0 f32
   + ((f & 8) ? 4 : 0)         # UV0 i16
   + ((f & 0x1000) ? 4 : 0)    # UV1 i16
normalOffset = k
k += ((f & 0x80)   ? 4 : 0)    # normal
   + ((f & 0x100)  ? 4 : 0)    # unused
   + ((f & 0x200)  ? 4 : 0)    # tangent
   + ((f & 0x400)  ? 4 : 0)    # bitangent
   + ((f & 0x8000) ? 4 : 0)
```

Decode values from the vertex base `b` (`p` = the field offset):

- Position (i16): `p * Scene[1] + Scene[0]` (Scale / Position bias).
- UV (i16): `p * Scene[4] + Scene[3]`, then **invert V** (`1 - v`).
- Normal / tangent / bitangent: 3 packed bytes, `packed = normalize(vec3(b[p+2], b[p+1], b[p]) / 127.5 - 1)`.
- Indices are u16; triangle winding is reversed relative to common convention.
- `Scene[1]` (position scale) and `Scene[4]` (UV scale) must be > 0.

There are 19 `SceneGeometryParams` floats: position bias/scale/extent, UV
bias/scale, bounding-sphere xyz+radius, bbox min/max xyz, and four extras.
An empty static prop simply has zero skeletons, an identity root matrix and an
empty armature chunk.

### Companion files

- `.xbgmip` (magic `GMIP`, i.e. `PIMG` byte order): external mip buffers, path
  suffix `.high.xbgmip`; header holds a version==1 and a buffer count that must
  equal the mesh's `FirstEmbedded` count.
- `.skel`: skeleton companion — signature, a bone-block length at `0x18`, a name
  offset table, a u32 hash list, a signed parent-index list (root = -1) and
  bones of 8 floats (location + quaternion).
- `.xbt`: texture companion referenced by the material.

### Writing a mesh back

A working writer quantises position to i16 (scale = maxAbs / 32760), UV to i16
(bias/scale from the UV bounding box), packs normals/tangents, reserves header
space for the tables (header base + materials×256 + parts×LOD count×128),
keeps `flags = 0x00ff0101`, and emits draws with vertex format `0x178a`
(stride 32). Round-trip is verified by re-parsing the output, not by eyeballing.

### Hashing rules

Two hash families appear and both are load-bearing:

- **Names** (bones, mesh states, nodes, shaders, FCB field/object names):
  standard CRC32, polynomial `0xEDB88320`.
- **Resource paths**: a masked 64-bit FNV.

`XbgLab` documents the resource hash as a 64-bit FNV-1 whose result is masked
to 61 bits and OR'd with a tag: `(raw & 0x1FFFFFFFFFFFFFFF) | 0xA000000000000000`,
after normalising the path (trim, `/`→`\`, trim leading `\`, lowercase,
ASCII only, no `:`). A second community source documents the WD2 material
form as `FNV1_64` low32 plus a transformed high32, where the transform takes
the FNV's top byte `msb`, sets `msbNew = (msb & 0x1F) | 0xA0`, and rebuilds the
u64 with that byte at bits 56–63. Treat the exact high-bits rule as the area
to re-verify before trusting a hand-built hash.

Important: the material-path hash uses **FNV-1** (multiply then XOR), not the
more common FNV-1a, with offset basis `0xCBF29CE484222325` and prime
`0x100000001B3`.

### The GLM source form

The community converter pipeline starts from an ASCII `.glm` (not the shipped
binary): `VERSION`, `TYPE "GEOM"`, `MATERIAL_REFERENCE_LIST` (a `SHADER` name
such as `WD2Generic`, plus a `SHADERREFID` pointing at a forward-slash
`.material.xml`), `SKELETON_LIST`, and `GEOMETRY_LIST` with `TRIMESH` blocks
(`VERTEX_LIST` / `NORMAL_LIST` / `TVERT_LIST` / `FACE_LIST`). FACE count =
`1 + 3 + 3 + 3×NB_UV_CHANNELS + 2`; inactive UV channels are `-1,-1,-1` and W
is always `0.0`. Going GLM→XBG the converter rewrites `.material.xml`→
`.material.bin`, `/`→`\`, and lowercases the shader name.

## Gotchas

1. **Mesh decodes to garbage / no vertices** → FVF stride mismatch → recompute
   the stride from the FVF bit table and require it to equal the stored stride;
   if not, the file layout is not the standard triangle-list path.
2. **UVs mirrored vertically** → V is stored bottom-up → apply `v = 1 - v` on
   read (and the inverse on write).
3. **Material reference never resolves** → wrong hash family → use FNV-1 (not
   FNV-1a) with the masked 61-bit resource tag; also confirm the path uses
   backslashes and is lowercased.
4. **Version check rejects every file** → the two u16 halves are labelled
   inconsistently between tools → compare the u32 `0x00460089` rather than
   either half.
5. **Normals look wrong** → byte order → reconstruct as
   `normalize(vec3(b2, b1, b0) / 127.5 - 1)`, i.e. reversed component order.
6. **Writer output loads with holes** → the header reserves fixed space for the
   material/skin/part tables → keep the original table sizes or grow them and
   re-point offsets; then re-parse to confirm.

## Seen in

- `XbgLab` (C# / .NET), `src/XbgReader.cs`, `XbgWriter.cs`, `Model.cs`
  (Hashing, lines 26–49) — reader+writer, fully reversed.
- `GlmCompilerToXBG` — the GLM→XBG research summary with DLL-verified offsets.
- `io_scene_WD2` (Blender importer, `import_WD2.py`) — independent `.xbg`,
  `.skel` and `.xbt` reading.
- Existing KB note `knowledge/games/watch-dogs/engine-fundamentals-and-native-patching.md`
  covers the runtime/native side; this note is the on-disk format side.
