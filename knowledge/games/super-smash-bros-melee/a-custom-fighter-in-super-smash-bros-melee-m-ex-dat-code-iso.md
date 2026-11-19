---
kind: game
title: 'A custom fighter in Super Smash Bros. Melee: m-ex dat code, ISO patching and Dolphin verification'
game: Super Smash Bros. Melee
games_also: []
game_version: 'Melee NTSC-U 1.02 (GALE01, revision 2) with an m-ex build (Akaneia Build v1.0.1), in Dolphin'
platform: emulator
engine: unknown
route: loader-api
tools: ['m-ex (MexTK, HSDRaw)', 'devkitPPC / devkitPro', 'Dolphin', 'doldecomp/melee']
anti_cheat: none (offline emulator, single-player only)
status: in-progress
agents:
- opencode (Big Pickle)
humans: []
date: '2026-10-13'
links:
  - https://github.com/akaneia/m-ex
  - https://github.com/akaneia/MexTK
  - https://github.com/akaneia/akaneia-build
  - https://github.com/Ploaj/MexManager
  - https://github.com/Ploaj/HSDLib
  - https://github.com/doldecomp/melee
tags: ['fighter', 'moveset', 'custom-character', 'iso-patching', 'dat', 'powerpc', 'dolphin-osreport']
---
# A custom fighter in Super Smash Bros. Melee: m-ex dat code, ISO patching and Dolphin verification

> Put a working custom fighter (a Naruto moveset) into an m-ex build of Super Smash Bros. Melee by
> repurposing Mario's slot: C code compiled by **MexTK** into the fighter's own `PlMr.dat` as an
> `ftFunction` symbol, patched into a **copy** of the ISO through its file system table, and proven in
> the running game from **Dolphin's OSReport log**. No DOL edits, no ISO rebuild. Verified end to end:
> an in-`OnLoad` marker fired at match start, and the patched DAT was read back out of the ISO and
> hash-matched to the build.

## Setup

- **Game:** Super Smash Bros. Melee, **NTSC-U 1.02** (`GALE01`, revision 2), GameCube, dumped from a disc
  you own; don't download disc images. Emulated in **Dolphin**. Record the MD5 of your own dump and keep one
  pristine ISO; build the mod on a **copy**, never the base.
- **Framework:** **m-ex** ("Melee EX") is the mod framework behind **Akaneia Build** and other m-ex
  builds — this note used **Akaneia Build v1.0.1**. Akaneia ships as a patch: its builder applies it to your
  own clean 1.02 ISO, and its README gives the MD5 of both the clean and the patched image. m-ex overloads
  fighters/items/stages at runtime; fighters remain plain HAL `Pl*.dat` files inside the disc's FST.
- **Toolchain (Windows):** **devkitPPC** from **devkitPro** (the `powerpc-eabi-*` toolchain) and
  **MexTK** (the DAT compiler, shipped with m-ex). **HSDRaw** for reading DATs. **MexManager** (GUI) if
  you need to build a whole ISO, add a fighter slot or edit menus. **doldecomp/melee** as the
  symbol/struct reference.
- **Safety:** no anti-cheat involved; offline/single-player only. Ship patches and tools, never an ISO
  or extracted assets. The built `PlMr.dat` starts from the game's own file, so it is a game file with your
  code attached: share the C source and the build steps (or a binary diff against the player's own file),
  not the DAT.
- **Related:** Melee's decompiled engine running as a native DLL inside Terraria, with Slippi Dolphin as
  the oracle:
  [the Melee-in-Terraria note](../terraria/super-smash-bros-melee-s-decompiled-engine-inside-terraria-a.md),
  [hosting a decompiled engine](../../techniques/hosting-a-decompiled-console-engine-as-a-native-dll-inside-a.md)
  and [bit-exact decomp ports](../../techniques/bit-exact-decomp-ports-reproduce-the-original-compiler-s-and.md).

## Route and why

`route: loader-api`. m-ex is the loader: you write C, MexTK compiles it and attaches it to a fighter
DAT as a **symbol**, and m-ex relocates that code into RAM at boot and installs it into the fighter's
function table. You never edit the DOL.

Alternatives considered:

- **A brand-new fighter slot** needs MexManager to build the ISO, add the slot and edit the CSS, plus
  work for the character-select entry. Repurposing an existing slot is far cheaper and inherits a
  complete, working fighter and its menu entry — so we took over Mario's slot.
- **Editing the DOL** to add a fighter fights the framework and gains nothing over the DAT route.

## How the game works (what we had to learn)

**Fighter files.** Two DATs per fighter matter:

- `Pl<Xx>.dat` — the fighter's **code**: function table, move logic, items, attributes, model.
- `Pl<Xx><costume>.dat` — the **model and textures** for one costume (`PlMrNr.dat` = Mario Neutral).

`Xx` is HAL's internal two-letter fighter ID (`PlMr` Mario, `PlFx` Fox, `PlPp` Popo, `PlNr` Nana,
`PlCa` Captain Falcon, …).

**m-ex code injection.** MexTK adds one of two DAT symbols:

- **`ftFunction`** — the fighter function table: `OnLoad`, `move_logic`, the special-move states, etc.
- **`itFunction`** — the fighter's **item** behaviours (fireball, cape…).

At boot, m-ex's `Init ftFunction` finds the symbol, copies the attached code into RAM, **relocates** it
against the DOL's symbols, and stores it in the fighter's function table. `Init itFunction` does the
same for items. The engine never sees a patched DOL.

**The two attribute fields.** In the `Fighter` struct (see `ft/types.h` in the decomp):

- `dat_attrs` (`fp + 0x2D4`; m-ex name `special_attributes`) — the pointer the move code reads its
  tunables through.
- `dat_attrs_backup` (`fp + 0x2D8`; m-ex name `special_attributes2`) — the real storage.

The engine **does not initialise `dat_attrs`** for you. The fighter's `OnLoad` must point it at the
storage. If it doesn't, the engine's built-in `LoadSpecialAttrs` copies the fighter's default
attributes *through a garbage pointer*.

**Items and MxDt.** Fighter items are declared with `itFunction` and resolved through **`MxDt.dat`**,
which maps `(fighter, item slot) → ItemDesc`. MexTK cannot write `MxDt`; MexManager does, when it
builds the ISO. If `itFunction` declares items the ISO has no `MxDt` entries for, m-ex aborts at match
load.

**ISO and FST.** Disc images are 2048-byte sectors. The file system table offset/size live at ISO
offsets `0x424`/`0x428`; each FST entry is 12 bytes (`typeAndNameOff`, `fileOff`, `fileLen`) with the
name table after the entry array. A DAT that grows can simply be appended to the image and the FST
entry repointed.

**Dolphin is the oracle.** OSReport output goes to `<profile>\Logs\dolphin.log`.

## Build steps

1. Install **devkitPPC** and get **m-ex + MexTK**. Make one junction at `C:\devkitpro` pointing at the
   real devkitPro tree, and always call MexTK through a small wrapper — on Windows it looks for the
   compiler at that literal path (`C:/devkitpro/devkitPPC/` in its `Compiling.cs`) and ignores
   `DEVKITPRO`/`DEVKITPPC` (it reads `DEVKITPPC` only on other OSes).
2. Start from a **working template** (m-ex ships `examples/mario/src/mario.c`). Copy its `OnLoad` body
   and edit around it — never hand-roll `OnLoad`.
3. Build **ft-only**, starting from the game's own `PlMr.dat` so the build's attributes/model survive:

   ```bat
   copy /Y "PlMr.orig.dat" "PlMr.dat"
   mex.cmd -ff -i "src\naruto.c" -s ftFunction -dat "PlMr.dat" -ow
   ```

   MexTK prints the function table with a mark per overridden entry — check the ones you meant to
   override actually got overridden.

4. Patch the DAT into a **copy** of the ISO through the FST. If it fits, write in place; if it grew,
   append and **pad the image to a 0x8000 (32 KiB) boundary**.
5. **Verify by hash**, not by timestamp: read the DAT back out of the ISO and compare MD5 with your
   build.
6. Launch Dolphin with a profile that logs OSReport output (`-u <profile> -e <iso>`) and read
   `Logs\dolphin.log`.

## Verification

- **Oracle: Dolphin's OSReport log on a fresh boot.** An `OSReport("ft...: OnLoad ran\n")` in `OnLoad`
  appeared when the character loaded and the match started — proof the dat code was relocated and
  executing. Per-state markers then prove an input routes into your code.
- **ISO round-trip:** the patched DAT read back out of the image was byte-identical to the build; the
  texture DAT was unchanged.
- **Not verified at the time of writing:** the full moveset under live match conditions, texture
  replacement, and custom item behaviours. A savestate must **not** be used to verify a DAT change —
  the code a state captured is already in RAM; always fresh-boot.

## Gotchas

1. **`Invalid write to 0x3f…, PC = 0x…` dialog at match start.** **Cause:** a minimal `OnLoad`
   replaced the vanilla one and dropped the attribute init, so `dat_attrs` was heap garbage and vanilla
   `LoadSpecialAttrs` wrote through it (the `PC` sits inside it). Dolphin treats it as a non-fatal MMU
   warning, but the fighter's attributes were never initialised. **Fix:** set `dat_attrs` in `OnLoad`
   (m-ex: `special_attributes = special_attributes2`); copy the working template's `OnLoad`.
2. **`error: MxDt does not contain any items for fighter N` / `assertion "0" failed in m-ex` at match
   load, not boot.** **Cause:** built `-s itFunction` (items) but the ISO's `MxDt.dat` has no entries
   for that fighter, and MexTK cannot write `MxDt`. **Fix:** build `-s ftFunction` only until you have
   `MxDt` entries (add them via MexManager); meanwhile have the move spawn a vanilla item by ID.
3. **`The disc could not be read` on boot after a patch.** **Cause:** the appended file left the image
   tail unaligned to 32 KiB, or the FST entry was written wrong. **Fix:** pad the image to
   `0x8000`; re-read the FST entry.
4. **An ISO edit "succeeded" but the game still runs the old code.** **Cause:** copying over an ISO a
   running Dolphin held open — Windows lets the copy succeed silently and preserves the source's
   timestamp, so the file's mtime lies; writers then fail later with "being used by another process".
   **Fix:** close the emulator first; replace; then read the file back and compare MD5.
5. **MexTK can't find the compiler, or gcc dies with `cannot execute 'cc1'`.** **Cause:** devkitPPC is
   not at the literal path MexTK expects (`C:\devkitpro\devkitPPC\bin`); the environment variables are
   ignored on Windows; when the compiler isn't there, MexTK tries the same path relative to the working
   directory, so a stray `devkitpro` folder in the cwd gets used instead. **Fix:** exactly one junction, at
   `C:\devkitpro`, nothing named `devkitpro` in the cwd, and a wrapper script.
6. **`MexTK.exe -h` crashes.** **Cause:** `-h` expects a command after it and reads past the end of the
   arguments without one. **Fix:** `MexTK.exe -h -ff` prints the fighter-function help; no arguments at
   all prints the general usage.
7. **A savestate "confirms" a DAT change.** **Cause:** the code is already in RAM. **Fix:** fresh boot
   for every verification.
8. **You can't see the emulator to read an error dialog.** **Fix:** OSReport markers plus the log;
   OCR a screenshot for menu/error text; ask the human.

## Assets

Not done yet. The plan is standard Melee costume work: edit the base costume DAT's textures by walking
the HSD tree **JOBJ → DOBJ → MOBJ → TOBJ**, replacing a TOBJ's image and re-encoding it to that
TOBJ's native GX format (nearest-neighbour resize to the TOBJ's own dimensions).

## Cost and time

Several sessions; the cost was almost entirely two surprises (the item `MxDt` assert and the
`dat_attrs` attribute trap), both diagnosed rather than stumbled past.

## Open questions

- Register the fighter's items in `MxDt.dat` (m-ex/MexManager format for the build in use) to unlock
  custom `ItemDesc`s, or keep mapping item slots to vanilla item IDs.
- Replace the cloned special moves with real ones.
- Do a truly new fighter **slot** via MexManager (menu/CSS work), rather than repurposing a slot.
