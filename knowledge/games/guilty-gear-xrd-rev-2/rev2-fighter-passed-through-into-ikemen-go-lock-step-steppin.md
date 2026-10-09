---
kind: game
title: 'Rev2 fighter passed through into IKEMEN GO: lock-step stepping, shared GPU layer and frame pacing'
game: Guilty Gear Xrd REV 2
games_also:
- IKEMEN GO
game_version: 'Guilty Gear Xrd -REVELATOR- (REV 2) Steam app 520440, build 11284329, 32-bit GuiltyGearXrd.exe (UE3, D3D9); IKEMEN GO pinned at commit 07558c8 (universal-fighter fork)'
platform: windows
engine: unreal
route: passthrough
tools:
- Frida 17.22.2 (Python bindings + JS agent)
- capstone 5.0.7 (offline disassembly)
- D3D9On12 (Windows' Direct3DCreate9On12)
- WGL_NV_DX_interop2 + D3D11/D3D12 shared handles
- MSYS2 MinGW64 Go toolchain (IKEMEN build)
anti_cheat: 'none in offline Training mode. The agent refuses to install outside offline Training (it checks the game mode) and nothing touches online play.'
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-08'
links:
- https://github.com/jerezereh/universal-fighter/tree/passthrough-v2-receiver
tags:
- fighting-game
- lock-step
- frame-pacing
- ue3
- d3d9on12
- shared-gpu-texture
- wgl-nv-dx-interop
- frida
- ikemen
---
# Rev2 fighter passed through into IKEMEN GO: lock-step stepping, shared GPU layer and frame pacing

> A live Guilty Gear Xrd REV 2 fighter (Sol, in offline Training) plays as a character inside IKEMEN GO. IKEMEN steps
> Rev2 one frame at a time (lock-step) over a loopback protocol; Rev2 renders the fighter into a named shared D3D12
> texture that IKEMEN samples with no CPU copy; hits found by IKEMEN's collision are replayed through Rev2's own hit
> pipeline, so Rev2 plays its native reactions. Verified with AI-vs-AI smoke matches in the real games (exit codes,
> per-step logs, screenshots) and by the human playing. Inside IKEMEN it is **not playable at 60 FPS** on an Iris Xe
> laptop: lock-step puts the whole guest round trip inside every host frame. A minimal custom arena (Rust, D3D11) that
> runs a pipelined tick barrier instead holds **60 drawn FPS** with the same Rev2 fighter; the human confirmed it plays
> well hands-on. The frame-pacing findings below are the main reason for this note.

## Setup
- Windows 11, Intel Iris Xe (integrated; shared by both games), 60 Hz panel.
- Rev2: Steam build 11284329 (exe SHA-256 starts `2d737e60`). It is launched through a small Frida host that sets
  `SteamAppId`/`SteamGameId` in the environment (no Steam relaunch) and redirects `Direct3DCreate9` to
  `Direct3DCreate9On12` at spawn, so the game's D3D9 device runs on D3D12 and its resources can be shared.
- Producer (private repo): a long-lived host process owns the one Frida session per game process; producer scripts
  connect to it over loopback. The JS agent hooks the game; Python speaks the receiver's protocol.
- Receiver: IKEMEN GO at a pinned commit, built with MSYS2 MinGW64 Go, with a passthrough runtime (public, link above)
  that treats a remote process as a character: length-prefixed JSON (`hello/reset/step/hit/contact/defeat`), strict
  session/sequence/tick checks, and a negotiated `shared-layer:d3d12` extension for the GPU image.
- Hook sites are resolved offline from the installed exe (every pattern must match exactly once, derived sites are
  bounds-checked, loaded bytes are compared with disk before patching). Most sites follow kkots'
  ggxrd_hitbox_overlay, which is MIT with a no-AI-training clause; its patterns are not reproduced here.

## Route and why
Passthrough (mashup-mods Pattern 2) instead of porting: the point is Rev2's real animation, renderer and hit
reactions. Unlike the GTA V / Portal 2 / HL2 passthrough notes, the guest is **stepped in lock-step** by the host
rather than free-running: a fighting game needs Sol's pose, hitboxes and the opponent on the same tick, and camera
re-projection (how those notes hide latency) has no equivalent for 2D animation frames. That choice is what makes
frame pacing hard; see Open questions for the alternatives.

## How the game works (what we had to learn)
- **Freezing and stepping the battle.** The world tick is entered from one call site in the engine loop; patching that
  call (not the function) lets the agent decide per loop whether the battle advances. The offline battle update and
  `TickActorComponents` are skipped on frozen loops, and `IsPaused` is answered "paused" on the right call so UE3
  keeps rendering. One allowed tick = exactly one battle frame (checked against the engine's tick counter).
- **Input.** The fighter's input word is substituted at the *entries* of the battle input push and its sink, filtered
  by return address to the battle caller. Training's own button-history UI keeps working.
- **Rendering a clean layer.** Camera is forced to a side view centred on the fighter (as the overlay's GIF mode does),
  HUD, darkening and the Training HUD are suppressed, the dummy is parked off-screen. A D3D9 pixel-shader pass at
  `Present` turns the backbuffer into a premultiplied layer (coverage = max(1 − A, max(rgb))), then the underlying
  D3D12 resource is copied on a D3D12 queue into a **named shared texture** and a **named shared fence** is signalled.
  All D3D resources are created and released on the render thread.
- **Native hits.** Copying the attacker's attack into the defender's received-attack record and calling the game's
  deal-hit routine applies hitstop but no reaction; also setting the defender's "hit this frame" flag and hitstun
  makes Rev2 play its own reaction (`CmnActNokezoriLowLv3` for a 16-frame result). Calling the per-pair active-frame
  hit routine directly was rejected by the game.
- **Settle.** The fighter's new pose is in the first `Present` after the tick (measured 101/101).
- **UE3 frame pacing (the part that matters for lock-step).**
  - The engine loop runs `appUpdateTimeAndHandleMaxTickRate` (UE3's frame-time limiter) every iteration. It asks the
    engine object for `GetMaxTickRate(DeltaTime, bAllowFrameRateSmoothing)` (a virtual on `GEngine`) and sleeps
    (1 ms `appSleep` steps, then spins) until 1/rate has passed. Rev2's override clamps a configured rate to 20..60.
    The `GEngine` global and the vtable slot can be found from that call site.
  - `GetMaxTickRate` is a `thiscall` returning a `float` **on the x87 stack**, and the callee pops its arguments.
  - The game's `UseVsync` setting (REDSystemSettings.ini) also holds `Present` to the display refresh.
  - The game thread and the render thread are separate; `Present` itself took ~1.5 ms.
- **IKEMEN's main loop** (pinned commit): logic tick → draw → `await` (swap, then drain `sys.mainThreadTask`, then sleep
  to the schedule). When a tick finishes more than ~17 ms late it keeps ticking **without drawing** (frame skip),
  drawing at least every 250 ms and re-basing the schedule when 150 ms behind. Its debug FPS counter counts **drawn**
  frames.

## Build steps
1. Resolve hook sites offline from the exe; refuse on any missing or ambiguous match.
2. Start the host: spawn Rev2 with the Steam env vars, redirect `Direct3DCreate9` → `Direct3DCreate9On12`, force
   `D3DPRESENT_INTERVAL_IMMEDIATE` in `CreateDevice`/`Reset`, keep the Frida session for the game's lifetime.
3. Open offline Training; the producer connects to the host, installs (or re-arms) the agent, freezes the battle,
   primes one frame (so the receiver's first request meets its deadline) and listens on loopback.
4. Patch the `GEngine` vtable slot for `GetMaxTickRate` with a small native stub (below); serve steps.
5. IKEMEN loads a passthrough character definition pointing at the producer's address with `shared_layer` enabled.
   The receiver opens the named fence (D3D12) and the named texture (D3D11 `OpenSharedResourceByName`), registers a
   texture with WGL_NV_DX_interop2, and each frame waits for the reply's fence value before locking it for GL.

The `GetMaxTickRate` stub (all native, swapped in with one aligned pointer store after it is fully written):
park on an event while serving and idle (bounded wait), call the original, store its x87 result for diagnostics,
and if serving replace it with the configured cap (`fstp st(0)` then `fld [rate]`), `ret 8`.

## Verification
- Smoke matches: IKEMEN AI vs AI on both sides, an 8-second round, `-log` match result, exit code 0; per-step request
  log with agent-side phase times; a receiver profile line every 60 guest frames (guest ticks/s, IKEMEN drawn FPS,
  exchange time, layer import phases).
- Screenshots of the IKEMEN window (`ffmpeg` gfxcapture; `PrintWindow` returned black) showing Sol drawn from the
  shared texture next to a native IKEMEN character, with hitboxes.
- Read-only Frida session to confirm live facts: the swap chain's `PresentationInterval` after the override, the
  patched vtable slot, and per-thread `Sleep`/`WaitForSingleObject`/`Present` time.
- Frame data cross-checked against kkots' overlay by the human (5P: 4 startup, 4 active, 6 recovery).
- **Pacing results (single smoke runs, noisy):** native cap: ~15 ms per step, IKEMEN fell behind and drew 5-15 FPS
  in human play. Cap 240 + vsync off: steps ~11 ms, ~59-60 ticks/s. Unlimited cap: worse (Rev2 floods the shared GPU).
  Render on demand + IKEMEN vsync off + same-frame image: ~59 ticks/s, **drawn 35-37 FPS**.
- **Pipelined barrier arena** (frame N: collect every fighter's tick N, resolve hits, post tick N+1, draw N while the
  guests compute N+1; D3D11 compositor with GPU-side fence waits; waitable flip swap chain): 59.8-60 drawn FPS, guest
  step 9.8-12 ms entirely off the critical path (barrier wait ~0.05 ms). Per step inside Rev2: ~7 ms from pickup to
  captured layer; Python adapter 0.5 ms; shared-memory transport (below) saved ~1 ms over Frida RPC + a host hop.
- Not verified: guard, air hits, knockdowns, characters other than Sol; a second real guest in the arena.

## Gotchas
1. **IKEMEN looked fine in logs but drew 5-15 FPS on screen.** **Cause:** the profile counted guest ticks per second,
   IKEMEN's counter counts drawn frames; a host that runs late keeps ticking and skips draws. **Fix:** log both
   (IKEMEN's `sys.gameFPS` as "drawn" next to ticks/s). Judge playability by drawn FPS.
2. **Lock-step steps took ~15 ms no matter what.** **Cause:** each step waits for Rev2's next engine loop, which UE3's
   limiter holds to 60 Hz on its own clock, drifting against the host's; stretches of bad phase pushed every frame
   late. **Fix:** while serving, replace `GetMaxTickRate` (and turn vsync off); see 3-5.
3. **Overriding `GetMaxTickRate` from Frida JS had no effect and read back a garbage native rate (5e-37).** **Cause:**
   the float return lives on the x87 stack for this 32-bit `thiscall`; a JS `NativeCallback`/`NativeFunction` with a
   `float` return did not deliver it. **Fix:** a hand-written native stub in the vtable slot (Build steps). Verify by
   reading back the original's stored result (60.0).
4. **Raising the cap changed nothing until vsync was off.** **Cause:** `UseVsync=True` made `Present` wait for the
   60 Hz refresh. **Fix:** force `D3DPRESENT_INTERVAL_IMMEDIATE` in `IDirect3D9::CreateDevice` and
   `IDirect3DDevice9::Reset` at spawn. Normal play is unaffected because the native limiter still caps it at 60.
5. **An unlimited cap was slower than 240.** **Cause:** Rev2 redrew frozen frames ~170 times/s on the GPU IKEMEN also
   uses. **Fix:** a cap, then render on demand: park the game thread on an event while serving with no request in
   flight; a request wakes it at once. Loop-start wait fell from ~3 ms (p90 8) to ~1 ms.
6. **The guest image was one frame behind its own state and hitboxes.** **Cause:** the receiver queued texture
   updates on `sys.mainThreadTask`, which IKEMEN drains only in `await` *after* drawing and swapping. **Fix:** run the
   update directly when already on the main (GL) thread (identified inside the first queued task).
7. **Doing the shared-texture import before the draw made it slower (interop lock ~1 ms → ~3.2 ms on Intel).**
   **Cause:** `wglDXLockObjectsNV` synchronises with GL work already queued for the frame. **Fix:** open; candidates are
   holding the lock across frames or a different import path.
8. **Intel's GL rejected the D3D12 shared handle (`GL_EXT_memory_object`).** **Fix:** wait on the D3D12 fence on the CPU,
   open the texture in D3D11 by name, copy it into a local D3D11 texture registered with WGL_NV_DX_interop2.
9. **Fighter taunted on every install, even with no keys pressed.** **Cause:** Frida's relocated copy of a hooked
   `call` instruction passed the wrong stack slot to the input function. **Fix:** never attach at a call instruction;
   hook the callee's entry and filter by return address.
10. **Game crashed when a producer script exited.** **Cause:** Frida script teardown and listener detach raced the game
    thread inside Frida's dispatch. **Fix:** one host per game process that keeps the agent loaded; "uninstall"
    restores game state and leaves hooks dormant (pass-through); never detach while the game runs.
11. **Fighter froze mid-attack after a contact.** **Cause:** an attack-record hitstop field uses INT_MAX as "default";
    copying it through froze the fighter. **Fix:** sanitise the field and pass the host's hitstop.
12. **IKEMEN panicked on the first request (hello took 544 ms, timeout 500).** **Cause:** the first GPU capture is cold.
    **Fix:** prime one frame before announcing readiness.
13. **A hard-killed producer never wrote its report or restored the game.** **Cause:** `Popen.terminate` is
    `TerminateProcess` on Windows. **Fix:** start it in a new process group and send `CTRL_BREAK_EVENT`.
14. **...but raising `KeyboardInterrupt` from that handler later broke the host connection ("invalid host message
    size").** **Cause:** the exception landed inside a socket RPC and left half a reply unread. **Fix:** the handler only
    sets a stop flag that the serve loop checks between requests.
15. **The first frame timed out with no hint why.** **Cause:** the game window was minimized; UE3 stops presenting.
    **Fix:** detect a minimized window of the game's process and say so.
16. **Frames with a hit cost ~10 ms more.** **Cause:** hit/contact were separate requests, each an injection plus an
    observe that waits for a present. **Fix:** a `step-events` capability: hits for the previous tick ride in the next
    step and are queued ahead of its battle update.
17. **The guest could overwrite its shared texture while the host still copied it.** **Fix:** a second named fence
    ("release"): the host signals it after its copy (GPU-side), the producer's queue waits on it before the next copy.
    Negotiated per session, and the producer CPU-signals it whenever a session or the agent ends.
18. **With the release fence on, Rev2 and the host froze, and the arena became unkillable.** **Cause:** the producer
    captured a frame internally that the host never saw, so its release never came; Rev2's copy queue waited, Rev2's
    D3D9-on-12 queue waited behind it, and the host's GPU wait on Rev2's ready fence never completed (a process cannot
    exit with stuck GPU work). **Fix:** release off while capturing internally; the host also confirms on the CPU,
    bounded to 250 ms, that a guest's ready fence will complete before telling the GPU to wait on it.
19. **Shared-memory replies were occasionally missed in tests.** **Cause:** a late reply to an older command and the
    current reply can coalesce into one auto-reset event signal. **Fix:** trust the reply's sequence number and re-check
    it in short waits until the deadline.
20. **Walking stopped dead although the arena showed open space.** **Cause:** the guest kept its own position between
    sessions and had drifted to Rev2's stage wall (~1.26M world units); the camera follows the fighter, so nothing
    showed. **Fix:** guest positions are internal: start each session at Rev2's centre and shift the fighter back (with
    the host-to-guest anchor, so the host sees no jump) whenever it is in neutral far from centre.
21. **An asymmetric crop was wrong whenever the fighter faced left.** **Cause:** the crop was in screen left/right.
    **Fix:** back/up/forward/down, mirrored with facing; sized from measured per-move extents (effects reach the screen
    edges, the body much less).

## Assets
None created. The fighter is rendered live by the user's own Rev2; nothing from the game is copied or committed.

## Cost and time
About two days of agent sessions with one human launching games, opening Training and playing.

## Open questions
- **Lock-step inside an existing engine vs a barrier host.** Inside IKEMEN the per-frame cost was transport ~4 ms, Rev2
  tick ~2, render to present ~3, GPU layer copy ~1-2, IKEMEN import ~5 (an OpenGL interop lock on Intel). A pipelined
  barrier host removes the guest from the critical path at the cost of one frame of display latency, uniform for every
  fighter (as a game's own render thread does). Free-running guests with clock sync were rejected: drift drops or
  doubles animation frames and puts cross-game hits on variable ticks. Rollback would need Rev2 save states.
- **Pushback, walls and corner rules** should be the host's (coordinator's) for all fighters; today each guest applies
  its own and the arena has none. Guest-native post-processing and correct alpha for additive effects (true
  transparency instead of reconstructing it from colour) are open.
- Hit/contact properties (guard, air, knockdown, pushback) are mapped roughly; the protocol is being redesigned.
