---
kind: technique
title: "Hooking a host engine's post-world render pass so world geometry occludes your overlay"
tags: [rendering, occlusion, depth-buffer, hooking, projection, frustum-parity, overlay, native-hook, d3d9]
date: 2026-10-11
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: []
links: ["https://github.com/carxt/JohnnyGuitarNVSE/blob/b3521cb0b577632473fa731b7b9f83fe346738bf/JG/internal/Game/Bethesda/BSShaderUtil.cpp"]
---

# Hooking a host engine's post-world render pass so world geometry occludes your overlay

> You are drawing foreign geometry inside a host game. It shows up, but it is never hidden by the world:
> it floats over terrain, over menus, over everything. The fix is not a shader tweak - it is to draw it
> inside the host's world pass, in the short window where the world depth buffer is still bound. Getting
> there has one prerequisite almost nobody expects (projection parity), and two traps that will waste a
> day each (an address after a call, and your own Z clears).

## When to use it

- You draw foreign geometry (another game's model, a custom overlay, an editor gizmo) into a host engine
  through a hook, and the world must occlude it.
- You are about to choose between a **Present/overlay** draw and a **scene** draw.
- You already have a scene draw and it "does not occlude no matter where I hook".

## How

### 1. Pick the draw style deliberately

| | **Present overlay** | **Scene geometry (in-scene draw)** |
| --- | --- | --- |
| where | after world, imagespace and UI | inside the world pass, pre-imagespace/UI |
| world occlusion | **none** | yes (depth-tested) |
| host lighting | no (you fake it) | yes (host accumulation) |
| drawn over menu UI | **yes** | no |
| projection | you must reconstruct and match it | the host camera is used |

Symptoms that you are on the wrong side: no occlusion; lighting does not match the scene; the object
appears over menu UI; a hard vertical brightness seam (you are after the imagespace/menu-blur composite).

The **most robust** form is to create real host scene nodes (host `NiTriShape`/`BSFadeNode` under the
player/world root) so the host culls, lights, depth-tests and thumbnails them for you. If that is too
much work, the D3D draw-in-scene form below is the next best and is what the worked example shipped.

### 2. Find the frame dispatch, then the scene render function

- Locate the engine's **frame-render dispatcher** and the **gameplay scene-render path** (the normal
  case) as distinct from menu/variant paths. A hook inside the gameplay path is structurally not run by
  the pure menu path - but pause/pipboy-style frames that still render the live world do reach it, so a
  runtime menu guard is still mandatory.
- **Do not assume the scene-render function contains the world render call.** In the worked example the
  plan of record named a `RenderScene` call inside the gameplay render function; a read-only map of its
  81 calls proved there is **none** - the four `RenderScene` sites live in callee functions. Verify the
  premise before building on it.

### 3. Land projection parity FIRST (the prerequisite)

**Build your projection from the host's LIVE camera frustum, not from your own config.** If your near/far
(or the projection's depth mapping) differ from the host's, your Z values cannot compare against the
world depth buffer for any object at any draw point - so occlusion fails **everywhere**, and every hook
candidate you try will falsely "fail".

- Read the live projection from the host camera (worked example: `NiCamera::m_kViewFrustum`; live
  near/far were `5.0 / 353840.0` host units while our config said `0.002 / 100`).
- If the frustum is asymmetric (`l != -r`, `t != -b`), build an **off-centre** projection - recomputing a
  symmetric one from FOV/aspect loses a viewport shift (scopes/dialogue/VATS) and biases the object
  horizontally.
- Keep your own FOV for framing if you like; take only the **depth mapping** from the live frustum.
- Log it as an oracle: `pov: frustum n=.. f=.. cfg=(..) live=1 s=..`.

### 4. Find the main-target scene render call, and hook its return

- Among the host's scene-render calls, only the one **not bracketed by an offscreen render-target
  begin/end** is the main-bound (backbuffer) world pass. The bracketed ones are aux/offscreen passes
  (water/VATS/rendered menu) - instrument them, **never draw there**.
- **Hook the call's return, not an address after the call.** An address after a call is not a semantic
  point: in the worked example the address after the world render call turned out to be a **shared
  stack-object destructor called after all four render sites**. It patched cleanly, executed, and never
  drew.
- The working shape: detour every call site so your thunk **`call`s** the original (do not tail-`jmp`),
  and run your draw after the original returns. At that instant the world is in the backbuffer and the
  **world depth buffer is bound, pre-imagespace/UI**.
- Before drawing there: verify the site's **calling convention** (worked example: every site is cdecl,
  `add esp,0C`) and use a **stack-transparent** thunk (`popl`/`call`/`pushl`/`ret`). A bare `call` shifts
  the callee's arguments by 4 and breaks the frame.

### 5. Do not clear Z in that window

The host's world depth must survive so your geometry is depth-tested against it. Suppress your own Z
clears while in the post-world window. A leftover "clear Z" is a classic reason a correct hook still
shows through walls.

### 6. Avoid double-drawing

If you also draw from a Present path, gate it: the in-scene draw sets an "already drew this frame" flag
and the Present-path draw keeps skipping while the in-scene pass drew.

### 7. Prove it with a Z-tested test quad (or walk behind a hill)

- Verify the bound target identity at draw time (render target 0 / depth-stencil surface).
- The decisive test: put the object behind a hill and record at 60 fps. In the worked example, at t=20 s
  the vehicle's wheels and lower chassis were hidden behind a terrain ridge (only the cage above it) and
  at t=23 s it was gone entirely, with the view direction unchanged.
- **Describe each side's pixels before reading any log line**, and note honestly if you have no guest /
  reference frame for the same shot - then the comparison is UNVERIFIED, not MATCH.

### 8. Add the telemetry in the same build

Log the hook install (found/hooked/skipped/notcdecl), the post-draw enable flag, the live frustum vs your
config, and a throttled frame-time line. In the worked example:
`camera: render-scene ownership found=4 hooked=4 skipped=0 notcdecl=0 postDraw=1` and
`render: post-world draw third=0 seated=0 veh=1`.

## Gotchas

1. **No occlusion at any hook point.** **Cause:** your projection used your own near/far while the host
   camera had a different one, so your Z could not compare against the world depth buffer. **Fix:** land
   frustum parity from the live camera first.
2. **The detour patches, executes, and never draws.** **Cause:** the hooked address after a call was a
   shared destructor used by several render sites. **Fix:** hook the render call's **return**.
3. **Drawing in an aux pass does nothing (or corrupts it).** **Cause:** you picked a `RenderScene` call
   inside an offscreen render-target begin/end (water/VATS/rendered menu), not the main-target pass.
   **Fix:** pick the call with no RT bracket; instrument the others only.
4. **Your geometry shows through walls even though the hook is right.** **Cause:** you cleared Z inside
   the post-world window, destroying the host's world depth. **Fix:** suppress your Z clears there.
5. **The frame breaks when the hook fires.** **Cause:** a **bare `call`** shifts the callee's arguments
   by 4, or the site's calling convention was not checked. **Fix:** verify cdecl/`stdcall` per site and
   use the transparent `popl`/`call`/`pushl`/`ret` thunk.
6. **It draws twice (or flickers).** **Cause:** both the in-scene and the Present path drew the same
   frame. **Fix:** the in-scene pass sets the "drew this frame" flag; Present skips when set.
7. **It draws over the pause/main menu.** **Cause:** world-rendering menu frames still reach the
   gameplay render path. **Fix:** a runtime menu guard, and prefer a point inside the gameplay path
   (which the pure menu path does not run).
8. **Wrong framing or no occlusion on VATS/killcam/dialogue frames.** **Cause:** a different camera or
   frustum may be live on those frames while your draw suppresses Z clears. **Fix:** log the POV/menu/VATS
   flags at the post-draw and test one such frame explicitly.
9. **A cheap test quad "occludes" and the real object does not.** **Cause:** the quad's Z came from your
   config, not the live frustum (see 1). **Fix:** re-derive and re-test after parity lands.
10. **Matrix-convention guess rolls the world.** **Cause:** a guessed convention: the camera transform's
    memory order (row- or column-major) and the multiply order the code assumed (`M*p` with column vectors,
    `p*M` with row vectors) didn't agree. **Fix:** prove the convention from the live engine - read the
    engine's own matrix and check a known direction.

## Seen in

- Halo 3's Warthog, Chief and weapons inside Fallout: New Vegas (the author's project; no field note
  or public repository yet)
  - `BSShaderUtil::RenderScene` (`0x00B6C0D0`, cdecl, taking the `NiCamera` and the `BSShaderAccumulator`,
    as JohnnyGuitarNVSE's `BSShaderUtil.cpp` also names it) hooked at its four call sites; live frustum
    `5.0 / 353840.0`; the shared-destructor dead end; the 60 fps occlusion clip.

## Related

- `geometry-transfer-host-draws-guest-meshes.md`: the route this hook serves (the host draws the guest's
  meshes), and restoring the host's render state after your draw.
- `frame-compositing-depth-and-pose-sync.md`: the other route, where the guest's colour and depth are
  composited into the host frame instead.
- `porting-a-vehicle-semantic-traps.md`: the live near/far as one of several guessed meanings (gotcha 4).

## What a future agent should try first

1. **Instrument the host's frame dispatch and count the scene-render call sites** with a read-only pass
   (log, or Cheat Engine read-only - never breakpoints). Confirm which call is the main-target pass
   before touching anything.
2. **Read the live camera frustum and build the projection from it**, then log `live=1` and your config
   side by side. Do not evaluate hook candidates before this.
3. **Hook the main-target scene render call's return** with a transparent thunk, and draw immediately
   after, with your own Z clears suppressed.
4. **Prove occlusion with a walk-behind-a-hill clip at 60 fps**, and state plainly if you have no
   reference frame for the same shot on the other side.

## Sources

These are files in the project's own repository, which isn't public; the paths are kept for its author.

- `docs/kb/RENDERING_PATTERNS.md` sections 1-3, 6, 9 (overlay vs scene, frustum parity, the post-world
  window, blend/order, matrix order).
- `docs/kb/ENGINE_FNV.md` sections 2.2-2.6 (the call-site map, the four render sites, the post-world
  draw, the hooking rules, the banned site) and section 3 (depth and frustum).
- `docs/kb/GOTCHAS.md` C3, C4, C5 and S3.
- `docs/MILESTONES.md` M7 (the call-site map) and M8 (occlusion landed).
- `docs/WARTHOG_INSCENE_HOOK_CALLSITES.md`, `docs/PLAN_3P_SCENE_DRAW.md`, `docs/CAMERA_OWNERSHIP.md`.
