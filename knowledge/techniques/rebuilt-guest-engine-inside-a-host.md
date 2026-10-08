---
kind: technique
title: "A rebuilt guest engine inside a real host: in-process DLL, worker processes, transplants and oracles"
tags: [mashup, reimplementation, skate, worker-process, ffi, c-api, shared-memory, coordinate-mapping, input-normalization, oracle, transplant, recovery]
date: 2026-10-05
agents: ["Claude Code (Opus 5.5)"]
humans: ["LeiiLo"]
links: ["https://github.com/chasmlol/2010-rust-rewrite-mashup", "https://github.com/samwhosung/benilla"]
---

# A rebuilt guest engine inside a real host: in-process DLL, worker processes, transplants and oracles

> Many "Game B inside Game A" projects never run Game B's executable. They rebuild Game B's engine, or one
> of its mechanics, and plug it into the real host: the Skate 3 engine in Bully, Garry's Mod, a
> recreated WoW client and older 32-bit hosts; Mirror's Edge movement in Skyrim and Minecraft; Mario 64's
> movement in Elden Ring; Diablo II movement in
> DevilutionX. This note compares where the rebuilt part runs and how each project checked it.

## When to use it
The guest's gameplay is a mechanic set the host lacks (skating, parkour, movement), a rebuilt engine
already exists or can be built, and running the original guest alongside would be heavier or impossible.
Compare `choosing-a-mashup-route.md` and the mashup skill's patterns 3–5.

## How

### Choose where the rebuilt part runs
| Placement | Example | Consequence |
|---|---|---|
| **In-process DLL behind a C API** | ER Mario compiles the C library libsm64 into a Rust DLL that Elden Ring loads through me3 | lowest latency, but must match the host's bitness and address budget; a guest fault is a host fault, so the guest must recover itself |
| **Worker processes** | [BullySkate](https://github.com/Faiqie/BullySkate): x86 Bully adapter + x64 Skate physics worker + separate sound worker | the guest can be 64-bit beside a 32-bit host and keep big state off the host's threads; needs a transport contract and lifetime binding |
| **Inside a host scripting runtime** | [SkateGM](https://github.com/the-schwilliam/SkateGM): the rebuilt Skate engine in Garry's Mod through a native module and Lua | the host's scripting decides what's easy; moving props need their own collision layer |
| **Inside a recreated host** | [World of Skatecraft](https://github.com/Kimmo3223/world-of-skatecraft): Skate engine added to [benilla](https://github.com/samwhosung/benilla) (recreated WoW 1.12.1 client) through an extension entry point that accepts extra Bevy plugins | no foreign process at all, but you depend on the recreated host's own fidelity |
| **Shared mechanic library for several hosts** | [Faith Runner](https://github.com/tnrjns/faith-runner): Mirror's Edge movement in Rust, statically linked into an SKSE plugin and loaded by Minecraft through Java's FFI | one mechanic, many hosts; each host supplies only box sweeps and overlap queries |
| **Mechanic inside a rebuilt host engine** | Diablo II movement in DevilutionX: fine coordinates above Diablo I tile occupancy, combat and saves | smallest scope; host systems stay authoritative |

Some projects load a 32-bit rebuilt engine DLL straight into an older 32-bit host, which brings every
constraint of the first row.

### Write a small fixed contract (BullySkate as the model)
- **No pointers, fixed size.** Bully ↔ physics shares a 6,184-byte C-compatible block, PID-scoped, with
  command/response events: up to 24 actors, 8 vehicles, 8 input samples; rider 36×13 and board 2×13 pose
  values; 64 sound floats.
- **Separate channel per consumer.** Sound gets a 296-byte version-1 block of latest observations
  protected by an odd/even sequence with three reader retries; the host never waits for the mixer.
- **Axes once.** Host Z-up, guest Y-up: positions and view vectors cross as (x, z, −y); mount yaw adjusted by π.
- **Guest clock.** Physics steps a fixed period accumulated from queued input durations, not once per host
  frame. On overflow it merges the last input and caps catch-up at 0.1 s.
- **Lifetimes.** The worker watches the parent's exit, the host watches worker health, and a Windows job
  object binds them.
- **Hand back.** The player leaves the board for doors, shops and missions, then re-mounts.

### Normalise at the engine boundary
SkateGM converts SDL controllers (PlayStation, Switch, generic) into the Xbox-shaped input structure the
rebuilt engine already used, and picks button labels separately. The engine's input ABI never changed.
Note its precedence rule: any connected XInput pad wins over SDL.

### Keep the host's own systems alive
ER Mario keeps a hidden native Tarnished following Mario, so Elden Ring still handles doors, menus, quests,
deaths and saves. Mario's progress goes in a separate offline save. Without the native character, each of
those systems would need rebuilding.

### Check against the original where you can
The Diablo II movement mod compares its tables with a user-supplied Diablo II 1.12 `D2Common.dll` and
an MIT-licensed reimplementation, keeps a probe/report harness, and falls back to stock tile walking when
continuous movement stalls. Faith Runner reads behavioural parameters from extracted UnrealScript and
Ghidra-inspected native code. Missing owned files skip those checks, so record when a run skipped them.

## Gotchas
1. **Invalid numbers from the guest.** **Cause:** a rebuilt physics state goes non-finite. **Fix:** keep
   the last finite transform, reset heading, restore the last good pose, and stop if another error arrives
   within a few seconds; some projects reload the guest engine off the main thread without restarting the
   host.
2. **Lost button presses during stalls.** **Cause:** merged/capped input catch-up (BullySkate). **Fix:** log
   merges; keep presses as edge events, not levels.
3. **Silence or looping sound.** BullySkate's sound worker mutes after 250 ms without a new sequence rather
   than repeating stale state; its mixer callback still takes an engine mutex, so "nonblocking host" is not
   "lock-free audio".
4. **Host collision for the guest.** Some in-process builds rebuild nearby car collision at most once a
   second after a set distance of movement and skip identical batches by hash; BullySkate uses physical COL volumes, not
   navigation volumes, and versions its grind-rail format (BMRL2 → BMRL3) with a receipt schema check;
   SkateGM needs an explicit collision layer for moving props. ER Mario's collision notes list the traps
   when Havok feeds libsm64: mirrored coordinate systems and triangle winding, convex hull orientation,
   moving-platform displacement, sequential wall correction, where ceiling queries are anchored, and stale
   invisible guard walls. Its tests cover translations, rotations, stream changes and rebasing, not every
   Havok situation.
5. **Unported original behaviour.** SkateGM skips an unported air-dismount producer instead of failing the
   tick; Faith Runner substitutes an undecoded vertigo predicate and enables auto-step that the original
   disabled. **Fix:** list substitutions next to features.
6. **"Original feel" from extracted numbers.** Faith Runner's doubled gravity is inferred from a developer
   comment; the actual doubling source is unresolved. Numbers matching is not behaviour matching.
7. **A feature that depends on a server.** World of Skatecraft's skateboarding profession needs its patched
   server core on Linux; the experimental Windows setup uses a stock server without it.
8. **Version drift in reports.** The Diablo mod's v0.1 used Diablo II speeds everywhere; v0.2 keeps Diablo I
   dungeon pace, but an older report still describes v0.1. Date every report.

## Verification
Rows with versions: `skills/mashup-mods/references/mashup-cases.md`. Creator results are reports.
