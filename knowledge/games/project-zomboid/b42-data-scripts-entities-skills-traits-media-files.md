---
kind: game
title: 'Build 42 content as data: the script block census, entities and fluids, custom skills (perks.txt), traits, professions, challenges and media data files'
game: Project Zomboid
games_also: []
game_version: 'Build 42.21.0 (Steam, Windows 10). A survey: block counts from the install''s media/scripts, javap listings of projectzomboid.jar, the install''s Lua and media/ files; nothing was built or run in game for this note'
platform: windows
engine: java
route: loader-api
tools: ["Project Zomboid script system (media/scripts *.txt)", javap, "media/perks.txt (CustomPerks)", "PZwiki ScriptsDocs"]
anti_cheat: 'none (data modding; no client patching)'
status: in-progress
agents:
- Devin (SWE-2 Medium)
humans: [Alistair-Afton]
date: '2026-10-12'
links:
- "https://pzwiki.net/wiki/Scripts"
- "https://pzwiki.net/wiki/CraftRecipe_(scripts)"
- "https://pzwiki.net/wiki/Entity_scripts"
- "https://github.com/ZioPao/The-Only-Cure"
tags: [b42, scripts, items, recipes, craftrecipe, entities, components, fluids, vehicles, weapons, perks, skills, traits, professions, survivorswap, challenges, radio, recorded-media, music, fonts, effects, data-oriented]
---
# Build 42 content as data: script blocks, entities and fluids, skills, traits and media files

> Build 42 defines almost all content in `media/scripts/**/*.txt` block files: items, weapons, craft recipes,
> craft stations, vehicles, fluids, sounds, models, traits and professions. Custom skills are a `media/perks.txt`
> file, and radio shows, CDs, music and fonts are data too. This note is a census of the block types in a
> 42.21.0 install, the syntax they share, the entity/component system behind `entity` blocks, and the character
> data (skills, traits, professions, play-as and challenges). It's a survey: nothing was built and run in game.
> Start with the [orientation note](b42-modding-orientation-layout-lua-runtime-tooling-interop-ui.md).

## Setup
- Project Zomboid **42.21.0**, Steam, Windows 10. Census of the install's `media/scripts/`: `entities/` (craft
  stations and world entities), `generated/` (items, recipes, characters, sounds, vehicles, weapons, physics),
  `ragdolls/`, `xui/`.
- A mod adds the same blocks in its own `media/scripts/*.txt`, inside `module Base { }` (the vanilla namespace)
  or its own `module MyMod { }` (ids become `MyMod.Thing`). `imports { Base }` inside a module lets it refer to
  vanilla blocks and `base:` tags.

## Route and why
Data first. Before writing Lua, check whether the content is a script block; Lua is for behaviour only.

## How the game works (what we had to learn)

### Block census (42.21.0 install, approximate counts)
| Block | Count | What it is | Vanilla files to copy |
|---|---|---|---|
| `item` | 5105 | every inventory item | `generated/items/{weapon,food,clothing,drainable,container,literature,normal,...}.txt` |
| `model` | 3835 | mesh + texture + shader + `animationsMesh` | `generated/vehicles/*_model.txt` and other `model_*.txt` |
| `sound` | 3038 | named sounds: category, 3D falloff, clip variants | `generated/sounds/**` |
| `craftRecipe` | 969 | B42 crafting recipes (replaces B41 `recipe`) | `generated/recipes/recipes_*.txt` |
| `xuiSkin` | 254 | skins for the entity UI | `entities/**/entity_*_xuiSkin.txt`, `xui/` |
| `vehicle` | 241 | vehicles, including templates | `generated/vehicles/`, `template_*.txt` |
| `entity` | 239 | placeable workstations and objects built from components | `entities/<domain>/...` |
| `timedAction` | 119 | script-declared timed actions | `generated/`, with Lua in `TimedActions/` |
| `character_trait_definition` | 97 | traits | `generated/characters/character_traits.txt` |
| `physicsShape` | 90 | physics colliders | `generated/physics/` |
| `template` | 77 | reusable block templates | `vehicles/template_*.txt` |
| `animationsMesh` | 75 | binds a model to an animation folder and prefix | `model_*.txt` files |
| `ragdoll` | 66 | ragdoll definitions | `ragdolls/` |
| `evolvedrecipe` | 63 | add-ingredient cooking (soups, stir fry) | `generated/recipes/` |
| `fluid` | 61 | B42 fluid types | search `generated/` for `fluid ` |
| `mannequin` | 30 | mannequin outfits and poses | `generated/` |
| `fixing` | 29 | item repair recipes | search `generated/` for `fixing ` |
| `character_profession_definition` | 25 | professions | `generated/characters/character_professions.txt` |

Also present in small numbers: `physicsHitReaction`, `clock`, `energy`, `soundTimeline`, `vehicleEngineRPM`,
`animation`, `xuiConfig`, and `itemMapper` sub-blocks. `media/items/items.xml` is a generated registry, not
the authoring format.

### Shared syntax
- A block is `name Id { key = value, ... }` inside `module X { }`; `;` separates list values.
- Item references: `[Base.Axe;Base.Saw]` is an explicit list; `tags[base:saw;base:crudesaw]` means any item whose
  `Tags` include one of them; `mapper:name` resolves the output through an `itemMapper` block with a `default`.
- Recipe input flags: `mode:keep` (a tool, not consumed) vs `mode:destroy` or the default (consumed);
  `flags[Prop1]`/`flags[Prop2]` pick the hand slot in the craft UI, `MayDegradeLight` costs a little condition,
  `InheritCondition` passes condition to the output.
- `template! = Name` inherits a `template` block and overrides keys (vehicle variants use it heavily).
- `Icon = Foo` resolves `media/textures/Item_Foo.png`. Display strings are translation keys
  (`DisplayName`, `Tooltip`, `UIName`).

A recipe in the vanilla shape (ids made up):
```
module MyMod {
  imports { Base }
  craftRecipe SawHardwood {
    timedAction = SawLogs,
    time = 300,
    Tags = InHandCraft;CanBeDoneFromFloor,
    category = Carpentry,
    xpAward = Woodwork:8,
    inputs {
      item 1 [MyMod.HardwoodLog] flags[Prop2],
      item 1 tags[base:saw] mode:keep flags[MayDegradeLight;Prop1],
    }
    outputs {
      item 4 MyMod.HardwoodPlank,
    }
  }
}
```
`timedAction` names a `timedAction` block (here a vanilla one); `category` is the craft UI tab. Recipes that
belong to a station are listed in that entity's `CraftBench` component instead of being global.

### Items, weapons and vehicles
- **Items:** `ItemType = base:weapon|food|clothing|drainable|normal|...`, `Weight`, `DisplayCategory`, `Tags`,
  `ClothingItem` + `BodyLocation` (clothing), `AttachmentType` (hotbar slot), `EatType`, `PourType`,
  `ReplaceOnUse`, `UseDelta`, `WorldStaticModel` (the model on the ground).
- **Weapons** are items: damage (`MinDamage`/`MaxDamage`), reach (`MinRange`/`MaxRange`), `BaseSpeed`,
  `CriticalChance`, `KnockdownMod`, `PushBackMod`, condition (`ConditionMax`, `ConditionLowerChanceOneIn`),
  `Categories`, `SwingAnim`/`IdleAnim`/`RunAnim`, and sounds (`SwingSound`, `HitSound`, `BreakSound`,
  `EquipSound`, `BringToBearSound` ...), plus ammo, magazine and fire-mode fields for guns. There are no new
  damage types: a special attack is an existing damage path plus Lua (Java-surface note).
- **Vehicles:** `model { file, scale, offset }` pointing at a `model` block, `skin { texture }` (several = paint
  jobs, PNGs in `media/textures/Vehicles/`), `extents`, `mass`, `centerOfMassOffset`, `physicsChassisShape`,
  shadow, `attachment` (trailer, seats, doors), `crawlThroughWheel`, and `template! = ...` for parts, engine and
  sounds (`template_*.txt`, `vehicleEngineRPM`). Part ids such as `Engine`, `GasTank` and the door parts drive
  the mechanics Lua in `client/Vehicles`: rename meshes freely, keep the part ids (the
  [vehicle-port technique note](../../techniques/porting-a-vehicle-semantic-traps.md)
  covers the semantics side of a port).

### Entities: the B42 component runtime
- `entity` blocks build **`GameEntity`** objects from components. The runtime is the `zombie.entity` package
  (`GameEntityManager`, `GameEntityNetwork` for MP sync, `MetaEntity`/`MetaEntitySystem` for entities in unloaded
  chunks, `EntityBucket` batching, `ComponentScriptFactory`). It is not `zombie.characters.ecs`, which is a
  small scaffold on characters (five public classes).
- Component packages in `zombie.entity.components`: `attributes`, `build` (`BuildLogic`), `combat`
  (`Durability`), `contextmenuconfig`, `crafting` (`CraftBench`, `CraftLogic`, `FurnaceLogic`, `DryingLogic`,
  `MashingLogic`), `fluids` (`FluidContainer`, `FluidType`, `PoisonEffect` ...), `lua` (`LuaComponent`), `parts`,
  `resources` (`Resource`, `ResourceChannel`, `LogisticsSystem`), `signals`, `sounds`, `spriteconfig`, `ui`.
  Components are Java types; a mod composes them in script data and adds behaviour through `LuaComponent`.
- An entity in the vanilla shape (ids made up):
```
entity MyMod_SmokerDrum {
  component UiConfig { xuiSkin = default, entityStyle = ES_MyMod_SmokerDrum, uiEnabled = true, }
  component CraftBench { Recipes = MyMod_SmokeMeat, }
  component SpriteConfig { health = 100, skillBaseHealth = 20,
    face SINGLE { layer { row = mymod_smoker_01_0, } } }
  component CraftRecipe { timedAction = BuildLowNoTool, time = 50, category = Cooking,
    Tooltip = Tooltip_MyMod_SmokerDrum,
    inputs { item 1 [Base.MetalDrum], item 2 [MyMod.WireRack], } }
}
```
  `SpriteConfig` names the sprite per facing, `CraftRecipe` is what building it costs, `CraftBench` lists the
  recipes it runs. Each vanilla entity pairs its `entity` file with an `entity_*_xuiSkin.txt` that defines the
  `entityStyle`. The vanilla `entities/` folders (agricultural, animals, appliances, barricades, blacksmith,
  fences_low, furniture, misc, outdoors, stairs, walls) are the only schema reference: copy the closest one.
- **Fluids:** a `fluid` block defines the type; containers and food declare capacity and contents. The
  `FluidContainer` API: `addFluid`, `adjustAmount`, `canAddFluid`, `getAmount`, `getCapacity`,
  `getFreeCapacity`, `getPrimaryFluid`, `getRainCatcher`, `getPoisonEffect`/`getPoisonRatio`, `copyFluidsFrom`,
  `CanTransfer`/`Transfer`, `Empty`. Fluids mix, have colours and can be poisonous; `ISFluidContainerMenu` is the
  vanilla UI.
- When to use what: an `entity` for interactive objects that stock components cover (it saves and syncs);
  a global-object system for behaviour no component covers (world note); a plain item for anything without a
  world presence.

### Characters: custom skills, traits, professions
- **Custom skills are data.** `CustomPerks` (with `CustomPerk`: `id`, `parent`, `passive`, `translation`, `xp`)
  loads `media/perks.txt`. B42 mods ship it, e.g. The Only Cure's `42/media/perks.txt`. The shape:
```
VERSION = 1,

perk MyMod_Beekeeping
{
    parent = Survivalist,
    translation = MyMod_Beekeeping,
    passive = false,
    xp1 = 75, xp2 = 150, xp3 = 300, xp4 = 750, xp5 = 1500,
    xp6 = 3000, xp7 = 4500, xp8 = 6000, xp9 = 7500, xp10 = 9000,
}
```
  `parent` is the skills-panel category (a parent of `None` makes a new category, as The Only Cure does).
- **The Java route** is `PerkFactory.AddPerk(perk, name, [parent,] xp1, ..., xp10 [, passive])`: four overloads,
  each with **10** ints. `PerkFactory.Perk` has `getXp1`...`getXp10`, `getXpForLevel` and `getTotalXpForLevel`,
  so the ints are the XP for each level, as in perks.txt. Use perks.txt unless the values must be computed.
- Registered perks show up in the skills panel (`ISCharacterInfo`, `ISPlayerStatsUI` read `PerkFactory`).
  Levels: `getPerkLevel(perk)`, `setPerkLevelDebug(perk, n)`; XP: `getXp():AddXP(perk, amount)`. A perk does
  nothing by itself: your Lua reads the level and applies the effect.
- **Traits and professions** are `character_trait_definition` (cost, `MutuallyExclusiveTraits`, `XPBoosts`,
  `GrantedRecipes`, `IsProfessionTrait`, `DisabledInMultiplayer`, `UIName`/`UIDescription`) and
  `character_profession_definition` (adds free clothing and starting items) blocks. In 42.21 Lua checks a trait
  with `player:hasTrait(trait)`, where `trait` is a `CharacterTrait` (constants such as `CharacterTrait.ATHLETIC`,
  lookup with `CharacterTrait.get`), and reads or edits the set through `player:getCharacterTraits()`
  (`getKnownTraits`, `add`, `remove`, `set`). Stock trait effects are hard-coded; a custom trait's effect is
  your Lua. The creation screen is `client/OptionScreens/CharacterCreationProfession.lua`.
- **Play as someone else:** `media/lua/shared/NPCs/SurvivorSwap.lua` is a vanilla table behind the debug
  "Survivor Swap" menu. `SurvivorSwap.applyCharacter(player, data)` rewrites name, profession, traits, perk levels
  (through `setPerkLevelDebug`), weight, sex, voice (type, pitch, prefix), hair, beard and skin, then calls
  `resetModel()`. `SurvivorSwap.Survivors` and `Loadouts` are tables a mod can extend.
- **Challenges** (`media/lua/client/LastStand/`): a Lua table registered with `addChallenge(table)`, with hooks
  such as `OnGameStart` and `OnInitWorld` (which overwrites `SandboxVars`) and a same-named `.png` thumbnail.
  Vanilla examples: `AReallyCDDAy` blows up a room at spawn with
  `IsoFireManager.explode(getCell(), square, 100000)`; `WinterIsComing.lua`, `28MinutesLater.lua` and
  `TopOfTheWorld.lua` show the other hooks.

### Media data files
- **Radio and TV:** `media/radio/RadioData.xml` drives every broadcast: `VoiceEntry` (speaker id and colour),
  `Adverts`, and per-channel `ScriptEntry` blocks (`startdelay`, `loopmin`/`loopmax`) of `BroadcastEntry` items
  with a `day` index (how broadcasts run out as the apocalypse goes on) and `LineEntry` lines. Dynamic channels
  (the weather report) are Lua in `server/radio/ISDynamicRadio.lua`; text lives in `RadioData.json` and
  `DynamicRadio.json`.
- **Recorded media (CDs, VHS):** `media/lua/shared/RecordedMedia/recorded_media.lua` is a generated table of
  `RecMedia["<guid>"] = { title, author, category = "CDs"|..., spawning, lines = { { text, r, g, b, codes } } }`
  where every string is an `RM_<guid>` translation key. Line `codes` such as `LEAR...` grant skill XP while
  watching. A custom tape = a new entry, its `RM_` keys and an item that references the GUID.
- **Music:** `media/lua/client/Music/MusicChoices.lua` scores tracks against a drama value (from the visible and
  chasing zombie counts); `media/music/luatriggered/` holds cues that only play when Lua triggers them; same-named
  files replace the menu theme.
- **Fonts and effects:** `media/*.fnt` with `*_0.png` pages are AngelCode bitmap fonts; `media/effects/*.txt`
  are key-value parameter files for bullet tracers and similar effects; `media/shaders/` holds GLSL pairs plus a
  `README-Shaders.txt` on the GL 2.1 fallback (whether a mod can override a shader is untested). Videos are
  Bink (`.bik`).

## Build steps
1. Pick the block type, copy the nearest vanilla file's shape into `media/scripts/mymod_<thing>.txt` under your
   own `module` (or `module Base` when vanilla code must find it by its plain name).
2. Translation keys (`ItemName_`, `Tooltip_`, `UI_trait_`, `Sandbox_` ...) in
   `media/lua/shared/Translate/EN/*.json`; icons as `media/textures/Item_<Name>.png`.
3. A station: an `entity` block and its `xuiSkin` file, copied as a pair from the closest vanilla entity.
4. A skill: `media/perks.txt`; read its level from Lua where it should matter.
5. Launch with `-debug` and read `console.txt`: script errors name the module, block and line.

## Verification
- Survey only. Read on 42.21.0: the `media/scripts` block counts, the vanilla `entities/` tree,
  `SurvivorSwap.lua`, the `LastStand` challenges, `RadioData.xml`, `recorded_media.lua`, `MusicChoices.lua`, and
  javap listings of `zombie.entity`, `PerkFactory` and `CustomPerks`.
- At review time the Java names were checked against the unofficial 42.21.0 javadocs
  (albion.codeberg.page/PZ-JavaDocs), and the perks.txt shape against The Only Cure's `42/media/perks.txt`.
- Not verified: anything in game. Not tried: a new entity from scratch, a custom `xuiSkin`, `LuaComponent`'s
  script grammar, a perks.txt skill, a custom radio channel or CD, `clock`/`energy` blocks.

## Gotchas
1. **A recipe doesn't show in the craft UI.** Cause: a missing translation for its `category`, or `Tags` that
   don't allow where you craft (`InHandCraft`, `CanBeDoneFromFloor` vs bench-only). Fix: add the key; check the
   tags.
2. **The tool got consumed.** Cause: no `mode:keep`. Fix: `item 1 tags[base:saw] mode:keep ...`.
3. **The wrong output variant.** Cause: the input isn't listed in the recipe's mapper, so it falls through to the
   `itemMapper`'s `default`. Fix: map every input.
4. **`base:` tags fail in your module.** Cause: no `imports { Base }`. Fix: add it.
5. **The item icon is invisible.** Cause: `Icon = X` without `media/textures/Item_X.png`. On the ground it also
   needs a `WorldStaticModel` pointing at a `model` block.
6. **A vehicle spawns as a cube or with odd collision.** Cause: `model.file` must name a `model` block that
   points at the mesh, and the scales differ between the mesh and the vehicle model block in vanilla. Fix: copy a
   vanilla vehicle's model/script pair and change one thing at a time.
7. **An entity builds but has no UI.** Cause: its `entityStyle` isn't defined in an xui skin file. Fix: copy the
   vanilla `entity` + `entity_*_xuiSkin.txt` pair together.
8. **A trait does nothing.** Cause: stock trait effects are hard-coded to the vanilla traits. Fix: your Lua checks
   `player:hasTrait(trait)` and applies the effect.
9. **Redeclaring a vanilla item doesn't stick, or breaks another mod.** Cause: two mods redeclaring
   `item Base.Foo` resolve by load order. Fix: change single fields at `OnGameBoot` through
   `getScriptManager():getItem("Base.Foo")` instead.
10. **A container shows empty and can't be filled.** Cause: only half the fluid pair was copied (the `fluid` type
    or the container's capacity fields). Fix: copy both sides from a vanilla container.
11. **Skill or XP changes made on an MP client don't stick.** Cause: B42 MP is server-authoritative. Fix: grant XP
    on the server.
12. **Trait edits don't show in the character screen.** Cause: the info panel caches them. Fix: SurvivorSwap sets
    `refreshNeeded = true` on the panel's `charScreen` (it gets the panel with the Lua function
    `getPlayerInfoPanel`).
13. **Hair or outfit edits don't redraw.** Cause: the avatar isn't rebuilt. Fix: `resetModel()` after visual
    edits.
14. **A challenge starts with the player's preset values.** Cause: `OnInitWorld` didn't set every `SandboxVars`
    value it relies on. Fix: set all of them.
15. **A custom CD shows raw keys.** Cause: lines that aren't `RM_<guid>` keys in the translation files. Fix: add the
    keys; set `spawning` for loot eligibility.
16. **A broadcast never airs.** Cause: its `day` is outside the world's day range. Fix: check `day` and the loop
    values.

## Assets
- Items, vehicles and entities are script plus textures and models; entity sprites come from tile definitions
  (`.pack`/`.tiles`, CDDA note); vehicle paint jobs are PNGs in `media/textures/Vehicles/`.

## Cost and time
Part of one research session on 2026-10-12.

## Open questions
- The full component list and per-component grammar for `entity` blocks (javap on `zombie.entity.components` or
  `ComponentScriptFactory`).
- Whether a `timedAction` block can replace an `ISBaseTimedAction` Lua class for a custom action.
- The translation key pattern for a perks.txt `translation` value (copy it from a shipped mod meanwhile).
- `mannequin` block fields beyond outfit and pose; `ResourceChannel`/`LogisticsSystem` semantics.
