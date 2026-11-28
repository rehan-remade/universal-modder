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
date: '2026-11-27'
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
- **`.tab`**: `u32 0x800`, `u32 <n2>`, then **one of two layouts** (Session 4):
  - A "flat" (game0/3/4/5/6/7/38/patch): `u32 0x800`, `u32 0`, then M 16-byte records
    `(name_hash, x, b, c)`.
  - B "grouped" (everything from game2 up): `u32 0x800`, `u32 n2`, then n2 variable-length
    **chunk-map group entries**, then M 16-byte records `(name_hash, x, b, c)`.
  `x` = 512-aligned offset in the `.arc`; `b` = raw-DEFLATE span; `c` = decompressed size.
- **`.arc` records: MULTIPLE concatenated raw-DEFLATE streams** (zlib wbits −15; records can be
  2–3 streams). Single-stream decompression silently truncates the payload and loses SARC file
  entries. Feed `unused_data` back until consumed; assert total == `c`.
- **Payloads**: either a SARC container — `[u32=4]['SARC'][u32 ver][u32 table_end=file-data
  start]` then per entry **`[u32 nlen][name: nlen bytes, NUL-padded][u32 off][u32 size]`**
  (the name field is nlen bytes wide, NOT NUL-terminated-then-scan — see the Session 4
  correction) — or a raw file (histogram: 20,077 x
  `W\xE0\xE0W`, 5,090 x **RTPC**, 2,413 x **ADF** (` FDA`), 1,935 x `DDS `, 313 x FMOD `FSB5`).
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
- The DLC `.tab` record layout (the game37 "layout change at rec3925+" was just
  layout B, see Session 4).
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
- Copy coverage: `convoy_formation_*ccenemyc` exists in 149/67/21 copies (not 127/61/26 — the
  first index under-counted). They were only 85/42/15 patchable until the .tab layout-B decode
  landed (Session 4); that is what the "index entry points PAST the record's own payload" symptom
  really was. After the fix every copy is patchable and all 237 hold our values with a consistent
  chunk map.

 
 # #   S e s s i o n   4   ( 2 0 2 6 - 1 1 - 2 7 ) :   t h e   . t a b   l a y o u t - B   d e c o d e ,   c h u n k   m a p s ,   a n d   t h e   c o n v o y   p a t c h   f u l l y   l i v e 
 
 * * T h e   \ 
 
 m u l t i - r e c o r d 
 
 S A R C \   b l o c k e r   i s   s o l v e d   -   i t   w a s   n e v e r   t h e   . a r c ,   i t   w a s   t h e   . t a b . * *   E v e r y 
 a r c h i v e   f r o m   g a m e 2   u p   u s e s   l a y o u t   B ,   a n d   t h e   o l d   f l a t - o n l y   r e a d i n g   m i s a l i g n e d   m o s t   o f   t h e m 
 ( w h i c h   i s   e x a c t l y   w h a t   m a d e   s o m e   c o p i e s '   i n d e x   e n t r i e s   p o i n t   p a s t   t h e i r   p a y l o a d ) : 
 
 ` 
 . t a b :     u 3 2   m a g i c ( 0 x 8 0 0 ) 
               u 3 2   n 2                                               < -   c o u n t   o f   C H U N K - M A P P E D   r e c o r d s   o n l y 
               n 2   x   g r o u p   e n t r y   ( v a r i a b l e ) :   [ h a s h ] [ n ] [ 0 ] [ 0 ]   +   ( n - 1 )   x   8 - b y t e   ( t a g ,   v a l u e ) 
               M     x   1 6 - b y t e   r e c o r d   ( n a m e _ h a s h ,   x ,   b ,   c ) 
 ` 
 -   g r o u p   e n t r y :   [ n a m e _ h a s h ] [ n ] [ 0 ] [ 0 ] ,   t h e n   ( n - 1 )   p a i r s .   * * t a g   =   k   *   0 x 0 2 c 0 0 0 0 0 * *   ( c u m u l a t i v e 
     D E C O M P R E S S E D   s i z e   a f t e r   c h u n k   k ,   i . e .   4 6 , 1 3 7 , 3 4 4 - b y t e   c h u n k s ) ,   * * v a l u e   =   t h e   c h u n k ' s 
     c u m u l a t i v e   C O M P R E S S E D   e n d   o f f s e t * *   i n s i d e   t h e   r e c o r d ' s   s p a n .   S o   a   c h u n k e d   r e c o r d   h o l d s   n 
     c o n c a t e n a t e d   r a w - d e f l a t e   s t r e a m s   a n d   t h e   g a m e   r e a l l y   r e a d s   i t   t h r o u g h   t h i s   m a p   -   M a d M a x . e x e 
     c a r r i e s   d e c o m p r e s s _ z l i b _ f r a g m e n t   a t   0 x 2 5 c d 5 b   n e x t   t o   E _ S E _ U N H A N D L E D _ D E C O M P R E S S I O N _ E R R O R , 
     E _ S E _ U N P A C K B U F F E R _ T O O _ S M A L L ,   E _ S E _ S T R E A M B U F F E R _ T O O _ S M A L L . 
 -   g r o u p   h a s h e s   a r e   a   s u b s e t   o f   t h e   r e c o r d   h a s h e s ;   M   > =   n 2 ;   g r o u p   e n t r i e s   a r e   1 6   +   8 * ( n - 1 ) 
     b y t e s ,   s o   t h e   r e c o r d s   s t a r t   a t   a   p e r - a r c h i v e   o f f s e t   ( t h i s   i s   t h e   t r a p   t h a t   b i t   u s   b e l o w ) . 
 -   D i s c r i m i n a t o r :   t r y   l a y o u t   B   f i r s t   ( t h e   g r o u p s   m u s t   t i l e   t h e   t a b   i n   8 - b y t e   s t e p s   a n d   e v e r y 
     r e c o r d   m u s t   b e   s a n e :   x   +   b   < =   a r c   s i z e ) ,   t h e n   f a l l   b a c k   t o   l a y o u t   A . 
 
 * * S A R C   e n t r y   s t r i d e   c o r r e c t i o n * *   ( t h e   o l d   N U L - s e a r c h   r e a d i n g   w a s   w r o n g ) :   e n t r i e s   a r e 
 [ u 3 2   n l e n ] [ n a m e :   n l e n   b y t e s ,   N U L - p a d d e d ] [ u 3 2   o f f ] [ u 3 2   s i z e ] .   V e r i f i e d   o n   t h e   g a t i n g   r e c o r d : 
 3 2 0   e n t r i e s ,   e v e r y   o f f + s i z e   i n s i d e   t h e   p a y l o a d ,   a n d   e x c e l _ d a t a / g a t i n g _ p r o f i l e s . g a t i n g c   a t 
 o f f   1 3 , 2 4 8 , 9 8 8   s i z e   5 , 5 1 3   -   t h e   e x a c t   v a l u e s   t h e   s h i p p i n g   p a t c h   u s e s . 
 
 * * U n d e c o d a b l e   r e g i o n s   e x i s t   a n d   a r e   p r e s e r v e d ,   n o t   f i x e d . * *   g a m e 1 9 / 2 2 / 2 7 / 2 8 / 3 1 / 3 5   r e c 0   c a r r y   a 
 r e g i o n   i n s i d e   c h u n k   0   t h a t   i s   n o t   r a w   d e f l a t e   ( n o   d i c t i o n a r y   s e t t i n g   d e c o d e s   i t ;   n o   z l i b / g z i p 
 s t a r t   a n y w h e r e   i n   t h e   7 . 9   M B ) .   C h u n k s   1 +   a r e   c l e a n   s i n g l e   s t r e a m s .   T h e   g a m e   r e a d s   i t ,   s o   t h e 
 c h u n k   m a p   i s   a u t h o r i t a t i v e   t h e r e ;   o u r   p a t c h e r   c o p i e s   t h e   r e g i o n   b y t e - e x a c t   a n d   r e w r i t e s   o n l y 
 t h e   c h u n k   t h a t   h o l d s   t h e   t a r g e t   f i l e .   A l l   s i x   c o n v o y   f i l e s   h a p p e n   t o   s i t   i n   t h e   f i n a l   c l e a n 
 c h u n k ,   s o   t h e y   a r e   p a t c h a b l e . 
 
 * * R e s u l t :   t h e   c o n v o y   m o d   i s   n o w   l i v e ,   f i n g e r p r i n t - v e r i f i e d . * *   T h e   1 4 9 / 6 7 / 2 1   a r c h i v e   c o p i e s   o f 
 c o n v o y _ f o r m a t i o n _ * c c e n e m y c   a l l   h o l d   t h e   h a l v e d   d i s t a n c e s   ( F R O N T / L E F T / R I G H T / B A C K   1 5 0 - > 7 5 , 
 F O L L O W 1   1 0 0 - > 5 0 ,   F O L L O W   7 0 - > 3 5 ,   F O L L O W 2   2 0 - > 1 0 )   w i t h   a   c o n s i s t e n t   c h u n k   m a p   o n   e v e r y   r e c o r d , 
 a n d   t h e   r u n n i n g   g a m e ' s   m e m o r y   s h o w s   7 5 . 0 x 4   ( O U R S )   x 2   |   1 5 0 . 0 x 4   ( v a n i l l a )   x 0   -   t h e   4 - f l o a t 
 f i n g e r p r i n t   i s   t h e   A / B   s t a n d a r d   ( a   s i n g l e   v a n i l l a   1 5 0 x 4   h i t   i s   a   c o i n c i d e n t a l   r u n   f r o m   o t h e r 
 d a t a ) .   F e e l   r e p o r t s   ( \ m a y b e 
 
 t i g h t e r \ ,   \ s c r a p 
 
 f e e l s 
 
 h i g h e r \ )   c a n n o t   d i s c r i m i n a t e ;   t h e 
 f i n g e r p r i n t   c a n . 
 
 * * T w o   t o o l   l e s s o n s   w o r t h   t h e   s p a c e : * * 
 1 .   T h e   t a b   r e c o r d   o f f s e t   d e p e n d s   o n   t h e   l a y o u t :   w r i t i n g   a   r e c o r d ' s      a t   t h e   f l a t   o f f s e t 
       ( 8   +   r e c n o * 1 6 )   i n s t e a d   o f   t h e   g r o u p e d   o n e   c o r r u p t e d   t h e   g r o u p   t a b l e s   o f   1 7   . t a b   f i l e s   a n d 
       c o s t   a   S t e a m   v e r i f y   c y c l e .   * * A n y   p a t c h   t o o l   m u s t   l o c a t e   r e c o r d s   t h r o u g h   a   l a y o u t - a w a r e 
       p a r s e r ,   n e v e r   a   h a r d c o d e d   8   +   r e c n o * 1 6 . * * 
 2 .   A   p a t c h   t o o l   m u s t   r e - r e a d   ( v e r i f y )   w h a t   i t   j u s t   w r o t e .   T h e   f i x e d   p a t c h e r   i n f l a t e s   t h e 
       r e c o r d   a g a i n   a n d   a s s e r t s   t h e   t a r g e t   f i l e ' s   v a l u e s ,   w h i c h   i s   w h a t   c a u g h t   t h i s   c l a s s   o f   b u g 
       i m m e d i a t e l y   o n   t h e   n e x t   r u n . 
 
 * * S a v e   h y g i e n e   ( r e - c o n f i r m e d ) : * *   t h e   g a m e   r o t a t e s   G a m e S a v e 0 2 . s a v   i n t o   B a c k u p   S a v e s \   o n 
 a u t o s a v e ,   s o   a n y   a u t o s a v e   t a k e n   w i t h   t h e   e c o n o m y   p a t c h   l i v e   h o l d s   d o u b l e d   r e s o u r c e   a m o u n t s   a n d 
 i s   p o i s o n e d   f o r   a   v a n i l l a   r u n   -   r e s t o r e   t h e   p r i s t i n e   s a v e   b e f o r e   a   v a n i l l a   t e s t . 
 
 

### Session 4 closing notes: the asset pipeline and the AI tuning surface

**Authored art loads.** An in-place, same-size edit of a named texture
(`textures/landscape/globalcolor_dif.ddsc`, game0, 2048x2048 DXT1) - filling the pixel
region with a repeating solid-colour DXT1 block - rendered in game: a solid-red world,
verified by screenshot, then reverted (the archive copy was confirmed byte-identical to
vanilla again). There are ~4,400 named `.ddsc` files in the index, so re-skins, recolours
and generated art are reachable with the existing tooling and no new capability.
The door that remains for Shape-B work is only for things a texture cannot be: new
*geometry* and new *paths* (repacker + new-path test), and FMOD/voice packing for audio.

**The car-combat / AI data model (all NATURED names, no content-marker hunting needed):**
- `vehicles/ccenemies/*.ccenemyc` - per-archetype position-preference weights. ADF,
  values blob at 0x50: `[u32 data_off=0x20][0][u32 count][0]`, then `count` 16-byte
  records at 0x70+i*16: `[u32 PointID][0][f32 Value][0]`, then the position names in the
  same order. Archetypes: chasing, fire_pipe (517 copies), boombug, boarding (530 copies),
  drop_kicker, simple (521), plus the convoy_formation_* trio already patched x0.5.
  **Watch the record count: boarding has 12 records (no FRONT_FLAME slot) while the
  others have 13, so its TOP positions sit two slots earlier.**
- `vehicles/ccdirectors/convoy.ccdirectorc` (25 copies) - `CarCombatDirectorDesc`:
  Scenarios[], Sequences[] (path + Weight), MapFile, DefaultScenarioSwitchTime (10.0).
- `vehicles/ccscenarios/convoy.ccscenarioc` (25 copies) - `CarCombatScenarioDesc`:
  Positions[] (PointID + Value) and SwitchToTime (-1 = inherit).
- RTPC records in `patch_win64` are property containers that EMBED the VFS path they
  configure (e.g. one references `vehicles/ccdirectors/convoy.ccdirector` and
  instantiates `CarCombatDirector1`) - the reliable way to identify a record by content.
- Frontier Reborn's AI tuning shipped on this surface: side-pursuit weights raised, the
  boombug's boarding weight raised, and DefaultScenarioSwitchTime 10 -> 20. All 1,089
  copies post-write verified; in-chase verdict from the player: "enemies feel more
  aggressive".


## Session 5 (2026-11-28): the physics VM architecture, the band law, the save node table

**The physics module + properties architecture** (the validator hunt): `vpdrivetrain.xvmc` is a VM module with a 16-byte-entry CONSTANT POOL (type 3 = f32 constant, type 4 = code reference); the per-car `interceptor001_vpdrivetrain_properties.xvmc` is an OVERRIDE LIST of (ref -> value) pairs targeting module code slots: 0x9->0.25, 0xf->2.13333, 0x12->10.6667, 0x15->1.0, 0x18->0.375, 0x1b->0.5, 0x21->PeakTorqueRpm, 0x24->PeakPowerRpm, 0x27->RevLimiter (value floats at entry+8: 0x2d8/0x2f8/0x318). The shared properties file maps the same slots to the shared defaults (1000/2000/3000).

**The boot matrix collapses to one law**: the properties' RevLimiter - PeakPowerRpm must be in [1000, 2000] RPM (an ABSOLUTE band, not a ratio): vanilla 600/2000/3000 band 1000 boots; x2 (1200/4000/6000) band 2000 boots; x3 (1800/6000/9000) band 3000 hangs; limiter-only 1500 (band -500) hangs; band-narrow (600/1500/2500) band 500 hangs; and 600/2000/4000 band 2000 boots (shipped this session). Gear-pair scaling either direction still hangs (a separate check - unresolved). With the module's pool 1.5 -> 2.0 the vanilla properties still boot (rules out a ratio check against the pool constant).

**Save format**: GameSaveXX.sav is XOR-masked (the key is the file's own empty tail) and DOUBLE-BUFFERED: a byte-identical copy of payload 1 follows a second copy of the header's section blocks (the header's 0x100 block = [magic 0x83a89d0d][0][offset 0x7990] names a fixed table). Every field edit must be written to BOTH copies. The resource-node table is 24-byte records (unaligned boundaries):
    [u32 amount][u32 x-fixed][u32 packed][u32 node-id][u32 0][u32 packed2]
1,514 records in every save (the static resource_table's ~1,519 nodes). The amount is frozen at instancing time (identical in pristine/poisoned/post-drive saves) - a fully-discovered save is therefore immune to economy-profile markers; a New Game is the fresh-instancing generator.

**The economy loader has a sanity range**: wild marker values (4321) are silently REJECTED and fall back to the compiled-in defaults (proven by a memory A/B: 4321.0f = 0 hits above the ~15 floor while the vanilla triple is resident; the same file re-patched to 77.5 = 50 hits). In-range markers (77.5, and session 4's 137.0) load fine. Never ship a value outside the plausible range for its field.

**Shipped/verified this session**: VisualRange 455 -> 600 passes fast travel (455 -> 1500 hung; the boundary is between); AI pillar 3 (convoy guard opportunist attacks 100->130, simple chaser sides 90->120/front 50->65/backs 30->45, convoy scenario LEFT/RIGHT/FRONT 50->75/BACK 50->65/FOLLOW* 25->40); a wider power band (600/2000/4000) boots and ships.
