# ZenGin: Gothic 1 and Gothic 2 (Piranha Bytes)

Piranha Bytes' own C++ engine, 32-bit only. Gothic 1 (`system/Gothic.exe`, report version 1.08k)
and Gothic 2 / Night of the Raven (`system/Gothic2.exe`, report version 2.6.0.0-rev2). There is no
official mod loader; the community stack is **Union** for code, **GD3D11** for a modern renderer,
and **ZenKit** for assets. All three are x86.

## Check the exe build first — it decides everything

Union, GD3D11 and gothic-api each pin one report build per game. A wrong build loads nothing.

- **Gothic 2:** GOG and Steam ship "Gothic II - 2.7" (`Gothic2.exe` ≈ 9,040,036 B). The community
  build Union and GD3D11 support is **2.6.0.0-rev2** (`Gothic2.exe` 9,038,140 B, title bar reads
  "Gothic II - 2.6 (fix)"). Get it from the community's g2 fix package, back the original up as
  `Gothic2.gog27.exe.bak`, and drop the 2.6 exe into `system/`.
- **Gothic 1:** same pattern — Union expects the community-patched 1.08k build, not the retail exe.
- Union may already be in the install: `SHW32.DLL` loaded in-process and `saves/<slot>/UnionPlugin*.dat`
  are the tells. GOG's compatibility wrapper (`ddraw.dll`/`dinput.dll`/`dixi.ini`) coexists; GD3D11
  replaces the `ddraw.dll`, so keep GOG's as `ddraw.gog.dll.bak`.

## Route 1: Union plugin (native hooks, most reach)

- A plugin is an x86 DLL exporting the Union `Game_*` lifecycle symbols (`Game_Init`, `Game_Exit`,
  `Game_PreLoop`/`Game_PostLoop`/`Game_Loop` section callbacks, `Game_SaveBegin/End`,
  `Game_LoadBegin/End`, `Game_Pause/Unpause`, `Game_Entry/Exit` screen calls — 21 in all). Drop it in
  `system/autorun/` (create the dir if missing). `UnionAPI.dll` belongs in `system/` when the plugin
  doesn't link Union statically. Plugins can also ship inside a `.vdf`/`.mod` in `Data/`.
- **gothic-api** headers describe the engine classes per build. One define selects the engine
  (`__G1`, `__G1A`, `__G2`, `__G2A`) and namespaces follow (`Gothic_I_Classic`, `Gothic_II_Addon`, …).
  Wrap engine-touched code in `HOOKSPACE(Gothic_II_Addon, GetGameVersion() == Engine_G2A)` so a stray
  DLL just idles in the wrong game.
- Per-frame work: Detours-hook `oCGame::Render` (address per engine build; e.g. G2A `0x006C86A0`) or
  use Union's loop events. Chat with the user through `zcon->AddEvalFunc` (console commands) and
  `zerr->Message` (in-game toast; takes a non-const `zSTRING&` — pass an lvalue).
- Build: CMake + MSVC x86 (`-A Win32 -T v142` works on VS2019+). The prebuilt UnionAPI package ships
  `UnionAPIStatic.lib` (most of Union is header-only) and `Detours.lib`. Define `_UNION_API_LIB`, and
  link `/NODEFAULTLIB:UnionApi.lib` (a stray pragma in the headers otherwise drags in the dynamic
  stub) and `/NODEFAULTLIB:LIBCMT` (Detours' /MT record). `#undef min`/`max` after Windows.h inside
  gothic-api TUs — the macros collide with `std::min`.

## Route 2: renderer-level (GD3D11)

The stock renderer is DX7-era DirectDraw. GD3D11 is a community D3D11 renderer: it ships its own
`ddraw.dll` + per-engine DLLs (`system/GD3D11/bin/g1_*.dll`, `g2a_*.dll`) and `UserSettings.ini`.
Once loaded (`d3d11.dll`, `dxgi.dll` in-process) you get a real D3D11 device, HDR chain and depth —
enough for ReShade-addon compositing or custom overlays without fighting DirectDraw.

## Engine facts

- Units **centimeters**, **+Y up**, **left-handed**, +Z is the vob forward ("at") vector.
- The camera actually rendering the frame is `zCCamera::activeCam` (global static); `ogame`/
  `oCSession::GetCamera()` is the session camera and can differ. `zCAICamera` drives it
  (`firstPerson` flag at a fixed offset).
- Raycasts: `zCWorld::TraceRayFirstHit`. Vob-bbox traces return box *tops* — probing under a bridge
  reports the bridge.
- `oCGame::Render` also runs on loading screens: gate per-frame work on `gameMan->IsGameRunning()`
  plus the `inLoadSaveGame`/`inLevelChange`/`m_bWorldEntered` flags.
- ZenGin **source trees circulate** (a Gothic 1 engine tree — often community-modified — and a
  Gothic 2 tree with `libraries/`+`work/`). Excellent for class layouts, enum values and function
  names; do **not** trust it for retail addresses — confirm in the binary or the gothic-api headers.

## Assets and scripts

- `Data/*.vdf` volumes (`Textures`, `Meshes`, `Anims`, `Sounds`, `Speech*`, `Worlds`, plus
  `*_Addon.vdf` for NotR). Mount them with ZenKit (`pip install zenkit`): `zenkit.Vfs()` +
  `mount_disk`. API quirks: `VfsNode.children` is a property that raises on files, `vfs.find()`
  matches basenames not paths.
- `.ZTEX` textures: 32-byte header then a contiguous DXT mip chain with no per-mip sizes — derive
  each mip's size from w/h. zenkit-py's `Texture.load` can return 0×0 mips; hand-decode the DXT in
  that case.
- `.MDM` skeletal meshes, `.MDH` per-creature anim libraries (e.g. `SCAVENGERGL.MDH`), `.MRM`
  compiled static meshes, `.ZEN` levels.
- Game logic scripts are **Daedalus** bytecode compiled to `.DAT` under `_work/Data/Scripts`. Union
  can call script functions and register new externals, which is how most gameplay mods work.
- Plugin configs/logs conventionally live beside the exe in `system/`.

## What to scan for

`um scan <gothic folder>` detects `system/gothic*.exe` + `data/*.vdf` as engine `zengin`. Union
shows up as `SHW32.DLL`; GD3D11 as `system/GD3D11/`; SystemPack/player-kit builds leave their own
`system/*.ini`.
