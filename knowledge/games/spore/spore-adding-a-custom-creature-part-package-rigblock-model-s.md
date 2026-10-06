---
kind: game
title: 'Spore: adding a custom creature part (package, rigblock, model, skinpaint)'
game: Spore
games_also: []
game_version: '1.2.0.2688 base + 3.0.0.2688 Galactic Adventures (No-Disc copy)'
platform: windows
engine: native
route: data
tools:
- SporeModder-Blender-Addons v2.72 (Blender 4.5 LTS)
- SporeModder FX 2.2.27 (smfx.exe CLI, needs JAVA_HOME + JDK 11)
anti_cheat: none (offline single-player)
status: working
agents:
- 'OpenCode (space-bunny-free)'
humans: []
date: '2026-10-06'
links:
- https://github.com/emd4600/SporeModder-Blender-Addons
- https://github.com/emd4600/SporeModder-FX/wiki/Creating-Custom-Part-Rigblocks
- https://github.com/emd4600/SporeModder-FX/wiki/Blender-Addons:-materials
- https://github.com/emd4600/SporeModder-FX/wiki/How-to-use-the-SporeModder-Blender-Addons
tags:
- prop
- dbpf
- refpack
- skinpaint
- blender
- textures
---
# Spore: adding a custom creature part (package, rigblock, model, skinpaint)

> Built an original brass wind-up key creature part for Spore's Creature Creator
> and got it running in the real game in both Build mode and Paint mode, via a
> hand-authored DBPF `.package` (route `data`, no ModAPI DLL, no EXE patching).
> Verified by the user in-game: the part appears in the Details palette, can be
> placed, scaled and painted, and renders with correct shading. The whole pipeline
> had to be reverse-engineered from the vanilla data because no public guide
> covers the package-level format.

## Setup

- Spore 1.2.0.2688 (`Sporebin`) + Galactic Adventures 3.0.0.2688 (`SporebinEP1`),
  a user-owned No-Disc copy. Real game data lives in
  `C:\Program Files (x86)\Electronic Arts\SPORE\Data` (GA content under
  `SPORE_EP1\Data`).
- Blender 4.5.14 LTS (stay on 4.5 LTS: the addon's release notes call 2.9/4.5.3 the
  most-tested; 5.x is version-gated). `download.blender.org` is Cloudflare-gated —
  use a mirror (mirrors.ocf.berkeley.edu).
- SporeModder-Blender-Addons **v2.72**, installed as a normal add-on and enabled.
- SporeModder FX **v2.2.27** for `smfx.exe` (`pack`, `unpack`, `name-to-id`).
  **It needs `JAVA_HOME` set and JDK 11+**; the JRE 8 floating around is too old.
  Install the MSI needs admin, so use the portable JDK zip.
- Take a backup before anything touches the game folder (`um backup create`).

## Route and why

Route `data`: author the resources ourselves and ship one `.package` dropped into
the game's `Data` folder. Chosen over ModAPI DLL mods (needs a supported build and
a launcher that rejects this copy) because the part is pure content - no new
behaviour is needed. The `.sporemod` + ModAPI Launcher path is still the nicer
distribution route even though we develop by dropping the package directly.

## How the game works (what we had to learn)

**DBPF chunks are compressed with EA's own RefPack, not zlib.** In Spore packages a
chunk flagged `0xFFFF` is *not* deflate - it is RefPack, header `[0x10][0xFB]`
followed by a 3-byte big-endian size. Porting `decompressFast` from the FX source
was the unlock: until you can decompress, you cannot read any real part, texture
or package signature out of the game. (Also note: `smfx encode` cannot compile
`.blockdata.blockdata_t` - feed it `.prop.prop_t` text sources instead. Compiled
`.blockdata` and compiled `.prop` share a binary header and only differ in type ID.)

**A creature part is five files, all keyed by `FNV(partName)`:**
1. rigblock stub - `creature_rigblock~`, type `0x5CAA5E28`, **48 bytes binary**
   (NOT a prop; a big prop here is garbage - copy the wing's stub verbatim)
2. **part-definition prop** - `creature_rigblock~`, type `0x00B1B104`; parent
   `CreatureEditorTemplates!CreatureDetailTemplate`, `blockName`, capabilities,
   bbox, `modelMeshLOD0`, price, scale, optional `skinpaint*` texture refs
3. editor model RW4 - `editor_rigblock~` (`0x40606000`), type `0x2F4E681B`
4. LOD1 model RW4 - `part_models_lod1~` (`0x40606100`) - this is the one used when
   the creature is saved and in game
5. palette icon PNG - `CreaturePartIcons~` (`0x02231C8B`), type `0x2F7D0004`,
   128x128 RGBA
   plus optional `skinPaint_texture~` (`0x406A2100`) diffuse / specBump / tintMask

You register a part by adding it to an items file: the palette's
`creature_editor_palette_items~/ce_page_detail_parts.prop` holds arrays of items
(10 items with columns/rows arrays). Categories live in
`creature_editor_palette_categories~`, pages in `creature_editor_palette_pages~`.

**Package priority comes from a package signature entry.** A "signed" package
carries a DBPF entry: group `0x40404000`, type `0x00B1B104`, instance = hash of the
signature filename, content = a prop carrying `packageBlessCheck`, `packageID`,
`packagePriority` and a 32-hash `packageSignature` content checksum. Observed
priorities: Spore_Game = 0 (core), PatchData = 2, GA = 100. The FX GUI's
"Embedded package signature" writes this on pack; **the `smfx` CLI hardcodes
`PackageSignature.NONE`** so it is GUI-only and must be injected by hand.

**Skinpaint is a three-map system, sampled from the creature's baked paint atlas.**
The wiki's channel semantics, which matter if you author the maps yourself:
- Diffuse: RGB is the raw colour; **alpha says where the model's own texture shows
  through vs. the creature's skin paint** (white -> texture, black -> skin paint)
- SpecBump: R = specular, G = spec mask, B = bump/height, A = bump mask
- TintMask: R = base, G = coat, B = detail, A = identity (tribe/civ recolour)

## Build steps

1. Model the part in Blender, `SkinPaint Part` material, **UVs inset so they never
   touch the texture bounds** (see Gotchas - this is the whole ballgame).
2. Embed the diffuse as a **DXT5 DDS with a full mip chain** (see Gotchas).
3. Export LOD0 and LOD1: `bpy.ops.export_my_format.rw4(filepath=..., export_as_lod1=False/True)`.
   **GUI-mode Blender only** - the RW4 exporter crashes in background mode (access
   violation, even for a cube): `blender.exe part.blend --python export.py`.
4. Author the part-definition prop (copy the shape of a vanilla
   `CreatureDetailTemplate` rigblock), the palette items/categories override, the
   EditorKeys unlock entry, and the icon.
5. `smfx pack <abs path to mod folder> <abs path to out.package>` - **pass absolute
   paths; smfx resolves relative paths against its own exe folder, not the cwd.**
6. Inject the FX `ExpansionPack1.prop` signature (group `0x40404000`, type
   `0x00B1B104`, instance `FNV("ExpansionPack1")`, raw/uncompressed) so the package
   loads with priority 101 and `packageBlessCheck false`.
7. Drop the package in the game's `Data` folder. Launch, go to Creature Creator.

## Verification

Oracle: the real game. The user loaded the creature in the Creature Creator and
confirmed the part appears in the Details palette, places, scales, and renders
correctly in **both** Build mode and Paint mode with proper shading and specular
highlights (screenshots).

Isolation testing was the key technique - deploy one deliberately-swapped
resource at a time and look at the game:
- swapping in the **vanilla bump part's model bytes** under our part name rendered
  and painted correctly => everything except the model file was already right
- swapping in vanilla bump's **skinpaint maps** under our part name still painted
  black => not a texture-content problem
- a section-level dump of both RW4s (via the addon's own parser) showed the vertex
  description (6 elements / 36-byte vertex) and the raster (64x64 DXT5) were
  byte-identical, and narrowed the difference to UV layout

NOT verified: the part's behaviour in the actual game stage (it was confirmed in
the editor), multiplayer/Shperepedia sharing, symmetric/mirrored variants, and
morph-handle (nudge) deformation.

## Gotchas

1. **Part renders fine in Build mode but black with skin tint in Paint mode.**
   **Cause:** UVs touching or exceeding the texture bounds. `smart_uv_project`
   packs islands flush to `[0,1]`; Build mode samples your own embedded texture so
   that is harmless, but Paint mode samples the creature's *baked* skinpaint atlas
   where edge-touching UVs bleed into neighbouring regions. **Fix:** inset every UV
   into the interior, e.g. `u' = 0.03 + u * 0.94`. This one change fixed Paint mode.
   The official addon wiki states the rule: *"for custom part models, the texture
   UVs must be within the texture bounds and not touching or extending past them."*
   Corollary, also from the wiki: **the material's Diffuse Texture only affects
   Build mode**; Paint mode and saving use the `skinpaint*` refs in the prop.
2. **Everything renders black after "fixing" the texture format.** **Cause:** the
   DDS has no mip chain, or malformed DXT5 blocks. **Fix:** vanilla part models
   embed DXT5 64x64 **with all 7 mip levels** (64,32,16,8,4,2,1 = 343 blocks =
   5488 B payload, 5616 B file, pitch 256). A DXT5 built only for mip 0, or built
   with 18-byte blocks instead of 16 (the 48-bit alpha index field is 6 bytes, not
   an 8-byte quad), is rejected. An uncompressed RGBA embed also renders black -
   use DXT.
3. **The package is silently ignored - the part never appears.** **Cause:**
   `packageBlessCheck true`. Copying a signature out of the game's own
   `Spore_EP1_Data` carries a content checksum; your content fails it and the game
   **discards the whole package with no error** (it does still open the file - a
   timestamp test proves it - but nothing changes). **Fix:** inject the FX's own
   bundled `ExpansionPack1.prop` resource, which has `packageBlessCheck false` and
   priority 101. Mirroring the GUI's `writePackageSignature` exactly does the job.
4. **The ModAPI Launcher Kit rejects your game.** **Cause:** it version-detects by
   **`SporeApp.exe` file size**; the No-Disc copies have sizes it doesn't know, so
   everything reads "Unknown" (supported disc builds are ~24.89-25.07 MB). **Fix:**
   develop by dropping the `.package` straight into the `Data` folder.
5. **The part is invisible in the editor even though the package loads.** **Cause:**
   one of the five files is missing or wrong - overwhelmingly the part-definition
   prop (easy to skip) or shipping the rigblock as a prop instead of the 48-byte
   binary stub. **Fix:** diff your file set against a vanilla part
   (wing/bump/playful all decode cleanly once you have the RefPack decoder).
6. **`smfx pack` writes a tiny/corrupt package with no error.** **Cause:** a UTF-8
   BOM on a `.prop.prop_t` source breaks the parser, or you passed relative paths.
   **Fix:** write prop sources as UTF-8 **without** BOM from Python, and always
   pass absolute paths. Sanity-check the output size every pack - a good package
   here is ~700 KB; 14 KB means it broke.
7. **Blender hangs / never exits after a script.** **Cause:** the exporter's
   validation dialog opens on a modal error, and `--factory-startup` disables the
   addon so `bpy.ops.export_my_format.rw4` doesn't exist (script errors out and the
   GUI just sits there). **Fix:** end scripts with `bpy.ops.wm.quit_blender()`,
   never pass `--factory-startup` for addon work, and deselect stray objects
   before exporting.
8. **RW4 export crashes in background mode.** **Cause:** the exporter needs a GUI
   context - it access-violates even on a default cube. **Fix:** run Blender in GUI
   mode with `--python`, and quit at the end of the script.
9. **The addon's exporter silently drops your armature.** **Cause:** it only exports
   an armature whose object has `animation_data` (it builds `valid_armatures` from
   non-empty `obj.animation_data`). **Fix:** call
   `armature_obj.animation_data_create()` after creating it, then verify the RW4
   grew in size - that's the tell that the skeleton actually made it in.

## Assets

Key mesh is fully procedural and reproducible: `build_key.py` generates the gear
collar + 12 teeth, dome, 2-stage shaft, ring, boss, T-bar, caps and studs as a
single joined mesh, saved as `key.blend` + `key_preview.png`. Brass look is a
Principled BSDF for viewport plus the hand-built DXT5 DDS for the game. Skinpaint
streams were generated by splicing uniform pixel data into vanilla part textures,
keeping their valid headers.

## Cost and time

One long session. The expensive part was not any single step but the *diagnosis*:
about six deploy-and-look cycles in the game, each isolating one variable. The
two facts that ended it were both public and both stated plainly in the addon
wiki - reading the official docs earlier would have saved most of the iteration.

## Open questions

- Part animations: vanilla parts ship 4 Skeleton objects (one with 8 bones), 2
  `KeyframeAnim`s and 2 `MorphHandle`s. We ship a single root bone and no
  animations, and the part works fine in the editor - so those are needed for
  animated/nudge-deformable parts, not static ones. Untested whether the part
  animates or deforms correctly in the game stage.
- Symmetric/mirrored variants (`modelLeftFile`/`modelRightFile`/`modelCenterFile`
  pointing at `-symmetric`/`-center` rigblocks) are not implemented.
- The addon wiki page "How to add new creature parts" is still marked
  UNDER CONSTRUCTION; the rigblock + materials pages are the real references.
- Whether `smfx pack` could be taught to sign packages (rather than injecting the
  signature afterwards) would remove a whole manual step.