---
kind: technique
title: 'Cyberpunk 2077 .archive conflicts from the index table: FNV1a64 backslash path hashes, WolvenKit names, load order,
  and a scripted Nexus install loop'
status: working
agents:
- Claude Code (Fable 5.1)
humans:
- Dexiom
date: '2026-10-24'
links:
- https://github.com/WolvenKit/WolvenKit
- https://wiki.redmodding.org/cyberpunk-2077-modding
- https://app.swaggerhub.com/apis-docs/NexusMods/nexus-mods_public_api_params_in_form_data/1.0
- https://api.nexusmods.com/v2/graphql
tags: [cyberpunk2077, redengine, archive, fnv1a64, wolvenkit, nexus, nexus-api, nxm, load-order, vortex, mod-manager, um-cp77, um-nexus]
---
# Cyberpunk 2077 .archive conflicts from the index table: FNV1a64 backslash path hashes, WolvenKit names, load order, and a scripted Nexus install loop

> A REDengine 4 `.archive` lists every file it carries as a 64-bit path hash in a small index table at the end
> of the file, so an agent can tell which mods override the same paths, and which vanilla files, by reading a
> few KB per archive and never unpacking anything. This note records the byte layout, the hash rule, how to get
> names back, the game's load order, and the Nexus API calls that turn "install the top texture mods" into a
> script (`um cp77`, `um nexus` in this repo).

## When to use it
- Installing more than a handful of Cyberpunk 2077 mods and wanting to know, before launching, which
  archives collide and who wins.
- Writing or scripting a mod manager for a REDengine 4 game: install, track every placed file, uninstall
  exactly those files, check Nexus for updates.
- Any time a mod page offers five variants of one `.archive`: the hash sets show whether they are the same
  paths (pick one) or additive (stack them).

## How

### The archive index (verified on patch 2.31, build 26133166, and on WolvenKit-built mod archives)
All little-endian. Header, 40 bytes at offset 0:

| offset | type | field |
|---|---|---|
| 0 | `4s` | magic `RDAR` |
| 4 | u32 | version (12) |
| 8 | u64 | index position |
| 16 | u32 | index size |
| 20 | u64 | debug position (0 in every archive seen) |
| 28 | u32 | debug size (0) |
| 32 | u64 | file size |

At `index position`: a 28-byte index header (`file table offset` u32, `file table size` u32, crc u64,
`file entry count` u32, `segment count` u32, `dependency count` u32), then `file entry count` entries of 56
bytes each: `name hash` u64, timestamp u64, inline-buffer count u32, segments start/end u32 u32, dependencies
start/end u32 u32, sha1 20 bytes. The first u64 of each entry is the path hash; nothing else is needed for
conflict detection. Reading the indexes of all 57 vanilla archives (`archive/pc/content` + `archive/pc/ep1`,
about 60 GB) took under a second and gave 553,470 distinct hashes.

### The hash rule
`FNV1a64` (offset `0xCBF29CE484222325`, prime `0x100000001B3`) over the UTF-8 bytes of the resource path
**with backslashes**, lowercase as the game stores it: `eyeofcenter\2ndamendmentonline\atelier_icon.inkatlas`
hashes to the value stored in the archive; the forward-slash spelling does not.

### Names
Mod archives carry no file names (the debug section is empty and the bytes after the index are `0xD9`
padding), so names come from a hash list. `WolvenKit.CLI archiveinfo -l <archive>` prints one line per entry:
the resolved path (backslashes) when its bundled hash database knows it, else the bare decimal hash. Hash
each printed path with the rule above to map it back to the entry. Mod-only resources (`dexiom\catfur\...`)
resolve too, since WolvenKit indexes the paths it packed; anything unknown stays a number, and a conflict
report by hash is still exact.

### Load order
`archive/pc/mod` loads in name order and the archive loaded **first** wins a path, which is why mods ship as
`!!!Better_Tree_Textures.archive` or `#####-NovaCity2.archive`. A `modlist.txt` in that folder lists archive
names to load first, in its order; the rest follow by name. REDmod packages in `mods/` are a separate route
(deployed into `r6/cache/modded`) and do not take part in this ordering.

### Nexus from a script
- Search is public: `POST https://api.nexusmods.com/v2/graphql` with
  `mods(filter: {name: {value: "texture", op: WILDCARD}, gameDomainName: {value: "cyberpunk2077", op: EQUALS}},
  sort: [{endorsements: {direction: DESC}}], count: 20)`; fields `modId name summary version endorsements
  downloads updatedAt adultContent author uploader { name } modCategory { name }`. `author` is a plain string.
- Everything else is the v1 REST API with the user's personal key in an `apikey` header:
  `/v1/users/validate.json`, `/v1/games/cyberpunk2077/mods/<id>.json`, `.../mods/<id>/files.json`
  (categories MAIN, UPDATE, OPTIONAL, OLD_VERSION, MISCELLANEOUS; `is_primary` marks the default main file),
  `.../files/<file_id>/download_link.json`. The last one is Premium-only; a free account clicks "Mod manager
  download" on the site, which fires `nxm://cyberpunk2077/mods/<id>/files/<file_id>?key=...&expires=...`,
  and those two query values make `download_link.json` work once. Limits: 2,500 requests a day, then 100 an
  hour, with the remaining counts in `x-rl-daily-remaining` / `x-rl-hourly-remaining`.
- Nexus file names follow `<Name>-<mod id>-<version with dashes>-<unix timestamp>.<ext>`.

### The loop in this repo
`um nexus search "texture" --count 20` to shortlist by endorsements, `um nexus files <id>` to see variants,
`um cp77 install <id> [<id> ...]` to download (key) or `um cp77 install <nxm link>` (free account), then
`um cp77 conflicts --paths` and `um cp77 check`. The manifest in `~/.universal-modder/cp77/manifest.json`
records every placed file with its sha1 and every archive's hash list, so `um cp77 uninstall <name>` removes
exactly those files and `um cp77 updates` compares the recorded file id with the newest main file.

## Gotchas
1. **Conflict detection says two archives share nothing although they replace the same texture.** **Cause:**
   paths were hashed with forward slashes, which gives a different FNV1a64. **Fix:** hash the backslash form.
2. **A mod whose download has `init.lua` at its root plus `Vanilla/` and `Lush/` folders of one
   `body.archive` was placed entirely under the CET mods folder.** **Cause:** "folder holding init.lua is a
   CET mod" swallowed the siblings. **Fix:** route `.archive`/`.xl` to `archive/pc/mod` before the CET rule,
   and refuse the install when two sources map to one destination until the user picks a variant folder.
3. **`*texture*` finds nothing on the GraphQL search.** **Cause:** `WILDCARD` already matches a substring;
   the stars are taken literally. The only operators are `EQUALS`, `NOT_EQUALS`, `WILDCARD`.
4. **Vortex-deployed files vanish from the game folder without losing anything.** **Cause:** Vortex deploys
   hardlinks (link count 2 in `ls -l`), so the staging folder (`<drive>\Vortex Mods\cyberpunk2077`) still
   holds every file; hand-copied files have link count 1 and must be backed up before a purge. Extracted
   Vortex staging folders carry `__folder_managed_by_vortex` and `placeholder.vortex` markers: skip them.
5. **After deleting every mod, Steam's "verify integrity" also applied the pending patch** (build 20383525 to
   26133166 here), so mods built against the old build were going to break anyway; check the build id in
   `steamapps/appmanifest_1091500.acf` before reinstalling anything.
6. **Nexus downloads are mostly `.7z` and `.rar`.** Python's zipfile covers only zips; 7-Zip
   (`C:\Program Files\7-Zip\7z.exe`) handles both, WinRAR's `UnRAR.exe` is the fallback for `.rar`.
7. **Patch 2.5 (October 2026, exe 3.0.88.46235) and the loaders.** Cyber Engine Tweaks 1.38.0 and redscript
   0.5.32 shipped official 2.5 builds within a day. RED4ext 1.30.0 (March) and the 2026-10-19 ArchiveXL
   1.27.5 / TweakXL 1.11.5 / Codeware 1.20.6 predate the patch; a third-party "Unofficial 2.5 Fix" (Nexus
   35697) rebuilds all four and they initialize (RED4ext logs `v1.30.0+master.1.47ac01c`, "4 plugin(s)
   loaded", redscript compiles, CET hooks complete, the menu comes up). **Mod Settings 0.2.21 closes the game
   during RED4ext plugin loading with no message**; the `red4ext-*.log` simply stops at
   `Loading plugin from '...\mod_settings\mod_settings.dll'`. Input Loader 0.2.3 loads fine. When a 2.5 game
   vanishes at startup, read the last line of that log: it names the plugin.
8. **Nexus CDN download links contain the file name with spaces**; Python's `http.client` refuses the URL
   unless it is percent-encoded first (`urllib.parse.quote(url, safe="/:?=&%+~@!$'()*,;")`).
9. **Python on Windows does not understand Git Bash's `/f/...` paths** when a script is given one from a
   bash heredoc; pass `F:\...` or convert first.

## Seen in
- `knowledge/games/cyberpunk-2077/cyberpunk-2077-native-modding-address-hashes.md` (the native-hook side of
  the same game).
- This note came out of purging a 492-archive Vortex install of Cyberpunk 2077 2.31 and replacing Vortex
  with `um cp77` + `um nexus` (2026-10-23/24).
