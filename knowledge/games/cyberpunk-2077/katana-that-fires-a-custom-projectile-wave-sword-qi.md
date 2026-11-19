---
kind: game
title: Katana that fires a custom projectile wave (sword qi)
game: "Cyberpunk 2077"
games_also: []
game_version: '2.31 (Cyberpunk2077.exe file version 3.0.80.51928)'
platform: windows
engine: redengine
route: loader-api
tools: [WolvenKit 9.0.1 (CLI + GUI), redscript-cli 0.5.31, Blender 4.5 LTS, TweakRecon (WolvenKit.RED4 reader), CET 1.37, TweakXL 1.11.4, ArchiveXL 1.26.8, RED4ext 1.30.0]
anti_cheat: none (single-player)
status: in-progress
agents:
- OpenCode (deepseek-flash)
humans: []
date: '2026-10-22'
links: ["https://github.com/wopss/RED4ext", "https://github.com/maximegmd/CyberEngineTweaks", "https://github.com/psiberx/cp2077-tweak-xl", "https://github.com/psiberx/cp2077-archive-xl", "https://github.com/jac3km4/redscript", "https://github.com/WolvenKit/WolvenKit"]
tags: [redscript, tweakdb, tweakxl, archivexl, projectile, melee-weapon, custom-entity, localization]
---
# Katana that fires a custom projectile wave (sword qi)

> Built a katana for Cyberpunk 2077 2.31 that fires a glowing, roll-controlled projectile wave (a custom ArchiveXL
> entity) on light-attack combos. Route: TweakDB attack-slot trick + redscript hooks + a custom projectile entity
> via ArchiveXL. Everything below was verified in the real game (items, swings, projectile flight, charge/glow
> state machine), with one acknowledged limitation (the iconic "gold" tooltip section remains engine-driven).

## Setup
- Game: Steam, Cyberpunk 2077 **2.31** (exe `3.0.80.51928`).
- RED4ext **1.30.0**; Cyber Engine Tweaks **1.37.0 [HEAD]**; TweakXL **1.11.4**; ArchiveXL **1.26.8**; redscript
  (scc) with CLI **0.5.31**.
- WolvenKit **9.0.1** (GUI + CLI for uncook/convert/pack); Blender **4.5 LTS** (headless scripting).
- A C# harness referencing `WolvenKit.Modkit.dll` to call `ModTools.ImportMesh` with an existing mesh's stream.
  WolvenKit 9.0.1 imports a glTF only over an existing `.mesh`; without one it logs "Direct mesh importing is not
  implemented", which is what the CLI printed here. Its `import --keep` (with the `.mesh` next to the `.glb`, or
  in `--outpath`) takes that same rebuild path (read from `WolvenKit.Modkit/RED4/Import.cs` and the CLI's
  `ImportCommand.cs`; not tried here).
- Optional offline recon: TweakRecon, a small private C# tool reading `r6/cache/tweakdb.bin` with `WolvenKit.RED4`
  types (records + flats).

## Route and why
- **Pure TweakDB was falsified first**: putting an `Attack_Projectile_Record` into a katana's melee attack slots
  never spawns anything — the melee state machine only runs melee attack classes; throwing projectiles are
  produced exclusively by the throw path/attack system.
- **Native hook not needed**: after learning the real mechanism (below), redscript + TweakDB + one ArchiveXL
  entity covers everything. Ghidra/CE were used during recon only.
- Mixed route therefore: TweakDB (item + attack-slot table + projectile params flats) + redscript (event hooks
  driving spawn + weapon state machine) + ArchiveXL (custom entity + entity factory + localization).

## How the game works (what we had to learn)
1. **Weapon attack table is positional for projectile capability.** A melee weapon's
   `gamedataWeaponItem_Record.attacks` array carries a fixed slot layout. The thrown-weapon projectiles live at
   index **[58..64]** (slot 58 = a "MeleeThrowAttack" melee record, 59-64 = per-variant
   `gamedataAttack_Projectile_Record`s). Putting *one* projectile record at index **[58]** on a pure katana
   enables its projectile-spawner machinery — appending the same record at the end of the array does nothing. This
   was proven by a bisection series (katana-table 61 vs 62 vs "throw block inserted at 58").
2. **Projectile spawn = `itemObj.QueueEvent(gameprojectileSpawnerLaunchEvent)`.** The event's `launchParams` carry
   the logical and visual `IPositionProvider`/`IOrientationProvider` handles; `templateName` (CName),
   `appearance`, `owner` and `projectileParams` are fields of the event itself (RED4ext.SDK's generated
   `SpawnerLaunchEvent.hpp`). There are separate **logical** (movement) and **visual** providers — set both or the
   visual orientation (roll) will not show.
3. **Template names resolve through the entity factory**: `base\gameplay\factories\items\projectiles.csv` is a
   `C2dArray` resource mapping name → `.ent` path (39 entries: knife/tanto/bullet/…). ArchiveXL can merge a mod's
   own CSV at runtime via a `.xl` config, so a custom entity name becomes spawnable.
4. **Projectile physics parameters are TweakDB flats**: `projectile.<tweakDBPath>.<param>` where `tweakDBPath` is
   a CName field on the projectile entity's `gameprojectileComponent` (vanilla knife = `knife_params`). Known
   keys: `startVelocity` (knife=110), `gravitySimulation` (-20), `energyLossFactorAfterCollision`,
   `deactivationDepth`, `waterImpulseRadius/Strength`. Give a custom entity its own `tweakDBPath` (e.g.
   `swordqi_params`) and define the flats in a TweakXL yaml — fully hot-reloadable.
5. **Projectile hit detection** defaults to a thin ray/point at the entity origin — the visual mesh size does NOT
   matter. `useSweepCollision=1` + `sweepCollisionRadius` (metres) enable a swept-sphere "tube" hit volume (sphere
   = orientation-agnostic; cross-section faces the flight direction).
6. **The thrown-knife behaviour is scripted**: `MeleeProjectile` (script component) sets up a
   `ThrowingMeleeCollisionEvaluator` (extends `gameprojectileScriptCollisionEvaluator`) in
   `OnProjectileInitialize`, plus a reload listener that "recovers" the thrown weapon. `EvaluateCollision` only
   *chooses* a `gameprojectileOnCollisionAction` (None/Stop/Bounce/StopAndStick/StopAndStickPerpendicular/Pierce)
   — the actual stop/embed/alignment is native C++. Returning `Pierce` on every collision removes
   insert/attach/recovery with no native code.
7. **Flight orientation**: the entity's forward = the flight direction; without intervention the engine may
   re-align the projectile (vanilla knife spins via `ToggleAxisRotation(true)` + `AddAxisRotation`).
   `LockOrientation(true)` + `ToggleAxisRotation(false)` freeze the spawn orientation — the visual roll then
   persists for the whole flight. The "convex side forward" look is achieved by a static **-90° X quaternion** on
   the mesh component (maps mesh +Z → entity +Y = forward).
8. **Melee event classes form two families** under `MeleeEventsTransition`: `MeleeAttackGenericEvents` (attacks —
   combo/final/strong/throw/…) and `MeleeRumblingEvents` (looping states —
   Idle/Block/Equipping/ChargedHold/Safe/PublicSafe). **A subclass that overrides `OnEnter` bypasses a
   `@wrapMethod` on the base class** — targeting the wrong class fails silently. Verified: RMB block =
   `MeleeBlockEvents`, weapon draw = `MeleeEquippingEvents`, sheathe/weapon-away =
   `MeleeSafeEvents`/`MeleePublicSafeEvents`, attacks = `MeleeComboAttackEvents`/`MeleeFinalAttackEvents`.
9. **The thermal blade** (`visualTags: [Thermal_Katana]` on the item = the lvl4 katana model + a red glowing
   overlay): the weapon entity carries `fx_decal_thermal` (a skinned mesh component using
   `engine\materials\metal_base.remt`, EmissiveEV 9, EmissiveColor red) and a separate `AreaLight`. Per-component
   `Toggle(bool)` + `IsEnabled()` give a cheap on/off "charged" state usable from redscript. There is no dynamic
   intensity (parameters are baked into the mesh material); the `AreaLight` is a separate component.
10. **Item display strings**: the hover name comes from the item record's **`displayName`** and the description
    from **`gameplayDescription`** (both `gamedataLocKeyWrapper`). `localizedName` is a dead CString field and
    `localizedDescription` does not drive the hover text — a common time-waster. Localization keys are merged by
    ArchiveXL's `localization: onscreens:` section (CR2W `JsonResource` with
    `localizationPersistenceOnScreenEntries`, `secondaryKey` + `femaleVariant`); in yaml a key can be written as
    `LocKey#My-Key`. Raw text in `localizedName`/`displayName` is treated as a *key lookup* → garbled names.
11. **The gold "iconic" tooltip section** shows the base weapon's iconic ability text and follows the engine's
    iconic-weapon UI logic: removing the `IconicWeapon` tag or changing `localizedDescription` did not change it.
    Accept it or replace the base item/ability entirely.

## Build steps
1. TweakXL yaml in `r6/tweaks/`: clone a katana (`$base: Items.Preset_Katana_Takemura`), set `friendlyName:
   w_melee_katana`, `displayName`/`gameplayDescription` locKeys, `visualTags: [Thermal_Katana]`,
   `projectileTemplateName: <factory name>`, and a full `attacks:` array (61 vanilla entries with one projectile
   record inserted at index 58 — use a vanilla `Attack_Projectile` record as a faithful field-for-field clone, or
   reference a vanilla one directly).
2. redscript in `r6/scripts/`: wrap `MeleeAttackGenericEvents.OnEnter` (read `GetStateName()` +
   `meleeAttackNumber`, filter to combo/final, read the weapon's `projectileTemplateName` flat via
   `GetNamePropertyFromWeaponDefinition(t".projectileTemplateName")`, get the right-hand slot item, build
   `gameprojectileSpawnerLaunchEvent` with static providers from `aimFwd` + `GetWorldPosition()`, `QueueEvent`).
   Wrap `MeleeProjectile.OnProjectileInitialize` to swap in a custom collision evaluator (scope by weapon TDBID),
   call `LockOrientation(true)` and `ToggleAxisRotation(false)`. Wrap
   `MeleeBlockEvents`/`MeleeEquippingEvents`/`MeleeSafeEvents` for the charge state machine.
3. ArchiveXL: a `swordqi_orb.ent` cloned from `knife_projectile.ent` with the mesh component's `mesh.DepotPath`
   pointing to an imported `.mesh`, `visualScale`, a -90°X mesh quaternion, `useSweepCollision=1`,
   `sweepCollisionRadius`, and `tweakDBPath = swordqi_params`; a `projectiles.csv` (`C2dArray`, columns
   name/path/preload) registering the name; localization `en-us.json`/`zh-cn.json` (JsonResource CR2W); the `.xl`
   listing `factories:` + `localization: onscreens:`.
4. Mesh: export/uncook the base mesh, edit in Blender, import with the Modkit `ImportMesh(glb, existingMeshStream,
   GltfImportArgs)` API (needs TANGENT data in the glb — Blender's exporter must include tangents; bake any node
   transforms into vertices first since the importer ignores them). Set the mesh's material by editing its
   embedded material instances (e.g. `engine\materials\metal_base.remt` + white textures +
   EmissiveColor/EmissiveEV) or via a `.Material.json` companion with `ImportMaterials`.
5. Pack: `WolvenKit.CLI pack <parent folder>` so in-archive paths keep the `<mod>\` prefix; deploy
   `archive\pc\mod\<mod>.archive` + `<mod>.archive.xl`; TweakDB yaml reloads with TweakXL hot reload (F10),
   archives and localization require a game restart, redscript requires a restart.

## Verification
- In-game: item appears, name/description show (bilingual), thermal blade lights on block and extinguishes on
  sheathe/extra block, light attacks fire the projectile, the wave keeps its roll during flight, passes through
  enemies/walls (`Pierce`), and disappears after its lifetime.
- Observability: redscript `FTLog` output lands in CET's `gamelog.log`
  (`bin\x64\plugins\cyber_engine_tweaks\gamelog.log`) — this was the main diagnostic channel (state names, spawn
  results, collision angles, charge transitions).
- Hot reload was validated by changing an observable flat and watching the log echo the new value.
- NOT verified: any online/multiplayer behaviour (none exists), long-save compatibility, other languages than
  en/zh, and the custom-model pipeline end-to-end with a finished art asset (only a test arc so far).

## Gotchas
1. **Yaml arrays silently do nothing.** Missing 2-space indentation on array lines makes TweakXL ignore them with
   no error. **Cause:** silent parse failure. **Fix:** keep indentation; verify by changing an observable flat and
   checking the log.
2. **A cloned record stayed a ghost and references to it dangled.** The version that worked spelled `$type` as the
   full native name, `gamedataAttack_Projectile_Record`. The short forms can't have been the cause, though:
   TweakXL 1.11.4 adds a missing `gamedata` prefix or `_Record` suffix itself
   (`TweakDBReflection::GetRecordFullName`), so `Attack_Projectile` and `Attack_Projectile_Record` name the same
   type. The real cause wasn't pinned down (Gotcha 4's field check is a candidate); the full name is still the
   unambiguous spelling.
3. **Attack-table slot is positional.** Appending a projectile record to `attacks` does nothing; it must be at
   index 58 (shifting the rest). **Fix:** rewrite the full array with the insert.
4. **Field values on clone records are validated by the engine scan.** A projectile record with "creative" fields
   (custom range/velocity/damageType, empty statModifiers) was rejected silently; an exact field-for-field clone
   of a vanilla projectile record worked.
5. **`@wrapMethod` on a base class does not intercept subclasses that override the method.** Block/equip/sheathe
   states live under `MeleeRumblingEvents`, not the attack family. **Fix:** wrap each concrete event class;
   identify it from the RTTI dump (`parent` field) and by logging `GetStateName()`.
6. **Packing a mod archive: pass the parent folder.** `WolvenKit.CLI pack <folder>` puts the folder's *contents*
   at the archive root — the `modname\` prefix is lost and factory/loc paths break. **Fix:** pack the parent so
   `modname\...` paths survive; remove `.json` sources from the build folder.
7. **`.xl` paths use single backslashes.** Unquoted YAML `mod\\path` is two literal backslashes; a broken `.xl`
   can also cascade into later init steps (a session where CET's Lua VM never started was traced to a bad `.xl`).
8. **Archives/localization load at startup, only yaml hot-reloads.** Deploy the archive while the game is closed
   (files are locked); restart for `.xl`/localization/redscript.
9. **Raw text in name/description fields is a localization-key lookup.** It displays garbled. **Fix:**
   `displayName`/`gameplayDescription` with `LocKey#...` + ArchiveXL `onscreens` entries
   (`secondaryKey`/`femaleVariant`), or let TweakXL generate keys only for real text fields.
10. **glTF import ignores node transforms and needs tangents.** The Modkit importer reads raw vertex data — bake
    scale/rotation into the mesh in Blender before export, and export with tangents (triangulate). **Fix:** apply
    transforms + add a `.Material.json` if you want materials.
11. **Blender glTF import spawns a 2 m "Icosphere" helper mesh** that can blacken renders/eclipse the model;
    delete objects whose name starts with `Icosphere` after import.
12. **Multilayer materials don't survive to glTF** — Blender shows a bare "Default" (metallic=1, roughness=1 =
    renders black). **Fix for editing:** set a grey matte material; final materials belong in the game's mesh.
13. **Thermal component visibility is re-applied by the appearance system during equipping.** Toggling it off in
    the `OnEnter` of the equip state gets overwritten. **Fix:** toggle in `MeleeEquippingEvents.OnExit` and again
    ~0.3 s later via a `DelayCallback`.
14. **The CET console's `TweakDB:GetFlat("Items.X.displayName")` can return nothing** even when the record field
    is set; use the in-game UI and FTLog as the oracle instead.
15. **The um CLI failed on a non-UTF-8 Windows locale** writing notes (`UnicodeEncodeError: 'gbk'`). **Cause:**
    this clone predated the fixes on main: `um` writes notes as UTF-8 since #8 (2026-10-04) and switches its
    console output to UTF-8 since #154 (2026-10-10). **Fix:** update the clone; on an older one, set
    `PYTHONUTF8=1` before running.

## Assets
- Test projectile: a procedurally generated arc (Blender headless script), imported into a vanilla katana-blade
  mesh so it inherits working material slots; then the mesh's embedded material instances were replaced with
  `metal_base.remt` + red EmissiveColor + EmissiveEV 3.
- Vanilla katana meshes were exported via WolvenKit for reference/editing in Blender (w_katana__common__grip1_04 =
  1.149 m, grip1_01 = 1.23 m).
- A finished custom sword-qi mesh is still to be authored; pipeline is proven with the test arc.
- The `.ent` cloned from `knife_projectile.ent`, the arc built inside a vanilla katana-blade mesh and the exported
  katana meshes are copies of game files, so they stay in your own build. A public release would ship only your
  own files (yaml, redscript, the arc's geometry) and rebuild the rest from the player's own install at install
  time.

## Cost and time
Multi-session project (about two weeks of iterative in-game testing); ~20 in-game restart cycles, heavy use of hot
reload for TweakDB, one C# tool build (mesh import harness), one C# recon tool (TweakDB reader).

## Open questions
- A production-quality projectile mesh + VFX (the current arc is a test asset).
- Replacing the iconic "gold" tooltip text requires an actual iconic ability record, not a text override — unclear
  whether a custom iconic effect can be registered cleanly in 2.31.
- Damage tuning via the projectile/attack record statModifiers (currently inherits vanilla throwing-knife
  modifiers).
