---
kind: game
title: "A brand-new playable map in Space Marine 2 with Saber's Map Converter, plus hub scene edits"
game: "Warhammer 40,000: Space Marine 2"
games_also: []
game_version: "Steam build 25799387 (Patch 15.1, Oct 2026). Mod Tools app 3856330 build 25506153 (ModelConverter --map_mode, UsfExporter, Furnace, AIConverter, TerrainConverter, LightProbeConverter, resolve_scene_resources)"
platform: windows
engine: unknown
route: data
tools: ["Saber SM2 Mod Tools (ModelConverter --map_mode, UsfExporter convert_tpl.py, furnace.exe, TextureConverter / convert_pct.py)", "Saber's shipped converter source (ToolsSource: MapConverter.cs, MapBuilder)", "Python 3 (own glTF writer, tpl_markup / lods_base patchers, lwi_container and dom_list readers)", "Blender (preview renders with back-face culling, BC6H decode)", "a small Win32 window-text reader for hidden crash dialogs"]
anti_cheat: "EasyAntiCheat. Everything here uses Saber's official mods folder (client_pc/root/mods), which flags the session 'Mods Detected' (private lobbies, separate progression). No injection, no EAC interaction, PvE only."
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-29
links: ["https://spacemarine2-modding.prismray.io/"]
tags: [space-marine-2, saber, swarm-engine, map, level, map-converter, furnace, gltf, lwi, instancing, grass, collision, cdt, sky, lighting, shadows, prefab, water, hub, dom-list, navmesh]
---

# A brand-new playable map in Space Marine 2 with Saber's Map Converter, plus hub scene edits

> We built a new 800 m outdoor PvE level for Space Marine 2 from our own glTF. It went through Saber's Map Converter
> (ModelConverter `--map_mode`) and Furnace, then got packed as a mission. It has terrain, a walled town, tens of
> thousands of instanced grass tiles and trees, a custom night sky with a moon, lamps and fires, a river, invisible
> walls and an animated ambient animal. The pipeline works end to end in game: test scenes and the full grey box load
> and are walkable. Later builds of the same map were played and exposed the limits below. Some parts are still
> untested in game; each one is labelled. The note also covers in-place edits of the retail hub scene (collision,
> instanced props, trigger zones). It builds on [the foundations note](sm2-modding-foundations-paks-tools-and-crash-triage.md)
> (paks, load order, ZIP_STORED, crash dumps), [the models note](sm2-models-tpl-format-modelconverter-and-textures.md)
> (tpl format, shader cache, `.cdt`, scene static collision) and
> [the missions note](sm2-missions-scenarios-faction-swaps-and-esd-spawning.md) (level file list, mission registration,
> navmesh rebakes, the ESD spawn director).

## Setup
- Steam build 25799387 (Patch 15.1). Saber's Mod Tools, Oct 2026 update. Read `Map_Converter_Guide.pdf` from the Mod
  Tools and Saber's docs site first. Then keep `ToolsSource/ModelConverter/Convert/MapConverter.cs` open: it answers
  what each glTF extra does faster than trial bakes.
- **A toolchain root in Saber's documented layout.** We used a mirror at `<toolchain>/client_pc/root` (called
  `<root>` below) holding
  `.project`, `prjenv`, `tools/bin` (ModelConverter, `ResourceTools/furnace`, the `ResourceManager` CDT / AI / Terrain
  converters) copied from the Mod Tools' `ModEditor`. It also holds `mods_source/`, `local/`, and junctions to the
  game's paks, `bin/pc`, prebuild and loadconfig (and `server_pc/root/paks`). The converters only work from this
  layout. Saber's own option is to extract the Mod Tools into the game's `client_pc/root`.
- ModelConverter must run with its working folder set to `<toolchain>/client_pc/root/tools/bin/ModelConverter`
  (it reads its `config.json` there).
- Python 3 for our own glTF writer and patch scripts. Blender only for preview renders (back faces culled, see
  Gotchas). Plan on 60+ GB of free RAM plus page file for a big bake, and a free disk for `%TEMP%`.
- Some building and vegetation meshes in our level were imported from other games the author owns. That route has its
  own cross-game porting note in this folder. This note sticks to the SM2 side: what the map pipeline, the scene
  files and the engine do with whatever meshes you feed in.

## Route and why
Data / asset route: a new scene built by Saber's own offline tools, shipped as loose scene files plus tpls in a mod
pak, and registered as a mission.
- **Not** editing a retail level: scenes can't be decompiled back to editable sources, and rebuilding a retail level
  through the converters means hundreds of thousands of instances and heavy native terrain (see the missions note).
- **Not** native SM2 terrain: retail open levels use a `terrain/` folder (`terrain.terrain`, 50-230 MB, material,
  colour, height and grass masks; roads as spline decal overlays). Its source format is editor-only. We used
  ordinary static meshes for the ground instead (tiles with layered materials, below).
- Hub edits are different: they are in-place binary edits of the retail hub scene's files (`.lwi_container`,
  `.dom_list`, `.lg_data`, class `tpl_markup`), because the hub can't be rebuilt either.

## How the game works (what we had to learn)

### The pipeline in one paragraph
Your glTF goes to `ModelConverter.exe --map_mode`. Every mesh node becomes its own tpl through UsfExporter
(`convert_tpl.py`, which also runs CDTConverterExe for collision), and the converter writes a text scene (an xscene)
under `mods_source/xscenes/<map>/`. Then `furnace.exe scene` bakes the scene binaries into `local/scenes/<map>.scn/`.
That covers cd_list, class_list, dom_list, `.lg`/`.lg_data`, `.cdt`, `lwi_container`, terrain stub, navmesh through
AIConverterExe, light probes through LightProbeConverterExe, sound, and finally `resolve_scene_resources.exe`, which
writes the `.scn.resource` link lists. You pack `scenes/<map>.scn/**` (client and `server/`) plus the converted
`tpl/sg_<map>_*` folders and every texture they link.

### glTF conventions the converter reads (MapConverter.cs)
- Y-up, metres. Counter-clockwise triangles are the visible side, and map-mode materials are drawn single-sided.
- A node with a mesh and no `xType` becomes its own tpl named `sg_<map>_<node name>_<glTF node index>`, with
  collision. The name key is `name.split('.')[0]`, so node names must be dot-free and unique.
- Node extras the converter understands: `xType` = `directional_light`, `mist_init`, `cubemap_probe`, `lightgrid`,
  `skydome`, `domain`, `prefab`, `static_geometry`. There is **no point-light type**. Also `xTplName` (instance
  source), `xCollisionPreset` (`no_collision` writes a per-instance `disableCollisionMask` of `all_collision`),
  `xCollisionLayers` (it only writes a per-instance DISABLE mask, it can't add a layer), `xPrefab`, `xDesc` and `xTag`.
- A domain (trigger volume) is a cube node with its origin at the bottom centre, `xType domain`, plus an `xTag`.
- A scene needs the prefabs `navmesh_magnus`, `navmesh_seed` and a `three_players_start` node (`xDesc
  three_players_spawn_point`, `xTag spawn_point_start`) to be playable. Saber's sample lighting nodes (`mist_init`
  with presets, `skydome_sphere`) are the starting point for lighting. Copy those from the sample scene.
- Empty scenario files `<map>_scenario_server.sso` / `_client.sso` (`__type = "LevelScenarioServer"` /
  `"LevelScenarioClient"`) build fine and get embedded in the SCN.
- A mesh node whose name ends in `_cdt` (and `mesh_cube_cdt` blockout cubes) is exported as collision-only geometry:
  the `cdt_low_res_geometry` affix group, so hidden and blocking players, AI, vehicles and camera. One mesh node
  named like `river_walls_cdt` is the cheap way to build invisible walls along banks and map edges. Offline the
  converter output is correct; in game these map-mode walls are untested.
- Map mode chooses the submaterial through the USF material text (`usf_default_material.txt`, layer
  `subMaterial`), passed as mesh extras `materials`.
- `mode`, `transform {position, rotation in degrees, scale}` and `desc` of prefab children are written as you give
  them. `WritePrefab` emits `{desc {properties; __type = <xDesc>}; __type = <xPrefab>}`.

### Instancing and the lwi container
- **Any node can reuse a converted mesh** as an Empty with extras `{xType: static_geometry, xTplName:
  sg_<map>_<node>_<index>}`. That writes a lightweight instance (lwi) of that tpl with no new conversion. We placed
  25,000 grass tiles from 14 source tpls and ~1,400 trees this way. Instances of retail tpls work the same way: give
  the retail tpl name.
- `<scene>.lwi_container` (hub and map scenes alike): a type list (each entry `lwi_type_base` + u8 flag + u32 length
  + tpl name, 1-based) and then groups (u32 type, u32 0, u32 count, then count x 55-byte records: f32 position xyz,
  f32 3x3 rotation*scale rows, u32, `ff 01 01`). World = P @ R + pos. The flag byte is 1 when the tpl has a `.cdt`
  (collision actor) and 0 when it has none (retail grass). Client and server copies are identical.
- **Map-mode types are listed alphabetically by tpl name** (your `fs_*`-style external tpls first, then
  `sg_<map>_*`). See gotcha 4 for what happens past ~1024 types.
- **Instanced tpls exist twice.** `--install_lwi` writes every instanced source tpl to `local/tpl/` AND
  `mods_source/tpl/`, and Furnace reads the `mods_source/tpl/` copy for instances. Anything you patch into a tpl
  between ModelConverter and Furnace (markup, `.cdt` removal, `.lods_base` flags) must go into both copies.
  Furnace resolves `xTplName` tpls only from `mods_source/tpl/` or the retail paks, never from `local/tpl/`.
- **Yaw past 90 degrees is mirrored by the bake.** ModelConverter writes a node yaw t with |t| > 90 as Euler
  (180, 180 - t, 180), and Furnace rebuilds that as a rotation of -t. We measured all 26,547 lwi records of one bake
  against their glTF nodes: every node between 91 and 179 degrees came out mirrored, |t| <= 90 was exact, and a
  float-exact +-90 was right (-90.04 was not). The likely explanation is a converter Euler order with Y in the middle
  while Furnace puts Y outermost. Under that explanation tilted nodes would be wrong even under 90 degrees; we never
  measured tilt + yaw.

### tpl_markup for map tpls (draw distance, shadows, navmesh)
A map tpl has no `tpl_markup` by default. We wrote one per tpl between ModelConverter and Furnace (`<tpl>.tpl_markup`
+ its `.resource`, linked from `tpl.resource` `linkTplMarkup` / `tplMarkup`), copied in shape from a retail text
markup such as `refrt_moss_grass_01`:
- `lodInfo {hideDistance, disableSMshadows, densityLodDistance [..]}`: draw distance and density fade, the fix for
  grass that pops in.
- `giParams` exclude, and `navMeshParams {enableNavMesh = false}` so plants and clutter don't feed the navmesh. With it,
  the AIConverter log for a grass test listed 27 solid objects instead of 427.
- We left out `rendParams`, `windParams` and `enableLwiLodTransition`. They are likely to need shader-cache
  permutations the game doesn't have (see the models note's shader-cache rule).
- **Walkable things keep their navmesh.** Turning navmesh off on every tpl with markup took it off bridge decks and
  an interior. Only plants, clutter and other non-walkable decoration get `enableNavMesh = false`.

### Collision
- Movement collision is the `.cdt` system, not Havok (models note). In a map scene, every converted mesh gets a
  `.cdt` unless you remove it. For plants, delete the tpl's `.cdt` and blank `cdt:` in its `tpl.resource`. The
  `no_collision` preset alone leaves the lwi type flagged as a collision actor.
- The player marine's movement capsule (`pc_marine_base_authority.cls`, `prop_character_rigid_body_with_fsm`):
  radius 0.75, standing height 2.7, `maxStepHeight` 0.5 (0.61 absolute), `maxSupportSlope` 60 degrees (54 on moving
  or keyframed bodies). Foot IK is off on keyframed surfaces. The Hive Tyrant: radius 2, height 6, step 1. Haloed
  backpacks reach 3.3 m, so interiors meant for marines need ~3.35 m of clearance, and doorways should be comfortably wider than the
  1.5 m capsule (we used 2.4 m). Size
  every walkable or blocking surface by these numbers before blaming a "wall".
- Furniture and other complex interiors: give them one hidden `*_cdt` box mesh rather than per-prop collision.
- Trees: a hidden bark-core collision cylinder inside each trunk, not the render mesh.
- **Hub collision is different:** in the hub, players walked straight through a hangar model's `.cdt` hit mesh but
  were stopped by its keyframed physics boxes (`tpl_markup` group `glr`, `prop_phys_system` Keyframed on the actor).
  Build hub walkable or blocking geometry as analytic `tpl_markup_shape_box` entities (full extents W/H/D along the
  owner's local axes, centred at `localTransform.position`; keep them axis-aligned). Convex `*_glr` shape meshes on a
  custom tpl crashed the level load (models note).
- A physics box that hangs lower than the visible model reads as an invisible wall. Build boxes from the visible
  underside, in small cells if the shape is curved.

### Materials and ground
- Map-mode tpls get FVF `47000b1c02420020000000` with submaterial `default`. A texture set only renders safely if a
  retail td family ships that exact (FVF, record shape) pair. `rock_06` (stone) and `imp_worned_wood_a` (wood) do;
  `imp_stone_01` does not. Clone those td families under new names and swap in your textures. UsfExport links
  `res://td|pct/<material name>` and Furnace resolves them from `mods_source/{td,pct}`, so converted textures must
  be copied there before the bake.
- In game, every such material is **opaque and single-sided**. Glass alpha is lost (a "glass" texture shows its dark
  diffuse), and any pane or wall piece that faces the wrong way is culled into a see-through hole. Panes must face the
  street or be duplicated with reversed winding.
- **Soft ground blending without native terrain:** the tpl material record has `layer0..layer3`, each with `texName`,
  `blending {useLayerAlpha, useHeightmap, heightmapSoftness, weights.colorSetIdx (which vertex-colour channel),
  upVector {enabled, angle, falloff}}`, tiling and `uvSetIdx`. glTF can't carry layers, so we patched the records into
  the built tpls. Each one is an exact copy of a retail layered combo (FVF with vertex colour, record shape, td family),
  with our textures in the layers: grass base, mud, cobble and dirt, chosen by vertex colour. It rendered in game. Before
  that, terrain triangles clipped along smooth noisy curves gave clean edges with no blend shader.
- Retail `ModelConverter` (tpl -> glTF) writes no meshes for joint-animated cloth flags and banners (joints and clips
  only, no error); decode those meshes from the tpl yourself. Retail scenes link such `__actor` flags under `linksTpl`
  (as actors), not `linksTplStatic`.

### Sky and moon
- The visible sky and the sky lighting come from a `new_sky` preset (`presets/data/<dir>/<name>.s3dprs`, linked from
  `scn.resource` `linksPreset`; its own `.resource` lists `linksPct`; retail resources use CRLF). Fields:
  `baseParams {textureName, tintColor, intensity, turnAngle, skyVisibleVertAngle}` drive LIGHTING.
  `cameraOverrides` (same fields plus enable) control what the camera SEES. Retail night skies use a separate camera
  texture. `sunDisc` is a plain white circle; zero its disc and flare intensities for a moon you paint yourself.
- Your own preset folder (e.g. `presets/data/<mymap>/`) works: Furnace resolves it from `mods_source`.
- **Remove the converter's `skydome` node.** It places a `skydome_sphere` actor with a retail daylight sky texture,
  which hid our preset through six builds. 38 of 40 retail levels draw the visible sky from `new_sky` instead.
- Skydome mapping (decoded from `skydome_sphere.tpl`): u = azimuth/360 with azimuth = atan2(z, x) (0 at +X, 0.25 at
  +Z, 0.75 at -Z), v = 0.5 - elevation/180 (equirect, `skyVisibleVertAngle` 180).
- Sky texture: BC6H UF16 = pct format 49, one mip, not streamed; the largest retail one is 8192x4096 (~33.5 MB). To make
  one, clone a retail sky td and run `convert_pct.py` on a `.hdr` named exactly like the texture (the converter takes
  the texture name from the file name). To read a retail sky as float, wrap the mip in a DX10 DDS header (DXGI 95)
  and load it in Blender (OIIO decodes BC6H to float). `texture2ddecoder` only gives clamped 8-bit.
- **Auto-exposure fights a dim sky.** Dimming the whole sky (intensity) made the scene dark, but the auto-exposure
  opened up and the visible sky came back as a grey overcast day (seen in game, twice). The approach that matches
  retail: keep the lighting texture in `baseParams` and give `cameraOverrides.textureName` a darker night texture
  with the moon painted in. Our in-game result for that version was not recorded.

### Lighting and shadows
- **The directional light gets prefab defaults.** The converter writes only a transform (Euler from the glTF
  quaternion), so the sun uses `ssl/prefabs/directional_light.prefab` (`editor_prefabs.pak`): warm colour, **intensity
  150**, default rotation [90,0,0]. Retail daylight suns are 9-12, so an untouched map-mode scene is 10-15x over-lit
  and night reads as day. Confirmed in game.
- **The light travels along node-local +Z** (the default [90,0,0] points straight down). Use a rotation about X alone
  to avoid Euler-order doubt: Rx(a) lights the scene FROM azimuth 270 (the -Z side) at elevation a. Confirmed in game.
- Colour and strength: inject `desc.properties.sfx.list.light {ColorCtrl [A,R,G,B], Intensity, __type sfx_light}` into
  the xscene's lighting node between ModelConverter and Furnace. It compiles to the same override shape retail
  cd_lists carry (checked in the baked cd_list). Retail cd_list descriptors are readable text, so compare against
  `story_tower` (main light 9) and similar.
- **Sun shadows end at 75 m** in map mode: the prefab's `SMParams` are split0 25 / pssmDist 75 with
  `dirLightBoundSize` 100. Retail outdoor suns override them to pssmDist 220-500, splits ~20/70, 3 splits. Add
  `SMParams` to the same injected override. Research only, not tested.
- **Not producible with the public tools:** a real `light_probe_grid` (Saber's own sample scene ships the 161-byte
  stub), `pssm_data` (every sun level has one), cubemaps (`WriteCubemapProbe` / `WriteLightgrid` are commented out in
  MapConverter.cs; Saber's guide says those nodes have no effect). A hand-made global cubemap might bind by name: an
  `lc/<x>.resource` name equals the probe actor path with `|` replaced by `_`. Untested.
- Post-FX presets: borrowing a retail level's preset set (dof left out: a depth-of-field preset blurs everything
  past a few metres) worked. A preset name inside the baked cd_list can be swapped after Furnace by a same-length
  rename (`pve_dread\\X_pve_dread` -> `<dir>\\X_<name>` of the same length). One night preset set we borrowed had
  the game's weakest ambient occlusion (empty `ao_shadowing`, SSAO gamma 1.5, hdr `ExposureScaleX` 100), which
  flattens a night scene.
- Card grass from another engine keeps sideways card normals: 43 % of its vertices were unlit under a 28-degree moon.
  Point grass normals up.

### Lamps, fires and other effects via prefabs
- There is no point-light node, so lights go in as **custom prefab children**. Put the prefab in
  `mods_source/ssl/prefabs/**/<name>.prefab` (`childs = {x = {mode; desc = {properties; __type = "actor"}; __type =
  "game_object"}}; __type = "game_object_base"`) and place it with a node `xType prefab`, `xPrefab <name>`. Furnace
  expands it into the baked class_list at compile time; the prefab file itself is not shipped.
- Light child: `desc.properties.sfx.list.light {lightType "point", RadiusCtrl, ColorCtrl, Intensity, __type
  "sfx_light"}` with `__onlyOn "visual"` in an `sfx_entity`, the same shape as `ssl/prefabs/light.prefab` (defaults
  radius 50, intensity 5000). Retail night lamps: intensity 0.5-5, radius 8-30, warm [255,255,196,119]. Retail fires
  flicker with `anim_noise_ctrl` on Intensity and RadiusCtrl, and lamp shadows are mostly cached.
- Fire child: an sfx list entry `part_mg_fire_near_01 {isAutoStart true, scale s}` with its smoke / perlin / ashes /
  vortex emitters set invisible, which is how retail builds its small fires.
- Retail level effects in general are `sfx_entity` actors. For a fountain, the looping
  `part_mag_lvl_story_tower_fountain_start` spray plus the 2 s splash effect worked as prefab children.
- In game the flames and fountain effects did appear (autostart works), but our placement and scale were off (flames
  outside their lanterns, effects far too big). Light strength under our exposure was never judged on its own.

### Water
- **Mesh water works:** a clone of the retail moving-water td `water_stream_02` (submaterials `solid1/solid2`: UV
  scroll, background distortion, dynamic alpha mask, vertex pulsation) on a river ribbon or pool mesh. Keep the keys
  and retune the numbers. Its unused `green` submaterial names a normal map that doesn't exist; rename that
  reference or your texture tooling may choke on it.
- **Native water (`prop_water` / PropWater) crashed the client at level init** in native `PropFluid.Reinit`
  (null read), called from `PropFluid.OnInitLevel`. We had put it on our own rendered water-plane tpl. Retail water
  geometry is different: a scene-local, collision-only tpl (no tpl_data, material `gmtl_editor`, `.lods_base`
  collision flags all false except `water = true`) with class `geom {isAlwaysCastSM = true; collisionLayers [21]}`.
  Terrain is not required (several retail water levels have none). The likely recipe: a `*_cdt` mesh node, then patch
  its `.lods_base` to the retail flag block between ModelConverter and Furnace, then give the `prop_water` actor that
  tpl at the same transform. This passed an offline diff against the retail fountain; it is **untested in game**.
  Mod Tools hints: `meta_desc.ps` (`prop_fluid` / `prop_water`) and `UsfExport/descs/affixes_mtl_water.desc`.
- Removing a crashing prefab child without a rebake: Furnace bakes prefab children into the class_list as
  u32-length-prefixed TEXT entries (`properties = {...};__type = "actor";`). Overwrite one with `properties = {`,
  spaces, `};__type = "actor";` at the same length.

### Living things in a custom level
- **Ambient animals without AI (verified in game: renders and animates):** a plain `actor` class with `geom.nameTpl`
  and `prop_animation_controller.controller.animations = [{animation = {name = "<sani path>"; __type =
  "AnimationInfo"}; playingRandomRange = [0,1]}]` loops one skeletal `.sani` with no Morpheme network. This is the
  same pattern as the hub's idle marine dolls. Clips bind to tpl bones by channel NAME, and channel 0
  `CharacterWorldSpaceTM` is identity in retail clips. The tpl_markup needs `objectInfos` animation roles (Trajectory
  = RIG_TRAJECTORY, CENTRE = RIG_CHARACTER_ROOT, animated bones RIG_INCLUDE). Keep CENTRE static and animate a child.
  Place it with a custom prefab node. A `sound_actor_full` child can loop a sound bank event. We had to append the
  animal's tpl to `scn.resource` `linksTpl` after Furnace.
- Level sequences autostart with `level_sequence_actor_client {desc = {type = {__type = "<xseq brand>"}; __type =
  "LevelSequenceDesc"}; isAutostart = true}`. They loop through markers or sections, not a flag.
- **Friendly human NPCs (planned, not built):** the host is the retail friendly `npc_guardsman_server/client`
  (GuardsmanBehavior squad AI, `cadian_trooper` animation set) on the modular `cc_cadian_shock_trooper` constructor
  over the SM2 human rig. Reskins are constructor parts re-weighted to that rig. Keep humans at 1.0x next to 2.6 m
  marines. New NPC classes in general: see the NPC note.

### Hub scene edits (in place)
- **Hub floors, pads, railings and crates are lightweight instances** in `<scene>.lwi_container`, not cd_list entities
  and not `.lg`. Hide one by setting its y to -100 (same file size). One mod copy covers client and server.
- Prefab props are flattened into separate world-placed entries (`<prop>__<part>__static_geom`). Sinking the prop
  alone leaves its parts floating, so sink every `<prop>__*` entry. A naive cd_list scan can miss two thirds of the
  entries: scan for every `{name = "|x|..";matr = [16]` record.
- **Trigger zones live in `<scene>.dom_list`**, baked in WORLD coordinates. After the 64-byte `1SER` header: u32 n,
  u32 9, u8 1, n x (i32 length + name); u8 1, per domain a u32 triangle count + triangles of (f32 x, f32 z); u8 1,
  f32 ybase[n]; u8 1, f32 height[n] (0 = unlimited); u8 1, 6 x f32 bbox[n]; a tail of flag bytes kept verbatim. The
  cd_list domain entities have unit matrices, so moving them does not move the zone; edit the triangles. Triangle
  counts can grow freely. Our reader/writer round-trips the hub files byte-exactly. A reshaped hub ready zone (the
  client `DomainBasedReadyStatusSetter` counts players inside the domain tagged `trigger_loading_new_level`) worked in
  game.
- Prefab parts are placed in their cd_list ENTITY frame, not their bone's rest frame: part world = bone_world @
  inv(bone_rest) @ entity_matr. A mirrored bone rest put a part we built 7-10 m under the floor.
- Scene static collision (`.cdt` MOPP over `.lg`) and invisible-wall removal: see the models note.

## Build steps
1. Build the toolchain root (Setup). Keep the list of what it came from (Mod Tools `ModEditor`, the game's
   `resources.pak` and `tools/meta_descs`, your own converted assets). Treat it as infrastructure (gotcha 16).
2. Write the glTF: Y-up metres, lower-case dot-free unique node names, every `sg_<map>_<node>_<index>` name <= 53
   characters, no yaw beyond +-90 (bake a 180-degree turned copy of the mesh instead: (x,y,z) -> (-x,y,-z) on
   positions, normals and tangents, and use yaw -+ 180), CCW faces outward, the required prefabs and start node, no
   `skydome` node. Instances as `static_geometry` + `xTplName`.
3. **Verify the assembled glTF before baking** (gotcha 15): renders from player eye height with back faces culled,
   plus automated checks (winding vs normals, hole and see-through rays, deck-to-bank gaps, grass vertices inside other
   meshes, longest tpl name, yaw report, lwi type count < ~1000, shader pair check of every new material against retail).
4. Convert textures (TextureConverter / `convert_pct.py`, absolute paths) into `mods_source/{td,pct}`. Put prefabs in
   `mods_source/ssl/prefabs/`, presets in `mods_source/presets/data/<dir>/`, external instance tpls in
   `mods_source/tpl/`.
5. ModelConverter, from its own folder: `ModelConverter.exe --map_mode "<root>/mods_source/xscenes/<map>/source/<map>.gltf"
   "<root>/mods_source/xscenes/<map>" "<root>" "<Mod Tools>/ModelConverter/UsfExporter" python --install_lwi`. Use
   the race workaround (gotcha 6) on large maps.
6. Patch between the two tools: tpl_markup + `.cdt` removal into BOTH tpl copies, the light override (colour,
   intensity, `SMParams`) into the xscene lighting node, layered ground material records, water `.lods_base` flags.
   Then check that every instanced tpl's `mods_source` copy has its markup.
7. Furnace with `TEMP`/`TMP` pointed at a roomy drive: `tools/bin/ResourceTools/furnace/furnace.exe scene
   "-p<root>/.project" "-s<map>.scn" "-d<root>/local/scenes/<map>.scn"`. Watch for hidden CRASH windows every minute
   (gotcha 7).
8. After Furnace: same-length preset renames if any, append missing `scn.resource` links, and check that every
   `res://` link resolves against an index of retail paks plus your pak.
9. Pack ZIP_STORED: `scenes/<map>.scn/**` and `server/` from `local/scenes` (skip `intermediate/`, `*.xls`,
   `export_options.ps`, `geom_dbg_schema`), `tpl/sg_<map>_*.tpl/{tpl,tpl.resource,tpl_data,lods_base,geom_dbg,cdt}`
   (+ markup), and every td/pct the tpls link (closed over `td.resource` links).
10. Register the mission: `levelUid` = the scene folder name. Merge into whichever installed pak owns
    `missions_consts.ext` / `missions_library.sso` / `ui_missions_library.sso` (the first alphabetically) and make
    yours sort first (missions note).

## Verification
- **In game (verified):** small test scenes and the full 800 m grey box load and are walkable (first loads are long).
  Layered ground materials, instanced imported houses and trees, card grass (badly at first: wrong UVs and pop-in),
  the ambient animal loop, prefab fire and fountain effects all appeared. The directional light's default intensity and +Z travel were
  confirmed. The native-water crash happened in game. The lwi missing-floor pattern (gotcha 4) was seen in game.
  Hub: physics boxes as walls, lwi hiding and a reshaped dom_list ready zone all behaved in game.
- **Offline only:** the yaw mirror (bake output measured against the glTF; the fix checked to 6e-14 m over 26,977
  nodes), the 53-character and capital-letter failures, the two tpl copies, the navmesh effect of markup (AIConverter
  logs), the water tpl diff against retail, the skydome UV mapping.
- **Not verified in game:** `*_cdt` invisible walls in a map scene, the dark camera-sky fix, `SMParams` shadow
  distance, cubemap binding, the native-water recipe, light strength of our lamps, tilted (non-yaw) nodes, the
  under-1000-types fix for the lwi limit, friendly NPCs (not built).

## Gotchas
1. **Furnace dies within 5 seconds with "Failed to extract libcrypto-1_1.dll".** **Cause:** `furnace.exe` is a
   PyInstaller bundle that unpacks into `%TEMP%`, and the system drive was full. **Fix:** set `TEMP`/`TMP` to a
   folder on a roomy drive for the Furnace process.
2. **Furnace runs for 30 minutes, then its last step fails: "can't find tpl file for sg_<map>_..."** and no
   `.scn.resource` is written. **Cause:** capital letters in glTF node names (and so in tpl names); the tpl existed.
   Domain names with capitals are fine. **Fix:** lower-case node names and `xTplName`. On Windows, writing a
   lower-case name over an existing folder keeps the old capitals, so move stale `sg_<map>_*` folders (both tpl
   copies) and `source/usf` files out first. Rescue without a rebake: byte-patch the names to lower case (same length)
   in `lwi_container`, `lwi_container_data`, `.nav` and the intermediates. Then run `resolve_scene_resources.exe
   --project <root> <root>/local/scenes/<map>.scn` alone (~12 s; it writes only `intermediate/.resolver_output`) and
   rebuild both `.scn.resource` files from a previous Furnace-written copy with the new link lists.
3. **ModelConverter dies (exit -1) partway through, UsfExport crash report "security check error in '_s' function".**
   **Cause:** a tpl name of 54+ characters overflows a `strcpy_s` in UsfExport. **Fix:** keep `sg_<map>_<node>_<index>`
   at 53 characters or fewer (shorten generated variant names). Remove the crashed name's stale `.usf` before rerunning.
4. **About 40 % of the map is missing in game: no floor, terrain tiles, streets and two buildings gone, far scenery
   floating.** **Cause (strong hypothesis):** the build had 1,257 lwi types. Every missing object was a
   single-instance type sorted at index >= 1024 in the alphabetical type list. Multi-instance types past 1024 still
   drew, and a 166-type build rendered fine. Retail levels with thousands of types keep unique architecture in the
   scene `.lg`, not lwi. Ruled out first: files, links, textures, winding, holes, conversion and lwi records.
   **Fix:** merge one-off pieces (e.g. backdrop tiles into 4x4 blocks with one primitive per material) and keep the
   type count (mesh nodes + external `xTplName` types) under ~1000. If something still vanishes, rename the big one-off
   pieces so they sort first. The fix is not yet confirmed in game.
5. **Houses, lanterns and bridges face the wrong way in the bake, but the glTF renders are right.** **Cause:** the
   yaw mirror past +-90 degrees (above). **Fix:** never write |yaw| > 90; for your own meshes bake a 180-degree turned
   copy. Instances of OUTSIDE tpls (retail tpls, prefabs, LOD trees) can't be turned that way and must stay within
   +-90. Test tilted markers in a bake before using any.
6. **ModelConverter `--map_mode` dies at random (exit 0xE0434352, ObjectDisposedException in
   `AsyncStreamReader.FlushMessageQueue`).** **Cause:** a race in `MapConverter.StartProcess` (shipped source). For each
   tpl it spawns `python convert_tpl.py`, waits only for process exit, then disposes the wait handle that the stdout-EOF
   callback still signals. **Fix:** from outside, with no Mod Tools file changed: a `sitecustomize.py` on
   `PYTHONPATH` for the converter's children that, at exit, flushes and redirects stdout/stderr to NUL and sleeps
   0.25 s, so EOF arrives before the parent moves on. Adds ~5 minutes to a 1,250-tpl run. Forcing thread-pool minimums
   only made it rarer.
7. **A bake "hangs": log frozen (e.g. at "Couldn't init lwi mutations: terrain not found"), a converter alive at
   ~0 % CPU, no dump.** **Cause:** a Saber tool asserted and is waiting on an INVISIBLE window titled `CRASH`.
   **Fix:** enumerate top-level windows titled CRASH (hidden ones too) and read the text of their edit controls
   (project, message, file, line, call stack). Check every minute during long bakes. A bake whose parent shell went
   away also stalls; kill it and rerun from the Furnace step.
8. **CRASH dialog "Error loading tpl descriptor <name>.tpl" during Furnace.** **Cause:** an external tpl used through
   `xTplName` was only in `local/tpl/`. **Fix:** put it in `mods_source/tpl/`.
9. **AIConverterExe "No memory left!" at 63 GB commit, an hour into the bake; grass blocks the player; grass never
   fades.** **Cause:** the markup and `.cdt` removal were patched only into `local/tpl/`, but Furnace read the
   `mods_source/tpl/` copies, so 44,000 grass and prop instances fed the navmesh with collision and no draw distance.
   **Fix:** patch both copies; count instances whose `mods_source` copy lacks markup before every bake.
10. **The map-mode scene looks like a bright day at "night", and the light comes from the wrong side.** **Cause:** the
    directional light keeps the prefab's intensity 150, and its axis is node-local +Z. **Fix:** inject colour and
    intensity into the lighting node (retail 9-12 for day, a few units for moonlight) and aim with a pure X rotation.
11. **Your sky preset never shows; a daylight sky is drawn instead.** **Cause:** the converter's `skydome` node.
    **Fix:** delete it and let `new_sky` draw the sky.
12. **The light-probe step spins at 100 % of one core for 15+ minutes and never ends.** **Cause:** a custom hdr preset
    with `AdaptationMinLum` raised (0.5). The retail hdr preset takes ~6 s. **Fix:** bake with a retail hdr preset, then
    swap the name in the baked cd_list by a same-length rename if you need your own.
13. **Client crash at level init in `PropFluid.Reinit`.** **Cause:** a `prop_water` actor on a rendered water plane
    instead of a collision-only water-layer tpl. **Fix:** use mesh water, or the retail-shaped recipe above (untested);
    remove a crashing actor by blanking its class_list text entry at the same length.
14. **Window glass and some walls are see-through in game though the Blender preview looks closed.** **Cause:** SM2
    draws these materials opaque and single-sided, so a pane facing inward is culled from the street; the source
    material's alpha and fake interiors only exist in the preview. **Fix:** preview in a "game look" (diffuse +
    normal, opaque, back faces culled, dropped materials deleted). Ray-test openings from the street, and flip or
    duplicate the panes.
15. **The first playable build is "a mess": bridges don't meet banks, houses miss doors, wall gaps, flames outside
    lanterns, huge effects, a leftover placeholder box.** **Cause:** only kits and plans were previewed; the final
    assembled glTF was never checked before a 30-minute bake. **Fix:** render the final glTF at every requested
    feature from eye height and run the automated checks (Build step 3) before baking. A bake plus a long first load
    is the most expensive test you have.
16. **Every map build and other converter jobs suddenly fail; the toolchain folder is gone.** **Cause:** a disk
    cleanup treated the 23 GB toolchain mirror (converters, `mods_source`, `local`, junctions) as junk, and it was
    deleted. **Fix:** treat the toolchain root as infrastructure. Exclude it from cleanup, keep it out of backups of
    "temp" data, and keep a written list of rebuild sources: Mod Tools `ModEditor`, the game's `resources.pak` and
    `tools/meta_descs`, and your converted assets, which can be extracted again from your own last built pak.
17. **Grass pops in near the player and looks like a repeating lattice.** **Cause:** no markup (default distances) and
    a 4 m grid of two tile layouts. **Fix:** markup `hideDistance` (90-150 m) and `densityLodDistance` (e.g. [60,100,130]),
    and varied tiles: habitat mixes, round patches, yaw-only random rotation, slope variants. Keep grass vertices out of
    roads and floors with a keep-off distance.
18. **A street or floor face is invisible from above.** **Cause:** the layout -> glTF transform used for one generator
    reversed its winding; a rotation (det +1) must keep the source winding. **Fix:** check triangle winding against
    vertex normals for every generated mesh.
19. **Bridge decks or an interior lose navmesh (enemies won't path there).** **Cause:** `enableNavMesh = false` in
    markup applied to every tpl that got markup. **Fix:** only plants and decoration get it; solid walkable tpls keep
    navmesh (or get no markup).
20. **A custom level pak makes another mod's mission vanish.** **Cause:** your pak now owns the shared mission files
    (first alphabetically) and a rebuild started from an older copy that lacked the other mod's entry. **Fix:** merge
    from the CURRENT winner each time and diff the mission ids against the previous build before installing.
21. **Hub players walk through a model's collision mesh but hit an invisible wall nearby.** **Cause:** the hub uses the
    model's keyframed physics boxes, and one box was bigger or lower than the visible model. **Fix:** build hub
    collision as markup boxes sized from the visible surface. Before editing, list every collision source that reaches
    the exact spot (scene `.cdt`, prefab collision models, physics boxes, scripted blockers).

## Assets
- Buildings, props, vegetation, ground textures, animal and moon source art were imported from other games the author
  owns, for personal use only and never distributed. The porting route is in the separate cross-game porting note in
  this folder. SM2-side, every texture set was a renamed clone of a shader-safe retail td family.
- The sky: a retail night sky scaled down, with a moon rendered as a lit sphere and painted behind the clouds
  (additive light; the unlit side stays invisible), saved as linear HDR and converted to BC6H.
- The level is personal use and not uploaded. Saber's mod rules also forbid AI-generated content in uploaded mods (see
  the foundations note).

## Cost and time
- Two weeks of sessions (Oct 16-29, 2026) for the level, plus earlier hub work.
- Bake times: a 300 m test map ~3.5 min; the 800 m grey box ~21 min (13 min navmesh); a full town build ~30 min of
  Furnace and ~29 min of ModelConverter for ~1,250 tpls. Furnace's "Process Lwi" took 37 s for 400 grass instances.
- Pak sizes grew from 0.2 GB (one test house) to 2.6 GB (~12,000 files) for the full town level.

## Open questions
- Confirm the single-instance lwi limit (and whether renaming one-offs to sort first is enough).
- Do map-mode `*_cdt` invisible walls block players in game? Does tilt + yaw also mirror in the bake?
- Native water through the collision-only water-layer tpl, and whether `useTerrain = false` presets behave without
  terrain.
- Longer sun shadows through `SMParams`; a hand-made global cubemap binding by actor name.
- Placing retail cloth flag actors (`__actor` tpls) in a custom map.
- Friendly guardsman-based NPCs and enemy spawning in the custom level (the ESD needs spawn points baked into the
  navmesh; see the missions note).
