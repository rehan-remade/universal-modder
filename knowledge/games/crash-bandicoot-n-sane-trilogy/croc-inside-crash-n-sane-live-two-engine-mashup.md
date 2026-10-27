---
kind: game
title: 'Croc inside Crash N. Sane: live two-engine mashup and native port'
game: Crash Bandicoot N. Sane Trilogy
games_also: ["Croc: Legend of the Gobbos (2025 remaster)"]
game_version: 'Steam 731490, exe PE timestamp 2018-07-19 (sha256 170c61d3...6af3); Croc remaster GOG 1152820153 build 58936832420733913'
platform: windows
engine: native
route: passthrough
tools: ["ReShade 6.8.0 add-on build", "Ultimate ASI Loader v9.7.4 (version.dll, Croc)", "MSVC 14.44", "capstone", "pefile"]
anti_cheat: none (Crash exe is SteamStub-wrapped; only the running process was hooked)
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-10'
links: []
tags: [alchemy-engine, mashup, passthrough, frame-compositing, reshade-addon, d3d11, d3d12, depth-compositing, render-hijack, input-forwarding, character-controller, hardware-breakpoint]
---
# Croc inside Crash N. Sane: live two-engine mashup and native port

> The real Croc (Croc remaster, D3D12) runs as a second process. His engine draws only Croc, through Crash's
> camera, and the picture is depth-composited into Crash's frame (D3D11) with Crash hidden.
> - **Stage A:** Crash's physics move the player and Croc mirrors his run, jump and spin.
> - **Stage B:** Croc's own physics (run, acceleration, tank turning, jump arc) drive Crash's character
>   controller. Crash keeps collision response, crates, enemies, lives and camera.
> - **Evidence:** verified in game with screenshots and recordings (run, jump onto the Aku Aku crate, spin
>   breaking crates, pit death and respawn, game over and retry, pause).

## Setup
- **Games:** both are the user's own copies. Crash Bandicoot N. Sane Trilogy from Steam (its exe is
  SteamStub-wrapped and is never modified on disk). Croc is the 2025 remaster, *Croc: Legend of the Gobbos*
  from GOG (DRM-free, released 2 April 2025; also on consoles). The 1997 PC original isn't sold any more and
  isn't needed: everything Croc-side comes from the remaster's own install (`remaster/` and `gdata/`).
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
- **Related:** Stage A is the frame-compositing route (`techniques/frame-compositing-depth-and-pose-sync.md`;
  the other ReShade add-on compositor is `games/gta-v/minecraft-passthrough.md`). Stage B's split (Croc owns
  movement, Crash owns collision, lives and camera, and takes the player back on death) is an ownership choice
  of the kind `techniques/bridge-contracts-ownership-units-and-lifecycle.md` asks you to write down. The native
  port is Pattern 1 in `skills/mashup-mods/SKILL.md`: the guest's assets converted from the user's install.

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
- **Depth:** Croc's depth target is reached through D3D12 render passes (ReShade's `begin_render_pass` event,
  not `bind_render_targets_and_depth_stencil`). Format R32_TYPELESS (39 → decode as float).
- **Player struct:** `[Croc64.exe+0xB26800]`. Fixed point 1/4096: x @+0x7B0, y @+0x7B4 (Y down), z @+0x7B8,
  previous position @+0x7C8.
  - The float at exe+0xA79AF8 only mirrors the camera target: a setter at exe+0x1CC740 is called from
    camera code.
  - Found with an in-process hardware write-watch and disassembly of the exe on disk.

## Build steps
1. Install as in Setup. Build both add-ons with MSVC (`/std:c++17 /we4129`, ReShade 6.8.0 headers).
2. Start Croc into a level, then Crash into a level (scripted with WinDrive; both games' menus need scan
   codes, and Crash's menus need *held* keys). The quick boot in the
   [uncapped FPS note](uncapped-fps-and-live-boss-powers.md) skips Crash's intros without any input; pressing
   Enter through them once loaded a save (its gotcha 9).
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
- **Not verified (live mashup; the native port's checks are at the end of its section):**
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
    `exe+0x1a59210 == 0` (see Death state). Latch on the alive → 0 edge; end on the flag going alive or on a
    horizontal respawn teleport, not on losing the player capsule (it vanishes during enemy deaths). Verified on
    pit, TNT and enemy (crab) deaths: Crash's own death animations play.
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
- **Choice:** Croc is a third hero on the game's own swap (see "Hero swap" below); the choice is saved in the
  add-on's ini.
- **Cache location:** the converter writes the rig into a local cache next to the mod, not
  `%LOCALAPPDATA%`; sandboxed writes there may be virtualised. The cache is converted Croc data: keep it out
  of any repository and don't share it.
- **Camera when the scene pass gives none** (Crash 1's Cortex boss, sparse map views): derive it from Crash's
  own skinned buffer. VP = World⁻¹ · WVP of the 4016-byte player buffer. In normal levels it equals the scene
  camera exactly, so use it only as a fallback. Also accept a lone camera candidate written ≥ 3 times/frame,
  and views up to 1000 units away (the airship node on the island map).
- **Mounts** (Hog Wild's hog): other models drawn centred under the player, about 100/s while riding and 0
  otherwise. While mounted, loop the guest's balancing clip instead of letting the bobbing trigger jump and
  land clips.
- **Croc's moveset only:**
  - Crash reads keyboard and mouse through user32, not DirectInput: its DirectInput object only serves pads,
    and no raw input is registered. So hook `GetKeyboardState`, `GetKeyState` and `XInputGetState` in the
    running process's import table (the exe on disk stays untouched), and subclass the game window.
  - **Hide Crash-only moves:** crouch/slide/body slam (right mouse; pad B and RT), Speed Shoes (Shift),
    bazooka (Q), the air spin, and the Crash 3 double jump.
  - **Croc's stomp:** a second jump in the air presses Crash's slide button for 150 ms. The engine's body
    slam then breaks what's below and shows the impact dust.
  - **Edges:** take key edges from `GetAsyncKeyState`. The game's own sources disagree for a few ms and
    create fake re-presses.
- **Vehicle levels** (Crash 3's biplane and motorbike):
  - **Detection:** no on-foot capsule or controller body exists, and the level-state flag reads 0 for the whole
    level. Key vehicle mode on the area archive's name (below): the pilot waits still behind the start line,
    so "the model keeps moving" never fires there, and his still bones read as a pause.
  - **What sits at the player:** three groups of draw: Crash's body (4016-byte buffer), his pilot outfit
    (other buffers, another vertex shader) and the vehicle (one vertex shader with the most draws there).
  - **What to hide:** everything at the player except the vehicle's shader. Croc then sits in the cockpit, and
    the pause preview shows it too.
  - **The vehicle's shader also draws the pilot's outfit** (the motorbike's ears, fur collar and gloves; the
    biplane's scarf, goggles and cap). Hide it by the index counts of `CrashBiker.igz` / `CrashAviator.igz`;
    Crash's on-foot body meshes use the same counts in every vehicle.
  - **Plane deaths:** the parachute pack mesh on the pilot's back is also the canopy once the parachute opens:
    hide it only while flying. The game keeps the body's World where the plane was hit and moves the body with
    its skinning matrices, so Croc isn't placed under the canopy yet; the parachute comes down empty.
- **Which area is loaded:** patch the running exe's `CreateFileW`/`CreateFileA` import entries (the file on
  disk stays untouched) and note the area archive it opens (`l100_hub.pak`, `l200_hub.pak`, `l300_hub.pak`,
  `l322_orangeasphalt.pak` ..., in lower case). The `*_hub` archives are the level-select screens. The archives
  also tell which levels are vehicle levels (`CrashBiker`/`CrashAviator` actors) and which are Coco-only (Crash 3
  tiger and jet-ski levels). The same hook drives
  [uncapped FPS and live boss powers](uncapped-fps-and-live-boss-powers.md).
- **Hero swap (Crash → Coco → Croc):**
  - The game swaps Crash and Coco with R2 (keyboard Ctrl) on Crash 1's island map and the Crash 2/3 warp rooms,
    once Coco is unlocked. The hero crouches and spins up in a swirl, and the other one drops in (about 1 s).
  - **Telling Crash from Coco:** a memory scan across swaps found only per-game heap flags, with no static path
    shared by the three games. The meshes drawn at the player work instead: their index counts are the same in
    all three games (Crash 22461, 9528, 5694, 4092; Coco 18288, 10614, 10404, 8256).
  - **Coco → Croc:** let the game swap back to Crash, hide the Crash who drops in (his meshes by index count,
    wherever drawn: he falls in from above, away from the player position) and draw Croc in his place.
  - **Croc → Crash:** Croc stays where he stood while the game swaps to Coco, who stays hidden. The add-on
    presses the swap again until the game takes it (about 1 s later, once Coco has landed), and Croc spins out
    upwards as Crash drops in. Press with the device the player used (Ctrl, or R2 in `XInputGetState`).
  - **No Coco yet** (no hero badge on screen): the press swaps Crash and Croc directly, with the spin effect.
  - Croc only stands in for Crash: while the game's hero is Coco, she is shown.
  - The island map draws the hero 1.4× larger (read the scale from the World matrix), and the level node under
    him uses a 1488-byte buffer: don't hide it.
- **Croc's face on the HUD:**
  - The hero icons are standalone BC3 textures:
    - the swap badge: `ui/Crash/HUD/Crash_Head1`, `Coco_head1` and their `_Glow` (stored upside down);
    - the lives counter: `ui/Crash/crashtoken` plus its line layer `crashtoken2`, used by
      `vfx/UI/Crash_Life_GUI`;
    - Crash 3's level card: a cell of `Boss_Portraits/character_sheet_filmstrip`, drawn in the scene pass;
    - the biplane health bar: `PilotHUD/Pilot-Crash-Portrait-2`;
    - Crash 3's pause screen: a Crash & Coco sticker painted on the left panel (`Pause/Crash3/BG_Left`). Its
      stand-in is that panel with the sticker painted out and a Croc sticker on it.
  - A script hashes their 16×16 centre blocks from the user's archives. It builds Croc's stand-ins from his own
    remaster lives icon (`remaster/ui/panel/croclife.tga`), outlined in black and framed like each original,
    into the local cache.
  - At runtime each texture bound to pixel-shader slot 0 is recognised once (by size, then a GPU read-back of
    the same blocks), and the stand-in is bound in its place for that draw. The badge's small face is the next
    hero: when Croc plays, Coco's head shows Crash.
- **Crash's props and effects around Croc:**
  - Crash's idle "timeout" animations (yo-yo, fruit juggling, a spin), his spin (hands swirl, Death Tornado ring)
    and the super body slam bring their own models and particles. They aren't part of the player draw, so hide
    them separately.
  - **Models by index count:** an IGZ model's `igIndexBuffer` objects hold the index count at +0x10, so the
    counts of every Crash prop can be read from the archives. Hide each group only in its moment and near the
    player, so scenery sharing a count stays.
  - **Particles by texture:** their vertex counts change every frame, and they're drawn in later passes. Follow
    Crash's effect files (`vfx/Characters/Playable/Crash/Crash_Attack_*`, `Crash_Timeout_*`) to their textures,
    hash those, and hide draws that sample them right after an attack or stomp, or after a long idle.
  - One idle draws Crash's whole body again in a later pass (a fruit-goo overlay): hide his body meshes near the
    player in every pass, not only the G-buffer pass.
  - **Finding them:** learn every draw signature (count, vertex shader, texture) in normal play and log the ones
    that appear only after an attack, a stomp or a long idle. Read texture info at draw time: a view saved for
    later may already be freed (that crashed the game once).
  - **Mount detection** must count only mount meshes (hog, jet-board, polar bear): crates and platforms under
    the player otherwise switch Croc into his riding pose.
  - **Death Tornado:** hold back a second attack press within 0.9 s; Crash chains spins into the tornado.
- **Test tooling:** `um win drive "idle N"` doesn't wait; it reports seconds since the last input. For timed
  combos, put the whole combo in one drive call: separate calls are too slow, because each one starts
  PowerShell. Pauses inside a call need the `sleep <ms>` verb from #206; without it, use `hold <vk> <ms>` or
  drive `um.win.Drive` from Python with `time.sleep` between commands.
- **Verified with the user's completed saves:**
  - Crash 1: the island map, the Cortex boss, Upstream (water), Hog Wild and The Great Hall.
  - Crash 2: the warp room and Hang Eight on foot.
  - Crash 3: the warp room, Flaming Passion, Orange Asphalt (motorbike) and Mad Bombers (biplane).
  - The swap: the full cycle in Crash 1's map and Crash 3's warp room; Crash ↔ Croc in Crash 2's warp room
    (Coco not unlocked in that save).

## Assets
None generated. Croc is drawn by his own engine from the user's install; nothing from either game is
redistributed.

## Cost and time
About a day and a half of agent time over four sessions, with the human mostly away.

## Open questions
- **Native port follow-ups:** Crash 2's jet-board and polar rides, Coco-only levels, bonus rounds, plane-level
  deaths, gamepad verification with a real controller (the R2 swap included), user rebinding support.
- **Remaining issues (live mashup):**
  - pose lag of 1–3 frames during fast camera moves (reproject).
