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
date: '2026-11-13'
links:
- https://github.com/adonis-singh/re4
tags: [reverse-engineering, ghidra, decompilation, address-map, rtti, vtables, direct3d9, xact]
---
# Naming the RE4 (2005) PC exe from the GameCube decompilation

**Result:**
- 8,068 of the PC `bio4.exe`'s 18,479 functions are named, plus 843 library functions recognised by Ghidra (about
  61% of the code by size), and about 170 globals.
- The names come from the complete GameCube decompilation (adonis-singh/re4) and, for the PC-only layers, from
  what the code does.
- Only one name is still an automatic guess. Every other one is pinned by evidence, anchored on a string, vtable or
  routine table, or named by hand.
- Six held-out runs found the automatic matcher 95–99% correct, and the remaining guesses were then read side by
  side against the GC source.

**Coverage:**
- **GameCube gameplay code:** the player, inventory, all enemies, weapons, cameras, collision and room scripts.
- **PC-only layers, hand-reversed:**
  - the Direct3D 9 render thread and its command layer;
  - the HD texture-pack loader;
  - every shader parameter;
  - the XACT 3 sound system.
- **Outputs:** a plugin header of RVAs and a named Ghidra database.

## Setup
- Static analysis only, on a copy of the untouched 2018 exe (Steam keeps it as `Bin32\bio4.exe.bak` when mods
  patch `bio4.exe`). No game launch needed.
- Ghidra 12.1.4 headless (`analyzeHeadless -import ... -postScript`), about 6 minutes of auto-analysis. Later
  passes use `-process ... -noanalysis -readOnly` with small export/decompile scripts.
- The GameCube decompilation provides `config/G4BE08/symbols.txt` and `sym_map.tsv` (names, GC addresses,
  units), `src/` and `include/` (class declarations with virtual order, the Dolphin SDK headers).

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
- **The PC-only layers have no GC twin.** They were named from the API interface slots they call (Direct3D 9,
  XACT 3), their log strings and the work arrays they walk.

## How the game works (what we had to learn)

**GameCube logic**
- **The PC port is the Xbox 360 HD port's code:** build path `RE4HD\Development\project\bio4pc`, platform layer
  `Hap\XBOX360\`.
  - Input, rendering, sound, saves and options are rewritten.
  - Everything else is the GameCube logic, very close to the decomp. Some room scripts were revised in the later
    ports, though, so the PC body can be longer than the GC source.
- **Link layout:** each source file stays contiguous. Files are ordered alphabetically (case-insensitive) within a
  folder, but functions are shuffled inside a file.
- **Every call goes through an incremental-link `jmp` thunk** (0x40xxxx). The call graph only works after
  resolving thunks.
- **Single inheritance vtables:** the base's slots come first, then new virtuals in declaration order.
  - The PC added slots in `cPlayer` (slot 9) and `cObjWep` (slots 9 and 16).
  - The PC made GC's non-virtual `reloadable()` virtual (slot 19).
- **The PC emulates GameCube REL modules:** a link routine picks a module table (enemies, stages, weapons, sound)
  and installs each module's prolog/epilog. The stage prologs fill the room table with every room's init/main
  pointer. That is how all 244 rooms' Init/Main functions were named.

**Rendering (PC only)**
- **There is a separate render thread.** A start routine creates it, plus three events the exe names itself
  ("GXProcessRequestStartEvent", "GXProcessStartEvent", "GXProcessEndEvent") and two 3 MB command buffers that
  swap every frame.
  - A command is {handler pointer, 16-bit size, arguments}.
  - While the device is lost, only a whitelist runs: present, plus the texture-pack and texture-object commands.
  - **Draw only on that thread** (between BeginScene and the frame present, or in a d3d9 EndScene/Present hook).
    Hooks on the game thread must queue their work.
- **The game still calls GameCube GX functions.** On PC each is a three-layer chain:
  - a game-side wrapper with the GX name that only queues a command;
  - a render-thread handler that unpacks it;
  - the implementation that touches Direct3D 9.

  The wrappers are laid out in alphabetical order (with one exception, `GXSetTexCopySrc`/`Dst`). That is how
  the unnamed ones were placed: argument sizes were matched against the Dolphin prototypes in each alphabetical
  gap.
  - `GXCopyDisp` is the frame present.
  - The GameCube vertex macros (`GXPosition3f32`, `GXColor4u8`, …) are real queued functions on PC.
- **HD texture packs:** a loader reads `ImagePackHD` or `ImagePack` (chosen by the config's HD-texture option)
  `\<id as 8 hex digits>.pack`, or a `.pack.yz2` compressed variant, into 64 pack slots. Sync and async versions
  exist, plus release by id / group / mask. This is the natural hook for texture replacement.
- **Shader parameters:** alongside the GameCube colour-combiner (TEV) setup, the game queues about 50 one-value
  setters that tell the D3D shaders which slot plays which role.
  - **Texture slots:** which GX texture map is bound to a fixed D3D sampler (s0 shadow / screen copy … s10 global
    illumination).
  - **Stage colours:** which TEV stage's constant colour goes to which pixel-shader constant.
  - **Texture matrices:** which texture matrix goes to which vertex-shader constants.
  - **Mode flags:** written into components of PS c0/c1 and VS c4, and ORed into a shader-variant word. The model
    draw compares that word against exact keys to pick its pixel shader.
- **Developer debug switches:** the main model draw has data-only switches (never written by the game) that skip a
  permutation, a draw-count range, a draw kind or a shader mode. They are handy for isolating draws.

**Sound (PC only)**
- **XACT 3 replaces the GameCube audio layer**, under the unchanged GC sound logic (SndInit, the voice-work code).
  - The engine loads `BIO4\snd\bio4_project.xgs`, sets up X3DAudio and sets the "Default" and "Music"
    categories. Sound runs on its own thread, behind one critical section.
  - Banks are .xwb/.xsb pairs (`bio4bgm`, `bio4evt`, plus per-room banks).
  - **Cue names are decimal numbers:** the game formats the number as text and asks the sound bank for that cue
    index.
  - Per-cue volume is the XACT cue variable "bio4_volume".
  - A 96-slot table holds the playing cues; there are separate work arrays for sound effects, streamed music and
    event sounds.
- **config.ini:** a save routine writes it and a load routine reads it, writing defaults first when it's missing.
  It holds 18 integers: resolution, vsync, fullscreen, adapter, shadow quality, motion blur, post-processing, HD
  textures, antialiasing, anisotropy, variable frame rate, subtitles and laser RGBA.

## Build steps
1. **Export:** a Ghidra postScript writes, per function, its direct callees (thunks resolved), referenced strings,
   globals, immediates, `.rdata` float constants, and the `ecx` loaded before each call. A second script dumps
   all RTTI vftables. A third lists every **non-call** reference to a function entry (stored function
   pointers): that is what pairs each render command with the code that queues it.
2. **Decomp side:** per function, string literals, call names, numeric literals and referenced globals.
   - Multi-line `#define`s must be skipped with their `\` continuations.
   - Keep overloads apart.
   - Expand calls through the header inlines (we found 584, including in-class methods). For example, the GC
     room-flag macros call the room-save accessor, so PC room scripts calling it is expected.
3. **Matcher phases:**
   - Pinned names and anchors: hand-checked pins, function-pointer tables, vtable slots.
   - Unique strings.
   - Call-graph voting.
   - Unit-range scoring.
   - Singleton `this` evidence.
4. **SDK names from call sites:** the GC source calls Dolphin SDK functions it never defines. Align each confirmed
   pair's PC callee list with its GC call list; named callees are fixed points, and equal-length gaps pair up by
   position. Accept a name only with 3+ votes and an 80% share.
5. **Hand passes on the PC-only layers:**
   - classify functions by the API vtable offsets they call;
   - name them from log strings and debug-event labels;
   - record each unnamed fact (an argument's role, a slot meaning) by checking where the draw code consumes it.
6. **Settle the remaining guesses side by side:** score the PC decompile against every function in the guessed
   GC file (rarity-weighted literals, including float constants read from `.rdata`, plus calls and strings). Then
   read the close calls and pin, rename or block.
7. **Apply and curate:** apply names to Ghidra (creating functions where needed) and generate a curated C header of
   RVAs. After every pass, diff the map against the previous one: a pass should change only the names it
   intended.

## Verification
- **Holdout:** hide 30% of the string anchors and rerun. 93% correct at first, 97–99% after the structural
  anchors.
- **Runtime-proven addresses from two existing plugins** land where expected: `pPL`, `CamCtrl`, `IdSys` and
  `EmMgr` exactly; the camera midhook inside `CameraMove`; the money-drop hook in `RandomItemCk`.
- **Hand reading:**
  - Several hundred gameplay functions were read against the GC source, and all 60 last guesses were read side
    by side.
  - The PC-only layers are named from API slots that the D3D9/XACT ABIs fix, and from the game's own log strings
    and event names.
- **Header:** compiles cleanly under MSVC /W4.
- **Not verified in the running game:** the render-thread split, the shader-slot meanings and the sound tables are
  static readings. A plugin logging the thread id in a Present hook would confirm the first. Check a name against
  your use before hooking it.

## Gotchas
1. **Call graph looks random.** **Cause:** incremental-link thunks. **Fix:** resolve every call/vtable target
   through its thunk.
2. **Matcher names move between reruns.** **Cause:** score ties and overloads. **Fix:** pin checked names in a
   file loaded first; select overloads by source order or by file; block wrong addresses.
3. **Seven different routines all parsed as one name.** **Cause:** a multi-line macro before them. **Fix:**
   follow `\` continuations when skipping preprocessor lines.
4. **Vtable naming is off by one in some classes.** **Cause:** PC-added virtuals. **Fix:** align on purecall
   slots and on each subclass's GC override set.
5. **The "PadRead" match is wrong.** **Cause:** the PC replaced input with its own routine. **Fix:** expect no GC
   twin in the input, render, sound and save layers.
6. **Function-pointer tables don't align.** **Cause:** tiny table-only bodies are not functions in Ghidra.
   **Fix:** accept any `.text` pointer in a table run.
7. **A global lands a few bytes off.** **Cause:** member accesses dominate the vote. **Fix:** use the `ecx`
   (`this`) evidence for singletons.
8. **Every decompile ends in a call to a "vector" function with `cookie ^ stack`.** **Cause:** the matcher had put
   a Dolphin math name on MSVC's 15-byte `__security_check_cookie`. **Fix:** name it; any tiny function called
   from hundreds of epilogues is the /GS check.
9. **A room function's PC body differs completely from the GC source, yet the name is right.** **Cause:** the PC
   descends from the later ports, and some room scripts were revised there. **Fix:** before blocking a name,
   check whether the PC body references the GC function's own helpers (the EndProc/_exit it registers with the
   scene-cancel call, or callees only 1–3 GC functions use). If it does, pin it.
10. **Literal matching misses obvious twins.** **Cause:** MSVC keeps float/double constants in `.rdata` behind
    data references, while the GC source has them as literals. **Fix:** read the values behind the data
    references from the exe and compare them as constants.
11. **Literal scores favour big functions.** **Cause:** a room's huge Init function shares the most constants with
    anything. **Fix:** normalise (weighted cosine, Jaccard for calls/strings) and never rename or block from the
    score alone; read first.
12. **Callee lists show contradictions that aren't.** **Cause:** the GC source calls header inlines (room-flag
    macros, item-type helpers), whose bodies the PC calls directly. **Fix:** expand GC calls through the inlines
    before comparing.
13. **Weak "callers agree" pins can be wrong.** **Cause:** two functions that are always called together share
    callers. (`GXSetTexCopyDst` sat on `GXInitTexObj`, and `GXLoadLightObjImm` on `GXInitLightColor`.) **Fix:**
    confirm against the body or a unique caller (every `*GetEFB` function calls the real copy-texture pair).
14. **Camera-tool names inside the sound layer.** **Cause:** single-string bulk pins on unrelated code. **Fix:** a
    function whose own log string names it (`[SndStremPlay]`, `GXInit :`, `[SndFileToLoad]`) beats any matcher
    name.

## Assets
None.

## Cost and time
Two long sessions (two days).

## Open questions
- **Still unnamed:**
  - the CRI middleware and the CRT;
  - about 55 small sound helpers (fade and pan math);
  - two texture commands;
  - the shader draw variants that have no single caller.
- **One automatic guess is left:** `MessageControl::loadFont`.
- **About 25 room-script functions were blocked** (not the guessed function, and their real names unknown). Many
  are probably PC-revised variants or functions that were split differently. A runtime breakpoint in the room would
  name them.
- **Not checked in the running game:** the render-thread and shader-slot conclusions.
