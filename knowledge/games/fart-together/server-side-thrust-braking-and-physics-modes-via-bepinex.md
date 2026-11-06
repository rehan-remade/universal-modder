---
kind: game
title: Host-side thrust, braking and physics modes via BepInEx
game: Fart Together
games_also: []
game_version: "Fart Together Demo (Steam app 5208630), buildid 26052013"
platform: windows
engine: unity-mono
route: managed-patch
tools: ["BepInEx 5.4.23.3", "HarmonyX", "ilspycmd 9.1", "UnityPy 1.25.4"]
anti_cheat: "none (no anti-cheat DLLs found by um scan)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["TolkoDev"]
date: '2026-10-21'
links: []
tags: ["physics", "server-authoritative", "fishnet", "harmony", "unity-mono", "boat", "thrust"]
---
# Host-side thrust, braking and physics modes via BepInEx

> A BepInEx/HarmonyX mod for Fart Together Demo that rebalances the boat's thrust and
> braking, adds physics modes (vanilla / boost / turbo) switchable in-match, and adds
> cosmetic visual effects (growing eyes, a flushed rear) driven by the replicated gas
> state. Everything physics-related is server-authoritative: the host's copy computes the
> motion and the clients only receive the replicated transform, so other players should see
> the effect without installing anything (read from the code; no second player was available
> to test it). Verified on the host by in-game HUD readings and BepInEx log lines.

## Setup
- Game: Fart Together Demo, Steam app 5208630, buildid **26052013** (the demo updates itself;
  the buildid is what these notes apply to).
- Engine: Unity **6000.4.10f1**, **Mono** (not IL2CPP). Game logic lives in one managed
  assembly, `Fart Together_Data/Managed/Assembly-CSharp.dll` (~1.1 MB).
- Loader: BepInEx **5.4.23.3** + HarmonyX (Harmony 2.x), plus the Unity Doorstop proxy
  (`winhttp.dll` + `doorstop_config.ini`) in the game root.
- Plugin target: .NET Framework **4.7.2**, `Private=false` on every game/BepInEx reference
  so nothing is copied next to the plugin.
- Tooling on the machine: `ilspycmd 9.1` (decompile, 509 .cs files), **UnityPy 1.25.4** (read
  the asset bundles), `um scan` (fingerprint the install), Python 3.11.
- OS: Windows 11. No anti-cheat: `um scan` found none, and the game was not modified in any
  way that touches ownership or competitive rules.
- **Multiplayer:** Fart Together is online co-op: 2-4 players steer one shared boat, in a
  Steam lobby that one player hosts. The mod changes that boat's physics for everyone in the
  match, so it's for single player or a lobby you host with friends who agreed to it. Don't
  use it in someone else's lobby.

## Route and why
**managed-patch** (BepInEx + HarmonyX) rather than asset-only or native hooking:
- the whole gameplay simulation is plain managed IL in `Assembly-CSharp.dll`, and the
  interesting knobs (`GasRampSeconds`, `MinGasForce`, `GlideFriction`, the gas force) are
  ordinary fields on a handful of components;
- the game ships with no loader and no anti-cheat, so a managed plugin needs nothing
  beyond the standard Doorstop install;
- asset work alone cannot change the motion: the boat's physics is code, not data.

The decisive architectural fact (see below) is that the **host's copy of the game computes
the physics**. A client that has no mod at all should still see the boosted boat move
correctly, because the motion arrives as a replicated transform (from the code; untested,
see Verification). The mod therefore only needs to be installed on the host; a client
install is only needed for the purely visual extras.

## How the game works (what we had to learn)
- **The race simulation is a FishNet network tick, and it only runs on the server.**
  `BoatPhysicsController.TimeManager_OnTick` (and the same hook on the other gameplay
  components) begins by returning unless the instance is server-initialised. Everything
  the game does to the boat — the gas thrust, the friction, the speed clamp — therefore
  happens **only on the host**. Clients get the boat's replicated transform plus a few
  replicated values.
- The tick is not 30 Hz: the TimeManager ticked at **64 Hz** on the test machine
  (measured `TickDelta` 0.0156 s).
- `RaceState.NormalGasForce` and `RaceState.SwirlBias` are `SyncVar<float>`: the gas strength
  and the swirl strength travel to every client.
- `RaceState.SetGasForce` **clamps the gas force to 100…6000 N** inside the setter. Any
  multiplier above that is silently discarded — the value you asked for never exists.
- The thrust is applied at `BoatPhysicsConfig.GasForceDrop`, which is the *Y of the centre of
  mass of the Rigidbody*; negative means below the centre, so the thrust produces a nose-up
  torque and **not** lift. The boat cannot take off from the gas alone.
- The head "pop" is `GasVisuals`: it lerps the head bone's `localScale` between 1 and
  `BoatPhysicsConfig.HeadPopScale` with the `HeadPopLerp` speed, and the same component
  drives the flame and the puff particles. Its "want pop" flag comes from the *replicated*
  gas state for non-owners — so clients see other players' heads swell, which is why a
  client without any mod should still show the effect (untested, see Verification).
- Three methods on `BoatGroundStabilizer` (`ApplyGroundAlign`, `RecoverIfFlipped`,
  `ClampTilt`) keep the boat level and clamp its tilt to `GroundAlignMaxTiltDeg` (30°).
  They are called every tick and they fight anything that would lift or tip the boat.
- `BarrierKill.GloballyEnabled` is a single static switch. The same component kills the
  boat both on wall collisions and on obstacle triggers (so a single flag covers both).
- **Unity accumulates `Rigidbody.AddForce` until the next `FixedUpdate`**, and the physics
  step runs at 50 Hz. A force added N times per second therefore contributes N × fixedDelta
  of its nominal value. This one rule explains most of the trouble we had (gotcha 1).
- The character rig: a `mixamorig1:Head` bone with `eye.left` / `eye.Right` child objects
  that **carry no renderer** — they are bones in the `SkinnedMeshRenderer`'s bone list. The
  visible eye geometry is skinned to the head, so scaling the eye bones changes nothing
  measurable (gotcha 3). The body is split into several meshes (`MainA`…`MainD` plus hat,
  shirt, trousers, shoes) and the rear is a **second submesh with its own material**, so it
  can be tinted separately through an *instanced* material without touching the shared asset.
- The client-side transport is FishySteamworks, which refuses to connect two builds that
  share one Steam ID, and the non-Steam client path is closed outright. A second local
  client is therefore not available for testing on a single machine and account.

## Build steps
1. Decompile: `ilspycmd -p -o <out> "<game>/Fart Together_Data/Managed/Assembly-CSharp.dll"`.
2. New C# class library, `net472`, `LangVersion latest`, references to the game's managed
   DLLs, `UnityEngine.*` module DLLs and the BepInEx core DLLs, all with `Private=false`.
   Reference the individual Unity *module* assemblies (e.g. `UnityEngine.ParticleSystemModule`,
   `UnityEngine.VFXModule`) when you touch their types, otherwise the build fails.
3. Build from a **private copy** of the project (no `obj`/`bin` in the copy) — see gotcha 9.
4. Copy the plugin into `BepInEx/plugins/` and start the game once: BepInEx writes
   `BepInEx/config/` and the plugin writes its own config there.
5. Config values are bound with BepInEx's `ConfigFile.Bind`; the file is rewritten on exit
   (gotcha 5).

## Verification
- **The in-game HUD as the oracle.** The plugin draws the measured values (speed, session
  peak, current mode, the drag factor, the computed speed limit, the requested vs applied
  force). Numbers were read off the screen by a human and cross-checked against the
  formulas. Example: with a force of 1200 N on a 60.2 kg boat and a drag factor of 1.0, the
  limit is 19.9 m/s and the HUD showed 19.9; the formula and the screen agreed.
- **BepInEx's log as the oracle for behaviour.** The plugin logs the measured tick
  (`TickDelta`, `fixedDeltaTime`), the applied force, the drag factor, the mode changes and
  a one-shot diagnostic line.
- **Reading strings inside the built DLL** to confirm that a code path really made it into
  the binary (a cheap smoke test when the game is not running).
- **Testing a Harmony transpiler outside the game**: load the real `Assembly-CSharp.dll` in
  a small harness, apply the patch to the real method, call it and check the result. This
  validates a constant-rewrite patch without Unity, and it is how we knew the force clamp
  could be lifted.
- **Not verified:** the client half of the "host-only" rule (needs a second Steam ID — the
  transport refuses two builds with one ID, and the non-Steam client path is closed); the
  boat taking off, seen on screen; the transpiler under Unity's Mono runtime (it was
  verified on .NET Framework, and Unity's Mono is a different patching backend — if it fails
  there it logs an error and the game keeps working); the whole "client without the mod"
  scenario.

## Gotchas
1. **The mod's drag was 4.2× stronger than designed** — the speed limit was unreachable and
   the boat stopped almost instantly. **Cause:** the mod applied its force from the
   per-frame update (≈125 Hz) while the game applies its forces from the network tick
   (64 Hz); Unity accumulates `AddForce` until the next `FixedUpdate`, so the effective
   strength scaled with the frame rate. **Fix:** apply every force from the same tick
   callback the game uses (a Harmony postfix on the game's tick method) so both sides
   accumulate identically.
2. **A force multiplier above 5 did nothing.** **Cause:** the game clamps the gas force to
   100…6000 N inside the setter, so the requested value never existed. **Fix:** rewrite the
   clamp constant in IL (Harmony transpiler) instead of trying to set the value.
3. **Scaling the eye bones had no visible effect.** **Cause:** the eye objects are
   renderer-less bones; the visible eye geometry is skinned to the head bone, so the eye
   bones carry (almost) no weight. **Fix:** measure the mesh's bone weights at runtime and
   fall back to scaling the head, so an "eye" multiplier can never be a no-op.
4. **A mode of the mod destroyed the user's settings.** **Cause:** the mode wrote other
   mechanics' config keys to disk (zeroing the speed limit and the swirl strength) and
   saved the file; on the next start those zeros were read back as the "originals" and could
   never be restored. **Fix:** a mode may only *read* other mechanics' keys; expose
   effective values as properties instead of mutating the config.
5. **Edits made to the config at runtime are lost.** **Cause:** BepInEx rewrites the whole
   config file on exit from the state it holds in memory. **Fix:** keep runtime overrides in
   fields of the mechanic, not in the config entry.
6. **The belief "the client needs a speed-clamp patch" is wrong here.** The vanilla clamp
   lives inside the server-only tick, so on a client it never runs and the replicated motion
   should be smooth even with no mod installed (from the code; no second client was
   available to test it). A client install is only needed for purely visual extras.
7. **Unity 6 keeps mesh bone weights in a binary blob**, so they cannot be read offline with
   UnityPy — only at runtime, from the live mesh.
8. **Documentation drifts from the code.** The config key counts in our own docs were
   written by eye and were wrong by 30 %. **Fix:** count the binds from the code and diff
   the list against the config file. Also scan markdown for control characters: a stray ESC
   byte silently corrupted a word in two documents and nobody noticed.
9. **CS0579 when building in the main project tree** — the project's glob picks up stale
   sources from its own `obj` folder. **Fix:** build from a private copy without `obj`/`bin`.
10. **Host-only visuals need a replicated identifier, not `IsOwner`.** The character's
    `ClientId` is 0 for the host on every peer, so `ClientId == 0` is a reliable way to
    make an effect apply to the host's character only, and identically on every client.
11. **A part of a skinned mesh can be tinted separately.** The body has a second submesh
    with its own material, so tinting the "rear" means instancing that material on the
    renderer — the shared asset must not be touched, or every character in the match
    changes colour.

## Assets
None. All visuals use the game's own assets: the character meshes, the head-pop, the flame
and the puff particles. The game ships no dance or emote clip at all (the only clips are
the gas, idle, scene and slide clips), so a custom breakdance would need an authored
AnimationClip and an AssetBundle shipped to every client.

## Cost and time
Two days of wall-clock across ~49 work items, no API spend. Most of the
time went into the force-application semantics (gotchas 1–3) rather than into the features
themselves.

## Open questions
- The client half of the host-only rule is still unverified (needs a second Steam ID).
- The takeoff: the boat lifts with a dedicated upward force while the game's
  ground stabiliser is suspended; there is no vertical drag yet, so the boat keeps rising
  while the key is held, and the height/feel have not been measured on screen.
- A custom dance clip and a custom character model would need an authored AssetBundle and
  a way to choose the model on every client.
- Whether the whole thing behaves on a second, real Steam account.
