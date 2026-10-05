---
name: asset-pipeline
description: Turn generated or hand-made art into exactly what a game engine loads. Covers sprite cutout, trim and nearest-neighbour fitting to frame sizes, pixelation to a palette, sprite sheets and strips, player/team-colour masks, seamless textures, and rendering a 3D model into sprite frames from the game's own camera (isometric/RTS 8 or 16 headings, side view, top-down) with Blender. Use after generating assets, or when the user asks to make sprites, sprite sheets, animation frames, isometric unit sprites or icons for a game.
---

# Asset pipeline: from art to engine-ready files

The fal-assets skill makes pictures. This skill makes **files the game accepts**: the right size, frame
layout, orientation, alpha, palette and format. All commands are `um sprite ...` and `um render3d ...`; each
has `--help` with examples.

## 1. Learn the target format from the game itself
Before converting anything, open two or three of the game's own assets and write down in MODLOG.md:
- **Dimensions:** frame size, frames per sheet, and the layout (vertical strip / grid / one file per frame).
- **Orientation:** which way the art faces (Terraria: items point right, NPCs face left, the engine flips
  them), and where the pivot or hotspot sits (AoE2: the unit's ground point at the canvas centre).
- **Alpha:** hard 1-bit edges (BC1 punch-through, pixel art) or soft.
- **Style:** palette size and outline (dark 1-2 px outline in most pixel-art games).
- **Format:** PNG, DDS BC1/BC3/BC7, XNB, SLD, atlas + JSON...

The draw code is the final authority. In Terraria, NPC frame height = texture height / `Main.npcFrameCount`,
so any consistent frame size works.

## 2. 2D pipeline
```bash
um sprite info raw.png                                    # size, alpha coverage, corner colour
um sprite cutout raw.png cut.png                          # flat bg → transparent (border flood fill keeps interior whites)
um sprite cutout raw.png cut.png --grey 150 --keep-top 0.8   # also remove a soft grey shadow / the floor under it
um sprite fit cut.png item.png --size 64x26 --hard-alpha  # trim + ONE nearest-neighbour scale into the frame
um sprite fit cut.png npc.png --size 38x34 --anchor bottom   # standing sprites sit on the frame's bottom edge
um sprite pixelate cut.png px.png --size 32x32 --colors 16 --outline   # true pixel art from painterly art
um sprite palette px.png px2.png --from stock_sprite.png  # snap to the game's own colours
um sprite frames npc.png frames/ --n 3 --kind bob          # cheap idle animation (bob/squash/wobble/flash)
um sprite sheet sheet.png frames/*.png --vertical         # Terraria-style strip (or --cols N grid)
um sprite slice sheet.png out/ --frame 32x32              # the other direction
um sprite team-mask unit.png unit_grey.png --hue blue     # player-colour mask (+ desaturated sprite)
um sprite preview item.png look.png --scale 6             # checkerboard + zoom: LOOK at it before shipping
```
- **Pixel art:** scale once, with nearest neighbour, to the final size. Never scale pixel art twice.
- **Painted / HD art:** use `fit --smooth`.
- **Real frames:** for animation frames beyond bob/squash, generate each frame with the fal edit endpoint
  using the base sprite as reference ("same drone, rotors tilted, frame 2 of 4"), then cut out and fit each
  frame the same way. Or go 3D (below).

## 3. 3D → sprites (consistent angles and animations)
```bash
um fal model3d concept.png --name unit                   # textured GLB (Trellis 2 by default)
um render3d assets/gen/unit.glb frames/ --preset aoe2 --length 80 --forward-yaw -90 \
  --anims idle:10:bob,walk:12:walk,attack:16:lunge,death:20:die --shadows --samples 40
um render3d assets/gen/unit.glb side/ --preset side --canvas 128 --length 110 --engine eevee   # platformer facing R + L
```
Presets:

| Preset | Projection | Camera | Facings |
|---|---|---|---|
| `aoe2` | ortho | 30° | 16 clockwise from east |
| `iso8` | ortho | 30° | 8 |
| `trueiso` | ortho | 35.264° | 8 |
| `topdown` | ortho | — | 8 |
| `side` | ortho | — | 2 (right, left) |
| `turntable` | persp | — | 24 (promo/icon spins) |

- `--length` sets the model's longest horizontal side in pixels at 1x, so match stock units.
- `--forward-yaw` turns the model so its nose faces +X; check the first frame.
- `--shadows` adds a shadow-only pass (`*_s.png`) for engines that keep shadows in their own layer.
- Motions: bob, walk, lunge, die, wreck, spin.
- Then pack with `um sprite sheet`, or with an engine writer (e.g. `examples/aoe2-de-civ/sld.py`).
- Needs Blender (`blender` on PATH or `BLENDER=...`). Cycles uses the GPU when available.
- Dark generated textures: raise `--sun` / `--ambient`, or brighten in post.
- For game-ready 3D (not sprites), remesh with `um fal run tripo3d/tripo/remesh mesh_url=@unit.glb face_limit:=8000`, then convert in Blender
  (GLB → FBX/OBJ) with the engine's scale and axis convention: Unity Y-up metres, Unreal Z-up
  centimetres, Bethesda NIF via PyNifly.

## 4. Textures and materials
- **Tiling:** `um fal texture` generates it tiled. Check with `um sprite tile-preview t.png t3.png`. Fix
  seams on other images with `um sprite seamless`.
- **PBR sets:** `um fal pbr`. Convert to the engine's packing: Unreal ORM (occlusion/roughness/metal in RGB),
  Unity metallic-smoothness (smoothness = 1 - roughness in alpha).
- **DDS:** texconv (DirectXTex) or `magick` with DXT settings. BC7 for quality, BC1 for cutout sprites, BC3
  when alpha is soft.

## 5. Verify in the game
Put one converted asset into the game and screenshot it next to stock art (`um win shot`). Check the scale,
facing, pivot, outline and palette. Fix the recipe, then batch-convert the rest with the same commands (a
small script or Makefile, so the pipeline is reproducible from `assets/gen/`).

## 6. Converting a guest game's Unity assets (mashups)
Read the user's own install with UnityPy and write a **local, private** resource pack. Never put the
output in the mod, its repo or a release; each user runs the converter on their own copy.
- **Memory:** `UnityPy.load()` decompresses a whole bundle (a 865 MB bundle became 8.7 GB of RAM).
  Decompress only the serialized files and read `.resS` / `.resource` lazily, block by block; run each
  converter module in its own process.
- **Environment:** `UnityPy.Environment(path="")`, and load cross-referenced bundles together; otherwise
  UnityPy searches the working directory for missing dependencies.
- **Finding assets:** Addressables bundle names are hashed per update (find them by prefix); Addressables
  2.x has a binary `catalog.bin`. Map game objects to prefabs through their GUID keys, not by guessing
  names. Prefer the low-quality variant if one exists (same meshes, smaller textures).
- **Skinned meshes are stored in bind pose (often a T-pose).** For the in-game look, evaluate the idle
  clip at t = 0 yourself (UnityPy reads AnimationClip objects but does not sample them; Generic clips
  bind Transforms by CRC32 of the path), rebuild world matrices, then skin.
- **Walk the hierarchy from the container root**, skip inactive GameObjects and their children, and drop
  helper meshes (eyelids, ground shadows, stencil/outline materials).
- **Axes:** Unity is left-handed, Minecraft right-handed: flip one axis for positions and normals and
  reverse the winding; flip V; clamp UVs. Verify with a named bone (the right hand ends on the right).
- **Shared atlases:** crop each part's texture to its UV bounding box and remap UVs.
- **Audio:** `AudioClip.samples` needs FMOD (`fmod_toolkit`); encode with ffmpeg to mono OGG.
- **Minecraft side:** a pack needs `pack.mcmeta` (`pack_format` 15 for 1.20.1); `ResourceLocation`s
  accept only `[a-z0-9_./-]`. For posed meshes, a custom mesh file drawn with
  `RenderType.entityCutoutNoCull` is more robust than `forge:obj` (block-atlas textures, `usemtl`).
- **Oracle:** render preview sheets by re-reading the files you wrote, and look at them.
