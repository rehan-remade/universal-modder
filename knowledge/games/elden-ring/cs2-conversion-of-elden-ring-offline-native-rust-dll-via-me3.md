---
kind: game
title: 'CS2 conversion of Elden Ring offline: native Rust DLL via me3 (fall death, spirit springs, 3D inspect, params)'
game: Elden Ring
games_also: ["Counter-Strike 2"]
game_version: 'Elden Ring 1.17.1 (exe 2.7.1.0, Steam build 25080141, regulation 1.17.1), Steam on Linux (Proton), CS2 install of 2026-10 as the asset source'
platform: proton
engine: fromsoft
route: native-hook
tools: ["me3 0.13.0", "fromsoftware-rs 0.14.0 (eldenring crate, vendored)", "hudhook 0.9.3 (vendored, patched)", "Rust 1.98 + cargo-xwin (x86_64-pc-windows-msvc)", "WitchyBND 3.0.1.0 linux-x64", "Source2Viewer-CLI (VRF) 20.0", "Wine/vkd3d for offline D3D12 + ImGui oracles"]
anti_cheat: "EasyAntiCheat: never touched. me3 launches the game offline with its own profile and a separate save file (ER0000.cs2er.sl2); Steam launch stays the untouched game"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: '2026-10-03'
links: []
tags: [total-conversion, mashup, d3d12-overlay, imgui, regulation-params, msb, fall-death, spirit-springs, movement-controller, skins, case-opening, 3d-inspect]
---
# CS2 conversion of Elden Ring offline: native Rust DLL via me3 (fall death, spirit springs, 3D inspect, params)

> A "play Elden Ring as Counter-Strike 2" conversion: CS2 guns with their real handling, CS2 movement
> (bhop), the CS2 agent in third person, grenades, HUD, buy menu, inventory, cases with Valve's odds, skins
> composited from CS2's own paint kits, a 3D item inspect, the CS2 death screen, and spirit springs on foot.
> It is a native Rust DLL loaded by me3 plus rebuilt regulation params; every CS2 asset is converted from the
> user's own CS2 install at build time and stays local. The user played every feature in the real game; the
> agent read the DLL's own log after each run and used offline D3D12 / ImGui renders under Wine as oracles.

## Setup
- Elden Ring 1.17.1 (exe ProductVersion 2.7.1.0 = fromsoftware-rs's `Ww2710` RVA table), Steam, CachyOS Linux,
  Proton. `um scan` mislabels the game as Unity (an `ERD_ArtbookOST` folder): it is Dantelion native.
- me3 0.13.0 profile: natives = our DLL, package = our `regulation.bin`, `savefile = ER0000.cs2er.sl2`.
  A wrapper launcher renames the user's existing `dinput8.dll` mod loader aside for the session and back after.
- Rust 1.98 + cargo-xwin, MSVC target, static CRT. fromsoftware-rs 0.14 and hudhook 0.9.3 vendored (patched).
- WitchyBND 3.0.1.0 (linux build) for params; it insists on a TTY: run it as `script -qec "WitchyBND --passive <path>" /dev/null`.
- Source2Viewer-CLI (VRF) reads CS2's VPKs: models/clips to glTF, `.vpcf` particles, `.vtex`, `.vsndevts`, panorama.

## Route and why
`native-hook`. Elden Ring has no scripting API; params alone cannot add guns, a movement controller or a UI.
Considered and rejected: a passthrough (running CS2 alongside: impossible offline with VAC, and pointless
since CS2's data can be converted), Elden Mod Loader DLL (fine, but me3 gives a profile, a separate save and
offline launch in one place). The DLL draws CS2 models with its own D3D12 renderer injected into the game's
frame (a pre-ImGui hook in hudhook), the UI with ImGui, and changes behaviour through the `eldenring` crate
plus regulation rows built from the user's vanilla `regulation.bin`.

## How the game works (what we had to learn)
- **Boot order:** don't resolve fromsoftware-rs singletons from `DllMain`'s thread before the game window
  exists. The crate's singleton map caches the first reflection scan forever; an early scan lacks later
  singletons (`InvalidRva`). Gate on: window visible, then a fresh scan finds the reflection name. Use the
  singleton attribute name (`CSTask`), not the Rust type name (`CSTaskImp`).
- **Input:** the game reads mouse and keyboard with DirectInput `GetDeviceState` only (never `GetDeviceData`).
  Hooking it lets you blank keys/buttons for the game while your own UI or controller uses them.
- **Movement:** `CSChrPhysicsModule` has no usable velocity: motion is root-motion driven. A kinematic
  controller (CS2's movement constants read from the user's `libserver.so`) moves the character with Havok
  ray casts (`CSPhysWorld::cast_ray`, filter 0x2000058 hits map collision) and writes `physics.position` +
  `chr_proxy_pos_update_requested` + orientation every frame after physics. Hand control back for ladders,
  mounting, throws, death and interactions; resync when the game warps the character (map re-basing moves the
  Havok coordinates by tens of metres while the character stays put).
- **Fall death under a position-writing controller (the hard one):** the game keeps applying its *own* gravity
  to the physics body while you write positions. The body's velocity builds up a hidden falling speed the
  whole time the character is airborne; at touchdown the behaviour script plays a scripted fall death, which
  is not damage. What does **not** stop it: zeroing `CSChrFallModule.fall_timer`,
  `CSChrMaterialModule.disable_fall_damage`, clearing `physics.is_falling`, SpEffects with `fallDamageRate 0`,
  `noDead`, or the spirit-spring immunities (184 / 185, stateInfo 420 / 464). What stops it: while your
  controller drives, set `CSChrPhysicsModule.gravity_multiplier = 0` and `gravity_disabled = true` (your
  controller does gravity), restore the saved multiplier whenever the game drives again. Then apply your own
  fall damage on landing (CS2: (speed - 580) / (1024 - 580) of max HP, in u/s).
- **Spirit springs:** they are MSB regions of type MountJump (46) with a jump height in the type data. Only a
  mount gets SpEffect 183 "In Range", so the character on foot never knows it stands in one. The loaded MSB
  files are reachable at runtime: `MsbRepository` → its `res_cap_holder.entries()` (named `m60_XX_YY_00`);
  the file image is found by scanning the file cap's pointers for the `MSB ` header. Check every read with
  `VirtualQuery` first. Parse the region param list per SoulsFormats' MSBE layout: positions are block-local
  and match `PlayerIns.block_position` / `current_block_id`. Verified in game: heights 24 / 26 / 45 m read
  correctly, and on-foot launches work.
- **Level-ups:** `PlayerGameData` holds level, the eight attributes, runes and HP/FP/stamina maxima. Comparing
  them each tick lets a mod undo a level-up and refund its exact rune cost (no ESD editing needed). The talk
  menu types (`MenuType::Soul` = level up) exist in the crate but the live `CSNpcTalkIns` is not easy to reach.
- **ER UI elements:** `CSMenuManImp.ui_states[0x46]` (created/visible bits) gives a cheap "which ER menu is
  open" signal. Log transitions to map ids to screens.
- **"YOU DIED":** FeTextEffectParam rows 5 and 50. Blank them (`resId 0`, `textId -1`, `seId -1`) and the
  banner and its sound disappear while the death flow continues. `CSFeManImp.full_screen_message_request_id`
  is the runtime request.
- **Killer / last hit:** `ChrIns.last_hit_by` is a field-ins handle. Resolve it through
  `WorldChrMan.chr_inses_by_distance` (that list's `distance` is a relative metric, not metres).
- **Gear neutralised by params:** EquipParamProtector (cut rates, resistances, poise, weight, resident
  SpEffects) and EquipParamAccessory (`refId`, resident SpEffects); WitchyBND omits default values in XML,
  so an unset field means default.
- **Rendering into the game:** capture the scene depth (main DSV `D32_FLOAT_S8X24_UINT`, reversed Z; copy at
  the first `ClearDepthStencilView` of that DSV each frame) to occlude your 3D draws. If the copy is a frame
  stale (alt-tab, resize), use the last one instead of skipping the draw. Otherwise the hidden ER character
  "reappears" in place of your model.
- **Bullets:** spawn real engine bullets (`CSBulletManager::spawn_bullet`, Throwing-Dagger-like rows) so the
  game does the hits. Give each gun row `HitBulletID` = an inert marker bullet: its spawn is an
  engine-confirmed impact point.

## Build steps
1. Unpack the user's vanilla `regulation.bin` once with WitchyBND; a Python script copies it, appends rows
   (bullets, attacks, SpEffects, AI sounds) and edits rows (FeTextEffectParam, armour/talismans), writes only the
   edited `.param.xml` files back and repacks. Rows must stay sorted by id.
2. Pipelines (Python + VRF) convert CS2 content from the user's install into a local `cs2assets/out/`
   (gitignored): viewmodels with clips and sound events, the agent with world clips, glove/agent/charm meshes,
   paint-kit inputs for runtime skin compositing, case catalogue, panorama UI art, particle systems.
3. `cargo xwin build --release` the DLL into the me3 profile's `natives/`; launch via the me3 profile.
4. Offline oracles before every in-game test: `vmtest.exe` (the real D3D12 renderer offscreen under Wine)
   and `uitest.exe` (the real ImGui frame, rasterised from its draw lists).

## Verification
- In game by the user, every feature, with the DLL's own log as the oracle. It logs HP drops as
  `HIT c#### npc=… hp a->b`, boot state, menu transitions, spring regions read, landings with which immunities
  were on, case rolls, and render errors.
- Offline: the renderer and UI harnesses above (screens compared against the user's own CS2 screenshots),
  native harnesses for movement and recoil (Rust vs a Python reference), a 2M-roll simulation of the case odds,
  and a round trip of every rebuilt param (unpack the built regulation and compare).
- Not verified: other game versions, Windows (built and run only via Proton), co-op of any kind (offline only).

## Gotchas
1. **Boot: `InvalidRva` 7 ms after load.** **Cause:** the crate's singleton cache was built before reflection
   finished. **Fix:** wait for the game window plus a fresh reflection scan; never call crate singletons from
   `DllMain`'s thread early.
2. **Boot gate never passes.** **Cause:** searched the Rust type name instead of the reflection name
   (`CSTaskImp` vs `CSTask`). **Fix:** take names from `<T as FromStatic>::name()`.
3. **Dying after dropping onto a spirit spring (or anywhere) despite every fall-immunity effect.**
   **Cause:** the game's own gravity keeps accumulating velocity on the physics body under a position-writing
   controller; touchdown at that speed plays the scripted fall death. Fall timer, material flag, `is_falling`,
   `fallDamageRate 0`, `noDead`, SpEffects 184 / 185 and stateInfo 420 all did not help (each was verified to be
   on in the log). **Fix:** `gravity_multiplier = 0` + `gravity_disabled = true` while your controller drives,
   and your own fall damage. It took six test rounds; log the state at landing from the start.
4. **On-foot spirit springs do nothing.** **Cause:** SpEffect 183 "In Range" is only given to a mount.
   **Fix:** read MountJump (46) regions from the loaded MSBs in memory and test the player's block position.
5. **WitchyBND refuses to repack "regulation version exceeds latest known".** **Cause:** its Paramdex lagged
   the game patch. **Fix:** compare the defs you touch with a current Smithbox; if identical, bump the
   Paramdex upgrader version (keep the original) and round-trip check. Re-check whenever you add a param
   (EquipParamProtector's def did change in 1.17).
6. **Unpacking one `.param` outside its folder fails ("Could not determine PARAM type").** **Cause:**
   WitchyBND needs the regulation folder's context file. **Fix:** unpack in place in the unpacked regulation
   folder.
7. **Melee / short-range bullets never hit.** **Cause:** a row with life = range / speed under one frame
   (Zeus: 3 m at 2000 m/s = 1.5 ms) dies before the engine collides it; a melee row shorter than your target
   acceptance falls short. **Fix:** speed so life spans about two frames; reach past the accepted target.
8. **Bullet holes in the air / on enemies.** **Cause:** decals were placed at the marker even with no map
   surface there, and the character-hit report can arrive after the impact marker. **Fix:** require a map ray
   hit within 25 cm along the shot, and skip any impact within a character capsule + 25 cm.
9. **The ER character reappears in third person after alt-tab.** **Cause:** the replacement model only drew
   with a depth copy from this or the last frame. **Fix:** fall back to the last copy.
10. **3D models either hidden under the ImGui menus or drawn over the HUD.** **Cause:** hudhook 0.9.3's DX12
    backend has no hook around its ImGui pass. **Fix:** patch in a pre-ImGui hook (world-space draws, under
    the HUD) and a post-ImGui hook (a 3D model inside a menu, e.g. the item inspect); both get the command
    list, RTV and frame slot.
11. **VRF-exported clips double the root transform.** **Cause:** a standalone clip export keeps glTF's
    Z-up → Y-up turn on `root_motion`, while a model export with `--gltf_animation_list` bakes it into the
    root's children. **Fix:** convert (root r·R0⁻¹, children R0·t / R0·r). Clips outside the agent's animation
    graph (CS2's death clips) are not exported with the model; export them on their own.
12. **Additive world clips used as poses give A-pose arms.** VRF composes additive clips over the bind pose
    (`--gltf_compose_additive`); apply them relative to their first frame, never as a full pose.
13. **Particles with tinted sprites look dark.** **Cause:** the additive pass multiplies colour by alpha, so
    textures baked premultiplied lose it twice. **Fix:** bake RGB without alpha for additive sprites.
14. **A small screen texture (Zeus charge digits) blurs.** **Cause:** a 7-segment display draws every segment
    from one texture column with its own row; mips merge the rows. **Fix:** one mip level for that texture.
15. **Case odds felt rigged.** **Cause:** the RNG was seeded from `Instant::now().elapsed()` (≈ 0, same seed
    every time). **Fix:** seed from the performance counter, time and pid; verify by simulation.
16. **The death screen named a long-dead enemy after a fall.** **Cause:** `last_hit_by` keeps the last
    attacker forever. **Fix:** treat a death right after a hard landing as a fall.
17. **The level-up undo looks like it might fight the game.** It doesn't, if you restore the previous tick's
    level, attributes, both PlayerGameData maxima and the ChrIns data-module maxima, and refund the rune
    delta of that same tick.

## Assets
None generated: everything is converted from the user's own CS2 install by pipelines (VRF + Python + Pillow)
into a gitignored folder, never committed or redistributed. Skins are composited at runtime from CS2's paint
kit inputs (wear and pattern seed per item).

## Cost and time
About three days of agent sessions (several usage-limit resumes); the user ran every in-game test.

## Open questions
- What exactly the scripted fall death reads (velocity on the Havok character proxy is the working
  hypothesis; the fix is consistent with it).
- Blocking the Equipment tab and the grace Level Up screen outright: `ui_states` ids are being logged to map
  them.
- CS2's lid animation and 3D warehouse scene for case opening (a 2D case image zooms instead).
