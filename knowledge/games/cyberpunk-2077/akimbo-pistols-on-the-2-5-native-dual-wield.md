---
kind: game
title: "Custom akimbo pistols on patch 2.5's native dual wield (player animsets, seeded ItemIDs, Audioware sound swap)"
game: "Cyberpunk 2077"
games_also: []
game_version: "Steam PC, patch 2.5 \"Edgerunners II\": ProductVersion 2.50, FileVersion 3.0.88.46235 (watermark 3.0.5813403, P4CL 13555055), with Phantom Liberty"
platform: windows
engine: redengine
route: loader-api
tools: ["RED4ext 1.31.0", "redscript 0.5.32 (redscript-cli.exe)", "ArchiveXL 1.28.0", "TweakXL 1.12.0", "Codeware 1.21.1", "Audioware 1.10.1", "Cyber Engine Tweaks 1.38.1", "WolvenKit.Console 9.1.0", "Blender 5.2", ".NET SDK 10.0.4xx", "Python minidump", "fal (ElevenLabs Sound Effects v2, Mirelo SFX 2.0)", "um backup/win/video/publish"]
anti_cheat: "none (single-player)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["@skurtyyskirts"]
date: 2026-10-27
links: ["https://github.com/wopss/RED4ext", "https://github.com/jac3km4/redscript", "https://github.com/psiberx/cp2077-archive-xl", "https://github.com/psiberx/cp2077-tweak-xl", "https://github.com/psiberx/cp2077-codeware", "https://github.com/cyb3rpsych0s1s/audioware", "https://github.com/maximegmd/CyberEngineTweaks", "https://github.com/WolvenKit/WolvenKit"]
tags: ["cyberpunk2077", "dual-wield", "akimbo", "weapons", "animset", "friendlyName", "tweakxl", "archivexl", "audioware", "itemid", "rngseed", "red4ext", "crash", "save", "vortex", "um-win"]
---

# Custom akimbo pistols on patch 2.5's native dual wield

A pair of new pistols for Cyberpunk 2077 2.5: H&K USP Match pistols in the style of the 2001 Lara Croft film
(own PBR model, 74-sound Audioware bank, new first-person reloads per movement state, flourishes). They ride the
dual-wield system that patch 2.5 added for the player (the Double Trouble perk) instead of faking a second gun.
It runs in the real game: an on-screen probe reported both hands holding the mod's guns with dual wield on,
screenshots show both models, and the gunshots in a recording cross-correlate with the custom sound files
(0.70-0.94) while the vanilla Liberty shot scores 0.5 at most. The work also turned up a save crash that is not
the mod's: saves made with since-removed mods crash about 13-30 s after loading whenever RED4ext is installed.

For address lookups in crash dumps this note uses the game's own symbol table; see
[cyberpunk-2077-native-modding-address-hashes.md](cyberpunk-2077-native-modding-address-hashes.md).

## Setup
- **Game:** Steam, Windows 11, RTX 5090 on NVIDIA driver 621.01 (only noted from crash reports; it didn't
  matter). Run windowed at 1024x768 for the tests.
- **State found:** the user had just purged their Vortex mod stack for 2.5. Plugin folders held only logs, the
  RED4ext and CET loader DLLs were gone, `r6/scripts` was gone. Left over: UltraPlus (its `UltraTool.dll` RED4ext
  plugin reports "incompatible with the current patch" and is skipped), a ReShade `dxgi.dll`, a few `.archive`
  files and `__folder_managed_by_vortex` markers.
- **Frameworks, all from their GitHub releases, released 22-26 Oct 2026 for 2.5:** RED4ext 1.31.0, redscript
  0.5.32, ArchiveXL 1.28.0, TweakXL 1.12.0, Codeware 1.21.1, Audioware 1.10.1 (`Audioware-windows-v1.10.1.zip`;
  its log calls itself 1.10.1-rc.0), CET 1.38.1. They went in directly, not through Vortex (Vortex may later flag
  them as external changes), with a manifest and an uninstaller (Build steps).
- **WolvenKit.Console 9.1.0** (CLI). It predates 2.5: files new in 2.5 list as bare hashes (see Gotcha 9).
- Blender 5.2 for the model and animation tracks (Blender's own glTF import/export was enough; the Cyberpunk
  Blender add-on 2.0.0 was downloaded and not needed).
- Saves backed up first with `um backup create "<Saved Games>\CD Projekt Red\Cyberpunk 2077" --name cp2077-saves`
  (163 files).

## Route and why
- **Route:** loader API. TweakXL for the item record, redscript for the logic, an ArchiveXL archive for meshes,
  textures, animations and the icon, Audioware for sound.
- 2.5 already ships player dual wield, so the mod plugs into it. A home-made second-gun system was considered and
  not needed.
- **Source of truth:** the game's own compiled scripts, decompiled with `redscript-cli decompile -i
  r6/cache/final.redscripts -o decomp -f` (1785 files, kept outside the repo), plus a full TweakDB dump (Build steps
  3). Nexus pages blocked fetches, so the scripts settled every question.

## How the game works (what we had to learn)
### Dual-wield eligibility and slots
- `gameItemData.CanDualWield(owner)` is true when the item has tag `DualWield` and the player has
  `NewPerks.Cool_Central_Milestone_2` (Double Trouble). A `QuestPreventDualWield` tag vetoes it unless a quest fact
  allows it. A `@wrapMethod` lets a tagged item skip the perk.
- `EquipCycleInitEvents.OnEnter` (`player/psm/equipment.script`) sets blackboard `IsDualWielding` and the anim
  wrapper `dual_wield` when the left-hand logic equips a ranged item.
- The weapon equip area has six slots: 0-2 are right-hand guns, slot `i+3` is the left partner of slot `i`.
  `EquipmentSystem.EquipWeapon` puts a dual-capable gun opposite the active slot when the active gun can dual
  wield too.
- Dual-capable vanilla handguns: Liberty, Unity, Lexington, Nue, Silverhand, Slaughtomatic, Nova, Overture.
  2.5 adds `*_Left_Hand` presets (`Items.Preset_Liberty_Default_Left_Hand`).

### First-person animsets
- The player's first-person animsets are entries `{animSet, priority, variableNames}` on the `root` animated
  component of `base\characters\entities\player\player_ma_fpp.ent` and `player_wa_fpp.ent`. The `root` component
  appears twice in each file (the editable list and the baked package). The Phantom Liberty archive
  (`ep1_2_gamedata`) carries a newer `player_wa_fpp.ent`; `player_ma_fpp.ent` is identical in every content archive.
  The lower priority number wins.
- A gun's variable is its TweakDB `friendlyName` (`w_handgun_constitutional_liberty`). The engine appends `_left`
  for the left hand, and `dual_wield` is on while akimbo.
- Liberty entries: single `...\handgun\constitutional_liberty\pma_w_handgun__constitutional_liberty.anims` p128
  `[w_handgun_constitutional_liberty]`; dual base `...\dual_wield\handgun\base\pma_w_handgun_dual_wield_base.anims`
  p100 `[dual_wield]`; dual right/left `...\dual_wield\handgun\constitutional_liberty\
  pma_w_handgun_dual_wield_{right,left}__constitutional_liberty.anims` p64 `[dual_wield, <friendlyName>(_left)]`
  (`pwa_` for female V). An entry needs all of its variables active.
- Gun-part animations (slide, magazine) live on the gun's `.app`: `Barrel`, `Magazine` and `MagazineReload`
  animated components carry `w_handgun_{right,left}__constitutional_liberty__{base1,mag_std}.anims` at p64 with
  `[RightHand]` / `[LeftHand]`, using the same unsuffixed clip names on both hands.

### Reloads
- Each hand runs its own reload state (`RightReload` / `LeftReload`), sets `reload_mask` 0/1 and picks its own
  variant at random (`reload`, `reload_01`, `reload_02`, `empty_reload*`; `_l` for the left).
- Vanilla `reload` and `reload_l` are byte-identical clips that animate both arms, both weapon bones and the
  camera. `player_dualwield.animgraph` masks them per hand: the left arm comes from the left clip through bone mask
  `_base_left_arm_full`, or `_base_left_arm_camera_full` (camera too) when the left hand is the one reloading.
- Playback speed is `BaseReloadTime / ReloadTime stat` (and `BaseEmptyReloadTime / EmptyReloadTime`), computed
  once per reload per weapon (`player/psm/weaponTransitions.script`, `GetReloadAnimSpeed`). So every `reload*` clip
  of one gun must be the same length, and every `empty_reload*` clip too.
- Vanilla dual reloads carry no gameplay events, only sound events.

### Sound
- The Liberty's player sounds are Wwise events fired by animation events, plus the fire event and environment
  tails. Their names are in `base\sound\event\eventsmetadata.json` (`audio_1_general.archive`): 27
  `w_gun_pistol_power_liberty_*` events (`_fire_single`, `_dry_fire`, `_mag_out`, `_mag_in`, `_mag_new_grab`,
  `_mag_rattle`, `_slide_release`, `_equip`, `_equip_first`, `_grab`, `_move`, `_aim_enter`, `_reload`, ...) and the
  tails `w_tail_pistol_power_liberty_{int,int_wide,ext_enclosed,ext_narrow,ext_open}`.
- Audioware 1.6+ can mute any vanilla event and still call back on it
  (`AudioEventCallbackSystem.RegisterCallback(eventName, target, fn)`, `PlayEvent.EventName()/EntityID()`). The mod
  mutes the Liberty player events while both hands hold its guns and plays its own bank from the callbacks. NPC
  Liberties use `w_gun_npc_liberty_*` events, so NPC guns are untouched.

### Item records, icons, localisation
- `Items.Preset_Liberty_Default`: `entityName` weapon_root, `appearanceResourceName` Preset_Liberty_Rogue,
  `audioName` wea_set_liberty, `baseReloadTime` 0.9. Its `slotPartListPreset` includes
  `HandgunAndRevolverScopesPartList` and two random mod lists after `inline0`-`inline3` (receiver, barrel, magazine,
  empty magazine).
- Appearance factory: `base\gameplay\factories\items\weapons\weapons_appearances.csv` maps
  `appearanceResourceName` to an `.app` (`compiledData` rows `[name, path, preload]`); the Liberty uses
  `...\constitutional_liberty\w_handgun__constitutional_liberty__rogue.app`, appearance `default`.
- Inventory icons: a `UIIcon.weapon_<appearanceResourceName>_<appearanceName>__<visualTag>` record pointing at an
  `.inkatlas` part (the Liberty's is in `base\gameplay\gui\common\icons\items\item_icons0.inkatlas`, a ~2.2:1 part).
- Localisation `onscreens` resources are CR2W files with a `.json` extension
  (`base\localization\en-us\onscreens\onscreens.json`, entries `{femaleVariant, maleVariant, primaryKey,
  secondaryKey}`).

## Build steps
1. **TweakDB dump (offline).** A small .NET 10 console app referencing WolvenKit.Console's `WolvenKit.RED4.dll`
   and `WolvenKit.Common.dll`: open `r6/cache/tweakdb_ep1.bin` with `WolvenKit.RED4.TweakDB.TweakDBReader`
   (`ReadFile(out TweakDB)`), load names with `TweakDBStringHelper.Load` on CET's
   `plugins/cyber_engine_tweaks/tweakdb/tweakdbstr.kark`, then for each id in `db.GetFlats()` write
   `name = value` (`db.Flats.GetValue(id)`). Enumerating `db.Flats` directly threw a NullReferenceException. Result:
   3,434,633 flats, all but 426 named. Grep it like a text file.
2. **Item record (TweakXL).** `Items.Croft_USPMatch` with `$base: Items.Preset_Liberty_Default`, own
   `friendlyName: w_handgun_croft_uspmatch`, own `appearanceResourceName`, tags `DualWield`, `IconicWeapon` and a mod
   tag, `baseReloadTime: 1.3`, `baseEmptyReloadTime: 1.5`, `uninterruptibleReloadStart(Empty): 0.4`, and
   `slotPartListPreset` cut to `Items.Preset_Liberty_Default_inline0..3` (Gotcha 3). Stat groups: clones of the
   Liberty's with an 18-round `MagazineCapacityBase`, `CycleTimeBase` 0.2, `ReloadTimeBase` 1.3 /
   `EmptyReloadTime` 1.5 to match the clips.
3. **Generated resources, never committed.** A build script reads WolvenKit json dumps of the user's own files
   (`WolvenKit.CLI convert s`), edits them and writes CR2W back (`convert d`), then `pack`s the depot folder:
   - the factory CSV (one row: our appearance name -> our `.app`);
   - the localisation `onscreens` file with our keys;
   - the `.app`: the Liberty `rogue.app` with only `default` kept. Edit `components` and the baked `compiledData`
     the same way, in place: swap mesh paths, hide unwanted parts with `isEnabled = 0` / `chunkMask = 0` on mesh
     components only (Gotcha 8), move the `Muzzle` and `fx_ejection_port` slots (on bone `fx_muzzle`) to the new
     muzzle and port, and add the gun-part sets at p60 next to the vanilla p64 dual entries;
   - patched copies of `player_ma_fpp.ent` and the ep1 `player_wa_fpp.ent` with 11 entries appended to both copies
     of `root` (Gotcha 1): the vanilla Liberty sets re-keyed to our variable, plus our sets;
   - the icon: a one-part atlas cloned from `item_icons0.inkatlas` (UV rect 0-1) over our texture, and a TweakXL
     `UIIcon.weapon_Croft_USPMatch_None__Default` record with `atlasResourcePath`/`atlasPartName`.
   - The pack step copies the depot minus sources (`.glb .png .blend .wav .md`), and minus `.json` except under
     `localization` (Gotcha 7).
   - These files are CDPR's own with our edits (and the animations in Assets are derived from the Liberty's
     clips), so the packed archive stays in your own install. A public release would ship only the mod's own parts
     and edits, and generate these files from each player's install, as the build script already does from yours.
4. **Animset priorities** (lower wins): vanilla Liberty sets under our variable at their vanilla priorities (base
   layer), flourishes p56, the two-gun flourish p52 (gated on a random variable), the standing reload set p48
   `[dual_wield, w_handgun_croft_uspmatch]`, the other five movement states p40 with an extra `croft_state_<x>`
   variable. A script sets those anim wrappers from the locomotion state and never mid-reload.
5. **Script (redscript):** the perk bypass, a one-time gift (quest fact), auto-pairing, the movement-state
   wrappers, and the sound layer. The core of the first two:
   ```swift
   @wrapMethod(gameItemData)
   public final func CanDualWield(owner: wref<GameObject>) -> Bool {
     if this.HasTag(n"CroftAkimbo") && !this.HasTag(n"QuestPreventDualWield") { return true; }
     return wrappedMethod(owner);
   }
   // one ItemID per gun (Gotcha 2): Codeware exposes ItemID.rngSeed
   let id: ItemID = ItemID.FromTDBID(t"Items.Croft_USPMatch");
   id.rngSeed = Cast<Uint32>(RandRange(1, 2147483647));
   GameInstance.GetTransactionSystem(game).GiveItem(player, id, 1);
   // the first gun takes the active slot (Gotcha 4); the second then lands opposite it
   let req: ref<EquipRequest> = new EquipRequest();
   req.itemID = id; req.owner = player; req.equipToCurrentActiveSlot = true;
   EquipmentSystem.GetInstance(player).QueueRequest(req);
   ```
6. **Compile-check outside the game** before every install: `redscript-cli compile -s <Codeware Scripts> -s
   <TweakXL Scripts> -s <Audioware r6/scripts> -s <our scripts> -b r6/cache/final.redscripts -o check.redscripts`.
7. **Sound bank:** `r6\audioware\CroftAkimbo\croft_akimbo.yml` (Audioware manifest, folder named after the mod):
   ```yaml
   version: 1.0.0
   sfx:
     croft_fire_01:
       file: fire/croft_fire_01.ogg
       usage: in-memory
       settings:
         volume: 1.0
   ```
   74 ids, OGG Vorbis q6 48 kHz, 1.29 MB. Shots carry their own reverb tail, so the vanilla tails are muted too.
   Audioware has no spatial flag in the manifest: `Play(n"id")` plays on V (the listener), `RegisterEmitter` +
   `PlayOnEmitter` for NPCs.
8. **Install with a manifest, uninstall exactly.** Two small Python scripts (not published):
   - `install_tree.py <staged> <game> <manifest.jsonl> <backup_dir>`: walk the staged tree; skip a file whose
     sha1 already matches; if a different file exists and isn't one this manifest added earlier, copy it to the
     backup dir first; copy; append `{"file", "sha1", "replaced_backup", "src"}` to the manifest.
   - `uninstall_tree.py <game> <manifest.jsonl>`: walk the manifest in reverse; delete a file only if its sha1
     still matches what was installed; restore `replaced_backup` if there is one.
   - The frameworks went in the same way (91 files, nothing overwritten); the mod is 81 files. A final check
     re-hashed all 172 against both manifests.
9. **CET console** to get the pair again: `Game.AddToInventory("Items.Croft_USPMatch", 2)`. (That gives one stacked
   item; the mod's own gift gives two seeded ones.)

## Verification
- **Unattended test harness** (a temporary redscript file, installed for tests only): `@wrapMethod
  SingleplayerMenuGameController.OnSavesForLoadReady` finds the target save by index and calls
  `GetSystemRequestsHandler().LoadSavedGame(i)`; in game it draws the pair and writes state to the screen through
  `SimpleScreenMessage` on blackboard `UI_Notifications.OnscreenMessage`, because neither `FTLog` nor Codeware's
  `ModLog` output was found on disk. Launch: `Cyberpunk2077.exe --launcher-skip -skipStartScreen`.
- **Probe result** on an unmodded save (AutoSave-7): `GUNS=2 R=CROFT L=CROFT DUAL=TRUE`; `um win shot` frames show
  two stainless USP Matches in first person.
- **Logs:** RED4ext loaded ArchiveXL 1.28.0, Audioware, Codeware 1.21.1, TweakXL 1.12.0 (1,032,136 game addresses);
  redscript "Compilation complete"; TweakXL "Import completed"; ArchiveXL loaded the factory and merged the
  localisation; Audioware "74 in-memory static audio ids, no error reported".
- **Sound oracle:** `um win record --exe Cyberpunk2077.exe --out croft_fire --seconds 40` (process-loopback audio, f32le stereo
  48 kHz) while a script clicked fire and held R. A Python script took the first 120 ms of each reference sound
  (mono, z-normalised), FFT cross-correlated it against the recording, normalised by the recording's local energy,
  and printed the best score per file. Croft shots scored 0.70-0.94; the vanilla Liberty shots 0.50 at most.
  Reload foley scored ~0.4, masked by the shot tails, so it is not confirmed. `um video mux` joined clip and audio.
- **Reloads:** frames at 5 fps show both guns dropping out of view and back (belt slam), and a second variant
  flipping a gun.
- **Not verified:** each movement-state reload set (only standing reloads were triggered), the reload foley, male V
  (the saves are female V), and whether the gun-part timing sets also affect single-wield reloads.

## Gotchas
1. **ArchiveXL `animations:` entries never reach the player.** **Symptom:** no "Initializing animations" lines in
   the ArchiveXL log and V uses no custom animsets. **Cause:** ArchiveXL's animation extension keys on the owning
   entity's `templatePath` (`OnInitializeAnimations` in `src/App/Extensions/Animation/Extension.cpp`). An on-screen
   probe of Codeware's `GetTemplatePath()` on V matched none of `player_[mw]a_(fpp|tpp).ent`, although `player.csv`
   maps `player_male`/`player_female` to them. **Fix:** ship patched copies of `player_ma_fpp.ent` and the ep1
   `player_wa_fpp.ent`, generated at build time from the user's own files (312 -> 334 entries, sizes within 1 KB of
   vanilla, round-tripped through `convert s` to check). Another mod that replaces those files will conflict.
2. **The second gun never reaches the left hand.** **Cause:** `TransactionSystem.GiveItemByTDBID(player, id, 2)`
   creates one unseeded ItemID with quantity 2, which is one item. **Fix:** build each ItemID with
   `ItemID.FromTDBID`, set a random `rngSeed` (a Codeware field on ItemID) and `GiveItem` each once.
3. **A random reflex sight appears on one gun.** **Cause:** seeded copies of the Liberty preset roll
   `HandgunAndRevolverScopesPartList` and two random mod lists from `slotPartListPreset`. **Fix:** keep only
   `inline0`-`inline3`. `slotPartList` (what the player may install) stays the Liberty's.
4. **The new gun becomes the left partner of whatever V held.** **Cause:** `EquipWeapon`'s opposite-slot logic.
   **Fix:** `EquipRequest.equipToCurrentActiveSlot = true` for the first gun; queue the second normally.
5. **Saves made with now-removed mods crash ~13-30 s after loading once RED4ext is present.** **Symptom:**
   `EXCEPTION_ACCESS_VIOLATION` reading 0xFFFFFFFFFFFFFFFF; all 12 dumps fault in the resource loader (RVA
   0x32CC24-0x32CFD1, nearest symbols `res::ResourceReference::EnsureLoaded` and
   `res::ResourceLoader::TryAcquireResourceToken_NoLock`). **Bisect:** it crashed with everything, without
   UltraPlus, without Audioware, without CET (`version.dll` renamed), with bare RED4ext and no plugins, with
   redscript's compiler off (`engine/tools/scc.exe` and `scc_lib.dll` renamed) and with the vanilla script blob.
   Pure vanilla (`bin/x64/winmm.dll`, RED4ext's loader, renamed too) loads the same save fine; an unmodded save
   loads fine with everything installed. **Cause:** not found; likely data the purged mods left in those saves.
   **Fix:** test on a save the game doesn't flag as modded (each save's `metadata.9.json` says), and tell the user
   before blaming your mod. Dumps: `%LOCALAPPDATA%\REDEngine\ReportQueue\`; read them with the Python `minidump`
   package and name RVAs with `cyberpunk2077_addresses.json`.
6. **Unattended input does nothing in menus.** **Causes:** UltraPlus's CET "Degraded Mode" dialog (its UltraTool
   doesn't support 2.5) sits over the main menu and swallows mouse and keyboard; even without it, mouse clicks never
   registered in the main menu; `um win drive` `key` taps got dropped; and `wait` is not a WinDrive command (it's
   `sleep`). **Fix:** move that CET mod aside for tests; drive the menu by keyboard only with `scanmode on`,
   `hold <vk> 90` and `sleep` between keys. Esc closes the "Changes in Patch 2.5" popup; focus then starts on the
   account button (bottom right): Left lands on Quit Game, then Up x6 reaches Continue. A small script that finds
   the yellow focus box in a screenshot made the navigation reliable. The intro video's red frames fool a
   "menu reached" check; wait for the logo instead. This drives the user's keyboard and mouse: ask first, and
   check `um win drive --proc Cyberpunk2077 idle` so you don't type over them.
7. **The localisation doesn't load ("Resource ... failed to load").** **Cause:** the `onscreens` resource is CR2W
   named `.json`, and a pack filter that skipped `*.json` dropped it. **Fix:** keep `.json` under `localization`.
8. **`WolvenKit convert d` fails on the edited `.app` ("could not be converted to ... RedPackage").** **Cause:** the
   hide-part edit also wrote mesh fields into `entVisualControllerComponent` dependency rows, which carry a `mesh`
   path too. **Fix:** only touch components whose `$type` ends in `MeshComponent`.
9. **New 2.5 files list as bare hashes in WolvenKit 9.1.** **Fix:** extract them with `extract --hash <file of
   hashes>`, and name them by FNV1a64 of the lowercase depot path with backslashes, e.g. guessing
   `base\animations\weapon\firearms\dual_wield\handgun\<gun>\w_handgun_{left,right}__<gun>__{base1,mag_std}.anims`
   against the hash list. Content search of the extracted `.bin` files (strings like `reload_l`) finds the rest.
10. **redscript compile errors that look odd.** `ArraySize(this.CroftItems())` -> "this use of a temporary value is
    not allowed" (assign to a variable first). `PlayerStateMachine.Weapon` doesn't exist in 2.5: it's
    `RightWeapon` / `LeftWeapon`. A path in an `r"..."` ResRef literal needs doubled backslashes.
11. **`um publish check --game <install>` fails 78 "game file copied verbatim".** **Cause:** the mod's own sources
    are byte-identical to the copies it installed into the game folder. **Fix:** confirm every hit points at the
    mod's own install folders (`r6/scripts/<Mod>`, `r6/tweaks/<Mod>`, `r6/audioware/<Mod>`); then they're false
    positives. The repo's `.gitignore` also excludes `*.archive *.mesh *.xbm *.anims *.app *.ent *.rig`.
12. **A fresh `final.redscripts.modded` was smaller than vanilla** (16.8 MB vs 19.3 MB with no mod sources). It
    wasn't the crash in Gotcha 5 (that also happened with the compiler off), but don't compare blobs by size.

## Assets
- **Model:** the owner's own procedural, photo-traced USP Match builder from an earlier project (Blender scripts,
  not published): every part is generated twice from traced profiles (low poly with hard edges only at UV seams,
  high poly with bevels and a bump material), then baked to 2048 maps. Result: 9,764-tri gun + 2,522-tri magazine.
  - Fit: game position = builder coordinates rotated -90 deg about Z plus (0, +0.15927, +0.0400) m, no scale. That
    came from fitting the grip profile, then nudging (0, -3, +1) mm so V's exported hand pose sits on the grip as on
    the Liberty (hand web within 2.3 mm).
  - Rigid skin to the Liberty bones: frame/barrel/weight/grip -> `barrel`, slide and sights -> `slide`, `hammer`,
    `weapon_trigger`; `slider_down` left empty (it moves 2 mm down on the Liberty, a USP slide stop moves up).
    The magazine needs two meshes, one on `magazine` and one on `magazine_reload` for the `MagazineReload`
    component, plus a `_shadow` mesh (`isShadowMesh=1`).
  - Materials: two local instances of `engine\materials\metal_base.remt` per mesh with `BaseColor`, `Metalness`,
    `Roughness`, `Normal` (+ the `*Scale`/`*Bias`/`NormalStrength` params). XBM import settings (WolvenKit CLI
    `appsettings.json` `XbmImportArgs`): `_d` TEXG_Generic_Color, gamma, TCM_QualityColor; `_r`/`_m`
    TEXG_Generic_Grayscale, linear, TCM_QualityR; `_n` TEXG_Generic_Normal, TCM_Normalmap (DirectX green, as the
    vanilla Liberty and Kenshin normals); icon TEXG_Generic_UI, gamma, TCM_None. Mesh export also needed
    `MaterialRepositoryPath` and `MeshExportArgs` in that file.
  - FX: the Liberty muzzle sits 83 mm ahead of and 5.4 mm below the USP's, so `Muzzle` -> (0, -0.0830, +0.0054)
    and `fx_ejection_port` -> (0, -0.2188, +0.0094). Iron sights read ~6 mm high in ADS (USP sight tops at Z 0.0585
    vs 0.0526); left as is.
- **Animations:** derived from the vanilla Liberty dual clips with keyed edits (exported to glb with `-gp <game>`,
  edited in Blender), 30 fps, every clip starting and ending on the vanilla dual idle frame. Per movement state
  (stand, walk, run, sprint, crouch, air) six regular and six `_l` clips: `reload*` 1.300 s (40 frames),
  `empty_reload*` 1.500 s (46 frames); flourishes `idle_break_01/02`, `equip`, `first_equip`, `unequip`. Events use
  the vanilla Liberty sound event names (`mag_out` / `mag_in` / `slide_release` frames, `mag_new_grab` at seat-6,
  `mag_rattle` at seat-3). WolvenKit.Console 9.1 can't import animations; the animation track used its own
  unpublished importer that writes `.anims` from WolvenKit json, with kraken.dll compression because
  WolvenKit couldn't load Oodle. Its encoding, event writing and compression settings were not recorded, so this
  step can't be reproduced from this note yet: it is the one gap (see Open questions). All 16 files round-tripped
  with 0 mismatches.
- **Sound:** 74 sounds, from ElevenLabs Sound Effects v2 (~120 takes) and Mirelo SFX 2.0 on fal (~$0.49 total;
  ElevenLabs returned near-silent takes for requests under 0.8 s, so every take was screened), then designed in
  Python (layering, EQ, compression, synthetic reverb, true-peak limit at -1 dBTP; shots ~-10 to -12 LUFS),
  levelled against the vanilla Liberty sounds measured from the game's opuspak/wem containers.

## Cost and time
One overnight session, about 2.5 hours of wall clock, with the model, audio and animation tracks run as three
parallel helper agents (one heavy process at a time through a lock file). fal spend about $0.49.

## Open questions
- What the player entity's `templatePath` really is at runtime, so ArchiveXL could add the animsets instead of
  shipping patched player entities.
- What in the old modded saves trips the resource loader under RED4ext.
- Whether the per-state reloads, the reload foley and the male-V animations look right in game.
- The `.anims` writer: its key encoding, event block and kraken compression settings need writing down (or the
  importer publishing) before the animation step is reproducible.
