---
kind: technique
title: "Engine recreation for mashups: what each rebuild measures, and what fidelity includes"
tags: [mashup, engine-recreation, reimplementation, static-recompilation, decompilation, fidelity, parity, scripts, benchmarks, sdk]
date: 2026-10-07
agents: ["Claude Code (Opus 5.5)"]
humans: ["LeiiLo"]
links: ["https://github.com/vladtrc/iw4L", "https://github.com/SK8-ENGINE/skate-3-rust-engine", "https://github.com/chasmlol/2010-rust-rewrite-mashup", "https://github.com/patchzyy/Wiicompiled"]
---

# Engine recreation for mashups: what each rebuild measures, and what fidelity includes

> Some mashups never run either original game. [IW4L](https://github.com/vladtrc/iw4L) (MW2),
> [SK8-ENGINE](https://github.com/SK8-ENGINE/skate-3-rust-engine) (Skate 3), [benilla](https://github.com/samwhosung/benilla) (WoW 1.12.1),
> CS:Craft (CS:GO formats) and [HL2-RS](https://github.com/kvalls/hl2-rs) rebuild an engine that reads the
> owner's data, and the [2010 Rust Rewrite Mashup](https://github.com/chasmlol/2010-rust-rewrite-mashup) fuses several of them in one process. This
> note covers how each kind of rebuild is measured, what fidelity includes, and the SDK rules that let other
> mods build on a recreation. Trace replay and byte-matching builds as oracles are in
> `oracles-how-agents-know-a-mod-works.md`; console decomps and recomps are in
> `skills/mod-any-game/references/engines/retro-decomp.md`.

## When to use it
`choosing-a-mashup-route.md` points you at engine recreation, or you're extending an existing recreation, or
you need to judge another project's "100%" or "parity" claim.

## How

### Name the kind of rebuild and its measure
| Kind | Produces | Measured by |
|---|---|---|
| **Matching decompilation** (mkdd) | source that compiles back to the original bytes | per-function byte match with the original compiler and flags |
| **Static recompilation** ([WiiCompiled](https://github.com/patchzyy/Wiicompiled)) | the original machine code translated ahead of time, plus a platform runtime | instruction coverage, and behaviour parity on real inputs |
| **Engine recreation** (IW4L, SK8-ENGINE) | a new engine that reads the original data and reimplements its rules | trace comparisons against the original, system by system |
| **Emulation** | the original binary on an emulated machine | timing and device accuracy |

A byte match, a linked build, a deterministic export and behaviour parity are four separate numbers. Don't
add them up, and don't quote one as another.

### Scripts are part of fidelity
- In the 2010 mashup's MW2 runtime, GSC scripts compile to an intermediate form and run only on authority
  frames. Scheduling, event order, copy and alias semantics and the random seed all change outcomes. A
  runtime error yields an undefined value and carries on without undoing earlier writes; runaway loops are
  capped. Match those rules or list where you don't.
- Its bots got slower once matches moved to MW2's own scripts, so performance numbers from before that
  aren't comparable.
- **Foreign maps keep host rules.** Maps from other titles bring their entities and assets; their gameplay
  and UI scripts are dropped and MW2's modes stay in charge. IW4L 0.1.0-demo.2 loads an MW2, an MW3 and a
  Black Ops map with bots under MW2 rules, which is map support for three titles. MW3 and Black Ops
  gameplay aren't part of it.

### What a rebuild doesn't give you for free
- **Determinism.** Identical generated source doesn't guarantee the same random numbers,
  floating-point order, thread order or host inputs. A deterministic build and a deterministic game are
  separate properties.
- **Graphics, audio and input.** Translating an executable leaves them as runtime work; WiiCompiled routes
  graphics through Aurora/GX and WebGPU/Dawn.
- **A faster physics tick.** WiiCompiled's 120/144 Hz interpolation changes presentation only and can add
  artefacts.
- **Parity beyond what was replayed.** Ghost-input replay is a strong parity test for the routes it
  replays and says nothing about the others.
- **Engines that fit together.** A shared language doesn't reconcile world IDs, coordinate systems,
  physics, input, entity lifecycle, animation, saves, assets or networking. The 2010 mashup retargets Skate
  bones to the MW2 soldier skeleton and derives grind rails from the map's walkable edges.

### Check renderer and loading work with renders
- SK8-ENGINE's renderer optimisations (bindless texture-slot reuse, conservative occlusion depth, cache
  keys tied to buffer identity and revision) must still let motion and visibility update. Check that with
  renders; assertions about data structures can't show it.
- CS:Craft's stutter fixes are a good starting list: pregenerate terrain, warm up shaders, bound uploads,
  keep mesh handles stable, avoid change notifications, and update lighting on worker threads.

### Give other mods a contract (SK8-ENGINE's SDK)
BullySkate, SkateGM, World of Skatecraft and the 2010 mashup all build on SK8-ENGINE. Its SDK rules:
- Lua owns game policy; native code exposes generic primitives.
- Session authority changes are asynchronous, and the host ratifies them.
- Settled counters and event cursors stop repeated triggers and fake achievements. Its "Simon Says"
  example mod reads the settled clean-trick counter instead of trusting a client.
- Overlap queries use real hulls but are sampled rather than swept, so a fast mover can skip a thin
  trigger between samples.
- A local command receipt isn't a remote acknowledgement.

### Write a parity document and scoped benchmarks
- CS:Craft's parity doc calls the project an adaptation: dragon AI, portals, effects and CS-scaled combat
  differ, and enchanting, brewing, advancements and multiplayer were unfinished. Its completion test uses
  staged fixtures. Keep a document like that next to your feature list.
- The 2010 mashup's performance doc compares alternating five-run medians on one machine and one no-bot
  route (183 → 362 fps) and says the heavy-bot case wasn't measured. Report every benchmark with its
  machine, route and what it left out.

## Gotchas
1. **A percentage from a different measure.** **Cause:** a byte-match or coverage figure quoted as
   "playable". **Fix:** name the measure next to every number.
2. **Docs for another build.** **Cause:** IW4L's network protocol changed across revisions. **Fix:** read
   the docs for your exact revision and pin it in `docs/CONTRACT.md`.
3. **Original-game findings mixed with runtime tests.** **Cause:** one log for both. SK8-ENGINE keeps them
   apart: a grind crash was a missing native adapter, resolved against the original assembly, while a
   quarter-pipe error was a wrong input action ID. **Fix:** label which side each finding came from.
4. **Suites that didn't run.** **Cause:** WiiCompiled's translator tests default to synthetic inputs and
   skip asset and host-compiler tests; unsupported instructions fail unless traps are switched on. **Fix:**
   report which suites ran, on which inputs.
5. **A rebuild that looks like it started from zero.** **Cause:** prior work left uncredited. IW4L's notice
   credits earlier asset, protocol and engine projects; SK8-ENGINE credits years of human research and
   extraction tools. **Fix:** list the prior work you relied on.

## Verification
Rows with versions: `skills/mashup-mods/references/mashup-cases.md`. Creator results are reports.
