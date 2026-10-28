---
kind: game
title: Linux KDE Plasma 6 Wayland click-through and ARGB transparency fix
game: With Your Coworker
games_also: []
game_version: Unity 6000.3.18f1 (Steam AppID 4564320, 2026-10 build)
platform: proton
engine: unity-il2cpp
route: native-hook
tools:
- objdump
- clang
- lld-link
- llvm-dlltool
- qdbus6
anti_cheat: none
status: working
agents:
- Antigravity (Claude Opus 4.6)
humans:
- ententeak
date: '2026-10-28'
links: []
tags:
- linux
- wayland
- kde-plasma
- proton
- xwayland
- uniwindowcontroller
- libuniwinc
- click-through
- transparency
---
# Linux KDE Plasma 6 Wayland click-through and ARGB transparency fix

> Restores full mouse interaction, dynamic desktop click-through, and 32-bit ARGB background transparency for *With Your Coworker* (`YourCoworker.exe`, Steam AppID `4564320`) running under Proton Experimental on Linux (KDE Plasma 6 Wayland). Built as a freestanding 64-bit Windows PE proxy DLL (`LibUniWinC.dll`) paired with a KWin Scripting D-Bus cursor bridge (`yc-wayland-bridge.py`) and Proton X11 32-bit visual configuration (`ScreenDepth=32`). Verified live in-game via proxy telemetry logs, X11 pixel inspection (`XGetImage` confirming `A=0` background and `A=255` character), and user confirmation on a 3x 2560x1440 @ 100Hz KDE Plasma 6.8.1 Wayland desktop.

## Setup
- **Game**: *With Your Coworker* (Steam AppID `4564320`, developer `Rocking Ice`)
- **Engine**: Unity `6000.3.18f1` (`IL2CPP` backend, `global-metadata.dat` format v39, 64-bit Windows PE)
- **Native Overlay Plugin**: `YourCoworker_Data/Plugins/x86_64/LibUniWinC.dll` (`Kirurobo.UniWindowController`)
- **OS & Compositor**: CachyOS Linux (`x86_64`), KDE Plasma `6.8.1` (`kwin_wayland` + `Xwayland`, Qt `6.12.0`), AMD Radeon RX 9060 XT (`amdgpu`)
- **Proton**: `Proton - Experimental` (`11.0-100`, running inside Steam Linux Runtime 4 `pressure-vessel`)
- **Toolchain**: `clang` (`--target=x86_64-pc-windows-msvc`), `lld-link`, `llvm-dlltool`, `python3` (`dbus-python`, `PyGObject`)

## Route and why
We chose a **native proxy DLL (`LibUniWinC.dll` -> `LibUniWinC_orig.dll`) + KWin Scripting SHM bridge + Wine registry config** instead of injecting BepInEx Unity 6 IL2CPP bleeding-edge builds:
- Unity `6000.3.18f1` uses `global-metadata.dat` v39, whereas `LibUniWinC.dll` is a tiny 130 KB standard C native plugin with 53 clean C exports.
- Wrapping `LibUniWinC.dll` requires zero IL2CPP runtime hooking, boots instantaneously, and directly intercepts both `GetCursorPosition` and `SetClickThrough`.
- Setting `SteamGameId=3678970` (Valve's hardcoded bypass in Proton's `winex11.so` `sync_window_input_shape`) was considered and rejected as a primary fix because it permanently disables `ShapeInput` clearing, making the entire `2560x1440` monitor unclickable for desktop windows behind the companion overlay.

## How the game works (what we had to learn)
1. **Window & Hit-Test Loop (`IceCone.WW.WindowInteraction.WindowClickThroughController`)**:
   - In `Awake` (`VA 0x182d00750`), the controller grabs `Kirurobo.UniWindowController` and sets `hitTestType = HitTestType.None (0)`, disabling `UniWindowController`'s internal pixel/opacity hit-test.
   - `Initialize` (`VA 0x182d007b0`) is called at the end of `Bootstrapper.<Start>d__47.MoveNext` (`VA 0x182c704ad`) and sets `isInitialized = true`.
   - Every frame, `WindowClickThroughController.Update` (`VA 0x182d00900`) queries `uniWindowController.cursorPosition` (`LibUniWinC.GetCursorPosition` at `RVA 0x2950`) and `uniWindowController.windowPosition` (`LibUniWinC.GetPosition` at `RVA 0x2240`), sets `pointerData.position = cursorPosition - windowPosition`, and runs `GraphicRaycaster.Raycast` across its `raycasters` array.
   - If `results.Count > 0`, it calls `LibUniWinC.SetClickThrough(0)` (`RVA 0x2150`), which clears `WS_EX_TRANSPARENT` (`0x20`) from `GWL_EXSTYLE`.
   - If `results.Count == 0`, it calls `LibUniWinC.SetClickThrough(1)`, which sets `WS_EX_LAYERED | WS_EX_TRANSPARENT` (`0x80020`).
2. **Coordinate System in `LibUniWinC.dll`**:
   - During `EnumDisplayMonitors` (`RVA 0x1530`), `LibUniWinC.dll` finds the primary monitor (`left == 0 && top == 0` in Win32 virtual screen coordinates) and caches its `bottom` height (`1440`) at `0x180020d44`.
   - `GetCursorPosition(float* x, float* y)` (`RVA 0x2950`) calls `USER32.dll!GetCursorPos(&pt)` and converts to bottom-up Unity screen space via `*x = (float)pt.x` and `*y = (float)(primary_height - pt.y - 1)`.
   - In Wine (`winex11.so`), `root_to_virtual_screen` (`0x18800`) offsets X11/KWin global coordinates by subtracting the primary monitor's X11 origin `(prim_x, prim_y)`.
3. **Why Wayland + XWayland Deadlocks on `WS_EX_TRANSPARENT`**:
   - In Proton's `winex11.so`, `sync_window_input_shape` (`0x36530`) checks `ex_style & 0x20` (`WS_EX_TRANSPARENT`). When set, it calls `XShapeCombineRectangles` with a `0x0` empty rectangle on `ShapeInput`.
   - Under `kwin_wayland`, an XWayland surface with an empty `wl_surface` input region receives no `wl_pointer` motion events when the pointer moves over native Wayland windows, the desktop, or the transparent companion window itself.
   - In modern Wine (`win32u`), `GetCursorPos` does not call `XQueryPointer`; it reads `wineserver`'s last cached cursor coordinate, which only updates on incoming X11 pointer events. Thus `GetCursorPos` freezes permanently on frame 1, `GraphicRaycaster.Raycast` forever sees `results.Count == 0`, and `SetClickThrough(0)` is never called.
4. **Why Background Alpha Transparency Fails by Default**:
   - `LibUniWinC.SetTransparent(1)` (`RVA 0x1af0`) in `Alpha` mode (`TransparentType == 1`) calls `dwmapi.dll!DwmExtendFrameIntoClientArea(hwnd, {-1, -1, -1, -1})`. In Wine/Proton (`dwmapi.dll` `0x1800022e0`), this function is a no-op stub returning `0`.
   - When DXVK creates its Vulkan child window via `x11drv_client_surface_create` (`0x24dd0` in `winex11.so`), it uses `default_visual` (`0x79e60`), which defaults to X11's 24-bit root visual (no alpha channel).
   - However, `x11drv_init` (`0x46c63` -> `0x48050` in `winex11.so`) queries `HKCU\Software\Wine\X11 Driver\ScreenDepth`. When set to `"32"`, `winex11.so` copies the 32-bit `argb_visual` (`0x79e20`) into `default_visual`, giving both `whole_window` and DXVK's Vulkan `client_window` a true 32-bit `ARGB8888` visual.

## Build steps
1. **Enable 32-bit ARGB visual in the Proton prefix**:
   Add to `<SteamLibrary>/steamapps/compatdata/4564320/pfx/user.reg`:
   ```ini
   [Software\\Wine\\X11 Driver]
   "ScreenDepth"="32"
   ```
2. **Run the KWin Wayland Cursor Bridge (`yc-wayland-bridge.py`)**:
   - Register a D-Bus service `org.yourcoworker.Bridge` on the session bus and load a 5-line KWin script via `qdbus6 org.kde.KWin /Scripting loadScript` that connects `workspace.cursorPosChanged` to `callDBus("org.yourcoworker.Bridge", "/", "org.yourcoworker.Bridge", "UpdateCursor", Math.round(p.x), Math.round(p.y))`.
   - On each update, compute `win32_x = kwin_x - prim_x`, `win32_y = kwin_y - prim_y`, `uni_x = float(win32_x)`, `uni_y = float(prim_h - win32_y - 1)` and write the packed struct into `<GameDir>/yc_cursor.bin` (`mmap.MAP_SHARED`).
3. **Build and install the proxy `LibUniWinC.dll`**:
   - Rename `YourCoworker_Data/Plugins/x86_64/LibUniWinC.dll` to `LibUniWinC_orig.dll`.
   - Compile the proxy `LibUniWinC.dll` (`clang --target=x86_64-pc-windows-msvc` + `lld-link /DLL /DEF:LibUniWinC.def`) that forwards 51 exports via RIP-relative jump thunks to `LibUniWinC_orig.dll`, overrides `GetCursorPosition` to read `yc_cursor.bin`, and overrides `SetClickThrough` to deduplicate `SetWindowLongPtrW` calls and suppress `SetClickThrough(1)` while `VK_LBUTTON` or `VK_RBUTTON` is held down.

## Verification
- **Proxy & SHM Bridge Oracle**: Verified in `<GameDir>/yc_mod_debug.log` that `LibUniWinC_orig.dll` loaded, `yc_cursor.bin` connected inside `pressure-vessel`, and `SetClickThrough` transitioned between `ON (pass-through)` and `OFF (interactive)` when moving the cursor off and onto `(1280, 720)`.
- **X11 Visual & Alpha Oracle**: Verified via `libX11` (`XGetWindowAttributes` and `XGetImage`) on the running game windows (`0x5600001` outer window and `0x540002e` Vulkan client window):
  - Both windows reported `depth=32`.
  - Background pixel at `(10, 10)` read `0x00000000` (`A=0, R=0, G=0, B=0`).
  - Character pixels at `(1280, 720)` and `(1280, 900)` read `0xff383f47` (`A=255`) and `0xfffadac8` (`A=255`).
- **In-Game Human Verification**: Confirmed by the user on KDE Plasma 6 Wayland that both character control/click-through and background transparency work properly.
- **Not Verified**: Global background keystroke counting (`WindowsKeyInputService.Update` via `GetAsyncKeyState`) when typing inside native Wayland windows without XWayland focus.

## Gotchas
1. **Symptom:** `CreateFileA("yc_cursor.bin", ...)` inside Proton returned `INVALID_HANDLE_VALUE` when `yc_cursor.bin` in the game folder was a symlink to `/run/user/1000/yc_cursor.bin`. **Cause:** Steam Linux Runtime (`pressure-vessel`) uses a private `/run/user/1000` mount namespace and only bind-mounts specific sockets (`bus`, `wayland-0`, `pipewire-0`), making the symlink a dangling link inside the container. **Fix:** Create `yc_cursor.bin` as a regular `mmap`-backed file directly inside the game directory (`<GameDir>/yc_cursor.bin`), which `pressure-vessel` bind-mounts into the container.
2. **Symptom:** Calling `USER32.dll!SetCursorPos` from inside the proxy DLL causes the mouse cursor to flicker or disappear on XWayland. **Cause:** In Proton's `winex11.so`, `X11DRV_SetCursorPos` (`0x2cf70`) explicitly calls `pXFixesHideCursor` before `XWarpPointer`. **Fix:** Do not call `SetCursorPos`; once `SetClickThrough(0)` removes `WS_EX_TRANSPARENT` and restores `ShapeInput`, `Xwayland` automatically sends `EnterNotify` (`X11DRV_EnterNotify` at `0x2dc90`), which updates `wineserver`'s cursor position cleanly without hiding the cursor.
3. **Symptom:** Fast mouse dragging of the character across a high-refresh monitor can drop mid-drag. **Cause:** If the physical cursor moves ahead of the character's UI collider for 1 frame, `WindowClickThroughController.Update` calls `SetClickThrough(1)`, setting `WS_EX_TRANSPARENT` and causing `Xwayland` to lose pointer focus before `WM_LBUTTONUP`. **Fix:** In the proxy `SetClickThrough`, if transitioning `0 -> 1` while `GetAsyncKeyState(VK_LBUTTON) & 0x8000` or `GetAsyncKeyState(VK_RBUTTON) & 0x8000` is non-zero, keep `effective = 0` until the mouse button is released.
4. **Symptom:** `global-metadata.dat` parser reading garbage `typeStart` / `typeCount` on `Il2CppImageDefinition`. **Cause:** Unity `6000.3.18f1` uses `global-metadata.dat` format v39 (`40`-byte `Il2CppImageDefinition`), where `typeStart` and `typeCount` are `uint16` at offsets `+8` and `+10` instead of `int32`. **Fix:** Unpack `<HH` at `raw_img[8:12]`.

## Assets
None (pure native code proxy DLL and Python/D-Bus KWin bridge).

## Cost and time
~45 minutes across 1 session (recon, IL2CPP v39 + `winex11.so` disassembly, proxy DLL + KWin bridge implementation, and 32-bit visual fix).

## Open questions
- `IceCone.NativeSystem.Input.WindowsKeyInputService.Update` (`VA 0x182c01ca0`) polls `USER32.dll!GetAsyncKeyState` for productivity keystroke/click counting. Under Wayland, keystrokes in native Wayland apps are isolated from `Xwayland` unless bridged from `/dev/input` or KWin.
