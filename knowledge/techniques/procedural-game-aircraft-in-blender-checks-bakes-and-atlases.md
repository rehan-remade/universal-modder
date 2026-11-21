---
kind: technique
title: 'Procedural game aircraft in headless Blender: geometry checks, world-position bakes and livery atlases that survive
  rebuilds'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-22'
links:
- https://github.com/riseofthewolfremake-lgtm/HeritagePairs-NuclearOption
- knowledge/games/nuclear-option/new-aircraft-with-blueprinter-nobp-b25h-ga25x-nimrod.md
tags: [blender, bpy, procedural-modeling, uv-atlas, baking, liveries, mesh-checks, damage, reference-comparison, cockpit, unity]
---
# Procedural game aircraft in headless Blender: geometry checks, world-position bakes and livery atlases that survive rebuilds

> How to build a damageable, multi-livery vehicle with a working cockpit from Python scripts in headless Blender, and keep it
> correct across dozens of rebuilds: a model contract the engine-side build checks, mesh checks that run on every build,
> texture art baked from world position, and a hashed livery atlas that fails the build when geometry moved the UVs.
> Worked example: six flyable aircraft (and a seventh in progress) for Nuclear Option (Unity 2022.3, Blueprinter .nobp packs),
> all built this way; every rule below comes from a defect a player or tester actually saw.

## When to use it
- A script (not hand modelling) generates a vehicle: airframe parts that detach on damage, moving control surfaces, gear,
  props or rotors, a cockpit with animated stick / throttle / dials, and several paint schemes (liveries).
- You rebuild the model often (every fix is a re-run of the generator), so anything that is only checked by eye once will
  silently regress.
- Setup it was proven on: Blender 5.2.2 in `--background` mode with `bpy` + `bmesh`, Cycles (GPU, CPU fallback) for bakes,
  numpy + Pillow for image work outside Blender, FBX export into Unity 2022.3.62f2 batch mode, Windows 11.
  Nothing in the method depends on the game; the Nuclear Option specifics are marked as such.
- Where it comes from: the open-source "Heritage Pairs" aircraft pack for Nuclear Option (public repo linked above;
  paths below are relative to it). No game files are involved: stock aircraft were only looked at for conventions.

## How

### 1. A model contract between the Blender side and the engine side
- Every object that the engine-side build touches gets its facts written to a JSON contract by a Blender script after the build:
  part name, parent, pivot, hinge axis and sign, travel range, axles, muzzles, hardpoints, cockpit movers (stick, throttle,
  needles), all in the ENGINE's coordinates (Unity: x right, y up, z forward; Blender +a about (x, y, z) becomes
  AngleAxis(-a, (x, z, y))). See `blender/v2/contract_b25h_v2.py`.
- The engine-side builder (Unity editor scripts under `unity/Editor/`) reads the contract instead of hard-coding numbers, and
  an offline stub test in plain Python (`blender/v2/test_contract_stub.py`) re-states, in a few lines, how the game's own drivers
  apply each value (control surface angle, throttle lever, turret, canopy hinge) and checks every sign / axis / range claim against
  probe points measured on the real mesh, with negative tests that must fail. Sign errors (elevator up for push, aileron reversed) are caught before any game run.

### 2. Mesh checks on every build (they fail the build, not a review)
Each aircraft has a `check_<aircraft>_model.py` run headless after the build. The checks that paid for themselves:
1. **Every face outward.** A lathe (surface of revolution) must take its winding from the profile polygon itself (the
   (along-axis, radius) polygon closed with the axis), not from "the first ring pair that has a non-zero score". Check: cast
   rays at each mesh from outside and fail it when too many first hits land on back faces (`check_winding` in
   `blender/b17g/check_b17g_model.py`); for a lathed part also count faces whose normal points toward the axis (spinner checks
   in `blender/nimrod/check_nimrod_model.py` and `blender/fd32/check_fd32_model.py`).
2. **Connectivity.** Every strut, wire, fin, stab, wing root and gear leg end lies within 1 cm of the surface it attaches to; no
   floating islands (`check_connect`). Note: a helper that returns the body width at a station can be up to 80 mm outside
   the real skin where a fillet blends in; use the actual skin ring for anything that must touch the skin.
3. **See-through with backface culling ON** (game engines cull, Blender's viewport does not): ray grids from many outside
   directions AND from inside every detached part / break, counting rays that leave through a back face (`check_see_through`).
4. **Z-fighting.** Pairs of visible faces that are nearly coplanar and overlap: the project's checks used 0.3 to 2.2 mm along
   the normal and 2 to 8 degrees, depending on the aircraft (`zfight_pairs` in `blender/b17g/check_b17g_model.py`: 0.8 mm,
   2 degrees); they render as flickering shards in game.
5. **Control-surface clearance through full travel.** Pose each hinge at both ends of its range and test against neighbours.
6. **Moving cockpit parts through their FULL travel**, not at rest: stick full forward / back / left / right and the diagonals,
   throttle 0 and 100 %. Fixed bases (stick boot, quadrant) are separate objects from the moving parts.
7. **One-piece sweeps.** A bent bar (throttle lever, canopy frame) is one closed shell swept along a polyline with mitred or
   filleted corners, never boxes butted together (they leave an open V at every bend). Check: the part is one welded,
   closed component.
8. **Symmetry.** Centreline parts (seat, sight, stick, canopy) at x = 0 within a millimetre; check the reference's
   claims before copying them (see Gotcha 5).
9. **Breaks (damage).** Every break face open like the engine's stock parts: skin edge, inner liner, a frame or rib set back
   from the plane, stringer stubs ending short of it; no solid disc in the break plane and no single plane that fills most of
   the view from the break (ray fractions per material and depth).

### 3. Bakes: project art in 3D, not in UV space
- Bake world POSITION and NORMAL per texel once (an Emission bake with Geometry -> Position wired to the emission colour, to a
  float EXR), then evaluate every texture feature (camo blotches, panel lines, rivets, wear, roundels, serials) in numpy from
  those per-texel 3D positions. Seams between UV islands don't show, because neighbours across a seam get the same 3D
  value, and markings land by 3D projection. See `blender/v2/textures/bake_maps.py`.
- Cycles multi-object bakes into ONE image apply the bake margin PER OBJECT, so each object's margin bleeds over other
  objects' islands. Bake with margin 0, then dilate the result yourself (nearest-island fill in numpy).
- Bake in a known pose (gear and doors closed): a door baked while lying inside a nacelle gave a dark blocky patch on every livery.

### 4. Atlas stability: the livery atlas is a contract too
- One global island pack (`bpy.ops.uv.pack_islands` over every paint face of every part, `pack_livery` in
  `blender/v2/build_b25h_v2.py`) moves EVERY island when ANY geometry changes. Textures baked on the old atlas then land
  on the wrong parts. Either re-bake every skin, livery and damage texture after any geometry change, or patch only the
  changed mesh into the shipped .blend so the atlas stays bit-identical.
- Hash the atlas and keep the hash in the texture manifest (`blender/atlas_guard.py`): per part, the SET of distinct UV
  points of its paint faces, quantised to 1/65536, sorted, SHA-1. A set does not depend on face order, triangulation or
  vertex splitting, so Blender loops and engine vertices hash the same. The engine-side build recomputes it from the imported
  meshes and FAILS on a mismatch (`unity/Editor/AtlasGuard1816.cs`); a standalone check runs on the exported FBX
  (`blender/atlas_check.py`).
- Compare every livery before and after a change from fixed cameras and the same light (`blender/render_atlas_compare1816.py`
  renders, then a per-pixel diff: share of aircraft pixels with any channel off by > 40).
- Keep the cockpit on its own atlas and its own textures, so cockpit work never moves the exterior liveries.

### 5. Renderer structure the engine expects
- Read how the game toggles renderers before splitting meshes. Nuclear Option's `ConstantSpeedProp` enables or disables only
  each blade's own `blade.renderer` when it swaps to the blur disc; any child renderer under a blade (for example a second
  material band split off as its own object) stays visible over the blur. Give blades exactly one renderer and no children.

### 6. Reference comparison before claiming a match
- Render your model from the reference's cameras (same orthographic side / top / front, same scale) and outline-compare the
  silhouettes: IoU plus, per reference outline pixel, the distance to your nearest outline pixel (median and 90th percentile),
  masking zones that differ by design. Put the numbers next to an overlay (ours red, reference cyan, overlap white).
- When someone reports a visual defect, look for it in your own last screenshots first; in this project it was usually already
  visible there.

## Verification
- Oracles: the per-build model checks above (exit code 1 fails the pipeline), the Unity batch-mode check suite (atlas hash,
  contract, materials) on the imported FBX, the before/after livery render diffs, outline IoU against the reference, and
  in-game tests of each release by the agent and by the human (flying, damage break-up, liveries, cockpit at every travel end).
- Six aircraft shipped publicly with this pipeline. The atlas guard was tested on its failure case: the frozen pack with the
  scrambled liveries, checked against the manifests of its textures, fails it.
- NOT verified: the method on non-aircraft vehicles; Blender versions other than 5.2.2 (the `pack_islands` call uses
  keywords such as `udim_source`, `rotate_method`, `margin_method` and `shape_method`; older versions may lack some); engines other than Unity; the exact Cycles per-object-margin behaviour in other Blender versions.
- The reference comparison only checks silhouettes; panel shapes, cockpit layout and colours still need a side-by-side look.

## Gotchas
1. **Symptom:** a see-through propeller spinner (448 of its 512 faces pointed inward). **Cause:** the lathe helper chose its
   face winding from the first ring pair with a non-zero orientation score; the spinner's first band was the flat back plate,
   whose score was rounding noise. **Fix:** orient every band from the profile polygon closed with the axis; add a check
   that the spinner is 512 / 512 outward.
2. **Symptom:** after a model fix, camo blotches on plain-painted parts and olive patches on natural-metal ones, on every
   livery of two aircraft. **Cause:** the rebuild re-ran the global atlas pack, which moved every UV island; the textures were
   not re-baked. No offline check, stub or game test looked at paint. **Fix:** atlas hash in the texture manifest, checked
   in Blender and in the engine build; re-bake after every geometry change; fixed-camera livery diffs before handover.
3. **Symptom:** prop blade tips visible over the spinning-prop blur disc. **Cause:** the engine-side build split a blade's
   sheath band into a child renderer; the game hides only the blade's own renderer. **Fix:** skip blades when splitting
   materials into child renderers; one renderer per blade.
4. **Symptom:** the throttle lever showed a visible gap at its elbow. **Cause:** two boxes butted at an angle leave an open V
   on the outside of the bend. **Fix:** one closed bar swept along the polyline with mitred / filleted corners (`_sweep_bar`
   pattern), plus a check that the lever is one welded component. Same fix for canopy frames.
5. **Symptom:** pilot seat, sight and controls sat 32 mm off-centre. **Cause:** they were positioned from the reference model's
   eye point, which itself is off-centre. **Fix:** centreline parts at x = 0; symmetry check; treat reference eye and
   camera points as approximate.
6. **Symptom:** a brief claimed the aft fuselage was 0.7 m short of the reference. **Cause:** the comparison render filter
   hid every object whose name contained "gun", which dropped the `tail_gun` fuselage section; overall length actually matched
   (22.60 vs 22.61 m). **Fix:** filter renders by an explicit object list, not by name substrings; measure lengths from the
   geometry as well as from renders.
7. **Symptom:** the engine-side atlas hash differed on one part with nothing wrong. **Cause:** Unity's FBX import drops
   degenerate triangles (collapsed quads at a nose pole), so some UV points never reach the engine. **Fix:** keep the exact hash
   for Blender, and in the engine pass a part when >= 99 % of its imported texel cells are manifest cells and >= 95 % of the
   manifest cells are present; a real re-pack overlapped only 0-14 % in the project's fixtures, so the rule cannot pass one.
8. **Symptom:** solid round metal discs at every break face, and a plain box visible through damage holes. **Cause:** fan caps
   closed each body section in the break plane; a fuel tank was modelled as a structure-material box. **Fix:** open breaks
   (setback frame, stubs, dark edge bands), tanks as rounded cells in their own plain material, and a check that no single
   plane fills more than ~60 % of the rays from a break.
9. **Symptom:** the stick boot rotated with the stick, a rod on the stick clipped through the front panel at some stick
   angles, and the throttle clipped through nearby parts at full travel while it looked fine at rest. **Cause:** fixed and moving parts in one object; clearance checked only at the rest pose. **Fix:**
   separate objects, and clearance sweeps through the full range including diagonals.

## Seen in
- Nuclear Option: `knowledge/games/nuclear-option/new-aircraft-with-blueprinter-nobp-b25h-ga25x-nimrod.md` (route, Blueprinter
  .nobp packs, flight and damage model) and the other notes in `knowledge/games/nuclear-option/`.
- Related technique: `knowledge/techniques/feather-pass-for-game-birds-in-headless-blender-conforming-c.md` (another headless
  Blender pipeline).
- Source: https://github.com/riseofthewolfremake-lgtm/HeritagePairs-NuclearOption (`blender/`, `unity/Editor/`).
