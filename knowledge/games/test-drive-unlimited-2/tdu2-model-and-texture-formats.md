---
kind: game
title: "TDU2 model and texture formats: .3DG/.3DD geometry, .2DM materials, .2DB textures"
game: "Test Drive Unlimited 2"
games_also: []
game_version: "retail (any; formats are version-independent between TDU1 and TDU2 for .2DM/.2DB)"
platform: windows
engine: unknown
route: data
tools: ["custom Python parsers (blender-io-tdu-series)", "Blender 4.0 LTS addon", "3ds Max MaxScript importers (vagos21)", "Krom bnk extractor"]
anti_cheat: "none"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links: []
tags: [tdu2, 3dg, 3dd, 2dm, 2db, mesh, texture, dxt, half-float, triangle-strip, little-endian, maxscript]
---

# TDU2 model and texture formats: .3DG/.3DD geometry, .2DM materials, .2DB textures

> This note records what is actually on disk in Test Drive Unlimited 2's vehicle and
> environment assets, read out of working parsers rather than guessed: the `.3DG`/`.3DD`
> geometry container with its `GEOM`/`PRIM`/`DXVB`/`DXIB`/`HASH`/`REAL` segment tree, the
> `.2DM` material container with `MATA` segments, and the `.2DB` texture container with
> DXT1/DXT5/ARGB8 payloads. Everything here is little-endian. The parsers are pure Python
> and run without Blender or the game; the route is **data** — no engine hooked and no exe
> run. This distils two independent implementations that agree (a Python parser set and the
> original 3ds Max MaxScript importers), so the layouts are cross-checked, not single-source.

## Setup

- Assets live inside `.bnk` containers of an installed TDU2; extract them first (Krom's bnk
  extractor; the MaxScript importer header names it). A vehicle folder then holds one
  `.3DG` (geometry), one `.3DD` (scene/hierarchy + instances), one `.2DM` (materials), and a
  pile of `.2DB` textures.
- Python side: `blender-io-tdu-series/io_scene_tdu2/{parser.py,types.py,dds.py}` are importable
  outside Blender (no `bpy`). Only `operators.py` needs Blender.
- Blender addon target: Blender 3.3+ declared, **confirmed working on 4.0 LTS**, broken on
  4.4.3 / 5.2. Mesh smooth API and material input names are `hasattr()`-guarded.
- No test framework; root `test_*.py` scripts build synthetic binaries and parse them.
- Nothing in this note required running the game or any executable.

## Route and why

Chose **data** (parse the containers directly) because TDU2 model/texture data is plain
little-endian structs with a self-describing segment tree — there is nothing to hook. The
alternative, the 3ds Max MaxScript importers (`TDU2-Mesh-Import/`, `TDU-Mesh-Extractor/`),
does the same parsing and was used as an independent cross-check. No decompiler, no runtime
instrumentation, no anti-cheat concern (single-player; the engine is not in play). The one
3D-editor-specific step in the MaxScript route is that it asks you to **rotate the imported
scene +90° about X** — that is the Y-up→Z-up conversion, not a format quirk.

## How the game works (what we had to learn)

### Container headers

- **`.3DG` / `.3DD`**: 16-byte header — `file_version` u16 @0, `some_flag` u16 @2, `unk1`
  u32 @4, `size` u32 @8 (whole-file byte count), `magic` u32 @12. Magic is `0x4744332E`
  (`.3DG`) or `0x4444332E` (`.3DD`). `size` must equal the file length or the parse is
  rejected/truncated.
- **`.2DM`**: same 16-byte shape, magic `0x4D44322E` (`.2DM`) @12.

### The segment tree (shared by `.3DG` and `.2DM`)

Both containers are a recursive list of segments. Each segment begins with a **16-byte
header**: `magic_type` u32 @0, `zero` u32 @4, `seg_size` u32 @8, `next_segment_ptr` u32 @12;
payload starts at +16. The grammar:

- If `0 < next_segment_ptr < seg_size`, this segment has **children**: its own payload runs
  from +16 only up to `next_segment_ptr`, and the child list begins at `offset + next_segment_ptr`.
- Otherwise payload runs to `seg_size` and the next sibling begins at `offset + seg_size`.
- A `seg_size` of 0, or any `offset + seg_size > size`, terminates the walk.

`.3DG` segment magics: `MOEG`=`0x4D4F4547` (byte literal `GEOM`), `MIRP`=`0x4D495250`
(`PRIM`), `BXVB`=`0x42565844` (`DXVB`, a D3D-style vertex buffer), `BXIB`=`0x42495844`
(`DXIB`, index buffer), `HASH`=`0x48534148`, `REAL`=`0x4C414552` (a colour block; the
MaxScript/AGENTS naming calls it `LERE`). `.2DM` nests `MATA`=`0x4154414D` segments, and a
second material magic `0x2E54414D` appears (the code searches for both).

### `PRIM` — one draw call / mesh piece

64-byte payload: `offset_index` u32 @0, `offset_vertex` u32 @4, `offset_bone` u32 @8,
`offset_unk` u32 @12, `unk2` u16 @16, `mat_id` u16 @18, `unk3` u32 @20, `unk4` u32 @24,
`n_verts` u32 @28, `unk5` u32 @32, `unk6` u32 @36, `nb_indices` u32 @40, three zero u32 @44/48/52,
`bound_radius` u16 @56, `bound_x/y/z` s16 @58/60/62 (an integer bounding sphere, not float).

The `offset_index` / `offset_vertex` fields are **absolute file offsets** to the `DXIB` and
`DXVB` segments; matching a prim to its buffers is done by comparing the buffer segment's
file `position` to these values. **`mat_id` is 4 in practice for every prim** — do not use it
for material assignment (see Gotchas). Group names come from the parallel `HASH` list, not
from `PRIM`.

### `DXVB` — vertex buffer

Payload @0: `n_verts` u32, then a byte-level "FVF" flag block (positions/normals/colour/UV
flags, tangent, bi-normal, bone indices/weights, and a UV-location word). The original
MaxScript read 28 FVF bytes and keyed off individual fields: `hasNormal`, `hasColor`,
`numUVs`, two "QQ" (tangent/bi-normal) flags, and `hasUVinPOS`. A hard-coded table of the
shipped vertex layouts exists in the MaxScript (`xyz`, `xyzUVJqq`, `xyzJqqcolorUV`,
`xyzUVUVJqqcolor`, …) — the trailing letters encode which channels follow.

Vertex stream layout is split into two strided regions after the 32-byte header:

- **float region** — per vertex: position `float3` (12 B), then *if* UV lives here, `float2`
  per UV set; optional bone-index/weight slots.
- **main region** — per vertex, in fixed order: **normals** = three **half-floats** (6 B)
  plus 2 B pad = 8 B; **colour** = 4 bytes; **UVs** = `float2` each *if* UV lives here;
  tangent 8 B; bi-normal 8 B.

Key confirmations:

- **Positions are `float32`; normals are IEEE-754 half-precision `float16` triplets** (6 bytes
  then a 2-byte pad). The parser implements half→float by hand (`half_to_float`) because it
  must run without numpy. The MaxScript just *skips* the normal block (8 bytes) — it never
  uses them, which is why the importer header warns "some normals will not be correct".
- **UVs can live in either stride**, selected by the `uv_loc` word. The MaxScript tests
  field 26: value **0x10 (→ high byte, parser mask `0xF000`) means UVs are interleaved with
  positions** (read right after each position); value **0x01 (parser mask `0xF00`) means UVs
  come after normals/colours in the main region**. The Python parser handles both; note the
  two flags are nibble-masked separately (`uv & 0xFF` count, `uv_loc & 0xF000`, `uv_loc & 0xF00`).
- UV V is negated on import in the MaxScript (`[u, -v, 0]`); the Python importer keeps raw.

### `DXIB` — index buffer

Payload @0: `nb_indices` u32, `n_type` u32, 8 bytes padding, then `nb_indices` × u16 starting
at +16. Indices are a **triangle strip** in D3D order. Strip→triangles uses alternating
winding: for strip position `j`, even `j` emits `(j, j+1, j+2)`, odd `j` emits
`(j, j+2, j+1)`; fully degenerate triangles (any two indices equal) are dropped. The writer
does the inverse (triangles→strip) by keeping the first triangle and appending
`(i2, i1)` per following triangle.

### `HASH` — group-name directory

Payload is a run of **16-byte entries**: an 8-byte mangled name, `offset` u32 (+8) pointing
at the corresponding `PRIM` file offset, and a zero u32 (+12). The i-th HASH entry names the
i-th `GEOM` child, so it is the source of mesh group names.

### The mangled 8-byte names

TDU2 names in `HASH`, `.2DM` layer rows, and `.2DB` texture keys are 8 raw bytes. Decoding:

- All bytes `0x20` (space) or all `0x3F` → empty.
- Any zero byte present → treat the whole thing as plain null-padded ASCII and strip nulls.
- Otherwise it may be the **mangled encoding**: the 8 bytes are a sum of the ASCII characters
  placed at `index % 8` (`b[i%8] += ord(c)`). Reversing it needs a dictionary of candidate
  plaintext names; the parser seeds one (~200 vehicle/layer/part names) and maps every known
  name to its 8-byte key. Unknown keys decode to `UNK_<hex>`.
- One more wrinkle: trailing `0x20` are normalised to `0x00` before the dictionary lookup,
  because some records pad the mangled key with spaces and others with nulls.

This is why `HASH` names and texture keys must be matched **on raw bytes**, not on
round-tripped strings.

### `REAL` — material colours embedded in `.3DG`

`REAL` payload is a sequence of `float4`s; each becomes a `TDUMaterial` with `diffuse = (r,g,b,a)`,
`ambient = (r,g,b,a) * 0.3`, white specular, black emissive. It is a fallback when no `.2DM`
is present.

### `.2DM` material segments

Inside a `MATA` node's payload (≥256 bytes):

- `hash_name` 8 bytes @0;
- `name` ASCII, null-padded, 32 bytes @16;
- `ambient` float4 @176, `diffuse` float4 @192, `specular` float4 @208, `emissive` float4 @224;
- `nb_layers` u16 @252 (capped at 32);
- then `nb_layers` × **32-byte texture-layer rows** from @256: an 8-byte `type_name`
  (plain ASCII or mangled — decode as above), an 8-byte `texture_name` key, and u16 flags /
  unknown at +16/+18.

Layer type names are the semantic map into the material graph: `COLOR`, `MATERIAL`, `DETAIL`,
`NORMAL`, `GLOSS`, `REFLECTION`, `GLOSSLIGHT`, `TEXLIGHT`, `SHADOW`, plus the TDU2-only set
(`DIRTSCRATCH`, `DIRTCOLOR`, `FLAKE`/`FLAKES`/`FLAKEABNS`, `STIKERS`, `DAMAGE`, `SPECPARM`,
`MATPARAM`, `ILUMPARAM`, `ILUMCOLOR`, `RAMPPOW`, `DMGCOLOR`, `MPCLR1/2/3`, `RAMP1/2`, …).
Layer rows are matched to geometry by **texture-name suffix ↔ HASH group name**, not by
`PRIM.mat_id`.

### `.2DB` texture

80-byte (0x50) header then the compressed payload:

| off | field |
|---|---|
| 0 | `file_version` u16 |
| 2 | `unk1` u16 |
| 4 | `unk2` u32 |
| 8 | `size` u32 (total file size, per the Python parser) |
| 12 | `id` 4 raw bytes |
| 16 | `id2` 4 raw bytes |
| 20,22 | `unk3`,`unk4` u16 |
| 24,28 | `some_size`,`some_other_size` u32 |
| 32 | `name` **8 raw bytes** (the cache key, not ASCII) |
| 40 | `width` u16 |
| 42 | `height` u16 |
| 44 | `param4` u16 |
| 46 | `param5` byte (mipmap count, read by the MaxScript) |
| 47 | `unk5` byte |
| 48 | `param7` u32 = **format** |
| 52,56,60 | `unk6`,`unk7`,`param6` u32 |
| 64 | `flags` u32 |
| 68..76 | `unk9`,`unk10`,`unk11` u32 |
| 80 | image data (`size - 80` bytes) |

Format values: **DXT1 = 132**, **DXT5 = 136**, **ARGB8 = 144** (raw BGRA/uncompressed),
**DXT1_OTHER = 196** (decoded as DXT1 too). FourCC equivalents used when writing DDS:
DXT1 `0x31545844`, DXT3 `0x33545844`, DXT5 `0x35545844`. The Python decoder handles
DXT1/DXT3/DXT5 and passes ARGB8 through raw; the MaxScript builds a DDS header and dumps the
payload. Cubemaps exist (the MaxScript special-cases `*cube*` filenames).

### Coordinates

TDU2 world/model space is **Y-up**; Blender is Z-up, so import/export rotate (the MaxScript
phrases it as "rotate everything +90° on X"). Conversion lives in `operators.py`
(`_yup_to_zup` / `_zup_to_yup`); the binary formats carry Y-up data verbatim.

### TDU1 vs TDU2

`.2DM` and `.2DB` are **identical between TDU1 and TDU2** — one parser serves both. Only the
geometry container differs. Among the ZModeler plugins, two named "TDU1" produce `.3dg/.3dd`
and `TestDriveUnlimited2.zmf` is the real TDU2 one. TDU2 adds more texture layers (26+ vs
TDU1's 10), listed above.

## Build steps

The parsers are read-only data tools; "build" here means reproduce the extraction + parse.

1. Extract the vehicle/level `.bnk` with Krom's bnk extractor → a folder of `.3dg`, `.3dd`,
   `.2dm`, `.2db`.
2. Python parse (no Blender, no game):
   ```python
   import sys; sys.path.insert(0, "io_scene_tdu2")  # package dir
   from parser import TDU2ModelParser, TDU2MaterialParser, TDU2TextureParser
   model = TDU2ModelParser.parse("car.3DG")          # .segments, .meshes (positions/normals/uvs/triangles)
   mats  = TDU2MaterialParser.parse_to_materials("car.2DM")   # colours + 32-byte layer rows
   tex   = TDU2TextureParser.parse("body.2DB")       # header + raw image_data
   from dds import decode_2db_texture                # -> RGBA bytearray
   rgba  = decode_2db_texture(tex)
   ```
3. Blender path: copy `io_scene_tdu2/` into the addons dir, enable "Import-Export: TDU2
   Scene", put `.3dg` + `.2dm` + all `.2db` in one folder, File → Import → TDU2 Model. Switch
   to Material Preview/Rendered to see textures (Solid viewport may not show them).
4. 3ds Max cross-check (if you have Max): run `TDU2_mesh_import v2.1.mcr` after `TDU_mesh_extractor.mcr`,
   point it at the same folder, and rotate +90° X.

## Verification

- **Cross-implementation agreement is the oracle.** The Python parser and the independent
  3ds Max MaxScript agree on the 16-byte segment header, the `next_segment_ptr` child rule,
  the `PRIM` offsets pointing at `DXVB`/`DXIB` by absolute file position, the 80-byte `.2DB`
  header and format codes (132/136/144), and the 32-byte `.2DM` layer rows. Two independently
  written readers landing on the same offsets is strong evidence the layouts are right.
- `.3DG` `size` is checked against the actual byte length; a mismatch raises.
- `REAL`-block counts and `HASH` entry count both divide their payloads exactly by 16.
- **What I did NOT verify:** I did not run the game, did not render an exported `.3DG` in-game,
  and did not repack any asset back into a `.bnk`. Export correctness is **unproven** (see
  Gotcha 5 and Open questions). The bounding-sphere fields are read as integers; I did not
  confirm their scale/units.

## Gotchas

1. **Symptom:** every mesh in a car imports with the same material / "Mat_4". **Cause:**
   `PRIM.mat_id` is `4` for all prims in the shipped data — it is not a material index.
   **Fix:** assign materials by matching the `.2DM` layer `texture_name` (suffix like
   `BODY_LR`) against the `.3DG` `HASH` group name, with display-name and keyword fallbacks.
2. **Symptom:** garbage or unreadable group/material/texture names. **Cause:** the 8-byte
   names are a *sum-mod-8 mangling* (or plain ASCII with null/space padding), not ASCII.
   **Fix:** match on raw bytes; decode via the sum dictionary and normalise trailing `0x20`→`0x00`
   before lookup. Unknown keys stay `UNK_<hex>` — expected, not a bug.
3. **Symptom:** normals look wrong / are declared unreliable by the importer. **Cause:**
   normals are **half-floats** (6 bytes + 2 pad) and the original MaxScript simply skips them.
   **Fix:** read them as IEEE-754 `float16` triplets (`half_to_float`); don't read them as
   `float3`.
4. **Symptom:** UVs come out scrambled or on the wrong vertices. **Cause:** UVs live in one of
   two strides, selected by the `uv_loc` word — `0xF000` nibble = UVs interleaved with
   positions; `0xF00` nibble = UVs after normals/colours. **Fix:** branch on the flags; also
   negate V if you want MaxScript-identical orientation.
5. **Symptom:** triangles are inside-out or the strip produces extra faces. **Cause:** the
   index buffer is a D3D **triangle strip** with alternating winding. **Fix:** emit
   `(j,j+1,j+2)` for even `j` and `(j,j+2,j+1)` for odd `j`, and drop degenerate triangles.
   (Suspect export issue: the writer sets `uv_loc=0x1000` — "UV with positions" — while
   actually appending UVs after normals in the main stride; treat exported UVs as unverified.)
6. **Symptom:** vertex data drifts into nonsense after the first few vertices. **Cause:** the
   buffer is split into a *float region* (positions + optional UV/bones) and a *main region*
   (8-byte normals, 4-byte colour, UVs, tangents, bi-normals) with different strides.
   **Fix:** compute both strides from the flag bytes; the Python parser also clamps `n_verts`
   to what the remaining bytes can hold, which is why a bad stride degrades instead of crashing.
7. **Symptom:** the model is rotated 90° / lying on its side. **Cause:** TDU2 is **Y-up**,
   the DCC tool is **Z-up**. **Fix:** rotate +90° about X (or run the `_yup_to_zup` helper).
   This is expected, not a parse error.
8. **Symptom:** a `.2DB` decodes to garbage. **Cause:** the payload format code at header
   offset 48 is one of 132 (DXT1), 136 (DXT5), 144 (ARGB8 raw), or 196 (DXT1 variant), and
   the image starts at byte 80. **Fix:** switch on `param7`; pass ARGB8 through undecoded.
   Note implementations disagree on the "size" field's base: the Python parser takes image
   length as `size(@8) - 80`, the MaxScript reads a size at @28 and subtracts 64 — reconcile
   against a known asset before trusting a length.
9. **Symptom:** the README says export "not yet functional" but `parser.py` clearly contains
   `TDU2ModelWriter`/`TDU2MaterialWriter`/`TDU2TextureWriter`. **Cause:** the README is stale;
   `AGENTS.md` states export is implemented. **Fix:** trust the code, not the README — but
   because no export has been round-tripped into the game, keep it marked unverified.

## Assets

None generated. All work was reading existing game data and existing parsers. No models,
textures, or audio were produced.

## Cost and time

Single session; no API-heavy generation. All findings are from static inspection of the
local parser sources, no game launch and no executable run.

## Open questions

- **Export round-trip is unproven.** The writer code exists but nothing was repacked into a
  `.bnk` and loaded in-game. The suspected `uv_loc` mismatch (Gotcha 5) should be fixed and a
  written `.3DG` reloaded before calling export working.
- **`.2DB` size-field semantics conflict** between the two implementations (`size@8 − 80` vs
  `field@28 − 64`). Which is authoritative needs one known-good asset to settle.
- **Bounding-sphere fields** (`bound_radius` u16, `bound_x/y/z` s16) are read but their scale
  and whether they are integer-quantised world units was not confirmed.
- **`.3DD` scene layer** (hierarchy/instances/matrices, read by the MaxScript `buildScene`
  path) is not covered by the Python parser — only `.3DG` geometry is. A `.3DD` parse would
  give instance transforms and combine multiple `.3DG` into a full car.
- **`n_type` in `DXIB`** and several `.2DB`/`.2DM` "unk" words remain unnamed.
