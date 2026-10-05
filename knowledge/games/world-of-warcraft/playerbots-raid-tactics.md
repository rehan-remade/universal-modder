---
kind: game
title: 'Teaching AzerothCore playerbots to raid: kill order from raid marks, boss positioning, lockouts and the strategy-reset traps'
game: World of Warcraft
games_also: []
game_version: 'AzerothCore WotLK (3.3.5a) Playerbot fork + mod-playerbots (2026-09 source); client 3.3.5a build 12340'
platform: linux
engine: native
route: other
tools: [mod-playerbots (C++), a small group-control addon (Lua 5.1), lua5.1 test harness]
anti_cheat: 'not applicable: the user''s own server; bots are server-side'
status: working
agents:
- Claude Code (Opus 5.5)
humans: [RedSuper]
date: '2026-10-04'
links: ['https://github.com/mod-playerbots/mod-playerbots']
tags: [playerbots, raid, ai, kill-order, raid-marks, positioning, instances, addon, private-server]
---
# Teaching AzerothCore playerbots to raid: kill order from raid marks, boss positioning, lockouts and the strategy-reset traps

> A 40-player Molten Core / Blackwing Lair raid where the human plays one character and 39 are mod-playerbots
> bots. Stock bots killed packs "by luck", ran into idle mobs and died to cleaves. Changes in the playerbots C++
> made raid marks a real kill order, gave tanks and ranged positions for specific encounters, and fixed the bot
> lockout and strategy problems that made bots vanish or ignore commands. A small addon drives the roster.

## Setup
- mod-playerbots built into the Playerbot fork of AzerothCore; raid roster = account-type bots added by the human,
  plus random bots kept low during raids.
- Patches go in mod-playerbots' value/strategy classes, compiled on another machine and installed with a restart.
- Group control: an addon that whispers bot commands (`co` combat / `nc` non-combat strategy edits, specs, gear)
  and calls server commands; tested under lua5.1 with the WoW API stubbed on a simulated clock.

## Route and why
Server-side AI changes, because bot behaviour lives entirely in the server (bots are real `Player` objects with a
null socket). Raid marks were chosen as the control surface because the human already places them, and they can be
placed before a pull without starting anything.

## How the game works (what we had to learn)
**Targeting**
- Kill order as pure rules (unit-testable, no server types): damage dealers attack the highest mark among mobs
  **already fighting** (skull, then cross, then square); a mark on an idle mob starts nothing. A bot whose own mark
  was set on purpose (`rti <mark>`) keeps it first.
- Tanks hold one mark each: main tank skull, first assist tank cross, second square. The main tank is the
  group's main-tank flag, else the first tank in the member list (newest first); assist tanks follow assistant
  flags then member order.
- Stock `AttackersValue` always added the skull target, so bots ran at marked idle mobs.

**Movement**
- **`AttackAction` derives from `MovementAction` but never walks.** A multiplier that zeroes every
  `MovementAction` (to hold bots in place) also stops them attacking: bots "stand and do nothing". Any movement
  multiplier must exempt attack actions.
- Encounter positioning, computed live from the room: Wyrmguard tanks pick a spot 20 yd from other Wyrmguards,
  18–24 yd from the ranged/healer centre and 30 yd from idle mobs and patrol paths; Nefarian phase 2 puts everyone
  but the main tank outside the front cone (45 yd) and rear cone (30 yd) read from the spell cone data.

**Instances**
- A player enters their own permanent bind first, else the group leader's (`PlayerGetDestinationInstanceId`).
  Bots bound to another, already cleared copy follow the leader's position **inside their own copy**: from the
  human's side they lag and vanish.
- Unbinding never moves a bot that's already inside the wrong copy; `.instance unbind` skips the current map and
  crashes from the console; `.playerbots bot refresh=raid` only reaches online bots.

**Strategies and commands**
- A respec (`talents spec`) calls `ResetStrategies()`, and the engine's `Init()` deletes every queued action. All
  chat commands have equal relevance, so whispers sent together are all queued before the first runs: strategy
  whispers sent within ~0.5 s of a respec are silently dropped.
- Strategies also reset when the master logs back in, when a bot is revived by the manager, when it joins a group
  and when leadership passes.
- `addStrategy(name)` stores under the strategy's own `getName()`, `removeStrategy(name)` looks up that stored key:
  `battleground` adds but only `Battleground` removes.
- A new chat command needs both an entry in the pass-through strategy's supported list and a creator in the chat
  trigger context, or it silently does nothing.
- "Selfbot" mode (the human's own character with a bot AI whose master is itself) is misclassified as a bot at
  ~55 call sites (`IsRealPlayer(master)` checks).
- Party-wide buffs (shouts, totems) apply per raid **subgroup**.
- Threat: giving every non-tank bot the `threat` strategy makes them hold back on a tank's target; tanks must not
  have it (an off-tank's untouched add counts as 100% threat for them and blocks their attack).

**Values and loot**
- `ItemUsageValue` is a `CalculatedValue` with a check interval of 1, so it recomputes on every read and has no
  re-entry guard. `IsItemNeededForUsefullSpell` asks for the usage of every known recipe's product, so a recipe loop
  (Transmute: Earth to Life plus Life to Earth, at max skill so no skill-up exits early) recurses until the stack
  overflows. The crash lands inside libstdc++'s `__dynamic_cast` (the value class uses multiple inheritance) on a
  map thread, a few seconds after a kill when loot rolls start.
- It only bites characters that take the bot path for loot decisions: random and account bots, and a "selfbot" (the
  human's character with bot AI), which `IsRealPlayer` misclassifies.

**Pulls nobody made**
- In Blackwing Lair a goblin pack on the floor above the Halls of Strife was pulled on every run by a shaman bot's
  Searing Totem: totems pick the nearest hostile in range with no line-of-sight or height test, and the core's
  line-of-sight test leaks through that floor. The full analysis is its own note ("Blackwing Lair trash pulled through
  the floor").

## Build steps
1. Kill order: a `KillOrder` rules header used by the DPS, tank, RTI and attackers values.
2. Encounter handlers in the raid strategy classes (triggers + actions + movement multipliers that exempt attack).
3. A server command (in our own small module) that clears every guild member's instance binds, offline ones
   included, keeping the caller's bind for their current map.
4. The addon: leave group → wait → re-invite → seat subgroups (swap-based; `SetRaidSubgroup` fails silently into a
   full group) → specs → a settle pause → strategies in a final pass.

## Verification
- Unit tests for the kill-order rules and positioning maths; addon tests on a simulated clock (including the
  respec race).
- Raids with the human after each change; DB checks of bind tables when bots went missing.
- The recursion: the crash signature (kernel log, fault address equal to the stack pointer) plus a replay of the
  item-usage evaluation over the character's real recipe list, which looped. No world-server crash since the fix
  went in, but that's about a day, not a long soak.

## Gotchas
1. **Bots stopped attacking after the first Wyrmguard died.** **Cause:** a movement multiplier zeroed `AttackAction`
   (it derives from `MovementAction`). **Fix:** exempt attack actions from every movement multiplier.
2. **A phase-1 "hold your spot" made bots idle.** **Cause:** the same inheritance trap. **Fix:** removed the hold.
3. **Bots kept vanishing in Blackwing Lair.** **Cause:** permanent binds to another, cleared copy. **Fix:** a
   guild-wide unbind command before the raid, and teleport stuck bots out and back in.
4. **Strategies "didn't stick".** **Cause:** whispers queued behind a respec were deleted. **Fix:** send strategies
   after a pause, in a final pass.
5. **`nc -battleground` did nothing.** **Cause:** add/remove key asymmetry. **Fix:** remove by the strategy's
   `getName()` spelling.
6. **A healer kept pulling aggro with Healing Stream Totem.** **Cause:** the totem's heal is cast without a
   triggering aura, bypassing the guard that stops healing from inheriting combat and forwarding threat (an open
   AzerothCore issue). **Fix:** give that cast no threat in the core.
7. **An off-tank never picked up its add.** **Cause:** a stale `rti moon` saved from an earlier encounter. **Fix:**
   reset it when the encounter ends and in the DB.
8. **Addon calls failed with "Interface action failed".** **Cause:** `UninviteUnit` / `SetPartyAssignment` are
   protected in 3.3.5a. **Fix:** server commands (`.group disband`) instead.
9. **Navmesh "could not load tile" errors looked like the cause of stuck bots.** **Cause:** they're harmless (grid
   unload keeps the tile); the bots were in another instance copy. **Fix:** check binds first.
10. **The world server crashed twice in Molten Core, right after kills.** **Cause:** the item-usage recursion above,
    started when the selfbot learned a transmute that closed a loop. **Fix:** a `thread_local` set of (bot, item)
    pairs being judged in `IsItemNeededForUsefullSpell` (an item already up the chain counts as not needed); the
    selfbot's roll policy now runs first and judges usage only for weapons and armour.
11. **A trash pack and a boss from the floor above arrived on every Blackwing Lair run.** **Cause:** a Searing Totem
    and a line-of-sight leak (see the separate note). **Fix:** proposed core change; not deployed yet.

## Open questions
- Encounters that need simultaneous kills (e.g. a boss and two adds within 10 s) need a "balance damage across the
  set" target rule; designed, not built yet.
