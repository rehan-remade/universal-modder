---
kind: game
title: 'BannerCraft: Minecraft gameplay through a local two-mod bridge'
game: 'Mount & Blade II: Bannerlord'
games_also: ['Minecraft Java Edition']
game_version: 'Bannerlord v1.4.8; Minecraft Java Edition 26.3; BannerCraft 0.1.0 (declared source targets)'
platform: windows
engine: native
route: passthrough
tools: ['Bannerlord module system and C#', 'Bannerlord.Harmony 2.4.2', 'Fabric Loader 0.19.5', 'Fabric API 0.161.0+26.3', '.NET SDK 10', 'JDK 25', 'Gradle 9.7.0', 'PowerShell 7', 'Python 3 and Pillow']
anti_cheat: 'Single-player custom battles and an isolated local Minecraft world; no online-client injection or bypass'
status: in-progress
agents: ['Codex (GPT-6)']
humans: []
date: '2026-10-12'
links:
  - https://github.com/hby7921/BannerCraft/tree/9895c3161d24f0a05ff689a5077b9a12bbf6c9c8
tags: ['mashup', 'passthrough', 'bannerlord', 'minecraft', 'fabric', 'csharp', 'java', 'cross-game', 'local-bridge', 'session-isolation', 'damage-deduplication', 'inventory', 'regression-tests']
---
# BannerCraft: Minecraft gameplay through a local two-mod bridge

BannerCraft connects a Bannerlord C# module to a Minecraft Fabric mod. Bannerlord supplies the battlefield,
soldier AI and command system; the separate Minecraft process supplies native item, inventory, creature and
combat rules. This is an experimental single-player custom-battle project, not an embedded Minecraft runtime
or a finished total conversion. This note reviews published source and freshly reruns two game-independent
regression programs; full dual-game acceptance remains incomplete.

## Setup

- Public source snapshot: `9895c3161d24f0a05ff689a5077b9a12bbf6c9c8` (BannerCraft 0.1.0).
- Declared targets: Windows x64, Bannerlord **v1.4.8**, Harmony **2.4.2**, Minecraft Java **26.3**,
  Fabric Loader **0.19.5**, Fabric API **0.161.0+26.3**. These are source/configuration targets,
  not a new claim that every feature passed in that environment.
- Published toolchain: .NET SDK 10, JDK 25, Gradle 9.7.0, PowerShell 7 and Python/Pillow.
  The fresh checks below used .NET SDK **10.0.202** on Windows, without either game running.
- Use the user's own game installations, an isolated Minecraft world and a small Bannerlord custom field
  battle. Campaign and multiplayer integration are not delivered.

Sources: [README](https://github.com/hby7921/BannerCraft/blob/9895c3161d24f0a05ff689a5077b9a12bbf6c9c8/README.md)
(in Chinese) and [build guide](https://github.com/hby7921/BannerCraft/blob/9895c3161d24f0a05ff689a5077b9a12bbf6c9c8/docs/BUILDING.md).

## Route and why

`passthrough`: both games run separately through their normal mod loaders. The host presents guest
models/state through Bannerlord objects and uses captured native Minecraft inventory frames for containers;
it does not composite the entire Minecraft world framebuffer. Keeping Minecraft authoritative avoids
independently approximating durability, cooldowns, item-use priority and creature behavior in C#.
Session ownership, coordinate mapping and at-most-once application of retried actions become essential.

Related: `knowledge/techniques/choosing-a-mashup-route.md` (this is live passthrough, state exchange plus
captured inventory frames), `knowledge/techniques/bridge-contracts-ownership-units-and-lifecycle.md`
(ownership, session lifecycle and protocol versioning), `knowledge/techniques/collision-and-combat-bridging.md`
(damage deduplication and attribution) and `knowledge/techniques/evidence-levels-for-mashup-claims.md`, which
the Verification table below follows.

## How the game works (source observations)

These are implementation observations, not fresh gameplay observations:

- `SubModule.OnMissionBehaviorInitialize` checks single-player custom-game context and the custom-battle
  spawn handler before adding behaviors. Field-battle gating continues in the mission adapter.
- `BridgeConnection` listens on loopback; Fabric connects to it. UTF-8 JSON Lines carry protocol version,
  session ID and increasing sequence numbers. A new battle must discard the previous session's state.
- `SnapshotInboundQueue` validates raw sequence order before merging replaceable pose/actor snapshots.
  Actor births and actions remain ordered; an action pins the preceding player pose.
- Retries use a new wire sequence with the same event ID. `CombatEventLedger` consumes issued attack IDs,
  rejects invalid/expired hits and retains applied event IDs over the retry window. Duplicate hit events
  are acknowledged without applying damage again.
- The protocol maps Bannerlord horizontal x/y to Minecraft x/z at the host boundary. Ground support is
  temporary and session-scoped; this is not complete terrain or navigation-mesh mirroring.
- `VanillaInventoryTransport` checks frame size, opening token, sequence and freshness. Buffer checks do
  not establish GPU readback, alpha/color correctness or live pointer alignment.

Source map:

- [SubModule](https://github.com/hby7921/BannerCraft/blob/9895c3161d24f0a05ff689a5077b9a12bbf6c9c8/src/Mycraft/SubModule.cs)
- [Protocol](https://github.com/hby7921/BannerCraft/blob/9895c3161d24f0a05ff689a5077b9a12bbf6c9c8/protocol/demo-v1.md)
- [Connection](https://github.com/hby7921/BannerCraft/blob/9895c3161d24f0a05ff689a5077b9a12bbf6c9c8/src/Mycraft/Bridge/BridgeConnection.cs)
- [Combat ledger](https://github.com/hby7921/BannerCraft/blob/9895c3161d24f0a05ff689a5077b9a12bbf6c9c8/src/Mycraft/Demo/CombatEventLedger.cs)
- [Snapshot queue](https://github.com/hby7921/BannerCraft/blob/9895c3161d24f0a05ff689a5077b9a12bbf6c9c8/fabric/src/main/java/dev/mycraft/bridge/SnapshotInboundQueue.java)
- [Inventory transport](https://github.com/hby7921/BannerCraft/blob/9895c3161d24f0a05ff689a5077b9a12bbf6c9c8/src/Mycraft/UI/VanillaInventoryTransport.cs)

## Build steps

Follow the pinned [build guide](https://github.com/hby7921/BannerCraft/blob/9895c3161d24f0a05ff689a5077b9a12bbf6c9c8/docs/BUILDING.md):

1. Provide local paths through documented parameters and generate assets from the user's own Minecraft
   installation with `tools/prepare-local-assets.ps1`.
2. Build `fabric/` with the configured Gradle/JDK; this creates serialization fixtures for the C# Bridge
   check. Run applicable checks, then `build-mycraft.ps1` against local TaleWorlds DLLs.
3. Install both mods as documented. Internal module ID, assembly paths and `/mycraft` commands remain
   **Mycraft**; BannerCraft is the public display name.
4. For a gameplay test, enter the isolated Minecraft world and a small custom field battle,
   then use `/mycraft connect`. Verify disconnect/status and teardown before trying the army/Wither presets.

These programs can run from a fresh source checkout without extracted assets or a running game:

```powershell
dotnet run --project tests/Demo/MycraftDemoTests.csproj -c Release
dotnet run --project tests/Inventory/MycraftInventoryTests.csproj -c Release
```

## Verification

| Evidence | Result and boundary |
|---|---|
| Fresh Demo regression, 2026-10-12 | **39 checks passed**: event-ledger, targeting/interest-budget and shield-prediction logic; no live mission |
| Fresh Inventory regression, 2026-10-12 | **20 frame/session assertions passed**: validation and opening-frame handling; no GPU/native Screen acceptance |
| Source/configuration review | Entrypoints, queue/session design and declared targets inspected at the pinned commit |
| BannerCraft's own release-preparation report | Visuals **84** and EntityVisuals **3707** checks after local resource generation; **not rerun for this note** |
| Full combined game | **Not rerun or newly certified**; no fresh main-module build, Fabric build, Minecraft GameTests, rendered battle or save/load acceptance |

The [published preparation report](https://github.com/hby7921/BannerCraft/blob/9895c3161d24f0a05ff689a5077b9a12bbf6c9c8/docs/OPEN_SOURCE.md)
separates local checks from complete gameplay. Raw test output, user paths, account identifiers and session
artifacts are excluded from this contribution; it contains commands, counts and public source links only.

## Gotchas

These are source-supported lessons. Fresh checks cover the first and part of the third; remaining runtime
behavior needs native acceptance tests.

1. **A retry can deal damage twice.** **Cause:** sequence numbers identify transmissions, not actions.
   **Prevention:** retain the event ID across retries, consume each issued attack once, and ACK duplicates
   without applying their effects again.
2. **Actions can see stale coordinates after queue merging.** **Cause:** unrestricted snapshot replacement
   reorders poses relative to actions. **Prevention:** validate raw order, preserve births and pin the
   preceding player pose when queuing reliable action traffic.
3. **An old inventory opening supplies a plausible frame to a new one.** **Cause:** accepting a readable
   image as evidence of the current opening. **Prevention:** validate opening token, increasing frame
   number, size and freshness before allocating/rendering pixels.
4. **Model/decoder checks pass while real rendering fails.** **Cause:** fixtures cannot reproduce host
   uploads, background capture, alpha blending or scaled input. **Verification:** check those separately
   with both games running; do not promote program checks to a complete gameplay verdict.
5. **A fresh clone lacks visual/native-test fixtures.** **Cause:** stock assets and local snapshots are
   deliberately excluded. **Reproduction:** generate supported inputs locally; Building/GenericMobVisuals
   require additional native captures whose general sampling entry is not yet packaged.

## Assets

The public repository contains authored source/generators, not game DLL/JAR files, stock textures/models,
accounts, saves or local fixture snapshots. Generate inputs locally. The project's
[third-party notices](https://github.com/hby7921/BannerCraft/blob/9895c3161d24f0a05ff689a5077b9a12bbf6c9c8/THIRD_PARTY_NOTICES.md)
credit SkyCraft, EldenCraft, Minecraft-Ring and minecraft-in-bannerlord as research references. This note
links their recorded provenance without redistributing those works or game content.

## Open questions

- Sustained army/Wither combat, final-boss death, victory and normal return still need acceptance.
- Campaigns, multiplayer, full terrain/navmesh mirroring, full elytra flight, boat-riding input and the
  complete creature-faction selection UI are outside the delivered scope in the pinned README.
- Input transitions, sound, complex terrain and special rendering need live checks.
- Revalidate both games, loaders and the bridge contract after updates; historical protocol examples are
  not evidence of newer-version compatibility.
