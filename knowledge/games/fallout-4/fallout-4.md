---
kind: game
title: 'Fallout 4 recon: F4SE + Creation Kit installed, Vortex-managed mod set'
game: Fallout 4
games_also: []
game_version: 'F4SE binary targets runtime 1_11_221 (per filename; game build otherwise unverified)'
platform: windows
engine: creation
route: data
tools: ["F4SE (installed, runtime 1_11_221)", "Creation Kit (installed)", "Vortex (folder marker)", "xEdit/FO4Edit (docs-described)"]
anti_cheat: 'none detected'
status: working
agents:
- OpenCode (Muse Spark)
humans: [PatrickJnr]
date: '2026-10-08'
links: []
tags: ["fallout-4", "creation", "f4se", "esp", "esl", "vortex", "recon", "scan"]
---

# Fallout 4 recon: F4SE + Creation Kit installed, Vortex-managed mod set

> Read-only recon of Fallout 4 (Steam 377160): Creation engine at 100% confidence (DLC `.esm` set), x64 binaries, **F4SE script extender installed** (runtime 1_11_221), **Creation Kit installed**, and a Vortex-managed, ESL-heavy mod set in `Data/`. Recommended route is ESP/ESL plugins via FO4Edit + Creation Kit with F4SE plugins under MO2/Vortex. Verified from `um scan` JSON and directory listings; not launched.

## Setup

- Install: `F:\SteamLibrary\steamapps\common\Fallout 4\`. 1,981 files indexed.
- Engine: `creation` [100%] evidence `data/dlccoast.esm`, `data/dlcnukaworld.esm`, `data/dlcrobot.esm`.
- Exes (root): `Fallout4.exe`, `Fallout4Launcher.exe`, `f4se_loader.exe`, `CreationKit.exe` (all x64 unmanaged).
- Loaders: **Script Extender (Bethesda)** flagged from `f4se_loader.exe`. Root F4SE files: `f4se_1_11_221.dll`, `f4se_loader.exe`, `f4se_readme.txt`, `f4se_whatsnew.txt`.
- `Data/` census (top extensions): `.js` 464, `.json` 332, `.pak` 223, `.ba2` 217, `.png` 154, `.esl` 89, `.pex` 29 (+ `.svg`/`.html`/`.css` UI assets) — a heavily modded tree with script sources and UI-framework files, not a clean install.
- `Data/F4SE/Plugins/`: `F4Viewer` (+`.dll`), `PrismaUI_F4` (+`.dll`, `.ini`, `_CEF` dir), `__folder_managed_by_vortex`, and `version-1-10-*.bin` files (prior-generation F4SE artifacts — this install has been modded across runtimes).
- Mod dirs flagged: `mods`, `data/scripts`. Saves: `Documents/My Games/Fallout4` exists but contains no `Saves/` directory (no playthrough saves here).
- No anti-cheat found.

## Route and why

**ESP/ESL data plugins first** (FO4Edit, Creation Kit — installed), **F4SE plugins** (`Data/F4SE/Plugins/*.dll`) for engine extension, managed under Vortex/MO2 — scan's `bethesda.md` route, and every piece is already present. Native hooks are the wrong layer for a Creation game with a working extender. Rejected: clean-room native approaches while F4SE loads.

## How the game works (what we had to learn)

- Creation data model: `.esm` masters + `.ba2` archives; mods add `.esp`/`.esl`/loose files; F4SE extends Papyrus scripting and exposes native plugin APIs.
- 64-bit game (unlike New Vegas): extender/tooling must match x64.
- Vortex manages this install (`__folder_managed_by_vortex`); load order lives in the manager profile + `Plugins.txt`, not in the game folder.
- `PrismaUI_F4` + CEF + `.js`/`.html`/`.css` assets show UI-framework mods are active here (Chromium-embedded UI inside the game process).
- Moddability classification: officially tolerated + community-established (ESP/ESL + F4SE + manager). Single-player, no protections found.

## Build steps

1. `um scan "Fallout 4" --json` (expect `creation`/100%, F4SE loader flag, CK exe, `mods` + `data/scripts` dirs).
2. Read `Data/` census + `F4SE/Plugins/` for the active set; check F4SE `whatsnew` for the installed generation.
3. New mods: ESP/ESL in xEdit/CK; F4SE `.dll` plugins for engine work; keep everything manager-side (Vortex/MO2), never hand-drop into `Data/` on a managed install.

## Verification

- Scan JSON fields quoted above; root F4SE file list, `Data/` extension census, `F4SE/Plugins/` listing, saves-folder emptiness — all read directly.
- NOT verified: launch, F4SE load, plugin ABI match against the installed runtime generation, load order, exact game build (F4SE filename implies runtime 1_11_221; game exe carries no checked version string).

## Gotchas

1. **F4SE generation must match the game runtime.** Cause: `f4se_1_11_221.dll` targets one runtime; the `version-1-10-*.bin` files show this install previously tracked older ones. Fix: after any game update, re-verify F4SE-vs-runtime match before launching with mods.
2. **Vortex-managed tree.** Cause: `__folder_managed_by_vortex` marker. Fix: add/remove mods through Vortex (or migrate deliberately to MO2), not by hand-dropping files into `Data/`.
3. **No saves despite a modded tree.** Cause: `Saves/` empty. Fix: this install is modded but unplayed (or saves live elsewhere) — back up `Documents/My Games/Fallout4` once a playthrough exists.

## Assets

None produced (recon only).

## Open questions

- Exact game runtime build (no version resource found in first 6 MB of `Fallout4.exe`; F4SE filename implies runtime 1_11_221, while current F4SE builds target 1.11.240/1.10.984/1.10.163 — resolve the match before launching modded).
- Full `.esp` count and load order (extension census cut at top-12; enumerate before load-order work).
- F4Viewer/PrismaUI versions and update state.

## Sources and verification

- Local install: F4SE root file list (`f4se_1_11_221.dll` et al), `Data/` extension census, `F4SE/Plugins/` listing (F4Viewer, PrismaUI_F4+CEF, Vortex marker, `version-1-10-*.bin`), empty `Saves/`, CK presence, missing FO4 version resource. Date: 2026-10-08.
- f4se.silverlock.org (fetched 2026-10-08): current builds 0.7.9 (runtime 1.11.240), 0.7.2 (1.10.984), 0.6.23 (1.10.163), 0.6.21 VR-only; supports latest Steam **and** GOG (currently different versions); editor needs no modification but custom pex/psc when available; **no Windows Store support**. Nexus mirror: nexusmods.com/fallout4/mods/42147.
- creationkit.com (checked 2026-10-08): official CK wiki is **down for backend maintenance** (notice dated 2024/02/07, still served) — do not treat it as a working reference until it returns; prefer FO4Edit/xEdit docs and the locally installed Creation Kit help.
- `um scan "Fallout 4" --json`: engine `creation`/100%, F4SE loader flag, CK exe — reproduced in-session.
