---
kind: technique
title: "Skinned 3D models inside tModLoader, posed by an external engine and matched to the original frame by frame"
status: in-progress
agents: ["Claude Code and agents", "Grok"]
humans: ["DarkameMaster"]
date: 2026-10-10
links:
  - https://github.com/Ploaj/HSDLib
  - https://github.com/FNA-XNA/FNA
  - https://github.com/tModLoader/tModLoader
  - https://github.com/project-slippi/slippi-ssbm-asm
tags: [tmodloader, terraria, fna, 3d, cpu-skinning, render-target, pose, animation, dynamic-bones, lighting, oracle, ram-dump, mashup, hsd, gamecube]
---

# Skinned 3D models inside tModLoader, posed by an external engine and matched to the original frame by frame

> Terraria is a 2D sprite game, but tModLoader's FNA can skin 3D meshes on the CPU every frame, render them into
> a render target and paste the result as a player layer. In the Melee-in-Terraria project a native engine
> (Melee's decompilation as a DLL) owns the skeleton and publishes joint matrices; the mod draws the converted
> models and lights them with Terraria's world light. Matching the original frame by frame took four
> layers of checks, the last one against real Melee's RAM, which showed that some bones in Melee only move
> right because the game *draws*.

## When to use it
- Another engine (a native DLL, a decomp, a simulator) already computes the skeleton and you want its 3D
  models in Terraria instead of pre-rendered sprite sheets. Sheets rendered in Blender cost about 0.11 s per
  frame, about 90 sheets per fighter; they bake in the lighting and miss parts whose visibility depends on the
  action (Mario's cape during his side special).
- You care whether the animation is *the original's*, not just plausible. The verification ladder below is
  the reusable part.
- Not needed if the model never animates, or if a handful of pre-rendered frames is enough.

## Setup (where this was measured)
Terraria 1.4.4.9, tModLoader 2026.08.3.0 with its .NET 8 runtime and FNA 23.10.0.0 (D3D11 backend), Windows 11,
one desktop machine. Models are converted from Melee 1.02's files by an own converter (C#,
`net8.0`) built on [HSDRaw](https://github.com/Ploaj/HSDLib). The converter's output stays outside the mod, so
the `.tmod` ships code only. Every player needs their own copy of the game.

## How

### 1. The pose contract (engine → mod)
- Per joint, a 3×4 world matrix in the engine's own units; per mesh, flags (visible, hidden, inserted, metal).
  The mod computes `S = W · IBM` per joint and skins each vertex with up to 8 weights. Blocks are fixed-size and
  pointer-free, with the frame number in the header so a stale pose is detectable.
- Items (a cape, a boomerang, a grappling hook) get their own pose readout, and the engine publishes which
  model ("article") each item uses. Guessing it from the item kind drew the wrong object.
- **Use the engine's matrices as they come; never recompose them from the root.** Some actions take their
  movement from the animation's root translation, and the engine zeroes that translation once it has moved
  the fighter (a flag in the action table, stored in disk byte order in the fighter struct, switches this).
- **Use the engine's visibility, not a guess.** Melee hides and shows parts per action, and a headless engine
  has to run the draw-time visibility code even though it never draws. Before that, every mesh was hidden.
- **Reading must not change the engine**, and a read that runs engine code can. In this project one item's
  pose read allocated 64 bytes in the engine's heap. The fix and the proof (pure reads into a private buffer,
  write-protected guest memory) are in `hosting-a-decompiled-console-engine-as-a-native-dll-inside-a.md`.

### 2. Convert the models yourself, into one vertex space
- An off-the-shelf GLB export (through HSDRaw's tooling) failed on 2 of 26 models and gave Mario's cape spikes
  even in bind pose: the export emitted it as loose triangles. Writing an own converter also brought out the
  real complication. HSD, the GameCube scene graph Melee uses, doesn't keep all vertices in one space:
  - rigid meshes are in their owner joint's local space;
  - envelope (weighted) meshes owned by the skeleton root with a single full weight are in that joint's space;
  - other envelope meshes are in model space;
  - a mesh owned by any other joint adds one more matrix.
- The converter moves every vertex into model bind space, so the mod applies one formula, `v = Σ w·(W·IBM)·v`,
  to every mesh. Inverse bind matrices are copied from the source bit for bit.
- **Check the conversion against the engine, not against itself.** A second agent with its own reader found
  the IBMs bit-exact against the matrices the engine itself uses for 8 models (cape included), weights summing
  to 1 within 4e-8 and bind·IBM = I within 1.3e-6.
- **Map joints by the engine's model index, never by position in an array.** Melee's per-fighter parts table
  has gap slots (Link, Young Link, Kirby), so after a gap joint *i* isn't part *i*. One joint (the item-holding
  joint) is scaled by 1/model scale and carries no vertices.
- After conversion the 26 fighters have 46-118 joints and 2,108-6,624 vertices (implementing agent's count).

### 3. Skin on the CPU
- FNA's `SkinnedEffect` is out: `MaxBones` is 72 (75 bones throws `ArgumentException`) and it takes 4 weights
  per vertex. Melee fighters have up to 118 joints, and Kirby's meshes use 6 influences.
- On one thread, a real lab run measured the whole frame (skinning, lighting, render) at 0.17-0.21 ms for Mario
  and 0.23-0.27 ms for Link, skinning itself 0.10-0.13 ms. Skin only visible meshes and keep arrays
  preallocated. At most two fighters per frame have been measured.

### 4. Where to draw: `Main.OnPreDraw`, one render target per fighter
- `Main.OnPreDraw` runs at the start of Terraria's draw, before any `SpriteBatch` is open, which makes it a safe
  place to switch render targets. It worked first time; no detour of `Main.DoDraw` was needed.
- One `RenderTarget2D` per fighter slot (`Depth24`, `PreserveContents`), sized to the vertex bounds plus 1.5
  units and rounded up to 32 px so it isn't recreated every frame. `BasicEffect`, `CullNone`, one sampler per GX
  wrap mode (clamp, repeat, mirror), an orthographic camera matching the guest's axes (Melee: +X right, +Y up,
  looking down −Z). Facing then comes from the matrices.
- Render at (3.5 px per unit × `Main.GameViewMatrix.Zoom`) and let the `PlayerDrawLayer` draw at `1/zoom`. One
  texel is one screen pixel at any zoom; live zoom changes resize the target.
- **Composite premultiplied.** Terraria composes premultiplied colour; a target drawn with
  `BlendState.NonPremultiplied` squared the alpha on edges and translucent parts.
- **Restore the device state in a `finally`** (render targets, blend, depth-stencil, rasterizer,
  `SamplerStates[0]`, viewport, scissor) and check it by reference after every frame. A second agent's lab runs
  found it restored on 3,097/3,097 and 3,064/3,064 frames. Not covered: `Textures[0]`, the bound shader, and a
  device reset.
- **Never leave the player invisible.** When the engine is off, a model is missing or Terraria owns the movement
  (mount, grappling hook, bed, teleport), draw the normal Terraria player and show one English notice per
  reason. Warm model files on a background thread before first use: without it a fighter's first appearance
  hitched 132-169 ms, and a cold synchronous preload still took up to 203 ms. A second agent measured the
  background warm-up at 20.5 MB in 52 ms with a warm file cache (304 ms in the implementing agent's run).

### 5. Materials
- About 90% of Melee's materials are "texture × diffuse light", which `BasicEffect` covers. The rest follows
  HSD's texture-stage rules: Link's shield came out grey until the specular light map stopped being painted as
  colour. Mr. Game & Watch is flat black vertex colour, set by his own init code. Not implemented: two blend
  modes (RGB mask, subtract); approximated: partial blends and spherical reflection maps.
- **Check the original before "fixing" a colour.** Mario's cape renders gold. A project note said it should be
  red; in Melee it is yellow, and the model's only texture is gold. The note was wrong, not the renderer.

### 6. Terraria's light on a 3D model
- Sample `Lighting.GetColor` at 5 points around the body (centre, left, right, above, below), bilinear between
  tiles, side samples at least 3 tiles out, smoothed over 0.10 s.
- Drive the `BasicEffect` lights from it: the guest's own rig (ambient plus key) scaled by the average world
  light, plus a fill light from the brighter side.
  - Measure brightness on the **maximum channel**, not luminance: a blue torch is bright in B and nearly black
    in luminance.
  - Point the fill along the normalised light gradient plus a bias towards the screen; without it, a torch on
    the left lit the fighter almost from the front.
- Offer modes: guest only, Terraria, and mixed with a minimum brightness (0.30). A second agent re-ran Link:
  in uniform daylight all three give exactly the guest's rig; in a dark room the render target's brightness was
  70.5 (guest only), 2.7 (Terraria) and 20.8 (mixed); a blue torch tints the side facing it.
- Terraria's own player visuals (buffs that turn the player to stone, debuff dust, the vanilla body) leaked
  over the fighter. Clear those draw flags (19 of them) for the fighter's draw and restore them after; the IL
  shows tModLoader calls the restoring hook unconditionally.

### 7. Matching the animation frame by frame: four layers
1. **The simulation itself is the original's.** The engine replays real recordings bit for bit (see the
   bit-exact technique note), so the action and the animation frame being drawn are Melee's.
2. **Drawing changes nothing.** Trace the engine with the 3D renderer on and off: 0 differences in 37 fields
   × 2,892 rows for Mario and Link (real lab runs, re-run by a second agent), and identical traces on 14 of 14
   fighters in a later batch.
3. **The pose equals the animation data.** An own decoder reads the animation tracks straight from the
   fighter's `.dat` (keyframes, Hermite splines) and evaluates them at the engine's frame. Mario's translation
   matched within 6.6e-6 with frame offset 0; in actions without blending, a second agent measured Link and
   Peach within 1e-4. **Make sure the test can fail:** a −1 frame offset gives 1e-2 to 1e-3, and a +0.001
   mutation drops a fighter from 4 clean actions to 0. Parts driven by dynamics or blending do not match a
   raw track (up to about 1.07 on single parts), which leads to layer 4. Euler angles have two equivalent
   solutions; compare both or you'll see false errors of 2.0.
4. **The pose equals real Melee's RAM.** Run the same inputs in real Melee under Dolphin and read the joint
   matrices and mesh visibility from emulated memory every frame. An own read-only reader (`OpenProcess`,
   `VirtualQueryEx`, `ReadProcessMemory`) finds the 32 MB main-RAM view by the game ID at its start, the same
   method as Dolphin Memory Engine. Blocking input and slowing emulation didn't pause this emulator build, so
   the reader sends the next frame's input first and polls until the state is post-render and stable on two
   reads. Prove the frame alignment: static joints match to 1.9e-6 at offset 0 and are about 1.1 units off at
   ±1. Check each dump against the recording's own state for that frame, hitlag included.

What layer 4 found:
- Two pose readers disagreed. A **pure** read (rebuild matrices and visibility from simulation state into a
  private buffer) and the old **persistent** read (run the scene graph's matrix setup on live state, which
  leaves matrices and dirty flags behind like a real draw).
- **Matrices followed the persistent read; visibility followed the pure one.** Fox's tail: median error 3.4e-5
  (persistent) against 0.024 (pure, max 6.35 units). Marth's cape: worst 0.061 against 10.24. But the persistent read
  showed stale meshes for hundreds of frames (Sheik 2,039, Kirby's faces 865, Marth 613); the pure read, none.
- **Cause.** When a dynamic chain (tail, cape, hair) switches on, Melee seeds each link from the joint's world
  matrix *as the previous frame's render left it*, without recomputing it. Headless, that matrix is stale, so
  the tail snaps towards an old position and the solver carries the error for several frames. Visibility is the
  opposite: each frame Melee's shadow pass resets the hidden group and the next draw step re-applies the
  current variant, so state that persists across frames is wrong.
- **Slippi already fixed half of this.** Its required `DynamicsFix` code (in
  [slippi-ssbm-asm](https://github.com/project-slippi/slippi-ssbm-asm)) runs the matrix setup over each
  fighter's joint tree at the end of its dynamics update, because skipped renders (fast-forward, rollback)
  hit the same bug. The oracle runs it, so the engine now does too.
- **The other half is a draw-effects step.** At the end of each engine frame, replay the matrix work of one
  frame of fighter drawing without any graphics calls, in Melee's order: the magnifier for off-screen fighters,
  the shadow pass (which walks every fighter, on screen or not), then the main render pass. Persist matrices,
  dirty bits and lazily allocated scale/constraint results; never persist visibility. In hitlag Melee skips the
  dynamics update, and its render leaves exactly three geometry-free leaf joints of Fox dirty; Slippi's code
  alone left 44-48 dirty, the full replay matches the 3.
- **Result, verified by a second agent from the raw dumps:** dirty bits 0 mismatches; visibility 0 failures;
  dynamic matrices Fox median 3.6e-5 (worst 1.33, during one up-smash), Roy worst 0.048, Marth worst 0.061; the 29-recording
  replay bench byte-identical; an emulated rollback 0 of 201 frames off; pose reads still pure; +0.026 ms per
  engine step. Not dumped: Peach, Zelda, Mewtwo and Bowser (synthetic checks only).

### 8. Sub-entities
Ice Climbers' Nana is a second entity in the same slot. Gate a "sub-entity pose" read on the entity's kind,
not on a "sub fighter" flag: Zelda's inactive Sheik carries the same flag. (Implemented and bench-tested by
one agent, then verified synthetically by a second agent with its own DLL: the 29-recording bench stayed
byte-identical, reads were pure (checked with four positive controls) and the rule holds for Zelda and Sheik.
Not run in game.)

## Verification
- **Real runs in the lab tModLoader, captures looked at:** 17 fighters drawn in 3D (Mario, Dr. Mario, Luigi,
  Bowser, Peach, Yoshi, Donkey Kong, Captain Falcon, Ganondorf, Falco, Fox, Ness, Popo, Kirby, Link, Samus, Pichu).
  Drawing never changed the simulation; 12 of the 15 in the batch matched real Melee on every comparable row (the
  other 3 differ at stage edges or by a random item, known beforehand). Lighting re-run for Link only.
- **Never run in the lab:** Zelda, Sheik, Young Link, Pikachu, Jigglypuff, Mewtwo, Mr. Game & Watch, Marth, Roy,
  and Nana. The project's owner reports having seen all 26 in 3D in the game; that is a report, not a lab
  record. Their poses were checked against the animation data in a synthetic host, at least 3 clean actions
  each (implementing agent; a second agent re-ran 3 of them).
- **Real Melee RAM:** Fox, Falco, Marth, Roy, Sheik and Kirby, one recording each (see layer 4).
- **Not verified:** more than 2 fighters drawn per frame; Kirby's copy-ability hats; most items (bombs, the
  hookshot chain); the non-diffuse materials; the Marth/Roy cape during their neutral special (about 15 and 9
  units off for every reader, open); fullscreen, screen filters, device reset, other mods that draw render
  targets; hot reload.

## Gotchas
1. **Reading a pose changed the simulation.** **Symptom:** the trace differed only in the engine's heap usage,
   +64 B from the first frame of one item. **Cause:** the scene graph lazily allocates a scale block inside its
   matrix setup (not the envelope matrices first suspected: that item is fully rigid). **Fix:** pure reads into
   private memory, proven with write-protected guest memory.
2. **Every mesh was hidden.** **Cause:** visibility is decided in draw-time code the headless engine never ran.
   **Fix:** run the visibility replay as part of the pose read.
3. **Fox's tail and Marth's cape flung out when they switched on.** **Cause:** the dynamics seed from matrices
   that only a render refreshes. **Fix:** Slippi's DynamicsFix plus the draw-effects step (layer 4).
4. **Stale faces and meshes after fixing the tail.** **Cause:** persisting visibility along with matrices.
   **Fix:** persist matrices, keep visibility pure.
5. **"Unexplained" one-frame mismatches in the RAM dumps.** **Cause:** the reader grabbed a frame after logic and
   before render; in hitlag the joint values freeze, so the "next logic" detector missed it. **Fix:** validate
   each dump against the recording's hitlag and percent for that frame.
6. **Spiky cape from a GLB export.** **Cause:** the export emitted loose triangles. **Fix:** an own converter,
   and an image check of every mesh in bind pose.
7. **`SkinnedEffect` looked like the obvious route.** **Cause:** 72-bone and 4-weight limits. **Fix:** CPU
   skinning; it's cheap at this vertex count.
8. **The fighter blinked and went dark at night.** **Cause:** the lab made the player immune every frame
   (Terraria draws the immune blink), and the old sprites were tinted by tile light. **Fix:** `immuneNoBlink` in
   the lab, forced daytime there, and world lighting as an explicit mode.
9. **One frame without a body when mounting or teleporting.** **Cause:** the draw keyed its per-tick decision on
   `Main.GameUpdateCount`, which increments *after* the player update, so it reused the previous tick's decision.
   **Fix (proposed, not applied yet):** key on the count of the tick that just ran.
10. **Dark fringes, and translucent parts too dark.** **Cause:** non-premultiplied blending into a
    premultiplied host. **Fix:** composite with a premultiplied "over".

## Seen in
- [Super Smash Bros. Melee's engine inside Terraria](../games/terraria/super-smash-bros-melee-s-decompiled-engine-inside-terraria-a.md)
- Related: `hosting-a-decompiled-console-engine-as-a-native-dll-inside-a.md` (the engine side and pure reads),
  `geometry-transfer-host-draws-guest-meshes.md` (the host draws guest meshes and must restore its render
  state), `frame-compositing-depth-and-pose-sync.md` (pose timing), `oracles-how-agents-know-a-mod-works.md`
  (trace replay), the Fal Arsenal note for tModLoader basics.

## Credits
- [HSDLib / HSDRaw](https://github.com/Ploaj/HSDLib) by Ploaj: the HSD reader under the converter.
- [FNA](https://github.com/FNA-XNA/FNA) and [tModLoader](https://github.com/tModLoader/tModLoader).
- [Project Slippi](https://github.com/project-slippi): `DynamicsFix` and the recordings format; Slippi's
  Dolphin ([Ishiiruka](https://github.com/project-slippi/Ishiiruka)) ran the oracle; [Dolphin](https://dolphin-emu.org/).
- [melee-pc](https://github.com/999sian/melee-pc) and [doldecomp/melee](https://github.com/doldecomp/melee).
- Built with AI agents: Claude Code and its agents implemented and verified (each result re-run by a different
  agent); Grok found the DynamicsFix connection while reviewing Slippi's codes read-only.
