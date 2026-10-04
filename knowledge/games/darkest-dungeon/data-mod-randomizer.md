---
kind: game
title: "A seeded randomizer (trinkets, heroes, monsters, curios, quirks, quests) as a Darkest Dungeon data mod"
game: "Darkest Dungeon"
games_also: []
game_version: "Steam app 262060, buildid 25463639, with DLCs Crimson Court, Shieldbreaker, Color of Madness, Musketeer"
platform: windows
engine: unknown
route: data
tools: ["Python 3.14 (stdlib only)", "localization.exe (ships with the game)", "git diff --no-index"]
anti_cheat: "none (single player); the multiplayer arena DLC folder was deliberately left untouched"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["Jagou"]
date: 2026-10-03
links: []
tags: [randomizer, data-mod, trinkets, buffs, localization, curios, quirks, quest-rewards, balancing]
---

# A seeded randomizer as a Darkest Dungeon data mod

> Darkest Dungeon has an official, data-only mod system: no scripting, so a "randomizer" is a generator that
> reads the user's own install, rolls everything from a seed, and writes override files into
> `<game>/mods/<name>/`. We first shipped a one-trinket test mod, then a randomizer covering trinkets, hero and
> monster stats, monster names, curio outcomes, quirk effects, shop prices, the starting party and quest rewards.
> Every section was checked in the real game by the human (tooltips, character sheet, combat, tutorial).

## Setup
- Darkest Dungeon on Steam (app 262060, buildid 25463639), Windows 11, all DLC folders present under `dlc/`.
- Python 3.14 from the Microsoft Store, standard library only (no Pillow needed).
- Nothing to install in the game: no loader, no DLL. The game's own `_windows/win32/localization.exe` compiles text.
- `um scan` reports "Unknown native engine" and suggests a proxy DLL. Ignore that: the data route covers it.

## Route and why
`data`. The game loads mod folders natively and data files drive almost everything (JSON, CSV and its own
`.darkest` line format). A native hook was never needed. Randomness can't run in-game (no scripting), so it is
baked in at generation time from a seed; each section uses its own RNG stream (`Random(f"{seed}:{section}")`) so
toggling one section doesn't reshuffle the others.

## How the game works (what we had to learn)
**Mod loading**
- A mod is `mods/<name>/project.xml` plus a tree that mirrors the game's folders. The player enables it per
  campaign in the Mods screen when creating or loading a save. Workshop mods live in
  `steamapps/workshop/content/262060/<id>/` with the same layout.
- **Same relative path = replacement** of the base file, including under `dlc/<id>/...` and
  `modes/<mode>/...` (radiant, new_game_plus). Proven by comparing installed Workshop mods' files to base paths.
- **New file name = merge/addition** for list-type files: `<x>.entries.trinkets.json`, `<x>.buffs.json`,
  `<x>.starting.trinkets.json`, `<x>_<lang>.loc2`.

**Text**
- Source text is `*.string_table.xml` (`<language id="...">` blocks of `<entry id="..."><![CDATA[...]]>`); the game
  reads compiled `*.loc2`. A mod's loc2 entries override base strings with the same key (verified with monster names).
- Keys: trinket `str_inventory_title_trinket<id>`, monster `str_monstername_<class_id>` (e.g. `skeleton_militia_A`),
  hero class `hero_class_name_<cls>`, combat skill `upgrade_tree_name_<cls>.<skill>`, camping skill
  `camping_skill_name_<id>`, items `str_inventory_title_<type><id>` (e.g. `supplyshovel`, `gemcitrine`),
  curio `str_curio_title_<id>`, quirk `str_quirk_name_<id>`.

**Trinkets and buffs**
- `trinkets/base.entries.trinkets.json` (+ one per DLC): `id`, `buffs` (list of buff ids), `hero_class_requirements`,
  `rarity`, `price`, `limit`. Icon: `panels/icons_equip/trinket/inv_trinket+<id>.png`, 72x144.
- Buffs (`shared/buffs/*.buffs.json`): `stat_type`/`stat_sub_type`/`amount`, plus a condition `rule_type` with
  `rule_data {float, string}` and `is_false_rule` (negates). `in_rank` is 0-based (`float 0` = position 1).
  Accuracy/dodge are fractions shown as points (0.05 = +5); damage/crit/prot are fractions shown as percent.
- Trinket tooltips are generated from the buffs. **Damage is always a pair**: `combat_stat_multiply/damage_low` and
  `damage_high` with the same amount and rule (173 of 173 damage trinkets), and the tooltip shows a single "DMG"
  line. Treat the pair as one effect.
- `<x>.starting.trinkets.json` gives trinkets at campaign start (they showed up after the tutorial).

**Heroes and monsters** (`.darkest`, one record per line, `key: .field value ...`)
- Hero `heroes/<cls>/<cls>.info.darkest`: `weapon:` (`.dmg min max`, `.spd`), `armour:` (`.hp`, `.def`),
  `resistances:` (percent), `combat_skill:` per level with `.atk`/`.dmg`/`.crit` in percent, `.launch` (ranks it can
  be used from, as digits), `.target` (`@` prefix = allies, empty = self). Each base class has exactly 7 level-0
  combat skills.
- Monster `monsters/<family>/<family>_<A|B|C|D>/<..>.info.darkest`: `stats:` (`.hp`, `.spd`, resists), `skill:` with
  absolute `.dmg min max`. Invulnerable scripted parts use `.hp 999`.

**Other systems**
- Curios: `curios/curio_type_library.csv` (+ `dlc/580100_crimson_court/curios/cc_curio_type_library.csv`). Each
  curio is a block: a header row (col 1 number, col 2 display name, col 4 Good/Mixed/Bad), a column-header row,
  then 8 outcome rows whose col 4 is Nothing/Loot/Quirk/Effect/Purge/Scouting/Teleport/Disease and whose cols 5+
  hold weights and results. Col 2 of those rows carries metadata (id, region, "full curio"). Item interactions
  follow in a separate sub-table.
- Quirks: `shared/quirk/quirk_library.json` (+ CC and CoM copies): `is_positive`, `is_disease`, `buffs`,
  `show_explicit_buff_description`, `show_flavor_description`, `curio_tag`.
- Starting party: `scripts/starting_save/persist.roster.json` (heroes with `heroClass`, `actor.current_hp`,
  `actor.ranks`, `skills.selected_combat_skills`, `skills.selected_camping_skills`). Camping skills:
  `raid/camping/default.camping_skills.json`, where `hero_classes == [cls]` means class-specific.
- First stage coach recruits: `first_hero_classes` in `campaign/town/buildings/stage_coach/stage_coach.building.json`
  (a radiant-mode copy exists under `modes/radiant/`). Nomad Wagon rarity odds: `rarity_generation_table` in
  `nomad_wagon.building.json`.
- Prices: `inventory/*.supply.inventory.items.darkest` (tab-separated, `.purchase_gold_value`).
- Quest rewards: `campaign/quest/quest.generation.json` → `generation.rewards`: `item_table[difficulty][length]`
  (difficulties 1/3/5/6 used, others empty), `heirloom_amount_table`, `trinket_chance_table` per rarity, and
  `resolve_xp_table`.

## Build steps
1. Back up saves first: `C:\Program Files (x86)\Steam\userdata\<id>\262060` (`um backup create ...`).
2. Write a generator that reads the install and writes only into `mods/<name>/` (wipe and regenerate on every
   run, guarded by a marker file so you never delete a folder you didn't create).
3. For text, write `<mod>.string_table.xml` into a temp folder **named `localization`**, run
   `_windows/win32/localization.exe` with that folder as CWD, then copy each `<lang>.loc2` out as
   `<mod>_<lang>.loc2`.
4. Add `project.xml` (copy `_windows/sample_project.xml`) and a `preview_icon.png`.
5. In game: new campaign → Mods → enable it. Restart the game after each regeneration.
6. Emit a human-readable spoiler file (in-game names, effects in words) so the player can check results.

## Verification
- Oracle: the human played and compared in-game tooltips, the character sheet and combat with the spoiler file.
  Confirmed: test trinket in the inventory after the tutorial; randomized trinket tooltips matching the spoiler
  exactly (after the damage-pair fix); hero HP and resistances; monster stats; shuffled monster names in combat;
  curios, quirks, shop prices, starting party, quest rewards "working well".
- Offline checks: `git diff --no-index --word-diff` of generated vs base files; JSON reload of every output; a CSV
  round-trip check (rows outside the swapped cells byte-identical, CRLF kept).
- Not verified: Workshop upload; behaviour with other mods that override the same hero/monster files (it will
  conflict, since whole files are replaced); radiant/stygian modes in depth; gem items inside quest rewards were
  reported as working, but vanilla only uses gold and heirlooms there.

## Gotchas
1. **`localization.exe` prints "SUCCESS!" but writes nothing.** **Cause:** it only works when its working
   directory is named `localization`. **Fix:** compile inside `<tmp>/localization/`.
2. **All game text disappears (risk).** **Cause:** the compiler outputs `english.loc2`, the same name as the base
   file, so shipping it in the mod replaces the whole base table. **Fix:** rename to `<mod>_english.loc2`.
3. **A randomized trinket effect is invisible in game** ("+39 % DMG in melee" missing). **Cause:** the tooltip
   shows one "DMG" line for the `damage_low`/`damage_high` pair, so a lone `damage_high` is hidden. **Fix:** never
   split the pair; draw and scale it as one effect.
4. **Randomized trinkets felt absurd** (+10 SPD only with a vampirism quirk, camp-only combat stats). **Fix:** for
   "playable" levels, keep each slot's polarity (bonus → bonus, malus → malus; note that for stress received,
   food consumption and surprise chance, lower is better), whitelist readable stats and conditions, and avoid
   duplicate stats on one trinket. Keep the unconstrained draw as an opt-in "chaos" level.
5. **Longer or harder quests paid less gold.** **Cause:** each `item_table` cell was rolled independently.
   **Fix:** one global multiplier per seed plus a small per-cell jitter (±15 %).
6. **Shop showed two prices for provisions.** **Cause:** `provision` is declared in both
   `base.supply...` and `mode.supply...`. **Fix:** roll once per (item id, base price) and reuse it.
7. **Tutorial wipe with a random starting party.** **Cause:** a class that can't attack from its rank, or 4
   drawn skills that are mostly utility (e.g. Man-at-Arms with Bolster/Command/Defender/Rampart). **Fix:** a class
   is eligible for rank r only with ≥ N damage skills launchable from r (enemy target, ACC > 0, DMG penalty no
   worse than −60 % or a bleed/blight effect) and enough base HP for that rank; guarantee N damage skills in the
   draw; exclude the Abomination (form-dependent kit).
8. **Quirk tooltips would lie.** **Cause:** some quirks show flavour text or have curio/act-out behaviour rather
   than a buff-generated tooltip. **Fix:** only swap `buffs` between quirks with `show_explicit_buff_description`
   true, no flavour text and an empty `curio_tag`, within the same group (positive / negative / disease).
9. **Some JSON/buff files are not valid UTF-8** (one `*.buffs.json` failed a strict decode) and the arena DLC's
   trinket file doesn't parse as plain JSON. **Fix:** read with `errors="replace"` and skip
   `dlc/1117860_arena_mp` (multiplayer, not worth touching anyway).
10. **`um scan` suggests native hooking.** **Cause:** no known engine signature. **Fix:** check the install for
    `mods/` and `_windows/sample_project.xml` first; Darkest Dungeon is fully data-moddable.

## Assets
The one-trinket test mod reused a base icon recoloured with a channel swap (local testing only; it must not be
published). The randomizer adds no art.

## Cost and time
One session of a few hours, iterating with the human testing in game after each step.

## Open questions
- Monster skill shuffling and enemy group composition (dungeon spawn tables) are the next obvious sections.
- Whether to leave the tutorial's first-expedition monsters unrandomized for new players.
- Publishing: ship a frozen seed (the generated files are derived from game data), not the generator's output
  for arbitrary seeds; check licensing of derived data before any upload.
