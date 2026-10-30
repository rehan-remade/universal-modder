---
kind: technique
title: "Hosting a decompiled console engine as a native DLL inside a .NET game mod"
status: in-progress
agents: ["Claude Code and agents", "Grok"]
humans: ["DarkameMaster"]
date: 2026-10-10
links:
  - https://github.com/999sian/melee-pc
  - https://github.com/doldecomp/melee
  - https://github.com/tModLoader/tModLoader
  - https://www.mingw-w64.org/
tags: [decomp, native-dll, pinvoke, tmodloader, dotnet, c-api, abi, stubs, arena, crash-guard, snapshot, rollback, determinism, versioning, mashup, gamecube]
---

# Hosting a decompiled console engine as a native DLL inside a .NET game mod

> Once a decompilation has a PC port, the game can be built as a headless x64 library and loaded into
> another game's .NET mod loader by P/Invoke. The host calls one function per frame and reads the guest's
> state back, so the guest's own code (every move, every special) runs unchanged while the host draws and owns
> the world. This note is the recipe and its traps, from putting Super Smash Bros. Melee's decompiled engine
> inside Terraria through tModLoader.

## When to use it
- A decompilation (or a decomp-based PC port) of the guest exists, and you need *its* behaviour, not an
  approximation. The alternative is rewriting the mechanics in the host's language. In this project a
  2,500-line C# rewrite matched walking within a few pixels, but drifted up to about 127 px elsewhere (against a
  truth that included the community controller fix) and needed hand-written logic for every special move (about
  34 distinct movement specials and 18 projectile moves across the roster).
- The host runs mods as .NET assemblies (tModLoader, BepInEx, SMAPI, MelonLoader...) and can call native code.
- You want rollback, replays or a "1:1" claim later. A library with an explicit snapshot and a fixed frame
  step makes that possible; a rewrite rarely does.
- Not for guests whose decomp still has non-matching functions in the parts you need (they behave
  differently), or for hosts with anti-cheat: loading native code is a client modification.

## Setup (where this was measured)
- Host: Terraria 1.4.4.9 on tModLoader 2026.08.3.0, its bundled .NET 8.0.0 runtime, FNA 23.10, Windows 11 x64.
- Guest: [melee-pc](https://github.com/999sian/melee-pc) at commit `e83383539a4fd06e9bd8b28c270b3d1ecc7d3be3`,
  the PC port built on the [doldecomp/melee](https://github.com/doldecomp/melee) decompilation. Built in WSL
  Ubuntu 24.04 with `x86_64-w64-mingw32-gcc` 13 (the **posix** threads variant), CMake 3.28 and Ninja.
- The guest reads its data files (`.dat` archives) at runtime from a folder outside the mod; every player needs
  their own copy of the game. Neither the DLL nor any game data goes into the `.tmod`.

## How

### 1. Cut the game library out of the port, without its renderer
- A decomp-based port usually already separates "the game" from "the platform layer". melee-pc's CMake builds
  the game as a static library (`melee_game`) and links it with a graphics and audio layer (aurora,
  Dawn/WebGPU, SDL3). Build only the library: here `ninja melee_game` took 48 s on 16 threads.
- **Don't link the guest's renderer.** The host draws. Linking aurora pulled in Dawn, SDL and abseil, and
  abseil resolved against a Windows DLL that CMake found through the WSL `PATH`. Leaving graphics out removed
  the problem.
- Link an empty probe against the library and look at what is undefined. Here it was 418 symbols, and every
  one belonged to console hardware or online services: graphics (GX) 117, audio (AX/AI/AR) about 45, OS 32,
  netplay/ranking/replay 80, memory card 20, video 12, disc 7, pad 5. No fighter, stage-collision, stage, item
  or scene-graph symbol was missing (implementing agent's count). That list is the size of the job.

### 2. Generate the stubs, and classify what returns a value
- A script links, collects the undefined symbols, writes stubs and repeats until the link converges (at most
  4 rounds). It reads already-provided symbols with `nm` from the objects, not from a hand list.
- Each stub returns a **typed zero**, counts its calls and warns once. A `void X(void){}` stub for a function
  that returns a value hands back whatever is left in RAX/XMM0, which is garbage (Gotcha 3).
- Port symbols that return a value make the generator **fail** unless a table classifies them:
  - `zero`: zero really is the right answer offline (no network, no memory card, unlock-all off);
  - `trap`: zero would be wrong, but only code the host never runs calls it (online mode, menus, music). The
    stub panics, and the crash guard turns that into an error code: it fails loudly instead of lying.
- Symbols the game declares as **data** need data definitions; the generator stops if one is missing.
- **Some "hardware" is arithmetic.** Vector normalisation, a screen projection (`GXProject`) and the port's own
  trig wrappers were among the generated no-ops. Link the math libraries, transcribe what is left from the
  original executable, and blank only real I/O (Gotcha 4).
- Make the guest's panic and log functions (`OSPanic`, `OSReport`) print before anything else. While they were
  stubbed, failures were silent segfaults; once they printed, each failure named its missing piece (the file
  system, the archive symbol table). Read the messages critically: a "heap is full" panic was really a missing
  archive, because the stubbed disc layer reported every file as size 0 (found by a second agent).

### 3. Give the guest an address space it believes in
- The port stores disc pointers in 32-bit slots and treats any value below 16 MB as an audio-RAM offset. So the
  guest's heap (the "arena", 96 MB here) must lie entirely inside `[16 MB, 4 GB)` of the 64-bit process.
- The DLL reserves it at a fixed address with `VirtualAlloc`, falling back to `VirtualAlloc2` with an address
  ceiling. `0x80000000` was free both in a plain `dotnet.exe` and inside tModLoader with FNA, SDL2 and Steam
  loaded.
- The guest's heap calls go to the DLL's own allocator over that arena: 32-byte aligned and zeroed, because the
  decompiled code assumes both.
- At startup the DLL checks that a test `malloc` from the C runtime lands above 16 MB, and refuses to start
  otherwise (Gotcha 2).

### 4. Guard every call
- Every exported call that runs game code sits between a `setjmp` and its return. The guest's panic and `abort`
  are wrapped at link time (`--wrap`), and a vectored exception handler catches access violations, illegal
  instructions and divisions by zero **on the calling thread, only during the call**.
- The call then returns an error code (`-6` panic, `-7` hardware exception) with the message in a last-error
  buffer, and the engine stays faulted (`-8` on any later call) until the host resets it.
- Without this, one guest panic ended the whole host process (measured: exit code 3 in a .NET test host).
- What a guard can't cover: a hang (a call that never returns can't be cut from its own thread), a stack
  overflow, silent memory corruption. The escape hatch for those is the same contract in a worker process:
  the ABI stays, only the transport changes.

### 5. Make "reset" a memory copy
- melee-pc already groups the decomp's statics for its netplay rollback: a build step renames `.data` and
  `.bss` into named PE sections between start and end markers. The DLL build adds to the same range the 10
  objects the port leaves out (audio, video and memory-card code), the port's own C objects, the DLL's glue and
  the stubs. Then it checks with `nm` that the key globals are inside and the DLL's own guard state is outside.
- The first `init` copies both ranges before any game code runs (about 0.34 MB of data and 2.3 MB of bss).
  `reset` clears the file cache, zeroes the used arena, copies the ranges back and bumps a **generation**
  counter. The DLL is then as freshly loaded, even after a fault mid-call.
- The same snapshot is what makes rollback possible later. Anything new that persists between frames (a draw
  mode, a camera block) must live inside it, or rollback breaks silently.

### 6. A small fixed contract (the "MTB" C API)
- Every block that crosses is fixed-size, pointer-free and little-endian, with 4-byte fields. `_Static_assert`
  pins every offset in C, and the C# side checks `Marshal.SizeOf` and `OffsetOf` of every field at load.
  Big-endian game data never crosses: the C side converts field by field when it copies host data in.
- The first call any host can make returns a 32-byte ABI block (magic `MTBR`, version, unit system, block sizes,
  limits). A host that disagrees **refuses and changes nothing**. From v2, `init` also fails (`-14`) until the
  host calls `handshake(2)`, so an old host that ignores the version still fails cleanly.
- Version rule: the major version moves with any change of meaning. Additive features that no published host
  uses yet get a **minor version** in a reserved field of the ABI block instead (pose channel, stage points,
  camera, Slippi's off-screen rule, and so on), so v2 hosts keep their handshake.
- The core calls are `abi`, `handshake`, `init(files_dir)`, `reset`, `load_collision`, `set_slot`,
  `create_fighters`, `step_pads` (one 60 Hz frame for up to 4 pads), `read_state_slot`, `read_items`,
  `set/get_rng_seed` and `last_error`. Later, optional: pose, camera, stage points, sub-entity pose, hit
  bridge, audio, effects.
- **Asking never consumes.** `last_error(NULL, 0)` returns the length; `read_items(NULL, 0)` returns the count.
- Errors are numbered, and the host treats any of them as "engine off, say why".

### 7. Bind it from .NET
- `NativeLibrary.Load` from a configurable path **outside the mod folder**, then
  `Marshal.GetDelegateForFunctionPointer` with `Cdecl` delegates. No `unsafe` is needed: blittable structs and
  arrays are pinned for the call.
- Required exports bind with `GetExport`, and a missing one rejects the DLL before any game code runs.
  **Optional features bind with `TryGetExport`**, plus a check of the minor version: an older DLL still loads
  and the feature is just off. Each feature lives in its own partial class file (`Native.Audio.cs`,
  `Native.HitBridge.cs`, ...), which also let parallel agents work without sharing a file.
- **The DLL is never freed.** A tModLoader mod reload unloads the managed assembly, but a native library loaded
  this way stays in the process with its arena and state. So every session starts with `reset` (idempotent)
  and then `init`, and the generation counter tells the host when to re-send collision and recreate fighters.
- One thread: every call comes from the game thread, never concurrently. No seqlock is needed while nothing
  else reads the blocks; if a worker thread or process ever does, the state snapshot needs one.

### 8. Step it once per host tick
- In tModLoader, `ModPlayer.PreUpdate` builds the pad and calls `step_pads`. `PostUpdateRunSpeeds` then writes
  the engine's position into the `Player` (feet anchored, velocity zeroed, Terraria's own movement suppressed
  for that frame). Both games run at 60 Hz, so one Terraria tick is one guest frame.
- Measured in two independent real runs inside tModLoader (3,065 steps each): mean 0.031-0.036 ms per step,
  max 0.21-0.23 ms. A full `reset` + `init` + `create` cost about 7.6 ms extra in the frame it happened
  (implementing agent's measurement).

### 9. Reads must be pure; prove it
- A read that runs guest code can change guest state. Here the first pose read ran the scene graph's matrix
  setup, and for one item kind it allocated 64 bytes in the arena: the simulation diverged only because the
  host *looked*.
- Make reads compute into a private buffer and return `-15` if the arena changed anyway. Test it by
  **write-protecting the guest's memory** (`VirtualProtect`) around every read. A second agent's harness found
  0 writes in 349,450 reads over 29 recordings and 50 item kinds, and its self-test tripped on the old DLL.
- When the original game *does* change state while drawing, model that as an explicit, deterministic step at
  the end of the frame, not as a side effect of the host's reads. The skinned-models note has the case.

### 10. Change it in pieces, in parallel, without breaking the oracle
- Never edit the upstream sources. Every behaviour change is a **build-time patch script**: it copies the
  upstream file, rewrites the exact statements, **fails if the anchor statement appears 0 or 2 times**
  (upstream moved), compiles with the exact line from `compile_commands.json`, and swaps the object in a copy
  of the library. Each patch is a named tag that can be switched off (`=0`) for causal experiments.
- For parallel work, each agent gets its own copy of the core and delivers a `patch -p1` file with an assigned
  minor version. New C code goes in new files and header additions in a delimited block. Patches merge in
  order of minor version, followed by one official build.
- The gate for every merge is the replay bench: all real recordings still bit-exact, with CSVs byte-identical
  to the previous build. A function-by-function disassembly diff with addresses stripped shows exactly which
  functions a patch changed (a second agent's rebuild of one patch: 0 of 23,563 functions different).

## Gotchas
1. **The data path set from C# never reached the DLL.** **Symptom:** the guest couldn't find its first archive
   and panicked. **Cause:** `msvcrt.dll` copies the process environment when it loads, so
   `Environment.SetEnvironmentVariable` in .NET changes a different copy from the one the C code's `getenv`
   reads. **Fix:** pass paths through the API (`init(files_dir)`), or export a setter that calls `_putenv`
   inside the DLL.
2. **An archive loaded as zeros, with exit code 0.** **Cause:** a test exe linked without ASLR got a C-runtime
   heap below 16 MB; the port's file cache took those buffers for audio-RAM offsets and cached zeros. The
   first load was still correct (the copy into the arena happened first); the second load of the same file
   panicked. **Fix:** link host exes with `--dynamicbase --high-entropy-va`. The DLL inherits a high heap from
   the .NET host, and refuses to start if a test `malloc` lands low.
3. **A stub that returned "something".** **Cause:** a `void` stub for the audio-RAM base pointer, whose caller
   copied from `data + RAX`. **Fix:** typed zeros, a value table with a source for each entry, and trap stubs
   that panic.
4. **Stubs that compile and lie.** **Symptom:** nothing aborts, but the floor normal comes out (0, 160), every
   fighter is "on screen" and every angle is wrong. **Cause:** vector normalisation, the graphics SDK's
   projection and the port's trig wrappers were blanked as "hardware". **Fix:** link every pure-math library.
   A lying stub is worse than an unresolved symbol, which at least gets reported.
5. **Six different compile errors, one cause.** **Cause:** the game target exports its include paths and
   defines as PUBLIC but its compile options as PRIVATE, among them a forced include (`-include src/pc/compat.h`)
   that defines the disc types. **Fix:** repeat the forced include on your own target.
6. **The link stopped on four symbols.** **Cause:** they are variables the game writes to; a function stub
   would put that write into `.text`. **Fix:** define them as data.
7. **Access violations deep into a match** (one fighter's recovery special ending at frame 2926, another
   fighter at 3025). **Cause:** a crowd-reaction pointer that the match scene initialises and a headless host
   never set. **Fix:** call the game's own setup function where the scene does. Look for everything else a
   headless loop skips: here also a stage object whose only job is to increment a collision counter every
   frame, which the airborne floor checks depend on (see the game note).
8. **A possible hang no time budget can catch.** **Cause:** a `while` loop in the scene code is controlled by a
   network stub; a garbage `true` would loop forever on the host's game thread. **Fix:** fixed values for every
   stub that controls flow, and a worker process as the fallback if a hang ever shows up.
9. **The arena ran out after about 990 terrain reloads.** **Cause:** the collision loader allocates fresh
   tables on every call, and the arena only shrinks on reset (about 94 KB per reload, 190 KB for a 1,482-line
   mesh). **Fix:** the DLL's allocator records the first tables and hands the same blocks back on later loads
   of the same size: 2,000 reloads left the arena unchanged. A later multi-joint loader found per-island blocks
   still leaking (about 822 KB over 200 reloads) and replays those too (implementing agent's report).
   Swapping the guest's data under it has a second trap: fighters keep *indices* into the old line table, and
   an index past the new count made a line walk spin forever. Remap every stored index to the matching new
   line, or to -1 so the fighter falls (implementing agent's report, synthetic tests only).
10. **A build overwrote the player's installed mod, twice.** **Cause:** `dotnet build` of a tModLoader mod also
    packs the `.tmod` into the player's `Mods` folder (`tMLMod.targets` runs `BuildMod` after `Build`), whether it
    builds the live source folder or a copy. It happened during a verification, and again later from a different
    agent that built in place; the installed file was restored from a backup eight minutes after the second one.
    **Fix:** compile checks on a private copy with the pack target removed; build the packed `.tmod` with tModLoader's own `-build` command and a `-tmlsavedirectory` that points
    into a lab folder, so the file lands there (the outputs confirmed it); keep the installed `.tmod` read-only
    while that runs; hash it, and note its modification time, before and after every build; back it up before the
    first build; and write the rule in the project's rules file and in every agent's brief.
11. **A configuration the API accepted ran NaN on every frame.** **Cause:** the camera block's validation missed
    a zero field of view, in a field everyone had read as a tilt angle. A second model's review and a boundary
    fuzzer found more holes of the same kind. **Fix:** derive every rule from the guest's own asserts and
    divisions, then fuzz boundary blocks. After the fix, a second agent's own search accepted 2,258 blocks with
    0 failures, while 213 of its 292 control blocks broke the earlier DLL.
12. **A meaning changed without a version bump.** **Cause:** bumping the major version would break every
    existing host's handshake. **Fix:** a minor version in a reserved ABI field for additive changes, and the
    rule written in the header.
13. **The host's own terrain streaming silently replaced the guest's stage collision one tick after a replay
    started.** **Symptom:** a recorded match replayed inside the host game agreed with the original for about 55 s
    of match time and then diverged: the first differing frame was before the match began (the floor line index
    was 1 in the headless replay and 0 in the host), and later a dash grab that missed in the original connected in
    the host. The headless replay of the same inputs was exact. **Cause:** the mod's terrain-to-collision streaming
    runs every tick for any session that has a fighter. The replay builds its stage mesh itself, so the streaming did
    not consider it its own: on the next tick it sampled the host world's tiles (where the stage had been stamped
    as visual blocks), rebuilt collision from them and reloaded it into the engine. The log said so 0.1 s after the
    creation. The new mesh had another line order, another load mode, and walls on tile edges instead of the
    stage's real edge, shifted by under one unit, which was enough to let one attack reach a frame earlier.
    **Fix:** a collision lock in the engine session (every reload request is refused, counted, and answered "ok"
    as for an identical mesh), switched on right after the replay creates its fighters; the streaming idles during a
    replay; and a watchdog that checks every step that the installed mesh and the load counter are the ones from
    creation and writes `COLLISION REPLACED` into the result file if not. **Proof:** a synthetic console that
    repeated the host's reload path produced a trace identical to the host's in every column except the line
    indices; the same path with the lock was identical to the headless replay. In the real game the replay then
    matched the headless engine across the whole match and the original recording on all 5,524 frames. **Lesson:**
    in a host, find everything that talks to the guest every tick, not only what you call yourself.

## Verification
- Real run inside tModLoader: the DLL loads from outside the mod, the arena reservation succeeds, and the
  engine drives the fighter on every traced frame (2,892/2,892, no fallback), at the step cost above. A second
  agent re-ran it with its own comparator.
- Synthetic (a .NET 8 test host, not the game): layout checks on both sides, idempotent reset, runs after a
  reset bit-identical to the first run, and a panic, an access violation and an `abort` each returned as codes
  and recovered by reset. A second agent with its own host reproduced 181 frames bit for bit against a real
  recording and ran 58 API abuse calls; another ran 1,017 abuse probes of the pose API with 0 failures.
- The replay bench (29 real recordings, both ports) is the regression gate for every patch; see the bit-exact
  technique note.
- Integration: seven patches written in parallel, each in its own copy of the core, were merged in minor-version
  order into one DLL (53 exports). The bench stayed 29/29 identical, and a combined soak with everything switched
  on ran 8.3 million steps with 0 failures and clean rollback and determinism (implementing agent). A different
  agent's 10-minute soak of the same DLL also passed: 268 matches (about 89 hours of Melee), 0 crashes, 15,186
  rollback checks without differences. Two hidden clashes were caught on the way: one pose id used by two features,
  and a version number defined twice.
- The bench itself was checked with twelve deliberately broken builds, which found four false greens
  (`prove-your-replay-bench-can-fail-mutant-builds-exposed-four-.md`).
- **Not verified:** unloading and reloading the DLL in one process (unsupported by design), a guest hang, the
  worker-process variant, any machine but one.

## Seen in
- [Super Smash Bros. Melee's engine inside Terraria](../games/terraria/super-smash-bros-melee-s-decompiled-engine-inside-terraria-a.md)
- Related: `rebuilt-guest-engine-inside-a-host.md` (where a rebuilt engine can run, in-process or in a worker;
  this note is the in-process case done with a full decomp), `bridge-contracts-ownership-units-and-lifecycle.md`
  (the contract template followed here), `bit-exact-decomp-ports-reproduce-the-original-compiler-s-and.md`
  (making the hosted engine match the original) and
  `skinned-3d-models-inside-tmodloader-posed-by-an-external-eng.md` (drawing what it simulates). For testing it
  safely and honestly: `running-several-isolated-tmodloader-test-instances-in-parall.md` (parallel lab
  instances), `when-the-first-real-run-fails-suspect-the-oracle-re-deriving.md` (first-run failures) and
  `prove-your-replay-bench-can-fail-mutant-builds-exposed-four-.md` (mutant builds).

## Credits
- [melee-pc](https://github.com/999sian/melee-pc), the PC port whose library split, rollback snapshot and file
  cache made this possible.
- [doldecomp/melee](https://github.com/doldecomp/melee), the decompilation underneath, by its contributors.
- [tModLoader](https://github.com/tModLoader/tModLoader) and [mingw-w64](https://www.mingw-w64.org/).
- Built with AI agents. Claude Code and its agents implemented and verified, with each result re-run by a
  different agent; Grok reviewed designs and patches read-only as a second model.
