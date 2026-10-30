---
kind: game
title: "Porting owned content from other games into Space Marine 2 (personal use): Witcher 3 level kit, Space Marine 1 Orks, Gears of War E-Day, Elden Ring, Helldivers 2"
game: "Warhammer 40,000: Space Marine 2"
games_also: ["The Witcher 3", "Elden Ring", "Gears of War: E-Day", "Warhammer 40,000: Space Marine - Master Crafted Edition", "Helldivers 2", "Red Dead Redemption 2"]
game_version: "SM2 Steam build 25799387 (Patch 15.1, Oct 2026), most work on Patch 14.x-15; Saber Mod Tools (Oct 2026: ModelConverter, UsfExporter, Map Converter + Furnace, TextureConverter). Sources: The Witcher 3 Remastered 5.01 (GOG), Space Marine Master Crafted Edition (Steam), Gears of War: E-Day (UE 5.5 IoStore build), Elden Ring + Shadow of the Erdtree (Steam), Helldivers 2 (Steam, Stingray)"
platform: windows
engine: unknown
route: asset-only
tools: ["Saber SM2 Mod Tools (ModelConverter --map_mode, UsfExporter, Furnace, TextureConverter)", "Blender (headless, isolated user profile)", "Witcher3-Blender-Tools (dingdio) Blender add-on", "own SpeedTree 7 .srt parser (Python)", "filediver v0.7.58 (Helldivers 2 extractor)", "own UE 5.5 IoStore + ACL v2.1 readers (Python)", "own Havok 2010.2 packfile reader (Python)", "Wwise 2019.2.15 WwiseConsole", "ffmpeg", "Python 3 (numpy, scipy)"]
anti_cheat: "SM2 has EasyAntiCheat: every build here loads through Saber's official mods folder (Mods Detected, private lobbies), no injection. Source games with anti-cheat (Elden Ring EAC, Gears E-Day EAC, Helldivers 2 GameGuard) were never launched or patched for this work; their files were read offline from the author's own installs."
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-29
links: []
tags: [space-marine-2, cross-game, port, asset-conversion, mashup, witcher-3, redengine, speedtree, map-converter, furnace, lwi, elden-ring, gears-of-war, unreal-5, iostore, acl, space-marine-1, havok, helldivers-2, stingray, wwise, opus, retarget, personal-use]
---

# Porting owned content from other games into Space Marine 2 (personal use)

> About two weeks of moving content from other games the author owns into Space Marine 2 (SM2): Witcher 3 buildings,
> wall and town kits, trees, grass, animals and their sounds for a custom 800 m level; the Space Marine 1 Ork Boy as a
> new SM2 enemy; Gears of War: E-Day sounds, a reticle, animation decoding and a Siege-mode slice; Elden Ring
> animation-donor research and a cape port; a Helldivers 2 flyer and pump-shotgun research. Route: offline asset
> conversion (see `techniques/choosing-a-mashup-route.md`): source files are read from the owned install, converted to
> glTF/WAV/clip data, and rebuilt with Saber's own tools into a mod pak. **All of it was for personal use, in private
> lobbies; no assets are redistributed, and none of these paks goes to the Workshop.** Each claim below is labelled as
> seen in game, built but untested, or rejected.

## Setup
- **Ownership and rules.** Every source game is a store copy the author bought. Read source files offline; never
  launch, patch or inject a source game that has anti-cheat. CD PROJEKT RED's fan-content terms do not allow putting
  their assets in other games, FromSoftware, Arrowhead/Sony, Microsoft and Rockstar own theirs, and Saber's mod rules
  only accept Warhammer 40,000 IP on the Workshop. So: personal-use paks only, and this note describes methods, not
  files. It does not cover opening encrypted archives; where a source's archives are encrypted, use its community's
  established unpacker on your own copy, or skip that game.
- SM2 Steam build 25799387 (Patch 15.1). SM2 side basics (pak layout, ZIP_STORED, load order, crash triage) are in
  [the foundations note](sm2-modding-foundations-paks-tools-and-crash-triage.md); the `.tpl` format, the converter
  round trip and the shader-cache crash are in [the models note](sm2-models-tpl-format-modelconverter-and-textures.md).
  This note only adds what is specific to bringing content in from elsewhere.
- **The Witcher 3:** Remastered 5.01 (GOG). The dingdio Witcher3-Blender-Tools add-on (v1.1.0) reads meshes, materials,
  rigs, animations, world layers, foliage and the sound cache straight from the game's bundles. Run it headless from an
  **isolated Blender profile** (`BLENDER_USER_RESOURCES` pointing at a project folder) so it never touches the main
  Blender install, and set its game path and uncook folder in the add-on preferences from your script.
- **Space Marine 1:** Master Crafted Edition from Steam. Animations are standard Havok 2010.2 x64 packfiles (the same
  generation Skyrim Special Edition uses); meshes are Relic `.dcm`.
- **Gears of War: E-Day:** UE 5.5 IoStore containers (utoc v8), not encrypted, compressed with Oodle **Mermaid**.
- **Helldivers 2:** Stingray bundles, extracted with filediver v0.7.58 (CLI; animations behind a flag).
- **Elden Ring:** the archives are packed; this note only records what was learned from the animation and cape data.
- Wwise 2019.2.15 Authoring (WwiseConsole) for SM2 sound banks; ffmpeg for decoding.

## Route and why
Offline asset conversion into SM2's own formats. Nothing runs the source game. Considered and not used:
- **Importing a whole source level.** Too heavy (SM2's converter has no terrain, and a Witcher 3 city is hundreds of
  thousands of placements), and the goal was an own map. Instead, kits (buildings, walls, props, trees) are placed by
  our own layout generator and baked with Saber's Map Converter.
- **Saber's runtime retarget node** for donor animations: per-frame and expensive; clips were converted offline instead.
- **Hand-drawn replacements** for emblems or props: rejected in favour of the real mesh and texture from a game asset.

## How the game works (what we had to learn)

### SM2 side of a custom level built from imported kits
- Pipeline (Saber's MapBuilder steps): ModelConverter `--map_mode <map>.gltf ... --install_lwi`, then
  `furnace.exe scene` on a project layout (`.project`, `mods_source/`, `local/`). The glTF is Y-up, metres. A mesh node
  without `xType` becomes its own tpl `sg_<map>_<node>_<node index>` with collision.
- **Instancing:** any other node can reuse that tpl as an empty with extras `xType: static_geometry` and
  `xTplName: <tpl name>`, written as an lwi instance with no new conversion. Keep instances yaw-only (see gotchas).
  `xCollisionPreset: no_collision` writes a per-instance collision mask; for grass also delete the tpl's `.cdt`,
  because the lwi type stays flagged as a collision actor while a `.cdt` exists.
- **Map-mode tpls have no LODs and no markup**, so their hide distance defaults to 20 km and every instance feeds the
  navmesh. Inject a small `tpl_markup` per tpl between ModelConverter and Furnace: `lodInfo` (hideDistance,
  densityLodDistance) and `navMeshParams.enableNavMesh = False` for plants. Leave render, wind and LOD-transition params
  out: they can create shader permutations the prebuilt cache lacks.
- **Materials:** every map-mode tpl gets one FVF and the submaterial `default`. The shader cache only holds the
  (FVF, material shape) pairs retail ships (see the models note), so imported textures go into **renamed clones of
  retail `.td` families that already pair with the map FVF**: a stone rock family with an MSCRGHAO spec, a worn-wood
  family, and a one-sided alpha-tested grass card family. Check every exported split against the retail pair list
  before baking: zero novel pairs was the rule that kept the level from crashing.
- Furnace resolves `res://td|pct/<name>` and external `xTplName` tpls from `mods_source/` (or retail paks), never from
  `local/`.
- **Custom prefabs:** a node with `xType: prefab` + `xPrefab: <name>` instantiates a compile-time `.prefab` from
  `mods_source/ssl/prefabs/`. Used for light + fire actors, an ambient animal and its sound actor.
- Cost: an 800 m grey box baked in about 21 min (13 of them the navmesh); with ~44k instances and missing markup the
  navmesh step ran out of memory (see gotchas).

### Witcher 3 meshes and textures
- **Textures (measured):** building normal maps are already DirectX (green down) like SM2, with **roughness in the
  normal map's alpha**. SpeedTree vegetation `_n` maps are **OpenGL** (green up): flip G. SpeedTree UVs are top-left
  like glTF, so no V flip for glTF; only Blender's bottom-left UVs need `1 - v`. Diffuse alpha is an alpha-test mask on
  plants; the `_s` alpha is a transmission mask.
- SM2's TextureConverter keeps TGA RGB as (metal, roughness, AO) for an MSCRGHAO spec and drops alpha; build the spec
  from W3's roughness-in-normal-alpha accordingly. It wants absolute input paths.
- **Texture-array materials** (Toussaint buildings use a vertex-blend colourize shader with wear paint) cannot be
  converted texture by texture. What worked: bake the add-on's own shader emulation in Cycles, per unique mesh, onto
  a new UV0, then treat the result as a plain diffuse/normal/spec set. Splitting the layers loses the colourize and
  paint masks (the first preview came out grey instead of red plaster and white stone).
- **In SM2 every converted W3 material is opaque and single-sided** (diffuse alpha forced to 255, back faces culled).
  W3 glass, lattices and fake-interior windows lose their alpha; fake-interior glass shows only its dark diffuse.
- **Scale:** W3 assets at **1.5x** suit the 2.37 m SM2 Primaris for anything the player must enter (the biggest W3
  doorway becomes 1.65 x 3.15 m). Town houses the player does not enter were left at 1.0x.

### Witcher 3 buildings and kits
- **A house is several meshes on one pivot:** ground floor, upper floors (the top one carries the roof), and in some
  families separate roof, porch, overhang or tower parts. Import every exterior part of a stem together; one floor
  alone is a roofless box. Skip winter, interior, volume and proxy meshes unless you need the interior.
- **Doors and windows are not part of the house mesh.** W3 places them separately in the level's world layers, often
  away from the building pivot. The reliable source is the world layer itself: dump each layer's sector meshes
  (position, 3x3 rotation, type) and entities (template + transform), then collect every door, window, glass and
  shutter piece inside the building's footprint.
  - Sector `type` 1 = render mesh, 2 = its collision duplicate (skip), 7 = dynamic mesh.
  - Sector rotation rows are the local X, Y, Z axes in world space, so the matrix is the rows transposed
    (world = T(pos) @ rot^T).
  - Entity rotation = Euler (yaw, pitch, roll) in YXZ order, the add-on's convention; the field named roll holds the
    heading.
  - Entity templates reference their meshes by path; string-scanning the extracted `.w2ent` for `.w2mesh` was enough.
- **City-wall kit:** wall sections are hollow boxes open at both ends (two faces plus the walk, no end caps), so ends
  must butt the next section's measured face span or sit inside a tower; laying pieces by their bounding boxes left
  slots and roof gaps. One gatehouse has no side faces below its roof; close them with strips in the gate's own stone,
  continuing its UV mapping round the corner (take the UV gradient from the face triangles, not from collinear edge
  vertices). Tower variants differ only in where the single wall-walk door faces: pick variant and yaw per corner.
- **Fences:** each section is two meshes on one pivot (beams + rope lashings). Posts sit inside the ends and the rails
  overhang, so neighbours share a post and each run ends on a standalone post. The gate leaf has no posts.
- **Market stalls:** W3 stall and tent canvases are APEX cloth and import as bare frames without an APEX importer.
  Use the static trader stalls, tournament tents and merged goods sets from the Toussaint expansion instead.
- **Bell tower:** W3 has no clock towers; a Toussaint tower with its see-through openings closed by copies of its own
  windows, plus a real W3 temple bell hung in the belfry, did the job (previews approved; not yet baked).
- **Layout statistics** read from W3's foliage cells (64 m each): 70-150 trees per hectare, no lone trees, 78-96 % of
  trees in groups of 10 or more, nearest neighbour about 3 m, 4-8 bushes per tree, fields and roads bare. Our tree
  generator copies that (woods with ragged edges, hedges, an orchard grid, and it drops any tree without a neighbour
  within 12 m). Villages: White Orchard is the most compact layout reference.

### Witcher 3 vegetation
- Grass, bushes and trees are **SpeedTree 7 `.srt`** blobs wrapped in a CR2W object. The add-on's SRT import needs an
  extra importer and its exe; a small own parser replaced it (fixed-size render-state records and a property table;
  all 116 files parsed exactly to their end).
- Camera-facing leaves were baked as crossed cards at a random yaw per card; group the card corners by their shared
  centre position (they are not always in runs of four). Wind data and the AO byte are dropped.
- **Grass:** 4 x 4 m tiles of W3 clumps as clones of a retail one-sided grass card material, instanced via
  `xTplName`, with markup (hide ~150 m, density LODs) and no collision. Real retail grass needs vertex colour channels
  and the converter has no terrain, so SM2's GPU grass scatter is not available. W3's fields hold 126k-262k clumps per
  hectare drawn only to 10-45 m, 10-20x SM2's densest; plan density accordingly.
- **Tree LODs:** map mode cannot carry LODs, so LOD trees go through the prop path (ModelConverter + UsfExporter):
  an empty `tpl_desc` actor node (the converter throws a null reference without it) holding the LOD0 mesh with
  `_lod1..3` children. LOD1-2 = W3 SpeedTree LODs, LOD3 = three crossed billboard cards from the `.srt` billboard views
  (keep each view's rotated flag). Fill `maxLodDist` in `lods_base` and in the markup yourself; the exporter leaves it
  empty. These tpls bake as instances once they sit in `mods_source/tpl/`.

### Witcher 3 animals (ambient, no AI)
- Rip: entity + appearance name + `.w2anims` + `.w2rig`. Without an appearance the horse imports as rig plus a debug
  mesh. The cow set has 18 clips (walk/run/turns, idles, eating, lying, death); the draft horse 191 (about 60 are
  additive layers; skip them and `test_` clips).
- An entity imports as a main rig plus one rig per mesh that follows it through constraints. Load clips onto the main
  rig, bake each clip onto the mesh rig with visual keying, remove the constraints, export glTF with one action per
  clip. A horse with four mesh rigs must first be joined into one rig (rename clashing bones first), or the glTF gets
  per-rig fragments.
- SM2 side: a plain class-list `actor` with `prop_animation_controller` looping one baked `.sani` (the pattern the hub's
  idle Marines use) plays skeletal animation with **no Morpheme network**. Clips bind to tpl bones by channel name;
  channel 0 `CharacterWorldSpaceTM` is identity in retail clips. The tpl_markup needs animation roles (Trajectory,
  CENTRE as character root, every animated bone included); keep CENTRE static and animate a child bone.
- Axes: W3 animals face +Y; Blender (x, y, z) maps to SM2 (-x, z, y). SM2 tpls take three skin weights: keep the three
  heaviest bones and solve the weights by least squares over the clip (plain drop-the-smallest collapsed near-equal
  ties by up to 16 cm).
- **Seen in game:** the cow renders and loops its animation in the level; the first build had a warped muzzle (jaw
  gotcha below). The jaw fix and the sound were built and approved from previews, not yet confirmed in game.

### Witcher 3 audio into an own SM2 bank
- Index: the add-on ships a sound-bank info table (events by name, streamed files by id, banks by id). Small sounds have
  no streamed `.wem`; their media sit inside the `.bnk` (read DIDX for id/offset/size into DATA).
- **Next-gen W3 media are Wwise Opus** (fmt tag 0x3041), which `ww2ogg` cannot read. The fmt extra holds frame size
  (960), total samples, packet count and pre-skip (312); the `seek` chunk lists u16 packet sizes that sum to `data`.
  Re-wrapping the packets as a standard Ogg Opus stream (OpusHead, OpusTags, one packet per page, granule = samples,
  standard Ogg CRC) lets ffmpeg decode it.
- Re-encode with WwiseConsole 2019.2.15 into an own bank (fresh ids checked against every retail bank; the HIRC rules
  are in [the voices note](sm2-voices-talkers-and-wwise-audio.md)).
- Level ambience: a prefab child `sound_actor_full` with `prop_initial_sound` naming the event (the retail setup),
  plus `linksSound` and the class links in the scene manifest.
- **`prop_animation_controller` fires no clip events**, so footsteps and bites cannot ride the clip. Pre-mix them into
  one track of exactly the clip's period and loop it sample-accurately from the same prefab. W3 keeps per-clip events
  (steps, bites, calls with times) inline after each animation-set entry; the add-on skips them, a small reader got the
  timings. Set `isAnimateHidden = True` or hidden actors stop animating.
- W3's own relative levels were too loud for SM2 twice; steps/bites ended 8 dB under the call. In-game playback not
  yet confirmed.

### Space Marine 1 Orks
- **Clip names must come from Relic's hkCombinerTOC** (the first root-level object of every Havok bundle: 48-byte
  entries of name, extension, hash, variant count; the variants that follow are in TOC order). Pairing the string
  table with animation containers in file order misnamed up to 100 % of a unit's clips. Sanity check: the root motion
  must match the name (a forward walk moves forward).
- Root motion: `hkaDefaultAnimatedReferenceFrame`, +Z up, +Y forward, metres plus yaw.
- **Timing lives in the behaviour graph**, on Relic's `hkbSequencerGenerator` tags: normalised times whose event ids
  resolve through the owning graph's event names. Useful ones: the primary-target hit (damage window), the melee combo
  branch (combo window), left/right foot events, voice cues. The foot events are sound cues, not plants: re-cut loops
  on measured foot plants. Ambient graphs borrow attack clips by name, so check clip content visually.
- **`.dcm` meshes:** bone records then section records (joint indices are section-local through a palette); bone
  matrices are row-vector inverse binds, so map bones by name. Stored V runs -1..0 (use `1 + v`); triangles are
  clockwise (flip for glTF/SM2). The plain `<unit>_dif` texture can be an old UV layout: pair mesh and textures through
  the mesh node's material name. Static meshes are in their node's local space (apply the node chain).
- SM2 side used the NPC class route from [the enemies note](sm2-new-enemies-npc-classes-and-morpheme-animation.md):
  Tyranid Warrior as the host network, scale x1.17 (the SM1 Ork:Marine ratio applied to the SM2 Primaris), all 175
  host melee clip slots mapped to SM1 clips (direct, cycled, additive, derived, or stand-in), Saber's leg IK switched
  off (it bakes the host's leg lengths), strikes re-timed on measured impacts, look-at baked into attack clips, and the
  Ork's own voice and effort sounds in an own bank.
- **Seen in game:** the Boy spawns, fights and plays its own sounds. Executing it froze the player until a
  pair-combat (finisher) entry existed, so executions were switched off for the time being. **Outcome: paused**: the
  tester found SM1's 2011 animation too light and dated next to SM2's. That led to the donor research below.

### Animation donors from other games (for the Ork)
- **Elden Ring** (research + one built moveset): a shortlist per Ork type by body plan and weight, measured with
  Froude number, cadence and wind-up length. Lessons: digitigrade donors need leg IK in the retarget (copied bone
  directions float the toes); Elden Ring hit reactions carry no root motion (the engine applies knockback), so borrow
  the host slot's trajectory; pick the run donor whose weight matches the host's, not the most dramatic one.
  **Rejected:** the converted moveset dragged the axe on the ground. Shelved.
- **Witcher 3** (small test first): human one-handed-axe clips through the same converter; the idle carries the
  weapon up in a guard. Verdict pending.
- Lesson: send a few converted attacks as a video before converting a full moveset from a new donor.

### Gears of War: E-Day
- **Containers:** IoStore utoc v8 with Oodle Mermaid. The common Python Kraken decompressor does not handle Mermaid;
  a Mermaid decoder was needed. No `.usmap` ships, so unversioned properties were decoded from the cooked
  UserDefinedStruct/Blueprint class property lists. Facts for this build: no array/map property-flags byte; property
  index order is most-derived class first; GameplayTagContainer = count + names; byte/enum values are raw ints.
- **Animations:** ACL v2.1 (qvvf, drop-w quaternions, segments), decodable from ACL's MIT-licensed headers. The
  track-to-bone map indexes the **shared biped skeleton** (280 bones), not the hero character's 469-bone skeleton;
  default tracks are the skeleton's reference pose (double-precision transforms, centimetres). Prop IK bones snapping
  ~120 degrees mid-clip were genuine (magazine attach), not a decode error.
- **Execution camera:** the paired-kill camera bones are a boom about a root (camera = root + pan rotation applied to
  camera position plus dolly), and sudden dolly jumps are authored punch-in cuts. Both rigs are A-posed, but the SM2
  melee idle is bladed side-on, so retarget bind-relative. Status: preview only.
- **Weapon audio:** each event asset embeds a whole Wwise bank (BKHD v145, Wwise 2022.1); its imported package names
  list the media, and each `.ubulk` media file is a complete RIFF wem (shots raw PCM, reloads Wwise Vorbis). Voice lines
  are external sources, one wem per line, named by speaker, category and text.
- **Mixing a borrowed shot into SM2** (seen and A/B-tested in game on a shotgun skin): drop the donor's baked tail and
  reverb and use SM2's own shot tail and sub-bass layer; measure the shot without the pump rack (vanilla guns have
  none), or the EQ fit darkens the shot; and **calibrate on in-game captures**: offline renders matched loudness, but a
  capture showed +5 dB at 1-4 kHz and +9 dB above 4 kHz against vanilla guns.
- **Reticle:** textures are inline BC7 in the export. The shotgun reticle is one corner bracket drawn four times,
  mirrored, which a screenshot showed; a guess from material switches (rotated pieces) was wrong. Built, not yet
  confirmed in game.
- **Siege mode slice:** E-Day's 12-player Siege (three squads of four on one map, point-budget waves, extraction) was
  decoded for design only. A first SM2 slice copied the retail end-of-mission Thunderhawk level sequence and the hub's
  seats into the testing arena. Seen in game: players reach the seats; the boarding flow was still being fixed.

### Elden Ring cape (Blaidd's) on the SM2 armour constructor
- Built and tested in game, then **abandoned**. Useful findings: the fur colour comes through the mesh's third UV set
  with alpha test at the game's own reference value; Elden Ring fades fur cards at the root (strand alpha x vertex
  alpha), which removes the grey sheet look; SM2's own wolf-fur clumps with Elden Ring colours looked fluffier than
  the original cards.
- Fit rules that held: one uniform scale (anisotropic stretch was rejected); where the shape cannot fit (an 8 cm neck
  hole against a 27 cm gorget), add filler geometry or tuck under armour instead of warping the original; preview on
  the real loadout (a snouted helmet collided with a front collar that never showed with the default helmet).
- The cloth never moved in game although every checkable setting matched a retail cape; cause not found.

### Helldivers 2
- filediver lists nothing without `-i "*"` or an archive name; hash globs never match unnamed files; per-clip JSON
  export fails on NaN and on additive clips, but the unit GLB carries every clip. The state machine exports to JSON and
  names the clips by role.
- A **flyer** built from the Shrieker's motion on the Tyranid Warrior host (wings on the second arm pair) loads and
  spawns in SM2 (details in the enemies note). Motion lessons: the donor wing stroke had to be damped or the wings
  crossed under the belly; a faithful 1:1 mapping looked better than added procedural layers; the arms looked best
  using SM2's own gargoyle fly-by clips (same rig) instead of another creature's.
- Pump-shotgun research: the weapon unit carries pump/bolt/magazine bones with a 14 cm stroke; body clips sit in the
  player avatar GLB. SM2 plays a reload as one clip (no per-shell loop), so a seven-shell reload is one long clip.

### Side notes
- **Red Dead Redemption 2** (not a port; RDR2 modding through LML, using only files from installed community mods):
  `.awc` containers (`ADAT`) hold a u16 chunk-index table, u32 stream infos (`chunks << 29 | id`), 8-byte chunk infos
  (tag, size, offset) and a 32-byte stream format (samples, loop, rate, headroom, codec). Stream ids are
  `joaat(lowercase name) & 0x1FFFFFFF`. Modding tools keep vanilla headroom per stream, which helped tell which streams
  belong to which firing mode. Ped component hashes are `joaat(drawable name)`, with an outfit token between ped and
  category name that defeats brute force. In-game result not recorded.
- **Sign lettering** for invented place names: mask the old letters (distance to a median-filtered background plus
  an ink-colour pass), inpaint with multi-scale normalised convolution plus donor grain, read text orientation from the
  mesh UV Jacobian, size the new text to the old lettering's extent, and carve or paint it with per-letter jitter and
  wear (crisp pasted fonts looked like stickers). W3 shop signs often share one UV island for both sides, so one side
  reads mirrored. Signposts: split post from boards and turn each board toward its real destination.
- **Detail transfer between two meshes of one object** (an AI generator's high- and low-poly exports): they differ in
  scale; a 3x4 affine ICP aligns them to about 0.15 % of size. Rasterise the high surface along the plate normal,
  sample it in the low mesh's UV space, include every outward-facing low triangle, and match roughness/metal levels
  over a feather ring.

## Build steps
1. Confirm a store install of the source game; read its files offline. Decide personal use only.
2. **Level kit:** import each building with all its parts and the openings filled from the world layer; render it in
   the game look (opaque, back faces culled) and check openings, scale (1.5x if enterable) and missing pieces.
3. Convert textures (flip SpeedTree green; MSCRGHAO spec as RGB metal/roughness/AO) into renamed clones of retail
   `.td` families that pair with the map FVF; copy them to `mods_source/{td,pct}`.
4. Write the glTF: Y-up metres, lower-case node names, yaw-only nodes with |yaw| <= 90 degrees (turned mesh copies
   beyond that), instances as `static_geometry` + `xTplName`, prefabs for lights/animals/sounds.
5. Run ModelConverter `--map_mode`, inject `tpl_markup` into BOTH tpl copies, run Furnace (TEMP on a drive with
   space), watch for hidden crash windows, then pack scene + tpl + textures and merge the mission entries.
6. **Characters/animals:** rip to glTF with baked clips, bind every bone to the mesh rest, three skin weights, export
   via the prop/character path, and loop or network the clips on the SM2 side.
7. **Sounds:** decode (re-wrap Wwise Opus as Ogg Opus), mix against SM2 references measured in game, encode with
   WwiseConsole into an own bank.

## Verification
- **Seen in game:** custom scenes built by this pipeline load and are walkable; W3 houses render correctly; the
  ambient W3 cow animates (jaw flaw found that way); SM1 Ork Boy spawns, fights and plays its own sounds (executions switched off); a Gears shot
  sound mix was A/B-tested in game; a Helldivers-driven flyer loads and spawns; the Elden Ring cape displayed but its
  cloth stayed rigid.
- **Seen in game, cause measured afterwards:** wrong yaw on 25 of 58 wall pieces and many houses and lanterns (matched
  against all ~26.5k baked instance records); a later bake missing about 40 % of the map's single-instance objects
  (fix built, retest pending, so the 1,024-type explanation is still a hypothesis).
- **Built, not yet confirmed in game:** grass after the UV fix, LOD trees, cow jaw fix and cow sound, the shotgun
  reticle, the Siege boarding fix.
- **Previews only:** bell tower, farm and fences, Gears execution retarget, W3 donor attacks.
- **Rejected:** Elden Ring Ork moveset; SM1 animation as final quality; Elden Ring cape; generic best-fit door and
  window fills; recoloured animal coats (the original coats were kept).

## Gotchas
1. **Symptom.** Lanterns face the wrong way, wall joints gape and the wall walk floats, although every offline render
   of the glTF is right. **Cause:** the Map Converter/Furnace bake mirrors any node yaw beyond +-90 degrees
   (the converter writes Euler (180, 180 - t, 180); Furnace rebuilds it as a rotation by -t). Exactly +-90 bakes right.
   **Fix:** never write |yaw| > 90: replace the mesh with a copy turned 180 degrees and use yaw -+ 180; for instances, add
   a turned variant source tpl. Tilted nodes were not measured; test a few before relying on them.
2. **Symptom.** Furnace runs all its steps for 30 minutes, then fails "can't find tpl file". **Cause:** capital
   letters in glTF node names (W3 kit names have them) become tpl names the final resolver can't find. **Fix:**
   lower-case node names and `xTplName`. On Windows, writing a lower-case name over an existing file keeps the old
   capitals: move stale tpl folders out first.
3. **Symptom.** About 40 % of a level missing in game (terrain, streets, two buildings), no crash. **Cause (strong
   hypothesis):** single-instance lwi types sorted past index 1,024 (types are listed alphabetically by tpl name) do
   not draw; multi-instance types past it did. **Fix:** merge small one-off pieces into blocks and keep the total lwi
   type count under ~1,000; count types before every bake.
4. **Symptom.** The bake's navmesh step dies "No memory left" about an hour in; grass is solid and draws to 20 km.
   **Cause:** `--install_lwi` writes every instanced tpl twice (`local/tpl` and `mods_source/tpl`) and Furnace reads the
   `mods_source` copy; markup had only been injected into `local`. **Fix:** write markup, its resource link and the
   `.cdt` removal into both copies; check before Furnace.
5. **Symptom.** A bake hangs with the log frozen and the converter at ~0 % CPU. **Cause:** a Saber tool asserted and
   opened an invisible window titled CRASH. Here the error was "Error loading tpl descriptor" because LOD-tree tpls
   lived only in `local/tpl`. **Fix:** enumerate CRASH windows and read their text controls; put external tpls in
   `mods_source/tpl/`. Also: Furnace is a self-extracting bundle that unpacks into `%TEMP%` and dies in seconds when
   that drive is full; point TEMP at a drive with space.
6. **Symptom.** Imported houses have open doorways and see-through windows in game; the player walks into an empty
   shell. **Cause:** W3 places doors and windows as separate level props, often off the building pivot, and some
   "windows" are fake light-volume effect quads. **Fix:** take the exact pieces W3 places in that opening from the world
   layer; doors only in ground-level doorways; drop effect materials; keep existing grilles, bars and lattices; where
   you can see through a closure, add the stem's own interior meshes. Generic best-fit fills (doors in upper windows,
   oversized double doors, stone surrounds on plaster) were rejected.
7. **Symptom.** Glass panes visible in Blender previews are holes to the sky in game. **Cause:** SM2 draws the
   converted materials opaque and single-sided, and the panes faced into the house, so they were culled; an
   orientation-blind ray test reported them closed. **Fix:** face closures outward or make them double-sided (opaque
   leaded glass in W3's own colour was chosen), clear custom normals on duplicated faces, and preview in a game look
   (diffuse + normal, opaque, back-face culling) with a back-face-aware see-through scan.
8. **Symptom.** Streets invisible from above in a preview with culling on. **Cause:** the layout-to-glTF transform
   `(x - c, z, c - y)` is a rotation (determinant +1), not a mirror, but one generator reversed the winding anyway.
   **Fix:** keep layout winding; gate every bake on a triangle-winding vs vertex-normal check.
9. **Symptom.** A fence run on a slope looks "diagonal", rails jump at every joint. **Cause:** map nodes must be pure
   yaw, so each section sits level. **Fix:** put pens on a flat pad and check the height step between neighbours, not
   only the gaps.
10. **Symptom.** Wall sections leave 1.2 m slots and roof gaps; a gatehouse shows holes beside it. **Cause:** the W3
    wall kit is hollow and open-ended, its flat outer face stops short of the piece ends, and one gate has no side
    faces. **Fix:** lay sections face span to face span (overlapping, nudged a few cm against z-fighting) and close
    gate sides with strips in the gate's own material and UVs.
11. **Symptom.** Grass looked bad and popped in. **Cause:** the SpeedTree UVs were flipped like Blender UVs, so cards
    sampled an opaque strip of the atlas; no hide distance. **Fix:** no V flip for glTF; flip only the normal map's
    green; markup hide distance and density LODs.
12. **Symptom.** Animal clips import with zero bone tracks ("Animation buffer has no properties"). **Cause:** the
    add-on's set importers read only clip headers; the keys live in numbered `.buffer` sidecars. **Fix:** decode each
    clip on its own with the single-clip loader, passing the rig.
13. **Symptom.** The cow's tongue pokes out of its cheek, even in the Blender import. **Cause:** the add-on wires the
    jaw with a child-of constraint plus an inverse matrix, a constant 27-degree offset; measuring the bind from the posed
    import copied it. **Fix:** bind every bone, the jaw included, to the inverse of the mesh rig's rest (how W3 skins);
    judge mouths against the bind mesh.
14. **Symptom.** The animal slides about 1 m when clips crossfade. **Cause:** W3 animal clips keep Root at the origin
    and carry travel in the pelvis (and a "walk_left" is a 180-degree U-turn). **Fix:** make Root ride the body's ground
    frame every frame and blend Root's children relative to it; check loops for pops using the shorter quaternion arc.
15. **Symptom.** `ww2ogg` fails on W3 sounds. **Cause:** next-gen media are Wwise Opus (fmt 0x3041). **Fix:** re-wrap
    the packets as Ogg Opus and decode with ffmpeg. Separately, `ww2ogg`/`revorb` on Wwise Vorbis can add up to ~960
    samples; the wem's fmt holds the true sample count.
16. **Symptom.** Random one-shot ambience crossfades into itself. **Cause:** a reused bank builder forced the
    cross-fade transition on every loop container. **Fix:** use the delay transition for random one-shots with gaps
    (what retail ambience uses).
17. **Symptom.** SM1 Stormboy poses came out as the wrong moves. **Cause:** clip names paired with containers in file
    order. **Fix:** name clips from the hkCombinerTOC; verify with root motion.
18. **Symptom.** SM1 mesh previews look broken (stretched UVs, inside-out faces, wrong texture). **Cause:** V stored as
    -1..0, clockwise triangles, and the plain diffuse set being an older UV layout. **Fix:** `1 + v`, flip winding, pair
    textures through the mesh node's material name.
19. **Symptom.** A Python Kraken decompressor fails on every Gears E-Day chunk. **Cause:** the containers use Mermaid,
    another Oodle codec. **Fix:** a Mermaid decoder (tANS and multi-array paths were not needed for this build).
20. **Symptom.** Gears clip bones land on the wrong joints. **Cause:** track indices refer to the shared biped
    skeleton, not the character's own. **Fix:** resolve the skeleton through the clip's imported package names.
21. **Symptom.** A borrowed gun shot sounds "out of place" though levelled to a vanilla gun. **Cause:** the donor's
    baked tail/reverb and raw-RMS matching of a bright sound; offline renders also hid a treble excess that in-game
    captures showed. **Fix:** donor punch/body + host tail + host sub; fit EQ on the shot alone against the vanilla
    median; calibrate on in-game captures timed from muzzle flashes.
22. **Symptom.** A multi-piece HUD element assembled wrong. **Cause:** cooked UE materials have no graph, so the
    layout was guessed. **Fix:** get a screenshot of the element before assembling it.
23. **Symptom.** A level-sequence actor's clip plays at the wrong place. **Cause:** level-actor clips with a world-space
    root ignore the entity matrix. **Fix:** bake the move into clip copies and keep the entities at identity. Also:
    `.resource` list items need the YAML `- `, and the level's replicas manifest must list the client classes of
    replicated objects.
24. **Symptom.** A ported cape looks wrong in game though fine in previews. **Cause:** previews used the default helmet
    and the shape had been stretched to cover armour. **Fix:** preview on the player's actual loadout, scale uniformly,
    and cover gaps with filler instead of warping the source shape.
25. **Symptom.** A new donor moveset is rejected after a full build. **Cause:** feel problems (weight, weapon dragging)
    only show in motion. **Fix:** convert a few attacks, show them as a video, then commit.

## Assets
All meshes, textures, animations and sounds came from the author's own copies of the games named above and stayed on
the author's machine. Previews were Blender renders. Some unrelated SM2 parts of the same projects used AI-generated
meshes (the detail-transfer side note); those, too, stay in personal builds under Saber's rules.

## Cost and time
The level-kit work (buildings, vegetation, animals, audio) spanned about two weeks of sessions (16-29 Oct 2026);
the SM1 Ork port four days to the pause; the Gears shot mix about a day of passes.

## Open questions
- Confirm the 1,024 single-instance lwi type explanation with the merged-block rebuild.
- How tilted (non-yaw) map nodes bake.
- Why the ported cape's cloth stayed rigid with a retail cape's configuration.
- Whether W3 or another donor gives the Ork the weight SM1 lacked.
