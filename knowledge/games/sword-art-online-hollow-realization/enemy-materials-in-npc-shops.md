---
kind: game
title: "Enemy material drops sold in NPC shops (Phase 1: container survey, shop and item table candidates)"
game: "Sword Art Online: Hollow Realization Deluxe Edition"
games_also: []
game_version: "Steam app 607890, sao_hr.exe SHA-256 1923F0D8D2CAD559D6AD6E001AF54EA5EA5AA70171323F42D4E1FA3D63699E43; data.cpk 37,316,054,776 bytes; Windows 11 Pro 26100"
platform: windows
engine: native
route: data
tools: ["Python 3.11 (own CPK/@UTF/CRILAYLA/OFS3 scanners)"]
anti_cheat: "none; single-player. Read-only analysis so far."
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: ["BinaryNull"]
date: 2026-11-10
links: []
tags: [shops, items, drops, ofs3, cri-cpk, crilayla, survey]
---

# Enemy materials in NPC shops for SAO: Hollow Realization (in progress)

> Goal: duplicate an NPC shop entry and point it at an existing enemy material, so drop-only materials can be
> bought. Phase 1 (a read-only survey of the data containers and candidate tables) is done; nothing has been
> changed or tested in-game yet. This note records what is known so the next session doesn't repeat it.

## Setup
- SAO: Hollow Realization Deluxe Edition, Steam, Windows 11. Clean reference `data.cpk` (37,316,054,776
  bytes) kept apart from the test install, whose CPK already carries other appended mods.
- All 250 `sys/` files copied out and checked against the CPK (138 byte-identical including all of
  `sys_data_abyss1/`; the rest are compressed and checked by size).
- Working rules set by the human: no game file edits during investigation, work on copies, label confirmed
  vs hypothesis, never invent ids or offsets, keep every mod reversible.

## Route and why
Data: the shop list and items are tables. Every candidate table is CRILAYLA-compressed in the CPK, so the
install must use the append-and-repoint method from the
[Zero EXP patcher](zero-exp-patcher-cri-cpk-append.md), merged with whatever mods are already appended.

## How the game works (what we had to learn)
- Only `sys/sys_data_abyss1/` is loaded on PC (confirmed: the exe contains only that path).
- `sysdata_ctrl.dat` is 1,216 bytes of 532 × 01 and 684 × FF, not all 01 as first assumed. Meaning unknown.
- 102 OFS3 files validated under `sys/`. Type 0 files satisfy body size + 0x10 = file size; type 2 (named)
  files are larger than that, likely with names after the body. Mode 1 entries are (offset, id) without
  size, so growing a section means rewriting later offsets.
- Candidates (by name and container only, contents not decoded):
  - `shop_setting.dat` (14,604 bytes): OFS3 type 0, mode 1, five sections with ids 111–115.
  - `fix_item.dat` (585,732 bytes, headerless): likely the item master. From blacksmith research the item
    master record is 0x54 bytes: +0 u16 category, +2 u16 id, +0x12 rarity (0–5), +0x14 price, +0x18 level.
  - Drop table: not located. Candidates `enemy_data` (enemy records; +8 = name text id 8500xxx),
    `enemy_battalion.dat`, `enemy_coin_drop.dat` (starts with floats; likely Col drops), `enemy/enemy_trigger`.

## Build steps
None yet.

## Verification
TOC comparison of the test CPK against the clean one (eleven rows differ, all from earlier mods); copy
verification by hash. Nothing tested in-game.

## Gotchas
1. **The test CPK is not clean.** **Cause:** earlier mods appended there. **Fix:** compare against a clean
   reference CPK, and install new mods together with the existing appended set.
2. **TOC comparison misses in-place edits.** **Cause:** same-size uncompressed files can be patched without
   touching the TOC. **Fix:** hash file contents, not just rows.

## Assets
None.

## Cost and time
One session (2026-11-08).

## Open questions
- Phase 2: decode `fix_item.dat` records and confirm material ids against in-game names.
- Phase 3: find the enemy drop table.
- Phase 4: decode `shop_setting.dat` sections 111–115 and add a row.
