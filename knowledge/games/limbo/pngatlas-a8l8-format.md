---
kind: game
title: Limbo A8L8 texture format, standalone sprites, and a live-verified menu-title mod
game: Limbo
games_also: []
game_version: 'Steam (appid 48000), Steam build ID 18220724, limbo.exe 5,453,312 bytes'
platform: windows
engine: native
route: data
tools: ["python+struct", "numpy", "pillow", "hgrep on limbo.exe", "um win"]
anti_cheat: "none (single-player; SteamStub DRM wrapper on the exe, which this route never touches)"
status: working
agents:
- 'OpenCode (big-pickle)'
humans: []
date: '2026-10-10'
links:
- 'https://github.com/hukultan/limbo-tools'
- 'https://github.com/gibbed/Gibbed.Limbo'
- 'https://github.com/theberrigan/apps/blob/master/projects/21_game-tools/tools_Limbo.py'
tags: [textures, atlases, pngatlas, a8l8, d3d9, asset-only, live-verified]
---

# Limbo A8L8 texture format, standalone sprites, live-verified menu-title mod

> Limbo stores sprite art as A8L8 (16-bit luminance+alpha) textures. Two layouts:
> **standalone sprite files** (`data/sprites/**/*.png`, `.png_a`, `.pngblur`) carry
> their own **render dims and a full mip chain**, and **atlases**
> (`data/texture/atlas/*.pngatlas`) **are themselves 6-level mip chains** (base
> 4096-wide level 0, then five halvings; confirmed by decoding level 1 as a
> 4096/2=2048-wide image). Runtime semantics (user-verified in the live game):
> the **L (luma, low byte) channel drives visibility** on the darkness/blur pass
> (L=0 → invisible), the **A channel is read by the shipped pixel shaders** (it feeds
> the output alpha, see Channel semantics below) though a live whole-sheet A=255 atlas
> edit looked ≈ vanilla; the **UI/menu is drawn
> from the standalone sprite files, not the atlas**; the atlas blob IS consumed
> (whole-sheet edits visually wreck the world), and the atlas **manifest
> `data/texture/atlas/atlas_blur.txt` is most likely the live path→rect table**
> (`atlases.txt`, a named boot entry listing the two `.png` atlas resources, is read
> at runtime — bogus names render the menu near-white — but a live swap of two rows
> was inconclusive). A byte-exact repack
> route ( `repack_limbo.py --entry <path.d> --in <edited>` → swap
> `limbo_boot.pkg` → launch) was proven: zeroing the L plane of the menu title
> sprite removed the LIMBO title, and a bulk extract → human repaint → pack loop put
> edited art for a menu sprite and two atlas members into the live game.

## Setup
- Steam install of Limbo (appid 48000) at `...\Steam\steamapps\common\Limbo`.
- `limbo_boot.pkg` / `limbo_runtime.pkg` unpackable with a Python port of
  [Gibbed.Limbo](https://github.com/gibbed/Gibbed.Limbo). Filelists:
  `bin\projects\LIMBO\files\limbo_boot.filelist` / `limbo_runtime.filelist` (they name
  1,088 of 1,410 boot entries and 222 of 455 runtime entries; NOTE the installed boot
  pkg for build 18220724 actually holds **1,600 entries** of which 1,091 are named —
  the filelist's own `1,088/1,410` head count is authored for an older build; the pkg
  hash is CRC32 of the lowercase '/' path).
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
  The third u32 is the **file-type/'atlas variant' flag, not a variant id byte**: 1 =
  plain sprite, 9 = `.png_a` / `.pngblur` (blur pass), 17 = `.pngatlas` (ATLAS), i.e.
  bit 0 always set, bit 3 (8) for blur and bit 4 (16) for atlases; theberrigan's script
  labels those bits "black only" and "b/w atlas". The exe holds the matching name
  tokens `'ATLAS'` and `'BLUR'`. The
  fourth u32 **is not a path CRC** — brute-forced CRC32 with multiple seeds/xors over
  `path`, `derived/pc/path`, `path.d`, lower/upper all mismatch. Across 135 files it
  is either 0, `0x12345678`, `0x00FF00FF`, or (33 files) a 4-byte slice of what looks
  like an authoring-era absolute path `c:/derived/pc/data/sprites/...` (e.g. `c:/d`,
  `/der`, `it00`), so it is stale debug/authoring cruft the loader never validates.
  Treat it as opaque; never parse it.
  Then the **internal texture header, 18 bytes**, at 17 + pathLen:
  ```
  u32 = 7 ; u16 ; u16 W ; u16 H ; u16 usedW ; u16 usedH ; u16 ; u16
  pixel start P = 17 + pathLen + 18 ; texels run to exact EOF
  ```
  `unk6` (the u16 after the 7) is **0 in 139 of 142 containers — every plain sprite
  (137) and both atlases**; it is nonzero in **exactly the 3 BLUR textures** and only
  there: `edges/wood.pngblur` = `0x3333`, `props/rope/tile_cable_01.pngblur_a` =
  `0x0C0C`, `text/menu/uk/c_id#04.pngblur_a` = `0xC8C8` (the exact set theberrigan's
  script asserts, `unk6 in [0, 3084, 13107, 51400]`). Each value has **high byte ==
  low byte** (`0x0C/0x33/0xC8`), i.e. a byte duplicated into a u16 — consistent with a
  normalized 0..1 factor (12/51/200 ÷ 255 ≈ 0.05/0.20/0.78). So it is a **per-texture
  parameter carried only by BLUR ("black only") textures**, most plausibly a blur
  strength/opacity authored alongside them. Whether the runtime reads it is unknown;
  nothing here depends on it. The first trailing u16 has low byte 2 and a **high byte
  that counts mip levels**: title `0x0C02` (W=2048 → 12), chapters/1 `0x0B02`
  (W=1024 → 11), metal_heavy 512-wide `0x0A02` (→ 10), atlases `0x0602` (6). For the
  sprites that's log2(W)+1, the length of a full chain down to 1×1, but **the files
  store fewer levels**: the stored chain stops when the short side reaches 1 (the
  title's and chapters/1's texel data end at 2×1, 11 and 10 levels, see the sums
  below). For the atlases it equals the 6 stored levels, so a reader has to treat the
  two kinds differently. The
  second trailing u16 is `0x0A01` for sprites / `0x0A11` for atlases — its low nibble
  repeats the file-type flag (1 vs 17).
  Example (menu title, pathLen 38): W=2048 H=1024 usedW=1280 usedH=720,
  tail u16s = [0x0C02, 0x0A01]. chapters/1.png (1024×512): tail [0x0B02, 0x0A01].
  atlas_blur: W=4096 H=4096 used=4064×3984 tail [0x0602, 0x0A11].
- **Texel = D3DFMT_A8L8**: LE u16, low byte = L (luma), high byte = A (alpha).
  Confirmed by exe string `only 8A8L format supported`. White on screen ⟺ high L.
- **Standalone sprites = mip chain, no packing**:
  pixel bytes = 2 × (W*H + (W/2)*(H/2) + … + 2*1). Title: 2048×1024 chain =
  2,796,202 texels = 5,592,404 bytes = file−(P) exactly. chapters/1: 1024×512
  chain = 699,050 texels = 1,398,100 bytes = exactly.
- **W/H ARE stored in the header** (at `se+6`/`se+8`, for sprites and atlases
  alike), so dimensions need no guessing; and the mip levels are **2×2 floor
  averages of the L and A bytes taken independently** (a PIL/BOXCAR resize gives
  ~46% mismatched mip bytes; the integer floor average gives 0). Re-encoding a
  decoded level 0 and regenerating the chain by that rule reproduces the shipped
  file byte-exact on **140/140 standalone sprites** — so editing level 0 and
  regenerating mips is a lossless no-op when nothing is changed.
- **Atlas blob = 6-level mip chain, CONFIRMED by decoding level 1**:
  - `atlas_blur.pngatlas`: header W=4096 H=4096 usedW=4064 usedH=3984; texel data =
    22,364,160 texels = 4096² + 2048² + 1024² + 512² + 256² + 128² exactly. Reading
    the bytes after the first 4096² as a 2048×2048 image yields a half-size copy of
    level 0 (corr 0.999999 vs a 2×2 box downsample) — this is a real mip chain, not
    a tall 4096×5460 sheet.
  - `atlas_norm.pngatlas`: own header **W/H = 4096 × 1024** (a 4×1 sheet, resolved —
    earlier the base was only guessed); usedW/usedH = 4064/720. Texel data = 5,591,040
    = 6-level chain of the 4096×1024 base (4096·1024 + 2048·512 + … + 128·32). Level
    1 (2048×512) is a half-size copy (corr 0.999998).
  - theberrigan's `parseSprite` also reads a 4096×4096 atlas as halving mip levels.
  - The member check below decodes level 0 at width 4096, which holds either way.
  - **Gotcha consequence:** editing level 0 alone leaves levels 1-5 holding old art
    (see Gotcha 5).
- **Channel semantics (live + shader)**: L drives a darkness/luminance pass.
  Whole-sheet edits prove the atlas is sampled (every texel 0xFFFF →
  "blocky-blobby, mostly black"); every-texel A=255 ≈ vanilla; every-texel L=255 →
  title screen pure black. **But A is not dead**: the shader sources shipped in the
  pkgs read the texel's alpha into the output alpha. `renderobject.fx` samples the
  texture's L and A together, scales them by the diffuse colour and writes the scaled
  A to the output alpha; in `fixedfunction.fx`, `FixedFunction3DColor[Specular]UVPS`
  multiply the vertex alpha by the texel alpha, `FixedFunction3DNUVPS` multiplies it
  by the texture factor's alpha, and `FixedFunctionOverDrawPS` passes it through;
  `watereffect.ps` uses the texel alpha as its alpha. So A is *used* by render paths
  (it feeds the alpha blend); the earlier "A effectively ignored" was an
  over-generalization from one whole-sheet A=255 test, whose pass simply didn't show
  it. Alpha is real; don't discard it when editing (see Gotcha 6).
- **UI/menu sprites are separate files, read at runtime**: zeroing L across all the
  menu title sprite's mips removed the LIMBO logo from the live main menu; the rest
  of the menu unchanged. The exe holds the strings `Loading atlas texture: '%s'`,
  `sprites/chapters/`, `sprites/text/`, `Atlases not found`/`Atlas not found [%s]`,
  `'ATLAS'`, `'BLUR'`, and `atlases.txt` — but no hardcoded `atlas_blur.txt` (the
  manifest path is derived from the `.png` name at runtime). `atlases.txt` (a named
  boot pkg entry) is just a 2-line list of `"data/texture/atlas/atlas_blur.png"` /
  `"data/texture/atlas/atlas_norm.png"` and IS read live: pointing it at bogus
  names rendered the menu near-white (mean 233 vs vanilla 45).
- **Boy / characters = atlas-only, CONFIRMED (no standalone sprite files)**. CRC32 of
  `derived/pc/data/sprites/characters/boy/...` variants for all 11 manifest boy
  members × 6 extensions (`.png` `.png.d` `.png_a` `.pngblur` …; 66 combos incl. the
  exact `head_cutoff.png.d`) matches **no entry in either the boot or the runtime pkg
  hash table**, and no pkg blob's internal wrapper path starts with
  `data/sprites/characters/boy/` in either pkg (the boot pkg has 84 blobs whose blob
  *content* mentions "boy", but all are cutscene scripts / ragdoll volumes). The boy
  exists only as **337 atlas manifest rects**; scenes/skeleton scripts reference those
  rects by path string.
- **The manifest is most likely the runtime rect source, but no live test has shown a
  row edit moving a sprite.** For it: `atlases.txt` is read live and names the two
  `.png` atlas resources, the exe has `Loading atlas texture: '%s'` but no hardcoded
  `atlas_blur.txt` (so the `.txt` path is derived from those names), and the rows
  match the atlas texels (42/42 members, see Verification). Against a clean answer:
  swapping the `myst` and `boy_default/head_cutoff` rows (texture untouched) produced
  only animation-noise pixel diffs in a clean single instance and no crash (see the
  retraction under Verification). Local pixel edits inside the boy's rects also
  showed nothing on screen — for zeroing his L that's a **black-on-black confound**
  (his texels are near-black); whites/A never visibly changed either path. A row swap
  between two visibly different members that are both on screen in a paused scene
  would settle it.
- Scenes / `skeleton.branch` reference sprites by path string plus per-instance
  floats (world size/basis), never by rect: e.g.
  `data/sprites/characters/boy/boy_default/head_cutoff.png` and
  `.../children/boy_skinny_01/l_thigh.png`.

## Build steps
The session's scripts are published at <https://github.com/hukultan/limbo-tools>
(MIT): `unpack_limbo.py`, `repack_limbo.py`, `limbo_tex.py` (inspect / extract /
pack / patch / round-trip), `limbo_workflow.py` (bulk extract/pack loop),
`make_titlezero.py`, `shot_diff.py`.
1. Unpack: `python tools/unpack_limbo.py pristine_pkg <filelist_dir> lab\boot`
   (boot and runtime). `.d` stored entries come out with the `.d` stripped.
2. Inspect: `uv run --quiet --with numpy python tools/limbo_tex.py inspect FILE`.
3. Hand-editing loop (decode → edit → encode → repack):
   ```
   # dump every sprite + atlas member to clean RGBA PNGs (L as gray, A as alpha)
   python tools/limbo_tex.py extract SPRITE.png --out edit.png            # dims from header
   python tools/limbo_tex.py extract ATLAS.pngatlas --rect 804,2345,215,206 --out head.png
   # ... human edits edit.png / head.png in any image editor ...
   python tools/limbo_tex.py pack  SPRITE.png  --out NEW --in edit.png     # rebuild + full mip chain
   python tools/limbo_tex.py patch ATLAS.pngatlas --out NEW --in head.png \
       --rect 804,2345,215,206 --mips                                       # edit rect in all 6 mips
   ```
   `pack`/`patch` keep the header verbatim and regenerate every mip level, so the
   file byte length is unchanged (safe for the `.d` deflate). A single old path:
   `tools/make_titlezero.py` zeroes the L byte of every texel in every mip of the
   menu title.
   For editing **many** assets at once, `limbo_workflow.py` wraps the same engine:
   `extract --boot lab\boot --out assets` dumps every standalone sprite and atlas
   member to RGBA PNGs (138 + 391) plus a `MANIFEST.json` of each PNG's source
   texture/rect and SHA-256; `pack --boot ... --assets ... --pkg-in ...
   --filelists ... --pkg-out ...` rebuilds **only** the PNGs that changed and
   repacks (untouched pkg entries copied verbatim).
4. Repack and swap:
   ```
   uv run python tools/repack_limbo.py pristine\Limbo\limbo_boot.pkg ^
       tools\Gibbed.Limbo\bin\projects\LIMBO\files ^
       lab\renders\limbo_boot_TAG.pkg ^
       --entry "derived/pc/data/sprites/text/menu/limbo title.png.d" --in NEWFILE
   Copy-Item lab\renders\limbo_boot_TAG.pkg "<install>\limbo_boot.pkg" -Force
   ```
   (Entry names are the boot-relative path + `.d`; a texture entry is deflated.)
5. Kill any running game by exact PID (`um win kill PID`), launch via Steam,
   screenshot (`um win shot out.png --exe limbo`), diff vs a vanilla capture with
   `tools/shot_diff.py` / numpy, verify with the human.
6. Restore: copy backed-up boot+runtime+settings.txt back and delete
   `<install>\derived`.

## Verification
- **Byte-exact round trip: 140/140 sprite files** parse → re-emit → identical SHA.
- **Extract→pack identity: 140/140 standalone sprites.** Decode level 0 to RGBA,
  re-encode, regenerate the mip chain by integer floor averaging → byte-identical
  to the shipped file. So the edit round trip is lossless when nothing changes.
- **Surgical repack (verified):** editing 2 PNGs (one sprite, one atlas member)
  through the extract/pack loop changed exactly those 2 pkg entries and left the
  other 1,593 byte-identical.
- **Live proof (multi-asset human-edit loop, user-confirmed in the live game):** the
  bulk `limbo_workflow.py` loop was driven end to end. `extract` produced 138
  standalone sprites + 391 atlas members as editable RGBA PNGs; a human repainted
  three of them — `derived/pc/data/sprites/text/menu/howtoplay_pc.png` (a full
  2048×1024 menu sprite), plus the `head.png` rects of `characters/sister` and
  `animation/boy/bones` inside `atlas_blur`. `pack` rebuilt exactly those textures
  (2 pkg entries changed — the sprite and the shared atlas — the other 1,593
  byte-identical) into a 20,743,398-byte `limbo_boot.pkg`, verified so the user's
  red channel became L (byte-exact) and every mip level's change stayed confined to
  the union of the edited rects. Swapped over the live Steam install (windowed,
  backed up first), the human confirmed **the edited art renders in-game**. This
  exercises the whole standalone-sprite path *and* the `patch --mips` atlas path on
  the real characters. Reverted to vanilla afterwards (SHA-verified).
- **42/42 atlas members** decode pixel-identical to their standalone file (Jaccard
  1.0) at sheet width 4096 (level 0).
- **Repack identity**: rebuild with zero replacements is byte-identical to input.
- **Live proof (standalone/UI)**: with the title L-plane zeroed, two menu screenshots
  agree (mean 14.4 vs vanilla 25.7) and the diff is confined to the title band
  (x184–828, y116–466, centroid 538,255, max diff 255); the human confirmed the title
  is gone in-game. Reverted to vanilla afterwards (SHA-verified).
- **Live proof (atlas/manifest IS read)**: `atlases.txt` (named boot entry
  `atlases.txt`, lists `data/texture/atlas/atlas_blur.png` + `atlas_norm.png`) pointed
  at bogus names → menu renders near-white (mean 233 vs vanilla 45; 84.8% pixels
  differ >50). Restored to vanilla afterwards.
- **Retracted (an earlier version of this note had it wrong)**: swapping the `myst`
  and `boy_default/head_cutoff` rows of `atlas_blur.txt` was first reported as moving
  the darkness pass (menu mean 58.97 vs 45.45). A clean, controlled single-instance
  re-run reached the menu fine with no crash (mean 26.92 vs ~26.6; pixel diffs were
  animation noise only). The 58.97 figure came from a botched comparison — a second
  Steam launch captured mid title-fade, not a real rendering change. A cutscene-skip
  (S) was used for correct states. Treat rect-swap claims as needing the same clean
  single-instance protocol. So a live row edit moving a sprite is still unshown.
- Negative (informative, re-interpreted): "zeroing the boy's manifest rects → nothing
  visible" was a black-on-black confound (his L is ~8), not evidence the manifest is
  unused. No A-only edit has visibly changed anything yet, though the shaders read A.
- Verified this pass: atlases are real 6-level mip chains (level-1 decodes as a
  half-size copy, corr 0.999); atlas_norm's own header is 4096×1024; the first tail
  u16's high byte counts mip levels (12/11/10 sprites, a full chain to 1×1; 6 atlases);
  the 4th prefix u32 is authoring cruft, not a CRC; manifest cols 5-6 are
  offset/pivot, not used dims (see Gotcha 4); the boy has **no** standalone sprites
  (CRC32 absent from both pkg tables, and no blob's internal path is under his
  folder); Steam build ID 18220724.
- Not verified: that editing a manifest row moves a sprite in game, and whether the
  runtime reads `unk6`.

## Gotchas
1. **Don't assert the file-start magic for the sprite header**: the wrapper starts
   with u32 9, which differs from the internal header u32 `7` at `se`. Read the
   internal header from `pathHeaderEnd` (= 16 + pathLen + 1), and read W/H at
   se+6/se+8, usedW/usedH at se+10/se+12, pixels at se+18. Pixel bytes count against
   the mip-chain sum, not `2*W*H`.
2. **Separate runs differ in menu animation timing** → whole-screen diff means
   little; use two captures of the same mod run (they agree when the change is
   real) and compare against a vanilla same-state capture. **Capture while the game
   is paused, not during the title/cutscene transition** — `um win shot --hwnd <id>`
   (or `--exe limbo`) captures the game window even when a Steam overlay/splash is
   up; do a fresh vanilla capture for every modified-state comparison, never reuse a prior run's.
3. **zlib `.d` entries**: replace by compressing again (repack tool does it); a
   hand-built replacement must stay byte-compatible (same length is the safe path).
4. **The atlas manifest is most likely the runtime rect source** — `atlas_blur.txt` /
   `atlas_norm.txt` rows (`x y w h offX offY "path"`, TAB-separated, CRLF; see How the
   game works for the evidence and the inconclusive swap). **Columns 5-6 =
   offset/pivot (X/Y) — resolved, matching theberrigan's `tools_Limbo.py` labels —
   NOT used W/H.** Proof: for the 11 atlas members that ALSO exist as standalone
   sprite files, manifest cols 3-4 (`w h`) equal each standalone's **usedW/usedH**
   exactly (all 11; e.g. metal_heavy manifest `512 9` = standalone
   usedW=512 usedH=9), so cols 3-4 already carry the used dims and cols 5-6 must be
   the pivot (e.g. metal_heavy `32 27`). Editing a row's rect should *move* a sprite,
   but that hasn't been shown live yet. To repaint a sprite, keep its rect and edit
   its pixels in the `.pngatlas` texel data: the level-0 byte offset is
   `P + 2*(y*4096 + x)`. The boy's texels are near-black, so zeroing his L shows
   nothing; test edits on him need a visible change in L, and see Gotcha 5.
5. **Stale atlas mips.** **Symptom:** a pixel edit to an atlas member doesn't show,
   or shows only at some sizes. **Cause:** the atlases are 6-level mip chains
   (verified by decoding level 1), so editing level 0 alone leaves levels 1-5 holding
   the old art, and a sprite drawn small or through the blur pass may sample those.
   **Fix:** `limbo_tex.py patch ... --rect x,y,w,h --mips` writes the downscaled edit
   into every level (verified confined to the scaled rect at all 6 levels of
   `atlas_blur`).
6. **Editing channel:** the tools decode L into `R=G=B` of the output PNG, so when
   packing, the **PNG's R channel becomes L (luminance)** and its **A becomes A**;
   G/B are ignored. LIMBO renders grayscale, so a coloured edit shows up as its
   **red channel as gray** — paint in grays (or knowingly accept red-as-gray)
   rather than expecting the literal RGB colour to survive.

## Assets
None generated with AI yet; only numpy/PIL test patterns and the L-zero title.

## Cost and time
Single session; free (local numpy/PIL, no API spend).

## Open questions
- Whether editing a manifest row moves a sprite in game. The one row swap tried was
  inconclusive; swap two visibly different members that are both on screen in a
  paused scene.
- `unk6` (`0x0C0C/0x3333/0xC8C8`, only in the 3 BLUR textures): a normalized blur or
  black-only parameter, or authored metadata the runtime never reads?
- Any *fog-particle-specific* alpha use: the shaders that read `texel.a` are the
  object/fixed-function/water ones; no particle shader was singled out.
