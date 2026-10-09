---
kind: game
title: "EA Black Box AEMS sound banks: the .abk container and .bnk sample banks (ABKTool + SX.EXE)"
game: "Need for Speed: Most Wanted (2005)"
games_also: ["Need for Speed: Carbon", "Need for Speed: ProStreet", "Need for Speed: Undercover"]
game_version: "Black Box-era AEMS audio (ABK header reports Aimex 1.1.1; sample is CAR_66_M3GTR)"
platform: windows
engine: unknown
route: data
tools: ["ABKTool.exe (xan1242's EA Black Box AEMS Bank tool)", "SX.EXE (EA wave extractor, shipped alongside ABKTool; not linked here)", "Wine (wine-staging) for the Windows binaries"]
anti_cheat: "none — offline audio extraction"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links: []
tags: [nfs, most-wanted, aems, abk, bnk, audio, soundbank, ea-black-box, x86, wine, reverse-engineering]
---

# EA Black Box AEMS sound banks: the .abk container and .bnk sample banks (ABKTool + SX.EXE)

> AEMS is EA Black Box's audio system; a `.abk` is the top-level bank that points at a `.bnk` sample
> bank (plus SFX/MIDI banks), and `ABKTool.exe` parses the header and shells out to EA's `SX.EXE` to dump
> the samples as WAV. These notes reconstruct the container layout from the tool's PDB symbols, its
> embedded format strings and hexdumps of a real sample pair. Status **in-progress** for
> reading/extraction via the shipped tool; the byte-exact field order is only partly confirmed.

## Setup

- Everything ran under **Wine (`wine-staging`)** on Linux; the tool is a 32-bit MSVC 2015 console app
  (PDB records `/m Machine:X86`, built from `E:\MyNFSCode\ABKTool\ABKTool\ABKTool.cpp`).
- `ABKTool` is **xan1242's** tool. It bundles EA's `SX.EXE`, so it is credited here in plain text and
  intentionally **not linked**.
- Files used from an unpublished local copy of the tool set:
  `ABKTool.exe` (13 KB), `ABKTool.pdb` (503 KB, symbols),
  `SX.EXE` (577 KB, EA's wave dumper) and the sample pair `CAR_66_M3GTR.abk` (147 665 B) /
  `CAR_66_M3GTR.bnk` (136 825 B).
- A pre-extracted `CAR_66_M3GTR/` folder with eight `.wav` files is the expected output shape.

## Route and why

**Data** route. The bank is a container; the samples inside are ordinary PCM. There is nothing to hook and
no reason to run the game — the tool plus its PDB already name every field. The alternative of hooking the
engine's sound loader was rejected as unnecessary and as touching a retail game process.

## How the game works (what we had to learn)

### Naming (from `ABKTool.pdb` symbols)

- Tool title string: `EA Black Box AEMS Bank tool`.
- Functions: `ParseAemsBank@@YAHPBD@Z`, `ExtractBNK@@YAHPBD@Z`, `ExtractSFXBank`, `GetBNKNumElements@@YAFPBD@Z`,
  `GeneratedBnkOutName`.
- Types: `AemsDef_ModuleBank`, `AemsDef_Snd10SampleBankHeader`, `AemsDef_TWEAKHEADER`, `enum AemsPlatform`,
  `PlatformStrings`.

### `.abk` header (per ABKTool's `AemsDef_ModuleBank`)

Field order from ABKTool's struct: `ID` (`%c%c%c%c`), Aimex Version (`%hhd %hhd.%hhd patch: %hhd`),
`Platform`, Target type, Num. modules (`%hd`), Debug CRC, Unique ID, Total size, Resident size, Module
offset, SFX bank offset, SFX bank size padded, MIDI bank offset, MIDI bank size padded, Func Fixup offset,
Static data Fixup offset, Interface offset. Struct fields include `nummodules`, `moduleoffset`,
`sfxbankoffset`, `sfxbanksizepadded`, `midibankoffset`, `midibanksizepadded`, `funcfixupoffset`,
`staticdatafixupoffset`, `interfaceOffset`, `residentsize`, `debugcrc`, `platform`, `target`/`targetType`,
`rva_target`, `DataOffset`, `streamfileoffset`, `cdOffset`, `InBank` (`AemsDef_ModuleBank`),
`pSnd10SampleBankHeader`, `ptweakheader`.

Header field offsets:

| Offset | Field |
|--------|-------|
| `0x00` | magic **`ABKC`** |
| `0x04` | Aimex version (`01 01 01 00` = 1.1.1 + patch 0) |
| `0x08` | platform |
| `0x09` | target type |
| `0x0A` | `u16` module count |
| `0x0C` | debug CRC |
| `0x10` | unique ID |
| `0x14` | total size |
| `0x18` | resident size |
| `0x1C` | module offset |
| `0x20` | SFX bank offset |
| `0x24` | SFX bank size |

Observed dwords in `CAR_66_M3GTR.abk`: `0x14` → `0x000240D1` (147,665, total size; equals the file
length), `0x20` → `0x00002680` (9,856, SFX bank offset) and `0x24` → `0x00021679` (136,825, SFX bank
size; equals the `.bnk` length, whose own header repeats it as a `u32` at `0x08`). The field labels
follow ABKTool's struct; the remaining dword-to-field mapping was not re-validated byte-for-byte.

### `.bnk` sample bank

Per ABKTool and vgmstream the header is: magic (4 bytes), `0x04` version, `0x06` `u16` sound slots,
`0x08` `u32` size, `0x14` per-sound offsets.

`CAR_66_M3GTR.bnk` begins:

| Offset | Bytes | Reading |
|--------|-------|---------|
| `0x00` | `42 4E 4B 6C` | magic **`BNKl`** (`l` = little-endian; `BNKb` is the big-endian variant) |
| `0x04` | `05 00` | `u16` version = 5 |
| `0x06` | `09 00` | `u16` sound slots = 9 |
| `0x08` | `79 16 02 00` | `u32` = 136 825 = file length |
| `0x14` | — | per-sound offset table (observed `u32` values `0x20, 0x50, 0x80, 0xB0, 0xE0, 0x110, 0x140, 0x170`, 0x30 apart) |
| `0x38` | `50 54 00 00` | `PT` sample marker |

`GetBNKNumElements` reads the element count; the tool errors with
`File should start with BNKx but this one starts with %c%c%c%c` on a bad magic.

### Extraction pipeline

`ABKTool` does not decode samples itself — it calls EA's `SX.EXE`:

```
sx.exe -wave "<in>" -="<out>" -onetomany
```

then renames `%s.%hd` → `%s\%s_%hd.wav`. On an unsupported codec it prints
`File %s cannot be extracted by SX due to an incompatible format!`. `SX.EXE` itself contains the same AEMS
strings (Aimex Version, Platform, Num. modules, SFX/MIDI bank offsets, Func/Static Fixup offsets), so it is
the real bank reader and ABKTool is the front end.

Dumped samples are **PCM 16-bit mono 32 000 Hz**, with a `smpl` loop chunk — consistent with looping engine
sounds. The eight `CAR_66_M3GTR` WAVs are engine-sound variations.

## Build steps

1. Under Wine, place `ABKTool.exe`, `SX.EXE` and the `.abk`/`.bnk` pair in one folder.
2. `wine ABKTool.exe <bank.abk>` (or the BNK extract entry point) — it locates the accompanying `.bnk`.
3. It shells `SX.EXE -wave ... -onetomany`, then renames the numbered outputs into `\wav_NNN.wav` files.
4. Inspect the WAVs (they are plain PCM with a loop chunk).

## Verification

- Magic bytes and the observed `0x14`/`0x20`/`0x24` dwords (`0x000240D1`, `0x00002680`, `0x00021679`)
  were read directly from the sample files with `xxd` (and the two sizes cross-check against the file
  lengths), so those **are** confirmed; their field labels follow ABKTool's struct.
- The field *order* comes from the tool's own `printf` strings and PDB field names, which is strong but not
  byte-proven.
- No WAV was re-generated in this session — the pre-extracted `CAR_66_M3GTR/` output was not re-run.

## Gotchas

1. **Tool exits without samples.** **Cause:** `SX.EXE` is missing or not next to the tool. **Fix:** keep both
   binaries in the same directory; ABKTool forks SX by bare name.
2. **"incompatible format" from SX.** **Cause:** sample codec SX can't decode (non-PCM variants). **Fix:**
   that bank's samples need a different decoder; the tool is not a general codec.
3. **Off-by-a-field reads of the header.** **Cause:** assuming the struct order from the string list is exact.
   **Fix:** validate against the confirmed anchors (`ABKC` magic, file-size word, SFX offset) before trusting
   neighbouring fields.
4. **`BNKl` vs `BNKb`.** **Cause:** the trailing magic byte encodes endianness (`l` = little-endian,
   `b` = big-endian), not a bank subtype. **Fix:** branch on it rather than hardcoding `l`.

## Assets

None — this note documents a container format and the official tool. No audio or game files are included.

## Cost and time

One subagent session (PDB symbol dump, `strings` on both EXEs, hexdumps of the sample pair).

## Open questions

- Field labels in the `.abk`/`.bnk` headers follow ABKTool's and vgmstream's structs; the sample's
  dword-to-field mapping was not re-validated byte-for-byte.
- Whether the `.bnk` `u32` table at `0x14` is strictly a per-sound offset table.
- Which AEMS codecs, beyond PCM, the samples use, and whether SX supports them.
- Which games ship `ABKC` v1.1.1 (`CAR_66_M3GTR` names a BMW M3 GTR, the NFS Most Wanted 2005 hero car, but
  the exact title build was not confirmed from the files).
- `AemsDef_TWEAKHEADER` / `pSnd10SampleBankHeader` layout is named but not decoded.
