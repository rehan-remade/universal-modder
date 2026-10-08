---
kind: game
title: 'Fallout New Vegas recon: Gamebryo, full DLC set, no script extender'
game: 'Fallout: New Vegas'
games_also: []
game_version: 'Steam 22380 (exact build unverified this pass; full DLC .esm set present)'
platform: windows
engine: creation
route: data
tools: ["xEdit/FNVEdit (to install)", "xNVSE (to install; Steam+GOG supported per xNVSE docs)", "Mod Organizer 2 (to install)", "FNV 4GB Patcher (docs-mentioned, not installed)"]
anti_cheat: 'none detected'
status: working
agents:
- OpenCode (Muse Spark)
humans: [PatrickJnr]
date: '2026-10-08'
links: ["https://github.com/xNVSE/NVSE", "https://www.nexusmods.com/newvegas/mods/67883"]
tags: ["fallout-new-vegas", "gamebryo", "creation", "esp", "nvse", "recon", "scan"]
---

# Fallout New Vegas recon: Gamebryo, full DLC set, no script extender

> Read-only recon of Fallout: New Vegas (Steam 22380): Gamebryo engine at 100% confidence from the DLC `.esm` set, stock launcher only (`falloutnv.exe` + `falloutnvlauncher.exe`, both x86 native), no script extender and no mod manager installed. Recommended route is ESP plugins via xEdit plus NVSE for script extension, under MO2. Verified from `um scan` JSON and `Data/` listing; not launched.

## Setup

- Install: `F:\SteamLibrary\steamapps\common\Fallout New Vegas\`. Only 475 files indexed (small root + `Data/` + `Redists/directx` + `.sentry-native`).
- Engine: `creation` [100%] evidence `data/caravanpack.esm`, `data/classicpack.esm`, `data/deadmoney.esm`.
- `Data/` census: 22 `.bsa`, 10 `.esm` (base + all DLC packs: caravan/classic/deadmoney-class DLCs present), 9 `.nam`, 0 `.esp` (no mods), plus Music/Sound/Video/Shaders dirs. No `nvse_loader.exe` / `nvse_*.dll` (no script extender — though a lone `nvmp.nvse.package` sits at install root, a New Vegas Multiplayer artifact, not the extender), no MO2 markers, no GECK.
- Exes: `falloutnv.exe`, `falloutnvlauncher.exe` (x86, unmanaged). No saves found by scan (Documents/My Games/FalloutNV unchecked — folder may not exist; never played here).

## Route and why

**ESP data plugins first** (xEdit/FNVEdit, GECK-style editing), **NVSE + MO2** for anything scripted or load-ordered. This matches scan's `bethesda.md` route. Native hooks are the wrong layer for a Gamebryo game with a mature extender ecosystem. The gap to close before modding: install NVSE (x86, matches the 32-bit exe) and MO2.

## How the game works (what we had to learn)

- Gamebryo/Creation data model: `.esm` masters + `.bsa` asset archives in `Data/`; mods add `.esp`/loose files; load order decides override winners (MO2 profiles manage this).
- 32-bit game: extenders and tools must match x86 (relevant when downloading NVSE).
- GECK is the official editor route for new content; xEdit for conflict resolution and patching.

### Script-extender facts (fetched 2026-10-08 from xNVSE/NVSE on GitHub)

- Install rule, quoted in spirit: copy the `.dll`/`.exe` files to the game root (where `FalloutNV.exe` lives) — **not** into `Data/`, **not** via MO2 as a normal mod.
- Launch via `nvse_loader.exe` — unless the game is 4GB-patched, in which case launch `FalloutNV.exe` (Steam overlay/community launch still works with the Steam Community option enabled).
- Compatibility matrix (docs-stated, not tested here): Steam and GOG supported; German No Gore, Xbox Game Pass, and Bethesda.net versions are **not** supported; Epic Games Store needs a separate community EGS patcher.
- Plugin extenders in the same family named by the task brief (JIP LN NVSE, JohnnyGuitar NVSE) layer on top of xNVSE as `nvse/plugins/*.dll`; none are installed here, and their currency was not re-verified this pass.
- Moddability classification: officially tolerated + community-established (ESP/ESM + NVSE + MO2). Single-player, no anti-cheat found.

## Build steps

1. `um scan "Fallout: New Vegas" --json` (expect `creation`/100%, DLC `.esm` evidence).
2. Confirm `Data/` has 22 `.bsa` / 10 `.esm` and no `nvse_*`.
3. Install NVSE + MO2 (not done here — and when installing NVSE, follow the xNVSE rule: binaries to game root, never `Data/`, never as an MO2 mod).
4. New mods: ESP work in xEdit/GECK; NVSE plugins as `nvse/plugins/*.dll` for engine extension.

## Verification

- Scan JSON fields; `Data/` extension census read directly; absence of `nvse_*`/MO2 markers checked by name.
- NOT verified: launch, NVSE load, load order behavior, exact game patch version, GECK availability.

## Gotchas

1. **475 indexed files looks thin.** Cause: small root + shallow `Data/`; the bulk is inside the 22 `.bsa` archives, which scan does not open. Fix: browse archives with xEdit/BSArch, don't judge by file count.
2. **Must match x86.** Cause: `falloutnv.exe` is 32-bit. Fix: NVSE x86, 32-bit tool builds where relevant.
3. **No saves found is expected on a fresh install.** Fix: run the launcher once, then back up `Documents/My Games/FalloutNV` before modding.

## Assets

None produced (recon only).

## Open questions

- Exact game patch version (no version resource in `FalloutNV.exe`; xNVSE supports Steam + GOG builds — confirm store build before installing).
- Whether 4GB-patcher/LAA flag is wanted (x86 address-space limits with DLC + mods; the xNVSE docs reference an FNV 4GB Patcher on Nexus for this).
- JIP LN / JohnnyGuitar plugin currency (named but not verified this pass).

## Sources and verification

- Local install: `Data/` census (22 `.bsa`, 10 `.esm`, 0 `.esp`), NVSE/MO2/GECK absence by name, x86 exes, missing version resource. Date: 2026-10-08.
- github.com/xNVSE/NVSE (fetched 2026-10-08): install rule (binaries to game root, never `Data/` or MO2-managed), `nvse_loader.exe` launch (or `FalloutNV.exe` when 4GB-patched), Steam+GOG supported, German No Gore / Xbox GP / Bethesda.net unsupported, EGS needs community patcher, releases + Nexus mirror (nexusmods.com/newvegas/mods/67883).
- `um scan "Fallout: New Vegas" --json`: engine `creation`/100% via DLC `.esm` set — reproduced in-session.
