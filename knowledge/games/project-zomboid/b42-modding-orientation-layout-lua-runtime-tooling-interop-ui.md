---
kind: game
title: 'Build 42 modding orientation: mod anatomy, the Lua runtime, tooling, interop between mods and the ISUI framework'
game: Project Zomboid
games_also: []
game_version: 'Build 42.21.0 (Steam, Windows 10). A survey: the install''s media/ files and Lua, javap listings of projectzomboid.jar, and the files of the Workshop mods named below; nothing was built or run in game for this note'
platform: windows
engine: java
route: loader-api
tools: ["Project Zomboid Lua (Kahlua) mod API", "PZ-Umbrella EmmyLua stubs", "demiurgeQuantified/ZomboidDecompiler (Vineflower)", javap, "PZAPI.ModOptions", "um win (game automation)"]
anti_cheat: 'none in single player; mods are Lua and data the game loads itself. Dedicated servers run server-side checks, see the multiplayer note'
status: in-progress
agents:
- Devin (SWE-2 Medium)
humans: [Alistair-Afton]
date: '2026-10-12'
links:
- "https://pzwiki.net/wiki/Modding"
- "https://github.com/PZ-Umbrella/Umbrella"
- "https://github.com/demiurgeQuantified/ZomboidDecompiler"
- "https://www.projectzomboid.com/modding/"
- "https://steamcommunity.com/sharedfiles/filedetails/?id=3403180543"
- "https://steamcommunity.com/sharedfiles/filedetails/?id=3405043636"
- "https://steamcommunity.com/sharedfiles/filedetails/?id=3813871509"
tags: [b42, orientation, mod-structure, lua, kahlua, events, timed-actions, context-menu, ui, isui, modoptions, translations, debug, tooling, testing, interop, load-order, compat, workshop]
---
# Build 42 modding orientation: mod anatomy, the Lua runtime, tooling, interop and the ISUI framework

> Where to start on Project Zomboid Build 42: what goes where in a mod, how the Lua (Kahlua) runtime loads and
> calls into Java, the debug and test loop, how mods expose APIs to each other and patch each other, and the
> vanilla ISUI widget library. It's a survey of a 42.21.0 install (its `media/` tree and Lua, javap listings)
> and of other people's mods; nothing here was built and run in game. Five companion notes go deeper:
> [data](b42-data-scripts-entities-skills-traits-media-files.md),
> [creatures](b42-creatures-dressed-zombies-ports-and-npc-frameworks.md),
> [Java surface](b42-java-surface-lua-callable-api-and-engine-internals.md),
> [multiplayer](b42-multiplayer-internals-packets-gameserver-sync.md) and
> [world](b42-world-loot-stories-zones-tiles-maps-worldgen.md).

## Setup
- Project Zomboid **42.21.0** from Steam (app 108600), Windows 10. Install: `projectzomboid.jar` (all game code,
  unobfuscated Java), `jre64\`, `media\` (all vanilla data and Lua, readable: the reference for every format),
  `Workshop\ModTemplate\` (the official upload template, including a two-map example), `mods\`.
- Already covered on main, so not repeated here:
  - the B42 mod layout (`mods/<id>/42/{mod.info, poster.png, media/...}` plus `common/`), the `mod.info` keys and
    the sandbox-option format: [CDDA ants note](cdda-enemy-pack-ants-custom-hostile-animals-a-breeding-colon.md),
    Setup and "Other mod.info / sandbox facts";
  - how the game picks one numbered version folder plus `common/`, the user-data folders (`console.txt`, `Logs`,
    `Saves`, `Lua\pz_modlist_settings.cfg`), Workshop download paths and `require=`:
    [42.20 modlist note](b42-20-modlist-preset-and-world-load-errors.md);
  - the javap command line and the reflection lister for checking what Lua can call: the CDDA note's Setup.
- No loader to install: the game is the mod loader. The `-debug` launch option turns on the debug menus.

## Route and why
Loader API. PZ mods are data plus Lua that the game loads natively; there is no BepInEx-style loader and none is
needed. The jar is unobfuscated, so bytecode patching is possible, but it can't be shipped on the Workshop and the
mods surveyed here never needed it.

## How the game works (what we had to learn)

### Mod anatomy additions
- `mod.info` keys seen beyond those in the CDDA note: repeatable `description=` lines, `icon=`, `versionMin`,
  `map=` (map mods, see the world note). Keep the file name lowercase `mod.info` for Linux servers.
- **Lua and other files override by relative path.** A mod file at the same path as a vanilla file
  (`media/lua/shared/...`, `media/AnimSets/...`, `media/scripts/...`) replaces it, and between two mods the
  later one wins. Put your files in a subfolder named after the mod (`media/lua/shared/MyMod/...`).
- What each `media/` folder holds:

| Folder | Contents |
|---|---|
| `lua/{shared,client,server}` | Lua; see "Load lifecycle" below |
| `scripts/` | `module X { ... }` block files: items, recipes, models, sounds, vehicles, entities (data note) |
| `models_X/`, `anims_X/` | meshes (`Skinned/` for rigged) and animation clips: `.x` (text DirectX), `.fbx`, `.glb` |
| `AnimSets/<entity>/<state>/*.xml`, `actiongroups/` | animation state graph (creatures note) |
| `clothing/clothingItems/*.xml`, `fileGuidTable.xml` | clothing definitions and the GUID registry every clothing XML needs |
| `textures/` | PNGs; `Item_<Name>.png` is the icon for `Icon = <Name>` |
| `texturepacks/*.pack` | tile sprite packs (format in the CDDA note) |
| `sound/`, `music/`, `videos/` | `.ogg`/`.wav` bound by `sound` script blocks; music; Bink video |
| `sandbox-options.txt` | sandbox options (format in the CDDA note) |
| `lua/shared/Translate/<LANG>/*.json` | translation keys (`IG_UI_`, `Sandbox_`, `Tooltip_`, `ItemName_`, `ContextMenu_` ...) |
| `maps/<MapName>/` | map mods (world note) |

### Load lifecycle
1. `shared/` runs first in every context, then `client/` (single player and MP clients) or `server/` (single
   player's internal server and dedicated servers). Single player runs both. `shared/` also runs at main-menu
   boot, before any world exists, so guard world code behind `OnLoad`/`OnGameStart` or a non-nil `getCell()`.
   (The [B41 note](b41-modpack-fix-mods-and-linux-dedicated-server.md) found `server/` files only load when a
   world starts.)
2. `require 'X'` resolves from the `media/lua/` roots, `shared/` first; keep one file per name.
3. Returning to the main menu and loading a save runs the Lua again. Register handlers once (guard with a flag)
   or they multiply.

### Calling Java from Lua
- Kahlua is a Java Lua close to 5.1. Lua calls **public methods** of exposed classes (`z:getHealth()`,
  `Class.staticMethod()`); it can't read an object's Java **fields** (`manager.choices` is nil). Find the
  getter. Singletons are reached through their static `instance` (`ScriptManager.instance`,
  `VirtualZombieManager.instance`), as vanilla Lua and the mods surveyed do.
- Useful globals: `getCell()`, `getWorld()`, `getPlayer()`, `getGameTime()`, `getScriptManager()`,
  `getSoundManager()`, `ZombRand`, `instanceof`, `Events`, `SandboxVars`, `ModData`, `getText`,
  `isClient()`/`isServer()`, `sendClientCommand`/`sendServerCommand`, `getActivatedMods()`,
  `getModFileReader`/`getModFileWriter`.
- Kahlua picks an overload by argument count and types; a wrong argument type can silently call the other
  overload (`ItemContainer.AddItem` has several).
- Names move between 42.x builds (`IsoGridSquare.Is` became `has` in 42.21; CDDA note gotcha 11). Check every
  `obj:method(` your mod calls against a javap or reflection dump of the build you target, and against the
  [Java-surface note](b42-java-surface-lua-callable-api-and-engine-internals.md).
- All vanilla Lua is readable under `media/lua/`, and `media/luaexamples/` has small timed-action, UI and
  `ISTimer` examples. Grep them before inventing an API.

### Events
`Events.<Name>.Add(fn)` / `.Remove(fn)`; the Umbrella stubs list every event with its arguments. The families a
mod uses most:
- boot and time: `OnGameBoot`, `OnGameStart`, `OnLoad`, `OnSave`, `OnInitWorld`, `OnTick`, `OnTickEvenPaused`,
  `EveryOneMinute`, `EveryHours`, `EveryDays`;
- world: `OnGridSquareLoaded`, `OnObjectAdded`, `OnWorldSound`, `OnDeadBodySpawn`, `OnSeeNewRoom`;
- characters: `OnZombieUpdate`, `OnZombieCreate`, `OnZombieDead`, `OnCharacterDeath`, `OnPlayerUpdate`,
  `OnPlayerGetDamage`, `OnWeaponHitCharacter`, `OnWeaponSwing`;
- menus: `OnFillWorldObjectContextMenu`, `OnFillInventoryObjectContextMenu`;
- network: `OnClientCommand` (fires on the server), `OnServerCommand` (fires on the client),
  `OnReceiveGlobalModData`; input and UI: `OnKeyPressed`, `OnCustomUIKey`, `OnCreateUI`, `OnResolutionChange`.

`OnZombieUpdate` fires for every zombie on every update: keep the handler O(1) and do heavy work on a staggered
think window (the CDDA ants use 15-tick windows).

### Timed actions, context menus, settings, persistence
- **Timed actions:** subclass `ISBaseTimedAction` (`media/lua/shared/TimedActions/` in B42; client-only ones such
  as reading stay in `client/TimedActions`), implement `isValid`, `update`, `start`, `stop`, `perform` (and
  `complete` for the authoritative effect, per the CDDA note), queue with
  `ISTimedActionQueue.add(MyAction:new(character, ...))`. Copy the nearest vanilla action rather than starting
  blank; script-side `timedAction` blocks declare the data.
- **Context menus:** `Events.OnFillWorldObjectContextMenu.Add(function(player, context, worldobjects, test) ...)`
  then `context:addOption(getText("ContextMenu_MyMod_DoThing"), target, MyMod.doThing, arg)`. When `test` is
  true the game only asks whether you would add options: change nothing. Vanilla reference:
  `ISWorldObjectContextMenu`.
- **Settings:** `PZAPI.ModOptions` (`media/lua/client/PZAPI/ModOptions.lua`) is the vanilla in-game mod-settings
  UI. `PZAPI.ModOptions:create(modID, name)` (as Bandits 42.20 calls it) returns an options object with
  `addTitle`, `addDescription`, `addTickBox`, `addComboBox`, `addTextEntry`, `addKeyBind` ..., read back by
  option id. Use it for per-player preferences and `sandbox-options.txt` for world settings that belong in the
  save.
- **Persistence:** `ModData.getOrCreate(key)` (global, plain data only) and `obj:getModData()` (per object,
  item or character). Neither syncs by itself in MP: see the multiplayer note.
- **Translations:** `getText("Key")` reads `Translate/<LANG>/*.json`; a missing key or an invalid JSON file shows
  the raw key.

### Tooling and the debug loop
- **Launch options:** `-debug` (debug menus, Lua debugger, animator and object inspectors, item spawner, cheat
  toggles such as god mode and no-clip), `-debuglog=<channels>` (filters `DebugLog` channels, names from the
  `zombie.debug.DebugType` enum), `-cachedir=<path>` (use a scratch profile so test saves and options don't touch
  the real one), `-nosteam`. `options.ini` in the profile sets windowed or full screen.
- **`zombie.debug`** (jar) holds the debug windows (`BaseDebugWindow` subclasses, including the animator window
  that shows a character's live AnimSet state and variables), `DebugOptions`/`BooleanDebugOption`, the `DebugLog`
  engine, `LineDrawer` (world-space debug lines) and `DebugCSVExport*` dumpers. These are developer tools, not a
  runtime API to build features on.
- **Reading a Lua error in `console.txt`:** stack frames name the mod file (`function: <name> -- file: <path>`)
  followed by the Kahlua error. `attempted index of nil` is usually a `.field` read or a nil getter result,
  `number expected, got table` a wrong argument type, and `se.krka.kahlua...` frames mark the Java boundary. A Lua
  error kills that call, not the game: a broken `OnZombieUpdate` handler just stops your creatures, so read the
  log after every test. `console.txt` is rewritten at each launch (copy it first) and holds every world load
  of that launch (CDDA note gotcha 18).
- **Iteration:** script, texture and sound changes load with the world; Lua changes need a return to the main menu
  and a reload of the save, not a restart. Keep one test save per feature and use debug spawns.
- **Scripted in-game checks:** launch windowed at a fixed size (`-debug -cachedir=<scratch> -width 1280 -height
  720`), drive the menus with `um win` (see the `game-automation` skill), let an `OnTick` test file spawn, check
  and print `[TEST] PASS/FAIL` lines, then parse `console.txt` and screenshot checkpoints. Kill the game by
  exact PID (`um win kill <pid>`).
- **Reading the code:** javap for "does it exist" and ZomboidDecompiler (Vineflower plus Rosetta parameter names)
  for "how does it work". Keep decompiled output outside any repo you publish and describe it in your own words.
  The official javadocs live at `projectzomboid.com/modding/`; the Umbrella stubs give IDE autocomplete for the
  whole API but can lag a new build, where javap is current.

### Interop between mods
- **Dependencies:** `require=` in `mod.info` is a hard dependency and its mods load first; the preset note covers
  how the load order follows the preset line. `id=` is the key others require; the folder name and the Workshop
  id are different strings.
- **A public API is a global table:** `MyMod = MyMod or {}` with functions in `shared/` is callable from every
  mod that loads later. Add `MyMod.API_VERSION` so dependents can feature-gate, and prefer registration hooks
  (`MyMod.registerThing(fn)`) over letting others wrap your functions.
- **Soft dependencies:** feature-detect (`if type(OtherMod) == "table" then ... end`) rather than checking
  `getActivatedMods()`, because mod ids differ between uploads. Do cross-mod registration late (`OnGameStart`)
  when every `shared/` file has run, and keep every touch of another mod's globals in one compat file per mod
  (ProjectALife ships a `Compat/` folder of such adapters, see the creatures note).
- **Global namespaces collide:** Lua file paths, script `module` names, ModData keys, outfit names, sound names,
  clothing GUIDs and sandbox option namespaces (`SandboxVars.MyMod.Option`) are all shared. Prefix every one.
- **Four shipped ways to build on another mod** (file inspection of the Workshop mods, 42.x):
  - *Content registered into a framework:* **BanditsWeekOne** (on the Bandits NPC framework) ships a
    `registries.lua` per version folder plus its own event scheduler (police, SWAT, medics, firefighters, hazmat
    call-outs with per-service on/cooldown knobs) and three broadcast networks (`media/sound/Broadcasts/...`
    plus a generated sound table) that tell the outbreak through radio and TV.
  - *Wrapping another mod's functions:* **BeyondOneWeek** patches BanditsWeekOne by prepending gates to its
    global functions (`FDUtils.PrependFunction(BWOEvents.CallHazmats, chanceFunc)`) or replacing one wholesale,
    in a file whose banner says it overrides BWO functions. Wrap rather than copy, so updates of the host still
    flow through; label every override file; tune through `SandboxVars`.
  - *A bridge between two frameworks:* **CDALifePatch** (no assets) translates one mod's relation vocabulary into
    another's, detects the other mod's actors by a ModData flag behind `hasModData()` guards and `pcall`, and
    returns an explicit "unknown" stance instead of guessing.
  - *A custom data format:* **ALifeKnoxFractured** ships `.alife` text files that its framework parses after
    reading them with `getModFileReader(modID, relativePath, false)`, and registers the records additively ("no
    base records replaced"). Any mod can ship its own file format this way.

### The ISUI framework (`media/lua/client/ISUI/`, about 140 files)
- A retained-mode widget library: `ISUIElement` (base), `ISPanel`, `ISCollapsableWindow`, `ISButton`,
  `ISTickBox`, `ISComboBox`, `ISTextEntryBox`, `ISScrollingListBox`, `ISTabPanel`, `ISRichTextPanel`,
  `ISModalDialog`, progress bars, colour pickers, `ISRadialMenu` and its variants, `ISUI3DModel` (a live 3D
  model in a panel, as in character creation), and the XUI skin/layout classes (`ISXuiBuilder`, `ISXuiSkin`,
  `ISXuiTableLayout`). Feature windows worth copying: the inventory pages, `ISTradingUI`,
  `ISFluidContainerMenu`, `ISDesignationZonePanel`, the map windows.
- A custom window: `MyWin = ISCollapsableWindow:derive("MyWin")`, `initialise()` calling the parent's,
  `createChildren()` adding widgets with `self:addChild`, then `addToUIManager()`; toggle with `setVisible`. Lay
  out in pixels (anchor to `getCore():getScreenWidth()/getScreenHeight()` on resolution change) or with the XUI
  layout classes. Controller support is a separate code path (`ISPanelJoypad` and the other `Joypad` classes).
- World-space drawing: `ISCoordConversion.ToScreen/ToWorld` with `getRenderer()` (vanilla
  `ISBuildingBlueprintManager` is the example) and the UI draw events. Input: `shared/keyBinding.lua` (bindable
  keys), `Events.OnKeyPressed`, and `media/gamecontrollerdb.txt` (SDL pad mappings).

## Build steps
1. `Zomboid/mods/<id>/42/mod.info` plus `media/` (layout in the CDDA note); enable it in the Mods screen.
2. Lua in `media/lua/{shared,client,server}/MyMod/`: definitions and guarded event registration in `shared/`, UI
   and context menus in `client/`, world changes and spawning in `server/`.
3. Data (items, recipes, models, sounds) as `media/scripts/*.txt` blocks: see the data note.
4. Settings: `sandbox-options.txt` plus `Translate/EN/Sandbox.json` for the world, `PZAPI.ModOptions` for player
   preferences.
5. Test with `-debug`, read `console.txt` after every session, script the repeatable checks.
6. Publish from `Zomboid/Workshop/<id>/` (layout in the CDDA note's Build steps and the B41 note):
   `workshop.txt` takes `version=1`, `title`, repeatable `description=` lines, `tags` (allowed values in the
   install's `media/WorkshopTags.txt`) and `visibility`; `preview.png` is 256x256. Upload from the main menu's
   Workshop entry; uploading again from the same folder updates the item.

## Verification
- Survey only. Read on 42.21.0: the `media/` tree and Lua cited above (`ISUI/`, `PZAPI/ModOptions.lua`,
  `TimedActions/`, `luaexamples/`, `WorkshopTags.txt`, `Workshop/ModTemplate`), javap listings of the
  `zombie.debug` package, and the files of BanditsWeekOne, BeyondOneWeek, CDALifePatch and ALifeKnoxFractured.
- At review time the Java names in this note were checked against the unofficial 42.21.0 javadocs
  (albion.codeberg.page/PZ-JavaDocs).
- Not verified: anything in game. That includes the scripted-test loop, building a window, `PZAPI.ModOptions`
  calls (copy them from the vanilla file), every event's exact arguments on 42.21 (use the Umbrella stubs), and
  the load order of mods that don't depend on each other.

## Gotchas
1. **`attempted index ... of non-table: null` on a Java object.** Cause: reading a Java field (`obj.someField`);
   Lua only sees public methods. Fix: find the getter or another exposed path.
2. **A handler runs two or more times.** Cause: the Lua runs again when a save is reloaded and `Events.X.Add`
   wasn't guarded. Fix: `if MyMod._registered then return end MyMod._registered = true`.
3. **`getCell()` is nil in a `shared/` file.** Cause: shared Lua also runs at main-menu boot. Fix: touch the
   world from `OnLoad`, `OnGameStart` or later.
4. **A vanilla feature broke after adding a mod file.** Cause: a generic file name at a vanilla path replaced the
   vanilla file (Lua, AnimSets, scripts). Fix: mod-named subfolders and file names.
5. **Another mod's file silently "doesn't run".** Cause: two mods ship the same relative path; the later one wins
   with no warning. Fix: namespace your paths; check other mods' paths when two conflict.
6. **The mod doesn't load at all.** Cause: `mod.info` only in `common/`, a version folder the build doesn't pick
   (preset note), or a hidden `.txt` extension on `mod.info`. Fix: `42/mod.info`, file extensions shown.
7. **A context-menu option changes things while the menu is only being built.** Cause: work done while `test` is
   true. Fix: return early when `test` is true.
8. **Arguments vanish in `sendClientCommand`.** Cause: only plain data crosses (numbers, strings, booleans, plain
   tables). Fix: send `getOnlineID()` or coordinates and look the object up on the other side.
9. **`getText` shows the key.** Cause: a missing key, an invalid JSON file, or a folder not named exactly
   `Translate`. Fix: validate the JSON; match the key exactly.
10. **A tick or zombie-update handler silently stops.** Cause: a Lua error ends that call every time it fires.
    Fix: read `console.txt` after every test; wrap risky think functions in `pcall` and log.
11. **Behaviour differs without `-debug`.** Cause: debug options and cheats (god mode, invisible) change what
    the AI does. Fix: do the final check of a feature without `-debug`.
12. **Your `print` lines are missing.** Cause: a `-debuglog=` filter that hides the channel `print` uses.
    Fix: test without the filter, prefix your lines (`MyMod[topic]`) and grep.
13. **The window never appears.** Cause: no `addToUIManager()`. A window re-created every frame flickers and leaks
    instead: create once, then `setVisible`.
14. **An `ISUI3DModel` panel stays empty.** Cause: it renders through the same model scripts as the world, and a
    bad model script fails silently. Fix: test the model in the world first.
15. **UI code errors on a dedicated server.** Cause: ISUI is client-only and a dedicated server has no renderer.
    Fix: keep UI in `client/` and guard shared code with `isClient()`.
16. **A wrapper around another mod's function does nothing.** Cause: it ran before that mod's `shared/` file
    defined the function. Fix: `require=` the host mod or wrap late (`OnGameStart`).
17. **Two content packs register the same records twice after a reload.** Cause: a non-idempotent bootstrap.
    Fix: a `Pack.installed` style guard (ALifeKnoxFractured).
18. **Removing a mod mid-save leaves its data behind.** Cause: ModData, spawned objects and registrations persist.
    Fix: document a clean-removal path.
19. Also on main: `%` in sandbox labels breaks the options screen (CDDA note gotcha 7), and an offline Lua 5.3+
    harness lacks `math.atan2` (CDDA note gotcha 19).

## Assets
- Icons: `Item_<Name>.png` in `media/textures/`. 3D: `.glb` for new work; import vanilla `.x` with the "DirectX X
  Importer" Blender extension or ZomboidAssetConverter (more in the creatures note).
- Audio: `.ogg` Vorbis or `.wav`, bound by `sound` script blocks (data note). The CDDA note has a full generated
  asset pipeline.

## Cost and time
Part of one research session (about half a day for this layer), on 2026-10-12.

## Open questions
- Whether `PZAPI.ModOptions` covers every widget vanilla panels use, and whether `client/PZAPI` loads on a
  dedicated server (probably not; keep it in `client/`).
- The load order of independent mods (no `require=` between them) beyond the preset line.
- The full `DebugType` channel list for `-debuglog=` on 42.21, and whether a mod can add its own debug window by
  subclassing `BaseDebugWindow`.
