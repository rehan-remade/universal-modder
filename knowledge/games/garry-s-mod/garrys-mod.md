---
kind: game
title: 'Garry''s Mod recon: Source engine, Workshop present'
game: Garry's Mod
games_also: []
game_version: 'Steam 4000 (exact build unverified this pass)'
platform: windows
engine: source
route: loader-api
tools: ["Garry's Mod Lua API", "Steam Workshop"]
anti_cheat: 'none detected (VAC applies on protected servers — single-player/local servers only for mod work)'
status: working
agents:
- OpenCode (Muse Spark)
humans: [PatrickJnr]
date: '2026-10-08'
links: ["https://wiki.facepunch.com/gmod/", "https://wiki.facepunch.com/gmod/Addon_Creation", "https://wiki.facepunch.com/gmod/Workshop_Addon_Creation"]
tags: ["garrys-mod", "source", "lua", "workshop", "recon", "scan"]
---

# Garry's Mod recon: Source engine, Workshop present

> Read-only recon of Garry's Mod (Steam 4000): Source 1 engine at 100% confidence (`garrysmod/gameinfo.txt`), x86 `gmod.exe`, Workshop content path present. Recommended route is the built-in Lua API (addons/gamemodes) plus Workshop distribution. Verified from `um scan` JSON; not launched.

## Setup

- Install: `E:\Steam\steamapps\common\GarrysMod\`. 3,558 files indexed.
- Engine: `source` [100%] evidence `garrysmod/gameinfo.txt`. Launcher: `gmod.exe` self-describes as **"Garry's Mod Version Selector (64-bit or 32-bit)"**, FileVersion **2026.09.16** (Facepunch) — so this install carries the x86-64 branch selector, not a pure-x86 binary; which architecture actually launches was not determined here.
- Local addons: `garrysmod/addons/` holds `gmod_toybox` + `melon_mayhem`. Workshop: 287 subscriptions under `workshop/content/4000`.
- Binary modules in use: `garrysmod/lua/bin/` ships `gmcl_gwater2` in win32/win64/linux64 flavors — native `.dll` extensions are already part of this install's mod set.
- No loaders reported (correct — GMod needs none; Lua is built in). No anti-cheat flagged by scan; VAC note: mod work belongs in single-player or servers you run, never against protected servers.

## Route and why

**Built-in Lua API** (autorun/entities/weapons/gamemodes under `garrysmod/lua`, distributed as `addons/` or Workshop items) — this is scan's `source.md` route, minus the parts GMod obsoletes (no SDK mod needed for Lua work; SourceMod is server-side). Rejected: native hooks/proxy DLLs (wrong layer while the Lua API reaches the idea).

## How the game works (what we had to learn)

- Source 1 layout: `garrysmod/` tree (`lua/`, `addons/`, `gamemodes/`, `materials/`, `models/`); `gameinfo.txt` defines the app. Mounted games (CS:S, TF2, HL2 assets) extend available content when owned.
- Launcher is an arch selector (x86 vs x86-64), not a fixed 32-bit binary: any `.dll` binary module must match the architecture that actually launches (unresolved here — the installed gwater2 module ships both win32 and win64 flavors, which sidesteps the question).
- Workshop path confirmed present, so subscription-based distribution is available.

### Lua vs native (local evidence + official wiki, fetched 2026-10-08)

- Standard route is pure Lua: addon folders with `addon.json`, client/server/shared realms (`States`), loading order documented under Lua_Folder_Structure / Lua_Loading_Order on wiki.facepunch.com/gmod. The 287 Workshop subs + 2 local addons here are this kind.
- Native route is **binary modules** (`lua/bin/*.dll`, server + client flavors): the wiki maintains dedicated guides (Creating Binary Modules via CMake/Premake/Rust, detouring functions, VS setup). The installed `gmcl_gwater2` win32/win64/linux64 set proves this install already runs one — match any new module's arch to the launched game arch (x86 vs x86-64 selector, unresolved here).
- Moddability classification: officially supported (Lua API + Workshop). Binary modules are community-established but version-sensitive (break across GMod updates); engine-level memory patching beyond modules is unsupported.

## Build steps

1. `um scan "Garry's Mod" --json` (expect `source`/100%, `gmod.exe` x86, Workshop path).
2. Check `garrysmod/addons/` + Workshop content for the active set.
3. New mods: Lua addon folder (with `addon.json` for Workshop upload) or gamemode; binary modules only if Lua cannot reach the idea.

## Verification

- Scan JSON fields quoted above; Workshop path existence checked.
- NOT verified: launch (and therefore which arch the selector picks), mounted-games set, full addon list behavior, Lua API version, exact game build.

## Gotchas

1. **3,558 files seems small for GMod.** Cause: content lives in mounted games + Workshop + addons; base tree is lean. Fix: inventory `addons/` and Workshop before judging scale.
2. **x86 process.** Cause: `gmod.exe` is 32-bit. Fix: any `.dll` binary module must be 32-bit.
3. **VAC scope.** Cause: scan reports no anti-cheat, but VAC guards official/protected servers. Fix: single-player or own servers for mod work.

## Assets

None produced (recon only). GMod assets are standard Source formats (VTF/VMT/MDL) convertible with community tooling if ever needed.

## Open questions

- Mounted-games inventory on this install (which Source games' content is available).
- Which architecture the x86-64 selector actually launches (determines binary-module builds).

## Sources and verification

- Local install: version resource (`Garry's Mod Version Selector`, 2026.09.16, Facepunch), local addons (`gmod_toybox`, `melon_mayhem`), Workshop subscription count (287), `lua/bin` module flavors, Workshop path presence. Date: 2026-10-08.
- gmod.facepunch.com (fetched 2026-10-08): Garry's Mod is "a physics based sandbox game built on a modified version of Valve's Source Engine" — official engine confirmation.
- wiki.facepunch.com/gmod (index fetched 2026-10-08): Addon_Creation, Workshop_Addon_Creation/Updating, Lua_Folder_Structure, Lua_Loading_Order, States (realms), Binary Modules guides (CMake/Premake/Rust, detouring, VS setup). Linked pages above were verified present in the fetched index; individual guide bodies not read.
- `um scan "Garry's Mod" --json`: engine `source`/100% via `gameinfo.txt` — reproduced in-session.
