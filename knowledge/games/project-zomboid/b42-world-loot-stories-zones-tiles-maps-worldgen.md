---
kind: game
title: 'The Build 42 world for modders: loot and foraging, world stories, zones, persistent world systems, tiles and moveables, map files, worldgen and basements'
game: Project Zomboid
games_also: []
game_version: 'Build 42.21.0 (Steam, Windows 10). A survey: the install''s media/ files and Lua (media/lua/server, shared and client), the media/maps folders and javap listings; nothing was built or run in game for this note'
platform: windows
engine: java
route: loader-api
tools: ["Project Zomboid Lua (Kahlua) mod API", javap, "TileZed/WorldEd community forks", "in-game world map editor (ISUI/Maps/Editor)"]
anti_cheat: 'none (single player and servers you host)'
status: in-progress
agents:
- Devin (SWE-2 Medium)
humans: [Alistair-Afton]
date: '2026-10-12'
links:
- "https://pzwiki.net/wiki/ProceduralDistributions"
- "https://pzwiki.net/wiki/Tile_properties"
- "https://pzwiki.net/wiki/Mapping"
tags: [b42, world, loot, distributions, foraging, world-stories, metazones, zones, global-objects, farming, fishing, tiles, tiledef, moveables, seating, spritemodels, maps, map-mods, stashes, worldmap, worldgen, basements, erosion]
---
# The Build 42 world for modders: loot, stories, zones, world systems, tiles, maps and worldgen

> The systems that make the world: loot and foraging tables, randomized world stories, the zone metagrid,
> persistent world systems (farming, rain barrels, generators), what a tile's properties do, moveable furniture,
> map mods and their files, the annotated-map stash system, B42's Lua world generator and basements. Most of it is
> Lua tables or text files a mod extends. It's a survey of a 42.21.0 install; nothing was built and run in game.
> Start with the [orientation note](b42-modding-orientation-layout-lua-runtime-tooling-interop-ui.md).

## Setup
- Project Zomboid **42.21.0**, Steam, Windows 10. The systems live in `<install>/media/lua/{server,shared,client}/`
  (readable), `media/maps/`, `media/*.txt`, and the jar's `zombie.iso`, `zombie.randomizedWorld`,
  `zombie.iso.worldgen`, `zombie.basements` and `zombie.erosion` packages.
- On main already: how `ProceduralDistributions` lists work, `Events.OnPreDistributionMerge` as the moment to edit
  them, and that loot is rolled when a container is first generated
  ([B41 note](b41-modpack-fix-mods-and-linux-dedicated-server.md)); cells of 256x256 squares, `getZonesAt` on
  unloaded areas, and the `.pack`/`.tiles` formats for custom tiles
  ([CDDA ants note](cdda-enemy-pack-ants-custom-hostile-animals-a-breeding-colon.md)).

## Route and why
Loader API: data tables, text files and exposed Java calls. For internals that aren't exposed, decompile and
describe; never ship patched classes.

## How the game works (what we had to learn)

### Loot
- `media/lua/server/Items/Distributions.lua` (with `SuburbsDistributions.lua` and the junk files) maps room types
  and container types to item lists; `ProceduralDistributions.list` holds the named tables containers reference.
- `ItemPickerJava.getLootModifier(item)` is the rarity modifier, and the `RemoveStoryLoot` sandbox option filters
  story clutter. `ScriptManager.instance:FindItem("Base.X")` checks an item id; use it at boot to log bad ids in
  your entries, because a typo just never spawns.

### Foraging (`media/lua/shared/Foraging/`)
A complete data system; `forageDefinitions.lua` documents every field inline.
- Item definitions: `type`, `minCount`/`maxCount`, `skill` and `perks`, `xp`, visibility gates (`recipes`,
  `traits`, `itemTags`), `categories`, weather and time chances (`rainChance`, `snowChance`, `dayChance`,
  `nightChance`), `zones = { Forest = n, DeepForest = n, ... }` where **n is a roll count, not a percent**,
  months (`months`, `bonusMonths`, `malusMonths`), `spawnFuncs`, placement flags, poison fields.
- Zone definitions: zone type, icon density, `refillPercent` per day, `abundanceSetting` (the `NatureAbundance`
  sandbox key) and `containsBiomes`. Category definitions: roll `chance`, the perk that identifies the category,
  floor rules, search-focus chances.
- Zone state lives in the `"forageData"` ModData. New forageables = an item definition, optionally a category.

### Randomized world stories
`zombie.randomizedWorld` (Java) with `server/RandomizedWorldContent/StoryTable_Initialization.lua` and
`StoryClutter/`: boarded houses, corpses with loot, burnt houses, crashed cars and table settings, attached to
rooms and roads at world generation. `RandomizedWorldBase` subclasses are offered candidate rooms by room type and
zone; clutter goes through `StoryTables.addItemToClutterTable`, which validates ids and applies the sandbox
blacklist. A new story *class* needs Java; loot-only stories are Lua tables. Stories only exist where the world
is generated after the mod was added.

### Zones (the metagrid)
- `getWorld():getMetaGrid()` is the zone registry and works for unloaded areas. Registration calls used by
  `server/metazones/metazoneHandler.lua` with map-provided data:
  `getWorld():getMetaGrid():registerAnimalZone(name, type, x, y, z, w, h, properties)` (it's on `IsoMetaGrid`,
  not `IsoWorld`), `registerGeometryZone(name, type, z, geometry, points, properties)` (polygons, also on
  `IsoMetaGrid`), and `getWorld():registerMannequinZone(...)`, `registerRoomTone(...)`, `registerWaterZone`,
  `registerWaterFlow`, `registerVehiclesZone`, `registerSpawnOrigin`.
- `AnimalsPathConfig.lua` and `BiomeMapConfig.lua` show habitats as zones with property maps; a custom creature can
  get natural habitats the same way.

### Persistent world systems
- **The pattern:** a server-side `SGlobalObjectSystem` (state, save and load, MP sync; Lua in
  `server/Map/SGlobalObjectSystem.lua`, Java in `zombie.globalObjects`), a client twin `CGlobalObjectSystem`
  (`client/Map/`), a context-menu entry and a timed action for the long verb. Rain barrels
  (`client/RainBarrel/CRainBarrelSystem.lua`), farming (`client/Farming/CFarmingSystem.lua`) and generators are
  built this way; the rain barrel is the smallest complete example to copy. Register both halves by the same name.
- Other loops: fishing (`client/Fishing/`: manager, handler, states), traps (items, trap objects,
  `AddExplosiveTrapPacket` in MP), fire (`IsoFireManager`). Prefer an `entity` with stock components when one
  fits (data note).

### Tiles, objects and moveables
- Every tile in a `.tiles` file has a property set; the install's readable `.tiles.txt` sidecars (such as
  `newtiledefinitions.tiles.txt`) show which properties vanilla uses: `container = <type>` (makes the tile a loot
  container of that type), `Door`, `doorN`/`doorW`, `WallN`/`WallW`, `solid`/`solidtrans`, `collideN`/`collideW`,
  `floor`, `water`, `bed`, `sittable`, `Table`, `Material`/`MaterialType` (hit sounds and scrap), `CanScrap`,
  `BlocksPlacement`, `Facing`, `FloorHeight`, `stair`, `tree`, `bush`. Unknown keys are ignored: copy names from
  the sidecar.
- Object classes on squares (`zombie.iso.objects`): `IsoDoor`, `IsoWindow`, `IsoCurtain`, `IsoBarricade`,
  `IsoThumpable`, `IsoGenerator`, `IsoStove`, `IsoFireplace`, `IsoCompost`, `IsoMannequin`,
  `IsoWorldInventoryObject` (items on the ground), `IsoLightSource`, `IsoJukebox`, `IsoDeadBody`, `IsoFire`,
  `IsoTrap`, `IsoWaveSignal` (radios and TVs), `IsoCarBatteryCharger`. Place a plain object with
  `IsoObject.new(cell, square, spriteName)` and `square:AddTileObject(obj)` (CDDA note).
- **Moveables:** `shared/Moveables/ISMoveableDefinitions.lua` and `ISMoveableSpriteProps.lua` decide which sprites
  can be picked up, with which tool and skill, the break chance and the resulting item; `ISMoveablesAction` is the
  timed action. Custom carryable furniture = entries for your sprites plus the tile properties.
- **Without TileZed:** `media/spriteModels.txt` puts a 3D `model` on a tile sprite (`tileset { name, tile { xy,
  modelScript, translate, rotate, scale } }`); `media/seating.txt` gives furniture tiles seat anchors per direction.
  A chair needs both the `sittable` property and a seating entry. Wall cutaways use the shared mask PNGs
  (`wallcutaways.png`, `mask_transparency_*.png`).

### Map mods and map files
- `media/maps/<MapName>/` with `map.info` (`title`, `description`, `lots = Muldraugh, KY` to stitch the map onto
  the world), `spawnpoints.lua`, `thumb.png`, and the binary cells. `mod.info` names the map with `map=` and its
  tilesets with `tiledef=`/`pack=`.
- A B42 town folder (`media/maps/Muldraugh, KY`) is a grid of `<x>_<y>.lotheader` and `chunkdata_<x>_<y>.bin` pairs,
  one pair per 256x256 cell, plus `WorldGenOverride.lua` (worldgen settings for the wilderness around that town),
  `basements.lua` and `objects.lua`. Missing either half of a pair corrupts the cell.
- Map mods replace whole cells; there are no partial-cell edits, and two mods replacing the same cell can't both
  win. Build maps with the community TileZed/WorldEd forks (B42 builds of the official tools weren't out at
  research time); `IsoChunk`, `IsoChunkLevel`, `ChunkSaveWorker` and `LotHeader` read the binaries.
- **The in-game map:** `client/ISUI/Maps/` (`ISWorldMap`, `ISMiniMap`, `ISMapSymbols`, a world-map `Editor/`);
  `MapSymbolDefinitions.getInstance():addTexture(name, texturePath, category)` registers stamps (categories
  Symbols, Loot, Locations; register at `OnGameBoot`). `zombie.worldMap` stores symbols on map items.
- **Annotated-map stashes:** `shared/StashDescriptions/*StashDesc.lua` with `StashUtil.lua`. In the vanilla shape
  (values made up):
```lua
local s = StashUtil.newStash("MyModStash1", "Map", "Base.MuldraughMap", "Stash_AnnotedMap")
s.spawnOnlyOnZed = true
s.buildingX, s.buildingY = 10000, 9000           -- the target building, in world coordinates
s.spawnTable = "MyModCache"                      -- the loot table for the placed container
s:addContainer("GunBox", "mymod_tiles_01_0", nil, "livingroom")
s:addStamp("X", nil, 9998, 8999, 1, 0, 0)        -- a symbol (or nil and a text key)
```
  A stash can also spawn zombies, traps and barricades at the target. `StashDebug.lua` shows them in `-debug`.

### Worldgen and basements
- `server/WorldGen/` (`Biomes.lua`, `Features.lua`, `Roads.lua`, `Veins.lua`, `Selection.lua`, `biomes/`,
  `features/`, `prefabs/`) fills a global `worldgen` table that `zombie.iso.worldgen` consumes (`WorldGenReader`,
  `WorldGenParams`, `WorldGenChunk`, `WorldGenSimplexGenerator`, `PrefabStructure`, `StaticModule`, and
  sub-packages `biomes`, `roads`, `rules`, `veins`, `zones`, `blending`, `attachments`). Vanilla wilderness is
  generated around the authored cells; a map mod can ship its own `WorldGenOverride.lua`. The table schema is
  only documented by the Lua files themselves.
- Basements: `Basements.getAPIv1()` (Lua) has `registerBasementSpawnLocation(mapID, name, type, x, y, z, w, h,
  properties)`. Prefab pieces are `media/basement_access/*.pzby`, a binary format (header `PZBY`, a tileset-name
  string table, then tile records); the runtime is `zombie.basements`.
- Seasons and overgrowth: `zombie.erosion` (`ErosionMain`) with `client/erosion/`; erosion tiles come from
  `media/tiledefinitions_erosion.tiles`, so a modded tile only takes part if it carries the matching properties.

## Build steps
1. Loot: append to the lists from a shared or server Lua file before containers are generated (the B41 note
   edits and removes entries in `Events.OnPreDistributionMerge`), and validate every id with
   `ScriptManager.instance:FindItem`. Forageables: an item definition in a shared file.
2. A persistent device: copy the rain-barrel `SGlobalObjectSystem`/`CGlobalObjectSystem` pair.
3. An interactive tile: the property set in your `.tiles`, a `seating.txt` or `spriteModels.txt` entry where needed,
   moveable definitions to make it carryable.
4. A map: TileZed/WorldEd cells into `media/maps/<name>/`, `map.info` with `lots =`, `spawnpoints.lua`, and
   `map=` in `mod.info`.
5. A treasure map: `StashUtil.newStash` in a shared file, symbol textures through `MapSymbolDefinitions`.
6. Zones: register on the server at world init; query anywhere with `getZonesAt`.

## Verification
- Survey only. Read on 42.21.0: the Lua and data files cited (distributions, foraging, story tables,
  `metazoneHandler.lua`, the global-object systems, moveables, stash files, `spriteModels.txt`, `seating.txt`,
  the Muldraugh map folder, `server/WorldGen/`), plus javap listings of the packages named. At review time the
  Java names were checked against the unofficial 42.21.0 javadocs (albion.codeberg.page/PZ-JavaDocs).
- Not verified: anything in game, custom worldgen prefabs, the full `Basements` API, hand-written map binaries,
  exporting annotations from the map editor, a dedicated server.

## Gotchas
1. **A loot entry never spawns.** Cause: a typo in the item id; vanilla only logs it. Fix: check ids with
   `FindItem` at boot and print the failures yourself.
2. **Foraged items far too common.** Cause: a zone value read as a percent; it's a roll count. Fix: compare with
   vanilla values.
3. **A story mod doesn't appear in an old save.** Cause: stories are placed when the world is generated. Fix: test
   in a new world or unexplored areas.
4. **Story items disappear with `RemoveStoryLoot`.** Cause: clutter goes through the sandbox blacklist. Fix: check
   `ItemPickerJava.getLootModifier` for your items.
5. **`registerAnimalZone` "doesn't exist" on `getWorld()`.** Cause: it's an `IsoMetaGrid` method. Fix:
   `getWorld():getMetaGrid():registerAnimalZone(...)`.
6. **A global-object device works in single player only.** Cause: only one half (server or client system) was
   registered. Fix: register both, paired by name.
7. **A stove that isn't a container, a chair you can't sit on.** Cause: a misspelled property (ignored silently),
   or a missing `seating.txt` anchor. Fix: copy property names from the sidecar; add both halves for seats.
8. **Picked-up custom furniture breaks.** Cause: the moveable `breakChance` rolls on pickup. Fix: set it (and the
   skill gate) deliberately.
9. **A map mod stands alone instead of joining Knox Country.** Cause: no `lots = ...` in `map.info`. Fix: add it.
10. **Two map mods fight over a cell.** Cause: cells are replaced whole. Fix: list the cells you replace in the
    mod description.
11. **The X lands on the neighbour's house.** Cause: stash stamps use world coordinates. Fix: read the coordinates
    in `-debug`; give `addContainer` a room name that exists in the target building.
12. **Map stamps don't show.** Cause: `addTexture` ran after the map UI was built. Fix: register at `OnGameBoot`.
13. **A basement registration does nothing.** Cause: the map id isn't an installed map. Fix: use the exact map id.
14. **Modded tiles don't erode.** Cause: missing erosion properties. Fix: copy them from
    `tiledefinitions_erosion.tiles`.

## Assets
- Map symbols: small PNGs in `media/ui/LootableMaps/`. Tile sheets and definitions: TileZed, or the hand-written
  `.pack`/`.tiles` formats in the CDDA note.

## Cost and time
Part of one research session on 2026-10-12.

## Open questions
- The full `worldgen` schema (features, prefabs, veins, blending) and how it maps to `WorldGenParams`.
- The complete `Basements` v1 API and the `.pzby` record layout; the byte layout of `.lotheader` and
  `chunkdata_*.bin`.
- Whether Lua can register new room types for loot, or only map data can.
- What drives the meta events (helicopter, alarms) in B42, and whether they run on dedicated servers.
