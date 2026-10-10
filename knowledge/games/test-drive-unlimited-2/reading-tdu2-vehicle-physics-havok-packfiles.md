---
kind: game
title: "TDU2 vehicle physics: the Havok 5.5.0 packfile format inside .bnk containers"
game: "Test Drive Unlimited 2"
games_also: []
game_version: "retail PC (TestDrive2.exe; bigfile_EU_1..5.big ~18 GB)"
platform: windows
engine: unknown
route: data
tools: ["grep", "dd", "parse_hkx.py (unpublished local script)"]
anti_cheat: "SecuROM; static read-only analysis only, no bypass or modification attempted"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-06
links:
  - "https://github.com/blueskythlikesclouds/HavokAnimationExporter"
tags: [havok, hkx, physics, packfile, bnk, knab, file-format, reverse-engineering, tdu2]
---

# TDU2 vehicle physics: the Havok 5.5.0 packfile format inside .bnk containers

> TDU2 (Eden engine) ships its vehicle physics as **Havok 5.5.0-r1 classic binary packfiles**
> embedded, uncompressed, in `KNAB` `.bnk` containers. No public HKX parser reads 5.5.0, so this note
> documents the *format* — enough to write your own reader. Extraction, the self-describing
> reflection, and the virtual/local/global fixup tables are verified; the write path is proven only
> as an off-game round trip with an unpublished local script.

## Setup

- Game: retail PC TDU2 (bigfiles `bigfile_EU_1..5.big`, ~18 GB), installed locally.
  Game data was unpacked to ~9665 `.bnk` files (~16 GB) in a local tree.
- No proprietary tooling is required for anything below — the packfile describes itself. A plain
  `grep`/`dd`/Python stack is enough.

## Route and why

Data-only route: read the physics assets to learn the format, then decode them. Considered the usual
HKX parsers first (`hkxpack`, `hkxpack-plus`, `HKX2-Enhanced-Library`, `havoklib`); all stop at
2014.x and reject 5.5.0. The same-era Havok Content Tools are a licensed/leaked build, so the
deliberate choice was **not** to depend on them: document the on-disk format instead, so readers and
writers can be built from the bytes. The round-trip writer used below is our own unpublished local
script (`parse_hkx.py`) — the SDK converter was never run.

## How the game works (what we had to learn)

### Container: `.bnk` is Eden `KNAB`, not a ZIP

Header at file start is `40 00 00 00 <4-byte hash>` followed by ASCII `KNAB` at offset 0x08.
Most pressed `.bnk` payloads are stored **uncompressed**, so embedded data is greppable in place.

### Embedded Havok classic packfile

Vehicle assets live under `Vehicules/High/`, `Vehicules/Med/`, … and each car's `.bnk` embeds a
Havok classic binary packfile. It starts with magic `57 E0 E0 57 10 C0 C0 10`, `fileVersion = 5`,
32-bit little-endian, and the version string at header+40 = `Havok-5.5.0-r1`.

Observed layout:

- **0x40-byte header** — magic `57 E0 E0 57`/`10 C0 C0 10`, `userTag`, `fileVersion`,
  `bytesInPointer`, `littleEndian`, `reusePadding`, a base-class-optimization flag, `numSections`,
  `contentsSectionIndex`, class-name-section index + offset, and the contents version string
  (at header+40).
- **Section table at 0x40** — one 48-byte entry per section: a 19-byte name tag, a `0xFF`
  separator, then seven `uint32` fields (`absoluteDataStart`, local/global/virtual fixup offsets,
  exports, imports, `endOffset`). Offsets are **relative to the section's `absoluteDataStart`**, and
  sections are contiguous: `__classnames__` 208+1280, `__types__` 1488+23584, `__data__`
  25072+7040 = 32112 = the whole file. Use that arithmetic to sanity-check a slice's length.
- **`__classnames__`** — a pool of `uint32 signature` + constant `0x09` marker + null-terminated name
  records. 54 records fill the 1280-byte section exactly (`0x1b58f0ef`→`hkpPhysicsSystem`, …). The
  header's class-name offset and every virtual fixup are **relative to the start of this section**.
- **`__types__`** — the `hkClass` reflection: each class's name, parent, size, enums and members
  (name, type, subtype, `cArraySize`, flags, offset). Because this is stored *in the file*, a reader
  does not need a version-specific class registry.
- **`__data__`** — the object graph, laid out per the reflection. Pointers are section-relative
  offsets repaired by three fixup tables reached from the section table:
  **virtual** = 12-byte `(srcOffset, sectionIndex, dstOffset)`, one per object, binding it to its
  class name (verified: `__data__`+0 → `(0, 0, 228)` → `__classnames__`+228 = `hkpPhysicsSystem`);
  **local** = 8-byte `(src, dst)` pairs within the section, sentinel-ended by `0xFFFFFFFF`; and
  **global** = 12-byte `(srcOffset, dstSectionIndex, dstOffset)` triples for cross-section pointers,
  likewise sentinel-ended. Stop at the sentinel or at the table end rather than by dividing the
  span: the tables are 16-byte aligned (in `__data__`: local 5904, global 5968, virtual 6560,
  exports 7040), so span ÷ record size can be off by one. The local span is 64 B = 8 pairs; the
  virtual span is 480 B = 40 × 12 (matching the 40 objects) and has **no sentinel**; the 592-byte
  global span is 49 triples plus a 4-byte `0xFFFFFFFF` sentinel (592 = 49×12 + 4), with no padding.

A reader is therefore: parse the header → walk the section table → read `__classnames__` → build a
class registry from `__types__` → walk the virtual fixups to bind each `__data__` object to its
class → apply local/global fixups → decode the object fields against the registry.

### What the physics data contains

Root object is an `hkpPhysicsSystem`. For a car (e.g. Ferrari F430) it holds rigid bodies, wheel
hinges (`hkpLimitedHingeConstraintData` with a local-transform atom plus an angular-motor atom), a
chassis collidable built from an `hkpListShape` of many `hkpBoxShape` / `hkpConvexTransformShape`
children, and `hkpProperty` entries keyed to material/userData tags. Physics data also appears in
level/scenario `.bnk` (e.g. `Islands/hawai/Level/commonworld.bnk`).

A census of `Vehicules/` found 285 `Havok-5.5.0-r1` strings and **zero** occurrences of any other
Havok version, so a private-server claim that TDU2 used a "2010 rc1" SDK is wrong.

## Build steps

```
# 1. Find the embedded packfile and its version
off=$(grep -abo $'\x57\xe0\xe0\x57\x10\xc0\xc0\x10' car.bnk | head -1 | cut -d: -f1)
dd if=car.bnk bs=1 skip=$((off+40)) count=16            # -> "Havok-5.5.0-r1"

# 2. Slice the packfile. NOTE: the packfile does NOT run to EOF — an XMBF curve table follows.
#    (For f430.bnk the packfile starts at 3696 and is 32112 bytes.)
dd if=car.bnk of=car_pf.hkx bs=1 skip=$off count=<packfile-size>

# 3. Parse with a reader you write from the spec above (see the unpublished local parse_hkx.py as a starting point)
python3 parse_hkx.py car_pf.hkx
```

## Verification

Oracle: the version string and header fields were read directly from the bytes; the section
arithmetic sums to the exact file size; the class-name pool parses to exactly 54 records filling its
section; and the virtual fixup table was resolved by hand — 40 records, each `(src, section, dst)`
landing on a valid class name (`__data__`+0 → `hkpPhysicsSystem`, the root). The version was also
census-confirmed across 285 `Vehicules/` `.bnk` (all `Havok-5.5.0-r1`, none other).

Not verified: a reader built solely from this spec (the object-field decode was cross-checked during
research against a converter's output, not reconstructed independently). The **write** path is
verified off-game only, with our unpublished local writer (`parse_hkx.py`): XML → binary → XML
round-trips at the same 32112 bytes and yields the same object graph, differing only in negative-zero
formatting. Still unverified: that the retail game loads the repack — swapping it back into the
`.bnk` remains the end-to-end oracle, and it has not been done.

## Gotchas

1. **`.bnk` looks like an archive but is not a ZIP.** **Symptom:** `unzip`/`7z` both refuse it
   (`End-of-central-directory signature not found`). **Cause:** it is the Eden `KNAB` container
   (`KNAB` at offset 0x08). **Fix:** read/parse it directly; the payload is uncompressed so
   `grep -abo` finds embedded signatures.
2. **No public Havok parser reads 5.5.0.** **Symptom:** `hkxpack` fails with
   `Could not find file for hkpPhysicsSystem.` **Cause:** bundled class definitions top out at 2014.x.
   **Fix:** parse the file's own `__types__` reflection rather than relying on a bundled registry.
3. **The `.hkx` slice is smaller than you think.** **Symptom:** `dd` to EOF gives ~25 MB and looks
   corrupt. **Cause:** a separate `XMBF` curve table follows the packfile. **Fix:** slice exactly the
   packfile size (32112 bytes for F430), not to EOF.
4. **The exe does not name its Havok version.** **Symptom:** `strings TestDrive2.exe` shows only a
   compatibility registry (`Havok-3.0.0` … `Havok-5.5.0-r1`) and a runtime format string.
   **Cause:** it is a registry, not the writer version. **Fix:** read the version from a real asset at
   packfile header+40.
5. **Do not reach for the era's SDK.** **Symptom:** you find a converter that reads the file and
   start scripting around it. **Cause:** those Havok Content Tools builds are licensed/leaked and
   not redistributable. **Fix:** treat parsing as format work; the packfile is self-describing, so a
   standalone reader is both possible and the publishable result. The one piece the spec does not
   give you for free is a *writer*, which must at least match the header's four `layoutRules` bytes to
   the target (see `techniques/havok-hkx-chunked-packfile-family.md`).
6. **A "byte-exact" repack that is unreadable can be big-endian.** **Symptom:** you write the
   binary back, the size and the magic match, and the reader crashes. **Cause:** the rule bytes at
   header offset 16 were written for the wrong target — the console rules flip every `uint32` in the
   file, and the magic is byte-swap-invariant so "the magic is right" proves nothing. **Fix:** copy
   the source header's `04 01 00 01` back verbatim, then read your own output and diff the XML.

## Assets

None — format research, not art/audio.

## Cost and time

One session. No paid tooling.

## Open questions

- Minimum viable writer: what metadata/fixup layout must be reproduced for the game to load a repack?
- Are the `userData` tags (18, 17, 37, 38, 27…) stable across cars and mapped to collision IDs?
- Can level/scenario `commonworld.bnk` physics be decoded the same way for world-collision mods?
