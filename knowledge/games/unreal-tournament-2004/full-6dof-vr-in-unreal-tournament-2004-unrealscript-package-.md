---
kind: game
title: 'Full 6DoF VR in Unreal Tournament 2004: UnrealScript package plus a d3d9 proxy for SteamVR'
game: Unreal Tournament 2004
games_also: []
game_version: 'OldUnreal patch 3374, 64-bit: built on Preview 9/23, released against Release Candidate 3 (build 2026-10-20, 185bad7f)'
platform: windows
engine: unreal
route: native-hook
tools: ["UCC make", "ucc batchexport", "MSVC 2022 (x64, /MT)", "OpenVR SDK", "um win (launch, shot, kill)"]
anti_cheat: "none (offline play against bots only; online play was never attempted)"
status: released
agents:
- Claude Code (Opus 5.5)
humans: ["jmkokko"]
date: '2026-11-20'
links: ["https://github.com/jmkokko/ut2004-vr", "https://github.com/jmkokko/ut2004-vr/releases/tag/v0.1.0"]
tags: [vr, openvr, steamvr, d3d9-proxy, unrealscript, ue2, motion-controllers, hud-capture, mock-headset]
---
# Full 6DoF VR in Unreal Tournament 2004: UnrealScript package plus a d3d9 proxy for SteamVR

> UT2004VR puts Unreal Tournament 2004 in a SteamVR headset with Half-Life: Alyx-style play: head-tracked stereo,
> the gun held in the tracked hand, smooth locomotion, snap turn and teleport, the game's own HUD, menus and
> scoreboard on panels, vehicles and turrets aimed with the controller. Two parts: an UnrealScript package (game
> type, mutator, PlayerController, console and HUD classes) that renders each eye with `ScriptedTexture.DrawPortal`,
> and a 64-bit `d3d9.dll` proxy that finds those eye textures and submits them to SteamVR, sending poses and
> controller input back over localhost UDP. Released as 0.1.0 and played by the human on a WMR headset (HP Reverb
> class, Oasis driver) through a whole development cycle; every change was also checked with a mock headset.

## Setup
- **Game:** OldUnreal patch 3374 (64-bit `UT2004.exe`, PE machine 0x8664; `System\Build.ini` `Label=` gives the
  build). The 32-bit retail 3369 has no x64 and no D3D9 path worth using. OldUnreal's full-game installer
  downloads the ISO and **the latest patch release** (`api.github.com/repos/OldUnreal/UT2004Patches/releases/latest`),
  so target that: 3374 Preview 9 (2026-02) crashed in Assault at round start inside the game itself; Preview 23
  (2026-07) and RC3 (2026-11) don't.
- **Renderer:** `D3D9Drv.D3D9RenderDevice` (the default), which calls plain `Direct3DCreate9`.
- **VR:** SteamVR (OpenVR 1.x API through `openvr_api.dll`), WMR headset on the Oasis driver. Windows 11, RTX 3060.
- **Build:** UCC from the game (`ucc make`), MSVC 2022 x64 for the proxy. Work happened from WSL with Windows
  paths under `/mnt/c`.
- **Reference source:** `ucc batchexport <Pkg>.u class .uc <dir>` exports a package's UnrealScript; kept outside
  the repo and only read, never copied (a 6-line-window comparison of every historical `.uc` against the export
  found no shared runs before the repo went public).

## Route and why
- **Considered:** UEVR (UE4.8-5.4 only), alternate-eye rendering from a pure proxy (shimmer, no second view),
  porting the maps into Half-Life: Alyx (loses UT's game), a native RenderDevice (no 3374 x64 SDK headers, an ABI
  gamble).
- **Chosen:** in-engine stereo. UnrealScript can render any camera into a `ScriptedTexture` with `DrawPortal`, so
  both eyes are true renders from the game at the tracked head pose, each frame. The proxy only has to hook
  `Direct3DCreate9` → `CreateDevice` → `CreateTexture`, recognise the two eye render targets and copy them to
  SteamVR. No engine binaries are patched and no native UnrealScript code is needed: the game side talks to the
  proxy through `IpDrv.UdpLink` on 127.0.0.1.
- **Distribution:** files into `System\` only. VR switches on only when the game starts with
  `-ini=UT2004VR_Game.ini` (made by `Play-VR.bat` from the player's `UT2004.ini`); the proxy checks the command line
  in `DllMain` and otherwise forwards straight to the system `d3d9.dll` (no hooks, no log), so the plain game is
  untouched and `UT2004.ini` is never edited.

## How the game works (what we had to learn)
- **Entry points:** a console class (`[Engine.Engine] Console=` in the ini, here a subclass of
  `XInterface.ExtendedConsole`) is the one hook alive in the main menus; it adds the VR mutator to every game the
  menus start (`?Mutator=` on the URL). The mutator swaps in the VR `PlayerController` and `Pawn` classes. The
  startup intro is `LocalMap=NvidiaLogo.ut2` (a Matinee in `CinematicGame`): add `?Mutator=` there too.
- **Eye rendering:** `Level.ObjectPool.AllocateObject(class'ScriptedTexture')`, `SetSize`, `Client = self`,
  `Revision++` each tick, and `event RenderTexture(ScriptedTexture Tex)` → `Tex.DrawPortal(x, y, w, h, Actor,
  Loc, Rot, FOV)`. Each texture has its own viewport, so the projection is square whatever the window. SteamVR's
  asymmetric frustum is matched by rendering a wider symmetric FOV and cropping in the submit bounds.
- **Finding the eyes in D3D9:** hook `IDirect3DDevice9::CreateTexture` (vtable 23); the eye targets are square
  `D3DUSAGE_RENDERTARGET` textures of the requested size. Left/right comes from a 6×6 coloured tag the script draws
  into a corner. With `D3D9Ex` (create the device through `Direct3DCreate9Ex`, convert `D3DPOOL_MANAGED` to
  `DEFAULT` in the hooks) the targets are shared with a D3D11 device on the adapter OpenVR names, so submission is a
  GPU copy (an early 4-minute session: 5.3 ms GPU and 13 ms CPU per frame on an RTX 3060, 20 % of frames reprojected).
- **Poses in:** the proxy sends text datagrams ("H seq pos fwd up", "R hand...", "I buttons axes", config lines).
  `UdpLink` in text mode, `ReceivedText`. Units: 52.5 uu per metre felt right (UT's 82 uu eye height ≈ 1.56 m).
- **Guns in the hand:** UT's first-person meshes pivot near the camera with the gun modelled off-axis and ~1.7×
  real size. The third-person attachment (`Weapon.ThirdPersonActor`) is the right model: its bounding-sphere
  centre and its `tip` bone (`flash` on the minigun) give the barrel axis, and the gun is placed so its handle sits
  at the controller. Shots: override `Pawn.EyePosition()` to return the muzzle, and every trace, projectile and
  most beam effects start there.
- **Beam effects** start at `Location + CalcDrawOffset(Weapon) + EffectOffset` in view axes. Most use the
  weapon's `EffectOffset`, but some add **their own** (Mine Layer guide beam, Painter beam): cancel the right one.
- **HUD and menus:** the game type's own HUD (`HUD_Assault`, `ONSHUDOnslaught`, ...) is spawned as a hidden
  "shadow" beside the VR HUD and drawn into the window only on capture frames, alternately over black and over
  white with a marker pixel; the proxy recovers alpha from the pair and shows it as an OpenVR overlay. Menus
  (`GUIController`) are drawn to the window over black and copied to a world-locked panel; the controller ray is
  turned into GUI mouse coordinates.
- **Vehicles:** UT steers turrets and guns from `Controller.Rotation` through `Vehicle.GetViewRotation`/
  `CameraRotation`; setting those from the hand aims everything. Seats are `ONSWeaponPawn`s with their own camera;
  per-seat eye offsets were needed. Assault's space fighters set `SpaceFighterRotation` directly.
- **Input:** SteamVR Input action manifest + per-controller default bindings next to the proxy
  (`System\UT2004VR\actions.json`); a mirrored second action set for left-handed play, switched from the game's own
  Weapon Hand setting (`Engine.Controller.Handedness`).

## Build steps
1. `ucc make` with `EditPackages=UT2004VR` (the release build uses a temporary ini: `ucc make -ini=Build.ini
   -userini=BuildUser.ini`, so the install stays stock).
2. `cl /O2 /MT /LD d3d9proxy.cpp /DEF:d3d9.def ... openvr_api.lib d3d11.lib ws2_32.lib` (static CRT: no VC++
   redistributable needed). Exports: `Direct3DCreate9`, `Direct3DCreate9Ex` and the `D3DPERF_*` forwards.
3. Ship `System\UT2004VR.u`, `UT2004VR.ucl`, `d3d9.dll`, `openvr_api.dll`, `UT2004VR\*.json`, the proxy ini and
   `Play-VR.bat`; an installer checks for 64-bit 3374 and keeps a foreign `d3d9.dll` (ReShade, dgVoodoo) aside.

## Verification
- **Mock headset:** the proxy's `Mock=1` sends scripted head/hand poses and buttons (`MockDemo=` scenes: still
  head, hand held out, fire once to join, look-away, sitting down, hand pointing left/right...) and `DumpEyes`
  writes the eye render targets as BMPs at chosen frames. The game side runs a `TestExec="cmd|cmd|..."` chain from
  its ini, one console command every ~90 frames, ending with `exit`. Each run backs up and restores every ini it
  can touch. This caught projection errors (calibration sprites at known angles vs. predicted boxes), gun and
  beam offsets (logged distance from beam start to muzzle: 105 uu → 0), HUD capture, menus and vehicles.
- **Real headset:** the human played and approved each feature in the headset; no frame drops were reported after the GPU path landed.
- **Release:** installed from the zip into a never-started RC3 install: first run, DM with a guided Redeemer,
  Onslaught vehicle, Assault load, plain flat launch (no proxy activity), uninstall.
- **Not verified:** network play (VR clients online), most of the game's bonus-pack maps, other headsets than
  WMR (bindings exist for Touch, Index, Vive).

## Gotchas
1. **Side-by-side `DrawPortal` on the main canvas was stretched 2× vertically.** **Cause:** it projects with the
   whole viewport's aspect, not the portal rectangle's. **Fix:** one `ScriptedTexture` per eye.
2. **After drawing a ScriptedTexture on the HUD, everything went into that texture** (black window). **Cause:**
   D3D9Drv doesn't restore the backbuffer render target. **Fix:** touch each eye texture as a 1×1 tile at (0,0) to
   trigger its render and draw nothing after.
3. **Garbage appended to UDP commands** (`SETRES 3292x1360318w`). **Cause:** `UdpLink.ReadText` doesn't stop at the
   datagram end; leftovers of a longer earlier packet stay. **Fix:** terminate each packet with " ;" and cut there.
4. **`SETRES` from `HUD.PostRender` crashed** ("render device is locked"). **Fix:** queue it, run it in
   `PlayerTick`.
5. **A console exec with three float parameters received only the first.** **Fix:** take one string and split it.
6. **`set <Class> <var> <value>` on a `globalconfig` variable writes the ini immediately** (e.g.
   `Engine.Controller Handedness` lands in `User.ini`). Back up `User.ini` around automated tests.
7. **UT has no single-weapon give command** in 3374 (`giveweapon` isn't an exec); `loaded` gives the stock set.
   Write your own exec that calls `Pawn.GiveWeapon` and switches to it.
8. **Zoom stuck after one step.** **Cause:** UT advances zoom in `AdjustView`, called from
   `Pawn.UpdateEyeHeight` on the stock movement path that VR movement skips. **Fix:** call it from `PlayerTick`
   when it didn't run.
9. **Mouse aim never moved in vehicles (keyboard mode).** **Cause:** `PlayerCalcView` returned a cached view
   rotation for the vehicle. **Fix:** read `Controller.Rotation` directly (converted when the seat uses
   `bPCRelativeFPRotation`).
10. **The guided Redeemer showed a flat "screen" of scope graphics and no map.** **Cause:** `HUD.PostRender` calls
    `Pawn.DrawHUD` when `bSpecialHUD` is set; drawn into the captured HUD layer, the warhead's full-screen 2D scope
    covered everything. **Fix:** clear `bSpecialHUD` around the shadow HUD's draw. Lesson: eye dumps don't show
    SteamVR overlays; when the user reports something the dumps don't, suspect the overlay layer.
11. **Walking slowly turned left; the seated "forward" was 75-107° off.** **Cause:** SteamVR's seated zero pose on
    this WMR setup didn't match the chair. **Fix:** derive the chair's forward from a histogram of where the
    player looks (±4° bins, 60 s half-life), and face intros and menus toward the head, not the seated zero.
12. **Player at floor level, crouch stuck on.** **Cause:** the Oasis driver reported no floor ("Cannot locate root
    anchor"); standing-universe height read below 0. **Fix:** calibrate height from the worn head after a short
    average, lift implausible readings to a standard eye height, re-level slowly.
13. **vrserver crashed when a controller woke up** (0xc0000409 in the Oasis driver's `MotionControllerHid.dll`
    while "Registering new controller: Built-in Bluetooth Right"). Driver-side, not the mod: wake controllers
    before launching.
14. **A d3d9 proxy in `System\` affects every launch of the game.** **Fix:** activate only on a marker in the
    command line (here the VR ini's name), otherwise forward `Direct3DCreate9(Ex)` untouched and don't even log.
15. **A fresh install has none of the author's tuning.** Per-weapon grip offsets lived only in the developer's
    saved ini. Bake config defaults into `defaultproperties` before release, and test with an empty ini.

## Assets
Only generated ones: a vignette, scope mask and rim, a porthole rim (TGA, made by script) and a two-sided disc
mesh for scope lenses (an Unreal-1 vertex mesh written by script; UCC takes packed vertex values as they are, and
ignores the two-sided flag, so both windings are in the mesh). No game assets are shipped.

## Cost and time
About six weeks of sessions (2026-10-09 to 2026-11-20), the human testing in the headset between them.

## Open questions
- Online play: client-side prediction and replication of the VR pawn (a plan exists in the repo, `docs/`).
- Info pods, the 3D objective arrow, Onslaught node health bars and CTF flags as 3D markers.
- OpenXR instead of OpenVR, for headsets without SteamVR.
