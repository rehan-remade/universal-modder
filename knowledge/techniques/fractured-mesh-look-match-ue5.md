---
kind: technique
title: "Making a fractured copy of a UE5 mesh look identical to the original (UV channels, V flip, normal frames, sun drift)"
game: "The Elder Scrolls IV: Oblivion Remastered"
game_version: "Oblivion Remastered 1.512.105 (UE5.3.2)"
platform: proton
engine: unreal
route: passthrough
tools: ["RE-UE4SS 3.0.1", "retoc", "Blender 4.x (bisect fracture)", "UE 5.3.2 editor commandlet (cook)", "python3"]
anti_cheat: "none"
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-11-07
links: []
tags: ["unreal", "materials", "uv", "normals", "fracture", "destruction", "swap", "a-b-test", "time-of-day"]
---

# Making a fractured copy of a UE5 mesh look identical to the original

> We swap a real Oblivion Remastered house (static mesh components) for ~1,700 fractured piece actors when it is first hit.
> At the swap the wall visibly changed: clean brick turned into darker, speckled small-scale stone. Three pipeline faults
> caused it, and one measurement trap hid how far the fix had got. Labels: [real run] an evidence file in the project
> records it; [source] code read; [inferred] reasoned, not tested.

## Setup
- Source meshes extracted from the user's install with `retoc to-legacy`, parsed by our own uasset reader, cut in Blender
  (bisect), written to our own binary piece format and cooked by a UE 5.3.2 editor commandlet into a pak.
- Pieces are spawned from UE4SS Lua and swapped in for the real components; stills come from an in-engine capture
  (SceneCapture to PNG), the same camera before and after the swap.

## What the engine/material actually does
1. **The house materials read a mask on UV1.** The material instance has the static switch `UseMaskUVChannel2` (seen as
   `+UseMaskUVChannel2` in the instance's name table); every source mesh has 2 UV channels. A pipeline that keeps only UV0
   makes the mask sample UV0, which tiles at brick scale: speckle [real run].
2. **V was flipped.** OBJ stores `1 - v`. 300 of 300 corner UVs of one cooked piece matched the source's `(u, 1 - v)` and 0
   matched as-is [real run]. Mirrored textures plus a flipped normal-map green channel read as "slightly darker" [inferred].
3. **Recomputed normals are flat.** A cook that gives every triangle its own vertices and calls
   `ComputeTangentsAndNormals(Normals|Tangents)` shades bevels flat. Carry the source TangentX/TangentZ (int8x4 or int16x4 in
   the cooked vertex buffer) through the fracture as extra UV layers. Then call `ComputeTangentsAndNormals(None)`: it fills
   only zero frames (cut faces) and keeps the valid ones [source: StaticMeshOperations.cpp].

## How it was verified
- An A/B in one run: film the intact wall, swap without a blast, film again, score `mean|diff|` and brightness on a wall crop
  (tools/swaplook.py). Old pak: wall diff 22.3, brightness 0.775. UV1 + V fix: 11.9, 0.906. Then the remaining "9% darker"
  turned out to be the trap below. With the sun held still: diff 7.2, blurred 3.1, brightness 0.999, against a no-swap floor
  (blurred 1.1) [real run].

## Gotchas
1. **Time of day moves between your A and B.** Oblivion runs at timescale 30 (1 real minute = 30 game minutes). Films taken a
   minute apart differ by more than the effect you are measuring. Proof: film the real house, swap and film the pieces, unswap
   and film the real house again. Real against real (no swap at all) gave brightness 0.747. Set `timescale to 1` (and a fixed
   `gamehour`) before any look comparison [real run].
2. **Setting pieces Static does not help.** Movable pieces looked darker, so we tried Mobility Static. Static with no baked
   lightmap gets no precomputed light at all: 0.761 against Movable's 0.893 [real run]. Keep pieces Movable.
3. **Float32 positions near 90,000 cm break a fine vertex-match key.** Matching cut-mesh loops back to source vertices on a
   0.01 cm grid matched only 47%. A 1 mm grid plus a neighbour search matched 648,168 of 648,174 [real run].
4. **Physics is not deterministic.** Two takes of the same rockets differ, so compare stills of one take (apply the change
   after the collapse, then re-shoot the same cameras) [real run].
5. **Open: moss on cut faces.** Faces created by the cut show uniform moss, whatever UV scale they get, with the house MIC or a rubble
   MIC (three UV tries). Two probes then changed a dynamic material instance on the cut-face slot: scalars by name, then per layer
   with `Set*ParameterValueByInfo` (the house material is a layered material: `Blend_Amount`, `Blendmask` and the rest exist once per
   layer, and setting them by plain name changes only the global one). Neither changed a pixel, not even black against white blend
   masks, so the panel was most likely not drawn with that instance at all [real run]. Lesson: start such a probe with a positive
   control (a change that must visibly alter the face) before testing any theory about the material. Unresolved.
