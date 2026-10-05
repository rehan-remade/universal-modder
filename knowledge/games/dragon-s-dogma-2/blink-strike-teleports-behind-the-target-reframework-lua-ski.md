---
kind: game
title: Blink Strike teleports behind the target (REFramework Lua skill rework)
game: Dragon's Dogma 2
games_also: []
game_version: dd2.exe 3.2.0.0, Steam 2054970 build 24831693; REFramework rev 0a07faae
platform: windows
engine: re-engine
route: loader-api
tools:
- REFramework (Lua)
- _ScriptCore (SilverEzredes, raycast helper)
anti_cheat: none found by um scan; single-player only
status: released
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-03'
links:
- https://github.com/ntgoten/blink-behind
tags:
- skills
- teleport
- input-hooks
- effects
- sounds
- raycast
---
# Blink Strike teleports behind the target (REFramework Lua skill rework)

> A single REFramework Lua script (`reframework/autorun/BlinkBehind.lua`) changes the Fighter's Blink Strike
> (both levels) so that after a 0.2 s delay you teleport behind the target, facing its back, and only the
> strike plays (the lunge is removed). The effects and sound of Mystic Spearhand's Skydragon's Fangtooth are
> played as departure/arrival cues, and the landing spot is raycast-checked against rocks and walls. Tested
> in the real game by the human over ~20 iterations, with a mod-written debug log as the oracle (v1.4.5 working).

## Setup
- Dragon's Dogma 2, Steam, Windows 11, dd2.exe 3.2.0.0 (Steam build 24831693).
- REFramework already installed (`dinput8.dll`, revision `0a07faae46a6fc1c51cd1699a0cf99a3f9c2679f`).
- The terrain check `require`s `_SharedCore/Functions`, which is **_ScriptCore** by SilverEzredes and
  alphaZomega (v1.2.07). NickCore and UDD2P also depend on it. Without it the script skips the terrain check.
- Other mods present and compatible: UDD2P, NickCore, True Warfarer, Fluffy Mod Manager installs.
  Developed and tested as Warfarer (Blink Strike used with the sword-and-shield weapon set); a final check as a
  pure Fighter also worked, effects included.

## Route and why
`loader-api`: REFramework Lua hooks on the managed (.NET-style) type system. Editing the skill's data
(pak/user files) can't add a teleport, and native hooks weren't needed. **Read the Lua mods that are already
installed before anything else.** Their `sdk.hook` targets (UDD2P's NoUnsheathe, True Warfarer, NickCore's FX
and Position helpers) gave every key type and method name. REFramework's
`reframework/data/usercontent/cache/typecache.json` (8 MB) lists the fields and properties of every type, but
not methods. Querying it with Python was the main way to discover data.

## How the game works (what we had to learn)
- **Skill input:** `app.PlayerInputProcessorDetail.processCustomSkill(app.HumanCustomSkillID, System.UInt64,
  app.LockOnController.Option, bool, bool, bool, app.LocomotionSpeedTypeEnum, bool)`. `args[3]` is the skill
  ID. It's called every frame while a press is buffered; the skill can start when `human.Track.All or
  human.Track.Skill` is true. There's an **outer** overload `processCustomSkill(app.CharacterInput.Action,
  app.HumanCustomSkillID, ...)` that calls this inner one, plus `processCustomSkillReservation(UInt64)`.
- **Skill IDs** (`app.HumanCustomSkillID`, an Int32 enum with 121 values): Fighter 1-12, Blink Strike = 1.
  Both levels share the ID; the level is a separate `HumanCustomSkillLevelNo`. Mystic Spearhand's Skydragon's
  Fangtooth = 76 (`app.Job07Parameter.SkyDiveParameter`, with `WarpRange`), and Dragoon's Foin = 73. Dullahan
  (Nexus 817) uses the unused IDs 102-109 for added skills.
- **Blink Strike data:** `app.CharacterManager.<HumanParam>k__BackingField.JobParam.Job01Parameter.BlinkStrikeParam`.
  `SecBlinkStrikeRush` = 0.750 and `SecBlinkStrikeRushLv2` = 0.950 are the lunge length in seconds. Pawns
  share these values. The action command class is `app.actinter.cmd.job01.BlinkStrike`.
- **Player:** `app.CharacterManager.<ManualPlayer>k__BackingField` (`app.Character`); `.WeaponJob` is the
  held weapon's vocation (1 = Fighter, 7 = Mystic Spearhand) and is useful with Warfarer.
  `get_ManualPlayerPlayer():get_LockOnCtrl()` returns `app.LockOnController` (`HasValidTarget`, `Target` → an
  `app.LockOnTargetWork` with `<Character>`).
- **Enemies:** `app.EnemyManager._EnemyList[i]._Chara`. `Character:get_IsGround()` is false for flyers,
  jumpers and knocked-up enemies. GameObject names: `ch220` humans/bandits, `ch221` saurians,
  `ch222000-003` Harpy / Venin Harpy / Gore Harpy / Succubus, `ch223`, `ch230` and `ch250` were also seen.
- **Moving the player:** `Transform:set_Position/set_Rotation`, then `<CharaController>k__BackingField:warp()`.
  This works **only before the skill's action starts** (see Gotcha 1). Characters face +Z, so a yaw
  quaternion is `(cos(y/2), 0, sin(y/2), 0)` with `y = atan(dx, dz)`.
- **Steering a skill:** set `Character.<TargetAngleCtrl>k__BackingField.Front/Move["<AngleDeg>k__BackingField"]`
  (as NickCore's `position.steer` does) to turn the facing and the intended move direction.
- **Effects:** `via.effect.script.ObjectEffectManager2.requestEffect(EffectID, vec3, Quaternion, GameObject,
  String, WwiseTriggerInfo)` on the player. `EffectID` is a class with `DataContainerIndex`, `ContainerID` and
  `ElementID`. It returns a container; call `finishAll()` on it yourself (Gotcha 6).
- **Sounds:** find the `soundlib.SoundContainer` component's `_TriggerInfoList` entry by `_TriggerId`, then
  `createRequestInfo(...)` and `trigger(...)`. All player sound triggers pass through
  `app.WwiseContainerApp.trigger(soundlib.SoundManager.RequestInfo)`.
- **Mystic Spearhand's effects are usable on a Fighter.** The Job07 effect and sound containers are loaded on
  the player both as Warfarer (sword set) and as a pure Fighter. Skydragon's Fangtooth recorded: takeoff = efx (14,7,10) + sound 1717783091; warp above
  the enemy at about 0.3 s = sound 2823464530, efx (14,7,11) and (13,0,10).
- **Raycasts:** `_ScriptCore`'s `cast_ray(from, to, layer 2, mask 0, radius, 0)` hits the world but not
  characters. Always pass a radius (sphere cast); see Gotcha 8.

## Build steps
1. Back up saves: `um backup create "<Steam>\userdata\<id>\2054970" --name dd2-saves`.
2. Put the script in `reframework/autorun/`. Hook the inner `processCustomSkill`; for skill ID 1, pick a
   target (enemy closest to the camera aim, with the lock-on target only preferred within 30° of the aim;
   skip airborne enemies).
3. On the press: play the departure cue, save the call (the `this` object and its parameters, with the
   `Option` object `add_ref`'d), and return `sdk.PreHookResult.SKIP_ORIGINAL`.
4. After the delay, from `re.on_pre_application_entry("UpdateBehavior")`, call the saved `processCustomSkill`
   yourself. Your own hook sees it, computes a terrain-safe spot behind the target, teleports, shortens
   `SecBlinkStrikeRush*` for 1.5 s, plays the arrival cue, and lets the original run.
5. No target, no safe spot, or the target is airborne: skip, and keep skipping that press for 0.6 s.
6. To find effect and sound IDs for any skill, add a recorder: temporarily hook every
   `ObjectEffectManager2.requestEffect*` overload plus `WwiseContainerApp.trigger`, filter to the player's
   GameObject, timestamp entries relative to the last skill press, and dump to JSON. Use the skill once with
   it on.

## Verification
- **Oracle:** the human tested in game. The script writes its own debug file
  (`reframework/data/BlinkBehind_debug.json`) because REFramework's log never received `log.info` lines after
  startup (Gotcha 2). Each line records what happened (`teleported 1.4m behind of ch221000 (aimed) arrive
  cues 2/2 efx 1/1 snd`, `no target, cancelled`, `no safe spot (0:wall@0.8 30:noground ...)`) with the held
  weapon. Screenshots from the human confirmed the visual bugs (detached body, lingering wisps).
- **Verified (as Warfarer, sword-and-shield set):** single-press teleports, both skill levels, lunge removal,
  Fangtooth cues, terrain shift to a side angle, no vanilla fall-through, no crashes since v0.9. **As a pure
  Fighter:** teleports and cues (`2/2 efx 1/1 snd`) confirmed in a short final test.
- **Not verified:** pawns' Blink Strike during the 1.5 s shortened-rush window; harpies after unblocking
  (v1.4.5); controllers other than the human's gamepad; other game builds.

## Gotchas
1. **Invisible player, body left behind.** Teleporting from `on_frame` after Blink Strike's action had
   started moved the controlled transform but left the body mesh at the old spot. **Cause:** moving the
   character mid-action. **Fix:** only teleport from the input hook, before the original skill call runs.
2. **No mod lines in `re2_framework_log.txt`.** In this setup the file stops at script initialisation, even
   after the game exits. **Fix:** write your own small JSON log, and load and append to it so it survives
   script resets.
3. **A delayed skill only fired when the button was spammed.** Returning `SKIP_ORIGINAL` from
   `processCustomSkill` makes the game drop that press; it isn't re-sent. **Fix:** save the call and replay it
   yourself after the delay.
4. **The game hard-crashed (froze) on every replayed press**, at first blamed on harpies. **Cause:** the
   third parameter `app.LockOnController.Option` is a **class** (typecache `type: 3`); replaying it as a
   32-bit number truncated the pointer. **Fix:** `sdk.to_managed_object(args[5]):add_ref()` and pass the
   object. Check each parameter's type in typecache before replaying a call.
5. **Vanilla skill sneaking in while tapping or turning.** Presses made while the skill couldn't start yet
   were passed through, so the game queued them and fired them later through a path that bypassed the
   decision. **Fix:** decide on every call for that skill ID, including `canStart == false`, and skip when
   there's no target or a cancel cooldown is running.
6. **Borrowed skill effects never disappear** (a teal wisp left on the ground). The original skill switches
   them off; a borrowed one doesn't. **Fix:** keep `requestEffect`'s return value (`add_ref`) and call
   `finishAll()` on it after about 1 s.
7. **Long sprint away from the enemy after a correct teleport.** Blink Strike took its lunge direction from
   the stick. **Fix:** remove the lunge (`SecBlinkStrikeRush*` set to 0.05 s, then restored) and land 1 m
   behind the target's body radius, plus steer `TargetAngleCtrl` at the target for 0.4 s.
8. **Every landing spot rejected ("no ground").** `cast_ray` with radius `nil` uses a `CastRayQuery` that
   doesn't apply the layer filter. **Fix:** always sphere cast (radius 0.05 for ground checks), as NickCore
   does.
9. **Thrown out of bounds behind a flying harpy.** A fallback teleported without terrain checks when there was
   no ground under the target. **Fix:** never teleport unchecked; for airborne targets, skip them.
10. **Recorder results were overwritten.** Ticking "record" again wiped the previous session. **Fix:** append
    sessions. Also note that `json.dump_file` writes an empty Lua table as `null`, so an empty list can't be
    told apart from a missing key on reload. Use booleans for on/off settings.
11. **The lock-on always won.** After a hit, the game keeps the last enemy locked, so turning toward another
    enemy still teleported to the old one. **Fix:** score candidates by angle from the camera aim, plus 1.5°
    per metre, and only keep the lock-on target if it's within 30° of the aim.
12. **False "bypass" detections.** The outer `processCustomSkill(app.CharacterInput.Action, ...)` overload
    calls the inner one, so a detector hooked on it fires on every normal press. It isn't a second input path.

## Assets
None created. The cues reuse the game's own Skydragon's Fangtooth effects and sound, referenced by numeric ID
at runtime; nothing is extracted or shipped. No fal.

## Cost and time
About one afternoon. Roughly 20 install-and-test iterations with the human, each a few minutes.

## Open questions
- Making it a **separate skill with its own ID** in the Fighter list (how Dullahan registers IDs 102-109:
  name and description text, learnability, skill menu entry), instead of replacing Blink Strike.
- An earlier episode where Blink Strike and Dragoon's Foin (same Warfarer button, True Warfarer per-weapon
  sets) both did nothing after load, then recovered. It wasn't reproduced and was probably a skill-set or
  weapon mismatch.
