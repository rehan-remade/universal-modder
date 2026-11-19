---
kind: technique
title: 'NeoForge 1.21.1 GameTests for mob AI: real survival players, structure y-offset, tick-0 hurt trap'
status: working
agents:
- Devin (model not recorded)
humans: []
date: '2026-10-07'
links: []
tags:
- minecraft
- neoforge
- gametest
- entity-ai
---

# NeoForge 1.21.1 GameTests for mob AI: real survival players, structure y-offset, tick-0 hurt trap

> Testing custom-mob AI (warn/aggro/flee/feed goals) with Minecraft GameTests is
> mostly fighting the *harness*, not the mob. Four non-obvious environment quirks
> make every entity-AI test silently fail if you don't know them.

## When to use it

Any NeoForge/Forge GameTest that needs a mob to perceive or attack a player —
`runGameTestServer` on MC 1.21.1 / NeoForge 21.1.x (verified on 21.1.256,
ModDevGradle 2.x). Most of it applies to any 1.20.5+ GameTest setup.

## How

Run `gradlew runGameTestServer` with `@GameTestHolder(MODID)` + `@GameTest(template = "flat")`.
Tests share ONE world in a concurrent batch — neighbouring test structures sit only
~5–10 blocks apart, so anything with an 8+ block scan radius can see the next test's
entities/players.

## Gotchas

1. **Symptom.** Entity scans (`getNearestEntity`, goals) never see the test player;
   or they see it but the mob refuses to stay targeted.
   **Cause (two traps in one).** `helper.makeMockPlayer(...)` returns a bare `Player`
   that is never added to the level. `makeMockServerPlayerInLevel()` *is* added, but
   its anonymous `ServerPlayer` **hardcodes `isCreative() -> true`** — creative
   players are rejected by `EntitySelector.NO_CREATIVE_OR_SPECTATOR` and by
   `MeleeAttackGoal`: its `canContinueToUse` returns false for a creative or
   spectator player, and `stop()` then calls `setTarget(null)`.
   **Fix.** Build a real `ServerPlayer` yourself:
   `new ServerPlayer(server, level, cookie.gameProfile(), cookie.clientInformation())`,
   `new Connection(PacketFlow.SERVERBOUND)` wrapped in an `EmbeddedChannel`, then
   `playerList.placeNewPlayer(connection, player, cookie)`,
   `setGameMode(GameType.SURVIVAL)` and belt-and-braces `getAbilities().instabuild = false`
   etc.

2. **Symptom.** Spawned mobs suffocate, have no line of sight to anything, and
   `hasLineOfSight`/raycasts return `BLOCK` into stone.
   **Cause.** GameTest loads the structure one block above the reported
   `structureBlockPos` (the structure-block convention). A "flat" 5×5 floor NBT
   (25 blocks at local y=0) ends up with its *top surface* at local y=2, not 1.
   Entities spawned at local y=1 are pushed down into the gap under the floating
   floor or wedged inside it — eyes inside stone, zero LOS.
   **Fix.** Spawn entities and items at local **y=2** on a 1-block floor template.

3. **Symptom.** `mob.hurt(...)` called in the test body registers
   `getLastHurtByMob()` but `HurtByTargetGoal` never retaliates.
   **Cause.** The test body runs when the fresh entity's `tickCount` is still 0, so
   `lastHurtByMobTimestamp = 0`; `HurtByTargetGoal.canUse` tests
   `timestamp != this.timestamp` and `this.timestamp` also starts at 0 → the wound
   reads as already-consumed.
   **Fix.** Hurt inside `helper.runAtTickTime(5, () -> mob.hurt(...))`.

4. **Symptom.** A flee goal clears the target (`setTarget(null)` in `start()`) but
   the target comes straight back.
   **Cause.** `TargetGoal.canContinueToUse` re-arms every evaluation:
   `mob.setTarget(targetMob)` whenever the mob has no target. Clearing the target
   once never sticks.
   **Fix.** Gate the target goal itself on the flee condition
   (`canUse`/`canContinueToUse` → `false`) so it `stop()`s and drops `targetMob`,
   and keep a per-tick `setTarget(null)` in the flee goal to cover `alertOther`
   (pack alerts set neighbours' targets directly, bypassing their goals).
   Bonus trap: an ungated `PanicGoal` holds the MOVE flag for ~100 ticks and can
   starve a directed flee goal — gate panic to babies/low-priority mobs.

5. **Symptom.** `@GameTest` crashes at startup with a doubled namespace like
   `modid:tests.modid:flat`.
   **Cause.** `template` is already inside the test namespace, and NeoForge 1.21.1
   prefixes it with the lower-cased class name by default
   (`GameTestHooks.prefixGameTestTemplate`). So `template = "modid:flat"` in class
   `Tests` becomes `modid:tests.modid:flat`.
   **Fix.** Write `template = "flat"`, not `"modid:flat"`; in class `Tests` that
   loads `modid:tests.flat`. Add `@PrefixGameTestTemplate(false)` to drop the
   class-name prefix.

6. **Recipe JSON (unrelated but same session).** 1.21.1 cooking/smelting recipes
   reject bare-string ingredients; use `{ "ingredient": { "item": "modid:thing" } }`.

## Seen in

- gothic-risen-mc (Gothic Scavenger animal mod) — 5 behaviour GameTests all pass
  after these fixes; full write-up in the project's MODLOG.md.
- [`games/minecraft/neoforge-1-21-1-custom-dimension-and-tool-tier.md`](../games/minecraft/neoforge-1-21-1-custom-dimension-and-tool-tier.md)
  — GameTests on the same NeoForge version, with `@PrefixGameTestTemplate(false)` and
  its own GameTest gotchas (dimensions, empty templates).
