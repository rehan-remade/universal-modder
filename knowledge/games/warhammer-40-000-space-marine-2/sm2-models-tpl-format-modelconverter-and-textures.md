---
kind: game
title: "Space Marine 2 models and textures: the .tpl format, Saber's converter round trip, the shader cache and custom meshes"
game: "Warhammer 40,000: Space Marine 2"
games_also: []
game_version: "Steam build 25799387 (Patch 15.1, Oct 2026); most findings on Patch 14.x (Aug-Oct 2026). Mod Tools app 3856330 build 25506153 (ModelConverter v13/v14, UsfExporter, TextureConverter)"
platform: windows
engine: unknown
route: asset-only
tools: ["Saber SM2 Mod Tools (ModelConverter, UsfExporter convert_tpl.py, TextureConverter)", "Python 3 (numpy, scipy, struct)", "pymeshlab (Python 3.12)", "xatlas", "texture2ddecoder", "Blender (previews only)"]
anti_cheat: "EasyAntiCheat. Everything here uses Saber's official mods folder (client_pc/root/mods), which flags the session 'Mods Detected' (private lobbies, separate progression). No injection, no EAC interaction, PvE only."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-29
links: []
tags: [space-marine-2, saber, swarm-engine, tpl, gltf, modelconverter, usfexport, shader-cache, textures, pct, constructor, armour, custom-head, ai-mesh, collision, cloth, skin-weights, mml-cfg, parallax]
---

# Space Marine 2 models and textures: the .tpl format, Saber's converter round trip, the shader cache and custom meshes

> Two months of putting new geometry and textures into Space Marine 2: custom heads and helmets inside the player
> armour constructors, new weapon models, a whole new creature model, a vehicle swap and many texture repaints. This
> note is the model/texture layer: how a `.tpl` is laid out, what Saber's glTF -> USF -> tpl pipeline silently changes,
> the prebuilt shader cache that turns any unexpected material into a crash, and the rules for AI-generated meshes.
> Assumes [the foundations note](sm2-modding-foundations-paks-tools-and-crash-triage.md) (pak layout, ZIP_STORED,
> load order, mml_cfg, crash reports, Saber's mod rules). Verified in game unless marked otherwise.

## Setup
- Steam build 25799387 (Patch 15.1). Patch 15 grew the soldier/raider constructors by ~15 % and changed many class
  files: anything rebuilt from a pre-patch retail tpl is stale. Re-export retail after every patch.
- Saber Mod Tools. Two ModelConverter copies exist and they are not the same:
  `ModEditor/tools/bin/ModelConverter/ModelConverter.exe` converts **tpl -> glTF**; the copy in
  `ModelConverter/ModelConverter/` only does USF <-> glTF and silently prints its version when given a tpl.
  (2026-10-29) Versions differ too: the glTF -> USF converter inside the game folder
  (`<game>/client_pc/root/ModelConverter/ModelConverter/`) reports **v13.0.0**; the Mod Tools app's release and its
  `ToolsSource` are **v14.0.0**. The USF format is the same, but v14 builds a second material layer and a `map2` UV set
  when a material's extras name a second texture; v13 silently ignores that texture. On a big armour merge that was 279
  meshes in 40 groups, i.e. new material shapes and shader-cache risk. Pick one converter per project and keep it
  (details in [the all-class constructor note](sm2-one-constructor-for-every-class-and-fast-usf-builds.md)).
- UsfExporter (`convert_tpl.py`) turns the USF into `.tpl` + `.tpl_data` + `.lods_base` + `.geom_dbg` + `.cdt`.
- Saber ships the converter SOURCE in `ModelConverter/ToolsSource` (GltfConverter.cs, Tpl.cs, USF code). Reading
  `Tpl.cs` answered more format questions than any amount of hex diffing.
- Texture conversion: Saber's TextureConverter (BC7/BC5/BC3, writes the `.pct.resource` and mip entries; its mips are
  sharpened like retail's). `texture2ddecoder` decodes retail BC7 for analysis.
- Python 3.12 venv for pymeshlab and xatlas (no 3.14 wheels at the time).

## Route and why
Asset route: a file in a mod pak replaces the retail file at the same path, so a model mod ships its own `.tpl`
family, textures, `.td` materials and the `.resource` manifests that point at them. Two ways to build the tpl:

1. **glTF round trip** (retail tpl -> glTF -> edit -> ModelConverter -> UsfExport). Easy, handles new objects,
   skinning, LODs and tpl-baked animations. But it rebuilds every material from defaults and changes vertex data in
   ways listed below, so a round-tripped model needs a fix-up pass before it is safe. Used for new weapons, a new
   creature, armour constructors and props.
2. **In-place binary edit of the retail tpl** (rewrite vertex/index bytes inside existing streams). Every vanilla
   object stays byte-identical, so no shader-cache risk, but you work inside fixed stream sizes. Used for early
   head swaps and LOD repairs.

Prefer 1 for anything structural; prefer 2 when you only touch a few objects and the rest must stay retail.

## How the game works (what we had to learn)

### The files of one model
- `tpl/<name>.tpl` (binary, object tree + GeomManager), `.tpl_data` (vertex/index streams, read by byte range out of
  the pak), `.lods_base` (TEXT: LOD distances, per-object collision and visibility flags), `.geom_dbg` (object paths),
  `.cdt` (movement-collision shapes), `.tpl_markup` (render params, locators, physics shapes, animation roles).
- Manifests in `resources.pak`: `<name>.tpl.resource` (links: `linksPct`, `linksTd`, `linkTplMarkup`, `tplMarkup`,
  `linksTpl`, `tplAsset`, `tplDataChunks`, `tags`), `<name>.tpl_markup.resource`.
- Materials: `td/<tex>.td` (+ `.td.resource`), one per texture set, holding named submaterial blocks.
- Textures: `pct/<tex>.pct.resource` header in resources.pak + mip data as separate `pct/<tex>_N.pct_mip` entries in
  `default_pct_*.pak`. Concatenating the mip files does not give a valid pct.

### `.tpl` binary layout (GeomManager)
- Every chunk is `u16 id, u32 absolute end offset, payload`; a chunk list ends with id `0xFFFF` + u32. The
  GeomManager is the last section. Find it by its INFO chunk (id 0, 32 bytes: root u16 + object/stream/geom/split
  counts), not by a known string: weapons and props have no `CENTRE` bone, and some files carry data after the final
  sentinel.
- GeomManager children: id 5 refs, id 2 streams, id 3 geoms, id 4 splits. The order and field layout per stream
  follow `Tpl.cs WriteTo`.
- **Splits (id 4)** subchunks: 0 split info, 1 geom index (u32 per split), 8 material records, 4 maxTile, 5
  offset/scale (12 bytes per split).
  - Split info: `u16 firstVertex, u16 numVertices, u16 firstFace, u16 numFaces, u16 pad, u16 0xFFFF, u32 uvMask`,
    then `2 * popcount(uvMask)` floats (UV density). 16 / 24 / 32 bytes.
  - maxTile (subchunk 4): for every split whose FVF has a compressed-UV bit, in split order: `u8 count`, then count x
    (`u8 uvSet, i16 maxTile`). A one-UV-set split is 4 bytes, which makes it look like a flat table; it is not.
  - Offset/scale (subchunk 5): per split int16 offset[3] + int16 scale[3] for compressed positions.
  - Material record: `u16 owner object id`, then `u32 entryCount` and the entries directly (the top-level dict has no
    type tag; only nested dicts do). Value types: 1 int32, 2 float, 3 bool (1 byte), 4 u32-length string, 6 array
    (count, then type + value each), 7 dict (count, then key, type, value). Keys include `shadingMtl_Tex`,
    `shadingMtl_Mtl`, `mayaMtl`, `lm/layer0/texName`, `layer1.*`, `extraParams.extraVertexColorData.*`.
    Mis-reading the leading count as a type tag desyncs the whole table.
- **Geoms (id 3)**: subchunk 2 = per geom `u8 refCount` + (u32 stream index, u32 byte offset) per ref; ref slots 0/1
  are vertex streams, slot 2 the index stream (6 bytes per face, 3 x u16, geom-relative: a split's faces index
  `firstVertex..firstVertex+numVertices-1`). Subchunk 0 = 11-byte FVF descriptor per geom.
- **Streams (id 2)**: per stream an element stride and a **byte size**. `.tpl_data` = the streams back to back:
  base offset of stream k = sum of the sizes before it, and the sum equals the file size exactly.
- **Refs (id 5)** subchunk 0 holds two stride-8 tables (cumulative tpl_data offsets and stream sizes) that must BOTH
  be updated if any stream changes size. Never hard-code their offsets; search for the known sequence and assert one
  hit. A newer sub-chunk 4 in refs (i32 count + u16 per object) exists in some Patch-15 tpls and older Saber tools
  reject it ("Unknown chunk id: 4").
- **FVF bits** (from Tpl.cs): 0 VERT, 3 VERT_COMPR, 7 WEIGHT4, 9 INDICES, 10 NORM, 11 NORM_COMPR, 12-16 TANG0-4,
  17 TANG_COMPR, 22-24 COLOR0-2, 25-29 TEX0-4, 30-34 TEX_COMPR, 45 NORM_IN_VERT4, 67 MASKING, 69 WEIGHT8, 70
  INDICES16. Common character FVFs: `47008b1c02420020000040` (constructors), `47008b3c02c60020000040` (adds a second
  UV set: hair/special shading), `47008b1e02420020000000` (creature body), `47000b1c02420020000000` (rigid vehicle).
- **Vertex data**:
  - Positions are int16 per axis: `p = q / 32767 * scale + offset` with the split's offset/scale record.
  - UVs are u16 with divisor **32768** (not 65535), times the split's maxTile for that UV set. Dividing by 65535
    silently halves every UV.
  - Tangent: 3 signed bytes, `b = floor((t + 1) * 127.5)`, decode `b / 127.5 - 1`; the 4th byte is handedness
    (255 for +1, 0 for -1). Negating a tangent is `b -> 255 - b` on all four bytes.
  - The 2-byte packed normal is NOT a global encoding: one code maps to one normal within an object but to
    different normals across objects. You can still write it with a codebook harvested from the same object
    (nearest neighbour on the sphere; ~0.5 deg error with ~11k codes). Validate a codebook by predicting a different
    LOD of the same object.
  - Weapons' LOD0 often uses an UNcompressed normal (3 x float32); there positions are quantised per axis to the full
    int16 range. ModelConverter's own decode of that normal is wrong (~89 deg off).
  - Skinned layout seen in constructors: stream A stride 20 (`int16 xyz`, 2-byte normal, 4 x u8 weights, 4 x u16 bone
    indices), stream B stride 8 (4-byte tangent, u16 U, u16 V). Bone indices index the tpl's node-name table directly.
  - (2026-10-22) **Only three of the four weight bytes are weights.** Retail characters never use a real 4th
    influence, ModelConverter always writes 255 into the 4th byte, and only `JOINTS_0` / `WEIGHTS_0` are read
    (`_1` sets are ignored). In the retail soldier constructor ~415k vertices have w1+w2+w3 < 255 and the shortfall
    sits on whatever bone is in joint slot 3 (CHEST, CENTRE, helmet-tail jiggles: one helmet goes down to 216/255).
    The likely encoding is an implicit `w4 = 255 - (w1+w2+w3)` on slot 3 (inferred from data, not confirmed in game).
    With three weights summing to 255 nothing changes. To fit a 4+-influence source, merge per host joint, then
    **subtract-min** (subtract the smallest of the four from all, renormalise): it stays continuous across rank swaps.
    Dropping the lightest left a crease at the belt; a per-vertex best-3-bones fit crumpled the surface because
    neighbours picked different trios.
  - (2026-10-29) Skin joint ids are ids in Saber's object table, not indices into the flat name list: bones come
    first (`obj_list.json engine_objects`, `bone: true`), the name table skips one unnamed object after them, and
    names can repeat. Map ids through `engine_objects`, never with a name lookup.
- Node/bone names: one flat run of `u32 len + ascii` (bones, then locators, then mesh LOD nodes `<obj>_grp`, `<obj>`,
  `<obj>_LOD1..5`). A split's owner object id = name index + K, where K differs per file (+1, +4, +58 seen); anchor it
  empirically (LOD0 holds the most vertices and counts descend). Objects bind to splits through parallel u16
  `firstSplit` / `splitCount` tables before the GeomManager.
- `.geom_dbg` = one path per object in object-id order; strip the root and any Maya namespace to get the glTF node name.

### Renderer invariants found the hard way (in-place edits)
- **Never change the size of a vertex stream** (geom ref slots 0/1); growing and shrinking both broke rendering of
  the objects at the END of that stream. Index streams (slot 2) resize safely.
- Within one object's run of splits, splits that use the same geom must be contiguous (every retail file obeys it).
- Raising an object's active split count above its retail value broke the NEXT object on one model (Dreadnought) but
  not on another: treat retail counts as the safe ceiling; park extra splits as dormant records after the run.
- A misaligned maxTile table shows up as textures tiling at the wrong scale on later splits, easy to mistake for
  geometry or material corruption.
- The GeomManager's final end value can be stale and the engine does not care.

### Materials, `.td` and the prebuilt shader cache (the crash you will hit most)
- The game ships a prebuilt shader cache and never compiles at runtime. Asking for a shader permutation it lacks is a
  fatal crash: "Prebuilt shader cache or executable is obsolete". `error.yaml` of the crash report lists the shader
  stage and the full **define list** (e.g. `GLT_USE_ANISO_SPEC`, `GLT_USE_SUBSURFACE_SCATTERING`,
  `TINT_BY_MASK`, `DOUBLE_SIDED_LIGHTING`, `VP_USE_SKIN`) - read it, it tells you which material feature is new.
- What selects the permutation: the pair (per-geom FVF, material record "shape") plus the feature set of the `.td`
  submaterial the record resolves to (`shadingMtl_Tex` -> `td/<tex>.td`, `shadingMtl_Mtl` -> submaterial). Keep
  bools/ints/enums, shading-model names (`shadingMtl_Mtl`, `layer0/1.mtlName`, blending method, `lm.source`) and
  `layer1` as values; texture names do not matter. Every (FVF, shape, td feature set) in your model must already exist
  in some retail tpl. Checking FVF and material separately passes while the combination is still novel.
- **`tpl_markup` is mandatory for constructors.** UsfExport writes a `.tpl.resource` with empty `linkTplMarkup` /
  `tplMarkup` and no markup file. The markup carries `rendParams` (`allowHashedTransparent`, `allowDissolve`,
  `allowFresnelHighlight`, `allowCovering` ...) that are part of the permutation; without it every build crashed no
  matter how clean the materials were. Saber's Model Converter reference says so in its FAQ. Always take RETAIL's
  `.tpl.resource`, add only your `linksPct` / `linksTd` lines (alphabetical, CRLF), and ship retail's `.tpl_markup`
  + `.tpl_markup.resource`. Every `.td.resource` needs `name:` and `td:`, every `.pct.resource` its `linkTd`; a td
  manifest missing them crashed at boot reading near-null.
- glTF material `extras` carry only `texture` and `submaterial`. `layer1` (hair overlays), `uvSetIdx`, `colorSetIdx`
  and everything else are rebuilt from defaults. The material drives the vertex format: with no `layer1` nothing
  references UV1 and the exporter strips the second UV set, so the hair/special objects come back on a different FVF
  and become novel permutations. Affix flags and copying the retail `.td` folder into the exporter project do not
  change this. (2026-10-29) That is the game-folder v13 converter. The v14 converter (Mod Tools release / source)
  does build a second layer plus a `map2` UV set when the extras name a second texture, which is a different material
  shape again; see Setup.
- (2026-10-14) **Parallax materials lose their height-map reference.** Retail materials whose td has a `parallax`
  block (hull walls, floors, grills) carry `extraParams.parallax.baseLayerParallax.textureName = "<tex>_hdetm"` in
  every split record; UsfExport always writes `""`, so a copy of such a material is a pair retail never ships. Patch
  the string back into the material records (splits sub-chunk 8). Strings are `u32 len + bytes`, so the record grows:
  re-emit sub-chunks 4 and 5 with new end offsets, the parent splits chunk end (the only header whose end equals the
  old sentinel offset) and the final `0xFFFF` sentinel; a scan of every u32 found nothing else holding those offsets.
  The tpl.resource needs no extra link (the `_hdetm` pct arrives through the td.resource). Offline-verified; the
  in-game difference was not checked.
- (2026-10-29) **Retail itself ships records whose submaterial the td lacks** (e.g. a Raven Guard torso record asks
  for `default1`); they fall through to the engine's global default. A deliberately missing name such as
  `zz_global_default` is therefore a safe retarget for a crashing object, at the cost of its look.
- (2026-10-29) **A green "lens" may be a material, not a texture.** Retail scanner lenses get their colour from the
  `glass` submaterial's values (tint, filter, chameleon); the lens texture and `_em` are neutral. For a red glowing
  lens clone a whole retail td whose submaterial already has an emissive block and is used on your FVF in a retail
  tpl, change only values, and put the colour into the `_em` texture. Retail Vanguard lens values are around
  `intensity 30, bloomIntensity 500` (a value change only, so features stay identical; bloom look not yet confirmed
  in game).
- Fixes that worked: (a) never round-trip vanilla objects you do not need to touch; (b) patch the few fields that make
  a pair novel IN PLACE in the exported tpl (e.g. restore `colorSetIdx` 1/2/3/0 on cloth objects from the same-named
  retail record) - never splice whole retail records by name, objects have several variants; (c) retarget a crashing
  object's shading model to one retail pairs with your FVF (`default` exists everywhere), or give it a submaterial
  name the `.td` lacks, which falls through to the engine's global default material (always cached).
- A submaterial copied from ANOTHER model's `.td` crashed although the (FVF, name) pair existed: same name, different
  feature set. Clone a whole retail `.td` that already ships on your FVF and only rename/recolour.
- Recolouring by a tint-mask clone of a skinned, double-sided material (a colourable hood) crashed. Retail colours such
  pieces with recoloured TEXTURES on the retail material type; do the same.
- Detail maps: only safe as an exact copy of a retail material that has one, on the same FVF. Example recipe from the
  Thunderhawk hull tds: `detail = {density, scale}`, `detailDiffuse = {density}`, `tex = {det = "car_13_det",
  detailDiffuse = "det_metall_02"}` plus the `_em` 8x8 black placeholder those atlases carry. Density is per UV unit.
  Engine glt defaults live in `default_presets.pak` (`sdr_presets/glt_sdr_preset_default.sd`); a compact td = defaults
  + overrides. `_nm`, `_spec`, `_em`, `_hdetm` are found by name suffix from the td.resource links.
- Emissive lens recipe: own opaque material with glt `emissive {tint, intensity, adaptiveIntensity, bloomIntensity}` +
  an emissive texture (usage MEM). A missing `intensity` means zero glow. Retail lens `glass` submaterials have no
  emissive block; colourable lenses use a `default CC`-style submaterial with a `_cc` mask, and the glass is a separate
  non-colourable shell.
- `texType` on a custom BC3 texture's `.pct.resource`: leave it `''`. A build that set `nm`/`spec` crashed with a
  skin permutation (that build had a second change, so the blame is not certain; empty is proven safe).
- (2026-10-29) **Check new materials against RETAIL tpls only.** A merged build passed a feature-set check against
  the previous merged build plus retail, then crashed in game: the earlier build "passed" only because nobody had
  opened the screen that draws those objects. Reference sets must be retail files the game ships, never your own
  earlier output. The crash dialog's `error.yaml` for this class of bug names `vid_sdr_cache.cpp` and a glt vertex
  shader with defines such as `GLT_SFX_HIGHLIGHT`, `RENDERBLOCK_COLOR`, `GEOM_TWISTING`,
  `USE_CUSTOMIZATION_TEXTURES`. `GLT_SFX_HIGHLIGHT` is most likely the armoury's hover highlight (one such crash came
  exactly when hovering an item), so an object can render fine and crash only on hover (more in the all-class note).

### What ModelConverter and UsfExport do to your model (measured)
- Converter: needs ABSOLUTE input/output paths, reads `config.json` from the CURRENT directory, and throws a
  "Press any key" exception (exit 82) after finishing when stdin is not a console - the output is already written.
- tpl -> glTF output: scene roots `hierarchy` (full rig incl. locators), `ROOT` (skin joints) and
  `skinned_geometry`; meshes per object with `_LOD1..5` (as children of LOD0 - render LOD0 alone when previewing) and
  `_cdt`; materials named `<td>_matN`; vertex buffers are INTERLEAVED (honour bufferView byteStride or you get
  exploded geometry). Winding comes out CW because the converter flips on both import and export; don't "fix" it.
- (2026-10-29) **A raw tpl -> glTF export does not convert back.** Every skinned mesh lands on an ANONYMOUS node that
  is a detached scene root, while the same-named node in the hierarchy stays empty. Fed back in, the importer types
  the named node as a skin, finds no skin and logs "Skipping ... no skin attached"; the USF then holds only the
  skeleton. It also fools analysis (a class comparison that read raw exports saw no meshes and reported zero
  conflicts). Fix: move `mesh` + `skin` from each anonymous node onto the node whose name equals the mesh name (on
  constructors every mesh name matches a node exactly), delete the anonymous nodes, reindex.
- (2026-10-16) **Unnamed tpl objects come back without their matrix.** The tpl -> glTF converter builds unnamed
  objects as bare `Obj<id>` nodes and never sets their transform. Retail uses such nodes for real transforms: a chain
  axe's group carries scale 0.01 (body under it at x100), and the soldier constructor has 46 unnamed parents with
  translations and 90 deg rotations above the cloth/damper capsule end points `*_cdt_*_a/b`. Re-exported, the axe
  rendered 100x size (the armoury showed only giant specular edges, no crash) and 90 capsule points sat 0.1-2.4 m
  off (trinkets swinging through legs and head). Fix: read each object's LOCAL matrix from the original tpl with
  Saber's own reader (the FioSaveLoad / GeomManager classes in the Mod Tools source) and write every non-identity one
  into its `Obj<id>` node before converting. Quick check for the scale case: count float32 `0.01` hits in the tpl
  (retail 71, broken export 0). On the constructor, matching the 67 `Obj<id>` nodes by their named descendants
  restored 46 matrices and brought every capsule point within 1 cm of retail (offline check).
- (2026-10-29) glTF `bufferView` offsets are read as **Int32** (the converter uses SharpGLTF): a single 3.99 GB
  `.bin` failed. Split the buffers so each `.bin` stays under 2 GB.
- **Tangents.** tpl -> glTF never writes TANGENT; glTF -> tpl reads TANGENT if present, otherwise every vertex gets a
  constant default (bytes 255,127,127,0). Every round-tripped model therefore had its normal map applied through a
  wrong basis until we supplied tangents. And when you supply them, ModelConverter **negates them** (xyz and w) unless
  you pass `--keep-tangent-orientation`. Retail stores `t = +dP/du` orthogonalised to N, w = +1 when
  `cross(N,T) . dP/dv > 0`. Retail LOD1-5 tangents are carried over from LOD0 per face corner (up to ~30 deg out of
  the LOD's own tangent plane): to match retail exactly, copy retail bytes by matching position + UV, don't recompute.
  Supplying TANGENT does not change the FVF, so it is permutation-safe.
- **Vertex colours** reach the tpl only if the USF material has `colorSets` (the built-in "Default" material has
  none, "Cloth" has 0-3), and the channels come out rotated: `tpl(R,G,B,A) = glTF(A,R,G,B)` (Saber's Color
  Channels page calls COLOR0 / COLOR1 "Vector4 ARGB data"). Pre-rotate. A glTF
  `mesh.extras.materials = [{"data":{"str": <material ps text>}}]` replaces the generated material of the same name -
  that is how to give a non-`_sim` mesh colour sets. Verify by reading tpl_data bytes, not by round-tripping (the
  round trip shows the rotation too).
- Node typing is by NAME: a lower-case `_sim` makes `CLOTH_SIM` with the Cloth material; `_rend`, `_lod`, `_cdt`
  are group suffixes. Any glTF with a `ROOT` is treated as a character, needs a `skinned_geometry` node, and forces
  skin compounds on.
- **Skin compounds** (`build_skin_compound = true` by default) merge objects with the same vertex format into unnamed
  `@skin_compound__*` objects, each source object becoming a compound bone - including an animated LOD0 part merged
  with LOD1-4 copies of other parts. The affix `compound_skin_exclude` keeps one object standalone. Inspect
  `<out>.tpl/obj_list.json` (`engine_objects`, `skin_compound_sources`) after every export.
- **Names need the preserve affixes.** An object without `export_preserve_geometry` / `export_preserve_position` in
  its `extras.affixes` is regenerated as an anonymous internal object (`"name": ""` in obj_list.json). The armour
  library binds by name, so a nameless object matches nothing and renders on EVERY loadout. Copy the full affix block
  of a retail sibling (LOD0 and LOD1-5 forms differ). Affix strings are blank-line separated.
- **Tiny triangles are culled/collapsed** inside native UsfExport: anything under ~1.5-2 mm^2 in OBJECT space
  disappears, and dense slivers get collapsed (vertices moved 1-2 mm). Weld settings in `default_options.ps` don't
  control it. Workaround that works in game, also on animated parts: store the mesh x10 and give the node scale 0.1.
  Or keep every triangle >= ~3-5 mm^2; when building LODs yourself, build each one at its own edge length rather than
  decimating a dense one.
- **Positions shrink 0.8 %.** Saber's encoder fills int16 to ~+-32500, so re-encoding a decoded export compounds
  32500/32767: every object comes back 0.99185x about its split offset point. Effects: decals sink into pads, cloth
  moves closer to fixed collision capsules, seams open between parts with different split offsets. Fix by scaling the
  quantised positions by 32767/32500 after export (then compare to retail: identical +-1).
- **Zero-filled tail.** Once, the last ~40 MB of a `.tpl_data` (54 streams) came out all zeros with exit code 0 and a
  fully consistent `.tpl`. Re-running fixed it. Check every export for all-zero streams before packing.
- Primitives whose materials resolve to the same texture are merged, cut at 62,500 faces. LOD0-4 of one object share
  one stream set; we kept LOD0-4 under ~170k vertices (largest vertex stream ~3 MB) as a precaution.
  `share_geometry = false` changes nothing.
- Objects named `rb_*` (weapon collider) are exported without UV/tangent streams whatever their material; on a melee
  weapon the armoury preview then crashes on a shader miss. Export it under a same-length stand-in name and swap the
  bytes back in `.tpl` / `.lods_base` / `.geom_dbg` (names are not hashed).
- `.lods_base` comes out with empty defaults (no LOD distances, every object visible and solid). Retail hides
  colliders (`visibleDefault = false`) and turns movement collision off on weapon meshes: with retail-identical object
  names, ship retail's `.lods_base`; otherwise patch `lodInfo.maxLodDist` and the flags.
- A group and a mesh with the same name come back with the mesh renamed `..._ConvHack_00`; rename the group to
  `_grp` before export or presets stop matching.
- Animation keys are read as consecutive 30 fps frames: author at exactly 1/30 s or timing stretches. Every round trip
  adds one frame to each clip (normal). The converter's rest pose is the first frame of the alphabetically first
  animation. Frame events are offset by the clip's start on the converter's concatenated timeline, so list
  `RELOAD_FULL` first (see the [weapons note](sm2-weapons-skins-reloads-perks-vfx-and-sounds.md)).
- Re-exporting into a `models/database/<name>.tpl` folder that still holds the previous run's intermediates makes
  UsfExport exit 0 and write nothing; wipe it. `convert_tpl.py` deletes the project's `models/` folder, so two exports
  sharing one exporter project destroy each other mid-run: use a private project copy per job (it needs `.project`
  and `resources/resources_schema.yaml`).
- When merging glTFs, remapped `JOINTS_n` must be written as uint16 AND the accessor componentType set to 5123. A donor
  with < 256 joints stores uint8; copying its accessor header made the exporter read every index as two bones. The
  error is invisible at bind pose (identity skinning) and shreds the mesh once the lobby pose moves. Shallow-copying a
  node also shares its `extras` (all copies got the last copy's customization set).
- (2026-10-14) **UsfExport asserts that every vertex's FIRST weight is > 0** (`obj->GetVertBoneWeight(k, 0) > 0`
  in `obj_skin_tools.cpp`, exit -1, no tpl; the text is only in `usf2tpl.err`, and a multi-GB crash dump lands in
  the exporter project's `sandbox/crash_dumps`). ModelConverter accepts such input. Meshes written with joints in a
  fixed bone order trip it whenever a vertex is fully on a later bone. Sort each vertex's influences heaviest first
  (like retail), point unused slots at joint 0 with weight 0, assert `W[:,0] > 0` before writing.
- (2026-10-15) **UsfExport welds coincident vertices regardless of per-vertex masks.** Vertices with equal position
  and UV are merged (`weld_vtx` / `weld_uv` 0.00005 in `default_options.ps`) even when their paint/gore mask bits
  differ; retail seams survive only because their two sides have different normals. To keep a hard mask seam, nudge
  each extra coincident copy by +0.0002 in U per copy (0.4 texel at 2048, survives int16 UV compression) and verify
  by a round trip matched on position AND UV.
- (2026-10-29) **Memory.** glTF -> USF holds the whole USF in memory and converts every skinned mesh twice; a ~4 GB
  input needed ~33-34 GB and took 62 min on a 32 GB machine, almost all of it paging. Free RAM first, or see the
  all-class note for a splice and a low-memory converter build that cut this to minutes. UsfExport on the same model
  took 11-13 min.

### Player armour constructors and the customization library
- All armour pieces of a class live in one constructor tpl (`cc_sm_constructor_soldier`, `_raider`, ...; soldier
  ~587 joints, raider ~598). `ssl/body/customization/character_customization_library.sso` lists body sections ->
  regions -> items whose `meshes` name tpl objects. Presets live under `customizationPresets`, keyed by mastery type;
  `PVE_PVP_*` and `STORY_*` sections exist per class, and CHAOS reuses class names (parse the LOYALIST team only).
- **Visibility is per class:** a region-flagged object that none of that class's items list is DRAWN. When several
  classes share one tpl, every class shows the other classes' pieces unless you add `isHidden = True` regions
  listing them (retail uses `isHidden` on ~32 regions; key order `... rarity, isHidden, isForAllCharacters,
  appearanceUids`). Cover every drawable object at any depth (seals, ropes, glass, ammo), skip LODs and sim meshes.
  Some retail objects have no region affix and are always drawn (e.g. a class's torso base): never duplicate them.
- **Removing a region whose object is still in the tpl makes it an orphan that is drawn at load**; if its material is
  the problem you get the crash earlier, not later. Hide, don't delete. Conversely, an item copied into a class whose
  tpl lacks the mesh shows as an empty slot (a blank head).
- Menu names: `ssl/ui/screens/codex/ui_heraldry_library.sso` (uid -> `UI_..._NAME/_DESC`) + `texts/*.str`.
- **Physics is per CLASS FILE, not per tpl**: `prop_cloth_sim_magnus` (cloth), `prop_phys_jiggle`
  (`objectsSettings`), `prop_motion_damper` (`springDampers`). Moving a piece to another class's constructor means
  merging the matching entries into that class's cls (both directions); seals and tabards are cloth, not jiggle.
- **Cloth (engine name "magnus")** is declared in the character's client `.cls` AND its `_client_base.cls`:
  `clothes = [{ simMeshName, renderMeshes, simRemapConfig, config { stiffnesses, gravity, cdtCapsules, cdtSpheres,
  solverFrequency, damping, drag } }]`. The render mesh is remapped onto the sim mesh at runtime by proximity. The sim
  mesh is a hidden object (`_SIM`, skinned 100 % to CENTRE, needs `visibility_hidden` or it renders as a grey tube)
  whose **pin weight is COLOR_0.r: 0 = pinned, 254 = free**. With the converter's channel rotation, unrotated pins
  read as "nothing pinned" and robes fly apart. (Saber's Cloth page agrees on the direction: some sim vertices must
  be completely black, "otherwise cloth falls off".)
- **Grafted bones must be animated.** Pieces skinned to bones the class's animation set does not drive (bones grafted
  from an NPC rig) look perfect in the lobby (rest pose at the origin) and stretch into huge sheets in missions. Move
  such weights to the nearest driven ancestor, or to a jiggle-driven bone the class already simulates. Test in a
  mission after moving, never only in the lobby.
- The raider skeleton already has ~1,300 `_jiggle` bones and hair joints that a retail helmet drives; re-weighting
  hair strands onto them is the cheap route to secondary motion (not tried in game). Changing weights onto bones a
  vertex already uses cannot move geometry at bind pose - it only changes deformation.
- The armoury figure is a separate dummy (`ssl/loading_scene_logic/customizable_character_dummy_factory.sso`), keyed
  by mastery type and carrying its own physics. Robe cloth that works in missions exploded on the dummy; removing the
  robe sims from the dummy only fixed it. The dummy and preset traps of a cloned class (`masteryType`, `isChampion`
  presets) are in the [class note](sm2-new-playable-class-on-character-mod-slot.md).
  (2026-10-22 correction) Removing the sims only works when the render meshes are skinned smoothly. Robe RENDs taken
  from an NPC were split hard between HIP_L and HIP_R (one panel 95 % per side with a jump of up to 0.75 at the seam);
  unsimulated they tore 17-21x into floor-length sheets as soon as the figure's thighs moved. What fixed it (confirmed
  in game): simulate them on the figure with vanilla's OWN figure cloth entries as templates (`robe_shared_03_front`
  for a front panel, `_back` for side skirts; topological remap ~0.16), which use per-cloth radii ~1.2-1.4 with
  `collisionThickness -1` and so effectively ignore the figure's shared capsules. Never use the `_vest` template for
  hanging pieces (gravity -1, damping 0.7, high air drag: strips drift down for seconds); a scarf worked with its own
  mission entry copied whole.
- (2026-10-29) Bone names exist twice in a constructor glTF (the `hierarchy` tree and the `ROOT` skin tree), and a
  merged skeleton can repeat names inside `ROOT` as well. Read inverse bind matrices through the mesh's `skin`, and
  map bones by full node path, never by the first node with that name.
- (2026-10-29) A tpl family is several files (`.tpl`, `.tpl_data`, `.geom_dbg`, `.lods_base`, `.cdt`,
  `.tpl_markup`, `.tpl.resource`), and the first-sorting pak wins PER FILE. Several test paks that each shipped part of
  the soldier constructor made the game load a mix (header from one pak, data from another, markup from a third).
  Ship the whole family from one build and check which pak wins each path. A rebuild from your glTF source also drops
  any byte-level patch applied to the previous tpl_data (e.g. a head moved in place), so re-apply those after every
  rebuild.
- After Patch 15 split sections into HALO / CLOTH / COAT, any preset missing those keys leaves the equipped uid blank
  and the WHOLE slot shows "not available for the selected Class". Presets must match retail's key set for the
  current patch. An equipped challenge-locked item gives the same message.
- Painted backpacks draw albedo from `<tex>_a` and a mask `<tex>_cc`; overriding the base diffuse does nothing under
  paint. Retail also ships unused alternate textures (e.g. a `_1` set of a helmet) worth checking before repainting.
- Colour values for "game-like" metals come from `ssl/body/customization/armor_color_library.sso` (tints, metalness
  and roughness bias per paint).

### Custom heads and helmets
- **Host choice matters.** A head object in the raider constructor (`tank_head_01`) owns two LOD0 skin splits and
  fixed stream budgets; `sniper_head_01` frees ~58k contiguous vertices in one geom once its hair/beard/lash/eye
  splits are switched off and has its own 2048 atlas used by nothing else. Both are skinned 100 % to bone `HEAD`, so a
  fitted transform transfers between them.
- Authoring geometry in place without understanding the packed encodings: decimate with half-edge collapses only
  (survivors keep their records byte-for-byte); fill a broken LOD by copying a good LOD's records and rebasing its
  indices; recover a scrambled vertex order with a Hungarian assignment on position (max error ~1-2 quantisation
  units means it is a pure permutation). An earlier third-party build "shredded" only because LOD0/4/5 index buffers
  were built against a different vertex order than the one written.
- Neck weights: a head 100 % on HEAD swings its neck as a rigid cylinder against the collar. Copy retail's head skin
  profile (only the bottom inch inside the collar blends into NECK/BACKup), not the collar's.
- Skull helmets: rigid on the `helmet` bone, a separate lens object with customization set `HELMET_LENSES` for a
  colourable lens, and an optional glass shell submaterial in front. Fit by measuring penetrations against the hood /
  collar meshes; AI models are normalised differently (by height or by bounding box), so refit scale per model.
- Head texture channels measured on retail: spec R (metal) ~0 on skin, G roughness 70-255, B AO 185-255; normal-map
  xy std ~17; diffuse alpha = subsurface mask AND transparency (`useDiffAlphaMask`): 255 on skin, ~128 on hair/beard,
  0 in sockets/mouth. Don't ship an all-zero channel or a near-flat normal map; aim for retail's statistics.

### AI-generated meshes (Tripo-style): rules that held
These apply to private builds only: Saber's mod rules don't allow AI-generated content in mods you release.
- **Measure the UV atlas before planning LODs**: chart count, median triangles per chart, share of vertices on a seam.
  Atlases with thousands of 2-triangle charts (~92 % seam vertices) cannot be decimated (triangles end up spanning two
  unrelated charts) and their mips bleed. Big-chart atlases (~3 % seam vertices) decimate fine with pymeshlab's
  texture-aware quadric collapse (feed it OBJ + MTL; a mesh built from arrays has no texture slot).
- A per-VERTEX textured preview hides all of this; render per pixel with UV interpolation.
- Re-unwrapping (xatlas into a few hundred charts with padding) and baking through the surface fixes seams, mip mud and
  texel density, but re-laying out a fixed painted atlas cannot add detail that the source export does not have.
- **Weld before averaging normals** (accumulate on unique positions); per-index accumulation on seam duplicates gave
  one-sided normals, away-facing patches (dark blotches that change with the light) and cracked meshes after inflation.
- AI normal maps can be a mosaic of square patches with different tilt - it is in the asset (check in a painting
  tool). Drop or heavily reduce it on skin; it reads as blotches through any tangent basis.
- AI "ORM" channels are R=AO, G=rough, B=metal; SM2 spec is R=metal, G=rough, B=AO. Some generators put metal ~200
  on everything (renders chrome/gold): check per model and rebuild from colour classes with retail values.
  AI normal maps are OpenGL (green up); retail is DirectX (green down).
- Hard edges come smooth-shaded from AI meshes (lines on flat plates): crease-split normals at ~40 deg. Audit for
  inconsistent winding, duplicate triangles (z-fight hairlines), T-junctions from local subdivision and open boundary
  loops before export; a software preview hides all four.
- Hi-poly and low-poly exports of the same generation are not at the same scale; align with an affine ICP before
  transferring detail.

### Textures (`.pct`)
- Formats seen: 52 = BC7 colour, 51 = BC7 (spec and others), 36 = BC5 (normal maps; weapon spec is BC5 R metal /
  G rough with td usage `MSCG+MRGH`), 17 = BC3 (accepted for custom textures). Usage tags: `MD` diffuse, `MD+MT` diffuse
  with transparency alpha, `MAO` (the converter reads AO from ALPHA: an RGB-only source gave black AO), `MEM` emissive,
  `MDT` detail. Normal maps are DirectX convention.
- Retail character sets are 2048 and listed in `mml_cfg` (see the foundations note): an unlisted 4096 is shown at
  2048 on High (measured from the exe), part of why a custom creature looked muddier than retail ones. The rest was
  the AI surface itself (lumpy mid-scale relief), which no resolution fixes. 8192 is only used for skies.
- Pillow resizes RGBA as premultiplied: with an SSS mask in alpha (0 on armour) an RGBA resize blacks out the RGB
  there. Resize RGB and alpha separately. `Image.BOX` when UPscaling is nearest-neighbour (blocky). Near-black paint
  needs variation in sRGB levels, not linear percentages, or it looks flat.
- AI atlases need chart-aware mips (each lower-mip texel averages only its dominant chart) or skin goes dirty at
  distance; the real fix is fewer, larger charts.
- Source TGAs handed to the converter should match retail's layout (uncompressed type 2, top-left origin, the
  TRUEVISION footer; copy the retail alpha plane if you only repaint RGB).
- UI textures (crosshair bitmaps): `.pct.resource` with format 0, one mip, and the mip file holding raw
  premultiplied BGRA pixels.
- (2026-10-15/23) **TextureConverter channel map**, measured with constant-colour test TGAs decoded back:

  | td usage | pct format | what is stored |
  |---|---|---|
  | `MD+MT` | 52 BC7 sRGB | RGBA as given |
  | `MNM` | 36 BC5 | XYZ renormalised, then XY |
  | `MSCG+MRGH` | 36 BC5 | R = metal, G = roughness taken from the source **alpha** |
  | `MAO` | 37 BC4 | AO taken from the source **alpha** |
  | `MEM` | (RGB-only format) | output alpha ~0 whatever the source |

  So write roughness into A (A = G) for weapon/tyranid specs. An `MNM` source needs a real Z in blue
  (`z*0.5+0.5`): with B = 0 the converter renormalises (x, y, -1) and flattens every normal. A three-channel
  `MSCRGHAO` spec (vehicles) reads B as AO, so a spec derived from a weapon needs B = 255. On Tyranid sets the
  `_em` texture is an AO map (usage MAO), not emissive.
- (2026-10-15) `convert_settings.resample = 1` in a td (sword / torso tds have it) HALVES the output: feed 2x the
  wanted size or set it to 0. The converter's `pct_resource_gen` step links only pcts that already exist, so convert
  the base texture LAST. It also writes a `.td.resource` and pct files into the shared exporter project; remove yours
  afterwards. The Mod Tools UsfExporter project already contains every retail td (18,316, identical to
  `default_td.pak`): to rebuild a retail-named texture use that td as is.
- (2026-10-14) **`mml_cfg` and non-retail sizes.** `topmip` counts kept mips from the smallest STORED one, and a
  chain stops at the 4-px short side (a 2048x512 texture stores 8 mips; retail lists it Ultra 9 / High 8 / Medium 7 /
  Low 6; non-square textures are common in retail). An entry copied from a 2048 template for a 4096 texture must add
  the extra stored mip on Ultra/High/Medium/Low (High 10 -> 11), or the 4K map is shown at 2K. Insert entries into the
  current retail file and ship it (foundations note); only one pak can win that path, so merge entries from several
  mods into one copy.
- (2026-10-22) Chrome-like painted metal measured on a retail gauntlet: metal 255, albedo ~148 neutral, roughness
  p10/p50/p90 = 48/63/119.

### Props, vehicles and collision
- Physics shapes built from mesh streams (`*_glr` convex shapes on a rigid-body object) crashed a level load (null
  stream pointer inside a convex-hull builder) for an exported prop, while retail ones work; cause unknown. Analytic
  boxes in the `tpl_markup` work: `tpl_markup_shape_box` entities (full extents W/H/D along the owner's local axes,
  centred at `localTransform.position`) on the rigid-body object, as retail turrets and the Dreadnought do. Capsules
  exist as `tpl_markup_shape_capsule`. Keep boxes axis-aligned (rotation order unverified). The server has no `.tpl`
  and builds physics from `.cdt`.
- **Player movement collision is the `.cdt` system, not Havok.** Affix groups `cdt_low_res_geometry` (invisible
  collision with player/AI/vehicles/camera) vs `cdt_high_res_geometry` (weapons/projectiles only). UsfExport bakes
  per-object flags into `.lods_base` (`collision = { plrMove = false ... __type = "tpl_markup_cdt_flags" }`).
  `geom.collisionLayerName` only picks a Havok layer and does NOT stop movement collision; a skinned prefab's movement
  collision comes from `geom.cdtSkeleton` (`geom_cdt_skel_tpl`), which can be removed from the class.
- **Level static collision** lives in the scene: `<scene>.cdt` is per-layer MOPP code over the geometry of
  `<scene>.lg` / `.lg_data` (no vertices of its own). The Map Converter guide says scenes can't be decompiled; reading
  them works anyway (the `.lg` is GeomManager-style chunks). Invisible walls are objects named
  `scripting|constrains|...` and similar. Remove one by making its faces degenerate in `.lg_data` (copy the first
  index over the other two): same size, MOPP untouched. Moving vertices does not move the collision.
- Prefab vehicles: a modded tpl BIND pose is ignored for animation; the game poses prefab bones from the retail rest
  and stacks additive TPL clips on it. Build anything riding a prefab bone relative to the retail rest pose and
  re-author the clips that move it.
- Swapping one vehicle model for another per level is a level-file edit (`class_list` `nameTpl`, `linksTpl`,
  cutscene copies: see the [missions note](sm2-missions-scenarios-faction-swaps-and-esd-spawning.md)). Model side:
  `objectsOverrides` hides old parts by RUNTIME object name, but unnamed skinned objects can't be targeted (hide
  `ROOT`), or point part classes at a locator-only tpl. A rigid hull placed directly inside an animated rig (no skin
  compounds) crashed in vertex-buffer binding; a static tpl on a root-attached part worked.
- Effect locators (jets, eye glows) come from the ANIMATION RIG at runtime; moving them in the tpl changes nothing.
  Either ship a renamed copy of a locator-only tpl and point `geom.nameTpl` at it, or offset the effect's own
  `transform` in the class, which IS applied relative to the locator.

### Replacing an NPC's mesh with a differently proportioned one
- Morpheme clips carry every bone's translation, so at runtime joints sit where the HOST's clips put them, whatever
  bind pose your tpl stores. Fitting the tpl skeleton to the new mesh stretched it in game. Either deform the mesh
  offline onto the host's bone offsets, or give the creature its own skeleton and rewrite the clips' fixed offsets
  (see the [NPC/animation note](sm2-new-enemies-npc-classes-and-morpheme-animation.md)).
- Verify by posing with the game's skinning (linear blend on the real rig), not by reading weight tables: rigid
  islands that share a welded shell (head vs hood) need a blend band between them; armour plates must be rigid on one
  bone each or they fold at the elbow; fingers need whole-finger components on the WELDED mesh.

## Build steps
New standalone model (weapon, prop, creature body):
1. Export the retail tpl you replace to glTF (ModEditor's ModelConverter, absolute paths) and copy its node tree,
   object names, affixes, LOD layout and tpl-baked animations. (2026-10-29) Before using that export: move meshes off
   the anonymous root nodes onto their named nodes, and copy the real local matrices of every unnamed `Obj<id>` node
   from the retail tpl.
2. Build your meshes into that tree (x10 + node scale 0.1 for small detail), one material/texture set per `_matN`,
   glTF TANGENT on every primitive, COLOR_0 pre-rotated where needed.
3. ModelConverter (cwd = its folder, `--keep-tangent-orientation`) -> UsfExport in a private project copy.
4. Check `obj_list.json` (names, face counts vs glTF, compounds), stream sizes, all-zero streams, tangents vs UV-derived
   frames, and every (FVF, material, td) triple against retail tpls.
5. Fix up: retail `.tpl.resource` + your links, retail `.tpl_markup(.resource)`, `.lods_base` flags/distances, collider
   name swap, unshrink positions if you compare to retail.
6. Textures via Saber's converter; td cloned from a retail td on the same FVF; `mml_cfg` entries.
7. Pak as ZIP_STORED with the manifests; test in game.

Adding pieces to an armour constructor: same, plus merge into the retail constructor glTF (uint16 joints, own `extras`
per copy, bones only from the class's driven rig), fix cloth pin colours and `colorSetIdx`, ship retail markup, add
library items/regions and `isHidden` regions for leftovers, merge physics entries into each class cls, update the
armoury dummy.

## Verification
- In game: round-tripped armour constructors with added helmets/heads/robes (rendering, cloth, class visibility), a
  new creature model with LODs and BC7 textures, new weapon models with tpl-baked reload/shot animations, a vehicle
  hull swap in levels, crash/no-crash for every shader-cache rule above, the tiny-triangle workaround, the
  grafted-bone stretch and its fix, the per-class visibility rule, the prefab bind-pose rule, the locator rule.
- Offline only: tangent byte encoding (99.95-100 % byte-exact vs UsfExport output), position shrink (5,160 of 5,172
  objects integer-identical to retail after the fix), maxTile parsing (28,084/28,084 bytes), scene `.cdt` decoding.
- Not verified in game: the latest tangent and unshrink fixes on every model, the scene-collision face removal, cloth
  hair re-weighting, the convex-shape crash's root cause.
- Added 2026-10-29. In game: the 100x weapon from a dropped `Obj<id>` scale (later builds with the matrix restored
  were played and worked), the robe-on-armoury-figure fix with vanilla figure templates. In the tools: the
  first-weight assertion and its fix, the anonymous-mesh-node export bug, the Int32 buffer limit. Offline: the
  TextureConverter channel table (constant-colour round trips), the 3-weight / slot-3 remainder statistics, the
  capsule points back within 1 cm of retail after restoring `Obj<id>` matrices, the v13/v14 second-layer difference
  (structural USF diffs), the mixed tpl family (by listing which pak wins each file). Not verified in game: the
  parallax record patch, the implicit 4th weight, lens bloom values.

## Gotchas
1. **Crash "Prebuilt shader cache or executable is obsolete" when an item is equipped or a level loads.** Cause: a
   novel (FVF, material shape, td submaterial) combination, very often from the glTF round trip dropping `layer1` /
   `colorSetIdx` or from a submaterial cloned from another model. Fix: read the define list in `error.yaml`, check
   every triple against retail, patch the fields in place or fall back to a cached shading model.
2. **Every rebuilt constructor crashed on the shader cache even with a clean material table.** Cause: UsfExport's
   `.tpl.resource` has empty `linkTplMarkup` / `tplMarkup`. Fix: retail resource + retail markup.
3. **Whole model renders with wrong materials after an in-place edit.** Cause: a hand-written `.tpl.resource` that
   blanked the markup link and dropped keys. Fix: rebuild it from retail, change only `linksPct` / `linksTd`.
4. **Normal map lighting "blotchy" on every round-tripped model.** Cause: no glTF TANGENT -> constant default
   tangents. Fix: supply tangents.
5. **Supplied tangents made it worse (99.6 % reversed).** Cause: ModelConverter negates TANGENT by default. Fix:
   `--keep-tangent-orientation`.
6. **Capes, tabards and robes hang rigid or fly apart after a rebuild.** Cause: COLOR_0 pin weights rotated by one
   byte, or lost entirely on cloth meshes whose names lack `_sim`. Fix: pre-rotate, give those meshes a material with
   colour sets via `mesh.extras.materials`, then restore retail `colorSetIdx`.
7. **A custom pauldron showed on every pauldron choice.** Cause: missing preserve affixes -> nameless object. Fix:
   copy the retail affix block; grep `"name": ""` in obj_list.json.
8. **Holes in fine detail (insignia, rims, lens LOD0).** Cause: UsfExport culls triangles under ~2 mm^2 in object
   space. Fix: mesh x10 + node scale 0.1.
9. **Several unrelated cosmetics vanished at once, no crash.** Cause: zero-filled tail of `.tpl_data`. Fix: re-export
   and scan for all-zero streams before packing.
10. **Decals sink into armour, seams open a few mm.** Cause: the 0.8 % re-encode shrink. Fix: rescale quantised
    positions by 32767/32500.
11. **Mesh shredded into long shards in the armoury, fine at bind pose.** Cause: merged JOINTS written as uint16 under
    a uint8 accessor header. Fix: set componentType 5123; verify by listing top-weighted bone names per object.
12. **Huge stretched sheets in missions only, lobby perfect.** Cause: weights on grafted, never-animated bones. Fix:
    re-bind to driven ancestors or jiggle-driven bones; test in a mission.
13. **Every class wears every other class's armour.** Cause: shared tpl + per-class visibility of unlisted region
    objects. Fix: `isHidden` regions per class covering every leftover object.
14. **Removing a crashing vanilla item made the crash happen earlier, at load.** Cause: orphaned tpl object drawn
    unconditionally. Fix: hide the region instead of deleting it.
15. **Whole armour slot "not available for the selected Class" (misleading text).** Cause: a preset lacks a Patch 15
    section key (blank equipped uid), or an equipped item is challenge-locked. Fix: match retail's preset key set for
    the current patch; strip or satisfy challenge locks.
16. **A helmet rendered collapsed although its own bytes were retail.** Cause: the previous object's streams changed
    size (vertex stream growth), plus misaligned maxTile entries. Fix: keep vertex stream sizes, fix maxTile per split.
17. **Textures tiling at the wrong scale on some parts.** Cause: maxTile table read/written as a flat array. Fix: the
    per-split `u8 count` + (u8 set, i16 tile) layout.
18. **UVs look like they sample a quarter of the atlas.** Cause: dividing u16 UVs by 65535. Fix: 32768 x maxTile.
19. **Writing the stream-size table 5 bytes off crashed the game, and the validator said PASS.** Cause: hard-coded
    offset, validator read the same wrong place. Fix: locate tables by searching, verify at the discovered location.
20. **Melee skin crashed in the armoury preview; then the collider drew as a white wedge.** Cause: `rb_*` objects lose
    UV/tangent streams in UsfExport, and the exported `.lods_base` makes every object visible. Fix: stand-in name +
    byte swap; ship retail `.lods_base`.
21. **Exporter exits 0 and writes nothing.** Cause: stale `models/database/<name>.tpl` intermediates. Fix: wipe it.
    Two jobs sharing one exporter project also wipe each other: use private copies.
22. **Moving tpl locators/bind pose changed nothing in game.** Cause: locators and bone positions come from the
    animation rig; prefab bind patches are ignored. Fix: offset effects in the class, re-author clips.
23. **Mesh fitted to a custom skeleton warped "to hell" when animated.** Cause: clips carry the host's bone
    translations. Fix: deform the mesh to the host offsets, or rewrite the clips' offsets for an own skeleton.
24. **Dark blobs on a custom face that change with the light.** Cause: normals averaged per vertex index on an AI atlas
    (seam duplicates) -> away-facing normals. Fix: weld before averaging.
25. **Polygonal patches on skin that survive every texture fix.** Cause: AI normal-map patch mosaic, or tangents copied
    from donor vertices with different UVs. Fix: drop the AI normal map on skin; write UV-derived tangents.
26. **Face looks clean close up, muddy at distance.** Cause: box-filter mips across tiny charts, and an unlisted 4K
    texture halved on High. Fix: chart-aware mips or a re-unwrap; `mml_cfg` entries.
27. **Every chitin/armour texel went black after resizing.** Cause: Pillow's premultiplied RGBA resize with an SSS
    alpha of 0. Fix: resize RGB and alpha separately.
28. **Level crashed loading an exported prop with physics.** Cause: convex `*_glr` shapes read stream data that was not
    resident. Fix: markup box shapes.
29. **Invisible wall the player can't pass after moving a prop.** Cause: level static collision (scene `.cdt` over
    `.lg`) or the prefab's `cdtSkeleton`, not Havok. Fix: degenerate the wall faces in `.lg_data`; remove
    `cdtSkeleton` from the class. `collisionLayerName` does not help.
30. **Lens lost its glow after export.** Cause: the lens faces were merged into the `default` submaterial. Fix: keep
    the lens as its own primitive with the retail `glass` (or an emissive) submaterial, with `intensity` set.
31. **Boot crash reading near-null after adding a texture set.** Cause: a cloned `.td.resource` lost its `name:` /
    `td:` lines. Fix: assert both on every td manifest.
32. **Robes explode on the armoury figure only.** Cause: dummy cloth config. Fix: remove the robe sims from the dummy
    entries (missions keep them), or use Saber's long-robe dummy settings. (2026-10-22) Removing the sims tears robes
    whose render meshes are split hard between the hips; the fix confirmed in game was simulating them with vanilla's
    own figure entries (`robe_shared_03_front` / `_back`) as templates, see gotcha 46.
33. **A re-exported weapon shows only giant specular edges in the armoury; trinkets swing through the legs.**
    Cause: unnamed `Obj<id>` nodes lose their matrices in tpl -> glTF (a 0.01 group scale, capsule parents' offsets).
    Fix: copy each unnamed object's local matrix from the retail tpl into the glTF before converting.
34. **glTF -> USF output holds only the skeleton ("Skipping ... no skin attached").** Cause: the raw tpl -> glTF
    export puts meshes on anonymous root nodes. Fix: move mesh + skin onto the same-named node, delete the anonymous
    ones.
35. **UsfExport exits -1 a few minutes in, no tpl.** Cause: assertion `GetVertBoneWeight(k, 0) > 0` (read
    `usf2tpl.err`): a vertex whose first weight slot is 0. Fix: sort influences heaviest first; delete the multi-GB
    crash dump it leaves in the exporter project.
36. **Conversion of a very large merged glTF fails reading buffers.** Cause: Int32 bufferView offsets; one 3.99 GB
    `.bin`. Fix: split into several `.bin` files under 2 GB each.
37. **glTF -> USF takes an hour and the PC crawls.** Cause: the converter keeps the whole USF in memory and converts
    skinned meshes twice; past physical RAM it pages constantly. Fix: free RAM, or splice changed groups / use a
    low-memory converter build (all-class note).
38. **A second texture requested in a material's extras never shows, or a converter swap creates new shader
    shapes.** Cause: the game-folder v13 converter ignores second textures; v14 adds a second layer and `map2` UVs.
    Fix: one converter version per project; audit materials if you switch.
39. **A copied hull/floor material with parallax may crash or look flat.** Cause: UsfExport blanks
    `baseLayerParallax.textureName`. Fix: write `<tex>_hdetm` back into the records and fix the chunk end offsets
    (in-game effect not checked).
40. **Normal map converts completely flat.** Cause: `MNM` source with B = 0. Fix: store a real Z in blue.
41. **Weapon or creature looks mirror-glossy / matte everywhere after a repaint.** Cause: `MSCG+MRGH` reads roughness
    from the source alpha. Fix: write roughness into A (A = G).
42. **Converted texture is half the expected size.** Cause: `convert_settings.resample = 1` in the cloned td. Fix: set
    0, or feed 2x.
43. **A new texture set is missing from its td.resource links.** Cause: `pct_resource_gen` links only pcts that exist
    when it runs. Fix: convert the base texture last.
44. **A 4K texture looks no sharper than the 2K one it replaced, even on High.** Cause: the `mml_cfg` entry copied
    from the 2048 template keeps the template's mip count. Fix: add the extra stored mip on every quality slot.
45. **A hard paint/gore mask seam comes back on the wrong vertices.** Cause: UsfExport welds coincident vertices
    with equal UVs regardless of masks. Fix: nudge each extra copy +0.0002 in U.
46. **Robe sheets to the floor on the armoury figure after the sims were removed from it.** Cause: NPC robe render
    meshes split hard between HIP_L / HIP_R tear once unsimulated. Fix: simulate them with vanilla's own figure cloth
    entries as templates (front / back); never the `_vest` template for hanging pieces (slow drifting strips).
47. **The model the game loads is not the build you think (fixes missing, parts from older tests).** Cause:
    first-sorting pak wins per file, so the game assembled one tpl family from several paks. Fix: ship and check the whole family
    together.

## Assets
Custom meshes came from AI 3D generation (Tripo) and from retail parts re-used inside the game's own tpls; textures
were baked from those sources, repainted in Substance Painter by the human, or derived from retail textures
(recoloured, high-pass detail transferred triplanar). Nothing from the game is attached to this note. Saber's mod
rules forbid AI-generated content in mods (see the foundations note's Setup), so keep builds with the Tripo meshes
private and use hand-made meshes for a release.

## Open questions
- Root cause of the convex-shape physics crash on exported props.
- Whether the engine draws skin compounds that mix LOD levels per bone or as a whole.
- Exact effect of `texType` on custom textures.
- A reliable way to enumerate the cached shader permutations (the `.sdc` cache is hash-keyed, no define strings).
- (2026-10-29) Whether the 4th weight byte really encodes an implicit remainder on joint slot 3.
- (2026-10-29) Seen in the ModelConverter source, not checked on data: the non-masked vertex-colour path appears to
  index colours per primitive instead of per mesh, so in a multi-material mesh with colour sets the 2nd and later
  primitives could overwrite the first primitive's colours and leave their own at 0. Worth checking before blaming
  `colorSetIdx` for colour bugs on multi-material meshes.
