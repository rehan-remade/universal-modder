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
- Don't Starve Mod Tools (Steam app 245850; autocompiler, ModUploader)
- Python + Pillow
- image_gen.py (the author's own local A1111/ComfyUI text-to-image adapter, not published)
anti_cheat: 'none found by um scan; official Lua mod API + Steam Workshop are the sanctioned route. Online co-op and PvP game: an item mod belongs in a world or server you run, with friends who agreed'
status: in-progress
agents:
- Claude Code (deepseek-v4-pro)
humans: []
date: '2026-11-05'
links:
- https://github.com/kleientertainment/ds_mod_tools
- https://kleiforums.com/forums/forum/79-dont-starve-together-mods-and-tools/
- https://kleiforums.com/forums/topic/140881-documentation-new-recipe-system-functions-other-info/
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
- **Multiplayer:** DST is online co-op and PvP. An item mod runs on the world's server, and
  `all_clients_require_mod = true` means every player who joins needs it too (Workshop mods download on join). So
  this is for a world or dedicated server you run, with friends who agreed to it. It can't reach someone else's server
  from the client, and this note doesn't try. Publishing to the Workshop is public, so ask your human first.
- **Don't Starve Mod Tools** (a free tool in the Steam library, app 245850) is required and provides
  `autocompiler.exe`, which runs `TextureConverter.exe` for you, and `ModUploader.exe`. Not yet installed here
  (pending the human).
- The game's own Lua is the real reference: `data\databundles\scripts.zip` in the install (`scripts/modutil.lua`,
  `mods.lua`, `prefabs/`, `components/`). Read it there and keep it out of repos.
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
- **`modinfo.lua`** (required): `name`, `description`, `author`, `version`, `api_version = 10` (current:
  `MOD_API_VERSION` in `scripts/mods.lua`; `api_version_dst` takes over if set), `dst_compatible = true`,
  `client_only_mod = false` (gameplay mods), `all_clients_require_mod = true`, `server_filter_tags`,
  `icon_atlas = "images/modicon.xml"`, `icon = "modicon.tex"` (the icon is looked up next to the atlas), `priority`.
- **`modmain.lua`** (required): declare `PrefabFiles = { "myweapon" }`, register recipes with
  `AddRecipe2(name, { Ingredient(...) }, GLOBAL.TECH.SCIENCE_TWO, { atlas = atlas, image = image }, { "WEAPONS" })`
  (the older `AddRecipe` with `RECIPETABS.WAR` prints a deprecation warning from `modutil.lua`), localize with
  `GLOBAL.STRINGS.NAMES`, `GLOBAL.STRINGS.CHARACTERS.GENERIC.DESCRIBE`, `GLOBAL.STRINGS.RECIPE_DESC` (keys are the
  upper-case prefab name). `modmain.lua` runs in its own environment: `Ingredient`, `Prefab`, `Asset` and `TUNING`
  are in it, while `STRINGS` and `TECH` need `GLOBAL.`
- **Prefabs** (`prefabs/<item>.lua`): `Prefab("name", fn, assets)`. Follow the shape of the game's own weapons
  (`prefabs/spear.lua`, `prefabs/nightsword.lua`): create the entity with `AddTransform`, `AddAnimState` and
  `AddNetwork`, set what clients need too (bank, build, tags), call `inst.entity:SetPristine()`, then
  `if not TheWorld.ismastersim then return inst end`, and add the server-side components after that. Components:
  `weapon` (`SetDamage`, `SetOnAttack(fn)` with `fn(inst, attacker, target)`), `tool`, `edible`, `finiteuses`
  (`SetMaxUses`/`SetUses`/`SetOnFinished`), `burnable` (`Ignite`/`IsBurning`), `inventoryitem` (`atlasname`),
  `equippable`.
- **Assets**: `.tex` is the Klei texture and the `.xml` beside it is the atlas/UV file. `autocompiler.exe` makes both:
  for every PNG under a mod's `images\` and `bigportraits\` it runs the tools' `png` compiler
  (`compiler_scripts/image_build.py`), which calls `TextureConverter.exe` for the `.tex` and writes the `.xml` itself.
  `TextureConverter.exe` alone takes flags (`--format bc3 -i ... -o ...`) and writes no `.xml`. Item icons go in
  `images/inventoryimages/<item>.tex` + `.xml`. Custom animation is compiled from Spriter `exported/` output into
  `anim/<name>.zip` by `autocompiler.exe` too; v1 can instead reuse a vanilla `bank`/`build` (e.g. `spear`, plus
  `swap_spear` for the held sprite) and skip the animation step. That reuse names the game's own files in the
  player's install, and nothing of Klei's goes in the mod.

## Build steps
1. Create `<install>\mods\<name>\` with `modinfo.lua`, `modmain.lua`, `prefabs/<item>.lua`,
   `images/inventoryimages/<item>.png` and `images/modicon.png`.
2. Run `mod_tools\autocompiler.exe` from the Mod Tools folder: it writes `<item>.tex` + `<item>.xml` next to each PNG
   under `images\`, `modicon` included.
3. (Optional, custom animation) Spriter → `autocompiler.exe` scans `exported/` → `anim/<name>.zip`.
4. Enable the mod in the in-game Mods menu.
5. Test in a world you host: open the console and run `c_give("<prefab>")`; watch `client_log.txt` for errors.

## Verification
- **Not yet verified end-to-end** (this note predates the ship; `status: in-progress`). Planned oracle: the
  Mods menu shows the mod and it enables without error; `client_log.txt` stays error-free; `c_give("<prefab>")`
  puts the item in the inventory; the weapon hits and applies its effect.
- Already verified here: install paths and the `um scan` fingerprint above; the `client_log.txt` location.
- Read, not run: the API facts above come from the game's scripts, and the `.tex`/`.xml`/`anim.zip` chain from the
  source of Klei's `ds_mod_tools` (`autocompiler`, `png`, `image_build.py`), which may differ in details from the
  Steam build of the tools.

## Gotchas
Nothing has been built yet, so none of these were hit here: they come from the docs and the game's scripts.
1. **Mod won't enable.** Cause: an `api_version` above 10 fails to load ("in the future"), one below 10 or missing is
   flagged "Old API!", and a `modinfo.lua` without `name`, `description`, `author` or `version` fails too
   (`scripts/modindex.lua`). Fix: keep `api_version = 10` and fill those in. A missing `modicon` isn't the cause: the
   game logs a warning, clears the icon and carries on.
2. **Item is blank in the inventory or errors.** Cause: the `.tex`/`.xml` pair is missing or the
   `AddRecipe2` atlas/image and the prefab's `inventoryitem.atlasname` do not agree. Fix: convert the PNG, point both
   at `images/inventoryimages/<item>.xml` + `<item>.tex`, and declare the pair with `Asset("ATLAS", ...)` and
   `Asset("IMAGE", ...)`.
3. **Prefab name collision overwrites a vanilla item.** Cause: reusing a stock prefab name. Fix: unique prefix
   (`fire_sword`, never a stock name like `spear`).
4. **Clients crash or desync while the host looks fine.** Cause: gameplay code and server-side components run on
   clients too, because they come before the `TheWorld.ismastersim` check. Fix: use the shape in "Prefabs" above, with
   `inst.entity:AddNetwork()` and `SetPristine()` before the check and server logic after it.
5. **Chinese text renders as garbage.** Cause: Lua files saved in a non-UTF-8 encoding. Fix: save every `.lua`
   as UTF-8.
6. **`client_only_mod` set for a gameplay mod.** Cause: misreading the field. Fix: keep it `false` unless the mod
   is purely client-side (UI/visuals); gameplay mods need it `false` + `all_clients_require_mod = true`. The two flags
   are mutually exclusive (`scripts/modindex.lua` warns).
7. **`autocompiler.exe` skips your mod.** Cause: it only looks for mods in `..\..\Don't Starve Together\mods` (plus
   the Don't Starve and Beta folders) relative to `mod_tools\`, and for PNGs only under `images\` and `bigportraits\`
   (`src/app/autocompiler/main.cpp`, `png.txt`). Fix: keep Mod Tools in the same Steam library as the copy you're
   modding, and the PNGs under `images\`.

## Assets
- Art and sound in the mod must be your own or generated. Don't copy Klei's `anim/*.zip`, `images/*.tex` or sound
  banks into the mod or a Workshop upload.
- Local generation, no fal key: an `image_gen.py` adapter (the author's own, not published) drives a local
  text-to-image backend. Current target backend is ComfyUI running MOSS-Image GGUF (Q4) for icon art, with the prompt
  style "game item icon, centered, single object, clean background". (A1111 + SDXL at 512px ran but quality was
  rejected; the plan is to move to ComfyUI + MOSS-Image.) `um comfy` in this repo also talks to a local ComfyUI.

## Open questions
- Install Don't Starve Mod Tools (pending the human) to get `autocompiler`/`ModUploader`.
- Confirm which install path (C: vs D:) is the active one the mod must drop into: Steam tracks one install per app,
  so it's the library that holds `appmanifest_322330.acf`. Mod Tools has to sit in that same library (gotcha 7).
- The end-to-end ship (a fire-sword item) and the `client_log.txt`/`c_give` oracle are still to be run.
- Whether MOSS-Image GGUF is usable at 4 GB VRAM (RTX 3050 Laptop) within acceptable wall-clock.
