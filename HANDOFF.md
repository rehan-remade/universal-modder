# Handoff: Battle Brothers modding

Goal: make Battle Brothers mods (Squirrel zips on Modern Hooks + MSU). First mod, "Training Grounds", is built.

Done (branch task/battle-brothers, local only, not pushed, no PR):
- Mod: examples/battle-brothers-training/ (town building, wizard on the vanilla event screen, -25% then
  raised start stats, MSU settings, own fal art). Zip: dist/mod_training_grounds-1.0.0.zip, copied to
  T:\All\Steam\steamapps\common\Battle Brothers\data\.
- Field note: knowledge/games/battle-brothers/squirrel-mod-via-modern-hooks-and-msu-a-training-grounds-tow.md
  (setup, how the game works, 6+ numbered gotchas). Read it before any new Battle Brothers mod.
- Tested in game by the user: building shows, wizard works. Not confirmed: boost after 5 days, -25% display,
  save/load mid-training, the richer screens (last commit 10473b2).

Next: start the new mod from the example folder. Loop: bin/um kb search "Battle Brothers", then
log.html (Documents\Battle Brothers) is the oracle after each restart of the game.
Open: PR for the example + note (needs user OK; mark note verified first); status in note is in-progress.

Key files / places:
- Vanilla decompiles + tools (outside repo, user PC only): C:\Users\alexs\bb-decomp (src\scripts, kit\adams_kit\sq.exe)
- Saves backup: C:\Users\alexs\.universal-modder\backups\battle-brothers-saves\20261007-132219.zip
- Game 1.5.2.3, Modern Hooks 0.6.0, MSU 1.9.0 installed in data\.

Not carried over: fal key (ask the user again, env var only, never in files); permission to write into the
game's data\ folder or to launch/drive the game (ask again each session).
