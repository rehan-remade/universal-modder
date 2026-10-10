---
kind: game
title: Replace the dwarf map sprite with a custom 32x32 sprite (Steam, Linux)
game: Dwarf Fortress
games_also: []
game_version: v53.16 (steam 975370, native Linux build)
platform: linux
engine: native
route: data
tools:
- Aseprite CLI (Steam build)
- um sprite
- um backup
- grim
anti_cheat: none found by um scan
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-09'
links:
- https://dwarffortresswiki.org/index.php/Graphics_token
- https://dwarffortresswiki.org/index.php/Graphics
tags:
- raws
- creature-graphics
- layered-graphics
- sprites
- load-order
---
# Replace the dwarf map sprite with a custom 32x32 sprite (Steam, Linux)

> A user's own 64x64 Aseprite character was turned into a 32x32 tile and shown as every dwarf on the fortress
> map in Dwarf Fortress v53.16 (Steam, native Linux). The route is pure raws: a local mod with a TILE_PAGE and
> `CREATURE_GRAPHICS:DWARF` layer sets, plus removing the vanilla dwarf layer sets from the install. With
> `REQUIRES_ID_BEFORE_ME:vanilla_creatures_graphics` the mod's layer sets lost to vanilla's; replacement mods
> normally declare `[REQUIRES_ID_AFTER_ME:vanilla_creatures_graphics]` and load above vanilla graphics instead,
> which wasn't tried here and might make the install edit unnecessary. The install-edit method was verified in a
> freshly generated world by a screenshot of the embark, with an empty `errorlog.txt`.

## Setup
- Dwarf Fortress v53.16 Steam (app 975370), native Linux binary `dwarfort`; raws report
  `vanilla_creatures_graphics` NUMERIC_VERSION 5316. Arch-based Linux, Hyprland (Wayland), 2x scaled display.
- No loader needed (no DFHack used).
- Aseprite (Steam build) for export; `um sprite` for cutting/fitting/packing; `um backup` for snapshots.

## Route and why
- Route `data`: DF graphics are plain-text raws plus PNG tile pages, read at world load.
- `um scan` reports "unknown native engine" and suggests a proxy-DLL/native-hook route. Ignore that for DF:
  everything visual is in raws. (DFHack exists for runtime scripting but isn't needed for sprites.)
- What was verified here is a mod plus an edit to one vanilla file in the install (Build steps 4-5). The usual
  community route for replacing vanilla graphics is a plain mod that loads *before* vanilla graphics:
  `[REQUIRES_ID_AFTER_ME:vanilla_creatures_graphics]` in `info.txt`, and the mod placed above
  `vanilla_creatures_graphics` in the mod list. It wasn't tried here (Gotcha 2). If it works, the install edit
  goes, the mod survives "Verify integrity", and it can be shared on the Workshop.

## How the game works (what we had to learn)
- A mod is a folder with `info.txt` (`ID`, `NUMERIC_VERSION`, `EARLIEST_COMPATIBLE_*`, `NAME`, `AUTHOR`,
  `DESCRIPTION`, optional `REQUIRES_ID_BEFORE_ME` / `REQUIRES_ID_AFTER_ME`) and a `graphics/` folder with
  `tile_page_*.txt`, `graphics_*.txt` and `graphics/images/*.png`.
- `[OBJECT:TILE_PAGE]` → `[TILE_PAGE:<ID>]` `[FILE:images/x.png]` `[TILE_DIM:32:32]` `[PAGE_DIM_PIXELS:w:h]`.
  Map creature tiles are 32x32.
- Humanoid civ creatures (dwarf, human, elf, goblin, kobold) use **layered** graphics:
  `[CREATURE_GRAPHICS:DWARF]` with `[LAYER_SET:DEFAULT]`, `[LAYER_SET:CHILD:DEFAULT]`, `[LAYER_SET:BABY:DEFAULT]`,
  each holding `[LAYER_GROUP]` … `[LAYER:<name>:<tile page>:<x>:<y>]` … `[END_LAYER_GROUP]` with conditions
  (skin colour palettes, worn items, syndromes, hair). Simple animals use `[DEFAULT:<page>:x:y:AS_IS]` instead.
- Vanilla splits one creature's graphics across files that all open `[CREATURE_GRAPHICS:DWARF]`
  (`graphics_creatures_dwarf.txt` = map layers, `graphics_creatures_portrait_dwarf.txt` = `LAYER_SET:…:PORTRAIT`),
  so same-ID graphics blocks **merge**. Statues are a separate `STATUE_CREATURE_GRAPHICS` object.
- When two sources define the same layer set for the same creature, load order decides. Community practice for
  creature graphics is that the first loaded definition is the one that shows, so replacement mods load before
  the module they replace and declare it with `[REQUIRES_ID_AFTER_ME:<module>]` (the "Naga Graphical Update"
  Workshop mod has `[REQUIRES_ID_AFTER_ME:sm_cv_naga]`). Here the mod used
  `REQUIRES_ID_BEFORE_ME:vanilla_creatures_graphics`, which makes it load after vanilla, and vanilla won
  (Gotcha 2). The other order wasn't tried.
- Mods are fixed per world: chosen at "Create new world" and copied into `<user dir>/data/installed_mods/`.
  Later edits in `mods/` aren't propagated to that copy (Gotcha 4). Vanilla content is read from the install's
  `data/vanilla/` and is not copied, so edits there also apply to existing worlds after a restart.

## Build steps
Steps 4-5 edit the install. They are what was verified; the untried mod-only alternative is in Route and why.

1. Export frames: `aseprite -b in.aseprite --data out.json --format json-array --sheet sheet.png`.
2. `um sprite slice sheet.png frames --frame 64x64`, then for each frame
   `um sprite fit f.png out.png --size 32x32 --anchor bottom --no-upscale --hard-alpha`,
   then `um sprite sheet strip.png fit/*.png --cols N`.
3. Mod folder in **`~/.local/share/Bay 12 Games/Dwarf Fortress/mods/<mod>/`** (Linux user dir, not the install).
   Tile page with your strip; `[CREATURE_GRAPHICS:DWARF]` with `LAYER_SET:DEFAULT`, `CHILD:DEFAULT`,
   `BABY:DEFAULT`, each a single unconditional `[LAYER:BODY:<your page>:0:0]` in a layer group. Bump the mod's
   `NUMERIC_VERSION` on every iteration (Gotcha 4).
4. `um backup create "<install>/data/vanilla/vanilla_creatures_graphics/graphics" --name df-vanilla-creature-graphics`.
5. Reduce `<install>/data/vanilla/vanilla_creatures_graphics/graphics/graphics_creatures_dwarf.txt` to its
   header, `[OBJECT:GRAPHICS]`, `[CREATURE_GRAPHICS:DWARF]` and the two `SKELETON*` lines (keeps bone piles).
6. Restart DF fully, create a world with the mod active, embark.

## Verification
- Oracle: screenshot of the embark (grim on the DF window), zoomed on the units; `errorlog.txt` in the install dir.
- Two negative results first (Gotchas 1 and 2), then the custom sprite on all seven dwarves, errorlog empty.
- Not verified: adventure mode, corpses/ghosts/undead look, children/babies on screen, other worlds' saves.
  `um publish check <mod> --game "<install>/data"` passes (no game files in the mod).
- Not tried: the mod-only route with `[REQUIRES_ID_AFTER_ME:vanilla_creatures_graphics]` and the mod loaded above
  vanilla graphics (Gotcha 2).

## Gotchas
1. **Mod never appears / world uses vanilla only.** **Cause:** on Linux, DF reads local mods from
   `~/.local/share/Bay 12 Games/Dwarf Fortress/mods/`, created on first launch (beside `save/` and
   `data/installed_mods/`); `<install>/mods/` is ignored. **Fix:** put the mod in the user dir. Check:
   `data/installed_mods/` in the user dir is empty if the world loaded no mods. Exception: in portable mode
   (`prefs/portable.txt`, or the in-game portable setting) DF uses the install folder for `mods/`, `save/` and
   `data/installed_mods/` instead (DF wiki, File page).
2. **Mod loaded (listed in `installed_mods`) but dwarves still vanilla.** **Cause:** not established; most
   likely load order. With `REQUIRES_ID_BEFORE_ME:vanilla_creatures_graphics`, which loads the mod after vanilla,
   vanilla's layer sets won. For creature graphics the first loaded definition is the one that shows, so
   replacement mods normally declare `[REQUIRES_ID_AFTER_ME:vanilla_creatures_graphics]` and sit above vanilla
   graphics in the mod list; that wasn't tried here. A stale `data/installed_mods/` copy (Gotcha 4) could also
   have affected the first mod test. **Fix to try first (untested here):** restore the vanilla file, add
   `[REQUIRES_ID_AFTER_ME:vanilla_creatures_graphics]` to `info.txt`, bump `NUMERIC_VERSION`, and put the mod
   above `vanilla_creatures_graphics` when creating a new world. **Fix verified here:** strip the layer sets from
   the vanilla file (step 5), with a backup. A Steam update or "Verify integrity" restores the vanilla file; redo
   the edit afterwards. Another untried alternative: a mod with the same ID as `vanilla_creatures_graphics` and
   a higher NUMERIC_VERSION.
3. **DF doesn't pick up raw changes mid-session.** **Cause:** raws load at startup/world load. **Fix:** quit DF
   fully and relaunch before testing.
4. **Edits in `mods/<mod>/` don't show up in a world.** **Cause:** DF copies a mod into
   `data/installed_mods/` when a world is created and uses that copy; per the DF wiki's Modding page, later
   changes in `mods/` aren't propagated to it. **Fix:** bump the mod's `NUMERIC_VERSION` (or delete its copy in
   `data/installed_mods/`) on every iteration, then create a new world to test.
5. **`um publish check <mod> --game "<install>"` FAILs every file as "game file copied verbatim".**
   **Cause:** the mod was still inside the install tree, so it matched itself. **Fix:** use `--game "<install>/data"`
   or keep the mod outside the install. (That's a bug in `um publish check`: it shouldn't compare a mod with
   itself when the mod sits inside `--game`.)
6. **Driving DF on Wayland (Hyprland) failed.** `um win` is Windows-only. A uinput virtual mouse registered
   (`hyprctl devices`) but `hyprctl dispatch movecursor` never moved the cursor over fullscreen DF, and
   `wtype -k Down` didn't move the title menu even with DF focused. **Fix used:** the human clicked, the agent
   screenshotted with `grim -g` (halve the 2x capture to get logical coordinates). Untried: ydotool,
   un-fullscreening DF first.
7. **Per-frame trim with `um sprite fit` drops an idle bob.** Harmless here: the fortress map draws one static
   tile per creature, so animation frames are unused.

## Assets
The user's own pixel art (64x64 frames, character ~16x27 px), no generation. No scaling was needed to fit 32x32;
`--no-upscale` keeps it crisp. Expect no clothing, hair or held weapon layers on the replaced sprite.

## Cost and time
One session, about an hour wall-clock including two failed in-game tests. No API spend.

## Open questions
- Adventure mode: same `CREATURE_GRAPHICS` should apply to the adventurer and NPC dwarves; untested.
- Does a plain mod with `[REQUIRES_ID_AFTER_ME:vanilla_creatures_graphics]`, loaded above vanilla graphics in a
  new world (with a bumped `NUMERIC_VERSION`), replace the dwarf layer sets without editing the install? If so,
  Build steps 4-5 go and the mod can go on the Workshop.
- Does a same-ID, higher-version `vanilla_creatures_graphics` override work instead of editing vanilla?
