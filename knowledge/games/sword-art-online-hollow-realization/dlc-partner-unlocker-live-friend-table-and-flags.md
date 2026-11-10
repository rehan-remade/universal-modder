---
kind: game
title: "DLC Partner Unlocker: Rain, Seven, adult Tia, Alice and Eugeo as friends and partners via the live friend table and story flags"
game: "Sword Art Online: Hollow Realization Deluxe Edition"
games_also: []
game_version: "Steam app 607890, sao_hr.exe PE timestamp 0x59DF33EF, SizeOfImage 0x10A2000, SHA-256 1923F0D8D2CAD559D6AD6E001AF54EA5EA5AA70171323F42D4E1FA3D63699E43; Windows 11 Pro 26100"
platform: windows
engine: native
route: other
tools: ["MSVC 2022 Build Tools (C console tool)", "Python 3.11 (own memory reader, script disassembler, CPK/OFS3 readers)"]
anti_cheat: "none; single-player. The Deluxe Edition ships these characters' data; the tool only changes friend state for characters already in the install, through live memory of the user's own running game."
status: released
agents: ["Claude Code (Opus 5.5)"]
humans: ["BinaryNull"]
date: 2026-11-10
links: []
tags: [partners, friends, dlc-characters, memory-editing, flags, script-vm, bytecode, save-checksum, npc-data, npcequip]
---

# DLC Partner Unlocker for SAO: Hollow Realization

> A console tool that adds Rain, Seven, adult Tia, Alice and Eugeo to the friend list of a running game, so
> they can be partners without playing each join event, and puts them in town. It writes friendship points,
> the joined byte and the right story flags into the live game, keeps a backup of every byte, and can undo.
> The game then saves the result normally. Released as v1.1.0; confirmed in-game (friend list, combat, town,
> Tia's look switch, persistence over save and reload).

## Setup
- SAO: Hollow Realization Deluxe Edition, Steam, Windows 11, exe identity as in the front matter. The tool
  refuses any other exe.
- C console tool (MSVC 2022), using OpenProcess / ReadProcessMemory / WriteProcessMemory.
- Research helpers were own Python scripts: a script-bytecode disassembler, a read-only memory dumper, a
  flag setter with backup/undo.

## Route and why
Live memory, not save editing. `GAME00.BIN` (0x80400 bytes, unencrypted) is checksummed (SHA-1 of the file
with bytes 0x00–0x13 and 0x78F10–0x78F17 zeroed, stored at 0x00; `SYSTEM.BIN` = SHA-1 with its first 20
bytes zeroed), and its layout differs from the in-memory struct. Writing the live state and letting the game
save avoids both problems. Running the join scripts themselves would need injection into the script VM;
applying their few effects directly was enough.

## How the game works (what we had to learn)
### Character data
- `sys/sys_data_abyss1/npc_data` (only abyss1 is loaded on PC): +0x12 u16 save slot, +0x17 weapon type,
  +0x2C/+0x2E skill set / learn-skill group, +0x9C body model (`chr/mod/aNNN`), +0xA4 head/hair model,
  +0xBF gender. Names are text 8100000+id in `usa.cpk msg/localize_msg.dat`.
- **Live character table** = `sao_hr.exe + 0xB190D8 + slot × 0x12C` (300 bytes): +0 u16 friendship points,
  +2 u16 level, +4 u32 EXP, +0x08.. learned skills, +0x100 u16 npc id, +0x103 u8 joined (IsJoined at
  `0x1402a4330` tests == 1).
- Slots / npc ids: Asuna 300/1 … Rain 312/13, Seven 313/14, Sumeragi 314/15, Kizmel 315, Premiere 316,
  child Tia 317/18, adult Tia 318/19, Genesis 319/24, Alice 320/25, Eugeo 321/26. Alice and Eugeo exist only
  in the abyss1 npc_data.
- Friendship thresholds 15/100/300/900/2700 for levels 1–5. The setter (`0x14029ffe0`) clamps at 2700 and
  sets joined = 1 at level 2. Level 5 normally unlocks a Steam achievement; direct writes skip it.

### Flags
- During play, story flags are a bit array at `sao_hr.exe + 0xB151DC + 0x280` (bit = flag id, ids below
  0x980). Story progress values: `+0xB151DC + 0x3B0 + idx × 4`. The save-struct global at RVA `0xB145F0`
  is only used on load/save.
- An exe table at `0x140A55740` maps npc id → **availability flag**: 13→1152, 14→1153, 16→1155, 17→1156,
  18→1157, 19→1294, 24→1161, 25→1295, 26→1296. It gates town placement (`0x14025dd60`), the friend-list
  location (`0x140265da0`, −1 = "Unknown"), kill-EXP sharing and quests.
- The friend list (CUiFriendList, `0x14038f0f0`) has a hard-coded refusal for Eugeo (26) when 1296 is off.

### Event scripts
- `usa.cpk script/script` = compiled scripts under base-36 hashed names. `script/debug` has the same names
  plus the original `GG_NNNN.c` name and an import table of native names (1639 names mapped).
- Instruction = u16 opcode; a 4-byte argument follows when `(op & 0x7F) < 34`. 0 push int, 1 push float,
  2 load var, 8 push string, 17/19 store, 26/28 jump, 29 call script function, 32/33 native call
  (void/returning). Argument count is pushed before a call. Native table at .data RVA `0xA53D30`.
- Natives: 82 SetFrnVal, 83 GetFrnVal, 84 SetFriendLv(chr, lv), 85 GetFrnLv, 133 dialogue (speaker = npc
  id), 166 show event CG.
- `event_list.dat` (abyss1, 35 sections, one per character chain): step (a, b) = script `a_b`. Every join
  event calls 84(id, 2) (Rain `51_5200`, Seven `51_5300`, Kizmel `50_7600`, ...). Adult Tia joins in
  catch-up script `11_0000`: if story value 43 ≥ 235 and flag 1294 is off, set 1294 and call 84(19, 2). No
  script ever adds child Tia (18).

### Tia
- Adult Tia (19) is the partner; child Tia (18) uses Premiere's model and only speaks in base-story scripts.
- Look is chosen in code from flags: 1299 → younger form (npc 799), else 1298 → Ch.3 white-cape look
  (npc 795), else 34 → another outfit (npc 798), else the default adult model. Flag 1754 enables "Change
  Appearance" in the friend talk menu, which toggles 1299.
- Town movement depends on `sys/NpcEquip` (OFS3 by npc id; 0x3C-byte rows with a condition at +9 and
  (tag u16, id u32) slots from +0x18; 0x14 weapon, 0x34 outfit). Tia's always-on set has no 0x34 outfit, so
  she stands frozen; the flag-selected sets have one.

## Build steps
1. Check the exe identity, that a save is loaded (slot 300 holds npc id 1) and that flag 1140 (Asuna) is on.
2. For each chosen partner, check the slot's npc id, then write points = 100 (level 2), joined = 1 and the
   availability flag. For adult Tia also set 1298 (Ch.3 look) and 1754 (Change Appearance), and reset child
   Tia's slot to 0 points / not joined.
3. Write a backup of every changed byte and flag bit first; undo restores it.
4. In-game: save, then restart and load so town placement is rebuilt.

## Verification
- In-game by the human: each partner in the friend list, fighting, in the Town of Beginnings, surviving
  save + reload; Tia's Change Appearance switching Ch.3 look ↔ younger form immediately.
- Add / undo / add again checked against the running game by reading the bytes back.
- Not verified: Sumeragi as a partner (set up like a non-combat NPC: no weapon or skill set, no script ever
  adds her). She was added and then removed at the user's request.

## Gotchas
1. **Eugeo added but couldn't be taken out.** **Cause:** the friend list refuses id 26 without flag 1296,
   and v1.0.0 only wrote points/joined. **Fix:** set availability flags (v1.1.0).
2. **Partners listed as "Unknown" location / not in town.** **Cause:** availability flag off. **Fix:** set
   it, save, restart.
3. **Tia frozen in town.** **Cause:** her always-on NpcEquip set has no outfit slot. **Fix:** flag 1298 or
   1299 selects a set with one.
4. **Tia's Ch.3 look had stiff legs, then a bald head.** **Cause:** models a322/a323/a325 are cutscene-only
   (one section, no `_lo` part), and that body expects head model 19, not 16. **Fix:** don't swap +0x9C;
   use flag 1298, which picks a complete npc record.
5. **The first roster guess was wrong** (Sumeragi counted as a friend). **Cause:** guessed from save
   bitsets. **Fix:** read the live table (points + joined).
6. **Save-file offsets didn't match memory.** **Cause:** different layout, plus checksums. **Fix:** live
   memory only.
7. **Story scripts reset some flags.** 1298 and 1299 are saved/restored by several story scripts, so a later
   story event can change Tia's look back.

## Assets
None.

## Cost and time
About two days of sessions (2026-11-07 to 2026-11-08).

## Open questions
- Child Tia (18) as a separate permanent partner.
- Setting friendship level 5 without skipping the per-character achievements.
