# Animated .b3d models into Roblox

How an animated viewmodel (arms + gun, 57 nodes, 201 keyframes) became a Roblox rig that plays the model's
own keyframes. Scripts in `scripts/roblox/` (Python 3, Blender 5 for the build/render steps). Each has a
docstring with its usage; run them with `python -I`.

Uploading a converted model, its textures or its sounds to Roblox publishes them. Only convert models the user
made or has a licence for, and keep the author's credit and licence with them. SCP: Containment Breach's own
models are CC BY-SA 3.0, but fan games mix licences per asset: SCP: Containment Breach 2's asset folders say
not all of their models are CC BY-SA and to ask before using one.

## Read the file

`b3d_skin.py MODEL.b3d OUT.json` dumps the node tree (rest pos / scale / rot as w,x,y,z), meshes per brush,
BONE weights, KEYS, ANIM and the `SEQS` chunk, an extension some SCP: CB fork models carry that names frame
ranges (`DRAW 1-44, idle 45-55, reload 56-179, ...`). Brushes with an empty texture are filled at runtime by
the game (per-class arm textures, for example); the game's code, not the file, says which. The game's own
anim table can differ from SEQS (an idle of 45-50 in the code against 45-55 in SEQS): use the code.
`vm_build.py` and `vm_anim_data.py` take the frame range from the root node's `seqs`; for a file without a
SEQS chunk, add one to the JSON first (`"seqs": [{"name": "all", "first": <first keyed frame>, "last": <last>}]`).

## Build and look

`vm_build.py` (Blender, headless) makes an armature with a bone for **every** node (so muzzle and camera
nodes come through), one skinned mesh per brush (Roblox: one texture per MeshPart; its mesh specifications
allow 20,000 triangles per mesh and 4 bone influences per vertex), and a preview action. `vm_render.py`
renders frames from the viewmodel camera (Blitz origin looking +z) into a contact sheet. Check that the hands
hold the gun through draw, idle, reload and shoot before uploading.

## Upload and rig

Upload the FBX as a Model (Open Cloud). Roblox imports it as a RootPart with Bones and skinned MeshParts,
turned 180 degrees about Y: Roblox model space = (-x, y, z) of Blitz, times the build scale. Known import
behaviour:

- Bones get their own axes (Blender's bone convention), not the node frames: store keyframes in node
  space and solve a fixed correction per bone at runtime, `C = nodeRestWorld^-1 * boneRestWorld`, then
  `Bone.Transform = (parentTarget * Bone.CFrame)^-1 * nodeWorld(t) * C`. Bone positions must match the
  nodes exactly; a non-zero correction position means the space mapping is wrong.
- Unweighted leaf nodes (muzzle and camera nodes such as `weaponfire` and `CameraBone`) are dropped: evaluate
  them from the keyframe data.
- `Bone.Transform` set from a script renders in Edit too, so poses can be checked without Play.

## Keyframes as data

`vm_anim_data.py IN.json OUT.luau --scale S --name NAME` writes every node's local transform per frame as a
Luau module (int16, base64; constant nodes stored once; ~180 KB for 57 nodes x 201 frames). The runtime side
(the port's own module, not included here) decodes it, solves the bone corrections, interpolates frames like
Blitz (lerp positions, slerp rotations) and blends poses for Animate transitions: 0.06 ms per pose.

## Scale

A viewmodel only has to look the same from the camera, so any uniform scale works if every camera-relative
offset scales with it. Pick one where the nearest visible geometry stays past Roblox's 0.1-stud near plane
(0.06 studs per model unit for the viewmodel above, which the game draws at 0.005 game units per model unit,
0.04 studs). Offsets the game applies to the scaled pivot in world units then scale by
`studsPerModelUnit / gameScale` (12 there).

## World (third-person) model

If the world model is the same mesh as the viewmodel's gun (same triangle counts per texture), take the gun
from the viewmodel in its gun bone's frame instead: vertex orders differ between the files, but the
viewmodel carries the bone weights that split moving parts (magazine, bolt) for free. The optical axis is the
line through the sight's glass and dot, not the sight mesh's centroid.

## Images

- Upload as Decal, then `InsertService:LoadAsset(decalId)` gives the image id (`Decal.Texture`).
  New images can sit in moderation for a while ("Asset is not approved for the requester").
- A mesh with several textures arrives as one MeshPart: write one OBJ object per material before export.
