---
kind: game
title: "A new playable class in Space Marine 2 on Saber's CHARACTER_MOD slot (a Chaplain)"
game: "Warhammer 40,000: Space Marine 2"
games_also: []
game_version: "Steam build 25799387 (Patch 15.1, Oct 2026); class first built on Patch 14.x (Sep 2026) and rebased onto Patch 15"
platform: windows
engine: unknown
route: data
tools: ["Saber SM2 Mod Tools (ModEditor, ModelConverter, UsfExporter)", "Python 3 (zipfile, own SSL text parser for 3-way merges)"]
anti_cheat: "EasyAntiCheat. Everything here uses Saber's official mods folder (client_pc/root/mods), which flags the session 'Mods Detected' (private lobbies, separate progression). No injection, no EAC interaction, PvE only."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-15
links: []
tags: [space-marine-2, saber, new-class, character-mod, chaplain, mastery, perks, armoury, talker, constructor]
---

# A new playable class in Space Marine 2 on Saber's CHARACTER_MOD slot (a Chaplain)

> A new playable PvE class (a Chaplain: own armour set, robes with cloth physics, own perk tree, own war-cry
> ability, own default voice, own melee weapon) added to Space Marine 2 entirely through data, on one of the class
> slots Saber reserves for modders. It plays in missions and the armoury in game. This note is the class-level recipe;
> the details live in the other SM2 notes:
> [foundations](sm2-modding-foundations-paks-tools-and-crash-triage.md),
> [models](sm2-models-tpl-format-modelconverter-and-textures.md) (constructor, customization library, cloth),
> [weapons](sm2-weapons-skins-reloads-perks-vfx-and-sounds.md) (melee slots, cloned abilities) and
> [voices](sm2-voices-talkers-and-wwise-audio.md) (talkers).

## Setup
- Steam build 25799387 (Patch 15.1). Built on Patch 14.x, then rebased with a 3-way merge onto Patch 15 (see the
  foundations note). Saber's Mod Tools, Oct 2026 update.
- Everything is text overrides in a mod pak plus one rebuilt character constructor model.

## Route and why
Data route on a **pre-registered class slot**. Saber ships three playable class slots, `CHARACTER_MOD_1..3`, each
with PvE and PvP variants:
- `ssl/player/characters/characters_library.sso`: `CHARACTER_MOD_N = { isHidden = True, __type = "CharacterDesc" }`.
- `ssl/main/user/mastery/mastery_library.sso`: `PVE_CHARACTER_MOD_N` / `PVP_CHARACTER_MOD_N` with only
  `character = "CHARACTER_MOD_N"`.
- `ssl/characters/player/marine/outfits/for_modders/pc_{pve,pvp}_modded_characterN_{client,authority,server}.cls`:
  one-line stubs, e.g. `__type = "pc_marine_pve_client"`. Their `.ssc` / sslbin modules are already compiled and
  already listed in `initial/replicas/initial_replicas_all_{client,server}.resource` and the scene replica lists.
- `ssl/game_mode/rules/available_game_mode_characters_library.sso` already lists the slot, and
  `weapon_loadout_skills_library.sso` already has `PVE_CHARACTER_MOD_N -> "SoldierModN"` packs.
So no new compiled class, enum or replica entry is needed: you fill the slot with data. A brand-new class name
would need compiled code (a new brand crashes the boot), which is exactly what the slots avoid.

## How the game works (what we had to learn)

### The files a class needs, and what each one does
| File | What we changed |
|---|---|
| `player/characters/characters_library.sso` | `CHARACTER_MOD_2.isHidden = False` (makes it selectable) |
| `main/user/mastery/mastery_library.sso` | `PVE_CHARACTER_MOD_2` filled in: `masterSkill` (base perks) + `tiers` of `MasteryLevel` entries (money/xp cost + skill link per level) - grew from 3 lines to ~350, cloned from a retail class's block |
| `main/user/mastery/mastery_skills_library.sso` | the class's `MasterySkill` sets: the base set (e.g. spawn-with-ability perk, dodge preset, reload-holster, healing injector) and a `<Class>_Progression` table of `LevelN = { perks = [...] }` |
| `player/perks/perk_server_factory.sso` (**server pak**) | new `PerkDesc` entries, e.g. `SpawnWith<Ability>` = `PerkTriggerPassive` + `PerkApplicationSetAbility` pointing at the class ability uid. Perks live only in the server pak's `default_other.pak` |
| `main/user/mastery/ui_armory_ordered_mastery_library.sso` | append `"PVE_CHARACTER_MOD_2"` so the class shows in the armoury class list |
| `ui/fusion/hud/squad_panel/code/ui_character_library.sso` | new `UiCharacterIconData`: tac-team image, roster card, class icon (we reused `soldier`), `masteryName/Desc`, `masteryAbility` (the HUD's ability icon), `characterName`, `narrativeName` |
| `ui/fusion/assets/switchers/class_icons/ui_switcher_class_icons_base.sso` | `PVE_CHARACTER_MOD_2 = { __value = "soldier" }` (icon switch) |
| `sounds/voiceover/talker/talkers_library.sso` | `PVE_CHARACTER_MOD_2 = { def = "<talker>" }` (default talker for the mastery) |
| `main/user/weapon_loadouts/skills/weapon_loadout_skills_library.sso` | the slot's `SoldierMod2` pack: allowed firearms / melee / abilities; we added our own melee weapon (`melee_mod_1 = { __type = "WeaponSkillLocks" }`) |
| `body/customization/character_customization_library.sso` | a `PVE_PVP_CHARACTER_MOD_2` section (armour regions, presets, shared items); the class key also appears in shared items' class lists |
| `body/customization/armor_pattern_library.sso`, `global_armor_color_pattern_library.sso` | add the class to the per-class pattern/colour availability blocks |
| `loading_scene_logic/customizable_character_dummy_factory.sso` | the armoury/lobby figure for `PVE_CHARACTER_MOD_2` (and PvP) |
| `characters/.../pc_pve_modded_character2_client.cls` | full class: cloned from a retail class (~28k lines), `geom.nameTpl` = the constructor, `animSet`, cloth (`prop_cloth_sim_magnus`), jiggle (`prop_phys_jiggle`), `masteryType = "PVE_CHARACTER_MOD_2"` |
| `..._authority.cls` | full clone (~64k lines): same constructor and animSet, voice/sound blueprints, `talkerRef` |
| `..._server.cls` | short child of `pc_marine_pve_server`: `talkerRef` + `masteryType` |
| `texts/strings_english.str` (and every other `.str` the game reads) | the new UI keys |

### Body, animation and physics
- The class body is a **character constructor** tpl (all armour pieces in one model, shown/hidden by customization
  regions). We put the Chaplain pieces into the shared soldier constructor, so the class uses the soldier `animSet`
  and inherits all Tactical armour. See the models note for the constructor merge rules (joint accessor types, vertex
  colour pin channels, tangents, hidden regions for unowned objects, `tpl.resource` / `tpl_markup`), for physics
  living in the class `.cls` (merge the cloth/jiggle entries of pieces you borrow from another class), and for
  grafted bones that stretch into "sheets" in missions only.

### Abilities, perks and weapons
- The class ability is a clone of a retail war cry on a new `AbilityUid` (Saber's enum extension). The list of
  uid-keyed files a cloned ability needs, and why the original's damage and perks keep working, is in the weapons
  note's Abilities section; for the class, the HUD `masteryAbility` and the granting perk are the class-side entries.
- A class-only melee weapon: Saber's `melee_mod_1..5` ability slots + the class's weapon pack (see the weapons note).
- `SpawnWith*` perks are how a class gets its ability at spawn; weapon-type perks key on `MeleeStrikeWeaponType`.

### Voice
- The class's own voice is its **BASE talker**: `talkerRef.def` in BOTH `_authority.cls` and `_server.cls`, plus the
  `talkers_library` entry, and each mission route's speaker switch extended for the new talker. Details in the voices
  note.

## Build steps
1. Copy a retail class's `client` and `authority` `.cls` text into the slot's stub files (keep `__type` at the
   bottom), change `nameTpl`, `animSet`, `masteryType`; write the short server child with `talkerRef` + `masteryType`.
2. Unhide the slot in `characters_library.sso`; fill `PVE_CHARACTER_MOD_N` in `mastery_library.sso` from a retail
   class's block; add the class's skill sets to `mastery_skills_library.sso` and any new perks to the SERVER
   `perk_server_factory.sso`.
3. Add the UI entries (armoury order, squad panel icon data, class-icon switcher), the talker, strings in every `.str`
   file the game reads.
4. Build the customization section: start from a retail class section, then add your items; make every preset's key
   set match retail's for that patch (see the models note's gotchas) and drop `isChampion` presets (Gotcha 2).
5. Add the armoury dummy entries for the slot (PvE and PvP), with `characterInfo.masteryType` = your slot.
6. Rebuild the constructor if the class has new armour; merge physics into the class files.
7. Pack (ZIP_STORED), test: class select -> armoury -> mission -> ability -> voice lines -> mission end.

## Verification
- In game (2026-10-03, user-confirmed): the class is selectable, the armoury and missions render it correctly, robes
  simulate in missions, perks and the ability work, the default voice drives the social wheel and chatter.
- In game (2026-10-15, user-confirmed): the class's own melee weapon on `melee_mod_1` works, using the retail
  one-handed hammer animations (see the weapons note).
- Not verified: PvP use of the slot (we only filled the PvE side), and class behaviour in every operation's scripted
  dialogue beyond the routes we patched.

## Gotchas
Other traps hit while building the class are written up in their home notes: robes exploding on the armoury figure,
grafted-bone "sheets" and the "not available for the selected Class" slot (models note); the talker set only in the
authority class and the boot crash from a voice-node class (voices note); the ability cast that hangs on an emote
(weapons note).

1. **Armoury shows every slot as "none", nothing selectable, the whole constructor drawn at once.** Cause: Saber's
   dummy-factory entries for the slot are Tactical copies with `characterInfo.masteryType = "PVE_SOLDIER"`, so the
   lobby resolves the loadout in the Tactical library section. Changing `nameTpl` alone isn't enough. Fix: rebuild
   both dummy entries with `masteryType = PVE_CHARACTER_MOD_N`.
2. **Selecting the class, re-entering the arming chamber: UI frozen, camera still turns.** Cause: the customization
   section was cloned from Tactical including `isChampion` presets, which are only a `skinOverride` to Tactical's
   champion doll; the slot has no champion doll, so `TakeDoll` returns null (visible in the `.ssldmp` JSON). Fix:
   drop every `isChampion` preset from a cloned class section.
3. **A stale standalone pak shadows the class.** An older test pak that ships its own copy of a class file and sorts
   first wins the whole file (first-alphabetical rule), e.g. an old voice pak reverting the class to another
   constructor. Fix: when the class misbehaves after an update, list every installed pak that ships any of the files in
   the table above.
4. **After a game patch the class half-works.** Patch 15 grew both constructors ~15 %, renamed presets
   (`PVP_*` -> `PVE_PVP_*`), added a class and new customization sections. Fix: re-export from the new retail,
   re-apply your edits with a tree 3-way merge, and audit presets against retail.

## Assets
The class armour, helmets and robes came from retail parts (the NPC Chaplain's body, other constructors' pieces) plus
custom helmets (AI-generated base meshes, repainted). The voice was text-to-speech cloned from a real voice actor's
original performance, converted to the game's Wwise format. Don't repeat that: cloning a real person's voice without
their consent is off-limits even for private builds (see the voices note). Saber's mod rules forbid AI-generated
content in mods (see the foundations note's Setup), so keep a build with the AI helmets private, and replace the
cloned voice with a stock or designed TTS voice (private only) or recorded lines.

## Open questions
- Whether slots 1 and 3 have any hard-coded differences from slot 2 (we only used slot 2).
- Whether the PvP variant of a slot can be filled the same way. A modded game can't use public matchmaking, so it
  could only be tried in a private lobby.
