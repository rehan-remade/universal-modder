---
kind: game
title: 'Hand of the King parry animation snap: setAffectS fires onAffectChange for fully resisted affects (live HashLink tracing)'
game: Dead Cells
games_also: []
game_version: 'v1.0 GOG (deadcells.exe 8,924,184 bytes, HLB v3 bytecode embedded at file offset 384784); compared against GOG 1.25.3 (Linux, hlboot.dat)'
platform: proton
engine: haxe
route: managed-patch
tools: [hlbc, python3, numpy, ptrace, dc-patcher/hlx, ffmpeg]
anti_cheat: none (single-player offline)
status: working
agents:
- Claude Code (claude-opus-5-5)
humans: []
date: '2026-11-07'
links: []
tags: [hashlink, haxe, dead-cells, boss, parry, stun, affects, animation, runtime-tracing, ptrace, breakpoint, wine, proton]
---
# Hand of the King parry animation snap: setAffectS fires onAffectChange for fully resisted affects (live HashLink tracing)

> In Dead Cells v1.0, parrying Hand of the King's lance combo cut his swing animation to idle, then his next hit
> snapped in from idle. That's a vanilla bug, fixed by Motion Twin in later versions. The cause was found by tracing
> the running game (a memory reader plus an int3 breakpoint on the JIT'd animation functions), not by reading
> bytecode. It's fixed with a 1-byte HashLink patch that matches the modern build's logic. The user confirmed it in game.

## Setup
- Dead Cells v1.0 GOG, run through Steam + Proton 9.0 (Beta) on Linux. `deadcells.exe` is a **32-bit** HashLink
  JIT host. The bytecode is embedded in the exe (HLB v3).
- A modern GOG build (1.25.3, native Linux, bytecode in `game/hlboot.dat`) was installed side by side as a reference.
  To make offset-based tools read it, pad the `.dat` with the v1.0 blob offset in zero bytes.
- Tools: `hlbc` 0.7 (through a small Rust CLI, `hlx`), Python 3 + numpy reading `/proc/<pid>/mem`, Python ctypes
  `ptrace` for breakpoints, and ffmpeg for frame-stepping the user's screen recordings.

## Route and why
- `managed-patch`: a same-size byte edit inside the embedded bytecode.
- Static bytecode reading alone failed several times (details under Gotchas). Two live captures settled it: a
  per-tick state trace and a breakpoint that names the caller. The modern build supplied the shape of the official fix.

## How the game works (what we had to learn)
- **Combo chaining.** Each of his combo hits is a `tool.MobAttack`. When a hit's charge completes, its
  `onChargeComplete` queues the next hit (`queueAttack`; his override keeps the queue alive ~99 s). The queued hit
  fires from `Mob.fixedUpdate` once his AI lock (cooldown key 239075328) expires, which is about when the swing
  animation ends. Unparried, the swing therefore flows straight into the next wind-up.
- **Parry handling.** On a parry, `tool.weap.BaseShield.onOwnerAttackResult` halves the attacker's velocity, bumps it,
  calls `setAffectS(Stun, strike duration)` on the attacker, then launches the counter attack.
- **The bug.** `Entity.setAffectS` returns early only when the *raw* duration is <= 0, and applies resistance
  afterwards. Its tail calls `onAffectChange(affect, added=true)` whenever the affect wasn't already active, even when
  the resisted duration is 0. For a boss that fully resists Stun, `Mob.onAffectChange` still takes its stun branch and
  calls `AnimManager.stopWithStateAnims`. That cuts the swing (atkA → atkAIdle → idle), and the queued next hit then
  starts from idle.
- **Modern fix.** In 1.25.3, `Entity.setAffectS` returns as soon as the *resisted* duration is <= 0. (Its stun
  branch in `Mob.onAffectChange` and the parry stun are unchanged.)
- **HashLink 32-bit runtime layouts, verified live:**
  - `hl_type` is 16 bytes, so the type table is easy to find by matching the bytecode's kind sequence at stride 16.
  - `hl_type_obj.rt` is at +40.
  - `hl_runtime_obj.fields_indexes` is at +32.
  - Native arrays have 16-byte headers.
  - Strings are `{type, utf16 bytes, length}`.
  - Enums without parameters store their index at +4.
  - `hl_module.functions_ptrs` (+16) is indexed by findex. Every JIT function starts with `55 8b ec`, so ebp-chain
    stack walks work and map back to findex through that table.
  - Inherited fields keep the same byte offset in subclasses.
- **Affects** are an `ArrayBytes_Float` indexed by `Affect` enum ordinal (8 Stun, 9 FreezeCast, 10 SlowCast,
  20 Frost, 21 Thaw). Values are in frames. -1 means the affect was never set.
- **Disassembler names for virtual calls are wrong.** Resolve the slot number against the class's proto `pindex`
  list. Examples: 33 bump, 38 applyAttackResult, 39 onDamage, 45 setAffectS, 48 getAffectResist, 50 onAffectChange.

## Build steps
1. In the HashLink bytecode, find `Entity.setAffectS`. In v1.0 GOG it's findex 1835 and the op is at exe offset
   1338077.
2. The op is `JNotGte r8, r2, +1` (bytes `37 08 02 01`), with r8 = 0.0 and r2 = raw duration. Change r2 to the
   register that holds the resisted duration, r5: `37 08 05 01`.
3. Same size, no jumps move. Check with a re-parse and an op-count verification.

## Verification
- **Live state trace** (`/proc/pid/mem`, about 1 kHz sampling) of his sprite group and frame, animation stack, every
  skill's charge and cooldown, affects, queued attack, cooldown keys and distance to the hero.
  - Parried: the thrust was cut at frame 12 of 19, on the tick the parry resolved.
  - Unparried: it ran to frame 18.
- **Caller capture.** An int3 on the JIT entry of `stopWithStateAnims` / `stopWithoutStateAnims`, conditioned on
  `[esp+4]` being HotK's AnimManager. All 13 mid-swing cuts in one fight had the stack
  `Mob.onAffectChange ← Entity.setAffectS ← BaseShield.onOwnerAttackResult ← Hero.applyAttackResult ← AttackData.hit
  ← (his hit closure) ← MobAttack.execute ← Skill.update`.
- **In game, after the patch:** the user parried his lance combo and the swings played through. Not separately
  verified: other bosses and other fully-resisted affects. The change only stops "added" callbacks for effects
  that would last 0 frames, which matches the modern build.

## Gotchas
1. **The previous patches did nothing.** Symptom: an earlier agent disabled HotK's `"parry"` and `"stun"`
   state-animation conditions, and nothing changed in game. Cause: `"parry"` is HotK's *own* shield-block skill. A
   parry applies Stun to him, but he resists it fully, so the >0.15 s stun state animation never qualified. Fix: trace
   the runtime before patching. Check what a closure is attached to (skill vs state animation) before assuming its
   name means what you think.
2. **A stun-immunity patch didn't help.** Symptom: making him always resist Stun (`getAffectResist` = 1) changed
   nothing. Cause: resistance only zeroes the duration, and `setAffectS` still fires `onAffectChange(added)` for a
   0-length affect. Fix: patch the early return in `setAffectS` instead.
3. **The snap looks like ordinary combo chaining in video.** Symptom: unparried clips also cut from the thrust
   straight into the next wind-up. Cause: that cut is normal (the next hit starts right as the swing ends). The bug
   was a 3-frame idle/transition pose after the parry freeze. Fix: compare parried and unparried frame by frame at
   full resolution, and compare animation frame cursors in a memory trace.
4. **"64-bit" is wrong for v1.0.** Symptom: memory layouts taken from 64-bit HashLink didn't match. Cause: an
   older note called `deadcells.exe` 64-bit (corrected since), but it's a 32-bit HashLink host (`PE32 … Intel
   80386`). Fix: use u32 pointers; `hl_type` is 16 bytes.
5. **Breakpoint bytes left in the live game.** Symptom: stopping the ptrace tool with Ctrl-C during detach left
   `int3` (0xCC) at two function entries, with no tracer attached. Fix: make SIGINT only set a flag so the restore
   runs uninterrupted, re-read the code bytes after every run, and write the original bytes back through
   `/proc/pid/mem` if needed.
6. **The tracer watched the wrong boss after a death.** Symptom: no hits after the player died and restarted the
   fight. Cause: the old HotK object was disposed and a new one created. Fix: watch the AnimManager's `destroyed`
   flag and re-find the boss in a background thread.
7. **Reading memory in a Proton game.** `/proc/<pid>/mem` and `ptrace` worked against the Wine process despite
   `ptrace_scope = 1`. Attach to every thread (`PTRACE_SEIZE` + `TRACECLONE`) and forward every signal you don't own,
   or Wine's exception handling breaks.

## Assets
None.

## Cost and time
About one long session. Two traced fights found the cause, after many hours of static analysis that went wrong.

## See also
- `dead-cells-v1-0-modding-reference.md`: files, tools, save format, function map.
- `knowledge/techniques/hashlink-in-place-bytecode-patching.md`: the patching rules and the live-tracing method
  in engine-neutral form.

## Open questions
- Other v1.0 bosses that resist stuns probably showed the same snap on parry. Not tested individually.
- The modern build also gates the "affect added" callback differently in several reworked places. Only the
  `setAffectS` early return was backported.
