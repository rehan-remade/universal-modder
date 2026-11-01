---
kind: game
title: 'NOLA: up to five player co-op in a single-player Unreal 5 game with a native UE4SS C++ mod'
game: 'S.T.A.L.K.E.R. 2: Heart of Chornobyl'
games_also: []
game_version: "Steam app 1643320, build 25382007 (game update 2.0 line, with the Cost of Hope DLC), Unreal Engine 5.5.4; UE4SS v3.0.1 experimental build 1164 as the loader"
platform: windows
engine: unreal
route: native-hook
tools:
- UE4SS v3.0.1 experimental (C++ mod API, PolyHook detours)
- CMake + MSVC
- Ghidra 12.1.4 (headless, full decompile of the shipping exe)
- repak 0.2.3
- Python (save codec oracle, table generators, fake clients)
- Steamworks flat API (the game's own steam_api64)
- C# (installer)
anti_cheat: none; single-player game with no anti-cheat and no online mode. NOLA only links players into sessions they host themselves, and nothing here touches DRM, ownership checks or Steam accounts
status: working
agents:
- Claude Code (Opus 5.5)
humans:
- Jaumn
date: '2026-10-21'
links:
- https://github.com/Joaovitor404silva/NOLA-Stalker2-Coop
tags:
- unreal
- ue5
- ue4ss
- cpp
- co-op
- multiplayer
- netcode
- host-authoritative
- a-life
- npc-sync
- damage
- downed-revive
- saves
- save-splice
- loading-screen
- quests
- steam-lobby
- udp
- installer
- repak
---
# NOLA: up to five player co-op in a single-player Unreal 5 game with a native UE4SS C++ mod

> NOLA ("No One Left Alone") adds co-op for up to five players (the host plus four) to S.T.A.L.K.E.R. 2,
> a single-player UE 5.5.4 game with no replication code at all. It is one UE4SS C++ mod plus one config pak:
> the host's game runs the real world (A-Life, NPCs, quests, weather), every other player joins that world and
> keeps their own character, and the two talk over Steam lobbies or plain UDP. It runs in the real game and is
> at V1 release candidate 1 (1.0-rc1): two-player play was tested a lot, three-player sessions in shorter runs,
> four and five players not yet. For what the game's data files say about A-Life, saves, quests and the rest,
> read the Zone Kit note in this folder first
> ([zone-kit-keep-the-game-systems-reference-drop-the-800-gb.md](zone-kit-keep-the-game-systems-reference-drop-the-800-gb.md));
> this note is about the native side and the co-op layer.

## Setup

- Game: Steam app 1643320, build 25382007, Windows 11, with the Cost of Hope DLC. Only this store and build are
  supported; every address below is for this exe build and moves with a game update. Exe image base is the usual
  `0x140000000`, so "exe+0x..." values below are RVAs.
- Loader: UE4SS v3.0.1 experimental (build 1164), installed next to the shipping exe (`dwmapi.dll` proxy plus the
  `ue4ss` folder). It only works on this game together with the game-specific custom config (signature scripts
  and a vtable layout file, Gotcha 1). `HookEngineTick = 1` must stay on: the mod's game-thread work runs from
  the engine tick pre-callback.
- The mod: one C++ DLL (`NolaNative`, about 60,000 lines in about 100 source files) built with CMake and MSVC
  against the UE4SS source tree, plus one merged config pak (`zzzzzz_Nola_P.pak`, classic pak, version V3, the
  usual GameData mount point, in `Content/Paks/~mods`). The pak adds the two prototypes the mod spawns for each
  remote player and a few thousand quest-node additions; the pak rules are in the Zone Kit note.
- Settings: one `flags.txt` (`key=value`, one per line) in a small bridge folder that the installer creates.
- Research tools: a headless Ghidra 12.1.4 decompile of the whole shipping exe (about 418,000 functions), the
  UE4SS object dump and `.usmap`, and our own searchable index of the decompile, the reflection data, the
  GameData configs and every verified finding. A debug build of the mod was used for testing.

## Route and why

Route is `native-hook`: a UE4SS C++ mod with detours on engine and game functions, the game's reflected
functions called through `ProcessEvent`, and a config pak for data.

- **Unreal networking: ruled out.** The game module `/Script/Stalker2` has no replicated classes and no RPCs.
  There is nothing to switch back on, so the mod brings its own transport, its own message set and its own
  authority rules.
- **First route: UE4SS Lua (dropped).** The project started as a Lua mod that called the game's reflected debug
  console functions (`CustomConsoleManager*` classes, about 400 `X...` functions such as `XSpawnObjBySID`,
  `XSetGameTime`, `XStartQuestNodeBySID`, `XSetEntityUnkillableByUID`). That is the fastest way into this game and
  it proved most of the design, but the Lua mod grew to about 18,500 lines plus about 16,000 lines of generated
  tables, and it kept crashing in ways a Lua mod cannot guard against:
  - UE4SS 3.0.1 runs `RegisterKeyBind`, `LoopAsync` and raw `ExecuteWithDelay` callbacks on another OS thread on
    the same `lua_State` as the game-thread tickers: random corruption and access violations;
  - indexing a cached `UObject` that the game freed, or calling `GetFName` on a null link of a property chain, is a
    native access violation that `pcall` cannot catch;
  - `FindObject` walks the whole `GUObjectArray` (31-41 ms frame spikes), and full `FindAllOf("Actor")` scans are
    too heavy in a streamed open world;
  - the real fixes for several sync bugs needed detours on unreflected native functions anyway (the damage gate,
    the NPC attack state machine, the save buffer), so half the logic already lived in a helper DLL.
- **Second route: all C++ (current).** The whole mod was ported to the UE4SS C++ API, table data moved to TSV files
  compiled into the DLL, and the release rule became "zero mod Lua". Each Lua module was kept running next to its
  C++ port until a parity bench (the old Lua under an offline Lua 5.4 stub against the C++ code) agreed. The Lua crash
  classes above went away with the port.
- **Rejected:** the official Blueprint mod route (needs the multi-hundred-GB editor and has no socket or file API),
  a reimplementation, and any "switch the client's A-Life off" lever (none of them works, Gotcha 8).
- **Design reference:** xrRazom, the community co-op mod for S.T.A.L.K.E.R. Anomaly: host-only spawns, send events
  and intents instead of full state, host owns NPCs, time and weather.

## How the game works (what we had to learn)

### Architecture as built

- **Authority.** The host is the master of everything that simulates: A-Life, NPCs and mutants, combat and damage
  to NPCs, time, weather, emissions, quests and story choices. Static or scripted things (doors, levers, padlocks,
  destructible props, anomalies, dropped items) are symmetric: whoever acts first sends the change and the host
  breaks ties. The host save is the save of record; each joiner keeps their own character inside it.
- **Players.** A remote player is two bodies on every other PC: a visible puppet (an NPC prototype from our pak,
  animated from the sender's pose and gait) and a hidden target body (`BP_AI_Human`, high max HP, kept still) that
  takes the bullets and gives local enemies something to aim at. Both are spawned with
  `XSpawnObjBySID(..., bDestroyOnOffline=false, ...)`; never `SpawnActor` a game pawn class (instant crash).
- **Transport.** Two interchangeable links under one message layer: Steam (lobbies through `ISteamMatchmaking`, data
  through `ISteamNetworkingMessages`, using the game's own `steam_api64` resolved with `GetProcAddress`, so nothing
  Steam-related ships with the mod) and plain UDP for LAN or a VPN. The host is a hub: `maxclients` (default 4)
  counts joiners, so host plus 4 is 5 players. Each joiner has a player id; per-view state (which NPCs a joiner can
  see, whose body is whose) is kept per id on the host.
- **Settings follow the host.** Keys marked host-owned are sent to every joiner on connect and override the
  joiner's own file while the session lasts.
- **Solo is untouched.** Nothing happens until the player picks one of the two new main-menu entries.

### Engine anchors (build 25382007)

- UE 5.5 `FField` layout: name at `+0x20`, `Offset_Internal` at `+0x44`, `sizeof(FProperty)` `0x70`.
  `ProcessEvent` is vtable slot `0x278`. Reflection names drop the U/A/F prefix.
- Character classes: `Obj` (under `Character`) is every living thing and holds HP and damage; `PC` is the player,
  `Agent` the NPCs and mutants. `Default__CppMediator:GetGUID(actor)` gives the numeric uid the console functions
  take (the local player is 0).
- In the decompile, `Class::execFoo` is the UFunction thunk and `Class::Foo` its body. A tiny function that calls the
  lazy reflection registrar once and returns a cached global is a class getter, not a real body; decompiler names
  near those are often wrong, so read the body before trusting a name.

### A-Life and NPC mirroring

- **One A-Life centre.** NPCs, squads and corpses are A-Life unit models; a unit is online (has an actor) only while
  it is near the one player unit whose id the game keeps in a single global (exe+0x9eec140). Every online/offline
  test reads that one id, so encounters exist only around the host. A joiner far from the host meets an empty
  Zone. V1 keeps players together (join teleport, cutscene pull, shared sleep and travel); a rotating centre is a V2
  study.
- **Client NPCs are real game NPCs ordered by the host.** S2 NPCs have no `AIController` or `BrainComponent`, and
  their locomotion is root motion plus motion matching fed by native AI, so writing velocity or input does nothing.
  The client keeps its own native copies and the host orders them: move goals through the `XAddMoveTo` path (it
  builds a native MoveTo goal), look/aim through `XNpcLookAt`, and gait speed through
  `ACharacter::AnimRootMotionTranslationScale` (read by `UCharacterMovementComponent::PerformMovement`).
- **No own shots on copies.** The NPC attack state machine lives in an `AttackComponent`; `AttackComp::MakeAttack`
  (exe+0x1038ad2) is the only Idle -> Shoot entry. A detour returns early for copies, and the host's shots are
  replayed by calling it on the copy and ending the burst with `StopAttack`. Montages are mirrored through
  `UAnimInstance::Montage_Play` and `Montage_StopInternal`, which every Blueprint, C++ and `PlayAnimMontage` path
  reaches.
- **Mutants** need their own movement parameters per class (Gotcha 16) and two extra bits: attack/ability montages
  and the bloodsucker cloak, whose only writer is a small native setter on its `InvisibilityComponent`.
- **Targeting.** The enemy target scorer gives a bonus to "is the player", tested as candidate id == that one
  player global, which is why enemies prefer the host. Each NPC also keeps its own accumulated personal relation to
  every body it fought, separate from faction defaults; `XSetRelation(a, b, v)` sets a pair symmetrically.

### Damage, friendly fire, downed and revive

- `Obj:ReceiveDamage(amount, type, ..., bone)` applies the bone multiplier and ignores armour;
  `Obj:ReceiveDamageStruct({...})` applies armour (each armour-piercing point doubles the multiplier) and ignores
  the bone. Neither is what a real bullet does. NOLA delivers a remote player's hit through the game's own hit entry
  (the function behind `ReceiveDamageStruct`), so bone, armour and the player-only reduction all apply once.
- Every hit passes a gate (exe+0x653281) that checks the attacker id first. Ids `0xFFFFFFFD`/`0xFFFFFFFE` pass,
  `0xFFFFFFF0..0xFFFFFFFC` and `0xFFFFFFFF` are dropped silently (Gotcha 10).
- Client bullets, knife and grenades on host NPCs are sent as hit events and applied once on the host; a client
  kill is credited to the host. Friendly fire works both ways and follows the host's setting and scale.
- Downed: at low HP the player is held by the game's own `Unkillable` bit
  (`XSetEntityUnkillableByUID`), not just an HP floor, so `Obj::CanDie` is false between ticks (Gotcha 11). A
  teammate holds F with a medkit nearby to revive, and the medkit's heal is applied. All players down means game
  over and a host reload, which every joiner follows.
- Grenades that land near a protected story NPC are defused by the stock game; that is not a sync bug.

### Items, loot and ownership

- The host decides every take per player id: first claim wins, the item is removed for everyone else.
- One body per death, at the same place for everyone; looting from any PC edits one shared list; an emptied body
  stays as a corpse with nothing to take.
- Quest items go to every player once, through a host ledger that survives save/load, reconnects and level
  transitions, so nobody ever gets a duplicate.
- Trader stock is its own native container per vendor, rolled when trade opens. V1 keeps it per player.

### Quests and story

- Quest progress follows the host: node starts and ends are relayed and replayed through the console's quest-node
  functions. `XEndQuestNodeBySID` only acts on a node that is active in its quest, so a catch-up that ends the
  other player's reached nodes cannot finish anything twice.
- Some quest event nodes complete only from a native event in the local world (for example a signal sender posting
  to the event bus), so a node finished on a joiner's PC never reaches the host. The pak adds about 1,600 small
  relay nodes so those events are reported and replayed.
- Story choices: about 2,900 branch nodes and 1,800 decisive answers were classified from the dialog and quest
  tables. A joiner's click on a decisive answer is refused at the commit point and they follow the host's pick;
  random branches are pinned to the host's roll.
- The dialogue widget `W_DialogueView_C` stays `IsInViewport` after it closes (Gotcha 13).

### Loading together and the save splice

- **Save format.** A slot file is a u32 raw size, an Oodle Kraken stream and a CRC32. Oodle is linked statically
  into the exe (no DLL ships), so the mod calls the game's own Kraken decoder and encoder; re-encoding at the
  game's level gives the game's exact bytes. The raw save is a version `0xBB` header, model pools
  (`FUnitModel`, `FModelItem`, `FModelItemContainer`, and so on) back to back, and name tables at the end; the only
  offset to patch is the name-table offset. The local player is unit 0 with container `0x38000000`.
- **Save splice.** That last fact is what lets a joiner keep their character: after each host save the host sends
  its world, and the joiner's mod writes a save that holds the host world plus the joiner's own character
  (inventory with condition, ammo and attachments, slots, quick slots, HP), checks the result decodes back to the
  same character, and keeps a backup. Co-op saves live in their own store (the save path is two `FString`s, one on
  the campaign manager and one on the save/load manager), so solo saves are never touched.
- **Load gate.** A joiner waits on the stock loading screen until the host's world is up: the mod detours the raw
  save buffer gate (exe+0x3b36404), which receives the decompressed save after it is read and before it is
  deserialised. Taking the buffer pauses the load inside the loading screen with no timeout; calling the original
  later with the host's bytes resumes it. Every host load, reload and death reload makes joiners follow the same way.
- **After a load** the game's `ScenarioManager` tick stays off, quest-node starts wait in a pending set and the game
  clock stands still until the "press any button" step of `W_LoadingScreen_C` runs (Gotcha 14).

### World objects and doors

- Doors, levers, switches and destructible props are replayed from a table of interactable classes (about 320 action
  classes and 200 padlock/lock classes) with the stock functions, for example a padlock break replayed through the
  object's own damage-accumulated event, and the door's lock bit synced with host authority. Anomaly triggers are
  replayed the same way.
- Time and weather follow the host's two clocks (the quest/A-Life clock and the separate weather/sun clock, see the
  Zone Kit note). Nobody can pause; sleeping needs everybody; emissions run for all.

### Menu entries and session messages

- The main menu gets two entries, **Host co-op** and **Join co-op**; the choice sets the role for that session, so
  every PC has the same files. Menu buttons come from a `MenuButtonModel` array that a menu sub-view reads when it
  builds the list; adding entries there shows them with the stock style. The menu is built once, so it has to be
  rebuilt after the co-op save store is switched in (Gotcha 18).
- Mod-made menu objects created with `StaticConstructObject` are freed on a world -> main menu round trip even when
  they are added to the root set, and an `FString` handed to a widget must never be rewritten later.
- Session messages (join, leave, lost signal) borrow the stock tutorial box. Stock tutorials have no queue: one
  widget per tutorial type, and a second show replaces the content in place.
- A small NOLA logo sits beside the game's logo in the main menu (a PNG loaded at runtime with
  `ImportFileAsTexture2D`).

### The flag file

- One `flags.txt`, `key=value` per line, re-read at runtime. Every feature is ON by default with an off key
  (`friendlyfire`, `downsecs`, `reviveitem`, `qsync`, `choice`, `doors`, `idrop`, `sleepsync`, `nopause`, ...),
  plus `net=steam|ip`, `netpeer` for IP play and `maxclients`. Host-owned keys follow the host while in its session.
  The public settings page lists the player-safe keys; the others are tuning values.
- The file is last-wins: a duplicate key silently overrides the first one. That cost a day once (a test value at
  the bottom of the file turned client damage off).

## Build steps

1. Install UE4SS 3.0.1 experimental with the game's custom config for this build (signature scripts and
   `VTableLayout.ini`), take an object dump and a `.usmap` once.
2. Build the C++ mod with CMake + MSVC against the UE4SS source tree (a C++ mod in `ue4ss/Mods/<Name>/dlls/main.dll`,
   enabled in `mods.txt`). Keep generated tables (interactables, quest relays, dialog branches, texts) as TSV in the
   repo and compile them in with a generator, so there is one source per table.
3. Build the pak only from its source folders with `repak pack --version V3` and the GameData mount point; the
   release builder refuses a pak whose node sets or contents differ from the sources (Gotchas 19 and 20).
4. Release package: a C# installer (`NOLA-Setup.exe`) and a manual zip with the same files and step-by-step notes.
   Both ship UE4SS (with its MIT licence), the custom config, the mod DLL, the pak and a default `flags.txt`; keep a
   backup of every replaced file; keep an existing `UE4SS-settings.ini` and `mods.txt` and only add the NOLA line;
   never touch saves. Every PC gets the same files; the role is chosen in the menu. The installer asks Steam or IP
   and writes the two connection lines.
5. The release builder switches every debug and test-only flag off and checks that dev-only modules are compiled out.

## Verification

- **Live rigs.** A test harness starts and drives up to three game instances on one PC (host plus two joiners,
  separate install copies, IP mode), sets flags live, sends input to the right window, collects logs and crash
  dumps, and restores the baseline afterwards. Two-PC runs covered LAN and the Steam lobby path. Scripted fake
  clients on a second machine exercised the hub with four joiners at the message level. Three full game instances on
  one PC are memory-bound: one run ran out of memory, so the harness now refuses to start a third instance
  without about 10 GB free.
- **Logs as the first oracle.** Every feature writes one line per decision with numbers (HP before and after, uid,
  distance, timing), and a log catalogue checks those lines against regex specs.
- **Screenshots with an independent verifier.** A "you can see it" claim counts only when screenshots and a claim
  file are confirmed by a fresh agent that did not run the test; it answers CONFIRMED, REJECTED or CAN'T TELL per
  claim. This caught several "the log says ok but the screen does not" cases (Gotcha 21).
- **Offline suites.** About 30 unit and golden suites (flags, save codec and splice against a Python oracle,
  damage parity against the old Lua, items, quests, travel, menu, network glue), plus our knowledge index of verified
  findings, with a search eval so a new note does not bury an old one.
- **Crash discipline.** After three identical failures, stop reproducing live and read the dump and the code
  instead. Dumps are triaged with our PDB and named exe frames.
- **Checked live on the release candidate:** join and land beside the host (about 1 s), leave and rejoin without a
  duplicate body, host/join switch without a restart, NPCs from the host and no invisible enemies (logs),
  dropped items, bodies and loot, padlocks, stashes, quest progress in the opening missions, quest items once each,
  host-only story answers on a sample, joiner damage, grenades (logs), enemies hurting every player, friendly fire
  both ways, downed and revive, game over, load together, the corrupt-save popup fix, session messages and menu
  texts in English, Portuguese and Spanish, one hand-played stability session with no crash.
- **NOT verified:** four and five player sessions with real games (only the hub logic with fake clients), long
  sessions of several hours, missions past the opening story, other mods alongside NOLA, guide fast travel
  together, the "host went silent" path, weapon upgrades after a join or reload, the full table of story branches
  one by one, other mutant types and how the mutant copies look, and a Steam session between two separate owners'
  accounts. Items a joiner picked up after the host's last save come back without upgrades on reload; one huge hit
  can still kill a joiner without the downed state; an extra remote body can appear after a very long teleport.

## Gotchas

1. **UE4SS starts but every hook fails.** Symptom: the UE4SS log reports failed scans for `GUObjectArray`,
   `FUObjectHashTables` and `GNatives`; the plain experimental zips (1161 and 1164) both fail. **Cause:** the
   generic patterns do not match this exe. **Fix:** use the game-specific custom config from the same UE4SS
   release (signature scripts plus `VTableLayout.ini` for this game), then the hash-table self test passes. Ship
   those files with the mod: a clean PC does not have them.
2. **Random Lua crashes that `pcall` never catches.** **Cause:** off-thread callbacks on a shared `lua_State`,
   stale cached objects, and null links in property chains are native faults. **Fix:** in Lua, only game-thread
   loops (`LoopInGameThreadWithDelay`, nothing under 100 ms), `IsValid()` on every link, and poll keys instead of
   `RegisterKeyBind`. For a mod this size: move to C++.
3. **Frame spikes from object lookups.** **Cause:** UE4SS `FindObject` scans the whole `GUObjectArray` in this game.
   **Fix:** resolve asset paths with `KismetSystemLibrary::Conv_SoftObjectReferenceToObject` (hashed, about 0.01 ms)
   and cache. Also: UE4SS `StaticFindObject` on a path with no dot throws a C++ exception, which kills the game
   inside a detour.
4. **Blueprint events silently stop running after a caught fault.** Symptom: pressing F on a door does nothing,
   only after a while in a session. **Cause:** `UObject::ProcessEvent` (exe+0x216a728) links each script frame
   into a per-thread slot and restores it only in its normal epilogue; an SEH `__except` around it skips that, so new
   frames inherit a garbage abort byte and run no bytecode. **Fix:** save that thread-local slot before `__try` and
   restore it in `__except`.
5. **Remote players' bodies multiply and come back as strangers.** Symptom: after a rejoin there are two bodies;
   after a reload, odd NPCs with max HP of about 120,020. **Cause:** the game saves our puppet and target bodies as
   ordinary A-Life units in every save, on both roles; on load they return with max HP times 1.2002 and get adopted
   again. Worse, entity uids allocated after the shared base point at different entities in the host's and the
   joiner's files (the same uid is a puppet in one and a stock NPC in the other). **Fix:** strip our units on every
   load in every role, never match entities by uid across two roles' saves, and key everything on the host's uid.
6. **Invisible enemies hurt the joiner.** **Cause:** the joiner's game still has its own live local NPCs. They are
   hidden, but they keep thinking, keep growing their personal hostility to our hidden target body and shoot it;
   and a game that booted as host and then joined kept its own A-Life. **Fix:** decide the role live from the
   session, and make every hidden live local NPC inert at the source: a MoveTo hold that ignores threat and
   combat, plus the `MakeAttack` cut, from one category table. Log the attacker of every hit on the local player.
7. **Enemies always go for the host.** **Cause:** the target scorer's "is the player" test compares against the
   single player id, so remote player bodies score as ordinary NPCs. **Fix:** hidden target bodies per remote player
   and host-side aggro that considers every player's view. This fix is designed and built but not yet confirmed in a live session.
8. **"Turn the client's A-Life off" does not exist.** `XALifeDisable` is an empty stub, `StopLogic`/`RestartLogic`
   are no-ops (no brain component), and the AI feature switches do not stop the spawn bubble. **Fix:** drive native
   copies from the host instead of trying to silence the client's simulation.
9. **Spawns that never appear.** `XSpawnObjBySID(..., bDestroyOnOffline=true, ...)` gives no pawn; spawns requested
   while a load is held all appear together after the release; spawns outside the bubble produce nothing.
   **Fix:** `false`, spawn only after the world runs, near a player.
10. **Friendly fire hits that lower no HP.** Symptom: the injected hit returns normally and HP stays at 100.
    **Cause:** the attacker id `0xFFFFFFFF` is dropped by the damage gate, which skips the whole hit body.
    **Fix:** use the game's own no-attacker id `0xFFFFFFFE` (the console's damage and suicide functions use it).
11. **A downed player dies at once.** **Cause:** the downed state was only an HP floor written each tick; any hit
    larger than the remaining HP between two ticks ran the stock death. **Fix:** hold the game's `Unkillable` bit
    while downed, with an owner rule so cutscene and emission protection do not release it early. Still open: one
    huge hit (a close grenade) can kill before the downed state starts.
12. **The joiner could not hurt the host.** **Cause:** the joiner's own sweep that hides stray local pawns hid the
    freshly spawned remote target and switched its collision off in the 1.5 s before the body was adopted, so
    bullets passed through. **Fix:** treat pending bodies as own bodies from the spawn request on.
13. **"Busy in dialogue" never clears.** **Cause:** `W_DialogueView_C` is collapsed, not removed, when a dialogue
    ends, so `IsInViewport` stays true. **Fix:** "dialogue open" = `IsInViewport` AND `IsVisible`. The stock
    tutorial box has the same trap: a collapsed one keeps its fade-out byte set forever.
14. **After a load, nothing runs until a key is pressed.** Quest-node starts pile up in `ScenarioManager`'s pending
    set, the game clock stands still and the player's weapon actor does not exist yet. **Cause:** the
    `ScenarioManager` tick is re-enabled only by the "press any button" step of the stock loading screen.
    **Fix:** the mod ends that step itself at load complete on joiners, and nothing waits on "pawn exists" as the
    in-world signal.
15. **The load gate held the main menu too.** **Cause:** the main menu reads saves through the same raw buffer gate
    with the same delegate (nine 13-19 MB reads as the menu opens). **Fix:** hold only when a real load began (the
    load-begin function ran since the last read), the delegate type matches, and the buffer is a full save with the
    `0xBB` header. Call the original and the lambda's destructor on the game thread to resume.
16. **Mutant copies run twice as fast as the host's.** **Cause:** the human gait thresholds picked entries from the
    wrong gait table for mutants (a bloodsucker walk came out 2.5 times too fast). **Fix:** per-class movement
    parameters for every mutant class from one table. Still visible: feet can keep moving a moment after a mutant
    stops.
17. **The join teleport took 42 s.** **Cause:** the floor under the host is a packed `ActorPackInstance` instanced
    mesh whose collision exists only near the local player, so a floor trace from far away misses forever even when
    `WorldPartitionSubsystem::IsStreamingCompleted` already says the cells are active; and the landing trace hit
    the player's own mesh. **Fix:** go as soon as the streaming query is ready, ignore the own pawn in traces, step
    aside once the floor appears. Also: teleports land at Z+100 cm, and a floor that has not streamed yet means a
    fall death.
18. **A false "save file is corrupted" popup.** **Cause:** the main menu is built once; switching to the co-op save
    store did not rebuild it, so Continue pointed at a save that the empty co-op store does not have. **Fix:**
    rebuild the menu after the store switch, and tell the host to pick Load or New Game when the co-op store is
    empty.
19. **A feature died in the release build only.** **Cause:** the merged pak was packed from source folders, and one
    node set (the about 1,600 quest-event relay nodes) existed only as an installed pak with no source folder, so it
    silently dropped out. **Fix:** every pak comes from a source folder, and the builder checks the expected node
    sets before it writes the release.
20. **repak output is not byte-stable.** Two packs of the same files differ in bytes. **Fix:** compare the unpacked
    contents (a hash over sorted `path + file hash` lines), never the pak's own hash.
21. **"ok=true" in the log, nothing on screen.** A wounded pose call logged success while the puppet stood upright.
    **Fix:** any visible claim needs a screenshot judged by a separate verifier; a log line only proves the call ran.
22. **Every quit with Steam running crashed on exit.** **Cause:** UE4SS runs no C++ mod shutdown at process exit, so
    the mod's Steam receive thread kept polling after the engine unloaded the Steam module. **Fix:** stop and join
    the thread in a detour on `GameEngine::PreExit` (it runs before module unload), with a bounded wait. The fix is in
    the release candidate but not yet confirmed in game.
23. **Tapping F on a corpse dragged it.** **Cause:** our interaction helper wrote the stock drag component's state on
    `DeadBody`, which the game keeps off except while dragging. **Fix:** a list of stock-owned components the mod never
    writes.
24. **Skipping a quest-node start leaks.** `StartQuestNode` consumes and releases both SID handles at every exit, so
    a detour that skips the original call must release them itself.

## Assets

No game assets were extracted or shipped. The remote players use stock meshes and animations through our NPC
prototypes. The only new art is the NOLA logo PNG.

## Cost and time

Many daily agent sessions under one human, with several agents working in parallel on separate
features. A full game restart costs over a minute, so the harness, live flag reloads and offline suites were built
early and paid for themselves.

## Open questions

- Four and five player sessions with real games, and long sessions.
- More than one A-Life centre when players are far apart (the bubble reads one global player id everywhere).
- Shared trader stock, weapon upgrades on restored items, and the occasional extra body after a long teleport.
- Spawning the joiner beside the host before its world loads (the load gate already splices before deserialising).
- Survival of the address set across a game update; a hook manifest with byte checks per detour exists but is not
  in V1.

## Credits

- **UE4SS** (UE4SS-RE, MIT licence): the loader and C++ mod API that makes this possible; its licence ships with NOLA.
- **repak** (trumank): pak listing and packing.
- **GSC Game World**: the game, and the Zone Kit configs that explain its systems. NOLA is an unofficial,
  non-commercial fan project, not affiliated with or endorsed by GSC, and it contains no game files.
- **xrRazom**: the S.T.A.L.K.E.R. Anomaly co-op mod whose host-authoritative design we followed.
- Built by Jaumn with heavy help from AI coding agents (Claude), who wrote most of the code, tests and documents
  under his direction; he ran the game tests and decided what shipped.
