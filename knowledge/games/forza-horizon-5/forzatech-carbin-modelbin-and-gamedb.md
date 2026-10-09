---
kind: game
title: "ForzaTech car assets: .carbin/.modelbin/.vfont, .ca2 archives and the GameDB.slt crypto"
game: "Forza Horizon 5"
games_also: ["Forza Horizon 4", "Forza Horizon 3", "Forza Motorsport 7", "Forza Motorsport (2023)", "Forza Motorsport 6: Apex"]
game_version: "FH5 v1.405.2.0 (Steam) tooling target; crypto supports FH5 v1.614.70.0 and earlier"
platform: windows
engine: unknown
route: data
tools: ["Blender 4.2 (carbin_importer.py, modelbin_importer.py, vfont_importer.py)", "ImHex v1.30.1 (patterns/)", "Node.js 18 (carbin_converter.mjs, string_extractor.mjs)", "ca2_extractor.py (python zlib)", "ForzaTech-crypto-tool (CryptoTool.exe, boost 1.82.0)", "3DSimED 3.2c"]
anti_cheat: "FH5 is online with anti-cheat. This note only reads an offline copy of the user's own game rip; nothing is injected into a running game and no protection is defeated."
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links: ["https://web.archive.org/web/20231023061958/https://forum.xentax.com/viewtopic.php?t=4256", "https://github.com/Nenkai/010GameTemplates/blob/main/Forza/TFIT.bt"]
tags: ["forzatech", "carbin", "modelbin", "vfont", "gamedb", "tfit", "arxan", "transformatit", "archive", "blender", "imhex"]
---

# ForzaTech car assets: .carbin/.modelbin/.vfont, .ca2 archives and the GameDB.slt crypto

> This note records the *file-format and crypto* knowledge behind extracting cars from
> ForzaTech titles (FH2–FH5, FM5–FM2023). Two public tools are the sources: Doliman100's
> Blender/Node/ImHex extraction toolkit (`ForzaTech-extraction-tools`) and a separate TFIT crypto tool
> (`ForzaTech-encryption-tool`) — credited in plain text, not linked here. It describes how a car rip
> is laid out, how the three asset containers are structured, how `GameDB.slt` is decrypted, and where
> support stops. Nothing here was executed against game data — it is a documentation pass over read
> sources, and the material path is explicitly partial.

## Setup

- Titles covered by the sources: Forza Motorsport 5/6/6Apex/7/2023, Forza Horizon 2/3/4/5.
- Scripts run **inside Blender 4.2** (Scripting tab → New Text → paste → Run). The README warns a
  user mentioned Blender 5.1.2 and API adjustments may be needed.
- ImHex **v1.30.1+** for the `.hexpat`/`.bt` patterns.
- Node **v18** for the two `.mjs` scripts.
- Crypto tool is a Windows `CryptoTool.exe` needing **boost 1.82.0**.
- The extraction toolkit and crypto tool are **separate repos**; GameDB decryption is external and
  must happen before the car importer is useful (unless `use_db = False`).
- Environment the sources were tested on: FH5 v1.405.2.0 (Steam), FH4 v1.466.445.0 (Steam),
  FH3 v1.0.37.2 (UWP).

## Route and why

- **Route: data.** Cars are plain resource files; the work is deserializing container formats, not
  hooking the running game. The only "protection" on the path is the file encryption/obfuscation on
  `gamedbRC.slt`, which is a static transform.
- Considered but not taken: native patching to fish assets out of memory. The tools show the data
  path is sufficient for meshes, LODs, wheels and (partially) materials.
- Two-stage pipeline is deliberate:
  1. **Crypto tool** decrypts `gamedbRC.slt`.
  2. **Extraction toolkit** reads the rip for geometry; the decrypted GameDB supplies the numeric
     car metadata (wheel size, track, wheelbase) that the files themselves don't carry.
- `.carbin` conversion exists because modern `3DSimED` can't read FH5/FM2023 files: a small
  Node script rewrites the container to an older dialect 3DSimED does understand.

## How the game works (what we had to learn)

### Rip folder structure (a hard requirement)

The importer resolves paths by string, so the rip must keep the original tree:

- `Media\Cars\CAR_NAME\CAR_NAME.carbin` — the car descriptor.
- Meshes live under the car's `scene\...` folders as `.modelbin` (plus `_skeleton.modelbin`).
- **FM7 and later:** move the contents of the `Base` and `PCFamily` folders *directly into* `Media`.
- Unzip `Materials_pri_*.zip` into a `Materials` folder.
- Decrypted GameDB comes from `Media\Stripped\gamedbRC.slt` and may sit outside the game folder.
- `game:` is a mount point inside swatch/material paths (e.g.
  `Game:\Media\cars\_library\materials\exterior_misc\carPaint_livery.materialbin`); the resolver
  currently just strips the `game:` prefix and appends to the rip root (a TODO admits directory
  handling is incomplete).

### `.carbin` — the car descriptor

- Root chunk carries a type: `05`/`06` for FH5 variants and `10`/`11` for FM (older titles used
  the same idea). Root holds a name, a skeleton path, then two model arrays (`ChunkA`/`blockB` and
  `ChunkB`/`blockC`; blockC is the upgrade-parts block).
- A **Model** chunk has a type that identifies the dialect: `16` = FH4, `17` = FM7, `18` = FH5,
  `21` = FM2023 (per the converter's assumptions), followed by a path, a parent-bone name, a
  materials array (each material = name + data string), a textures array, swatches, and a
  `partName`.
- **The unrecognized modern layout.** FH5/FM2023 add bytes the older parser doesn't expect. The
  converter's entire trick is: switch model type to the older value, replace the root type byte
  with `05`, and **drop 5 bytes at the end of each model chunk**. Field order between FH and FM
  also differs (FH5 puts a 4-byte sequence before the 16-byte one; FM does the reverse).
- Older `3DSimED`-incompatible `.materialbin` is a separate modern change, so the converter prints
  many skipped-material warnings.

### `.modelbin` — the mesh container

- A `Bundle` tagged multichar `'Grub'` (`0x47727562`), versioned (tool supports up to 1.1; 1.1+
  switches the blob count from `u16` to `u32`). Blobs are keyed by tag and stored in an
  unordered-multimap; each blob has metadata (`Id`, `Name`, `TXCH`) and a data block.
- Blob tags the importer handles: `Skel` (skeleton), `Mrph` (morph), `MatI` (material info),
  `Mesh`, `IndB` (index buffer), `VLay` (vertex layout), `VerB` (vertex buffer), `Skin`, `MBuf`,
  `Modl` (the model blob).
- The **Model** blob begins with mesh/buffer/vertex-layout/material counts, a
  `LODFlags` field (`levels_of_detail`), and — from blob version 1.2 — a `decompress_flags` byte.
  A newer FH5 `Modl` blob version is noted as a distinct case.
- **Vertex layout** mirrors D3D12: a list of semantic name strings, then
  `D3D12_INPUT_ELEMENT_DESC`-style entries (semantic index, input slot, format). This is what
  lets a generic `modelbin_importer.py` read any mesh — cars, props, characters, buildings.
- Importer features that fall out of this: original mesh names, LODs (`LODS`, `LOD0`, `LOD1`, …),
  normals/UVs, draw-group filtering (exterior, cockpit, shadow, hood, windshield reflection),
  hiding transparent parts (windows, wheel blur) by render-pass flag, and optional quadrangulation
  matching the `3DSimED > .3ds > 3ds Max` pipeline.

### `.vfont` — bitmap and vector fonts

`vfont_importer.py` reads the font header (name, char count, then win/typo/hhead ascent-descent,
line gap, em size, capital height), a per-character width table, then glyphs. Each glyph has
`f16` vertices, **two** UV sets, and a 16-bit index buffer. The second UV set encodes curvature, so
with `is_vector = True` the script reconstructs quadratic Bézier outlines from the UVs and converts
them to cubic Bézier splines; otherwise it builds a plain UV-mapped mesh. It lays glyphs out
10-per-row using the advance derived from win ascent+descent over em size.

### `.ca2` / `.xb2` — archived containers

`ca2_extractor.py` documents and implements the rule: a `.ca2` (resp. `.xb2`) is a **concatenation
of 4 MB chunks of a `.cab` (resp. `.xbp`) file, each zlib-compressed and aligned to 2048 bytes**.
The decompressor loops `zlib.decompressobj()`, writes the decompressed chunk, uses
`unused_data` to find the next chunk, and masks the offset to 2048-byte alignment:

```python
# essence of ca2_extractor.py
d_stream = zlib.decompressobj()
out = d_stream.decompress(buf)
offset = len(d_stream.unused_data) & ~0x7FF   # 2048-byte alignment
if offset == 0: break
buf = buf[-offset:]
```

### `GameDB.slt` — the crypto (TFIT)

- Path: `Media\Stripped\gamedbRC.slt`. It is needed for correct **wheel scaling/positioning** and
  tire selection; without it you fall back to manual values.
- FH5 executable reference (build CRC32 `BFCEECA8`) shows the call site
  `call DeobfuscateGameDB(_, _, destination, size, _)` at `0x00000001408FCFFE`.
- **Two layers:**
  1. **Arxan TransformIT (GuardIT)** — block encryption with a MAC.
  2. **CRC-32-based obfuscation** — a second pass over the decrypted bytes.
- **TFIT file structure:** `u8[16] IV`, `u32 padding_size` (unencrypted), `u8[16]` header MAC
  (unencrypted), then `DataBlock`s of `u8[0x200 or 0x20000]` encrypted payload + `u8[16]` MAC of
  the decrypted block (MAC itself encrypted). FH headers add a leading `u32 data_size` and a
  trailing `u32 padding_size`; FM headers only add `u32 data_size`.
- The tool auto-detects game and key by trying candidate keys and checking the MAC, so the caller
  doesn't pass a game unless encrypting. Key types include `SFS` (`media\sfsdata`), `GameDB`,
  `File`/`ConfigFile` (`.zip`/`.xml`/`.ini`) and others. Only the GameDB decrypt path is used here.
- **Obfuscation algorithm** (`obfuscation.h`): a stateful pass keyed by a `uint32 seed` and a
  256-byte CRC32 mapping table. For each aligned offset it computes
  `step = seed + (seed+1) * (offset/4)`, then for each dword sets `hash = CustomCRC32(step)` and
  XORs byte-by-byte, shifting `hash >>= 8`; `step += seed+1` per dword. `CustomCRC32` is a
  standard CRC-32 over the four bytes, but with a table-index indirection — and the quirk that
  **FM6Apex–FH4 do not cast the index to `uint8_t`**, while later titles do.
- Coverage ceiling: crypto supports **FH5 up to v1.614.70.0**. The extraction README separately
  notes FH5 **v1.642.644.0 and later** and FM2023 no longer ship a usable GameDB, so those cars
  need `use_db = False` and manual wheel values.
- `.zip` support targets files stored with **compression method 22**; when the tool rewrites those
  entries it changes the method to `8` and writes the decrypted payload.
- String tables `Media\Stripped\StringTables\EN\*.str` relate to gamedb tables: version `00 04`,
  a table-name buffer, then `StringInfo` entries whose id is the first byte of a placeholder-name
  hash.

### Shaders (context)

`Media\_library\Shaders\*\*.shaderbin` holds compiled HLSL: **DXBC** (FH3) and **DXIL** (FH5).
Types include `WheelBlurScenario`, `CarShadowDepthLightScenario`, `SimpleCarLightScenario`, and
`CarLightScenario` (Morphing/Skinning variants). DXBC disassembles with the Windows SDK `fxc
/dumpbin` using the `.pc.vso/pso` variants (Durango ones error); decompilation used the
`HLSLDecompiler` project, again picking `.durango.vso` there.

## Build steps

1. Rip the game with the original folder tree intact (`Media\Cars\NAME\NAME.carbin`, `scene\...`).
2. Decrypt the GameDB:
   ```
   CryptoTool.exe -i"...\media\Stripped\gamedbRC.slt" -o"gamedbRC.slt"
   ```
   For FH5 ≤ v1.614.70.0. Otherwise skip and use `use_db = False`.
3. Lay out the rip: FM7+ → merge `Base`/`PCFamily` into `Media`; unzip `Materials_pri_*.zip` into
   `Materials`.
4. In Blender 4.2, paste `carbin_importer.py`; set `game_path` (rip root), `db_path` (decrypted
   slt), `media_name`; Run. For a bare `.modelbin`, use `modelbin_importer.py` with a direct path.
5. Game auto-detection heuristics pick the dialect; disable with `use_db = False` + manual values
   when no GameDB exists.
6. Optional: convert a copy of the `.carbin` for 3DSimED:
   ```
   node carbin_converter.mjs "D:\games\rips\FH5\media\Cars\NUL_Car_00\NUL_Car_00.carbin.bak"
   ```
   (rename the original to `.carbin.bak` first; the script refuses a non-`.bak` input).
7. Optional research: `string_extractor.mjs` dumps `<u16/u32 length><bytes>` strings; ImHex opens
   `patterns/*.hexpat|*.bt`.

## Verification

- **What the sources establish:** the formats above are documented by the scripts that parse real
  files, and the crypto algorithm is transcribed with the exact reverse-engineered addresses
  (`DeobfuscateGameDB` call site; `Obfuscate` at `0x0000000140912AB0`; `CustomCRC32` at
  `0x0000000140FF9050`). The importer's feature list (LODs, draw groups, quadrangulation) is
  framed as working against named cars.
- **What the sources do NOT establish, and I did not run:** nothing was executed against game data
  in this note. No end-to-end decrypt→import→render round-trip was reproduced. Material support is
  explicitly partial (see Gotchas 1), and several cars carry noted defects in the importer comments
  (`AUD_S4_13` normals, `LAM_Countach_88` missing controlArm bone, `MOR_3Wheeler_14` no rear
  brakes, `NAP_Railton_33` missing BrakePart, `MER_G63AMG6x6_14` no LM/RM wheels).
- Blender **5.1.2** compatibility is unverified; the scripts target 4.2.

## Gotchas

1. **Symptom.** Materials come out wrong or not at all. **Cause:** material support is partial — the
   README states only `FOR_FocusRSRX_16` (an FH3 car) was validated, and the modern `.materialbin`
   format isn't understood. **Fix:** leave `use_materials = False` (default); treat materials as
   experimental (`shader_processor` 1 = per-shader, 2 = universal shader).
2. **Symptom.** Wheels are the wrong size or sit in the wrong place. **Cause:** scaling/positioning
   needs the GameDB tables (`Data_Car`, `Data_CarBody`: `FrontTireWidthMM`, `FrontWheelDiameterIN`,
   `ModelWheelbase`, track values). **Fix:** decrypt `gamedbRC.slt` and set `db_path`; otherwise
   `use_db = False` and enter manual values.
3. **Symptom.** Importer can't find meshes/materials. **Cause:** the resolver does string matching
   on the folder tree and on the `game:` mount prefix. **Fix:** preserve the exact original
   `Media\Cars\...` structure; for FM7+ merge `Base`/`PCFamily` into `Media`; unzip the Materials
   archive into `Materials`.
4. **Symptom.** `CryptoTool` reports "None of the keys matched." **Cause:** all candidate keys
   failed MAC verification — wrong game/key, a newer title, or corrupt input. **Fix:** confirm the
   title is within coverage (FH5 ≤ v1.614.70.0); note the tool ships **without key files**.
5. **Symptom.** `.carbin` won't open in 3DSimED. **Cause:** FH5/FM2023 dialects (model type 18/21)
   and the modern `.materialbin` are unsupported by 3DSimED 3.2c. **Fix:** run
   `carbin_converter.mjs` (rewrites root type to `05`, switches model type, drops 5 trailing bytes
   per model chunk) and expect skipped-material warnings.
6. **Symptom.** Decompressed `.ca2` is garbage after the first 4 MB. **Cause:** treating it as one
   zlib stream. **Fix:** it's independent 4 MB chunks aligned to 2048; decompress sequentially,
   advancing by `len(unused_data) & ~0x7FF` (see `ca2_extractor.py`).

## Assets

- No game files, binaries, keys or dumps are included here. The crypto tool deliberately **omits**
  key files.
- Tool sources: Doliman100's `ForzaTech-extraction-tools` and `ForzaTech-encryption-tool` (public
  GitHub; credited in plain text, not linked).

## Cost and time

- A documentation pass only: reading two repos (README/AGENTS + three Blender importers, two Node
  scripts, the crypto `main/obfuscation`, and the pattern index). No Blender runs, no decryption,
  no game data touched. Wall-clock: a single session.

## Open questions

- Does the material pipeline work beyond the single tested FH3 car, and would a per-shader
  processor (mode 1) or a universal shader (mode 2) close the gap?
- Exact byte layout of the `5 unnecessary bytes` the converter drops, and of the newer FH5 `Modl`
  blob version — both are handled bluntly, not understood.
- Whether FH5 v1.614.70.0 → v1.642.644.0+ GameDB encryption changed, or the keys simply aren't
  public yet.
- Importer correctness on cars the comments flag as defective (normals, missing bones, missing
  brake parts) — no oracle run here.
- Whether the `game:` mount-point resolver's TODO cases (nested `media` roots) matter in practice.
