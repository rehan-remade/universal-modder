---
kind: game
title: 'Unpack a BeamNG.drive mod before editing: rebadge and taillights on an unpacked vehicle'
game: BeamNG.drive
games_also: []
game_version: '0.40.4.0.296339 (Steam)'
platform: windows
engine: unknown
route: asset-only
tools: ["Blender 4.5.10 (headless import/render)", "PowerShell", "XML editing of the .dae"]
anti_cheat: 'none known: offline single player, files edited in current\mods\unpacked (not audited)'
status: in-progress
agents:
- OpenCode
humans: []
date: '2026-11-04'
links: []
tags: [beamng, vehicle, dae, jbeam, materials, glowmap, unpack, blender, rebadge, taillights]
---
# Unpack a BeamNG.drive mod before editing: rebadge and taillights on an unpacked vehicle

> A Daewoo Lanos vehicle mod was rebadged and got new rear lights by editing the unpacked copy of the
> mod, not the zip: the `.dae` was changed node by node, the `jbeam` files were left alone, and only
> material names that already existed were used. The edited DAE re-imports with all 96 nodes and the
> original names. Not verified: loading the rebuilt vehicle in the game (needs a play test).

## Setup
- BeamNG.drive 0.40.4.0.296339 from Steam, `C:\Program Files (x86)\Steam\steamapps\common\BeamNG.drive`.
  The Uninstall registry entry still points at a `D:\SteamLibrary\...` folder that does not exist; the
  authoritative path is in `libraryfolders.vdf`.
- User folder: `%LOCALAPPDATA%\BeamNG\BeamNG.drive\current`; mods live in `...\current\mods`.
  `Documents\BeamNG.drive\mods` exists but is empty and is not used by 0.40.
- Source zip `%USERPROFILE%\Downloads\Daewoo_Lanos_Revamp.zip` (99 159 528 B, 206 entries). Inside there is
  no top-level `info.json`: it sits at `vehicles/lanos/info.json`.
- Blender 4.5.10 portable, used headless (`-b --factory-startup`) for import checks and renders.

## Route and why
Asset-only edits on an already-unpacked mod. No loader, no Lua extension, no repack needed: the game reads
`current\mods\unpacked\<name>` directly, and `db.json` already had the entry (`active: true`,
`orgZipFilename: /mods/Daewoo_Lanos_Revamp_040.zip`).
Two routes were rejected:
- Repacking the whole vehicle from the Downloads zip - the installed copy is a slightly different build
  (`lanos.jbeam` 5 629 vs 5 623 B, `main.materials.json` 18 411 vs 18 348 B, `materials.cs` 10 412 vs
  10 407 B; `lanos.dae` identical in size), so the zip is not the build the game actually runs.
- Full re-export of the 77 MB DAE from Blender - a re-export renames nodes and rewrites texture paths, and
  the `jbeam` files reference those node names.

## How the game works (what we had to learn)
- Vehicle mod layout: `vehicles/<model>/` with `info.json` (brand, name, `default_pc`, paint list),
  `.pc` configurations (format 2, `model` field), `jbeam` parts, `materials.cs` / `materials.json` /
  `main.materials.json`, and the `.dae` plus textures.
- `jbeam` binds geometry by node name: `lanos_taillight.jbeam` has flexbodies `lanos_taillight_L/R`, and
  `lanos_trunk.jbeam` has `lanos_trunklight_L/R`; `lanos_body.jbeam` pulls in the part files. Renaming a DAE
  node therefore silently detaches a part.
- Material definitions for this vehicle are not in `main.materials.json` (that file holds `pessima_*`
  templates for glass, dash, headlights) - the real ones are in `materials.cs`, plus one entry in
  `materials.json`. Lens colour maps and glow/translucency are set there, not in the DAE.
- The DAE alpha does not control glass in game: the lens caps `lanos_taillight_L/R` ship with
  `transparent 0.243` and no texture, and the game renders them with `colorMap vehicles/lanos/daewoolanosport.png`
  plus `translucent`/`Sub`.
- Colour sections of a light cluster can be faces inside a bigger mesh rather than separate nodes: the red
  section lives in `lanos_body` (`lanos_gaby`), the small stop/reverse sections in `lanos_trunk`
  (`lanos_stop`, `lanos_revers`). They cannot be replaced without touching that mesh.
- A badge is not necessarily an object either: the Daewoo emblem was an island of `lanos_chrome` inside
  `boot_L0-mesh` (98x4x38 mm at (0; 2.080; 0.968)), the same material used for every other chrome part.
- Axis convention in this mod's DAE: `+Y` is the rear, `X` is width, metres.

## Build steps
1. Unpack into a temp dir, never in place and never over the zip:
   `Expand-Archive <zip> -DestinationPath %TEMP%\opencode\lanos_work\src`
   (198 files, 234 MB).
2. Copy the vehicle folder for the edit: `src\vehicles\lanos` -> `chevrolet_mod\vehicles\chevrolet_lanos`
   (193 files). The original unpack, the installed mod and the zip stay byte-identical.
3. Edit the copy's `.dae` surgically: delete the triangles of the old badge/text and insert new geometry
   (2 172 vertices, 724 triangles) bound to an existing material, with normals facing out. 26 edit sites,
   script kept next to the copy, `.dae` backup next to it.
4. Reuse material names for the lenses instead of adding new ones: outer caps got the existing
   `lanos_gaby` (red) on the lower half plus `instance_material lanos_gaby`, inner caps were switched from
   `lanos_steklofar` to the existing `lanos_revers`, and the node binding was renamed with them.
5. Check by re-importing the DAE: 96 nodes / 96 geometries, mesh objects 96, key names unchanged,
   `nan_vertices` 0, and `float_array` counts plus every `<p>` index consistent.
6. Render before/after in headless Blender to look at the result; build the `.pc`/`info.json` and the zip
   only after the geometry is right.

## Verification
Done: re-import round-trip of the edited DAE (all 96 nodes, names unchanged, 0 NaN introduced, index
counters consistent), material assignment read back per cap, Cycles renders of the rear at 1280x720.
Not done: loading the rebuilt vehicle in the running game, and no in-game light/glow check - the mod was
not installed while the DAE was being edited.

## Gotchas
1. **Editing the zip or the live `unpacked` copy.** Symptom: nothing to roll back to once the game or a
   mod update rewrites the folder. **Cause:** the unpacked folder is the game's working copy. **Fix:** unpack
   to temp, copy the vehicle folder, edit the copy; keep the original zip untouched as the reference.
2. **Full DAE re-export from Blender.** Symptom: the vehicle loads with missing parts or white textures.
   **Cause:** re-export renames nodes and texture paths while `jbeam` binds geometry by node name. **Fix:**
   edit the DAE XML in place (delete/insert triangles, add nodes with the old names) and keep the material
   names; verify with a re-import listing of all node names.
3. **Adding a new material for a lens.** Symptom: the new lens has no glow or is opaque in game, even though
   it looks right in Blender. **Cause:** colour maps, `translucent` and glow come from `materials.cs`, not
   from the DAE. **Fix:** reuse existing material names (`lanos_gaby`, `lanos_steklofar`, `lanos_revers`,
   `lanos_povL/R`, `lanos_stop`) and, where a node needs a second material, add
   `<instance_material ...>` to the node instead of inventing a material.
4. **Trusting the DAE for glass.** Symptom: glass looks transparent in Blender and wrong in game.
   **Cause:** the DAE alpha (`transparent 0.243`, no map) is not what the game uses. **Fix:** check
   `materials.cs` for the real `colorMap`/`translucent` and judge by an in-game screenshot, not a render.
5. **Pre-existing NaN vertices.** Symptom: import warnings about NaN in UVs. **Cause:** the shipped
   `chassis_L0-mesh-map-0/1` already contains 2 430 NaN literals. **Fix:** diff the count before/after the
   edit instead of trying to clean them.
6. **Assuming the Downloads zip equals the installed build.** Symptom: fixes "disappear" after install.
   **Cause:** the `unpacked` copy was a slightly different build (jbeam/materials byte sizes differ).
   **Fix:** edit the copy of the installed folder when the goal is to fix what the game runs.

## Assets
Geometry for the new badge and lettering was generated headless in Blender (JSON) and written into the DAE
XML by a script; no external asset packs, no generated textures. Renders used Cycles CPU (40 spp).

## Cost and time
Recon (unpack, structure, materials) about 10 minutes; DAE edit plus re-import and renders about 30 minutes
of wall clock in one session.

## Open questions
- `vehicles/lanos/info.json` declares `default_pc: LX_M`, but no `LX_M.pc` exists in the archive; how the
  game builds the default configuration is unknown.
- Whether the game must be restarted (or the mod re-selected) to pick up an edited DAE in
  `current\mods\unpacked` - not tested here.
- Whether the `pessima_*` templates in `main.materials.json` are still required once `materials.cs` defines
  the vehicle's own materials is unclear.
- No in-game validation of the edited vehicle was done in this session.
