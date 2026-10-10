---
kind: technique
title: "Disrupt engine shader and model modding (Watch Dogs 1/2/Legion)"
tags: [disrupt, ubisoft, watch-dogs, shaders, dx11, d3d12, raytracing, models, xbg, material]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links: []
---
# Disrupt engine shader and model modding (Watch Dogs 1/2/Legion)
> Disrupt is Ubisoft's Dunia 2 (Far Cry 3) fork that powers Watch Dogs 1, Watch Dogs 2 and Watch Dogs: Legion. It renders with deferred lighting plus a forward transparent pass: geometry fills a G-buffer, a multi-pass deferred lighting job evaluates direct lights, and light probes supply indirect ambient. Shaders are custom HLSL-like `.fx` files compiled to DXBC with a per-file `.header` stub the engine needs to load them; models are XBG meshes referenced through `graphickit_*` / `items` XML and material descriptors. This note covers both routes and separates what has been verified from what is inferred.

## Setup

- **Shader source (WD1)**: the game ships full HLSL source in `shaders.dat`/`shaders.fat` (62 MB, 595 entries, magic `0F F5 12 EE`); the extracted tree is `shaders_unpack/engine/shaders/` (775 files, ~107 includes + 234 `.fx`/`.meta.xml`/`parameters`).
- **Shader compiler**: the `.fx` sources compile with the Windows SDK x64 `fxc.exe` (on `PATH`); on Linux use DXC (e.g. `~/.local/bin/dxc`). The compile-and-repack workflow follows the community's `Disrupt-Shader-Compiler` (Miru); that repository carries no license and ships the game's own shader files, so treat it as a reference for the workflow rather than a redistributable package. The shader sources still have to come from unpacking your own `shaders.dat`/`shaders.fat` with Gibbed.Disrupt, not from a bundled third-party package.
- **Model tooling**: `DisruptEditor` (C++/SDL2/OpenGL, MIT; Linux port builds with CMake + system SDL2/OpenGL), a community Blender add-on, `glm2obj` (C++ GLM→OBJ), `material_bin.py` (TAM material reader/writer).
- **Archive tooling**: `Gibbed.Disrupt` (.dat/.fat unpack/pack, .NET 8.0) to get at `shadersobj.fat` and asset archives.

## Route and why

- **Shader modding** is the highest-leverage route on WD1 because the shipped source tree is complete. WD1 ships the source; WDL does not (you get compiled objects only). The `PreparePlatformData64.exe` pipeline seen in the research comes from a **leaked 2020 dev build** — it is **not present in retail**, so it is not the official route and should not be relied on.
- **Model modding** splits into two levels: (1) pure-XML reassembly — repoint `graphickit_models` / `graphickit_parts` / `items.lib` IDs to existing models or parts, no mesh authoring; (2) actual mesh work — parse/export XBG via `DisruptEditor`/`glm2obj`, edit in Blender, convert back.
- **Ray tracing / RTGI** is a research route, not a shipped mod. WD1/WD2 are DX11-only (no hardware RT); WDL has a native D3D12 RT path. Engine-level passes are provably injectable in WD1 via ASI/DLL-proxy hooks (Shadow Engine), but no RTGI integration has been verified in-game from these notes.

## How the game works

**Rendering pipeline** (verified from shader source + Wii U debug symbols + decompilation):

1. Depth pre-pass
2. G-buffer fill
3. `CMultiPassDeferredLighting` — deferred light accumulation (`deferredlighting.fx`, shared `lighting.inc.fx`)
4. Forward transparent pass (water, glass, particles — `forwardlighting.inc.fx`)
5. Post-processing (bloom, DOF, color grading, FXAA/SMAA, motion blur)
6. UI/HUD overlay, present

**G-buffer layout** (from `gbuffer.inc.fx`): `SV_Target0` albedo RGB + alpha/test; `SV_Target1` packed world-space normal; `SV_Target2` specular mask + glossiness (glossiness, not roughness); `SV_Target3` material flags (character, hair, reflection); `SV_Target4` velocity/motion vectors; plus scene depth. Ambient occlusion is pre-baked. Light probes (`lightprobes*.fx`, `SRadianceTransferProbeCompute`, 32 B SH radiance-transfer struct) supply indirect/ambient lighting.

**Shader identity and compilation** (Ubisoft's `ShaderCompiler2` tool): `ShaderGenerator2` → `ComputeShaderID` → `TShaderID<uint64>` where high bits are the family and low bits the define-variation → `d3dcompiler_47.dll` → `obj/pixel_<id>.pso`. Base string hash is FNV-1 64 (`NomadDefaultHashFunctor`). `ShaderCompilerUtils_r64.dll` is obfuscated (bogus export AddressOfFunctions RVA, ordinal-only), so `ComputeShaderID` is not resolvable through the export directory.

**Shipped object format**: compiled `.pso`/`.vso`/`.cso` are a `.header` stub followed by the DXBC container (first u32 = content version 0–9). Measured across all 39,136 retail entries, stub lengths are **4/8/12/16/20/24/40 bytes** (4 and 12 dominate). The `.header` stub is mandatory — without it the engine refuses the shader. A separate 2-byte `.crc` file is the verifier. Verified on retail: a 300-file sample of the base unpack had zero files with `DXBC` at offset 0.

**Model representation**: XBG meshes (i16 vertices, indices, material references) referenced by hash from XML. `graphickit_models.lib` defines composed/single models as an ordered list of parts (each with a part ID, material variation ID, and per-part position/rotation/scale). `graphickit_parts.lib` defines the parts and their material overrides. `items.lib` defines shop items (outfit → model ID, icon, price, access ID). Materials are TAM binaries (v7 little-endian magic `54 41 4D 00`, v5 big-endian magic `00 4D 41 54`) pointing at textures wrapped as XBT (DDS wrapper).

## Build steps

**Recompile a shader family (WD1):**
1. Unpack `shaders.dat`/`shaders.fat` from your own install with Gibbed.Disrupt; the extracted tree is `engine/shaders/`. Put the Windows SDK x64 `fxc.exe` dir on `PATH` (Windows), or use DXC (e.g. `~/.local/bin/dxc`) on Linux.
2. Compile **all** shaders once first — the engine needs consistent input/output signatures across the database. Then compile a family (e.g. `Mesh_DriverGeneric`, or `.fx` for everything). The database has 178 families and roughly 128k permutations; that permutation list itself **cannot be regenerated from retail alone** (it comes from the engine's `ComputeShaderID`, which is not resolvable from the shipped binaries — see "Shader identity and compilation").
3. Each compiled output gets the shipped `.header` stub prepended (`engine/shaders/obj/hXX/<name>.<type>.header`); output goes to `COMPILED/engine/shaders/obj/hXX/`.
4. To load from disk: unpack `Watch_Dogs\data_win64\shadersobj.fat` with Gibbed.Disrupt, rename `shadersobj.fat`/`.dat` to `.bak`, and move the unpacked `engine/` folder to `Watch_Dogs\data_win64\`.

**Edit a model (XML-level, WD1 example):**
1. Change `graphickitmodelModel` (BinHex model ID) in an `items.lib` outfit XML, keeping `hidKey` unique, to load a different existing model.
2. Or add parts to a `graphickit_models.lib` entry: a part `<object>` with `graphickit part ID` and material variation ID; position/rotation/scale only affect non-skinned geometry (hats, accessories), not animated skinned meshes.
3. Material overrides in `graphickit_parts.lib` name the `.material.bin` (hex-encoded path field); textures are XBT → convert with `xbt2dds`, edit DDS, then re-wrap by **stripping the original XBT header and re-prepending it** (a generic `dds2xbt` header is rejected).

**WDL shader archive (from a leaked dev build, not retail):** a 2020 dev build ships `PreparePlatformData64.exe -platform=win64 -shadersobj=all` (wipes `obj/`, ~6 h) or `-shadersobj=bigfileonly` (repack only). Compiled shaders live in `data_win64/engine/shaders/obj/` (+ `obj_editor/`). DX11 shaders compile; the DX12 path is unclear. This tool is **not present in the retail game**.

## Verification

- **Verified**: G-buffer target semantics and pipeline order (shader source); `.header`+DXBC object layout (300-file retail sample); `.dep` checksum = FNV-1 64 of raw CRLF bytes (`fnv164(DepthShadow.inc.fx) = 0xb8d6781ddfedf051`); FNV-1 64 base hash; the shader registry (`fastinitdata.bin`, 128,973 IDs) must contain a modded shader ID or the engine won't load it (a leaked dev build also ships `FastInitData_editor.bin` with per-family membership, but retail reads `fastinitdata.bin`); XBG parser behavior and TAM material v5/v7 endianness; model part reassembly in XML (community-reported working for cars, partial for outfits).
- **Inferred / not verified**: RTGI integration in WD1/WD2 (the RTGI document is an architecture analysis and proposal, not an in-game result); WDL DX12 shader recompile path; the exact retail build toolchain for WD1 shaders.
- **Refuted / closed**: reproducing the leak's bare-entry shader style. Neither fxc nor DXC compiles it (E5004 / X3502 "missing semantics"), and every available d3dcompiler (MS 43/46/47, wine/vkd3d) rejects bare input-struct members. The shipped `.pso` encodes the exact ISGN/OSGN semantics (e.g. bbox PS: ISGN=SV_Position, OSGN=SV_Target) — derive semantics from those, don't guess.

## Gotchas

1. **Symptom.** Compiled shader is rejected by the engine / no visual change. **Cause:** the `.header` stub was not prepended to the DXBC. **Fix:** prepend the shipped per-file `.header` stub (`engine/shaders/obj/hXX/<name>.<type>.header`); a correct compiler wrapper does this — don't strip it.
2. **Symptom.** A single shader family compiles but the game misbehaves. **Cause:** only part of the database was compiled, so input/output signatures are inconsistent. **Fix:** compile all shaders once before compiling any specific family.
3. **Symptom.** A modded shader never loads. **Cause:** its shader ID is not registered in the shader registry. **Fix:** register the ID in `fastinitdata.bin` (the file retail reads; top byte `sid>>56` = family ID). A leaked dev build's `FastInitData_editor.bin` is not what retail loads.
4. **Symptom.** fxc/DXC errors `E5004` / "Semantic must be defined" on the community source. **Cause:** the reconstructed source uses bare struct members; the retail compiler style isn't reproduced. **Fix:** derive the real ISGN/OSGN from the shipped `.pso` and annotate the source to match; don't try to force bare-member compilation.
5. **Symptom.** Linux compile fails on missing paths / case mismatch. **Cause:** a Windows-generated compile manifest may carry title-case paths (`meta\DeferredLighting.fx`) while on-disk files are lowercase. **Fix:** resolve source case automatically (or write a small case-insensitive resolver); don't hand-fix paths.
6. **Symptom.** Model edit does nothing / wrong proportions. **Cause:** position/rotation/scale on a skinned mesh is ignored, or you edited the wrong ID field. **Fix:** only non-skinned parts honour transforms; verify the part ID and reversed byte order between `graphickit_models.lib` and `graphickit_parts.lib`.
7. **Symptom.** FCBastard crashes on WD2/WDL. **Cause:** a Vector3 buffer overflow on `colorColor`; FCBastard's latest works on WD1 only. **Fix:** use WD1-only FCBastard for those files, or other tooling; don't assume cross-title support.
8. **Symptom.** `ConvertBinaryObject` crashes on old material files. **Cause:** pre-2014 / beta material assets. **Fix:** use `material_bin.py` instead; it auto-detects v5 BE vs v7 LE.
9. **Symptom.** WD1 colorgrading changes are ignored. **Cause:** any channel left at default (R/G/B=0, Saturation=1, Contrast=0) makes the whole colorgrading file ignored. **Fix:** set dummy values (±0.001) for unused channels; don't make them too small or weather transitions break.

## Assets

- **WD1 shader source**: `Watch_Dogs/shaders_unpack/engine/shaders/` (also `shaders_test/`, identical). Shader struct header for Ghidra/IDA: `disrupt_shaders_gpu.h` (203 constant-buffer structs incl. `LightDataCB` 412 B, `SRadianceTransferProbeCompute` 32 B, `GBuffer` 104 B), regenerated by `shaders_to_header.py`.
- **Shader registry**: `fastinitdata.bin` (128,973 IDs); a leaked 2020 dev build also has `FastInitData_editor.bin` + `.debug.xml`.
- **Models**: `DisruptEditor/` (patched working version, material conversion + XBG import/export); `glm2obj/`; a community Blender add-on; `create_pimg.py` / `xbg_to_pimg.py` (XBG→PIMG `.high.xbgmip` for WD1).
- **Material data**: `materialNames.txt` (916 CRC32→parameter names), `materialdescriptors/` (44 shader types).
- **Shader addon framework**: Parallellines' addons (`ADDON_XEGTAO`, `ADDON_CUBICLIGHTPROBES`, `ADDON_HORIZONFADE`, etc.) — 40+ defines for extending engine shaders.
- **Engine-level patch reference**: `temdah/Shadow-Engine` (WD1; expands shadow maps 16→30 across five executables; documents construction-window, pass-registration, capacity-layout, transaction and activation-proof contracts).

## Cost and time

- Full shader database compile: heavy (the Windows compile step wipes output and compiles ~128k permutations). WDL's dev-build `-shadersobj=all` is ~6 hours and wipes the obj folder.
- Model XML reassembly: minutes per item. Mesh authoring: hours per model (parse → Blender → convert → repack).
- Engine-level RT/pass work: months — requires profile detection, hooking, resource construction in the native window, and activation proof; treat as research.

## Open questions

- What toolchain produced the retail WD1 shader objects? Every available d3dcompiler rejects the leak's bare-entry style, so a driver-level `fxc.exe` step, an older `d3dcompiler_3x`, or build-time-only sources must have been used. Closed as un-reproduced, not solved.
- Is the WDL D3D12 shader recompile path workable? Only DX11 shader compilation is confirmed.
- Can RTGI be integrated into WD1's DX11 pipeline with verified in-game output? The architecture is documented; no build has been proven.
- Exact texture→shader→material resolution for `_UNKNOWN` material folders (WD1) is still manual and painful.
- Full WDL/WD2 `.wem` audio decoding inside Disrupt containers remains open.

## Seen in

- Watch Dogs 1 (`Disrupt_b64.dll`, dlc01-pc; DX11; ships full shader source; `Watch_Dogs Wii U Retail/` retained SYMTAB/STRTAB).
- Watch Dogs 2 (`bin/Disrupt_64.dll` retail 349 MB, `bin_plus/Disrupt_64.dll` debug 427 MB; DX11; same deferred pipeline, more material flags).
- Watch Dogs: Legion (`DuniaDemo_clang_64_dx12.dll` 1.6.3, dx11 build; D3D12 with native RT).
- Dunia lineage: Far Cry 3+ share the format family, so Gibbed.Dunia / FCBastard-style tooling transfers.
