---
kind: game
title: "Space Marine 2 new enemies: NPC classes, cloned Morpheme networks, .sani clips, retargeting and executions"
game: "Warhammer 40,000: Space Marine 2"
games_also: []
game_version: "Steam build 25799387 (Patch 15.1, Oct 2026); most findings on Patch 14.x (Sep-Oct 2026). Mod Tools app 3856330 build 25506153"
platform: windows
engine: unknown
route: data
tools: ["Saber SM2 Mod Tools (ModEditor, ModelConverter, UsfExporter)", "Python 3 (numpy, scipy, struct, zlib crc32)", "own .sani reader/writer", "own Morpheme .nmb asset/string-table patcher", "Blender + three.js viewer (previews)", "pymeshlab"]
anti_cheat: "EasyAntiCheat. Everything here uses Saber's official mods folder (client_pc/root/mods), which flags the session 'Mods Detected' (private lobbies, separate progression). No injection, no EAC interaction, PvE only."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-29
links: []
tags: [space-marine-2, saber, npc, enemy, boss, tyranid, morpheme, nmb, sani, animation, retarget, finisher, execution, interplay, xseq, spawning, bio-titan, boss-ai, melee-timing, gore, wwise, root-motion]
---

# Space Marine 2 new enemies: NPC classes, cloned Morpheme networks, .sani clips, retargeting and executions

> How we added a brand-new boss enemy (a custom AI-generated Tyranid on its own skeleton, animated with the Hive
> Tyrant's moves) that spawns, fights and animates next to an untouched retail Hive Tyrant, plus a hovering flyer
> prototype and an execution (finisher) for the boss. The hard part was the Morpheme animation side: cloning a network
> without colliding with the original, and the naming rules behind every animation lookup. This note lists every rule
> we paid a boot crash for. Builds on [the foundations note](sm2-modding-foundations-paks-tools-and-crash-triage.md)
> (manifests, crash dumps, the new-brand crash) and
> [the models note](sm2-models-tpl-format-modelconverter-and-textures.md) (tpl export). The Marine-side network edits
> for weapon clips are in [the weapons note](sm2-weapons-skins-reloads-perks-vfx-and-sounds.md). Verified in game
> unless marked. Additions from 2026-10-15..29 are dated: a close-range boss built on the retail Bio-Titan (Hierophant)
> class, a ported humanoid melee NPC (gore, sound bank, strike timing, reaction exits, network caches), and how
> sequences move actors and play sounds/VFX.

## Setup
- Steam build 25799387 (Patch 15.1); most of the work on Patch 14.x. Saber Mod Tools (Oct 2026) incl.
  `ModEditor/documentation/CLS_File_Guide.pdf` and `Enum_Extension_Tutorial.pdf`.
- Animations: `default_animation.pak` (`.sani` + `.sani_data` sidecars, `morpheme/<set>/<set>.nmb`); manifests
  (`.mr.resource`, `.sani.resource`) in `resources.pak` (client and server copies are identical).
- Test bed: the arena level `test_scene_mod` (Saber's sample level, as shipped by [Testing
  Menu](https://www.nexusmods.com/warhammer40000spacemarine2/mods/233) by Hypexs777 (Nexus Mods)) with spawn buttons
  (below).

## Route and why
Data route plus binary patching of animation assets. A new enemy is: a class (Saber's NPC modder slot, or the newer
official `noSsl` CLS route), its own tpl, a COPY of a donor's Morpheme network made unique, an animation table written
inline, retargeted clips written by our own `.sani` writer, an archetype, and a scenario pool entry. We never edit the
donor creature: everything is cloned, because the engine keys animations by name and shares assets by ID.

## How the game works (what we had to learn)

### NPC class plumbing
- NPCs are replicated server/client pairs (`npc_<x>_server.cls` / `_client.cls`, parents `npc_server` / `npc_client`).
  Their compiled side declares which client class pairs with the server class.
- **What does not work:** a new data "brand" (`.sso` + own sslbin, e.g. a new anim-table type) crashes at boot reading
  0x48. Hand-built class sslbins (we cloned a trivial retail one and swapped its string table and CRC) are IGNORED:
  the log path says "no ssl class for ... Using parent brand ssl class", and the client class still comes from the
  donor's compiled `net_type_client`. Text-only `.cls` classes do load, but cannot choose their own client class.
- **What works:** Saber's pre-registered NPC slots `ssl/characters/modded/npc_modded_1..5_{server,client}` (compiled,
  paired, already in both initial-replica lists, same shape as a declaration-only retail NPC). Put the WHOLE class text
  into the slot's `.cls` (model, bundle, actor name, links, abilities swapped) and give the slot's `.cls.resource` the
  donor's links with the slot's `.ssc.resource`. Verified in game.
- **Since Oct 2026, officially unlimited classes:** `CLS_File_Guide.pdf` "Creating custom NPC" describes the
  `noSsl` route (a copied retail pair with its own `.ssc.resource` per side and `clientClassName`; recipe in the
  foundations note). It would also answer "text-only can't pick its client class". Not yet tried by us.
- Spawnable = an archetype in `ssl/spawn_system/archetypes/archetypes_library.sso` (server `default_other`) whose
  server class appears in that file's `.sso.resource` `dynamicLinks`, plus a `LevelArchetype` pool entry AND a
  `linksDescWeak` class link in every scenario that spawns it (foundations note). Archetype names, smart names and
  anim-table actor keys are plain strings: new ones are fine.
- Melee for NPCs: a weapon desc + ability uid. Ability uids are a compiled enum; before Saber's enum extension a new
  uid crashed at boot (`StringToEnum`), so we borrowed an unused retail NPC melee uid and the modder desc brands
  `for_modders/melee_mod_desc_1..5` (`MeleeModDesc1..5`). With the enum extension a new uid on a `.ext` file loaded.
- Display name: `ui_ai_archetypes_library.sso` entry keyed by ARCHETYPE -> `UI_AI_ARCHETYPE_<X>_NAME` +
  `texts/strings_english.str` (plaintext values render).
- Model: a boss's retail model may be a damaged variant missing skin joints; a cinematic "clean" variant can have the
  full skin. The client effects attach to `fx_*` locators that are MARKUP entities (ship the boss's `.tpl_markup`:
  locators, ragdoll shapes, render params, mutators), not tpl nodes. The server class can keep the donor's tpl for
  hitboxes (`ownerTplName` in the weapon desc).

### Gore on a new model (2026-10-15..16)
- `ssl/damage/gore/gore_mesh_library_mgs.sso` `meshes.<archetype>.<object>` LOOKS per archetype, but its constructor
  fills ONE map keyed by mesh OBJECT name across all archetypes. A new archetype block repeating a retail object name
  throws on the duplicate key and the client hangs on "joining server" forever: no crash dialog, empty report folders,
  only a `.ssldmp` in `...\client\ssl_crash_dump\` (stack: dictionary add <- gore library constructor <- creating the
  Hub game system). Check that folder first for any "joining server" hang.
- Consequence: a model that REUSES a retail model's object names silently gets that model's cut regions and gibs
  (retail variants share regions this way). Own gore = unique object names. Missing hit-hull names in the region lists
  are tolerated.
- **The gore system is switched on per TPL name, not per archetype:** the same file needs `ecsGoreTplLib.<tpl> =
  { __value = "<gore set tpl>" }` and `gorePools.<tpl>`. Without both, the model's cap meshes (hidden per region via
  vertex-colour ids) are drawn permanently and nothing can be cut ("spawns with gore coming out of him").
- **Caps still drawn after that = the instance-constructor template is never applied.** It needs a row
  `<tpl> = { variants = [ { templateName = "..." } ], __type = "InstConstructorTemplateLinkVariants" }` in
  `ssl/main/game/actor_geom_level_customizer.sso`, in EVERY section (a level's own section replaces `default` with no
  fallback). Applying the template shows only the objects its layers name, which is what hides the caps, so the layers
  must name YOUR objects (inline `geomObjNames` override, as a retail cultist variant does) or the whole model vanishes.
  The hang and the permanent caps were seen in game; the build with the customizer row raised no cap complaint in its
  test, but that was not explicitly confirmed.

### A custom sound bank for a new NPC (2026-10-15..16)
- Host wiring (Warrior-class example): the client cls `play_sound_on_morpheme_event.mrEventSounds` maps clip strings to
  Wwise events; the cls `prop_blueprints.Sound` graph starts/stops idle and run loops on Morpheme TAGS, plays death on
  `OnDeath` (except execution targets / mortal headshots) and hit sounds; the `.cls.resource` `linksSound` loads each
  event's bank. NPC step sounds come from clip cues, not a step system. `npc_client`'s sound-group loader loads the group
  named after the class.
- Clip cues are payload events (a `Sound` string) and may only go into the clip's own retail tracks (`Sound`,
  `Sound_Vox`, `Sound_Step`, `SFX` ...), because network anim nodes cache each clip's track list (below). Loco loops
  carry no sound tracks; their `*_sound` sibling clips carry the steps.
- **HIRC order is children-first.** Wwise links a parent only to children ALREADY loaded, and an event only to actions
  already loaded; nothing is re-linked later. Retail writes Sounds, then their containers, then mixers bottom-up, then
  actions, then events. A bank sorted by object type parsed cleanly in a bank viewer but loaded 47 of 49 containers
  empty: the NPC was completely silent in game (proved by cross-correlating the recording against every source file).
  Before shipping a hand-built bank, simulate the load order and count empty containers (retail: zero).
- Events with `prepareOrder <= 0` play straight from the loaded bank (correct for in-bank media; retail has hundreds,
  NPCs included). Bank layout details for this Wwise version (v150): FX entries are 6 bytes; a random/sequence
  container's child list is easiest found from the END of its body. Continuous loops use the continuous bit with loop
  count 0; a per-hit chance = silent takes plus the weighted bit. The children-first rebuild of the same bank played in
  game (verified).

### How character animation is wired (everything by name)
- Client `prop_morpheme_controller` (`animSet`, `nameBundle`) + `.cls.resource` `linksMr` pick
  `morpheme/<set>/<set>.nmb` and its `.mr.resource` (JSON listing the clips the network plays).
- Moves come from an anim table (`ssl/animation/categories/anim_table_<actor>.sso`, entries with `pathToAnim`)
  registered by actor name in `ssl/animation/animation_table.sso`; `actorName` in
  `prop_morpheme_animation_{client,server}` selects it. A new table type crashes (new brand); writing the table INLINE
  inside `animation_table.sso` as an `AnimTableActor` object works.
- Everything else links `"<Actor>.<Category>.<Move>"` strings: the melee weapon desc (attacks), `smarts_library`
  (an actor block of smarts), the server class (traversal, hit reactions), the resurrection prop. Fork all of them to
  your actor name.
- **Animation FILE NAMES are global.** The engine keys clips by file name, not path: a copy with the retail basename in
  a new folder replaced the retail creature's clip (the retail boss started playing our retargeted motion with
  stretched limbs). Every clip of your creature needs a unique file name.
- **How an `animName` resolves:** the per-bundle reader names each clip by its FILE name minus the network's
  set-name suffix (`<prefix>_<move>_<set>` -> `<prefix>_<move>`), and a category's `characterName` selects which set of
  the network to search. **Slot entries** (`pathToAnim` -> anim source) resolved in every test. **Network-only
  entries** (an `animName` with no slot category) resolve against a game-wide registry of the BASE game's networks that
  a mod network never joins: a miss on an `AnimInfoTrajectory` entry is a boot crash (index -1), while `AnimSlotInfo`
  entries tolerate misses (retail has some). **Rule: every table entry that names one of YOUR set's clips must be a slot
  entry.** Retail tables freely use slot files of other sets.
- **`AnimInfoTrajectory` clips need start/end events** (Footsteps track, user ids 200 / 205 = `animStartId` /
  `animEndId`). Every retail trajectory slot clip has them; a victim clip without them crashed the client when the
  execution started (a float read as a pointer).
- The `.ssldmp` JSON heap (`objects`) lists every `AnimInfo` with its `animName` and whether `morphemeInfo` resolved -
  the fastest way to see which lookup failed before a crash.

### Cloning a Morpheme network (`.nmb`) safely
- An `.nmb` is a bundle of assets with 40-byte headers (type, a 32-bit ID, size, alignment). Types seen: 13 = anim file
  list and 12 (one fixed ID shared by every network), 1 = rig, 6 = rig-to-anim map, 7 = controller, 2 = animation set,
  10 = network. Rig/map/controller/set/network IDs are UNIQUE per retail network and registered GLOBALLY; the network
  refers to the others by ID.
- **A byte copy keeps the donor's IDs, so the engine keeps ONE network for both creatures**: whichever loads first
  serves both bundles. That is how a clone can "work" while secretly using the retail definition, and how the retail
  creature ends up playing the clone's clips. **Give every cloned network new asset IDs** (we used a CRC of a namespaced
  string and checked it against every retail ID).
- **String tables are hashed and sorted.** Every multi-entry string table stores a CRC-32/BZIP2 hash per string
  (poly 0x04C11DB7, init/xorout 0xFFFFFFFF, not reflected; little-endian u32) and keeps the hash array SORTED
  ascending for binary search; ~650 node names are hashed, the anim PATH strings are not. Renaming hashed strings (even
  with correct new hashes) leaves the array unsorted and lookups miss: the clone crashed only once it got unique IDs
  and was actually used. **Never edit hashed strings in a clone** (except one-entry tables); same-length renames of
  anim paths are fine.
- **Own animation set:** the network's set table holds `[u32 CRC][name]` entries (a network can carry several sets,
  e.g. the Tyranid warrior network holds three). Give the clone its own set name, rewrite the set name's CRC in the set
  header (big-endian) AND the packed partial copies of that CRC in the controller and network headers - all three must
  agree. For a multi-entry set table, pick a set name whose CRC keeps the table sorted. Name your clips
  `<prefix>_<move>_<yourset>`, set every category's `characterName` and the client `animSet` to it.
- The network's anim list (asset type 13) has four parallel tables: path, load format (`sani` = regular, `sani+` =
  regular + additive stream), and two empty strings. Same-path pairs are (sani, sani+), never spare duplicates.
- New clips need manifests: `animation/<path>.sani.resource` per clip (`res_desc_animation`: animation, name, animData)
  and a link in the set's `.mr.resource` `linksAnimation`. Without them: boot crash on a null stream.

### The Morpheme rule list (one line each; every one cost a crash or a hijack)
1. Clip file names are global: unique `<prefix>_<move>_<set>` names, never a retail basename in a new folder.
2. A cloned network gets NEW asset IDs (rig, map, controller, set, network) or it silently merges with the donor.
3. Own animation set: own set name, its CRC in the set header and the packed copies in controller/network headers.
4. Never edit hashed strings (node names): the CRC-32/BZIP2 arrays must stay sorted. Unhashed anim paths may be
   renamed at the same length.
5. Every anim-table entry that names a clip of your set is a SLOT entry (`pathToAnim`), never network-only.
6. `AnimInfoTrajectory` clips carry Footsteps start/end events (200 / 205).
7. Every new clip has a `.sani.resource` and a link in the set's `.mr.resource`.
8. From the Marine network work (details in the weapons note's network section): reused anim slots resolve by LEAF
   name and the first namesake wins; a Blend2 never sits under a SingleFrame or wraps a clip whose markers must
   arrive; additive streams start from the LIVE retail clip's frame 0.

### Network internals that matter when clips change (2026-10-15)
Decoded on the Tyranid Warrior network (3 sets, ~1200 nodes) while porting a humanoid melee enemy onto it; a parser
for node definitions, attributes and state machines read all 44 retail networks cleanly.
- Network asset: u32 at +168 = node count, u64 at +176 = offset of the node-offset table (0 = no record). Attribute
  handles are SELF-relative i64 offsets; per-set attributes are indexed `set * nSemantics + semantic`. Node type ids
  follow Morpheme's public enums; attribute type ids differ (measure them).
- **Anim nodes (type 104) cache clip data per animation set:** anim-list index, set asset id, the clip DURATION, the
  number of discrete and duration event tracks and a CRC-32/BZIP2 hash of each track GUID (clip file order). The
  single-set Marine network keeps the same block at a fixed offset. Clips re-made with different timing or a different
  track list leave these caches stale. What worked: give every new clip the retail track list back (dropped tracks
  stay, empty), fresh GUIDs, and write durations + hashes into YOUR set's blocks only. The same nodes cache the clip's
  start/end trajectory (positions and quaternions); copied nodes may hold zeros there, harmless unless root motion is
  applied.
- Saber anim-slot nodes are type 1001 (slot id inside); the slot table lives in the network asset. A declared slot no
  node reads can carry info-only table entries for moves the network plays from fixed nodes. Network-only table
  entries name anim NODE leaf names, not clip names.
- **Transitions** are an OR of AND-groups; conditions are variable-size records (type, negate flag, the CP node id,
  greater/less/or-equal and in-range variants). State machines keep no CP input list, so a condition can be repointed at
  any CP node. Saber's expression VM: `[s][a][b][op]` with move, divide, compares and jump opcodes.
- **Creature LOCO hard-codes the donor's speeds** (Warrior: walk/run blend over 2.25..6 m/s, sprint only when the max
  desired speed is exactly 8.5, walking start for desired speed 2..2.5, stop choice at 4). A creature whose clips move
  at other speeds needs those gates re-pointed (e.g. at the walking-mode CP).
- **Saber LegIK (type 158) stores the HOST's leg segment lengths** (and derived sums) in the node; a retargeted body
  with other proportions gets bent legs. Disabling it (its distance threshold expression set to -1) was the fix.
- **Sync:** walking stops enter by a sync-event transit that uses the event INDEX, so loops feeding them must keep the
  host's two foot events per cycle; start -> loco is a plain transit, so a start clip must end on the loop's frame 0.
  Measure foot plants from motion, not from imported "foot" tags (another game's tags were sound cues).
- **Reaction exits on event 205.** The Warrior network leaves heavy-hit, stagger, parry-reaction and stun-out states on
  Footsteps event 205 (the track partitions the clip as 200 | 0 | 205) with a 0.5 s blend to LOCO. A clip that copies the
  host's event fractions inherits the host's recovery time: a body still lying on the floor got blended to running in
  0.5 s. Rule used: 205 no earlier than the frame from which key joints stay within ~35 cm of the settled end pose and
  the head is at >= 90 % of its final height; only ever move it later.
- **Snap entries:** ANY -> heavy hit and stagger use a 0 s blend, so a clip that starts kneeling teleports to the floor.
  Prepend a short transition reel. Pair stun loops with their own exits (a standing-daze exit after a kneeling loop
  spun the body 170 deg while matching in head height).
- **Head look is off during attacks:** attack states emit `look_at_enable_mr` = 0 and re-enabling waits for the melee
  CP to drop, so the clip's own head shows. Bake the look direction into attack clips.

### Melee strike timing for NPCs (2026-10-15)
Validated on the retail Tyranid Warrior (all five strikes land in a replay, and the fit lands on Saber's own
constraint ends):
- Constraint window events: 305 = position + rotation, 306 = position, 307 = rotation. At the window END the attacker
  faces the target and the gap between the two rigid-body capsules equals `constraintOffset` (Saber's hint: extra
  offset between collision capsules, -1 = constrain to the target root). Value = the strike's
  `constraintSettingsOverrides.ConstraintOffset`, else the combo desc's `constraintSettings` (1.8 for the claw desc);
  speed capped by `maxLinearSpeed` (10, heavies 20). Capsule radius 0.75 for both Warrior and Marine.
- Damage window 405: the strike's `meleeDetectors` (named segments on locator bones) are swept against the target's
  hit hulls. Hits are purely geometric: the blade must pass through the player.
- Retail norm over 287 NPC attack clips: exactly one 405 per strike, and the constraint ends a median 0.067 s AFTER
  405 opens (only 9 end more than 0.15 s before it).
- AI start distance: the Warrior combo kata sprints until the enemy is within `ComboSlashRangeMax` (class blackboard:
  10 brawler / 4 defensive); jump attack 7-16 m, heavy 0-5 m.
- Recipe for new or ported clips: place a target at the constraint end, measure where the weapon sweeps through it,
  put 405 around that impact and end the constraint there; `ConstraintOffset` = measured distance minus 1.5 m of
  capsule radii; check `ComboSlashRangeMax` against the clip's reach. Imported hit tags from another game were gameplay
  timers (no blade test) and made most strikes whiff, one mid-spin with the back to the player. The model is checked
  offline against retail; strikes retimed with it were built, but their hit rate in game was not confirmed (the port
  was paused for animation feel).

### `.sani` clip format (what our writer handles)
- A chunked file plus a `.sani_data` sidecar. Chunks: 241 meta (channel names), 242 regular animation data (inline;
  246 streamed), 243 additive layer (inline; 247 streamed), 244 trajectory (root motion), 245 events - always the LAST
  chunk, so it can be resized by rewriting only its own end. The sidecar holds 242 (+243).
- Versions: v1 (cinematics) = raw floats with no leading compression field; v2 = u16 compression 1 (Optimized, raw
  floats, rows padded to multiples of 4 entries of 16 bytes); v3 = compression 2 "QuantizationTo16" with eight counts
  (animated/fixed x position/rotation/scale/float), a fixed-scale quantisation block and per-channel scales. Base clips
  inline their first 3 frames. Many cinematic clips use other compression ids we did not decode.
- **Fixed vs animated channels:** creature clips store most bones' local translations as "fixed positions" (one value
  per clip, u16-quantised with a shared range) equal to the bind-pose local offset; only ~25 channels (pelvis/spine,
  tail, hand holds, foot targets) have animated positions. This is what makes a skeleton swap possible.
- Additive layers are deltas from the clip's FIRST frame: `p(t) - p(0)`, `q(t) * q(0)^-1`. TPL (tpl-baked) clips are
  additive on the tpl bind.
- Trajectory chunk: u16 2, vec3 position offset/scale and rotation offset/scale, then u16x3 positions for every
  keyframe, THEN u16x3 rotations (structure of arrays); cumulative root motion (a run cycle moves ~10 m).
- **Events chunk:** `u32 nTracks`; per track `name, 16-byte GUID, u32 type (1 = duration windows, 0 = payload),
  u8 flag, u32 nEvents`; per event `f32 start, f32 duration` (FRACTIONS of the clip), `u32 userData`, payload ids; then
  a string table (`"Sound"` entries with blob offsets) and a NUL-separated blob. Attack timing lives HERE, not in the
  melee desc. Measured user ids: damaging window 405, next-input storing 510, next combo hit 515, aborting 505,
  position constraining 306, rotation constraining 307, endurance 15, look-at disable 3311, Footsteps 200/205, legs
  10/11. Payload tracks point at strings: damage windows, `attack_indication_dodge` (the dodge flash), Wwise events,
  camera shakes, `fx_*` locators, step markers. Track names vary (typos); ids and strings are what count. The anim
  table entry's `durationEvents = { Name = id }` maps ids to meanings for code.
- A from-scratch writer reproduced 155 retail clips to 0.02 mm / 0.003 deg. Pitfalls: a rotation "is it constant"
  epsilon of 1e-5 froze slow bones (use ~1e-9); an older public reader takes the LAST 242/243 chunk (misreads additive
  files) and pads Optimized rows wrongly.
- (2026-10-15) Full survey with Saber's own reader as the oracle (the `FioSaveLoad` library from the Mod Tools): all
  ~44,900 retail clips (client, server, TPL paks) parse with exact byte consumption and re-serialise byte-identical.
  Header `ETNA` + u16 version: 1 = no compression (cinematics; Optimized layout only; trajectory uncompressed as vec3
  then WXYZ quaternion arrays), 2 = quantization (a u16 compression id per layer and for the trajectory), 3 = TPL object
  clips (Q16 with scale tracks and one visibility float curve per joint). Chunk 248 is an empty "out of streaming
  budget" flag; streaming chunks 246/247 carry `preload` frames while the sidecar holds ALL frames.
- Q16 packing: positions packed 11/11/10 bits in a u32, rotations u16x3 of `q.xyz / (1 + w)`, floats u16, offset = min,
  ranges below 1e-4 widened to 1e-4. Optimized rows: vec3/quat rows padded to 4 entries, float rows never padded.
- **Every clip of an animation set has the IDENTICAL channel list = the rig's bone order** (one list across ~17,400
  Marine clips; 195 channels on the Warrior): a new clip must reproduce it exactly. Player clips run at 24 fps, NPC
  clips at 30. Player float curves (length, foot positions, look-at) are almost always constant 0. Event parameters
  have Bool/Int/Float/String types; retail uses only String (`Sound`).

### Retargeting creature motion onto a new body without reshaping the mesh
- Give the creature its OWN skeleton: donor hierarchy and bind orientations, joints placed at the new anatomy. Then
  replace the clips' fixed offsets with yours, shift animated position tracks by (your bind local - donor bind local),
  keep rotations. The mesh is never deformed. (Moving only the tpl bind pose never works: clips carry translations.)
- Retarget relative to the donor's IDLE for the upper body (the donor idle differs from its bind by 15-45 deg per
  spine/shoulder joint) but relative to the BIND for pelvis/legs if the idle stance is staggered; correct the inherited
  lean where an idle-referenced joint hangs under a bind-referenced one. Soft-limit idle-relative rotation deltas
  (`L * tanh(k * theta / L)`) on neck/head/jaw/spine/clavicles: donor attacks swing the head 90-127 deg.
- Moves from a DIFFERENT creature: world-delta rotations for mapped bones; legs by foot placement (follow the source
  foot path, pin plants, lower the pelvis when out of reach), not by copying knee angles; joint limits LEARNED from
  your already-approved clips (elbows turned out to be hinges); per-direction torso-lean limits (exclude death/faint
  clips from the learning); full pelvis rise when the source is airborne; capsule collision between limbs and torso.
  Look at the source motion before mapping a new creature (dangling tails/arms need special handling).
- Skinning rules that held: rigid = armour/chitin (classify by texture colour), stretch = flesh; implicit diffusion
  for weight smoothing (iterative Laplacian gave hinge-like folds); rigid hooves with a flex clamp; a jaw split by
  surface distance; always compare foot tracks (min/max height, stride) after changing the retarget reference.
- Blender round trip for an animator: export the armature with exactly the clip channels and rest = bind; read back
  world deltas `R(t) = Rf(t) * Rf_rest^-1 * R_bind` (immune to Blender re-orienting bones), root -> trajectory; for an
  execution, keep the creature relative to the executor's `smart_target`. Round-trip error ~8 mm / 0.08 deg (Q16).
- Saber's official **Animation Retargeting** blueprint node (Oct 2026) maps the Primaris set onto a humanoid of other
  proportions (sample config in the test scene mod's client scenario; equipment positions need manual tuning). It is
  Primaris-based and does not cover creature sets.
- (2026-10-16..23) **What made new creature moves acceptable** (judged by a human from rendered videos): moves built on
  the creature's OWN retail clips, or a limb driven along a designed path by IK with a clear weight shift and the other
  feet planted. Rejected as "super rough": attacks made from a few rotation offsets on spine/neck/tail chains plus IK,
  added tremble, arms wound up too high or spread out, joints bent past what retail clips ever bend. Rules that came
  out of it: cap every IK joint inside the range measured from the retail clips (keep never-bent joints rigid); no added
  jitter; monotone curve tangents (no overshoot); after a strike, one hold and ONE pull-back into the idle (no tug);
  neck extension jams armour plates into the back shell, so let the body rear or tip instead; check mesh
  self-intersection per frame on the real mesh before rendering; verify signs (a jaw pitch sign was inverted in every
  early preview, closing the jaw into the skull); look targets must lie in front of the head (on a huge creature the
  head sits far forward of the origin).
- When trying a new animation DONOR (another creature or game), render 3-5 attacks plus the idle carry/stance first.
  A full 175-slot moveset was rejected on sight for one trait visible in the idle (the weapon dragging on the ground).

### Executions (finishers)
- Who can execute what: `ssl/smarts/pair_combat_library.sso` -> executors -> `targetsInfo.<KEY>.finisherDescs`, KEY =
  the target's server `actorName`. Each `PairCombatDesc` = `cinematicDescLink` + the executor's anim (chosen by a
  "destiny" float). Bosses have no entry.
- `cinematicDescLink` -> the target CLIENT class's `prop_interplay_resource_import.interplayController` (e.g.
  `ssl/interactive_animations/interplay_controller/interplay_controller_lictor.sso`) -> `LevelSequenceDesc` naming an
  `.xseq` under `ssl/interactive_animations/finishers/`. Retail names can be crossed (a "safe" key points at an
  "unsafe" sequence).
- An `.xseq` holds both clips, prop actors (e.g. a severed claw attached to the target's `cam_anim` bone), blueprint
  event tracks (invisibility on/off), gore presets and a kill track. Staging: the target clip's root = the executor's
  `smart_target` bone.
- Executable at low health = server `damagable_health_server.incapModuleDesc` (a `DamagableIncapModuleDesc` with
  incap start/loop/end anim links); bosses ship it as `null`. Copying a retail incap block made our boss go down and
  show the execute prompt (verified).
- **A new `.xseq` must be registered in the GLOBAL `interplay_controller_default.sso`**; a class-inline interplay
  override was ignored and the execution crashed (`interplaySequence` null). There is no unused retail xseq to borrow.

### Sequences (`.xseq`): root motion, sounds and VFX actors (2026-10-15)
- **No root motion from emotes or sequences.** Root motion is script-driven only: the Morpheme prop's root mover /
  move-by-trajectory (melee, `BlueprintNodeAbilityTaskRootAnimation`, grabs) or the controller's native
  `useAnimRootMotion` (deaths; off for players). A smart emote's anim mode only puts the rigid body in anim mode;
  nothing moves it, and retail emote clips carry zero trajectory.
- **Retail moves actors in a sequence by ATTACHING them to an animated bone:** a usable door attaches `#/initiator`
  via `xc_track_attach_to_object` to a bone of the door's animated object; cinematics spawn an actor with geom
  `cc_cinematic_items` (rig ROOT + CENTRE + Trajectory + `item_01..24`, metres) that plays a standalone section clip,
  and other actors attach to its item bones (the `.xseq.resource` links the clip's `.sani.resource`, the actor class
  and the tpl). Spawnables are placed in local metres around the sequence origin; an emote's origin is the user.
- **But an attach inside a smart EMOTE did not move the player** (the sit played in place; tested). Retail
  player-moving sequences attach the initiator to SCENE object bones under a usable (anim mode NONE), and interaction /
  finisher smarts pause the character transform sync; finishers move the initiator with a root mover on the clip's
  trajectory. Use a usable + level sequence for anything that must move the player.
- Absolute scene references exist: `<scn>/<scene>__<layer>/a/b` names a scene object (`<layer>__a__b` in the cd_list).
- **Sounds:** sound-track sections `{from, to, rowIndex, soundDesc{type{name, __type GameSound}, __type
  GameSoundDesc}}` on an `xc_track_actor` bound to a `sound_actor_full` actor. Every event must be listed in the
  `.xseq.resource` `linksSound` (that loads its bank). `GameSound` has no volume (only fades and parameter overrides);
  emitters have attenuation scale and size. Some retail events are SILENT (`media_bundles: []`, wem in no header):
  check media before choosing one. A section spanning a sequence loop's points keeps playing; keep one-shots out of
  loop ranges.
- **VFX:** the xseq's trailing actors dict holds `sfx_entity` actors (`transform` world position/rotation,
  `desc.properties.sfx.list.<sfx brand> = { scale }`, `__onlyOn "visual"`); a track `#/<name>` with path
  `desc/properties/sfx/list/<brand>/active` and an `xc_spline_bool` switches each on at a time.
- Lamps in `.sfx` files are `sfx_light_base` entries (`lightType "point"`, `RadiusCtrl`, `ColorCtrl` A,R,G,B,
  `Intensity`) inside an `sfx_group`; retail "glowing" lenses are small 0.2-0.4 m lights right on the lens, no
  sprites. Continuous particles use a `constantFlow` emission type.

### Spawning in the testing arena
- Testing Menu's copy of `xscenes/test_scene_mod/test_scene_mod_scenario_server.sso` sets
  `useDefaultArchetypesPoolsLibrary = False` with an explicit pool: add your `LevelArchetype` + `linksDescWeak` there.
- Level actors: usable buttons tagged `usable_button_1..5`, spawn domains `dom_spawn_1..4`. Wiring:
  `GetFirstTaggedActor(tag)` -> `SubscribeToUsableActor` (`subscribeOnInitRef True`) `OnUsed` ->
  `SpawnActorByArchetype` with `typeRef` and a transform from `GetFirstTaggedActor("dom_spawn_N")`. Ship it as a small
  pak that sorts before the testing menu. (The menu's own F2 spawn list lives in a 100+ MB player class - avoid.)

### Flying enemies
- Retail ships a gargoyle model and network that only perch and die (decoration); real flight exists only for the
  cosmetic boid flock. A playable "flyer" = a ground NPC whose clips hold the body several metres above its ground
  capsule (hover), with attacks diving down into parry range. Wings can ride a donor's second arm pair (the Tyranid
  warrior network). Loaded and spawned in game; combat feel and execution still open.

### A close-range boss on the retail Bio-Titan class (2026-10-22..29)
Goal: turn the long-range Bio-Titan (internal name Hierophant, archetype `TyrHierophant`, ~45 m tall) into a boss that
walks up to the squad, takes real bullet damage and fights with stomps, swipes and acid. Built by overriding its class
(no new skeleton), with new clips on its own network.
- Retail facts: 49 per-bone `*_cdt` hit meshes already cover the body (88 % of the surface within 0.5 m); damage
  sensitivity 0.02 for bullets and 0 for melee, HP 1100; it keeps 50-215 m away; its smokescreen spawns at map markers.
  Changing the class also changes the Bio-Titan in every mode that uses it.
- **Its server body is a 1.8 m `char_server` pillar** scaled up, so the legs cannot be hit in melee. Fix: `geom_server`
  `nameTpl` = its own model (as the Lord of Change class does), plus server `cdtSkeleton` collision. Scaled-down copies
  (client `geom.scale` in spare `npc_modded_N` slots; scale nodes cannot target other actors) keep the pillar.
- **Target picking:** an inline override of the Hive Tyrant's target-picker brand made it chase whoever deals it the
  most damage (built; not checked on its own).
- **New moves:** a new clip played through an existing network state (the smoke ability's), an anim-table entry, a new
  `AbilityUid` via the enum extension (see the [active reload / abilities note](sm2-active-reload-and-cloned-abilities.md))
  and a server-side ground burst at a leg locator. Retail taunts (with their `abort` entry) served as phase roars at HP
  thresholds; a charged shot fires the retail big shells from a client view module. In an ability CLIENT blueprint,
  getting a transform without an actor ref returns the owner. Retail bomb projectiles use gravity 30 (the big one 10).
- **AI pitfall:** a close-range branch put first under "Shooting / Movement" sat under a top-priority utility monitor
  whose cooldown starts only ON_SUCCESS, so it kept pre-empting the kata and restarting the retail volley (the "spammed
  charged shot"). Fix: put the branch under "Approach / Walking" and gate the volley to >= 35 m.
- **Idling:** the retail walk fallback needs level `MovementPoints` (a test arena has none) and waits 6.5-13 s, and an
  approach band of 32-42 m left it standing. Next build: approach 22-30 m and walk an arc around the target with
  `BhvNodeMoveToPosition` between attacks (built, untested).
- **Blood on hits** comes from the covering system (`prop_covering`, a voxel field: 0.5 m voxels on `npc_client`, 1 m and
  a 1000 m max distance on Saber's own cutscene Bio-Titan); a 45 m body needs the override.
- Also in the build: weak-point damage multipliers per body part, a melee damage multiplier, LOD distance past 120 m.
- **Textures:** PC ships only one 2048 set for it (cutscenes and gibs use the same), ~24 texels/m on the body. A
  4096 set under the retail names plus an `mml_cfg` top-mip entry raised the detail.
- Parry route (researched, not built): parriable NPC strikes come from the NPC melee system (`MeleeDesc` strikes with
  `isLockParryStance`, no `attack_indication_dodge` track, not `isPervasive`).
- Status: tested in game as "pretty good" (close-range moveset, acid spew, stomp flurry, belly slam, phase roars,
  weak points); remaining complaint = idling between attacks.

### Creature textures and part swaps
- Retail Tyranid conventions: DirectX normal maps (strong, xy std ~0.35-0.4), spec R metal 0 / G rough / B AO, diffuse
  alpha = subsurface mask (~255 flesh, ~0 chitin). Matching an AI texture to retail: per-material-class Lab palette
  transfer + high-pass retail detail projected triplanar with stochastic tiling, and roughness quantile-matched per
  hard class. Boosting AI normals amplifies AI "lumps"; darkening curvature noise reads as leopard print.
- Retail eyes/teeth onto a custom creature: copy the retail primitive per LOD with the retail MATERIAL NAME; it exports
  to the same tpl material block, so keep the retail `pct`/`td` links in the `.tpl.resource` and ship nothing. Measure
  occlusion on the shipped game LOD, not the source mesh; add a dark socket cup behind domes so cut-outs don't open
  the head. Retail parts that must conform to a different body: enclose (sleeve) rather than cut.

## Build steps
1. Class: an `npc_modded_N` slot (or the `noSsl` CLS route) with the donor's full class text, swapped names/links.
2. Model: own tpl on the donor's skeleton layout (or own joints), LODs, tangents, ship the donor's markup.
3. Clips: retarget into `<prefix>_<move>_<yourset>.sani` with the source's event tracks, `.sani.resource` each.
4. Network: copy the donor `.nmb`; new asset IDs; own set name + CRC (+ packed copies); never touch hashed strings;
   same-length path renames to your folder; own `.mr.resource`.
5. Anim table inline in `animation_table.sso`; all your entries as slot entries; trajectory clips with Footsteps
   start/end events; fork every `<Actor>.<Cat>.<Move>` link (melee desc, smarts, server cls).
6. Archetype + scenario pool + `linksDescWeak`; display name; arena spawn pak. ZIP_STORED; test that a retail donor
   spawned beside it still animates normally.

## Verification
- In game: the new boss boots, spawns, animates with its own network, and a retail Hive Tyrant spawned next to it is
  normal (the decisive test for ID/name collisions); modder slot class; inline anim table; incap + execute prompt via
  `pair_combat_library`; flyer prototype loads and spawns; enum-extended ability uid loads.
- Every crash rule above came from a real boot or load crash, confirmed by the `.ssldmp` heap or error.yaml.
- Not verified: the execution sequence itself after the Footsteps-event fix, a globally registered new xseq, the
  official `noSsl` NPC route, combat AI on new movesets (built clips are not yet wired into AI behaviour trees).
- (2026-10-15..29) In game: the gore-library hang and its fix by unique object names; a hand-built NPC bank silent
  until rebuilt children-first; the sit attach inside an emote NOT moving the player; the Bio-Titan boss with real
  bullet damage, new close-range moves on new ability uids, AI branch moved under approach, tested as "pretty good"
  (combat AI on a new moveset now partly answered: new branches inside the retail behaviour tree work). Built, not
  confirmed: the level-customizer cap fix, retimed strike windows, reaction-exit retiming, the arc-walk between attacks.

## Gotchas
1. **New NPC looks exactly like the donor in game.** Cause: hand-built class sslbins are ignored and the client class
   comes from the donor's compiled pair. Fix: `npc_modded_N` slots or the `noSsl` CLS route.
2. **Boot crash in AbilityLibrary StringToEnum.** Cause: new ability uid without enum extension. Fix: enum extension
   or an unused retail uid.
3. **The retail creature suddenly plays your retargeted motion.** Cause: clip file names reused (names are global), or
   network asset IDs shared with the donor. Fix: unique file names AND new asset IDs.
4. **Server crash at barge load after renaming anim names.** Cause: `animName` is matched to loaded FILE names minus
   the set suffix; renaming the suffix or the set breaks it. Fix: `<prefix>_<move>_<set>` naming with an own set.
5. **Boot crash on a network-only entry (`TraversalDown.End`-style) no matter how the network is renamed.** Cause:
   network-only names resolve only against base-game networks. Fix: make every own-set entry a slot entry.
6. **Clone crashes the moment it finally uses its own network (a float parameter on a null network).** Cause: renamed
   hashed strings left the sorted hash array unsorted. Fix: keep retail node names/hashes; only own set name + CRCs.
7. **Clone "works" only while it shares the donor's IDs.** Cause: one global network served both. Fix: new IDs, then
   fix whatever the clone's own network breaks.
8. **Execution crashed the client reading a float (1.0) as a pointer.** Cause: trajectory slot clip without
   Footsteps start/end events. Fix: copy the source clip's Footsteps track.
9. **Execution crashed: interplay sequence null.** Cause: new xseq only listed in a class-inline override. Fix:
   register it in `interplay_controller_default.sso`.
10. **Boot crash on a null stream, "Filename is empty!".** Cause: clip without `.sani.resource` / `.mr.resource` link.
    Fix: ship both.
11. **Retargeted creature's feet take giant strides / chest folds into the belly.** Cause: wrong retarget reference
    (staggered idle for legs, bind for the hunched spine). Fix: per-region reference + lean correction.
12. **Elbows/claws bend unnaturally on borrowed moves.** Cause: copied joint rotations off the hinge axis. Fix:
    project onto limits learned from approved clips.
13. **Crest/back tears in attacks.** Cause: donor head-vs-back swings up to 127 deg. Fix: soft rotation limits and
    rigid plates on the back bone.
14. **Slow bones frozen after re-encoding.** Cause: constant-channel epsilon too large. Fix: ~1e-9.
15. **A clip decodes as garbage with an older public reader.** Cause: it takes the last 242/243 chunk and pads
    Optimized rows wrongly. Fix: walk the chunk table; 16-byte row padding.
16. **Effects (eye glow, claw fx) at the wrong place on a custom mesh.** Cause: `fx_*` locators are markup entities /
    rig locators, not tpl nodes. Fix: ship the donor markup; offset effects in the class.
17. **Spawn button does nothing.** Cause: archetype missing from the level's explicit pool or its `linksDescWeak`.
    Fix: add both in the arena scenario copy.
18. **Display name still the donor's.** Cause: name comes from `ui_ai_archetypes_library` keyed by archetype, and the
    first-sorting pak's `strings_english.str` wins. Fix: own entry + merged strings file.
19. **Client stuck on "joining server" forever, no crash dialog.** **Cause:** a gore-library entry repeated a retail
    mesh object name (one global map). **Fix:** unique object names; read `client\ssl_crash_dump\*.ssldmp` first.
20. **New model spawns with gore caps showing and can't be dismembered.** **Cause:** no `ecsGoreTplLib`/`gorePools` rows
    for its tpl, then no level-customizer template row (the template is what hides the caps). **Fix:** all three, in
    every customizer section, with layers naming your objects.
21. **Hand-built NPC bank completely silent although it parses.** **Cause:** HIRC objects not written children-first, so
    containers and events linked to nothing. **Fix:** retail order (sounds, containers, mixers bottom-up, actions,
    events); simulate the load and count empty containers.
22. **Ported NPC blends from lying on the floor straight into running.** **Cause:** reaction exit event 205 copied from
    the host's timing. **Fix:** move 205 to where the body has settled (never earlier).
23. **Hit reaction teleports the body to a kneel.** **Cause:** 0 s entry blends show frame 0 at once. **Fix:** start
    reaction clips standing or prepend a transition reel.
24. **Ported strikes whiff, one with the back turned.** **Cause:** imported hit timing; SM2 hits are geometric at the
    constraint end. **Fix:** measure the sweep at the constraint end, set 405 there, set `ConstraintOffset`.
25. **Retargeted creature walks with bent legs / wrong gait gates.** **Cause:** LegIK stores the host's leg lengths; LOCO
    gates on the host's exact speeds. **Fix:** disable the LegIK threshold; re-point speed conditions.
26. **New clips lose events or end at the wrong time.** **Cause:** anim nodes cache per-clip duration and track hashes.
    **Fix:** retail track list, fresh GUIDs, patch durations/hashes in your set's blocks.
27. **Sit/walk-in sequence plays on the spot.** **Cause:** sequences and emotes apply no root motion, and attaching inside
    an emote does not move the player. **Fix:** a usable + level sequence that attaches the initiator to a scene bone.
28. **Boss legs can't be hit in melee.** **Cause:** the server body is a small scaled pillar. **Fix:** `geom_server
    nameTpl` = the real model.
29. **Boss spams its retail volley after adding a close-range branch.** **Cause:** the branch sat under a top-priority
    utility monitor with an ON_SUCCESS cooldown, restarting the volley. **Fix:** put it under approach/walking and gate
    the volley by distance.
30. **Boss idles for long stretches in a test arena.** **Cause:** the walk fallback needs level `MovementPoints` and
    waits 6.5-13 s. **Fix (untested):** explicit move-to-position arcs between attacks.
31. **New creature moves rejected as rough.** **Cause:** offset keyframes on chains, joints past retail ranges, added
    tremble, overshoot. **Fix:** build on retail clips or path-driven IK capped to retail ranges; show 3-5 moves first.

## Assets
The boss mesh was AI-generated (Tripo) and repainted by the human in Substance Painter; motion is the retail
creatures' own clips retargeted offline; eyes/teeth are retail parts reused by material name. Nothing from the game
is attached to this note. Saber's mod rules forbid AI-generated content in mods (see the foundations note's Setup),
so keep builds with the AI-generated boss private.

## Open questions
- Wiring retargeted cross-creature moves into AI behaviour (kata trees, smarts) for a new boss.
- Whether new interplay sequences work once registered globally.
- Decoding the remaining cinematic `.sani` compression ids.
- Whether the official `noSsl` CLS route makes the modder slots fully obsolete for complex bosses.
- Whether a parriable boss strike works through the NPC melee-desc route on a 45 m creature.
- Whether new interplay sequences can move the player inside an emote at all (only usables did).
