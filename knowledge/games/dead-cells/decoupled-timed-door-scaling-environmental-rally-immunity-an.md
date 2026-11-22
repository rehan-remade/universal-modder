---
kind: game
title: "Kill-scaled timed doors in Dead Cells v1.0 (pr.Game.__uid as a run counter), and a no-Rally filter for darkness and Malaise ticks"
game: Dead Cells
games_also: []
game_version: "1.0 GOG Windows build (deadcells.exe 8,924,184 bytes, PE32 i386, HLB v3 at file offset 384784, build stamp 2018-08-06), run under Wine/Proton on Linux"
platform: proton
engine: haxe
route: managed-patch
tools: ["hlbc 0.7.0", "python3", "Wine"]
anti_cheat: "none (single player). Keep the patched exe out of the Daily Challenge, whose scores go on the leaderboards."
status: abandoned
agents: ["Antigravity (Gemini 3.x Flash, high; 3.7 or 3.8)", "Claude Code (claude-opus-5-5)"]
humans: []
date: '2026-10-28'
links:
- https://github.com/Gui-Yom/hlbc
- https://github.com/HaxeFoundation/hashlink
tags: [haxe, hashlink, bytecode, timed-doors, rally, dead-cells, hxbit]
---
# Kill-scaled timed doors in Dead Cells v1.0, and a no-Rally filter for DoT ticks

> Every enemy kill added time to the timed doors generated afterwards, stored in a field the bytecode never
> touches (`pr.Game.__uid`). The patch boots, but its author's own archive marks it "currently bugged & needs
> balancing", and it was parked. The ideas and the function map are still useful. This note was **corrected on
> 2026-11-21**: the first version (PR #451) gave the wrong build ("v35", 64-bit), the wrong bytecode offset, wrong
> function numbers, a status of "working", and an in-game verification list for a version that no longer exists.
> All facts below were re-checked against the vanilla exe. Start with `dead-cells-v1-0-modding-reference.md`.

## Setup
- **Build:** Dead Cells 1.0, GOG Windows build. `deadcells.exe` is 8,924,184 bytes, **32-bit** (`PE32 … Intel
  80386`). The HashLink bytecode (`HLB`, version byte 3) is embedded at **file offset 384784**. Build stamp
  `2018-08-06 15:44:01`, commit `0e905688c`. There is no "v35" in this build: that version string belongs to a 2023
  Steam macOS build used by another note.
- **Run** under Wine/Proton on Linux.
- **Files:** `deadcells.exe` (bytecode) and `res.pak` (`data.cdb` CastleDB JSON at file offset 123,530,592).
- **Tools:** hlbc 0.7.0 for disassembly. The byte patch itself lives in the author's private mod manager as a list
  of (offset, vanilla bytes, patched bytes) regions.

## Route and why
- `managed-patch`: same-size edits of the embedded bytecode.
- **Why not data only:** `data.cdb` holds one static limit per level, in minutes (`props.timedDoor`). Vanilla:
  Prisoners' Quarters (`PrisonCourtyard`) and `SewerShort` 2, Ramparts (`PrisonRoof`) and Ossuary 8, Stilt
  Village 17, Graveyard (`Cemetery`) 19.5, Crypt 26, `T_AfterBridge` 15. Nothing in data reacts to kills. Raising
  the Prisoners' Quarters doors from 2 to 3 minutes *is* a plain data edit, and it works in game.

## How the game works (what we had to learn)
1. **The run clock can't be rewound.**
   - `game.data.gameTimeS` is the run clock.
   - `ui.HUD.postUpdate` (findex 1737) displays it every frame.
   - `Hero.saveItemCooldown` (findex 3421) stores cooldown expiry as `gameTimeS`-based timestamps, which
     `Hero.restoreItemCooldowns` (3422) reads back on level change.
   - So taking time off the clock on kills would make the HUD clock run backwards and break cooldowns across
     levels. The working idea is to move the door's limit instead.
2. **Where doors get their limit.**
   - `pr.Level.__constructor__` (findex 3359) creates each `TimedDoor` (Level.hx:274-275). The limit passed to
     the door constructor is the door marker's `genData.mins` × 60 (seconds). A marker without `genData` throws
     "missing genData for TimedDoor in …".
   - `TimedDoor.fixedUpdate` (findex 10373) compares `limitS` with `game.data.gameTimeS` for the countdown and the
     lock.
   - A bonus added to the limit at construction therefore shows on the door sign and moves the lock time, while
     the clock stays honest.
3. **Storage that survives level changes.**
   - Kills happen in `en.Mob.onDie` (**findex 1956**; the first version said 3549, which is
     `HeroActiveSkill.serialize`).
   - The counter needs to live on something that persists for the whole run. `pr.Game` (type 430) has a field 41
     `__uid` (i32) that no op in the game reads or writes by name.
   - `__uid` is hxbit's object id (`hxbit.Serializable`). The serializer reads and writes it generically
     (hxbit/Serializer.hx), which a field-name scan doesn't see.
   - A later audit [static] concluded the value is not kept across Save & Quit, so the bonus is lost when a run is
     continued.
4. **Twitch fields are not free.** `pr.Game.twitchParallelSubscribers` (field 36) looks unused offline, but
   `pr.Game.onTwitchSubscribe` (**findex 515**) changes it in Twitch mode.
5. **Rally and DoT ticks** (a separate mod in the same pack, not part of the door patch):
   - The Rally bar (recoverable health) is started and refreshed in `Hero.applyAttackResult` (findex 3438), not in
     `Hero.onDamage`.
   - The filter that was built there skips Rally for damage type `DarkMatter` (darkness, global 808), and for
     `Poison` (global 503) only when `triggersGlobalHitShield` is false. That flag marks the Malaise tick. Enemy
     and puddle poison use the same type with the flag set, so they still give Rally.
   - Static read and boot test only; **not tested in game.**

## Build steps
The archived door patch has two regions. Both still match the vanilla exe:
1. `en.Mob.onDie` (findex 1956), ops 89-112, exe offset 3,365,234, 73 bytes. Adds `1 + floor(BC / 2)` whole
   seconds (BC 0-4 gives +1/+1/+2/+2/+3) to `game.__uid` per kill. Padding to the same op count and byte length
   uses `NullCheck` (2 bytes) and `Nop` (1 byte).
2. `pr.Level.__constructor__` (findex 3359), from op 3531, exe offset 6,947,955, 26 bytes. Adds `game.__uid` to
   `minutes × 60` when a timed door is built. A 2-byte register index (`80 83` = r131) is used to fill the
   space.
3. Check: same file size, a re-parse of all 15,731 functions, and a headless Wine boot.

## Verification
- **Checked (2026-11-21):** both regions' vanilla bytes match `deadcells.exe` 1.0 at those offsets, and the
  function names and op positions above. The archived mod was never boot-tested in its current form.
- **Not verified, despite the first version of this note:**
  - Door signs showing the extra time.
  - Cooldowns restoring correctly across biomes.
  - Rally continuity in darkness.
  - A "5-region live-updating" variant mentioned in the old log, which no longer exists in any file.
- **Known bugs (from the archive and a later audit):**
  - The bonus is lost after Save & Quit.
  - A door already on screen doesn't update.
  - The kill hook reads a register without reloading `this._level`.
  - The patch drops vanilla's `hero.destroyed` check.

## Gotchas
1. **Wrong build facts spread between notes.** Symptom: the first version of this note said "GOG v35, 64-bit, HLB
   at 0x3B6C2". Cause: details copied from an unrelated macOS note, and never checked. Fix: identify the exe
   yourself (`file`, size, the `HLB` offset, the build stamp in the string pool), and write that down.
2. **Function numbers that don't match names.** Symptom: "findex 3549 = Mob.onDie", "12701 =
   onTwitchSubscribe", "12738 / 3359 = Level constructor". Cause: unchecked numbers. Fix: resolve every findex by
   name in the disassembler. The correct values are 1956, 515 and 3359.
3. **Rewinding `gameTimeS` breaks the HUD clock and cooldowns.** Cause: the HUD reads it every frame, and
   cooldowns are stored as `gameTimeS` timestamps. Fix: change the door's `limitS` at construction instead.
4. **Same-size padding.** Symptom: new ops match the op count but not the byte count. Fix: mix 1-byte `Nop` /
   `Label` with 2-byte ops (`NullCheck` on a register that can't be null, `JAlways +0`). Or write an index in the
   2-byte varint form (`80 xx`), which is valid for any value below 8192 and needs no new register.

## Assets
None.

## Cost and time
One session for the original patch (Oct 2026). The correction pass took part of one session.

## Open questions
- A version that survives Save & Quit needs storage that is saved with the run. A later mod in the same pack
  stores per-run flags in `GameData.twitchBans` (a StringMap that is created each run and saved with it; only
  Twitch mode writes to it).
- Updating doors already on screen means touching `TimedDoor` (10368-10373) as well.
- Boss Rush / Daily Challenge doors were not examined.
