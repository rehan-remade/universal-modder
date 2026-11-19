---
# Field note: how a game was modded, written so the next agent can repeat it. Keep the keys; delete the comments.
# Quote list items with ": ", a comma or only digits in them, e.g. games_also: ["Cataclysm: Dark Days Ahead"].
kind: game
title: "Homing missiles and a tactical nuke in Terraria"   # what you built, in plain words
game: "Terraria"                                          # the game's usual name
games_also: []                                            # other games involved (mashups), e.g. ["Minecraft Java Edition"]
game_version: "1.4.4.9 via tModLoader 2026.07, Steam"     # exact build that worked
platform: windows                                         # windows | linux | macos | proton | emulator | console | other
engine: xna-fna                                           # um scan's engine key (unity-mono, unreal, source2, rage, ...) or unknown
route: loader-api                                         # data | asset-only | loader-api | managed-patch | native-hook | reimplementation | decomp-recomp | passthrough | emulator | other
tools: ["tModLoader", "ilspycmd", "fal (flux/dev)"]
anti_cheat: "none"                                        # what protects it, and how you stayed clear (e.g. "BattlEye, story mode with -nobattleye only")
status: working                                           # idea | in-progress | working | released | abandoned
agents: ["Claude Code (Opus 5.5)"]                        # agent + model that did the work
humans: []                                                # handles of the humans involved, if they want credit
date: 2026-09-30
links: []                                                 # repo, example folder, video, post
tags: []                                                  # free-form: weapons, boss, sprites, depth-compositing, ...
---

# Homing missiles and a tactical nuke in Terraria

> Two to four sentences: what you built, in which game, by which route, and whether it runs in the real game
> (and how you know).

## Setup
Game build, store, OS, loader/tool versions, anything installed first. The versions that worked are the most
useful thing you can write down.

## Route and why
Which route (see `route:`), what else you considered, and why you didn't take it.

## How the game works (what we had to learn)
The engine facts you discovered: file formats, key classes/functions/natives, coordinate systems, data layouts,
frame layouts, hard-coded limits. Describe them in your own words and name the symbols; don't paste decompiled
code or game data. Link public docs where they exist.

## Build steps
The shortest path to reproduce, in order: commands, settings, where files go.

## Verification
How you knew it worked: the oracle (in-game test scene, logs, screenshots you looked at, trace replays,
round-trips), and what you did NOT verify.

## Gotchas
The most valuable section. Numbered; each one symptom → cause → fix.
1. **Symptom.** What you saw. **Cause:** what it really was. **Fix:** what worked.

## Assets
How art/audio/3D were made (models, prompts, `um` commands), if any.

## Cost and time
Optional: wall-clock, sessions, API spend.

## Open questions
What's unresolved or would be the next step.
