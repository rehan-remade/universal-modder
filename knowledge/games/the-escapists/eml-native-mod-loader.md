---
kind: game
title: 'EML: a native mod loader for The Escapists (Clickteam Fusion 2.5)'
game: The Escapists
games_also: []
game_version: 'Steam build 1513201 (v1.37), TheEscapists_rus/eur/pol.exe, Fusion 2.5 Unicode runtime build 286'
platform: windows
engine: native
route: native-hook
tools: [CTFAK 2.0 (patched), Ghidra 12.2, MinHook 1.3.4, Dear ImGui 1.93.0, LuaJIT 2.1, sol2 3.5.0, MSVC 14.44]
anti_cheat: none (single player; Steam leaderboards only)
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-02'
links: ["https://github.com/CTFAK/CTFAK2.0", "https://github.com/TsudaKageyu/minhook"]
tags: [clickteam, fusion, winmm-proxy, lua, mod-loader, items, crafting, custom-maps]
---
# EML: a native mod loader for The Escapists (Clickteam Fusion 2.5)

> EML is a Forge-style mod loader for The Escapists (2015). A `winmm.dll` proxy loads a core DLL that hooks
> the Fusion runtime in memory, so the exe on disk is never changed. Mods are folders with a `mod.json` manifest,
> Lua scripts, asset overrides and INI patches. Through registries they add new items with sprites, crafting
> recipes and custom prisons, and they get mechanic events (routine, health, craft). Every feature was checked
> in the running game with screenshots plus the loader log.

## Setup
- Steam app 298630, build 1513201 (v1.37). Steam starts `TheEscapists.exe`, a language launcher, which spawns
  `TheEscapists_rus.exe`, `_eur` or `_pol`. Those can also be started directly.
- The game is Clickteam Fusion 2.5 Unicode, x86, D3D9 (`mmf2d3d9.dll`). The exe carries a Fusion pack overlay,
  and `mmfs2.dll` and the extension `.mfx` files are unpacked to `%TEMP%\mrtXXXX.tmp` at start.
- Build: VS 2022 Build Tools (MSVC 14.44, x86), CMake 3.24 or newer. LuaJIT is built with `msvcbuild.bat static`.

## Route and why
- **No community loader exists.** The knowledge base had nothing for this game or Fusion.
- **Data-only modding was ruled out.** The user asked for more than texts and images, and recipes turned out
  to be hard-coded in events anyway.
- **Patching the exe was ruled out.** The user asked for no changes on disk.
- **Chosen route: native hooks.** A `winmm.dll` proxy (193 forwarded exports) loads `eml\eml_core.dll`, which
  checks the exe's SHA-256, scans for signatures, and hooks with MinHook.

## How the game works (what we had to learn)
- **Event dump.** The game logic lives in Fusion events. They were dumped with a small CTFAK plugin to readable
  text. Stock CTFAK cannot decrypt this game: the RC4-like key material (name + copyright + editor path) must be
  **truncated to 128 bytes**. The real key was read from live memory (`CRunApp+0x26C`) to find this.
- **Struct offsets.** Runtime structures match the Clickteam `MMF2SDK_Unicode` headers compiled for x86 with
  pack 2. Compile `offsetof` for RunHeader, headerObject, RunObject (rCom 0xB8, rAni 0x1CE), OI (oiOC +0x14)
  and CRunApp (`m_ois` +0x19C) instead of guessing. The event engine is in the exe (inner loop at rva 0x45E60;
  one logical tick per change of `rhLoopCount`).
- **nvar.mfx.** This old-SDK ANSI extension keeps most game state as named variables in a `std::map`: day and
  time, Cash, Heat, `Inv1..6`, and the current routine name in the string `Lesson`. Its action jump table
  (from the exported `GetRunObjectInfos`) gives "set value" (index 0) and "set string" (index 8). Hooking
  those two gives access to almost every game state change.
- **Data files.** `Data\items/data/speech_<lang>.dat` are INI files read with `GetPrivateProfileStringW`
  (through kcini), so virtual INI keys can add data without touching files. Every 60 s the game hashes their
  text and compares the result with `val.dat`. On a mismatch it leaves the prison, so never override them as
  files.
- **Recipes** are about 99 events that compare `CraftString` (slot item ids sorted as strings, e.g.
  `-1_24_74`) with literals. Mod recipes swap in a "carrier" vanilla recipe string and then swap its output id.
- **Item sprites.** An item's picture is an animation direction of the `Items` / `Items_HUD` Actives. Free
  slots are IDs 281..287. Animation tables use 16-bit relative offsets inside the OC block, and missing
  anims or dirs hold the negated offset of their substitute. New directions need a copied OC (allocated with
  the runtime's `malloc` through `mvCallFunction` 100), and images come from `mvCallFunction` 116
  (CreateImageFromFileW).
- **Custom prisons** are `.cmap` files in `Documents\The Escapists\Custom Maps`, listed with FindFirstFileExW.
  They are the decrypted `.map` text plus `[Info] Rdy=1`. Vanilla `.map` files are Blowfish-ECB, key
  `mothking`, with little-endian 32-bit halves.

## Build steps
1. Clone the EML repo and put MinHook, ImGui, sol2 and LuaJIT into `tools/src`.
2. Build LuaJIT with `msvcbuild.bat static`.
3. Configure and build: `cmake -S . -B build -A Win32`, then build `install_game` and `package_release`.
4. Copy `winmm.dll`, `eml\eml_core.dll` and `EML Launcher.exe` into the game folder, and mods into `mods\`.

## Verification
- **Oracle:** the real game driven by `um win drive` (menus, the tutorial desk and crafting, a custom prison
  run), plus `um win shot` screenshots that were looked at, plus `eml.log` lines from every subsystem.
- **Verified:**
  - Overlay input and Lua events, including `day_change` (log "day 1 started").
  - INI patches (title strings) and file overrides (ground texture).
  - Mod recipe crafts with mod sprites and names: Soap Shiv and Herbal Tea.
  - Custom prison: 9 guards instead of 5, and the mod's intro text.
  - Events: routine, health and craft.
  - Configs and the launcher, including play without mods (no `eml.log` written).
- **Not verified:**
  - The hash function behind `val.dat`.
  - Mod sprites in the main prison frame: they were seen in the tutorial frame only, with a forced-anim
    fallback.
  - Prison variants other than Center Perks.

## Gotchas
1. **CTFAK says the file is broken or decrypts garbage.** **Cause:** the decryption key material is truncated
   to 128 bytes in this runtime. **Fix:** patch CTFAK's Decryption to truncate.
2. **Mouse clicks do not reach the ImGui overlay.** **Cause:** input goes to the child window
   `Mf2EditClassTh`, not the main window. **Fix:** subclass the children and map their coordinates to the
   D3D device window.
3. **The CreateFileW hook fails silently.** **Cause:** `MH_Initialize` had not run yet. **Fix:** initialise
   MinHook before the VFS hooks; hook kernelbase, not kernel32.
4. **The mod sprite showed a vanilla icon after a frame change.** **Cause:** images created with
   CreateImageFromFile are dropped when the frame changes, and their handles are reused. **Fix:** recreate the
   sprites on every frame change.
5. **Image handles in a loaded OC do not match CTFAK's.** **Cause:** the runtime renumbers the bank at load
   (237 → 209). **Fix:** never map CTFAK image handles onto live data.
6. **The tutorial showed the wrong icon for IDs above 255.** **Cause:** the tutorial frame maps them to anim 7,
   the prison frame to anim 10. **Fix:** pin the anim and direction of mod items each tick.
7. **A custom map gives "missing or corrupted".** **Cause:** the load frame checks that the file exists
   (GetFileAttributes) and that `[Info] Rdy` is non-zero. **Fix:** hook GetFileAttributesW/ExW for the virtual
   files and add `Rdy=1`.
8. **Overriding `items_*.dat` gets you kicked out of the prison after about 60 s.** **Cause:** the integrity
   check ("Chexington" event group) against `val.dat`. **Fix:** serve keys virtually through the INI reads and
   keep the raw file intact.
9. **nvar `Lockdown` stays 0 during the Lockdown routine.** **Cause:** it is not the lockdown flag. **Fix:**
   detect lockdown from the routine (`Lesson`, `[Routines]` key 3).
10. **`WritePrivateProfileStringW` loses non-ASCII text.** **Cause:** the file is created as ANSI. **Fix:**
    create it with a UTF-16 BOM first.

## Assets
The example sprites (16×16) and the ground checkerboard are generated by small Pillow scripts in the example
mods. No game art is used.

## Cost and time
One long session (about a day of agent time): recon and dumps, then 5 loader milestones, each committed
separately.

## Open questions
- Hash function behind `val.dat` (parser expression 121 over `"l0l_" + file text`).
- More than 7 new items needs new anim slots plus patched "Set Item Graphic" logic.
- Spawning items directly (`Inv1..6` look writable; untested).
