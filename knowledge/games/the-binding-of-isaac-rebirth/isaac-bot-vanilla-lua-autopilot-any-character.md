---
kind: game
title: 'Isaac Bot: a vanilla-Lua autopilot that plays Repentance+ runs with any character'
game: 'The Binding of Isaac: Rebirth'
games_also: []
game_version: 'Repentance+ v1.9.7.17.J460 (Steam 250900)'
platform: windows
engine: native
route: loader-api
tools: [um win shot, um win drive, um backup]
anti_cheat: 'none; offline single-player runs only (never Daily Runs or online)'
status: working
agents:
- Claude Code (claude-opus-5-5)
humans: [netlesha]
date: '2026-10-15'
links: ['https://github.com/netlesha/isaac-bot']
tags: [bot, autopilot, ai-player, lua, input-injection, pathfinding]
---
# Isaac Bot: a vanilla-Lua autopilot that plays Repentance+ runs with any character

A vanilla Isaac Lua mod (no REPENTOGON, no exe patching, no OS-level input) that plays whole runs on its own:
it clears rooms, dodges, picks up items and pickups, routes the floor map and takes the exit toward a chosen
ending, for any character. Verified in the real game: runs as The Lost, Isaac and Azazel reached Depths I /
Caves I with item pickups, boss kills and auto-restart after death, checked in screenshots and `log.txt`.

## Setup
- Repentance+ v1.9.7.17.J460, Steam, Windows 11. `EnableMods=1` in `options.ini`.
- Mod folder `<install>/mods/isaac_bot` is an NTFS symlink to the working copy, so edits go live with the
  console command `luamod isaac_bot`.
- Saves backed up first (`um backup create` on the Steam userdata and My Games folders).
- **Offline single-player runs only.** Never run the bot in a Daily Run (they have a global leaderboard) or online.
  The game won't start a Daily Run while mods or the debug console are active (wiki.gg, Daily Challenge page);
  after the day's Daily it allows mods on practice runs, so keep the bot off those too. Players report that
  Repentance+ online play can't be entered with mods enabled; don't pair the bot with third-party patches that
  allow modded online play.
- **It plays on your save.** Mods don't disable achievements once Mom has been beaten on the save file (IsaacDocs
  modding FAQ), so the bot's unseeded runs count toward unlocks, Steam achievements and statistics. Runs with an
  entered seed (`seed`, the bench) can't earn achievements (wiki.gg, Seeds page). Use a spare save slot if that
  matters.

## Route and why
`loader-api`: the game's own Lua API. `MC_INPUT_ACTION` answers movement, shooting, bomb and active-item
buttons (ButtonAction 0-9) for the player; logic runs in `MC_POST_UPDATE` (30 Hz); a status line and an F8
settings panel draw in `MC_POST_RENDER`. Considered and rejected: OS-level key injection (fights the user's
keyboard, needs focus) and REPENTOGON (extra dependency; the vanilla API was enough).

## How the game works (what we had to learn)
- Input: `MC_INPUT_ACTION` hook 0 = pressed, 1 = triggered, 2 = value. The bot owns actions 0-9 and builds
  a fresh input table each update.
- Room grid: `Room:GetGridIndex` / `GetGridPosition`, grid width from the room shape; cost map + flood fill
  + A* per room, rocks optionally passable for bomb planning.
- Floor map: `Level:GetRooms()` descriptors; `desc.Data.Doors` is the mask of door slots the layout
  *allows*, not the doors that exist (see gotchas).
- Weapons: `EntityPlayer:HasWeaponType(WeaponType.*)` picks a firing style (tears / charge / melee /
  steered Ludovico & Epic Fetus). `MaxFireDelay` drives charge time.
- The debug console runs `lua <code>` in the mod environment and pauses the game while open.

## Build steps
1. Put the mod in `<install>/mods/isaac_bot` (copy or symlink), enable mods, start a run.
2. Test bridge: the mod polls `isaacbot_bridge/cmd.lua` every 15 render frames via `include`; a script
   writes `ISAACBOT_BRIDGE = {id = N, cmds = {...}}` and the mod runs each new id once (console commands
   through `Isaac.ExecuteCommand`, including `luamod isaac_bot` for hot reload and `restart <PlayerType>`).
3. Telemetry: one JSON `EV {...}` line per event via `Isaac.DebugString` into `log.txt`; a small script
   summarises runs, deaths (with the damage source type), stuck events and items.

## Verification
- Oracle: `log.txt` EV lines + `um win shot` screenshots read at 0.5 scale, plus live state dumps through
  the bridge (`lua ... Isaac.DebugString(...)`).
- Seen working: multi-floor runs as The Lost (Basement II → Depths I, 15 items), Azazel (Cellar I → Caves
  I, Brimstone charge learned at ~35 updates), restart after death, hot reload mid-run.
- Not verified: a full run to Mom's Heart / It Lives and later bosses; Jacob & Esau, T.Forgotten, T.Cain
  crafting (not handled).

## Gotchas
1. **Bot stands still in an open doorway.** **Cause:** during door transitions the game polls movement with
   `entity == nil`; a hook that only answers for the player entity returns nothing. **Fix:** answer
   nil-entity queries for the owned actions too.
2. **Routing to rooms that are not connected.** **Cause:** `RoomDescriptor.Data.Doors` lists slots the
   layout allows (every 1x1 room reports 15). **Fix:** keep an edge only if both neighbours allow it
   (mutual), and add the current room's real doors from `Room:GetDoor` as ground truth.
3. **`include()` of the bridge file gave nothing usable.** **Fix:** have the file set a global
   (`ISAACBOT_BRIDGE = {...}`) and read that; clear `package.loaded[...]` before each include so it re-reads.
4. **`Isaac.RenderText` text was not visible.** **Fix:** `Font()` loaded from `font/luaminioutlined.fnt`,
   `DrawString` at `Isaac.GetScreenHeight() - 34`.
5. **Fireplaces treated as unbreakable enemies.** **Cause:** a fireplace is an NPC with contact damage,
   so it woke the dodge simulation and counted as a wall forever. Put out, it keeps existing with
   `CollisionDamage` 1.0, but `HitPoints` drops 5 -> 1, `EntityCollisionClass` 4 -> 0, `State` 1 -> 3.
   **Fix:** "lit" = `HitPoints > 1` (white variant 4 cannot be put out); only lit ones block the grid and
   count as static contact hazards (no dodge simulation); a lit one on the path to a pickup or door is
   shot out first. Also: when the wanted move is itself safe, take it before scoring alternatives.
6. **Ping-pong between two rooms.** **Cause:** the goal (the bedroom, RoomType 18) sits behind a door that
   stays locked with keys; BFS doors of equal distance alternated. **Fix:** only take a door that strictly
   shortens the distance; a door still locked on arrival marks its room unreachable for the floor.
7. **Deaths to Monstro and Gish while "holding".** **Cause:** jumping bosses fail `IsVulnerableEnemy` and
   have `ENTCOLL_NONE` in the air, so they were neither targets nor dodge bodies; the bot walked to the room
   centre and was landed on. **Fix:** treat untouchable bosses as danger zones at their projected landing
   spot and move to the reachable cell farthest from them.
8. **Charge weapons (Brimstone) hardly fired.** **Cause:** the release check looked for a player laser by
   `SpawnerEntity` + `FrameCount <= 4` and never matched, so the learned hold time ran to its cap (5 s).
   **Fix:** snapshot player attacks by `InitSeed` (matching `SpawnerType` or `Parent`) at release and look
   for a new one over the next 10 updates; learn per weapon, keep the longest failed hold as a floor,
   rescale with `MaxFireDelay`.
9. **Stuck forever next to a closed Host.** **Cause:** a closed Host is invulnerable with 0 contact damage,
   so it was ignored; the blind "sweep" fire turned direction every 20 updates, which with a charge weapon
   just kept charging and never released. **Fix:** fight shut enemies like visible ones (line up, fire),
   and make the sweep finish each charge before turning.
10. **Callbacks before the first update.** `MC_POST_NEW_ROOM` / `MC_POST_GAME_STARTED` can fire before the
   first `MC_POST_UPDATE`; module upvalues must be bound at load time or you get nil-index errors.
11. **Start character lost on `luamod`.** Module state resets on reload; fall back to the player type on
   screen when choosing the next character.
12. **Brimstone fired into empty rooms.** Releasing the charge when a room cleared wasted a shot and
   restarted a 1 s charge on arrival. Keep holding the fire button between fights instead, and do not
   learn from a failed release right after a room change.
13. **Brimstone beams cut short.** **Cause:** pressing fire while the beam is on cancels it and starts a new
   charge; the bot pressed again 3 updates after release, and also dropped input on room-entry frames, so
   a held charge fired and was cut at 2 frames. Azazel's beam lives 8 updates (`EntityLaser.Timeout`
   7 -> 0). **Fix:** keep the button up while a new player laser has `Timeout > 0`; keep holding on frames
   the bot otherwise skips. Verified with a `MC_POST_LASER_UPDATE` probe: 36/36 beams full length.
14. **Frozen beside a fireplace.** A dodge simulation that walks 16 updates in a straight line overshoots
   the goal; a static contact hazard checked at every step made a firing spot next to a fireplace look
   deadly. Count static hazards only for imminent contact, and release a full charge after 3 s of aiming
   even if not lined up, so nothing can hold forever.
15. **Standing on the boss-room trapdoor forever.** A trapdoor that spawns under the player stays closed
   (sprite animation `"Closed"`, `State` 0) until the player walks away; a bot that heads straight for
   the exit never leaves it. Read `GridEntity:GetSprite():GetAnimation()`, and while it is `"Closed"`
   move 110-200 units away; it plays `"Open Animation"` -> `"Opened"` (State 1) and can then be entered.
16. **Bridge dead after a fresh game launch.** `include()` searches only `resources/scripts/` until a
   `luamod` adds the mod folder, and returns the "no file ..." error string. **Fix:** a second channel in
   the mod's own save data (`<install>/data/<mod>/save1.dat`, read with `mod:LoadData()`): the host tool
   writes `{"bridge": {id, ts, cmds}}` there and the mod polls it once a second; a `ts` check
   (`os.time()`, under 60 s old) lets the first packet after a launch run without replaying old ones.
17. **Walled in by a rock and a lit fire.** The breaker flood (rocks and fires passable at a price) used the
   passable cost for the no-corner-cutting check, so its path slid diagonally between the two and the
   planner found nothing to break. **Fix:** check corners with the real cost; also let fire-out tries
   come back after a pause instead of never.
18. **Unattended nights.** The game pauses when it loses focus (any window popping up); a once-a-minute
   heartbeat line with `paused`/`dead`/room age lets a host watchdog focus the window, press Esc, start a
   new run, or kill and relaunch by PID. The menus after a launch are cleared with Enter only (intro,
   title, file, Continue/New Run, character screen keeps the last character and difficulty).
19. **Bedroom door is a bomb door.** **Cause:** bedrooms (RoomType 18/19, more likely to spawn when the
   player is low on health) sit behind a door with `IsLocked()` true and variant 3 (DOOR_LOCKED_CRACKED); keys do
   nothing and the bot pushed into it. **Fix:** treat it as needing two player bombs from the cell in front
   (step away while each bomb is down); without the bombs, never pick the room. To test it, a seeded floor
   regenerated with `stage N` at half a heart gets the bedroom.
20. **Stalled in a doorway by poop.** **Cause:** door routing used radius 1, so poop on the cell in front of
   the door counted as "arrived" and the bot pushed into it until the stuck timer fired, then came back.
   **Fix:** check that cell first and shoot the poop (bomb a rock) before walking in.

## Assets
None (text UI only).

## Cost and time
Several sessions over three days; most time went into live debugging through the bridge + log loop.

## Open questions
- Pills/cards, secret rooms, crawlspaces, alt path (Downpour/Mines, Mother) and late-game bosses are not
  handled.
- Jacob & Esau, T.Forgotten and T.Cain need their own control logic.
