---
kind: game
title: "Helldiver survivor: custom skills, stratagems, Helldivers 2 models on the Commando rig, config, lab bridge and benchmark"
game: "Risk of Rain 2"
games_also: ["Helldivers 2"]
game_version: "1.5.0#1224 (Hallowed Concepts update, Steam build 25921972; Unity 2021.3.33f1, Mono), Steam, Windows 11; first built on 1.4.1#912; separate lab copy of the install"
platform: windows
engine: unity-mono
route: loader-api
tools: ["BepInExPack 5.4.2122", "RoR2BepInExPack 1.46.0 (1.43.0 on 1.4.1)", "R2API ContentManagement 1.1.0 (1.0.11 on 1.4.1) / Language 1.1.0 / Prefab 1.1.1", "HookGenPatcher 1.2.9 (lab only)", ".NET SDK 8 (netstandard2.1)", "ilspycmd 8.2", "filediver 0.7.55", "Blender 4.0 (headless)", "uv + numpy/pillow"]
anti_cheat: "none (co-op PvE, no anti-cheat); all testing in a separate lab copy of the game"
status: released
agents: ["Claude Code (Claude Opus 4.x, Sonnet and Opus 5.5 across sessions)"]
humans: ["Terr4"]
date: 2026-10-18
links: ["https://github.com/TheTerr4/RoR2-Helldiver", "https://thunderstore.io/c/riskofrain2/p/Terr4/Helldiver/"]
tags: [survivor, skills, entity-states, stratagems, skinned-mesh, model-swap, ik, cloth, normal-maps, decimation, texture-compression, config, benchmark, test-bridge, game-update]
---

# Helldiver survivor: custom skills, stratagems, Helldivers 2 models on the Commando rig

> A new survivor (clone of the Commando body) with two automatic weapons, two grenades, a dive and a jump pack, and five
> Helldivers 2 stratagems called in by typing arrow codes and throwing a sticky beacon. An optional Model folder replaces the Commando
> with a Helldiver converted from the player's own HD2 install (body skinned to Commando's bones, two weapons held with two-hand IK,
> a Verlet cape, a jump pack with flames). 1.0.0 adds a full BepInEx config and optimized models. Verified in the real game through
> an in-process test bridge: scripted feature runs, screenshots and an A/B benchmark. Released on Thunderstore; players tested it in co-op.
> 1.0.4 survived the game's 1.5.0 "Hallowed Concepts" update, which stopped 1.0.3 from loading at all (see "Game update 1.5.0").

## Setup
- Lab: a copy of the Steam install with BepInEx; the real install stays vanilla. RoR2BepInExPack must live in
  `plugins/RiskofThunder-RoR2BepInExPack/` (a folder named `plugins/RoR2BepInExPack` is deleted by the preloader).
- R2API 5.x split modules at their latest versions. The versions pinned by the R2API 5.0.5 meta-package are stale and fail on Newtonsoft/MMHOOK.
- Game code is in `RoR2.dll`, not Assembly-CSharp. HookGenPatcher needs `MMHOOKAssemblyNames = RoR2.dll`.
- Build: netstandard2.1, references straight from the lab `Managed/` and plugin folders. A `Lab` configuration adds the test bridge (`#if LAB`)
  and the MMHOOK/MonoMod references; the release DLL has neither.

## Route and why
BepInEx plugin + R2API (ContentAddition, PrefabAPI, LanguageAPI). This is the standard RoR2 route, and RoR2 has no anti-cheat.
- **Body:** a `PrefabAPI.InstantiateClone` of CommandoBody keeps animations, hurtboxes and networking for free.
- **Skill families:** the clone's GenericSkill slots get new SkillFamilies, set through the private `_skillFamily` field.
- **States:** every skill is its own EntityState type, registered with `ContentAddition.AddEntityState`.
- **Models:** HD2 art is converted offline and loaded at runtime from loose files. It is never compiled into the DLL, so a share-safe package is just the DLL.

## How the game works (what we had to learn)
- **Entity states are rebuilt by type on remote clients.** A state can't carry constructor arguments, so every stratagem needs its own state
  types. Keep them as one-line subclasses over a data table (`StratagemDef` indexed by an enum).
- **EntityStateConfiguration.** Static fields apply to the exact type. Instance fields go through `EntityStateCatalog.InitializeStateFields`,
  keyed by `GetType()`. A subclass of a vanilla state therefore does not get the vanilla tuning; copy it from a plain `new VanillaState()` instance.
  Vanilla states also share static effect fields (DodgeState's `jetEffect`): null them around `base.OnEnter()` instead of hooking.
- **Skill selection order.** Player profiles store the selected variant per slot by index, so only ever append variants.
  In the character select the display model has no body or skills: read the choice from
  `userProfile.loadout.bodyLoadoutManager.GetSkillVariant(bodyIndex, slot)`.
- **Model swap.** The skin system (ModelSkinController) re-applies Commando's mesh and materials whenever the loadout or skin changes, which happens
  constantly on the character select. Check the body SkinnedMeshRenderer every LateUpdate and re-apply.
  - **Bones:** a mesh fitted to the Commando rest pose can reuse Commando's bindposes, with bones resolved by name.
  - **Add-ons:** for extra renderers (weapons, backpack, cape) to fade with the camera, cloak with stealth items and show hit flashes and elite
    overlays, they must be in `CharacterModel.baseRendererInfos`. The skin system replaces that array, so re-append them after every skin apply.
- **Update order.** `ModelLocator.LateUpdate` moves the model to the body. Anything reading bones in LateUpdate (cloth, IK) needs a late
  `[DefaultExecutionOrder]`, or it lags one frame (about 35 cm while sprinting at 20 FPS).
- **Hopoo deferred standard shader.** Properties: `_MainTex`, `_NormalTex` + `_NormalStrength`, `_EnableCutout` + keyword `CUTOUT` (no `_Cutoff`),
  `_Cull`, `_EmPower`, `_Smoothness`, and `_Fade` / `_FlashColor` driven by CharacterModel. The normal map is unpacked RG-or-AG, so DXT5nm works.
- **AimThrowableBase** fires its projectile in `OnExit`, and `PickNextState()` chooses the follow-up. Since 1.5.0 the aiming half
  (`KeyIsDown`, `UpdateTrajectoryInfo`, the nested `TrajectoryInfo`) lives in a new parent class, `AimThrowableBaseAimOnly`. Return a tiny "wait for the fire button to be
  released" state, or the held click immediately fires the primary on the same Weapon state machine.
- **Automatic weapons.** A one-shot state with interrupt priority Any re-triggers every physics frame (an endless stream). Use one long-lived state
  that fires at an exact rpm while the key is held.

## Build steps
1. Code: Content/ (survivor, tokens, assets, passive), States/, Stratagems/, Visuals/, Settings.cs (all BepInEx config entries), Dev/ (lab only).
2. Models: filediver (read-only on the HD2 install) writes GLB units. Python scripts then:
   - fit the avatar onto Commando's rest skeleton (one rigid + axial-scale transform per Commando bone, linear blend skinning);
   - bake weapon and backpack rest poses;
   - resample the cape into a 9 x 13 grid.

   Then `optimize.py` runs inside Blender (`blender -b -P`):
   - weld the triangle soup;
   - collapse-decimate (vertex groups carry the skin weights);
   - Smart UV Project + pack;
   - Cycles bake, selected-to-active: emission for colour, tangent-space normal map;
   - write the mesh with Blender's MikkTSpace tangents, so the game decodes the normal map exactly as baked.
3. Runtime textures: PNG, then block-compressed at startup:
   - colour maps: copy into an RGB24 texture, then DXT1 (PNG `LoadImage` always gives ARGB32, which compresses to DXT5);
   - normal maps: swizzle to DXT5nm, then compress without dithering;
   - release the CPU copy with `Apply(false, true)`;
   - preload everything in `Awake`, inside the loading screen.
4. Package: manifest + README + CHANGELOG + icon, built by one script from the version in `Plugin.cs`. Thunderstore wants those files at
   the root of the zip (no wrapping folder) and forward-slash paths; Windows PowerShell 5.1's `Compress-Archive` writes backslashes, so use
   Python's `zipfile` or Windows' `tar.exe -a`. A second zip wraps the same files in a folder for manual installs.

## Verification
- **Oracle: an in-process test bridge.**
  - **Input:** a MonoBehaviour polls `BepInEx/hd_cmd.txt`. Input is injected after `PlayerCharacterMasterController.FixedUpdate` (MMHOOK), so
    held skills, move/look, arrow keys and loadout changes need no OS input.
  - **Output:** screenshots via `ScreenCapture`, `status` lines in the log, and timed `seq` scripts.
  - **Quiet runs:** director enemies are removed unless asked for.
  - **Fixed location:** `stage <scene>` calls `Run.instance.AdvanceStage`, and `tpabs` teleports to a set point. Together they give repeatable
    scenes; cheats are server-only, so console `set_scene` is unavailable.
- **Scripted checks:**
  - **Full feature run:** both guns empty their magazine and reload; grenades and stratagems spend charges with the configured cooldowns; the
    jump pack nozzles exist and point down; the log has no errors.
  - **Config:** edit the .cfg, launch, and confirm health, charges, magazine, rpm, reload and cooldown changed.
  - **Share-safe build:** no Model folder, no errors.
- **Benchmark:** MonoMod detours time the mod's Update/LateUpdate/OnGUI methods and its loading. Four uncapped 8 s scenes: idle, firing,
  sprinting in circles, and 12 extra display-model copies in front of the camera. It reports FPS, 1% lows, mod ms/frame, GC and texture bytes
  computed from the formats; the profiler reports 0 for non-readable textures. Hooks are resolved by type name, so the same tool builds against
  old source for an A/B.
  - **Result** (7800X3D + 4080 Super, 1440p): idle 398 → 542 FPS, 13 Helldivers 318 → 420. Mod CPU 0.385 → 0.097 ms/frame. Our meshes
    209k → 30k vertices; GPU textures 48 → 13 MB.
- **Multiplayer:** never run with a second client in the lab; the user's friends played it in co-op, and their reports became the 1.0.2 fixes.

## Game update 1.5.0 (Hallowed Concepts, 1.0.4)
Players reported that the mod did nothing after the update. The log shows
`TypeLoadException: VTable setup of type HelldiverMod.States.ArmedBase failed`, so the whole plugin fails to load.
- **New lab, old one kept.** Rename `lab` to `lab-1.4.1`, copy the updated Steam install to a new `lab`, and carry over `BepInEx/`,
  `doorstop_config.ini` and `winhttp.dll`. Then update every package Thunderstore shows as updated after the patch date (here:
  RoR2BepInExPack 1.46.0, R2API ContentManagement 1.1.0, Director, Dot, Elites, Skins and its patcher). HookGenPatcher regenerates MMHOOK on
  the first launch. Confirm the version with `Risk of Rain 2 build: ver.` in the log and `buildid` in `appmanifest_632360.acf`.
- **Reproduce first.** The shipped 1.0.3 DLL in the new lab gave the players' exact error, plus a second one their log did not show.
- **Rebuild against the new DLLs, then run the full scripted test.** The release build compiled with no errors; the only compile error was in
  the lab bridge. Both real breaks were found by loading the game, not by the compiler.
- **Diff the vanilla classes you subclass or configure.** Decompile only the changed types into a new folder outside the repo and diff their
  member lists against the old decompile. Here: `ProjectileImpactExplosion.explodeOnLifeTimeExpiration` was removed (lifetime still
  detonates), `ProjectileSimple.spawnEffect` was removed, `ProjectileController.ghostPrefabReference` was renamed `ghostPrefabAddress`, and
  `ProjectileStickOnImpact` gained `attachToCharacter`, `ignoreImpact` and `ignoreDeadCharacters`.
- **Ship it as a new version** whose changelog says it needs the updated game, and bump the manifest's dependency pins to the post-patch
  packages. ContentManagement 1.1.0 now warns "has no ghost prefab assigned" for cloned projectiles; that is harmless.

## Gotchas
1. **Commando flashes for one frame on the character select.** Cause: the skin system re-applies Commando's mesh on every loadout/skin change. Fix: check the SMR's sharedMesh and material every LateUpdate and re-apply; a 0.5 s poll is too slow.
2. **The cape lags behind the body.** Cause: it read bones before `ModelLocator.LateUpdate` moved the model. Fix: `[DefaultExecutionOrder(32000)]` on the cloth component.
3. **The cape cost 20 FPS.** Cause: every one of ~1,300 vertices was simulated, and a low frame rate meant more sub-steps (a spiral). Fix: a 5 x 7 particle grid rendered as an interpolated 9 x 13 mesh, at most 3 sub-steps, and the body's movement partly passed straight to the particles. Fix 2: write the hot loops in floats; Mono runs Vector3 operators as real calls, and this was another 4x.
4. **Stealth items cloak the body but not the gun or backpack** (they also don't fade near the camera or take overlays). Cause: CharacterModel only manages `baseRendererInfos`. Fix: append your renderers there, and again after each skin apply.
5. **The fitted body's hands had the wrong chirality and needed 110-160° of wrist twist.** Cause: the z mirror of the coordinate conversion. Fix: reflect the glove vertices across the hand bone's local plane offline. A weighted blend twists the wrist triangles, so use a hard cut. Lesson: plot the mesh in bone space before guessing axes.
6. **A subclassed vanilla state does not get vanilla tuning** (duration, speeds). Cause: state configuration is keyed by exact type. Fix: copy the values from a plain instance of the vanilla type once.
7. **Throwing the beacon also fires the gun.** Cause: after AimThrowableBase exits, the held fire button triggers the primary on the same state machine. Fix: `PickNextState` returns a short state that ends when the button is released.
8. **The aim arc goes NaN when aiming straight down or at something in your face** (log spam). Cause: AimThrowableBase trajectory maths divides by zero. Fix: override `UpdateTrajectoryInfo` and fall back to a plain forward throw.
9. **Decimation was hampered by the converted meshes.** Cause: they were triangle soups with a per-triangle colour cell, so every edge is a UV seam (41k triangles meant 123k vertices). Fix: weld by position, drop UVs, decimate, re-unwrap, and bake the colour back from the soup.
10. **HD2 normal maps look wrong if used as RGB.** Cause: R/G hold X/Y with +Y up in the image, B is not Z, and A is a height map. Check by correlating R/G with the derivatives of A. Fix: rebuild Z from X/Y before baking. The bake then puts HD2's panel lines and screws on the low-poly model.
11. **Colour maps came out DXT5 instead of DXT1.** Cause: `Texture2D.LoadImage` gives ARGB32 for every PNG. Fix: copy into an RGB24 texture before `Compress`.
12. **Benchmark FPS differed by up to 30% between runs of the same build.** Cause: `tptele` stands next to the teleporter, which spawns somewhere different each run. Fix: a fixed stage and an absolute teleport.
13. **Lab bridge commands got lost.** Cause: command files written less than ~1.5 s apart race the 0.25 s poll. Fix: one file with a `seq "a; wait 0.5; b"` command.
14. **Config sections came out in the wrong order** ("10." before "2."). Cause: BepInEx writes sections sorted as strings. Fix: zero-pad the numbers ("01.").
15. **Old config entries linger after an update.** Cause: BepInEx keeps unknown entries as orphans. Fix: read the protected `OrphanedEntries` by reflection, migrate the values, remove the keys and Save.
16. **After the 1.5.0 update the plugin fails to load: `VTable setup of type ...ArmedBase failed`.** Cause: the game moved the nested struct `TrajectoryInfo` from `AimThrowableBase` into its new parent `AimThrowableBaseAimOnly` (and gave it two more fields). An override compiled as `UpdateTrajectoryInfo(out AimThrowableBase.TrajectoryInfo)` names a type that no longer exists, so Mono cannot lay out the class, and `GetTypes()` fails for the whole assembly. Fix: recompile against the new `RoR2.dll`; the source did not change, because C# resolves the inherited nested type by name.
17. **After the same update, `NullReferenceException` in `Plugin.Awake` while building the stratagem beacon.** Cause: the vanilla prefab it was cloned from, `RoR2/Junk/Commando/CommandoStickyGrenadeProjectile.prefab`, no longer has a `ProjectileStickOnImpact`. Fix: add one when it is missing. A component added at runtime starts with `null` where the inspector gives `""` and `[]`, and `TrySticking` reads `stickSoundString.Length`, so set `stickSoundString = ""` and `stickParticleSystem = Array.Empty<ParticleSystem>()`. Leave the new `attachToCharacter` false to keep the old follow-the-hurtbox behaviour. Lesson: never assume a vanilla prefab, least of all one under `Junk/`, keeps its components across updates; check for null and log what it holds.

## Assets
- Icons are procedural, embedded in the DLL.
- **Models:** converted from the player's own Helldivers 2 install. They are kept out of the source repo (`.gitignore`); the release zips
  carry them in a Model folder next to the DLL, and without that folder the survivor falls back to a recoloured Commando.
- **Colour:** HD2 stores no albedo for this gear (layered material IDs), so colours are baked per region by script.
- **Normal maps:** the weapons and pack carry HD2's normal-map detail into the bake.
- **Budgets:** body 12,000 tris (2048 colour, 1024 normal); weapons ~3,500 each; pack 1,800 (1024 maps).

## Cost and time
Several sessions over about four days. The 1.0 cleanup, optimization, config and benchmark took one long session.

## Open questions
- Multiplayer has only been tested by players, never in the lab: a second lab client would catch lobby and sync bugs before release.
- An in-game options menu (Risk of Options) instead of editing the .cfg.
- Under the cloak shader the cape ignores its alpha cutout, so it shows as a plain sheet.
