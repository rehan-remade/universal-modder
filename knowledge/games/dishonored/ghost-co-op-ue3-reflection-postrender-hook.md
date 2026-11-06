---
kind: game
title: 'Ghost co-op for Dishonored (2012): UE3 reflection, PostRender hook, UDP puppet'
game: Dishonored
games_also: []
game_version: 'Definitive Edition, Steam buildid 8335061 (Dishonored.exe PE timestamp 2022-02-17), 32-bit UE3 licensee (package FileVersion 801 / LicenseeVersion 30)'
platform: proton
engine: unreal
route: native-hook
tools: ['dinput8.dll proxy (own)', 'llvm-mingw 20261006 (i686 cross-compile)', 'CMake + Ninja', 'Python 3 + capstone/pefile', 'xdotool + ImageMagick import (XWayland)', 'winedbg (Proton)']
anti_cheat: 'none (single-player game, Steamworks API only, no SteamStub); offline LAN/localhost only'
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-11'
links: ['https://github.com/Jarvis-Production/DisCraft']
tags: [multiplayer, co-op, ue3, reflection, processevent, proton, two-instances, puppet, udp]
---
# Ghost co-op for Dishonored (2012): UE3 reflection, PostRender hook, UDP puppet

> Two copies of Dishonored (Steam, under Proton on Linux) each show the other player as a puppeted "ghost"
> body that follows the partner's real position.
> - The connection is our own UDP host/join (30 Hz snapshots, 100 ms interpolation), carried by a native DLL
>   loaded through a `dinput8.dll` proxy.
> - The DLL finds GNames/GObjects by content and calls engine functions by name through ProcessEvent.
> - Verified in game with two copies on one PC: numeric traces show final ghost error under 0.1 uu and
>   about 18 uu lag at walking speed (≈100 ms), with screenshot contact sheets in both directions.
> - Only transforms are shared. No combat, AI or world-state sync yet.
> - A closed-source co-op mod already exists (Nexus mod 450, J.P, Sept 2026). This note documents an open route.

## Setup
- Dishonored Definitive Edition, Steam app 205100, buildid 8335061.
  - `Binaries/Win32/Dishonored.exe`: PE32, **no ASLR** (DllCharacteristics 0x8100), so image base 0x400000 is fixed.
- Garuda Linux, KDE Plasma (Wayland). The game runs through XWayland under **Proton Experimental** ("11.0-100").
  - RTX 3060.
- Toolchain: llvm-mingw 20261006 (`i686-w64-mingw32-clang++`), C++20, static runtime. The DLLs import only
  system DLLs and UCRT api-sets.
- Mod files (all new files, no game file modified) in `Binaries/Win32/`:
  - `dinput8.dll`: proxy that forwards to system32 and loads GhostCoop.dll;
  - `GhostCoop.dll`: host;
  - `GhostLogic.dll`: hot-reloadable net/ghost logic;
  - `GhostCoop.ini`: role/IP/port per instance.
- Launch: `WINEDLLOVERRIDES="dinput8=n,b"`.
  - From Steam, set it as the launch option.
  - Our scripts run `proton run` directly with `SteamAppId=205100`. Steam must be running; ownership is
    checked normally.
- **Co-op scope.** Each player runs their own copy of Dishonored. The link is the DLL's own UDP over a direct
  connection (localhost here; between two PCs, a LAN or VPN address), not Steam networking or any Bethesda
  service. The one-PC setup below runs the same install twice, for testing.

## Route and why
- **UPK/UnrealScript edits: rejected.**
  - Packages are cooked and compressed (`PKG_StoreCompressed`).
  - Editing them breaks "never modify game files".
  - Worse, **UE3's netcode is stripped**: `IpDrv.upk` is a 1.6 KB stub, and the exe has no
    `TcpNetDriver`/`IpNetDriver` strings. We found nothing to switch replication back on with.
- **External memory-reading sidecar: rejected.** It can't call engine functions safely. On Linux,
  `ptrace_scope=1` plus Proton reparenting the game to `systemd --user` blocks `/proc/<pid>/mem` from a
  non-root shell anyway.
- **Chosen: an in-process native DLL.** It does SDK-free UE3 reflection, swaps a `UFunction::Func` for a
  game-thread tick, calls ProcessEvent, and runs its own UDP layer.
  - Idea credit: [DisCraft](https://github.com/Jarvis-Production/DisCraft) (Jarvis-Production, MIT), a
    Minecraft-in-Dishonored passthrough, describes content-based GNames/GObjects discovery in `docs/DESIGN.md`.
    Its README says it was written without the game and hadn't been run in real Dishonored yet.
  - Our implementation is independent, and several of DisCraft's documented assumptions turned out wrong for
    this build (see Gotchas).
- **Related:** `knowledge/games/assassin-s-creed-iv-black-flag/coop-ghost-avatar.md` is the same idea in AC4
  (a puppet body moved by transform writes from the plugin's own UDP link), and
  `knowledge/techniques/bridge-contracts-ownership-units-and-lifecycle.md` covers ownership and link
  lifecycle for when world state starts crossing.
  `knowledge/games/dishonored/telekinesis-ragdoll-control-hand-anims-pickups.md` builds a telekinesis power
  on the same reflection and PostRender route, with many more calls tested from render time (ragdolls, PhysX
  channels, emitters, Wwise events, anim nodes).

## How the game works (what we had to learn)
**Globals for this build** (we find them by content at runtime; the addresses are for debuggers):
- GNames `TArray<FNameEntry*>` @0x01435674; the entry text is at +0x10 and is ANSI.
- GObjects @0x01423630.
- `UObject::ProcessInternal` = 0x0045FF10 (shared Func of every script function).
- `ProcessEvent` = vtable slot 59 (0x00470640).

**Layout (LicenseeVersion 30):**
- **UObject:** Index **0x04** (stock UE3: 0x20), ObjectFlags 0x08, Outer 0x24, Name 0x28, Class 0x30,
  Archetype 0x34.
- **UField / UStruct:** Next 0x38, SuperField 0x44, Children 0x48, PropertySize 0x4C.
- **UProperty:** ArrayDim 0x3C, ElementSize 0x40, Flags 0x44, Offset 0x5C, Struct/BitMask 0x6C.
- **UFunction:** Flags 0x80, iNative 0x84, NumParms 0x91, ParmsSize 0x92, RetOffset 0x94, **Func 0x9C**.
- **FFrame:** Node at +0x10, Locals at +0x1C.
- Each offset is re-verified at startup against `Core.Object.Vector` (X/Y/Z at 0/4/8, size 12),
  `Engine.Actor.Location` (12 bytes) and `Engine.Actor.SetLocation` (2 parms, 0x10 bytes).

**Game-thread hook:** there is **no `PlayerController.PlayerTick` UFunction** in Dishonored. We swap `Func` on
`DishonoredGame.DishonoredViewportClient.PostRender(Canvas)`, a script event called every rendered frame
with a Canvas. That gives a tick plus an overlay through `Canvas.SetPos/SetDrawColor/DrawText`. The engine
assigns `Func` only when the class links, so a watchdog re-applies the swap.

**World and players:**
- Persistent world `DishonoredGameFull_P`; missions stream in as `L_*_P`.
- `WorldInfo.GetMapName()` returns the mission (case varies: lower-case it).
- Local controller = `Engine.GamePlayers[0].Actor` (Engine+0x480, Player.Actor +0x3C). Player pawn
  `DishonoredPlayerPawn`.
- Actor offsets: Location 0xC4, Rotation 0xD0, Velocity 0x1B4, Physics 0x104.

**Menus:**
- The title screen's "press any key" is a login step: `DisGFxMoviePlayerMainMenu.m_Screen` goes 1→3 and
  `m_LoginStep` 1→9.
- After that, calling `OnNewGameConfirm` on the menu movie starts the campaign through the real flow.

**What works from PostRender:**
- These work: `Spawn`, `SetHidden`, `ForceUpdateComponents`, `SkeletalMeshComponent.SetSkeletalMesh`,
  `ConsoleCommand`, `GetMapName`, Canvas drawing.
- `SetLocation`/`SetRotation`/`Move`/`Destroy` **return false** (even on the player pawn), presumably because
  we aren't inside the world tick.

**Ghost:**
- `Engine.SkeletalMeshActorSpawnable` with a live NPC's `Mesh.SkeletalMesh` (e.g.
  `Npc_EliteGuard.Mesh.Skm_EliteGuard_Body`).
- Moved by writing Location/Rotation and calling `ForceUpdateComponents`; hidden rather than destroyed.
- Z = pawn Location.z − 40 uu puts the feet on the floor.
- It renders headless (heads are separate `Attachments`) and in reference pose.

**Input facts (Proton, KDE Wayland):**
- The keyboard arrives as window messages (DirectInput is used for the mouse only).
- `PlayerInput.aBaseY`/`aBaseX`/`aTurn` (DishonoredPlayerInput) can be written every frame from the hook to
  walk the player with no OS input at all. `aBaseY=1` for 2 s moved about 650 uu; 0.5 walks at about 185 uu/s.

## Build steps
1. Cross-compile (llvm-mingw toolchain file, CMake + Ninja) → `dinput8.dll`, `GhostCoop.dll`, `GhostLogic.dll`.
2. Copy them plus `GhostCoop.ini` into `Binaries/Win32` by copy + rename. Never overwrite a DLL a running
   game has mapped.
3. Run the first copy with the Steam prefix and the second copy with its own Proton prefix
   (`STEAM_COMPAT_DATA_PATH=~/.local/share/ghostcoop/prefix2`). Both need `SteamAppId=205100`,
   `WINEDLLOVERRIDES=dinput8=n,b` and `DXVK_CONFIG="d3d9.presentInterval = 0; d3d9.maxFrameRate = 60"`.
   Use `-windowed -resx=1280 -resy=720 -nostartupmovies`.
4. Pass the title in each window (a real keypress/click), then call `OnNewGameConfirm` (or click New Game),
   then press a key on the mission loading screen.
5. GhostCoop.ini: `[Instance1] Role=host`, `[Instance2] Role=join HostIP=127.0.0.1` (port 27960). For two
   PCs, use `Role=join` and the host's LAN IP.

## Verification
- **Oracle 1, numeric:** each copy's DLL serves a localhost-only debug port with state JSON and RPC
  (`find/get/set/call/props`).
  - The test script reads the mover's real pawn Location from its own process and the ghost actor's Location
    in the observer's process, at 10 Hz.
  - Final horizontal error: 0.05 uu (A, 508 uu walk) and 0.01 uu (B, 1075 uu walk).
  - Lag while moving: mean 17–19 uu, max 23 uu at about 185 uu/s.
  - z is always −40 by design. RTT 16–17 ms on localhost.
- **Oracle 2, visual:** observer screenshots at about 3 fps (contact sheets). The ghost climbs the dock stairs
  and recedes (A); the ghost approaches from behind, passes the camera and walks ahead (B).
- **Oracle 3, link loss:** partner `netoff` → the host overlay shows "hosting, waiting for player" and hides
  the ghost; rejoin → "connected".
- **Not verified:**
  - two physical PCs over a real LAN;
  - long sessions;
  - mission transitions with both players;
  - any world-state sync;
  - Windows (only Proton/Linux was tested).

## Gotchas
1. **Symptom:** DisCraft-style hook on `PlayerController.PlayerTick` finds nothing. **Cause:** Dishonored has no
   such UFunction. **Fix:** swap `Func` on `DishonoredViewportClient.PostRender` (tick plus Canvas).
2. **Symptom:** hook "installed" but never called; the original Func reads as 0. **Cause:** the UFunction exists in
   GObjects before its class is linked, and linking overwrites Func. **Fix:** a watchdog that re-applies the swap
   whenever Func isn't ours.
3. **Symptom:** UObject::Index search lands on offset 0x04, which looks wrong. **Cause:** Dishonored's UObject
   really has Index at 0x04 (stock UE3: 0x20). **Fix:** trust a "self-index on every sampled object" detector
   over hard-coded layouts.
4. **Symptom:** `open L_Pub_Day_P` loads the map, then sits on "press any key" forever, even for real keypresses.
   **Cause:** the title-screen login was never passed. **Fix:** pass the title first (watch
   `m_Screen`), then use the menu's `OnNewGameConfirm`. Don't use raw `open`.
5. **Symptom:** spawning the ghost froze the game. **Cause:** we found "a PlayerController" by scanning GObjects
   and got the previous world's, which lingers until GC, then spawned through it during a transition.
   **Fix:** use `Engine.GamePlayers[0].Actor`, and only spawn after the local pawn has been stable for 3 s.
6. **Symptom:** `SetLocation`, `Move` and `Destroy` return false, even on the player. **Cause:** called from
   PostRender, outside the world tick (likely an engine guard). **Fix:** for a collision-free puppet, write
   Location/Rotation and call `ForceUpdateComponents`. Hide instead of destroy, and keep the actor pointer in
   host memory so logic hot-reloads don't leak ghosts. For real gameplay sync, hook inside the world tick.
7. **Symptom:** the unfocused copy pauses. **Cause:** `Engine.bPauseOnLossOfFocus=TRUE` (BaseEngine.ini).
   **Fix:** at runtime, clear it and `m_bRequestOpenPauseMenu_FocusLost` on the `DishonoredEngine` object every
   frame. No ini edit needed.
8. **Symptom:** one copy freezes when the windows overlap. **Cause:** a covered XWayland window blocks in Present
   with DXVK vsync and stalls the game thread. **Fix:** `DXVK_CONFIG="d3d9.presentInterval = 0; d3d9.maxFrameRate = 60"`
   and windows on separate monitors. KDE clamps a window to a monitor, so x-offsets that cross a monitor edge
   still overlap.
9. **Symptom:** synthetic input can't dismiss "press any key". **Cause:** these never reach the game:
   posted WM_KEYDOWN, faked GetFocus/GetForegroundWindow/GetActiveWindow, a GetKeyState hook, DirectInput
   state/buffer injection and `SendInput` without real focus. **Fix:** `xdotool windowactivate` + key/click for
   menus. That drives the real desktop, so ask the human first and don't do it while they're typing. For
   gameplay, write PlayerInput axes from the hook.
10. **Symptom:** a copy hangs permanently (main thread stuck in `PeekMessageW`/win32u or inside system dinput8;
    winedbg backtrace). **Cause:** not proven. Both times followed `xdotool windowactivate` + synthetic keys
    while two copies were running (once while we patched DirectInput vtables). **Fix:** keep desktop input to the
    title/loading screens only, and drive gameplay tests through `PlayerInput` axes.
11. **Symptom:** every debug-port round trip takes about 40 ms. **Cause:** Nagle plus delayed ACK on localhost TCP.
    **Fix:** `TCP_NODELAY` on both ends, and bulk "gather" ops (one round trip for 74k objects).
12. **Symptom:** a lambda can't be passed to `CreateThread` (i686). **Cause:** stdcall vs a lambda's default
    calling convention. **Fix:** a named `WINAPI` function.
13. **Symptom:** the ghost mesh floats. **Cause:** a pawn's Location is its collision-cylinder centre (player half-height
    87.5); a mesh actor's origin isn't. **Fix:** an empirical −40 uu for the NPC body in reference pose.
14. **Symptom:** `ParentAnimComponent` → live NPC mesh makes the ghost vanish. **Cause:** unknown. **Fix:**
    reverted. Animation is an open question.
15. **Symptom:** `um scan` reports "Unknown native engine (10%)". **Cause:** the scanner misses the "Unreal Engine 3
    Licensee" string and the `.upk` packages. **Fix:** identify the engine by hand. (Worth improving the scanner.)

## Assets
None generated. The ghost borrows the body mesh of an NPC already loaded in the level, at runtime; nothing is
extracted or shipped.

## Cost and time
About two working sessions (2026-10-10/11), including two full reverse-engineering passes and about 10 automated
two-copy restarts. Each automated restart into the mission takes about 4 minutes.

## Open questions
- Which script event runs inside the world tick and lets `SetLocation`/`Destroy` succeed? This is needed for
  doors, NPCs and deaths. The telekinesis note's probe of 659 script functions on the player objects saw only
  `HUD.PostRender` and `GameInfo.Timer` fire (its Gotcha 4). That note has since tried `GameInfo.Timer`:
  traces fail there too (`SetLocation` from it is untested). Its Open questions have a lead that may cover
  `SetLocation`/`Move`/`Destroy` as well: like `Trace`, they are natives with a fixed index.
- Giving the ghost a head (NPC `Attachments`) and animation (anim tree on a non-pawn owner, or a real AI-less
  `DishonoredNPCPawn`).
- Stable cross-process actor IDs for level-placed vs spawner-spawned actors.
- Real two-PC LAN latency; behaviour across mission transitions and saves.
- The cause of the two Wine hangs.
