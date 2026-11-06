---
kind: game
title: 'Gameplay mod: bonus phases after majin kills, with an in-VM self-test (r10-mod-system)'
game: Rance X
games_also: []
game_version: '1.04 (Version.txt "1.04"), community English patch 1.04.20, Windows 11, run through Locale Emulator 2.5.0.1'
platform: windows
engine: unknown
route: loader-api
tools: ["r10-mod-system 0.1.1", "alice-tools 0.13.0 (0.11.1 is bundled, see Setup)", "Locale Emulator 2.5.0.1", "Python 3"]
anti_cheat: "none (offline single-player strategy / visual novel)"
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-16'
links: ["https://github.com/nunuhara/r10-mod-system/releases", "https://github.com/nunuhara/alice-tools", "https://github.com/xupefei/Locale-Emulator"]
tags: [gameplay, turn-system, alicesoft-system4, jaf, self-test, hidden-desktop, rance]
---
# Gameplay mod: bonus phases after majin kills, with an in-VM self-test (r10-mod-system)

> A Rance X (Rance 10) mod that gives the player extra quest phases in the Part 1 strategy layer after killing
> majin, before the demon army moves: one kill in a turn gives one extra Mission and one extra Base phase; two
> or more give three extra Base phases. Built as .jaf code injected with nunuhara's r10-mod-system. The rule
> logic passed a 23-check self-test run inside the real game VM at boot; a real play-through to a majin kill is
> not done yet, hence `in-progress`.

## Setup
- Rance X 1.04 with the community English patch 1.04.20, on Windows 11 with a Western system code page.
- r10-mod-system 0.1.1 unpacked into `<game>/Mods` (mods go in its `src/` folder). Its `build.bat` builds
  `Rance10.ain`, `Rance10ModEX.ex`, `Rance10ModCG.afa` and `Rance10Pact.afa` into the game folder. A second
  (quest) mod was installed at the same time and both built together.
- alice-tools: this note was written against 0.13.0, but the r10-mod-system 0.1.1 release zip bundles 0.11.1
  (its `alice-tools\alice.exe` reports `alice-tools version 0.11.1`), and `build.bat` runs that copy unless
  you replace it. Gotcha 1 is the same in both versions.
- A full bytecode listing of the game code (`alice ain dump`, Japanese names), for research only. It's the
  game's code, so it stays outside any repository.
- Locale Emulator 2.5.0.1 to start the game (Gotcha 2).

## Route and why
r10-mod-system compiles your .jaf files into the original .ain with `override` / `super`, so only the hooked
functions change. Rejected: (a) editing the bytecode listing and recompiling the whole game: a huge diff, and
new functions need table work; (b) changing the turn counter to replay or extend turns: about 140 story checks
compare the turn number with constants, so story events would re-fire or be skipped, and there are no turn
banners past 15. Redirecting the phase loop avoids both.

## How the game works (what we had to learn)
- **Part 1 turn loop.** A chapter-1 controller loops over a switch on the current phase and moves on by calling
  the chapter's phase *setter*. Order: turn banner → turn-start events → Preparation (choose, then run one
  quest) → food tickets → Mission (choose, run) → food tickets → Base (choose, run) → turn-end events 1 →
  result screen (enemy advance, human death rate) → turn-end events 2 → turn + 1. These are phases 3 to 16 of
  the game's phase enum; Base ends by setting phase 13. Only the loop calls the setter; loading a save goes
  through the getter.
- **Deadline.** Turn-end events at turns 14 and 15 make Kayblis the Demon King; four fallen regions end the
  game. Time is the scarce resource, so phases that skip the enemy turn are a real reward.
- **Quest lists are rebuilt** each time a choose-phase starts, so sending the loop back to Mission or Base
  offers a fresh, valid choice.
- **Story state.** Flags are a large global int array. The flag *strings* the scripts pass around (such as
  "<name>死亡＝１") are setters handled by one big flag function: passing one changes the story. To test a flag,
  read the array slot that setter writes. "Quest cleared" is a separate, saved set of quest ids.
- **Ground truth for "who died".** The developers left debug functions that print the route state (who died,
  who joined, which shortcut route was taken). They gave the death markers directly. Several first guesses
  from map icons and boss-battle names were wrong: some majin you fight join you, escape, or die off-screen.
- **Saved mod state without changing the save layout.** The quest-history set accepts any string key, is
  saved, and nothing lists or counts it. It is append-only, so counters are stored as numbered keys.
- **File output.** Rance X has no `File2` library. `TextFile` (Create/Write/Close) writes text, with the path
  built from the save-folder getter.

## Build steps
1. Write the mod folder (`source.inc` plus .jaf files). Hook `override void GameChapter1@Phase::set(int value)`:
   when `value == 13` and bonus phases are owed, call `super(8)` (Mission) or `super(11)` (Base) instead.
2. Count kills in the hook: compare the game's death markers with "already counted" keys, grant bonuses, and
   consume each one *before* calling `super`, so a save made inside the bonus phase can't grant it twice. On
   the first run in an existing save, mark kills already made as counted, with no reward.
3. Compile all mods into a scratch copy first, then build into the game with r10-mod-system's `build.bat`.

## Verification
- **Oracle: a boot-time self-test in the real game VM.** The rule is a function the hook calls. Debug-only
  globals inject a fake kill count, log the dialog text instead of showing it, and prefix the state keys so
  each case starts clean. A `SELFTEST` constant runs 11 cases from the mod system's init hook and writes
  PASS/FAIL lines and a final `RESULT pass=N fail=M` to a text file. The game ran on a hidden Windows desktop
  (never on the user's screen); the file was polled for `RESULT` and the test instance killed.
  Result: 23 checks, 0 failures. Covered: no kill, single, double and triple kills, kills during bonus phases
  in both orders, other phases passed through, the old-save first run, the counter cap, and one case with
  every debug global zeroed to prove normal play reads the real flags.
- Each new .jaf file was proven to be compiled by adding an undefined name once and seeing the build fail there.
- The save folder was restored from backup and byte-compared afterwards.
- **Not verified:** the info dialog shown from the phase loop (the game itself never shows it at that point), a
  real redirect after a real kill, saving and reloading mid-bonus, and one shortcut-route death marker.

## Gotchas
1. **The mod silently did nothing.** A global declared `int X = -1;` read 0 at runtime. **Cause:** alice-tools
   only stores the initial values of added globals in the .ain's GSET section, and `Rance10.ain` has none, so
   they are dropped and the build prints `N global initvals ignored` (`src/ainedit/jaf_compile.c` in 0.11.1,
   `src/core/jaf/compile.c` in 0.13.0). **Fix:** design every added global so 0 or "" means normal play, and
   reset them in an init-hook override.
2. **The game never opened when launched by a script**, at almost 0 % CPU. **Cause:** a hidden message box,
   "failed to read AliceStart.ini", from a Japanese install path on a non-Japanese code page (the working
   directory was already right). **Fix:** start through Locale Emulator (`LEProc.exe -run <exe>`, working
   directory = game folder). To read a dialog on a hidden desktop, enumerate that desktop's windows.
3. **Background input does nothing.** System 4 ignores posted window messages, and a hidden desktop gets no real
   input. **Fix:** test rule logic in the VM with simulated inputs, and leave real UI checks to a person.
4. **Wrong death markers from the obvious signals.** A majin map icon and a won boss battle did not mean the
   majin died. **Fix:** read the developers' route debug functions, and check both the "joined" and "died" flags.
5. **Flag strings are setters.** Passing "<name>死亡＝１" to the flag function to *check* it would kill the
   character. **Fix:** read the array slot the setter writes.
6. **An apostrophe in in-game message text breaks the line.** **Fix:** reword. A possible second issue, a
   lowercase `r` acting as a line break in one dialog, is unconfirmed.
7. **Booting rewrites two global save files** (collection and global data) even without loading a save.
   **Fix:** back up the whole save folder before automated runs and restore it afterwards.

## Assets
None.

## Cost and time
One long session: researching the turn system in the bytecode listing, four implement-and-review rounds with
subagents, and one hidden-desktop test session (three launches; the third used Locale Emulator).

## Open questions
- Does the info dialog work when called from the phase loop instead of from inside another scene?
- Do the added globals survive loading a save untouched? They sit in a different global group from the save
  data, so they should; not tested.
- Part 2 has its own chapter controller and was left alone.

## Credits
- nunuhara's r10-mod-system (MIT) and alice-tools, which do the compiling and packing.
- xupefei's Locale Emulator.
