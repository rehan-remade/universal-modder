---
kind: game
title: "An external game master on a Barotrauma server: a LuaCs C# plugin that observes, talks, moves NPCs and spawns items"
game: "Barotrauma"
games_also: []
game_version: "1.13.4.0 (game and DedicatedServer), Steam build 23799131; LuaCs 1.0.116 (Workshop 2559634234)"
platform: windows
engine: dotnet
route: loader-api
tools: ["LuaCs/Luatrauma", "C# assembly plugin (IAssemblyPlugin)", ".NET SDK 8.0.423", "Mono.Cecil", "AI NPCs (Workshop 3074046183)"]
anti_cheat: "none; only local dedicated servers the operator ran, with disposable campaigns"
status: in-progress
agents: ["Codex (GPT-6)"]
humans: ["jkjkj2805"]
date: 2026-10-13
links: ["https://github.com/evilfactory/LuaCsForBarotrauma", "https://luatrauma.github.io/Luatrauma.Docs/cs/setup-assembly-csharp/", "https://github.com/FakeFishGames/Barotrauma", "https://steamcommunity.com/sharedfiles/filedetails/?id=3074046183"]
tags: [luacs, dedicated-server, game-thread, campaign, npc, ai-objectives, entity-spawner, chat, ai-game-master]
---

# An external game master on a Barotrauma server: a LuaCs C# plugin that observes, talks, moves NPCs and spawns items

> A C# plugin loaded by LuaCs on a Barotrauma dedicated server feeds an external program (an AI game master
> called Randur) with snapshots of the campaign and the submarine, and runs a few narrow actions back in the
> game. In real runs it kept the campaign's identity through reloads and restarts, recognised a player who
> reconnected, made one NPC answer a player's targeted chat, walked one AI crewmember to a chosen room, and
> spawned one crate on a headless server. The plugin is private; this note records what the game does and the
> traps, so you can build your own.

## Setup
- Barotrauma and DedicatedServer 1.13.4.0 (Steam build 23799131) on Windows, with LuaCs 1.0.116 from the Workshop
  (item 2559634234, runtime revision `0d380afcd1`).
- A C# assembly plugin built with .NET SDK 8.0.423 against LuaCs's publicized references, following the
  [Luatrauma C# setup guide](https://luatrauma.github.io/Luatrauma.Docs/cs/setup-assembly-csharp/). Mono.Cecil
  was used to read the installed game assemblies' method bodies without running them.
- Targeted chat used a private, trimmed fork of [AI NPCs](https://steamcommunity.com/sharedfiles/filedetails/?id=3074046183)
  by RubbingMyAxe (version 1.6 in the author's records) (its syntax is `!firstname message` / `!lastname message`). The operator reports the
  author's permission for private changes; that isn't a licence to redistribute, so ask before shipping any of
  its code.
- Everything ran on servers the operator hosted, with disposable campaigns and saves. Credit: FakeFish/Undertow
  for Barotrauma, the LuaCs/Luatrauma maintainers for the loader.

## Route and why
- An `IAssemblyPlugin` on the authoritative dedicated server sees the real campaign, characters and items.
- Read game objects only on the game's update thread, serialise a bounded snapshot there, and hand only strings
  to the network worker. The worker never touches a live `Character`, `Hull`, inventory or campaign object.
- The external program talks to the plugin over its own loopback TCP connection (authenticated, one peer), not
  through the game's multiplayer transport.
- Actions are narrow, typed and off by default: say a line as a given NPC, walk a given AI crewmember to a given
  room, place one allowlisted item in a given room. No console, reflection or arbitrary prefabs.

## How the game works (what we had to learn)

### Some "read-only" getters change the campaign
In this build, reading these getters changes state:
- `Location.AvailableMissions` removes completed, failed (unless retry is allowed) and force-failed missions
  from the location's list;
- `Location.SelectedMissions` drops selected missions that are no longer available;
- `MultiPlayerCampaign.LastSaveID`, on a server, bumps the save ID when it's below 1.

The plugin reads the backing fields instead. A matching signature in a publicized reference isn't enough: check
the method body in the installed assembly (the upstream source matches here, at the 1.13.4.0 commit of
FakeFishGames/Barotrauma).

### Identity
| Thing | What identifies it | What it doesn't tell you |
| --- | --- | --- |
| Campaign | The original save file instance, mapped to an ID the plugin keeps | That a copied save is the same world (copies keep their content and seed) |
| Player | The Steam ID the server authenticated | Their current connection or body |
| Connection | The current `Client` object | Who it is after a reconnect (a new `Client`) |
| Body | The current `CharacterInfo` and `Character` | A persistent NPC identity across rounds |
| Room, item | The exact object in the current round | Anything after a reload or a gap in observation |

Names, map seeds, save hashes and the game's numeric IDs are labels, not identities. A disconnect isn't a
death: death is the dead flag going from false to true for the same body. `Level.LevelData.IsBeaconActive` tells
you a beacon's state, not who activated it or when; level generation already sets it to true at random, so a
true value at the start of a round proves nothing.

### NPC perception
`ISpatialEntity.CheckVisibility` checks facing (when `checkFacing` is set) and occlusion with a physics raycast
(windows let sight through only when `seeThroughWindows` is set). The raycast uses static scratch state on
`Submarine`, which the plugin saved and restored around its calls. Being in the same `Hull` is only a candidate
filter, not sight. The plugin capped range at 600 units, treated windows as blocking, and checked that bodies
and colliders still existed before calling the spatial getters.

### Chat to a specific NPC
The AI NPCs mod picks the addressed NPC with the game's own eligibility and hearing checks plus first- or
last-name matching (it also accepts roles, such as `!mechanic`). Pass the exact `Client`, speaker and target
`Character` objects from Lua to C# through `ILuaCsHook.Call`/`Add` (the `Add` overloads are marked obsolete in
favour of `ILuaEventService.Add`), and don't look the target up again later by name or job. Hook the server's
chat path (`chatMessage`): a client-side message rewrite hook never sees what other players type.

### Walking an NPC with the game's own AI
Add an `AIObjectiveGoTo` through the character's `AIObjectiveManager.AddObjective` on the game thread. Normal
pathfinding, doors, ladders and hazard priorities then apply; nothing sets positions. `AddObjective` can
replace an existing objective of the same type (it removes them unless the objective allows multiple
instances, and `AIObjectiveGoTo` doesn't), so refuse when the NPC already has one or has a conflicting order.
The objective finishing, or the NPC being close, isn't arrival: in the tested walk the NPC was in the target
room while the objective's `IsCompleted` and `Abandon` were both false. (Reading `IsCompleted` also runs the
objective's `CheckState()`, so it isn't a passive read either.) Check the character's current `Hull` in a later
snapshot.

### Spawning an item
The overload used was `EntitySpawner.AddItemToSpawnQueue(ItemPrefab, Vector2 position, Submarine sub, float?
condition, int? quality, Action<Item> onSpawned)`. Positions are relative to the submarine, so pair
`Hull.Position` with that hull's `Submarine`. The game creates the item, queues the spawn network event and then
calls `onSpawned` with that exact item. That event doesn't prove a client received or rendered it.

The plugin only placed the item in a dry, fire-free room on the main submarine, at least 200 by 120 units, with
no item or body within 100 units of the centre. A room picked from a partial snapshot failed that check in the
game (its centre was obstructed), so the plugin now has the game side list the legal rooms and re-checks the
chosen one when the action runs.

### Storage paths
`SaveUtil.DefaultSaveFolder` is a static built from `Environment.GetFolderPath(LocalApplicationData)`, which
.NET resolves through Windows KnownFolder, so overriding `APPDATA` or `LOCALAPPDATA` doesn't move it. The
configured save path only changes where saves go. The Workshop mod cache (`WorkshopMods/Installed` under that
folder) is another static, and startup can write to it. To isolate a test server, check every storage root
before launching it. (The author patched two storage-root instructions in a private lab copy of the dedicated
server to relocate them; nothing in the installed game was changed.)

## Build steps
1. Pin the game, LuaCs and reference versions. Check every getter and hook you'll call in the installed
   assemblies.
2. Snapshot on the update thread into an immutable, size-capped string; hand it to the socket worker. Start with
   observation only.
3. Keep campaign, player, connection and body identity separate in every message, and drop pending actions when
   any of them changes or observation has a gap.
4. Add one action at a time, off by default. Re-check the target objects on the game thread right before acting,
   and report success only from a later snapshot (the NPC in the target `Hull`, the spawned item in the target
   room).
5. Test in disposable campaigns: progress, reload, full restart, a cloned save, a player reconnecting, and
   replaying the same action (expect one effect, not two).

## Verification
- **In the real game (2026, on the operator's own servers):** the campaign ID survived a voyage, a reload and a
  full game/server restart; a cloned save and an independent campaign got different IDs. A real client
  reconnected and was recognised as the same player with a new connection, and the old connection and body
  references were rejected. One targeted chat message got a reply from the right NPC (the human confirmed it). One
  AI crewmember walked to a chosen room through `AIObjectiveGoTo`; arrival was confirmed from a later snapshot
  (no human watched the walk). On a headless isolated server one empty `metalcrate` was spawned through the
  spawn queue, seen in three later snapshots, and replaying the command didn't spawn a second.
- **Offline tests:** stale or cross-world messages, old connections and forged receipts are rejected; the
  socket worker recovers from a dropped connection while the game is idle.
- **Not verified:** that a client sees the spawned item; listen/P2P servers and EOS accounts; long outages;
  other mod combinations; current builds (nothing was re-run for this note).

## Gotchas
1. **Reading the campaign changes it.** **Cause:** some getters (above) prune mission lists or bump the save ID.
   **Fix:** read the backing fields, and check method bodies in the installed assemblies.
2. **Targeted chat never reaches the plugin.** **Cause:** a client-side rewrite hook was mistaken for the server
   path that receives multiplayer chat. **Fix:** trace the server's `chatMessage` path and confirm the message and
   target arrive before generating a reply.
3. **An order silently replaces the NPC's normal work.** **Cause:** `AddObjective` replaces a same-type
   objective. **Fix:** refuse when there's a conflicting objective or order.
4. **A walk is reported as done when the NPC isn't there.** **Cause:** objective creation, completion or distance
   was used as the check. **Fix:** require the same character in the target `Hull` in a later snapshot.
5. **A lost acknowledgement causes a second walk.** **Cause:** a generic transport retry resent a command that
   can't be undone. **Fix:** give each action a durable ID, suppress replays, and don't retry automatically when
   the outcome is uncertain.
6. **A reconnect reuses an old target.** **Cause:** the same player was taken to mean the same connection and
   body. **Fix:** re-check the current `Client` and `Character` after every reconnect.
7. **A copied save inherits another world's history.** **Cause:** the world was identified by name, seed or
   content hash. **Fix:** treat a copied save file as a new world.
8. **A private save path still touches the real Workshop cache.** **Cause:** the default save folder and the
   Workshop cache come from KnownFolder regardless of the configured path. **Fix:** check every storage root before launching a test server.
9. **The socket worker never notices a dropped connection while the game is quiet.** **Cause:** it blocked on
   an unbounded wait for the next snapshot. **Fix:** bound that wait, and require a fresh full snapshot before
   resuming.

## Assets
None. The item was a vanilla prefab from the operator's install. No game files, prefab XML, plugin source or
campaign data are included.

## Open questions
- Whether a client sees and can pick up an item spawned this way.
- Whether the NPC's identity can be followed across rounds and reloads.
- The plugin and the AI NPCs fork are private; a public minimal version would let others re-run these checks.
