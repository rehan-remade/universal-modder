---
kind: game
title: "Binding of Terraria: Terraria bosses, weapons, minions and a hotbar inside Isaac Repentance+"
game: "The Binding of Isaac: Rebirth"
games_also: ["Terraria"]
game_version: "Repentance+ v1.9.7.17.J460 (Steam, Windows 11); Terraria 1.4.5.8 (Steam) as the asset source"
platform: windows
engine: native
route: loader-api
tools: ["Isaac Lua mod API (vanilla Repentance+, no REPENTOGON)", "xnbcli (LeonBlade)", "Pillow", "um win / um video"]
anti_cheat: "none"
status: working
agents: ["Claude Code (Fable 5.1)"]
humans: []
date: 2026-10-11
links: ["https://github.com/LeonBlade/xnbcli", "https://wofsauge.github.io/IsaacDocs/rep/"]
tags: [mashup, boss, weapons, familiars, hud, asset-conversion, xnb, anm2, stb, boss-rooms, completion-marks, repentance-plus, test-bridge]
---

# Binding of Terraria: Terraria bosses, weapons, minions and a hotbar inside Isaac Repentance+

> A vanilla Isaac Lua mod (no native hooks) that swaps every Isaac boss, story bosses included, for one of
> sixteen Terraria bosses at spawn time (custom themed boss rooms, versus screens and completion marks to
> match), puts 21 Terraria weapons and 12 summon staffs into the item pools with a 1-0 hotbar that replaces
> tears, and runs Terraria sprites and sounds converted from the player's own Terraria install. Verified in
> the real game by screenshots and a recorded clip: real boss rooms show the versus screen with the Terraria
> boss, the fight runs, the room clears, and Mom's and It Lives' rooms still hand out the Polaroid/Negative,
> trapdoor and beam of light.

## Setup
- Isaac: Repentance+ v1.9.7.17 (Steam 250900). Mods folder is `<install>/mods` (savedatapath.txt in the
  install folder says so; the Documents folder only holds options.ini and log.txt). Saves are in Steam
  userdata, backed up with `um backup create` first.
- `options.ini`: `EnableMods=1`, `EnableDebugConsole=1`, `Fullscreen=0` for stable screenshots.
- The mod folder is an NTFS junction (`mklink /J`) from the mods folder to the git repo's `mod/`.
- Terraria 1.4.5.8 for assets only (never launched). node 24 + `npm install github:LeonBlade/xnbcli`.
- `um win setup` for the gfxcapture ffmpeg; add `%LOCALAPPDATA%\universal-modder\ffmpeg\bin` to PATH for
  `um video`.

## Route and why
Mashup pattern 1 in `skills/mashup-mods/SKILL.md` (port the content into the host) + asset conversion.
Isaac's Lua API covers everything in the brief: custom NPCs with Lua AI (bosses), custom collectibles and item pools, custom familiars, a HUD
drawn in MC_POST_RENDER, keyboard input. Terraria as host was rejected because the user wanted Isaac's
characters and runs. No decompiling of either game was needed.

## How the game works (what we had to learn)
- **Entity types.** Custom NPCs use a type id vanilla doesn't use (790; vanilla types jump from 413 to 801,
  effects are 1000) with explicit variants; `Isaac.GetEntityTypeByName` / `GetEntityVariantByName` resolve them. Types >= 10
  are EntityNPC; type 3 = familiar, 1000 = effect.
- **Boss replacement.** `MC_PRE_ENTITY_SPAWN(type, variant, subtype, pos, vel, spawner, seed)` returning
  `{790, v, 0, seed}` replaces the vanilla boss before its init, for room-placed bosses and console `spawn`.
  Room clear, boss drop and trapdoor still work because the replacement entity has `boss="1"`. Larry Jr /
  Pin rooms place several segment entities, so extra spawns are turned into a poof effect.
- **Boss rooms** all live in `00.special rooms.stb` in Repentance (not the stage files); the game picks the
  boss from the stage's boss pool, then a boss room whose `subtype` equals that boss's BossType id. A mod's
  `content/rooms/00.special rooms.stb` with weight 40 rooms per boss id wins almost every floor. The STB1
  binary layout is Basement Renovator's `commonToSTBAB`; `tools/gen_rooms.py` writes it from Python.
- **Story bosses** can be replaced the same way (Mom 45.0, Mom's Heart 78.0/78.1, Isaac 102.0/1/2, Satan
  84.0, Lamb 273.0, Mega Satan 274.0, Hush 407, Delirium 412, Mother 912.0/912.10). The outcome of those
  rooms (Polaroid/Negative, trapdoor, beam of light) comes from Isaac's room-clear logic, not from the
  boss entity's death, so a replacement boss with `boss="1"` is enough. Their rooms place the vanilla
  entity several times (Mom x5), so dedupe with `Isaac.CountEntities`.
- **Completion marks** are 16x16 cells in `gfx/ui/completion_widget.png` and `completion_widget_pause.png`
  (384x384 on Repentance+; one row per difficulty, red at y=96 and dark at y=112: Polaroid 0, Negative
  16, Cross 32, Upside-down cross 48, Heart 64, Star 80, Mega Satan 96 and 112, Hush 128, Greed 144, then
  three newer marks). A plain PNG override in the mod's resources changes them, as long as it keeps that
  size and layout (gotcha 20).
- **Player look-alikes without touching the player anm2**: hide the body with `player.Color =
  Color(1,1,1,0,0,0,0)` each MC_POST_PLAYER_UPDATE (costumes go with it) and draw your own `Sprite` in
  MC_POST_PLAYER_RENDER at `Isaac.WorldToScreen(player.Position)`; nothing else in the game cares.
- **Character select sheet** `gfx/ui/main menu/charactermenu.png` (512x1024): 48x48 portrait cells
  (positions in characterportraits.anm2) and 80x32 name cells (charactermenu.anm2); a plain PNG override
  in `resources/` works on Repentance+ as long as the size stays 512x1024.
- **Versus screen** uses the room's original boss portrait; override `gfx/ui/boss/portrait_<id>_<name>.png`
  (192x192) and `bossname_<id>_<name>.png` (176x38) in the mod's resources. Rebirth-era bosses are numbered by
  entity type (20.0_monstro); newer ones by a different boss id (276.0_gurglings) or not at all
  (turdlings) - match by name. The exact file list is in `tools/ResourceExtractor/filelist.txt`.
- **anm2 format**: generated from Python (one spritesheet, one layer, frames crop a vertical strip). The
  `<Spritesheet Path>` is relative to the anm2's own folder.
- **Tears with custom sprites**: `player:FireTear(...)`, then `tear:GetSprite():Load(anm2, true)` and
  `FallingAcceleration < 0` so they never land; TearFlags give bounce/homing/pierce/boomerang for free.
- **Suppressing tears** while a weapon is selected: `player.FireDelay = max(FireDelay, 2)` each
  MC_POST_PEFFECT_UPDATE; `player:GetShootingInput()` gives the aim.
- **Familiars**: `player:CheckFamiliar(variant, count, RNG(), itemConfig)` in MC_EVALUATE_CACHE with
  CACHE_FAMILIARS; contact damage in MC_PRE_FAMILIAR_COLLISION; ranged minions `Isaac.Spawn` tears with
  the familiar as spawner (they count as player tears).
- **Hostile projectiles with custom sprites**: `npc:FireProjectiles` + MC_POST_PROJECTILE_INIT reading the
  spawner's data to `Sprite:Load` the Terraria sprite.
- **Item pools**: `MC_PRE_GET_COLLECTIBLE(poolType, decrease, seed)` returning a collectible id swaps the
  pull; a mod `content/itempools.xml` with `<Item Name=...>` also adds custom items to vanilla pools.
- **Terraria sprites**: XNB with LZX (flags 0x80); xnbcli decodes them. NPC sheets are vertical strips;
  frame count = Terraria's npcFrameCount (sheet height / frame count). Unrotated sprites face down, so
  rotation = atan2(dy, dx) - 90 degrees, exactly like Terraria's own code.
- **Isaac.ExecuteCommand** runs console commands from Lua (`restart`, `stage 1`, `debug 3`, `spawn 20`).
  Debug flags toggle.
- **Only the first MC_PRE_ENTITY_SPAWN callback that returns a value runs**; a second callback that only
  observes never fires once the first returned a replacement.
- **Input.IsButtonTriggered inside a 30 fps update callback misses short key presses**; poll
  `Input.IsButtonPressed` in MC_POST_RENDER (60 fps) and edge-detect yourself.

## Build steps
1. `um backup create` the Steam userdata save folder and the Documents options folder.
2. Set the options.ini flags; junction the repo's `mod/` into `<install>/mods/binding-of-terraria`.
3. `python tools/import_terraria.py` (xnbcli, then re-save PNGs with Pillow, fit 32x32 icons),
   `python tools/gen_anm2.py`, `python tools/gen_hud.py`, `python tools/gen_portraits.py`.
4. content/entities2.xml (bosses, minions, effects), items.xml, itempools.xml, sounds.xml; scripts in Lua.
5. Launch via Steam (`um win launch --steam 250900`), start a run, iterate with `luamod binding-of-terraria`
   (Lua) or a restart (XML/anm2, or `clearcache` for anm2 only).

## Verification
- Oracle: the game's `log.txt` (`Isaac.DebugString`) plus `um win shot` screenshots read at 0.5 scale, and a
  file bridge (`tools/bridge.py` <-> `scripts/bridge.lua`, see gotcha 8) that runs arbitrary Lua in the
  running game and returns results through the log. All testing used the vanilla launch, no --luadebug.
- Verified: every boss spawns, animates, moves and dies (Death animation, gibs); boss rooms on fresh floors
  (Larry Jr -> Eater of Worlds, Gurglings -> King Slime, Turdling untouched before the mapping was widened)
  show the versus screen with the override portrait and name, fight, clear the room and spawn the trapdoor;
  hotbar draws, keys 1-0 switch, swords swing in the aim direction, projectiles fly, falling stars land,
  minions chase and hit, imps shoot; a 92 s recorded take cut into a 38 s showcase.
- Verified later: custom boss rooms chosen on 11/14 sampled floors; every story boss spawns and fights;
  Mom's room and It Lives' room resolve normally after the Terraria boss dies.
- Not verified: controller input for the hotbar keys; co-op; Greed mode; the endings after Isaac, Satan,
  ???, Lamb, Mega Satan, Hush, Delirium and Mother (only Mom and It Lives were played through); The Beast
  and Dogma are untouched; balance (damage multipliers are guesses).

## Gotchas
1. **Boss spawns, health bar shows, nothing drawn, no log line.** Cause: the anm2's `<Spritesheet Path>`
   was written relative to `gfx/` ("terraria/x.png"); it is relative to the anm2 file's folder.
   `Sprite:IsLoaded()` still returns true. Fix: bare file name next to the anm2.
2. **Still invisible after the path fix.** Cause: PNGs written by xnbcli (pngjs) did not display. Fix:
   re-save every converted PNG with Pillow (`Image.open(p).convert("RGBA").save(p)`); the importer does it.
3. **`Sprite:HasAnimation` is nil.** Vanilla Repentance+ has no such method (REPENTOGON does). Just `Play`.
4. **Console `luamod` and `clearcache` close the console**; the rest of the typed batch goes into the game
   as WASD movement. Reopen the console after each.
5. **Console key on a UK keyboard is VK 0xDF (OEM_8)**, the key left of 1, not 0xC0. The first character
   typed after reopening sometimes becomes a stray space; send a Backspace first.
6. **`MC_EXECUTE_CMD` never fired for us on Repentance+ (v1.9.7.17).** Not a name collision: `bot`,
   `terraria` and `botx` typed in the console all just print the console's command list,
   `Isaac.ExecuteCommand("botx 1")` from Lua is silent too, and
   `Isaac.GetCallbacks(ModCallbacks.MC_EXECUTE_CMD)` shows the handler registered. IsaacDocs still says the
   callback is skipped only for the game's own commands. `lua <code>` works, and so does
   `Isaac.ExecuteCommand` for the game's own commands.
7. **Launching isaac-ng.exe directly with `--luadebug` blocks every later Steam launch.** Steam holds a
   hidden "launch with arguments?" dialog (`LaunchApp waiting for user response to ShowGameArgs` in
   Steam's console_log.txt). Fix: `steam.exe -shutdown`, start Steam again, launch through Steam.
8. **Automation without --luadebug.** `include("bridge.cmd")` re-reads the file from disk on every call, so
   a mod can poll `bridge/cmd.lua` every 10 render frames and run it when its `id` changes; results go to
   log.txt via `Isaac.DebugString`. Keep the last id in `_G` so a `luamod` reload does not re-run it, and
   ignore whatever the file holds at game start.
9. **Character select continues the previous run** (CONTINUE is preselected when a run exists). Use the
   console's `restart` for a fresh run; `stage N` regenerates a floor and the Level API
   (`level:GetRooms()`, `RoomType.ROOM_BOSS`, `game:StartRoomTransition(idx, Direction.NO_DIRECTION,
   RoomTransitionAnim.TELEPORT, player)`) teleports into its boss room. `goto s.boss` did nothing.
10. **`debug 3` toggles.** Calling it again per floor turned god mode off and the showcase player died.
11. **Spawning enemies into an already cleared boss room produced an instant death splash**; test spawns
    in a fresh room.
12. **Larry Jr rooms place several segment entities**; each became a full worm (4 worms). Dedupe in
    MC_PRE_ENTITY_SPAWN with `Isaac.CountEntities`.
13. **Isaac's shipped `tools/ResourceExtractor/ResourceExtractor.exe` seemed to write nothing.** Its first
    argument is the *input* (the game root; it appends `resources/packed` itself), so an output folder in
    that slot gives "No archive files found". Run it from its own folder with no arguments: it unpacks every
    `.a` of the install, Rep+ included (18.7k files, 1.2 GB), into `<game>/extracted_resources/resources*/`
    and logs each path to `ResourceExtractor_log.txt` next to it. That's where the vanilla anm2s and sheets
    for gotchas 20-21 come from. `filelist.txt` has the names.
14. **`um publish check --game` flags your own files** when the mod folder is a junction inside the game
    folder (it sees them as "game files copied verbatim"). Lint a `git archive` export instead.
15. **Hotbar vs boss bar.** Isaac's boss health bar sits at the bottom centre; draw the hotbar ~36 px up.
16. **Custom boss rooms in the stage files never get used.** `goto d.9000` found a test room in the mod's
    `01.basement.stb`, but boss rooms there were never picked. **Cause:** Repentance keeps every boss room
    in `00.special rooms.stb` (the console's `goto s.boss.<var>` searches stage id 0 and finds vanilla
    Basement boss rooms there). **Fix:** write them to `content/rooms/00.special rooms.stb`.
17. **Hotbar needed several presses.** `IsButtonTriggered` in MC_POST_PEFFECT_UPDATE (30 fps) misses
    presses shorter than a tick. **Fix:** edge-detect `IsButtonPressed` in MC_POST_RENDER.
18. **A sprite sheet that is a grid, not a strip** (Moon Lord's head, 573x804 = 3x3) shows three heads if
    cut as a vertical strip. Count transparent row gaps and columns before writing the anm2.
19. **Spawning a test boss in a room with pits** puts Isaac in a pit and respawns him at the door, so the
    screenshot shows no boss; test in plain rooms.
20. **Game hangs at file select, no log line, right after "Loading GameState".** Looks like a corrupt
    save; it is not. **Cause:** a 256x256 override of `gfx/ui/completion_widget.png` (Repentance's size
    and layout). Repentance+'s sheet is 384x384 with a new layout, 13 cells in one row (red/hard at
    y=96, dark at y=112, x=0..192: Polaroid, Negative, Cross, upside-down Cross, Heart, Star, two Mega
    Satan cells, Hush at 128, Greed at 144, three newer marks) and more paper variants, so its anm2
    crops past 256 px. Padding the 256 sheet to 512 stopped the hang but lost the character-select paper.
    **Fix:** start from the extracted Rep+ sheet (gotcha 13) and stamp at its coordinates, keeping
    384x384; same for `completion_widget_pause.png`. Bisect hangs by setting `EnableMods=0`, then
    removing overrides one at a time.
21. **Title-screen sheet override ignored.** `gfx/ui/main menu/titlemenu.png` (and `_2`, `_3`) in a mod's
    `resources/` changed nothing on Repentance+. **Cause:** Rep+ no longer keeps the logo in that sheet. Its
    `titlemenu.anm2` (extract it, gotcha 13) has `Logo` and `LogoShadow` layers that read
    `gfx/ui/main menu/logo.png` (480x320: logo in rows 0-159, its blurred shadow in rows 160-319);
    `titlemenu.png` only holds the background. This gotcha's earlier fix, an older (1.7.9b) `titlemenu.anm2`
    next to the PNG, only worked because that version still crops the logo from `titlemenu.png` at (0,272)
    480x111; don't use one. **Fix:** override `logo.png` alone, no anm2: keep "THE BINDING OF" from the
    vanilla top rows, paste your logo below, blur a grey copy into the bottom half. Verified on v1.9.7.17.
    The generator reads the vanilla `logo.png` from your own extraction (gotcha 13), so nothing from the
    game is committed or downloaded.

## Assets
All Terraria art and sound converted locally from the player's install by `tools/import_terraria.py`
(xnbcli unpack -> PNG/WAV, Pillow re-save, 32x32 nearest-neighbour icons from the item sprites, sizes.json
for the anm2 generator). Portraits are cut from the same sheets. The vanilla Isaac sheets the UI
generators start from (`logo.png`, `completion_widget.png`, `charactermenu.png`) are read from
`<game>/extracted_resources` (gotcha 13), not downloaded. The only committed art is the two hotbar
slot PNGs drawn with Pillow. No fal calls (the key had expired). The mod folder holds the converted
Terraria files and the UI sheets built from Isaac's own, so don't upload it to the Workshop as it is: share
the code and the importer, and let each player build from their own installs.

## Cost and time
One session, about 1 h 45 min wall clock from recon to showcase, most of it on the two invisible-sprite
causes (gotchas 1-2) and the console/Steam launch dance (gotchas 4-7).

## Open questions
- Versus-screen name plates use Impact; Isaac's hand-drawn font would fit better.
- Balance pass on damage/use times; Wall of Flesh for Mom and Moon Lord for Mom's Heart were not attempted
  because those fights have scripted room logic.
- Controller support for the hotbar (D-pad or bumpers).
