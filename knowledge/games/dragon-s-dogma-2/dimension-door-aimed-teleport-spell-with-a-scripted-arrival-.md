---
kind: game
title: 'Dimension Door: aimed teleport spell with a scripted arrival camera (REFramework Lua)'
game: Dragon's Dogma 2
games_also: []
game_version: dd2.exe 3.2.0.0, Steam 2054970 build 24831693; REFramework rev 0a07faae (v1.5.9.1+505)
platform: windows
engine: re-engine
route: loader-api
tools:
- REFramework (Lua)
- _ScriptCore (SilverEzredes and alphaZomega, raycast helper)
- il2cpp_dump.json (REFramework SDK dump) for symbol lookup
anti_cheat: none found by um scan; single-player only
status: released
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-05'
links:
- https://github.com/ntgoten/dimension-door
- knowledge/games/dragon-s-dogma-2/blink-strike-teleports-behind-the-target-reframework-lua-ski.md
tags:
- teleport
- camera
- cutscene
- animation
- input-hooks
- gamepad
- effects
- raycast
- fall-damage
---
# Dimension Door: aimed teleport spell with a scripted arrival camera (REFramework Lua)

> One REFramework Lua script (`reframework/autorun/DimensionDoor.lua`) adds a D&D-style Dimension Door to
> Dragon's Dogma 2. A key (B) or gamepad combo (hold the Vocation Action + give Go!) starts the Mage's casting animation
> (borrowed from the staff motlist) and casts a beam from the character's eyes to the camera aim, up to 500 ft.
> A second press opens a door of the Frost Boon shimmer next to the player and a visual one at the target.
> Walking through it plays a scripted arrival: the camera flies over and the character walks out of the far door
> toward the camera. Then the camera swings back behind the player. Tested in the real game by the human over
> ~65 iterations (v0.1 to 0.8.1), with a mod-written JSON debug log plus screenshots as the oracle.

## Setup
- Dragon's Dogma 2, Steam, Windows 11, dd2.exe 3.2.0.0 (Steam build 24831693).
- REFramework installed (`dinput8.dll`, revision `0a07faae`, menu shows v1.5.9.1+505).
- The ray/sphere casts `require("_SharedCore/Functions")`. That is **_ScriptCore** by SilverEzredes and
  alphaZomega; NickCore and UDD2P users already have it. Its `cast_ray(from, to, layer, mask, radius, options)` is
  used throughout.
- Symbols were looked up in REFramework's `il2cpp_dump.json`, using a small script that prints one type's members.
- Builds on the earlier note [Blink Behind](blink-strike-teleports-behind-the-target-reframework-lua-ski.md)
  (effects by ID, sounds, `play_efx` / `play_sound` helpers).

## Route and why
`loader-api`: a REFramework Lua script, with no game files changed. Everything visible is the game's own:
- Fangtooth effects and sounds (by EffectID and trigger ID);
- the Frost Boon shimmer from the held weapon's own effect list;
- the Mage casting animations, loaded as a dynamic motion bank.

Considered and dropped:
- `TimeSkipManager.requestPlayerWarp`: always fades to black.
- A custom glowing-panel mesh: not needed.
- A drawn laser overlay: the user found it jarring.

## How the game works (what we had to learn)
- **Teleporting a character: `app.Character.warp(via.vec3, via.Quaternion, app.CharacterWarpOption)`** with the
  static `app.CharacterWarpOption.ResetPosRotContext`.
  - Setting the transform directly (plus `CharaController.warp()`) gets undone. The character keeps a position
    history (`CharacterPosRotContext`) that restores the old spot: the body mesh arrives and the character and
    camera stay behind.
  - We call warp from a post-hook of `app.UserInputManager.updateInput` (the game's input processing step), then
    hold the position for 8 frames.
- **`TimeSkipManager.requestPlayerWarp(h, m, day, via.Position, quat, Action, bool, bool)`** is a full fast-travel
  warp: fade to black and a reload around the target. Its position is the **universal** `via.Position`
  (`transform:get_UniversalPosition()`), not `get_Position()`. Passing a local position sent the player
  somewhere else, into a low-LOD empty world.
- **Cameras after a long jump:** they keep looking at the old spot unless told.
  - Call `CameraManager.setCurrentCameraReset(ResetOption)`.
  - On every `app.CameraControllerBase` in the scene, set `IsFirstProcAfterWarp = true` and call
    `onWarpTarget()`.
  - `ResetOption` bits (low 32 bits of the dump defaults): DisableManualControl 1, ImmediateTerrainCorrection 2,
    ForceApply 4.
- **Overriding the camera for a fly-by:** `app.MainCameraController` (`_Role` 0 = main) positions the view through
  its **camera joint** (`_CameraJoint`) from its `_Position` / `_Rotation`.
  - Write your pose with `_CameraJoint:set_Position / set_Rotation` in a post-hook of
    `MainCameraController.lateUpdate`. The game writes the joint every frame, so control comes back by itself
    when you stop.
  - Writing the camera GameObject's transform instead froze the rendered view for good. The minimap and pawn
    name tags (which use the controller's pose) kept moving with the mouse, but the picture didn't.
  - Writing the controller's `_Position` before `lateUpdate` does nothing: the game recomputes it.
  - In the post-hook, `mainCam._Position / _Rotation` is the game's own pose for that frame. It's useful for
    blending the camera back.
- **Locking the player's input without the game's cutscene lock:** in the same `updateInput` post-hook, compare
  the `app.UserInput` argument (`args[3]`) with `player:get_Input()` **by `get_address()`**. Two Lua handles to the
  same object are not `==`. Then zero `ButtonOnFlags / ButtonTriggerFlags / ButtonReleaseFlags /
  ButtonRepeatFlags` and call `setAxisL / setAxisR`.
- **Scripted walk:** inject the left stick there too. It's relative to the game's own camera: x = right,
  y = forward, from `mainCam._Rotation`. A self-check flips the stick if the character moves away from the
  target.
- **Gamepad:** raw pad from `via.hid.GamePad.get_MergedDevice():get_Button()`. `via.hid.GamePadButton` values:
  - d-pad: LUp 1, LDown 2, LLeft 4, LRight 8;
  - shoulders: LTrigTop (L1) 256, RTrigTop (R1) 1024, LTrigBottom 512, RTrigBottom 2048.
- **The player's action flags:** `ButtonOnFlags / ButtonTriggerFlags / ButtonReleaseFlags / ButtonRepeatFlags`
  (UInt64) on the player's `app.UserInput` have **one bit per `app.CharacterInput.Action` value** (bit = 1 << index;
  take the low 32 bits of the dump's enum defaults).
  - Examples: AttackS 1, AttackL 2, Jump 3, Dash 4, Grab 5, Interact 6, Skill1-4 7-10, Shift1 14, Shift2 15.
  - The pawn commands are Come 17, Go 18, Help 19 and Wait 20.
  - JobSpecialAction 29 = the "Vocation Action". Other values: Sheathe 36, Draw 37, Lantern 38, RecoverHpItem 39,
    RecoverStaminaItem 40, Walk 60.
  - So a combo can follow the player's own button mapping: "Vocation Action held + Go! triggered" is R1 + d-pad up
    on default controls, wherever the player rebound it. Clearing bits 17-20 while the Vocation Action is held
    turns the d-pad into a free shortcut layer.
  - Raw pad as an alternative: `via.hid.GamePad.get_MergedDevice():get_Button()` (`via.hid.GamePadButton`:
    LUp 1, LDown 2, LLeft 4, LRight 8, LTrigTop/L1 256, RTrigTop/R1 1024). But physical buttons ignore the
    player's remapping.
- **Animations from another vocation:** the player's motlists are
  `animation/ch/ch00/motlist/ch00_00X_com|atk.motlist`.
  - 006 is the staff (Mage); 005 has a charge set too.
  - Load one as a dynamic bank: `sdk.create_resource("via.motion.MotionListResource", path)` →
    `create_holder` → `via.motion.DynamicMotionBank` with `set_OverwriteBankID(true)` and `set_BankID(id)` →
    `Motion:setDynamicMotionBank`. This is the same method as _ScriptCore and NickCore's `add_dynamic_motionbank`.
  - Then play a motion on layer 0 with `changeMotion(bank, motion, frame, interp, 1, 1)`.
  - Motion names can be listed at runtime: `Motion:getMotionInfo(bank, id, via.motion.MotionInfo)` →
    `MotionInfo.get_MotionName / get_MotionEndFrame`, scanning ids 0-3000.
  - The Mage's shared cast set in `ch00_006_atk`:
    - 700 `attackspelling_start` (60 f);
    - 701 / 702 `attackspelling_chant1/2` (230 / 180 f, loopable);
    - 750-753 `spellstock_release_*` (45 f);
    - per-spell `*_ready`, `*_ready_loop` and `*_activate` sets, e.g. firestorm 1021/1022, frostspike 1102-1104.
- **Keeping your motion on screen:** in some idle states the player's `via.motion.MotionFsm2` rewrites layer 0
  every frame. Pause it while the scripted animation plays and always unpause on end, cancel, error and script
  reset. It's a `via.behaviortree.BehaviorTree`, so `set_Paused(true / false)`.
- **Fall damage:** `app.Character.<FallInfo>k__BackingField` is an `app.FallInfoHolder` (`HighestPositionOnAir`,
  `BaseFallHeight`). Right after the teleport, call `resetBaseHeight(via.Position)` and
  `set_HighestPositionOnAir(via.Position)` with the arrival position, plus `resetFallHeight()`, for ~12 frames.
  The height you jumped from then doesn't count; later falls do.
- **Collision layers for casts** (via `_ScriptCore`'s `cast_ray`):
  - Layer 2 is open-world terrain, and it answers **sphere** casts but not thin rays. Town ground
    (`EnvRoot_TWN01_01`, layers 2/23/24) answers thin rays, but some spots don't answer spheres.
  - Layer 0 holds big invisible quest volumes (`Resource_qu...`) around the player.
  - Use `options = 1` (all contacts) and skip by GameObject name: `^Resource_`, `^ch%d` (characters), Area,
    Trigger, Sensor, Volume, Sound, Wwise, Event.
  - `_ScriptCore`'s plain-ray path *does* use the layer you pass. It shares the filter object with the sphere path.
- **Effects:**
  - The Frost Boon shimmer is `EffectID{-1, 0, 25}` on the **held weapon's** `ObjectEffectManager2`. Get it from
    `player._WeaponElementController:getWeapon(false):get_GameObject()`.
  - It loops until finished. It can be attached to a bare GameObject you create, so you can place it anywhere:
    `requestEffect(EffectID, GameObject, Int32, WwiseTriggerInfo)`.
  - Scaling that anchor object makes the effect invisible.
  - Fangtooth's spark `{14, 7, 11}` has its colour baked in. The only colour control (`EffectPlayer.Color`)
    drives a screen-wide layer, so recolouring it pulses the whole screen.
  - Requesting the same borrowed effect many times along a line showed only one instance (pooling, apparently).

## Build steps
1. Install REFramework and _ScriptCore.
2. Drop `DimensionDoor.lua` into `reframework/autorun/`. The source and release zip are at
   https://github.com/ntgoten/dimension-door.
3. In game: Insert → Script Generated UI → Dimension Door. Settings are saved to
   `reframework/data/DimensionDoor.json`, and a rolling log goes to `DimensionDoor_debug.json`.

## Verification
- **Oracle:** the human played every build. The script writes a 60-entry JSON event log (beam lock distance,
  hit / open air, landing corrections, cast start / skip, learned pad bits, errors). We read the log after each
  test, alongside the human's screenshots and descriptions.
- **Verified in game:**
  - aiming and locking the target;
  - casting animation, after the FSM pause;
  - door crossing and teleport (`Character.warp`);
  - camera fly-out and hand-back (joint write);
  - walk-out direction;
  - Vocation Action + Go! with pawn commands blocked (on a remapped pad);
  - doors floating at roof edges;
  - no fall damage after a downward jump.
- **Not verified:** carrying another character through the door; online / pawn-share side effects; every terrain
  type. The last tested build still got one user report of "probably good, not sure" on rocky ground.

## Gotchas
1. **Body arrived, but the camera and control stayed behind.** **Cause:** a direct transform set is undone by the
   character's position history (PosRotContext); only the mesh moved. **Fix:**
   `Character.warp(vec3, quat, CharacterWarpOption.ResetPosRotContext)` from the input-processing hook.
2. **The game warp blacked out and dropped us in an empty, low-LOD world.** **Cause:**
   `requestPlayerWarp` wants the universal position. **Fix:** add `UniversalPosition - Position` of the player,
   or don't use it for short hops (it always fades).
3. **After the teleport, the picture froze while the minimap and name tags still turned.** **Cause:** our fly-by
   wrote the camera GameObject's transform, but the view is driven by `MainCameraController._CameraJoint`.
   **Fix:** write the joint after `lateUpdate`. Also check your test switches: ours didn't really disable the
   flight, which wasted two rounds.
4. **The camera didn't follow a 20 m+ jump.** **Fix:** `setCurrentCameraReset(6)` plus `onWarpTarget()` and
   `IsFirstProcAfterWarp` on every `app.CameraControllerBase`.
5. **The game's CutScene input lock (`UserInputManager.requestDisable(1, 7)`) left the character broken.**
   **Fix:** do your own lock by zeroing the player's `UserInput` in the `updateInput` post-hook.
6. **The injected walk did nothing.** **Cause:** `curInput == player:get_Input()` is always false for two handles
   to the same object. **Fix:** compare `get_address()`.
7. **The walk-out went backwards, then forwards again later.** **Cause:** the stick's y axis is relative to
   whichever camera you take the rotation from. We inverted it when that was our overridden shot, then forgot
   once we switched to the game's camera. **Fix:** derive it from the game's own pose, plus a runtime flip check.
8. **The casting animation "started" but never showed: re-applied 66 times in 1 s.** **Cause:** `MotionFsm2`
   rewrites layer 0 every frame in fresh idle. It worked after walking a bit. **Fix:** `set_Paused(true)` on the
   player's `MotionFsm2` while casting, always unpaused afterwards.
9. **The marker or beam stopped at 0 ft / found "no ground", in town and outdoors.** **Causes:**
   - an overhead check that started 0.3 m above a slope hit the slope itself;
   - only one cast flavour was used (rays miss terrain, spheres miss some town ground);
   - `options = 0` stopped at the first contact, which was the quest volume we stood in.

   **Fix:** try both flavours on layers {2, 23, 24}, use `options = 1`, and skip volumes by name.
10. **Aiming outdoors always ended "500 ft, open air".** **Cause:** a rays-only optimisation; terrain doesn't
    answer rays. **Fix:** always run one sphere cast on layer 2 too.
11. **Under the map, twice.**
    - The thin ray went through a hill (terrain ignores rays) and hit something behind it. The sphere pass only
      ran when rays found nothing. **Fix:** always run both and take the nearer hit.
    - Safety net: a mid-air landing with any surface within 80 m above it is moved up onto that surface.
12. **Landed inside a rock.** **Cause:** the beam hit the rock's side, and the ground search found the terrain
    continuing *inside* the rock: casts that start inside a mesh don't see it. **Fix:** a landing must be reachable.
    There must be a clear line from the beam's open-air path to chest height, plus head room. Otherwise step
    back along the beam (0.6 / 1.5 / 3 / 5 / 8 m), or fizzle.
13. **The head was above ground, then the character sank through it after a long jump.** **Cause (likely):** the
    ground collision at the destination isn't loaded yet. **Fix:** for 2 s, if the character drops 0.6 m below
    the ground height measured at lock time, put them back on top.
14. **Fall damage after jumping into the door and arriving lower.** **Fix:** reset `FallInfoHolder` to the
    arrival position for a few frames.
15. **The door sank onto a lower roof / looked lifted in the air.** **Causes:** the ground search reached 4 m
    down; the shimmer plumes rise ~1 m above their spawn point. **Fix:** keep the door at feet height (snap
    within 0.5 m only), and shift the look by -0.4 m. A shorter frame looked bad.
16. **The target light blinded up close and was heavy; scaled effects vanished.** **Fix:** sparks alone are
    visible far away even at night. No light, no scaling.
17. **The recoloured target pulsed the whole screen red.** **Cause:** the spark's colour lives in its texture;
    `EffectPlayer.Color` drives a screen-wide layer. **Fix:** don't recolour that effect.
18. **Once you zero the player's input every frame (your own lock), a held button is only reported on its first
    frame.** Example: hold the Vocation Action, then press Go! during the lock; the combo never fires. **Fix:**
    track "held" yourself, from the On/Trigger bit until the Release bit (which is still reported), with a
    timeout as a safety net. While everything is blocked anyway, accept Go! alone.
19. **The RE Asset Library pak extractor found nothing**, not even a catalog mesh path, through
    `extractFilesFromPakCache` from Blender's Python. Unresolved. Listing motion names at runtime, through a
    dynamic bank and `getMotionInfo`, was simpler anyway.

## Assets
None made. All visuals and sounds are the game's own, used by ID:
- Fangtooth effects 14/7/10, 14/7/11 and 13/0/10;
- sounds 1717783091 and 2823464530;
- the Frost Boon shimmer -1/0/25 on the held weapon;
- Mage motions 700 / 701 / 750 from `ch00_006_atk.motlist`.

## Cost and time
One long session over two days, ~60 builds. The camera (gotchas 3-5) and ground detection (9-13) took the most
rounds.

## Open questions
- A solid glowing panel inside the door (the user's idea): needs either a flat emissive mesh or a sheet-like game
  effect.
- Whether carried characters reliably come along through `Character.warp`.
- Why the RE Asset Library pak cache lookup failed in a standalone run.
- A water-surface layer, for landing on water. A runtime layer probe was written but never got a result.
