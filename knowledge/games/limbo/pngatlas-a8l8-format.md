---
kind: game
title: Limbo A8L8 texture format, standalone sprites, and a live-verified menu-title mod
game: Limbo
games_also: []
game_version: 'Steam (appid 48000), limbo.exe 5,453,312 bytes; Steam build ID not recorded'
platform: windows
engine: native
route: data
tools: ["python+struct", "numpy", "pillow", "hgrep on limbo.exe", "um win"]
anti_cheat: "none (single-player; SteamStub DRM wrapper on the exe, which this route never touches)"
status: working
agents:
- 'OpenCode (big-pickle)'
humans: []
date: '2026-10-07'
links:
- 'https://github.com/gibbed/Gibbed.Limbo'
- 'https://github.com/theberrigan/apps/blob/master/projects/21_game-tools/tools_Limbo.py'
tags: [textures, atlases, pngatlas, a8l8, d3d9, asset-only, live-verified]
---

# Limbo A8L8 texture format, standalone sprites, live-verified menu-title mod

> Limbo stores sprite art as A8L8 (16-bit luminance+alpha) textures. Two layouts:
> **standalone sprite files** (`data/sprites/**/*.png`, `.png_a`, `.pngblur`) carry
> their own **render dims and a full mip chain**, and **atlases**
> (`data/texture/atlas/*.pngatlas`) are 4096-texel-wide sheets whose sizes match a
> 6-level mip chain exactly, so they most likely carry mips too (not yet confirmed by
> decoding level 1). Runtime semantics (user-verified in the live game):
> the **L (luma, low byte) channel drives visibility** on the darkness/blur pass
> (L=0 → invisible), the **A channel is effectively ignored**; the **UI/menu is drawn
> from the standalone sprite files, not the atlas**; the atlas blob IS consumed
> (whole-sheet edits visually wreck the world), and the atlas **manifest
> `data/texture/atlas/atlas_blur.txt` IS the live path→rect table** (swapping two
> entries' rects in the text changed the rendered darkness pass; `atlases.txt`, a
> named boot entry listing the two `.png` atlas resources, is also read at runtime —
> bogus names render the menu near-white). A byte-exact repack route (
> `repack_limbo.py --entry <path.d> --in <edited>` → swap `limbo_boot.pkg` → launch)
> was proven: zeroing the L plane of the menu title sprite removed the LIMBO title.

## Setup
- Steam install of Limbo (appid 48000) at `...\Steam\steamapps\common\Limbo`.
- `limbo_boot.pkg` / `limbo_runtime.pkg` unpackable with a Python port of
  [Gibbed.Limbo](https://github.com/gibbed/Gibbed.Limbo). Filelists:
  `bin\projects\LIMBO\files\limbo_boot.filelist` / `limbo_runtime.filelist` (they name
  1,088 of 1,410 boot entries and 222 of 455 runtime entries; the pkg hash is CRC32 of
  the lowercase '/' path).
- Working dir was a pristine copy of the install with an SHA-256 manifest, plus a
  save backup before anything was launched modded. Everything reverted afterwards.

## Route and why
- Route: **data / asset-only** — decode, edit, re-encode, repack the .pkg, swap in.
  Launches via Steam only (`um win launch --steam 48000`); the game window is
  `limbo` (1024×576 when windowed). It writes no logs. Steam does NOT revert
  swapped pkgs; swap back manually from backups.
- Anti-cheat: none. The exe carries Steam's SteamStub DRM wrapper; this route leaves
  the exe alone and changes only data files, so no hook is needed.
- Live workflow: back up install → `Copy-Item` modded `limbo_boot.pkg` over the
  live one → launch → screenshots via `um win shot <out> --exe limbo` → drive with
  `um win drive --proc limbo "focus" "key 0x0D"` (Enter) → confirm with the human →
  restore boot+runtime+settings from backup and delete the game's `derived` folder.

## How the game works (verified facts)
- PKG: u32 count; then count × (u32 name_hash, u32 entry_off, u32 size); blobs at
  table-end + entry_off. `.d` entries are zlib-deflated; repack wrote them back
  deflated, untouched entries by verbatim slice (no-op rebuild is SHA-identical).
- Texture file wrapper (all sprite + atlas files). The prefix is four u32s, then the
  path (layout per theberrigan's `tools_Limbo.py`, `checkSprites`):
  ```
  u32 = 9 ; u32 = 2 ; u32 flags (1, 9 or 17) ; u32 (varies)   # 16-byte prefix
  u8  pathLen ; ascii path (lowercase, '/' separators)
  ```
  The id-like byte seen here (e.g. 0x72, 0xB1, nibble patterns; NOT a path CRC) and
  a byte that reads 1 are somewhere in that 16-byte prefix; their exact positions
  weren't confirmed.
  Then the **internal texture header, 18 bytes**, at 17 + pathLen:
  ```
  u32 = 7 ; u16 ; u16 W ; u16 H ; u16 usedW ; u16 usedH ; u16 ; u16
  pixel start P = 17 + pathLen + 18 ; texels run to exact EOF
  ```
  The u16 after the 7 was 0 in the files checked here; theberrigan's script also
  sees 0x0C0C, 0x3333 and 0xC8C8 there.
  Example (menu title, pathLen 38): W=2048 H=1024 usedW=1280 usedH=720,
  tail u16s = [0x0C02, 0x0A01]. chapters/1.png (1024×512): tail [0x0B02, 0x0A01].
  atlas_blur: W=4096 H=4096 used=4064×3984 tail [0x0602, 0x0A11].
- **Texel = D3DFMT_A8L8**: LE u16, low byte = L (luma), high byte = A (alpha).
  Confirmed by exe string `only 8A8L format supported`. White on screen ⟺ high L.
- **Standalone sprites = mip chain, no packing**:
  pixel bytes = 2 × (W*H + (W/2)*(H/2) + … + 2*1). Title: 2048×1024 chain =
  2,796,202 texels = 5,592,404 bytes = file−(P) exactly. chapters/1: 1024×512
  chain = 699,050 texels = 1,398,100 bytes = exactly.
- **Atlas sizes match a 6-level mip chain exactly, so these are most likely mip
  chains** (not yet confirmed by decoding level 1): atlas_blur's texel data is
  4096 × 5460 = 22,364,160 texels = 4096² + 2048² + 1024² + 512² + 256² + 128², a
  4096×4096 base plus five halvings, and its header tail byte is 0x06. atlas_norm's
  4096 × 1365 = 5,591,040 texels is exactly the same 6-level chain of a
  4,194,304-texel base (4096×1024 or 2048×2048), which fits its 4064×720 used size;
  its own header W/H weren't recorded here. theberrigan's `parseSprite` also reads a
  4096×4096 atlas as halving mip levels. The member check below decodes level 0 at
  width 4096, which holds either way.
- **Channel semantics (live, user-confirmed)**: A is effectively unused by the
  shader/loader; L drives a darkness/luminance pass. Whole-sheet edits prove the
  atlas is sampled (every texel 0xFFFF → "blocky-blobby, mostly black"); every-texel
  A=255 ≈ vanilla; every-texel L=255 → title screen pure black.
- **UI/menu sprites are separate files, read at runtime**: zeroing L across all the
  menu title sprite's mips removed the LIMBO logo from the live main menu; the rest
  of the menu unchanged. The exe holds the strings `Loading atlas texture: '%s'`,
  `sprites/chapters/`, `sprites/text/`, `Atlases not found`/`Atlas not found [%s]`,
  `'ATLAS'`, `'BLUR'`, and `atlases.txt` — but no hardcoded `atlas_blur.txt` (the
  manifest path is derived from the `.png` name at runtime). `atlases.txt` (a named
  boot pkg entry) is just a 2-line list of `"data/texture/atlas/atlas_blur.png"` /
  `"data/texture/atlas/atlas_norm.png"` and IS read live: pointing it at bogus
  names rendered the menu near-white (mean 233 vs vanilla 45).
- **Boy / characters**: no `boy_default` name appears in the boot filelist, but the
  filelists are partial (about 550 entries across both pkgs have no name), so that
  doesn't show the boy is atlas-only. He does appear in the atlas manifest (337
  entries). Live proof that the manifest is the runtime rect source: swapping the
  `myst` (fog, L mean ≈205) and `boy_default/head_cutoff` (L mean ≈8) rects in
  `atlas_blur.txt` — texture untouched — moved the rendered darkness pass (menu after
  swap: mean 58.97 vs vanilla 45.45; region grid shows the change concentrated at the
  fog/boy band, hot pixels x[619–1696] y[43–827], centroid (1194,452)). Earlier,
  localized pixel edits in the boy's rects showed nothing. For zeroing his L that's a
  **black-on-black confound** (his texels are already near-black); whitening showing
  nothing isn't explained by that, and stale lower mips (Gotcha 5) are worth ruling
  out. The manifest edits themselves DID land.
- Scenes / `skeleton.branch` reference sprites by path string plus per-instance
  floats (world size/basis), never by rect: e.g.
  `data/sprites/characters/boy/boy_default/head_cutoff.png` and
  `.../children/boy_skinny_01/l_thigh.png`.

## Build steps
The scripts named here (`unpack_limbo.py`, `limbo_tex.py`, `make_titlezero.py`,
`repack_limbo.py`, `shot_diff.py`) are the session's own and aren't published; the
format section above is enough to rewrite them.
1. Unpack: `python tools/unpack_limbo.py pristine_pkg <filelist_dir> lab\boot`
   (boot and runtime). `.d` stored entries come out with the `.d` stripped.
2. Inspect: `uv run --quiet --with numpy python tools/limbo_tex.py inspect FILE`.
3. Edit a standalone sprite in place (SAME byte length so the .d deflate stays
   valid): e.g. `tools/make_titlezero.py` zeroes the L byte of every texel in every
   mip of the menu title and writes `lab\renders\limbo_title_zero.png`.
4. Repack and swap:
   ```
   uv run python tools/repack_limbo.py pristine\Limbo\limbo_boot.pkg ^
       tools\Gibbed.Limbo\bin\projects\LIMBO\files ^
       lab\renders\limbo_boot_TAG.pkg ^
       --entry "derived/pc/data/sprites/text/menu/limbo title.png.d" --in NEWFILE
   Copy-Item lab\renders\limbo_boot_TAG.pkg "<install>\limbo_boot.pkg" -Force
   ```
5. Kill any running game by exact PID (`um win kill PID`), launch via Steam,
   screenshot (`um win shot out.png --exe limbo`), diff vs a vanilla capture with
   `tools/shot_diff.py` / numpy, verify with the human.
6. Restore: copy backed-up boot+runtime+settings.txt back and delete
   `<install>\derived`.

## Verification
- **Byte-exact round trip: 140/140 sprite files** parse → re-emit → identical SHA.
- **42/42 atlas members** decode pixel-identical to their standalone file (Jaccard
  1.0) at sheet width 4096 (level 0).
- **Repack identity**: rebuild with zero replacements is byte-identical to input.
- **Live proof (standalone/UI)**: with the title L-plane zeroed, two menu screenshots
  agree (mean 14.4 vs vanilla 25.7) and the diff is confined to the title band
  (x184–828, y116–466, centroid 538,255, max diff 255); the human confirmed the title
  is gone in-game. Reverted to vanilla afterwards (SHA-verified).
- **Live proof (atlas/manifest IS read)**: (1) `atlases.txt` (named boot entry
  `atlases.txt`, lists `data/texture/atlas/atlas_blur.png` + `atlas_norm.png`) pointed
  at bogus names → menu renders near-white (mean 233 vs vanilla 45; 84.8% pixels
  differ >50). (2) Swapping the `myst` and `boy_default/head_cutoff` rows of
  `atlas_blur.txt` (text only) → darkness pass visibly moved (mean 58.97 vs 45.45;
  hot region matches the fog/boy band). Both restored to vanilla afterwards.
- Negative (informative, re-interpreted): "zeroing the boy's manifest rects → nothing
  visible" was a black-on-black confound (his L is ~8), not evidence the manifest is
  unused. A8 is still not observed doing anything.
- Not verified: that the atlases carry mips (only the sizes and tail byte say so), and
  whether a standalone boy sprite exists alongside the atlas entries.

## Gotchas
1. **Don't assert the file-start magic for the sprite header**: the wrapper starts
   with u32 9, which differs from the internal header u32 `7` at `se`. Read the
   internal header from `pathHeaderEnd` (= 16 + pathLen + 1), and read W/H at
   se+6/se+8, usedW/usedH at se+10/se+12, pixels at se+18. Pixel bytes count against
   the mip-chain sum, not `2*W*H`.
2. **Separate runs differ in menu animation timing** → whole-screen diff means
   little; use two captures of the same mod run (they agree when the change is
   real) and compare against a vanilla same-state capture.
3. **zlib `.d` entries**: replace by compressing again (repack tool does it); a
   hand-built replacement must stay byte-compatible (same length is the safe path).
4. **The atlas manifest IS the runtime rect source** — `atlas_blur.txt` /
   `atlas_norm.txt` rows (`x y w h c5 c6 "path"`, TAB-separated, CRLF) are parsed
   live. Columns 5-6 were read here as used W/H; theberrigan's `tools_Limbo.py`
   labels them pivot X/Y, and which it is wasn't checked. Edit rects in the text to
   *move* a sprite (as the myst/head swap proved), but to repaint a sprite keep its
   rect and edit its pixels in the `.pngatlas` texel data: the level-0 byte offset is
   `P + 2*(y*4096 + x)`. The boy's texels are near-black, so zeroing his L shows
   nothing; test edits on him need a visible change in L, and see Gotcha 5.
5. **Likely risk, not tested: stale atlas mips.** **Symptom:** a pixel edit to an
   atlas member doesn't show, or shows only at some sizes. **Cause (likely):** if
   the atlases are 6-level mip chains (see above), editing level 0 alone leaves
   levels 1-5 holding the old art, and a sprite drawn small or through the blur pass
   may sample those. **Fix:** write the edit into every level (downscale the edited
   level-0 region by 2 per level), as the menu title edit did for all of its mips.

## Assets
None generated with AI yet; only numpy/PIL test patterns and the L-zero title.

## Cost and time
Single session; free (local numpy/PIL, no API spend).

## Open questions
- ~~Runtime path→rect table for atlas members~~ — **RESOLVED**: it is the shipped
  `atlas_blur.txt` / `atlas_norm.txt` text manifests (live-proven above). The exe
  contains `Loading atlas texture: '%s'` + `atlases.txt`; the `.png` names in
  `atlases.txt` are resolved to the `<name>.txt` manifest and the
  `derived/pc/data/texture/atlas/<name>.pngatlas.d` texture.
- Confirm the atlases are mip chains by decoding level 1: the texels after
  atlas_blur's first 4096×4096 read as a 2048×2048 image should be a half-size copy.
  Record atlas_norm's own header W/H while there.
- Meaning of the two trailing header u16s across flag variants, and of the id-like
  byte (aa/bb nibble patterns) and where it sits in the 16-byte prefix. The high byte
  of the first tail u16 (0x0C title, 0x0B chapters/1, 0x06 atlas) looks like a mip
  count; for the sprites that would mean chains down to 1×1, one level more than the
  byte sums above.
- Whether the boy also has standalone sprite files: check the CRC32 of
  `derived/pc/data/sprites/characters/boy/boy_default/head_cutoff.png.d` against both
  pkg tables.
- Manifest columns 5-6: used W/H or pivot X/Y.
- The Steam build ID of the tested install.
- Whether the A (alpha) channel is used by any render path (fog particles?) at all.
