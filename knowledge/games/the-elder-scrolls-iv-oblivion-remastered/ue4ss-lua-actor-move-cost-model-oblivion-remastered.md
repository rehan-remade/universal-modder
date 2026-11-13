---
kind: game
title: "UE4SS Lua cost model for moving many actors in Oblivion Remastered"
game: "The Elder Scrolls IV: Oblivion Remastered"
games_also: ["Red Faction: Guerrilla Re-Mars-tered"]
game_version: "Oblivion Remastered 1.512.105 (UE5.3.2)"
platform: proton
engine: unreal
route: loader-api
tools: ["RE-UE4SS 3.0.1", "Proton 11.0", "perf-house.sh", "bench-calls.lua", "gamescope"]
anti_cheat: "none"
status: in-progress
agents: ["Antigravity (Gemini 3.8 Flash High, first draft of everything above Gotcha 5)", "Claude Code (Sonnet 5.5; Gotchas 5 to 8, and the audit of every claim on 2026-11-05, see docs/kb-drafts/AUDIT.md)"]
humans: []
date: 2026-11-05
links: []
tags: ["ue4ss", "lua", "performance", "profiling", "actors", "staticfindobject", "out-parameters", "cost-model"]
---

# UE4SS Lua cost model for moving many actors in Oblivion Remastered

> Measured costs of moving about 1,500 actors every pass from RE-UE4SS Lua in Oblivion Remastered (UE5.3.2, lab copy,
> headless). Labels: [real run] an evidence file records it; [source] code read; [inferred] reasoned, not tested;
> [unverified] no evidence found. The first unoptimised collapse ran at 3.0 fps (minimum 0.3) with 907 ms per second of
> game-thread time in the mod [real run, `evidence/perf-phase0-run1.txt`]. Caching actor pointers (a `StaticFindObject` by path
> cost about 5 ms per call) removed most of it. With the hidden second game capped at 60 fps, four valid collapse runs
> measured 36.3 to 44.0 fps (minimum 33 to 37) [real run]. Lua at 10 Hz still looked choppy (74 percent frozen frames), which
> is why a native mover was built afterwards (see the ProcessEvent note). The 30 fps "gate" was a plan target; the user
> later said frame rate gates nothing for now (`CHECKPOINT.md`, 2026-11-03).

## Setup

- **Target Engine:** Unreal Engine 5.3.2 (shipping build 1.512.105), Win64 running under Proton 11.0 on Linux.
- **Scripting Layer:** RE-UE4SS v3.0.1 Beta (Git SHA bc66bb1 per its log) [real run]; the Lua 5.4 version is [unverified].
- **Measurement hardware:** Linux, AMD RX 9070 XT GPU [real run, `docs/PERFORMANCE_PLAN.md`], headless under gamescope. The CPU model is [unverified].
- **Test Workload:** 1,479 individual static mesh actors for the Chorrol house
  (`BP_ChorrolHouseUpper01`).
- **Timing Harness:** Per-section microsecond timers wrapped around bridge parsing, actor lookups, transform updates,
  rotation calculations, NPC sweeps, and GC operations (`tests/perf-house.sh`, `tests/lua/bench-calls.lua`).

## Route and why

- **Route:** In-engine scripting via RE-UE4SS Lua (`loader-api`).
- **What actually happened [real run, `docs/PERFORMANCE_PLAN.md`]:** Phase 0 measured per-call costs before any native work.
  The engine calls were cheap (about 36 ms per second for 1,479 moves at 24 microseconds); about 800 ms per second went
  into the mod's own per-record Lua work. Cheap Lua fixes cleared the plan's 30 fps target in the valid runs. A native
  `ProcessEvent` mover was still built in Phase 2 for smoothness, and it is on by default; so the first draft's line
  "cleared the gate without requiring a native rewrite" is true for fps only.

## How the game works (what we had to learn)

Measurements found four bottlenecks:

### 1. Path lookups via `StaticFindObject` (about 5 ms each) [real run, `evidence/perf-phase0-run2.txt`]
- In Phase 0 run 1, the collapse cost 907 ms/s of game-thread time (pieces 796 of it).
- Run 2 added timers and showed that looking up actors by string path (`StaticFindObject(path)`) cost
  approximately **5 ms per call**. At 176 lookups per second, path string hashing and engine object-tree searches
  consumed 915 of the 971 ms per second spent by the mod. Run 3 with the fix: 28.5 fps average (min 15), from 1.8 [real run, `perf-phase1-run3.txt`].
- **Fix:** Retain direct pointer references (`actor_obj`) upon creation. Calling `actor_obj:IsValid()` takes less than
  1 microsecond, completely bypassing engine object table lookups.

### 2. Out-parameter calls (23 to 35 microseconds against 3 to 6) [real run, `tests/lua/bench-calls.lua`, `evidence/bench-teleport.txt`]
- Benchmarking 1,500 calls of `K2_SetActorLocationAndRotation` vs methods without out-parameters (`bench-calls.lua`):
  - Function without out-parameters: **3 to 6 μs per call**.
  - Function with out-parameters (passing `{}` for hit result): **23 to 35 μs per call**, generating **~3 KB of Lua garbage per call**.
- 1,479 calls at 24 microseconds is about 36 ms (arithmetic). The claim that the garbage causes "frequent GC sweeps" and
  that passing nil avoids them is [unverified]; the measured fix was to move from `K2_SetActorLocationAndRotation` to
  `K2_TeleportTo` (6.4 microseconds per call; collapse GeoPass cost 110 to 63 ms/s, `perf-smooth2-V0` against
  `perf-smooth3-T0`).

### 3. Rotator helper (`MakeRotFromXZ`) [real run, `docs/PERFORMANCE_PLAN.md`]
- Converting an orthonormal orientation matrix from the physics guest into an Unreal Engine rotator via reflected
  helper `KismetMathLibrary:MakeRotFromXZ` (called twice per piece record) cost 4 ms/s in run 2 and 68 ms/s in run 7. Run 7 is one of the runs that left the
  pieces hidden (see below), but the rotation timer is independent of that.
- **Fix:** Implemented a pure Lua rotation matrix to Euler angles converter, validated against the engine helper at
  startup [source; the 100 ms/s saving is not isolated: condition B bundles it with cached lookups, 143 to 177 down to 48 to 70 ms/s].

### 4. The hidden second game uses the GPU [real run, `docs/PERFORMANCE_PLAN.md`]
- When running a hidden secondary simulation process (Red Faction Guerrilla) beside Oblivion, the guest ran uncapped
  at ~250 fps, consuming **1.8 CPU cores and 70% to 100% of an AMD RX 9070 XT GPU**.
- This resource starvation throttled Oblivion's render thread. Enforcing a hard 60 fps cap in the guest's mod proxy
  lifted Oblivion's idle frame rate from 37.7 to about 40 to 42 fps (idle runs; the collapse comparison without the cap is swap-invalid).

## Build steps

1. **Implement Actor Object Caching:**
   - On initial actor spawn or resolution, store the raw `actor_obj` in the piece state table.
   - Guard updates with `if actor_obj:IsValid() then` rather than re-resolving by name or path.
2. **Implement Pure Lua Rotation Math:**
   - Avoid calling `MakeRotFromXZ` across the reflection boundary every frame.
   - Compute pitch, yaw, and roll directly in Lua from the guest's forward and up vectors.
3. **Time-Budget Pre-spawning:**
   - Building all 1,479 mesh actors at once froze the game (minimum 1 fps; mesh asset loading about 21 per second, up to 1.5 s per pass).
   - Build pieces across passes with a 10 ms-per-pass budget (about 8 pieces/s, about 3 minutes in total; minimum fps 29
     during the build) once the player is within range [real run, `perf-phase1-run4.txt`].
4. **Cap Secondary Process:**
   - If running a guest physics process, lock its frame rate to 60 fps to leave GPU headroom for the host.

## Verification

### The Swap-Invalid Runs: Why Run Integrity Matters [CRITICAL]
During development, a critical bug was discovered in commit `227f785`: the function `do_swap` referenced `crumb(10)`
before `crumb` was defined (a nil global access). The pcall failed silently right after setting `swapped = true`.
- **Consequence [real run]:** the intact house was never hidden and the 1,479 prebuilt pieces were never shown (the `SWAP:` line was blank).
- **Honest Status:** Runs 6, 7 and the initial cap runs (`perf-cap-A1`, `A2`, `B1`, `B2`) were **SWAP-INVALID for
  collapse performance**. They measured the collapse with the pieces hidden.
  **These runs must never be cited as valid collapse performance results.**

### Valid collapse measurements [real run, `evidence/perf-swap-A1`, `B1`, `A2`, `B2`; table from `docs/PERFORMANCE_PLAN.md`]
Following the forward-declaration fix, all runs confirmed the swap via log line:
`SWAP: real house hidden (1 actors), 1479 prebuilt pieces shown`.
Tested under identical conditions with RFG capped at 60 fps (A = baseline Lua with fix; B = cached lookups + pure Lua rotation):

| Run | Collapse fps (min) | Worst Frame | GeoPass Script Time | Quiet Near House | Idle Far |
|---|---|---|---|---|---|
| **A1** (Baseline) | 36.3 (33) | 74 ms | 143 ms/s | 43.7 fps | 38.4 fps |
| **A2** (Baseline) | 42.0 (33) | 94 ms | 177 ms/s | 45.5 fps | 40.3 fps |
| **B1** (Optimized) | 42.1 (36) | 75 ms | 48 ms/s | 46.0 fps | 41.3 fps |
| **B2** (Optimized) | 44.0 (37) | 93 ms | 70 ms/s | 48.0 fps | 42.0 fps |

- **Verdict:** Condition B cut GeoPass CPU cost by 2x to 3x (down to 48–70 ms/s).
- Every valid run stayed at or above 33 fps. One run per condition; single-run noise is about 2 fps and A varies by 5.7 fps
  between its own two runs, so the fps gap between A and B is not significant; the GeoPass cost gap is consistent.

## Gotchas

1. **`StaticFindObject` string lookup is catastrophic in loops.** **Symptom [real run]:** 3.0 fps in the collapse. **Cause:** [unverified] why one lookup costs about 5 ms; the cost itself is measured.
   **Fix:** Cache `actor_obj` pointers upon instantiation; test validity with `:IsValid()`.
2. **Silent script termination in pcall hooks.** **Symptom:** Swap reported active, but visual swap never occurred.
   **Cause [real run]:** a local function (`crumb`) used before its definition is a nil global; the error inside a `pcall` was silent.
   **Fix:** Add strict breadcrumb logging and assert that post-condition log markers (`SWAP: ... pieces shown`) exist.
3. **Out-parameter memory churn.** **Symptom:** Periodic multi-millisecond frame spikes during steady motion.
   **Cause:** [unverified] the "frame spikes during steady motion" symptom and the "table and registry reference per out-parameter"
   mechanism were not found in the repo; the measured facts are 23 to 35 microseconds and about 3 KB of garbage per call.
   **Fix [real run]:** use a function without an out parameter (`K2_TeleportTo`).
4. **Guest game GPU starvation.** **Symptom:** Host game drops frames even when Lua script execution is under 20 ms.
   **Cause:** the uncapped guest runs at about 250 fps using 70 to 100 percent of the GPU [real run]; "GPU compute queues" is [inferred]. **Fix:** a 60 fps cap inside the guest's mod library (`src/rfg/bridge.h` frame cap, `rfg_fps.txt`) [source; idle fps gain real run]. The symptom "drops frames even when Lua is under 20 ms" is [unverified].
5. **`GetActorBounds` silently fails with three arguments.** **Symptom [real run, `evidence/house-floor.txt`, commit 093c5e0]:** a bounds read wrapped in `pcall` printed
   "bounds call failed". **Cause [the 4-argument form worked in commit 093c5e0; that the missing argument was the sole cause is inferred]:** the function takes four arguments (`bOnlyCollidingComponents, Origin, BoxExtent,
   bIncludeFromChildActors`); with the last one missing the out-parameter tables stay empty. **Fix:** pass all four, e.g.
   `a:GetActorBounds(false, o, e, false)`, then read `o.X/Y/Z` and `e.X/Y/Z`. Two other routes failed in the same
   session: reading `RootComponent.Bounds` ("cannot read number from UObject") and `K2_GetComponentsBoundingBox`
   (the member call hit a null instance). Use `GetActorBounds` (`evidence/house-floor.txt`, 78 ms for one actor).
6. **`LineTraceSingle` is cheap enough for grids [real run, `evidence/ground-grid.txt`].** 961 downward traces (a 31 x 31 grid, 2 m cells) took 26 ms,
   about 27 us each (58 ms for the whole eval), all hits, on `Default__KismetSystemLibrary`. The trace hits the first thing below the start, so roofs and trees need a
   filter or a start point just above the terrain.
7. **On-demand scene capture is unusable, every-frame capture works [real run, `docs/PLAN_STATE.md`, `evidence/film-hq.out`].** `CaptureScene()` on demand hung the game
   twice (62 and 3 frames captured) and the frames were washed out; capturing every frame gave 287 frames in 53.5 s at
   1920x1080 (5.3 fps) with correct exposure.
8. **Per-component render switches do not recover standing cost [real run, `evidence/standing-runs.txt`].** Showing the 1,479 prebuilt pieces costs
   8.5 ms per frame by fps (real house 65.8 fps, pieces 42.3 fps); by the logged mean frame time it is 7.4 ms (house 16.3 ms, pieces 23.7 ms, p99 25.8 ms). The two measures differ because fps and the per-frame mean are computed differently (evidence/standing-base.txt). Variants (single runs, noise about
   +-0.5 ms): no shadows 8.3, no distance-field/occluder/decals 8.1, cull distance 30 m 8.3, all combined 8.6. So the
   cost scales with the number of visible components (submission), not with shadows, distance fields or culling. Remaining
   levers [INFERRED, untested]: fewer components (hide enclosed pieces, merge settled pieces, instancing). A "static
   mobility" variant produced no valid run and is untested. Earlier standing and lighting runs were invalid because the swap
   never ran (see the swap-invalid section above).

## Assets

- Performance test scripts: `tests/perf-house.sh`, `tests/lua/bench-calls.lua`.
- Test harness logs and summaries: `tools/perf-summary.py`.

## Cost and time

- Elapsed time: the profiling ran across 2026-11-03 and 2026-11-04; "8 runs over about 6 hours" is [unverified]. No cloud spend is recorded.

## Open questions

- **Smoothness vs update rate:** Lua decodes at 10 Hz (not 9). The per-frame interpolation was moved into a native
  library, `geomod_native.dll` (not `geomod_guard.dll`, which is the crash guard); see the ProcessEvent note.
  19 to 20 percent frozen frames remain [real run].
- **Dynamic shadows:** a test of shadows, distance fields and cull distance on the 1,479 pieces found no change in
  standing cost (Gotcha 8); the first draft's question is answered for those switches, not for Lumen or Virtual Shadow Map cost in general.
