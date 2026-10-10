---
kind: game
title: "No Man's Sky: PSAR/HGPAK archives, the MBIN binary format, and loose-file modding"
game: "No Man's Sky"
games_also: []
game_version: "PC (GOG/Steam), 2016–2023 RE window; PS4 and Switch variants noted"
platform: windows
engine: unknown
route: data
tools: ["brink.bms (QuickBMS)", "MBINCompiler (monkeyman192)", "NMS-Tools (HugoPeters)", "HGPAKtool (monkeyman192)", "Switch-Toolbox (KillzXGaming)", "010 Editor templates"]
anti_cheat: "none known"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links:
  - "https://github.com/monkeyman192/MBINCompiler"
tags: ["hello-games", "psar", "hgpak", "mbin", "exml", "mbincompiler", "loose-files", "glsl", "skeleton", "archive"]
---

# No Man's Sky: PSAR/HGPAK archives, the MBIN binary format, and loose-file modding

> No Man's Sky runs on a custom Hello Games engine, not Unity or Unreal. Its data
> lives in `.pak` archives (a PSAR variant on PC, HGPAK on PS4/Switch) and its
> core data format is `.mbin`, which decompiles to XML (`.exml`). The useful modding
> lever is that the PC build loads loose files from `GAMEDATA/PCBANKS/` (pre-5.50;
> since 5.50, January 2025, mods go under `GAMEDATA/MODS/`) without
> repacking, and shaders ship as editable GLSL. This note records the formats and
> the known gaps from the XeNTaX extraction.

## Setup
- Game: No Man's Sky PC (PSAR variant PAK), plus PS4/Switch (HGPAK).
- Tooling used on the forum: QuickBMS + aluigi's `brink.bms`, HugoPeters'
  NMS-Tools (`NMS-Extract`, `NMS-View`), MBINCompiler (monkeyman192) with
  010 Editor templates, HGPAKtool for console PAKs, Switch-Toolbox for console
  textures/audio. hcs64 tools (vgmstream, ww2ogg) for the standard Wwise audio.
- No version pin was recorded in the dump; treat format details as
  2016–2023-era. Note: since 5.50 (January 2025) the PC build's `.pak` archives
  are **HGPAK** too (no longer the PSAR variant), and mods load from
  `GAMEDATA/MODS/`. Verify against the current build before relying on them.

## Route and why
- **Data modding, loose-file first.** The PC game loads loose files from
  `GAMEDATA/PCBANKS/` (pre-5.50; `GAMEDATA/MODS/` on 5.50+), so shader and
  texture edits (chromatic aberration off, vignette off, shader injection) need
  no archive repack. Repacking PSAR/HGPAK
  is the hard part and was avoided. An emoose Reddit guide (2016) documents the
  loose-file approach.
- MBIN is the editable data layer: decompile `.mbin` → `.exml` (XML), edit,
  compile back. That avoids touching the container entirely for gameplay/UI/localization data.

## How the game works (what we had to learn)

### Engine and archives
- Custom Hello Games engine.
- PC archive: `.pak`, a **PSAR variant** (PSAR is the PS3/PS4 format aluigi's
  scripts already handle). Files are **zlib-compressed in 64 KiB chunks**.
  `brink.bms` works; the one required edit is changing
  `log NAME OFFSET SIZE` → `clog NAME OFFSET SIZE SIZE` so entries are treated
  as compressed. Batch command from the dump:
  `quickbms -d -F "*.pak" "brink.bms" "PCBANKS" "OUTPUT"`.
- Console archive: `.pak` with **`HGPAK`** magic (not PSAR), compressed with
  **zstd (possibly Oodle)**. HGPAKtool extracts; repacking was WIP. A QuickBMS
  script only handled uncompressed entries.
- Two named PAKs carry useful content: `NMSARC.553AF401.pak` (engine settings)
  and `NMSARC.EEAC04FA.pak` (shaders).

### MBIN (the core data format)
Layout as documented:
```
Header:
  int32  cc / magic
  int32  version
  int32  padding[2]
  int64  hash
  char   type[64]   # e.g. "cTkLocalisationTable", "GcWidgetData"
  int64  padding
  ... type-dependent data follows
```
Known types: `cTkLocalisationTable` (localization), `GcWidgetData` (UI widgets),
`GcSceneData` / `GcModelData` (scene/model descriptors), `GcSkeletonData`
(skeleton/bone hierarchy).

Localization is the best-documented type:
`Header → LocalisationTableHeader → LocalisationTableEntry[key[32], lines[]]`,
handled by an Atvaark 010 Editor template. Workflow: `.mbin` → extract `.exml`
(XML) → edit → compile → `.mbin` (MBINCompiler).

### Models, textures, shaders
- Model data is embedded inside `.mbin` (types `GcModelData` / `GcSceneData`),
  with standard vertex buffers (positions, normals, UVs).
- Textures are `.dds` (DXT/BC) and directly editable.
- Shaders are **uncompiled GLSL** in `NMSARC.EEAC04FA.pak` — directly text-editable.
- Skeleton descriptor is a separate `.mbin` with bone hierarchy + transforms;
  a `transmat` field holds 9 values. Coordinate system is OpenGL (right-handed,
  Y-up). Rotation order was inconsistent: **XZY for some models, XYZ for others**.

### Audio
Standard **Wwise** `.bnk` / `.pck`; bnkextr / vgmstream handle it. Not heavily
discussed in the source threads.

## Build steps
1. Extract PC PAKs: `quickbms -d -F "*.pak" "brink.bms" "PCBANKS" "OUTPUT"`
   (with the `clog` edit). For console, use HGPAKtool.
2. For data edits: decompile target `.mbin` to `.exml` with MBINCompiler, edit
   the XML, compile back.
3. For shader/texture edits: drop loose files under `GAMEDATA/MODS/` (5.50+) or
   `GAMEDATA/PCBANKS/` (older) so the game loads them without repacking.
4. To inspect models: NMS-View (models + skeletons); Blender via OBJ/FBX.

## Verification
- The dump does not record an end-to-end verified mod. The loose-file loading
  path and shader edits (chromatic aberration / vignette removal) are described
  as working community mods from 2016. Treat everything else as
  format-documented, not reproduced.

## Gotchas
1. **`brink.bms` extracts nothing useful.** **Cause:** files are zlib-compressed
   but the script logs them raw. **Fix:** change `log` → `clog` (size, size).
2. **PC vs console PAK mismatch.** **Cause:** on the described 2016–2023 builds
   PS4/Switch use `HGPAK` magic and zstd/Oodle while the PC uses a PSAR variant;
   since 5.50 (Jan 2025) the PC build uses HGPAK as well, so the split is no
   longer clean. **Fix:** use HGPAKtool for HGPAK archives.
3. **Repacking fails / game rejects rebuilt archives.** **Cause:** no confirmed
   repacker; console repacking is WIP. **Fix:** use loose files in
   `GAMEDATA/MODS/` (5.50+) or `GAMEDATA/PCBANKS/` (older) and never repack.
4. **Skeleton comes out misaligned.** **Cause:** rotation order differs per model
   (XZY vs XYZ). **Fix:** none known — inspect and pick the order per model.
5. **Only localization MBIN is fully understood.** **Cause:** other `Gc*` types
   are undocumented. **Fix:** use `NMS-View` / MBINCompiler where it covers the type.

## Assets
No art/audio pipeline was recorded; textures are plain `.dds`, shaders are plain
GLSL, so external assets are edited directly rather than authored via a tool.

## Cost and time
Unknown — the source is a forum-knowledge extraction, not a build log.

## Open questions
- Full MBIN spec: only `cTkLocalisationTable` is documented; other `Gc*` types unknown.
- HGPAK compression: zstd confirmed, Oodle suspected (unresolved).
- HGPAK repacking for PS4/Switch — blocked.
- Procedural planet/ship assembly logic in MBIN — not reverse engineered.
- Animation format — not documented in the threads.
- Skeleton rotation-order rule (XZY vs XYZ) — no reliable selector found.
