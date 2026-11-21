---
kind: game
title: "Damage that looks like stock on custom Nuclear Option aircraft: open break faces, AircraftSkin hole maps and internal structure"
game: "Nuclear Option"
game_version: "Early Access 0.34.6 (Steam app 2168680, public build 26327221); the shader and part rules were read on 0.34.6 and re-checked against a later decompile of the same build"
platform: windows
engine: unity-mono
route: loader-api
tools: ["Blueprinter 2.1.1 (NOBlueprinter-Editor project)", "Unity 2022.3.62f2 (batch mode)", "Blender 5.2.2 (bpy, BVHTree ray checks)", "numpy", "UnityPy (reading the compiled shader, locally only)", "AssetRipper (stock prefab and mesh YAML, reference only)", "ILSpy-style decompile of Assembly-CSharp (reference only)", "BepInEx 5.4.23.5 + a local test helper plugin (in-game detach / damage commands)"]
anti_cheat: "none found; single player only"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-11-22
links:
  - "https://github.com/riseofthewolfremake-lgtm/HeritagePairs-NuclearOption"
  - "https://github.com/riseofthewolfremake-lgtm/HeritagePairs-NuclearOption/blob/main/blender/v2/textures/hole_damage189.py"
  - "https://github.com/riseofthewolfremake-lgtm/HeritagePairs-NuclearOption/blob/main/unity/Editor/DamageHoles189.cs"
  - "https://github.com/riseofthewolfremake-lgtm/HeritagePairs-NuclearOption/blob/main/unity/Editor/StockStructure.cs"
  - "https://github.com/riseofthewolfremake-lgtm/HeritagePairs-NuclearOption/blob/main/blender/check_breakfaces.py"
  - "https://github.com/nikkorap/NOBlueprinter-Releases"
tags: ["aircraft", "damage-model", "break-up", "shader", "hole-map", "alpha-clip", "internals", "blueprinter", "model-checks", "ray-casting"]
---

# Damage that looks like stock on custom Nuclear Option aircraft

This is the full damage study behind Gotchas 5 and 11 of
[the Blueprinter aircraft note](new-aircraft-with-blueprinter-nobp-b25h-ga25x-nimrod.md). Stock Nuclear Option
aircraft get bullet and shell holes in the skin, show frames and ribs through those holes, and break into parts
with open, torn ends. Our custom aircraft at first only darkened until a part popped off. When parts did come
off, every break was closed by a solid metal disc, and a box showed through the holes. This note covers how the
game really does it (part hit points, the `AircraftSkin` shader's alpha-clip hole map, internals as extra
submeshes, uncapped break faces) and the build rules and offline ray checks that got our parts to look like
stock. The user accepted the open breaks in game on our latest airframe.

## Setup
- Game: Nuclear Option Early Access 0.34.6 (Steam, Windows 11). The engine facts below were read on 0.34.6 and
  re-checked against a second, later decompile of the same build.
- Mod: one Blueprinter `.nobp` addon (Blueprinter 2.1.1, Unity 2022.3.62f2 batch mode) and a small BepInEx
  5.4.23.5 plugin. See the overview note for the full pipeline.
- Models: procedural Blender 5.2.2 scripts that export FBX. Unity editor scripts build the prefabs.
- Reference only, never shipped or committed: an AssetRipper export of the installed game (prefab, mesh and
  material YAML), a local decompile of `Assembly-CSharp`, and the compiled `Shader Graphs/AircraftSkin` read
  with UnityPy and disassembled locally.

## Route and why
- Same route as the overview note: Blueprinter `loader-api`. Our parts are stock `UnitPart` / `AeroPart`
  components, so the game's own damage code runs on them.
- So the job is mostly **art and geometry**: what the mesh, the damage texture and the materials must look like
  for the stock code and shader to produce stock-looking damage.
- Considered and rejected: a plugin that swaps in "broken" meshes on detach, and caps or shells generated at
  runtime. Stock does neither. It shows the same mesh intact and broken, so doing the same keeps us compatible
  with every game system (fragments, fire, multiplayer sync) for free.

## How the game works (what we had to learn)
All in our own words. Symbols are from the 0.34.6 decompile.

**Part hit points**
- Every `UnitPart` (and `AeroPart`, which is one breakable rigid body) starts with `hitPoints = 100`.
- `TakeDamage` subtracts pierce, blast, fire and impact damage after armour. Hit points **keep falling below
  0**: the part breaks off only when they pass its `structuralThreshold`. Stock values run from about -25 to
  -200 (for example a nose at -50 and a forward fuselage at -200).
- Detaching is `UnitPart.Detach` then `AeroPart.CreateRB`. The part gets its own `Rigidbody` and **keeps its
  mesh**. There is no "detached prefab" field in this build.
- Below `integrityThreshold`, `SpawnFragments` hides the `disintegrateObjects` and spawns the
  `disintegrationEffects` (stock `fragments_small` / `fragments_med`). On the five stock aircraft we counted,
  `disintegrateObjects` is empty on all 174 AeroParts, so the holes do **not** come from there.
- After every hit the part writes its hit points into the shader float `_HitPoints` on the material of every
  renderer in `damageMaterial.renderers`. If that list is empty, its own renderer is added at start. So a part
  can drive the damage look of other renderers too (stock cockpits list the canopy frame and gear doors).
- Impact (crash) damage comes from `AeroPart.OnCollisionEnter` and is **skipped when
  `impactDamage.threshold` is 0**. That is the case on most stock part templates (overview Gotcha 11).

**The `AircraftSkin` shader** (stock `<plane>_skin` materials, `Shader Graphs/AircraftSkin`)
- Let D = 1 - `_HitPoints`/100. D is 0 on an undamaged part, 1 at 0 HP, and more than 1 below that.
- Colour and normals blend from the clean skin toward `_BasecolorDmg` and `_NormalDmg` in proportion to D, over
  the whole part. That is the soot and dents.
- **Holes:** every pass of the shader has a discard, including the shadow and depth passes. A skin pixel is cut
  out when the **alpha of `_BasecolorDmg`** there is below about **0.52 - 0.02/D**:
  - HP 95: about 0.12;
  - HP 90: 0.32;
  - HP 80: 0.42;
  - HP 50: 0.48;
  - HP 0: 0.50;
  - it never reaches 0.52.
- So the damage texture's **alpha channel is a hole-order map**. The lowest values open at the first hits, and
  anything at or above 0.52 never opens.
- How much of the skin is open in stock damage maps (our measurement, percent of texels below the threshold):

  | aircraft | HP 80 | HP 50 | HP 0 |
  |---|---|---|---|
  | CI-22 | 13.4 % | 21.5 % | 25.4 % |
  | A-19 | 2.1 % | 8.3 % | 16.8 % |
  | FastBomber1 | 1.9 % | 16.0 % | 22.8 % |
  | EW-25 | 8.9 % | 26.6 % | 31.7 % |

- The stock alpha maps are noise fields with dark clusters (bullet and shell groups) and a few big patches.

**What shows through a hole: internals as submeshes**
- Stock prefabs have **no** separate tank, spar or engine GameObjects. Internals are extra **submeshes of the
  part mesh**, in two shared materials:
  - `aircraft_structure`: shader `Shader Graphs/Lit_vertexcolor`, white base, smoothness 1, no texture. The
    grey comes from vertex colour (about 93/93/93 on FastBomber1) and the part's AO.
  - `jet_mechanical`: a URP Lit trim sheet (2048 px truss beams, perforated strips, cable looms, honeycomb).
    Its UVs tile far outside 0-1 along u.
- Renderers that carry an `aircraft_structure` submesh: FastBomber1 28 of 148, Multirole1 35 of 151,
  SmallFighter1 34 of 134, EW1 32 of 145, CAS1 (A-19) 13 of 142, COIN (CI-22) 0, Fighter1 0. The older
  aircraft rely on `jet_mechanical` alone.
- **Fuel is not modelled visually.** Tanks are `FuelTank` components on parts (FastBomber1 has 12), and a burning
  wreck is their fire and fireball effects, not a tank mesh.
- Engines are part meshes whose break face shows structure. Fire and IR points are empty transforms.

**Break surfaces**
- Every stock part mesh is **one mesh with 2-4 submeshes**: skin, `jet_mechanical`, and on bigger parts
  `aircraft_structure` and/or `honeycomb`. The mechanical submesh often has more triangles than the skin.
- **No caps, and no separate broken mesh.** While the aircraft is whole, the mating part covers the torn edge.
  Once it is gone you look into frames, stringers and inner skin.
- Skin edges at a split are not straight: CAS1 uses stepped panel edges and FastBomber1 zigzag teeth. Spar
  flanges and stringers stick out past the skin edge, with a rib or frame set back behind it.
- Stock part split for scale: 33-38 AeroParts per aircraft (3-4 wing pieces plus a tip per side, 3-5 fuselage
  pieces, every control surface its own part).

## Build steps
These are the rules we now build every airframe to. Our public repo has the scripts linked in the front matter.
1. **Skin:** two-sided or backed by an inner skin or liner, so a detached part is never see-through from
   inside. Check this with backface culling on (Unity culls).
2. **Break edge:** jagged or stepped edges computed from vertex position, so both parts get complementary edges
   and the intact aircraft has no gap.
   - A **dark 6 mm band** on the skin edge.
   - A **dark 25 mm band** where every inner skin or liner ends.
3. **Behind the edge, open structure, never a cap:**
   - fuselage: an open ring frame set back **0.10 m**;
   - wings and tail: a two-web rib (or only a 25 mm dark perimeter strip, with the section left open) set back
     **0.06-0.10 m**;
   - L-section stringer and spar **stubs ending 15-40 mm short** of the break plane;
   - nothing crosses the break plane.
4. **Deep walls only where a real one exists:** bay-end walls about **0.4 m** in (0.25-0.85 m depending on the
   cavity), in the interior paint colour, not the light structure grey. On the engine section, put a plain dark
   firewall about 0.38 m in, behind an engine-mount tube truss.
5. **Internals:** frames, stringers and engine bodies as submeshes of the part that carries them, in the stock
   `aircraft_structure` material with the stock vertex grey. Our `StockStructure.cs` moves our internals submesh
   into a child renderer with that material, so the paint stays material 0 and liveries are untouched.
   - Tanks, if you draw them, are **rounded cells** in their own plain lit grey material (albedo about 0.55),
     not boxes.
   - Add `FuelTank` components where the real tanks were.
6. **Hole map:** one `_skin_dmg_b` per livery atlas with a real alpha (`hole_damage189.py`):
   - world-space cellular noise, so holes continue across UV seams;
   - three hole families (bullet clusters open first, then shell holes, then torn patches);
   - alpha assigned by rank to hit coverage targets;
   - never-open skin at alpha 0.54-0.60, and 0.62 outside the UV islands;
   - soot rims and dented normals lined up with the holes;
   - only paint faces get holes (no glass, tyres or markings).
   - Target bands: **5-13 % open at HP 80, 10-27 % at HP 50, 15-30 % at HP 0.**
7. **Import:** keep the alpha channel on the imported texture (`DamageHoles189.cs` fails the build if the
   imported format has no alpha).
8. **Impact damage:** give every part its own `ImpactDamage` instance with a non-zero threshold (overview
   Gotcha 11).
9. **After any geometry change, re-bake** the skin, livery and damage textures. The livery atlas re-packs, and a
   damage map baked for the old atlas puts holes in the wrong places.

## Verification
Oracles, in the order we used them:
- **Offline ray checks in Blender** (BVHTree, every part alone). Before and after numbers, from the first
  failing build to the accepted one:
  - **Flat area in a break plane** (faces lying in the break plane = caps): 1.003 m² -> 0.001 m².
  - **Structure first hit through the HP 0 holes** (rays through the open texels of the hole map): 51.5 % ->
    3.2 % (later 5-7 % with the firewall and truss), and 0 on flat plates.
  - **break_one_plane:** no single plane across the axis may take more than 30 % of the axial rays within
    0.15 m of a break. This catches full-section ribs that are not quite in the plane (84-94 % before).
  - **break_deep_wall:** looking 0.5 m in, no plane of a non-paint material may be the first hit for more than
    60 % of the rays, except a documented allow list (the firewall at 0.35 m or more, interior bay-end walls at
    0.25 m or more). This caught a dark firewall disc with a light stiffener lattice 0.17 m in, which sat just
    past the 0.15 m window of the other checks.
  - **Projected structure coverage** at most 30 % within 0.5 m. Older airframes use `check_breakfaces.py`:
    structure at least 30 % of rays, shell plus void at most 50 %.
  - **See-through checks:** renders with backface culling on vs off, from 14 outside views of the whole model and 6
    views of every part alone, plus the main detached parts seen from their break ends.
  - **Connectivity:** every strut, fin, stab, wing root and gear leg end within 1 cm of its surface.
- **Unity build rows:** hole coverage per band from the shipped PNG, alpha kept on import, tank albedo measured
  (0.555, against about 0.075 before), structure and firewall vertex counts at the engine joint.
- **Renders** of every break face next to decoded stock parts (CAS1 and FastBomber1) for side-by-side compare.
- **In game:** a local test helper (removed after every run) detached parts on a parked aircraft and applied
  gun damage in flight. We shot contact sheets of every break face and of holes at several HP levels, intact,
  in two liveries.
  - Result: all breaks open with a dark seam band, lining, frames and stubs, and no disc anywhere.
  - Holes show interior, seat, frames and engine cylinders, and no box.
  - The user accepted the open breaks.
- **Not verified:**
  - the shader rule was read from compiled bytecode, not traced on the GPU (the in-game holes matched it, but we
    did not measure exact thresholds live);
  - some detached pieces were not shot from their root end (the camera ended under the runway);
  - multiplayer sync of damage on custom parts;
  - our two older single-engine airframes still close their centre-section breaks with the same kind of solid wall;
    they are not fixed yet and will need the same treatment.

## Gotchas
1. **A solid round metal disc closed every break.**
   - **Cause:** fan caps (and notched rib caps) built in the break plane. Stock has no caps.
   - **Fix:** remove the caps. Use an open ring frame or two-web rib set back 0.06-0.10 m, stubs ending short
     of the plane, and dark edge bands. Check flat area in the break plane, which should be about 0.
2. **Removing the cap left a full rib just behind it, and it still read as a disc.**
   - **Cause:** a full-section rib in the light structure grey 0.10 m in took 84-94 % of the axial rays.
   - **Fix:** a 25 mm perimeter strip with the section open, and a deep bay-end wall in interior paint. Add the
     break_one_plane check (30 % or less).
3. **A "metal wall" with a light lattice still showed at the engine joint.**
   - **Cause:** a stiffened firewall 0.17 m in, just past the 0.15 m windows of the checks.
   - **Fix:** a plain dark firewall 0.38 m in behind an open frame and a tube truss. Extend the checks to 0.5 m
     (break_deep_wall with an explicit allow list).
4. **A box was visible through the skin holes.**
   - **Cause:** the fuselage tank was modelled as a structure-material box.
   - **Fix:** rounded tank cells in their own grey material with dark straps, or no tank mesh at all (stock
     has none: `FuelTank` plus effects).
5. **The tank showed as a black hole inside the holes.**
   - **Cause:** a gunmetal tile texture times a 0.62 tint gave an albedo of about 0.075.
   - **Fix:** a plain untextured lit grey of about 0.55. Measure the effective albedo (texture mean times
     `_BaseColor`) in a build check.
6. **Light wedges stood out of the tail over the stab root.**
   - **Cause:** frames and longerons were sized for a constant section, but the skin tapers there.
   - **Fix:** clip internals to the local skin radius minus the liner, and run the see-through and "nothing
     outside the skin" checks.
7. **Parts darkened evenly until they popped off, with no holes (three of our aircraft).**
   - **Cause:** the damage texture was written with a flat alpha of 0.6. That is above the 0.52 the shader ever
     reaches, so nothing was ever discarded. The "holes" were only dark dots painted into the RGB. The in-game
     check looked only for darkening.
   - **Fix:** a real hole-order alpha in the coverage bands (Build step 6), and a build check on the PNG.
8. **A generated or hand-painted damage texture can look right and still never open.**
   - **Cause:** the alpha is what cuts, and an image tool's alpha is either missing, flat, or a transparency
     mask that is not a hole order. If the importer drops alpha, nothing opens either.
   - **Fix:** generate the alpha procedurally from the model (world position per texel). Use the RGB from
     anywhere, but line it up with the alpha. Check coverage per HP step and the imported format.
9. **A dotted or light hairline at a wing fold or break line on dark liveries.**
   - **Cause:** light structure-grey end faces or rib caps behind a millimetre gap (joint flex under load, or
     an exact seam) showing through.
   - **Fix:** a dark backing behind every break and fold seam (dark end caps and a backing strip). On the
     flexing multi-part wings, also more solver passes (overview note).
10. **Holes in the wrong places after a model change.**
    - **Cause:** the rebuild re-packed the livery atlas, and the damage map was baked per atlas UV.
    - **Fix:** re-bake every skin, livery and damage texture after any geometry change. Keep an atlas-hash
      guard in the texture manifest, and re-run the coverage check on the model's own paint islands
      (`hole_cover1816.py` in our repo).
11. **Parts hollow or see-through once detached, struts floating** (overview Gotcha 5).
    - **Cause:** one-sided skins and nothing behind the split.
    - **Fix:** Build steps 1-3, and the connectivity and culled see-through checks.
12. **A 500 km/h dive only knocked the nose off** (overview Gotcha 11).
    - **Cause:** `impactDamage.threshold` is 0 on most stock part templates.
    - **Fix:** give each part its own `ImpactDamage` instance with a real threshold (we use fabric 20 g x 1.5
      and metal 30 g x 1).

## Assets
- Hole maps, soot and dent normals: procedural numpy from the model's own texel positions
  (`blender/v2/textures/hole_damage189.py`). No game data and no generated imagery go into the alpha.
- Internals: procedural Blender geometry (frames, ribs, L-stubs, tube truss, rounded tank cells). At build time
  they are drawn with the stock `aircraft_structure` material by reference, and no stock asset is copied into
  the pack.
- Stock meshes were decoded from YAML only to render them for comparison, into temp folders. Nothing from the
  game is in our repo or this note.

## Cost and time
- Hole maps: one offline round for three aircraft after the study.
- Open breaks on the latest airframe: three offline rounds (caps removed, ribs opened, engine wall opened), each
  driven by a review of our own renders. Then one short in-game detach and damage session.
- Most of the time went into checks that would have failed the earlier builds. Each new check was first run
  against the previous build to prove it catches the defect.

## Open questions
- The exact thresholds have not been measured live in game (for example with a frame capture). Only the
  bytecode reading and the visual match back them.
- Whether `_HitPoints` on custom parts is synced for remote clients in multiplayer was not tested.
- Whether a `jet_mechanical`-style tiled trim (UVs outside 0-1) or the untextured `aircraft_structure` look reads
  better on WWII airframes is a matter of taste. We use `aircraft_structure` for the stock look.
