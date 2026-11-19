---
kind: technique
title: "Prove your replay bench can fail: mutant builds exposed four false greens and two false reds"
status: in-progress
agents: ["Claude Code and agents"]
humans: ["DarkameMaster"]
date: 2026-10-10
links: []
tags: [oracle, verification, mutation-testing, bench, replay, determinism, rollback, native-dll, false-green]
---

# Prove your replay bench can fail: mutant builds exposed four false greens and two false reds

> A bench tool that replays 29 real recordings through any build of an engine DLL, plus a soak that checks
> determinism and rollback, passed every good build. An independent agent then fabricated a dozen broken builds
> with exactly one defect each. All twelve failed where they should, but four defects slipped through some mode
> as a pass and two situations made good builds fail until the work folder was deleted. A fix diff closed all six
> on a copy, and a third agent applied it to the real tool and re-ran the mutant matrix. The soak part of that
> last re-run is still running.

## When to use it
- Any gate that decides "this build is safe to merge or install": replay benches, golden-trace comparers,
  determinism soaks, schema checkers.
- Especially when an agent wrote the tool and another agent is asked to verify it. Running good inputs only
  shows that the tool can pass.

## How
1. **Make one-defect builds.** Rebuild the engine with a single, scripted change per mutant, and patch the binary
   for the ones that are not source changes. A useful set: a one-bit change in a physics constant, in the RNG
   step, a crash on call N (caught by the crash guard), an `_exit(0)` on call N, a copy of a state field kept
   outside the rollback memory, uninitialised stack, uninitialised heap, a `rdtsc` bit that feeds the simulation,
   a different state-struct size, a missing required export, a DLL that fails to load, a missing optional export,
   and a stripped binary.
2. **Check that each mutant really changes behaviour.** The first uninitialised-stack mutant did nothing: the
   build flags zero-initialise automatic variables, so the compiler zeroed the array. The working one needed an
   attribute that disables that. A mutant that passes may be a dud, not a hole.
3. **Run every mutant in every mode and option**, including the "faster" ones: `--no-ref`, `--allow-diff`, a
   broken `--ref`, interrupted runs, partial (`--only`) runs, a work folder reused.
4. **Match each failure to its message.** The report must say which recording, frame and field, or which setup
   problem. A failure with the reason "empty log" costs the next person an hour.
5. **Fix with a diff, prove it on a copy, then re-run the whole matrix on the real tool with a contrast run of
   the original.**

## Verification
Synthetic (a headless host, no game). A second agent built 21 DLLs: seven good builds and the mutants.
- Good builds: 29/29 identical and 29/29 equal to the recordings; the report is byte-identical on a repeat
  and works from an empty folder.
- The mutants: the gravity bit fails 24 of 29 at the exact frame with a 1-ULP difference; the RNG mutant
  fails the comparison with the reference even though its own truth check is perfect; the crash and `_exit`
  mutants fail both bench and soak; the out-of-rollback field passes the linear bench (correct) and fails the
  soak's rollback check; the uninitialised-heap mutant passes a clean run and is caught by the soak.

**False greens found:**
| # | Defect | Fix |
|---|---|---|
| V1 | A DLL without the camera API passes the default bench: its camera runs simply run without a camera, and the difference is a note. | Compare the DLL's exports with the reference's; a missing one is a failure even with `--allow-diff`. |
| V2 | With `--no-ref` or `--allow-diff` the RNG and item checks are skipped, so a changed RNG step or a missing item reader passes. | Compare the per-frame seed with the recording's (already computed, never used); fail when fewer frames match than the reference. |
| V3 | The soak did not check the ABI: a state struct of 116 bytes instead of 112 passed. | The same ABI check the bench does. |
| V4 | A binary without its symbol table silently turns the rollback check off with a warning, then prints `SOAK PASS ... 0 rollback checks`. | Fail when rollback was requested and zero checks ran. |

**False reds that persisted until the work folder was deleted:**
| # | Defect | Fix |
|---|---|---|
| R1 | The reference's cache key was written before its runs finished, so after an interrupted run every later run said "references up to date" and failed. | Write the key when all reference runs have completed. |
| R2 | A partial (`--only`) run deleted the reference outputs but not the key. | Delete the key too (and the calibration key). |

On a copy, with the fix diff: every false green became a failure with a specific message, R1 and R2 became passes,
and the good builds gave the same numbers as before. A third agent then applied the diff to the real tool and re-ran
the bench matrix, finding every mutant behaving correctly and confirming R1 and R2 against the original tool as a
contrast run.

**Not verified:** the final soak runs on the patched tool (waiting for a free machine); whether the recordings
themselves are right (the tool takes them as truth); `--no-ref` still cannot check the RNG, which is why the
documentation now says it is not the standard check.

## Gotchas
1. **The first "uninitialised" mutant passed.** See How, 2.
2. **`wsl.exe` swallows standard input.** **Symptom:** a loop over a list of runs executed the first one and
   silently skipped the rest. **Cause:** the first run that compiled the host read the list from the loop's
   stdin. **Fix:** `< /dev/null` on every call.
3. **The soak never said which step first differed.** **Cause:** the script grepped for `byte N`; Git Bash's
   `cmp` prints `char N`. **Fix:** match both.
4. **Resource limits produced fake bugs.** **Symptom:** a soak plus two benches at once, with other jobs on the
   machine, gave 112 "setup problems" and one spurious difference (`Win32 error 1455`, `fork: Resource
   temporarily unavailable`). **Cause:** a soak of 14 jobs commits hundreds of MB each. **Fix:** never run two
   soaks at once, and say so in the tool's documentation.
5. **A failure without a reason.** Setup failures before the log header went to stdout only and the script
   deleted the empty log, so the report said "empty log". **Fix:** write them to the log.

## Seen in
- [Super Smash Bros. Melee's engine inside Terraria](../games/terraria/super-smash-bros-melee-s-decompiled-engine-inside-terraria-a.md)
- Related: `bit-exact-decomp-ports-reproduce-the-original-compiler-s-and.md` (the bench's recordings),
  `oracles-how-agents-know-a-mod-works.md`, and `when-the-first-real-run-fails-suspect-the-oracle-re-deriving.md`
  (re-deriving first-run failures from raw traces).

## Credits
- Built with AI agents: an agent wrote the tool; a different agent, Claude Code and its agents, fabricated and ran
  the mutants and wrote the fix diff; a third, Claude Code and its agents, applied and re-ran it. Human direction:
  DarkameMaster.
