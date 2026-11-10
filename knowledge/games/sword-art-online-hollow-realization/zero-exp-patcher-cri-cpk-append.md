---
kind: game
title: "Zero EXP patcher: enemy, quest and duel EXP off, with a partners-still-level mode (CRI CPK append patching)"
game: "Sword Art Online: Hollow Realization Deluxe Edition"
games_also: []
game_version: "Steam app 607890, sao_hr.exe PE timestamp 0x59DF33EF, SizeOfImage 0x10A2000, SHA-256 1923F0D8D2CAD559D6AD6E001AF54EA5EA5AA70171323F42D4E1FA3D63699E43; Windows 11 Pro 26100"
platform: windows
engine: native
route: data
tools: ["Python 3.11 (own CPK/@UTF/CRILAYLA/OFS3 scripts)", "PyInstaller 6.11.1 (v1.x)", "MSVC 2022 Build Tools (v2.x patcher and DLL)", "zig cc 0.13.0 (first DLL build)", "YACpkTool", "OFS3_TOOL v1.0"]
anti_cheat: "none; single-player. No DRM wrapper on the exe. The optional code change is applied in memory by a dinput8.dll proxy; the exe on disk is never modified."
status: released
agents: ["Claude Code (Opus 5.5)"]
humans: ["BinaryNull"]
date: 2026-11-10
links: []
tags: [cri-cpk, crilayla, utf-table, ofs3, exp, quests, duels, partners, proxy-dll, dinput8, patcher]
---

# Zero EXP patcher for SAO: Hollow Realization

> A patcher that sets EXP to 0 from enemy kills, request quests, episode/field quests and duels, each
> selectable, plus a "partner mode" where the player gains nothing but partners still level. It edits the
> user's own `data.cpk` (each file SHA-256 checked, no game files shipped), keeps a backup and uninstalls
> byte-identically. Released as v2.0.1 (C rewrite); every option was confirmed in the real game.

## Setup
- SAO: Hollow Realization Deluxe Edition, Steam, Windows 11. Exe guard: PE timestamp `0x59DF33EF`,
  SizeOfImage `0x10A2000`, image base `0x140000000`, `.text` RVA = file offset + `0x1000`.
- Data: `pkg/data.cpk` (35.6 GB, 11,363 files, CPK version 7 rev 14, built by CPKMC2.49.32).
- Tests ran on a copy of the install launched from `sao_hr.exe` directly, plus a second copy kept only for
  install/uninstall hash checks.
- v1.x: Python + PyInstaller 6.11.1. v2.x: C, MSVC 2022 Build Tools (`vcvars64`, `cl`, `/MT`).

## Route and why
Data edits for every reward value, since each is a table field. The CPK can't be rebuilt reliably with
public tools (Gotcha 1), and the tables are compressed (Gotcha 2), so the patcher **appends** modified files
to the end of the CPK and repoints their TOC rows. For partner mode no data-only split exists (player and
partners share one multiplier table), so a 12-byte code change is applied in memory by a `dinput8.dll`
proxy. A proxy keeps the exe untouched, which Nexus prefers.

## How the game works (what we had to learn)
### CRI CPK and friends
- `@UTF` tables are big-endian and XOR-obfuscated (seed `0x655F`, multiplier `0x4115`). TocOffset 2048,
  Align 2048. Absolute file position = `FileOffset + TocOffset`. No CRC over TOC or files.
- About half the files are **CRILAYLA**-compressed (CRI's backwards LZ). A row with FileSize == ExtractSize
  is read as uncompressed, which is what makes appending plain files work.
- **OFS3** container used by most tables: magic, u32 header size 0x10, u8 type (0 unnamed, 2 named), u8
  alignment, u8 entry mode, u32 body size, u32 count, entries relative to 0x10. Mode 0 = (offset, size),
  mode 1 = (offset, id) with no size.
- **Only `sys/sys_data_abyss1/` is loaded on PC** (the exe contains only that path). `sys_data` and
  `sys_data_abyss2` are leftovers; the patcher edits all three anyway, harmlessly.

### Where EXP comes from
- **Kills**: `exp_param.dat` section 0 = %-multiplier tables. Zeroing them zeroes player and partner EXP.
  Section 1 = EXP needed per level (Lv58 = 9794, matches a save). Section 3 = two ±10 level-difference
  tables, purpose unknown. These files are uncompressed, so same-size in-place writes work.
- **Quests** in `quest_setting.bin` (OFS3, 20 named sections):
  - `reqquest.dat` (856 × 240 bytes): +80 = Col, +84 = EXP, +68 low u16 = kill count, +64 high u16 =
    target enemy id.
  - `mapquest_setting.dat` (333 × 560): +548 = EXP (episode/field quests; checked: 50 EXP, 0 Col).
  - `quest_setting.dat` (144 × 368): +316 = EXP (same value as mapquest for every quest).
- **Duels** ignore `exp_param`. EXP comes from `pvp_calc.bin` (OFS3 type 0, float (low, high, value)
  tables). Zeroing the outputs of sections 0, 1, 2, 3, 9 and 10 gives 0 duel EXP; Rank is unaffected.

### Kill-EXP code (for partner mode)
- The function at `0x14021e680`–`0x14021f125` builds a party array and a per-member EXP array, takes the
  player as the member whose type (vfunc 0x1a8) is 1, 11 or 19, and grants EXP through vfunc 0x820 (AddExp)
  in a loop at `0x14021eb19`. A reserve-partner loop follows.
- Partner mode replaces the 12 bytes at RVA `0x21eb3f` with "compare member to player index; jump past the
  grant" (padded with NOPs), so the player is skipped and partners keep their share.
- The "<name> has gained X exp." popup is `info_msg.dat` (28-byte records) message 0x21. Its subject mask at
  +0x1a is 0x10 (player types only; 0x20 is presumably partners). Partner mode sets it to 0x30 so partner
  gains are visible.

## Build steps
1. Read the CPK: decode the @UTF header and TOC (FileName, DirName, FileOffset, FileSize, ExtractSize), and
   CRILAYLA-decompress entries whose FileSize ≠ ExtractSize.
2. Edit the tables listed above for the chosen options; verify each source file's SHA-256 first.
3. Append each modified file uncompressed at the 2048-aligned end of `data.cpk`, set its row's FileOffset
   (relative to TocOffset), FileSize and ExtractSize, and re-encrypt the TOC in place.
4. Backup = the original rows + original CPK length. Uninstall truncates and restores the rows.
5. Partner mode: also install the proxy `dinput8.dll` next to `sao_hr.exe`. The DLL forwards the real
   exports, checks the PE timestamp, SizeOfImage and the original bytes, patches in memory, and logs to a
   file replaced at each launch. The patcher refuses partner mode combined with the enemy option, a wrong
   exe or a foreign `dinput8.dll`.

## Verification
- In-game by the human, per option: kills, a request quest, an episode quest ("Boarish Intruders"), a DLC
  duel (NM: Furious Berserker, previously 235 EXP), and partner mode (partners leveled, popups shown).
- Offline: install/uninstall on a spare copy compared by SHA-256; uninstall is byte-identical, including
  cross-uninstall with the [Genesis Unlocker](genesis-as-a-combat-partner.md) in both orders. The C v2.0
  output was byte-identical to Python v1.3 for every option.
- Not verified: what exp_param section 3 does.

## Gotchas
1. **YACpkTool `-X <file>` crashes (AccessViolation)** even on an untouched CPK; `-R` failed on paths with
   spaces and once died mid-write. **Cause:** tool bugs. **Fix:** own reader/appender; check results by
   reading bytes at TOC offsets.
2. **In-place quest edits had no effect.** **Cause:** `quest_setting.bin` is CRILAYLA-compressed in the CPK.
   **Fix:** append the uncompressed file and repoint the row.
3. **Duel EXP survived exp_param at 0 %.** **Cause:** duels use `pvp_calc.bin`. **Fix:** zero its outputs.
4. **Partners also got 0 EXP.** **Cause:** shared multiplier table. **Fix:** leave it, skip only the player
   in code.
5. **Partner mode looked broken (no popups).** **Cause:** message 0x21's mask is player-only. **Fix:** 0x30.
6. **OFS3_TOOL overwrote edits.** **Cause:** clicking Extract again re-extracts over the folder. **Fix:**
   edit copies, or use a script.
7. **Two proxy mods both want dinput8.dll.** **Fix:** other mods use a different system DLL (see
   [Smith Radar Percent](smith-radar-percent-winmm-proxy.md)).

## Assets
None.

## Cost and time
Two days of sessions (2026-11-06 to 2026-11-07), v1.0.0 → v2.0.1.

## Open questions
- exp_param section 3 meaning.
- Duel Rank source (not in the zeroed pvp_calc tables).
