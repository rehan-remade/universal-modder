# MODLOG: The Wolf Among Us → Garry's Mod Sandbox Conversion

Journal for this mod. It becomes the knowledge-base field note at the end.

## 2026-10-18: recon, route, first code (nothing run in game yet)

### Target: The Wolf Among Us (Steam 250320)
- `C:\Program Files (x86)\Steam\steamapps\common\The Wolf Among Us\TheWolfAmongUs.exe`, 9,297,080 bytes,
  PE timestamp 1384476156 (2013-11-15). **x86 (32-bit)**, DllCharacteristics 0x8140 → **ASLR on**: every
  address below is an RVA from image base 0x400000.
- Imports `d3d9.dll`, `d3dx9_41.dll`, `DINPUT8.dll`, `fmodex.dll`, `steam_api.dll`. **Direct3D 9.**
- Has a `.bind` section (SteamStub), but `.text` is plain on disk (20,879 `push ebp; mov ebp,esp`
  prologues), so static RVAs are valid. We don't touch the stub: the mod loads as `dinput8.dll` and
  only hooks after the game created its D3D9 device.
- `um scan`: "Unknown native engine", no anti-cheat, no loaders. Single-player only.
- **No physics engine** in the exe (no PhysX/Havok/Bullet). `Physics*` Lua functions are just movers
  (`PhysicsMoveAgentToBySpeed` etc.). Ragdolls must be our own simulation.

### Lua: Lua 5.1.4, statically linked, `lua_Number` is FLOAT
- `math.abs` does `fstp dword` → numbers are 32-bit float. Linking stock Lua and calling it on the game's
  `lua_State` would corrupt it. Use the game's own API functions only.
- Found through the stdlib `luaL_Reg` tables in `.rdata` (base lib at 0xA1E4E8, string 0xA1D938, math
  0xA1D798) and by disassembling `print`, `loadstring`, `pcall`, `type`, `rawget`, `tonumber`, `assert` and
  `luaopen_base` (at 0x8594B0):

| function | VA | how identified |
|---|---|---|
| lua_gettop | 0x8415B0 | print, pcall |
| lua_settop | 0x8415D0 | print (`lua_pop`), rawget |
| lua_insert | 0x841670 | pcall |
| lua_pushvalue | 0x841760 | print |
| lua_type | 0x841790 | type |
| lua_typename | 0x8417B0 | type |
| lua_isnumber | 0x841800 | tonumber |
| lua_tonumber | 0x841990 | tonumber (returns float in st0) |
| lua_toboolean | 0x841A10 | assert |
| lua_tolstring | 0x841A40 | print |
| lua_pushnumber | 0x841C30 | math.abs (float arg) |
| lua_pushlstring | 0x841C70 | luaopen_base ("_VERSION") |
| lua_pushstring | 0x841CC0 | type |
| lua_pushcclosure | 0x841D90 | luaopen_base (ipairs/pairs) |
| lua_pushboolean | 0x841E30 | pcall |
| lua_getfield | 0x841ED0 | print (`tostring`) |
| lua_rawget | 0x841F30 | rawget |
| lua_createtable | 0x841FB0 | luaopen_base (newproxy) |
| lua_setfield | 0x8420F0 | luaopen_base (`_G`) |
| lua_setmetatable | 0x842230 | luaopen_base |
| lua_call | 0x842370 | print |
| lua_pcall | 0x8423D0 | pcall; prologue `55 8B EC 8B 4D 14` (hookable) |
| luaL_error | 0x842A20 | assert |
| luaL_callmeta | 0x842B50 | tostring |
| luaL_loadbuffer | 0x8430B0 | loadstring |
| luaL_checktype | 0x8433B0 | rawget |
| luaL_checkany | 0x843410 | pcall |
| luaL_checklstring | 0x843440 | loadstring |
| luaL_optlstring | 0x8434A0 | loadstring |
| luaL_checknumber | 0x843500 | math.abs |
| luaL_register | 0x8439D0 | luaopen_base |

- `LUA_GLOBALSINDEX` = -10002 (0xFFFFD8EE pushed in print).
- No static `luaL_Reg` tables for the engine API: Telltale registers its functions in code. Their names
  are in `.rdata` though, so the names used by `lua/gmod_sandbox.lua` were all checked to exist
  (`AgentGetWorldPos`, `AgentSetWorldPos`, `AgentSetWorldRotFromQuat`, `AgentHide`, `AgentCreate`,
  `AgentDestroy`, `AgentGetControllers`, `ControllerSetTimeScale`, `ControllerGetTime`,
  `ControllerSetTime`, `ControllerSetContribution`, `CameraPush`, `CameraPop`, `CameraSetFOV`,
  `SceneGetAgents`, `SceneGetActiveSceneNames`, `SceneOpen`, `PlayAnimationLooping`, `CursorHide`,
  `GetFrameTime`, `Vector`, `Quaternion`, `ResourceExists`, `SetSubProject`, `GetSubProjectExists`,
  `WalkBoxesPosOnWalkBoxes`, `DialogStopAll`, ...). **Their argument conventions are NOT verified**:
  every call in the Lua side goes through a logged `pcall` so the first in-game run says which ones need
  fixing.
- Loose-file route exists too: the exe has `_resourcedescriptions_` and `set.gameDataArchives = `
  (resource sets are Lua). Not used yet; the native bridge doesn't need the Blowfish key.

### Archives (`Pack\*.ttarch2`), parsed and checked on all 48 files
- Two wrappers: `NCTT` (u32 magic, u64 size, then raw stream) and `ZCTT` (u32 magic, u32 chunk size
  0x10000, u32 chunk count N, u64 offsets[N+1] absolute; each chunk is **raw deflate**, zlib wbits -15).
  No `ECTT` (encrypted) in this game.
- Inner stream `3ATT`: u32 version (2), u32 name-table size, u32 file count, then 28-byte entries
  {u64 crc64, u64 offset, u32 size, u32 unknown, u16 name block, u16 name offset}; names at
  `block*0x10000 + offset` in the name table; file data offset is relative to the end of the name table.
- 156,789 files: 64,315 .anm, 24,583 .wav, 22,825 .chore, 20,855 .d3dtx, 6,703 .d3dmesh, 750 .skl,
  284 .scene, 353 `sk*.prop` character props.
- **Skeleton families by prefix**: `sk54_` men (bigby, beast, bluebeard, crane, woodsman, jack,
  georgie, cops...), `sk55_` women (snow, beauty, faith, nerissa, bloodyMary...), `sk56_rachel`,
  `sk15_` short (dee, dum, grendel, mrToad, hollyTroll), `sk18_colin` (pig), `sk35_wolfBigby` (wolf),
  `sk37_crowCrooked` (crow), `sk39_bufkin` (flying monkey). `obj_*`/`fx_*` are props.
- Story scenes are `adv_*.scene` in `Fables10N_data`: 56 of them (barTripTrap, andersenWoodsmanAptDay,
  businessOffice, puddingNPie, crookedManLair, butcherShop, foundry, ...).
- **Faces**: `<face>_phoneme_default_<emotion>A.anm` is the resting face per emotion
  (angry/happy/sad/fear/surprised/worried/... vary per character), `<face>_face_browsUp/browsDown/
  browsFurrow/eyesLook*/blink/squint/eyesWide(_add).anm` are the channels. Face prefix =
  skeleton name minus `skNN_` (`sk54_bigby` → `bigby`).

### Garry's Mod side (all found by reading the VPK trees)
- `garrysmod\garrysmod_dir.vpk`: `models/weapons/v_toolgun.*`, `v_physcannon.*` (GMod version),
  camera model, toolgun screen materials.
- `sourceengine\hl2_misc_dir.vpk`: `v_crowbar/v_pistol/v_smg1/v_shotgun/v_rpg/v_physcannon.mdl`.
- `sourceengine\hl2_sound_misc_dir.vpk`: `sound/items/flashlight1.wav`, weapon fire sounds,
  `weapons/physcannon/hold_loop.wav`, `npc/scanner/scanner_photo1.wav`, `common/wpn_moveselect.wav`.
- HUD font: `garrysmod\resource\HALFLIFE2.ttf` (loose) and `sourceengine\resource\halflife2.ttf`.

### Route
Native hooks (native.md): our `dinput8.dll` proxy in the game folder forwards to the system dinput8 and
loads `TWAU_GMod.asi`. The ASI:
1. hooks D3D9 `EndScene`/`Reset` (ImGui HUD, menus, viewmodels, flashlight overlay);
2. hooks `lua_pcall` (RVA 0x4423D0) to get the game's `lua_State` on the game thread, loads
   `gmod_sandbox.lua` with the game's own `luaL_loadbuffer`, and registers `GMN_*` natives;
3. drives the engine only through its Lua API (no struct offsets), so most of it survives without
   further reverse engineering.
Ragdolls/physics are our own (verlet particles), applied to agents as world transforms. Per-bone ragdoll
needs the skeleton instance layout: open RE item.

### Open items (in order)
1. First in-game run: check the `lua_pcall` hook gets a state and the console (Insert) runs Lua.
2. Fix argument conventions from the console log (`GM.Probe()` dumps what each call returns).
3. Calibrate camera axes (`gm_calibrate` in the console) and units (Bigby's height).
4. Per-bone ragdoll: find the skeleton instance (`SkeletonPose`, `module_skeleton.prop`) in Ghidra.
5. Cross-episode map switching (`SetSubProject`) beyond the current episode.

### Build and offline verification (2026-10-18)
- VS 2022 + CMake, `-A Win32`; ImGui 1.91.9b, MinHook 1.3.3 (no CMakeLists in that tag: sources built
  directly), zlib 1.3.1. Clean build, no warnings. `dinput8.dll` exports all six system exports (x86).
- `twau_assetscan` passes every check on the real installs: 7 VPKs + 48 archives mounted in ~0.5 s;
  94,941 unique names (156,789 entries with repeats); 71 characters (2 quadrupeds, 67 with a walk clip,
  54 with a face rig); 57 scenes over 5 episodes; all 8 viewmodels load with textures, posed from
  `idle01`/`idle`/`draw` frame 0, bind self-check error ≤ 2.7e-5.
- Gotchas found on the way:
  1. The same scene file is in several episodes with different contents (`adv_barTripTrap.scene` in 101,
     102 and 103): a location is (scene, episode).
  2. An archive file name can carry a space (`sk55_snowStandA _turn90LeftToWalk.anm`); never split names on spaces.
  3. Story idles are `sk54_idle_<who>StandA.anm`, not `<who>StandA...` (those are gestures and `_add` layers).
  4. `small` is a macro from `rpcndr.h` once `dinput.h`/`d3d9.h` are in: don't name a variable `small`.
- `um publish check`: PASS (20 files).

## 2026-10-18: first in-game runs (1-9)

Saves backed up first (`um backup`), then `dinput8.dll` + `TWAU_GMod.asi` + `gmod\` installed. Each run:
kill by PID, rebuild, copy, `um win launch --steam 250320`, click "Click anywhere" → PLAY → CONTINUE
(Episode 1 save, `adv_andersenWoodsmanAptNight.scene`), drive the console through `gmod\cmd.txt`.

### Rendering hook: the game uses D3D9Ex and the Steam overlay sits in front
- Runs 1-3 (temporary HAL device from the init thread) failed: device lost, then a heap corruption
  (`c0000374`) from racing the game's own `CreateDevice`. No D3D work off the game thread.
- Runs 4-6: hooking the `Direct3DCreate9` export from `DllMain` saw nothing. Reason, from a `D3DKMTPresent`
  stack: the game calls **`PresentEx`** (`exe+0x1952FE: call [vtable+0x1E4]`, slot 121) on an
  **`IDirect3DDevice9Ex`** made with `Direct3DCreate9Ex`, and `gameoverlayrenderer.dll` (loaded right after
  us) patches `Direct3DCreate9`, `Direct3DCreate9Ex` and `PresentEx`. Its trampolines jump back into d3d9
  past the entry, so any hook placed *before* the overlay's is never reached.
- Working route (run 7 on): from the game thread ~40 ticks after start, make a throwaway **NULLREF**
  device, hook d3d9's `EndScene` with it; the game's next `EndScene` hands over its device; then hook that
  device's `Present`/`PresentEx`/`Reset`/`ResetEx`. Hooking last puts us in front of the overlay.
- D3D9Ex has **no `D3DPOOL_MANAGED`**: viewmodel buffers failed silently (`0 parts`). Default pool for static
  buffers, textures filled in system memory + `UpdateTexture`.

### Lua: several VMs, Telltale opcodes, verified conventions
- The game makes **new Lua VMs** (three at startup, one per load). `GM` is anchored in the registry; a tick
  in a VM without it reloads `gmod_sandbox.lua`, a tick in another globals table gets it put back.
- A native crash inside our tick (run 7: `SceneGetCamera()` with no argument) can't be caught by `pcall`;
  the SEH guard turns the mod off for the session. Guard arguments before calling natives.
- Game scripts are `.lenc` (encrypted). Hooking **`lua_load` (RVA 0x4424F0**, called by `luaL_loadbuffer`)
  dumps them decrypted, as Lua 5.1 bytecode with float numbers (only when `<game>\gmod\dump\` exists; the
  dumps stay out of the repo). Telltale **permutes the opcodes**: aligning the game's
  `string.dump(loadstring(s))` with stock 5.1's for the same snippet gives (0 operand mismatches over 85
  instructions) MOVE 1, LOADK 2, LOADBOOL 3, LOADNIL 4, GETUPVAL 5, GETGLOBAL 6, GETTABLE 7, SETGLOBAL 9,
  SETUPVAL 10, SETTABLE 11, NEWTABLE 12, SELF 14, ADD 16, SUB 17, MUL 18, DIV 19, MOD 20, POW 21, UNM 22,
  NOT 23, LEN 24, CONCAT 25, JMP 27, EQ 28, LT 29, LE 30, TEST 31, TESTSET 32, CALL 33, TAILCALL 34,
  RETURN 36, FORLOOP 37, FORPREP 38, TFORLOOP 39, SETLIST 40, CLOSE 42, CLOSURE 43, VARARG 44.
- Conventions, from the game's own calls and in-game probes:
  - `SceneGetActiveSceneNames()` lists each scene once per layer (8x); `(true)` adds `logic.scene` and `ui_*`.
  - Agents and quaternions are Lua tables: `AgentGetWorldRotQuat` → `{x,y,z,w}`, `AgentSetWorldRotFromQuat`
    takes one. The global `Quaternion()` is not a constructor (returns a number).
  - `AgentSetWorldRot(agent, Vector(pitch, yaw, roll))` in degrees. Y up, agent forward **+Z**, positive
    pitch looks down, right-handed rotation math; units are metres (Bigby's feet at y = 0.012).
  - `AgentGetForwardVec(agent, true)`; `AgentCreate(name, prop, pos, nil, scene, false, false)` then
    `CameraPush(agent)` (as `cam_ui_platform_debug` in the scripts).
  - Pause like the game's own (`Game.lua`): `SceneFind(name)` → `SceneSetTimeScale(scene, 0)`, keep
    `SceneGetTimeScale` for resume. `logic.scene` keeps running; `ControllerSetScene(c, "logic.scene")` puts
    our NPC clips on its clock so spawns animate in a frozen story.
  - `WalkBoxesPosOnWalkBoxes(pos, 0, PathAgentGetWalkBoxes(agent))` → nearest point on the walk boxes.
  - `SceneGetCamera(scene)` needs the scene name: without it, native crash.

### Verified in game (run 9)
F1 freezes the scene (583 agents snapshotted) and pushes our camera; calibration passes (forward +Z, dot
1.000); WASD + mouse look; walk boxes stop the player at walls; GMod HUD, HL2 weapon selector, ammo; physgun,
pistol and shotgun viewmodels with Source textures; Q spawn menu (71 characters, biped/quadruped/bird
filters); spawning a character (Cop Fables C, Faith) with its own walk clip while the story stays frozen;
pistol/shotgun damage, death → rigid ragdoll falls; noclip (V); F3 resumes the scene, destroys spawns and
our camera, story camera back.

### Open items (new)
1. ~~NPCs aren't clamped to walk boxes; bullets ignore level geometry.~~ Fixed in runs 10-11 (below).
2. The game's hover UI (hand icon, "Door" label, tutorial text) still reacts in sandbox mode.
3. Per-bone ragdolls (still one rigid body), flashlight light agent, Face Poser and the map menu: not
   tested in game yet.
4. Automated menu clicks land on the tile hovered before the move (ImGui sees the move one frame late).

## 2026-10-18: walls for NPCs and bullets (runs 10-11)
- No engine raycast reaches level geometry: `AgentAtScreenPos` only picks selectable agents (nil on a bare
  wall). The walk boxes stand in for the floor plan instead: off them (by more than 0.3 m) counts as a wall.
- Adapter: `GM.Snap(x,y,z)` (nearest walk-box point) and `GM.WallDistance(origin, dir, max, floorY, step,
  margin)`, which marches the ray every 0.2 m and returns where it leaves the walk boxes or meets the floor.
  It returns nothing when the shot starts off the walk boxes (noclip), so there are no walls then.
- C++ (`CombatAndRagdollPhysics.cpp`):
  - `TraceWorld` is `Trace` cut at the wall. Bullets, the physgun grab, the toolgun and rockets use it, and
    tracers end at the wall. A target less than 0.6 m past the wall line (someone at a counter or in a
    doorway) still gets hit.
  - NPC steps are snapped back onto the walk boxes, so they slide along walls. A wanderer that stalls in a
    corner picks a new goal. Wander/follow goals and spawn points are snapped too.
  - Thrown rigid bodies bounce off the walk-box edge if they started on the walk boxes.
- New console command `ai [agent] stay|wander|follow` (the E toggle needs a still target within 2.5 m).
- The Woodsman's hallway (`adv_andersenWoodsmanAptNight`) has a single walk-box rectangle, x -3.5..9 and
  z 5.5..7.5. The visible bend beyond it isn't walkable.

### Verified in game
- Faith wandered for 20 s and stayed at z 5.67..7.24, stopping at the wall instead of entering it.
- Open shots: two pistol hits, HP 100 → 76.
- Then the physgun carried her through the wall (it doesn't collide, like GMod's noclip-held props) and
  froze her at (4.97, 3.88), 1.4 m behind the wall. Four pistol shots aimed at her (`lookat`): HP stayed 40.
- One carry left her only 0.36 m behind the wall line, inside the counter tolerance, and those shots hit,
  as designed.
- Rockets and the toolgun use the same trace but weren't fired at a wall in game.

### Notes
- During run 10 the camera weapon got selected with no input from the test script, and one stray photo was
  saved to `<game>\gmod\screenshots\`. The cause isn't known yet; a mouse-wheel tick is the likely one.
- Low obstacles that are off the walk boxes (counters, beds) stop bullets as if they were full walls.

## 2026-10-18: the game's UI, rockets, idles, Face Poser and flashlight (runs 12-16)

### Fixes
- Hover UI: `Reticle_IsEnabled()` was already false in sandbox mode; the labels and markers come from two
  other places.
  - The `ui_*` scenes (`ui_main`, `ui_reticle`, `ui_subtitle`, `ui_overlay`, `ui_inventory`,
    `ui_hud_notification`): `GM.Freeze` hides the visible ones with `SceneHide` and `GM.Unfreeze` shows them
    again.
  - The interaction dots (`ui_<agent>_dot`, `_point`, `_pulse`, made by `ReticleSelection.lua`, whose update
    thread runs on the live `logic.scene`): `ReticleSelection_ShowNearDots(false, "gm_sandbox")` (ref-counted)
    plus `ReticleSelection_HideDots(true)` on F1, and the reverse on F3. F1 also hides the `ui_*` agents of the
    snapshot.
  - Spawns get `AgentSetSelectable(a, false)`: no "Talk To" hover and no dot of their own.
- Rockets went through walls: one step out of the muzzle a rocket is already off the walk boxes, where the
  wall test means "noclip, no walls".
  - A rocket now remembers it was fired from the walk boxes and explodes on the near side once its next
    position would leave them.
  - Blasts test walls too: the kitchen props of the Woodsman's apartment behind the corridor wall are shielded.
- Blast impulse: `Explode` passed a direction scaled by 3, so corpses left at about 36 m/s and flew 40 m,
  sometimes over the corridor wall. Now about 9 m/s. Corpses that leave the walk boxes bounce off the edge
  (pelvis only).
- Logical helpers were hittable: `obj_lookAtBigby`, `obj_matchbookLogical`, `obj_counterStation` got "killed"
  by blasts and caught toolgun shots. The snapshot now records whether the agent has a `D3D Mesh List`
  property, and helpers without one are not hittable.
- T-pose:
  - 17 characters had no idle clip, so an NPC told to stay played nothing. Faith only ships
    `sk55_faithStandSmoke_weightShiftA.anm`, so the search also accepts `<name>Stand*_weightShift*`
    (non-additive), and characters still without one borrow a sibling's idle on the same skeleton.
  - Only the crow and the wolf are left without one.
  - A clip that fails to start is retried next tick.
- Face Poser: Faith "had no face rig". She has no plain `faith_face_blink.anm` or
  `faith_phoneme_default.anm`, only emotion variants. Any `<face>_phoneme_default_*` or `<face>_face_*` clip
  now counts. "Dead" falls back to the first non-additive `<face>_face_blink*` clip.
- Flashlight:
  - `"Light Type"` is an enum object, set by name (the scripts use `'Local Ambient Light'`).
  - The spot cone is a fraction (0.2 / 0.9 on every light in the hallway).
  - A light needs `"Light Turned On"`.
  - Even so, a fresh `module_light.prop` agent lights nothing: TWAU lights only reach their light groups.
    `AgentDuplicate("gm_flashlight", <light_CHAR_* of the scene>)` does work, so the flashlight is a copy of
    the scene's own character light.
- Spawn point: when you faced a wall, the NPC was snapped into your face. The spawn now tries all four sides
  and keeps the roomiest.
- `lookat` aims at a corpse's body on the floor instead of 1.3 m above it.
- The camera-weapon mystery from run 10: one wheel notch up from the physgun selects the Camera (GMod's
  order). The test script sent no wheel events, so it was a real wheel tick on the game window.

### Verified in game
- F1 hid 6 UI scenes and 9 markers; no dots, labels or tutorial text.
- An NPC told to stay right after spawning animates (Faith in her smoking stand).
- Toolgun remover at an NPC behind the wall: nothing happens. At an NPC in the open: she is removed.
- Rocket at an NPC behind the wall: it explodes at the wall and she is shielded. The NPC in the open 2.9 m
  away takes 40 damage.
- A direct rocket hit kills, and the corpse stays in the corridor.
- Flashlight on/off: screen mean brightness 47 → 66 → 47. It lights characters; the floor and walls don't
  react to any duplicated scene light.
- Face Poser on Faith shows every preset and a `blinkhappyb` channel. Angry, Happy and Dead change the face
  (mean pixel difference 5-11 around it, 0 elsewhere). The expressions are subtle; Dead half-closes the eyes.
- Map menu opens with Episode 1's 16 locations and tabs for all five episodes; picking one is not tested yet.
- F3 brings back the UI scenes, markers, story camera and Bigby, and removes the flashlight and spawns.

### Still open
- The second rocket in run 15 never fired: the R reload tap was probably missed. Input is polled with
  `GetAsyncKeyState`, so a tap shorter than a frame can be lost.
- The flashlight can't light environment surfaces.
- The ImGui one-frame click lag.

## 2026-10-18: inverted mouse and A/D, per-bone ragdolls (runs 17-24)

The user reported (after the map menu worked) that moving the mouse right turned the camera left, A walked
right and D walked left, and that corpses fell like mannequins.

### Controls
- Calibration probed screen-right with `CameraGetScreenPosFromWorldPos` and flipped `rightSign` to +1. That
  call reads the camera as it was last frame, so the probe was wrong. Telltale's screen-right is
  -cross(up, forward): `rightSign` is now a constant -1, and the probe only logs.
- Verified: mouse right turns toward the right wall, D strafes right.

### Finding the bones
- RTTI in the exe: `SkeletonInstance` (vtable RVA 0x5f95a4). A `skel` console command scans private
  read-write memory for that vtable; spawning Faith adds one with 110 bones.
- SkeletonInstance: +0x0c the agent's node, +0x14 the skinning matrices (4x4, 64 bytes each), +0x1c bone
  count, +0x24 the bone nodes, +0x4c the frame it was last updated.
- Bone node (vtable RVA 0x5fb3e8, stride 0xd8): +0x10 name hash, +0x18 flags (bit 0: global is valid),
  +0x1c local quaternion (x, y, z, w), +0x2c local position, +0x3c global quaternion, +0x4c global position,
  +0x64 parent, +0x68 first child, +0x70 next sibling. global = parent global * local (Hamilton product,
  checked on a dump).
- `hwbp <addr>` puts a hardware write watch on every thread and reports the writers:
  - RVA 0x1e9520: per bone, applies the animation mixer's result to the local transform (thiscall,
    4 stack args).
  - RVA 0x1eb9f0 (approximately): computes the global transform lazily.
  - RVA 0x3cdb50: builds a matrix from a quaternion and position for skinning.
  - RVA 0x5d050: Node invalidate. It clears the valid bit and recurses into the children.

### The ragdoll
- At death the corpse's skeleton is matched by its root bone's parent: that's the agent's node, at the
  agent's exact position. Matching by "the biggest skeleton nearby" picked a 116-bone character standing
  next to her in one run.
  - The heap scan takes about 1 s, so it runs on a thread when F1 is pressed and after each spawn. A kill
    then takes 31-47 ms.
- One verlet particle per bone. Short links (< 10 cm) merge into their parent's rigid piece:
  - the pelvis takes the hips and the spine base;
  - the chest takes the collarbones;
  - the head takes the face;
  - the palm takes the knuckles.
- Joints between pieces have cone limits in the parent's frame: 30° for the spine and neck, 100° for the
  rest. Knees and elbows also bend one way only: knees back, elbows forward, or the way they were bent at
  death.
- Each frame, each bone's rotation is recovered from the piece it carries: a two-vector frame for pieces,
  the shortest arc for chains. Its local rotation is written into the node and then invalidated. The hook on
  0x1e9520 writes it again after the mixer, so the idle pose can't win.
- Bugs on the way:
  - A one-sided joint-limit push (0.7/0.3) propelled the body 8 m down the corridor and 4 m up.
  - The physics ran at the frame rate (~350 fps here); it now steps at a fixed 120 Hz.
  - Bone 0 was mistaken for a root at the feet; it is the pelvis.
- The physgun pins the pelvis at the grab point and the rest hangs. `lookat` aims at a corpse's pelvis.
- A story character killed in the sandbox gets its death pose back when F3 drops the ragdoll.

### Verified in game
- Two shotgun blasts at Faith: she is thrown back, tumbles legs-over-head and ends on her back with her arms
  and knees bent. The head stays 0.58 m from the pelvis (it folded to 0.07 m before the pieces existed).
- Physgun: she hangs from the beam and falls in a heap when released.
- A rocket at the corpse throws it again.
- F3 returns to the story with no errors in the log.

### Still open
- No self-collision: an arm can pass through the torso.
- No twist limits: forearms and shins keep the twist they died with.
- A hard physgun swing throws the corpse far.

## 2026-10-19: maps of every episode, ragdoll v2 (runs 25-31)

The user asked to keep working on the ragdoll and reported that many maps fail to open, Episode 5 most of all.

### Why maps crashed
- Each episode is a resource set (`Fables101` ... `Fables105`); running Episode 1 enables only `Fables101`
  (plus the always-on `PC105` sets). Disabling the running episode's set crashes the game. `GM.UseEpisode`
  now only enables the target set and its sub-sets (`SubProject_GetResourceSets`) and raises its priority.
- Even then most Episode 2-5 scenes crashed at exe+0xefd98 (`[ecx+0x24]` on a null scene). A vectored
  exception handler (`CrashNote` in `dllmain.cpp`) logs the registers, the ebp caller chain as RVAs and the
  strings the stack points at, for the first three access violations inside the exe. It showed the game's
  own scene script calling the native `SceneGetCamera` (RVA 0x2cafb0, registered at RVA 0x5e4000) with a
  non-string argument before the scene had loaded.
- `LuaBridge` now wraps that native (MinHook + SEH): an access violation inside it returns nil, logs
  `[guard] SceneGetCamera(...) faulted` with a Lua traceback, and the script carries on.
- Sweep of all 41 Episode 2-5 scenes from the console (`map <scene> <episode>`, F1, screenshot, F3): 41 open,
  no crash; the guard fired once.

### Where to stand
- Scenes opened from the map menu often have no Bigby, or park him off the level (`adv_fabletownStreetTile105`
  has him at x 8 and its street at x 397). Walk boxes are not only Bigby's: the agent named after the scene
  carries a `Walk Boxes` property, and every path agent in it shares that table.
- `GM.StartPoint(scene, x, y, z)` takes Bigby's spot, else the story camera's, and moves it onto the nearest
  walk box when it is more than 1.5 m off them. The player's floor height now comes from that start point.
- No walk boxes at all (`adv_barTripTrapExterior104`, `adv_centralParkBridge104`): the player starts at the
  story camera's eye with noclip on.
- Chase scenes keep their level meshes (`<scene>_meshesA/B`) hidden until the script lays the street out; when
  none is visible, F1 shows them (F3 hides them again).
- Still dark: `adv_barTripTrapExterior104` is black even in story view (its lights come from the story), and
  `adv_openArmsLobby` / `adv_introEnding` are stubs with no level (the HUD says so).

### Ragdoll v2
- Self-collision: capsules along every bone longer than 8 cm (11 cm radius for spine and neck, 6 cm for long
  limb bones, 5 cm otherwise); pairs that already touched at death (thigh and pelvis) are skipped. Faith: 24
  capsules, 206 pairs.
- Twist: a chain bone is carried by its parent's rotation, then swung onto its child, so forearms and shins
  turn with the limb instead of keeping the twist they died with.
- Velocity cap of 12 m/s per particle: a hard physgun swing throws the body about 4 m, not across the map.
- Knee and elbow hinges were only built for bones with a single child; Faith's shins and forearms have twist
  helpers, so she had 2 of 4. The hinge now uses the bone's frame member (the farthest one), giving 4.

### Verified in game
- Rocket at Faith (Episode 1 corridor): she ends on her side, one knee bent the right way, arms in front of the
  chest, nothing through the torso. Log: `110 bones, 397 constraints, 46 cones, 4 hinges, 24 capsules / 206
  pairs (32 ms)`.
- Shotgun at point-blank (Episode 5 business office): she drops in a heap; the physgun lifts her by the pelvis
  and a sideways swing lands her 4 m away.
- Maps: Episode 5 street (Open Arms exterior), Crooked Man's lair, business office; Episode 4 park bridge.

### Still open
- Characters spawned into some Episode 5 scenes render as black silhouettes (the scene's light groups don't
  include them).
- Test driving: the game window's client area is now 1066x600 logical; click at its centre (`rect`), and run
  `mdown` in the same call as `focus`.

### GMod physics, viewmodel bob, Face & Finger Poser (2026-10-19)
The goal: corpses that fall limp as in GMod, a physgunned body that still swings (not a dried mummy),
weapon bob while running, and finger and face control.
- Why the body was stiff: a held corpse wasn't simulated at all (only its pelvis was dragged), floor friction
  ran every solver iteration (glue), and every particle weighed the same (the 15 finger bones outweighed the
  chest; face bones made the head a lead ball).
- Masses: bones under 6 cm weigh 50 g, trunk bones `5 + 20 * length` kg, limb bones `12 * length`, the pelvis
  at least 10; a light bone between heavy ones (twist helpers) gets 1 kg so the limb doesn't stretch.
- Shots: momentum (as if into 40 kg) goes to the bones within 35 cm of the hit, by mass: the trunk goes back
  and the arms fly up.
- Floor: Coulomb friction once per step (at most 0.5 x how far the floor pushed), so bodies slide and roll.
- Physgun: grips the heaviest-enough bone nearest the aim ray. That bone and the two that orient its piece
  follow the beam with a stiff spring and turn with the player's yaw (as GMod holds a physics object's
  angles); the rest of the body keeps simulating and hangs off it. Held by the pelvis, Snow folds in a V (head
  and feet 0.6-1.0 m below the grip) and swings +-0.15 m as the beam moves. Without the orientation hold
  she cartwheeled over the grip.
- A test trap: in `adv_andersenWoodsmanAptNight` the story's own Faith stands next to a spawned Faith; the
  physgun took the live one. Test with a character the scene doesn't have (`spawn snow`). The log now says
  what the physgun holds.
- Viewmodel bob: HL2's `CalcViewmodelBob`/`AddViewmodelBob` (vertical cycle 0.45 s, lateral 0.9 s; pitch,
  roll, yaw and offsets). Our speeds map to GMod's (walk 3 m/s = 200 units/s, run 6 m/s = 400, capped 320);
  metres x 39.37 gave 118 units at a walk and a bob too small to see.
- Face & Finger Poser (C): all rest faces (Bigby 23, Faith 12), 11 mouth shapes with an amount slider (the
  `phoneme_<shape>_<emotion>` clip at 50%, speed 0), the channel sliders, and fingers. Hands are found by
  shape; Bigby: 2 hands, 10 fingers. The finger rotation goes on after the mixer in the per-bone hook, and is
  re-based whenever the mixer writes the bone, so it doesn't pile up.
- Verified in game: Snow shot at point-blank falls back with arms flailing; physgun lift and swing (numbers
  above); Bigby angry + mouth AA + a fist (thumb over the fingers); the shotgun bobs and sways at a walk.
- Test driving: mouse sensitivity is 0.12 degrees per mickey, so lifting needs `rel 0 -400`, not `-40`; `hold`
  takes a VK code (`hold 0x57 2000`), not a letter.

### Restore path
Installed: `dinput8.dll`, `TWAU_GMod.asi`, `gmod\` (ini, `lua\`, log, `dump\`) in the game folder. Uninstall:
delete those three. Saves were backed up with `um backup` before the first modded launch. `gmod\dump\`
holds decrypted game scripts: never commit or share it; delete it when the reverse engineering is done.
