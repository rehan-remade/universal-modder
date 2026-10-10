---
kind: game
title: "Jevil fight practice mode for DELTARUNE Chapter 1"
game: "DELTARUNE"
games_also: []
game_version: "Steam Chapters 1-5 release (Chapter 1 data.win, GameMaker 2.3+, bytecode 17, VM), Windows 10"
platform: windows
engine: gamemaker
route: data
tools: ["UndertaleModTool CLI 0.9.2.0"]
anti_cheat: "none (single-player, DRM-free runner, no steam_api.dll)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ['@italalaev']
date: 2026-10-10
links: []
tags: [gamemaker, data.win, undertalemodtool, gml, boss-practice, jevil, input-blocking, save-isolation, csx]
---

# Jevil fight practice mode for DELTARUNE Chapter 1

> A practice menu for the Jevil fight, injected as GML into Chapter 1's `data.win` with an UndertaleModTool C# script.
> It warps to the fight from any save, retries on defeat, can force any of Jevil's 14 attacks, starts at any phase, and
> tracks his TIRED (pacify) counters. It runs from a copy of the install with its own save folder. Every feature was
> verified in the real game with screenshots of the running window.

## Setup
- DELTARUNE from Steam: `steamapps/common/DELTARUNE`. `DELTARUNE.exe` plus a launcher `data.win` (chapter select),
  then `chapterN_windows/data.win` for chapters 1-5, with music in a shared `mus/` folder at the root.
- Chapter 1 `data.win`: GMS2, bytecode 17, **VM**. UTMT `info` reports "Is YYC - False" and a non-empty `CODE` chunk.
  See [the YYC vs VM check](../../techniques/gamemaker-yyc-vs-vm-check-the-code-chunks-before-trusting-th.md).
- UndertaleModTool CLI 0.9.2.0 (`UTMT_CLI_v0.9.2.0-Windows.zip`), self-contained, so no .NET install is needed.
- `um` didn't run here (no Python on the machine), so recon used UTMT `info`/`dump` and a chunk walk in PowerShell.

## Route and why
Data route: `UndertaleModCli load <data.win> -s mod.csx -o <out>`, where the script uses `CodeImportGroup`. It adds one
new global script with all the mod's functions (`QueueReplace("gml_GlobalScript_<name>", code)` with
`AutoCreateAssets = true`), plus a few `QueueAppend`/`QueueFindReplace` hooks. The decompiler round-trips this game
cleanly, so find/replace on decompiled lines is reliable. The bundled sample `HeCanBeEverywhere.csx` (a Jevil mod)
is a good API reference.

Distribution is "bring your own game": ship the `.csx` and `.gml`, plus an installer that copies the user's install and
patches the copy. Never ship a modified `data.win`.

## How the game works (what we had to learn)
- **Persistent controller:** `obj_time` exists all game. Its Begin Step polls the keyboard/gamepad into
  `global.input_pressed/held/released[0..9]`. Everything else reads input through helpers like `button1_p()` and
  `left_h()`, which read those arrays. Appending to `obj_time` End Step (logic) and Draw GUI (overlay) gives a mod a
  global tick.
- **Jevil:** the battle object is `obj_joker` (monstertype 20), encounter **25**, room **`room_cc_joker`**. The door from
  `room_cc_prison_prejoker` uses `global.entrance = 1` (marker A). `obj_jokerbattleevent` runs the room's intro and
  battle start. It only runs while `global.flag[241] < 6` (5 = door open, 6 = beaten, 7 = after/spared). If
  `global.tempflag[4] == 1` it plays the game's own short re-entry intro, which makes a fast retry loop.
- **Warping in from anywhere:** set `darkzone = 1`, the party `char[0..2] = 1, 2, 3`, `flag[241] = 5`, `tempflag[4] = 1`,
  `entrance = 1`, `interact = 0`, `fighting = 0`, refill `hp[]`. Then create `obj_persistentfadein` and
  `room_goto(room_cc_joker)`. This worked from a Card Castle save and from an early Forest save.
- **Attack choice:** `obj_joker` Step picks `jattack` (0-13) from a `jturn` script. The first turns are fixed, then there
  are random picks at jturn 4/9/14/19. Phases advance at 80/60/40/15% HP. `event_user(5)` spawns an
  `obj_dbulletcontroller` with a `type` per attack. Forcing an attack = override `jattack` just before the line that
  checks for "all-target" attacks (2, 5, 9, 13, 15).
- **TIRED / pacify:** Pacify spares when `global.monsterstatus[i] == 1`. Jevil gets there two ways:
  1. `hypnosiscounter`: +1 per Hypnosis ACT (50% TP), +0.5 per Pirouette (20% TP). The act performed while it is
     already >= 9 sets TIRED.
  2. At the start of his turn: `jturn >= 19` and `turns >= 29 - hypnosiscounter`, where `turns` counts attacks done
     (incremented in `event_user(5)`). Hypnosis also lowers the phase-change turn thresholds (5/11/17 minus count).

  A phase preset therefore has to set `turns` as well as `jturn`/HP, or the pacify timer is wrong.
- **Invincibility for free:** `scr_damage` already skips damage when `global.chemg_god_mode` is set. It's a leftover
  debug hook.
- **Game over:** `scr_gameover` → `room_gameover`. A guarded early return at its top that calls the warp gives instant
  retry.
- **Saves:** `%LOCALAPPDATA%\<GEN8 Name>`, where Name = "DELTARUNE". Changing `Data.GeneralInfo.Name` in **every**
  `data.win` of the copy isolates its saves.
- **Boot:** `obj_initializer2` Step goes to `room_legend` (story + title) when `filech1_3/4/5` exist (Chapter 1
  completed), otherwise straight to the file menu (`PLACE_MENU`).
- **Chapter launch:** the launcher calls `game_change("/chapterN_windows", "-game data.win launcher switch_N returning_N")`.
  A chapter can be started directly from its folder with `..\DELTARUNE.exe -game data.win launcher`.

## Build steps
1. Copy the whole install somewhere else and keep a pristine copy of `chapter1_windows/data.win`.
2. `UndertaleModCli load pristine.win -s JevilPractice.csx -o chapter1_windows/data.win -f`.
3. For the launcher `data.win` and chapters 2-5: `UndertaleModCli load X -s SaveFolder.csx -o Y`, where the script
   sets `Data.GeneralInfo.Name`.
4. Launch: cwd = `chapter1_windows`, then `..\DELTARUNE.exe -game data.win launcher`.

## Verification
- After each build, decompiled the injected entries back out with `dump -c`.
- Launched the copy and drove it with keyboard input, checking screenshots of the window:
  - the warp entered the fight from two different saves;
  - a forced attack (8 Carousel, 10 Clubs) was used on turns that would normally pick something else;
  - a party wipe and no-hit mode both restarted the attempt at full HP;
  - the phase preset showed a ~40% HP bar;
  - the tracker went "Timer: 10 turns" → 9 after an attack, and Hypnosis 0/9 → 1/9 with the timer −1;
  - the input filter: holding an arrow with the menu open didn't move the battle cursor.
- Music: checked that the game holds `mus\joker.ogg` open during the fight (opening the file exclusively failed).
- The real install's `data.win` hashes and the real save folder were unchanged afterwards.
- **Not verified:** Pirouette's +0.5 in the tracker (no TP for it in that run), gamepad input with the menu open,
  and the attack names, which are labels inferred from the bullet objects.

## Gotchas
1. **No music in the modded copy.** **Cause:** `snd_init` loads `mus/` relative to the working directory unless
   `global.launcher` is set, and that only comes from a `launcher` command-line argument. **Fix:** pass `launcher`
   after `-game data.win`.
2. **The phase preset only worked from the overworld, not when restarting mid-fight.** **Cause:** the warp and the
   phase setup ran in the same frame, before `room_goto` takes effect, so the setup hit the *old* battle's `obj_joker`.
   **Fix:** a two-stage flag. Wait until the old `obj_battlecontroller` is gone, then apply to the next one.
3. **A pause menu built with `instance_deactivate_all` breaks things and blacks out the screen.** `obj_time`'s Begin
   Step dereferences `obj_gamecontroller`, so that must stay active. The battle visuals are instances, so the screen
   goes black. **Better:** don't pause. Zero the `global.input_*` arrays at the end of `obj_time`'s Begin Step while
   the menu is open, and keep zeroing until the menu keys are released. That way the confirming Z/arrow doesn't leak
   into the battle menu.
4. **The `-l "C# code"` argument loses its inner quotes under Windows PowerShell 5.1.** It fails with CS0103 "name
   DELTARUNE_JEVIL does not exist". **Fix:** put the line in a tiny `.csx` and pass `-s`.
5. **A copied save folder includes a completed Chapter 1, so the copy always plays the legend intro.** **Fix:**
   find/replace the `room_legend` choice in `obj_initializer2` Step with `PLACE_MENU`.
6. **Packaged-app path redirection:** when the agent runs inside the MSIX-packaged Claude desktop app, files written
   under `%APPDATA%\Roaming\Claude\...` really live under `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\...`.
   Tools launched from the agent see the virtual path, but the user's Explorer doesn't. Build user-facing installs in
   a normal folder.
7. **Moving the game window:** the GameMaker window started at (-25600, -25600), i.e. hidden off-screen. Restore it
   with `MoveWindow` before taking screenshots.

## Assets
None. The mod only adds text overlays drawn with the game's own "main" font.

## Cost and time
One session, roughly 1.5 hours wall-clock, mostly in-game verification and five rounds of user feedback.

## Open questions
- A gamepad-friendly menu key (the menu only uses keyboard checks).
- Hard-confirming the attack names, e.g. by recording each forced attack.
- Whether the same approach carries over to Chapter 2's secret boss (Spamton NEO), which has a similar structure.
