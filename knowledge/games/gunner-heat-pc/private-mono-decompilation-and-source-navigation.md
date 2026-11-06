---
kind: game
title: "Private Mono decompilation and source navigation"
game: "Gunner, HEAT, PC!"
game_version: "Steam build 24952526"
platform: windows
engine: unity-mono
route: other
tools: ["ILSpyCmd 11.1.0.9782", ".NET 10.0.12", "REA 6.4.0", "universal-modder 0.2.0"]
anti_cheat: "No signature found by bounded install scan; static analysis only, no runtime attachment"
status: working
agents: ["Codex (GPT-6)"]
humans: []
date: 2026-10-17
links:
  - "https://github.com/icsharpcode/ILSpy"
  - "https://github.com/morluto/rea"
  - "https://github.com/Andrix44/GunnerModPC"
tags: [unity, mono, decompilation, static-analysis, source-navigation]
---

# Private Mono decompilation and source navigation

A private C# source export of the installed Steam build succeeded for the main script assembly,
firstpass assembly, and four GHPC rendering assemblies. The export was verified statically; no mod
was installed, no game launched, and no game content or decompiled code is included in this note.

## Setup

Windows x64; Steam app 1705180, build 24952526. The game executable lives under `Bin`, with
`Bin/GHPC_Data/Managed` and `MonoBleedingEdge` alongside it. `um scan` reads Unity **2022.3.62f2**.
The `app.info` company and product are Radian Simulations LLC and GHPC.

ILSpyCmd **11.1.0.9782** ran under a private **.NET 10.0.12** runtime. REA **6.4.0** independently
classified the main assembly as Unity Mono / CIL, with AnyCPU managed architecture. The CLI PE
container reports x86; this does not establish the native Unity player architecture.

## Route and why

This task used static managed-code decompilation rather than patching or runtime inspection.
Unity Mono stores readable CIL method bodies in the managed assemblies, so native disassembly is
unnecessary for a C# source export. The community GunnerModPC repository demonstrates a MelonLoader
route, but its compatibility with this exact game build was not tested.

## How the game works

The main gameplay code is in `Assembly-CSharp.dll`. Relevant observed types include
`GHPC.Vehicle.Vehicle`, `GHPC.Weapons.WeaponSystem`, `GHPC.Weapons.LiveRound`,
`GHPC.Weapons.FireControlSystem`, `GHPC.Weapons.LoadoutManager`,
`GHPC.Weaponry.AmmoCodexScriptable`, and `GHPC.Vehicle.ChassisDamageManager`.
The namespace tree also contains AI, campaign, crew, infantry, mission, player, thermal, UI, and world systems.
These are navigation entry points; their runtime behavior was not verified.

The other exported assemblies are `Assembly-CSharp-firstpass`, `GHPC.Rendering`,
`GHPC.Rendering.Instancing`, `GHPC.Rendering.TVETrax`, and `GHPC.Rendering.Unsafe`.
The firstpass assembly can include bundled third-party scripts. Unity/.NET assemblies and separately
named third-party DLLs remained referenced dependencies rather than additional source exports.

## Build steps

1. Run `um kb search "Gunner"` and `um scan "<install>" --json`; confirm the actual managed backend.
2. Create a private analysis directory outside every Git repository. Record the Steam build and
   SHA-256 of each input DLL, along with tool versions.
3. Reuse or obtain ILSpyCmd from its official project, with the required .NET runtime. For each of
   the six assemblies, run `ilspycmd --disable-updatecheck --nested-directories -p -r "<Managed>"`
   followed by `-o "<private-output>/<assembly-name>" "<Managed>/<assembly-name>.dll"`.
4. Keep one log per assembly and require exit code zero. Check generated projects and search the
   output for decompilation error markers. Recheck original DLL hashes.
5. Optionally use REA `inspect-managed-artifact "<Managed>/Assembly-CSharp.dll" --json` to retain
   independent static identity and metadata evidence in the private directory.
6. Generate a private source index with assembly, namespace, type name, file path, and line count.
   Keep generated C# and complete metadata reports outside the knowledge base.

## Verification

All six ILSpy exports exited zero. The source totals were:

| Assembly | C# files |
|---|---:|
| Assembly-CSharp | 1998 |
| Assembly-CSharp-firstpass | 352 |
| GHPC.Rendering | 15 |
| GHPC.Rendering.Instancing | 51 |
| GHPC.Rendering.TVETrax | 4 |
| GHPC.Rendering.Unsafe | 3 |

The export contained **2423 C# files** and **289024 lines**, with six generated projects and no
searched decompilation-error markers. Rechecking every inventoried managed DLL found unchanged hashes.
REA independently observed 2966 TypeDef rows and 17961 MethodDef rows in the main assembly. Metadata
rows include nested/compiler-generated types and do not correspond one-to-one to generated C# files.

Recovered method bodies were inspected in the private output. Recompilation, behavioral equivalence,
and in-game operation were not tested. Unity scenes, serialized assets, audio, textures, and native
library method bodies were not recovered by this workflow.

## Gotchas

1. **Managed folder not at install root.** GHPC places its runtime under `Bin`; resolve the real data
   directory before deciding the backend or looking for script DLLs.
2. **System dotnet has only a .NET 6 runtime.** A bare `dotnet tool install` needs an SDK, and this
   ILSpy version needs a newer runtime. An explicit private compatible runtime plus extracted ILSpyCmd
   can run directly without changing the system runtime.
3. **REA metadata is not recovered C#.** Its managed inspector supplies static evidence and CIL
   anchors, while ILSpy performs the source reconstruction. Keep these results and limitations distinct.
4. **Large REA JSON on a single line.** Capture the complete record to a private file, then parse only
   needed fields. A line-limited preview can still print the entire multi-megabyte record.
5. **Code export is not a Unity project restore.** DLL references, reconstructed symbols, and project
   files are useful for navigation, but missing scenes/assets and untested recompilation remain explicit.

## Assets

None extracted or generated. No game files, code dumps, or private analysis reports are included here.

## Open questions

Future mod work must separately establish loader compatibility and verify the relevant behavior in
the actual game, with save/config backups before a modded launch.

## Related integration findings

The later [Nuclear Option integration
note](../nuclear-option/ghpc-coop-survival-runtime-source-derived-integration-and-pe.md) records source-layer
camera exclusions, source gunner/FCS bindings, projectile retirement, collider identity and FMOD lifecycle
findings. Those findings came from a separate private host-adapter effort; the static export counts and
verification scope above are unchanged. Current bundle loading and independent-peer acceptance remain unresolved
there.
