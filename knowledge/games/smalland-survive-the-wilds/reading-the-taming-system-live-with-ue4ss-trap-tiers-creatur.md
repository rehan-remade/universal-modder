---
kind: game
title: 'Reading the taming system live with UE4SS: trap tiers, creature difficulty and the measured success formula'
game: 'Smalland: Survive the Wilds'
games_also:
- Valheim
game_version: steam 768200, buildid 22695059, UE 4.27 (++UE4+Release-4.27)
platform: windows
engine: unreal
route: loader-api
tools:
- UE4SS experimental (v3.0.1-1160-g3f4037d2)
- UE4SS Lua
- UE4SS CXX header dump
anti_cheat: "none (um scan found none, and the Steam store page lists none; RedpointEOS is Epic Online Services for co-op). UE4SS only ran in a solo/offline world, never in co-op."
status: working
agents:
- Claude Code (Opus 5.5)
humans:
- Culp
date: '2026-10-05'
links:
- ../valheim/smalland-style-trap-taming-in-valheim-four-trap-tiers-tame-a.md
tags:
- ue4ss
- taming
- gameplay-ability-system
- measurement
- oracle
- encrypted-paks
- live-read
---
# Reading the taming system live with UE4SS: trap tiers, creature difficulty and the measured success formula

> UE4SS Lua mods read Smalland's taming data straight from the running game: every creature's taming
> difficulty, all four taming-trap tiers, and the success formula, measured by calling the trap's own roll
> function 9,600 times. The point was to port the system into another game (Valheim), so nothing in Smalland
> is changed. Verified in the real game: 2x run speed toggle confirmed by the human, and every number came
> from live objects.

## Setup
- Smalland Steam build 22695059, Windows 11, solo/offline world.
- **Keep the modded game out of co-op.** Smalland has online co-op and dedicated servers. UE4SS was only ever
  loaded in a solo/offline world, and the modded game never hosted or joined a session. Take `dwmapi.dll` out
  of `Binaries/Win64` (or start the game unmodded) before playing with anyone.
- **UE4SS experimental `UE4SS_v3.0.1-1160-g3f4037d2`** (GitHub `experimental-latest`, sha256
  `8318394877278a6342f2bbff3778f076da042d2fff91c414f66b227388488e48`). Layout: `Binaries/Win64/dwmapi.dll` +
  `Binaries/Win64/ue4ss/` (log at `ue4ss/UE4SS.log`).
- `UE4SS-settings.ini`: `MajorVersion = 4`, `MinorVersion = 27` (required), `EnableHotReloadSystem = 1` (Ctrl+R).
- Only our Lua mods + `Keybinds` enabled; the default cheat/console mods turned off.
- Saves backed up first: `um backup create "%LOCALAPPDATA%\smalland\Saved" --name smalland-saved`.

## Route and why
UE4SS Lua (loader API): reads and writes any UProperty and calls UFunctions in the live game. Pak extraction
was the alternative, but the paks are AES-encrypted (see Gotchas), and we did not want to extract keys. Reading
the running game's memory needs no key and gives the real values.

## How the game works (what we had to learn)
- Player pawn `BP_BaseCharacter_C`, custom movement `SLPlayerMovementComp` (still honours
  `CharacterMovement.MaxWalkSpeed`: 450 base). Stats live in the Gameplay Ability System
  (`SLAbilitySystemComponent`, attribute sets such as `SLSurvivalAttributeSet` with `TamingSkillModifier`,
  `PlayerPartyPoints`, `StableCapacity_*`).
- **Taming is a deployable trap, not feeding.** `ABP_TamingTrap_Base_C` (children Basic / Improved / Advanced /
  Supreme) at `/Game/Construction/Deployables/TamingTraps/<Tier>/BP_TamingTrap_<Tier>`; items at
  `/Game/Items/Deployable/TamingTraps/` (`DI_`, `BPI_`, `CR_` = item data, item, crafting recipe). Trap fields:
  `TrapTamingSkill`, `BaseRateRange` (Vector2D), `TrapAttractionRadius`. Flow: trigger overlap -> valid
  `ASLAnimalCharacter` -> countdown -> `RollTamingSuccess(skill, difficulty)`.
- **Per-creature data** is a `USLCharacterData` data asset (`CD_<Creature>`): `bIsTameable`, `TamingTrapDifficulty`,
  `TamingTrapCountdown`, `Tier`, `DifficultyRating`, `PartyWeight`.
- **Tamed state** on `ASLAnimalCharacter`: `TamingPlayer`, `bShouldFollowTamer`, `CurrentRider`, `OwningStable`,
  `CharacterProgressionComp`. Commands are interaction widgets (CanTame, Release, Follow / Stop / Pause,
  AggressionStance with `ESLAIAggressionStance` Default / Defensive / Aggressive / Passive, HarvestResourceNode,
  Pet, Inspect). Mounts: `GA_IE_TryMountCreature`, `GA_Dismount`, per-creature mounted attacks.

### Numbers read live (build 22695059)
| Trap tier | TrapTamingSkill | BaseRateRange | TrapAttractionRadius |
|---|---|---|---|
| Basic | 1 | 1, 10 | 6250 |
| Improved | 2 | 1, 10 | 6250 |
| Advanced | 3 | 1, 10 | 6250 |
| Supreme | 4 | 1, 10 | 6250 |

Tameable creatures seen (difficulty / countdown s / tier / party weight): Ladybug 3 / 5 / 0 / 5,
Grasshopper 5 / 5 / 1 / 10, Damselfly 5 / 5 / 1 / 10, Gecko 8 / 5 / 2 / 15, Hornet 16 / 5 / 4 / 25.
Difficulty set but `bIsTameable` false: ant worker 3, butterfly 3, bees 5, red ant warrior 5, sawyer 5,
wasp 8, jumping spider 12, **horned beetle 28**. Never tameable (-1): ghosts, birds, Wyrd Weaver, humanoids.
The Wyrdweaver albino scorpion companion is tameable with difficulty -1 (not by trap). Countdown is 5 s for all.

### Measured success formula
Calling the Basic trap CDO's `RollTamingSuccess(skill, difficulty)` 400 times per pair (skill 1-4 x
difficulty 3, 5, 8, 12, 16, 28) fits
**success iff `skill * Uniform(1, 10) >= difficulty`**, i.e. `P = clamp((10 - difficulty/skill) / 9, 0, 1)`.
All 24 cells are within sampling noise (max |z| = 1.84), and the 0 % / 100 % cells are exact. A Basic trap can
never catch anything above difficulty 10. Not measured: how the player's `TamingSkillModifier` enters (it was 0).

## Build steps
1. `um scan smalland`, then back up `%LOCALAPPDATA%\smalland\Saved`.
2. Install UE4SS **experimental** (not stable) into `SMALLAND/Binaries/Win64`, set the 4.27 override.
3. Lua mod `Mods/<Name>/Scripts/main.lua`, enable in `Mods/mods.txt` **and** `Mods/mods.json`.
4. Useful calls: `FindAllOf("SLCharacterData")`, `LoadAsset(<path>.<Class>_C)` then `:GetCDO()` (loads a
   class without placing anything), `ForEachUObject` to discover asset paths, BP functions with out params
   take a table: `cdo:RollTamingSuccess(skill, diff, out)` then `out.SuccessfullyTamed`.
5. Ctrl+H (Keybinds mod) dumps CXX headers (3,761 files) to find classes; copy the dump out of the game folder.

## Verification
- F6 test mod logged the pawn and toggled `MaxWalkSpeed` 450 -> 900; the human confirmed 2x speed in game.
- Creature and trap numbers came from live objects (CSV written by the probe). The formula came from the
  game's own function (9,600 calls), compared cell by cell with the model above.
- These measurements became the oracle for the Valheim port (linked note): Valheim's roll matches them within
  0.1 in all 24 cells.
- Not verified: the player taming-skill modifier, failure-side effects (refunds), stables, the relation system.

## Gotchas
1. **Stable UE4SS v3.0.1 never starts mods.** Log: `Failed to find EngineVersion`, then
   `Failed to find FText::FText(FString&&)` repeated until `Fatal Error: PS scan timed out`. **Cause:** the
   stable build's signatures don't match this 4.27 exe. **Fix:** set `MajorVersion=4 / MinorVersion=27` (fixes
   the first) and use the **experimental** build (fixes FText). Harmless warning left: ConsoleManagerSingleton
   found 2 values.
2. **Setting changes did nothing.** The human returned to the main menu instead of quitting; the process start
   time was older than the ini edit. **Fix:** check process start time; quit to desktop.
3. **The experimental build's log is buffered.** F7 output appeared ~6 minutes later. Not a hang: check
   `Responding` and CPU of the process before assuming one.
4. **Paks are AES-encrypted** (pak v11, `bEncryptedIndex = 1`, zero key GUID): grepping the index finds no
   paths. **Fix:** don't extract keys; read the live game with UE4SS instead.
5. **Trap classes aren't loaded until a trap exists**, so `FindAllOf` finds nothing and the human may have
   used their only trap. **Fix:** `ForEachUObject` to find the package paths, then `LoadAsset` the
   `BP_TamingTrap_<Tier>_C` class and read its CDO. No trap needed.
6. **A name search matched the wrong object.** The first probe counted the `BPI_TamingTrap` *item* CDO as a
   trap and stopped. **Fix:** load the exact `/Game/Construction/Deployables/...` class paths.
7. **`mods.txt` edits ignored** after a CRLF/LF mix from shell edits. **Fix:** normalise line endings and also
   add the mod to `mods.json` (the experimental build reads both).

## Assets
None.

## Cost and time
One evening (~2 h for this part), no API spend.

## Open questions
- How `TamingSkillModifier` combines with `TrapTamingSkill` (add or multiply); needs a save with a non-zero bonus.
- Exact relation-level rewards, stance AI and pet harvesting rules.
- Whether the horned beetle's `bIsTameable` is off by design or unfinished.
