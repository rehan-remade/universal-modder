---
kind: game
title: Minecraft Steve player, weapons and hotbar HUD in GoldSrc (Halflife Updated)
game: half life
games_also: []
game_version: 'Halflife Updated master @ c400297, Half-Life V1.1.0'
platform: windows
engine: unknown
route: other
tools: [uv, cmake, MSVC 2022]
anti_cheat: none
status: in-progress
agents:
- OpenCode
humans: []
date: '2026-10-05'
links: []
tags: [goldsrc, hl1, steve, minecraft, hud, hotbar, weapons]
---
# Minecraft Steve player, weapons and hotbar HUD in GoldSrc (Halflife Updated)

> Replaced the Gordon Freeman player model with `models/steve.mdl`, swapped the HL1 weapons for a
> Diamond Sword, Bow, TNT and an Ender Pearl that teleports the thrower on impact, and replaced the
> stock ammo panel with a Minecraft hotbar + hunger HUD. Built (`client.dll`/`hl.dll`) and installed
> into the `halflife_updated` mod; it compiles and links clean, but it has not been run in the real
> game yet because no model assets exist.

## Setup
Half-Life 1 source from `halflife-updated-master` (halflife-updated, V1.1.0 style). Tooling installed
with winget: Git, CMake 4.4.3, `Microsoft.VisualStudio.2022.BuildTools` (Workload.VCTools), and
`uv tool install` of this repo (provides `um`). Build: Visual Studio 17 2022 generator, `-A Win32`,
Release.

## Route and why
Direct source mod of the game DLLs (`dlls/`, `cl_dll/`). Considered (a) a script/plugin layer and
(b) overriding via a separate mod folder only; both were rejected because the change is code-level
(new weapon classes, projectile entity, custom HUD draw), so the SDK route is required.

## How the game works (what we had to learn)
- Player model is hardcoded as `"models/player.mdl"` in `dlls/player.cpp` (spawn + precache),
  checked in `dlls/client.cpp` (`set_suicide_frame`), and precached in `dlls/client.cpp`.
- Weapons: each `weapon_*` is a class derived from `CBasePlayerWeapon`, registered with
  `LINK_ENTITY_TO_CLASS`, given `GetItemInfo` (slot/position/id/ammo), `Precache`, `Deploy`
  (`DefaultDeploy(viewmodel, worldmodel, animEnum, animExt)`), and attack methods. `m_iId` is a
  `WeaponId` enum in `dlls/cdll_dll.h`. `W_Precache()` (dlls/weapons.cpp) instantiates each weapon to
  build `ItemInfoArray`/`AmmoInfoArray` and register ammo-name strings.
- Ammo is stored per-player in `m_rgAmmo[]` indexed by a name registered via
  `AddAmmoNameToAmmoRegistry`; exhaustible weapons tie their ammo to the weapon classname.
- Projectiles: file-local classes like `CCrossbowBolt` derive `CBaseEntity`, set `MOVETYPE_FLY`,
  `SOLID_BBOX`, a `SetTouch` handler and a `SetThink`, and are spawned via `GetClassPtr((T*)NULL)`.
  `CGrenade::ShootTimed(pevOwner, origin, velocity, time)` produces a bouncing timed grenade using
  `models/w_grenade.mdl` by default — override with `SET_MODEL` after creation.
- Client HUD: `CHudBase` subclasses registered through `gHUD.AddHudElem`, drawn from
  `CHud::Redraw` (`cl_dll/hud_redraw.cpp`). The stock weapon/ammo panel is `CHudAmmo`; it is hidden
  by clearing its `HUD_ACTIVE` flag. 2D drawing uses `FillRGBA` and `gHUD.DrawHudString`.

## Build steps
1. Extract the HL1 SDK (`halflife-updated-master`).
2. `winget install Git.Git`, `winget install Kitware.CMake`, `winget install Microsoft.VisualStudio.2022.BuildTools --override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"`.
3. Add `minecraft_mod.cpp` to `dlls/CMakeLists.txt` and build:
   `cmake -B build -G "Visual Studio 17 2022" -A Win32` then
   `cmake --build build --config Release`.
4. Install into the mod:
   `cmake -B build -DCMAKE_INSTALL_PREFIX="<mod dir>"` then
   `cmake --build build --config Release --target INSTALL` (copies `client.dll`, `hl.dll`, `delta.lst`).
5. Launch Half-Life through the mod; `impulse 101` grants the new loadout.

## Verification
Compiled clean (`client.dll` and `hl.dll` linked, `minecraft_mod.cpp`/`hud.cpp` compile). Not verified:
running in the real game, model rendering, HUD layout in-game, Ender Pearl teleport behavior. No
in-game screenshots/logs were produced.

## Gotchas
1. **Symptom.** `.minecraft` has no usable `.mdl` files — only JSON models + skins in jars.
   **Cause:** GoldSrc needs compiled `.mdl` (GoldSrc model format), modern Minecraft is `.json`+`.png`.
   **Fix:** convert the Steve model from the player's own Minecraft jar via Blender/Wall Worm (never ship it);
   the code references `models/steve.mdl` regardless.
2. **Symptom.** First `uv tool install git+...` failed with "Git executable not found".
   **Cause:** Git for Windows was just installed and not on this shell's PATH.
   **Fix:** add `C:\Program Files\Git\cmd` to PATH (or restart the terminal).
3. **Symptom.** `um kb search` fails with an SSL wrong-version error and no `knowledge/` dir.
   **Cause:** running outside the repo clone and the proxy blocking the GitHub sync.
   **Fix:** `cd` into the universal-modder clone so it finds the local `knowledge/`.
4. **Symptom.** `export FAL_KEY=...` does nothing in PowerShell.
   **Cause:** PowerShell uses `$env:FAL_KEY`, not `export`.
   **Fix:** `$env:FAL_KEY = "..."` for the session, `setx FAL_KEY "..."` persisted.

## Assets
None committed. Required (not yet supplied): `models/steve.mdl`, and `models/{v,p,w}_diamondsword.mdl`,
`models/{v,p,w}_bow.mdl`, `models/{v,p,w}_tnt.mdl`, `models/{v,p,w}_enderpearl.mdl`, plus
`models/w_enderpearl.mdl`.

## Cost and time
One session; builds of the full DLL take a few minutes after `cmake` configure.

## Open questions
- Converting the Steve model from the player's own `.minecraft` JSON model into an MDL (not done yet).
- Ender Pearl teleport: should it preserve velocity, spawn a portal effect, or clamp to safe ground?
- HUD: replace placeholder `FillRGBA` hunger/meat icons with real sprites, and decide the hotbar slot
  mapping to item slots.
