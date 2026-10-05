---
kind: game
title: 'Blackwing Lair trash pulled through the floor: a Searing Totem and the hit-sphere line-of-sight leak in AzerothCore'
game: World of Warcraft
games_also: []
game_version: 'AzerothCore WotLK (3.3.5a) Playerbot fork, 2026-10 source; vmaps and mmaps extracted from the 3.3.5a client (build 12340); a 40-player mod-playerbots raid'
platform: linux
engine: native
route: other
tools: [AzerothCore source, a small C++ tool linked against the core's collision library (StaticMapTree), Python 3, MySQL 8.4]
anti_cheat: 'not applicable: the user''s own server'
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: [RedSuper]
date: '2026-10-04'
links: ['https://github.com/azerothcore/azerothcore-wotlk', 'https://github.com/mod-playerbots/mod-playerbots']
tags: [azerothcore, line-of-sight, vmaps, hit-sphere, totems, aggro, formations, playerbots, blackwing-lair, debugging, private-server]
---
# Blackwing Lair trash pulled through the floor: a Searing Totem and the hit-sphere line-of-sight leak in AzerothCore

> Every Blackwing Lair run wiped at the entrance of the Halls of Strife: a goblin pack from the drake hall on the
> floor above, then Broodlord and the suppression room, all walking in through a closed gate, with nobody in sight of
> them. The first pull comes from a shaman's Searing Totem. Its target search has no line-of-sight or height filter,
> and the server's own line-of-sight test sees through that floor, because it measures from a point the hit-sphere
> logic pushes about a yard under the upper floor. Found by analysis with an exact replica of the server's test; the
> two-part fix passes the replica but has not been deployed yet.

## Setup
- AzerothCore WotLK (Playerbot fork), 2026-09/10 sources; vmaps and mmaps extracted from the 3.3.5a client.
- The raid: one human and 39 mod-playerbots bots, walked along a fixed route by a dungeon-clear module. That module
  logs a "first contact" line whenever a party member enters combat: the distance to the mob, and the mob's
  distance from its spawn. Those lines were the main evidence.
- Tools: a ~60-line C++ program linked against the core's `libcommon` that loads the map's vmap tiles with
  `StaticMapTree` and answers line of sight the way the server does; Python scripts that generate position pairs
  from the world database and read the client DBCs.

## Route and why
Analysis only. Trial-and-error server changes were ruled out by the human, and the obvious configuration theories
(assistance radius and period) didn't fit the logs. So: list every code path that can put a creature in combat, rule
each one out with data, and replicate the core's geometry tests offline until one path fits all the evidence.

## How the game works (what we had to learn)
**Every way a creature enters combat, and what each one checks**
- **Proximity aggro** (`CreatureAI::MoveInLineOfSight` → `Creature::CanStartAttack`): |Δz| minus both combat reaches
  must be ≤ 3 (`CREATURE_Z_ATTACK_RANGE`), plus line of sight. It cannot cross a 20-yard floor.
- **Assistance:** `Creature::CallAssistance` on attack and then every `CreatureFamilyAssistancePeriod`: 10 yards,
  line of sight between the two creatures. It spreads a pull but never starts one through a floor.
- **Formations** (`creature_formations`, groupAI 1/2/3): no distance and no line-of-sight test. One engaged member
  engages the whole group.
- **Bosses on `BossAI`** zone every player in the map into combat on engage and pulse it every few seconds.
- **Spells:** area effects check line of sight per target; exceptions are `SPELL_ATTR2_IGNORE_LINE_OF_SIGHT`, a
  triggering aura with it, and game-object casts (which only ignore M2 doodads).
- **Totems** (`TotemAI`): the target search is "the nearest attackable unit within the spell's range plus both
  combat reaches", measured in 3D, with **no line-of-sight and no height test**. Only the cast itself
  (`Spell::CheckCast`) checks line of sight, and not even that for positive totem spells.
- **Navmesh paths ignore doors:** a pulled pack walks straight through a closed portcullis.

**The hit-sphere point**
- `WorldObject::IsWithinLOSInMap` measures from a player's feet plus collision height, but from a creature's
  hit-sphere point (`GetHitSpherePointFor`): its centre (feet plus collision height) moved toward the other end by
  min(distance, combat reach).
- For a creature on an upper floor and a target below it, that point moves almost straight down by the combat reach.
  With reach 3.4 and collision height 2.08 (one of the four Blackwing Technician models, also the Warlock's) or reach
  3.125 (the Death Talon Overseer), it ends up about a yard **below the floor the creature stands on**.
- In this map's vmap the drake-hall floor is a single top surface, and the ceiling of the hall below isn't collision
  geometry. A ray that starts under that surface reaches the hall: line of sight "yes", while a player sees a ceiling.
- `creature_model_info` combat reaches under 0.1 are replaced by 1.5 when the table loads, so models stored with 0
  still get an offset (too small to leak here).

**The chain in Blackwing Lair**
1. During the first Death Talon Captain pull, ranged and healers stand in the strip just inside Vael's gate, under
   the goblin formation of the drake hall (the route module also drags the fight there).
2. A shaman bot drops Searing Totem: a 20-yard spell, so it reaches 20 + 1.5 + 3.4 = 24.9 yards. The Captain pack is
   about 45 yards away; the nearest hostile is a goblin 21–25 yards overhead.
3. Searing Bolt's line-of-sight check passes through the floor. One goblin is hit, and the 14-creature formation
   (groupAI 3) engages.
4. The Technicians throw bombs at the raid below through the same leak; the logs show party members entering combat
   with a Technician at about 25 yards while it stands on its spawn.
5. The pack paths down through Broodlord's closed portcullis; Broodlord stands 6 yards from it, assists, and zones
   the whole raid; the suppression room joins as the pack passes. The Warlocks' demon portals leave Felguards that
   nothing despawns after the wipe.

## Build steps
1. **Replica of the server's test:** load every vmap tile of the map with `StaticMapTree` (tile files are named
   `<map>_<tileY>_<tileX>.vmtile`). Compute both ends exactly as `IsWithinLOSInMap` does: a player's eye at feet +
   collision height, a creature's hit-sphere point. Collision height is the unit's scale ×
   CreatureModelData.CollisionHeight × CreatureModelData.Scale × CreatureDisplayInfo.Scale; combat reach comes from
   `creature_model_info` with the 1.5 floor.
2. **Pairs:** every candidate standing spot along the route and in the hall (a 1-yard grid, floors snapped from the
   vmap) against every creature on the floors above within range, for every display variant of each creature.
3. **The fix (proposed, not deployed):** in `GetHitSpherePointFor`, keep the contact point's z at least 0.1 above
   the object's own feet (`contactPoint.z = std::max(contactPoint.z, GetPositionZ() + 0.1f)`); and require line of
   sight in `TotemAI`'s target search, so a totem doesn't lock onto a mob it can't hit.

## Verification
- **Replica:** 29 totem spots (on the 1-yard grid) with line of sight "yes" and in range of 9 Technicians and the
  formation's Overseer: 48 spot/creature pairs. A vertical probe at one of them is blocked from just above the upper
  floor and clear from a yard below it.
- **The fix in the replica:** clamping at feet + 0.1 leaves 0 leaks; clamping exactly at the feet still leaves 2
  (rounding at the floor surface).
- **Logs** of the last runs: the overhead pack, Broodlord and suppression-room mobs reached the raid 50–200 yards
  from their spawns within about 30 seconds of the first trash pull. On another pull, a shaman entered combat first,
  from 21 yards, before anyone else: a totem acting on its own.
- **Not verified:** the fix in game (not deployed yet); which shaman's totem fired on a given run (there is no
  server-side combat log); the missing ceiling collision was inferred from ray probes, not by opening the WMO.

## Gotchas
1. **"There's no line of sight" was checked offline and came out wrong.** **Cause:** the first replica measured feet +
   2 yards at both ends; the server measures from hit-sphere points. **Fix:** replicate `IsWithinLOSInMap` exactly,
   including combat reach and collision height.
2. **Configuration theories (assistance radius and period) went nowhere.** **Cause:** those paths need 10 yards and
   line of sight; they only spread a pull. **Fix:** find the first engagement before tuning anything.
3. **"They walk through the gate."** **Cause:** the navmesh ignores closed doors. Real, but it only explains how the
   pack reaches the raid, not why it was pulled.
4. **Model data says combat reach 0.** **Cause:** the core replaces values under 0.1 with 1.5. **Fix:** do the same in
   any replica.
5. **Starfall looked like the culprit (30-yard radius in 3D).** **Cause:** its script filters targets by line of sight
   to the target's feet plus the caster's height, which the floor blocks, and the bot action refuses to cast it with
   an unengaged hostile within 40 yards. Not it.

## Open questions
- Deploy the fix and confirm the pull is gone in game.
- Any place where a large creature stands right above a walkable area probably leaks the same way.
