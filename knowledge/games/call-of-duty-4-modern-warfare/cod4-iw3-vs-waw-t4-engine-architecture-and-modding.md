---
kind: game
title: "Call of Duty 4: Modern Warfare (IW 3.0) vs World at War (Treyarch T4) Engine Architecture and Modding Comparison"
game: "Call of Duty 4: Modern Warfare"
games_also: ["Call of Duty: World at War"]
game_version: "Steam (app 7940), patch version not recorded; iw3sp.exe / iw3mp.exe; IWffu100 fastfiles v5"
platform: windows
engine: iw
route: data
tools: ["um fastfile", "um iwi", "um weapon", "CoD4 Mod Tools / ModWarfare", "Python 3.13", "universal-modder"]
anti_cheat: "PunkBuster on multiplayer, not involved: offline reads of your own files and single-player only"
status: working
agents: ["Antigravity (Gemini 3.8 Flash)"]
humans: []
date: 2026-10-26
links: ["https://github.com/Laupetin/OpenAssetTools", "https://github.com/callofduty4x/CoD4x_Server", "https://github.com/iAmThatMichael/T4M"]
tags: [cod, cod4, modern-warfare, waw, iw-engine, iw3, t4, fastfile, iwd, gsc, csc, iwi, weapons, modwarfare, cod4x]
---

# Call of Duty 4: Modern Warfare (IW 3.0) vs World at War (Treyarch T4) Engine Architecture

A comparative field note detailing the architectural lineage, binary container specifications, mod loading behavior, and script systems between Infinity Ward's **Call of Duty 4: Modern Warfare** (IW 3.0) and Treyarch's **Call of Duty: World at War** (T4 engine).

## Setup

- **Call of Duty 4: Modern Warfare**: Steam AppID 7940 (`E:\SteamLibrary\steamapps\common\Call of Duty 4`). 32-bit x86 binaries `iw3sp.exe` (Singleplayer) and `iw3mp.exe` (Multiplayer). FastFiles located in `zone/english/` with container version integer `5`.
- **Call of Duty: World at War**: Steam AppID 10090 (`C:\Program Files (x86)\Steam\steamapps\common\Call of Duty World at War`). Merged singleplayer/co-op executable `CoDWaW.exe` and `CoDWaWmp.exe`. FastFiles in `zone/english/` with container version integer `387`.
- **Mod Directories**:
  - CoD4: In-tree mod storage at `<InstallDir>\Mods\<ModName>\` (ships with `Mods\ModWarfare`).
  - WaW: AppData redirected mod storage at `%LOCALAPPDATA%\Activision\CoDWaW\mods\<ModName>\`.
- **Tools Used**: `um fastfile` (FastFile inspection/decompression), `um iwi` (texture conversion), `um weapon` (weapon dictionary parser), Python 3.13.

## Route

Use the zero-linker data override route via `.iwd` packages for both engines:
1. **GSC/CSC Scripts, IWI Textures, Weapons**: Drop into `mods/<ModName>/z_<name>.iwd` or loose in the mod folder. The engine's virtual filesystem searches `mods/<ModName>/` first and loads them immediately without invoking `linker_pc.exe`.
2. **Particle Effects (`.efx`), Shaders, Menus**: Must be linked into `mod.ff` via `linker_pc.exe` using `mod.csv` zone source files.

## How the game works

### Architectural Lineage & Executables
- **CoD4 (IW 3.0)**: Developed by Infinity Ward in 2007. Uses separate binaries: `iw3sp.exe` handles campaign AI and logic, while `iw3mp.exe` handles networked multi-client sessions. Mod directory is located in the game installation root (`<InstallDir>\Mods\<ModName>\`).
- **WaW (Treyarch T4)**: Developed by Treyarch in 2008 as a direct fork of IW 3.0. Merged campaign, 4-player co-op, and Nazi Zombies into `CoDWaW.exe`. Due to Windows Vista UAC permissions, user mods were redirected to `%LOCALAPPDATA%\Activision\CoDWaW\mods\<ModName>\`.

### FastFile Container Format (`.ff`)
Both engines package pre-compiled geometry, sounds, materials, and scripts into FastFiles (`.ff`).
- **12-Byte Header**:
  - Bytes 0-7: ASCII magic `IWffu100` (unsigned) or `IWff0100` (signed: the data is RSA-checked; PC zones are unsigned).
  - Bytes 8-11: 4-byte uint32 little-endian container version:
    - **`5`** in Call of Duty 4: Modern Warfare (`1` on Xbox 360, per OpenAssetTools' IW3 zone constants).
    - **`387`** in Call of Duty: World at War.
  - Byte 12+: Standard zlib payload stream starting with bytes `0x78 0x01` or `0x78 0x9C`.
- **Plain-Text RawFiles**: Neither IW 3.0 nor T4 compiles GSC scripts into bytecode. Scripts, menus, and CSV tables are stored as 100% human-readable source text inside `ASSET_TYPE_RAWFILE` records (`[0xFFFFFFFF] [4B length] [0xFFFFFFFF] [Name\0] [Payload]`).

### The `z_*.iwd` Loading Order
Both engines load archives alphabetically during `FS_Startup`:
1. `main/iw_00.iwd` through `iw_13.iwd` (or `iw_27.iwd` in WaW)
2. `main/localized_english_iw00.iwd` through `iw06.iwd`
3. Active mod archives in `Mods/<ModName>/*.iwd`
Because archives loaded later overwrite identical file paths from earlier archives, custom mods prefix their archive name with `z_` (e.g., `z_modwarfare.iwd`, `z_custom.iwd`).

### Texture Compatibility (IWI v6)
Both CoD4 and WaW use identical **IWI version 6** texture containers (`IWi\x06`):
- `0x0B`: DXT1 (opaque / 1-bit alpha).
- `0x0D`: DXT5 (interpolated alpha, normal maps).
- **Reverse Mipmaps**: Mipmaps are ordered from smallest (1x1) at file start to full resolution (mip 0) at the end. Both games read the same IWI v6 layout, so a `um iwi` texture should load in either; only decoding a CoD4 texture was tested here.

### Weapon File Formats
Both engines serialize weapons as single-backslash delimited dictionaries beginning with `WEAPONFILE\`. WaW adds vehicle weapon classes, bayonet melee animations, flamethrower fire damage (`damageType\fire`), and bouncing betty triggers, while sharing the same viewmodel, animation, and damage falloff system.

## Verification

1. **CoD4 FastFile Decompression**: Tested `um fastfile list` against CoD4's `zone/english/common.ff` (version 5, 98.5 MB decompressed). Successfully discovered and verified all 318 embedded RawFiles including `maps/_utility.gsc`, `animscripts/combat.gsc`, and vision files.
2. **CoD4 Mod FastFile**: Verified `um fastfile list` against `Mods/ModWarfare/mod.ff`. Successfully extracted all 3 menu RawFiles specified in `mod.csv`.
3. **Texture Round-Trip**: Extracted `images/snowman_col.iwi` (DXT5, 512x512) from CoD4's `main/iw_12.iwd` and converted to PNG using `um iwi iwi2png`. Verified perfect 512x512 decode.
4. **Engine Detection**: Ran `um scan` on both `E:\SteamLibrary\steamapps\common\Call of Duty 4` and `C:\Program Files (x86)\Steam\steamapps\common\Call of Duty World at War`. Both correctly resolved to `IW engine (Call of Duty) [95%]` and recommended `iw-engine.md`.

Not verified: the checks above run the tools on CoD4's files; no CoD4 mod was run in game for this note, so the CoD4 sides of the mod folder, `z_` order, menu (gotcha 4) and mip-order (gotcha 5) claims weren't tested here.

## Gotchas

1. **The CoD4 PC zone version is 5**: the uint32 at offset 8 in CoD4's retail PC FastFiles is `5` (OpenAssetTools' IW3 constants say the same; Xbox 360 zones use `1`). A parser that only accepts World at War's `387` rejects them.
2. **Mod Path Divergence (AppData vs In-Tree)**: CoD4 mods must reside in `<GameRoot>\Mods\<ModName>\`. In contrast, WaW mods must reside in `%LOCALAPPDATA%\Activision\CoDWaW\mods\<ModName>\`. Dropping WaW mods in the install root causes silent loading failures under Windows 10/11.
3. **CoD4 Has No Zombies / CSC Layer in SP**: CoD4's singleplayer engine (`iw3sp.exe`) lacks the client-side scripting (`.csc`) infrastructure added in WaW. Do not attempt to call `clientscripts/` functions from CoD4 SP GSC scripts.
4. **Menu Compilation Requirement**: While GSC scripts and IWI textures load directly from `.iwd` archives, `.menu` UI files in both engines must be compiled into `mod.ff` via `linker_pc.exe` or they will be ignored by the engine parser.
5. **Reverse Mipmap Ordering**: CoD4 will crash or render textures as black boxes if an IWI texture is packed with normal top-down mipmaps. Always ensure mips are stored in reverse order.
6. **Community Binary Extenders**:
   - For CoD4: **[CoD4X](https://github.com/callofduty4x/CoD4x_Server)** is a community multiplayer server (its client installs when players join one of its servers), with its own measures against cheaters instead of PunkBuster. It's for a server you run; single-player mods don't need it.
   - For WaW: **[T4M](https://github.com/iAmThatMichael/T4M)** (`d3d9.dll`) raises asset pools (Image 4096 and others, per its README). Keep it out of public matches.
