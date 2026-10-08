---
kind: technique
title: "Bethesda ESL light masters and plugin↔archive load pairing (the CC-merge route)"
tags: [bethesda, fallout4, starfield, skyrim, esl, light-master, ba2, plugins-txt, load-order, creation-club, cc-packer, creation-engine]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - "https://github.com/TES5Edit/TES5Edit"
  - "https://github.com/jturnley/CC-Packer"
  - "https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/TES4"
---

# Bethesda ESL light masters and plugin↔archive load pairing (the CC-merge route)

> Two engine rules drive a lot of Fallout 4 / Skyrim / Starfield mod packaging: (1) an archive
> (`.ba2`) is only loaded when a **plugin of the same base name** exists, and (2) a plugin can be a
> **light master** (`.esl`) that occupies a special slot and does not consume one of the 255 full
> load-order slots. The light flag is `0x200` on Fallout 4 and Skyrim SE, and `0x100` on Starfield.
> This note records the rules, the minimal synthetic plugin that
> satisfies rule 1, the loose-file/`plugins.txt` handling, and the practical split thresholds from
> the FO4 CC-Packer merge tool. For the per-record byte format, see the companion note on
> ESM/ESP/ESL record layout.

## When to use it

- Shipping assets (textures, meshes, sounds) in a `.ba2` when you do **not** want a real gameplay
  plugin — you still need a placeholder plugin with the same base name.
- Merging many Creation Club / DLC archives into a couple of archives to get under the plugin cap.
- Debugging "my archive loads but the game ignores it" or "textures are missing in-game".

## How

### Rule 1 — archives pair with a same-base-name plugin

Fallout 4 loads `Data/<Name> - Main.ba2` and `Data/<Name> - Textures.ba2` only if the game also
loads a plugin named `<Name>` (`.esp`/`.esm`/`.esl`). A pure-asset archive with no matching plugin
is present but never mounted. CC-Packer's `_create_vanilla_esl` exists solely to satisfy this:
its docstring states Fallout 4 requires a plugin file to exist for any BA2 to load
(FO4/CC-Packer-linux/merger.py:1544-1567).

Consequence: asset-only mods ship a **dummy plugin**. It does not have to contain records.

### The minimal synthetic placeholder plugin

CC-Packer writes a byte-exact empty light master, `_create_vanilla_esl` (merger.py:1544-1623). It
is the smallest correct `TES4`:

```
'TES4'
U32 recordSize                 (written back as len(record) - 24 at the end)
U32 flags = 0x00000001 | 0x00000200   // Master (ESM) + Light master (ESL)
U32 formID = 0
U32 versionControlInfo1 = 0
U32 formVersionAndUnknown = 0      // FormVersion U16 + unknown U16
  'HEDR' U16 0x0C
    float version = 1.0            // bytes 00 00 80 3F
    U32 recordCount = 0
    U32 nextObjectID = 0
  'CNAM' <creator>                 // 'CC-Packer\0'
  'SNAM' <summary>
  'INTV' U32 0
```

Flags `0x201` deliberately omit `0x80` (Localized) so no `.STRINGS` files are needed. The record
size is only known after building the body, so it is patched back into the 24-byte header. (The
tool's code comment cites the UESP TES4 format page, README link above.)

Note: the plugin must be a **light master** (`.esl`, flag `0x200`) to avoid eating a full-load-order
slot. A dummy `.esp` with the same job also works but costs a slot and, on FO4, is subject to the
255-plugin limit.

### Rule 2 — light masters and the slot algebra

An ESL/light-flagged plugin occupies a light slot (`0xFE<slot:12>`), up to 4096 of them, and does
not consume one of the ~255 full slots. With light modules present the highest usable full slot
is `0xFD` (`0xFC` on Starfield, which also has medium modules). The record's object ID must fit in
12 bits — so a
real gameplay plugin converted to ESL must have its object IDs compacted first. See the companion
ESM/ESP/ESL note for the exact masks and errors.

### Load order — `plugins.txt`

On Fallout 4 the enabled-plugin list is `%LOCALAPPDATA%/Fallout4/plugins.txt`; an entry prefixed `*`
is enabled. CC-Packer edits it idempotently, preserving the file's BOM
(`_add_to_plugins_txt` / `_remove_from_plugins_txt`, merger.py:1439-1550). The management tool must
not blindly rewrite the file — a wrong format or lost BOM disables plugins.

### Loose files vs archives — override order and invalidation

Bethesda engines honor loose files in `Data/` **in addition** to archives; loose files generally
win when both exist. Practical implications seen in CC-Packer:

- **Localization files** (`.STRINGS`/`.ILSTRINGS`/`.DLSTRINGS`) are extracted **loose** into
  `Data/Strings/` rather than packed (merger.py:1170-1187). If a `.strings` file stays inside the
  archive while an edited one sits loose, the loose copy usually wins — confusing results if you
  mix. Move them out so there is exactly one source of truth.
- **Archive invalidation** depends on file timestamps. CC-Packer copies (not `copy2`) the strings
  files specifically to refresh mtime: "Use copy instead of copy2 to update timestamp (helps with
  archive invalidation)" (merger.py:1174). A repacked archive that did not change its own mtime can
  be skipped by the engine.

### Format-specific packing

| Content | Archive | Notes |
|---|---|---|
| General assets | `<Name> - Main.ba2` | GNRL, compressed |
| DDS textures | `<Name> - Textures.ba2` | DX10, compressed, split when large |
| Sound (`.xwm`/`.wav`/`.fuz`/`.lip`) | `<Name> - Main.ba2` | packed **uncompressed** (codec-sensitive) |
| Strings (`.*STRINGS`) | *loose* `Data/Strings/` | not archived |

Textures **must** go in a `... - Textures.ba2` (the DX10-format archive); general assets go in
`... - Main.ba2` (GNRL). Getting this wrong yields missing/untextured meshes. CC-Packer's
`bsarch.exe` (from the xEdit project) does the packing, and its bsarch runs under Wine on Linux
(AGENTS.md; README.md:41-45).

### The CC merge route in practice

CC-Packer (`FO4/CC-Packer-linux/`) merges many `cc*.ba2` Creation Club archives into a few
`CCPacked_*.ba2` plus placeholder ESLs, shrinking plugin count (AGENTS.md:38-50; README.md:135-148):

1. Validate each CC item (plugin + `- Main.ba2` + `- Textures.ba2`).
2. Back up the originals to `Data/CC_Backup/<timestamp>/`.
3. Extract via `bsarch` into temp general and texture dirs.
4. Pull `.strings` files loose to `Data/Strings/`.
5. Separate sounds for uncompressed packing.
6. Repack GNRL + DX10 archives.
7. Write placeholder ESLs via `_create_vanilla_esl`.
8. Register in `plugins.txt`.
9. Delete the originals and temp.

## Gotchas

1. **Archive present but ignored in-game.** **Symptom:** `Data/X - Main.ba2` exists, nothing loads.
   **Cause:** no plugin named `X` is loaded, so the engine never mounts the archive. **Fix:** add a
   matching plugin (a dummy ESL is enough) and ensure it is enabled in `plugins.txt`.
2. **Textures missing / untextured after merge.** **Symptom:** meshes render with no material.
   **Cause:** DDS textures packed into a `... - Main.ba2` (GNRL) instead of a `... - Textures.ba2`
   (DX10). **Fix:** route textures to the `Textures` archive.
3. **Sound plays distorted or not at all after packing.** **Symptom:** audio breaks.
   **Cause:** `.xwm`/`.wav`/`.fuz`/`.lip` compressed in the archive. **Fix:** pack sounds
   uncompressed.
4. **Edited strings have no effect.** **Symptom:** old text persists. **Cause:** an archived copy
   wins, or the loose file's mtime was not refreshed so archive invalidation did not fire.
   **Fix:** keep strings loose only, and touch/re-copy (not `copy2`) to refresh timestamps.
5. **Plugin cap / "too many plugins".** **Symptom:** game or xEdit complains about load-order size.
   **Cause:** every dummy plugin added as a full ESP. **Fix:** use light masters (`0x200`) and,
   when converting real plugins, compact object IDs to fit the 12-bit light range.
6. **`plugins.txt` loses entries / all mods disable.** **Symptom:** mods vanish after a tool edit.
   **Cause:** the tool rewrote `plugins.txt` without preserving BOM/format, or dropped the `*`
   enable prefix. **Fix:** edit idempotently and preserve BOM (CC-Packer does).
7. **Huge texture archive → "Brown Face" / garbled textures.** **Symptom:** NPC faces render brown.
   **Cause:** an oversized `Textures.ba2`. **Fix:** split texture archives. Note: the tool's code
   uses a **7 GB uncompressed** split threshold (merger.py:1246), while its README says `>3 GB`;
   the discrepancy is unresolved (see Open questions).

## Seen in

- FO4 CC-Packer-linux (unpublished local tooling) — synthetic ESL, merge flow, `plugins.txt`
  editing, string/sound/split handling.
- xEdit / BSArch (unpublished local checkout) — archiving and the plugin-format reference
  (`techniques/bethesda-plugin-record-format-esm-esp-esl.md`).
- Applies to Fallout 4, Skyrim SE, Starfield (medium modules on Starfield), and their VR variants.

## Open questions

- **Split threshold:** CC-Packer code uses 7 GB uncompressed (`MAX_SIZE = int(7.0 * 1024 * 1024 * 1024)`,
  merger.py:1246) but README.md claims `>3 GB` prevents the Brown Face bug. Which value is actually
  required is unverified — treat 7 GB as what the tool does, and the 3 GB figure as a claim.
- Whether the placeholder ESL's `flags`/subrecord set is the *minimum* the engine accepts, or just
  what this tool emits. Not tested against the game with a stripped variant.
- Whether the engine treats loose files as always overriding archives, or only when newer — stated
  here from tool behavior and common knowledge, not from an engine trace.
- Starfield medium modules (`0xFD`, `0x400` flag) are documented from xEdit's definitions only; no
  hands-on packaging test.
- The exact Creation Club plugin/archive base-name pairing rules beyond `- Main`/`- Textures` (e.g.
  multi-part texture archives) are inferred from CC-Packer's naming, not an official spec.
- The Wine-only `SFHighPriorityLauncher`/Wine monitor-region note in `SF/` is a Wine compat fix,
  unrelated to plugin/archive loading, and is not part of this technique.
