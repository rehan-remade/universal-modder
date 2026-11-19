---
kind: technique
title: "When the first real run fails, suspect the oracle: re-deriving failures from raw traces and mutating real data"
status: in-progress
agents: ["Claude Code and agents"]
humans: ["DarkameMaster"]
date: 2026-10-10
links: []
tags: [oracle, verification, first-real-run, trace-analysis, mutation-testing, collision, tmodloader, mashup]
---

# When the first real run fails, suspect the oracle: re-deriving failures from raw traces and mutating real data

> An automatic in-game test suite for a tile-collision bridge ran in the real game for the first time and 13 of
> 27 scenarios failed. Most of the collision failures were not bugs of the mod: some were the original game's own
> behaviour that the checker had no name for (a fighter grabbing the edge of a hole), some were a helper that
> returned a cell inside a solid mass, and one scenario was built one tile row off. A different agent proved it by
> recomputing from the raw traces, then showed the corrected checker still catches real fall-throughs by mutating
> copies of the real data. The corrected suite has not been re-run in the game yet.

## When to use it
- You have a scripted scene plus a checker that turns traces into PASS/FAIL, and its first real run fails a lot.
- Before you "fix" the mod to satisfy a checker that has never run against reality, and before you relax the
  checker to make a red run green.
- Any guest-in-host mod where the guest has its own rules (here a fighter that grabs ledges), so "expected"
  behaviour lives in the guest, not in the host's physics.

## How
1. **Triage each failure against the raw traces, by someone who did not write the checker.** Rebuild the world
   from the scenario's operations and the trace's initial grid, then follow the actor's feet frame by frame after
   each edit. Classify every event: lands on the first walkable surface, catches an edge, never fell, moved by a
   special, or really passed through something.
2. **Name the guest's legitimate end states** before judging "fell through" or "kept falling": an edge catch
   (state ids, same hang geometry on every catch), landing on the old level after a special, never leaving the
   ground. A verdict list with only "landed" turns every legitimate behaviour into a failure.
3. **Check the helpers, not just the rules.** The "first floor below" helper had a comment saying it skipped
   solid cells, and code that did not.
4. **Check the scenario's coordinates.** The scenario format defined "origin row 0" as the top row of the floor;
   the harness put the origin one row higher. Replaying the real scenario in a synthetic host at both origins
   reproduced the real failures exactly at the wrong one and passed at the right one.
5. **Mutate real data to prove the corrected checker can still fail.** Copy the real traces and edit them: the
   actor falls through floor B and lands on floor C; it falls forever; it stays standing in the air above the
   hole. A fourth control removes the support from the collision data only. A checker that is green on all of
   them is not a checker.
6. **Write down what the fix gives up.** Accepting an edge catch as a valid end state means two scenarios no
   longer test "lands on the floor below"; keep a scenario that still does.

## Verification
- **Derived from raw traces by a second agent (no game launched):** of the 10 "kept falling" verdicts that were
  visible, 6 were edge catches (fourteen to fifteen frames after the break, the same hanging geometry each time),
  1 never fell, 3 were specials that carried the fighter back to the old level. "Fell through the floor" verdicts
  were false positives of the helper. The five floor-break scenarios pass under the
  corrected checker on the same real data; the ramp scenario still fails, partly for the off-by-one origin
  (reproduced synthetically) and partly for the checker reading the neighbouring column at a half-block edge.
- **Mutations on copies of the real data:** two fall-through mutations fail the corrected checker; the third
  (standing in the air) fails through two other checks, not the one meant for it.
- **Not verified:** the corrected checker and the origin fix in a new real run; that the guest's edge-catch rule
  matches the original game (only that the engine does it consistently, with no sign of a mod bug).

## Gotchas
1. **A legitimate behaviour had no name in the checker.** **Symptom:** "kept falling" after the floor under the
   actor was broken. **Cause:** the actor caught the hole's edge. **Fix:** list edge catches as valid end states,
   and keep a variant with a hole wide enough that an edge catch is impossible (the author proposed holes of 8 or
   more tiles).
2. **A helper returned the interior of a slab.** **Symptom:** "fell through the floor at y A" when the actor stood
   on the real first floor at y B. **Cause:** the helper took the first solid cell below the start without
   checking that the cell above it was air. **Fix:** a floor is a solid cell with air above it; the foot path must
   cross one and not land on it within a window of rows.
3. **The scenario was built one row off.** **Cause:** two pieces of code disagreed on what row 0 means. **Fix:**
   use the same support-row function for every placement, and replay at both values to see which reproduces the
   real failure.
4. **One global tolerance.** **Cause:** the allowed sinking into solids during airborne actions was the largest
   value of any fighter (about 28 px), which lets a fighter that sinks 15.9 px pass when its own real maximum is
   13.6. **Fix:** a per-fighter limit measured from the original recordings (suggested; not implemented).
5. **Cosmetic notes lie too.** **Symptom:** "+42 px on a floor below" printed for a case that landed at the old
   level. **Cause:** the old level was measured mid-jump. **Fix:** measure the reference at the frame the edit
   happens.

## Seen in
- [Super Smash Bros. Melee's engine inside Terraria](../games/terraria/super-smash-bros-melee-s-decompiled-engine-inside-terraria-a.md)
- Related: `oracles-how-agents-know-a-mod-works.md` (the oracle catalogue and its gotchas),
  `collision-and-combat-bridging.md`, and `prove-your-replay-bench-can-fail-mutant-builds-exposed-four-.md`
  (proving a bench can fail with mutant builds).

## Credits
- Built with AI agents: Claude Code and its agents implemented the suite and its checker; a different agent,
  Claude Code, re-derived the failures and ran the mutations. Human direction: DarkameMaster.
