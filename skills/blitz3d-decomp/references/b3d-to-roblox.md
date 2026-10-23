# Animated .b3d models into Roblox

How CB2's P90 viewmodel (arms + gun, 57 nodes, 201 keyframes) became a Roblox rig that plays the game's own
keyframes. Scripts in `scripts/roblox/` (Python 3, Blender 5 for the build/render steps, numpy for
`wm_build.py`). Each has a docstring with its usage; run them with `python -I`.

## Read the file

`b3d_skin.py MODEL.b3d OUT.json` dumps the node tree (rest pos / scale / rot as w,x,y,z), meshes per brush,
BONE weights, KEYS, ANIM and the `SEQS` chunk, an extension in UE/CB2 files that names frame ranges
(`DRAW 1-44, idle 45-55, reload 56-179, ...`). Brushes with an empty texture are filled at runtime by the
game (CB2's arms: `GFX/Items/Weapons/Hands_textures/<class>_hands.png`); the game's code, not the file,
says which. The game's own anim table can differ from SEQS (CB2's P90 idle is 45-50, not 45-55): use the code.

## Build and look

`vm_build.py` (Blender, headless) makes an armature with a bone for **every** node (so muzzle and camera
nodes come through), one skinned mesh per brush (Roblox: one texture per MeshPart, 20k triangles each), and
a preview action. `vm_render.py` renders frames from the viewmodel camera (Blitz origin looking +z) into
a contact sheet. Check that the hands hold the gun through draw, idle, reload and shoot before uploading.

## Upload and rig

Upload the FBX as a Model (Open Cloud). Roblox imports it as a RootPart with Bones and skinned MeshParts,
turned 180 degrees about Y: Roblox model space = (-x, y, z) of Blitz, times the build scale. Known import
behaviour:

- Bones get their own axes (Blender's bone convention), not the node frames: store keyframes in node
  space and solve a fixed correction per bone at runtime, `C = nodeRestWorld^-1 * boneRestWorld`, then
  `Bone.Transform = (parentTarget * Bone.CFrame)^-1 * nodeWorld(t) * C`. Bone positions must match the
  nodes exactly; a non-zero correction position means the space mapping is wrong.
- Unweighted leaf nodes (CB2: `weaponfire`, `CameraBone`) are dropped: evaluate them from the keyframe data.
- `Bone.Transform` set from a script renders in Edit too, so poses can be checked without Play.

## Keyframes as data

`vm_anim_data.py IN.json OUT.luau --scale S --name P90` writes every node's local transform per frame as a
Luau module (int16, base64; constant nodes stored once; ~180 KB for 57 nodes x 201 frames). The runtime
side (the SCP-Roblox project's `ReplicatedStorage/Weapons/CB2/Viewmodel.luau`) decodes it, solves the bone
corrections, interpolates frames like Blitz (lerp positions, slerp rotations) and blends poses for Animate
transitions. 0.06 ms per pose.

## Scale

A viewmodel only has to look the same from the camera, so any uniform scale works if every camera-relative
offset scales with it. Pick one where the nearest visible geometry stays past Roblox's 0.1-stud near plane
(the P90 at 0.06 studs per model unit; CB2 draws it at 0.005 CB units per model unit, 0.04 studs). Offsets
the game applies to the scaled pivot in world units then scale by `studsPerModelUnit / gameScale` (12 for
the P90).

## World (third-person) model

If the world model is the same mesh as the viewmodel's gun (same triangle counts per texture), take the gun
from the viewmodel in its gun bone's frame instead: vertex orders differ between the files, but the
viewmodel carries the bone weights that split moving parts (magazine, bolt) for free. `wm_build.py` does
that for the P90 and places the gun in an existing template's gun space (-Z bore, +Y up, same length and
muzzle). The optical axis is the line through the sight's glass and dot, not the sight mesh's centroid.

## Images, flashes, sounds

- Images: upload as Decal, then `InsertService:LoadAsset(decalId)` gives the image id (`Decal.Texture`).
  New images can sit in moderation for a while ("Asset is not approved for the requester").
- A mesh with several textures arrives as one MeshPart: write one OBJ object per material before export.
- Sounds: the project's `tools/sound_batch.py --root <game> --key-prefix CB2/` packs clips into one atlas
  with CBSound index keys like `CB2/SFX/Weapons/P90/shoot0.ogg`.
