---
kind: game
title: "61 destructive modes for a Minecraft 26.3 Forge terraforming tool: subcategories, server-side containment of spreading warps, cross-mode interactions, and real-time pacing"
game: Minecraft
games_also: []
game_version: "Minecraft Java 26.3, Forge 66.1.5 (ForgeGradle 7, Java 25)"
platform: windows
engine: java
route: loader-api
tools: ["Forge 66.1.5", "ForgeGradle 7", "decompiled 26.3 sources for API checks (kept out of the repo)", "scripted dev clients", "a dev dedicated server"]
anti_cheat: "none (single player and a dev dedicated server the user runs)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: '2026-11-16'
links: []
tags: [terraforming, destruction, undo, containment, interactions, world-editing, self-test, dedicated-server, forge]
---
# 61 destructive modes for a Minecraft 26.3 Forge terraforming tool

> A fourth round on a Forge mod's World Warper item (see the notes on 84, 150 and 222 modes): 61 destructive modes
> (283 plus Custom) in 11 subcategories (explosive, thermal, cryogenic, kinetic, corrosive, energy, gravitational, sonic,
> natural forces, biological, exotic), each with its own damage type and death message. Spreading modes (a firestorm, a
> blight, a locust swarm) are capped by the server (radius, lifetime, blocks), persistent ones (mines, remote charges, a
> coil) are saved zones, two modes fire while right-click is held, and seven switchable interactions let modes act on
> what other modes left (cracked, frozen, corroded, wet). Every write still goes through the recording sink, so undo stays
> exact. Checked in the real game with a self-test of every mode, a containment test, scripted interaction scenarios,
> another mod pair loaded, and a dedicated server.

## Setup
- Minecraft Java 26.3, Forge 66.1.5, ForgeGradle 7, JDK 25. No mixins.
- Dev runs only (`runClient` with a scenario script, `runServer` for the dedicated checks); the user's launcher instance
  and saves untouched (backed up first).

## Route and why
Loader API plus the mod's plan / sink design. New shared pieces: a `spreading()` and a `paced()` flag on plans, a hook in
the recording sink for interactions, an in-memory store of block "conditions" (cracked, weakened) with expiry, and zone
kinds for persistent objects. Existing modes were re-tested unchanged (same pass / known-limit list as before).

## How the game works (what we had to learn)
- **A job's `step()` can run many times per server tick.** The job runner hands a plan its block budget in 256-block
  slices, calling `step` once per slice. Plans that count *ticks* (a 15 s swarm, a swing, a wait between blasts) ran ~16x
  fast: a 15 s Locust Swarm ended in 19 ticks. Fix: a `paced()` plan gets one `step` per game tick with the whole budget.
  (Older animated modes have the same effect; left as they were, noted.)
- **What the game breaks next.** Removing a block also removes what depended on it: snow layers, plants, torches (broken
  by neighbour updates, not by your writes), leaves' `distance`, gravel and sand that then fall. Undo only knows your
  writes. Before removing a block, snapshot the attached neighbours (up and the four sides, non-full-cube) into the record;
  place gravel / sand only on something that stays solid (decide end states first, bottom up).
- **Fluids keep going.** Water you place flows up to 7 blocks (more down slopes) and forms new sources next to existing
  water. For a flood: snapshot the band the water can reach before placing any, drain the whole band at the end, and keep
  fluid placement 8 blocks inside any radius cap so the flow stays inside it.
- **Disaster events finish after the warp.** A warp that starts a small disaster (acid rain, a tremor) returns at once; a
  test that counts changes 2 s later sees nothing. Wait out the event's duration.
- **26.3 details:** `ParticleTypes.FLASH` takes a `ColorParticleOption` (`ColorParticleOption.create(FLASH, argb)`);
  `AreaEffectCloud(level, x, y, z)` with `setRadius`, `setDuration`, `setWaitTime`, `setRadiusPerTick`, `addEffect`
  (`MobEffects.POISON` is a `Holder`). The mod's TNT-compat "volatile" tag lists only the TNT mod's blocks, so chain
  reactions can't be tested without that mod.

## Build steps
1. **Subcategories as data, not new categories.** An enum (name, colour, icon, damage type id) and a map of mode id to
   subcategory; the browser groups Destruction under headings, the radial menu shows a ring of 11 subcategory tiles first.
   Existing modes got tags only.
2. **Containment in the sink, not the modes.** For a plan marked spreading, the job refuses writes farther than the cap
   from where it started, stops after a block cap and ends at a lifetime cap, whatever the mode's own settings say.
   `/jod stopall` ends spreading jobs (what they did stays undoable) and disarms persistent zones.
3. **Persistent objects are zones.** Mines, remote charges and a coil are saved zones (listed, removable, capped per
   player, undone with their warp). Their later detonations write through a per-zone record so undo can still restore.
4. **Hold to fire.** The client sends a small "hold" packet every 2 ticks while use is held; the server warp keeps
   going while they arrive (an 8-tick gap = released), draining charge per second.
5. **Interactions in one place.** The sink calls a hook after a 1.17 mode's write: frozen neighbours shatter (kinetic,
   sonic, explosive), weakened neighbours give way (anything but corrosive), heat melts sand to glass and ice to water
   (thermal). One layer, never chained (a re-entry flag). Marks (cracked, weakened) live in memory with an expiry and a
   cap, so nothing is saved and stale marks vanish. Each interaction is a config switch.
6. **Damage types per subcategory** as data (`damage_type/*.json`, death messages in the lang file, explosive in
   `is_explosion`, thermal in `is_fire`).

## Verification
- **The 61 modes (self-test: build a scene, apply, count, undo, compare):** first full run 53 / 61; 8 fixed (falling
  gravel, leaves, flood water, snow layers, a crash on a null block, a plan that never advanced); then 61 / 61, and again
  after pacing.
- **All 283 + Custom:** 277 pass + the same 6 known limits as before + one night-time refusal (the half-hour test let the
  clock run; now stopped at noon): no regression in the old modes. Server tick during the new modes: 2.6 ms average,
  10 ms worst.
- **Containment test:** 12 spreading modes at radius 40 / 120 s against caps of radius 6 / 3 s / 300 blocks: every one
  stopped at 60 ticks, farthest change 6.4 blocks, undo exact.
- **Interactions (scenario):** each of six pairs changed what it should (e.g. resonance shattered all 149 cracked bricks)
  and undoing all nine warps restored the counts exactly.
- **Custom chains:** the 61 as one-step Custom warps 61 / 61; a two-step chain of new modes applied and undone exactly.
- **Dedicated server with a TNT mod and an add-on loaded:** see the project's status file (op / non-op, a protected
  area, mines and charges surviving a restart).

## Gotchas
1. Tick-counting plans and a job that steps per budget slice: pace them per game tick or they run many times too fast.
2. Snapshot attached neighbours (snow, plants, torches) before removing their support, or undo leaves them gone.
3. A returned `false` inside a `for` loop skips the loop's increment: a plan that never advances and never ends. Give
   self-tests a per-mode timeout so one stuck mode doesn't hang the run.
4. Water you place keeps flowing after the warp and outside any cap: snapshot first, drain everything, keep it inside.
5. A long self-test in a world with a running clock reaches night; day-only modes then refuse. Stop the clock.
6. Scenario `fill` commands over 32,768 blocks fail silently in the log; split them, or sand placed above air falls away.
7. A screenshot taken in the same tick as hiding the HUD still shows the HUD; wait a few ticks.
8. A random-tick world turns covered grass to dirt during a test; turn random ticks off when counting blocks.
9. Bash heredocs passed through a tool wrapper can break on quotes in the payload; write patch scripts to a file.

## Assets
No new textures; damage types and death messages are data files. The mode icons are vanilla item ids.

## Cost and time
One long session. The 61-mode self-test takes about 6 minutes, the full 284-mode run about 30 minutes, the containment
test about 2 minutes.

## Open questions
- Interactions don't fire inside Custom chains (the chain, not the mode, is the warp); worth passing the step's
  subcategory down.
- The older animated modes still run faster than their seconds setting (left unchanged on purpose).
