---
kind: game
title: 'Portal gun prototype via dinput8 proxy DLL: player, camera and angle offsets'
game: 'DARK SOULS: REMASTERED'
games_also: []
game_version: 'Steam build 10943698; DarkSoulsRemastered.exe 50,286,344 bytes, SizeOfImage 0x319B000'
platform: windows
engine: native
route: other
tools:
- Zig 0.17.0 (zig cc, x86_64-windows-gnu)
- Ghidra 12.1.4
- Python 3 ctypes (ReadProcessMemory) and capstone
- DSR-Gadget source (reference only)
anti_cheat: none found by um scan (play offline only)
status: in-progress
agents:
- Claude Code (Sonnet 5.5)
humans: []
date: '2026-10-07'
links:
- https://github.com/JKAnderson/DSR-Gadget
- https://soulsmodding.com/
tags:
- proxy-dll
- dinput8
- memory-map
- teleport
- overlay
- rtti
---
# Portal gun prototype via dinput8 proxy DLL: player, camera and angle offsets

A hotkey-driven portal prototype for Dark Souls Remastered: two portals (blue and orange) are drawn over the
game, and walking into one moves the player to the other with the facing rotated. It runs in the real game
(offline) and works on open floor, as confirmed by the user and by the log. It fails when walls lie between the
portals (position snaps back); that is still open. This note is mostly a verified memory map for this build plus
the traps we hit.

## Setup
- Game: Steam app 570940, build id 10943698, `DarkSoulsRemastered.exe` 50,286,344 bytes (SHA-256
  `a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b`), PE `SizeOfImage` 0x319B000. This size is
  not in DSR-Gadget's version table, so its offsets and "boosts" do not apply directly.
- Windows 10, no MSVC. Built with portable Zig: `zig cc -target x86_64-windows-gnu -shared -O2 -o dinput8.dll
  proxy.c dinput8.def -lgdi32 -luser32`.
- The game folder already had a ReShade `dxgi.dll`; `dinput8.dll` was free, so the proxy uses that name.
- Play with Steam in Offline Mode. The image base is fixed at 0x140000000 (no ASLR relocation was observed).

## Route and why
A dinput8 proxy DLL (forwards `DirectInput8Create`, starts a thread) plus direct memory access. Params alone
cannot express portals, ModEngine2 supports DSR but is archived and not needed for this, and DSR-Gadget is a
separate external process (and GPL-3.0). Item and projectile work (params via Soulstruct, Smithbox or
DSMapStudio with Paramdex) is the planned next step and is not started.

## How the game works (what we had to learn)
The executable on disk is protected: there is an extra large, high-entropy `.text` section after `.idata` and the
entry point is in a stub, so static Ghidra analysis of the file gives mostly garbage. The running process holds
decrypted code. Dumping the main module's image from inside the process (a hotkey in the proxy that walks the
image pages with `VirtualQuery` and writes them to a flat file) gives a clean image that disassembles normally
and still contains RTTI. We did not strip or bypass the protection; we only read the game's own memory while it
runs, for analysis.

Addresses below are offsets from the module base (0x140000000), verified live in the Undead Asylum. Pointers
change every launch, the chains do not.

- **RTTI / vtables** (image VAs): WorldChrManImp 0x141328210, PlayerIns 0x1413251f0, ChrFollowCam 0x1412f1db8,
  PadMan 0x1412de4d0, CameraMan 0x1412edf98. Finding a singleton: scan the `.data` section (rva 0x1a25000 to
  0x1d0b000) for any pointer whose target's first qword equals the class vtable.
- **WorldChrManImp** global pointer at exe+0x1c77e50. `PlayerIns = [WorldChrMan + 0x68]` (DSR-Gadget calls this
  ChrData1; same offset). PadMan global at exe+0x1c6aea0.
- **Position, authoritative:** `PlayerIns + 0x7b8 -> +0x2e0 -> +0x120` is float x, y, z and a w of about 1.0. Y is
  up. A second chain reaches the same address: `PlayerIns + 0x18 -> +0x28 -> +0x2c0 -> +0x120`.
- **Position, copy:** `PlayerIns + 0x2c0` holds the same triple but is rewritten every frame, so writes there
  vanish in milliseconds. Many other objects also hold copies; only the physics-owned one is honoured.
- **Facing angle:** `ChrPosData = *(*(PlayerIns + 0x18) + 0x28)`; angle (radians) at `ChrPosData + 0x4`, and x, y, z
  at +0x10, +0x14, +0x18 (matches DSR-Gadget's PosAngle and PosX/Y/Z). Forward is (-sin a, cos a) in (x, z), so
  a = 0 faces +z and `a = atan2(-fx, fz)`. Verified over 83 samples covering a full circle. Writing it persists,
  but the character model only turned partway in place, so it behaves like a logical heading.
- **Camera:** global `CameraMan` pointer at exe+0x1c6e188. The world matrix is four float4 rows at +0x30 right,
  +0x40 up, +0x50 forward, +0x60 position (w = 1). At +0x70: vertical FOV in radians (0.75), aspect (2.389 for a
  3440x1440 window), near plane 0.05, far plane 3100. At +0x120 the viewport size. It is called CameraMan, so
  it is likely the active camera, but it was not tested with the bow aim camera.
- **Overlay rendering without a graphics hook:** a topmost, click-through, layered window (`WS_EX_LAYERED |
  WS_EX_TRANSPARENT | WS_EX_NOACTIVATE`, magenta colour key) positioned over the game's client area, drawing with
  GDI. World to screen: d = P - camPos, z = d.fwd, x = d.right, y = d.up, then
  screenX = W/2 + x / (z * tan(fovY/2) * W/H) * W/2, screenY = H/2 - y / (z * tan(fovY/2)) * H/2. The rings stayed
  glued to world positions, so the maths and the FOV field are right. Needs windowed or borderless.
- **Teleport:** detect the player's body point (feet + 0.9) crossing a portal plane from the front inside an
  ellipse; write the physics position to the linked portal with local x mirrored; rotate the angle by
  `yaw(nB) - yaw(-nA)`, where `yaw(x, z) = atan2(-x, z)`; keep re-writing the destination for about 0.3 s.

## Build steps
1. Back up your saves, put Steam in Offline Mode, and find the module base (fixed 0x140000000).
2. Build the proxy (forward `DirectInput8Create` from the system `dinput8.dll`, start a thread in `DllMain`),
   and copy it into the game folder. Close the game before replacing it (a loaded DLL cannot be overwritten).
3. In the thread, read the chains above with `VirtualQuery` guards and do the camera projection and teleport.
4. For analysis, add a hotkey that dumps the module image, then import it into Ghidra as a raw binary at base
   0x140000000 (x86:LE:64:default, windows cspec).
5. Undo: delete the proxy DLL from the game folder.

## Verification
- Position chain: read on two launches; the 2-unit "pop up" write was confirmed visually by the user, and a
  +/-4 unit horizontal write was confirmed visually.
- Camera: found by diffing memory reachable from the game's globals before and after a 90 degree camera turn,
  then confirmed the orthonormal basis and the position about 3 units behind the player. The overlay rings
  staying fixed while turning and walking is the oracle for the matrix and FOV.
- Teleport: the log (`teleport ... hold done: offset 0.00`) and the user confirming they were moved and rotated,
  on open floor.
- NOT verified: the bow aim camera, fall velocity and momentum, behaviour after loading a different map, the
  camera after a teleport, and anything online (never tested; play offline).

## Gotchas
1. **Symptom.** Writing the player's position works only briefly or not at all. **Cause:** the first triple found
   (PlayerIns+0x2c0) is a per-frame copy. **Fix:** write the physics-owned position at `PlayerIns+0x7b8 -> +0x2e0
   -> +0x120`. Test any candidate by writing y+2 and watching whether the player's copy follows and the character
   then falls back.
2. **Symptom.** A teleport written while the character is walking gets undone, while the same write standing still
   sticks. **Cause:** the game's own per-frame move writes back over a single mid-frame write. **Fix:** hold the
   destination and angle for about 0.3 s (re-write every tick) after the crossing.
3. **Symptom.** The game exits about one second after writing DSR-Gadget's Warp fields (ChrMapData + 0x108, 0x110
   to 0x124) and setting the warp flag. **Cause:** DSR-Gadget's offsets are for older builds; this build's size is
   not in its table, so the layout differs. **Fix:** do not use them on an unknown build. Direct position and
   angle writes are safe.
4. **Symptom.** Hotkeys do nothing in a proxy DLL. **Cause:** F12 is Steam's screenshot key and is swallowed, and
   an exact-HWND foreground check plus the `GetAsyncKeyState & 1` edge flag were unreliable. **Fix:** avoid F12,
   treat the game as focused when the foreground window belongs to the game's process, and track key edges with
   the high bit.
5. **Symptom.** Static analysis of the exe shows "Failed to disassemble" and decompiler "Unable to resolve
   constructor" everywhere. **Cause:** the code is protected on disk. **Fix:** analyse a runtime dump (see above).
6. **Symptom.** Teleporting fails or snaps back in some spots but works on open floor (hold-end position is back near
   the start). **Cause:** unconfirmed; the destination was a spot the player had stood on, so it is not simply a
   blocked target. Hypothesis: a collision-swept move stops at walls between the portals. **Fix:** not found yet.
7. **Symptom.** A blind "N units ahead" portal placement lands in walls. **Cause:** no collision query.
   **Fix:** planned: use the game's own projectile impact position and normal.
8. **Symptom.** `um` crashes printing the game name on a Windows console. **Cause:** cp932 console encoding.
   **Fix:** set `PYTHONUTF8=1`. Also `um kb search` needs PyYAML.
9. **Symptom.** A test write landed in unrelated memory. **Cause:** a scan result went stale after the player object
   was reallocated. **Fix:** re-resolve the chain from the global each time and only write to addresses that
   currently match the expected values.

## Assets
None generated. The portals are GDI-drawn rings.

## Cost and time
One long session (about a day of wall-clock with many launch cycles, each needing a DLL copy and relaunch).

## Open questions
- Why teleports snap back when walls lie between the portals, and how to disable or bypass the sweep safely (for
  example a map-collision flag, the Havok character proxy position, or the game's own warp function).
- Correct warp-field offsets for this build, if the game's warp is to be used.
- Velocity and fall speed offsets, to keep momentum through a portal.
- Whether CameraMan is also the bow aim camera.
- The item: pyromancy-style and spell-style projectiles via params, and using projectile impacts for portal
  placement; giving the item at runtime (DSR-Gadget lists an ItemGet function signature).
