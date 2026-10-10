---
kind: technique
title: "Evidence levels: reports, source reading, proposals and real runs"
tags: [verification, evidence, field-notes, honesty, attribution, lineage, tests, mashup]
date: 2026-10-05
agents: ["Claude Code (Opus 5.5)"]
humans: ["LeiiLo"]
links: []
---

# Evidence levels: reports, source reading, proposals and real runs

> When an agent reads up on existing mods (or writes up its own), the same sentence, "X works", can
> rest on a creator's video, a README, code that was read, a test that passed, or a real play session. Keep
> those apart in notes and in what you tell the user.

## When to use it
- Researching existing projects before choosing a route (`um kb search`, READMEs, commit pages, repos).
- Filling a field note's **Verification** section and `status:`.
- Reporting progress to the user.

## How

### Label every claim with one of these
| Level | Means | Wording |
|---|---|---|
| **Creator report** | someone says it works (README, post, video, commit message) | "the creator reports…" |
| **Design / proposal** | planned, drafted or described as future work | "planned", "proposed" |
| **Source inspection** | code or docs were read; nothing was run | "the code does…", "static finding" |
| **Derived comparison** | a diff or comparison between versions or forks | "compared with upstream X" |
| **Synthetic test** | a test, fake host or fake guest ran | "passes against a fake host" |
| **Real run** | the real game(s) ran this build and someone looked | "verified in game on <version, OS, GPU>" |

Only the last row supports `status: working` from your own work, and only for the scenarios actually played.

### Things that look like proof and aren't
- **A design document.** [Garry's Redemption](https://github.com/codeByAlexff/garrys-redemption)'s `CLAUDE.md` brief plans in-frame Vulkan/DX12
  compositing; v0.1.0-beta ships a separate overlay window, and its README calls in-frame drawing "not built".
- **A passing test that checks little.** The GTA V example's `ws_test.cpp` passes if any received string
  contains `explosion`. One project's changelog records a save-verification task that once passed with no game data
  present. A conditional asset test can skip the meaningful check when owned files are missing.
- **A synthetic peer.** [LibertyCraft](https://github.com/mrborghini/libertycraft) ships stand-ins for both ends of its bridge; passing one still needs both
  real games.
- **A percentage badge.** AnyPS5 reports progress against *known declared* system functions; the denominator
  grows as more are found. It is not game compatibility.
- **A clean install on the author's PC.** It isn't a second machine. Several projects report a single tested
  machine (e.g. Garry's Redemption: one Windows 11 / NVIDIA / Vulkan PC).
- **A "golden" sweep that can't fail.** The [benilla](https://github.com/samwhosung/benilla) / [World of Skatecraft](https://github.com/Kimmo3223/world-of-skatecraft) history records correcting tests
  whose names promised more than they checked, and screenshot sweeps that were reporting success without checking; it later made
  a skipped addon test fail instead of pass.
- **A count of checks.** The Diablo II movement mod reports 65/65 checks, but they measure different things
  (table agreement, travel time, level hashes, best-of-N frame rate), and owned-file checks skip when files
  are missing.
- **Changed rules, same leaderboard.** [Touhou HFR](https://github.com/vittorioromeo/th12_hfr)'s smaller simulation steps can change hits and scores, so
  its own docs say runs aren't comparable with stock; full-run replay parity is unverified.
- **Docs stronger than code.** [Signet](https://github.com/kian-cx/signetprotocol)'s docs say the client never blocks and that authority prevents
  cheating; the code writes TCP under a lock and the roadmap lists command-rate checks as pending.
- **A clip of one mode.** [Halo / MW2 Director](https://github.com/0xburn/halo-mw2-director) has an authored cinematic, an imported map that MW2's
  rules run, and a bot match. Footage of one says nothing about the others, so name the mode a clip shows.
- **A source repo's "no assets" wording.** CS:Craft's source copies no assets, but its Windows release
  bundles a Minecraft client JAR and assets (its release README says so). Check the release package as well as
  the repo. [WiiCompiled](https://github.com/patchzyy/Wiicompiled)'s THIRD-PARTY-NOTICES lists every bundled runtime file
  and where it came from: copy that.
- **A negative result without its scope.** Host depth that's flat in the main menu says nothing about depth
  during gameplay. Record where a negative result was taken.
- **An edited video.** Cuts hide stale frames, sampled frames miss short events, and automatic captions
  misname games.
- **An action the bridge offers.** In [chasm](https://github.com/chasmlol/chasm) (language-model NPCs with a Fallout: New Vegas bridge), an
  action being available isn't proof it ran in the game.

### Lineage and attribution
- Record the exact upstream commit a fork started from. LibertyCraft's first commit says it forks [SkyCraft](https://github.com/chasmlol/SkyCraft)'s
  Fabric mod and protocol header, but it has no parent, so the exact base can't be recovered from history.
- A new file name isn't new code; relocated upstream helpers stay upstream work.
- A fork's history includes the upstream's commits and their credits. [FalloutCraft](https://github.com/zeyvu/FalloutCraft)'s history carries SkyCraft
  commits co-authored with an AI model; they don't describe the later Fallout-specific changes.
- AI credit attaches to the work its author credits. Explicit model credits exist for several projects
  ([NewVegasCraft](https://github.com/Davozh/new-vegascraft)'s pages, the Half-Life bridge, Garry's Redemption); historical foundations such as
  older decompilation projects and DevilutionX are human-led. Absence of credit is not proof either way.
- A project in a recent video isn't necessarily AI-made. libsm64 had Garry's Mod hosts calling into it
  long before the current wave of AI-made mashups.

### In a field note
- `status:` describes your own verified state; quote others' claims in the text.
- In **Verification**, say what was run, on which versions/OS/GPU, and what was not.
- Keep corrected diagnoses: LibertyCraft's history first blames one cause for a GFWL loop, then removes a
  different add-on as the real cause. The correction is the useful part.

## Gotchas
1. **Collapsing sources into one claim.** **Symptom:** a note says "supports multiplayer" because a README
   says so. **Cause:** report treated as verification. **Fix:** "the creator reports LAN multiplayer; not
   tested here".
2. **Counting reposts as corroboration.** Several representations of one creator's material are not
   independent. **Fix:** count sources, not copies.
3. **Treating extraction as reading.** Hashing, unzipping, OCR or listing archive members is not having read
   or understood the code. **Fix:** say what was read, by file.
4. **Upgrading creator measurements.** "18.7 → 5 ms" from a commit page is the creator's number. **Fix:** keep
   the attribution even when it's convenient to drop it.

## Verification
This is a method note; its examples are indexed in `skills/mashup-mods/references/mashup-cases.md`.
