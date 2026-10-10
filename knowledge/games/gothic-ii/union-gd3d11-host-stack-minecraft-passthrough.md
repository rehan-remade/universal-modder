---
kind: game
title: "Gothic II NotR: Union plugin host stack for a passthrough (camera, ground raycasts, console, WS out)"
game: "Gothic II"
games_also: ["Minecraft Java Edition"]
game_version: "Gothic II Gold GOG (goggame-1207658718), system/Gothic2.exe swapped to community 2.6.0.0-rev2"
platform: windows
engine: zengin
route: passthrough
tools: ["Union 1.0m", "gothic-api headers", "GD3D11 nightly (g2a_avx2)", "MSVC 2019 v142 + CMake", "Detours (prebuilt UnionAPI-v142 package)", "ZenKit (zenkit-py)", "ReShade x86 addon (planned compositor)"]
anti_cheat: "none (2002 single-player game)"
status: in-progress
agents: ["Devin (SWE-2)"]
humans: []
date: 2026-10-08
links: ["https://github.com/Patrix9999/union-plugin-template", "https://gitlab.com/union-framework", "https://github.com/kirides/GD3D11", "https://www.worldofgothic.de/dl/download_278.htm"]
tags: ["gothic", "zengin", "union", "gd3d11", "passthrough", "native-hook", "camera", "raycast", "websocket"]
---

# Gothic II NotR: Union plugin host stack for a passthrough (camera, ground raycasts, console, WS out)

A Union plugin (`G2Passthrough.dll`) that publishes camera pose, first-person flag, player feet/heading
and a raycast ground grid over a WebSocket to a Minecraft guest mod — phase 1 of "Minecraft inside
Gothic 2". Builds cleanly with a clean dependency list; **not yet loaded in-game**. The reusable part
is the stack itself: exe version swap, GD3D11, the gothic-api address table, and the Union build recipe. See `references/engines/zengin.md` for the engine playbook.

## Setup

- Host: `C:\Program Files (x86)\GOG Galaxy\Games\Gothic 2 Gold`, a DRM-free GOG install. The GOG build
  reports "Gothic II - 2.7", `system/Gothic2.exe` 9,040,036 B (no VersionInfo resource).
- **Required swap:** Union + GD3D11 + gothic-api only support report version **2.6.0.0-rev2**. The
  community g2-fix package (an NSIS `gothic2_fix-2.6.0.0-rev2.exe`, extractable with 7z) carries the
  right `system/Gothic2.exe` (9,038,140 B). Get it from World of Gothic,
  https://www.worldofgothic.de/dl/download_278.htm (the page GD3D11's README links). Keep the original as
  `Gothic2.gog27.exe.bak`. After the swap the title bar reads "Gothic II - 2.6 (fix)".
- GD3D11 nightly (`GD3D11-git-<rev>.zip`) extracts into `system/`; it brings its own `ddraw.dll`, so
  back up GOG's wrapper dll first. Verified loaded in-process: `GD3D11/bin/g2a_avx2.dll`, `d3d11.dll`,
  `dxgi.dll`, `D3DCOMPILER_47.dll`, `GFSDK_SSAO_D3D11.win32.dll`. Needs `vcruntime140_1` x86.
- Union runtime presence check: `SHW32.DLL` in the process module list, and
  `saves/savegame*/UnionPlugin*.dat` proves plugin persistence already works on this install.
- Guest side (MC Fabric mod, ws `127.0.0.1:25602` + shared memory `Local\G2PassthroughFrame`) was
  adapted from `examples/minecraft-gta5-passthrough` in this repo.

## Route and why

Passthrough: the host game keeps running unmodified and streams state out; the guest renders its own
world. Alternatives considered: reimplementing ZenGin (years), or hooking DirectDraw for pixels (the
stock DX7-era renderer gives no usable depth/swapchain — that's why GD3D11 comes first). Union was
chosen over a hand-rolled proxy DLL because SHW32 already loads `system/autorun/*.dll` on this build
and gothic-api ships per-build class layouts and addresses.

## How the game works (what we had to learn)

Addresses below are **G2A (2.6.0.0-rev2) only**, from gothic-api headers; another build shifts them.

| Symbol | Address / offset | Use |
|---|---|---|
| `oCGame::Render` | `0x006C86A0` | per-frame hook (runs after original → camera is final) |
| `ogame` global | `0x00AB0884` | session/game object |
| `player` global | `0x00AB2684` | hero fallback |
| `gameMan->IsGameRunning()` | `0x0042B200` | menu/in-game gate |
| `oCGame::{inLoadSaveGame, inLevelChange, m_bWorldEntered}` | offsets `0x28/0x2C/0x144` | loading gate |
| `zCSession::GetCamera()/GetCameraAI()/GetWorld()` | `0x005DE790/0x005DE7A0/0x005DECF0` | camera + world access (`oCGame` derives from `zCSession`; `0x005DE7B0` is `GetCameraVob`) |
| `oCGame::GetSelfPlayerVob()` | `0x006C2C60` | hero vob |
| `zCCamera::activeCam` + `GetCamPos` | static ptr, `0x0054B960` | **the rendering camera** |
| `zCCamera::{camMatrix, trafoViewInv, fovV, nearClipZ, farClipZ}` | offsets `0xA4/0x188/0x91C/0x900/0x8FC` | pose + projection |
| `zCAICamera::firstPerson` | offset `0x294` | fp flag |
| `zCWorld::TraceRayFirstHit(from,dir,vob,flags)` | `0x00621E70` | ground probes → `traceRayReport.foundIntersection` |
| `zCVob::GetPositionWorld/GetAtVectorWorld` | `0x0052DC90/…B0` | player pos/heading |
| `zrenderer->{vid_xdim,vid_ydim}`, `hWndApp` | `0x00982F08`+`0x0C/0x10`, `0x008D422C` | viewport dims |
| `zcon->AddEvalFunc` | `0x00784F80` | register a console command |
| `zerr->Message(zSTRING const&)` | `0x0044DA10` | message via `zERROR`, the engine logger (whether it shows in game is unconfirmed) |

- Coordinates: **centimeters, +Y up, left-handed** (+Z forward). Minecraft mapping used:
  `mc = (-x, y, z) / 100` (mirror X, switchable to Z in the ini — needs an in-game strafe test);
  `yaw = deg(atan2(-f.x, f.z))`, `pitch = -deg(asin(f.y))`.
- Ground grid: `TraceRayFirstHit` straight down per MC column center within radius, flags
  `zTRACERAY_VOB_BBOX | VOB_IGNORE_CHARACTER | VOB_IGNORE_NO_CD_DYN | VOB_IGNORE_PROJECTILES |
  POLY_IGNORE_TRANSP`, 160-probe/frame budget, per-column memoization, `{"t":"clear"}` + resample on
  request.

## Build steps

1. `cmake -B build -S . -G "Visual Studio 16 2019" -A Win32 -T v142 && cmake --build build --config Release`
   — plugin is x86, `UnionAPIStatic.lib` + `Libs/v142/Detours.lib` from the prebuilt UnionAPI-v142
   package, `_UNION_API_LIB` defined.
2. Drop `G2Passthrough.dll` into `system/autorun/` (create it). No `UnionAPI.dll` dependency when
   linked statically.
3. Config in `system/G2Passthrough.ini` (ws port, ground radius, probe budget, mirror axis, logCam);
   log at `system/G2Passthrough.log`; `g2pt status|on|off|relevel` console command + F7/F8 hotkeys.

## Verification

- Build: clean compile on VS2019 14.29.30133; dependency list limited to
  WS2_32/KERNEL32/USER32/MSVCP140/VCRUNTIME140/UCRT/dbghelp. Exports don't show that a plugin loads: in
  union-plugin-template the `Game_*` functions are plain functions in `GOTHIC_NAMESPACE`, each called from a
  hook in `src/Plugin.ipp`, and neither union-api nor gothic-api looks for them.
- Runtime stack verified in-process **without** the plugin: SHW32 + g2a_avx2 + d3d11 all loaded,
  menu reachable windowed 1024×768, screenshots fine.
- **Not verified:** that the plugin loads at all (no log line from `DllMain` yet, not checked in Union's
  plugin list), the plugin in-game, the X-mirror calibration, and GD3D11 depth for the ReShade compositor
  oracle.

## Gotchas

1. **Symptom.** Union/GD3D11 "don't work" on a fresh GOG install. **Cause:** GOG ships report build
   2.7; everything targets 2.6.0.0-rev2. **Fix:** swap `system/Gothic2.exe` (see Setup).
2. **Symptom.** `um scan` reported no executables. **Cause:** scan only fingerprinted top-level exes;
   Gothic's exe is `system/Gothic2.exe`. **Fix:** fixed upstream in `um` (nested-exe fingerprinting).
3. **Symptom.** Link pulls `UnionApi.lib` (dynamic stub) even with the static lib. **Cause:** a
   `#pragma comment(lib)` behind `_UNION_API_LIB` in the headers of the prebuilt UnionAPI-v142 package.
   Current union-api main (https://gitlab.com/union-framework/union-api) has no such pragma, so this may be
   specific to that package. **Fix:** `/NODEFAULTLIB:UnionApi.lib`, plus `/NODEFAULTLIB:LIBCMT` for
   Detours' /MT record.
4. **Unconfirmed.** **Symptom.** `zerr->Message(zSTRING("..."))` didn't compile. **Cause:** not known.
   It was put down to a non-const `zSTRING&` parameter, but in gothic-api's G2A headers
   `zERROR::Message(zSTRING const&)` (`0x0044DA10`) takes a temporary fine. The non-const overload at
   `0x0078E5F0` that was first listed here is the private `zCParser::Message(zSTRING&)`. **Fix:** passing
   an lvalue compiled; check which function the call actually resolves to.
5. **Symptom.** `std::min` errors inside gothic-api TUs. **Cause:** Windows.h `min`/`max` macros.
   **Fix:** `#undef` them after the includes.
6. **Expected, not observed (the plugin hasn't run in game).** **Symptom.** Spawned-at-runtime queries
   return the menu camera's pose. **Cause:** `ogame`'s session camera isn't necessarily the render
   camera. **Fix:** read `zCCamera::activeCam`, fall back to `ogame->GetCamera()`.
7. **Expected, not observed.** **Symptom.** A console command registered at `Game_Init` does nothing.
   **Cause:** most likely `Game_Init` never ran: in union-plugin-template each `Game_*` callback is called
   from a hook that ships commented out in `src/Plugin.ipp`. A null check on `zcon` doesn't help, because
   gothic-api declares `zcon` as the fixed address of the engine's static console object (`0x00AB3860`),
   so `zcon != nullptr` is always true. **Fix:** enable the hook behind the callback you register from, and
   confirm it runs (a log line) before debugging the console.
8. **Expected, not observed.** **Symptom.** Stray camera frames during loading screens. **Cause:**
   `oCGame::Render` runs there too. **Fix:** gate on `IsGameRunning()` + the three loading flags (harmless
   either way).
9. **Symptom.** zenkit-py `Texture.load` returns 0×0 mips on ZTEX files. **Cause:** apparent zenkit-py
   bug. **Fix:** hand-decode. ZTEX is a 36-byte header (`ZTEX`, version, format, width, height, mip count,
   reference width/height, average colour), plus a 1 KB palette for P8, then the mip chain smallest first
   with no per-mip sizes. Size each level from w/h and the format; the full-size mip is the last block.
   ZenKit's C++ `Texture::load` reads it this way.

## Open questions

- Does the plugin load at all? Needs a real load check: a log line from `DllMain`, or the plugin showing
  up in Union's plugin list.
- Are the hooks behind each `Game_*` callback the plugin relies on actually enabled in `src/Plugin.ipp`?
  The template ships them commented out.
- Which `Message` does the plugin's `zerr->Message` call resolve to (Gotcha 4), and does `zERROR` show
  anything in game or only write to its log?
- Mirror axis (x vs z) — decided by the first in-game strafe test (`mirror=z|n` ini + `logCam=1`).
- Whether ReShade's depth on GD3D11 is usable for compositing (the Black Myth note warns ReShade
  depth can be flat — verify the oracle before building the compositor; fallback is a GD3D11 fork).
- Phase 2: inbound `blocks`/`mobs`/`mcpos` messages → collision proxy vobs and NPC proxies.
