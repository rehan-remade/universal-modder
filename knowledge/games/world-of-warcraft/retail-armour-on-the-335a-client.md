---
kind: game
title: 'Retail armour models on the 3.3.5a client: M2 multi-texture effects, BLP limits and the material-index trap'
game: World of Warcraft
games_also: []
game_version: 'Wrath of the Lich King client 3.3.5a (build 12340, enUS, Direct3D 9) on a self-hosted AzerothCore server; source models from the retail 12.x client'
platform: windows
engine: native
route: asset-only
tools: [Python 3.12 (own M2/.skin writer, BLP and DBC tools), numpy, Pillow, Blender, StormLib/smpq, capstone, Ghidra 12.1]
anti_cheat: 'none touched: a private server the user runs; only client data files (a patch MPQ) change'
status: working
agents:
- Claude Code (Opus 5.5)
humans: [RedSuper]
date: '2026-10-02'
links: ['https://wowdev.wiki/M2', 'https://wowdev.wiki/M2/.skin', 'https://github.com/Deamon87/WebWowViewerCpp']
tags: [m2, skin, blp, mpq, dbc, armour, shaders, texture-combiners, crash, reverse-engineering, private-server]
---
# Retail armour models on the 3.3.5a client: M2 multi-texture effects, BLP limits and the material-index trap

> Retail (12.x) armour sets (Tier 2 remakes, PvP and trading-post sets, weapons) ported to the 2010 WotLK client
> 3.3.5a for a private server: shoulders, helms, belts and weapons, with retail's animated glow effects, on all
> 20 race/sex bodies. Route: write the old M2 (v264) + .skin files directly from the retail data, re-encode
> textures, add DBC rows, ship one patch MPQ. Dozens of items run in the real client. The traps below cost the most
> time; three of them are client behaviours nobody had written down, found by reading Wow.exe.

## Setup
- Client 3.3.5a build 12340 enUS, Direct3D 9 (the user also runs DXVK, which changed nothing here). Server:
  AzerothCore (WotLK) the user hosts; item display rows come from the client's `ItemDisplayInfo.dbc`, item ids
  from the server's `item_template`.
- Source: retail 12.x item `.m2`/`.skin` and BLP/texture files read from the retail install (CASC), referenced
  by FileDataID.
- Our tools: a Python M2/.skin writer for v264, BLP2 encoder (DXT1/DXT5) with mip control, a DBC reader/writer,
  StormLib/smpq (in WSL) for MPQs, Blender only for checking geometry, capstone and Ghidra for reading Wow.exe.

## Route and why
**Asset-only, written straight from retail data.** A Blender round trip loses what matters on these items:
retail's multi-texture effect batches (a mask on UV1 times a scrolling copy on UV2), texture transforms, layers and
blend modes. So the converter maps each retail batch to 3.3.5 batches itself and writes the binary formats. The
client is not patched for any of this (a separate project hooks it for other features).

## How the game works (what we had to learn)
- **Two-texture batches exist in 3.3.5**, behind M2 header flag `0x08`: the header grows to `0x138` and gains a
  `texture_combiner_combos` array at `0x130`. A batch's shader field then indexes that array, one combine op per
  stage: 0 Opaque, 1 Mod, 2 Decal, 3 Add, 4 Mod2x, 5 Fade, 6 Mod2xNA, 7 AddNA.
- **Load-time shader id** (Wow.exe `0x836990`): op0 is forced to Opaque on opaque materials; a stage whose
  texture-unit lookup value is above 2 (store -1) is a sphere map (`|8`); unit 1 on the last stage sets `0x4000`
  (UV2). The id is `(op0 << 4) | op1`.
- **Effect build** (`0x836600`): two stages always use vertex shader `Diffuse_T1_T2` (stage 0 on UV1 with texture
  matrix 0, stage 1 on UV2 with matrix 1) unless a stage is a sphere map (`*_Env`). Pixel shader pairs that exist:
  `Opaque_` + {Opaque, Mod, Add, Mod2x, Mod2xNA, AddNA}, `Mod_` + {Opaque, Mod, Add, Mod2x, Mod2xNA, AddNA},
  `Add_Mod`, `Mod2x_Mod2x`; anything else falls back to `Mod_Mod`. `Combiners_Mod_Mod` multiplies colour AND alpha
  of both stages with the vertex colour (read from the ps_3_0 shader in the stock archives).
- **Retail effect ids** (`0x8000 | n`) are resolved through the shader table that WebWowViewerCpp reproduces
  (`M2ShaderTable`); e.g. effect 21 = mask stage on UV1 × scrolling stage on UV2, which 3.3.5 draws natively as
  `Mod_Mod` with units (0, 1).
- **Texture transforms:** stock items only key the translation track (110 of 110 transforms); empty rotation and
  scaling tracks are normal.
- **Blend modes stop at 6** (0 Opaque, 1 AlphaKey, 2 Alpha, 3 NoAlphaAdd, 4 Add, 5 Mod, 6 Mod2x). Retail's 7
  ("BlendAdd", One / InvSrcAlpha) does not exist in 3.3.5.
- **The material-index copy pass** (`0x837680`, the loop at `0x8379e1`): after the shader ids, if any batch has a
  material layer above 0, every batch whose material INDEX equals the previous batch's gets that batch's shader,
  texture count, texture combo and transform combo copied over its own (texture-unit combo and weight are kept);
  the copies chain down a run. Blizzard's exporter only gives consecutive batches the same index when they are
  layers of one material. The same pass also fuses an opaque batch followed by certain one-texture layers
  (sphere-map ones) into special `0x8000` effects.
- **Batch flag `0x10`** is only read for doodad batching (`M2BatchDoodads`, on by default) and sorting; stock
  animated batches never set it (0 of 81), static ones almost always do. It didn't change anything we saw.
- **BLP size limit:** the client creates a texture over 1024 px one mip level smaller on the GPU but copies the
  full-size rows into it.

## Build steps
1. Read the retail item's model files and textures (by FileDataID).
2. Per retail batch: resolve its effect to stages (texture, UV set, transform, combine op); map blend 7 to 4.
3. Write v264 `.m2` + `00.skin`: one material record per batch where the next rule needs it (see gotcha 1),
   header flag `0x08` + combos when any batch has two stages or a non-UV1 unit.
4. Re-encode textures as BLP2 DXT1/DXT5, at most 1024 px (drop top mips).
5. Add/point `ItemDisplayInfo.dbc` rows (model, texture names) for the display ids the server's items really use.
6. Pack everything into a patch MPQ whose name sorts after the others (a later patch letter wins), install, test.

## Verification
- In the real client on the private server: the sets were checked on characters in game by the human, against
  retail's model viewer and in-game retail screenshots.
- For the effect bugs: a small software rasteriser that draws a built model's batches from the file data with the
  client's combiner maths, plus an emulation of the copy pass. It reproduced the broken in-game look exactly (flat
  bright bars and panels) on the old files and a clean render on the fixed ones. The client functions were read
  with capstone and confirmed in Ghidra's decompiler.
- A scan over the whole built stage reports every model whose batches the copy pass would change (19 found, 0
  after the fix).
- Not verified: the fixed priest shoulders and helms in game (the fix shipped the same day; awaiting the in-game look).

## Gotchas
1. **Effect cards drew as flat white bars and panels: no mask, no scroll.** **Cause:** the converter shared one
   material record between all batches with equal (flags, blend); the two-stage scrolling cards came right after a
   one-texture glow layer with the same material index, so the client's load pass (`0x837680`) copied the glow
   layer's shader, texture and transform over them. **Fix:** give a batch its own copy of the material record when
   the previous batch has the same index but other stages (compare what the combo indices resolve to); identical
   layers may share.
2. **Solid pale panels on effect geometry.** **Cause:** retail blend mode 7 written as is; 3.3.5's blend table ends
   at 6. **Fix:** map 7 to 4 (additive), as our particle converter already did.
3. **Crash in `Wow.exe+0x11ede`, or silent heap corruption, after a texture update.** **Cause:** a 2048 px BLP; the
   client allocates one mip smaller and overruns by ~0.5 MB. **Fix:** never ship a BLP over 1024 px; drop the top
   mip.
4. **Crash at `0x7BD450` on a simple attached model.** **Cause:** a one-sequence model whose Stand record links a
   variation (`variationNext` ≠ -1); the bounds read at `0x825750` isn't checked. **Fix:** `variationNext = -1`,
   frequency 32767, as stock does; never copy a body's Stand record as is.
5. **Glowing mesh outlines instead of a fel glow.** **Cause:** guessing which UV set a retail effect stage uses (or
   replacing the mask with a constant); the mask is 0 on the shells' borders. **Fix:** map each stage to its UV set
   from retail's effect table.
6. **Helms float or sink.** **Cause:** retail moved the helm attachment ~20 cm relative to the 3.3.5-era HD bodies.
   **Fix:** offset helms by (retail attachment 11 − body attachment 11). Shoulders and the belt buckle (attachment
   53) match.
7. **The DBC edit "does nothing".** **Cause:** the items use other display rows than the obvious ones (here the
   suffixed variants). **Fix:** look up the server's `item_template.displayid` first.
8. **Skies turned green after a texture pack.** **Cause:** palettised BLPs where the client expects DXT in that
   folder. **Fix:** match the stock format per folder; re-encode as DXT.
9. **Bright effect panels persisted after "fixing" them by dropping stages.** **Cause:** fixing the symptom: the
   real cause was gotcha 1, and dropping the stages removed the effect entirely. **Fix:** reproduce the in-game look
   from the file data first (emulate what the client does), then change the writer.

## Assets
All textures come from the retail files or are recoloured/upscaled locally (Pillow/numpy, Real-ESRGAN ncnn). No
generated art, no paid services.

## Open questions
- In-game confirmation of the gotcha-1 fix on the T2 priest shoulders and helms.
- The other half of the copy pass (opaque + sphere-map layer fusion into `0x8000` effects) is only partly mapped;
  a converter that emits such pairs should check it.
