---
kind: game
title: "Space Marine 2 Battle Barge hub: replacing the hero Thunderhawk, a walk-in ramp with push-button seats, the launch countdown, hidden collision and usables"
game: "Warhammer 40,000: Space Marine 2"
games_also: []
game_version: "Steam build 25799387 (Patch 15.1, Oct 2026). Mod Tools app 3856330 build 25506153"
platform: windows
engine: unknown
route: data
tools: ["Saber SM2 Mod Tools (ModelConverter, UsfExporter)", "Python 3 (struct, zipfile, numpy)", "own cd_list / class_list / dom_list / lwi_container codecs", "own .sani clip codec and Morpheme .nmb patcher", "own sslbin disassembler", "Blender (offline preview renders)"]
anti_cheat: "EasyAntiCheat. Everything here uses Saber's official mods folder (client_pc/root/mods), which flags the session 'Mods Detected' (private lobbies, separate progression). No injection, no EAC interaction, PvE only."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-29
links: []
tags: [space-marine-2, saber, hub, battle-barge, thunderhawk, vehicle, usable, level-sequence, xseq, smart, collision, lwi, cd-list, dom-list, countdown, textures, banners]
---

# Space Marine 2 Battle Barge hub: replacing the hero Thunderhawk, a walk-in ramp with push-button seats, the launch countdown, hidden collision and usables

> Two weeks of work on Space Marine 2's Battle Barge hub (Oct 2026, Patch 15.1): the parked hero Thunderhawk was
> replaced by a repainted retail Corvus Blackstar model with an opening rear ramp and a troop bay, players walk up the
> ramp, press Use to sit, and the operation launches once everyone is seated, with take-off lights, sound and smoke.
> Along the way we mapped where the hub's invisible walls really come from, how its ready zone and countdown work,
> and a recipe for "press Use, walk to a spot, play a sequence on the player". The seats, the launch flow, the ship
> on the pad centre and the collision fixes were played and approved in game; items marked otherwise were not.

Builds on [the foundations note](sm2-modding-foundations-paks-tools-and-crash-triage.md) (paks, manifests, crash
triage), [the models note](sm2-models-tpl-format-modelconverter-and-textures.md) (tpl export, `.cdt` collision,
locators, bind poses), [the map note](sm2-building-a-new-map-with-the-map-converter.md) (lwi, dom_list and hub
collision-box formats) and [the missions note](sm2-missions-scenarios-faction-swaps-and-esd-spawning.md) (cd_list /
class_list formats, per-level class swaps, the 12-player flag that splits the hub barge). Morpheme network patching
is in [the weapons note](sm2-weapons-skins-reloads-perks-vfx-and-sounds.md) and
[the NPC note](sm2-new-enemies-npc-classes-and-morpheme-animation.md).

## Setup
- Steam build 25799387 (Patch 15.1). Hub level: `scenes/hub_battle_barge.scn/` inside the client and server scene
  paks (`<game>/client_pc/root/paks/client/default/scenes/hub_battle_barge.pak` and the server equivalent): client
  and server `.cd_list` / `.class_list` / `.dom_list`, one `.lwi_container`, `.lg` / `.lg_data` / `.cdt` and
  `hub_battle_barge.scn.resource`. The hub's client and server scenario graphs are plain-text `.sso` in
  `default_other.pak` (`xscenes/`), like every level's.
- The loading/travel cutscene is its own scene: `scenes/loading_scene.scn` in `client/default/scenes/loading_scene.pak`.
- All edits ship in ZIP_STORED mod paks in `client_pc/root/mods/`; nothing is injected. Paks were swapped only with
  the game closed.
- Oracle: load the hub, walk it, record a short video. Every "invisible wall" report came with a screenshot or sketch
  of where the player stopped; that position, measured in ship coordinates, is what finally pinned each source.

## Route and why
Data route only. The hub is a level, so the work is level-file edits (same-length text edits and appended entities
in the cd_list, `nameTpl` edits in the class_list, instance edits in the lwi container, ready-zone triangles in the
dom_list), scenario-graph edits, new `.xseq` sequences with their clips, and one Morpheme network extension for the
seat animations.
- A custom-rigged replacement hull crashed in vertex-buffer binding; a static model on a root-attached part of the
  retail rig worked (models note). So the retail Thunderhawk rig, animations and logic stay; only what is drawn changes.
- Scenario-started emotes cannot seat a player (no root motion, no attach), and a global emote override broke every
  emote in the game. A usable that plays a level sequence (recipe below) is the route that worked.
- Retail compiled code can't be replaced (foundations note), so every behaviour change is graph data.

## How the game works (what we had to learn)

### Hub level files
The [map note](sm2-building-a-new-map-with-the-map-converter.md) ("Hub scene edits", "Instancing and the lwi
container") has the formats: floors, pads, railings and crates are lightweight instances in the `.lwi_container`
(hide one by setting its y to -100), trigger zones are world-space triangles in the `.dom_list`, prefab props are
flattened into `<prop>__<part>` entries. What the hub work added:
- The hub `.lg` has no floor near the pads. To map the walkable deck, rasterise the up-facing faces of the deck-module
  tpls the lwi container places (landing pads, hangar floor pieces). A height map built from all scenery was polluted
  by cloud planes, far-plane columns, barrels, cranes and ceiling panels.
- Hub cd_list entity records are text (`{name = "|x|...";matr = [16 floats] ... __type ...}`); same-length edits keep
  the file valid. Stage-container children live in that text part; some top-level instances (the ready-zone domain)
  keep binary matrices. A scanner that follows only one record layout found 4,570 of the hub's 13,338 entries.
- Filter clutter by tpl prefix (`refrt_` = level prop), not by name: a "skip anything named thunderhawk" rule kept the
  Thunderhawk cargo crates in the way.

### Which Thunderhawk is which
- `imp_thunderhawk_01__actor` is the loading-scene / story-intro ship with a baked interior. The flying, hangar,
  mission and cutscene ship is the prefab `thunderhawk_body` (293-bone rig, 25 TPL animations, ~290 attached part and
  interior actors), baked into EVERY level's class_list as `<level>__thunderhawk__x__*`,
  `<level>__thunderhawk_interior__x__*` and `<level>__thunderhawk_stationary__x__*`. Its scripted logic is the global
  `scripted_vhc_thunderhawk.cls`; levels store only variables. Never blank a shared Thunderhawk tpl globally: the
  loading scene uses a static copy of the same prefab.
- The hub has 9 hero ships: 3 parked plus 6 interplay ships. **Interplay ships sit at the world origin and their clips
  carry world-space `root_jnt` motion.** The ship parked by the mission box is the arrival / tactical-team interplay
  ship held in static "right pad" clips (landing loop, ready, idle, engine); to move or turn the parked hero, edit
  `root_jnt` in those clips, not a matrix. `cinematics__thunderhawks__cont_*` are cutscene ships. All hub Thunderhawks
  instance one class, `hub_battle_barge__thunderhawk`, so hub-only bone edits (a door bone the retail hub never
  animates) break no other level.
- Background ships: a container of low-res instances (`refrt_imp_thunderhawk_01_fp`) and three flyby interplays that
  spawn `refrt_imp_thunderhawk_01_lr`. A same-length `nameTpl` swap to the locator-only `thunderhawk_root_trajectory`
  removes them.
- Effects: the prefab actor `thunderhawk_effects` (on `root_jnt`) is the Thunderhawk VFX source; its jets and lamps sit
  on locators in the geometry-less tpl `sfx_thunderhawk_locators` (matrices are two 64-byte-per-object arrays). Each
  level also has ~31 static steam / idle-jet `sfx_entity` classes around the ship (empty their `list` to remove them),
  and cutscenes / interplays spawn their own VFX source in the `.xseq` `spawnableActors`, so a locator copy must be
  pointed at from those too.
- Parts are placed in their cd_list ENTITY frame, not their bone's rest frame (map note). On the Thunderhawk the
  left foot's two frames agree, but the right foot's bone rest is the entity frame turned 180 deg about X, so a ramp
  modelled in the bone rest was drawn flipped, metres under the floor. The 6 hub interplay ships (their containers
  store world matrices) make a good test of any bone-attached part.
- The game poses prefab bones from the RETAIL rest pose; the first animation slot is an interpolated pose and every
  TPL clip is additive (a delta from its frame 0). Parked ships with no clip show the retail rest, so the Thunderhawk's
  legs-up foot pose (21.3 deg rolled, 3.5 m up) is what a parked ship shows. Extra geometry riding a bone (landing
  gear on the left-foot part, a rear ramp on the right-foot part, a ramp lip on an unused door bone) needs every clip
  that moves that bone re-authored. The Thunderhawk's own front ramp is skinned (no part on its door bone), so the
  new ramp needed another animated part as carrier.

### Where the invisible walls around a prefab Thunderhawk come from
Nine builds chased one "invisible box" in front of the turned ship. Each guess hit a real collision source, just not
the one in the way. The full list, as found:
1. The body class's keyframed physics (`prop_phys_system` with `*_glr` shapes from the tpl markup), which turns with
   the ship.
2. `geom.cdtSkeleton` on the body class (movement collision of a skinned prefab, see the models note).
3. The level's own fence: an `.lg` object named `scripting|constrains|...` running round the pad (models note:
   degenerate its faces in `.lg_data`). The hub `.cdt` sections that matter hold only a handful of objects; `.lg`
   objects like `lighting|mesh_cube_cdt_*`, navmesh and fly planes are not player walls.
4. **`thunderhawk_body_collision`**: a separate 5-piece convex model under `phys_body` (its front piece reaches 21 m
   ahead of `root_jnt`, floor to 10.6 m). Three copies follow every prefab Thunderhawk's `root_jnt`, all created from
   GLOBAL classes in `ssl/scene_object/scripted_vehicle/thunderhawk/`: the client driven-part class inherits it as
   `geom.nameTpl`, the client scripted-vehicle logic creates `thunderhawk_body_collision_actor` (Havok keyframed,
   layer `constr_plr_and_ai`) at level init and makes it follow `root_jnt`, and the server driven class does the same.
   No level class_list mentions it. This was the box.
5. Invisible player blockers in the client cd_list (`invisible_player_blocker` cubes, ~92
   `low_res_player_blocker_sphere` per parked ship) and the server-side `server_driven` wing / missile parts (stripping
   those changed nothing).

**Lesson:** when an invisible wall moves with a prefab, resolve every class's `__type` chain down to the global `.cls`
and grep those for `CreateActor` and `nameTpl`; an audit of the level class_list alone reports such parts as "no tpl".

**Refitting a collision model without exporting:** ship only `.tpl` + `.tpl_data` at retail size with new numbers.
Positions are int16 per split (q / 32767 x scale + offset; the six int16 offsets sit in the splits sub-chunk), and the
84-byte GeometryData box + OBB and the model box near the start of the `.tpl` must be rewritten to match. The retail
`.cdt` is MOPP code over the OLD triangles, so moved triangles stop counting for `.cdt` movement checks, while the Havok
shapes follow the new vertices.

**The hub refines the models note's ".cdt, not Havok" rule (2026-10-15):** in the hub, players walked through walls
in a hull's `.cdt` hit mesh but were stopped by the same hull's keyframed physics markup boxes, and the refitted Havok
collision pieces above blocked them too. The map note gives the box recipe. From the ship:
- Axis-aligned boxes were enough: stairs for a slope, overlapping 1.2 m boxes every 0.8 m for a diagonal wall. Risers
  of 0.22 m are fine (the marine's max step height is 0.5 m). Boxes are written into the hull's markup at package
  time, so a collision change needs only a repack, not a re-export.
- A box that hangs lower than the visible hull reads as an invisible wall; derive boxes from the visible surface
  (0.4 m cells worked).
- A collision refit made for a closed hull becomes a wall the day the model gains walk space (the old prisms filled
  the new troop bay for nine builds). Run a capsule walk test whenever walkable geometry changes.

### The hub launch flow
- **Ramp state machine (client scenario -> arrival `.xseq` sections):** `hng_thunderhawk_open` -> `ready_in` (6.7 s),
  `door_loop` -> `ready_loop`, `wait` -> `engine_idle`, `ignite` -> `engine_start` (3.33 s retail), `ig_loop` ->
  `engine_loop`. Sections play from the markers of the FIRST actor tagged `hng_thunderhawk`
  (`PlayLevelSequenceSections`, `needFinishPreviousSection = True`).
- Retail sets `hng_thunderhawk_ignite` when the gather stage starts, i.e. as soon as a mission is selected (server
  hub scenario: gather-in-ready-zone stage -> state update), and nothing reopens the ramp on deselect. Tie anything to
  ignite and you must cut that link.
- **Ready zone = the dom_list** (format in the map note). Moving the client domain entity or the hidden "visual
  placeholder" cubes does not move it; reshape its triangles in BOTH hub dom_lists. The client copy drives the native
  countdown, the server copy the ready state (marker glow, hub stage).
- **The countdown starts when every player is inside the ready domain AND the zone is "available"** (client
  `DomainBasedReadyStatusSetter`: mission selected and the hub data says the zone is available; it re-reads the
  domain's occupants on change). Retail switches availability on in one place, from the gather stage. Drop that link
  and drive `BlueprintNodeHubReadyZoneAvailability` (`isAvailableRef`) yourself to start the native ~5 s countdown
  exactly when you want (we wait until every player has been seated for 3 s).
- **Departure:** retail hides the arrival-sequence hero via `StartCinematic departure_*` -> a pipe that resets the ship
  states -> client `ResetLevelSequence`. A custom graph that sets ship states after that reset re-shows the parked
  hero, so two ships appear at take-off. Latch your logic off on the same departure pipe.
- The stock PvE mission start (inside missions, not the hub) is server `SubscribeToDomainEvents` on
  `Thunderhawk_start_sequence_domain` -> `OnLeave` -> actors in domain = 0 -> `ChangeScenarioState
  thawk_start_takeoff`; the client plays the tagged `*_start_loc_*` level-sequence prefabs. Retail end-of-level ship
  sequences carry nobody.

### The ASSEMBLE marker and the countdown beeps
- The "ASSEMBLE" waypoint is the hub server scenario's `AddPathMarkerByDomain` (domain `ld_hangar`, highlight preset
  `ObjectiveAssemble`) marking the actor spawned by `|x|scripting__objective_markers__gather_near_thunderhawk_marker`
  (an `objective_marker_actor_spawner`), which exists only in the hub SERVER cd_list. Move it by editing that entity's
  matrix translation (same length).
- The launch "beep beep" is the player's PvE authority-only sound blueprint
  (`ssl/characters/player/marine/blueprint_marine_authority_only_sounds_pve.sso`): a session-match-timer subscription
  feeds a `SwitchByInt` on the seconds left into `ui_mission_timer_done` / `_odd` / `_even`. Nothing else uses that
  node, so setting its `subscribeOnInitRef` to False silences the countdown with a one-token edit.

### Usables that walk the player to a spot and play a sequence on him
Retail's hub keypads and the armoury use this; it needs only global classes inline in the cd_lists (no class_list edit):
- **Server cd_list:** a `usable_object_server` whose `prop_usable_server.smartEntries` holds a
  `SmartEntryPointBaseServer` with `smartsCollection` = [`SmartHoldableTimerServer {holdTime}`,
  `SmartLevelSequenceServer {flagsMask INTERACTION, HIDE_SIGHT}`], plus `isDeactivateWhileUsing` (default True),
  `isDeactivateOnComplete` (default False; keypads use True), `isUnlockedByDefault` (default True), a tag, and
  `prop_replication_id.id` = the CLIENT usable's name. Add a `level_sequence_actor_server` whose replication id names
  the client sequence actor. The server needs no `.xseq` and no rig.
- **Client cd_list:** a `usable_object_client` (`prop_usable_client`: `levelSequenceActorName`,
  `constraintTargetActorName`, `constraintTargetActorLocatorName` (default `player_position`), smart entries copied
  from the hub keypad, replication id = its own name), a `level_sequence_actor_client` with
  `desc = {type = {__type = "<your xseq brand>"}; __type = "LevelSequenceDesc"}`, and any actors the sequence animates
  (we used a `cc_cinematic_items` carrier rig per seat). Absolute `|x|...` names work in xseq `fullName` and usable fields.
- `holdTime` takes 0 (tap), 0.25, 0.5, 1 (default), 2 or 3. Use radius is 2.5 m from the use locator (the placeholder
  sits 1.5 m above the entity), and the ray from the player's neck to it must be clear.
- **Client flow (decompiled):** movement disabled (collisions off) -> walk-to onto the target actor's locator (a missing
  locator skips the walk and starts at once) -> play from marker `interaction` -> the player replaces `#/initiator` ->
  sequence. The global `initiator_detach` event only arms the abort watcher; any abort action (movement) completes the
  use, detaches and re-enables movement. The attach holds until then. No `exit` marker = the interaction ends with its
  section. No camera track = free camera. Bone convention: +z = facing.
- **The `.xseq`** (client-only typemask; manifest = a copy of `usable_keypad.xseq.resource` plus your clip and rig
  links): marker `interaction` at 0; a `#/initiator` track with anim-table sections and an attach-to-object track
  (`attachTo` = the rig's track, `boneName`); the rig track = consecutive standalone animation sections. Copy the
  keypad's `spawnableActors.initiator` block as raw text (re-serialising it turned numbers into quoted strings).
- **Animate the player in the EVENTS slot, never an emote state.** A usable abort resets the anim-table floats to 0,
  and the emote state machine only exits on its stop clip's event 36 or a negative emote value, so the player stays
  stuck in the emote. Retail usables request `Primaris.Usable.*` entries (events process 1, an event destiny, request
  `events_ingame`) into the unarmed state machine; the exit comes from the clip's Footsteps sync track (index 1 plus
  movement input, or 2-3 automatically). The events switch reads a FROZEN destiny, so a reset cannot swap clips
  mid-exit; add your clips by wrapping a child on that freeze node (wrap-in-Switch pattern, weapons note). One clip
  per state you need.
- That slot runs under the unarmed foot IK and hand IK, so seat clips must keep the IK helper joints on the hands and
  feet as retail clips do, or a hand reaches out into the air.
- **Re-use:** set `isFinishIntroSection = false` on `SmartLevelSequenceServer`. With the default True the next use
  waits for the previous sequence to stop, and an aborted use leaves it running, so the second user is stuck with
  movement disabled.
- **Lock a seated player** (camera free, no standing up): client scenario on a server state update ->
  `BlueprintNodeEnableDisablePlayerControls` True (filter rule `scenario_no_control`: only rotation passes), False to
  release. The rule clears itself when the doll leaves the level.
- **Armed levels:** that events slot is the UNARMED one. An armed marine's request goes to the armed events switch,
  where the same destiny is the stock keypad press, so he presses a keypad and then glides along the carrier. Data-only
  fix: make him unarmed before he can reach the usable with server `BlueprintNodeActivateDeactivateUnarmedMode`
  from a position check (retail hub and story levels use it); switching on use races the tap usable's request.
  Not yet confirmed in game.
- Sit clip source: retail `animation/interplay/battle_barge/tacticus/tacticus_stand_up_tired_intercessor` played
  backwards is a turn-and-sit followed by a seated hold. When you blend two clips whose root frames differ, express
  both in one frame first; slerping root and centre separately made the seated marine jiggle.

### Smart types when a scenario starts them (decompiled)
- `BlueprintNodeEnterSmart` (server) builds the smart from `smartDesc` and enters it with no parameters.
  `BlueprintNodeLeaveSmart` ends it; no character command interrupts a smart.
- A scenario-started **`SmartEmoteServer`** behaves like a wheel emote: uncancellable intro, the `loop` marker section
  repeats (`loopCount` 0 = until exit), movement plays the `outro` section, fire / zoom / dodge force-exit with the
  abort animation, the actor track is `#/target`, and it plays at the actor's current transform (teleport first). It
  never moves the player.
- **`SmartInteractionServer`** binds the user to `#/initiator` and plays straight through; the generic abort only
  completes it; `startActorTag` works (tagged locators only need to exist in the SERVER cd_list); the user collides
  `geom_only` meanwhile.
- `SmartInteractionConstraintParams` (walk-to) needs a usable entry-point owner and null-derefs on the client without
  one, so a scenario cannot use it: that is why the seats are usables.

### The travel cutscene's Thunderhawk
- `scenes/loading_scene.scn` plays seated-character clips (`animation/cinematics/loading_screen/shot_01/...char_*`);
  no Thunderhawk clip. Cameras: `cinematics__camera`, `cam_preview_char_a/b/c` (matrix row 2 = look direction).
- Its cd_list is binary: 64-byte header, u32 count, u32 0xA, u8 1, then count x (i32 length + name), 2 bytes, then
  count x 64-byte row-vector matrices. `geometry__thunderhawk_stationary` sits at the origin, so the matrices are
  already in the Thunderhawk `root_jnt` frame and its seat rows match the hub interior's numbers.
- Its interior has 4 seats a side, each under a restraint harness (`refrt_imp_thunderhawk_seat_holder_02`) on the
  `l/r_seat0N_jnt1` bones, plus wall dressing the hub interior lacks. Seat tpls hold 4 LOD splits each. Two decode
  traps: `thunderhawk_body_interior`'s visible mesh and `refrt_imp_engine_01`'s LOD0 are object-local and land metres
  off unless offset.
- The loading-screen roster and its 3-seat cap are covered in the missions note.

### Lights, sounds and smoke in the arrival sequence; retiming a section
- Take-off effects were added as rows of the hero's arrival `.xseq`: retail sound events (a steam-valve release, the
  ramp door motor, jet start, an elevator-stop "kerchunk" as the ramp shuts) and `sfx_entity` actors with active
  tracks: strip and room lights cloned from `fx_thunderhawk_belly_spots`, and smoke emitters copied from a retail
  smoke particle effect with a constant flow. No sound bank was edited.
- **`ig_loop` may replay the `engine_loop` section.** Every sound row must end before that section or span all of it,
  or it re-triggers on each loop (~1.5 s).
- `xc_section_animation` has `speed`, `loop` (default True), `useDurationFromAnimation` (default True) and
  `playSegment`, but `speed` != 1 is unused in retail. To slow the ramp we stretched the clip itself (own name + own
  `.sani.resource`) and shifted every later time / marker in the xseq by the added length. Spinning parts flip 180 deg
  per frame in some Thunderhawk clips; leave them out of any interpolation check.

### Repainting a hub vehicle and the hub banners
- The retail Corvus Blackstar exists only as a crash-site model (`refrt_imp_corvus_blackstar_destroyed_01`, left side
  intact) plus intact low-res and rear-ramp pieces; mirroring the intact side repaired it. Its crash damage is
  sculpted into the high-poly bake: craters and gashes in the AO, pitting in the normal map; rivets often exist only
  in the normal map. Filling AO cavities filled whole outlined plates.
- Decide paint masks per triangle sample, not per texel's mean 3D position: shared UVs otherwise paint stray stripes.
  When two surfaces share texels (both wing bands, side and underside stripes), re-map the faces you want different
  onto other texels of the same atlas, or put text on its own alpha-kill decal sheet a few mm above the skin (far
  LODs need more lift: 4 / 8 / 15 mm worked).
- **Flat full-metal decals (lettering, plaques) mirror the dark hangar and read DARK in game**, while an offline render
  shows them silver even with a near-black sky. Judge metal decals from in-game shots; dial metalness down.
- A one-sided part seen from behind (the ramp's outer skin, its rims) is see-through: add an inner plate, and back
  copies of rim faces (reversed winding, normal and tangent w negated). A part cut 1 cm under a floor whose material
  has parallax still showed through as a dark ring; 13 cm cleared it.
- ModelConverter's glTF of one retail weapon had half its triangles wound against their normals (strip parity), and
  the weapon rendered black once re-exported; re-wind each triangle to agree with its normals. A retail weapon's own
  LOD2 carried a black triangle, so pick display LODs by eye.
- **Hub banners:** `bb_flag_long_01/02_cloth` use `imp_flags_05`, `bb_flag_long_03_cloth` `imp_flags_04`,
  `imp_flag_long_03/04/05` `imp_flags_07`, `imp_flag_short_02` `imp_flags_01` (also used by about ten missions),
  the idle intercessor's banner `ch_banner_01`, Mechanicus flags `imp_flags_06`. A repaint can ship as retail-named
  `_N.pct_mip` files only (keep the retail alpha silhouette and normal map, rebuild spec). Built and decoded, not yet
  seen in game.

### Several mods on one hub
The hub cd_list, lg_data, dom_lists and lwi container are each winner-takes-all, and several of our hub mods changed
them (ship and seats, a pad move, a separate hub-room project, a throne). What worked:
- Layer them: each mod's copy is built on the copy of the mod below it, sorts first, and is rebuilt whenever the lower
  one changes. Removing the lower pak alone leaves the upper one's cd_list naming classes and tpls that no longer
  exist (expect a crash): swap both in one step.
- Never build a layer on an already-merged pak: a "move by delta" edit then applies twice.
- Moving a set piece (the parked ship onto the pad centre) touched every file holding its world position: the static
  pad clips' root, seat entities in the client and server cd_lists, the ASSEMBLE marker, the ready-zone triangles in
  both dom_lists, the sequence actors, AND hard-coded seat positions inside the server scenario graph (missed at first,
  which broke the seated check).
- Two mods hooking the same smart events interfere: a throne mod's "hide weapons when a seat use starts within 3 m"
  chain ran at the start of every Corvus sit and the sit never played. And a long chain of nodes run in series in one
  frame inside a smart's enter overflowed the script stack (a 5 s freeze); running the chains in parallel cut the
  same-frame depth from about 300 to about 30.

## Build steps
Replace a vehicle model on the hub (and in missions):
1. Keep the retail rig. Export the new hull as a static tpl, attach it to an identity `root_jnt` part (we used the
   ship's windows part), hide the body's rendered objects by runtime name (`ROOT` for unnamed skinned objects), point
   other part classes at a locator-only tpl, and add `linksTpl` to each `<level>.scn.resource` (missions note).
2. Ship a renamed copy of the effect-locator tpl and point the level classes and every xseq VFX source at it.
3. Refit `thunderhawk_body_collision` inside the new hull, strip the body physics / `cdtSkeleton`, degenerate the pad
   fence faces, add markup physics boxes for anything walkable. Capsule-walk test.
4. Turn or move the parked hero through `root_jnt` of the static pad clips; re-author every clip that poses a bone
   carrying new parts (build them in the retail rest pose and the cd_list entity frame).
5. Custom maps that clone a level keep the base level's FILE names (class_list, scn.resource): patch their copies too,
   in a pak that sorts before them.

Push-button seats that launch the operation:
1. Per seat: server + client usable and sequence-actor entities, a carrier rig, a client-only `.xseq` (recipe above);
   seat clips in the unarmed events slot with IK helper joints; `isFinishIntroSection = false`.
2. Reshape the ready zone in both dom_lists; move the ASSEMBLE marker in the server cd_list.
3. Server scenario: occupancy per seat, cut the retail gather-stage ignite and zone-availability links, drive
   `HubReadyZoneAvailability` after everyone is seated for a few seconds, latch off on the departure pipe.
4. Client scenario: lock controls while the ramp closes; optional silence of the countdown beeps.

## Verification
- In game and approved: the Corvus in the hub and in mission cutscenes, the pad-centre move, the wall pass round the
  pad, walking up the ramp into the bay, the push-button sit / stand / re-sit, the 3 s pause then the native 5 s
  countdown and take-off with the ramp closing, the bay lights and the ramp lip, the seat fix after the throne
  conflict, and the throne sit after flattening its chains. The `thunderhawk_body_collision` refit was confirmed by
  walking where the box had been.
- Offline: cd_list / class_list / dom_list / lwi round trips, a capsule walk test over the physics boxes, renders from
  the travel-scene cameras, per-pak checks that every shipped file was built on the copy the game currently loads.
- Not verified: the armed-level unarmed-mode fix, the banner repaint, whether the hub floor behind the ship has its own
  collision, the seat lock on its own (it sits in the approved build but was never tested in isolation), and whether
  the take-off smoke reads well (not commented on).

## Gotchas
1. **Invisible box in front of a turned or replaced Thunderhawk, surviving every physics edit.** Cause: the global
   `thunderhawk_body_collision` actor three classes create at level init and pin to `root_jnt`. Fix: refit that model
   inside the new hull (same-size tpl edit); trace walls through the global `.cls` chain.
2. **Players walk through a new hull's `.cdt` hit mesh in the hub, yet hit an invisible wall on the ramp.** Cause: in
   the hub the keyframed Havok physics boxes are what block; one filled the troop bay. Fix: build walk space and walls
   as markup boxes; keep them inside visible geometry.
3. **Invisible wall appears the build after a model gains a bay or ramp.** Cause: an old collision refit made for the
   closed hull. Fix: re-fit to the solid parts only; capsule-walk every build that changes walkable geometry.
4. **New ramp missing ("no ramp") though its clips play.** Cause: modelled in the mirrored bone rest instead of the
   part's cd_list entity frame. Fix: part world = bone world x inverse(bone rest) x entity matrix.
5. **Parked ships show gear up; patched bind pose ignored.** Cause: parked ships play no clip and the game uses the
   retail rest pose. Fix: build for the retail rest; drive poses through clips.
6. **Picking a mission closes the ramp.** Cause: retail sets the ignite state when the gather stage starts. Fix: cut
   that link in the hub server scenario.
7. **Hub ships vanished after editing interplay sequences.** Cause: a duplicate `properties` key in the edited `.xseq`
   files; the interplays failed to load. Fix: check for duplicate keys after every xseq edit.
8. **Scenario-started seat emote plays on the spot and never seats the player.** Cause: emotes have no root motion and
   ignore attaches. Fix: a usable with a level sequence. And never ship a global emote override: it broke every emote.
9. **Standing up leaves the marine stuck in a kneel emote.** Cause: seat animations ran in an emote state, which a
   usable abort cannot exit. Fix: the events slot.
10. **Sit -> stand -> sit again locks the player.** Cause: `isFinishIntroSection` True waits for the previous (aborted,
    still running) sequence. Fix: False.
11. **Seated pose wrong: a hand held out, leaning.** Cause: the events slot runs under hand / foot IK and the clip lacked
    IK helper joints. Fix: keep them pinned like retail.
12. **Two ships at take-off.** Cause: custom logic set ship states after retail's departure reset. Fix: latch off on the
    departure pipe.
13. **ASSEMBLE waypoint stays where the old ready box was.** Cause: it marks a server-only marker spawner, not the
    domain. Fix: move that entity's matrix in the server cd_list; reshape the ready zone in the dom_lists.
14. **Take-off sounds repeat every ~1.5 s.** Cause: `ig_loop` replays `engine_loop`; rows straddling its start re-fire.
    Fix: end rows before the section or span it.
15. **Prompt appears, no sit animation, then take-off.** Cause: another mod's scenario ran a hide chain on every seat
    use within 3 m. Fix: find every graph subscribing to the same smart events; disable the overlap.
16. **5 s freeze entering a seat.** Cause: long serial chains in one frame inside a smart enter overflowed the script
    stack. Fix: run them in parallel.
17. **Lettering and plaques look black in game, silver in previews.** Cause: flat full-metal surfaces reflect the dark
    hangar. Fix: lower metalness; judge from in-game shots.
18. **A re-exported retail weapon renders black.** Cause: half its triangles wound against their normals in the
    converter's glTF. Fix: re-wind by normal.
19. **Dark ring on the floor over a part cut just under it.** Cause: the floor's parallax shows geometry a few cm below.
    Fix: cut deeper (13 cm).
20. **Moved set piece, but the seated check broke.** Cause: positions hard-coded in the server scenario graph were not
    moved with the entities. Fix: list every file with world coordinates for the piece, graphs included.

## Assets
All geometry and textures are retail game assets, recoloured or re-arranged inside the game's own files: the Corvus
crash model repaired by mirroring, the Deathwatch emblem taken from a retail rifle mesh, seats and harnesses from the
Thunderhawk interior, retail sound events and particle effects. Lettering used a system font. The banner artwork was
supplied by the mod author. Nothing from the game is in this note.

## Open questions
- Whether the hub floor behind the pad has collision of its own (the `.lg` has no floor there).
- A data path to a 4th seat in the loading-scene Thunderhawk (needs cd_list tracks and new seated clips).
- Whether the armed-level unarmed-mode switch is enough for seat usables in combat levels.
