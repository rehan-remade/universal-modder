---
kind: game
title: 'Porting ASBR characters into Storm 4: both games'' CPK payloads are encrypted'
game: 'Naruto Shippuden: Ultimate Ninja Storm 4'
games_also:
- 'JoJo''s Bizarre Adventure: All-Star Battle R'
game_version: Steam build 5376895 (steam 349040); ASBR Steam build 13123765 (steam 1372110)
platform: windows
engine: native
route: other
tools:
- own read-only CRI CPK reader (Python, about 170 lines)
anti_cheat: none in Storm 4; EasyAntiCheat in ASBR (ASBR was never launched, only its files read)
status: abandoned
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-04'
links: []
tags:
- cyberconnect2
- cri-cpk
- xfbin
- crossover
- encrypted-archives
---
# Porting ASBR characters into Storm 4: both games' CPK payloads are encrypted

> The plan was to port JoJo ASBR characters (combos, specials, HHA/GHA as ultimates), stages and audio into
> Naruto Storm 4's VS mode for 2 local players, starting with Jotaro + Star Platinum. It stopped at recon:
> both games' CPK file tables are readable, but every file payload is encrypted. Getting the keys would mean
> breaking a protection measure, which this toolkit's rules don't allow. Nothing was installed or changed in
> either game.

## Setup
- Windows 11, Steam installs. Storm 4 build 5376895, ASBR build 13123765 (from `appmanifest_*.acf`).
- `um scan` reports both as "Unknown native engine" (10%). Both are really CyberConnect2's in-house engine:
  CRI CPK archives holding NUCC `.xfbin` containers. Storm 4: no anti-cheat. ASBR: EasyAntiCheat
  (`start_protected_game.exe`).

## Route and why
- The plan was data/asset only: extract the ASBR `.xfbin` files, convert to Storm 4's xfbin version, add new
  character slots through Storm 4's tables, then rebuild each moveset by hand in Storm 4's moveset format.
  The two fighting systems don't map 1:1.
- Code injection into ASBR was ruled out from the start because of EAC. Reading its files from disk never
  runs the game, so EAC doesn't come into it.
- Abandoned at step 1 (extraction) because the payloads are encrypted (see Gotchas).

## How the game works (what we had to learn)
- **Archives.** Both games use CRI CPK, `Tvers` "CPKMC2.45.00, DLL3.15.00", Version 7 Rev 11, Align 2048,
  `Codec 0`, `EnableFileName 1`, TOC only (no ITOC/ETOC/GTOC). The header and TOC `@UTF` tables are **not**
  encrypted, so the full file lists (names, sizes, offsets) can be read with any standard CPK parser.
- **Storm 4 layout.**
  - `data/launch/*.cpk` (data1, adx2, sound, stage1, movie1, dataRegion), `data/sim/data2.cpk`,
    `stage2.cpk`.
  - `data/patch/12/{data,launch,sound}.cpk`: the patch overrides base.
  - `data/disc/movie2|3.cpk` (about 27 GB of video), `dlc/9/data/sim/data.cpk`.
  - The `data` folder is about 39 GB.
- **ASBR layout.**
  - `data/launch/{data,stage,sound,adx2,movie,platform}.cpk`, plus per-language `data/launch/<lang>/`
    `{data,platform}.cpk`.
  - `data/patch/patch110…patch230.cpk`, applied in numeric order, and `bgm.cpk`.
  - About 4.9 GB.
- **Character codes.**
  - Storm 4 uses 4 characters (`1nrt` = Naruto). ASBR uses 6 (`3jtr01` = Part 3 Jotaro). A Stand is its own
    code (`3stp01` / `3stp02` = Star Platinum), with its own bod/mot/prm files.
- **Per-character files.** Same naming scheme in both games under `data/spc/`:
  - `<code>bod1` model, `eff1` effects, `prm.bin` moveset, `_anmofs` animation offsets.
  - Storm 4 adds `spl1*` (ultimate cinematics) and `skl*`.
  - ASBR adds `mot1` animations, `ghh1` and `prm_gha.bin` (Great Heat attack), `col0-3` alternate colours,
    and `acc1`.
  - Voice is `data/sound/PC/<lang>/v_btl_<code>.acb/.awb` (ASBR).
- **Storm 4 global character tables** (in `data1.cpk`, overridden by `patch/12/data.cpk`):
  - `data/spc/characode.bin`, `duelPlayerParam`;
  - `data/spc/WIN64/playerSettingParam.bin`, `skillCustomizeParam`, `spSkillCustomizeParam`.

## Build steps
None; this stopped at recon. To reproduce the finding, parse any CPK's TOC, read one entry's bytes at
`FileOffset + TocOffset` and compare its length with `FileSize` / `ExtractSize`.

## Verification
- The TOC offsets are right: each payload starts exactly where the zero alignment padding ends.
- The payloads are compressed (`FileSize` < `ExtractSize`). They don't start with `CRILAYLA` or `NUCC`, and
  every one tested measures 8.000 bits/byte of entropy.
- Storm 4's payloads share an identical first 8 bytes across unrelated files. ASBR's differ per file. That
  fits encryption keyed differently in the two games, not some unknown compression codec.
- Not verified: whether Storm 4 would load an unencrypted CPK added under `data/patch/`. That would only help
  with content made from scratch, not with porting ASBR assets.

## Gotchas
1. **The extracted `.xfbin` files are noise, though the file list parsed fine.** **Cause:** CRI file-level
   encryption on the payloads. Only the `@UTF` header/TOC tables are in the clear. **Fix:** none within this
   toolkit's rules. Don't derive keys from the executables. Check this before planning any extraction-based
   mod on these two games.
2. **`um scan` says "Unknown native engine" for both.** **Cause:** there's no engine signature for
   CyberConnect2's engine. **Tell:** `data/**/*.cpk` plus `.xfbin` files and `CrashRpt*.dll` (Storm 4).
3. **ASBR file lists show some names twice** (e.g. `3jtr01_anmofs`, `3stp01prm.bin`), because later
   `patchNNN.cpk` archives carry newer copies. Apply the patches in numeric order over `launch/` when
   collecting a character's files.

## Assets
None.

## Cost and time
About one session of recon. The CPK reader is about 170 lines of Python (UTF table parser, TOC, CRILAYLA).

## Open questions
- Does Storm 4 accept unencrypted CPKs or loose files for new content? If it does, original (non-ported)
  characters might be possible, but the reference files you'd need to learn its formats are themselves
  encrypted.
- The user's real goal (JoJo cast, local 2P versus) is already covered by ASBR's own offline Versus mode.
