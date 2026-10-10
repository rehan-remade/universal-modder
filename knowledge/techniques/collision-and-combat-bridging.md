---
kind: technique
title: "Collision and combat across two games: representations, directions and proxies"
tags: [mashup, passthrough, collision, havok, bsp, voxel-proxy, streaming, combat, damage-mapping, proxies, vehicles, recovery]
date: 2026-10-05
agents: ["Claude Code (Opus 5.5)"]
humans: ["LeiiLo"]
links: ["https://github.com/chasmlol/SkyCraft", "https://github.com/mrborghini/libertycraft"]
---

# Collision and combat across two games: representations, directions and proxies

> "Collision supported" hides at least four separate jobs: getting host geometry, turning it into something
> the guest understands, sending guest builds back so host actors respect them, and keeping both fresh as
> things move. Combat adds units, attribution and double counting. This note compares how bridges
> did each job. Creator test results are reports.

## When to use it
Passthrough and geometry-transfer mashups once a value crosses the bridge and the player needs to stand on,
build in, or fight in the other game's world.

## How

### 1. Acquire host geometry (per host)
| Host | Method |
|---|---|
| Skyrim ([SkyCraft](https://github.com/chasmlol/SkyCraft)) | walks Havok shapes under native locks; a worker streams nearby regions |
| GTA IV ([LibertyCraft](https://github.com/mrborghini/libertycraft)) | incremental native line probes plus nearby-object sampling |
| GTA V (example) | ground probes: 160 columns per frame within radius 40, plus 120 around mobs and police |
| Fallout: New Vegas ([NewVegasCraft](https://github.com/Davozh/new-vegascraft)) | distance-sorted radius-32 disk, at most 48 columns per host tick, terrain-height fallback and highest downward ray |
| Half-Life (GoldSrc) | BSP faces and the player-clip hull (hull expansion removed first); moving brushes send updates |
| Super Mario Galaxy 2 ([GalaxyCraft](https://github.com/M0uidev/GalaxyCraft)) | the other way round: guest geometry is sent as KCL collision for the native game |

LibertyCraft kept SkyCraft's guest-side representation (triangles plus eighth-block voxels) and replaced only
the acquisition. Reusing the representation is what made the fork cheap.

### 2. Choose representations per consumer
SkyCraft keeps exact triangles for the local player's smooth movement, voxelised shapes for general entity
queries, and a coarse occupancy for other uses; capsules and spheres become boxes, unsupported convex shapes
become bounding boxes, some unknown shapes are skipped. LibertyCraft uses smooth triangles for the local
player, voxels for other guest entities, full-cell masks for host NPC obstruction, and column heights for
native water. Name the representation whenever you write "exact collision".

SkyCraft also tells apart a region it knows is empty from a region it hasn't received yet. Do the same in
the guest, or players fall through ground that hasn't arrived yet.

### 3. Send guest builds back to the host (the other direction)
| Project | Guest → host |
|---|---|
| GTA V example | boolean solid/not-solid block changes become frozen GTA boxes (max 400, up to 30 new per frame); slabs and stairs are just solid |
| [FalloutCraft](https://github.com/zeyvu/FalloutCraft) | guest solid blocks become greedy native Havok boxes; NPCs collide with them but don't path around them |
| NewVegasCraft | not built at the listed version: host actors pass through guest blocks |
| SkyCraft | native mesh cutting for dug holes, extra support/wall planes in native collision collectors, land-rescue interception so NPCs aren't lifted out of holes |

Physical blocking, AI navigation and visual removal are three separate outcomes; check each.

### 4. Keep it fresh without stalling
- **Prioritise along velocity and hold the guest.** Early [ValCraft](https://github.com/LoAlCo/ValCraft) prefetches host regions in the direction of
  travel, holds the guest at its last position while preserving momentum, and makes the host puppet
  kinematic so a collision gap can't fling it. A two-second timeout then lets movement continue, so this
  reduces rather than removes the problem.
- **Budget rebuilds.** Some rebuilt-engine projects watch cars within a radius, rebuild only after a set
  distance of movement, at most once a second, and skip identical triangle batches by an FNV-1a hash
  (identical order only; not geometric equivalence).
- **Mark moving regions dirty.** The Half-Life bridge unions a moving brush's old and new regions and cancels
  stale worker jobs with an epoch, but flushes only when the worker is idle.

### 5. Combat: proxies, units and attribution
- **Invisible proxies** are the common pattern: host NPCs become invisible guest entities (villagers in the GTA
  V example, LivingEntity proxies in SkyCraft) so guest weapons can hit them; guest fighters become frozen,
  invisible host doubles so host AI can target them. SkyCraft repositions client proxies every frame because
  server-tick replication was too late for visual hit alignment.
- **Put the unit in the damage message.** MC 20 → Half-Life 100 (×5) in the GoldSrc bridge; native HP in the
  MHW bridge; MC damage converted by target max HP in the ER bridge. SkyCraft scales damage by NPC level,
  so fights don't play like vanilla Minecraft; say which feel you're aiming for.
- **Deduplicate.** The GTA V example remembers eight recent explosion positions for half a second and stops
  player projectiles hitting ped proxies.
- **Keep native attribution.** LibertyCraft adds explicit crime attribution, delayed ragdoll-before-death, safe
  in-car death and a large native health buffer feeding guest-authoritative damage.
- **Write down what invulnerability costs.** Making the host player explosion-proof to stop double damage
  also blocks real host explosion damage.
- **Give short-lived bullets about two frames of life.** A host bullet whose life is shorter than one
  collision frame never hits (see gotcha 7 in
  `knowledge/games/elden-ring/cs2-conversion-of-elden-ring-offline-native-rust-dll-via-me3.md`).

## Gotchas
1. **Host NPCs walk through guest blocks.** **Cause:** collision was only sent host → guest. **Fix:** add the
   reverse path, and treat navigation separately.
2. **Barriers left behind when a door or car moves.** **Cause:** cached columns are never invalidated
   (NewVegasCraft keeps successful columns until reset). **Fix:** dirty-region invalidation for movers.
3. **Blocks placed inside rocks and signs.** **Cause:** a thin barrier skin only. **Fix:** NewVegasCraft
   switched to solid columns from terrain to the highest surface (capped around 24 blocks), which also fills
   arches; record that trade-off.
4. **Dug holes refill.** **Cause:** LibertyCraft's sampled city (BlockyCity) can refill dug holes when new
   collision updates arrive; unseen regions lack data and thin objects vanish. **Fix:** persist edit masks
   separately from sampled geometry.
5. **Destruction that only exists near the host player.** SkyCraft enables terrain destruction only where the
   host knows native geometry; guests' explosions far away leave Skyrim terrain alone. **Fix:** document it.
6. **Vehicles and cutscenes.** **Cause:** a collision-free puppet can't trigger native doors or seats.
   **Fix:** LibertyCraft hands control to GTA in cars and makes the guest follow a non-physical mount; it
   pushes door leaves with a remembered contact side and tries several native door paths.
7. **Guest engine produces invalid numbers.** Keep the last finite transform, reset heading, restore the
   last good pose and stop if another error arrives within a few seconds. Some projects also reload the
   guest engine off the main thread without restarting the host.
8. **Water by name only.** [Signet](https://github.com/kian-cx/signetprotocol)'s Doom and Quake-style importers set the neutral water flag false even for
   water/lava/toxic materials. **Fix:** map hazards explicitly (SkyCraft exports a surface-column grid that
   only guest entity physics sees; LibertyCraft exports hazard tags that trigger native damage and wading).

## Verification
Per-project versions are in `skills/mashup-mods/references/mashup-cases.md`. Creator test results are reports.
