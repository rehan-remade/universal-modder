---
kind: technique
title: 'Retrofitting stereo VR into an old D3D9 game: in-engine eye renders, a d3d9 proxy and a mock headset'
status: working
agents:
- Claude Code (Opus 5.5)
humans: ["jmkokko"]
date: '2026-11-20'
links: ["https://github.com/jmkokko/ut2004-vr", "games/unreal-tournament-2004/full-6dof-vr-in-unreal-tournament-2004-unrealscript-package-.md"]
tags: [vr, openvr, steamvr, d3d9, d3d9ex, proxy-dll, stereo, mock-headset, testing, hud, input]
---
# Retrofitting stereo VR into an old D3D9 game: in-engine eye renders, a d3d9 proxy and a mock headset

> How to give a pre-VR game real stereo 6DoF VR when it has a scripting layer that can render a camera into a
> texture, plus how an agent can test VR work without wearing the headset. Proven on Unreal Tournament 2004
> (see the linked game note); the pieces carry over to other D3D9 games with render-to-texture in script or mods.

## When to use it
- The game runs on Direct3D 9 (or can, through a wrapper) and has a mod layer that can render the scene from an
  arbitrary camera into a texture (UnrealScript `ScriptedTexture.DrawPortal`, Source's render targets, a
  Lua/plugin API with offscreen views...).
- Injectors like UEVR don't cover the engine, and alternate-eye rendering (one eye per frame from a proxy alone)
  would shimmer and halve the frame rate.
- Not for: games with no way to render a second view; D3D11/12 games (use their own swap-chain hooks or UEVR-like
  tools); online games with anti-cheat.

## How it works
1. **Two eye renders in the game.** The mod renders each eye into its own square render target at the tracked
   head pose, every frame, with an FOV wide enough to cover the headset's asymmetric frustum. One target per eye
   matters: a split viewport on the main canvas usually projects with the whole window's aspect.
2. **A `d3d9.dll` proxy next to the exe.** Export `Direct3DCreate9`/`Direct3DCreate9Ex` (plus `D3DPERF_*`
   forwards), load the real one from the system directory, and patch the vtable of the created object
   (`CreateDevice`) and of the device (`CreateTexture`, `Present`, `Reset`). Recognise the eye targets by their
   description (square, `RENDERTARGET`, the size the mod asked for) and tell left from right by a small colour
   tag the mod draws into a corner.
3. **Hand-off to the compositor on the GPU.** Create the game's device through `Direct3DCreate9Ex` (convert
   `D3DPOOL_MANAGED` resources to `DEFAULT` in the hooks, which Ex requires), create the eye targets as shared
   textures, open them on a D3D11 device on the adapter OpenVR reports (`GetDXGIOutputInfo`; it matters on CPUs
   with an iGPU) and `Submit` them. Gate the first `Submit` on a successful `WaitGetPoses` (error 101 otherwise).
   Keep a CPU-copy fallback for drivers where Ex fails.
4. **Poses and input back to the game** over localhost UDP as short text lines (head, hands, buttons and axes,
   a sequence number). Terminate each datagram explicitly: some engines' UDP text readers don't stop at the
   datagram's end. Use SteamVR Input (action manifest + per-controller default bindings shipped with the mod);
   a mirrored action set gives left-handed play for free.
5. **HUD and menus as layers.** Draw the game's 2D HUD/menus into the window on capture frames over black and
   then over white with a marker pixel; the proxy recovers alpha as `1 - (white - black)` and shows the result as
   an OpenVR overlay (head-locked for the HUD, world-locked for menus). The desktop window keeps a mirror of one
   eye.
6. **Off unless asked for.** A proxy DLL in the game folder loads for every launch: switch VR on only for a marker
   in the command line (a dedicated ini, a flag) and otherwise forward everything untouched.

## The mock headset (how an agent verifies VR without wearing it)
- The proxy has a `Mock` mode: no OpenVR; it sends scripted poses and button presses (scenes picked by an ini key:
  head still, hand held out, look 60° away, sit down, press fire once...) through exactly the same channel as the
  real headset.
- `DumpEyes` writes the eye render targets as images at chosen frames; stitch them into a contact sheet and look.
- The game side runs a console command chain from an ini key (one command every N frames, ending with `exit`), so
  a test is: write the chain, launch, wait for the process to end, grep the log, look at the dumps.
- **Oracles that worked:** calibration sprites at known yaw/pitch drawn against boxes where the maths predicts
  them (projection, roll, pitch); logged distances (beam start to muzzle, handle to hand through ±60° wrist roll);
  log lines for state changes (entered vehicle, riding, menu open).
- **Limits:** eye dumps don't contain the compositor's overlays (HUD/menu layers), real-device quirks (driver
  floor height, seated zero pose, controller wake-up crashes) and comfort. Keep the human in the loop for those,
  and when a bug report doesn't reproduce in the dumps, suspect the overlay path first.

## Steps
1. Prove the projection first: a still mock head pitched and rolled, calibration sprites, eye dumps.
2. Then the proxy's GPU path and real `Submit`, then poses at frame rate (check the compositor's reprojection
   stats).
3. Then hands and weapons, HUD/menus, locomotion and comfort options, then the game's special cases.
4. Release: activation only through the launcher, defaults baked in (test with an empty config), a static CRT
   (`/MT`) so no runtime installer is needed, an installer that keeps a foreign `d3d9.dll` aside.

## Gotchas
1. **Side-by-side eyes on one canvas came out stretched.** **Cause:** the engine projected with the full
   viewport's aspect. **Fix:** a separate render target per eye.
2. **Drawing a render target on the HUD broke all later drawing.** **Cause:** the D3D9 renderer didn't restore the
   backbuffer target. **Fix:** trigger the eye renders with a 1×1 draw at the corner and draw nothing after.
3. **Seated forward was wrong by up to 107°** on a WMR headset. **Fix:** estimate the chair's forward from where
   the player looks most (a decaying histogram), not the runtime's seated zero.
4. **No floor height from the driver** made the player tiny and crouched. **Fix:** calibrate eye height from the
   worn head and clamp implausible values.
5. **A full-screen 2D effect leaked into the HUD layer** (a pawn's own HUD, here a guided missile's scope). Audit
   what the game draws in 2D for special views before capturing it.

## Open questions
- OpenXR instead of OpenVR (Quest Link, WMR without SteamVR).
- Generalising the proxy (eye-target detection by tag, overlay capture) into a reusable kit for other D3D9 games.
