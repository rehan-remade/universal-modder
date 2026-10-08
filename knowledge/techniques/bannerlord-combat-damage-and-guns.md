---
kind: technique
title: "Combat in Bannerlord mods: damage models, scripted blows, AI combat properties and guns on the crossbow class"
status: in-progress
game: "Mount & Blade II: Bannerlord"
games_also: ["Borderlands 2"]
game_version: "v1.4.8.119303 (Steam, Windows 11); client TaleWorlds.Native.dll 14,185,944 bytes, PE timestamp 0x6a732505; Bannerlord.Harmony 2.4.2"
platform: windows
engine: unknown
route: loader-api
tools: ["Bannerlord module system (ModuleData XML + XSLT, C# net472 SubModule)", "Bannerlord.Harmony 2.4.2", "ilspycmd 9.1", "Ghidra 12.1.4 headless on a copy of TaleWorlds.Native.dll"]
agents: ["Claude Code (Opus 5.5)", "Claude Code subagents (Sonnet 5.5)"]
humans: ["@theartur2000"]
date: 2026-10-07
links: []
tags: [bannerlord, combat, damage-model, blow, registerblow, morale, ai, guns, crossbow-class, missiles, friendly-fire, auto-resolve]
---

# Combat in Bannerlord mods: damage models, scripted blows, AI combat properties and guns on the crossbow class

> How damage flows in Bannerlord, how to deal your own damage safely, which AI properties decide blocking and aim, and how to
> build working guns when the game's Pistol and Musket classes are dead: everything on the crossbow class. From a Borderlands 2
> total conversion ([`../games/mount-and-blade-ii-bannerlord/bannerlord-borderlands-2-total-conversion.md`](../games/mount-and-blade-ii-bannerlord/bannerlord-borderlands-2-total-conversion.md)).

Evidence tags: **[V]** seen in the running game or by a byte-exact round trip, **[M]** measured, **[S]** static analysis only,
**[H]** hypothesis. "TN n" = gotcha n of [`editor-free-bannerlord-assets.md`](editor-free-bannerlord-assets.md).

## When to use it
- You change how much damage anything does, deal damage from script, or need deaths, knockouts and morale to behave.
- Your AI troops never block, never fire or deal zero damage.
- You want firearms in Bannerlord (the Pistol and Musket classes do not work), explosions, pellets or range caps.

## How
**Agents, combat and damage**
- **Models are the extension point.** Game models (`AgentApplyDamageModel`, `AgentStatCalculateModel`, `BattleMoraleModel`,
  `PartySizeLimitModel`, `BattleRewardModel`, `SettlementEconomyModel`, `AgentDecideKilledOrUnconsciousModel`,
  `StrikeMagnitudeCalculationModel`...) are looked up so the LAST registered one wins. Wrapper pattern: in `OnGameStart` find the
  registered model with `gameStarter.Models.OfType<X>().LastOrDefault()`, `gameStarter.AddModel(new Wrapper(inner))`, where
  `Wrapper : X` forwards every abstract member (33 for the damage model) and overrides the one you change. Never subclass a SandBox
  type from the always-loaded assembly or the module fails to load in custom battles. Mission models: `MissionGameModels.Current`.
  A wrapper around `AgentStatCalculateModel` misses calls the inner model makes to its own virtuals, so rescale after.
- **Damage pipeline.** `AgentApplyDamageModel` is the one damage step for melee, missiles, area, charge and falls;
  `ApplyGeneralDamageModifiers` is the last step before `InflictedDamage`; `ApplyDamageAmplifications` multiplies after armour.
  `Agent.HandleBlow` kills only when health is below 1 and drops a 0-damage hit (no flinch, blood or hit event; the swing bounces):
  let 1 through. Not covered: drowning, burning (`RegisterBurnBlow` calls Die), `Mission.KillAgentsOnEntity`. Armour: damage x
  50/(50+armour), then a type-dependent subtraction.
- **Own damage.** Build a `Blow` (`DamageCalculated=true`, `InflictedDamage`, `DamageType`, `BoneIndex`, `VictimBodyPart`,
  `WeaponRecord.FillAsMeleeBlow(null,null,-1,0)`, `BlowFlags`) plus an `AttackCollisionData` from `GetAttackCollisionDataForDebugPurpose`
  and call `victim.RegisterBlow(blow, in cd)`. The engine never filters this path (no friendly-fire cancel, no armour). Registering
  blows or spawning from inside an engine callback (missile hit, removal) is unsafe: queue to the next tick or `OnPreMissionTick`. Kill
  credit comes from the `_lastHitInfo` a blow in another agent's name sets.
- **Kill or knock out** is decided late: `Agent.HandleBlow` -> `Mission.OnAgentHit` -> `Agent.Die` -> native -> `Mission.GetAgentState` ->
  `AgentDecideKilledOrUnconsciousModel`. In a campaign mission a hero or boss death may come out Unconscious, so check Killed OR Unconscious.
  A missile's damage type and flags come from the AMMO item and `AttackCollisionData.DamageType` is get-only.
- **Morale.** Each nearby death moves a human AI agent's morale (0 to 100) through `BattleMoraleModel.CalculateMoraleChangeToCharacter`; at 0 it
  asks `CanPanicDueToMorale`, so a wrapper lets robots never rout.
- **AI skill properties** are written at the end of the stat model's `UpdateAgentStats` (at spawn and on every equipment/wield change).
  Block and parry: `AIBlockOnDecideAbility`, `AIParryOnDecideAbility`, `AIParryOnAttackAbility`, `AIParryOnAttackingContinueAbility`,
  `AiParryDecisionChangeValue`, `AiDefendWithShieldDecisionChanceValue`, `AiUseShieldAgainstEnemyMissileProbability`,
  `AiAttackingShieldDefenseChance`; aim: `AiRangerLeadErrorMin/Max`, `VerticalErrorMultiplier`, `HorizontalErrorMultiplier`,
  `WeaponInaccuracy`. Zero the first eight and the AI never blocks. Re-apply anything you pin on a short timer.
- **Spawning an agent mid-battle.** `new AgentBuildData(troop).Team(team).Formation(team.GetFormation(FormationClass.Infantry))
  .TroopOrigin(new BasicBattleAgentOrigin(troop)).InitialPosition(in pos).InitialDirection(in dir).Controller(AgentControllerType.AI)
  .IsReinforcement(true)`, then `Mission.SpawnAgent(data)`, then `agent.WieldInitialWeapons()` and
  `agent.SetWatchState(Agent.WatchState.Alarmed)` (what `Mission.SpawnTroop` does); without the last two the AI never wields or picks a
  target. A custom battle loads troops as `BasicCharacterObject`, the campaign as `CharacterObject`. Spawn after deployment, never from a callback.
- **Pinning an agent** (stationary bosses): `Controller = None`, `MaxSpeedMultiplier = 0` + `UpdateCustomDrivenProperties`, re-applied on a timer.
- **Friendly fire.** In single-player field battles `Mission.MissileHitCallback` cancels a non-physics missile meeting a friend (AI always;
  the player because both `FriendlyFireDamageRanged*Percent` options are 0), and melee against a friend is cancelled. A bouncing physics
  missile does hurt friends; splash through your own `RegisterBlow` is never filtered.
- **Items.** A hand-written `<Item>` melee weapon gets inertia = weight x 0.05, centre of mass = length/2 and damage factor 0.4; Native
  weapons are `CraftedItem`s with piece physics, so the same sword hits for about 7 instead of about 47: keep Native ids and re-skin.
  Weapon reskin takes THREE hooks: `MissionWeapon.OnGetWeaponDataHandler` (Native's `ViewSubModule` RESETS it at every game start: install in
  `OnGameStart` after Native's and again at `OnMissionBehaviorInitialize`), `CraftedDataView.OnWeaponMeshBuilt` and `ItemObject.MultiMeshName`
  set by reflection. Item value: shield tier = (hit_points^1.22 + 3 x body armour + thrust speed) / (6 + weight^1.11) x 0.04 minus 2; value =
  100 x 2.75^tier x (1 + 0.2 x (appearance minus 1)); loot rolls 7.25 x level^2 per casualty, so a looter can drop any item it carries.

**Guns on the crossbow class**
- **`Pistol` and `Musket` classes are dead in 1.4.8** (no skill, ammo type, item usage or animations). EVERY gun is `Type="Crossbow"`,
  `ammo_class="Bolt"`, with crossbow item usages (heavy `crossbow` with `CantReloadOnHorseback`, or `crossbow_light`), the Crossbow skill
  relabelled "Guns". The Old Realms and Shokuho do the same with own item usages.
- **Missile physics.** Damage = gun `thrust_damage` + ammo damage, scaled by (impact speed / launch speed)^2 (`SandboxStrikeMagnitudeModel`),
  so faster bullets are NOT harder. Vanilla bolts at 55 to 97 m/s drop about 3 m at 50 m; `missile_speed` 180 to 420 gives about 4 cm. The AI
  aims with the gun's own speed, but `Agent.GetMissileRange` grows with speed and `Mission.SetMissileRangeModifier` is ONE number for the
  whole mission (the weather model may overwrite it).
- **Ammo and reload.** `ammo_limit` becomes the magazine size; a crossbow is preloaded with min(ammo_limit, stack) at spawn;
  `reload_phase_count` is read (max 10; native crossbows use 2). Aim spread = (100 minus accuracy) x (1 minus 0.002 x skill) x 0.001.
- **Muzzle and eye.** The item XML `AmmoOffset` (weapon-local vec3 on the main-hand item bone) sets the muzzle; the missile start point
  measured as the EYE position. AI fires when a ray from the eye to the target is clear; an eye inside the model's own mesh blocks it.
- **Pellets.** Extra missiles come from `Mission.AddCustomMissile` (no gun damage bonus: scale strike magnitude in a wrapper). Every shot
  reaches `MissionBehavior.OnAgentShootMissile` with the `Missile` already in `Mission.MissilesList`; `Mission.OnMissileRemovedEvent` works
  while `OnMissileRemoved` is never called. The list mutates during hit hooks: snapshot it.
- **AI range control.** No managed hook can veto a native release. What works: per-agent `Agent.SetFiringOrder(HoldYourFire)` on a 4 Hz
  sweep for gunners whose `GetTargetAgent()` is beyond range; blocking releases beyond 1.1x range in `OnAgentShootMissile`.
  `Formation.SetFiringOrder` copies onto units only when the order changes or a unit joins.
- **Auto-resolve ignores guns.** `MapEvent.SimulateBattleRound` -> `DefaultCombatSimulationModel.SimulateHit` ->
  `MilitaryPowerModel.GetTroopPower` -> `GetDefaultTroopPower` = (2 + tier) x (10 + tier) x 0.02 (hero x1.5), tier = clamp(ceil((level
  minus 5)/5), 0, 6). Party strength, army power and garrison use the same function; wrapping it changes them all at once.

## Gotchas
1. **Symptom.** A fully soaked hit leaves the target immortal in melee and the swing bounces. **Cause:** `Agent.HandleBlow` drops 0-damage hits.
   **Fix:** let 1 damage through at the end of the damage model. [V]
2. **Symptom.** AI troops spawned after deployment (reinforcements, scripted swarms) deal zero damage. **Cause:** `Mission.SpawnAgent` alone does not do
   what `Mission.SpawnTroop` does: no `WieldInitialWeapons`, no `Alarmed` watch state. **Fix:** call both after spawning; make test spawns mimic the game. [V]
3. **Symptom.** `Agent.Die` from script throws or the death never registers. **Cause:** `CalculateMaxMoraleChangeDueToAgentIncapacitated` throws when a
   death has no affector, and native models read the killer's formation. **Fix:** always give a killer; have the morale wrapper catch and return (0,0). [V]
4. **Symptom.** `thrust_damage_type="Blunt"` or `CanKillEvenIfBlunt` on a gun does nothing for knock-outs. **Cause:** a missile's damage type comes from the
   AMMO item and `AttackCollisionData.DamageType` is get-only. **Fix:** mark the victim in `OnAgentHit` and answer Blunt from a wrapper
   `AgentDecideKilledOrUnconsciousModel`; in custom battle the default model always kills. [S]
5. **Symptom.** Guns have too much bullet drop; after raising speed they snipe across the whole map. **Cause:** vanilla bolt speed 55 to 97 m/s; raising it
   inflates `Agent.GetMissileRange` (AI engagement range) while the range modifier is global; damage does not inflate (magnitude is relative to the weapon's
   own launch speed). **Fix:** bullet speed 180 to 420 m/s by class, hold-fire sweeps and release blocks beyond a per-class range cap, reduced AI aim error. [engine check V, behaviour partly unverified]
6. **Symptom.** Mass battles with scatter guns flood the engine with live missiles. **Cause:** every pellet is an engine missile. **Fix:** for AI shooters one
   real missile plus "group" missiles standing for several pellets; above 700 live missiles groups of 6 and merged bursts, above 1,300 every volley collapses to one. [V]
7. **Symptom.** Splash does not hurt allies; bullets disappear on a friend. **Cause:** a non-physics missile meeting a friend is cancelled and melee against a
   friend is cancelled; your own `RegisterBlow` is never filtered. **Fix:** explosions through your own blows (friendly fire by design); a direct rocket hit on a
   friend is cancelled but the rocket still bursts. [V]
8. **Symptom.** Robots and creatures still block and parry. **Cause:** block and parry are AI properties set by the stat model, not by the roster. **Fix:** zero
   the eight AI properties for the agents concerned at the end of `UpdateAgentStats` (the engine reruns it on equipment change). [unverified until tallied]
9. **Symptom.** A pinned boss or a property you set drifts back. **Cause:** the stat model rewrites driven properties on every weapon or formation change and
    controller changes reset speed limits. **Fix:** re-apply on a 0.25 s timer, comparing to the last value you wrote (an unexpected value is the new base). [V]
10. **Symptom.** Damage hooks run on hits that never hurt; damage applied twice, native callback state corrupted. **Cause:** wooden-shield-blocked and
    weapon-blocked missiles also run the calculation; blows registered or behaviours removed inside engine callbacks. **Fix:** skip blocked hits; queue work for
    the next tick, a few blows per tick, re-validated. [V]
11. **Symptom.** Auto-resolve says "gun troops 3x too strong" or a huge beast pack looks harmless. **Cause:** auto-resolve, party strength and fight-or-flee read
    the TROOP TIER only. **Fix:** do not add scale constants; wrap `MilitaryPowerModel.GetDefaultTroopPower`. [V by reading]

## Seen in
- [Borderlands 2 as a Bannerlord total conversion](../games/mount-and-blade-ii-bannerlord/bannerlord-borderlands-2-total-conversion.md), where every item here was learned.
- [Editor-free assets for Bannerlord](editor-free-bannerlord-assets.md) for the binary formats behind the races and clips.
