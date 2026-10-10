---
kind: game
title: Limbo A8L8 texture format, standalone sprites, and a live-verified menu-title mod
game: Limbo
games_also: []
game_version: 'Steam (appid 48000), Steam build ID 18220724, limbo.exe 5,453,312 bytes'
platform: windows
engine: native
route: data
tools: ["python+struct", "numpy", "pillow", "hgrep on limbo.exe", "Ghidra (decompile of a memory-dumped unpacked exe)", "um win"]
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
> (L=0 → invisible), the **A channel is read by the pixel shaders** (it becomes the
> output alpha — see the Shader note below) though a live whole-sheet A=255 atlas edit
> looked ≈ vanilla; the **UI/menu is drawn
> from the standalone sprite files, not the atlas**; the atlas blob IS consumed
> (whole-sheet edits visually wreck the world), and the atlas **manifest
> `data/texture/atlas/atlas_blur.txt` IS the live path→rect table (the loader reads
> it at boot and materializes each row into a rect map — decompile-confirmed;
> `atlases.txt`, a named boot entry listing the two `.png` atlas resources, is also
> read at runtime — bogus names render the menu near-white). A byte-exact repack
> route ( `repack_limbo.py --entry <path.d> --in <edited>` → swap
> `limbo_boot.pkg` → launch) was proven: zeroing the L plane of the menu title
> sprite removed the LIMBO title.

## Setup
- Steam install of Limbo (appid 48000) at `...\Steam\steamapps\common\Limbo`.
- The SteamStub-packed `limbo.exe` (5,453,312 bytes on disk) was analyzed by letting
  the game run once, finding its base in the process snapshot, dumping the mapped PE
  (`lab\renders\limbo_unpacked.exe`, 5,763,584 bytes) with python, and loading that
  into a Ghidra project named `limbo_proj` in `lab\ghidra\`. All function addresses
  below are from that unpacked dump; the packed exe still hosts the strings listed
  further down.
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
  plain sprite, 9 = `.png_a` / `.pngblur` (blur pass), 17 = `.pngatlas` (ATLAS). The
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
  strength/opacity authored alongside them. No runtime reader was located (the header
  is parsed through a vtable-delegated resource decoder), so until proven it is
  authored metadata the runtime ignores — the loader keys BLUR behaviour off the
  *name*, not this field. The first trailing u16 (**high byte = mip
  count**, low byte = 2): title `0x0C02` (W=2048 → 12 mips), chapters/1 `0x0B02`
  (W=1024 → 11), metal_heavy 512-wide `0x0A02` (→ 10), atlases `0x0602` (6). The
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
  title screen pure black. **But A is not dead**: the shipped pixel shaders read the
  alpha channel into the output alpha — `renderobject.fx` `pixel.xw =
  tex2Dbias(TextureSampler, uv0).xw * diffuse.xy;` then `pixel = float4(pixel.r,
  pixel.r * diffuse.a, 0, pixel.a);` (output.A = texel.A · diffuse.y); the fixed-
  function shaders `color.a *= texel.a;` (`FixedFunction3DColor[Specular]UVPS`),
  `return float4(16.0/255.0, 0, 0, texel.a);` (`FixedFunctionOverDrawPS`), and
  `float alpha = texel.a * textureFactor.a;` (`FixedFunction3DNUVPS`); `watereffect.ps`
  `alpha = tex.a;`. So A is *used* by render paths (it feeds the alpha blend); the
  earlier "A effectively ignored" was an over-generalization from one whole-sheet
  A=255 test, whose pass simply didn't show it. Alpha is real; don't discard it when
  editing (see Gotcha 6).
- **UI/menu sprites are separate files, read at runtime**: zeroing L across all the
  menu title sprite's mips removed the LIMBO logo from the live main menu; the rest
  of the menu unchanged. The exe holds the strings `Loading atlas texture: '%s'`,
  `sprites/chapters/`, `sprites/text/`, `Atlases not found`/`Atlas not found [%s]`,
  `'ATLAS'`, `'BLUR'`, and `atlases.txt` — but no hardcoded `atlas_blur.txt` (the
  manifest path is derived from the `.png` name at runtime). `atlases.txt` (a named
  boot pkg entry) is just a 2-line list of `"data/texture/atlas/atlas_blur.png"` /
  `"data/texture/atlas/atlas_norm.png"` and IS read live: pointing it at bogus
  names rendered the menu near-white (mean 233 vs vanilla 45).
- **Atlas loader, decompiled** (Ghidra over a memory-dumped unpacked exe):
  `FUN_004e7dd0` (init) loads `plugins/png.dll`, creates a texture object, then calls
  `FUN_004e7c60("atlases.txt")` which reads that 2-line list and for each line calls
  `FUN_004e5550(line)` — the atlas loader: it opens `<base>.txt`, parses each manifest
  row as **six ints `(x y w h offX offY)` + a path** (via a tokenizer at
  `FUN_00737470`; ints land at `rect+0x1c..0x30` from `FUN_004e1eb0`), logs
  `Loading atlas texture: '%s'`, and resolves the texture via `FUN_004e40c0(name,
  "ATLAS")` → cache lookup or `FUN_004e3160` (ctor), which sets a flag word to 0x11
  (bits 0+4) when the name/token contains `"ATLAS"` (`DAT_007cc564`) and ORs bit3 (8)
  when it contains `"BLUR"` (`DAT_007cc56c`) — a substring scan via `FUN_00735020`.
  So the exe's flags map exactly onto the on-disk third u32: 1 = plain, 9 = `1|8`
  (black-only/blur), 17 = `1|16` (`0x11`, b/w atlas); a suffix selector
  (`FUN_005ea9b0`) then picks `_A` / `BLUR_A` / `""` from bits of that flag word. The
  generic texture loader `FUN_004d6fd0` checks "Atlas not found [%s]", rejects size 0,
  and treats the `'XXXX'` (0x58585858) sentinel as invalid — the root reason a rect
  swap of near-black boy texels changed nothing visible.
- **Boy / characters = atlas-only, CONFIRMED (no standalone sprite files)**. CRC32 of
  `derived/pc/data/sprites/characters/boy/...` variants for all 11 manifest boy
  members × 6 extensions (`.png` `.png.d` `.png_a` `.pngblur` …; 66 combos incl. the
  exact `head_cutoff.png.d`) matches **no entry in either the boot or the runtime pkg
  hash table**, and no pkg blob's internal wrapper path starts with
  `data/sprites/characters/boy/` in either pkg (the boot pkg has 84 blobs whose blob
  *content* mentions "boy", but all are cutscene scripts / ragdoll volumes). The boy
  exists only as **337 atlas manifest rects**; scenes/skeleton scripts reference those
  rects by path string.
- **Live proof the manifest is the runtime rect source (decompiled + repack)**:
  the boot-time loader (see above) materializes each manifest row into a rect map
  keyed by path — so a repack that keeps the same paths/rects (e.g. `metal_heavy`
  used-dims) lands pixel-exact; the earlier `myst`/`boy_default/head_cutoff` rect-row
  swap (texture untouched, both near-black L≈8/205) produced only animation-noise
  pixel diffs in a clean single instance and no crash, consistent with the loader (the
  swap swapped two *loaded* rects; whatever the renderer does with the boy's texels
  stays dominated by the near-black art, see the `'XXXX'` sentinel note above). Local
  pixel edits inside the boy's rects also showed nothing on screen — for zeroing his
  L that's a **black-on-black confound** (his texels are near-black); whites/A never
  visibly changed either path.
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
- **Retracted (was in the first draft, wrong)**: swapping the `myst` and
  `boy_default/head_cutoff` rows of `atlas_blur.txt` was first reported as moving the
  darkness pass (menu mean 58.97 vs 45.45). A clean, controlled single-instance
  re-run reached the menu fine with no crash (mean 26.92 vs ~26.6; pixel diffs were
  animation noise only). The 58.97 figure came from a botched comparison — a second
  Steam launch captured mid title-fade, not a real rendering change. A cutscene-skip
  (S) was used for correct states. Treat rect-swap claims as needing the same clean
  single-instance protocol.
- Negative (informative, re-interpreted): "zeroing the boy's manifest rects → nothing
  visible" was a black-on-black confound (his L is ~8), not evidence the manifest is
  unused. A8 is still not observed doing anything.
- Verified this pass: atlases are real 6-level mip chains (level-1 decodes as a
  half-size copy, corr 0.999); atlas_norm's own header is 4096×1024; the first tail
  u16's high byte is a mip count (12/11/10 sprites, 6 atlases); the 4th prefix u32 is
  authoring cruft, not a CRC; manifest cols 5-6 are offset/pivot, not used dims (see
  Gotcha 4); the boy has **no** standalone sprites (CRC32 absent from both pkg
  tables); Steam build ID 18220724.

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
   (or `--exe limbo`) grabs retargeted even when a Steam overlay/splash is up; do a
   fresh vanilla capture for every modified-state comparison, never reuse a prior run's.
3. **zlib `.d` entries**: replace by compressing again (repack tool does it); a
   hand-built replacement must stay byte-compatible (same length is the safe path).
4. **The atlas manifest IS the runtime rect source** — `atlas_blur.txt` /
   `atlas_norm.txt` rows (`x y w h offX offY "path"`, TAB-separated, CRLF) are parsed
   live. **Columns 5-6 = offset/pivot (X/Y) — resolved, matching theberrigan's
   `tools_Limbo.py` labels — NOT used W/H.** Proof: for the 11 atlas members that ALSO
   exist as standalone sprite files, manifest cols 3-4 (`w h`) equal each standalone's
   **usedW/usedH** exactly (all 11; e.g. metal_heavy manifest `512 9` = standalone
   usedW=512 usedH=9), so cols 3-4 already carry the used dims and cols 5-6 must be
   the pivot (e.g. metal_heavy `32 27`). Edit rects in the text to *move* a sprite
   (the loader applies each row to a rect map), but to repaint a sprite keep its
   rect and edit its pixels in the `.pngatlas` texel data: the level-0 byte offset
   is `P + 2*(y*4096 + x)`. The boy's texels are near-black, so zeroing his L shows
   nothing; test edits on him need a visible change in L, and see Gotcha 5.
5. **Stale atlas mips (now confirmed real structure, fix applies).** **Symptom:** a
   pixel edit to an atlas member doesn't show, or shows only at some sizes. **Cause:**
   the atlases are 6-level mip chains (verified by decoding level 1), so editing level
   0 alone leaves levels 1-5 holding the old art, and a sprite drawn small or through
   the blur pass may sample those. **Fix:** `limbo_tex.py patch ... --rect x,y,w,h
   --mips` writes the downscaled edit into every level (verified confined to the
   scaled rect at all 6 levels of `atlas_blur`).
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
- ~~Runtime path→rect table for atlas members~~ — **RESOLVED**: it is the shipped
  `atlas_blur.txt` / `atlas_norm.txt` text manifests (live-proven above). The exe
  contains `Loading atlas texture: '%s'` + `atlases.txt`; the `.png` names in
  `atlases.txt` are resolved to the `<name>.txt` manifest and the
  `derived/pc/data/texture/atlas/<name>.pngatlas.d` texture.
- ~~Are the atlases mip chains?~~ — **RESOLVED**: yes, 6-level chains (level-1 decodes
  as a 2×2-box half-size copy; corr 0.999). atlas_norm header W/H = 4096×1024.
- ~~Tail u16s / id-like bytes in the 16-byte prefix~~ — **resolved earlier**: flags live
  in the third prefix u32 (1/9/17); first tail u16 high byte is a mip count (12/11/10
  sprites, 6 atlases); the 4th prefix u32 is authoring cruft, not a path CRC.
- ~~Low-byte meaning of the internal header's second u16 (`unk6`: `0x0C0C/0x3333/0xC8C8`)~~ —
  **partly resolved here**: `unk6` is nonzero in **only the 3 BLUR ("black only")
  textures** and is 0 in all 137 plain sprites + 2 atlases; each value is a **byte
  duplicated into a u16** (`0x0C/0x33/0xC8`) → a plausible normalized 0..1 blur/black
  parameter. Whether the runtime *reads* it is still unconfirmed (no reader found; the
  header is parsed via a vtable-delegated resource decoder). Best guess: authored blur
  metadata the runtime ignores.
- ~~Whether the A (alpha) channel is used by any render path~~ — **RESOLVED**: yes. The
  pixel shaders read alpha into the output alpha (`renderobject.fx` output.A = texel.A;
  `fixedfunction.fx` `color.a *= texel.a` / `texel.a * textureFactor.a` / OverDrawPS
  returns `texel.a`; `watereffect.ps` `alpha = tex.a`). See the Channel-semantics bullet.
- ~~Does the boy have standalone sprite files?~~ — **RESOLVED**: no. CRC32 of all
  `data/sprites/characters/boy/**` combos is absent from both pkg hash tables; the
  boy exists only as atlas manifest rects (337 entries).
- ~~Manifest columns 5-6: used W/H or pivot X/Y~~ — **RESOLVED**: offset/pivot, via
  the 11 members that also exist standalone (cols 3-4 equal standalone usedW/usedH, so
  cols 5-6 are the anchor).
- ~~Steam build ID~~ — **RESOLVED**: 18220724.
- Any *fog-particle-specific* alpha use: the shaders that read `texel.a` are the
  object/fixed-function/water ones; no particle shader was singled out.
