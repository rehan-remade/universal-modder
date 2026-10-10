---
kind: game
title: 'Factorio 2.0 recon: official Lua mod API, info.json, mods under %APPDATA%'
game: Factorio
games_also: []
game_version: '2.0.x win64 Steam + Space Age; 2.0.72 at last launch (log dated 2026-01-05); installed version not read'
platform: windows
engine: native
route: loader-api
tools: ["official Lua modding API", "Mod Portal (mods.factorio.com)"]
anti_cheat: 'none detected'
status: in-progress
agents:
- OpenCode (Muse Spark)
humans: [PatrickJnr]
date: '2026-10-08'
links: ["https://lua-api.factorio.com", "https://lua-api.factorio.com/latest/auxiliary/mod-structure.html", "https://mods.factorio.com", "https://wiki.factorio.com", "https://forums.factorio.com"]
tags: ["factorio", "lua", "mod-api", "info-json", "space-age", "recon"]
---

# Factorio 2.0 recon: official Lua mod API, info.json, mods under %APPDATA%

> Read-only recon of Factorio on Steam (app 427520) with the Space Age DLC: a native C++ game with an official Lua
> mod API. Mods are folders or zips in `%APPDATA%\Factorio\mods`, each with an `info.json`. `data.lua` defines
> prototypes and `control.lua` does runtime scripting, and the API reference ships with the game in `doc-html/`.
> Nothing was built or launched, and the version below comes from an old log, not from the install.

## Setup

- Steam, Windows x64. The game binary is `bin\x64\factorio.exe`, not in the install root.
- Version: the last launch was `2.0.72 (build 84292, win64, steam, space-age)`, from
  `%APPDATA%\Factorio\factorio-current.log` dated 2026-01-05. Steam has probably updated the game since. The
  installed version is in `data/base/info.json`, which wasn't read (Gotcha 1).
- The install's `data/` has `base/`, `core/` and the Space Age folders `elevated-rails/`, `quality/` and
  `space-age/`.
- User data: `%APPDATA%\Factorio` holds `mods/` (with `mod-list.json`), `saves/`, `player-data.json` and the logs.
  The log also prints the config, data and write-data paths the game uses.
- `doc-html/` in the install is the Lua API reference (classes, concepts, prototypes).
- Current releases (lua-api.factorio.com, 2026-10-08): stable 2.0.77, experimental 2.1.21.

## Route and why

The official Lua API: develop in `%APPDATA%\Factorio\mods` and publish on the Mod Portal. No loader, hooks or
patching. `um scan`'s known-game route says the same (`misc-engines.md`). Rejected: native hooks, which are
unsupported and unnecessary next to an official API.

## How the game works (what we had to learn)

- `info.json` is the only mandatory file in a mod (Lua API docs, "Mod structure"). `name`, `version`, `title` and
  `author` are mandatory. `factorio_version` defaults to `"0.12"` when it's left out, so set it to `"2.0"`. A mod
  that uses Space Age content lists `space-age` in `dependencies`.
- Naming: an unzipped mod folder is `{name}_{version}` or just `{name}`. A zip must be `{name}_{version}.zip`, and
  the folder inside it can have any name.
- Stages: `data.lua` (with `data-updates.lua` and `data-final-fixes.lua`) defines prototypes. `control.lua` is
  runtime scripting.
- Mods are enabled in `mods/mod-list.json` or the in-game Mods menu, which also downloads from the Mod Portal and
  resolves dependencies.
- The base game and the DLC sit in the install's `data/` with their own `info.json`. Don't edit them in place;
  override from a mod.
- The online API docs are versioned (`lua-api.factorio.com/<version>/`), and `/latest/` is the newest stable.
  Read the tree for the installed version, or the `doc-html/` that ships with the install.

## Build steps

1. `um scan Factorio --json`: expect engine `native`, the known-game Lua API route, and the `%APPDATA%\Factorio`
   saves hint.
2. Read the installed version from `data/base/info.json` (`version`) and use the matching API docs.
3. Create `%APPDATA%\Factorio\mods\<name>\` with an `info.json` (`name`, `version`, `title`, `author`,
   `factorio_version: "2.0"`), then `data.lua` for prototypes and/or `control.lua` for runtime scripting.
4. Back up `%APPDATA%\Factorio\saves` (`um backup`), then enable the mod in `mod-list.json` or the in-game Mods
   menu.

## Verification

- Read directly on 2026-10-08: `um scan` output, the head of `factorio-current.log` (version, build, paths), the
  `%APPDATA%\Factorio` listing, the install's `data/` folders and `doc-html/`.
- From the docs: the `info.json` rules and folder naming (Lua API "Mod structure" page, checked 2026-10-09), and
  the current versions (2026-10-08).
- Not verified: the installed version, launching with a mod, Mod Portal downloads, Space Age prototype overrides,
  multiplayer mod sync.

## Gotchas

1. **The version in `factorio-current.log` can be months old.** The log read here said 2.0.72 and was dated
   2026-01-05. **Cause:** the game writes that log when it starts, and Steam updates the files without launching
   the game. **Fix:** read `version` from `data/base/info.json` in the install.

## Assets

None (recon only). Factorio mods are mostly prototypes and Lua. Art would follow the sprite specs in the
prototype docs.

## Open questions

- The installed version (read `data/base/info.json`).
- How mods sync to a headless server (there's no server on this machine).

## Sources and verification

- Local install and user data, read-only, 2026-10-08: the head of `factorio-current.log` (dated 2026-01-05), the
  `%APPDATA%\Factorio` listing, the `data/` folders, `doc-html/`, `bin\x64\factorio.exe`.
- lua-api.factorio.com (fetched 2026-10-08): versioned API trees, latest stable 2.0.77, experimental 2.1.21. The
  front page links the Mod Portal, the wiki and the forums.
- lua-api.factorio.com/latest/auxiliary/mod-structure.html (checked 2026-10-09): `info.json` is "the only
  mandatory file", its mandatory fields, the `factorio_version` default, folder and zip naming.
- `um scan Factorio --json`, run in-session.
