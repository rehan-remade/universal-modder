---
kind: game
title: "Starfield animation (.af/.rig) and physics (Havok 2019.02)"
game: "Starfield"
games_also: []
game_version: "Bethesda Game Studios, 2023, Creation Engine 2 (PC)"
platform: windows
engine: creation
route: asset-only
tools: ["CALUMI.Animation (Calaverah, LGPLv3)", "sf_animation_io Blender addon (Deveris256)", "StarfieldMeshConverter", "Blender 4.3"]
anti_cheat: "none relevant to asset conversion (offline files)"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links:
  - "https://github.com/Calaverah/CALUMI.Animation"
tags: [starfield, creation-engine, animation, af, rig, havok, physics, blender]
---

# Starfield animation (.af/.rig) and physics (Havok 2019.02)

> Starfield splits its two "Havok-shaped" problems apart. **Physics/collision still uses Havok** —
> the 2019.02 chunked packfile format. **Animation does not**: BGS dropped Havok and ships custom
> `.af` (animation) and `.rig` (skeleton) formats. Animation tooling works as a Blender addon and
> needs no script extender.

## Setup

- **Game:** Starfield (Bethesda, 2023), Creation Engine 2, PC.
- **Animation:** BGS custom `.af` + `.rig`, handled by **CALUMI.Animation** (a conversion DLL,
  Calaverah, LGPLv3) and the **`sf_animation_io`** Blender addon (Deveris256, v1.0.0 2026-03-18)
  that wraps it. Works in **Blender 4.3**; **does not need SFSE** (Script Extender).
- **Physics/collision:** Havok **2019.02** chunked packfile (`SDKV="20190200"`, tags
  `TAG0/SDKV/DATA/TYPE/INDX/PTCH`). Parser: `StarfieldMeshConverter` (Blender 3.5/3.6 Geometry
  Bridge), whose scope is models, morph, geometry and physics — **not** animation.
- **Samples used:** `bipeda_skeleton.rig` (13.7 KB) plus four `.af` animations
  (`relaxed_walkforward_start`, `staggerbackwardmedium`, `threat_curious01`, `walkbackward`).

## Route and why

Asset-only, via existing open tools. Starfield's animation is not Havok, so no Havok SDK is involved;
the shortest path is the CALUMI DLL through the Blender addon. For physics, the chunked format is
self-describing enough that the 2019.02 parser reads it without an SDK (see the HKX technique note).

## How the game works (what we had to learn)

- **Animation was deliberately taken off Havok.** `.af`/`.rig` are BGS-custom containers; do not try
  to feed them to a Havok tool.
- **Physics stayed on Havok**, at 2019.02, in the newer *chunked tagfile* shape (not the FO4-era
  classic packfile). The chunk tags match the WDL 2017.2.0 family, so the same parser structure
  applies.
- **No SFSE dependency for animation** — the conversion is pure file I/O, so it runs as a Blender
  addon rather than an in-process game hook.

## Build steps

1. Install the `sf_animation_io` Blender addon (Blender 4.3); it bundles/uses CALUMI.Animation.
2. Convert `.af`/`.rig` samples to a Blender-importable form and inspect the skeleton/animations.
3. For physics/collision, use `StarfieldMeshConverter` (models/morph/geometry/physics) — not the
   animation addon.

## Verification

- Format identification is verified by inspection: `.rig`/`.af` are handled by CALUMI, and the
  physics chunk header decodes to `sdk_version="20190200"`.
- The parser repo (`StarfieldMeshConverter`) was confirmed up to date with upstream at the time
  (HEAD `00e5529`).
- **NOT verified:** in-game round-trip of an edited animation, and anything requiring SFSE. Treat this
  note as tooling/format knowledge, not a released mod.

## Gotchas

1. **Don't route animation through Havok tools.** **Symptom:** a Havok parser rejects a Starfield
   animation file. **Cause:** Starfield animation is BGS-custom, not Havok. **Fix:** use
   CALUMI.Animation / `sf_animation_io`.
2. **Physics and animation are separate pipelines.** **Symptom:** a "Starfield mesh" tool ignores
   animation. **Cause:** `StarfieldMeshConverter` is scoped to models/morph/geometry/physics.
   **Fix:** pick the tool by the data type.
3. **The 2019.02 chunk layout is not the FO4 layout.** **Symptom:** a classic-packfile parser fails on
   Starfield physics. **Cause:** 2019.02 is a chunked tagfile. **Fix:** use a chunked parser; the WDL
   2017.2.0 reference works.
4. **No SFSE assumption.** **Symptom:** you plan an in-game hook for a format task. **Cause:**
   assuming animation needs runtime access. **Fix:** it is offline file conversion; a Blender addon
   suffices.

## Assets

Not applicable — this note is about reading/converting existing game assets, not authoring new ones.

## Cost and time

Not recorded.

## Open questions

- In-game verification of an edited `.af`/`.rig` round-trip.
- A complete field-level spec of `.af`/`.rig` (CALUMI is the current de-facto decoder).
- Whether any Starfield physics path needs the Havok SDK, or whether chunked parsing is always enough.
