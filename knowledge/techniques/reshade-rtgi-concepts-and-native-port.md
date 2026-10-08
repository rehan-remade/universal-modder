---
kind: technique
title: "ReShade RTGI concepts and porting to a native engine pipeline"
tags: [rtgi, global-illumination, reshade, screen-space, denoising, temporal-accumulation, brdf, blue-noise, dx11]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - https://martysmods.com
  - https://reshade.me
  - https://github.com/GameTechDev/XeGTAO
  - https://github.com/dtrail/ZN_FX-Updated
  - https://github.com/BlueSkyDefender/AstrayFX
  - https://github.com/kiselgra/rtgi
  - https://github.com/NVIDIAGameWorks/RTXGI-DDGI
  - https://github.com/NVIDIA-RTX/RTXGI
---

# ReShade RTGI concepts and porting to a native engine pipeline

> Ray-traced global illumination can be delivered as a ReShade post-process shader in any DX9/DX10/DX11/DX12 game, or moved into an engine's own render pipeline. This note covers the general concepts any such implementation shares — depth/normal estimation, stochastic screen-space tracing, BRDF importance sampling, denoising and temporal accumulation, blue-noise dithering, and ray-based AO — then outlines the open-source references that document them concretely and what a native port requires. The concepts here were learned from open, readable implementations — in particular **DAMP RT** (the active fork of ZN_FX, `dtrail/ZN_FX-Updated`) — and not from iMMERSE Pro's shader files; this note documents general RTGI theory only, not any proprietary implementation.

## When to use it

- You want indirect/global illumination (color bleeding, soft indirect shadows, ambient variation with geometry) in a game that only exposes depth and color to post-processing.
- You have a deferred-rendering engine with a G-buffer (depth, normals, albedo, specular, and ideally motion vectors) and want to add an indirect lighting pass.
- You are deciding between a screen-space (DX11, no RT hardware) and a hardware-RT (DX12/DXR) path.
- You want to understand the shared skeleton behind every RTGI shader before reading any single implementation.

**Credit and prior art.** The practical, game-agnostic form of this technique was popularized by **iMMERSE Pro** (Pascal Gilcher / Marty's Mods) — see https://martysmods.com. It is the reference for how RTGI can run as a universal ReShade shader rather than a per-engine integration. This note is educational documentation, not a competitor or replacement; buy the original if you want the working product. Concrete, readable detail here is drawn from the open-source projects listed below (DAMP RT / ZN_FX-Updated in particular), not from iMMERSE Pro's source.

## How

### The pipeline every implementation shares

```
G-Buffer  ->  Ray generation  ->  Intersection  ->  Shading at hit  ->  Denoise  ->  Composite
(depth,       (stochastic        (screen-space     (direct +          (spatial +   (add or
 normals,      hemisphere/        depth search      indirect light,    temporal)    replace light
 albedo,       BRDF sampling)     or HW BVH)        BRDF eval)                      probes)
 motion)
```

1. **G-buffer generation.** Per-pixel surface data. In a deferred engine this already exists and RTGI just reads it: depth, world-space normals, albedo, roughness/glossiness, and motion vectors. Depth must be linearized before use; normals may need reconstruction from depth (or decode from the G-buffer's packed form, e.g. octahedral encoding).
2. **Ray generation.** Reconstruct world position from depth, pick a direction, and randomize across pixels. Direction distribution is the sampling strategy (below).
3. **Intersection.** Either screen-space (march the depth buffer) or hardware RT (traverse a BVH). Screen-space is the only option without DXR/Vulkan RT.
4. **Shading at the hit.** Evaluate lighting where the ray lands — direct light plus a bounce, modulated by the hit surface's BRDF and albedo (this is what produces color bleeding). Real-time budgets usually allow one or two bounces; each bounce roughly doubles cost.
5. **Denoising.** Raw Monte Carlo output at 1 sample per pixel is salt-and-pepper noise. Combine spatial filtering (edge-aware) with temporal accumulation (reuse across frames).
6. **Composite.** Blend the indirect term into the image — additively, or by replacing the precomputed light-probe contribution.

### Depth and normal estimation

- Linearize hardware depth to view/world distance before comparing or reconstructing position.
- Reconstruct normals from depth when no normal buffer is available (sample neighboring depths and cross the position differences). The **DAMP RT** lineage cites improved normal-reconstruction work; treat this as a standard technique.
- In a deferred engine, prefer the engine's own world-space normals; note that some engines store *glossiness* (inverse roughness), which must be inverted before GGX sampling.

### Stochastic screen-space tracing

- **Depth-mip traversal** is the key trick for GI without RT hardware: prefilter the depth buffer into a mip chain (min/max per 2×2, recursively), then march the projected ray and sample progressively coarser mips with distance. Coarser mips approximate a widening cone, which approximates what hardware RT would find while using only the depth buffer. This is the approach documented by **DAMP RT** (`dtrail/ZN_FX-Updated`, GPL v3, fork of the archived Zenteon/ZN_FX).
- Screen-space tracing only finds *visible* surfaces: off-screen geometry, occluded geometry, and thin geometry between depth samples are missed, and quality degrades at screen edges and grazing angles.

### Sampling strategies and BRDF importance sampling

- **Cosine-weighted** hemisphere sampling for diffuse surfaces — bias rays toward the normal.
- **GGX lobe** sampling for glossy/specular surfaces — bias rays around the reflection vector, widening with roughness.
- **Metalness** blends diffuse vs specular response; metallic specular is tinted by albedo, dielectric specular is white.
- **Multiple importance sampling (MIS)**, **next event estimation (NEE)**, and **Russian roulette** are standard variance-reduction tools documented in the academic references (kiselgra/rtgi implements NEE + MIS).
- Importance sampling concentrates samples where they contribute most, which directly reduces the denoiser's workload.

### Denoising and temporal accumulation

- **Spatial:** bilateral / edge-aware filters guided by depth, normals, and albedo, so smoothing happens within a surface and stops at edges. Variance estimation lets filter strength adapt spatially.
- **Temporal:** the most important real-time technique. Trace few rays per frame and accumulate across frames:

```
current    = trace_rays(this_frame)
previous   = read_accumulation_buffer()
reprojected= sample(previous, screen_pos - motion_vector)
final      = lerp(reprojected, current, alpha)   // alpha ~0.05-0.5
write_accumulation_buffer(final)
```

- Use **motion vectors** (engine-provided or computed from depth + previous camera matrices) to reproject. Detect **disocclusion** (newly revealed pixels have no valid history) and drop the history weight there. Use **neighborhood/variance clamping** of the reprojected value to suppress **ghosting**. **Double-buffer** the accumulation target (read one, write the other, swap).

### Blue-noise dithering

- White noise is independent per pixel and reads as annoying high-frequency grain; **blue noise** decorrelates nearby pixels so the residual looks like fine, even grain and is perceptually preferable.
- For temporal accumulation, use **temporally stable** blue-noise sequences so each pixel's noise follows a blue-noise distribution over time, not just within a frame. Noise is used to randomize ray directions, to choose which pixels to trace in half-resolution mode, and to jitter sub-pixel samples.

### Ray-based AO as a byproduct

- When tracing GI rays, the ratio of blocked to unblocked rays already approximates ambient occlusion. Many implementations emit an AO term from the same pass at little extra cost, and it can be used to enhance a pre-baked AO channel.

### Open-source references for concrete detail

| Project | License | What to read it for |
|---------|---------|---------------------|
| XeGTAO (Intel) | MIT | Template for screen-space effects as compute passes (Prefilter → Main → Denoise), header-only HLSL, DX11/DX12 |
| DAMP RT / ZN_FX-Updated | GPL v3 | Full screen-space RTGI pipeline: depth-mip cone tracing, temporal accumulation with variance clamping, motion-vector support, bounce lighting |
| RadiantGI (AstrayFX) | CC BY-ND 4.0 | Alternative approach — disk-to-disk radiance transfer instead of path tracing; **no derivatives allowed** |
| kiselgra/rtgi (Kiel University) | GPL-3.0 | Textbook wavefront path tracing; uniform/cosine/light/BRDF sampling, NEE + MIS, OpenImageDenoise integration |
| RTXGI v1.x DDGI (NVIDIA) | Custom | Probe-based irradiance caching, spherical harmonics, engine-integration docs |
| RTXGI v2.0 NRC/SHaRC (NVIDIA) | Custom | Radiance caching: neural (NRC, needs Tensor Cores) and spatially hashed (SHaRC, vendor-agnostic) |
| Quake II RTGI (vkPT) | GPL-2.0 | Complete real-time Vulkan path tracer (hardware RT) |

### Moving a ReShade GI shader into a native pipeline

ReShade auto-manages uniforms, textures, samplers, and pass scheduling. In native code each becomes explicit plumbing (the `reshade-to-native` mapping):

| ReShade FX | Native (D3D11) |
|-----------|----------------|
| `uniform float X <...> = 0.5;` | `cbuffer` + `Map`/`Unmap` |
| `texture Tex { Width=BUFFER_WIDTH; }` | `ID3D11Texture2D` + `CreateTexture2D` |
| `sampler S { Texture=Tex; }` | `ID3D11SamplerState` |
| `technique T { pass P {...} }` | `CSSetShader` + `Dispatch` (or `Draw(3,0)`) |
| `BUFFER_WIDTH/HEIGHT`, `BUFFER_PIXEL_SIZE` | fields in a per-frame constant buffer |
| `ReShade::Depth`, `ReShade::BackBuffer` | engine depth SRV / backbuffer RTV |

Standard screen-space compute shape: 8×8 thread groups, one dispatch per pass, a UAV barrier (unbind the UAV before rebinding it as an SRV) between passes, ping-pong or double-buffered targets for temporal stages. The core HLSL math (`lerp`, `saturate`, `tex2Dlod`, matrices) maps 1:1; only the framework layer is manual.

**Engine integration points (deferred renderer):**

```
1. Geometry pass      -> G-buffer
2. [RTGI pass]        -> indirect lighting buffer (RGB16F, linear HDR)
3. Deferred lighting  -> combine direct + indirect
4. Forward pass       -> transparents read the same indirect buffer, or fall back to probes
5. Post-processing    -> tonemap + AA
```

- **Option A (recommended):** separate compute pass between G-buffer and deferred lighting; clean separation, easy to toggle.
- **Option B:** embed the indirect term directly in the deferred lighting shader; fewer reads but modifies an existing shader.
- **Option C:** post-deferred composite; least invasive but has less per-surface data and integrates less accurately.

**Half-resolution tracing** (trace at half res, bilateral-upscale guided by depth) is the single most effective optimization — roughly 75% fewer rays.

### Worked example: Disrupt (Watch Dogs) family

- **Disrupt** is a Dunia 2 (Far Cry 3) fork: deferred lighting with forward transparency. Key shaders at `Disrupt/Watch_Dogs/shaders_unpack/engine/shaders/`: `deferredlighting.fx` (integration point), `lighting.inc.fx`, `gbuffer.inc.fx` (octahedral-encoded normals), `lightprobes*.fx` (the indirect lighting RTGI would replace/augment), `forwardlighting.inc.fx`, `depth.inc.fx`, `ambient.inc.fx`.
- **G-buffer already carries what RTGI needs:** albedo, world-space normals, specular/glossiness, material flags, velocity (SV_Target4), and scene depth.
- **WD1/WD2:** DX11 only, no hardware RT. Path is screen-space RTGI as a 5-pass compute chain (PrepareGBuffer → DepthMipTrace → TemporalAccumulate → SpatialDenoise → Composite). Estimated 2–3 ms at 1080p. Note ReShade cannot reach depth mipmaps or the G-buffer, so a native/engine-level patch is required to get the inputs.
- **WDL:** native D3D12 RT path (BLAS/TLAS, DXR dispatch already present) — the most tractable target. Viable approaches: DDGI-style probe caching, screen-space + HW-RT hybrid, or per-pixel RT; SHaRC (RTXGI v2.0) is a vendor-agnostic cache option.
- **Engine-level patching is proven feasible** in WD1 via ASI/DLL-proxy injection: the Shadow Engine project (`temdah/Shadow-Engine`) extends dynamic shadow-map capacity and publishes an OKF bundle of generalizable safety contracts. Distilled rules that apply to a GI pass: allocate GI render targets inside the native **resource-construction window** (not lazily); register GI passes during the native **pass-registration phase before table finalization** (late registration can silently never execute); route expanded indices through **patch-owned storage**; use **two-phase transactions** (Phase A allocate early, Phase B install frame-hook routing) with rollback; require **activation proof** (dispatch counters > 0 and the output actually read by lighting — allocation alone proves nothing); and **fail closed** on unknown builds. Cross-title observations (e.g. WDL's RT path) are architectural evidence only — offsets and layouts do not transfer to WD1.

## Gotchas

- **Screen-space limits.** No off-screen or occluded contributions; thin geometry can be missed between depth samples; edge/grazing-angle artifacts. This is the fundamental quality ceiling of the DX11 path.
- **Depth mipmaps are not free.** DX11 does not auto-mip a depth buffer; generate an edge-aware mip chain in a compute pass (8–12 levels) or tracing quality suffers.
- **Ghosting vs. lag.** Heavy temporal accumulation (low alpha) is smooth but smears on motion; inaccurate motion vectors (silhouettes, transparency, specular) cause ghosting. Neighborhood/variance clamping and disocclusion detection are the mitigations.
- **Motion-vector coverage.** Transparent objects may lack motion vectors; verify quality and coverage before relying on them.
- **Glossiness vs. roughness.** Some G-buffers store glossiness (inverse roughness) — invert before GGX sampling.
- **Format/space.** Keep the GI term in linear HDR (RGB16F or R11G11B10F); tonemap with the rest of the scene. RGBA8 bands in dark areas.
- **Budget.** At 60 fps the whole frame is 16.6 ms; budget RTGI 2–5 ms. Denoiser cost is real — cheap bilateral filters are not free, and AI denoisers cost more.
- **Licenses matter.** RadiantGI is CC BY-ND 4.0 (no derivatives); DAMP RT is GPL v3 (copyleft). Check before reusing any code.
- **Don't infer engine layouts from a successor title.** WD2/WDL observations tell you *what to measure* in WD1, not how WD1 works; every WD1 offset and lifetime path must be recovered from WD1.

## Seen in

- **iMMERSE Pro** (Pascal Gilcher / Marty's Mods) — universal ReShade RTGI for DX9/DX10/DX11/DX12 games; credited as the popularizer of the technique. https://martysmods.com
- **DAMP RT** (Zenteon; active fork `dtrail/ZN_FX-Updated`) — GPL v3 ReShade RTGI using depth-mip cone tracing and temporal accumulation.
- **RadiantGI** (BlueSkyDefender / AstrayFX) — CC BY-ND 4.0 ReShade GI via disk-to-disk radiance transfer.
- **XeGTAO** (Intel, MIT) — screen-space AO compute architecture, widely used as the structural template for native screen-space passes.
- **Quake II RTGI (vkPT)** (GPL-2.0) — full hardware-RT Vulkan path tracer.
- **RTXGI DDGI / SHaRC** (NVIDIA) — probe- and hash-based radiance caching used by engines with DXR.
- **Disrupt (Watch Dogs 1/2/Legion)** — deferred engine analyzed as a target for a native RTGI port; WD1/WD2 screen-space, WDL hardware RT.
