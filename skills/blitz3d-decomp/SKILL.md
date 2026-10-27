---
name: blitz3d-decomp
description: Decompile a Blitz3D game to readable Blitz source with B3DDecomp and port what it does to another engine. Covers SCP - Containment Breach-era and other .bb games, B3DDecomp, Blitz3D runtime behaviour (fixed tick, Animate, CurveValue, Euler angles, quaternions, Rnd), animated .b3d models (viewmodels with bones and keyframes) into Roblox, and where to stop (builds protected against decompiling, games and assets the user has no rights to). Use when a Blitz3D game's code or animated models are needed.
---

# Blitz3D decompile and port

Blitz3D games ship as one exe: the runtime in `.text` and the compiled game in a resource module that
the runtime links at load. Ghidra on the exe shows only the runtime. The route that works:
**B3DDecomp disassembles the module and decompiles it to Blitz source.** Then the source is the spec for the
port, and the original game stays the oracle.

Keep every disassembly and decompile outside any repo (convention: `~/<game>-decomp/`), and never
publish them; the scripts here are fine to keep. Leave proprietary DLLs that forbid decompiling alone: their
export names in the exe are enough. Journal in the mod's `MODLOG.md`.

Read the source when there is one: SCP: Containment Breach (Regalis11/scpcb) and its Ultimate Edition Reborn
fork (Jabka666/scpcb-ue-my) are open source under CC BY-SA 3.0.

**What a port may use.** A port that re-expresses a game's logic, or converts its models, keyframes,
textures or sounds, redistributes that game once it is published or uploaded (to Roblox too). Port only what
the user has the rights to: their own game, or an openly licensed one on its terms (SCP: Containment Breach:
credit it and keep the port under CC BY-SA 3.0, and check each asset's credits, since fan games mix
licences). Anything else stays a private study: nothing from it is uploaded or published.

## 1. Tools

- B3DDecomp (juanjp600/B3DDecomp, C#, GPL-3): clone outside the repo, then
  `dotnet build Blitz3DDecomp.sln -c Release`. It needs a .NET 8 SDK; a user-local one installs without admin
  (`dotnet-install.ps1 -Channel 8.0 -InstallDir <dir>`). Run with `DOTNET_ROLL_FORWARD=Major` and
  `bin/Release/net8.0` on `PATH`: the decompiler starts `Blitz3DDisasm` by name.
- If one function aborts the whole run, apply
  [references/b3ddecomp-skip-failures.patch](references/b3ddecomp-skip-failures.patch) (`git apply`; made on
  commit 2b3148b): the decompiler then skips a function it can't finish, with a `step5 failed` line, instead
  of stopping.

Done when `Blitz3DDecomp.exe` and `Blitz3DDisasm.exe` build.

## 2. Disassemble and decompile

`Blitz3DDecomp.exe <copy of game.exe>` writes `<game>_disasm/` (Code/ per function, Type/, Strings.txt,
BuiltIn/, Libs/, BuiltInSymbols.txt), then decompiles it to `<game>_decomp/`. Games built from SCP:
Containment Breach's code need the game's `fmod.decls` as a second argument (B3DDecomp's README: the shipped
decls drop a parameter from `FSOUND_Stream_Open`).

When it still aborts, the exception names the construct. Never make a type setter silently ignore writes to
get past one: the type propagation then loops forever with no output.

**Protected builds: stop.** Some builds are protected against this step: a modified compiler and runtime
hash every function, type and builtin name (B3DDecomp stops with `Unrecognized function:
@_builtIn_f<garbled>`; SCP: Containment Breach 2's client is built this way), or the module is encrypted.
Those are protections the developer added against decompiling. Don't reverse them: tell the user and stop
(`skills/mod-any-game/references/safety.md`). Current B3DDecomp undoes one of them by itself, without saying
so: an XOR on a `.b3dmod` section. List the exe's sections first (`objdump -h`, or any PE viewer) and stop if
it has one.

Done when `<game>_decomp/` holds `Main.bb`, `Functions/`, `Types/` and `Decls/` and the run prints
at most a handful of `step5 failed` lines.

## 3. Find the system

- Strings first: an asset path or sound the system loads (`grep -l StringConstant_<n> Code/*`).
- Data-driven templates: the init function stores constants into a template per item. If the game has an
  addon/JSON loader, it names every field.

Done when every number the port will use is traced to the line that sets it and the line that reads it.

## 4. Port

Read [references/blitz-runtime.md](references/blitz-runtime.md) before writing port code: Blitz3D's clock,
Animate, CurveValue, Euler angles, Rnd and entity calls behave in ways a straight transcription gets wrong.
For animated `.b3d` models (viewmodels, rigs, keyframes) into Roblox, follow
[references/b3d-to-roblox.md](references/b3d-to-roblox.md); its scripts are in `scripts/roblox/`.

Port step for step: same order, same constants, same tick. Mark every deviation in a comment with the reason.
The rights rule above covers the code as much as the models.

## 5. Verify against the oracle

Measure the port against the decompiled numbers in the engine, not by eye: rates (shots per second at the
fixed tick), durations (frames / speed / ticks per second), aim (the sight's dot on the screen centre),
ammo on the server. Record each check and its result in the journal.

Done when every ported behaviour has a measured number next to the decompiled one.
