---
kind: game
title: "SSC Counter: the save's hidden Sword Skill Connect combo total shown on the Status screen (dbghelp.dll proxy)"
game: "Sword Art Online: Hollow Realization Deluxe Edition"
games_also: []
game_version: "Steam app 607890, sao_hr.exe PE timestamp 0x59DF33EF, SizeOfImage 0x10A2000, SHA-256 1923F0D8D2CAD559D6AD6E001AF54EA5EA5AA70171323F42D4E1FA3D63699E43; Windows 11 Pro 26100"
platform: windows
engine: native
route: native-hook
tools: ["MSVC 2022 Build Tools (dbghelp.dll proxy, /MT)", "Capstone (disassembly)", "Keystone (assembling stubs)", "OFS3 TOOL by Liquid-S", "CriPakTools (CRILAYLA reference)"]
anti_cheat: "none; single player only (the game also has online co-op and PvP). The exe on disk, game data and saves are never modified; one call is redirected in memory."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["BinaryNull"]
date: 2026-11-14
links: ["https://github.com/Liquid-S/OFS3-TOOL", "https://github.com/esperknight/CriPakTools"]
tags: [phyreengine, ssc, sword-skill-connect, ui, status-screen, proxy-dll, dbghelp, code-cave, skill-unlocks, save-data]
---

# SSC Counter for SAO: Hollow Realization

> Adds "SSC Counter: N" under "Max SSC" on the Status screen. N is the total number of Sword Skill Connect
> combos you have started. The game already tracks and saves this total, as progress toward skill unlocks
> like "perform SSC combo X times", but never displays it. A `dbghelp.dll` proxy redirects one text lookup
> in memory and reads the number from the loaded save every time the screen draws. v1.1.0 is the current
> version; confirmed in-game (the logged total climbed from 1,954 to 3,200 over one play session).

## Setup
- SAO: Hollow Realization Deluxe Edition, Steam, Windows 11, exe identity as in the front matter. No ASLR,
  image base `0x140000000`.
- MSVC 2022 Build Tools: `cl /O2 /MT /W4 /LD`. Capstone and Keystone were used during research.
- Shares the proxy-DLL pattern of the [Smith Radar Percent](smith-radar-percent-winmm-proxy.md) and
  [Zero EXP](zero-exp-patcher-cri-cpk-append.md) mods.
- Multiplayer: SAO:HR also has online co-op and PvP for up to four players. The mod only changes what your
  own screen shows, but it was tested in single player only (Not verified below); keep it out of online
  sessions with other people unless they all agreed.

## Route and why
- **Proxy DLL** (`dbghelp.dll`), because the game loads it from its own folder at startup and it is not
  already taken: the Zero EXP mod uses `dinput8.dll`, and Smith Radar Percent uses `winmm.dll`. All three run together.
- **v1.0.0** counted on its own: it hooked the SSC chain increment, counted 0→1 transitions (one per
  combo), seeded the total from the save and kept it in `SSC_Counter.txt`.
- **v1.1.0** dropped the hook and the file. While seeding from the save it became clear that the save's
  value *is* a running total that the game raises by 1 per combo. Reading it live is simpler, and it
  follows save slots and save/quit correctly. Only the Status-screen label patch remains.

## How the game works (what we had to learn)
- **Status screen labels**: a label loop calls GetText (`0x14036E7F0`, text id → string) at `0x1404017C9`.
  "Max SSC" is text id **505103**.
- **SSC chain**: `0x14020DBC4` adds 1 to a u16 at character + `0xF88A` (the current SSC chain length;
  `r14` = character). A chain going 0 → 1 is a new combo. The character type (vfunc 0x1A8; player = 1, 11
  or 19) separates the player from partners. v1.0.0 used this; v1.1.0 doesn't need it.
- **Skill-unlock progress in the save**: function `0x1403643A0` returns the loaded save's skill block. In
  single player this is the local data the unlock checks read. Layout:
  - from +0: up to 32 EX-skill-tree entries × 12 bytes (u8 tree id, u32 progress at +8);
  - from +0x180: skill entries × 12 bytes (u32 skill id, u32 progress at +4);
  - u16 tree-entry count at +0x3180, u16 skill-entry count at +0x3182. Both 0 = no save loaded yet.
- **The SSC total**: tree entry id **0x1E** (the Soaring Slash tree, whose unlock condition is SSC combos)
  counts every SSC combo, once per combo, and keeps counting after its skill unlocks. Skill entries
  **0x1E1402** and **0x1E1403** count only 3-hit and 5-hit combos; they are read as a fallback, taking the
  largest value.
- Partners' SSCs are not counted, and a combo counts once however long the chain gets.

## Build steps
1. Generate `exports.h`: one `/export` pragma per export of the Windows dbghelp.dll, forwarding by the same
   ordinal to `\\.\GLOBALROOT\SystemRoot\System32\dbghelp.dll`, so the game's crash reporting still works.
2. In DllMain (process attach): check the process name is `sao_hr.exe`, the PE timestamp and SizeOfImage,
   and that the call site at RVA `0x4017C9` holds `E8 22 D0 F6 FF`. If any check fails, patch nothing and
   log the reason.
3. `VirtualAlloc` an executable block within ±2 GB of the image (so a rel32 call reaches it). Write a stub
   that saves the text id, calls GetText, then calls `StatusLabel(text, id)`.
4. `StatusLabel` returns the text unchanged unless id == 505103. For that id it reads the save block and
   returns `"<text>\nSSC Counter: N"` from a static buffer. Reads are wrapped in SEH; a missing save shows
   the plain label.
5. Overwrite the 5-byte call with a call to the stub, flush the instruction cache, and log "patched".
   Install = copy `dbghelp.dll` next to `sao_hr.exe`; uninstall = delete it.

## Verification
- In-game by the human: the line appears under Max SSC. In v1.0.0 the starting total matched the save
  (1,929) and rose with each combo (1,929 → 1,931). v1.1.0 shows the save's own value, rising during play
  (the log shows 1,954 → 3,200 across one session); separate save slots show separate totals.
- Runs together with the Zero EXP `dinput8.dll` and Smith Radar Percent `winmm.dll`.
- The log records "patched" and every change of the value.
- Not verified: behaviour in online co-op (the save accessor is the single-player local block).

## Gotchas
1. **Counting it yourself duplicates game state.** **Cause:** the save already keeps the total (as
   skill-unlock progress). **Fix:** read it live (v1.1.0). A side file goes out of sync with save slots
   and with quitting without saving.
2. **The 3-hit / 5-hit skill entries undercount.** **Cause:** they only count combos of that length.
   **Fix:** use tree entry 0x1E, which counts every combo; keep the skill entries only as a fallback.
3. **The value is garbage before a save is loaded.** **Cause:** the block exists but is empty. **Fix:**
   treat tree count 0 or > 32, or skill count 0 or > 1000, as "no save" and show the plain label.
4. **rel32 call can't reach a normal heap allocation.** **Cause:** x64 heap/DLL memory may be more than
   2 GB from the image. **Fix:** probe `VirtualAlloc` at addresses near the image base.
5. **Proxy DLL clashes.** **Cause:** only one `dbghelp.dll` can be in the folder. **Fix:** a different
   proxy name per mod (dinput8, winmm, dbghelp here).

## Assets
None.

## Cost and time
Two days of sessions (2026-11-12 to 2026-11-13), v1.0.0 → v1.1.0.

## Open questions
- Other unlock-progress counters in the same save block (kills, skill uses) could be shown the same way.
