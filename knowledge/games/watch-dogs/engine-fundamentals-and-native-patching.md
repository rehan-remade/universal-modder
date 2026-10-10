---
kind: game
title: "Watch Dogs (Disrupt/Shadow engine): structure, build identity and native patching"
game: "Watch Dogs"
games_also: []
game_version: "see note — five executable profiles; Global/04DF base image 0x7FFC39BF0000, timestamp 0x5CD045B4"
platform: windows
engine: unknown
route: native-hook
tools: ["Ghidra", "TinyCC 0.9.27 (win64)", "build.ps1", "validate_release.py", "Python (offline harnesses)", "NexusTools host/loader", "ETW/DXGI presentation capture"]
anti_cheat: "No anti-cheat interaction is documented in this knowledge base. Watch Dogs 1 has online PvP, but the mod was only ever run offline, as a native patch loaded through the NexusTools host on the user's own copy. Nothing here describes defeating protection."
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links: ["https://github.com/temdah/Shadow-Engine", "https://github.com/temdah/Watch_Dogs_OKF"]
tags: ["disrupt", "shadow-engine", "native-patching", "build-identity", "rva", "runtime-profiles", "transactions"]
---
# Watch Dogs (Disrupt/Shadow engine): structure, build identity and native patching

> Watch Dogs 1 runs on Disrupt (a Dunia 2 fork) with a shadow pipeline that assigns a
> fixed number of local shadow maps, admits a bounded priority set of lights, and
> consumes results through a renderer queue. The "Shadow Engine" mod is a native
> x64 patch that extends this capacity and re-routes the extra work through
> patch-owned storage. Every address is an RVA into one specific executable build;
> the mod selects one coherent runtime profile and refuses to write if it cannot
> prove the layout.

## Setup

- Game: Watch Dogs 1 (PC, x64). Most findings concern WD1; WD2 comparisons are
  labelled separately and are static-analysis only.
- Loader: the NexusTools host loads the patch. The mod is a native DLL/ASI-style
  patch, not a data-only mod.
- Build toolchain: TinyCC 0.9.27 for win64, driven by `build.ps1`, producing one
  translation unit (`shadow_engine_patch.c`) assembled from ordered include modules.
- Static analysis: Ghidra. Runtime: the game itself, plus offline native harnesses.
- The KB this note summarises holds documentation only — no game binaries, no
  proprietary dumps, no installable mods. Mod source lives in its own repository.

## Route and why

- The shadow capacity is baked into native code as a fixed pool of 16 local maps and
  a 17-entry renderer queue. Changing it by data alone is not possible, so the route
  is a native hook.
- The engine is recompiled per region/store, so the same logical routine lands at
  different RVAs in different executables. The mod therefore models each supported
  build as an immutable **RuntimeProfile**, not a version branch inside feature code.
- Supported profiles: Global/04DF, Shev/A4EE, VMPless, Complete Edition, Asia/Miru.
  The "VMPless" build is a shipped build distributed without VMProtect packing (a
  raw, signed PE without VMProtect), not an unpacked or cracked dump.
  Core modules never branch on the profile number; capacity, residency, admission,
  result routing and cleanup share one policy.
- Fail-closed rule: profile selection must be unique and coherent, and every mutation
  site is validated in read-only preflight before any write. Unknown, ambiguous or
  incomplete layouts get diagnostics only — no hooks, no writes.
- Adding a new build means adding one complete, validated profile, not forking logic.

## How the game works (what we had to learn)

### Frame pipeline

`input/network -> gameplay -> animation/physics -> visibility/LOD -> lighting/shadow
selection -> render graph/commands -> GPU submission -> presentation`.

Frame budgets are 16.67 ms at 60 FPS and 33.33 ms at 30 FPS; stages overlap. A
faster helper is not automatically a faster frame.

### Five distinct shadow boundaries

Confusing these is the most common source of wrong conclusions. A shadow map must
pass all five:

1. **Allocation** — storage exists.
2. **Admission** — the light was selected for a shadow.
3. **Scheduling** — the map is updated this cycle.
4. **Residency** — the map is retained or replaced.
5. **Consumption** — a later lighting pass actually samples the result.

Increasing allocation does not guarantee admission, scheduling, residency or
consumption.

### Pools are coupled, not one number

The logical bound and the physical storage are different things. A queue that holds
`entries[16]` cannot hold 24 just because a count field says 24: the physical
allocation, the producer/consumer bounds, the moved tail fields, every instruction
that indexes the array, the handle/pass registrations and pointer lifetimes all
change together. The real WD1 queue has three independently growing regions, so a
single uniform stride assumption is wrong.

### Wrappers and handles

A light travels `logical key -> lookup -> engine wrapper/handle -> API view -> GPU
allocation`. Two handles can point at the same resource while still carrying two
separate ownership obligations, so pointer equality does not collapse the work.

### Shadow pipeline stages

`world and vehicle lights -> candidate construction and classification -> manager
admission and priority -> fully dynamic or cached-owner residency -> render-queue
records and cumulative face allocation -> local-map handle and Shadow/ShadowAlpha
pass lookup -> SliceExecute dispatch and result store -> stock post-call consumer ->
external-result consumer and native-wrapper release`.

Failure localisation follows that order: profile/preflight, then native+external
resource handles, then pass-table population, then manager candidates/admissions,
then queue records and cumulative faces, then SliceExecute stores, then external
consumption/release counters.

### Capacity layout

- Native engine: 16 local maps, 17 physical queue entries (the extra entry preserves
  a special long-range job).
- For a target of `M` maps: physical queue entries `= M+1`; queue index-array clear
  bytes `= 4 + 4*M`; external map count `= M-16`; external slice-result count `= M-17`.
- Pass 16 is `LongRangeShadow`; maps below 16 keep their native pass index; local map
  `m >= 16` uses pass `m+1`.
- One local-map record is `0x24C0` bytes. The three queue regions grow with strides
  `0x24C0`, `0x24C4` and `0x24C8` respectively — each old value must be relocated
  using its owning region's stride, not one shared stride.
- The shadow category is `0x0C`; the native registry holds 64 slots. Each added map
  needs a paired `Shadow` and `ShadowAlpha` pass (two slots). A 30-map build uses
  passes 17–30, slots 34–61, max key `0x3D0C`.
- A capacity change is one contract: map-loop construction, handle routing, pass
  routing, result routing, queue immediates, allocation size and all 46 recovered
  embedded references.

### Resource and pass lifecycle

- Extra maps must be created by extending the native resource-constructor loop while
  engine dependencies are still valid. Indices 0–15 keep native manager storage;
  indices 16+ are redirected to a patch-owned handle with aligned 16-byte companion
  arrays.
- Pass registration is also an object factory: it constructs the pass and inserts it
  into the renderer's two-level table. Added passes are registered inside the native
  registration phase, immediately after native pass 16 and before the table is
  finalised.
- For added local map `m`, register pass `p = m+1`: `Shadow` key `= (p << 9) | 0x0C`,
  `ShadowAlpha` key `= (p << 9) | 0x10C`.
- Activation proof requires all external handles non-zero and distinct, paired pass
  slots non-zero and distinct, downstream routing installed only after those checks,
  added indices actually consumed, and teardown/release counters coherent.

## Build steps

1. **Model the build as a `RuntimeProfile`.** It carries PE identity, a clustered or
   explicit RVA strategy, helper addresses, validation signatures and the detour
   prologue. Profiles are immutable data.
2. **Preflight read-only.** Resolve the profile and validate every mutation site
   without changing memory. Reject unknown/ambiguous/incomplete layouts.
3. **Commit through a prepared plan.** Executable writes are journaled before
   mutation. A failed phase restores bytes in reverse order, clears published
   trampoline pointers and releases transaction allocations. This is journaled
   rollback, not atomic code replacement against concurrent threads.
4. **Publish trampolines before detours are reachable.** v2.0.12 publishes the
   callable original trampoline before writing the detour entry, so a rollback can
   clear the pointer.
5. **Split early construction from deferred installation.** The game creates required
   objects between the two phases, so they are separate transactions. Engine objects
   created in between cannot be rolled back.
6. **Keep startup supervision alive.** Through .76 the startup worker exited after
   60 s even when the early transaction had committed, leaving downstream routing
   uninstalled when native constructors ran late. The .77 fix keeps one module-pinned
   worker responsible for deferred completion beyond 60 s, observing at a bounded
   cadence, with positive resource/pass invariants and a 1 s stabilisation before the
   deferred installer.
7. **Build reproducibly.** Warning-clean TinyCC 0.9.27 win64 builds via `build.ps1`.
   `validate_release.py` inspects the compiled PE without loading it: exports,
   ordinals, version and the fixed policy.

## Verification

- Evidence categories (from the KB policy): **Runtime-observed**, **Statically
  confirmed**, **Inference**, **Untested**. Visual observations are not promoted to
  complete fixes without repeatable captures.
- Offline gates: actual-source native harnesses, source contracts, independent
  byte/layout checks, fault injection proving reverse-order restoration and allocation
  cleanup. Offline success never establishes injected execution, rendered fidelity or
  in-game performance.
- Runtime corpus gate: verifies all five exact PE identities and resolves
  capacity-sensitive RVAs. v2.0.5 ran 63 byte-exact checks per usable profile
  (15 signatures, 46 relocations, construction, pre-finalizer/decoded-call);
  `--intersection-diagnostic` raises this to 71. It derives each new value from the
  owning `0x24C0`/`0x24C4`/`0x24C8` region and simulates every write in a disposable
  memory copy. A4EE is identity-checked but returns `manual-required`.
- Regional matrix: an "all five profiles" claim requires one frozen candidate.
  v1.2.1 (ASI SHA256 `006CEBE876D2997CBDFE5D525D5CFBD071FA3A9FF1D00C053C3C2210519A9EBC`)
  and v1.2.3 (`5510E9F34F62DD61F6C49E4F946664A9241A743C9E989B98DABF335506ED4CC2`)
  each passed all five on 2026-08-24.
- Refactor equivalence: splitting 2,903 source lines into eight ordered include
  modules reproduced SHA256
  `D622440495530E905C96B0B8D5CC6C0D9A4E7EDE3F0979BF75341F8A260415C0` before the
  version change; the two 76,288-byte binaries differed only in 42 version/checksum
  bytes. Replacing 98 aliases with 457 explicit context accesses left the ASI bytes
  identical. Neither proved a performance improvement.
- The runtime-corpus gate catches wrong RVAs, stale bytes, regional mapping errors and
  formula errors. It does not run the game, prove the detour executes, or judge visuals.

## Gotchas

1. **Symptom.** Queue is populated but both SliceExecute counters read zero and all
   shadows are absent (v1.2.2).
   **Cause:** All 46 relocated references were shifted by the same `0x24C8` stride,
   but the three queue regions use `0x24C0`, `0x24C4` and `0x24C8`.
   **Fix:** Assign each old value to its owning region (v1.2.3).
2. **Symptom.** A smaller, "cleaner" build behaves differently from the baseline.
   **Cause:** A mandatory result lookup was assigned only inside a diagnostic
   conditional, then used outside it; with diagnostics compiled out the pointer was
   uninitialised (2.0.71).
   **Fix:** Move the mandatory lookup outside optional observation. Smaller binary is
   not equivalent behaviour.
3. **Symptom.** Committed early hooks, construction/downstream counts zero, then
   resources and pass slots appear tens of seconds later (`.71` Complete Edition).
   **Cause:** The startup worker exited at 60 s before native constructors ran.
   **Fix:** Keep the module-pinned supervisor responsible for deferred completion
   beyond 60 s (`.77`).
4. **Symptom.** Crash on first late `ShadowMap16` construction, even from the renderer
   thread.
   **Cause:** Calling the resource builder outside the proven-safe lifecycle.
   **Fix:** Install constructor hooks during the early NexusTools callback; do not
   build shadow maps late.
5. **Symptom.** Missing pass key `0x220C` (pass 17) and a null renderer-initialiser
   fault at reported RVA `0x408A4F` (v1.2.9).
   **Cause:** The added pass object did not exist before the renderer table was
   finalised.
   **Fix:** Register added passes inside the native registration phase, immediately
   after native pass 16.
6. **Symptom.** Cache-owner pointers become stale after the fifth owner appears.
   **Cause:** The old config reserved physical space for 4 owners but allowed 8
   logically; a 5th allocation could move the `0x700`-byte record vector after earlier
   pointers escaped.
   **Fix:** Use the native reserve routine to provide 8 contiguous records before
   admission (v0.7.7).
7. **Symptom.** A single old/new layout pair suggests a uniform relocation delta.
   **Cause:** Sampling one region does not prove the others.
   **Fix:** Derive each region's stride independently; treat all 46 sites as one
   contract.

## Assets

- No game files, binaries, dumps or installable mods are distributed in this KB.
  Undistributed evidence is identified by stable IDs and hashes; those references do
  not make the raw material public.
- Mod source: https://github.com/temdah/Shadow-Engine
- KB: https://github.com/temdah/Watch_Dogs_OKF

## Cost and time

- This is a long-running, multi-revision RE effort (hundreds of versioned
  experiments). The engineering cost is dominated by static analysis of five regional
  binaries, offline harnesses and in-game validation windows, not by writing patch
  code.
- The mod ships as a small ASI/DLL; the intellectual cost is proving build identity,
  ownership and rollback safety.

## Open questions

- Exact retail build numbers for the five profiles (the KB names them by
  region/edition, not by a version string).
- Live acceptance of A4EE/Shev: no mapped observer; it stays disabled/`manual-required`.
- Whether the extra passes and maps are safe on every derived teardown path and under
  live array replacement.
- Whether the deferred-install window can ever exceed the supervisor's coverage on
  slow or unusual machines.
- No GPU-completion or visual-equivalence proof exists for the capacity changes.
