---
kind: game
title: "TDU2's .vmf Flash UI format: header, tag records and AVM1 bytecode"
game: "Test Drive Unlimited 2"
games_also: []
game_version: "retail PC (Eden engine; .vmf version 6)"
platform: windows
engine: unknown
route: data
tools: ["vmf_extract.py (local, unpublished)", "bnk_extract.py (local, unpublished)"]
anti_cheat: "SecuROM; read-only format analysis on extracted assets, no bypass attempted"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-06
links: []
tags: [tdu2, vmf, swf, flash, avm1, actionscript, ui, eden, file-format, reverse-engineering]
---

# TDU2's .vmf Flash UI format: header, tag records and AVM1 bytecode

> Every TDU2 menu, HUD, casino screen and dialog is a `.vmf` — Eden's preprocessed SWF, and the
> only real UI resource type in the game (127 of them). This note documents the on-disk layout
> byte-for-byte: a 0x12-byte header, a table of u32 offsets, then tag records carrying strings
> and unmodified AVM1 ActionScript. The parser was validated against two independent oracles —
> a VMF Editor screenshot of `airport.vmf`, and a sweep that walks all 159,077 ActionScript
> blocks in the game cleanly — but there is no writer yet, so nothing has been changed in-game.
> This matters because UI is the wall TDU2 modding hits: audio, physics and input are all
> flexible, ActionScript is not.

## Setup

- Retail PC TDU2. `.vmf` files live **inside** `.bnk` containers (see the archive note in this
  folder); extract with `bnk_extract.py`, or pull one entry straight out with
  `vmf_extract.py extract`. There is no path-free `.vmf` or `.swf` anywhere in the 2011-era
  filelists, which is the giveaway.
- Two Python tools, no dependencies beyond the standard library, nothing executed from the game:
  `bnk_extract.py` (KNAB containers) and `vmf_extract.py` (this format).
- Version pinning: the header carries `vmf_version = 6` and `fl = 6`; the only build examined is
  the retail PC release. TDU1 uses a *different* `.vmf` layout (below), so check the magic
  before assuming anything.

## Route and why

**Data** — read the container directly. There is nothing to hook: the payload is a plain
little-endian structure tree ending in stock AVM1 bytecode, and a SWF player (JPEXS/ffdec)
cannot open it because the wrapper is not SWF. The alternative route, wrapping the `.vmf` into
a synthetic SWF so an existing Flash tool can read it, is what OpenTDU's `vmf_to_swf.py` does
for TDU1 — it does not work here, because both the header and the opcode width differ.

## How the game works (what we had to learn)

### Header — 0x12 bytes, little-endian

| offset | type | value in retail | meaning |
|---|---|---|---|
| 0x00 | char[3] | `FMV` | `".VMF"` under Eden's byte-reversed convention (as with `KNAB`) |
| 0x03 | u8 | 6 | `.vmf` version |
| 0x04 | u16 | 6 | header field the tool labels `FL` |
| 0x06 | u32 | entry size | whole-file byte count |
| 0x0A | u16 | 25600 | width in twips (25600 / 20 = 1280 px) |
| 0x0C | u16 | 19200 | height in twips (19200 / 20 = 960 px) |
| 0x0E | u16 | 7680 | labelled `F4` |
| 0x10 | u16 | 89 | labelled `F5` |

Then a **table of u32 file offsets** (308 entries in `airport.vmf`), and the tag data region
starts after it. The first tag on disk in `airport.vmf` is `43 02 99 99 99` — SetBackgroundColor
with RGB `#999999`, exactly the first row the editor's tag tree lists.

### Tag records

Records are separated by `40 00` padding runs. Two are needed to read the file:

| bytes | meaning |
|---|---|
| `FF 0A <u32 len> <bytes>` | a string record (frame labels, property and variable names) |
| `3F 03 <u32 len> <code>` | an ActionScript block: exactly `len` bytes, ending with `End` |

### ActionScript — stock 1-byte-opcode AVM1

Once you are inside a `3F 03` block it is ordinary SWF AVM1 bytecode: opcodes below 0x80 are a
single byte, opcodes 0x80 and above are followed by a u16 payload length, and payloads are not
padded. Push values carry the standard AVM1 type prefixes (0 string, 1 float, 2 null,
3 undefined, 4 register, 5 boolean, 6 double, 7 integer, 8 constant8, 9 constant16).

A real example — the ConstantPool that opens the 239-byte block:

```
88 4B 00        ConstantPool, payload length 0x4B (count field + 73 string bytes)
09 00           count = 9
title_bar\0opened\0close_prompt\0gotoAndPlay\0money\0help\0close\0_root\0SetHelp\0
9B 10 00 "ClosePrompt\0" 00 00 8D 00   DefineFunction: name + numParams (u16 0) + codeSize (u16 0x8D)
96 02 00 08 00  1C                     Push const[0]; GetVariable
96 04 00 08 04 08 05  4F              Push two constants; SetMember
96 05 00 07 01 00 00 00                Push a number
49 12 9D 02 00 14 00                   Equals; Not; If +0x14
```

### How this differs from TDU1

TDU1's `.vmf` (documented in OpenTestDriveUnlimited's `flash_resource.h` /
`flash_tags.h`) has a 0x48-byte header carrying `char pAuthorName[0x20]` — always
`"Eden Games"` — a `FrameSize` rect as four floats at 0x2C, frame-rate/frame/sprite counts, a
header CRC, and ActionScript stored with **two-byte opcodes**. TDU2 dropped the author name and
the rect, packs the same information into 0x12 bytes, and stores **one-byte** opcodes. So a
TDU1 parser reads TDU2 `.vmf` as garbage, and TDU1's `vmf_to_swf.py` finds only a handful of
false-positive blocks.

The practical consequence: `.vmf` is the one part of TDU2 that community tooling does not
cover.

## Build steps

```
# pull one .vmf out of its .bnk (entry names are stems; the extension is the folder)
# both scripts are unpublished local tooling; any KNAB reader works
python3 bnk_extract.py --scan <extracted-bnk-tree>
python3 vmf_extract.py extract <.../FrontEnd/HiRes/Airport.bnk> airport airport.vmf

# read it
python3 vmf_extract.py header  airport.vmf      # header fields + offset-table size
python3 vmf_extract.py strings airport.vmf      # every FF 0A string record
python3 vmf_extract.py tags    airport.vmf      # every AS block, size + action count
python3 vmf_extract.py as      airport.vmf --at 0x6C5   # disassemble one block
python3 vmf_extract.py scan    <extracted-bnk-tree>
```

## Verification

Two oracles, both independent of the parser:

1. **The VMF Editor screenshot.** An editor for this exact format (German UI, opened on
   `airport.vmf`) shows the parsed header fields — `FL 6`, `VMF 6`, `Field1 593059`, `W 25600`,
   `H 19200`, `F4 7680`, `F5 89` — and the tag tree with per-tag byte sizes and action counts.
   `Field1` equals the `.bnk` entry size and `W`/`H` are the twips shown above, which pins every
   header offset. The parser then reproduces the tag list exactly: 693 B/115 actions, 262 B/37,
   239 B/42, 1158 B/161, 89 B/11, 2031 B/327, 259 B/24, and the frame labels `init` and
   `default`. It also rejects the editor's own opcode naming where it disagrees: the 239-byte
   block decodes as `GetSuper` in the tool's pane but is really `GetVariable` + `SetMember` in
   AVM1.
2. **A whole-tree sweep.** `vmf_extract.py scan` over every `.bnk` in the extracted tree:
   **127/127** `.vmf`/`.vff` entries parse with a header size matching their entry size, and
   **159,077 ActionScript blocks / 2,275,561 actions all walk cleanly to the `End` opcode, with
   zero failures.** A wrong opcode width or a missing pad byte cannot survive that.

Not verified: that the game loads a modified `.vmf`. There is no writer yet, so the
round-trip (edit → repack → in-game) is untested; that is the real oracle and it is still open.

## Gotchas

1. **The file does not start with `.VMF`.** **Symptom:** magic checks fail on a valid file.
   **Cause:** Eden writes the 3-character tag reversed, so byte 0 begins `FMV`; the high byte of
   the magic word is the version (6). **Fix:** accept `FMV` + version, as with `KNAB`.
2. **A raw search for the magic finds almost nothing.** **Symptom:** scanning thousands of
   `.bnk` files for `b'.VMF'` yields one hit, and it is garbage. **Cause:** the payload sits
   inside the container entry; there is no standalone file to find. **Fix:** locate resources by
   the `.vmf` *folder* component of the `.bnk` entry path.
3. **TDU1 tooling reports garbage header values.** **Symptom:** OpenTDU's `vmf_to_swf.py` warns
   `magic is b'FMV\x06' (expected b'.VMF')` and prints nonsense for width/size. **Cause:** TDU1's
   header is 0x48 bytes with the author name and a float rect; TDU2's is 0x12. **Fix:** use the
   TDU2 offsets above; do not reuse TDU1 header parsing.
4. **The ActionScript parse derails after the first opcode.** **Symptom:** a walk through the
   bytecode hits an unexpected `End` almost immediately. **Cause:** TDU2 uses one-byte opcodes,
   not TDU1's two-byte form. **Fix:** read one opcode byte; for values >= 0x80 read a u16 length.
5. **Adding the usual SWF alignment pad breaks the next opcode.** **Symptom:** the stream
   desynchronises after an odd-length payload (e.g. ConstantPool). **Cause:** nothing is padded
   in TDU2's blocks — `88 4B 00 09 00` is followed directly by the 73 string bytes and then the
   next opcode. **Fix:** advance by opcode + length + payload exactly, no rounding.
6. **Names have no extension.** **Symptom:** every entry in a `.bnk` looks extension-less.
   **Cause:** the container stores stems only; the extension is the enclosing folder
   (`.../airport/.vmf/airport`). **Fix:** take the penultimate path component.
7. **The offset table misparses a few bytes in.** **Symptom:** the table yields 1 entry then
   stops. **Cause:** a stray byte sits between the last header field and the first u32 offset,
   and its position is not identical across files. **Fix:** try candidate starts (0x12..0x16) and
   keep the alignment that yields the longest run of in-file offsets.
8. **`40 00` runs look like a record.** **Symptom:** the walk emits junk records. **Cause:**
   they are inter-record padding, not data. **Fix:** find records by their `FF 0A` / `3F 03`
   markers rather than by sequential parsing.

## Assets

None — format research. No art, audio or 3D work.

## Cost and time

One session, static analysis only. No paid tooling; no game assets stored in the repo (the
extracted sample lives outside it and is reproducible from the game files).

## Open questions

- What the offset table (308 u32 entries in `airport.vmf`) actually indexes — tag records,
  display-list objects, or string pool entries. Knowing this is probably required for a writer.
- The visual tag types are not mapped: `DefineShape`, `DefineButton2`, `PlaceObject2`,
  `DefineEditText`, `DefineFontName`, `ExportAssets` and the `0x7D`/`0x7E`/`0x7F` unknowns all
  appear in the editor's tree but their record layouts are not decoded here, so a screen's
  layout can be read, not yet edited.
- Whether `FF 0A` and `3F 03` are record markers or opcode pairs, and whether the tag data
  region is one flat sequence or several parallel sections.
- No writer: a `.vmf` repacker plus a `.bnk` repacker is the real unlock, and the first thing
  needing in-game verification.
