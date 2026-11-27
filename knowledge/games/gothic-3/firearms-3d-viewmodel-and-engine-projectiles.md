---
kind: game
title: "Firearms in Gothic 3: a 3D revolver and AK-47 in first person, drawn by our own D3D9 pass and fired through the engine's projectile pipeline"
game: "Gothic 3"
games_also: []
game_version: "1.75.20108.14 (Steam 39500) + Community Patch 1.75 + Community UpdatePack 1.04 + PUP + Union+ 1.6.4, Windows 11"
platform: windows
engine: native
route: native-hook
tools: ["gothic3sdk (rev 90bfd34)", "MSVC 2022 Build Tools (Win32)", "CMake", "fxc (Windows SDK)", "Blender 5.2 (headless)", "Python (uv, numpy, Pillow, capstone, pefile)", "Ghidra 12.1.4", "Gothic 3 Modkit (FSG.exe)", "Rimy3D", "g3dit", "g3blend"]
anti_cheat: "none; single-player only"
status: working
agents: ["Claude Code (Opus 5.5)", "OpenCode (models not recorded)"]
humans: ["Arekosandoru"]
date: 2026-11-11
links: ["https://github.com/georgeto/gothic3sdk"]
tags: [genome, gothic-3, firearms, fps, viewmodel, d3d9, endscene, projectiles, sdk-hooks, offline-test-host]
---

# Firearms in Gothic 3: a 3D revolver and AK-47 in first person, drawn by our own D3D9 pass and fired through the engine's projectile pipeline

A script DLL (`scripts\Script_FpsLayer.dll`, built on the open-source gothic3sdk) adds a revolver and an AK-47 to
Gothic 3. **F** puts the gun in the hero's hands in the game's own first-person camera. An arm holding a real 3D
gun model is drawn over the frame by our own Direct3D 9 pass, with hammer and cylinder animation, a muzzle flash
and ejected cases. Each shot is a real engine projectile (a cloned `Bolt` template), so hits, damage, deaths and
XP come from the engine itself. Verified in the real game up to build v66 (2026-11-10): log oracle plus in-game
screenshots. Two later tuning builds are not yet verified (see Verification).

## Setup
- Gothic 3 **1.75.20108.14**, Steam app 39500, Windows 11, D3D9 renderer.
- Patch layers: Community Patch 1.75, Community UpdatePack 1.04, PUP (version not recorded), Union+ 1.6.4.
  Union+ ships its own `Strings` and `newGameSkills.ini`, which other mods have to build on (Gotchas).
- Engine addresses below were checked against `Script_Game.dll` sha256 `4d29189281ec26ea…f4262a24` (the
  UpdatePack build). The hero's script logic lives in that DLL, so other patch stacks will have other addresses.
- SDK: [georgeto/gothic3sdk](https://github.com/georgeto/gothic3sdk) at `90bfd34` (2025-11-13), GPL-3.0.
  All hooks go through its `Hook.h`. Its `Script_AniName_Adp` sample is a minimal working hook to start from.
- Build: VS 2022 Build Tools, Win32, C++17, CMake; `fxc` compiles one SM3 HLSL file into headers at build time.
- Data tools: FSG.exe from the official Gothic 3 Modkit for `.pak` packing, Rimy3D for `.xcmsh` meshes, g3dit and
  g3blend as format references. Our own Python readers/writers for `.pak`, `.tple`, `.xact`, `.xmot`, `.ximg`.
- Reverse engineering: Ghidra 12.1.4, capstone and pefile for spot disassembly.

## Route and why
**Route: a native script DLL plus a few small data overlays.** Gothic 3 loads every `scripts\Script_*.dll` by
scanning the folder, and the SDK gives typed access to the engine's classes, so no exe patch or loader is needed.

What the DLL does:
- **Viewmodel:** our own D3D9 render of an arm and a gun, in a hook on `eCDX9Device::EndScene`, only while the
  game's own first-person camera is active and no menu, dialogue or GUI page is open. Models are our own small
  format (skinned, up to 64 bones, attach points `muzzle`/`eject`, an optional `fire` clip) with DDS textures.
- **Ballistics:** the engine's own projectile recipe, repeated from our code: spawn a cloned `Bolt` template
  (`Bullet`, in `Templates.mNN`), give it a `Point` collision shape in the `Projectile` group, set
  `PathStyle = Physics`, put damage on the projectile's `gCDamage_PS`, then `gCProjectile_PS::Shoot`. We never
  wrote our own physics, hit test or damage.
- **Input:** the layer reads the mouse itself. While our gun is out, the game's script handlers `OnPlayerAction`
  (LMB) and `OnPlayerSecondaryAction` (RMB) are hooked, so the hero doesn't also swing, loot or talk.
- **Data overlays:** `Templates.mNN` (the `Bullet` template), `_compiledMesh.mNN` (a 2 cm bullet mesh),
  `Sound.mNN` (gunshot samples, swapped in by two hooks).

Routes we took first and abandoned, each after an in-game test:
- **Gun as an inventory item** (a cloned crossbow with 148 cloned hero animation clips). It works, but the hero
  stays in crossbow stances: the barrel points about 45° up in first person, and the cadence is the crossbow's.
- **Bow UseType** (`UseType = 5`). Damage works, but the bow is a hold-to-draw weapon: a click gives a weak
  shot at your feet, and the pose is a horizontal bow pose. Not fixable through templates or actors.
- **Our own spawned bolt** (`SpawnEntity` + `Shoot`). It flies but touches nothing, because it has no collision
  shape (see How the game works).
- **2D sprites of the gun** (v13–v59). They worked and shipped for a while, but a sprite can only line up the
  barrel with the crosshair on the image, never in 3D. Real models replaced them in v60.

## How the game works (what we had to learn)
**Modules.** `Engine.dll` (application, frames, sound, animation, data mounting), `Game.dll` (game logic,
property sets, projectiles, damage, effects), `Script.dll` (script API wrappers), `SharedBase.dll` (strings,
containers, memory), and `scripts\Script_Game.dll` (the hero's state machine, shipped by the Community Patch /
UpdatePack). There is no PDB. Names in `Game.dll`/`Engine.dll` come from MSVC mangled export strings and RTTI.
`Script_Game.dll` names come from its own registration code: every state is registered as a pair "name string →
function", so walking those registration calls rebuilds the whole state map (we got 429 entries).

**Data mounting.** `Data\<Name>.pak` (retail), `.p00` (patches), `.mod` (CP and Union+), then mods as
`.m00 … .mNN`. Generations mount strictly in sequence, and the first missing number stops everything above it,
silently. Install a mod as the next free number. The pak header's `Reserved` field must be `'G3PD'`
(0x44503347); FSG writes garbage there, and the game then skips the pak without a word.

**Templates (`.tple`).** A self-describing `GENOMFLE` container: each property is name, type, magic, size,
value, with names and types in a string table. The GUID is 16 significant bytes out of 20. A clone needs a new
GUID, and the file name must equal `EntityName`. Byte offsets differ between the retail file and the one the
Genome editor writes, so build from one reference file. A changed template is only picked up in a new game, but
a **new** template (our `Bullet`) is found in existing saves.

**Actors (`.xact`) and clips (`.xmot`).** `GENOMFLE` → u16 version → u32 offset of the `DEADBEEF` marker →
content → `DEADBEEF` → strings. Chunks: NODE=0, MOTIONPART=1, ANIM=2, MESH=3, SKINNINGINFO=4, MATERIAL=6.
Vertex positions and normals are stored as (Z, Y, X). Submeshes have 2 padding bytes and meshes 3; getting either
wrong breaks the file. The hero skeleton has 112 bones, bind pose is a T-pose, and keyframes are absolute local
transforms. Hero clip names are assembled by `GetAniName` (`Game.dll` RVA 0x16F840) from enum-indexed tables
(actor, stance, UseType of each hand, action, phase, direction). There is no way to add a UseType, so custom
clips need a hook on `GetAniName` or `QueryMotionDataEntity`.

**Textures and strings.** Normal maps use the game's own layout: X in alpha, Y in green, R = B = 0, always DXT5
(all 418 vanilla normal maps agree). `stringtable.ini` is UTF-16-LE with exactly one BOM, languages separated
by `;;`.

**Sound.** A shot plays through an effect: `eff_*` → `PlaySound` command → sample. The engine looks samples up
by bare name, without folder or extension, so a new `.ogg` in `foley/...` works without touching `Library.*`.
To give one weapon its own sound we hook `StartEffect` (set "our shot" flag) and `PlaySample3D` (swap the name).
The effect's owner is the projectile entity, and the sample position isn't the shooter's, so neither identifies
who fired.

**How the hero shoots** (read from the disassembly, then reproduced in our code and confirmed in game):
1. spawn the ammo's template;
2. `SetOwner(projectile, shooter)`;
3. `CreateShape(Point = 7, Projectile = 5)`;
4. disable collision with the shooter;
5. `PathStyle = Physics` (2) for the player, `TouchBehavior = MaterialDependant`;
6. direction = normalize(screen-centre pick point − weapon position);
7. damage goes into the projectile's `gCDamage_PS`;
8. `gCProjectile_PS::Shoot`.

Without step 3 and Physics, the projectile has no body and is purely visual. `Line` and `Reflect` path styles
hit precisely but deal no damage.

**Projectile flight** (from the disassembly; not yet measured in game):
- **`ShootVelocity` is in km/h.** The engine multiplies the unit direction by `ShootVelocity × 0.27778 × 100`
  to get cm/s, so 260 is 72 m/s.
- With `PathStyle = Physics`, the velocity is set **once**. After that PhysX flies the projectile, and drop is
  the scene's gravity. `Line` (NPCs) sets the velocity every frame, so there's no drop.
- **Hits come from a ray, not rigid-body contact.** A `Point` shape keeps its last position. On every move the
  engine casts `TraceRayNearestHit` along "last → current", starting 100 cm back, and on a hit sends touch events
  to both entities, with a per-bone check against creatures. A fast bullet can't tunnel through a target.
- **Damage is native:** `gCTouchDamage_PS::TriggerTarget` applies it. The script callback `OnTouchDamage` is only
  a reaction hook; changing it doesn't deal damage.

**Hero state machine and input.**
- Ranged combat is a set of `PS_Ranged_*` states. A state that reaches its end is re-run from block 0 **every
  frame**, so a "run once" gate inside a state isn't "once per entry".
- The action queue holds a single action, and a new one replaces the old.
- Key messages carry `IsPressed` / `IsPressedBefore` bits. For every key except Use1/Use2, an action is created
  only on a press or release edge, so holding a button never repeats it.
- Synthetic input therefore needs a full click (down + up, about 30 ms apart) to count as an edge.

**Rendering.**
- `EndScene` fires **several times per frame**: once for the HDR scene target (format 113), once for an 8-bit
  target (21), and once for the final target, which matches the backbuffer (22). Draw only into the last one.
- Inside `EndScene`, `D3DTS_VIEW` is not the game camera. Use `eCDX9Device::GetViewMatrix` with
  `D3DTS_PROJECTION`.
- Camera space is left-handed: X right, Y up, Z forward, in centimetres. A glTF model converts by negating X,
  which also flips the triangle winding.

**A frame tick without hooking frame functions:** `timeSetEvent` (8 ms) plus the exported
`eCApplication::GetMasterFrameCounter()`; act when the counter changes.

## Build steps
1. Get the SDK: `git clone https://github.com/georgeto/gothic3sdk` and check out `90bfd34`.
2. Build the DLL and the offline test host (Win32):
   ```powershell
   cmake -S gunplay -B gunplay/build -G "Visual Studio 17 2022" -A Win32
   cmake --build gunplay/build --config Release --target Script_FpsLayer
   cmake --build gunplay/build --config Release --target vmhost
   ```
3. Models: donor model → Blender headless (bake procedural materials, UVs) → a Python packer writing the
   viewmodel file plus DDS textures. Attach points `muzzle` and `eject`. The last frame of the `fire` clip is
   the rest pose.
4. Projectile data: clone the vanilla `Bolt` `.tple` with a new GUID and `EntityName = Bullet`, pack it with FSG
   (absolute paths only), fix the pak header (`Reserved = 'G3PD'`), check the pak against the source folder,
   and install it as the next free `Templates.mNN`. Same for the bullet mesh (`_compiledMesh.mNN`) and sounds
   (`Sound.mNN`).
5. Copy `Script_FpsLayer.dll` and its model folder into `<game>\scripts\`. Back up saves first.

## Verification
- **Offline gate, before every install** (one script):
  - format tests for the model and DDS files against the loader's struct sizes;
  - the test host renders both guns with the same viewmodel code into PNGs, which the agent looks at;
  - a PE `.text` comparison that proves a rebuilt DLL matches what's installed;
  - an import check that every DLL import exists in the game's DLLs (a missing one makes the game skip the DLL
    silently);
  - sha256 of the installed kit against the build.
- **In-game oracle:** our own log in `<game>\logs\`. It records `init log ok`, one `hook <name>=1` per hook,
  model loaded, viewmodel drawn, `real=1` per shot when the engine accepted the projectile, the target's HP and
  `dead=1`, and the flight trace of the first bullets. `Documents\Gothic3\Lastlog_GE3.log` holds crashes. Each
  run was played manually with screenshots; both logs were read afterwards and a verification report written per
  build.
- **Verified in game (v60–v66, 2026-11-10):**
  - 3D revolver and AK-47 with arm, hammer/cylinder animation, muzzle flash and cases;
  - light follows frame brightness (night, caves);
  - no items visible through walls;
  - LMB only fires while armed (no loot/talk/attack);
  - damage and kills on NPCs and monsters;
  - no crashes in those runs.
- **Not verified:**
  - v67/v68 (smaller AK on screen, 1300 km/h AK bullets, aim on held RMB): installed, not run;
  - the km/h reading of `ShootVelocity`, and ray hits at high speed (disassembly only);
  - the game's normal-map layout on our own textures;
  - other resolutions and AA settings, and the fallback path when the final target isn't found;
  - compatibility with other script mods;
  - restoring first person after a save load or dialogue;
  - one `Engine.dll` access violation in an older build (v40) whose cause was never found.

## Gotchas
1. **Mod files "don't exist", no error.** **Cause:** a gap in the `.mNN` chain stops mounting at that number.
   **Fix:** install as the next free number and list `Data\<Name>.*` to check the chain.
2. **A freshly packed pak is ignored.** **Cause:** FSG writes garbage into the header's `Reserved` field.
   **Fix:** set it to `'G3PD'` after every FSG run.
3. **FSG says "Done" but the pak didn't change.** **Cause:** FSG doesn't overwrite an existing `.pak`.
   **Fix:** delete the old pak first, then compare the pak against the source folder.
4. **All menu and item names vanish.** **Cause:** a second BOM in `stringtable.ini`, or a `Strings` mod that
   isn't a superset of Union+'s. **Fix:** exactly one `FF FE`; build on top of Union+'s strings.
5. **Starting a new game hangs while loading.** **Cause:** `DamageAmount = 5000` on a template. **Fix:** 500
   works; the vanilla ranged maximum is 190.
6. **Dialog "Found non unique Filenames" at startup.** **Cause:** the same file name twice anywhere under
   `Data` or `scripts\`, folders included (we hit it with a specular map, then with same-named textures in two gun folders). **Fix:**
   make every file name unique; give specular maps their full `Data/Materials/Images/...` path.
7. **A hook silently does nothing.** **Cause:** the hook object was a local, and its destructor removed the
   hook. **Fix:** make hook objects `static` or global; log `hook <name>=<ok> proc=<address>` for each.
8. **Crash at `SharedBase.dll+0xEA00`.** **Cause:** hand-written `__asm` trampolines or IAT patching.
   **Fix:** use the SDK's `Hook.h` only.
9. **Crash at `Engine.dll+0x888A0`, or an access violation when starting a new game.** **Cause:** hooking a
   per-frame function (`eCApplication::OnRun`) or the script processor (`ProcessScript`). **Fix:** use the
   `timeSetEvent` + `GetMasterFrameCounter` tick, and hook specific script *functions* such as
   `OnPlayerAction`, not the processor.
10. **The bullet flies but never hurts anything.** **Cause:** no collision shape, or `PathStyle` Line/Reflect.
    **Fix:** repeat the engine's recipe: `CreateShape(Point, Projectile)`, `PathStyle = Physics`, damage on the
    projectile. In the disassembly the call pushes 5 then 7; under `__thiscall` the first argument is pushed
    last, so shape type is 7 and group is 5, not the other way round.
11. **Synthetic `LEFTDOWN` presses are ignored** (78 presses, 8 shots). **Cause:** the engine acts on edges and
    needs both. **Fix:** send a full click about 30 ms long; read the real button with `WH_MOUSE_LL`, filtering
    out `LLMHF_INJECTED`.
12. **Auto-fire stops after a loading screen while the log still says the mouse hook is installed.** **Cause:**
    Windows silently removes a low-level hook whose thread is slow to pump messages. **Fix:** re-install it when
    the engine sees LMB but the hook doesn't.
13. **Items show through walls while the gun is out.** **Cause:** we cleared the game's depth buffer during the
    HDR pass. **Fix:** never touch the game's depth; use our own depth surface and draw only into the final
    target.
14. **Our gun fires and the hero's bow or sword attacks too.** **Cause:** the game's script reads the same LMB
    through `OnPlayerAction`. **Fix:** hook that script function and skip it while our gun is out (same for RMB
    and `OnPlayerSecondaryAction`).
15. **Mouse becomes slow in first person.** **Cause:** `EnableTempFirstPerson` in Ranged mode is the bow-aim
    branch. **Fix:** switch the camera with `SetMode(0xB)` instead.
16. **The mod key makes the hero sprint and holster.** **Cause:** F6 is bound to `OnPlayerToggleSpeedUp` in
    `Ini\controls.ini`. **Fix:** check `controls.ini` before choosing a key (plain F was free).
17. **The AK model points backwards.** **Cause:** the forward-axis sign differs per donor model; the revolver's
    "muzzle along −Z" rule didn't carry over. **Fix:** check orientation in the test host or the game, not from
    code.
18. **"Export not found."** **Cause:** pefile stops parsing exports when many names share one address
    (`Engine.dll` accessors). **Fix:** read the export table directly.
19. **Each "safety" layer on synthetic input broke the previous fix** (four regressions in an hour). **Cause:**
    every guard changed edge timing. **Fix:** roll back to the last working build and change input one thing
    at a time, testing in the menu and in the world.

## Assets
- Revolver: a free third-party model with its own 2048² textures and bones. We added hammer, cylinder and
  trigger animation.
- AK-47: a free third-party model. It had no UVs or textures, so we unwrapped it and baked its procedural
  materials in headless Blender.
- Arm: a separate hands model, re-posed to hold both guns.
- Bullet mesh: our own, 2 cm, built with Rimy3D from OBJ. Gunshot samples: our own.
- No game files or extracted assets are in this note.

## Open questions
- Measure the real bullet speed and drop in game, to confirm the km/h reading.
- Reloading the revolver (the model has `hinge` and `rod` bones).
- FOV zoom while aiming; the gun is still drawn over the HUD.
- A Genome engine playbook: no engine page exists for Gothic 3 yet, and much of the above would belong there.
