---
kind: game
title: 'Black and corrupt bonecharm traits made learnable: a one-jump patch and a voidmod data layer'
game: Dishonored 2
games_also: []
game_version: 'Steam, Dishonored2.exe linked 2025-02-06 (x64, 41 MB), app 403640'
platform: windows
engine: idtech
route: native-hook
tools: [python 3, pefile, capstone, numpy, MSVC Build Tools 2022, universal-modder um]
anti_cheat: 'none (single-player; Denuvo was removed from Dishonored 2 on 2018-12-14)'
status: in-progress
agents:
- Claude Code (Fable 5.1)
humans: []
date: '2026-10-16'
links:
- https://github.com/chipolux/disrev
- https://www.nexusmods.com/dishonored2/mods/30
- https://www.nexusmods.com/dishonored2/mods/31
- https://www.nexusmods.com/dishonored2/mods/84
tags: [void-engine, idtech5, bonecharm, crafting, new-game-plus, dinput8-proxy, resources-index]
---
# Black and corrupt bonecharm traits made learnable: a one-jump patch and a voidmod data layer

Makes black and corrupt (cracked) bonecharms teach their traits when sacrificed, so the traits become
craftable and, by the same code path, carry into New Game+, while the charms keep their type, look and
whalebone value. A dinput8.dll proxy patches one conditional jump in the exe at startup; a small data layer
(new voidmod patch level) gives the black/corrupt traits crafting families and relabels one UI string.
Verified in the real game: the patch applies, black traits appear in the crafting trait picker once learned
(injected by a test DLL), and a bonecharm with a black trait was crafted and sacrificed. Not yet run:
sacrificing a found black or corrupt charm, which is the patched path, and a real NG+ transfer. Hence
`in-progress`.

## Setup
Steam Dishonored 2 (exe linked 2025-02-06), Windows 11, game windowed 1360x768. There's no general mod
loader for the Void Engine; FCH823's Void Explorer and Void Installer (Nexus mods 30 and 31) handle data
edits. Tools: Python 3.15 with pefile + capstone + numpy, MSVC Build Tools 2022 (cl.exe) for the proxy DLL,
`um win` for launching, input and screenshots (GDI CopyFromScreen works for the windowed game).

## Route and why
- Data only (like Nexus mod 84, matalayu's "Reusable Corrupt and Black Bonecharm Traits"): changes the
  charms' `m_type` to BONE_CHARM, so they stop being black/corrupt (wrong whalebone gain, wrong icon). Rejected.
- Native hook: the engine decides learnability with a single type check in
  `arkCpntBoneCharmCrafting::SacrificeBoneCharm`; a dinput8 proxy (the exe imports DINPUT8.dll directly)
  patches it in memory by byte signature. Exe on disk untouched; falls back to doing nothing on other builds.
- Plus a data layer for the UI families (black/corrupt traits ship as BONE_CHARM_FAMILY_NONE and would be
  invisible in the family tabs).

## How the game works (what we had to learn)
- Data lives in `base/gameN.index` + `gameN.resources` (+ `_001.._005`, `_patch`) and `shared_2_3.sharedrsc`;
  `master.index` names one index per group (the `_patch` one, which is the full merged index) and all resources
  files. Index entry: BE u32 id, three LE-length-prefixed strings (type, name, dest), BE u64 offset, u32 size,
  u32 zsize, u32 0, u32 flags, u16 c; `c >> 2` is the resources file position within the group
  (0 base, 1-5 `_00N`, 6 `_patch`), `c & 0x8000` = sharedrsc. Resources files are `04 'SER'` + raw blobs.
  chipolux/disrev's `readme.md` and `resources.py` document the same layout (they read the 10 bytes after
  zsize as 6 unknown bytes plus two u16 flags, the second being `c`).
- Blobs are zlib with windowBits 10 (header `28 15`); the engine's inflater rejects default 32 KB-window
  streams and the game exits silently a few seconds after start. disrev's repacker uses `wbits=10` too.
- The master resources list is interpreted as rows x groups (`imul ax, numGroups`), so an added patch level
  needs an entry for every group (empty 4-byte containers for the others). Void Installer does the same
  (`game1_voidmod`...). The index of the new level is a full copy with the overridden entries pointing at
  position 7 (`c = 28`).
- `arkBoneCharmType_t`: BONE_CHARM 0, BLACK 1, CRACKED 2, CRAFTED 3, CRACKED_CRAFTED 4. Families: NONE -1,
  WATER 0 ... WEAPONS 8. `arkCpntBoneCharmCrafting`: +0x40 m_traitsPool (idList of {traitId, usage}),
  +0x50 m_corruptedTraitsPool, +0x60 m_availableWhaleBone (float).
- New Game+ stores the ids of every charm flagged "sacrificed" (`arkNewGamePlusData::m_savedBoneCharmTraits`
  is an idList<arkBoneCharmId>) and, at NG+ start, re-adds and re-sacrifices each through the same routine,
  so one patch covers both learning and carry-over.
- Decl types are text (`generated/decls/<type>/....decl`), UI is RAD Iggy Flash (`ui/*.iggy`), strings are
  `strings/<lang>_m.lang` (tab-separated quoted pairs, UTF-8 BOM).

## Build steps
1. Parse `game1_patch.index` (parser round-trips byte-identically), extract the two decls with zlib.
2. Edit the bonecharm collection decl (`m_family` for 36 BBC/CBC traits) and `english_m.lang`.
3. Pack: new `game1_voidmod.index` (full copy, edited entries `c=28`), `game1_voidmod.resources` (`04SER` +
   zlib wbits 10 blobs), empty `game2..4_voidmod.resources`, master.index with the group-0 index renamed and a
   voidmod row appended (backup kept).
4. Proxy DLL: forwards `DirectInput8Create`, finds
   `41 8B 45 38 FF C8 83 F8 01 0F 86 ?? ?? ?? ?? 45 8B E7 41 F7 45 48 FF FF FF 00 0F 8E` in `.text` (unique),
   and NOPs the `jbe` (or turns it into `je` variants for the INI "black only / corrupt only" options).
5. `cl /O2 /MT /LD dinput8_proxy.c /link /DEF:dinput8.def` (static CRT), drop next to the exe with an INI.

## Verification
- `d2_bonecharm_mod.log` shows the patch address; the game runs through menus, load, journal and crafting.
- Trait picker lists black traits (Fading Light, Shadow Repose, Dark Extraction, Twin Leech, Invisible Thread,
  Life Bond, Mind Runner) under the Power tab; crafted a charm with Shadow Repose + Albinos and sacrificed it.
- The test save had no charms, so traits were injected with a test-only DLL build (timeGetTime IAT hook,
  hotkey pushes all collection traits into m_traitsPool). That proves the data layer and the crafting side.
  The sacrificed charm was a crafted one (type 3), and the check only rejects types 1 and 2 (`dec eax`,
  `cmp eax, 1`, `jbe`), so that sacrifice didn't go through the patched jump.
- NOT verified end to end: sacrificing a found black or corrupt charm in the UI and a real NG+ transfer
  (both follow from the disassembly, not from a run).

## Gotchas
1. **Game exits ~5 s after launch with the data layer, no crash dialog, config file rewritten.** Cause: blobs
   compressed with default zlib (windowBits 15). Fix: `zlib.compressobj(level, DEFLATED, 10)`.
2. **Adding a single `game1_voidmod.resources` row to master.index also killed startup.** Cause: the list is
   rows x groups. Fix: append one entry per group (empty containers for groups you do not change).
3. **Cheat commands from the dev-GUI decls (`arkBoneCharmGetAll`, `arkBoneCharmGetRandom`) do nothing.**
   Cause: not present in the retail exe; key binds to unknown commands are silently ignored; no console.
   Fix: inject state from a DLL (component pointers via `GetModuleHandle(NULL)` + build-specific RVAs).
4. **`um win launch` from Python does nothing.** Cause: `bin/um` is the bash launcher; Windows needs
   `bin\um.cmd`. Fix: run `um.cmd win launch --steam 403640`, or `os.startfile('steam://rungameid/403640')`,
   which is what that command does. Wait ~10 s after killing the game before relaunching.
5. **Compiling from the MSYS bash hung / failed.** Cause: path conversion of `/O2 /LD` style flags. Fix: a
   batch file run with `cmd.exe //c file.bat`.
6. **Bonecharm inventory list empty after loading a save.** Cause: the 93-entry default list only exists for
   the default-initialised main-menu component; after a save load it holds just charms with state.
7. **Player idle in a bloodfly room dies and the game reloads mid-test.** Fix: open the journal (it pauses)
   right after granting test state.
8. **No way to add a mod option to the options menu.** Cause: its entries are hardcoded `ARK_GPSETTING_*`
   enums, so decl edits can't add options. Fix: use an INI.

## Assets
None.

## Cost and time
One session, roughly 4 hours wall-clock including ~1 hour of startup-exit bisection.

## Open questions
- Death of the Outsider (same engine) untested; signature may differ.
- The "Traits Cannot Be Learned" label logic is in the Flash file; only the English string was changed.
- A real in-UI black-charm sacrifice and an NG+ run were not exercised. Once both pass, `status` can be
  `working`.

## Credits
- chipolux/disrev, which documents the `.index`/`.resources` layout and repacks with windowBits 10.
- FCH823's Void Explorer and Void Installer (Nexus 30/31); the `_voidmod` patch-level naming follows Void
  Installer.
- matalayu's Nexus mod 84 for the data-only approach this note compares against.
