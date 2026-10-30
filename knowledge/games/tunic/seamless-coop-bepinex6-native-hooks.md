---
kind: game
title: Seamless co-op for TUNIC (BepInEx 6 IL2CPP, native hooks, autonomous 2-PC testing)
game: TUNIC
games_also: []
game_version: Unity 2020.3.17f1, IL2CPP (Steam 553420, build id 10650562)
platform: windows
engine: unity-il2cpp
route: native-hook
tools:
- BepInEx 6.0.0-pre.1 (UnityIL2CPP x64)
- MonoMod.RuntimeDetour NativeDetour (ships in BepInEx/core)
- LiteNetLib 1.2.0
- ilspycmd 8.2.0.7535
anti_cheat: none found by um scan
status: working
agents:
- Claude Code (Opus 5.5)
humans:
- Freddy
date: '2026-10-12'
links:
- https://github.com/BepInEx/BepInEx/releases/tag/v6.0.0-pre.1
- https://github.com/silent-destroyer/tunic-randomizer
- https://github.com/AfroPK/tunic-seamless-coop
tags: [co-op, multiplayer, netcode, il2cpp, native-hook, harmony, bosses, autopilot, automated-testing]
---
# Seamless co-op for TUNIC (BepInEx 6 IL2CPP, native hooks, autonomous 2-PC testing)

> A 2–8 player co-op mod for TUNIC as a BepInEx 6 IL2CPP plugin: player puppets with smooth animation, shared
> world flags, shared inventory/money, synced pots/coins/chests, per-enemy ownership with hit forwarding,
> scene transitions and death/respawn. It runs in the real game: the features were verified on two physical
> PCs plus a third game instance by an in-mod test autopilot driven over files/SSH, checked via state
> files, logs and screenshots the agent looked at. Verification lists what wasn't.

## Setup
- TUNIC (Steam 553420), Unity 2020.3.17f1, IL2CPP, product folder `AppData\LocalLow\Andrew Shouldice\Secret Legend`.
- BepInEx **6.0.0-pre.1 UnityIL2CPP x64** (same as the TUNIC Randomizer). Runtime is Mono → target `net472`.
  First launch generates interop assemblies in `BepInEx/unhollowed` (UnhollowerBaseLib, not Il2CppInterop).
- .NET 8 SDK; `ilspycmd` latest fails on .NET 8 → `dotnet tool install -g ilspycmd --version 8.2.0.7535`.
- LiteNetLib 1.2.0 (UDP, MIT) shipped next to the plugin.
- **Co-op scope.** Every player runs their own copy of TUNIC. LiteNetLib connects straight to the host's IP and
  port, and the host relays to the others. No game traffic goes through Steam networking or any other online
  service. Since v0.2.0 the mod also does a few things online, each behind a config switch: it asks the host's
  router to forward the port (UPnP), looks up the host's public address with one STUN request
  (`stun.l.google.com`), can use a self-hosted introducer that only exchanges addresses, checks GitHub once per
  launch for a newer release, and in a Steam copy sets Steam rich presence, so friends get "Join Game" with the
  join code in its `connect` string.

## Route and why
BepInEx plugin + **native code hooks**. The mod's hooks are MonoMod `NativeDetour`s on the IL2CPP methods'
native code, because an early Harmony attempt seemed not to fire. A later re-test showed Harmony **does** work
on this build (Gotcha 1), so either is fine for new work. World state is mostly **polled**, not hooked, because
hooks on the `SaveFile.SetInt`/`SetFloat`/`SetString` setters never saw the game's own writes (Gotcha 1).

## How the game works (what we had to learn)
- **Player**: `PlayerCharacter.instance` (static); `PlayerCharacter : Creature`; `Creature.cachedAnimator`;
  god mode for tests: static `PlayerCharacter.DebugInvincible`.
- **World state** is a flat KV store: `SaveFile.intStore/floatStore/stringStore` with `SetInt/SetFloat/SetString`;
  `StateVariable` wraps it (`NotifyAllSubscribers` wakes listeners). Opened chests = `"chest open <chestID>"`;
  inventory mirrors to `"inventory quantity <Item>"`; money item is `MoneySmall`. Per-player keys include
  `playtime`, `last spawn *`, `last campfire *`, `bloodstain *`, `hp_lost`, `Has Ever Died`.
- **Inventory**: `Inventory.itemList` (116 items), `Item.Quantity` get/set, `Inventory.GetItemByName`.
- **Coins**: pooled `ItemPickup`s: `CoinSpawner.poolList[].pool[]` (one `PooledFX` per denomination, value =
  `quantityToGive`), `CoinSpawner.SpawnCoins(value, pos)`, `PooledFX.GetNext(pos)`.
- **Breakables**: `SmashableObject` (`smashed`, `smash(force)`, `minCoinDrop/maxCoinDrop`), a
  `PermanentStateByPosition` → identify by position.
- **Chests**: `Chest` (`chestID`, `IInteractionReceiver_Interact`, coroutine class `_openSequence_d__35`);
  the opened key is written at open time. `BloodstainChest` is your dropped money after death.
- **Monsters**: `MonsterManager.instance.monsters`; `Monster.runtimeStableID.ID` is **identical across
  machines** (verified, 60/60). `Creature.hp` (setter clamps to maxhp), `IsDead`,
  `IDamageable_ReceiveDamage(dmg, poise, force, freeze, poison)`; `MonsterManager.checkMonster` deactivates
  monsters far from the *local* player.
- **Scenes**: `ScenePortal` (`destinationSceneName`, `id`, trigger collider); `ScenePortal.DepartToScene(runner,
  whiteout, duration, scene, id, pauseTime, delay)` is the clean programmatic transition to a connected area
  (for warps, see "Bosses, runtime spawns and sleepers").
- **Input**: InControl. `PlayerInput.Actions` (PlayerCharacterActionSet); gamepad bindings read at runtime:
  InteractDodge=Action1, Item1=Action3, Item2=Action4, Item3=Action2, Flask=RB, Shield=RT.
- **Title**: `TitleScreen.__Continue()/__NewGame()`; `FileManagementGUI.LoadFileAndStart(file)`.

## Build steps
1. Install BepInEx pre.1 into the game, run once.
2. `dotnet build src/TunicCoop -c Release -p:TunicDir=<game> -p:Deploy=true` (references `BepInEx/core` and
   `BepInEx/unhollowed`; copies `TunicCoop.dll` + `LiteNetLib.dll` to `BepInEx/plugins/TunicCoop`).
3. Architecture: `Net` (LiteNetLib star, host relays), `Puppet`+`Visibility` (player mirrors),
   `WorldSync` (poll + deltas), `CoinSync`, `SmashSync`, `ChestSync`, `MonsterSync`, `NativeHook`, `Autopilot`.

## Verification
An **in-mod autopilot** (`Debug.EnableAutopilot`): reads `BepInEx/coop_test/cmd.txt`, writes
`results.txt`/`state.json`, takes screenshots, drives a virtual InControl gamepad (`new InputDevice`,
`InputManager.AttachDevice`, values pushed in `InputManager.add_OnUpdateDevices`). Second PC driven over SSH
(file append + scp). Suite of ~40 checks, each from a fresh session (save reload): presence (puppet error
0.00 m both ways), coins (3 race scenarios, exact money), chests, pots, enemy ownership/positions/kills both
ways, enemies attacking the remote player (real hp loss), scene transitions, death + bloodstain recovery,
3 players. v0.2.0 grew it to ~106 checks: five bosses and the Cathedral gauntlet (players warped in, see
below), host rules, revive and bleed-out, pings/chat, shared camera, go-to-teammate, join codes, rejoin after a
simulated crash and a NAT punch-through relay. The last full run: 101/106; the 5 failures were boss-test setup
(fixed and re-run per boss). **Not verified**: The Heir (needs an endgame save), >3 players, UPnP on a router
that supports it, Steam "Join Game" (tests start the exe outside Steam).

The autopilot's input is a virtual device inside the game, so it never moves the OS mouse or keyboard. The
second PC was set up with the human (they authorized the SSH key); gotcha 5 says what a remote launch does
there. The same command-file pattern is written up in
`knowledge/techniques/driving-a-game-from-a-mod-side-command-file-lab-profile-wake.md`.

## Gotchas
1. **"Harmony never fires" was wrong; hooks on `SaveFile.SetInt` miss the game's writes.** The first attempt
   saw 0 calls on `Chest.Interact`, a coroutine `MoveNext` and `SaveFile.SetInt`. **Re-test**, patched exactly
   like the TUNIC Randomizer (`harmony.Patch(AccessTools.Method(...), postfix: new HarmonyMethod(...))`,
   counting postfixes, no native detour on the same methods): `PlayerCharacter.Update` 57,941 calls,
   `Chest.IInteractionReceiver_Interact` 1 per chest opened by the player, `Chest._openSequence_d__35.MoveNext`
   221, `SaveFile.SetInt` **0** while the chest wrote `chest open 15 = 1`. So pre.1's `FastNativeDetour` on the
   `MethodPointer` catches native and vtable callers. The first result was most likely a test that never really
   opened a chest: in the re-test the fox first stood *behind* the chest and Interact never ran. For the
   setters, our explanation is that `SetInt` and friends are tiny statics inlined into their callers, where no
   hook on them sees the write (not checked in the disassembly); either way, poll the stores instead. Don't put
   Harmony and a `NativeDetour` on the same method. **Native alternative (what the mod uses):** `NativeDetour`
   on `*(IntPtr*)NativeMethodInfoPtr_<method>` (first field of Il2CppMethodInfo = methodPointer); delegate
   `ret fn(IntPtr self, args…, IntPtr methodInfo)`; Win x64: Vector3 *args* by pointer, Vector3 *return* via a
   hidden first-arg buffer. Keep delegates alive. Verified with a counter on `PlayerCharacter.Update`
   (15k calls).
2. **Injected MonoBehaviour crashes the game at load** (native, nothing logged) after adding an iterator method
   and a `Nullable<Vector3>` return to the class. **Fix:** keep `ClassInjector` types to simple signatures;
   helpers in plain static classes.
3. **Exclusive fullscreen freezes unfocused** (even `Application.Quit` never completes; process stuck).
   **Fix:** test launches `-screen-fullscreen 0 -screen-width 1280 -screen-height 720`; set
   `Application.runInBackground` every frame; `InputManager.SuspendInBackground=false`.
4. **Relaunched game ran without BepInEx.** Child processes inherit `DOORSTOP_*` env vars and Doorstop skips.
   **Fix:** clear them before `Process.Start` (self-restart). Use `UseShellExecute=true` or the child's
   inherited handles hang Unity's quit.
5. **SSH can't start a windowed game.** Session 0. **Fix:** one-shot `schtasks /create … /it` → `/run` →
   `/delete` (date format may be yyyy/mm/dd); afterwards the game restarts itself from inside the session.
   Ask the human first: `/it` starts the game on the desktop of whoever is logged in on that PC.
6. **`ScreenCapture.CaptureScreenshot` is stripped** ("Method unstripping failed") and **`Camera.allCameras`
   throws** `ObjectCollectedException`. **Fix:** `FindObjectsOfType<Camera>`, render main + overlay
   (Depth/Nothing clear) cameras into a RenderTexture, `ReadPixels`, `ImageConversion.EncodeToPNG`.
7. **Inputs ignored right after loading.** Loading a save plays an island camera flyover. **Fix:** wait until
   `Camera.main` is < 70 m from the fox (gameplay camera sits ~50 m away). `SceneLoader.Progress` parks at 0.9.
8. **Puppet shows every weapon/effect at once.** Prefab children are toggled by scripts the puppet doesn't
   have. **Fix:** sync per-child-path (FNV hash) active/renderer/emitting flags; send as a separate reliable
   delta message (the full 303-node table blew the ~1.4 KB unreliable MTU).
9. **Roll lags/offsets on puppets.** Roll is root motion + an Animator *trigger*. **Fix:** a component with an
   empty `OnAnimatorMove` (consumes root motion) + 100 ms snapshot interpolation + immediate send on animator
   state change + crossfade at the right offset.
10. **Money double-paid / diverged.** Polling item deltas raced with remote applies; game-paid coin pickups
    couldn't be deduplicated. **Fix:** shift the baseline by the applied delta; while connected set every coin's
    `quantityToGive=0` and credit once via an owner-arbitrated claim (first claim wins).
11. **Mirrored enemies all died instantly.** `hp = 9999` sentinel clamped to maxhp (10) → read as 9989 damage.
    **Fix:** pin mirror hp to the owner's streamed hp; damage = drop below the pin.
12. **Enemies won't attack the non-host.** Redirecting `get_playerOrBaitWorldPosition`, NavigatingMonster
    destination/facing, `ReceiveBroadcastAggro` all failed; `checkMonster` deactivates monsters far from the
    local fox. **Fix:** per-monster ownership by proximity with owner-driven handoff (≥4 m hysteresis): the
    unmodified AI then chases its local fox = the nearest player.
13. **Blue fox in Sword Cave on one PC only** = a TUNIC ghost-fox NPC tied to that save's progress, not a mod
    bug (prove by entering alone). Separately, tether-wand windup tentacles (own Animators) render as blue
    wisps on puppets and the real fox's hiding mechanism wasn't found → hidden on puppets.
14. **Test harness traps:** a steering command must stop on scene change (it walked the fox back out of the
    door it entered); multi-word scene names; dead monsters leave `MonsterManager.monsters`;
    `BloodstainChest` steals the interaction near your death spot; PowerShell `@(f) + @(g)` vs string concat.

## Bosses, runtime spawns and sleepers (v0.2.0)
- **Warp anywhere:** static `Cheats.CheatWarpToPortal(scene, fullId)` arrives at the portal whose
  `ScenePortal.FullID` (`<destinationScene>_<id>`) matches. `DepartToScene` from an unrelated area has no arrival
  portal and drops the fox into the void. List FullIDs by warping with an empty id and reading the scene's
  `ScenePortal`s before the fall.
- **Bosses are ordinary `Monster`s** (`Spidertank`, `Librarian`, `ScavengerBoss`, `Knightbot`, `Foxgod`); the
  Guard Captain is a 50 hp `Skuladin` named by a `BossAnnounceOnAggro`. Never hand an engaged boss (hp < max or
  aggroed) to another player: its phase state only exists in the owner's game. Defeat flags are plain SaveFile
  ints (`SV_Fortress Arena_Spidertank Is Dead`, `Librarian Dead Forever`, `SV_ScavengerBossesDead`,
  `SV_Archipelagos Redux TUNIC Knight is Dead`, `SV_Forest Boss Room_Skuladot redux Big`).
- **Mirrors replay attacks.** A mirrored boss's own explosions damage it on the mirror machine. Mirrors must
  never decide their own damage or death: forward the local player's hit from the damage hook, keep the mirror
  at ≥1 hp, and die only when the owner says so. If that message lands in post-hit invulnerability, call
  `Monster.Die()` directly.
- **Runtime spawns** (boss adds, `(Clone)`s) have no `RuntimeStableID`: the spawning machine names them; others
  pair by name + distance or instantiate a copy from a same-named monster/prefab.
- **Sleepers** (Cathedral wave altars, ambushes) are pre-placed and inactive until a trigger in one game. An
  object that never ran Awake has `Monster.runtimeStableID == null`: read the component and derive
  `buildIndex * 1e6 + intraSceneID`, wake your copy, mirror the claimer's.
- **Defaults aren't progress:** a scene writes new SaveFile keys = 0 on load; syncing them reset a teammate's
  altars. `Creature.ModifyDefensePower` doesn't affect direct `IDamageable_ReceiveDamage`: scale damage in
  your own hook. `DownloadHandlerBuffer` is stripped (use `HttpWebRequest` + TLS 1.2); `steam_api64.dll`
  (needed for rich presence) sits in `Tunic_Data/Plugins/x86_64`, where Mono's DllImport misses it
  (`GetModuleHandle` + `GetProcAddress`).
- **Test rig traps:** saves autosave in boss arenas, so the next session loads there; fast chasers close any
  distance you set up (freeze the boss's AI on its owner first); config changes made by one test persist.

## Assets
None (no new art).

## Cost and time
One long agent session over ~2 days, plus two short human interventions (authorizing an SSH key, ending one
hung process the sandbox couldn't kill).

## Open questions
- The Heir (`Foxgod`) fight and its cutscenes under the boss rules (needs an endgame save).
- Internet play without port forwarding now uses UPnP when the router allows it, or a self-hosted relay
  (LiteNetLib `NatPunchModule` introducer) that only exchanges addresses; game traffic stays a direct
  connection. Neither has been tried across two real NATs yet.
- Why the tether-wand windup tentacles are invisible on the real fox (renderer flags, forceRenderingOff,
  bones, bounds, animator state, property blocks and materials were all identical).
