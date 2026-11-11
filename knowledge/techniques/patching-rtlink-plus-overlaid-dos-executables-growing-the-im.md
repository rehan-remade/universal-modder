---
kind: technique
title: 'Patching RTLink/Plus overlaid DOS executables: growing the image and calling new code safely from overlays'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-25'
links: ["https://github.com/eb4x/ghidra-plugin-rtlink", "https://github.com/keystone-engine/keystone", "https://github.com/capstone-engine/capstone"]
tags: [dos, rtlink, overlays, vm-manager, binary-patching, mz-exe, trampolines, code-cave, x86-16, memory-pressure, conventional-memory, page-cache, umb, gates, hook-dispatcher, relocations, keystone, assembler, 8086-compatibility, calling-convention, general-midi, stack-buffer-overflow, text-drawing, register-clobbering]
---
# Patching RTLink/Plus overlaid DOS executables: growing the image and calling new code safely from overlays

> How to add new code to a DOS game linked with .RTLink/Plus (Pocket Soft's "VM" overlay manager, common in
> early-90s MicroProse titles) and call it from overlay code without the manager returning into the wrong
> code. Learned while binary-patching Sid Meier's Colonization 3.0 (VICEROY.EXE, MSC 6.0 + .RTLink/Plus 6.10):
> first about 14 KB of new code reached from 40+ hook sites inside the image (2026-10-25), then (2026-10-27 to
> 11-01) most new code moved to an upper memory block, reached through gates and one shared hook dispatcher;
> verified by emulated tests of the manager's rules and full suites of 296 to 334 tests per release.

## When to use it
- The EXE contains the string `Internal error in .RTLink(R)/Plus run-time code.` (or similar), has a small
  MZ image followed by a chain of "page" records, and most game code lives in those pages.
- You need more code than fits in caves, or you need to call new code from overlay (page) code.
- Format reference: eb4x/ghidra-plugin-rtlink,
  [`docs/rtlink-format.md`](https://github.com/eb4x/ghidra-plugin-rtlink/blob/main/docs/rtlink-format.md)
  (Apache-2.0) - read it first. It also has a Ghidra loader for the pages.

## How

### The layout in brief (from the reference, confirmed on VICEROY)
- MZ main image (resident code, the VM manager, DGROUP), then the overlay area: a chain of page records from
  the first paragraph past the MZ image. Each record header is 8 words (total paragraphs, overhead paragraphs,
  frame, relocation start index, three list counts, codeview). List 1 entries are (offset, segment index)
  sites inside the page that hold resident segment values.
- A segment list (32-byte descriptors) inside the image; the dword at +8 is a page record's file offset.
- `$$VMTAB` sits just before it; one word there is the resident extent in paragraphs (image + uninitialised
  data + stack), and the manager range-checks segments against it.
- Overlay code calls resident code and other pages through manager stubs; the manager loads, discards and
  moves pages as memory requires, and fixes up return addresses of callers whose page moved.

### Growing the image (room for new code)
- Appending code to the file image doesn't work: past the image is uninitialised data (zeroed at startup)
  and the C startup frees memory beyond the stack. Insert paragraphs *inside* the image instead, before a
  segment S of your choice (VICEROY: just before DGROUP, after the last code segment).
- Inserting N paragraphs before S shifts S and everything after it, so add N to every segment value >= S:
  - MZ relocation targets and the relocation entries' own segments;
  - overlay list-1 sites that name such segments;
  - SS in the MZ header, and the `$$VMTAB` resident extent;
  - the segment list's page file offsets (the overlay area moves N*16 bytes down the file);
  - the image size in the header.
- Check the result with a layout test: zero growth must reproduce the original byte for byte; after growth
  every DGROUP reference and page offset must be shifted and the page code otherwise unchanged.
- Build the patched EXE from a definition file (edits at ORIGINAL offsets, mapped through the growth; new
  code placed in the block) rather than by hand, so it can be rebuilt and verified at any time.
- MZ relocation slots are limited by the header's free space. Avoid using them for new code: write the
  block's segment into your code at run time from CS (a small `fixsegs` routine called first).

### Calling new code from overlay code: the trampoline layout the manager recognises
Overlay code never calls a far address directly: it calls a manager vector (in VICEROY `lcall 110D:0D91`;
eb4x's doc writes it `210d:0d91` because Ghidra loads the image at segment 0x1000, and calls the call-plus-jump
pair a resident-target trampoline), which rewrites the offset word of the calling `lcall` and continues through
the far jump that follows it.
On a call, the manager also inspects the caller's call target to decide whether the call comes from an
overlay page; only then does it protect the caller's return address against the page being discarded.
- **Working layout (18 bytes):** the hook site in the overlay does `lcall NEWSEG:t`, and
  `t: call fixsegs; jmp far v; v: lcall <vector>; ljmp NEWSEG:hook`. The manager follows a `call near` only
  when a `jmp far` comes next, so this chain reaches the vector call and is recognised. fixsegs fills the
  segment words of the `jmp far`, the `lcall` and the `ljmp` from CS.
- A literal `lcall <vector>; ljmp seg:off` entered at the lcall (segment words relocated by the MZ table)
  also works.
- **Broken layout (13 bytes):** `t: call fixsegs; lcall <vector>; ljmp NEWSEG:hook`. The manager doesn't
  follow `call near` + `lcall`, treats the call as coming from resident code, and leaves the overlay's return
  address unprotected (gotcha 1).
- Emulate the manager's test: for every hook site, decode the chain from the call target the way the manager
  does and assert it reaches the vector call. This catches a bad layout in seconds.

### Calling code in an upper memory block: gates
Once the new code lives in a UMB (see
[Upper memory for patched DOS games in DOSBox](upper-memory-for-patched-dos-games-in-dosbox-code-in-a-umb-e.md)),
its segment is only known at run time and the overlay manager must still see a vectored call. Each call from an
overlay goes through a 10-byte **gate** in a small block that stays in conventional memory: the literal
`lcall <vector>; ljmp UMBSEG:hook` (the second working form above, entered at the lcall), with the `ljmp` segment
filled in by the start-up loader. The overlay site keeps its `lcall NEWSEG:gate` form, so run the emulated
call-target test over every gate too.
- Calls from resident code need only a 5-byte direct `ljmp`.
- Calls between code still in conventional memory and the UMB code go through small far stubs both ways (a near
  call can't cross segments); UMB code must not read conventional data through CS.
- The gate block has a fixed size. The one-shot start-up code can sit in the gate area of the EXE image and be
  overwritten by the gates once it has run (gotcha 16).

### One gate for many hooks: a dispatcher keyed by the return address
Gates are scarce (118 slots here, 6 left at one point); MZ relocation slots are scarcer (3 left). Cold hooks can
share ONE gate:
- every such overlay site calls the same gate, which jumps to a dispatcher in the UMB;
- the dispatcher checks that its far return address points just past an `lcall NEWSEG:<that gate>`, builds a key
  from the low 4 bits of the return offset plus the 6 bytes after the call, looks it up in a table generated at
  build time, and enters the hook with a near `ret`, so registers, flags and stack are exactly what a gate of its
  own would leave;
- the build keeps a site on its own gate when the 6-byte window holds a relocated word or a patched segment word
  (it would read differently at run time), when the site is a far jump or a resident caller, or when two hooks
  share a key. Hot hooks (per pixel, per tile, per move, AI scoring) keep their own gate on purpose: the lookup costs
  about 20 instructions plus about 12 per table entry before the match;
- count hits per site, and misses with their return address, in a small header; a miss stops the game in a loop
  rather than running the wrong hook, and the tests read the counters from guest RAM and require zero misses;
- **the manager may hand you its own return vector instead of the caller's address** (gotcha 12). After the first
  call through a vectored stub, RTLink returns through a fixed vector in its own segment and keeps the real return
  address in a stack of 10-byte records (offset, segment, overlay, previous slot, segment). When the dispatcher sees
  that vector and the manager's "replaced slot" variable names its own gate, it reads the caller from the top
  record. The build asserts that the manager bytes it relies on are unchanged.

Result here: 47 sites of 41 hooks moved onto one gate; free gates went from 6 to 46.

### Refuse patches on relocated words at build time
A word that the DOS loader (MZ relocation table) or the overlay manager (a page's list-1 entries) relocates is
rewritten when the code loads. A patch that puts other bytes there runs as garbage, but only once that page is
loaded, so emulated tests that don't model relocation miss it (gotcha 11). Make the build compute every relocated
word of the patched EXE and refuse any patch byte on one, unless the word is still a resident segment operand or is
declared harmless in a reviewed list (6 such hits here).

### Hooks keep their own BP frame
The manager re-vectors overlay return addresses by walking the BP chain. A hook entered from an overlay must:
- `push bp; mov bp, sp` on entry, so [bp+2] is its own return address;
- make every far call (to the original function or other overlays) from that frame: re-push the arguments,
  call, `mov sp, bp; pop bp`;
- return normally. Never tail-jump from the hook into an overlay stub or the original function.
- Treat every game routine you call as clobbering the registers its compiler may clobber (MSC: AX, BX, CX, DX, ES),
  C library calls such as `fread` included. Keep counts and lengths in memory or on the stack across the call, and
  don't trust an emulated test that stubs the routine to prove otherwise (gotcha 18).

### How much can the image grow? (the page cache and the budget)
Every paragraph inserted into the image is 16 bytes less free conventional memory at run time. On VICEROY
(measured 2026-10-25) the manager's startup:
- detects EMS and XMS, grows the program's memory block to the maximum, then allocates the overlay page pool
  ONCE at the top of memory: a fixed minimum (a word near the start of `$$VMTAB`) plus a cache extra, capped by
  one of three `$$VMTAB` words depending on what it found (EMS / XMS / neither; all 0xB40 paragraphs here);
- stops with "evm0006 Insufficient memory to run" if even the minimum doesn't fit;
- could hand pool memory back to DOS when a later allocation fails, but only if a feature bit in `$$VMTAB`
  is set, which this game doesn't set: the pool never shrinks.
So:
- measure the game's own low-water free memory in the heaviest scenarios (see the DOSBox note's guest-RAM
  section), set a budget for the inserted block with a safety margin, and test it automatically;
- for more room, lower the cache caps: each paragraph taken from the cache gives one back to the budget
  (VICEROY: 16 and 32 KB smaller caches showed no slowdown over several turns, even with EMS/XMS off).

### Hooks that record state must tell real actions from look-ups
Games often run the same routine to *ask* something as to *do* it (VICEROY's AI "lifts" a ship's passengers
to count them, then puts them back; the Europe screen lifts them to list them). A hook that records state on
that routine (here: which ship carries which unit) must recognise the look-only callers, or it records things
that never happened. List every caller of the routine you hook and classify each one.

### Several patchers at once: hand out space from one ledger
With several people or agents patching in parallel (one git branch each), "find a free gap and use it"
breaks: on VICEROY (2026-10-27) three branches put hooks in the same unused 96 bytes, a fourth placed its
new block on top of another branch's, and two used the same save-chunk number. Each branch passed its
own tests; the clash only shows at merge, or worse, after it.
- Once the original free code area is full, give each feature its own block appended to the inserted
  image, and compute every block's base from the previous block's end (never a literal address), so a
  block that grows shifts the later ones instead of overlapping them.
- Keep ONE record of every claim: code ranges, block order and size, data-segment holes, save-chunk ids
  and page-cache cuts, with an owner and a merged/reserved status. Hand space out with a small script that
  takes a lock file (`O_EXCL`), picks the lowest free range and appends the reservation; refuse requests
  for the full fixed area.
- Check it at build time: fail if the tree uses a range not reserved for that owner, overlaps another
  owner, or gives a block a literal base. Compare each branch with its merge base, not current master.

### Stress-test it
With EMS/XMS available the manager rarely discards pages, so a broken hook fails only now and then. Run the
in-game tests once more in DOSBox with `[dos] xms=false ems=false umb=false`: pages swap constantly and the
same bug fails every time.
- Once the patched game *requires* a UMB (DOSBox 0.74 gives one only with XMS on), that conf can't start it. This
  project dropped the stress conf then (2026-10-27) and relies on the emulated call-target test over every site and
  gate, plus long soak runs: a 40-turn soak found the 1-in-15 crash of gotcha 10 that the normal suite had missed.

## Not verified
Only VICEROY.EXE (MSC 6.0 + .RTLink/Plus 6.10). The Keystone behaviour (gotchas 13-15 and 17) was seen with Keystone
0.9.2 only. A small re-test with PyPI's keystone-engine 0.9.2 on Linux reproduced the `;` hang, the radix-16 errors,
and the 66h and 67h forms, but not all of gotcha 15: `leave` came out as a correct `C9`, a final `.short` without a
newline was kept, the labels `out` and `eb0` assembled, and a near `jmp` past -8000h came out as `66 E9` with a 4-byte
displacement rather than dropped. Those may need a particular source. What the 67h forms would do on an 8086 or 286
was not tried (no such CPU or emulator was run). The return-vector record layout (dispatcher section) was read from
this manager and confirmed in game on it only. Gotcha 22's fix is planned, not built. eb4x's doc finds the VM
manager's routine bodies byte-identical across the games it covers (only their offsets move), so the trampoline rule
should carry over, but run the emulated call test on your own binary before trusting it. The call-target rule, the
BP-chain walk and the page-pool startup were read from VICEROY's manager and its error messages; eb4x's doc doesn't
cover them.

## Gotchas
1. **About 1 run in 10-20: debug assertion popups, garbage prompts with nonsense values, an R6003 divide by
   zero, a freeze after ending the turn.** (2026-10-25.) **Cause:** 13-byte trampolines
   (`call fixsegs; lcall vector; ljmp`) - the manager did not recognise the call as coming from an overlay, the
   page was discarded while the hook called other overlays, and the hook returned into whatever code now
   occupied that memory. **Fix:** the 18-byte layout with a `jmp far` after the `call near`; confirmed under the
   no-EMS/XMS conf (failed every time before, passed every time after).
2. **Fatal manager error "evm0012 ... Return address could not be found on the BP chain" right after a hook
   ran.** (2026-10-24.) **Cause:** the hook jumped on to the original function without a frame of its own.
   **Fix:** BP frame, call, return.
3. **"Unvectored call to resident symbol" (evm0012) at random points late in a session.** (2026-10-25.)
   **Cause:** same family as gotcha 1 (a broken trampoline on a path that ran earlier). **Fix:** convert every
   hook, then re-test.
4. **A `call thunk; jmp` variant froze the game at the first call.** (2026-10-23.) **Cause:** the vector
   rewrites the offset word just before its return address (`[ret-4]`), which only works when it was called by a
   literal `lcall`. **Fix:** keep the `lcall <vector>` instruction literal in the trampoline.
5. **New code appended after the image vanished at run time.** (2026-10-23.) **Cause:** that area is
   uninitialised data and is zeroed at startup. **Fix:** insert the block inside the image (see "Growing the
   image").
6. **Emulated tests passed, the game crashed.** (2026-10-24.) **Cause:** the emulator didn't model the VM
   manager, so frame and trampoline mistakes are invisible to it. **Fix:** model the manager's call-target test
   in the emulator, and keep in-game tests under the stress conf.
7. **Addresses read from data were text-pool indices, not pointers.** (2026-10-24.) **Cause:** in this game
   many "string" fields are indices into a text table resolved by a resident routine. **Fix:** resolve them
   through the game's own lookup; check a value against the table before treating it as a pointer.
8. **"Tried to allocate N bytes when only M bytes were free" was expected, but the game kept going.**
   (2026-10-25.) **Cause:** most large buffers are optional; the game falls back to a smaller one or none when
   DOS refuses. **Fix:** measure refused allocations and the low-water mark, not only crashes; a build can be
   "working" while degrading screens.
9. **A state-recording hook tied units to AI ships that never sailed.** (2026-10-25.) **Cause:** the hooked
   routine was also called by the AI to count and put back. **Fix:** treat those call sites as look-only.
10. **"evm0012" with a CS of DEAD after long play, about 1 run in 15 of a 40-turn soak.** (2026-10-28.) **Cause:**
    given free upper memory, the manager built a page heap there, right under DOSBox's EMS page frame at E000. A
    return into a page was re-vectored to a frame whose segment plus the module's offset gave DEAD (DE52 + 5B), so
    the manager couldn't place the return address. The unpatched game has the same hazard (a few of its
    test runs were flaky the same way). **Fix:** the start-up allocates all remaining upper memory after its own
    block and keeps it, so the manager keeps its pages in conventional memory and EMS/XMS. 42 clean soaks after.
11. **MSC run-time error R6001 at the end of a game, only with one feature in play.** (2026-10-28.) **Cause:** a
    patch moved an `lcall` three bytes on, so the patched bytes covered a word the overlay manager relocates; when
    the page loaded, the call was rewritten into garbage. Emulated tests passed because they didn't apply the
    relocation. **Fix:** keep the call at its old address, and add the build-time relocated-word check above.
12. **The first dispatcher build stopped at the title with a miss.** (2026-10-30.) **Cause:** the miss address was
    the manager's own return vector, not an overlay: after the first vectored call RTLink substitutes it for the
    caller's return address. **Fix:** recognise the vector and read the real caller from the manager's record
    stack; the emulated dispatcher test now models both cases (plain return address, and vector plus record).
13. **A build step hung for good while assembling.** (late October 2026.) **Cause:** in Keystone's default syntax
    (0.9.2, 16-bit mode here) `;` isn't a comment but the statement separator (`MCAsmInfo`: `SeparatorString` is `;`,
    `CommentString` is `#`), so the text after it is parsed as code. A statement that starts with `(`, `[`, `-`, `'`
    or `<` hangs the parser, which also fits the one source a regex had mangled; other text fails as an invalid
    mnemonic, and `; nop` or `; rep` silently assembles. **Fix:** never pass comments to Keystone (strip them from
    generated asm), or write them with `#`. A timeout around each call would turn a hang into an error (not used
    here).
14. **About 1 assembly in 600 read every decimal literal as hex (`cmp al, 10` became `cmp al, 10h`); once it
    raised "Literal value out of range for directive" on a source that assembled before and after.** (2026-10-31,
    2026-11-01.) **Cause:** in Keystone 0.9.2 `MCAsmInfo`'s constructor never sets `Radix`, and `AsmLexer` reads every
    number as hex when that field happens to hold 16, so it depends on what was left in that heap memory. `.byte 200`
    read as hex is the "out of range" error. `ks_option` also starts with `setRadix(16)`, so setting any option
    (`ks.syntax = ...`) turns hex on for that engine every time. **Fix:** a wrapper that appends a sentinel
    (`cmp al, 10`), assembles on a fresh engine, retries until the sentinel's bytes are `3C 0A` (up to 16 tries) and
    drops it; it also retries a `KsError` on a fresh engine and re-raises after 3, so a real source error still fails
    fast. Literals written as `0x..` read the same either way.
15. **Wrong or missing bytes from Keystone in 16-bit mode, with no error.** (2026-10-22 to 10-30.) **Cause:** it
    emits 32-bit forms (66h prefix) for `push imm`, `retf`, long `jcc` and `call dword ptr [x]`, mis-encodes 16-bit
    `call imm`, `ret` and `leave`, silently drops near displacements below -8000h, rejects or misreads labels named
    like registers, mnemonics or hex numbers (`out`, `k2`, `eb0`), and dropped a trailing `.short` when the source
    had no final newline. **Fix:** hand-encode those forms, wrap displacements at 64 KB, and disassemble every
    assembled piece and compare it with the source before it goes into the EXE.
16. **No gate slots left for new hooks.** (2026-10-28.) **Cause:** the one-shot start-up code filled the gate
    block. **Fix:** keep the start-up code in the gate area of the image and let the gates overwrite it after it
    has run (room for 66 more gates at the same size); later the shared dispatcher for cold hooks.
17. **Keystone assembled `cs:[label]` memory operands as 386 code, silently.** (2026-11-03; one module had 13 such
    operands.) **Cause:** in 16-bit mode Keystone 0.9.2 encodes a memory operand that is a bare label (`[name]`,
    `cs:[name]`) in the 32-bit address form (67h prefix, 4-byte displacement), for labels defined above as well as
    below (`mov bx, [name]` gives `67 8B 1D` plus 4 bytes). Numeric addresses, `[bx+name]` and the accumulator's
    `mov ax, [name]` stay 16-bit. DOSBox emulates a 386-class CPU and every displacement
    was small, so the code ran correctly and every in-game test passed; on an 8086 or 286 those instructions are not
    valid. **Fix:** replace such labels by their numeric addresses before assembling (assemble once to learn the
    addresses, substitute, repeat until they settle), then disassemble each whole assembled image (Capstone,
    skipping data) and fail the build on any 0Fh, 66h or 67h opcode byte or prefix. A scan of the project's other
    generated modules found about 320 such forms, harmless in DOSBox and left for later cleanup.
18. **A saved chunk was read wrongly in game but correctly in the emulated test.** (2026-11-03.) **Cause:** module
    code read a save-file chunk with the game's own `fread` and kept the chunk length in CX across the call. The
    game's `fread` changes CX; the emulated test's stand-in for it did not, so the emulated test passed while the
    first in-game run took every new-version chunk for the old version. **Fix:** keep the length in memory or on the
    stack across the call. An emulated test can't catch this class of bug unless it runs the game's real routine or a
    stand-in that clobbers every scratch register (which this project did not add).
19. **A popup opened from a correctly framed hook still stopped with "evm0012 ... Return address could not be found
    on the BP chain".** (2026-11-03.) **Cause:** the hook was entered through the shared dispatcher, a plain
    `call far` from overlay code into the UMB that does not pass through the manager's vector, so the manager never
    recorded the call. The popup routine is resident, but it calls a code page through a vector; to protect the
    caller's page the manager then looks for the resident call's return address on the BP chain, and that address
    is in the hook's code, which it never saw. A BP frame doesn't help. Popups called by the game's own overlay code
    work, and so do popups from hooks entered through a vectored entry. **Fix:** defer the work: the click hook only
    sets a flag; a second hook on the screen's input loop (its `key ready` call, a site whose call is vectored)
    checks the flag, opens the popup, redraws the panel and returns "no key". The emulated test checks the flag, the
    deferred popup and the redraw.
20. **A hook reached through the shared dispatcher crashed with evm0012 only after it opened a sub-screen.**
    (2026-11-04.) **Cause:** the same as gotcha 19, but without any popup: the hook's module called resident
    routines that made the overlay manager swap a page out, and the manager could not find the unvectored caller on
    the BP chain. Any callee that can load or drop an overlay page counts, not only dialogs. **Fix:** give that hook
    its own vectored gate (the game's call vector, not the dispatcher's plain far call). Rule of thumb: dispatcher
    entry only for hooks whose whole call tree stays resident or in already-loaded pages.
21. **A rule needed a new condition in a hot drawing path, and every hook option cost memory or a gate.**
    (2026-11-05.) **Fix:** the target was a small leaf function (a 58-byte neighbour test with one caller) that
    could be rewritten in place: the new condition (read one more bit of a map byte) assembled to 54 bytes. No
    hook, no gate, no upper memory. Look for these: a decompilation's call graph tells you a function's callers and
    its size; reassemble, check the size and the callers' expectations, and keep the original bytes as the test's
    reference.
22. **Pause and volume in a DOS General MIDI driver did not do what their names said.** (2026-11-05, Colonization's
    GSOUND.) **Cause:** the driver's pause call stopped the stream player but silenced only channels 2-10, and resume
    restored the driver's own channel volumes rather than the song's; it had no master volume at all.
    **Fix (planned):** pause silences every music channel and remembers each channel's last volume, resuming
    resends them; volume is done by scaling every channel-volume (CC 7) message as the player sends it and
    resending all channels on a change. The GM master-volume SysEx is ignored by some synths.

23. **evm0012 "unvectored call" the second time a hook called a resident routine.** (2026-10-27.)
    **Cause:** the hook made the far call as `push seg; push off; retf` into the resident routine; the
    manager couldn't vector it. **Fix:** `call far cs:[ptr]` with the far pointer stored in the block.
24. **The game jumped into garbage after the first menu choice through a new dialog hook.** (2026-10-27.)
    **Cause:** two of the game's menu routines remove their own arguments (`retf N`), and the hook also
    did `add sp` after the call, as for a C-style routine. **Fix:** read the callee's return instruction
    before calling it; test the hook in an emulator that checks SP after the call.
25. **Three branches' hooks in the same 96 free bytes.** (2026-10-27.) **Cause:** each agent picked "free"
    space by reading the code in its own branch. **Fix:** the ledger above; nobody picks space by hand.

26. **A freeze ("invalid opcode", stack inside a data array) after clicking a label in a new screen.**
    (2026-11-11.) **Cause:** the game's text drawing routine copies the string into an 80-byte buffer on its
    own stack with no length check. A composed line of 90 characters (a narrow font let it pass the pixel
    width check) ran past the buffer into the saved BP and the return address. 81-86 characters only
    overwrite the colours stored above the buffer, which is why a slightly long line had worked for weeks.
    Enlarging the routine's frame was not safe (its saved parameters sit just below it). **Fix:** draw long
    lines in pieces of at most 79 characters, each starting at the x the previous call returned (same
    pixels); a build check that fails on any new string constant of 80+ characters; audit every caller of
    the routine's entry points for composed lines (names + clauses at their longest).
27. **A message box showed the first lines of the message file (its copyright header) instead of a
    message.** (2026-11-11.) **Cause:** the hook kept the message key's pointer in CX across two calls to
    the game's C routines; Microsoft C callers may clobber AX, BX, CX, DX and ES, so the key arrived as 0,
    and the text lookup only seeks a key when the pointer is non-null - with null it reads the file from the
    top. The emulated test faked those game calls without touching CX, so it passed. **Fix:** push/pop
    around the calls; make every emulated fake of a game routine clobber the volatile registers, so tests
    catch values held across calls. Also add a check that every message key the patch names exists in the
    message files.
28. **Moving a merged ledger record before its code was merged broke the space check on every other
    branch.** (2026-11-11.) **Cause:** a feature needed to move three older data tables into freed space; the
    records were repointed at once, but only the feature's branch had the new code, and the check reads
    every live record against each tree. **Fix:** record the new homes as the feature's own reservations
    (no overlap with anything) and swap the old records over in the same step that merges the feature.
29. **evm0012 "Unvectored call to resident symbol" in an AI's turn, now and then, never on a reload.**
    (2026-11-11, cause narrowed, not confirmed.) Reading the message: RTLink prints "near address" with an
    absolute segment (not a map address) only when CS lies outside the resident image, i.e. inside the
    page pool. Compare that address with each overlay's load frame: here CS was one overlay's frame but
    the bytes there were another, smaller overlay's (both frames end at the top of the pool), and the
    printed call was that overlay's code at the same linear address. So a far call into the second overlay
    evicted the caller's overlay and returned straight into its old place without the manager's reload
    thunk. It only happens when the patch has shrunk the page pool below the size of the two overlays
    together (here 0x999 paragraphs vs 0xE99 needed; the original's pool holds both), which explains a
    patch-only, intermittent crash. Leftover return records from resident calls are normal RTLink behaviour
    (the original EXE has them too). Check every patch hook inside the calling overlay first (frames,
    gates); then trap the manager's thunk-skip path in a debugger build instead of sampling, which is too
    slow to see one short call.

## Seen in
- Sid Meier's Colonization 3.0 (DOS, GOG release) binary-patching project (no public game note yet).
- Related: `driving-dosbox-games-from-tests-background-input-parallel-sa.md` (the in-game test harness and the
  no-EMS/XMS stress conf) and `upper-memory-for-patched-dos-games-in-dosbox-code-in-a-umb-e.md` (moving the new
  code into a UMB, transient code modules).
- Credit: the page format comes from eb4x/ghidra-plugin-rtlink (`docs/rtlink-format.md`). Assembly and the image
  scans use Keystone and Capstone.
