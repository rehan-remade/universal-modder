# Motion vectors for neural upscalers (any game)

A repeatable recipe for giving a game **its own motion-vector + depth source** so a neural upscaler
(DLSS SR/DLAA, FSR 2/3/4, XeSS) can be added to games with **no native upscaler** — without optical
flow, without screenshots, and without the Feeder-ecosystem color heuristics. Everything comes from
RE'd engine state: camera and entity transforms read at render time.

Proven on: Cult of the Lamb (Unity 2022.3 Mono, DX11, no native upscaler) — see
`cotl-scaler-core/PLAN.md` + `stage1/RESULTS.md`; numbers used as the worked example below.

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

## Stage B — camera motion-vector field (the 95%)

- The whole trick for 2D/2.5D games: the world lies on/near a world plane, so the per-frame MV field is
  a **plane homography**: `H = P_prev · inv(P_curr)` with `P` = clip→pixel map of `[VP rows x,y,w]`.
  For each pixel `p`: motion = `p − H·p` (pixels, current-minus-previous). Handles translation, zoom
  and rotation of the camera exactly for planar content. For general 3D, do per-pixel
  unproject(currentVP) → reproject(prevVP) instead; same idea, per-pixel cost.
- Write MV texture + analytic depth texture (view depth of the plane/hit point) every frame, on the
  game's own device (CommandBuffer blit / CPU fill), names fingerprinted (e.g. `COTL_MV_241x135`),
  odd dimensions as discovery marker.
- Formats: RG16F is the upscaler-native dtype; RG32F is fine if the host normalizes (we used RG32F
  because BepInEx plugins cannot load compiled shaders at runtime → CPU fill; document your tradeoff).
- Conventions to record: pixels vs normalized (÷resolution), y-up (Unity) vs y-down (D3D), and the
  current-minus-previous convention the host must translate.
- CPU fill pitfalls that cost a stage: never invert matrices per texel (hoist), no per-texel Vector3
  allocations, no per-row CSV flush at 60 fps (buffer!), config systems that pin defaults on first run
  (BepInEx cfg edits need the file checked, not just the default changed).
- Scale divisor: texture = screen/N (N=16 healthy: ~1.2 ms CPU at 4K/Mono for 241×135). Planar fields
  interpolate exactly; projective-only fields accept small bilinear error.

## Stage C — entity/object motion via RE (the remaining 5%, build on demand)

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
this — detect → verify → mitigate:

| Residue | How to detect | Verify it's the cause | Mitigations (in order) |
|---|---|---|---|
| Skeletal/limb articulation (Spine/Animator/AnimBP) | limbs ripple/trail while root path is sharp | freeze the root, limbs still animate → ghost persists on limbs | per-bone tracking of key movers; shorter MV exposure (higher native fps); accept |
| Vertex/particle/FX motion (foliage sway, water, cloth, smoke, confetti) | static MV region visibly moves | occlude/unspawn the FX or toggle quality presets that disable them | shader-level MV injection (ReShade add-on path), accept as ambient blur, or exclude layer |
| UI/HUD on a separate camera | HUD trails when world pans | HUD MVs=ε while world moves | HUD gets zero/own MV — usually correct already; only fix if misregistered |
| Scene-transition camera jumps | huge one-frame MVs, validation error spikes | rotation delta > 0.05°/frame or telepor detection | skip/flag those frames; upscaler disocclusion handles it |
| Sprite sub-pixel stepping (fixed-timestep logic vs render rate) | MV field squares/steps during slow pans | move at constant input across several frames; look for plateaus | sample transforms at render callback (late), not logic tick |
| Reflection/shadow cameras feeding the screen floor (e.g. `*RT_Camera`) | floor shows trailing copies | disable the RT camera in a test build or check RenderDoc which cameras contribute | leave invalid MVs there; usually invisible, verify visually |
| Zero-MV unknowns (anything you didn't track) | "smear trail" exactly on movers | anything you didn't track | extend coverage; the movers list is data-driven from the decompile; for un-fixable layers use the Stage D+ estimators below |

Also validate always:
- Independent prediction path (different code from the writer) → per-sample error CSV, gate ~1 px.
- Frame-rate invariance: same play speed at fps1 and fps2 → equal px/s. If not, timing bug.
- Perf A/B with and without the source (route-matched): plugin CPU cost < 2% of frame budget.
- Watch loader conflicts (injectors vs proxy-DLL loaders like Doorstop/BepInEx — documented COTL gotcha:
  RenderDoc launcher bypassed BepInEx; mid-run inject black-screens D3D11).

## Stage D+ — ecosystem options for residue pixels (better-than-RE alternatives, researched 2026-10-29)

For pixels RE can never cover (limbs, FX, foliage), the modding ecosystem has two estimators and one
conduit. Put these in every future game's decision tree BEFORE building exotic RE coverage:

1. **LumeniteFX LumaFlow** (`github.com/umar-afzaal/LumeniteFX`) — ReShade-FX per-pixel motion
   estimation ("where did this pixel originate last frame"). Covers anything rendered; estimation
   quality: "ghosting in fast motion, softness on thin moving geometry"; HUD gets blurred with the
   scene. Selected in DLSS5-Feeder as `DLSS5_MV_PROVIDER = 3` ("LumeniteFX Kernel"). Community-proven
   in messy engines (City of Heroes).
2. **NVIDIA Optical Flow via ReShade add-on** (`kibblerz/DLSS5-Reshade-AIO` v2.2.0+) — hardware OFA
   (Turing+; every RTX has it), profile-free, "massively reduces temporal boiling... and ghosting".
   Caveat: flames/lights/emissives create false motion.
3. **DLSS5-Feeder** (`github.com/jlrouzies-fr/DLSS5-Feeder`, same-GPU DLSS5-NR for games without DLSS,
   D3D9/11/12/Vulkan) — supplies depth + chosen MVs to a synthetic DLAA contract; providers chosen via
   `DLSS5_MV_PROVIDER`. Two things to verify per game: when the game uses Smooth Motion and for Vulkan
   games / and whether a **custom/external MV provider slot** exists — if it does, plug the exact
   camera+entity texture from OUR host into their pipeline (hybrid: exact where RE covers, neural
   model + their stack for residue). If not: hybrid = our host renders with our textures and accepts
   residue; plan-B = Feeder+LumaFlow for everything (lose exactness, gain full coverage, HUD blur).

Decision rule for a new game:
- Exact camera MV (this baseline) first — it is free and correct for the dominant motion.
- RE entities second, sized by the ghosting A/B (movers only; data-driven from the decompile).
- Residue estimator (LumaFlow or OFA) third — adopt per layer only if the A/B shows it beats
  exact-with-holes; OFA when hardware + many emissives skimmed; LumaFlow when ReShade is acceptable.
- Full-estimator route (Feeder+LumaFlow) is plan-B: simplest setup, worst ceiling (estimated motion,
  HUD blur), but the community default for no-DLSS games.

Verify the Feeder provider slot question on each new game (link: DLSS5-Feeder README "Choosing a
provider" section) before writing any merger code.

## Stage E — consuming the textures (host)

- Backend-agnostic host reads the fingerprinted textures, normalizes MVs (÷ res, flip y), feeds the
  backend: DLSS via NGX (NVIDIA), FSR 2.2.1/3.1 DX11 ports (any GPU), FSR4-INT8 (RDNA2/3 community
  builds) / official when available. OptiScaler alone is NOT applicable to no-native-upscaler games
  (needs an existing input to hook) — it is useful only as a config/debug shell around your own host.
- For Frame Generation later: same textures are exactly what FSR3-FG needs (any GPU), but FG needs
  presentation pacing (Reflex-like) — separate project; do not couple.

## Worked example numbers (Cult of the Lamb, 4K, Unity Mono DX11)

- World camera: `Camera`, persp fov 60, pitched −45°, refDist 9.12, plane px scale 205 px/unit.
- Validation after fix: center error max 0.0004 px; corner ~0.01 px (0.99 px on one transition frame).
- CPU: 1.18 ms/frame (241×135); 197.9 fps with vs 207.7 without on ~200 fps uncapped route.
- First-timer mistakes actually hit and fixed: 34 ms/frame (per-texel inverse), 22 fps (per-row flush),
  stale config default (ScaleDivisor), RenderDoc×BepInEx bypass, monitor-selection registry key.
