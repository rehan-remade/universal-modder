---
kind: technique
title: "What dgVoodoo2 really does to an old D3D8 game, and how to spy on a packed D3D wrapper"
tags: [dgvoodoo, d3d8, d3d11, wrapper, dxbc, vtable-hooks, id3d10multithread, scaling, filtering, fog, renderdoc]
date: 2026-10-09
agents: ["Claude Code (Opus 5.5)"]
humans: ["GR33N"]
links: ["https://dege.freeweb.hu/dgVoodoo2/"]
---

# What dgVoodoo2 really does to an old D3D8 game, and how to spy on a packed D3D wrapper

> dgVoodoo2 is the usual fix for 1999-2006 Direct3D games, and people credit it with "magic": a smoother
> image, no fog bugs, working Alt+Tab. We captured exactly what dgVoodoo2 2.87.5 (D3D8.dll, D3D11 output)
> sends to Direct3D 11 for a 2004 D3D8 RTS: every shader, state and draw. There is no magic, only a handful
> of choices you can copy into your own wrapper. RenderDoc could not see its device, so the method was a
> spy `d3d11.dll` of our own. Measured on The Dark Legions while building GR33N's The Dark Legions Reloaded
> mod (see the game note); the findings are about dgVoodoo, so they apply to any D3D8/D3D9 game run through it.

## When to use it
- You want to know why a game looks or behaves differently under dgVoodoo (or any packed D3D wrapper) and
  copy the good part into a mod of your own (e.g. a single-DLL fix without dgVoodoo).
- RenderDoc / PIX don't capture it in your setup (ours: a packed wrapper with its own device creation path, and
  a UAC-elevated game; see Gotcha 4).

## How: a spy d3d11.dll
dgVoodoo's D3D8.dll is packed (one section, entropy ~7.9, imports only LoadLibrary / GetProcAddress /
VirtualProtect). It loads `d3d11.dll` by name, and the game's folder comes first in the DLL search order:
1. Copy the system's 32-bit `d3d11.dll` (SysWOW64) next to the game as `d3d11_real.dll`.
2. Build your own `d3d11.dll` (32-bit, static CRT) that exports only `D3D11CreateDevice` and
   `D3D11CreateDeviceAndSwapChain` (ordinals 22/23). That was enough for dgVoodoo; forwarding the rest with a
   .def file failed to link and was not needed.
3. In those two, call the real ones, then patch the device's and the immediate context's vtable entries
   (keep the originals in a map keyed by vtable+slot, since contexts can share vtables). Useful slots:
   device CreateTexture2D 5, SRV 7, RTV 9, VS 12, PS 15, CS 18, blend 20, raster 22, sampler 23; context
   PSSetShaderResources 8, PSSetShader 9, PSSetSamplers 10, VSSetShader 11, DrawIndexed 12, Draw 13,
   IASetInputLayout 17, OMSetRenderTargets 33, OMSetBlendState 35, RSSetState 43, RSSetViewports 44,
   ResolveSubresource 57, Dispatch 41.
4. Dump each shader's bytecode as DXBC (hash it, write once) and disassemble offline with `D3DDisassemble`
   from `d3dcompiler_47.dll` (callable from Python through ctypes). Log states per draw, in bursts (the first
   few thousand draws, then N draws every M seconds, and on a hotkey), not every frame.

## What dgVoodoo2 2.87.5 does (config: Resolution max_isf, MSAA 4x, ScalingMode stretched, Filtering appdriven)
- **Resolution and output:** the game is drawn at an integer multiple of its resolution (2x: 1024x768 ->
  2048x1536) into an MSAA target. At the end there is ONE ResolveSubresource straight into a swap chain
  buffer of that same size, a small shader paints the borders black, and DXGI stretches the buffer to the
  monitor (bilinear). No Lanczos, no sharpening, no post-processing anywhere, in menus or in missions.
- **2D (splash, menus, HUD):** drawn with the game's own point filter, viewport offset by +0.5 px (the D3D8
  pixel-centre convention). Point sampling at 2x, then a bilinear stretch, gives "sharp texel squares with
  only the steps between them blended, about one monitor pixel wide". That is the whole of its "smoother
  splash screen".
- **16-bit textures** are kept as raw 16-bit data and expanded in the pixel shader through two lookup tables
  (low byte and high byte -> RGBA, summed), which is exact for any 16-bit format.
- **Fixed function** is emulated by generated pixel shaders: `tex * diffuse + specular`, alpha test as
  `discard` (alpha*255 <= ref), stage combinations (ADD, second stage's alpha).
- **Fog is computed per pixel in the shader:** f = saturate((end - depth) / (end - start)) with depth =
  SV_Position.w (eye distance), colour = lerp(fog colour, colour, f). It never asks a driver for table fog,
  which is why games with broken table fog (see Gotchas) look right under dgVoodoo.
- **Samplers:** exactly what the game sets (appdriven): point mag + linear mip for most 3D, some trilinear,
  anisotropy 1 everywhere. A wrapper that forces 16x anisotropic filtering already looks sharper in 3D.

## Copying it into your own wrapper (D3D9Ex or D3D11)
- Supersample at an integer factor + MSAA, then filter down to the monitor. Lanczos-3 is crisper than
  dgVoodoo; a tent (bilinear) kernel reproduces dgVoodoo's softer look. Offer both.
- To match its stretched 2D pictures, do NOT use linear or bicubic filtering (users saw them as blurry, and a
  B-spline as soft and grainy). Use a "sharp bilinear" lookup: inside a texel flat, a ramp one output pixel
  wide between texel centres: `k = saturate((frac(t - 0.5) - 0.5) * pixelsPerTexel + 0.5)`, sample at
  `floor(t - 0.5) + 0.5 + k` with a linear sampler and clamp addressing (pictures cut into tiles must not
  wrap).
- Fog: in D3D9 you do not need a shader. Table fog is per-pixel, W-based fog already, as long as the
  projection matrix has a finite far plane (see Gotchas). Same formula as dgVoodoo's shader.

## Gotchas
1. **Symptom:** the spy logs the splash screen, then no draws at all. **Cause:** dgVoodoo queries
   `ID3D10Multithread` (9b7e4e00-342c-4106-a19f-4f2704f689f0, the same IID as ID3D11Multithread) and turns
   protection on; Direct3D then swaps thread-safe entries into the context vtable, replacing your hooks.
   **Fix:** a thread re-checks the vtable every ~50 ms; a slot that no longer points at your hook holds the new
   original, so store it and hook again.
2. **Symptom:** you look for deferred contexts or a second device. **Cause:** the same vtable swap (1).
   dgVoodoo used only the immediate context. **Fix:** check the vtable first.
3. **Symptom:** a screenshot of dgVoodoo is 4:3 while the monitor showed it stretched. **Cause:** in windowed
   mode a capture grabs its internal 4:3 frame before DXGI stretches it. **Fix:** compare by looking at the
   monitor, or capture fullscreen. We first "fixed" a stretched splash into 4:3 because of this.
4. **Symptom:** RenderDoc shows no device, in D3D11 or D3D12 mode. **Cause:** the packed wrapper and its own
   device path; the game also asked for UAC elevation (compatibility flags), and RenderDoc had to be started
   with `__COMPAT_LAYER=RunAsInvoker` to inject at all. **Fix:** the spy DLL above.
5. **Symptom:** blue blotches or a blue haze close to the camera in an old game with fog, on modern drivers,
   gone under dgVoodoo. **Cause:** the game's projection has an infinite far plane (_33 = _34 = 1,
   _43 = -near); drivers derive the W range for table fog from the projection and get infinity. **Fix**
   (D3D9 wrapper): give the projection a finite far plane (e.g. 1e6) in SetTransform; or fog per vertex.

## Seen in
- The Dark Legions (2004, D3D8): `knowledge/games/the-dark-legions/reloaded-single-dll-fix.md`.
