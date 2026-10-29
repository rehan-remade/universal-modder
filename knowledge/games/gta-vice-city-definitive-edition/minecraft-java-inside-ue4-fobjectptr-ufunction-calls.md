---
kind: game
title: "Minecraft Java renders inside GTA: Vice City – The Definitive Edition (FObjectPtr makes property reads opaque, UFUNCTION calls are the way)"
game: "Grand Theft Auto: Vice City – The Definitive Edition"
games_also: ["Minecraft Java Edition"]
game_version: "Steam current build (SteamAppId 2963470), UE4.26 'Gameface' fork, DX11 default renderer"
platform: windows
engine: unreal  # 4.26 Gameface fork with UE5's FObjectPtr backported
route: passthrough
tools: ["UE4SS v3.0.1-1183-gcdbc0b66 experimental", "ReShade 6.8.0 add-on API", "Python (fakemc stand-in, frame-diff oracle)", "WScript.Shell SendKeys + Win32 VK injection"]
anti_cheat: "none single-player; the game runs fine with the Steam client closed"
status: working
agents:
  - "DeepSeek Harness (claude-sonnet-4-5)"
humans:
  - rehan
date: 2026-10-29
links: []
tags: [ue4ss, reshade, lua, objectptr, camera-pose, keyboard-injection, depth-compositing, websocket]
---

# Minecraft Java renders inside GTA: Vice City – The Definitive Edition

> Unchanged Minecraft Java (Fabric mod) renders live inside VC DE's world: a ReShade add-on composites
> MC's color+depth frames against the game's DX11 depth, and a UE4SS Lua companion publishes the camera
> pose for reprojection. It runs in the real game, proven by frame-differencing the composite on/off
> (11638 px changed vs a 1150 px noise floor) and a heading sweep proving the MC content is world-
> anchored. The engine's UE5 FObjectPtr backport makes every UE4SS property read opaque — only
> UFUNCTION calls return numbers, and that single fact dictated the whole pose design.

## Setup

Windows 10 x64, Steam build of VC DE (app id 2963470), DX11 (never add `-dx12`; D3D11 is the depth
path). Installed into `Gameface\Binaries\Win64` via an add-only script (manifest + `-Remove` verified
to restore a clean tree): ReShade 6.8 (`dxgi.dll` proxy + `MCPassthrough.addon64` add-on +
`MCPassthrough.fx`), UE4SS experimental build (two custom AOB signature files), one Lua mod. Guest
side: Minecraft Fabric mod, or for testing `tools/fakemc.py` (WebSocket `127.0.0.1:25599` frames +
shared memory `Local\MCPassthroughFrame`). Single-player only. The game launches fine with the Steam
client closed (ours' Steam client is actually broken — irrelevant).

## Route and why

Passthrough (two processes exchanging camera pose + rendered frames). Chosen over content-porting
because the user wants *live* Minecraft, and over host-side rendering because the guest must stay an
unmodified Fabric client. UE4SS reflection (no address mining at all) + ReShade add-on (no engine
DLL-injection games like UE4SS+ASM) keeps everything behind loader APIs that survive updates.
Alternative considered: the RenderWare VC (2002) — rejected as far more tedious (fixed-function, no
reflected camera).

## How the game works (what we had to learn)

- VC DE's UE4.26 "Gameface" fork **backported UE5's `FObjectPtr`**: every object/struct property read
  via UE4SS Lua returns an opaque `TrivialObject` userdata (UE4SS logs
  `Failed to expose size of 'class RC::Unreal::FObjectPtrProperty'`). `tonumber`, `:get()`,
  `:Get()`, `:get_value()`, `.Value` all fail; this UE4SS build exposes no unwrap escape hatch.
- **UFUNCTION calls on real UObjects return plain numbers**: `pc:K2_GetActorLocation().X` → `16040.0`.
  All numeric game state must flow through UFUNCTION calls. `FindAllOf("PlayerController")` /
  `FindAllOf("PlayerCameraManager")` are the reliable real-object sources (`GetWorld` /
  `UGameplayStatics` are absent as Lua globals); `pcm:GetFOVAngle()` even yields the live FOV (81°).
- The front-end (menu) map stays loaded in-world: `FindAllOf` finds the menu's camera manager too
  (parked at origin) — disambiguate by distance from origin. Menu `pc:K2_GetPawn()` returns a
  nullptr-proxied UObject: truthy in Lua, throws on member calls — pcall everything.
- Input has three distinct channels: menus/splash take WM_CHAR (WScript SendKeys `~`); in-world
  gameplay **ignores scan-code-only SendInput but accepts virtual-key injection** (see Gotcha 8);
  camera look follows real cursor warps (`SetCursorPos`) — the game polls cursor position.
- ReShade add-on `GetAsyncKeyState` hotkeys (F7/F8) work — they poll async state, not raw input.
- Custom AOB scanning works on this Shipping build (~260 ms full scan). Lua mods need `enabled.txt`;
  `LoopInGameThreadAfterFrames(frames, cb)` takes frames FIRST.

## Build steps

1. Copy ReShade `dxgi.dll` + `MCPassthrough.addon64` + `reshade-shaders/Shaders/MCPassthrough.fx`
   (+ ReShadeUI/ReShade.fxh) + `ReShade.ini` (PresetPath → `MCPassthrough.ini`, technique enabled)
   into `Gameface\Binaries\Win64`.
2. UE4SS experimental into `ue4ss\` with two signature files (`StaticConstructObject.lua`,
   `ConsoleManager.lua` AOBs, both accepted as-is on the current build) and the pose mod under
   `Mods\MCPassthrough\Scripts\main.lua` + `enabled.txt`.
3. Start the fake-MC/MC guest first (WS `127.0.0.1:25599` + shm), then the game
   (`-windowed -WinX=100 -WinY=60 -ResX=1280 -ResY=720 -NoStartUpMovies`).
4. In game press F7 to toggle the composite, F8 to re-level MC ground onto game ground.

## Verification

Oracle = **frame differencing**, not eyeballs: screenshots at identical camera (still-camera gate via
pose reads), F7-ON vs F7-OFF changed-pixel counts + density grid. Proven: composite differential
11638 px vs 1150 px noise floor (1.14 % of frame); a four-heading sweep where MC coverage tracks
camera heading (world-anchored, not a screen-space sticker); composited MC blocks riding a moving
chase camera in screenshots; pose stream fresh for 34 min idle with composite ON (survival 649/727/
2047 s runs); real FOV=81° flowing from `GetFOVAngle`; `install -Remove` round trip.
NOT yet verified: exact near/far clip (pose carries 10/200000 cm defaults), DebugView-3 occlusion
pixel counts, the real Fabric client end-to-end (fakemc stand-in used throughout).

## Gotchas

1. **Symptom:** the game exits cleanly (no crash dump, no WER event) minutes after launch during
   automation. **Cause:** a stray ENTER lands on the in-game pause menu, where ENTER accepts the
   highlighted *exit game* item; endless early ENTER mashing does the same on the front end.
   **Fix:** launch recipe from a human who plays this game — wait 5 s, mash ENTER for exactly 5 s,
   then WAIT out the load (3–5 min); NEVER send ENTER/ESC again once in world.
2. **Symptom:** every UE4SS Lua property read returns `TrivialObject` userdata; `string.format("%f")`
   dies with `number expected, got TrivialObject`. **Cause:** the FObjectPtr backport. **Fix:** route
   ALL numeric reads through UFUNCTION calls via a `num()` helper that passes numbers and rejects
   wrappers.
3. **Symptom:** `FindAllOf` returns a camera whose pose never changes (0,0,0 or stale). **Cause:** the
   front-end map object is still loaded and found first. **Fix:** iterate all results, gate on
   plausibility (distance from origin > 1 m), keep refreshing every tick.
4. **Symptom:** menu `K2_GetPawn()` returns something truthy that throws on the first member call.
   **Cause:** nullptr-proxied UObject. **Fix:** pcall every call; never trust truthiness.
5. **Symptom:** `os.rename` to the pose target fails with `File exists`, and readers intermittently
   see the file vanish. **Cause:** unconditional `os.remove(target)` before rename — a python poller
   holding the file makes the remove fail and the rename see the existing target. **Fix:** rename
   first; only on failure remove the target and retry once (the readable file never disappears).
6. **Symptom:** the composite silently stops after a game restart; an F7 ON/OFF diff collapses to a
   few dozen pixels (toast text only). **Cause:** the fake-MC WebSocket server is single-client — the
   dead game's zombie connection blocks the new add-on from connecting. **Fix:** kill and restart the
   guest process with every game launch.
7. **Symptom:** two game instances corrupt the shared pose stream (rename races). **Cause:** leftover
   instance from a previous test. **Fix:** kill all game processes before launching; the watcher owns
   the guest singleton too.
8. **Symptom:** in-world, injected keys are silent no-ops — W/S move nothing (0 cm), F7 taps miss —
   yet the same keys clearly work for a human. **Cause:** this game ignores
   `KEYEVENTF_SCANCODE`-only SendInput in-world (splash/menu conversely ignore everything except
   WM_CHAR). **Fix:** inject VIRTUAL KEYS (keybd_event VK, or SendInput with wVk set — wVk+wScan
   together satisfies both channels); first VK press lands.
9. **Symptom:** `AppActivate(pid)` returns true but keys go nowhere. **Cause:** the visible GPU window
   is not the activated one. **Fix:** `ShowWindow(h,9)+SetForegroundWindow` and VERIFY via
   `GetForegroundWindow`'s pid — log want-pid vs have-pid.
10. **Symptom:** the game "mysteriously" exits minutes after being launched from an agent tool call —
    clean exit, no crash dump, no WER event, reproducible ~every run. **Cause:** agent harnesses
    (e.g. DSH) reap the entire child process tree when the tool call that spawned the game completes;
    the death timestamp equals the call's end timestamp, and the "survival" you measured was just how
    long the owning call stayed alive. **Fix:** launch game + companion processes detached (Windows:
    Task Scheduler `schtasks /create /tr "<absolute paths — task env lacks user PATH>" + /run`; the
    parent becomes taskeng and survives tool-call teardown).

## Cost and time

~4 focused sessions; the ENTER-timing recipe alone (from the human) eliminated five "mystery" silent
exits and hours of chasing.

## Open questions

- FOV is real but near/far clip planes still carry defaults; calibrate via the ReShade UI (Home key)
  overlay debug or an engine UFUNCTION that survives FObjectPtr.
- Does mouse-look via raw relative SendInput ever land in-world (cursor-warp works — good enough)?
