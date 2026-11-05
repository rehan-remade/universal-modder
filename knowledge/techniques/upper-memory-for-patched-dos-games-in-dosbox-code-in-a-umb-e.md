---
kind: technique
title: 'Upper memory for patched DOS games in DOSBox: code in a UMB, EMS off, an XMS-backed EMS for sound drivers, transient
  modules'
status: working
agents:
- Claude Code (Claude Opus 5.5)
humans: []
date: '2026-11-02'
links: ["https://www.dosbox.com/", "https://github.com/dosbox-staging/dosbox-staging", "https://github.com/joncampbell123/dosbox-x"]
tags: [dos, dosbox, umb, upper-memory, xms, xms-cache, unreal-mode, int21h-hook, ems, int67h, sound-drivers, dma, code-modules, overlays, conventional-memory, binary-patching, x86-16, guest-memory]
---
# Upper memory for patched DOS games in DOSBox: code in a UMB, EMS off, an XMS-backed EMS for sound drivers, transient modules

> When a binary patch has grown so much that it eats the game's free conventional memory, move the new code into an
> upper memory block (UMB): the patched EXE allocates the UMB at start-up, reads its code there from its own file
> and enters the game. With EMS off DOSBox gives one 128 KB UMB; a small XMS-backed int 67h EMS keeps sound drivers
> that need EMS working, and cold code is loaded on demand into a shared slot. Built for Sid Meier's Colonization
> 3.0 (DOS, GOG release, VICEROY.EXE): about 65 KB of new code and modules ran from upper memory by 2026-10-30
> (more since), and the full suites (emulated and in-game, 296 to 349 tests) passed on every release since. Since
> 2026-11-03 the module images are cached in XMS, so a module swap is one memory move instead of a file read.

## When to use it
- Your patch adds code to a DOS game and every paragraph of it is a paragraph less for the game's own allocations
  (measure that first: [Driving DOSBox games from tests](driving-dosbox-games-from-tests-background-input-parallel-sa.md),
  "Measure free conventional memory").
- The game runs in DOSBox (or you can require DOSBox-like settings from your players). On real hardware, upper
  memory depends on the player's memory manager; this note only covers DOSBox.
- Setup used: DOSBox 0.74-2 (the build GOG bundles) for all measurements and tests; DOSBox Staging 0.83 and
  DOSBox-X 2026.10 are supported in the shipped player confs but were checked only by reading their source.
- If the game is an RTLink/Plus overlaid EXE, read
  [Patching RTLink/Plus overlaid DOS executables](patching-rtlink-plus-overlaid-dos-executables-growing-the-im.md)
  first: calls from overlay code into the UMB still need gates the overlay manager recognises.

## How

### What DOSBox gives
`[dos] umb=true` alone is not enough in DOSBox 0.74: UMBs exist only with `xms=true` too. The EMS page frame sits at
E000-EFFF, so `ems` decides how big the one UMB is:

| DOSBox | how we know | `ems=true` | `ems=false` |
|---|---|---|---|
| 0.74-2 | measured (MCB walk in guest RAM) | one block D001-DFFF (0xFFF paragraphs, 64 KB) | one block D001-EFFF (0x1FFF paragraphs, 128 KB) |
| Staging 0.83 | source (`DOS_BuildUMBChain` in `dos_memory.cpp`) | D001-DFFF | D001-EFFF |
| DOSBox-X 2026.10 | source (`xms.cpp`: UMB from D000 up to below the BIOS ROM, cut below the EMS frame only when EMS is on) | D001-DFFF | D001-EFFF |

With `ems=false` the game in this project also had 48 bytes more conventional memory, and 20-turn soak runs took
the same time (83 s vs 82 s mean over 3 runs each). Measure both on your game: what loses EMS matters more (next
sections).

### Loading code into the UMB at start-up
Make the patched EXE's entry point a small loader that runs before the game's own start-up:
1. Save the DOS UMB link state and allocation strategy (int 21h 5802h / 5800h), link UMBs in (5803h, BX=1), set
   the strategy to "upper memory only" (5801h, BX=40h), allocate (48h), and restore both, whatever happened.
2. Refuse to start when there is no UMB, or when the block you got lies below A000 (check the returned segment;
   the emulated start-up test covers that case). Print a message that names the DOSBox
   settings (`xms=true`, `umb=true`, `ems=false`) and exit with an error code. Here the user chose "UMB required, no
   fallback"; a fallback would mean two code layouts to test.
3. If the block is too small (an old conf with `ems=true`), ask DOS for the largest UMB (48h with BX=FFFFh under the
   same strategy) and print a second message, "turn EMS off", instead of the generic one.
4. Read the code from the EXE file itself: store it after everything the loader of the game reads (here behind the
   overlay area, after a zero paragraph), open the EXE by the program path found after the environment block's
   double NUL (the PSP comes from int 21h 62h), seek, read, close. Use your own file handle; don't move a handle
   the game or its overlay manager already has open.
5. Fix up the segment words in the loaded code (the UMB segment is only known now) and far-jump to the game's
   original entry point.

The calls from game code into UMB code need a stub that stays in conventional memory (a far jump whose segment word
the loader fills). Keep those stubs small and count them: they are the conventional cost that remains.

### Claim the rest of upper memory if a manager would use it
After its own block, the loader here allocates every remaining UMB (up to 4 blocks) and keeps them until exit. The
game's overlay manager otherwise built a page heap in upper memory right under the EMS frame and crashed on segment
arithmetic that ran past it (RTLink note, gotcha 10). Look at what your game's memory managers do with free UMBs
before you leave any.

### Turning EMS off when a sound driver needs EMS
In this game the overlay manager uses EMS or XMS only as a small second-level page cache (the same size with
either), so `ems=false` cost nothing there. But the four sound drivers load their sampled effects (a ~970 KB file)
into EMS and have no other path: with `ems=false` they silently skip the digital set-up and the effects are gone.
Instead of patching four drivers, the patched EXE installs a small EMS of its own when no real EMM is present:
- an int 67h handler whose segment has `EMMXXXX0` at offset 000Ah (drivers check the device name through the
  vector's segment, so the handler must sit at offset > 0Ah of its own segment, not inside a bigger block);
- functions 40h-48h, the logical pages kept in an XMS block (XMS move function 0Bh);
- the "page frame" is a 16 KB buffer in upper memory (EC00-EFFF here, at the top of the UMB claim; 16 KB aligned,
  and inside one 64 KB physical page, which ISA DMA cannot cross). Mapping a page copies it from XMS into the buffer.
  While the driver is loading, a map call first writes the buffer it just filled back to XMS. This works because
  the drivers map one page per DMA chunk and a chunk never spans two pages, so the buffer does not change while a
  chunk plays;
- function 46h (version) answers 1.0, so the overlay manager, which wants EMS 3.2 or later, ignores this EMS and
  keeps using XMS;
- not installed when a real EMM exists, so with `ems=true` the drivers keep real EMS.
Proof: an emulated test runs each driver's own init and every sample of its table through the handler and compares
the bytes in the DMA buffer with the sample file; an in-game test watches the page switches in guest RAM.

### Loadable modules: resident and transient code
Even 128 KB fills. Code that runs rarely (screens, dialogs, one-shot parsers) goes into modules stored in the EXE
and loaded on demand into a module area after the UMB code:
- **Resident** modules are loaded once and keep their data (BSS) for the session. Use them for hot or stateful code.
- **Transient** modules share a slot sized by the largest; calling another transient reloads the slot (from the
  EXE, or from the XMS cache below). Their BSS is lost on every swap, so state that must survive goes into a small
  per-module state block (zeroed once) or into permanent data. The upper memory cost of all transients is the
  largest one per slot. This project started with ONE slot and added a second later (below).
- A module image has a small header (magic, id, size, entry count, a fixup list of segment words the loader adds
  the load segment to, the game's load segment for computed pointers) and a near-jump table of entries called
  far. Write far pointers to game code as pointers with listed fixups, not as `call far`/`jmp far` immediates.
- The caller passes a selector (module, entry); the manager returns carry set when the module cannot be loaded (no
  file, read error, bad image, or a transient swap while another transient's call is still on the stack). Every
  caller then keeps the game's original behaviour, so a load failure never crashes.
- Never swap a slot that has a call in progress (transient A calls the game, which calls transient B): A's
  frames would be overwritten. With one slot that means refusing B (carry set); count refusals and fail the tests if
  any appear.
- **A second slot for nested calls** (added 2026-11-03, when such nesting became common): the loader picks the
  empty slot first, else the one not used last, and never one with a call in progress. Keep a call count per slot
  and a small bit stack (one bit per active call: which slot it runs in), so a return lowers the right count. Only a
  third level (both slots busy) gets carry set. Cost here: one more slot of 0x160 paragraphs (5.6 KB) of UMB.
  Tested emulated for real: transient N calls the game, the game calls transient M, M lands in the other slot, and
  a third transient asked for from inside M gets carry set.
- A hook entered from the game becomes a tiny resident thunk: `push bp; mov bp, sp; mov dx, SEL; call MOD_CALL;
  jnc done; <the original call>; done: pop bp; retf`. The module reads the hook's arguments from the thunk's frame.
Moving five cold features into one transient slot freed about 5 KB of upper memory here; later work moved more.

### Cache the module images in XMS
Reading a module from the EXE on every swap costs a DOS open, seek, read and close. The game already requires XMS
(DOSBox gives UMBs only with `xms=true`), so the module images can sit in one XMS block:
- On the **first** module load, find the XMS driver (int 2Fh 4300h / 4310h), allocate one block for the whole file
  range that holds the module images (43 KB here), and copy that range in from the EXE in chunks. The transient
  slots are empty at that moment, so they serve as the copy buffer: no extra memory.
- After that, every load and swap is one XMS move (function 0Bh) into the target segment. Measured in DOSBox 0.74 with
  a small benchmark program in the test DOSBox, for a 5.4 KB module: 687 us per swap from the file, 11 us per XMS
  move (about 60x).
- Keep the file path as the fallback: no XMS driver, a refused allocation, a read or move error, or an image outside
  the cached range all load from the EXE as before. Test each fallback (emulated here, with an emulated XMS driver).
- XMS handles do not belong to a process: DOS frees nothing at exit. Hook int 21h after the cache is filled, and on
  4Ch (exit) and 4B00h (exec: this game runs its ending and intro programs, which re-run the game in the same
  process; see gotcha 5) free the block and restore the old vector, then chain on with the registers unchanged.
  Restore the vector only while int 21h still points at your hook; other functions (including 4B03h overlay loads by
  the sound drivers) pass straight through.
- Costs here: conventional memory 0, a few hundred bytes of manager code, 43 KB of XMS.
- Two risks the design leaves open (reasoned from the design, neither observed or tested in game):
  - an abnormal end that does not come through the int 21h vector (a DOS Ctrl+Break or critical-error abort can
    terminate the program inside DOS) never frees the block, so it leaks until DOSBox restarts;
  - if another program hooks int 21h after the game and is still chained to the hook when the game's upper memory
    is freed, its saved vector points into freed memory. The hook frees the XMS block anyway and leaves that
    vector alone, which is the safe choice for the block but can't fix the other program's chain.

### Unreal mode: possible in DOSBox 0.74, not used
The idea: keep data above 1 MB and read it with 32-bit offsets ("unreal" or big real mode: load a 4 GB descriptor
into a segment register in protected mode, then return to real mode), instead of copying it in and out of XMS. A
386 probe program in the test DOSBox (0.74-2, `core=dynamic`, `cycles=max`, `ems=false`) locked a 64 KB XMS block at
linear 0x110000, turned A20 on and read a marker there through `fs:[ebx]` with a #GP counter on int 0Dh:
- in plain real mode with **no setup at all**, the read worked with 0 faults: DOSBox 0.74 does not enforce real-mode
  segment limits, so any 32-bit offset (prefix 67h) reaches all memory once A20 is on;
- after the unreal switch, and after 200 DOS calls, 200 XMS moves and 3 s of timer interrupts, it still worked
  (DOSBox's DOS, XMS and BIOS are native callbacks and reload no segment register).
It does not carry over: under a V86 monitor (EMM386, QEMM, a Windows DOS box) the protected-mode switch faults, and
HIMEM-style block moves on real machines can reset the cached limit. Code can't run above 1 MB anyway (CS:IP stays
20-bit), so modules would still be copied down, which the XMS cache already does in one move. Verdict here: not
built; only a big table read by hot code without copying could justify it, and then behind a start-up probe with an
XMS-move fallback. Don't rely on DOSBox's missing limit checks by accident either: see the Keystone gotcha in the
RTLink note (stray 67h forms run fine in DOSBox and would fault on an 8086 or 286).

### Budget it at build time
- Keep one record of who owns which part of upper memory (here a ledger that a reservation script edits, plus a
  build check), so parallel work never picks the same "free" gap.
- The build refuses an image + module area bigger than the UMB less anything placed at its top (the DMA buffer).
- Measure in game, read-only, from guest RAM: the MCB chain (the UMB owned by the game, the claim), module loads,
  swaps and refusals.

### Two cheap ways to free resident room
- **Templates into tables.** The start-up code built the 10-byte gates from a byte-for-byte template of all 90
  gates (0x31B bytes) in the start-up window. A 2-byte entry per gate (the hook's target), expanded by the start-up
  code, does the same in 0x1A6 bytes all told; check that the expanded gates are byte-identical to the old build's
  in an emulated start-up.
- **Cold resident code into transient modules.** Survey every resident block first (size, hot or cold, owner):
  cold means rare dialogs, reports, one-off rules. Move the biggest cold bodies into transient modules and keep
  only a thunk and the quick checks resident (here: a rule for abandoned colonies kept its per-site checks and
  fallbacks; the body loads only when a move onto an empty colony happens). Never make a transient bigger than
  the largest one, which sizes the transient slots; leave code that unmerged branches touch for after they merge.
  Here three moves gave 0x6D paragraphs of resident room and 0x253 bytes of the start-up window.

## Not verified
- DOSBox Staging and DOSBox-X UMB ranges come from their source, not a measurement (neither was installed); the
  probe that measured 0.74 should be rerun with their executables. Other forks (DOSBox ECE, SVN builds) not checked.
- Real hardware and real memory managers (EMM386, QEMM, HIMEM-only) not tried; their UMB layout differs.
- The XMS cache was measured and tested on DOSBox 0.74 only; the unreal-mode probe was not run on DOSBox Staging or
  DOSBox-X (their CPU cores may check real-mode limits). The two XMS-cache risks above are reasoned, not reproduced.
- How the effects sound through the emulated EMS: all test runs are muted; the bytes are compared, not listened to.
- The intro program (a separate EXE with its own copy of the driver) finds no EMS with `ems=false`; it played no
  sampled effect in a 120 s run with EMS on either, so nothing seems lost, but that was not proven for every path.

## Gotchas
1. **No UMB although the conf says `umb=true`.** (2026-10-27, found while designing the loader.) **Cause:** DOSBox
   0.74 builds UMBs only when XMS is on. **Fix:** `xms=true` and `umb=true`; name both in the start-up message. This
   also ended the "no EMS/XMS/UMB" stress conf that made overlay bugs deterministic: a game that requires a UMB
   cannot run under it, and the project dropped it.
2. **The code no longer fit in a 64 KB UMB.** (2026-10-29.) **Cause:** with `ems=true` the EMS page frame
   occupies E000-EFFF, so the UMB stops at DFFF. **Fix:** `ems=false` doubles it (table above), plus an XMS-backed
   EMS for the drivers that needed EMS. Ship your own DOSBox confs and launchers: a player who starts through the
   store's own conf (GOG's has `ems=true`) would otherwise only see "not enough upper memory", so when the
   allocation fails, ask DOS for the largest UMB and print "turn EMS off" when one exists but is too small.
3. **Sound effects silently gone with `ems=false`.** (2026-10-29, measured: the drivers' sample handle and frame
   stayed 0.) **Cause:** the sound drivers load their samples only into EMS and skip the digital set-up when the EMS
   check fails; music, which doesn't use EMS, kept playing and the game ran normally, so nothing looked wrong. **Fix:** the int 67h emulation above. Before turning EMS off, search every driver and
   helper EXE for `EMMXXXX0`.
4. **The emulated EMS played the wrong data.** (2026-10-30.) **Cause:** a merge had left a shift count of 0x14
   where the page-to-XMS-offset shift for 16 KB pages must be 14 (0xE); every load and play went to the wrong XMS
   offset. **Fix:** write shift counts in hex in the generator and check the assembled shifts; the build refuses an
   emulated-EMS block that differs from its generator's output.
5. **After a won game the score screen ended at the DOS prompt with "needs upper memory".** (2026-10-31.) **Cause:**
   the game hands over to its other programs with the C library's `exec` (int 21h 4B00h), which loads the next
   program into the same PSP; DOS keeps every block the old program allocated, including its UMB, the claim of the
   rest and the int 67h hook pointing into it. When the chain came back to the game, it found no UMB. **Fix:** the
   loader first walks the MCB chain (UMB link on) and frees every upper block owned by its own PSP; if int 67h points
   into such a block and shows `EMMXXXX0`, it restores the saved vector and frees the emulation's XMS handle first.
   Test every program-to-program handover of the game (intro → game, game → ending → game, demo restarts), not only
   a fresh start. Not freed: XMS handles other code of the old process forgot (they leak once per handover).
6. **Original-EXE comparison runs failed now and then (evm0012) in a few tests.** (2026-10-28.) **Cause:** the
   unpatched game has no claim, so its overlay manager puts a page heap into free upper memory, with the hazard of
   gotcha 10 in the RTLink note. **Fix:** run original-EXE variants with `umb=false`.
7. **The emulator kept running the old code after a module was loaded over it.** (2026-10-28, Unicorn.) **Cause:**
   Unicorn caches translated blocks; reading a new module over code that already ran left the stale translation.
   **Fix:** after each emulated module read, drop the translation cache for that range (`ctl_remove_cache`).
8. **A menu built by a transient module came up late under a loaded test machine, and a test timed out.**
   (2026-11-01.) **Cause:** the first call reads the module from the EXE file, which is slower while many DOSBoxes
   share the machine. **Fix:** in tests, wait for the screen with a timeout that allows for the read (here up to
   10 s for that menu) instead of a short fixed one.

9. **Raising the start of the upper-memory image (to give memory back) broke the build for most shifts.**
   (2026-11-03.) **Cause:** the low code blocks lie over other code at the same offsets in another segment, and the
   linker refuses true clashes (a call target or a trampoline that lands on an instruction start of the code
   underneath). Moving every low block by the same amount moves all those clashes: shifts of 0x210 to 0x270
   failed on a block with no slack; 0x280 fitted. A second trap: a generator that runs before the low-block
   generators checked against their old offsets. **Fix:** give jump tables and fixed entry points a pad constant,
   add nops automatically before labels that land on an instruction start, try the shifts in a loop, and shift the
   stale low entries once so the first regeneration goes through.

10. **The space ledger said 0x329 paragraphs of upper memory were free; the build had 0x179.** (2026-11-05.)
    **Cause:** the ledger still counted reservations of branches that had already merged as separate claims
    (status "reserved"), and some module growth on the integration branch was not booked. **Fix:** measure free
    upper memory from the built image (the linker's own budget report), treat the ledger as the booking record,
    and mark a merged branch's reservations merged right after promotion; the build check then caught the one
    module whose booked size lagged its table entry.

## Seen in
- Sid Meier's Colonization 3.0 (DOS, GOG release; VICEROY.EXE, MSC 6.0 + .RTLink/Plus) binary-patching project
  (no public game note yet).
- Related: [Patching RTLink/Plus overlaid DOS executables](patching-rtlink-plus-overlaid-dos-executables-growing-the-im.md)
  (gates and the shared hook dispatcher for calls from overlays into the UMB) and
  [Driving DOSBox games from tests](driving-dosbox-games-from-tests-background-input-parallel-sa.md) (guest-RAM
  memory measurements, the parallel test harness).
