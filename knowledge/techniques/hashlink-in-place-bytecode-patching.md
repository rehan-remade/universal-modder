---
kind: technique
title: "Patching HashLink bytecode in place: same-size rules, JIT pitfalls, growing functions, helper slots and live tracing"
status: working
agents: ["Claude Code (claude-opus-5-5)"]
humans: []
date: '2026-11-21'
links:
- https://github.com/Gui-Yom/hlbc
- https://github.com/HaxeFoundation/hashlink/tree/1.5/src
tags: [hashlink, haxe, bytecode, jit, patching, varint, debug-info, runtime-tracing, ptrace, wine, proton]
---
# Patching HashLink bytecode in place

> HashLink games (Haxe compiled to HL bytecode, run by HashLink's JIT) ship their game logic as one bytecode blob:
> embedded in the exe (Dead Cells 1.0: a Windows `RT_RCDATA` resource named `HLBOOT.DAT` in an `hl.exe` host),
> or as a separate `hlboot.dat`. When there is no mod loader, you can edit
> that blob in place without moving anything else. This note covers the rules that keep the JIT happy, how to
> rewrite or grow a function in place, where to put new logic, and how to check the result against the running
> game. It was worked out on Dead Cells v1.0 (HLB v3, HashLink 1.5-era 32-bit JIT, ~70 mods), so read
> `knowledge/games/dead-cells/dead-cells-v1-0-modding-reference.md` for game specifics. The engine facts are
> checked against HashLink's 1.5 source, as cited.

## Reading the blob
- **Find it:** search for `HLB` followed by a version byte. In a Windows exe, also list the PE resources (e.g.
  with Python `pefile`). The blob may be a resource with other data after it, so "offset to end of file" is not
  its length. The next varint holds the flags; bit 0 = debug info.
  With debug info, every op carries a source file and line. Dump a full disassembly once to a text file (Dead
  Cells: ~2M lines) and grep it.
- **hlbc** (Rust, crates.io) parses versions 3-5 as a library. Version 0.7.0 accepts v3 only because its
  version check, `version < 4 && version > 5`, is never true. If you depend on v3 support, pin the version.
- **hlbc's writer (0.7.0) round-trips to the same size, but not byte for byte.** Object `bindings` live in a
  `HashMap`, so they come back in a different order. On Dead Cells v1.0 that was 2,047 changed bytes, and the
  game booted with the result written back in place. Whole-blob rewriting is therefore possible, but it changes
  bytes that other offset-based patches may compare against. Small in-place patches stay easier to combine.
- **findex** = global function index (natives and bytecode functions share one index space). Notes and tools
  should always give findex + name: positions in the functions array are a different number, and mixing the two
  up produced several wrong notes.
- **Virtual calls:** `CallThis` / `CallMethod` take a **proto slot**, not a findex. Disassemblers that print a
  name for them are often wrong. Resolve the slot against the class's proto list (with inherited protos first).

## Encoding facts you need for same-size patches
- **Index varints** (`hl_read_index` in `src/code.c`; hlbc `read_vari`):
  - 0..127: 1 byte (`0x00-0x7F`);
  - 128..8191: 2 bytes (`0x80 | hi5`, `lo8`);
  - larger: 4 bytes (`0xC0 | …`);
  - bit `0x20` of the first byte is the sign (`0xA0` / `0xE0` forms) for signed values such as jump offsets.
- **A small value can be written in a longer form** (`80 05` = 5). The reader accepts it. This is the main tool
  for absorbing spare bytes without adding ops. A call to a findex above 8191 costs 4 bytes for the index alone
  (Dead Cells: `Call1` to such a function = 7 bytes).
- **Do-nothing ops for padding** (each counts as one op):

  | op | bytes | note |
  |---|---|---|
  | `Label` | 1 | `0x42`; also safe as a backward-jump target |
  | `JAlways +0` | 2 | |
  | `Mov rX = rX` | 3 | |
  | `NullCheck r0` | 2 | only where r0 can't be null, e.g. `this` in a method |

- **Jumps are relative op counts:** target = current op + 1 + offset. They have to land inside the function.
  hlbc's parse doesn't check jump targets; your own verifier should.

## The rules (each one cost a debugging session)
1. **Same byte length, and the same op count per function.** The header stores `nops`, the reader reads exactly
   that many ops, and then it reads the function's debug info as run-length entries over `nops`. If your bytes
   decode to a different number of ops, the debug stream is misread. HashLink 1.5's `hl_read_debug_infos` then
   reports `Outside range` (the check is `i + count > nops`) and the game exits at startup. To change the op count
   legitimately, rewrite `nops` *and* re-encode the debug info (see "Growing a function").
2. **Register types are static and the JIT asserts on them.** Every function declares a type for each register.
   Writing a float into an i32 register, using a bool register as f64, or `Mov` between an object and a String
   register aborts at startup with `JIT ERROR <n> (jit.c line <m>)`. That message comes from the JIT's `ASSERT`
   macro, which prints and calls `exit(-1)`. A parse won't catch it. Before you pick registers, print the
   function's register list. When you rewrite a donor function's body, check *its* register types too.
3. **Backward jumps must land on a `Label`.** The JIT keeps values cached in CPU registers between ops. It drops
   the cache at `OLabel` (`discard_regs`) and at forward-jump targets it has registered, but nothing like that
   happens for a backward jump into an arbitrary op. Symptom on Dead Cells: a value computed in an out-and-back
   block was silently ignored, because the code after the jump back used the stale cached copy. The Haxe compiler
   always emits a `Label` at loop heads; do the same. Out-and-back blocks either return to a `Label` or make the
   call themselves before jumping back.
4. **Registers aren't zeroed for you.** HashLink 1.5's `hl_jit_function` allocates the frame (`SUB ESP, size`)
   without clearing it, and Haxe-generated code always writes a register before reading it. A patch that reads a
   register it never wrote gets whatever was on the stack. An earlier Dead Cells session traced access violations
   in a callee to exactly this; that crash wasn't reproduced for this note. Write a `Null` or a constant first.
5. **Check what your write clobbers.** A register that looks free can carry a live value through your range.
   List the registers your range writes that are read later, and compare against the unpatched function.
6. **Constants come from pools.** `Int` / `Float` ops take an index into the int / float pool, so you can only use
   values that are already pooled. Find an existing pool entry with your value, or compute the value (e.g. `0.35`
   as `7 / 20` from pooled ints). Strings used only in `throw` messages can be rewritten in place at the same
   length to get new label text.

## Rewriting and growing a function in place
- **Same-op-count edits** (most mods) are hand-encoded: replace ops A..B with new ops, pad with the do-nothing ops
  above, and keep the bytes and op count identical. Verify by diffing the function's disassembly before and
  after: only your range may change.
- **Growing a function** needs a tool, and room comes from inside the function. The Dead Cells project wrote an
  "op splicer" on top of hlbc that does this:
  - Replace or insert op ranges written in a small assembly language. Jumps can target "original op N" or a named
    label.
  - Re-target every original jump, including `Switch` and `Trap`. A jump into the middle of a replaced range is
    refused.
  - Re-encode the debug info the way the Haxe compiler does. As a self-test, an empty spec must reproduce the
    input byte for byte.
  - Pad the result back to the original length with unreachable trailing `Label`s and padded `nregs` / `nops`
    varints. If the result is longer, the tool refuses.
- **Where the room comes from:**
  - Error-message builders that are never reached (`new String … concat … Throw` shortened to a bare
    `Throw rX`). These are often 20-60 bytes each.
  - Inlined code that a branch makes dead.
  - Debug variable-name records (the per-function `assigns` table, present in v3+ bytecode with debug info).
    Dropping them frees bytes and changes nothing at runtime.
- **Pitfalls:**
  - **Adding a register** grows the function header, so *every* byte of that function moves. Never add one in a
    function that other patches address by offset.
  - **The splicer's output isn't canonical everywhere.** A function that other mods patched by hand (with padded
    varints) re-encodes differently even with an empty spec. Splice from the pristine function, or hand-encode.
  - **"Insert before op A" moves the target of jumps to A.** A jump to A now lands on the first inserted op. If
    the inserted block must be skippable, end it with a named label. One Dead Cells patch nearly shipped an
    infinite loop because of this.

## Where to put new logic: helper slots
You can't append functions, but a call site can call any existing function of the right type. Find functions
that are **never called** in this build, then overwrite their bodies with your helper. A "whole function
rewrite" tool can also change the function's type and register list, and pad the result to the slot's size. Good
sources on Dead Cells:
- dev/test classes (an unused test mob, debug popups, debug level layouts);
- a serializer class that is never constructed;
- an Early Access room that a constant-false branch made unreachable.

Rules:
- **Prove zero callers.** Scan static calls, closures *and* virtual slots. Methods only reachable through a
  vtable are fine if the class is never built.
- **Never take hxbit `serialize` / `unserialize` methods:** loading or saving a game calls them.
- **Keep a registry** of which slots are used, their sizes, and which mod owns each.
- **Low findexes (< 8192) are worth more:** a call to one is 2 bytes shorter, which can decide whether a call
  site fits.

## Verifying a patch
1. **Re-parse** the whole blob: function count and file size unchanged.
2. **Jump-target check** on changed functions.
3. **Clobber check** on changed ranges (rule 5).
4. **Headless boot:** a copy of the game folder (no saves), a fresh Wine prefix, `timeout 60 xvfb-run -a wine
   game.exe`. Pass = the game's own "assets loaded" line. Bytecode and JIT errors print before it and end the
   process. This catches rules 1 and 2; nothing static does.
5. **Live check** for anything behavioural (next section). Several patches that read correctly in the bytecode
   did nothing at runtime.

## Live tracing a HashLink JIT game (Linux, Wine/Proton, 32-bit)
- **Reading memory:** `/proc/<pid>/mem` and `ptrace` on the Wine process worked with `ptrace_scope = 1`.
  - Find the `hl_type` table by matching the bytecode's sequence of type kinds against memory at the struct
    stride (16 bytes on 32-bit). Demand exactly one hit.
  - The class's runtime info gives field byte offsets: `hl_type_obj.rt` at +40, then
    `hl_runtime_obj.fields_indexes`. Its offset was probed (+28 / +32) and validated, not assumed.
  - From there, walk objects from a known global (the game singleton).
  - Strings are `{type, UTF-16LE bytes, length}`. Enums without arguments keep their index at +4.
- **Finding code:** `hl_module.functions_ptrs` maps findex → JIT address. Every JIT'd function starts
  `55 8b ec` (push ebp; mov ebp, esp), so an ebp-chain walk gives the callers. Map the return addresses back to
  findexes by sorting the function addresses.
- **Breakpoints:** write `0xCC` at a function entry and catch the trap.
  - Seize *every* thread (`PTRACE_SEIZE` + `TRACECLONE`), and pass on every signal that isn't yours, or Wine's
    exception handling breaks.
  - Filter in the tool, e.g. by `[esp+4]` = the `this` you care about.
  - Make SIGINT only set a flag so the original bytes are always restored, then re-read them after detaching.
    One run left an int3 in the live game.
- **Objects get replaced.** A boss or level object you're watching can be disposed (death, restart). Watch its
  `destroyed` flag and find it again.

## Gotchas
1. **Game exits at startup printing `Outside range`.** Cause: op count drift (rule 1). Fix: keep the op count, or
   splice with debug-info re-encoding.
2. **`JIT ERROR n (jit.c line m)` at startup.** Cause: a register type mismatch (rule 2), often in a donor
   function used as a helper slot. Fix: check the register types of every function you write into.
3. **The patch "works" in the disassembly but not in game.** Cause: a stale JIT register after a backward jump to
   a non-Label (rule 3), or the wrong function. Fix: land on Labels, and confirm with a breakpoint.
4. **Random access violations in a function you didn't touch.** Cause: reading an unwritten register (rule 4).
   Fix: initialise it.
5. **A patch broke a different mod.** Cause: overlapping byte ranges, or "free" filler that belonged to another
   patch. Fix: check every region's full range before adding one. For spans two mods must share, store bytes for
   each on/off combination.
6. **Rebuilt exe won't start ("Bad EXE format").** Cause: the exe was cut at the end of the bytecode, dropping
   the PE data after the resource (`.reloc`, manifest, signature). Fix: write a same-size blob back over the
   resource. A different size needs the resource section and PE headers rebuilt.

## Open questions
- Only HLB v3 with HashLink 1.5's 32-bit JIT was tested. A 64-bit HashLink build uses 8-byte pointers, so the
  runtime struct offsets above change (and the stack walk uses rbp). HLB v4/v5 add a constants table (and v5 a bytes pool), which hlbc handles.
  The encoding rules should be the same.
- HashLink/C builds (`hl2c`, compiled to native code) don't have bytecode at all. None of this applies to them.
