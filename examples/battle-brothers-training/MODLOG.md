# MODLOG: Battle Brothers Training Grounds (Steam 365360)

## Recon (2026-10-07)
- Game is C++ with embedded Squirrel 3 scripts (.cnut inside data_*.dat zips) and a Coherent UI front end. No anti-cheat.
- Installed in data/: Modern Hooks 0.6.0, MSU 1.9.0, Legends 19.4.22 (not a dependency of this mod), other mods.
- Saves: Documents/Battle Brothers (OneDrive-synced).
- Backup before any modded launch: `um backup create` -> name battle-brothers-saves, zip at
  `%USERPROFILE%\.universal-modder\backups\battle-brothers-saves\20261007-132219.zip` (8 files, 17.9 MB).
  Restore with `um backup restore`.

## Route
Modern Hooks (`::Hooks.register`, `mod.hook(path, function(q){...})`) + MSU settings. Zip with `scripts/` and a
private `training_grounds/` include folder at the root, like MSU does.

## Tools (outside the repo, in a user folder)
- bbkit v0.1.3 release zip (Enduriel/bbkit): `adams_kit/nutcracker.exe`, `bbsq.exe` (decrypt .cnut), `sq.exe` (Squirrel 3.0.7 compiler/interpreter).
- Extract data_001.dat (zip), `bbsq -d` the .cnut files (batch with xargs, argument list is limited), then `nutcracker x.cnut > x.nut`.
- sq.exe doubles as the interpreter for the pure-logic test.

## Vanilla facts found (names)
- Buildings: `scripts/entity/world/settlements/buildings/building` (m.ID/Name/UIImage/Tooltip, onClicked(_townScreen)).
  Vanilla training hall = `training_hall_building` -> `_townScreen.showTrainingDialog()`.
- `settlement.m.Buildings` has 6 slots, saved by class-name hash (so a mod building stored there would tie saves to the mod).
  `settlement.getUIInformation()` builds `Slots`; `settlement.onSlotClicked(_i, _townScreen)` dispatches clicks.
  Coastal towns force the port into slot 3 (settlement.nut ~1198).
- Tooltips: `tooltip_events.general_queryUIElementTooltipData(_entityId, _elementId, _elementOwner)`.
- Brother base stats: `player.getBaseProperties()` keys Hitpoints, Bravery, Stamina, Initiative, MeleeSkill, RangedSkill, MeleeDefense, RangedDefense.
- Start roll = `character_background.buildAttributes()`: defaults (HP 50-60, Res 30-40, Fat 90-100, Init 100-110, MSk 47-57, RSk 32-42, MDef 0-5, RDef 0-5) + `background.onChangeAttributes()`.
- Level-up gains are NOT recorded. `player.m.Attributes[i]` holds only pending pre-rolled gains (10 of them, then +1 each).
  `Const.AttributesLevelUp` = per-stat min/max, talent stars shift the roll. `player.m.LevelUps` = unspent level-ups.
  => start roll must be estimated (see logic.nut).
- Status effects: `scripts/skills/skill`, hooks `onUpdate(_properties)` (use *Mult fields), `onNewDay()` (called from asset_manager per brother),
  own `onSerialize/onDeserialize`. `getFlags().set/has` on a brother is saved.
- Dialog: `World.State.showEventScreenFromTown(event)`; event buttons come from `ActiveScreen.Options`; `getResult` may return a screen table;
  `setScreen` resets `Characters`, so portraits are pushed in the screen's `start`. `World.Events.m.ActiveEvent` must be set for button input.
- Squirrel gotcha: `base` is a keyword.

## Design decisions
- Building not stored in `m.Buildings` (no save-hash dependency), shown in the first free slot via hooks.
- Training state is a skill on the brother (saved with him; dies with him).
- Dialog via event screen wizard (no custom JS).

## Verified
- All scripts compile under Squirrel 3.0.7 (`sq -c`); arithmetic tests pass (`tests/test_logic.nut`); zip builds.
## Not verified (needs the game)
- Everything that runs inside the game: hook loading, slot image, tooltip, event wizard flow, menu-stack pop, penalty display, save/load of the effect, the log lines.
- Next step: user launches the game with a backup in place, enters a village with a free slot, uses the building, checks `log.html` in Documents/Battle Brothers.
