---
kind: game
title: 'The Java surface of Build 42: Lua-callable methods on the key classes, and the AI, animation, audio, weather, body and damage internals behind them'
game: Project Zomboid
games_also: []
game_version: 'Build 42.21.0 (Steam, Windows 10). A survey: javap listings of projectzomboid.jar and the install''s Lua; names cross-checked against the unofficial 42.21.0 javadocs; nothing was built or run in game for this note'
platform: windows
engine: java
route: loader-api
tools: ["javap (JDK)", "PZ-Umbrella stubs", "ZomboidDecompiler (Vineflower)", "unofficial 42.21.0 javadocs (albion.codeberg.page/PZ-JavaDocs)"]
anti_cheat: 'none'
status: in-progress
agents:
- Devin (SWE-2 Medium)
humans: [Alistair-Afton]
date: '2026-10-12'
links:
- "https://www.projectzomboid.com/modding/"
- "https://albion.codeberg.page/PZ-JavaDocs/"
- "https://github.com/PZ-Umbrella/Umbrella"
tags: [b42, api, cheat-sheet, javap, isozombie, isoplayer, isoanimal, isogridsquare, isocell, isoworld, isometagrid, bodydamage, stats, scriptmanager, basevehicle, ai, statemachine, pathfinding, animation, animator, audio, fmod, weather, climate, damage, ballistics, worldsound, internals]
---
# The Java surface of Build 42: Lua-callable methods and the engine internals behind them

> A map of what Lua can call on the classes modders touch (from javap listings of 42.21.0's
> `projectzomboid.jar`), and of the engine systems behind them: the AI state machine and pathfinding, the
> animator, FMOD audio, the climate simulation, the body simulation and the damage and noise paths. It's for
> answering "does the game expose X?" before writing code. Every name here is public in the unofficial 42.21.0
> javadocs, but this is a survey: none of it was called in game for this note. Lua calls these as
> `obj:method(args)` (see the [orientation note](b42-modding-orientation-layout-lua-runtime-tooling-interop-ui.md)).

## Setup
- `javap -cp projectzomboid.jar zombie.characters.IsoZombie` lists the public surface (JDK 25 here); `-p` adds the
  private members, which Lua can't reach; `-c` prints bytecode. The CDDA note's Setup has the jdeps form and a
  reflection lister.
- Signatures with parameter names: the Umbrella stubs or the javadocs. Behaviour: ZomboidDecompiler; describe what
  you learn in your own words and never commit decompiled code.
- Where to look in the jar: `zombie.iso` (the live world, objects, weather), `zombie.characters` (characters,
  body damage, traits, skills), `zombie.ai` and `zombie.pathfind`, `zombie.scripting` (the script parser and
  block types), `zombie.entity` (entity components), `zombie.inventory`, `zombie.vehicles`, `zombie.audio`,
  `zombie.network` and `zombie.popman` (multiplayer note), `zombie.randomizedWorld` and `zombie.iso.worldgen`
  (world note), `zombie.debug`, `zombie.commands` (admin commands), `zombie.Lua` (`LuaManager`, the Kahlua
  bindings and event dispatch). Native libraries ship beside the jar: `PZBullet64` (physics), `PZPathFind64`,
  `PZPopMan64`, `jassimp64` (model import), the FMOD and networking DLLs.

## Route and why
Loader API. This note is an index of that API, plus the internals that explain what it does.

## How the game works (what we had to learn)

### Characters
- **`IsoZombie`:**
  - dress and identity: `dressInPersistentOutfit`, `dressInPersistentOutfitID`, `dressInNamedOutfit`,
    `dressInRandomOutfit`, `getOutfitName`, `isPersistentOutfitInit`, `getPersistentOutfitID`, `getHumanVisual`,
    `getOnlineID`, `isRemoteZombie`, `getOwnerPlayer`;
  - senses and targeting: `spotted`, `isTargetInCone`, `RespondToSound`, `isRespondingToPlayerSound`, `addAggro`,
    `clearAggroList`, `pathToCharacter`, `pathToLocationF`, `setWalkType`, `setSpeedTypeFromWalkType`;
  - state: `setCrawler`, `setCanCrawlUnderVehicle`, `setFakeDead`, `setForceFakeDead`, `setKnockedDown`, `knockDown`,
    `setOnFloor`, `setCanWalk`, `setSitAgainstWall`, `setReanimatedForGrappleOnly`, `GetAnimSetName`;
  - combat and voice: `Hit`, `setAttackOutcome`, `playHurtSound`, `getVoiceSoundName`, `getBiteSoundName`,
    `updateVocalProperties`; lifecycle: `removeFromWorld`, `isDead`, `setHealth`.
- **`IsoGameCharacter`** (base of players, zombies and animals): animation variables `setVariable`,
  `getVariable`, `getVariableBoolean`, `clearVariable`, `getAdvancedAnimator`, `reportEvent`; `getModData`;
  position `setX`/`setY`/`setZ` with `setLastX`/`setLastY`; `getCurrentSquare`, `getInventory`,
  `getPrimaryHandItem`/`setPrimaryHandItem`, `getWornItems`, `setInvisible`, `setGodMod`, `pathToLocation`,
  `pathToCharacter`, `setDirectionAngle`, `MoveForward`, `faceThisObject`, `getBodyDamage`, `getXp`,
  `hasTrait`, `getCharacterTraits`, `getPerkLevel`, `setPerkLevelDebug`, `setHealth` (doesn't clamp at 1 for
  animals, per the CDDA note).
- **`IsoPlayer`:** `getDescriptor`, `resetModel`, `getStats`, `getNutrition`, `getFitness`, `getMoodleLevel`,
  `hitConsequences`, `playerVoiceSound` (and `transmitPlayerVoiceSound`, `stopPlayerVoiceSound`), `setVoicePitch`,
  `playGainExperienceLevelSound`, `isAsleep`, `allPlayersAsleep`, `getZombieKills`, the lead system
  (`addAttachedAnimal`, `getAttachedAnimals`, `checkAnimalAttachedToRope`), and the bump sequence (`setBumpType`,
  `setBumpFall`, `setBumpFallType`) that the CDDA note uses for knockdowns.
- **`IsoAnimal`:** `getBehavior()` returns a `BaseAnimalBehavior` (`goAttack`, `forceFleeFromChr`; its busy flag
  `isDoingBehavior` is a field, so Lua can't read it), `pathToLocation`, `pathToCharacter`, `pathToTrough`,
  `fleeTo`, `respondToSound`, `changeStress`/`getStress`, `isAlerted`/`setIsAlerted`, `hitConsequences`,
  `setHitReaction`, genetics (`getFullGenome`, `copyGenome`), `getBreed`, milk and eggs (`canBeMilked`,
  `milkAnimal`, `createEgg`, `getEggsPerDay`), `pathFailed`/`shouldFollowWall`, and `save`/`load`/`unloaded`.
  The CDDA note documents how these behave.
- **`zombie.characters.BodyDamage.BodyDamage`** (`player:getBodyDamage()`): `AddDamage`,
  `AddGeneralHealth`/`ReduceGeneralHealth`, `DamageFromWeapon`, `applyDamageFromWeapon`, `DamageFromAnimal`,
  `AddRandomDamageFromZombie`, `damageFromSpikedArmor`, `IsBandaged`, `IsBleeding`, `IsDeepWounded`,
  `getNumPartsBleeding`, `IsFakeInfected`, `getApparentInfectionLevel`, `setInfected`, `ReducePanic`,
  `JustAteFood`, `JustTookPainMeds`, `WasBurntToDeath`. Body parts are a fixed `BodyPartType` list.
- **`Stats`** (`player:getStats()`): `get`/`set`/`add` per stat, `getNumVisibleZombies`, `getNumChasingZombies`,
  `getNumVeryCloseZombies`, `getVisibleZombies`, `setTripping`.

### World, objects and data
- **`IsoGridSquare`:** `getObjects`, `AddTileObject`/`RemoveTileObject`, `getRoom`, `getBuilding`, `isInARoom`,
  `isFree`, `has(...)` (the 42.21 name for flag checks; `Is` was removed), `hasWater`, `getZone`, `getFire`,
  `splatBlood`, `removeBlood`, `removeCorpse`, `removeGrime`, `removeGraffiti`, writeable light
  (`GetRLightLevel`/`SetRLightLevel` and G/B), and the MP verbs `transmitAddObjectToSquare`,
  `transmitRemoveItemFromSquare`, `transmitModdata`.
- **`IsoCell`** (the loaded world): `getGridSquare(x, y, z)` (nil outside the loaded area), `getZombieList`,
  `getObjectList`, `getRoomList`, `addToProcessIsoObject` (per-tick updates for an object), `addLamppost`
  (a light source), `addMovingObject`.
- **`IsoWorld`:** `getCell`, `getMetaGrid`, `getWorldAgeDays`, `getWeather`/`setWeather`/`transmitWeather`,
  `registerZone`, `registerVehiclesZone`, `registerMannequinZone`, `registerRoomTone`, `registerWaterZone`,
  `registerWaterFlow`, `registerSpawnOrigin`, `getRandomizedBuildingList`, `getRandomizedVehicleStoryByName`,
  `getRandomizedZoneStoryByName`, `getSpawnRegion`/`setSpawnRegion`. Time of day is
  `getGameTime():getTimeOfDay()`.
- **`IsoMetaGrid`** (`getWorld():getMetaGrid()`, works for unloaded areas): `getZonesAt`, `registerZone`,
  `registerAnimalZone`, `registerGeometryZone`, `registerMannequinZone`, `registerRoomTone`.
- **`VirtualZombieManager.instance`:** `createRealZombieNow`/`createRealZombie`/`createRealZombieAlways`,
  `createCorpseZombie`, `createEatingZombies`, `createHordeFromTo`, `addZombiesToMap`, `removeZombieFromWorld`,
  `addToReusable`/`isReused` (the recycling pool behind the creatures note's identity bugs),
  `spawnBuildingKeyOnZombie`, `AddBloodToMap`.
- **`ItemContainer`:** `AddItem` (several overloads), `AddItemBlind`, `contains`, `getItemFromTypeRecurse`,
  `getCapacity`/`setCapacity`, `getEffectiveCapacity`, `isExplored`/`setExplored` (the "already looted" flag),
  `getNumberOfItem`. **`InventoryItem`:** `getModData`, `getType`, `getCategory`, `getWorldItem`,
  `loadCorpseFromByteData` (a corpse stored as an item), the equip and drop sound getters,
  `registerWithSoundLimiter`, `UseAndSync`.
- **`BaseVehicle`:** keys (`createVehicleKey`, `putKeyToZombie`, `addKeyToGloveBox`), engine
  (`getEngineCondition`, `setEngineSpeed`), paint (`getSkinCount`, `setSkinIndex`, `updateSkin`,
  `LoadVehicleTexture`), parts (`getPartById("Engine")`, `getPartCount`, from `VehiclePartOwner`),
  `playPartAnim`, `playPartSound`, `toggleLockedDoor`, `setGeneralPartCondition`, `isHornSounding`.
- **`ScriptManager.instance`:** `getItem`, `FindItem`, `getAllItems`, `getRecipe`, `getVehicle`,
  `getModelScript`, `addModelScript`, `getAnimationsMesh`, `getGameSound`, `getSoundTimeline`,
  `getGameEntityTemplate`, `getMannequinScript`, `getSpriteModel`, `getScriptsForType`.
- **`IsoObject`:** `getSprite`/`setSprite`, `getContainer`, `getModData`/`hasModData`, `getDamage`/`setDamage`,
  overlay sprites (`addAttachedAnimSprite`, `addAttachedAnimSpriteByName`, `clearAttachedAnimSprite`), and MP sync
  (`sync`, `syncIsoObject`, `transmitModData`).

### Damage, noise and feedback
- **Damage entry points** (pick the nearest real path so armour, pain, blood and sync come with it):
  `DamageFromWeapon`/`applyDamageFromWeapon`, `DamageFromAnimal` (claws and bites; it plays no pain voice and
  fires no damage event, per the CDDA note), `AddDamage`, `hitConsequences` (stagger and death presentation),
  `applyDamageFromVehicleHit`. Explosions and fire: `IsoFireManager.explode(cell, square, power)` (the vanilla
  challenge uses 100000) and `IsoFireManager.StartFire`.
- **Noise that zombies and animals hear** goes through `WorldSoundManager.instance:addSound(source, x, y, z,
  radius, volume, ...)` (six overloads), `addSoundRepeating`, `getSoundZomb`, `getSoundAnimal`. Creatures react
  through `RespondToSound` (zombies) and `respondToSound` (animals). This is separate from the audio players
  hear (below): a loud custom sound needs both.
- **Ballistics:** `BallisticsController` getters expose the live aim (`getMuzzlePosition`,
  `getMuzzleDirection`, `getTargets`, `getSpreadData`, `getTargetedBodyPart`). `zombie.core.physics.Bullet` wraps
  Bullet physics (`addRagdoll`, `applyImpulse`, constraint helpers); whether Lua can use it directly is unknown.
- **Visual feedback:** `ModelInstance` attachment sockets (`getAttachmentById`, `getAttachmentWorldPosition`,
  `setItemVisual`) and `dismember`; blood through `IsoGridSquare.splatBlood` and
  `VirtualZombieManager.AddBloodToMap`; overlay sprites on objects.

### The body simulation
`Nutrition` (`getCalories`/`setCalories`, carbohydrates, lipids, proteins, `getWeight`, `canAddFitnessXp`),
`Metabolics` (activity levels with `MetToW`, `getMet`), `Thermoregulator` (`getCoreTemperature`,
`getCoreHeatDelta`, `getBodyHeatMultiplier`, `getExternalAirTemperature`, `getCatchAColdDelta`), `Fitness`
(`exerciseRepeat`, `setCurrentExercise`, `incRegularity`, stiffness). Food, clothing warmth, wetness and wind
already feed these; a mod adds its own effects by reading them or writing the setters. Weight moves through
`Nutrition`, not `Stats`. Exercise definitions are Lua data in `shared/Definitions/FitnessExercises.lua`.
`MoodleType` (in `zombie.scripting.objects`, like `CharacterTrait`) has `register` and `get` in 42.21, so the older
"moodles are a fixed enum, fake them with a UI icon" advice may be out of date; whether a mod can register a
working moodle is untested. Body parts are still a fixed `BodyPartType` enum.

### AI and saves
- `zombie.ai`: every character owns a `StateMachine` over state classes in `zombie.ai.states` (about 90 public
  ones shared by players, zombies and animals: `PathFindState`, `AttackState`, `LungeState`,
  `ZombieHitReactionState`, `FakeDeadZombieState`, the climbing and grapple states ...). Paths come from
  `zombie.ai.astar.AStarPathFinder` (and the native `PZPathFind64`). `MapKnowledge` and `KnownBlockedEdges`
  remember blocked edges; `ZombieGroupManager` handles groups.
- What Lua can do: choose targets, issue paths, set locomotion, set animation variables and report events, and
  make noise. What it can't: add states, change path costs or edit the state machine. A "new behaviour" is a Lua
  controller choreographing existing states (the Cry of Fear and CDDA brains).
- `zombie.ai.sadisticAIDirector` holds `SleepingEvent`/`SleepingEventData`; the Lua
  `server/NPCs/SadisticAIDirector/SadisticMusicDirector.lua` picks music intensity from the visible and chasing
  zombie counts.
- Saves: `zombie.savefile` has `PlayerDB`, `ClientPlayerDB` and `ServerPlayerDB` (player data lives in a database,
  not loose files). Plain Lua globals don't survive a save; use ModData.
- `zombie.characters.ecs` (`ECSEntity`, `ECSComponent` and three lifecycle hooks) is a small scaffold; the
  component runtime mods use is `zombie.entity` (data note).

### The animator
- `char:getAdvancedAnimator()` returns an `AdvancedAnimator`: `setState`, `getCurrentStateName`,
  `containsState`, `setAnimSet`, `getRootLayer`/`getSubLayerAt`/`getSubLayerCount` (layers: an upper-body layer
  over locomotion, as in aiming while walking), `addAnimCallback`, `debugGetVariables`, `updateSpeedScale`,
  `Reload`.
- Variables are typed slots (bool, int, float, string, enum and callback variants in
  `zombie.core.skinnedmodel.advancedanimation`); animNode conditions read them. Clips fire named `AnimEvent`s
  (footsteps, hit frames); `BaseGrappleable` and `GrappleOffsetBehaviour` place grappling characters;
  `DeadBodyAtlas` renders corpses.
- Prefer driving variables and letting transitions run: `setState` fights the AI states.

### Audio (FMOD)
- `GameSound` is a named bank of clips (`getRandomClip`, `getCategory`, `isLooped`, `getUserVolume`);
  `GameSoundClip` has the FMOD event, volume, pitch, distances, `hasParameter`, `hasSustainPoints` and
  `checkReloaded`. Parameters are global (`FMODGlobalParameter`) or per instance (`FMODLocalParameter`).
- `FMODAmbientWalls`, `ObjectAmbientEmitters` (loops attached to world objects) and `TreeSoundManager` are the
  ambience layers; `SoundInstanceLimiter` with `SoundLimiterParams` caps concurrent clips (items opt in with
  `registerWithSoundLimiter`); `MusicIntensityConfig` and `MusicThreatConfig` drive dynamic music. Dedicated servers
  use `DummySoundBank`/`DummySoundEmitter`.

### Weather and climate
- `getClimateManager()`: `getClimateFloat`/`getClimateBool`/`getClimateColor` (typed channels from
  `ClimateValues`), `getAirTemperatureForSquare` and `getAirTemperatureForCharacter` (temperature varies by square),
  `getAirMass`, `getCloudIntensity`, fog and night colours (`getColFog`, `getColNight`), `getClimateForecaster`,
  `getClimateHistory`, `CopyClimateValues`, `execute_Simulation`, `forceDayInfoUpdate`, `getThunderStorm`.
- `ThunderStorm`: `startThunderCloud`, `stopAllClouds`, `triggerThunderEvent`, `applyLightningForPlayer`,
  `isModifyingNight`, and `readNetThunderEvent`/`writeNetThunderEvent` (thunder is synced in MP). Weather radio
  reports read the forecaster.

## Build steps
1. Before calling a method, find it here or with javap on the build you target; confirm it's public and on the
   class you hold (or a superclass).
2. Get argument names and types from the Umbrella stubs or the javadocs.
3. For behaviour, decompile with ZomboidDecompiler outside your repo and write down what you learn in your own
   words.
4. After a game update, re-run javap on the classes your mod uses and diff the method names.

## Verification
- Survey only: names from javap listings of 42.21.0, reading the install's Lua, and the Cry of Fear and CDDA mods'
  use of some of them. At review time every class and method name here was checked against the unofficial
  42.21.0 javadocs (public members only); names that weren't public there were removed or corrected.
- Not verified: calling any of this in game for this note; argument lists (use the stubs); which of these classes
  Kahlua exposes (`Bullet`, `BallisticsController`, `ModelManager`, the popman classes); the behaviour claims
  about the animator, audio and climate beyond what the names say.

## Gotchas
1. **`attempted index` on a Java object.** Cause: reading an instance field (`obj.field`, or
   `BaseAnimalBehavior.isDoingBehavior`). Fix: find the getter.
2. **The wrong overload runs.** Cause: Kahlua picks by argument count and type (`AddItem(String)` vs
   `AddItem(InventoryItem)`). Fix: pass exactly the types the overload you want takes.
3. **A javap name fails from Lua.** Cause: `javap -p` lists private and package-private members too, and some
   names in vanilla Lua are Lua functions, not Java (`getPlayerInfoPanel`). Fix: list without `-p`, or check the
   javadocs.
4. **`attempted to call nil` on `IsoGridSquare:Is`.** Cause: 42.21 renamed it (`has`, `hasWater`). Fix: re-check
   names on every build (CDDA note gotcha 11).
5. **`BodyDamage` can't be found as an inner class.** Cause: `zombie.characters.BodyDamage.BodyDamage` is the class
   `BodyDamage` in the package `zombie.characters.BodyDamage`. Fix: use that full name with javap; from Lua,
   `player:getBodyDamage()`.
6. **Your change never reaches MP clients.** Cause: a plain setter on the server. Fix: the `transmit*`/`sync*`
   verbs (multiplayer note).
7. **`getGridSquare` returns nil.** Cause: the square isn't loaded. Fix: work with `IsoMetaGrid` zones and build when
   the square loads.
8. **A container won't refill.** Cause: it's marked explored. `setExplored(false)` makes it lootable again; state
   flags like this exist on many classes, so search the listing before deciding something is impossible.
9. **A custom creature makes no sound for zombies.** Cause: it only played audio. Fix: also
   `WorldSoundManager.instance:addSound(...)`.
10. **Forced animator states flicker.** Cause: `setState` against the state machine. Fix: drive variables.
11. **A loop keeps playing after its object unloads.** Cause: emitters need an explicit stop. Fix: stop loops on
    unload and on identity changes.
12. **A climate write snaps back.** Cause: the air-mass simulation keeps running. Fix: write the values, then step
    the simulation, and on a server send `transmitWeather`.
13. **Server code waits on a sound.** Cause: dedicated servers use dummy sound banks. Fix: never gate gameplay on
    audio.

## Assets
None.

## Cost and time
Part of one research session on 2026-10-12.

## Open questions
- Which of these classes Kahlua actually exposes (the `zombie.core.physics` classes, `ModelManager`, the popman
  classes): test a call, or read the exposer.
- `AStarPathFinder` costs, per-state entry and exit conditions, and whether `MapKnowledge` survives zombie recycling.
- How `AnimationVariableSlotCallback*` slots bind to Lua callbacks; whether `MoodleType.register` gives a mod a
  real moodle.
- The full `ClimateValues` channel list (the debug weather window shows it) and whether the forecaster is seeded per
  save.
