---
kind: technique
title: "Ekey's `.Tool` family: one C# unpacker per game container, and the container layouts behind them"
tags: [archive-formats, unpacking, repacking, tool-catalogue, container-layout, name-hash, re-engine, elden-ring, nfs, ets2, tdu2, farcry, uncharted, quantic-dream, oodle]
date: '2026-10-13'
agents:
- OpenCode (DeepSeek V4.1 Flash)
humans: []
links: ["https://github.com/Ekey"]
status: in-progress
---
# Ekey's `.Tool` family: one C# unpacker per game container, and the container layouts behind them

> Ekey (Christian Black) keeps 55 small C# tools, one repo per game container: `REE.PAK.Tool`,
> `ER.BDT.Tool`, `NFS.BIN.Tool`, `ETS2.SCS.Tool`, `TDU2.BIG.Tool` and so on. 37 of them are archived, and
> `BW.WPK.Tool` has been blocked by a DMCA notice since December 2025. Two things make the family worth
> knowing: for several containers it is the only public implementation (the table below says which), and
> each tool is small enough to read the container layout straight out of the source. This note records
> that layout, so the next person can write a parser instead of transcribing one.

## When to use it
- You know the container (`.pak`, `.bdt`, `.scs`, `.big`, `.psarc`, `.bin`, `.pkg`, `.npk`, `.arc` …) and the
  game, and you need to extract or repack now.
- No maintained alternative exists, and you want the layout rather than a binary: the tables below give the
  magic, header fields, entry stride and name-hash scheme.
- You want a second implementation to cross-check a format you are already parsing.

## How
Naming is `<ABBREV>.<FORMAT>.Tool`; the executable is `<ABBREV>.Unpacker`. Seven repos also ship a packer
(DSR, KG, NFS, REE, RS, SC, TXA). Almost every tool follows the same shape: read the header, validate a magic
and often a version, read a fixed-stride entry table, resolve each entry's name through a name list shipped
in the repo, then copy or decompress from an offset in the same file or a sibling payload file.

Recurring conventions and traps:
- **.NET Framework 4.7.2** for most builds (60 of the 68 projects; a few target 4.8 or 4.5.2), so a
  Wine/mono run needs that runtime, not .NET 8.
- **Oodle**: two routes. The two tools that need it load the game's own DLL beside the exe —
  `oo2core_6_win64.dll` (Elden Ring), `oo2core_9_win64.dll` (Uncharted: Legacy of Thieves) — copied from
  the user's install, never redistributed. The open-source route is **ooz** (`powzix/ooz`, a
  Kraken/Mermaid/Selkie/Leviathan/LZNA/Bitknit decompressor; its forks `rarten/ooz`, `abheekda1/ooz`
  (formerly ADawesomeguy) and `brunoanc/ooz`). WolvenKit falls back to an ooz build (`kraken.dll`,
  `libkraken.so`, `libkraken.dylib`) when Oodle's DLL can't be loaded (WolvenKit/WolvenKit#316, PR #655).
  There is a Rust port (`lvlvllvlvllvlvl/oozextract`) and a Python wrapper around a C build
  (`baconwaifu/python_oodle`). Decompression is the reliable half: rarten's fork adds a Kraken, Mermaid,
  Selkie and Leviathan compressor, but its output isn't byte-identical to Oodle's at the same level
  (WolvenKit compresses at level 4 on ooz and uses 6 only with the real DLL, per #316), so a game that
  validates its own compressed sizes still wants the real DLL.
- **The name tables are the valuable part of the clone.** Most repos ship
  `<X>.Unpacker/<X>.Unpacker/Projects/FileNames.list` (plain paths, or hash → path); `REE.PAK.Tool` has
  one `Projects/<TAG>.list` per title at the repo root (about 90), and `ETS2.SCS.Tool` one per game. They
  run from a few hundred bytes to 60 MB (`ER.DATA.Tool`). The 54 reachable repos hold about 655 MB at HEAD,
  451 MB of it in `REE.PAK.Tool`. 21 of them ship no list at all.
- **Completeness is stated honestly per archive** (Elden Ring `Data0` 4422/4434 = 99%, `Data1`–`Data3` 100%;
  ATS `base.scs` 99%, `core.scs` 1%). Missing files are a tool gap, not a corrupt archive.
- **Repacking is the exception**, and where it exists the README flags the caveat: `REE.PAK.Tool` has
  `REE.Packer`; `NFS.BIN.Tool` repacks but says the index (`ZDIR.BIN`) must be replaced along with the
  archives, and that its packer is untested in games.
- **Byte order varies.** Several tools read most fields big-endian (TDU2, Quantic Dream, PSARC below), so
  check the reader's `ReadInt32(true)`-style flag before trusting a field list.

## Superseded, co-maintained, or alone
Alternatives checked 2026-10-13. **superseded** = a maintained tool does more than Ekey's; **co-maintained** =
there is a sibling tool with the same extract-only or stale limitation; **alone** = no public alternative found,
so the layout below is the documentation.

| Container | Alternative (repo · ★ · last push · license) | Verdict |
|---|---|---|
| RE Engine `.pak` | `eigeen/ree-pak-rs` 74★ 2026-04 MIT + `ree-pak-gui` 57★ 2026-05; FluffyQuack `REtool` (closed). Ekey 413★ 2026-10 is still the most-starred | co-maintained |
| Elden Ring `.bhd`/`.bdt` | `vawser/Smithbox` 736★ 2026-10 MIT (decrypts and reads the BHD5 archives); `ividyon/WitchyBND` 273★ 2026-07 GPL-3 handles the BND/BXF binders inside them, not BHD5 | superseded |
| ATS/ETS2 `.scs` | official `scs_packer`/`scs_extractor`; `sk-zk/TruckLib` 44★ 2026-09 GPL-2 | co-maintained |
| CDC / Foundation `TIGER` + `.drm` (CDC's "Data Ram" resource-section files, not copy protection) | `gibbed/Gibbed.CrystalDynamics` 18★ 2026-06 Zlib (pack, unpack and `.drm` tools). Ekey's tool unpacks TIGER v3/v4/v5/v8 and dumps `.drm` sections, with no packer; spec at cdcengine.re | co-maintained |
| Uncharted LOT `.psarc` | `rm-NoobInCoding/UnPSARC` 91★ 2025-10 MIT (unpack+pack) | superseded |
| Enshrouded / Keen `kfc_data` | `Brabb3l/kfc-parser` 44★ 2026-04 GPL-3 (+ mod loader) | superseded |
| Crimson Desert `.paz` | `hzeemr/crimsonforge` 18★ MIT (archived), `LukeFZ/pycrimson` 9★ MIT, `potter420/crimson-rs` 8★ MIT | superseded |
| NFS console `ZZDATA` | quickbms `nfsu_bun.bms`; NFS Modding Wiki lists Ekey as current | co-maintained |
| TDU2 `.big` | `djey47/tdumt2` 9★ MIT, `djey47/tduf-next` 9★ MIT (2023) | co-maintained |
| Far Cry Instincts `FAT`/`DAT` | none confirmed: FCBConverter and the Dunia tools target later Far Cry games | alone (unconfirmed) |
| Quantic Dream `BigFile` | `otuva/Detroit-Become-Human-Tools` 7★ 2025-04, archived (DBH assets only, extract-only) | co-maintained |
| Apex `TAB`/`ARC` (Ekey: Ravenbound, Second Extinction) | `kk49/deca` 133★ 2025-12 MIT (Generation Zero, theHunter: COTW, Just Cause 3 and 4, RAGE 2, Second Extinction; basic archive rebuilding); `gibbed/Gibbed.JustCause4` 27★ 2019, `EonZeNx/apex-tools` 4★ 2024 | co-maintained |
| Metroid Dread `.pkg` | `UltiNaruto/PKGTool` 5★ 2022 MIT, `kriogenic/DreadPKG` 1★ 2022, `randovania/dread-editor` 7★ 2024 GPL-3 — all stale | co-maintained |
| Marvel Ultimate Alliance `.bin` | aluigi quickbms `marvel_ultimate_alliance.bms`; `nikita488/raven-formats` 2024 MIT | co-maintained |
| MELTY BLOOD: TYPE LUMINA `.bin` | none — Mizuumi FPANModding points at Ekey; `lioncash/ExtractData` handles only old Melty Blood | alone |
| LifeAfter `.npk` | none — Ekey's tool is **archived**; NeoXtractor #50 reports the format unsupported, and a commenter there describes 48-byte entries and zstd, so Ekey's 2021 layout (below) may be stale | alone |
| Demiurge `.sar`; Sacred Citadel `.vfs`; TAISHO x ALICE `.dat` | none — only loose ResHax BMS/Noesis scripts | alone |

Public written specs exist for three: RE Engine `.pak` (XentaxWiki `RE_Engine_PAK`; `ree-pak-rs` DeepWiki;
`Backporter/RE-PAK` `PAK.bt` 010 template), Elden Ring BHD5 (Souls Modding Wiki dvdbnd description;
`JKAnderson/SoulsFormats` FORMATS.md enumerates BHD5/BND/BXF; exact byte layout still source-only), and
ETS2/ATS HashFS (`trucklib` docs: CityHash64 of the UTF-8 path, optional directory listings, HashFS v2 since
1.50 merges tobj+dds; SCS Modding Wiki Game Archive Packer). Everywhere else the layout below came from
reading Ekey's `*Header.cs`/`*Entry.cs`.

## Container layouts
Grouped by the shape that matters when you write a parser.

### Index file plus sibling payload
- **TDU2 `.big` + `.map`.** Index magic `XMBF` (0x46424D58), version 257; Ekey's reader takes every
  later field big-endian. Header: structure-names offset (28), structure-names table offset (224), then
  sub-header offset; at sub-header+4 read total files, sub-header size (24), record count (== total
  files), records offset. A `u64` name-hash table follows the sub-header; the record table (at
  sub-header+records offset) is `i32 size` + `i64 offset` into the `.big`. Each file's payload is XORed
  with the repeating 4-byte key `D7 A8 E2 D4`, restarting at the file's first byte. The KB's
  [TDU2 archive note](../games/test-drive-unlimited-2/tdu2-archive-and-container-formats.md) has the full
  layout, the hash seeds and the other TDU2 containers.
- **Far Cry Instincts `FAT`/`DAT`.** `DAT2` magic (0x32544144) + `i32 total files`. The entry stride
  self-detects: if file size equals `totalFiles*12 + 8` it is the old 12-byte entry (`u32 offset`,
  `i32 uncompressed size`, `u32 CRC32`), otherwise 16 bytes with `i32 compressed size` inserted. Names are
  the standard IEEE CRC-32 of the path with a leading backslash. Payload is the sibling `.dat`; entries are
  stored raw when compressed size equals uncompressed (or is zero), else LZMA.
- **Quantic Dream `BigFile`.** Fields are big-endian. Index magic is the ASCII string
  `QUANTICDREAMTABINDEX`, then `i32 version` (13 Heavy Rain, 17 BEYOND, 18 Detroit), `i32 unknown`
  (13→65535, 17→0, 18→11548767), a 72-byte `ZEPZEP…ZEP` sub-magic, one extra byte in v18, then
  `i32 total files`. Entry:
  `i32 resourceTypeID`, `i32 flag`, `i32 fileID`, `u32 offset`, `i32 size`, `i32 paddedSize`,
  `i32 packageID`; names appear only when debug files ship. Payloads live in archives named by `packageID`
  (0 is `<base>.dat`, any other value `<base>.dNN`).
- **Metroid Dread `.pkg`.** Header is three `i32`: table size, archive size, total files, and the invariant
  `tableSize + archiveSize + 4 == file length`. Entry: `u64 hash`, `u32 offset`, `u32 size` — where the
  third field behaves as an *end offset* (the tool copies `size - offset`). Names via a CRC-64 table list.
- **Apex `TAB`+`ARC` (Ravenbound, Second Extinction).** Index magic `TAB\0` (0x424154), major 3, minor 1,
  alignment 4096; header carries total files, cache-table size (`*8`), unknown, max compressed/decompressed
  block size. Entry: `u64 hashName`, `u32 offset`, `i32 compressed`, `i32 decompressed`, `u16 id`,
  `u16 compressionType` (3 = ZSTD).
- **Just Cause `TAB`/`ARC` (older).** Version 3, alignment 2048, `u32 totalArchives`, `i32 totalFiles`;
  entry `u32 hash`, `u32 rawOffset`, `u32 offset`, `i32 size`, `i32 archiveID`.
- **NFS `ZZDATA`.** Entry: `u32 nameHash`, `i32 archiveID`, `u32 localOffset`, `u32 totalOffset`,
  `i32 size`, `u32 checksum`. Two index generations: the old form (`-true`) is only Hot Pursuit 2 on PS2.
- **LifeAfter `.npk`.** Header: `u64 hash`, magic `NXPK` (0x4B50584E), version, table offset/size, total
  files. Entry: `u64 hash`, `u32 offset`, compressed/decompressed sizes, compressed and decompressed CRC,
  `i32 compressionFlag` (2 = LZ4).
- **Romancing SaGa `IDX`+`BIN`.** Two magics: `THDR` (0x52444854) v8 + total files + alignment 16, then
  `TFIL` (0x4C494654) + table size. Entry: `u32 hash`, `u32 offset` (multiply by alignment), `i32 size`.
- **Ray Gigant `.bin`+hash.** Two magics: `bin.` (0x2E6E6962; header size 32, entry-data offset +16, table
  sizes, flag −1) and a `hash` block table (0x68736168) with 1 MiB blocks of `u32` block hashes.
- **FC LPKG (Furyu).** Table magic `LCAC` (0x4341434C) v120, total files, total lpkgs; chunk magic `LCD1`
  (0x3144434C) + decompressed size. Entry: `u32 nameHash`, `u32 crc`, `i64 packageID`, `i64 offset`,
  `i64 size`.
- **Treasure Island `.dat`.** `PACK` magic (0x4B434150) + table size, archive size, reserved, total files,
  and the constants 64/16/128. Entry: 104-byte name, unknown, `u32 CRC32`, `u32 offset`, `i32 size`,
  `i64 reserved`.
- **King of Meat `gpak`.** Magic `gpak` (0x6B617067), minor 2, major 32, serialise revision 47, total files,
  archive parts (6), base offset, files-data size. A hash table holds one MurmurHash3_x64_128 of the
  lowercased UTF-8 path per file (seed `0xA9401E9F`, stored as two `u64` halves); a parallel table holds
  `i64 offset` (relative to the base offset) and `i64 size`. The tool targets the King of Meat technical
  test.
- **Demiurge `SAR`** (Puzzle & Glory, MARVEL Puzzle Quest, SEGA Heroes). Magic 0x0000DA7F.
- **Pivotal Games `DAT`** (the Conflict series, The Great Escape). Entry: `u32 hash`, `u32 offset`, `i32 size`.
- **Juiced `DAT`.** Header: total files + table offset. Entry: `u32 hash`, `u32 offset`, `i32 chunks`,
  compressed/decompressed sizes with a 32 KiB max chunk.
- **Juiced 2 `JFS`.** Header is a single `i32 total files`. Entry: `u32 hash`, `u32 offset`,
  compressed/decompressed sizes, compression level, and a boolean compressed flag.
- **Marvel: Ultimate Alliance `.bin`.** Magic 0xB19ACA6E, version 1, compression type 17 (zlib), total files,
  index compressed size, names decompressed/compressed sizes, base offset. Entry: `u64 unknown`,
  `i64 nameOffset`, `i64 offset`, `i64 compressed`, `i64 decompressed`, plus the name.
- **Sacred Citadel `.vfs`.** Magic 0x0F11350D + total files; entry `u32 hash`, `i32 size`, `u32 offset`.
  A packer exists.
- **KOK3 `.lpq`.** Header: archive size, flags 1, `u32 hash`, version 8, header size 56, block files,
  reserved, total files, block-table size, hash-table size. Entry: `i32`/`u32` unknowns, attributes,
  `u32 offset`, compressed/decompressed, file ID, file hash, file time.
- **Crimson Desert `META`+`PAZ`.** META magic 0x610E0232 (or 0), checksum, total archives, unknown fields,
  archive size, folder/name table sizes, total folders/files. Entry: name offset, `u32 offset`,
  compressed/decompressed, `i16 archiveId`, `i16 flags`, plus encryption and compression enums.
- **Keen Games `kfc_data`.** Magic `KFC0` (0x3043464B), total files twice, reserved, `i64 archive size`.
  Entry: `u64 hashName`, decompressed, compressed, file number, flag (1/2), `i64 offset`. Extract + repack.
- **Kingdom Under Fire 2 `PKG`.** Magic `BEAR` (0x52414542), v2.1, `i64 total files`,
  `i64 table size`, `u32 seed`. Entry: `u64 nameHash`, compressed/decompressed, file number, reserved.
- **Lords of the Fallen `PKG`.** Chunk magic 0x02012201 stored / 0x02012001 LZ4, plus decompressed size,
  max chunk size, compressed size. Entry: `i64 offset`, sizes, `u32 nameHash`, unknown (11), layer ID.
- **Stella Maiden `PKG`.** Magic 0x01E2393F, with a custom cipher module.
- **Archlord 2 `.apk`.** Magic 0x4034B50 — a ZIP local-file header standing in for the container magic.
  Entry: fixed 128-byte name, decompressed size, encrypted flag, CRC32, compressed size, offset.
- **Run Sackboy! Run! `.pak` (OBB).** Magic 0x50414B31 (`1KAP`), total files, entry-table offset. Entry:
  `u32 hashName`, `u32 unknown`, decompressed/compressed sizes, `u32 offset`.
- **Under Night In-Birth II `Data`.** Header: total folders, total files, archive size, 0x34-byte archive
  name. Entry: decompressed, compressed, `u32 offset`, 0x40-byte name.
- **Wushu Chronicles 2 `PACKAGE`.** Magic `PCK0` (0x304B4350), version 20, patch version, flags, total files,
  compressed/decompressed table sizes, flag. Entry: `i16 file ID`, `i64 offset`, sizes, CRC, unknown, flag,
  name.
- **Touhou `PAK`.** Header is just `i32 table size`. Entry: Shift-JIS name, compressed/decompressed,
  `u32 offset`, a one-byte flag, `u32 seed`. The seed initialises an MT19937 generator whose output is a
  64-byte repeating XOR key for that file; the entry table is XORed the same way, seeded with the table
  size.
- **ZLL2 `PAK`.** Magic `KAPY0700`, header size 64, total files, entry/name table offsets, a
  compressed+decompressed size for each table, block size 262144. Entry carries two compressed sizes and an
  internal block size of 1024.

### Single-file archives with a names or hash table inside
- **RE Engine `.pak`.** Header: magic `KPKA` (0x414B504B), `u8 major`, `u8 minor`, `i16 feature flags`,
  `i32 file count`, `u32 fingerprint`. v2.0 = Kitchen PS4 demo; v4.0/4.1/4.2 otherwise. Feature flags the
  tool accepts: 0, 8 (encrypted entry table, decrypted with a 128-byte RSA-encrypted key → PKC), 12 and 44
  (DLC extra data), 24 (an extra `i32`), 40 (chunked resources) and 104 (Dragon's Dogma 2). Each entry
  carries two `u32` name hashes: Murmur3_32 (seed `0xFFFFFFFF`) of the UTF-16LE path lowercased, and of it
  uppercased. A v4 entry (48 bytes) is the two hashes, `i64 offset`, `i64 compressed`, `i64 decompressed`,
  `i64 attributes` (compression in `attr & 0xF`, encryption in `(attr >> 16) & 0xFF`) and `u64 checksum`;
  a v2 entry (24 bytes) is `i64 offset`, `i64 decompressed` and the two hashes. Names resolve against the
  per-title `Projects/<TAG>.list` files, which the later Rust/GUI tools still borrow from here.
- **Elden Ring `BHD5`+`BDT`.** The `.bhd` header file is RSA-encrypted; the tool decrypts it first with
  the per-archive public keys it ships (SoulsFormats' reader expects it already decrypted). Then: magic
  `BHD5` (0x35444842), an endianness byte (0xFF = little-endian) and a flag byte (Ekey reads these four
  bytes as an `i32` "version" 511), an `i32` that is always 1, data size, bucket directory count/offset,
  and a length-prefixed salt. Names hash as `h = h*133 + c` into a `u64`. Entry: `u64 nameHash`,
  `i32 paddedSize`, `i32 size`, `i64 offset`, `i64 shaHashOffset`, `i64 aesKeyOffset`. The SHA block is a
  32-byte hash plus a range count and `{i64 start, i64 end}` ranges; the AES block is a 16-byte key plus
  its own range count and ranges. Compressed members arrive wrapped in DCX (`DCX\0`, `DCS\0`, `DCP\0`,
  `DCA\0`; codec `DFLT` = zlib or `KRAK` = Oodle Kraken).
- **Uncharted `PSARC`.** Big-endian. Magic `PSAR` (0x52415350), v1.4. Compression is a fourcc: `oodl`
  (0x6C646F6F) or `zlib` (0x62696C7A); header size, entry size, total files, block size 65536, flags.
  Entry (30 bytes): 16-byte MD5 of the ASCII path, `u32` first block index, then a 40-bit decompressed size
  and a 40-bit offset (a byte plus a `u32` each). A `u16` block-length table follows the entries, and names
  come from the archive's own `NamesLookUp.txt`.
- **Sniper Fury `GLA2`.** Version 0, table offset, total files, magic 0xA9D10201. Entry: `u32 hash`,
  `u32 offset`, decompressed/compressed, reserved, `i32 encrypted` (values 0/1/8 hint at the algorithm).
- **Sine Mora `.bin`.** Entry: two `u32` hashes plus an extension hash, decompressed/compressed, `i64 offset`.
- **Rocket Knight `ARC`.** No magic: `u32 unknown` (64016), `i32 total files`, `i32 table size`,
  `i32 padded`. Entry: `u32 hash`, `u32 offset`, compressed/decompressed.
- **SNK HEROINES `WAD`.** Magic `AGAR` (0x52414741), two version fields, `u64 reserved`, `u32 table size`
  where the high bit signals an encrypted table (mask 0x7FFFFFFF). Entry: name (present when the table is
  not encrypted), size, flags, `i64 offset`.
- **Bright Shadow (2009) `PAK`.** Magic `PACK` (0x4B434150). Entry: `i32 nameLength`, name, `u32 offset`,
  `i32 size`, `u32 encFlags` (0x20000001 = encrypted XML/TXT), reserved.
- **Batman Arkham Origins Blackgate `ARA`.** Magic `ARMA` (0x414D5241), version 2, total files, entry count
  8192, table offset, base offset, reserved. Entry: `u32 nameHash`, `u32 offset`, two `u16` unknowns,
  compressed/decompressed, flag.
- **Bravely Default: Fairy's Effect `ARC`.** Entry name hash is an MD5 string; offset and compressed size.
- **`EPK` (`HP.EPK.Tool`; its README names the game 画皮世界).** Magic 0x1A545352, versions 0x20110224 and
  0x20110425, table offset, base offset 64, valid/max table numbers, package size, total files. Entry: name
  hash, folder hash, offset, sizes, entry type, compression type, name length, two timestamps, MD5.
- **League of Angels `BTFC`/`JLUA`/`JPAK`.** Three container magics: cache 0x43465442, Lua scripts
  0x41554C4A, pak 0x4B41504A; cache entry carries a name plus `u32 hash`.
- **Dogbyte `XPAK`.** Magic `XPAK` (0x4B415058).
- **Devil Slayer: Raksasi `ALP`.** Magic `ALP$` (0x24504C41) + table offset. Entry: offset, size, name
  length, name. A packer exists.
- **FSZHS (封神召唤师) `MP3`.** Signature 0x1A435443; the tool also ships a `FolderNames.list`.
- **CosmicBreak `KAR`.** Table size/offset/seed, total files, password, MD5, compression, timestamp. Entry:
  first path, second path, per-file password, size, offset, seed.
- **TAISHO x ALICE `DAT`.** ASCII magic `GAMEDAT PAC2` + total files. Entry: name, `u32 offset`, `i32 size`.
  Extract + repack.

## Gotchas
1. **No license on any of the 55 repos.** `license` is null for all of them (checked via the GitHub API on
   2026-10-14). Read the layout, do not vendor the code into a shipped mod, do not republish binaries.
   Expect gaps when cloning: `BW.WPK.Tool` returns HTTP 451 (DMCA, December 2025).
2. **A missing Oodle DLL looks like a generic failure.** Symptom: unpack dies or writes zero files.
   **Cause:** `oo2core_*_win64.dll` was not copied beside the exe. **Fix:** copy it from the user's own
   install (the version matters: 6 for Elden Ring, 9 for Uncharted). An ooz build is not a drop-in: the
   tools hard-code the `oo2core_*` file name and the `OodleLZ_Decompress` entry point, while ooz builds
   export `Kraken_Decompress`, so it needs a shim DLL or a source edit.
3. **Silent partial extraction.** Symptom: expected files absent, no error. **Cause:** the README's
   completeness percentage is real. **Fix:** read the table and treat gaps as a tool limit.
4. **Wrong tag/list file.** Symptom: unknown names or a pack the game refuses. **Cause:** the tag list is
   title/build specific. **Fix:** pick the tag for the exact build, and unpack base before patch archives.
5. **Repacking needs the index too.** Symptom: repacked archive loads but nothing mounts. **Cause:** for
   `ZZDATA`, `ZDIR.BIN` must be replaced as well. **Fix:** repack the index with the payload.
6. **Hash collisions are silent.** Symptom: one entry unpacks under another file's name. **Cause:** the name
   tables are the only name source, and several games store truncated (32-bit) hashes. **Fix:** cross-check
   sizes/offsets against the tool's own listing before trusting a path.

## Seen in
- `knowledge/games/elden-ring/cs2-conversion-of-elden-ring-offline-native-rust-dll-via-me3.md` — that note
  uses WitchyBND for params; `ER.BDT.Tool` is the smaller route for bulk `.bdt` extraction.
- Docs site (`open-source-modding.github.io`): `docs/ets2/ets2-formats.md` and `docs/nfs/nfs-formats.md`
  cover two of these containers with their own tooling; `docs/farcry/filelists.md` is the same
  name-table problem as `Projects/FileNames.list`.

## Open questions
- Does the family run under a Wine prefix with .NET Framework 4.7.2, or does it need a Windows host?
- Several tools were last pushed in 2022 (TDU2, ETS2, Uncharted; `NFS.BIN.Tool` was updated in July 2026):
  has any of those containers changed since?
