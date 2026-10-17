---
kind: game
title: "Crysis Remastered nanosuit in GTA San Andreas 1.0 US (native ASI on plugin-sdk)"
game: "Grand Theft Auto: San Andreas"
games_also: ["Crysis Remastered"]
game_version: "Steam NewSteam R2 (build 459558) downgraded to 1.0 US HoodLum exe (14,383,616 bytes); Crysis Remastered Steam (appid 1715130) as asset source"
platform: windows
engine: native
route: native-hook
tools: ["plugin-sdk (DK22Pac) commit 15f15b60", "Visual Studio 2026 (MSVC 14.51, Win32)", "Ultimate ASI Loader 9.7.4 (dinput8.dll)", "SilentPatch SA 1.1 build 34.1", "gtasa-open-downgrader v0.2.3 (logic re-implemented headless)", "Ghidra 12", "Blender 5.1 + DragonFF b3bd7aa", "Python 3.12 (uv)"]
anti_cheat: "none; single-player only. The Crysis Remastered exe is Steam-DRM encrypted and was not touched: values came from its shipped cfg/Lua"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["ovROG"]
date: 2026-10-17
links: ["https://github.com/ovROG/gtasananosute"]
tags: [gta-sa, renderware, plugin-sdk, asi, call-site-redirect, hoodlum, silentpatch, first-person, cloak, ped-model, skinning, facial-rig, cryengine2, crysis, pak, dff, txd]
---

# Crysis Remastered nanosuit in GTA San Andreas 1.0 US

NanoSuitSA v1.0 brings the Crysis Remastered nanosuit into GTA San Andreas as a native ASI plugin built on
plugin-sdk: a 200-point energy pool, Armor / Strength / Speed / Cloak with Remastered controls, a per-mode
post-process visor, cloak-aware AI, strength physics against cars and props, grab & throw, first person on foot
and in vehicles, nanovision, and a Prophet or Nomad body skinned onto CJ (cutscenes included, with jaw and brow
motion). Every feature was verified in the real game by the human player, backed by the plugin's own log. All
Crysis art, audio and model data is extracted at install time from the player's own Crysis Remastered copy; the
mod ships none of it. Source, extractor scripts and the full technical journal (`MODLOG.md`):
[github.com/ovROG/gtasananosute](https://github.com/ovROG/gtasananosute).

## Setup
- Windows 11, Steam. GTA SA Steam appid 12120, TargetBuildID 459558 ("NewSteam R2", ~4.0 GB).
- Downgraded to the **1.0 US HoodLum** exe (`gta_sa.exe`, md5 `170b3a9108687b26da2d8901c6948a18`, 14,383,616
  bytes). This is the exe plugin-sdk's raw addresses target. Used the community downgrader
  xxanqw/gtasa-open-downgrader **v0.2.3** (NewSteam R2 → 1.0 US), re-implemented as a headless Python script
  that reads the same manifest, applies its own published xdelta3 patches and checks hashes (originals go to
  `<game>ackups` like the GUI, so its Revert still works). 16 files patched, 0 failed. Back up the 16 changed files first
  (about 1.7 GB with `stream.ini`/dlls); Steam "Verify files" restores the originals. Keep Steam auto-update off.
- **Ultimate ASI Loader 9.7.4** (x86) as `dinput8.dll`, with `dinput8.ini` (DebugLog=1) and an **empty
  `wndmode.ini`**, which gives windowed mode for testing.
- **SilentPatch SA 1.1 build 34.1** in `scripts\` (it supports 1.0 US).
- **plugin-sdk** (DK22Pac) at commit `15f15b60` (2026-09-08), solution generated with premake5 `vs2026`,
  built with Visual Studio 2026 (v18, MSVC 14.51), Win32.
- Crysis Remastered, Steam appid 1715130, as the source of suit values, voice/SFX, HUD icons and the body model.
- Blender 5.1 with DragonFF (commit b3bd7aa, loaded from `sys.path`) for the DFF export; Ghidra 12 for reading
  the GTA exe.

## Route and why
`native-hook`: a C++ ASI built on plugin-sdk, loaded by Ultimate ASI Loader. SA has no official mod API.
plugin-sdk gives typed game classes, raw 1.0 US addresses, events (`gameProcessEvent`, `pedRenderEvent`,
`shutdownRwEvent`, ...) and `patch::RedirectCall`. That is more than CLEO scripts can reach (render callbacks,
camera matrices, AI vision) without writing scripts. The plugin refuses to run on any exe other than 1.0 US.
Every function hook is a **call-site redirect**, never an inline hook (Gotcha 1).

## How the game works (what we had to learn)
- **Hook points (1.0 US).** Each is reached by redirecting its call sites. Before patching, the plugin checks at
  runtime that the site's byte is `E8` and that the call target is the expected function, and logs any site it
  skips.

  | Function | Address | Call sites redirected |
  |---|---|---|
  | `CPad::UpdatePads` | 0x541DD0 | 0x53BEE6 (in `CGame::Process`) |
  | `CPedDamageResponseCalculator::ComputeDamageResponse` | 0x4B5AC0 | 26: 0x439074, 0x4813E5, 0x4BA0A8, 0x5680D3, 0x56828C, 0x5E2F8F, 0x5E3054, 0x5F0D2A, 0x5F0F44, 0x6049C9, 0x604AB8, 0x629810, 0x63344A, 0x654034, 0x65698C, 0x67C911, 0x68604B, 0x68B462, 0x6A92BB, 0x6A94FA, 0x6B6396, 0x6B6580, 0x6D840A, 0x6DB326, 0x6DBE9C, 0x73A6E9 |
  | `CDraw::SetFOV` | 0x6FF410 | 0x52C976, 0x53BD7A, 0x5BA224, 0x156D57E (inside the `.HOODLUM` section) |
  | `CCamera::CopyCameraMatrixToRWCam` | 0x50AFA0 | 0x51A587, 0x51A5B1, 0x52C98B |
  | `CCamera::Find3rdPersonCamTargetVector` | 0x514970 | 0x60B703, 0x61F06D, 0x627E34, 0x628469, 0x62AD98, 0x73E8CC, 0x7403BE |
  | `CPed::OurPedCanSeeThisEntity` | 0x5E1660 | 0x47B2A0, 0x4831D9 (script "spotted" checks) |
  | `CPed::CanSeeEntity` | 0x5E0730 | 0x73CE60 |
  | `CPedIntelligence::CanSeeEntityWithLights` | 0x605550 | 0x4B37F8, 0x4B39B2, 0x606CA1, 0x607577, 0x62B93D (acquaintance scanner, events, kill task) |
- **Damage.** All ped damage goes through `ComputeDamageResponse`. `m_fDamageFactor` is the HP about to be
  applied, and `m_pDamager`/`m_weaponType` say who did it with what (weapon types ≤ 15 are melee). Armor scales
  the factor down and charges energy. Power melee scales it up. Fall damage (`WEAPONTYPE_FALL`) is zeroed after
  a power jump. To knock a ped over from your own code, call `CWeapon::GenerateDamageEvent(victim, CJ,
  WEAPONTYPE_RAMMEDBYCAR, dmg, torso=3, 0)`. Inside the damage hook, defer this by one frame (re-entrancy).
- **Movement.** SA moves peds by animation root motion, so Speed mode scales the run/sprint animation speed
  (`m_fSpeed`) instead of setting velocity. Infinite stamina comes from `CPlayerData::m_fTimeCanRun`. Sprint is
  tapped rather than held: `CPad::GetSprint` flickers, so the plugin treats sprint as held for 350 ms after the
  last tap.
- **Cloak.** Peds use `CVisibilityPlugins::SetClumpAlpha`, re-applied in `pedRenderEvent`. Police are handled
  with `CWanted::m_bLeavePlayerAlone` plus `m_fMultiplier = 0` (no witnesses), restored on uncloak. The three
  vision functions above return "not seen" for a cloaked CJ beyond 3 m. To lose pursuers, on engage and every
  second, non-mission peds (`m_nCreatedBy != 2`) within 40 m that are running a combat task (KILL_PED_ON_FOOT*,
  SIMPLE_FIGHT, USE_GUN, GANG_HASSLE_PED) get `FlushImmediately(true)`.
- **Transparency of non-ped things.** For the held weapon, grabbed props and bikes, a per-atomic render
  callback lowers material alpha only for that atomic's draw and restores it afterwards, because geometry is
  shared with every other instance. It also needs `rpGEOMETRYMODULATEMATERIALCOLOR` (Gotcha 3).
- **Strength physics.** Cars: `ApplyMoveForce` (mass × 0.22 forward, + 0.06 up) plus `ApplyTurnForce`, hit
  tested against the col-model bounding box in the car's frame. Props: `ObjectDamage`. Rooted props
  (`bIsStatic`, `bIsLampPost`) and corpses ignore velocity, so a throw flies them along a hand-simulated
  ballistic arc and hands them to physics on landing. A breakable prop has `m_nColDamageEffect != 0`.
- **Camera / first person.** Redirect `CopyCameraMatrixToRWCam` and, before the original runs, move
  `TheCamera.m_mCameraMatrix` and the placeable position to the eye. SA keeps doing mouse look, movement and
  aiming itself. Near clip 0.03. Crosshair multipliers set to 0.5/0.5 put SA's own aim ray through the screen
  centre. Aim parallax is fixed by swapping the active cam source only inside the 7
  `Find3rdPersonCamTargetVector` calls (Gotcha 5). `CDraw::SetFOV` is the single funnel for every FOV the game
  sets, so the visor's FOV offset is added there.
- **Bones.** `RpHAnimHierarchy::pMatrixArray` holds world-space matrices in SA. On foot, the eye is the physics
  root plus a low-passed root-to-head offset (the raw head bone shakes with the run cycle). Head bones (ids 6-8
  and ≥ 5000) are collapsed before the player renders, and shoulders/arms near the eye are pulled in.
- **Cutscene CJ** is a `CObject` with model `CSPLAY` (id 1), not a ped, and is drawn through
  `objectRenderEvent`. `csplay.dff` has its own **61-bone rig**: jaw1 5015 / jaw2 5016, lbrow1 5004 / lbrow2 5003,
  rbrow1 5001 / rbrow2 5002, eyelids 5005 / 5006, cheeks 5020 / 5021, lips 5007-5014 and 5017, eyes 5018 / 5019,
  extra thumb bones 28 / 29 / 38 / 39 and nubs 5022-5026. Player CJ (32 bones) only has jaw 8, left brow 6,
  right brow 7. Mapping used: 8 ← 5016, 6 ← 5004, 7 ← 5001.
- **Body swap.** The suit clump is swapped into CJ's entity only around `CEntity::Render`, so CJ's model,
  clothes, animations and weapons stay untouched. Pose transfer:
  - **Body:** CJ's bone matrices are copied directly by HAnim id every frame.
  - **Face:** jaw and brows are retargeted relative to the head:
    `Pose' = (Bind_face' · InvBind_head') · (Lb_cj⁻¹ · Pose_face_cj · Pose_head_cj⁻¹) · Pose_head_cj`.

  A full bind-space retarget (`Bind_ours · InvBind_cj · Pose`) turned the whole body 90° (Gotcha 8).
- **Shutdown.** Destroy your own clump/TXD in `shutdownRwEvent` (Gotcha 13).
- **Nanovision** is SA's own thermal post effect, `CPostEffects::ScriptInfraredVisionSwitch`.
- **Crysis Remastered data.** `Game\*.pak` are plain deflate zips with backslash local headers (Gotcha 9). One
  x64 exe, `Bin64\CrysisRemastered.exe` (34.6 MB), with CryGame linked in. Its `.text` is Steam-DRM encrypted,
  so suit balance was read from the shipped cfg/Lua instead: energy 200; regen to full in 4 s after a 2.5 s
  delay; health regen to full in 6 s after 5 s; Armor soaks 125 HP per full bar (1.6 energy/HP, at least 30%
  absorbed); cloak drains 10 energy/s base; speed sprint costs 24/s at ×3 (×1.8 when empty); melee ×1.4. Jump
  force/cost and melee cost were not found. Remastered also has "Classic suit" variants of several cvars.
- **Crysis suit modes are shader passes, not textures** (Gotcha 10).
- **Crysis model files.** Every `.chr` is a CryEngine 2 chunk file, version 0x745.
  - Body: `objectsch.pak` → `objects/characters/Human/US/NanoSuit/NanoSuit_us.chr` (74-bone Bip01, 6015 v /
    9219 t) plus helmet `NanoSuit_Helm_simple.chr`; `nanosuit_us.cdf` puts both on
    `generic/skeleton_male.chr`.
  - Prophet: `Laurence_Barnes.cdf` = suit body + `Heads/Story/Laurence_Barnes/Barnes.chr` (only Spine3/Head
    bones, 89 facial morph targets, no face bones) + a neck helmet + 2 × `Eye_generic_04.cgf`.
  - Morph records are `{u32 vertex, f32 delta[3]}`. SA's jaw/brow weights were derived from the Jaw_dropper_*
    and Brow_*_raiser_* morphs.
  - Bone-mapping ids in the mesh streams are local to the subset's bone table (MeshSubsets flag 2).
  - Diffuse alpha is a gloss mask, not opacity.
- **SA ped skin bind space** (as DragonFF sees it): up = +X, front = +Y, left = +Z, pelvis at the origin. Crysis
  Bip01 and SA are both Biped rigs: mapping bone frames puts bone directions within 3.5° (arms), so bone roll
  was taken from the frames. Final model: one atomic, ≤ 32 skin bones, ≤ 4 weights per vertex, TXD in DXT1 with
  mips.

## Build steps
1. Downgrade the Steam exe to 1.0 US (see Setup), then install UAL 9.7.4 as `dinput8.dll` with an empty
   `wndmode.ini` and SilentPatch 34.1 in `scripts\`. Launch `gta_sa.exe` directly; Steam is not needed. On the
   first run, choose the resolution in "Device Selection" with the mouse.
2. Build plugin-sdk: set `PLUGIN_SDK_DIR`, run `premake5 vs2026` in `tools/premake`, then
   `msbuild plugin_sa\Plugin_SA.vcxproj /p:Configuration=Release /p:Platform=Win32` (produces a ~258 MB
   `Plugin.lib`).
3. Build the mod: `msbuild NanoSuitSA.vcxproj "/p:Configuration=Release GTA-SA" /p:Platform=Win32`. The
   configuration is named `Release GTA-SA`, not `Release`. Copy `NanoSuitSA.SA.asi` to `scripts\`.
4. Extract Crysis voice/SFX/icons from the player's own install (Python + ffmpeg) into
   `scripts\NanoSuitSA\crysis`. Build the body model (Python + Blender/DragonFF), which reads the player's own
   Crysis paks and SA `gta3.img`, into `scripts\NanoSuitSA\model`.
5. Settings live in `NanoSuitSA.ini`, written with defaults on first run. It includes `[Debug]` switches that
   turn each redirect group off, for bisecting conflicts.

## Verification
- **Oracle:** in-game play by the human, confirmed feature by feature, plus the plugin's own log (opened with
  `_fsopen(..., _SH_DENYNO)` so it can be read while the game runs). The log records:
  - an init line with the exe version and the count of redirected sites per group (e.g. "damage call sites
    26/26");
  - a state dump every 2 s;
  - every armor absorb, power hit and cloak break with numbers;
  - "N ped(s) lost track of CJ" for the cloak.
- **Verified by the user:** intro skip; radial menu with Crysis icons; mode announcements, voice and SFX; armor
  absorption; power melee and power jump with no fall damage; enemies losing a cloaked CJ; strength against
  cars and props; grab & throw of peds, props and bikes; first person on foot ("good enough") and in vehicles;
  nanovision; Prophet body in game, in first person and in cutscenes with lip and brow motion; per-mode suit
  looks. The human accepted v1.0.
- **Checked offline:** the model pipeline (vertex, triangle and bone counts, ≤ 4 weights; the Nomad
  build stayed byte-identical after the Prophet work).
- **Not verified:**
  - other exes (Compact 1.0, 1.01, Steam/RGL builds); the plugin refuses them;
  - clump-type weapons under cloak;
  - swimming/climbing in first person;
  - long play sessions;
  - unattended automated tests: SA pauses when its window loses focus and ignores synthetic keys (Gotcha 15).

## Gotchas
1. **Inline hooks "succeed" but the game silently breaks.** On `CPad::UpdatePads` (0x541DD0), cutscene skipping
   stopped working. On `ComputeDamageResponse` (0x4B5AC0), no damage was ever calculated for anyone, and nobody
   noticed for two builds because nobody fought. **Cause:** on the 1.0 US HoodLum exe many function entries are
   crack stubs (`push esi; push edi; jmp <stub>` or `mov eax,[esp+4]; jmp <stub>; ret`). A trampoline built from
   those bytes is broken (the UpdatePads case also sits next to SilentPatch's keyboard-latency fix). **Fix:** never inline-hook on this exe.
   Redirect each call site with `patch::RedirectCall` and call the untouched original by address. Check each
   site's `E8` and target at runtime first. The full site list is in the table above; one SetFOV caller lives in
   the `.HOODLUM` section (0x156D57E).
2. **With Strength on, every ped's punch on CJ became a mega punch.** **Cause:** `CHEAT_MEGA_PUNCH` is a global
   cheat flag, not per-ped. **Fix:** don't use it. Scale damage in the damage hook and apply knockback yourself.
3. **Material alpha does nothing on props and weapons** (peds fade fine). **Cause:** RenderWare ignores
   material colour unless the geometry has `rpGEOMETRYMODULATEMATERIALCOLOR`. Peds have it; most props and
   weapons don't. **Fix:** set the flag and the alpha only around that atomic's draw (render callback), then
   restore both, because the geometry is shared.
4. **A thrown prop's line-of-sight test always hit something immediately.** **Cause:** the ray started at the
   prop's own pivot and hit the prop. **Fix:** set `CWorld::pIgnoreEntity` to the prop for the
   `CWorld::ProcessLineOfSight` call.
5. **First-person aim had parallax, and the first fix hung a new game about 2 s in.** **Cause:** swapping the
   active camera source across frames (via a `CCamera::Process` redirect) breaks camera state. **Fix:** swap it
   only for the duration of the 7 `Find3rdPersonCamTargetVector` calls.
6. **After moving the camera, objects outside the original view vanished.** **Cause:** culling uses the
   frustum derived before the move. **Fix:** after changing the camera matrix following `CCamera::Process`, call
   `CCamera::CalculateDerivedValues(false, true)` (0x5150E0), as SA does right before
   `CopyCameraMatrixToRWCam`.
7. **HUD text invisible at 640×480.** **Cause:** plugin-sdk's `SCREEN_COORD*` macros truncate to int, so font
   scales become 0. **Fix:** compute HUD units as floats.
8. **The suit body was rotated 90° after a "proper" bind-pose retarget.** **Cause:** CJ's skins (the
   clothes-built player and `csplay`) use a differently rotated model space from the DFF bind. **Fix:** copy
   CJ's pose matrices directly by HAnim id for the body. Retarget only the face, relative to the head (formula
   above). Use csplay's own 5000-series ids in cutscenes.
9. **Python `zipfile` refuses Crysis paks** ("File name in directory ... differ"). **Cause:** local headers
   store `\` while the central directory stores `/`. **Fix:** on that error, retry the member name with
   backslashes.
10. **No per-mode suit textures exist in the paks.** **Cause:** Crysis suit modes are shader passes. The mode
    `.mtl` files turn on `%NANOSUIT_EFFECTS` in `Cloth.cfx`: additive moving spark lines masked by the diffuse
    alpha (red for strength, yellow for speed, a metallic look for armor). **Fix:** bake each look statically
    into a per-mode texture and swap material 0's texture by mode at runtime.
11. **Crysis Remastered exe can't be disassembled for cvar defaults.** **Cause:** `.text` is Steam-DRM
    encrypted. **Fix:** don't touch it. Take the values from shipped cfg/Lua files (list above); what's only in
    code stays unknown.
12. **Crash at start with GTASA.WidescreenFix (release asset dated 2026-10-04) plus SilentPatch 34.1.**
    **Cause:** an unhandled C++ exception when one of its HUD hook patterns finds nothing, because SilentPatch
    already patched that code. Load order doesn't matter. **Fix:** don't install it alongside SilentPatch 34.1
    (it works without SilentPatch). An upstream compatibility fix (2026-10-07) existed only as a CI artifact at
    the time. Its zip also ships UAL as `vorbisFile.dll`; don't add that next to `dinput8.dll`.
13. **Exit crash at 0x4DD5A3** (audio code, null + 0x24, access violation on window close). **Cause:** it
    happens **without the mod** too (tested with the ASI renamed): this 1.0 + UAL wndmode + SilentPatch setup
    has it. Don't chase it as yours. A different exit crash at 0x7C6A28 (skin plugin destructor, via
    `RpAtomicDestroy` from `rsRWTERMINATE`) *was* ours. **Fix:** destroy your own clump/TXD in
    `shutdownRwEvent` and add a per-frame guard that restores any clump left swapped.
14. **Log file unreadable while the game runs.** **Cause:** `fopen_s` opens exclusively. **Fix:**
    `_fsopen(path, "a", _SH_DENYNO)`.
15. **Agent-driven keyboard tests stall.** **Cause:** SA pauses itself when its window loses activation, and
    synthetic keys don't reach it (mouse clicks do reach menus). The opening intro could not be skipped by
    synthetic input. **Fix:** a human tester, or an in-plugin test driver that writes `CPad` state.
16. **Prophet's eyes rendered as black holes.** **Cause:** SA's ped pipeline drew the blended lash overlay
    opaque and didn't cut out the eyeball alpha. Crysis diffuse alpha is a gloss mask, which made holes too.
    **Fix:** drop all alpha from the model and bake the iris into the eyeball texture.
17. **cgf-converter 2.0.0 crashes on `NanoSuit_us.chr`** (CompiledBones_800 chunk) and drops UVs without
    `-mtl`. **Fix:** write your own reader for chunk file version 0x745. DragonFF also rebuilds frames from the
    inverse bind matrices, so the stock rotated "Root" frame changes. Graft the skin onto the stock DFF frames
    instead.
18. **A build failed but was still deployed and committed.** **Fix:** build scripts must check `$LASTEXITCODE`
    before copying or committing.

## Assets
None are generated or shipped. Crysis voice lines, SFX, HUD icons and the suit/Prophet model are extracted at
install time from the player's own Crysis Remastered paks by Python scripts. Audio is converted with ffmpeg.
The model goes through a custom `.chr` reader, glTF, then Blender 5.1 + DragonFF to DFF, and is grafted onto
the stock SA skeleton. Diffuse textures (very dark, mean 38/255) were given baked relief (from the Crysis normal maps),
cavity, Cycles AO and a spec hint, keeping mean brightness. Per-mode textures were baked from the Cloth.cfx
effect look.

## Cost and time
One long day (2026-10-17), 48 commits from first scaffold to the v1.0 tag, with the
human playing every build.

## Open questions
- Support the Compact 1.0 exe (untested; whether its entries are free of stubs was not checked).
- Find Crysis's jump force/cost and melee energy cost, which aren't in cfg/Lua.
- Cover clump-type weapons under cloak, and stop the cloak's "lose pursuers" from interrupting unrelated gang
  fights within 40 m.
- Build an in-plugin `CPad` test driver for unattended regression runs.
- Re-check Widescreen Fix once its SilentPatch compatibility fix ships in a release.
