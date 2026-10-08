---
kind: technique
title: "Frostbite bundle/chunk/EBX asset pipeline and the EALayer3 audio codec"
tools: ["bf4dumper.py", "sw_dumper.py", "swbf_me-c_edit", "fb3decoder.py", "ealayer3 (Zench / daemon1)", "Ninja Ripper", "Texmod"]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - "https://github.com/NicknineTheEagle/Frostbite-Scripts"
  - "https://github.com/vgmstream/vgmstream"
tags: ["frostbite", "bundle", "chunk", "ebx", "ealayer3", "mirrors-edge", "battlefield", "star-wars-battlefront", "nfs", "audio", "asset-pipeline", "file-format"]
---

# Frostbite bundle/chunk/EBX asset pipeline and the EALayer3 audio codec

> Frostbite games (Mirror's Edge Catalyst, Battlefield 4, Star Wars Battlefront,
> NFS 2016+) all share one asset model: bundles of resources live inside the
> `.toc`/`.sb` superbundles (there are no standalone `.bundles` files), `.chunk`
> files are raw blobs with meaningless names, and the real identity of every
> resource lives in **EBX** metadata keyed by hash/GUID. Because the same dumper
> and decoder scripts work across titles with small edits, this is a reusable
> pipeline rather than a per-game trick. Audio uses EA's **EALayer3** codec, a
> proprietary MPEG-layer-3 variant.

## When to use it
- You are extracting assets or audio from any Frostbite title and see `.toc`/`.sb`
  superbundles / `.chunk` / `.ebx` files.
- You need to turn nameless chunks back into named resources.
- You are decoding EALayer3 audio from an EA game (Sims 3 Xbox 360 music is also
  EALayer3, per the Sims 3 dump).

## How

### The bundle/chunk/EBX model
- Bundles live **inside** the `.toc`/`.sb` superbundles — there are no standalone
  `.bundles` files.
- `.chunk` — raw resource blobs. Filenames are not meaningful; resource names do
  not live in chunk names.
- **EBX** — object/type metadata database. Each sound/mesh/etc. is described by
  an EBX file that references chunk data by hash/GUID. Map chunks back to meaning
  through EBX.

### Extraction and decoding
1. Extract bundles → chunks with a Frostbite dumper: `bf4dumper.py` (Battlefield 4)
   or `sw_dumper.py` (Star Wars Battlefront), edited for the target's
   `targetDirectory`. A community `swbf_me-c_edit` adaptation targets Mirror's
   Edge Catalyst's bundle layout.
2. Decode audio with `fb3decoder.py` (Frostbite 3 audio decoder): walks `.ebx`
   files, finds audio chunks, writes decoded `.wav` using the **`ealayer3`** tool
   for the EALayer3 codec. The script needs `dumpDirectory`, `targetDirectory`
   and `ealayer3Path` set.

### EALayer3
EA-proprietary MPEG-layer-3 variant used across Frostbite and some Sims titles.
Battlefield 4 also ships XAS1 (EA ADPCM), Speex and raw PCM audio alongside
EALayer3.
Prefer **daemon1's ealayer3** build: Zench's original mis-splits multi-sound
chunks (a 5-sound chunk produced 15 files with 10 duplicates).

### EBX field types (`numDict`)
`fb3decoder.py` decodes EBX fields by mapping 16-bit type codes to Python
`struct` format chars:

| Code | Struct | Meaning |
|------|--------|---------|
| `0xC12D` | `Q` | uint64 (8 bytes) |
| `0xC0CD` | `B` | uint8 (1 byte) |
| `0x0035` | `I` | uint32 (4 bytes) |
| `0xC10D` | `I` | uint32 (4 bytes) |
| `0xC14D` | `d` | double (8 bytes) |
| `0xC0AD` | `?` | bool (1 byte) |
| `0xC0FD` | `i` | int32 (4 bytes) |
| `0xC0BD` | `b` | int8 (1 byte) |
| `0xC0ED` | `h` | int16 (2 bytes) |
| `0xC0DD` | `H` | uint16 (2 bytes) |
| `0xC13D` | `f` | float (4 bytes) |

## Gotchas
1. **`KeyError: 49437` (`0xC11D`) while decoding EBX.** **Cause:** a newer patch
   introduced a field type absent from `numDict`. **Fix:** daemon1's guidance —
   this type is unrelated to audio; delete the non-audio EBX folders and rerun.
   (A low-confidence community guess is `("q", 8)`, int64.)
2. **A multi-file audio chunk explodes into duplicates.** **Cause:** Zench's
   ealayer3 mis-splits multi-sound chunks (5 sounds → 15 files). **Fix:** use
   daemon1's ealayer3.
3. **Chunk filenames are garbage.** **Cause:** chunks are hash/GUID-addressed;
   names live only in EBX. **Fix:** map through EBX, don't trust chunk names.
4. **A dumper script fails on your title.** **Cause:** the scripts are written
   for a specific game's bundle layout. **Fix:** use the closest community edit
   (e.g. `swbf_me-c_edit` for ME Catalyst) or adjust `targetDirectory` and layout
   handling.

## Seen in
- Mirror's Edge: Catalyst (Frostbite 3) — full pipeline source.
- Battlefield 4 (Frostbite 3) — `bf4dumper.py` origin.
- Star Wars Battlefront (Frostbite 3) — `sw_dumper.py` origin.
- Need for Speed 2016 / Payback (Frostbite 3), Heat / Unbound (Frostbite 4) —
  same bundle/chunk model.
- The Sims 3 Xbox 360 music and SimCity-era audio also use EALayer3 (different
  container: DBPF v2 / RIFF Vorbis).
- Mirror's Edge (2008, UE3) does **not** use this pipeline: textures were ripped
  via Ninja Ripper / Texmod only.

For the concrete Battlefield 4 byte layout (magics, `3I6H3I` EBX header, DJB2
keyword hashing, field-type map, chunk audio tags), see
`games/battlefield-4/frostbite-3-archive-and-ebx-formats.md`.
