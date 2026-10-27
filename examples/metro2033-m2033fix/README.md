# Metro 2033 (2010) crash fix: m2033fix

A 26 KB `dinput8.dll` for the **original Metro 2033** (Steam 43110, `metro2033.exe` 1.0.0.1). It fixes a
vanilla crash that hits about **25–35 s after start**. The crash shows up as an access violation at
`0x84F72A` (sometimes `0x84F53C`), followed by "Previous launch was unsuccessful. Would you like to start in
safe mode?" on the next start.

Version 0.4.1 (fix groups in `m2033fix.ini`: core / compat / perf / research) also:
- brings over what the DRM-free GOG release fixes in the same exe build: 1024 display modes, working V-Sync
  under DX11, mouse and keyboard on the "press any key" screen with a gamepad present, no driver popups;
- fixes a crash on an empty display-mode list and on a `user.cfg` line of 1024+ characters;
- enters real fullscreen once the window is in front when the game started without focus (Steam "Play");
- replaces the vanilla frame limiter with an exact one driven by `target_fps`;
- writes the reason of an engine `!!! STOP` to its log before the game goes down.

- **The game is untouched.** The exe, its SteamStub DRM and the archives are not modified. All changes
  live in the game's memory. They are made after SteamStub has decrypted the code itself, and only when the
  exact expected bytes are found.
- **No loader is needed.** Windows loads `dinput8.dll` from the game folder. The DLL imports only
  `kernel32.dll` (user32 is looked up at run time) and uses no CRT. `DllMain` only records the folder and starts
  one watcher thread for P12.
- **Easy to roll back.** Each fix is a switch in `m2033fix.ini`, and deleting the DLL gives back the
  vanilla game.

Tested on: Windows 11, Steam build of `metro2033.exe` 1.0.0.1 (PE timestamp `0x4C7775B7`), DX11,
fullscreen 1920×1080, Russian text, on an RTX 3050 Ti laptop (hybrid with an AMD iGPU) and on a desktop
(Ryzen 7 7800X3D, RTX 4060); 0.4 on the desktop (see Verification). Field note:
`knowledge/games/metro-2033/original-metro-2033-steamstub-exe-vfi-upk-archives-quicklz-a.md`.

## The bug (P1)
- About 25 s after start, the main thread switches the text language (`FUN_0085B090`). It does three
  things in order:
  1. sets the global charmap pointer `DAT_00A14F88` to NULL;
  2. frees the old charmap (`0x40C060`, which also zeroes its size);
  3. stores the new one.
- Meanwhile a worker thread lays out UI text. Its chain is `0x7A40C3 → FUN_00846E10 → FUN_00846010 →
  FUN_008456E0 → FUN_0084F6E0`, and `FUN_0084F6E0` converts UTF-16 to the game's charmap encoding.
- That conversion loads the global once, into `edi` at `0x84F6F5`, and reads the table through it. If the
  load lands between the NULL store and the new store, the worker dereferences NULL+0xC at `0x84F72A` and
  the game dies. The 46 callers of `0x84F510` load the global into `edi` the same way, which gives the
  second crash site, a write to 0 at `0x84F53C`. A worker that loaded the old pointer just before the
  switch is left holding freed memory. The crash was confirmed by call-validated stack scans of 5
  minidumps.
- The switch happens on every start, whatever the Steam language. How often the race hits depends on the
  machine: vanilla crashed in **5 of 10** starts on the test laptop and in **4 of 41** on a desktop.

## What it changes (complete list)
| Id | Address | Bytes | Effect | Default |
|---|---|---|---|---|
| P1 | `0x85B0A8` | `C7 05 88 4F A1 00 00 00 00 00 E8 A9 0F BB FF` → 15× `90` | The NULL store and the free disappear. The new charmap is installed by the existing single aligned store at `0x85B0C2`, so the global is never NULL, and the old table stays valid for a thread still reading it. It leaks one table of a few KB per language switch (one per start). | on |
| P4 | `0x7A1F1A`, `0x7A1F3F`, `0x7A1F4F`, `0x7A1F77` | `B8 40 38 00 00` → `B8 80 70 00 00`; `8D 95 C0 C7 FF FF` → `8D 95 80 8F FF FF`; `C7 45 FC 00 02 00 00` → `C7 45 FC 00 04 00 00`; `8D 8D C0 C7 FF FF` → `8D 8D 80 8F FF FF` | `FUN_007A1F17` reads `IDXGIOutput::GetDisplayModeList` into a stack buffer of 512 modes. This raises the stack frame, both buffer references and the capacity to 1024, byte for byte as the GOG build does. All four parts are applied, or none. With 512 modes or fewer nothing changes. | on |
| P5 | `0x7A1733`, `0x7A1D71` | `53 53 57 FF D1` and `53 55 FF 50 20` → `E9 rel32` to a stub in this DLL | Both per-frame `IDXGISwapChain::Present` calls pass `SyncInterval = 0` whatever `r_vsync` says. The stubs push `r_vsync ? 1 : 0` (bit `0x10` of `0x9F2820`), call `Present`, and jump back. Each 5-byte jump is written with one `cmpxchg8b`. The `r_vsync` registration code is checked first. With `r_vsync off` the frames are the same as vanilla. | on |
| P8 | `0x8536FB` | `A1 08 BE A1 00` → `E9 rel32` | The vanilla limiter sleeps whole milliseconds and does nothing when the GPU is the bottleneck. The stub waits until the previous frame's QPC stamp plus 1/`target_fps` (high-resolution timer, spin for the last `fps_limiter_spin_us`). Also sets the save flag of `target_fps` (byte `0xA1BE03` `00` → `01`, formerly P9) unless `target_fps_save = 0`. | on |
| P10 | `0x7A1EE1`, `0x85B523` | `8B 07 8D 4D F4` → `E9 rel32`; `E8 68 FB FF FF` → `E8 rel32` | `CreateSwapChain` asks for fullscreen, gets `DXGI_STATUS_OCCLUDED` without focus and leaves a window; the game never retries. The first stub notes the result; the second runs once per frame on the main thread and, when the game window is in front, calls `SetFullscreenState(TRUE)` under the renderer lock `0xA2E5B0` (max 5 tries, 500 ms apart). | on |
| P11 | `0x7B3740` | `55 8B EC 83 E4` → `E9 rel32` | The function picks the aspect ratio from the largest display mode and reads the last list entry without checking that the list has one. The stub returns with the desktop aspect on an empty list and otherwise runs the moved prologue. | on |
| P12 | `0x422702` | `8B F8 57 56 8D` → `E9 rel32` | `config_load` copies each `user.cfg` line with `strncpy_s(buf[1024], len)`; 1024+ characters end the process. The stub clamps the length to 1023. Applied by the watcher thread right after SteamStub decrypts (the first `user.cfg` read comes before `DirectInput8Create`). | on |
| P13 | `0x8543E2` | `74 0B` → `EB 0B` | The "press any key" screen after a load takes only gamepad codes when a gamepad (Steam Input too) is present. Same byte as GOG 1.01 v5 (GOG also drops the 1 s guard; kept here). **Not verified in game.** | on |
| P14 | `0x938EA5`, `0x938F9E` | `E8 rel32` → `E8 rel32` | The "unsupported graphics card", "driver needs to be upgraded" and "cannot extract driver info" warnings call a MessageBox that can hide behind the fullscreen window. The stub writes the same game-log line and a line in `m2033fix.log` instead. Real DX error boxes are untouched. | on |
| P17 | `0x9316BB` | `55 8B EC B8 04` → `E9 rel32` | The engine's `!!! STOP` handler: the stub writes reason, file, function and line to `m2033fix.log`, then runs the moved instructions; the game crashes as before. | on |

Nothing else is hooked. There are no IAT hooks and no Steam or input hooks; every detour above sits in the game's
own code and checks its bytes first. 5-byte jumps inside one aligned qword are written with one `cmpxchg8b`; P14's
two calls run only on the main thread, which is inside `DirectInput8Create` while they are written. `DirectInput8Create`, the game's only import
from dinput8, is forwarded unchanged to the system DLL.

**Dropped in 0.2:**
- **P2** kept the charmap alive at shutdown. No exit crash was ever traced to it.
- **P3** set the save flag of the `mouse_inertion` cvar. It was a convenience, not a fix, and the option
  isn't in the original config at all.

**Deliberately not ported from GOG:**
- GOG's 120 FPS busy-wait limiter: P8 does the same job driven by `target_fps`, mostly sleeping.
- GOG's removal of the 1 s guard on the "press any key" screen.

## How it works
1. **`DllMain`** only records the DLL folder and starts the P12 watcher thread, which polls 8 bytes every 10 ms
   and writes one jump once SteamStub has decrypted them (~0.6 s; the first `user.cfg` read is at ~1.95 s). At
   that point the loader lock is held and `.text` is still encrypted. MetroDeveloper 1.2.2, a `dinput8.dll`
   proxy too, hangs this build forever by doing its work here.
2. **The game's first `DirectInput8Create` call** (main thread, about 2 s after start) does the rest. This
   is long before the language switch, the display-mode query (about 4 s) and the first `Present`.
   1. loads `GetSystemDirectoryW()\dinput8.dll` by full path;
   2. checks the exe: base `0x400000`, SizeOfImage `0xB64000`, TimeDateStamp `0x4C7775B7`;
   3. compares the exact bytes at each site;
   4. applies each enabled patch independently with VirtualProtect, write and FlushInstructionCache;
   5. writes `m2033fix.log`;
   6. forwards the call.
3. **On any mismatch** the patch is skipped with `SKIP … found …` in the log, and the game runs vanilla.
4. **Rebasing:** P5's stubs return through variables that the DLL's relocations fix up. The test system
   loaded the DLL away from its preferred base, and the return path worked.

## Build
You need [Zig](https://ziglang.org/) (0.13+; 0.17.0 was used) on PATH.
```
powershell -ExecutionPolicy Bypass -File build.ps1      # -> build\dinput8.dll
```
- The build compiles with the Windows headers, then links with `-nostdlib`.
- `src/dinput8.def` exports the undecorated `DirectInput8Create`.
- The result imports only KERNEL32.
- The P5 stubs are a top-level `__asm__` block in `src/m2033fix.c`.

## Install
1. Close the game, then run `powershell -ExecutionPolicy Bypass -File install.ps1`.
   - It finds the Steam install, or you can pass `-Game "<install folder>"`.
   - If another `dinput8.dll` is there (MetroDeveloper), it stops. With `-Replace` it renames that one to
     `dinput8.dll.off`.
   - It copies `build\dinput8.dll`, plus `m2033fix.ini.txt` as `m2033fix.ini` (only if there is none
     yet).
   - To install by hand, copy those two files the same way.
2. Start the game. `m2033fix.log` next to the exe should start with `m2033fix 0.4.1` and show `OK` for each
   enabled patch (`P12 … OK at … ms` with a time below ~1900).

**Upgrading from 0.2/0.3:** `install.ps1` keeps your `m2033fix.ini`. Its `[fix]` keys still work; the 0.4
fixes (P10–P14, P17) stay off until you add their keys, e.g. by taking the new `m2033fix.ini.txt`.

**Upgrading from 0.1:**
- `install.ps1` replaces the DLL but keeps your `m2033fix.ini`.
- 0.2 ignores the old keys (`exit_charmap_free`, `save_mouse_inertion`).
- The new keys default to on when they are missing.
- A `mouse_inertion` line that 0.1 got saved into `user.cfg` is dropped by the game at the next settings
  save.

## Uninstall
`powershell -ExecutionPolicy Bypass -File uninstall.ps1 -Game "<install folder>"`, or delete `dinput8.dll`
and `m2033fix.ini`. A `dinput8.dll.off` is renamed back.

## Settings (`m2033fix.ini`)
| Key | Default | Meaning |
|---|---|---|
| `[core] lang_switch_race` | `1` | P1 |
| `[core] empty_mode_list_guard` | `1` (template), `0` if missing | P11 |
| `[core] config_line_clamp` | `1` (template), `0` if missing | P12 |
| `[compat] display_modes_1024` | `1` | P4 |
| `[compat] vsync_follow_cvar` | `1` | P5. V-Sync itself is the game's `r_vsync on`/`off` in `user.cfg` (the original menu has no switch). |
| `[compat] fullscreen_retry` | `1` (template), `0` if missing | P10 |
| `[compat] press_key_any_input` | `1` (template), `0` if missing | P13, not verified in game |
| `[compat] no_driver_popup` | `1` (template), `0` if missing | P14 |
| `[perf] fps_limiter_deadline` | `1` | P8 (and saving `target_fps`; the old key `target_fps_save = 0` turns the saving off) |
| `[perf] fps_limiter_spin_us` | `600` | P8 spin before the deadline, 100..3000 µs |
| `[research] log_stop` | `1` (template), `0` if missing | P17 |
| `[log] enabled` | `1` | `m2033fix.log`: startup, then one line per P10/P11/P14/P17 event |

Old `[fix] key = …` lines are read when the section has no such key.

The game reads `user.cfg` from **Steam Cloud first** (`<Steam>\userdata\<id>\43110\remote\user.cfg`), so
edit that copy. FOV is `sick_fov` (saved; same value as `r_base_fov`, default 45).

## Verification
Same PC and settings, Steam launches of 130 s each, closed by PID:

| Build | Runs | Crashes | Notes |
|---|---|---|---|
| Without the DLL | 10 | **5/10** at 26–28 s | 4× `0x84F72A` (read `0xC`), 1× `0x84F53C` (write `0x0`); same worker chain in every dump |
| 0.1 (P1 + P3) | 10 | **0/10** | No dumps; the charmap pointer went old → new directly in every run |
| 0.2 test build, `r_vsync on` | 10 | **0/10** | P5 A/B OK in every log |
| 0.2, `r_vsync off` | 10 | **0/10** | No dumps; P1, P4 ×4, P5 A/B OK in every log |

Without the DLL vs 0.1: Fisher exact, one-sided, p = 0.016.

**Second PC** (desktop: Ryzen 7 7800X3D, RTX 4060 with an AMD iGPU, 32 GB, Windows 11, same Steam build 21327
and the same Steam Cloud `user.cfg`):

| Build | Runs | Crashes | Notes |
|---|---|---|---|
| Without the DLL, smoke (2026-10-22) | 2 | **1/2** at 26 s | `0x84F72A` |
| 0.1 (P1 + P3), smoke (2026-10-22) | 2 | **0/2** | P1 OK, P3 OK in the log |
| Without the DLL (2026-10-23) | 9 | **0/9** | Run 8 exited by itself at 42 s with code 0, no dump; a 10th run was stopped |
| Without the DLL (2026-10-23) | 30 | **3/30** at 26–27 s | 2× `0x84F72A` (read `0xC`), 1× `0x84F53C` (write `0x0`); worker chains as on the laptop |
| 0.2, P1 only (`display_modes_1024 = 0`, `vsync_follow_cvar = 0`) (2026-10-23) | 30 | **0/30** | P1 OK in every log; no dumps, no WER events; the charmap pointer went old → new directly in every run |

- Without the DLL the desktop crashed in 4 of 41 runs, about 10% (95% CI 3–23%), against 5 of 10 on the
  laptop. The render settings were identical across these runs, so the rate depends on the machine, not on
  the config.
- In all three dumps the global already held the new table when the dump was written: the worker had loaded
  it inside the window that P1 removes.
- P1 only, 0/30 against 4/41 without the DLL: Fisher exact, one-sided, p = 0.10. At this crash rate 30 runs
  are not enough on their own (about 60 clean runs would give p < 0.05); the desktop result agrees with the
  laptop's p = 0.016 and with the dumps, but does not prove the fix by itself.

**P5:** a Frida hook on `dxgi.dll`'s `Present` (not on game code) read the SyncInterval of the frames.
- With `r_vsync off` it saw `SyncInterval = 0`; with `r_vsync on`, 1 from the first frame.
- Setting the `r_vsync` bit in a running game switched it to 1 within the same session.
- Vanilla passes 0 in all of these cases, and PresentMon agrees.

**P4:** all four writes apply (log `OK`) and the game starts and runs normally. The laptop has only 62
display modes. On the desktop's 3840×2160 @ 240 Hz monitor DXGI returns 553 modes: vanilla keeps 512 and loses
every 3840×2160 entry (its largest is 2560×1440), with P4 the call returns all 553 (`hr = 0`) and 3840×2160
reaches the menu list.

**Desktop, 0.3-pre (P1 + P4 + P5 + P8 + P9), 1920×1080, `r_vsync on`, `target_fps 60`:**

| Test | Result |
|---|---|
| Soak 10 × 130 s | 10/10 alive, every patch `OK` in every log |
| Race amplifiers: game on 2 cores (affinity `0x3`), then 4 cores + 12 busy processes | 20/20 alive, charmap pointer set once, never NULL |
| Play: 2 h new game, 15 levels | no crash or hang; 59.4 FPS, p99 18.2 ms, SyncInterval 1, Independent Flip |
| 49 save loads (Anomaly, Front Line); Advanced PhysX on the GPU, 32 min | clean |
| 8 resolution changes up to 4K, Alt+Tab, monitor off, PC sleep | clean |
| Play with 5 options-menu language switches (12 + 40 min) | 0 exceptions (Frida first-chance log), exit code 0 |
| Application Verifier, light PageHeap + Handles: 5 starts + 26 min play | 0 verifier entries |

- **P8:** vanilla did not cap at all when GPU-bound (129 FPS average at `target_fps 120`). P8 holds 120.0 or 60.0 FPS
  (median 8.33 / 16.67 ms) with input-to-photon latency like uncapped (7.9 ms at 120, 8.9 ms at 60), against 11.0 /
  12.1 ms for the NVIDIA driver cap. With the save flag (formerly P9) `target_fps` survives a restart.

**Desktop, this version (the tests ran on a pre-release build with the same patches), template ini, same
config.** The final build's control start (130 s) logged every patch `OK`.

| Test | Result |
|---|---|
| First start via Steam, no input | every patch `OK`; P12 applied at 719 ms (first `user.cfg` read ~1950 ms); `P10: … got DXGI_STATUS_OCCLUDED` |
| Click into the window | `P10: try 1 SetFullscreenState(TRUE) hr 0x00000000, now fullscreen`; menu exit, code 0 |
| Soak 10 × 130 s; again on 2 cores (affinity `0x3`) | 20/20 alive, every patch `OK` in every log, charmap pointer never NULL |
| Play, 36.7 min: chapter select, 2 level transitions, 15 saves, 7 loads | no crash, hang or STOP; exit code 0; 59.5 FPS, p99 17.9 ms, Independent Flip after the click |
| The six new keys set to `0` | those patches log `disabled in ini`, the rest `OK`; 130 s alive |
| Application Verifier, light PageHeap + Handles, 5 × 130 s | 5/5 alive, 0 verifier entries |

In the play session P17 logged `SKIP, bytes differ`: a Frida logger had hooked the same address first, and the byte
check left it alone.

**Not tested:**
- P13 with a gamepad (no gamepad on the test machines);
- P11, P12, P14 and P17 on the failures they handle (an empty mode list, a 1024+ character line, a driver warning
  and an engine STOP did not occur); they are verified by their log lines and by the game running normally;
- a long 4K session (the largest free address block fell from 158 to 118 MB in 30 minutes; no crash);
- other builds (Redux, retail).

The GOG build is not supported. Its exe has no SteamStub section (SizeOfImage `0xB0C000`), so the identity
check fails and it stays vanilla. It already ships its own equivalents of P4, P5, P13 and P14, and its own
frame limiter.

## Known limits
- Only `metro2033.exe` 1.0.0.1 (Steam) is supported; anything else stays vanilla.
- It can't be used together with MetroDeveloper, since both are `dinput8.dll`. MetroDeveloper 1.2.2 hung
  this build at startup anyway.
- P1 leaks one charmap object per language switch.
- With P5 and `r_vsync on`, the frame rate is capped at the display's refresh rate.

## Credits
- [tsnest/MetroTools](https://github.com/tsnest/MetroTools): reference for the VFI/UPK archive format used
  during the investigation.
- [tsnest/MetroDeveloper](https://github.com/tsnest/MetroDeveloper): the community engine mod for the
  series. It uses the same `dinput8.dll` load path, and its settings documented the dev console and
  config cvars.
- The GOG release of the same exe build (the author's own GOG copy, 1.01 GOG v5) was the reference for P4, P5,
  P13 and P14.
- Ghidra, Frida, capstone, minidump (Python), PresentMon, Zig.
- **AI disclosure:** the investigation, code and tests were done by Claude Code (Opus 5.5) with and for
  wh1tem0nst3r. wh1tem0nst3r reviewed each design before the DLL was built, chose P5's stub variant and
  ran the in-game exits.
