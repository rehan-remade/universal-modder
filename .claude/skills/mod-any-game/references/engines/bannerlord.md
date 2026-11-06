# Mount & Blade II: Bannerlord

**Identify.** `Modules/Native/SubModule.xml`, module `ModuleData/` folders and `TaleWorlds.*.dll` assemblies in
`bin/Win64_Shipping_Client/` (`bin/Gaming.Desktop.x64_Shipping_Client/` in the Xbox PC / Game Pass build;
`bin/Win64_Shipping_wEditor/` belongs to the Modding Kit's editor). Gameplay code is managed (.NET Framework, so
C# modules target `net472`); the engine is native (`TaleWorlds.Native.dll`). For single-player mods, start with the
official module system. `um scan` reads the version from `bin/<platform>/Version.xml` when the build has one.

Written against v1.4.8 from static checks of that install's DLLs and XML, without a modded launch. Versions move:
check the user's build before trusting an API.

## Routes

1. **Data:** put the mod in `Modules/<id>/` with its own `SubModule.xml` and `ModuleData/` XML.
   Register managed XML through the manifest's `Xmls` entries; engine-side XML uses
   `ModuleData/project.mbproj`. Use XML merging or XSLT for targeted changes, and check the installed
   version's schemas and merge rules. Keep base-game files intact. Later modules win, so load the official ones
   (`Native`, `SandBoxCore`, `Sandbox`, `CustomBattle`, `StoryMode`) before yours, or your XSLT won't see their
   XML.
   See TaleWorlds' [module guide](https://moddocs.bannerlord.com/asset-management/quickguide_create_a_mod/) and
   [XML merging guide](https://moddocs.bannerlord.com/bestpractices/merging_module_xml_files_with_native/).
2. **C# module:** build a DLL containing an `MBSubModuleBase` subclass, normally deployed under the
   mod's `bin/Win64_Shipping_Client/`. Its DLL name and fully qualified entry class must match
   `SubModule.xml`. Use lifecycle callbacks to register campaign behaviors, models or mission logic;
   inspect the current declarations before choosing a hook. For persistent campaign features, inspect
   `CampaignBehaviorBase.RegisterEvents` and `SyncData` plus the relevant save-system types.
3. **Managed patches:** when a suitable public hook is absent, use
   [Bannerlord.Harmony](https://github.com/BUTR/Bannerlord.Harmony) for managed methods. Check the
   current compatible release, declare its module dependency and verify the exact target overload.
   Avoid bundling a conflicting copy of shared libraries.
4. **Native engine:** Harmony doesn't patch `TaleWorlds.Native.dll`. Crashes and hangs inside it often come from
   bad mod data the client doesn't check: find them from minidumps with Ghidra on a copy of the DLL, and guard them
   from managed code (`knowledge/techniques/bannerlord-native-crashes-and-hangs.md`).
5. **Assets** (`.tpac` packages, skeletons, animation clips) normally come from the Modding Kit's editor. They can
   also be written offline: `knowledge/techniques/editor-free-bannerlord-assets.md` and the published
   [editor-free SDK](https://github.com/theartur2000/bannerlord-editor-free-sdk).

## Knowledge first, then the current install

- Run `um kb search "Bannerlord"`. The v1.4.8 Borderlands 2 total conversion
  (`knowledge/games/mount-and-blade-ii-bannerlord/bannerlord-borderlands-2-total-conversion.md`) links technique
  notes on assets, combat and guns, custom races and creatures, and native crashes. They are version-specific:
  their native addresses are for v1.4.8.119303 only.
- Record the real install, full game version, active modules and dependency versions in `MODLOG.md`.
- The DLLs and XML of the current install are the implementation authority. Reference its assemblies when
  building; confirm method signatures, lifecycle and data IDs there. Keep ILSpy output outside the repository.
  Online API docs, generated scaffolds and old mods are leads until checked against those files.
- Optional: [BannerlordSage](https://github.com/hby7921/BannerlordSage), a stdio MCP server, indexes the user's own
  install (decompiled source, XML, docs) and a local mod workspace for search, with Harmony/XSLT scaffolding and a
  `bannerlord_doctor` module check. `start:bannerlord` runs its query-first toolset; `start:bannerlord:full` adds
  workspace creation, XSLT generation and experimental editor tools. Compare `bannerlord_index_status` with the
  live `Version.xml` first: an index of another build is history, not the current API. Its index holds decompiled
  source, so it stays out of repos and releases.

## Verify and record limits

- Build against the target installation without deploying first. Validate the manifest, referenced DLLs, XML
  IDs and XSLT output (`bannerlord_doctor` checks module dependencies, missing DLLs, duplicate libraries and
  load-order declarations).
- Saves and configs live in `Documents\Mount and Blade II Bannerlord\` ("and", not "&"): `Game Saves\` and
  `Configs\`. Back them up with `um backup` before a modded launch.
- Launching the client with a `/singleplayer _MODULES_*Native*...*<YourModule>*_MODULES_` line skips the launcher
  (the total-conversion note has the exact line). After a crash, answer No to "enable safe mode?": it disables
  mods.
- Test one small feature in the real game with the intended module order and inspect logs. Campaign initialization
  or persistence changes need a new campaign and a save/load round trip; check existing-save compatibility
  separately if promised. Mission changes need the relevant battle or scene, not only a successful menu launch.
- Record compile, static, in-game and save/load results separately. Module health checks and indexed source
  don't prove runtime behavior. Ship only authored code/assets; keep game files, extracted content, decompiled
  source, index databases and local credentials out of the release.
