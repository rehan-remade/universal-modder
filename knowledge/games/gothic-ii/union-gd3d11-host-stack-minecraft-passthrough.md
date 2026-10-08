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
links: ["https://github.com/Patrix9999/union-plugin-template", "https://gitlab.com/union-framework"]
tags: ["gothic", "zengin", "union", "gd3d11", "passthrough", "native-hook", "camera", "raycast", "websocket"]
---

# Gothic II NotR: Union plugin host stack for a passthrough (camera, ground raycasts, console, WS out)

A Union plugin (`G2Passthrough.dll`) that publishes camera pose, first-person flag, player feet/heading
and a raycast ground grid over a WebSocket to a Minecraft guest mod — phase 1 of "Minecraft inside
Gothic 2". Built and verified to *load-grade* (all 21 `Game_*` exports, clean dep list); **not yet
confirmed in-game**. The reusable part is the stack itself: exe version swap, GD3D11, the gothic-api
address table, and the Union build recipe. See `references/engines/zengin.md` for the engine playbook.

## Setup

- Host: `C:\Program Files (x86)\GOG Galaxy\Games\Gothic 2 Gold` — GOG build reports "Gothic II - 2.7",
  `system/Gothic2.exe` 9,040,036 B (no VersionInfo resource).
- **Required swap:** Union + GD3D11 + gothic-api only support report version **2.6.0.0-rev2**. The
  community g2-fix package (an NSIS `gothic2_fix-2.6.0.0-rev2.exe`, extractable with 7z) carries the
  right `system/Gothic2.exe` (9,038,140 B). Keep the original as `Gothic2.gog27.exe.bak`. worldofgothic.de
  hides it behind Anubis anti-bot; the Tawerna Gothic Dropbox mirror works. After the swap the title
  bar reads "Gothic II - 2.6 (fix)".
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
| `oCSession::GetCamera()/GetCameraAI()/GetWorld()` | `0x005DE790/…A0/…B0` | camera + world access |
| `oCGame::GetSelfPlayerVob()` | `0x006C2C60` | hero vob |
| `zCCamera::activeCam` + `GetCamPos` | static ptr, `0x0054B960` | **the rendering camera** |
| `zCCamera::{camMatrix, trafoViewInv, fovV, nearClipZ, farClipZ}` | offsets `0xA4/0x188/0x91C/0x900/0x8FC` | pose + projection |
| `zCAICamera::firstPerson` | offset `0x294` | fp flag |
| `zCWorld::TraceRayFirstHit(from,dir,vob,flags)` | `0x00621E70` | ground probes → `traceRayReport.foundIntersection` |
| `zCVob::GetPositionWorld/GetAtVectorWorld` | `0x0052DC90/…B0` | player pos/heading |
| `zrenderer->{vid_xdim,vid_ydim}`, `hWndApp` | `0x00982F08`+`0x0C/0x10`, `0x008D422C` | viewport dims |
| `zcon->AddEvalFunc` | `0x00784F80` | register a console command |
| `zerr->Message(zSTRING&)` | `0x0078E5F0` | in-game toast |

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

- Build: clean compile on VS2019 14.29.30133; `dumpbin /exports` shows all 21 `Game_*` exports;
  dependency list limited to WS2_32/KERNEL32/USER32/MSVCP140/VCRUNTIME140/UCRT/dbghelp.
- Runtime stack verified in-process **without** the plugin: SHW32 + g2a_avx2 + d3d11 all loaded,
  menu reachable windowed 1024×768, screenshots fine.
- **Not verified:** the plugin in-game, the X-mirror calibration, and GD3D11 depth for the ReShade
  compositor oracle.

## Gotchas

1. **Symptom.** Union/GD3D11 "don't work" on a fresh GOG install. **Cause:** GOG ships report build
   2.7; everything targets 2.6.0.0-rev2. **Fix:** swap `system/Gothic2.exe` (see Setup).
2. **Symptom.** `um scan` reported no executables. **Cause:** scan only fingerprinted top-level exes;
   Gothic's exe is `system/Gothic2.exe`. **Fix:** fixed upstream in `um` (nested-exe fingerprinting).
3. **Symptom.** Link pulls `UnionApi.lib` (dynamic stub) even with the static lib. **Cause:** a
   `#pragma comment(lib)` behind `_UNION_API_LIB`. **Fix:** `/NODEFAULTLIB:UnionApi.lib`, plus
   `/NODEFAULTLIB:LIBCMT` for Detours' /MT record.
4. **Symptom.** `zerr->Message(zSTRING("..."))` won't compile. **Cause:** non-const ref param.
   **Fix:** pass an lvalue.
5. **Symptom.** `std::min` errors inside gothic-api TUs. **Cause:** Windows.h `min`/`max` macros.
   **Fix:** `#undef` them after the includes.
6. **Symptom.** Spawned-at-runtime queries return the menu camera's pose. **Cause:** `ogame`'s session
   camera isn't the render camera. **Fix:** read `zCCamera::activeCam`, fall back to `ogame->GetCamera()`.
7. **Symptom.** Console command/hotkey does nothing early. **Cause:** `zcon` doesn't exist at
   `Game_Init`. **Fix:** register the eval func lazily on the first frame where `zcon != nullptr`.
8. **Symptom.** Stray camera frames during loading screens. **Cause:** `oCGame::Render` runs there
   too. **Fix:** gate on `IsGameRunning()` + the three loading flags (harmless either way).
9. **Symptom.** zenkit-py `Texture.load` returns 0×0 mips on ZTEX files. **Cause:** apparent zenkit-py
   bug. **Fix:** hand-decode — ZTEX is a 32-byte header then a contiguous DXT mip chain sized from w/h.
10. **Symptom.** Sources corrupted after heredoc writes (`\G`, `\` escapes). **Fix:** grep new files
    for stray single backslashes before compiling.

## Open questions

- Mirror axis (x vs z) — decided by the first in-game strafe test (`mirror=z|n` ini + `logCam=1`).
- Whether ReShade's depth on GD3D11 is usable for compositing (the Black Myth note warns ReShade
  depth can be flat — verify the oracle before building the compositor; fallback is a GD3D11 fork).
- Phase 2: inbound `blocks`/`mobs`/`mcpos` messages → collision proxy vobs and NPC proxies.
