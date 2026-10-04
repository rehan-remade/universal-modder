---
kind: game
title: BL3 weapons and movement in Borderlands 2 (Willow2 SDK mods)
game: Borderlands 2
games_also: ["Borderlands 3"]
game_version: "Borderlands 2, Steam 49520, changelist 2863302 (exe v8639); Willow2 Mod Manager v3.8 (unrealsdk 3.2.0, pyunrealsdk 1.10.0, Python 3.14)"
platform: windows
engine: unreal
route: loader-api
tools: ["Willow2 Mod Manager v3.8 (pyunrealsdk)", "OpenBLCMM-Data BL2 dump (2023-04-20)", "pure-Python LZO1X package reader", "BPD graph decoder", "um scan"]
anti_cheat: "none; single player only (co-op untested)"
status: working
agents:
- Claude Code (Opus 5.5)
humans: ["@Pherdee-boi"]
date: '2026-10-03'
links: []
tags: [borderlands, gearbox, ue3, pyunrealsdk, weapons, anointments, movement, slide, mantle, ground-slam, projectiles, hooks]
---
# BL3 weapons and movement in Borderlands 2 (Willow2 SDK mods)

> Two Python SDK mods bring Borderlands 3 mechanics into Borderlands 2.
>
> **BL3 Weapons** gives each BL2 gun maker its BL3 trait:
> - Maliwan element switch, Vladof underbarrels, Torgue sticky/impact, Dahl fire modes;
> - Tediore turret/MIRV/chaser/bouncing throws;
> - COV-style overheat on Bandit, Jakobs crit ricochets, Hyperion ADS shield;
> - plus anointments.
>
> **BL3 Movement** adds slide, mantle and ground slam.
>
> Every feature was verified by the human playing the real game, with the agent reading `unrealsdk.log`
> between builds. No live in-game REPL was used (see Gotcha 1).

## Setup
- **Game:** Borderlands 2, Steam, Windows 11, changelist 2863302.
  - `um scan` reports it as "Unknown native engine". It is UE3 (Gearbox "Willow"), 32-bit,
    `Binaries/Win32/Borderlands2.exe`.
- **SDK:** [Willow2 Mod Manager](https://bl-sdk.github.io/willow2-mod-db/) v3.8.
  - **Install:** unzip over the game folder. That adds `Binaries/Win32/ddraw.dll`, `Binaries/Win32/Plugins/*` and
    `<game>/sdk_mods/`.
  - **Mods:** folders (or `.sdkmod` zips) in `sdk_mods/`. Log: `Binaries/Win32/Plugins/unrealsdk.log`.
  - **Replacing an old PythonSDK 0.7.x install:** move `ddraw.dll`/`python37.*` aside. With
    `legacy_mod_migration = true` (in `Plugins/unrealsdk.toml`), old `Binaries/Win32/Mods/*` are moved into
    `sdk_mods/` and run through `legacy_compat`.
- **Launch:** `Borderlands2.exe` can be started directly (skips the 2K launcher; `steam_appid.txt` is
  present). Mods do not hot-reload, so restart the game for every build.
- **Offline source of truth:**
  - the [OpenBLCMM-Data](https://github.com/BLCM/OpenBLCMM-Data/releases) BL2 pack: an SQLite object index plus
    `obj dump` text of every object;
  - the game's own `WillowGame.upk` / `Engine.upk` / `GearboxFramework.upk`, decompressed locally for
    function signatures. See the technique note
    `techniques/reading-ue3-gearbox-games-offline.md`.

## Route and why
Willow2 SDK Python mods (hooks plus object edits at runtime):
- **Text/hotfix mods (OpenBLCMM):** they can change stats but cannot add input, state or per-frame logic.
- **Native hooks:** they would duplicate what pyunrealsdk already gives.

Design rule that kept saves safe: **never put transient objects into anything the game saves.** Every part
swap uses real game parts. Runtime-only state (cooldowns, heat) lives in Python; per-gun choices (rolled
anointment, second element...) live in a mod settings JSON keyed by `DefinitionData.UniqueId`.

## How the game works (what we had to learn)
**Hooks.**
- Names are `Package.Class:Function`. State functions use `Package.Class:State.Function`, e.g.
  `WillowGame.WillowPlayerController:PlayerWalking.PlayerMove`.
- A pre-hook can return `Block`, or `(Block, value)` to replace a return value.
- To change a call's arguments: block it and re-call `func(args)` inside
  `unrealsdk.hooks.prevent_hooking_direct_calls()`.
- Post-hooks don't run for a blocked call; use `Type.POST_UNCONDITIONAL` if another hook may block it.

**Guns.**
- `WillowWeapon.DefinitionData` holds the parts. Parts include `BarrelPartDefinition` and
  `ElementalPartDefinition` (a gun's element is its elemental part, e.g.
  `GD_Weap_SMG.elemental.SMG_Elemental_Fire`).
- **Live part swap:** copy `DefinitionData`, change a part, call
  `InitializeFromDefinitionData(NewDefinitionData, InAdditionalQueryInterfaceSource=weapon.Owner,
  bForceSelectNameParts=False)` on the held gun. Mesh and stats update instantly.
- **`ReloadCnt` = rounds left in the magazine** (not rounds fired). Restore it after a re-init.
- **Firing mode:** `WillowWeapon.GetFiringModeDefinition()` is called per shot through ProcessEvent.
  Overriding its return swaps the firing mode with no part or save change (used for Torgue sticky with BL2's
  E-tech `Bullet_Pistol_Spiker`).
  - Uniques carry their special shot as `CustomFiringModeDefinition` on a part. Detect that and leave them
    alone.
- **Per-shot event:** `ConsumeAmmo(byte)` runs once per shot. `ShouldRefire()` returning False ends auto
  fire; `BeginFire(byte)` can be blocked.
- **Burst:** `AutomaticBurstCount` is an attribute that BL2 recomputes on zoom. Re-apply it every tick if you
  override it.
- **Zoom:** `ZoomState` takes the values `ZST_NotZoomed`, `ZST_ZoomingIn`, `ZST_Zoomed` and `ZST_ZoomingOut`.
- **Rarity:** `StaticCalculateWeaponRarityLevel(DefinitionData)` gives rarity: 1 white … 4 purple, 5
  legendary, 500+ special tiers (506 seen).

**Damage.**
- **Enemies:** damage arrives in `WillowAIPawn.TakeDamage(Damage, InstigatedBy, HitLocation, Momentum,
  DamageType, …)`. `DamageType` is a class `WillowDmgSource_*` (Bullet, Pistol, SubMachineGun, Shotgun,
  Sniper, MachineGun, Rocket, Grenade, Melee, StatusEffect, …).
- **Crits:** `WillowPawn.bWasLastDamageACriticalHit` is valid in a TakeDamage post-hook.
- **The player:** damage arrives in `WillowPlayerPawn.TakeDamage`.
- **Finding enemies:**
  - walk `WorldInfo.PawnList` / `NextPawn` (see Gotcha 4);
  - hostility: `player_pawn.IsEnemy(other)`;
  - alive: `IsAliveAndWell()`.

**Firing real shots from anywhere.**
- `WillowWeapon.Behavior_Fire(FiringModeDefinition, Direction, WorldBodyInterface, DamageAmount,
  DamageRadius, Momentum, DamageType, DamageTypeDefinition, ImpactDefinition, FireSourceSocket,
  bTreatDirectionAsDestination)`.
- Pass a projectile or pawn as the world body and `bTreatDirectionAsDestination=True`. You get real
  bullets with tracers and impacts, and walls block them physically.
- Supporting calls: `GetDamageTypeDefinitionForFiringMode(fm)` and `GetTraceImpact()`.
- **Explosions on demand:** fire `GD_Weap_AssaultRifle.FiringModes.Bullets_Assault_Torgue_GyroJet`
  (explodes on any impact) straight down.

**Tediore throws.**
- The thrown gun comes from a `Behavior_SpawnProjectile` in the Tediore weapon *type's*
  BehaviorProviderDefinition. Example: `WeaponType_Tediore_Pistol:BehaviorProviderDefinition_6` has `_4` (the
  normal throw) and `_5` (the Gunerang unique).
- Pointing the base spawner at another `ProjectileDefinition` while the gun is held changes its throw.
  Uniques keep theirs.
- Base throws explode on a `Behavior_Delay` fuse (1.7 s; 3 s for launchers).
- `WillowProjectile.InitializeFromDefinition` (post) catches the spawned projectile.
  `WillowProjectile.Explode` can be blocked.

**Movement.**
- **Slide:** `WillowPawn.CrouchedPct` scales crouch speed (0.5 normally). That's Juso's Sliding technique.
- **Hooks:** `WillowPlayerInput:DuckPressed`, `:Jump`, and `WillowPlayerController:PlayerWalking.PlayerMove`
  (has `DeltaTime`).
- **Sprint** is driven by `PlayerInput.bTryToSprint`, `WillowPawn.CanSprint()` and
  `WillowPlayerController.BeginSprint()`. Crouching cancels it.
- **Wall hits in mid-air:** set `Controller.bNotifyFallingHitWall = True` and widen `MinHitWall` (default
  is head-on only). UE3 then calls `Engine.Controller:NotifyFallingHitWall(HitNormal, Wall)` while airborne.
- **Landing:** `WillowPlayerPawn:Landed` is the physics landing event.
- **First-person look:** offsets on `Pawn.Arms.SkeletalMesh.RotOrigin` / `.Origin` move the arms and gun;
  `WillowPawn.BaseEyeHeight` dips the camera.

**HUD.**
- `WillowGameViewportClient:PostRender(Canvas)` with `Canvas.SetPos/SetDrawColor/DrawRect(w, h,
  Canvas.DefaultTexture)` draws gauges.
- `ui_utils.show_hud_message` for popups.

## Build steps
1. Install Willow2 Mod Manager v3.8 and launch once. Check `unrealsdk.log` for "pyunrealsdk … loaded" and the
   main menu for MODS.
2. Each mod is a package folder in `sdk_mods/`:
   - **`__init__.py`:** calls `mods_base.build_mod(...)` with explicit `options=`, `keybinds=`, `hooks=` and
     `on_disable=`.
   - **One module per feature:** e.g. `maliwan.py`, `vladof.py`, `slide.py`, `mantle.py`.
   - **`core.py`:** shared helpers (held weapon, rebuild, safe pawn walk, per-gun saved state via a
     `HiddenOption`).
3. Per-gun random choices are seeded with the string `"<feature>:<UniqueId>"` and stored, so they survive
   restarts and differ per feature.
4. Before every build, confirm the exact function signature from the decompressed package (technique note)
   instead of guessing, then copy the folder into `sdk_mods/` and restart.

## Verification
- **Oracle:** the human played each build in game (Sanctuary target dummy plus open maps) and described what
  happened. The agent read `unrealsdk.log`, where each feature logs one line on its first success, plus
  diagnostic counters such as "N enemies in range, M visible" and "ground slam: N enemies hit for X".
- **Freezes and crashes:** the last log line before the hang located the failing call (Gotchas 4 and 5).
  `.dmp` files in `WillowGame/Logs` were parsed with the `minidump` package; one launch crash at engine init
  (before mods load) was judged unrelated.
- **Not verified:**
  - co-op/multiplayer;
  - other BL2 builds;
  - TPS/AoDK;
  - long sessions;
  - every unique gun (only Unkempt Harold and Unicornsplosion were checked for Torgue);
  - mantle on many maps.

## Gotchas
1. **A file-drop "exec agent Python in game" bridge was refused by the agent's permission policy (RCE
   surface).** **Fix:** ship normal mods with fixed code, read the log, and ask the human to test. Budget for
   about 2–10 human test rounds per feature.
2. **Every sight check called from the SDK said "blocked".** `Actor.FastTrace` from a projectile always
   returned False, and `Trace` from a projectile never hit anything (shots went through walls).
   `pawn.FastTrace(a, b)` between points returned False, even straight up into open air. Even
   `Controller.LineOfSightTo(enemy)` returned False for enemies in plain view. **Cause:** unknown (possibly
   the projectile's collision channel and how these natives behave when called from Python). **Fix:** don't
   build on mod-side line of sight. Fire **real projectiles** with `Behavior_Fire` and let collision decide.
3. **Direct `TakeDamage` with `WillowDmgSource_Melee` froze the game** whenever an enemy was hit (hard hang,
   no dump). **Fix:** use `WillowDmgSource_Bullet` (or another gun source) inside
   `prevent_hooking_direct_calls()`. Bullet damage via direct TakeDamage worked in three features.
4. **Freeze when an area attack killed an enemy:** TakeDamage was called while walking
   `WorldInfo.PawnList`. A killed pawn leaves the list mid-walk and `NextPawn` can loop forever. **Fix:**
   collect targets first, then damage. Walk with a guard (stop on a repeated address or after 1000 steps).
   Also defer work out of physics events like `Landed` to the next `PlayerMove` tick.
5. **Underbarrel launcher came out with an empty magazine.** **Cause:** `ReloadCnt` is rounds *left*, not
   fired. **Fix:** a full magazine is `ReloadCnt = ClipSize`.
6. **"B only says stowed" on some Vladof ARs.** **Cause:** Vladof ARs can roll a Torgue rocket barrel
   natively (`AR_Barrel_Torgue_Vladof`), so the "underbarrel" was the gun's own barrel. **Fix:** never roll
   the gun's current part as its alternate.
7. **Torgue sticky broke uniques** (Unkempt Harold's split shot, the Unicornsplosion's unicorns). **Cause:**
   their special shot is a part's `CustomFiringModeDefinition`, and the firing-mode override replaced it.
   **Fix:** skip guns whose parts carry a firing mode, except the plain `FM_Rocket_Torgue`.
8. **Repurposing another gun's projectile behaviour didn't work.** The Deliverance's thrown gun never fires
   from other guns: its graph gates `FireShot` on checks tied to its own gun. The Avenger's throw is just a
   bouncing damage pulse, despite the name. **Fix:** build the behaviour yourself (hover by `SetLocation`
   every tick, since `SetPhysics(PHYS_None)` alone didn't hold, block `Explode`, fire real bullets). Decode the
   graph first (technique note) before assuming what a projectile does.
9. **Infinite mantle under an overhang.** **Cause:** the wall kept reporting contact while the pawn couldn't
   rise, so neither "height reached" nor "top cleared" ever happened. **Fix:** a hard time limit (1.2 s),
   abort if not rising for 0.25 s, abort on ground, and a 0.5 s retry cooldown. Make animation poses expire
   unless refreshed each frame.
10. **Python's seeded `random.Random(int)` gave the same Tediore throw on 4 of 4 guns.** That was bad luck
    (the distribution is fine over 20k IDs), but seeding every feature with the same int also correlates
    rolls across features. **Fix:** seed with the string `"<feature>:<UniqueId>"`.
11. **`um scan` doesn't recognise UE3.** It reports "Unknown native engine". Look for
    `WillowGame/CookedPCConsole/*.upk` and the UE3 package tag `0x9E2A83C1`.
12. **Old advice about `CallPostEdit(False)` wiping status effects** comes from the legacy SDK. In the new SDK,
    property writes don't post-edit unless you use `unrealsdk.unreal.notify_changes()`.

## Assets
None. All visuals come from the game's own parts, projectiles, explosions and arm poses.

## Cost and time
About two long sessions, roughly 40 human test rounds. Most time went into the Tediore turret (10 builds,
Gotchas 2 and 8) and the two slam freezes (Gotchas 3 and 4).

## Open questions
- Why do traces called from the SDK always report blocked/no-hit? A working mod-side line of sight would
  simplify a lot.
- Effects/UI pass: visible Jakobs ricochet shots via `Behavior_Fire`, anointment text on item cards.
- Per-legendary rules (keep the unique effect, add the manufacturer effect, or both).
- Co-op: everything is host/single-player only. The `networking` library in the mod manager would be the
  starting point.
