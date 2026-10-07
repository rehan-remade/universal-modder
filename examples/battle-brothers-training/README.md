# Training Grounds for Battle Brothers

A town building where one brother can be drilled hard. For a few days he suffers -25% on every
attribute. Afterwards three attributes you chose have their starting roll lifted to the best start his
background allows. Level-up gains stay on top.

Example: a brother whose Melee Skill started at 47 and gained 13 from levels (60) ends at 56 + 13 = 69
when his background maxes out at 56.

Status: first version, **not yet tested in the real game**. Read "Limits" below.

## Requirements
- Battle Brothers (Steam, base game; no DLC and no Legends needed, Legends is not a dependency)
- Modern Hooks 0.6.0 or newer (Nexus mod 685)
- MSU 1.9.0 or newer (Nexus mod 479)

## Install
1. Install Modern Hooks and MSU as their pages describe (zips in `Battle Brothers/data/`).
2. Run `python build.py` in this folder. It writes `dist/mod_training_grounds-1.0.0.zip`.
3. Copy that zip into `Battle Brothers/data/` (or `python build.py --install "<data folder>"`).
4. Start the game. Back up your saves first (`Documents/Battle Brothers`).

## Use
Only some towns have it (25% by default, chosen from the town's name, so the same towns always do) and the town needs a free building slot. A new "Training Grounds" building
appears in the first free slot. Click it, pick a brother (3 per page), pick three attributes, confirm.
The price is taken at once, the penalty runs for the set number of days, then the gain is applied and
logged. Open Mod Settings (MSU) to change:

| Setting | Default |
|---|---|
| Training days | 5 |
| Base cost (gold) | 500 |
| Cost per level (gold) | 150 |
| Towns with a Training Grounds (%) | 25 |

Price = base + per level * brother level.

## How it works
- The building is injected into the town screen by hooking `settlement.getUIInformation` and
  `settlement.onSlotClicked`. It is not stored in `settlement.m.Buildings`, so a save never references a
  class from this mod for towns.
- The state (days left, chosen attributes) lives in a skill on the brother, `effects.tg_training`,
  which saves with him and vanishes if he dies or is dismissed.
- The dialog is a vanilla event screen built on the fly. Each screen shows brother portraits (`Characters`) and an
  icon list (`List`, vanilla stat icons, vanilla event green/red text colours): the brother page lists level,
  background and price; the attribute page lists all 8 attributes with current value, estimated gain and a
  "chosen" mark; the confirm page shows before/after, cost, days and the -25% warning. The drill master lines
  are picked at random from `training_grounds/game.nut`.
- When a brother finishes, a notice is queued and shown as a one-screen event with his portrait and the gains.
  It is fired from a hook on `event_manager.update` behind `canFireEvent`, so it waits for the next quiet moment
  on the world map. Queued notices are not saved: quitting before it shows loses the notice, not the gain.

## Limits
- The game does not store a brother's starting roll. It is estimated as the base value minus the expected
  level gains (using his talent stars), kept inside the range his background allows. Exact for level 1
  brothers, close otherwise. Buttons say "about +N".
- Start ranges are read from the background plus vanilla defaults. Mods that change start rolls
  (Legends does) can make the maximum differ.
- Each attribute can be raised once per brother (flag `tg_max_<Stat>`).
- Removing the mod while a brother is training breaks loading that save (unknown skill).
- The building has its own picture (day and night, 410x275, `mod/gfx/ui/settlements/`). The tooltip icon is still the vanilla `vet_hall` icon.
- Tooltips, the event layout (portraits, icon lists, how many list rows fit), the completion notice and the -25% display are unverified in game.

## Tests
`sq tests/test_logic.nut` (any Squirrel 3.x interpreter) checks the arithmetic.
`SQ=<sq> python build.py` syntax-checks every script before zipping.

## Credits
- Building art (`tg_training_grounds.png`, `tg_training_grounds_night.png`) is AI-generated with fal: the day image with FLUX schnell (`fal-ai/flux/schnell`), the night variant with Nano Banana 2 edit, then cut out and scaled to 410x275 with `um sprite`. No vanilla art is included.
- Built with AI assistance (Claude, Anthropic) as part of the universal-modder toolkit. Code review in a
  real game is still pending, so treat it as untested.
- Relies on Modern Hooks and MSU by the MSU team, and on Battle Brothers by Overhype Studios.
- Vanilla scripts were read for reference (decompiled locally with bbkit / nutcracker). No game files or
  decompiled code are included.
