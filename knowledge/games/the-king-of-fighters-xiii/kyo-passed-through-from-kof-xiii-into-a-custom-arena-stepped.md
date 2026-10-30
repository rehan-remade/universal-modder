---
kind: game
title: 'Kyo passed through from KOF XIII into a custom arena: stepped frames, native hit injection and a shared GPU layer'
game: The King of Fighters XIII
games_also: []
game_version: 'THE KING OF FIGHTERS XIII STEAM EDITION release v1.4b, Steam app 222940, build 151721, 32-bit kofxiii.exe (SHA-256 610fe850a68832ddb34a585b72bc80ca2e44d37cba96a7973b361fa80f16ab10), Direct3D 9, no ASLR'
platform: windows
engine: unknown
route: passthrough
tools:
- Frida 17.22.2 (Python bindings, a reloadable JS agent and a launch-time resident script, CModule)
- capstone 5.0.7 (offline disassembly of the installed exe)
- Python 3.12 + numpy 2.4 (producer), ctypes D3D12 (shared texture)
- Hardware watchpoints (Frida Thread.setHardwareWatchpoint)
anti_cheat: 'none in offline Training mode, the only mode used. Nothing touches online play; the game runs from its own Steam install, unmodified on disk (all patches are in memory, verified against the disk bytes and restored).'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-11'
links: []
tags: [mashup, passthrough, fighting-game, frame-stepping, hit-injection, d3d9, shared-texture, frida, cmodule, performance]
---
# Kyo passed through from KOF XIII into a custom arena: stepped frames, native hit injection and a shared GPU layer

> Kyo Kusanagi from the real KOF XIII (Steam, offline Training) plays inside a separate arena host. The host drives
> him one battle frame per host tick. Hits, guards and contacts go through KOF's own hit records, so his reactions,
> pushback, hitstop shake and hit sparks are KOF's. His isolated sprite reaches the host as a shared D3D12 texture.
> The host's conformance kit passes, a human played it ("it feels good"), and it holds 60 ticks/s with about 0.1
> late frames per second on an Intel Iris Xe laptop.

## Setup
- KOF XIII Steam (app 222940, build 151721, release v1.4b), 32-bit `kofxiii.exe`, Direct3D 9, image base 0x400000
  with no ASLR, MSVC RTTI present. Windows 11, launched windowed (`-w`).
- Frida 17.22.2 spawns the game and loads a "resident" script before resume, so it can hook device creation.
  A hook-free agent script handles reads and patches and can be reloaded.
- **Offline only.** KOF XIII has online play; everything here ran in offline Training. The resident script is
  loaded at spawn and stays for the life of the process (device hooks, the Present replacement and, with
  free-run, the present interval), so a KOF launched this way is instrumented in every mode. Never take it
  online (ranked or player matches): quit it and start KOF from Steam first.
- The host is a small custom Rust/D3D11 arena with a length-prefixed JSON protocol over loopback TCP: hello /
  step / hit / contact, with step events and a shared-layer image mode. The approach applies to any host that steps
  a guest and wants its native mechanics.
- The repos are private. The note describes them in prose; ask if you need the code.

## Route and why
Passthrough: run the real game, freeze it, step it one frame at a time, and read state, boxes and an isolated
sprite each step. The host owns position and resolves contacts; the guest applies the outcome through its own
code.
- **Reimplementation was rejected.** Converting the character into the host means extracting data and copying
  the mechanics, and it is only ever approximately faithful.
- **D3D9On12 was rejected.** Creating the device through D3D9On12 (`Direct3DCreate9On12`), which would make its
  targets shareable as D3D12 resources, crashed KOF in `dxilconv.dll` (shader translation). So the plain D3D9
  device is kept, and pixels go through a CPU readback, then an upload into a D3D12 shared texture made by the
  producer.

Related: `knowledge/techniques/frame-compositing-depth-and-pose-sync.md` (as in its bridges, the pixels cross on
the CPU here; only the producer-to-host hop is a shared GPU texture) and
`knowledge/techniques/bridge-contracts-ownership-units-and-lifecycle.md` (the host owns position and contacts, KOF
applies hits, and a lease restores KOF if the producer dies).

## How the game works (what we had to learn)
**Pause and step.**
- `GamePause` is a static object at `0x7f4980`. Its fields: `+8` pause request, `+9` "paused this frame", `+0xa`
  step request. Its update is vtable slot 1 at `0x443c90`.
- A step is complete when `+0xa` has been consumed **and** `+9` is back to 1. Reading as soon as `+0xa` clears
  races the battle update.
- The loop order per iteration is: `GamePause::update`, then render + Present, then the battle update. So a step
  always takes two iterations: the stepped battle update runs after that iteration's Present, and first appears
  in the next one.
- About 3 ms of other loop work runs before `GamePause::update`. Gating there instead of after Present lets that
  work overlap the wait for the host.

**Players.**
- `PlayerPort` is at `0x832098`, with the P1 controller at `+8` and P2 at `+0xc`. The AnimObj is
  `[[[controller+0x38]+8]+8]`.
- AnimObj fields: x / y / vy are floats at `+0x120` / `+0x124` / `+0x130`; action is at `+0x8c`, facing (float ±1)
  at `+0x138`. Controller fields: life `+0x50`, hitstop `+0xf4`, hitstun `+0x114`.
- The round-start separation is 384 world units. The host maps that to its own start distance.

**Input.**
- Each input object's held word comes from `0x443780` (the object is passed in `eax`); `0x443b30` stores it at
  `object+4`. P1's battle input object is `controller+0x18`.
- Raw words: right 0x1, up 0x2, left 0x4, down 0x8, LP 0x100110, HP 0x200440, LK 0x401220, HK 0x802080.
  Directions are screen-absolute.
- Replacing `0x443780`'s return value for that object drives Kyo whatever window has focus. KOF stops polling
  DirectInput while unfocused, so a DirectInput override died as soon as the host window had focus.

**Collision.**
- The manager is at `0x7eabf0`. It holds 2 × 5 per-frame circular lists from `+0x18`: 12 bytes per list, P2's block
  0x3c after P1's. Each node: next at `+0`, owner record at `+8`, box floats `[left, bottom, width, height]` at
  `+0xc` (y up), rect key at `+0x1c`.
- Lists: 0 push, 1 hit, 2 a proximity box (triggers guard stance), 3 hurt, 4 throw.
- The battle routine's passes: push `0x50d010` (0×0), clash `0x50d760` (1×1), `0x50da90` (1×2), hit `0x50db00`
  (1×3), throw `0x50ebd0` (4×3 and 4×0). Then the box display `0x50f210`, which runs after all of them and is a good
  snapshot point.
- Patching each pass's entry to `ret 4` (`ret` for the throw pass, whose manager is in `ebx`) switches off native
  interaction. The lists stay filled.

**Hit resolution.**
- The pair test `0x50db70` calls the resolver `0x50dca0(manager, &attacker record, &defender record)`. Records are
  `PlayerController::AvatarHook` owners; one record owns all of a fighter's boxes.
- The resolver writes its result into both records. Defender on hit: flags `+8 |= 0x1180`, damage at `+0xc` and
  `+0x18`, hitstop at `+0x10` and `+0x14`, reaction level `+0x20`, pushback float `+0x28`, attack id `+0x34`, last-hit
  stamp `+0x6c`, contact point `+0x88..`, spark id `+0x94`.
- On guard: flags 0x1c0, a guard value at `+0x24`, no damage. The attacker gets flags 0x800a on hit (0x800c on
  guard), its own hitstop at `+0x10` and the opponent's at `+0x14`.
- The controller reacts later in the same battle frame.
- **Injection:** write the same fields into Kyo's record at the entry of `0x50ca60` (the pass right after the hit
  passes). That reproduces a native hit or guard exactly. Damage and hitstop follow what you write; the reaction
  and its stun or blockstun length follow the attack id.
- Writing a spark id and contact point into the attacker's record makes `0x50ca60` spawn KOF's own hit spark, a new
  AnimObj drawn like a fighter.

**Attack data.**
- `0x50c170` is a named-parameter getter: the manager in `eax`, a rect key in `ecx`, an index 1–20 on the stack;
  it returns a float in ST0 (`ret 4`).
- Index names: Attack, AttackCore, HitBack, HitStop, HitStopCore, PushCore, PushedCore, AttackHard, AttackConcept,
  AttackAttribute, AttackKind, GaugeParam, RectType, guard_crash, stun, HitSlow, Score, Effect, ComboLimitRate,
  HitBackPattern.
- They are read from script tables. Called through a small thunk, this gives each hitbox's damage, hitstop,
  pushback, reaction id (RectType) and stun level. Block height is not among them.

**Rendering.**
- Each fighter is usually one `DrawPrimitive` (a 4-vertex strip) inside `AnimObj::Drawer::draw` (`0x40d8a0`, vtable
  slot 1; drawn object = `[[this+0x50]+8]`). Some moves add a second draw.
- They go into a 960×540 scene target through a vertex shader whose constants are: c0–c3 the sprite's world matrix
  (c3 = position, c0.x = −1 when facing right, since sprites are authored facing left), c4–c7 the view projection
  (one world unit = one target pixel; c7 holds the camera offset), c8 the viewport half-size.
- From those, each frame's crop and foot pivot are exact, with no camera address needed.
- KOF shakes the defender during hitstop by moving that transform about ±2.5 units. Anchor the pivot to the logical
  x, or the shake cancels out.
- The swap chain uses the default (vsync) present interval, and KOF resets the device after creating it.

## Build steps
1. **Launch.** Spawn `kofxiii.exe -w` with `SteamAppId=222940` under Frida, with Steam running (the variable only
   names the app; the Steam client still checks the licence). Load the resident before resume. It hooks
   `Direct3DCreate9`, then CreateDevice, Reset and Present (Present as a native replacement).
2. **Free-run (optional).** Set the present interval to immediate in both CreateDevice **and** Reset. Cap idle
   frames with a high-resolution waitable timer in Present.
3. **Isolation.** Pause through `GamePause`. Patch the five collision passes (checked against the disk bytes first,
   restored under a lease). Keep KOF's P2 a little ahead of Kyo on the host-facing side, so KOF's auto-turn agrees
   with the host.
4. **Each step,** through a shared-memory channel (a named mapping plus named events; the wake event is also the
   frame gate):
   1. write the placement, input and queued interactions, and set the step request;
   2. the stepped frame's box display gives the boxes and attack parameters;
   3. Kyo's draws, reported by a native DrawPrimitive filter, are replayed into a private A8R8G8B8 target with
      blending and depth off;
   4. at Present, read the state, StretchRect the crop into a 512×512 target, read it back, and copy it natively
      into the mapping, already premultiplied and mirrored to face right.
5. **Producer.** Upload the crop into a D3D12 shared B8G8R8A8 texture (a persistently mapped upload buffer and one
   CopyTextureRegion; a simultaneous-access texture needs no barriers). Send the layer description with its ready
   and release fences.
6. **While serving,** the native DrawPrimitive and Clear filters skip everything but Kyo, and the Present
   replacement skips the window swap.

## Verification
- **Conformance.** The host's kit passes in shared-layer and RGBA modes: 32 passed, 0 failed, 0 warnings. It covers
  sequence/tick rules, validity, hit and contact operations, step events, defeat, reset and nine malformed-request
  checks.
- **Native-behaviour oracles.**
  - A traced native LP on P2 against an injected LP on Kyo: same life loss, hitstop, hitstun and reaction action.
  - Iori blocking natively against an injected guard: same block reactions (actions 34/35, blockstun 28/36).
  - Contact sheets of seven moves: every stepped frame shows Kyo's whole sprite.
  - Contact sheets of the spark on hit and guard.
  - Each frame's sprite draw x equals the state x read at the same Present.
- **Robustness.** A producer killed with `taskkill /F` mid-session leaves KOF unpaused and unpatched, and rendering.
- **Hand play.** Four sessions; each finding is a gotcha below.
- **Performance.** Step median 5.8 ms standalone; host 60.1 ticks/s with 3 of 1797 frames late; KOF 47% of one
  core while serving.
- **Not verified:** specials and supers beyond normals, throws, KO, other characters, other stages, and online
  anything.

## Gotchas
1. **Steps read half-updated state.** Cause: `GamePause +0xa` is consumed at the start of the stepped frame, before
   its battle update. Fix: wait for `+0xa == 0` and then `+9 == 1`.
2. **The resident script loaded but had no RPC exports.** Cause: an early hook threw on a 3-byte stub (an empty
   virtual), so `rpc.exports` was never assigned. Fix: define exports first and guard every hook.
3. **Heap scans timed out (30 s RPC limit).** Cause: JavaScript loops over about 100M dwords. Fix: CModule
   kernels, in batches.
4. **Input worked until the host window had focus.** Cause: KOF stops calling `GetDeviceState` while unfocused.
   Fix: override the held word at `0x443780` for P1's controller input object. A hardware write watchpoint on a
   known input word found the writer in one try.
5. **`Memory.alloc`'d thunks crashed later.** Cause: Frida frees `Memory.alloc` memory when the JS pointer object
   is garbage-collected, even if a `NativeFunction` still holds the raw address. Fix: keep every allocation
   referenced from module scope. Test with a forced `gc()`.
6. **KOF crashed when I installed a CModule replacement from a probe.** Cause: the CModule's own data page is not
   writable, so storing the trampoline into a CModule global faulted after `Interceptor.replaceFast` was already
   live, and the next call went to address 0. Fix: keep CModule state in JavaScript-allocated memory passed as
   symbols, and make the C code skip, not call, while the original pointer is null.
7. **Per-draw `Interceptor.attach` failed ("wrong type").** Cause: Frida will not attach to a function you
   replaced. Fix: make the native replacement report the draws you care about through a `NativeCallback`.
8. **The sprite vanished during HP.** Cause: the drawer issues two draws there, and only the last draw state (a
   floor draw) was replayed. Fix: replay every draw inside the drawer, and crop to the union.
9. **The hitstop "freeze" felt like a stall in the host.** Cause: native hitstop (7–13 frames) shown without KOF's
   spark and shake. The pivot taken from the draw transform cancelled KOF's ±2.5-unit defender shake. Fix: anchor
   the pivot to the logical x, spawn KOF's spark through the record, and shake the host's dummy too.
10. **Native stun length ignores what you write.** Cause: the reaction animation ends the stun (it even rewrites
    the counter), not the controller counter. Fix: pick the reaction by attack id (light or heavy). This diverges
    from a protocol where the attacker owns stun frames: an open issue.
11. **`--free-run` did nothing at first.** Cause: KOF resets the device after CreateDevice, with its own present
    parameters. Fix: set the interval in Reset too.
12. **The first frame gate made steps take 120 ms.** Cause: the promise resolved inside the Present callback, then
    the same callback waited at the gate, and Frida delivers an RPC reply only when that callback returns. Fix: never
    block in the callback that resolves. Polling gates with `Thread.sleep` also released late (Windows sleep
    granularity), so use a Win32 event.
13. **330 ms stalls on every hit.** Cause: without `step-events`, the host sent each hit as its own request, and the
    reply took an old capture path that waited out the gate. Fix: fold events into steps, and answer separate
    hit/contact requests from the cached frame.
14. **16–22 ms receive spikes in the host, independent of process priority.** Cause: a ~190 KB base64 image
    reply over loopback TCP; `TCP_NODELAY` and priority made no difference. Fix: the shared GPU layer.
15. **Capture readback waited 3–5 ms.** Cause: `LockRect` waits for the GPU, which D3D9 only submits at Present or
    lock. Fix: an event query with `D3DGETDATA_FLUSH` right after each replay (−0.8 ms per step), and StretchRect
    only the crop.
16. **The uncapped frame rate loaded the PC.** Cause: free-run removes vsync for menus too. Fix: cap Present with a
    high-resolution waitable timer while not serving. The frame gate already holds KOF while serving.

## Assets
None created. Nothing from the game is stored: all pixels are KOF's own, rendered live.

## Cost and time
Two days of sessions (2026-10-10 to 2026-10-11), each change verified live on the running game.

## Open questions
- The attacker-owned stun length on Kyo as defender (hold or cut KOF's reaction animation).
- KOF's own block-height field, probably in the RectType table.
- Throws and KO.
- Other characters: the drawer and hit-record approach should be generic.
- Zero-copy sharing of KOF's private target, which would need a D3D9Ex or D3D9On12 device. D3D9On12 crashed it, and
  D3D9Ex rejects managed-pool resources.
- Skipping KOF's whole render pass in the stale first iteration of each step, which would save CPU.
