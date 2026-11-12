---
kind: game
title: Naming the RE4 (2005) PC exe from the GameCube decompilation
game: Resident Evil 4
games_also: []
game_version: 'Steam UHD, original bio4.exe of 2018-01-27, 9,126,456 bytes, SHA-1 3ddec5c068c0c968c95a5694a44389b8b8518205'
platform: windows
engine: native
route: native-hook
tools: [Ghidra 12.1.4 headless, Python 3.10, MSVC 2019 (header compile test)]
anti_cheat: none (single-player)
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-12'
links:
- https://github.com/adonis-singh/re4
tags: [reverse-engineering, ghidra, decompilation, address-map, rtti, vtables]
---
# Naming the RE4 (2005) PC exe from the GameCube decompilation

We named about 5,900 of the 18,479 functions in the PC `bio4.exe` (≈49% of its code by size; enemy code ≈82%)
and 116 globals. The names come from the complete GameCube decompilation (adonis-singh/re4). The result is a
plugin header of RVAs and a named Ghidra database. Anchors are text strings, RTTI vtables, routine tables and
`this`-pointer evidence; the call graph spreads the names further. Six held-out runs found the automatic matches
95–99% correct. Gameplay classes are hand-checked and pinned: player, inventory, enemy base, all enemies,
weapons, camera, over-the-shoulder camera and scenery collision. Hook sites that existing plugins proved at
runtime landed in the expected functions.

## Setup
- Static analysis only, on a copy of the untouched 2018 exe (Steam keeps it as `Bin32\bio4.exe.bak` when mods
  patch `bio4.exe`). No game launch needed.
- Ghidra 12.1.4 headless (`analyzeHeadless -import ... -postScript`), about 6 minutes of auto-analysis.
- The GameCube decompilation provides `config/G4BE08/symbols.txt` and `sym_map.tsv` (names, GC addresses,
  units), `src/` and `include/` (class declarations with virtual order).

## Route and why
- **No PDB or symbols ship with the exe**, so the names have to come from the GameCube build.
- **Signature tools (FLIRT/BSim) need the same compiler.** The decomp targets PowerPC CodeWarrior while the exe
  is x86 MSVC, so we matched structure instead.
- **Structure available to match on:**
  - strings, with ~55 `__FILE__` paths of the form `...\bio4pc\src\...`;
  - call graphs and numeric constants;
  - MSVC RTTI (327 classes);
  - the decomp's function-pointer tables;
  - singletons passed as `this`.

## How the game works (what we had to learn)
- **The PC port is the Xbox 360 HD port's code:** build path `RE4HD\Development\project\bio4pc`, platform layer
  `Hap\XBOX360\`.
  - Input, rendering, sound, saves and options are rewritten and have no GameCube twin.
  - Everything else is the GameCube logic, very close to the decomp.
- **Link layout:** each source file stays contiguous. Files are ordered alphabetically (case-insensitive) within a
  folder (`game/` atari→tv_mode), but functions are shuffled inside a file. A second "PC-modified" block holds
  cam_ctrl, item, pl_* and sscrn.
- **Every call goes through an incremental-link `jmp` thunk** (0x40xxxx). The call graph only works after
  resolving thunks.
- **Single inheritance vtables:** the base's slots come first (overridden in place), then new virtuals in
  declaration order, with overloads as separate slots. The PC port added slots in some classes:
  - `cPlayer`: one at slot 9.
  - `cObjWep`: slots 9 and 16, and the GC's non-virtual `reloadable()` became virtual (slot 19).
  - Per-weapon PC classes such as `cObjShotgunWep33` replace the GC per-file classes.
- **Enemy ids:** door and rack ids are the GC ids + 0x10 (door 0x51 vs 0x41).
- **Routines:** enemy R0/R1 routine tables survive as data (e.g. Em10_R1_move_tbl with 220 entries). The camera
  routines are a `switch` in `CameraControl::Move`.
- **Many small GC helpers and constructors are inlined.** Some static constructors sit in gaps Ghidra never
  turned into functions; find them by searching code for their vftable address.

## Build steps
1. **Export:** a Ghidra postScript writes, per function, its direct callees (thunks resolved), referenced strings,
   globals, immediates, `.rdata` float constants, and the `ecx` loaded before each call (constant, or `[abs]`
   through register copies). A second script dumps all RTTI vftables.
2. **Decomp side:** per function, string literals, call names, numeric literals and referenced globals.
   - Multi-line `#define`s must be skipped with their `\` continuations, or the macro text bleeds into the next
     signature.
   - Keep overloads apart.
3. **Matcher phases:**
   - Pinned names and anchors: hand-checked pins, function-pointer tables, vtable slots.
   - Unique strings.
   - Call-graph voting.
   - Unit-range scoring (only units alphabetically between the nearest matched neighbours; callee/caller
     agreement + IDF-weighted constants + size ratio; mutual best with a margin).
   - Singleton `this` evidence.
4. **Globals:** voted from co-references in matched pairs.
5. **Apply and curate:** apply names to Ghidra (creating functions where needed) and generate a curated C header
   of RVAs.

## Verification
- **Holdout:** hide 30% of the string anchors and rerun. 93% correct at first, 97–99% after the structural
  anchors.
- **Runtime-proven addresses from two existing plugins** land where expected: `pPL`, `CamCtrl`, `IdSys` and
  `EmMgr` exactly; the camera midhook inside `CameraMove`; the money-drop hook in `RandomItemCk`.
- **Hand reading:** several hundred functions were read against the GC source. Constants match (e.g.
  `GameAddPoint`'s 10999 clamp and /1000), and so do bodies (e.g. `cObjShotgunWep33::moveFire` vs GC
  `cObjShotgun::moveFire`).
- **Header:** compiles cleanly under MSVC /W4.
- **Not verified in the running game:** the names themselves. Check a non-pinned name against your use before
  hooking it.

## Gotchas
1. **Call graph looks random.** **Cause:** incremental-link thunks. **Fix:** resolve every call/vtable target
   through its thunk.
2. **The matcher names stay put, then move between reruns.** **Cause:** score ties and overloads (`num`×3,
   `bulletNum`×3). **Fix:** pin checked names in a file loaded first; select overloads by source order
   (`#k`) or by file (`<unit>|<name>`); block wrong addresses and mark inlined GC functions so the matcher can't
   put them elsewhere.
3. **Seven different routines all parsed as `em10AtkCk`.** **Cause:** a multi-line macro before them. **Fix:**
   follow `\` continuations when skipping preprocessor lines.
4. **Vtable naming is off by one in some classes.** **Cause:** PC-added virtuals. **Fix:** align on purecall
   slots and on each subclass's GC override set (which GC methods each weapon defines → which PC slots it
   overrides).
5. **The "PadRead" match is wrong.** **Cause:** the PC replaced input with its own routine. **Fix:** trust only
   names whose callers fit, and expect no GC twin in the input, render, sound and save layers.
6. **Function-pointer tables don't align.** **Cause:** tiny table-only bodies (empty `br_Dummy`) are not
   functions in Ghidra. **Fix:** accept any `.text` pointer in a table run.
7. **A global lands a few bytes off** (`RoomData` at +2). **Cause:** member accesses dominate the vote. **Fix:**
   use the `ecx` (`this`) evidence for singletons.

## Assets
None.

## Cost and time
One long session (one day).

## Open questions
- **The PC-only layers (input/render/sound/saves), CRI middleware and the CRT** are mostly unnamed. They need
  library signatures or manual reversing.
- **About 385 small enemy helpers** are unplaced (likely inlined), plus the 33 Ganado-variant init wrappers,
  which nothing references directly.
- **Room scripts (st*/r*.cpp), effects and menus** are matched but not hand-pinned.
