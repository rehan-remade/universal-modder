---
kind: game
title: DLSS5 neural rendering + DLSS frame generation in a custom REFramework build, with Tobii eye tracking
game: Resident Evil 2 (2019)
games_also: []
game_version: Steam 883710, build 11636119 (DX12 / ray-tracing update)
platform: windows
engine: re-engine
route: native-hook
tools:
- REFramework (pd-upscaler branch, a24c345, custom build)
- PDPerfPlugin (Nexus RE2 mod 2611)
- NVIDIA NGX (DLSS SR 310.8.0, DLSS NR 310.8.0)
- NVIDIA Streamline 2.14.1 (DLSS-G 310.9.1, Reflex, PCL)
- Tobii Stream Engine runtime 4.1 to 4.25 (tested range)
- ReShade 6.8.0 + RenoDX (HDR fix)
- PresentMon
anti_cheat: none found by um scan; single-player only
status: working
agents:
- Claude Code (Opus 5.5)
humans:
- GautamtmD
date: '2026-10-09'
links:
- https://github.com/praydog/REFramework/tree/pd-upscaler
- https://github.com/NVIDIA-RTX/Streamline/releases/tag/v2.14.1
- https://www.nexusmods.com/residentevil22019/mods/2611
- https://www.nexusmods.com/residentevil22019/mods/1644
tags:
- dlss
- dlss-nr
- frame-generation
- streamline
- reflex
- reshade
- hdr
- eye-tracking
- tobii
- render-pipeline
---
# DLSS5 neural rendering + DLSS frame generation in a custom REFramework build, with Tobii eye tracking

> RE2 (2019, DX12) got DLSS SR, DLSS5 neural rendering (NR) and DLSS frame generation (2x/3x/4x) from one
> custom REFramework `dinput8.dll`. NR runs on the DLSS output with the engine's own motion vectors and depth,
> and frame generation interpolates whatever is on screen (DLSS or NR). A separate REFramework plugin adds Tobii
> eye/head-tracked camera lean. It runs in the real game: the human verified image quality and motion at 2x
> and 4x with NR on and off, and PresentMon measured 259 displayed fps at 4x from ~65 game fps.

## Setup
Verified on:
- AMD Ryzen 7 5800X3D, 128 GB RAM, NVIDIA GeForce RTX 5070 Ti 16 GB (game GPU, device 0x2C05; an RTX 5060
  Ti is also installed), NVIDIA driver 617.42, Windows 11 Home 10.0.26200.9457.
- Hardware-accelerated GPU scheduling on (DLSS-G requirement), LG ULTRAGEAR+ monitor, Windows HDR on.
- RE2 Steam build 11636119.

Components:
- **REFramework**, `pd-upscaler` branch at a24c345, rebuilt with our changes. Its TemporalUpscaler drives DLSS
  SR through PureDark's PDPerfPlugin.
- **PDPerfPlugin.dll** (Aug 2023) and `nvngx_dlss.dll` 310.8.0, from Nexus RE2 mod 2611.
- **NVIDIA's signed `nvngx_dlssnr.dll` 310.8.0** beside `re2.exe`. NVIDIA does not ship it in a public SDK
  (Streamline 2.14.1 and DLSS SDK 310.9.1 have no NR); NBA 2K27, DLSS 5's launch title (Sept 2026), ships this
  310.8.0 build, so a player can copy it from their own install. Optional: NR switches itself off without it.
- **Streamline 2.14.1** from NVIDIA's official GitHub release: `sl.interposer`, `sl.common`, `sl.dlss_g`,
  `sl.reflex` and `sl.pcl`, plus `nvngx_dlssg.dll` 310.9.1.
- **Tobii Eye Tracker 5** with Tobii Experience. The plugin uses the `tobii_stream_engine.dll` that Tobii's
  software installs (gotcha 16). Tested from the SDK's 4.1 runtime up to the 4.25 one Tobii Experience installs.
- **For correct HDR:** ReShade 6.8.0.2155 with add-on support, plus RenoDX
  `renodx-re7-2r-3r-village.addon64` 0.2026.706.2142 (Nexus mod 1644).

Toolchain:
- VS 2026 Community (MSVC 14.51), CMake 4.2, Ninja.
- REFramework submodules, plus the ReShade v6.8.0 `include/`, NGX headers (from the Streamline SDK) and
  Streamline headers, vendored into `dependencies/`.

## Route and why
Native-hook, inside REFramework itself (a superset `dinput8.dll`), not a plugin and not a ReShade add-on.
- **Plugin route (ruled out):** REFramework's plugin API gives a plugin the device, swap chain and queue, but
  no engine render targets. A TDB sweep of about 79k types found no D3D12 handles for depth, motion vectors or
  UI. TemporalUpscaler already captures exactly those from the render layers (`Scene` layer depth and motion
  vectors, `PrepareOutput` colour), so NR and frame generation live next to it.
- **RenoDX DLSS5 add-on (rejected):**
  - Its Present stage feeds NR synthetic display-res motion/depth.
  - Its Upscale stage never fires, because it never sees PDPerfPlugin's SR evaluates.
  - Its direct-snippet path spoofs the caller identity of the signed NR DLL (an IAT patch on
    `GetModuleFileNameW`). We did not copy that. The driver's public NGX core works instead (gotcha 4).
- **OptiScaler (rejected):** crashed alongside REFramework (double DXGI interception).

## How the game works (what we had to learn)
- **Two threads per frame.**
  - The main thread simulates frame N: application entries `UpdateHID` … `UpdateBehavior` …
    `LateUpdateBehavior` … `LockScene`.
  - It then blocks in `WaitRendering` until the render thread presents N−1, and builds frame N:
    `BeginRendering` … `EndRendering`.
  - A separate render thread presents frame N while the main thread already simulates N+1.

  Measured with timestamps and thread ids on all REFramework application-entry callbacks: about 11.7 ms per
  frame at 85 fps. This is what Reflex/PCL frame tokens have to follow.
- **Camera matrices** in `SceneInfo` are glm column-major (`clip = P * V * world`), rewritten by the engine
  every frame. TemporalUpscaler adds jitter in its `Scene` layer update hook, so unjittered matrices for
  Streamline must be read *before* that. Reversed-Z depth.
- **Engine buffers:**
  - Motion vectors are `R16G16_FLOAT`, in clip-space units: DLSS SR scales them by (w/2, −h/2) to pixels;
    Streamline's normalized convention is (0.5, −0.5).
  - Depth is `R32G8X24_TYPELESS`, at render resolution.
  - The title scene renders its buffers *smaller* than the size TemporalUpscaler reports (1476x830 vs
    1919x1079 in DLAA mode).
- **The UI is already in the colour DLSS consumes.** TemporalUpscaler overwrites the whole back buffer at
  present, yet menu text survives, so DLSS, NR and frame generation all see the HUD baked in. No HUD-less
  buffer is available. RE2's HUD is minimal, and frame generation is paused in menus.
- **Swap chain:** the game creates its swap chain very early, about 3 s before REFramework's D3D12 hook
  exists. It uses `R10G10B10A2_UNORM` (format 24), 3 buffers, flags 0x842 (mode switch, waitable object,
  tearing). It flips between formats 24 and 28 at startup and never calls `SetColorSpace1`.
- **Camera state:** `app.ropeway.camera.CameraSystem` (managed singleton) has a 4-byte reflection property
  `BusyCameraType`: PLAYER = 0, PLAYER_SIGHT = 1, EVENT = 6 (cutscene), TITLE = 9. Used as the gameplay
  gate for both the Tobii camera lean and frame generation.
- **NR contract (feature 18 = `NVSDK_NGX_Feature_Reserved18`):**
  - Parameters are under `DLSSNR.*`.
  - Colour and output are at the DLSS output size.
  - `DLSSNR.MVec` and `DLSSNR.Depth` are at render size, with their own subrects and `DLSSNR.MVecScaleX/Y`
    (same scale as SR).
  - Plus `DLSSNR.DepthInverted`, `Reset`, `Intensity`, `LocalToneStrength`, `LocalStructureStrength`,
    `SkinStructureStrength`, `UseAutoMask`, `Style` (0 Default, 1 Natural, 2 Cinematic),
    `Hint.Render.Preset` (create time), and a `DLSSNRComputeScalingRatioCallback`.
  - Takes the SDR `R10G10B10A2` back buffer directly.
- **HDR:** RE2's own HDR output looks washed out even fully vanilla (verified with every mod file parked).
  The community fix is ReShade + RenoDX.

## Build steps
1. Clone REFramework `pd-upscaler` and init its submodules. In `cmake.toml` and the generated
   `CMakeLists.txt`, drop `CSharp` from `languages`. Configure with
   `cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DDEVELOPER_MODE=ON`, run `MakeCommitHash.bat` once, then
   `cmake --build build64 --target REFramework`.
2. **Compose before ReShade:** register REFramework as a ReShade add-on (from a translation unit with no
   ImGui) and do TemporalUpscaler's evaluate + back-buffer copy from ReShade's `present` event. Fall back to
   REFramework's own Present hook when ReShade is absent.
3. **NR:** after `EvaluateUpscaler`, on the upscaler's own command list:
   - Get `_nvngx.dll` (already loaded by PDPerfPlugin) and its exported `NVSDK_NGX_D3D12_*` functions. Check
     `DLSSNR.Available` in the capability parameters.
   - `CreateFeature(18)` and `EvaluateFeature` on the DLSS output (transitioned UAV → non-pixel SRV and
     back), with the engine motion vectors and depth.
   - Copy the NR output to the back buffer.
4. **Streamline bootstrap, RE2 only, in the REFramework constructor right after the logger exists:**
   - Verify `sl.interposer.dll`'s signature, load it, and `slInit` with `eUseManualHooking |
     eUseFrameBasedResourceTagging | eDisableCLStateTracking` and features DLSS_G, Reflex and PCL.
   - Pointer-hook `IDXGIFactory2` vtable slot 15 (`CreateSwapChainForHwnd`). In the hook:
     `slSetD3DDevice(queue->GetDevice)`, then `slUpgradeInterface(&factory)`, then create the swap chain through
     the proxy factory. A thread-local guard stops the re-entry when the proxy calls the native slot.
5. **REFramework's D3D12Hook "proxy mode":** vtable-hook Present/ResizeBuffers/ResizeTarget on the
   *proxy* object, and take the command queue from creation (the proxy has no native layout for REFramework's
   offset trick).
6. **Frame generation:**
   - On `pre UpdateHID`: `slGetNewFrameToken`, `slReflexSleep` and SimulationStart.
   - On `pre BeginRendering`: SimulationEnd and RenderSubmitStart, then hand the token to the render thread.
   - At the proxy Present: RenderSubmitEnd, `slSetConstants` (camera captured before jitter), depth and
     motion-vector tags (`eOnlyValidNow`, render-size extent), `slDLSSGSetOptions` and PresentStart.
     PresentEnd after it returns.
   - Gate on `BusyCameraType` ∈ {0, 1, 6}. Request `reset` when the NR look changes.
7. **Tobii:** a plain REFramework plugin.
   - Stream Engine via `GetProcAddress`; callbacks pumped on present.
   - Camera lean written into the primary camera's world matrix on `pre BeginRendering`.

## Verification
- **Logs:**
  - `NGX_D3D12_CREATE_DLSS_EXT ... Success`, `DLSS NR feature created via the NGX core`, `first evaluate OK`
    with buffer formats.
  - `Game swap chain created through Streamline`, `Hooking the Streamline proxy swap chain`,
    `tagged depth + motion vectors ... eOk`, `DLSS-G on (4x): eOk`.
  - Camera-state transitions.
- **PresentMon:** at 4x, 2585 presents in 10 s (259 fps), all displayed, Independent Flip. That is about
  65 game fps, from ~85 without frame generation (DLSS-G 4x costs ~3.6 ms at 1440p).
- **Pixel A/B:** the same build with and without `sl.interposer.dll`. REFramework's menu region was
  byte-identical, which proved Streamline doesn't alter the frame data.
- **Human eyes:**
  - The ReShade overlay is visible with DLSS on.
  - The NR controls change the look, and NR on looks better with no artifacts.
  - No warping, judder or smearing at 2x and 4x with NR on and off.
  - HDR is correct with RenoDX on top.
  - The Tobii lean is correct after sign fixes.
- **Not verified:**
  - 3x mode.
  - Inventory and pause camera states (the gate may leave frame generation on there).
  - Swap-chain recreation after a mid-session resolution change.
  - Reflex latency numbers.
  - VR.
  - Machines without a second GPU.
  - GPUs older than Blackwell for NR.

## Gotchas
1. **ReShade overlay invisible while TemporalUpscaler runs.** **Cause:** the upscaler copies its output to the
   back buffer inside REFramework's Present hook, which sits *below* ReShade's DXGI proxy, so it paints over
   ReShade's effects and overlay every frame. **Fix:** do the copy from ReShade's `present` add-on event, which
   fires before effects and overlay.
2. **ImGui broke when `reshade.hpp` was included.** **Cause:** it pulls in `reshade_overlay.hpp`, which redirects
   ImGui calls to ReShade's function table once `imgui.h` was seen. **Fix:** keep the ReShade bridge in its own
   translation unit with no ImGui.
3. **RenoDX DLSS5 add-on: NR at the Present stage looked off; the Upscale stage did nothing.** **Cause:** at
   Present it feeds synthetic display-res motion/depth, and it never sees PDPerfPlugin's SR evaluates (it only
   logs the creates). **Fix:** run NR ourselves right after SR, with the engine buffers.
4. **The only known NR path looked like it needed a caller-identity spoof.** **Cause:** the add-on calls the
   snippet DLL directly. **Fix:** don't. The driver core (`_nvngx.dll`) reports `DLSSNR.Available = 1`, and
   `NVSDK_NGX_D3D12_CreateFeature(18)` succeeds through the public exports once PDPerfPlugin has initialized
   NGX. Proven first with a 150-line probe plugin.
5. **NR read past the engine buffers on the title screen.** **Cause:** the title renders depth/MV at 1476x830
   while the upscaler reports 1919x1079. **Fix:** clamp the MV/depth subrect to the texture size, and derive
   the MV scale from that region.
6. **Streamline never saw the game's swap chain.** **Cause:** RE2 creates it about 3 s before REFramework's
   D3D12 hooks exist (no `create_swapchain` line in the log). **Fix:** hook factory vtable slot 15 from the
   REFramework constructor, right after the logger.
7. **With `sl.dlss_g` loaded, the game froze: REFramework's present hook went quiet, the upscaler never ran,
   and window capture got no frames.** **Cause:** DLSS-G gives the game "fake" back buffers and presents through
   its own native swap chain (6 buffers, format 28). REFramework's global native-Present hook latched onto that
   one, then starved, and the hook monitor re-hooked every 11 s. **Fix:** vtable-hook the proxy object the game
   presents through. That also puts REFramework's compose and ImGui *above* frame generation, so the real frame
   is never painted over generated ones.
8. **`slSetTagForFrame` returned `eErrorInvalidIntegration` every frame.** **Cause:** it needs
   `PreferenceFlags::eUseFrameBasedResourceTagging` at `slInit`. **Fix:** set the flag.
9. **Worry: two NGX initializations (PDPerfPlugin for SR, Streamline for DLSS-G) on one device.** **Result:**
   no conflict; both run fine.
10. **Frame-generation gate: the title screen reports `BusyCameraType` 0 for its first ~18 s,** then 9, so
    frame generation briefly runs on the title. Harmless.
11. **"Washed out" colours, even on splash screens, after adding frame generation.** **Cause:** not the mod.
    Vanilla RE2's HDR output looks like that. Every mod file was parked: still washed out. Renaming
    `sl.interposer.dll` made no difference. Pixel A/B showed identical data. **Fix:** ReShade + RenoDX (Nexus
    1644) on top. ReShade ends up wrapping Streamline's internal swap chain, *under* frame generation, so the
    order is: game → our DLSS/NR (SDR) → DLSS-G → RenoDX HDR encode per presented frame. NR stays on SDR,
    which suits it (the human reports it looks right).
12. **A RenoDX package installed its own REFramework `dinput8.dll` during a trial.** **Fix:** install only
    ReShade's `dxgi.dll` and the `.addon64`; this mod *is* REFramework.
13. **Build environment.**
    - The REFramework configure needed C# (`No CMAKE_CSharp_COMPILER`), with no C# targets present: remove the
      language.
    - The agent shell sets `NoDefaultCurrentDirectoryInExePath=1`, so DirectXTK's `CompileShaders.cmd` "is not
      recognized": clear it in the build `.bat`. Also bypass the user's `cmd` AutoRun with `cmd /d`.
    - `CommitHash.autogenerated` was missing under Ninja: run `MakeCommitHash.bat` once.
14. **Tobii plugin.**
    - The plugin's `game_name` must be `"RE2"` (uppercase).
    - Camera writes stick only on `pre BeginRendering`; later writes are overwritten by transform
      propagation.
    - Steering the flashlight manager's transform does nothing (dead end).
    - Head-pose rotation is in radians, not degrees.
    - The `BusyCameraType` getter writes 4 bytes: zero-initialize a 64-bit buffer.
15. **Packaging: zips from Windows PowerShell 5.1's `Compress-Archive` store `dir\file` entry names,** which
    some extractors and mod managers turn into files named with backslashes. **Fix:** write the zip with
    `System.IO.Compression` and forward slashes.
16. **Can the Tobii runtime ship with the mod? No.** The Stream Engine headers carry Tobii AB's notice that
    reproduction is forbidden without written permission, and the SDK bundle grants no redistribution right.
    **Fix:** don't ship it. Tobii Experience installs it at `C:\Program Files\Tobii\Tobii EyeX\`, and the plugin
    falls back to that path (then PATH). Verified 2026-10-09: with no Tobii runtime and no `nvngx_dlssnr.dll`
    the game runs, DLSS SR and frame generation work, and NR and eye tracking switch off with one log line each.
    A self-contained Stream Engine API reference, the extended-view recipe with the tuned values, and the pitfalls
    the public docs miss (3- vs 4-parameter `tobii_device_create`, radians, reconnect) are in
    [the Tobii technique note](../../techniques/tobii-eye-tracking-in-any-pc-game-stream-engine-without-ship.md).

## Assets
None generated. Evidence screenshots and PresentMon CSVs live in the working folder, not in the repo.

## Cost and time
About two days (2026-10-07 to 2026-10-09), several sessions. Most of the time went to proving where things sat
in the present chain: ReShade vs REFramework vs Streamline.

## Open questions
- HUD-less colour and a UI alpha for DLSS-G. That needs a capture before the GUI pass; better UI
  interpolation would come from it.
- Inventory and pause camera states for the gate.
- Swap-chain recreation: REFramework's own `create_swapchain` hook chains onto ours and runs its reset logic
  twice on a recreate. Not yet seen to break anything.
- Streamline logs `getResourceSize ... native 13` errors for the motion-vector clones (bookkeeping only).
- Whether to upstream the ReShade-compose and Streamline proxy-mode changes to REFramework.
- The mod's source is not published yet.
