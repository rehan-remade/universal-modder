---
kind: game
title: "Custom Characters and Weapons with BepInEx IL2CPP in Megabonk"
game: "Megabonk"
game_version: "1.0.69, Steam"
platform: windows
engine: unity-il2cpp
route: loader-api
tools: ["BepInExPack_IL2CPP 6.0.755", "ilspycmd", "dotnet 10"]
anti_cheat: "none, but runs post to online leaderboards: turn Upload score to Leaderboards off for every modded run"
status: working
agents: ["Gemini CLI (gemini-3.8-flash)"]
humans: ["SyronAscalon"]
date: 2026-10-12
links: ["https://github.com/BepInEx/BepInEx", "https://thunderstore.io/c/megabonk/p/BepInEx/BepInExPack_IL2CPP/"]
tags: ["characters", "weapons", "melee", "il2cpp", "bepinex6", "harmony", "vfx", "particles", "shaders", "balancing", "hats"]
---

# Custom Characters and Weapons with BepInEx IL2CPP in Megabonk

> Implemented a new custom character (The Farmer) based on Amog with procedural denim overalls, bespoke balanced starting attributes, passive ability, head-adjusted sheriff hat, and a unique melee weapon (Pitchfork) featuring a 3-pronged gold slash arc, 3D fork mesh, and controlled stacking execution and armor mechanics. Runs verified in Megabonk 1.0.69 with BepInEx 6 IL2CPP and HarmonyX.

## Setup
- **Game:** Megabonk build 1.0.69 (Steam AppID 3405340)
- **Engine:** Unity 2023.2.22f1 (IL2CPP, x64)
- **Mod Loader:** BepInExPack_IL2CPP 6.0.755 (Thunderstore)
- **SDK:** .NET 6.0 (`net6.0`) with C# `latest` and `AllowUnsafeBlocks: true`
- **OS:** Windows 10 / 11 x64
- **Leaderboards:** Megabonk posts finished runs to online leaderboards. A custom character with an execute weapon
  is a cheat there, so set **Upload score to Leaderboards** to Off in the game's settings before any modded run.
  This plugin doesn't touch that setting. Other Megabonk mods (Megamod, for one) lock it off while they're loaded,
  and a released version of this one should too.

## Route and why
We chose the **loader-api** route using BepInEx 6 IL2CPP with Harmony detours. Megabonk runs on Unity 2023.2 IL2CPP. BepInEx generates interop assemblies (`BepInEx/interop/Assembly-CSharp.dll`, `UnityEngine.*.dll`) containing typed invoke stubs. Data-only modding is impossible because characters and weapons are ScriptableObject instances loaded into internal dictionaries. Native DLL injection with MinHook is unnecessarily complex given that BepInEx IL2CPP provides full C# access to all engine types and Harmony method patching.

## How the game works (what we had to learn)
- **Central Registries:** `DataManager` holds `characterData` (Dictionary of `ECharacter, CharacterData`), `unsortedCharacterData` (List), `weapons` (Dictionary of `EWeapon, WeaponData`), and `unsortedWeapons` (List). Populating these during `DataManager.Load` integrates custom content into the game.
- **Character Selection Grid:** `CharacterMenu` dynamically creates button instances (`MyButtonCharacter`) from `characterPrefabUi` under `characterGridParent`. By instantiating `characterPrefabUi` in `CharacterMenu.TryInit` Postfix, custom characters appear natively in the selection grid.
- **Weapon System:** Every weapon evaluates stats through `WeaponBase.GetValue(EStat)`. The weapon's `baseStats` dictionary must include all standard keys (`Projectiles`, `ProjectileSpeedMultiplier`, `SizeMultiplier`, `DamageMultiplier`, etc.), otherwise the combat loop throws a `KeyNotFoundException`.
- **Damage Pipeline:** Player damage flows through `Enemy.DamageFromPlayerWeapon(DamageContainer dc)`. Non-boss enemies can be executed by checking `enemy.IsBoss()`, `IsStageBoss()`, and `IsFinalBoss()`, and setting `dc.damage = enemy.hp + 999999f`, `dc.crit = true`, `dc.isExecute = true`.
- **Combat Feedback:** Floating damage text can be spawned dynamically from `PoolManager.Instance.GetDamageNumber()`.
- **Localization:** `UnlockableBase.GetName()` and `GetDescription()` attempt to read from Unity string tables. Without custom table entries, it throws a NullReferenceException, which can be bypassed via Harmony prefixes.
- **Hat Attachment & `HatOrientation`:** Hats are managed via `PlayerRenderer.SetHat(HatData)`. Each `HatData` contains a `List<HatOrientation>` specifying local `pos`, `rot`, and `scale` indexed by `ECharacter`. For modded character IDs, this lookup returns null and places hats at root `(0, 0, 0)`, causing them to clip into character torsos or visors. Custom characters need explicit `hatTransform.localPosition` offsets (e.g. `y ≈ 0.62f` for Amog's rounded mesh).
- **Melee Slash VFX Architecture:** Melee weapon attacks in Megabonk (like Dexecutioner) do not use 3D blade meshes or `TrailRenderer` components. The attack is driven by `WeaponAttack.prefabProjectile`, where the visual slash arc is an Archanor Retro Arsenal `ParticleSystem` (`Atlas03Glow` material with `BasicGlow` shader). Modifying the slash visual requires manipulating `ParticleSystem.main.startColor`, recoloring `Renderer` materials via `_TintColor` / `_Color`, and parenting custom 3D mesh hierarchies directly to the projectile root.
- **Cel-Shaded Character Skins:** Character models like Amog utilize cel-shaders (`_MK_LIGHT_CEL`) that read textures from the `_AlbedoMap` shader property rather than standard Unity `_MainTex` or `mainTexture`. The keyword and property names are those of MK Toon, an Asset Store toon shader, whose tint is `_AlbedoColor`. Procedural skins must assign to `_AlbedoMap` directly.
- **Exponential Scaling in Horde Combat:** With cleaving melee weapons (`canMultiHit = true`), uncapped per-execution stat stacking (e.g. +0.25% impale chance, +0.35 armor per kill) creates runaway snowball curves when fighting dense enemy packs. Balancing requires hard caps (e.g. 20% max proc chance) and fractional increments (+0.05% per execution).

## Build steps
1. Install BepInExPack_IL2CPP 6.0.755 into the game folder and run once to generate interop assemblies. In the
   game's settings, set **Upload score to Leaderboards** to Off.
2. In `BepInEx/config/BepInEx.cfg`, set `EnableAssemblyCache = false` and delete `BepInEx/cache/chainloader_typeloader.dat`.
3. Create a C# project targeting `net6.0` referencing `BepInEx.Core.dll`, `BepInEx.Unity.IL2CPP.dll`, `0Harmony.dll`, and interop assemblies (`UnityEngine.PhysicsModule.dll`, `UnityEngine.ParticleSystemModule.dll`).
4. Implement registration in `DataManager.Load` Postfix, grid injection in `CharacterMenu.TryInit` Postfix, and weapon damage interception in `Enemy.DamageFromPlayerWeapon` Prefix.
5. Deploy compiled DLL to `BepInEx/plugins/<ModName>/`.

## Verification
- **Oracle:**
  - BepInEx console and file logs (`BepInEx/LogOutput.log`) confirming plugin initialization, asset loading, and data registration with 0 errors.
  - In-game screenshot capture via `um win shot`: The Farmer button was rendered in the Character Selection grid with custom straw hat icon, description, Pitchfork weapon card, and Bountiful Harvest passive.
  - In-game gameplay capture: Confirmed the Pitchfork weapon slot rendered (`LVL 1 Pitchfork`) under the player HP bar in an active combat run.
  - Character preview capture: Confirmed Sheriff hat sitting flush on Amog's head at `y = 0.62f` and custom overalls texture loaded.
  - Diagnostic tree logging: Confirmed `ParticleSystem` components and `Atlas03Glow` materials recolored from magenta to warm harvest gold.

## Gotchas
1. **The plugin DLL is in `plugins/` but never loads.** BepInEx caches what it found in each DLL in `BepInEx/cache/chainloader_typeloader.dat` (`EnableAssemblyCache`, on by default). Entries are keyed by path and a hash of the file's bytes (`TypeLoader.FindPluginTypes`), so a rebuilt DLL is scanned again, but a byte-identical DLL keeps whatever an earlier scan found, including no plugins. Fix: delete the cache file, or set `EnableAssemblyCache = false` while iterating.
2. **Texture loading in `BasePlugin.Load()` crashes with AccessViolation.** Calling `new Texture2D()` or `LoadImage` inside `BasePlugin.Load()` causes a fatal DirectX AccessViolation because the GPU device context is not yet active during BepInEx Chainloader startup. Fix: defer all texture loading to `DataManager.Load` Postfix.
3. **ImageConversion.LoadImage fails with ObjectCollectedException in IL2CPP.** Passing an implicit `Il2CppStructArray<byte>` to `ImageConversion.LoadImage` creates an unpinned managed wrapper collected by IL2CPP GC before native marshalling finishes. Fix: pre-convert images to raw RGBA32 byte files (`.raw`) and load them directly via `Texture2D.SetPixel(x, y, color)` and `Apply()`.
4. **Custom weapons crash on attack with KeyNotFoundException.** Megabonk expects all standard stats (`Projectiles`, `ProjectileSpeedMultiplier`, etc.) in `weaponData.baseStats`. Omitting them crashes on the first attack swing. Fix: clone all key-value pairs from `baseWeapon.baseStats` and add a Harmony prefix fallback on `WeaponBase.GetBaseValue`.
5. **Character selection card throws NullReferenceException on GetName.** Modded unlockables lack localization table entries, causing `UnlockableBase.GetName()` to dereference null. Fix: hook `UnlockableBase.GetName` and `GetDescription` with Harmony prefixes returning the modded name/description directly.
6. **HatOrientation lookup failure causes hats to sit in character faces or float.** `PlayerRenderer.SetHat()` searches `HatData.hatOrientations` for `character == this.character`. For modded character IDs, it defaults to `(0, 0, 0)`, landing in Amog's torso/visor. Manually hardcoding `y = 0.98f` makes it float in mid-air. Fix: measure and set `hatTransform.localPosition` to `Vector3(0f, 0.62f, -0.02f)` so the brim rests cleanly atop Amog's head curve.
7. **Melee slash visual modifications fail because attacks are ParticleSystems, not meshes.** Modifying `MeshRenderer` or `TrailRenderer` on an instantiated `attack` prefab has no effect on Dexecutioner because it contains 0 meshes and 0 trails. The slash arc is an Archanor Retro Arsenal `ParticleSystem` with material `Atlas03Glow`. Fix: access `wa.prefabProjectile`, set `ParticleSystem.main.startColor = harvestGold`, clone `Renderer` materials with updated `_TintColor` / `_Color`, and construct a 3D primitive hierarchy (`Cylinder` shaft + `Cube` crossbar + 3 tines) parented to the projectile.
8. **Toon/Cel shaders ignore Texture2D on mainTexture without `_AlbedoMap`.** Setting `Material.mainTexture` or `_MainTex` leaves Amog with default textures because `_MK_LIGHT_CEL` uses the `_AlbedoMap` shader property. Fix: explicitly call `material.SetTexture("_AlbedoMap", texture)` and `material.SetTexture("_MainTex", texture)`.
9. **Cleave multi-hit weapons cause runaway exponential scaling on execution mechanics.** Cleaving melee attacks (`canMultiHit = true`) trigger hit hooks for every mob in an arc. With large swarms, uncapped stacking per execution causes exponential feedback. Fix: introduce hard caps (`Mathf.Min(CurrentChance + Step, MaxChance)`) and scale increments in small fractions (e.g. `+0.05%` per execution up to `20.0%` cap, `+0.10` armor per stack).
10. **Cloned weapon prefabs retain native execution subroutines.** Weapons cloned from Dexecutioner inherit `ProjectileDexecutioner`, which can trigger its own built-in execute effect on low-health targets independently of custom mod mechanics. Fix: none found yet; see Open questions. Count it in balancing until it's decoupled.

## Assets
- `farmer_icon.png`: 256x256 pixel-art character portrait with straw hat, wheat stalk, and denim overalls.
- `pitchfork_icon.png`: 256x256 melee weapon icon showing a sharp 3-pronged iron pitchfork with gleaming tips.
- `harvest_icon.png`: 256x256 passive icon showing tied golden wheat stalks and glowing embers.
- Assets were pre-converted to 128x128 raw uncompressed RGBA byte files (`.raw`) for safe zero-alloc IL2CPP texture loading.

## Cost and time
- Session duration: ~2 hours.
- Automated verification: 8 in-game screenshots captured and analyzed.

## Open questions
- Decoupling native `ProjectileDexecutioner` execution checks from custom weapon damage scripts.
- Adding additional weapon upgrade branches to `WeaponData.upgradeData`.
