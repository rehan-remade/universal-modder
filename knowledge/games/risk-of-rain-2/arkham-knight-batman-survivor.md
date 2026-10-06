---
kind: game
title: "Arkham Knight Batman as a Risk of Rain 2 survivor: UE3 model and animations ported with umodel, Blender and a Unity AssetBundle"
game: "Risk of Rain 2"
games_also: ["Batman: Arkham Knight"]
game_version: "RoR2 1.4.1#912 (Unity 2021.3.33f1, Mono), Steam build 21587608; Batman: Arkham Knight Steam build 13250859 (UE3 863/32995); Windows 11"
platform: windows
engine: unity-mono
route: loader-api
tools: ["BepInExPack 5.4.2122 (Doorstop 4)", "RoR2BepInExPack 1.43.0", "R2API Core 5.3.0 + split modules (Prefab 1.1.1, Language 1.1.0, Sound 1.0.3, RecalculateStats 1.6.6, ContentManagement 1.0.11, Networking 1.0.4, DamageType 1.1.7, Orb 1.0.1)", "HenryTutorial @ 42797355 (AC update)", ".NET SDK 5.0.104 (dotnet build, netstandard2.1, C# 7.3)", "RiskOfRain2.GameLibs 1.4.1-r.0", "ilspycmd 11.1.0.9782", "UE Viewer (umodel) build 1590, 64-bit, 2023-07-07", "Blender 5.2.2 LTS portable + io_scene_psk_psa 9.1.3", "Unity 2021.3.33f1 (Personal, batchmode)", "Thunderstore Mod Manager 1.25 (Overwolf)"]
anti_cheat: "none (RoR2 co-op PvE has no anti-cheat; Arkham Knight was only read offline, never launched or modified)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-05
links: ["games/risk-of-rain-2/helldiver-survivor.md"]
tags: [survivor, port, ue3, umodel, psk, psa, blender, unity-assetbundle, animation-retarget, cape, root-motion, henry-template, loader-hooks, melee]
---

# Arkham Knight Batman as a Risk of Rain 2 survivor

> A new RoR2 survivor built on the HenryTutorial template (BepInEx + R2API) with a 15-skill Arkham-style kit (Freeflow
> combo meter, 4-hit lunge chain, Counter, Cape Stun, Fear Multi-Takedown, gadgets, glide). The real Batman model and 51
> animations are extracted from the player's own Arkham Knight install with umodel, rebuilt headlessly in Blender and
> packed into an AssetBundle by a headless Unity 2021.3.33f1 builder. Verified in game: the mod loads the real-model
> bundle with no mod errors, and the human played the final reviewed build (real model, all 51 animations, merged
> Grapnel Batclaw, 47 review fixes) and reported that it works. Multiplayer is untested. Ripped assets stay local and are
> never shipped.

## Setup
- RoR2 1.4.1#912 (the Feb-2026 "Steamdeck Controls Update", RoR2.dll sha1 `5c183b2d…`), Unity 2021.3.33f1, Mono.
  Same build as the [Helldiver note](helldiver-survivor.md); its runtime setup applies unchanged.
- Mod manager: a fresh Thunderstore Mod Manager profile with bbepis-BepInExPack 5.4.2122 and the R2API split modules
  listed above. A 2023-era profile (BepInEx 5.4.21 / Doorstop 3, R2API 5.0.x, Wwise v135 banks) was **not** reusable.
- Code: HenryTutorial master `42797355` ("AC update", 2026-01-19), netstandard2.1, LangVersion 7.3, built with
  `dotnet build` from SDK 5.0.104 against GameLibs 1.4.1-r.0, plus a post-build reflection check against the installed
  `Managed\RoR2.dll` (see Gotcha 13).
- Asset pipeline: UE Viewer build 1590 (`umodel_64.exe`), Blender 5.2.2 portable with the DarklightGames PSK/PSA
  extension 9.1.3, Unity 2021.3.33f1 Personal (Hub sign-in once, then batchmode builds work).
- Reference: decompiled RoR2.dll (ilspycmd), kept outside the repo.

## Route and why
- **Loader API (BepInEx + R2API), HenryTutorial template.** The body is a CommandoBody clone whose model and every child
  are rebuilt from the bundle; skills are EntityStates on custom SkillFamilies. Standard RoR2 route; nothing else was
  considered for the code.
- **Model: Unity AssetBundle with Arkham's own animations on a Generic rig**, not the Helldiver note's no-Unity
  "skin onto Commando's bones" route. Batman is melee; fitting him to Commando (or Merc) would keep that body's
  animations (guns, or Merc's two-handed sword with left-arm IK). The cost is a Unity install plus Unity ID sign-in.
- **Audio: vanilla RoR2 Wwise events only** for now (Gotcha 15).

## How the game works (what we had to learn)
**Arkham Knight packages (UE3).**
- `BmGame\CookedPCConsole\*.upk`: FileVersion 863, LicenseeVersion 32995, zlib chunk compression
  (CompressionFlags 1). umodel maps that pair to `batman4`; no Oodle DLL is needed.
- Name, import and export tables sit inside the compressed chunks. Export entries are 72 bytes: standard UE3 plus one int32.
- Property tags use Rocksteady's own compact format, so a stock UE3 property parser fails.
- **Default Batsuit v8.03:** `Playable_Batman_Std_SF.upk`, three SkeletalMeshes: `Batman_BM3_V2_Skin` (body),
  `_Skin_Head`, `_Skin_Cape`. On this build `Playable_Batman_Pristine_SF` exports byte-identical files.
- **Textures:** DXT1/DXT5/BC5. High mips live in `Chunk1.tfc`, and umodel exports 2048 at most.
  `_R` maps are channel-packed (R ≈ metal/reflectance mask).
- **Animations:** Batman's core AnimSets live in `Startup.upk`, `StartupPatch.upk` and `BmGame.upk`:
  - movement and combat: BM_Movement, BM_Attack (121 strikes), BM_Combat, BM_TG_Counter, BM_TG_Takedown, BM_TG_Beatdown, BM_HitReaction;
  - traversal: BM_Glide, BM_Grapple, BM_Climb;
  - gadgets: BM_Batarang, BM_BatClaw, BM_ExplosiveGel, BM_Smoke;
  - cape: the `Batman_Cape2_Anims` sets.
  `Anim_Batman_JB/PP_Com_SF.upk` hold only paired boss fights. 26 sets in total: 1,454 clips, 114k frames at 30 fps.
- **Skeleton:** a 3ds Max Biped (`Bip01_*`) with 70 cape bones (`Bone_Cape_1..7_00..09`, 7 chains), about 236 `Flappy_*`
  jiggle bones and 61 FaceFX `FcFX_*`. Only about 54 bones carry tracks in a body clip; the rest are procedural in game.
- **Cape:** bone-driven by Rocksteady's own systems (no APEX). Cape clips are separate and live in the cape skeleton's own
  hierarchy: `Cape_Dummy > Spine2 > Spine3 > clavicles > UpArmTwist`, with the twist bones under the clavicle.
- **Root motion:** baked into Bip01. Many attack clips start about 39° yawed and turn hundreds of degrees, because Arkham
  aims them at a victim.

**RoR2 side** (facts not already in the Helldiver note).
- The animator layer layout follows Henry: Body (locomotion blend trees), Impact (additive), `Gesture, Override` (masked to
  the upper body, legs keep running), `FullBody, Override`, AimPitch/AimYaw (additive against a DefaultPose clip).
- The `aimPitchCycle` parameter is `Remap(pitch, -60..60 -> 1..0)`, so pitch clip frame 0 is looking DOWN.
  `aimYawCycle` frame 0 is LEFT (`AimAnimator.UpdateAnimatorParameters`).
- AssetBundle MonoScripts that name `Assembly-CSharp` resolve through Assembly-CSharp's type forwarders into RoR2.dll.
  Editor stub scripts therefore must use the exact RoR2 namespace (e.g. `RoR2.HurtBox`, global `ChildLocator`); a stub in
  the wrong namespace becomes a missing script at runtime.
- Unity audio is disabled in the player: `globalgamemanagers` AudioManager `m_DisableAudio = 1`. A mod `AudioSource` is
  silent; sound must go through Wwise (bank version 150 = Wwise 2023.1) or a separate library.
- Loader's two hooks:
  - Grapple Fist is `FireHook` + `LoaderHook`, Spiked Fist is `FireYankHook` + `LoaderYankHook`.
  - `ProjectileGrappleController` deducts a **secondary** stock from the owner when it bites, whatever slot fired it.
  - Both pull the owner toward terrain, so as Batclaw and Grapnel they felt like the same move in play.

## Build steps
The steps, in order. Scripts live in the mod's repo; their names are given here so the shape can be repeated.
1. **Extract** (`extract_batman.ps1`, about 15 s):
   - `umodel_64 -path=<AK>\BmGame\CookedPCConsole -game=batman4 -export -png -out=work\ak_export\mesh_std Playable_Batman_Std_SF.upk`;
   - per AnimSet: `umodel_64 -path=... -game=batman4 -export -groups -out=work\ak_export\anim <Package>.upk <AnimSet> AnimSet`;
   - keep each PSA's `.config` file next to it.
2. **Model** (`build_model.py`, Blender headless, about 30 s):
   - import body, head and cape into one armature by bone name and prune to 128 bones (biped and fingers, twist bones,
     gadget dummies, 70 cape bones), moving every removed bone's weights to its nearest kept ancestor;
   - delete the face skin under the cowl;
   - decimate per region to about 36k tris, 1.90 m tall, feet at the origin, facing -Y;
   - downscale textures and flip normal-map green;
   - export FBX: `FBX_SCALE_ALL`, forward -Z, up Y, no leaf bones.
3. **Animations** (`build_anims.py` plus a data table `clip_table.json`, about 60 s for 51 clips). For each RoR2 clip, the
   ordered Arkham candidates (trim range, speed, mirror), root handling (strip XY; yaw start / end / impact / lock /
   mean / none) and cape source, then:
   - attach the cape to the clavicle/Spine3 anchors;
   - author DefaultPose/AimPitch/AimYaw from Idle;
   - export one FBX take per clip, then re-import the FBX to prove all 51 takes arrived once with the right length.
4. **Unity** (batchmode `-executeMethod` builder):
   - import with Generic rigs, Standard materials (converted to HGStandard at runtime) and extracted `.anim` clips;
   - build an animator controller in Henry's layout plus a menu controller, then the `mdlBatman` and `BatmanDisplay` prefabs;
   - build the AssetBundle for StandaloneWindows64, reload it and validate it.
5. **Mod:** `dotnet build -c Release` → post-build reflection check → copy the DLL and bundle into the profile's
   `BepInEx\plugins\<Mod>\`.
6. **Pick clips by eye.** A review mode renders contact sheets of candidate clips (8 frames per clip,
   root XY zeroed) with per-limb peak speed, azimuth and yaw stats. Seven reviewer agents plus seven independent checkers
   replaced 37 of the first 51 picks this way.

## Verification
- **Static:**
  - a post-build reflection check resolves every RoR2 type and member the mod DLL references against the installed RoR2.dll;
  - the Blender FBX re-import (51 takes, 128 bones, lengths match);
  - the Unity builder's own checks (feet and height, skeleton, 51/51 clips resolved, 0 fallbacks, bundle reload);
  - contact sheets of every clip, looked at.
- **In game (the human launched; the agent read `BepInEx\LogOutput.log`):**
  - on the placeholder model, all skills visibly worked: stun rings, explosions, Counter flash, Fear Takedown chain,
    combo HUD to x19;
  - on the real model the log shows `'arkhambatmanbundle' is the Arkham Batman bundle (mdlBatman)`, two runs, and no mod errors;
  - 2026-10-05: the human played the final reviewed build (real model and animations, merged Grapnel Batclaw, the 47
    review fixes) and reported "It works great!". This is a human report; the agent did not review screenshots or video of it.
- **NOT verified:**
  - by the agent itself: real-model animation quality in game (no screenshots or video reviewed; only the human's report above);
  - each item of the in-game checklist one by one (e.g. Bandolier under a Special Combo, AI umbras, Backup Magazine stock edge cases);
  - Counter against ranged, boss and multiple attackers;
  - anything multiplayer.

## Gotchas
1. **umodel download is a 9 KB HTML page.** Cause: gildor.org redirects direct downloads without a Referer to "Page not
   found". Fix: send `Referer: https://www.gildor.org/en/projects/umodel` (the zip is about 2.5 MB and includes `umodel_64.exe`).
2. **Arkham packages load the wrong content.** Cause: `DLC\367480\COMMUNITYPATCH` contains packages with the same names
   as vanilla ones. Fix: point `-path` at `BmGame\CookedPCConsole` only.
3. **A set will not export, or exports the wrong copy.** Cause: `Takedown_Cape_Anims` exists twice in StartupPatch.upk.
   Fix: add `-groups`.
4. **`-lods` gives only LOD0.** umodel build 1590 writes only LOD0 for these meshes, although LOD1 (about 9k tris) exists.
   Fix: decimate LOD0 in Blender.
5. **Animations explode or sink by about 1 m.** Cause: io_scene_psk_psa 9.1.3 applies the PSK import scale as OBJECT scale.
   Fix: the PSA translation scale must match the rig. Use 1.0 while the scale is still an object scale, and the uu→m
   factor (0.008988 here) once the scale is applied to the armature.
6. **Twist and Spine2 rotations are wrong only in cape clips.** Cause: the importer applies UE's root-bone quaternion
   convention to any bone whose armature parent is missing from the PSA, and cape PSAs leave those parents out. Fix:
   detect these bones and undo the conversion (the conjugated key, pre-multiplied by the inverse rest).
7. **Cape flails through the body in every attack.** Cause: body clips carry no cape keys, so the cape follows the
   upper-arm twist bones rigidly. Fix: rebuild each cape chain relative to its anchor (clavicle for chains 1-3 and 5-7,
   Spine3 for chain 4) from a same-named `*_Cape`/`*_CapePose` clip, or else from a held `Cape_Stand` pose.
8. **Strikes punch sideways or spin the character around.** Cause: Arkham attacks are aimed at a victim (they start
   about 39° yawed and turn up to 500°). Fix: per clip, turn the whole clip so the fastest hand or foot at its peak
   points forward, or lock yaw. Prefer clips whose end yaw is close to their start yaw (RoR2 turns the body itself, so a
   clip that ends facing elsewhere snaps). Paired counters and takedowns mostly need replacing with solo strikes
   (`Counter_*_Weak_*`, `Low_Counter_*`, `Attack_Far_Forward_03`).
9. **Strafes step diagonally and the head looks away from the aim.** Cause: `Walk_Strafe_Left` is authored with the hips
   opened 35° toward the move; removing the mean Bip01 yaw turns the whole clip. Fix: keep the authored yaw (`none`).
   Mirror the left strafe for the right one; there is no right strafe and no run-speed strafe or backpedal, so speed
   up the walk versions.
10. **Legs hitch once per loop.** Cause: cross-fading the last frames into frame 0 on a loop that already closes.
    Fix: measure closure first and only fix loops that do not close.
11. **Skin pokes through the cowl.** Cause: the head mesh is a whole unmasked face; in game the SKIN_DECOWL shader hides it
    with `Head_Cowl_Mask.B`. Fix: delete skin faces by mask value (B < 0.15 always; 0.15-0.85 if under or near the cowl).
12. **Unity build fails "feet at y=-0.129".** Cause: the cape hem hangs 13 cm below the soles in the bind pose.
    Fix: measure the feet without the cape renderer.
13. **GameLibs compiles, but is the API still there?** Cause: GameLibs 1.4.1-r.0 and MMHOOK 2025.12.9 were built from the
    Dec-2025 RoR2.dll, not the installed Feb-2026 one. Fix: a post-build reflection check of every RoR2 member the mod references.
14. **Unity "installed" but missing; Personal license.** Cause: a leftover `Hub\Editor\2021.3.5f1` folder had no
    Unity.exe. Fix: install exactly 2021.3.33f1 (changeset ee5a2aa03ab2). Personal needs one Hub sign-in (no manual
    .alf/.ulf), after which `-batchmode` builds work. "Code 10 while verifying Licensing Client signature" is benign.
15. **Mod sounds are silent.** Cause: `m_DisableAudio = 1` (see above); x753's AudioEngineFix pattern no longer matches
    1.4.1's globalgamemanagers. Fix: use vanilla Wwise events, or build v150 banks for R2API.Sound.
16. **VS 2022 MSBuild cannot build the template.** Cause: no .NET SDK resolver without the .NET workload (MSB4236).
    Fix: `dotnet build`; SDK 5.0.104 restored and built netstandard2.1 fine.
17. **"rest pose differs between the FBX files" (spine 4-18°).** Cause: Blender's all-actions FBX export writes an evaluated
    pose into the animation FBX's node transforms; the numbers change with the AimPitch amplitude. Harmless when every bone
    is keyed every frame.
18. **Two hook skills feel identical.** Cause: LoaderHook and LoaderYankHook run the same `ProjectileGrappleController`
    code. It yanks a body lighter than `yankMassLimit` and reels the owner to anything else, including terrain. The two
    hooks differ only in serialized values (mass limit, reel speeds, range, damage components). The grapple also deducts
    SECONDARY stock on every bite, even when a utility skill fired it, which needed a refund hack. Fix: one secondary
    skill built on one LoaderYankHook clone that has LoaderHook's world-stick settings. Tell terrain apart by
    `ProjectileStickOnImpact` hit hurtbox index -2. On terrain, apply LoaderHook's reel values and turn off its overlap
    attack. Saved loadouts are keyed by SkillDef *name*, so keep the merged skill's `skillName`; a removed variant falls
    back to index 0.
19. **Your tracker locks onto the farthest enemy.** Cause: `BullseyeSearch.SortMode.DistanceAndAngle` ranks candidates so
    that the FARTHEST in the cone comes first (vanilla never relies on it for melee). Fix: sort yourself by distance
    multiplied by an angle penalty.
20. **AI copies of your survivor freeze (Vengeance umbras, Goobo Jr.).** Cause: an AISkillDriver with `buttonPressType
    Hold` on a `mustKeyPress` skill claims the press once; if the skill is still "ready" afterwards (extra stocks, an
    override with no cost) the AI holds forever and never reaches its other drivers. Fix: TapContinuous drivers for
    mustKeyPress skills, and a SkillDef that refuses AI bodies while its own state still runs.
21. **NullReferenceException in vanilla on-hit code from your attack.** Cause: a hand-built `DamageInfo` passed to
    `TakeDamage` + `GlobalEventManager.OnHitEnemy` without `inflictedHurtbox`; vanilla readers (e.g.
    `WyrmOnHitBehavior.TryFire`) don't null-check it. Fix: set it to the hit HurtBox (or `mainHurtBox`) and call
    `ModifyDamageInfo(hurtBox.damageModifier)`, as OverlapAttack and BlastAttack do.
22. **One player's combo step resets another's.** Cause: `SteppedSkillDef` keeps its step-reset timer on the SkillDef
    asset, which every player using the skill shares. Fix: a SteppedSkillDef subclass that keeps the timer in its
    per-slot instance data.
23. **AssetBundle import settings: keep meshes readable.** RoR2 reads skinned-mesh data at runtime, so import the model
    FBX with Read/Write enabled.

## Assets
- Everything visual comes from the player's own Arkham Knight install, extracted locally and never committed or shared.
  The shareable part is the scripts, which rebuild everything from the user's own game files.
- 22 skill icons were drawn in code from Pillow primitives; no ripped UI art.

## Cost and time
About 1.5 days of wall-clock across a local session, a cloud session and a second local session (2026-10-04 to 10-05),
using multi-agent workflows: research, skill implementation, animation-clip review, and a full adversarial code review
(24 finders, skeptic verification, per-area fixers, regression review). That review confirmed 47 of 55 unique findings.
Most were multiplayer roles and interactions with vanilla items/AI, not crashes. Two usage-limit stops: make workflows
resumable, and count an unverified finding as unverified, not refuted.

## Open questions
- Detailed in-game review of the real-model animations (sliding, strike readability) from video; the human reports they play well.
- Cape physics: authored cape clips plus held poses only. RoR2's own `DynamicBone` (an old version, present in RoR2.dll)
  could add motion.
- Arkham audio: decode the WWAD/Vorbis SFX with vgmstream and author v150 Wwise banks.
- Multiplayer: client authority of lunges, teleports and the hook reel.
