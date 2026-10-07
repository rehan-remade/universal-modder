---
kind: game
title: 'Squirrel mod via Modern Hooks and MSU: a Training Grounds town building'
game: Battle Brothers
games_also: []
game_version: 1.5.2.3 (Steam 365360)
platform: windows
engine: native
route: loader-api
tools:
- Modern Hooks 0.6.0
- MSU 1.9.0
- bbkit v0.1.3 (nutcracker, bbsq, sq.exe 3.0.7)
- fal (FLUX schnell, Nano Banana 2 edit)
anti_cheat: none (single-player)
status: in-progress
agents:
- Claude Code (Sonnet 5.5)
humans: []
date: '2026-10-07'
links:
- https://github.com/MSUTeam/MSU/wiki
- https://github.com/Enduriel/bbkit
tags:
- squirrel
- modern-hooks
- msu
- town-building
- event-screen
---
# Squirrel mod via Modern Hooks and MSU: a Training Grounds town building

A mod that adds a "Training Grounds" building to Battle Brothers towns. The player picks a brother and three
attributes; the brother is weakened for a few days, then the chosen attributes are raised. The building, the
click and the wizard screens were run in the real game and debugged from `log.html`. The stat boost itself and
save/load mid-training were **not** verified in game yet.

## Setup
- Battle Brothers 1.5.2.3 (Steam), Windows. The engine is C++ with embedded Squirrel 3 scripts and a Coherent UI front end, so the key is `native` but the real route is Squirrel. Mods are zips dropped in `<game>/data/`.
- Already installed in the test setup: Modern Hooks 0.6.0, MSU 1.9.0, Legends 19.4.22. The mod needs only the
  first two. Versions of Modern Hooks come from the zip name; its Nexus page returned 403 for us.
- bbkit v0.1.3 gives `nutcracker` (decompile `.cnut`), `bbsq` and a standalone `sq.exe` (Squirrel 3.0.7).
  Keep the decompiled vanilla scripts outside any repo (we used a folder in the user profile, about 1700 files).

## Route and why
Loader API: a Squirrel mod zip on Modern Hooks plus MSU. No native code, loaders were already present, and
the community uses the same route. `um scan` calls the game "unknown native engine, no loaders", which is
wrong; the native playbook does not apply.

## How the game works (what we had to learn)
- Vanilla scripts live compiled in `data_*.dat`. Mods add or override scripts by path inside their zip
  (`scripts/...`) and art as `gfx/ui/<path>.png`, referenced as `ui/<path>`. No registration step.
- Town buildings inherit `scripts/entity/world/settlements/buildings/building` (fields ID, Name, UIImage,
  UIImageNight, Tooltip; `onClicked(_townScreen)`). `settlement.m.Buildings` is a 6-slot array and
  `getUIInformation` builds the slot list for the UI; `onSlotClicked(_i, _townScreen)` dispatches the click.
  We hooked those two instead of adding a class to the array, so saves never reference a mod class there.
- A brother's stats are `player.getBaseProperties()` (Hitpoints, Bravery, Stamina, Initiative, MeleeSkill,
  RangedSkill, MeleeDefense, RangedDefense). The starting roll is NOT stored: `m.Attributes` holds only
  pending level-up rolls, so a start roll can only be estimated (current base minus expected level gains).
- Per-brother state goes in a skill (we used `effects_world`): it saves with the brother and disappears with
  him. `*Mult` fields in `onUpdate` apply a percentage penalty; `onNewDay` counts days.
- Dialogs use the vanilla event screen: `World.State.showEventScreenFromTown(event)`.
- Settings use MSU `addRangeSetting` on a mod page.

## Build steps
1. Source in `examples/battle-brothers-training/` of this repo, build with `python build.py` (zip in `dist/`).
2. Copy the zip into `<game>/data/`, restart the game (the zip is read at start only).
3. Syntax check every `.nut` with `sq -c file.nut -o NUL`. It writes `out.cnut` into the current directory;
   delete it before committing.

## Verification
The oracle is `Documents/Battle Brothers/log.html`. Strip the tags and grep for `Script Error`,
`Unable to open file` and your own `logInfo` lines. Each restart gave a fresh log, and every bug below was
found from it. Verified in game: mod loads, building appears, click reaches our code, wizard buttons show.
Not verified: the boost applying after the days pass, the -25% showing, save/load mid-training.

## Gotchas
1. **Symptom.** Clicking the building does nothing; log: `the index 'EventLog' does not exist`.
   **Cause:** `Tactical.EventLog` only exists during battles. **Fix:** on the world map use `logInfo` (vanilla
   never writes to an event log there).
2. **Symptom.** Log spam `Unable to open file "gfx/ui/settlements/<name>_b.png"`. **Cause:** the town UI
   also requests a `_b` variant of every building image. **Fix:** ship `<name>_b.png` (and the `_night_b`
   one) next to the normal files; plain copies work.
3. **Symptom.** Click on a building gives no feedback. **Cause:** our `onClicked` returned early at night.
   **Fix:** do not gate on `World.getTime().IsDaytime` without a message.
4. **Symptom.** Event screen shows only one button and Leave cannot be reached. **Cause:** the button area is
   a small fixed footer; many buttons overflow. **Fix:** at most 5 buttons per screen (3 choices, a cycling
   "more" button, Leave or Back).
5. **Symptom.** Pressing any option does nothing; log: `comparison between 'table' and '0'` in
   `event.processInput`. **Cause:** a button's `getResult` must return a screen ID string (or 0 to close).
   Returning a screen table crashes the check even though `getScreen` accepts tables. **Fix:** store the new
   screen in `m.Screens` under a fresh ID and return the ID.
6. **Symptom.** `um scan` reports the wrong engine. **Cause:** no Squirrel detection. **Fix:** ignore it, check
   `data/` for existing mod zips and `log.html` for "Modern Hooks registered".

## Assets
Building art: FLUX schnell through `um fal` (best of 3, roughly $0.06 total with the night variant made by an
image edit), cut out and fitted to the vanilla building size 410x275 with `um sprite`. It came out brighter and
more painterly than vanilla. Credits are in the mod README.

## Cost and time
About two hours of sessions, mostly bug cycles through the in-game log; art about $0.06.

## Open questions
- What the `_b` image is for (hover state?). We shipped plain copies.
- Real in-game behaviour of the stat boost, the -25% penalty display and save/load.
- A way to read a brother's true start roll; the mod estimates it and labels gains "about +N".
