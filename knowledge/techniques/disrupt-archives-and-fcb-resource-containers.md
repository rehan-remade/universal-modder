---
kind: technique
title: Disrupt archives and FCB/Nomad resource containers (Watch Dogs 1/2/Legion)
game: "Watch Dogs: Legion"
games_also: ["Watch Dogs", "Watch Dogs 2"]
game_version: "WD1 (BigFileV3) / WD2 / Legion"
platform: windows
engine: unknown
route: data
tools: [Gibbed.Disrupt, DisruptEd, encryptedsfbc, fcb_tool.py]
anti_cheat: unknown
status: working
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links: []
tags: [disrupt, watch-dogs, archive, fat, bigfile, fcb, nomad, entity-library, lz4lw, hashing, compression]
---

# Disrupt archives and FCB/Nomad resource containers

> Almost all Disrupt game data lives inside `.fat`/`.dat` archive pairs (a FAT5
> index plus a data blob) or in Nomad "FCB" binary-object files (`.fcb`/`.lib`)
> that store a name-hashed object tree with shared payloads. Editing either
> means reproducing the engine's exact hashing and compression. This note
> records the archive header/version facts, the compression schemes (including
> the in-place LZ4 variant), and the FCB object model.

## When to use it

- Unpacking or repacking a `.fat`/`.dat` pair to swap a file.
- Reading/writing `.fcb`/`.lib` resources (entity library, gameplay data) as XML.
- Getting a name→hash lookup right so the engine finds your object or field.
- Diagnosing a repack that the game refuses to load.

## How

### Archives (`.fat` + `.dat`)

An archive is a small index file (`.fat`) plus a big data file (`.dat`). Version
is in the signature:

- `BigFileV13` — Legion, signature `FAT5` (`0x46415435`). *(community fork; upstream `Gibbed.Disrupt` exposes `BigFileV3`/`V5` only.)*
- `BigFileV11` — WD2 (split from the earlier V5 line). *(community fork.)*
- `BigFileV3` — WD1-era line; its name hash is a truncated FNV-1a64.

Legion's `windy_city.fat` holds ~149,013 entries and `installpackage.fat`
~31,934, so the index is the authoritative entry list. Most Legion entries use
scheme 3 (LZ4LW); Oodle/LZMA are rare and the rest are stored.

Repacking Legion means writing the header's version fields to match the retail file:

- package/platform version — `13` (`BigFileV13`).
- compression version — `8`. This is the compression *scheme family*; it selects the scheme table below.
- name-hash version — `70`.

(Those fields are what a repacker must set. Retail WD2 files use compression version 6; Legion uses 8.)

### Compression schemes

From the decompressor (upstream `Gibbed.Disrupt` exposes compression schemes V0, V4, V5,
V6, V8 and V9 plus the `EntryDecompression.cs` entry-decompression path; a community fork
adds `CompressionSchemeV2`/`CompressionSchemeV9B`):

- Scheme 0, size 0 = stored (raw).
- Scheme 0, size > 0 = LZMA, with one leading flag byte before a standard LZMA
  header.
- WD1 PC uses compression version 5, whose ids are **1 = LZO1x**, **2 = Zlib**,
  **3 = XMemCompress** — there is no LZ4LW under version 5.
- LZ4LW (an in-place LZ4 variant) is id **2** under upstream's `CompressionSchemeV6` and id
  **3** under versions 8/9 (upstream `V8`/`V9`); only id **4** under the fork's `V9B` table is
  fork-only. Always check which table the archive's compression version selects.

LZ4LW block layout: `[header varint tailCount][LZ4 block][raw tail]`. The
decoder emits the match **offset before** the match-length extension, which is
reversed from standard LZ4, and match offsets stay below `0xE000` so there is
no offset-extension byte. If the compressed form would be >= the input, the
entry is stored instead. This decoder was validated byte-identical on four real
files.

### FCB / Nomad binary objects (`.fcb`, `.lib`)

Magic `nbCF` (`0x4643626E`), u16 version 3, u16 flags 0, u32 total object count,
u32 total value count. The tree is written with a variable-length count code
(`ReadCount`):

- a byte `< 0xFE` → literal count;
- `0xFF` + u32 → literal count (large);
- `0xFE` + u32 → a **backward pointer** into an already-written object or shared
  payload, i.e. the file is a DAG, not a strict tree.

A node is: `ReadCount childCount`; if the count was `0xFE`-tagged it is a
pointer to a previously parsed object, otherwise `u32 nameHash`, `ReadCount
valueCount`, then values (`u32 fieldHash` + a payload whose size also comes from
a `ReadCount`, which is where the `0xFE` sharing shows up), then its children.
Object and field names are plain CRC32.

Gibbed's `ConvertBinaryObject` round-trips a resource between binary and XML:

```
ConvertBinaryObject --export input.fcb output.xml
ConvertBinaryObject --import input.xml output.fcb
```

On import the output extension is derived from the XML root's `name` attribute
(`lib` → `.lib`, `obj` → `.obj`, otherwise `.fcb`); `--nme` is a no-op because
multi-export is always on. Tools need a project definition (e.g.
`bin/projects/current.txt` pointing at `<name>.xml`, plus `binaryclass.xml`,
`binaryobjectfile.xml`, `strings.txt`) to turn hashes into names.

Other Nomad resource families sharing the same serializer machinery:
`CombinedMoveFile`, `FCXMap` (custom map), `Oasis`, `EntityLibrary`, plus
generic/RML/XML variants. The entity library is large: exporting WD1's
`entitylibrary.fcb` yields ~5,681 XML files.

### Hashing cheat-sheet

- FCB field/object names — CRC32, case-sensitive, every game.
- WD1 (FNV1a32) — 64-bit FNV-1a of the lowercased string, truncated to u32,
  then OR'd with a `0xFFFF0000`-style fix; it is **not** standard FNV-1a.
- WD2 / Legion (FNV1a64) — 64-bit FNV-1a masked with
  `0xA000000000000000 | (hash & 0x1FFFFFFFFFFFFFFF)`.
- Archive name hash (V3) — FNV1a64 of the lowercased path, truncated.

These differ from the mesh/material-path hashing (which uses FNV-1 and a
backslash-normalised path), so keep the two rules separate.

### Vehicle/collision footnote

Collision (`COL`) files carry a header that differs between the leaked build
(`0x9B`) and retail/London (`0x9C`); this is why vehicle mods made against a
leaked build can fail on retail. HKX (physics) support is not ready in the
Gibbed tools.

## Gotchas

1. **Repacked Legion archive won't load** → wrong header version fields → set
   package version 13, compression version 8 and name-hash version 70; Legion needs
   V13 with the LZ4LW-capable scheme.
2. **Decompressed bytes differ from the original** → LZ4LW interpreted as
   standard LZ4 → use the in-place variant that emits offset before length
   extension and never adds an offset-extension byte.
3. **FCB parser loops or over-reads** → the `0xFE` prefix was treated as a size
   → it is a backward pointer; resolve objects/payloads from the already-parsed
   table.
4. **Names show as raw numbers** → missing project strings/definitions → point
   the tool at the game's `bin/projects` definition (CRC32 for fields; note WD1
   uses a non-standard FNV1a32, WD2/Legion use masked FNV1a64).
5. **Vehicle collision breaks only on retail** → leak vs retail `COL` header →
   build collision against the retail header (`0x9C`), not the leak (`0x9B`).
6. **XML import lands in the wrong container type** → output extension is
   inferred from the XML root `name` attribute → set it explicitly (`lib`,
   `obj`) or the tool defaults to `.fcb`.

## Seen in

- `Gibbed.Disrupt` (upstream) — `BigFileV3`/`V5`, `ConvertBinaryObject`, `BinaryObjectInfo`, plus compression schemes V0/V4/V5/V6/V8/V9.
- A community fork of `Gibbed.Disrupt` — adds `BigFileV13`/`V11` and the `CompressionSchemeV2`/`CompressionSchemeV9B` tables.
- `DisruptEd` / `FCBastard` — Nomad serializers (`CombinedMoveFile`, `FCXMap`,
  `EntityLibrary`, `Oasis`, generic/RML/XML) and the `encryptedsfbc` branch.
- `fcb_tool.py` (Disrupt project root) — minimal FCB reader/writer with a
  byte-identical round-trip proof.
- `disrupt-armory-public` — WD1 weapon/entity/SPK XML tooling that consumes the
  entity library and SPK sound-id byte order.
