# The Binding of Isaac: Rebirth (Afterbirth+, Repentance, Repentance+)

**Identify.** `isaac-ng.exe` (32-bit native), `resources/packed/*.a`, a `mods/` folder in the install (since
1.9.7.6; `savedatapath.txt` in the install names it) and `tools/` with `ResourceExtractor`,
`IsaacAnimationEditor`, `IsaacItemPoolEditor`, `RoomEditor`, `ModUploader` and `LuaDocs` (an offline Doxygen
dump of the API). `options.ini` and `log.txt` live in `Documents\My Games\Binding of Isaac <newest DLC>\`
(`Repentance+` today); unlocks in Steam `userdata\<id>\250900\remote\`. No anti-cheat. Repentance+ added
online co-op, and the official FAQ says all mods must be disabled and the game restarted to play online, so
everything here is for single player and local co-op.

**Route: a Lua mod on the vanilla API, no decompiling.** Custom entities with Lua AI, items and pools,
familiars, HUD rendering, input, save data and console commands are all covered. Reach for REPENTOGON only
for what vanilla hides (XML data at runtime, ImGui, extra callbacks, unlocks for modded content).
- Reference: IsaacDocs, `https://wofsauge.github.io/IsaacDocs/rep/` (classes, 74 callbacks, every content XML,
  the console, launch options, troubleshooting). Tutorials: Isaac Blueprints, `https://isaacblueprints.com/`
  (crash course, kept current for Repentance+). Community: the Modding of Isaac Discord, r/themoddingofisaac.
- Worked example in the knowledge base: `games/the-binding-of-isaac-rebirth/` (Terraria bosses, items and a
  HUD inside Isaac, with 21 gotchas and a file bridge for testing). Facts below marked *(verified)* were
  checked in game on Repentance+ v1.9.7.17 while writing this page.

## Mod anatomy
- `mods/<folder>/` with `metadata.xml`: `<name>`, `<directory>` (= the folder name; also names the save-data
  folder), `<description>`, `<version>`, `<visibility>`, and `<id>` once uploaded. Launching with an empty
  folder generates the file *(verified: name, directory, description, version 1.0, visibility, no id)*.
  Mods load alphabetically by folder name, which is why library mods use folders like `!!mod config menu`.
  Workshop subscriptions install as `mods/<directory>_<workshop id>` after staging in
  `steamapps/workshop/content/250900/<id>`.
- `main.lua`: `local mod = RegisterMod("Name", 1)`, then `mod:AddCallback(ModCallbacks.MC_X, fn, filter)`
  where the optional filter is an entity type, variant, item or card id, and `mod:AddPriorityCallback(cb,
  CallbackPriority.EARLY, fn)` to run before other mods. `main.lua` runs even with mods disabled in the menu.
  `REPENTANCE_PLUS` is a global constant since 1.9.7.8; `REPENTANCE` likewise for Repentance.
- `content/*.xml` adds data: `entities2.xml`, `items.xml`, `itempools.xml`, `sounds.xml`, `music.xml`,
  `players.xml`, `challenges.xml`, `costumes2.xml`, `bossportraits.xml`, `rooms/*.stb` and about twenty
  more (IsaacDocs' XML index lists them all). `content/bosspools.xml` does nothing in a mod: a custom boss
  joins vanilla pools through StageAPI, or by replacing a vanilla boss at spawn (below).
- `resources/` mirrors the vanilla tree and overrides any file by path (PNG, anm2, fonts, music). The game's
  own `resources-dlc3/` held Repentance's files and beat `resources/`; Repentance+ merged them into
  `resources/`. A mod's `resources-dlc3/` is still read on Repentance+ *(verified: a sheet present only there
  was used)*, so a mod written for Repentance keeps working; new mods need only `resources/`.
- `require("x")` caches and resolves across every loaded mod, so two mods with `lib.lua` collide: keep files
  under a folder named like the mod. `include("x")` never caches and only sees your own mod; it is what
  `luamod` reloads.
- Persistence: `mod:SaveData(str)`, `LoadData()`, `HasData()`, `RemoveData()` write
  `<game>/data/<directory>/save1-3.dat` per save slot *(verified: plain text, written immediately)*, the only
  writable files without `--luadebug`, and only during a run. Save in `MC_PRE_GAME_EXIT`; load in
  `MC_POST_GAME_STARTED(isContinued)`, which also tells new run from continue (the docs warn that
  `MC_POST_PLAYER_INIT` sees incomplete data on a continued run). `pcall` the JSON decode (`require("json")`)
  and keep Vector, Color and RNG userdata out of it. `entity:GetData()` is a plain table that dies with the
  entity. Mods block achievements until Mom has been killed once on that save file (challenges and dailies
  don't count); no official source says the kill must happen with mods off.
- Vanilla assets to read or copy sizes from: run `tools/ResourceExtractor/ResourceExtractor.exe` from its
  own folder with no arguments; it unpacks every archive to `<game>/extracted_resources/` (the first
  argument is the *input* path; an output folder there gives "No archive files found"). `filelist.txt` has
  the names. Never ship those files: a UI override is your own PNG at the vanilla sheet's size.

## Versions and extensions
- Afterbirth+ → Repentance changed the API in places (IsaacDocs marks them); there is no separate
  Afterbirth+ edition of the docs.
- Repentance+ (v1.9.7.4, November 2024; v1.9.7.17 since April 2026) broke many Workshop mods at launch.
  1.9.7.10 renumbered the `ButtonAction` enum "to match the code" (hard-coded ints break) and fixed modded
  curses, trinkets and `QueueItem`; the API gained `Entity:KillWithSource`, `ItemPool:GetCollectible(...,
  backupPool)`, new fonts and `FontRenderSettings`. Isaac Blueprints keeps a "Repentance+ changes" page.
- REPENTOGON (`https://repentogon.com/`, GPL-2.0) is the native script extender: Lua 5.4, 800+ extra
  functions, ImGui console and menus, `XMLData`, unlocks for modded content. Its launcher is kept outside
  the game folder, copies the game, downloads a patch keyed by the vanilla exe's hash and runs the patched
  copy (Steam launch option `"<path>\REPENTOGONLauncher.exe" --isaac=%command%`); after a Steam update,
  update the launcher first or it reports the exe as incompatible. Patches exist up to 1.9.7.17. A snippet
  that calls `Sprite:HasAnimation` or `XMLData` assumes it; vanilla lacks them. Ask before installing it.
- Library mods a new mod usually leans on, each detected by its global and guarded with `if X then`:
  External Item Descriptions (`EID:addCollectible(id, text, name)`; `__eidItemDescriptions[id]` works
  regardless of load order), Mod Config Menu Pure (`ModConfigMenu`; never `require` it), StageAPI
  (`StageAPI.Loaded`; custom stages and boss pools; queue work in `StageAPI.ToCall` if you load first).
  There is no dependency field in `metadata.xml`. IsaacScript (`https://isaacscript.github.io/`) writes mods
  in TypeScript with a save-data manager and typed API, Repentance+ aware, REPENTOGON optional.

## Facts to know
- Entities are addressed as `type.variant.subtype` everywhere (console, XML, spawn calls). Custom NPCs
  take an id vanilla doesn't use (vanilla types run to 413, then 801-970; the cap is 4095; 3 = familiar,
  1000 = effect) and are renumbered when mods overlap, so resolve them at runtime with
  `Isaac.GetEntityTypeByName` / `GetEntityVariantByName`. `boss="1"` in `entities2.xml` marks a boss; in
  practice that is enough for room clear, the boss drop and the trapdoor to work for a custom boss.
- `Isaac.Spawn(type, variant, subtype, pos, vel, spawner)` and `Game():Spawn(type, variant, pos, vel,
  spawner, subtype, seed)` take different argument orders; `Isaac.Spawn` can roll seed 0 and crash, so
  prefer `Game():Spawn` with a seed from `GetDropRNG()` or similar. `RNG():SetSeed(seed, 35)` needs a
  non-zero seed.
- Rates *(verified)*: `MC_POST_UPDATE` and `MC_POST_PEFFECT_UPDATE` 30/s, `MC_POST_RENDER` and
  `MC_POST_PLAYER_UPDATE` 60/s; updates pause with the game. `Isaac.GetFrameCount` is the 60/s counter and
  runs in menus, `Game():GetFrameCount` the 30/s one. `Isaac.GetPlayer()` is nil in the main menu.
- `MC_PRE_ENTITY_SPAWN(type, variant, subtype, pos, vel, spawner, seed)` returning `{type, variant,
  subtype, seed}` replaces anything before init, room-placed bosses included. The first callback to return
  a value wins and the chain stops: later callbacks in the same mod, in other mods, and at lower priority
  never run, and the replacement is not re-offered to them *(verified; IsaacDocs says the last return wins,
  which did not match)*. Use `AddPriorityCallback` to get ahead. Returning type 0, a non-table, or swapping
  across entity classes (pickup to effect) crashes. `MC_PRE_GET_COLLECTIBLE` must return a collectible id
  or nil.
- Boss rooms: a mod's `content/rooms/00.special rooms.stb` with rooms whose subtype is the boss id gets
  picked; the same rooms in `01.basement.stb` were never used (observed on 1.9.7.17; the console's
  `goto x.boss.<n>` shows stage files can hold boss rooms, so this is about selection). Write STB with
  Basement Renovator, or from Python using its STB1 layout.
- `Sprite:Load(path, true)` takes paths from the resources root (`gfx/...`) *(verified)*. A missing file
  still gives `IsLoaded()` true; the reliable check is `GetDefaultAnimationName() ~= ""` *(verified)*.
  After `ReplaceSpritesheet` call `LoadGraphics()`.
- anm2 is XML (ElementTree is enough): layers in ascending id order, every layer needs a
  `<LayerAnimation>`, paths are case-sensitive in practice. `<Spritesheet Path>` is relative to the anm2's
  own folder: vanilla `gfx/ui/main menu/titlemenu.anm2` names `TitleMenu.png` beside itself *(verified in
  the extracted files)*. IsaacDocs says "starting from gfx/", which only agrees for anm2 files in `gfx/`.
- Invisible entity: wrong sheet path, or a PNG the game won't decode (pngjs output, odd bit depth; a black
  or red square is the bit-depth case). Re-save PNGs with Pillow as 32-bit RGBA.
- A UI sheet override of the wrong size hangs the game at file select with no log line (Repentance+ moved
  and resized several: the title logo is its own `logo.png`, the completion-mark sheets are 384x384).
  Extract the vanilla sheet and keep its size; bisect hangs with `EnableMods=0`.
- `MC_EXECUTE_CMD(cmd, args)` is the documented way to add console commands (skips built-ins; any non-nil
  return crashes). In the session behind this page (1.9.7.17) it never fired for a custom name, typed or via
  `Isaac.ExecuteCommand`, although the handler was registered *(verified)*; the cause wasn't found. Test it
  once before relying on it, and fall back to `lua <code>` or a command file if it stays silent.
- Input: `Input.IsButtonTriggered` is consumed by the first call per update and missed automated short
  presses in a 30/s callback; edge-detect `Input.IsButtonPressed` in `MC_POST_RENDER` when it matters.
- `Isaac.DebugString` truncates at about 10 KB; `log.txt` is wiped each launch and shows nothing on a
  crash, so print-bisect. Fully restart after enabling or disabling a mod.

## Tools
- Basement Renovator (`github.com/Basement-Renovator/basement-renovator`, Python): rooms and `.stb`, with a
  Repentance+ compatibility mode; launch it with your mod enabled or its entities are missing. The install's
  `tools/RoomEditor` is the older official editor.
- `tools/IsaacAnimationEditor` edits anm2 (its FPS and attribute panels are preview-only); Anm2ed
  (`github.com/ShweetsStuff/anm2ed`) is the community alternative. `tools/IsaacItemPoolEditor` for pools.
- `tools/ModUploader/ModUploader.exe`: point it at `metadata.xml`, set description (BBCode), tags, visibility
  and a thumbnail under 1 MB; the first upload writes `<id>` into the file, every update needs a higher
  `<version>`. IsaacScript's GitHub Action can do updates from CI once the id exists.

## Console and iteration
`EnableDebugConsole=1` in `options.ini`. The key depends on the layout: IsaacDocs lists `` ` `` or `~` for US
and `'` or `@` for UK; on a UK keyboard VK 0xDF (the key left of 1) also opened it *(verified)*. `luamod
<folder>` re-runs the mod's Lua and `clearcache` reloads sprites; both close the console, so reopen it
before typing more or the text becomes WASD movement. XML changes need a restart. Useful: `lua <code>`,
`restart [character]`, `stage 1-13[a-d]`, `goto s.boss.<variant>` / `d.<n>` / `x.<room type>.<variant>`,
`spawn t.v.s`, `giveitem c15`, `reseed`, `debug 3` (god mode; the flags toggle), `testbosspool`, `copy`
(last three commands to the clipboard). `Isaac.ExecuteCommand` runs the same from Lua. `--luadebug` unlocks
`io`, `os`, `debug` and unsandboxed `require` for every mod, which IsaacDocs warns can compromise the
machine; prefer a stock launch.

## Automation
Launch through Steam (`um win launch --steam 250900`); on one machine, starting `isaac-ng.exe --luadebug`
directly made Steam hold a "launch with arguments?" dialog that wedged every later launch until
`steam.exe -shutdown`. Without `io`, a complete file bridge still works: `include()` re-reads its file from
disk on every call, so a mod that includes a command file every few render frames and logs the result
through `Isaac.DebugString` lets an agent run Lua in the live game and read answers from `log.txt`
*(verified; every fact marked verified on this page came through it)*. Windowed mode (`Fullscreen=0`) for
`um win shot`. The main menu defaults to Continue when a run exists; spawn test bosses in rooms without pits
or Isaac falls in and respawns at the door.
