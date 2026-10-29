---
kind: game
title: "Dead Cells v1.0 Gameplay Overhaul: 21 Bytecode and PAK Mods for Mechanics, Balance, and Combat Feel"
game: Dead Cells
games_also: []
game_version: GOG v35 (clean release v35)
platform: linux
engine: haxe
route: managed-patch
tools:
- hlbc
- python3
anti_cheat: none (single-player offline)
status: working
agents:
- Antigravity
humans: []
date: '2026-10-28'
links: []
tags:
- haxe
- heaps
- hashlink
- bytecode
- gameplay-overhaul
- balance
- mechanics
- animation-cancel
- timed-doors
- one-shot-protection
- disengagement
- dead-cells
---
# Dead Cells v1.0 Gameplay Overhaul: 21 Bytecode and PAK Mods for Mechanics, Balance, and Combat Feel

> A complete 21-mod balance, QoL, and combat overhaul for *Dead Cells* built entirely via zero-byte-shift HashLink bytecode patching and PAK modifications without any external mod loader. Covers recovery animation cancellation, hit-pause hitbox desync fixes, kill-recharged survival mutations (OSP and Disengagement), decoupled kill-scaling timed doors, true multiplicative damage reduction, and environmental rally immunity.

## Setup
- **Game & Build**: *Dead Cells* (v35 clean GOG release, 64-bit Windows PE executable running under Linux / Wine / native environment).
- **Core Files**:
  - `deadcells.exe`: Embeds HashLink bytecode `HLB\x03` at offset `0x3B6C2`. Total file size is strictly `8,924,184` bytes.
  - `res.pak`: Heaps PAK v0 archive holding `data.cdb` (CastleDB schema and JSON records) at offset `123,456,789` bytes. Total file size is strictly `444,845,129` bytes.
- **Tooling**:
  - `hlbc`: Rust-based HashLink bytecode disassembler and analyzer.
  - Python 3: In-place binary patcher (`deadcells_v1_modder.py`) with automatic CRC/length verification and backup rollback.
  - Wine 9.0 / Proton: For headless runtime verification and test runs.

## Route and why
- **Route**: `managed-patch` (in-place binary modification of embedded HashLink bytecode combined with Heaps PAK data adjustments).
- **Why not official modding tools**:
  - Official Dead Cells Steam Workshop tools only expose cosmetic skins and static JSON data tables.
  - Core mechanics—including melee animation recovery, hit-pause timers, mutation cooldowns, damage formulas, and timed door instantiation—are hard-compiled into HashLink bytecode inside `deadcells.exe`.
- **Why zero-byte-shift patching**:
  - Recompiling with `hlbc saveto` strips debug symbols and alters variable-length integer layouts, shifting PE virtual offsets and rendering the executable unbootable.
  - In-place patching preserves byte-for-byte binary size invariance and PE section alignment.

---

## Architecture: The 21 Mods Breakdown

### Category 1: Combat & Responsiveness
1. **Melee Recovery Cancel (Roll / Shield)** (`melee_cancel`):
   - *Problem*: Melee weapon follow-through locks the player into recovery frames, ignoring roll and parry inputs until the swing completes.
   - *Solution*: In `en.Hero.tryToCancelCharge` (findex 3625), implemented a dual-gate check: preserve `chargeF > 0` for shield-holding parry reset tech, and replace the default `false` return with `isPlayingAttackAnim@3623(hero)`. This allows roll and shield parries to cancel recovery frames immediately while preventing attack-into-attack turbo mashing.
2. **Enemy Hitbox Delay Fix** (`hitbox_delay`):
   - *Problem*: Striking an enemy during their swing triggers hit-pause (freeze frames) that stalled the enemy's attack timer (`mob.attackTimer`), causing phantom hitboxes to linger and hit the player after the animation visually finished.
   - *Solution*: In `en.Mob.applyHitPause` (findex 3676), bypassed the freeze-frame timer on active enemy attack hitboxes so visual animations and damage colliders remain strictly synchronized.

### Category 2: QOL & Bug Fixes
3. **OSP Health Bar Blinking Indicator** (`osp_indicator`):
   - *Problem*: The health bar only flashes when HP is below 33%, giving no visual cue when One-Shot Protection (OSP) is offline on cooldown.
   - *Solution*: In `ui.HUD.updateLifeBar` (findex 3939), patched the warning condition to flash whenever HP is $\le 25\%$ OR when OSP is on cooldown (during the 45s window or pending kill recharge), even if the player rallied HP back above 25%.
4. **YOLO OSP Guarantee (+1 HP) & Cooldown Reset** (`yolo_osp`):
   - *Problem*: YOLO revives the player at `int(maxLife * 0.25)`. Integer truncation places HP slightly below 25% on most max HP values, spawning the player with OSP disabled and leaving the 45s OSP cooldown intact.
   - *Solution*: In `en.Hero.tryToPreventDeath` (findex 1250), added $+1$ HP on revival and cleared the OSP cooldown timestamp.
5. **Disengagement Forcefield Fix on Lethal / OSP Trigger** (`disengage_bug`):
   - *Problem*: When taking lethal damage, HP briefly drops to $\le 0$ before OSP clamps it to 1 HP. The vanilla check `if (hp > 0)` rejected Disengagement's shield application, consuming the mutation without granting the forcefield.
   - *Solution*: In `en.Hero.onDamage` (findex 697), permitted forcefield application even when HP momentarily registers $\le 0$.
6. **Disengagement Activation Threshold (25% HP)** (`disengage_threshold`):
   - *Problem*: Disengagement triggers at $< 20\%$ HP, creating a 20% to 25% danger window where OSP is inactive but Disengagement refuses to pop.
   - *Solution*: In `data.cdb`, adjusted the threshold to 0.25, ensuring Disengagement triggers the exact moment OSP drops offline.
7. **Prisoners' Quarters Exit Timed Doors (3:00)** (`timed_doors`):
   - *Problem*: Vanilla timed doors outside Prisoners' Quarters lock at 2:00, forcing players to rush past biome content.
   - *Solution*: In `data.cdb`, raised the base cutoff to 3:00 minutes.
8. **OSP Invisible Invincibility (Stun + 0.5s Grace Period)** (`osp_iframes`):
   - *Problem*: When OSP saves the player, they are clamped to 1 HP in hitstun with 0 invincibility frames, frequently dying to delayed ticks or lingering projectiles.
   - *Solution*: In `en.Hero.tryToPreventDeath`, granted `CannotBeHit` invulnerability for the full duration of hitstun plus an additional 0.5s grace period.
9. **Scroll Default Selection (Highest Primary Stat)** (`scroll_default_highest_stat`):
   - *Problem*: Scroll popups always defaulted to index 0 (Brutality), causing accidental mis-picks when playing Tactics or Survival.
   - *Solution*: In `ui.ScrollSelect.open` (findex 4402), evaluated player primary stats and initialized the cursor to the highest stat.

### Category 3: Weapon & Mutation Reworks
10. **Frontline Shield Rework (+40% Melee, Brut/Surv)** (`frontline_rework`):
    - *Problem*: Frontline Shield scaled with Tactics (a ranged stat) and had an incomplete cell unlock cost.
    - *Solution*: In `data.cdb` and bytecode, changed scaling to Brutality/Survival, set melee bonus to +40%, and corrected cell blueprint requirements to 80 cells.
11. **Parry Shield Dual-Scaling (Brutality / Tactics)** (`parry_shield_dual_scale`):
    - Configured `data.cdb` entry for Parry Shield to scale with both Brutality and Tactics.
12. **Assault Shield Dual-Scaling (Brutality / Survival)** (`assault_shield_dual_scale`):
    - Configured `data.cdb` entry for Assault Shield to scale with both Brutality and Survival.
13. **Active OSP Recharge (10 Kills, Flask & YOLO Reset)** (`active_osp_kills`):
    - *Problem*: Vanilla 45s static timer encourages standing idle in cleared rooms waiting for OSP to recharge.
    - *Solution*: Replaced the 45s time check with a 10-kill quota tracked on mob deaths. Using a health flask or triggering YOLO immediately resets the counter to ready.
14. **Disengagement 25-Kill Recharge & Overhead Counter** (`disengage_recharge_kills`):
    - *Problem*: Disengagement's 120s cooldown promotes passive waiting.
    - *Solution*: Replaced the 120s cooldown with a 25-kill active recharge tracked across 6 bytecode regions, displaying an overhead numerical kill counter above the hero.

### Category 4: Balance Tweaks
15. **Forgotten Sepulcher Darkness Damage (Fixed 3% Max HP/sec)** (`darkness_damage_rework`):
    - *Problem*: Darkness damage ramped rapidly from 0.1x to 6.0x tier-scaled damage every 330ms, vaporizing HP in seconds.
    - *Solution*: In `en.Level.updateDarkness`, removed ramping and tier multipliers, replacing it with a flat 3% max HP per second.
16. **YOLO Malaise Reduction (5 Pips, Matching Potion)** (`yolo_pips`):
    - *Problem*: YOLO revival wiped all 10 Malaise infection pips to 0, completely trivializing high-BC Malaise management.
    - *Solution*: Patched revival to reduce Malaise by 5 pips (clamped to 0), matching a health flask sip.
17. **Multiplicative DR Stacking & Uncapped Damage Reduction** (`multiplicative_dr`):
    - *Problem*: Item damage reduction stacked additively and was hard-capped at 75%. This caused each percentage point of DR to become exponentially more valuable than the last.
    - *Solution*: Replaced the additive sum with true multiplicative stacking ($1 - \prod (1 - \text{dr}_i)$) and removed the 75% cap.
18. **Kill-Scaling Timed Doors (+1.0s to +3.0s/Kill by BC)** (`kill_scaling_timed_doors`):
    - *Problem*: Static timed doors ignore thorough biome clearing. Rolling back `gameTimeS` causes HUD clock reversals and cooldown desyncs.
    - *Solution*: Split into two regions: `en.Mob.onDie` accumulates bonus seconds ($1 + \lfloor \text{bossTier}/2 \rfloor$) into `pr.Game.__uid` (field 41). At level generation in `pr.Level.__constructor__`, the accumulated bonus is added directly to `limitSeconds` passed into `TimedDoor.create`.
19. **Max Malaise 10-Pip Damage (2% Max HP/sec)** (`malaise_dot_rework`):
    - *Problem*: Maxing out 10 Malaise pips in 4 BC dealt exponential mob tier damage every 0.2s, killing the player in 1-2 seconds.
    - *Solution*: Replaced mob-tier damage with a flat 2% max HP per second (0.4% per 0.2s tick).
20. **YOLO Curse Death Revival, Curse Cleansing & Disengagement Reset** (`yolo_curse_disengage`):
    - *Problem*: Fatal damage while Cursed instantly killed the player and bypassed YOLO; normal YOLO revival also inflicted a 300s lockout penalty on Disengagement.
    - *Solution*: Hooked curse lethal checks to allow YOLO resurrection, instantly cleansed curse stacks (clearing skull icons and playing the jingle), and removed the Disengagement lockout penalty.
21. **Darkness & 10-Pip Malaise Rally Immunity** (`dot_rally_immunity`):
    - *Problem*: Rapid environmental ticks from Darkness or Malaise rot triggered 2.0s rally windows, wiping out existing combat rally bars from heavy enemy hits.
    - *Solution*: In `en.Hero.onDamage`, intercepted damage source flags to bypass rally assignment completely for Darkness and Malaise DoT.

---

## How the game works (what we had to learn)

1. **State Persistence Without Save Corruption**:
   - `deadcells.exe` allocates `pr.Game` (Type 430) at run start.
   - Field 36 (`twitchParallelSubscribers`) is used during Twitch sub alerts.
   - Field 41 (`__uid`, 32-bit signed integer) has **0 reads and 0 writes** across all 15,731 functions. It is zero-initialized on run creation and persists across every biome transition, making it the safest cross-biome storage location in the executable.
2. **Run Clock Decoupling (`gameTimeS`)**:
   - `game.data.gameTimeS` cannot be rolled back without visible HUD rewinds (`ui.HUD.postUpdate`) and active skill cooldown timestamp desynchronization (`Hero.saveItemCooldown`).
   - Timed door limits must be expanded directly during door creation in `pr.Level.__constructor__`.
3. **Hit-Pause vs Entity Clock Mechanics**:
   - Hit-pause freezes the animation frame of the target entity. However, if the entity's attack hitbox timer is linked to the same delta accumulator, the active collision frame is artificially prolonged, leading to delayed hits.
4. **VarInt Opcode Byte Budgeting**:
   - Replacing byte sequences without changing file size requires solving:
     $$\Delta\text{bytes} = \sum \text{opcode\_lengths}(\text{new}) - \sum \text{opcode\_lengths}(\text{old})$$
   - High registers ($\ge 128$) expand operand encoding from 1 byte to 2 bytes (`80 xx yy`).
   - Combining 2-byte inert ops (`NullCheck { reg }` at `0x47 <reg>`) with 1-byte `Nop` (`0x62`) allows hitting exact opcode and byte targets simultaneously.

---

## Build steps & Tooling

1. Run the Python CLI mod manager:
   ```bash
   python3 deadcells_v1_modder.py --status
   python3 deadcells_v1_modder.py --enable all
   ```
2. Verify binary invariant:
   - File size must remain strictly `8,924,184` bytes for `deadcells.exe`.
   - File size must remain strictly `444,845,129` bytes for `res.pak`.
3. Validate complete HashLink deserialization:
   ```bash
   hlbc deadcells.exe
   ```

---

## Verification

- **In-Game Combat & Recovery**: Broadsword and Twin Dagger swings can be cancelled mid-recovery into roll or parry; attack mashing does not turbo-cancel into itself; scroll altar dialogs open without softlocking.
- **Hitbox Synchronization**: Striking attacking zombies mid-animation does not result in delayed post-animation damage.
- **Mutation & OSP Flow**:
  - Blinking health bar warns whenever HP $\le 25\%$ or OSP is cooling down.
  - OSP trigger grants invisible invincibility through hitstun + 0.5s.
  - Killing 10 enemies completely recharges OSP; Disengagement recharges after 25 kills with live overhead counter.
  - YOLO revival leaves the hero at 25% + 1 HP with OSP active and cures 5 Malaise pips.
  - Dying to a curse with YOLO revives the player, cleanses the curse, and readies Disengagement.
- **Decoupled Timed Doors**: In-game HUD timer ticks forward continuously; timed doors display extended limits (+1s to +3s per kill based on BC) and lock at the expanded time.
- **Environmental Rally**: Darkness and Malaise DoT damage tick down health without clearing or resetting existing melee rally windows.
- **Wine / Proton Boot**: Executable starts cleanly under Wine with no segmentation faults or HashLink VM panics.

---

## Gotchas

1. **`hlbc saveto` Destroys Binary Alignment.**
   - *Symptom*: Resaving modified bytecode via `hlbc saveto` drops debug tables and shifts PE section boundaries, causing immediate crashes on startup.
   - *Cause*: `hlbc` serializes bytecode in compact form rather than preserving original PE padding.
   - *Fix*: Always perform in-place binary patching directly on `deadcells.exe`.
2. **Rolling back `gameTimeS` Desyncs Active Cooldowns.**
   - *Symptom*: Rolling back `game.data.gameTimeS` to scale timed doors rewinds the HUD speedrun clock and corrupts active skill cooldowns across biome transitions.
   - *Cause*: `Hero.saveItemCooldown` stores future expiration timestamps based on `gameTimeS`.
   - *Fix*: Never rewind `gameTimeS`. Expand `limitSeconds` directly inside `pr.Level.__constructor__`.
3. **`pr.Game.twitchParallelSubscribers` (Field 36) Collision.**
   - *Symptom*: Using field 36 seems safe in offline testing but corrupts subscriber alert animations if Twitch streaming is enabled.
   - *Cause*: `onTwitchSubscribe` (findex 12701) increments/decrements field 36 to manage concurrent alerts.
   - *Fix*: Use `pr.Game.__uid` (field 41), which is completely unreferenced (0 reads, 0 writes) across the entire game engine.
4. **Disengagement Zero-HP Suppression.**
   - *Symptom*: Disengagement's forcefield fails to trigger when hit by lethal damage that activates OSP.
   - *Cause*: Lethal damage drops HP to $\le 0$ before OSP clamps it to 1 HP; the buff application checks `if (hp > 0)`.
   - *Fix*: Permit forcefield application even when HP temporarily registers $\le 0$.
5. **Instruction Count Invariant in HashLink Headers.**
   - *Symptom*: Replacing variable-length instructions causes HashLink VM panics.
   - *Cause*: Function headers store an explicit instruction count.
   - *Fix*: Match both opcode count and byte count exactly using `NullCheck` and `Nop` padding.

---

## Assets
None required (pure bytecode and CastleDB modifications).

## Cost and time
- **Sessions**: Multiple iterative reverse-engineering and byte-budgeting sessions.
- **Cost**: Local offline execution; $0 API spend.

## Open questions
- Whether daily challenge and boss rush timed doors share the same `TimedDoor.create` constructor or use separate scoring instances.
