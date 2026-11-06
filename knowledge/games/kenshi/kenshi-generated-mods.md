---
kind: game
title: 'Data mods without FCS: generated .mod files, Blender weapons, a race, custom weapon grades'
game: Kenshi
games_also: []
game_version: '1.0.65 x64 (Newland) as the game reported it; Steam public branch buildid 13871665, which is 1.0.68 (see Setup)'
platform: windows
engine: native
route: data
tools: [Python 3.12, Blender 5.2.2, "Kenshi_IO_Continued (2024-08-21, patched)", OgreXMLConverter (bundled with Kenshi IO), Pillow, numpy, OpenConstructionSet (source read only), dnfile]
anti_cheat: none (offline single-player)
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-15'
links:
- https://github.com/lmaydev/OpenConstructionSet
- https://codeberg.org/Kindrad/Kenshi_IO_Continued
- https://github.com/BFrizzleFoShizzle/RE_Kenshi
tags: [kenshi, ogre, physx, fcs, mod-file-format, blender, weapons, races, kep, data-mod]
---
# Data mods without FCS: generated .mod files, Blender weapons, a race, custom weapon grades

> In Kenshi on Steam (reported as 1.0.65; see Setup) we built three data mods without opening FCS. All records
> were written as v17 `.mod` files from Python. The mods add: new melee weapons (low-poly rebuilds of
> AI-generated `.glb` models, exported with a patched Kenshi IO addon), unique NPCs and characters that always
> spawn with them, a hand-wrap armour for martial arts, a custom weapon grade with its own forge, and a new
> playable race cloned from Greenlander.
> The human tested everything in the real game: grips, scabbards, damage, spawns, race, appearance.
> The game logs were used to confirm assets load without errors.

## Setup
- Kenshi 1.0.65 x64 as reported, Steam public branch, Windows 11. RE_Kenshi 0.3.5 with KenshiLib 0.5.0 was
  installed, but nothing here needs it. Steam's public build 13871665 is 1.0.68 (Lo-Fi's 1.0.68 patch notes and
  the branch update are both 2024-04-01). The 1.0.65 is most likely the 1.0.65-compatible executable that
  RE_Kenshi's installer creates for 1.0.68 installs (RE_Kenshi README). Data mods don't depend on the exe build.
- Other Kenshi notes: the [1.0.65 recon](kenshi-1-0-65-native-ogre-recon.md) (engine, FCS, load order,
  RE_Kenshi) and the [first-person camera plugin](first-person-camera-and-wasd-on-vanilla-kenshi-1-0-68-an-ogr.md)
  (native code on vanilla 1.0.68).
- The install was heavily modded: 26 mods, including a 10 GB Russian overhaul (Second Life of Kenshi) that
  bundles KEP (Kenshi Extension Plugin). The overhaul changes vanilla records, for example the quality-grade
  textures and the Greenlander limb HP. Always read records merged in load order, never just the base files.
- Blender 5.2.2 with the vendored Kenshi_IO_Continued addon (officially for Blender 3.6), loaded from a folder
  by script rather than installed. 4 small patches were needed (Gotcha 1).
- Python tools: a v16/v17 `.mod` reader and writer, a type-15 data-file reader and writer (saves, `.platoon`,
  `.bod2`), and a record-merge helper. The writer round-trips an FCS-saved mod byte for byte, except the
  save counter.

## Route and why
- **Data route.** Records generated in code instead of clicking through FCS: reproducible, diffable, and able to
  patch hundreds of records at once (a race had to be added to about 550 lists).
- **Not used, but checked:**
  - C++ through RE_Kenshi/KenshiLib (needs the VC++ 2010 v100 toolset). The only reason to go there was gating
    a crafting grade by smithing skill 100.
  - An equippable "fist weapon" with the martial-arts skill category. No vanilla or community precedent, and
    behaviour unknown.

## How the game works (what we had to learn)
- **`.mod` v17 layout** (matches OCS's reader):
  - Header: type 17, header length, then version, author, description, comma-separated deps and refs, then
    save count, last-merge, and byte-sized counts of merge and delete entries.
  - Then last id, record count, records.
  - Record: an int that is the whole record's byte length including itself; type id; id; name; stringId; change
    word `(saveCount << 4) | kind`, where kind 0 = new, 1 = changed, 2 = renamed (OCS's `ItemChangeType`).
    Then dictionaries of bool, float, int, vec3, vec4, string and **file** (file paths are a separate
    dictionary from plain strings), reference categories `(sid, v0, v1, v2)`, and instances.
  - A ref whose three values are all `2147483647` removes that ref when merged.
  - Kenshi merges per field and per ref, so a "changed" record only needs the fields and refs you touch.
- **Type-15 data files** (saves, `.platoon`, `.bod2` body presets): type 15, last id, count, then records like
  above, except the leading int of each record is not a length: it's 0, or the instance count for an
  `InstanceCollection` record (as OCS's writer does it).
  - A `.bod2` is a single `CharacterAppearance` record (sex, about 50 sliders, head, hair, beard, race ref).
  - Copy a character's `CharacterAppearance` from their `.platoon` in a save. Pair it with the `Stats` record
    whose numeric id is one higher. Write it as a `.bod2` and point the Character's `body` file field at it.
    The character then always spawns with that look.
- **Melee weapon visuals ignore the mesh's material.**
  - Texture and normal map come from the quality model (`MaterialSpecsWeapon`: Rusted Junk … Meitou). The
    manufacturer's `weapon models` refs give each model its level (val0, 1–100).
  - All vanilla grade textures share one 1024² atlas layout. Roughly: u 0–0.11 bright edge metal; 0.11–0.37
    heavy metal body; u 0.38–0.68 × v 0–0.58 grip/handle; same u × v 0.58–1 fittings; u 0.68–1 long blade metal,
    bottom strip trim.
  - UV a new mesh to those regions and every vanilla grade "just works".
  - A per-weapon texture is only possible by giving the weapon its own quality model, and therefore its own
    manufacturer.
- **Crafted weapons are always manufacturer "Homemade"** (`PLAYER_WEAPONS`). Grades become craftable through
  Research `enable weapon model`.
  - Each smithing bench is a Building → BuildingFunctionality with an explicit `weapon crafts` list of models and
    a `tech level` cap. A model listed only on your own bench can be forged only there.
  - There is no data field for "needs smithing skill N".
- **KEP adds fields to `MATERIAL_SPECS_WEAPON`:** `cut/blunt/pierce damage mod`, `bleed mod`,
  `armour penetration mod`, `combat weight mod`, `length mod`, `indoors mod`, and others (see the overhaul's
  `fcs.def`). Putting a grade's strength there makes crafted (Homemade) copies as strong as handed-out ones.
- **Character weapon refs:** `weapons` (quantity, slot 0 hip / 1 back, absolute chance %). Many vanilla records
  have chance 0 and still carry their weapon, but use 100 to be sure. `weapon level` picks the manufacturer,
  which sets the grade. Delete the other weapon refs, or the game may pick them.
- **Race lists that matter:**
  - Armour `races` and `races exclude`, dialogue `my race`, `target race` and `my subrace`, weapon `race damage`.
    Add the new race wherever Greenlander is named.
  - **Do not** add it to Faction `races`: that is the race mix a faction spawns with, and new-race NPCs appear
    all over the world.
  - Combat anatomy refs are (hit chance, health). HP is per race, not per gender, so use two subraces in your own
    RaceGroup for different male/female HP.
  - Playable needs an `editor limits` XML and membership in a RaceGroup.
- **Stat enum** for race `stats good/bad` is a sequential `StatsEnumerated`. It lives in the FCS .NET assembly and
  can be read from its metadata with `dnfile`, no decompiling. The game data confirms it (Greenlander good =
  science, farming, cooking; heal stat 9 = medic). Ids used here: 2 melee attack, 19 melee defence,
  30 martial arts, 32 dodge.
- **Global constants:**
  - `damage multiplier` (0.65) scales weapon damage only. Martial arts has its own `unarmed damage mult`, and
    crossbows have `pierce damage multiplier`.
  - The new-game/import "Global damage multiplier" slider is per save: stored as `gdm` in the save's Camera-state
    record next to `rs`, `ps`, `bs`, `ht`, `cod`, `nnm`. Its range is hard-coded in the exe.
- **Weapon mesh conventions** (OGRE axes):
  - Y along the weapon, origin = main-hand grip, 1 unit ≈ 10 cm. Heavy weapons are 16–21 long with the grip
    about 25% from the bottom.
  - Katana edge on +Z, blade bowing toward +Z, tip curving back toward −Z.
  - Katanas need three meshes: sheathed, bare, and sheath alone.
  - Ground physics is a PhysX 2.8 NXU XML in Blender axes (Z up). It is one dynamic actor with one convex shape.
    Raw points/triangles with `NX_CF_COMPUTE_CONVEX` and empty cooked data load fine.
  - Body mass in vanilla files is not proportional to item weight, so scale relative to the template file you copy.

## Build steps
1. Read merged records in `mods.cfg` order. Copy a vanilla record as the template and change only what you need.
2. Write new records plus "changed" records (refs only) with the v17 writer. Validate before installing:
   - every ref resolves in the merged data;
   - every file path has no control characters and points at a real file.
3. Weapons from an AI `.glb`:
   - PCA-align it, measure silhouettes and profiles, and rebuild a clean low-poly (about 250–310 tris, vanilla
     heavy weapons are 316–329);
   - give every face an explicit outward direction;
   - UV it to the vanilla atlas regions;
   - export with Kenshi IO through an ASCII temp folder. Its bundled converter writes
     `[MeshSerializer_v1.40]`; the game's own meshes are v1.100 (recon note), and it loads both;
   - check winding in the exported XML before shipping.
4. Physics: copy a vanilla item XML as the template, replace the hull and mass properties.
5. Textures: DDS DXT5 diffuse with gloss in alpha, DXT1 normal (green flipped, DirectX), full mip chain.
   Pillow writes one level at a time; concatenate the levels and patch the header.
6. Put the mod folder in `mods/`, append it to `data/mods.cfg` with the game closed, and back up `mods.cfg` first.

## Verification
- **Oracle:** the human played in game and reported back:
  - weapons in hand, on back and on hip, attacks, and on the ground;
  - NPCs spawning with their gear and quality;
  - start characters with the new race and the saved appearance;
  - damage changes;
  - no new-race NPCs in the world after the faction fix.
- **Logs** after every run:
  - `kenshi_info.log`: mods loaded, in order;
  - `kenshi.log`: our meshes and textures load with no errors; auto-icon textures appear as
    `<weapon sid>.<model sid>.png`;
  - `RE_Kenshi_log.txt`: plugin and stat events.
- **Not verified:**
  - exact damage numbers: nothing logs per-hit damage;
  - the final percentage of the race's natural armour;
  - whether `damage multiplier` affects crossbows;
  - KEP fields without KEP installed: they are expected to be ignored.

## Gotchas
1. **Kenshi IO fails in Blender 4.1+/5.x.** **Cause:** `import imp` (removed in Python 3.12), `use_auto_smooth`,
   `calc_normals_split`, `mesh.vertex_colors`. **Fix:** alias `importlib` as `imp` and guard the rest with
   `hasattr`/`getattr`. Then call `OgreImport.load`/`OgreExport.save` directly from a script: the operators
   expect a file-browser `files` list.
2. **Exported `.mesh` silently missing.** **Cause:** OgreXMLConverter cannot open non-ASCII paths (a Cyrillic
   folder name). **Fix:** export into an ASCII temp folder, then copy.
3. **Haft looks hollow and cut off in game but fine in Blender.** **Cause:** `bmesh.ops.recalc_face_normals` on an
   open tube flipped every face inward; Blender renders backfaces, Kenshi culls them. **Fix:** build every face
   with an explicit outward direction, and run a winding check on the exported XML: compare each face normal with
   the direction from the centre of its own cross-section.
4. **Katana held "the wrong way" (edge up, tip curling down).** **Cause:** the exporter maps Blender +Y to OGRE −Z;
   the vanilla edge is on OGRE +Z. **Fix:** compare edge side and curvature with `katana05_bare` and mirror the
   model (mirror Y, then reverse faces).
5. **Gap between blade and guard.** **Cause:** the first blade station sat above the tsuba, and the blade root was
   open. **Fix:** start the blade inside the guard.
6. **PCA basis came out mirrored.** **Cause:** `thick = cross(axis, bend)` makes a left-handed basis; harmless for
   silhouettes, but it inverts normals when used to bake. **Fix:** use `x = y × z` and assert `det > 0`.
7. **Corrupt file paths in generated records.** **Cause:** Python string escapes in Windows paths: `\f`, `\b`,
   `\1`, `\r` inside `"mesh\flint02.mesh"`. **Fix:** double the backslashes, and make the build fail if any file
   field has a control character or points at a missing file.
8. **Low-gloss texture regions came out dark red or olive.** **Cause:** Pillow's RGBA resize premultiplies by
   alpha, and alpha here is the gloss mask (near 0 on wood). **Fix:** resize RGB and alpha separately.
9. **New race appeared all over the world.** **Cause:** it was added to Faction `races` (the spawn mix).
   **Fix:** leave Faction lists alone; armour and dialogue lists are safe.
10. **Martial-arts damage ignored a global damage mod.** **Cause:** unarmed damage has its own
    `unarmed damage mult`. **Fix:** scale both constants.
11. **Copying a vanilla manufacturer as "neutral" carried hidden penalties.** **Cause:** Ancient is cut ×0.9,
    weight ×0.7, price ×0.8. **Fix:** read and state every multiplier you copy.
12. **The overhaul replaces textures and stats of vanilla records.** **Cause:** the overhaul mod overrides them.
    **Fix:** compare against vanilla-only and merged data before saying "vanilla value".
13. **"Global damage multiplier" in the new-game screen is not a constant.** **Cause:** it is saved per save
    (`gdm`). **Fix:** a constants mod applies to all games; editing `gdm` in a save is the per-game way.

## Assets
- Two axes and a katana were rebuilt from user-supplied AI-generated `.glb` models (500–700k tris, twisted or
  bent). The low-poly is built from measured profiles.
- One axe's texture was painted procedurally in Python (engravings, burnt wood, leather straps). It was not used
  in game, because melee weapons take their textures from the grade.
- High-poly → low-poly bakes (colour, roughness, metal, normal) with Cycles, selected-to-active.
- Recolours: black hand-wrap textures and a black-and-gold grade atlas, made from the vanilla atlas luminance.

## Cost and time
About two long sessions, including recon. Most of the time went into the Blender addon fixes, katana
orientation and backface issues found in game, and learning the quality-grade system.

## Open questions
- Which executable ran: Steam's 1.0.68 build or RE_Kenshi's 1.0.65-compatible one (see Setup).
- Exact damage formula: how the level, the manufacturer mods and the KEP model mods combine.
- Whether `damage multiplier` affects crossbows.
- A true "smithing skill ≥ 100" crafting gate needs a RE_Kenshi/KenshiLib plugin that hooks crafting.
- Making an equippable martial-arts weapon (skill category 5) is untested.
