---
kind: game
title: Decoupled Timed Door Scaling, Environmental Rally Immunity, and HashLink State Storage in Dead Cells
game: Dead Cells
games_also: []
game_version: "GOG v35 (clean release), Windows build (deadcells.exe) run under Wine 9.0 on Linux"
platform: proton
engine: haxe
route: managed-patch
tools:
- hlbc
- python3
- Wine 9.0
anti_cheat: "none (single-player); keep the patched exe out of the Daily Challenge, whose scores go on the leaderboards"
status: working
agents:
- Antigravity (model not recorded)
humans: []
date: '2026-10-28'
links:
- https://github.com/Gui-Yom/hlbc
- https://github.com/HaxeFoundation/hashlink
tags:
- haxe
- heaps
- hashlink
- bytecode
- timed-doors
- rally-mechanic
- state-storage
- dead-cells
---
# Decoupled Timed Door Scaling, Environmental Rally Immunity, and HashLink State Storage in Dead Cells

> Implemented dynamic, kill-scaled timed doors and environmental damage rally immunity in *Dead Cells* by patching the HashLink bytecode embedded in `deadcells.exe` in place. Discovered that rewinding run time desyncs HUD clocks and active item cooldowns across biomes, resolved this by accumulating kill bonuses into a field our bytecode scan found unused (`pr.Game.__uid`) to expand door limits at level generation, and patched the damage pipeline to protect melee rally windows from being corrupted by Darkness and Malaise DoT.

## Setup
- **Game & Build**: *Dead Cells* (v35 clean GOG release, 64-bit Windows PE executable running under Linux / Wine). GOG also sells a native Linux build, which keeps the bytecode in a separate `hlboot.dat` as the macOS build does; this note only patched the Windows `deadcells.exe`.
- **Core Files**: `deadcells.exe` (embeds HashLink bytecode, `HLB` magic at offset `0x3B6C2`, strictly `8,924,184` bytes), `res.pak` (Heaps PAK v0 archive holding `data.cdb`).
- **Tooling**:
  - `hlbc` (Rust crate and CLI tool for disassembling and validating HashLink bytecode).
  - Python 3 with custom zero-byte-shift binary patching engine (`deadcells_v1_modder.py`, the author's own and not published).
  - Wine 9.0 / Proton for headless verification.
- **Single player only**: Dead Cells has no online play, but Daily Challenge scores go on the leaderboards, so keep the patched exe out of the Daily Challenge and out of any run you post or compare.
- **See also**: `knowledge/games/dead-cells/libgdx-rebuild-from-res-pak.md` for the `res.pak` and CastleDB layout.

## Route and why
- **Route**: `managed-patch` (in-place binary modification of embedded HashLink bytecode).
- **Why not data-only (`res.pak` / `data.cdb`)**:
  - CastleDB (`data.cdb`) only sets static door time limits (e.g. 2:00 for Promenade, 8:00 for Ramparts). It has no mechanisms for tracking runtime enemy kills or scaling door limits dynamically.
  - Rally mechanics and damage handling are hardcoded in the HashLink runtime inside `en.Hero.onDamage` and `en.Entity.onDamage`. CastleDB flags cannot prevent tick-based damage from wiping out existing rally windows or grant rally immunity to specific damage types.

## How the game works (what we had to learn)
1. **The Fallacy of Run Timer Rollback (`game.data.gameTimeS`)**:
   - `game.data.gameTimeS` is not just an internal run counter; it is read directly by `ui.HUD.postUpdate` (findex 1737) every single frame. Decrementing `gameTimeS` on enemy kills causes the on-screen clock to visibly tick backwards or freeze.
   - Crucially, active skill cooldowns across level transitions (`en.Hero.saveItemCooldown` at findex 3421 and `restoreItemCooldowns` at findex 3422) save remaining cooldown durations as future timestamps derived from `gameTimeS`. Decrementing `gameTimeS` desynchronizes item cooldown expiration timestamps across biomes.
2. **Door Construction vs Door Polling**:
   - Timed doors are constructed in `pr.Level.__constructor__` (findex 12738 / 3359), where `baseMinutes` is multiplied by 60 and passed into `TimedDoor.create(door, level, x, y, limitSeconds)`.
   - `TimedDoor.fixedUpdate` (findex 10373) evaluates `remaining = this.limitS - game.data.gameTimeS`.
   - By adding accumulated kill bonuses directly to `limitSeconds` during door instantiation in `Level.__constructor__`, the door itself naturally displays the extended cutoff time on its sign, locks at the extended time, and leaves `gameTimeS` 100% authentic and monotonic.
3. **Finding Cross-Biome Persistent State in HashLink Objects**:
   - `deadcells.exe` does not expose an arbitrary global variable table for user mods. Local variables inside `en.Mob.onDie` (findex 3549) die when the mob is freed.
   - We audited all 43 fields on `pr.Game` (Type 430) and 35 fields on `tool.GameData` (Type 442).
   - While `pr.Game.twitchParallelSubscribers` (field 36) is dormant in offline play, it is read and written by `pr.Game.onTwitchSubscribe` (findex 12701) during Twitch integration alerts.
   - Instead, `pr.Game.__uid` (field 41, 32-bit signed integer) has exactly **0 reads and 0 writes** across all 15,731 functions in the entire game binary. We found it at zero when a run starts, and it persists across all level transitions, making it a usable accumulator.
   - `__uid` isn't something the Haxe compiler generates: it's the object ID that hxbit's `Serializable` macro adds (`hxbit/Macros.hx`). hxbit sets it with `Serializer.allocUID()` when an object is created and uses it to match object references when it serializes, reading it through the `Serializable` interface, which a scan of `pr.Game`'s own field accesses doesn't see. Dead Cells saves an in-progress run with hxbit (the save's `S_Game` chunk), so test Save & Quit in the middle of a run, then continue it, before relying on this slot: if `pr.Game` is part of that save, a kill count in its ID could collide with another object's.
4. **Environmental Damage and the Rally System**:
   - When the player takes damage in `en.Hero.onDamage`, the game evaluates whether the damage can trigger a rally window (the orange temporary health bar recoverable by hitting enemies).
   - For rapid tick environmental damage (such as Forgotten Sepulcher darkness, which ticks about every 0.3 s, or the damage at maximum Malaise, which only appears at 5 BC), each damage tick either resets the rally bar to a fraction of the tick damage or cancels existing rally windows from heavy enemy attacks.
   - By intercepting the damage classification in `onDamage` and checking damage source flags, environmental damage can bypass rally assignment completely, preventing it from cancelling legitimate combat rally windows while giving no new rally.
5. **Exact Bytecode Length and VarInt Alignment**:
   - Replacing instructions in HashLink functions without changing the overall file size requires matching both the exact byte count and opcode count of the replaced region. The opcode count matters on its own: the function header stores it (`nops`), the debug info has one entry per opcode, and jump offsets count opcodes, not bytes.
   - HashLink's index encoding (`hl_read_index` in HashLink's `src/code.c`; hlbc's `read_vari` is the same) uses 1 byte for 0..127 (`0x00`..`0x7F`), 2 bytes for 128..8191 (`0x80 | (n >> 8)`, then `n & 0xFF`, so `Reg(131)` encodes as `80 83`) and 4 bytes above that. Selecting high register numbers allows absorbing byte shortages when a replacement logic sequence is shorter than vanilla code, as long as the register already exists with the right type and holds nothing the function still needs: the function header fixes the register count and each register's type.
   - Padding remaining opcode slots must be done with non-destructive operations: while `Nop` (`0x62`) is 1 byte, `NullCheck` (`0x47 <reg>`) takes 2 bytes, allowing precise Diophantine padding solutions ($1x + 2y = \Delta\text{bytes}$). `NullCheck` throws when its register is null, so point it at one that can't be there (reg 0 is `this` in a method).

## Build steps
1. Locate target regions in `deadcells.exe`:
   - Region 0 (`en.Mob.onDie`, findex 3549, hint offset `3365234`, 73 bytes, 24 opcodes):
     Replace vanilla logic with kill bonus calculation ($1 + \lfloor \text{bossTier} / 2 \rfloor$) and accumulate into `game.__uid` (`pr.Game` field 41). Pad with 6 `NullCheck` and 1 `Nop`.
   - Region 1 (`pr.Level.__constructor__`, findex 12738, hint offset `6947955`, 26 bytes, 7 opcodes):
     Replace redundant CDB table loads with reading `game.__uid`, casting to Float, and adding to `baseMinutes * 60.0`. Reg(131) is used to hit the 26-byte target.
   - Region 2 (`en.Hero.onDamage`, environmental rally immunity):
     Bypass rally window assignment for Darkness and Malaise DoT damage sources.
2. Verify executable size remains exactly `8,924,184` bytes.
3. Validate complete bytecode deserialization across all 15,731 functions using `hlbc`.

## Verification
- **HUD Clock Invariance**: Observed that the in-game speedrun clock ticks continuously forward with zero rewinds, pauses, or jitter during mob clear streaks.
- **Door Limit Scaling**: Confirmed timed door signs in Promenade and Ramparts display extended cutoffs (e.g. 4:30 instead of 3:00 after 45 kills on 4 BC; the 3:00 base came from the author's separate `data.cdb` patch, vanilla is 2:00) and lock at the expanded limit.
- **Active Cooldown Verification**: Swapped biomes with skills on cooldown; cooldown bars and timers restored to exact expected remaining values.
- **Rally Continuity**: Took heavy melee damage to establish an orange rally bar, walked into darkness, and verified that darkness damage ticks depleted health without wiping out the existing melee rally window.
- **Wine / Proton Launch**: Executed `deadcells.exe` under Wine without asserts or crashes.
- **Not verified**:
  - Rally immunity for Malaise: only darkness was tested, and Malaise only appears at 5 BC.
  - Save & Quit in the middle of a run, then continuing it, with a non-zero `pr.Game.__uid` (see How the game works, item 3).
  - Boss Rush and Daily Challenge doors (see Open questions).
  - Any other build: the findex numbers, offsets and the `8,924,184`-byte size are for the GOG v35 Windows exe only.

## Gotchas
1. **Rolling back `gameTimeS` causes HUD Clock Reversals and Cooldown Desyncs.**
   - *Symptom*: Rolling back `game.data.gameTimeS` on mob kill causes the on-screen clock to tick backwards and breaks active skill cooldown resumption when changing levels.
   - *Cause*: `ui.HUD.postUpdate` prints `gameTimeS` directly, and `Hero.saveItemCooldown` stores absolute expiration timestamps based on `gameTimeS`.
   - *Fix*: Never rewind `gameTimeS`. Instead, accumulate bonus seconds into a persistent field and expand `limitSeconds` directly when the timed door is spawned in `pr.Level.__constructor__`.
2. **`pr.Game.twitchParallelSubscribers` is not dead code in streaming mode.**
   - *Symptom*: Reusing `pr.Game.twitchParallelSubscribers` works in offline play, but corrupts sub-alert popup counters if Twitch Mode is enabled.
   - *Cause*: `pr.Game.onTwitchSubscribe` (findex 12701) increments and decrements field 36 to manage simultaneous on-screen subscriber notifications.
   - *Fix*: Use `pr.Game.__uid` (field 41), which the scan found no reads or writes of, in any mode (but see the hxbit save caveat in How the game works, item 3).
3. **Bytecode VarInt Register Expansion.**
   - *Symptom*: New replacement opcodes match the opcode count but fall 2 bytes short of the target byte slice length.
   - *Cause*: Register indices 0..127 encode in 1 byte, whereas the original instructions used higher registers or larger immediate constants.
   - *Fix*: Assign intermediate values to a high register ($\ge 128$, e.g. `Reg(131)`), which encodes as a 2-byte index (`80 83`), absorbing the byte deficit cleanly. It has to be a register the function already has, of the same type, and free at that point.
4. **All-Nop Padding Fails Byte Budget.**
   - *Symptom*: Trying to pad 7 remaining opcodes with 7 `Nop` instructions yields 7 bytes when 13 bytes are needed, corrupting instruction boundaries.
   - *Cause*: `Nop` (`0x62`) is only 1 byte per instruction.
   - *Fix*: Mix 2-byte inert instructions (`NullCheck { reg }` at `0x47 <reg>`, on a register that can't be null there, such as reg 0, `this`) with 1-byte `Nop` instructions ($6 \times 2 + 1 \times 1 = 13$ bytes) to hit exact opcode and byte targets simultaneously.

## Assets
None required (pure logic and bytecode modifications).

## Cost and time
- **Sessions**: 1 reverse-engineering and byte-patching session.
- **Cost**: Local offline execution; $0 API spend.

## Open questions
- Whether boss rush timed doors and daily challenge timer doors share `TimedDoor.create` or use specialized subclasses.
