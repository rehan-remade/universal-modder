---
kind: game
title: 'Stardew Valley recon: SMAPI installed, MonoGame, mods present'
game: Stardew Valley
games_also: []
game_version: 'Game 1.6.15.24356, SMAPI 4.4.0 (both from version resources, Steam 413150)'
platform: windows
engine: xna-fna
route: loader-api
tools: ["SMAPI 4.4.0 (installed; upstream 4.5.2 per smapi.io)", "Content Patcher (docs-based)", "Harmony via SMAPI (0Harmony.dll on disk)"]
anti_cheat: 'none detected'
status: working
agents:
- OpenCode (Muse Spark)
humans: [PatrickJnr]
date: '2026-10-08'
links: ["https://smapi.io", "https://stardewvalleywiki.com/Modding:Index", "https://github.com/Pathoschild/SMAPI"]
tags: ["stardew-valley", "smapi", "monogame", "dotnet", "recon", "scan"]
---

# Stardew Valley recon: SMAPI installed, MonoGame, mods present

> Read-only recon of the installed Stardew Valley (Steam 413150): game 1.6.15 with SMAPI 4.4.0 already installed and 255 mods in `Mods/`. Recommended route is SMAPI (Content Patcher JSON packs or C# mods). Verified from `um scan` JSON, version resources, and directory listings; the game was not launched.

## Setup

- Install: `E:\Steam\steamapps\common\Stardew Valley\` (Steam 413150). No Workshop entry (Stardew uses Nexus/mods folders, not Workshop).
- Scan: engine `xna-fna` [95%] evidence `MonoGame.Framework.dll`; 21,825 files indexed, not truncated.
- Exes (root level): `Stardew Valley.exe`, `StardewModdingAPI.exe`, `createdump.exe` — all reported unmanaged x64 by PE CLR-header check (modern .NET single-file/bundled binaries have no CLR header; same shape as Kenshi's KMM).
- Loaders: **SMAPI 4.4.0** (`StardewModdingAPI.exe` ProductVersion `4.4.0+b84a896…`; `smapi-internal/` ships `0Harmony.dll`, Cecil, MonoMod, Newtonsoft.Json — the full loader stack). Mod dir: `Mods/` with **255 entries** (including AdvancedCasksMod, Adventurer's Guild Expanded 1.0.15, AeroCore, Almanac, AntiSocialNPCs, AtraCore, AutoAnimalDoors, Automate, AutomaticGates, Beatrice NPC, …).
- Game version: `Stardew Valley.exe` reports `1.6.15.24356` (ConcernedApe).
- Saves: scan found none — `%APPDATA%\StardewValley` does not exist on this machine (game never played here, or saves live elsewhere).

## Route and why

**SMAPI first**: Content Patcher JSON content packs for data/asset changes, C# SMAPI mods with Harmony for code — this is also `um scan`'s known-game route and matches the installed reality (SMAPI present, mods present). Native hooks are unnecessary. Rejected: managed-patch without SMAPI (no reason to bypass the installed loader).

## How the game works (what we had to learn)

- MonoGame Framework on .NET (modern single-file distribution, hence the unmanaged PE flags). SMAPI launches via `StardewModdingAPI.exe` and loads `Mods/*` (each a folder with a manifest + optional DLL/content-pack).
- Loader stack on disk (`smapi-internal/`): `0Harmony.dll` (Harmony patching), Cecil/MonoMod (assembly weaving), Newtonsoft.Json, Markdig, Pintail — new C# mods must target the Harmony generation SMAPI 4.4.0 ships, not latest upstream.
- Save location convention is `%APPDATA%\StardewValley` (per community docs); absent here, so no save to back up yet.
- Scan caveat carried over from the Kenshi work: only root-level exes are fingerprinted; subdirectory binaries are not classified.

### Ecosystem currency (fetched 2026-10-08 from primary sources)

- Upstream SMAPI is **4.5.2** (per smapi.io; requires Stardew 1.6.14+). Installed here: game **1.6.15** + SMAPI **4.4.0** — compatible, but one minor behind; update via the smapi.io installer or Nexus before starting new C# work.
- SMAPI ships its own compat tooling (mod-compatibility list, log parser, JSON validator on smapi.io) — use the log parser on first launch with this 255-mod stack.
- Docs entry: Modding:Index on the Stardew Valley wiki (linked from smapi.io); player guide and install guides live there, not in this note.
- Moddability classification: officially tolerated + community-established (SMAPI/Content Patcher/Harmony). No anti-cheat, no integrity checks against modding found. Multiplayer modding requires all players to run the same mod set (docs-described, not tested here).

## Build steps

1. `uv run --project T:\unversemodder python -m um scan "Stardew Valley" --json` to reproduce (expect `xna-fna`, SMAPI loader).
2. List `Mods/` for the active mod set; read `StardewModdingAPI` log after a launch for load order (not done here).
3. New mods: Content Patcher pack (JSON) for data/assets, or SMAPI C# project for code.

## Verification

- Scan JSON fields quoted above; `Mods/` count (255) and sample listing observed; version resources read for game (1.6.15.24356) and SMAPI (4.4.0); `smapi-internal/` stack listed; `%APPDATA%\StardewValley` absence checked.
- NOT verified: game launch, SMAPI mod load order/errors, save behavior. Web research for current SMAPI/Content Patcher/Harmony upstream versions was blocked this session (search rate-limited) — re-check versions before starting a mod.

## Gotchas

1. **Exes report unmanaged though the game is .NET.** Cause: modern bundled .NET has no CLR data-directory entry, which is all `pe_info` checks. Fix: treat the `xna-fna` engine evidence (MonoGame DLL) as authoritative, not the per-exe managed flags.
2. **No saves found.** Cause: `%APPDATA%\StardewValley` absent — fresh/never-played install. Fix: play once before modding so there is a save to back up with `um backup`.

## Assets

None produced (recon only).

## Open questions

- SMAPI mod load order/errors on this 255-mod stack (run the smapi.io log parser on first launch output).
- Exact Content Patcher version(s) in the stack (read mod manifests, not done here).

## Sources and verification

- Local install: version resources (game 1.6.15.24356, SMAPI 4.4.0+b84a896), `Mods/` count 255 + sample, `smapi-internal/` stack listing, `%APPDATA%\StardewValley` absence. Date: 2026-10-08.
- smapi.io (fetched 2026-10-08): SMAPI is the mod loader; current release **4.5.2**; requires Stardew **1.6.14+** (installed 1.6.15 qualifies); ships mod-compatibility list, log parser, JSON validator. Download via GitHub Pathoschild/SMAPI, Nexus mod 2400, or CurseForge (links on smapi.io).
- Modding:Index on the Stardew Valley wiki (linked from smapi.io; fetched 2026-10-08): mod definition, migration guides through 1.6.16, player/developer guides. Scope note: page revision oldid=189642 as fetched.
- `um scan "Stardew Valley" --json`: engine `xna-fna`/95%, SMAPI loader flag — reproduced in-session.
