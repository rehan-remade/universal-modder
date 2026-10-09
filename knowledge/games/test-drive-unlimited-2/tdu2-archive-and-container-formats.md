---
kind: game
title: "TDU2 archives and containers: .BIG bigfiles, KNAB .bnk banks, XMBF indexes"
game: "Test Drive Unlimited 2"
games_also: []
game_version: "retail PC (bigfile_EU_1..5.big + matching .map indexes; Eden engine)"
platform: windows
engine: unknown
route: data
tools: ["TDU2.Unpacker (TDU2.BIG.Tool)", "ModdingLibrary_2 (tdumt2/Bnk.cs, Xmb.cs)", "xmbf_convert.py (local, unpublished)", "bnk_packcdb.py (local, unpublished)", "bnk_extract.py (local, unpublished)", "vmf_extract.py (local, unpublished)"]
anti_cheat: "SecuROM; read-only static format analysis, no bypass or modification attempted"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-06
links:
  - "https://github.com/djey47/tdu-cp/wiki/Tools-reference"
tags: [big, bnk, knab, bndl, xmb, xmbf, file-format, archive, containers, reverse-engineering, tdu2]
---

# TDU2 archives and containers: .BIG bigfiles, KNAB .bnk banks, XMBF indexes

> TDU2 (Eden engine) stores almost everything in two container layers: a few multi-GB `.BIG`
> bigfiles indexed by a sidecar `.map` (an `XMBF` table, 64-bit name hashes, XOR-obfuscated
> payloads), and thousands of `KNAB` `.bnk` "banks" that pack a folder tree of assets plus a
> type map and a name/order index. This note records the on-disk layouts as the local tools
> implement them — enough to read both containers and to understand why repacking a `.bnk` is
> where the community tooling breaks down. Reads are well documented by working parsers;
> a clean writer exists in a third-party Python packer but the mainstream C# tool has a known
> repack bug.

## Setup

- Game: retail PC TDU2. Bigfiles are `bigfile_EU_1..5.big` (~18 GB total) each with a sibling
  `.map` index (`bigfile_EU_1.map`, …). Tools in the repo expect the pair side by side.
- Sources read for this note (no proprietary tools run; retail `.bnk` data is read directly in the
  byte-level section below):
  - `TDU2.BIG.Tool` (community tool) — C# `TDU2.Unpacker`, .NET 8, reads `.big` + `.map`.
  - `TDU2-BIG-Unpacker` — older binary build (`TDU2BIGUnpacker.exe` + `TDU2Lib.dll`)
    with the same `FileNames.list` hash→path project file.
  - `tdumt2` / `ModdingLibrary_2` (community tool) — `Bnk.cs` is the reference `.bnk` (KNAB) parser
    and rewriter, `Xmb.cs` a small `.xmb` audio-volume database editor.
  - `carvst editor` (local, unpublished) — Python `xmbf_convert.py` (XMBF format reference) and
    `tomake sound/bnk_packcdb.py` (an independent KNAB pack/unpack + TDU DB XTEA impl).
  - Small binary utilities `TDU2-Bin-Renamer`, `TDU2-BNK-File-Locator`, `TDU2-BNK-Finder`,
    `TDU2-BNK-Guts-Viewer`, `TDU2-HashGen`, `TDU2-Music-Extractor` (no source/readme shipped —
    see Open questions).

## Route and why

Data-only route: learn the actual container bytes so a reader/writer can be built. There is no
public Eden SDK, so the layout has to come from the community parsers. The interesting
questions were (a) how the `.big`/`.map` pair encodes names and where the payload bytes live,
and (b) whether the `.bnk` "packed hierarchy" is safe to rewrite. Both have working readers;
the `.bnk` writer is the weak link, which is why the note spends most of its length on the
KNAB layout and the repack bug.

## How the game works (what we had to learn)

### Layer 1: `.BIG` bigfile + `.map` index

`TDU2.Unpacker` requires `bigfile_EU_N.big` **and** `bigfile_EU_N.map`; it aborts if the
`.map` is missing. The `.map` is itself an `XMBF` container (magic `0x46424D58` = bytes
`X M B F`, version `257` = `0x101`) — the same magic and version the audio-config `.xmb`
files use, so `XMBF` is a general Eden structured-binary/table format, not bigfile-specific.

`.map` header as read by `MapHeader.cs`/`BigUnpack.cs` (all little-endian):

- `0x00 uint32 magic` = `0x46424D58` (`XMBF`)
- `0x04 int32  version` = `257`
- `0x08 int32  stringPoolOffset` (28 in the shipped maps)
- `0x0C int32  schemaTableOffset`
- `0x10 int32  subHeaderOffset`
- then `seek(subHeaderOffset + 4)` and read: `totalFiles`, `subHeaderSize` (=24),
  `numRecords` (== `totalFiles`), `recordsOffset`.
- Two parallel arrays, both of `totalFiles` entries:
  - at `subHeaderOffset + subHeaderSize`: `uint64 nameHash` per entry;
  - at `subHeaderOffset + recordsOffset`: `int32 size` + `int64 offset` per entry.

So an entry is `(nameHash, size, offset)`. Names are not stored — `BigHashList` rebuilds the
hash→path map at load time from `Projects/FileNames.list`, whose format is `HEXHASH "path"`
(e.g. `29EB451710E98BEA "euro/bnk/avatar/avatar_face_fx.bnk"`), and it *verifies* each stated
hash against the computed one (warning on mismatch). A hash with no path resolves to
`__Unknown\<16 hex>`.

The name hash is a **CRC64-ECMA-style** function (`BigHash.iGetHash`) seeded with
`dwCrc1 = 0xFAC432B1`, `dwCrc2 = 0x0CD5E44A`, using the dual polynomial table
(`0x00600340` / `0x00F0D50B`) and returning `(dwCrc2 << 32) | dwCrc1`. It is computed over the
path with forward slashes.

Payload bytes are **not** plain. `BigCipher.iDecryptData` XORs every byte with the repeating
4-byte key `D7 A8 E2 D4`. The unpacker reads `size` bytes at `offset` from the `.big`, XORs
them, and writes the file to the path the hash resolved to. Unresolved entries become
`__Unknown`.

### Layer 2: `.bnk` is Eden `KNAB` (not a ZIP, not a Wwise SoundBank)

The reference parser is `tdumt2/tdumodlib_2.0/ModdingLib/fileformats/banks/Bnk.cs`. A `.bnk`
is a sequence of CRC-checked sections, each laid out as an 8-byte common header
(`uint32 length` + `uint32 crc32`) followed by `length` bytes of payload and padding to a
block size. The header section sits at offset 0, so the file begins:

```
0x00  uint32  header section length  (0x40 = 64)
0x04  uint32  header section CRC32
0x08  'K' 'N' 'A' 'B'                <- the KNAB tag (4 of the 12-byte tag field)
```

`_HEADER_LENGTH = 64` and `_SECTION_HEADER_LENGTH = 8` in `Bnk.cs`, matching the observed
`40 00 00 00 <crc> KNAB` opening. (The tdumt2 `AGENTS.md` — unpublished local notes — calls these "BNDL archives", but
"BNDL" does not appear anywhere in the source — the parser calls it a *packed hierarchy*
rooted at `PackedRoot`. Treat "BNDL" as a label, not a signature.)

Header payload (offsets within the 64-byte header, i.e. byte 8 in the file):

- `[0:12]`  tag `"KNAB"` + 8 zero bytes
- `[12:14]` SpecialFlag1 (u16, "should never change")
- `[14:16]` SpecialFlag2 (u16)
- `[16:20]` file_size (u32, whole file)
- `[20:24]` packed_size (u32, sum of file payload sizes)
- `[24:28]` BlockSize1 (u32) — 4 or 32 per `Bnk.cs`
- `[28:32]` BlockSize2 (u32) — 16 per `Bnk.cs`
- `[32:36]` packed_count (u32, number of files)
- `[36:40]` year (u32)
- `[40:44]` size_section_addr
- `[44:48]` type_mapping_section_addr (0 = absent)
- `[48:52]` tree_section_addr
- `[52:56]` order_section_addr
- `[56:60]` unknown2/magic_section_addr (0 = absent, not implemented by tdumt2)
- `[60:64]` data_section_addr

Section order in the file (from `Save()`): header, sizes, optional type map, tree, order,
optional unknown2, then packed data.

**Sizes section.** One entry per file plus a terminating entry. Entry size is auto-detected as
`section_length / (packed_count + 1)`: 16 bytes = TDU1, 20 bytes = TDU2. Layout:
`uint32 address`, `uint32 size`, `uint64 magic`, and (TDU2 only) `uint32 constant 16`. The
terminator entry marks end-of-data.

**Tree section** (the packed hierarchy). Recursive records, name-stem only for files:

- directory: first byte = `256 - name_len` (negative when read as `s8`), then a `children_count`
  byte, then an optional extra byte (tdumt2 reads the next byte and rewinds unless it is `0x01`;
  `bnk_packcdb.py` describes this as an extra byte when `child_count >= 176`), then the name.
  A directory whose name starts with `.` supplies the extension for its file children.
- file leaf (inside an extension directory): `byte name_len`, then the stem bytes (no
  extension). The extension comes from the enclosing `.EXT` directory.
- A `0x00` first byte terminates the tree.

**Order section**: one index per file, mapping tree order → sizes-section slot. Value is `byte`
when `packed_count <= 256`, else `uint16`.

**Type mapping section** (optional): one `uint32` per file. `bnk_packcdb.py` records the code as
`(category_u16 << 16) | subtype_u16`; tdumt2 keeps a per-extension cache and warns that `.2dm`
colour files can reuse a different id, so the cache is not fully reliable.

**Packed data**: raw file bytes back to back, each padded to `BlockSize2`, padding filled with
a known ASCII string (tdumt2's current pad is `"TDUMTII-UNBIN-BRAVO LES POTES-EPIC-"`; the
original Eden pad string is documented in the source comment as
`"STNICC2000 RULEZPADDING DATAS...-ORIC AND ATARI--COOL  MACHINES-"`).

`bnk_packcdb.py` additionally documents that **`.db` files inside `DB.bnk` are XTEA-encrypted**
(a TDU1-era DB encryption; key and CBC scheme in that file). Everything else in a `.bnk` is
plain.

### Byte-level check (2026-10-06, added after parsing retail banks)

The section-based layout above was derived from tool source. Parsing the shipped banks directly
confirms it and fixes one thing the source-based reading got wrong.

Confirmed on retail `Airport.bnk` (3,219,456 B, year 2011): file size at 0x18, packed size at
0x1C, `BlockSize1` 32 at 0x20, `BlockSize2` 16 at 0x24, `packed_count` 5 at 0x28, year 2011 at
0x2C, sizes section at 0x30+8, type map at 0x34+8 (224 — present, not absent), tree at 0x38+8,
order at 0x3C+8, `unknown2` 0 at 0x40, data at 0x44+8 = 0x1B0 (which is exactly where the first
payload begins). Its five entries are three `.2db` (262224, 262224, 2097232 B), one `.2dm`
(2704 B) and one `.vmf` (593059 B). A sizes-section entry is 20 bytes as observed:
`offset u32, size u32, 4 B near-constant (d6 16 19 01 / d2 16 19 01), 4 B per-file value (looks
like the resource hash — the `.vmf` entry reads `4f ab 5d df`), u32 0x10`.

**The name blob is a forest, not one tree.** Read top-level nodes and keep going until exactly
`packed_count` file leaves have been collected; do not call the recursive walk once. A
single-call walk under-reads multi-root containers — 29 of 9,663 banks fail that way
(`numFiles(4) != walked(3)` for `Avatar/CLOTHES/pnj/W_PN_B_Skirt_Host_Rpt.bnk`,
`numFiles(510) != walked(9)` for `Islands/hawai/Level/Commonworld.bnk`,
`numFiles(220) != walked(92)` for `Interior/Icaspok1__Fr.bnk`; the misses are whole sibling
subtrees). Multi-root counts seen: 2, 6, 128.

Leaf names are stems whose enclosing `.EXT` folder supplies the extension, and the full path is
retained from the build — e.g.
`D:\Eden-Prog\Games\TestDrive2\Resources\5Prepared\PC\EURO\FrontEnd\airport\.vmf\airport` and
`V:\projects\testdrive2\resources\1rawdata\graphs\characters\clothes_pnj\...\maps\.2db\...`.
Because the extension lives in the path, the resource mix of a whole tree can be counted:
`.2db` 43874, `.pmi` 19984, `.wav` 15077, `.2dm` 12295, `.3dd` 10868, `.3dg` 10310, `.shk` 7481,
`.pgr` 4000, `.psa` 3987, `.flg` 3984, `.anm` 3465, `.xmb` 3340, no-extension 3002, `.rd` 2572,
`.pen` 1550, `.sce` 1455, `.cin` 1442, `.bfx` 1398, `.uva` 1381, `.lmp` 951, `.txt` 900,
`.bin` 900, `.dhk` 500, `.bas` 494, `.fxe` 395, `.ini` 355, `.prt` 345, `.trk` 341, `.xsb` 230,
`.vmf` 127. The `.vmf` total is the whole UI of the game — see the Flash UI note in this folder.

One bank is deliberately not supported: `Physics/Tires.bnk` (2,698 B, a 2026 build year in a
2011 tree) is hand-made. It writes folder lengths *without* the negation (`02 01 "D:"`,
`06 06 ".bpjka"` = length 6, six children), fills its payloads with repeated `dead 40 06`, ends
with an all-zero "no-file" sizes entry 0x18 before the order table, and carries the watermark
`PACEJKA TIRE FLE`. Its six sizes records are still readable.

### `.xmb` / `XMBF`, two uses

There are two distinct things under the `.xmb` name:

1. **`XMBF` table format** (magic `0x46424D58`, version `0x101`). `carvst editor/xmbf_convert.py`
   documents it: 28-byte header (`magic, version, stringPoolOffset (0x1C), schemaTableOffset,
   dataSectionOffset, count1, count2`) then a string pool, a schema table, and a data section.
   Its concrete use there is `CarVSTConfig*.xmb` (vehicle audio config): records at a fixed
   82-byte stride (`GAP(30) + BankBody(40) + CurveSet(12)`), with 13 volume floats preceding
   each event name and confirmed indices `10=Road, 11=Grass, 12=Dirt`. Round-trip is
   byte-perfect because the XML embeds raw sections as base64. The `.map` indexes are the same
   `XMBF` magic/version, which is why this format reference is worth reading even for archives.
2. **tdumt2 `Xmb.cs`** (MiniXmb). This is a lighter, older view used for sound-sample volume
   editing: it keeps the whole file as a byte[], finds a sample by searching for the byte pair
   `0x80 0x3F` immediately followed by the ASCII sample name, then reads two `float` volumes at
   `nameIndex - 24` (in) and `nameIndex - 20` (out), and patches them in place. `Save()` rewrites
   the file. So the same `.xmb` can be manipulated either as a structured `XMBF` table or by
   byte-pattern search, depending on the tool.

### The known `.bnk` repack bug

`BNK Manager/AGENTS.md` (unpublished local notes) documents that repack fails under Wine ("end of stream" in
`_ReadPackedHierarchy()` when `Read()` runs after `SaveAs()`; all sections pass checksum but the
tree parser reads more entries than the data holds). Reading `Bnk.cs` shows two concrete
suspects, both on the write path:

- `Bnk.cs:1286` — `Save()` opens with `FileMode.OpenOrCreate`, which does **not** truncate. If
  the repacked file is shorter than the original, stale trailing bytes survive and the next
  `Read()` parses through them.
- `Bnk.cs:931` — `byte childrenCount = (byte) entry.Children.Count;` truncates any
  `children_count > 255` to its low byte, so the reader walks past the end of the real children.

A third, related hazard is in the tree writer: `_UpdateTreeSection()` (`Bnk.cs:888-914`) writes
the tree into a 65536-byte buffer then truncates at the **first `0x00` byte**. A directory with
zero children writes `children_count = 0x00`, which would end the section early. (This one is
reasoned from the code, not observed in-game — see Open questions.)

## Build steps

```
# --- Layer 1: explode the bigfiles to a folder tree -------------------------
# Needs bigfile_EU_N.big and bigfile_EU_N.map together.
# TDU2.Unpacker is .NET 8; it XORs each payload with D7 A8 E2 D4 and writes by resolved path.
dotnet TDU2.Unpacker/bin/Debug/net8.0/TDU2.Unpacker.dll \
    <install>/bigfile_EU_1.big  <unpacked-tree>
# (Repeat per bigfile. Names resolve via Projects/FileNames.list; misses land in __Unknown.)

# --- Layer 2: inspect/repack a .bnk -----------------------------------------
# tdumt2 builds the MiniBnkManager GUI (a Wine prefix for the prebuilt exe):
WINEPREFIX=<wineprefix> wine MiniBnkManager.exe
# Logs: Logs/ModdingLib.log (set DEBUG in Conf/log4net.xml for verbose tree parsing).

# --- Independent KNAB packer (no .NET) --------------------------------------
python "carvst editor/tomake sound/bnk_packcdb.py" unpack  INPUT.bnk  OUTPUT_DIR
python "carvst editor/tomake sound/bnk_packcdb.py" pack    INPUT_DIR  OUT.bnk
# Unpack writes a .bnk_meta.json sidecar so a later pack restores type codes, tree, order,
# year, section block size and padding exactly.

# --- XMBF <-> XML -----------------------------------------------------------
python "carvst editor/xmbf_convert.py" to-xml CarVSTConfig.xmb out.xml
python "carvst editor/xmbf_convert.py" verify CarVSTConfig.xmb   # byte-perfect round-trip
```

## Verification

What is verified from the sources:

- `.BIG`: the `.map` header magic/version checks are literal in `BigUnpack.cs`
  (`0x46424D58`, `257`); the entry layout `uint64 hash / int32 size / int64 offset` and the
  two-array seek scheme are read directly from that code; the CRC64 seeds/polynomials and the
  XOR key `D7 A8 E2 D4` are literal constants in `BigHash.cs`/`BigCipher.cs`. The
  `FileNames.list` format and its self-check are in `BigHashList.cs`.
- `.bnk`: all field sizes and offsets come from `Bnk.cs` constants and read/write methods, and
  independently from `bnk_packcdb.py`'s documented layout, which agrees on the 8-byte section
  header, the `KNAB` tag, the header field order, the `packed_count + 1` entry rule, the 16/20
  entry sizes, the tree record shapes and the type-code packing.
- `.xmb` / `XMBF`: `xmbf_convert.py` states its round-trip is byte-perfect and ships a `verify`
  command; `Xmb.cs`'s in/out volume offsets are literal.

Not verified here (`.big`, `.map` and `.xmb` are source-only, and nothing was repacked or run in
game): the repack bug is **not** reproduced —
the two suspects are read out of `Bnk.cs`, not observed. The field layout above and the
tree-terminator hazard are tool-source-only at this point. (`.bnk` bytes are examined in the
dated byte-level section below; the source-only statement applies to `.big`, `.map` and `.xmb`.)

Added 2026-10-06, from parsing the retail banks directly (`.bnk` only; `.big`, `.map` and
`.xmb` are still source-only):

- The local, unpublished `bnk_extract.py --scan` parses **9660/9660** banks in an extracted retail tree with every
  `(offset, size)` inside the file, and
  **3573/3573** in the TDU2.Unpacker output tree. Three files under `Interior/`, `Islands/`
  are not KNAB containers.
- The `.vmf` payload pulled out by path was checked against an independent editor screenshot:
  header and tag list match exactly, and a sweep of all 127 UI resources walks 159,077
  ActionScript blocks without a failure.
- Still not verified: that any repacked `.bnk` loads in game. Nothing was written back.

## Gotchas

1. **`.big` will not unpack without its `.map`.** **Symptom:** `TDU2.Unpacker` errors that the
   `.map` does not exist. **Cause:** the bigfile is a flat blob; all names/sizes/offsets live in
   the sibling `XMBF` index. **Fix:** keep `bigfile_EU_N.big` and `bigfile_EU_N.map` together.
2. **Unpacked payloads look corrupt / high-entropy.** **Symptom:** a `dd` slice is garbage.
   **Cause:** every `.big` payload is XORed with the repeating 4-byte key `D7 A8 E2 D4`
   (`BigCipher.cs`). **Fix:** XOR the slice before use (the unpacker does this automatically).
3. **Filenames are hashes, not strings.** **Symptom:** entries with no name, or a folder full of
   `__Unknown\XXXXXXXX...`. **Cause:** the `.map` stores only 64-bit CRC64 name hashes.
   **Fix:** resolve via `Projects/FileNames.list`; unknown hashes are genuinely unknown.
4. **`.bnk` is not a ZIP and not a standard Wwise SoundBank.** **Symptom:** archive tools reject
   it. **Cause:** it is the Eden `KNAB` container (tag at 0x08). **Fix:** parse it directly with
   the section layout above; `bnk_packcdb.py` reads/writes it without .NET.
5. **Repack "end of stream" under Wine.** **Symptom:** `_ReadPackedHierarchy()` throws after
   `SaveAs()`, though every section's checksum passed. **Cause:** likely
   `FileMode.OpenOrCreate` not truncating (`Bnk.cs:1286`) so stale tail bytes are re-read, and/or
   the `children_count` → `byte` cast (`Bnk.cs:931`) truncating counts > 255. **Fix (per
   `BNK Manager/AGENTS.md` (unpublished local notes)):** try native .NET 4.8 under Wine
   (`winetricks dotnet48`), and/or change `Save()` to `FileMode.Create` and rebuild.
6. **`DB.bnk` contents are encrypted.** **Symptom:** `.db` files from `DB.bnk` are unreadable.
   **Cause:** TDU1-era XTEA-CBC DB encryption (key/IV scheme in `bnk_packcdb.py`); decrypted
   text starts with `//`. **Fix:** decrypt with that scheme; all other BNK types are plain.
7. **Tree section truncated at the first zero byte.** **Symptom:** a repacked BNK reads only part
   of its hierarchy. **Cause:** `_UpdateTreeSection` stops at the first `0x00`; a directory with
   zero children emits `children_count = 0x00`. **Fix (reasoned, untested):** don't rely on the
   zero-scan — size the tree from the written length, or ensure no empty directories are packed.
8. **`.2dm` colour files break the extension→type cache.** **Symptom:** wrong `uint32` type on
   repack for colour files. **Cause:** `Bnk.cs` warns that 2DM files can carry a different id, so
   the per-extension cache is not always reliable. **Fix:** preserve each file's original `type`
   from the source BNK (tdumt2 copies prior magic/type when the path matches) instead of
   re-deriving from the extension.
9. **A name-blob walk stops short in ~29 of 9,663 banks.** **Symptom:** the tree yields fewer
   leaves than `packed_count`, and the reader desynchronises (e.g. 510 expected, 9 walked for
   `Islands/hawai/Level/Commonworld.bnk`). **Cause:** the blob is a *forest*; a single recursive
   call consumes one top-level tree and leaves the sibling trees unread. **Fix:** loop
   top-level `walk("")` calls until exactly `packed_count` leaves are collected (2026-10-06,
   retail PC: fixed this in a custom parser, which then read 9660/9660 banks cleanly).
10. **A handmade bank parses into nonsense names.** **Symptom:** folder names come out as
   garbage lengths. **Cause:** `Physics/Tires.bnk` writes folder lengths *without* Eden's
   negation, so a length `>= 0x80` is impossible to distinguish from a large file name.
   **Fix:** recognise the file (build year 2026 in a 2011 tree, `PACEJKA TIRE FLE` watermark)
   and skip it rather than special-casing the format.

## Assets

None — container/format research, not art or audio authoring.

## Cost and time

One session. No paid tooling. The `.big`/`.map`/`.xmb` reading is tool-source-only; the `.bnk`
byte-level section reads retail game data directly with local parsers (nothing written back).

## Open questions

- The small utilities were read only as names/dirs (no source or readme shipped):
  `TDU2-HashGen` (with `tdu2.dll`), `TDU2-Bin-Renamer`, `TDU2-BNK-File-Locator`,
  `TDU2-BNK-Finder`, `TDU2-BNK-Guts-Viewer`, `TDU2-Music-Extractor`. Their exact behaviour is
  **inferred from their names** — likely: hash generator for the `FileNames.list`/`.map` hashes,
  a bulk file renamer, BNK locators/finder, a BNK internals viewer, and a Wwise/BNK audio
  extractor. Confirm before relying on them.
- Header field `[24:28]`/`[28:32]`: `Bnk.cs` names them BlockSize1/BlockSize2 and says TDU2 is
  "4 or 32" and "always 16", while `bnk_packcdb.py` labels `[28:32]` as file_block_size
  "16=TDU1, 20=TDU2". **Partly settled 2026-10-06:** the sizes-section entry stride is 20 for
  TDU2 (a 20-byte stride parses all 9660 retail banks cleanly; `Airport.bnk` reads
  `0x20 = 32`, `0x24 = 16`), so `[28:32]` is not the entry size — the two accounts are
  reconcilable if `bnk_packcdb.py` conflated the header field with the stride. Why BlockSize1
  differs per bank (32 here) is still open.
- The repack bug is not reproduced here. Is `FileMode.Create` alone sufficient, or is the
  `children_count` truncation the real cause (or both)? A byte-diff of original vs repacked BNK,
  then an in-game load, is the real oracle.
- The `unknown2`/magic section is unimplemented in tdumt2 (`_UpdateUnknown2Section` throws).
  What does it hold, and can a BNK without it be loaded after a repack?
- Are `.map` entry arrays sorted, and is the `.map` appended-to or rebuilt when a mod adds files?
- Does `XMBF` use one schema for both `.map` indexes and `CarVSTConfig*.xmb`, or per-file schema
  tables? Same magic/version, but the two tools never cross-check.
