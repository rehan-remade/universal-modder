# Call of Duty IW Engine (IW 3.0 / Treyarch T4)

Covers **Call of Duty 4: Modern Warfare** and **Call of Duty: World at War** (PC Steam/retail x86), single-player, co-op/Zombies, and custom multiplayer.

**Online.** Mods are for single player, solo Zombies, a co-op lobby you host with friends who agreed, or a
multiplayer server you run (`devmap`, a private match, your own dedicated or CoD4X server). Official multiplayer
used PunkBuster, and Plutonium T4 servers run their own anti-cheat: never join public servers with modified game
files or a proxy DLL (T4M) loaded.

**Identify.** Executables `CoDWaW.exe`, `CoDWaWmp.exe`, `iw3sp.exe`, `iw3mp.exe`. File formats: Fastfiles (`zone/<lang>/*.ff`), archive packages (`main/*.iwd`), loose folders (`raw/`, `mods/<name>/`), and mod tools (`bin/linker_pc.exe`, `cod2map.exe`, `cod2rad.exe`, `CoDWaWRadiant.exe`).

---

## Engine Evolution: Why World at War (T4) Differs from Other CoD Titles

The "IW Engine" is not a static platform; it diverged significantly with each release. Techniques that work in World at War will fail in earlier or later titles:

| Engine / Game | Fastfile Version | GSC Script Format | Distinct Architecture |
|---|---|---|---|
| **IW 3.0** (*CoD4: Modern Warfare*) | `5` on PC (`1` on Xbox 360) | Plain text RawFile | SP campaign (`iw3sp.exe`) & MP (`iw3mp.exe`). Mods stored in `<GameRoot>/Mods/<name>/`. Reference mod: `Mods/ModWarfare/`. |
| **Treyarch T4** (*CoD: World at War*) | Container `387` (`0x183`) | Plain text RawFile | Forked from IW 3.0. Merged SP/Co-op (`CoDWaW.exe`). Mods moved to `%LOCALAPPDATA%/Activision/CoDWaW/mods/<name>/`. Added Nazi Zombies, 4-player co-op, limb gibbing/crawlers (`self.has_legs`), flamethrower charring masks (`clothcharr`), and Patch 1.4 script routing (`patch.ff`). |
| **IW 4.0** (*Modern Warfare 2*) | `276` (`0x114`) | zlib-compressed text RawFile | RawFiles carry a compressed length; signed zones (`IWff0100`) are RSA-checked, not encrypted. |
| **Treyarch T5** (*Black Ops 1*) | `473` (`0x1D9`) | Plain text RawFile | Memory partitions (zones 0-4), Lua UI integration, SndBank resident audio. |
| **Treyarch T6+** (*Black Ops 2+*) | Variable | **Compiled Bytecode** | GSC scripts are compiled into binary bytecode rather than raw text. Cannot be extracted with text regex; requires a bytecode decompiler. |

> [!IMPORTANT]
> This guide and `um fastfile` specifically target **Treyarch T4 (World at War)** and **IW 3.0 (Call of Duty 4)**. Never assume FastFile formats or plain-text script structures carry over to IW 4.0+ or Black Ops 2+.


---

## 1. Filesystem & Loading Precedence
Engine resolves assets via `FS_Startup` in this priority order (from the field notes: mod files over base files were tested, not every level):
1. **Loose files in `mods/<ModName>/`**: Highest priority. Overrides everything.
2. **Mod Archives (`mods/<ModName>/*.iwd`)**: Searched in reverse alphabetical order, so `z_*.iwd` overrides `a_*.iwd`. Standard ZIP format.
3. **Mod Fastfile (`mods/<ModName>/mod.ff`)**: Compiled binary assets (compiled menus, particle effects `.efx`, compiled shaders).
4. **Base game `raw/` and `main/`**: Stock loose assets.
5. **Base game IWDs (`main/iw_00.iwd` - `iw_13.iwd` in CoD4, `iw_27.iwd` in WaW)**: Stock textures, materials, and sounds.
6. **Base game Fastfiles (`zone/<language>/*.ff`)**: Core level and common binaries (`code_post_gfx.ff`, `common.ff`, `<map>.ff`, `patch.ff`).

> [!NOTE]
> **Mod Installation Directories:**
> * **Call of Duty 4 (IW 3.0)**: Mods live in `<GameRoot>/Mods/<ModName>/`. CoD4 ships with an official reference mod: `Mods/ModWarfare/`.
> * **Call of Duty: World at War (T4)**: Mods live in `%LOCALAPPDATA%/Activision/CoDWaW/mods/<ModName>/` (Windows UAC redirection out of Program Files). Installing mods to `<GameRoot>/mods/` in WaW often fails or gets quarantined by Windows VirtualStore.

> [!TIP]
> **Zero-Linker Live Iteration:** GSC/CSC scripts, IWI textures, weapons, and sound aliases can be placed loose or inside an `.iwd` in `mods/<ModName>/`. They load immediately without recompiling `mod.ff`. Only compile Fastfiles when shipping or adding binary effects (`.efx`), custom materials, or global precaches.

---

## 2. GSC & CSC Scripting Architecture

### Server GSC vs. Client CSC
* **Server GSC (`maps/`)**: Authoritative logic: damage calculations, AI navigation, score allocation, round tracking, and spawner management.
* **Client CSC (`clientscripts/`)**: Client-side cosmetics: particle attachments, dynamic light flickers, and eyeball glow billboards. Runs locally on the client to avoid consuming server entity slots (`MAX_GENTITIES`).

### Compiler & Runtime Invariants
* **Strict Single-Pass Compiler**: The engine halts map loading with `Server script compile error: unreachable code` if an unconditional `return;` is placed before existing statements. Always wrap early returns inside conditional guards:
  ```gsc
  if( IsDefined( level.mod_active ) && level.mod_active )
  {
      return;
  }
  ```
* **Singleplayer Function Scope Trap**: In Singleplayer and Nazi Zombies, `iprintln` and `iprintlnbold` are **global functions** (`iprintlnbold(msg);`), **NOT** entity member methods (`player iprintlnbold(msg);`). Calling them on `self` or a player entity fails silently.
* **PrecacheItem Rule**: Never call `PrecacheItem()` on weapons not included in the map's level fastfile. Precache misses cause fatal server script aborts during map initialization. Weapons must either be embedded in `mod.ff` via `zone_source/mod.csv` or dynamically verified against `level.zombie_weapons`.

---

## 3. 2D HUD & Renderer Rules

* **The FontScale Underflow Bug (`fontScale < 1.0`)**: In the IW3 2D renderer, `HudElem.fontScale` does not support floating point values less than `1.0` (such as `0.85` or `0.92`). Passing $< 1.0$ causes an internal UV texture projection underflow, rendering text 10× larger across the entire screen. Always keep `fontScale >= 1.0` and manage width/padding with coordinate placement.
* **Strict 31–32 Client `HudElem` Budget**: The engine allocates a hard limit of ~31 to 32 active `HudElem` structs per client. Exceeding this budget causes subsequent HUD elements to drop silently.
* **No String Auto-Wrapping**: `SetText()` does not wrap lines. Multi-line UI elements must be split into separate `HudElem` instances with explicit `y` coordinate offsets.
* **Layering & Depth**: Use `elem.sort = 1;` for backgrounds, `elem.sort = 2;` for borders, and `elem.sort = 3;` for foreground text.

---

## 4. Nazi Zombies Gameplay Systems

### Map Family Redirection (Treyarch Patch 1.4+)
Patch 1.4 redirected map startup scripts in `zone/<language>/patch.ff`:
* **Nacht der Untoten**: Calls `maps/_zombiemode_prototype::main()` and spawners in `_zombiemode_spawner_prototype.gsc`.
* **Verrückt**: Calls `maps/_zombiemode_asylum::main()` and spawners in `_zombiemode_spawner_asylum.gsc`.
* **Shi No Numa & Der Riese**: Call `maps/_zombiemode::main()` and spawners in `_zombiemode_spawner.gsc` (Der Riese uses `_zombiemode_blockers_new.gsc`).
* **Rule**: Universal zombie mods must patch and compile all 3 master scripts and all 3 spawner scripts, or maps under `patch.ff` will revert to stock vanilla logic.

### Health, Caps, and Powerups
* **Zombie Health Formula**:
  * Round 1: 150 HP (`level.zombie_vars["zombie_health_start"]`).
  * Rounds 2–9: Linear scaling: `150 + 100 * (round - 1)`.
  * Round 10+: Exponential scaling: `health = int(health * 1.1)`.
* **Entity & AI Limits**: Hard cap of 24 concurrent active zombies (`zombie_max_ai = 24`). Engine has a strict 1,024 entity limit (`MAX_GENTITIES`); T4M's README lists asset-pool and memory increases, not an entity one.
* **Powerup Drop Escalation**: Cumulative score threshold `(players * 500) + 2000`, escalating by 14% (`*= 1.14`) each drop, capped at 4 drops per round maximum.
* **Pack-a-Punch Hook**: Machine checks for `level.zombie_include_weapons[current_weapon + "_upgraded"]`. Upgraded variants must strictly follow the `<weapon>_upgraded` suffix naming convention.

---

## 5. Toolchain & Map Compilation (Radiant / Cod2Map)

* **Working Directory (CWD)**: run `linker_pc.exe` from `<GameRoot>\bin\`, but `cod2map.exe` and `cod2rad.exe` from the game root `<GameRoot>\` (from `bin\` they miss `main/` and write a hollow 840-byte BSP). Piped stdin (`echo. | linker_pc.exe ...`) is mandatory to avoid CLI hangs on asset warnings.
* **Concave Winding Assertion (`tris_mergeconcave.cpp:1120`)**:
  * Symptom: `cod2map.exe` aborts with `ASSERTION: w->ptCount <= ARRAY_COUNT( indices )`.
  * Cause: Complex concave brushes or high-density terrain windings during BSP merge pass.
  * Fix: Split concave brushes into convex primitives in Radiant, or pass `-keeplightmapcuts` / `-nomerge` flags to `cod2map.exe`.
* **Memory Limits & T4M**: Complex custom maps with dense texture packs need the [T4M](https://github.com/iAmThatMichael/T4M) proxy (`d3d9.dll`; maintained fork: [T4M Enhanced](https://github.com/JBShady/T4M-Enhanced)). Its README lists the raised pools (Image 4096, Material 4096, FX 600, Loaded Sound 2400, XModel 1500, Weapon 320) and a larger memory limit; check the current release.

---

## 6. FastFile (.ff) Binary Layout & Decompilation

In retail Call of Duty: World at War (T4) and Call of Duty 4 (IW 3.0) on PC, FastFiles (`.ff`) are standard zlib streams with a 12-byte header:
* **Header Layout**:
  * Bytes 0–7: Container magic (`IWffu100` for an unsigned zone, `IWff0100` for a signed one, whose data is RSA-checked; PC zones are unsigned).
  * Bytes 8–11: 4-byte little-endian version number (`5` for CoD4, `387` for WaW; OpenAssetTools' zone constants agree).
  * Byte 12+: Standard zlib compressed payload stream (`0x78 0x01` / `0x78 0x9C`).
* **RawFile Serialized Layout**:
  Unlike later titles which compile scripts into bytecode, **World at War and CoD4 store GSC and CSC scripts as 100% human-readable plain text source code** inside `ASSET_TYPE_RAWFILE` records:
  ```text
  [0xFFFFFFFF] (4B sentinel)
  [Length]     (4B uint32 little-endian)
  [0xFFFFFFFF] (4B sentinel)
  [Name\0]     (null-terminated ASCII path, e.g. maps/nazi_zombie_factory.gsc\0)
  [Payload]    (Length bytes of raw source code or text)
  ```
  `um fastfile` finds RawFiles by scanning for this layout rather than parsing the whole zone. It only reads
  unsigned zones and never writes or signs one. What it dumps is the game's own code: keep it outside any repo.

### Using `um fastfile`
The toolkit includes built-in inspection and extraction commands for FastFiles:
```bash
# List all GSCs, CSCs, menus, and configs inside a FastFile
um fastfile list zone/english/patch.ff
um fastfile list zone/english/nazi_zombie_factory.ff

# Extract all raw scripts to a directory
um fastfile dump zone/english/patch.ff -o extracted_patch/
um fastfile dump zone/english/nazi_zombie_factory.ff -o der_riese_scripts/
```

## 7. IWI v6 Texture Conversion (`um iwi`)

Call of Duty games utilize Infinity Ward Image (`.iwi`) containers for textures. World at War and CoD4 use **version 6**:
* **Header Structure (28 bytes)**, as in [OpenAssetTools](https://github.com/Laupetin/OpenAssetTools)' `IwiTypes.h`:
  * Bytes 0–3: Magic `IWi\x06` (ASCII `IWi` + version byte `0x06`).
  * Byte 4: Format identifier (`0x01` RGBA8, `0x02` RGB8, `0x03` LA8, `0x04` L8, `0x05` A8, `0x0B` = DXT1 opaque/1-bit alpha, `0x0C` = DXT3, `0x0D` = DXT5 interpolated alpha, `0x0E` = DXN).
  * Byte 5: Flags (`0x01` no picmip, `0x02` no mipmaps, `0x04` cubemap, `0x08` volume, `0x40`/`0x80` clamp U/V; e.g. `0x03` for a single-level HUD image).
  * Bytes 6–7: Width (`uint16_t` little-endian).
  * Bytes 8–9: Height (`uint16_t` little-endian).
  * Bytes 10–11: Depth (`uint16_t`, 1 for 2D textures).
  * Bytes 12–27: File size for picmip 0–3 (`uint32_t[4]` little-endian): entry *i* is the file size up to and including mip level *i*, so entry 0 is the whole file.
* **Reverse Mipmap Ordering**:
  Crucially, mipmaps in IWI v6 files are stored in **reverse order**: the smallest mipmap is stored first immediately following the 28-byte header, and the full-resolution base image (mip 0) is stored last at the end of the file. A mipmapped file holds the whole chain down to 1x1, and levels under 4x4 still take one DXT block.

### CLI Usage:
```bash
# Convert a custom PNG texture into game-ready IWI v6 format:
um iwi png2iwi hud_custom_icon.png images/hud_custom_icon.iwi --format dxt5 --mips

# Decode an existing in-game IWI v6 texture back to PNG for inspection/editing:
um iwi iwi2png images/weapon_usa_colt45.iwi raw_textures/colt.png
```

## 8. Weapon File Editing (`um weapon`)

Call of Duty weapons are defined in text files using a single-backslash delimited dictionary format starting with `WEAPONFILE\`. Over 300 properties configure ammunition, damage, viewmodels, recoil, spread, and sound effects. The files in the Mod Tools' `raw/weapons/` are Treyarch's and Infinity Ward's data: write edits to your mod's copy (`-o`), keep copies of raw files out of any repo, and ship changes as a diff or a build step that runs `um weapon` on the player's own files.

### Key Weapon Attributes:
* `damage` / `minDamage`: Base hit point damage and minimum damage at maximum falloff range.
* `damageType`: `bullet`, `grenade`, `splash`, `fire`, etc.
* `clipSize` / `maxAmmo` / `startAmmo`: Magazine capacity and reserve pools.
* `fireTime`: Interval between rounds (seconds).
* `projectileModel`: Swaps hitscan bullets for simulated physics projectiles (e.g., `projectile_usa_m9a1_riflegrenade`).

### CLI Usage:
```bash
# Inspect all weapon stats or query a specific key:
um weapon get weapons/sp/colt
um weapon get weapons/sp/colt damage

# Modify specific stats and output to a mod folder:
um weapon set weapons/sp/colt damage=250 clipSize=14 -o mods/MyMod/weapons/sp/colt_modded

# Clone a weapon with presets (e.g. explosive ammo or upgraded stats). --explosive copies the rifle-grenade setup of
# Treyarch's colt_dirty_harry (the Zombies last-stand pistol), so its projectile model and trail effect must be loaded:
um weapon clone weapons/sp/colt mods/MyMod/weapons/sp/colt_explosive --damage 500 --clip 14 --explosive

# Compare differences between two weapon definitions:
um weapon diff weapons/sp/colt mods/MyMod/weapons/sp/colt_explosive
```

## 9. Field notes, credits and links

* Field notes: `knowledge/games/call-of-duty-world-at-war/` (Mod Tools, fastfiles, IWDs and Zombies; the Xbox 360
  prototype notes) and `knowledge/games/call-of-duty-4-modern-warfare/` (CoD4 against WaW).
* [OpenAssetTools](https://github.com/Laupetin/OpenAssetTools): dumps and links IW3 and T4 zones (RawFile and GfxImage
  among the supported asset types) and reads and writes IWI images; the zone versions, RawFile struct and IWI header
  above match its source. Reach for it when `um fastfile` (rawfiles only) isn't enough.
* [T4M](https://github.com/iAmThatMichael/T4M) (archived) and [T4M Enhanced](https://github.com/JBShady/T4M-Enhanced):
  World at War limit raises through `d3d9.dll`.
* [CoD4x](https://github.com/callofduty4x/CoD4x_Server): a community server (and client, installed when you join one
  of its servers) for CoD4 multiplayer. For servers you run; single-player mods don't need it.
* The official Mod Tools for each game (`linker_pc.exe`, `cod2map.exe`, Radiant, Asset Manager): their `raw/` files are
  Treyarch's and Infinity Ward's, so they stay out of repos.


