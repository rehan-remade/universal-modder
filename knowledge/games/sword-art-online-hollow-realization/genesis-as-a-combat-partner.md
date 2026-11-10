---
kind: game
title: "Genesis Unlocker: the story antagonist as a working combat partner (npc_data + NpcEquip data patch, live friend add)"
game: "Sword Art Online: Hollow Realization Deluxe Edition"
games_also: []
game_version: "Steam app 607890, sao_hr.exe PE timestamp 0x59DF33EF, SizeOfImage 0x10A2000, SHA-256 1923F0D8D2CAD559D6AD6E001AF54EA5EA5AA70171323F42D4E1FA3D63699E43; Windows 11 Pro 26100"
platform: windows
engine: native
route: data
tools: ["MSVC 2022 Build Tools (C tool)", "Python 3.11 (own CPK/OFS3 readers, memory scans)"]
anti_cheat: "none; single-player. Edits the user's own data.cpk and the user's own running game."
status: released
agents: ["Claude Code (Opus 5.5)"]
humans: ["BinaryNull"]
date: 2026-11-10
links: []
tags: [partners, npc-data, npcequip, cri-cpk, memory-editing, flags, skills, combat-ai]
---

# Genesis as a combat partner in SAO: Hollow Realization

> Genesis (npc 24) has a save slot and an availability flag but was never meant to be a partner: added as a
> friend he follows you and stands idle. The Genesis Unlocker patches his `npc_data` record and adds a
> `NpcEquip` entry (both borrowed from adult Tia, who shares his two-handed weapon type), then adds him to
> the friend list in the running game. Released as v1.0.0; confirmed in-game that he fights, and that it
> survives save, restart and reload.

## Setup
- SAO: Hollow Realization Deluxe Edition, Steam, Windows 11, exe identity as in the front matter.
- Builds on the CPK append method and readers from the [Zero EXP patcher](zero-exp-patcher-cri-cpk-append.md)
  and the live friend table from the [DLC Partner Unlocker](dlc-partner-unlocker-live-friend-table-and-flags.md).

## Route and why
The missing pieces are data: a weapon, partner fields and a skill list. Combat AI code is shared by all
CChrPartner actors, so giving him a working partner's data is enough. His boss AI lives in CChrEnemyBase
(enemy_data id 8400) and can't be plugged into a partner by data, so that route was dropped.

## How the game works (what we had to learn)
- Genesis: npc_data id 24, slot 319, body model 317, weapon 2500 type 20 (two-handed, same as adult Tia 19),
  gender 1. Availability flag 1161 (exe table at `0x140A55740`). He speaks only in story scripts; no
  script ever adds him as a friend.
- Compared with real partners his record is empty at +0x10/+0x11 (0xFFFF), +0x22..+0x27, +0x2C..+0x2F
  (skill set / learn-skill group; Tia 19/78), and the (value, id) block +0x32..+0x47. He has no `NpcEquip`
  entry and no `trg_talk.dat` section.
- `learn_skill.dat` = 407 × 0x68 records (+0 skill id, +2 group); npc_data +0x2E picks the group. The
  char-table init (`0x1402a41b0`) copies npc_data +0x0C to level, +0x2E to learned skills, +0x2B to char
  +0x10C.
- `NpcEquip` (OFS3, mode 1 (offset, id) entries): u16 npc id, then 0x3C-byte rows (+2 level, +9 condition,
  (tag u16, id u32) slots from +0x18: 0x14 weapon, 0x34 outfit). Adding a section means rewriting the later
  offsets (mode 1 entries have no size).
- Live char table: `sao_hr.exe + 0xB190D8 + slot × 0x12C`; learned skills at +0x08..+0x2F.

## Build steps
1. From the user's own `data.cpk` (SHA-256 checked): copy adult Tia's npc_data +0x10/+0x11, +0x22..+0x27,
   +0x2C..+0x2F and +0x32..+0x47 into Genesis's record (abyss1 file offset 0x3008).
2. Add `NpcEquip` section 24 holding Tia's four always-on rows (weapon tag 0x14, id 2500).
3. Append both files to `data.cpk` and repoint their TOC rows. The backup stores only those two rows and
   lengths; uninstall is refused if something was appended after it.
4. In the running game: points 100, joined 1, flag 1161, and Tia's learned skills if his list is empty.
5. Save. He can be called from the friend list in the field.

## Verification
- In-game by the human: he fights after restart with only the data patch (no live npc_data edits), and
  survives save to a spare slot, restart and reload.
- Offline: install, double install refused, combined with the Zero EXP patcher, uninstall in both orders →
  byte-identical CPK.
- Not verified / not working: Genesis in town (never appears even with 1161; no talk data). Accepted.

## Gotchas
1. **Joined but idle.** **Cause:** he needs the weapon (NpcEquip), the partner npc_data fields *and* a
   learned skill list together. Weapon only, weapon + skills, or fields without weapon all stay idle.
   **Fix:** all three.
2. **His model vanished.** **Cause:** writing char-table role bytes +0x10B/+0x10C (copied from Tia). **Fix:**
   don't; they aren't needed.
3. **One save never spawned him again.** **Cause:** unproven; most likely saved while half-applied live
   experiments were active. **Fix:** test on a spare save slot. A plain add on a clean save works.
4. **Skill table bug in the tool.** **Cause:** a skill entry written at the wrong list offset. **Fix:** list
   offset 0x26 = char +0x2E.
5. **Signature scans for his live npc_data stop matching after the patch.** **Cause:** the pattern was taken
   from the unmodified file. **Fix:** scan for the patched bytes.

## Assets
None.

## Cost and time
One day of sessions (2026-11-08).

## Open questions
- Talk data and town presence for Genesis.
- What npc_data +0x98/+0x26/+0x54 do during actor setup (`0x1402a6780`).
