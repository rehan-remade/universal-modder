---
kind: game
title: 'Dwarf Fortress recon: native game, raw-file modding route'
game: Dwarf Fortress
games_also: []
game_version: 'Steam 975370 (exact build unverified this pass)'
platform: windows
engine: native
route: data
tools: ["raw-file modding (verified layout, not exercised)", "Steam Workshop (no subscriptions here)", "DFHack (docs-verified, not installed)"]
anti_cheat: 'none detected'
status: in-progress
agents:
- OpenCode (Muse Spark)
humans: [PatrickJnr]
date: '2026-10-08'
links: ["https://docs.dfhack.org", "https://github.com/DFHack/dfhack/releases", "https://www.bay12games.com/dwarves/"]
tags: ["dwarf-fortress", "native", "raw-files", "workshop", "recon", "scan"]
---

# Dwarf Fortress recon: native game, raw-file modding route

> Read-only recon of Dwarf Fortress (Steam 975370): native x64 game (`Dwarf Fortress.exe`), no engine signature, no loaders, no mod dirs flagged. The documented route is raw-text-file modding plus Steam Workshop distribution — stated per community docs, not exercised here, hence `status: in-progress`. Verified from `um scan` JSON; not launched.

## Setup

- Install: `E:\Steam\steamapps\common\Dwarf Fortress\`. 2,628 files indexed.
- Engine: `native` [10%] (`no known engine signature`) — custom C++ game, correctly unclassified.
- Exe: `Dwarf Fortress.exe` x64 unmanaged. No anti-cheat, no loaders, no mod dirs, no saves found.

## Route and why

**Raw-file data mods first** (verified layout below; plain-text raws defining creatures/items/materials, distributed via Steam Workshop), **DFHack second** for behavior changes, automation, and UI (docs-verified, not installed here). Native hooks are the wrong layer for a game whose content is text-defined. Rejected: proxy-DLL/memory approaches (scan's generic fallback) for any content-level idea.

## How the game works (what we had to learn)

- Custom native engine (SDL2 + FMOD + libpng/libjpeg/libtiff/libwebp observed at root); game content is substantially data-driven through human-readable raw files.
- Raw layout verified on disk: `data/vanilla/` holds the stock raws (`vanilla_bodies`, `vanilla_buildings` + `_graphics`, `vanilla_creatures` + `_extinct` + `_graphics`, interaction examples, readme); `data/installed_mods/` exists but is **empty** (no mods installed); there is no `mods/` directory; Workshop content for app 975370 is absent. Release docs on disk: `readme.txt` (includes backup instructions: copy the region folder out of `save/`), `release notes.txt`, `file changes.txt`, `command line.txt` (world-gen from CLI).
- No DFHack markers at root (no `hack/` dir, no dfhack-named files) — DFHack is not installed here.
- Steam release adds official Workshop support for distributing raw mods.
- Single-player, no protections — unrestricted scope.

### DFHack (docs fetched 2026-10-08 from docs.dfhack.org)

- DFHack is a memory-editing library exposing a cross-platform tool/plugin environment over DF; the default distribution ships bugfixes, UI improvements, automation, and modding tools, plus third-party tools. Docs version read: **53.16-r2**. Releases at github.com/DFHack/dfhack/releases; install/upgrade/uninstall guides under docs/Installing; a dedicated modding guide under docs/guides/modding-guide.
- Safest-behavior ladder for this install: raw-file mods (reversible, Workshop-distributable) first; DFHack (matching the exact DF build — DFHack is version-locked per release) only for what raws cannot express. DFHack was not installed or tested here.

## Build steps

1. `um scan "Dwarf Fortress" --json` (expect `native`/10%, single x64 exe).
2. Inventory the raw tree and Workshop subscription state (not done here).
3. New mods: raw-file packages via Workshop; validate by world-gen + launch (not done here).

## Verification

- Scan JSON fields quoted above; raw tree (`data/vanilla/*`, empty `data/installed_mods/`, absent `mods/`) and Workshop absence checked; DFHack absence checked by name; SDL2/FMOD library set listed; release-doc set noted.
- NOT verified: world-gen with a mod, DFHack install/attach against this DF build, exact game build, save locations. The DFHack recommendation is docs-backed (docs 53.16-r2 fetched), not locally demonstrated.

## Gotchas

1. **Engine `native [10%]` is correct-but-empty.** Cause: custom engine with no signature entry. Fix: read it as "custom native, use game-specific routes", and prefer the documented raw-file route over the generic native-hook fallback.
2. **No mod dirs flagged.** Cause: no mods installed (and Workshop state unchecked). Fix: check Workshop subscriptions before concluding anything about mod support.

## Assets

None produced (recon only).

## Open questions

- One raw tweak validated in world-gen (the remaining gap to `working`).
- Exact game build vs DFHack 53.16-r2 support window (match before installing DFHack).

## Sources and verification

- Local install: raw tree (`data/vanilla/*` names listed), empty `data/installed_mods/`, absent `mods/`, absent Workshop content (app 975370), DFHack absence by name, SDL2/FMOD library set, release-doc set. Date: 2026-10-08.
- docs.dfhack.org (fetched 2026-10-08, docs version 53.16-r2): DFHack is a memory-editing library with a cross-platform tool/plugin environment; releases at github.com/DFHack/dfhack/releases; install/upgrade/uninstall + modding guides under docs/. Bay12 official site bay12games.com/dwarves resolves (landing page fetched; version info not extracted).
- `um scan "Dwarf Fortress" --json`: engine `native`/10%, single x64 exe — reproduced in-session.
