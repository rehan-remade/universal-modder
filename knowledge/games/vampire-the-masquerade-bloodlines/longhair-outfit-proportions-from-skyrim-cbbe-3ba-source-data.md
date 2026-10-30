---
kind: game
title: "Bloodlines MDL2531 outfit transfer and native secondary motion: bind frames, pose provenance and receiver flags"
game: "Vampire: The Masquerade - Bloodlines"
games_also: ["The Elder Scrolls V: Skyrim Special Edition"]
game_version: "Local Version.inf 1.2; enabled Unofficial Patch Plus metadata 11.5.46.0; Fashionista portable MO2 profile"
platform: windows
engine: source
route: native-hook
tools: ["Blender 4.5.15 LTS", "BodySlide/Outfit Studio 5.8.1", "SourceIO MDL2531/VTX107 readers", "MO2 2.5.2", "Zig 0.13.0 (x86)", "Bullet 3.25", "Python/NumPy", "srctools"]
anti_cheat: "Single-player Bloodlines instance; no anti-cheat signature found in bounded local scan, no multiplayer interaction or protection/ownership bypass"
status: in-progress
agents: ["OpenCode (GPT-6.1 Sol)", "OpenCode (GPT-6.1 Sol Fast)", "OpenCode (GPT-6 Astra)", "OpenCode (GPT-6 Astra Fast)"]
humans: ["Kokuru"]
date: 2026-10-28
links:
  - "https://github.com/REDxEYE/SourceIO/tree/fe24260b97ac03b899d9b5d4f0fd7b34772f3647"
  - "https://github.com/ousnius/BodySlide-and-Outfit-Studio/blob/59fca3a4787153e7349aa0fb01c716235f9f9b27/src/components/Automorph.cpp"
  - "https://github.com/ousnius/BodySlide-and-Outfit-Studio/wiki/Conversion-references-and-using-them"
  - "https://github.com/ousnius/BodySlide-and-Outfit-Studio/wiki/Making-a-new-conversion-reference-%28external-tools%29"
  - "https://github.com/ZeqMacaw/Crowbar/blob/0d46f3b6a694b74453db407c72c12a9685d8eb1d/Crowbar/Core/GameModel/SourceModel2531/SourceMdlFile2531.vb"
  - "https://github.com/c6-dev/vtmb-tweaks/blob/5d9ea803a35261fb2ad120737d8d2419ce893e72/vtmb-tweaks/dllmain.cpp"
  - "https://github.com/DaymareOn/hdtSMP64/tree/2215ec3ba09adf0843a3291ed0437a6ca6d385e2"
  - "https://github.com/bulletphysics/bullet3/tree/2c204c49e56ed15ec5fcfa71d199ab6d6570b3f5"
tags: [mdl2531, vtx107, source, body-proportions, conversion-carrier, animation, secondary-motion, native-hook, pose-provenance, mo2, verification]
---

# Bloodlines outfit transfer and native secondary motion

> A private asset-conversion and x86 runtime prototype transferred supplied
> CBBE/3BA proportions onto an existing LongHair outfit, then added solver-backed
> secondary motion. The human accepted the motion, its smoothness and the absence of
> visible distortion in the sampled motion review. The project remains in progress:
> contacts, broad animation/control coverage and an independent-outfit test are
> not complete, and this note is not a distributable mod or turnkey converter.

**Read this before** adding bones to a Bloodlines model or diagnosing motion that
passes an offline skinning test but breaks in game. The strongest findings are the
native rotation flag, repeated-pose feedback, and the difference between a disk
model, its initialized cache and its actual animated baseline.

## Setup

- Windows, **Bloodlines (2004), x86**. Local `Version.inf` reported **1.2**;
  enabled Unofficial Patch Plus (Wesp5) metadata reported **11.5.46.0**. These are
  the recorded local identifiers, not a claim to identify every DLL by that label.
- Existing **Fashionista portable MO2 2.5.2** installation and engine fixes were
  retained. The configured launch used `Vampire.exe -game Unofficial_Patch -window`.
- The supplied **LongHair** female Toreador outfit had armor0-3 variants. Its local
  metadata did not identify an authenticated author/release/download source.
  Files were privately hash-pinned; no universal LongHair version is inferred.
- Source inputs were locally labelled **CBBE 2.0.3 / 3BA 2.48**, with **BodySlide /
  Outfit Studio 5.8.1**. The full authoring reference and preset were supplied
  separately. Permission to use them for this private experiment is not permission
  to redistribute them.
- **What stays private:** everything from the Skyrim side (the CBBE/3BA reference,
  the preset, BodySlide's morph data and the shapes derived from them) comes from
  the user's own installs, and the converted LongHair models stay in the private
  build. CBBE (Ousnius and Caliente), CBBE 3BA (Acro748) and BodySlide are community
  projects with their own permissions, and so is the LongHair outfit: a converted
  outfit can only be published with their authors' permission and credit, and
  nothing from Skyrim's own files ships.
- **Blender 4.5.15 LTS**, build `5afeabba6097`; **Zig 0.13.0**, x86 target;
  **Bullet 3.25**, commit `2c204c49e56ed15ec5fcfa71d199ab6d6570b3f5`.
- **SourceIO** readers pinned to `fe24260b97ac03b899d9b5d4f0fd7b34772f3647`;
  Outfit Studio conform reference pinned to
  `59fca3a4787153e7349aa0fb01c716235f9f9b27`.

Native rotation-flag observations below are bound to the inspected `client.dll`
SHA-256 `e88beae0dd03af06493c71c5e8d87a6993b54e590cb6ad37cd3513c588582870`.
No executable bytes, native instruction listings or process-memory captures are
included. Nothing in this work removed DRM or changed an ownership check.

## Route and why

First establish a native **asset-only proportion slice**, then treat rigging,
animation, physics and contacts as separate acceptance gates. Source anatomy and
target outfit anatomy have different rest shapes: adding the same sparse deltas
to unrelated targets is not an equivalent proportion transfer.

Use the actual source reference and a source-topology conversion carrier fitted
to the target base. Transfer the prescribed-shape minus carrier displacement,
following the public Outfit Studio conform mechanism. Preserve target materials,
UV ownership, attachments and native animation unless a separate reversible
experiment requires a change. Do not apply the preset again to a baked output.

The existing native chest driver provided rotational motion but did not deliver
the independent receiver translation/range sought in the private prototype. A
separately authorized, version-bound **in-process x86 adapter** and Bullet-backed
solver were therefore tested. This is not Skyrim DLL compatibility with Bloodlines.
The native actor/model binding, compiled plugin and converted assets are not
released here; build steps below describe the method and gates, not an installer.

## How the game works (what we had to learn)

### Actual model format, stored weights and variant authority

The supplied models were **IDST version 2531**, with **VTX version 107**, not a
modern Source MDL layout. The pinned
[SourceIO readers](https://github.com/REDxEYE/SourceIO/tree/fe24260b97ac03b899d9b5d4f0fd7b34772f3647)
and [Crowbar's version-specific reader](https://github.com/ZeqMacaw/Crowbar/blob/0d46f3b6a694b74453db407c72c12a9685d8eb1d/Crowbar/Core/GameModel/SourceModel2531/SourceMdlFile2531.vb)
are useful references; an importer is not an exporter.

Each supplied model decoded to **8,388 vertices, 66 bones and 7 LODs**. The tested
float vertex representation used **44-byte records** with position, normal, UV,
three stored byte weights and int16 bone indices. **70 records** had unresolved
weight encodings. They were preserved rather than normalized or silently omitted
from a claimed complete skin certificate.

Armor0/1/3 geometry matched in the supplied set; armor2's dress differed despite
sharing topology-related fields. Its texture references also reused some armor0
face/hair resources. Follow actual material paths and compare variants before
copying positions. A later mesh/rig expansion required both VTX companions, their
hardware influence palettes and all affected LODs to be rebuilt and reopened.

Independent frames matter: compose world bind frames from local positions,
quaternions and parents, then compare the separately stored inverse binds. Also
check the **actual editor bone frames**. Wrong bind/inverse pairs can cancel at
rest; a zero-skinning test alone missed broken armature orientations.

The source preset contained **88 explicit signed `big` entries**: 86 position
controls and 2 UV-only entries. `small`, missing defaults and actor-weight blending
were not imported. UV-only controls were recorded, not misinterpreted as XYZ data
for the target's unrelated atlas. The complete authoring reference was not the
same mesh/skeleton as the smaller main 3BA render body.

### Native driver discovery and animation provenance

Zero generic procedural-rule types did not mean zero native physics: this model
family also had a separate auxiliary-chain consumer. Discover the actual readers
and writers rather than interpreting an empty parser field as absent behavior.

A later native hook's call count also did not mean a new animation pose. Some
same-clock passes reused the adapter's previously published receiver matrices while
unrelated limb matrices changed. Treating those outputs as fresh animation added
motion repeatedly. A guard relative to the contaminated incoming pose then tested
only incremental deformation, missing cumulative error from the real animation.

The correction retained true animation and the last committed output separately.
Recover an owned baseline only with matching actor/resource/buffer identity, exact
last-output recognition and unchanged declared protected inputs. Preserve unrelated
current animation and still compare actual input when checking post-solve races.
Partial old/new output blocks must not qualify as an exact repeat.

### Bone flags can change native composition without changing the hierarchy

The working pre-expansion rig had **72 bones**, including six solver receivers.
A directional transfer experiment added **162 identity-local children of torso
bone 9**, producing **234 bones**. It copied the torso's inverse bind and flags.
The native export/reopen, ordinary hierarchy audit, solver fixtures, initialized
model admission and plugin telemetry all passed, but the game showed severe
chest/neckline stretching even before solver displacement.

For these 160-byte native bone records, the uint32 flags field is at **`+0x88`**
(the MDL 2531 bone layout SourceIO's reader uses: no Euler rotation or alignment
quaternion, so the flags follow the pose-to-bone matrix directly).
In the inspected native consumer, **flag mask `0x2`** selected **actor/root-relative
rotation** while translation still followed the parent. Clearing that bit selected
full parent-relative composition. Copying torso flags `0xfffe` onto identity-local
receivers was therefore wrong; their stored torso-copy inverse binds required the
parent-relative behavior. Changing only that flag on the **added** bones to
`0xfffc` fixed the mismatch. Original bones' flags/animations were left alone.

The observed composition contract, expressed mathematically rather than copied
from the executable, is:

- Flag clear: `R_world = R_parent * R_local`.
- Flag set: `R_world = R_actor * R_local`.
- Both paths: `t_world = R_parent * t_local + t_parent`.

These equations use column vectors; `R` is the transform's 3×3 linear block and
`t` its translation. They describe composition, not an on-disk matrix storage order.
Mask `0x2` means zero-based bit 1, not mask `0x4`. Keep the other flag bits intact.

Thus an identity-local child must match its parent's full animated matrix only
on the parent-relative path. This is a direct regression to check before tuning
any spring or weight: compare actual receiver and parent matrices with motion
disabled, then repeat with the solver active using the separately captured baseline.

This is a build-specific observed flag meaning, not a universal Source enum or
permission to clear flags on an arbitrary rig. Private negative-control testing
replayed the inspected composition arithmetic, then the correction was checked
against true live receiver baselines. The code/data used for that private native
analysis are not part of this contribution.

For a new implementation, an informative synthetic case uses **different actor
and parent rotations**, a nonidentity local rotation and a nonzero local translation.
An all-identity fixture cannot distinguish the two paths. Check rotation and
translation separately, then the complete matrix; use the actual native result as
the oracle rather than comparing two functions built on the same hierarchy assumption.
This is a recommended fixture design; the measured synthetic/live counts appear below.

### Initialized cache, call order and timing are separate contracts

- The engine-initialized model is not necessarily byte-identical to the disk MDL.
  Identify actual initializer writes and compare a precisely predicted initialized
  form. Validate runtime registry indices/handles by their named resources instead
  of ignoring every differing byte. Relocated tables need relocated expectations.
- Stored record order was not linked-list traversal order in this build. The
  production adapter had to preserve actual native traversal and prove that later
  hair writes were disjoint from every solver/guard dependency.
- Native limb animation included slight affine contraction. Retain valid native
  affine baselines; requiring every bone to be perfectly rigid rejected legitimate
  animation. Solver anchors and owned receiver/output requirements remain separate.
- A tick budget must count complete ticks due, not mistake a fractional remainder
  for an extra tick. Replay with the captured remainder; a zero-initialized replay
  missed the observed false reset.
- A held fixed-tick **world-space** result against newer animation caused visible
  stepping. Interpolating equilibrium-local histories and reapplying them to current
  animation improved presentation, at approximately one 60 Hz tick of latency
  (**16.67 ms**). This is not an overall game-frame-rate claim.

## Build steps

1. Back up the actual active saves, settings, mod profile and overridden files.
   Resolve MO2's selected game plugin and effective providers; default save/config
   paths were wrong for this installation.
2. Read the actual native format and all outfit variants. Preserve unsupported
   records and establish independent source/target bone frames before posing.
3. Evaluate the explicit source preset once. Fit a source-topology carrier to the
   target base, transfer carrier-to-preset displacement, and inspect front, both
   three-quarter views, both profiles and underside before export.
4. Reopen native output, check original authority fields and affected LODs, and
   render original/converted data with equal cameras. Separate wrong fabric/UV
   ownership from geometric folds; smoothing does not repair the wrong atlas region.
5. Install a single reversible override only after review. Keep the original outfit
   and modlist fixes. Verify effective files, then use a human-controlled game test.
6. For a separately authorized native runtime experiment, establish ownership/read
   sets, lifecycle identity, true-animation provenance, all-or-nothing publication,
   exact disabled recovery and cumulative deformation checks before tuning amplitude.
   Source simulator configuration must be interpreted in its own frames/units.
7. Test added bones' **actual native animated matrices** before physics quality.
   Correct an asset/composition mismatch at its cause rather than adding compensating
   solver offsets. Preserve a known failed candidate as a negative control.
8. After every candidate change, regenerate strict model/cache bindings and keep
   an exact rollback. Verify deployment, live baseline, cumulative deformation,
   visible appearance and human motion feel separately.

### Minimal diagnostic record for another runtime

Keep these records together when investigating a failed frame:

| Record | Question it answers |
|---|---|
| Effective disk model hash and predicted initialized-cache identity | Did this actor actually use this candidate? |
| Actor/resource/buffer identity and callback time | Is this the same instance and pass, rather than merely the same model name? |
| Incoming matrices, separately retained animation baseline and last committed output | Is incoming data fresh animation, an exact repeat or a mixed block? |
| Parent and added-receiver matrices before solver displacement | Is native composition already wrong? |
| Proposed output, committed output and protected-input comparison | Was the checked result the one published, with unchanged dependencies? |
| Declared guard face set and its maximum cumulative bound | What geometry was covered, and relative to which baseline? |

This is a suggested reproduction record, not an additional completed test suite.
Capture it locally; a public finding can summarize the comparison without attaching
process memory or model data. On an unrecognized partial repeat or changed identity,
do not label a guessed baseline as recovered animation. The prototype's exact-repeat
rule is deliberately narrower than approximate visual similarity.

## Verification

Evidence was collected privately from the user's own installation. Public code
links establish tool/interface provenance, not independent reproduction of these
specific measurements. No private repository or missing local guide is required
to read this note, but the custom runtime is **not supplied** for installation.

| Gate | Observed result | What it does not establish |
|---|---|---|
| Initial proportion slice | Four native models reopened; human accepted the demonstrated corset appearance | Every variant/animation tested live |
| Later surface cleanup | Human accepted the shown armor0 appearance | Automatic cleanup of another outfit |
| Refit transfer corpus | 15,650 x86 pose/fade cases passed production limiting; 1,069 raw asymmetric proposals needed attenuation | Equal full motion range at every asymmetric setting |
| Lift objective | Offline refit retained about 80.0155% of the previously defined target lift | 80% of every source axis, live maxima, or source-solver parity |
| Failed expanded-rig trial | Correct deployed cache/callback and fault-free publications, but severe stretching | Telemetry or an incremental guard proving baseline appearance |
| Rotation-flag negative control | 6,480 old receiver comparisons reproduced captured baselines and failed the intended parent-frame oracle | Uncaptured actor telemetry; actor rotation for this identity-local comparison was reconstructed from receiver output |
| Isolated flag correction | 6,480 exact corrected parent comparisons plus 512 independent synthetic actor/parent/local cases | Whole-engine support for arbitrary expanded rigs |
| Corrected production fixtures | 720 comparison phases, including captured-animation/repeated-pass cases | Complete authored-animation or contact coverage |
| Corrected live baseline | 40 stable phases, all 162 added matrices equal the torso bit-exact: 6,480 comparisons | Every animation and runtime state |
| Live composition/guard | Independent reconstruction exact; maximum sampled cumulative bound 0.94992349 against a strict 0.95 margin | Global self-collision, swept collision or garment contact |
| Corrected human test | Human accepted the motion, smoothness and no visible distortion after the motion-review request | Exhaustive motion/contact or extreme-pose appearance acceptance |

The deformation guard bounded the displacement gradient on the declared affected
triangle set relative to true animation. It did not certify a previously malformed
baseline, all unresolved-weight joins, or nonlocal layer intersections. No guard
threshold was relaxed to accept the rotation correction.

For each tested triangle, form the two baseline edge vectors as columns of `E`,
and the changes to those edges as columns of `D`. The check was
`||D * pseudoinverse(E)||_F < 0.95`. Here `E` and `D` are 3×2 matrices and `_F`
denotes the Frobenius norm; valid use requires a nondegenerate baseline triangle.
A pseudoinverse returning a number is not itself a degeneracy check. Report the
maximum over the declared face set and distinguish it from contact clearance or
whole-character safety. A broken animation baseline can pass even this cumulative
test; the parent-matrix regression addresses that different failure.

Static inspection found several **350-entry local animation buffers**, but that is
not a certified whole-engine bone limit. The 234-bone live result is scoped to the
tested actor/model/path. Global allocation, IK and other render consumers still
need their own evidence before generalizing.

## Gotchas

1. **Symptom: an armature passes zero skinning but explodes when posed.** Cause:
   degenerate editor bones lost orientation. Fix: create nonzero head/tail first,
   then check each constructed bone frame against independent native frames.
2. **Symptom: armor2 loses its dress shape or hair texture.** Cause: copying armor0
   positions or guessing neighboring texture files. Fix: use the variant's own base
   and follow the actual material reference chain.
3. **Symptom: a fabric-coverage complaint survives geometry smoothing.** Cause:
   wrong texture ownership was treated as an anatomy problem. Fix: inspect labelled
   atlas samples, freeze geometry for a texture-only pass, and protect neckline texels
   and mip padding as well as vertices.
4. **Symptom: increasing solver gain creates sharp central folds.** Cause: native
   stored weights, transition geometry and mixed-side ownership limit displacement.
   Fix: inspect limiting faces, stored-byte behavior and intermediate asymmetric
   fades; reassess representation rather than weakening the acceptance margin.
5. **Symptom: a new model is rejected despite matching the intended disk file.**
   Cause: initialized native cache state differs. Fix: trace/predict those specific
   fields and validate named references; do not turn admission into a wildcard.
6. **Symptom: motion accumulates even though per-pass guard checks pass.** Cause:
   previous outputs are mistaken for fresh animation. Fix: explicit true-baseline
   provenance and exact repeat recognition, with partial-repeat negative controls.
7. **Symptom: native poses have gross stretching while cache and telemetry pass.**
   Cause here: copied actor-relative rotation flag on new identity-local receivers.
   Fix: trace native composition flags and verify actual animated receiver matrices;
   the corrected native test must reject the retained failure witness.
8. **Symptom: physics looks lower-FPS than animation.** Cause in this prototype:
   fixed-tick world-pose holding against current animation. Fix: equilibrium-local
   interpolation/current-animation reapplication, with the latency stated explicitly.
9. **Symptom: one solver's settings are treated as another's softness preset.**
   Cause: conflating the inspected Full SMP comparator profile with a CBPC softness
   preset, or authored endpoints with live maxima. Fix: pin the actual source
   profile and distinguish constraint settings, static endpoints and observed motion.

## Assets

This text-only contribution contains no game/mod assets, private preset, derived
mesh, texture, screenshot, simulator XML, DLL, disassembly or memory dump. SourceIO
(REDxEYE), Crowbar (ZeqMacaw), srctools (TeamSpen210), vtmb-tweaks (c6-dev),
BodySlide/Outfit Studio (Ousnius and Caliente), FSMP (DaymareOn) and Bullet retain
their licenses; source-derived adapters need their own license/provenance review
before any release. Referencing public source here does not relicense its
implementation as original project code.

The supplied LongHair release identity remains unknown; crediting the filename is
not a substitute for resolving its author and redistribution terms before shipping
a converted outfit. This contribution shares findings, not that outfit.

## Open questions

- Broader authored-animation, IK, distant-LOD and contact/collision coverage.
- Independent/asymmetric control quality on the corrected expanded rig; some
  offline proposals require substantial limiting.
- Historical neckline depth and endpoint angularity outside the accepted sampled
  live test. The human's current acceptance is not every possible endpoint view.
- The 70 preserved unresolved weight records and their affected interfaces.
- Automatic profile restoration/save-load lifecycle behavior, deliberately deferred.
- Final independent-outfit validation after combined controls/integration.
- General converter portability and a reproducible distributable runtime package.

For the earlier source-game evidence, see the
[Skyrim OSD/TRI and isolated BodySlide note](../skyrim-special-edition/cbbe-mesh-osd-tri-isolated-bodyslide-validation.md).
