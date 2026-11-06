# TWAU: Garry's Mod Sandbox Conversion

Press **F1** anywhere in *The Wolf Among Us* and the story freezes in place: same scene, same light, every
character where they stood. You're in first person with Garry's Mod's HUD, physgun, toolgun and HL2 guns.
**F3** clears everything you spawned, puts every story character back, and the chore continues from the
second you left it.

Bring your own games: the mod reads models, sounds and fonts straight from your Garry's Mod install and the
character/scene lists straight from your TWAU archives. Nothing from either game is shipped.

## Status (2026-10-18)

| Part | State |
|---|---|
| `AssetBridge`: VPK v1/v2, `.ttarch2` (NCTT/ZCTT + 3ATT), catalogs, MDL/VVD/VTX/VTF/WAV | **verified offline** on both installs (`twau_assetscan`: all checks pass) |
| `LuaBridge`: the game's Lua 5.1.4 C API by RVA, `lua_pcall` hook | **works in game** (handles the game's several Lua VMs) |
| `gmod_sandbox.lua`: engine adapter | **conventions verified** against the game's own scripts and in-game probes (MODLOG) |
| D3D9Ex `PresentEx` hook (in front of the Steam overlay), HUD, viewmodels, spawn menu | **works in game** |
| F1 freeze / F3 resume, first-person camera, WASD + mouse, walk boxes, noclip | **works in game** |
| Spawning characters (animated while the story is frozen), guns, death → ragdoll | **works in game**; NPCs stay on the walk boxes |
| Walls for bullets, rockets, blasts, physgun and toolgun | **works in game** (the walk boxes stand in for walls: the engine has no level raycast) |
| The game's own UI (hover verbs, interaction dots, tutorials) | **hidden in sandbox**, back on F3 |
| Physgun grab and freeze | **works in game** |
| Flashlight | **works in game** on characters (a copy of the scene's character light); walls and floors stay unlit |
| Face & Finger Poser | **works in game**: every rest face the character has (Bigby 23, Faith 12), 11 mouth shapes with an amount slider, face channels, and per-finger curls with presets (fist, point, peace...) |
| Viewmodel bob | **works in game**: HL2's `CalcViewmodelBob` (the gun bobs, rolls and sways while you walk or run) |
| Map menu | **works in game**: all 41 Episode 2-5 scenes open (the game's resources switch to that episode; a guard stops a native crash in the game's own scene script); you start on the scene's walk boxes, or fly from the story camera where there are none |
| Per-bone ragdolls | **works in game**: every bone of the corpse is simulated (Faith: 110), joints bend within limits, knees and elbows one way only, limbs collide with the body and each other; bones weigh by size (trunk heavy, fingers light), shots push the bones near the hit, the floor has Coulomb friction; the physgun grips the bone under the crosshair and the rest hangs and swings |
| Big Bad Wolf (`sk35`) locomotion | the game data has no walk/run clip for it; it glides in place |

## Controls

| Key | |
|---|---|
| F1 / F3 | enter sandbox / back to the story |
| WASD, Space, Shift, Ctrl, mouse | move, jump, sprint, crouch, look |
| V | noclip (Space/Ctrl up/down in noclip) |
| F | flashlight (GMod `items/flashlight1.wav`) |
| 1-6, wheel | weapon slots: 1 Physics Gun, 2 Tool Gun, 3 Crowbar, 4 Pistol/SMG, 5 Shotgun/RPG, 6 Camera |
| LMB / RMB | fire; physgun grab / freeze; toolgun use |
| E | physgun: rotate the held object with the mouse; other weapons: an NPC follows you / stays |
| Wheel (holding) | physgun: push / pull |
| R | reload; toolgun: next tool mode |
| Q (hold) | spawn menu: NPCs, ragdolls, playermodels (filter: bipeds / quadrupeds / birds), tools |
| C (hold) | Face & Finger Poser (pick the character with the toolgun's Face Poser mode): emotions, mouth shapes, face channels, fingers |
| M | map menu: every location of the five episodes |
| Insert | console (`help`, `lua <code>`, `spawn <name>`, `lookat`, `ai stay/wander/follow`, `map [scene] [episode]`, `probe`, `agents`, `reload`, `thirdperson`; reverse engineering: `skel`, `peek`, `poke`, `hwbp`) |

F12 is never used (it's the recording key on the test PC).

## Architecture

```
TheWolfAmongUs.exe (x86, D3D9, Lua 5.1.4 with float numbers, no physics engine)
 └─ dinput8.dll  (proxy: forwards to System32\dinput8.dll, loads *.asi)
     └─ TWAU_GMod.asi
         ├─ AssetBridge.cpp          VPK + ttarch2 readers, catalogs, Source model/texture/sound decoding
         ├─ LuaBridge.cpp            the game's Lua API by RVA, lua_pcall hook = one tick per frame on the game thread
         ├─ StateAndCameraManager.cpp  F1/F3, snapshot/restore, FP controller, noclip, flashlight, axis calibration, console
         ├─ GModMenuAndHUD.cpp       D3D9Ex PresentEx/Reset hooks, ImGui HUD and menus, viewmodels, beams, screenshots, input isolation
         ├─ CombatAndRagdollPhysics.cpp  weapons, HP, physgun, toolgun, rigid bodies, verlet ragdolls, NPC locomotion
         ├─ Audio.cpp                XAudio2 playback of GMod .wav straight from the VPKs
         └─ <game>\gmod\lua\gmod_sandbox.lua   GM.* adapter over the engine's own Lua functions
```

Every engine action goes through Lua (`AgentSetWorldPos`, `ControllerSetTimeScale`, `PlayAnimationLooping`,
`CameraPush`, ...), so the C++ side needs no engine struct offsets. Each Lua call is wrapped and logs its
first failure to `<game>\gmod\gmod_sandbox.log`, which is how the unverified argument conventions get fixed.

How the pieces map to the request:
- **Freeze (F1):** `GM.Snapshot` records every agent's world position, quaternion and visibility;
  `GM.Freeze` sets every controller (chores, animations, the playing dialog line) to time scale 0 and notes
  its time. **Resume (F3):** spawns destroyed, agents put back, controller times restored, scale 1.
- **First person:** our own camera agent (`module_camera.prop`) pushed over Telltale's. Its local forward axis
  and the screen handedness are found at runtime by reading `AgentGetForwardVec` and
  `CameraGetScreenPosFromWorldPos` back. Movement is clipped to Telltale's walk boxes unless noclip is on.
- **Quadrupeds:** body plan from the skeleton family (`sk18_colin`, `sk35_wolfBigby` are four-legged,
  `sk37_crow` a bird), locomotion clips from the catalog (`sk18_colin_walk.anm`, not a biped walk), with
  siblings of the same skeleton family lending clips (`sk54_crane_walk` drives any `sk54` man). Werewolf
  Bigby sprints with `sk54_bigbyWere_runQuadruped.anm`.
- **Face Poser:** emotions play `<face>_phoneme_default_<emotion>.anm` (the resting face per emotion; the
  menu lists every one the character has). Mouth shapes are the lip-sync poses
  `<face>_phoneme_<AA|EE|I|O|U|FV|LL|MM|NN|SH|TH>_<emotion>.anm`, parked at their middle frame and weighted
  by the slider, in the current emotion's variant when there is one. Sliders weight additive
  `<face>_face_brows*/eyesLook*/blink/squint/eyesWide_add.anm` layers with `ControllerSetContribution`.
- **Finger Poser:** bones carry no names we can read, so hands are found by shape (a bone with 4-6 child
  chains 2.5-20 cm long, in a mirrored pair); the thumb is the chain pointing away from the others. A curl
  turns each joint about the axis the finger already bends around, added after the animation mixer by the
  same per-bone hook as the ragdolls, so the pose holds while the character idles. Console:
  `pose emotion angry`, `pose mouth AA 0.8`, `pose fingers 0.8 1 1 1 1` (the last spawn).
- **Death:** HP per agent; at 0 the clip stops and the corpse becomes a verlet ragdoll with one particle per
  bone. The character's `SkeletonInstance` is found in memory (its root bones hang off the agent's node), the
  bones are grouped into rigid pieces (pelvis, chest, head, hands) joined by cone-limited joints, knees and
  elbows bend one way only, and capsules along the bones keep limbs out of the torso and each other. Each frame the particles become local bone rotations, written into Telltale's bone
  nodes and re-applied from a hook on the engine's per-bone animation call, so the idle pose can't come back.
  If no skeleton is found (another build of the game), a 7-particle body drives the root transform instead.

## Build

Visual Studio 2022 (or Build Tools) and CMake; dependencies (Dear ImGui 1.91.9b, MinHook 1.3.3, zlib 1.3.1)
are fetched at configure time.

```bash
cmake -S . -B build -A Win32
```

```bash
cmake --build build --config Release
```

Offline check against your installs (no game launch):

```bash
build/Release/twau_assetscan.exe --chars --scenes
```

## Install (not done automatically)

1. Back up the saves: `um backup create "%USERPROFILE%\Documents\Telltale Games\The Wolf Among Us" --name twau-saves`.
2. Copy `dinput8.dll` and `TWAU_GMod.asi` next to `TheWolfAmongUs.exe`.
3. Copy `lua\gmod_sandbox.lua` to `<game>\gmod\lua\` and `gmod_sandbox.ini` to `<game>\gmod\`.
4. Launch, load a chapter, press F1. Logs: `<game>\gmod\gmod_sandbox.log`.
5. Optional, for testing: console commands written to `<game>\gmod\cmd.txt` run on the next tick (output in
   the log).

Uninstall: delete `dinput8.dll`, `TWAU_GMod.asi` and the `gmod` folder.

## Credits

Garry's Mod and Half-Life 2 content © Facepunch Studios / Valve, The Wolf Among Us © Telltale Games / LCG
Entertainment: read from your own installs, never redistributed. Dear ImGui (MIT), MinHook (BSD-2), zlib.
Built with an AI coding agent (Claude Code); the reverse engineering notes are in `MODLOG.md`.
