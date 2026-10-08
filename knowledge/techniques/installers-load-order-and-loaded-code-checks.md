---
kind: technique
title: "Installers, load order and loaded-code checks for multi-part mods"
tags: [installer, uninstall, backup, load-order, asi-loader, dll-proxy, steam-drm, fingerprint, hash-pinning, dependencies, mod-coexistence]
date: 2026-10-05
agents: ["Claude Code (Opus 5.5)"]
humans: ["LeiiLo"]
links: []
---

# Installers, load order and loaded-code checks for multi-part mods

> Mashups ship several moving parts (a host plugin, a loader, a guest mod, sometimes a worker or a converted
> asset set), and their install scripts are where users lose settings or end up with half an install. These
> are the patterns and pitfalls found in projects' installers and loaders.

## When to use it
Before writing an install/uninstall script, a launcher, or a startup check for a mod that hooks a native
game, and when a mod "doesn't load" for some users.

## How
1. **Check the loaded code, not just the file.** Steam-wrapped executables are decrypted in memory, so the
   file on disk doesn't show the real code. [BullySkate](https://github.com/Faiqie/BullySkate) launches Bully through Steam, then its native plugin
   requires all 203 code fingerprints and 19 data locations before installing hooks. [Touhou HFR](https://github.com/vittorioromeo/th12_hfr) also
   requires Steam versions to be launched through Steam and checks expected instructions.
2. **Load early enough.** PipeLink found `dinput8.dll` loaded too late for GTA SA's mod loader and its own
   plugin; it installed the same loader payload under the name of a DLL imported at startup, keeping the
   original under a new name.
3. **Pin and verify downloads.** [SkateGM](https://github.com/the-schwilliam/SkateGM)'s fetch script pins SDL2 2.32.10 and a mapping-database commit and
   checks SHA-256. Counter-examples: the [Minecraft × Half-Life](https://github.com/SawyerTheNerd/Minecraft-X-HalfLife) tools fetch Java from a mutable "latest"
   endpoint; [NewVegasCraft](https://github.com/Davozh/new-vegascraft)'s first script pinned versions without hashes and pulled shader headers from a
   moving branch. A download "stamp" is not a content digest.
4. **Record ownership so uninstall can be exact.** BullySkate validates prepared asset sets by hash, keeps
   timestamped backups and refuses an unknown existing loader. NewVegasCraft's early installer kept existing
   configuration on install but deleted those paths on removal; the GTA V example's `--remove` deletes
   `ReShade.ini` even if the user had one before. Keep a manifest of what you created vs replaced.
5. **Replace loaded DLLs safely.** NewVegasCraft switched to copy-then-rename so an already-mapped DLL isn't
   rewritten in place (under its Proton setup).
6. **Divide responsibilities with other mods.** Touhou HFR with a popular rotation wrapper: the wrapper owns render targets,
   rotation and presentation; HFR owns timing, input and replay and turns off its own scaling. HFR re-takes
   its graphics imports after a translation patch loads, then chains them, after older imports had been
   silently removed. Document the exact combinations tested.
7. **Separate "installed", "loaded", "connected" and "plays".** Each is its own check; a successful
   install is not gameplay acceptance.

## Gotchas
1. **Name checks pass on the wrong build.** **Cause:** the installer checks only file or process names
   (e.g. a batch-file installer). **Fix:** hash or fingerprint the target.
2. **Half an install.** **Cause:** copies are not transactional (BullySkate and SkateGM both copy in
   steps). **Fix:** stage to a temp folder, verify, then swap; detect a partial previous run on start.
3. **A backup marker that lies.** One installer uses the backup DLL as the only "backup complete" marker, and copies
   DLL and launcher in separate steps. **Fix:** write the marker last, after verifying every file.
4. **Version parsing.** BullySkate's loader check compares decimal versions, so 15.10 would read as 15.1.
   **Fix:** compare version components as integers.
5. **Duplicate loaders.** PipeLink's early return when a loader already exists happens before cleaning
   obsolete copies. **Fix:** inventory every loader before deciding.
6. **Tests that print instead of fail.** SkateGM's disc-image fixture and several Lua checkers print
   failure without a failing exit status. **Fix:** make every check affect the exit code.
7. **A build that skips the meaningful checks.** One project's default build skips asset-dependent smoke
   tests and reuses an existing library without validating its revision. **Fix:** report skipped checks.

## Verification
Versions are in `skills/mashup-mods/references/mashup-cases.md`. Creator results are reports.
