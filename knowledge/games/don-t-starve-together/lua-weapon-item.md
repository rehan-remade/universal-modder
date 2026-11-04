---
kind: game
title: 'Official Lua mod API: a new weapon item'
game: Don't Starve Together
games_also: []
game_version: 'Steam app 322330 (exact build not yet pinned); Windows 11 10.0.26200'
platform: windows
engine: native
route: loader-api
tools:
- Don't Starve Mod Tools (TextureConverter, autocompiler, ModUploader)
- Python + Pillow
- image_gen.py (local A1111/ComfyUI text-to-image adapter)
anti_cheat: 'none found by um scan; official Lua mod API + Steam Workshop are the sanctioned route'
status: in-progress
agents:
- Claude Code (deepseek-v4-pro)
humans: []
date: '2026-11-05'
links:
- https://github.com/kleientertainment/ds_mod_tools
- https://forums.kleientertainment.com/forums/forum/79-dont-starve-together-mods-and-tools/
tags: [klei, lua, loader-api, mod-tools, workshop, weapon, item, tex, atlas, inventory-icon]
---

# Official Lua mod API: a new weapon item

> Don't Starve Together (DST) has a first-party Lua mod API, and this is the correct route: a `mods/<name>/`
> folder of `.lua` + Klei `.tex`/`.xml` assets that the game loads itself and that publishes through Steam
> Workshop. `um scan` currently mislabels DST as an "unknown native engine" with only a proxy-DLL hook route —
> the real, sanctioned path is `loader-api`. End-to-end ship is still in progress; this note records the API
> facts and the environment so the next agent does not fall back to native hooking.

## Setup
- Windows 11 (10.0.26200). DST is Steam app **322330**. `um scan "Don't Starve Together"` resolves it to
  `D:\SteamLibrary\steamapps\common\Don't Starve Together`; a second copy exists at
  `C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Together` (active path to confirm before shipping).
- **Don't Starve Mod Tools** (free on Steam) is required and provides `TextureConverter.exe`, `autocompiler.exe`,
  `ModUploader.exe`. Not yet installed here (pending a human Steam subscribe).
- User config and logs live under `Documents\Klei\DoNotStarveTogether\`; the error log is
  `client_log.txt` there. Workshop content lands in `<SteamLibrary>\steamapps\workshop\content\322330`.
- Mods are dropped into `<install>\mods\` and enabled in the in-game Mods menu.

## Route and why
`loader-api` via the official Lua API (`api_version = 10`). `um scan` reports engine "Unknown native engine" and
only suggests proxy-DLL + function hooks (MinHook/Ghidra/x64dbg) — that is a dead end for ordinary mods. DST is
a Klei custom engine (not Unity/Unreal) with embedded Lua; the game itself loads `modinfo.lua` + `modmain.lua`
+ prefabs. This route is official, works for all clients (`all_clients_require_mod`), and has no anti-cheat
concern, so native hooking is both unnecessary and the wrong tool.

## How the game works (what we had to learn)
- **`modinfo.lua`** (required): `name`, `description`, `author`, `version`, `api_version = 10` (current),
  `dst_compatible = true`, `client_only_mod = false` (gameplay mods), `all_clients_require_mod = true`,
  `server_filter_tags`, `icon_atlas = "modicon.xml"`, `icon = "modicon.tex"`, `priority`.
- **`modmain.lua`** (required): declare `PrefabFiles = { "myweapon" }`, register recipes with
  `AddRecipe(name, { Ingredient(...) }, RECIPETABS.WAR, TECH.SCIENCE_TWO, nil... , atlas, image)`, localize with
  `STRINGS.NAMES`, `STRINGS.CHARACTERS.GENERIC.DESCRIBE`, `STRINGS.RECIPE_DESC`.
- **Prefabs** (`prefabs/<item>.lua`): `Prefab("name", fn, assets)`; server logic must be gated behind
  `if TheWorld.ismastersim then ... end`. Components: `weapon` (`SetDamage`, `SetOnAttack(weapon, attacker,
  target)`), `tool`, `edible`, `finiteuses` (`SetMaxUses`/`SetUses`/`SetOnFinished`), `burnable`
  (`Ignite`/`IsBurning`), `inventoryitem` (`atlasname`), `equippable`.
- **Assets**: `.tex` is the Klei texture (converted from PNG by `TextureConverter.exe`, which also emits the
  `.xml` atlas/UV file). Item icons go in `images/inventoryimages/<item>.tex` + `.xml`. Custom animation is
  compiled from Spriter `exported/` output into `anim/<name>.zip` by `autocompiler.exe`; v1 can instead reuse a
  vanilla `bank`/`build` (e.g. `spear`) and skip autocompiler.

## Build steps
1. Create `mods/<name>/` with `modinfo.lua`, `modmain.lua`, `prefabs/<item>.lua`,
   `images/inventoryimages/<item>.png`.
2. `TextureConverter.exe <item>.png` → emits `<item>.tex` + `<item>.xml`; same for `modicon`.
3. (Optional, custom animation) Spriter → `autocompiler.exe` scans `exported/` → `anim/<name>.zip`.
4. Drop the folder into `<install>\mods\`, enable it in the in-game Mods menu.
5. Test: open the console and run `c_give("<prefab>")`; watch `client_log.txt` for errors.

## Verification
- **Not yet verified end-to-end** (this note predates the ship; `status: in-progress`). Planned oracle: the
  Mods menu shows the mod and it enables without error; `client_log.txt` stays error-free; `c_give("<prefab>")`
  puts the item in the inventory; the weapon hits and applies its effect.
- Already verified here: install paths and the `um scan` fingerprint above; the `client_log.txt` location; the
  `.tex`/`.xml`/`anim.zip` format chain and `api_version = 10` from official docs and Klei forums.

## Gotchas
1. **Mod won't enable / crashes on enable.** Cause: missing `modicon.tex`+`.xml`, or a wrong `api_version`.
   Fix: run TextureConverter on a `modicon.png`, and keep `api_version = 10`.
2. **Item is blank in the inventory or errors.** Cause: the `.tex`/`.xml` pair is missing or the
   `AddRecipe` atlas/image path and the prefab's `inventoryitem.atlasname` do not agree. Fix: convert the PNG and
   point both at `images/inventoryimages/<item>.xml` + `<item>.tex`.
3. **Prefab name collision overwrites a vanilla item.** Cause: reusing a stock prefab name. Fix: unique prefix
   (`fire_sword`, never `sword`).
4. **Server logic never runs / desyncs clients.** Cause: gameplay code outside the `TheWorld.ismastersim` guard
   while `all_clients_require_mod` is set. Fix: gate server-side logic in `if TheWorld.ismastersim then ... end`.
5. **Chinese text renders as garbage.** Cause: Lua files saved in a non-UTF-8 encoding. Fix: save every `.lua`
   as UTF-8.
6. **`client_only_mod` set for a gameplay mod.** Cause: misreading the field. Fix: keep it `false` unless the mod
   is purely client-side (UI/visuals); gameplay mods need it `false` + `all_clients_require_mod = true`.

## Assets
- Local generation, no fal key: an `image_gen.py` adapter drives a local text-to-image backend. Current target
  backend is ComfyUI running MOSS-Image GGUF (Q4) for icon art, with the prompt style
  "game item icon, centered, single object, clean background". (A1111 + SDXL at 512px ran but quality was
  rejected; the plan is to move to ComfyUI + MOSS-Image.)

## Open questions
- Install Don't Starve Mod Tools (pending human Steam subscribe) to get `TextureConverter`/`autocompiler`/
  `ModUploader`.
- Confirm which install path (C: vs D:) is the active one the mod must drop into.
- The end-to-end ship (a fire-sword item) and the `client_log.txt`/`c_give` oracle are still to be run.
- Whether MOSS-Image GGUF is usable at 4 GB VRAM (RTX 3050 Laptop) within acceptable wall-clock.
