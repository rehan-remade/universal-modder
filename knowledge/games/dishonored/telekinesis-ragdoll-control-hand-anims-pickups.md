---
kind: game
title: "Telekinesis power for Dishonored (2012): controlled ragdolls, impact damage, hand animations, object pickup"
game: "Dishonored"
games_also: []
game_version: "Definitive Edition, Steam app 205100, 32-bit UE3 licensee; same globals as the ghost co-op note (GNames 0x01435674, GObjects 0x01423630)"
platform: windows
engine: unreal
route: native-hook
tools: ["dinput8.dll proxy (own)", "llvm-mingw 20261006 (i686)", "Python 3 (debug-port scripts)", "um win shot/drive/record"]
anti_cheat: "none (single-player); offline only"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["depa00"]
date: 2026-10-17
links: []
tags: [telekinesis, ragdoll, physx, impact-damage, first-person-animation, anim-tree, pickups, particles, sound, wwise, bend-time, hot-reload, ue3, reflection]
---

# Telekinesis power for Dishonored (2012): controlled ragdolls, impact damage, hand animations, object pickup

> A new power in Dishonored (Windows, Steam): hold Mouse4 on a guard or a physics object to lift it, move it
> with the view and the wheel, release to throw. Guards dangle from the torso, take damage from real impacts,
> knock other guards over and get back up if they survive; whale oil tanks explode on impact; pickups
> (grenades, elixirs, ammo, rewire tools) are pulled to the hand and picked up. The left hand plays the
> Possession cast pose while holding and the Windblast push on release; the Possession smoke wraps the held
> object; the Blink charge sound plays on grab, the Windblast gust and a sword whoosh on throw. Native
> in-process DLL (dinput8 proxy) driving the engine through SDK-free UE3 reflection. Verified in the real game
> with debug-port numbers, per-frame logs, screenshots and scripted stress tests.

## Setup
- Dishonored Definitive Edition, Steam app 205100, Windows 11, launched with
  `-windowed -resx=1280 -resy=720 -nostartupmovies` (via `steam -applaunch 205100 ...` so the arguments
  actually reach the game).
- Toolchain: llvm-mingw 20261006 (`i686-w64-mingw32-clang++`), C++20, `-static`, `-Wl,--kill-at`.
- Two DLLs in `Binaries/Win32` (new files only, no game file modified):
  - `dinput8.dll`: proxy + host. Hooks `DishonoredViewportClient.PostRender`, serves a localhost debug port,
    filters the DirectInput mouse wheel, and hot-reloads the logic DLL when it changes on disk (it loads a
    private copy so the build can overwrite the original while the game runs).
  - `DisPowersLogic.dll`: all gameplay (powers, overlay, debug commands).
- Reflection layout, GNames/GObjects discovery and the PostRender `Func` swap are exactly as in
  `knowledge/games/dishonored/ghost-co-op-ue3-reflection-postrender-hook.md`; everything there held for this
  install. That note ran buildid 8335061 under Proton, this one native Windows 11; `Dishonored.exe` has no
  ASLR, so the identical GNames/GObjects addresses point to the same exe build.

## Route and why
- Native in-process DLL, same reasons as the ghost co-op note (cooked packages, no script compiler route).
- Everything runs from the PostRender hook (render time). No per-tick script hook was found (see Gotchas),
  so the design works around render-time limits instead of fighting for a tick hook.
- Hot reload of the logic DLL was decisive: dozens of rebuilds without restarting the game.
- **Related:** the ghost co-op note above (same host/logic DLL split and debug port), and its open question
  about a script event inside the world tick, which Gotcha 4 here probes.

## How the game works (what we had to learn)
**Calling functions.** ProcessEvent with a parameter block filled by property name works for script and
native functions. Subclasses often override with *renamed* parameters (e.g. `DishonoredEmitterPool.SpawnEmitter`
takes `_pEmitterTemplate, _SpawnLocation, _SpawnRotation, _pAttachToActor`; `DisAnimNodeSeqPlayer.PlayAnim`
takes `_bLoop, _fInRate, _fStartTime`; `DishonoredNPCPawn.SetPushesRigidBodies(_bNewPush)`). Always list the
functions of the actual object, not the base class.

**What fails from PostRender.** `Actor.Trace`/`FastTrace` always report nothing/blocked (even 10 uu in empty
space). Not a render-time problem: they fail the same way from inside `GameInfo.Timer` (world tick, see Open
questions), while `Actor.TraceComponent` against one given component works. `PC.Use()` does nothing.
`SetPhysics(PHYS_RigidBody)` is ignored on resting pickups. `ForceUpdateComponents(bCollisionUpdate=true)`,
`SetRBCollisionChannels(Channels)` and `SpawnEmitterMeshAttachment` on a ragdoll bone hit a fatal assert.
(The ghost co-op note calls `ForceUpdateComponents` from PostRender to move its puppet without trouble;
UE3's default is `bCollisionUpdate=false`.) These work: `InitRagdoll`/`TermRagdoll`,
`SetRBLinearVelocity`, `AddImpulse(bVelChange)` on a bone, `SetRBPosition`, `GetBoneLocation`,
`RB_BodyInstance.GetUnrealWorldVelocity`, `SetRBCollidesWithChannel`, `TakeDamage`, `SpawnEmitter`,
particle `SetTranslation`/`SetScale`/`DeactivateSystem`/`KillParticlesForced`, anim `SetAnim`/`PlayAnim`,
`PC.Dis_EquipItemByType`.

**Time (Bend Time).** `WorldInfo.TimeDilation` is ignored. `DishonoredGameInfo` recomputes
`m_fCurrentWorldTimeDilation` / `m_fCurrentPlayerTimeDilation` every frame from `m_BendTimeInfo`
(11 x `BendTimeChannelInfo`, 0x40 bytes: world current/target at +0x10/+0x14, player at +0x1C/+0x20).
Writing one channel slows the world and not the player; channel 9 is not saved (0 and 7 are). The world is
slowed per actor: the emitter pool actor itself gets `CustomTimeDilation` 0.3. A
`DisParticleSystemComponent` follows the time of its `m_pTimeBoundActor`: binding our emitters to the player
pawn keeps them at real speed (measured `AccumTickTime` rate 1.1 vs 0.3 for a level emitter).
`DishonoredEngine.bPauseOnLossOfFocus` and `m_bRequestOpenPauseMenu_FocusLost` can be cleared every frame.

**Targeting without traces.** Walk `WorldInfo.PawnList` / `Pawn.NextPawn` (NPCs) plus a once-a-second list of
`KActor`s from GObjects, and pick the one closest to the view direction inside a ~10 degree cone (no line of
sight).

**Ragdolls of living NPCs.**
- After `InitRagdoll` a living NPC's mesh stays in its pawn RB channel (54) and collides only with
  `DisPawnChannel*`: it flies through walls. A death ragdoll made by the game uses `RBChannel` 16 (DeadPawn)
  and `RBCollideWithChannels` = 0x00050221 (Default, GameplayPhysics, SeveredLimbs, DeadPawn,
  ClothingCollision: bits 0, 5, 9, 16 and 18, the stock UE3 `ERBCollisionChannel` positions, where bit 9 is
  `RBCC_Untitled3`). We set that channel and write that raw mask; `SetRBCollidesWithChannel(Default, true)`
  then pushes the whole container to PhysX (`SetRBCollidesWithChannel(20..26)` does not reach the
  DisPawnChannel bits).
- Do NOT add `BlockingVolume`: the level's invisible player-blocking walls stop thrown bodies mid-air.
- A living pawn has a kinematic push body (`PhysicsPushBody` = the `BounceBox` body,
  `bPushesRigidBodies`); death clears both. `SetPushesRigidBodies(false)` removes it.
- Ragdolls we create are never ended by the game: survivors stay on the ground forever unless the mod
  calls `TermRagdoll` itself.
- `TermRagdoll` puts the pawn back in its standing animated pose around the pelvis. Near the floor the legs
  are then inside the floor, and a ragdoll re-created from that pose (or the standing pawn) falls through
  the world (health ends near -1000). Lift first: after re-creating, move the new bodies up with
  `SetRBPosition` before the next physics step; for a get-up write `Location.z += 90` and
  `PHYS_Falling` (only the Location field: no component update calls from render time).
- City guard ragdoll bodies: Root_jnt, spine_1_jnt, spine_3_jnt, neck_jnt, arms, legs, feet, Back_pan_*;
  no Torso_jnt body. Body lookup: `PhysicsAsset.BodySetup[i].BoneName` -> `PhysicsAssetInstance.Bodies[i]`.

**The ~10 m freeze (cause NOT found).** Ragdolls we create stop dead when they get ~10-11 m from the player
sideways or ~7.7 m up, and hang there forever (re-grabbing them and letting go returns them to the same
spot). Ruled out: world collision (persists with every channel off and `BlockRigidBody` off), BlockingVolume,
channel mask, push body, Bend Time, particles, our own tracking code, `m_bFrozen`/bone springs (all off on
the hanging bodies). `TermRagdoll` + `InitRagdoll` (plus collisions) at the hang point frees it, and it then
flies on past 25 m. Re-creating it at grab or at throw time does not help. Workaround in use: detect a body
that was moving fast and is stopped in the 850-1450 uu band from the player, re-create it there and give
back its pre-stop velocity. It works most of the time but some re-created ragdolls still fly off oddly.

**Driving a held ragdoll.** Spring-damper on a velocity state (K 140, D 15, max 6000 uu/s) toward
`camera + view * distance (+40 uu up for guards)`. With bone drive, only the torso body gets
`AddImpulse(target - measured, bVelChange=true)`, so arms and legs dangle (visible in screenshots: legs trail
when swinging the view). Physics answers commands 2-3 frames late.

**Impact damage.** Per-frame velocity from Location deltas is noise (physics steps are not render frames:
1300 -> 9400 uu/s on consecutive frames of a smooth pull). Use velocity over a ~60 ms window. A wall hit
spreads over ~6 frames of that windowed speed (4155 -> 3767 -> 3235 -> 2601 -> 2020 -> 1544), so look for
speed below 60 % of the max of the last 150 ms with a drop over 900 uu/s, collect for 100 ms, apply one
`TakeDamage(DisDamageType_RagdollImpact)` with damage (drop - 700) / 30. While held, compare against the
spring's command (shifted ~30 ms) instead, and require the body to have really been moving (a guard pinned
against a wall while the spring winds up is not a hit). Full throws into a wall: 128-144 damage.

**First-person left-hand animations.** Player power anims live in `Ply_Powers_as` (object names are generic,
the real name is `AnimSequence.SequenceName`): `Powers_Cast_Blink_In/Loop/Out`,
`Powers_Cast_Possession_In/Loop/Out`, `Powers_Cast_Windblast`, ... The player tree has no AnimNodeSlot. Its
`PlayerStack` (ArkAnimNodeStack) has four overlay channels `PlayerSeq1..4` (DishonoredAnimNodeSeq) that
override the whole body. The node `LeftArmFilter` (DisAnimNodeBlendPerBone) takes the left arm from its
`Target` input. Rewiring `LeftArmFilter.Children[1].Anim` to `PlayerSeq1` playing a sequence, and putting the
original pointer back afterwards, animates only the left arm in any state. Find nodes with
`AnimTree.FindAnimNode(name)`. Set `bNoNotifies` on that channel: the Possession anims start a looping sound
from a notify that only `Possession_Out` stops.

**Freeing the left hand.** Real inventory = `pawn.m_pInventory` (the `pInventory` subobject is a different
object). Left-hand slot = `m_EquipUsageInfo[2].m_iEquippedSlot` (`EDisEquipUsage`: 0 None, 1 Primary,
2 Secondary); items in `m_Slots[i].m_pItem`. Swap with `PC.Dis_EquipItemByType(itemClass, 2)` (usage 0 gives
inconsistent results). The swap has its own arm animation: rewiring the arm before it finishes left the
crossbow attached to the hand.

**Objects.** Whale oil tank = `DisWhaleOilBattery` (KActor family, PHYS_RigidBody); our impact damage makes
it explode by itself. Placed pickups (`DisElixirHealth`, `DisElixirMana`, `DisStatPickup`,
`DisAbstractItemPickup`, `DishonoredInventoryPickup`) rest with PHYS_None and a fixed body: write
`Physics = 10` (PHYS_RigidBody), call `StaticMeshComponent.BodyInstance.SetFixed(false)` and
`WakeRigidBody`. They implement the native `IDisInteractableInterface` (no script functions): the game's own
prompt ("[F] Pick up") appears when the held object sits exactly under the crosshair, and the real use key
picks it up while held.

**Effects borrowed from powers** (already loaded in missions): `Vfx_GamePlay.Possession.PossesTarget_Human_01`
on the held object (scaled to its `Bounds.SphereRadius` / 90), `Possession_HandCast_01` at the hand (it loops:
stop it), `Windblast_lvl1` on throw, `Windblast_GroundImpact_01` on hard impacts. Take the component from
`SpawnEmitter`'s return value (with the renamed parameters).

**Sounds (Wwise).** Dishonored plays sounds through Wwise: `AkEvent` objects (e.g.
`Snd_Power_Player.Snd_Power_P_Blink_Start`) posted on an actor with the native `Actor.PostAkEvent(InAkEvent)`,
which works from PostRender. There is no generic stop call: looping events need their own paired stop event,
so for a power prefer one-shot events and check each one. We play `Snd_Power_P_Blink_Start` (the Blink
charge, one-shot ~3 s) on grab, and on throw `Snd_Pwr_P_WindBlast_lvl_1` on the player plus
`Snd_Weapon.Snd_Weapon_Sword_Whooshe_ak` on the thrown actor (both one-shot). `Snd_Power_Possession_In_Lvl1`
(one-shot ~2 s) also works but felt too repetitive on every grab. Find events with a name search over
GObjects (`AkEvent` class).

**Mouse wheel.** The game reads the mouse through DirectInput, so a low-level Windows hook does not stop the
weapon wheel. Patching the vtables of `IDirectInput8::CreateDevice` and, for `GUID_SysMouse`,
`GetDeviceState` (zero `lZ`) / `GetDeviceData` (drop `DIMOFS_Z` records) while the power is held does.

## Build steps
1. Build both DLLs with llvm-mingw (host: `-lws2_32`; logic: `-lshlwapi`), `-static -Wl,--kill-at`.
2. Copy `dinput8.dll` (game closed) and `DisPowersLogic.dll` into `Binaries/Win32`. Later logic builds can be
   copied while the game runs; the host reloads them within a second.
3. Launch with `steam -applaunch 205100 -windowed -resx=1280 -resy=720 -nostartupmovies`.
4. Press a key on the title, Continue, press a key on the loading screen.

## Verification
- Debug port on 127.0.0.1 (find/props/funcs/call/set, struct and array dumps, per-frame watch logs) to read
  engine state and call functions while the game runs; helper scripts for grab/throw trajectories.
- Screenshots of every visual change (dangling guard, hand poses, crossbow restored, FX scale, tank
  explosion) checked one by one.
- Scripted stress test: 3 rounds x 5 throws in different directions + held wheel-out + get-ups, no crash.
- Sounds: game-only audio captured with `um win record` (process loopback) while posting each event from the
  debug port, then loudness / band energy per 125-250 ms to see when a sound starts and whether it ends.
- Crashes diagnosed from the game's minidumps (module list + exception address -> symbol of the logic DLL).
- Not verified: other NPC types than city guards (bone names may differ), rats (crowd agents, not pawns),
  other gadgets than the crossbow for the hand swap, controllers.

## Gotchas
1. **Symptom:** F6 slow motion changes nothing. **Cause:** `WorldInfo.TimeDilation` is ignored.
   **Fix:** write a `m_BendTimeInfo` channel (9 is not saved).
2. **Symptom:** traces never hit anything. **Cause:** not found. `Trace`/`FastTrace` called through
   ProcessEvent fail in every context tried (PostRender and `GameInfo.Timer`), while `TraceComponent` hits
   through the same path (but see the native-index lead in Open questions). **Fix:** cone targeting over
   `PawnList` / KActors.
3. **Symptom:** native call "returns nothing". **Cause:** a subclass override with renamed parameters; unknown
   names are silently ignored. **Fix:** dump the object's own functions and fill both names.
4. **Symptom:** `GameViewportClient.Tick` hook never fires; a probe of 659 script functions on the player
   objects saw only `HUD.PostRender` and `GameInfo.Timer`. **Cause:** gameplay is native. **Fix:** stay in
   PostRender. `GameInfo.Timer` runs only once a second, and traces fail there too (Open questions).
5. **Symptom:** thrown guard flies through walls. **Cause:** living-pawn RB channel/mask. **Fix:** DeadPawn
   channel + raw mask 0x00050221.
6. **Symptom:** thrown guard stops mid-air against a building front. **Cause:** BlockingVolume channel.
   **Fix:** never enable it.
7. **Symptom:** thrown/held guards freeze ~10 m out and hang. **Cause:** unknown (see above). **Fix
   (workaround):** re-create the ragdoll at the hang point and restore its velocity.
8. **Symptom:** guards fall under the map after a re-created ragdoll or a get-up. **Cause:** standing pose
   legs inside the floor. **Fix:** lift with `SetRBPosition` / Location before the next step.
9. **Symptom:** `Fatal error!` on grab. **Cause:** `SpawnEmitterMeshAttachment` on a ragdoll bone from render
   time. **Fix:** pooled emitter moved with `SetTranslation`.
10. **Symptom:** `Fatal error!` during an unstick while held. **Cause:** cached `RB_BodyInstance` of the old
    ragdoll. **Fix:** cache keyed on the current `PhysicsAssetInstance` and non-null `BodyData`.
11. **Symptom:** access violation in our frame code. **Cause:** a destroyed actor's memory was freed.
    **Fix:** check the pointer is readable before reading `UObject::Index`.
12. **Symptom:** `Fatal error!` lifting an actor. **Cause:** `ForceUpdateComponents(bCollisionUpdate)` from
    render time. **Fix:** write Location only.
13. **Symptom:** `Fatal error!` setting collision channels. **Cause:** `SetRBCollisionChannels`. **Fix:**
    write the container and call `SetRBCollidesWithChannel(Default, true)`.
14. **Symptom:** held guard "dies" without hitting anything. **Cause:** false impacts from per-frame noise
    and command lag. **Fix:** windowed velocity, lag-shifted command, require a real measured peak.
15. **Symptom:** thrown guards take no damage. **Cause:** confirming a hit against an expectation derived from
    the already-collapsed measurement. **Fix:** compare with the max of the last 150 ms.
16. **Symptom:** wheel still switches weapons. **Cause:** DirectInput, not window messages. **Fix:** filter
    `GetDeviceState`/`GetDeviceData` in the dinput8 proxy.
17. **Symptom:** whole body animates (crossbow arm too). **Cause:** stack channel overrides all bones.
    **Fix:** rewire `LeftArmFilter`'s Target input.
18. **Symptom:** crossbow stays glued to the open hand. **Cause:** rewired before the equip swap finished.
    **Fix:** wait for the slot change + ~0.6 s.
19. **Symptom:** endless sound after throwing. **Cause:** Possession loop sound from an anim notify.
    **Fix:** `bNoNotifies` on the channel.
20. **Symptom:** dark globs stay where things were grabbed. **Cause:** `Possession_HandCast_01` loops.
    **Fix:** stop it (and kill pooled leftovers) on release.
21. **Symptom:** held pickups can't be picked up. **Cause:** held above the crosshair. **Fix:** no lift for
    objects; auto-press the use key when pulled close (key held ~80 ms; a same-instant down/up is missed).
22. **Symptom:** elixirs/ammo can't be grabbed. **Cause:** PHYS_None + fixed body. **Fix:** `Physics = 10`
    (PHYS_RigidBody) + `BodyInstance.SetFixed(false)`.
23. **Symptom:** test results made no sense. **Cause:** the human was playing at the same time.
    **Fix:** ask for hands-off windows during scripted tests.
24. **Symptom:** effects "cast from the left hand" appear on the right, by the sword. **Cause:** UE3 is
    left-handed (X forward, Y right, Z up), so `view x up` points to the LEFT; we subtracted it as if it
    pointed right. **Fix:** add it (or use `up x view` for right).
25. **Symptom:** the game-audio capture is pure silence. **Cause:** the game mutes when its window is not in
    the foreground, and on the Game Over screen (a guard alerted by the tests killed the player). **Fix:**
    focus the window right before recording (ask the human first, and not while they're typing) and keep the
    player safe; check a screenshot when a capture is flat zero.

## Assets
None created. All effects and animations are the game's own, used at runtime; nothing extracted or shipped.

## Cost and time
One long working day (about 9 hours), roughly 60 hot reloads and 8 game crashes along the way.

## Open questions
- The real cause of the ~10 m freeze of script-created ragdolls (a native system tied to living NPCs or to
  ragdolls not started by the death path?). Finding it would remove the unstick workaround.
- A natural get-up animation instead of `TermRagdoll`.
- A per-tick hook for physics work. `GameInfo.Timer` was tried (2026-10-17, same build): it fires exactly
  once a second (15 calls in 15 s), and with its `Func` swapped, `Actor.Trace` from inside it still returns
  None with HitLocation (0,0,0), the same as from PostRender. So traces do not fail because of render time.
  The same ProcessEvent path works for `Actor.TraceComponent`: against the player's CollisionCylinder it hits
  (z 4099.5, normal 0,0,1) and returns `true`. World line checks fail for every variant tried: `Trace`
  returns None with `ExtraTraceFlags` 0-15, with a box extent, with bTraceActors 0 and 1, and called on the
  pawn, the PC or WorldInfo, and `FastTrace` returns false ("blocked") even for 50 uu of empty air 5 km above
  the map. Either Dishonored routes world queries some other way, or the call itself goes wrong (next
  item). `SetLocation` from the Timer was not tested.
- A lead on the traces, not tried: every call that fails quietly here and in the ghost co-op note is a native
  with a fixed index in UDK's `Actor.uc`: `Trace` (277), `FastTrace` (548), `SetLocation` (267),
  `SetRotation` (299), `Move` (266), `Destroy` (279) and `SetPhysics` (3970). The natives that work have no
  index: `TraceComponent`, `Spawn`, `SetHidden`, `ConsoleCommand`, `InitRagdoll`, `SetRBPosition`,
  `AddImpulse`. Public UE3 SDK generators special-case such functions when calling them through
  ProcessEvent: TFL's generator sets `UFunction::iNative` to 0 for the call and restores it after, and
  BmSDK's generated wrappers also clear `FUNC_Native`. Check `iNative` on these functions in this build, and
  try the same around one `Trace` call.
- Other NPC skeletons, rats (crowd agents), other gadgets.
