---
kind: technique
title: "Bit-exact decomp ports: reproduce the original compiler's and math library's floating point (and the oracle's own patches)"
status: in-progress
agents: ["Claude Code and agents", "Grok"]
humans: ["DarkameMaster"]
date: 2026-10-10
links:
  - https://github.com/999sian/melee-pc
  - https://github.com/doldecomp/melee
  - https://github.com/project-slippi/slippi-ssbm-asm
  - https://github.com/altf4/libmelee
tags: [decomp, port, floating-point, float32, fma, fmadds, paired-singles, mwcc, msl, musl, mingw, bit-exact, trace-replay, determinism, oracle, slippi, gecko, gamecube, powerpc]
---

# Bit-exact decomp ports: reproduce the original compiler's and math library's floating point (and the oracle's own patches)

> A decompilation rebuilt with a modern compiler for x86-64 runs the right logic but rounds differently from the
> original console build, and in a physics-heavy game one ULP grows into a different action a few hundred frames
> later. Making the Melee-in-Terraria engine replay real recordings bit for bit took three floating-point fixes
> (the C runtime's FMA, the original compiler's fusions, the original math library) and three that only looked
> like rounding drift: a field the decomp declares with the wrong type, a patch the oracle's emulator applies to
> the game, and things a headless host forgets to run. The replay bench went from 0 to 29 of 29 recordings.

## When to use it
- You embed or port a decomp (`decomp-recomp` route) and need it to match recordings of the original exactly.
  Netplay with rollback, shared replays or a "1:1" claim all need this.
- A replay matches for hundreds of frames, then one float field is off by 1-3 ULP while every other field was
  bit-exact the frame before.
- Not needed if "close enough" is the goal: a port that drifts by a ULP still plays fine. It just can't share
  replays or rollback with the original.

## Setup (where this was measured)
- Original: Super Smash Bros. Melee NTSC-U 1.02 (GameCube, PowerPC "Gekko"), built with Metrowerks CodeWarrior
  (MWCC) and its MSL C library.
- Port: [melee-pc](https://github.com/999sian/melee-pc) at commit `e83383539a4fd06e9bd8b28c270b3d1ecc7d3be3`
  (on [doldecomp/melee](https://github.com/doldecomp/melee)), built as a Windows DLL with
  `x86_64-w64-mingw32-gcc` 13-posix in WSL Ubuntu 24.04, `-O2 -ffp-contract=off`, no `-m` flags (so no inline FMA
  instructions). Linux builds used gcc 13.3.0.
- Truth: `.slp` recordings from Slippi Dolphin 3.6.4 driven by [libmelee](https://github.com/altf4/libmelee)
  0.47.3. `.slp` stores per-frame state as raw float32, so a comparison can be bitwise. 29 recordings: one
  scripted recording per fighter (26, plus a Link pilot), each 2,952 compared frames, plus two earlier Mario
  recordings.
- The original executable (`main.dol`), read with an own PowerPC disassembler and a small interpreter that follows
  Dolphin's floating-point rules. Every player needs their own copy of the game.

## How

### 1. Get an oracle that sees bits, then localise
- Replay the recorded inputs into the port, re-seed the RNG every frame from the recording, and compare every
  state field bitwise per frame, for both ports. Report the **first** diverging frame and field: later
  differences are mostly consequences, and a comparator that prints only the first failure hides a second,
  independent one (Kirby had two).
- At the first divergence, find the one computation whose inputs were bit-exact and whose output isn't. Then
  run a **causal experiment**: build a copy with only that change toggled. If the divergence comes and goes
  with it, it's the cause. Every fix here was kept only after that check.
- Calibrate the bench's start, not just its inputs. The idle second fighter's animation phase depends on how
  many neutral frames the bench plays before replaying, and hurtboxes follow the animation, so one hit that
  connected in Melee missed in the bench. Choosing the neutral-frame count per recording so the idle fighter's
  action frame matches fixed it, and the per-frame RNG seed match rose from about 97.2% to 99.6%.
- Keep the "same on Linux and Windows" check, but don't mistake it for fidelity: the port's musl trig was
  deterministic on both platforms and still wrong against the original.

### 2. The C runtime's `fmaf` may not be fused
- The port emulates PowerPC `fmadds`/`fnmsubs` (computed exactly, rounded **once** to single precision) with
  `fmaf`. On mingw-w64 that resolves to libmingwex's `fmaf`, which splits the operands and adds partial
  products with ordinary single-precision instructions, rounding several times. The visible symptom: Final
  Destination's floor normal came out one ULP above 1.0 instead of one below, and positions drifted from
  frame 1529 of a two-Mario recording.
- How wrong it is, measured by a second agent against the CPU's own hardware FMA: on 40 M Windows inputs (5 M in
  each of 8 distributions) mingw's `fmaf` disagreed on 4-30% depending on the distribution, and on 24.6% of
  inputs shaped like the game's own two call sites (a reciprocal-square-root refinement and a squared-magnitude
  sum). The implementing agent separately measured 23% on the refinement step alone.
- `(float)fma((double)a, (double)b, (double)c)` is close but not exact. The product of two floats fits in a
  double; the sum doesn't always, so it rounds twice. Counterexample: a = 1 + 2⁻²⁰, b = 0.5·(1 − 2⁻²⁰),
  c = 8388609; the exact value is 8388609.5 − 2⁻⁴¹, which rounds to 8388609; the double route gives 8388610.
  It fails rarely on random inputs and on 30.5% of a near-tie set (Gotcha 4).
- **What worked:** compute the product exactly in double, add in double with **round-to-odd** (TwoSum gives the
  exact error; if it's non-zero and the result's last bit is even, step one ULP towards the exact value), then
  round once to float. Rounding to odd at 53 bits and then to nearest at 24 bits (53 ≥ 24 + 2) equals one
  correct rounding, with no FMA instructions needed. The second agent found it bit-identical to the hardware FMA
  on all 240 M of its inputs (200 M on Linux, 40 M on Windows), apart from NaN results, which it
  compared as NaN against NaN with different payload bits in about 173,000 cases.

### 3. Reproduce the original compiler's fusions, statement by statement
- MWCC turned some `a*b + c` and `c − a*b` source statements into `fmadds`/`fnmsubs` (one rounding). A port built
  with `-ffp-contract=off` rounds twice there.
- **Don't reach for the host compiler's contraction.** GCC with `-mfma -ffp-contract=fast` fuses *different*
  subexpressions: it duplicated products used twice and fused each copy, where MWCC kept them as separate
  multiplies and fused only the final chain of single-use products. Contracting the whole game changed nothing
  beyond the statements that mattered, and even `a·a + b·b` fuses the other way round in GCC.
- **What worked:** build-time scripts copy the affected source files and rewrite only the fused statements to
  call the single-rounding helper; the upstream sources stay untouched. Confirm each fusion in the original
  executable's disassembly: the instruction and which registers hold which operands. Found this way:
  - the scene graph's animation curves (linear keys and the Hermite spline): walk and dash root motion. The
    oracle discriminates the form: fusing in the other order fails every recording, sometimes earlier than no
    fusion at all;
  - the knockback formula, the airborne knockback decay, and four more in the physics update (knockback
    magnitude, shield-knockback decay) that no recording exercises, so they were proven synthetically;
  - Pikachu's and Pichu's up-special (10 fusions);
  - Link's hookshot chain: 112 fused multiply-adds in the original (two for each of 26 squared lengths, one for
    each of 60 link placements) and an interpolation.
- **Hand-written paired-single code counts too.** The original's matrix concatenation (`PSMTXConcat`) is
  assembly on the Gekko's paired-single unit: per element, one multiply and two fused multiply-adds, each
  rounded once (one more for the translation). The port uses the SDK's plain-C version. Link's hookshot
  recording needed **both** this and the hookshot fusions; either alone still failed (+1 and +3 ULP).
- The first round of patches was an inference validated only by the oracle; reading the executable later
  confirmed it. Say which one you have.
- Known and not patched: 86 single-precision fusions in the camera code. Nothing in the 29 recordings depends
  on them yet. A later inventory counted 1,875 fused operations in 598 gameplay functions that the port still rounds
  twice; no recording flags any of them either.

### 4. Use the original math library, not the port's
- The port sent `sinf`/`cosf`/`tanf`/`atanf` to musl. The game runs Metrowerks MSL's `sinf`/`cosf`/`tanf` plus its
  own `atanf` (which its `atan2f`, `acosf` and `asinf` call).
- MSL's `cosf` has a small-argument path that leaves out a π/4 factor that its `sinf` keeps, so cos(π/2) in the
  game differs from musl's by a ratio of exactly 4/π. That moved aerial up-specials (stick straight up →
  `atan2f` gives exactly π/2 → speed × cos(π/2)). cos(π/4) is also one ULP apart, which moved laser knockback.
- **What worked:** transcribe each routine from the executable instruction by instruction into C, with the same
  operation order and single-precision rounding, and validate it by running the original machine code in the
  interpreter against your C: random values, ±40 ULP around each kπ/4, huge and tiny values, ±0, NaN. A second
  agent's interpreter found 0 differences on 18,152 inputs per function (musl, as a control, differed on 5,525
  to 10,941). Link it in place of the port's libm for both the game and its vector library.

### 5. Divergences that only look like rounding
- **A field the decomp declares with the wrong type.** Kirby's inhale has a minimum loop length. The decomp
  declares the attribute as a 32-bit integer and stores it into a 16-bit field, which keeps the *low* half; the
  original loads the *high* half as a signed 16-bit value. Melee read 40 frames, the port 0, and Kirby left his
  inhale on the first frame B was released: a different action for 154 frames. **Lesson:** when a whole action
  differs rather than a ULP, read the width of the original's load instruction. The fix is a build-time patch
  that reads the high half.
- **The oracle isn't the vanilla game.** Slippi's Dolphin applies `$Required` Gecko codes (their sources are in
  [slippi-ssbm-asm](https://github.com/project-slippi/slippi-ssbm-asm)). One of them, `BrawlOffscreenDamage`,
  replaces the 1%-per-second off-screen damage check: Melee's own version asks the HUD magnifier; Slippi's tests
  the fighter's position against the stage's camera bounds. Kirby took the damage one frame earlier in the
  truth than in the port.
  - Measure before you theorise: the `.slp` records the fighter's own "off-screen" flag. Compared with the
    engine's camera result, it matched in all 159,312 comparisons (the implementing agent's count; a second
    agent's method counted 165,970, also with no differences), which refuted the camera-precision hypotheses and
    pointed at the code.
  - Fix: transcribe the code as a switchable build tag (on by default), and **decide the target explicitly**.
    Here it is Melee 1.02 plus Slippi's required codes, the way Melee is played online today, **minus UCF**:
    the community controller fix (dashback, shield drop, SDI...) sits in the same required block, and the
    project removed its 9 code blocks from a lab copy of the emulator's game settings, after checking that the
    edit removed exactly those lines.
  - Inventory every code the oracle's emulator applies. Several more change the simulation (wobbling, a freeze
    glitch, dead-upward fall physics) or only its determinism (the Ice Climbers' partner AI); none of the 29
    recordings exercises them yet.
- **Things a headless host forgets to run.** A stub returning (0, 0) for a pure-arithmetic screen projection
  made every fighter "on screen"; a stage object whose only job is to tick a collision counter every frame
  changed which floor routine airborne fighters use; an uninitialised crowd-reaction pointer crashed two
  fighters late in their recordings. Details in the engine-hosting note.

### 6. Make bit-exact the default build
Each floating-point and Slippi fix is a named, switchable tag, and the default build has all of them on. With
the four floating-point switches off, a second agent got 0 of 29 recordings (26 of 58 ports); with them on, 29
of 29.

## Verification
The replay bench (a headless host, not the final game) replaying the 29 real recordings on both ports. Each
stage was re-run by a different agent with its own host, `.slp` reader and comparator, and each causal
experiment (remove one fix) brought its divergence back. The bench itself was later checked with deliberately
broken builds (`prove-your-replay-bench-can-fail-mutant-builds-exposed-four-.md`), which found and closed four
false greens.

| Fixes in the build | Recordings bit-exact on both ports |
|---|---|
| port as shipped (mingw `fmaf`) | 0: every per-fighter recording failed at frame 240 |
| single-rounding `fmaf` + animation-curve fusions | 7 of the 22 fighters recorded then |
| + stage counter, crowd init, blast zones (not float) | 18 of 27 |
| + MSL trig + knockback fusions | 23 of 27 |
| + physics and up-special fusions, Melee's camera in the engine, calibrated bench start | 27 of 29 (56 of 58 ports) |
| + Kirby's inhale field, Slippi's off-screen rule, hookshot fusions + paired-single matrix concat | **29 of 29 (58 of 58 ports)**, with and without the camera API |

**Not verified:**
- The truth is Dolphin, not a GameCube. Dolphin may emulate `fmadds` as a double FMA rounded to single with one
  operand pre-rounded to 25 bits, which differs from a true single rounding only on near-ties. None showed up;
  no independent check has measured it.
- The reciprocal-square-root estimate (`frsqrte`) is emulated as an exact `1/sqrt`, and the port's own
  refinement skips Dolphin's 25-bit operand rounding (4% of results on [1, 4) differ). Neither has been tied to
  a divergence.
- mingw's `sqrt`, `pow`, `exp` and `logf` also differ from glibc by 1 ULP on a small fraction of inputs
  (implementing agent's measurement); no recording has flagged them.
- For the Ice Climbers the bench compares the leader only; Nana's own track is not part of the 58 ports.
- Only the bottom blast zone and one stage (Final Destination) are exercised; one machine and CPU.

## Gotchas
1. **Calibrating physics against drift.** **Symptom:** a walk speed looks wrong after 900 frames. **Cause:**
   one ULP compounding, or a shifted recording (Melee ignores the pad for about 100 entry frames). **Fix:** find
   the first diverging frame and field before touching any constant.
2. **"Deterministic" taken for "faithful".** **Symptom:** Linux and Windows builds agree bit for bit, so the port
   seems right. **Cause:** both used the same wrong library. **Fix:** compare against the original's recording,
   not against another build of the port.
3. **The host compiler's FMA flags made it worse in places.** **Cause:** a different fusion policy from the
   original compiler's. **Fix:** fuse exactly the statements the original executable fuses.
4. **`(float)fma(double…)` passes random tests.** **Cause:** double rounding only bites on near-ties, which random
   inputs rarely hit. A second agent's test against the CPU's hardware FMA found 3 failures in 25 M random-bit
   inputs on Linux and 1 in 5 M on Windows, against 30.5% of its own near-tie set. **Fix:** test adversarial
   near-tie inputs, or use round-to-odd.
5. **A fix that only the oracle supports.** **Cause:** no disassembly to hand. **Fix:** label it as inferred, and
   confirm it later from the original executable.
6. **A whole action wrong for 154 frames, chased as drift.** **Cause:** a decomp field type that keeps the wrong
   half of a 32-bit attribute. **Fix:** compare load widths in the original.
7. **One frame of difference in off-screen damage, chased as camera precision.** **Cause:** a Gecko code in the
   oracle's emulator. **Fix:** read the emulator's game settings and the recording's own state flags before
   theorising.
8. **A hit that connects in Melee and misses in the bench.** **Cause:** the idle fighter's animation phase
   (and so its hurtboxes) came from the bench's start, not from the recording. **Fix:** calibrate the
   neutral-frame count per recording.

## Seen in
- [Super Smash Bros. Melee's engine inside Terraria](../games/terraria/super-smash-bros-melee-s-decompiled-engine-inside-terraria-a.md)
- Related: `hosting-a-decompiled-console-engine-as-a-native-dll-inside-a.md` (the build-time patch mechanism and
  the bench as a merge gate), [Eye of Cthulhu RL agent](../games/terraria/eye-of-cthulhu-rl-agent.md) (float32
  constants in a C#-to-numba port), `engine-recreation-measures-and-fidelity.md` (a deterministic build isn't a
  deterministic game), `oracles-how-agents-know-a-mod-works.md` (trace replay) and
  `prove-your-replay-bench-can-fail-mutant-builds-exposed-four-.md` (proving the bench can fail).

## Credits
- [doldecomp/melee](https://github.com/doldecomp/melee) and [melee-pc](https://github.com/999sian/melee-pc):
  the code being matched.
- [Project Slippi](https://github.com/project-slippi) (Slippi Dolphin, the `.slp` format and the Gecko codes in
  [slippi-ssbm-asm](https://github.com/project-slippi/slippi-ssbm-asm)) and [libmelee](https://github.com/altf4/libmelee)
  by altf4: the oracle. [Dolphin](https://dolphin-emu.org/) underneath it. [mingw-w64](https://www.mingw-w64.org/).
- Built with AI agents: Claude Code and its agents implemented and verified (each result re-run by a different
  agent); Grok, as a read-only second reviewer, independently confirmed the Kirby field and the
  Slippi code and found that the paired-single fix was off in the default build.
