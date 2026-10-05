---
kind: game
title: 'A Build 41 Project Russia modpack: three small fix mods and a modded Linux dedicated server'
game: Project Zomboid
games_also: []
game_version: 'Build 41.78.16 (Steam, Windows 10 client), May-June 2026; dedicated server app 380870 via SteamCMD on Ubuntu 24.04; about 140 Workshop mods with the Project Russia map. The legacy branch is now 41.78.21 (not re-tested)'
platform: windows
engine: java
route: loader-api
tools: [Python 3.12 (catalog and Lua generator scripts), SteamCMD, systemd, mcrcon, the in-game Workshop uploader]
anti_cheat: 'none; a private server the player hosts for friends, every player runs the same mod list'
status: working
agents:
- Claude Code (Opus 4.7)
- Claude Code (Opus 4.8)
- Claude Code (Opus 5.5)
humans: [RedSuper]
date: '2026-10-04'
links: ['https://pzwiki.net/wiki/Mod.info', 'https://pzwiki.net/wiki/Procedural_distributions', 'https://github.com/FWolfe/Zomboid-Modding-Guide']
tags: [b41, mod-info, textures, loot, distributions, onpredistributionmerge, radio, item-scripts, dedicated-server, workshop-upload, spawn-regions]
---
# A Build 41 Project Russia modpack: three small fix mods and a modded Linux dedicated server

> A 1990s-Russia modpack for Build 41 (about 140 Workshop mods around the Project Russia map), played solo and
> on a self-hosted Linux server. Three small mods were written and published on the Workshop along the way: a
> Build 41 port of a texture mod that only worked on Build 42, a clothing-loot rebalance that hooks the
> distribution tables, and an item-script patch so Project Russia's Soviet radios can tune True Music Radio.
> All three work in game and on the server. The server notes cover `Map=`, spawn regions, checksums and why
> joining reloads Lua.
>
> **Age warning:** this is old data. The work was done in May–June 2026 on Build 41.78.16 by older models
> (Claude Opus 4.7, then 4.8), and only written up in October 2026. That session got several diagnoses wrong
> before finding the real cause; only the confirmed results are kept here, but re-verify anything you build on.

## Setup
- Client: Project Zomboid **41.78.16** from Steam on Windows 10. Mod lists managed with Star's Mod Manager (its
  presets live in `Zomboid\Lua\saved_modlists.txt`; the game's own enabled list is `Zomboid\mods\default.txt`).
- Server: Ubuntu 24.04 VPS (4 vCPU, 8 GB), Project Zomboid Dedicated Server **app 380870** installed with
  SteamCMD, run as a `pzserver` user under systemd (`start-server.sh -servername servertest`), Java heap set with
  `-Xmx6500m` in `ProjectZomboid64.json`, leaving about 1.5 GB for the OS and Workshop downloads. UDP 16261/16262 and the
  Steam query ports 8766/8767 open.
- Mods built here: "Hidden Backpack Straps b41 Fix" (texture port), "Equipment Distribution Setting for
  ProjectRussia by RedSuper" (loot rebalance), "Project Russian - True Music Radio Compatch" (radio ranges).

## Route and why
The game's own mod loader (`loader-api`): `mod.info` + `media/` folders, Lua in `media/lua/{shared,client,server}`,
item scripts in `media/scripts`. Each fix is a separate small mod loaded after what it fixes, so nobody else's
files are edited. Publishing went through the in-game Workshop uploader, the only B41 path that worked first time.

## How the game works (what we had to learn)
**B41 only reads `mod.info` at the mod-folder root.** Build 42 mods often ship `mod.info` only inside `42/` (or
`42.x/`), which B41 doesn't look into, so the mod is simply absent from the B41 mod list.

**B41 and B42 keep worn-bag textures in different places.** B41 resolves backpack textures flat in
`media/textures/<Name>.png` (vanilla has `BigHikingBagBlue.png`, `schoolbag.png` there). B42 nests them in
`media/textures/Clothes/Bag/`. A B42 texture-replacement mod loads under B41 but changes nothing until the files
are moved flat. Only names matching B41 items do anything (18 of the 64 textures in the mod we ported).

**B41's `mod.info` parser matches keys by substring.** It reads each line and tests "contains `id=`" before
"contains `url=`" (`ZomboidFileSystem.readModInfoAux`). A line like
`url=https://steamcommunity.com/sharedfiles/filedetails/?id=3450978326` contains `id=`, so it **replaces the
mod's id** with the rest of that line. The server then logs that the required mod isn't found on every boot and
the client mod list shows it as `[Not found]`. Plain `url=` lines without `?id=` are harmless.

**Loot tables are one shared global.** `ProceduralDistributions.list.<ListName>.items` is a flat array of
alternating item id and chance; every mod `table.insert`s into the same arrays (they append, they don't
overwrite). A handler on `Events.OnPreDistributionMerge` runs once at world start, after all mods have added
their entries and before the game merges them, which is the right moment to edit or remove entries. Our probe
counted 720 lists and 20,278 entries with this modlist. Some packs also add their own container lists (survivor
crates, pistol cases, army medkits).

**Loot is rolled when a container is first generated** and then saved with the world. Testing a distribution
change needs a new world and buildings nobody has entered.

**Small chances still show up.** With the list totals around 400, items at chance 0.002–0.003 still appeared in
about 2 of 4 wardrobes, so a chance behaves like a per-item, per-roll chance rather than a share of the list
total. Useful vanilla anchors: the Big Hiking Bag sits around 0.05 in civilian wardrobes and the katana at 0.001
in the hobbies list.

**Lua scope load timing.** `shared` and `client` files load at start-up; `server` files only when a world
starts. A test that launches to the main menu and quits can't tell you whether a `server/` file loads.

**True Music Radio needs an exact channel match.** It plays only when a radio's channel equals one of the
`TMRChannel1..5` sandbox values exactly; the server logs "Sending play to clients" when it does. Radio item
scripts set `MinChannel`/`MaxChannel`; Project Russia's AFN sub-mod redefines the radios with Soviet ranges (for
example 12–72 MHz), so they can't reach True Music's default 94 MHz, and vanilla FM radios (88–108) can't reach
low Soviet bands.

**A radio's range is stored on the radio, not read from the script.** The script's `MinChannel`/`MaxChannel` are
copied into the item's `DeviceData` when the radio is created and saved with it (we read this in the `Radio` /
`DeviceData` classes). Changing the script changes only radios created afterwards.

**Server and client must run identical mod files.** With `DoLuaChecksum=true`, a client whose copy of a mod
file differs from the server's is kicked on join; this happened for a `.lua` file and for an item-script `.txt`.

**Joining a server reloads Lua when the mod sets differ.** The client loads Lua from its own enabled list
(`mods\default.txt`) at launch; the server's `Mods=` decides the session. If they differ in content or order,
the client reloads Lua on join and again on leaving. The server doesn't change the client's list (its timestamp
stayed put).

**`Map=` on a dedicated server is the list of map folders to load.** Single player loads all enabled map mods;
the server loads only what `Map=` names, by **folder name** (`Project Russia` with its space, `DolgoprudnyPR`).
`Zomboid/Server/<name>_spawnregions.lua` is read at server start, so spawn edits need a restart. City names in
the spawn screen come from the map's translation files and can differ from folder names
(`Bolotnoe` shows as "Sloboda").

## Build steps
**Porting a B42-only texture mod to B41:** copy `mod.info`, `poster.png`, `icon.png` from `42/` to the mod
root; move bag textures from `media/textures/Clothes/Bag/` (and `Clothes/Hat/`) to flat `media/textures/`;
restart the game fully and test in a new save. Ask the original author before publishing a port, and credit
them in the description.

**Workshop upload (B41):** stage `Zomboid\Workshop\<Folder>\workshop.txt` + `preview.png` +
`Contents\mods\<ModFolder>\...`; main menu → Workshop → Create → pick the folder → Test → Upload. Steam writes
the new `id=` into `workshop.txt`; uploading again from that folder updates the same item.

**Distribution rebalance:** one table mapping item ids to per-list weights, one handler on
`Events.OnPreDistributionMerge` that walks every list, rewrites chances for mapped items and removes the id and
its chance (two array slots) for items that should never spawn. Only touch lists you have classified; leave
other packs' custom containers alone. The files live in `media/lua/shared/` so the same code runs in single
player and on the server.

**Radio compatibility patch:** an item-script file in a mod loaded after `projectrussia` and `projectrussiaafn`
that redefines the five Soviet radios with `MaxChannel = 108000` (min unchanged). The server log shows the
override order as `mod "X" overrides media/scripts/items_radio.txt`; the last one wins.

**Server:** both `Mods=` (mod ids) and `WorkshopItems=` (workshop ids); `Map=` with every map folder from the map
author's Steam page plus `Muldraugh, KY` last; set `RCONPassword` and send `save` (then `quit`) through an RCON
client such as `mcrcon` before restarting, because the systemd unit had no stdin to type console commands into.

## Verification
- Texture port: the mod appeared after the `mod.info` move, and bags showed without straps after the texture
  move (player's screenshots, new save). Later confirmed on the server after the `url=` fix.
- `mod.info` bug: the server's "required mod not found" warning, present on every boot, was gone on the next
  start after removing the `url=` line; the Workshop item was updated the same way.
- Loot: a probe inside the handler logged 619 mapped items, 720 lists, 3,030 entries changed and 0 remaining
  entries for removed items; the player checked closets in fresh worlds over several rounds of tuning.
- Radio: the server log shows the patch loading after both Project Russia mods; the player confirmed True Music
  plays on radios that can reach the channel. The fresh-radio test for already-saved radios wasn't reported back.
- `Map=`: after listing every map folder (and restoring the spawn region, then restarting) the player had no
  further reports about that city; not confirmed explicitly.
- Not verified: whether `print()` from a mod is really absent from `console.txt` (it never showed up in our runs);
  how `chance` exactly maps to spawn probability; what happens to sandbox values below a client's local `min`.

## Gotchas
1. **A Workshop mod tagged "Build 41, Build 42" doesn't appear in the B41 mod list.** Cause: `mod.info` only in
   `42/`. Fix: copy it (with poster and icon) to the mod-folder root.
2. **The ported texture mod is listed and enabled but changes nothing.** Cause: B42 texture paths
   (`textures/Clothes/Bag/`). Fix: move the files flat into `media/textures/`.
3. **"Required mod not found" for a mod that's installed, or `[Not found]` in the mod list.** Cause: a `url=`
   line containing `?id=` overwrote the mod id. Fix: drop `url=` or leave `?id=` out of it.
4. **A test `server/` Lua file "never loads".** Cause: the test quit at the main menu; `server/` only loads when a
   world starts. We first concluded that local mods can't load `server/` Lua and moved everything to `shared/`;
   that works, but the conclusion was probably wrong.
5. **The game hung on a black screen at start-up** after we added `error()` calls at file scope for diagnosis;
   it started again once they were gone. Fix: keep diagnostics inside the event handler. A deliberate syntax error
   is a safer "is this file loaded?" test: it shows up as a Kahlua parse error in `console.txt`.
6. **Tuned loot still looks wrong in a world you've been testing.** Cause: those containers were already rolled.
   Fix: new world, unvisited buildings.
7. **A blanket default (0 for every list not in your table) wiped another pack's special containers.** Fix:
   apply a default only to items you want removed everywhere; leave unknown lists alone.
8. **The radio patch "didn't work": an old car radio still stops at 78 MHz.** Cause: the range was saved on that
   radio when it was created. Fix: test with a newly spawned radio.
9. **Kicked on join right after a quick fix on the server.** Cause: a mod file edited on the server only; the
   checksum no longer matched the client's Workshop copy. Fix: never hot-edit Workshop files on the server; ship
   an update to the Workshop item.
10. **True Music stays silent after moving its channels to 65.2 MHz.** Cause: the channel values had to be
    unlocked in the server's copy of the mod's `sandbox-options.txt` (`min = 88000`); clients still had the
    original. Fix we kept: leave True Music on its default FM channels and widen the Soviet radios' range
    instead (gotcha 8 applies).
11. **`Object tried to call nil in mapLoadingRadios` every minute or two.** Cause: Project Russia places radio
    sprites as map decoration that aren't radio objects; True Music's map-load callback fires for them. Old logs
    showed it months before the server existed. Log noise, not why radios were silent.
12. **A city's spawn preview is blank on the server but fine in single player.** Cause: `Map=` named only the
    parent map, and with the wrong folder name (`ProjectRussia` instead of `Project Russia`). Fix: list every map
    folder.
13. **A spawn region edit doesn't show up.** Cause: spawn regions are read at server start. Fix: restart.
14. **Lua reloads every time you join the server.** Cause: the client's enabled list differs from `Mods=`. Fix:
    make the client's list match the server's order exactly, or ignore it; nothing is overwritten.

## Assets
Only the original mod's textures, moved (credited, linked to the original). No new art.

## Cost and time
Many sessions between 2026-05-24 and 2026-06-07, most of it on the loot rebalance (tier design with the player)
and the radio diagnosis. Written up 2026-10-04 from the session transcripts and the project's notes.

## Open questions
- Does a chance of exactly 0 stop an item from spawning, or only removal? We removed entries and never isolated
  that.
- What does a client do with a sandbox value below its local `sandbox-options.txt` minimum? Reading
  `IntegerConfigOption` suggests it rejects it and keeps the default, but we didn't test it.
