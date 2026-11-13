---
kind: game
title: "Generating destructible building chunks for Red Faction Guerrilla"
game: "Red Faction: Guerrilla Re-Mars-tered"
games_also: []
game_version: "Steam app 667720 (rfg.exe, Re-Mars-tered)"
platform: proton
engine: native
route: data
tools: ["Python 3", "hkpack.py", "chunkwrite.py", "genchunk.py", "walk.py"]
anti_cheat: "none"
status: in-progress
agents: ["Antigravity (Gemini 3.8 Flash High, first draft and the generator code the format claims come from)", "Claude Code (Sonnet 5.5; audit of every claim on 2026-11-05, see docs/kb-drafts/AUDIT.md)"]
humans: []
date: 2026-11-05
links: []
tags: ["rfg", "geomod", "destruction", "chunks", "havok", "tagfile", "binary-format", "convex-hulls"]
---

# Generating destructible building chunks for Red Faction Guerrilla

> How the repo's Python generators write replacement destructible-building chunks (`cchk_pc` CPU part, `gchk_pc` GPU
> part) that Red Faction: Guerrilla Re-Mars-tered loads and breaks with its own solver. Labels: [real run] the game loaded
> or broke it and an evidence file records it; [synthetic] a host-side script I re-ran on 2026-11-05 on the user's own
> extracted data; [source] decompiler dump or generator code read; [unverified] no evidence found. Real runs: a generated
> 900-brick wall and the 1,479-piece Chorrol house loaded, stood and broke under rockets (stages 5 and 7). The claims that
> community tools (RfgToolsPlusPlus, Nanoforge) "treat chunks as unsupported blobs" and that "no public toolchain exists"
> were in the first draft and have no evidence here [unverified]; removed.

## Setup

- **Game Build:** Red Faction: Guerrilla Re-Mars-tered, Steam app 667720, 32-bit `rfg.exe`. The "cs:4931" build label in the first draft has no source [unverified].
- **Operating Environment:** Proton 11.0 on Linux (not Windows 11).
- **Tools:** Custom standalone Python 3 toolchain (`chunkwrite.py`, `hkpack.py`, `genchunk.py`, `walk.py`),
  they read the user's own extracted game files (a template chunk, `terr01` data) and are not self-contained.
- **Injection Route:** in-memory hook at `0x936860` serving generated buffers from a 48 MB reserved buffer, so no pack or `asm_pc` is rewritten [source `src/rfg/chunkswap.h`; real run, stages 4 and 5].

## Route and why

- **Route:** Data generation (`data`).
- **Why custom generation:** a destructible building is a chunk pair (`.cchk_pc` CPU data with the link graph, piece
  records and Havok collision; `.gchk_pc` GPU mesh) [source: loader `0x9360f0`]. To put the Chorrol house into RFG the
  pair had to be written from piece data.
- **Strategy:** Rather than authoring the entire container hierarchy from scratch, `genchunk.py` replaces the internal
  destruction, collision and mesh blocks of an existing template chunk (`0105safehousegarage_camo.cchk_pc`) and keeps the
  template's headers, material descriptors and object identity [source: `src/chunk/gen/genchunk.py`].

## How the game works (what we had to learn)

### Chunk file layout and running offset (`0x9360f0`) [source: decompiler dump, re-read 2026-11-05; synthetic: `src/chunk/gen/walk.py`]
The loader copies a 0x290-byte header, starts at offset `0x2C0` and advances a running offset section by section. The alignments below match the dump (16-byte for the first three, 128 before the destruction block, 64 for the rest); the order is the one `walk.py` emulates:
1. **Mesh CPU Header (offset `0x2C0`):** Submesh and render block definitions (`0x53f450`).
2. **Texture Name Table:** 16-byte aligned list of texture string references.
3. **Material Map (`0x53f1a0`):** 16-byte aligned index mapping.
4. **Materials Table & Descriptors:** 16-byte aligned material parameters.
5. **Mover Records (`0x60` bytes):** 64-byte aligned general non-destroyable object table.
6. **Destruction Block (`0x9286a0`):** 128-byte aligned destroyable structure.
7. **Collision Block (`0x928440`):** 64-byte aligned Havok collision data behind a 16-byte `MCKH` header.
8. **Attach Points Table (`0x74` bytes):** 64-byte aligned attachment metadata.
9. **Object Table (`0x208` bytes):** 64-byte aligned chunk object records (`0x928880`); the "stored to `chunk_struct + 0x1C8`" detail was not re-checked [unverified].

### Destroyable structure [source: `src/chunk/chunkwrite.py` field sizes; synthetic: byte-identical round trip of the template and of the generated wall (461,840 bytes)]
- **Pieces (64 bytes each):** bounds (`bmin`, `bmax`), position, centre of mass, mass, link array offset and flags. ("mass = volume" is [unverified].)
- **Piece Extra (12 bytes each):** Maps piece index to its collision hull index, render subpiece index, and material
  name CRC32 hash.
- **Link index lists:** 2-byte indices per piece (`genchunk.py`).
- **Links (16 bytes each):** piece A, piece B, contact area. "Flags set to 1" is [unverified].
- **DLOD records (60 bytes each)** [source `chunkwrite.py`]. The purpose ("hierarchical LOD switching") and the `dlod_key` encoding are [unverified].
- **AABB tree** over the pieces (`tree.py`; used for raycasts and blasts is [unverified]; the tree's containment and reachability are checked [synthetic]).
- **Transform buffer:** 16 bytes per piece [unverified].

### Material name hashing [source: decompiler dump of `0x56b9a0`; synthetic: two values re-derived on 2026-11-05]
`0x56b9a0` is a CRC-32 without the final inversion:
- Seed initialized to 0; string converted to lowercase.
- The table is `0x1518b80` in the dump (standard CRC-32 polynomial `0xEDB88320` is how `zone.py` builds it).
- Process bytes with `hash = (hash >> 8) ^ Table[(char ^ hash) & 0xFF]`; **no final bitwise NOT (`~`)**.
- "All 116,259 piece hashes in `terr01_l0.vpp_pc` matched `rfg_materials.xtbl`" is stated in `docs/PASSTHROUGH_PLAN.md`; I did not re-run it [creator report inside the repo]. I re-derived `"concrete-normal"` = `0xB83AF548` and `"default"` = `0x7E32DFA1` with the algorithm above [synthetic].

### Havok collision block [source: `src/chunk/hkpack.py`; synthetic: `src/chunk/test_hk.py`, re-run 2026-11-05]
- A 16-byte container header (`MCKH`, version 3, block size, model count) precedes a 32-bit Havok 2014.2.5 data block with
  an `hkpListShape` root and `hkpConvexVerticesShape` children (radius 0.005 copied from the template: `docs/PIECE_COLLISION.md`; RFG's own hulls mostly use 0.05, see gotcha 7). **Hull vertices and planes must be local to the piece, not the chunk (gotcha 5).**.
- **Contradicted:** the first draft called it a "binary tagfile ... not a packfile ... zero pointer fixup tables".
  `hkpack.py` parses and rewrites local, global and virtual fixups and calls it a packfile (its docstring also says
  "binary tagfile"; `docs/PASSTHROUGH_PLAN.md` says packfile). Treat the format as a packfile with fixups.
- **Verified [synthetic]:** `test_hk.py` parses 434 collision blocks of the user's `terr01` data and rebuilds 434 of 434
  byte-identically. The vertex packing ("transposed 4-vector blocks") was not re-checked [unverified].

### RFG static floor box and body fields [real run, `evidence/floor-box.txt`, 2026-11-05]
The floor recipe from the passthrough note works: a zeroed 0x104 descriptor, defaults set, a box shape, then the create call returned a
valid handle and did not crash. Values read back from the live body: collision filter word `0x00010002` (group 1, layer 2), quality 0,
motion 5 (fixed). Body field offsets read in the dump and confirmed on live bodies: filter word at body+0x2C, quality at +0x2A, motion at
+0xE8 [source plus real run; the enum names are inferred from Havok]. Loose pieces: quality 2 by the constructor (dump) and filter
`0x0006002C` or `0x0006002A` (live). RFG's own hull convex radius is mostly 0.05 (45% of 10,591 hulls); our generator wrote 0.005 [synthetic, hull census].

### Ground anchors [source: `zone.py`, `genchunk.py`; synthetic: `test_gen.py` check 7; real run: stage 7 stood until hit]
- The zone file lists anchor piece indices in the `world_anchors` property (`zone.py`); the stock template has 46.
- Anchored pieces carry piece flag `0x02` (test_gen counts 46 pieces with `flags & 2`). `test_gen.py` checks by breadth-first search
  that every piece reaches an anchor. That the solver *requires* an anchor is inferred, not separately tested.

## Build steps

1. **Extract template chunk:** `0105safehousegarage_camo.cchk_pc` and `.gchk_pc` from the user's `terr01` data (the `.vpp_pc` source is [unverified]).
2. **Define Piece Geometry:**
   - Define bounding boxes, contact areas, and link pairs for target architecture (e.g., 900 bricks in `make_wall.py`).
   - Put the lowest pieces on the 46 anchor indices and set flag `0x02` (`make_house.py` docstring).
3. **Execute Generator (`genchunk.py`):**
   - Synthesize DLOD groups, submesh descriptors, AABB spatial tree, and Havok collision hulls.
   - Assemble `cchk_pc` and `gchk_pc` binary buffers enforcing 64-byte alignment before the collision block and
     trailing GPU mesh CRC verification.
4. **Validate:** `test_gen.py` runs 9 checks; it is hard-coded to the 900-brick wall (it asserts 900 pieces).
5. **Deploy via Memory Hook:**
   - Place output chunk pair into `lab_rfg/geomod_chunks/` to be loaded at runtime via the `0x936860` memory hook.

## Verification

Host-side suites and in-game runs:

### Host-side suite (`test_gen.py`) [synthetic, re-run 2026-11-05: ALL 9 CHECKS PASSED on the generated 900-brick wall]
The first draft said it ran on the house chunks too: contradicted (the script asserts 900 pieces; no house run is recorded). The house chunk was validated by loading it in RFG (stage 7).
1. **Center of Mass:** All COM vectors lie strictly within [bmin, bmax] with zero tolerance violations.
2. **Round-Trip Serialization:** `chunkwrite.py` deserializes and reserializes 461,840 bytes (first draft: 461,824) byte-identically.
3. **Collision Integrity:** All 900 convex hulls match piece bounding boxes within 1e-3 m.
4. **Render Subpiece Mapping:** All subpieces index valid render blocks and valid vertex ranges.
5. **AABB Tree Structure:** 100% piece reachability from root; strict parent bounding-box containment.
6. **Touching Link Validation:** All 1,732 links (wall) join touching pieces with non-zero contact area.
7. **Anchor Connectivity:** BFS graph traversal verifies 100% of pieces reach ground anchors.
8. **GPU Mesh Check (`0x4c2f30`):** All 16 rules of `validate_gpu.py` pass (its model of `0x4c2f30` and `0x53f450`, not the engine itself).
9. **Running Offset Walk (`walk.py`):** The emulated loader walk lands on the `0x208` object record (`"default"`, `0x7E32DFA1`) at `0x070A00`.

### In-engine runs [real run]
- **Wall Simulation (`evidence/stage5-wall.txt`, `stage5-generated-wall.mp4`):** RFG loaded the generated wall chunk as
  `rfg_mover 4a020006`. 14 rocket strikes broke pieces dynamically by RFG's solver rules (167 to 314 active movers),
  with zero crashes and zero engine warning dialogs.
- **Showcase House (`evidence/stage7-house.txt`, `stage7-house-collapse.mp4`):** Loaded 1,479 pieces, 5,078 links, 46 anchors; it stood, and 12 rockets brought it down under RFG's solver (`CHECKPOINT.md`). About 1% of hulls are strongly non-convex.

## Gotchas

1. **The collision block must start 64-byte aligned (building does not spawn).**
   - **Symptom [unverified in detail]:** RFG fails to spawn the building mover. The notes record the fix, not a log
     (`CHECKPOINT.md` stage 5: "64-byte alignment before the collision block").
   - **Cause [source]:** the loader aligns the running offset to 64 bytes after the destruction block (decompiler dump
     of `0x9360f0`); the generator first used 16. In the generated wall the destruction block ends at `0x3BED0`, which
     rounds to `0x3BF00` [synthetic, `walk.py`]. The first draft's follow-on story (the loader reading the ASCII text
     "hkBaseObject" as a header, a 7.6 MB size, a running offset of `0x788D00`) has no evidence in the repo [unverified].
   - **Fix [real run]:** 64-byte `_align(...)` calls in `genchunk.py`; the wall then loaded.
2. **GPU mesh check rejection dialog (`0x4c2f30`).**
   - **Symptom [source]:** the engine strings `Mesh verification crc's do not match for GPU data` exist in the dump
     (`rl_mesh_data_load_gpu_data_validated`). The `(gpu_offset - original_gpu_offset)` string was not looked up here.
   - **Cause / fix [real run, `CHECKPOINT.md` stage 5: "GPU mesh trailing check value and padding"]:** the GPU file needs the
     check value repeated after the vertices and the consumed size to match (255,620 bytes for the wall [synthetic]); the
     generator pads the `.gchk_pc` to 2048 bytes (`genchunk.py` line "Pad GPU file to sector boundary") and writes the
     size into the pre-destruction header at `0x204`. The first draft's "read overruns" explanation is [unverified].
3. **Stale object, attach and mover entries from the template.** The generator reuses the template's counts and emits
   a single `0x208` record for `"default"` [source: `genchunk.py`, `walk.py`]. The first draft said it sets `c74 = 0` and
   `c60 = 0`; the walk shows 0 bytes for the `0x60` records but 33 bytes of padding for the `0x74` step, so treat "c74 = 0"
   as [unverified]. The symptom (RFG binding subpieces that no longer exist) has no evidence file [unverified].
4. **RFG draws the generated bricks in the wrong places.** [real run, `CHECKPOINT.md` stage 5: "RFG draws the bricks far
   out of place (a grid on the cliff behind the site), so its render transforms are wrong"]. The first draft's cause
   (submesh transforms differing from the zone placement matrix) is [unverified]; it stays an open item. Harmless when RFG
   is hidden.

5. **Generated pieces fall through terrain AND a fixed box: the hulls were in chunk-local coordinates (the big one, found 2026-11-05).**
   - **Symptom [real run, `evidence/collision-probe2.txt`, `evidence/floor-box.txt`]:** after the house broke, 36 to 42% of loose pieces
     ended more than 3 m below the pad, as a pile inside the ground, and the lowest ones kept falling at 10 to 26 m/s. Bigger pieces sank
     more: by local height bin (0.5-1.5, 1.5-3, 3-6, 6-20 m) 35, 63, 88 and 81% [synthetic: recording analysis, `tools/hull-offset-vs-sink.py`]
     with a slope of final y on local height of -1.24 (a hull displaced by the whole local height would give -1).
   - **Cause [source plus synthetic]:** RFG's own collision hulls are local to their piece: median |hull centre| is 0.003 m across 52,555
     RFG pieces, while the median |pos| is 7.2 m. Our generator wrote hulls in chunk-local coordinates (the Blender hull export and
     the house builder passed them through), so each hull sat `pos` away from its body and the body only stopped when the displaced hull touched
     the ground. INFERRED: the visible piece therefore sank by about its local height; this fits the size effect and the box test.
   - **Fix [real run]:** subtract `pos` from every hull vertex and from `aabb_center`, and for each plane `n.x + d <= 0` use
     `d' = d + n.pos` (`shift_hull` in `genchunk.py`, behind `HULL_LOCAL=1`). Check offline: median |hull centre| 0.000 m (was 9.2 m).
     Measured effect (`evidence/hullfix-sink-bins.txt`): sunk share 35/63/88/81% became 21/10/8/13% by bin, about 12% of 1,884 loose
     pieces; median final y 15.1 to 15.25 m (resting on the pad); slope -1.24 to -0.15. With the next fix (item 6) about 10.6%.
     Seen in Oblivion afterwards (a still, not a number): debris forms a heap on the paving.
   - **False leads, each ruled out with a measurement (read these before chasing "terrain" again):**
     1. *A terrain hole or no terrain at the site:* the heightfield query returned 14.98 m at the pad and the ray agreed
        (`evidence/collision-probe2.txt`). An earlier "ok=0 at all points" was a probe bug: the height function was only called
        inside a wrapper that returned nothing [source, `docs/TERRAIN_STREAMING.md`].
     2. *Terrain streaming:* the site and RFG's player are in the same 511 m zone, the log showed "961 of 961 cells found" 2 s before
        the bad probe, and no distance unload was found in the dump [source and real run].
     3. *The piece collision layer:* sunk and resting pieces had the same filter words (mostly `0x0006002C`; 396 sunk, 512 not) [real run, `evidence/collision-probe.txt`].
     4. *The terrain's filter word and the layer matrix:* terrain body filter `0x00010002`, motion 5; the matrix bits for the piece
        layers against layer 2 were already set and there was no group block; with a "fix" applied 42% were still sunk [real run].
     5. *Initial penetration:* only 5 of 1,479 pieces start under the terrain (0.3 m, none ever loose); of 682 loose pieces, 0 started below it; sinking rose with start height and size [synthetic, `lab` recording frame 0].
     6. *Tunnelling:* sinkers moved less than their thickness per step in 76% of cases (median 0.14 m per step against 0.63 m thick), entered slowly (0.15 m deep at first sight) and then free-fell with no braking [synthetic].
   - **The decisive test [real run, `evidence/floor-box.txt`]:** a fixed 60 x 2 x 60 m box under the site, recipe below, top at the pad height.
     The pieces fell through the box too (51.3% more than 3 m below at 60 s, baseline 36 to 42%). So the cause could not be the terrain; it had to be the pieces.
     Comparing hull frames against RFG's own chunks then gave the answer. Rule: when a generated body passes through a floor
     you built, check the body's shape frame before the floor.
6. **Non-convex plane sets in the generated hulls (small effect).** [synthetic, `src/chunk/gen/test_hull_local.py`] 295 of 1,479 hulls had a
   vertex up to 2.5 m outside one of their own planes (RFG: 10 of 3,044). Planes came from mesh faces of concave pieces rather than
   from the vertex hull. `HULL_CONVEX=1` rebuilds the planes from the vertices (all 1,479 within 2.5e-7 m; at most 43 vertices and 72 planes;
   no format limit was hit; planes of 1,456 hulls changed). Measured effect [real run, `evidence/convex-sink-bins.txt`]: sunk share
   15/5/6/14% by bin, about 10.6% overall against about 12% with local hulls only: within run-to-run noise, kept because it is correct
   by construction. The first draft's "about 1% strongly non-convex" refers to a different measure and is superseded by this count.
7. **What the remaining 10% are.** [synthetic, `tools/residual-sinkers.py` on `lab/collapse-convex.gbrec`] They are handles that vanished,
   not pieces resting low: 167 of 1,595 leave the record at 16 to 19 s, all last seen at y about -17.3. RFG appears to delete
   pieces at about y -17.5 [INFERRED: one common last y, no code reading]. They are smaller and thinner (longest side 1.0 against 1.6 m;
   thin side 0.50 against 0.71 m). Entry is slow (157 of 160 first seen under by 0.5 m or less). Causes, ranked by inference: thin pieces
   penetrating with no restoring contact, push from the pile, a slope or edge 15 to 40 m out. Convex radius is a candidate:
   RFG's own hulls mostly use 0.05 (45% of 10,591) and ours used 0.005. Variants `HULL_INFLATE_THIN=0.3` and `HULL_RADIUS=0.05` are staged and NOT tested [unverified].

## Assets

- Generators: `src/chunk/gen/genchunk.py`, `make_wall.py`, `src/chunk/house/make_house.py`.
- Checks: `src/chunk/gen/validate_gpu.py`, `walk.py`, `test_gen.py`, `src/chunk/test_hk.py`. No game data is in this note.

## Cost and time

- The first draft said about 12 hours of analysis [unverified]. The generator work spans 2026-11-03 (stages 4 and 5, commits c1e4fb9 onward).

## Open questions

- Why RFG draws generated pieces misplaced (render subpiece and vertex-range mapping, or the placement matrix): not known.
- The 20-byte `dynamic_links` records are parsed in `zone.py`; authoring arbitrary joints from them is untested.
- A house-sized `test_gen` run: the suite is wall-only.
- Does `HULL_RADIUS=0.05` or thin-piece inflation remove the last 10%? Staged, not run. Does RFG's delete plane sit at y -17.5? Inferred from one last-y value only.
