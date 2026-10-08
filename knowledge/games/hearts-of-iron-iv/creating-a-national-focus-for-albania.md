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
status: working
date: 2026-10-08
agents: ["Codex (gpt-6)"]
---

# Creating a national focus for Albania

This note records a minimal working national focus tree for Albania in Hearts of Iron IV 1.19.3. The test was created as a standalone mod with a single `common/national_focus/ALB.txt` file.

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

The tested Albania condition uses a base `factor = 0` and a modifier adding `10` when the country tag is `ALB`.

The tested focus has:

- ID: `ALB_test_focus`
- icon: `GFX_focus_AUS_bring_back_the_habsburg_rule`
- position: `x = 6`, `y = 2`
- cost: `10`
- completion reward: `add_political_power = 67`

## Build steps

1. Create the mod directory.
2. Create `common/national_focus`.
3. Create `ALB.txt`.
4. Define the Albania focus tree.
5. Add the focus to the tree.
6. Enable the mod in the HOI4 launcher.
7. Start as Albania and verify that the focus tree appears.
8. Complete the focus and verify that the political power reward is applied.

## Verification

The completed test mod was checked with:

`um publish check "<mod path>" --game "<HOI4 installation>"`

The result was:

`PASS: 3 files, 0 failures, 0 warnings`

The three files were:

- `descriptor.mod`
- `README.md`
- `common/national_focus/ALB.txt`

## Gotchas

1. The Universal Modder `publish check` validates the mod for publish-related problems, but it does not prove that HOI4's focus logic is correct. A successful `publish check` should not be treated as proof that the focus tree will appear or behave correctly in-game.

2. The focus tree must also be tested inside Hearts of Iron IV.

3. The tested country condition uses `factor = 0` with an Albania modifier using `add = 10` and `tag = ALB`.

4. Using an existing focus icon is possible without adding a new image asset. The test uses an existing Austrian focus icon.

5. Do not copy original HOI4 game files into the mod. The mod should contain only the data that is being changed or added.

## Assets

No custom assets were required for the tested focus.

The focus uses the existing game icon:

`GFX_focus_AUS_bring_back_the_habsburg_rule`

## Cost and time

A minimal focus tree can be created with only a few plaintext files. The main work is writing valid Clausewitz data and testing the result in-game.

## Open questions

- Whether additional focus-tree validation can be performed automatically for HOI4 1.19.3.
- Which HOI4-specific syntax errors Universal Modder can detect beyond publish checks.
- Whether future Universal Modder knowledge entries should document more complex focus prerequisites, mutually exclusive branches, effects, and triggers.