---
kind: game
title: 'Abiotic Factor recon: Unreal Engine, IoStore paks, saves found'
game: Abiotic Factor
games_also: []
game_version: 'Steam 427410 (exact build unverified this pass)'
platform: windows
engine: unreal
route: loader-api
tools: ["UE4SS (docs-verified, not installed)", "FModel/retoc/repak (docs-described, not used here)"]
anti_cheat: 'none detected'
status: working
agents:
- OpenCode (Muse Spark)
humans: [PatrickJnr]
date: '2026-10-08'
links: ["https://ue4ss.com"]
tags: ["abiotic-factor", "unreal", "ue4ss", "pak", "iostore", "recon", "scan"]
---

# Abiotic Factor recon: Unreal Engine, IoStore paks, saves found

> Read-only recon of Abiotic Factor (Steam 427410): Unreal Engine at 100% confidence (`abioticfactor-Win64-Shipping.exe`, 5 paks, IoStore `.utoc` present), saves under `%LOCALAPPDATA%\abioticfactor`, no loader installed. Recommended route is UE4SS and/or `~mods` pak mods. Verified from `um scan` JSON; not launched.

## Setup

- Install: `F:\SteamLibrary\steamapps\common\AbioticFactor\`. Only 42 files indexed at top level (Unreal installs concentrate content in a few pak/container files — normal, not a thin install).
- Engine: `unreal` [100%] evidence `*-Win64-Shipping.exe`; project `abioticfactor`, exe `abioticfactor/binaries/win64/abioticfactor-win64-shipping.exe`, `iostore: true`, `paks: 5`.
- Exes (root): `abioticfactor.exe` x64 unmanaged (launcher stub; the shipping binary lives under `Binaries/Win64` — same root-only-exe limitation seen on Factorio).
- Saves: `%LOCALAPPDATA%\abioticfactor` and `...\Saved` both found.
- No anti-cheat, no loaders, no mod dirs flagged.

## Route and why

**UE4SS (Lua/C++ hooks, live property viewer) and/or pak mods** in `Content/Paks/~mods` (browse with FModel, pack with retoc/repak) — scan's `unreal.md` route. Native hooks only if UE4SS cannot reach the idea.

## How the game works (what we had to learn)

- Modern Unreal packaging: IoStore (`.utoc`/`.ucas`) + paks; `~mods` subfolder is the community pak-override slot. Concretely on disk: `Content/Paks/` holds the `global` triple plus `pakchunk0-Windows` and `pakchunk0optional-Windows` (each as `.pak` + `.ucas` + `.utoc`); `~mods` does **not** exist yet (re-verified) and must be created for pak mods.
- Per-project layout under `abioticfactor/` (`Binaries/Win64` shipping exe).
- Save/config tree at `%LOCALAPPDATA%\abioticfactor\Saved` — back this up before modded runs.

### UE4SS facts (docs fetched 2026-10-08 from ue4ss.com)

- Install is proxy-DLL based with CLI controls including `--disable-ue4ss` (run without uninstalling) and `--ue4ss-path` (test alternate builds). Building UE4SS from source needs MSVC 19.43+ (VS 17.13+), Rust ≥ 1.73, CMake ≥ 3.22, Ninja or MSVC — none of which was exercised here; the prebuilt install path is the documented one for players.
- Moddability classification: community-established (UE4SS Lua/C++ + `~mods` paks). Packaged-build limits (signed/cooked content, IoStore) apply as documented for UE titles generally; per-game limits for Abiotic Factor were not probed.

## Build steps

1. `um scan "Abiotic Factor" --json` (expect `unreal`/100%, iostore + 5 paks, saves paths).
2. Browse paks with FModel; install UE4SS (not done here) for live work.
3. New mods: `~mods` pak or UE4SS Lua/C++ mod.

## Verification

- Scan JSON fields quoted above; saves paths confirmed present by scan; pak triplets listed from `Content/Paks/`; full-exe UE-version-string hunt attempted (137.9 MB shipping binary contains no `++UE4/5+Release-` marker — custom/stripped build or relocated version resource).
- NOT verified: launch, UE4SS attach, pak mod load, exact UE minor version (use FModel against the paks next).

## Gotchas

1. **42 files looks empty.** Cause: Unreal concentrates gigabytes into 5 paks; file count is meaningless here. Fix: judge by pak sizes via FModel, not file count.
2. **Root exe is a stub.** Cause: real binary is `Binaries/Win64/abioticfactor-Win64-Shipping.exe`. Fix: target the shipping exe for any loader install/analysis, not the root stub.

## Assets

None produced (recon only).

## Open questions

- Exact UE version (read `FEngineVersion` from the shipping exe) for UE4SS build matching.
- Whether the 5 paks include a pre-existing `~mods` slot or it must be created.

## Sources and verification

- Local install: pak triplets listed from `Content/Paks/`, saves paths confirmed present, full-exe UE-marker hunt (137.9 MB binary, no `++UE` marker — attempted, absent). Date: 2026-10-08.
- ue4ss.com (fetched 2026-10-08): proxy-DLL install with `--disable-ue4ss` / `--ue4ss-path` flags; source builds need MSVC 19.43+ (VS 17.13+), Rust ≥ 1.73, CMake ≥ 3.22.
- `um scan "Abiotic Factor" --json`: engine `unreal`/100%, iostore + 5 paks — reproduced in-session.
