---
kind: technique
title: "Bridge contracts for two-game mods: ownership, units, transport and lifecycle"
tags: [mashup, passthrough, shared-memory, seqlock, ring-buffer, endianness, coordinate-mapping, authority, lifecycle, restart, protocol-versioning]
date: 2026-10-05
agents: ["Claude Code (Opus 5.5)"]
humans: ["LeiiLo"]
links: ["https://github.com/chasmlol/SkyCraft", "https://github.com/mrborghini/libertycraft"]
---

# Bridge contracts for two-game mods: ownership, units, transport and lifecycle

> Most hard bugs in two-game mods come from something nobody wrote down: who owns the player, which unit a
> number is in, which frame a pose belongs to, or what happens when one side pauses or restarts. Write a
> contract (`docs/CONTRACT.md`) before the bridge code and check every change against it. Creator
> test results are reports.

## When to use it
Any route where two programs share state: live passthrough, frame compositing, geometry transfer, a
transplanted subsystem behind a C API, or a worker process. See `choosing-a-mashup-route.md` first.

## How

### Contract fields
1. **Route and exact versions** of both programs, loaders and any translation layer (Proton, CrossOver).
2. **Ownership table**: player position/physics, camera, world geometry, collision in each direction, NPCs,
   damage/health, inventory, saves, menus/pause/loading, and scripted events (cutscenes, vehicles,
   furniture). For each row: the owner, the hand-back trigger, and how control returns.
3. **Units and axes**, written as a function both sides share.
4. **Channels**: kind (snapshot, queue, byte ring, image), direction, rate, and the policy when full or late.
5. **Protocol identity**: name, magic, version, byte order, and how each side detects the other restarting.
6. **Lifecycle**: start order, pause, load/area change, death, disconnect, crash, uninstall.
7. **Not covered**: the systems this bridge leaves alone and what the player will see.

### Ownership and hand-back choices
| Project | Owner of player movement | Hand-back rule |
|---|---|---|
| [SkyCraft](https://github.com/chasmlol/SkyCraft) 0.1.2 | Minecraft | furniture, mounts, kill-moves and native camera scenes return control to Skyrim temporarily |
| [LibertyCraft](https://github.com/mrborghini/libertycraft) | Minecraft | GTA takes over for missions, cutscenes, minigames and cars; the guest follows a non-physical mount at the seat and re-syncs by a teleport handshake |
| Minecraft × GTA V example | GTA on foot; Minecraft in elytra flight | GTA supplies look and chase camera during flight |
| [Minecraft × Half-Life](https://github.com/SawyerTheNerd/Minecraft-X-HalfLife) (GoldSrc) | Minecraft | ladders, `use`, noclip and death return movement to Half-Life |
| [Garry's Redemption](https://github.com/codeByAlexff/garrys-redemption) (design doc) | hidden Garry's Mod | native actors mirrored as invisible proxies; the guest drives grabbed/struck proxies, ownership returns after release and settling |

### Unit mappings
| Project | Mapping |
|---|---|
| Minecraft × GTA V example | 1 GTA metre = 1 block; GTA (x, y, z) → MC (x, z + yOffset, −y); yaw = 180 − heading |
| LibertyCraft (GTA IV) | 1 metre per block |
| [NewVegasCraft](https://github.com/Davozh/new-vegascraft) (FNV 1.4.0.525) | 70 host units per block; host x-east/y-north/z-up → MC x / z + yOffset / −y; exterior yOffset fixed at −34 after per-load releveling moved builds by about 0.9 m |
| Minecraft × Half-Life | 40 units per block; 72 units ≈ 1.8 m; health MC 20 → HL 100 (×5) |
| [Faith Runner](https://github.com/tnrjns/faith-runner) in Skyrim | 70 units per metre |
| [Killcraft](https://github.com/goonsn/Killcraft) (ULTRAKILL) | 2 host units per block |
| Garry's Redemption design | 0.01905 m per Source unit, with a planned floating origin |
| SkyCraft | 70 host units per block |
| [2010 Rust Rewrite Mashup](https://github.com/chasmlol/2010-rust-rewrite-mashup) | 36 host units per block |

### Channel delivery policies (LibertyCraft, inherited from SkyCraft's Windows transport)
- **Seqlock snapshots** for continuously replaced state (pose, player state). The counter is odd while
  writing and even when done; the reader checks it before and after copying.
- **Bounded queues** for discrete events, with explicit drop behaviour.
- **Padded byte rings** for variable-size data (meshes).
- **Latest-frame triple buffering** for images and overlays.
- **Restart generations**: a changed generation triggers a resend of state the other side lost.

SkyCraft's header also carries process IDs, heartbeats and epochs, so a reader can tell a live peer from
stale data, and it keeps the previous and current Minecraft tick so the host can interpolate 20 Hz ticks
into its own frame rate. Its Java and C++ layouts are mirrored by hand, so they can drift apart; the
layout test below catches that.

### Byte order and layout
[GalaxyCraft](https://github.com/M0uidev/GalaxyCraft)'s host protocol is little-endian (version 10) while the emulated PowerPC mailbox is big-endian
(version 5); many display-list/model payloads are already big-endian and must not be swapped again. A shared
C assertion file pins offsets, region lengths and struct sizes. Add the same kind of compile-time layout
test on both sides.

### Template for `docs/CONTRACT.md`
```markdown
# Bridge contract: <guest> inside <host>

Route: <passthrough | frame compositing | geometry transfer | rebuilt engine | ...>
Host: <game, exact build, loader + version, OS / translation layer + version>
Guest: <game or engine, exact version, loader + version>

## Ownership
| System | Owner | Hand-over trigger | How it comes back |
|---|---|---|---|
| Player movement | | | |
| Camera | | | |
| Collision host → guest | | | |
| Collision guest → host | | | |
| NPCs | | | |
| Damage / health | | | |
| Inventory | | | |
| Saves | | | |
| Menus / pause / loading | | | |
| Cutscenes / vehicles / furniture | | | |

## Units and axes
host_to_guest(x, y, z) = ...

## Channels
| Name | Kind | Direction | Rate | When full or late |
|---|---|---|---|---|

## Protocol
Magic: ... Version: ... Byte order: ... Restart detection: ...

## Lifecycle
Start order / pause / level change / death / disconnect / crash / uninstall

## Not covered
...
```

## Gotchas
1. **Matching magic, different meaning.** **Symptom:** a bridge built for one host half-works on another.
   **Cause:** the CrossOver Elden Ring and Monster Hunter: World bridges share magic/version and common
   offsets but differ in header size, regions, units and damage semantics (ER sends Minecraft damage
   converted by target max HP; MHW sends native HP). **Fix:** version per host; put the unit in the message.
2. **A "seqlock" that isn't one.** **Symptom (hypothesis):** occasional torn frames. **Cause:** the MHW frame
   writer's update takes an even counter straight to the next even value, so it never marks a write in
   progress; the ER writer sets the counter odd first, as intended. No visible glitch was shown.
   **Fix:** test the writer: assert the counter is odd during the write.
3. **Layout reuse is not compatibility.** LibertyCraft kept SkyCraft's fixed v11 byte layout but changed the
   magic and added GTA-specific events and flags. **Fix:** change the magic or version whenever meaning
   changes, so an old peer is rejected instead of misread.
4. **Mismatch handling that overwrites.** The Half-Life bridge's shared mapping overwrites an existing layout
   on magic/version mismatch rather than rejecting it. **Fix:** reject and log, so two builds can't corrupt
   each other.
5. **Recycled entity IDs.** **Cause (hypothesis):** the Half-Life bridge refers to native entities by index
   without a generation tag, so a delayed event could reach a recycled entity. MHW hazards add a serial for
   this reason. **Fix:** send (index, generation) pairs.
6. **Blocking calls on the game thread.** NewVegasCraft's first WebSocket client sent synchronously from the
   game loop with no deadline and unbounded receive size; [Signet](https://github.com/kian-cx/signetprotocol)'s client writes TCP while holding a mutex,
   and its server broadcasts while holding shared state. **Fix:** a sender thread with a bounded queue, and
   time-outs.
7. **Events consumed by a size query.** Signet's C interface consumes events even during a null-buffer sizing
   call, so the usual size-then-copy pattern loses them. **Fix:** make sizing side-effect free, or document a
   fixed buffer.
8. **A setting both sides touch.** NewVegasCraft restores the host's fight-disable bit only if the plugin set
   it; that still can't arbitrate a later mod changing it. **Fix:** record the original value and owner.
9. **Producer/consumer format drift.** [BullySkate](https://github.com/Faiqie/BullySkate)'s collision file moved from segments (BMRL2) to polylines
   (BMRL3) with a receipt schema bump that the launcher checks. **Fix:** version every generated file and
   refuse a mismatch.
10. **Scripted openings with the guest in control.** SkyCraft's notes warn the Helgen cart opening may stall
    while Minecraft owns movement and suggest Alternate Start or a post-Helgen save. **Fix:** hand control
    back for scripted sequences, or document the workaround.

## Verification
Versions per project are in `skills/mashup-mods/references/mashup-cases.md`. Items
marked "hypothesis" are inferences, not reproduced results.
