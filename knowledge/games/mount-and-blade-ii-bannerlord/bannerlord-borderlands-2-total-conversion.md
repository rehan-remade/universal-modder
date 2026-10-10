---
kind: game
title: "Borderlands 2 as a Bannerlord total conversion: own skeletons, guns, creatures and BL2 rules in a C# module"
game: "Mount & Blade II: Bannerlord"
games_also: ["Borderlands 2"]
game_version: "v1.4.8.119303 (Steam, Windows 11); client TaleWorlds.Native.dll 14,185,944 bytes, PE timestamp 0x6a732505 (all crash offsets in these notes are for this build); Modding Kit (Steam app 1393600) build 24575232; Bannerlord.Harmony 2.4.2. Guest: Borderlands 2 on Steam (UE3 packages, version 832)"
platform: windows
engine: unknown
route: loader-api
tools: ["Bannerlord module system (SubModule.xml, ModuleData XML + XSLT, C# net472 SubModule built with the .NET 8 SDK)", "Bannerlord.Harmony 2.4.2 (optional, never shipped)", "Python 3.10 + numpy (own LZ4, xxHash64, DXT/BC encoders, .tpac/.rdc writers)", "Blender 4.2 headless", "umodel (UE Viewer)", "Ghidra 12.1.4 headless + JDK 21", "ilspycmd 9.1", "python minidump package", "FMOD Studio 2.02.27 CLI", "wwiser + vgmstream", "ffmpeg", "PowerShell 5.1 test harness"]
anti_cheat: "none. Single player only. Borderlands 2 is never launched, patched or hooked: its package files are read offline, read-only. Bannerlord tests start the normal client with its own command-line module list; no injection, no bypass. One optional feature (comic shading) edits three of the game's own shader/post-effect files with hash-checked backups and a revert script"
status: in-progress
agents: ["Claude Code (Opus 5.5)", "Claude Code subagents (Sonnet 5.5)"]
humans: ["@theartur2000"]
date: 2026-10-07
links: []
tags: [bannerlord, borderlands-2, total-conversion, mashup, csharp-submodule, harmony, moduledata, xslt, project-mbproj, custom-race, creatures, guns, siege, campaign, gauntlet, fmod, psai, cel-shading, umodel, ghidra, minidump, test-harness]
---

# Borderlands 2 as a Bannerlord total conversion: own skeletons, guns, creatures and BL2 rules in a C# module

> A Mount & Blade II: Bannerlord v1.4.8 module ("BL2Port") that re-skins the game as Borderlands 2 while keeping
> Bannerlord's battles and campaign: troops on their own BL2 skeletons and animations, creatures as mounts, bosses, guns
> on the crossbow class, shields, elements, loot, HUD, audio and campaign systems. The route is the official module
> system plus a C# SubModule with optional Harmony patches, plus our own offline writers for Bannerlord's binary asset
> formats. Verified by about 180 unattended recorded test runs, byte-exact format round trips and offline validators;
> NOT verified: the one-command converter has never been run from scratch, and audio was never heard by the agent.

Game-level companion of [`../../techniques/editor-free-bannerlord-assets.md`](../../techniques/editor-free-bannerlord-assets.md)
(`.tpac` / `.rdc` formats, skeletons, clips, packing, the 64-bone limit), which this note does not repeat. Evidence tags:
**[V]** seen in the running game or by a byte-exact round trip, **[M]** measured, **[S]** static analysis only,
**[H]** hypothesis. "TN n" = gotcha n of the asset note.

## Setup
- **Game:** Bannerlord **v1.4.8.119303**, Steam. NavalDLC and BirthAndDeath are present but optional; many test runs did
  not load NavalDLC, which matters for items, clans and banner icons that reference it by id.
- **Modding Kit** (Steam app 1393600): ground-truth packages and the `editor` build of the native DLL (asserts and strings
  the client lacks). Client and editor DLLs differ: client for crash offsets, editor for format questions. After any game
  update every `0x18...` address is stale.
- **Libraries seen for 1.4.8** (none needs BLSE): Harmony 2.4.2, ButterLib 2.12.0, UIExtenderEx 2.13.3, MCM 5.12.3. Only
  Harmony was adopted, as an optional `DependedModule` (`Private=false`) with a non-Harmony fallback for every feature.
- **Module order that worked:** Harmony, `Native`, `SandBoxCore`, `Sandbox` (the id is `Sandbox`, not `SandBox`),
  `CustomBattle`, `StoryMode` (BEFORE the mod, so the mod's XSLT sees its XML), then the mod. Later modules win for
  same-name items, prefabs, scene folders and battle-scene rows.
- **Launch without the launcher UI:** run the client exe with
  `/singleplayer _MODULES_*Native*SandBoxCore*CustomBattle*<YourModule>*_MODULES_` (add `Sandbox` for campaign tests; the
  editor takes the same line). After a crash answer No to "enable safe mode?" (it disables mods) and to "collect files".
- **Tools:** Ghidra on a COPY of the DLL; `ilspycmd` into an uncommitted scratch folder; `dotnet build -c Release` for the
  `net472` module, with `-p:Bl2NoDeploy=true` as a compile gate that skips the copy-to-`Modules` targets. FMOD Studio
  **exactly 2.02.27** (the runtime refuses banks from 2.03). ffmpeg cannot decode Bink 2.
- **Module tree:** `SubModule.xml`, `bin/Win64_Shipping_Client/`, `ModuleData/` (+ `project.mbproj`), `Assets/*.tpac` +
  `RuntimeDataCache/*.rdc`, `Prefabs/` (loaded WITHOUT registration), `GUI/`, `Sounds/PC/`; an empty `AssetSources/` must exist.
- **Reading Borderlands 2:** offline, read-only. `umodel` over the `.upk` packages (material instance constants need
  `-dump`; DLC textures export at 64 px unless the path is the `Compat` folder, not `Compat/Content`); our own readers for
  tagged properties, Wwise `.pck` and Scaleform HUD movies. Ripped data stays local; the converter reads each owner's own install.

## Route and why
`route: loader-api`: XML merged and patched with XSLT at load, a C# SubModule that registers game models, campaign
behaviours and mission logics, optional Harmony patches of MANAGED methods, plus offline writers for the binary formats.
- **1. Port the content (chosen).** Bannerlord is a host with rich systems (agents, ragdolls, formations, sieges, economy,
  campaign map); Borderlands 2 is a donor with rich content. Content was ported and the donor's rules (recharging shields,
  elements, rarity-coloured loot) re-expressed as Bannerlord data and C#. Every unit gets its own body, skeleton and
  animations; an audit script lists each boss as OWN, STAND-IN or REUSE.
- **2. Passthrough:** not tried. **3. Embed a decomp:** no. Bannerlord's managed assemblies (and two other total conversions, The Old Realms and Shokuho)
  were decompiled locally with `ilspycmd` only to read APIs and conventions; nothing is copied or shipped.
- **4. Reimplement (in part):** BL2's rules run on top of Bannerlord (model wrappers, mission logics), not instead of it.

For assets we tried, in order: rigid pieces on the human skeleton at runtime (nothing could be skinned); driving the
Modding Kit editor by UI automation (about 15 clicks per material); an in-editor command bridge; **writing the engine's own
formats directly from Python** (about 3 s per asset set, scriptable; chosen). Native patching was rejected: Harmony patches
only MANAGED methods, and binary-patching the 64-bone layout was scoped at 52 function rewrites (about 166 KB of machine
code) redone on every update. Data stays inside the limits and managed code guards the rest. The one-plan converter
(`scripts/convert/convert.py`, 110 stages) has had `--dry-run` and `--selftest` exercised but no real `--run`.

## How the game works (what we had to learn)
Learned from game files, managed assemblies (decompiled locally, never published), the native DLL and many crashes. Names
are managed TaleWorlds names unless marked "native". Companion notes:
- Asset facts (axes, materials, inventory icons, colour-grade LUTs): "Axes, materials, icons and colour grades" in the asset
  note. Scene folders, battle-scene rows, prefabs, banners, menu video and shaders are below.
- Races, skeletons, animation, creatures: [`../../techniques/bannerlord-custom-races-and-creatures.md`](../../techniques/bannerlord-custom-races-and-creatures.md).
- Combat, damage models, own blows, guns on the crossbow class: [`../../techniques/bannerlord-combat-damage-and-guns.md`](../../techniques/bannerlord-combat-damage-and-guns.md).
- Native crashes, hangs, dump analysis: [`../../techniques/bannerlord-native-crashes-and-hangs.md`](../../techniques/bannerlord-native-crashes-and-hangs.md).

**Registration and merging**
- *Managed* data files (Items, NPCCharacters, EquipmentRosters, Monsters, SPCultures, Settlements, partyTemplates, GameText...)
  are named by `<XmlNode><XmlName id=... path=.../>` in `SubModule.xml`, any file name. *Engine-side* files (action sets, usage
  sets, skins, sounds, prebaked animations) go in `ModuleData/project.mbproj`, which only works with **canonical ids**:
  `XmlResource.GetMbprojxmls` keeps just `id` and `name`, and the engine asks for each kind under a FIXED id (`soln_action_sets`,
  `soln_skins`, `soln_monsters`, `soln_monster_usage_sets`, `soln_action_types`, `soln_item_usage_sets`, `soln_movement_sets`,
  `soln_full_movement_sets`, `soln_combat_system`, `soln_voice_definitions`, `soln_sound_files`, `soln_sound_event_data`,
  `soln_soundtrack`, `soln_decal_textures`, `soln_particle_systems`). Any other id is silently never merged.
- A same-named `.xslt` beside an engine file runs on the document merged so far BEFORE that file merges (how rider rows get
  appended to Native's `human` usage set). An XmlNode with only an `.xslt` patches everything merged before it, so order nodes.
- Merge rules: same-id elements merge; usage-set rows are keyed by `@action` ONLY (a module row with an existing action
  overwrites it); `_replaceWhileMerging="true"` replaces; same-id action sets merge by appending.
- The native sound loader opens every module's `project.mbproj` and loads each named `sound_event_data` XML RAW (no XSLT; a
  MISSING file crashes the game). A new event path is appended, an existing one overwritten.
- XSLT runs on `XslCompiledTransform`: 1.0 patterns cannot use variables, attribute values with localisation ids need `{{ }}`,
  `document()` needs `XsltSettings.TrustedXslt`. Apply every generated stylesheet to the real files and validate against
  `XmlSchemas/*.xsd` before a launch. Patch items of a possibly absent module with XSLT, not override elements.
- Items: ammo needs `item_usage` / `flying_mesh`; melee items need `bo_*` collision bodies. A roster is rolled PER SOLDIER.
  `NotUsableByPlayer` is not an `ItemFlags` member in 1.4.8 (use `NotUsableByMale` / `NotUsableByFemale`). Item categories are
  registered in code from `InitializeSubModuleGameObjects`. `upgrade_requires` is enforced by the player's party screen only.
- Languages: the "English" id is never read from files; register a NEW id in `ModuleData/Languages/language_data.xml` and switch
  at runtime from `OnBeforeInitialModuleScreenSetAsRoot`. `LoadLanguage` takes `ChildNodes[1]` as the root. Keep `{VARIABLES}`
  tokens identical (`LocalizedTextManager.CheckValidity`). Custom cultures need `str_culture_description.<id>`,
  `str_neutral_term_for_culture.<id>`, `str_faction_*.<id>`.
- Hook order: `OnSubModuleLoad` -> `InitializeSubModuleGameObjects` -> `OnBeforeInitialModuleScreenSetAsRoot` -> `OnGameStart`
  (models, campaign behaviours) -> `OnBeforeMissionBehaviorInitialize` -> `OnMissionBehaviorInitialize`; `OnApplicationTick`
  runs even when the map is paused.
- Persistence: prefer `SyncData` with plain keys over a `SaveableTypeDefiner` (real quests need one). Statics survive a new
  campaign in the same process: reset them in constructors. Banners, races and new items need a NEW campaign. Give every system
  an off switch so a crash can disable one feature.

**Missions and sieges**
- `Mission.AfterStart` calls `OnBeforeMissionBehaviorInitialize`, then `OnBehaviorInitialize` for every behaviour, then
  `OnMissionBehaviorInitialize`. A view added early has no `MissionScreen`: attach Gauntlet layers on the first tick that has one.
- Deployment: `FinishDeployment` inside a mission tick removes behaviours mid-loop (defer to `OnApplicationTick`).
  `DeploymentMissionController.SetupTeams` dereferences `Mission.InitialPlayerAgent` and dies as a hardware fault when the hero
  is not in the roster. After `Utilities.QuitGame()` scripts run with `Mission.Current` null: end the mission, wait for null, quit from the MAP.
- Battle size: `DefaultBattleMissionAgentSpawnLogic` clamps `_battleSize` to `MaxNumberOfAgentsForMission / 2`; the initial spawn
  is not throttled by live agents (reinforcements are, mounts counted double). A Harmony postfix on its constructor can raise it
  (parameter names must match: `suppliers`, `playerSide`, `battleSizeType`).
- Time: `Mission.AddTimeSpeedRequest(new Mission.TimeSpeedRequest(speed, id))`; `RemoveTimeSpeedRequest` throws if absent. Sky objects
  are entities re-placed each frame at camera position + direction x distance (map far plane 300 m, missions 12.5 km).
- Sieges: `Mission.IsSiegeBattle` is known only after the first tick; wall defenders stand on `archer_position`. `UsableMachine`
  counts only machines that `IsVisibleIncludeParents`, so hiding an entity switches the machine off, and deployment shows it again.
  In one clean custom-battle test (300 troops, machines visible, 4 minutes) the attacker AI fired no machine at all.
- Native AI: ranks targets by ground distance; `BehaviorMountedSkirmish` finds nothing when the enemy side is only immobile
  agents; an AI gunner with a pinned spot and no formation never fires; `IsSideDepleted` counts origins, not formations, so
  leftover pack members keep a mission undecided and the campaign pays nothing.

**Campaign, economy and AI**
- Town gold moves 25 percent per day toward a target and every sale drains it. `PartySizeLimitModel` returns an `ExplainedNumber`
  base x (1 + sum of factors): scale as a flat add of result x (f minus 1)/(1 + sum). `FindAppropriateInitialRosterForMobileParty`
  is the only funnel for template-built rosters; `GetTotalWage` is the flat upkeep funnel.
- NPC troops have `hit_points=100` and no perks; armour is a property of the ITEM, so troops sharing a body mesh need item copies.
- Parties think when `Ai.HourCounter % 6 == 0`. `CampaignEvents.TickEvent` fires only while the map clock runs. Captures go through
  `TakePrisonerAction.Apply`. `LeaveSettlementAction.ApplyForParty` throws when `MainParty.CurrentSettlement` is null. `StartQuest`
  during a friendly encounter ends it (defer). `PlayerEncounter.DoMeetingInternal` starts the map conversation.
- Custom map parties stay out of native AI with `SetDoNotMakeNewDecisions`, `IgnoreByOtherPartiesTill(Never)` and a clan WITH a leader.
- Character creation: the handler lists six culture ids; a new culture throws unless rosters named
  `player_char_creation_<culture>_<title>_<m|f>` exist. A custom `ICharacterCreationContentHandler` registers from
  `OnCharacterCreationInitialized` at priority 1000 (vanilla 800, StoryMode 900). The face editor shows a race dropdown once
  `FaceGen.GetRaceCount() > 1`.
- Heroes: `CharacterObject.Race` is NOT saved (`Hero.IsFemale` is). One `covers_head` item hides the native head. Look must be set
  in BOTH equipment sets (towns use civilian). `HeroCreator.DeliverOffSpring` asserts equal race.
- StoryMode: `OnBeforeGameStart` disables its XML for any game it did not start; `TutorialPhaseCampaignBehavior` backs up the hero's
  12 equipment slots at creation end and writes them back.

**Rendering and audio**
- Runtime meshes: `Mesh.CreateMesh(true)`; `LockEditDataWrite()` -> `AddFaceCorner(...)` (flip V) -> `AddFace` -> `UnlockEditDataWrite`;
  `ComputeTangents()`, `RecomputeBoundingBox()`, `CullingMode = None`; attach with `GameEntity.AddMultiMesh` or
  `AddMultiMeshToSkeletonBone`. `Texture.CreateTextureFromPath` is the Gauntlet route.
- Entities with clips: `GameEntity.CreateEmpty`, `Skeleton.CreateFromModel`, `Skeleton.SetAnimationAtChannel`; poll
  `GetAnimationParameterAtChannel(0)` to restart one-shots; far entities `EntityFlags.DoNotTick` with hand ticks.
- Comic shading edits the final-pass and tonemap shaders and the Native post-effect graph, then forces a recompile at launch.
- FMOD 2.02.27 is statically linked; banks in `soundfiles.xml` load AFTER Native's, and a module bank needs only Native's MasterBank
  (buses, VCAs, snapshots are shared by GUID). Samples are FSB5 FMOD-Vorbis (codec 15), 48 kHz, two Vorbis setups. Bannerlord has ONE
  release event per weapon CLASS, so per-gun sounds are new events played from code with `Mission.MakeSound` in `OnAgentShootMissile`.
- Runtime WAV: `SoundEvent.CreateEventFromExternalFile("event:/Extra/voiceover", path, scene, is3D, false)`, `Play()`, then
  `Stop()` + `Release()`. Mono 16-bit; rate-limit on real-time clocks. Music is psai and keyed by hard-coded `MusicTheme` ids.

**Scenes, prefabs, banners, menu video and shaders**
- **Scene folders** hold `scene.xscene` (XML: entities, terrain layers, atmosphere), `terrain.bin` (chunks MIDX, HGHT, NRML, WGHT, PHYM;
  HGHT is PNG-like blocks with a non-standard header, not decoded), `navmesh.bin`, `flora.bin`, `prt_data.bin` (baked lighting, settlement
  scenes only, up to 128 MB) and `atmosphere.xml`. `navmesh.bin` vertices are plain float triples about 0.2 m above the terrain, readable
  by range + neighbour test (15k to 45k clean vertices per scene), so you can read ground height offline. A module scene folder with the
  SAME name replaces the Native one (last module wins). A renamed COPY of a Native battle scene under a new id works with text edits only
  (the scene id is not checked against file contents), reusing Native terrain, navmesh and flora; no writer for terrain or navmesh exists.
- **Scene choice for field battles:** `DefaultSceneModel` + `Campaign.InitializeScenes` read `ModuleData/sp_battle_scenes.xml` of every
  active module: rows `<Scene id= terrain= forest_density= map_indices=...>`. The root must be the SECOND child of the document
  (declaration first, no comment before the root). Two scenes sharing a `map_index` trigger a `FailedAssert` ("Multiple battle scenes for
  map patch", log only in retail) and a random pick. Custom battle lists come from a `CustomBattleScenes` XmlNode that SubModule.xml must
  name. The campaign map's battle index map is one byte per cell.
- **Terrain layer textures are looked up BY NAME per season** in `scene.xscene`, so same-name module textures reskin the ground of every
  scene using them (309 ground textures covered 99 percent of layers over 108 land scenes). The campaign map terrain itself is a 2.1 GB
  virtual-texture tile set that a module cannot override; named terrain-layer textures and the `mainmap_cliff_*`, `mainmap_decal_*`,
  `worldmap_*` tree materials can be. Flora kinds name their materials, so same-name material overrides could re-grade flora (unproven at
  the time). Sky, fog, terrain shape, navmesh and flora placement cannot be reached by override (copy the scene folder instead).
- **Prefabs:** a `Prefabs/*.xml` file in a module redefines a Native prefab by name with no registration (later module wins; root
  `<prefabs>`, top-level `<game_entity name=...>`). Instances in scenes are baked at load and are NOT `GameEntity` objects at runtime (one
  town: 9,030 top-level entities in the file, 1,978 at runtime), so runtime code can only reach hand-placed ones. Redefine the prefab:
  keep the root's physics shape, drop its meta mesh and occlusion body (a dropped occlusion body also stops people being culled behind
  lower replacement pieces), add your pieces as children. 159 buildings were dressed this way and verified in game. Children transform
  with Euler order Rz Rx Ry.
- **Settlement scenes:** 173 outdoor settlement scenes (53 town centres, 22 castles, 86 villages, 12 hideouts) carry about 447,000
  top-level entities and 419,340 prefab instances of 3,609 prefabs. Overriding the metamesh by name was applied to 3,518 building meshes
  (95 percent of instances, 3.83 GB, 171 `bl2w_*` materials that are Native records with texture guids swapped). Collision stays Native,
  so the baked navmesh still fits.
- **Campaign-map scene:** a module `SceneObj/Main_map/scene.xscene` is the one the game loads (proved by scaling a town 3x). Settlement
  entities carry tagged children (gate, wall, siege, banner); untagged mesh and decal components can be stripped and replaced by NEW
  top-level entities. Extra children under settlement entities crash the campaign load; multi-material Z-up icon FBXs crash the map too;
  single-material meshes rotated +90 degrees about X work.
- **Banners:** a banner key is groups of 10 numbers per layer (mesh, colour, colour2, w, h, x, y, stroke, mirror, rotation); group 1 is
  the background. Icons come from the merged `BannerIcons` XML (ids 7000+); each icon is a quad of a material whose texture is a 4x4 grid
  of 512 px cells (`texture_index` 0 top-left, row-major, 2048x2048 BC7). Shader `gui_color_and_stroke`: G = fill, R = outline ring, A =
  coverage. Clans inside a kingdom are recoloured to the kingdom's colours only if those hexes are palette entries. Banners are saved with
  the clan: a new campaign is needed.
- **Main-menu video:** every active module's `Videos/initial_menu/<name>/` with a `*_pc.ivf` AND an `.ogg` is a candidate; one is picked
  at random per screen. Native ships 8 (VP8 in IVF, 2560x1440, 24 fps, about 32 s, Ogg Vorbis 48 kHz). Ours: 1920x1080, VP8 two-pass, key
  frame every 48 frames, audio length equal to video length exactly.
- **Shaders:** sources ship in `Shaders/Sources` (`.rs` shader with `main_vs`/`main_ps`/`main_cs`, flags as `#define`s; `.rsh` include),
  compiled with the shipped `d3dcompiler_47.dll`; but variants are taken from `Shaders/D3D11/compressed_shader_cache.sack` (about 1.5 GB)
  by a key of shader name + flag words with no source hash, so editing sources alone changes nothing. Misses log `Missing shader from
  sack` and `compile_shader:` and are cached in a ProgramData folder. The console command `resource.shader.recompile_single_shader
  <substring>` (call it through `Utilities.ExecuteCommandLineCommand`) evicts a shader's keys. Modules cannot override core shaders or the
  Native default post-effect graph (first definition wins, Native loads first). GPU skinning is compute-only and its palette is 64 bones.
- **Post-effect inputs:** `postfx_graphs.xml` `<input index=N type=provided|node source=...>` becomes `texture<N>`; provided sources
  include `gbuffer_depth`, `gbuffer_depth_with_water`, `gbuffer_normals`, `gbuffer_stencil`, `gbuffer_motion_vectors`, `screen_rt`; index
  4 is last frame, 5 the cube map. `gbuffer_stencil.g` low 4 bits are a material id (1 standard: bark, characters, props; 3 terrain; 6
  flora leaves; 7 and 9 far-tree billboards; 8 grass); 0x10 decals, 0x20 stationary, 0x40 not season-affected.

**UI and Gauntlet**
- Own HUD: a `MissionView` adds `new GauntletLayer(name, order, false)`, `layer.LoadMovie("Prefab", viewModel)`, `MissionScreen.AddLayer`
  on the first tick with a screen. Native views reset `IsVisible` each tick: hide by fading layer alpha.
- Sprites: swap `SpriteCategory.SpriteSheets[i]` at load for a texture of identical layout; fonts are SDF atlases, swappable.
- `LoadingWindowViewModel.TitleText` / `DescriptionText` are empty outside multiplayer; fill them when `IsLoadingWindowActive` turns
  true. `Modules/Native/splash.bmp` and the first loading image (inside vanilla `core.tpac`) cannot change from a module.
- Main menu video: replace the view as `MBInitialScreenBase.RefreshScene` does (StopVideo + FinalizePlayer, new `VideoPlayerView`,
  assign `_videoPlayerView`, PlayVideo, RefreshVideoAspect). Replaying on the existing view stays black.

## Build steps
The asset writers, validators, safe installer, test harness and crash-dump tools are the author's own SDK, which is not published yet
(the author may add a link later); the Borderlands 2 conversion pipeline itself is not published either. The order we recommend for a
NEW Bannerlord mod:
1. An empty module loading with `Native`, `SandBoxCore`, `Sandbox`, `CustomBattle` and a log you control, plus the compile gate.
2. A test harness BEFORE content: command-line launch with an explicit module list, muted test config restored byte for byte, kill only
   the PID it started, mod log, first-chance exception logger, a watchdog that dumps a hung game.
3. Data first, with offline proof: XSLT applied to the real XML before every launch; `project.mbproj` with canonical ids from day one and
   an install-time check that rejects any other id.
4. Assets with the asset note's writers, proven by re-packing the game's own files byte for byte.
5. A first custom race on the humanoid path, validators, one silent recorded battle; fix the class of any crash and add a validator rule.
6. Combat clips in copy mode, model wrappers, creatures as mounts with a hidden rider, then pack assets.
7. Install = backup, manifest first, a revert command, refuse while the game runs, repack once at the end.

## Verification
| Oracle | What it covers | Result |
|---|---|---|
| Byte-identical re-pack of the game's own files | every binary writer | 150 of 150 Native packages; 103 of 103 clip caches; 95 of 95 mesh edit blobs |
| Offline validators before install | NaN, bone count/order, ragdoll bodies and joints, `ik` rules, canonical ids, clip-name length, partner rule | every explained crash became a rule |
| Offline XSLT apply + compile gate | stylesheets on the real XML checked against the XSDs; build with `Bl2NoDeploy` | before every launch |
| Unattended silent recorded runs | battle, siege, campaign walk, story and mega suites with video, contact sheets, metrics from the mod log | about 180 tagged runs |
| Crash triage | WER offset -> `minidump` -> Ghidra on a DLL copy -> fix -> validator rule | 13 native crash offsets, 2 hangs solved |
| Frames at full size | contact sheets at about 960 px per picture, every picture opened | found a mirrored preview camera, grey props |

Measured [M]: 34,265 loose packages start in 25.7 s warm / 280.3 s cold, 5.6 s packed into 26; 1,000 agents 150 to 164 fps average,
1,400 agents 121 to 153; map AI think spikes 107 to 119 ms every six game hours -> 45 to 74 ms after spreading `HourCounter`.
Lessons that held: turn every explained crash into a validator rule and fix the class, not the feature; prove a data file loaded
before reverse engineering the engine around it; look at pictures at full size; read a file before overwriting it; record who
verified each claim (harness, self-test, in game).

**Not verified:**
- The converter as a whole. The shield-partner fix (`blends_with` restored on 7,974 clips) and the IK hit-bone guard were compiled
  but never A/B tested in game; refit hit capsules were measured only offline.
- The body-rotation-reference guard (crash note gotcha 9) was compiled; no in-game run of it is recorded.
- Riderless creature fighters (still crash at the AI target scorer), Spiderant mounts in full battles, Helios sky at dusk or night.
- Audio was never heard by the agent (tests are silent); the FMOD bank loads clean (1,628 to 1,634 events).
- Cold-cache start-up after packing; other Bannerlord versions; multiplayer; saved-game compatibility (new campaign required).

**Where our own records disagree:**
- Crash 4 (quadruped creatures): the pace-1 theory and the canonical-id fix changed together; which one removed the crash is unknown.
- 62 same-name material overrides changed nothing on town houses while metamesh overrides worked: unexplained.

## Gotchas
Evidence: V seen or measured in game, S static analysis only. Race, creature, combat and native-crash gotchas live in the companion notes.

### Data, registration and XML
1. **Quadruped mounts crash at the first movement tick (+0x760967, +0x636b6e), even as an exact copy of `as_horse`.** See TN 8.
2. **Symptom.** 2,597 string overrides do nothing, or a language file loads 9 of 794 strings. **Cause:** the "English" id is never read from
   files; a comment between the XML declaration and the root hides everything. **Fix:** a new language id; comments inside the root. [V]
3. **Symptom.** `The stylesheet is too complex` at launch (about 450 per-troop plus 217 gun templates); an override element for an absent
   module's item becomes a broken stub. **Fix:** one template per job with ids in an inlined `|id=value|` lookup (560 templates worked); patch
   by XSLT template, which just does not match; apply every stylesheet with `XslCompiledTransform` before launching; escape quotes. [V]
4. **Symptom.** Patching the Native horse usage set changes every horse. **Cause:** rows merge by `@action` only. **Fix:** a new usage id plus
   rider rows added to `human` by a same-named `.xslt`; copy the 1.4.8 Native set, never an older mod's copy (it lacks `strike_swim_action`). [S]
5. **Symptom.** Looters became Marauders, the player became a Goliath on a stealth mission, a race vanished from a shared XML after a rebuild.
   **Cause:** body template ran after the troop template; level-less stealth rosters hit the last rule; a later generator rewrote the shared
   file from an older stage. **Fix:** order XmlNodes so a node patches only what came before, one generator per output, regenerate shared XML
   from the INSTALLED copy before each install. [V]
6. **Symptom.** New campaign crashes in `InitialChildGeneration` for a new culture; pages show "ERROR: Text with id". **Cause:** no
   child/teen/lord rosters for the cloned culture; missing culture/faction GameTexts; castles and clans without `text=`. **Fix:** clone all
   ~257 empire rosters per culture, copy the 341 `char_creation` rosters untouched, register GameTexts, add `text` attributes by XSLT. [V]
7. **Symptom.** A hero's race is lost after loading a save. **Cause:** `CharacterObject.Race` is not saved. **Fix:** store hero id -> race in
   `SyncData`, restore on `OnSessionLaunchedEvent`; Harmony postfix on `FaceGenVM.get_CanChangeRace` to hide the race dropdown. [S]
8. **Symptom.** New items never appear in markets; the first hit with a new weapon crashes; the custom-battle screen crashes on new ammo.
   **Cause:** no market item category; no `bo_*` collision body; no `flying_mesh` / `item_usage`. **Fix:** reuse Native `bo_*` bodies by name
   and mirror the native bolt. [V]
9. **Symptom.** 25 lords wore one hero's body. **Cause:** hero bodies were shared items and `NotUsableByPlayer` does nothing in 1.4.8.
   **Fix:** exclusive hero races, purge race-skinned bodies from loot and packs by code, plus an audit script. [V]

### Missions, sieges and campaign
10. **Symptom.** Mission behaviours never initialise; NRE in `OnMissionScreenInitialize`. **Cause:** behaviours added in
    `OnMissionBehaviorInitialize` miss `OnBehaviorInitialize`; `MissionScreen` is null for views added early. **Fix:** register in
    `OnBeforeMissionBehaviorInitialize`, add the layer on the first tick with a screen. [V]
11. **Symptom.** `ArgumentOutOfRange` in `Mission.OnTick` right after deployment. **Cause:** `FinishDeployment` called inside a mission tick.
    **Fix:** defer to `SubModule.OnApplicationTick`; found with a first-chance exception logger. [V]
12. **Symptom.** Attacker siege machines never fire in custom-battle sieges. **Cause:** not found; hiding a machine switches it off for the
    engine. **Fix:** "called shots": hide the machine, re-hide on every scan (deployment shows machines again), put a mast in its place, resolve
    impacts on a timer. [V]
13. **Symptom.** A siege troop is not found in custom battles; townsfolk scenes throw in `Team.IsEnemyOf` and `Mission.SpawnAgent`.
    **Cause:** `CharacterObject` is null outside the campaign; townsfolk have `Team.Invalid`; custom races lacked `_settlement` monster
    variants. **Fix:** look up as `BasicCharacterObject`, guard team tests, generate the variant monsters. [V]
14. **Symptom.** The campaign map stutters every six game hours (107 to 119 ms). **Cause:** a new game, war or peace zeroes every party's
    `Ai.HourCounter` (565 of 660 parties shared one hour). **Fix:** spread `HourCounter` over 6 values at load and daily: spikes 45 to 74 ms. [V]
15. **Symptom.** Revival after capture and the map sky never run. **Cause:** hung on `CampaignEvents.TickEvent`, which fires only while the map
    clock runs. **Fix:** tick from `SubModule.OnApplicationTick`. [S]
16. **Symptom.** NRE in `bandit_start_defender_condition` on a map conversation; map crash seconds after loading a boss party. **Cause:**
    `CreateCustomPartyWithTroopRoster` with radius above 0 can land off the navigation cache; a leaderless bandit clan crashes the patrol AI.
    **Fix:** a checked land spot with radius 0; AI decisions off, a clan with a leader, move by script. [V; first part S]
17. **Symptom.** Merchants have no money in a big town. **Cause:** town gold drains with every sale. **Fix:** a `SettlementEconomyModel`
    wrapper with a higher target and a floor, topped up on load and on entering a town. [V]
18. **Symptom.** Reskinned items show vanilla names in inventory, shop and loot; a 15,000 shield drops from looters. **Cause:**
    `OnGetWeaponDataHandler` covers missions, party and portraits only and Native's `ViewSubModule` resets it every game start; the vanilla
    shield price formula plus a loot roll that can pick any carried item. **Fix:** the three reskin hooks (combat note), re-installed after
    Native's; a `BattleRewardModel` wrapper capping item value; an audit of everything troops, shops and loot can produce. [V]
19. **Symptom.** The hero loses the class kit after creation; StoryMode tests find no story data. **Cause:** the tutorial phase writes back
    a 12-slot backup; `OnBeforeGameStart` disables StoryMode XML for a game it did not start. **Fix:** re-check after the tutorial; call its
    private StartGame in tests. [V]

### Rendering, audio and UI
20. **Retextured Native buildings do not change (62 material overrides).** See TN 1 and 2.
21. **Symptom.** Runtime "dressing" of towns reaches almost nothing. **Cause:** prefab instances are baked at load and are not entities.
    **Fix:** redefine the prefab by name in `Prefabs/*.xml`. [V]
22. **Symptom.** Runtime quads draw black, white or mud; a moon renders as a grey disc over the HUD. **Cause:** pictures on the default
    material misbehave; the moon material is additive and ours was opaque. **Fix:** no picture, default material, colour through
    `Mesh.Color`, colour pre-compensated for the grade; `SetAlphaBlendMode(Add)` for additive sprites. [V]
23. **Symptom.** Cel shading inks every blade of grass; greens turn ochre under the colour grade. **Cause:** depth and normal edges on
    foliage; the LUT shifts colours. **Fix:** exclude stencil ids 3, 6, 7, 8, 9 and pixels with 6 of 8 vegetation neighbours, fade out by 40
    to 100 m; pre-compensate authored colours. [V offline]
24. **Symptom.** Edited shader sources change nothing; a Steam update or "verify" silently reverts edited game files. **Cause:** variants
    are looked up in the shader cache by name + flags with no source hash; Steam rewrites files whose depot hash changed. **Fix:**
    `resource.shader.recompile_single_shader <substring>` once per launch before the first menu; sha256 backups, a refuse-if-unknown-build
    rule and a revert command. [V]
25. **Symptom.** Textures drawn with red and blue swapped or upside down. **Cause:** `Texture.CreateFromMemory` reads PNG channels as BGR
    with a bottom-left origin. **Fix:** pre-swap R and B and flip V; `Texture.CreateTextureFromPath` for Gauntlet. [S/V]
26. **Symptom.** Gun icons are a blob cut by the border, guns hang sideways, an imported weapon is 58 m long. **Cause:** crossbow-class
    items use a fixed `crossbow_cam` pose looking along +Z, exports lay along +Y; FBX unit scale from a cm-based Blender. **Fix:** barrel
    on +Z, top on +Y; global scale 0.01. [V]
27. **Symptom.** A patched BL2-derived FMOD bank gives "Error loading file" (error 13). **Fix:** build a fresh bank headless with
    `fmodstudiocl` 2.02.27 from a generated project and ship a real sound-event XML (1,628 events, 7,806 files); 2.03 banks are refused. [V]
28. **Symptom.** The soundtrack throws `ArgumentException` on the music thread, or added themes never play. **Cause:** the psai merge
    adds to a dictionary keyed by hard-coded ids. **Fix:** do not register `soln_soundtrack`; call `PsaiCore.Instance.LoadSoundtrackFromProjectFile([ModName])`
    (wrapped; Native music remains on a bad XML). [V offline]
29. **Symptom.** Every hit, death and shield spams voices. **Cause:** the bank voices every event. **Fix:** lower bark chances and a
    token bucket on real-time clocks (3 per s, 4 at once, 5 s per agent, nothing beyond 40 m). [V]
30. **Symptom.** Prefab edits do nothing for inventory, party or trade screens; hidden native HUD elements reappear. **Cause:** precompiled
    layouts; native views reset `IsVisible` in their own tick. **Fix:** a passive `ScreenLayer` that tints brush clones; fade layer alpha,
    or `IsAgentStatusAvailable = false` each tick. [V]

### Pipeline and testing
31. **Start-up of 26 s warm, 280 s cold with 34,265 one-asset packages.** See TN 28.
32. **Symptom.** Installs take hours, fail with Windows error 5, or are refused. **Cause:** a manifest rewritten per file, identical files
    re-copied; Windows briefly locks a fresh manifest; the running game and `Watchdog.exe` hold the module DLL; `tasklist` truncates image
    names to 25 characters. **Fix:** manifest per 200-file batch, written BEFORE copying; skip identical files; retry; match
    `Bannerlord.exe` and the launcher by prefix; deploy only with the game closed. [V]
33. **Symptom.** A normal launch ran test code; `meet=looter` ran the loot test; "Harmony fixes passed" but never ran. **Cause:** a killed test
    left `autostart.txt`; substring matching of test words; the test launcher lacked Harmony so only fallbacks ran. **Fix:** honour test
    words only when the launcher set `BL2_AUTOTEST=1`, whole-word matching, Harmony first with a `-noHarmony` flag. [V]
34. **Symptom.** Verdicts wrong both ways; the fatal exception never logged; mirror fights decided by start side (265 to 0). **Cause:**
    custom test words print different end lines; a 60-entry log cap hid the 61st; side bias. **Fix:** classify by the log with an explicit end
    marker, one line per NEW stack after the cap, run every matchup twice with sides swapped and compare survivors. [V]

## Assets
Nothing here is Borderlands 2 or Bannerlord content. Everything is derived by scripts from a local install and stays local: characters,
creatures, guns, towns, HUD movies, sounds and music exported with `umodel` or our readers, fitted and baked in Blender, written with our own
writers. Every generated picture was opened at about 960 px in 2x2 sheets; the converter re-reads its own output to render previews.

## Cost and time
The journal runs 2026-10-02 to 2026-10-07. A clean conversion is estimated at 3 to 5 hours (target about 1 hour: parallel races, one repack,
fingerprint caches); race build about 7 minutes, pack 424 s, install of 52k files about 9 minutes. Dead ends cost the most time.

## Credits
- **TaleWorlds Entertainment** (Bannerlord, the Modding Kit, shipped shader sources and XML) and **Gearbox Software / 2K** (Borderlands 2) own
  the games' content; nothing from either is included in this note or the repository.
- **TpacTool** (szszss, MIT) showed `.tpac` is a readable container; **The Old Realms** and **Shokuho** showed how large total conversions
  register action sets, usage sets and mounts (nothing copied); **Harmony** (Andreas Pardeike), **Bannerlord.Harmony** (BUTR).
- **Ghidra**, **ILSpy**, **UE Viewer**, **Blender**, **FMOD Studio**, **wwiser**, **vgmstream**, **ffmpeg**, **LZ4** and **xxHash** (Yann Collet).

## Open questions
- Why does the engine refuse an animated weapon switch away from a crossbow-class gun on a mount with `FamilyType` of 10 or more?
- Which engine function computes the missile start point (measured: the eye position)?
- Can the hit-IK helper be disabled by a data flag instead of remapping the bone in managed code?
- Why did same-name material overrides fail on town houses while metamesh overrides work? Can a module ship two skin files?
- Does a same-id usage set from a module merge or replace in the NATIVE loader?
- Is a side channel for more than 64 bones workable (frame-pool reservation + per-mesh bone windows)?
- A first clean `convert.py --run` on a fresh machine; after any game update every address and shader edit needs re-checking.
