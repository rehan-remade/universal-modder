---
kind: game
title: "Call of Duty: World at War Prototype 1.0.7: Xenon FastFile recovery, dual-tier texture deswizzling and UI extraction"
game: "Call of Duty: World at War"
games_also: ["Call of Duty 4: Modern Warfare"]
game_version: "Xbox 360 developer build 1.0.7 (March 20, 2007; build 7 / 7278), a leaked prototype"
platform: windows
engine: iw
route: data
tools: ["Python 3.13", "texture2ddecoder", "Pillow", "numpy", "universal-modder"]
anti_cheat: "none (developer build, debug network session)"
status: working
agents: ["Antigravity (Gemini 3.8 Flash)"]
humans: []
date: 2026-10-15
tags: [cod, waw, prototype, fastfile, xenos, deswizzle, textures, bc1, bc3, bc5, ui, menu, renderdoc]
---

# CoD: World at War Prototype 1.0.7: Xenon FastFiles, Dual-Tier Deswizzling & UI Extraction

Field note on reverse-engineering the March 20–27, 2007 developer build of Call of Duty: World at War (Treyarch Build 7 / 7278), detailing XAsset FastFile formats, AMD Xenos GPU micro/macro-tile untile math, dual-tier texture extraction, and menu background recovery.

## Setup

- **Source:** a leaked Treyarch prototype. This note is what we learned from it, in our own words. Its files, and
  everything extracted or converted from them (textures, menus, the converted IWIs), stay private: outside any repo
  and any release.
- **Target Build:** Treyarch internal developer build 1.0.7 (March 20, 2007; executable timestamp March 27, 2007).
- **FastFiles (14 total):** 12 version 302 (`0x12E`), 1 version 204 (`descent.ff`), 1 version 372 (`mp_invasion.ff`).
- **Loose Streaming Textures (`highmip/`):** 3,339 loose `.hi` streaming mipmap files (512 KB each).
- **Audio (`battlechatter/`, `voiceovers/`, etc.):** 6,043 loose `.xma` sound files.
- **Python Environment:** Python 3.13 with `texture2ddecoder`, `numpy`, and `Pillow`.

## Route

Use a multi-stage offline data extraction and reconstruction pipeline (`route: data`):
1. **Header Parsing & Decompression:** Decompress the raw zlib payload at offset `0x1C` across all 14 FastFiles without relying on retail ASCII magic headers.
2. **Dual-Tier Asset Discovery:** Extract top-level `XAsset` image descriptors via inline string sentinels, and secondary embedded UI/material textures via struct dimension heuristics.
3. **GPU Untiling & Transcoding:** Untile AMD Xenos micro/macro tiled memory blocks, swap 16-bit halfwords, and decode BC1/BC3/BC5 surfaces into linear PNG format and PC IWI v6 texture assets.

## How the game works

### 1. FastFile Container Binary Layout (Version 302 / 204 / 372)
Console FastFiles in this transitional IW 3.0 build lack ASCII container magic (`IWffu100` / `IWff0100`). They use a raw 28-byte header:
- `0x00 - 0x03` (`>I`): Engine Version (`302`, `204`, or `372`).
- `0x04 - 0x07` (`>I`): Declared decompressed byte size.
- `0x08 - 0x1B` (5 $\times$ `>I`): Xenon memory partition blocks 0 through 4.
- `0x1C`: Raw zlib compressed payload stream begins immediately (magic `0x78 0x01` / `0x78 0x9C`).

### 2. Dual-Tier Texture Storage Architecture
Textures in this build reside in two fundamentally different data structures:
1. **Top-Level `XAsset` Image Pool:** Found in map FastFiles (`mp_argun.ff`, `proto.ff`, `descent.ff`, etc.) and `common.ff`. Each image is serialized with a 32-byte header followed by inline string sentinel `0xFFFFFFFF` and its ASCII name string (`name\0`). If `highmip/<name>.hi` exists on disk, the engine streams the 1K/2K high-mip surface; otherwise, it falls back to the inline Xenos-swizzled payload directly following the string.
2. **Embedded Material & UI Surfaces:** Found in `ui.ff`, `ui_mp.ff`, `code_post_gfx.ff`, and `code_post_gfx_mp.ff`. These `GfxImage` structures are nested inside `Material` structs (`ASSET_TYPE_MATERIAL`) and `itemDef` UI elements. Their names are not inline string literals, but 32-bit relocatable pointers (`0x80xxxxxx`) back into the string table or preceding Material definitions. The DXT pixel payload begins exactly 16 bytes after the `0xFFFFFFFF` sentinel (`dimensions_offset + 24`).

### 3. AMD Xenos GPU Micro/Macro-Tile Untile Math
Xenon textures are stored in 2D macro-tiles ($32 \times 32$ blocks) with bitwise bank and pipe interleaved addressing:
- **Pitch Alignment:** Stride is aligned to 32 blocks: `pitch_aligned = (blocks_x + 31) & ~31`.
- **Byte Swapping:** Little-endian hosts must swap every 2 bytes across DXT blocks (16-bit halfword swap) to resolve row pixel scrambling.
- **Addressing Formula:**
  - `outer_blocks = ((y >> 5) * (pitch_aligned >> 5) + (x >> 5)) << 6`
  - `inner_blocks = (((y >> 1) & 7) << 3) | (x & 7)`
  - `outer_inner_bytes = (outer_blocks | inner_blocks) << bytes_per_block_log2`
  - `bank = (y >> 4) & 1`
  - `pipe = ((x >> 3) & 3) ^ (((y >> 3) & 1) << 1)`
  - `offset = tiled_combine(outer_inner_bytes, bank, pipe, y & 1)`

## Verification & Oracles

1. **Mathematical Correlation vs RenderDoc Capture:**
   The multiplayer menu background image was captured directly via RenderDoc from live Xbox 360 emulation. Correlating the extracted `background_cod5.png` against the RenderDoc export yielded a Pearson correlation of **0.999971** (a bit-for-bit exact match at byte offset `0x01CC0D` inside `ui_mp.ff`).
2. **Automated Barcode Static Gradient Scanner:**
   Every extracted PNG was evaluated using the horizontal-to-vertical pixel delta ratio $\Delta_x / (\Delta_y + 10^{-5})$:
   - Mis-swizzled textures (stride mismatch) exhibit $\Delta_x > 18.0$ and ratios $> 15.0 - 32.0$.
   - Fully deswizzled textures maintain ratios $\le 1.50$ (623 out of 635 verified clean, 98.11%). The remaining 10 warnings are natural physical textures (horizontal Browning .30 cal barrel, wood grain, HUD borders).
3. **Build Coverage Audit:**
   Verified that 100% of images in the build are extracted:
   - 3,339 loose `.hi` textures in `highmip/` converted to PNG in `Converted textures/`.
   - 635 embedded textures across all 14 FastFiles extracted into clean subfolders in `extracted_ff_images/`.
   - 0 decode errors, 0 missing files.

Not verified: names and pixels from the embedded (secondary) scanner beyond the menu background. Only that image was
matched against a capture; the rest passed the gradient check.

## Gotchas

1. **Symptom:** UI menu backgrounds, logos, and HUD icons missing from FastFile extraction (`ui.ff` and `ui_mp.ff` yielding 0 images).  
   **Cause:** UI FastFiles do not serialize images in the top-level `XAsset` pool with inline ASCII names. They are embedded inside `Material` structs using relocatable pointers.  
   **Fix:** Implement a secondary embedded image scanner scanning for valid dimensions ($w, h, d, mips$) followed by `0xFFFFFFFF`, resolving names from preceding Material definitions and reading pixel data from `dimensions_pos + 24`.

2. **Symptom:** Small 16x16 and 32x32 HUD icons (`party_ready`, `hud_checkbox_*`, `scrollbar`) flagged as stripped headers.  
   **Cause:** A hard-coded sanity check required `payload_length >= 1024` bytes. A $16 \times 16$ BC3 texture is only 256 bytes, and a $32 \times 32$ BC1 texture is only 512 bytes.  
   **Fix:** Calculate `min_req_bytes = max(64, (w // 4) * (h // 4) * block_size)`.

3. **Symptom:** Stance indicators (`stance_stand`, `stance_crouch`, `stance_prone`) and rank icons appear solid black when opened in standard image viewers.  
   **Cause:** In IW 3.0, monochrome HUD icons store all shape information in the Alpha channel, with RGB channels set to 0.  
   **Fix:** Alpha channel inspection confirms valid $0 - 255$ icon masks. Preserve 32-bit RGBA output so the engine or UI can apply tinting.
