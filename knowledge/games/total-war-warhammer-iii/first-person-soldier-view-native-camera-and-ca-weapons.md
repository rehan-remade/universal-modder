---
kind: game
title: "First-person soldier view in Warhammer III battles: a Lua-loaded native DLL, our own camera, engine projectiles and CA's own weapon meshes drawn in D3D11"
game: "Total War: WARHAMMER III"
games_also: []
game_version: "9.0.5.0 (Warhammer3.exe PE stamp 0x6AE2A00B, SizeOfImage 0x0E53A000), Steam 1142710, Windows 11; started from 9.0.4"
platform: windows
engine: native
route: native-hook
tools: ["MSVC x64 (cl, one C file)", "Python (uv): own PFH5 pack reader/writer, RMV2 reader", "Lua 5.1 (compile check)", "Ghidra 12.1.4", "capstone", "pefile", "Blender 5.2 (headless)", "Mod Configuration Tool (MCT)"]
anti_cheat: "none in single-player; the mod turns itself off when cm:is_multiplayer() is true and was only run in single-player custom battles and campaign"
status: working
agents: ["Claude Code (Opus 5.5)", "OpenCode (models not recorded)"]
humans: ["Arekosandoru"]
date: 2026-11-11
links: ["knowledge/games/total-war-warhammer-iii/bigger-units-scale-every-model-including-workshop-mods.md", "knowledge/games/total-war-warhammer-iii/valkia-khorne-subjugation-reusing-archaon-dilemmas.md", "https://github.com/Frodo45127/rpfm"]
tags: [warscape, total-war, fps, first-person, camera, d3d11, present-hook, vtable-copy, lua-loadlib, projectiles, viewmodel, rmv2, nav-grid, mct]
---

# First-person soldier view in Warhammer III battles: a Lua-loaded native DLL, our own camera, engine projectiles and CA's own weapon meshes drawn in D3D11

In a single-player battle, **F6** drops the camera into a soldier's eyes:
- WASD movement with sprint, jump and crouch;
- eight weapon slots (rifle, sword, pistol, repeater, halberd and shield, drakegun, ratling gun, shotgun) with
  aim-down-sights, recoil, magazines and reload;
- melee light/heavy attacks and block;
- the hero's abilities;
- a campaign armory to buy the heavy weapons;
- walls and buildings block movement.

Shots are real engine projectiles fired from script, so hits, deaths and kill counts are the game's own. The
weapon in frame is CA's own 3D mesh for that weapon, drawn by our D3D11 pass inside the swapchain's `Present`.
Verified in game on 9.0.5 (2026-11-02 to 11-04): logs plus window screenshots.

## Setup
- Total War: WARHAMMER III **9.0.5.0**, Steam 1142710, Windows 11, D3D11, single-player only. Work began on
  9.0.4; the 9.0.5 patch moved every address (Gotcha 16).
- Our mod has two parts:
  - a PFH5 pack with 5 Lua scripts and 2 generated DB tables;
  - a native x64 DLL next to the exe, built with MSVC from one C file of about 5.5k lines.
- Optional dependency: Mod Configuration Tool (MCT) for an in-game settings page.
- Tools: our own Python PFH5 reader/writer (layout from RPFM), an RMV2 mesh reader, Blender headless for previews,
  Lua 5.1 for compile checks. Ghidra, capstone and pefile for reverse engineering.

## Route and why
**Route: battle Lua loads our DLL with `package.loadlib`.** Warscape's Lua 5.1 isn't sandboxed (`io`,
`loadfile`, `require` and `package.loadlib` all work), so there's no proxy DLL, injector or loader to install.
The DLL is inert until the battle reaches the `Deployed` phase.

- **Lua ↔ DLL over text files.** A `package.loadlib` function can't return values to Lua in practice (our
  attempts came back `nil`), and the DLL never calls into Lua. So the two talk through small `key=value` or
  one-line text files next to the exe: F6 state, key events, ammo text, ground height, a navigation grid and
  a "lab" tuning file. Lua polls every 50 ms.
- **Camera:** our own camera object. The battle camera manager re-asserts its active camera every frame, so the
  DLL takes the active-camera pointer back every frame and restores the saved one on exit. Copying FOV, near and
  far from the previous camera keeps the projection matching.
- **Hooks are vtable copies, not code patches:** the camera manager's object and the swapchain get a copied
  vtable with one slot replaced (`Present`). Hooks are only installed after `Deployed`.
- **Input:** mouse through Raw Input (wheel included), keyboard through `GetAsyncKeyState`.
- **Shooting stays in the engine:** the DLL gates fire rate, magazine and reload and writes `f` into the key
  file; Lua calls `battle:trigger_projectile_launch(projectile_key, eye, aim_point)`. Penetration comes from
  generated DB rows: cloned projectile rows with a larger `entity_size_cap`.
- **Melee and block** are approximated at unit level. Lua finds an enemy unit in an arc in front of the camera
  and applies `attack_unit` or a damage splash. Block returns HP with `heal_hitpoints_unary`.
- **Weapon in frame:** CA's own weapon meshes (RMV2), converted to our simple mesh and texture files next to the
  exe and drawn in `Present`. A layered-window sprite is the automatic fallback when the files are missing or
  D3D setup fails.
- **Walls:** Lua samples a 65 × 65 grid of 1 m cells around the player. A cell is blocked if
  `battle:is_area_clear(pos, 0, 1, 1)` returns false, or if the height step to a neighbour is over 1.7 m. The DLL
  reads the grid every 100 ms and slides along blocked cells.

Why not alternatives: a script-only camera (`camera:move_to`) stutters and can't take mouse look. A proxy DLL
or injector adds an install step the game doesn't need. Our own projectile physics would lose the engine's hit,
morale and kill logic.

## How the game works (what we had to learn)
**Packs and scripts.**
- PFH5 header is 0x1C bytes. Each index entry is `u32 size, u8 compression flag, NUL-terminated name`, with no
  trailing sentinel or GUID, and file bodies follow in index order. CA's vanilla packs are zstd-compressed
  (flag 1); Workshop packs are often stored raw.
- Script folders by context:
  - `script/_lib/mod/` loads at startup;
  - `script/battle/mod/` in battle;
  - `script/campaign/mod/` in campaign;
  - `script/mct/settings/` is picked up by MCT.
- `Warhammer3.exe` only reads the enabled mod list (`used_mods.txt`) when started from the CA launcher. Started
  directly, it runs vanilla.
- A battle Lua file is limited to **200 locals**. Over that, the file fails to load with nothing useful in the
  log. Keep state in tables and compile-check with Lua 5.1 before packing.

**Battle script API, as observed:**
- Damage and heal (`reduce_hitpoints_unary`, `heal_hitpoints_unary`) work per unit, not per soldier, and apply on
  the next tick. Read HP about one second later to see the change.
- A projectile row with `entity_size_cap = medium` stops on the first infantry model whatever
  `max_penetration` says; `large_*` and up pass through. In our test (120 bullets per type, still targets), the
  vanilla rifle bullet killed 7, a `large_5` clone 10, and a `large_7` clone 23.
- `set_enabled(false)` hides a unit **and** makes it untouchable, and the unit then ignores orders, sometimes
  for good. To hide a model and keep it working, use `set_invisible_to_all(true, false)`.
- `perform_special_ability(key, unit)` and `perform_special_ability_ground(key, pos)` cast a hero's abilities;
  the engine rejects targets that don't fit and says so in the return value.
- `cm:is_multiplayer()` lets campaign scripts switch themselves off in multiplayer.

**Camera internals** (9.0.4/9.0.5; addresses are build-specific, so we describe the shape, not the numbers):
- The battle object holds the camera manager. The manager holds a pointer to the active camera, which is an
  object of the base camera class.
- The camera's vtable has setters for position, look target and up-vector. FOV, near and far are separate
  setters that take their value in `xmm1`; called without it, they write garbage and the frame goes black.
- A working per-frame order: up → position → fov/near/far → target, then write our camera into the manager's
  active slot.
- Validate the camera object by checking several vtable slots against expected functions. The derived manager
  class has a different vtable from the base camera, and checking against the wrong one is an easy mistake.

**D3D11 access.**
- The renderer object holds an interface you can `QueryInterface` for `IDXGISwapChain`. Its vtable lives in the
  system `dxgi.dll`; nothing in the engine wraps or blocks it.
- From `Present` you get the device with `GetDevice` and the back buffer with `GetBuffer(0)`. Create a render
  target view and your own depth buffer once per session, and draw.

**Weapon meshes.** CA weapons are `*.rigid_model_v2` (RMV2, versions 7 and 8) inside `variants*.pack`, with
textures in `variants_dds*.pack`. Our reader takes the first LOD, converts it to a flat vertex/index file plus an
RGBA texture, and keeps everything on the user's machine. These are CA assets: generate them locally from the
player's own install, never ship them.

## Build steps
1. Lua sources → pack: our PFH5 writer packs `mods/<mod>/` into `<mod>.pack` (flags 3) and puts it in
   `<game>\data\`. Enable it in the launcher.
2. DLL: one `cl /LD` build (x64). Copy it next to `Warhammer3.exe`. The loader script in `_lib/mod` calls
   `package.loadlib("<exe folder>\\<dll>", "luaopen_<name>")` with an explicit path.
3. Weapon meshes: run the converter against the player's own `variants*.pack` to write the mesh and texture files
   next to the exe. Without them the sprite fallback is used.
4. Penetration rows: a generator clones the chosen vanilla projectile rows with new keys and a larger
   `entity_size_cap`, and writes the DB tables into the pack.
5. Deploy only with the game closed: the running game locks both the pack and the DLL. Start the game through
   the CA launcher.

## Verification
- **Oracles:** the DLL's own log (`exe: build stamp … MATCH/MISMATCH`, hook installation, `vm: steps QI=0x0
  GetDevice=0x0 GetBuffer=0x0 RTV=0x0`, camera take-overs, nav blocks), the Lua log (`f` events,
  `trigger_projectile_launch` results, HP before and one second after), and window screenshots. Test input was
  scripted. Saves and settings were backed up before each run and restored by hash afterwards.
- **Verified in game on 9.0.5 (2026-11-02 to 11-04):**
  - F6 enter/exit with HUD, cursor and input restored;
  - camera and movement; all 8 slots as 3D CA meshes plus the shield, with ADS, recoil and reload;
  - F6 off/on releases and recreates all D3D resources;
  - a second battle in the same process;
  - melee from the camera (HP 0.890 → 0.870 at 2.9 m);
  - rifle penetration (numbers above);
  - abilities, and enemy aggro released on exit;
  - armory purchase surviving a full restart;
  - stopping at Altdorf's walls and passing through open gates.
- **Offline:** 17 pytest tests for the tools, a Lua 5.1 compile of every script, and a WARP test host that draws
  the same mesh code into a PPM file without the game.
- **Not verified:**
  - animation smoothness;
  - penetration of pistol, volley and ratling rows;
  - closed gates and real cliffs;
  - aggro hold for its full 40 s;
  - armory rank refusal (offline only);
  - window resize while in first person;
  - any game version after 9.0.5. A MISMATCH only logs; it doesn't stop the DLL.
- Two features from 9.0.4 (driving the hero's body along, hiding the hero model) are switched off on 9.0.5,
  because their addresses weren't found again.

## Gotchas
1. **The game closes silently before or during battle load.** **Cause:** hooks installed at DLL load.
   **Fix:** stay inert until the battle phase is `Deployed`.
2. **Crash at startup after adding logging.** **Cause:** CRT calls or a thread started in `DllMain`. **Fix:**
   log with plain WinAPI (`CreateFileW`/`WriteFile`) and start no background threads.
3. **Crash after leaving a battle for the campaign.** **Cause:** Lua dropped the library, unloading a DLL whose
   `Present` hook was still live. **Fix:** pin the DLL for the process lifetime (`GetModuleHandleEx` with
   `PIN`) and re-attach on the next battle.
4. **"D3D is blocked by an engine wrapper" (`E_NOINTERFACE`, 0x80004002).** **Cause:** a typo. We asked for
   `IID_IDXGIFactory` instead of `IID_IDXGISwapChain`. **Fix:** copy IIDs from `dxgi.h`/`d3d11.h` in the Windows
   Kits, never from memory.
5. **Hangs while looking for the swapchain.** **Cause:** scanning process memory for it. **Fix:** don't; take it
   from the renderer with `QueryInterface`, or from the `Present` hook.
6. **The camera snaps back to the RTS view every frame.** **Cause:** the manager re-asserts its own active camera.
   **Fix:** write your camera pointer every frame (`re-took over` in the log is normal) and restore the saved one
   on exit.
7. **Black frame after setting FOV.** **Cause:** the FOV, near and far setters read their value from `xmm1`.
   **Fix:** call them with the float actually in `xmm1` (declare the argument as `float`, not through a generic
   pointer call).
8. **A battle script stops working, with nothing in the log.** **Cause:** over 200 locals in one Lua file.
   **Fix:** move state into tables and compile with Lua 5.1 first.
9. **The mod doesn't load at all.** **Cause:** the exe was started directly, so it ignored the mod list.
   **Fix:** start through the CA launcher.
10. **Keyboard input dead in game.** **Cause:** keyboard registered through Raw Input alongside the game.
    **Fix:** poll keys with `GetAsyncKeyState`; keep Raw Input for the mouse.
11. **The hidden unit stopped obeying orders.** **Cause:** `set_enabled(false)` also makes the unit untouchable
    and order-deaf. **Fix:** `set_invisible_to_all(true, false)`.
12. **Melee hit a unit 66 m away.** **Cause:** the range check was dropped whenever our unit was in melee.
    **Fix:** in a melee scrum take the nearest enemy in any direction, but never beyond reach + 10 m, because
    unit centres in a fight are up to 10 m apart.
13. **HP "didn't change" after a scripted hit.** **Cause:** unit-level damage applies on the next tick, and
    0.5 % of a unit is less than one soldier. **Fix:** read HP about one second later; use larger test damage.
14. **A changed setting has no effect.** **Cause:** battle Lua reads settings only at battle start. **Fix:**
    start a new battle; re-entering F6 isn't enough.
15. **Our pack reader showed names that didn't match their contents.** **Cause:** an off-by-one in our own index
    parser (we assumed a 32-byte header and name-first entries). **Fix:** check that the index ends exactly
    where data starts, and that the sizes add up to the file size.
16. **Hooks never install after a game patch** (`renderer not ready … Present not hooked`). **Cause:**
    hard-coded RVAs moved. **Fix:** re-capture all of them in one session with byte signatures, vtable-slot
    scans and global-pointer scans; update the expected PE stamp and SizeOfImage.
17. **13 of 17 addresses from decompiler output were wrong.** **Cause:** Ghidra folded extra offsets into
    expressions. **Fix:** confirm every address against the disassembly, not the pseudocode.
18. **No `.pdata` section, so function bounds can't be found.** **Cause:** the exception directory lives inside
    another section. **Fix:** find it through the PE Data Directory, not by section name.
19. **Copying the new pack or DLL fails ("being used by another process").** **Cause:** the running game locks
    both. **Fix:** deploy only with the game closed; keep the last good copy for rollback.
20. **A screenshot "shows" that the cursor is hidden.** **Cause:** `CopyFromScreen` never captures the cursor.
    **Fix:** check `GetCursorInfo` (`CURSOR_SHOWING`) instead.
21. **Synthetic input does nothing in fullscreen.** **Fix:** run test sessions windowed (1920 × 1080).
22. **Sprites came out with blue cuffs instead of red.** **Cause:** Pillow gives RGB, the DLL wanted
    premultiplied BGRA. **Fix:** convert explicitly.
23. **Behaviour changes when other mods are enabled.** **Cause:** other camera or overlay mods hook the same
    things (camera, Raw Input, `Present`, `version.dll`). **Fix:** debug with only this mod enabled.

## Open questions
- Per-soldier hits and block. The script API is unit-level; a native path would be needed.
- Driving the hero's body along with the camera, and hiding only the hero's model, on 9.0.5 and later.
- Resize handling for the D3D11 render target while in first person.
