---
kind: technique
title: "Custom races and creatures in Bannerlord at runtime: the humanoid path, quadruped mounts and hidden-rider creatures"
status: in-progress
game: "Mount & Blade II: Bannerlord"
games_also: ["Borderlands 2"]
game_version: "v1.4.8.119303 (Steam, Windows 11); client TaleWorlds.Native.dll 14,185,944 bytes, PE timestamp 0x6a732505 (all crash offsets here are for this build); Bannerlord.Harmony 2.4.2"
platform: windows
engine: unknown
route: loader-api
tools: ["Bannerlord module system (ModuleData XML + XSLT, C# net472 SubModule)", "Bannerlord.Harmony 2.4.2", "Python 3.10 + numpy (own .tpac/.rdc writers)", "Blender 4.2 headless", "Ghidra 12.1.4 headless", "ilspycmd 9.1"]
agents: ["Claude Code (Opus 5.5)", "Claude Code subagents (Sonnet 5.5)"]
humans: ["@theartur2000"]
date: 2026-10-07
links: []
tags: [bannerlord, custom-race, custom-skeleton, animation, action-sets, monsters, quadruped, mounts, creatures, jockey-pair, flying, humanoid-path]
---

# Custom races and creatures in Bannerlord at runtime: the humanoid path, quadruped mounts and hidden-rider creatures

> What it takes to make Bannerlord accept non-human bodies that move, fight and ride: races on their own skeletons (the
> humanoid path), creatures as mounts (the quadruped path), why a creature cannot be a soldier on its own and the hidden-rider
> workaround, flying creatures, and the animation rules that decide whether any of it moves. Learned while porting Borderlands 2
> ([`../games/mount-and-blade-ii-bannerlord/bannerlord-borderlands-2-total-conversion.md`](../games/mount-and-blade-ii-bannerlord/bannerlord-borderlands-2-total-conversion.md));
> binary formats are in [`editor-free-bannerlord-assets.md`](editor-free-bannerlord-assets.md).

Evidence tags: **[V]** seen in the running game or by a byte-exact round trip, **[M]** measured, **[S]** static analysis only,
**[H]** hypothesis. "TN n" = gotcha n of the asset note. Offsets are search handles for the client build above.

## When to use it
- You want a non-human body in Bannerlord that walks, fights or can be ridden: a monster, a robot, an animal, a boss.
- Your custom race spawns but slides, T-poses, never hits, or crashes seconds after it appears.
- You want a creature as a mount or as a fighter on its own, or something that flies (agents cannot).

## How
**Races and animation**
- A **race** is a skin entry (skeleton, body/face/hair meshes, deform keys) mapped to a `Monster` (bone fields, capsules, flags)
  whose action set, found by the name `as_<monster>[_female]<suffix>`, names the skeleton and the clip for every action. The agent's
  VISUAL skeleton comes from the ACTION SET's `skeleton=`, not the skin's; UI paths that pass no action set (character-creation
  preview, `BasicCharacterTableau`) use set 0, the human set, which twists a custom body and reads past the human bone array.
- **Humanoid path** (everything that fights as a troop): a copy of the human race with `skeleton=<own>`, `body_meta_mesh=<own mesh>`,
  every other body slot a one-triangle "none" mesh, `uses_stitching="false"`; hair/beard entries nameless but the ENTRY COUNTS kept;
  empty `<deform_keys />`; a placeholder face mesh with a submesh; non-empty colour lists. A monster with ALL ~55 bone fields named
  (omitted ones inherit the BASE monster's INDEX), plus `<id>_settlement`, `_settlement_slow`, `_settlement_fast`, `_child` variants;
  keep `IsHumanoid` (AI, morale, deployment read it). An action set per suffix the code asks for (`_warrior`, `_facegen`, `_map`,
  `_poses`, `_villager`, `_lord`, tavern and carry sets: **88 `as_human_*` sets, 7,649 actions**); `MBGlobals.GetActionSet` THROWS when
  one is missing (about 35 call sites of `FaceGen.GetMonsterWithSuffix`). A clip must exist for EVERY action type of the human set
  or the engine plays nothing; races copy all human sets and re-point only actions that have a clip.
- **28 biped bone order:** see "What the engine assumes about a human" in the asset note (first 28 bones in human biped order,
  extras after 27). Hero rigs of 90 to 122 bones are 27 body + face + finger bones; dropping face and fingers leaves 28 to 36.
- **Movement.** `movement_sets.xml` has 18 slot actions (idle, forward, backward, strafes, rotate, adders); the engine caches
  per-direction speed = distance per cycle / duration. Native locomotion clips are authored IN PLACE; speed comes from the agent and the
  clip's `bip_mov_ik` distance block, not the root channel. Recipe: one FBX per movement sequence, cycles in place, `bip_mov_ik` =
  metres per cycle measured from the planted foot.
- **Key units:** see "Clip record" in the asset note. Measure the key rate per rig, or hit windows land on the wind-up instead of the
  contact frame (gotcha 3).
- **Layers.** Channel 0 is movement, channel 1 the upper body (ready, aim, release, reload, defend); the skeleton's per-bone
  `lowerbody` flag decides which bones channel 0 keeps. Never set `enforce_*` flags on ready, release, reload or defend clips.
- **Combat clips** are written in copy mode from the Native clip of the same action. The hit window is `combat_parameters.xml`
  `collision_check_starting_percent` .. `ending_percent` of clip progress (parser default start 1.0 = empty window, so a plain clip never
  hits; e.g. 1h overswing 0.38 to 0.50). Ranged releases need step points (launch: bow 0.0, javelin 0.25); equip/unequip use the 4th
  step point as the switch progress and `agent_wield_update` needs channel 1 to play an equip/unequip action (type 33) until then or
  it logs "Weapon wield interrupted". Ready clips keep the `keep` flag. Keep Native durations to keep AI timing.
- **Hit geometry.** A chain of segments from shoulder to weapon bone, then along the weapon. A hit by an arm segment is
  `HitWithAnotherBone` (bounced, damage multiplied by `SwingHitWithArmDamageMultiplier`). Blow magnitude uses `AttackProgress`
  through `SpeedGraphFunction` (`managed_core_parameters.xml`) times weapon speed; bone velocity is not used.
- **Prebaked animations:** custom clips have none and off-screen agents' skeletons are not ticked, so
  `AgentVisuals.GetBoneEntitialFrame` returns stale or NaN frames: call `Skeleton.ForceUpdateBoneFrames` first.
- **Loop flags.** Conversation, inventory and pose "start" clips run once and rely on `continue_with` and the loop clip's `cyclic`
  flag; battles hide a missing one because movement re-issues idle.
- **Face builder:** see "Skin and face" in the asset note and TN 13. In addition, hair and beard lists are bound-checked (face,
  mouth, eyebrow and tattoo lists are not); put the fixed head in `body_meta_mesh`. `FaceGenVM` throws in randomise for a female skin
  with 0 beards.
- Tracks carry rotations per bone plus root translation only: non-root bone translations never animate; design rigs around rotations.
- **Retargeting a foreign body onto Bannerlord joints:** fit each bone with an affine, move vertices by linear blend skinning. BL2 is
  right-handed, forward +X, up +Z; Bannerlord agents face +Y, left at -X. Native clips cannot drive a foreign skeleton (bind rotations
  differ by a median 7 to 28 degrees).

**Creatures**
- A **quadruped path** exists and is safe only for mounts: an action set with `movement_system="quadrupedal"` and its own `skeleton=`.
  Rider and mount poses come from `monster_usage_sets.xml` (Native: human, horse, camel, animals). All monsters on one action set must
  share `num_paces` and `monster_usage`; the pace table is built once PER ACTION SET by the first agent using it.
- **Recipe (own-skeleton mounts):** canonical ids; an action set with the Native horse's action types; your own usage set (a copy of
  the horse's rows with a new id) as a new file under `soln_monster_usage_sets`; rider rows (`mount_id=<new usage id>`) appended to
  Native's `human` set by a same-named `.xslt`; gait clips with `quad_movement` as the FIRST of at most two parameter entries. Base the
  creature on the HORSE when its back is at horse height: rider clips are absolute from the mount origin and `rider_sit_bone` does not
  lift or lower the rider.
- **Mount monster fields:** `rider_sit_bone` a real back bone; `front_/back_bone_to_detect_ground_slope_index` are raw bone NUMBERS
  (signed byte), not names; `body_rotation_reference_bone` must not be the root; `fall_blow_damage_bone` below 28; a unique `family_type`
  keeps horse harnesses off. `Mission.SpawnAgent` mounts any agent with a rideable horse in slot 10.
- **Riderless creature troops are unsafe.** Native builds a non-humanoid agent only from a horse item; a character agent on a quadruped
  monster runs character-only steps (weapon component, facial controller, voices, formation, the AI target scorer reading the TARGET's
  weapon component). Guards held for most sites but the AI target-scorer site still crashed, so creatures are **jockey pairs**: a human
  cavalry NPC (no `race=`) rides an invisible-rider mount whose item carries the creature's monster and skin metamesh.
- **Jockey pair details.** Hide the rider with `AgentVisuals.SetVisible(false)` at build and EVERY tick; health 100000, healed inside
  `OnAgentHit`; blows on the rider are redirected to the mount one tick later in the attacker's name; the rider's own swings are dropped
  (`IsDamageIgnored`); no dismount by blow; mount and rider die together; scale, health and speed live on the MOUNT. The creature attacks
  with a scripted blow in the rider's name shortly after the mount plays a kick clip. The mount agent has no team (use the rider's).
- **Creature AI.** Native AI gives non-humanoid agents no attacks and native cavalry AI charges through and wheels away, so a boss mount is
  in reach a fraction of the time. A hold-and-bite driver (`Agent.SetScriptedPosition` with `AIScriptedFrameFlags`) fixes it.
- **Humanoid-path creatures** (fight as team members or never walk): `monster_usage="human"`, bipedal sets, at most 64 bones with the first
  28 in biped order; bosses that never walk play attacks through spare action slots and are pinned.
- **Flight.** An agent cannot be held in the air: `TeleportToPosition` every tick is pulled back down. Fly a separate `GameEntity`.

## Gotchas
1. **Soldiers slide with frozen feet, later drift and snap each cycle.** See TN 6.
2. **Every animation plays the same death pose.** See TN 5.
3. **Symptom.** Swings land on the wrong part of the arc. **Cause:** clip ranges are in stored keys and rigs store different rates (12.548 keys/s
   for one bake, one per frame for others). **Fix:** measure the key rate per rig and fit ranges in keys. [V]
4. **Symptom.** Conversation, inventory and party-screen figures fall to the reference pose after 2 to 3 s. **Cause:** start clips run once; loop
   clips lacked `cyclic` and the start clip lacked `continue_with`. **Fix:** looping copies with Native's stock flags and follow-ups. [V]
5. **AI troops with new combat clips deal no damage; troops swap weapons back ("Weapon wield interrupted").** See TN 21.
6. **Managed throw in the campaign UI, map or town code for a custom race.** See TN 19 (88 suffix sets and four monster variants).
7. **Holstered items on the wrong bone, UI code reading past the bone array, hit chain misaligned.** See TN 16.
8. **A Native clip on a custom skeleton plays garbage or crashes.** See TN 22.
9. **Symptom.** Melee does about 1 damage per swing; blows register at attack progress 0.00 to 0.04 or with the back of the weapon. **Cause:** the
   race builder gave every race the CROSSBOW AIM frame on the weapon bone, so the blade swung sideways (blade reach 0.59 of Native). **Fix:** a per-rig
   grip rotation on the weapon bone searched over the melee release clips (reach 0.99); recompute landed blows with the engine's `ComputeRawDamage` if
   the swings move the weapon slower in the damage window. Cover every monster that shares the skeleton. [V]
10. **Symptom.** AI never fires although it has line of sight; barely shoots. **Cause:** the AI shoot check traces from the eye (head-look bone frame +
    eye offset, moved back 0.45 x scale) and the eye sat inside the model's own mesh; the aim pose held the gun beside the body. **Fix:** eye at standing
    height, 5 cm in front of the front surface; a torso-only aim layer with the gun in front at chest height. [V]
11. **Riders float 0.45 m above a custom mount's back with straight legs.** See TN 24.
12. **Gait crash at creature spawn in an own quadruped set.** See TN 9, and TN 8 for the canonical-id cause.
13. **Symptom.** A player cannot switch from a heavy gun to melee on a creature mount; a mounted player cannot reload. **Cause:** native refuses the
    animated switch AWAY from a crossbow-class gun on a mount with `FamilyType` of 10 or more (182 of 210 refused; on foot 0), cause unknown; the
    generator wrote `CantReloadOnHorseback` on guns copied from the heavy crossbow usage. **Fix:** Harmony prefixes on `Agent.TryToWieldWeaponInSlot` and
    `WieldNextWeapon` force Instant for those riders (210 of 210); stop writing the flag where a mounted reload clip exists. [V]
14. **Symptom.** Boss rider redirect does nothing; hidden agents reappear. **Cause:** an Invulnerable victim drops every blow before any hit event
    exists; the engine re-shows agent visuals every tick. **Fix:** make the rider mortal with 100000 health and heal inside `OnAgentHit` (runs before the
    death check), redirect to the mount next tick; call `SetVisible(false)` every tick. [V]
15. **Symptom.** Map figure, encounter conversation and loot screen of a creature party show the hidden human jockey; a bandit-talk surrender is offered.
    **Cause:** the party leader is the human rider troop. **Fix:** a Harmony prefix on `PlayerEncounter.DoMeetingInternal` taking the engine's own army path
    (an "Attack / Leave" menu) and a postfix on `CharacterImageIdentifierVM` showing the mount item picture. [V]
16. **Symptom.** A flying boss made by teleporting the real agent every tick falls back to the ground. **Cause:** the engine pulls agents down. **Fix:**
    park the real agent (hidden every tick, AI off, engine blows ignored, following the flyer's ground shadow so enemy AI gathers under it) and fly a
    `GameEntity` built from the creature's skinned metamesh and skeleton along a precomputed arc to a navmesh landing spot; swap back in the same tick;
    far entities `DoNotTick` with hand ticks; fail-safe to a ground boss on any exception. Enemy AI aims at the parked agent's shadow, so count bullets at
    an airborne flyer as aimed. [V]
17. **Symptom.** Small troops are missed by the AI and barely hit. **Cause:** scale 0.45 to 0.5 gives tiny hit capsules. **Fix:** never scale
    below 0.65; for the capsule refit see TN 29. [offline measurement]

## Seen in
- [Borderlands 2 as a Bannerlord total conversion](../games/mount-and-blade-ii-bannerlord/bannerlord-borderlands-2-total-conversion.md), where every item here was learned.
- [Editor-free assets for Bannerlord](editor-free-bannerlord-assets.md) for the binary formats behind the races and clips.
