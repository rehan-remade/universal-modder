---
kind: game
title: 'Build 42 multiplayer for modders: commands, transmit and sync verbs, ownership, server anti-cheat, the packet layer and the population manager'
game: Project Zomboid
games_also: []
game_version: 'Build 42.21.0 (Steam, Windows 10). A survey: javap listings of zombie.network and zombie.popman, the install''s Lua and other mods'' files; no server was run for this note'
platform: windows
engine: java
route: loader-api
tools: ["javap (JDK)", "zombie.network / zombie.popman packages", "vanilla ServerCommands.lua", "dedicated server (Steam app 380870)"]
anti_cheat: 'B42 dedicated servers run server-side checks (zombie.network.anticheats, switched by the ServerOptions antiCheat* settings); this note is about servers you host, and a mod that changes state on a client can trip them'
status: in-progress
agents:
- Devin (SWE-2 Medium)
humans: [Alistair-Afton]
date: '2026-10-12'
links:
- "https://pzwiki.net/wiki/Networking"
- "https://albion.codeberg.page/PZ-JavaDocs/"
tags: [b42, multiplayer, server, dedicated-server, co-op, networking, commands, sync, ownership, moddata, anti-cheat, packets, popman]
---
# Build 42 multiplayer for modders: commands, sync verbs, ownership, anti-cheat and the packet layer

> Since 42.13 the B42 server is authoritative, so most "works solo, breaks in MP" bugs are sync-model bugs. This
> note gives the rules a mod has to follow (where code runs, how state crosses the wire, who owns an object, what
> the server's anti-cheat watches) and maps `zombie.network` and `zombie.popman` behind them. It's a survey of
> javap listings, the install's Lua and other mods' files; no server was run for it. Single-player basics are in
> the [orientation note](b42-modding-orientation-layout-lua-runtime-tooling-interop-ui.md); a modded B41
> dedicated server (`Mods=`, `WorkshopItems=`, `Map=`, checksums) is in the
> [B41 note](b41-modpack-fix-mods-and-linux-dedicated-server.md).

## Setup
- Project Zomboid **42.21.0**, Steam, Windows 10; the dedicated server is Steam app 380870. Multiplayer returned to
  B42 in 42.13 (December 2025).
- Vanilla references: `media/lua/client/ServerCommands.lua` and the server-side command tables, plus Cry of Fear
  Monsters' network split (creatures note).

## Route and why
Loader API. The network layer is Java, but mods reach it through Lua commands and the engine's `transmit*`/`sync*`
verbs; mods can't add packet types.

## How the game works (what we had to learn)

### Where code runs
- `shared/` runs everywhere; `client/` on single player and MP clients; `server/` on single player and the server.
  A dedicated server never runs `client/` (no UI, no renderer), and an MP client never runs `server/`.
- Change world state on the server (`server/` files, or shared code behind `isServer()`); keep presentation (UI,
  sounds, particles, animation variables a client reads locally) on clients.

### Commands: the mod-level wire
- **Client to server:** `sendClientCommand(module, command, args)` (Lua global; Java `GameClient`). The server
  receives it with `Events.OnClientCommand.Add(function(module, command, player, args) ... end)`.
- **Server to client:** `sendServerCommand(module, command, args)` to everyone or
  `sendServerCommand(player, module, command, args)` to one player (Java `GameServer`). Clients receive it on
  `Events.OnServerCommand`.
- `args` must be plain data (numbers, strings, booleans, nested plain tables). Send `getOnlineID()` or coordinates
  and look objects up again on the other side.
- **Global mod data:** `ModData.transmit(key)` sends a table, `ModData.request(key)` asks the server for it, and
  `Events.OnReceiveGlobalModData` receives it (the table can be `false` in a reply to a request). Keep authoritative
  data on the server; a client's copy isn't kept across reconnects.

### Transmit and sync verbs: the engine-level wire
- Squares: `sq:transmitAddObjectToSquare(obj)`, `sq:transmitRemoveItemFromSquare(obj)`, `sq:transmitModdata()`.
- Objects: `obj:transmitModData()` (capital D on `IsoObject`), `obj:sync()`, `syncIsoObject`, the fluid-container
  sync. Also `transmitPlayerVoiceSound`, and `getWorld():transmitWeather()` after a server-side weather change.
- A plain setter on the server changes the server's world silently; clients don't see it. Damage applied on the
  server should be followed by a `sendServerCommand` for the presentation (the Cry of Fear pattern).

### Ownership and remote objects
- `isRemoteZombie()`, `getOwnerPlayer()`, `getOwner()` and `getOnlineID()` say who drives a zombie. A remote zombie
  is a view of another client's simulation: changing it locally ghosts the state. Bandits only lets the owning
  client steer (`BanditUtils.IsController`).
- `zombie.popman` is the population layer behind this: `ZombiePopulationManager`, `NetworkZombieManager`,
  `NetworkZombieSimulator`, `NetworkZombiePacker`, `ZombieCountOptimiser`, `Ownership`, `LoadedAreas`, and
  `popman.animal.AnimalController`. It's Java-internal; mods reach it through `VirtualZombieManager` and the
  population sandbox settings. A zombie you see may be simulated by another client, so identity must live on the
  object itself (a persistent outfit), never in a client-side table.

### Server anti-cheat
`zombie.network.anticheats` has about 20 check classes (`AntiCheatSpeed`, `AntiCheatNoClip`,
`AntiCheatHitDamage`, `AntiCheatHitLongDistance`, `AntiCheatXPUpdate`, `AntiCheatSafeHouseMember`, ...) plus
`PacketValidator` and `SuspiciousActivity`, and `ServerOptions` has matching switches (`antiCheatSpeed`,
`antiCheatNoClip`, `antiCheatHit`, `antiCheatXp`, `antiCheatChecksum`, `antiCheatSafeHouse`, ...). A mod that
moves players, deals damage or grants XP on a client instead of the server can trip them. `ChunkChecksum`
compares client and server chunks, and `AddWarningPointPacket` exists: client-side world edits look like cheating.

### The packet layer (`zombie.network`)
- `GameServer` and `GameClient` are the two endpoints; `ServerOptions`/`ServerSettings`;
  `GameServerWorkshopItems` syncs Workshop items to clients.
- `zombie.network.packets` has one class per action (272 public types in the 42.21 javadocs, 112 in the top
  package; the jar holds 296 `.class` files counting inner classes): `AddItemToMapPacket`,
  `AddExplosiveTrapPacket`, `AddXPMultiplierPacket`, `BodyDamageUpdatePacket`, `AddWarningPointPacket` ... A mod
  doesn't create packets; it calls the API whose packet already exists, or uses commands.
- Hosting from the game client runs an in-process server (`CoopMaster`/`CoopSlave`). Chunk sync and integrity:
  `ClientChunkRequest`, `ChunkChecksum`, `ClientServerMap`. Other classes in the package: `FakeClientManager`
  (fake clients for load tests), `BodyDamageSync`, `BanSystem`, and `DiscordBot`/`DiscordSender` (server messages to
  Discord); none of these were tried.

## Build steps
1. Spawn creatures and change the world only on the server (`createRealZombieNow`, `addAnimal`, object adds); never
   on a client, or you get duplicates or phantoms.
2. Brains that change damage, aggro or spawns run on the server; clients present (sounds, particles, the animation
   variables their AnimSets read).
3. Identity crosses the wire once: the server says "this zombie is monster X", each client sets its variables and
   visuals locally (Cry of Fear's remote presentation). Don't push Lua state every tick.
4. Use commands for your own messages and the `transmit*`/`sync*` verbs for stock object changes.
5. Test with co-op hosting from the client plus a second client, or the dedicated server on the same machine; read
   `console.txt` on each side.

## Verification
- Survey only. Class names from javap listings of 42.21.0, checked at review time against the unofficial 42.21.0
  javadocs (public types only); the command directions and Lua signatures from `LuaManager.GlobalObject`,
  `GameClient` and `GameServer` there. The patterns from reading Cry of Fear Monsters and Bandits.
- Not verified: anything on a running server, `FakeClientManager` or `DiscordBot` use from a mod, Workshop sync
  edge cases, B42 dedicated-server start flags.

## Gotchas
1. **"Module not found" only on a server.** Cause: a table the server needs lives in `client/` (or the reverse).
   Fix: shared tables in `shared/`.
2. **A spawn works in single player and does nothing (or duplicates) in MP.** Cause: client-side spawning. Fix:
   spawn on the server.
3. **A command's arguments arrive empty.** Cause: Java objects, functions or userdata in `args`. Fix: plain data.
4. **A remote zombie ignores your changes or flickers.** Cause: `isRemoteZombie()` is true; another client owns it.
   Fix: change it through the owner or the server.
5. **Square ModData syncs but object ModData doesn't.** Cause: `IsoGridSquare.transmitModdata` covers the square.
   Fix: `IsoObject.transmitModData()`, `obj:sync()` or your own command.
6. **Players get flagged or kicked after a mod action.** Cause: B42's server anti-cheat (`zombie.network.anticheats`,
   `ServerOptions` `antiCheat*`) saw a client-side move, hit or XP change, or chunks diverged. Fix: do it on the
   server.
7. **Client code silently does nothing on a dedicated server.** Cause: `client/` isn't loaded there. Fix: log once
   from `shared/` with `isServer()`/`isClient()` so you know where each file ran.
8. **The server errors in UI or render code.** Cause: a dedicated server has no renderer. Fix: keep that code in
   `client/`.
9. **Weather or thunder differs between players.** Cause: changed on one side. Fix: change it on the server and
   `transmitWeather()`; thunder events are written by the server and read by clients.

## Assets
None.

## Cost and time
Part of one research session on 2026-10-12.

## Open questions
- Whether anything lets a mod register its own packet type (almost certainly not from Lua).
- B42 dedicated-server start flags for headless testing, and how B42 Workshop sync differs from the B41 note.
- Whether animals are virtualised like zombies (`popman.animal.AnimalController`).
