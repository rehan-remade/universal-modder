# ZenGin: Gothic 1 and Gothic 2 (Piranha Bytes)

Piranha Bytes' own C++ engine, 32-bit only: Gothic 1 (`system/Gothic.exe`) and Gothic 2 / Night of the Raven
(`system/Gothic2.exe`). Gothic 3 (Genome) and Gothic 1 Remake (Unreal Engine 5) are different engines.
- Most gameplay mods are **Daedalus** scripts built with the official Mod Development Kit (MDK), and THQ Nordic's
  Steam releases have an official Workshop beta.
- For engine code the community stack is **Union** (C++ plugins), **GD3D11** (a modern renderer) and **ZenKit**
  (assets). Union plugins and GD3D11 are x86, like the game.

## Check the exe build first: it decides everything

Union, GD3D11 and gothic-api target specific exe builds, and a wrong build loads nothing.
- **Gothic 1:** **1.08k_mod (Player Kit build)**, not the retail exe. GD3D11 calls it "1.08k (1.30.0.0)",
  gothic-api "v1.08k_mod".
- **Gothic 2 NotR:** **2.6.0.0-rev2** (`Gothic2.exe` 9,038,140 B, title bar "Gothic II - 2.6 (fix)"; gothic-api
  calls it "v2.6 (fix)"). GOG and Steam ship "Gothic II - 2.7" (`Gothic2.exe` ≈ 9,040,036 B).

How to get there depends on the store:
- **Where the builds come from:** GD3D11's README links World of Gothic's download page,
  https://www.worldofgothic.de/dl/download_278.htm. Check the current release there, and don't take an exe from
  anywhere else.
- **GOG (DRM-free):** swapping the exe is a downgrade, which is fine. Back the original up (e.g.
  `Gothic2.gog27.exe.bak`), then drop the supported exe into `system/`.
- **Steam:** don't swap the Steam exe. Whether it carries Steam DRM is unverified, and replacing a DRM-wrapped
  exe would strip the DRM. Use THQ Nordic's official Workshop beta instead (game Properties → Betas): it starts
  the game through a Workshop launcher, and Union and plugins install by subscribing to Workshop items. Which exe
  build that branch runs, and whether GD3D11 works on it, isn't verified here.
- Union may already be in the install: `SHW32.DLL` loaded in-process and `saves/<slot>/UnionPlugin*.dat` are
  the tells. GOG's compatibility wrapper (`ddraw.dll`/`dinput.dll`/`dixi.ini`) coexists; GD3D11 replaces the
  `ddraw.dll`, so keep GOG's as `ddraw.gog.dll.bak`.

## Route 1: Daedalus script mods (start here for gameplay)

Items, NPCs, dialogue, quests and AI live in Daedalus scripts. For "add a new item to Gothic 2", start here, and
reach for a C++ plugin only when scripts can't get at what you need.
- The official MDK ships the script sources under `_work/Data/Scripts/` (`Content/` for the game, `System/` for
  the menus). They compile to `.DAT` files in `_work/Data/Scripts/_compiled/`.
- A mod packs its `.DAT`s and assets into a `.mod` volume in `Data/ModVDF/` and adds a `system/<Mod>.ini` whose
  `[FILES]` section names it (`VDF=MyMod.mod`). `GothicStarter_mod.exe` lists and starts it.
- **Ikarus** gives Daedalus scripts raw memory access and engine calls. **LeGo** builds on Ikarus (frame
  functions, engine hooks, views and more).
- **Ninja** loads modular patches, so several script mods can run together without replacing the game's `.DAT`s.
  It supports G1 1.08k_mod and G2 NotR, and it's also on the Steam Workshop.
- With Union installed, its zParserExtender plugin injects Daedalus scripts from `system/autorun/`.

## Route 2: Union plugin (native hooks, most reach)

- A plugin is an x86 DLL that Union loads from `system/autorun/` (create it if missing) or from a `.vdf`/`.mod`
  volume in `Data/`. It installs its own hooks through union-api
  (`Union::CreateHook(SIGNATURE_OF(&oCGame::Render), ...)`).
  - [union-plugin-template](https://github.com/Patrix9999/union-plugin-template) wraps the common hooks as
    `Game_*` callbacks (`Game_EntryPoint`, `Game_Init`, `Game_PreLoop`/`Game_PostLoop`,
    `Game_LoadBegin_*`/`Game_LoadEnd_*`, `Game_Pause`/`Game_Unpause`, ...).
  - Each callback fires only once you uncomment its hook in `src/Plugin.ipp`. They aren't DLL exports.
  - `UnionAPI.dll` belongs in `system/` when the plugin doesn't link Union statically.
- **gothic-api** headers describe the engine classes per build. One define selects the engine
  (`__G1`, `__G1A`, `__G2`, `__G2A`) and namespaces follow (`Gothic_I_Classic`, `Gothic_II_Addon`, …).
  Wrap engine-touched code in `HOOKSPACE(Gothic_II_Addon, GetGameVersion() == Engine_G2A)` so a stray
  DLL just idles in the wrong game.
- Per-frame work: hook `oCGame::Render` (address per engine build; e.g. G2A `0x006C86A0`) or use the template's
  `Game_PreLoop`/`Game_PostLoop`. Talk to the user through `zcon->AddEvalFunc` (console commands), and log
  through `zerr->Message(...)` (zSpy / log file).
- Build: CMake + MSVC x86 (`-A Win32 -T v142` works on VS2019+). With union-plugin-template, the union-api
  submodule's CMake target `union_api_lib` (a compiled library, not header-only) defines `_UNION_API_LIB` for
  you. `#undef min`/`max` after Windows.h inside gothic-api TUs: the macros collide with `std::min`.

## Route 3: renderer-level (GD3D11)

The stock renderer is DX7-era DirectDraw. [GD3D11](https://github.com/kirides/GD3D11) is a community D3D11
renderer for the builds above: unpack its release zip into `system/`. It ships its own `ddraw.dll` + per-engine
DLLs (`system/GD3D11/bin/g1_*.dll`, `g2a_*.dll`) and `UserSettings.ini`. Once loaded (`d3d11.dll`, `dxgi.dll`
in-process) you get a real D3D11 device, HDR chain and depth: enough for ReShade-addon compositing or custom
overlays without fighting DirectDraw.

## Engine facts

- Units **centimeters**, **+Y up**, **left-handed**, +Z is the vob forward ("at") vector.
- In gothic-api's headers: the global `zCCamera::activeCam`, the session camera `zCSession::GetCamera()`
  (`oCGame` derives from `zCSession`), raycasts through `zCWorld::TraceRayFirstHit`, and
  `gameMan->IsGameRunning()` plus the `inLoadSaveGame`/`inLevelChange`/`m_bWorldEntered` flags.
- **Not verified in game yet** (expected behaviour from a plugin that hasn't run):
  - The camera rendering the frame is `zCCamera::activeCam`, and it can differ from the session camera
    (`ogame`/`zCSession::GetCamera()`). `zCAICamera` drives it (`firstPerson` flag at a fixed offset).
  - Vob-bbox traces return box *tops*, so probing under a bridge reports the bridge.
  - `oCGame::Render` also runs on loading screens. Gate per-frame work on `gameMan->IsGameRunning()` plus the
    loading flags above.
- ZenGin **source trees circulate** (a Gothic 1 engine tree, often community-modified, and a Gothic 2 tree with
  `libraries/`+`work/`). These are leaked trees: use them to understand the engine (class layouts, enum values,
  function names), and never paste, ship or link code from them. Don't trust them for retail addresses either;
  confirm in the binary or the gothic-api headers.

## Assets and scripts

- `Data/*.vdf` volumes (`Textures`, `Meshes`, `Anims`, `Sounds`, `Speech*`, `Worlds`, plus `*_Addon.vdf` for
  NotR). Mount them with ZenKit's Python bindings (`pip install zenkit`): `zenkit.Vfs()` + `mount_disk`. API
  quirks: `VfsNode.children` is a property that raises on files, `vfs.find()` matches basenames not paths.
- `.ZTEX` textures: a 36-byte header (`ZTEX`, version, format, width, height, mip count, reference width/height,
  average colour), a 256-entry palette for P8, then the mip chain **smallest first** with no per-mip sizes.
  Derive each size from w/h and the format; the full-size mip is the last block. zenkit-py's `Texture.load` can
  return 0×0 mips; hand-decode the DXT in that case.
- `.MDM` skeletal meshes, `.MDH` model hierarchies (the skeleton; ZenKit's `ModelHierarchy`), `.MAN`
  animations, `.MRM` compiled static meshes, `.ZEN` levels.
- Game logic is **Daedalus** bytecode in `.DAT` files (Route 1). Union plugins can call script functions and
  register new externals for scripts.
- Plugin configs/logs conventionally live beside the exe in `system/`.

## What to scan for

`um scan <gothic folder>` reports engine `zengin` for `system/Gothic.exe`, `Gothic1.exe` or `Gothic2.exe` alone,
or for `system/vdfs32.dll`/`vdfs32g.dll` plus `Data/*.vdf`. Union shows up as `SHW32.DLL`; GD3D11 as
`system/GD3D11/`; SystemPack/player-kit builds leave their own `system/*.ini`.

## Projects

Versions move, so check the current release of each.
- Union: [union-framework](https://gitlab.com/union-framework) (union-api, gothic-api) and
  [union-plugin-template](https://github.com/Patrix9999/union-plugin-template).
- Renderer: [GD3D11](https://github.com/kirides/GD3D11).
- Assets: [ZenKit](https://github.com/GothicKit/ZenKit) and its Python bindings
  [ZenKit4Py](https://github.com/GothicKit/ZenKit4Py).
- Scripts: [Ikarus](https://github.com/Lehona/Ikarus), [LeGo](https://github.com/Lehona/LeGo),
  [Ninja](https://github.com/szapp/Ninja), and the
  [Gothic Modding Community docs](https://gothic-modding-community.github.io/gmc/) (Daedalus, VDFS, Ikarus/LeGo).
- Exe builds: [World of Gothic's download page](https://www.worldofgothic.de/dl/download_278.htm), as linked from
  GD3D11's README.
