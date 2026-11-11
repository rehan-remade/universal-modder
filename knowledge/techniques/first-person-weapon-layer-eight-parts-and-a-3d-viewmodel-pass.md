---
kind: technique
title: "A first-person weapon layer for a game that has none: the eight parts, and drawing a 3D viewmodel in EndScene (D3D9) or Present (D3D11)"
tags: [fps, first-person, viewmodel, d3d9, d3d11, endscene, present-hook, depth-buffer, lighting, projectiles, vtable-copy, offline-test-host, oracle]
date: 2026-11-11
agents: ["Claude Code (Opus 5.5)", "OpenCode (models not recorded)"]
humans: ["Arekosandoru"]
links: ["knowledge/games/gothic-3/firearms-3d-viewmodel-and-engine-projectiles.md", "knowledge/games/total-war-warhammer-iii/first-person-soldier-view-native-camera-and-ca-weapons.md", "knowledge/techniques/hooking-a-host-post-world-render-pass-so-the-world-occludes-your-overlay.md", "knowledge/techniques/geometry-transfer-host-draws-guest-meshes.md"]
---

# A first-person weapon layer for a game that has none: the eight parts, and drawing a 3D viewmodel in EndScene (D3D9) or Present (D3D11)

> We added shooter-style first person with guns to two very different games: Gothic 3 (Genome, D3D9, x86) and
> Total War: WARHAMMER III (Warscape, D3D11, x64). Both ended up with the same eight parts. In both, the weapon
> on screen is our own 3D mesh drawn at the end of the frame, and every shot goes through the engine's own
> projectile code. This note is the reusable part: what to build, in which order, and the rendering details that
> made the gun look like it belongs in the scene. Both mods are verified in game; game-specific details are in
> the two game notes linked above.

## When to use it
- The game has a player or units with weapons, but no first-person shooting, or only a crude one.
- You can run native code in the process: a script DLL folder, a Lua `package.loadlib`, a plugin SDK, or a
  loader the game already supports.
- You want the gun on screen to be a real 3D model that lines up with the crosshair from any angle. A 2D sprite
  can only match the crosshair on the picture itself.

## How

### 1. The eight parts (build them in this order)
| # | Part | What it gives | How we did it |
|---|---|---|---|
| 1 | **Door** | our code inside the process | Gothic 3: the game loads every `scripts\Script_*.dll`. WH3: battle Lua `package.loadlib`. |
| 2 | **Camera** | the view from the eyes | Gothic 3: the game's own first-person mode (`SetMode`). WH3: our camera object, re-installed as the active camera every frame. |
| 3 | **Input** | mouse look and fire | Raw Input or a low-level mouse hook for buttons; `GetAsyncKeyState` for keys; stop the game acting on the same button (see the rules below). |
| 4 | **Carrier** | what stands where the camera is | Gothic 3: the hero. WH3: a soldier of the selected unit; on 9.0.5 the hero stays put and the camera moves. |
| 5 | **Viewmodel** | the gun in frame | our own 3D pass at the end of the frame (section 2). |
| 6 | **Ballistics** | shots that hurt | the engine's own projectile, spawned or launched from our code. Never our own physics. |
| 7 | **Content** | more guns | a table of weapons: model, placement, recoil, rate, projectile, sound. |
| 8 | **Survival** | doesn't crash after a patch | check the exe build at load, gate hooks on a vtable check, log `MISMATCH`, stay inactive. |

Rules:
- **Ask the engine first.** If it already has a first-person or aiming camera, part 2 is free; spend the
  effort on 5 and 6.
- **Never write your own ballistics.** In both games our own projectile flew and hit nothing. Hits, damage,
  deaths, XP and kill counters all live in the engine's pipeline. Read how the player's own shot is made,
  then repeat that recipe from your code (Gothic 3: spawn ammo template → owner → point collision shape in the
  projectile group → physics path → damage on the projectile → `Shoot`). Or call the script API that already
  does it (WH3: `battle:trigger_projectile_launch`).
- **Change data, not code.** A copied vtable with one slot replaced, or a swapped pointer, undoes with one write.
  Inline patches don't.
- **Hook late, release everything on exit.** Install when the level or battle is really running. On exit,
  restore camera, cursor, HUD and input, and release every D3D object you made.
- **Share the button with the game deliberately.** If the player's LMB fires your gun, the game is also reading
  that LMB. Find the game's handler (Gothic 3: the script function `OnPlayerAction`) and skip it while your gun
  is out. Otherwise the hero also swings a sword, loots a corpse or starts a conversation.

### 2. Drawing the viewmodel
Common to D3D9 and D3D11:
- **Draw into the final frame only.** Gothic 3's `EndScene` fires three times per frame, for an HDR scene target,
  an 8-bit intermediate and the final target. Check the render target's size and format against the back buffer
  and draw only into that one. WH3 `Present` is called once, on the back buffer.
- **Use your own depth buffer; never touch the game's.** Clearing the game's depth inside its HDR pass made
  world items show through walls. A private depth surface the size of the back buffer, cleared every time you
  draw, lets the gun self-occlude correctly and never disturbs the scene.
- **Use your own projection.** A viewmodel wants its own FOV (we used 55° vertical) and a near plane of about 1 cm,
  so the gun doesn't clip into the camera or stretch at wide FOVs. You don't need the game's view matrix for the
  gun itself, only for things placed in the world (tracers): in Gothic 3 that comes from the engine's own
  accessor, because `D3DTS_VIEW` inside `EndScene` isn't the game camera.
- **Save and restore all device state.** D3D9: capture a `D3DSBT_ALL` state block before drawing and apply it
  after. D3D11: save and restore the render targets, viewport, shaders, input layout, blend, depth and raster
  states you change.
- **Handle device loss and resize.** D3D9: release your default-pool resources in a `Reset` hook and recreate
  them afterwards. D3D11: create the render target view and depth buffer when the mode is entered and release
  them on exit. Our WH3 mod still doesn't handle a resize while active; plan for it.
- **Match the scene's light cheaply.** Every 0.15 s (the readback stalls the GPU, so not every frame), and
  before drawing the gun, `StretchRect` the finished frame into a 32 × 16
  render target, `GetRenderTargetData` it into system memory, and average it in linear space to get the scene's
  brightness and tint. Scale the gun's ambient and diffuse by that, smoothed over time. This was enough for
  night, caves and torchlight in Gothic 3; without it, a daylight-lit gun glows in a dark cave.
- **Effects in the same pass.** Muzzle flash and ejected cases are drawn after the gun, with the same depth
  buffer, so the gun correctly hides part of the flash.
- **Gate the pass.** Draw only while your mode is on and the game is actually in play: no menus, dialogue
  cameras, inventory pages or loading screens.

### 3. Getting to the device (D3D11)
Find an engine object that holds the swapchain (WH3: the renderer). `QueryInterface` it for `IDXGISwapChain`,
replace `Present` in a **copy** of its vtable, and from inside `Present` call `GetDevice` and `GetBuffer(0)`.
Don't scan memory for the swapchain, which hung the game. Take IIDs from the Windows Kits headers: one mistyped
GUID returned `E_NOINTERFACE`, which looks exactly like the engine blocking D3D.

### 4. Models
- Keep the format trivial: positions, normals, UVs, bone indices and weights, a bone list with bind matrices,
  named attach points (`muzzle`, `eject`), one optional clip (`fire`), and a texture path. Write it with a Python
  packer; the C++ loader stays a few hundred lines, and a pytest checks the packer against the loader's struct
  sizes.
- Convert the axes once, in the packer. Gothic 3 is left-handed, Y-up, in centimetres, so glTF needs X negated
  and the triangle winding flipped. Even so, check each donor's forward axis by eye: our revolver and AK came
  from different sources and pointed opposite ways.
- Using the game's own weapon meshes (WH3: RMV2 from the player's install) gives a gun that matches the game's
  look perfectly. Generate those files on the player's machine and never ship them.

### 5. Test without the game
Build the same renderer code into a small standalone exe (D3D9 HAL, or D3D11 on WARP) that loads the model,
applies a placement, and writes a PNG or PPM. In one command it shows placement, scale, lighting, animation
frames and the muzzle-flash position, without the minutes a game launch costs. We used it for every placement
change; the game was launched only to confirm a batch.

## Gotchas
1. **The overlay shows world items through walls.** **Cause:** we cleared or reused the game's depth buffer
   during one of its intermediate passes. **Fix:** private depth buffer; draw only into the final target.
2. **The gun is drawn twice, or squashed.** **Cause:** `EndScene` runs for offscreen and intermediate targets
   too. **Fix:** compare the bound render target with the back buffer (size and format) before drawing.
3. **Tracers and world-space effects drift away from the bullet.** **Cause:** `D3DTS_VIEW` inside `EndScene`
   isn't the game camera. **Fix:** get the view matrix from the engine.
4. **The gun glows in the dark.** **Cause:** fixed lighting. **Fix:** sample the finished frame's brightness
   (above).
5. **A "D3D is blocked" conclusion.** **Cause:** a wrong IID. **Fix:** copy IIDs from SDK headers and log every
   step's HRESULT (`QI`, `GetDevice`, `GetBuffer`, `RTV`) in one line.
6. **The player's click also makes the game act.** **Cause:** the game reads the same button. **Fix:** suppress
   the game's handler for that button while your weapon is out, at the script level when possible.
7. **Bullets fly but never hurt.** **Cause:** your own projectile lacks whatever the engine uses for hits (a
   collision shape, a damage component, a projectile DB row). **Fix:** reproduce the engine's own shot exactly,
   or call its launch API.
8. **A 2D sprite of the gun never looks right.** **Cause:** a sprite can line the barrel up with the crosshair
   only on the picture; from the side it visibly points elsewhere. **Fix:**
   use a real 3D model.

## Seen in
- [Gothic 3 firearms](../games/gothic-3/firearms-3d-viewmodel-and-engine-projectiles.md): D3D9 `EndScene`,
  three per-frame targets, frame-sampled lighting, script-level input suppression, engine projectile recipe.
- [Warhammer III first-person view](../games/total-war-warhammer-iii/first-person-soldier-view-native-camera-and-ca-weapons.md):
  D3D11 `Present` through a vtable copy, the game's own weapon meshes, `trigger_projectile_launch`, WARP host.
- Related: [hooking a post-world render pass](hooking-a-host-post-world-render-pass-so-the-world-occludes-your-overlay.md)
  covers the opposite need, where the world should hide your geometry. A first-person gun is drawn after
  everything and only needs its own depth.
