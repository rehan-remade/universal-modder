---
kind: game
title: 'Croc inside Crash N. Sane: live two-engine mashup'
game: Crash Bandicoot N. Sane Trilogy
games_also: [Croc Legend of the Gobbos (2025 remaster)]
game_version: 'Steam 731490, exe PE timestamp 2018-07-19 (sha256 170c61d3...6af3); Croc remaster GOG 1152820153 build 58936832420733913'
platform: windows
engine: native
route: passthrough
tools: [ReShade 6.8.0 add-on build, Ultimate ASI Loader v9.7.4 (version.dll, Croc), MSVC 14.44, capstone, pefile]
anti_cheat: none (Crash exe is SteamStub-wrapped; only the running process was hooked)
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-09'
links: []
tags: [alchemy-engine, mashup, passthrough, frame-compositing, reshade-addon, d3d11, d3d12, depth-compositing, render-hijack, input-forwarding, character-controller, hardware-breakpoint]
---
# Croc inside Crash N. Sane: live two-engine mashup

> The real Croc (Croc remaster, D3D12) runs as a second process. His engine draws only Croc, through Crash's
> camera, and the picture is depth-composited into Crash's frame (D3D11) with Crash hidden.
> - **Stage A:** Crash's physics move the player and Croc mirrors his run, jump and spin.
> - **Stage B:** Croc's own physics (run, acceleration, tank turning, jump arc) drive Crash's character
>   controller. Crash keeps collision response, crates, enemies, lives and camera.
> - **Evidence:** verified in game with screenshots and recordings (run, jump onto the Aku Aku crate, spin
>   breaking crates, pit death and respawn, game over and retry, pause).

## Setup
- **Install:**
  - Crash: ReShade64.dll as `d3d11.dll` (Crash imports d3d11 directly).
  - Croc: ReShade as `ReShade64.asi`, loaded by the Ultimate ASI Loader installed as `version.dll`.
  - A `dxgi.dll` proxy is ignored by Croc: it loads dxgi/d3d12 with a System32-only search, but its static
    imports aren't restricted.
- **Add-ons load from a folder outside the game:** each `ReShade.ini` sets `[ADDON] AddonPath`, so rebuilds
  never touch game folders (a running game locks its add-on: LNK1104).
- **Croc settings:**
  - Windowed 1280×720 so a frame fits the shared slot.
  - MSAA Off (in-game Display Setup): a multisampled depth can't be copied.
- **Crash settings:** Keyboard Controls → Attack second key = F (see Gotchas). Borderless windowed is forced
  by the host add-on.

## Route and why
- **Taken:** passthrough with a render hijack, i.e. frame compositing plus state exchange in both directions.
- **Considered and deferred:** a native port (Croc model, animations and moveset rebuilt in Crash's .igz
  data). It's the better shippable product, and the live bridge is now its measuring tool. The user chose
  "both games running live".
- **Not used:** a whole-frame overlay of Croc's own level. It looks pasted on; skipping every non-Croc draw
  gives a clean character layer with true depth.

## How the game works (what we had to learn)
**Crash (Alchemy, D3D11)**
- **Per-view constant buffer:**
  - World vertex shaders read `SceneGeometryConstants` (400 B, VS slot 0): `ig_matrix_model` @0,
    `ig_matrix_viewproj` @64 (row-vector), `ig_matrix_viewproj_previous` @128.
  - The game re-maps it per draw, so the camera VP is the perspective matrix written about 165 times per
    frame at +64 of 400-byte buffers.
  - The names come from the main scene VS's reflection data.
- **Units:** render units are inches; render = collision units × 39.3701 (Crash's blob shadow sits exactly
  there).
- **Depth:**
  - World geometry is drawn with viewport depth range [0, 0.8]; far layers use 0.8–1.
  - The scene depth is R24G8 at back-buffer size. Pick it by aspect ratio, not draw count: the 4096×16384 R16
    shadow atlas has more draws.
- **Player position:**
  - The collision-capsule array `[exe+0x1A5C160]` region and `[exe+0x1A5C158]+0x38` (0x90 stride) is
    rebuilt every frame from entity transforms. The player's slot moves and can go stale after respawn; the
    rendered body (4016-byte skinned buffer, World @64 ÷ 39.37) is reliable.
  - The authoritative, writable position is the character-controller body at `[exe+0x1A5C160]+0xE0 → +0x80`
    (float3, collision units). It was found by a displacement diff scan plus live write tests.
- **Pause:** detected as "bone data in the 4016-byte buffer unchanged for 6 frames".
- **Death state:**
  - The int32 at `exe+0x1a59210` reads 2 while Crash is alive and under control, and 0 from about 0.4 s into a
    death until the respawn teleport (also on the game-over screen). Jump, spin and pause don't change it.
  - It's static, so it survives level reloads.
  - Found by sampling the module's writable data through pit deaths and filtering against no-death runs.
  - The lives counter is a heap int that changes too late (about 1.5 s after the death starts) and moves on
    every retry.
  - Use it to hand back: show Crash, don't composite the guest, and stop writing the body.

**Croc remaster (Argonaut/Titanium engine, D3D12)**
- **Draws:** about 280 indexed draws per frame, each with one 512-byte root CBV in persistently mapped upload
  memory. @0 is world·view·proj (row-vector), @64 is world, @480 is the projection.
  - Croc's body parts are the draws whose world translation sits at the player.
  - Rewriting @0 at draw time (world × Croc→Crash mapping × Crash VP) and skipping other perspective draws
    renders only Croc, seen through Crash's camera.
- **Depth:** Croc's depth target is reached through D3D12 render passes (`begin_render_pass`, not
  bind_render_targets). Format R32_TYPELESS (39 → decode as float).
- **Player struct:** `[Croc64.exe+0xB26800]`. Fixed point 1/4096: x @+0x7B0, y @+0x7B4 (Y down), z @+0x7B8,
  previous position @+0x7C8.
  - The float at exe+0xA79AF8 only mirrors the camera target: a setter at exe+0x1CC740 is called from
    camera code.
  - Found with an in-process hardware write-watch and disassembly of the exe on disk.

## Build steps
1. Install as in Setup. Build both add-ons with MSVC (`/std:c++17 /we4129`, ReShade 6.8.0 headers).
2. Start Croc into a level, then Crash into a level (scripted with WinDrive; both games' menus need scan
   codes, and Crash's menus need *held* keys).
3. **Stage A:** Croc's frame plus depth go through 3 seqlocked shared-memory slots at about 30 Hz (D3D12
   readback with a fence, never waiting). The Crash pixel shader shows Croc where his depth is less than 1 and
   0.8·z ≤ Crash depth. Crash's own model draws are skipped while a fresh Croc frame exists.
4. **Stage B:**
   - Crash's input is blocked (ReShade `block_input_next_frame`) and the keys are read with
     `runtime->is_key_down`, then posted to Croc's window.
   - Croc is pinned each tick and his own displacement is published. The host rotates and scales it (one
     fixed rotation phi, × 14.4) into Crash's controller body; airborne height × 14.4 goes into z.

## Verification
- **Oracles:** screenshots read back after every change (ReShade's own screenshots while exclusive
  fullscreen), recordings tiled into frame grids, per-second logs on both sides, and the depth error of the
  camera candidate against the real depth buffer (≈ 0.001).
- **Seen working:** occlusion behind crates, walking, jumps, a spin breaking crates, Aku Aku pickup, pit death
  and respawn, game over and retry, pause.
- **Not verified:**
  - vehicle and riding levels and bosses;
  - other levels' camera behaviour, beyond Jungle Rollers and the Crash 2 warp room;
  - long play sessions;
  - Proton.

## Gotchas
1. **Croc's `dxgi.dll` proxy never loads.** **Cause:** Croc loads dxgi/d3d12 from System32 only.
   **Fix:** load ReShade through an ASI loader installed as `version.dll`, a static import.
2. **The first camera lock was wrong but tracked the player on screen.** **Cause:** an object/model matrix
   with a unit column. **Fix:** validate candidates against the real depth buffer, then use the structural
   source (most-written VP at +64 of 400-byte buffers).
3. **The depth test failed everywhere.** **Cause:** Crash draws the world with viewport depth [0, 0.8].
   **Fix:** stored depth = 0.8 · ndc_z, i.e. read the viewport most scene draws use.
4. **Crash exits on Alt+Enter after adding an overlay.** **Cause:** our back-buffer RTV and a context-state
   binding kept a reference, so ResizeBuffers failed with INVALID_CALL. **Fix:** release both every present.
5. **Crash froze on a black screen at startup with borderless.** **Cause:** SetWindowPos called from the
   present path, where the render thread waited on the window thread. **Fix:** do window changes on a worker
   thread.
6. **Croc pauses whenever Crash has focus.** **Fix:** subclass Croc's window and swallow
   WM_ACTIVATE(inactive), WM_ACTIVATEAPP(0), WM_KILLFOCUS and WM_NCACTIVATE(0).
7. **Croc's whole frame painted over Crash.** **Cause:** R32 depth decoded as D24. **Fix:** treat format 39 as
   float.
8. **Croc rendered dark at times.** **Cause:** his vertex lighting comes from where he stands in his own
   level. **Fix:** pin him on his lit spawn spot.
9. **Writing the obvious position copies does nothing.** **Cause:** capsule records and skeleton roots are
   rebuilt from the controller each frame. **Fix:** a diff scan by the exact displacement (m and in), then a
   live write test against the rendered position (`findmover`).
10. **Stage B keys read as 0.** **Cause:** ReShade's input block also hides GetAsyncKeyState inside the game
    process. **Fix:** `effect_runtime::is_key_down`.
11. **Menus stuck in Stage B.** **Cause:** the input block also blocked menus and game over. **Fix:** block
    only in a live level that isn't frozen; unblock-and-resend Esc.
12. **Attack never reached Crash while blocked.** **Cause:** buffered DirectInput drops presses made while
    blocked, and borderless Crash ignored synthetic clicks. **Fix:** bind F as Crash's second Attack key,
    unblock for 14 frames on the attack edge and SendInput F.
13. **Write AV crash during a level load.** **Cause:** Stage B applying idle drift through a stale pointer
    chain. **Fix:** write only with a live camera, a body near the player and real movement.
14. **Ini paths silently broken.** **Cause:** heredocs/scripted edits collapsed `\\` in `L"..."` paths into
    `\m`, `\c`. **Fix:** `/we4129` makes unknown escapes errors.
15. **Hardware write-watch crashed the game after disarm.** **Cause:** a late DR0 hit was passed on as
    unhandled. **Fix:** the VEH always absorbs its own hits and clears DR7.
16. **The screenshot oracle lied twice.** **Cause:** window capture freezes in exclusive fullscreen; a 1 s
    capture start misses a 0.4 s spin; an injected PrintScreen with Ctrl held is not ReShade's key.
    **Fix:** ReShade screenshots or short recordings tiled into frames.

17. **Croc slid and drifted in Stage B.** **Cause:** his level (2-4) is ice, so his real physics slide.
    **Fix:** run him in a grass level (1-1); also apply his motion only while a move key is held (+0.6 s coast)
    or while airborne.
18. **Remastered Croc rendered pale blue.** **Cause:** with the Croc → Crash matrix, clip w was in Crash inches,
    so his shaders' distance fog saw him as far away. **Fix:** scale the whole matrix by 1/k; x/w, y/w and z/w
    are unchanged.
19. **Croc stayed bright over Crash's black death fade.** **Fix:** average the finished back buffer (mipmapped
    copy, 1×1 mip) and scale Croc by luminance / 0.2.
20. **"Croc ignores arrows after respawn".** **Cause:** tank controls; Left/Right turn on the spot. Not a bug.
21. **Crash's death played with nobody on screen** (Crash hidden, Croc standing idle). **Fix:** hand back while
    `exe+0x1a59210 == 0` (see Death state). Verified on pit, TNT and enemy (crab) deaths: Crash's own death animations play. Latch on the alive → 0 edge; end on the flag going alive or on a horizontal respawn teleport, not on losing the player capsule (it vanishes during enemy deaths).
22. **Croc drawn over the HUD.** **Fix:** composite into Crash's intermediate final texture at the first draw
    that has no depth target bound (the HUD pass), not at present.
23. **The pause menu's level preview showed only Crash's shadow.** **Cause:** the preview is a still: a separate
    3840×2160 render target, captured when the pause begins and sampled by the pause frame's first no-depth
    quad into the back buffer. **Fix:** while paused, composite the guest once into that texture, reusing the
    last live frame's composite settings. Find it by logging the PS t0 of each back-buffer draw.
24. **Crash's silhouette shadow stayed under Croc.** **Cause:** the shadow passes (R16 depth targets) bind no
    object buffer near the player, so the main-pass "is this the player" test never matches. **Fix:** remember
    the geometry of the draws hidden in the main pass (index buffer, index count, first index, base vertex)
    and skip identical draws in the shadow passes. Give the guest a contact shadow of its own: a screen-space
    ellipse from the projected ground ring, depth-gated against the scene, kept on the ground during jumps.
25. **The island map ignored the arrow keys.** **Cause:** a "player + camera present" test also passes on the
    map, so the host kept blocking Crash's input. **Fix:** block and forward input only after a few consecutive
    frames in which the guest's motion actually drove a sane level body. Level changes then work with no
    restart (verified Jungle Rollers → map → N. Sanity Beach).
26. **After some respawns no capsule has the player's shape.** **Fix:** fall back to the rendered model when the
    character-controller body agrees with it.

## Native port: Croc as an extra character, no Croc process (2026-10-10)
After the live mashup, the user wanted Croc native: an extra character with his real model, animations,
feel and attacks.
- **No `.igz` authoring:** there's no public tool to author a new skinned `.igz` model, and character
  behaviour is code in the exe.
- **Instead**, the same ReShade add-on draws a converted Croc rig at Crash's player draw, and Crash's own
  controller moves him.

**Croc remaster formats** (from Croc64.exe's loader and its shipped shaders):
- **ZMOD** (`remaster/models/hd/*.zmod`): objects; each has sub-meshes {name = atlas id, index count, first
  index, AABB}, a vertex block, u32 indices, then a morph binding or 0 (static).
  - Morph objects: UNORM16 UVs, per-vertex (first, count) influence ranges, then per influence a cage index
    and three float weights (position, tangent U, tangent V), stored as separate arrays.
  - Static objects: 24-byte vertices {float3, packed normal, UNORM16 uv, rgba}.
- **Deformation** (decompiled from `gdata/shaders/DIRECT3D12/morph_gpu_hd_obj.vert`, a DXIL container at
  +0x34; `dxc -dumpbin`): `pos = Σ w·P`, `normal = normalize(cross(Σ w_u·P, Σ w_v·P))`, with P lerped between
  two cage frames.
- **ZMOR** (`remaster/anims/*.zmor`): frames × cage verts × float4. Croc's cage is the original 311-vertex
  model.
- **Rigid parts** (eyes, eyelids, arms, backpack): their transforms are in the original `gdata/anims.wad`
  `.ANI`.
  - WAD index lines are `NAME,off,size,unpacked,type`. Type `w` is a word RLE (signed control byte: ≥0
    repeat next u16 c+2 times, <0 copy −c words); `b` is the byte RLE.
  - The last frames × 240 + 4 bytes of an ANI are 10 × int16 {R 3×3 4.12, t/4096} per frame; part k drives
    object k + 1.
- **Textures:** sub-mesh `016` means `remaster/atlases/hd/atlas016.DDS` (BC7); sample at (u, 1 − v).

**Inside Crash:**
- **Deferred G-buffer:** the scene pass is 4 × RGBA8 + D24S8. Layout from Crash's own player pixel shader:
  o0 albedo | pack.r, o1 normal × 0.5 + 0.5 | 0.49, o2 (pack.b, pack.g, emissive, 0.49), o3 (0, 0.5, 0.5, 1).
- **Stencil:** write the G-buffer with Crash's own depth-stencil state and stencil ref, or the lighting pass
  won't shade the pixels.
- **Feel:** Croc's measured run (1.10 u/s), jump (0.319 u, 0.70 s) and acceleration match Crash's
  controller (11.6 u/s, 3.36 u, 0.66 s) within 1–6% at Croc height 1.95 Crash units. So Crash's controller
  moves him: real collision and camera-relative "modern" controls.
- **Proxy velocity is a dead end:** writing it fails; it comes out of Havok's simplex solver.
- **Player draw detection:** recognise the player's draw by geometry signature too, or it fails
  mid-jump/spin.
- **Deaths:** play `crocdie1` and draw Croc at any G-buffer draw while dying.
- **Choice:** F6 switches between Crash and Croc and saves to the add-on's ini.
- **Cache location:** the converter writes the rig into a local cache next to the mod, not
  `%LOCALAPPDATA%`; sandboxed writes there may be virtualised.
- **Camera when the scene pass gives none** (Crash 1's Cortex boss, sparse map views): derive it from Crash's
  own skinned buffer. VP = World⁻¹ · WVP of the 4016-byte player buffer. In normal levels it equals the scene
  camera exactly, so use it only as a fallback. Also accept a lone camera candidate written ≥ 3 times/frame,
  and views up to 1000 units away (the airship node on the island map).
- **Mounts** (Hog Wild's hog): other models drawn centred under the player, about 100/s while riding and 0
  otherwise. While mounted, loop the guest's balancing clip instead of letting the bobbing trigger jump and
  land clips.
- **Croc's moveset only:**
  - Crash reads keyboard and mouse through user32, not DirectInput: its DirectInput object only serves pads,
    and no raw input is registered. So patch the exe's imports `GetKeyboardState`, `GetKeyState` and
    `XInputGetState`, and subclass the game window.
  - **Hide Crash-only moves:** crouch/slide/body slam (right mouse; pad B and RT), Speed Shoes (Shift),
    bazooka (Q), the air spin, and the Crash 3 double jump.
  - **Croc's stomp:** a second jump in the air presses Crash's slide button for 150 ms. The engine's body
    slam then breaks what's below and shows the impact dust.
  - **Edges:** take key edges from `GetAsyncKeyState`. The game's own sources disagree for a few ms and
    create fake re-presses.
- **Test tooling:** `um win drive "idle N"` doesn't wait; it reports seconds since the last input. Use
  `sleep <ms>` inside one drive call for timed combos. Separate drive calls are too slow: each one starts
  PowerShell.
- **Verified with the user's completed saves:** Crash 1's island map, the Cortex boss, Upstream (water) and
  Hog Wild; Crash 2's warp room and Hang Eight on foot.

## Assets
None generated. Croc is drawn by his own engine from the user's install; nothing from either game is
redistributed.

## Cost and time
About one day of agent time over three sessions, with the human mostly away.

## Open questions
- **Native port follow-ups:** a character-select UI (F6 only now), Crash 2/3 vehicles and Coco levels, bonus rounds,
  gamepad filter verification with a real controller, user rebinding support.
- **Remaining issues:**
  - pose lag of 1–3 frames during fast camera moves (reproject);
