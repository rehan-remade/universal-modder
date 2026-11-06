---
kind: game
title: 'Complete Edition after a Steam re-update: 1.0.8.0 mod stack silently not loading, infinite loads in TBoGT'
game: Grand Theft Auto IV
games_also: []
game_version: 'Steam Complete Edition 1.2.0.59 (app 12210, buildid 14009960)'
platform: windows
engine: rage
route: loader-api
tools:
- GTAIV.EFLC.FusionFix 5.0.1
- Ultimate ASI Loader 9.7.4
- ZolikaPatch 7.65 (disabled)
- IV-SDK .NET (disabled)
anti_cheat: none
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-25'
links:
- https://github.com/ThirteenAG/GTAIV.EFLC.FusionFix
- https://github.com/ThirteenAG/Ultimate-ASI-Loader
tags: [troubleshooting, infinite-loading, fusionfix, zolikapatch, downgrade, achievements, tbogt, eflc]
---
# Complete Edition after a Steam re-update: 1.0.8.0 mod stack silently not loading, infinite loads in TBoGT

> A player replaying The Ballad of Gay Tony missions from the phone (going for gold) hit an infinite load
> after finishing the first underground fight club mission. The mod stack had been built for a downgraded
> 1.0.8.0, then Steam put the game back on Complete Edition 1.2.0.59, and an earlier "launch fix" had renamed
> the ASI loader to `xlive.dll`, which CE never loads, so no mod was running at all. With FusionFix alone
> on CE plus a 30 FPS cap, the player reports the mission now completes. No agent-run in-game test was done.

## Setup
- Steam GTA IV: The Complete Edition, `GTAIV.exe` 1.2.0.59, Windows 11, i5-11400H (12 threads), GTX 1650.
- Found in the game folder: FusionFix 5.0.1 in `plugins\` (+ its `update\` folder), ZolikaPatch 7.65,
  IV-SDK .NET with the ImmersiveIV script, Ultimate ASI Loader 9.7.4 present twice (as `xlive.dll` and as
  `dinput8.dll.asibak`), several `*.asi.ce_disabled` leftovers (AdvancedHook, GFWLProtectionDisabler,
  aCompleteEditionHook), and `commandline.txt` with `-nomemrestrict -norestrictions -availablevidmem 3072`.
- The `IVSDK\` folder only had `1070.ini` and `1080.ini` offset files, and FusionFix.ini comments mentioned
  1.0.8.0. Both were clues that the stack targeted a downgrade. The Steam appmanifest and file dates showed a
  fresh re-download the evening before.

## Route and why
Stay on CE with FusionFix only. Downgrading to 1.0.8.0 would bring ZolikaPatch and IV-SDK back, but the
player's goal was Steam achievements. CE has them natively. On 1.0.8.0 they need the downgrader's
achievements enabler, and forum reports say it is unreliable once a mod stack is present. Reports also
disagree on whether the episodes survive a downgrade. FusionFix itself now targets CE: its README says only
the Complete Edition is fully supported, and 1.0.7.0/1.0.8.0 need its Legacy Addon on top.

## How the game works (what we had to learn)
- CE 1.2.0.59 `GTAIV.exe` imports `DINPUT8.dll`, `VERSION.dll`, `WINMM.dll` and `d3d9.dll`, but **not
  `xlive.dll`** (GFWL was removed). An ASI loader named `xlive.dll` is just never loaded on CE. Grepping the
  exe for `*.dll` names is enough to check.
- ZolikaPatch 7.65 refuses CE: on launch it opens its "downgrading" page in the browser and the game does
  not start. Its own page lists 1.0.8.0, 1.0.7.0, 1.0.4.0 and 1.0.0.0 as the supported versions.
- IV-SDK .NET reads per-version offset files (`IVSDK\<version>.ini`). With only 1070/1080 present it does not
  support CE.
- FusionFix supports CE. Its `[FRAMELIMIT]` has `FpsLimit`, `LoadingFpsLimit`, `MinigamesFpsLimit` and
  `UnlockFramerateDuringLoadscreens`. In 5.0.1 (`source/framelimit.ixx`):
  - the ini's `FpsLimit` is only used when the in-game FPS Limiter is set to Custom; its other settings are
    fixed values, and Off means no cap;
  - a separate loading-screen limiter is always on: `LoadingFpsLimit`, default 30 and never below 30, which
    the shipped ini says is there "to avoid game freeze on loading (e.g. Off Route mission)".

## Build steps
1. Back up saves. CE keeps them in `Documents\Rockstar Games\GTA IV\Profiles\<id>` (PCGamingWiki), so
   `um backup create "%USERPROFILE%\Documents\Rockstar Games\GTA IV\Profiles" --name gta4-ce-saves`. The
   `%LOCALAPPDATA%\Rockstar Games\GTA IV` folder holds the settings and the saves from the 1.0.8.0 days
   (`um backup create "%LOCALAPPDATA%\Rockstar Games\GTA IV" --name gta4-settings`). Copy
   `commandline.txt`, `ZolikaPatch.ini`, `plugins\GTAIV.EFLC.FusionFix.ini` somewhere safe.
2. Loader: rename `dinput8.dll.asibak` → `dinput8.dll` and `xlive.dll` → `xlive.dll.off` (one loader, under
   a name CE actually imports).
3. Disable non-CE plugins: `ZolikaPatch.asi` → `.off`, `IVSDKDotNet.asi` → `.off` (this also drops its
   scripts).
4. `commandline.txt`: keep only `-availablevidmem 3072`, and drop `-norestrictions` / `-nomemrestrict`.
5. FusionFix.ini: `FpsLimit = 30` and `UnlockFramerateDuringLoadscreens = 0`, and set the in-game FPS Limiter
   to Custom (the ini value is ignored otherwise; picking 30 from the menu's list also works), so the cap is
   always 30 FPS.

## Verification
- Before step 2, the in-game FPS was 144 (uncapped, desktop refresh). That was the giveaway that FusionFix's
  limiter, and FusionFix itself, wasn't loaded. Windows Application log had an `APPCRASH` for `GTAIV.exe`
  1.2.0.59, `c0000005` at offset `0x3be0`. The cause wasn't diagnosed further.
- After step 2 alone, ZolikaPatch loaded and opened the downgrading page instead of starting the game.
- After step 3, the game starts. The player reports the fight club mission now finishes and "it seems fixed".
  Whether achievements pop wasn't confirmed by the agent.

## Gotchas
1. **Edits to FusionFix/ZolikaPatch ini have no effect, FPS is uncapped.** **Cause:** the ASI loader is named
   `xlive.dll`, which CE doesn't import, so nothing loads. **Fix:** name it `dinput8.dll`. Check by looking
   for the FPS cap or the FusionFix entries in the game's settings menu.
2. **Game won't start, browser opens zolika1351.pages.dev/mods/ivpatch/downgrading** (a 404 page as of
   October 2026). **Cause:** ZolikaPatch on CE 1.2.0.59. **Fix:** disable ZolikaPatch on CE (FusionFix covers
   the important fixes), or downgrade.
3. **A previously working modded install breaks overnight.** **Cause:** Steam re-downloaded or updated the
   game back to CE while the mods were for a downgrade. **Fix:** check `GTAIV.exe` FileVersion before
   touching configs, then pick mods for that version.
4. **Earlier "fixes" can hide the real problem.** Here someone renamed the loader so the game would launch,
   which disabled all mods without anyone noticing. Look for `*.asibak`, `*.ce_disabled` and backup folders
   in the game dir.
5. **Overlapping ZolikaPatch options.** If both run (on a downgrade), `NoLoadingSleep`, `NoPhysicsSleep`,
   `HighFPSSpeedupFix`, `HighFPSBikePhysicsFix`, `SpeedupBugFix` overlap FusionFix's frame and loading
   handling. `TryToSkipAllErrors` can turn a crash into a hang. They were turned off here as a precaution,
   without a proven effect.

## Assets
None.

## Cost and time
One session, about an hour of back-and-forth, no API spend.

## Open questions
- Exact TBoGT mission name. The player described it as "the first one in the underground fight club".
- Whether the infinite load was caused by the missing fixes, high FPS or the non-CE mod stack. All three were
  changed at once. High FPS is the likeliest: FusionFix's always-on loading limiter exists to stop freezes on
  load screens, and with FusionFix not loaded nothing capped them. It wasn't isolated.
- Whether 60 FPS is also stable for this mission on CE with FusionFix loaded.
