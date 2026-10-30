---
kind: game
title: Mass Effect biotics, kinetic barriers and rifles as a WotR class (UMM, blueprints in code)
game: 'Pathfinder: Wrath of the Righteous'
games_also:
- Mass Effect
game_version: Enhanced Edition, Version.info "2025-Apr-02 eb82d8f2 2.7.0x" (steam 1184370)
platform: windows
engine: unity-mono
route: loader-api
tools:
- Unity Mod Manager 0.32.4
- HarmonyX (0Harmony shipped with UMM)
- Krafs.Publicizer 2.2.1
- ilspycmd 8.2.0.7535
- .NET SDK 8 (target net48)
anti_cheat: none found by um scan
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-18'
links:
- https://github.com/newman55/unity-mod-manager
- https://github.com/krafs/Publicizer
tags:
- mashup
- new-class
- blueprints
- mass-effect
- unity-mod-manager
- save-compat
---
# Mass Effect biotics, kinetic barriers and rifles as a WotR class (UMM, blueprints in code)

> A cross-game mashup: a new base class, "N7 Biotic", plus an "Alliance Marine (Displaced)" background that
> drop a Mass Effect character into WotR's unchanged story. It runs on Mass Effect's systems on top of Pathfinder's:
> - biotic powers as spell-like abilities sharing one recharge timer;
> - primer/detonator combos;
> - a kinetic-barrier temp-HP shield;
> - ammo-power toggles;
> - crossbow-rules rifles with a rifle mesh built in code.
>
> It's a Unity Mod Manager C# mod that creates every blueprint in code. Verified in the real game: character
> creation, the starting kit, the barrier, and Warp → recharge → rifle → Throw → "BIOTIC EXPLOSION" against
> spawned dretches, confirmed by screenshots, the mod log and the game's `combatLog.txt`.

## Setup
- WotR Enhanced Edition, Steam, Windows 11, Unity 2020.3.48f1, Mono. `um scan` says "BepInEx" because of the
  doorstop `winhttp.dll`, but the doorstop's `target_assembly` is UMM's `UnityModManager.dll`. It's a UMM install.
- UMM 0.32.4 was already installed with ToyBox 1.7.19 and BubbleBuffs 5.2.3. Mods go in `<game>/Mods/<Id>/`
  with an `Info.json` (`EntryMethod`, `AssemblyName`).
- Build: `dotnet build` of a net48 SDK project.
  - It references `Wrath_Data/Managed/*.dll` and `UnityModManager/{UnityModManager,0Harmony}.dll`.
  - **net472 fails**: UMM's 0Harmony is built against 4.8.
  - Publicize `Assembly-CSharp` and `Owlcat.Runtime.Core` with Krafs.Publicizer 2.x item syntax
    (`<Publicize Include="Assembly-CSharp" />`). The `Publicize="true"` attribute on `<Reference>` is ignored.
- `ilspycmd` 11.x won't install on the .NET 8 SDK (missing DotnetToolSettings.xml). That error means the tool
  targets a newer .NET: 10.x and 11.x ship only for net10.0. 9.1.0.7988 targets net8.0, so it's the newest that
  fits SDK 8; 8.2.0.7535 (net6.0) is the one used here.

## Route and why
- A UMM loader-API mod: create blueprints in a `BlueprintsCache.Init` postfix, add a few Harmony patches, and
  write custom `ContextAction`/component classes for the mechanics.
- Data-only isn't possible (WotR has no JSON override loader in this setup).
- Owlcat's own modification template needs the Unity editor, and this machine had no Unity, Blender or fal key.
- BlueprintCore (the community library) would also work. Plain code with a 150-line helper was enough.

## How the game works (what we had to learn)
- **`blueprints.zip` in the game folder holds every blueprint as JSON** (`.jbp`, 252k files): GUIDs, component
  types, FX AssetIds and projectile links. Grep it instead of decompiling to find what to reuse.
- New class: `BlueprintCharacterClass` appended to `BlueprintRoot.Instance.Progression.m_CharacterClasses`.
  - Character creation sorts base classes alphabetically (N7 Biotic landed between Monk and Oracle).
  - Saves: stock `BlueprintStatProgression`s (medium BAB `4c936de4…`, good save `ff4662bd…`, poor `dc0c7c1a…`).
  - DCs for class abilities: the `ContextCalculateAbilityParamsBasedOnClass` component.
- Background: add a `BlueprintFeature` to both `m_AllFeatures` and `m_Features` of `BackgroundsBaseSelection`
  (`f926dabe…`). It shows at the top of the list.
- **No crossbow reload exists in WotR**; crossbows attack like bows. Weapon category is a fixed enum, so a "rifle"
  is a clone of the LightCrossbow / HeavyCrossbow `BlueprintWeaponType`. Clone `m_VisualParameters` too (shallow
  clones share it), then point `m_Projectiles` at a custom projectile.
- Force damage = `DamageEnergyType.Magic`.
- Stock building blocks:
  - `ContextActionPush` (from a DLC);
  - `ContextActionKnockdownTarget`;
  - `AbilityCustomTeleportation` (Dimension Door FX; the projectile becomes the caster's flight streak);
  - `AbilityCasterHasNoFacts` (a shared cooldown is just "caster lacks the Recharging buff");
  - `ITickEachRound` on *feature* components (UnitTicksController calls it for non-buff facts);
  - `IUnitCombatHandler.HandleUnitJoinCombat`;
  - `Stats.TemporaryHitPoints.AddModifier`.
- Weapon models: `UnitViewHandSlotData.RecreateModel` instantiates `WeaponVisualParameters.Model`. A postfix there
  can rebuild `VisualModel`. Weapon shader is `Owlcat/Lit` (`_BaseMap`, `_BaseColor`, `_BumpMap`, `_MasksMap`,
  `_Roughness`, `_Metallic`, `_EmissionColor`, `_EmissionColorScale`).
- Localisation: a prefix on `LocalizationPack.GetText` serving our own keys survives locale changes.

## Build steps
1. Make the csproj as above. Add an `Info.json` with `EntryMethod: N7.Main.Load`.
2. Write `Load`: `new Harmony(id).PatchAll()`, plus a postfix on `BlueprintsCache.Init` that builds the content
   once.
3. Create blueprints:
   - `new T { name, AssetGuid = MD5(name) }`, then `BlueprintsCache.AddCachedBlueprint`;
   - give components **deterministic names** (see gotcha 2);
   - give buffs `FxOnStart`/`FxOnRemove = new PrefabLink()` (gotcha 1).
4. Add icons as PNGs next to the DLL: `Texture2D.LoadImage` + `Sprite.Create`.
5. Copy `bin/Release/{dll,Info.json,Assets}` to `Mods/<Id>/`.
6. For testing, an `entry.OnUpdate` hotkey that calls `Game.Instance.EntityCreator.SpawnUnit(CR2_DretchStandard
   2d643696…, pos, rot, Game.Instance.State.LoadedAreaState.MainState)` gives a combo target on demand.

## Verification
- Drove the real game with `um win`. Display scale was 125%, so client coordinates = 1/3-scale screenshot × 1.6.
  WotR ignores virtual-key events in game (`scanmode on` fixes it), but UMM's IMGUI hotkeys need VK mode.
- Character creation: class, icons, progression chart, background and skill modifiers all checked on screenshots.
- New game through the Kenabres prologue (the human played to the caves and saved). Then load that save, spawn
  dretches, Warp one, shoot during the recharge, Throw it.
  - Mod log: `[power] … N7_PowerWarp; amp recharging 2 rounds`, then `[combo] BIOTIC EXPLOSION on Dretch: 2d6
    force, DC 15`.
  - `combatLog.txt`: Reflex saves for every unit in the blast, a Fortitude save for Throw's knockback, and the
    "Warped" DoT.
- The barrier shows on the portrait as `8+10/10` and refills on joining combat.
- **Not verified:** Pull, Charge, Singularity, Nova, Cryo/Disruptor ammo, the sniper rifle, level-ups past 1,
  the 2-round barrier regen, and the armour recharge penalty.

## Gotchas
1. **NullReferenceException in `Buff.OnRemove` when a creature carrying our buff dies.** **Cause:**
   `Buff.OnRemove` calls `Blueprint.FxOnRemove.Load()` unconditionally, and a code-made buff has a null
   `PrefabLink`. **Fix:** default `FxOnStart`/`FxOnRemove` to `new PrefabLink()` (and `ResourceAssetIds` to an
   empty array) on every buff.
2. **After loading a save, class features silently do nothing.** No barrier, no recharge, and the log shows
   `EntityFact.PostLoad: can't find source component $N7KineticBarrier$<guid>`. **Cause:** saved component data
   is matched to blueprint components *by name*, and the names were `Guid.NewGuid()` each launch.
   `EntityFact.PostLoadComponents` disposes unmatched components and never recreates them. **Fix:** name
   components deterministically (`$Mod$<Type>$<bp>#<i>`). To repair saves made by an earlier build, add a
   postfix on `EntityFact.PostLoadComponents` that calls the (publicized) private `EntityFact.Setup(Blueprint)`
   for your facts; it recreates any missing components.
3. **The crossbow still shows next to the custom rifle mesh.** **Cause:** `UnitViewHandSlotData.AttachModel`
   re-collects and re-enables every renderer under the model, so `renderer.enabled = false` is undone.
   **Fix:** `Object.DestroyImmediate` the original renderers on the instance, after reading the material you
   want to clone (otherwise `sharedMaterial` throws).
4. **The combo detonator can never reach the primer.** **Cause:** the primer lasted 2 rounds, which equals the
   shared 2-round recharge. **Fix:** make primers outlast the recharge (3 rounds).
5. **Class preview and paper doll are naked in character creation.** **Cause:** a code-made class has empty
   `Male/FemaleEquipmentEntities`. **Fix:** copy them, and the colours, from an existing class (Fighter
   `48ac8db9…`).
6. **Clicking an enemy after choosing an ability sometimes just attacks.** **Cause:** the click landed off the
   unit's hitbox and fell through to a normal attack order. Casting also needs ~2–3 s of unpaused time, and the
   order is dropped if the target dies first (prologue companions kill centipedes very fast). **Fix:** hover
   and confirm the red highlight before clicking, and use tougher spawned targets for tests.
7. **`um publish check` fails on the mod's own icons and DLL.** **Cause:** with `--game`, it compares against the
   game folder, and that includes the copy you installed in `Mods/`. **Fix:** ignore matches under
   `Mods/<your mod>` (a toolkit fix would be to skip them).

## Assets
- Icons: `tools/make_icons.py` (Pillow) draws 17 Mass-Effect-style icons: dark gradient plates, Gaussian-blur
  glow, biotic blue/violet, N7 orange.
- Rifle: boxes on the cube primitive's mesh, placed in the crossbow model's local frame. The longest bounds axis
  is the muzzle and the shortest is up. Materials are clones of the crossbow's `Owlcat/Lit` material with solid
  textures.
- Slug projectile: the crossbow-bolt projectile with the kineticist metal-shard view (`9b4bee9b…`) at Speed 45.
- Reused FX:
  - Force-bomb hit (`7317ab56…`) for the biotic explosion;
  - Faerie Fire glow (`3cf209e5…`) for Primed;
  - Hold Person (`eb0e36f1…`) for Warped/Lifted;
  - Aeon black hole area (`4fbea239…`) for Singularity;
  - Dimension Door FX for Biotic Charge.

## Cost and time
One session, about 5 hours of wall clock, including roughly 8 game restarts. No API spend (no fal key).

## Open questions
- Play-test the level 2–8 powers. Singularity's pull of 10 ft/round toward the centre may need tuning.
- The rifle materials could use a proper ME palette (darker grey, roughness via `_Roughness`). A real GLB model
  needs a runtime loader or the Unity 2020.3.48 editor for an AssetBundle.
- Companion barks and dialogue that acknowledge the isekai, via dialogue blueprints, without touching quest
  flags.
