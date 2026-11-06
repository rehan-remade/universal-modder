---
kind: game
title: 'Split-screen co-op fixes for Arkham City (BmSDK C# scripts: cameras, P2 gadgets and suits, final boss, per-player
  Wwise listeners)'
game: 'Batman: Arkham City'
games_also: []
game_version: 'Game of the Year Edition, Steam, 32-bit DX11, with BmSDK v0.21.0'
platform: windows
engine: unreal
route: loader-api
tools: ["BmSDK v0.21.0", "dnfile (Python)", "capstone (Python)", "pefile (Python)", "gh"]
anti_cheat: "none (single-player); the Steam exe's code is encrypted on disk, so it was read from the running process for reverse engineering"
status: released
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-25'
links: ["https://github.com/etkramer/SplitScreenMod", "https://github.com/etkramer/SplitScreenMod/pull/21", "https://github.com/etkramer/SplitScreenMod/pull/22", "https://github.com/etkramer/SplitScreenMod/pull/23", "https://github.com/etkramer/SplitScreenMod/pull/25", "https://github.com/etkramer/SplitScreenMod/pull/26", "https://github.com/Kendoismebutmaybenot/SplitScreenMod-fixes", "https://github.com/Team-BmSDK/BmSDK-AC"]
tags: [split-screen, co-op, unreal-engine-3, bmsdk, wwise, audio, camera, possession, redirect, detour]
---
# Split-screen co-op fixes for Arkham City (BmSDK C# scripts: cameras, P2 gadgets and suits, final boss, per-player Wwise listeners)

> About 20 fixes to etkramer's local split-screen co-op mod for Batman: Arkham City, written as BmSDK C# scripts
> (UnrealScript function redirects, plus two native detours for sound). They cover unstretched per-player cameras,
> P2 gadgets, suits and characters, playing the story through to the final boss in co-op, and per-player sound.
> Every fix except the Clayface one was played and confirmed by the human in the real game (Steam build). PRs #21,
> #22, #25 (no teleport when sliding under gaps; solo kept like the normal game) and #26 (the extra player ragdolls
> on death instead of P1; no teleport to P1 after a fight) were merged upstream. #23 (finding the sound range check
> by its bytes, so it can work on Epic) is still open there, so that part is only in the author's fork for now.

## Setup
- Batman: Arkham City GOTY, Steam, Windows 11. The game runs as 32-bit DX11.
- BmSDK v0.21.0 (`dinput8.dll` + `plugins\BmSDK.Host.asi` + an `sdk` folder with a bundled .NET runtime). BmSDK has
  run on the Steam exe as shipped since v0.19.0. It tells builds apart by the exe's PE `TimeDateStamp`
  (`0x520000F7` Steam, `0x5D9F84DF` Epic) and logs "Detected Steam build".
- Older BmSDK instructions, and the troubleshooting list in SplitScreenMod's README, still mention a "compatibility
  patch" that replaces `BatmanAC.exe`. Skip it and keep the exe the store installed. This work ran on the Steam exe
  as installed: its code is still encrypted on disk (Gotcha 8).
- Mod: `BmGame\Mods\SplitScreenMod-main\` (`mod.toml` plus `scripts\**\*.cs`). BmSDK compiles the C# scripts **at
  game start** and logs to `Binaries\Win32\BmSDK.log`. One compile error disables the whole mod.
- There was no .NET SDK on the PC, so nothing could be compiled offline. API signatures were checked against
  `Binaries\Win32\sdk\BmSDK.dll` with `dnfile` (TypeDef/MethodDef/property lists) and against `BmSDK.xml`.
- Two or more controllers. G adds a player, **only at the main menu** (`IsFrontend`).

## Route and why
BmSDK exposes the UE3 object model as generated C# (`BmSDK.Engine`, `BmSDK.BmGame`, ...) and lets a script:
- `[Redirect(typeof(Class), nameof(Class.Func), AllowSubtypes = true)]` to replace any UnrealScript/UFunction and
  call the original by calling the same method on `self`;
- `[ScriptComponent(AutoAttach = true)]` + `[ComponentRedirect]` to do the same per object;
- `DetourUtil.NewDetour<TDelegate>(rva, detour)` to hook native code at an RVA from the exe base;
- `OnTick`, `OnKeyDown`, `Main`.

Almost everything was solved with redirects. Native detours were used only where no UFunction exists, and both are
for sound: Wwise's exported `SetActiveListeners` and the game's sound range check (below). Recompiling the game or
editing packages was never needed.

## How the game works (what we had to learn)
**P1 is special everywhere.** Much game logic runs only for `GamePlayers[0]` or reads P1's options:
- story, cutscenes and game over;
- the cryptographic sequencer, the line-launcher wire and the batarang invert option.

The most reusable trick: **swap `GamePlayers[0]` and `[i]` around the call**, then swap back. That runs P1-only
logic for another player.

**Cameras.** `CalcSceneView` (native) uses the whole window's aspect ratio unless the player camera's
`bConstrainAspectRatio` is set, and then it uses `ConstrainedAspectRatio`. Set these per player to the real size of
their half of the screen, and widen the FOV (Hor+). That gives unstretched 2P views without letterboxing. It needs
no detour, but the values have to be written after every camera update: stock UE3's `Camera.DoUpdateCamera` resets
`bConstrainAspectRatio` to false and `ConstrainedAspectRatio` to the view target's aspect each frame (UDK
`Camera.uc`). So the mod redirects `R3rdPersonCamera.UpdateCamera`, calls the original, then writes them. The
original mod forces `RGameRI.IsMultiplayer()` to false, which fixes the level-up screen and other menus.

**Characters and suits.**
- `RGameRI.PlayerCharacters[0..7]` holds one slot per player (`CharacterName`, `MeshName`, `MeshData`).
- `RGameInfo.GetPlayerCharacterIndex(controller)` picks the slot.
- `RPawnPlayer.SetupPlayerMesh` finds the **first slot whose `CharacterName` matches**. So two Batmen both get P1's
  suit. The fix: while an extra player's pawn runs `SetupPlayerMesh`, put that player's suit's `MeshData` in slot 0
  briefly. Do it at spawn time: redirect `SpawnDefaultPawnFor` to remember which player is spawning.
- **Swapping the mesh on a live pawn with `ApplyMeshData` crashed** once the pawn moved.
- The game later re-applies P1's suit with `ApplyMeshData`. Block that only when the mesh is exactly P1's.
- After the story, switching Batman/Catwoman runs `RPlayerController.PrepareForPlayerSwitch` and reloads the slots.
  The slot's `MeshData` comes back as the character's default suit, so re-set it before `SetupPlayerMesh`.

**Gadget icons** come from `CharacterData.CharacterAcronym` in the player's own slot.

**Robin's grapnel boost** isn't an upgrade-name check. It's gated by `RPawnPlayer.bCanGrappleBoost` and
`bCanDiveBoost`. Copying them from P1 to an extra **Robin** works. Nightwing and Catwoman get stuck mid-grapple with
the boost.

**Remote-control batarang.** The original mod removes slow-mo in split screen. The batarang's per-tick location
step ignores `ThrowSpeed` and `Velocity`, so it flew about 3x too fast; scale its step by the slow-mo factor
instead. Extra players don't load P1's options, so copy `RPlayerInput.bInvertBatarang` from P1 each tick.

**Cutscenes** only unlock P1's controls when they end. Afterwards, release any other player still flagged
cinematic, forced or ignoring move/look, and teleport them to P1 if they're over 5000 uu away. Only teleport players
that were locked during the cutscene too: the slow-motion finish of a fight locks only P1 (Gotcha 11).

**Final boss (Monarch Theatre).** The checkpoint possesses `RPawnPlayerBatmanWithSword` **for every player in
turn**, so P2 steals it and P1 is left pawnless, which is an instant game over.
- Fix: redirect `RPlayerController.Possess`. An extra player can't possess a pawn that another player's controller
  holds. They go back into their previous pawn (tracked in `UnPossess`), or `Respawn()` next to P1.
- Also block player-vs-player `EncroachedBy` and `CrushedBy`.
- Rescue an extra player on `FellOutOfWorld`, `OutsideWorldBounds`, or a death during P1's cutscene.

**Game over only runs for P1.** An extra player's real death left a permanent black screen: their controller goes
to its `Dead` state, but nothing calls `TriggerGameOver` for it.
- Fix: let the extra player's `Died` run (they ragdoll), then call `PawnDied(p1Pawn)` on **P1's controller**
  without killing P1's pawn. P1's controller enters `Dead` and runs the normal fade, `TriggerGameOver`, game over
  movie and checkpoint reload, while P1's pawn just stands there.
- Keep a fallback: if `TriggerGameOver` hasn't fired 10 s later, re-possess P1's pawn and kill it.
- An earlier version killed P1's pawn (`Health = 0; Died(...)`) and kept the extra player alive. That works, but P1
  ragdolls and P2 stays standing, so players can't tell who died (Gotcha 5).

**Level transitions.** `RLevelTransition.SetPlayerLocation(PC, Pos, Rot, TellPlayerHesMoved, bForSavingOnly)` moves
the player through a transition, and the original mod's redirect then moved every other player there too. The game
also calls it with `bForSavingOnly = true` just to record a spot (e.g. when Batman slides under a gap), and the
redirect moved everyone anyway, P1 included, even in solo. Return early when `bForSavingOnly` is set or in solo,
and skip the player the game already moved (Gotcha 12).

**Keep solo exactly like the normal game.** Several split-screen workarounds ran with one player too:
- investigation scenes: AI X-ray sprites turned off and `StartInvestigateMovie` rewritten;
- the cryptographic sequencer drawn as a flat overlay (`bWorldRendered = false`) instead of the in-world hologram;
- Nightwing's wrist darts refilling without their timer (`RegenWristDart`).

Gate each on `GamePlayers.Count > 1` and call the original otherwise. Don't use `RGameRI.IsMultiplayer()` for this:
the mod forces it to false (see Cameras), so it's false in co-op too. The ghost debug key was left working in solo
on purpose.

**Clayface's mud men** (`RBMBehaviour_ClayfaceDrone(Small)`) hard-target P1 through their `Batman` field. Set it to
the nearest player in `OnActivate`/`Tick`, with an 800 uu switch margin, and call `SetTargetPlayer`. (Not verified
in game; there was no save at that point.)

**Audio is Wwise, and the exe exports the Wwise API by C++-mangled name.** That includes
`AK::SoundEngine::SetActiveListeners`, `SetListenerPosition`, `SetPosition` and
`Query::GetListenerPosition`/`GetActiveListeners`. Get them with `GetProcAddress(GetModuleHandle(NULL), "?Set...")`.
They are cdecl, game object IDs are 32-bit, and there are 8 listeners. The mangled names confirm the first two:
`?SetActiveListeners@SoundEngine@AK@@YA?AW4AKRESULT@@IK@Z` is `AKRESULT __cdecl (unsigned int, unsigned long)`.
- The game keeps 3 listener records (player, camera, composite) in an audio manager. Only the composite one is a
  real Wwise listener (index 0): the player's body position with the camera's orientation.
- Every player's view writes it in turn, so in split screen **it ends up on the last player** (P2 with 2 players),
  not P1.
- Unreal to Wwise coordinates: Wwise = (−X, Z, Y) × 0.01, and the game applies the same scale to the orientation
  vectors.
- Object positions are set for all listeners (index −1), so extra listeners hear objects in the right place.
- Fix part 1: put Wwise listeners 1–3 on the players the game's listener misses, every tick. Detour
  `SetActiveListeners` to OR those bits into any mask that has bit 0.
- Fix part 2: before creating a sound source, the game runs a native "is this position within radius R of one of my
  listeners" check (Steam RVA `0x7BB410`, thiscall; arguments: position, radius, listener-type mask, needs-a-Wwise-
  listener flag, any-vs-all flag). It only knows its own listener, so sounds near the other players were never
  created. Detour it: if the original says no and the check is the "any" kind, say yes when the position is within R
  of another player. The function is found by searching the executable sections for its first 48 bytes, which
  appear exactly once in the Steam exe.

## Build steps
1. Install BmSDK into `Binaries\Win32`, then extract the mod into `BmGame\Mods\` (or use the fork's
   `SplitScreenMod-main` folder).
2. Each fix is one `[Script]` class in `scripts\<area>\*.cs`. Guard everything with `GamePlayers.Count > 1` so solo
   play is unchanged.
3. Before shipping a new API use, check that the member really exists in `BmSDK.dll` (see Gotcha 3). Restart the
   game, then read `BmSDK.log` for `Success! N scripts compiled`.
4. Native work: dump the running exe's image with `ReadProcessMemory` from 0x400000 for SizeOfImage. The on-disk
   `.text` is encrypted, and the exports' RVAs only point at real code in memory. Disassemble the dump with
   capstone, and find callers by scanning for `E8`/`E9` rel32 targets. The dump is for reading only: keep it
   private and outside any repo, and never write it into the game folder or run it (CONTRIBUTING.md, DRM-wrapped
   executables).

## Verification
- The oracle is the human playing 2P on two controllers plus `BmSDK.log`. Every fix logs what it did, for example
  `SplitScreenDeathGuard: P2 died: cause=..., N from P1`, `SplitScreenSkin: P2 slot had ..., set to ...` and
  `SplitScreenAudio: range check found at +0x7BB410`.
- For audio, temporary every-2-seconds logging compared player and camera positions with the game's listener
  records, and read back Wwise's own listener positions and an object's active-listener mask. That showed the
  listener ends on P2, and that the mask fix worked but sounds were still dropped before reaching Wwise.
- Solo was checked by reading a solo session's log: no player-added line and none of the fixes' log lines. That
  only covers the fixes: the original mod's workarounds don't log, and some of them did run in solo (see "Keep solo
  exactly like the normal game" and Gotcha 12).
- **Not verified:** the Clayface mud men (no save there); the Epic Games Store build (other scripts list a separate
  Epic RVA for each hook, but the audio range check is untested on Epic); 3–4 player audio.

## Gotchas
1. **The whole mod stops loading.** **Cause:** one compile error in any script, for example calling
   `SetLocationIgnoringCollision` on `Pawn`; it only exists on `RPawn`. **Fix:** check every new member against
   `BmSDK.dll` metadata before shipping, and read the compile lines at the top of `BmSDK.log` after each start.
2. **Crash when the game calls a redirected function.** **Cause:** BmSDK can't marshal interface-typed parameters
   back (a `NotImplementedException`), e.g. functions taking `RDisruptableInterface`. **Fix:** never redirect a
   function with an interface-typed parameter; redirect its caller instead.
3. **P2 gets P1's suit, or the default suit after a Batman/Catwoman switch.** **Cause:** `SetupPlayerMesh` matches
   the first slot with the same `CharacterName`, and the switch reloads slots with default meshes. **Fix:** at spawn,
   put the player's suit in slot 0 (same character as P1) or their own slot (different character) just before
   `SetupPlayerMesh`. Don't swap meshes on a live pawn.
4. **Instant game over at the Monarch Theatre.** **Cause:** the checkpoint possesses the sword-Batman pawn for every
   player, and P2 takes it from P1. **Fix:** block an extra player from possessing a pawn another player holds.
5. **Black screen with no retry after a co-op death.** **Cause:** calling `Respawn()` inside a
   `TriggerGameOver`/`GameOver` redirect cancels a real game over. **Fix:** only log in those redirects. Let the
   extra player die, then put P1's controller into its dead state with `PawnDied` so the normal game over runs.
   Killing P1's pawn instead also gives a game over, but the wrong player ragdolls (fixed 2026-10-25 in
   SplitScreenMod #26).
6. **P2 teleported to P1 with full health instead of dying.** **Cause:** a "far from P1 = left behind, rescue" rule
   also caught real combat deaths. **Fix:** rescue only during cutscenes, out-of-world falls and crushing.
7. **Sounds silent once the players split up, including P1's own punches.** **Cause:** the single Wwise listener
   follows the last player, and a native range check drops sources far from it before they reach Wwise. Adding Wwise
   listeners alone did **not** fix it (the active-listener mask readback was right, and sounds were still silent).
   **Fix:** extra listeners plus the range-check detour.
8. **Reading the Steam exe on disk shows garbage code.** **Cause:** its code is encrypted on disk. **Fix:**
   reverse-engineer a memory dump of the running process (read-only, and kept private: Build step 4).
9. **The camera aspect fix flickers on and off.** **Cause:** gating on `IsAsyncLoading()`; open-world streaming keeps
   it true. **Fix:** don't add that guard to camera code.
10. **Swapping who is P1 mid-game.** Pairwise `LocalPlayer.SetControllerId` calls worked, but were roundabout.
    **Simpler:** rotate `ControllerId` directly, the way UE3's debug-only `SSSwapControllers` does (it's compiled
    out of shipping builds). The human confirmed it works.
11. **P2 teleported to P1 from across the city whenever P1 finished a fight.** **Cause:** the after-cutscene rescue
    (teleport extra players more than 5000 uu from P1) treated the slow-motion fight finish as a cutscene, because
    it locks P1's controls. **Fix:** while P1 is locked, record which other players are locked too, and only
    teleport those. Story cutscenes lock every player; a fight finish locks only P1. Confirmed in game.
12. **Every player, P1 too, snapped to a spot when Batman slid under a gap, even in solo.** **Cause:** the
    `SetPlayerLocation` redirect moved all players without checking `bForSavingOnly`, which the game sets when it
    only records the spot. **Fix:** do nothing when `bForSavingOnly` is set or with one player, and move only the
    players the game didn't. Confirmed in game.

## Assets
None.

## Cost and time
Several long sessions over 2026-10-12 to 10-25. Each test needs a game restart, because scripts compile only at
start.

## Open questions
- Epic build: does the 48-byte search find the audio range check there?
- Audio with 3–4 players. Listeners 1–3 should cover it, but it's untested.
- The Clayface mud-men retargeting is unverified.
- Does Wwise take the maximum or the sum across listeners in this version? It sounded normal in testing.

## Related and credits
- [etkramer/SplitScreenMod](https://github.com/etkramer/SplitScreenMod), the split-screen mod these fixes build on,
  by the BmSDK authors.
- [BmSDK-AC](https://github.com/Team-BmSDK/BmSDK-AC) (Team-BmSDK, MIT), the C# script loader it runs on.
- [Arkham Knight split-screen](../batman-arkham-knight/splitscreen-one-view-composited-twice.md): on BmSDK-AK with
  two local players, Arkham Knight renders one scene view and shows it in both halves, so per-player camera fixes
  like the ones here don't carry over. Its route renders the second view separately (still in progress there).
