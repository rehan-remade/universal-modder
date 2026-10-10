---
kind: technique
title: "Bethesda ESM/ESP/ESL plugin record format: header, GRUP, record header, FormID slots, STRINGS"
tags: [bethesda, plugin, esm, esp, esl, creation-engine, gamebryo, formid, records, xedit, strings, localization]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - "https://github.com/TES5Edit/TES5Edit"
  - "https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format"
  - "https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/TES4"
  - "https://tes5edit.github.io/fopdoc/Fallout4/Records.html"
---

# Bethesda ESM/ESP/ESL plugin record format: header, GRUP, record header, FormID slots, STRINGS

> Bethesda game data (Morrowind through Starfield) lives in plugin files — `.esm` master, `.esp`
> plugin, `.esl` light master — built from the same container: a version-dependent record header
> (24 bytes from FO3 onward, 20 on Oblivion, 16 on Morrowind), a tree
> of GRUP groups, and main records whose headers carry a FormID, flags and version. This note records
> the concrete layout xEdit/TES5Edit implements: the record and group structures, the TES4 header
> subrecords, the FormID full/light/medium slot algebra, the `XXXX` oversized-subrecord escape, and
> how localized plugins move strings out to sibling `.STRINGS` files.

## When to use it

- Writing a tool that reads or writes a plugin without xEdit (a FormID rewriter, a merge tool, a
  corpus parser, a synthetic-ESL generator).
- Debugging FormID addressing: "my record resolves to the wrong master", "the light module won't
  save", "strings show as garbled IDs".
- Understanding what a `.esl` actually is before you create one.

If you only need to browse/edit an existing plugin, use xEdit (see below) — this note is for
implementing or reasoning about the format itself.

## How

### Container model

A plugin is a flat stream of **main records** and **GRUP** group records. Groups nest: a group can
contain records and further groups. There is no global table of contents; readers walk the stream
and accumulate group context to reconstruct the tree.

### Main record header (24 bytes from FO3 onward; 20 on Oblivion, 16 on Morrowind)

```
offset  size  field
0       4     signature (4 ASCII chars, big-endian comparison, e.g. 'TES4', 'WEAP')
4       4     dataSize (U32) — payload length that follows the header
8       4     record flags (U32)
12      4     FormID (U32)
16      4     version control info 1 (U32) — timestamp/date on pre-FO4
20      2     form version (U16)  [pre-FO4: this is the low half of VCS1]
22      2     version control info 2 (U16)
24      ...   subrecord payload (dataSize bytes)
```

The header grew over time. **Morrowind (TES3)** records are 16 bytes — `signature(4) + dataSize(4) +
unknown(4) + flags(4)` — and have **no FormID at all** (the record type is the identity). **Oblivion
(TES4)** adds a FormID and a single VCS1, giving 20 bytes, but still has no form version. **FO3 and
later** add the form version and VCS2 for 24 bytes. xEdit models the header as a union switched on
game version (see `TwbMainRecordStruct`, TES5Edit/Core/wbImplementation.pas:1072-1094).

Inside the payload, **subrecords** are `signature(4) + size(U16) + data(size)`, concatenated. A
subrecord signature such as `XXXX` is not data — it is an escape (see below).

### GRUP group record

```
offset  size  field
0       4     signature 'GRUP' (U32)
4       4     groupSize (U32) — total size including this 24-byte header
8       4     label (U32) — FormID for child groups, or a 4-char record signature for top-level type groups
12      4     groupType (Int32)
16      4     stamp (U32)
20      4     unknown (U32)
24      ...   contents
```

Modeled as `TwbGroupRecordStruct` (wbImplementation.pas:1888-1895). The `label` is polymorphic:
for a "type" group it is the four signature bytes of the record type; for a "children"/persistent
group it is a parent FormID.

### The plugin header record (signature `TES4`)

Every plugin starts with a `TES4` main record whose subrecords are the file-level metadata. The
common subrecords xEdit defines (TES5Edit/Core/wbDefinitionsCommon.pas:5790-5808 and the game
definition units):

| Subrecord | Meaning |
|---|---|
| `HEDR` | Header: float version, U32 record count, U32 next object ID (`wbHEDR`, wbDefinitionsCommon.pas:6965-6970). Required. |
| `MAST` | Master file name (one per master). An 8-byte `DATA` (master file size) follows each `MAST` since Oblivion. |
| `CNAM` | Author (TES5/FO4); creator string in generated plugins. |
| `SNAM` | Description/summary. |
| `ONAM` | Overridden forms — record types this file overrides in its masters. |
| `INTV` | Interior cell count. |
| `INCC` | Interior cell count (other form). |
| `TNAM` | Transient record types (FO4/SF). |
| `BNAM` | Branch (Starfield). |
| `CHGL` | Change forms (Starfield). |

`HEDR` version is game-specific: TES5 = 1.71, FO4 = 0.95 (or 1.0), Starfield = 0.96
(wbDefinitionsSF1.pas:2854; wbDefinitionsFO4.pas:13726-13728). The record header's own FormID is
usually `0`.

### Record flags (record header offset 8)

Flag semantics are per-game but the spine is stable (TES5 definitions, wbDefinitionsTES5.pas:10458-10486):

```
bit 0  0x00000001  ESM (Master)
bit 1  0x00000002  Altered
bit 3  0x00000008  Active
bit 4  0x00000010  Optimized
bit 5  0x00000020  Temp ID owner
bit 7  0x00000080  Localized   <-- payload strings are LString IDs, not inline text
bit 8  0x00000100  Precalc data only (Skyrim)
bit 9  0x00000200  Light master / Small (ESL)
bit 20 0x00100000  Update (Skyrim/FO4) / Medium etc. on later games
```

Starfield renames/extends: `0x100`=Small, `0x200`=Update, `0x400`=Medium, `0x800`=Blueprint
(wbDefinitionsSF1.pas:15938-15983).

### FormID slots: full / light / medium

A FormID is 32 bits: the **high byte is the file index in the load order**, the low bytes are an
**object ID** within that file. xEdit's `TwbFileID` splits it (TES5Edit/Core/wbInterface.pas:22843-22856):

```
fullSlot   = formID >> 24
lightSlot  = (formID >> 12) & 0xFFF    when fullSlot == 0xFE (LightFullSlot)
mediumSlot = (formID >> 16) & 0xFF     when fullSlot == 0xFD (MediumFullSlot)
```

So:

- **Full module** (`.esm`/`.esp`): FormID = `<fileIndex:8><objectID:24>`, file index `0x00`-`0xFD`
  (`0x00`-`0xFC` on Starfield, where `0xFD` is the medium slot).
- **Light module** (`.esl`, and any ESP tagged ESL): FormID = `0xFE<lightSlot:12><objectID:12>`.
  The object ID gets only the **low 12 bits** — `0x800`-`0xFFF` is the range Bethesda normally
  allocates for new records, but any 12-bit value is addressable.
- **Medium module** (Starfield `0xFD`): FormID = `0xFD<mediumSlot:8><objectID:16>`.

Slot ceilings: `MaxLightSlot = 0xFFF` (4096 light modules), `MaxMediumSlot = 0xFF` (256 medium),
`MaxFullSlot = 0xFE`, decremented to `0xFD` when light is supported and to `0xFC` when light+medium
are both supported (wbInterface.pas:22930-22954). Exceeding a ceiling raises the xEdit errors
"Too many light/medium/full modules" (wbImplementation.pas:3286-3300).

**Light-module object-ID validation** (wbImplementation.pas:2430-2449): a record whose FormID has
any bit set in `$00FFF000` (i.e. object ID above 12 bits) cannot be saved in a light module. xEdit
emits the literal message `<record> has invalid ObjectID <hex> for a light module. You will not be
able to save this file with the Light flag active.` The medium-module variant tests `$00FF0000`.

Practical consequence: to convert an ESP to ESL you must **compact object IDs into the low 12 bits**
(0x800-0xFFF for new records, plus remap existing ones), not just add the ESL flag.

### `<name>.STRINGS` localization

When the file header has the Localized flag (`0x80`), string subrecords store a **U32 string ID**
instead of inline text. The text lives in three sibling files next to the plugin:

| Extension | Type | String encoding |
|---|---|---|
| `.STRINGS` | plain strings | null-terminated |
| `.ILSTRINGS` | indexed strings | length-prefixed |
| `.DLSTRINGS` | delimited strings | length-prefixed |

Format (TwbLocalizationFile.ReadDirectory, TES5Edit/Core/wbLocalization.pas:330-357):

```
offset  size  field
0       4     stringCount (U32)
4       4     dataSize (U32) — skipped on read
8       8*N   directory: N × (stringID:U32, offset:U32)     N = stringCount
8+8*N   ...   string data; a directory 'offset' is relative to this point
```

So the absolute position of a string is `8 + 8*N + offset`. Null-terminated for `.STRINGS`,
length-prefixed for the `I`/`D` variants. xEdit resolves a subrecord's string ID against the
localization file matching the requested language.

### Oversized subrecords: `XXXX`

Subrecord size is a U16, so a payload over 64 KiB cannot be expressed directly. The escape is a
`XXXX` subrecord (wbImplementation.pas:15991, :16136, :16458):

```
'XXXX'  size=4  <realSize:U32>
then the following subrecord's normal header (signature + size), with its size field = 0,
then the realSize-byte payload
```

A reader that does not special-case `XXXX` sees a zero-size subrecord and desyncs; the following
subrecord's normal header still has to be read (with its size ignored) before the payload.

## Gotchas

1. **Record tree comes out wrong / desyncs after a big subrecord.** **Symptom:** every record after
   one large one parses as garbage. **Cause:** `XXXX` override not handled; the following subrecord
   was read as zero-length and its payload was not consumed. **Fix:** detect `XXXX`, read the U32
   real size, then read the following subrecord's normal header (its size field is 0) and consume
   that many bytes.
2. **Object IDs "too large for light module".** **Symptom:** xEdit refuses to save a flagged ESL.
   **Cause:** object ID has bits above bit 11; `formID & $00FFF000 != 0`. **Fix:** renumber the
   records' object IDs into the 12-bit range (Bethesda's 0x800-0xFFF convention) before flagging
   light.
3. **Strings show as numbers / garbled.** **Symptom:** localized names read as integer IDs.
   **Cause:** Localized flag set, so the payload really is an ID; the `.STRINGS`/`.ILSTRINGS`/
   `.DLSTRINGS` file is missing or the wrong language. **Fix:** supply the matching STRINGS file
   next to the plugin; offset is relative to `8 + 8*count`, not to file start.
4. **Masters resolve to the wrong file.** **Symptom:** a FormID loads a different object than
   expected after load-order changes. **Cause:** full FormIDs store the load-order file index, so
   the same FormID is only meaningful under one master ordering; ESL/medium slots are `0xFE`/`0xFD`
   pseudo-indices. **Fix:** resolve by master list (`MAST` order), and when adding/removing masters,
   rewrite FormIDs through the master remap (xEdit's `FixupFormID`).
5. **Adding the ESL bit alone truncates records.** **Symptom:** a working ESP becomes broken after
   being tagged ESL. **Cause:** the ESL flag changes the FormID encoding to a 12-bit object ID, so
   any object ID above 0xFFF collides. **Fix:** compact/renumber before flagging; verify with the
   object-ID validation above.

## Seen in

- xEdit / TES5Edit `Core/` — `wbImplementation.pas`, `wbInterface.pas`, `wbDefinitions*.pas`,
  `wbLocalization.pas`, `wbLoadOrder.pas`.
- Game modes exposed by the same codebase: `TES4Edit`, `TES5Edit`, `SSEEdit`, `FO3Edit`, `FNVEdit`,
  `FO4Edit`, `FO76Edit`, `SF16Edit`, plus Enderal and VR variants (TES5Edit/README.md:109-123).
- FO4 CC-Packer's synthetic `TES4` placeholder (see the companion note on ESL/archive pairing; the
  file's `_create_vanilla_esl` writes exactly this header/subrecord layout).

## Open questions

- Exact bit assignments for the medium/blueprint flags are read from xEdit's Starfield definition
  only; not independently confirmed against a Starfield binary.
- Version control info 1 semantics differ pre/post-FO4 (`wbFormVersionDecider(44)` switch). Not
  traced to the exact game-version boundary (FO4 1.10.162?) — unverified.
- Whether the engine, not just xEdit, enforces the 12-bit light object-ID range or merely the
  `0x800-0xFFF` convention (xEdit's error implies it does). Not confirmed in-game.
- `ONAM`/`TNAM`/`BNAM`/`CHGL` semantics are transcribed from the definitions, not from a runtime
  trace.
- Plugin header record is assumed at offset 0 always; not verified for all formats (e.g. embedded
  header in some console builds).
