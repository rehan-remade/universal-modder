---
kind: game
title: "Extracting Darktide units into Blender and rebuilding the Beast of Nurgle as one clean, animatable rig"
game: "Warhammer 40,000: Darktide"
games_also: ["Warhammer 40,000: Space Marine 2"]
game_version: "Darktide.exe 0.0.3.0 (e808530), Steam, Oct 2026"
platform: windows
engine: unknown
route: asset-only
tools: ["limn 0.7.1", "Bitsquid Blender Tools 0.8.4", "Blender 5.2.2 LTS (headless, Python 3.13)", "numpy"]
anti_cheat: "Easy Anti-Cheat (online-only live service). Everything here reads the installed bundle files on disk with the game closed; nothing touches the running game, the network, or the community Lua mod loader."
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-21
links: ["https://github.com/manshanko/limn", "https://gitlab.com/qasikfwn/bitsquid-blender-tools"]
tags: [darktide, stingray, bitsquid, limn, bundle, unit, bones, animation, scene-graph, rig, skinning, weights, influences, blender, beast-of-nurgle, cross-game-port]
---

# Extracting Darktide units into Blender and rebuilding the Beast of Nurgle as one clean, animatable rig

> First half of a Darktide -> Space Marine 2 port: the Beast of Nurgle pulled out of Darktide's bundles into Blender
> with its textures, its body rebound to one clean 337-bone armature (single root, at most 3 influences, as SM2
> needs), and a real Darktide clip played on it by exact forward kinematics. Verified offline only: renders, rest-pose
> round trips and stretch metrics. Nothing is in SM2 yet. For the SM2 side (networks, clips, retargeting) start with
> the [SM2 enemies note](../warhammer-40-000-space-marine-2/sm2-new-enemies-npc-classes-and-morpheme-animation.md).

## Setup
- Darktide.exe 0.0.3.0 (e808530), Steam. Bundles in `bundle/` (15,743 files, 14 GB), Oodle-compressed;
  `binaries/oo2core_9_win64.dll` is the decompressor limn loads from your own install.
- Bitsquid Blender Tools **0.8.4** (2026-10-01, GPL-3.0, needs Blender **5.2+**), installed as a Blender extension.
  It bundles **limn 0.7.1** (`unpacking/limn.exe`). Steam guides still say "0.6.9": that is stale, check the GitLab
  releases API (`/api/v4/projects/qasikfwn%2Fbitsquid-blender-tools/releases`).
- Blender 5.2.2 LTS, run headless (`--background --python`). All conversion scripts run inside Blender, importing
  the add-on's parser modules (`bl_ext.user_default.bitsquid.*`).
- `um scan` reports Darktide as "Unknown native engine" and suggests native hooks; ignore that. The client runs
  Easy Anti-Cheat, so hooking or injecting into it is out (`skills/mod-any-game/references/safety.md`). It is a
  Stingray (Bitsquid) fork with LuaJIT game code, and the useful route is assets read from disk.

## Route and why
Asset-only: extract with limn, import with the add-on, rebuild in Blender with scripts. Nothing loads into Darktide.
The target engine (SM2) wants one armature, one root, max 3 bone weights per vertex, and every deforming joint keyed
in its clips, so the rebuild aims at that instead of keeping Darktide's split, runtime-driven setup.

The port is for your own install. The Beast's mesh, textures and clips are Fatshark's files, so an SM2 pak that
carries them stays private and is never published (Workshop, Nexus or anywhere else); a shareable version would
have to rebuild them from the player's own Darktide install at install time. In SM2 it's for solo play or a private
lobby with friends who agreed (modded sessions are flagged "Mods Detected", see the
[foundations note](../warhammer-40-000-space-marine-2/sm2-modding-foundations-paks-tools-and-crash-triage.md)).

## How the game works (what we had to learn)

### Extracting
- limn with a **name dictionary** extracts only known names, with real paths: `-f unit` gave 8,987 files (1.96 GB)
  in 8 s, `-f bones` 1,486 files in 0.5 s. The add-on builds the dictionary (913k names) with
  `unpacking.dictionary.make_combined_limn_dict()`.
- A **small dictionary** (only the names containing `beast_of_nurgle`) is the cheap way to pull one creature's
  named files: 73 `.animation` and 3 `.state_machine` files in under a second.
- Units name their **materials by 64-bit hash**, not path, and most texture names are not in the dictionary either.
  `--dict-no-skip` also writes unknown files as `<hash>.<ext>`, and the add-on resolves those by hash. All 26,104
  materials take 5 s. **All textures (DDS) take 406 s and 102 GB**: plan the disk, prune afterwards.
- A raw `.material` can be a 68-byte stub pointing at streamed data (`data/<xx>/<hash>`); the add-on still reads its
  shader variables.

### What a creature looks like
- Beast of Nurgle (`content/characters/enemy/chaos_beast_of_nurgle/`): `attachments_base/body.unit` is the skin
  (262,795 verts, 282,670 tris, 5 materials, 214 weight groups, **195,009 vertices with 4 influences**);
  `third_person/base.unit` is the animation skeleton (186 bones, the `.bones` list) plus a 97-vertex proxy mesh;
  gibs and swallow props are separate units.
- Body and skeleton share one rest pose: 238 shared joints within 0.37 mm.
- The import is split: the body deforms only with its own 129-bone armature, while 156 of its weight groups are named
  after skeleton bones and 8 (`j_tail_bind_NN`) exist only as scene-graph nodes. 69 joints have no known name.

### Scene-graph convention (the important one)
- The add-on parses a node's local as `T(s) @ R`. Darktide's real local offset is **`R^T @ s`**: for all 312 nodes
  of base.unit, `world.t = parent.t + parent.R @ R^T @ s` and `world.R = parent.R @ R`. Chaining corrected locals
  reproduces the stored rest worlds to 2 micrometres; chaining them as parsed is off by up to 3.4 m.
- **Animation position samples are already the true offset** (median difference to `R^T @ s` over 186 bones: 0.0);
  rotations are plain local quaternions; scale is keyed too (the weakspot pulses).
- Forward kinematics: `world = parent_world @ T(p) @ R(q) @ S(s)` for animated bones, corrected rest local otherwise.

### Runtime-driven joints
- Darktide computes some joints at runtime instead of keying them:
  - tail: `j_tail_spline_NN` (unanimated, under the root) is the parent of both `j_tail_anim_NN` (keyed controls)
    and `j_tail_bind_NN` (what the skin is weighted to); all three coincide at rest;
  - the arm chain skips its `armspline` joints;
  - the crown is a physics chain (`j_hair_X_offset -> dynamic -> ...`) under the keyed `j_hair_X`.
- Hit reactions look like **additive** layers: played alone they tear the mesh even with Darktide's own weights
  (13,665 edges stretched > 3x). Don't use them as full poses.

### The add-on's animation importer
It only targets an armature whose bone count equals the `.bones` list, and converts keys approximately (rest-relative
differences, with failed attempts left in comments). For a port, sample the clip yourself with the add-on's
`AnimationResourceDT` parser and the corrected FK above.

## Build steps
1. Install Bitsquid Blender Tools 0.8.4 into Blender 5.2+; set the add-on prefs `game_dir_dt` and
   `extracted_files_dir_dt` (headless imports fail with "Cannot determine relative path" without them).
2. limn: dictionary + `--dump-raw -f unit`, then `-f bones`; `--dict-no-skip -f material`; `--dict-no-skip -f texture`
   (DDS) if you need textures; a small dictionary + `-f animation` for clips.
3. Import `body.unit` (materials on) and `base.unit` into one scene with `bpy.ops.import_scene.unit_dt`.
4. Build one armature from every weighted joint + the 186-bone skeleton + ancestors, each bone from its joint's world
   matrix (scale dropped). Take parents **from the units' own scene graphs** (parse them with `UnitResourceDT`), base
   first, then body; fall back to other evidence only where neither gives a real parent. Hang leftovers on the
   skeleton root. Rebind the body (vertex-group names are joint names) and delete the old armatures and empties.
5. Reduce to 3 influences by **least-squares fitting** (below), normalise, check sums == 1 and the rest pose.
6. Play clips by FK onto the rig; drive each `j_tail_bind_NN` with its `j_tail_anim_NN` as a stand-in for the
   runtime spline.

### Reducing 4 -> 3 influences
For each 4-influence vertex, try the 4 ways of keeping 3 bones; solve least squares for 3 weights (sum 1, clipped >= 0)
that best reproduce the original 4-bone positions over a set of training poses; keep the best subset. 18-23% of the
fitted vertices end up keeping their smallest weight and dropping a larger one. Train on **real clip frames**, not random
poses: 42 frames from 7 clips beat 8 random poses clearly on a held-out clip (table below).

## Verification
- Rest pose of the rebuilt rig reproduces the imported mesh to about 1 micrometre; every vertex has <= 3 influences
  summing to 1; 337 bones, 214 deform, one root, no cycles, depth 14, 14 root children (as in Darktide).
- Held-out clip `attack_tail_whip_left` (70 frames) played by FK, compared with the same clip on Darktide's own
  4-weight skin rebound to the same armature:

  | Weights | Edges stretched > 3x (worst frame) | Median drift vs 4 weights | Vertex samples off > 2 cm (5 frames) |
  |---|---|---|---|
  | Darktide 4 weights | 2,437 | 0 | 0 |
  | Fit on 8 random poses | 5,748 | 4.8 mm | 235,805 |
  | **Fit on 42 real frames** | **4,401** | **2.4 mm** | **80,705** |

  On the 42 training frames, fitting against plain truncation: median 29.3 -> 16.0 mm, p99 165.5 -> 109.0 mm,
  max 408 -> 211 mm (per-vertex worst frame).

- Renders of the held-out clip: the tail whips, the crown follows the head, no spikes.
- **Not verified**: anything in Space Marine 2; Darktide's real tail-spline maths (the bind = control stand-in is an
  approximation); the crown's physics; additive clips; LODs and materials for SM2.

## Gotchas
1. **Headless `unit_dt` import: "Cannot determine relative path ... is the 'DT extracted files directory' option
   set".** Cause: add-on prefs unset in a background session. **Fix:** set `game_dir_dt` and `extracted_files_dir_dt`
   on `bpy.context.preferences.addons["bl_ext.user_default.bitsquid"].preferences` first.
2. **"Could not locate ...bones".** Cause: only `.unit` extracted. **Fix:** extract `-f bones` too.
3. **Mesh imports with default materials; warnings name `<hash>.material`.** Cause: unit material references are
   hashes the dictionary doesn't know. **Fix:** `--dict-no-skip -f material`, then the same for textures.
4. **The rebuilt rig tears when you pose a single bone in Blender.** Cause: runtime-driven joints (tail binds, arm
   splines, crown) that a single-bone pose can't move; Darktide's own weights tear the same way. **Fix:** judge the rig
   with real clips, not hand poses.
5. **Forward kinematics is metres off.** Cause: the parsed scene-graph local offset is in the wrong frame. **Fix:**
   use `R^T @ s` as the local offset (animation positions need no change).
6. **The tail doesn't move in a clip.** Cause: the skin is weighted to `j_tail_bind_NN`, which no clip keys. **Fix:**
   drive binds from `j_tail_anim_NN` (stand-in), and bake that into the target engine's clips.
7. **The crown stays still while the head turns.** Cause: Blender's import dropped `j_hair_X_offset -> j_hair_X`, so
   the chain hung off the root. **Fix:** take parents from the units' scene graphs, not from the imported objects.
8. **Blender's "limit total" to 3 influences drifts up to ~10 cm and tears more.** Cause: renormalising the
   survivors pulls vertices toward far bones. Giving the dropped weight to the nearest kept bone barely helps.
   **Fix:** least-squares fit on real clip frames.
9. **Hit-reaction clips look broken.** Cause: they are additive layers. **Fix:** test them on top of a base clip.
10. **The add-on can open a web server on all interfaces.** Its experimental "VT2 Level Editor" preference starts
    uvicorn on `0.0.0.0:2523`. Off by default; leave it off.
11. **Agents in a packaged (MSIX) desktop app:** Blender started from the app's shell writes `%APPDATA%` into the app's
    private storage, so an add-on installed that way is invisible to the user's own Blender (uv's Python install broke
    the same way). **Fix:** point Blender at a lab profile with `BLENDER_USER_RESOURCES`, and tell the user to install
    the add-on themselves (drag the zip onto Blender).
12. **The weakspot renders white.** Cause: its parent material (`basic_pulse_skin`) has no node setup in the add-on.
    **Fix:** none yet; substitute a material.

## Assets
No assets were made; everything came from the user's installed copy and stays in a private lab folder outside the
repo. Nothing extracted is shipped.

## Cost and time
One session. Full texture extraction (7 min, 102 GB) dominated; every Blender script runs in 15 s to 6 min.

## Open questions
- Darktide's real spline evaluation for the tail and arms (`ap_spline_blend` is keyed and probably blends it).
- Whether a 4-influence-like quality is reachable at 3 influences with more training frames or helper bones.
- The SM2 side: LOD chain, material conversion, which SM2 network the Beast can borrow, and baking runtime-driven
  joints into SM2 clips.
