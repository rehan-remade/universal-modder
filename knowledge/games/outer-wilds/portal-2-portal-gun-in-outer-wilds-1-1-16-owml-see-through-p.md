---
kind: game
title: 'Portal 2 portal gun in Outer Wilds 1.1.16 (OWML): see-through portals, momentum, ship and scout'
game: Outer Wilds
games_also: [Portal 2]
game_version: "1.1.16.1372 (Steam 753640, buildid 20230391), Unity 2019.4.39f1 Mono, Echoes of the Eye installed"
platform: windows
engine: unity-mono
route: loader-api
tools:
- Outer Wilds Mod Manager 0.15.7 (GUI + owmods CLI)
- OWML 2.16.3
- HarmonyX (bundled with OWML)
- NuGet OWML 2.16.3 + OuterWildsGameLibs 1.1.16.1372 (publicized refs), net48
- ilspycmd 9.1 (.NET 8)
- Python 3.14 + Pillow + numpy (converter)
anti_cheat: none (single-player)
status: working
agents:
- Claude Code (Opus 5.5)
humans:
- charlystereo
date: '2026-10-10'
links:
- https://github.com/ow-mods/owml
- https://github.com/ow-mods/ow-mod-man
tags: [unity, owml, harmony, portals, stencil, oblique-camera, render-texture, teleport, viewmodel, momentum, mashup, portal-2]
---
# Portal 2 portal gun in Outer Wilds 1.1.16 (OWML): see-through portals, momentum, ship and scout

> An OWML mod that adds Portal 2's portal gun to Outer Wilds on key 5, in every save, from the first second of
> each loop, with or without the suit. Portals show the other side (stencil + oblique camera), keep momentum relative
> to the bodies they ride, stick to planets and the ship, and vanish at loop reset. Player, scout and ship go
> through. The viewmodel and sounds are converted from the user's Portal 2 (companion note in `games/portal-2/`).
> Verified in the real game through a mod-side command bridge (screenshots, traces, OWML log) and real
> keyboard/mouse input. Code: `examples/outer-wilds-portal-gun`.

## Setup
- Windows 11, Steam. Game reports `Outer Wilds Version: 1.1.16.1372` in `Player.log`
  (`%USERPROFILE%\AppData\LocalLow\Mobius Digital\Outer Wilds`). OWML's `game-versions.json` lists steam 1.1.16.1372.
- Mod Manager installed silently (`Outer.Wilds.Mod.Manager_0.15.7_x64-setup.exe /S` → `C:\Program Files\Outer Wilds
  Mod Manager`); OWML via its CLI: `owmods --analytics false setup` → `%APPDATA%\OuterWildsModManager\OWML`. Mods go in
  `OWML\Mods\<uniqueName>\` (manifest.json, default-config.json, dll). Launch with `OWML.Launcher.exe` (patches the
  game's Assembly-CSharp at start; undo = Steam "verify integrity"). Log: `OWML\Logs\latest.txt`.
- Project = the official template (`ow-mods/ow-mod-template`): `net48`, NuGet `OWML` + `OuterWildsGameLibs` (exact game
  version exists), `OutputPath` straight into the mods folder.

## Route and why
OWML mod + Harmony. No portal mod existed (searched 2026-10-10). Rendering had to use shaders already in the build:
a mod can't compile shaders and there is no Unity 2019.4 editor here for an AssetBundle. `UI/Default` exposes stencil
and colour-mask properties, which is all a stencil portal needs.

## How the game works (what we had to learn)
- **Player camera** `PlayerCamera` (`OWCamera`): deferred, HDR, near 0.1, far 50000, fov 70. The skybox is drawn by a
  command buffer from `SkyboxRenderer.activeSkyboxRenderers` (AfterLighting), not by clear flags: copy it onto any
  extra camera or space renders black. `clearStencilAfterLightingPass = true`, so the stencil is free for the forward
  (transparent) queue.
- **Tools** render with `Outer Wilds/Utility/View Model (Cutoff)` plus `View Model Prepass` on layer
  `VisibleToPlayer`, using global `_ViewmodelMatrixVP` (fixed viewmodel fov 70) under keyword `_VIEWMODEL_OVERRIDE`.
  Cloning the Signalscope's two materials onto your own skinned mesh gives a viewmodel that never clips walls.
  Disable `_ALPHATEST_ON`/`_METALLICGLOSSMAP`/`_EMISSION` when your textures' alpha means something else.
- Shaders findable by name in this build: `Standard`, `UI/Default`, `Sprites/Default`, `Legacy Shaders/Particles/Additive`.
- **ToolModeSwapper** knows four tools (`ToolMode` Probe/SignalScope/Translator/Item). It reports the old mode until the
  old tool finishes stowing. With nothing held, `TOOL_PRIMARY` (right mouse on KB+M, RB on pad) takes out the scout
  launcher (only with the suit). Default KB+M: right mouse = tool primary/probe launch/retrieve, R = tool
  secondary, **left mouse = `lockOn`** (ReferenceFrameTracker.UpdateTargeting), E = interact. Key 5 is only read by
  ScreenshotController together with the screenshot key.
- **Moving bodies:** `OWRigidbody.WarpToPositionRotation` (+ `SetVelocity`, `SetAngularVelocity`). On the player it
  fires `WarpPlayer` (trigger volumes/sectors re-check) and `PlayerRepositioned` (CenterOfTheUniverse recentres).
  `ShipBody.SetPosition/SetRotation` carry a player walking inside the ship. `SetVelocity` takes velocities in the
  universe's static frame (it adds the CenterOfTheUniverse frame velocity itself). Velocities must be mapped relative
  to the bodies the portals ride: `parentBody.GetPointVelocity(p)`.
- **Player controller:** grounding is `CastForGrounded` (SphereCast, radius 0.46) validated by `IsValidGroundedHit`;
  ground snapping runs when `_wasGrounded` and `Time.time > _lastJumpTime + 0.5`. `Physics.IgnoreCollision` does not
  affect any of that.
- **Scout:** a kinematic body that predicts impacts with a raycast each step and calls `ProbeAnchor.AnchorToObject`.
- **Loop reset** = `Flashback` → `LoadManager.ReloadSceneAsync`; objects created in the SolarSystem scene vanish,
  `LoadManager.OnCompleteSceneLoad` fires again (SolarSystem → SolarSystem). After a reload the wake-up is automatic;
  only title → SolarSystem shows the "Wake up [E]" prompt.
- Profiles: `StandaloneProfileManager.SharedInstance` (`TryCreateProfile`, `SwitchProfile`, `profiles`, `isInitialized`);
  saves in `SteamSaves\<profile>\data.owsave` (Steam cloud).

## Build steps
1. `python tools/convert.py` (reads Portal 2, writes `%LOCALAPPDATA%\OWPortalGun`, ~8 MB, <1 s).
2. `dotnet build src -c Release` (drops into `OWML\Mods\charlystereo.PortalGun`).
3. Start from the Mod Manager. Log: `Portal Gun loaded`, then `portal gun added to the loop`.

## Implementation that worked
- **Portal view:** per portal a disabled `Camera` (CopyFrom the player camera) placed at the mapped camera pose
  (`to * Rot180(Y) * inverse(from)`), oblique near plane on the exit plane, rendered from `Camera.onPreCull` of the
  player camera into a screen-sized `RGB111110Float` RT (no alpha channel, so `UI/Default`'s alpha blend is opaque).
  Stencil writer = ellipse + 0.6 m tube behind it (`UI/Default`, `_ColorMask 0`, `_StencilComp Always`, ref 64/128,
  queue 2990, `unity_GUIZTestMode` = LessEqual set **on the material**); composite = full-screen quad parented to the
  camera at near*1.05 (`UI/Default`, `_StencilComp Equal`, ZTest Always, queue 2991). Post-processing then applies to
  the composited frame, so both sides match. Scissor the view camera to the portal's screen rect.
- **Crossing:** each FixedUpdate, OverlapSphere around each portal + player/ship/launched scout; track the reference
  point (player: the camera; others: centre of mass) in portal space; crossing = prev.z ≥ 0 → z < 0 inside the
  ellipse. A LateUpdate re-check for the player's camera avoids one frame behind the plane.
- **Holes:** while a body is in the hole column (inside the ellipse, z in [-3-r, 2.5+r], r = body radius from collider
  bounds) re-apply `IgnoreCollision` with every collider under the portal each step; postfix `IsValidGroundedHit` to
  reject hits in that column (z < 0.3).
- **After a player warp:** come out upright for the exit's gravity (`GravityVolume.CalculateForceAccelerationAtPoint`),
  yaw from the mapped view, pitch into `PlayerCameraController.SetDegreesY`, keep the **eye** on its mapped point
  (+3 cm out), call `MakeUngrounded` and set `_wasGrounded=false`, `_lastJumpTime=Time.time` by reflection.
- **Fitting to terrain:** 16 samples (outline + inside) cast along the hit normal; average-normal plane; accept ≤ ~1 m
  unevenness (35 % of height for ship-size portals); retry a sample from 3x higher if it starts inside a hill; place the
  portal on the most protruding sample; nudge in quarter-size steps like Portal 2.

## Verification
Oracle: a mod-side command file (`dev.enabled` + `dev_commands.txt` → `dev_log.txt`, `shots/`; see the technique
note `techniques/driving-a-game-from-a-mod-side-command-file-lab-profile-wake.md`), run on a lab profile `PortalLab`.
- Gun: draw animation, game viewmodel shading, skin turns blue/orange with each shot (screenshots).
- Portals on BatchedMeshColliders of TimberHearth_Body, closed static until both exist, then each shows the other side.
- Floor↔floor: endless Portal-style fall loop, rel speed 6.5 → 6.3 → 5.4 m/s, upright, no view jumps (trace at 20 Hz).
- Wall→floor→wall: in at 2.5 m/s, out of the floor at +2.5 m/s, gravity apex 0.4 m, back in, out of the wall at 2.7 m/s.
- Ship dropped 30 m into a person-size floor portal: out of a wall portal at 25.8 m/s (and into the player).
- Scout launched into a floor portal at 48 m/s: out of the wall portal on its trajectory.
- Loop reload: portals gone, gun re-added and usable in the new loop.
- Real input (SendInput via `um win drive`): `5` equips/holsters, left click = blue, right click = orange, scout
  launcher not taken out, wheel shows the size message.
- FPS at 3440x1440: 121 without portals; 93 with a near portal, 82 with both visible (69 before scissoring).
- **Not verified:** generic loose physics props (none free in the village; the code treats any non-kinematic
  OWRigidbody the same as the ship), portals on moving islands/Brittle Hollow fragments, other planets, Echoes of the
  Eye (the gun is put away in the dream world), gamepad buttons, other screen sizes.

## Gotchas
1. **Equip key read as LeftCtrl.** `Key.Digit0 + 5`. **Cause:** in Unity's `Key` enum Digit1..Digit9 are consecutive
   and Digit0 comes after Digit9. **Fix:** `'0' ? Digit0 : Digit1 + (c - '1')`.
2. **`FieldAccessException` and a whole method that never runs.** **Cause:** Mono checks field access when it JITs the
   method, even when you compiled against publicized OuterWildsGameLibs; one private field in a big `switch` killed
   every case. **Fix:** reflection (`AccessTools.Field/Method`) for private members.
3. **Loading SolarSystem straight from the title = NREs, input stuck at None.** **Cause:** profiles not initialised,
   and the wake-up prompt waits for `interact`. **Fix:** wait for `isInitialized`, use the title's resume action, run
   what the wake prompt runs (see the technique note).
4. **Player hovers over a floor portal.** **Cause:** grounding is a SphereCast, unaffected by IgnoreCollision.
   **Fix:** postfix `IsValidGroundedHit` to drop hits in the hole column.
5. **Player falls through the planet after exiting a floor portal.** **Cause:** the controller still thought it was
   grounded on the entry side and ground-snapped onto caves under the exit. **Fix:** MakeUngrounded + `_wasGrounded =
   false` + `_lastJumpTime = Time.time` after the warp, eye 3 cm in front of the exit, crossing test `prev.z >= 0`.
6. **Exit speed vanishes on a floor exit.** **Cause:** a planar "frame" collider around the hole (meant to replace the
   ignored wall) caught the capsule at the rim; also, ground hits deeper in the hole column made the controller kill
   vertical speed. **Fix:** no frame collider; filter every ground hit behind the plane inside the ellipse.
7. **Collisions come back mid-crossing.** **Cause:** Unity forgets `IgnoreCollision` when a collider is re-enabled
   (the player's anti-sinking collider toggles). **Fix:** re-apply every physics step while in the hole.
8. **Player comes out upside down.** **Cause:** floor→floor maps through a 180° turn about a horizontal axis; the game
   rights the player slowly in the air. **Fix:** compute an upright rotation for the exit gravity and keep the eye on
   its mapped point.
9. **Ship lands on the rim.** **Cause:** ignore zone sized for the player. **Fix:** scale the zone by body radius
   (ship ≈ 7.6 m) and, for bodies bigger than the portal, ignore the static ground of the same body within reach.
10. **Scout sticks to the wall behind the portal.** **Cause:** it anchors from its own raycast before any physics
    check. **Fix:** prefix `ProbeAnchor.AnchorToObject`: inside an open portal, warp and map its velocity instead.
11. **The stowed scout gets teleported at 217 m/s.** **Cause:** `Locator.GetProbe()` exists while stowed. **Fix:** only
    track it when `IsLaunched()` and active.
12. **Left click does nothing, right click places the "blue" portal.** **Cause:** OW binds right mouse to tool primary
    and left mouse to lock-on. **Fix:** read `Mouse.current` buttons directly for the gun; consume tool primary/
    secondary in a `ToolModeSwapper.Update` prefix and `lockOn` in a `ReferenceFrameTracker.UpdateTargeting` prefix.
13. **Notifications don't show.** **Cause:** `NotificationManager` messages appear on the suit's helmet HUD only.
    **Fix:** own IMGUI text (and Portal 2's crosshair from `sprites/hud/portal_crosshairs`).
14. **Rough rock walls rejected / big portals rejected over water.** **Cause:** strict all-points-on-plane test;
    samples starting inside a hill see nothing (rays skip back faces, CheckSphere misses mesh interiors); water has no
    physical collider. **Fix:** averaged plane with tolerance, retry from higher, place on the most protruding sample.
15. **A synthetic "walk" launched the player at 180 m/s.** **Cause:** using absolute velocity (planet orbit ~217 m/s)
    as the base and adding speed every step while airborne. **Fix:** only push while grounded, relative to the ground
    body's point velocity.
16. **Ship spawned 22 m up drifts sideways at 20 m/s.** **Cause:** it was inside tree canopies. **Fix:** find open sky
    first (sphere casts down from 60 m) or use the portal's own normal.

## Assets
Only the user's Portal 2 files, converted locally (see the Portal 2 note). No generated assets.

## Cost and time
One session of about 2.5 hours from install to verified, around 25 game launches driven by the command bridge.

## Open questions
- Recursion (a portal seen inside a portal shows the wall there, not another view).
- The other portal's rim is visible around the view inside a portal (looks like Portal 2, but unplanned).
- Portals on planets that unload (Brittle Hollow fragments falling, Giant's Deep islands thrown by tornadoes).
- A shader-free way to get the game's fog/atmosphere right through a portal (the view camera lacks OWCamera's hooks).
