---
kind: technique
title: "Choosing a mashup route: seven ways to put a game inside a game"
tags: [mashup, passthrough, route-selection, frame-compositing, geometry-transfer, shared-simulation, reimplementation, asset-conversion, subsystem-transplant, ownership]
date: 2026-10-05
agents: ["Claude Code (Opus 5.5)"]
humans: ["LeiiLo"]
links: ["https://github.com/chasmlol/SkyCraft", "https://github.com/mrborghini/libertycraft", "https://github.com/vladtrc/iw4L", "https://github.com/samwhosung/benilla"]
---

# Choosing a mashup route: seven ways to put a game inside a game

> "Minecraft in X" covers at least seven architectures that look the same in a clip. Pick the route from
> what the user wants (real guest behaviour, or only its look or one mechanic), who owns the
> player, and what each player must own.

## When to use it
Before the first line of mashup code, and again whenever a plan quietly changes route (for example a
"passthrough" that has become a frame overlay). It complements `skills/mashup-mods/SKILL.md`, whose
patterns map onto the routes below.

## How

### 1. Classify the idea
| Route | What runs | What crosses | Every player needs | Examples |
|---|---|---|---|---|
| **Live passthrough** (state exchange) | both real games | positions, collision, hits, events | both games + both loaders | [SkyCraft](https://github.com/chasmlol/SkyCraft) (Skyrim/SKSE + Minecraft/Fabric), [LibertyCraft](https://github.com/mrborghini/libertycraft) (GTA IV fork of SkyCraft), [ValCraft](https://github.com/LoAlCo/ValCraft), [Killcraft](https://github.com/goonsn/Killcraft) |
| **Frame compositing** (picture transport) | both real games | colour + depth + HUD images and a camera pose | both games | `examples/minecraft-gta5-passthrough`, CrossOver Elden Ring / Monster Hunter: World bridges, [NewVegasCraft](https://github.com/Davozh/new-vegascraft), Wither Storm × GTA V |
| **Native geometry transfer** | both real games; the host draws guest meshes | meshes, atlases, collision | both games | SkyCraft's renderer, LibertyCraft, [Minecraft × Half-Life](https://github.com/SawyerTheNerd/Minecraft-X-HalfLife) (GoldSrc), [GalaxyCraft](https://github.com/M0uidev/GalaxyCraft) (SMG2 in Dolphin) |
| **Shared neutral simulation** | a separate server; games are viewers | neutral state and input intents | a viewer | [Signet](https://github.com/kian-cx/signetprotocol) |
| **Engine recreation** | one rebuilt engine reading owned data | nothing; one process | the original's files | [IW4L](https://github.com/vladtrc/iw4L), [benilla](https://github.com/samwhosung/benilla), [HL2-RS](https://github.com/kvalls/hl2-rs), [2010 Rust Rewrite Mashup](https://github.com/chasmlol/2010-rust-rewrite-mashup), CS:Craft, [World of Skatecraft](https://github.com/Kimmo3223/world-of-skatecraft) (Skate engine added to benilla) |
| **Asset / map conversion** | the host only | converted files, made offline | the host (and own copy of the source) | Doom WADs rebuilt in Hytale, one open-world RPG converted into another, PipeLink converters, a Halo CE map imported into IW4L |
| **Rebuilt guest engine or mechanic in a real host** | the real host plus a rebuilt guest engine or one rebuilt mechanic | the rebuilt part's state, via a DLL or a worker process | the host + own copy of guest data | Skate 3 engine in Bully ([BullySkate](https://github.com/Faiqie/BullySkate) workers) and Garry's Mod ([SkateGM](https://github.com/the-schwilliam/SkateGM)); [Faith Runner](https://github.com/tnrjns/faith-runner); AC1 movement; Diablo II movement in DevilutionX |

Out of scope here, though also called mashups: cross-game progression links (multiworld randomizers), protocol
translators ([HyCraft](https://github.com/EdwardBelt/HyCraft): Minecraft clients on a Hytale server), programs compiled into Minecraft commands
([Wasmcraft2](https://github.com/SuperTails/wasmcraft2)), and emulators inside games.

Most shipped projects mix routes: frame compositing for the picture plus state exchange for collision and
combat is the common combination.

### 2. Answer four questions, in order
1. **Real guest behaviour or only its look/rules?** Real behaviour needs the guest running (passthrough,
   compositing, geometry transfer). Look or rules alone is conversion, transplant, or pattern 5 in the
   mashup skill. Original-looking assets don't imply original physics: Signet's Doom viewer draws
   Doom-looking walls on a simplified shared 2.5D movement mode.
2. **Who owns the player, and how does control come back?** Write it down now (see
   `bridge-contracts-ownership-units-and-lifecycle.md`). Choices differ: Minecraft owns movement
   in SkyCraft (Skyrim takes over for furniture, mounts, kill-moves); GTA owns it on foot and Minecraft in
   elytra flight in the GTA V example; ladders, `use`, noclip and death return control to Half-Life in the
   GoldSrc bridge.
3. **Can the host draw guest geometry itself?** Yes means native lighting/shadows but work inside the host
   renderer's timing and state. No means a pasted picture with image-estimated lighting and stale-frame
   risks (`frame-compositing-depth-and-pose-sync.md`).
4. **What must every player own and run, and on which OS?** Record exact builds from day one: some
   hosts need one exact executable version; NewVegasCraft targets Steam 1.4.0.525; the GTA V example was tested on
   Legacy build 3889. Windows hosts can run elsewhere through a translation layer, by creator report:
   LibertyCraft (GTA IV under Wine on Linux), NewVegasCraft (Proton), the [CrossOver bridges](https://github.com/justbustin/minecraft-crossover-bridge) (macOS, native
   Minecraft). Each needed platform-specific fixes; name the layer and version.

### 3. Build the first working slice for that route
| Route | First slice that proves the route | Game-specific check before adding features |
|---|---|---|
| Passthrough | host plugin logs one line; one float (player x) crosses and is logged on both sides with a frame counter | positions agree within a frame while walking; teleport/load does not desync |
| Frame compositing | a fake host renders known geometry against an exported guest frame and its recorded pose | in the real host: a debug view of host depth alone; a marker dropped at the host crosshair lines up with guest pixels |
| Geometry transfer | one guest cube drawn by the host renderer at a known position | it is occluded by a host wall and lit by host light; host state restored after the draw |
| Shared simulation | two viewers see the same server state | prediction corrections logged and bounded (Signet logs corrections over 5 cm) |
| Engine recreation | load one asset from the owned install and render it | round trip or byte-match oracle for that format |
| Conversion | convert one map/model and load it in the host | the converted level is completable (a Doom-in-Hytale conversion left a hidden door blocking E1M1) |
| Transplant | the mechanic runs on a greybox with no game data | in the host: the mechanic's numbers match a recorded reference scenario |
| Rebuilt engine in a host | the engine steps from a fixed contract (inputs in, pose out) against a fake host | in the host: mount, ride, dismount and a crash/stall of the guest each behave as the contract says |

Don't advertise a universal adapter. Every bridge needed per-host reverse engineering (camera,
safe game-thread entry, collision queries, actors, health, display and input ownership), even when two
bridges shared one creator, magic number and layout.

## Gotchas
1. **A "passthrough" that is really an overlay.** **Symptom:** blocks float over host walls or ignore host
   light. **Cause:** a frame overlay without depth, or a separate window ([Garry's Redemption](https://github.com/codeByAlexff/garrys-redemption) ships an overlay
   window above RDR2 that can't do exclusive fullscreen, though its design document planned in-frame
   compositing). **Fix:** decide compositing vs geometry transfer explicitly (see
   `frame-compositing-depth-and-pose-sync.md` and `geometry-transfer-host-draws-guest-meshes.md`), and check
   release notes, not the design doc, before listing a feature.
2. **Mixing up route vocabulary between projects.** **Symptom:** an agent ports a technique that cannot work
   in the chosen route (e.g. native shadows on a pasted image). **Cause:** "passthrough" is used for three
   different routes. **Fix:** name the route in `MODLOG.md` and in the field note's `route:` and tags.
3. **Running the whole second game for one mechanic.** **Cause:** defaulting to passthrough. **Fix:** a
   transplant (Faith Runner needs only box sweeps and overlap queries from its host) or pattern 5 is often
   smaller and less fragile. For a full mechanic set (skating), a rebuilt engine in the host is the
   pattern; see `rebuilt-guest-engine-inside-a-host.md`.
4. **Treating shared rules as the original games.** **Cause:** a neutral simulation runs its own physics.
   **Fix:** list per viewer what is native (appearance) and what is shared (movement, hits).
5. **Assuming one bridge fits a second host.** The CrossOver bridges keep the same control magic/version but
   differ in header size, regions, units and damage meaning. **Fix:** version the protocol per host and keep
   adapters in separate folders.
6. **"Same language" assumed to mean composable.** **Cause:** two Rust/Bevy engines still disagree on
   coordinates, entity IDs, physics, input, animation and saves. CS:Craft's plan to "stitch" with IW4L
   (shared content IDs, per-game weapon behaviour, a common trace interface) is still a design.
   **Fix:** list each seam explicitly before promising a merge (see
   `engine-recreation-measures-and-fidelity.md`).

## Verification
Per-project versions are in
`skills/mashup-mods/references/mashup-cases.md`. Creator
statements are reports. Re-check each project's current README before relying on a version.
