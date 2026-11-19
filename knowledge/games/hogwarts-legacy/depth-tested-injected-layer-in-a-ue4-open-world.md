---
kind: game
title: "Compositing an externally rendered layer into a UE4 open world: a native publisher and a depth-tested ReShade compositor"
game: "Hogwarts Legacy"
games_also: []
game_version: "Epic build fa4240e57a3c46b39f169041b7811293, Unreal Engine 4.27.2 (4.27.2-2013408+++stream), ReShade 6.8.0, RE-UE4SS 3.0.1-1161 experimental"
platform: windows
engine: unreal
route: loader-api
tools: ["RE-UE4SS 3.0.1-1161 experimental (EngineVersionOverride 4.27)", "ReShade 6.8.0 add-on API (dxgi.dll proxy)", "Rust (native frame publisher, no dependencies)", "MSVC cl.exe 14.44 (ReShade add-on, no ReShade import lib)", "um scan", "um win launch", "um win shot", "um video (gfxcapture)", "WinDrive", "cargo test", "Python 3.12 (shared-memory layout checker)"]
anti_cheat: "none found by um scan; single-player only throughout, no online service touched. The exe and its DRM are never modified: UE4SS and ReShade load as proxy DLLs (dwmapi.dll, dxgi.dll)."
status: working
agents: ["Claude Code (Opus 5)"]
humans: ["TolkoDev"]
date: '2026-10-20'
links: ["../gta-v/minecraft-passthrough.md", "https://github.com/rehan-remade/universal-modder/tree/main/examples/minecraft-gta5-passthrough", "https://github.com/codeByAlexff/garrys-redemption"]
tags: [unreal, ue4ss, reshade, reshade-addon, shared-memory, depth-compositing, frame-compositing, game-thread-timer, native-publisher, loader-api, units, coordinate-system, ue4-27]
---

# Compositing an externally rendered layer into a UE4 open world: a native publisher and a depth-tested ReShade compositor

> Hogwarts Legacy is a UE 4.27 open world with no anti-cheat, and it accepts a layer that is not part of the
> game: a native publisher rasterises that layer into shared memory, a ReShade add-on uploads it as textures,
> and a compositor shader mixes it into the host's frame **only where the layer is nearer than the host's own
> depth buffer**, so host geometry correctly cuts into it. The chain ran in the real game for 15 minutes of
> camera-pose writes with zero errors, and occlusion is proven by pixel counts rather than by eye.

## Setup

- **Game:** Hogwarts Legacy, Epic Games Store, build `fa4240e57a3c46b39f169041b7811293`, Unreal Engine
  4.27.2 (`4.27.2-2013408+++stream+Main_TeamCity_Code`). Host OS Windows 10.0.19045 x64. `um scan` reports
  no anti-cheat. Everything here was single-player, no online services touched.
- **RE-UE4SS 3.0.1-1161 experimental** with `EngineVersionOverride 4.27`. Its proxy is `Win64\dwmapi.dll`.
- **ReShade 6.8.0 with full add-on support**, loaded as the `Win64\dxgi.dll` proxy. The add-on API is only
  enabled in that unsigned build (reshade.me), so keep it to single-player games like this one.
- **Own code installed into the game folder:** the ReShade add-on DLL, the compositor shader under
  `Win64\reshade-shaders\Shaders\`, the ReShade preset, and the Lua mod under
  `Win64\ue4ss\Mods\<mod>\Scripts\`.
- The game folder is on `D:\Epic Games`, not under Program Files, so writing to it needs no elevation - but
  installing a loader into it still needs the human's explicit word.
- Back up the save folder before any launch. Saves live in
  `%LOCALAPPDATA%\HogwartsLegacy\Saved\SaveGames\<id>\` - note that the folder name has no space, unlike the
  game directory, which is a real trap: the save folder is `HogwartsLegacy` **without** a space, and only
  `Mods` lives in the spaced one.
- The Epic overlay has to be switched off with the environment variable
  `EOS_OVERLAY_DISABLE_VULKAN_WIN64=1`; the launcher itself offers no toggle for it.
- The stock UE4SS mods are all switched off, and so is UE4SS's own GUI console. Both cost a crash to learn.

## Route and why

`route: loader-api`. The host ships no scripting API, so the chain is: read the camera pose from the game's
own thread through UE4SS, hand it to a native publisher over a file, let the publisher rasterise the layer
and publish it into shared memory, and let a ReShade add-on upload that memory into textures the compositor
shader samples.

Each hop was chosen because the alternative was known to be worse:

- **Why a file bridge for the pose:** UE4SS's Lua cannot write into shared memory, only files. The pose is
  112 bytes, so a file hop is cheap. It is *not* the right bridge for pixel layers - see Gotcha 18.
- **Why a native publisher:** the layer has to be rasterised with correct depth and alpha, and Lua inside
  UE4SS has no drawing API. The publisher is a dependency-free Rust binary; it renders pixels and knows
  nothing about the game.
- **Why a ReShade add-on rather than a UE plugin:** the compositor needs the host's own depth buffer to decide
  where the layer is visible, and under D3D12 the cheapest way to reach a frame's depth is from inside the
  graphics stack. A shipping-build UE plugin would have needed the game's own toolchain and symbols.
- **What was rejected:** a from-scratch compositor. The expensive unknown was not the shader, it was whether
  ReShade exposes a usable depth buffer under D3D12 at all. That is worth borrowing rather than re-deriving.
- **The mistake worth naming:** the compositor *was* a byte-for-byte copy of this repo's
  `examples/minecraft-gta5-passthrough` example, and it kept the example's numbers. The example's host
  measured in metres; this host measures in centimetres. The copy compiled, ran, and was silently wrong.
  See Gotcha 1.

In `knowledge/techniques/choosing-a-mashup-route.md` terms this is the host half of the frame-compositing route,
with a test cube standing in for the guest game; `knowledge/techniques/frame-compositing-depth-and-pose-sync.md` has
the general method. For the opposite result on Unreal 5, see
[Black Myth: Wukong](../black-myth-wukong/reshade-depth-dead-end.md), where ReShade found a depth buffer but it held
no scene geometry.

The split that fell out of this work: **C++ inside the game only writes state, the Rust binary outside only
draws pixels, and Lua stays only until C++ can replace it.** Lua is currently a camera probe and nothing
else.

## How the game works (what we had to learn)

**The pose.** The Lua mod ticks in the game's own thread and writes a 112-byte little-endian record to
a pose file: sequence, camera rotation, vertical field of view, near/far clip, viewport size, camera
position, and a validity flag. Camera position is in **world centimetres**. The player's location (its root
component's `RelativeLocation`; the actor itself has no such property, Gotcha 13) differs from the camera by about
two metres, which is exactly what a shoulder camera should give, and is the check that proved the numbers are
world space and not local.

**Units.** Everything Unreal is centimetres. The world origin sits hundreds of thousands of centimetres from
the map centre, so absolute coordinates are large; all offsets inside the layer are small.

**The published frame.** The publisher writes into a named shared memory object, which is
**126.6 MiB at 2560x1440**. A descriptor is followed by three pixel layers laid out consecutively, each
`width * height * 4` bytes: `world_rgba` (premultiplied RGBA), `world_depth` (float32) and `overlay_rgba` (a
screen-space layer). The stride accounts for all three. The roles differ and it matters: the world layer
carries depth and is cut into by host geometry, while the overlay layer is always on top and needs no depth.
The publisher does not write the overlay at all yet, so that third of the buffer stays zero.

**Depth encoding.** The layer's depth is not a raw depth buffer. It is encoded as
`d = near * (far - z) / (z * (far - near))`, clamped to `[0,1]`, with `d = 1` at the near plane and `d = 0` at
the far plane, and `d = 0` meaning "no surface here". The shader's inverse is
`z = near * far / (near + d * (far - near))`, and `d <= 0` is treated as infinitely far. This is reversed-Z,
consistent between publisher and shader, and the round trip is covered by a test.

**Row order.** The publisher writes rows **bottom-up**: row 0 is the bottom of the screen. The compositor
flips V once, and that is correct. But the descriptor carries a flags byte whose bit 1 is documented as "rows
already top-down, do not flip", and the publisher always sets it. The flag is wrong, and following it puts the
layer upside down. See Gotcha 11.

**The flags byte.** The publisher writes `7` (depth in [0,1], rows bottom-up, reversed Z) as a constant and it
overwrites whatever the Lua side put there. Nobody reads it: the add-on passes the whole byte to the shader as
a float, and the shader hard-codes all three conventions as constants. The numbers happen to be right today.
They are right by accident, not by protocol.

**Host depth.** The shader samples the host's depth through `ReShade::DepthBuffer` and the host's colour
through `ReShade::BackBuffer`. Under D3D12 the host's depth buffer is reversed, and the shader has a branch
for both layouts selected by a `HostReversedZ` uniform. The add-on never sets that uniform, so the default is always used.
Which way round is correct was never tested by experiment; it is assumed. Depth access itself was confirmed
with the stock `DisplayDepth` technique, which is how the host's depth buffer was located in the first place.

**The compositor shader** runs four passes: a quarter-resolution mip chain of the host picture (used as a
cheap local light and colour source), the composite itself (which also writes a per-pixel info texture with
coverage, guest depth and host depth), a bright pass over that info, and the final pass that applies edge
softening, contact shadows, glow, and the screen-space overlay. Depth testing happens once, in the composite
pass: the layer is visible where its depth is nearer than the host's, plus a small allowance.

**The class of the player actor** is `BP_Biped_Player_C` (a `BlueprintGeneratedClass` under
`/Game/Pawn/Player`). Useful to know because guessing property names on it is dangerous.

**The UE4SS Lua API surface that matters here.** `FindAllOf("PlayerController")` to enumerate instances,
`pc.Pawn` to reach the controlled actor, and on an object `GetClass()`, `GetFullName()`, `GetName()` and
`type()` to identify it. `NotifyOnNewObject("/Script/Engine.PlayerController", ...)` exists and fires when
an object of that class is constructed - it was confirmed working for exactly one class, and it is the way to
catch an object at creation rather than searching for it later. The game-thread timers need the loader's
EngineTick hook, and there is a flag for whether it is available: when it is not, a mod that depends on it
should stay silent rather than fall back to a foreign thread, which is the crash in Gotcha 3.

**Host and loader quirks worth knowing.**
- The window that says unofficial mods were detected is shown **after a crash**, not before startup. Its
  text says a crash occurred, and dismissing it returns to the menu. Reading it as a startup obstruction
  wasted time, and treating it as a warning about the mods is what caused the confusion.
- `LS-0018` from the Epic launcher means an instance is already running - and an instance sitting on that
  crash dialog looks exactly like a running game.
- The Epic overlay is disabled only through the environment variable above; the launcher has no checkbox.
- The game folder holds the save-less `Mods` directory with a space in its name while the real saves live
  in a differently spelled folder, which makes a "back up the saves" step easy to get wrong.

## Build steps

1. **Publisher** (Rust, no dependencies): `cargo test` then `cargo build` in the publisher directory. It maps
   the shared memory object, reads the pose file, rasterises the layer and publishes it.
2. **Add-on** (C++, ReShade add-on API, no link against ReShade - it resolves its own API through
   `GetProcAddress`):
   ```
   cl /nologo /LD /O2 /EHsc /std:c++20 /MT /W3 /DWIN32_LEAN_AND_MEAN /DNOMINMAX ^
     /I third_party\reshade src\<addon>.cpp /Fo"build\\" /Fe"build\<addon>.dll" ^
     /link ws2_32.lib user32.lib
   ```
   It exports `AddonInit` and `AddonUninit` by name (ReShade calls them when present; registering from
   `DllMain` also works); check with `dumpbin /EXPORTS`, and `dumpbin /DEPENDENTS` should show only
   `KERNEL32.dll` when the ReShade import lib is correctly absent. ReShade only loads add-ons named `*.addon64`
   (or `*.addon`) from its add-on path, so install the DLL under that extension.
3. **Shader**: the `.fx` goes to `Win64\reshade-shaders\Shaders\`.
4. **Preset**: `Win64\ReShadePreset.ini` needs **both** a `Techniques=<name>@<file>.fx` line **and** a section
   named after the technique with `f0_active=1`. One without the other silently does nothing, and the
   ReShade overlay rewrites the preset whenever the user touches it, so keep a master copy and redeploy it
   before every run.
5. **Lua mod**: `Win64\ue4ss\Mods\<Name>\Scripts\main.lua`, enabled in `Win64\ue4ss\Mods\mods.txt`. A
   deployment script that adds the whole `mods` directory at once will enable the dangerous probe mods too -
   add entries by name, and deploy with the flag that preserves the existing mod list whenever a specific
   configuration is being prepared.
6. **Waiting for the world:** do not use a file's growth as a "world is loaded" signal - see Gotcha 16.
7. **Checks that catch layout drift**: a Python script that compares the shared-memory constants in the
   add-on against the format document (29 checks), and the publisher's own unit tests (16).

## Verification

The oracle was a debug view inside the compositor plus a pixel scan of a captured frame, with a human eye as
the final check. One rule was learned the hard way and is worth repeating: **no conclusion about a run until
the harness has reported an explicit survived-or-died verdict**, because a process that looks healthy may be a
hung game or a crashed one sitting on a dialog. Numbers from the working configuration (2026-10-08/09):

- **Pose writes:** from the game thread, **sustained for 15 minutes** with 0 errors and 0 crash dumps - at the
  time, far longer than any earlier run had lasted. The harness reported the rate as 75.1 k/s. That can't be
  pose records per second (the game-thread timers fire at most once per frame), so the unit is unconfirmed.
- **Occlusion, proven numerically.** With the debug view set to the depth-difference mode, the guest layer
  region contained **3315 green pixels** (guest nearer than the host surface, therefore visible) against
  **2532 red pixels** (guest behind the host surface, therefore occluded). The green region's bounding box was
  `x 1200..1366, y 652..790`, matching an independently measured frame from an earlier run
  (`x 1200..1367, y 648..790`). This is the claim that the layer is correctly hidden by host geometry, and it
  is a count, not an impression.
- **The layer actually composites.** With the haze calibration fixed, a scan of the frame found **4651** pixels
  of the layer colour, the strongest being exactly `RGB(255,0,255)`, which is the publisher's test-cube
  colour.
- **The layer renders in the real game**: a human confirmed the cube visible in the host's world, following
  the camera.
- **The proof is a recording, not a screenshot.** Clips were captured with `um video` so that any claim can be
  re-checked by someone else, and so that a claim about a moving picture is not judged from one still.

Not verified: which host depth layout is correct, since the uniform is never set; whether the publisher's
per-publish allocations matter under load; flat faces on the test cube; camera pitch in the layer.

## Gotchas

1. **A copied compositor keeps the original's units, and nothing tells you.** Symptom: four separate
   failures, each looking unrelated - the layer's far plane collapsed from 400 m to 4 m so nothing beyond
   4 m was ever visible; a depth-band debug view rendered a completely black frame; the reprojection ray
   search hit its limit at 4 m; and a test cube specified as 8 m stood 8 cm from the camera. Cause: the
   compositor was copied from an example whose host measured in metres, while Unreal measures in
   centimetres, and every constant came across unchanged. Fix: treat **every number** from a foreign project
   as unverified until its unit is re-derived, and re-derive it from the target's own units.
2. **A haze constant in metres silently erases the whole layer.** Symptom: the layer was invisible in normal
   view while the depth-difference debug view said it was visible and nearer than the host. Cause: a distance
   falloff of `1 - exp(-(z - start) / length)` with a length of 160 (metres) against a layer at 1500
   centimetres gives `exp(-9.3) ~ 0`, so the falloff was 0.85 and 85 % of the layer was replaced by blurred
   host colour. It was still there, just washed out - which is why a naive "is it visible" check said no.
   Fix: set the falloff distance in the host's own units and re-check.
3. **`LoopAsync` plus reading UObjects crashes, inside UE4SS.** Symptom: `ACCESS_VIOLATION` with the fault
   address inside `UE4SS.dll` (offset `0xC653A5`), reproducible on every attempt. Cause: reading a UObject
   from a foreign thread races the graphics hooks ReShade installs. `ExecuteInGameThread` at 60 Hz did not
   help. Fix: use this build's game-thread timers, `LoopInGameThreadAfterFrames(frames, cb)` and
   `LoopInGameThreadWithDelay(ms, cb)`. The older `LoopAsync`/`ExecuteAsync` are marked deprecated here.
4. **UE4SS's `HookProcessConsoleExec` crashes the game on its own.** Symptom: death at about +55 s with the
   hook enabled, 120 s clean with it disabled. The hook fails to install five times over
   (`detour installation likely failed`). Fix: keep it off. This, and not the mere presence of the other
   mods, is what made the stock mods look dangerous.
5. **The stock UE4SS mods are not safe alongside your own.** Symptom: each is fine alone, together they die at
   about +20 s. Fix: disable them all. (Related: UE4SS's `LogicMods` do not survive a mod restart, and
   `mods.txt` does affect loading.)
6. **ReShade must be the `dxgi.dll` proxy, not `d3d12.dll`.** Symptom: the `d3d12.dll` variant loses the
   device after 22 seconds with `DXGI_ERROR_DEVICE_REMOVED` caused by `DXGI_ERROR_INVALID_CALL`. Fix:
   `dxgi.dll`.
7. **An HLSL debug marker can kill the whole shader file, silently.** Symptom: the effect appears not to work
   at all, no error in the log. Cause: HLSL rejects code after an unconditional `return` as unreachable code,
   and one file failing means the whole technique fails. Fix: never put a marker after a `return`, and
   **treat every conclusion drawn from the picture after such a change as false until the log is clean.**
8. **ReShade 6.8's `log::message` takes no varargs.** Symptom: garbage or a hard failure in the log call.
   Fix: format into a buffer yourself and pass one string.
9. **Lua cannot write shared memory.** Symptom: no way to publish pixels from the mod. Fix: publish the pose
   through a file and let a native binary do the shared-memory work.
10. **"UFunction calls do not work" is usually the wrong conclusion.** Symptom:
    `attempt to call a TrivialObject value (method 'SetVisibility')` - the method access returns a wrapper,
    not a function. **Cause: the function does not exist on the object you called it on.**
    `SetVisibility` belongs to `USceneComponent`, and there is no such function on `AActor`; calling it on
    the actor fails, and the natural but wrong reading of that is "calls are broken in this binding". On the
    component the same call is a normal UFunction call. Fix: before concluding that a call mechanism is
    broken, check that the function exists on that class - the generated SDK lists every UFunction per
    class, so the check is a file read, not an experiment.
11. **A flags byte that nobody reads is worse than no flags byte.** Symptom: the layer renders upside down
    while the documentation says it should not. Cause: the descriptor's flags say "rows already top-down" but
    the publisher writes rows bottom-up; the shader ignores the flags entirely and flips unconditionally,
    which happens to be right. Fix: read the flags, or delete them; never trust a flag that no code reads,
    and never trust the documentation over the code that writes the data.
12. **UE4SS can generate the whole SDK with property offsets, and nobody told us.**
    `GenerateSDK()` is a global of the loader core; the built-in `Keybinds` mod binds it to `Ctrl+H`, but
    with `Keybinds : 0` in `mods.txt` the binding is never registered - and the function can be called
    straight from your own mod. It writes **`ue4ss\CXXHeaderDump\`** (about 1800 headers), not the
    `UE4SS_SDK` directory the setting's name suggests, and every field carries
    `// 0xOFFSET (size: 0xSIZE)`. This is the cheapest route to real offsets: it replaces guessing field
    names with reading them. Caveats: it unloads forcefully loaded assets, and the game tends to die a
    dozen seconds later; and the byte layout of a bitfield is not in the header, only the declaration
    order is, so the exact bit still has to come from a measurement.
13. **Reading a field of a struct on a pawn crashes UE4SS and the game.** Symptom: `Unhandled exception`
    with the whole stack inside `UE4SS.dll`, reproducibly, and the crash dialog offering to open a support
    page. Cause: not fully established. A struct that did not resolve returns **itself** when you ask for a
    field, so `X`, `Y` and `Z` all come back as the same address. On the same class, `RelativeLocation` belongs
    to `USceneComponent` and does not exist on the actor itself, and `ComponentToWorld` is an `FTransform`
    that this binding does not expose at all. A read-only probe that touched no struct fields also crashed,
    so the trigger is wider than struct access. Fix: treat any field access on a pawn as high risk, keep
    probes to a single read, and prefer a native path that writes through a pointer you already hold.
14. **Do not guess property names.** Symptom: of four guessed names, exactly one appeared to work - it
    round-tripped a value - and the game crashed shortly after. Fix: obtain real offsets. Names that look
    right are not evidence, and a self-consistent read/write round trip on a wrong address proves only that
    the same wrong address was read and written.
15. **The game writes its own crash dumps, in two places.** Symptom: hunting for a minidump that was not
    where you looked. Fix: look in the game folder (about 129 MiB per dump) and in
    `%LOCALAPPDATA%\HogwartsLegacy\Saved\Crashes\<GUID>\CrashContext.runtime-xml`, which carries the error
    message, the crash type and the call stack.
16. **A screenshot taken too early is not a measurement.** Symptom: repeated scans reported the layer absent
    while a human could see it on screen. Cause: the capture landed on a loading screen or on the crash
    dialog, and the "world is loaded" signal being used was a file that grows in the menu too. Fix: use a
    signal that only exists with a live world (a live pawn), detect the crash dialog before capturing, and
    confirm the game is actually rendering - a process that is alive is not proof, because a crashed game
    stays alive showing its dialog. Never conclude "the layer is missing" from a scan without a human
    confirming the same frame.
17. **`LS-0018` from the Epic launcher means an instance is already running.** Symptom: the launcher refuses
    to start the game. Cause: a previous instance is still alive - possibly sitting on the post-crash dialog,
    which looks like a healthy running game. Fix: look for the process and for that dialog before assuming
    the launcher is broken.
18. **A file bridge is fine for 112 bytes and wrong for tens of megabytes.** Symptom: the pose bridge works and
    the pixel path would not. Cause: per-frame file opens, latency and truncation. Fix: keep the file for the
    pose only, and have the native side write the pixels straight into shared memory.
19. **The add-on binds textures and uniforms by string name, and a mismatch is silent.** Symptom: the effect
    simply does nothing, with no error anywhere - the shader compiles, the preset is enabled, the add-on
    loads and reports itself as registered, and the frame is unchanged. Cause: the shader declares a texture
    with a semantics name and the add-on binds it by passing that name as a string; the same goes for
    uniforms, which the add-on looks up by name. Rename one side without the other and the texture stays
    unbound (the sampler reads nothing) while the uniform handle comes back as zero. Fix: rename both sides
    in the same change, and read the add-on's own diagnostic line, which prints the uniform handle - a
    non-zero handle is proof the lookup succeeded.
20. **The window about unofficial mods appears after a crash, and it is easy to misread.** Symptom: the game
    seems to refuse to start and complains about mods, and it is tempting to blame the mods. Cause: the dialog
    is the game's crash report - its own text says a crash occurred - and dismissing it returns to the menu.
    Fix: read the text, treat it as a crash report, and go looking for the dump.
21. **The Epic overlay is only switchable through an environment variable.** Symptom: the overlay draws over
    the game and there is no setting for it anywhere in the launcher. Fix: set
    `EOS_OVERLAY_DISABLE_VULKAN_WIN64=1` in the launch configuration.
22. **The save folder and the game folder are spelled differently.** Symptom: a backup of the "game folder"
    contains no saves. Cause: the saves live in `HogwartsLegacy` **without** a space, and the spaced
    directory holds only `Mods`. Fix: take the backup from the save path, and check it is not empty.
23. **A retracted claim about the crash is still a claim someone will make.** In one day the diagnosis of
    these crashes changed six times, and the plausible-sounding conclusions that were withdrawn are worth
    listing, because the next person will re-derive them:
    - "ReShade is incompatible with UE4SS" - the crash reproduces **without** ReShade.
    - "The crash happens even with the mod disabled" - that observation came from a different build and was
      never verified.
    - "Our mod is not to blame" - every one of the six crashes happened with the mod **enabled**.
    - "The stock mods make the game hang" - the hang was in a session that had been killed at the start of
      the next one, so it was never a hang.
    - "FPS dropped because of UE4SS's OpenGL console" - unverified; re-sorting layers in the scene explains
      it better.
    - "The hypothesis about the flapping hook is disproved" - it was declared from a screenshot of an
      unfinished measurement, and the crash actually arrived 55 seconds after that measurement.
    Fix: when a diagnosis changes, write down what was withdrawn, not just what replaced it.
24. **A measurement harness will lie to you, so make it report a verdict rather than a heuristic.** Symptom: a
    session was declared healthy while the game was actually hung - frames stopped, the process was alive, and
    the verdict was "survived". Fix: no conclusion at all until the harness reports an explicit survived-or-died
    verdict; check the known ways a harness flatters itself, which here were: "alive" meaning only "the process
    exists"; a marker file not validated by timestamp in attach mode, so a stale non-empty file reported the
    world loaded instantly; a 30 second window that hides an early crash as a launcher restart; a "newest dump"
    lookup that surfaces an old dump as the after-state when there is no new one; and a start time taken from
    the log while the countdown began at detection.
25. **A deploy script that enables everything it finds will quietly spoil a controlled measurement.**
    Symptom: the mod list was deliberately narrowed to one entry, the measurement ran, and afterwards four
    mods were enabled. Cause: the deploy step enables every mod it finds in the mods directory, and it ran
    after the configuration was set. Fix: always deploy with the flag that preserves the existing mod list
    when a specific configuration is being prepared.
26. **Per-publish allocations dominate the publisher, not the pose read.** Symptom: the publisher's counter
    reached about 8.4 k against 75.2 k for the pose, in the same unconfirmed unit as Verification (8.4 k
    publishes a second of two 14.7 MB buffers would be about 250 GB/s). Cause: every publish allocates and
    zeroes two buffers of 14.7 MB (2560 x 1440 x 4 bytes) each and then writes the layers element by element.
    Fix: reuse the buffers.

## Assets

None. The only visual content is a solid-colour test cube rasterised by the publisher. No game assets were
extracted, unpacked or redistributed, and no decompiled code is included here. The compositor shader and the
add-on are this project's own code, started from the in-repo example linked above and then rewritten. A
related, non-trivial predecessor worth reading is a Garry's Mod pass-through project (MIT), linked above: it
shows the same shape of problem - a foreign game drawn into a host's frame - solved in a different engine.

## Cost and time

One evening's worth of sessions to get the chain closed and the occlusion proven, plus a longer evening spent
on the hide mechanism, which is where five game crashes came from. Most of the time went into instrumentation
rather than graphics: the pose bridge, the depth encoding, the shared-memory layout, the calibration of a
dozen constants, and a measurement harness that had to be rewritten twice because its "world is loaded" signal
was wrong. An original estimate of 34 hours for the wider project was taken from a different codebase and does
not hold: the reconnaissance phase alone took over a day, most of it spent finding the cause of crashes rather
than on new features.

## Open questions

- **Writing a property on a host actor.** The offsets can now come from UE4SS's CXX header dump
  (`GenerateSDK()`, Gotcha 12), and names can't be guessed (Gotcha 14). What's open is making the write safely,
  given the crash in Gotcha 13. The promising route is to bypass the binding that keeps crashing - read only an
  object's **pointer** in Lua, pass that pointer through shared memory, and have the native add-on write the byte
  directly, where memory access is under our control. A bitfield's exact bit still has to come from a
  measurement.
- **Which host depth layout is right.** The uniform is never set by the add-on, so a default is assumed. The
  depth-difference debug view is consistent with the assumed one, but that is not an experiment.
- **Publisher throughput.** About 8.4 k published frames against 75.2 k of pose (unit unconfirmed, see
  Verification), and the gap is allocation and writing, not reading the pose file.
- **The crash trigger for field access on a pawn is not established**, and a read-only probe triggered it too.
  Until it is, any further in-game probing on that class is a gamble.
- The test cube has flat faces, and the publisher does not apply camera pitch, so the layer's vertical
  position does not follow the host camera.
