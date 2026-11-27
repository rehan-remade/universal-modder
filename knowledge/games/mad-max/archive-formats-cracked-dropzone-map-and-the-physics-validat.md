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
date: '2026-11-26'
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

## Session 2 (2026-11-26): the data formats are fully cracked and three live mods shipped

**ADF (` FDA`, version 4) container — the general case**, and the schema is in the exe (strings
near 0x92427 carry the same type/field names the files do, so the reflection table can be
cross-checked):
- header `[magic][ver=4][1][secA_off][root_type_count][secB_off][0][0][name_count]
  [name_len_table_off][eof]` (0x28 bytes);
- name table `[nlen x N][N nul-terminated names]` — nlen counts the bytes of the name field,
  and eof is hit exactly;
- section A: 24-byte records `[name_hash][type_hash][offset][size][name_idx][0]` = the root
  blob(s), one per root type (an `.xvmc` is just 3 of these: module/debug_info/debug_strings);
- section B: 32-byte field descriptors `[name_idx][0][type_hash][size][offset][flags][?][0]`.
  **Anchor them by finding the first valid `[name_idx=0..N][0][type_hash][size][offset]`
  record** — the section is padded by other 24/32-byte array/enum records that do not fit the
  shape; the ccenemy file's `Value` float@offset 8 is a good anchor test;
- the values blob: `[u32 data_off][u32 record_count][u32 id_hash][0]` header then
  `record_count` records of the struct size implied by the field offsets.
  Verified on 4 files; pools close exactly on their sheet names.

**`excel_data/gating_profiles.gatingc` — decoded and patched** (5,513 B, ONE copy:
game1 rec94, SARC-inner at offset 13,248,988 — it shares the record with
`legend/player_upgrades.xlsc`, so re-deflating that 13.2 MB record is the cost of a patch).
23 names, and the `GatingProfile` record is **40 bytes**:
`ID u32@0 | JimmyBar..Explosion u8@4..11 (Max's upgrade levels) | StructureLevel@12 |
Type@13 | HasRequirements@14 | JacketLevel@15 | MapIconIndex@16 | IconType@17 |
VisualRange f32@20 | HeaderTextId u32@24 | DescriptionTextId u32@28 | RaycastValidation u8@32
| RaycastSafeHitDistance f32@36`. **107 records**, not the 9 the early recon guessed.
Exe corroboration: `CGatingProfilesManager` + `GatingGetJimmyBar/Pliers/NightVision/
RammingLvl/HarpoonLvl/ExplosionLvl/VisualRange/RaycastValidationInfo` sit next to
`CreateScoutableIcons`, i.e. this table drives scoutable map icons and upgrade levels. The
name-hash function is still uncracked (not fnv/djb2/sdbm/oaat/crc32/xxhash/sfh), so records
must be addressed by index, not name.

**XLSBook ADLs (`legend/*.xlsc`) — the spreadsheet variant**, and these are the real
progression/economy files. Blob layout `[u32 dir_off=0x80][0][u32 pool_count][0]` + per-sheet
`[off][0][size][0]`; the pool directory at 0x80 is `pool_count x [u32 cols][count][off][0]
[bytes][0][end][0]` where **cols = u32s per row**; each pool is one sheet's rows (row-major,
one u32 per column = a string-pool index) and the **sheet name is a nul-terminated string
right after the pool**; the shared string pool sits after the last sheet region:
- `legend/player_upgrades.xlsc` — 4 sheets: categories (2 cols, 14 categories), **upgrades
  (5 cols, 42 rows) = Max's 41 Legend abilities** with the unlock event that gates each,
  character_stats (9 cols), max_stats (4 cols).
- `legend/upgradeable_values.xlsc` — 'Blad1' (24 cols = Name ID, type, then 11 x
  (lvl event, lvl value)) + 'Sheet1'; 38 upgradeables including
  `project_prize_modulation` (the stronghold-project cost multiplier).
- `encampment_upgrades/encampment_projects.xlsc` — sheets enc1000/enc1010/enc1020/enc2010/
  enc2020 (17 cols each) plus **'All projects' (16 cols, 101 rows)** + Requirements +
  EncampLevelReq: Name, Desc, Reward, Category, IconIndex, Completion Event, req 1/2/3
  (name, id, amount), contribution — the stronghold menu, with story-gated completion
  events (`msy.sm_jeet_02.completed`).

**`global/economyresources.economyresourcesc` — the economy core** (68,485 B, ONE copy:
game1 rec81): 3 root blobs (profiles / resource_table / positions).
`EconomyResourceProfile` = **36 bytes**: `Profile u32@0, Type enum@4, RegenerationRate
f32@8, StartAmountMin f32@12, StartAmountMax f32@16, Capacity f32@20, CoolDownTime f32@24,
Infinite u8@28, FillChance f32@32` — enum confirmed 0-based from section B:
Water 0, Food 1, Fuel 2, Scrap 3, Threat 4, Ammo_Shotgun 5, Ammo_Sniper 6,
Ammo_Thunderstick 7, Shiv 8. Profile counts: Scrap 27, Threat 12, Fuel 8, Water 7, Ammo 12,
Food 3, Shiv 2; scrap nodes hold 1-100, r68 (capacity 1,000,000) is Max's wallet, r70 is the
only RegenerationRate != 0.

**Three mods shipped and verified in memory** (all same-size float/byte edits via the
in-place archive patcher, boot-verified by screenshot to the attract screen each time):
1. gating — VisualRange 455→1500 on the 7 long-range records, and StructureLevel −1 across
   the 30 records of Types 16-19 (that table's 1,1,2,2,3,3,4,4 progression shifts one level
   earlier);
2. economy — the 24 lootable scrap profiles x2 on StartAmountMin/Max/Capacity
   (world scrap doubled);
3. convoys — `vehicles/ccenemies/convoy_formation_{frontline,midfield,back}.ccenemyc`
   distances x0.5 (records at `0x70 + slot*16`, float at +8; SUPPORT1/2 = 1.0 are flags, not
   distances).

**Verification without eyeballing the screen** — a memory-scanning monitor replaces
"did it change?". Swap a value for a **unique marker** (1337.5 / 1337.0) that the game would
never produce naturally, then scan the running process (ctypes `VirtualQueryEx` /
`ReadProcessMemory`, ~3.7 GB in under a minute) — if the marker is resident, the game loaded
our data. Two hard-won rules: (a) markers must live in **inert tables only** — a wild value
in a spawned/placed structure (a convoy formation distance) hangs the loader, which is how
one fast-travel hang was caused and fixed; (b) where a marker is undesirable, use a
**fingerprint** instead (the convoy formation's four identical floats 75/75/75/75 vs the
vanilla 150/150/150/150).

**Tool gotchas worth passing on:**
- `inflate()` must stop at the tab's `c`: records carry trailing slack that otherwise gets
  mis-parsed as extra deflate streams, inflating the payload far past `c` (game16 rec3: one
  stream alone = 84.9 MB against a `c` of 22.8 MB) and forcing spurious SKIPs.
- The winnt.h `MEMORY_BASIC_INFORMATION` (x64) field order is BaseAddress / AllocationBase /
  **AllocationProtect** / align / RegionSize / State / Protect / Type — putting the pad
  before AllocationProtect makes State/Protect read 0 and the scan silently finds nothing.
- `wmic` is gone on modern Windows; enumerate PIDs with a CreateToolhelp32Snapshot.
- Copy coverage matters: `convoy_formation_*ccenemyc` exists in 127/61/26 copies and only
  85/42/15 were patchable — the rest live in records whose index entry points PAST the
  record's own payload (game16 rec3: index off 152,290,600 vs payload 84.9 MB), i.e. those
  SARCs span MULTIPLE records. **Open: decode the multi-record SARC layout** in `mmx.py`;
  until then multi-copy patches are only partially covered and must be judged by the
  fingerprint/hash scan rather than assumed.