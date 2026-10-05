---
kind: technique
title: 'Loading Pre-Sequel assets in Borderlands 2: header-only package surgery, mesh conversion and what still fails'
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: ["@Pherdee-boi"]
date: '2026-10-04'
links: []
tags: [ue3, unreal3, gearbox, borderlands, borderlands-tps, upk, package, staticmesh, shaders, tfc, porting, pyunrealsdk]
---
# Loading Pre-Sequel assets in Borderlands 2: header-only package surgery, mesh conversion and what still fails

> Borderlands 2 and The Pre-Sequel (TPS) are the same UE3 branch: both cook packages as version 832,
> licensee 46. This note is how an agent got TPS's laser beam particle systems and TPS's tether mesh to load
> and render inside BL2, from the user's own TPS install, by patching a copy of TPS's `Startup.upk` header
> and converting one native format. TPS's shader cache still crashes BL2, so materials come from BL2.
> Nothing from either game is shipped: the user runs the converter on their own files.

## When to use it
- You want an asset from TPS (or another cooked UE3 game of the same version) inside BL2, loaded by an SDK
  mod, without a GUI tool.
- You need to know which parts of a cooked TPS package BL2 can read as-is and which crash it.

## How
**1. Find the assets.** TPS keeps all laser content in `Startup.upk`: `GD_Cork_Weap_Lasers` (types,
balances, firing modes), `FX_CO_Wep_Laser` (particles, meshes, materials, textures), `Weap_Co_Lasers`
(models), `Ake_Cork_Wep_Lasers` (audio). Decompress a copy (see `reading-ue3-gearbox-games-offline.md`).
The OpenBLCMM-Data TPS pack has the property dumps.

**2. How BL2 loads a foreign package.**
- Put the file in `WillowGame/CookedPCConsole/` and restart (the package list is read at startup). Name it
  after the root package you want to address, e.g. `FX_CO_Wep_Laser.upk`.
- `DynamicLoadObject("Pkg.Obj", Class)` on an object of a package that isn't loaded returned None. What
  works is `unrealsdk.load_package("Pkg")`, which loads the **whole** package; then `find_object`.
- Loading the same package a second time crashed the game. Load once, keep a flag.
- Root what you keep (`ObjectFlags |= 0x4000`, RF_RootSet).

**3. Make the copy loadable by patching only header bytes** (export data keeps its offsets):
- **Summary:** BL2 silently refuses a cooked package from another cooker. Set `CookerVersion` to BL2's
  (134; TPS had 0x80086) and `EngineVersion` to BL2's (1712575; TPS 2630070). Clear
  `PKG_StoreFullyCompressed` (0x04000000) in the package flags when you store the file decompressed.
- **Root:** in a seek-free `Startup.upk` each original package is a top-level export flagged
  `EF_ForcedExport` (0x1). Re-parent the children of the package you want (outer → 0, the file's root) and
  clear `EF_ForcedExport` on that subtree.
- **Only load what you need:** compute the closure of the objects you want (tagged object references from
  the dumps and the binary, plus a material's native `UniformExpressionTextures`). Clear
  `RF_LoadForClient | RF_LoadForServer | RF_LoadForEdit` (0x0007000000000000 in the 64-bit object flags) on
  every other export: `load_package` then never creates them (52,000 of 52,600 exports here).
- **Imports:** point every import nothing in the closure needs at the `Core` package, so TPS-only classes
  and missing assets are never looked up. Retarget a TPS-only class used by the closure to a BL2 class with
  a compatible role (here `Engine.OzParticleModuleLocationLine` → `Engine.ParticleModuleLocation`, whose
  unknown properties are skipped on load).
- **Shared content both games have** (e.g. `FX_Shared_Sparks`): leave it out and assign BL2's copy at
  runtime.

**4. Streamed textures.** A texture's top mips may live in a `.tfc` (here TPS `CharTextures.tfc`); BL2 has a
file with the same name but different contents. Copy just those LZO blocks into a new `.tfc`, set the
texture's `TextureFileCacheName` to an existing name entry, and rewrite the mips' offsets in place.

**5. Static meshes need converting** (they crashed BL2's loader as-is). Diffing meshes that ship in both
games' Startup showed one real difference:
- TPS packs vertex positions: stride 8, two extra bytes, a bias and scale (3 floats each), then int16 x, y,
  z, w per vertex, position = bias + scale × v / 32767. BL2 stores stride 12 and three floats.
- BL2 has one more byte (zero in every shared mesh) 44 bytes before the end of the native data, right before
  the lighting GUID.
- Inline bulk-data headers store the absolute file offset of their payload. After converting, append the
  export at the end of the file, update its serial offset and size, and rewrite those offsets.
- Converted TPS copies of shared meshes match BL2's bytes except for the material reference and position
  rounding.

**6. Drive what TPS's engine drove.** The TPS beam is a local-space mesh emitter. TPS's firing mode has
fields BL2 lacks (`BeamLengthScaleName`, `BeamMeshRestSize`, `BeamContinuousDamage*Name`), so in BL2:
- put the TPS particle system into BL2's beam firing mode (`PartSysTemplate`); BL2 spawns it and feeds
  `SourceLocation`, `TargetLocation` and `Direction` (same parameter names);
- each frame, find the component BL2 spawned and set `BeamLengthScale` (length / rest size), the damage-ramp
  parameter, its translation and its rotation toward the target.

## Gotchas
1. **Silent "None" from `load_package`.** **Cause:** cooker/engine version mismatch in the summary.
   **Fix:** BL2's values (step 3).
2. **Crash while loading.** **Cause:** a native format BL2 reads differently. Find it by staging: build
   one test package per piece (texture, mesh, shaders, material), load them in order, and append a progress
   line to a file with `fsync` before each load (the SDK log loses its tail in a crash). Here the texture was
   fine, the mesh and the shader cache crashed.
3. **TPS `SeekFreeShaderCache` crashes BL2.** BL2 keeps all material shaders in
   `RefShaderCache-PC-D3D-SM3.upk` (chunk-compressed); TPS embeds a shader cache per package. Without
   shaders a TPS material can't render, and BL2 can't rebuild it (cooked materials keep only their parameter
   expressions). **Fix (for now):** a BL2 material, or a runtime `MaterialInstanceConstant` of a BL2 master
   with the TPS texture.
4. **Python traces don't work in BL2's SDK** (see the BL2 game note), so you can't find where a beam hits
   from the mod. **Fix:** let BL2's beam code compute the ends and read them back from the component's
   parameters.
5. **Crash dumps** (`WillowGame/Logs/*.dmp`) showed exception code 0x1 raised from KERNELBASE, which is
   the engine's fatal-error path. The text of the last mod log line was still in the dump's memory when the
   log file didn't have it.

## Open questions
- Port TPS shaders: decode BL2's shader cache format (per shader type) and translate the TPS entries, or
  accept BL2 materials.
- Check the remaining native formats (skeletal meshes, AkEvents) the same way before porting whole guns.
