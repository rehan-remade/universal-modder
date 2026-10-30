---
kind: game
title: 'Portal 2 portal gun viewmodel converted for another engine: VPK, MDL v49, VTF, sounds'
game: Portal 2
games_also: [Outer Wilds]
game_version: "Steam 620 (2026 build), portal2/pak01_dir.vpk"
platform: windows
engine: source
route: asset-only
tools:
- Python 3.14 + Pillow + numpy (own VPK/MDL/VTX/VVD/VTF readers)
anti_cheat: none (files only, the game never runs)
status: working
agents:
- Claude Code (Opus 5.5)
humans:
- charlystereo
date: '2026-10-10'
links:
- https://github.com/rehan-remade/universal-modder/tree/main/examples/outer-wilds-portal-gun
- https://developer.valvesoftware.com/wiki/MDL
- https://developer.valvesoftware.com/wiki/VTF
- https://developer.valvesoftware.com/wiki/VPK
tags: [source, mdl, vvd, vtx, vtf, vpk, viewmodel, animation, content-port, portal-gun]
---
# Portal 2 portal gun viewmodel converted for another engine: VPK, MDL v49, VTF, sounds

> A Python converter that reads the user's own Portal 2 install and writes the portal gun viewmodel (skinned mesh,
> bones, attachments, all 14 sequences decoded to per-frame bone poses), its textures, Portal 2's portal colour ramps,
> masks and crosshair, and 28 weapon/portal sounds, for a Unity mod (Outer Wilds, see the companion note
> `games/outer-wilds/portal-2-portal-gun-in-outer-wilds-1-1-16-owml-see-through-p.md`). Checked with a software
> render before use and then in the host game. The generic MDL v49 / VVD / VTX / VTF reading steps are in
> `techniques/reading-source-engine-models-and-animations.md`; this note keeps what is specific to Portal 2 and to
> converting for Unity.

## Setup
Portal 2 from Steam (`steamapps/common/Portal 2`). Everything needed is in `portal2/pak01_dir.vpk` (VPK v2, ten
`pak01_NNN.vpk` archives). Search order used: `portal2_dlc2`, `portal2_dlc1`, `portal2` VPKs, then loose `portal2/`.

## Route and why
Asset-only: read files, never run the game, convert on the user's machine into a folder outside any repo.

## How the game works (what we had to learn)
- **Files:** `models/weapons/v_portalgun.{mdl,vvd,dx90.vtx}`; textures in
  `materials/models/weapons/v_models/v_portalgun/` (`v_portalgun`, `_blue`, `_orange`, `_glass`, `_normal` DXT1,
  `_exponent`, `_lightwarp`); portal look in `materials/models/portals/` (`portal-blue-color` / `portal-orange-color`
  are 256x1 BGR888 ramps, `portal_mask` 512² ellipse, `noise-blur-256x256`); crosshair
  `materials/sprites/hud/portal_crosshairs` (256x64 BGRA8888, five 48 px cells: left arc, right arc, left filled, right
  filled, dot; the 2 px columns between cells are separators). Sounds in `sound/weapons/portalgun/`
  (`wpn_portal_gun_fire_{blue,red}_0[1-3]`, `portal_open_blue_01`, `portal_open_red_0[12]`, `portal_enter_0[1-3]`,
  `portal_exit_0[12]`, `portal_invalid_surface_0[1-4]`, `portal_fizzle_0[12]`...), all PCM16 RIFF.
- **MDL v49:** 31 bones (`ValveBiped.Bip01` arm chain, `ValveBiped.Base`, claws `Arm1-3_A/B/C`, wires, plus a second
  root `valvebiped.portalgun_reference`); 17 attachments (`muzzle`, `Arm*_attach*`, `Body_light`, `Beam_point1-5`,
  `Inside_effects`); 5 textures; skin families `[0,1,2,3,4]`, `[1,...]`, `[2,...]` = neutral/blue/orange body; body part
  0 = gun (7242 + 48 tris), body part 1 = potatOS (skip). Sequences at 30 fps: fire1, fizzle, draw, holster,
  idletolow, lowtoidle, lowidle, dryfire, idle_layer, idle (180 f), idle_to_carrying, idle_carrying, carrying_to_idle,
  end_draw. **No sequence events**: Portal 2 plays the gun sounds from code.
- **Record sizes and field offsets** (bone, model, animation and sequence descriptions, events, attachments): see
  the technique note, step 2. The VVD has fixups when present.
- **Animation decode:** the technique note's "bone by frame" style (Quaternion48/64 raw rotations, half-float raw
  positions, RLE animated channels scaled by the bone's rotscale/posscale and added to its defaults unless DELTA).
  All of `v_portalgun`'s animations are embedded in the MDL (animblock 0).
- **VTX (dx90) in Portal 2** uses the extended strip-group (33 B) and strip (35 B) headers; the 25/27 B layouts fail
  to parse. Strips were all triangle lists.
- **VTF 7.2–7.5:** in 7.3+ the image data is found through the resource entry tagged `0x30 0 0`; DXT decodes with
  Pillow's `bcn` decoder (n=1 for DXT1, n=3 for DXT5).
- **Axes:** Source X forward, Y left, Z up, inches → Unity `(−y, z, x) * 0.0254`. The map is a mirror (det −1) yet the
  triangle winding did not need flipping (vote of face normals against vertex normals); flip V. Bind poses = converted
  `poseToBone`. The viewmodel origin is the eye: put the model at the camera.

## Build steps
`python tools/convert.py [--portal2 <install>] [--out <dir>]` in `examples/outer-wilds-portal-gun`. Output: binary
`portalgun.owpg` (bones, mesh, submeshes by texture name, attachments, sequences as [frame][bone] pos+quat),
`textures/*.png`, `sounds/*.wav`, `manifest.json`. 0.8 s, 8.3 MB.

## Verification
- Every one of the 14 animations decodes to finite values.
- Software render (numpy + Pillow painter's algorithm, back-face culled) of `idle` frame 0 from the eye at 54° fov:
  gun bottom-right pointing forward with claws, wires and glass, as in Portal 2. Done before writing any game code.
- In Outer Wilds: draw/fire/holster animations, skins switching, all sounds play; textures and crosshair decoded
  correctly (checked on a contact sheet).

## Gotchas
1. **VTX parse fails with the classic headers.** **Cause:** Portal 2-era VTX adds two ints to strip groups and strips
   (technique note, step 3). **Fix:** try 33/35-byte headers first, fall back to 25/27.
2. **`v_portalgun.vtf` looks washed out.** **Cause:** its alpha is a constant 38 (a phong mask), not opacity. **Fix:**
   ignore alpha for the body (the blue/orange variants' alpha is a self-illum mask).
3. **Crosshair shows vertical lines.** **Cause:** sampling the full 48 px cell includes the 2 px separators. **Fix:**
   use the 42 px of art at cell offset +3.
4. **Expecting sound events in the sequences.** There are none in Portal 2's viewmodel; choose sounds in code.

## Assets
Only the user's own Portal 2 files, converted locally. Nothing from Valve is committed or shipped.

## Open questions
- Exponent/lightwarp maps and Portal 2's portal shaders (PortalRefract stages) were not ported; the host draws its
  own rim from the colour ramp and mask.
