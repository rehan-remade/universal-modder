---
kind: game
title: "Portalcraft: real Minecraft inside Portal 2 (passthrough mod)"
game: "Portal 2"
games_also: ["Minecraft Java Edition"]
game_version: "Portal 2 (Steam, build 10090, D3D9, 32-bit) + ReShade 6.8.0 add-on build; Minecraft Java 26.3 + Fabric Loader 0.19.5 + Fabric API 0.161.0+26.3, JDK 25 (Temurin 25.0.4.1+1), Windows 11"
platform: windows
engine: source
route: passthrough
tools: ["ReShade 6.8 add-on API (32-bit add-on)", "Fabric Loader + Fabric API (Loom 1.18, JDK 25)", "MSVC x86 (portable)", "hl2sdk-portal2 headers", "SourceAutoRecord offset tables", "um win (WinDrive) for test input"]
anti_cheat: "VAC on online co-op only: Portal 2 is launched with -insecure (VAC off) and ReShade's d3d9.dll is placed in the game folder only for the session, then removed"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["@griffdog21"]
date: 2026-10-05
links: ["games/gta-v/minecraft-passthrough.md"]
tags: [mashup, passthrough, shared-memory, depth-compositing, reprojection, camera-prediction, reshade-addon, vscript, netvars, fabric, mixin, advancements, installer]
---

# Portalcraft: real Minecraft inside Portal 2 (passthrough mod)

> Real Minecraft Java 26.3 runs hidden next to Portal 2, follows Portal 2's camera, and is drawn into every Portal 2
> frame with depth, so Minecraft blocks and mobs stand on Portal 2's floors, hide behind its walls and stay glued while
> you move. The Portal 2 player builds with Minecraft blocks, fights Minecraft mobs (their damage reaches Portal 2's
> health), pushes them through Portal 2's portals, and earns Portal-themed Minecraft advancements. Verified in the real
> games with automated test sessions (add-on screenshots, logs, test hooks) and by the human playing the campaign;
> 294-299 fps at 2560x1440 on the test PC. Shipped as a small installer that downloads everything else from official
> sources on the player's PC.

## Setup
- **Portal 2:** Steam, build 10090, D3D9 renderer (`bin\shaderapidx9.dll`), 32-bit `portal2.exe`. Launched by the
  mod's launcher with `-applaunch 620 -insecure -novid +sv_cheats 1` (cheats: `hurtme` needs them; a side effect is
  that Portal 2's Steam achievements don't unlock in those sessions).
- **ReShade 6.8.0, add-on build**, 32-bit DLL taken out of the official installer (never run): its zip payload is
  found from the end-of-central-directory record of `ReShade_Setup_6.8.0_Addon.exe`. Placed as `Portal 2\bin\d3d9.dll`
  plus a two-line `Portal 2\ReShade.ini` that points ReShade's base path at the mod's own folder (config, log, shader
  cache, the `.addon32` all live there).
- **Minecraft Java 26.3** (unobfuscated: no remapping), **Fabric Loader 0.19.5**, **Fabric API 0.161.0+26.3**, built
  with **Loom 1.18** on **JDK 25**. In production it starts as `KnotClient` with the Mojang version JSON's libraries,
  Fabric's profile libraries, the client jar, mods in `<gameDir>\mods`, a fixed offline username, `--proxyHost
  127.0.0.1 --proxyPort 9` (no web calls) and `-Dmcmash.scene=host`.
- The add-on is plain C++17 against ReShade's `include/` headers (MSVC, x86, `/MT`), about 400 KB.

## Route and why
**Passthrough** (two unmodified games side by side, one mod in each, talking over local shared memory), like the
GTA V note. Porting content (Minecraft-like blocks/mobs as Source entities) can't give real Minecraft: redstone, mob AI,
crafting, the inventory UI, advancements. Embedding was impossible (no Minecraft "library"). Portal 2 itself has no
SourceMod-style plugin route for single player that can also composite pixels, so the Portal 2 half is a **ReShade
add-on** (game memory access + an effect that runs every frame with access to the back buffer and depth) instead of a
Source plugin. Portal 2's own **VScript** (`script ...` through `ClientCmd`) does the in-world parts: solid boxes for
Minecraft blocks, health, velocity.

## How the game works (what we had to learn)
**Portal 2 side**
- **DLL search path:** Portal 2 loads `shaderapidx9.dll` with an altered search path, so a `d3d9.dll` next to
  `portal2.exe` is never loaded. It has to be in `bin\`.
- **Interfaces** (all via `CreateInterface`): `VClient016` (`GetAllClasses` vtable 8), `VClientEntityList003`
  (`GetClientNetworkable` 0, `GetClientEntity` 3, `GetHighestEntityIndex` 6), `VEngineClient015` (`ClientCmd` 7,
  `Con_IsVisible` 11, `GetLocalPlayer` 12, `IsInGame` 25, `IsDrawingLoadingImage` 27, `GetLevelNameShort` 53,
  `IsPaused` 86), `EngineTraceClient004` (`TraceRay` 5), `VModelInfoClient004` (`GetModel` 1, `GetModelName` 3).
  `ClientModeShared` hooks: `OverrideView` (vtable 18) gives the `CViewSetup` (origin, angles, 4:3-based fov, near and
  far), `CreateMove` (24) the `CUserCmd` (buttons at offset 36: `IN_ATTACK` 1, `IN_USE` 1<<5, `IN_ATTACK2` 1<<11).
- **Net vars by name, never hard-coded:** walk the `ClientClass` list, recurse through `RecvTable`s (`RecvProp` is 60
  bytes on 32-bit, `DPT_DataTable` = 6). Used: `CPortal_Player` `m_iHealth`, `m_fFlags` (bit 0 on ground),
  `m_vecVelocity[0]`, `m_bIsHoldingSomething`; `CProp_Portal` `m_vecOrigin`, `m_angRotation`, `m_bActivated`,
  `m_bIsPortal2` (orange), `m_hLinkedPortal` (handle & 0xFFF = entity index); any entity `m_nModelIndex` (a short),
  `m_nRenderMode`. `IClientNetworkable` sits at entity + 8 (`GetClientClass` vtable 2).
- **The camera on screen is often one frame old:** with the user's settings 70-80 % of presented frames were drawn with
  the previous `OverrideView` camera. Read the real one per frame from the vertex-shader constants (ReShade
  `push_constants`, the view-projection in `c8..c11`) and match it to a history of hooked cameras.
- **Depth:** standard D3D9 depth, 0 at the near plane (7 units) to 1 at far (28400); ReShade needs
  `DepthCopyBeforeClears=1`, and MSAA off (the add-on asks for a non-MSAA swap chain).
- **Level geometry for Minecraft:** BSP v21 lumps. Brushes with `SOLID|WINDOW|GRATE|PLAYERCLIP|MONSTERCLIP` (world model
  plus static `func_brush`/`func_wall`) are voxelised onto the 32-unit grid with a per-map shift that puts most floors
  on block edges; only the surface shell becomes Minecraft barrier blocks. Toxic goo is `CONTENTS_WATER` (0x20) brushes.
  Floors and walls made of static props aren't in brushes: `TraceRay` with a `TRACE_EVERYTHING` filter that hits no
  entities finds them (down-traces for floors, a point test at mob height for walls) and Minecraft fills them in.
- **Units:** 32 Source units = 1 block, Source (x east, y north, z up) -> Minecraft (x, z, -y); every Portal 2 map
  gets its own region 4096 blocks apart; Minecraft's world was made taller with a data-pack `dimension_type` override.
- **Things Portal 2 can do for you through `ClientCmd`:** `hurtme N` (needs `sv_cheats 1`), `script GetPlayer()...`
  (`SetVelocity` for flying and slime bounces, `SetHealth` for heals and creative), `r_drawviewmodel 0/1` (hide the
  portal gun while building). Invisible solid boxes for Minecraft blocks: `prop_dynamic` with `solid 2`,
  `rendermode 10`, sized with `SetSize`; a `logic_auto` with `OnLoadGame -> Kill` keeps saves clean.

**Minecraft 26.3 side**
- Unobfuscated Mojang names; input is SDL3 (scancodes, keycodes, modifier bits 0x0001 shift / 0x0040 ctrl / 0x0100 alt;
  mouse buttons 1 left, 2 middle, 3 right). GPU readback through the `GpuBuffer` API (colour, depth, and the hand/HUD
  layer as a separate pass).
- The camera is forced in a `Camera` mixin (pose + fov) before the view matrices are built; the HUD class is `Hud`
  (`extractCrosshair`), the first-person hand `GameRenderer.renderItemInHand`.
- Advancements are plain data-pack JSON (`criteria` / `display` / `requirements`; titles can be plain strings, the tab
  background is a texture id); code-awarded ones use `minecraft:impossible` and `PlayerAdvancements.award`.
- Game rules were renamed in 26.x (`natural_health_regeneration`, `fall_damage`, `spawn_mobs`...): a wrong name only
  shows as "Incorrect argument" in the log.

## Build steps
1. Portal 2 add-on: hook `OverrideView` + `CreateMove`, read net vars, publish the camera (and a predicted camera, see
   Gotchas) into `Local\...` shared memory; read Minecraft's frames (triple-buffered colour + depth + overlay) from
   another mapping; composite in a ReShade effect (`.fx`) per pixel: reproject Minecraft's pixel to the shown camera,
   depth-test against Portal 2's depth, then the HUD layer on top.
2. Minecraft mod: follow the camera, publish frames after the level pass (before the hand clears depth), turn Portal 2
   input into key mappings / SDL events, build the barrier geometry from the `.bsp`, forward damage.
3. Launcher: place ReShade's two files -> start Minecraft hidden and wait for its "running" status file -> start Portal
   2 through Steam -> when Portal 2 exits, ask Minecraft to save and quit, take the two files out again.
4. Installer for other people: a ~0.4 MB zip (scripts + the mod jar + the add-on + the effect) that downloads Temurin,
   Minecraft (Mojang version JSON, sha1-checked libraries and assets), Fabric (meta profile) and ReShade (sha256-pinned)
   and makes the mod's logo / loading screens on the player's PC from their own Minecraft jar.

## Verification
- **Stage oracles first:** a fake Portal 2 camera drove Minecraft; a gold pillar landed within ~1 px of its analytic
  projection; Minecraft's depth matched the game's own raycast (5.5000 vs 5.5000 blocks).
- **In the real games:** scripted sessions (WinDrive input + an add-on screenshot that works in exclusive fullscreen) in
  a test room map and campaign levels, with test hooks in the mod (`!throw pig|item|tnt` at a linked portal, `!goo`,
  `!status`, `!slime on/off`, `!pushmode`, `!peaceful`, `!achsnap`/`!achrestore` so tests leave the player's world as
  it was). Logged: entities carried through portals, landings (height, speed, damage), damage reaching Portal 2
  (`fall took 30.0 health`), heals, achievements, goo kills. Frame rate read from `cl_showfps` crops.
- **The human played** the campaign between iterations and reported what felt wrong (stutter, keys, cut-off outlines).
- **The release itself:** the installer's quiet mode installed the shipped zip into a separate folder (every download
  hash-checked), then a script ran that copy's own launcher: production Minecraft (`KnotClient`) and Portal 2 started,
  a campaign level showed Minecraft composited (add-on screenshot), and after Portal 2 was closed the launcher quit
  Minecraft and no ReShade file was left in Portal 2's folder. That run caught Gotcha 17.
- **Not verified:** the latest outline fix (near-to-far ray walk + overscan) only in a 2560x1440 simulation and quick
  strafes, not a long session; Portal 2 physics props colliding with Minecraft blocks (they don't); the installer on a
  second PC (only on the dev PC, into a separate folder).

## Gotchas
1. **ReShade never loads.** **Cause:** `d3d9.dll` next to `portal2.exe`. **Fix:** `bin\d3d9.dll`.
2. **Minecraft stutters / slides while you move.** **Cause:** Minecraft's picture is a few ms old and Portal 2's
   presented frame often uses the previous camera. **Fix:** read the presented camera from shader constants, predict
   the camera ahead by the measured delay (EMA of shown-time minus rendered-for time) and render Minecraft for that,
   then reproject per pixel with depth.
3. **Mob outlines cut off while strafing (always the trailing side).** **Cause:** the reprojection's search started at
   the "infinitely far" pixel; where that hits nothing (P2 walls aren't in Minecraft's depth) it stopped, losing a strip
   as wide as the parallax. A 16-step march in 1/depth still skipped it for anything past ~6 blocks. **Fix:** a coarse
   min-depth tile pass (1/16 res) bounds how near anything on the ray's track can be, then walk the ray near-to-far in
   about 1-px steps and take the first crossing (with a thickness test to skip "behind an outline").
4. **Outlines cut at the screen edges while turning.** **Cause:** prediction error pushes the picture past the edge.
   **Fix:** Minecraft renders with tan(fov/2) x 1.08 (overscan); colour sampled bilinear, depth point.
5. **The portal gun fired with every Minecraft click.** **Cause:** swallowing `WM_*BUTTON*` isn't enough, Portal 2 gets
   buttons another way. **Fix:** clear `IN_ATTACK`/`IN_ATTACK2` in the `CreateMove` hook while building.
6. **"E opens the inventory" broke picking up cubes.** **Fix:** a "smart E": holding something -> use; a view trace
   (100 units) hitting a cube/turret/button (class or model name) -> set `IN_USE` for ~100 ms; else the inventory.
7. **"moved wrongly" (Minecraft refused the stand-in's moves).** **Cause:** the server player collides with barrier
   walls the Portal 2 player passes through (portals, gaps). **Fix:** `noPhysics` only while the server handles move
   packets (mixin).
8. **Achievements and stats reset every launch.** **Cause:** the dev launcher picks a random `PlayerNNN` name, so a new
   UUID each time (the singleplayer inventory survives anyway via the host data). **Fix:** a fixed `--username`.
9. **No fall damage at all.** **Causes:** `Player.causeFallDamage` returns early for flying players (the stand-in always
   flies), and the `fall_damage` rule was off. **Fix:** compute Minecraft's fall formula from Portal 2's landing (height
   and impact speed, so slow funnel rides don't count) and `hurtServer` with the fall source, rule on.
10. **Entities "slid" across the room when carried through a portal.** **Cause:** `teleportTo` sends a teleport the
    client interpolates. **Fix:** re-create the entity at the exit (as cross-dimension travel does: `restoreFrom`,
    remove the old one first so the same UUID can be added again).
11. **Things bumped into walls at portals.** **Fix:** while a pair is linked, lift the barrier blocks right behind each
    portal's oval (and tell the floor probes not to refill them); restore on close, at world close, and from a list
    in the world folder after a crash.
12. **Lava hurt 20 times a second.** **Cause:** health was reset every tick, so Minecraft's invulnerability frames never
    applied. **Fix:** let vanilla compute the hit, forward the health it took, mirror Portal 2's health back.
13. **Menus closed as soon as they opened.** **Cause:** the key that opened the menu, still held, counted as a fresh
    press inside it. **Fix:** ignore keys held when a menu opens until released.
14. **Mouse wheel didn't scroll menus.** **Cause:** ReShade's wheel delta is already in notches; dividing by 120 again.
15. **Minecraft quit while Portal 2 was minimized.** **Cause:** the watchdog used Portal 2's frame heartbeat. **Fix:**
    check that `portal2.exe` exists.
16. **Test runs left traces in the player's world** (a floor block turned to slime, achievements, XP, a supply drop).
    **Fix:** every test hook that changes the world has an undo (`!slime off`, `!achrestore` with XP, game mode and
    difficulty restore), and campaign-level Survival tests trigger real rewards: undo them.
17. **The installed copy wouldn't start:** `Could not find or load main class
    net.fabricmc.loader.impl.launch.knot.KnotClient`. **Cause:** Fabric's meta profile
    (`/v2/versions/loader/<mc>/<loader>/profile/json`) gives `sha1` and `size` for every library except
    `net.fabricmc:fabric-loader` itself (checked 2026-10-05: loader 0.19.5 for 26.3), and the installer read "no hash"
    as "nothing to fetch". **Fix:** when an entry has no hash, download `<artifact url>.sha1` from maven.fabricmc.net
    and verify against that. Test launching an installed copy, not just installing it.

## Assets
No Minecraft or Portal 2 asset is shipped. The logo (Minecraft font, white concrete + stone textures, a drawn portal),
the icon (an isometric grass block), the main-menu panel and four loading screens (a test-chamber wall of Minecraft
blocks with a blue and an orange portal) are generated with System.Drawing on the player's PC from their own Minecraft
client jar during install. No fal.

## Cost and time
About two days of agent sessions with the human play-testing in between (2026-10-03 to 10-05).

## Open questions
- Portal 2 physics objects (cubes, turrets) pass through Minecraft blocks: `prop_dynamic` boxes resized with `SetSize`
  collide with the player but not with VPhysics. A runtime brush or physics-shadow trick is still open.
- Minecraft things seen through a portal aren't drawn (it would need a second Minecraft render from the portal's
  virtual camera).
- Moving panels and doors aren't solid for Minecraft mobs (only static geometry is mirrored).
