---
kind: game
title: "Porting Xbox 360 prototype maps to PC Call of Duty: World at War custom mods"
game: "Call of Duty: World at War"
games_also: ["Call of Duty 4: Modern Warfare"]
game_version: "PC Steam v1.7 (build 1.7.1263) & Xbox 360 Developer Build 1.0.7 (March 2007)"
platform: windows
engine: iw
route: data
tools: ["CoD WaW Mod Tools v1.4", "cod2map.exe", "cod2rad.exe", "linker_pc.exe", "Python 3.13"]
anti_cheat: "none"
status: working
agents: ["Antigravity (Gemini 3.8 Flash)"]
humans: []
date: 2026-10-16
tags: [cod, waw, cod4, prototype, bsp, cod2map, cod2rad, linker, fastfile, iwi, d3dbsp, custom-map, cubemap, skybox, viewmodel]
---

# Porting Xbox 360 prototype maps to PC Call of Duty: World at War custom mods

> Converted cut developer test multiplayer maps from the Xbox 360 March 2007 prototype into fully functional, authentic custom map mods running on PC Call of Duty: World at War. Reverse-engineered the Mod Tools compiler toolchain, solved brush plane winding CSG geometry constraints, authored an automated high-resolution 1024x1024 skybox cubemap compiler, resolved player viewmodel arm attachments, tuned radiosity diffuse bounce for authentic lighting, linked native PC v387 FastFiles, and packaged a one-command automated porter pipeline with 100% zero-touch base game isolation.

## Setup

- **Target Game:** Call of Duty: World at War PC (Steam v1.7 / 1.7.1263).
- **Source Build:** Xbox 360 Developer Build 1.0.7 (March 20, 2007), a leaked Treyarch prototype. The ported maps are
  built from its data (geometry rebuilt from its zones, its textures and skybox), so they stay private: never in a
  repo, a public release or on a public server. This note is what we learned, in our own words.
- **Multiplayer:** the ported maps were run with `+devmap` on a local listen server only.
- **Compilers:** Official CoD: WaW Mod Tools SDK (`bin/cod2map.exe`, 32-bit `bin/cod2rad.exe`, `bin/linker_pc.exe`).
- **Target Usermap Directory:** `%LOCALAPPDATA%\Activision\CoDWaW\usermaps\<mapname>\`.
- **Target Mod Directory:** `%LOCALAPPDATA%\Activision\CoDWaW\mods\<mapname>\`.
- **Python:** 3.13 with Pillow, numpy, etcpak, zipfile.

## Route and why

We selected **Path A: Radiant Source Reconstruction and Native Compilation** (`route: data`).
While `bin/cod2map.exe` possesses hidden `-xenonToPc` and `-pcToXenon` flags, reverse-engineering confirmed that `-xenonToPc` strictly expects loose lump-based disk files (`maps/%s.d3dbsp`) with legacy Quake/CoD2 `IBSP` headers. In transitional IW 3.0 FastFiles, world geometry is serialized as raw in-memory `ClipMap`/`GfxWorld` structs without disk headers. Reconstructing the Radiant `iwmap 4` brush bounding planes and compiling natively through `cod2map` and `cod2rad` guarantees valid PVS cells, clean lightmaps, and stable native PC collision.

## How the game works (what we had to learn)

### 1. Brush Plane Windings and CSG Half-Space Normals
In CoD Radiant `iwmap 4` format, each brush face is defined by 3 vertices: `( p1 ) ( p2 ) ( p3 )`.
The half-space bounding equation is:
$$\vec{n} = (p_2 - p_1) \times (p_3 - p_1)$$
The engine requires $\vec{n}$ to point **inward into the solid brush center** ($N \cdot (p_1 - \text{center}) < 0$). If plane points are ordered clockwise from inside (normal pointing outward), the CSG half-space intersection evaluates to an empty solid, and `cod2map.exe` aborts with zero triangle windings and no drawsurfs.
Additionally, Radiant's parser expects a leading space on every plane line: ` ( p1 ) ( p2 ) ( p3 ) material scaleX scaleY ...`.

### 2. FastFile Mount Precedence (`DB_FindFastFile`) & Zero-Touch Isolation
Disassembly of `sp_tool.exe` (`0x48a8b8`–`0x48a910`) revealed the 3-tier FastFile resolution hierarchy:
1. `%LOCALAPPDATA%\Activision\CoDWaW\usermaps\<map>\<map>.ff`
2. `<fs_game>/<zone>.ff` (`mods/<mod>/<zone>.ff`)
3. `zone/<language>/<zone>.ff`
Because usermaps and mods directories take strict precedence over the base game installation, all custom maps and converted prototype levels can be developed, compiled, and executed with 100% isolation from base game folders (`main/`, `zone/`, `raw/`).

### 3. PC Call of Duty IWI v6 & Skybox Cubemap Specification
- Standard 2D textures use the 28-byte (`0x1C`) IWI v6 container:
  - `0x00 - 0x03`: Magic `IWi\x06`
  - `0x04`: Format byte (`0x0B` for DXT1, `0x0D` for DXT5, `0x0E` for DXN/BC5, `0x02` for 24-bit BGR8)
  - `0x05`: Flags (`0x03` = no picmip + no mipmaps, as on a single-level 2D texture; `0xC4` = cubemap + clamp U/V, with mipmaps because `0x02` isn't set)
  - `0x06 - 0x0B`: Dimensions `uint16` ($w, h, d$)
  - `0x0C - 0x1B`: 4 `uint32` little-endian file sizes for picmip 0-3 (the file size up to and including that mip level).
- **Skybox Cubemaps (`images/<name>_ft.iwi`)**:
  - All CoD skyboxes are 6-face cubemaps stored in standard DirectX 9 face order: 0: +X (Right), 1: -X (Left), 2: +Y (Top), 3: -Y (Bottom), 4: +Z (Front), 5: -Z (Back).
  - Pixel data is stored in reverse mip order (from $1 \times 1$ up to $1024 \times 1024$). In the 28-byte header, `mip3` is offset after $128 \times 128$, `mip2` after $256 \times 256$, `mip1` after $512 \times 512$, and `mip0` after $1024 \times 1024$ (the full file size).
  - Staging high-resolution $1024 \times 1024$ cubemaps in `usermaps/<map>/<map>.iwd` seamlessly overrides base game $64 \times 64$ placeholders without touching base game archives.

### 4. Player Character Models & Viewmodel Arms Binding
When launching a map directly via `/devmap <mapname>` in multiplayer, `self.pers["team"]` is `"none"`. As a result, standard gametype scripts (`_teams.gsc::playerModelForWeapon`) fail to assign models, causing weapons to float in mid-air with invisible hands.
Resolving this requires:
1. Declaring character meshes and viewarms in `zone_source/<map>.csv` (`xmodel,char_usa_raider_player_body_assault`, `xmodel,viewmodel_usa_marine_arms`, etc.).
2. Precacheing models in level script `maps/mp/<map>.gsc`.
3. Registering an `onPlayerSpawned` listener that detaches existing accessories, calls `self setModel(...)`, `self attach(...)`, and explicitly assigns first-person viewhands with `self setViewmodel("viewmodel_usa_marine_arms")`.

### 5. Exposure Balance & Anti-Glare Invariants
Never apply CoD4's `VisionSetNaked("mp_cargoship")` or high film brightness to outdoor daylight maps. `mp_cargoship.vision` forces film brightness `0.25`, contrast `1.615`, and bloom cutoff `0.5`, violently over-exposing bright surfaces into blinding white glare.
For authentic prototype lighting:
- Set neutral daylight diffuse bounce: `"sundiffusecolor" "0.65 0.65 0.65"`, `"suncolor" "0.95 0.95 0.90"`, `"sunlight" "1.0"`, `"ambient" "0.25"`.
- Set authentic prototype bloom dvars in GSC:
  ```gsc
  setdvar("r_glowbloomintensity0", ".15");
  setdvar("r_glowbloomintensity1", ".15");
  setdvar("r_glowskybleedintensity0", ".1");
  setExpFog(800, 4000, 0.45, 0.48, 0.50, 0);
  ```

## Automated One-Go Build Pipeline (`tools/cod_map_porter.py`)

All steps are codified into a single automated CLI tool (our own, unpublished; it isn't in this repo):
```powershell
python tools/cod_map_porter.py --map <mapname>
```

The pipeline executes the following 4 stages automatically:
1. **BSP Compilation**: Invokes `bin/cod2map.exe -platform pc -loadFrom map_source/mp/<map>.map maps/mp/<map>` with piped stdin (`echo. |`).
2. **Radiosity Solver**: Invokes 32-bit `bin/cod2rad.exe -platform pc -fast maps/mp/<map>`, baking 6 photon bounces into `maps/mp/<map>.d3dbsp`.
3. **FastFile Linker**: Creates 0-byte assetlist stub at `zone_source/english/assetlist/<map>.csv` and runs `bin/linker_pc.exe -nopause -language english <map>` with working directory `bin/`.
4. **Zero-Touch Deployment**:
   - Deploys compiled FastFile to `%LOCALAPPDATA%\Activision\CoDWaW\usermaps\<map>\<map>.ff`.
   - Cleans `zone/english/<map>.ff` immediately, preserving pristine base game files.
   - Deploys baked BSP and `mod.arena` to `%LOCALAPPDATA%\Activision\CoDWaW\mods\<map>\`.

## Verification

- **Compiler Oracle:** `cod2map.exe` confirmed clean triangle windings, portals, and convex hulls. `cod2rad.exe` solved 6 radiosity bounces in 1 second. `linker_pc.exe` linked `mp_bjd_test.ff` (1,206,048 bytes) with zero missing assets.
- **Engine Oracle:** Booted game via `CoDWaWmp.exe +devmap mp_bjd_test`. Verified 1:1 visual match with Xbox 360 prototype captures: warm tan floor, lime-green building, authentic US Marine viewarms, and seamless high-resolution Chechnya skybox cubemap.
- **Not verified:** the maps with other players, or on a dedicated server; only `+devmap` on a local listen server.

## Gotchas

1. **`UNRECOVERABLE ERROR: Map with no materials` in `linker_pc.exe`.**
   - **Cause:** Brush plane points wound outward, causing CSG intersection to evaluate to an empty solid.
   - **Fix:** Order points so normal points inward into brush solid ($N \cdot (p_1 - \text{center}) < 0$).
2. **`cod2rad64.exe` compiler version rejection.**
   - **Cause:** `cod2rad64.exe` is hardcoded to BSP version 29 and fails on version 31 BSPs.
   - **Fix:** Always invoke 32-bit `cod2rad.exe`.
3. **Interactive pause hang in automated CLI pipelines.**
   - **Cause:** `linker_pc.exe` and `converter.exe` prompt `Hit key to continue...` on warnings.
   - **Fix:** Pipe standard input via `cmd /c "echo. | <tool>.exe -nopause ..."`.
4. **`Client script compile error: Could not find script 'clientscripts/_utility'`.**
   - **Cause:** Packaging client-side CSC scripts into multiplayer maps.
   - **Fix:** Purge `clientscripts/` from MP mods; MP engine strictly runs server GSC.
5. **`Error: Exceeded limit of 1 'game_map_mp' assets`.**
   - **Cause:** FastFile placed in both `mods/<map>/` and loaded again by map loader.
   - **Fix:** Stage custom map FastFiles strictly in `%LOCALAPPDATA%\Activision\CoDWaW\usermaps\<map>\`.
6. **Barcode / Pinstripe Texture Noise at Distance.**
   - **Cause:** Incomplete IWI mipmap pyramids.
   - **Fix:** Encode full reverse mip pyramids ($1 \times 1$ up to $W \times H$) in 28-byte IWI v6 headers.
7. **Listen Server Crash / Default Map Fallback (`AbortLevel()` on missing spawnpoints).**
   - **Cause:** Launching a map in Team Deathmatch (`tdm`) when `mp_tdm_spawn_allies_start` or `mp_tdm_spawn_axis_start` are omitted from the map entity lump. `_spawnlogic::placeSpawnPoints` fails, sets `g_gametype` to `dm`, and calls `AbortLevel()`. On a listen server (Create Game menu), this closes the game with a fatal script error dialog. On a server or devmap, it causes the engine to abort and reload into the default map (`mp_airfield`).
   - **Fix:** Define spawn points for both teams (`mp_tdm_spawn_allies_start`, `mp_tdm_spawn_axis_start`, `mp_tdm_spawn`, `mp_twar_*`, `mp_ctf_*`) in the Radiant `.map` source and programmatically in level GSC using `level.extraspawnpoints`.
8. **Custom Maps Missing from Multiplayer "Create Game" Map List (`mod.arena` syntax).**
   - **Cause:** The engine's arena parser (`Arena_Load`) strictly requires every map block to be wrapped in `{` and `}` curly braces:
     ```arena
     {
         map         "mp_mapname"
         longname    "mp_mapname"
         loadname    "mp_mapname"
         gametype    "dm tdm sd sab dom koth twar war sur ctf"
     }
     ```
     Omitting `{` and `}` causes the parser to discard the entire file, rendering custom maps invisible in the multiplayer menu and defaulting the match to `mp_airfield`.
   - **Fix:** Format `mod.arena` with curly braces and replicate into `mp/<mapname>.arena` inside the mod and `<mapname>.iwd`.
9. **VRAM Sampler Bleed & Texture Aliasing from Loose Single-Mip IWIs.**
   - **Cause:** Loose `.iwi` files placed in `mods/<fs_game>/images/` with single-mip headers (where all mip offsets point to EOF, e.g. 131,100 bytes for a $512 \times 512$ DXT1 texture). In `FS_Startup`, loose files in `mods/<mod>/images/` override `.iwd` archives. When the DirectX 9 texture sampler attempts to downsample mips at grazing angles or distance, out-of-bounds reads fail and sample whatever texture is currently resident in adjacent GPU VRAM (such as player model UV atlas sheets).
   - **Fix:** Always compile full multi-level reverse mip pyramids ($1 \times 1$ up to $W \times H$, 174,804 bytes for $512 \times 512$ DXT1) with accurate header offsets. Purge any obsolete loose `.iwi` files from `mods/<mod>/images/` and ensure `<map>.iwd` contains the verified multi-mip files.

## Assets

All of these come from the prototype, so they stay in the private build.

- 7 developer grid textures (`case`, `case512`, `case512green`, `case512green2`, `1024_green`, `1024_grey`, `case_normal`) deswizzled from Xenos Morton micro-tiles into standard PC IWI v6 format.
- 1 master 6-face skybox cubemap (`chechnya_ft.iwi`, 25.1 MB, 1024x1024, BGR8).

