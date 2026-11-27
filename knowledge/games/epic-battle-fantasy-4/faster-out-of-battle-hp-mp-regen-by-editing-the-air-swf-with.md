---
kind: game
title: Faster out-of-battle HP/MP regen by editing the AIR SWF with FFDec
game: Epic Battle Fantasy 4
games_also: []
game_version: Steam 265610, AIR app EpicBattleFantasy4 v1.0.0 (SWF 171,914,112 bytes, as of 2026-11-15)
platform: windows
engine: unknown
route: managed-patch
tools: ["JPEXS FFDec 26.5.0", "Eclipse Temurin JRE 21.0.13 x64"]
anti_cheat: none (offline single-player; Steam only for achievements/cloud via the FRESteamWorks ANE)
status: working
agents:
- Claude Code (Opus 5.5)
humans: ["SophiaUrabe"]
date: '2026-11-15'
links: ["https://github.com/jindrapetrik/jpexs-decompiler"]
tags: [flash, actionscript3, adobe-air, swf, ffdec, regen, rpg]
---
# Faster out-of-battle HP/MP regen by editing the AIR SWF with FFDec

We sped up Epic Battle Fantasy 4's map regeneration so the whole party refills HP and MP in about 1.5 s after a
fight, instead of ~30 s (HP) and ~120 s (MP). The game is an Adobe AIR captive-runtime app whose code is all
ActionScript 3 in one loose SWF. We edited two classes, recompiled them in place with FFDec, and copied the SWF
over the original. The user confirmed in game that it works.

## Setup
- Windows 11, Steam release (appid 265610). The install holds `EBF4.exe` (the AIR launcher, 32-bit),
  `Adobe AIR\Versions\1.0\Adobe AIR.dll` and `Epic Battle Fantasy 4.swf`. The SWF is uncompressed (`FWS`,
  SWF version 50).
- `um scan` reports "Unknown native engine". That's wrong: the giveaways are the `Adobe AIR` folder,
  `META-INF\AIR\application.xml` and the big `.swf`.
- JPEXS FFDec 26.5.0 (release zip, run with `java -jar ffdec.jar`).
- **64-bit Java is required** for the 172 MB SWF. We used a portable Temurin 21 JRE with `-Xmx6g`.
- Saves (`*.meow`) and `errorLog.txt` live in the game folder itself, not in AppData. Back up the saves first.

## Route and why
- AS3 source-level patch through FFDec's `-replace` (it recompiles one class and writes a new SWF).
- No mod loader exists for this game, and none is needed: the code is managed bytecode in a loose file.
- Fallback if the AS3 recompile fails: edit the method's P-code (AVM2 bytecode) constants in FFDec.
  We didn't need it.

## How the game works (what we had to learn)
- Frame rate: 30 fps (`Main` SWF metadata). The options menu's "2x Game Speed" sets the stage to 60 fps.
- The map screen class `Maps` registers `handleKeys` on `ENTER_FRAME` while the map is up, so it runs every
  frame, in both mouse and keyboard movement modes.
- `handleKeys` counts a `secondTimer` field up to 30, then calls `MapPlayer.passiveHeal()`.
- `MapPlayer.passiveHeal()` loops over `Players.player1..player4`:
  - Each gets `ceil(maxHP/30)` added to `realHP` and `ceil(maxMP/120)` added to `realMP`, capped at max.
  - It then refreshes the HUD through `MapMenu.updatePlayerBars()` and `initFood(false)`.
  - So vanilla goes empty to full in 30 s (HP) and 120 s (MP).
- KO'd members: `Player.clearBattleVars()` resets `dead` after battle, and `passiveHeal` never checks `dead`.
  KO'd members therefore regen on the map like everyone else; no separate revive is needed.
- Lava tiles (in `MapPlayer`, while wearing thermal boots) take 2% maxHP per step and never drop below 1 HP.
  Fast regen effectively cancels this damage.
- An in-battle standby-player heal exists in `Battle` (+20% HP / +10% MP per turn). It's unrelated to the map regen.

## Build steps
1. Back up `Epic Battle Fantasy 4.swf` and all `*.meow` saves.
2. Export scripts:
   `java -jar ffdec.jar -export script <outdir> "Epic Battle Fantasy 4.swf"` (~1.5 min, 1953 scripts).
   The export is the game's decompiled code: keep `<outdir>` private, outside any repo.
3. Copy `Maps.as` and `MapPlayer.as` out of the export (default package) and make three edits:
   - In `Maps.handleKeys`, fire the heal when the timer is `>= 3` instead of `== 30` (10 ticks/s).
   - In `MapPlayer.passiveHeal`, the HP divisor goes 30 → 15.
   - In the same method, the MP divisor goes 120 → 15.
   - Result: 15 ticks × 3 frames = 45 frames ≈ 1.5 s from empty to full.
4. Recompile into a new SWF:
   `<jre64>\bin\java.exe -Xmx6g -jar ffdec.jar -replace <backup.swf> <out.swf> Maps Maps.as MapPlayer MapPlayer.as`
   (prints "This feature is EXPERIMENTAL"; exit 0).
5. Copy `out.swf` over the game's SWF. To uninstall, copy the backup back. Steam "verify files" also restores it.
   `out.swf` is the whole game with two classes changed, so it stays in your own install. Share the mod as these
   steps (or a patch applied to the player's own SWF), never the SWF.

## Verification
- Static: re-exported just those two classes from the built SWF
  (`-selectclass Maps,MapPlayer -export script`) and confirmed the three new values.
- Runtime: the game boots through Steam with the modified SWF, and the user won a fight and confirmed the bars
  refill in about a second or two on the map.
- Not verified: behaviour at 60 fps (it should be ~0.75 s), and long-term save compatibility. Saves should be
  unaffected because only code changed.

## Gotchas
1. **FFDec "out of memory" dialog during `-replace`** (the export worked fine). **Cause:** the system Java was
   32-bit Java 8, capped at ~1160 MB heap; rewriting a 172 MB SWF needs more. FFDec's dialog even says
   "You are running 32bit Java". **Fix:** use a portable 64-bit JRE (Temurin 21) with `-Xmx6g`.
2. **`um scan` says "Unknown native engine".** **Cause:** no AIR/Flash signature in the scanner. **Fix:** look for
   the `Adobe AIR` folder, `META-INF\AIR\application.xml` and a `.swf`; mod that SWF, not the exe.
3. **Worried the AIR signature (`META-INF\signatures.xml`) would reject a modified SWF.** **Cause:** none. The
   captive runtime doesn't verify it on launch. **Fix:** nothing needed; the modified SWF loads as is.
4. **Don't trust `errorLog.txt` as a "did it start" oracle.** It wasn't rewritten on launch here; the tail
   still showed an older session. Use the process and its window or a screenshot instead.
5. **Line endings:** editing the exported `.as` files with sed on Git Bash dropped CRLF. FFDec recompiled them
   fine; diff with `--strip-trailing-cr` to see the real change.

## Assets
None.

## Cost and time
About one session. Most of the time went to waiting: script export (~1.5 min) and `-replace` (a few minutes).

## Open questions
- Make the regen happen only right after a battle (e.g. a timer started on return from battle) rather than any time on the map.
- `um scan` could learn an `adobe-air` / Flash fingerprint.
