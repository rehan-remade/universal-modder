---
kind: game
title: 'CDDA Enemy Pack: Ants - custom hostile animals, a breeding colony and a custom nest tile in Build 42'
game: Project Zomboid
games_also: ["Cataclysm: Dark Days Ahead"]
game_version: 'Build 42 (Steam, Windows 10): built against 42.15-42.20, final in-game tests on 42.21.0 (console.txt "version=42.21.0 4a0e9546ec"), single player. Starving Zombies mod (Workshop 3396867685, 42.15 folder) installed alongside'
platform: windows
engine: java
route: loader-api
tools: ["Project Zomboid Lua (Kahlua) mod API", "javap + a small Java reflection lister", "lupa (Python Lua runtime) offline harness", pymeshlab, trimesh, numpy/scipy, Pillow, ffmpeg, "fal (nano-banana-2, Meshy v7.1 image-to-3D, BiRefNet, ElevenLabs SFX)"]
anti_cheat: 'none (single-player mod; no client patching, everything through the Lua mod API)'
status: working
agents:
- Claude Code (Opus 5.5)
humans: [Comrade Worldpeace]
date: '2026-10-09'
links: ["https://github.com/CleverRaven/Cataclysm-DDA"]
tags: [b42, animals, custom-monster, ai, colony, breeding, custom-tiles, texture-pack, tiledef, skinned-mesh, pig-skeleton, sandbox-options, corpses, cross-game-port]
---
# CDDA Enemy Pack: Ants - custom hostile animals, a breeding colony and a custom nest tile in Build 42

> A port of the ants from Cataclysm: Dark Days Ahead (giant ant, soldier, super soldier, larva, queen) into Project
> Zomboid Build 42 as hostile *animals*: own 3D models skinned to the pig skeleton, a zombie-style AI layer in Lua
> (awareness, alarm pheromone, searching, flanking, retreat, corpse eating), and a colony system with an egg-laying
> queen, larvae that grow into weighted variants, and a 2x2 nest built from a custom texture pack + tile definition
> that spawns on a town edge and can be buried with a shovel. Pure Lua mod API, no Java patching. Played and
> log-checked by the human over ~12 in-game test sessions; 0 mod errors in the last two sessions.

## Setup
- Project Zomboid Build 42 from Steam, Windows 10 (i5-10600K, 64 GB). Final tests on **42.21.0**; a mid-project
  API rename (see Gotcha 11) shows the Lua surface moves between 42.x builds.
- Mod layout (B42): `mods/<id>/42/{mod.info, poster.png, media/...}` plus an empty `common/`. Lua in
  `media/lua/{shared,server,client}`, animal definitions in `media/lua/shared/Definitions/animal/`, meshes in
  `media/models_X/Skinned/*.x` (text DirectX), textures in `media/textures/Body/`, model scripts and sounds in
  `media/scripts/`, sandbox options in `media/sandbox-options.txt` + `media/lua/shared/Translate/EN/Sandbox.json`.
- Reverse-engineering: `java -m jdk.jdeps/com.sun.tools.javap.Main -cp projectzomboid.jar -p -c <class>` for
  bytecode, plus a 15-line Java reflection lister (`Class.forName(..., false, loader).getMethods()` filtered by
  regex) to see what Lua can call. No decompiler needed.
- Offline: Python 3.13 with lupa (Lua 5.5), trimesh, pymeshlab, scipy, Pillow; ffmpeg; `um fal`.

## Route and why
Loader API (the game's own Lua mod API + data files). Build 42's animal system (`IsoAnimal extends IsoPlayer`,
definitions in Lua tables, animsets, behaviours) already gives pathing, attack animations, hit reactions, death,
butchering and saving, so a monster can be an "animal" with a Lua brain on top. Rejected: a zombie reskin (zombie
AI can't be told to fight zombies, and zombie outfits can't make an ant body) and Java patching (not distributable
on the Workshop without a loader, and unnecessary).

## How the game works (what we had to learn)
**Animals**
- Definition tables: `AnimalDefinitions.animals[type]` (model, animset, sizes, `attackBack`, `knockdownAttack`,
  `canDoLaceration`, hunger multipliers...), `AnimalDefinitions.breeds[type]` (texture, sounds, forced genes),
  `stages`, `genome`, plus `AnimalAvatarDefinition` and `AnimalPartsDefinitions.animals[type..breed]` (butchering;
  `noSkeleton = true` stops a skeleton corpse). Spawn with `addAnimal(cell, x, y, z, type, breed)` + `addToWorld()`.
- A new body can reuse a vanilla animation set if the mesh is skinned to that skeleton: model script
  `animationsMesh = Pig_BoarAndSow` and definition `animset = "pig"`.
- Animals only bite `IsoAnimal.fightingOpponent` (not settable from Lua). A zero-damage
  `ant:hitConsequences(nil, player, true, 0, false)` followed by `setHitReaction("")` makes the vanilla
  fight-back logic adopt that player, which then produces real animal bites, lacerations and damage.
- Movement: `BaseAnimalBehavior.goAttack(target)` marks the animal busy (`isDoingBehavior`) so the vanilla
  eat/drink/wander check doesn't override the walk; `IsoAnimal.pathToLocation(x, y, z)` (what vanilla wandering
  uses) walks to a tile centre and isn't overridden while the animal is moving. A failed path runs
  `pathFailed()` and sets `shouldFollowWall` (the zig-zag) - a free "unreachable" signal.
- The walk anim's speed comes from the animation variable `animalSpeed` (vanilla only sets it when an animal is
  led on a rope); setting it every think changes walking speed.
- Fleeing: animals flee when spotted/stressed (`BaseAnimalBehavior.fleeFromChr`, stress, `isAlerted`).
  `changeStress(-getStress())` + `setIsAlerted(false)` keeps an animal calm; a startle still nudges position
  even with `setBlockMovement(true)`.
- Size: `AnimalData.setSize` clamps to the definition's min/max and is called on load and while ageing;
  `setSizeForced` doesn't clamp but isn't persistent. Health: `IsoGameCharacter.setHealth` doesn't clamp at 1 for
  animals and the saved float is restored on load, so tougher monsters can just have health > 1.
- Animal bites on players go through `BodyDamage.DamageFromAnimal`: no pain voice, no `OnPlayerGetDamage`.

**Zombies vs animals**
- Never `zombie:setTarget(animal)`: vanilla zombie states read the target's moodles (animals have none) -> NPE,
  game crash. `setTarget(nil)` and `pathToCharacter(animal)` are safe; damage in Lua.
- A zombie only swings when `getShouldAttack()` passes, which needs the target within 0.72 tiles (and more), so
  zombie attack animations on animals aren't reachable from Lua; claws were applied on a timer instead.

**World, map and objects**
- Cells are 256x256 tiles in B42 (`IsoCell.CELL_SIZE_IN_SQUARES`). Only squares near players exist in memory;
  `getCell():getGridSquare()` returns nil elsewhere, so world objects/animals can only be placed when their ground
  loads.
- The zone map is global: `getWorld():getMetaGrid():getZonesAt(x, y, 0)` (zone `getType()`: `TownZone`,
  `TrailerPark`, `Forest`, `DeepForest`, `Vegitation`, `FarmLand`, `Nav`...) works for unloaded areas; with
  `getMinX/MaxX/MinY/MaxY()` (cells) it's enough to pick "edge of a town" sites anywhere.
- `OnWorldSound(x, y, z, radius, volume, source)` fires for every world sound (gunshots, shouts, alarms).
- `IsoDeadBody`'s constructor fires `OnDeadBodySpawn` *before* it sets `deathTime`.
- Player knockdown from Lua (the game's own drunk-trip sequence): `setVariable("BumpDone", false)`,
  `clearVariable("BumpFallType")`, `setBumpType("stagger")`, `setBumpFall(true)`,
  `setBumpFallType("pushedFront"|"pushedBehind")`, `player:reportEvent("wasBumped")`.
- `player:playerVoiceSound("PainFromBite")` plays `VoiceMale/FemalePainFromBite`.

**Custom tiles (no TileZed needed)** - formats read from vanilla files and written by our own script:
- `.pack`: `"PZPK"`, int version 1, int page count; per page: string name, int entry count, int has-mask (1);
  per entry: string sprite name, ints x, y, w, h (rect in the page PNG), ox, oy (offset inside the frame),
  frame w 128, frame h 256; then int PNG length + PNG bytes. Strings are int-length-prefixed, little endian.
- `.tiles`: `"tdef"`, int version 1, int tileset count; per tileset: `name\n`, `image.png\n`, ints columns, rows,
  id, tile count; per tile: int property count, then `key\nvalue\n` pairs (e.g. `CustomName`, `GroupName`).
- `mod.info`: `pack=<PackName>` loads `media/texturepacks/<PackName>.pack` as given (B42 frames are 128x256);
  `tiledef=<file> <number>` with a file number 100-8189; sprite names are `<tileset>_<index>`. A ground object's
  floor diamond is the bottom 64 px of the frame (vanilla ramps end at y = 256). Place with
  `IsoObject.new(getCell(), sq, spriteName)` + `sq:AddTileObject(obj)`; remove with `sq:RemoveTileObject(obj)`
  (SP) or `sq:transmitRemoveItemFromSquare(obj)` (server).
- A multi-square isometric object (2x2 nest): one sprite per square. Split the big image so every pixel belongs to
  exactly one part (left quarter -> west square, right quarter -> east, middle half -> north above the footprint's
  centre line, south below), crop each to its square's 128x256 frame; drawn back-to-front it reassembles seamlessly.

**Other mod.info / sandbox facts**
- B42 `mod.info` supports `incompatible=\ModA,\ModB`, `require=`, `loadModAfter/Before`, `poster=`, `modversion`.
- Sandbox options: `option <Ns>.<Name> { type, min, max, default, page, translation }`; enums use `numValues` +
  `valueTranslation` with labels `Sandbox_<valueTranslation>_option1..n`; a page's label is `Sandbox_<page>`;
  options appear on tabs per `page`. Saved values are keyed by option name, so moving options between pages is safe.
- Shovel check: `item:hasTag(ItemTag.DIG_GRAVE)`; dig animation `BuildingHelper.getShovelAnim(item)`; B42 timed
  actions live in `shared/TimedActions` and `complete()` runs where the world is authoritative.

## Build steps
1. Animal definition: copy the pig's definition shape, point `bodyModel`/`modelscript` at your model script entry,
   `animset = "pig"`, empty `breed.sounds` (play sounds from Lua so a volume slider covers them),
   `knockdownAttack = false`, `fleeZombies = false`, `attackBack = true`.
2. Model: concept image -> image-to-3D -> decimate with texture to ~2.6-3.2k faces -> orient into the pig mesh space
   (Y up, head toward -Z) -> weight to pig bones by anatomy -> write a text `.x` that reuses the pig's frame
   hierarchy and per-bone offset matrices -> model script with `animationsMesh = Pig_BoarAndSow`.
3. AI in `media/lua/server/`: one OnTick loop over a per-window snapshot of ant/zombie positions (8-tile grid),
   ants staggered over a 15-tick think window; provoke + `goAttack` for players, Lua bites/claws for zombies.
4. Colony: global mod data (`ModData.getOrCreate`) for nests and pending sites; build the nest when its square loads;
   queen/larva behaviour via a per-type `onThink`.
5. Tiles: generate art -> background removal -> split/fit -> write `.pack` + `.tiles` -> `pack=`/`tiledef=` lines.
6. Upload folder: `Zomboid/Workshop/<id>/{Contents/mods/<id>/..., preview.png (256x256), workshop.txt}`.

## Verification
- **In game (the real oracle):** the human ran ~12 sessions (battle tests, a full in-game day with a 171-ant colony,
  shooting the colony, being bitten, burying the nest) and the agent read `console.txt` after each. A sandbox
  "debug logging" switch (now a developer constant) wrote `CDDAMonsters[topic]` lines for every decision (targets,
  give-ups, lays, growth, enrage, bites, knockdowns) and a 10-second status line counting ants per activity - that is
  how the feeding bugs and the queen not laying were found. 171 ants on screen showed no performance dip.
- **Offline harness:** the real server Lua run in lupa against stand-in animals/zombies/players/squares for
  thousands of ticks, with scenarios (classic/advanced AI, Starving Zombies present, feeding, unreachable zombies,
  reload, 70 ants vs 410 zombies, a full colony with accelerated hours, queen kill/regrow/enrage/bury). The stand-in
  zombie raises an error on `setTarget(animal)`.
- **API name check:** every `obj:method(` in the mod checked against a reflection dump of ~30 game classes - catches
  renamed/missing Java methods the harness stubs would hide.
- **Mesh oracle:** pig animations played on the skinned `.x` offline, reporting edge-stretch percentiles per anim.
- **Not verified:** multiplayer; the v1.0.1 nest placement ring (500-1500 tiles) in a real world; the newest soldier
  and super soldier meshes in the renderer; behaviour on builds after 42.21.

## Gotchas
1. **Ants stood still or ignored hits after switching to a custom animset copy.** **Cause:** our copy of the pig
   animset/actiongroups broke movement, hit reactions and death. **Fix:** use the vanilla `pig` animset via
   `animationsMesh`; drive extra behaviour from Lua.
2. **Animal stands still when told `pathToCharacter`.** **Cause:** the vanilla behaviour check overrides raw paths
   unless the animal is "doing a behaviour". **Fix:** `getBehavior():goAttack(target)` for chases;
   `pathToLocation` (issued once per destination) for walks to a spot.
3. **Animal won't bite the player.** **Cause:** bites only target `fightingOpponent`. **Fix:** zero-damage
   `hitConsequences(nil, player, true, 0, false)` + `setHitReaction("")`, refreshed periodically.
4. **Every bite knocked the player down (stunlock).** **Cause:** `knockdownAttack = true` applies on every animal
   bite. **Fix:** false, and roll your own knockdown (bump sequence above) per ant type.
5. **Game crash when zombies fight animals.** **Cause:** `zombie:setTarget(animal)` -> zombie states read moodles
   the animal doesn't have (NPE). **Fix:** never set an animal as a zombie target; `pathToCharacter` + Lua damage.
6. **Ants back to full size after leaving and returning.** **Cause:** `AnimalData.setSize` clamps to the
   definition range on load and ageing; our `setSizeForced` only ran when we first saw the ant, and a quick
   reload reused the old Lua state. **Fix:** store the size in mod data; re-apply when a new object appears for the
   same animal ID and every 2 s.
7. **Sandbox labels with "%" broke the options screen.** **Cause:** labels go through Java `String.format`.
   **Fix:** write "percent".
8. **Every fresh corpse "smelled" from the maximum range.** **Cause:** `OnDeadBodySpawn` fires before `deathTime`
   is set, so the age looked like the whole world age. **Fix:** read the death time later (first refresh).
9. **Ants walked to food or a spot, stopped, gave up.** **Cause:** any failed path sets `shouldFollowWall`, and one
   failure was treated as "unreachable forever"; arrival was also measured to the tile corner while paths end at
   the tile centre. **Fix:** temporary blacklist, larger reach, compare against `x + 0.5, y + 0.5`.
10. **Ants never finished eating.** **Cause:** any zombie within the 40-tile hunt range pulled them off, and the
    retry-backoff branch dropped the meal every think. **Fix:** eating ants only react to adjacent zombies or
    attackers; backoff doesn't cancel idle tasks. Found only through per-ant debug logs.
11. **136 errors from minute one; natural nests never built (42.21).** **Cause:** `IsoGridSquare.Is(flag)` doesn't
    exist in this build (`has(...)`, `hasWater()`); the harness stub accepted it. **Fix:** `hasWater()`, plus the
    reflection-based API name check before every handoff.
12. **"attempted index: reportEvent of non-table: ActionContext".** **Cause:** `ActionContext` isn't exposed to Lua.
    **Fix:** `IsoGameCharacter:reportEvent("wasBumped")` on the player.
13. **Players silent when bitten by ants.** **Cause:** `DamageFromAnimal` plays no voice and fires no damage event.
    **Fix:** record body health at the attack start, check after the bite, `playerVoiceSound("PainFromBite")`
    (rate-limited per player).
14. **Fifty ants biting nearly crashed the audio driver.** **Cause:** dozens of overlapping one-shot clips. **Fix:**
    a global limiter (at most N bite/hiss clips started per 700 ms window).
15. **Larvae and queen slid a tile "in a wave" when shot at.** **Cause:** vanilla startle/flee moves animals even
    with `setBlockMovement(true)`; gunshot alerts also hit non-fighters. **Fix:** calm them each think and pin the
    position each tick (`setX/Y` + `setLastX/Y`); alerts skip ants that don't fight.
16. **"Why doesn't the nest exist at world creation?"** **Cause:** objects need loaded squares. **Fix:** choose and
    store the site at world start, build it when the ground loads (like vanilla's randomized world stories).
17. **Natural nest never found.** **Cause:** sites anywhere on the whole map. **Fix:** a 500-1500 tile ring around
    the start/current player, re-rolled every 15 in-game days.
18. **`console.txt` showed old errors after a fix.** **Cause:** it holds several sessions when the player returns
    to the main menu and loads again. **Fix:** analyse from the last `loading <modid>` line.
19. **Offline harness crashed on `math.atan2`.** **Cause:** lupa is Lua 5.5; the game's Kahlua is 5.1-like and has
    `atan2`. **Fix:** `local atan2 = math.atan2 or math.atan`.
20. **New caste models looked like the worker.** **Cause:** image-edit from the worker concept preserved too much.
    **Fix:** text-only prompts naming the caste's anatomy (physogastric abdomen; oversized head and mandibles).
21. **A big-headed soldier tore at the neck in hit reactions.** **Cause:** the head copies the pig's full head swing.
    **Fix:** weight only 60 percent of the head to the pig's head/neck bones (rest on the spine).
22. **Queen's rear legs moved with her abdomen.** **Cause:** a radius test for "leg vs body" failed when the abdomen
    was wider than the legs' reach. **Fix:** classify leg vertices by surface (geodesic) distance from each foot to
    the thorax core.

## Assets
- Concepts: `um fal image` / `um fal edit --ref` (nano-banana-2), white background. Nest: an isometric dirt mound
  on white -> `um fal rmbg` (BiRefNet); gpt-image-2 rejected `background=transparent` in this setup.
- 3D: `um fal model3d <concept> --engine meshy --faces 6000 --texture 1024` (Meshy v7.1), then pymeshlab quadric
  decimation with texture to 2.6-3.2k faces; base-colour texture resized to 512.
- Rigging to the pig skeleton (own scripts): split per-corner UVs to per-vertex, orient, align the creature's neck
  with the pig's, weight by anatomy (antennae -> ear bones, mandibles -> jaw, head/neck, thorax -> spine bones,
  abdomen -> pelvis/tail, front legs -> arm chain, rear legs -> leg chain, middle legs shared, foot bones unused,
  limb motion damped to 65-85 percent), smooth weights over the welded surface, max 4 influences. Grub larva: no
  legs, weighted along geodesic distance from the head onto Head/Neck/Spine1/Spine/Pelvis/Tail.
- Sounds: `um fal sfx` (ElevenLabs), then ffmpeg normalize -> trim silence -> gain to a target mean dB (two passes
  for short clips) -> limiter -> Vorbis; new voices matched to the existing clips' loudness within 1 dB.
- Credit: the ant roster (giant ant, giant soldier ant, super soldier ant, ant larva, giant queen ant) and their
  behaviours are adapted from Cataclysm: Dark Days Ahead (CleverRaven and contributors, CC BY-SA 3.0). The
  models, textures and sounds above are new.

## Cost and time
About two days (2026-10-08 to 10-09) across many sessions, including a standalone single-ant release that was
later folded into the pack. Asset generation: a few dozen fal calls (concepts, 5 image-to-3D runs, ~20 SFX).

## Open questions
- Multiplayer: server-side Lua is structured for it (commands, transmit calls) but untested.
- Real underground anthills (B42 underground levels) instead of a surface mound; CDDA's acid ant line, chitin/egg
  loot, grab/drag attacks and caste ageing aren't ported yet.
- Whether zombie attack animations on animals can be triggered at all without Java changes.
