---
kind: game
title: "Mini tribes: Easterling and Gondorian-deserter captains in their own Nemesis rows, built from the game's own models and deployed to Lithlad and Gorgoroth"
game: 'Middle-earth: Shadow of War'
games_also: []
game_version: 'Steam build 3095001 (exe 1.0.8874.0, public branch, unchanged since 2018-09-05), Windows 10 22H2. Every asset comes from that same Steam copy: the Easterling mercenaries from its DLC4 (Baranor) data, the Gondorian soldiers from the Minas Ithil base data. No other game was used.'
platform: windows
engine: unknown
route: data
tools: ["custom C# gamedb reader-writer + two config-driven builders (PowerShell Add-Type)", "Python 3.12 (save decrypt/edit, world-object dump, bone check)", "Ghidra 12.1.4 (headless, analysis only) + Temurin JDK 21", "QuickBMS + aluigi shadow_of_mordor.bms 0.4", "MinGW-w64 GCC 16.2 (w64devkit: OfflineMode v0.13, diagnostic trace plugin)"]
anti_cheat: "none; single-player only. The mod is game.gamedb + string tables (+ world stations in the imported Udûn region only); the exe file is untouched (SteamStub/Denuvo untouched). Every build and test ran offline with the offline-mode DLL installed (never signed in to WB)."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["DeimozZarco"]
date: '2026-11-06'
links:
  - "knowledge/games/middle-earth-shadow-of-war/offline-mode-and-local-garrison.md"
  - "knowledge/games/middle-earth-shadow-of-war/goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md"
  - "knowledge/games/middle-earth-shadow-of-war/falmer-tribe-a-skyrim-creature-as-a-nemesis-tribe.md"
  - "knowledge/games/middle-earth-shadow-of-war/small-mods-new-orc-bodies-talion-armour-and-mesh-draw-counts.md"
  - "knowledge/games/middle-earth-shadow-of-war/map-import-shadow-of-mordor-udun-as-a-new-region.md"
  - "knowledge/games/middle-earth-shadow-of-war/save-format-decrypt-and-collectible-quests.md"
tags: [nemesis, captains, mini-tribe, faction, army-screen, rows, refill, promotion-events, dominate, garrison, pit-fight, raise-dead, skeleton, anim-base, voices, personalities, character-bundle, preload, body-type, armour-pickers, name-table, titles, strings, spawn-locations, gamedb, save-editing, npc-id]
---

# Mini tribes: Easterling and Gondorian-deserter captains in their own Nemesis rows

> Two small **human** captain tribes in the Nemesis system, made only from models that ship with Shadow of War:
> **Easterlings** (the DLC4 mercenaries) and **Deserters** (the Minas Ithil Gondorian soldiers, with their own four
> names, 13 titles and a "Deserter" label). Each tribe has its own locked 2-slot row on a region's army screen, and
> only that tribe refills it. Its captains spawn at fixed camps, take damage and break, can be Dominated and
> Recruited, go to the Garrison and back, Deploy, fight in pits, speak, and keep their own body when raised as undead.
> Both tribes were built and tested first in an imported test region (Udûn, see the map-import note), then
> **deployed to two stock campaign regions by database edits alone**: the Easterlings to Lithlad, the Deserters to
> Gorgoroth. The user tested every step in the real game (2026-11-02 to 2026-11-06). The last two tests were the
> Lithlad and Gorgoroth deployments, and both passed. The work is driven by two config-file builders, so a third tribe
> is a new JSON file, not new code.

## Disclaimers
- **Personal project.** The mod was made for the author's own install. It is **not distributed**, publicly or
  privately, and won't be: the built `game.gamedb` and string tables are modified Monolith / WB Games data, so anyone
  else, friends included, builds them from their own copy of the game. This note shares the process, tools and
  research only, in the hope that the framework helps other modders add their own mini tribes.
- **All game assets used are from the games the user owns.** Here that is one game, the user's own Steam copy of
  Shadow of War (build 3095001) with its DLC data; no model, texture or sound was taken from anywhere else.
- **The previously made offline mode mod is always on and present when making and installing mods into the user's
  own game.** Every build, install and test in this note ran with the
  [offline-mode DLL](offline-mode-and-local-garrison.md) in place (v0.12, then v0.13 from 2026-11-06). Keep it
  installed while the modded database is in use, and don't use Online Conquest, Online / Friend Vendettas or WB's
  own Garrison: a stored or shared captain of a mini tribe references records an unmodded game doesn't have.
- **Only tested on the Steam build** (3095001, exe 1.0.8874.0, Windows 10 22H2). Every exe address below is for that
  build only. Not tested on GOG / Epic / Microsoft Store / console builds, other exe versions or Proton.
- **No game files are in this repo.** No database, string table, mesh or extracted data; record names are quoted so
  the steps can be repeated on your own copy.

## Credits and prerequisites
- **Monolith / WB Games** for Shadow of War: every model, animation, voice and record used here is theirs, from the
  user's own copy.
- Ghidra (NSA), QuickBMS and `shadow_of_mordor.bms` 0.4 (Luigi Auriemma), w64devkit (Christopher Wellons).
- Earlier notes this builds on, read them first:
  - [offline mode](offline-mode-and-local-garrison.md): offline play, the local Garrison and the Nemesis id fix that
    mini-tribe captains need (v0.13 section);
  - [Goblins of War](goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md): the `game.gamedb` format, name hashes, the
    sort rule, roles → tribes;
  - [Falmer tribe](falmer-tribe-a-skyrim-creature-as-a-nemesis-tribe.md) and [small mods](small-mods-new-orc-bodies-talion-armour-and-mesh-draw-counts.md):
    body types, body items, captain bodies;
  - [save format](save-format-decrypt-and-collectible-quests.md): save decrypt / edit (used for two save fixes here);
  - [map import](map-import-shadow-of-mordor-udun-as-a-new-region.md): the Udûn test region. **Not needed** for the
    stock-region deploys; a mini tribe can go straight into a stock region (section "Deploying a tribe to a stock region").
- Other plugins present in the test install (not part of this mod, loaded by a small ME ModLoader shim): Nemesis
  Recurrence, Always All Upgrades and Talion Level 85 Cap, all by YoRHa9S (Nexus 278 / 289 / 286), plus the diagnostic
  trace plugin from the map-import note.

## Setup
- Shadow of War Steam build 3095001, Windows 10 22H2; the user's long-running campaign save (Act 3+, Lithlad
  unlocked, Udûn imported as a region). Lithlad needs the region's DLC config (`DLC.Config:Lithlad`), present on the
  test copy.
- Offline-mode DLL v0.12 → v0.13 (`GarrisonSize` raised to 100 on 2026-11-06), see Disclaimers.
- Our tools (all own code, described so another agent can rebuild them):
  - `GameDb.cs`: the `game.gamedb` reader-writer from the Goblins note (named and unnamed records, heap strings,
    link fields, one `SortTouched` before save).
  - `MiniTribe.cs` (wrapper `mini_tribe.ps1 -Config <tribe>.json -Db <in> -Out <out> [-DryRun]`): builds a whole tribe
    into one region from a JSON config (table in Build steps). Adopts records that exist, so a re-run on its own
    output changes nothing.
  - `MiniTribeDeploy.cs` (`mini_tribe_deploy.ps1`): puts an already built tribe into another region's faction.
  - `db_diff_named.ps1` / `db_diff_structs.ps1`: record-by-record diff of two databases (about 10 min each).
  - `dbq.ps1` (`DbQuery.cs`): one-load batch queries (describe / walk links / who links here / list / faction rows /
    location fields).
  - `bone_check.py`: lists which bones of a creature's meshes are missing from `orc_base.skel` and how far its bind
    pose is from the orc one.
  - `som_world_objects.py` + `spots_by_location.py`: dump a world `.objres` and count captain spawn spots per location.
  - Save tools on the save note's decrypt: `fix_npc_ids.py [--garrison <x64\OfflineGarrison>]` and
    `fix_udun_locations.py`.
  - An installer per build: checks the game is closed and the installed db md5 is the expected previous build, backs
    up saves + db, copies, re-checks md5.

## Route and why
- **Data only.** Every change is in `game.gamedb` (plus the string tables for the Deserters' names). The stock
  Nemesis plumbing already handles non-orc captains if the records point at the right orc pieces; no exe patch was
  needed for the tribes themselves.
- **Route 1: a row inside an existing region faction** (chosen). A region override replaces a region's faction; it
  can't add a second faction. But a faction's class setup can mix class maps of different tribes (the stock DLC4 orc
  faction already mixes orc and Easterling maps), so a mini tribe is one more class map + one more row.
- **Route 2: a separate faction on its own virtual region** (like the DLC4 `desert_mercs`): rejected. It needs exe
  answers (can two factions place captains in one world, does the hierarchy screen show it) for no gain.
- **Third side vs orc side.** The first Easterling builds were a hostile third side (own alignment, hates orcs and
  Talion). That needs the region's stock spawn kits to get mini-tribe escorts (a world edit), because stock camps spawn
  orc grunts who would fight their own captain. Both tribes ended **orc-side** (alignment `Orc_FactionA`): mercenary /
  turncoat captains serving the region's overlord. That is data only and works with every stock camp.

## How the game works (what we had to learn)

### 1. The Nemesis plumbing a non-orc captain needs
A captain is `Combat/Tree` (class, combat type, stats, inventory, template) → AI template → `Character/Models` (AI
character type, behaviour graph, state FX, class nav marker, NPC bundle, SimpleModel) → `Model/SimpleModel` (body
entries + anim base). The stock Easterling mercenaries are blue allies with no Nemesis moves. What had to come from
the orc records, found one test at a time:
- **Targeting and colour:** the merc trees use `RenderIDSetup Friendly_NPC` and their combat types sit in
  `Excluded_PoolAttacks`, so Talion couldn't target them and wraith view showed them blue. Use the orc captain tree's
  values.
- **Stats:** merc trees carry ally defence stats (no damage from the player, ignore damage while downed). Use the orc
  defence stats.
- **AI character type = the orc profile.** Orcs, ologs and the brandable undead Gondorians share one profile (three
  unnamed range values 70 / 155 / 40 that read as grab / interaction ranges, a bool that is 0 for them and 1 for
  humans, a flags word, a per-class threat picker, `NavMarkerAwareness Default`). Humans have -1 / -1 / 0, so they
  can't be grabbed (no grab-Dominate, no brand). Clone the orc AI types and change only the alignments.
- **State FX:** `Character/StateEffects:NamedOrcFX` has the Weakened / Broken / Hate rings; the merc
  `NamedEasterlingFX` has no Broken ring.
- **Behaviour graph:** the orc graph. The Easterling `.bvr` has almost no grab states (1 "grab" string against 248 in
  the orc graph).
- **Captain Dominate gate:** the Dominate syncs need the target's combat type in the combat-type list
  `All_Orcs_OlogHai`. That list already holds the stock Easterling types; Gondorian types are not in it.
- **Own combat types** (see 5): twins of the orc `Orc_*_FacA` types, appended to every list that holds the orc one.
  Then every orc predicate (execution, grab, instakill hints, Dominate gate) accepts the tribe, and data can still
  name or exclude the tribe on its own.
- `Combat/Sever/Setup:Human` and face setup `Human` on the captain trees: orc dismemberment on a human mesh stretched
  it.

### 2. Skeleton: animation sets come from the SimpleModel's anim base
- `Model/SimpleModel` field a0 = an anim base `Model` whose `.skel` lists the playable `.anix` animation sets.
  `orc_anim_base` (`orc_base.skel`) gives every orc move. The Easterling base (`easterlings_anim_base`) only plays
  shared biped moves. Symptom with the Easterling base: the captain broke and showed the Dominate prompt, Talion's half
  of the move played, but the captain never knelt and the interrogation menu never opened.
- **No re-rig needed for these humans.** `bone_check.py` on the extracted bundles: every Easterling body / armour /
  cape / quiver / hair mesh and the Gondorian soldier body are skinned to bones that `orc_base.skel` (107 bones) has,
  with bind poses within 1.0 cm mean / 3.4 cm max of the orc buff body. Missing are only `L/C/R_Collar` and the
  128-bone human face rig of the heads. So: copy the creature's SimpleModels and point them at `orc_anim_base`.
- A creature on another skeleton (e.g. from another game) needs the Falmer-note conform onto the orc rig first.
  Putting the captain models on the stock **orc SimpleModel** (orc skeleton, Easterling items for the look) as a
  diagnostic made Dominate work but twisted the Easterling meshes.

### 3. Voices: a personality's voice code must have Nemesis scenes
- `Faction/Personalities` = voice code + personality item + trait marker. The DLC4 Easterling class map uses four
  merc personalities with voice codes `ea1`-`ea4`. Nemesis scenes, facial animations and dialogue events are named
  per voice code (`dx_pr_ps_FightPitChall_<code>_NN` …; `br1` alone has 1,621 scene names), and **no `ea1`-`ea4`
  scene exists**. Result: silent captains, and the pit-fight intro waits forever on the load screen.
- Fix: the mini tribe's class map uses `Orc_Personalities` (orc voice codes). Captains made before the fix: point the
  four merc personalities' voice codes at orc twins (`ea1` → `br1`, `ea2` → `wh1`, `ea3` → `cv1`, `ea4` → `pr1`; this
  also changes DLC4's hired mercs) and append each to every `Faction/Predicates/PersonalityLists` list that holds its
  twin (those lists pick scene speakers). Combat grunts and shouts stay human (`hmn_infantry` voice set).

### 4. Character bundles must be preloaded where the tribe can spawn
- `Character/Models.Server.NPCBundle` names the bundle a model needs. Orc models have none. The spawn check
  (`FUN_14016652c`, called from the faction-member spawn checks `FUN_141ac21b8` / `FUN_141ac2494`) passes when the
  model has no bundle or the bundle is in the loaded set. Otherwise it logs "%s doesn't have character bundle '%s'
  loaded" and asks for a load, but only where streaming loads are allowed. **Arenas don't allow them**: the pit fight
  logged "unable to spawn - Template not found" a thousand times and hung on the load screen.
- Fix: one NPC bundle record for the tribe (Easterlings: `easterlings_base` + `gondorian_soldiers` `.bndl`), added to
  the preload lists `Server/NPCBundle/Lists`: `World_Common_Load` (arenas), `FactionBase` (the SinglePlayer
  game-mode list of the stock regions checked, Lithlad and Gorgoroth) and the region's own game-mode list if it has
  one (`WorldInfo:<region>.GameModeBundles`).
  The imported Udûn uses its own list; a tribe there that is only in `FactionBase` never spawned.
- **Every piece a tribe can roll needs its mesh in a bundle the NPC bundle loads.** The Easterling head pool includes
  an eyepatch head whose mesh is only in `gondorian_soldiers.bndl`; captains that rolled it had floating eyes and hair.
  Head pieces carry no bundle of their own.

### 5. Combat types are identity records
- `Combat/CharacterType` records have no attributes; they are referenced only by `Combat/Tree` and by combat-type
  lists (`Orc_Infantry_FacA` is in 95 lists). The tribe gets `UD_<id>_Infantry` / `_Archer` / `_Defender` = twins of the
  orc ones, appended to all 131 lists that hold an orc twin (292 entries), plus its own list (`UD_Easterlings`).
- That own list is what the undead items exclude (field `F15EA6B9` on `Body_Scar_BodyReplacement` and
  `I_Am_Undead_Appearance`). Before it, raised Easterlings got the orc scar body and orc undead skin (black body).

### 6. Body type ids and armour pickers (the raise-dead look)
- SimpleModel entries carry a `BodyType` id. `ArmorData.ModelPicker` = list of {RequiredBodyType, SimpleModelPiece}:
  an armour item draws nothing on a body type it has no picker for, silently.
- Raise Dead (`Combat/ResurrectionData BIP_Necro_RaiseDead_AOE`) removes the old body and hands out `IT_Orc_Body_LOD`
  (slot 8, the far / army-screen unibody) plus a body replacement (slot 10, `AD_Body_Scar` / `orc_Cursed`). Those only
  had pickers for 2-5 (orc slim / buff / stocky, olog), so a raised Easterling (type 12) was **invisible** apart from
  the undead smoke.
- Fix: a picker for the tribe's body type on every slot-8 / slot-10 ArmorData that has orc pickers (9 records:
  `AD_Orc_Body_LOD`, `AD_Flint/Tinder_BodyLOD`, `AD_Body_Scar`, `AD_Tower/Tinder/Falmer/Flint/Infested_Body`): LOD →
  the creature's LOD unibody, body → its arms / body piece. Raised Easterlings and Deserters then keep their look
  (with `orc_Cursed`'s red eyes and veins, whose head-material overrides reach human heads too).
- **Pick a body type id no other creature uses.** Ids 0-12 are all taken in stock data (0 Serka / Torvin, 1 rat /
  Nazgûl / werewyrm / balrog and 85 SimpleModels in all, 2-4 orc, 5 olog, 6 Talion, 7 wraith Talion, 8 Baranor /
  Gondorian archer, 9 Eltariel, 10 Celebrimbor, 11 legendary Eltariel, 12 Easterling). Two tribes on one id share the
  raised look. The Gondorian soldier and defender entries are type 1, shared with unique orcs (Ratbag, Mogg, Brogg,
  Orthog, Zhoja), so their pickers would leak onto them: the Deserters copy those entries and set them to **8** (only
  player gear has type-8 pickers, never NPC items). Ids 13+ are untested.

### 7. Inventory items the Nemesis predicates look for
- Captain inventories (`Combat/InventorySetup.ItemsFactionMember`) need `Item_Marker_In_Hierarchy` (Dominate /
  named-enemy predicates) and must not carry `DisallowIdentify_IT`. The stock Gondorian soldier inventories lack the
  marker and carry `DisallowIdentify_IT`. The Deserters clone the working Easterling captain inventory and swap the
  weapons (`Gondorian_1HS_Longsword`, `Gondorian_2HR_Longbow`, `Gondorian_Shld_Defender_and_1HSp_Halberd`), dropping
  the Easterling look items.
- Fixed weapons per class, no orc gear pickers, no weapon generation: exactly the "preset captain" design. Keep
  `DoNotDecapitate` for meshes without gore caps.

### 8. Names, titles and the tribe label
- `Faction/NameTable` = one list `NameStringIDs` of string keys (no gender, no weights). The table comes from the
  tribe's class map, so an own map with an own table needs no exe work.
- Shown name = name + the role's `Title` key ("Mistadir" + "the Runaway"); the tribe word in "Deserter Destroyer" is
  `TribeDef.DisplayName` (cloned Easterling tribes say "Vanishing Sons", key `Merc_Tribe_Title`).
- The Deserters: 4 names, 13 title roles (one clone of a base role per title; 10 stock already-localised titles such
  as `Orc_Title_Traitor`, `Merc_Title_Oathbreaker`, plus 3 new keys), label key → "Deserter".
- **String tables are not merged.** `x64\default.archcfg` is searched bottom-up and the last entry that holds a file
  wins, so a new `string.strdb` hides every other mod's strings. Copy the live set (here the Goblins / Falmer mod's 28
  files, 14 languages × `string` / `string_uwp`), add the keys, and install the copy in a loose folder that sits lower
  in the list. Keep the source md5s in a manifest, and rebuild when the source mod changes.

### 9. Rows, ranks and the refill chain
- A faction's `Rows` list `Faction/Rows` records: rank (`Faction/RowRanks`), `ColumnMax` slots, three location tiers,
  sim-event setup, levels. Stock region armies have 6 rows (overlord 1, inner warchiefs 2, outer warchiefs 4, captains
  4 + 8 + 7); **no stock faction has 7**.
- Refills: the faction's `Faction/Events/Setup.PromoteEventSetup` → `PromotionEventSetup` entries
  {GlobalVarPredicate, **RowIndex**, NumSimEvents per difficulty step, SimEventsToCreate} → sim events
  `PromoteEmpty_Builder_Transform` / `PromoteDead_Builder_Transform` → participants → job `TransformNew_*` with a
  `Faction.Builder` (no `CombatTrees` = the faction's class picker; with trees = only those classes).
- **The slot to fill is picked by rank, not by row** (`SimEventPosition:EmptyPosition` = {RowRank, MustBeEmptySpace}).
  A second captain-rank row would be filled by the orc refills too. A locked row therefore needs its own rank (clone
  of `Captain` with the same flags) and its own copies of position → participants → job → builder (trees = the tribe's
  captain trees) → sim events. The rank never takes part in warchief promotion or bodyguard rows, so mini-tribe
  captains stay captains (wanted).
- `TimedEvents:CompletelyEmpty.MinNumHoles` = the number of captain slots of the regions using it (stock 19). Add the
  new slots, but only on a timed event the region owns.
- A redeployed follower goes into a standard captain slot, which frees the mini-tribe slot; it refills.

### 10. Captain locations
- Each row lists `AI/SpawnAmbient/Locations` in three tiers (`Locations`, `LocationsLowPriority`,
  `LocationsLastResort`); a location names an area (`AI/SpawnAmbient/Areas`). In the world, captain spots are
  `AISpawnerAmbientLocation` objects with `LOCATION=<name>`; several spots can share one location, and the captain
  appears at one of them when Talion is near and the spot's spawn predicate passes.
- Picker `FUN_14078adb8(faction, row, member, flag)`: goes through the tiers in order and takes the best-scored valid
  location (quest gates, `MustEvalQuestToAssign`, tag / trait checks, random tie-break). `FUN_14078b074` lists the
  location of every other member of the faction (all rows), and the tier picker skips those: **one captain per
  location, faction-wide**. Nothing valid → the captain has no spot and never appears in the world.
- **Locations are saved and kept** across loads; a member is re-picked only when his location fails a validity check,
  not when the row's lists change. So changing a row's locations doesn't move captains already placed (save fix below).
- `MustEvalQuestToAssign = 1` (all stock camps) needs the region's Nemesis quest lists. It passes in stock regions,
  Easterling types included (Lithlad test). In a region without quests (the imported Udûn) set it to 0, or no captain
  is ever posted.
- Spawn predicates on stations: stock `AmbShort` spawns only at 10-60 m out of line of sight or 60-75 m off-screen, so
  open-ground spots rarely spawn; `NotOnScreenOrNear` (≥ 20 m, off-screen) is the reliable one. Stock camps keep their
  own predicates.
- Stock quirk (Lithlad): the last-resort locations `Desert_Backup_A-G` have **no** spots in the world; the 7 backup
  spots there carry the Gorgoroth names `V_Backup_A-G`. Lithlad captains that fall to the last tier never appear.

### 11. The army screen
- Stock forts place rows 0-3 on fixed stage pieces (`Faction/World/Fort/Piece`, 11 `_base_Row*` pieces in all 33
  stock fort setups); rows 4-5 stand on the member grid. A 7th row (index 6) also lands on the grid: in Lithlad it
  showed as the front pair of rings, and the cursor reached it. No stage pieces needed in stock regions.
- The cursor is confined to the scene's `WorldUIFortCursorBrush` volumes. Slots placed outside them can't be selected
  (a dominated captain there couldn't be given orders). In a region with fixed pieces for every slot (Udûn), put the
  tribe's slots on spare spots of the captain grid.

### 12. Shared stock records (what a stock-region deploy must not touch)
- Stock regions share most army records: `CombatTreePicker:Default` and `ClassMemberSetup:Default` (24 factions each),
  event setups (`Faction_desert_Setup` is shared by 5 desert factions, `Faction_volcano_Setup` by 7 volcano ones),
  `PromotionEventSetup:Default` (linked by 6 event setups, 3 timed events and the 3 difficulty overrides `Difficulty_3Hard
  / 4Brutal / 5Bloody.PromotionEventOverrides` Default → HardMode), and even row records (the main-game desert rows
  are shared by 3 factions).
- Entries for rows a faction doesn't have are ignored (the 1-row `Faction_Player` runs on the 6-row Default setup).
  So a RowIndex-6 entry in `Default` / `HardMode` reaches only factions that have a row 6: fine for **one** deployed
  tribe.
- **The second region with a row 6 collides:** refill entries are matched by RowIndex only, and the refill chain is
  tribe-specific. Gorgoroth's Deserter row would have been refilled by the Easterling entry Lithlad added. Fix after the
  stock precedents (Minas Ithil has `Default_MinasIthil` / `HardMode_MinasIthil` + its own difficulty pairs): the
  second region gets its own promotion setups (copies minus the other tribe's row-6 entries), own difficulty pairs,
  own copies of the timed events that point at the setup, and its event setup re-pointed.
- Clone, don't edit, the shared class setup: `<Region>_ClassMemberSetup` = `Default` + the tribe's class map, and
  only that faction points at it. The class picker stays `Default`, so the tribe never rolls into orc rows.
- The exe hard-codes `Faction_desert_mercs_DLC4` by name (hire logic); clones are ordinary factions.

### 13. Nemesis ids and the Garrison
- Captains made while the offline DLL's id prefix wasn't set got bare ids `_NPC_<n>` (`n` restarts at 0 each launch).
  The Garrison refuses a captain whose id another captain has, and that includes captains **stored in the Garrison**
  (they are not in the save). A mini-tribe row that refills right after a load is the typical source. Details and the
  v0.13 fix (the DLL replaces the game's id writer in memory, so every id is prefixed from the first captain on) are in
  the [offline note](offline-mode-and-local-garrison.md).

## Build steps

### A. Build a tribe (MiniTribe.cs, one JSON config per tribe)
The config names every record (`{id}` = tribe id, `{c}` = class), the sources to clone, and the region. Steps, in run
order; each adopts a record that already exists instead of cloning it:

| step | what it writes |
|---|---|
| precheck | sources exist; body type per class; picker pieces; bundles; personalities; a NEW tribe whose record names already exist stops the build (protects the first tribe when a config is copied) |
| region | the region faction's own class picker / class setup (cloned when missing) |
| units | per class: captain AI type = orc profile + own alignments; captain tree = orc tree + tribe template, inventory, human sever / face, own combat type; grunt tree; templates → models (orc graph, `NamedOrcFX`, orc class marker, tribe SimpleModel on `orc_anim_base`, tribe NPC bundle); grunt AI types + a mixed patrol type; optional own inventory = clone of a working one with items swapped / dropped |
| combat types | twins of the orc types in every list holding the orc one; tribe list; exclusion on the undead items |
| tribe | `TribeDef` clone; one role per title (or a clone of every role of a single-tribe role list); own name table; class map (trees, roles, `Orc_Personalities`, name table) into the region class setup |
| voices | legacy personalities → orc voice codes + personality lists (only for captains made before the fix) |
| bundle | NPC bundle record + its preload lists |
| row | own rank, row (slots, locations, tiers), refill chain copies, promotion entry, `CompletelyEmpty` holes, army-stage pieces when the region fixes every slot |
| body | the tribe's body-type picker on the 9 slot-8 / slot-10 ArmorData |
| strings | live string set + the tribe's keys → 28 files + md5 manifest |
| extraSets | free field edits, e.g. `TribeDef.DisplayName = s:<key>`, emptying an old row's location tiers |

Run `-DryRun` first (full report, no db), build, then diff old vs new db with both diff tools (in the background, one
at a time). The kit's own NEW / CHANGED list must equal the diff. Checks that held for every build: a re-run on the
output = 0 new / 0 changed; the Easterling config rebuilt the hand-made build chain's result with no named or struct
differences (only the layout table and header counts differ in bytes); a second test
tribe built fresh from stock sources matched the first in 109 of 111 record pairs after name mapping (the other 2 were
its own stage spots).

### B. Deploy a built tribe to a stock region (MiniTribeDeploy.cs)
The unit, tribe, voice, bundle and body records are region-free, so a deploy only adds the region side. Config for
Gorgoroth (the second tribe on a row 6, so it uses `ownPromotion`; Lithlad's config is the same without it, with
`promotionSetups ["Default", "HardMode"]` and an `alignment` block):

```json
{
  "tribe":  { "classes": ["Infantry", "Archer", "Defender"], "captainTree": "AI_UD_Des_{c}", "rank": "UD_DesCaptain" },
  "region": {
    "faction": "Faction_volcano",
    "classMemberSetup": "Volcano_ClassMemberSetup", "classMemberSetupFrom": "Default",
    "classMapFrom": "Udun_ClassMemberSetup",
    "ownPromotion": {
      "setup": "Volcano",
      "setups": [ { "name": "Volcano", "from": "Default" }, { "name": "HardMode_Volcano", "from": "HardMode" } ],
      "difficultyPairs": [ { "incoming": "Volcano", "override": "HardMode_Volcano", "templateIncoming": "Default",
                             "difficulties": ["Difficulty_3Hard", "Difficulty_4Brutal", "Difficulty_5Bloody"] } ],
      "eventSetup": "Faction_volcano_Setup",
      "timedEvents": [ { "name": "Volcano_HalfEmpty", "from": "HalfEmpty" },
                       { "name": "Volcano_FillUp", "from": "FillUpCompletely_LongDelay" },
                       { "name": "Volcano_CompletelyEmpty", "from": "CompletelyEmpty" } ]
    },
    "promotionSetups": ["Volcano", "HardMode_Volcano"],
    "promotionEntryFrom": { "setup": "Udun", "rowIndex": 3 },
    "completelyEmpty": "Volcano_CompletelyEmpty"
  },
  "row": {
    "name": "volcano_Row_Des", "from": "volcano_Row_Captain_0", "slots": 2,
    "locations": ["V_StagingMill", "V_BulwarkFire"], "lowPriority": ["V_LedgeCamp", "V_AshCamp_1"], "lastResort": [],
    "removeFromRows": ["volcano_Row_Captain_0", "volcano_Row_Captain_1", "volcano_Row_Captain_2"]
  }
}
```

What the deploy does, in order:
1. **Alignment** (optional): the tribe's AI types and grunt templates to the region's side (`Orc_FactionA`, followers
   `PlayerFollower`, grunt templates no alignment). This changes the tribe everywhere it lives.
2. **Class setup:** clone `Default` as the region's own setup, link the tribe's existing class map, point the faction
   at it.
3. **Row:** clone a stock captain row of that region (keeps its levels, sim-event setup and rewards); set the
   tribe's rank, slots and location tiers; append to the faction's `Rows` (it becomes index 6).
4. **Camps:** choose stock camp locations with no filters except `MustEvalQuestToAssign` (Lithlad and Gorgoroth both
   have 6-8 low-priority camps with 3-4 compact spots each), list them in the new row and **remove them from the orc
   captain rows** of that faction (a location holds one captain faction-wide). Give 2 spares in the low-priority tier.
   Before installing, check the save: a captain already holding a chosen camp keeps it.
5. **Own promotion records** (only for the second tribe on the same row index): clone the setups minus the other
   tribe's entries for this row index, add the difficulty pairs (copied from the `Default` pair), clone the timed events
   onto the new setup and swap them into the region's event setup, re-point the event setup's `PromoteEventSetup`.
6. **Refill entry:** a copy of the tribe's existing entry (from its first region) with the new RowIndex, in each
   promotion setup the region uses. The tribe's refill chain is reused: it is faction-free.
7. **Holes:** add the slots to the region's own `CompletelyEmpty` (never the shared one).
8. **Retire** (optional): drop the old region's refill entry and holes. Keep the old row record while saved members
   are in it; empty its location tiers so a resurrected member can't reclaim the spots.
9. No preload change in stock regions (they use `FactionBase`), no stage pieces, no world edit.

Then diff, install with the game closed (installer checks the previous db md5, backs up saves + db), and test.

### C. Save fixes used along the way
- **Locations stick** (10): when the imported region's rows changed, legacy captains kept old or no locations.
  `fix_udun_locations.py` gives each member a free location from his own row's list (location = the u32 after the bytes
  `04 FF FF FF FF 00` in the member record; row link next to the faction link).
- **Duplicate ids** (13): `fix_npc_ids.py --garrison <x64\OfflineGarrison>` rewrites every duplicated bare
  `_NPC_<n>` to a unique same-length id, counting the ids of garrisoned captains (`npc_profile_guid` in the
  `.agb` files) as taken.

## Verification
All in the real game by the user, offline, on the long-running campaign save; screenshots and the trace / offline
logs checked after each test.
- **Easterlings in the imported region (2026-11-02 / 03):** captains red and hittable, break with the BROKEN ring,
  kneel for Dominate, interrogation menu, Recruit, follower turns blue, Garrison send and return, Deploy (to Núrnen),
  pit fights load and play (mask and scarf move with the voice lines), voiced, heads on every new captain, raised
  Easterlings visible with their own body (army screen LOD and up close), branding grunts.
- **Locked row (2026-11-03 / 05):** only Easterlings refill their row, orc rows stay orc; captains at their fixed
  stations.
- **Easterlings to Lithlad (2026-11-05, PASS):** the 7th row refilled in a Lithlad that Talion holds; both captains
  found at their camps; one dominated, garrisoned and redeployed; cursor reaches the row.
- **Deserters (2026-11-05, PASS):** row fills; names, titles and label show ("Dregron the Wanderer, Deserter Slayer",
  "Mistadir the Runaway, Deserter Destroyer"); Dominate; Garrison; pit fight against an orc; raised Deserter keeps the
  Gondorian body; Deploy to Cirith Ungol. One archer was refused by the Garrison (duplicate id, Gotcha 11); after the
  save fix and OfflineMode v0.13 he was accepted (2026-11-06).
- **Deserters to Gorgoroth (2026-11-06, PASS, the user: "everything checks out").** Database diff vs the previous
  build: only the planned records (2 promotion setups, 3 difficulties, 3 timed events, the new row, the 3 orc rows,
  the faction, its class setup and event setup) and no existing struct changed; a re-run on the output = no changes.
- **Not verified:** other builds and stores; a tribe rolling into normal orc rows at a weight (`rollWeight`, built, not
  tested); every one of the 4 Deserter names seen (3 seen so far); a Garrison list past 50 captains; the new titles in
  languages other than English (the new keys hold English text in all 14); DLC4 (Baranor) mode with the deployed rows
  (it swaps Lithlad's faction, so the row should not exist there); fort sieges with a mini-tribe captain in Sauron's
  offense.

## Gotchas
1. **Talion couldn't target the new captains; wraith view showed them blue.** **Cause:** the merc trees'
   `RenderIDSetup Friendly_NPC` and `Excluded_PoolAttacks`. **Fix:** orc captain tree values; own combat types.
2. **Captains took no damage from Talion.** **Cause:** ally defence stats on the merc trees. **Fix:** orc defence
   stats.
3. **Captains broke but never knelt; the Dominate menu never opened.** **Cause:** orc-only animation sets need the
   orc skeleton, which comes from the SimpleModel's anim base. **Fix:** tribe SimpleModels on `orc_anim_base` (the
   meshes already fit the orc bones, `bone_check.py`).
4. **Grunts couldn't be grabbed or branded; no grab-Dominate.** **Cause:** the human AI character profile. **Fix:**
   orc AI type clones with own alignments.
5. **Pit fight stuck on the load screen; captains silent.** **Cause:** DLC4 merc voice codes `ea1`-`ea4` have no
   Nemesis scenes. **Fix:** `Orc_Personalities` in the class map; old captains via voice-code twins + personality
   lists.
6. **Pit fight still stuck; trace: "Template not found".** **Cause:** the tribe's character bundle isn't loaded in
   arenas, which can't stream. **Fix:** preload the tribe bundle in `World_Common_Load` and `FactionBase`.
7. **Floating eyes and hair instead of a head.** **Cause:** a rollable head's mesh lived in another bundle. **Fix:**
   every rollable piece's `.bndl` in the tribe's NPC bundle.
8. **Raised captains came back black.** **Cause:** shared orc combat types, so no undead item could exclude the tribe.
   **Fix:** own combat types + exclusion list.
9. **Raised captains invisible except for the smoke.** **Cause:** no armour picker for the tribe's body type on the LOD
   and body-replacement items handed out by Raise Dead. **Fix:** body-type pickers on the 9 ArmorData.
10. **(Avoided by research)** Deserter captains on the stock Gondorian inventories would miss the Dominate /
    named-enemy predicates. **Cause:** those inventories lack `Item_Marker_In_Hierarchy` and carry
    `DisallowIdentify_IT`. **Fix:** clone a working captain inventory and swap the weapons (the kit now warns on both).
11. **"You cannot send this Follower to the Garrison" for one Deserter only.** **Cause:** a bare id `_NPC_0` shared
    with two other save captains **and** a garrisoned orc; the v0.12 prefix window had missed that session. **Fix:**
    save id rewrite counting Garrison ids + OfflineMode v0.13. Check the Garrison store as well as the save.
12. **A tribe in its own region never spawned; trace: "doesn't have character bundle … loaded".** **Cause:** that
    region's game mode uses its own preload list, not `FactionBase`. **Fix:** add the tribe bundle there too.
13. **No captain was ever posted in the imported region.** **Cause:** `MustEvalQuestToAssign = 1` on locations of a
    region without Nemesis quests. **Fix:** 0 there; leave stock regions alone (it passes for these tribes).
14. **Orc refills took the tribe's slots** (first locked-row design). **Cause:** refills pick the slot by rank. **Fix:**
    own rank + refill chain copies.
15. **Mini-tribe slots on the army screen couldn't be selected.** **Cause:** fixed stage pieces outside the cursor
    brush volumes. **Fix:** spare captain-grid spots (stock regions: no pieces at all, the grid works).
16. **(Avoided by research)** The second deployed tribe on row 6 would be refilled by the first tribe's builder.
    **Cause:** shared `PromotionEventSetup:Default`, entries matched by RowIndex. **Fix:** own setups, timed events and
    difficulty pairs for the second region.
17. **Deploy configs are not independent.** The Lithlad deploy's `retire` block drained the Udûn row of that tribe;
    the Udûn row was later re-pointed at new spots by another config. Re-running the old config as is would drain it
    again. Keep a build log of which config ran on which db, and build each database from the previous one.
18. **`db_diff_named` always reports `NEW Faction/Loot/TagWeight:` and `NEW Faction/Loot/Tag:`.** Two stock records
    whose names hold a non-ASCII byte; the name lookup returns null. False positives.
19. **Changing a row's locations didn't move existing captains.** **Cause:** locations are saved and kept. **Fix:**
    the location save fix, or wait for the captains to die / be dominated.
20. **The database header's named / unnamed counts grew with every hand-made build.** **Cause:** the early tools never
    reset the count snapshot before saving, so each save added the totals again. Harmless to the game; the kit keeps
    the base db's value.

## Known issues (open, by the user's choice)
- Slot-11 head replacements (e.g. sack / infested heads handed out on raise) have no human head picker.
- About 150 shared power-struggle jobs exclude Easterling combat types, so mini-tribe captains get few Nemesis
  missions.
- Faces: the human head meshes use a face rig the orc skeleton lacks; masks and scarves move with the voice lines,
  bare faces were not checked closely.
- In the imported region only: two patrols copied from one stock caravan kit never spawn together (shared
  `ScenarioSetup`); parked.

## Assets
None made: every model, texture, animation and voice is the game's own. New data is records and 8 strings per
language.

## Cost and time
Five days of sessions, 2026-11-02 to 2026-11-06: about 20 database builds for the first tribe (one test round each
for most gotchas above), then the kit and its regression builds, the Deserters (3 builds: tribe, army-screen spots,
new Easterling spots), the Lithlad deploy (1 build) and the Gorgoroth deploy (1 build). Each database diff takes
about 10 minutes.

## Open questions
- Body type ids 13+ (would free the shared-id problem for many more tribes).
- A third tribe on row 6 in a third region: the `ownPromotion` path is generic, but only tested once.
- A creature from another game as a mini tribe: needs the Falmer-note conform onto the orc rig, then a kit config
  (the kit has a checklist; the knight-type creature it was designed for is not built yet).
- The Garrison list past 50 captains (the offline DLL serves up to 256; the game asks for 50).
