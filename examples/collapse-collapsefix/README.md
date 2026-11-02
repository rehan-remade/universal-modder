# collapsefix 1.0.0: a fix for Collapse (2008)

Fixes for **Collapse** (Creoteam, 2008; Steam 289620) on modern Windows. There are two parts:

| Part | What it fixes | State |
|---|---|---|
| `laa_patch.exe` (or `patch/laa_patch.py`): a one-bit **Large Address Aware** patch of `collapse.exe` | the crash `0xc0000005 in KERNELBASE.dll` on level loads and checkpoint reloads | tested |
| `collapsefix`: a **`dinput8.dll` proxy** with an ini file | Alt+Tab leak and "Cannot initialize video", unsupported display modes and refresh rates, blurry scaling, the coarse game timer, narrow FOV on wide screens, a small interface on large screens, key names following the keyboard layout, silent save failures, the game's memory leak, a navigation freeze, a mouse crash during scene loads | tested; the whole campaign was played through on LAA + collapsefix |

Changes per version: `CHANGELOG.md`. License: MIT, the license of the
[universal-modder](https://github.com/rehan-remade/universal-modder) repository (`LICENSE` in the release zip).

You need both. The DLL cannot replace LAA: the engine reserves its address space before any DLL of ours
can run.

## The crash and why LAA fixes it
- At start, before `WinMain`, the engine's `init_heap` reserves every free address range below 0x70000000
  for its own heap. Everything else has to fit into what is left: the D3D9 driver, DLLs, and the level
  packages.
- Level packages are memory-mapped **whole**. `data\laboratory.t000` alone is 114 MB and needs one
  contiguous free hole of that size each time the level loads or a checkpoint reloads.
- Each load and reload fragments the space that is left. When no hole is big enough, the engine logs
  `out of virtual memory: map size …` in `collapse.log` and raises 0xC0000005 itself (inside KERNELBASE).
- The exe is not Large Address Aware, so on 64-bit Windows it gets only 2 GB of addresses. With the LAA bit
  it gets 4 GB. The engine's reservation stops at 0x70000000, so the whole extra 2 GB stays free for the
  driver and the mappings.

Measured on the same profile and route:

| | Original exe | With LAA |
|---|---|---|
| Session | crash after 37 min, on a checkpoint reload in `laboratory` | 25 min, 4 `laboratory` loads including checkpoint reloads, clean exit |
| Largest free address block | 415 → 102 MB (the package needs 114 MB) | 2045 MB the whole time |
| `out of virtual memory` | yes | no |

collapsefix (`release_batches`) stops the leak that made every reload fragment the space further. Without LAA but with the DLL,
nine `laboratory` loads in a row held the largest free block at 134 MB, only 20 MB above the 114 MB package, on
one PC and one driver. That is too thin to rely on: keep LAA.

A different line, `out of virtual memory: alloc size …`, means Windows ran out of commit (a small or
disabled page file), not addresses. LAA does not help there: set the page file to "System managed size".

## The Alt+Tab leak and why the DLL uses a borderless window
- In exclusive fullscreen every Alt+Tab loses the D3D9 device. The engine does not release its old
  device: it creates a new one, and while the game is in the background it retries every 1–4 seconds.
- Each new device costs about 80–90 MB. After a few Alt+Tabs (or one long one) the address space is gone,
  and the game stops with "Cannot initialize video" (`8876086a`). Measured: 27 lost devices, private memory
  1.1 → 3.1 GB, then the dialog.
- `borderless=1` (the default) gives the game a windowed device in a borderless window over the whole
  monitor. A windowed device is never lost: in the same test there was one display init per session and
  private memory stayed at 1084 MB.
- With `borderless=0` (the game's own exclusive fullscreen) the DLL stops the background retry loop. Since 0.5.6
  the old device is also released on each Alt+Tab: what kept it alive were the geometry buffers the game forgot
  (`release_batches`). Over 84 Alt+Tabs in three runs every old device was destroyed, and process memory and
  the game's video memory stayed flat. So `borderless=0` is a fair choice now, for example for a lower resolution
  or the lowest input lag. Borderless stays the default: its Alt+Tab is instant, and screenshots and overlays
  always work.

## Install
Needs the Steam build of the game (`collapse.exe` 2,392,108 bytes, SHA-256 `3003600f…bded283`; the Russian and
English Steam depots share this exe).

1. Close the game. Back up `Documents\Creoteam Collapse\saveGame\`.
2. Unzip `dinput8.dll`, `collapsefix.ini` and `laa_patch.exe` into the game folder, next to `collapse.exe`
   (Steam → Collapse → Properties → Installed Files → Browse).
3. **LAA.** Double-click `laa_patch.exe` in the game folder (or drop `collapse.exe` onto it). It:
   - checks the exe hash and refuses any other file;
   - copies the original to `collapse.exe.bak` (an existing backup is never overwritten);
   - sets bit 0x20 (`IMAGE_FILE_LARGE_ADDRESS_AWARE`) in the PE header. Nothing else changes.

   From a command prompt, `laa_patch.exe [path\collapse.exe] --dry-run` only reports what it would do. Running
   it twice does nothing the second time. `patch/laa_patch.py` in the source does the same with Python 3.8+.
4. Start the game. `collapsefix.log` appears next to the exe and lists every fix as `OK` or `SKIP`.

After **Verify integrity of game files** or a Steam update, run `laa_patch.exe` again: Steam puts the
original exe back. `dinput8.dll` is not a game file, so Steam leaves it alone.

### Building from source
The DLL is plain C, 32-bit, with kernel32 as the only import and no C runtime; `laa_patch.exe` is a small C
console program. With [zig](https://ziglang.org/) on PATH:
```
powershell -ExecutionPolicy Bypass -File patch/build.ps1 -Out build
powershell -ExecutionPolicy Bypass -File patch/package.ps1 -Build build -Out release
```
`build\dinput8.dll` and `build\laa_patch.exe` are the results; `package.ps1` makes the release zip. The DLL
forwards `DirectInput8Create` to the system `dinput8.dll`, so the game's input works as before.

The DLL checks the exe's PE timestamp (0x48F36777). On any other exe it stays a plain proxy and changes
nothing. Patch sites are found through the import table, the D3D9 and DirectInput vtables, and, for `fov`,
`ui_scale`, `nav_guard` and `release_batches`, byte patterns that must match exactly once (otherwise the log says
`SKIP`), not through fixed addresses. Those change instructions in memory; the exe on disk stays as it is.

## Settings (`collapsefix.ini`)
1 = on, 0 = off.

| Key | Default | What it does |
|---|---|---|
| `borderless` | 1 | Fullscreen becomes a borderless window over the monitor (see above). Alt+Tab is instant. |
| `dpi_aware` | 1 | Tells Windows the game handles display scaling, so at 125 % or 150 % the window is sharp and the right size. |
| `alt_tab` | 1 | Exclusive fullscreen only: no background re-init loop while the game is not in front. |
| `display_mode` | 1 | Exclusive fullscreen only: a `Resolution` the monitor does not support falls back to the desktop mode, instead of an endless `CreateDevice returned 8876086c` retry. |
| `refresh` | 0 | Exclusive fullscreen refresh rate: 0 = same as the desktop, -1 = the game's own choice, or a number in Hz. |
| `vsync` | 0 | V-Sync. The game never enables it on its own. |
| `timer` | 1 | The game measures time with `GetTickCount` (15.6 ms steps; the menu judders at 31/47 ms frames). This gives it 1 ms steps. |
| `save_log` | 1 | Logs every save file the game fails to create (the game itself shows "game saved" anyway). |
| `fov` | auto | Field of view. `auto` keeps the 4:3 vertical view and adds width (90° at 16:9). `0` = the game's own, including a `FOV:` line in `setup.ini`. A number = horizontal degrees, 40–150. Engine cutscenes widen by the same factor; pre-rendered videos do not change. |
| `ui_scale` | auto | Size of the interface: frames, icons, crosshair and text grow together. `auto` fits the resolution: 125 % at 1080p, 167 % at 1440p, 250 % at 4K. `100` = the game's own, or a percent, 100–400. Letters get softer as they grow. The main menu keeps its size: it already follows the screen. |
| `english_keys` | 1 | Key names in hints stay English (`Press E`) whatever the keyboard layout at launch. Bindings do not change. |
| `pad_camera_deadzone` | 0 | Gamepad, right stick: dead zone in percent, 0..90. 0 = the game's own 13 %. Try 30 if the camera drifts on a worn stick. Tested with a simulated pad only. |
| `input` | 1 | Logs mouse and keyboard errors from DirectInput. Changes nothing in the game. |
| `nav_guard` | 1 | Stops an endless loop in the game's navigation mesh code, which freezes the game with the mouse still moving. Tested by forcing the loop, not yet met in normal play. |
| `release_batches` | 1 | Releases the level geometry buffers the game forgets on every level load and reload. Without it memory grows until the game runs out of address space after a few hours. |
| `mouse_keeper` | 1 | Keeps one extra mouse device open. The game closes and reopens its mouse on every scene load, and when the last one closes, Windows' `dinput8.dll` frees a table that its own mouse thread may still be reading: a rare crash inside `dinput8.dll`. Nothing reads from the extra device. |

`[log] enabled=0` turns the log off. `[log] d3d_counts=1` writes the count of live D3D resources every 30 s, for testing.

## Uninstall
- Delete `dinput8.dll`, `collapsefix.ini` and `collapsefix.log` from the game folder.
- `laa_patch.exe --restore` (from a command prompt in the game folder) puts the original exe back, or use
  Steam → Collapse → Properties → Installed Files → **Verify integrity of game files**. Then delete
  `laa_patch.exe` and `collapse.exe.bak`.

## Troubleshooting
| Symptom | Cause | What to do |
|---|---|---|
| "Load" is grey, no saves after death, `Documents\Creoteam Collapse` is missing or empty | **Controlled Folder Access** (Windows Security → Ransomware protection) blocks the game from Documents. The game then writes into a path that does not exist and says nothing. | Allow `collapse.exe` under "Allow an app through Controlled folder access". collapsefix detects this at start and shows a message. |
| Hero under the floor or falling through the level after loading a checkpoint, then a crash | a save with a bad game state (reported in Mark's Castle, checkpoints 3–4). A half-written save is not the cause: the game skips it and loads the previous checkpoint. | Delete the newest `NN_level_K.jpg` in `saveGame\profile.<name>\` (back it up first). |
| `STOP: hardware acceleration not available` on RTX 40 / 50 series | not resolved yet. Starts fine on an RTX 3050 Ti. | Use DXVK (`d3d9.dll` from a DXVK release, 32-bit) next to the exe. |
| `out of virtual memory: alloc size` | page file too small or off | Page file: "System managed size". |
| `d3dx9_31.dll` not found | old DirectX runtime missing | Install the DirectX End-User Runtime (June 2010). |
| Monitor says "out of range", sound plays | exclusive mode at a refresh rate the panel cannot show | `refresh=0` (default) or `borderless=1`. |
| QTE arrows appear, but nothing happens | the arrows on screen mean W/A/S/D | Press W/A/S/D, not the arrow keys. |
| `FOV:` line disappears from `setup.ini` | the game rewrites the file without it | Use `fov` in `collapsefix.ini` instead. |
| Stutter on a laptop on battery | the laptop lowered the refresh rate (seen: 144 → 60 Hz) and probably the GPU's power; plugging in stopped it (one play test, not measured) | Play plugged in. |
| Start fails with overlays | Steam overlay, RTSS / MSI Afterburner and compatibility mode load DLLs into the range the engine wants for itself (the engine warns "may cause memory allocation problems") | Turn them off for the game. Do not use compatibility mode. |

`setup.ini`, `collapse.log` and the saves live in `Documents\Creoteam Collapse\`.

## Known issues and plans
| Problem | State |
|---|---|
| Crash on level loads and checkpoint reloads | **fixed** (LAA) |
| Alt+Tab leak, "Cannot initialize video" mid-game | **fixed** with `borderless=1`. Since 0.5.6 exclusive fullscreen (`borderless=0`) and a change of the desktop's refresh rate (a laptop switching power) no longer leak a device either: tested with 84 Alt+Tabs and two refresh changes, process and video memory flat |
| Unsupported `Resolution` or refresh rate | **fixed** (`display_mode`, `refresh`) |
| Blurry window at display scaling above 100 % | **fixed** (`dpi_aware`) |
| Saves silently not written | **detected**; the fix is the Controlled Folder Access exception |
| Stutter and judder | **fixed** (`timer=1`; A/B play test: the stock timer judders visibly, the fix removes it) |
| QTE does not work (Sentinel, Wormboss) | **works**: Sentinel in every mode tested, uncapped FPS included; through the whole campaign (many Wormboss fights and several unique bosses) every QTE worked. Press **W/A/S/D** when the "Action!" icon lights up; the on-screen arrows mean those keys, not the arrow keys. The Anchor boss works differently: its QTE is a mouse click, and it worked too. The Sentinel fight felt harder with `timer=0 vsync=0` (first impression, not counted) |
| V-Sync | **works** (`vsync=1`, tested in borderless at 144 Hz) |
| RTX 40 / 50 start failure | open, waits for a test on such a GPU; DXVK works around it |
| Freeze with the mouse still moving, seen in Mark's Castle | **guarded** (`nav_guard=1`), tested by forcing the loop |
| Memory grows until the game runs out of address space after some hours, faster with many reloads | **fixed** (`release_batches=1`): the game did not free its level geometry buffers between loads. In an 82-minute run to the end of the campaign with 44 loads memory stayed at about 1.1 GB, where it used to pass 2.2 GB within an hour. Not yet tested over several hours |
| Crash in the system `dinput8.dll` during a level load | **fixed** (`mouse_keeper=1`). Seen once in 3 hours; the cause was measured directly: without the fix the shared mouse table is freed several times a minute, with it never |
| Mouse not working (cursor stays, camera does not turn) | open, not reproduced here; `input=1` logs which DirectInput call fails, so please attach `collapsefix.log` to a report |
| FOV, Hor+ on widescreen | **fixed** (`fov=auto`; compared in play: wider view, more of the hero in frame, no distortion) |
| Interface too small on large screens | **fixed** (`ui_scale=auto`; tested in play at 1080p on NVIDIA, one frame on AMD; 1440p and 4K not tried) |
| Text still soft or small: `rr` in "barricades" merges, subtitle capitals are about 16 px at 1080p | open: the font images are small. New fonts and HUD art are planned as a separate stage |
| Key hints show Cyrillic letters (`Press у`) on a Cyrillic layout | **fixed** (`english_keys=1`, tested on a Ukrainian layout). Named keys such as Space are not changed |
| Two bodies stay solid black after a cutscene in the first level, swords of other bodies stay | open, cosmetic. Also happens without collapsefix and on both NVIDIA and AMD, so it looks like a bug in the game |
| No subtitles during phone calls: Russian voice, English text only in a brief afterwards | open, not known yet whether this is by design |
| Gamepad: 24 % left stick threshold, no remapping | open; the threshold is read from the code, nothing changed yet |
| English text with Russianisms and empty notes | planned, as a separate text patch |
| Crash on the station level after the elite shooters (player reports) | possibly the `dinput8.dll` crash above, which we saw at a `station_02` load; not proven |

## Tested on
Windows 11 Pro, Steam build 222225 (PE 2008-10-13), Russian and English depots. Laptop: Ryzen 5 5600H,
AMD Radeon iGPU and NVIDIA RTX 3050 Ti Laptop (both tested), 1920×1080 at 144 Hz, display scaling 125 %,
profile with a Cyrillic name.

## For developers
- How the engine works (formats, memory, timing, device setup, saves), how each fix was found and verified,
  and 21 gotchas: the field note `knowledge/games/collapse/collapse-2008-formats-memory-timing-and-8876086c.md`
  in the universal-modder repository.
- `patch/tests/` holds the byte checks (`st_a.py`, `st16_laa.py`). `tools/` holds the measuring harness (set
  `COLLAPSE_DIR` to your game folder and `COLLAPSE_RUNS` to a folder for raw data outside the repo):
  - `run.py`: external address-space and commit sampler, mapped-file and DLL log, ProcDump on crash;
  - `probe.js`: a Frida probe that hooks system DLLs only;
  - `savetrace.js`: a Frida trace of save-file writes;
  - `pad.js`: a simulated gamepad through a hook on `XInputGetState`;
  - `navtest.js`, `navcall.js`: force the navmesh loop state to test `nav_guard`;
  - `gpumem.ps1`: the game's dedicated and shared GPU memory every 2 s, read from outside through WMI;
  - `regress.py`: regression part A, the game started to the menu once per ini variant, no input;
  - `mouseref.c`, `mouseref_watch.py`: read the shared mouse count in Windows' `dinput8.dll` (offsets of one
    Windows build, `dbcea407`; they refuse any other) to test `mouse_keeper`.
- No game files, extracted assets or decompiled code are included.

## Credits
- Collapse by Creoteam (Kyiv), 2008. This is an unofficial fan fix.
- Testing and play sessions: wh1tem0nst3r. Analysis and code written with an AI agent (Claude Code,
  Claude Opus 5.5), directed and checked in play by wh1tem0nst3r.
- Prior community work: the WSGF FOV guide, the PCGamingWiki page, and the Steam Community players whose
  reports shaped the list of problems.
- Built with [zig](https://ziglang.org/). No third-party code is included.

## License
MIT, under the universal-modder repository's `LICENSE` (Copyright (c) 2026 Rehan and universal-modder
contributors), a copy of which is in the release zip. It covers collapsefix and the patcher, not the game: you
need your own copy of Collapse.
