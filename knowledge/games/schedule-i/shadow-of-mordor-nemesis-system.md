---
kind: game
title: "Shadow of Mordor Nemesis system across Cartel and Police factions in Schedule I"
game: "Schedule I"
games_also: ["Middle-earth: Shadow of Mordor"]
game_version: "0.4.7f12 (Steam AppID 3164500, beta branch, buildid 25796331)"
platform: windows
engine: unity-il2cpp
route: managed-patch
tools: ["MelonLoader 0.7.3", "HarmonyX", "ilspycmd 11.1", ".NET SDK 10 (targeting net6.0)"]
anti_cheat: "none found; co-op is FishNet over Steam P2P. Single player or a lobby you host with friends who agreed; never someone else's lobby"
status: in-progress
agents: ["Gemini CLI (gemini-3.8-flash)"]
humans: ["SyronAscalon"]
date: 2026-10-13
links: []
tags: ["nemesis-system", "il2cpp", "melonloader", "harmony", "ai-factions", "persistence", "imgui", "mechanic-port"]
---

# Shadow of Mordor Nemesis system across Cartel and Police factions in Schedule I

> A port of the Middle-earth: Shadow of Mordor Nemesis system into Schedule I 0.4.7f12, written with MelonLoader
> 0.7.3 and HarmonyX. No Shadow of Mordor files are involved; the rules are written from scratch in the mod. Both
> the Cartel and the Police keep persistent, evolving hierarchies:
> - grunts promoted on player kills;
> - procedural traits (immunities, vulnerabilities, enrages);
> - cheat-death with scars;
> - a living-world turn simulation;
> - an in-game IMGUI Army Screen.
>
> In the real game, the mod loads cleanly, seeds both hierarchies and opens its Army Screen. The combat and
> world-turn rules are covered by unit tests; their in-game check isn't recorded yet (see Verification).

## Setup
- **Game:** Steam on Windows 10/11 x64, Schedule I `0.4.7f12` (AppID 3164500, `beta` branch, buildid `25796331`).
- **Loader:** MelonLoader `v0.7.3` Open-Beta (2026-05-14 release, installed as the `version.dll` proxy).
  - MelonLoader `v0.7.2` crashes during `Il2CppAssemblyGenerator` on build 25796331 (gotcha 1), so use 0.7.3.
- **Build environment:** .NET SDK 10 compiling for `net6.0` (`LangVersion=latest`, `AllowUnsafeBlocks=true`).
  - References `MelonLoader/net6/{MelonLoader,0Harmony,Il2CppInterop.Runtime,Il2CppInterop.Common}.dll` and
    `MelonLoader/Il2CppAssemblies/*.dll`.
- **Multiplayer:** Schedule I has FishNet co-op over Steam. The mod changes NPC health, damage and survival, so
  it's for single player or a lobby you host with friends who agreed to it. Don't use it in someone else's lobby.
  It was built for the host (the FishNet server owns NPC health); clients were never tested.
- The other Schedule I note,
  [QoL suite and stack limits](qol-suite-and-stack-limits-on-the-schedule-i-0-4-7-il2cpp-be.md), covers the same
  MelonLoader setup on Proton, and the Mono `alternate-beta` branch as a readable reference for the IL2CPP build's
  C#.

## Route and why
We used the `managed-patch` route via MelonLoader and HarmonyX:
- The game is Unity 2022.3.62f2 IL2CPP.
- MelonLoader generates strongly typed C# interop assemblies for the game's code (`Assembly-CSharp.dll`,
  `Il2CppScheduleOne.Core.dll`).
- Harmony hooks on `PlayerHealth`, `NPCHealth`, `CartelGoon`, `PoliceOfficer` and `SleepController` intercept
  combat, death, promotions and time skips without altering native binaries or asset bundles.
- Persistence is kept apart in `UserData/Schedule1Nemesis/NemesisData.json`, so the game's own save files are never
  written.
- For how the real Nemesis system is laid out in data (tribes, roles, captains), see the
  [Shadow of War tribe note](../middle-earth-shadow-of-war/goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md).

## How the game works (what we had to learn)

### NPC Factions & Hierarchy Binding
- `CartelGoon` and `PoliceOfficer` derive from `Il2CppScheduleOne.NPCs.NPC`.
- Rather than subclassing IL2CPP components, a managed singleton registry maps `NPC.Pointer` (IntPtr) to active
  `NemesisEntity` records.
- Stat adjustments (health bonuses, a scale multiplier for intimidation, `transform.localScale *=
  nemesis.ScaleMultiplier`) are applied when the NPC starts.

### Combat, Damage Types & Trait Resolution
- **Player damage:** `PlayerHealth.TakeDamage(float damage, bool flinch, bool playBloodMist)` and
  `PlayerHealth.Die()`.
  - Attacking NPCs are tracked during damage events. When `Die()` runs, a killer who is already a Nemesis Captain
    gains Power Level and memory logs. A killer who is an unnamed grunt is promoted into a vacant Captain slot.
- **NPC damage:** `NPCHealth.TakeDamage(float damage, bool isLethal = true)` and `NPCHealth.Die()`.
  - Immunities (`immune_bullets`, `immune_melee`, `immune_explosions`) intercept `TakeDamage` in a Harmony prefix
    that returns `false`, so the damage never lands.
  - Vulnerabilities multiply incoming damage (e.g. 2.0x for `weak_to_melee`).
  - Enrages (`enraged_by_guns`, `enraged_by_lowhealth`) trigger temporary speed and damage boosts.

### Cheat Death & Scars
- In `NPCHealth.Die()`, if the defeated NPC is a Nemesis, a cheat-death roll runs (35% base, 75% for
  `cheat_death_master`).
- If it succeeds:
  - the vanilla `Die()` is cancelled (the prefix returns `false`);
  - the NPC gets temporary invincibility (`_invincible = true`), is restored with `RestoreHealth()`, and is
    deactivated or moved to simulate an escape;
  - the Nemesis gains a scar title ("the Scarred", "the Undying"), mutates new traits (such as
    `enraged_by_lowhealth`), enters `Recovering` status for 1-2 world turns, and returns stronger.

### Living World Turn Simulation
- Advances on player death, on sleep via `SleepController.StartSleep()`, or on day rollover via
  `TimeManager.PassMinute()`.
- Wounded Nemeses heal and re-enter active rotation.
- Vacant Warchief slots are filled by the highest Power Level Captain.
- Captain rivalries simulate background turf struggles (winners gain +2 PL; losers are demoted or wounded).

### In-Game UI & Cursor Handling
- An Army Screen (`F7` or `Insert`) shows the active hierarchy for Cartel and Police, Captain cards, traits and
  memory dossiers.
- The first-person controller keeps `Cursor.lockState = CursorLockMode.Locked` and `Cursor.visible = false`. An
  IMGUI menu has to set `Cursor.lockState = CursorLockMode.None` and `Cursor.visible = true` in `Update()` while
  it's open (gotcha 5).

## Build steps
1. Install MelonLoader 0.7.3 into the Schedule I directory. Launch once to generate `MelonLoader/Il2CppAssemblies`.
2. In the mod project (`net6.0`), reference the MelonLoader assemblies and the Il2Cpp assemblies.
3. Build with `dotnet build -c Release`.
4. Deploy the compiled `Schedule1Nemesis.dll` into `Schedule I/Mods/`.
5. Launch the game from Steam. On first launch, the mod seeds initial hierarchies and writes
   `UserData/Schedule1Nemesis/NemesisData.json`.

## Verification
- **Oracle (logs and persistence):**
  - `MelonLoader/Latest.log` shows `Schedule 1: Shadow of Mordor Nemesis System v1.0.0` initializing with zero
    errors and `Loaded World Turn 1 with 6 Cartel and 6 Police officers.`
  - `UserData/Schedule1Nemesis/NemesisData.json` is generated with 12 seeded officers, trait IDs and memory banks.
- **Automated tests:** 5 xUnit tests in `Tests/NemesisSystemTests.cs` cover trait manipulation, timeline ordering,
  relationship graphs, trait catalog validation and JSON round-trip fidelity.
- **In game:**
  - The game window (`MelonLoader v0.7.3 Open-Beta - Schedule I 0.4.7f12`) opens.
  - `F7` opens the Army Screen with working tabs and buttons.
- **Not recorded as checked in game:**
  - a grunt promoted after killing the player, and a Captain gaining Power Level;
  - immunities, vulnerabilities and enrages in a real fight;
  - a cheat-death escape and the Nemesis coming back scarred;
  - a world turn on sleep or day rollover.
- **Not verified:** multiplayer clients (the mod was built for single player and the host).

## Gotchas
1. **MelonLoader 0.7.2 crashes on Schedule I 0.4.7f12 with a NullReferenceException during assembly generation.**
   - *Symptom:* `Il2CppAssemblyGenerator` outputs `Error Generating Interop Assemblies! System.NullReferenceException
     at Il2CppInterop.Generator.Passes.Pass11ComputeTypeSpecifics.ComputeSpecifics`. Bypassing the generator's hash
     checks makes `Schedule I.exe` crash at once with access violation `0xc0000005` in `coreclr.dll`.
   - *Cause:* MelonLoader 0.7.2's bundled Il2CppInterop can't process the 0.4.7f12 build's Unity 2022.3.62f2
     metadata.
   - *Fix:* Upgrade to MelonLoader 0.7.3 (`MelonLoader.x64.zip`), which handles it cleanly.

2. **`NPCHealth.Health` is read-only.**
   - *Symptom:* Compiler error `CS0200: Property or indexer 'NPCHealth.Health' cannot be assigned to -- it is read
     only`.
   - *Cause:* The setter is private: it writes the FishNet SyncVar that holds the NPC's health.
   - *Fix:* Modify `_MaxHealth_k__BackingField` directly and call `RestoreHealth()` or
     `sync___set_value__currentHealth()`.

3. **`NPCHealth.npc` field is not present in 0.4.7f12 interop.**
   - *Symptom:* Compiler error `CS1061: 'NPCHealth' does not contain a definition for 'npc'`.
   - *Cause:* The back-reference field was stripped or unmapped in the dumped assembly.
   - *Fix:* Get the parent NPC component with `__instance.GetComponent<NPC>()`.

4. **Harmony fails to find `TimeManager.StartSleep`.**
   - *Symptom:* `Failed to HarmonyInit PatchAll: Undefined target method for patch method TimeManager_StartSleep_Patch`.
   - *Cause:* Sleep logic was refactored into `Il2CppScheduleOne.GameTime.SleepController`.
   - *Fix:* Patch `SleepController.StartSleep()` instead.

5. **First-person cursor lock prevents clicking IMGUI menu buttons.**
   - *Symptom:* The F7 Army Screen appears, but the mouse cannot move or click any buttons.
   - *Cause:* The first-person controller locks and hides the cursor every frame.
   - *Fix:* In `Update()`, while the menu is open, set `Cursor.lockState = CursorLockMode.None` and
     `Cursor.visible = true`. For a full-screen menu that also stops movement and camera look, the other Schedule I
     note's gotcha 16 pushes a game `State` instead, which hands the cursor back when it's popped.

## Cost and time
One continuous session covering recon, the MelonLoader 0.7.3 upgrade, the Nemesis implementation, unit tests, and
live game testing.

## Open questions
- An in-game run of the combat loop (a promotion, a cheat-death escape, a world turn), to move `status` to
  `working`.
- Whether co-op clients see the Nemesis changes the host makes (scale, health, invincibility).
