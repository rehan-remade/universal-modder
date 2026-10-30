---
kind: game
title: 'Creatures in Build 42: monsters as dressed zombies, porting creatures from other games, other chassis, and how the NPC frameworks work'
game: Project Zomboid
games_also: ["Cry of Fear", "Half-Life", "Cataclysm: Dark Days Ahead"]
game_version: 'Build 42.21.0 (Steam, Windows 10). A survey: the files of the Workshop mods named below (Cry of Fear Monsters 0.68.25 with versionMin=42.20, Bandits, CompanionDogs, ProjectALifeNPCs), a local-only Half-Life port, javap listings and the install''s Lua; nothing was built or run in game for this note'
platform: windows
engine: java
route: loader-api
tools: ["Project Zomboid Lua (Kahlua) mod API", javap, "Blender + DirectX X importer", "Paddlefruit rig / PY-BobBatchExportGLB.py", "Crowbar (Half-Life .mdl)"]
anti_cheat: 'none (single-player creature mods; the multiplayer note covers servers you host)'
status: in-progress
agents:
- Devin (SWE-2 Medium)
humans: [Alistair-Afton]
date: '2026-10-12'
links:
- "https://steamcommunity.com/sharedfiles/filedetails/?id=3268487204"
- "https://steamcommunity.com/sharedfiles/filedetails/?id=3740052292"
- "https://steamcommunity.com/sharedfiles/filedetails/?id=3803984183"
- "https://pzwiki.net/wiki/Animation_guide"
tags: [b42, creatures, custom-monster, zombies, clothing, bodylocation, persistent-outfit, animsets, animnode, animation-variables, spawning, outfits, cross-game-port, npc, survivors, companion, bandits, mannequin, thumpable, case-study]
---
# Creatures in Build 42: dressed zombies, ports from other games, other chassis and NPC frameworks

> How custom creatures are built on Project Zomboid Build 42, read from mods that ship them: Svide's *Cry of Fear
> Monsters* (23 humanoid monsters, each a **zombie wearing an invisible whole-body clothing item** whose model is
> the monster), a local Half-Life Houndeye port on the turkey's animal rig, and three NPC frameworks (Bandits,
> CompanionDogs, ProjectALife). The animal route is in main's
> [CDDA ants note](cdda-enemy-pack-ants-custom-hostile-animals-a-breeding-colon.md) and isn't repeated here. This
> is a survey of other people's mod files plus javap listings; nothing was built and run in game.

## Setup
- Project Zomboid **42.21.0**, Steam, Windows 10. General mod layout and the Lua runtime: the
  [orientation note](b42-modding-orientation-layout-lua-runtime-tooling-interop-ui.md); Java names: the
  [Java-surface note](b42-java-surface-lua-callable-api-and-engine-internals.md).
- Mods read (structure only, described in our own words):
  - *Cry of Fear Monsters* by Svide (Steam Workshop), v0.68.25, `versionMin=42.20`: about 13k lines of Lua in
    `42/media/lua/{shared,client,server}`, data in `common/media/{models_X,anims_X,clothing,scripts,sound,
    textures,fileGuidTable.xml,registries.lua}` and `42/media/{AnimSets,sandbox-options.txt}`. Its files carry
    the authors' own bug history in comments.
  - *HLMonsters*: a Half-Life Houndeye port that only exists in the contributor's local `Zomboid/mods` folder; it
    was never published.
  - Bandits (Workshop 3268487204), CompanionDogs (3740052292) and ProjectALifeNPCs (3803984183).

## Route and why
Loader API: everything below is the game's own Lua plus its asset pipeline. The first decision is the chassis:

| | Dressed zombie (Cry of Fear) | B42 animal ([CDDA note](cdda-enemy-pack-ants-custom-hostile-animals-a-breeding-colon.md)) |
|---|---|---|
| Base object | `IsoZombie` wearing a custom whole-body clothing item | `IsoAnimal` (a subclass of `IsoPlayer`) |
| Free | hunting and attacking players, hit reactions, deaths, crawling, fake-dead, vehicle hits, netcode | pathing, eating, fleeing, growth, butchering, saving |
| You build | the look (body item, model, AnimSet nodes), identity, spawning | the whole attack brain in Lua |
| Skin to | the `Bip01` human rig (Bob/Kate) | the closest animal rig (pig, turkey, raccoon ...) |
| Best for | humanoids that hunt players | creatures with their own behaviour, packs, colonies |

Rule of thumb from the ports: if the creature should hunt the player like a zombie, use a zombie and get the AI
free; if it needs its own behaviours, use an animal and write the brain.

## How the game works (what we had to learn)

### The dressed-zombie chassis (Cry of Fear Monsters)
- **One new body location.** `common/media/registries.lua` is one call,
  `ItemBodyLocation.register("COF:MonsterBody")`. At `OnGameBoot` a shared Lua file takes the "Human"
  `BodyLocationGroup`, calls `getOrCreateLocation` for the new location and `moveLocationToIndex` to put it at the
  `UNDERWEAR_BOTTOM` index, the lowest body layer. The monster's model then replaces the zombie's visible body and
  ordinary clothing still renders over it.
- **The body is an invisible clothing item:** a script item with `ItemType = base:Clothing`,
  `ClothingItem = COF_<Monster>Body`, `BodyLocation = COF:MonsterBody`, `WorldRender = false`, `hidden = true`,
  `Tags = base:noragdoll`.
- **The clothingItem XML** points `m_MaleModel`/`m_FemaleModel` at the mesh in `models_X`, has one fixed GUID,
  sets all 16 `m_Masks` (hiding the base body), `m_Static` false and one `textureChoices` atlas. A matching
  corpse XML per monster keeps the look on dead bodies. Every clothing XML's GUID goes into `fileGuidTable.xml`.
- **Identity is the outfit, not mod data.** Each monster is a persistent outfit containing only its body item.
  `dressInPersistentOutfit(name)` applies it, `getOutfitName()` reads it, `isPersistentOutfitInit()` says whether
  the game has dressed the zombie yet.

### Why identity is the hard part (from the mod's own bug notes)
- **The engine recycles zombie objects.** A recycled zombie keeps its old `getOutfitName()` until it's re-dressed,
  which happens when it comes into view. Controllers that claim zombies by outfit name then grab the wrong one,
  and two controllers strip each other's body item (a naked zombie playing the wrong sounds).
- **Mod-data marks get lost** when a monster leaves and re-enters the loaded area, so unmarked types spawn again
  (their log: 13 of one monster and endless flowers in an hour).
- **Their fix:** in `OnZombieCreate`, when `isPersistentOutfitInit()` is false, clear the stale outfit with
  `getHumanVisual():setOutfit(nil)` and immediately `dressInPersistentOutfitID(getPersistentOutfitID())`, so the
  controller owns the zombie before it's ever seen. The high half of `getPersistentOutfitID()` is the outfit
  index, and a table learned from dressed monsters maps index to monster.
- **One dispatch point:** every controller registers with the mod's dispatcher on `OnZombieUpdate`; a weak-keyed
  "previous identity" table spots a recycled zombie and gives the old controller one cleanup pass (stop loops,
  drop tables).

### Animation plumbing
- **The stack:** an AnimSet (per entity, `media/AnimSets/<entity>/<state>/*.xml`), an ActionGroup state machine
  over its states (`media/actiongroups/`), and `animNode` XML: `m_AnimName`, `m_Looped`, `m_BlendTime` and
  `m_Conditions` on animation variables that Lua sets with `character:setVariable("Name", value)`.
- **Merge, don't replace.** Mod XML under `media/AnimSets/zombie/<state>/` merges into the zombie's graph. Cry of Fear
  adds nodes to the vanilla states (`attack`, `walktoward`, `idle`, `hitreaction`, `lunge`, `getup`, `eatbody`,
  `fakedead`, `bumped`, the vehicle-collision and corpse-drag states ...) gated on `COF_Is<Monster> == true`, and
  picks attack clips through a STRING variable the conditions read. The vanilla `ZombieBiteDone` variable gates
  bite damage, and controllers set it themselves. Their `COF_AnimTemplates/` folders are reference copies that
  the game doesn't load (only `media/AnimSets/` is read).
- **Clip folders:** only `anims_X` subfolders named by the model's `animationsMesh` script entry are scanned, with
  the prefix that entry sets; human rigs scan `Bob/` and `Kate/` with `Bob_`/`Kate_` prefixes, which come from
  each ActionGroup root's `animNodeFilter` (`media/actiongroups/zombie.xml`, `player.xml` ...). The install's
  `Master_Variables.xml` lists the variables conditions can read.
- **Formats:** `.glb` (recommended, hot-reloadable; the Paddlefruit community rig and its
  `PY-BobBatchExportGLB.py` exporter, 30 fps), `.fbx`, or vanilla text `.x`. Import vanilla `.x` into Blender with
  the "DirectX X Importer" extension or ZomboidAssetConverter. Models load through the game's assimp
  (`jassimp64`), so no conversion to `.x` is needed. AnimZed, TIS's own tool, was announced but not released at
  research time.
- `media/animscript/combat.xml` is a second, older AnimStates language (`<PlayAnim>`/`<Out>` states); don't mix
  it up with AnimSet `animNode` files.

### Spawning
- **Outfits** are `media/clothing/clothing.xml` entries per sex: a name, a GUID and items by clothingItem GUID with
  optional probabilities and alternates. Every item GUID must be in your `fileGuidTable.xml` or the outfit
  silently fails.
- **Zone spawn tables:** `media/lua/shared/NPCs/ZombiesZoneDefinition.lua` maps a map zone name to
  `chanceToSpawn`/`toSpawn` and outfit entries (`name`, `toSpawn`, `gender`, `mandatory`, `room`, `chance`). A mod
  adds keys from a shared Lua file: that's how "special zombies in special places" works (vanilla: a wedding party
  in a church).
- **By hand:** `addZombiesInOutfit(x, y, z, count, outfit, femaleChance, ...)` needs the zombie population on.
  With population None, Cry of Fear calls `VirtualZombieManager.instance:createRealZombieNow(x, y, z)` and sets
  everything itself (`setFemaleEtc`, `dressInPersistentOutfit`, `setCrawler`, `setFakeDead`, `setHealth` ...).
  It works only on the server (an MP client gets an empty result), and an old version read a Java field there and
  spawned nothing.
- On top sits the mod's own spawn system: weighted rarity per monster independent of the zombie population,
  per-monster sandbox toggles and rarity enums, a night event, spawn diagnostics in the log, and debug
  right-click spawns.
- Multiplayer: creation is server-only, controllers early-return on `isServer()` and the factory on `isClient()`;
  the server tells clients "this zombie is monster X" and each client sets the variables and visuals locally. See
  the [multiplayer note](b42-multiplayer-internals-packets-gameserver-sync.md).

### Porting a creature from another game: three asset routes
- **A. The other game's own assets** (Cry of Fear Monsters ships Cry of Fear's models, animations and sounds;
  its Workshop page credits them to Team Psykskallar and states no licence or permission). If the source game
  exports skinned meshes and clips as `.fbx`/`.glb`/`.x`, they load directly.
- **B. Converted assets** (HLMonsters): Half-Life `.mdl` -> Crowbar (or similar) to `.smd`/`.fbx` -> re-skin to a PZ
  rig -> text `.x` (`media/models_X/Skinned/Houndeye.x`, clips in `media/anims_X/houndeye/he_*.x`, an
  `animationsMesh` with `animationDirectory = houndeye`, `animationPrefix = he_`). Its AnimSet is a copy of the
  turkey's state folders with `he_` entries.
- **C. Generated assets** (the CDDA ants): no source assets at all; the pipeline is in the CDDA note's Assets.
- **Rights:** A and B are another game's copyrighted content, taken from your own install. Keep such a port
  private; a public release needs the rights holder's permission, or your own assets (route C). Converting a
  format doesn't change who owns it. HLMonsters stays local for this reason.
- **Skeleton:** reuse a PZ rig (`Bip01` or an animal's) so the vanilla AnimSet works; a custom skeleton means
  authoring every state. Rename source clips into PZ's state folders on export, and make sure the clip name
  inside each file matches `m_AnimName`.

### Other chassis (catalogue; none of these was tried)
| Body | Engine object | Notes |
|---|---|---|
| Friendly or neutral humanoid | `IsoZombie` that never gets a target | `clearAggroList`, no `spotted(player)`, steer with `pathToLocationF`/`pathToCharacter`; other zombies, melee auto-aim and player panic still treat it as a zombie |
| Pet or pack animal | `IsoAnimal` on a lead | `IsoPlayer:addAttachedAnimal`, `checkAnimalAttachedToRope`; troughs, milk, eggs |
| Static figure | `IsoMannequin` | `mannequin` script blocks, `registerMannequinZone` (on `IsoWorld` and `IsoMetaGrid`); poses, no skeletal animation |
| Turret, mimic, plant | `IsoThumpable` | `Thump`, `WeaponHit`, `animalHit`, `changeSprite`; no locomotion; tick it with `IsoCell:addToProcessIsoObject` |
| Visual only | `IsoObject` + sprites | `addAttachedAnimSprite` overlays; `WorldSoundManager.instance:addSound` for noise |
| Boss or swarm | several of the above | one controller, shared ModData pool; reassemble after chunk unload |

Whether Lua can drive the `Bullet` physics wrapper or `ModelManager.addStatic` directly is unknown; plan around the
engine's own hit and vehicle paths. `playerVoiceSound` is player-only: NPC barks are positioned `sound` entries,
and overhead speech text is `IsoGameCharacter:addLineChatElement(text, r, g, b ...)` (BeyondOneWeek uses it with
`getSpeakColour()` for debug lines).

### NPC frameworks in the wild
- **Bandits** (survivor NPCs on zombies):
  - identity is a boolean animation variable, read with `zombie:getVariableBoolean("Bandit")`, plus a brain table
    per bandit (`BanditBrain.Get(zombie)`) keyed by a stable id, and position-only "light" caches for the per-tick
    path;
  - verbs are 49 action modules in `shared/ZombieActions/` with `onStart`/`onWorking`/`onComplete(zombie, task)`
    (walking, climbing, aiming, shooting, reloading, looting, bandaging, fishing, generator work, burying ...);
  - programs in `shared/ZombiePrograms/` (`ZPBandit`, `ZPCompanion`, `ZPLooter`, `ZPThief` ...) are state machines
    that return `{status = ..., next = "State", tasks = {...}}`;
  - locomotion uses the player-style animation channel on the zombie: a `BanditWalkType` variable,
    `setBumpType("IdleToRun"|"IdleToWalk")`, `pathToLocationF` and `faceLocationF`, with the mod's own AnimSets
    and actiongroups;
  - in MP only the owning client steers (`BanditUtils.IsController(zombie)` gates the path calls), and
    `OnZombieUpdate` returns early on the server, so the brains run on clients and sync through commands.
- **CompanionDogs** builds a dog on the **raccoon**: `cd`-prefixed animNodes merged into
  `media/AnimSets/raccoon/`, a radial command menu (`ISRadialMenu`), status, stray-scan and bag windows.
- **ProjectALife** splits an NPC suite into subsystem folders, a shared `alife_runtime` catalog that several
  scenario mods build on, and a `Compat/` folder with one adapter per other mod.

## Build steps
1. Chassis (table above); write down which free systems you rely on.
2. Dressed zombie: register a body location in `common/media/registries.lua` and move it to the
   `UNDERWEAR_BOTTOM` index at `OnGameBoot`; skinned mesh in `models_X/<Monster>/`; clothingItem XML with all 16
   masks, a fixed GUID and a texture atlas, plus a corpse variant; GUIDs in `fileGuidTable.xml`; an invisible
   clothing item on your location; an outfit with only that item.
3. AnimSet nodes under `media/AnimSets/zombie/<state>/` keyed on `MyMod_Is<Monster>`; clips in
   `anims_X/<Monster>/` matching the `animationsMesh` entry.
4. A controller per monster behind one `OnZombieUpdate` dispatcher keyed on the persistent outfit; set the
   variables at claim time, drive attacks with `ZombieBiteDone` and a clip-select variable, clean up on identity
   change.
5. Spawn on the server only: `createRealZombieNow` + `dressInPersistentOutfit`, or `addZombiesInOutfit` when the
   population is on; sandbox toggles and rarities; debug right-click spawns for testing.
6. On `OnZombieCreate`, clear the stale outfit and re-dress before the zombie is seen.

## Verification
- Survey only: the mods' files were read end to end (structure, names, comments); none of them was run for this
  note, and no creature was built. The Java names were checked against the unofficial 42.21.0 javadocs
  (albion.codeberg.page/PZ-JavaDocs) at review time, and the Bandits identity check against a public copy of its
  42.20 Lua.
- For your own creature: `console.txt` after every session, the `-debug` animator window to watch which
  animNode plays, and debug spawn entries.
- Not verified: Cry of Fear's MP layer on a dedicated server; whether the persistent-outfit timing changed after
  42.21; any of the "other chassis"; Bandits in MP.

## Gotchas
1. **A monster's controller grabs the wrong zombie.** Cause: recycled zombies keep a stale outfit name.
   Fix: on `OnZombieCreate`, `getHumanVisual():setOutfit(nil)` when not `isPersistentOutfitInit()`, then
   re-dress from `getPersistentOutfitID()`.
2. **Duplicate spawns over time.** Cause: mod-data marks don't reliably survive chunk unload and reload. Fix:
   identify and count monsters by persistent outfit, not marks.
3. **A naked zombie playing the wrong sounds.** Cause: two controllers on one zombie. Fix: one dispatch point,
   previous-identity tracking, a cleanup pass on change.
4. **Looping monster sounds outlive the monster.** Fix: stop them in the identity-change cleanup, not only on
   death.
5. **`addZombiesInOutfit` does nothing.** Cause: zombie population set to None. Fix: server-side
   `createRealZombieNow` and set the properties by hand.
6. **Custom attack clips never play.** Cause: vanilla bites need the target within reach (about 0.72 tiles, CDDA
   note), a check Lua can't call. Fix: your own attack variables, a clip-select string variable, and set
   `ZombieBiteDone` yourself.
7. **The clothing body vanishes across saves or in MP.** Cause: a clothing XML without its `fileGuidTable.xml`
   entry. Fix: a unique, stable GUID per clothing XML.
8. **The monster turns back into a zombie after a reload.** Cause: the body item was lost while the zombie
   persisted. Fix: a corpse body variant, and the controller re-adds the body item while the identity holds.
9. **Vanilla hands or head poke through the monster.** Fix: all 16 `m_Masks`, `m_Static` false, no attach bone.
10. **The new AnimSet replaces movement instead of adding to it.** Cause: replacing the base set (the same
    failure as the animal-animset copy in CDDA gotcha 1). Fix: add nodes into the vanilla state folders, gated
    on variables.
11. **An animation file never loads, with no error.** Cause: the `anims_X` folder or file prefix doesn't match the
    `animationsMesh` entry (or the `Bob_`/`Kate_` prefixes for humans), or the clip name inside the file differs
    from `m_AnimName`. Fix: match all three.
12. **A recycled Bandits-style NPC keeps its flag.** Cause: animation variables stay on the zombie object. Fix:
    clear them in the same recycle cleanup as outfits.
13. **A friendly zombie still behaves like a zombie.** Cause: other zombies, melee auto-aim and player panic key
    on the zombie type. Fix: budget overrides, or use a mannequin or an animal.
14. **Publishing another game's assets gets the mod pulled.** Fix: keep such ports private, get permission, or
    generate your own assets.

## Assets
- Meshes in `models_X/<Monster>/`, texture atlases in `textures/` (`textureChoices`), clips in
  `anims_X/<Monster>/`, sounds in `sound/<mod>/` bound by `sound` blocks (category `Zombie`, 3D falloff, several
  `clip {}` variants per sound).
- Credit: Svide's *Cry of Fear Monsters* for the dressed-zombie technique (Cry of Fear's assets belong to Team
  Psykskallar); the Bandits, CompanionDogs and ProjectALife authors for the NPC architectures.

## Cost and time
Part of one research session on 2026-10-12.

## Open questions
- How much of Cry of Fear's net layer a listen-server co-op needs versus a dedicated server.
- A hybrid: an animal body with a zombie-hunter brain (the CDDA note shows hostile animals; zombie-vs-animal
  targeting crashes, see its gotcha 5).
- Whether a non-network `IsoPlayer` can be spawned as a puppet; the smallest workable AnimSet for a custom
  skeleton; `zombie.popman` hooks for horde-scale monster populations.
