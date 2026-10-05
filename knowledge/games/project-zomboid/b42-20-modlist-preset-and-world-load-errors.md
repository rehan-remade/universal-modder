---
kind: game
title: 'A 130-mod Build 42.20 modlist: the preset file, version folders and "World loading could not proceed"'
game: Project Zomboid
games_also: []
game_version: 'Build 42.20.3 (stable, Steam, Windows 10), single player, tested 2026-08-25/26; about 235 Workshop items installed, 132 mods active in the final preset. Not re-tested on 42.20.4 or 42.21'
platform: windows
engine: java
route: loader-api
tools: [Python 3.12 (own scripts for mod.info scanning, preset writing and log triage), Steam Web API, grep]
anti_cheat: 'none (single player)'
status: working
agents:
- Claude Code (Opus 5)
- Claude Code (Opus 5.5)
humans: [RedSuper]
date: '2026-10-04'
links: ['https://pzwiki.net/wiki/Mod.info', 'https://pzwiki.net/wiki/Mod_structure']
tags: [modlist, load-order, presets, mod-info, version-folders, workshop, crash-triage, world-dictionary, vehicles, b42]
---
# A 130-mod Build 42.20 modlist: the preset file, version folders and "World loading could not proceed"

> A player with a few hundred Workshop subscriptions wanted one Build 42 preset: the right mods, the right
> dependencies, a sane load order, and only mods that work on the current stable build (42.20.3). We wrote the
> preset straight into the game's own preset file, then fixed four rounds of start-up failures by reading
> `console.txt`. The game now starts a new world with 132 mods. Most of the time went into traps the mod menu
> doesn't show: a preset format that silently fails, one-folder-per-version loading, a dependency library that
> pruned templates other mods still used, and a recipe calling for a fluid that doesn't exist.
>
> **Age warning:** the work was done in August 2026 on 42.20.3 by an older model (Claude Opus 5) and written up
> in October 2026, after 42.21 went stable. The engine behaviour is likely to still hold; the per-mod findings
> (which uploads break, which forks work) date fast. Re-check them against the build you run.

## Setup
- Project Zomboid **42.20.3** from Steam (`version.txt` in the user's `Zomboid` folder shows the build), work done
  2026-08-25/26. Build 42 went stable as 42.20.0 on 2026-07-29, with hotfixes 42.20.1/.2 (2026-08-05), 42.20.3
  (2026-08-17) and 42.20.4 (2026-08-26, right after this work); **42.21 went stable on 2026-09-28** and is newer
  than anything here. Dates from the Steam news feed (`ISteamNews/GetNewsForApp`, app 108600).
- Workshop content in `<Steam library>\steamapps\workshop\content\108600\<workshop id>\mods\<mod folder>\`.
- User data in `C:\Users\<user>\Zomboid\`: `console.txt` (latest run), `Logs\` (older runs),
  `Lua\pz_modlist_settings.cfg` (presets), `Saves\`.
- Nothing in the game install was modified. All work was reading files, writing one line of the preset file, and
  reading logs.

## Route and why
The game's own mod loader (route `loader-api`): we only choose which Workshop mods are active and in what order.
A preset in the vanilla Mods screen is the unit the player loads, so we generated that preset rather than editing
per-save `mods.txt` files. We didn't use a mod-manager mod: the vanilla B42 screen already has presets.

## How the game works (what we had to learn)
**The preset file belongs to the game, not to a mod.** `Lua\pz_modlist_settings.cfg` is read and written by the
vanilla Lua in `media/lua/client/OptionScreens/ModSelector/` (`ModSelectorModel.lua` loads and saves it,
`ModListPresets.lua` applies a preset). Format: one line per preset, `Name:modid;modid;...;`, and the first line
is the favourites line `!fav!:`. The whole file is rewritten from memory when the game saves it.

**Applying a preset matches entries against mod ids exactly.** The apply code walks every installed mod, enables
it if its `mod.info` id is a key in the preset, and lists every preset key that matched nothing in a
"MISSING MODS" window. So each entry must be the bare `id=` value. The presets already on this install had a
backslash before every id (`\damnlib;\tsarslib;...`); copied in that form, every entry came up missing.

**The load order followed the preset line.** We wrote the line in load order and the game loaded the mods in
exactly that order (checked in `console.txt`). The apply step also inserts each mod's `require=` entries ahead of
the mod.

**Mods ship one folder per game version, and only one is used.** A B42 mod folder can hold `42.0/`, `42.13/`,
`42.17/`, `42.20/` ... next to `common/` (and sometimes a legacy root `mod.info` + `media/` for Build 41). The
game uses `common/` plus a single numbered folder; everything we saw fits "the newest folder not above the
running build". Files that exist only in an older numbered folder are **not** merged in. Each numbered folder has
its own `mod.info`, so the id, `require=` and `versionMin` can differ per version: More Traits' root `mod.info`
says `id=ToadTraits`, its `42.x` ones say `id=1299328280/ToadTraits` (workshop id prefixed), and its
`42.17`/`42.20` ones add `require=UnifiedCarryWeightFramework`.

**`require=` values can carry a leading backslash** (`require=\tsarslib,\KillCount`). Strip it before comparing
ids.

**Two installed items can declare the same `id=`.** Typical case: a B41-only upload and its separate B42 re-upload
(Tsar's Common Library, Moodle Framework, True Music, Auto Mechanics ...). `ModSelectorModel.reloadMods` builds its
table keyed by id and skips an id it has already seen, so the Mods screen shows one entry per id. We did not prove
which copy wins.

**`console.txt` lists the active mods.** Each active mod logs `LOG  : Mod  f:0> loading <id>`; inactive installed
mods don't appear. Diffing those lines against the intended preset is the fastest way to see what actually ran.

**Unresolved vehicle parts and recipe fluids are fatal; Lua errors are not.** When these scripts fail to resolve,
world creation aborts after the map loads with `zombie.world.WorldDictionaryException: World loading could not proceed,
there are script load errors. (Actual error may be printed earlier in log)` and the game shows
"Sorry, an unexpected error occurred". Two kinds we hit:
- `ERROR: template "X" not found` / `ERROR: part "X" not found` while vehicle scripts load;
- `ScriptManager.PostWorldDictionaryInit> Exception thrown ... Fluid not found: Alcohol. line: fluid 0.1 [Alcohol]`
  from a craft recipe. 42.20 has no fluid named `Alcohol` (the closest is `RubbingAlcohol`); the vanilla fluid
  list is in `media/scripts/generated/fluids*.txt`.

A recipe input that names a missing **item** (`Invalid input. line: item 1 [Base.MRE] mode:destroy`) is only
logged and the world still loads. Lua exceptions (`Lua((MOD:...)).fn> Exception thrown`) and the many
`require("...") failed` warnings don't stop loading either.

**that DAMN Library moved its templates.** Its template counts per folder: `42.0` 412, `42.13` 349, `42.17` 349,
`42.20` 19, `common/` 336. The per-vehicle profession templates (`DAMN86fordE150<company>`, `DAMN83amgeneralM923`)
exist only in `42.0`. Vehicle mods that still ship only a `42.0` folder and reference them now fail. Other vehicle
mods reference parts that are defined nowhere, in any of their own folders or any damnlib folder
(`BR89SpareTiresPD`, `JP82SpareTireRear`, `BUSHTires`, `P19ABigTrunkCompartment2`); presumably lost when files
were split into version folders.

## Build steps
1. **Index what's installed.** Walk `workshop/content/108600/*/mods/*/` and record every `mod.info`: the root one
   and one per numbered or `common` folder (names are `42`, `42.0`, `42.13`, `42.20`, not just `42`). Keep
   `id`, `name`, `require` (backslash stripped), `versionMin`, and the folder list.
2. **Check each mod against the build** with Steam data (build tags, last update vs. 2026-07-29) and the folders
   it ships; see the technique note "Checking Steam Workshop mods against a game version". Prefer a fork whose
   title and folders say 42.20 over a stale original.
3. **Resolve dependencies** from the `require=` of the folder the game will actually use, recursively.
4. **Order** libraries and frameworks first, then body/character mods, clothing, compatibility patches, content,
   QoL, visuals, diagnostics last; patches after what they patch.
5. **Write the preset with the game closed.** One line `Name:id;id;...;` with bare ids, appended to
   `pz_modlist_settings.cfg`, keeping the other lines. Back the file up first.
6. **In game:** Mods screen, pick the preset, check the active count, start a **new** world.
7. **On a crash:** open `console.txt`, find `WorldDictionaryException`, then search upward for
   `ERROR: template|part ... not found` and `PostWorldDictionaryInit`. Grep the Workshop folder for the missing
   name to find who references it and whether anyone defines it, then disable the referencing mod or swap it for
   a maintained fork.

## Verification
- Oracle: starting a new world and reading `console.txt` afterwards. Final run: 133 `loading` lines matching the
  preset, no `WorldDictionaryException`, world loads and plays.
- The only Lua exception left was Braven's Achievements throwing `Object tried to call nil in everyFiveMinutes`
  on a timer; it was then disabled (132 mods).
- Each fix was confirmed by the next run's log: the template errors went 95 → 0 after disabling the referencing
  vehicle mods; with the original Common Sense replaced by its 42.20 fork, the world loaded.
- Not verified: which copy loads when two installed items share an id; how the Save button in the Mods screen
  writes entries (we wrote the line ourselves); long-term play with every mod.

## Gotchas
1. **Every mod in the preset shows up in "MISSING MODS", each with a leading `\`.** Cause: entries written as
   `\modid`; the apply code compares raw entries to mod ids. Fix: write bare ids. We copied the backslash form
   from presets already in the file, so don't trust existing lines as a format reference.
2. **You edit the preset, but the game loads the old list.** Cause: the game keeps the presets in memory and
   rewrites the whole file on exit, so an edit made while it runs is lost. Seen as 10 removed mods coming back.
   Fix: edit only with the game fully closed (check for the `ProjectZomboid64` / `javaw` process).
3. **A dependency is reported missing although the mod "has no requires".** Cause: you read the root (B41)
   `mod.info`; the 42.x one declares more. Fix: read the `mod.info` of the folder the game will use.
4. **A scanner finds the mod but not its B42 id (`YakiHRB42` "not installed").** Cause: version folders are named
   `42.0`, `42.13`, `42.20`; matching only `42` misses them. Fix: match `4\d(\.\d+)*` and `common`.
5. **`ERROR: template "DAMN86fordE150..." not found`, world won't load.** Cause: that DAMN Library dropped those
   templates after its `42.0` folder; the '86 Econoline "Expanded" module (and the '83 M923) only ship `42.0`.
   Fix: disable the referencing modules (the base Econoline and its other variants loaded fine).
6. **`ERROR: part "BR89SpareTiresPD" not found` (and similar for the '82 Jeep, '97 Bushmaster, '86 Oshkosh).**
   Cause: referenced but defined nowhere. Fix: disable those mods. Popularity didn't help: the Bronco and the Jeep
   each have over 1.2M subscribers and hardly any recent comments.
7. **`Fluid not found: Alcohol`, world won't load.** Cause: Common Sense (original upload) has a craft recipe
   using a fluid B42 doesn't have, plus three more Lua errors (`BB_CS_Fireplace.lua:42`, `BB_CS_RecipeCode.lua:13`,
   `BB_CS_GunStats_UI.lua:147`). Its comments are disabled, so nobody could report it. Fix: the separate
   "Common Sense [B42.20+]" upload (`id=VB_CommonSense`).
8. **The mod menu shows one entry for a mod you have twice.** Cause: two installed items with the same `id=`
   (B41 and B42 uploads). Fix: if you only play B42, unsubscribe the B41 copy; if you keep both, know the menu
   picks one.
9. **A "fixed fork" keeps the original's id.** "Reorder The Hotbar (B42+ Fixed)" declares `REORDER_THE_HOTBAR`, the
   same as the discontinued original; others (Equipment UI, Draw On The Map) chose new ids. Fix: unsubscribe the
   original when the fork reuses its id.
10. **GaelGunStore and the combined Brita port don't mix.** GaelGunStore's page says it replaces and edits all
    vanilla firearms and ammunition and is incompatible with any weapon mod that touches vanilla guns or ammo; the
    combined Brita weapon+armour port uses vanilla magazines. Fix: GaelGunStore for guns plus the armour-only Brita
    port ("Brita's Armor Pack B42.20 - Standalone Armor Port").
11. **A mod the player "just installed" has no folder in `content/108600`.** Cause: Steam is still downloading it
    (items in progress sit in `steamapps/workshop/downloads/108600/<id>`, a 3-4 GB pack takes a while), or the
    subscription never registered. `steamapps/workshop/appworkshop_108600.acf` lists what the account is actually
    subscribed to; one mod the player believed installed wasn't in it at all. Fix: check both before writing the
    mod into a preset; the real id is only in the downloaded `mod.info`.

## Assets
None; no files were created except the preset line and our own scripts.

## Cost and time
One long session with four start-up test runs by the player.

## Open questions
- Everything mod-specific here is as of 42.20.3. On 42.21 mods may ship `42.21/` folders (which would replace
  their `42.20/` contents), and the broken vehicle and Common Sense uploads may have been fixed or broken anew.
- Which copy wins when two installed items share an `id=` (load-order position, scan order, or folder name)?
- Does the Mods screen's own Save write the backslash form, and does such a preset apply when the game itself
  wrote it?
- PoweredBuildings V2 logs 16 `require(...) failed` warnings for its own action files; we didn't check whether its
  actions work in play.
