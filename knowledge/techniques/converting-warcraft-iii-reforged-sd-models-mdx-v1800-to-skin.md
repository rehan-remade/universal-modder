---
kind: technique
title: Converting Warcraft III Reforged SD models (MDX v1800) to skinned glTF
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-13'
links:
- knowledge/games/age-of-mythology-retold/warcraft-iii-races-and-campaigns-as-a-data-mod-for-age-of-my.md
tags: [mdx, warcraft-iii, reforged, casc, stormex, gltf, skinning, skeletal-animation, model-conversion, team-colour]
---
# Converting Warcraft III Reforged SD models (MDX v1800) to skinned glTF

> How to turn the classic (SD) models that ship inside Warcraft III Reforged, which are MDX version 1800, into
> one skinned, animated glTF per unit: every sequence as a named animation, a team-colour mask and attach points.
> About 280 units, buildings and missiles went through it into Age of Mythology: Retold (via CryBar's
> `glb-to-tmm`), checked by Blender renders and in game: see
> [Warcraft III races and campaigns in AoM: Retold](../games/age-of-mythology-retold/warcraft-iii-races-and-campaigns-as-a-data-mod-for-age-of-my.md).
> The converted models are still Blizzard's art: keep them on your own PC.

## Setup
- **Source:** Warcraft III Reforged 3.0.0.24268 installed (CASC storage). [stormex](https://github.com/Talv/stormex)
  2.2.0 reads it. The SD art is under the `war3.w3mod:` prefix (`war3.w3mod:units\orc\grunt\grunt.mdx`).
  `_hd.w3mod` holds the Reforged HD art, and an `_de.w3mod` tree exists too. Localized voices are under
  `_locales\<lang>.w3mod`.
- **Listfile:** dump the full CASC file list once (about 95,000 names) and search it locally.
- **Unit data that helps the conversion:**
  - `units\unitskin.txt`: model file and `modelScale:sd`;
  - `units\unitweapons.slk`: attack release time `dmgpt1`, weapon type, range;
  - `units\*unitfunc.txt`: `Missileart`;
  - names in `_locales\<lang>.w3mod:units\*unitstrings.txt`.
- **Code:** Python 3.12 with numpy and Pillow, no SDK. Blender 5.2 only for checking.

## How it works
- **MDX v1800 is still a chunked format:** a 4-byte tag, a size, then the payload. Read every chunk and every
  object strictly by its declared size, and skip what you don't know: unknown tracks then cost nothing. We
  validated the reader by checking that every chunk's byte count adds up. Older tools target older versions.
- **Material layers in v1800** carry a table of `(texture id, slot)` pairs; the old single `textureId` field
  reads 0 and is not reliable.
- **Coordinates:** WC3 is Z-up, facing +X, with left at +Y; glTF is Y-up, facing +Z, with left at +X.
  `(x, y, z) → (y, z, x)` is a proper rotation, so triangle winding is kept. Scale: the Grunt is 103 WC3 units
  tall at rest, which we map to 2.30 m, then apply `modelScale:sd`.
- **Skeleton:** bones, helpers and attachment nodes, under one synthetic root. Rest pose = the pivots, inverse
  bind = translate by minus the pivot (classic MDX has no bind rotation). Bones may come after their children
  in the file: sort them topologically before writing joints.
- **Skinning:** from matrix groups, equal weights, first four bones.
- **Animation:** one global timeline cut into sequences `[start, end]` in ms. Sample each requested sequence at
  30 fps. Keys outside a sequence's window do not count inside it (WC3 semantics); bake global sequences in.
  Write translation and rotation for every bone in every animation, or viewers keep the previous pose.
- **Visibility (`KGAO`, geoset alpha):** same window rule, else the static value. Turn hidden into a near-zero
  scale (0.001; exact zero breaks matrix decomposition) on the bones only that geoset uses.
- **Which geosets to keep:** drop effect geosets (all layers additive or modulate, filter mode 3 or more), team
  glow (replaceable texture 2), lower LODs, and geosets never visible in the converted sequences. Keep a
  per-model allow-list for the rare additive body that is the unit itself (ghosts, wisps, some missiles).
- **Team colour:** the team-colour layer is an underlay (replaceable texture 1) that shows where the diffuse
  alpha is low. Derive the player-colour mask from the diffuse alpha; a gamma and a minimum help on some models.
- **Alpha-tested layers** (filter 1) become cut-out materials. A threshold of about 0.75 matched WC3 on capes that
  also draw in a "Transparent" layer.
- **Attack timing:** `dmgpt1` divided by the attack sequence's duration gives the normalized moment of the hit or
  the missile release. A missile MDX's own Birth sound events give a launch sound.
- **Output for AoM: Retold (CryBar `glb-to-tmm`):** one mesh with several primitives, a single buffer, u8 joints,
  POSITION/NORMAL/TEXCOORD_0 present, one glTF animation per target animation. Each animation becomes one TMA.

## Gotchas
1. **A model converts to nothing (empty geometry, crash on an empty array).** **Cause:** the config names a
   sequence the model doesn't have; missiles often use `Stand -1`, not `Stand`, so every geoset looks never
   visible. **Fix:** list the sequence names first and match them exactly.
2. **A missile or ghost converts empty.** **Cause:** all its geosets are additive effect layers.
   **Fix:** allow-list those geosets for that model.
3. **A weapon blinks once per loop.** **Cause:** visibility sampled at the sequence's last ms, where the next
   key already applies. **Fix:** sample at `end - 1`.
4. **Every texture is wrong on v1800.** **Cause:** using the layer's old `textureId`. **Fix:** read the
   texture/slot table.
5. **Attach points not found.** **Cause:** some node names end with a space (`"Hand Right Ref "`).
   **Fix:** strip names before matching.
6. **All units the same size.** **Cause:** reading the bare `modelScale` key, a default of 1. **Fix:** read
   `modelScale:sd` (the Grunt is 1.1, the Black Dragon 1.75).
7. **stormex under Git Bash fails on paths and patterns.** **Cause:** mingw mangles backslashes in its regex and
   Windows output paths. **Fix:** use `[.]`, `.` and forward slashes.

## Verification
- Chunk byte counts add up for every file read.
- Blender contact sheets: one frame per converted animation, compared against WC3.
- In AoM: Retold: size, team colour, animations, weapon visibility, attach points (weapons, missile launch
  point), sounds on animation events.
- Not done: particle emitters (`PRE2`) and ribbons are skipped, so their fire, glows and trails are lost; HD
  (`_hd.w3mod`) models were not tried.
