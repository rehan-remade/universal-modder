---
kind: game
title: 'First-person camera and WASD on vanilla Kenshi 1.0.68: an OGRE plugin plus signature-scanned game internals'
game: Kenshi
games_also: []
game_version: '1.0.68 x64 (Newland), Steam build 13871665, kenshi_x64.exe md5 8a03c256f0da1555d9cceb939b41530a'
platform: proton
engine: native
route: native-hook
tools:
- clang + lld-link + llvm-dlltool (freestanding x86_64-pc-windows-msvc DLL, no Windows SDK)
- Wine 11.18 (offline harness), Proton 11.0
- objdump, winedump
- KenshiLib headers (reference only)
- python-evdev over /dev/uinput (test input)
anti_cheat: none
status: working
agents:
- Claude Code (Opus 5.5)
- Codex CLI 0.155
humans: []
date: '2026-10-10'
links:
- https://github.com/BFrizzleFoShizzle/KenshiLib
- https://github.com/BFrizzleFoShizzle/RE_Kenshi
tags:
- ogre
- first-person
- camera
- signature-scan
- rtti
- proton
- two-agents
---
# First-person camera and WASD on vanilla Kenshi 1.0.68: an OGRE plugin plus signature-scanned game internals

> A plugin DLL that puts Kenshi's camera at the eyes of the selected character and walks that character with
> W A S D. It is loaded by OGRE itself from `Plugins_x64.cfg`, drives the camera through `OgreMain_x64.dll`
> exports only, and reaches the selected character and the game's own movement code by scanning the 1.0.68
> exe for signatures. It runs in the real game under Proton: toggling, mouse look, walking, running, wall
> collisions and right-click orders from the first-person view were all exercised in a loaded save, with
> positions read back from the plugin's log. Two agents built it: Claude Code did the plugin and the in-game
> tests, Codex did the static reverse-engineering of the exe and a safety review.

## Setup
- Kenshi 1.0.68 x64 from Steam, Linux (CachyOS, Hyprland/Wayland), Proton 11.0-100. No mods, no RE_Kenshi.
- The game (`kenshi_x64.exe`) is native C++ built with MSVC 2010 (`MSVCR100`, `MSVCP100`, `mfc100u`); only
  the editor, `forgotten construction set.exe`, is .NET (older `um scan` builds reported the whole game as
  .NET because of it). For the data/FCS routes, load order and the RE_Kenshi route on 1.0.65, see the
  companion note [`kenshi-1-0-65-native-ogre-recon.md`](kenshi-1-0-65-native-ogre-recon.md), and for
  `.mod` files written from code, the [generated data mods note](kenshi-generated-mods.md); this note
  covers a native plugin on vanilla 1.0.68 without RE_Kenshi.
- Engine DLLs next to the exe: `OgreMain_x64.dll` (OGRE 2.0.0 "Tindalos", 9333 exports, patched by Lo-Fi),
  `RenderSystem_Direct3D11_x64.dll`, `MyGUIEngine_x64.dll`, `OIS64.dll`, PhysX, Havok.
- Saves live in the Proton prefix: `compatdata/233860/pfx/drive_c/users/steamuser/AppData/Local/kenshi/save`
  (the `save` folder in the install only holds templates).
- Build host needs only `clang`, `lld-link`, `llvm-dlltool`. The DLL is freestanding C: import libraries
  for `kernel32`, `user32` and `msvcrt` are generated from `.def` lists, so no Windows SDK or mingw.

## Route and why
`native-hook`, in two layers.

1. **Camera through OGRE only.** OGRE loads every `Plugin=<name>` line of `Plugins_x64.cfg` and calls its
   exported `dllStartPlugin`. That is how RE_Kenshi gets in too. No proxy DLL and no `WINEDLLOVERRIDES`.
   Everything the camera needs is an export of `OgreMain_x64.dll`, resolved with `GetProcAddress` on the
   MSVC-mangled name, so this layer does not depend on the game build.
2. **Character and movement through the exe.** There is no way to know which character is selected, or to walk
   it, from OGRE. The community's map of Kenshi's classes (KenshiLib) has addresses for **1.0.65**; RE_Kenshi
   is based on 1.0.65, and for 1.0.68 its installer creates a compatible executable in the `RE_Kenshi` folder
   (RE_Kenshi README). Instead, the dozen addresses this mod needs were found in the 1.0.68 exe by static
   analysis and are located at load time by byte signature. If any signature fails to match exactly once the
   layer switches itself off and the camera still works.

Not taken: an RE_Kenshi plugin (needs the installer's compatible exe, a Windows GUI installer run through
Proton, and the VS2010 compiler for the STL ABI), and inline hooks (import-table and vtable slots were
enough).

## How the game works (what we had to learn)
**Frame loop.** The exe imports `Root::startRendering` and `add/removeFrameListener`, not `renderOneFrame`:
the game runs inside OGRE frame listeners. Lo-Fi added a virtual to `Ogre::FrameListener`:
`[0] frameStarted [1] frameRenderingQueued [2] framePostAnimationUpdates() [3] frameEnded [4] dtor`.

**Where a camera override has to go.** Inside `SceneManager::_cullPhase01` (vtable slot 86) the order is:
frustum culling, then `updateAllOldAnimations` (poses the *visible* v1 skeletons on worker threads and fires
`framePostAnimationUpdates`), then the render queue. That animation step is Lo-Fi's too: stock ogre-next
`v2-0` only culls in `_cullPhase01`. Bones are only fresh after culling. So the camera is placed twice per
pass: in a vtable hook on `_cullPhase01` before culling (last frame's pose, so the engine culls for the eyes)
and again in `framePostAnimationUpdates` (this frame's pose, so the view does not trail the head).

**Camera rig.** Camera `mainCamera` (local position 0, local orientation 180° about Y) hangs under node
`camera_node`, under node `camera_center` (the orbit pivot), under `Ogre/SceneRoot0`. The scene root is at
minus the world position of the play area (floating origin): render position = world position + root
position. Near clip 5, vertical FOV 45°. The game rewrites the node transforms every frame but never the
camera's own local transform, so overriding the camera's local position and orientation holds, and writing
the saved values back restores the normal camera exactly. Kenshi keeps the pivot position only in the
`camera_center` node: writing that node each frame keeps the pivot (and with it streaming and sound) on
the character after W A S D has broken the game's follow mode.

**Picking reads the OGRE camera.** A right-click while the camera is overridden orders the character to
what the overridden view shows. Point-and-click therefore keeps working in first person for free.

**Characters in the scene.** One character is many `Ogre::Entity` objects sharing a skeleton (body
`human_male.mesh_morph_1`, hair, clothes). Bones are 3ds Max Biped names (`Bip01 Head`, `Bip01 HeadNub`,
`Bip01 Neck`...). Scale is about 10.8 units per metre; Head→HeadNub is 2.165 units. All entities can be
walked without touching STL containers through `SceneManager::_getEntityMemoryManager(SCENE_DYNAMIC)`,
`ObjectMemoryManager::getNumRenderQueues` and `getFirstObjectData`, which fills a struct of parallel
arrays (`mOwner` is the array of `MovableObject*`); filter by the exported `Entity` vtable.

**Hiding the head.** Lo-Fi's `OldBone::setBoneSize` (the body-proportion hook) at 0.01 on `Bip01 Head`
removes head, hair and beard. The game resets bone sizes itself, so set it every frame and restore nothing.

**Mouse.** While Kenshi rotates its camera it holds the cursor still, so cursor deltas are zero. The game's
`OIS::Mouse` can be captured with an import hook on `OIS::InputManager::createInputObject` (type 2). With
MSVC 2010 layouts the mouse state is at object `+0x48`: `X.rel` `+0x58`, `Y.rel` `+0x68`, buttons `+0x80`.

**Game objects in 1.0.68** (RVAs for the md5 above; names from KenshiLib's headers, offsets re-checked in
this binary's code):
- `GameWorld` is a static object at `0x2134110`; `+0x580` is `PlayerInterface*`.
- `PlayerInterface`: selected-set element count `+0x228`, focus `hand` `+0xF0`. `hand::getCharacter`
  (`0x79D410`) turns it into a `Character*`.
- `Character`: `+0x448` AnimationClass (`+0xA8` is the body `Ogre::Entity*`), `+0x640` CharMovement.
  `getPosition` at `0x5CE680`. Live objects are `CharacterHuman` / `CharacterAnimal`.
- `CharMovement::setDirectMovement(const Vector3&, float)` at `0x333300`: sets mode 2 (`+0x378`), stores
  the direction at `+0x38C` and `sqrt(limit)` at `+0x398`. `setMovementMode` at `0x65F110`. Feet position
  `+0xC4`.
- `Character::playerMoveOrderDefault(Building*, RootObject*, const Vector3&)`: vtable slot `0x318`, body
  `0x5D22B0` for all three character classes. It is what a right-click on the ground ends in.
- `CameraClass` has no virtuals and no RTTI name in this exe; `PlayerInterface +0x30` points at it.

**What direct movement does** (measured in the game): the length of the direction vector is a fraction of
the character's own top speed (0.1 → 7 u/s, 0.3 → 22 u/s, 1.0 → 70 u/s for a starting character). The
game turns and animates the character, follows the terrain and stops at walls.

## Build steps
1. Write the DLL as freestanding C for `x86_64-pc-windows-msvc`: `-ffreestanding -fms-extensions
   -mno-stack-arg-probe`, link with `lld-link /dll /noentry /nodefaultlib` against import libraries made by
   `llvm-dlltool` from `.def` files. Define `_fltused`. Export `dllStartPlugin` and `dllStopPlugin`.
2. In `dllStartPlugin`: resolve the OGRE exports by mangled name, `Root::getSingletonPtr`,
   `Root::addFrameListener` with a hand-built vtable in the order above.
3. Patch the exe's import-table slots for `Root::createSceneManager` (capture scene managers and install
   the `_cullPhase01` vtable hook; find the slot by scanning the exported `??_7SceneManager@Ogre@@6B@` for
   the exported function), `Root::destroySceneManager`, and OIS `createInputObject`/`destroyInputObject`.
4. Find `mainCamera` by name in `SceneManager::getCameras()` (a `std::vector`: begin and end pointers at
   `+0`/`+8`). Each pass: bone position in entity space (`OldNode::_getDerivedPosition`) times
   `MovableObject::_getParentNodeFullTransform`, add the eye offset, convert to the camera's parent space,
   `Camera::setPosition` / `setOrientation`.
5. Scan `.text` of the main module for the signatures, derive the addresses, check each lands in the right
   section, run an RTTI self-check, and only then enable W A S D.
6. Copy the DLL next to `kenshi_x64.exe` and append `Plugin=KenshiFP` (CRLF) to `Plugins_x64.cfg`.

## Verification
- **Offline harness, no game process.** A small Wine host loads the game's own `OgreMain_x64.dll`,
  constructs `Ogre::Root` with a `plugins.cfg` naming the plugin (so OGRE loads it the way the game does),
  creates a scene manager, a `mainCamera` and an entity from the game's `human_male.mesh`, and drives the
  plugin through a command file. It proved the string and vector layouts, the listener vtable, hidden
  return pointers, the entity walk, the bone math and unload with hooks removed before the game ever
  loaded the DLL. A second host maps the real exe as an image and runs the same scanner code: twelve
  signatures match once at the expected RVAs.
- **In the game.** Positions and state were read from the plugin's log through a command file the plugin
  polls (`on`, `off`, `yaw`, `walk`, `dump`), with screenshots at each step. Checked: F6 on/off restores the
  camera to the same position; 200 px of mouse travel turns 34.4° at 0.003 rad/count; W, D and Shift+W
  through real key events move the character along the view direction; it holds position on release; it
  stops at a wall; a right-click on the ground walks it along the first-person view (direction error under
  1°); 217 FPS in a town with 645 entities; no fault over about 15 minutes in first person.
- **Final build**, in the game: W and Shift+W through real key events, hold on release, a quickload (F9)
  with the plugin loaded (it re-attaches to the reloaded character), and two scripted recorded takes with
  no fault logged.
- **Not verified:** the plugin's unload path in the real game. Closing the game window ends the process
  without an OGRE shutdown (`dllStopPlugin` is never called), and the quit confirmation in the Esc menu
  ignored synthetic clicks, so unload is covered by the offline harness only. Also not exercised: loading
  a save while first person is on, switching between several squad members, combat, animals, other game
  builds, and running next to RE_Kenshi (or on the compatible exe its installer creates).

## Gotchas
1. **Symptom.** A frame listener written from the OGRE headers that ship with KenshiLib has `frameEnded`
   in the wrong slot. **Cause:** Lo-Fi inserted `framePostAnimationUpdates` at slot 2; the bundled headers
   are stock OGRE 2.0. **Fix:** read the order from the exported vtable `??_7FrameListener@Ogre@@6B@` and
   match slots to exported function addresses.
2. **Symptom.** With the camera set only in `framePostAnimationUpdates`, the view would be right but
   objects go missing at the edges. **Cause:** that callback fires after the frustum culling of the same
   pass. **Fix:** also set it before culling, from a vtable hook on `SceneManager::_cullPhase01`.
3. **Symptom.** The signature scan finds the `Character` vtable, yet every live character is refused.
   **Cause:** live objects are `CharacterHuman` and their animation is `AnimationClassHuman`; an exact
   vtable compare never matches. **Fix:** walk MSVC RTTI (vtable[-1] → complete object locator → class
   hierarchy → base class names) and accept anything derived from the class.
4. **Symptom.** The same RTTI walk fails in the offline scan test. **Cause:** an exe mapped with
   `LoadLibraryEx(..., DONT_RESOLVE_DLL_REFERENCES)` under Wine is not relocated, so `vtable[-1]` holds an
   address for the preferred base. **Fix:** if the pointer is outside the image, translate it with the
   header's `ImageBase`.
5. **Symptom.** Release W and the character sprints back to where it started. **Cause:** leaving
   `MOVE_DIRECTION` with `setMovementMode(0)` hands it back to its previous order. **Fix:** follow the stop
   with `playerMoveOrderDefault` to the position it reached, and only when the stop itself ended direct
   movement, so a newer order is not overwritten.
6. **Symptom.** Mouse look does nothing while the rotate button is held. **Cause:** Kenshi freezes the
   cursor while rotating. **Fix:** read relative motion from the game's OIS mouse object. Related: in two
   recorded takes the view snapped to the ground the instant the button went down (one large relative
   move, cause not pinned down, did not recur); ignoring motion for 100 ms after the press and dropping
   any single frame above 250 counts guards against it.
7. **Symptom.** `setDirectMovement` flips the mode before it writes direction and limit, with no lock, and
   whether `CharMovement::update` can run on another thread then was not established. **Fix:** write
   direction and `sqrt(limit)` into the fields first, then call it; any interleaving reads a consistent
   order. No fault was seen either way.
8. **Symptom.** Booting OGRE headless crashes in `Frustum`, in the mesh loader and in `updateSceneGraph`.
   **Cause:** no `HardwareBufferManager`, no active render system, no `ControllerManager`. **Fix (test
   host only):** construct `DefaultHardwareBufferManager` and `ControllerManager` (both exported), and
   point `Root+0x28` at a stand-in object whose vtable answers `_convertProjectionMatrix` (slot `0x2B8/8`)
   and `getColourVertexElementType` (slot `0x2B0/8`, return 10) and whose `+0x3E0` capabilities report 8
   texture units.
9. **Symptom.** OGRE unloads plugins while the game is still shutting down, leaving patched pointers that
   aim at unmapped code. **Fix:** in `dllStopPlugin` remove the listener and restore every patched slot,
   and pin the DLL (`GetModuleHandleEx` with the pin flag) so a late call still lands on code.
10. **Symptom.** The Kenshi launcher's OK button ignores synthetic clicks under Proton. **Fix:** press
    Enter. More generally on Hyprland: compositor-level synthetic clicks reach Steam's window but not the
    Wine game window; a `/dev/uinput` device does. Steam's "Processing Vulkan shaders" dialog comes back on
    every launch and has to be skipped. Synthetic input lands on whatever has focus: check focus before
    each burst (a human came back mid-test and received the key presses in their browser).
11. **MSVC 2010 x64 layouts used by hand:** `std::string` is 0x28 bytes (16-byte inline buffer or pointer,
    size, capacity, allocator), and a `const std::string&` parameter can be a struct on the stack; member
    functions returning `Vector3` or `Quaternion` by value take a hidden result pointer in RDX after
    `this`; OGRE's `IdString` is 4 bytes in release and travels in a register.

## Assets
None.

## Cost and time
One evening session. Roughly: recon and route 30 min, camera slice with the offline harness 1 h, three Codex
rounds (static RE about 10 min, module about 12 min, review about 10 min) run in the background while the
plugin was built and tested, in-game verification over five launches.

## Open questions
- Attack, block and interact from first person without the cursor (entry points not mapped).
- Always-on mouse look needs the game's cursor hidden or captured while it is active.
- Thread on which `CharMovement::update` runs relative to `frameStarted`.
- Signatures for other builds (GOG 1.0.68, 1.0.65). The camera layer should work there as is.
