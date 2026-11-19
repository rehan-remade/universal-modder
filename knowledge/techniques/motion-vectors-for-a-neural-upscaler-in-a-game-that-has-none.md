---
kind: technique
title: "Motion vectors for a neural upscaler in a game that has none: a camera homography first, entities on demand"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: []
date: 2026-10-29
links:
  - https://github.com/NVIDIA/DLSS
  - https://renderdoc.org
  - https://github.com/umar-afzaal/LumeniteFX
tags: [motion-vectors, depth, dlss, ngx, upscaling, homography, unity, bepinex, validation]
---

# Motion vectors for a neural upscaler in a game that has none: a camera homography first, entities on demand

> A repeatable recipe for giving a game **its own motion-vector + depth source** so a neural upscaler can be
> added to a game with **no native upscaler**, without optical flow and without screenshots. Everything comes
> from RE'd engine state: camera and entity transforms read at render time.
>
> Run on one game so far: [Cult of the Lamb](../games/cult-of-the-lamb/custom-motion-vectors-and-an-ngx-dlss-host-for-cult-of-the-l.md)
> (Unity 2022.3 Mono, DX11), with camera motion only and DLSS DLAA through NGX. Its numbers are the worked example
> below. Entity motion (Stage C), the residue table (Stage D) and every other upscaler are a plan, not results.
> If the game already renders jittered frames with depth and motion vectors, use those instead:
> [DLSS from a game's own depth and motion vectors](dlss-sr-frame-generation-and-neural-rendering-from-engine-motion-vectors.md).

## Stage A — probe (never skip)

1. Camera census per scene: name, tag, ortho vs persp, fov/orthoSize, rotation (euler — look for
   surprising pitch), z distance to content plane, `depth`, render target vs backbuffer,
   `depthTextureMode`, `allowHDR/allowMSAA`, MSAA quality setting, graphics API.
2. Motion magnitudes: log per-frame camera deltas converted to pixels; measure px/s of typical play.
3. Resolution behaviour: do launch args (`-screen-*`, `-w`, `-d3d12`) apply? Does the game re-persist
   window position/monitor selection (registry keys — pin them)? Which display does it choose?
4. Capture a frame with RenderDoc for the pass/swapchain inventory (note: render-layer injection often
   breaks plugin loaders — probe both paths; do not assume).

Gate: you can state, with numbers, which camera renders the world and its px/world-unit scale.

## Stage B — camera motion-vector field (the dominant motion)

- The whole trick for 2D/2.5D games: the world lies on/near a world plane, so the per-frame MV field is
  a **plane homography**: `H = P_prev · inv(P_curr)` with `P` = clip→pixel map of `[VP rows x,y,w]`.
  For each pixel `p`: motion = `p − H·p` (pixels, current-minus-previous). Handles translation, zoom
  and rotation of the camera exactly for planar content. For general 3D, do per-pixel
  unproject(currentVP) → reproject(prevVP) instead; same idea, per-pixel cost.
- Write MV texture + analytic depth texture (view depth of the plane/hit point) every frame, on the
  game's own device (CommandBuffer blit / CPU fill), names fingerprinted (e.g. `COTL_MV_241x135`),
  odd dimensions as discovery marker.
- Formats: the DLSS Programming Guide takes RG32_FLOAT or RG16_FLOAT for MVs (3.3, 3.6.1). The first stage here
  used RG32F and the plugin as built writes RGHalf, both filled on the CPU. A plugin can load a compiled shader
  from an AssetBundle, but that needs a Unity project of the game's major version
  (`skills/mod-any-game/references/engines/unity.md`), which this project didn't set up. Document your tradeoff.
- Conventions to record: pixels vs normalized (÷resolution), y-up (Unity) vs y-down (D3D), and the
  current-minus-previous convention the host must translate: DLSS wants pixels at render resolution, y-down,
  pointing towards the previous frame (Programming Guide 3.6.1, 3.6.1.1, 3.6.3).
- CPU fill pitfalls that cost a stage: never invert matrices per texel (hoist), no per-texel Vector3
  allocations, no per-row CSV flush at 60 fps (buffer!), config systems that pin defaults on first run
  (BepInEx cfg edits need the file checked, not just the default changed).
- Scale divisor: texture = screen/N (N=16 healthy: ~1.2 ms CPU at 4K/Mono for 241×135). Planar fields
  interpolate exactly; projective-only fields accept small bilinear error. DLSS reads MVs at render resolution,
  so the host has to bring a smaller field up to that size.

## Stage C — entity/object motion via RE (build on demand; not built yet)

Gated on Stage D's ghosting A/B: if movers smear unacceptably, add per-object MVs:

1. Find the transform registries by decompiling (Mono: ILSpy; IL2CPP: Il2CppDumper + BepInEx-style
   hooks; UE: SDK/allocator reflection). Look for the singleton-manager + list-of-movers pattern
   (`MonoSingleton<T>`, brain/managers, `TransformTracker`).
2. Each frame: for every mover, `screenVel = project(curr) − project(prev)` (exact; camera matrices
   only). Raster the entity's screen-space bounding box into the MV texture (CPU fill of small boxes
   is cheap; no shaders needed). Optionally give the entity exact depth.
3. Coverage drives effort: track root transforms first; the movers list is data-driven from the
   decompile (brains, spawners, projectile/particle managers).

## Stage D — validation + what RE does NOT fix (and how to follow the residue)

RE fixes transform-readable motion. Anything else keeps ghosting/smearing. Follow the residue like
this — detect → verify → mitigate. This table is a plan for the next game; the Cult of the Lamb run didn't work
through it.

| Residue | How to detect | Verify it's the cause | Mitigations (in order) |
|---|---|---|---|
| Skeletal/limb articulation (Spine/Animator/AnimBP) | limbs ripple/trail while root path is sharp | freeze the root, limbs still animate → ghost persists on limbs | per-bone tracking of key movers; shorter MV exposure (higher native fps); accept |
| Vertex/particle/FX motion (foliage sway, water, cloth, smoke, confetti) | static MV region visibly moves | occlude/unspawn the FX or toggle quality presets that disable them | shader-level MV injection (ReShade add-on path), accept as ambient blur, or exclude layer |
| UI/HUD on a separate camera | HUD trails when world pans | HUD MVs=ε while world moves | HUD gets zero/own MV — usually correct already; only fix if misregistered |
| Scene-transition camera jumps | huge one-frame MVs, validation error spikes | rotation delta > 0.05°/frame or teleport detection | skip/flag those frames; upscaler disocclusion handles it |
| Sprite sub-pixel stepping (fixed-timestep logic vs render rate) | MV field squares/steps during slow pans | move at constant input across several frames; look for plateaus | sample transforms at render callback (late), not logic tick |
| Reflection/shadow cameras feeding the screen floor (e.g. `*RT_Camera`) | floor shows trailing copies | disable the RT camera in a test build or check RenderDoc which cameras contribute | leave invalid MVs there; usually invisible, verify visually |
| Zero-MV unknowns (anything you didn't track) | "smear trail" exactly on movers | anything you didn't track | extend coverage; the movers list is data-driven from the decompile; for un-fixable layers use the estimators below |

Also validate always:
- The inputs as the upscaler reads them: for DLSS, the development DLL's overlays ([section 2 of the DLSS note](dlss-sr-frame-generation-and-neural-rendering-from-engine-motion-vectors.md)).
  A near-identical output doesn't prove the MVs arrived right, and the Cult of the Lamb run hasn't done this yet.
- Independent prediction path (different code from the writer) → per-sample error CSV, gate ~1 px.
- Frame-rate invariance: same play speed at fps1 and fps2 → equal px/s. If not, timing bug.
- Perf A/B with and without the source (route-matched): plugin CPU cost < 2% of frame budget.
- Watch loader conflicts (injectors vs proxy-DLL loaders like Doorstop/BepInEx — documented COTL gotcha:
  RenderDoc launcher bypassed BepInEx; mid-run inject black-screens D3D11).

## Stage D+ — estimators for residue pixels (researched 2026-10-29, not tried)

For pixels RE can never cover (limbs, FX, foliage), two estimators exist. Neither was run in this project:

1. **LumeniteFX LumaFlow** (`github.com/umar-afzaal/LumeniteFX`, under its own AGNYA licence) — ReShade-FX per-pixel
   motion estimation ("where did this pixel originate last frame"). Its README still describes LumaFlow; the motion
   shaders in the repo today are `lumenite_Kernel.fx` and `lumenite_PocketMV.fx`. Covers anything rendered. Reported
   weak spots: ghosting in fast motion, softness on thin moving geometry, and the HUD blurred with the scene.
2. **NVIDIA Optical Flow** — hardware OFA (Turing and later, so every RTX card), through the API the display
   driver supplies. Flames, lights and emissives create false motion.

Public ReShade add-ons wire estimators like these into DLSS5 neural rendering for games without DLSS
(DLSS5-Feeder, DLSS5 ReShade AIO). The KB doesn't take that route: they need `nvngx_dlssnr.dll`, which NVIDIA
doesn't publish, and Feeder's installer downloads it, modified builds included, while AIO ships a bridge DLL to pass
the NR snippet's caller check. The [DLSS note](dlss-sr-frame-generation-and-neural-rendering-from-engine-motion-vectors.md)
has the route the KB does take (section 6).

Decision rule for a new game:
- Exact camera MV (this baseline) first — it is free and correct for the dominant motion.
- RE entities second, sized by the ghosting A/B (movers only; data-driven from the decompile).
- Residue estimator third — adopt per layer only if the A/B shows it beats exact-with-holes; OFA on RTX
  hardware when emissives are few; LumaFlow when ReShade is acceptable.

## Stage E — consuming the textures (host)

- The host reads the fingerprinted textures, puts the MVs in the units and direction its backend wants (Stage B),
  and feeds it. Only DLSS via NGX (NVIDIA) was built. FSR 2.2.1/3.1 DX11 (open source, any GPU) is the next one
  to try. OptiScaler alone is NOT applicable to no-native-upscaler games (needs an existing input to hook) — it
  is useful only as a config/debug shell around your own host.
- Sub-pixel jitter is where DLSS gets its extra samples (Programming Guide 3.7). A host that sends jitter 0 on an
  unjittered camera gives it none, so expect DLAA to come out close to its input until the game's camera is
  jittered too.
- For Frame Generation later: same textures are exactly what FSR3-FG needs (any GPU), but FG needs
  presentation pacing (Reflex-like) — separate project; do not couple.

## Worked example numbers (Cult of the Lamb, 4K, Unity Mono DX11)

- World camera: `Camera`, persp fov 60, pitched −45°, refDist 9.12, plane px scale 205 px/unit.
- Validation after fix: center error max 0.0004 px; corner ~0.01 px (0.99 px on one transition frame).
- CPU: 1.18 ms/frame (241×135); 197.9 fps with vs 207.7 without on ~200 fps uncapped route.
- First-timer mistakes actually hit and fixed: 34 ms/frame (per-texel inverse), 22 fps (per-row flush),
  stale config default (ScaleDivisor), RenderDoc×BepInEx bypass, monitor-selection registry key.

## Verification

Cult of the Lamb only, with the checks and limits in [that note](../games/cult-of-the-lamb/custom-motion-vectors-and-an-ngx-dlss-host-for-cult-of-the-l.md):
the MV field against an independent reprojection, the host evaluating DLAA in the real game, and same-instant A/B
dumps.

**Not verified:** Stages C, D and D+; any other game, engine or upscaler; true upscaling (the host only runs DLAA);
the MVs as DLSS reads them.
