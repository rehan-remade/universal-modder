---
kind: game
title: "Space Marine 2 modding foundations: paks, load order, Saber's tools, manifests and crash triage"
game: "Warhammer 40,000: Space Marine 2"
games_also: []
game_version: "Steam build 25799387 (Patch 15.1, Oct 2026); earlier findings on Patch 14.x (Aug-Sep 2026). Mod Tools app 3856330 build 25506153 (Oct 2026 update)"
platform: windows
engine: unknown
route: data
tools: ["Saber SM2 Mod Tools (ModEditor, ModelConverter, UsfExporter, Meta Desc Patcher)", "Python 3 (zipfile, struct)", "own minidump / .ssldmp readers"]
anti_cheat: "EasyAntiCheat. Everything here uses Saber's official mods folder (client_pc/root/mods), which flags the session 'Mods Detected' (private lobbies, separate progression). No injection, no EAC interaction, PvE only."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-29
links: ["https://spacemarine2-modding.prismray.io/", "https://www.nexusmods.com/warhammer40000spacemarine2/mods/233"]
tags: [space-marine-2, saber, swarm-engine, pak, load-order, ssl, sso, crash-triage, mod-tools]
---

# Space Marine 2 modding foundations: paks, load order, Saber's tools, manifests and crash triage

> Two months of SM2 (Saber Swarm engine) modding through Saber's official mod support: weapon skins, new NPCs,
> custom animations, voices, mission edits. This note is the base layer every other SM2 note assumes: how mod paks
> are read, which files are text and which are compiled, the manifest rules that cause most crashes, and how to read
> a crash when the game gives you nothing. Everything below was verified in the real game unless marked otherwise.

The other SM2 notes build on this one, and each fact lives in one of them:
[models and textures](sm2-models-tpl-format-modelconverter-and-textures.md),
[weapons](sm2-weapons-skins-reloads-perks-vfx-and-sounds.md),
[new enemies and Morpheme animation](sm2-new-enemies-npc-classes-and-morpheme-animation.md),
[a new playable class](sm2-new-playable-class-on-character-mod-slot.md),
[missions and the spawn director](sm2-missions-scenarios-faction-swaps-and-esd-spawning.md),
[voices and Wwise audio](sm2-voices-talkers-and-wwise-audio.md) and
[the Battle Barge hub](sm2-hub-battle-barge-thunderhawk-and-usables.md) (added 2026-10-29).
Lines dated "(2026-10-2x)" were added after the first publication.

## Setup
- Steam build 25799387 (Patch 15.1). Patch 14 -> 15 moved many files, so date your findings.
- Saber's official modding docs: <https://spacemarine2-modding.prismray.io/> (installing the Mod Editor, Model
  Converter and Map Converter references, uploading, playing with mods).
- **Saber's mod rules (the docs' Legal Notice):** mods must not contain AI-generated or AI-assisted content, must
  not be sold, and may only use Warhammer 40,000 IP; uploading to Steam Workshop or saber.games means accepting the
  EULA's Mods section. Several of these notes used AI-generated meshes and textures, so keep builds that contain
  them private, and use hand-made art and recorded voices for anything you release. Their TTS voices were cloned
  from a real voice actor, a route the voices note now drops (see its Assets).
- Saber's Mod Tools (Steam app "Warhammer 40,000: Space Marine 2 - Mod Tools"). Prefer the standalone tool folder
  over the older copy inside the game. Docs ship in `ModEditor/documentation/` (`CLS_File_Guide.pdf`,
  `Enum_Extension_Tutorial.pdf`, `whitelisted_enums.txt`, `Map_Converter_Guide.pdf`, samples) and a modding how-to
  PDF in ModEditor.
- After EVERY game update or file verification, run `client_pc/root/tools/MetaDescPatcher.exe` and press Patch.
  The meta descs now ship with the game, so Mod Editor keeps working after patches, but link fields stay locked
  until you patch.
- **The best single reference:** `client_pc/root/tools/meta_descs/meta_desc_ssl.ps`. It lists every blueprint node
  and field: input/output pin names (`__diagram.__input/__output`), param types, `__defaultValue`, captions and
  hints. Read it before guessing a pin name.
- Saber also ships tool SOURCE: `ModelConverter/ToolsSource` (GltfConverter.cs, Tpl.cs, USF code, scene
  CDList/ClassList/DOMList/MapBuilder). Reading it answered many format questions faster than reversing binaries.

## Route and why
Data route: mod paks are zip files dropped in `client_pc/root/mods/`, and a file in a mod pak overrides the retail
file at the same path. Gameplay logic is mostly plain-text `.sso` / `.cls` / `.prop` (Saber's SSL data format);
code is compiled `.sslbin`, which you cannot replace (see Gotchas). No loader or injection exists or is needed.
EasyAntiCheat blocks RenderDoc and live-memory tools, so all inspection is offline.

Modded play stays inside Saber's mod support. Its "Playing with Mods" page says that when mods are detected the
game leaves public matchmaking, plays in private lobbies only (invite or code), shows a watermark, and keeps a
progression separate from the official one. For quick iteration the docs also allow loose files in
`client_pc/root/local/` (same relative paths; the game warns about corrupt files and loads slower, because loose
files don't stream). Paks are what you ship.

## How the game works (what we had to learn)

### Pak layout
- Retail data: `client_pc/root/paks/client/default/*.pak` and `server_pc/root/paks/server/...`. The game runs a
  local SERVER even in solo play; server crashes go to a separate report folder (below).
- `default_other.pak` = plain-text SSL data (`ssl/**/*.sso`, `.cls`, `xscenes/`), shipped on BOTH client and server.
  Editing the text is enough for gameplay data; no recompile.
- `default_ssl.pak` = compiled `*_release.sslbin` / `_profile.sslbin` modules. Many are ~400-byte class stubs; the
  real data lives in the text.
- `resources.pak` (client and server) = the `.resource` manifests (YAML-ish, CRLF, 3-space indent). Every asset
  is resolved through its manifest, not by path alone.
- Textures: `default_pct_*.pak` hold mips as `pct/<name>_N.pct_mip`; models in `default_tpl_*.pak`
  (`.tpl`, `.tpl_data`, `.lods_base`, `.geom_dbg`, `.cdt`, `.tpl_markup`); animations in `default_animation.pak`.
- `texts/strings_english.str`: UTF-16LE with BOM, `KEY<tabs>"value"`. Retail values are obfuscated (`6d3s9<hex>`),
  but plaintext values also render. Some values span lines with real newlines; edit single-line keys only.

### Load order and conflicts
- **When two mod paks contain the same file, the pak that sorts FIRST alphabetically wins.** Saber's "Using Mod
  Packs" page says so: mod paks override the default paks and are sorted alphabetically, and if modA and modB change
  the same file the virtual file system takes modA's. This is the reverse of the usual "z_ loads last" convention.
  Name an override `00000_0_...` to beat a pak named `00000_t...`; `0000_x` sorts AFTER `00000` because `'0' < '_'`.
  The same page says editing the default paks directly crashes the game at start: mod paks are the only route.
- Shared files (`strings_english.str`, `mml_cfg/all_levels.mml_cfg`, `sounds/localization/english.sound_localization.resource`,
  big libraries like `melee_actor_factory.sso`) are winner-takes-all. Two mods that both ship one silently erase each
  other's entries. Build your copy as a MERGE: current retail + every installed mod's changed keys + yours, and
  rebuild whenever those mods change.
- **Write mod paks with `zipfile.ZIP_STORED` for every file** (Saber's page: a pak is a ZIP with compression set to
  Store). The engine streams `tpl_data` and texture mips by byte range straight out of the pak. A DEFLATED pak loads
  but renders black textures and invisible near LODs.
- **Write plain local headers: no zip64.** Python's `ZipFile.open(info, "w", force_zip64=True)` gives every local
  header version 4.5, `0xFFFFFFFF` in both 32-bit size fields and a 20-byte zip64 extra field holding the real sizes,
  which the central directory doesn't carry. A pak written that way mounts but breaks the game's text at startup and
  loops an arena load back to the menu (gotcha 13). The same files repacked with plain headers (version 2.0, extra
  length 0, data right after the name) loaded. Set `info.file_size` and leave `force_zip64` False: CPython only
  switches to zip64 by itself for entries near 2 GiB (`ZIP64_LIMIT`), and pak entries stay far under that. Check
  every local header after writing.
- **Check EVERY file you ship against EVERY installed pak before building (2026-10-22).** Build each file on the copy
  the game loads today (the winning pak's copy, else retail) and assert that base in your verifier. A small pak that
  shipped one player `.cls` built on retail sorted first and silently switched off two features a big mod kept in the
  same file; we had checked only some of the paths (gotcha 14).
- A mod built for an older patch keeps overriding patched retail files for as long as it sorts first (2026-10-15). A
  testing-arena mod built on Patch 14 still replaced the hub scenarios, the player classes, the missions library and
  ~26 files Patch 15 had changed; it was the prime suspect for a hub-load server crash (not confirmed) and masked any
  mod that needed the newer hub scenario. Retire such paks after a patch or rebuild their files on current retail.
- A custom map that clones a retail level keeps the base level's FILE names (its class_list, `.scn.resource`), so a
  per-level edit has to be repeated on the map's copies, in a pak that sorts before the map's pak (2026-10-14).

### Merging many mods into one pak (2026-10-22)
Folding 10-20 separate paks into one large mod (twice) taught a few rules. The goal: the merged pak loads exactly what
the game loads today, so retiring the separate paks changes nothing in game.
- Merge in load-precedence order, lowest first, each onto the previous result. Where two paks ship a file, the
  first-sorting pak's copy is what players see now, so that copy (or a merge onto it) is the target.
- Pick the merge base per pak: for a pak built ON the large mod, the large mod's copy it only adds to (normalise
  trailing commas: appending to a list adds one); for a pak that loads OVER the large mod, the large mod's current
  copy. Choosing "the base with the smallest diff" produced dozens of false conflicts. If the pak's text copy holds
  every line of the target's, take it whole: stacked list appends defeat line-based replay.
- **`.resource` manifests: never union retail links blindly.** Add only links whose target the merged file actually
  references (plus retail's implicit ones, e.g. `esd_enemy_*_desc`). A blind union re-added enemy classes a faction
  swap had removed (gotcha 17).
- Binary files can't be merged; take a pak's copy only after a lineage check. Morpheme `.nmb`: only if its network
  holds every animation NAME of the target's (each animation mod in our chain was built on the one below). Level
  binaries (`.cd_list`, `.class_list`, `.lwi_container`, `.lg_data`): only if each layer keeps the layer below (see the
  [hub note](sm2-hub-battle-barge-thunderhawk-and-usables.md)). Any other binary: only if the target is unchanged.
- A dependent pak's shared files (animation network, anim table, `mml_cfg`, string tables) mask the base mod's newer
  copies. After any base rebuild, diff every dependent pak's shared files against the current base and rebuild
  them (gotcha 19).
- Verify file by file: merged copy == (or, for merged text, contains every line of) the copy the game loads now, and
  no remaining separate pak would take over a file once the merged ones are retired.

### Manifests (`.resource`) and the crash rules they cause
- `.sso.resource` has several link sections (`linksDesc`, `linksDescWeak`, `linksSsl`, `parents`, `dynamicLinks`).
  Scan all of them before deciding something is undeclared.
- **Node-type declarations in scenario manifests are all-or-nothing per type.** Measured over every retail
  scenario: some blueprint node types are declared in `linksDesc` every time they're used
  (`EsdUpdatePressureAndDurationSettings`, `EsdSetScenarioHoldStage`, `OnBlueprintStartedOrReset`,
  `EsdUpdateFactionAndPackSettings`, `SwitchByInt`, `GetDifficultyLevel`, `AddResourcesToPlayers`), others never are.
  Map a `__type` to its module by snake_casing the class name. Library nodes (`BlueprintStringLibraryAppend` etc.)
  live in `.ssolib.resource`, not `.sso.resource`.
- **Archetype pool <-> `linksDescWeak` is 1:1.** Every `LevelArchetype` entry in a scenario has a matching
  `<npc>.cls.resource` in `linksDescWeak`. Add one without the other and the class never loads.
- Symptom of breaking either rule: ACCESS_VIOLATION reading `0x8` (null class pointer) during scene load.
- `.tpl.resource`: always start from RETAIL's and only add `linksPct` / `linksTd` entries (alphabetical, CRLF).
  The exporter's own `.tpl.resource` leaves `linkTplMarkup` / `tplMarkup` empty, which crashes on a shader-cache
  miss (see the [models note](sm2-models-tpl-format-modelconverter-and-textures.md)).
- New animation clips need a `.sani.resource` and a link in `<set>.mr.resource`, or the game crashes at boot (see
  the [NPC/animation note](sm2-new-enemies-npc-classes-and-morpheme-animation.md)).
- A node type that exists in `meta_desc_ssl.ps` is not necessarily shipped. Assert that every node type you use
  has a resource in that side's `resources.pak` (example: `BlueprintNodeEsdClientGetStage` is described but not shipped).

### SSL: what you can and cannot change
- Text `.sso` / `.cls` overrides work. Keep every `__type` line when overriding a node; keep indentation exact
  (a node nested inside a field instead of beside it passes brace checks but breaks).
- **A mod pak that replaces an existing retail `.sslbin` crashes the server at startup**, even a same-length
  one-byte edit. Hand-built new sslbins are ignored. Change behaviour through data only.
- **A new data "brand" (new compiled class referenced by `__type`) crashes at boot.** Use existing types, inline
  objects, or Saber's modder slots / the official CLS route (below).
- **Official way to add classes (Oct 2026 Mod Tools, `CLS_File_Guide.pdf`):** copy a retail `.cls`, write its
  `.ssc.resource` with `noSsl: true` (no ssl/sslbin fields), `className`, `clientClassName` / `authorityClassName`
  for replicated pairs, `isServerReplicaModule` / `isClientReplicaModule`, links = own `.cls.resource` + the
  parent's `.ssc.resource`, `parentClassName`. Append net-replicated ones to
  `initial/replicas/initial_replicas_all_{server,client}.resource`. The guide states this gives unlimited custom
  NPCs, actors and outfits. (We built NPCs on Saber's older `npc_modded_1..5` slots before this existed.)
- **Custom enum values** (same update): set `extension: <file>.ext` on the enum's `.ssl.resource` (retail
  `ability_consts_library.ssl.resource` already has an empty `extension:` field); the `.ext` is YAML
  (`enumExtend: / - enumName: AbilityUid / enumValues: [...]`). Only enums in `whitelisted_enums.txt` (AbilityUid,
  FirearmUid, MeleeStrikeWeaponType, ...). Verified in game: a cloned ability on a new AbilityUid works.
- Saber also pre-registers modder slots: `melee_mod_1..5`, `ultimate_mod_1..5`, `equipment_mod_1..5`
  ability uids, `for_modders/melee_mod_desc_1..5`, `ssl/characters/modded/npc_modded_1..5_{server,client}`,
  `CHARACTER_MOD_N` classes.
- Reading compiled logic: the sslbin is a protobuf-like container (field 6 string table, type table, class defs,
  functions with a simple stack bytecode: word op = `w & 0xff`, arg = `(w >> 8) - 0x800000`). A rough
  disassembler is a day's work and was worth it: it settled equipment, lobby and HUD questions that data alone
  couldn't. Client and server global-function indices differ.

### Other game-wide levers found
- `mml_cfg/all_levels.mml_cfg` (JSON, default_other.pak) caps texture mips per quality slot by texture NAME
  (`topmip` = mips kept, counted from the smallest). **Unlisted textures lose their top mip on High** (the exe skips
  1 mip on High, 2 on Medium, 3 on Low unless a side is small). Every custom texture shows at half resolution on
  High unless you add entries. Insert yours at the top of the CURRENT retail file and ship it. Only one pak wins it.
- Quality-setting data (`ssl/main/user/quality_settings/`, `animation_quality_settings.sso`): ragdoll / gib caps,
  ragdoll freeze timers, cloth/physics quality presets. Console "SPEED" presets show Saber's own perf cuts.
- Key codes in keymaps / `InputActionHold` are DirectInput scan codes (Esc 1, Enter 28, P 25, Numpad2 80), not ASCII.
- Cosmetic challenge locks are data: `challengeLock = { challengeUid, tier, __type "ChallengeLockReason" }` blocks on
  regions in `character_customization_library.sso` and on decals.
- Lobby/session: `ssl/main/user/mod_support_consts.sso` holds mod-support switches (e.g.
  `isTwelvePlayerPveLobbyEnabled`, which also splits the hub barge: see the
  [missions note](sm2-missions-scenarios-faction-swaps-and-esd-spawning.md)).
- **Custom save data for mods** (Saber's Oct 2026 tools announcement; not used here): a persistent tree of namespaces
  (e.g. `author.mod_name.data`) holding typed values by key, read and written from blueprints. The server can request
  a namespace from any player, but receives ONE namespace without its sub-namespaces, so split data accordingly. Saber
  says it is neither private nor secure, and not a progress backup.
- `texts/` can hold more than one string table (2026-10-16). A mod that ships an extra table overrides the main
  table's values for every key it holds; one we audited carried a full pre-patch copy that kept 45 perk and item texts
  on old values after Patch 15 (gotcha 20). After a patch, compare every table, not only `strings_english.str`.
- Profiles and user configs are SSF1 containers (md5 + compressed payload), so a broken profile is fixed in game data,
  not by editing the save (gotcha 16).
- The retail game writes no log files. Your only runtime readouts are crash reports, `.ssldmp` script dumps and
  on-screen debug (`BlueprintNodeDrawModUiLog` = "Draw UI Mod Message", client side; its input pin is `Draw`).

### Crash triage when the game shows nothing
- Reports: `%LOCALAPPDATA%\Saber\Space Marine 2\{client,server}\reports\report_<ts>_pid<N>\` (error.yaml, a
  `.ssldmp`, `CrashDump.dmp`). Script errors without a crash also land in `...\client\ssl_crash_dump\`.
- **An empty `report_*` folder is created at EVERY launch.** A crash = `CrashDump.dmp` present. The folder is
  deleted when the dialog closes, so copy it while the dialog is open.
- `error.yaml` says client vs server and the active scene. Its callstack is often empty: go to the minidump.
  Parse it with Python `struct` (stream 6 = exception, 4 = module list) to get module+offset. Reading `0x8` / `0x48` =
  a lookup returned null (usually a class or resource that never loaded).
- Since Patch 15.1 the `.ssldmp` is JSON `{callstack, objects}`. The `objects` heap is gold: count `$type`s to see
  which libraries were built, and inspect objects (e.g. which anim lookups resolved) right before the crash.
- Since 15.1, server code lives in `...Retail.dll` (thread DLL_SERVER_MAIN), not the exe.
- Compare module+offset only within one build.
- **`...\client\ssl_crash_dump\ssl_dump_*.ssldmp` survives when the crash dialog is closed** (the report folder does
  not), so read it first (2026-10-15). It is also written on script errors with no crash at all (UI freezes, menu hangs).
- "Crashed, no report": an empty report folder plus a Windows Application event 1002 (app hang) is a HANG, not a crash
  (ours was RAM exhaustion from other jobs). Check events 1000 / 1001 / 1002 before chasing a mod (2026-10-09).
- **Game-mode rules are keyed by class NAME, not `__type`** (2026-10-08). A rule Patch 15 removed
  (`GameModeRuleChallengesDifficultyMutator = {}`) left in a modded `game_mode_pve_server.sso` crashed every PvE load
  (server stack `GameModeServer.CreateRulesTypemap` -> `TypeMap.Set` with a null value). A scan of `__type` values
  misses it; grep `GameModeRule*` keys against current retail after each patch (gotcha 15).
- A missing-type scan over all installed mods (every `__type` that neither retail nor any mod defines) still earns its
  keep. Known false positives: `mod1` / `mod2` (local emitter types in retail `.sfx`), `xc_track_*` (xseq engine types).
- Once a crash is traced to one file or change, report it with a proposed fix and test that in game; an in-game test
  is faster than ruling out every other theory offline first (2026-10-16).
- Saber's "Install Extra Tools" page also describes an advanced crash reporter: copy the toolset's `CrashReporter`
  files into `client_pc/root/bin/pc` for more detail on each crash. This note doesn't cover it.

### Auditing a cut-down build for a console release (2026-10-13 to 10-16)
A large PC mod was trimmed into a smaller variant intended for a console release through Saber's official mod
channels (retail player models, no custom maps or new weapon models: the author's scope, not a documented platform
rule). What the audit had to catch, all offline; none of it has been tested on a console:
- Library edits that only make sense with the full build's swapped models show retail leftovers or orphaned objects
  once those models are gone (armour regions pointing at objects only a custom constructor has; a pauldron edit that
  orphaned a shield plate onto every pauldron). Audit every class for orphans after removing a model swap.
- Every class a player's profile might reference needs a default armour preset (gotcha 16).
- Sync to the current patch with the same 3-way merge as the full build; compare every string table.
- Remove leftovers: Saber's mod-tools sample blueprint had been pasted into a player authority class and spawned an
  actor that doesn't exist; on-screen debug nodes; a mangled class name (`npc_ive_yrant_server`) in a level pool,
  the likely cause of an earlier crash; rules the patch removed; an execution sequence edited so its weapon-unholster
  request fired 0.1 s before the sequence end, which locked up the Heavy class (retail timings fixed it).
- Retail data differs per platform: the SPEED (performance) preset in `quality_settings_console.sso` turns armour
  covering (blood and grime) off on several consoles, so a feature built on covering will not show there. Read from
  the retail data, not checked on hardware.

## Build steps
1. Extract the retail files you change from the CURRENT paks (an extraction from an older patch silently differs;
   we lost a day to a stale animation clip).
2. Edit text files; keep CRLF and indentation; add `.resource` links for anything new.
3. Write a ZIP_STORED pak with plain (non-zip64) local headers, named so it sorts before anything it must beat; put it
   in `client_pc/root/mods/`.
4. Never swap paks while the game runs: it caused an out-of-memory server crash mid-load. Check for the process
   `Warhammer 40000 Space Marine 2 - Retail` first (note: `tasklist` truncates names to 25 chars).
5. After a game patch: 3-way merge your text edits (old retail -> new retail onto yours). Line-based merges misplace
   SSL blocks; a tree merge keyed by unique fields (`firearmUid`, `type`, `packUid`) leaves only real decisions.
   Treat numeric lists (splines) as atomic values. Scan for types the patch removed.

## Verification
- Oracle = the real game: the testing arena `test_scene_mod`, taken from
  [Testing Menu](https://www.nexusmods.com/warhammer40000spacemarine2/mods/233) by Hypexs777 (Nexus Mods), with
  buttons wired to `SpawnActorByArchetype`, plus screenshots and crash dumps. The level itself is Saber's sample: the
  Map Converter docs build it with `tools/MapBuilder.exe`. Saber's autostart flag
  `--startup --set /Config/WhiteListedVariables/enableModdersAutostartFlow true` jumps straight into the mod test scene.
- Every rule above came from a crash or a visible failure that went away when the rule was applied.
- (2026-10-15) After Patch 15 we stopped installing the Patch-14 Testing Menu build (see Load order). Later arenas
  give Saber's test level its own mission-select entry instead: a new `MissionUid` through enum extension
  (`missions_consts.ext`), entries added to the winning missions library and UI missions library, the RETAIL
  `test_scene_mod` scenario and an explicit archetype pool. Retail leaves its buttons 3-5 unwired and has an
  unconnected TyrWarrior spawn at `dom_spawn_2`, so there is room for your own button wiring.
- Not verified: whether `mml_cfg` defaults differ on consoles.

## Gotchas
1. **Two mods override the same file and one "stops working".** Cause: first-alphabetical pak wins the whole file.
   Fix: merge and ship a superset in the first-sorting pak.
2. **Black textures, invisible LOD0/LOD1, far LODs fine.** Cause: pak written with DEFLATE. Fix: ZIP_STORED.
   Cost us ~6 test rounds chasing geometry first.
3. **Server crashes at startup after shipping a "harmless" patched sslbin.** Cause: retail sslbins can't be
   replaced. Fix: data-only changes.
4. **Boot crash reading 0x48, stack mentions the new type** (e.g. `AnimTableActor` for a new anim-table type).
   Cause: a new compiled brand / hand-built sslbin. Fix: inline objects, existing types, modder slots or the `noSsl`
   CLS route.
5. **Scene-load crash reading 0x8.** Cause: undeclared always-declared node type, or a `LevelArchetype` without its
   `linksDescWeak` class. Fix: follow the two manifest rules.
6. **Client crash at scenario load with a garbage type index.** Cause: a blueprint link to a pin that doesn't exist
   (e.g. `Input` instead of `Draw`). Fix: validate every link against `meta_desc_ssl.ps` (inputs AND outputs, following
   `__type` inheritance).
7. **Server crash on a scenario int field.** Cause: `IntRefParam` written as a quoted string `"2"`. Fix: write
   Int/Float/Bool values bare.
8. **Custom textures look soft on High but fine on Ultra.** Cause: not listed in `all_levels.mml_cfg`. Fix: add entries.
9. **"Mods Detected" even for a tiny performance tweak.** Any mod pak does it, and with it come private lobbies only
   and the separate progression; there is no "vanilla-safe" pak.
10. **Saber's tools crash and fill the disk.** Running them with a cwd on a small drive, one tool wrote a 270 MB
    dump per model into `<cwd>\sandbox\crash_dumps` (12 GB in one run). Run them from a roomy drive and watch that folder.
11. **ModelConverter exits with code 82 and a "Press any key" exception.** Harmless; it happens after the work is done
    when stdin isn't a console. Don't treat exit codes as failure signals for these tools.
12. **A patch silently changes text you merged.** Strings, cloth colours, presets and class names moved in Patch 15
    (`PVP_*` presets -> `PVE_PVP_*`, new `PVE_MEDIC`). Fix: the 3-way merge in Build steps; for armour presets see
    the models note (gotcha "not available for the selected Class").
13. **Startup text broken (raw or garbled), then "Continue" loads part way and drops back to the same screen; no
    crash report, no dump.** Cause: the pak's local headers carry zip64 extras (above). Every content fix tried first
    changed nothing: the arena pool, inline animation clips, a Wwise bank rename. Found by diffing the zip STRUCTURE
    against a pak that worked, not the files. Fix: plain headers. If a pak with the same contents as a working one
    misbehaves, compare `version needed` and the local extra lengths first. Cost us 3 test rounds (Patch 15.1,
    Oct 2026).
14. **A big mod's feature (a walk toggle, permanent armour blood) silently stops after installing a small pak.**
    Cause: the small pak ships a file the big mod also changes, built on retail, and sorts first. Fix: build every
    shipped file on the copy the game currently loads; check every path against every installed pak (2026-10-22).
15. **Every PvE mission crashes at load after a patch; server stack in `CreateRulesTypemap`, null value.** Cause: a
    game-mode rule the patch removed, still listed by name in a modded game-mode file. Fix: remove it; grep
    `GameModeRule*` keys against retail after each patch (2026-10-08).
16. **Main menu never finishes loading; the `.ssldmp` ends in `ValidateEquippedCustomArmorPreset`.** Cause: the profile
    holds a custom outfit for a class whose customization section has no default armour preset; retail's
    `CHARACTER_MOD_1..3` stubs have none, so a build without the class another build added dereferences null while
    validating the saved set. Fix: give every such section a default preset (we used a retail Tactical preset plus
    `defaultArmorPreset`). The first boot then resets that class's saved set to the default parts. Fix built and
    installed; not yet confirmed in game (2026-10-15).
17. **A re-merged scenario manifest brings back enemies a faction swap had removed.** Cause: a blind union of retail
    `.resource` links. Fix: add only links the merged file references (2026-10-01).
18. **"It crashed" but the report folder is empty.** Cause: a hang (Windows event 1002), here from RAM exhaustion.
    Fix: check the event log; free memory; it isn't a mod bug (2026-10-09).
19. **After the base mod was rebuilt with 65 new animation clips, an installed add-on still shipped the base's OLD
    network, anim table and manifest.** Caught offline before launch; it would have masked the new clips (broken
    feature or boot crash). Cause: the add-on's shared copies were built on the older base and sort first. Fix:
    rebuild every dependent pak on the current base; diff shared files before installing (2026-10-15).
20. **Perk descriptions still show pre-patch numbers although the perk data is current.** Cause: an extra string table
    in a mod holding a stale full copy wins over the main table. Fix: update or drop the stale values in every table
    (2026-10-16).

## Assets
None in this note.

## Open questions
- Whether `.ssldmp`-style heap dumps can be triggered on demand (they'd make an oracle without crashing).
- Exact rules behind `mml_cfg` size budgets for the `*Base` quality slots.
