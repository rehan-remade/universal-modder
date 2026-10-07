---
kind: technique
title: "Madness/Chameleon binary containers: .bml (binary XML) and .sgb/.sgx (track scenes)"
tags: [madness-engine, chameleon, nfs-shift, project-cars, bml, sgb, sgx, binary-xml, reflection, scene-graph, 3ds-max]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - "https://www.tapatalk.com/groups/kottons_chop_shop/ti-scp-ti-sms-model-importer-t3217.html"
---

# Madness/Chameleon binary containers: .bml (binary XML) and .sgb/.sgx (track scenes)

> Slightly Mad Studios' Madness/Chameleon engine stores object hierarchies two ways: a compact binary
> `.bml`/`.sgb` and a plain-XML `.xml`/`.sgx` sibling built from a **reflection schema**. The container
> is simple — a magic, a chunk table, then per-chunk payloads — but the payload is a typed attribute
> stream that references separate number/bool/string sections. This note records the byte layout and the
> attribute IDs you need, so a tool can read the containers without re-deriving them. Mesh payloads
> (`.meb`/`.imb`) and the car transform file (`.vhf`) are covered separately.

## When to use it

- You have a `.bml` (car/setup), `.sgb` (track scene) or `.sgx` (XML track scene) from NFS Shift / Shift 2 /
  Project CARS / Test Drive: Ferrari Racing Legends and need the object list, transforms, and mesh
  references.
- You are extending/replacing the 3ds Max **SMS Importer** (`SMS_import.mcr`) or the Blender
  `meb_import`/`vhf_import` addons, and need a documented container instead of reverse-engineering the
  MaxScript.
- Related prior note: car meshes `.meb`/`.imb` and transforms `.vhf` are documented in
  `games/need-for-speed-shift-2/chameleon-mesh-formats-meb-vhf.md`; this note is the *container* layer only.

## How

Authoritative source: `SMS_import_v3.1c.mzp` → `SMS_import.mcr` by vagos21 & Chipicao. Function anchors:
`readBLMY` (line 60), `readCarBML` (line 1107), `readNODE` (line 1208), `readTrackSGB` (line 1259),
`readTrackSGX` (line 1376), `recurXML` (line 1148).

### `.bml` — binary XML (`readBLMY`, line 60; struct comment at line 28)

- Magic **`BLMY`** at `0x00`.
- Header: `u32 numChunks`, `u32 filesize`, `u32 zero`.
- Chunk table, one entry per chunk: 4-char name + `u32 size` + `u32 offset` + `u32 zero`. Seek to `offset`.
- Known chunks: **`HEAD`, `ELMT`, `ATTR` (typo'd `ATT R` in some dumps), `COLL`, `NUMB`, `BOOL`, `STRS`** —
  i.e. `struct BLMY(ELMT, ATTR, COLL, NUMB, BOOL, STRS)` (line 28). A real sample also showed a `STRSL`
  string-list chunk.
- `HEAD` yields `num_elmt`, `num_attr` (lines 88–89).
- `ATTR` entries are `struct attr(ID, type, val, num_values, nextAttr)` (line 29). An attribute is a
  **typed reference into another section**: numeric values come from `NUMB` (indexed by `val`), booleans
  from `BOOL`, collections from `COLL`, and strings from `STRS`/`STRSL` relative to a base offset
  (`STRSoffset`).
- Attribute IDs that matter for cars (`readCarBML`, lines 1119–1132):
  - `773578924` = **OBJpos** — 3 consecutive `NUMB` floats (`val+1..val+3`).
  - `-351767367` = **OBJorient** — a quaternion, 4 `NUMB` floats.
  - `1933617737` = **OBJscale** — 1 `NUMB` float.
  - `1259803821` = **mesh filename** — a string at `ATTR.val + STRSoffset` (import the referenced `.meb`).
  - `-263649155` = **modelName** — the same, used to rename the paired `.vhf`.
- The `.bml` has a human-readable sibling `.xml` (e.g. `t01_01_03_setup.xml` next to
  `t01_01_03_setup.xml.bml`). That XML is the **reflection schema**: `<class name="..." base="...">` with
  `<prop name="..." type="String|U32|F32|Bool|Fct"/>`, defining classes such as `BRTTIRefCount`,
  `BPersistent`, `CMissionSettings`, `CCareerEventSettings`. The `.bml` is the serialised instance of that
  schema — same data, compact form.

### `.sgb` — binary track scene (`readTrackSGB`, line 1259)

- Start by seeking to **16** (the magic/header word).
- Then a sequence of chunks to EOF: 4-char `CHname` + `u32 CHsize` + `u32 CHcount`.
- **`TALF`**: `fseek(CHsize - 12)` — a section to skip.
- **`MMUS`**: `CHcount` object records, each with `OBJsize, OBJid, STRstart, vhfOffset, v2, v3, v4`.
  `OBJsize` selects the node shape:
  - **108** → a single node: three strings (`NODEtype`, `NODEname`, `mebpath`) then sphere
    (`offset` vec3 + radius), transform (`pos` vec3, `orient` quat, `scale`), `matrixNumber`, instance count.
  - **152 / 204 / 256** → a `readNODE` chain of 1/2/3 nested nodes.
  - default → three stacked transforms followed by two nested `readNODE`s.
- `readNODE` (line 1208) reads `NODEtype`/`NODEname` via an offset-based `getSTR`, a bounding sphere, a
  transform, then discovers how many object offsets follow by a heuristic loop (comment in the source:
  *"assumption is the mother of all fuckups"*), then per object reads `NODEtype`, `NODEname`, `mebpath`.
  A path containing `_data` is rewritten to the shared track-assets directory.
- Any unrecognised chunk is skipped with `fseek(CHsize - 12)`.

### `.sgx` — XML track scene (`readTrackSGX`, line 1376)

Plain XML with root **`SCENE`**, loaded via .NET `System.Xml`. `recurXML` (line 1148) walks
`OBJ_ID`/`NODE` (recurse), `MATRIX` (attributes `Offset` vec3, `Orientation` quat, `Scale`), and `RESOURCE`
(attribute `Filename` → a `.meb` to import). It is the XML twin of `.sgb`.

## Gotchas

1. **Chunk names look misspelled.** **Cause:** the binary chunk tags are `ATTR`/`STRS` etc. and some tools
   render them with stray bytes. **Fix:** compare on the first three chars or use the known 4-char list.
2. **Wrong number of objects in `.sgb`.** **Cause:** the `readNODE` object-count discovery is a heuristic
   loop, not a stored count. **Fix:** follow `OBJsize` (108/152/204/256) and re-derive; treat the default
   branch as "unknown, needs the MaxScript logic".
3. **Strings read as garbage.** **Cause:** `ATTR` string values are **offsets into the `STRS` section**, not
   inline strings. **Fix:** seek `val + STRSoffset`, then `readstring`.
4. **Transforms accumulate unexpectedly.** **Cause:** `readNODE`/default branches compose `OBJpos +=` and
   `OBJorient *=` across successive nodes. **Fix:** mirror the MaxScript's parent/child composition order,
   or import each node with a dummy parent rather than assuming a single transform.
5. **`.bml` vs `.xml` disagree.** **Cause:** the `.xml` is the *schema* (class/prop definitions), not the
   data instance; the data is in the `.bml`. **Fix:** use the `.xml` to name/type the attributes, and the
   `.bml` to read values.

## Seen in

- **NFS Shift / Shift 2 Unleashed, Project CARS, Test Drive: Ferrari Racing Legends** (Madness/Chameleon
  engine) — `.bml`+`.vhf` cars, `.sgb`+`.sgx` tracks, `.meb`/`.imb` meshes.
- SMS Importer 3.1c by **vagos21 & Chipicao** (`SMS_import_v3.1c.mzp` → `SMS_import.mcr`); the Blender
  `meb_import`/`vhf_import` addons handle meshes/transforms but not these containers.
- Forum attachment sample pair `t01_01_03_setup.xml` + `t01_01_03_setup.xml.bml` (NFS Shift era) was used to
  confirm the `BLMY` header and chunk list.
