---
kind: game
title: "Space Marine 2 missions: scenario faction swaps, level files, the ESD spawn director and rebaking a navmesh with spawn points"
game: "Warhammer 40,000: Space Marine 2"
games_also: []
game_version: "Steam build 25799387 (Patch 15.1, Oct 2026); faction swap on Patch 14.x (Sep 2026). Mod Tools app 3856330 build 25506153 (AIConverter, Furnace, MapBuilder)"
platform: windows
engine: unknown
route: data
tools: ["Saber SM2 Mod Tools (ModEditor, AIConverterExe, furnace.exe, ModelConverter --map_mode)", "Python 3 (struct, zipfile)", "own cd_list / class_list readers-writers (ports of Saber's shipped C# source)", "own ctypes debugger for Saber's offline tools", "own sslbin disassembler"]
anti_cheat: "EasyAntiCheat. Everything here uses Saber's official mods folder (client_pc/root/mods), which flags the session 'Mods Detected' (private lobbies, separate progression). No injection, no EAC interaction, PvE only. The debugger was only ever attached to Saber's offline converters, never the game."
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-13
links: []
tags: [space-marine-2, saber, scenario, mission, faction-swap, tyranids, chaos, esd, spawn-director, navmesh, aiconverter, furnace, cd-list, class-list, level, lobby]
---

# Space Marine 2 missions: scenario faction swaps, level files, the ESD spawn director and rebaking a navmesh with spawn points

> Mission-level modding in Space Marine 2: swapping a mission stage's enemies from Chaos to Tyranids (working in
> game), turning the campaign prologue into a PvE operation with the stock enemy spawn director (in progress: the map
> plays, the navmesh was rebuilt with 388 spawn points, enemies from the director not yet seen),
> per-level vehicle swaps, and why the 12-player flag splits the hub barge. Builds on
> [the foundations note](sm2-modding-foundations-paks-tools-and-crash-triage.md) (scenario manifest rules, blueprint
> pin and value rules, crash triage); level collision and models are in
> [the models note](sm2-models-tpl-format-modelconverter-and-textures.md).

## Setup
- Steam build 25799387 (Patch 15.1). Scenario text in `default_other.pak` (`xscenes/<level>/<level>_scenario_server.sso`
  and `_client.sso`); level binaries in per-level scene paks (`paks/client/default/scenes/<level>.pak` and the server
  equivalent) under `scenes/<level>.scn/`.
- Saber Mod Tools with the documented toolchain layout (the package extracted into the game's `client_pc/root`, or
  a mirror of that layout elsewhere with junctions to the game paks) for AIConverter / Furnace / MapBuilder.
- `meta_desc_ssl.ps` for every node's pins and the on-screen debug node `BlueprintNodeDrawModUiLog`: see the
  foundations note.
- Saber's own Map Converter / Furnace pages (spacemarine2-modding.prismray.io) cover building NEW levels from glTF;
  this note works on existing levels.

## Route and why
Data route: scenario graphs are plain text and can be edited freely as long as every node type is declared and every
link targets a real pin. Level data (entities, classes, navmesh, static geometry) is binary, but Saber ships the C#
source of its scene readers/writers, so cd_list / class_list can be rewritten byte-exactly. A level's scenario logic is
a compiled module, so a cloned level cannot get its own scenario; modded levels branch inside the original level's
scenario.

## How the game works (what we had to learn)

### Scenario waves and faction swaps
- Waves are `GetCustomEnemyPackComposition` blocks: `archetypeN` (`AiArchetypeRefParam`) + `amountN`. Valid archetype
  names live in `ssl/spawn_system/archetypes/archetypes_library.sso`, grouped `NPC_TYRANIDS` / `NPC_CHAOS` /
  `NPC_LOYALIST`, each with `threatClass`, `powerRating`, `combatType`: match those when swapping to keep pacing.
  Omitting `amountN` while keeping `archetypeN` is a normal retail idiom (~43 % of compositions).
- **The pool table is the must-do.** Each `*_scenario_server.sso` ends with `useDefaultArchetypesPoolsLibrary = False`
  and an `archetypes = { ... }` table of `LevelArchetype` entries (`amount = N` concurrent pool, or `takeDefault =
  True`, plus the `npc_*_server` class). A level can only spawn archetypes listed there, and each needs its class in
  the scenario manifest's `linksDescWeak`. Size `amount` for peak simultaneous demand, not one wave.
- `spawnVisTypeRef` (`CHAOS_PORTAL` / `TYRANID_SPOROCYST` / `VR_PORTAL`) is cosmetic; it does not gate archetypes.
  Portals, swarms (`BlueprintNodeStartSwarm` `spawnerTagRef`) and flocks are LEVEL actors: you can change what walks
  out of a portal, not the portal.
- `BlueprintNodeGetCharactersByArchetypeUid` finds spawned enemies BY ARCHETYPE NAME for scripted beats; retarget those
  lookups when you swap, or the array is empty and the beat silently dies. `Chs*Dummy` / `Tyr*Dummy` are invisible AI
  targets; leave them.
- Mixed factions in one level are supported (several retail levels do it), but assets stream per level: prefer
  archetypes that already appear in some campaign mission.
- Worked example (one stage of a Chaos mission -> Tyranids, 61 references): Cultist -> Termagant, Tzaangor ->
  Hormagaunt Sergeant, shieldless Tzaangor -> Hormagaunt, Rubric Marine -> Warrior (assault), flamer Rubric -> Warrior
  (whip), Occult Terminator ranged -> Zoanthrope, melee -> Ravener, lesser Sorcerer -> Zoanthrope; gaunt counts doubled
  to offset their much lower power rating; seven pool entries appended. Played fine; Tyranids walking out of warp
  portals is the accepted cosmetic cost.

### Level files
- Per level: `.cd_list` (entities: name, row-major 4x4 matrix with translation at elements 12-14, affixes, a
  descriptor text, parent index/object, flags), `.class_list` (64-byte header, u32 count, u32, u8, the names, u8, then
  each descriptor as u32 length + text; nothing after it, so it can be resized), `.dom_list`, `.lg` + `.lg_data`
  (static geometry, GeomManager-style chunks), `.cdt` (static collision, see the models note), `.nav` (navmesh; the
  same file is in the client and server scene paks), `lwi_container` (instanced props), terrain. Client and server
  have their own cd_list and class_list (spawn points and `server_driven` physics parts are server-side).
- Invisible walls come from two places: static-collision objects in the `.lg` named `scripting|constrains|...`,
  `*_playable_zone` and camera constraints (removing one: see the models note's level collision), and scripted 1x1 m
  `invisible_player_blocker` entities in the cd_list scaled by their matrix. The navmesh stops at those walls too.
- Saber ships `SaberTools/Scene/CDList.cs`, `ClassList.cs`, `DOMList.cs`, `SaberScene.cs`, `MapConverter.cs` and
  MapBuilder in `ModelConverter/ToolsSource`; a straight port round-trips retail files byte-exactly, and entities can
  be APPENDED.
- Entity descriptors are plain text (`matr`, `__type`, ColorCtrl light colours as A,R,G,B); same-length edits keep a
  file valid without any re-layout. Scene post-FX presets live in `default_presets.pak`
  (`presets/data/<scene>/*.s3dprs`).
- Some binary lists (e.g. `loading_scene.cd_list` records: marker, u32 next-field offset, u32 flag, u32 end offset, u32
  length, text) use ABSOLUTE offsets: resizing one record shifts every later one.
- Per-level class swaps: a vehicle that appears in many levels is baked into each level's class_list as its own
  classes. Swap a model by changing `nameTpl` of the right class in every level's class_list and adding the tpl to
  `linksTpl` of `<level>.scn.resource`. Cutscene copies and interplay ships are separate: `.xseq` files spawn their own
  actors in `spawnableActors` (give them `desc.properties.geom.nameTpl` overrides + a `linksTpl` in the xseq's
  resource). Interplay ships sit at the origin and their clips carry world-space root motion. Class-level
  `objectsOverrides = { <runtime object name> = { isHidden = true } }` (or `transform`) hides or moves parts.
- Do not "clone" a level to get new logic: a cloned level re-homed under a new name still runs the original level's
  compiled scenario. Branch inside the original scenario on `CompareGameModeName "Pve"` and add "Pve" to its
  `startingParameters`.
- New mission-select entries extend the `MissionUid` enum (Saber's enum extension) and the shared missions files;
  several map mods do this, so ship a merged copy of the current winner and sort first.

### The ESD spawn director
- ESD = the enemy spawn director of operations. Pressure presets are in `esd_manager.sso` `basePressureSettings`
  (NORMAL 140 in retail), waves/breathers and swarm cooldowns there too; `ai_spawn_manager` `maxAiCount` (100 by
  default, 150 in story). Influencers: progress spline, players count, difficulty.
- **Spawn points are navmesh inputs.** `ai_dynamic_spawn_point` entities (`__type = "ai_dynamic_spawn_point";`,
  flags 1, aggro / idle / miniboss variants) sit in the SERVER cd_list and are baked into the `.nav`
  (`AiDynamicSpawnPointCreator` only enables points that match targets baked into the level). A campaign level has
  none, so adding points means rebuilding its navmesh (next section).
- **The server scene manifest must link the spawn-point classes**:
  `scenes/<level>.scn/server/<level>_server.scn.resource` (server `resources.pak`) needs
  `ssl/spawn_system/dynamic_spawn/ai_dynamic_spawn_point{,_idle}.{cls,ssc}.resource` and
  `ssl/spawn_system/archetypes/ai_archetype_classes.ssl.resource`, or the server never creates the entities. We then
  added every server-scene link that ALL reference PvE levels share and the target lacks (34 links, e.g.
  `hidden_spawn_table/hidden_spawn_target.ssc`, `float_range`, `dom_players_and_bots_check`,
  `dom_dynamic_spawn_area`), computed as a set intersection at build time.
- **The director starts ON HOLD.** Every retail operation releases it with `BlueprintNodeEsdSetScenarioHoldStage`
  (`stateRef` False). Retail starts only set faction/pack settings (`EsdUpdateFactionAndPackSettings`) and never force
  a stage; forcing a stage left desired pressure at 0. Readouts: `GetEsdWavesBreathersInfo.IsOnHold`,
  `GetEsdPressure` (Desired / Current / Available, server).
- Domain-based packs: `Spawn Npc Pack` (Domain preset) into the level's `enemy_spawn_domains`. On a converted campaign
  level in PvE mode these never produced enemies. Decompiled reasons it can fail silently: the node always fires
  `OnExit`; each spawn request times out after 5 s and then reports "finished" even with zero actors (so `OnSpawned`
  means "requests finished", not "enemies exist"); a domain without a random navmesh tracker yields nothing; the NPC
  limit or an empty pool returns null.
- `ESD: Select Aggro Pack` does not scale with ESD pressure and clamps to pool availability.
- **What always worked:** direct `SpawnActorByArchetype` at a random navmesh point near a squad member
  (`GetRndNavmeshPointInRadius`), with `isIdle True` for idle groups; loop with `ForEachInt` over
  `CreateRandomizedIntArray` (output pin `Get`).

### Rebaking a level's navmesh with spawn points (Saber's offline toolchain)
- `ModEditor/tools/bin/ResourceManager/AIConverterExe.exe` builds a navmesh from the EXISTING scene binaries
  (`--cd-list --class-list --dom-list --geom-dbg --lg --lg-data --lwi-container -o -p <project>`), adds terrain, and
  bakes spawn points. Furnace calls it with an extra `--xgine-link intermediate/.xgine_link` (one line:
  `xgine-scene-path: <map>\<map>.scn`, relative to `mods_source/xscenes`); without a text SCN providing the
  `navmesh_project` object it prints "Skipping navmesh generation". Run from the standalone tools folder it silently
  does nothing: it needs Saber's documented layout (`.project`, prjenv, tools, preload, mods_source, paks).
- **Spawn generation is switched by the SERVER cd_list:** AIConverter reads navmesh settings from the
  `navmesh_project` entity's descriptor. Campaign levels have a bare `__type = "navmesh_project";`; PvE levels have
  `settings = {advanced = {spawnPointsGeneration = {isEnabled = true;};};};` in front of it. With that string the
  rebuild reported our 388 points and ~3,600 total spawn points.
- `-o` must be the scene folder under `<root>/local/scenes/<map>.scn`; copy the level's `terrain/` there (else
  "Invalid terrain version 0 instead of 1"); provide `intermediate/.lwi_container_conv_output` (and `_unresolved`)
  listing the lwi containers and the unique tpl names they use; extract the level's scene paks into `mods_source/`
  (scene-local collision lives there: "there are no collision file").
- Patch-15 tpls with a newer refs sub-chunk are rejected by the tools ("Unknown chunk id: 4"); rewriting it to the
  old form (same size) only took effect in a COPY of the default tpl paks, because a second loader opens the original
  pak entry directly.
- The tools print their real error only through OutputDebugString and then hang on an assert; a small debugger that
  logs debug strings and kills the process after an error report made them usable.
- Cost: ~45 min per rebuild (~25-35 min loading every prop's descriptors in tiny reads, then the navmesh), peak ~23 GB
  commit. Don't rebuild a whole existing level through the Map Converter (scenes can't be decompiled; hundreds of
  thousands of instances and heavy terrain).

### Turning a campaign level into an operation (what else we hit)
- A story "get up" interplay registered in `interplay_controller_default` can be played by any player via
  `EnterSmart`; teleport first, wait ~0.5 s, then EnterSmart (both in one frame fails). Strip camera-cut, game-camera
  and letterbox tracks from the xseq for gameplay use; `SequenceHolsterWeaponTrack` hides weapons (link its module).
- Use `PLAYERS_AND_BOTS` when collecting the squad, or bots miss scripted steps.
- `Delay` nodes stop on node reset; `OnStartedOrReset` fires on start, reset and reload. Chain long sequences from
  independent timers while debugging, with numbered on-screen checkpoints.
- Objective gates: `InteractWithObjectStage`; the default highlight preset's marker has no distance cull (a cloned
  preset with `isCullByDistance` fixes far markers - prepared, not tested).
- Client graph crashes at level load, beyond the foundations note's pin, shipped-node and bare-value rules: a debug
  readout using a node with zero retail client uses (`Vector3dToString`). Prefer nodes retail uses on that side.

### Hub barge and the 12-player flag
- `ssl/main/user/mod_support_consts.sso` `isTwelvePlayerPveLobbyEnabled` is read in five places (decompiled): on the
  client it makes PvE sessions ignore the match's hub data, so each player loads their OWN barge; on the server it
  allows duplicate classes in private sessions and disables class-conflict tracking. The host only publishes its barge
  address when its own flag is off, so "host on, joiners off" can't work, and the flag must be the same on client and
  server. A one-byte edit of the compiled server module to allow duplicates crashed the server at startup (sslbins
  can't be replaced). Data-only fix for a shared barge: flag False.
- The loading-screen Thunderhawk roster is client-side (session members this client knows, duplicate classes dropped
  in compiled code, bots fill to 3); seats are `interplayTracks` in `scenes/loading_scene.pak` `loading_scene.cd_list`
  plus 3 tracks per loading cinematic. The 3-member squad cap is compiled.

## Build steps
Faction swap: rewrite `archetypeN` in the stage's compositions (role/threat matched), fix
`GetCharactersByArchetypeUid` lookups, append `LevelArchetype` pool entries + `linksDescWeak` classes, adjust counts,
ship the scenario `.sso` (+ `.sso.resource`) in a ZIP_STORED pak.

Spawn points on a level without them:
1. Port Saber's CDList code; append `ai_dynamic_spawn_point` entities (per area: aggro / idle / miniboss, anchored on
   the level's own enemy domains and spawn markers) to the SERVER cd_list.
2. Replace the `navmesh_project` descriptor with the PvE one that enables spawn-point generation.
3. Rebuild the `.nav` with AIConverter in Saber's toolchain layout (inputs above), ship the `.nav` + server cd_list.
4. Link the spawn-point classes (and the PvE-shared links) in the server scene manifest.
5. In the scenario: set faction/pack settings, release the hold stage, set pressure; keep direct spawns as a fallback.

## Verification
- In game: the Chaos -> Tyranid stage swap (played through); direct `SpawnActorByArchetype` spawns; the modded
  prologue loads, plays its objectives and the get-up; the rebuilt navmesh (with 388 baked points) loads; the server-side
  pressure / hold readouts work (they showed desired pressure 0 and "ON HOLD", which led to the hold-stage finding);
  the `IntRefParam` and missing-pin crashes.
- Offline: cd_list / class_list byte-exact round trips; the rebuilt `.nav` contains all 388 point names.
- NOT yet seen in game: enemies spawned by the director on the converted level (the hold release was the last fix and
  is untested), the shared-barge fix pak, near objective markers.

## Gotchas
1. **Swapped enemies never appear.** Cause: archetypes not in the level's `LevelArchetype` pool (and `linksDescWeak`).
   Fix: append pool entries; size them for peak concurrency.
2. **A scripted beat silently stops after a swap.** Cause: `GetCharactersByArchetypeUid` still looks for the old
   archetype names. Fix: retarget those lookups.
3. **New enemies still come out of Chaos portals.** Cause: portals are level actors; `spawnVisTypeRef` is cosmetic.
   Fix: none from the scenario; accept or edit the level.
4. **Cloned level runs the original mission's logic.** Cause: the scenario is a compiled per-level module. Fix: branch
   inside the original scenario on game mode.
5. **"Spawned" fired but no enemies.** Cause: spawn requests report finished after a 5 s timeout with zero actors.
   Fix: verify with a direct spawn and on-screen counts; don't trust `OnSpawned`.
6. **Domain packs never spawn on a converted level.** Cause: no usable domain trackers / navmesh match in PvE mode.
   Fix: direct `SpawnActorByArchetype` near the squad, or rebake with ESD points.
7. **Rebuilt navmesh has no spawn points ("Skipping...").** Cause: the server cd_list's `navmesh_project` has no
   spawn-generation settings, or no xgine link/text SCN. Fix: the PvE descriptor string + Furnace's inputs.
8. **Spawn points baked but never created.** Cause: the server scene manifest lacks the spawn-point class links. Fix:
   add them (and the PvE-shared links).
9. **Director stuck: desired pressure 0, "ON HOLD".** Cause: the scenario never released the hold stage (and/or a
   forced stage). Fix: `EsdSetScenarioHoldStage` False; don't force stages.
10. **Stage readout printed every tick.** Cause: `GetEsdStage` feeds an enum into `If`, which is true for any non-OFF
    stage. Fix: compare against a specific value.
11. **Saber's AIConverter exits 0 with no output, or -1 after "Loading resources...".** Cause: wrong layout, `-o`
    outside `local/scenes`, missing terrain / lwi conversion output / scene collision. Fix: mirror Saber's layout and
    capture its debug output with a debugger.
12. **Tools reject a retail tpl ("Unknown chunk id: 4").** Cause: Patch-15 refs sub-chunk newer than the tools. Fix:
    downgrade it in a copy of the pak the tools read.
13. **Client crash at level load after adding a debug readout.** Cause: a client node with no retail use, or a link to
    a missing pin. Fix: validate pins, use retail-proven nodes.
14. **Teleport + get-up in one step: camera cuts, Marine just stands.** Cause: same-frame teleport and EnterSmart. Fix:
    wait ~0.5 s between them.
15. **With the 12-player flag every player loads their own barge.** Cause: the flag makes clients ignore the match's
    hub data. Fix: flag False (shared barge); a host-only setting cannot work.

## Assets
None. A short intro voice line for the converted level was produced separately (see the voices note for the media
bundle route).

## Open questions
- Whether the director spawns on the rebaked level now that the hold stage is released.
- Why domain-based packs fail on a converted campaign level (an unknown domain flag is skipped by native code).
- A data path to more than 3 seats in the loading Thunderhawk.
