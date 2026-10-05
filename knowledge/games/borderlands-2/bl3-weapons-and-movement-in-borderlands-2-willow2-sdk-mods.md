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
date: '2026-10-04'
links: []
tags: [borderlands, gearbox, ue3, pyunrealsdk, weapons, anointments, movement, slide, mantle, ground-slam, projectiles, hooks, item-cards, loot-beams, hud, camera, materials, underbarrels, fire-modes, sound]
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
> - UI/effects (added 2026-10-04): anointment and Maliwan second-element lines on item cards, Jakobs
>   ricochet tracers, a tinted in-world Hyperion shield with a % in the HUD font, BL3-style rarity loot
>   beams with a ground glow and a legendary drop sound.
> - Later the same day: Vladof underbarrels on ARs, pistols and snipers (grenade/rocket launcher,
>   shotgun, taser, zip rockets, double barrel, bipod) with own ammo, sounds and muzzle effects; true
>   Dahl semi-auto; movement, shield and grenade anointments; a reworked Tediore MIRV/Chaser/turret.
>
> **BL3 Movement** adds slide and ground slam, with BL3-style camera work (slide FOV kick and tilt, slam
> shake). A mantle exists but is off by default: from the SDK nothing can see a ledge ahead
> (Gotcha 21).
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
- **Rarity:** `StaticCalculateWeaponRarityLevel(DefinitionData)` (items:
  `WillowItem.StaticCalculateItemRarityLevel`). The authoritative meaning is BL2's own table,
  `GlobalsDefinition.RarityLevelColors` in the data dump: 1 white, 2 green, 3 blue, 4 purple, **5 and 7-10
  legendary** (a legendary-pool drop reported 9), **6 e-tech**, 500 pearlescent, 501 seraph, 503, 506
  "rainbow". Don't assume "5 and up = legendary" (Gotcha 18).
- **Fire timing:** shots inside a burst are spaced by the gun's `FireInterval` (an `Engine.Weapon`
  attribute, read when each shot's refire timer starts); the pause after a burst is
  `WillowWeapon.BurstInterval`. Both can be written per frame like any attribute (Gotcha 16).

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
- **Text in the game's own HUD font:** the Scaleform HUD movie is `pc.myHUD.HUDMovie`. Create an empty clip
  (`CreateEmptyMovieClip`) and AS2 text fields in it with `GFxObject.Invoke("createTextField", ...)`, set
  `html`/`embedFonts`, and write `htmlText` with `<font face="$WillowCompact">`. BL2's white text with a
  black outline = 8 black copies offset by 1 px under the white field. Re-create it after map loads. The
  HUD stage is 1280 x 720 with the reticle at its centre; the ammo number is `_root.p1.bullets.bullet_c`.
- **Item cards:** every card (inventory, vendors, loot you look at) is an `ItemCardGFxObject`.
  `SetItemCardEx(WPC, InventoryItem, ...)` / `SetItemCard(...)` tell you which item it shows;
  `SetFunStats(FunStatsText)` is the red flavour block (HTML). Remember the item per card, then block
  `SetFunStats` and re-issue it with extra `<font color>` lines.

**Things in the world.**
- **Mesh pieces:** construct a `StaticMeshComponent` with the pawn as outer, `pawn.AttachComponent` it,
  then `SetAbsolute(True, True, True)`, `SetStaticMesh`, `SetMaterial(0, ...)`, and move it each frame with
  `SetTranslation` / `SetRotation` / `SetScale3D`. Turn its collision off. Hold components through
  `WeakPointer` and drop them all when the pawn changes (map load).
- **Recoloured materials at runtime:** construct a `MaterialInstanceConstant`, `SetParent(material)`, then
  `SetVectorParameterValue` / `SetTextureParameterValue` / `SetScalarParameterValue`. Parameter names are
  the material's `MaterialExpression*Parameter` subobjects in the decompressed package; a parameter stored
  with no name is set with the name `"None"` (the shield hex material's colour). Set
  `ObjectFlags |= 0x4000` (RF_RootSet) on objects you construct so they survive map changes.
- **Particles:** `WorldInfo.MyEmitterPool.SpawnEmitter(Template, Location, Rotation, ...)`. Beam2 tracers
  take their ends from `SetBeamSourcePoint(i, P, 0)`, `SetBeamTargetPoint(i, P, 0)` and
  `SetBeamEndPoint(i, P)` per emitter. Instance parameters: `SetVectorParameter` / `SetFloatParameter`
  (BL2's loot sparkle `fx_shared_items.Particles.Part_LootableLocator` is coloured by `RColor`).
- **Pickups:** loot on the ground is a `WillowPickup` with `Inventory` and `InventoryRarityLevel` (a
  different scale from the item's own rarity). Dropped guns are rigid bodies: they arrive through
  `PickupAtRest`, not `Landed` (Gotcha 19).
- **Sound:** `actor.PlayAkEvent(AkEvent)` plays a Wwise event from that actor
  (`Ake_UI.UI_Mission.Ak_Play_UI_Mission_Reward` makes a good "legendary dropped" sting).

**Camera.**
- `PlayerController.ClientPlayCameraAnim(Anim, Scale, Rate, BlendIn, BlendOut)` with BL2's always-loaded
  camera anims: `Anim_CameraAnimations.Explosions.Canim_Explosion_{Minor,Medium,Large,WarriorEarthquake}`
  and `Anim_CameraAnimations.Melee.Canim_*_Melee`. Startup has no `CameraShake` objects.
- FOV: add on top of `PlayerController.DesiredFOV` (BL2's sprint FOV uses the same attribute) and
  re-read it whenever BL2 changes it. A slight camera roll: `PlayerController.Rotation.Roll`.

**Changing how a gun fires, live (no part swap).**
- **Any firing mode on any gun:** override `WillowWeapon.GetFiringModeDefinition` to return e.g. BL2's real
  launcher mode `GD_Weap_Launchers.FiringModes.FM_Rocket_Vladof` on an AR or sniper, or the small AR rockets
  `GD_Weap_AssaultRifle.FiringModes.FM_Rocket_Vladof` on a pistol.
- **Attributes held every frame:** `ProjectilesPerShot`, `Spread`, `PerShotAccuracyImpulse` (kick),
  `FireInterval`, `ClipSize`, `StatusEffectChanceModifier`, and the pawn's `GroundSpeed`. Re-read the gun's
  own value whenever it differs from what you wrote (relative tolerance), and restore on stow, on weapon
  switch and on mod disable. A shotgun: 8 pellets, Spread 7, kick 12 (BL2's Jakobs shotgun type is 7 / 7.4 /
  11).
- **Own ammo:** note `WillowWeapon.GetAmmoCount()` on deploy and give back the difference with `AddAmmo(n)`.
  Setting `ClipSize` to the special shots removes BL2's reload prompt (the HUD compares rounds to
  `ClipSize`).
- **Element for a while:** `rebuild` with the type's `*_Elemental_Shock` part and save the original part in
  the mod's settings, so a save taken mid-way is put right on the next hold.
- **Spin-up barrels** fire slower until `WillowWeapon.BarrelSpinUpPercent` reaches 1 (the part's
  `StartingSpinUpFireIntervalMultiplier`); hold it (and `MagazineSpinUpPercent`) at 1 for a steady rhythm.
- **Aim-down-sights effects** are attribute effects applied by `ApplyAllZoomWeaponAttributeEffects` /
  `RemoveAllZoomWeaponAttributeEffects`; re-apply your values in post-hooks on both (Gotcha 25).

**Muzzle effects and sounds.**
- **On the first-person gun:** construct a `ParticleSystemComponent`, `SetTemplate`,
  `SetDepthPriorityGroup(weapon.FirstPersonMesh.DepthPriorityGroup)`, then
  `weapon.FirstPersonMesh.AttachComponentToSocket(comp, WeaponTypeDefinition.MuzzleFlashSocket)`.
  `SetTranslation` on it is relative to the socket (the socket sits in front of the barrel).
  `DeactivateSystem` + `DetachComponent` to remove.
- **Sounds:** `pawn.PlayAkEvent(AkEvent)`. Weapon equip clacks: `Ake_Obj_Pickup.Obj_Pickup_Equip.
  Ak_Play_Obj_Pickup_Equip_{Pistol,Rifle,RL,Shotgun,SMG}`. Loops come in Play/Stop pairs (e.g.
  `Ake_FX_Global.Ak_Play/Ak_Stop_FX_Elemental_*_StatusEffect_lp`); a loop without a Stop event (the Vladof
  minigun `Ak_Play_Wep_Rifle_Vladof_Spin_Loop`) ends with its spin-down plus
  `WillowWeapon.StopLoopingSounds()`. `WillowWeapon.PlayStartSpinningUpSound()` plays a gun's spin-up.

**Shields, grenades and other equipped items.**
- `WillowPawn.EquippedItems` holds the equipped shield / grenade mod / class mod / relic (tell them apart by
  class). Items have `DefinitionData.UniqueId` like guns, and `StaticCalculateItemRarityLevel` for rarity.
- Shield: `GetShieldStrength` / `GetMaxShieldStrength` / `SetShieldStrength` (Gotcha 27 for breaks).

**Menus and startup.**
- `WillowGFxMoviePressStart.extContinue()` = pressing a key on the title screen;
  `FrontendGFxMovie.LaunchSaveGame(PlayThrough)` = the Continue button. The 2K/Gearbox logos are
  `StartupMovies` in the user's `Documents/My Games/Borderlands 2/WillowGame/Config/WillowEngine.ini`
  (comment them out; mods load after them, so a mod can't skip them).

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
- The 2026-10-04 additions were verified the same way (item cards, loot beam colours and sound, tracers,
  shield tint, camera effects). The mantle was judged unsatisfying by the human and turned off.
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
13. **Crash on quit-to-menu** (access violation in pyunrealsdk) after holding `UObject`s across a map
    change. **Fix:** hold anything cached as `unrealsdk.unreal.WeakPointer` and re-resolve it.
14. **A hit counted twice:** two features each blocked `TakeDamage` and re-issued it with their own
    multiplier. **Fix:** exactly one block-and-re-call damage hook that multiplies every bonus together.
15. **Timers and regen kept running while paused.** **Fix:** a game clock that only advances while
    `WorldInfo.Pauser` is None.
16. **A damage ramp grew to absurd numbers.** It wrote the gun's damage attribute each frame and treated
    "current differs from what I wrote by more than 0.01" as "BL2 recomputed it, take a new base". float32
    rounding of large damage numbers exceeds 0.01, so the ramped value became the base every frame.
    **Fix:** compare with a relative tolerance (1e-4), and restore saved bases unconditionally.
17. **Loot beams invisible:** a flat mesh with a one-sided material, facing away. **Fix:** two
    back-to-back faces.
18. **Legendary beams came out purple:** rarity 9 fell into an "epic" bucket built from a guess. **Fix:**
    use `GlobalsDefinition.RarityLevelColors` (Rarity bullet above). The same table showed that e-tech (6)
    had been treated as legendary for anointments.
19. **Drop sound never played:** it hung on `WillowPickup.Landed`, which rigid-body pickups never call.
    **Fix:** `PickupAtRest`.
20. **A "round glow" texture rendered as a square:** BL2's bullet-trail material reads one channel of each
    texture through a static component mask and has no texture-shaped opacity (and GreyPack textures
    keep a different shape per channel). **Fix:** a particle (`Part_LootableLocator` with `RColor`) instead
    of a textured quad.
21. **No mantle that feels like BL3's.** Nothing can see a ledge ahead: `Trace` never hits, `FastTrace`
    always says blocked (Gotcha 2), and `Actor.SetLocation` refused even the pawn's own spot, so it can't
    probe for free space. `NotifyFallingHitWall` only fires when (HitNormal . Velocity.SafeNormal) <
    MinHitWall, so head-on jumps (mostly vertical velocity) rarely register even with MinHitWall 0.1.
    Reacting to "pushing forward but not moving" detects walls, but without the ledge height every
    version felt like a jump boost. **Fix:** none found; it ships off by default.
22. **A save loaded in the middle of a game (crash):** a "continue my save" helper reacted to
    `FrontendGFxMovie.NotifyAtMainMenu`, which also fires when the Mods menu is opened from the pause menu.
    **Fix:** only act when `WorldInfo.GetMapName(False)` is `menumap` and there is no pawn.
23. **Explosion damage lands after `Detonate()` returns,** so a "scale hits during this call" window
    misses them. **Fix:** key the bonus to the victim, with a short time window.
24. **"Semi-auto" still fired full-auto while the button was held.** BL2 starts the next shot itself; pre-hooks
    that refuse `WillowWeapon.ShouldRefire` or `BeginFire` didn't stop it (the native path doesn't go through
    them). **Fix:** in a `WillowWeapon.ConsumeAmmo` post-hook (once per shot), call
    `Weapon.ClearPendingFire(0)`: the gun stops as if the trigger were released and the next press fires again.
25. **A chosen fire mode reverted while aiming.** The zoom attribute effects override the value until your
    next per-frame write and shots fire in between. **Fix:** re-apply in post-hooks on
    `ApplyAllZoomWeaponAttributeEffects` / `RemoveAllZoomWeaponAttributeEffects` and on every shot.
26. **A borrowed homing throw (the Deliverance's) hit for 0 on other guns,** and a borrowed split throw (Baby
    Maker) made one extra blast: their damage and children come from their own unique gun. **Fix:** catch your
    throw in `WillowProjectile.InitializeFromDefinition` (post) and deal the damage yourself in an
    `Explode` pre-hook (targets collected first). Projectiles that `Behavior_Fire` spawns are initialised
    inside that call, so set a flag around it to recognise them.
27. **`WillowPawn.OnShieldDepleted` never fired for the player from Python.** **Fix:** poll
    `GetShieldStrength()` and treat a drop to 0 as the break.
28. **A Tediore reload (the throw) never went through `WillowWeapon.BeginReload`,** so "rounds left at the
    throw" was unknown. **Fix:** sample the held gun's `ReloadCnt` every frame and take the lowest value of
    the last ~0.6 s at the throw.
29. **Muzzle particles and repeating muzzle flashes:** a re-activated muzzle-flash particle on a socket
    showed nothing, and launcher muzzle blasts read as a stray explosion; looping particles (shock sparks)
    worked. Sound sold the underbarrel changes better than particles.

## Assets
None. All visuals come from the game's own parts, projectiles, explosions and arm poses.

## Cost and time
About five long sessions, roughly 150 human test rounds. Most time went into the Tediore turret (10 builds,
Gotchas 2 and 8) and the two slam freezes (Gotchas 3 and 4).

## Open questions
- Why do traces (and `SetLocation` as a probe) fail from the SDK? A working collision query would unlock
  a real mantle and mod-side line of sight.
- Porting Pre-Sequel assets: see `techniques/loading-pre-sequel-assets-in-borderlands-2.md`.
- Per-legendary rules (keep the unique effect, add the manufacturer effect, or both).
- Co-op: everything is host/single-player only. The `networking` library in the mod manager would be the
  starting point.
