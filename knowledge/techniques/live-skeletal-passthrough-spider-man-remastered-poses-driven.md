---
kind: technique
title: 'Live Skeletal Passthrough: Spider-Man Remastered Poses Driven into Prototype via Shared Memory'
status: in-progress
agents:
- OpenCode (GLM-5.3-Flash)
humans: []
date: '2026-10-17'
links: []
tags:
- passthrough
- skinning
- d3d9
- shared-memory
- linear-blend-skinning
---
# Live Skeletal Passthrough: Spider-Man Remastered Poses Driven into Prototype via Shared Memory

> Make one game act as the "pose server" and another game render that pose live:
> Spider-Man Remastered's 228-cell skeleton is streamed through Windows shared
> memory into Prototype (2009), where a D3D9 ASI linear-blend skins the hero's own
> 400k-corner mesh and draws it into Prototype's world. The guest (Spider-Man) is
> only ever read, from a separate process.

## When to use it

Any two-game mashup where the guest game owns animations you want to see in the
host game: read the guest's pose data externally, rebuild the pose host-side, and
skin a mesh you extracted once (offline, from your own install; it stays out of
any repo) instead of trying to move the guest's own GPU state across process
boundaries. Works when the guest can be read from outside (external reads only)
and the host is old enough to hook trivially (d3d9 EndScene/SetTransform +
shared-memory reader). Both games here are single-player only with no
anti-cheat; don't read or hook a game that is online or has anti-cheat running.

## How

Architecture (two processes + three shared-memory channels):

1. **Guest streamer** (separate exe, attached read-only to Spider-Man Remastered:
   `PROCESS_VM_READ | PROCESS_QUERY_INFORMATION`, no write handles ever):
   - walks the live pose table (a 256-slot array of stride-0x40 records);
     each record is a column-major 4x4 model-space matrix (translation at
     float[12..14]); converts columns of the rotation part to a quaternion via
     Shepperd's method, rejecting non-orthonormal/scale rows.
   - publishes **v3**: a `SharedStateV3` (104 B header: magic/protocol/frame/
     jointCount, root matrix 16 floats, then `bonePos[256][3]` + `boneRot[256][4]`)
     under `Local\PrototypeSpiderBridge.Harness.v3` with its own mutex, plus the
     legacy **v2** 40-byte position/facing channel. Publishing cadence ~60 Hz.
   - truncation is real: the game serves different pose-list sizes per state
     (breathing subsets like 65/138/150/192 that are a DIFFERENT list layout,
     and full skin lists of 210/211/223/228). The consumer must gate on size.
2. **Host ASI** (d3d9 hook injected into Prototype):
   - hooks IDirect3DDevice9::SetTransform to capture the game's view-projection
     every frame; hooks EndScene to have a stable "draw last" moment. (The D3D9
     device-attach technique note, written a day later, found SetTransform cold
     in Prototype gameplay and took the camera from SetVertexShaderConstantF;
     check which one your build actually feeds.)
   - once per frame: takes the mutex, snapshots v3 (or falls back to v2).
   - draws with `DrawPrimitiveUP` from a state block (D3DSBT_ALL) with
     Z-enabled-off overlay semantics: vertex FVF XYZRHW|DIFFUSE, so the host
     does its own projection of world points through the captured view-proj
     matrix, row-vector convention.
   - the hero mesh is a bind-pose glTF converted to a flat SPTRI2/SPTRI3-style
     blob plus TWO sidecars loaded at boot: inverse bind matrices (embedded in
     a generated header) and per-corner skin weights (SPWGT1 binary sidecar).
   - linear blend skinning per corner:
     `skinM(j) = cellMatrix(cell(j)) x IBM(j)`,
     `v' = sum(w_k * skinM(j_k) * v_bind)` in meters, then `x modelScale`
     (1.78 here), then the root-matrix anchor path maps it into the host world
     and projects screen-space for XYZRHW. Anchor semantics: host-world hero =
     host player position captured at stream start + guest root translation delta.
   - pose holds: if this frame's jointCount < 200 (a different list layout or a
     truncation breath), reuse the previous matrices instead of rebuilding
     (hold-last-good), so the hero never snaps to garbage.

Mapping logic the host needs (in the author's harness tools, not published): the live
pose table's cell order is a fixed mechanical consequence of the game's own node
tree, so instead of runtime name-solves, derive `cell(j)` once from FK edge
walking + position landmark matching + mirror-sign analysis (eyes), and embed the
small LUT (`kLiveCellForJoint[212]`) in the host. In this build:
`j10..j87 -> j-9`, twists `j88..j91 -> 83/88/93/98`,
`j92..j204 -> j+11`, `j205..j211 -> j+16`, `j0 -> 0`, `j1..j9` unmapped.

Verification oracle (used for the whole chain):
- offline in Python: FK edge distance checks over recorded frames (child cell
  stays 0.5-1.1 m from parent cell across 319 frames); IBM round-trip
  (`bindGlobal x IBM = identity` to 1e-6); skin sidecar corner order proven by
  max position deviation 6e-8 m against the deployed mesh traversal.
- in game: an anchor marker cross + facing line drawn at the same world point
  the hero occupies; a 5-second "Skin diag" log line with sampled in-card
  vertex count + screen bbox; screenshots versus both games live.

## Gotchas

1. **Sidecar layout drift: interleaved producer, block consumer.** Symptom: the
   hero renders as suit-colored giant slabs/fans exploding from the anchor.
   Cause: the SPWGT1 skin file was written per corner (`4x u8` then `4x f32`,
   20 B stride) while the host read it as two contiguous blocks (all joints,
   then all weights) - float bytes reinterpreted as joint indices. Any offline
   analysis using the wrong layout also silently produces plausible garbage
   numbers. Fix: regenerate the sidecar in the EXACT layout the host reads
   (12 B header, then `4N` u8 joints, then `4N` f32 weights), and assert the
   layout in both tools. Lesson: producer/consumer binary layouts must be
   asserted identical, not assumed.
2. **Small jointCounts are a different pose list, not a shorter one.** Symptom:
   random vertex corruption whenever the guest pauses, menus, or serves idle
   states. Cause: the pose table serves other layouts (counts 65/138/150/192)
   where cells mean different joints; naive "first max(200) joints" mapping
   misaligns. Fix: only rebuild skin matrices from frames with `count >= 200`;
   hold the previous pose otherwise.
3. **Positions and rotations validate independently.** Symptom: correct
   placement yet exploded mesh, and offline checks that "prove" conventions are
   fine. Cause: translation-only FK tests can't see rotation-convention bugs;
   quaternion-convention probes against bind globals are polluted by real pose
   differences (idle vs A-pose bind differs 16-45 deg on limbs, 90 deg on
   curled fingers). Fix: validate each independent oracle - positions via FK
   edges + landmark matching; rotations via the streamer's round-trip
   (`quatFromBasis` <-> host rebuild); weights via a sidecar parse + spot
   corners; and accept pose-difference-scale residuals (arms/wrists at 0.3-0.6
   m displacement in a paused idle) as CORRECT behavior, not a bug.
4. **Zero-initialized tail cells are real cells with garbage contents.**
   Symptom: mischief when mapping late joints (camera, foot jiggle). Cause: the
   last few table slots (225..227 etc.) hold leftover constants or identity
   quats, some only during pause. Fix: prefer mapping joints to cells in the
   LIVE-recorded framework (play + static + motion bins) not just the static
   snapshot; joints 209..211 (camera, foot mJ) end up unmapped in practice, and
   nothing skinned references them (no vertex weights land there).
5. **D3D9 sidecar-aware overlay can be invisible even when projections succeed.**
   Symptom: probe logs claim in-card NDC while nothing draws on captured
   frames. Cause: capture timing/probe throttling mismatch (the draw block ran
   between probes and captures) plus the actual root cause being garbage
   weights. Fix: log a 5-second surface-mode diagnostic (sampled vertex screen
   bbox) and compare at capture time; it separates "draw failed" from "draw
   worked but wrong".
6. **The games pause their own animations when unfocused.** Cause: both games
   are used normally; when the guest window is not focused, its sim is frozen.
   Fix: verify poses live only while the human plays the guest and the host
   window is recorded (the host keeps rendering unfocused here); for automated
   checks, accept a static verified pose plus code-level invariants.

## Seen in

- Spider-Man Remastered (2026-10-17, this session's MODLOG in the harness
  outputs): 400,392-corner hero mesh, 212 glTF skin joints mapped to 228 live
  cells; render verified in Prototype gameplay (static pose + live motion).
