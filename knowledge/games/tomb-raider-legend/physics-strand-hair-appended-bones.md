---
kind: game
title: "Physics strand hair on appended bones in Legend's player .drm models (an ASI solver and a .hair file)"
game: "Tomb Raider: Legend"
games_also: []
game_version: "Steam PC build, trl.exe MD5 bd846c8fb3223e53bee022bb307b21bc (NextGen renderer on), Windows 11"
platform: windows
engine: unknown
route: native-hook
tools: ["Ultimate ASI Loader + TR7-Menu-Hook 2.5 (the TRLAU-menu-hook release zip)", "MinHook 1.3.4", "MSVC 19.51 x86 + CMake + Ninja", "Blender 5.2.1", "cdcEditor 0.1.1 (Blender add-on)", "Python 3 + numpy (+ scipy for the groom previews)", "Ghidra 12.0.1 + GhidrAssistMCP", "capstone + pefile", "um backup / um publish check"]
anti_cheat: "none (single-player; Steam copy, SteamStub left untouched: runtime hooks and mods\\ files only)"
status: in-progress
agents: ["Claude Code (Opus 5.5)", "Claude Code (Fable 5.1)"]
humans: ["@skurtyyskirts"]
date: 2026-10-27
links: ["https://github.com/TheIndra55/TRLAU-menu-hook", "https://github.com/ThirteenAG/Ultimate-ASI-Loader", "https://github.com/TsudaKageyu/minhook", "https://github.com/Raq1/cdcEditor", "https://matthias-research.github.io/pages/publications/FTLHairFur.pdf"]
tags: ["hair", "physics", "cloth", "rig", "cdc-engine", "drm", "native-hook", "crash", "outfits"]
---

# Physics strand hair on appended bones in Legend's player .drm models (an ASI solver and a .hair file)

Long loose hair with per-strand physics was added to two outfits of a 2001-film-style Lara outfit pack for Tomb Raider:
Legend (the Tokyo party gown and the torn tactical dress, plus their cutscene, title and wardrobe-preview copies).
Each strand is a chain of new bones appended to the outfit's rig inside its `.drm`; a native ASI simulates the chains
every frame and writes their bone matrices, and a text `.hair` file next to the game holds every physics value, so
tuning needs no rebuild. Builds 0.9.2 and 0.9.6 ran in the real game on the human's PC and were judged from their
reports and screenshots; the final solver model (0.9.7) was built, self-checked and deployed but not yet seen in game in
these sessions. The ASI, reload and DRM animation basics are in
[film-reloads-qa-bridge-physics-mags-asi.md](film-reloads-qa-bridge-physics-mags-asi.md); this note does not repeat them.

## Setup
- Steam build of Legend (trl.exe MD5 above, image base 0x400000), Windows 11 x64, the game's NextGen renderer.
- Loader pair, ASI build chain, deploy-from-`mods\` and the save/registry backups: exactly as in the reloads note
  (Ultimate ASI Loader as `binkw32.dll` from the TR7-Menu-Hook 2.5 zip; MinHook 1.3.4; MSVC x86 + CMake + Ninja;
  `um backup create` of `Documents\Tomb Raider - Legend` before every deploy).
- Blender 5.2.1 with cdcEditor 0.1.1 to import/export the player DRMs; numpy for the groom and the solver twin.
- Ghidra 12.0.1 with the GhidrAssistMCP server for decompiles; capstone + pefile on trl.exe for byte proofs.
- All the mod's own tools (groom, assembler, solver twin, ASI) live in the author's unpublished repository; everything
  they do is described below precisely enough to rebuild.

## Route and why
Native hook plus data. The engine's own strand cloth (the `ClothSetup` rules that drive Lara's braid and the two face
strands) only knows fixed distance/plane rules on a handful of points, and a vanilla rig has no spare bones. So the
hair became new bones inside the model, posed by an ASI solver that runs right after the engine's own cloth pass.
With the ASI loaded but the simulation switched off, the hair hangs rigidly in its rest pose. Removing the ASI
entirely is **not** safe: it also removes the 256-segment buffer patch, and the 240/237-segment hair rigs then
overflow the engine's 180-segment arrays (Gotcha 1). Uninstall the hair DRMs together with the ASI.

## How the game works (what we had to learn)
- **Legacy segment records** are 0x40 bytes. A real record holds its parent (i32) at +0x38 and an HInfo pointer at
  +0x3C; virtual records (two-bone blend helpers) follow the real ones and hold index (i16), weightIndex (i16) and
  weight (f32) at +0x38; a vertex names its segment as an i16 at +10.
- **Matrix pool.** `INSTANCE_SetModel` (0x455F57 / 0x455F9B) sizes it `numSegments + numVirtSegments + 1` per buffer.
  `G2Instance_BuildVirtualTransforms` (0x4DF260) only writes `matrix[numSegments + v]` and is called right after the
  cloth pass `G2Instance_BuildClothTransforms` (0x4DF240; call sites 0x454D16 then 0x454D1B). That gap is where the hair
  solver runs: after animation, cinematic and cloth matrices, before the virtual ones.
- **Appending bones.** Add N bones at indices `B .. B+N-1` (B = the rig's segment count), all children of the head. Insert
  N vertex-less records at index B *before* the virtual records (pivot = the bone's bind position minus the head's
  absolute pivot; parent = head; HInfo null), then add N to every legacy vertex whose segment is `>= B`. Existing
  indices, animations, markers, the ClothSetup and the bone mirror stay valid. Gameplay animations key
  `min(section, anim count)` channels and reset the rest to identity + pivot; cutscenes build segments past the stream's
  bone count from the pivots, so new bones need no animation data.
- **NextGen render model (PCD9).** Skin maps are u32 and reference real segments only, 2 influences, 16 bones per batch.
  cdcEditor writes the bone table as `range(max bone + 1)` and maps a vertex group `bone_<N>` to bone N, so a hair mesh
  with groups `bone_96 .. bone_239` makes `num_bones` 240 with no other change. The 0.9.2 tactical dress went from 17
  to 28 draw batches.
- **Rigs.** Lara's main rig has 109 segments (head 5); the tactical-dress family 149 (head 5). The party gown is a
  separate 96-segment rig (head 10): lara.drm's skeleton renumbered, with an inserted upper-chest bone (4), a 5-bone
  braid chain (36-40) and a handbag bone (95). The engine applies channel i to segment i, so a 109-segment clip played
  on the 96 rig drives the wrong bones (see the outfit gotchas below).
- **Engine strand rules** (decoded from trl.exe): the face strands use joint maps whose "two-vector" mode 2 builds the
  frame from local +Y along the chain and local +Z toward a pinned helper point; without it a segment inherits its roll
  from its parent by shortest arc and the strand twists (measured up to 35-38 degrees on the forehead locks).
- **Hard per-segment limit.** The animation system's segment value arrays hold 180 segments (0x2D00 bytes = 180 x 64),
  in two statics and four scratch requests, with no bound check. Vanilla rigs stop at 149. See gotcha 1.
- Units: 1 unit is about 3 mm, z up, Lara faces -Y. Gravity used: 2,800 units/s^2 (the engine's own is ~2,700).

## The `.hair` file and the solver
The ASI reads `mods\hair\<name>.hair` (text, `;` comments, `Key=Value`). Positions are in the target rig's bind space.

```ini
[Hair]
Version=1
Objects=lara_evening,cine_lara_evening   ; object names this file drives
BaseSegments=96                          ; B: the model must have exactly B + Bones segments
Bones=144
Head=10
HeadCenter=0,6.5,474                     ; bind normals point away from it
Model=2                                  ; 1 = Verlet + global shape memory, 2 = local shape (below)
Gravity=2800
Damping=3.2                              ; 1/s, relative to the head's rigid motion, not world velocity
AirDrag=0.6
Iterations=6
Substep=0.008333
MaxSubsteps=8
Friction=0.35
EdgeCollide=1
FTLDamping=0.9
PinPoints=2                              ; points per strand pinned to the head
Inertia=0.7,0.5                          ; share of the head's linear / angular acceleration felt
BendTip=0.6                              ; local stiffness at the tip over the root link (geometric)
Cohesion=0.3,0.12                        ; slack, velocity share to the next strand
MaxSpeed=900                             ; units/s relative to the head
BendDamping=0.3
[Colliders]
C=10,sphere,0,5,476,0,5,476,15.5         ; seg, kind, a(xyz), b(xyz), radius
C=9,capsule,0,4,440,0,6,458,9.0
[Strands]
S=6,0,0,0.42,0.9,0.3                     ; points, rootStiff, tipStiff, bendStiff, radius, cohesion
P=x0,y0,z0, x1,y1,z1, ...                ; point 0 = the pinned root; points 1.. own the bones in file order
```
(The physics values above are the 0.9.7 gown's; the collider and point numbers are placeholders.)

- **Hook.** The solver runs in the post-detour of `G2Instance_BuildClothTransforms` (0x4DF240) for an instance whose
  object name is listed in a loaded file and whose model has `B + Bones` segments. Up to 4 hair instances at once.
  `dt = timeMult / 30` s clamped to 0..0.1; `n = ceil(dt / Substep)` substeps (at most MaxSubsteps), the head matrix
  interpolated per substep.
- **Reset** to the rest pose on first sight, a new instance, > 15 frames unseen, or a head jump of more than
  `ResetDistance` (80 units) or `ResetAngle` (70 degrees) in one frame (cutscene cuts, teleports).
- **Model 1 step:** Verlet with damping relative to the root's motion (`v = (vr + (dx - vr) e^(-Damping h)) e^(-AirDrag
  h)`), pinned root, a global shape memory toward the groomed rest (geometric from root to tip), one bend constraint per
  substep, then `Iterations` x (inelastic point collisions using the pre-push velocity, follow-the-leader lengths), then
  edge collisions (barycentric, once per substep) and a final follow-the-leader pass with the dynamic FTL velocity
  feedback (Mueller 2012).
- **Model 2 step** (0.9.7): each point's velocity is measured relative to the head's rigid motion through it over the last
  two substeps, plus `(1 - Inertia)` of the head's acceleration removed; each link is pulled toward its rest direction
  expressed in its parent link's *current* frame (TressFX-style local shape; straight hair stays straight and never
  coils); optional cohesion links to the same point index on the next strand; then bend-damping (velocity toward the
  neighbours' mean), a cohesion velocity share and the `MaxSpeed` cap.
- **Bone matrices.** Tangents from the chords, the normal at point 1 from `P_1 - HeadCenter`, carried along the strand by
  the double-reflection rotation-minimising frame (Wang et al. 2008); `R = F0^T F`, translation = the point.
- **Off switch and live tuning.** ini `[Hair] Sim=0` leaves the hair in its rest pose. With the JSON bridge on,
  `hair`, `hair on|off`, `hair reset`, `hair reload` and `hair set <file> <Key> <value>` tune it live.
- **Twin.** A Python copy of the solver is the reference; the ASI's self-check runs the C++ on a sample file and compares
  every tip with the twin's golden numbers (0.0002 units for Model 2).
- **Every other feature that recognises a rig by its segment count** (cutscene eye fixes keyed on 96/109/149, the braid
  restore on segments 31-40) must use the *base* count B, or it silently turns off on the hair models.

## Build steps
1. **Groom** (Python, numpy): from the target rig's bind pose and body mesh, place strand guides (a side part or a ring
   around the back of the head), fit inscribed collider spheres/capsules to the head, neck, chest, breasts, ears and
   arms, drape the guides under gravity, and build cards along each strand (tapering clumps, a crossed card for
   profiles, stray hairs) with `bone_<B+k>` weights. Write `groom.npz`, `<object>.hair` and a report.
2. **Component** (Blender 5.2.1, no armature): one mesh per material, `bone_N` vertex groups, the hair atlas.
3. **Assemble** the outfit DRM with cdcEditor (`--nextgen-only`, the rig's bone count raised by N), then insert the N
   vertex-less legacy records as described above and verify: segment and PCD9 bone counts equal `B + N`, every hair
   pivot within 1e-5 units of the groom, every hair bone a child of the head, only the model and vertex sections changed.
4. Build the copies (`cine_`, `title_`, `costume_`) with the donor's bone list so they carry the same bones.
5. Package `mods\<object>.drm` + `mods\hair\<object>.hair` + the ASI; deploy with the game closed, after `um backup`.
6. Tune in place: edit the `.hair` file (or `hair set` over the bridge) and restart.

## Verification
- Offline (every build): the solver twin replays the outfit's own animation clips (idle, walk, turn, run, jumps, flips,
  climbs, hangs) through the real rig and scores tip whip, tip speed, fold angle, tip lift above the root, stretch,
  penetration and settle time, with contact-sheet strips. 0.9.7 gown against 0.9.6: whip score 5,190 vs 16,102, tip speed
  p95 240 vs 1,265 units/s, lift 0.17 vs 2.2, worst extra fold 47 vs 160 degrees, settles 0.2 s after a stop (0.9.6
  never settled).
- ASI self-check: 1,257 checks, 0 failures at 0.9.7, including C++ vs twin.
- In game (the human's runs, 2026-10-12): 0.9.2's dresses crashed (gotcha 1); 0.9.6's hair was reported as "flailing"
  (gotcha 3). 0.9.7 was deployed with the normal-play ini and not yet reported on in these sessions.
- Not measured: frame time, memory headroom over long Tokyo sessions (each dress DRM grew ~10 MB with a 2048 atlas).

## Gotchas
1. **The Tokyo dresses crashed the game in the outfit menu preview and in gameplay.** Minidumps showed
   `g_pInputSystem` (0x1101680) zeroed, read from `UIItemModel_DoFront` and `InterpoBlend::CheckTransition`, with 240
   / 237 segment value records just before it. **Cause:** the hair rigs (96 + 144, 149 + 88) overflowed the animation
   system's 180-segment value arrays (two statics and four scratch requests, unchecked). **Fix:** an ASI feature that
   rewrites the 12 immediates and the buffer pointer (0x010FE980) to ASI-owned 256-segment buffers, all-or-nothing behind
   16 byte-checked sites. Any rig over 180 segments needs it; over 256 the buffers must grow (and two nested scratch
   requests must fit the 64 KB scratch). The groom now refuses `B + N > 256`.
2. **Hair copies broke the build with `KeyError '240'` and "unexpected changed section".** Post-steps and checks keyed on
   the segment count. **Fix:** subtract the hair bones (use B) wherever a rig is identified, and allow the model-0 and
   vertex sections to change when a spec declares extra bones.
3. **The hair "flailed": tips flung above the roots, links folded to 160 degrees, never at rest even in the idle.**
   **Cause:** 0.9.6 shipped rope strands with no bending structure, light damping and added gusts/turbulence: a 5-link
   chain like that is a chaotic multi-pendulum. The builds before it had the opposite flaw, a global shape memory toward
   the groomed rest that read as stiff. **Fix:** Model 2's local shape (each link relative to its parent link's current
   frame), damping relative to the head's rigid motion, partial inertia, cohesion and a speed cap; no turbulence.
4. **Hair dragged behind like in a headwind while she walked.** **Cause:** damping applied to the world velocity.
   **Fix:** damp only the motion relative to the root's (head's) motion, plus a small separate air drag.
5. **Strands slowly gained energy and jittered.** **Cause:** collisions that turned the push-out into velocity, and the
   bend constraint inside the iteration loop fighting the length projection. **Fix:** inelastic collisions using the
   velocity from before the push; the bend once per substep; edge collisions once per substep, barycentric.
6. **Strand frames flipped every link.** **Cause:** reflecting across the tangent difference alone is one reflection
   and mirrors the frame. **Fix:** the double-reflection rotation-minimising frame, the first reflection across the plane
   normal to the chord.
7. **At 144 fps the hair was stiffer than at 60.** **Cause:** per-substep stiffness constants. **Fix:** rescale every
   per-substep rate to the actual step, `k' = 1 - (1 - k)^(h / Substep)`.
8. **The forehead strands twisted while running.** **Cause:** the joint maps inherited roll from the parent by shortest
   arc, and some card UVs were left-handed so the shader's binormal disagreed with the exporter's tangent. **Fix:**
   two-vector joint-map mode 2 with a pinned roll helper on the head's axis at the strand's tip height, and every card
   authored with a right-handed UV frame (u = n x T, v from root to tip). Root roll fell from 35 to 3 degrees.
9. **Ears showed and the back of the gown hair had a "step", although every automated check passed.** Only opaque
   ribbons hide anything; the alpha locks do not. **Fix:** head-bound sections over each ear down to the lobe with the
   physics starting below it, the crown volume flowing into the lengths; always look at the textured bind renders before
   deploying.
10. **Front strands rooted in front of the skull fell through the face** once no shape held them. **Fix:** root them where
    the skull is underneath (the temples).
11. **The loose hair looked grey next to every other outfit's hair.** It had its own material entry (another tint, no
    roughness map) and atlas. **Fix:** copy the head hair's material entry and match the atlas to the head hair's tones.
12. **A rig change silently disabled another feature** (cutscene eye correction keyed on 96/109/149). **Fix:** every such
    test goes through the base segment count.

## Assets
Hair cards and atlases were generated procedurally in Python from tile recipes (locks, waves, splits, wisps,
flyaways); no generated images and no game textures are shipped beyond the mod's own.

## Cost and time
Four sessions between 2026-10-11 and 2026-10-13, Blender and solver jobs queued one at a time
through a CPU-slot limiter (idle priority, half the cores) after an earlier freeze from parallel heavy jobs.

## Open questions
- 0.9.7 in game: does Model 2 read as calm, straight hair in climbs and hangs without clipping into the back?
- A leash (each point kept within a distance of its rest place, like the engine's own face strands) would bound
  worst-case flips; not built in these sessions.
- Whether the bigger dress DRMs (~78 MB) stall Tokyo after repeated loads; a 1024 atlas saves ~7.5 MB each.
