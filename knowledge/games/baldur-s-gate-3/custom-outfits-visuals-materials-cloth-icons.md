---
kind: game
title: "Custom outfits from cloned mod and vanilla meshes: visuals, materials, body masks, cloth, LODs, icons and the Blender GR2 round trip"
game: "Baldur's Gate 3"
games_also: []
game_version: "Patch 7 era (Apr 2026) to Patch 8 hotfix (Sep 2026), Steam, Windows"
platform: windows
engine: unknown
route: asset-only
tools: ["LSLib Divine 1.18.7 / 1.20.4", "Blender 4.0.2", "Norbyte dos2de_collada_exporter (io_scene_dos2de, later v3.0.0)", "texconv (DirectXTex)", "BG3 Modders Multitool (vanilla unpack)", "Python (lsx edits, gates)"]
anti_cheat: "none; single-player"
status: working
agents: ["Claude Code (Opus 4.7)", "Claude Code (Opus 5)", "Claude Code (Opus 5.5)"]
humans: [RedSuper]
date: 2026-10-04
links: []
tags: [clothing, armour, root-templates, visual-bank, material-bank, vertex-color-masks, underwear, cloth-physics, lod, icons, gr2, blender, dos2de, soft-dependency, equip-sound]
---

# Custom outfits from cloned mod and vanilla meshes: visuals, materials, body masks, cloth, LODs, icons and the Blender GR2 round trip

> A personal item mod for Baldur's Gate 3 with about a dozen wearables (dresses, underwear, heels with
> stockings, a bag worn in the cloak slot, a nightgown with cloth physics, pyjamas cut down from a vanilla camp
> outfit, a soft-dependency armour) built from pieces of other mods and vanilla meshes, with our own edits made
> in Blender. Everything is data and assets in one `.pak`: root templates, visual/material/texture banks,
> stats, localisation, icons. Every item below was checked in game by the human; the places where only part of
> a behaviour was checked are marked.

## Setup
- BG3 on Steam, Windows 10. Work ran from Patch 7 (April 2026) through the Patch 8 hotfix (September 2026);
  the cloth fix below is the post-Patch-7 one.
- LSLib `Divine.exe`: 1.18.7 at first, 1.20.4 later (better LZ4 compression, ships `granny2.dll` for vanilla
  compressed GR2s, and fixed a DAE that 1.18.7 produced unusable). Divine wants absolute paths.
- Blender 4.0.2 with Norbyte's `dos2de_collada_exporter` addon (`io_scene_dos2de`), later v3.0.0. The addon's
  preferences field `lslib_path` points at `Divine.exe`. The importer is `import_scene.dos2de_collada`.
- texconv (Microsoft DirectXTex) to write DDS; Blender's OpenImageIO only reads DDS.
- Vanilla data unpacked with BG3 Modders Multitool (Gustav, Shared, SharedDev, Models). Source mods unpacked
  with Divine: Lovely Dresses, Drow Weaponry Fencer, Silverwings, Queen's Garments (EQL), Everdawn dress,
  Knights and Dames, Elven Weaponry - Plate, Ninja Princess set. Some items clone their assets, some keep
  pointing at the source mod (soft dependency, see below).

## Route and why
`asset-only`: a pak with `Public/<Mod>/RootTemplates`, `Public/<Mod>/Content/Assets/...` banks,
`Generated/Public/<Mod>/Assets/*.GR2` + DDS, `Public/<Mod>/Stats/Generated/Data/*.txt`, `Localization`, and
`Mods/<Mod>/GUI` for icons. No Script Extender needed. Two ways to reuse another mod's piece:
- **Clone** GR2 + textures + material + visual under new UUIDs: self-contained, bigger pak.
- **Soft dependency**: clone only the visual (new UUID) and keep its `SourceFile`/`Template`/`MaterialID`
  pointing at the original mod. Smaller, survives the source's updates, needs the source mod loaded earlier.
  This is how the Knights and Dames armour clone, the stockings and the Valkyrie-based pyjamas work.
Never clone another mod's compiled shaders (`.bshd`): doing that crashed the game on launch; referencing the
source mod's material instead (soft dependency) was the fix.

## How the game works (what we had to learn)

### The item chain
- **Stats** (`Stats/Generated/Data/*.txt`): `new entry "X"` / `type "Armor"` / `using "<parent>"` /
  `data "RootTemplate" "<uuid>"`, slot, rarity (`"VeryRare"` is one word), boosts, passives.
- **Root template** (`RootTemplates/*.lsx`, compiled to `.lsf`): `GameObjects` with `MapKey`, `Stats`,
  `ParentTemplateId`, `Icon`, `DisplayName`/`Description` as `TranslatedString` handles, `VisualTemplate`, and
  `VisualSet`. **`VisualTemplate` is only the dropped/ground model. The worn look is
  `VisualSet > Visuals > Object(MapKey=<body type>) > MapValue(Object=<visual>) x N`**: a list of visual
  resources per body type that together form the outfit. Removing a piece (jewellery, a cape, a hat) is
  deleting one `MapValue`. A body type whose list holds one combined visual cannot be split that way.
- **Body-type keys** are the character templates' `EquipmentRace` GUIDs (list on bg3.wiki "Race UUID").
  `71180b76-5752-4a97-b71f-911a69197f58` is the feminine humanoid body used by human, elf, half-elf, drow and
  tiefling women; that is usually the multi-piece list.
- **Visual resource** (VisualBank, under `Public/<Mod>/Content/Assets/.../*.lsf`; the `Content/` segment is
  required, a bank at `Public/<Mod>/Assets/...` is never indexed; any file name, one or many resources per
  file): `SourceFile` = GR2 path; `Template` = `<GR2 path>.<model node name>.0` (the model node is a real
  string in the GR2, e.g. `Dummy_Root`); `Slot`; `Objects` (one per mesh and LOD: `ObjectID` =
  `<GR2 file name>.<mesh name>.<index>`, `MaterialID`, `LOD`); `VertexColorMaskSlots`; and the child nodes
  `AnimationWaterfall`, `ClothProxyMapping`, `Base`. A working visual has 21 attributes and 4 child nodes;
  empty values must still be present (see Gotchas).
- **Material** (MaterialBank): `SourceFile` = a vanilla shader graph under
  `Public/Shared/Assets/Materials/Characters/`, `MaterialType`, `Texture2DParameters`,
  `VirtualTextureParameters`, `Vector3Parameters` (colours), `ScalarParameters`.
- **Localisation**: text lives in `Localization/English/<Mod>.xml` but the game reads the compiled `.loca`:
  `divine -g bg3 -a convert-loca -s X.xml -d X.loca` after every edit.

### Masks: what hides the body
- A visual's `VertexColorMaskSlots` hides **body** regions under the garment. The body mesh is vertex-painted
  with one colour per region; listing a region hides those body vertices. Names (case-sensitive): `feet`,
  `shins`, `knees`, `Thighs`, `hands`, `wrists`, `lowerarm`, `upperarm`, `Shoulders`, `Torso`,
  `decolletage_01`, `decolletage_02`, `Underwear_Bra`, `Underwear_Panties`, `Underwear_Panties_Tail`,
  `Private_Parts`, `ModestyLeaf`, `Nipple Covers`. `toes` is not a region (ignored); `feet` covers toes and
  lower shin. Regions are fixed: you cannot hide "half a thigh".
- Each slot is its own sibling node: `<node id="VertexColorMaskSlots"><attribute id="Object" ... value="Torso"/></node>`.
- **Equipped underwear is hidden the same way.** Underwear meshes are vertex-painted with the region colours
  (`#01A001` = `Underwear_Bra`, `#01AA01` = `Underwear_Panties`, `#022902` = `Private_Parts`), use a
  `VertCut` shader (`CHAR_BASE_MSK_VertCut_VT`), and a body garment that lists those regions culls them. It is
  not a root-template flag and not `ShowEquipmentVisuals` (an NPC-level switch that hides all gear).
- Garments that show bare skin replace the hidden body with their own geometry: the Nurse Skirt GR2 ships a
  trimmed nude-body mesh as one of its rendered objects with the vanilla skin material
  (`5e46e917-0c94-44ae-a41e-96428aa5ea32`). The same trick fills a gap: a small cut body piece in its own
  visual (`Slot` Footwear, that skin material, `SupportsVertexColorMask=False`).

### Shaders and colour
- `CHAR_BASE*` shaders need a bound `basecolor` texture (strip textures and it renders white); `*_VT` shaders
  need a `VirtualTextureParameters` binding; `VertCut` shaders need the region vertex colours on the mesh.
- Two colour conventions: older shaders read `Color_01/02/03`, newer ones read `Cloth_Primary/Secondary/
  Tertiary`, `Leather_*`, `Metal_*`, `Accent_Color`, `Custom_1/2`. A colour preset only changes parameters the
  shader actually has; a `Cloth_*` preset does nothing to a `Color_01` material.
- **Tint by preset:** root template `VisualSet > MaterialOverrides > MaterialPresets` with a
  `MaterialPresetResource` and `ForcePresetValues=True` (a dye preset UUID works; we used the one a vanilla
  dye's ItemCombination applies to make an armour black by default). It recolours **every** visual in the set
  whose material exposes those parameter names, which bleeds onto attached pieces.
- **Tint by cloned material:** clone the material under a new UUID, write the colours into its
  `Vector3Parameters` (`Value` and `BaseValue`, `Enabled=True`), point only one visual at it. Isolated and
  predictable; this is how the bleed was fixed.

### LODs
- The switch distance lives in the GR2, per mesh (`LODDistance`, written by the Blender addon from
  `ls_properties.lod_distance`); the visual's `Objects` only say which LOD slot a mesh fills.
- `lod_distance = 0` means "never switch": one mesh per object, one `Objects` entry with `LOD=0`, always drawn.
  This "single-LOD" pattern fixed a bag and a bra that vanished at distance.
- A non-zero distance on LOD0 with no next tier = vanishes at range. All tiers at 0 = all draw at once.

### Which meshes render
- **`Objects` assigns materials; it does not choose which meshes render.** Every mesh in the GR2 is drawn.
  Delete an `Objects` entry and that mesh still draws, untextured. To drop parts, edit the GR2 (see Build steps).
- In practice the engine matched `Objects` by mesh name even with a stale GR2 prefix and index. Do not rely on
  that; `ClothProxyMapping` does not behave that way (next section).

### Cloth physics (post-Patch-7)
Three pieces must all be right:
1. Visual `ClothProxyMapping`: one `Object` per mesh index with `MapKey` literally `..0`, `..1`, ... (two dots
   and the index, not an ObjectID). Blanket `..0` to `..10` is harmless on meshes without cloth paint.
2. GR2 per-mesh metadata on the simulated mesh: `DivModelType=Cloth` and a non-zero `LODDistance` (10 worked).
   In Blender: `ls_properties.cloth = True`, `lod_distance = 10.0`. Rigid parts stay `cloth=False`.
3. Root template `PhysicsTemplate` (inherited from the parent if absent; vanilla `ARM_Robe` chain carries
   `55f51913-5383-d402-d81d-4d179c66eb54`).
`ClothProxyMapping` can also carry `ClosestVertices` arrays (vertex indices into the cloth proxy mesh); any
vertex deletion invalidates them, so reset to the `..N` form after changing a GR2's mesh set.

### Icons (three lookups, plus a registry)
- **Tooltip:** `Mods/<Mod>/GUI/Assets/Tooltips/ItemIcons/<Name>.DDS`, 144x144, BC3, no mipmaps.
- **Controller / slot:** `Mods/<Mod>/GUI/Assets/ControllerUIIcons/items_png/<Name>.DDS`, same file.
- **Inventory / hotbar:** an atlas DDS (`Public/<Mod>/Assets/Textures/Icons/<Atlas>.dds`, 64x64 tiles,
  BC3 sRGB, no mipmaps), one TextureBank `Resource` per icon name in
  `Public/<Mod>/Content/UI/[PAK]_UI/_merged.lsf` (all sharing the atlas UUID, `Template="Icons_Items"`), and the
  UV map `Public/<Mod>/GUI/Icons_Items.lsx`, which stays `.lsx` (never compiled).
- **Registry:** `Mods/<Mod>/GUI/metadata.lsf` with one `Object` per DDS, `MapKey` ending in `.png` although the
  file is `.DDS`, plus `w`, `h`, `mipcount=1`. Missing it gives a "Missing MetaData" popup at startup.
- **A status icon uses the same `Icons_Items` atlas and the same two folders** (verified on a custom status).
  A separate `Icons_Skills` atlas with `Tooltips/Icons/` + `skills_png/` was structurally valid and rendered
  blank. Passives shown inside an item tooltip did not display custom icons either way.
- texconv: `texconv -nologo -f BC3_UNORM -m 1 -w 144 -h 144 -if POINT_DITHER -ft dds -y -o <out> <in.png>`.

### Equip sound
`EquipSound`/`UnequipSound` on the root template exist (FixedString, inherited from the parent), but setting
them to any of the three item-equip event families (`Items_Armor_*`, `Items_Armor_Smaller_*`,
`Items_Objects_*`) did not change what we heard: Wwise events carry logic modders cannot see. What worked:
**copy a vanilla item in the same slot that sounds right, wholesale**: its `ParentTemplateId`,
`PhysicsTemplate`, `VisualTemplate`, and no sound attributes if it declares none (`ARM_Vanity_ElegantRobe`
for a soft camp outfit).

### Delivery: a container in the tutorial chest
Stats `type "Object"` `using "_Container"`; a root template with `ParentTemplateId`
`aebf62bd-e68d-4e14-9ed7-1d51289a3e4e`, `InventoryType=11`, `TreasureOnDestroy=True` and
`InventoryList > InventoryItem(Object=<treasure table name>)`; `TreasureTable.txt` with
`new treasuretable "TUT_Chest_Potions"` + `CanMerge 1` holding the container, and the container's own table
with one `new subtable "1,1"` per item (`object category "I_<stats name>",1,0,0,0,0,0,0,0`). `CanMerge 1`
merges with every other mod's tutorial-chest additions.

## Build steps
**New item from existing pieces (no mesh edits):**
1. Find the source item from its display name: grep the source mod's `english.xml` for the text, take the
   handle, find the root template with that handle, read its `VisualSet` list for your body type.
2. Clone each visual you need (depth-matched node copy, new `ID`/`Name`), or reference it as is.
3. Write the root template by cloning a working one of the same slot verbatim and changing `MapKey`, `Name`,
   `Stats`, `Icon`, loca handles and the `VisualSet` list. Add the stats entry and loca, compile both.
4. Gate before packing: every `.lsx` parses, every GUID is hex, stats `RootTemplate` == RT `MapKey`,
   RT `Stats` == entry name, every visual/material GUID resolves in a bank under `Content/`.

**Editing meshes (the garment pipeline that ended up working end to end):**
1. Build an editable `.blend` by importing each GR2 with `import_scene.dos2de_collada`: garment collections,
   plus a **visible** reference body (`HUM_F_NKD_Body_A.GR2`) on its own armature. Expect welded vertex counts
   (vanilla body 9359 in the GR2 → 8044 in Blender); that is correct. Mark what needs editing in a named vertex
   group so it is one click to select.
2. The human edits LOD0 only and saves.
3. Sync LOD1 by deleting the **same parts** from vanilla's LOD1 (identify them by diffing edited LOD0 against
   pristine LOD0 per vertex island, by position) instead of re-decimating LOD0.
4. Export: delete reference collections (`use_active_layers=True` exports everything visible), drop empty vertex
   groups, set `ls_properties.export_order` 1..N in the order the visual expects, then
   `export_scene.dos2de_collada("EXEC_DEFAULT", filepath=<x>.GR2, use_active_layers=True,
   use_export_selected=False, use_triangles=True, use_tangent=True)`. The `.GR2` suffix is what makes the addon
   call Divine. Gate by converting the new GR2 back to DAE and reading mesh order, vertex counts,
   `LODDistance` and `DivModelType`.
5. Reset `ClothProxyMapping` to `..N`, repack, diff the new pak's file list against the installed one.

**Dropping whole meshes from a GR2 without Blender:** `divine -a convert-model -s Foo.GR2 -d foo.gltf -o gltf`,
remove the unwanted mesh nodes from `scenes[0].nodes` (keep the skeleton root), convert back with `-i gltf`,
convert the result to glTF again to check the mesh list. Then update the visual's `SourceFile`, `Template`
and every `ObjectID` (indices renumber in the new GR2).

**Combining another mod's garment with your own pieces (a soft-dependency top on our edited skirt):**
1. Read the source item's `VisualSet` for the body type. Some mods bake their own replacement body meshes into
   the garment GR2 (a torso and legs to sit under a catsuit); decide per mesh which ones to keep, and strip the
   rest from a copy of the GR2 (`Objects` alone cannot hide them).
2. Clone the source visual and copy its `VertexColorMaskSlots`, then drop only the regions no remaining mesh
   covers (here `Thighs`, once the leg pieces were gone), or the body vanishes there with nothing drawn.
3. Make every visual of the outfit carry its own complete masks and its own `ClothProxyMapping`, even when a
   partner visual in the same outfit already masks those regions. Masking a region twice is harmless; relying on
   the partner breaks silently the day the partner changes.
4. To hide equipped underwear under a garment that belongs to a mod you cannot edit, do the same: clone its visual
   into your mod, add `Underwear_Panties` (or the missing region), point your root template at the clone.

## Verification
- Every item was spawned and equipped in game by the human: rendering, colours, masks, icons in tooltip and
  inventory, and distance behaviour (walking the camera out).
- Cloth: the nightgown swings with the three cloth pieces set; with the GR2 copied straight from the source mod
  as a control, physics worked, which is how the missing `DivModelType` was found.
- Not verified: the stale-`ClosestVertices` case beyond "resetting to `..N` brought cloth back"; equip-sound
  theory (only the "mirror a reference item" result is verified).

## Gotchas
1. **Underwear rendered nothing, even pointing at vanilla visuals.** **Cause:** body-type GUIDs pasted in the
   other byte order: LSX written with `lslib_meta="v1,bswap_guids"` stores the first three groups swapped, so
   `71180b76-5752-4a97-1fb7-1a911969587f` and `...-b71f-911a69197f58` are different keys at runtime.
   **Fix:** copy GUIDs only between files with the same meta header; the canonical key is `...-b71f-911a69197f58`.
2. **Edits had no effect.** **Cause:** the `.lsx` was edited but never re-converted, so the pak shipped the old
   `.lsf`; or loca XML not compiled. **Fix:** convert after every edit and gate on file times.
3. **Item exists but is invisible everywhere.** **Cause:** a hand-written visual with 5 attributes instead of 21
   (no `MaterialType`, `SkeletonResource`, `BoundsMin/Max`, `ClothColliderResourceID`, ... and no
   `AnimationWaterfall`/`ClothProxyMapping`/`Base`). It packs and cross-references cleanly and draws nothing.
   **Fix:** clone a working visual node and change only `ID`, `Name`, `SourceFile`, `Template`, `ObjectID`s.
4. **Invisible after a re-export.** **Cause:** the GR2's mesh names changed (a vanilla source name leaked
   through), so `ObjectID`s no longer matched; or the model node name changed, so `Template` dangled.
   **Fix:** round-trip the GR2 to DAE and compare node names with the visual before packing.
5. **Removed parts still there, some untextured.** **Cause:** `Objects` does not gate rendering. **Fix:** strip
   the meshes from the GR2 (glTF route above).
6. **Cloned dress renders but has no cloth physics.** **Cause:** any one of: `ClothProxyMapping` written as full
   ObjectIDs or pointing at indices from the source's 10-mesh GR2; `cloth=False` on export; `cloth=True` with
   `lod_distance=0` (that makes the cloth mesh invisible). **Fix:** all three pieces of the cloth section.
   Physics does not show in a screenshot; test it moving.
7. **Item disappears at a distance / all LODs draw at once.** **Cause:** LOD distances, see LODs. Cloning LOD1
   into LOD2-4 slots made it worse. **Fix:** single-LOD with `lod_distance=0`, or declare every tier the GR2 has.
8. **A garment's own mask hid its own mesh.** **Cause:** the bra mesh was painted `Underwear_Bra` and its visual
   also masked `Underwear_Bra` with `SupportsVertexColorMask=True`. **Fix:** mask `Private_Parts` +
   `ModestyLeaf` on the bra visual. Likewise a skirt masking `Underwear_Panties` hid panties placed in the same
   outfit until their visual had `SupportsVertexColorMask=False`.
9. **Invisible ankle between stocking and shoe.** **Cause:** the shoe masked `feet` and `shins` but its mesh did
   not cover the lower shin, and the stocking masked nothing there: body hidden, nothing drawn. **Fix:** mask
   only what the mesh covers; additive garments with no masks are the safe default.
10. **Custom bra invisible with the vanilla underwear material.** **Cause:** a `VertCut` shader on a mesh whose
    region vertex colours were lost in the Blender round trip (the vanilla DAE had 3 colour sets, ours 1).
    **Fix:** paint the exact colour by script (`(1/255, 160/255, 1/255)`; Blender's picker rounds 1/255 to 0),
    or transfer colours from the vanilla mesh, and keep the `VertCut` shader so it still hides under armour.
11. **Panties red under one dress, navy elsewhere.** **Cause:** the cloned material's own `Cloth_Primary` was
    pure red; another item's preset had been masking it. **Fix:** clone the material per item with real values.
12. **Whole dress recoloured with the wrong palette.** **Cause:** a `MaterialPresets` entry recolours every
    attached visual. `ForcePresetValues=False` broke it; two sibling `MaterialOverrides` or a non-empty
    `MaterialResource` made the root template fail to load (invisible, no icon). **Fix:** bake colours into
    cloned materials and drop the preset.
13. **Placeholder visual GUIDs in a root template** silently fall back to the parent template's visuals, which
    looks like "my change did nothing". Check every GUID resolves.
14. **A cloak adapted from an underwear template rendered nothing**, even pointing at a vanilla cloak mesh.
    **Fix:** clone a vanilla cloak root template verbatim (`using "ARM_Cloak"`) and change only ids and visual.
15. **Clothing stats with an unwanted passive.** `ARM_Cloth_Body_1` inherits a Martial Arts passive; use
    `ARM_Robe_Body_1` for plain clothing. Walk the whole `using` chain before choosing a parent.
16. **Inventory icon missing while the tooltip works.** **Cause:** a packing step deleted `Icons_Items.lsx`
    because it looked like a stale twin. **Fix:** delete an `.lsx` only if a same-name `.lsf` exists.
17. **All new icons blank, every field identical to a working icon.** **Cause:** new `Object` nodes appended to
    `metadata.lsf` before the last `</children>`, one level too high (siblings of `entries`). **Fix:** insert
    after `<node id="entries"><children>`, and verify node depth against a working icon, not presence.
18. **Blender crashed opening a converted DAE / the GR2 came back broken.** **Cause:** LSLib 1.18.7 output and a
    Divine-only DAE→GR2 round trip (item lay on the ground, file 3.5x larger). **Fix:** LSLib 1.20.x and the
    dos2de addon for both directions. The addon then had a bug with spaces in paths (a subprocess call built as
    one string); we patched it locally to pass an argument list.
19. **Blend full of stray objects, oversized armature, wrong colour attribute names.** **Cause:** the addon's
    glTF importer (adds `Icosphere` objects for dummies, a `glTF_not_exported` collection, `Col` instead of
    `<mesh>-colors0`). **Fix:** import with the Collada importer, as every working blend was.
20. **Export wrote to the wrong path.** **Cause:** passing `auto_name` (or `directory`) to the export operator
    triggers a callback that resets `filepath`. `use_normals` is not a valid keyword. **Fix:** pass neither.
21. **`ls_properties` missing in a headless script.** **Cause:** the addon was enabled before
    `read_factory_settings`/opening the blend. **Fix:** enable it after the blend is loaded; also switch to
    OBJECT mode first (a blend saved in Sculpt mode makes operators fail on context).
22. **Hidden objects silently left out of the export**, and reference meshes left visible silently put in.
    Control visibility explicitly before exporting.
23. **Weights after moving parts.** Shrinkwrap destroyed thin straps; nearest-face weight transfer from the body
    picked wrong bones on a bag strap ("fine in Blender, broken in game" is always weights). What worked: split
    loose parts, move rigid parts by centroid, and paint per-region bone gradients with a smoothstep falloff
    (e.g. `Spine1_M → Chest_M → Scapula_L`). Max 4 bone influences per vertex; Divine drops the rest.
24. **Copying vertex positions between blends.** One blend was Z-up (armature transforms applied), the other
    Y-up (as imported): `(x, y, z) → (x, z, -y)`. Swapping `obj.data` loses vertex groups; replace the object.
25. **"New" visuals ignored entirely.** **Cause:** bank file under `Public/<Mod>/Assets/...` instead of
    `Public/<Mod>/Content/Assets/...`. **Fix:** move it under `Content/`.

26. **Leftover bits on the legs after removing a mesh.** **Cause:** vanilla garments hide geometry inside other
    meshes; two small islands on each ankle of a camp outfit's body mesh sat inside its high boots and became
    visible once the boots mesh was stripped. **Fix:** delete those islands in Blender and mirror the deletion to
    LOD1 (same islands, matched by position).
27. **Divine details that cost retries:** the action is `convert-resource` (`convert-resources` for a folder);
    `extract-single-file -f <path in pak>` is more reliable than `extract-package -x <glob>`; the source file's
    extension picks the format, so a backup named `*.GR2.old` fails with "Unrecognized model file extension"
    (name backups `*_PRISTINE.GR2`); some mod GR2s fail glTF export (a 60-bone skeleton under a mesh skinned to
    82 groups) and have to go through the Blender importer, which raises on the missing bones but imports the
    mesh and armature correctly.
28. **"Device or resource busy" when deploying.** The running game holds every loaded pak open; nothing gets
    replaced. Check for `bg3_dx11.exe`/`bg3.exe` before packing into the Mods folder.

## Open questions
- Whether the stale `Objects` ObjectIDs that still resolved (old GR2 prefix and index) are a documented engine
  behaviour or luck.
- A deterministic recipe for a sound that differs from the parent's, rather than mirroring a reference item.
