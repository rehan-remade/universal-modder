---
kind: game
title: 'Translating the Batmobile into a Just Cause 3 vehicle: a row ledger from two file grabs'
game: 'Just Cause 3'
games_also: ['Batman: Arkham Knight']
game_version: 'JC3: Steam build 20206564 (2025-12-17), JustCause3.exe timestamp 0x5787641c. BmAK: GOG Premium Edition 1.999, buildId 57731640734362250'
platform: windows
engine: native
route: asset-only
tools: ['custom Python generators with --write/--check (one per translation card)', 'Gibbed.JustCause3 tools', 'Blender 5.2 (headless)', 'Capstone (executable store-site search)']
anti_cheat: 'none (single-player, offline)'
status: in-progress
agents: ['Freebuff (DeepSeek V4.1 1017)', 'Claude Code (Opus 5.5)']
humans: ['@NotTrevino']
date: '2026-10-30'
links: []
tags: ['porting', 'cross-game', 'vehicles', 'translation-ledger', 'batmobile', 'damage-model', 'weapons', 'audio', 'lights', 'collision', 'verification', 'agent-workflow']
---

# Translating the Batmobile into a Just Cause 3 vehicle: a row ledger from two file grabs

> Porting a vehicle between two engines is not one conversion; it is a few hundred small
> decisions, each of which can be silently wrong. This project made every one of them a **row**:
> a source value from Batman: Arkham Knight, a carrier in Just Cause 3, a transform, a
> disposition and the file that proves it. The ledger holds **180 rows**: 126 resolved from
> evidence, 1 assumed, 17 blocked, 43 out (JC3 has no system for them) and 8 superseded. **No row
> has been verified in game yet**, so this note is about the method and what the files decided,
> not about a finished car.

## Setup

- The two read-side grabs come first and have their own notes: the
  [Arkham Knight Batmobile scrape](../batman-arkham-knight/scraping-the-batmobile-umodel-pskx-wwise.md)
  (mesh, materials, audio, 423 named native fields, animations, damage rules, camera, HUD) and the
  [JC3 fleet read](reading-the-vehicle-fleet-archives-rtpc-havok.md) (every vehicle's modules,
  meshes, collision and systems). The geometry side is the
  [mesh-editing note](vehicle-mesh-editing-added-geometry-loads-with-matching-toc.md).
- The donor is the Serpente, `v0300_car_kensington_sportsmuscle_civilian_01`. Both games are owned
  by the user. Nothing from either game is in this repository.
- Work was split into cards (G1 = BmAK grab, G2 = JC3 grab, T = translate, B = build). The agents
  were Freebuff running DeepSeek V4.1 1017 and Claude Code, with one card per session and a
  journal entry before and after each card.

## Route and why

The obvious route is "convert the mesh, copy some handling numbers, drive it and tweak". It was
tried first, and it fails in a specific way: a value that looks right in game can be right by
accident. This project's camera distance was 7.0 m both before and after decoding the camera,
but the original method (scaling by body length) was wrong. A tweak loop cannot tell those apart.

The ledger route:

1. **Grab both sides to files first.** Every value on both sides comes from a decoded record with a
   `--check`, never from memory or a forum post.
2. **One row per requirement.** Each requirement code (`WPN-1` heavy cannon, `ARM-2` tank-shell
   armour, `AUD-2` boost sound …) gets one or more rows. 75 of 75 requirement codes are mapped.
3. **A disposition per row, with a class per value.** Dispositions: `next` (queued for a build),
   `keep` (the donor's value is already right), `blocked` (a named probe would decide it), `out`
   (JC3 has no system for it) and `superseded` (moved to a later card that found a carrier).
   Every value also carries a class: `decoded`, `derived`, `assumed` or `UNKNOWN`. A guess is never
   written down as `decoded`.
4. **The status page is generated, never asserted.** Percentages are counts over files, and no
   workstream as a whole is ever called 100%.

## How the translation works (what we had to learn)

### Decisions the files cannot make

Ten design decisions were put to the user in one table, each with the evidence for every option,
and their rulings recorded with a revert path. Examples: D-1 keep the PSKX's true scale (the tyre
measures 1.366 m, not the wiki's 1.40); D-2 one hybrid car that carries both pursuit and battle
mode; D-3 accept JC3 lethality (a lethal/non-lethal toggle was added and then withdrawn by the user);
D-6 a standalone entity rather than replacing traffic (the donor is traffic, so replacing it puts
NPC-driven Batmobiles on the roads); D-8 the car sinks and stalls in water, which matches the lore;
D-10 no JC3 gear mods, and JC3 functions may only be borrowed to make the car lore-accurate.

### What the files decided

- **Armour.** `CCar.invulnerable` is an all-or-nothing engine gate, so a tank cannon would read
  "never kills", and the lore ratio (24 tank shells) cannot exist under it. The armour comes from
  the armour channel split plus `max_health` **36000**. If one in-game probe shows damage is
  applied as a percentage rather than as flat hit points, the same ratio needs 18000. The two
  candidates differ by exactly the factor the probe tests.
- **Weapons.** Each Batmobile weapon gets an existing JC3 carrier: heavy cannon →
  `w602_mediumtank_canon` on `main_weapon`; Vulcan → `w603_mediumtank_mgun` on the second driver
  slot (`00568A74`); missiles → the donor's own `w618_sportsmuscle_missile`. The EMP missile is
  blocked, because JC3's pulse has no "disable" member. Of 136 weapon aspects, 53 are `UNKNOWN`,
  and they are named rather than guessed.
- **Moving parts.** 11 parts cut from the body by bone ownership (turret, cannon, Vulcan, riot
  suppressor, two missile pods, four aero flaps, jet). Every pivot agrees with the bone table to
  1.39e-5 m. Joint spans and rates are measured from the exported key frames. For example, the
  Vulcan spins 6.00 turns in 3.9 s; the earlier "357.4° per spin" was a wrap-around artefact.
- **Lights.** The donor's module addresses a light preset by a 32-bit id and its graph names it by
  string. `hash_jenkins(name)` joins the two. All 28 entries of the Batmobile's light rig map to an
  `SVehicleLight` or a named omission.
- **Audio.** 53 rows over the donor's 45 FMOD events. A swap counts as `mapped` only with a chosen
  slot and a loudness delta measured on the exact payload the swap would write. With no semantic
  bridge, the row is `blocked` with a named probe, not "kept vanilla" by default.
- **Collision.** Arkham Knight's 32 physics bodies are not the drivable car. The asset is
  `Batmobile_V3_Destroyed_Physics`: 18 debris fragments, a 30 cm placeholder root and no chassis
  body. Only 11 bodies are drivable, and they map onto 7 donor hull slots. The new moving parts
  have no slot, so giving them collision needs a new hull, which the `.physicsc` writer cannot yet
  make.
- **Interaction.** Entry, exit and stunt points are placed by role, not by the donor's position:
  side doors by a ray cast at seat height, hood points on the front deck and stunt points on the
  roof. Each point is pushed out along the surface normal until it clears the body by the donor's
  own measured clearance.
- **Modes.** JC3 has no mode switch, so the hybrid car carries 7 of the 15 mode rows directly, keeps
  1 inside a band and omits 7, each with the compromise stated. Battle mode's speed curve and the
  21.6 km/h turning-mode cap need a switch the engine does not have.
- **HUD.** No entity reaches `hud.gfx`, and the Batmobile's speed readout is a debug feature, so
  the HUD rows map to the existing vehicle weapon slots, reticle and cooldown setters.

### The build scaffold

`bm_build.py` makes a build from the ledger alone. Its first output, `bm-001`, is an **identity
build**: no rows are applied, and it repacks the donor `.ee` (590 files) with a matching `.toc`
and a receipt of digests. Every later build is that control plus a listed set of rows, so a crash
can always be bisected to a row.

## Build steps

1. Grab both games to records with `--check` gates (see the two grab notes).
2. Write the requirement codes (what the car must do, from the lore), then one row per code and
   carrier, each with its evidence file.
3. Put every choice the files cannot make to the human as a decision table, record the ruling with
   a revert path, and never let an agent decide one.
4. Generate each translation document from its row data with a script, and fail `--check` on any
   number typed into prose.
5. Close the ledger: every requirement code has a row, and every `next` row is assigned to a build
   batch.
6. Build an identity control first, then add batches of rows on top of it.
7. Verify each batch in game, one manoeuvre per row. **Not done yet.**

## Verification

- 75 of 75 requirement codes mapped; 777 Batmobile feature rows (weapons, animation, audio, lights)
  each assigned to a translation row by a declared rule, with an unmatched row a FAIL.
- Built and read back: test-085 carries 35 values over 16 rows, read back through its `.toc`
  (35/35). Later batches are in test-089 (4 values) and test-090 (2 values), and test-090 is read
  back through the installed `.toc`. All of that is file level, not behaviour.
- **Not verified:** any row's behaviour in game (0 of 180). Four rows have partial manoeuvre
  measurements.

## Gotchas

1. **A right number from a wrong method.** **Cause:** a tweak loop accepts any value that looks
   right. **Fix:** re-derive each value from its source and record the method; the camera's 7.0 m
   survived a wrong method by accident.
2. **The denominator makes 100% impossible.** **Cause:** rows that JC3 cannot express were counted
   as unfinished. **Fix:** exclude `out` rows from completion and require a re-readable proof that
   the system is absent.
3. **An `out` row was never re-read.** **Cause:** rows were marked `out` before the JC3 grab had
   looked for a carrier. **Fix:** re-open every `out` row once the fleet records exist. 16 were
   re-decided, and 5 moved to cards that found a carrier (weapons, EMP, battle values, spotlight,
   battle camera).
4. **A green check over a stale artefact.** **Cause:** a generator copied a live row from another
   card's document, and the other card later changed it. **Fix:** never embed another card's live
   decision; freeze a snapshot with its sha256 and point to the live row.
5. **Hand-written prose rots.** **Cause:** numbers typed into Markdown next to a checked JSON.
   **Fix:** render every number from data, and diff the page byte for byte in `--check`.
6. **Reviews find real bugs.** Every finished card was reviewed by a second agent session and
   reworked against the data. Across the reworks, almost every issue was confirmed when re-checked,
   and a few review claims were rejected with evidence. Re-check each issue before editing, and
   expect the reviewer's own numbers to be wrong sometimes.

## Assets

None in this repository: the ledger rows, generators and decision table live in the project
folder, and every build stays local.

## Cost and time

About a week of agent sessions (2026-10-24 to 10-30) for the translation and review cycle, on top
of the two grabs. Most of the cost was rework: making every page generated and every check honest.

## Open questions

- **Every row, in game.** One manoeuvre per row, starting with the identity build and the first
  batches.
- **The damage model probe.** Flat hit points or a percentage decides between `max_health` 36000
  and 18000.
- **New collision hulls** for the 11 moving parts.
- **The EMP missile's disable effect** has no carrier in JC3's data.

## Related and credits

- [Arkham Knight Batmobile scrape](../batman-arkham-knight/scraping-the-batmobile-umodel-pskx-wwise.md)
- [JC3 fleet read](reading-the-vehicle-fleet-archives-rtpc-havok.md)
- [JC3 vehicle mesh editing](vehicle-mesh-editing-added-geometry-loads-with-matching-toc.md)
