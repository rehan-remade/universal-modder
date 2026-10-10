---
kind: technique
title: "Wwise SoundBank (BNK): chunk layout, HIRC objects, and the per-version .wschema"
tags: [wwise, bnk, hirc, wem, wschema, soundbank, watch-dogs, wd3, fusiontools, kaitai, varint]
date: 2026-10-05
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - "https://github.com/WolvenKit/wwise-audio-tools"
  - "https://github.com/hpxro7/wwiseutil"
  - "https://github.com/audiokinetic/WwiseIncludes"
---

# Wwise SoundBank (BNK): chunk layout, HIRC objects, and the per-version .wschema

> A Wwise `.bnk` is two problems stacked: a simple chunk container (`BKHD`/`DIDX`/`DATA`/
> `HIRC`) and a `HIRC` section whose per-object field layout changes with the bank version.
> Generic parsers (Kaitai/`wwiseutil`) get the container right but overrun on the HIRC
> objects; the authoritative object layouts live in FusionTools `.wschema` files — one
> self-describing schema per bank version (`v34`…`v150`). This note records the container
> shape, the HIRC framing, and how the `.wschema` schema resolves the Kaitai overrun. For the
> authoring-version → bank-version mapping (e.g. `v132` = Wwise 2019.2.15, the Watch Dogs: Legion
> match) and the open toolchain, see the companion note
> `techniques/wwise-soundbank-versions-and-open-toolchain.md`.

## When to use it

- You are reading or replacing audio inside a Wwise `.bnk`/`.nbnk` (media = WEMs) or a
  `.pck`/`.npck` package.
- A version-generic parser throws while walking `HIRC` on real banks (many objects), but
  works on tiny hand-made fixtures — the Kaitai overrun below.
- You need the *object* layout (loop points, effects, child/parent links, wem references),
  not just the media payload — this is the `HIRC` problem, and its layout is
  version-specific.
- You are converting WEM↔WAV/OGG and need to know what the container and the `HIRC`
  stream source say about codec/plugin.

## How

### 1. Container: a flat sequence of framed chunks

A BNK is `magic[4] + u32 length + body`, repeated. Recognised magics (little-endian u32):
`BKHD`, `DIDX`, `DATA`, `HIRC`, `STID`; anything else is preserved as an unknown chunk.
Sections written in the order `BKHD`, `DIDX`+`DATA`, `HIRC`, `STID`, unknowns.

- **`BKHD`** — the version gate. Body: `version u32`, `id u32`, `language i32`,
  `feedback i32`, then `projectID u32` **only if `version > 76`**, then padding ints.
  Everything downstream is keyed off `version`.
- **`DIDX`** — the media index: `length/12` entries of `{ wemID u32, offset u32, length u32 }`.
  `offset` is relative to the start of the `DATA` body. In BNK the WEMs are packed with
  **16-byte alignment**; PCK has **no** alignment.
- **`DATA`** — the raw WEM bytes, laid out physically; `DIDX` offsets point into it.
- **`HIRC`** — object hierarchy. Body: `u32 object count`, then objects (below).
- **`STID`** — optional string-ID table.

The `length` field after each magic is the body length, **excluding** the 8-byte
magic+length header. `HIRC`'s length covers `count(4) + all objects`.

### 2. HIRC object framing

Each object is `type + u32 length + body[length]`:

```
type    u8    object type ID          (u32, not u8, when BKHD.version <= 48)
length  u32   length of body
body    ...   object ID (u32) followed by type-specific fields
```

The **`length` includes the 4-byte object ID**, and the object body's first field is that
ID. The field layout after the ID depends on `type` **and** on `BKHD.version`. The type
IDs are `0x02` Sound, `0x03` Action, `0x04` Event, `0x05` Random/Sequence container,
`0x07` Actor-Mixer, `0x0A` Music Segment; the full map is in each `.wschema`'s type-id table.

### 3. HIRC object serialization is schema-driven (`.wschema`)

The object field list is not fixed across versions, so the authoring tools emit a schema per
version. FusionTools `.wschema` is a self-describing binary (`WSCH`) that lists, for one
Wwise version, every object type, its field layout, enums, and the paths that mark
child-object and WEM references.

`WSCH` layout (all little-endian):

```
"WSCH" u8[4]
schema_version u16
wwise_version  u32
string_table   u32 count, count*(u16 len + utf8)
enum_table     u16 count, each: u16 nameIdx + u16 n + n*(i32 key + u16 valIdx)
typeid_map     u16 count, each: u8 typeId + u16 nameIdx
struct_table   u16 count, each: u16 nameIdx + u16 n + n*FieldDef
object_table   u16 count, each: u16 nameIdx + u8 typeId + u16 n + n*FieldDef
                               + u8 nChild + nChild*u16
                               + u8 nWem   + nWem*u16
```

A `FieldDef` starts with a flags byte (`1` has-name, `2` has-condition, `4` has-semantic,
`8` write-skip), then `u16 name` if named, then the type byte, then a type-specific payload.
The field types and their payloads:

- Scalars: `U8/U16/U32/S8/S16/S32/F32/F64`, `Bool`, `Bool255` (0/255), `Var` (7-bit **big-endian**
  varint), `LenString` (i32 length + bytes), `NullString` (UTF-8 + NUL).
- `Struct` — `u16` name of a nested struct definition.
- `List` — one byte selects the count mode: `0xFF` fixed count (`u16`), `0xFE`
  count-from-field (`u16` field name + `u16` divisor), otherwise an integer `FieldType` used
  as the count type; then the recursive element `FieldDef`.
- `Bitfield` — a storage type, then `u8 n` × `{ name, bit_position, bit_count }`; bits are
  packed into one integer.
- `PropList` — count type + property-type type + property-value type; serialised as a type
  array followed by a value array.
- `ConditionalBlock` — a `ConditionDef` then `u16 n` sub-fields, present only if the
  condition holds (evaluated against fields already parsed and the bank owner).
- `Seek` (i16 skip), `Remaining` (every byte to end of the object), `Switch` (dispatch on
  another field's value to a named struct).

`ConditionDef` = `field_ref u8 + field_name u16 + op u8 + value_type u8` then a value
(`Bool`, `Int`, or `IntList`). The `object_table` also carries `child_object_fields` and
`wem_fields` — dot-paths used to collect referenced child object IDs and WEM IDs from a
parsed object.

Reading a HIRC object with a schema is therefore: read `type`+`length`, copy the body, look
up the type→name map, then walk the object's `FieldDef` list (recursing into structs/lists
and honouring conditions), instead of hard-coding a version's struct.

### 4. WEM / WAV

Both are RIFF: `"RIFF"` + `u32 size` + `"WAVE"` + chunks. WEM carries `fmt`, `cue`, `list`,
`data` (and `junk`); WAV carries `fmt`, `data`, `cue`. A Wwise **Vorbis** WEM is *not* a plain
OGG file — the codec setup packet is in the WEM.

- **WEM → OGG** uses `ww2ogg` (vendor Vorbis → OGG) followed by `revorb` (fix headers/
  granule positions). Both are vendored in `wwise-audio-tools`.
- **WAV → WEM** is the unfinished direction. Two viable routes: (a) encode Vorbis into a
  Wwise-compatible stream (FusionTools ships its own Vorbis/PCM encoder), or (b) rewrap an
  existing OGG into the WEM RIFF header (quality-preserving). Either way you must set the
  `HIRC` stream-source **Plugin** value to the Vorbis plugin the game expects — `4` for
  newer games, `262145` for older — or the game will not play it.
- FusionTools codec coverage: decode Vorbis, PCM, PCMA, PTADPCM, OPUS, OPUSWW, IMA;
  encode Vorbis, PCM.

### 5. Where the pieces live

- **Unpublished local work.** The author's C++ merge target (`wwise-audio-tools`, a local
  checkout, not published from this work): Kaitai BNK/WEM parsers (`ksy/`),
  `ww2ogg`/`revorb`, the `.wschema` loader (`include/wwtools/schema.hpp`), and the CLI
  `wwtools schema <vNN.wschema>`.
- **Unpublished local work.** A `wwiseutil` Go checkout kept as a read-only reference
  (format + `ReplaceWems` algorithm), no `go.mod`.
- **Unpublished local work.** The `FusionTools` `.wschema` files (16 of them; `v88` is a
  bundled .NET PE, not a real schema) and the `wschema_dump.py` dumper.
- Local Wwise authoring installs and the WDL version mapping.

## Gotchas

1. **Kaitai overruns on HIRC sections with many objects — the bug the `.wschema` resolves.**
   **Symptom:** the generated `bnk.ksy` parser throws `std::ios_base::failure`
   (`basic_ios::clear: iostream error`) on `complex.bnk`, `0_replaced_with_*.bnk`,
   `loop_infinity.bnk`, while `simple.bnk`/`loop_2.bnk`/`loop_none.bnk` (HIRC ≤ 59 bytes)
   parse fine. The file itself is well-formed. **Cause:** `ksy/bnk.ksy`'s `hirc_obj` reads
   `type`, `length`, `id`, then runs a fixed, version-agnostic `switch-on-type` parse for
   the known types that is **not bounded by `length`**; on a real object whose body is larger
   or differently laid out than the KSY's model, it reads past the object into the next one
   and eventually past EOF. (The KSY's fallback does `random_bytes(length - 4)`, i.e. it
   assumes `length` includes the ID — so the framing is known, but the known-type bodies
   are wrong.) **Fix:** don't rely on the KSY's HIRC path. Parse the per-version layout from
   the `.wschema` (below), or hand-parse `type`/`length`/`id` and step the body by `length`,
   only decoding the object types you actually need. This unblocks loop editing and full
   HIRC object parse.

2. **HIRC object `type` is 4 bytes on old banks, 1 byte on newer ones.**
   **Symptom:** a version-agnostic parser desyncs (garbage `type`, wrong length) on old
   Wwise banks. **Cause:** `object_type` width changed — `u32` for `BKHD.version <= 48`,
   `u8` after. **Fix:** branch the type read on the bank version before reading `length`.

3. **Wwise varints are MSB-first; a Kaitai spec reads them little-endian.**
   **Symptom:** list/parameter counts come out absurdly large or negative.
   **Cause:** Wwise varints are 7-bit **MSB-first** (`AkBankReadHelpers.h`
   `ReadVariableSizeBankData`; FusionTools' `ReadVarInt` shifts left). The KSY's
   `vlq_base128_le` for the Event action count is a **KSY bug**, not a second encoding.
   **Fix:** use the MSB-first form everywhere in the bank; do not special-case the
   header counts as little-endian.

4. **Padding is a per-container invariant, and `alignment = 0` means "don't".**
   **Symptom:** replaced WEMs corrupt following offsets, or a last WEM gets too much
   padding. **Cause:** BNK aligns WEMs to 16 bytes; PCK does not. Naively `endOffset %
   alignment` over-aligns the final WEM when `DATA` has fewer bytes left than a full stride.
   **Fix:** recompute padding only when `alignment != 0`; bound the last WEM's padding by
   `dataLength - (offset + newLength)` clamped to `[0, alignment)`; shift subsequent
   `offset`s by the cumulative size surplus.

5. **`BKHD` layout is version-gated.** **Symptom:** reading `BKHD` shifts by 4 bytes on some
   versions, giving garbage `projectID`/padding. **Cause:** `projectID u32` exists only when
   `version > 76`. **Fix:** read it conditionally on the version you just read.

6. **`DIDX` offsets are DATA-relative and stale after a replace.** **Symptom:** after
   replacing a WEM, other WEMs read as junk. **Cause:** the offsets don't track DATA-section
   shifts. **Fix:** the replace algorithm must re-emit every shifted `DIDX` offset, not just
   the replaced one.

7. **`v88.wschema` is not a schema.** **Symptom:** the loader throws bad magic or blows up on
   one file. **Cause:** `v88.wschema` is a ~1.78 MB bundled .NET PE, not a `WSCH` file (the
   real schemas are ~10 KB). **Fix:** skip `v88`.

8. **WEM filename width is computed, not fixed.** **Symptom:** extracted names collide or
   padding looks wrong. **Cause:** `CanonicalWemName` width is `len(str(wemCount))`, not 4 —
   e.g. `index=0, wemCount=100` → `"001.wem"`. **Fix:** derive width from the WEM count; the
   Go `util/util.go` is the reference (an older spec example was wrong).

9. **"A WEM plays silently after a replace" is a `HIRC` problem, not a media problem.**
   **Symptom:** the replaced WEM is valid audio but the game plays nothing. **Cause:** the
   `HIRC` stream source still names the old codec/plugin, or a loop parameter was dropped.
   **Fix:** edit the object's codec/plugin value in `HIRC` (Vorbis `4` newer / `262145`
   older) and preserve loop parameters; use the `.wschema` layout to do it correctly.

10. **Tooling verification is incomplete — treat both parsers as unproven.** **Symptom:** the
    bundled `wschema_dump.py` throws `IndexError` on real schemas (`v34`, `v132`, `v150`,
    failing in the `Interpolator` struct) instead of dumping them; the AGENTS.md claim that
    the C++ loader handles 15/16 schemas could not be reproduced here (the prebuilt `wwtools`
    binary predates the `schema` subcommand, so it rejects the command).
    **Cause:** schema-parser implementations diverge on some field. **Fix:** rebuild the CLI
    and round-trip a real bank before trusting either parser; do not assume the schema is
    parsed correctly just because the loader ran.

## Seen in

- **Watch Dogs: Legion / WD3** — BNKs are SoundBank **v132 (0x84) = Wwise 2019.2.x**; the
  Wwise authoring install that round-trips them is **2019.2.15.7667** (the 2021.1 install
  writes a different bank version and is incompatible). ~371,599 BNKs in the leak tree
  (`Sound/WD3/GeneratedSoundBanks/Windows/`); retail audio packed in `sound.dat` (~303 MB).
- **FusionTools 2.0.1** supported banks v34, v44, v48, v53, v62, v65, v88, v113, v120, v125,
  v128, v132, v135, v140, v145, v150; known-good games include the Assassin's Creed series
  (II → Mirage), Far Cry 5 / New Dawn / 6, Watch Dogs 2 / Legion, Mafia 3 /
  Definitive Edition, Life Is Strange.
- **Cyberpunk 2077** — WolvenKit `wwise-audio-tools` handles BNK extract and the `w3sc`
  sound-cache format (the upstream of the C++ merge target here).
- **Generic Wwise modding** — `wwiseutil` (Go, hpxro7 fork) replaces/dedupes WEMs; the
  `.wschema` loader is the newer route to the object layer.

## Open questions

- Confirm the C++ `.wschema` loader parses all real schemas after a rebuild (the `wschema`
  CLI subcommand exists in `src/main.cpp` but not in the June-2026 prebuilt binary), and
  reconcile it with the `wschema_dump.py` `IndexError` on the same files.
- Map the remaining Wwise version ↔ BNK version numbers (only `v132 = 2019.2.x` is confirmed
  here — verify 2021.1's version against a real bank).
- Finish the WAV→WEM path (the project TODO lists "WAV→WEM converter **or** OGG→WEM header
  rewrap (whichever preserves quality best)") and the Audacity WEM plugin.
- Port Phase 2b/2c in `wwise-audio-tools` (loop edit + full HIRC object parse/serialise) on
  top of the schema loader; the C++ port is **paused** after Phase 2a.
