---
name: blitz3d-decomp
description: Decompile a Blitz3D game to readable Blitz source, including obfuscated builds (SCP - Containment Breach 2, symbols like _fTX8F4Z88ZZD), and port what it does to another engine. Covers SCP - Containment Breach and its forks (Ultimate Edition Reborn, CB Multiplayer, CB2), B3DDecomp, recovering hashed names, CB2's weapon code, Blitz3D runtime behaviour (fixed tick, Animate, CurveValue, Euler angles, Rnd), and animated .b3d models (viewmodels with bones and keyframes) into Roblox. Use when a Blitz3D game's code or animated models are needed.
---

# Blitz3D decompile and port

Blitz3D games ship as one exe: the runtime in `.text` and the compiled game in a resource module that
the runtime links at load. Ghidra on the exe shows only the runtime. The route that works:
**B3DDecomp disassembles the module, names are recovered, B3DDecomp decompiles it to Blitz source.**
Then the source is the spec for the port, and the original game stays the oracle.

Keep every disassembly and decompile outside any repo (convention: `~/<game>-decomp/`), and never
publish them; the scripts here are fine to keep. Leave proprietary DLLs that forbid decompiling alone
(CB2's `uemp.dll`): their export names in the exe are enough. Journal in the mod's `MODLOG.md`.

Already done for **SCP: Containment Breach 2**: its function map, weapon fields, timing and the P90 port
are in [references/cb2.md](references/cb2.md). Read it before redoing any of the steps below for CB2.

## 1. Tools

- B3DDecomp (juanjp600/B3DDecomp, C#, GPL-3): clone outside the repo, apply
  [references/b3ddecomp-cb2.patch](references/b3ddecomp-cb2.patch) (`git apply`; built on commit 2b3148b)
  so it gets through CB2-style builds, then `dotnet build Blitz3DDecomp.sln -c Release`. It needs a .NET 8
  SDK; a user-local one installs without admin (`dotnet-install.ps1 -Channel 8.0 -InstallDir <dir>`).
  Run with `DOTNET_ROLL_FORWARD=Major` and `bin/Release/net8.0` on `PATH`: the decompiler starts
  `Blitz3DDisasm` by name.
- Ghidra (headless) for the runtime side only. Its `.bat` launcher breaks on paths with parentheses
  (`Program Files (x86)`): copy the exe out first. `cmd` eats `%` in arguments: pass search strings in a
  file (`scripts/ghidra/DumpStringUsers.java OUTDIR @needles.txt`).

Done when `Blitz3DDecomp.exe` and `Blitz3DDisasm.exe` build.

## 2. Disassemble

`Blitz3DDecomp.exe <copy of game.exe>` writes `<game>_disasm/` (Code/ per function, Type/, Strings.txt,
BuiltIn/, Libs/, BuiltInSymbols.txt). For a stock build it continues to `<game>_decomp/`: done, skip to
step 5. If it stops with `Unrecognized function: @_builtIn_f<GARBLED>`, the names are hashed: step 3.

Done when `<game>_disasm/Code` has one file per function and `Strings.txt` lists the game's strings.

## 3. Recover hashed names

CB2-style runtimes register every builtin under `_f` + hash(lower-case name), and the compiler names user
functions and types the same way. `scripts/b3dnames.py` implements the hash (and documents it). It can't be
inverted, so hash candidates: every identifier of the game's open ancestors (for CB forks: Regalis11/scpcb,
Jabka666/scpcb-ue-my, juanjp600/SCPCB-Multiplayer-decompiled), the runtime's signatures, and the runtime's
own registration tables for commands the disassembler's scan missed.

1. Confirm the hash: `python -I scripts/b3dnames.py obf Rnd` must match a `_builtIn_` import. If not, the
   runtime differs: find its linker (Ghidra, the string `Can't find symbol`) and the name transform it calls.
2. Missing runtime commands: the runtime registers them as `(*rtSym)("%Rand%from%to=1", fn)` in a dozen
   table functions (CB2: all called from `FUN_10220720`). Decompile those with `scripts/ghidra/DecompAt.java`
   and pull the strings into a signatures file. CB2's is
   [references/cb2-runtime-sigs.txt](references/cb2-runtime-sigs.txt).
3. `python -I scripts/b3dnames.py recover <game>_disasm names.json --sources <ancestor sources> --sigs sigs.txt
   [--stub SYMBOL=Name]`. Stub whatever is still unresolved after the signatures (give each stub a matching
   line in the signatures file).

Done when the recover report shows every builtin resolved (CB2: 440/440; user functions and types only
partly resolve, 509/1640 and 89/173, since the game's own new code has no named source).

## 4. Rename and decompile

`python -I scripts/rename_disasm.py <game>_disasm names.json <game>_named_disasm --extra-sigs sigs.txt`, then
`Blitz3DDecomp.exe <game>_named_disasm/`. The script also rewrites the CB2 compiler's indirect userlib
calls and function-pointer calls and fixes dynamic-vector field types; the patch makes the decompiler skip,
not abort on, a function it can't finish.

When it still aborts, the exception names the construct: fix the input in `rename_disasm.py` rather than
the decompiler where possible, and never make a type setter silently ignore writes (the type propagation
then loops forever with no output).

Done when `<game>_named_decomp/` holds `Main.bb`, `Functions/`, `Types/` and `Decls/` and the run prints
at most a handful of `step5 failed` lines (CB2: 1298 functions, 2 failed).

## 5. Find the system

- Strings first: an asset path or sound the system loads (`grep -l StringConstant_<n> Code/*`).
- Data-driven templates: the init function stores constants into a template per item. If the game has an
  addon/JSON loader, it names every field (CB2's weapon loader did). `scripts/cb2_weapon_table.py` dumps such
  stores straight from the disassembly as a cross-check.
- Unnamed CB2 functions stay hashed (`T808422X82`): name them in the journal as you learn them.

Done when every number the port will use is traced to the line that sets it and the line that reads it.

## 6. Port

Read [references/blitz-runtime.md](references/blitz-runtime.md) before writing port code: Blitz3D's clock,
Animate, CurveValue, Euler angles, Rnd and entity calls behave in ways a straight transcription gets wrong.
For animated `.b3d` models (viewmodels, rigs, keyframes) into Roblox, follow
[references/b3d-to-roblox.md](references/b3d-to-roblox.md); its scripts are in `scripts/roblox/`.

Port step for step: same order, same constants, same tick. Mark every deviation in a comment with the reason.

## 7. Verify against the oracle

Measure the port against the decompiled numbers in the engine, not by eye: rates (shots per second at the
fixed tick), durations (frames / speed / ticks per second), aim (the sight's dot on the screen centre),
ammo on the server. Record each check and its result in the journal.

Done when every ported behaviour has a measured number next to the decompiled one.
