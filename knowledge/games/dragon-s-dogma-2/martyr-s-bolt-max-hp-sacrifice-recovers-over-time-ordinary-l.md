---
kind: game
title: Martyr's Bolt max-HP sacrifice recovers over time, ordinary Loss Gauge untouched
game: Dragon's Dogma 2
games_also: []
game_version: Steam 2054970 build 25920212 (Oct 2026 update); REFramework nightly-01433 (d4611aef)
platform: windows
engine: re-engine
route: loader-api
tools:
- REFramework (Lua)
- REFramework Dump SDK (il2cpp_dump.json)
- fengari 0.1.4 (offline Lua tests)
anti_cheat: none found; single-player only
status: released
agents:
- Claude Code (Opus 5.5)
humans:
- MizaelX
date: '2026-10-22'
links:
- https://github.com/MizaelX/DD2-Martyr-s-Bolt-Recovery
- https://github.com/praydog/REFramework
- https://github.com/D3athAn63l/DD2_Stuff/tree/main/research/baselines/health/2026-10-11
tags:
- skills
- health
- loss-gauge
- magick-archer
- attribution
- sdk-hook
---
# Martyr's Bolt max-HP sacrifice recovers over time, ordinary Loss Gauge untouched

> One REFramework Lua script makes the max HP that the Magick Archer's Martyr's Bolt sacrifices come back
> linearly (100% of original max HP per 300 s), while Loss Gauge from enemies, falls and everything else stays
> until a rest or curative, as in vanilla. The hard part was attributing each Loss Gauge drop to the skill;
> it's done by hooking the game's own sacrifice routine and cross-checking against the game's own sacrifice
> counter. Verified in the real game by the human (playtests plus the mod's debug log), and released.

## Setup
- Dragon's Dogma 2, Steam, Windows 11 Pro, Steam build 25920212 (`DD2.exe` dated 2026-10-16). TDB 83.
- REFramework **nightly-01433** (published 2026-10-21). The nightlies are now a single monolithic
  `REFramework.zip` for every RE Engine game; extract **only** `dinput8.dll` into the game folder. It was the
  only build newer than the 2026-10-16 game update at the time.
- No other mods. Saves were backed up first (`Steam\userdata\<id>\2054970`).
- Starting point for the health API: D3athAn63l's live snapshot, a read-only probe script and its capture
  (https://github.com/D3athAn63l/DD2_Stuff/tree/main/research/baselines/health/2026-10-11). Everything in it
  still worked on this build.

## Route and why
`loader-api`: REFramework Lua with `sdk.hook`. Data edits can't do runtime HP accounting. The two candidate
designs were (a) polling `ReducedMaxHp` while the skill's charging state is active, or (b) hooking the code that
applies the cost. Polling can't separate the skill's drain from a hit taken mid-charge (Gotcha 3), so the mod
uses (b). A read-only probe script came first, to find the names and prove the attribution before any write
code existed.

## How the game works (what we had to learn)
- **Skill identity:** Martyr's Bolt is `app.HumanCustomSkillID.Job08_SpiritArrow` (91). Magick Archer is job 8
  (`Human:get_JobContext().CurrentJob`) and is **Arisen-only**, so pawns never run this skill.
- **The action:** `app.Job08SpritArrow` (note the typo "Sprit"; parent `app.UseHumanAction`) is the
  behavior-tree action. Its `update(ActionArg)` calls `processSacrifice()` every frame while charging, and that
  call lowers the Arisen's max HP through `app.HitController.setReducedMaxHp(Single)`. Warrior's Scarlet Vow has
  its own `processSacrifice` on `app.Job05ScarletVowController`; don't confuse the two.
- **The game's own counter:** `Human:get_Job08ActionCtrl()` → `app.Job08ActionController`
  `get_SpritArrowSacrificedHitPoint()` is the HP sacrificed by the current cast. It reads 0 between casts,
  restarts at the first tick and matched the measured gauge drop exactly (1647.25 vs 1647.25). On lethal casts
  it slightly overshoots the real drop, because the gauge clamps at 1.
- **Drain rate:** `app.Job08Parameter.SpiritArrowParameter.MaxHpDamageRateByFrame`. Observed about 4.5 HP per
  frame on 1804 max HP (about 18–22 per 50 ms). A full charge took 1439–1800.
- **Current HP vs max HP:** the skill drains `ReducedMaxHp`; current `Hp` is clamped down to it. If you're
  already hurt, only the gauge drains until the two meet.
- **FSM** (`via.motion.MotionFsm2:getCurrentNodeName(0)` on the player's GameObject): charging =
  `Job08.Job08_SkillAttack.Job08_CS12.Job08_ReadySpiritArrow`, release = `...Job08_ShootSpiritArrow`.
  The node name is a good "is charging" signal.
- **Ordinary damage:** `HitController.updateDamageHp(DamageInfo, Single, Boolean)`, which calls
  `setReducedMaxHp` **outside** `processSacrifice`. The Loss Gauge share was about 10% of damage (78 → 7.79).
- **Other HP paths seen:**
  - Rest at a camp: `setReducedMaxHp(orig)`.
  - Wakestone revive (FSM `Damage.HumanDamage_Root.ReviveFromWakestone`):
    `recoverHpAndMaxHpCompletely(true)`.
  - Death by the bolt: gauge drains to 1.00, then `updateDamageHp(1.00)` brings HP to 0
    (FSM `Damage.Damage_Root.DieCollapse`).
  - Other mutators on `app.HitController`: `setReducedMaxHpValue`, `recoverMaxHp`, `recoverHp`, `setHp`,
    `setHpValue`, `updateReductionMaxHPDamage`, `setMinRateMaxHp`, `set_MinRatioReducedMaxHp`.
- **Writing max HP:** `HitController:call("set_ReducedMaxHp(System.Single)", v)` sticks, reads back
  immediately and does **not** change current HP. The value is a float32.
- **No cancel, no refund:** there's no manual cancel for the charge (tested on controller). A grab
  (`Caught.Caught_Root.Caught_Stand.Caught_Standing`) interrupts it, and nothing is refunded.
- **Save load** gives the Arisen a new `HitController` (new address). Pause = `app.GuiManager:isPausedGUI()`;
  combat = `app.BattleManager:get_BattleMode() ~= 0`.

## Build steps
1. Install REFramework (`dinput8.dll` only). Back up saves.
2. Probe first (read-only): hook `app.Job08SpritArrow.processSacrifice`/`start`/`update` and the
   `HitController` mutators above, filtered to the Arisen's HitController address. Log every Hp and
   ReducedMaxHp change, tagged by whether it happened inside `processSacrifice`. The probe is in the repo
   (`tools/MartyrsBoltProbe.lua`).
3. The mod (`src/MartyrsBoltRecovery.lua`):
   - **Register:** hook `processSacrifice`. For each call, register
     `min(drop of the Arisen's ReducedMaxHp during the call, advance of SpritArrowSacrificedHitPoint during the call)`.
     A counter decrease means it restarted, so the advance is its new value. One pool, in HP points.
   - **Recover:** every 0.1 s of unpaused time, raise `ReducedMaxHp` by
     `OriginalMaxHp / 300 × dt`, capped by the pool and by the missing max HP. Read the value back and charge
     the exact delta to the pool.
   - **Reconcile:**
     - Clear the pool on HP 0, on max HP fully restored, and on a new HitController.
     - Any other rise in max HP with `OriginalMaxHp` unchanged (items) uses up the pool first.
     - Never let the pool exceed the missing max HP.
   - **Suspend** while charging (FSM node or a sacrifice in the last 0.3 s), while paused, during battle
     (configurable), and on frame gaps over 1 s.

## Verification
- **Oracle 1, probe logs:** two runs of the read-only probe with the human placing marks (start charge,
  release, hit while charging, ordinary damage, rest, death). The decisive cast: a hit landed mid-charge. It
  produced 33.50 Loss Gauge outside `processSacrifice` and 312.02 inside, and the game counter read 312.02.
- **Oracle 2, mod debug log** during the human's playtest:
  - Casts registered and accumulated (240.19 + 217.27 → pool 449.16).
  - Measured recovery was about 6.05 HP/s at 1804.1 max HP (expected 6.01).
  - Death, rest and save load each cleared the pool.
- **Human-reported in game:** ordinary damage not restored; a starting Loss Gauge stays after recovery ends;
  pause; fast travel keeps the pool; combat on/off.
- **Offline:** 48 checks running the real script in fengari against a stubbed REFramework and a fake Arisen
  (including the spec case: 300 ordinary + 1000 sacrificed ends at exactly 1700). Simulated, not in game.
- **Not verified:** other game builds; partial max-HP restoration items in game (only simulated); keyboard
  and mouse input.

## Gotchas
1. **0 hooks installed, empty reflection dumps.** **Cause:** a filter like `name:find("hp|damage")`. Lua
   patterns have no `|` alternation, so it matched the literal string. **Fix:** loop over a list of plain
   substrings, or list the exact method names.
2. **Watching `ReducedMaxHp` during the charge can't attribute a mid-charge hit.** The hit's ~10% gauge share
   (a few HP) disappears into 18–22 HP drain steps, and hitstop briefly pauses the drain, so you can't spot it.
   **Fix:** measure inside `processSacrifice` and cross-check with `SpritArrowSacrificedHitPoint`.
3. **The skill and damage both write through `setReducedMaxHp`,** so hooking that method alone doesn't tell you
   the source. **Fix:** attribute by call context (inside `processSacrifice` or not), not by method.
4. **`update()` wraps `processSacrifice()`.** A before/after delta on `update` double-counts the cost.
   **Fix:** measure on `processSacrifice` only.
5. **Recovery stopped 0.026 HP above the ceiling.** **Cause:** `ReducedMaxHp` is float32. Charging each tick's
   *planned* amount to the pool, instead of the read-back delta, let rounding drift over about 1,500 writes.
   **Fix:** charge the exact read-back delta, and zero the pool below 0.01.
6. **Dump SDK crashed the game,** but `il2cpp_dump.json` (1.16 GB) was complete and valid. Grep it for type and
   method names. It's too big for `JSON.parse` in Node; use line ranges.
7. **Every "full HP" event in the first probe run was a rest,** not a vanilla regeneration. Mark tests in the
   log (menu buttons), or you'll misread them.
8. **The probe's `MotionFsm2:getCurrentNodeName(0)` worked first time** and is far more readable than motion
   bank/ID pairs (`180/1300` charge start, `180/1305` loop, `180/1310` shot). Log both.
9. **Windows tooling:** without uv, the toolkit's bash launcher `bin/um` (what Git Bash runs) tries `python3`
   first. python.org's classic `.exe` installer doesn't create that name (the newer Python install manager
   does), so it hits the Microsoft Store stub. Install `uv` (both launchers prefer it) or disable the alias;
   `bin/um.cmd` (cmd and PowerShell) calls `python` instead.

## Assets
None.

## Cost and time
One evening of work over two days: two probe iterations and one mod iteration with the human playing. Most of
the wall-clock time was playtesting.

## Open questions
- Partial max-HP restoration items in game (the logic is only simulated).
- Whether a game update renames `Job08SpritArrow` / `SpritArrowSacrificedHitPoint`. The mod reports
  "Detection: FAILED" in its menu if the hook target is missing.
- In-game slow-motion counts as normal time (recovery uses real elapsed time with pause detection).
