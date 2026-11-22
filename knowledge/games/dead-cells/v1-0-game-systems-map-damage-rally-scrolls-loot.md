---
kind: game
title: "Dead Cells v1.0 game systems for modders: damage and tier scaling, scroll limit, Rally, one-shot protection, DR, loot, prices (with function numbers)"
game: Dead Cells
games_also: []
game_version: "1.0 GOG Windows build (deadcells.exe 8,924,184 bytes, HLB v3 at file offset 384784, build stamp 2018-08-06); data from res.pak (data.cdb at file offset 123,530,592)"
platform: proton
engine: haxe
route: managed-patch
tools: ["hlbc 0.7.0 (disassembly with file:line debug info)", "python3 /proc/pid/mem reader (live telemetry)"]
anti_cheat: "none (single player); keep patched builds out of the Daily Challenge leaderboard"
status: working
agents: ["Claude Code (claude-opus-5-5)"]
humans: []
date: '2026-11-21'
links: []
tags: [dead-cells, hashlink, game-mechanics, damage-formula, scaling, rally, scrolls, boss-cells, affixes, castledb, reference]
---
# Dead Cells v1.0 game systems for modders

> A map of the main gameplay systems in the v1.0 build: where each lives (findex, file:line from the debug
> info), the formula, and which numbers come from `data.cdb` and which are inlined in the code. It's the
> groundwork for a balance or rework mod. Every item is marked **[file]** (constant or data read from the vanilla
> exe/pak on 2026-11-21), **[live]** (seen in a running game with a memory reader), **[in game]** (a player saw it)
> or **[static]** (bytecode read, not run). Formulas are paraphrased, not copied code. File formats, tools and
> patching rules are in `dead-cells-v1-0-modding-reference.md`.

## Setup
- Dead Cells 1.0 GOG Windows (`deadcells.exe` 8,924,184 bytes), run under Proton.
- Function numbers are HashLink findexes in this exe. They don't apply to `deadcells_gl.exe` (a separate compile)
  or to later versions.
- `data.cdb` is plain JSON inside `res.pak`. Its 21 sheets: `truelle` (global tuning), `item`, `mob`, `weapon`,
  `affix`, `itemTag`, `level`, `room`, `roomMarker`, `roomType`, `lightConf`, `biome`, `layer`, `scatterConf`,
  `blueprintDrop`, `dailyReward`, `tierCategory`, `bossRuneGP`, `backFrames`, `loreRoom`, `gui`. Display names in
  it are **French** (`Bombe incendiaire`, `Cauchemar`); look items up by `id`.

## Route and why
This is a reference note: it maps systems so that `data` edits (numbers in `data.cdb`) and `managed-patch`
edits (bytecode) can be targeted. Several "data" values are inlined in the code and ignore `data.cdb`; those
cases are called out.

## How the game works (what we had to learn)

### Tiers: how mobs scale [file]
- **Mob damage:** `scaleMobValueToTier` (4318, Const.hx:305-306) =
  `v × 1.09^(t-1) × (1 + 0.55·(t-1))`.
- **Mob life:** `scaleMobLifeToTier` (4545) = `v × 1.08^(t-1) × (1 + 0.12·(t-1))`.
- **Level tier** [static, live-consistent], decided once when a level is generated (`LevelMap` constructor):
  1. Start from the level's `baseMobTier` (data `level`).
  2. Add the Boss Cell extra (data `bossRuneGP.extraMobTier`: **0 / 2 / 5 / 8 / 11** for BC 0-4 [file]).
     Scoring runs skip this.
  3. Apply `getAdjustedMobTier` (4541) = `max(tier, B+T+S-4)`, where B, T, S are the hero's three colour tiers
     (each starts at 1).
- **Consequences:**
  - "Scrolls" = `B+T+S-3`. Each scroll above `baseMobTier + BC extra + 1` raises the tier of levels generated
    afterwards by 1. Scrolls picked up inside a level only matter from the next level.
  - Colour tiers also count `BrutalityUp` / `TacticUp` / `SurvivalUp` affixes on equipped gear, so swapping gear
    moves the floor too.
  - The lab confirmed this live on a BC3 run: Stilt Village map tier 19 = 11 + 8 [live].
  - At the tiers of a BC3 mid-game, +1 tier is about +13-14 % mob damage and +11-12 % mob life, while a scroll
    gives the hero +15 % damage on one colour. Over the limit, a scroll is a net loss.
- **Traps** use the same tier (`LevelTrap` from `map.mobDmgTier`). Only three level traps deal damage: spikes
  (`Spikes.onTouch` 8148), rotating balls (11122) and shooters (11133) [static].
- **Spike damage to the hero:** base 22 (×0.8-1.2), 2 s cooldown, 0.5 s stun [static]. **The 22 is inlined**;
  `TrapSpikesHero` in `data.cdb` isn't read for it.
- **Biome depth** = `level.worldDepth + 1` [file]:

  | depth | biomes |
  |---|---|
  | 1 | Prisoners' Quarters |
  | 2 | Promenade, Toxic Sewers, Prison Depths |
  | 3 | Ramparts, Ancient Sewers, Ossuary |
  | 4 | Black Bridge, Insufferable Crypt, Corrupted Prison |
  | 5 | Stilt Village, Slumbering Sanctuary, Graveyard |
  | 6 | Clock Tower, Forgotten Sepulcher, Cavern |
  | 7 | Clock Room, Guardian's Haven |
  | 8 | High Peak Castle |
  | 9 | Throne Room |

  Corrupted Prison has data and rooms but **no entrance in v1.0**: its passage has worldDepth 0 [static].

### The damage pipeline: `AttackData.hit` (3676, 6,991 ops) [static unless noted]
- **Base roll.** Power × random 0.8-1.2, or random in [min, max] for ranged ones, unless the debug
  `NO_RANDOM` flag is set.
- **Order** (simplified): roll → tier scaling (`dmgScaledAdd` is added after scaling, so crits and affixes don't
  multiply it) → crit multiplier → item damage reduction → front block / partial block → minimum 1 damage →
  perk procs → Rally heal for the attacker.
- **Exactly 0 damage skips the minimum-1 rule.**
- **Item DR is multiplicative.** A register holds the *remaining* damage multiplier (1.0, × (1 - x) for each
  source), clamped at 0. If you add a new DR source, multiply; don't add.
- **Item DR vs damage bonus** (`InventItem.hasDamageBonus` 411, `getDamageReduction` 409):
  - Only items tagged `NegligibleDamage` or `NoDamage` give carry DR.
  - Untagged items in groups 0-6 (shields are group 6) count as damage-bonus items instead.
  - Block absorption is the separate `props.prct` (e.g. Rampart 0.85).
- **Boss damage soft cap** (`Entity.applyAttackResult` 1818). Mobs with `dmgSoftCap: [min, max]` in data [file]:
  `Behemoth` [0, 0.05], Conjunctivius `Beholder` [0, 0.05], its tentacles `BeholderTtcl` [0, 0.25], 
  `Berserk` [0, 0.03], Hand of the King `KingsHand` [0, 0.05]. They take damage `min·M + e·K / (e + K)`, where M = max life, e = raw damage above
  min·M, and K = (max - min)·M. A single hit can never exceed about max·M.
- **One-shot protection** (`Hero.tryToPreventDeath` 3437):
  - A hit that would kill from at least 25 % of max life [file: the 0.25 constant] leaves you alive.
  - Then a cooldown starts, 45 s [file: inlined int 45, scaled by a multiplier field].
  - YOLO and other revive perks are handled in the same function.

### Rally (recoverable health) [file constants, static logic, in game where noted]
- **Heal per hit:** `min(0.12 × damage dealt, 0.2 × maxLife)` [file: `hit` ops 5489-5501].
- **Starting the bar:** `Hero.applyAttackResult` (3438) sets `lastHitTimer = 36` [file]. The hero's fixed
  update subtracts 2 per 30 Hz tick, so a new hit within **0.6 s** merges into the current bar.
- **Shields:** parries and blocks run the same function but don't refresh the bar.
- **Who can heal Rally:** only hits whose `source` is the Hero.
  - Weapons, power skills and the arrow affixes pass the hero as source.
  - Grenades, turrets, pets and ground fire pass their own entity. DoT ticks pass null.
  - So grenades never heal Rally in vanilla [in game: confirmed when a mod changed it].
- **The shield-hit buff shrinks Rally.** With a `Shield`-tagged item equipped, any hit with
  `triggersGlobalHitShield` gives the hero `GlobalShield` for 0.5 s (`Hero.onDamage` 3433, Hero.hx:1439). While
  it's active, Rally heals are × (1 - 0.65) = 0.35 [file: `hit` ops 5502-5520 test `affects[26] > 0`].
  Constant poison ticks kept it up and made Rally heals tiny [in game: the player noticed it].
- **Tick damage marks itself.** `AttackData.ignoreGlobalShields` is false by default and set only on DoT and
  hazard ticks (burn, bleed, poison, Malaise, darkness). It's the cleanest flag to tell ticks from real hits.

### Status effects ("affects")
- **Storage:** an array of floats indexed by the `Affect` enum. Values are frames left (30 per second), and
  -1 means never set [live]. Ordinals [live]: 8 Stun, 9 FreezeCast, 10 SlowCast, 20 Frost, 21 Thaw. Enum
  globals can be listed from the bytecode.
- **`Entity.setAffectS` (1835)** applies resistance *after* its early-out. A fully resisted affect still fires
  `onAffectChange(added)`, which cut boss animations on parry. Modern 1.25.3 returns on the *resisted*
  duration [in game: the fix confirmed; see the Hand of the King note].
- **Hit delay:** in v1.0, damaging an enemy gives the hero a 0-0.1 s `FreezeCast` (`dmgFreezeCast`). That
  pauses `Skill.update`'s charge countdown (2034) while the animation keeps playing, so hitboxes lag behind
  the animation. Modern removed it [static].

### Loot, affixes, prices [static unless noted]
- **Boss Cell loot bonus:** `bossRuneGP.extraLootLevel` is **0 / 0 / 0 / 1 / 2** [file], but it's added twice
  (LevelMap.hx:148 and LootGen.hx:53), so items are +0/+0/+0/+2/+4 levels. Item DR scales with level, so at
  4 BC armour-type items gain more than intended.
- **Affix rolls:**
  - `ItemGen.addRandomAffix` (13215) does a weighted draw over `affix.chance` [static; edited weights load fine, but the change in drop odds wasn't measured].
  - Group 3 = starred affixes. `generateStats` (13212) forces one starred affix on Legendary items, else 17 %.
- **Paid reroll** (`ForgeUnderground.reforge` 6985): it calls `generateStats` with new seeds, up to 50 times,
  while the new affixes are ≥ 70 % similar to the old ones.
- **Shop price** (`getDefaultPriceWithAffixes` 434):
  - Base × each affix's `costImpact` × `1.4^(item level - 1)`, then rounded to 10 below 500, 50 below 5000,
    100 above.
  - **Food bases 600 / 1200 are inlined** [file]; the `truelle` rows `SmallFoodCost` / `LargeFoodCost` aren't
    read there.
  - A shop's prices are fixed and saved when the shop is generated, so data changes only reach shops generated
    afterwards.
- **Forge:** `truelle.ForgeCellCosts` = cells per forge level, read only by `ItemMetaManager.f_getMaxCells` (3917).
  Neighbours: `ForgeUpgradeMaxRatio`, `ForgeRerollCostBase`, `ForgeRefineCost`.
- **Starting room** (`LootGen.generate` 13605, LootGen.hx:1154-1220):
  - Three slots: bow, melee, shield.
  - Each is a seeded draw over unlocked items, with non-unique items scored -10. The fallbacks are the start
    sword, bow and shield.
  - Shields and bows are both `InventItemKind.Weapon`.

### Movement and timers [static unless noted]
- **Velocity mutation kill streak:** `Hero.spdComboFrames` counts down once per 30 Hz tick.
  `initSpeedComboTimer` (3395) sets it, and `onMobDeath` (3396) refreshes it.
- **Ledge grab** is `Hero.cliffGrab` (3511). The Spider Rune wall cling is `startClimbing(false)` (3513), gated by
  `isDiving` (3444).
- **Ladder re-grab lock:** cooldown key 12582912 (250 ms), set by `stopClimbing` (3514) for ladders *and* wall
  clings.
- **Low-HP effects** (injured run, blood drips, red outline) use three separate inlined `0.33` thresholds in
  `getRunAnimId` (3403) and `Hero.fixedUpdate` (3533). The HUD flash is separate.
- **Max life on load:** `Hero.updateMaxLife` (3398) runs three times through intermediate maxima when a save
  loads. With flooring, you lose a few HP per reload in vanilla.

### Bosses and enemies [mixed]
- **Hand of the King's shield charge** is inline in `KingsHand.fixedUpdate` (6090, KingsHand.hx:1396-1435), not a
  `MobAttack`. A per-target 1.7 s hit lock (`effectCD`) is armed on any contact.
- **Assault Shield vs charging enemies.** `DashShield.push` (14957) calls `cancelVelocities` on the enemy every
  contact frame. Conjunctivius' tentacle sweep only hits while it's moving (`abs(dx) >= 0.05`), so dashing into
  a charging tentacle zeroes its speed: no hit, no parry, and the hero is stuck against it. Swapping that call
  for an empty method of the same type fixed it [in game: 27 parries in 34 dashes in a traced fight].
- **Perk procs** (Combo, Melee, Tainted Flask, Gastronomy, Vengeance, Support, Tranquility, Extended Healing) each
  have a 112-op block in `hit` after a `dmgType == perk` check, with per-target cooldown keys [static].
- **Sadism** in v1.0: an extra hit of 24.75 × 1.15^(brutality-1), at most once per 0.33 s per target. It triggers
  on hero hits while a burning, poisoned or bleeding mob is within 8 cells [static].

## Build steps
To change one of these systems:
1. Find the function above in a full disassembly (file:line debug info makes it readable).
2. Decide whether the value is data (`data.cdb`) or inlined.
3. For data, edit the JSON in place at the same length.
4. For code, follow the rules in the reference note and boot-test.

## Verification
- **[file]** items were read from the vanilla exe / `res.pak` on 2026-11-21: the tier scaler constants, Rally
  0.12 / 0.2 / 36 and the 0.65 shield cut, OSP 0.25 / 45, food prices, the Boss Cell rows, `dmgSoftCap` rows,
  timed-door data.
- **[live]** items come from a memory reader on a running game. Scroll telemetry was checked against map tiers
  on a BC3 run.
- **[in game]** items are things a player saw: grenades not healing Rally, the Rally heal shrink under poison,
  the tentacle charge, the parry snap fix.
- Everything else is **[static]**: read from the bytecode and not run. Several static readings in this project
  had to be corrected after a live trace, so confirm before building something big on one.

## Gotchas
1. **Editing `data.cdb` did nothing.** Cause: the value is inlined in the code (spike damage 22, food prices
   600/1200, the low-HP 0.33 thresholds). Fix: list every reader of a field before editing it. If there's no
   reader, patch the constant in the bytecode.
2. **Raising a cap crashed the game later.** Cause: a level field had five `Switch` readers, and one with a
   "not handled" throw was missed (a tentacle level above 3 crashed at level 4). Fix: find *every* reader,
   including switches with throwing defaults, before widening a range.
3. **A balance change didn't show in the current level or shop.** Cause: mob tiers and shop prices are decided
   when the level or shop is generated, and shops are saved. Fix: test in a newly generated level.
4. **Boss Cell loot looked too strong.** Cause: `extraLootLevel` is applied twice in v1.0. Fix: account for it,
   or patch one of the two sites.
5. **Names in data don't match the game.** Cause: `data.cdb` names are French. Fix: search by `id` (e.g.
   `FireBomb`, `DashShield` = Assault Shield, `BumpShield` = Cudgel, `HoldShield` = Frontline Shield, `Rampart`).

## Assets
None.

## Cost and time
This note is a summary of five weeks of mod work. Writing it up took part of one session.

## Open questions
- What makes a held Frontline Shield block still stun the hero? Static reading found no stun on that path. A live
  trace is the next step.
- Modern (1.25.3) equivalents of most of these functions are unmapped. Use `strings` on `hlboot.dat` and the
  class names to find them.
