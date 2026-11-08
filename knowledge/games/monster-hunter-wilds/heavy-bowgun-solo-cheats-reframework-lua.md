---
kind: game
title: "Heavy Bowgun solo cheats with an online cut-off (REFramework Lua)"
game: "Monster Hunter Wilds"
games_also: []
game_version: "Steam 2246340 build 25921695 (2026-10-28 patch); REFramework nightly commit d052e8fd, TDB 81"
platform: windows
engine: re-engine
route: loader-api
tools: ["REFramework (Lua)", "Vortex (deploy)", "lupa (offline Lua syntax check + stub dry runs)"]
anti_cheat: "none found by um scan; online lobbies/SOS exist, so every cheat switches itself off when another player is in your instance or quest (checked online by the human)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-11-08
links: []
tags: [weapons, bowgun, ammo, gauges, fire-rate, damage, guard, hit-hooks, motion-speed, item-pouch, solo-only]
---

# Heavy Bowgun solo cheats with an online cut-off (REFramework Lua)

> One REFramework Lua script (`reframework/autorun/HBGCheat.lua`) adds toggles for the Heavy Bowgun:
> fire-rate slider (shots and reloads), no reload, infinite pouch ammo, full Ignition gauge and Wyvernsnipe
> ammo, damage multiplier, auto perfect block, no recoil / no flinch and instant charge. Every feature turns
> off while another player is near you or in your quest. All of it was confirmed in the real game by the human,
> over 13 versions, with logs the mod wrote as the oracle. A "load any ammo type" feature was a partial dead
> end and was removed (Gotcha 10).

## Setup
- Monster Hunter Wilds, Steam app 2246340, build id 25921695 (the 2026-10-28 patch), Windows 11.
- REFramework nightly (commit `d052e8fd`, TDB version 81), installed and managed through **Vortex**. The
  LooseFileLoader fails on this build ("Failed to find via.io.file"), so loose `natives\` mods don't load; Lua does.
- The mod ships as a Vortex zip containing only `reframework/autorun/HBGCheat.lua`, because Vortex manages
  `reframework\` and `reframework\autorun\` (Gotcha 8).

## Route and why
`loader-api`: REFramework Lua (`sdk.hook`, `get_field`/`set_field`, `re.on_pre_application_entry`). The only
community "infinite bowgun ammo" mod is a loose-file mod, which can't load on this REFramework build, and
every feature here needs runtime state anyway. Work went **probe first**:
- A read-only probe script snapshotted the bowgun's handling object and the save's item pouch.
- It logged every value change together with the current base/sub action, all action changes, the master
  hunter's hits on monsters, and online-looking getters on manager singletons.
- It also dumped a keyword-BFS type list.

The human played for a few minutes, and the cheat was designed from those logs.

## How the game works (what we had to learn)
- **Player:** `app.PlayerManager` singleton → `getMasterPlayer()` → `get_Character()` (`app.HunterCharacter`).
  `get_WeaponType()` returns 12 for the Heavy Bowgun (13 for the Light Bowgun). `get_WeaponHandling()` is an
  `app.cHunterWp12Handling` (parent `app.cHunterWpGunHandling`).
- **Magazine:** `handling:getCurrentAmmo()` returns an `app.cWeaponGunAmmo` (parent `app.cAmmo`).
  - Loaded, limit and backup counts are stored as encrypted `via.rds.Mandrake`, so read and write them with
    `get_LoadedAmmo` / `get_LimitAmmo` / `get_BackupAmmo` and `setLoadedAmmo(int)` / `setBackupAmmo(int)`.
  - All 20 slots are in `_Ammos[]`. The slot index equals `EquipShellInfo` index equals `_ShellType`.
  - Shots spend ammo through `cHunterWpGunHandling.subAmmo(System.Int32, System.Int32)`.
  - `EquipShellInfo[i].Num` is the magazine capacity, not a live count.
- **Pouch:** `app.SaveDataManager:getCurrentUserSaveData()._Item._PouchShell[]` holds `app.savedata.cItemWork`
  (`ItemIdFixed`, `Num`). In a hunt (not the training area), **ammo is consumed per shot** from this pouch,
  and the gun's `BackupAmmo` is re-derived from it every frame.
- **Gauges:**
  - `handling._EnergyBulletInfo._CurrentEnergy` (0–100, `get_MaxEnergy`) is the Ignition gauge used by energy
    mode, the gatling, the laser and the grenade.
  - `handling._SnipeAmmo._CurrentAmmo/_MaxAmmo` holds the Wyvernsnipe shots, which recharge via `_ChargeTimer`
    up to `_ChargeTime` (23 s).
- **Actions** (category, index):
  - Sub-actions: `Wp12SubAction.cShootMiddle` 2,1 (~0.94 s), `cShootHigh` 2,3, `cShootTriple` 2,2,
    `cReloadLight` 2,4 (~1.0 s), `cReloadMiddle` 2,5 (~1.7 s), `cShootGatling` 2,8, `cShootEnergyLaser` 2,10.
  - Base actions: `Wp12Action.cShootMiddle` 2,0, `cWeakPointSnipeShot` 2,27, `cEnergyGrenadeShot` 2,33,
    `cParryShot` 2,30, `cGuard` 1,141, `cGuardReaction_Tech` 1,146 (perfect guard).
- **Speed:** `HunterCharacter:set_SubActionMotionSpeed(float)` and `set_ActionMotionSpeed(float)` speed up the
  current motions. For reloads, see Gotcha 4.
- **Damage you deal:** `app.EnemyCharacter.evHit_DamagePreProcess(app.HitInfo)` and `evHit_Damage` fire in the
  same frame.
  - `HitInfo:get_AttackData()` (`app.cAttackParamPl`) `_Attack` is the per-hit computed value (e.g. 42.6 from a
    base of 13); `_FixAttack` and `_AttrValue` are the others.
  - Scaling `_Attack` in the pre-process hook works. Keep a per-object record of what you wrote, so an object
    seen twice isn't multiplied twice.
  - Owner check: `getActualAttackOwner()` == the hunter's `get_GameObject()`.
- **Damage you take:** `app.HunterCharacter.evHit_DamagePreProcess`, `evHit_ShellDamagePreProcess` (monster
  projectiles) and `evHit_Damage` (all with an `app.HitInfo`) return `app.Hit.RESULT`.
  - Returning SKIP_ORIGINAL in pre and `to_ptr(1)` (FAILURE) in post cancels the hit.
  - `HitInfo:get_DamageOwner()` is the victim.
- **Hit reactions:** `app.cHunterStockDamage.getDamageType(app.HitInfo, app.cHunterDamageInfo)` decides
  `cHunterDamageInfo._DamageType` (`app.HunterDef.DAMAGE_TYPE`).
  - NONE is -1; 0–20 cover small, slip, smash, upper, gesture, roar, wind and tremor; stun and statuses are
    21+, guards 34–44 (GUARD_TECH = 37), grabs 45–48.
  - Setting NONE in the post hook stops knockbacks while damage still applies.
- **Recoil:** `cHunterWp12Handling.getShootActType(int)` returns `WeaponGunDef.SHOOT_ACT_TYPE`.
  - Values: MIDDLE 7, HIGH 8, RAPID_MIDDLE 10, RAPID_HIGH 11, BUST_MIDDLE 5, BUST_HIGH 6, MORTAR_MIDDLE 14,
    MORTAR_HIGH 15.
  - Mapping each HIGH to its MIDDLE in a post hook (and skipping `updateRequestRecoil`) removes heavy recoil.
- **Charge:** `Wp12Action.cWeakPointSnipeCharge` and `cParryShotCharge` hold `_ChargeTimer` (it counts up)
  and `_ChargeLv`. The thresholds are in `handling:get_Wp12Param()._WeakPointSnipeBullet_ChargeInfo._Time[]`
  (boxed floats: read `m_value`). Pushing the timer to the maximum gives an instant full charge.
- **Online / multiplayer:** `PlayerManager.get_InstancedPlayerNum()` (1 when solo) and
  `get_QuestPlayerListCount()` (0 or 1 when solo). Treat either value above 1, or any read error, as "not solo".
  The human confirmed in an online session that the status switched to OFF. `app.NetworkManager` had no clear
  online flag.
- **Weapon data** (from the load-any-ammo work):
  - `app.WeaponDef.Data(app.WeaponDef.TYPE, Int32 weaponId)` returns `app.user_data.WeaponData.cData`, and
    `HunterCharacter:get_WeaponID()` gives the id.
  - `cData._ShellLv` is a 20-entry `app.BowgunShellLv.SHELL_LV_Fixed[]` (hashes: NONE -1067201536,
    SL_000 -29471984, SL_001 1468794112, SL_002 1769455744).
  - `cData._ShellNum` is a capacity **rank** (3, 2, 3, 1, 0 …), not a magazine size.
  - `handling:setupAmmoInfo(bool)` rebuilds `EquipShellInfo` from this data whenever items change.
  - The static `WeaponDef.ShellLv/ShellNum(type, id, slot)` helpers are not called by that rebuild.

## Build steps
1. Back up saves (`um backup create "<Steam>\userdata\<id>\2246340\remote\win64_save" --name mhwilds-saves`).
2. Write a read-only probe first. Snapshot the handling object with a recursive walker, watch for changes
   along with the current base/sub action class, and hook monster-hit functions. Have the human play solo
   **in the field** (not the training area) with the bowgun for 5+ minutes, then read the JSON.
3. In the cheat, do everything from `re.on_pre_application_entry("UpdateBehavior")`. Re-check "solo" every
   30 frames, and only act when the weapon type is 12 and the handling class is `app.cHunterWp12Handling`.
4. Hooks: `subAmmo` (skip for the master handling address), the enemy `evHit_DamagePreProcess` (damage), the
   hunter hit hooks (block), `getDamageType` (flinch), `getShootActType` / `updateRequestRecoil` (recoil),
   and the post hook of `WpGunSubActions.cReloadBase.doUpdate` (reload speed).
5. Infinite pouch: while the weapon is drawn (`get_IsWeaponOn`), refund any drop of `_PouchShell[].Num` and
   `BackupAmmo` back to the last seen value. Accept drops while it's sheathed, so moving ammo to the box doesn't
   duplicate it.
6. Package as a zip with `reframework/autorun/HBGCheat.lua` and install it through Vortex.

## Verification
- **Oracles:**
  - the probe's JSON;
  - the mod's own counters (Details panel, and a `cheat_status.json` dump), e.g. shots kept, refunds,
    boosted hits, blocks, recoil swaps, flinches removed, charge timer direction;
  - opt-in debug logs (`hit_log.json`, `pouch_log.json`), off by default (Gotcha 7);
  - the human's report, one feature per test.
- Lua syntax was checked offline with lupa. Every version was dry-run against a stub `sdk`/`re`/`imgui` with
  fake game objects (up to 109 scripted checks), including the multiplayer cut-off and "nothing written
  when a safety check fails".
- **Verified in game:** all eight features, and the online cut-off.
- **Not verified:** other bowguns' gatling/laser edge cases, controller-only play, and builds after 25921695.

## Gotchas
1. **Magazine count never changed in the probe's field walk.** **Cause:** `cAmmo` stores counts as encrypted
   `via.rds.Mandrake`. **Fix:** use the `get_*Ammo` / `set*Ammo` methods.
2. **"The pouch never goes down."** **Cause:** the human tested in the training area, which doesn't consume
   items. **Fix:** probe consumption in the field. There, ammo leaves the pouch **per shot**.
3. **Infinite pouch flickered (count dipped for a few frames).** **Cause:** `BackupAmmo` is re-derived from the
   save's pouch every frame, and the pouch was only checked every 5 frames. **Fix:** check the pouch every frame
   while the weapon is drawn.
4. **Fire rate sped up shots but not reloads.** **Cause:** the reload sub-action resets the motion speed during
   its own update. **Fix:** re-apply after it in three places: a post hook on `cReloadBase.doUpdate`,
   `re.on_application_entry("UpdateBehavior")`, and `get_MotionComponent():getLayer(i):set_Speed()` on every
   layer while reloading (restore the originals afterwards).
5. **"sol_lua_push: … is not a managed object" in the `getDamageType` hook.** **Cause:**
   `sdk.to_managed_object(args[3])` on an argument that isn't a managed object at that position. **Fix:** scan
   `args[2..5]`, convert each with pcall, and pick `app.HitInfo` / `app.cHunterDamageInfo` by type name.
6. **The probe logged real `false` values as errors.** **Cause:** the Lua idiom `ok and v or "ERR"` turns a
   successful `false` into "ERR". **Fix:** branch on `ok` explicitly.
7. **Frame drops every ~2 s.** **Cause:** scripts that `json.load_file` + `json.dump_file` a growing log every
   2 s. A leftover action-recorder probe from another mod had grown its file to 2.5 MB, and an 81 KB pouch log
   was being rewritten every 120 frames. **Fix:** keep debug logs off by default, write rarely, and remove probe
   scripts from autorun when done. REFramework's script runner can switch a script off to confirm the cause.
8. **Scripts vanished or came back.** **Cause:** Vortex manages `reframework\autorun`. A redeploy removed
   hand-placed files, and later re-deployed a removed probe from an older install. **Fix:** ship every script
   as its own Vortex zip and update through Vortex.
9. **Starting a call tracer (about 200 `sdk.hook`s at once) made REFramework reload all scripts twice.**
   **Cause:** mass hooking at runtime. **Fix:** don't. Find candidate methods from type/method listings
   (`get_methods`, parameter types) and hook a handful.
10. **"Load any ammo type" is a partial dead end.**
    - **What failed:**
      - Editing the handling's `EquipShellInfo` / `_Ammos` is undone by `setupAmmoInfo`.
      - Hooking `WeaponDef.ShellLv/ShellNum` does nothing (they're never called).
    - **What half-worked:**
      - Patching `cData._ShellLv` in memory (NONE → SL_000) unlocked 4 of 13 types. The patch was only made
        after checking that `read_dword` at offset 0x20 + 4i matched `get_element(i)`, and was restored when
        switched off.
      - Raising rank 0 to 1 in `_ShellNum` changed nothing.
    - **What still failed:** elemental (Flaming/Water/Thunder/Freeze/Dragon), status (Poison/Paralysis/Sleep)
      and Sticky ammo stayed out of the HUD ammo list, even though the rebuild loaded magazines for them.
      Forcing `_ShellType` / `SelectedShellItem` is switched straight back by the game.
    - **Fix:** none found. The feature was removed. The HUD's filter for those groups is the open question.
11. **Damage multiplier compounding risk.** **Cause:** an `AttackData` object can be seen more than once.
    **Fix:** key a small table by `get_address()` with the value you wrote, and multiply the original value
    again rather than the scaled one.
12. **Auto block missed some hits.** **Cause:** some monster hits never reached the hunter's
    `evHit_*PreProcess` cancel. **Fix:** fall back in `getDamageType` post: if the attacker's name starts
    with `Em` and the type is a flinch type, set `_DamageType` to GUARD_TECH (37) and `_GuardReaction` to
    TECHNICAL (4), which plays the game's own perfect guard.

## Assets
None.

## Cost and time
About 1.5 days of sessions with the human testing in game between versions (v0.1 → v0.13). Roughly half of
that went into the abandoned load-any-ammo feature.

## Open questions
- Which rule hides elemental, status and Sticky ammo from the Heavy Bowgun's HUD ammo list after `_ShellLv` is
  unlocked? Possible places to look: a GUI-side ammo filter, `app.MainShellType`/`AmmoStrength`, or the
  weapon's `ShellList` prefab set.
- Whether `get_InstancedPlayerNum` stays 1 in an online lobby when other hunters are far away. The cut-off
  switched OFF when it should; the edge cases weren't mapped.
