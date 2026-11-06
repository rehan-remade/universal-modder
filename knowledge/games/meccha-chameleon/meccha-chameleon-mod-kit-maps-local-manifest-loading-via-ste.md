---
kind: game
title: 'MECCHA CHAMELEON: Mod Kit maps, local manifest loading via SteamWorkshopMapSubsystem, UE4SS PvE hunter'
game: MECCHA CHAMELEON
games_also: ['Wolfenstein: The New Order']
game_version: 'Steam app 4704690, buildid 25293176 (reported as 1.1.0; exe dated 2026-09-14, Steam patch notes at 4.1.x)'
platform: windows
engine: unreal
route: loader-api
tools: [official Mod Kit (UE 5.6.1), UE4SS + FOVControl StaticConstructObject signature]
anti_cheat: 'none found (um scan, PCGamingWiki); private solo lobby only'
status: in-progress
agents:
- Claude Code (claude-opus-5-5)
humans: []
date: '2026-10-15'
links:
- https://github.com/TakoKylo/MecchaChameleon-FOVControl
- https://github.com/c0re-i5/meccha-chameleon-modkit-guide
- https://allthings.how/meccha-chameleon-custom-maps-how-to-build-upload-and-play-them/
tags: [unreal-5.6, mod-kit, steam-workshop, ue4ss, pve, ai-bots, crossover]
---
# MECCHA CHAMELEON: Mod Kit maps, local manifest loading via SteamWorkshopMapSubsystem, UE4SS PvE hunter

> This is a recon and design note for a solo "Hunter vs AI hiders" mode on a ported Wolfenstein map, played in
> a private lobby the user hosts with nobody else in it. The game has no offline or single-player mode: every match
> is an online lobby that a player hosts.
> - The map, props and weapon assets go through the official Mod Kit as a content-only plugin.
> - The hunter-only mode, the weapon and the AI hider state machine are a UE4SS Lua mod that runs host-side in a
>   solo lobby.
> - The map should load from a local manifest through the game's own `SteamWorkshopMapSubsystem`, so nothing gets
>   uploaded.
>
> **None of this has run in game yet.** The engine facts below come from the install's manifest and exe strings.

## Setup
- The install has `Chameleon/Binaries/Win64/PenguinHotel-Win64-Shipping.exe`, UE 5.6 with IoStore, and
  `Chameleon-Windows.{pak,utoc,ucas}` + `global.*`.
- `Manifest_UFSFiles_Win64.txt` in the install root lists every packaged asset path. It is great for finding class
  paths without FModel.
- The online stack is Redpoint EOS + Steamworks. Mod.io plugins ship too.
- The Mod Kit needs UE **5.6.1** exactly. It is in the Steam library under Tools.

## Route and why
- Maps can only be shipped through the Mod Kit: a content-only plugin with one World Partition map, streaming off,
  spawn at 0,0,100, and the `CameraBlockWall` collision profile on walls. Packaging uses the FullGame then DLC
  profiles with I/O Store. Upload is SteamCMD `workshop_build_item`.
- Gameplay changes such as role forcing, a new weapon or bots need code. UE4SS is proven on this game by the
  FOVControl mod.
- **Anti-cheat:** none found. `um scan` found none and PCGamingWiki lists none. The Steam patch notes mention cheat
  countermeasures (fix2.5.1, 2026-07-07) and a host BAN list (update 3.8.0) but no anti-cheat product, and
  FOVControl's UE4SS proxy DLL loads, which a client anti-cheat would normally block.
- **Where it may run:** only a lobby you host, set to private, with nobody else in it. The store page says a server
  that isn't set to private is open to anyone. A hunter-only mode, forced roles and AI hiders change the match for
  everyone in it, so disable the mod (or remove UE4SS: `dwmapi.dll` and `ue4ss/` in `Binaries/Win64`) before you
  host or join any other match.

## How the game works (what we had to learn)
- **Hiders paint themselves; they don't turn into props.**
  - Survivor variations live in `BluePrints/cLeon/SurvivorVariations/`, named
    `BP_FirstPersonCharacter_cLeon_Character_Survivor_Default_<body>_<size>`: body `Base_Child`, `Cube` or
    `Fukuyoka`, size `0point5`, `1point0`, `1point4` or `1point7`.
  - Each has a matching decoy: `BluePrints/cLeon/Decoy/BP_cLeonDecoy_*`.
  - Paint: `BP_BrushPlane`, `BrushMaterial/M_PaintTarget`, `WBP_PaintMode_Cursor`.
- **Hunter.**
  - Pawn: `BP_FirstPersonCharacter_cLeon_Character_Hunter[_Default|_Cube|_Fukuyoka]`.
  - Shotgun: mesh `3Dmodel/cLeon/charactor/gun/gun`, plus `CAS_ShotGun`, `SC_ShotGun`, `BP_ShotGunShake`.
  - Inputs: `FirstPerson/Input/IMC_Weapons`.
  - The hunter is chosen by `BP_cLeonHunterLotteryArea`.
- **Match classes:** `BP_GameMode_cLeon`, `BP_GameState_cLeon`, `BP_FirstPersonPlayerState_Online_cLeon`, and the
  enums `EN_cLeonGamePhase` / `EN_cLeonMainGamePhase` / `EN_cLeonBodyType`. The main level is
  `stage_level/cLeon_game`.
- **Existing AI:** penguins use `PneguinAI/BP_AIController`, `BT_Enemy`, `BB_Enemy` and BT tasks such as
  `BTTask_RandomLocation`, so navigation works in this build.
- **Workshop map loader** (`/Script/SteamWorkshopMaps`, names read from the exe):
  - `USteamWorkshopMapSubsystem` has `LoadWorkshopMapFromManifest(ManifestFilePath)`, `ReadWorkshopMapDescriptor`,
    `GetPakMountDiagnostics(PakFilePath)`, `MountPakFromWorkshopItem`, `LoadWorkshopMapLevel`,
    `ScanMountedMapAssets` and `GetSubscribedWorkshopItems`.
  - `ASteamWorkshopMapReplicator::HostLoadWorkshopMapFromDescriptor(WorkshopItemId, Descriptor, AnchorTransform,
    bUseDescriptorEntryTransform, PakOrder, bAutoUnloadPreviousLevel)` streams the map in as `WorkshopMap_%s_%d`
    at an `AWorkshopMapAnchor`.
  - `FWorkshopMapDescriptor` serialises as JSON with the keys `schemaVersion`, `mapPackage`, `pakFileName`,
    `entryTransform{location,rotation,scale}` and `requiredGameVersion`.
  - Workshop folders hold only `<Plugin>-Windows.pak/.ucas/.utoc`, `AssetRegistry.bin` and `Preview.png`.
- **UE4SS** (these three come from the FOVControl mod's README and comments):
  - It needs FOVControl's custom `StaticConstructObject_Internal` signature (UE 5.6), or it loops on
    `PS Scan attempt N (Phase 2)`. The signature may need re-checking after a game update.
  - Don't mutate engine containers (TMap, FString, FText) from Lua: FOVControl's v2 crashed in FMallocBinned2
    ("realloc unrecognized block").
  - Get the local controller with `GameplayStatics:GetPlayerController(world, 0)`. On a listen server
    `UEHelpers.GetPlayerController` can return a remote player's controller.

## Build steps
Planned, not yet run in game. The mod's own files are not in this repo.
1. Convert the guest assets to OBJ/WAV outside the repo (see the Wolfenstein: The New Order note).
2. In the Mod Kit (UE 5.6.1), create a content-only plugin with one World Partition map, streaming off.
   - Import the meshes. Give the level mesh complex-as-simple collision and the `CameraBlockWall` profile.
   - Add a NavMeshBoundsVolume and TargetPoints tagged as hide spots.
   - Package the FullGame profile, then the DLC profile.
3. Install UE4SS in `Chameleon/Binaries/Win64` with FOVControl's `StaticConstructObject.lua` signature fix.
4. Lua mod, host-side, in a private lobby with nobody else in it:
   - dump the classes above (`ForEachProperty` / `ForEachFunction`) to confirm names;
   - call `LoadWorkshopMapFromManifest` on a local descriptor JSON next to the pak;
   - possess a spawned hunter pawn;
   - spawn survivor variations, give each an AIController, and drive them with `MoveToLocation`.

## Verification
- Done: names and paths come from the shipped manifest and the exe. The Lua parses and the Python byte-compiles.
- Not done: nothing has run in the game. The parameter lists of `LoadWorkshopMapFromManifest` and the role property
  are guesses until the UE4SS dump.

## Gotchas
1. **A "prop hunt" design doesn't fit this game.** **Cause:** hiders camouflage by painting, choosing a body type
   and posing. **Fix:** map "morph into a smaller prop" to respawning as the `0point5` survivor variation, and
   "decoy" to the game's own `BP_cLeonDecoy_*`.
2. **Workshop items carry no manifest file.** **Cause:** the descriptor is read from the mounted plugin's assets or
   built by the host. **Fix (untested):** write the descriptor JSON yourself next to a local pak and call
   `LoadWorkshopMapFromManifest`. `GetPakMountDiagnostics` reports why a mount fails.
3. **Ported maps must not go to the Workshop, not even as private items.** **Cause:** that redistributes the other
   game's assets. **Fix:** load locally.

## Assets
Map, props and weapon come from the user's own Wolfenstein: The New Order install (see that game's note). The
materials are procedural: no textures, tintable.

## Cost and time
One session of recon, converters and mod code.

## Open questions
- Exact UFunction signatures on `USteamWorkshopMapSubsystem`, and whether a non-Workshop pak path is accepted.
  Update 3.1.0 (2026-07-25) added a "security patch for MOD maps" after malicious Workshop maps ran code on
  players' PCs, so the mount path may now be checked.
- How `BP_GameMode_cLeon` reacts to a match with zero player hiders: does the round end at once?
- The real role field on the player state, and the lottery function to hook.
- How long `SteamWorkshopMapSubsystem` lasts. The developer's Switch 2 launch post (2026-09-09) says the Steam
  Workshop will be replaced by a new MOD system with cross-play mod maps by the end of 2026. Whether the Mod.io
  plugins in the install are that system is unconfirmed.
