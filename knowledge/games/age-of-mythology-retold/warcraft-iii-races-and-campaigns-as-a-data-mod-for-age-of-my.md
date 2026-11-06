---
kind: game
title: 'Warcraft III races and campaigns as a data mod for Age of Mythology: Retold'
game: 'Age of Mythology: Retold'
games_also:
- Warcraft III
game_version: 'AoM: Retold v100.19.17020 (Steam, October 2026); Warcraft III Reforged 3.0.0.24268 (CASC, SD models)'
platform: windows
engine: native
route: data
tools: [CryBar.Cli 1.3.20, stormex 2.2.0, Blender 5.2, Python 3.12 (own MDX reader and MDX-to-glTF converter), um win launch]
anti_cheat: 'none for skirmish and single-player campaigns; personal mod, multiplayer never used'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-13'
links:
- knowledge/techniques/converting-warcraft-iii-reforged-sd-models-mdx-v1800-to-skin.md
- https://github.com/CryShana/CryBarEditor
- https://github.com/Talv/stormex
tags: [total-conversion, data-mod, culture, civilization, campaign, scenario-triggers, xs, cinematics, model-conversion, tmm, tma, manifest-limit, mdx]
---
# Warcraft III races and campaigns as a data mod for Age of Mythology: Retold

> The four Warcraft III races (Humans, Orcs, Undead, Night Elves) are playable cultures in AoM: Retold, each with
> three major gods (WC3 heroes), minor gods, units and buildings converted from the WC3 SD models, WC3 voices
> and an AI. Two Reign of Chaos campaigns (21 missions) are rebuilt as AoM scenarios with XS trigger scripts and
> cinematics. Everything is additive data in local mods. It runs in the real game: each change is checked by
> launching to the main menu and reading the game's merged data dump, then playtested.

## Setup
- **Game:** AoM: Retold on Steam, Windows 11. Local mods live in
  `%USERPROFILE%\Games\Age of Mythology Retold\<steamid>\mods\local\<Mod name>`.
- **Debug dump:** add `DebugOutputGameData` to `<profile>\config\user.cfg`. At every launch the game writes the
  data it really merged (base + every active mod) as UTF-16 XML under
  `%LocalAppData%\Temp\Age of Mythology Retold\Data\game\data\` (`gameplay\proto.xml`, `techtree.xml`,
  `tactics\*.tactics`...). Errors go to `<install-or-user>\temp\Logs\MythLog.txt`.
- **Tools:** CryBar.Cli (BAR archives, `glb-to-tmm`, XMB, `xs-to-xml`), stormex (reads the WC3 3.0 CASC storage),
  Blender (previews and portraits only), Python for everything else.
- **Source assets:** an installed Warcraft III Reforged (read-only). Nothing from either game is redistributed;
  the mod is personal. Its models, icons and voices are Blizzard's, so the built mod stays on this PC: no upload to
  the AoM: Retold mod site or Nexus, and it isn't handed to other players for a multiplayer match. A shareable
  version would need original art and audio.

## Route and why
A pure **data mod**: proto/techtree/culture/civ XML through `*_mods.xml` merge files, new art (TMM/TMA models,
DDT textures), sounds, UI pages and scenarios. Bang is native code with no supported plugin loader, and data
covers everything needed: new cultures, gods, AI personalities, triggers. No DLL, no hook.
- The Bang engine's additive merge (`mergeMode`) and `DebugOutputGameData` are documented officially for Age of
  Empires III: DE, with different file names there (`protomods.xml`):
  [Additive Data Mods](https://support.ageofempires.com/hc/en-us/articles/360062106732-Additive-Data-Mods).
- The other new-civilization data mod in the KB is
  [San Franciscans for AoE II DE](../age-of-empires-ii-de/san-franciscans-civ.md) (Genie engine, units rendered
  from 3D). Another Blizzard-asset port kept private is the
  [StarCraft II character in SWBF2](../star-wars-battlefront-ii-2005/porting-a-skinned-starcraft-ii-character-onto-the-swbf2-2005.md).

## How the game works (what we had to learn)
- **Merge files:** each data file has a `*_mods.xml` twin (`proto_mods.xml`, `techtree_mods.xml`,
  `civs_mods.xml`, `cultures_mods.xml`, `minorgods_mods.xml`, `unitfunctiondata_mods.xml`, `unittransforms_mods.xml`,
  `protounitcommands_mods.xml`, `powers_mods.xml`, `simdata_mods.xml`...). Elements carry `mergeMode="add"`
  (or `remove`). Several local mods stack by priority and their merge files merge too.
- **A new culture = a cloned culture.** Copy the data graph of a base culture (its own techs, units, buildings,
  gods), rename every id with a prefix, then re-wire what is shared: train lists of shared buildings,
  `<animfile culture="x">` on shared protos, unit functions, transforms, unit commands, god picker and tech
  tree XAML pages. Age-up techs of cloned minor gods only show if added with the trick the community
  [Major God Builder](https://forums.ageofempires.com/t/major-god-builder/287709) uses:
  `CommandRemove SecretsOfTheTitans`, `CommandAdd <age tech> row=2 column=0` on `AbstractTownCenter`, then
  `CommandAdd SecretsOfTheTitans`, all in the culture's start tech.
- **What an attack is:** a proto's `<protoaction>` (HandAttack, RangedAttack, ChargedRangedAttack...) only works
  if the proto's `<tactics>` file declares that action. The tactics `rate` decides what the action may target
  (`greek_hero.tactics` gives heroes a RangedAttack that only hits `AbstractFlyingUnit`). The animation played is
  the one named in the tactics action (`<anim>RangedAttack</anim>`), looked up in the unit's animfile.
  Projectiles are protos too: the look is the projectile proto's animfile, launched from the `LaunchPoint`
  attach point. A mod can add its own `.tactics` files under `game\data\gameplay\tactics\`: they load (they show
  up in the dump).
- **Models:** `glb-to-tmm` (CryBar) turns one glTF into a TMM plus one TMA per animation. `.material` and the
  simdata (bounds, attach points, animation durations and tags) are written by hand. Materials are
  `opaque_lit` with BaseColor, Normals, Masks (AO, roughness, metal) and Masks2 (R = player colour);
  alpha cut-out is the `ALPHA_CUT_OUT` permutation plus a threshold. The MDX side is in the technique note
  [Converting Warcraft III Reforged SD models](../../techniques/converting-warcraft-iii-reforged-sd-models-mdx-v1800-to-skin.md).
- **The model manifest has a hard limit** (see Gotchas): the base game has about 12,800 entries in
  `intermediate\modelcache\modelManifest*.xml`, and the game crashes after loading data when the total passes
  about 14,460. That leaves about **1,650 TMM + TMA entries for all active mods together**.
- **Sounds:** additive soundsets (`game\sound\soundsets_<x>.soundset`) with 48 kHz mono PCM16 WAV work without
  touching `soundmanifest.xml`. WC3 animation sound events (`SNDx` event objects in the MDX) map to
  `ui\soundinfo\animsounds.slk` and become `SpecificSoundSet` tags.
- **Icons and portraits:** PNG under `game\ui_myth\resources\...`, referenced as `resources\...png`.
- **Skirmish AI:** a personality in `game\ai\personalities\personalities_mods.xml` pointing to a copy of the
  standard AI script with the culture's units; list every culture's personality in that one file, or the last
  mod copied overwrites the others.
- **Scenarios and triggers:** a `.mythscn` scenario can include XS files (`<Script name="campaign\...\x.xs"/>` in
  its `<Triggers>`), searched under `game\trigger\`. `crybar convert xs-to-xml` turns XS rules into a trigger
  block. Missions were generated from Python scripts into XS with a shared library (camera shots, dialogue with
  subtitles and voice, unit staging, waves from destructible buildings).

## Build steps
1. Extract the base game data from the BAR archives (CryBar) once, for reference and cloning.
2. For each WC3 unit: one JSON config (MDX path, sequence to AoM animation map, attach points, icon, voice set),
   converted MDX → glTF → TMM/TMA (`glb-to-tmm`), plus `.material` and simdata written by the build.
3. For each race: one culture config (base culture, gods, unit slots, overrides, techs), cloned into
   `*_mods.xml` files.
4. Write everything into `mods\local\<Mod>` from scratch at every build (never edit the mod folder by hand).
5. Launch to the menu (`um win launch --steam 1934680`), then read the dump and `MythLog.txt`.
6. Split models into separate mods (skirmish pack, one per campaign) to stay under the manifest limit.

## Verification
- **Oracle 1, the merged data dump:** after each build, launch to the main menu only. The dump shows what the
  engine really merged. Static audits run on it: unit stats against WC3, ranged units really ranged with a
  fitting projectile, animations present in the animfile, tech effects aimed at existing actions, manifest count.
- **Oracle 2, the game's log:** `MythLog.txt` shows load errors.
- **Oracle 3, playtests and screenshots:** skirmish games and full campaign missions, by the human and by the
  agent (game window capture with `um win shot --exe AoMRT_s.exe`, menus driven by computer use, debug builds of
  missions that play themselves). Ordinary screenshots of a fullscreen game only see the desktop.
- **Offline staging check of cinematics:** a simulation of each scripted scene flags actors too close to talk,
  attacks with no enemy in reach, and animations missing from a model.
- **Not verified:** multiplayer, and whether TMAs can be left out of the manifest.

## Gotchas
1. **The game crashes right after loading data, with no useful error.** **Cause:** the model manifest is over
   its limit (about 14,460 entries in total; the base game uses about 12,800), proven with dummy entries.
   **Fix:** share byte-identical TMAs between animations (Idle/CarryIdle/Birth on the same sequence), one variant
   per action, and split the models into separate mods. A campaign mod ships only the models its missions show.
2. **"Assertion Error" on TMM/TMA at launch.** **Cause:** the game was started while a build was rewriting the
   mod folder. **Fix:** never launch during a build.
3. **A unit set to ranged still walks into melee.** **Cause:** its tactics file has no ranged action for ground
   targets (Greek hero tactics only allow ranged against flyers), or the default attack is the hand attack.
   **Fix:** set `<tactics>` to a ranged tactics (`rangedattack.tactics`, `rangedattack_heal.tactics`,
   `rangedattack_chargedrangedattack.tactics`), remove the HandAttack, add the RangedAttack.
4. **Upgrades stop working after a melee/ranged swap.** **Cause:** cloned techs aim at an action by name
   (`action="HandAttack"`). **Fix:** retarget them, and check the dump for effects aimed at actions the proto no
   longer has.
5. **A projectile is invisible in one mod but not another.** **Cause:** the projectile's model sat in a mod that
   was not active (models were split per campaign). **Fix:** ship every projectile model a mod's units fire.
6. **A converted unit seems to hit the air.** Some base projectiles use an invisible animfile
   (`ball_of_fire_invisible`); the visible part (breath, swirl) is presumably on the base unit's own model or its
   spawned effects, which a converted model does not have. **Fix:** give such units a visible projectile (a clone
   of the same projectile proto with another animfile keeps its spawn on hit). Found by audit, not yet seen in game.
7. **Age II never appears for a new culture.** **Cause:** cloned minor-god age techs added to the Town Center
   proto do not show. **Fix:** the CommandRemove/CommandAdd trick above.
8. **Two personalities, only one AI loads.** **Cause:** each culture wrote its own
   `personalities_mods.xml`. **Fix:** one merged file.
9. **`um scan` says the game is .NET.** **Cause:** a .NET helper exe ships with the game. The engine is native
   Bang: use the data route.
10. **Base-game rank names rename your units** ("Medium Contarius"). **Cause:** cloned unit-line upgrade techs
    carry `SetName` effects. **Fix:** drop `SetName` effects whose new name is a base `STR_UNIT_` string.
11. **After a crash, Steam will not relaunch the game.** **Cause:** the crash reporter window stays open.
    **Fix:** close it, or start `AoMRT_s.exe` directly.
12. **A scenario test from the main menu shows a black background and no error.** **Cause:** the scenario was not
    loaded at all. **Fix:** test scenarios from the in-game editor (open, then play).
13. **Computer-use clicks miss the top-right corner of the game** (the main menu button). **Cause:** an invisible
    agent window covers it (`um win drive` reports the agent as foreground). **Fix:** use Escape in game, or ask the
    human for that one click.
14. **Python written through a Bash heredoc came out broken** (`\n` and `\b` turned into control characters).
    **Cause:** not Bash itself, which keeps `\n` and `\b` as two characters in any heredoc (a quoted one,
    `<<'EOF'`, changes nothing at all); a layer between the agent and the shell converted them. **Fix:** write code
    files with a file tool.

## Assets
All art and audio come from the user's own installed Warcraft III: SD models converted by script, SD command
button icons upscaled, original voices. Hero portraits are Blender renders of the WC3 portrait models from the
model's own camera. No generated art. Nothing from either game is shared, and the built mod stays private (see
Setup).

## Cost and time
About a week of agent sessions (2026-10-06 to 2026-10-13), local and cloud, with daily playtests by the human.
No API spend.

## Open questions
- Can TMAs be left out of the model manifest (the official docs only mention TMMs)? That would lift the main
  limit.
- Which of `cultures_mods.xml` / `culture_mods.xml` the game really reads (both were written; one culture
  appears).
- A fifth race needs either the reduced animation profile or a further split of the model mods.
