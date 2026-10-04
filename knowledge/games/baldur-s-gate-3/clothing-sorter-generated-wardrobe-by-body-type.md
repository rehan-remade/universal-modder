---
kind: game
title: "A generated wardrobe mod: 260 clothing mods sorted by race and body type into containers summoned by reusable scrolls"
game: "Baldur's Gate 3"
games_also: []
game_version: "Patch 8 / Patch 8 hotfix (Jun-Sep 2026), Steam, Windows; Script Extender v32"
platform: windows
engine: unknown
route: data
tools: ["LSLib Divine 1.20.4", "PowerShell + bash generator pipeline", "AV Item Shipment Framework (ISF)", "Script Extender (Lua handler)", "Nexus Mods GraphQL API (mod descriptions)"]
anti_cheat: "none; single-player"
status: working
agents: ["Claude Code (Fable 5)", "Claude Code (Opus 4.8)", "Claude Code (Opus 5)", "Claude Code (Opus 5.5)"]
humans: [RedSuper]
date: 2026-10-04
links: []
tags: [containers, treasure-tables, body-types, equipment-race, soft-dependency, item-shipment-framework, script-extender, generator, deterministic-uuids, self-check-gates, classifier]
---

# A generated wardrobe mod: 260 clothing mods sorted by race and body type into containers summoned by reusable scrolls

> A generator reads ~260 installed clothing, armour and weapon mods, decides for every wearable which race and
> body-type combinations it actually supports, and writes one mod ("ClothingSorter") whose containers hold only
> compatible items: per body type (32 containers), per category (melee, ranged, shields, other), per mod and
> per author. Nothing is spawned up front; AV Item Shipment Framework delivers a toolbox of reusable scrolls,
> and using a scroll summons one container. Other mods' items are referenced, not copied, through self-named
> stub entries. In use in game across several rebuilds (latest: 261 mods, 11,345 containers, 327 scrolls).

## Setup
- BG3 Patch 8 / hotfix on Steam, Windows; Script Extender v32; AV Item Shipment Framework (ISF) installed.
- Source data: every installed pak, extracted with `divine -a extract-package` (filter flag is `-x <glob>`;
  `-e` is silently ignored and extracts nothing), `.lsf` converted with `divine -a convert-resource`.
- Pipeline (all scripted, one command end to end): scan paks → classify candidates by stats content →
  extract → force-convert every `.lsf` to `*.cnv.lsx` → parse each mod to JSON → build the support matrix →
  apply author-claim overrides → generate the mod → self-check gates → convert, pack, deploy.

## Route and why
`data`, plus a 40-line Script Extender handler. Alternatives considered:
- Dump everything into the tutorial chest (what most mods do): with ~20,000 items from 400 mods the chest
  froze the game when its contents spawned. Nesting alone does not help as far as we could tell (a container's
  contents appear to be created with the container); summoning containers on demand does.
- Pure-stats summoning with `SummonInInventory(<root template uuid>, -1, 1, false, false, false)` works for a
  container (vanilla Transmuter's Stone and a shipping basket mod do it) but needs an equipped item that
  grants the spell. ISF-style click-to-use scrolls fit better, and SE was already required by ISF.
- Copying other mods' items into ours: no. Items are referenced by stats name; if a source mod is missing,
  the treasure-table entry just fails to resolve and is skipped (logged, no crash).

## How the game works (what we had to learn)
- **Body types are the item root template's `Equipment > Visuals` MapKeys**, and they equal the character
  templates' `EquipmentRace` GUIDs. 25 keys cover the playable bodies; human, elf, drow, half-elf and tiefling
  each have female/male/strong-female/strong-male, half-orc, githyanki, dwarf, halfling, gnome and dragonborn
  female/male (32 containers, Karlach has her own key). Drow players inherit the elf keys through their base
  templates. Half-orc *players* have their own keys, while some NPC bases use the human-strong ones; mods key
  either. A `ParentRace` entry with a zero GUID opts a race out of the automatic fallback.
- **Same rig, same verdict:** human/elf/drow/half-elf/tiefling/githyanki of one gender share a body rig, so an
  item that works for one works for all of them; the matrix unions them per rig group.
- **Placeholder detection:** an item whose map entry for a body type points at a vanilla underwear or nude-body
  visual, while the mod has its own content elsewhere, is a "not supported, shows a placeholder" entry, not
  support. Dangling visual GUIDs contribute nothing.
- **Container recipe** (from a shipping container mod): stats `type "Object"` `using "_Container"`; root
  template parented to vanilla container `aebf62bd-e68d-4e14-9ed7-1d51289a3e4e`, `InventoryType=11`,
  `TreasureOnDestroy=True`, `InventoryList > InventoryItem(Object=<treasure table name>)`. Containers nest:
  a container's table can list other containers.
- **Referencing another mod's item:** a stub `new entry "X"` / `using "X"` makes the name resolve in our stats
  without redefining it; the generator emits one for every foreign item it puts in a table.
- **Reusable scroll** (copied from ISF's own scrolls): stats `using "_MagicScroll"`; root template parented to
  the vanilla scroll `4ffd5c4b-4c56-4f05-a228-a33754bb1806` with
  `OnUsePeaceActions > Action(ActionType=12) > Attributes(ClassId=a865965f-501b-46e9-9eaa-7748e8c04d09,
  Consume=False, SkillID=<marker spell>)`. `Consume=False` is what keeps it reusable.
- **Marker spell:** a standalone `SpellType "Shout"` with empty `SpellProperties` and `TargetConditions
  "Self()"`, no `using`. The SE side listens to `CastedSpell` and calls `Osi.TemplateAddTo(<container>, caster,
  1, 0)` for that spell; `caster` makes it per player in co-op. The finished design sends the spawned container
  to the camp chest with `Osi.SendToCampChest(item, player)` from a `TemplateAddedTo` listener.
- **ISF integration:** ship `Mods/<Mod>/ItemShipmentFrameworkConfig.json` listing container `TemplateUUID`s;
  ISF spawns them into a per-player mailbox in the camp chest. Unknown templates are warned and skipped.
- **Item categories from stats** (resolve the `using` chain first): `Weapon` + `data "Weapon Group"` ending in
  `RangedWeapon`/`MeleeWeapon` (the field name has a space); thrown weapons are melee except `WPN_Dart`;
  shields are `type "Armor"` with `Shield "Yes"` (their `ArmorType` is "None"); rings, amulets and instruments
  are `type "Armor"` but go to "other"; anything `type "Object"` is other.

## Build steps
1. **Scan and classify** every pak by its stats content, then curate: a stats entry is not a new item (a mod
   can redefine vanilla names, add picker placeholders or recolours). Count items through root templates.
2. **Extract** candidate mods and convert **every** `.lsf` to `.cnv.lsx`; the parser reads only those, because
   paks often ship a stale `.lsx` beside the real `.lsf`.
3. **Parse** each mod: items (root template + resolved stats + visuals per body type), native containers and
   their treasure tables (to keep the author's grouping and order), icons, loca.
4. **Matrix:** per item × body type: own visual / another mod's visual / vanilla placeholder / dangling, union
   by rig group, then subtract author claims (descriptions fetched from Nexus' public GraphQL endpoint
   `api.nexusmods.com/v2/graphql`, which returns full descriptions without login; claims only remove support).
5. **Generate** with deterministic UUIDs (MD5 of a fixed prefix + seed); one race container → author
   super-container → mod container → the mod's native containers → items in original order; icons: the mod's
   own bag icon, else its chest-piece item icon, else a verified vanilla icon; race containers use the vanilla
   Disguise Self portraits (`Spell_Illusion_DisguiseSelf_<Race>_<Body>`, all 32 exist).
6. **Self-check gates** (build aborts before packing): every icon name exists in vanilla or an installed mod;
   every treasure-table reference has a stats entry; stats names, treasure-table names and root-template
   MapKeys are unique; no stats name is defined twice; every scroll → spell → container chain resolves; rig
   groups agree.
7. Bump `Version64` every build (it is how BG3 notices the pak changed), keep every UUID stable, pack, deploy,
   and update the mod's MD5 in `modsettings.lsx`.

## Verification
- Pilot with two mods and six containers in game: nesting fills, a fem-human-only dress absent from dwarf and
  dragonborn containers, elf wearing a human-rig dress renders correctly.
- Full builds in game: containers and scrolls work; a reported "items in the wrong race" problem led to the rig
  union and author overrides (82 mods constrained, 14,791 wrongly granted cells removed).
- A self-written Script Extender diagnostic (appending timestamped lines to a file on load, cast and spawn)
  proved which build was running when "nothing changed in game" was reported.
- Not verified: a freeze-free experience for the very largest containers (see Open questions).

## Gotchas
1. **Truncated names collided.** **Cause:** stats names capped at 90 characters by plain substring; four
   sub-containers of one mod collapsed onto one name with four different root templates and tables. All
   existence-style gates passed, because a name defined four times still "exists". **Fix:** names over the cap
   get a deterministic hash suffix (UUIDs come from the raw seed, so none changed), plus uniqueness gates.
2. **Scrolls became equippable and unusable.** **Cause:** the stub generator also stubbed our own scrolls (they
   sit in treasure tables) and defaulted the stub to `type "Armor"`; the stub shadowed the real
   `using "_MagicScroll"` entry. A self-referential stub is right for another mod's entry and wrong for your
   own. **Fix:** filter stubs against our real definitions at assembly; gate on duplicate entry names.
3. **Scroll applied Guidance and played its cast effect.** **Cause:** the marker spell inherited from
   `Target_Guidance`. **Fix:** a standalone spell with no `using`. (Vanilla `Shout_Repulsor` shows that an empty
   `SpellProperties` does override a parent's; the standalone form simply leaves nothing to leak.)
4. **Changing UUIDs bricks saves.** Every container, scroll and item stub is referenced from saves by UUID.
   Never change the seed prefix or hash; bump `Version64` instead. A structural redesign that needs new UUIDs
   is a new version the player starts fresh with.
5. **Items silently missing from the parse (`items=0`).** Causes found: re-extracted mods without `.cnv.lsx`
   conversions; mods whose root templates omit `Stats` and link only from the stats side
   (`data "RootTemplate"`), now back-filled; outfits whose root template carries an `InventoryList` (to deliver
   their own chest) misfiled as containers, now decided by the resolved stats type (one mod alone had 94
   wearables missing).
6. **Mod identity read wrong.** Taking the first `value=` in `meta.lsx` returns a dependency (everything looked
   like "GustavX"), and `Dependencies` is a sibling of `ModuleInfo`, not a child. **Fix:** parse the XML.
7. **Sanitised pak names end in `_`** (from `tr` converting the trailing newline), which broke name matching.
8. **Controls locked after a big spawn, world still running.** Investigated at length: not disk, not CPU, not
   an in-game UI capture window, not native input mods. It went away after a series of changes (camp-chest
   delivery, a dependency-order fix for the MCM framework library, clearing a stuck ImGui layout) and the
   single cause was never isolated. One related, reproducible case: ISF's own "reset tutorial chest" deletes and
   re-creates the container the open chest UI is bound to; with the chest UI closed it is fine.
9. **"Instant spawn, client alive" diagnostics were wrong.** The diagnostic file was overwritten on every write
   and `TemplateAddTo` only queues the spawn. **Fix:** append with timestamps and measure the add events.

## Open questions
- The exact cause of the control lock (point 8).
- Whether very large single containers (1,000+ items) still freeze on open on slower machines; the 32-way and
  per-author split keeps most summons small.
