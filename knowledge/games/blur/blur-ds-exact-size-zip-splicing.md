---
kind: game
title: "Exact-size zip splicing for Blur DS texture edits"
game: "Blur"
games_also: []
game_version: "Blur DS beta, Europe, unreleased; 64 MB NDS ROM, title BLUR, game code BBRP, maker code 36"
platform: console
engine: unknown
route: asset-only
tools: ["Python 3 (struct, zlib)", "melonDS 1.1", "COLLADA .dae export (mesh comparison)"]
anti_cheat: "none — unreleased offline beta"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash Free)"]
humans: ["@GameBreaker20XX"]
date: 2026-10-21
links: ["https://github.com/melonDS-emu/melonDS"]
tags: [nds, zip, deflate, exact-size, splicing, texture, palette, firebrand, octane, blur, rom-patching]
---

# Exact-size zip splicing for Blur DS texture edits

> Blur DS keeps every asset in a plain `vfs.zip` sitting at a fixed offset inside a 64 MB NDS ROM, so
> anything that changes an entry's compressed size shifts every offset after it. I wrote car-texture edits
> into unused palette space and spliced the resulting deflate streams back at **exactly** their original
> lengths, producing a ROM with the zip byte-size unchanged and all 3,146 entries intact. The texture ROM is
> structurally verified; **it was never confirmed booting in-game**, so treat it as unverified. Status
> `in-progress`.

## Setup

- **Game:** Blur (DS), Europe beta, unreleased — the DS counterpart to the 2010 console title. 64 MB
  (67,108,864-byte) NDS ROM, title `BLUR`, game code `BBRP`, maker code `36`.
- **Where this copy came from:** the game was never sold, so there is no shop copy to dump. The author used a
  public copy of the unreleased beta from the Hidden Palace archive. It is not linked here, and this note
  gives no checksums for it.
- **Test car:** the author's texture tests were on the car called the Spiral. The patch pass below covers all
  24 car directories, and Verification says what was and wasn't checked.
- **Engine:** Firebrand Octane, Firebrand's in-house engine. This beta has a `vfs.zip` container, `.n` models,
  NitroSDK 2D formats and Lua 5.1 bytecode.
- **Container:** `vfs.zip`, **24,658,789 bytes, 3,146 entries**, stored in the ROM at `0x021C4800` and
  ending at `0x03948B65`.
- **Tools:** Python 3 with `struct` and `zlib` only; melonDS 1.1 to launch; COLLADA `.dae` export for
  mesh comparison.

## Route and why

`asset-only`, because the goal was a content change on an offline beta with a plain-file container.

- **`data`** would have changed the car roster or stats, not the visuals — easier, but not the goal.
- **`native-hook` / loader** means patching ARM9 code in an unreleased beta with no loader ecosystem. Far
  more risk than the task justified, and it fails the moment anything re-reads the cartridge image.
- **`decomp-recomp`** — no decompilation of this engine exists.

Asset-only is the right call *provided* you can write into the ROM without moving anything. That
constraint turned out to be the whole project.

## How the game works (what we had to learn)

### The container is a stock zip at a fixed offset

`vfs.zip` is a normal zip with Deflate-compressed entries: local headers, compressed streams, then a
central directory and end-of-central-directory record. Because the whole archive sits at one fixed ROM
offset, **any change to any entry's compressed size shifts every byte after it** and invalidates the
central directory's offsets. On a 64 MB cartridge image that is not a problem you can paper over with a
rebuild — it is the problem.

The workable consequence: if you can produce a new Deflate stream of **exactly** the old `csize`, the
archive's layout is untouched, and you only have to overwrite those bytes in the ROM.

### Car meshes and their LOD ladder

Cars live under `Graphics/Cars/<car code>/<variant>/`, each with an eight-file LOD ladder:
`lod0`, `lod1`, `lod1net`, `lod2`, `lod3`, `lod3net`, `lod4`, `lod4net`. There are 24 car directories, so
24 `lod0` files.

`.n` files carry GX-style primitives (tri-strips, triangles, quads) and palette-indexed textures. Two
palette groups showed up repeatedly, a body palette (`custom_pl`) and a reflection palette (`envmap_pl`).

### Free palette pairs are the writable real estate

A car's texel data is palette-indexed. Some palette index pairs are **never referenced by that mesh's
UVs** — dead entries. Writing into the texel regions those pairs cover changes the image without
touching anything the model actually samples. That is the trick that makes a texture edit possible under
an exact-size budget: you are changing bytes that the original compressor already had to encode, in a
region whose colour statistics you can keep close to the original.

In practice the patch pass located a rectangular site per car, wrote a label into it in a single flat
colour, and then recorded four numbers: how many blocks changed, how many bytes changed, whether anything
inside the site was invalid, and **whether anything outside the site changed at all**.

### The exact-size splice

For each patched `.n`:

1. Recompress the modified file.
2. Tune the stream until its length equals the original entry's `csize` exactly.
3. Overwrite that entry's stream in a copy of `vfs.zip`.
4. Update the entry's CRC-32, which covers the *uncompressed* data and so changes with the edit. It is
   stored twice: in the entry's local header (offset 14, or in a data descriptor after the stream when
   flag bit 3 is set) and in its central directory record (offset 16). No offset needs recomputing,
   because no length moved.

Every spliced entry in the log reports `stream exact`, which is the invariant that matters.

## Build steps

1. Extract the ROM and locate `vfs.zip` (offset and length above).
2. Inventory entries and record each entry's `csize` — that number is your hard budget.
3. For a texture edit, find palette pairs the mesh never references, pick a texel site, write into it.
4. Recompress and force the stream to the original `csize`.
5. Splice the streams into a copy of `vfs.zip`; assert the archive length is unchanged.
6. Overwrite only the zip region in the ROM image.

## Verification

**Structurally verified:**

- `testzip`: **ALL OK** on the rebuilt archive.
- Per-entry round-trip CRC for all 24 spliced entries.
- Central directory CRC records re-verified.
- **Archive size identical**: 24,658,789 bytes before and after.
- **ROM writes stayed inside the archive**: 1,614,744 bytes changed, all within the zip range.
- **Geometry untouched**: exported `.dae` for original vs patched car is identical apart from the
  exporter's `<created>`/`<modified>` timestamps — 391 lines each, 4 differing lines, all timestamps.
- Texture-patch pass: **24/24 cars** patched, each with `verify_changed_outside: 0`.

**Not verified:**

- **The modded ROM was never confirmed running.** No screenshot, no emulator log, no in-game observation —
  the pipeline ends at a written ROM. Everything above proves the file is structurally sound,
  not that the game accepts it.
- Whether the patched texels are actually invisible on the car. Free palette pairs are *unreferenced by
  the mesh*, which is a strong argument, but it was never confirmed on screen.
- The CRC copies in the local headers. `testzip` and the central-directory check above read only the
  central directory's CRCs (Python's `zipfile` never compares the local header's), and the game's own
  reader may use either.

## Gotchas

1. **`19/24` on the first texture pass, `24/24` on the second. Symptom:** five cars failed with
   `no free palette pair`. **Cause:** some meshes reference every palette pair in their body palette.
   **Fix:** widen the search to a cross-palette region (the reflection palette) instead of only the body
   palette. Budget the writable area per car rather than assuming it exists.
2. **A single byte of size drift invalidates the whole archive.** **Symptom:** anything that recompresses
   an entry normally makes the game's reads land on garbage after that point. **Cause:** every central
   directory offset is relative to the archive start, so a longer stream moves all of them.
   **Fix:** treat `csize` as immutable and assert it before writing, per entry.
3. **"It recompressed fine" is not verification.** **Symptom:** a stream that decompresses correctly but
   is the wrong length looks healthy in isolation. **Cause:** correctness and length are separate
   properties. **Fix:** check both, per entry, and assert the archive length is unchanged as a whole.
4. **Exported-mesh diffs lie about timestamps.** **Symptom:** comparing original vs patched `.dae` reports
   four changed lines and looks like geometry drift. **Cause:** the exporter stamps `<created>` and
   `<modified>` per run. **Fix:** ignore those two elements when hashing or diffing, or normalise them
   first — otherwise you cannot tell "geometry is identical" from "geometry moved slightly".
5. **A bad splice can't be undone in place.** **Symptom:** one bad entry written straight into the ROM
   image. **Cause:** with 3,146 entries in a 24 MB archive, a rewrite in place leaves nothing to compare
   against or roll back to. **Fix:** splice into a copy of `vfs.zip`, write that into a copy of the ROM, and
   keep the original image until the splice is verified.

## Assets

None shipped: no game files, extracted textures or ROM images are included here.

## Cost and time

Several sessions. The texture-patch path converged in two passes.

## Open questions

- **Does the patched ROM actually boot?** This is the single missing check and it is cheap: load it in
  melonDS and look at a car. Until then the texture work is structurally sound and unproven.
- **Are free palette pairs genuinely invisible?** Unreferenced-by-UV is a strong signal, not a guarantee;
  a mip or a second UV set could still sample them.
