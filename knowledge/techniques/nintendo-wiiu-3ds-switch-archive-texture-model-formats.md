---
kind: technique
title: "Nintendo Wii U / 3DS / Switch archive, texture and model formats (Yaz0, SARC, GTX, CMB/CSAB, BWAV/BAR)"
tools: ["Syroot.NintenTools.Yaz0", "Switch-Toolbox (KillzXGaming)", "JayK SARC unpacker", "texconv2", "QuickBMS", "OoT3D-Importer (MeltyPlayer)", "GAR/ZAR unpack", "vgmstream", "HKXConverter-2012"]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - "https://zeldamods.org/wiki/Yaz0"
  - "https://zeldamods.org/wiki/SARC"
  - "https://github.com/zeldamods/oead"
tags: ["zelda", "nintendo", "yaz0", "sarc", "gtx", "cmb", "csab", "bwav", "bars", "wiiu", "3ds", "switch", "big-endian", "archive", "texture", "file-format"]
---

# Nintendo Wii U / 3DS / Switch archive, texture and model formats (Yaz0, SARC, GTX, CMB/CSAB, BWAV/BAR)

> Nintendo's modern formats stack in a predictable way: a container (SARC), often
> compressed (Yaz0 on Wii U, zstd on Switch), holding assets that are themselves
> Nintendo-specific (GTX/BWAV on Wii U/Switch, CMB/CSAB on 3DS). Wii U data is
> **big-endian**; 3DS and Switch are **little-endian**. Repacking works with real
> encoders (oead's Yaz0 at levels 6–9 and `SarcWriter`, which preserves endianness
> and alignment), so the old "no working re-compressor" gap does not apply. This
> note records the formats across Breath of the Wild, Tears of the Kingdom,
> Twilight Princess HD, Skyward Sword, Ocarina of Time 3D and the Sonic Lost
> World Zelda DLC.

## When to use it
- You meet a `.pack`, `.sarc`, `.sblarc`, `.arc`, `.zar`, `.gtx`, `.cmb`,
  `.csab`, `.bwav` or `.bars` and need to know container vs asset, endianness,
  and which tool reads it.
- You are on a Nintendo target where the bottleneck is **repacking**, not extraction.

## How

### Archives and compression
- **Yaz0** — Nintendo's LZSS variant. Magic `Yaz0`, **big-endian**. Original spec:
  `http://www.amnoid.de/gc/yaz0.txt` (GameCube era). In BotW a `.sblarc` is a
  Yaz0 stream wrapping a SARC: `content/Pack/*.pack` (SARC) → `Layout/*.sblarc`
  (Yaz0). Tools: `Syroot.NintenTools.Yaz0` (C#), `Yaz0.exe`.
- **SARC** — plain container, magic `SARC`. JayK's 2015 unpacker works across
  BotW, Mario 3D World, Captain Toad. oead's `SarcWriter` repacks it correctly,
  keeping the target's endianness and alignment.
- **Twilight Princess HD** — `.pack.gz` (gzipped SARC); QuickBMS extracts to
  `geo/` and `tex/`.
- **TotK** — `.bars.zs` is **zstd**-compressed; decompress to `.bars` (contains
  `.bwav`).
- **Skyward Sword** — LZ compression + `.arc`; enemy data in `.endat`/`.entxt`/
  `.zev.dat` (spawn/event formats undocumented).

### Textures: GTX / GX2 / VTFX-adjacent
- **GTX** (Wii U) — block-compressed texture. Standard tools (texconv2, Noesis)
  read only the **first** texture in a file. TPHD uses a newer GTX storing
  **multiple textures per file**; a community splitter was being developed but
  never released.
- **GX2** — Wii U texture header seen in Sonic Lost World Zelda DLC `.dds`
  files (`Gfx2` header).

### Models and animation: CMB / CSAB (3DS)
- `.cmb` = model container; `.csab` = skeletal animation; `.zar` = archive
  holding both. `N3dsCmb Viewer` loads `.cmb` but **fails on `.csab`**.
- CSAB notes (shakotay2): bone weights live in `VatrChunk.BoneWeights`;
  animation data at `sepd.BoneWeightArrayOffset`; frame data is **16 bytes/frame**
  (offset difference = frame count × 16). Skinning weights possibly in the `.dae`
  export (unconfirmed).
- Working pipeline: GAR-ZAR unpack → `OoT3D-Importer` (Blender) → save `.blend`
  → open in Blender 2.83+ LTS to fix viewport GFX issues.

### Audio: BWAV in BAR/ZS
- `.bwav` inside `.bars.zs` (zstd) → `.bars`. ~90% playable in Foobar2000 +
  **vgmstream**; ~10% fail (possibly a different encoding).
- Switch-Toolbox reads BWAV.

### Zelda DLC on a non-Zelda engine
- Sonic Lost World Wii U (Hedgehog Engine) Zelda Zone DLC:
  `.cpk` (CriWare) → QuickBMS CPK script → `.pac` (pacpack-WiiU) → assets.
- `.model` → FBX via `modelfbx_2012` (no bones); `.skl.hkx` + `.anm.hkx` are
  **Havok 2012** packfiles → `HKXConverter-2012-With-Metadata` for bones.
  `zdlc03_obj_fairy.model` converts to 5 planes (texture-driven geometry); the
  4th material slot expects the literal string `"water"` or it errors.

## Gotchas
1. **Yaz0 repack produces a valid file the game rejects.** **Cause:** early tools
   re-encoded at fake compression (level 0), which the game rejects. **Fix:** use a
   real encoder — oead's Yaz0 at levels 6–9 produces files the game accepts.
2. **SARC repack crashes even with untouched content.** **Cause:** a repacker that
   did not preserve the container's endianness/alignment. **Fix:** use oead's
   `SarcWriter`, which keeps both; avoid ad-hoc repackers.
3. **Only the first texture extracts from a GTX.** **Cause:** TPHD-era GTX
   packs multiple textures; texconv2/Noesis read one. **Fix:** splitter never
   released — unresolved.
4. **`.csab` animation won't load.** **Cause:** N3dsCmb viewer has no CSAB
   playback. **Fix:** export via OoT3D-Importer/Blender path; treat CSAB as
   data-documented only.
5. **`.bars`/`.bwav` audio won't play.** **Cause:** ~10% of BWAV streams use an
   encoding vgmstream doesn't handle. **Fix:** none recorded.
6. **Blender importer shows broken GFX.** **Cause:** old Blender viewport.
   **Fix:** open the saved `.blend` in Blender 2.83+ LTS.

## Seen in
- Breath of the Wild (Wii U/Switch): Yaz0, SARC, GTX.
- Tears of the Kingdom (Switch): `.bars.zs` (zstd), `.bwav`.
- Twilight Princess HD (Wii U): multi-texture GTX, `.pack.gz`.
- Skyward Sword (Wii): LZ/ARC, `.endat`/`.entxt`/`.zev.dat`.
- Ocarina of Time 3D / Majora's Mask 3D (3DS): CMB/CSAB/ZAR.
- Sonic Lost World Wii U Zelda Zone DLC: CPK/PAC, Havok 2012 HKX, GX2 textures.
- Four Swords Anniversary (DSi): `.bin`, `.blz` (no documented tool).
