---
kind: game
title: "rf-gmod: a Garry's Mod-style sandbox (gravity gun, physgun, HL2 weapons, noclip) in RFG Re-Mars-tered, with an untested Armageddon port"
game: "Red Faction: Guerrilla Re-Mars-tered"
games_also: ["Red Faction: Armageddon", "Half-Life 2", "Garry's Mod"]
game_version: "RFG: Steam app 667720, rfg.exe cs:4931 (SHA-256 0d52039e7f2d3f25a4be52a2aba83919456fb3f00e52e75051726247471a2df4); RF:A: Steam app 55110, RedFactionArmageddon_DX11.exe (SHA-256 6a3c42dc...1dea, link timestamp 0x57B0E035)"
platform: windows
engine: native
route: native-hook
tools: ["MinHook 1.3.4", "Dear ImGui 1.91.9b", "Ghidra 12.1.4 (headless)", "capstone + pefile (via uv)", "XAudio2 2.9", "MSVC x86 (Visual Studio 18) + CMake + Ninja", "doctest", "numpy, scipy, Pillow", "um backup"]
anti_cheat: "none; single-player only. The DLL refuses any exe whose SHA-256 it doesn't know and stays idle in multiplayer."
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: ["@skurtyyskirts"]
date: 2026-10-27
links: ["control-resonant-dylan-takeover-retargeted-animations.md", "https://github.com/rfg-modding/RSL", "https://github.com/rfg-modding/RFGR_Types", "https://github.com/LostPhysx/RFG-VR", "https://github.com/gibbed/Gibbed.Volition", "https://steamcommunity.com/sharedfiles/filedetails/?id=2665902404", "https://www.moddb.com/downloads/half-life-2-mmod-version-11", "https://github.com/TsudaKageyu/minhook", "https://github.com/ocornut/imgui"]
tags: ["gravity-gun", "physgun", "telekinesis", "source-movement", "noclip", "viewmodels", "d3d11", "havok", "raycast", "despawn", "blood", "draw-distance", "clean-reinstall", "cross-game-port", "dinput8-proxy"]
---

# rf-gmod: a Garry's Mod-style sandbox (gravity gun, physgun, HL2 weapons, noclip) in RFG Re-Mars-tered, with an untested Armageddon port

> A private sandbox mod for Red Faction: Guerrilla Re-Mars-tered: Source-engine movement and noclip, a "mega"
> gravity gun and a physgun that hold, throw, freeze and tear pieces out of buildings, HL2's weapons (models and
> sounds read from the human's own Half-Life 2 / Garry's Mod installs) drawn in first person, nothing despawning.
> It is a native `dinput8.dll` proxy plus MinHook DLL built on the plumbing of the earlier
> [Dylan Faden mod](control-resonant-dylan-takeover-retargeted-animations.md). Two RFG builds ran in the human's
> tests: the second confirmed the guns and gravity gun hit the world (8,867 raycasts logged). The latest build
> (blood, MMod viewmodels, dual pistols, longer draw distance, building rebuild) and the **whole Red Faction:
> Armageddon port are untested**: Armageddon never ran because Steam's licence prompt was still waiting for the
> human to accept it.

## Setup
- **RFG:** Steam app 667720, the exe hash above (the same exe as the Dylan mod; check it before reusing any
  address). Windows 11. The exe is ASLR-relocated; addresses below are VAs at image base 0x400000.
- **RF:A:** Steam app 55110. Only DX9 and DX11 exes exist (no DX12; both import only d3d9 or d3d11 + dxgi).
  Target: `RedFactionArmageddon_DX11.exe`, x86, image base 0x400000, no ASLR, no SteamStub section, imports
  `dinput8!DirectInput8Create` (so the same proxy loads), **not large-address-aware** (2 GB). The only community
  tools found for it are [Gibbed's Volition packfile tools](https://github.com/gibbed/Gibbed.Volition), shipped in
  the game's `build\` folder.
- **Source assets, read from the human's installs and never committed:** Half-Life 2 (app 220, the 2024
  anniversary VPK layout), Garry's Mod (app 4000; its `hl2/resource/halflife2.ttf` is the HUD font), and their
  Garry's Mod Workshop subscriptions: the [[TFA][AT] Project HL2 MMod Pack](https://steamcommunity.com/sharedfiles/filedetails/?id=2665902404)
  and the "TFA INS2 USP Match" pistol packs. The [MMod download on ModDB](https://www.moddb.com/downloads/half-life-2-mmod-version-11)
  sits behind a Cloudflare check; the Workshop pack already had the weapons.
- **Build:** MSVC x86 (Visual Studio 18) + CMake + Ninja, `/W4 /WX`; [MinHook 1.3.4](https://github.com/TsudaKageyu/minhook)
  and [Dear ImGui 1.91.9b](https://github.com/ocornut/imgui) fetched by CMake, pinned by SHA-256. One source tree
  builds two DLLs (Route). Ghidra 12.1.4 headless on both exes, one instance at a time, BelowNormal.
- **Backups with `um backup` before anything was installed:** RF:A's Steam-cloud saves
  (`userdata\<id>\55110\remote\`, snapshot `rfa-saves`, restore with `um backup restore rfa-saves --yes`, game
  closed), RFG saves and config (`rfg-saves`, `rfg-config`) before the clean reinstall.
- **The earlier Dylan mod was uninstalled first**: its deploy script restored `misc.vpp_pc` / `table.vpp_pc` from
  the hash-checked `um backup` copies, and its installed files were zipped to an archive outside the repo. rf-gmod's deploy
  refuses to install while that mod's `resonant\` folder is present.

## Route and why
- **Native hooks through a `dinput8.dll` proxy**, the route the Dylan mod proved on the same exe: the proxy loads
  `rf-gmod\rf_gmod.dll` (kill switch: an empty `rf-gmod\disable.txt`). The address table carries a confidence per
  entry and build-time prologue fingerprints from the human's own exe; an unknown exe disables every hook.
- **A game-agnostic core** (C++20, an `IGame` interface: player, view, raycast, bodies and humans near a point,
  body velocity / impulse / freeze, rip a piece, explode, damage, ragdoll, game actions) holds all sandbox rules
  and is tested against a fake world. Each game supplies an engine layer.
- **Two DLLs from one tree:** a compile switch selects RF:A's engine layer (`src/rfa/`) and its types, declared
  in the same `rfg` namespace, so the shared code compiles unchanged. Each DLL is fingerprinted against its own exe.
- **HL2 weapons drawn by the mod** at DXGI Present with its own depth, since neither game can load Source models.
- Considered: Armageddon's DX12 (doesn't exist), raising the object pools (deferred: test on RF:A first).

## How the game works (what we had to learn)
RFG facts the Dylan mod established (input getters, damage sink, despawn sweep and fade starters, pools, camera,
render frame) are in [that note](control-resonant-dylan-takeover-retargeted-animations.md). New here:

### Movement, bodies and the raycast (RFG)
- **Noclip:** hold the character controller still (no gravity, zero velocity) in the proxy update 0x837D90 and
  place the player with the human's own `update_pos_and_orient` 0xA9AF70 (vtable +0x30,
  `thiscall(pos*, orient*, bool move_controller)`, `ret 0xC`; moves object and controller in world coordinates).
- **Freeze / unfreeze:** `havok_body_set_movable` 0x823DA0 (false = Havok motion type 5 FIXED, true = 1 DYNAMIC and
  activate). Angular velocity: read 0x817510 (body+0x1C0), set 0x823910 (wakes first). Ragdoll with impulse
  0xAD4F50; holster 0xAB8040.
- **Explosions** use a cloned `explosion_info` (0xF0 bytes); the structural damage unit is 10000 (an RFG rocket
  is 23625).
- **The raycast layer decides what a ray can see.** The game's bullet trace 0xBE5C80 calls the raycast 0x835A30
  (at 0xBE5F56) and then `world_object_from_handle`; it passes the u32 at **0x165FE84 (value 0x19)** as the layer
  (input +0x24) and **2 at input +0x2C**. The ray filter 0x81C010 indexes a collision matrix by
  (layer low 16 bits) x 128 + the body's layer; +0x2C (global 0x2B82280) skips shapes whose property 8 (0x816C10)
  has those bits. 0x165FE00..0x165FEFC is the game's table of layer words: 0x165FE84 has 84 readers in the exe,
  0x165FE9C (0x20) only two (Gotcha 1).

### World tweaks (RFG; static RE, values read back from the exe offline)
- **NPC distance fade:** opacity floats at 0x165CBF0 / 0x165CBF4 (65 / 75 m). The game itself sets them far out
  while the player is scoped; the mod writes 10000 / 10001.
- **Pop-in:** ambient despawn rings 0x16B6B1C = 120, 0x16B6B20 = 260, 0x16B6B24 = 160, each with a squared copy
  (0x374831C, 0x37457CC, 0x374A4E0) that must change too; crowd cull 0xB4DB70 `cdecl(min², max²)`; corpse cap
  0xA5AB30 (7); human LOD table 0x165F3AC (10/30/50/100); far clip 0x1DE5350 = 475 m, high-LOD distance 0x1DE5354
  = 320 m (setter 0x7C2C40). The human caps (74/89) were left alone.
- **Blood:** `effect_find` 0x7431F0 and `effects_play` 0x747910 (cdecl, 10 args: effect, pos*, orient*, looping,
  host handle, tag, source, float volume, camera bool, category; caller cleans 0x28). On a human hit,
  `wep_bullet_impact_flesh_a` gives the game's flesh puff and its sound; world splatter 0x74B940 (cdecl, 6 args);
  gore byte 0x1663169, decals byte 0x165CC74.
- **Rebuild:** the multiplayer repair event `0x7140E0 cdecl(mover*, repairer*, local pos*, float radius,
  int amount, bool force)`, called on the main thread for standing building movers (+0xF8 == 0, +0x154 == 1,
  +0x14C set), at most 8 per frame, amount -1 = full. It deletes chunks that return to the building and anything
  inside the rebuilt volume; keeping rubble needs a flag around the handler 0x733FE0 and a refusal in a detour of
  the world delete 0x91D070. It can't rebuild a building whose root object is gone.
- **Lighting for the viewmodels:** scene = `*(0x2533894)`: fog +0x30, colour correction +0x50..+0x74, HDR +0x78,
  sun colour +0xF0, sun direction +0x100, ambient +0x10C, ground ambient +0x11C (written each frame on the render
  thread before Present).
- **Hiding the player's body:** `human::set_opacity_plus_child_items` 0xA7E1D0 (thiscall, `ret 4`) is what the
  game uses when Mason zooms in; forcing alpha 0 for the local player hides body and held item. A shadow-flag
  setter is at 0xA54700 (untested).
- **Havok, the consistent way:** solver = hkpWorld+0x1F0 (world* at 0x2B82284); steps at solver+0x12C, micro
  steps +0x130, 1/micro +0x134, 1/steps +0x138; `setupSolverInfo` 0xE03DC0; fixed-step byte 0x165FB5B.

### Source-side facts
- Movement in Source units (1 u = 0.0254 m) with GMod's defaults: walk 200, run 400, slow walk 100, crouch x0.3,
  jump 200, gravity 600 u/s² (15.2 m/s², for the player only), accelerate 10, air accelerate 10 with the 30 u/s
  wish cap, friction 8, stop speed 10. Noclip 1000 u/s along the view (Shift x3, Alt x0.25).
- Viewmodels: Source model space is view space; D3D view = (-y, z, x). HL2's viewmodel FOV 54° is horizontal at
  4:3 (41.98° vertical). Activities are `ACT_VM_*`; the gravity gun's claws open through its `active` pose
  parameter. MMod models are MDL v48 with 60 fps sequences (resampled to 30).

### Red Faction: Armageddon (static analysis only, nothing confirmed live)
- Static world at 0x1535EF8; `player_do_frame` 0x7C4530 is cdecl(player*); the proxy update has RFG's shape;
  raycast input is 0x34 bytes; damage sink 0x785310 is `float cdecl(damage_info*)`; `explosion_info` is 0x144
  bytes (mover/vehicle/human impulses +0x64/+0x68/+0x6C, structural +0x74, type +0x7C, radii +0x80/+0x84);
  `explosion_create` takes 9 args; input getters are `cdecl(int action, int user, int* src)` (17 primary ... 31
  use, 24 crouch); body handles are `hkpRigidBody*`; hkpWorld* at `*0x1683698`, solver steps at solver+0x304,
  micro +0x308, 1/micro +0x30C, 1/steps +0x310 (an earlier table had these wrong); despawn sweep gate byte
  0xD9BA48, debris lifetime at +0x9C; NPC fade floats 0xDB13D8/0xDB13DC (65/75), LOD table 0xDDB8F8, scene at
  `*(0x161CD98)`, opacity setter 0x779E60.
- Armageddon's Reconstruct (the Nano Forge's repair) pulls loose pieces back into buildings by design, so "keep
  the rubble" there would mean repair events for building movers only; not built.

## Build steps
1. **HL2 packs** (Python via `uv`, from the human's HL2 / GMod / Workshop folders, output outside the repo): read
   VPK v1/v2 with gameinfo search paths, KeyValues, MDL v44-48 with animation decode, VVD/VTX meshes, VTF
   textures, VMT materials, WAV and soundscripts; Workshop `.gma` archives. Write a viewmodel pack (the mod's own
   RVMP format: skinned meshes, PBR-ish texture sets, sequences at 30 fps, attachments, events) and a sound pack
   (RSFX, the same container as the Dylan mod: named sounds, variants, cues; the viewmodel animation events drive
   the cues, so build viewmodels first). RFG pack: 98 MB of viewmodels at 1024 px textures; RF:A pack: 69 MB at
   512 px (Gotcha 8).
2. **Native:** build script → `dinput8.dll`, `rf_gmod.dll` for RFG and `rfa\rf_gmod.dll` for RF:A; it checks both
   DLLs export the proxy's entry point. Core tests (45 cases) and native tests (53) plus a smoke host.
3. **Before deploying an address**, check offline that each new global sits in a writable section of the real exe
   and holds the value the RE predicts (e.g. 65/75 for the fade floats, 10/30/50/100 for the LOD table).
4. **Deploy** with the game closed (scripts refuse while it runs): RFG gets the proxy + `rf-gmod\` (DLL, packs);
   RF:A the same plus its own DLL, DX11 exe only (the DX9 exe also loads the proxy and the mod declines there).
   `-DryRun`, `-Uninstall`, `-ResetIni`; ini changes go through versioned migrations with `.v<N>.bak` backups.
5. RF:A windowed 1280x720: `HKCU\Software\Volition\Red Faction: Armageddon\Video Settings` (delete to restore).
6. Controls (GMod's PC defaults): WASD with air strafing, Shift run, Alt slow walk, Ctrl crouch, V noclip, C first
   person, G god mode (off at start), E use / carry props up to 35 kg, slots 1-6 with Q for the last weapon. Slot 1
   cycles crowbar → gravity gun → physgun. Gravity gun: right click pulls and holds, left click launches; at a wall
   right click rips a piece, left click blasts it. Physgun: left click grabs, wheel for distance, E + mouse
   rotates, right click freezes, R unfreezes. Slot 2: dual USP Match (left/right click fire right/left, R reloads
   both). F6 rebuilds buildings. Insert opens the panel.

## Verification
The human runs every RFG test (the agent never launches RFG); the agent reads `<RFG>\rf-gmod\rf_gmod.log`.
- **RFG test 1 (2026-10-26):** no crash; every hook, the sandbox, viewmodels, sounds, first person and noclip ran.
  The human saw no telekinesis, guns that touched nothing, and NPCs and gravity "really off" (Gotchas 1-2).
- **RFG test 2:** no crash, all 88 addresses and 23 hooks in. In 6 minutes: 8,867 raycasts (building 1,484,
  human 161, body 240, vehicle 109, static 1,083, nothing 5,790), 123 damage hits, 42 blasts, 5 rips, 4 freezes,
  1 ragdoll. The head-hide lookup logged `head bone -1` (Gotcha 3).
- **Clean reinstall (the human suspected the old Dylan mod):** RFG's folder renamed aside, Steam re-downloaded 26 GB
  (`steam://validate/667720`), and the fresh copy was compared with the old one: 168 vs 190 files, the extra 22
  being only this mod's files, the proxy and logs; `misc.vpp_pc` and `table.vpp_pc` hash-identical; `rfg.exe`
  the same hash. The old mod had left nothing behind, so the problems were rf-gmod's own.
- **Latest build (2026-10-27): not run.** Checked offline: both DLLs build clean, tests pass, every new address
  fingerprints in both exes and every new global is writable and holds the predicted shipped value.
- **Red Faction: Armageddon: never run.** Steam shows its licence agreement on launch, and accepting it was left to
  the human; three launch requests were queued behind it. Every RF:A address is static-only.

## Gotchas
1. **Guns and the gravity gun went through people and debris.** **Cause:** the raycast passed the layer word at
   0x165FE9C (0x20), copied from caller 0x83C4F0, which isn't a weapon; the layer picks a row of the collision
   matrix. **Fix:** use the bullet trace's layer (0x165FE84 = 0x19) and flags 2. Test 2 then logged hits on
   buildings, humans and bodies. Log the first raycasts by hit kind so the next test settles it.
2. **NPCs and gravity felt wrong world-wide.** **Cause:** "max physics" wrote Havok's step count (4 → 8) without
   the stored inverse, so rigid bodies stepped at twice real time while NPC controllers didn't (the same cause as
   the Dylan mod's test 4). **Fix:** write steps 8, 1/steps 0.125, micro steps 1 and 1/micro 1 together in the
   step detour; leave tau and damping. (Turned back on in the latest build at the human's request; untested.)
3. **The body showed in first person.** **Cause:** the head-bone lookup by name returned -1 on the live rig.
   **Fix:** a detour of 0xA7E1D0 forcing alpha 0 for the local player (`camera.fp_hide_body`).
4. **The RPG's flight sound looped forever.** **Cause:** a cue-looped WAV was started as a one-shot at the launch
   point with nothing to stop it. **Fix:** a keyed positional loop per projectile, stopped when the rocket
   explodes; one-shots never loop; rockets expire after 10 s so the RPG can't wait forever on a lost rocket.
5. **The human couldn't find the telekinesis.** **Cause:** it is the gravity gun in slot 1, behind the crowbar.
   **Fix:** document the slot cycle (Build steps 6) and the panel.
6. **"Is my old mod breaking this?"** A clean reinstall plus a file-list and hash diff against the old folder
   answers it in minutes; keep the old folder until the human is happy.
7. **`namespace rfg = rfa` broke the build.** **Cause:** shared headers reopen `namespace rfg`, which an alias
   can't be. **Fix:** declare RF:A's types inside `namespace rfg` in its build. Also `far` is a `windows.h` macro:
   don't name a variable `far`.
8. **RF:A can address only 2 GB.** **Cause:** its exe isn't large-address-aware. **Fix:** cap its viewmodel
   textures at 512 px (69 MB pack instead of 98 MB).
9. **Licence prompts block an agent's launch.** Steam's first-launch EULA for RF:A must be accepted by the human;
   queued launches start once it is.
10. **PowerShell `git commit -F - @'...'@` failed** with a pathspec error. **Fix:** write the message to a file
    and use `git commit -F <file>`. Bash heredocs with Windows paths also mangled `\r` (a journal line became
    `rf-gmod<CR>f_gmod.dll`): write files with an editor tool or a script file.

## Assets
No generated assets. HL2, Garry's Mod and Workshop models and sounds are converted from the human's own installs
into packs that stay on that PC and are never published.

## Cost and time
About two days of sessions (2026-10-26 to 2026-10-27), with sub-agents for the HL2 asset pipeline, the RF:A RE
pass and the RFG world-tweaks RE pass (about 48 minutes).

## Open questions
- The latest build in game: MMod/USP viewmodels lit by the game's sun, blood, no NPC fade, draw distance, Havok at
  8 steps done consistently, rebuild keeping rubble (duplicate or shoved chunks are expected), shadow with the body
  hidden.
- NPCs hit by the mod's guns skip the game's own hit reactions; routing hits through them is next.
- Bullet impacts on walls make a sound but no spark or decal.
- All of Armageddon: a live pass of every address once its licence is accepted, head/body hide, its effects
  table, rebuild.
- Bigger object pools (RFG's debris pool holds 500).
