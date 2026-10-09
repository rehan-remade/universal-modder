---
kind: technique
title: "Disrupt-engine HKX collision: old packfile vs TAG0, and how a community Blender add-on reads and injects it"
tags: [havok, hkx, disrupt, watch-dogs, tag0, packfile, collision, blender, injection]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links: []
---

# Disrupt-engine HKX collision: old packfile vs TAG0, and how a community Blender add-on reads and injects it

> Ubisoft's Disrupt engine (Watch Dogs 1/2, Legion) ships its collision as Havok `.hkx` in **two
> different shapes**: a 64-bit **classic packfile** (WD1) and a **TAG0 tagfile wrapped in a Dunia
> header** (WD2/WDL retail). The companion note covers the classic packfile byte layout; this note is
> about the *reader/injector implementation* in a community Blender add-on's `modules/Havok/` — what it parses
> and, importantly, what it does **not** write.

## When to use it

When you need to read or modify collision in a Disrupt title and want a known-good reference for the
two packfile shapes, the `ITEM`/`PTCH` object graph, or the compressed-mesh item types. Also useful
as a worked example of *in-place* HKX editing (displacement injection) without re-serializing the
whole file.

## How

### One entry point, two shapes

`hkx_format.parse_hkx(path)` sniffs the first bytes:

- `57 E0 E0 57 10 C0 C0 10` (`HAVOK_MAGIC`) within the first 32 bytes → `OldPackfileParser`.
- `TAG0` within the first 32 bytes → `Tag0Parser`.
- Otherwise it searches for `TAG0` before offset 64 — the Dunia wrapper puts the tagfile 4 bytes
  past a small header, so the parser re-enters at `idx - 4`.

### Old packfile (WD1)

Same structure as the TDU2 note: a 0x40-byte header, then one **48-byte section entry** per section
(19-byte name tag + `0xFF` + seven `int32`: `abs`, `local`, `globalFixups`, `virtualFixups`,
`exports`, `imports`, `end`). This implementation is **64-bit only** — it rejects anything whose
`bytesInPointer` byte at header+16 is not `8`. The three fixup tables are how the object graph is
rebuilt:

- **virtual fixups** (`abs + virtual` up to `abs + exports`, 12-byte records): `(objOffset,
  sectionIndex, classNameOffset)`. `classNameOffset` is resolved against the `__classnames__`
  section base, giving each object offset its class name.
- **local fixups** (`abs + local` up to `abs + globalFixups`, 8-byte `(from, to)`), for
  intra-section pointers.
- **global fixups** (`abs + globalFixups` up to `abs + virtual`) are always 12-byte
  `(from, section, to)`; only the local fixups are 8-byte `(from, to)` pairs.

Reads are absolute: `fileOffset = __data__.abs + objOffset + fieldOffset`, so the parser keeps the
raw bytes and a `base` and never copies the graph out.

### TAG0 (WD2 / WDL retail)

A flat sequence of chunks. Each chunk is a `uint32 size_and_flags` followed by a 4-byte magic
(`TAG0`, `SDKV`, `DATA`, `TYPE`, `INDX`, `ITEM`, `PTCH`). `TAG0` is itself a container of the same
sub-chunks, so the parser recurses one level. `SDKV` carries the version string; `DATA` is the item
payload area.

- **`ITEM`** — 12-byte records `(type_and_flags, dataOffset, count)`; `type_id` is the low 24 bits
  and `flags` bits 24–27. An item's bytes are `DATA[dataOffset : dataOffset + count]`.
- **`PTCH`** — 12-byte records `(pointerType, pointerLocation, targetItem)`; the fixup table that
  links items into an object graph.

### Compressed mesh: the same data, fragmented

`tag0_compressed_mesh.py` documents how a `hkpBvCompressedMeshShape` looks in each shape. In the old
packfile (WD1) its tree arrays are **inline** in one contiguous object. In TAG0 (WD2/WDL) the same
data is **split across items** linked by `PTCH`:

| Item type | Holds |
|---|---|
| `0x7e` | section-header array (0x60 bytes each; domain AABB + codec floats) |
| `0x3c` | packed vertices (`u32`, 11/11/10-bit) |
| `0x80` | primitives (`u8[4]`) |
| `0x6f` | shared vertices (`u64`, 21/21/22-bit) |
| `0x94` | individual compressed-mesh shapes |

Decompression is shared across both shapes: 11/11/10-bit vertices map via
`x = (v & 0x7FF)*sx + ox`, etc.; 21/21/22-bit shared vertices map against the domain
(`x = (v & 0x1FFFFF)/2097151 * sx + minx`).

### Writing: it is an injector, not a serializer

The module docstring says "parser and writer", but there is no code that synthesizes a packfile from
an object graph. Injection works by copying the **original file bytes** and overwriting fields in
place at their existing offsets (`_write_u32` / `_write_f32` at absolute offsets), then saving to a
new path:

- WD1: full collision rebuild (add/delete geometry) and in-place displacement.
- WD2: displacement-only injection into a copy of the `.hkx`.
- WDL: collision is import-only in this addon.

So the byte-layout knowledge here gets you a reader and a patcher; producing a brand-new HKX still
requires reproducing the serializer's fixup/metadata layout (the TDU2 note round-trips one 32-bit 5.5.0
packfile with an unpublished local writer, off-game only).

## Gotchas

1. **A "HKX writer" in a mod tool is usually an in-place patcher.** **Symptom:** you look for the
   packfile serializer and find none. **Cause:** the tool copies the original and overwrites
   offsets. **Fix:** don't expect it to mint a new file; displacement edits preserve size and
   layout, adding/removing data needs a real writer.
2. **The old packfile parser is 64-bit only.** **Symptom:** `Expected 64-bit packfile, got 32-bit`.
   **Cause:** the pointer-size byte at header+16 is checked. **Fix:** for a 32-bit file (e.g. TDU2
   5.5.0) write your own pass; the structure is otherwise identical.
3. **Global-fixup table runs off the end when read as 8-byte pairs.** **Symptom:** the local
   table parses but the global table overruns. **Cause:** global fixups are always 12-byte
   `(from, section, to)`; only local fixups are 8-byte `(from, to)` pairs. **Fix:** read globals as
   12-byte triples, bound the walk by the next table's start and sanity-check the last entry
   (`p + 12 <= abs + virtual`).
4. **TAG0 can sit behind a vendor header.** **Symptom:** `TAG0` is not at offset 0. **Cause:** the
   Dunia wrapper. **Fix:** search for the magic in the first 64 bytes and re-enter 4 bytes earlier,
   as `parse_hkx` does.

## Seen in

- Watch Dogs 1 collision `.hkx` (old packfile, 64-bit, full rebuild + injection)
- Watch Dogs 2 / Legion retail collision `.hkx` (TAG0 in a Dunia wrapper; displacement injection)
- A community Blender add-on (v3.1.2, MIT) — `modules/Havok/hkx_format.py`, `tag0_compressed_mesh.py`,
  `decompress_compressed_mesh.py`, `import_hkx*.py`
