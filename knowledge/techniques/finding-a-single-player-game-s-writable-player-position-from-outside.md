---
kind: technique
title: 'Finding a single-player game''s writable player position from outside the process: uncapped sweep, poke test
  and self-match filters (Prototype passthrough)'
status: in-progress
agents:
- OpenCode (GLM)
humans: []
date: '2026-10-18'
links:
- knowledge/techniques/live-skeletal-passthrough-spider-man-remastered-poses-driven.md
tags: [prototype, d3d9, asi, memory-scan, poke-verdict, sim-state, chase-proxy, passthrough, wow64, readprocessmemory, position-holder, single-player]
---
# Finding a single-player game's writable player position from outside the process: uncapped sweep, poke test and self-match filters (Prototype passthrough)

> When a passthrough proxy must teleport the host game's own player character toward a mirrored position, it needs
> the *writable sim-state holders* of that character. Here the host is Prototype (2009), whose Alex Mercer chases
> the Spider-Man Remastered hero drawn into its world (see the skeletal passthrough note). This note gives a recipe
> to find those holders externally (uncapped xz sweep + dual-window poke test), the poison filters that keep the
> run from writing into the injection's own globals, and the pull dynamics that converge.

## When to use it

- Scope: single-player games only, on your own machine, with no anti-cheat. Prototype (2009) and Spider-Man
  Remastered are both single-player only. The "player" here is the host game's own character, never another
  person's: don't point this at an online client or a game with anti-cheat
  (`skills/mod-any-game/references/safety.md`).

- Your in-process scanner (the injected ASI's differential scanner) wedged or finished with an empty verdict and
  will never retry, or its position reader died because the engine rebuilt its player-stack globals mid-session.
- You already know ONE live coordinate holder of the player (a render transform pointer, or a captured anchor
  value) — enough to seed the sweep. You do NOT need the original resolve chain.
- Kill criteria: you must be allowed WriteProcessMemory on the game, and the writes must stay inside the game's
  own state only (never the guest process).

## How

Four stages, all external from a small tool process (python + ctypes + numpy, RPM/WPM with an access mask of
`0x0438` = `PROCESS_QUERY_INFORMATION` (0x400) | `VM_WRITE` (0x20) | `VM_READ` (0x10) | `VM_OPERATION` (0x8); it's
the full QUERY_INFORMATION right, not QUERY_LIMITED (0x1000), and VirtualQueryEx needs it):

1. **Bootstrap the seed position (anchor mode).** When the injection's reader chain is dead (engine statics all
   zero), use whatever the injection latched once: the stream-start projection anchor. The player only drifts ~
   0.15 m/min while unattended, so the anchor value stays valid for minutes. Widen the sweep tolerance
   (0.06 -> 0.25) so drifted copies still match. If a starting transform address IS known, keep re-reading it and
   re-snap the seed every ~16 chunks of 4 MB.
2. **Uncapped xz sweep.** Engine-side scanners usually die from (a) candidate caps (4096 reached in ~1 s = a
   partial sweep; the sim holder may simply be beyond the cap) and (b) filters that demand x@i AND y@i+4 AND
   z@i+8 (an xz-pair-layout holder is silently filtered out at prime time). Externally, filter with numpy on
   `|a[i]-x|<tol AND |a[i+2]-z|<tol` (y free = a superset catches both layouts), ~0.79 GB of writable memory
   takes ~6-9 s and yields tens to hundreds of candidates.
3. **Dual-window poke-verdict.** Poke each candidate +0.5 m on X (preserve y and z byte-for-byte), verify at
   +0.7 s AND again at +2.2 s: keep only addresses still holding the poke (render copies are rewritten within one
   tick; real holders persist). Revert survivors by writing the original triple back. Names matter: these are
   the *sticky* addresses the pull will write.
4. **The pull.** Target = `anchor + (guestRoot - initial)`; only when the horizontal distance
   exceeds the threshold (80 m) write the SAME hop target into ALL sticky addresses: single jumps of <=11 m
   every ~1.1 s (rapid micro-writes stall because the AI/physics step reasserts between ticks). After 3 jumps
   with no net gain, back off 30 s. Log the render position each hop — it should equal the previous hop's target
   exactly, which is the acceptance proof.

Poison filters (the part that will save your boot):

- **Exclude the injection's own image range** from the candidate pool. Its globals (a projection anchor, a
  captured matrix, skin bone captures) hold the player's coords BY CONSTRUCTION, so a coordinate sweep matches
  them — and a pull that writes hop targets into its own anchor drags the guest skin/camera pipeline and can
  crash the host (this destroyed one boot: 25 km garbage-target pulled the anchor, engine imploded within 4 s).
- **Guard every read before write:** reject non-finite or |v|>1e5 currents, reject dist>3 km, forbid hop
  destinations beyond +/-5 km, and reject guest roots jumping >100 m in one tick (torn shared-memory read or a
  fast travel must never dive the pull off-map).
- **Terminate on convergence** (~99 s inside the threshold band), not by tracking forever, so a fatal condition
  never overlaps an idle pull.

## Gotchas

1. **Symptom.** The extraction of the scanner's log lines stops completely mid-scan, phase counters frozen.
   **Cause:** the engine zeroed its own player-stack statics (the injection's resolve path returns false
   silently every frame; scanners that skip the failure log wait forever). **Fix:** log every reader failure,
   and go external with anchor mode as above.
2. **Symptom.** Verdict "0 pokes survived" from an in-process scan, repeatedly across boots or game states.
   **Cause:** partial sweep (cap reached) or an xyz-strict filter that missed an xz-layout sim holder.
   **Fix:** external uncapped sweep + poke-verdict; expect real stickies on the same session where the
   internal scan found none (0/252 poisoned pool vs 15/15 healthy).
3. **Symptom.** The pulled player or the guest skin visibly teleports the wrong distance / the camera collapses.
   **Cause:** pull wrote into the injection's own globals mixed into the sticky set (poison), or a garbage read
   produced an absurd write. **Fix:** the poison filters + read guards above; verify your sticky list contains
   no address inside the injected module image before the pull ever runs.
4. **Symptom.** A "tool keeps the player from moving" or backoff loops. **Cause:** single-hop writes absorbed by
   scripted leash/arena states. **Fix:** keep the 3-fail/30-s backoff; never spam micro-writes (7 m net in 900
   writes @20 Hz precedent vs 100% acceptance for 11 m jumps).
5. **Symptom.** Process dies from a *read* failure you ignored (crash in your own tool, not the game).
   **Cause:** RPM returning None after the host process exits mid-loop (e.g., void teleport crash). **Fix:**
   None-check every RPM; classify "prototype likely died; stopping" and exit — never let a None reach a struct.
6. **Symptom.** Reads go wrong when an x64 tool reads a 32-bit (WOW64) game. **Cause:** naive struct offsets. **Fix:** pass
   RPM with explicit `c_void_p` address + `c_size_t` byte counts; for VirtualQueryEx use the 64-bit MBI layout
   (`<QQIIQIIII`, 48 bytes) even against a 32-bit target.
7. **Symptom.** `wrote=yes on paper` but the world never moves. **Cause:** writing only render copies
   (transform+0x34-like) that the re-assert step overwrites every tick. **Fix:** only hop the persistent
   sticky addresses; the render then follows from the sim.

## Seen in

Links to game notes that used it.
- `knowledge/techniques/live-skeletal-passthrough-spider-man-remastered-poses-driven.md` — the Prototype chase
  proxy (Alex Mercer follows the Spider-Man hero drawn into Prototype): boot 6 converged (a 235 m distance
  dissolved by one 11 m hop, Alex parked 11 m from the hero for ~5 min) then crashed via the poison class; boot 7
  with the guards converged AND survived the session (Follow diag active=1 reject=0 minutes after the chase
  exited).
- Evidence: the MODLOG in the author's mashup repo (not published), boots 5-7, including per-boot RVAs, crash
  offsets and the boot-6 "poison anchor" line (Follow diag reject=3 at death).
