---
kind: game
title: "Mindustry 160.7: a reproducible JSON and JavaScript homing lab on macOS"
game: Mindustry
games_also: []
game_version: "160.7, official itch.io macOS desktop distribution"
platform: macos
engine: java
route: loader-api
tools: ["Universal Modder 0.2.0", "Mindustry built-in JSON and JavaScript mod API"]
anti_cheat: "Single-player local test only; no anti-cheat modifications or multiplayer testing"
status: released
agents: ["Codex (GPT-6)"]
humans: ["B.Liu (liubrain39)"]
date: 2026-10-09
links:
  - https://mindustrygame.github.io/wiki/modding/1-modding/
  - https://github.com/Anuken/Mindustry/tree/v160.7
  - https://github.com/liubrain39/modlab-homing-lab
  - https://modlabguides.online/workshop/mindustry-homing
tags: [mindustry, java, json, javascript, homing, macos, verification, backups]
---

# Mindustry 160.7: a reproducible JSON and JavaScript homing lab on macOS

A small released mod compares straight and guided projectiles in the real desktop engine. The useful
lesson is to use the game's supported JSON/JavaScript API even when a generic Java scan suggests bytecode
patching, and to make both installation and the comparison reproducible.

## Setup

- Mindustry **160.7**, downloaded from the author's [official itch.io page](https://anuke.itch.io/mindustry).
  The author provides a free download; Steam is not required for this case.
- macOS **15.7**, Apple M1 Max. The official x86_64 app runs under Rosetta and bundles Java **25.0.1**.
  This describes the tested machine, not a requirement that every reader install that Java version.
- Universal Modder **0.2.0**, revision `8370faa8e114baf33acdb23079aff552a7728c4b`.
- ModLab Homing Lab **0.1.0**, original MIT-licensed code and simple geometric turret sprites.
  No game binaries or extracted game assets are distributed.
- A separate clean game-data profile was restored from a backup before the ZIP installation test.

## Route and why

**Loader API:** Mindustry's built-in mod system loads `mod.json`, JSON content definitions and JavaScript
from the mod ZIP. No external loader, bytecode patch, native injection, paid asset or API key is needed
to run this example. Universal Modder knowledge search returned no Mindustry note before this contribution.
The generic scan classified the bundle as Java, found no installed loader and suggested Java patching;
that output did not recognise Mindustry's supported mod interface. Reviewing the official game documentation
and source supplied the route. Scan output is a hypothesis to check, not proof that no API exists.

## How the game works

- The loader reads `mod.json` or `mod.hjson` at the mod root (it steps into a single top-level folder),
  content from `content/<type>/*.json` or `.hjson`, sprites from `sprites/`, and scripts from `scripts/`:
  a lone `.js` file there runs as the main script, otherwise `scripts/main.js`.
- `content/blocks/baseline.json` and `homing.json` define two `ItemTurret` blocks with a copper-ammo
  `MissileBulletType`. That type's constructor sets `homingPower = 0.08`, so the straight lane has to set
  `homingPower: 0` explicitly. The mod name prefixes content identifiers: `modlab-homing-baseline` and
  `modlab-homing-homing`.
- Keep bullet speed **2.7**, damage **12**, lifetime **105 ticks**, reload **70 ticks** and no splash
  identical. `homingPower` changes from **0** to **0.08**; colours are labels.
- `homingRange: 200` is in world units (8 per tile, so 25 tiles). It is measured from the bullet's aim point,
  not from the bullet: a turret passes its target position as the bullet's `aimX`/`aimY`, and
  `BulletType.updateHoming` steers toward the closest target within `homingRange` of that point. Here the
  fixed aim point is the centre of the target's path, so the target is always in range. `homingDelay: 8` is
  simulation ticks. Do not label either value as seconds or tiles without conversion.
- The original helper script makes a temporary local world, supplies ammunition and gives both lanes
  identical scripted moving targets and a fixed aim point. It reads actual turret `totalShots` and counts
  `UnitDamageEvent` events for the corresponding target and bullet owner. It does not invent successful hits.
- The simulation uses `Time.delta`; **1800 simulation ticks** target 30 simulation seconds. Wall time and
  video frame count are not the result's clock.
- The start handler rejects an active network connection and refuses to replace another active world.
  F8 starts/restarts the lab; F9 returns to the menu. The lab does not save a campaign.

## Build and install steps

1. Back up existing game data. For a first test, use a clean profile rather than an existing campaign.
2. Use the [released source and tested ZIP](https://github.com/liubrain39/modlab-homing-lab/releases/tag/v0.1.0).
   The ZIP root must contain `mod.json`, with `content/`, `scripts/` and `sprites/` beside it.
3. In the game choose **Mods → Open Folder**, quit, copy the ZIP into that folder, keep it zipped, and restart.
4. From the main menu select **ModLab Homing Lab [F8]**. Let the 30-second comparison finish. Record both
   launch and damage-event counts; the script writes `modlab-last-run.json` in the game-data directory.
5. For an edit, extract to a new folder, change one value in `homing.json`, and ZIP the files *inside* the
   folder. With the game closed, replace the previous ZIP and rerun. The suggested **0.02** guidance
   experiment is not a verified result.
6. Exit with F9, disable the mod in Mods and restart. For a pre-existing world containing the new blocks,
   recover from the backup made before installing it.

## Verification

The oracle was the actual Mindustry desktop window plus the mod's real engine-event log. A recorded
30-second run produced straight **1 hit / 25 launches** and guided **24 / 25**. Installing the supplied ZIP
on the restored clean profile reproduced **1 / 25** and **24 / 25**. Disabling the mod and restarting removed
the ModLab menu entry. Universal Modder backup restore/diff found zero added, removed or changed files
before the clean-profile launch; publication checking reported zero failures and zero warnings.

- [Machine-readable verification](https://github.com/liubrain39/modlab-homing-lab/blob/main/evidence/mindustry-verification.json)
- [Recorded workshop, installation and recovery](https://modlabguides.online/workshop/mindustry-homing)
- Tested ZIP SHA-256: `4048d28855e299342e2b9123c8b751bb1a09a0ad1909b717fadd639781850b3a`.

These counts are a **controlled steering demonstration**, not normal-game balance, DPS or general AI-agent
quality. The targets have scripted movement and extra health; the turrets have fixed aim. Other operating
systems, multiplayer, independent learner acceptance and the 0.02 guidance experiment were **not tested**.
The recording uses 55 actual window screenshots sampled at approximately 1.5 fps, with repeated frames
encoded at 24 fps and no audio; it is not a native 24-fps gameplay capture.

## Gotchas

1. **The scan suggests patching Java despite the game supporting mods.** **Cause:** the generic scanner
   detects JARs but does not infer every game's built-in content API. **Fix:** inspect the official mod
   documentation and choose the built-in JSON/JavaScript route for this idea.
2. **Mods → Import Mod → Import File does not open a file picker on the tested Mac.** **Cause:** unresolved
   in this session; do not claim a diagnosed OS cause. **Fix:** the verified alternative is Open Folder,
   quit, copy the ZIP, then restart. The Import File route remains unverified.
3. **A repackaged mod has no recognised metadata.** **Cause:** `mod.json` is not at the archive root.
   Mindustry (`Mods.resolveRoot`) steps into a single top-level folder, so one wrapper folder alone still
   loads; it fails when anything else sits next to that folder, such as a `__MACOSX/` folder. **Fix:** ZIP
   the files inside the project folder and inspect the ZIP entries.
4. **A test is described as “homing is 24 times better”.** **Cause:** treating scripted fixed-aim steering
   as ordinary gameplay. **Fix:** publish the controlled setup and both denominators; re-test separate
   sandbox/automatic-targeting behaviour before making game-balance claims.
5. **A demonstration could discard another active world.** **Cause:** loading the lab requires resetting
   the current world. **Fix:** reject networked or unrelated active sessions, start only from the main
   menu, and save/exit another game first. Keep campaign data in the backed-up profile.
6. **An uninstall is called verified without a restart.** **Cause:** checking only that the checkbox
   changed does not test a fresh engine load. **Fix:** disable the mod, restart, and confirm the lab's
   menu item is gone. Back up any existing world using its content.

## Cost and open questions

Running the tested package requires no game purchase, paid assets, API key or coding-agent account.
Editing with a hosted coding agent may incur that service's usual usage cost. This case does not establish
cross-platform support, multiplayer compatibility, or game-balance outcomes. ModLab is an independent
resource, unaffiliated with the Mindustry or Universal Modder maintainers.
