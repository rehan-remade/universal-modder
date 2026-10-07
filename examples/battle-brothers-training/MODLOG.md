# MODLOG: Battle Brothers (steam 365360)

## Recon (2026-10-07, read-only)
- Path: T:\All\Steam\steamapps\common\Battle Brothers (data\ holds data_*.dat, gfx, mod zips)
- Saves: C:\Users\alexs\OneDrive\Documents\Battle Brothers (OneDrive-synced; back up before modded launches)
- um scan said "unknown native engine, no loaders": wrong. Game is C++ with embedded Squirrel scripts (.cnut in data_*.dat), Coherent UI front end.
- Already installed in data\ (zips, never unzipped): Modern Hooks 0.6.0 (nexus 685), MSU 1.9.0 (nexus 479, GitHub MSUTeam/MSU, latest tag 1.9.0), Legends 19.4.22 + assets, Faster mod, More Weapon Skins, Dynamic Battle Stats, Settlement Situation Tooltip, Smart Recruiter, ~mod_msu_launcher.zip.
- Anti-cheat: none (single-player).
- KB: no notes for Battle Brothers or Squirrel.

## Route
Drop-in mod zip in data\ using Modern Hooks (Hooks.register / ::Hooks.QueueBefore/After, preserves vanilla scripts, no overwriting) plus MSU for settings/keybinds/skill framework. Mod zip layout: scripts/..., gfx/..., plus a mod_*.nut registering the mod. Docs: https://github.com/MSUTeam/MSU/wiki . Vanilla scripts need decompiling (cnut -> nut) with nutcracker (DamianXVI) / bbkit (https://github.com/Enduriel/bbkit, last push 2021) / TaroEld massdecompile. Examples: https://github.com/jcsato (sato mods).

## Sources
- https://www.nexusmods.com/battlebrothers/mods/479 (MSU)
- https://www.nexusmods.com/battlebrothers/mods/685 (Modern Hooks; fetch blocked 403, version from local zip name)
- https://github.com/MSUTeam/MSU/releases/tag/1.9.0
- https://github.com/Enduriel/bbkit
- https://github.com/jcsato/sato_men_at_arms_mod

## Journal
- Nothing installed, no files or saves touched.
- TODO: verify Modern Hooks current version and install steps on Nexus; check log.html in Documents\Battle Brothers for loaded mods.

## 2026-10-07 Design (user request, assumptions pending confirmation)
Idea: "Ordeal/Hard training" action at a settlement (or Legends camp). Brother gets -25% stats for N days,
then 3 stats get their base (starting) value raised to the background's max roll; level-up gains stay on top
(example: base 47, +13 from levels = 60 -> base 56, +13 = 69).
Route: Squirrel zip on Modern Hooks 0.6.0 + MSU 1.9.0 (both already in data\). Decompile of vanilla .cnut not yet done (needs download permission).
Open: location (town building vs Legends camp), duration, cost, which 3 stats, what "56" is (bg max?).
