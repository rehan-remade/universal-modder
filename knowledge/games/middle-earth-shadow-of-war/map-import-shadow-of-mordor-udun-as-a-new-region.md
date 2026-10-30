---
kind: game
title: 'Map import: Shadow of Mordor''s Udûn as a playable new region in Shadow of War'
game: 'Middle-earth: Shadow of War'
games_also: ['Middle-earth: Shadow of Mordor']
game_version: 'Shadow of War Steam build 3095001 (exe 1.0.8874.0, public branch, unchanged since 2018-09-05), Windows 10 22H2; Shadow of Mordor Steam copy (public branch, build 7348332) as the map source'
platform: windows
engine: unknown
route: data
tools: ["Python 3.12 + numpy/Pillow (own SoM/SoW format readers, converters and writers)", "C# GADB reader-writer (PowerShell Add-Type)", "Recast v1.6.0 (recastnavigation, own CLI)", "TagTools (Havok 2016 TAG0 reader/writer, ported to Python 3)", "QuickBMS + aluigi shadow_of_mordor.bms 0.4", "Ghidra 12.1.4 (headless, analysis only) + Temurin JDK 21", "w64devkit GCC 16.2 (trace plugin, Recast CLI)", "Shadow of War Dll Loader (Nexus 99, loads the diagnostic plugin)", "texconv (DirectXTex)", "Blender 4.2.3 (headless previews)"]
anti_cheat: "none; single-player only. The mod is data (an extra .arch06 + game.gamedb), the exe file is untouched (SteamStub/Denuvo untouched). The diagnostic trace plugin hooks code in memory and is only installed for tests. Every test ran offline through the offline-mode DLL (never signed in to WB)."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["DeimozZarco"]
date: '2026-10-29'
links:
  - "knowledge/games/middle-earth-shadow-of-war/map-import-toolkit-formats-and-tools.md"
  - "knowledge/games/middle-earth-shadow-of-war/offline-mode-and-local-garrison.md"
  - "knowledge/games/middle-earth-shadow-of-war/goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md"
  - "knowledge/games/middle-earth-shadow-of-war/save-format-decrypt-and-collectible-quests.md"
  - "https://github.com/recastnavigation/recastnavigation"
  - "https://github.com/blueskythlikesclouds/TagTools"
  - "https://www.nexusmods.com/middleearthshadowofwar/mods/99"
tags: [map-import, total-conversion, mashup, new-region, world-map, fast-travel, region-map, minimap, prefab-conversion, material-conversion, texture-conversion, havok, hknp, collision, navmesh, recast, hkai, parkour, terrain, army-screen, nemesis, faction, ai-spawns, quests, lua, trace-plugin, lithtech, firebird]
---

# Map import: Shadow of Mordor's Udûn as a playable new region in Shadow of War

> Shadow of Mordor's first map, **Udûn**, is a playable region in Shadow of War. It has its own crest and fast-travel
> point on the world map, and loads as its own world with SoM's scenery, real 3D collision, parkour and a navmesh. It
> also has a region map, a HUD minimap and a **limited army** (1 warchief + 3 captains, slot counts set in a JSON
> file). Orc stations, patrols and Ghûls fill the white ruins and the western field, and the army's captains get
> Nemesis missions there: duels, trials, hunts and revenge. Everything is data: an extra `.arch06` archive plus
> game.gamedb edits, built by ~150 small tools we wrote (described in the companion
> [toolkit note](map-import-toolkit-formats-and-tools.md)). Verified in the real game by the user over ~90 test
> builds from 2026-10-21 to 2026-10-29: screenshots plus a diagnostic trace plugin's log. The last build fixed the
> remaining spawn problem, and the user declared the import a success.

## Disclaimers
- **Personal project.** The real mod was made for the author's own install. It is **not distributed**, publicly or
  privately, and won't be: the built archives hold converted Shadow of Mordor and Shadow of War assets, so anyone
  else, friends included, builds them from their own copies of both games. This note shares the process, tools and
  research only, in the hope that the framework helps other modders bring other maps, or other ideas, into the game.
- **Only tested on the Steam build** of Shadow of War (build 3095001, Windows 10 22H2) with a Steam copy of Shadow of
  Mordor as the source. Not tested on GOG/Epic/Microsoft Store/console builds, other exe versions, Proton or any other
  platform. Every exe address in this note is for that Steam build only.
- **No game files are in this repo.** Everything SoM- or SoW-derived (meshes, textures, collision, databases, world
  files) is extracted from the user's own copies at build time. The built archive contains converted Monolith /
  WB Games assets, so it must not be uploaded or shared.
- **Play the modded game offline**, as in the other notes here: keep the
  [offline-mode DLL](offline-mode-and-local-garrison.md) installed while the `MapImport` lines are in
  `default.archcfg`, and don't use Online Conquest, Online or Friend Vendettas, or WB's own Garrison (the DLL
  removed). A save with Udûn's region, `Faction_Udun` and its captains references records an unmodded database
  doesn't have, and those modes carry your captains into other players' games.
- The mod sits on top of the author's other private mods (Goblins of War and Falmer databases); the database steps
  below apply to any game.gamedb.

## Credits and prerequisites
Third-party tools (each GitHub tool's source was reviewed for malicious code before it was built or run):
- **Recast** (recastnavigation, Mikko Mononen and contributors), tag v1.6.0, commit 6dc1667, zlib licence:
  <https://github.com/recastnavigation/recastnavigation>. Only the core `Recast` library is compiled, inside our own
  CLI (`recast_cli.cpp`); it builds the Udûn navmesh polygons.
- **TagTools** (blueskythlikesclouds, MIT), commit 70d05f8: <https://github.com/blueskythlikesclouds/TagTools>. Its
  Havok 2016 tagfile (TAG0) reader **and writer** (`TagTools.py`, Python 2), ported to Python 3, are the base of our
  `tag0.py` (collision, navmesh and heightfield blobs). Only `TagTools.py` was used: the repo's prebuilt
  `Dependencies/AssetCc2.exe` (Havok's own converter) and `CollisionConverter.exe` (built against the Havok SDK)
  were *not* kept or run.
- Reviewed but not usable for SoW (Havok 2016): **HKLib** (The12thAvenger, Havok 2018) and **HavokLib**
  (katalash fork of PredatorCZ's, packfiles / animation only). Worth knowing for other Havok games.
- **QuickBMS** (Luigi Auriemma) with his **`shadow_of_mordor.bms` 0.4** script: lists and extracts SoW `.arch06` (LTAR v4,
  Oodle) and bundle `.embb`. <http://quickbms.aluigi.org>
- **Ghidra 12.1.4** (NSA) with Temurin JDK 21: headless static analysis of a memory dump of the running exe, kept
  private outside any repo (no exe patching). <https://github.com/NationalSecurityAgency/ghidra>
- **w64devkit** (Christopher Wellons): GCC 16.2 for the trace plugin and the Recast CLI. <https://github.com/skeeto/w64devkit>
- **Shadow of War Dll Loader** by survivalizeed (Nexus mod 99): loads `x64\plugins\*.dll`, used only for our
  diagnostic trace plugin. <https://www.nexusmods.com/middleearthshadowofwar/mods/99>
- **texconv** (Microsoft DirectXTex): texture decode / re-encode in the texture fixes. <https://github.com/microsoft/DirectXTex>
- **Blender 4.2.3** (headless OBJ previews), **Python 3.12** with numpy, Pillow, capstone, lz4; **.NET** (C# through
  PowerShell `Add-Type`); **GitHub CLI** for the KB PR.
- Ideas studied, not used: *More Captains in Free Roam* by naamionallex (Nexus 255; its plugin is called Roaming
  Captains) for outpost captains (we built captain placement from stock kits instead).
- Our earlier notes this builds on: [Goblins of War](goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md) (gamedb
  format, AttrHash, record sorting), [offline mode](offline-mode-and-local-garrison.md) (every test ran with it),
  [save format](save-format-decrypt-and-collectible-quests.md) (save backup / restore).
- Monolith Productions / WB Games: both games. All content comes from the user's own copies.

## Setup
- Shadow of War, Steam build 3095001, Windows 10 22H2, 16 GB RAM (one heavy job at a time: Ghidra, a world build or
  a 2 GB bundle write can each fill it). Offline-mode DLL v0.12 installed for every test.
- Shadow of Mordor, Steam (app 241930, public branch: build 7348332, unchanged since 2021-09-13), in the same
  library (`udun.arch05` 5.3 GB + `udun_0.arch05` high mips + `udun_weather.arch05`).
- Load order: our archive and database are mounted from their own folder with lines in `x64\default.archcfg`
  (`..\MapImport`, `..\MapImport\mapimport_uNN.arch06`, the region-map and army-stage archives). The database folder
  is mounted after any other mod's database.
- Build host tools as listed under Credits; Python with numpy runs everything else.

## Route and why
- **Data route.** Shadow of War has no public world editor or SDK, but its world files are bundles of documented-by-us
  binary formats, and SoM's Udûn is the same engine family (LithTech Firebird, two format generations apart). So the
  import is a **conversion**: decode each SoM format, write the SoW version, rebuild what has no counterpart (navmesh,
  terrain, AI population) with SoW-native data, and wire the region in through game.gamedb.
- Rejected: rebuilding Udûn by hand from SoW assets (no editor; loses the real layout); overwriting SoW's prologue
  world `worlds\retail\blackgates\blackgates` (SoM uses the same path! that would break the prologue); calling SoW's
  linked Havok navmesh generator from a plugin (harder than Recast + a writer).
- Gameplay objects (spawns, captain spots, missions, travel points) are **not** converted from SoM. They are stock
  SoW object kits copied from Cirith Ungol (`mtnpass`) and placed on SoM's positions, so they run on SoW's own
  systems.
- Diagnostics use a **native-hook trace plugin** (logging only). Every "the game does X instead of Y" problem was
  solved by logging the game's own decisions instead of guessing.

## How the game works (what we had to learn)
Exe addresses are for Steam build 3095001 (`FUN_14xxxxxxx` = Ghidra names on a memory dump). Format layouts are in
the [toolkit note](map-import-toolkit-formats-and-tools.md).

### 1. Archives, bundles and load order
- Files live in LTAR archives (`.arch06` = LTAR v4; SoM `.arch05` = LTAR v3 with zlib chunks). `x64\default.archcfg`
  lists archives and folders; **later lines win**, and the file must stay **CRLF**.
- A world, prefab or UI scene is a **bundle**: a `.bndl` load list (names + sizes + bundle type) plus an `.embb` data
  file. **The newest `.bndl` wins** (patch archives included). A file inside a bundle can only be overridden by
  shipping that bundle; changing a file's size means shipping a `.bndl` with the new size.
- A plain folder override only reaches files that exist as real archive files. Files that exist only inside a bundle
  need an **LTAR archive with an `archivepatchloosefiles.txt`** index (hash-sorted path list) in its root, which is how
  community mod archives are built too.
- Names everywhere are hashed with **sowhash** (the Goblins note's AttrHash): `h = h*0x397 + map[c]` over a
  case-folding table (exe FUN_140C6DA00). Attribute names in databases, Lua section names, bundle sections, object
  names and surface tags all use it.

### 2. Regions, the world map and fast travel
- Udûn reuses the unused **`Regions/Region:BlackGates`** record (the prologue region). Fields that matter:
  `WorldInfo`, `Faction` (army), `Names`, `TravelPoints`, the Unlock / Revealed / **Garrison** predicates (copied from
  Minas Ithil), the zone-map fields (§9) and the quest lists (§12).
- The world map is a 3D prefab scene, `prefabs\ui\worlduimenuws.objres`. Per region it needs a `WorldUIRegionPoint`
  (crest; prop `Region`), `WorldUIMapZoneInfoNode`s (fort / fast-travel icons; prop 0x39108014 = a
  `Regions/ZoneInfoNode` record, whose `LegendNode` row lists `FastTravelPoints`) and a **`WorldUIZoneMap`** (prop
  `Region`). Pressing Map activates the `WorldUIZoneMap` whose Region is the current region (FUN_1418003a0); without
  one the Map button shows black.
- Which region is under the cursor comes from a 512² lookup texture
  (`interface\textures\minimap\worldmapcursorsample.texcpu` + its BC1 `.tex` copy): blue = region slot ×23, mapped to
  regions by `_StructuresWorldMapMaterialOverrideGroup`; green = border lines, red = glow. Icon heights must sit on
  the map surface (stock −96,700…−99,900).
- **Fast travel:** a `Regions/TravelPoint` record (clone of a zone-edge point with no unlock item) in the region's
  `TravelPoints`, plus a `TravelPoint` object (prop `TravelRecord` 0x09B4B8B3) at the arrival spot in the world's
  `.objres`. Trace: Fast Travel → `SetRegion` → world load → player at the TravelPoint.
- **World Lua can redirect.** The prologue world's script `IBG_Skip_SC` sends any save past the intro to Minas Ithil
  (`System:LoadWorld(DBWorldInfo.MinasIthil)`). That was why every trip landed in Minas Ithil.

### 3. A world
- A world is a `KrakenBaseLevel` bundle `worlds\retail\<w>\<w>`: `.objres` (object list + embedded databases +
  physics + parkour + volumes), `.wldclnt` (scene list: prefab instances), `.inst` (world prefab), `.terrain` + loose
  height tiles `<w>.hm_XX_YYter.tex`, `.hkai` (navmesh), `.scripts` (Lua), `.uis` / `.uiwd` (map shapes), `.veggrid`,
  `.wldmsh`, `.cres`. A **`WorldInfo`** record points the region at the world and carries climate, AI budget, scenario
  overrides and **game-mode bundles** (faction NPC assets).
- Udûn lives in its **own world** `worlds\retail\udun_world\udun_world`, a clone of the prologue world. The new name has
  the same length as `blackgates`, so every internal path renames in place. Its `WorldInfo:Udun` points at it.
- World **root objects at the origin** (`WorldCollision` PhysicsBSP, `WorldModelBase WMB_00`) carry the world's
  collision and scenery: move them and everything falls away.
- **World Lua:** a world's `.scripts` is one Havok Script chunk, `local section_<sowhash(.scripts resource path)> = {…}`,
  and the objres `SCRB` bindings carry the same hash. A copied world must rename both, or none of its object scripts
  run (no error).

### 4. Scenery: prefabs, materials, textures
- Static scenery = scene-list rows (`.wldclnt`, WDSC v9 in SoW / v5 in SoM): prefab path, transform, bounds,
  **variant** (= which LOD-set record of the prefab is drawn) and a draw-distance field. SoM rows carried 0/−1 there
  (nothing drew). Udûn: 5,418 instances of 395 prefabs, plus 228 world-prefab records.
- **Prefabs** (`.inst`, PRFB v5 → v8): per-record LOD tables, vertex declarations, buffers, submeshes, materials,
  80-byte render pieces. SoW splits positions into stream 0 and everything else into stream 1. Record byte `b20` =
  number of leading submeshes drawn **only in the shadow pass**.
- **Materials** (LTMI v4 → v8): 700 of Udûn's 1,030 SoM materials use shaders SoW no longer has. Each becomes a stock
  SoW template material of the same (or a mapped) shader with SoM's textures in the matching slots. A shader's
  vertex inputs must match the mesh: SoW's `specular.fxo` reads **COLOR0**, so a mesh laid out without colour silently
  isn't drawn.
- **Textures** (TEXR v3 → v8): header rewrite, SoM's separate `.tex0` top mip merged, mips completed to 1×1. Normal
  maps need **blue = 255** (SoM has 0 → nearly black lighting). Specular maps differ: SoM `_s` B = gloss, SoW `_s` B =
  roughness and R = reflectance class (170 for dielectrics), so SoM's maps read as chrome until converted.
- **Streaming stamps:** SoM draws whole areas far away as baked low-detail "stamps". Some structures exist only
  there (the south Black Gate), with one blurry atlas texture.

### 5. Ground: render terrain and collision heightfield
- SoW draws ground from `.terrain` (TERR v9: quadtree cells, L16 height tiles 64+4 samples with borders) and collides
  with a **separate baked Havok heightfield** (513² u16 samples inside the world objres's WorldPhysics TAG0). Editing
  the render tiles changes nothing for collision. Collision heights must be read through the Havok data itself
  (instance translation + int-to-float scale + heightScale), never from a fit to the render tiles.
- Heightfield samples carry a **shape tag**; 895 = `Air` = no collision. The prologue's out-of-street samples all had it.
- SoM has **no heightfield**: its ground is meshes (terrain prefabs, vertex-painted 3-layer blends). We draw SoW
  terrain tiles on SoM's ground and paint them from SoM's vertex paint with four Cirith Ungol terrain layers (grass,
  stony dirt, mud, rock). All tiles must sample **one** surface on the depth-1 lattice, or tiles of different detail
  crack along their edges.

### 6. Collision
- SoW world collision is **Havok 2016 hknp** in TAG0 tagfiles inside the objres (`hknpCompoundShape` of
  `hknpCompressedMeshShape`s, convex polytopes, the heightfield). SoM Udûn's collision is **Havok 2012 hkp** in its
  objres (chunk 0xb9e81cf3): one static compound of 3,311 instances (2,612 compressed meshes, 444 convex hulls, 255
  boxes), already in world space.
- The compressed-mesh **tree layout is the same** in both versions, so meshes convert by copying the tree and
  building the new parts (SIMD BVH, key fields). Heightfield faces **can't be climbed**: climbing needs real mesh
  collision.
- **Surface tags** (u16 per triangle run / convex shape / heightfield sample) = `(v + (v >> 16)) & 0xFFFF` of the
  sowhash of a `Surfaces/Surfaces` record name (`dirt` 32231, `stone` 5941, `wood` 47942, `Air` 895, `WallRun` 7846).
  Every SoM tag in Udûn exists in SoW. Unknown tag = no surface = every flag false.
- Every TAG0 we write must have a **THSH hash for every ITEM and PTCH type**, or the game's tagfile loader crashes.

### 7. Parkour (Talion's movement)
- Four kinds of data drive traversal: collision, surface tags, **context-action lines** (objres `CADB` chunk:
  `Edge_Hang`, `Edge_Pullup`, rails, poles, ropes, ladders, ziplines) and the **navmesh**. Talion's moves are a
  behaviour graph (`behaviors\player\player_elf.bvr`, GADB): a transition fires when its predicate tree passes, and
  prompts show when the same autopicker passes.
- Hang exits need **`Predicate.CanJump`**: a navmesh point near the target (box search along DistanceRange) plus a
  vertical physics ray within `MaxPhysicsOffsetY` (30 cm for Pull Up, 1 m for Drop). Havok's closest-point test assumes
  faces wound **counter-clockwise seen from above**; a face wound the other way is found by the box query but never
  gives a point (no landing, no prompt).
- SoM ships climb lines per streaming area (`blackgates.ss_*.cntx`) besides the world CADB; both must be converted
  (CADB v1 → v3).

### 8. Navmesh
- `.hkai` = `HKAI` container holding a Havok 2016 TAG0 with `hkaiNavMesh` (faces, half-edges with opposite links,
  vertices in metres, clearance caches, generation settings, user edges for AI mantles/jumps).
- SoM's navigation (LithTech PATH) has no SoW counterpart → we generate one with Recast over the same collision the
  game uses. Settings that work: cell 0.25 m, height 0.05 m, agent height 2 m, **step 0.5 m** (0.33 m split the ground
  into thousands of pieces = invisible walls for mounts and AI), no erosion, no ledge filter. Faces must be wound
  normal-up and lie within 30 cm / 1 m of the collision.

### 9. Region map and minimap
- **Region map** = a tiny world section (`prefabs\ui\zonemaps\<r>\<r>.bndl`, type UI_ZoneMap) streamed in and filmed
  from above: a map mesh in ±256 map units (UV = pos/512 + 0.5), the `zonemap.fxo` material and overlay texture, its
  own collision (the cursor, marker and icons are placed by a vertical ray onto it), and world stubs. Region fields:
  `ZoneMapTexture` A86E0DAB, `ZoneMapBundle` 2C8E024A (`interface\bundles\maps\<r>.bndl` = the world's `.uis` / `.uiwd`),
  `ZoneMapWorldSection` E6EF7533. World ↔ map conversion uses the **`.uiwd` bounds**; the icon list is the `.uiwd`
  entries (type 1 = travel point).
- **Minimap (HUD):** the world's `MapRegion` object (centre + half-extents) and its `MapCanvas` sections: filled
  triangles in the `.uis` (UISH v3, keyed by sowhash of the canvas object name) and outline loops in the `.uiwd` blob.
  The prologue had a ±128 m box and 7 street shapes; we refill the canvases from the navmesh in three height bands.

### 10. Army (Nemesis hierarchy)
- `Region.Faction` → `Faction/Definition` → `Rows` (`Faction/Rows`: `Rank`, **`ColumnMax` = slots**, `ColumnLocks`,
  `HenchmenRows` = bodyguards from captain rows, `Locations` / `LowPriority` / `LastResort` = where members may stand,
  `SimEventGenerationSetup` = which missions they get). BlackGates had `Faction_None`.
- New members appear through **`Faction/Events/PromotionEventSetup`**, indexed by **row index**: `NumSimEvents[empty
  slots]` new orcs per time advance. The stock `Default` table gives rows 0–2 (overlord / warchiefs) nothing, so a
  faction whose row 0 is a warchief and row 1 captains never fills with it.
- **GADB bools are bits** of the record's first value word, and the layout's `first` field is a **bit index**. A
  repacker that re-lays bools out as slots scrambles them (our older Goblins/Falmer builds had this bug; repaired).
- The army screen is SoW's own: a tiny scene bundle per `Faction/World/Faction` (`Instance`), a member grid computed
  from rows/columns (`RowGap` 185, `ColumnGap` 175), a fort diorama from `Faction/World/Fort/Setup` pieces, and
  `WorldUIFixedFactionMemberPos` slot positions. SoM's army screen is a separate small world and can't be ported as is.
- Hostility: every enemy tribe and region shares alignment `Orc_FactionA`. The stock `Goblins` alignment (hates
  orcs and the player) is already a third side; a new faction would clone it.

### 11. AI population
- An area is populated by **object kits** in the world objres: e.g. `StatOrc_NN.*` (captain spot
  `AISpawnerAmbientLocation` with `LOCATION=<AI/SpawnAmbient/Locations record>`, gang, caragor, banner orc, grunts,
  spawn sets, node set, script objects), activity-spot `Node*` kits, patrol routes `SP_NN` + `Sentry_*`, ranging packs,
  Ghûl kits + forage-node kits. Kits wire up through the ObjectDB (embedded GADB), **SCRB** (object → Lua bindings),
  **ONLS** (name groups) and the world `.scripts`.
- **Locations need areas:** every `AI/SpawnAmbient/Locations` record names an `Areas` record, which must exist as an
  `AreaBrush` volume in the world's **VOLM** chunk. The spawner must stand inside it. SoM's Udûn areas (`BG_Ruins_*`,
  `BG_Wild_*`) are still in SoW's database and their brushes merge from SoM's VOLM.
- Spawn sets resolve `Predicate=AutoPredicate` in the kit's Lua (AmbShort / AmbLong by distance). `AmbShort` only spawns
  out of the player's line of sight within 60 m, which works among walls but never in an open field. Stations
  come in day-only / night-only sets.
- Engine-wide caps: `WorldInfo.AICount` → `AI/Count/Configuration` (MaxAmbientAI 100; Low/Med/High 30/10/10) and
  per-category scenario caps (`AmbStaticOrcs` 32, `AmbGhulCount` 10) in the WorldInfo's `ScenarioOverride` list.
- **Spawn height:** stock spawners sit **~2 m above the ground** (Cirith Ungol: 7,149 `AISpawnerAmbientNormal`,
  median +2.02 m over the navmesh), and the AI drops onto the floor. A spawner at or under the floor spawns the orc
  under it.
- Captain posting: captains are assigned to locations at run time (`PriorityForAILocations` per area;
  `MustEvalQuestToAssign` on locations). Warchiefs don't roam: they appear through missions.
- The retail exe still formats its AI spawn debug messages through stub loggers (FUN_141a9fbb4, FUN_1419c83ac,
  FUN_140166520), gated by bytes such as 0x142a35409 / 0x142a34d8c. Redirecting the stubs and setting the bytes gives
  the game's own reasons ("LOS Predicate failure", "Hasn't passed evals", "FactionMember not found"). With those bytes
  set, **travelling out of the world crashed** (spawner-list assert), so turn them on for single diagnosis runs only.

### 12. Nemesis missions (quests)
- A mission = a **db record** `Quest/Quests` (job setup, objectives, `Predicates`: `SimEventPredicate` + **`RequiredFaction`**,
  `Overrides` for revenge variants) + a **`Quest` object** in the main world (`QuestRecord`, `TriggerObject`,
  `WorldSection0` = its section bundle) + its own **WorldQuest section bundle** (objres, Lua, navmesh piece, map
  shapes). The region's `NemesisQuests` / `AllNemesisQuests` / `AdditionalQuests` lists make them available.
- A captain's row `SimEventGenerationSetup` generates sim events (PowerStruggle: Duel, Trial…; Hunting: FeastSingle…;
  Revenge; Location). A sim event becomes a visible mission only through a listed quest whose predicate names it and
  whose `RequiredFaction` is the region's army.
- Revenge (captain who killed Talion) = an `Overrides` entry to `<mission>_Revenge`, sharing the base mission's world
  content.

## Build steps (the framework)
The order we used; each step is a build with an installer that checks the previous state, backs up the saves and the
archcfg, copies the archive (md5 check) and swaps the archcfg line. Tool names are described in the
[toolkit note](map-import-toolkit-formats-and-tools.md).

**0. Recon.** List both games' archives (QuickBMS; `ltar3.py` for SoM), extract SoM's Udûn bundle (`som_bndl4.py`)
and SoW's prologue + Cirith Ungol worlds, dump every object (`som_world_objects.py`, 42,006 SoM objects), compare
format versions (`hdrs.py`), render a top-down overview from SoM's own map art (`udun_overview.py`).

**1. Region + world-map icons + travel point** (database + world-UI prefab).
- `MapImport.cs` on game.gamedb: `Region:BlackGates` made playable (in `Regions/Global.RetailRegions`, Minas Ithil's
  predicates), its `Regions/ZoneInfoNode` records and a cloned legend row whose region-specific links all point at
  BlackGates, a `Regions/TravelPoint` (clone of a zone-edge point) in `TravelPoints`.
- `add_worldmap_icons.py` + a JSON spec: clone a stock `WorldUIRegionPoint` and `WorldUIMapZoneInfoNode`s into
  `worlduimenuws.objres` at the Black Gate spot (height on the map surface), later the `WorldUIZoneMap` (§9).
  Ship the objres with its size-patched `.bndl` (`patch_bndl_size.py`).
- `worldmap_region.py`: paint Udûn's slot into the cursor-sample texture (`.texcpu` + BC1 `.tex`), keeping icons
  ≥ 12 px inside the painted area.

**2. Own world.**
- `clone_world.py`: prologue world → `worlds\retail\udun_world\udun_world` (bundle, core files, loose tiles; same-length
  rename, prefab header hash = sowhash of its new path). `WorldInfo:Udun` points at it.
- `patch_bg_scripts.py`: the intro-skip redirect's condition → `false`, padded to the same length.
- `objres_add.py`: the arrival `TravelPoint`. `UdunClimate.cs`: Udûn gets its own climate with a daylight default
  pattern (the prologue's `CaveLT01` has no sun).

**3. Assets.**
- `tex_pipeline.py` (`som_tex.py` + `tex_fix.py`): every SoM texture → SoW TEXR v8, normal maps blue = 255, specular
  maps converted (R 170, B inverted).
- `mat_catalog.py` (stock SoW materials by shader) → `mat_convert.py`: LTMI v4 → v8 on templates.
- `prfb_convert.py`: every PRFB v5 → v8 (records widened, streams split, submeshes widened with LOD metrics,
  generated normals/tangents for layouts without them, header decl counts kept in sync). Proven first on one tent
  by swapping a stock prop (`prfb_transplant.py`, `build_swaptest.py`).

**4. Scene.** `build_udun.py` in one pass: append every converted instance to the scene list (`wdsc_add.py`) at the
SoM → SoW offset **(+8846, −16203, −888) cm**; clear the prologue's own scene rows, objects and street collision out
of the way (`world_clear.py`, never the origin root objects); set the arrival; write the terrain. Then
`world_pieces.py` adds SoM's world-prefab pieces (shanty bases etc.) as ordinary scene rows.

**5. Ground.** `udun_ground.py` rasterizes SoM's ground meshes into a heightmap; `terrain_write.py` writes render tiles
+ collision heightfield (tags set to `dirt`, height band re-based to Udûn's span, all 16 root quadrants filled).
Later passes: `som_paint.py` + `ground_paint.py` (SoM's vertex paint on SoW terrain layers), `ground_surface.py` (one
crack-free surface, fills under rock walls and in SoM's terrain holes), `paint_split.py` (dirt-painted rock ledges
split into a soil-material prefab).

**6. Collision.**
- `som_collision.py` decodes SoM's collision (with the borrowed-vertex fix, Gotcha 18).
- `som_to_hknp.py` converts the 2,610 meshes to hknp compressed meshes in one compound.
- `som_props_hknp.py` adds the 699 convex / box props as `hknpConvexPolytopeShape`s.
- `build_udun.py --som-physics` swaps the blob into the world's WorldPhysics. Verify with `hknp_mesh.py`: every
  triangle matched SoM's to 0.008 cm.

**7. Parkour.** `cadb.py` converts SoM's world CADB (v1 → v3, `build_udun.py --som-cadb`) and the 5 streaming areas'
climb lines (52,668 lines).

**8. Navmesh.**
- `navmesh_build.py` runs Recast over the in-game collision (SoM meshes + props + heightfield quads) in tiles and
  stitches them.
- `hkai_patch.py --replace` writes it into the world `.hkai` with faces wound up and clearance caches extended.
- `hkai_winding.py` checks the winding.

**9. Visual clean-up.**
- `lighting_patch.py`: move the prologue's cave light volume and atmosphere box out of Udûn (loose `day01.objres`).
- `clutter.py`: clear the prologue's ObjRes.Clutter street pieces.
- `scene_sink.py`: sink rows SoM never shows (raised lod −1 twins, proxy-only pieces, floating kit copies).
- `stamp_clip.py` + `stamp_retexture.py` + `stamp_vcol.py`: the south Black Gate from the damaged outpost stamp,
  with tiling UVs and a colour stream.
- `edge_mountains.py`: SoM mountain pieces to wall off open map edges.
- Forge towers: SoM's wraith-world towers are converted with stone textures graded to Morgul green, and lowered 2 m.

**10. Region map + minimap.**
- `zonemap_build.py`: from a stock zone-map prefab as template, a grid mesh of Udûn's ground in map space, an
  overlay texture and the material.
- `zonemap_hf.py`: map collision as a heightfield rescaled from the world's.
- The `.uis` / `.uiwd` with Udûn's bounds and a travel entry go in the map bundle.
- `MapZone.cs`: the three Region strings plus `HierarchyMapScale` / `CameraHeight` / `MapCanvasStaticDefaultVisibility`
  from Minas Ithil.
- `add_worldmap_icons.py`: the `WorldUIZoneMap` object.
- `minimap_build.py`: the MapCanvas shapes from the navmesh. The world's `MapRegion` is widened to the Udûn square.

**11. Limited army screen** (`UdunArmy.cs` via `udun_army.ps1`, settings `udun_army.json`).
- `Faction_Udun` = clone of `Faction_MtnPass` with SoM's structure: no overlord row, one warchief row whose
  bodyguards come from the captain row, one captain row. `ColumnMax` comes from the JSON (`warchiefs` 1,
  `captains` 3, `overlord` off), so opening slots later = edit the numbers and rebuild the database (1–2 min).
- Udûn's own `PromotionEventSetup` (row 0 `[0,1]`, row 1 `[0,1,2,3]`: refill every empty slot) and timed events.
- `Region:BlackGates.Faction` = `Faction_Udun`; `WorldInfo:Udun` uses Cirith Ungol's game-mode bundles (faction NPC
  assets).
- Army stage: we tried SoM's look (stage, pedestals, rings) as fort-piece sections (`som_bndl4.py`,
  `build\stage*_build.py`). The user settled on **Minas Morgul's stock fort setup** with our own slot positions
  (warchief on the lower wall, captains on the ground, within the cursor's reach).
- Bool repair (`RepairBools.cs`) runs first on any database built with the old repacker.

**12. Outpost and population** (all in the world objres; `kit_copy.py` is the core).
- `ruins_outpost.py`: 10 open-air `StatOrc` stations on SoM's 10 white-ruins captain spots on the main navmesh
  island, locations `Udun_Ruins_Main / _South / _West`, every third with olog grunts, the AutoPredicate baked to the
  Lua's result, time-of-day off, plus their activity-spot kits.
- `volm.py merge_brushes`: SoM's 22 Udûn `AreaBrush` areas into the world VOLM.
- `ruins_patrols.py`: SoM's ruins routes as SoW sentry routes, plus ranging packs.
- `ruins_props.py`: fire pits and grog spots.
- 5 `Cap_LostHearth` captain kits for a guaranteed outpost captain (`CapCheckWilderness`).
- `ruins_more.py`: stations at SoM's densest spawner clusters.
- `west_camps.py`, `west_spawns.py`, `west_fix.py`, `west_more.py`: western field camps after SoM's own layout
  (per-area locations, SoM routes as patrols, slave gangs, caragor packs, Ghûl kits + stock forage-node kits), an
  open-ground predicate `UdunOpen` (20–90 m any, 5–20 m off-screen only), second stations, fill orcs at 25–90 m.
- db: `Udun_*` locations with `PriorityForAILocations` 4. Udûn's own scenario override list `UdunBase`
  (`AmbStaticOrcs` 64, `AmbGhulCount` 20) and AI budget (`AI/Count:Udun` 160 ambient).

**13. Missions** (`quest_extract.py`, `quest_port.py`, `navheight.py`; db in `UdunArmy.cs Quests`).
- Ported from Cirith Ungol: 2 Duels (captain vs captain), Trial_Caragor + Trial_Graug (captain vs beasts), 2
  FeastSingle hunts (Talion vs captain) and their Revenge overrides.
- Each section bundle is renamed to `worlds\retail\udun_world\sectionsandlayers\quests\ud_*`: Lua section hash, SCRB
  hash, `.inst` hash, veggrid path, `MP_` → `UD_` strings in place. The mission is moved rigidly to a site in the
  western field, with heights re-fitted object by object from Cirith Ungol's navmesh to ours.
- The main-world `Quest` + trigger objects come via `kit_copy` and are put back on the ground (`u88_fix`).
- db: cloned quest records with `RequiredFaction = Faction_Udun`, lists `PowerStruggle_Udun` / `QuestAdditional_Udun`
  on the region, the captain row's `Udun_Captain` generation setup (PowerStruggle, Hunting, Revenge, Location).

**14. Spawn heights** (`spawn_audit.py`, U94). Every spawner / AI node goes to the **real floor** (the up-facing
collision surface nearest the navmesh, never more than 0.35 m under it) **plus the stock offset of its class**
(spawners +2.0 m, menace / route / goto nodes +1.9–2.0, node sets +0.05, vignette sets +0.5), at least 0.3 m under any
ceiling. Spawners in walls, sealed pockets or off the navmesh move to the nearest clear main-island spot (≤ 10 m).

**15. Packaging.** `ltar.py <tree> <out.arch06>` (stored LTAR + patch list) → copy to `<game>\MapImport\`, md5
check, one archcfg line per archive (byte-exact CRLF replace), the database in `MapImport\database\game\`. The world
bundle is ~2.1 GB; the region-map and army-stage bundles ship as separate small archives.

## Verification
- **Oracle:** the user played each build (game closed for every install) and took Steam screenshots. The **trace
  plugin** (`MapImportTrace.dll`, loaded by the Dll Loader) logged the game's decisions with exe call stacks:
  `SetRegion`, world loads, CanJump evaluations, navmesh queries, AI spawn reasons. F12 (the Steam screenshot key)
  logged Talion's position (`MARK pos=`, feet + 1.04 m) with the same timestamp as the screenshot. Screenshot
  contact sheets labelled with the nearest mark (`ss_sheets.py`) matched images to positions.
- **Offline checks:**
  - byte-identical round trips for every writer (objres / OBJL / GADB, kit copies with nothing added, TAG0 with all
    742,627 values equal, `.uis`, LTAR);
  - `hknp_mesh.py` structural checks on every collision blob;
  - `hkai_winding.py` on every navmesh;
  - stock-world calibrations (spawner heights, record formats) before applying a rule to ours.
- **User-confirmed in game:** fast travel in and out; ground, scenery and lighting; climbing / Pull Up / Drop / Leap
  Behind / ropes / ziplines across the map; mounts (mostly); region map with in-map fast travel; minimap; army screen
  filling on time advance with battle reports; outpost activity, patrols, Ghûls foraging; captains roaming the field;
  duels, trials, hunts and revenge missions.
- **Final test (U94, 2026-10-29):** after the spawn-height pass, no orc spawned underground or inside the white ruins'
  walls / floors any more (U93 had both). With that, the user called the map import a success.
- **Not verified:** any platform or build other than Steam 3095001; co-existence with online modes (never tested,
  play offline).

## Gotchas
1. **Fast travel to the new region landed in Minas Ithil.** **Cause:** the prologue world's Lua `IBG_Skip_SC`
   redirects post-intro saves. **Fix:** set its condition to `false`, padded to the same length (found by tracing
   SetRegion → OnWorldLoad → LoadWorld).
2. **The new travel icon sent every trip to Gorgoroth.** **Cause:** a cloned legend row kept Gorgoroth's links.
   **Fix:** replace every region-specific link in cloned rows.
3. **Hovering Udûn showed another region.** **Cause:** the region under the cursor comes from the cursor-sample
   texture, and our first box sat too close to the icon. **Fix:** paint the slot generously.
4. **archcfg edits broke loading.** **Cause:** `sed -i` turned the file to LF. **Fix:** byte-exact CRLF replaces only.
5. **Override files ignored.** **Cause:** folder overrides don't reach bundle-only files. **Fix:** LTAR archive with
   `archivepatchloosefiles.txt`.
6. **Endless fall after clearing the prologue street.** **Cause:** the world root objects at the origin (collision
   BSP, WMB_00) were moved with the rest. **Fix:** never move origin root objects.
7. **Fell through new ground everywhere but the old street.** **Cause:** heightfield shape tag 895 (`Air`). **Fix:**
   tag written samples `dirt` (32231).
8. **Converted scenery invisible.** **Cause:** SoW's instance draw-distance field (SoM rows had 0 / −1). **Fix:**
   400,000 for ground, 30,000 default.
9. **World black.** **Cause:** the cloned climate's default pattern was the prologue cave (`CaveLT01`). **Fix:** own
   climate, daylight pattern.
10. **Crash on travel with the full map.** **Cause:** the converter added a vertex declaration without updating the
    PRFB header's decl counts (loader arena overflow); not the 2 GB size. **Fix:** keep header fields in sync + a
    check pass.
11. **A sharp light/dark plane and cave fog over the map.** **Cause:** the prologue's cave light volume and
    atmosphere box in `day01.objres`. **Fix:** move them away in a loose override, same size.
12. **Chrome terrain / black normals.** **Cause:** SoM `_s` B = gloss, `_n` B = 0. **Fix:** convert `_s` (R 170,
    B = 255 − B), `_n` blue = 255.
13. **Ground drawn in only part of the map.** **Cause:** the cloned terrain had cells in 4 of 16 roots. **Fix:** add
    depth-1 leaf tiles everywhere (`fill_quadrants`).
14. **No climbing on walls, even tagged WallRun.** **Cause:** heightfield collision can't be climbed. **Fix:** real
    3D mesh collision converted from SoM.
15. **Crash stepping off structures.** **Cause:** 177 SoM primitives `(a,b,c,b)` read by Havok 2016 as custom
    primitives. **Fix:** write them as proper triangles.
16. **Crash on travel / at Start after adding props.** **Cause:** TAG0 written without THSH hashes for some
    ITEM / PTCH types (`hkUint16/64`, `hkArray<…>`). **Fix:** every written TAG0 must pass a "no unhashed types" check.
17. **Pull Up / Drop missing everywhere in Udûn.** **Cause:** our navmesh faces were wound normal-down; Havok's
    closest-point test rejects them (the box query still finds them). **Fix:** orient every face up; check winding.
18. **Holes, spikes and sink-through on crate stacks / stairs.** **Cause:** "borrowed vertices": SoM's mesh packer
    adds shifted components, so a vertex quantized to −1 borrows from the next field and SoW decodes it on the far side
    of its section (3,369 vertices). A second case hid where a primitive's leaf box spans the whole section. **Fix:**
    pick the reading that lies inside the section's BVH leaf boxes; if both do, pick the one with the fewest
    collapsed edges.
19. **White ruins, shanty towns, north-gate wood: no climbing.** **Cause:** SoM's per-streaming-area climb lines
    (`.cntx`) were never imported. **Fix:** convert and merge them (52,668 lines).
20. **Surface tags decoded wrong.** **Cause:** the fold is `(v + (v >> 16)) & 0xFFFF`, not XOR (XOR matched `dirt` and
    `Air` by chance).
21. **No landing on bridge decks.** **Cause:** the Recast input took heights from a render-tile fit that was invalid
    after re-basing the height band (a phantom plane). **Fix:** always read collision heights through the Havok data.
22. **Pale untextured coverings / black flat shapes.** **Cause:** SoM shadow proxies in records drawn by the main
    pass (converted to visible shaders). **Fix:** don't place proxy-only records; map shadow-only materials to
    z-prepass; set `b20` right.
23. **A wall disappeared after a material swap.** **Cause:** the new shader reads COLOR0; the stamp's vertex layout had
    none. **Fix:** re-lay the range in a declaration with a white colour stream.
24. **See-through holes in a clipped stamp.** **Cause:** clipping by triangle centroid dropped big faces that only
    touched the kept area. **Fix:** sample points over each face; box-map UVs per face, not per vertex normal.
25. **The world-map Fast Travel option to Udûn vanished** (twice). No single save field explained it. **Fix:** restore
    the save from before the bad session to **both** save locations (Steam cloud folder + `%LOCALAPPDATA%`) with the
    same build installed. Keep a save backup per install.
26. **Army screen: one empty slot, nobody ever promoted.** **Causes:** (a) our gamedb repacker scrambled bools (bit
    indices treated as slots: `FillFactionOnInitialization` off, etc.); (b) the stock promotion table is per row index
    and gives warchief rows nothing. **Fix:** repair bools; Udûn's own promotion table.
27. **No orcs at all in the region.** **Cause:** `WorldInfo:Udun` used the prologue's game-mode bundles (no faction NPC
    assets). **Fix:** Cirith Ungol's.
28. **Stations copied, ruins empty.** **Causes, in turn:** cave stations (`SpaceCave` / `SpaceCliffs` categories forced
    off outside cave volumes); missing `AreaBrush` areas; the kit Lua never ran (the world kept the prologue's Lua section
    hash) so `AutoPredicate` never resolved; 7 of 10 stations night-only. **Fix:** open-air kits, merged areas, renamed
    Lua section (`section_6274b3ed`), baked predicates, time-of-day off.
29. **Crash travelling from Udûn to Minas Morgul.** **Cause:** the trace plugin's spawn-debug bytes. **Fix:** set them
    only for single diagnosis runs that stay in the world.
30. **Captains never posted to the ruins.** **Causes:** SoM's areas had `PriorityForAILocations` 0; the region had no
    quest lists. **Fix:** priority 4, `MustEvalQuestToAssign` off on Udûn spots, Nemesis quests; stock outpost captain
    kits with their own captain check.
31. **Open-field camps never spawned.** **Cause:** `AmbShort` needs the spawn point out of sight within 60 m (walls
    make the ruins work). **Fix:** a stock-style predicate with no sight check up close.
32. **Ghûls spawned singly and stood still.** **Cause:** no `AmbMonster` / beast-roam nodes in the world. **Fix:** stock
    Ghûl forage-node kits.
33. **Mounts and AI stopped at invisible lines.** **Cause:** Recast step height 0.33 m split the western ground into
    pieces along small steps. **Fix:** 0.5 m.
34. **Mission markers 13–24 m in the air.** **Cause:** stock Quest objects stand on ridges above their arenas where the
    source navmesh has no surface. **Fix:** re-ground markers after the move.
35. **Orcs spawned underground and inside the ruins' floors / walls.** **Cause:** our snap tool put spawners *at* the
    navmesh using each polygon's mean height (half ended up below it; the navmesh itself lies ~0.25 m above the real
    floor). Stock puts spawners ~2 m above the floor. **Fix:** step 14 (confirmed in game). Rule: never snap spawners
    onto the navmesh.
36. **Quest sections' `.bndl` lost an entry on rebuild.** **Cause:** our bundle writer rebuilds the `.bndl` from the
    `.embb` entries and drops the zero-size `.wldmsh` entry stock sections list. **Fix:** keep the original `.bndl`
    when sizes don't change.
37. **Region map: black, then wrong mesh, offset marker, floating marker, no travel icon.** **Causes:** no
    `WorldUIZoneMap` for the region; the template's mesh name in an objres chunk; the `.uiwd` bounds still the
    prologue's; the map collision still the template's; no `.uiwd` travel entries. **Fix:** step 10.
38. **Minimap showed a bit of street, black elsewhere.** **Cause:** the prologue's ±128 m `MapRegion` and 7 street
    canvases. **Fix:** step 10.
39. **Invisible forge towers you could climb.** **Cause:** SoM's tower prefab uses wraith-world FX materials. **Fix:**
    convert with stone materials; the converted prefab sat 2 m above its collision, lowered.
40. **Agent / host ops:** the desktop app froze when parallel sessions ran heavy jobs → one heavy job at a time on
    16 GB. An installer run twice overwrote its own backup → installers refuse unless the current archcfg names the
    previous build. F12 position marks can lock onto stale memory (e.g. after drake travel) → the trace filters
    implausible positions, and screenshots are the fallback.

## Known issues (open, by the user's choice)
- North-gate burnt-foundation ramp: Talion walks up the middle of the ramp inside its solid collision wedge
  (waist-deep). The converted collision is correct, and stock SoW uses the same shape; left as is (that area is the
  creature / tribe test zone).
- Tents / tarps: the cloth sits 1–1.4 m above SoM's simpler tent collision.
- A few mount snags remain (ruins stairs, a raised stone platform, a narrow gorge).
- Garrison Deploy can't target Udûn (an enemy army region); fine for a test map.
- Udûn's mission icons show on the minimap and in the field, but not on the region map.
- No day/night cycle in Udûn (stations run day-only data).
- SoM's own army-screen look (stage, pedestals, rings) didn't render; Minas Morgul's stock fort is used.
- Outpost alarm, teardown mission (Talion vs warchief) and red outpost highlight were not built. They move to future
  mod ideas, along with the third-faction test this framework was set up for.

## Assets
No generated art. Every mesh, texture, material, collision piece and climb line is converted from the user's own
Shadow of Mordor install. Fill materials (terrain layers, Morgul stone grade, soil, north-gate brick) are stock
Shadow of War materials from the user's install.

## Cost and time
About 8 days (2026-10-21 → 2026-10-29), roughly 25 sessions, 94 world builds (U1–U94), 18 army databases, 6
region-map builds, 3 army-stage builds and 24 trace-plugin versions. The world bundle is ~2.1 GB; a build that
rewrites it, plus packing, takes 10–20 minutes on the test machine.

## Open questions
- Why the region map doesn't show mission icons (suspects: the region-map bundle's `.uiwd` / MapCanvas entries, or the
  quest type's zone-map flag).
- Whether one region can host two armies at once (needed for a third faction; `GameModeFactionOverrides` /
  `InvasionFaction` show switching, not two at once).
- The remaining burnt-ramp clip and whether stock has the same behaviour.
- Next maps: Núrn (SoM's second map) and the SoM DLC maps should follow the same framework; the formats are the same.
