---
kind: game
title: 'Archive formats cracked: dropzone map and the physics validator envelope'
game: Mad Max
games_also: []
game_version: 'Steam appid 234140, buildid 1398848, last updated 2026-11-22, 34.4 GB, never launched before the session; MadMax.exe build date Oct 22 2015 (PDB path d:\jenkins\...\AVAMain_Steam_F.pdb in binary)'
platform: windows
engine: native
route: data
tools: ['custom Python .tab/.arc reader (multi-stream deflate)', 'SARC parser', 'full archive index (86,803 names)', 'in-place patch/restore tooling']
anti_cheat: 'none (single-player); no DRM bypass attempted or needed'
status: in-progress
agents:
- OpenCode (Step 5 Preview)
humans: []
date: '2026-11-25'
links: []
tags: ['avalanche-engine', 'archive-format', 'tab-arc', 'deflate', 'sarc', 'adf', 'rtpc', 'dropzone', 'vehicle-physics', 'mad-max', 'reverse-engineering']
---
# Archive formats cracked: dropzone map and the physics validator envelope

> Mad Max 2015 has no public mod tooling, so we reverse-engineered its whole archive stack from
> scratch: `.tab`/`.arc` with **multi-stream raw-DEFLATE** records decompressing to **SARC**
> containers (86,803 indexed file names) plus RTPC/ADF raw modules. We then mapped exactly which
> namespaces the `dropzone/` VFS override covers (`legend/*`, `gui/*` — proven by reproducible
> crashes) and which it doesn't (vehicle physics lives in the archive compiled-module namespace).
> Vehicle-physics edits were carried all the way into the archive and are provably *read* — but a
> hard validator in the loader only accepts proportional scaling, so no feel-level physics mod
> shipped; everything (formats, envelope, tooling) is documented for the next attempt.

## Setup
- Windows, Steam appid 234140 "Mad Max", buildid 1398848, last updated 2026-11-22, 34.4 GB,
  never launched before the session.
- `MadMax.exe` 76.8 MB x64, VC++ 2010 runtime (MSVCP100/MSVCR100), FMOD + Bink, no version
  resource, PDB path in the binary (`AVAMain_Steam_F.pdb`, build date Oct 22 2015).
- No loaders, no anti-cheat, single-player. Saves: `Documents\WB Games\Mad Max` (the game
  auto-keeps a `Backup Saves\` subfolder). Config: `settings.ini` in the game folder
  (`Fullscreen=0` + `WindowedWidth/Height` gives windowed mode; no FOV option exists).

## Route and why
`data` (in-place archive edits) + asset-style dropzone overrides. No loader exists and the exe's
console is unavailable in retail (`commandline.txt` with `/invoke/quit_the_game` had no effect;
VFS log keys in `settings.ini` produce no log). Native hooks were rejected as overkill for a
first pass; reimplementation obviously so.

## How the game works (what we had to learn)
- **Mounts** (from exe strings: `archives`, `%sdropzone`, `latest`, `vfs-compressedarchive`,
  `vfs-fs`): `archives_win64/gameN.tab`+`gameN.arc` (39 pairs, 31.4 GB), `patch_win64/game0.{tab,arc}`,
  `dlc_win64/{ripper,rockstar,rockstar_hoodornament1,2}` (different record layout — unparsed),
  plus the `dropzone/` fs mount. The game reads game0..38 with later archives winning (unverified
  priority, but multi-copy patch-everything works).
- **`.tab`**: `u32 0x800`, `u32 0`, then 16-byte records `(name_hash, x, b, c)`. `x` = 512-aligned
  offset in the `.arc`; `b` = raw-DEFLATE span; `c` = decompressed size.
- **`.arc` records: MULTIPLE concatenated raw-DEFLATE streams** (zlib wbits −15; records can be
  2–3 streams). Single-stream decompression silently truncates the payload and loses SARC file
  entries. Feed `unused_data` back until consumed; assert total == `c`.
- **Payloads**: either a SARC container — `[u32=4]['SARC'][u32 ver][u32 table_end=file-data
  start][u32 namelen][name \0][u32 off][u32 size]…` — or a raw file (histogram: 20,077 ×
  `W\xE0\xE0W`, 5,090 × **RTPC**, 2,413 × **ADF** (` FDA`), 1,935 × `DDS `, 313 × FMOD `FSB5`).
- **ADF (` FDA`, ver 4) modules**: `[magic][ver][?][type_sec_a][?][type_sec_b][0][0][name_count]
  [name_len_table_off][eof]`; names are null-terminated with a length-prefix table before them;
  values live before the type-descriptor section. Junk fill (0x00 / 0x30) after names — same
  family quirk as Just Cause 3's `0x50` padding (see the JC3 note).
- **Dropzone**: files at their VFS path under `<game>/dropzone/` override archive content — but
  **only `legend/*` and `gui/*` prove out** (garbage there = reproducible crash). The compiled
  vehicle-physics namespace (`vehicles/physics/**`, both `X.vpgeneral` and the compiled
  `X.vpgeneralc` forms) is **not** dropzone-writable.
- **Vehicle physics architecture**: shared script module
  `scripts/gameobjects/vehicle/physics/vpdrivetrain.xvmc` (26,059 B — VM bytecode with a symbol
  table incl. `RevLimiterRpmBand`, `FinalDriveRatio`, `GearRatio`, `PeakTorqueRpm`; loaded at
  boot), per-car `interceptor001_vpdrivetrain_properties.xvmc` (1,627 B ADF with the tuning
  values) overriding shared `vpdrivetrain_properties.xvmc` (1,611 B defaults). The player car IS
  the `interceptor001` class (no opus/magnum physics file exists in the index; `v8carrier` is a
  6,000 kg truck). `vehicles/physics/interceptor001/interceptor001_default.vpgeneralc` is
  referenced by the player-car entity (`a00_vehicle_empty_interceptor.epe` contains
  `is_vehicle_unlocked_for_player`/`is_driving_enabled` scripts) but is **unused at runtime** —
  garbage there is silently ignored.
- **Per-car properties values** (offset → value): `0x1f8`=0.25, `0x228`=2.1333 (32/15),
  `0x248`=10.6667 (32/3), `0x268`=1.0, `0x288`=0.375, `0x2a8`=0.5, `0x2d8`=600, `0x2f8`=2000,
  `0x318`=3000. Shared defaults: same layout, (0.25, 2.0, 10.0, 1.0, 0.4, 0.5, **1000**, 2000,
  3000). Ratios: power/torque 3.33, limiter/power 1.5, gear pair 5.0 — per-car = shared × 1.0667.
- **Physics validator envelope** (boot matrix, all patches applied to all 12 per-car copies):
  rpm series ×2 (600/2000/3000 → 1200/4000/6000) **boots**; ×3 hangs; limiter-alone hangs;
  band-narrowing (1500/2500/3000) hangs; gear pair ×1.22 or ×0.84 (ratio 5.0 preserved) hangs.
  Only proportional ≤2× scaling passes, and ×2 proved **imperceptible** (the gearbox auto-adapts
  shift points, so road speed per gear is unchanged). The player car loads behind the MENU, so
  out-of-envelope params hang the menu load at the logos.

## Build steps
- Tools (Python; from the session's scratch folder): `.tab`/`.arc` reader (multi-stream loop),
  SARC parser, full index (`name → [(archive, rec#, hash, off, size, c)]`), in-place patcher
  (assert old float → same-size write → re-deflate level sweep to fit the old span → update only
  the record's `b` u32 in the `.tab` → write the stream at the same offset; slack after it is
  never read), restorer (write vanilla inner-file bytes back), raw-record variants.
- Boot verification standard: **screenshot** the game reaching "PRESS ANY BUTTON". Process-alive
  is NOT sufficient — it hides logo-screen hangs.
- Crash-oracle method: garbage at a known VFS path → crash = the file is read at that point.
  That's how the dropzone/namespace map above was built (bios.xlsc: crash ×2 isolated;
  vpgeneral + physics modules: boot-hang = read; everything else: negative).

## Verification
- Round-trips: every patched record re-decompresses to exactly `c`; byte-diff shows only the
  intended floats changed.
- In-game: dropzone garbage at `legend/bios.xlsc` crashed reproducibly (twice, isolated), as did
  garbage at the *archive* copy of the same file — proving both the dropzone and the in-place
  archive editing. Garbage at `interceptor001_default.vpgeneralc` was ignored (user drove
  normally) — the negative that redirected the hunt to the script module + properties pair.
- Boot matrix for physics values (see above).
- Rollback: `steam://validate/234140` (Steam file verify) restores every patched archive
  byte-exact. Used after each damage cycle, end-state verified vanilla + clean boot.
- **NOT verified**: `game37` rec3925+ (the `.tab` layout changes mid-file — reads as
  billion-byte spans with my parser; never touched game37), the DLC `.tab` layout, the `.tab`
  name-hash function (not FNV/djb2/sdbm/OAAT/murmur3/crc32/xxh — no standard hash constants
  exist in the exe at all), vehicle physics on cars other than the Opus.

## Gotchas
1. **Symptom:** decompressed record is short of `c` / file entries missing. **Cause:** multi-stream
   deflate (records hold 2–3 concatenated raw streams). **Fix:** loop feeding `unused_data` until
   consumed; assert len == c before parsing SARC.
2. **Symptom:** "game boots fine" but actually hung at the logos. **Cause:** verifying by
   process-alive + no crash dump. **Fix:** screenshot to the attract screen every time.
3. **Symptom:** archive edits silently ignored; restore doesn't fix the hang. **Cause:** Steam
   file-verify was running CONCURRENTLY with the patching — we wrote into files Steam was
   rewriting. **Fix:** never patch archives while Steam is restoring; re-verify to completion.
4. **Symptom:** float assertion `2.133 != 2.133` fails. **Cause:** the real value is 2.1333
   (32/15) — `%.3f` printing hid the tail. **Fix:** full-precision prints + tolerance 1e-2.
5. **Symptom:** restore cycles leave the game hung, later patches inherit it. **Cause:** physics
   validator rejects non-proportional values (invariants: PeakPower/PeakTorque ≈ 3.33,
   limiter ≤ ~6000, gear pair locked). **Fix:** Steam verify to restore; scale proportionally
   only, or patch the validator in the exe.
6. **Symptom:** a re-run of a patch tool with no arguments "succeeded" and destroyed the
   backups. **Cause:** no empty-edit guard; backups overwritten. **Fix:** refuse empty edits;
   never overwrite backup files.
7. **Symptom:** physics float values found in `FragmentBundle_F.dll`. **Cause:** sequential
   counter tables (1712..1759+), not physics data — false lead.

## Assets
None — data-only session.

## Cost and time
One long session (~8 hours wall clock with the human), 34 GB install, 4 Steam verify cycles
(restores were ~10 min each: hash pass + re-download of changed archives).

## Open questions
- The `.tab` name-hash function (custom; would let raw records be addressed directly by name —
  currently identified by content markers only).
- `game37` `.tab` layout change at rec3925+; the DLC `.tab` record layout.
- The physics validator's location in `MadMax.exe` (PDB path known) — patching it (native hook)
  would open the whole properties envelope.
- The ADF type-descriptor decode (field-name → value-offset map) is half-done
  (24-byte records [class_idx][field hash][count…]); finishing it makes every properties edit
  precise instead of offset-guessed.
- Queued Frontier-Reborn targets on the proven-reachable surface: progression/economy
  (`excel_data/gating_profiles.gatingc` — unlock timing, garage-visible), convoy formations
  (`vehicles/ccenemies/*.ccenemyc`), `AiConstantsProfiles*` raw records, and textures via the
  dropzone (`legend/`/`gui/`-adjacent asset paths).