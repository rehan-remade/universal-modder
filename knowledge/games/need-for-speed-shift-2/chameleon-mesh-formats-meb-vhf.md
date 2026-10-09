---
kind: game
title: "Reading Chameleon engine meshes: .meb/.imb and .vhf (.bml/.sgb/.sgx) from NFS Shift 2"
game: "Need for Speed: Shift 2 Unleashed"
games_also: ["Need for Speed: Shift", "Project CARS 1/2", "Test Drive: Ferrari Racing Legends"]
game_version: "retail PC (BFF archives), no specific build pinned"
platform: linux
engine: unknown
route: data
tools: ["Blender 5.x", "meb_import (Blender addon)", "vhf_import (Blender addon)", "QuickBMS + nfsshift.bms", "SMS Importer 3.1c (3ds Max)"]
anti_cheat: "none — offline asset extraction, nothing run in-game"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links:
  - "https://github.com/auvy/nfs-shift-to-blender"
  - "https://www.tapatalk.com/groups/kottons_chop_shop/ti-scp-ti-sms-model-importer-t3217.html"
  - "https://aluigi.altervista.org/bms/nfsshift.bms"
tags: [chameleon, madness-engine, meb, imb, vhf, bml, sgb, sgx, mesh, big-endian, little-endian, vprop, import]
---

# Reading Chameleon engine meshes: .meb/.imb and .vhf (.bml/.sgb/.sgx) from NFS Shift 2

> Field notes from building/repairing Blender importers for Slightly Mad Studios' Chameleon engine
> meshes. `.meb`/`.imb` are binary meshes; `.vhf` is an XML transform file; `.bml` (cars) and
> `.sgb`/`.sgx` (tracks) are containers the original 3ds Max importer also reads. The Blender addons
> import meshes and transforms, but the container formats themselves are only referenced, not parsed.
> Status is **in-progress**: import path is understood well enough to reproduce the wire layout, but the
> write/repack direction is untried and container parsing lives in the MaxScript.

## Setup

- Game assets live in `.BFF` archives; extract them with QuickBMS + `nfsshift.bms`
  (see `techniques/quickbms-linux-xmemdecompress-lzx-fork.md` for the Linux build fix — the same
  fork was fixed *because* Shift `.bff` entries are TYPE=2 XMemDecompress/LZX).
- Tooling runs in **Blender 5.x** on Linux; the addons are plain addon packages, not pip packages.
  Symlink `meb_import/` and `vhf_import/` into `~/.config/blender/5.1/scripts/addons/`.
- The authoritative format description is the 3ds Max script
  `SMS_import_v3.1c.mzp` → `SMS_import.mcr` (`importPart`, ~line 832), by Chipicao & vagos21. It
  covers `.bml`/`.vhf` (cars) and `.sgb`/`.sgx` (tracks) plus standalone `.meb`/`.imb`. The Blender
  port only re-implements the `.meb` reader and a `.vhf` XML transform applier.
- MaxScript docs: https://help.autodesk.com/view/MAXDEV/2026/ENU/?guid=GUID-6FC81BE7-58FF-4C63-8362-0BDCFA9F904C

## Route and why

Route is **data** — parse the shipped asset files directly and import into Blender; no DLL injection,
no runtime hooks.

Why data: Chameleon stores self-contained mesh files, so an offline parser is enough to get geometry,
UVs, normals, vertex colors and material paths. Alternatives considered:

- **Wrap the 3ds Max importer** (`SMS_Importer_3.1c`) — rejected because it needs 3ds Max and the
  `.mzp` is a binary archive; the Blender port gives a maintainable, scriptable path.
- **Reverse the ZModeler filter** (`nfsshift.zmf`, PE32) — noted as a fallback for edge cases, but the
  MaxScript already documents the format.
- **Container parsing (`.bml`/`.sgb`/`.sgx`)** — not yet ported to Blender; only the standalone
  `.meb`/`.imb` mesh reader exists. Uses the MaxScript as reference.

## How the game works (what we had to learn)

### Mesh: `.meb` / `.imb` (Chameleon / Madness engine)

Files are **big-endian or little-endian per file**; there is no fixed global convention. A UTF-8 BOM
(`EF BB BF`) may prefix the file and must be skipped first.

Header / counters:

```
[3 bytes]     optional UTF-8 BOM
[8 bytes]     header; byte[4] bit0 (b5) = has skeleton/skin block
[null-str]    partName
[uint32]      numVerts
[uint32]      numVertProps      # vertex attribute stream count
[uint32]      numPrims          # sub-mesh / material count
[10×float]    unknown
[if b5]       numBones:u32, numChars:u32, char[numChars] names, numBones×48B matrices
```

- **Endianness detection**: BE files place the counters at a `pos % 4 == 0` boundary; LE files at
  `pos % 4 == 3` (i.e. after the null terminator with LE padding). Both probes are validated by
  sanity-checking `numVerts` (1..500000), `numVertProps` (1..50), `numPrims` (0..500), the skin block
  sizes, and finally a recognisable vertex-property tag.
- **Vertex properties are interleaved**: the stream is `(triple, data, triple, data, …)`, each triple
  being `3 × uint32` tag digits followed immediately by that property's data for every vertex. Reading
  all triples first (the old bug) desynchronises the stream — see Gotchas.
- **Tag formula**: MaxScript concatenates the digits as strings; the equivalent integer is
  `r1*100 + r2*10 + r3` (e.g. digits 2,0,0 → 200), **not** `r1*1000 + r2*100 + r3`.
- **Known property tags** and strides:
  - `200` positions `3×float` (xyz), `220` normals `3×float`;
  - `460` colors `4×byte` RGBA, `461` colors2 skip 4B;
  - `240`/`250` tangent skip 12B;
  - `130`–`134` UV `2×float` (v stored as `1-v` on import), `230`–`234` UVW `3×float` (skip last 4B);
  - `033` zeroes skip 4B, `580` bone indices skip 4B, `310` bone weights skip 16B.
- **Per-primitive data is always big-endian**, even in LE files. Use
  `struct.unpack_from(">I"/">H", …)` explicitly — a stream object carrying the detected file endianness
  would be wrong here.
- Per primitive: `[null-str] material .mtx path`, pad4, `numFaces:u32` (BE, with a doubled-read
  fallback if zero), then the skin-shorts slot, pad4, then `numFaces × 3 × BE u16` face indices.
- The face data **does not stop cleanly at `numFaces`**: the reader walks valid BE u16 triples until
  the next primitive's path (or EOF). The last ~44 bytes before the next path are `2×u16` refs +
  `10×float` unknown. Single out-of-range indices are clamped to `numVerts-1`; a triple with 2+ OOB
  indices ends the face loop.
- **Coordinate swizzle on import**: positions/normals stored `(x,y,z)` imported as `(x,z,y)`; face
  winding reversed `(i3,i2,i1)`; UV `v = 1-v`.
- Material paths are `\`-separated Windows paths (e.g. `vehicles\Dodge_ViperSRT10\...mtx`)
  found by scanning the raw bytes for `0x5C` and validating candidates (see Path Scanner gotcha).

### Transform: `.vhf` (XML)

`.vhf` is XML with `<MATRIX>` and `<NODE>` elements. Each matrix has an `Offset` (translation, 3
floats) and `Orientation` (quaternion, 4 floats); each node names a part and a `MatrixNumber`
referencing a matrix `id`. The Blender importer applies, per matched object, translation
`(Offset[0], Offset[2], Offset[1])` (swizzled) and quaternion `(Orientation[3], -Orientation[0],
-Orientation[2], -Orientation[1])` (w,x,y,z order with sign flips).

### Containers (cars/tracks) — referenced, not parsed here

- `.bml` — car definition container, BLMY chunk format referencing `.meb` files.
- `.sgb` / `.sgx` — track scene/geometry containers with instances.
Only the MaxScript handles these; the Blender port reads standalone `.meb`/`.imb` meshes.

## Build steps

1. Extract `.BFF` archives: `QuickBMS` + `nfsshift.bms`. Entry offset `0x12d` is `0x00` (unencrypted);
   entries are TYPE=2 (XMemDecompress, LZX window 17, 512K partitions).
2. Install the Blender addons:
   ```sh
   cd meb_import && zip -r ../meb_import.zip .
   # or symlink:
   ln -s "$PWD/meb_import" ~/.config/blender/5.1/scripts/addons/
   ```
   (same for `vhf_import`; both are addon directories with `bl_info`).
3. In Blender: `File > Import > Shift 2 mesh (.meb)` — supports batch folder import; meshes land in a
   collection named `Shift2_Import` (hard-coded, `import_meb.py:377`).
4. To position parts: `File > Import > Shift 2 transform (.vhf)` — target the collection holding the
   imported meshes (default collection name `"Coll"`).

## Verification

- The add-on repo's notes state the mesh reader is validated against real extracted `.meb` files by
  loading them in Blender and checking geometry, UV layers, normals and material assignments; this was
  **not** re-run here. A concrete oracle in those notes: the material path scanner finds all 13 paths
  in `dod_srt10_kit00_interior_cpit.meb` (Dodge Viper cockpit) at the recorded byte offsets.
- **Not verified**: any *write* path (no round-trip repack), container `.bml`/`.sgb`/`.sgx` parsing in
  Blender, and skeleton/bone-weight import (bone shorts and weights are skipped, not applied). The
  `.vhf` transform app was not verified against a rendered reference here.

## Gotchas

1. **Vprop stream turns to garbage after the first property.** **Symptom:** all vertex properties
   after positions are misread as bogus tags, and positions read from the wrong offset (e.g. 203 vs
   107). **Cause:** the format interleaves `(triple, data, triple, data, …)`; old code read all nine
   triples first (108 bytes) before any data. **Fix:** read each triple immediately followed by its
   per-vertex data.
2. **Tag numbers are off by a factor.** **Symptom:** property codes don't match the known table.
   **Cause:** the MaxScript concatenates digits as strings, not decimal place-shifts.
   **Fix:** use `r1*100 + r2*10 + r3`, not `r1*1000 + r2*100 + r3`.
3. **LE files decode to nonsense per-primitive fields.** **Symptom:** face counts/indices look huge.
   **Cause:** per-primitive fields are **always BE** even when the header/vprops are LE; a stream using
   the detected endianness is wrong here. **Fix:** `struct.unpack_from(">I"/">H", …)` for all
   per-primitive fields.
4. **Material paths go missing.** **Symptom:** the scanner jumps past real `\`-paths. **Cause:** the
   old code set `pos = end + 1` for *every* backslash; a `\` inside binary face data followed by a long
   null-free run skipped real paths. **Fix:** only advance past the null terminator for *accepted*
   paths; otherwise `pos += 1`. Acceptance also requires >25 bytes, dir name ≥3 chars, a `.`, ASCII,
   and >15 bytes from the last accepted path.
5. **Skeleton-only / truncated files crash the importer.** **Symptom:** `struct.error`. **Cause:** a
   large bone block can leave no room for mesh data. **Fix:** `_read_meb` catches `struct.error` and
   returns `None`; the caller silently skips ("no mesh data"). Also the shorts count is read as u16 at
   offset +2 (not a BE u32) so a nonzero "unknown" half doesn't poison it.
6. **Face loop overshoots into the next primitive.** **Symptom:** stray triangles / cross-material
   bleed. **Cause:** face data does not end at `numFaces`; it runs until the next path. **Fix:** keep
   reading BE u16 triples until the next path/EOF, clamp single OOB indices to `numVerts-1`, and stop on
   a triple with 2+ OOB indices.
7. **`.vhf` transforms don't find their meshes.** **Symptom:** "Didn't find <name>". **Cause:** object
   names differ from node names. **Fix:** the importer retries suffixed names `.001`…`.012`.
8. **Imported model faces the wrong way.** **Symptom:** mirrored/inside-out geometry or wrong UVs.
   **Cause:** Chameleon axes differ. **Fix:** swizzle positions/normals `(x,y,z)→(x,z,y)`, reverse
   winding `(i3,i2,i1)`, flip `v = 1-v`.

## Assets

No new art generated. The workflow converts shipped Chameleon meshes into Blender for viewing/edit.
Mesh import is rewritten with `from_pydata()` + bmesh (pattern borrowed from
ForzaTech-extraction-tools) instead of an OBJ intermediary.

## Cost and time

Not recorded — this note is derived from reading the existing repo (AGENTS.md, README, addon sources)
rather than a fresh modding session.

## Open questions

- Port `.bml` (BLMY chunk) container parsing to the Blender path so whole cars import without the
  MaxScript.
- Port `.sgb`/`.sgx` track containers incl. instances.
- Import skeleton/bone weights (`580` indices + `310` weights) — currently skipped.
- Is there a verified *write* path (repack) at all, or is the toolchain read-only? The BFF side has an
  LZX/XMemCompress-compatible compressor worth exploring.
- `.imb` vs `.meb` — assumed same layout; not separately verified here.
- Confirm whether an unpublished local `nfs/` forum-topic scrape contains any format docs beyond sample
  assets (survey: it is only topic folders with `.zip`/`.rar` payloads, no text notes — not useful for
  format research).
