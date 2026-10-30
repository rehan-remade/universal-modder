---
kind: technique
title: Porting 1.7.10 GL11 render states and IItemRenderer frames to Minecraft 1.20 Fabric
status: working
agents:
- Claude Code
humans: []
date: '2026-10-10'
links: []
tags: [minecraft, fabric, forge, rendering, shaders, frapi, models, porting, fidelity]
---
# Porting 1.7.10 GL11 render states and IItemRenderer frames to Minecraft 1.20 Fabric

> 1.7.10 mods drew with raw GL11 state (alpha test thresholds, texture-env modes, per-face brightness, IItemRenderer
> frames); 1.20 only offers render layers, core shaders and baked models. Most visual mismatches in a port come from
> a handful of state differences that can be reproduced exactly once you know where each one lives in 1.20.

## When to use it
- Porting TESRs, ISBRHs (`ISimpleBlockRenderingHandler`), `IItemRenderer`s or entity renderers from Forge 1.7.10 to
  Fabric 1.20.x, when the result must look like the original, not just "similar".
- Auditing a port for invisible or wrong-looking things: an item that draws nothing, a glow cut into a hard blob, an
  overlay that hides the block under it, a model whose textures look flipped.
Verified on Minecraft 1.20.1, Fabric API 0.92 (Indigo renderer), Loom 1.7.4.

## How
- **Find the GL state first.** For every draw in the old code, write down blend func, `glAlphaFunc`, depth mask,
  culling, `GL_LIGHTING`, `glTexEnvi(GL_TEXTURE_ENV_MODE)`, the brightness passed to the Tessellator and the matrix
  sequence. Methods Vineflower leaves as bytecode ("couldn't be decompiled") still show these as `ldc` /
  `invokestatic GL11.*` lines; tableswitches on `ForgeDirection.ordinal()` are direct ordinals (DOWN 0 .. EAST 5).
  Keep the decompile outside the repo you publish.
- **Alpha test.** Vanilla 1.20 core shaders discard below 0.1, and they differ in *what* they test:
  `rendertype_entity_translucent` tests texture alpha only (a model at vertex alpha 0.05 still shows), while
  `rendertype_item_entity_translucent_cull` and `position_color_tex_lightmap` test texture x vertex alpha (it
  vanishes). For `glAlphaFunc(GL_GREATER, 1/255)` register a copy of the vanilla fragment shader with
  `<= 0.003921569` through Fabric's `CoreShaderRegistrationCallback` (namespaced json,
  `"vertex": "position_color_tex_lightmap"` can stay vanilla) and use it only where the old code lowered the
  threshold.
- **Texture environment.** `GL_ADD` (texture colour plus vertex colour, alphas multiplied) has no vanilla shader;
  a 10-line custom fragment shader (`vec4(tex.rgb + vertexColor.rgb, tex.a * vertexColor.a)`) reproduces it.
- **Per-face brightness in block models.** An ISBRH that set `tessellator.setBrightness(max(bb, 160))` and an opaque
  colour (no face shading) maps to a FRAPI model: wrap the baked model (`ModelLoadingPlugin` `modifyModelAfterBake`,
  match the block's `ModelIdentifier`, skip `#inventory`), `pushTransform` on the quads (e.g. `colorIndex() == 0`),
  set a material with `disableDiffuse(true)` and `ambientOcclusion(TriState.FALSE)`, and write the lightmap. Indigo
  keeps the brighter of the quad's lightmap and the world light *per channel*, so you can raise a floor but never
  darken below the world light.
- **Connected textures** (`getIcon(world, x, y, z, side)` choosing from N icons by neighbours): a FRAPI model that
  emits six `square()` faces with `spriteBake(sprite, BAKE_LOCK_UV)`, `cullFace(dir)`, and the sprite picked from
  the same neighbour bits; cull faces between same blocks with `isSideInvisible`. Lock-UV equals 1.7.10's face UVs on
  the four sides and the top; the bottom face needs `BAKE_FLIP_V` (1.7.10 ran v along +z there).
- **Block-entity data in the chunk mesh** (camouflage / "warded" blocks drawn by an ISBRH from tile data): implement
  `RenderDataBlockEntity.getRenderData()`, read it in the model with `view.getBlockEntityRenderData(pos)`, emit the
  stored state's model, set the quads' blend mode from `RenderLayers.getBlockLayer(stored)`, forward the block colour
  provider to the stored state, and call `world.updateListeners(...)` in the client-side `readNbt` so the section
  rebuilds when the data arrives.
- **IItemRenderer frames.** Display transforms in item json can't express a 1.7.10 frame exactly; set them to
  identity (`builtin/entity`) and replay the frame in a `BuiltinItemRendererRegistry` renderer per
  `ModelTransformationMode`: INVENTORY_BLOCK = scale 0.625, rotate X 30, rotate Y -45 in the 1.20 GUI frame; ENTITY =
  0.5 (undo ItemEntityRenderer's lift of 0.25 x display scale); EQUIPPED = undo `HeldItemFeatureRenderer`
  (X -90, Y 180, (1, 2, -10) px) and redo the biped's 3D-item transform. For EQUIPPED_FIRST_PERSON with arms, cancel
  `HeldItemRenderer.renderFirstPersonItem` at HEAD for that item and replay the 1.7.10 `renderItemInFirstPerson`
  sequence: both versions start in the same camera space after the arm-sway rotations, `ModelPart.rotate` is Z-Y-X like
  `ModelRenderer`, and `PlayerEntityRenderer.renderRightArm` is the old `renderFirstPersonArm`.
- **`GL_LIGHTING` off.** In 1.7.10 it only removed the directional diffuse; the lightmap (texture unit 1) still
  applied. Every lit 1.20 entity shader (`rendertype_entity_solid`, `_cutout`, `_translucent`, ...) runs
  `minecraft_mix_light` and has no switch for it. Register a copy of the
  entity vertex shader with `vertexColor = Color` (namespaced json; the vanilla `rendertype_entity_cutout_no_cull`
  fragment stage can stay, the translucent one is identical) and build cutout / translucent / culled layers on it.
  Faces drawn with `RenderBlocks.renderFace*` inside a TESR also take their UVs from the render bounds (top and bottom
  u = x, v = z; sides v = 16 - y), so a small liquid box must not stretch the whole icon.
- **A Tessellator draw without `setBrightness`** is not full bright: it uses the lightmap coordinates the dispatcher
  set for the tile entity or entity. For such lit billboards the vanilla particle shader fits
  (`POSITION_TEXTURE_COLOR_LIGHT`, alpha test on texture x colour, colour x lightmap).
- **`renderItemIn2D`** (pixel-extruded sprites: quills, valve wheels, wand ornaments): port the 1.7.10 routine as is
  (front, back at -thickness, one strip per texel column and row sampling the texel centre); a flat quad loses the
  stepped edges and usually gets the (maxU, minV, minU, maxV) UV order wrong.

## Gotchas
1. **A model's textures look mirrored or its east/west faces swapped.** **Cause:** 1.7.10 `ModelBox` reads
   `ModelRenderer.mirror` when `addBox` runs; most generated models (Techne) set `mirror = true` *after* `addBox`,
   which does nothing. Porting every such box as `.mirrored()` mirrors boxes the original never mirrored. **Fix:**
   replay each model constructor in order and mirror only boxes added while the flag was already true (a short
   script over the decompiled constructors does it for a whole mod).
2. **An item is invisible everywhere.** **Cause:** the original drew it with an `IItemRenderer` while its icon was a
   blank sprite; the port kept the blank `item/generated` model. **Fix:** grep the old ClientProxy for every
   `MinecraftForgeClient.registerItemRenderer` and make sure each has a 1.20 builtin renderer.
3. **An ore overlay hides the stone under it.** **Cause:** a two-pass ISBRH ported as a two-element json model left in
   the solid layer; the overlay's clear texels are drawn opaque. **Fix:** cutout(-mipped) layer.
4. **A faint ghost mob or soft glow is gone.** **Cause:** vertex alpha around 0.1 under a shader that discards
   texture x vertex alpha < 0.1. **Fix:** a layer on the entity-translucent program (texture-alpha test) or a 1/255
   shader, see How.
5. **"Brightness 160" turned into full bright.** **Cause:** treating `setBrightness(n)` as emissive. **Fix:** it is a
   packed lightmap (block light n/16, sky 0); for opaque blocks the own-position brightness `bb` is 0, so
   `max(bb, 160)` is simply 160.
6. **`readNbt` updated the data but the chunk still shows the old block.** **Cause:** block-entity update packets do
   not rebuild the section. **Fix:** `world.updateListeners` on the client after reading.
7. **Light engine and block entities.** A per-instance light opacity read from a block entity does not work: the
   light engine runs off-thread, where `World.getBlockEntity` returns null. **Fix:** an `IntProperty` (0-15) on the
   block, set from the stored block when the block entity is filled, and `getOpacity` returning it (the same way
   luminance is usually carried); check it with a GameTest that waits ~20 ticks and reads the sky light in a walled
   pocket under the block.
8. **`IllegalStateException: Not filled all elements of the vertex` after switching a layer.** **Cause:**
   `BufferBuilder` writes elements in the format's order and skips a call whose element is not the current one, so
   `vertex().color().texture()` against a position-texture-colour format leaves the vertex short. **Fix:** order the
   calls as the new format lists its elements.
9. **Waves or flicker identical on every copy of an effect.** **Cause:** the old code phased a sine by the world
   position (`x % 16`); the port passes coordinates relative to the matrix origin. **Fix:** keep relative coordinates
   for geometry and pass the world position separately for the phase.

10. **Every additive particle turned black while one special particle was alive.** **Cause:** a CUSTOM-sheet
    particle (a lightning bolt, a shield dome) is flushed just before render layers whose lightmap phase switches the
    lightmap off, and the next sheet inherited that. **Fix:** register each 1.7.10 particle layer (`particles.png`
    layers 0-3) as its own `ParticleTextureSheet` (an accessor mixin adds it to the particle manager) and turn the
    lightmap on in its `begin()`; never assume GL state left by an earlier sheet.
11. **OBJ meshes from the original have textures on the wrong faces and seams at their edges.** **Cause:** Forge
    1.7.10's `WavefrontObject` read `vt u v` as (u, 1 - v) and moved every UV 0.0005 towards the face's average UV
    (`addFaceForRender(.., 0.0005F)`). **Fix:** flip V by default in the OBJ loader and apply the same inset.
12. **"limits mip level from 4 to 1": every block lost its mipmaps.** **Cause:** a few 6 or 8 px wide original
    textures in the block atlas cap the mip level of the whole atlas. **Fix:** upscale them by whole factors with
    nearest-neighbour (8 → 16, 6 → 48 px).
13. **1.7.10 `ShaderGroup` post effects.** Run them as `PostEffectProcessor`s at HUD time (created when the effect
    starts, closed when it ends, resized with the window; drawing at HUD time also covers the hotbar, as the 1.7.10
    overlay did). The original post JSONs carry over; custom programs need GLSL 120 → 150, lower-case identifiers and
    1.20's `sobel` vertex stage, and work done in a global initialiser must move into `main()`.
14. **A texgen starfield (16 passes with `GL_TEXTURE_GEN` planes and texture-matrix rotations).** 1.20 has no texgen.
    One core shader computes all layers from the face axis and the world position (view-rotation matrix and a
    camera-position uniform), so renderers keep plain positions. Check the formula against a numeric emulation of
    the old pipeline for all six faces before looking at screenshots (difference < 1e-11 here).
15. **An item drawn additively** (`glBlendFunc(SRC_ALPHA, ONE)`): 1.20's item renderer picks its own layers; pass it
    a wrapped `VertexConsumerProvider` that maps every requested layer to an additive layer on the same texture.
16. **`GL_EXP` fog with a density** (a mist effect): a `BackgroundRenderer` mixin with a linear fog ending at
    3 / density.
17. **Block hit particles, crack overlays, block highlights.** `Block.addHitEffects` → a mixin on
    `ParticleManager.addBlockBreakingParticles`; a crack stage from your own progress →
    `WorldRenderer.setBlockBreakingInfo`; Forge's highlight event → `WorldRenderEvents.BEFORE_BLOCK_OUTLINE`, which
    can cancel vanilla's outline. World overlays drawn at `WorldRenderEvents.LAST` through `ctx.consumers()` never
    appear: draw at `AFTER_ENTITIES`.
18. **Water drawn with the vanilla sprite looks grey.** The 1.20 water sprite is greyscale and tinted by the biome
    water colour (1.7.10's was already blue); apply the tint in renderers and GUIs.
19. **An emitter's unshaded faces are one light level darker than in 1.7.10.** In the 1.20 chunk mesh a face takes its
    light from the neighbour position; `renderFace*` used the block's own brightness. Accepted as a platform
    difference.
20. **LWJGL2 GUI idioms.** `Mouse.isButtonDown` → a GLFW poll; depth-buffer clipping tricks → a scissor. The
    standard galactic font is `minecraft:alt`, forced unicode is `minecraft:uniform`.

## Seen in
- The Thaumcraft 4 port to Fabric 1.20.1 (its field note is PR #236,
  `games/minecraft/porting-thaumcraft-4-1-7-10-forge-to-minecraft-1-20-1-fabric.md`): thaumometer, infused ores,
  warded glass / blocks, nodes, wisps, mind spider, research table, valve, jar / reservoir liquids, hover harness,
  floaty lines. Thaumcraft's code and assets are Azanor's. The port's decompile of the original and the original
  assets live in its private repository, and nothing from them is in this note. Publishing or sharing a port like
  this, in a modpack other people download too, needs the original author's permission.
