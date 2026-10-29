---
kind: game
title: "Bigger Units: every battle model 1.75x, including units from Workshop mods, via a generated DB patch pack"
game: "Total War: WARHAMMER III"
games_also: []
game_version: "9.0.4.0 (Warhammer3.exe), Steam build 25961564, Windows 11"
platform: windows
engine: native
route: data
tools: ["Python 3.14 (stdlib compression.zstd)", "agent-written PFH5 pack reader/writer", "RPFM schema_wh3.ron"]
anti_cheat: "none (EOS SDK ships for crossplay only); tested in single-player custom battles and campaign"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-29
links: ["valkia-khorne-subjugation-reusing-archaon-dilemmas.md"]
tags: [warscape, total-war, db-tables, variants, unit-scale, formation-spacing, compatibility-patch, generator, workshop]
---

# Bigger Units: every battle model 1.75x, including units from Workshop mods, via a generated DB patch pack

Every unit model in battle (infantry, lords and their alternate looks, mounts, monsters, chariots, war
machines) is drawn 1.75x bigger, and formation spacing is widened by the same factor so soldiers don't clip.
Hitboxes, collision, mass and stats are unchanged. Because the result has to cover units from whatever mods
the player has enabled, the mod is a small generator that reads the player's own vanilla DB plus every
enabled mod and writes one patch pack. Confirmed in game by the human player: infantry, cavalry (riders
seated correctly), monsters, Daemon Princes and units from Workshop mods.

## Setup
- Total War: WARHAMMER III, Steam app 1142710, `Warhammer3.exe` 9.0.4.0, Steam build 25961564, Windows 11,
  AMD RX 7900 XT. 136 Workshop/local mods enabled, managed with a third-party mod manager that writes
  `used_mods.txt`.
- Python 3.14 via the `py` launcher. 3.14's standard library has `compression.zstd`, so reading CA's
  zstd-compressed packs needs no third-party package.
- RPFM's schema file `schema_wh3.ron` (RPFM downloads it into its config folder). It gives every DB table's
  field names and types per table version; the generator parses it with a few regexes.

## Route and why
- **Data only:** two DB tables in one PFH5 mod pack. No script, no native code.
- **Why a generator instead of a static pack:** DB rows override by key, so a pack only scales the variants it
  contains. A static "all vanilla variants x1.75" pack would miss every unit added by other mods, and would
  also overwrite mods that edited a vanilla variant (reverting their mesh). Reading the player's actual load
  order and writing the *winning* row for each key, with only `scale` changed, covers both.
- **Rejected:** a Lua route. Campaign/battle Lua has no call that rescales a unit's model, and DB values are
  read at load, so script can't do this.
- **Collision deliberately untouched** (the player's choice): `battle_entities` `radius`/`height`/`mass`
  would change hit chance, mass and balance. Spacing alone fixes the visual clipping.

## How the game works (what we had to learn)
- **Model scale lives in `variants_tables`** (v6 at this build): `variant_name` (key), `tech_folder`,
  `variant_filename`, `low_poly_filename`, `mount_scale`, `scale`, `scale_variation`,
  `super_low_poly_filename`. `scale` is the whole entity's scale (most vanilla rows are 1.0, 1.15, 1.2...).
- **Which variants are battle units:** search the schema for fields whose `is_reference` points at
  `("variants", "variant_name")`. The unit-relevant ones are:
  - `unit_variants_tables.variant` (soldiers, lords);
  - `mounts_tables.variant`;
  - `battlefield_engines_tables.variant` (chariots, artillery, engines);
  - `animals_tables.variant`;
  - `unit_variant_upgrades_tables.variant_name`;
  - `agent_uniforms_tables.battle_filename` (lords' alternate battle looks from art sets: without this,
    many named-lord variants from mods are missed);
  - `battle_personalities_tables.variant`.

  With vanilla plus 22 model-adding mods this selected 3,581 of 4,476 variants. Left out: Daemon Prince
  armory parts (`armory_item_variants`, about 560 rows), campaign-map models (`*_campaign*`, `*_fort`) and
  unreferenced rows.
- **Armory parts and mounts follow the base model.** Daemon Prince parts were not scaled, and they still
  matched the 1.75x body. Riders and mounts are scaled separately (rider variant via `unit_variants`, mount
  via `mounts_tables`), and `mount_scale` did not need changing: riders sat correctly.
- **Formation spacing is `unit_spacings_tables`** (v7, about 170 rows, key `key`, referenced from
  `land_units.spacing`). The distance columns are `close_`/`loose_`/`dismounted_close_`/
  `dismounted_loose_formation_spacing_` + `horizontal`/`vertical`/`variation`. `testudo_*` and
  `shield_wall_*` look like multipliers (0.85, 1.0) and were left alone, as were the `ship_*` rows. Side effect
  of scaling them: each unit's battle line is 1.75x wider.
- **Override priority** (what decides the "winning" row): enabled mods in `used_mods.txt` order, then within
  a pack the table files sorted by name (`!` sorts first), then vanilla `db.pack`; the first row for a key
  wins. Naming both the pack and its table files with a long run of `!` puts the patch ahead of everything.
  Some mod managers also generate merged patch packs named `!!!!...`; check that none of them carry the
  tables you patch (here they carried `land_units`, `main_units`, `battle_entities`, but not `variants` or
  `unit_spacings`).
- **PFH5 layout, as used here:** `PFH5`, u32 flags (3 for a mod pack), u32 dependency count, u32 dependency
  index size, u32 file count, u32 file index size, u32 timestamp (28 bytes; flag 0x100 adds 20 more). The
  file index is, per file, u32 size, (u32 timestamp only if flag 0x40), u8 compressed, NUL-terminated
  backslash path. Data follows the index in the same order. Compressed entries are u32 uncompressed size +
  a zstd frame. Writing an uncompressed mod pack (compressed byte 0) loads fine.
- **DB table binary:** optional GUID marker `FD FE FC FF` + u16 length + UTF-16 GUID, version marker
  `FC FD FE FF` + i32 version, one u8, u32 row count, then rows field by field: `StringU8` = u16 length +
  UTF-8 bytes, `OptionalStringU8` = u8 flag then a string if 1, `F32`/`I32` 4 bytes, `I64` 8, `Boolean` 1.
  Decoding vanilla `variants_tables` and `unit_spacings_tables` and re-encoding them gave byte-identical
  output, which is a cheap check that the decoder is right.

## Build steps
1. Read the schema and build a decoder for the tables above (about 150 lines of Python).
2. Walk the sources in priority order: each enabled mod from `used_mods.txt` (resolve each pack in
   `data\` or one of the `add_working_directory` folders), then vanilla `data\db.pack`. Skip your own output
   pack.
3. For each `variants_tables` / `unit_spacings_tables` file, keep the first row seen per key. For each
   referencing table above, collect the variant keys it uses.
4. Write rows: every winning variant whose key is referenced, with `scale *= 1.75`, and every non-ship spacing
   row with its 12 distance columns `*= 1.75`. Rows from older table versions get their missing fields
   filled from the newest template. Encode with the newest version found (vanilla's) and keep its GUID.
5. Write one PFH5 mod pack with `db\variants_tables\<!!!...name>` and
   `db\unit_spacings_tables\<!!!...name>` to `data\`, then enable it in the launcher or mod manager.
6. **Re-run after any change to the mod list**, or new units stay normal size.

## Verification
- **Offline:** both tables round-trip byte-for-byte against vanilla; the written pack re-reads with the
  expected row counts (3,581 variants, 170 spacings); no table in any of the 136 enabled mods failed to
  decode against the schema. The only key conflicts were mods overriding vanilla rows (15), which the
  generator resolves by load order.
- **In game:** the human player ran custom battles and the campaign with the pack enabled and reported
  units 1.75x bigger with wider formations, cavalry riders seated correctly, Daemon Princes correct, and
  Workshop units scaled.
- **Not verified:** pathing of the wider formations in sieges and narrow maps; multiplayer (the pack changes
  DB data, so every player would need the identical generated pack).

## Gotchas
1. **A static pack misses mod units and can revert other mods.** **Cause:** DB rows override by key; a row
   copied from vanilla replaces a mod's edited row (its mesh path, not just the scale). **Fix:** generate from
   the actual load order and copy each key's winning row, changing only `scale`.
2. **Named lords from mods stay normal size.** **Cause:** their alternate looks come from art sets through
   `agent_uniforms_tables.battle_filename`, not `unit_variants`. **Fix:** include that reference (and
   `battle_personalities.variant`); coverage went from 2,452 to 3,581 variants.
3. **Bigger models clip into each other in formation.** **Cause:** spacing is a fixed distance in
   `unit_spacings_tables`, independent of model size. **Fix:** scale the spacing distance columns by the same
   factor. Hitboxes stay as they were.
4. **Daemon Prince parts look like they need their own scale.** They don't: armory parts follow the base
   body. Don't scale `armory_item_variants`.
5. **`um scan` reports "unknown native engine".** **Cause:** no Warscape signature in the scanner. **Fix:**
   ignore it; Warscape mods are packs (see the Valkia note linked above).
6. **The toolkit CLI fails with `No module named 'numpy'` on a system Python without uv.** **Cause:** the CLI
   imports every module at start. **Fix:** this route needs none of it; Python 3.14's stdlib reads zstd packs.
7. **Not a mod bug, but it cost hours while testing:** after the player swapped a 1080p second monitor (left
   of the main one) for a second 2560x1440 one, the game drew its UI only in the right half of the main screen
   (menu and campaign HUD; the 3D view filled the screen). Disabling mods, windowed/fullscreen, restarting and
   AMD Eyefinity on/off didn't help (Eyefinity made it a 1024x1024 corner render). **Fix:** in Windows Display
   settings, drag the second monitor to the other side, apply, then drag it back and apply. That rewrote the
   saved monitor layout and the game has drawn correctly since. Check this before suspecting a UI mod.

## Assets
None. All meshes are the game's or the installed mods' own; only numbers change.

## Cost and time
One session: about an hour from recon to an installed pack, then human playtesting. Most of the remaining
time went to gotcha 7.

## Open questions
- Do 1.75x-wide formations path badly through settlement streets and gates? If so, a smaller spacing factor
  (for example 1.4 with models at 1.75) may be the better trade-off.
- Should campaign-map figures be scaled to match? They were left out on purpose.
- Scaling `battle_entities` collision as an option, for players who want "realistic" big units and accept the
  balance change. Some mod managers ship their own merged `battle_entities` patch, so that would have to be
  generated after theirs.
