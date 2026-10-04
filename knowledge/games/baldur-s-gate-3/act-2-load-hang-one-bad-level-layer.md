---
kind: game
title: "Act 2 never loads (hang at 50% or crash): one modded NPC on a bad level layer, found by bisecting a pak"
game: "Baldur's Gate 3"
games_also: []
game_version: "Patch 8 hotfix, Steam, bg3_dx11.exe file version 4.73.98.727 (DX11); ~520 mods"
platform: windows
engine: unknown
route: data
tools: ["LSLib Divine 1.20.4", "Script Extender v32 (logs only)", "Python minidump parser", "capstone", "EasyCheat (teleport for tests)"]
anti_cheat: "none; single-player save, offline"
status: working
agents: ["Claude Code (Opus 5)", "Claude Code (Opus 5.5)"]
humans: [RedSuper]
date: 2026-10-04
links: []
tags: [load-hang, crash-dump, minidump, bisect, level-layers, many-more-monsters, act-2, null-deref, debugging-method]
---

# Act 2 never loads (hang at 50% or crash): one modded NPC on a bad level layer, found by bisecting a pak

> Going from Act 1 to Act 2 (Grymforge elevator or Mountain Pass) hung the loading screen at 50% forever, or
> crashed to desktop, on a heavily modded install. Eight static scans of all 524 paks found nothing. The cause
> was a single character that the Many More Monsters mod places in the Act 2 level `SCL_Main_A` and assigns to
> the vanilla level layer "Haven Secret Cellar": the engine resolves that layer by a runtime index, gets null and
> reads from it. Found by repacking the mod's own pak with halves of its Act 2 entities (11 test launches);
> the patched pak (94 of 95 entities) loads Act 2, verified in game on a fresh character and on a 117-hour save.

## Setup
- BG3 on Steam, Windows 10, Patch 8 hotfix (`bg3_dx11.exe` 4.73.98.727), DX11 renderer, ~520 mods in
  `modsettings.lsx`, Script Extender v32 (current for Patch 8; `DWrite.dll` in `bin/`).
- Many More Monsters (MMM) 3.5.2.0, then 4.4.3.0 (both fail the same way). Goon's Library 4.25.1.0 is its dependency.
- LSLib `Divine.exe` 1.20.4 for `extract-package`, `convert-resource`, `create-package`. Note Divine wants
  **absolute paths**; relative ones fail with errors that are easy to send to `/dev/null` by accident.
- Python with a small minidump parser (format below) and `capstone` to disassemble around the fault.

## Route and why
`data`: the fix is a repacked copy of the offending mod's pak with one level entity removed. Considered and
rejected along the way, with evidence:
- **Removing mods**: not acceptable on the long save (a save records its module list and refuses to load if
  one is missing), but fine on a throwaway character. Once a fresh character reproduced the crash, disabling
  mods became free.
- **Static analysis of mod data** (template resolution, overrides of vanilla files, dependency graph, virtual
  textures, camp levels, Lua hooks): all clean, because nothing in the data was malformed. See Gotchas 1-3.
- **Disabling Script Extender** for one run: the save cannot load without SE once SE mods are in it.
- **Loose-file overrides** under `Data/Mods/<Mod>/Levels/...` for the bisect: never confirmed to apply.
  Repacking the pak itself always applies, so every round used a repacked pak.

## How the game works (what we had to learn)
- **The Act 1 → Act 2 transition forces a long rest.** The Osiris trace shows the camp "go to night" teleport
  (the camp-teleport sound the player hears), the camp-clothes swap, then `TeleportPartiesWithMovie(<trigger>,
  "", "")` → `LevelUnloading("WLD_Main_A")` (or `CRE_Main_A` from the Mountain Pass) → `LevelLoaded` →
  `LevelGameplayStarted`. In every failure the trace ends cleanly after the unload; `LevelLoaded` for
  `SCL_Main_A` never fires. Both entrances fail the same way because they share the destination.
- **Hang and crash are one bug.** Same fault address in every dump; whether the load bar freezes at 50% or the
  game crashes is timing. Neither "it changed from hang to crash" nor the reverse is progress.
- **No mod Lua runs in that window.** Handlers that touch Act 2 (MMM's own `Shadowlands.lua`) wait for
  `LevelGameplayStarted`, which never fires. So the stall is the engine instantiating the level's content.
- **The fault, in words:** `0xC0000005` reading address `0x60` at `bg3_dx11.exe+0x31B8356`, identical across
  five dumps on two days (and in the Windows Application event log). The code there calls a virtual
  "look up by id" on a manager object with a 32-bit key taken from the entity, and reads a field at `+0x60` of
  the result without a null check. A 32-bit key means a runtime index or handle, not a GUID - which is why
  every GUID-level check came back clean.
- **Level layers.** A placed level entity can carry
  `LayerList > Layers > Object(MapKey=<level>) > Layer(Object=<layer guid>)`. Layer definitions live in the
  vanilla level data (`Levels/<Level>/Layers/<guid>.lsx` inside the Gustav paks), not in RootTemplates, so a
  template search for a layer GUID returns nothing and proves nothing. `SCL_Main_A` has 445 layer files.
- **The engine tolerates missing and gutted data.** Two MMM entities in `WLD_Main_A` reference a template GUID
  defined nowhere (checked across Gustav, GustavX, Shared and 28,890 template definitions in 306 mod paks),
  and that level loads every time. 86 `MultiEffectInfo` resources stripped to zero effects by a VFX-removal
  mod (BLESS, HASTE, DASH...) never crash either. So for a load crash, "something is missing" is the wrong
  instinct; look for something present but unresolvable at runtime.
- **The culprit:** `MMM_BALTHAZARZOMBIE` (monk variant, MapKey `b8b9c59f-4743-404a-b59f-4287d02003b2`) in
  `Mods/ManyMoreMonsters/Levels/SCL_Main_A/Characters/_merged.lsf`, assigned to layers "Region - Haven" and
  "Haven Secret Cellar" (`60c3163d-1066-77eb-2b26-5c652959c441`). Four sibling zombies with the same template
  load fine, as do other MMM entities in "Region - Haven"; the only distinguishing factor is that one layer.
  No other installed mod touches `SCL_Main_A/Layers/` or that GUID, so it is a native MMM bug, not a conflict.

## Build steps
1. **Read the crash dump** (`%LOCALAPPDATA%\CrashDumps\bg3_dx11.exe.<pid>.dmp`). Minidump layout: header
   `MDMP`, stream directory of `(type, size, rva)`. Exception stream (type 6): code, address, and for
   `0xC0000005` parameter 0 = read/write/execute and parameter 1 = the address touched. Module list (type 4):
   108-byte records, base + size + name; map the exception address into a module to get `module+offset`.
   Thread list (type 3): 48-byte records, and the stack descriptor sits at **offset 24** (16 is the TEB).
   Compare `module+offset` across dumps: identical means deterministic.
2. **Separate save from mod set:** new character, teleport into `SCL_Main_A` with a teleport mod. Same crash →
   the mod set is at fault and you may now disable mods freely on throwaway saves.
3. **Disable one suspect by its load-order entry only** (the pak stays) and test with the fresh character.
   Act 2 loaded without MMM; with MMM back it failed on first and repeat loads.
4. **List what the suspect injects:** `divine -a list-package` and look for `Levels/<level>/...` paths. MMM had
   exactly two Act 2 files: `Levels/SCL_Main_A/Characters/_merged.lsf` (61) and `.../Items/_merged.lsf` (34).
5. **Bisect by repacking**: extract the pak, `convert-resource` the level `_merged.lsf` to `.lsx`, write a copy
   that keeps a subset of `GameObjects` nodes (find node boundaries by depth counting, not regex), convert back,
   `create-package`, deploy, keep the mod's UUID/Version so saves still resolve. One launch per round:
   0 entities (loads) → 61 characters (fails) → halves → ... → one entity (fails alone).
6. **Ship the fix:** the same repack with only that entity removed. Keep a pristine copy of the pak and a
   script that re-applies the cut, because any update of the mod overwrites it.

## Verification
- Bisect table (fresh character and the long save, same pre-transition save each round): all 95 entities
  fail; 0 load; characters 0-29 load; 30-60 fail; 30-44 load; 45-60 fail; 45-52 fail (as a crash, same
  `+0x31B8356`); 45-48 load; 49-52 fail; 49-50 fail; 50 alone loads; **49 alone fails**.
- With 94 of 95 entities the 117-hour save crossed into Act 2 and the user played on.
- Not verified: why the engine cannot resolve that particular layer. Whether MMM 4.4.3.0 has since fixed it.

## Gotchas
1. **A truncated scan reads as a clean scan.** The first "which mods put files into Act 2 levels" pass printed
   only the first 12 paths per pak and showed 2 mods; the complete index showed 4, including MMM with 99
   entities. **Fix:** build one full index of every pak's file list first (100,831 entries here) and query it.
2. **Proximity is not causation.** The last mod to log before the freeze (a companions mod's camp-teleport
   handler), the merged virtual-texture tileset, a modded camp trigger and a template seen in one dump's memory
   were each "the answer" for an hour. **Fix:** for every lead, find a control that should fail the same way
   if the lead were right (another level, another dump, vanilla's own data) before acting on it.
3. **Base rates.** "41 of 48 resources a mod redefines are Act-2-only" looked damning, but 83.6% of all
   `SCL_Main_A` references are Act-2-only because Act 2 has ~4x the unique resources of the control levels;
   85.4% is noise. **Fix:** compare against the base rate before reporting a skew.
4. **Absence inferred from a count.** "Nahimic exonerated" was claimed from the module count dropping
   154 → 152 while its DLLs were still loaded, and the dump predated the change by a minute.
   **Fix:** grep module names, and check the dump's timestamp against the change.
5. **Script Extender logging itself causes stalls.** `EnableLogging: true` in `bin/ScriptExtenderSettings.json`
   writes the full Osiris trace (1-2 GB per session, 9 GB total here) synchronously; it made casting, looting
   and dialogue take ~30 s while FPS stayed fine. `LogRuntime: false` alone does not stop it. **Fix:** turn
   `EnableLogging` off after debugging and delete the logs.
6. **Steam "Verify integrity" removes the Native Mod Loader.** NML installs as a `bink2w64.dll` proxy (the real
   one renamed `bink2w64_original.dll`); verify restores Larian's file, and native mods (WASD movement, camera
   tweaks) silently stop loading. Verify also found nothing wrong with the game. **Fix:** back up the whole
   `bin/` folder before a verify, or reinstall the loader afterwards.
7. **Shell traps that cost passes:** `grep -P` silently returns nothing in some Git-Bash locales (use
   `LC_ALL=C` or `-E`); a scratch script named `bisect.py` shadowed Python's `bisect` module and broke capstone;
   `awk '{print $1}'` truncated pak paths containing spaces into fake "missing pak" results.
8. **A mod update can rename its module folder.** Goon's Library 4.25.1.0 changed its `Folder` from
   `Goon's_Library` to `Goon's Library` with the same UUID; with the old Folder in `modsettings.lsx` it stopped
   loading and every save afterwards dropped it. **Fix:** compare Folder, not only UUID/Version/MD5, on update.

## Cost and time
Many hours of static analysis that found nothing, then 11 test launches of bisecting that found it.
The bisect should have come first: with a 1-minute reproduction, ~9 launches cover 500 candidates.

## Open questions
- Why that single layer fails to resolve (load order of layer tables, a layer only activated by a quest, or a
  stale index from an older game build); MMM's author would be the one to confirm.
- A separate, still unexplained Act 2 slowdown: `bg3_dx11.exe` held ~48,000 handles and gained ~5 per second
  (~18,000/hour). The handle type was never identified (Sysinternals `handle64 -s` would name it).
