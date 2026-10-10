---
kind: game
title: "Reading Frostbite 3 data: .toc/.sb/.cas archives, .cat catalog and .ebx binary XML (Battlefield 4)"
game: "Battlefield 4"
games_also: ["Battlefield 3 (same tooling, BF3 bundle magic)", "other Frostbite 3 titles"]
game_version: "retail PC (Python 2 tooling written against 2013-era BF4 data)"
platform: linux
engine: frostbite
route: data
tools: ["Frankelstner's Frostbite-Scripts (community Python 2 tooling)", "bf4dumper (community Python 2 tool, from a forum attachment)", "fb3decoder", "python2.7", "Zench ealayer3.exe (for EALayer3 audio) — Windows/Wine"]
anti_cheat: "FairFight + PunkBuster — offline extraction of shipped data only; nothing is injected into a running game"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links:
  - "https://github.com/NicknineTheEagle/Frostbite-Scripts"
tags: [frostbite, battlefield, bf4, ebx, toc, superbundle, cas, cat, lz77, delta-patch, audio, xas, ealayer3, speex, python2]
---

# Reading Frostbite 3 data: .toc/.sb/.cas archives, .cat catalog and .ebx binary XML (Battlefield 4)

> Notes taken while reading a community Python 2 dumper for Battlefield 4 / Frostbite 3 game data.
> Frostbite splits a build into a text-ish `.toc` tree, binary `.sb` super-bundles, and content-addressed
> `cas_XX.cas` blobs catalogued by `.cat`; individual objects serialise as `.ebx` binary XML keyed by a
> DJB2 string hash. The tooling is **in-progress** for extraction and text conversion (the dumper was
> read, not run); it is Python 2 and was written against one game build, so treat every offset as
> version-sensitive.

## Setup

- The dumper arrived as a forum attachment (`mirrors_edge/topic_14259_bf4dumper/.../bf4dumper.rar`) but the
  code is 100% Battlefield 4 / Frostbite 3 (it hardcodes a `bf4Directory` and BF4 `resTypes`), *not* Mirror's
  Edge. Trust the code over the folder name. Frankelstner's Frostbite-Scripts
  (https://github.com/NicknineTheEagle/Frostbite-Scripts) are the reference tooling for this family.
- It is **Python 2** (`print` statement era, `cPickle` used in `ebxtotext.py`). Run it with `python2.7`; on a
  modern box that means a Python 2 interpreter or a container, not the system `python3`.
- Audio needs Windows helpers: `xas.dll` / `xas_decode.exe` (XAS1/EA ADPCM) and `easpeex.dll` (Speex) ship
  next to `fb3decoder.py`; EALayer3 is MP3-family and is best handed to Zench's `ealayer3.exe`.
- Bundle layout read from the extracted sources:
  `~/.../bf4_dump/{bf4dumper.py, cas.py, noncas.py, ebxtotext.py}` and
  `~/.../fb3decoder/fb3decoder.py` (paths are the extracted copy, not the workspace original).

## Route and why

Pure **data** route. The goal was to read shipped assets, so there is no hooking and nothing touches the
running game. The alternative — hooking the engine's own file system to dump on load — was rejected because
the archive formats are self-describing enough to parse statically, and because BF4 is online-protected
(FairFight/PunkBuster); offline parsing keeps the work well clear of anti-cheat.

## How the game works (what we had to learn)

### Paleolithic overview: `.toc`, `.sb`, `.cas`, `.cat`

- **`.toc`** is a near-text "Entry" tree. Each entry starts with a type byte (`0x82` ordinary, `0x87` rarer),
  then a LEB128 (`read128`, 7 bits/byte) size and a list of typed fields. Field data-type bytes: `0x0f` id
  (16 B), `0x09` Q (8 B), `0x08` I (4 B), `0x06` bool (1 B), `0x02`/`0x13` blob (read128 length), `0x10` sha1
  (20 B), `0x07` string (read128 length, NUL included), `0x01` list (read128 count of nested entries, ends on
  a null). (`cas.py`: `Entry`, `addField`, `read128`.)
- **TOC/CAT obfuscation** (`cas.py`: `unXor`): a magic of `0x00D1CE00`/`0x00D1CE01` means the file is
  XOR-encrypted with a signature; seek to offset 296, read a 260-byte key, XOR every key byte with `123`
  (bytes 257–259 are unused), then `data[i] ^= key[i % 257]`. Magic `0x00D1CE03` means a signature but an
  empty key (not encrypted) — seek 556. Anything else is plain.
- **`.cat` catalog** (`bf4dumper.py`: `readCat`): skip the first 16 bytes ("nyan" magic), then each record is
  `sha1(20 B) + unpack("<III")` = `offset, size, casNum`. The blob is `cas_%02d.cas`. So `.cas` is
  content-addressed: the catalog maps logical assets to (file, offset, size).
- **`.sb` non-CAS bundle** (`noncas.py`: `Bundle`): a big-endian header. First a `u32` meta size, then eight
  `u32` header words: magic (BF4 `0x9D798ED5`, BF3 `0x970d1c13`), `totalCount`, `ebxCount`, `resCount`,
  `chunkCount`, `stringOffset`, `chunkMetaOffset`, `chunkMetaSize`.
  - Then a sha1 list (20 B × `totalCount`).
  - Then `ebx` entries: two `u32` (`nameOffset`, `originalSize`).
  - Then `res` entries: two `u32` + `resType u32` + 16-byte `resMeta` + `u64 resRid`.
  - Then chunks: 16-byte id + `u16 rangeStart` + `u16 logicalSize` + `u32 logicalOffset`, where
    `originalSize = logicalSize + logicalOffset`.
  - Names live NUL-terminated in the string section.
- **LZ77 blocks** (`noncas.py`: `seekLZ77Block`): big-endian `u32 decompressedSize`, `u16 compressionType`,
  `u16 compressedSize`. Types `0x70`, `0x71` and `0` mean **stored** (skip `decompressedSize` bytes);
  `0x970` means LZ77-compressed; anything else is unknown — bail rather than guess.
- **Delta/patch bundles** (`noncas.py`: `patchedBundle`): a delta stream begins with magic
  `"\0\0\0\x01\0\0\0\0"`, then big-endian `u32 deltaMetaSize`, `u32 deltaPayloadSize`. Metadata instructions
  are `u32 split1v7` = high 4 bits type, low 28 bits size: `0` copy base, `4` skip base, `8` copy delta.
  Payload instructions: `0` base blocks as-is, `2` tiny fix (`u16 size+1` of delta), `1` large fix (each
  iteration `u16 targetOffset`, `u16 skipSize`), `3` delta blocks, `4` skip. A patched ebx's filename comes
  from the `Name` field of its primary instance.

### `.ebx` binary XML ("dbx")

- Magic `0xCED1B20F` (little-endian file) or `0x0FB2D1CE` (big-endian).
- Header (36 B, unpack `"3I6H3I"`): `absStringOffset, lenStringToEOF, numGUID, numInstanceRepeater,
  numGUIDRepeater, unknown, numComplex, numField, lenName, lenString, numArrayRepeater, lenPayload`.
- Then: `fileGUID` (16 B), padding to 16, `externalGUIDs` (`numGUID` × (16+16)), keyword names (`lenName`),
  and a keyword dictionary built with a **32-bit DJB2** hash (offset basis `5381`, multiplier `33`).
- Descriptor tables: `fieldDescriptors` = `"IHHii"` (16 B: `hashName, type, ref, offset, secondaryOffset`);
  `complexDescriptors` = `"IIBBHHH"` (16 B); `instanceRepeaters` = `"2H"`; `arrayRepeaters` = `"3I"`.
- Payload starts at `absStringOffset + lenString`; the array section starts at
  `absStringOffset + lenString + lenPayload`.
- **Field types** worth keeping: `0x0029`/`0xd029`/`0x0000`/`0x8029` = complex; `0x0041` = array;
  `0x407d`/`0x409d` = string (`i32` offset into the string section, `-1` = null); `0x0089`/`0xc089` = enum;
  `0xc15d` = 16-byte chunk GUID; `0x417d` = 8 bytes. The scalar dictionary: `0xC12D` Q, `0xc0cd` B, `0x0035`
  I (link), `0xc10d` I, `0xc14d` double, `0xc0ad` bool, `0xc0fd` i, `0xc0bd` b, `0xc0ed` h, `0xc0dd` H,
  `0xc13d` float.
- Alignment gotcha: instances flagged alignment-4 need **8 subtracted** from every field offset and size
  (`obfuscationShift`); miss this and every value reads 8 bytes off.
- `ebxtotext.py` converts ebx → `.txt` and builds a `fileGUID → filename` table (via `cPickle`) so
  cross-file GUID links resolve to names. It deliberately ignores `RawFileDataAsset`.

### Audio inside chunks (`fb3decoder.py`)

- An audio segment begins with magic `48 00 00 0c`, then one `audioType` byte: `0x12` PCM (big-endian
  16-bit), `0x14` XAS1 (EA ADPCM, the BF3 default), `0x16` EALayer3 (MP3-family → Zench `ealayer3.exe`),
  `0x19` Speex (→ `easpeex.dll`).
- The container is the `SoundWaveAsset` ebx class: `$::SoundDataAsset/Chunks::array` (`ChunkId` 16 B,
  `ChunkSize`), `Segments::array` (`SamplesOffset`, `SeekTableOffset`, `SegmentLength`), and
  `RuntimeVariations::array` (`ChunkIndex`, `FirstSegmentIndex`, `SegmentCount`).
- Output naming is `ebxname + ChunkIndex + Variation.Index + segment index`. Console builds may permute
  chunk ids as `[3,2,1,0,5,4,7,6,8..15]`.

## Build steps

1. Extract the dumper; keep `bf4_dump/` and `fb3decoder/` side by side.
2. Point the tool at the game's `Data/` folder (the hardcoded `bf4Directory`) — read the scripts and adjust
   the top-level path rather than editing constants deep in the parser.
3. `readCat` the `.cat` to enumerate `(sha1, cas file, offset, size)`; carve `.cas` blobs to `ebx`/`res`
   payloads.
4. For `.sb` bundles, parse the header → sha1/ebx/res/chunk tables, then `seekLZ77Block` each stored block
   and decompress compressed ones.
5. Run `ebxtotext.py` over the ebx set to get readable `.txt` and a GUID→name map.
6. For audio, slice chunks by the `SoundWaveAsset` arrays and dispatch by `audioType` to PCM / XAS1 /
   EALayer3 / Speex decoders.

## Verification

- The header magic and counts were checked against sample bundles and are self-consistent (BF4 bundle magic
  `0x9D798ED5` vs BF3 `0x970d1c13`).
- Level of proof is **format reading**, not a full round-trip: this subagent read the parser sources and
  reasoned about them; it did **not** run the Python 2 dumper against a real install, so the "in-progress" status
  reflects the tool's provenance and internal consistency, not a re-run in this session. Re-run and confirm
  before relying on it.

## Gotchas

1. **Wrong folder name.** The attachment lives under `mirrors_edge/` but the tool is BF4/Frostbite — **Cause:**
   forum poster reused a Mirror's Edge topic. **Fix:** classify by the code's own constants, not the directory.
2. **Nothing parses under `python3`.** **Cause:** Python 2 syntax plus `cPickle`. **Fix:** use `python2.7`
   (or port the handful of 2/3 differences deliberately).
3. **Every field reads 8 bytes off.** **Cause:** 4-byte-aligned ebx instances carry an `obfuscationShift` of 8.
   **Fix:** subtract 8 from field offsets/sizes for those instances.
4. **Garbage bundle contents.** **Cause:** treating a stored block as compressed. **Fix:** dispatch on
   `compressionType`: `0x70`/`0x71`/`0` are stored (skip `decompressedSize`), only `0x970` is compressed.
5. **Encrypted `.toc`/`.cat` noise.** **Cause:** the file has a `0x00D1CE00/01/03` magic. **Fix:** apply the
   `unXor` path (key at offset 296, XOR by 123, then `key[i%257]`) or skip 16/556 bytes for the signature-only
   variants.
6. **Audio decodes to static.** **Cause:** wrong codec dispatch. **Fix:** read the `audioType` byte and route
   `0x14`→XAS1, `0x16`→EALayer3, `0x19`→Speex, `0x12`→big-endian PCM.

## Assets

None — extraction tooling only. No game files, assets, or decoders are redistributed with this note.

## Cost and time

One subagent session (source reading + format reconstruction from the extracted Python).

## Open questions

- Exact `cas.py`/`noncas.py` line numbers were not pinned in this pass; the function names above are the
  traceable anchors (`Entry`, `addField`, `read128`, `unXor`, `readCat`, `Bundle`, `seekLZ77Block`,
  `patchedBundle`).
- Never executed against a live BF4 install here — needs a re-run to claim verified extraction.
- `resType` value table and the BF4 `resTypes` map were not enumerated.
- Whether the same parser covers Battlefield 1/5 (later Frostbite) is untested; the bundle magic almost
  certainly differs.
- EALayer3 output was not decode-tested; the `ealayer3.exe` dependency is Windows/Wine.

See also `techniques/frostbite-bundle-chunk-ebx-and-ealayer3.md` for the general Frostbite
bundle/chunk/EBX + EALayer3 pipeline this note specialises.
