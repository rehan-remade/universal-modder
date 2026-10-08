---
kind: game
title: 'Factorio 2.0.72 recon: official Lua API, Space Age, no mods installed'
game: Factorio
games_also: []
game_version: '2.0.72 win64 Steam + Space Age (from factorio-current.log dated 2026-01-05)'
platform: windows
engine: native
route: loader-api
tools: ["official Lua modding API", "in-game mod portal"]
anti_cheat: 'none detected'
status: working
agents:
- OpenCode (Muse Spark)
humans: [PatrickJnr]
date: '2026-10-08'
links: ["https://lua-api.factorio.com", "https://mods.factorio.com", "https://wiki.factorio.com", "https://forums.factorio.com", "https://factorio.com"]
tags: ["factorio", "lua", "mod-api", "space-age", "recon", "scan"]
---

# Factorio 2.0.72 recon: official Lua API, Space Age, no mods installed

> Read-only recon of Factorio 2.0.72 (Steam 427520, Space Age): native C++ game with an official Lua mod API (`data.lua` + `control.lua`), full Lua API docs shipped in `doc-html/`, and user data (mods/saves/logs) under `%APPDATA%\Factorio`. Verified from `um scan` JSON, the game log, and directory listings; not launched.

## Setup

- Install: `E:\Steam\steamapps\common\Factorio\`. Real binary at `bin\x64\factorio.exe` (scan's root-only exe list sees just `unins000.exe` — limitation noted below). 19,041 files indexed.
- Version: `2.0.72 (build 84292, win64, steam, space-age)` from `%APPDATA%\Factorio\factorio-current.log`; log also confirms config/data/write-data paths.
- Engine: scan says `native` [10%] (`no known engine signature`) — correct in the sense of "custom native engine", with the known-game route carrying the real answer (official Lua API, `misc-engines.md`).
- User data: `%APPDATA%\Factorio` exists with `mods/` (only `mod-list.json` — no mods installed), `saves/`, `player-data.json`, current/previous logs. Install `data/` holds `base/`, `core/`, `elevated-rails/`, `quality/`, `space-age/` (DLC present).
- `doc-html/` ships the Lua API reference: 148 `classes/`, 422 `concepts/`, 278 `prototypes/` pages — the modding spec, on disk.

## Route and why

**Official Lua API**: `mods/` folder under `%APPDATA%\Factorio` (`data.lua` + `control.lua`), plus the in-game mod portal. No loader, no hooks, no patching needed — this is also scan's known-game route. Rejected: native hooks (unsupported and unnecessary against an official API).

## How the game works (what we had to learn)

- Native x64 game; mods are zip/folder overdrops in `%APPDATA%\Factorio\mods`, enabled via `mod-list.json` and the in-game portal (which also handles Space Age dependency gating).
- Data lives in install `data/` (`base`, `core`, DLC folders); never edit in place — override via mod files.
- Scan caveats (same family as Kenshi): exes fingerprinted at root only (`bin\x64\factorio.exe` missed); mod dirs detected under the install only (`%APPDATA%` mods missed, though `save_hints` did find the saves path).

### Ecosystem currency (fetched 2026-10-08 from official sources)

- API docs live at lua-api.factorio.com with per-version trees: latest **stable 2.0.77**, experimental **2.1.21**. Installed game is **2.0.72** — five patches behind stable; match the doc tree to the game (read the 2.0.7x history, not `/latest/`) or update the game first.
- Canonical venues (all linked from the API docs front page): Mod Portal (mods.factorio.com) for distribution + dependency resolution, wiki.factorio.com for guides, forums.factorio.com for API questions.
- Moddability classification: officially supported, first-party (data/control stages, migrations, dependencies). Everything below the API surface (rendering, simulation core) is unsupported-by-design — native modification is not a route here.

## Build steps

1. `um scan Factorio --json` (expect `native`/10% + known Lua-API route + `%APPDATA%\Factorio` saves).
2. Read `factorio-current.log` head for exact version; read `%APPDATA%\Factorio\mods\mod-list.json` for the active set.
3. New mods: folder/zip in `%APPDATA%\Factorio\mods` following `doc-html/` prototypes; enable via mod-list or in-game portal.

## Verification

- Scan JSON, log head (version/build/paths), `%APPDATA%` listing (mods + saves + logs), `data/` DLC folders, `doc-html/` page counts — all read directly.
- NOT verified: launching with a mod, portal downloads, Space Age prototype overrides, multiplayer mod sync.

## Gotchas

1. **Scan shows no game exe.** Cause: root-only exe fingerprinting; the binary is `bin\x64\factorio.exe`. Fix: check `bin/` when `executables` looks empty.
2. **Scan shows no mod folders.** Cause: mod-dir detection is install-scoped; Factorio mods live in `%APPDATA%\Factorio\mods`. Fix: check the saves-hint paths too.
3. **Engine `native [10%]` looks alarming.** Cause: no engine signature table entry for Factorio's custom engine. Fix: the known-game route is the operative line; engine key here means "custom native", not "unknown risk".

## Assets

None produced (recon only). Factorio mods are code/prototypes; art would follow the game's sprite-spec docs if ever needed.

## Open questions

- Exact Space Age prototype gaps for any future mod idea (read `doc-html/prototypes`).
- Headless-server mod sync behavior (server not present here).

## Sources and verification

- Local install + user data: version/build/Space Age from `factorio-current.log` (2026-01-05), `%APPDATA%\Factorio` listing (mods with only `mod-list.json`, saves, logs), `data/` DLC folders, `doc-html/` page counts (148 classes / 422 concepts / 278 prototypes), `bin\x64\factorio.exe` path. Date: 2026-10-08.
- lua-api.factorio.com (fetched 2026-10-08): versioned API trees — latest stable **2.0.77**, experimental 2.1.21 (installed 2.0.72: read the matching tree); front page links Mod Portal (mods.factorio.com), wiki.factorio.com, forums.factorio.com, factorio.com.
- `um scan Factorio --json`: known-game Lua-API route + `%APPDATA%\Factorio` saves hint — reproduced in-session (engine key itself is uninformative `native`/10%).
