# Changelog

## 1.0.1 (unreleased)
- `heap_guard` (new, on by default): a crash while loading a save (`collapse.exe` access violation). When a block
  of the game's memory became free, its allocator could hand part of it back to Windows, report a failure, then
  write into the part it no longer had; it could also give back memory next to the block. Memory now goes back
  to Windows only when all of the block can go, and never past it. Tested without the game on the game's own code
  (`tools/heapguard_test.c`) and in play.

## 1.0.0 (2026-11-02): first public release
Tested on the Steam build (`collapse.exe` PE 2008-10-13), Windows 11, NVIDIA RTX 3050 Ti Laptop and AMD Radeon
iGPU, 1920×1080. The whole campaign was played through on this fix, then a release regression: every ini key on
and off, exclusive mode with 84 Alt+Tabs, a virtual gamepad, and a clean install from Steam by the README.

**`laa_patch.exe`** (new): the Large Address Aware patch as a small program, so Python is no longer needed. It
checks the exe hash, keeps `collapse.exe.bak`, and `--restore` puts the original back.

**collapsefix** (`dinput8.dll`, all keys in `collapsefix.ini`):
- **Crashes and freezes**
  - `release_batches`: the game never released its level geometry buffers, so memory grew with every level load
    and checkpoint reload until it ran out after a few hours. With the fix memory stays flat. This also stops the
    device leak on Alt+Tab in exclusive fullscreen and on a desktop refresh change.
  - `mouse_keeper`: a rare crash inside Windows' `dinput8.dll` during a scene load, caused by the game closing its
    mouse while dinput8's own thread still reads shared mouse state.
  - `nav_guard`: an endless loop in the navigation code (Mark's Castle) that froze the game with the mouse moving.
  - `borderless` (default) and `alt_tab`: Alt+Tab no longer ends in "Cannot initialize video".
  - `display_mode`, `refresh`: an unsupported `Resolution` or refresh rate falls back to the desktop mode instead
    of an endless "CreateDevice returned 8876086c" or an "out of range" monitor.
- **Picture and controls**
  - `fov=auto`: Hor+ field of view for wide screens, 90° at 16:9; engine cutscenes widen too.
  - `ui_scale=auto`: the interface grows with the resolution (125 % at 1080p).
  - `timer`: 1 ms game timer instead of 15.6 ms steps, so camera and menus no longer judder.
  - `vsync` (off by default), `dpi_aware` (sharp window at display scaling above 100 %).
  - `english_keys`: key hints stay English on any keyboard layout.
  - `pad_camera_deadzone`: an adjustable right-stick dead zone for worn gamepads.
- **Diagnostics**: `save_log` (saves the game failed to write, and a Controlled Folder Access warning), `input`
  (DirectInput errors), `[log] d3d_counts` (live D3D resources).

Known issues are listed in `README.md`. Development versions 0.1 to 0.5.7 were not released; how each fix was
found is in the universal-modder field note on Collapse.
