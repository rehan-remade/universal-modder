# Mashup cases: routes, versions and ownership

A compact index of mashup projects. Use it to find the closest prior project before choosing a route.
Versions are the ones the projects named; check current releases. Creator claims are reports.

| Project | Route | Host / guest and versions | Player owner | Units | Transport |
|---|---|---|---|---|---|
| [SkyCraft](https://github.com/chasmlol/SkyCraft) 0.1.2 | passthrough + geometry transfer | Skyrim (SKSE, D3D11; AE path preferred) / Minecraft Fabric | Minecraft; Skyrim for furniture, mounts, kill-moves | 70 Skyrim units per block | named shared memory: snapshots, rings, actor tables, triple-buffered overlay |
| [LibertyCraft](https://github.com/mrborghini/libertycraft) | passthrough + geometry transfer (fork of SkyCraft) | GTA IV (a community scripting SDK, D3D9) under Wine on Linux / the forked Fabric mod | Minecraft; GTA for missions, cutscenes, cars | 1 m per block | SkyCraft v11 layout, new magic; seqlocks, bounded queues, byte rings, triple buffers; Windows/POSIX split |
| [ValCraft](https://github.com/LoAlCo/ValCraft) | passthrough | Valheim (BepInEx) / hidden Minecraft Fabric | Minecraft simulates the player | — | shared memory |
| [Killcraft](https://github.com/goonsn/Killcraft) | passthrough (SkyCraft's guest mod) | ULTRAKILL / hidden Minecraft running SkyCraft's Fabric mod | Minecraft (movement, health, inventory, combat) | 2 host units per block | — |
| [FalloutCraft](https://github.com/zeyvu/FalloutCraft) | passthrough (SkyCraft lineage) | Fallout 4 1.11.240, F4SE 0.7.9 / Minecraft 26.3 Fabric | — | — | — |
| Minecraft × GTA V (`examples/minecraft-gta5-passthrough`) | frame compositing + state | GTA V Legacy build 3889, ScriptHookV 3889.0, ReShade 6.8.0 / Minecraft 26.3 Fabric (author's test, Sept 2026) | GTA on foot; Minecraft in elytra flight | 1 m = 1 block; (x, y, z) → (x, z + yOffset, −y) | WebSocket 127.0.0.1 for gameplay; named shared memory for colour/depth/HUD |
| Wither Storm × GTA V | frame compositing + state (built from the GTA V example) | GTA V Legacy / Minecraft Java 1.20.1 with a large boss mod | — | 1 m = 1 block | the GTA V example's transport |
| [CrossOver bridge](https://github.com/justbustin/minecraft-crossover-bridge): Monster Hunter: World | frame compositing + state | MHW 15.23.00 (build 421810), CrossOver with a Direct3D-on-Metal layer, D3D11 / Minecraft 1.21.1 Fabric on native macOS | Minecraft drives movement and camera | damage = native HP | file-backed shared memory (8 MiB control + frame mapping) |
| CrossOver bridge: Elden Ring | frame compositing + state | ER app 1.17.1 (exe 2.7.1.0), CrossOver D3DMetal/D3D12 / Minecraft 1.21.1 Fabric | Minecraft drives movement and camera | damage = MC damage scaled by target max HP | as above, frame layout v2 with separate hand layer |
| [NewVegasCraft](https://github.com/Davozh/new-vegascraft) | frame compositing + state | Fallout: New Vegas Steam 1.4.0.525, xNVSE, ReShade (Proton setup) / Minecraft | Minecraft | 70 host units per block; exterior yOffset −34 | WebSocket + mapped file |
| [Minecraft × Half-Life](https://github.com/SawyerTheNerd/Minecraft-X-HalfLife) (GoldSrc) | geometry transfer | Half-Life client/server DLLs (OpenGL) / hidden Minecraft | Minecraft; Half-Life for ladders, use, noclip, death | 40 units per block; health ×5 | shared mapping (SkyCraft-derived name) |
| [GalaxyCraft](https://github.com/M0uidev/GalaxyCraft) | geometry transfer into an emulated game | Super Mario Galaxy 2 in Dolphin + native module / Minecraft Fabric | native Mario, or Minecraft with Mario hidden | GX display lists, KCL collision | 30,134,304-byte mapping; host LE v10, mailbox BE v5 |
| [Signet](https://github.com/kian-cx/signetprotocol) | shared neutral simulation | own server; Doom/Quake-style viewers are reimplementations; Minecraft via official-server gateway | server-authoritative, 20 Hz client prediction | neutral metres, 2.5D height grid | JSON over TCP |
| [Faith Runner](https://github.com/tnrjns/faith-runner) | subsystem transplant | Mirror's Edge movement in Rust → Skyrim (SKSE) and Minecraft (Java FFI) | the transplanted mechanic | 70 units per metre in Skyrim | static/dynamic C exports |
| ER Mario 0.3.8 | rebuilt mechanic, in-process | Elden Ring (me3) / libsm64 compiled into a Rust DLL; owner's US Mario 64 ROM for textures, audio and animations | Mario; a hidden native character follows for doors, menus, quests, deaths and saves | — | in-process C API |
| libsm64 | rebuilt mechanic as a library | any host that feeds collision and input (Garry's Mod, ER Mario) / Super Mario 64 decomp | Mario's state, stepped by the host | — | C library |
| [AC1 Movement Rewritten](https://github.com/Banned445/AC1-Movement-Rewritten) | subsystem recreation | Bevy greybox; owned AC PC install for models/animations; capsule fallback | the recreation | — | — |
| Diablo II movement in DevilutionX | subsystem transplant | DevilutionX (Diablo I) | Diablo I systems underneath | 256/8 fine units per tick at 20 ticks/s (v0.2) | in-process |
| [Garry's Redemption](https://github.com/codeByAlexff/garrys-redemption) | frame overlay window + state | RDR2 / hidden Garry's Mod | GMod for sandbox and player physics (design) | 0.01905 m per Source unit | versioned shared memory per direction |
| [BullySkate](https://github.com/Faiqie/BullySkate) | rebuilt guest subsystems in workers | Bully (ASI + scripting) / Skate physics and audio workers | the worker while skating | — | event-driven worker contracts |
| [IW4L](https://github.com/vladtrc/iw4L) 0.1.0-demo.2 | engine recreation | MW2 assets from the owned install / Rust, Bevy, wgpu; D3D9 shaders translated toward WGSL | the recreation (authoritative state, client prediction, snapshots) | — | one process |
| [benilla](https://github.com/samwhosung/benilla) | engine recreation | WoW 1.12.1 (build 5875) data / Rust, Bevy; extension point for extra Bevy plugins | the recreation | — | one process |
| [SK8-ENGINE](https://github.com/SK8-ENGINE/skate-3-rust-engine) | engine recreation (base of BullySkate, SkateGM, World of Skatecraft, the 2010 mashup) | owner's Skate 3 Xbox 360 data / Rust, Bevy; Lua SDK owns game policy | the recreation | — | one process |
| [HL2-RS](https://github.com/kvalls/hl2-rs) | engine recreation (standalone) | Half-Life 2 Source assets / Rust | the recreation | Source units converted at load | one process |
| CS:Craft | engine recreation + added Minecraft mode | CS:GO formats in Rust/Bevy, fixed 64 Hz simulation | the recreation | Source (x, y, z) → Bevy (x, z, −y), inches kept | one process; [IW4L](https://github.com/vladtrc/iw4L) "stitching" is a design |
| [World of Skatecraft](https://github.com/Kimmo3223/world-of-skatecraft) | rebuilt Skate engine inside a recreated host | [benilla](https://github.com/samwhosung/benilla) (recreated WoW 1.12.1 client, build 5875 data) + patched private-server core on Linux | the Skate engine while skating | — | in-process via extension entry point |
| [SkateGM](https://github.com/the-schwilliam/SkateGM) | rebuilt Skate engine inside a host | Garry's Mod / rebuilt Skate engine, owner Xbox 360 data | the Skate engine while skating | — | in-process native module + Lua |
| [Halo / MW2 Director](https://github.com/0xburn/halo-mw2-director) | engine recreation + map import + authored cinematic | IW4L (Rust MW2 runtime) on macOS Metal / owned Halo CE assets | IW4L (MW2 movement and rules) | — | one process |
| PipeLink | installer + converters around GTA SA × Skate × MW2 | GTA SA 1.0 US / Skate engine, IW4L | — | GTA Z-up → Skate Y-up | — |
| [Touhou HFR](https://github.com/vittorioromeo/th12_hfr) (adjacent: timing/render mod, not a mashup) | native timing and graphics patch | Touhou executables (TH08–TH20 targets by version) and New Classic | the original game | 60 Hz native vs substeps | proxy DLLs |
| [2010 Rust Rewrite Mashup](https://github.com/chasmlol/2010-rust-rewrite-mashup) | engine recreation + fusion | IW4L-derived runtime + Minecraft reimplementation | one runtime | 36 host units per block | one process |

## Using a row
1. Open the closest row's own repository and read its current README and design doc.
2. Copy its ownership and unit decisions into your `docs/CONTRACT.md`
   (`knowledge/techniques/bridge-contracts-ownership-units-and-lifecycle.md`).
3. Note its known limits as your first test cases.
4. Never cite a row as proof that something works in game.
