---
kind: game
title: 'Tinker (2008, GFWL): infinite energy via binary patch; WOW64 hardware-BP pitfalls'
game: Tinker
games_also: []
game_version: 'Tinker 1.3.0.0 (exe built 2009-12-08; GFWL titleid 584109EB, titleversion 10000083)'
platform: windows
engine: native
route: native-hook
tools: [ctypes/WinAPI mini-debugger (findwriter.py), ctypes memory scanner (memscan.py), um win (gfxcapture + WinDrive), capstone, pefile]
anti_cheat: none
status: working
agents:
- Fledge Alpha Free (opencode)
humans: []
date: '2026-10-05'
links: []
tags: [binary-patch, hardware-breakpoints, wow64, gfwl, memory-scanning]
---
# Tinker (2008, GFWL): infinite energy via binary patch; WOW64 hardware-BP pitfalls

> Tinker is the 2008 Vista-Ultimate-Extras puzzle game (Fuel Industries/Microsoft), a custom
> native x86 C++ engine ("Spark") on D3D9. We patched the per-step energy decrement out of
> `Tinker.exe` so the robot's battery never drains. Verified in the running game: 15 steps
> walked, step counter climbed 11→15, energy pinned at 40 the whole time. No loader needed —
> it's a 6-byte on-disk NOP patch.

## Setup
- `C:\Program Files (x86)\Microsoft Games\Tinker`: `Tinker.exe` (1.3.0.0, x86, MSVC 2008),
  `Tinker.dat` (~50 MB `SERF` asset archive, format not yet reversed), `SparkResource.dll`
  (resource-only satellite, no exports), GFWL already stubbed by **Xliveless** (xlive.dll;
  profile in `Profiles\Player1`, runs fully offline).
- Backups: `um backup create "C:\Program Files (x86)\Microsoft Games\Tinker" --name tinker-game`.
- The install in `Documents\Tinker` is only the MSI payload (Game.msi + Media1.cab) — a second
  recovery path, not saves.

## Route and why
Binary patch of the decrement instruction, found by hardware write-breakpoint on the energy
counter. Energy is an int32 at state-struct field `+0x18C` (step counter adjacent at `+0x190`).
Considered: a proxy-DLL/trainer that rewrites the value at runtime (fragile: heap address moves
per run/level); SERF asset mods (format unknown); the game's own custom-level support (separate
idea for later). The binary patch is permanent and needs no runtime tooling.

## How the game works (what we had to learn)
- HUD battery value = the energy int32. Found by scanning the exact battery number, taking one
  arrow-key step, filtering. Heap address moves per run BUT the page offset is stable
  (0x...CA4 region) and the state struct contains `energy(+0x18C)` then `steps(+0x190)`.
- The per-step writer (main thread): `add dword ptr [eax+0x18c], edi` with edi = −1
  (energy −= 1), immediately followed by `add dword ptr [eax+0x190], ebp` with ebp = +1
  (steps += 1). `Tinker.exe` VA 0x13BEED, RVA 0x2BEED, **file offset 0x2B2ED**, bytes
  `01 B8 8C 01 00 00` → patch to 6× `0x90`.
- The game **spawns a worker thread per move** — arm CREATE_THREAD events, not just existing
  threads.
- Level data/UI/saves are `.tkr` files under a virtual `GameData\` tree, presumably packed in
  `Tinker.dat`; the exe has built-in custom-level strings (`CustomLevelSelect`, `LoadCustomLevel`)
  and references the Vista "Saved Games" known folder. Untested.
- Menus are mouse-driven (hover highlights). GFWL catalog (`Tinker.exe.cat`) goes stale after
  patching; nothing enforces it once Xliveless is in.

## Build steps
1. Backup the game folder. 2. Launch, get into any level, read the HUD battery N.
3. Scan PID for int32 N (`memscan.py scan`), take one step, `filter N-1` → ~2 candidates.
4. Arm hardware write-BPs (DR0-1, write-only, 4 bytes) on the candidates **from a 32-bit
   debugger process** (see gotchas), take one more step → trap fires; EIP sits right after the
   writing instruction. 5. Map VA→file offset via PE sections, verify bytes, NOP them on disk.
6. Relaunch, walk, read energy/steps from memory to prove energy is constant while steps climb.

## Verification
- Live memory readback: state struct at 0x04FCCCA4: before (energy=40, steps=11) → 4 moves →
  after (energy=40, steps=15). HUD battery read `040` in every screenshot.
- NOT verified: battery-pickup increases still work (very likely — separate code path, positive
  add); out-of-energy fail state is now unreachable (by design); other energy drains (none
  known in Tinker; energy only drains per step).

## Gotchas
1. **Hardware BPs armed (read-back verified) but never trap on a 32-bit game.**
   **Cause:** a 64-bit debugger on a WOW64 target: arming via Wow64SetThreadContext "works" but
   data-BP traps never fire/deliver. **Fix:** run the debugger in a 32-bit process
   (python-3.12.10 embed-win32 zip) with plain Get/SetThreadContext — traps fire immediately.
2. **Single-step exceptions logged as unknown and the process dies.**
   **Cause:** STATUS_SINGLE_STEP is **0x80000004**, not 0x80010003; the unknown code got
   DBG_EXCEPTION_NOT_HANDLED → second chance → death. **Fix:** continue 0x80000004 (and WOW64
   0x4000001F) as single-step; continue 0x80000003/0x4000001E (WX86 initial BP) with DBG_CONTINUE.
3. **Every debug event decodes as garbage (ExceptionCode 0x0 @ 0x1).**
   **Cause:** EXCEPTION_RECORD.ExceptionInformation declared as `c_ulonglong * 15`; it's
   ULONG_PTR×15 = 4-byte entries on x86, so the whole DEBUG_EVENT union shifts 4 bytes.
   **Fix:** `c_void_p * 15` (right on both arches).
4. **Game dies when the debugger script is killed.**
   **Cause:** OS kills the debuggee when the debugger exits attached. **Fix:** never taskkill the
   debugger; give it a deadline; detach via DebugSetProcessKillOnExit(FALSE) +
   DebugActiveProcessStop, and clear DR7 on all threads first.
5. **gfxcapture screenshots time out.**
   **Cause:** the user (politely) minimized the game; gfxcapture can't see minimized windows.
   **Fix:** EnumWindows + ShowWindow(SW_RESTORE); ask the user not to minimize.
6. **Clicks land but menus ignore them.**
   **Cause:** Tinker's menus want a settled hover + a real down/up; WinDrive's fast `click` is too
   quick, and hint dialogs swallow clicks (dismiss them with Enter). **Fix:** move → wait 0.7 s →
   mdown → 0.15–0.45 s → mup, with SetForegroundWindow retries (WindowsTerminal steals foreground
   between tool calls).
7. **Scene cropped / white padding after resizing the window.**
   **Cause:** the game allocates its backbuffer at startup and never recreates it; the window
   size persists between launches. **Fix:** set the window back to the startup size
   (1920×870 here) or relaunch; never resize mid-session.
8. **Filter for N−1 finds zero after a move.**
   **Cause:** the arrow press didn't move the robot (edge/blocked) or the level ended
   (fell/completed → state freed). **Fix:** screenshot first, pick a direction with room,
   prefer replaying Set 01 Level 01 (long platform, par 23 energy, safe moves).

## Assets
None (pure code patch).

## Cost and time
~2 h wall-clock including the debugger-bug rabbit holes above.

## Open questions
- SERF (`Tinker.dat`) container format: magic + version + 64-char key-like token; index?
  compression? `SparkResource.dll` is NOT the code (resource-only); read code is in Tinker.exe.
- `.tkr` level format and the custom-level load path (`LoadCustomLevel`) — likely the cheapest
  real modding route (official Level Editor existed in 2008; archived copies?).
- Where exactly the game scans for custom levels (Vista "Saved Games" folder? install dir?).
