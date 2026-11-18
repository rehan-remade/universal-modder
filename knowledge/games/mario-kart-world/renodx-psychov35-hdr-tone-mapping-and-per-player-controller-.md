---
kind: game
title: RenoDX PsychoV35 HDR tone mapping and per-player controller remapping in the mkw-recomp static recompilation
game: Mario Kart World
games_also: []
game_version: 'Switch 2 Mario Kart World as dumped by the player, run through mkw-recomp 0.1.13 (Windows x64)'
platform: windows
engine: native
route: decomp-recomp
tools:
- mkw-recomp 0.1.13 (github.com/adriadam10/mkw-recomp) and its main branch of 2026-11-18
- Vulkan SDK 1.4.363.0 (spirv-cross, glslangValidator, spirv-val)
- llvm-mingw + SDL3 via the repo's tools/build/windeps.py, uv
- RenoDX PsychoV35 (github.com/clshortfuse/renodx, MIT)
anti_cheat: none in the recompiled runtime; online play not involved (local split-screen and offline only)
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-18'
links:
- https://github.com/adriadam10/mkw-recomp
- https://github.com/adriadam10/mkw-recomp/pull/580
- https://github.com/clshortfuse/renodx
tags:
- hdr
- renodx
- tonemapping
- spir-v
- static-recompilation
- nintendo-epd
- split-screen
- input-remapping
---
# RenoDX PsychoV35 HDR tone mapping and per-player controller remapping in the mkw-recomp static recompilation

Two runtime changes to mkw-recomp, the static recompilation of Mario Kart World (Switch 2) to Windows. The first
replaces the game's HDR tone curve with RenoDX's PsychoV35 by rewriting the game's prepared SPIR-V. The second
gives each local split-screen player their own button bindings. Both run in the real game. The HDR change was
verified by measuring nits in raw PQ swapchain captures (the vanilla peak was 723 nits, PsychoV35 reached 960-1206
on a 1200-nit display) and by same-frame split-screen A/B shots. The bindings were played by the human. The HDR
work is upstream PR #580.

## Setup
- Windows 11, NVIDIA GPU, HDR10 display (Windows reports a 1200-nit peak and 480-nit SDR white).
- mkw-recomp 0.1.13, installed by its own launcher from the player's dump. The game code is a locally generated
  `mkwgame.dll` and the runtime is `mkw.exe`. The install folder may still carry an older version in its name;
  `setup-state.json` "port" holds the real version.
- The runtime is built from source: `uv run tools/build/windeps.py`, then
  `uv run tools/build/build.py --target windows --dist --runtime-only --jobs 12`. Only `mkw.exe` is swapped; the
  game DLL stays.
- Vulkan SDK 1.4.363.0 for the offline shader tool.

## Route and why
This is decomp-recomp: the runtime is open source C, so the changes go straight into it. For HDR the
alternatives were ReShade/RenoDX add-ons (they don't apply: there is no PC build with known shader hashes, and the
recomp translates the game's SM86 shaders to SPIR-V offline). Live SPIR-V patching was another option, but
editing decompiled GLSL offline is far simpler and fully validated. The recomp already loads `<game>/spirv/<key>.spv`
by program key, so a replacement folder plus a setting is all the runtime needs.

## How the game works (what we had to learn)
**HDR pipeline** (from the runtime's own frame dump, `MKW_CTL` `dump DIR ubo`):
- The scene buffer is **linear Display-P3**. The final PQ pass's constant matrix is exactly P3→BT.2020 times the
  nits of 1.0.
- A **LUT pass** encodes scene + 4×bloom as the bits of a half float: `(half_bits & 0x7fff) * 2^-14 - 0.3125`
  maps log2(v) for v in [2^-12, 16] onto 0..1, then a scale and bias from the constant bank. It looks this up in
  a static **32³ rgba16f LUT** (two of them blended by area or depth). Its output is still scene-linear (up to 68
  in the dump), so this pass is **grading only**.
- A **final tone curve pass** (24 program variants, including big post-process uber shaders of about 4000 GLSL
  lines) multiplies by an exposure and applies a per-channel shoulder: linear up to `c[1].x`, then
  `1 - 2^(x*c[1].y + c[1].z)`. In its HDR mode (`c[7].x == 6`) it expands that by up to `c[6].x = 1.5`
  (P / (1 + (P-1)(1-s)^c[6].z), with the channels pulled together by `c[6].w`), times `c[5].w = 1/1.5`.
- So output 1.0 is 1.5× paper white. **Vanilla HDR never exceeds 1.5× paper white**: 720 nits with a
  480-nit white, regardless of the display's peak. That's why it looks flat.
- The game reads peak and paper white from nn::vi every frame, and the runtime answers from SDL. Windows gives
  the SDR content brightness slider as paper white.
- There are also 36 shaders containing the ACES/Narkowicz fit (2.51/0.03/2.43/0.59/0.14), 18 of them with an HDR
  luminance expansion. They look like the obvious target, but they were **not used** in any dumped frame.
- The constants and luma weights (0.2989/0.5866/0.1144) are identical to the Switch 2 OoT remake's (same EPD
  engine), so Longshot's PsychoV35 port fits unchanged.

**Input:** upstream had one global binding table (`input_map`) applied to every pad. Per-player tables are
`input_maps[8]`, with `MKW_P<N>_BIND_*` keys for players 2-8 (player 1 keeps the keyboard).

## Build steps
1. In the runtime, add a setting `MKW_HDR_TONEMAP`. When it's on, `prepared_load` (gfx_shader.c) loads
   `<spirv>/renodx/<key>.spv` in place of `<spirv>/<key>.spv`. The resource layout is unchanged, so the
   `.res.json` reflection still matches.
2. Write an offline tool (`tools/shaders/renodx.py` in the PR) that does the following:
   - finds candidate programs by constant words in the SPIR-V (6.0, -log2(e), the Rec.709 and Rec.601 luma
     weights);
   - runs `spirv-cross` on each to get GLSL;
   - finds the `if (M == 6.0)` HDR-mode test (M is the flushed `c[7].x` of a constant bank) and the shoulder's
     three `exp2(fma(X, A, B))` inputs;
   - maps each channel by following assignments back from the final `out.x/y/z` writes into the mode-6 block and
     then to the nearest shoulder input (spirv-cross output is SSA with uint bit-cast phis, so simple regexes on
     names fail);
   - appends `if (M == 6.0) out.rgb = PsychoV35(x_P3→709, mid grey matched to the game's expansion,
     peak = headroom) × c[5].w`;
   - compiles with `glslangValidator -V --target-env vulkan1.3` and checks with `spirv-val`. A variant that fails
     any step is left as the game's.
3. Pass the display headroom (peak / paper white) as a **specialization constant** with a high `constant_id`
   (30000). Because no pipeline specializes that id, the runtime sets it by patching the `OpSpecConstant`
   default in the module words at load (find `OpDecorate <id> SpecId 30000`, then that id's `OpSpecConstant`).
4. Add peak and paper white overrides to the HDR code (told to the game and written into the HDR metadata), plus
   menu rows: 1-nit sliders with Automatic below the lowest value.

## Verification
- **Oracle:** the runtime's control pipe (`MKW_CTL=<name>`, a Windows named pipe, written from PowerShell with
  `NamedPipeClientStream`). `screen PATH` saves the swapchain; a small added knob (`MKW_SCREEN_RAW=1`) also saves
  the raw 10-bit PQ words. Decoding PQ in numpy gives nits per pixel.
- **Same-frame A/B:** a second specialization constant, `MKW_RDX_SPLIT=<px>`, keeps the game's curve left of x.
  The title demo shows a different scene every run, so separate before/after runs were useless.
- **Results:**
  - Vanilla: max 716-723 nits in every frame.
  - PsychoV35: 960-1206 nits, with mid-tones matched and deeper shadows (RenoDX's look).
  - The HUD is unchanged.
- **Math:** the GLSL port of PsychoV35 matches RenoDX's reference path to 1.5e-6 relative error on 2000 random
  inputs.
- **Runtime checks:** `--probe-cfg` and `--selftest` pass.
- **Not verified:**
  - which of the 24 tone curve variants races use (8 converted, including the title and free-roam one; a scripted
    quick race returned to the title);
  - the PR branch rebased on upstream main builds but wasn't run (the game DLL id differs and needs a fresh
    setup);
  - per-player binds were tested by the human only.

## Gotchas
1. **The rebuilt exe refuses the game DLL ("game id mismatch").** **Cause:** RT_GAME_ID is a sha256 of generator
   flags plus raw header bytes, so a CRLF checkout (`core.autocrlf=true`) changes it. A launcher update can also
   leave a different version installed than the folder name says. **Fix:** set `core.autocrlf=false` in the repo,
   check out with LF, build on the exact installed tag, and compare `build/dist/windows/mkwgame.id` with the
   game's before swapping.
2. **build.py crashes on `/proc/meminfo` on Windows.** **Cause:** its job-count memory probe is Linux-only.
   **Fix:** pass `--jobs N`.
3. **Older tags fetch a Linux llvm-mingw on Windows; ninja fails with "not a valid Win32 application".**
   **Fix:** use a tag that has the Windows-host build commits (0.1.13 has them).
4. **The first HDR target was wrong.** I replaced the 32³ LUT lookup with PsychoV35 and midtones blew out.
   **Cause:** the LUT is grading only, and its output is unbounded scene-linear. The cap sits in the next pass.
   **Fix:** dump each pass's min/max (`images.txt`) before choosing what to replace. Frame dumps may skip copies
   ("too many copies in flight"); raising the dump's in-flight cap locally fixed that.
5. **The replacement shader ran with headroom 0.** **Cause:** pipelines are prebuilt from `pipeline-keys.bin`
   before the window exists, so the system's HDR values are still unknown. **Fix:** remember the last seen system
   peak and white in the settings file and use them at load. Changing peak or white with PsychoV35 on needs a
   restart.
6. **glslang rejects `transpose()` in a global `const mat3`.** **Fix:** write the matrix rows as columns and use
   `v * M`.
7. **Embedding a magic float to patch later doesn't work.** **Cause:** glslang folds constant expressions.
   **Fix:** use a specialization constant.
8. **Python heredocs through Git Bash mangled `\b` and `\n` in regex and edit scripts** (they turned into
   backspace characters and real newlines). **Fix:** make exact edits with a file editor, or write the script to
   a file first.
9. **The i18n catalog updater writes CRLF on Windows**, which turns a small change into a 54k-line diff.
   **Fix:** strip the `\r` before committing.
10. **Windows locks a running exe.** **Fix:** rename `mkw.exe` to `.old` and copy the new one in; it takes effect
    on the next launch.

## Assets
None. The screenshots for the PR are generated from raw PQ captures: an "HDR range" view with the display's
peak as white, and a log-scale nits false-colour map.

## Cost and time
About one long session of agent work, including recon, about 15 game runs and the PR.

## Open questions
- Convert the remaining tone curve variants (the uint-SSA forms where a shoulder input is made in a nested block
  or reached only through deeper phis), and check which ones races load.
- Hook `renodx.py` into the recomp's setup so players don't need the Vulkan SDK.
- Feed the headroom live (per frame) instead of at load, so peak and paper white changes apply without a restart.
- Motion vectors for DLSS: upstream issue #316. MKW renders none, so they'd have to come from camera
  reprojection plus depth.
