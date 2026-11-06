---
kind: game
title: Custom motion vectors and an NGX DLSS host for Cult of the Lamb (Unity DX11, no native upscaler)
game: Cult of the Lamb
games_also: []
game_version: 'Steam build 25223484, v1.5.26.1058'
platform: windows
engine: unity-mono
route: native-hook
tools: ["BepInEx 5.4.21", "HarmonyX", "ILSpy 8.2", "RenderDoc 1.46", "NVIDIA DLSS SDK (nvngx 310.x)", "BepInEx.ConfigurationManager v19.1", "MSVC 2022"]
anti_cheat: 'none (single player and local co-op; no online mode)'
status: working
agents:
- OpenCode (DeepSeek V4.1 Flash)
humans: []
date: '2026-10-29'
links: ["https://github.com/NVIDIA/DLSS", "https://renderdoc.org", "https://github.com/BepInEx/BepInEx.ConfigurationManager", "https://docs.bepinex.dev", "https://thunderstore.io/c/cult-of-the-lamb/p/BepInEx/BepInExPack_CultOfTheLamb/"]
tags: ["cult-of-the-lamb", "unity", "motion-vectors", "dlss", "ngx", "native-hook", "upscaling"]
---
# Custom motion vectors and an NGX DLSS host for Cult of the Lamb (Unity DX11, no native upscaler)

> Built a BepInEx plugin that derives motion vectors and depth from the game's own camera each frame and a
> native D3D11 host that runs NVIDIA NGX DLSS (DLAA) with them, inside a game that has no upscaler at all.
> Runs in the real game: the game holds 130-160 fps at 4K with NGX evaluating every frame, the host call costs
> 0.07-0.11 ms of CPU per frame, and same-instant A/B pairs show ~1/255 difference and no colour regrade. So it
> runs and does no harm, but DLSS isn't adding visible detail yet, and that doesn't prove the MVs arrive right
> (Verification). Moving-entity ghosting wasn't seen in the sampled frames, but none of them caught an entity moving
> relative to the world.

## Setup
Steam, Windows, x64. Game v1.5.26.1058 (build 25223484), Unity 2022.3.62f2 Mono, **Built-In Render Pipeline**,
**Direct3D 11**. No native upscaler (no FSR2/DLSS/XeSS DLLs or plugins) and no anti-cheat (local co-op
only). BepInEx 5.4.21 (Thunderstore pack) + HarmonyX; RenderDoc 1.46 portable for pass inventories;
NVIDIA DLSS SDK from the public `NVIDIA/DLSS` repo (`include/` headers + `lib/Windows_x86_64/rel/nvngx_dlss.dll`);
BepInEx.ConfigurationManager v19.1 for the F1 settings menu; MSVC 2022 for the host DLL.

## Route and why
Native hook (host) + loader API (plugins), because the game has **no upscaler input to replace**: OptiScaler
and similar tools need the game to already call DLSS/FSR/XeSS. The whole problem is to produce the inputs
(colour, depth, motion vectors) the upscaler expects. Route chosen: compute MVs from the camera/entity
transforms (exact, no optical flow), write them into fingerprinted textures, and run NGX ourselves.
Rejected: OptiScaler (nothing to hook), RTX Remix (DX8/9 fixed-function path-tracing platform, wrong class
of tool for a DX11 2D game), LumaFlow/optical-flow estimators (plan-B if exact MVs prove insufficient). The
reusable recipe is in `techniques/motion-vectors-for-a-neural-upscaler-in-a-game-that-has-none.md`.

## How the game works (what we had to learn)
- The world camera is named `Camera`, **perspective, fov 60, pitched -45 deg (euler X 315)**, ~9.1 units above
  the z=0 plane, `depth = -1`, `depthTextureMode = Depth`, `QualitySettings.antiAliasing = 0`. A second
  `CameraTrackedFloorRT_Camera` (ortho size 15, 1024x1024) renders a floor texture - ignore it. Menus reuse
  `Camera`; `Main Camera` (ortho, size 5) is the loading/BufferScene camera.
- World content sits on/near the **z = 0 plane**, so the camera-only motion field is a **plane homography**:
  `H = P_prev * inv(P_curr)`, where `P` maps world-plane (x,y,1) to pixel-homogeneous space via the VP
  matrix's x,y,w rows (compose with the clip->pixel scale). For a current pixel `p`, MV = `p - H*p`, in
  pixels, current-minus-previous. At 4K the plane scale is ~205 px/unit; walking gives ~5 px/frame at
  ~200 fps (1000 px/s) and idle sway ~0.5 px.
- Backbuffer: `R8G8B8A8_UNORM`, 3840x2160, depth `D32S8_TYPELESS` (RenderDoc inventory, 202 textures).
- The game persists window monitor choice in the registry (`UnitySelectMonitor`), not just window position.

## Build steps
`cotl-scaler-core/` is the author's private working folder. It isn't in this repo or published anywhere yet, so
read these steps as what the project does. If it's ever published, nothing from the game goes with it, and
`nvngx_dlss.dll` comes from NVIDIA's public SDK.

1. `dotnet build cotl-scaler-core/cotl-motion-vectors` and `.../cotl-camera-probe` (net472, references to the
   game's `BepInEx/core` and `Managed` assemblies). Copy the DLLs to `BepInEx/plugins/`.
2. Build the host: `powershell -File cotl-scaler-core/cotl-scaler-host/build.ps1` (calls vcvars64 + cl
   `/LD /O2 /EHsc host.cpp`, links d3d11/dxgi/user32). Deploy layout:
   `BepInEx/plugins/UniversalModder.CotlScalerHost.dll` + `BepInEx/plugins/cotl-scaler/` containing
   `cotl-scaler-host.dll` and `nvngx_dlss.dll`.
3. The host loads the driver's `nvngx.dll` from the DisplayDriver DriverStore, calls
   `NVSDK_NGX_D3D11_Init(appId, folderWithDlssDll, device, 0x15)` (`0x15` is `NVSDK_NGX_Version_API`),
   `GetCapabilityParameters`, `CreateFeature(DLAA)`, and per frame `EvaluateFeature` with colour (copy of the
   backbuffer), our MV (`R16G16_FLOAT`) and depth (`R32_FLOAT`) textures, `MV.Scale = 1/res` (as recorded; see
   Not verified), jitter 0, reset on start/toggle.
4. Present is hooked by creating a dummy swapchain once, then patching the shared `IDXGISwapChain::Present`
   vtable slot. No DXGI proxy needed.
5. Settings: BepInEx.ConfigurationManager (F1) exposes `[Upscaler] Mode = Off|DLAA` and `[Diagnostics]`
   (dump folder/frames). F9 toggles the mode, F10 queues a same-instant A/B dump.
6. The MV plugin writes `COTL_MV_WxH` (`RGHalf`, pixels, y-flipped for NGX because DLSS MVs are y-down) and
   `COTL_DEPTH_WxH` (`RFloat`, normalised to [0,1] per frame) at screen/16 (odd dimensions as a fingerprint).

## Verification
- Same-instant dumps: the host writes `color_*.bmp` (pre-DLSS backbuffer) and `out_*.bmp` (DLSS result) for
  the same frame. Diffing them (PIL/numpy) gives channel shift -0.1..-0.2/255 and mean |diff| ~1/255 even at
  109 px/frame camera motion - DLSS is near-identity. That isn't a measure of what DLSS could do here: the
  camera isn't jittered and the host sends jitter 0, and sub-pixel jitter is where DLSS gets its extra samples
  (DLSS Programming Guide 3.7). Crop inspection of walking lamb + followers: no trails, no colour regrade.
- MV field validation: an independent reprojection path (unproject current pixel to z=0, project with the
  previous VP) matched the stored homography within 0.0004 px centre / ~0.01 px corner.
- Perf: host call 0.07-0.11 ms/frame (the CPU side of the call; DLAA's GPU time wasn't measured separately); game
  130-160 fps at 4K with DLSS on (60 Hz panel).
- NOT verified: an entity that moves relative to the world (wandering follower/animal caught mid-walk) - all
  sampled entities were static in-world, where the plane MV is correct; combat projectiles untouched.
- NOT verified: the MVs as DLSS reads them. They haven't been checked on the development DLL's overlays (Programming
  Guide 8.2, and section 2 of `techniques/dlss-sr-frame-generation-and-neural-rendering-from-engine-motion-vectors.md`).
  Three details recorded here don't match the guide as written: `MV.Scale` should be 1.0 for MVs already in pixels
  (3.6.3), so 1/res would leave DLSS almost no motion; DLSS MVs point towards the previous frame (3.6.1.1, 3.6.3),
  and the field here is current-minus-previous with only y flipped; and DLSS reads MVs at render resolution (3.6.1),
  and the texture here is screen/16. A near-identical output can't tell these apart.

## Gotchas
1. **NGX `CreateFeature` returns 0xBAD00005 (FAIL_InvalidParameter).** Cause: creation params were incomplete.
   Fix: set `Width/Height` (render), **`OutWidth/OutHeight` (output)**, `PerfQualityValue` (DLAA),
   `DLSS.Feature.Create.Flags` and `DLSS.Enable.Output.Subrects`.
2. **`GetCapabilityParameters` is not exported by `nvngx_dlss.dll`.** Cause: the parameter/feature entry
   points live in the driver-installed NGX core. Fix: locate it under
   `%WINDIR%\System32\DriverStore\FileRepository\nv*inf_amd64_*\` and `LoadLibrary` it; pass the folder that
   contains `nvngx_dlss.dll` to `NVSDK_NGX_D3D11_Init`. This host loads `nvngx.dll`; the SDK's own loader
   (`nvsdk_ngx_loader.h`) tries `_nvngx.dll` first, since drivers 471.11 and later use that name. Passing the DLL's
   folder is what worked here, but `nvsdk_ngx.h` documents that argument as the folder for logs and temporary files
   (write access required), and feature DLL search paths as `InFeatureInfo`'s `PathListInfo`.
3. **DLSS refuses the MV texture or behaves badly.** Cause: NGX takes `RG16_FLOAT` or `RG32_FLOAT` MVs (this host
   uses `R16G16_FLOAT`) and one-channel depth such as `R32_FLOAT` (Programming Guide 3.3), and MVs are y-down while
   Unity screen space is y-up. Fix: flip y only for the upload, normalise depth to [0,1] per frame.
4. **RenderDoc launch bypasses BepInEx.** Symptom: capture works but plugins never load (no log written).
   Cause: with `renderdoccmd capture` the Doorstop proxy loads but the BepInEx preloader never runs (working
   directory exonerated); mid-run `inject` black-screens D3D11. Fix: launch via Steam/direct for plugin work;
   for capture inventories use `qrenderdoc --python inventory.py <rdc>`.
5. **`qrenderdoc --python` runs before the capture is opened.** Fix: in the script call
   `LoadCapture(path, renderdoc.ReplayOptions(), path, False, True)`, poll `IsCaptureLoaded()`, and use the
   `qrenderdoc.CaptureContext` API directly (`GetTextures()`, `CurD3D11PipelineState()`,
   `CurRootActions()` are methods; `TextureDescription` uses `arraysize`/`msSamp`).
6. **The game launches on the wrong monitor.** Cause: `HKCU\Software\Massive Monster\Cult Of The Lamb`
   `UnitySelectMonitor` pointed at the second display. Fix: set it to 0 (back the key up first) and/or keep
   re-asserting the window position for the first ~20 s.
7. **Synthetic input does nothing.** Cause: COTL uses Rewired raw input; menus accept with **E**, not
   Enter/Space, and synthetic mouse clicks are ignored. Fix: `um win drive` with `scanmode on`, use `hold` for
   movement, and send F-keys inside the same session as the held key when timing matters.
8. **BepInEx config changes do not appear.** Cause: BepInEx pins entries in the per-plugin cfg on first run.
   Fix: delete/regenerate the cfg (or edit the cfg) after changing entries; this also applies to renamed
   sections (`[General]` -> `[Upscaler]`).
9. **Dumps froze the game for 15-17 s.** Cause: PNG encoding two 4K frames + deleting old dump sets, all
   synchronously inside Present (2.7-2.9 s/frame). Fix: queue to a worker thread, reuse double-buffered
   staging textures, write BMP for the colour pairs, rotate dumps off-thread.
10. **A/B stats lied.** Cause: cross-time screenshots included scene animation, and the CSV `unixTime` was a
    float32 (~128 s quantisation). Fix: same-instant dump pairs, event-marker CSV, segment by `gameTime`.
11. **The game's own hitches look like ours.** 60-70 ms single-frame spikes and 14-15 fps idle stretches exist
    with all plugins disabled (Stage 1 baseline); never attribute them to the upscaler without comparing
    against a plugin-off baseline.
12. **MV CPU fill cost 34 ms/frame.** Cause: per-texel matrix inversion in the fill loop. Fix: hoist the
    inverse, flatten the loop, texture at screen/16 (~1.2 ms at 4K).

## Assets
None generated; all textures are data produced at runtime.

## Open questions
- Moving-entity MVs (per-object velocity from the RTS/character transforms) if the un-captured mover case
  proves to ghost in practice.
- True DLSS Quality/Balanced/Performance presets need Unity dynamic-resolution integration: in BIRP the game
  renders straight into the backbuffer before the Present hook, so a lower internal render res is not
  reachable from the host as built.
- Steam Deck leg: DXVK/Vulkan host port for FSR 2.2/3.1.
