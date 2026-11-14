---
kind: game
title: "Inside the SAOHR Living World mod (Supporter DeathMode 0.3.1 test build): a dinput8.dll runtime with embedded Lua and SQLite, plus hash-pinned usa.cpk block patches"
game: "Sword Art Online: Hollow Realization Deluxe Edition"
games_also: []
game_version: "Steam app 607890, sao_hr.exe PE timestamp 0x59DF33EF, SizeOfImage 0x10A2000, SHA-256 1923F0D8D2CAD559D6AD6E001AF54EA5EA5AA70171323F42D4E1FA3D63699E43; mod package SAOHR-Supporter-DeathMode-0.3.1-test.20261028.5 (dinput8.dll SHA-256 36A89D71...7F8C5); Windows 11 Pro 26100"
platform: windows
engine: native
route: native-hook
tools: ["Python 3.11 + pefile + capstone (PE, exports, call-site disassembly)", "own CRI CPK @UTF / CRILAYLA / OFS3 readers (from the Zero EXP note)", "reading the mod's own PowerShell installers, Lua policy and runtime log"]
anti_cheat: "none; single-player. Analysis only: nothing was patched, run or redistributed by us. The mod itself changes the exe only in memory, and changes pkg/usa.cpk on disk after checking its hash."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["BinaryNull"]
date: 2026-11-14
links: []
tags: [teardown, third-party-mod, proxy-dll, dinput8, lua, sqlite, death-mode, living-world, npc-simulation, guild, party, cri-cpk, crilayla, ofs3, phyre, block-patch, call-site-hook, vtable-hook, fail-closed]
---

# Inside the SAOHR Living World mod (Supporter DeathMode 0.3.1 test build)

> A teardown of someone else's mod, not one we built. The "SAOHR Living World" mod (this build:
> *Supporter DeathMode 0.3.1-test.20261028.5*) turns SAO:HR into a permadeath game with a persistent NPC
> world. It has two halves. A 13.5 MB `dinput8.dll` proxy hooks hundreds of game functions in memory and
> runs embedded Lua 5.5 and SQLite. Hash-pinned block patches to `pkg/usa.cpk` add a Guild menu, a
> re-painted title screen and optional PlayStation button glyphs. Everything below comes from the package
> files, the game's own archives, disassembly of the game's exe, and the mod's runtime log on a machine where
> it is installed and running.

## Setup
- Game: same exe as the other notes in this folder (identity in the front matter); image base `0x140000000`, no ASLR.
- Mod package contents: `dinput8.dll` (x64; 1,560 exports: `DirectInput8Create` and the COM stubs, plus
  ~1,550 `DeathMode*` / `Saohr*` telemetry getters), the runtime folder `saohr_supporter_death_mode\` (`lua55.dll`,
  `mode.default.ini`, `policy\*.lua`, `density_source\*.dat`), patch blocks under `controller-assets\`,
  `title-assets\` and `guild-assets\`, and PowerShell + bash installers (bash for Proton / Steam Deck).
- The mod comes in three editions (Community / Supporter / Beater) × three rulesets (DeathMode / LevelOne /
  RegularDeath). Each pair has its own runtime folder `saohr_<edition>_<ruleset>` and its own world database.
- The build manifest names a source branch `codex/supporter-systems-audit-20261028`. The original author is not
  named anywhere in the package.

## Route and why
- **In-memory hooks from a proxy DLL** (`native-hook`) do all of the logic. The exe on disk is never touched.
  The DLL loads the real system `dinput8.dll` and forwards `DirectInput8Create`.
- **On-disk CPK block patches** are used only for UI resources that the game must load from `usa.cpk`.
- **Lua 5.5** runs the character-generation policy. It began as Cheat Engine table scripts (comments mention CE,
  `getAddressSafe`, `readInteger`). The native side swaps CE's memory writes for a returned write plan.
- **SQLite** stores the persistent world: NPCs, parties, guilds, relationships and history.

## How the game works (what we had to learn)
### 1. Installer transaction (`Install-Release.ps1`)
- Refuses to run while `sao_hr` is running. It stages `dinput8.saohr-release-new.dll`, checks its SHA-256 against
  `runtimeSha256` in `RELEASE_MANIFEST.json`, then swaps it in with `File.Replace`. It then needs **8 matching
  hash samples 250 ms apart** before it records success, because antivirus can quarantine the proxy after the
  rename.
- An existing `dinput8.dll` that is not from this mod is backed up to
  `saohr_release_state\dinput8.pre-saohr-release.dll` and restored on uninstall. A DLL counts as an earlier copy
  of this mod (and is thrown away) if its bytes contain one of `gameplay_settings_interface`,
  `living_world.sqlite3`, `saohr_beater_`, `saohr_supporter_` or `deathmode_native`, in ASCII or UTF-16.
- `mode.default.ini` is **merged** into `mode.ini`: only missing keys are added, so player settings survive an
  update. On a first install with no database, `world_seed` is replaced with 63 random bits. A one-time
  migration forces `permanent_death=1` and keeps a backup of `mode.ini` plus a marker JSON.
- State lives in `saohr_release_state\`: `install-state.json`, `controller-profile.json`, and an append-only
  `owned-runtime-directories.txt`. Uninstall deletes only folders on a hard-coded allowlist, and only inside the
  game folder.

### 2. The usa.cpk patch chain (all verified against the stock archive)
Every step checks the SHA-256 of the whole 700 MB archive before and after. The work happens on a temporary
copy that replaces the live file only after it verifies.

| Step | Size → size | What changes in the CPK |
|---|---|---|
| Stock Xbox | 718,969,200 | `27D10069…` (backup kept as `usa.cpk.saohr-native-xbox.bak`) |
| → PlayStation glyphs (optional) | same | three 64 KiB blocks: one TOC block where only `sys/sysp_pc` FileSize changes (72,700 → 66,632), and two content blocks that rewrite `sysp_pc` in place (same ExtractSize) |
| → REALIZED title | → 735,457,280 | 14 bytes at file offset 203,296 inside the **encrypted** TOC (the `ui/title` row's FileSize + FileOffset, already XOR-encrypted), then 1,680 zero bytes + the 16,486,180-byte CRILAYLA payload + 220 zero bytes appended |
| → Guild UI | → 735,920,128 | the CPK header (848 B @16), the whole TOC (221,184 B @2048) and the ETOC (88,064 B @718,882,816) are rewritten. A new row `ui/guild` (ID 7185, Files 7185 → 7186) points at a CRILAYLA payload appended at 735,457,280 |

- The REALIZED payload is the game's `ui/title` OFS3 package with **only `013_title_tex.tga.phyre` changed**.
  The header, pane, anim, timeline, buv and frame members are byte-identical. You can re-skin a menu by swapping
  only the Phyre texture.
- `ui/guild` is a 9-member OFS3 package built on the game's blacksmith menu layout (`027_blacksmith_header/pane/
  anim/timeline/tex.tga.phyre/buv/frame/txt*`). The DLL opens it for the Guild screens.
- The chain is ordered: Guild needs REALIZED, which needs a stock Xbox or PlayStation archive. Switching the glyph
  layout rebuilds the whole chain from the `.bak`.

### 3. The proxy DLL: identity check and hook styles
- On start it logs `supported sao_hr.exe build verified`. The exe's PE timestamp and SizeOfImage appear dozens of
  times as constants in the DLL. Every feature also checks its own call sites, so a different exe build turns
  each feature off on its own instead of crashing.
- **Call-site retargeting** (the main technique): the DLL reads an `E8 rel32` call, checks the opcode and the
  current target, writes a new rel32 to a thunk, reads it back, and rolls back if the readback fails. Sites
  named in its error messages, all confirmed on this exe with Capstone:
  `0x1CC1B0 → 0x2A1060` (player-Party identity), `0x234CB0 → 0x2321A0` (NPC name projection),
  `0x260E2C → 0x260B80` (field-party generation candidates), `0x261614 → 0x29F8B0` (generation roster, after
  checking 7 planning calls).
- **Vtable slot swap**: vtable `0x816A18`, slot `+0xB40` holds `0x234410` (the NPC build resolver). The DLL
  checks that function's prologue before it replaces the slot.
- **Prologue-checked trampolines** are used for the enemy, combat-hit, backstep and render hooks. Their log
  messages say `bytes differ`, `prologue-mismatch` or `trampoline allocation failed`.
- **DirectInput vtable hooks** on `CreateDevice`, `GetDeviceState` and `GetDeviceData` handle the extra
  controller shortcuts: L2+Circle / LT+B for Social Actions, and holding Triangle / Y / Space for 1.5 s to skip
  story scenes.
- Every subsystem reports itself with a "fail-closed" message and leaves native behaviour alone when it can't
  verify something. When it stops, it leaves its hook code in place and lets late callbacks fall through to the
  native function instead of freeing the code.

### 4. What the runtime changes (grouped from exports, the INI and the log)
- **Death rules.** A lethal-attacker capture and a 3-second fall delay run before the defeat screen. Then comes
  a "Kirito room" respawn checkpoint and a *successor* roll: a new random character. LevelOne resets to level 1;
  RegularDeath keeps native death.
- **Living world.** Persistent adventurers, parties and guilds; off-screen simulation (`simulation_interval_seconds=60`,
  catch-up capped at `simulation_maximum_elapsed_hours=6`); map-to-map travel; NM/HNM hunting cohorts;
  relationships; town residency.
- **Player systems.** Guild through the innkeeper, a Friends-style Guild directory, Social Actions (friend /
  Party / Guild invites), and a Party screen with 4 rows: the player plus the 3 native companion slots.
- **Density and difficulty.** Field-ally groups ×3 (authored 4 → +8 groups). The enemy active cap goes 30 → 60
  by copying the formation records owned by the native scheduler. Town population ×1.5 (cap 180). Hard
  difficulty multiplies ordinary enemies by 1.35/1.65 and bosses by 1.20/2.00. Ordinary-enemy perception is
  20 units.
- **Graphics and performance.** Draw-distance, tree-shadow, fog and borderless/ultrawide projection controls.
  The Phyre worker pool is capped at 7, and render paths get caches and atomics (`sites=12`). Each of these
  installs separately and logs its own result.

### 5. Embedded Lua: the successor-character policy
- `native_policy_adapter.lua` is the contract between the DLL and Lua. The DLL calls `dmNewCharacterPrepare(event)`
  (event mode `player_down` / `party_wipe`), then `dmNativeBuildGearPlan(roll)` or `dmNativeBuildLevelOneResetPlan`.
  These return gear rows plus `nativeProgressionWrites`, an ordered list of `{offset, value, width}`.
- The offsets are **relative to `sao_hr.exe`** and fall inside its `.data` section (0xA52000–0xFFE538):
  weapon proficiencies from `0xB15F52` with a 0xC stride (9 weapon types, stored ×10), unspent SP `0xB15F54`,
  landed 1H-sword skills `0xB15FF4` (the Dual Blades gate, set to 2000), Horizontal Arc ownership `0xB16302`,
  active EX selector `0xB190D4`, partner affection from `0xB2F068` (stride 0x12C), Col `0xB6BBE8`. Skill
  ownership values are 1 = visible and 2 = learned.
- The roll picks an origin from 22 weighted profiles (`hr_origin_profiles.lua`, from "Poor New Player" to
  "Beater"), then level and Col bands, weapon mastery, an EX build, and gear ranked by power
  (`deathmode_power_ranked_looter.lua`, 1.6 MB, generated from a spreadsheet). It also writes a background story
  for the character from the enemy, reward and world-history catalogs. A palette plan is rejected if it contains
  a skill the character hasn't learned.

### 6. World database (`world\<edition>_<ruleset>.sqlite3`)
- 93 `CREATE TABLE`s across **38 numbered migrations** (`schema_migrations`, checksums `lw-schema-v1`…`v38`),
  from `foundation` to `legacy-friend-rank-repairs`. Heavy use of `CHECK` constraints, and
  `BEFORE INSERT/UPDATE/DELETE` triggers with `RAISE(ABORT)` keep observation records immutable.
- Writes go through a queue (`save_queue_capacity=512`, `save_batch_size=64`) with `backup_count=3` rotating
  backups. Each install's random `world_seed` gives it a different cast.

## Build steps (repeating the analysis)
1. Unzip into an empty folder. Read `RELEASE_MANIFEST.json`, then the `.patch` text manifests (`offset:length:file:sha256`).
2. Diff the TOCs of `usa.cpk.saohr-native-xbox.bak`, the REALIZED copy and the live `usa.cpk` with an @UTF reader
   (TOC at 2048, file offsets relative to the TOC). For the glyph patch, overlay `block-000.bin` at 196,608 onto
   the stock TOC bytes in memory and parse again.
3. Decompress the payloads with CRILAYLA (keep the 0x100 raw prefix) and list them as OFS3. Compare each member
   with the stock `ui/title`.
4. Run pefile on the DLL (exports, imports, strings). Grep the strings for `rva=0x`, `expectedRva=0x` and
   `prologue`. Disassemble those RVAs in `sao_hr.exe` with Capstone to confirm the call targets and vtable slot.
5. Read `<runtime>\logs\native_runtime.log`. Its startup lines list each hook that installed on your build.

## Verification
- Every CPK fact above was measured against the user's stock backup and live archives. The 4 call sites and the
  vtable slot were disassembled on this exe and match what the DLL expects. The `density_source\*.dat` files
  are byte-identical to the stock `sys/sys_data{,_abyss1,_abyss2}/enemy_battalion.dat` in `data.cpk`.
- The runtime log on this machine (sessions of 2026-11-11 and 2026-11-13) shows each of the hooks above
  installing on this exe, and the world database working (19 MB).
- NOT verified: the hook bodies themselves (we read guard messages, not code), the exact formulas behind the
  Hard multipliers, and the death → successor flow end to end (the log has no death in it). PlayStation glyph
  content and the Linux installer were not exercised.

## Gotchas
1. **This mod takes `dinput8.dll`.** **Cause:** the [Zero EXP patcher's](zero-exp-patcher-cri-cpk-append.md)
   partner-mode proxy uses the same name. **Fix:** the installer backs up any `dinput8.dll` that isn't its own
   and puts it back on uninstall, so Zero EXP partner mode is off while Living World is installed. The `winmm`
   and `dbghelp` proxies from the other notes are not affected.
2. **Any other usa.cpk mod blocks the install.** **Cause:** every step requires one of 6 exact archive
   hashes; an unknown hash is kept only if an earlier install recorded it. **Fix:** put the stock archive back
   (Steam "Verify integrity" or the `.bak`), or pass `-ControllerCpk`. Mods that patch `data.cpk` are fine; it
   isn't pinned.
3. **A game update turns features off one by one.** **Cause:** each hook checks its own bytes or call target
   at a fixed RVA. **Fix:** read the `failed closed` / `guard rejected` lines in the log. Each names the RVA it
   expected.
4. **Patching the TOC needs bytes that are already encrypted.** **Cause:** CPK TOCs are XOR-encrypted with a
   key stream that depends on position. **Fix:** like this mod, write the bytes as they appear encrypted at
   that exact offset, or decrypt, edit and re-encrypt the whole @UTF.
5. **The proxy gets quarantined after a successful copy.** **Cause:** antivirus scans after the rename.
   **Fix:** this installer only reports success after 2 s of stable hash checks. Copy that pattern for any
   proxy installer.
6. **Proton doesn't load the proxy.** **Fix:** `WINEDLLOVERRIDES="dinput8=n,b" %command%`.
7. **The package ships stock game data** (the three `enemy_battalion.dat`). This note and any re-implementation
   should take it from the user's own `data.cpk` instead.

## Assets
None made by us.

## Cost and time
One session (2026-11-14), read-only analysis.

## Open questions
- What the hooked functions are (`0x2A1060`, `0x2321A0`, `0x260B80`, `0x29F8B0`, `0x234410`) in game terms. Names
  are inferred from the mod's log messages only.
- Who the original author is, for credit.
