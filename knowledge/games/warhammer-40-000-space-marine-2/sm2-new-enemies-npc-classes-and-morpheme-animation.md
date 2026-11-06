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
date: 2026-10-15
links: []
tags: [space-marine-2, saber, npc, enemy, boss, tyranid, morpheme, nmb, sani, animation, retarget, finisher, execution, interplay, xseq, spawning]
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
> unless marked.

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
