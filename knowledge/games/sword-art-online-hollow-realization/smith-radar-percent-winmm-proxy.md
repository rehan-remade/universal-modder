---
kind: game
title: "Smith Radar Percent: blacksmith stats as percentages on the Craftsman Data radar (winmm.dll proxy), plus the enhancement formula"
game: "Sword Art Online: Hollow Realization Deluxe Edition"
games_also: []
game_version: "Steam app 607890, sao_hr.exe PE timestamp 0x59DF33EF, SizeOfImage 0x10A2000, SHA-256 1923F0D8D2CAD559D6AD6E001AF54EA5EA5AA70171323F42D4E1FA3D63699E43; Windows 11 Pro 26100"
platform: windows
engine: native
route: native-hook
tools: ["MSVC 2022 Build Tools (winmm.dll proxy)", "Python 3.11 (table decoding, exe patch prototype)"]
anti_cheat: "none; single-player. The exe on disk is not modified; the proxy patches one call in memory."
status: released
agents: ["Claude Code (Opus 5.5)"]
humans: ["BinaryNull"]
date: 2026-11-10
links: []
tags: [blacksmith, enhancement-formula, ui, proxy-dll, winmm, code-cave, localize-msg]
---

# Smith Radar Percent for SAO: Hollow Realization

> The Craftsman Data screen shows each smith's five stats only as a radar shape. This mod adds the value as
> a percentage beside each label ("Precision 80%"). It is a `winmm.dll` proxy that redirects one text call to
> a small code cave in memory. Released as v1.0.0; confirmed in-game. The research behind it also decoded the
> smith tables and the enhancement success formula, written up below.

## Setup
- SAO: Hollow Realization Deluxe Edition, Steam, Windows 11, exe identity as in the front matter.
- MSVC 2022 Build Tools; the DLL is built `/MT` and imports only KERNEL32.

## Route and why
First tried a text-only mod: putting the numbers into the profile name (text 8110000+npc in
`usa.cpk msg/localize_msg.dat`, which *is* the Craftsman Data name). It worked, but the user wanted the
numbers beside the radar labels. A direct exe patch also worked; the release uses a proxy DLL because Nexus
discourages exe edits. `winmm.dll` was chosen over `dinput8.dll` so it can sit beside the
[Zero EXP patcher's](zero-exp-patcher-cri-cpk-append.md) dinput8 proxy.

## How the game works (what we had to learn)
### Tables (`sys/sys_data_abyss1/`, the only folder loaded on PC)
- `smith_param.dat`: 22 × 20 bytes: u16 idx, u16 npc id, u16 unknown, five stat bytes in UI order
  Precision / Technique / Growth / Knowledge / Recycling (1–5), up to five craftsman skill ids (0xFF = none).
  The radar shows stat × 20 %. The abyss1 copy gives many smiths +1 Precision over the other copies.
- Stat meanings (from their help text): Precision = enhance/transform success, Technique = stat bonus on
  enhancement, Growth = smith EXP, Knowledge = skill imbue chance, Recycling = materials returned.
- `blacksmith.dat` (OFS3, 7 sections): section 3 = 30 craftsman skills × 72 bytes (activation %, item filter
  bytes, effect type, amount); section 0 = 48-byte enhancement recipes, base chance float at +0x2C (weapons
  +1..+9: 100, 90, 80, 75, 70, 65, 60, 55, 50).
- smith_param records for npc 301–303 are town guards, not usable smiths.

### Enhancement success (routine `0x140184260`)
- chance = base(step) × (1 + Precision term) × (1 + sum of triggered skill bonuses) × level factor.
  Precision term for P1..P5 (table at RVA `0x805530`): −0.6, −0.3, 0, +0.25, +0.5. Level factor = smith
  level minus *item level*, clamped ±10, mapped to ×0.9..×1.4. Roll = random 0..99.
- Skill filters: +0xF = 1 weapon-only, +0x10 = 1 armor-only (checked by code); the "Weapon/Armor Smithing"
  filter bytes are not checked, so those apply to every item. Three skills carry the armor-only byte and
  therefore never trigger on weapons.
- Item **rarity is not read** on this path; it only affects the Col cost.
- With global flag 0x52 on, displayed success is 100 and a "Chance of Master Stroke" line appears.
  Alchemic stones add a flat bonus and force the max-stat result, and one stone is consumed per enhance.

### Radar labels
- Craftsman Data setup is `0x14044c2c0`. Its label loop at `0x14044c67b` reads five label text ids (table
  at `0x1408372f8`, order P, R, T, K, G), fetches each string and passes it to a SetText function that
  copies it.
- The patch redirects the SetText call at `0x14044c6a6` to a 124-byte cave in end-of-.text padding
  (RVA `0x7fdf60`) that formats "%s %d%%" with the stat value via the CRT `_snprintf` from the IAT, into a
  buffer in the caller's frame, then calls the original SetText.

## Build steps
1. Proxy: generate forwarders for all 181 winmm exports to the System32 copy (GLOBALROOT path), so the
   game's own winmm calls still work.
2. In DllMain: check PE timestamp, SizeOfImage and the exact original call bytes; write the cave, then
   rewrite the call; log the result.
3. Drop `winmm.dll` next to `sao_hr.exe`. Remove it to uninstall.

## Verification
- In-game by the human: labels show percentages for each smith.
- The exe-patch prototype was reverted and the test exe hash compared against a clean copy.
- Not verified: the meaning of the three Technique-row values; what sets flag 0x52; the stone quirk when
  success + bonus exceeds 100.

## Gotchas
1. **Profile-name text mod changed the wrong place for the user's taste.** **Cause:** 8110xxx is the
   Craftsman Data *name*, not the labels. **Fix:** code patch on the label loop.
2. **Exe edits not acceptable for Nexus.** **Fix:** the same patch applied in memory by a proxy DLL.
3. **dinput8.dll was already taken by another mod.** **Fix:** proxy winmm.dll instead.
4. **Not every smith in smith_param is a usable smith.** **Cause:** three records belong to town guards.
   **Fix:** exclude npc 301–303 from smith comparisons.

## Assets
None.

## Cost and time
One day of sessions (2026-11-09).

## Open questions
- What sets global flag 0x52 (it is also read in kill-EXP code).
- Exact effect of the Technique row values on non-Master-Stroke results.
