---
kind: technique
title: "Replacing dgVoodoo with your own D3D8 -> D3D9Ex wrapper in one DLL"
tags: [d3d8, d3d9ex, wrapper, proxy-dll, supersampling, lanczos, msaa, xyzrhw, widescreen, gamma, fog, rust]
date: 2026-10-09
agents: ["Claude Code (Opus 5.5)"]
humans: ["GR33N"]
links: []
---

# Replacing dgVoodoo with your own D3D8 -> D3D9Ex wrapper in one DLL

> An old Direct3D 8 game can get a modern renderer from a single `d3d8.dll` placed next to its exe: your DLL
> implements the D3D8 interfaces on top of Direct3D 9Ex, and the same DLL also patches the game (crash fixes,
> widescreen, new menus). Built in Rust for The Dark Legions (2004); it replaced dgVoodoo2 and was better on
> every count we measured (sharper, faster, fixes dgVoodoo could not make). These are the parts and the
> traps, in the order you meet them.

## When to use it
- A D3D8 game (or D3D9 with care) that you want to ship as "one file, drop it in", with control over the
  final image, the 2D layer and the game's own code.
- If you only need it to run, dgVoodoo2 or DXVK is less work. See
  `dgvoodoo2-internals-and-spying-on-a-packed-d3d-wrapper.md` for what dgVoodoo does, so you can match it.

## How
1. **Proxy:** export `Direct3DCreate8` from your `d3d8.dll`; Windows loads it from the game folder first.
   Your IDirect3D8 / IDirect3DDevice8 / textures / buffers / surfaces are your own COM objects (vtables
   built by hand) that forward to D3D9Ex objects. Settings in an ini the DLL writes itself on first run
   (with comments), a log next to the exe; anything else the DLL creates on demand.
2. **Window and device:** borderless window over the monitor (or a framed window), DPI-aware, D3D9Ex device
   with FLIPEX. The game keeps thinking it runs at its own resolution (e.g. 1024x768); you translate the
   mouse from monitor pixels to game pixels (WndProc messages, GetCursorPos, ClipCursor).
3. **Render target:** the game draws into your target at `scale` x its resolution (auto: the smallest integer
   factor covering the monitor) with MSAA. At Present: resolve, then a 2-pass separable Lanczos-3 (kernel
   widened by the shrink ratio so nothing aliases, weights normalised, fp16 intermediate so negative lobes
   survive) down to the monitor. A tent kernel in the same shader is the "soft" option. Only ever shrink by
   a non-integer ratio, never stretch by a few percent: that makes pixel-drawn text uneven.
4. **2D (pre-transformed XYZRHW vertices):** D3D9 draws them at the exact pixel given, so on a 2x target the
   whole interface lands in the top-left quarter. Bind a generated vs_2_0 per FVF that maps game pixels to
   the scaled target, through a vertex declaration that declares the position as POSITION (float4): SetFVF
   with XYZRHW means POSITIONT, and D3D9 skips vertex processing, your shader included, for POSITIONT. Map x
   as (x - 0.5) * scale: games put their 2D corners on 0.5, which at 1x hid a row and a column that show at
   2x/3x.
5. **Gamma:** a windowed / FLIPEX device cannot set the monitor's gamma ramp. Keep the game's
   SetGammaRamp as a 256x1 texture and apply it in the last filter pass (on every filter, including soft).
6. **Performance:** see Gotchas 3 and 4. After those, the wrapper's own cost was ~15% of a frame.
7. **Widescreen and menus** live in the same DLL: widen the game's projection, keep the HUD where it was,
   centre menus by moving their vertices (identify screens by the texture file names the game loads),
   stretch full-screen pictures, and move the mouse back by the same offset.

## Gotchas
1. **Symptom:** blue blotches / haze on things near the camera (also in the original game on today's
   drivers). **Cause:** table fog with an infinite-far projection (_33 = _34 = 1); the driver's W range is
   infinite. **Fix:** rewrite the projection with a far plane of 1e6 in SetTransform; per-vertex fog as a
   fallback option.
2. **Symptom:** long stretched triangles ("wedges") across the screen. **Cause:** the game turns
   D3DRS_CLIPPING off, which D3D9 hardware vertex processing honours. **Fix:** keep clipping on.
3. **Symptom:** low FPS in a 2004 game on a modern GPU. **Cause:** the game asks for software vertex
   processing. **Fix:** create the device with hardware vertex processing and handle the SOFTWAREPROCESSING
   buffer usage yourself.
4. **Symptom:** still slow; the GPU is fine, the CPU is busy uploading. **Cause:** the game rewrites
   MANAGED / static vertex buffers hundreds of times a frame (a 160 KB buffer to draw a few KB). **Fix:** keep
   a system-memory copy of each buffer and upload only the range a draw actually uses into one big shared
   ring (VB, IB16, IB32; NOOVERWRITE, DISCARD on wrap). 100 MB/frame became 2.4 MB/frame.
5. **Symptom:** a texture the game locks keeps its old content, or goes black after a reset. **Cause:**
   D3D9Ex has no MANAGED pool. **Fix:** managed textures = a system-memory copy the game locks + a DEFAULT
   texture, uploaded before the next draw that uses them.
6. **Symptom:** the image looks "softer" than under dgVoodoo, or text looks smeared. **Cause:** linear
   filtering applied to pictures that dgVoodoo point-samples. **Fix:** keep the game's point filter for 2D,
   and use a sharp-bilinear shader where you stretch (see the dgVoodoo note).
7. **Symptom:** Alt+Tab or closing from Task Manager leaves an invisible game running (it even autosaves).
   **Cause:** the game has no focus/close handling. **Fix:** on WM_DESTROY, terminate the process if it is
   still running after a few seconds.

## Seen in
- The Dark Legions Reloaded, a mod by GR33N (2004 game): `knowledge/games/the-dark-legions/reloaded-single-dll-fix.md`.
