---
kind: game
title: 'Smalland-style trap taming in Valheim: four trap tiers, tame-anything switch and a rideable Seeker Soldier'
game: Valheim
games_also:
- 'Smalland: Survive the Wilds'
game_version: steam 892970, built on buildid 25527674; re-verified on 25909357 (Valheim 1.0.20), Unity 6000.0.75f1 (Mono)
platform: windows
engine: unity-mono
route: managed-patch
tools:
- BepInExPack_Valheim 5.4.2351
- Jotunn 2.30.2
- HarmonyX
- ilspycmd 9.1.0.7988
- .NET 8 SDK (net472 target)
anti_cheat: none found by um scan; local test world and test character only
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans:
- Culp
date: '2026-10-05'
links:
- ../smalland-survive-the-wilds/reading-the-taming-system-live-with-ue4ss-trap-tiers-creatur.md
tags:
- mashup
- mechanic-port
- taming
- mount
- saddle
- jotunn
- custom-piece
- harmony
---
# Smalland-style trap taming in Valheim: four trap tiers, tame-anything switch and a rideable Seeker Soldier

> A mashup pattern 1 (port the mechanic): Smalland's trap taming, with its rules read live from Smalland
> (see the linked Smalland note), rebuilt in Valheim as a BepInEx + Jotunn plugin. Four buildable trap tiers
> lure a creature, hold it for 5 s and roll Smalland's formula. Five species Valheim can't tame become
> tameable, tames follow their tamer and stay on command, and the Seeker Soldier is rideable with a Lox saddle.
> All of it was verified by the human in a local test world. Art is still placeholder.

## Setup
- Valheim Steam buildid 25527674 (same build as `mjolnir-frostner-rework.md`), Windows 11.
- BepInExPack_Valheim 5.4.2351 + Jotunn 2.30.2 (Thunderstore). Only the Windows files of the pack
  (`winhttp.dll`, `doorstop_config.ini`, `.doorstop_version`, `BepInEx/`).
- Plugin: C# `net472`, .NET 8 SDK + `Microsoft.NETFramework.ReferenceAssemblies`. References
  `assembly_valheim.dll`, `assembly_utils.dll`, `UnityEngine` + `CoreModule`, `InputLegacyModule`,
  `PhysicsModule`, **`AssetBundleModule`** (Jotunn's `CustomPiece` needs it), BepInEx, 0Harmony, Jotunn.
- Saves are in Steam Cloud on this machine (`Steam/userdata/<id>/892970/remote`), not `LocalLow`: back up
  that folder. All testing in a new local world + character.
- Decompile with `ilspycmd -t <Type>`. The latest ilspycmd fails to install on the .NET 8 SDK
  (`DotnetToolSettings.xml not found`); `--version 9.1.0.7988` works.

## Route and why
Managed patch through Valheim's own taming code: success calls the private `Tameable.Tame()` (via
`AccessTools`), so saving, follow/stay and saddles keep working. Considered: a passthrough with Smalland
running (pointless for a rules port), or a full reimplementation of taming (would break vanilla tames).
In `knowledge/techniques/choosing-a-mashup-route.md` terms this is a rebuilt mechanic in a real host: only
Smalland's rules cross, read once from the live game (linked note), and Smalland doesn't run alongside.

## How the game works (what we had to learn)
- `Tameable` (vanilla on Boar, Hen, Wolf, Lox, Asksvin): taming time 1800 s, ticks every 3 s while the creature
  is fed (within 30 s), not alerted and not tamed; a nearby player with the TamingBoost status doubles it.
  Progress and feeding time live in the ZDO (`s_tameTimeLeft`, `s_tameLastFeeding`), so they persist.
- Commands: interacting with a tame pets it; if `m_commandable`, it toggles follow (`MonsterAI.SetFollowTarget`)
  / stay (`SetPatrolPoint`). Boars and hens are **not** commandable in vanilla.
- **A tame with no follow target and no patrol point wanders around its *current* position**
  (`BaseAI` uses the transform position, not the spawn point, when tamed), so it drifts away indefinitely.
- `BaseAI.Follow` stops moving at 3 m from the target (centre to centre).
- Saddles: `Tameable.m_saddleItem` + `m_saddle` (a `Sadle` on a child object). `Tameable.Awake` registers the
  saddle RPCs only if `m_saddle` is already set. `Sadle.Awake` finds the creature with `GetComponentInParent`.
  The Lox saddle is one object `Sadel` (SkinnedMeshRenderer + SphereCollider + Sadle, anim `attach_lox`).
  E on the body = follow/stay, E on the saddle collider = ride.

## Build steps
1. Port the rules: difficulty per prefab on Smalland's scale (Boar 3, Hen 3, Neck 5, Greyling 5, Tick 5, Wolf 8,
   Lox 16, Asksvin 16, Seeker 16, SeekerBrute 28), roll `skill * Random(1, 10) >= difficulty`.
2. `PrefabManager.OnPrefabsRegistered`: add `Tameable` (+ the Boar's effects) to listed prefabs with a
   `MonsterAI` that lack one, and set `m_commandable = true` on all listed tames.
3. `PrefabManager.OnVanillaPrefabsAvailable`: four `CustomPiece`s cloned from `piece_chest_wood` (remove the
   `Container`) on the Hammer table with a `TamingTrap` behaviour: lure the nearest listed, untamed creature
   within 20 m with `SetFollowTarget(trap)`, catch within 4.5 m minus the creature radius, 5 s countdown, roll,
   then destroy the trap (single use). Tier costs: Wood+Resin, Wood+Bronze+TrollHide, ElderBark+Iron+Chain,
   FineWood+Silver+WolfPelt.
4. After a successful tame, call `Tameable.Command(tamer)` so it follows (Smalland behaviour).
5. Mount: set `m_saddleItem = SaddleLox` on the SeekerBrute prefab, and in a **Harmony prefix on
   `Tameable.Awake`** build the saddle on each spawned SeekerBrute: copy the Lox `Sadel` (inactive), remove its
   renderer, add a placeholder mesh with a Valheim material, new attach point, parent to the `spine` bone
   + 0.35 m.
6. Test-world keys (config): F8 roll on the crosshair creature, F9 spawn next listed creature (god + ghost),
   Shift+F9 spawn SeekerBrute, F10 cycle test trap tier, F11 free building + Hammer + Lox saddle,
   F12 remove wild creatures within 60 m.

## Verification
- Every roll is logged (`skill x r = roll vs difficulty -> TAMED / escaped`). All 10 species were tamed in the
  real game; escape/tame streaks matched the odds (e.g. Seeker 3 escapes at 67 %, SeekerBrute first try at 33 %).
- The human confirmed: tames show "(Tame)", follow and stay on E, hostile tames (Greyling, Seeker, Seeker
  Soldier) get along, the trap countdown shows and the trap disappears, and riding the Seeker Soldier works
  (screenshots: mounted HUD with the Seeker Soldier's 1500 HP / 240 stamina).
- **2026-10-17, after the Valheim 1.0.20 update (build 25909357), SmallTaming 0.5.3:**
  - In-game regression tests run through a small HTTP test bridge in the test world all pass, 4 of 4: two
    traps luring one creature, the Neck catch at 4.5 m, the SeekerBrute saddle, and the roll rate.
  - The roll was measured in Valheim (a console command rolling n times per skill and difficulty pair) and
    compared with Smalland's own measured odds (linked note). All 24 cells agree within 0.1; the largest
    difference is 0.041.
- Not verified: multiplayer/dedicated server, long play sessions, the Smalland stances / party cap / gathering
  (not built).

## Gotchas
1. **Fresh tames wander off out of sight.** **Cause:** tamed with no follow target or patrol point, BaseAI
   wanders around wherever it is. **Fix:** make the new tame follow the tamer; "stay" sets a patrol point.
2. **Neck lured but never caught.** **Cause:** `BaseAI.Follow` stops at 3 m, the trap demanded <= 3 m.
   **Fix:** catch at 4.5 m minus `Character.GetRadius()`.
3. **Several traps lured one creature, which bounced between them.** **Fix:** skip creatures whose follow
   target is another trap.
4. **`Cannot instantiate objects with a parent which is persistent`.** **Cause:** adding a child to a prefab
   asset (the saddle). **Fix:** build it per instance in a `Tameable.Awake` prefix; put only fields on the prefab.
5. **Saddle on, E only gives follow/stay.** **Cause:** the saddle collider sat inside the body collider at
   capsule height. **Fix:** put the saddle on the back bone with a 0.75 m sphere.
6. **Rider floated above the head; saddle magenta.** **Cause:** the SeekerBrute capsule is much taller than its
   crab body; `CreatePrimitive` uses the default Unity shader. **Fix:** parent to the `spine` bone; use a
   Valheim material (`piece_chest_wood`'s).
7. **Wild spawns killed the test mount.** Monsters attack tames. **Fix:** F12 clear + Shift+F9 direct spawn.
8. **F5 console didn't open.** It needs the `-console` Steam launch option; we built test keys into the mod.
9. **Code edits need a full game restart** (no BepInEx hot reload); Smalland's UE4SS has Ctrl+R.

## Assets
None yet. Trap and saddle are placeholders (scaled wood chest, wood-material block).

## Cost and time
One evening (~3 h with the Smalland research), no API spend.

## Open questions
- Smalland stances, party-weight follower cap, pet gathering, relation levels, stables.
- A proper trap model and saddle mesh; a custom saddle item instead of the Lox saddle.
- Behaviour with several players / dedicated server (the plugin declares EveryoneMustHaveMod).
