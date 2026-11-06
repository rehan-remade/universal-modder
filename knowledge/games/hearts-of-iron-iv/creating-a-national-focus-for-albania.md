---
kind: game
title: Creating a national focus for Albania
game: Hearts of Iron IV
game_version: "1.19.3"
platform: windows
engine: clausewitz
route: data
tools:
  - Universal Modder
  - Steam
anti_cheat: none found by um scan
status: in-progress
date: 2026-10-08
agents: ["Codex (gpt-6)"]
links:
  - https://hoi4.paradoxwikis.com/National_focus_modding
tags: ["hoi4", "national-focus", "paradox-script"]
---

# Creating a national focus for Albania

This note records a minimal national focus tree for Albania in Hearts of Iron IV 1.19.3, built as a standalone mod
with a single `common/national_focus/ALB.txt` file. Only `um publish check` has been run on it so far; the tree
has not been checked in game yet (see Verification).

## Setup

The mod uses the normal Hearts of Iron IV user mod structure:

- `descriptor.mod`
- `README.md`
- `common/national_focus/ALB.txt`

The focus file defines a focus tree with an Albania-only country condition.

## Route and why

Use the normal data modding route because national focus trees are defined through plaintext game data.

Relevant path:

`common/national_focus/ALB.txt`

The game loads the focus tree from the mod's `common/national_focus` directory.

## How the game works

A minimal focus tree can be defined with:

- a `focus_tree` block;
- an `id`;
- a `country` condition;
- `default = no`;
- one or more `focus` blocks.

The `country` block is a score: each country gets the tree with the highest score. The Albania condition here uses a
base `factor = 0` and a modifier adding `10` when the country tag is `ALB`. Albania has no vanilla tree of its own
(it uses the generic one), so `add = 10` has nothing to beat (Gotcha 3).

The focus has:

- ID: `ALB_test_focus`
- icon: `GFX_focus_AUS_bring_back_the_habsburg_rule` (a vanilla sprite; vanilla's Austrian tree uses it)
- position: `x = 6`, `y = 2`
- cost: `10` (cost is in weeks, so 10 is 70 days)
- completion reward: `add_political_power = 67`

## Build steps

1. Create the mod directory.
2. Create `common/national_focus`.
3. Create `ALB.txt`.
4. Define the Albania focus tree.
5. Add the focus to the tree.
6. Enable the mod in the HOI4 launcher.
7. Start a new game as Albania and check that the focus tree appears (not verified yet; see Verification).
8. Complete the focus and check that the political power reward is applied (not verified yet).

## Verification

- **Checked:** `um publish check "<mod path>" --game "<HOI4 installation>"` gave
  `PASS: 3 files, 0 failures, 0 warnings` for `descriptor.mod`, `README.md` and `common/national_focus/ALB.txt`.
  That only shows the mod passes the pre-release lint (no game files, decompiled code or secrets); it doesn't
  check focus logic.
- **Not verified:** the in-game test (Build steps 7-8): that the tree shows when starting as Albania, that
  completing `ALB_test_focus` gives +67 political power, and that `error.log`
  (`Documents/Paradox Interactive/Hearts of Iron IV/logs`) stays clean.

## Gotchas

The gotchas below come from the HOI4 wiki's national focus modding page, not from this test.

1. **The focus shows its raw ID (`ALB_test_focus`) as its name.** **Cause:** it has no localisation. **Fix:** add
   `ALB_test_focus:` and `ALB_test_focus_desc:` keys to a `localisation/english/*_l_english.yml` file, saved as
   UTF-8 with BOM.
2. **The new tree doesn't appear in an existing save.** **Cause:** the tree with the highest `country` score is
   chosen before the game starts, and the choice is never refreshed. **Fix:** enable the mod first, then start a
   new game.
3. **A custom tree doesn't replace a country's own vanilla tree.** **Cause:** that tree's `country` score is
   higher. **Fix:** beat its score (Austria's tree uses `add = 50`). Albania uses the generic tree, which is why
   `add = 10` is enough here.
4. **The focus is missing from the focus search filters.** **Cause:** `search_filters` is optional and isn't set.
   **Fix:** add a `search_filters` block to each focus (recommended, e.g. `FOCUS_FILTER_POLITICAL` for a political
   power reward).

## Assets

No custom assets were required for the focus.

The focus uses the existing game icon:

`GFX_focus_AUS_bring_back_the_habsburg_rule`

## Cost and time

A minimal focus tree can be created with only a few plaintext files. The main work is writing valid Clausewitz data
and testing the result in-game.

## Open questions

- Does the tree appear in game when starting as Albania, and does the reward apply (Build steps 7-8)?
- The exact `ALB.txt` and `descriptor.mod`, and where the mod folder and the launcher's outer `.mod` file went.
- Whether additional focus-tree validation can be performed automatically for HOI4 1.19.3.
- Which HOI4-specific syntax errors Universal Modder can detect beyond publish checks.
- Whether future Universal Modder knowledge entries should document more complex focus prerequisites, mutually
  exclusive branches, effects, and triggers.
