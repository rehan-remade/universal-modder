---
kind: game
title: Widescreen, texture overrides and a geometry-based cartoon look for Disney's Extremely Goofy Skateboarding (D3D8 ASI
  plugin)
game: Disney's Extremely Goofy Skateboarding
games_also: []
game_version: "Retail PC CD release (Krome Studios / Disney Interactive, 2001), Skating.exe 911,491 bytes; Windows 11 Home 26200"
platform: windows
engine: unknown
route: native-hook
tools: ["Ultimate ASI Loader 9.7.4 (32-bit, as dinput8.dll)", "safetyhook", "Ghidra 12.1.4 + GhidraMCP", "MSVC (VS Build Tools) + CMake, Win32", "Python 3 + Pillow / OpenCV", "ComfyUI + Qwen-Image-Edit-2511 (textures)", "Real-ESRGAN / 4x-UltraSharpV2 (textures)"]
anti_cheat: "none (offline single-player). The retail disc build uses SecuROM 4, which does not start on Windows 10/11; nothing here touches or describes the protection."
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-09'
links: []
tags: [d3d8, widescreen, hor-plus, hud, borderless, asi-loader, texture-replacement, upscale, cel-shading, toon, outlines, inverted-hull, draw-call-log]
---
# Widescreen, texture overrides and a geometry-based cartoon look for Disney's Extremely Goofy Skateboarding (D3D8 ASI plugin)

> A 32-bit ASI plugin for Krome's 2001 Direct3D 8 skateboarding game gives native-resolution borderless widescreen
> with Hor+ FOV and a 4:3-pillarboxed HUD, WASD controls, loose-file texture overrides (upscaled and AI-redrawn
> textures), and a cartoon look drawn on the game's own meshes: inverted-hull ink outlines on characters, ink strokes
> on level edges, and a stepped key light. Widescreen, controls and textures were verified in game by the human owner.
> The cartoon look was verified on captured frames of the deterministic attract demo; a hands-on play test is pending.

## Setup
- Retail PC disc release, `Skating.exe` 911,491 bytes. All addresses below are for that exe. The game uses
  `dinput8.dll`, `d3d8.dll` (via `Direct3DCreate8`), `binkw32.dll` and `fmod.dll`.
- Windows 11 Home (build 26200), RTX 5070 Ti Laptop GPU, 2560x1600 at 150 % DPI. No dgVoodoo or other wrapper needed.
- Ultimate ASI Loader v9.7.4 x86 installed as `dinput8.dll` (the exe imports it statically, so the proxy loads
  before the entry point). Plugin: one `dllmain.cpp`, CMake `-A Win32`, static CRT, safetyhook for inline/mid hooks.
- Ghidra 12.1.4 with a GhidraMCP bridge for static analysis.

## Route and why
Native hooks from an ASI plugin. There is no mod loader or scripting layer; the game data sits in one archive that
the engine already lets loose files override (see below), so textures needed no repacking. For the cartoon look,
screen-space filters (colour-edge outlines, posterising, bilateral smoothing, even an AI img2img redraw of whole
frames) were mocked up first and rejected by the owner as looking like a Photoshop filter. The working approach
hooks the D3D8 device vtable and adds draws on the real geometry. ReShade + d3d8to9 was considered and turned out
not to be needed.

## How the game works (what we had to learn)
**Display.** Screen size globals `g_ScreenWidth/Height` at `0x487b98`/`0x487b9c` (initialised `.data`, 640x480),
read by WinMain before `BG_Init` (`0x44a6e0`) → `BG_CreateDevice` (`0x44a840`). Windowed flag `0x00a2bdec`; with
it set and the window a `WS_POPUP` at the desktop size, the game runs borderless with no other change. Device
pointer global: `0x00a82378`. End of frame (EndScene + Present): `BG_EndFrame` `0x449de0` (fastcall).

**FOV.** `BG_SetFov` `0x447960` and `BG_SetFovXY` `0x4479b0` build the projection in `0x489e98`, and cache X/Y
scales at `0x48a3ec`/`0x48a3f0` that culling and billboards use. Hor+ = after the original, set `_11 = _22 / aspect`
(aspect from the current viewport, not the back buffer, so 4:3 sub-viewports stay right) in the matrix and the
cache, then `SetTransform(PROJECTION)` again.

**HUD.** All 2D goes through `BG_Draw2DQuad` `0x44b120` (cdecl; vertex X args 7/11/15/19 in a virtual 640x480).
A mid hook at entry compresses X toward 320 by `(4/3)/aspect`, skipping quads that span the full width (fades,
backgrounds) and pixel-mode quads (flag `0x00a2be88`).

**Archive.** `Data\data0.pkg` is a plain ZIP (1,118 Deflate entries, flat names; .tga/.bmp textures, .ase models,
.wav/.mp3, level and animation data) opened with stock minizip ("unzip 0.15"). The file-open routine looks for a
loose file first, recursively under the game folder, and only then the archive. So a file of the same name in any
`Data\` subfolder overrides the archive.

**Textures.** Loaded with D3DX8 `CreateTextureFromFileInMemoryEx` into the managed pool. D3DX goes by the bytes,
so a DXT1/DXT5 DDS saved under the original `.tga` name loads fine. The material table (stride `0xb0`, name at
`+0`, `IDirect3DTexture8*` at `+0x20`) stores the texture's real size at `+0x28/+0x2c` (written at `0x44ae89`/
`0x44ae8c`). Only the GUI sprite code reads it, to turn 256-based pixel rectangles into UVs. So upscaled GUI atlases
need a mid hook at `0x44ae8f` that writes back the original size, or sprites sample the wrong quarter.

**Controls.** The live key map is 8 DirectInput codes at `0x49a7a0` (up, down, left, right, ollie, trick2–4), filled
with numpad 8/2/4/6, Space, C, V, B at profile init `0x438f4a` and saved to the save file. Copies at the player
object and the console variables are written but never read; rewrite the live table instead.

**Frame pacing.** The main loop caps at 30 fps; physics may depend on it (not lifted).

**What the renderer draws (from a draw-call log, see Build steps).**
- Every 3D mesh is one `DrawIndexedPrimitiveUP`, triangle list, 16-bit indices, FVF `XYZ|NORMAL|DIFFUSE|TEX1`
  (0x152), stride 36. 75–90 per gameplay frame. Normals are real unit normals on every mesh.
- Fixed-function lighting is off. The shading is baked into the vertex colour by the game's CPU code, and it is
  blotchy on the low-poly characters.
- The HUD (`DrawPrimitiveUP`, XYZRHW|DIFFUSE|SPECULAR|TEX1) is drawn after all 3D.
- Device caps on this machine: VS 1.1, PS 1.4. Depth buffer D16. Level meshes use an identity world matrix.
- **The world is mirrored: y points down** (the camera's y is smaller than the skater's while it sits above him).
- Characters are closed meshes. **Level meshes are open shells** (a ramp is one surface with no back faces).
- The attract demo (title screen idle for about 2 minutes) replays fixed recordings and is frame-deterministic:
  the same frame numbers show the same moment in every run, so it works as a visual regression test.

## Build steps
1. Proxy-load the plugin with Ultimate ASI Loader (`dinput8.dll`). Run `Init` in `DllMain` (only the main thread
   exists; WinMain hasn't read the globals yet). `memcmp` 10 bytes at every patch site first and patch nothing on a
   mismatch.
2. Widescreen: write the screen-size globals and the windowed flag; Hor+ detours on the two FOV setters; the HUD
   mid hook; after Present, clear the pillarbox bars (menus don't redraw them and the COPY swap effect leaves
   trails); subclass the window to minimise on deactivation and restore after unlock.
3. Textures: put DDS files (original names) in `Data\remaster\` plus a `sizes.txt` of original sizes for the
   size-restoring hook.
4. Device hooks: in the end-of-frame hook, once the device pointer is set, patch its vtable (slots: SetRenderState
   50, SetTexture 61, SetTransform 37, Clear 36, DrawPrimitive 70, DrawIndexedPrimitive 71, DrawPrimitiveUP 72,
   DrawIndexedPrimitiveUP 73, SetVertexShader 76, SetStreamSource 83, SetPixelShader 88). Track states, textures,
   transforms and FVF in the hooks.
5. Recon: an INI-driven draw-call log for chosen frames (one line per draw plus a JPEG of the frame from the back
   buffer). Run it on the attract demo.
6. Cartoon look, per `DrawIndexedPrimitiveUP` of format 0x152 (skip blended, no-z-write and alpha-tested draws):
   - **Characters (non-level textures): inverted hull.** Draw again with vertices pushed along the averaged normal
     by `width_px * 2 * z_view / (P22 * screenH) / worldScale`, cull flipped, stage 0 = SELECTARG1 DIFFUSE, ink colour.
   - **Level (`lvl*` textures): edge strokes.** Weld vertices by quantised position, build edge → faces, and ink
     creases (> 35°), silhouettes and front-facing borders as camera-facing quads (side = cross(edge, mid − camera),
     camera found by inverting World*View), pulled 0.3 % toward the camera, fog off, cull none.
   - **Cel key light on characters.** Vertex colour → hue only; brightness = `0.45 + 0.55 * max(0, N·L)` with a
     fixed view-space light, passed as a second texcoord (FVF TEX2) and modulated on stage 1 by a 256x1 three-band
     ramp texture (managed pool, linear filter, very short soft edges). Restore every stage-1 state afterwards.

## Verification
- Widescreen, HUD, borderless focus handling, WASD and texture overrides: hand-tested in game by the owner on the
  2560x1600 display, against vanilla screenshots of gameplay, menus and loading screens.
- Texture overrides: tinted test textures for each container format; the archive's SHA-256 is unchanged.
- Cartoon look: the plugin's back-buffer capture of attract-demo frames 2200/2500/2800/3100, compared with the same
  frames from a vanilla run. Not verified yet: a hands-on play test, other levels and characters, Alt+Tab/device
  Reset with the added resources, and frame time.

## Gotchas
1. **Screen-space cartoon filters look cheap.** Colour-edge outlines traced every speck of the gravel texture,
   smoothing smeared the small character, and an AI img2img redraw that keeps the layout barely changed anything.
   **Fix:** work on the geometry (hulls, edge strokes, stepped lighting) through draw-call hooks.
2. **Crash on the first frame after adding device hooks.** **Cause:** a helper called "the original" for vtable
   slots that were never patched (GetTextureStageState 62, SetTextureStageState 63), so it called null.
   **Fix:** fall back to the live vtable entry for unpatched slots.
3. **Hull outlines show on the skater but not on the level.** **Cause:** level meshes are open shells; a hull of a
   one-sided surface has no back faces to show. **Fix:** ink edges (creases, silhouettes, borders) as quads.
4. **Edge strokes on the wrong edges (or missing).** **Cause:** the world has y pointing down, so the cross-product
   face normals were all inverted, and "faces the camera" tests flipped. **Fix:** orient each face by the sign of
   its dot product with the summed vertex normals.
5. **Distant ink lines turn white.** **Cause:** the game's fog applies to the added stroke draw. **Fix:** fog off
   (D3DRS 28) for the stroke draw, restored after.
6. **Hull tears open at hard corners.** **Cause:** faceted meshes duplicate corner vertices with per-face normals.
   **Fix:** push along normals averaged over all vertices at the same position.
7. **Cel shading did nothing visible on characters.** **Cause:** the baked vertex lighting is nearly flat and
   blotchy. **Fix:** replace it with a fixed view-space key light and drop the vertex hue.
8. **Blotchy trousers that looked like bad lighting were a texture.** The originals for clothes are 8x8 flat
   colours, and an AI texture redraw had added a woven pattern. **Fix:** flag flat originals (per-channel standard
   deviation < 4) whose replacement isn't flat, and put the flat colour back.
9. **Upscaled GUI atlases draw the wrong sprite pieces.** **Cause:** GUI UVs divide 256-based pixel rectangles by
   the texture's real size. **Fix:** report the original size through the material-entry hook.
10. **Menu buttons leave trails in the pillarbox bars.** **Cause:** windowed swap effect COPY and menus that
    redraw only part of the screen. **Fix:** clear the bars after Present.
11. **Unattended runs stop drawing.** **Cause:** the plugin minimises the borderless window on focus loss.
    **Fix:** skip the minimise while frame capture is enabled; capture from the back buffer, not the screen
    (works even with the PC locked).
12. **No debugger needed for render recon.** A one-frame draw log with texture names (found by scanning the
    material table for the texture pointer) answered every question about formats, lighting and pass order.

## Assets
Textures: all 500 upscaled 4x (4x-UltraSharpV2, Real-ESRGAN ncnn), then about 300 scenery textures redrawn locally
with Qwen-Image-Edit-2511 (8-step Lightning LoRA, ComfyUI, GGUF) or detail-transferred from CC0 ambientCG materials,
picked by an automatic layout-fidelity check plus a by-eye override list. Packed as DXT1/DXT5 DDS with full mips.
No game files are distributed; users bring their own disc.

## Cost and time
About four working days across sessions for widescreen, controls and textures; the cartoon look took one afternoon
from recon to working capture. All generation ran locally on one laptop GPU.

## Open questions
- Lifting the 30 fps cap safely (physics may assume it).
- The cartoon look on the other levels and characters, and in motion (flicker of edge strokes at grazing angles).
- Fewer edge strokes reach the planks lying directly on roofs (they lose the depth test); a small depth bias or a
  per-mesh exception may help.
- Bink splash videos draw corrupted (also without the plugin).
