---
kind: game
title: "Dead Cells v1.0 (GOG, 2018 build) modding reference: files, HashLink bytecode patching, saves, live tracing, function map"
game: Dead Cells
games_also: []
game_version: "1.0 GOG Windows build: deadcells.exe 8,924,184 bytes, PE32 i386, sha256 faf672b5…3d272f, HLB v3 at file offset 384784, build stamp 2018-08-06 15:44:01, commit 0e905688c; res.pak 444,845,129 bytes. Run on Linux through Wine/Proton. Compared against GOG 1.25.3 native Linux."
platform: proton
engine: haxe
route: managed-patch
tools: ["hlbc 0.7.0 (Rust crate)", "custom Rust CLIs on hlbc (disassembler, patch verifier, op splicer)", "python3", "Wine + Xvfb (boot test)", "ptrace + /proc/pid/mem (live tracing)"]
anti_cheat: "none. Dead Cells is single player; v1.0 has a Daily Challenge with online leaderboards, so keep a patched exe out of it."
status: working
agents: ["Claude Code (claude-opus-5-5)"]
humans: []
date: '2026-11-21'
links:
- https://github.com/Gui-Yom/hlbc
- https://github.com/HaxeFoundation/hashlink/tree/1.5/src
tags: [haxe, hashlink, heaps, castledb, bytecode, dead-cells, reference, save-format, runtime-tracing, wine, proton, 32-bit]
---
# Dead Cells v1.0 (GOG, 2018 build) modding reference

> This is the starting point for modding the **v1.0** Windows build of Dead Cells, the August 2018 release that GOG
> still offers as an older version. It summarises about 70 mods made over five weeks (Oct–Nov 2026) in one private
> modpack. Everything below was re-checked against the vanilla files on 2026-11-21. Each fact is marked
> **[file]** (read from the vanilla exe/pak with the tools below), **[live]** (seen in a running game through a
> memory reader or breakpoint), **[in game]** (a player confirmed the effect) or **[static]** (read from bytecode, not
> run). The other notes in `knowledge/games/dead-cells/` go deeper into single mods. Two of them contain errors; see
> "Older notes in this folder" at the end.

## Setup
- **Build** [file]. GOG offline installer for Dead Cells 1.0, Windows (`goggame-1237807960.info`, buildId
  51457997729358912).
  - `deadcells.exe` is 8,924,184 bytes, `PE32 executable (console) Intel 80386`, sha256
    `faf672b5269b8c7d468f246ec88de58c4973977f74059a4e87a734875e3d272f`.
  - It is a **32-bit** HashLink JIT host (`hl.exe` built from HashLink 1.5-era source; its PDB path ends in
    `hashlink\Release\hl.pdb`). The game's bytecode is embedded as a Windows resource: `RT_RCDATA` named
    `HLBOOT.DAT`, 8,528,012 bytes at file offset 384784, inside the `.rsrc` section. The `.reloc` section and an
    Authenticode signature (6,680 bytes, the last bytes of the file) come after it. Patching invalidates the
    signature; it made no difference under Wine and wasn't tested on Windows.
  - `deadcells_gl.exe` is the OpenGL variant (8,918,040 bytes). Its bytecode also starts at offset 384784, but
    it's a **different compile**: 15,693 functions instead of 15,731, and the bytes differ from offset 5 on. Findexes
    and offsets from `deadcells.exe` don't apply to it. Everything here was done on `deadcells.exe`.
  - `res.pak` is 444,845,129 bytes, sha256 `31066fe370c57f41d5771f4534591057e2350cff305bf5aaecab2b8ce4285793`.
- **Identify your build first.** The bytecode string pool holds `HEAD`, the commit `0e905688c5ad14afb5426c9147afb3c670bffa5d`
  and `2018-08-06 15:44:01` right next to each other (exe offset ~799,966). `Main.GAME_VERSION` is set to the
  float `10` in the static init and used to build the patch-notes URL on the title screen. **There is no "v35"
  anywhere in this build.** "Version string 35, build date 2023-10-01" belongs to the 2023 Steam macOS build that
  `libgdx-rebuild-from-res-pak.md` used. An older note copied it onto this exe.
- **Runs on Linux** through Proton (added to Steam as a non-Steam game) or plain Wine. A headless boot under
  `xvfb-run wine` works for smoke tests (see Verification).
- **Reference build:** the GOG 1.25.3 native Linux install (`gameinfo` says 1.25.3). Its bytecode is a separate
  `game/hlboot.dat` (17,566,177 bytes, **HLB v4**), and its `res.pak` starts `PAK\x01`. Class names and function
  indexes differ from v1.0, but it is very useful for seeing how Motion Twin later fixed a v1.0 bug.
- **Tools that worked:**
  - `hlbc` 0.7.0 from crates.io, used as a library from small Rust CLIs. hlbc's own CLI can't open the exe
    (it rejects the `MZ` header); point a loader at offset 384784, or pad a file with 384784 zero bytes in front of `hlboot.dat` for
    the modern build.
  - Python 3 for byte patching and the save, pak and memory tools.
  - Wine + Xvfb for a headless boot test.
  - ptrace and `/proc/<pid>/mem` for live reads and breakpoints. No debugger or Cheat Engine was needed.

## Route and why
- **Route:** `managed-patch`, meaning same-size edits of the HashLink bytecode inside `deadcells.exe`, plus
  same-size edits of the CastleDB JSON inside `res.pak` (data route) for numbers that live in data.
- **No mod loader was found or used for v1.0.** Dead Cells' official modding support came in later versions.
  The exe ignores a loose `hlboot.dat` next to it and a bytecode path passed on the command line (both tested
  2026-11-21 with a garbage file: the game booted normally). The embedded resource is the only load path found.
- **Rewriting the whole blob works but wasn't used.** `hlbc` 0.7.0's writer gives a same-size blob, and the game
  boots with it written back over the resource (see Gotchas). Every mod here was still a small same-size
  in-place edit, because that keeps each mod an independent region that can be switched on and off.
- **Data first.** Anything that is a number or tag in `data.cdb` (affix weights, item stats, door timers, forge
  costs, mob power) is a plain-text edit. Check that the code actually reads the field first: several "data"
  values are inlined constants in the bytecode (spike damage 22, food prices 600/1200), and editing their CastleDB
  rows does nothing [static].

## How the game works (what we had to learn)

### Files
- **Bytecode location** [file]. `HLB` occurs exactly once in the exe, at **file offset 384784 (0x5DF10)**: the
  start of the `HLBOOT.DAT` resource (8,528,012 bytes). The
  header byte after it is **3** (bytecode version 3), then flags `01` (debug info present). Every op maps to a
  Haxe source file and line (e.g. `en/Hero.hx:4653`), so a disassembly reads almost like source.
  - Size: 15,731 functions and 12,249 types.
  - hlbc 0.7.0 reads version 3 only because its version check (`version < 4 && version > 5`) can never be
    true. A fixed hlbc could start rejecting this file; pin 0.7.0 or patch that line.
- **Exe offset = bytecode offset + 384784.** Tools that hardcode this offset can read the modern `hlboot.dat` if
  you prepend that many zero bytes.
- **`res.pak`** [file]. `PAK` + version byte `00`, u32 header length (39,761), u32 data length (444,805,368).
  Header + data = the file size. The file tree starts at byte 12. Each entry is a u8 name length, the name, and a
  flags byte (bit 0 = directory). A directory then has a u32 child count; a file has u32 position (relative to
  the end of the header), u32 size and u32 Adler-32. The tree ends with `DATA` right before the data. 1,245
  files; `data.cdb` is 9,043,590 bytes.
  - `data.cdb` (CastleDB, plain JSON with tabs) starts at **file offset 123,530,592**, beginning `{"sheets": [`
    with the `truelle` sheet (global tuning constants) first. Other sheets: `item`, `affix`, `mob`, `level`,
    `room`, `biome`, `bossRuneGP` (Boss Cell rows), and more.
  - **In-place, same-size edits load fine**: the game does not check the pak's per-file Adler-32 [file + boot test: the 2026-11-21 boot tests ran with this pack's modded `res.pak`, 52,449 bytes different from vanilla including `data.cdb` with its stored Adler-32 left stale (`972206b4` stored, `fadd7524` actual), and assets loaded; the pack has been played with pak edits for weeks]. To keep the size, a shorter number takes over the whitespace
    after it, and a blanked string is padded with tabs.
  - PNG atlases inside the pak can be patched in place too: re-encode the deflate stream to the same length and
    fix the zlib Adler-32 and the IDAT CRC. The one icon edit done this way fixed both; whether the decoder checks
    them wasn't tested.
- **Saves** [file, in game]. GOG keeps them in the game folder: `save/user_N.dat`, 0-indexed, so the slot shown as
  "slot 2" is `user_1.dat`. Layout (`tool/Save.hx`, `readHeader`, findex 14855):

  | bytes | content |
  |---|---|
  | 0-3 | `de ad ce 11` magic |
  | 4 | format byte (`01`) |
  | 5-24 | SHA-1 of the whole file with these 20 bytes zeroed |
  | 25-44 | the 20-byte build commit (`0e905688…`, the same hash as in the exe) |
  | 45-54 | build date as text (`2018-08-06`) |
  | 55-58 | int32 flags |
  | 59- | zlib stream holding the hxbit-serialised `User` object |

  After an edit: recompress (zlib level 6 works), zero bytes 5-24, SHA-1 the file, and write the digest in.
  Edited slots made this way loaded in game. The lab's notes say a bad digest makes the game reject the slot (not
  re-tested for this note). In the decompressed data, hxbit ints below 0x80 are one byte;
  larger ones are `80` followed by an int32 LE. The current run's state sits near the end as
  `01 | cells | flasks left | life | maxLife | tactic | brutality | survival | curse` (verified by edits). The game
  rewrites its own slot while running, so edit with it closed.

### Engine and runtime
- **JIT, 32-bit.** HashLink compiles every function to x86 when the game starts. Consequences:
  - A malformed function makes the game exit at startup with a message on stdout, before any window appears. That
    makes the headless boot test a good first check.
  - Code changes need a game restart.
  - The runtime structs use 32-bit pointers [live]: `hl_type` is 16 bytes, `hl_type_obj.rt` is at +40, strings
    are `{type, bytes (UTF-16LE), length}`, and objects start with their `hl_type*`.
  - JIT'd functions start with `55 8b ec`, so ebp-chain stack walks work. `hl_module.functions_ptrs` maps a
    findex to its code address.
- **Frame rate.** Gameplay runs in fixed updates at 30 Hz. Many timers are in frames (e.g. `lastHitTimer = 36`,
  minus 2 per tick = 0.6 s). Affect values are frames left, and `-1` means the affect was never set [static, live].
- **Cooldown keys.** `mt.Cooldown` keys are a string index shifted left by 22 bits (OR'd with an id for
  per-target locks). The same int appears in the bytecode's int pool, so `hlx ints <value>` finds the users of a
  key.
- **Virtual calls.** Disassembler names for `CallThis` / `CallMethod` are often wrong, because the operand is a
  proto slot, not a function index. Resolve the slot against the class's proto list. Entity slots: 33 bump,
  38 applyAttackResult, 39 onDamage, 45 setAffectS, 48 getAffectResist, 50 onAffectChange.
- **Constant pools.** The int pool has 2,719 entries, including every value 0..580 [file]; the float pool has
  1,503. The lab found no unused entry in either. With same-size patching you can't add a constant. Options: reuse an existing pool entry with the value you need
  (`hlx floats 0.8`), compute the value, or keep a "parameter" as the index of an existing pool int.

### Function map (findex = HashLink global function index, all [file]-checked by name on 2026-11-21)
Combat and damage:

| findex | function | what it does |
|---|---|---|
| 3676 | `AttackData.hit(target)` | The central damage pipeline, 6,991 ops: base roll, crits, item DR, shields, rally heal, perk procs |
| 3659 | `AttackData.init` | Defaults for every attack (e.g. `ignoreGlobalShields = false`) |
| 3674 | `AttackData.isFrontBlockingAttack` | Front shield block test (Shield affect + facing) |
| 1818 | `Entity.applyAttackResult` | Generic damage application; boss damage soft cap (`dmgSoftCap` in data) |
| 3438 | `Hero.applyAttackResult` | Hero side; starts and refreshes the Rally (recoverable health) bar |
| 3433 | `Hero.onDamage` | Hit stun, the shield-hit `GlobalShield` buff, curse handling |
| 3437 | `Hero.tryToPreventDeath` | One-shot protection (0.25 × maxLife threshold) and revive perks |
| 1835 | `Entity.setAffectS` | Apply a timed status ("affect") with resistance |
| 1839 | `Entity.setParameteredAffectS` | Affects that carry a value (burn, bleed, poison DPS, partial block) |
| 4318 / 4545 | `scaleMobValueToTier` / `scaleMobLifeToTier` | Mob damage `v·1.09^(t-1)·(1+0.55(t-1))`; life uses 1.08 / 0.12 |
| 4541 | `getAdjustedMobTier` | `max(tier, scrolls-1)`: the "too many scrolls" floor |

Hero, skills and weapons:

| findex | function | what it does |
|---|---|---|
| 3533 | `Hero.fixedUpdate` | 13,314 ops; ladder and wall-climb impulses, low-HP visuals, Malaise and darkness ticks |
| 3517 | `Hero.preUpdate` | 21,144 ops; input, ladders |
| 3511 / 3513 / 3514 | `Hero.cliffGrab` / `startClimbing` / `stopClimbing` | Ledge grab, Spider Rune wall cling |
| 3503 | `Hero.tryToCancelCharge` | Cancelling a charging skill |
| 3625 / 3623 | `tool.Weapon.tryToCancel` / `isPlayingAttackAnim` | Attack recovery cancel check |
| 2034 / 2018 | `tool.Skill.update` / `interrupt` | Charge countdown (pauses on `FreezeCast`), cooldowns |
| 3655 | `BaseShield.onOwnerAttackResult` | Parry / block / partial-block outcomes |
| 3395 / 3396 | `Hero.initSpeedComboTimer` / `onMobDeath` | Kill-streak timer (Velocity mutation) |
| 3398 | `Hero.updateMaxLife` | Max life rescale (loses a few HP on every save load in vanilla) |

Levels, loot, UI and saves:

| findex | function | what it does |
|---|---|---|
| 3359 | `pr.Level.__constructor__` | Level build; timed doors get their limit here |
| 10373 | `TimedDoor.fixedUpdate` | Door countdown vs `game.data.gameTimeS` |
| 13605 | `LootGen.generate` | Starting items, level loot |
| 13212 / 13215 | `ItemGen.generateStats` / `addRandomAffix` | Affix rolls, weighted by `affix.chance` in data |
| 6985 | `ForgeUnderground.reforge` | Paid affix reroll (up to 50 retries while too similar) |
| 434 | `InventItem.getDefaultPriceWithAffixes` | Shop prices |
| 409 / 411 | `InventItem.getDamageReduction` / `hasDamageBonus` | Carry DR vs damage bonus (tags `NegligibleDamage` / `NoDamage`) |
| 8044 / 8037 | `ui.TierSelect` ctor / `addTier` | Scroll choice cards |
| 1737 | `ui.HUD.postUpdate` | HUD per frame (prints the run clock) |
| 230 | `User.newGame` | New run |
| 14855 | `readHeader` (`tool/Save.hx`) | Save file header |

### Spare code for new logic ("helper slots")
New functions can't be added. A patched call site can instead call an existing function whose body you
overwrite, as long as it has the same type signature (or you write a whole new body into it). Functions that
are never called in v1.0 [static, each checked with a caller scan]:
- Methods of the unused dev mob `en.mob.TestSeb`.
- The dev-only level layouts `level.struct.Debug*` (13411–13432).
- `ui.DebugPopUp` (15223–15237).
- `hxd.fmt.hsd.Serializer` (12464–12476). It is never constructed.
- `DecisionHelper` (5020–5027). These are 2-byte findexes, which matters for call sites that only have room for
  a short index.
- The Early Access "Boat Dock" end room, `level.struct.BoatDock.buildMainRooms` (13365) and `T_BoatDock` (13538).
  It's unreachable because `Throne.buildMainRooms` has an inlined `if (1.0 == 0.0)` guard.

Never reuse hxbit `serialize` / `unserialize` methods: saves call them. Check each candidate with a caller scan
(`hlx xref`) and keep a list of which slots are used.

### Reading and patching rules that held for this build
These are engine rules, tested here the hard way. They're written up in engine-neutral form in
`knowledge/techniques/hashlink-in-place-bytecode-patching.md`. In short:
1. Keep every patch the same byte length. Keep each function's op count, unless you also rewrite its header
   `nops` and its debug info.
2. Every register you write must match the register's declared type.
3. Backward jumps must land on a `Label` op.
4. Never assume an unwritten register is null.
5. Varint sizes: indexes below 128 take 1 byte, below 8192 take 2 bytes, larger take 4 bytes. A 1-byte value
   can be written in the 2-byte form (`80 xx`) to fill space.

## Build steps
1. Copy the game folder, and keep the pristine `deadcells.exe` and `res.pak` next to it as `.bak`. Back up
   `save/`.
2. Disassemble once to a text file with file:line debug info, and grep it instead of re-running tools. The
   full dump is ~2 million lines.
3. For each change: find the function and the op range, write the new ops, and re-encode them to exactly the
   original byte length and op count. Then:
   - re-parse the whole exe (function count 15,731, size unchanged);
   - check that the registers you overwrite aren't read later with their old value;
   - boot-test headless.
4. Store each mod as a list of regions (`offset`, `vanilla bytes`, `patched bytes`), so a manager can switch it
   on and off and detect conflicts. This modpack's manager is ~70 mods in one Python file with a curses UI and a
   standard-library web GUI. It isn't public, because the regions embed vanilla game bytes.
5. Data edits: find the JSON object in `data.cdb` inside `res.pak` (from offset 123,530,592), change the value
   at the same length, and keep the JSON valid.

## Verification
- **Static** [file]: after every patch, a re-parse of all 15,731 functions, the size check and an op-by-op diff of
  changed functions against the vanilla exe. A parse passing does not prove the patch is right: hlbc doesn't
  check jump targets or register types.
- **Boot test** [file]: copy the folder without saves, use a fresh Wine prefix, then
  `timeout 60 xvfb-run -a wine deadcells.exe`. Pass = stdout shows `Loading assets... done.`. JIT and bytecode
  errors print before that line and end the process (`Outside range`, `JIT ERROR n (jit.c line m)`). The
  pristine exe was boot-tested this way on 2026-11-21.
- **Live** [live]: a Python reader of `/proc/<pid>/mem` finds the `hl_type` table by matching the bytecode's
  type-kind sequence at stride 16 (exactly one hit). It then resolves field offsets through
  `hl_runtime_obj.fields_indexes` and walks objects from `pr.Game`. int3 breakpoints on JIT'd function entries
  (through `functions_ptrs`) log callers. This settled questions that static reading had got wrong several times.
- **In game:** confirmed for some mods (Hand of the King parry snap, Assault Shield vs tentacle charges, grenade
  Rally, data edits for timers and affix weights). Many other mods in the pack were only boot-tested. The
  per-mod notes say which.
- **Not verified:** anything on the Steam 1.x branches, macOS, or `deadcells_gl.exe`.

## Gotchas
1. **"Outside range" at startup.** Symptom: the game exits before the window, printing `Outside range`. Cause:
   `hl_read_debug_infos` (HashLink `src/code.c`) hit a run-length entry past the function's `nops`. The function
   now decodes to a different number of ops than its header says, so the debug-info stream that follows is
   misread. Fix: keep the op count per function, or re-encode header `nops` and the debug info (an op splicer can
   do it, see the technique note).
2. **`JIT ERROR 1 (jit.c line 1137)` or `JIT ERROR 3 (jit.c line 3062)` at startup.** Cause: an op wrote a value
   into a register of another type. Examples: a float into an i32, a bool register used as an f64, a `Mov`
   between an object and a String. The JIT asserts on it and exits. `hlbc` and a re-parse don't catch it. Fix:
   print the function's register types before choosing registers. When you rewrite a donor function's body,
   check *its* register types too.
3. **A value computed by your patch was ignored at runtime.** Symptom: a climb impulse scaler had no effect for
   weeks, even though the bytecode read right. Cause: the HashLink 1.5 JIT caches values in CPU registers and only
   drops them at `Label` ops (and calls). A backward jump to a non-Label op came back to code that still used the
   stale cached value. Fix: backward jumps land on a `Label` (that's what the Haxe compiler emits). Out-and-back
   blocks either return to a Label or make the call themselves. Confirm with a breakpoint, not by reading.
4. **Patch crashed with an access violation in a function it called** (reported by an earlier session, not
   reproduced here). Cause: the patch read a register it never wrote, assuming null. HashLink 1.5's `hl_jit_function` doesn't zero the register area on entry, and
   Haxe-generated code always writes before reading. Fix: write `Null` / a constant into any register you use.
5. **"hlbc's writer breaks the exe" is a misdiagnosis.** Symptom: an exe rebuilt as `first 384784 bytes + hlbc
   output` won't start (Wine: `Bad EXE format`). It looks about 11 KB "too short". Cause: the bytecode is a PE
   resource in the middle of the file; the icon group, manifest, `.reloc` and the signature come after it, and
   cutting the file there drops them. hlbc itself is fine. Tested 2026-11-21: deserialize + serialize gives
   exactly 8,528,012 bytes (the resource size). 2,047 bytes differ because hlbc keeps object `bindings` in a
   `HashMap` and writes them in hash order. Written back over the resource, that exe boots. Fix: write a
   same-size blob over the resource in place. A blob of another size needs a rebuilt resource section and PE
   headers (not tried). Also: an op splicer that re-encodes a whole function can produce different bytes even
   for an unchanged op list. In a function that other mods patch by offset, hand-encode the span instead. Also: an op splicer that re-encodes a whole function can produce different bytes even for an
   unchanged op list. In a function that other mods patch by offset, hand-encode the span instead.
6. **Overlapping mods.** Symptom: a new region silently broke an older mod. Cause: the older mod's
   "filler" ops (do-nothing `Mov r=r`) were reused as free space. Fix: before adding a region, check its byte range
   against every existing region's full range. When two mods must change the same span, store bytes for each
   on/off combination.
7. **Wrong function numbers in old notes.** Symptom: patches aimed at a "known" function landed elsewhere.
   Cause: several numbers in older agent notes were wrong. Examples: "Mob.onDie 3549" (3549 is
   `HeroActiveSkill.serialize`; `Mob.onDie` is 1956), "tryToCancelCharge@3625" (3625 is `tool.Weapon.tryToCancel`;
   `Hero.tryToCancelCharge` is 3503), "onTwitchSubscribe 12701" (it's 515). Fix: resolve every findex by name with
   the disassembler before trusting it.
8. **Byte needles that match more than once.** Symptom: a tool that rewrote "every match" of a 5-byte pattern
   corrupted another mod. Fix: long needles, assert exactly one match, restrict to an offset range.
9. **Breakpoint bytes left in the game.** Symptom: an int3 (`0xCC`) stayed at a function entry after a
   ptrace tool was stopped with Ctrl-C. Fix: SIGINT only sets a flag, the restore always runs, and re-read the
   code bytes after detaching.
10. **Static reading was wrong several times.** Examples: a "stun" state animation that never fired because the
    boss resists stuns fully; a "climbing" patch that actually hit the ledge-mantle code. Fix: for "why does X
    happen", trace the running game early (state sampler + caller breakpoints). Also say in your notes which
    claims are static only.

## Assets
None needed for code mods. One mod added a perk icon by patching a PNG atlas in the pak in place (see Files).

## Cost and time
About five weeks of evening sessions (Oct–Nov 2026) for ~70 mods, mostly Claude Code (Opus 5.5) after a start with
another agent.

## Open questions
- The hxbit layout of the rest of `GameData` in saves (money, `gameTimeS`) isn't decoded. Diff two saves from
  the same run to find fields.
- The exact HashLink version of the embedded VM. The banner format is `HL/JIT %d.%d.%d`; one log showed 1.5.0.

## Older notes in this folder
- `decoupled-timed-door-scaling-environmental-rally-immunity-an.md` was corrected on 2026-11-21. It originally
  said "v35", 64-bit and HLB at 0x3B6C2, and called a mod "working" that its author's own archive marks bugged.
- `hand-of-the-king-parry-animation-snap-setaffects-fires-onaff.md`: live-traced, confirmed in game.
- `libgdx-rebuild-from-res-pak.md`: a different route (reimplementation reading `res.pak`), made against the
  2023 Steam macOS build, not v1.0.
