---
kind: game
title: 'Pactblade: a custom vocation on VSB - recoloured effects, own sound banks, binds, warps and crash rules'
game: Dragon's Dogma 2
games_also: []
game_version: dd2.exe 4.1.0.0 (post-DLC), Steam 2054970 build 25920212; REFramework (nightly, Oct 2026)
platform: windows
engine: re-engine
route: loader-api
tools:
- REFramework (Lua)
- _DragonCore 1.2.0 + VSB (Vocation & Skill Builder) 1.1.0
- REE-Lib (efx read/write; the author's local, unpublished patch for the DD2New efx version 5965310)
- ree-pak-cli (pack), vgmstream, ffmpeg
anti_cheat: none found; single-player only (online / pawn-share side effects untested)
status: released
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-24'
links:
- https://github.com/ntgoten/pactblade-scriptonly
- https://github.com/praydog/REFramework
- https://www.nexusmods.com/dragonsdogma2/mods/1916
- https://www.nexusmods.com/dragonsdogma2/mods/1917
- https://github.com/kagenocookie/RE-Engine-Lib
- https://github.com/eigeen/ree-pak-rs
- https://github.com/vgmstream/vgmstream
tags:
- custom-vocation
- skills
- effects
- recolour
- sound-banks
- crashes
- teleport
---
# Pactblade: a custom vocation on VSB - recoloured effects, own sound banks, binds, warps and crash rules

> A warlock-style custom vocation for Dragon's Dogma 2, built as a VSB vocation pack plus one large REFramework Lua
> script (~7000 lines) that replaces Fighter skills with new ones: eldritch blasts that bind, warp combos, an acid
> spell, a teleport-dive, a Hex mark, and a recoloured sword look. Effects are recoloured by baking edited copies of
> game `.efx` files into a pak; custom sounds go through a cloned Wwise bank. Developed over ~300 test builds with the
> human playing each one; oracle = a mod-written trace file + REFramework's log + screenshots. Released as 1.0-1.2
> (October 2026). The script-only edition linked here ships the script, the VSB pack, default settings and guides,
> and no game files; without the pak (Build steps 2-3, from the player's own install) the effects show in the game's
> own colours and the custom sounds are silent.

## Setup
- Dragon's Dogma 2 4.1.0.0 (Steam build 25920212, after the paid Dark Arisen expansion launched on 2026-10-09),
  Steam, Windows 11. REFramework nightly (dinput8.dll).
- **Needs the paid Dark Arisen expansion** (Steam DLC 2593290), which the author owns. Archfey Combo plays
  `Job01_RushAttack` / `Job01_RushAttackFinish`, the actions of the expansion's Fighter skill Whirlwind Strike (custom
  skill 102), and the Misty Dive flash recoloured in the pak (`0/15/0`, `13_ch00_EX_000_00` from `15_EXSkill_DLC`) is
  an expansion effect. The mod doesn't check ownership: only use it if you own the expansion.
- **_DragonCore 1.2.0** (actor/action helpers, summons, shells) and **VSB 1.1.0** (custom vocation packs, picked per
  weapon type). Pactblade = VSB pack with `vocation.weapon = "Job01"`; the script checks VSB's pick through
  `VSB_API.app.picks.Job01`. The 1.1.2 and 1.2 READMEs ask for VSB 1.4.0 or newer, _DragonCore 1.2.0 or newer
  (tested with 1.2.5) and _ScriptCore (ground checks).
- Paks in `<game>/pak_mods/` (numbered `x000N-Name.pak`, higher number wins on equal paths). REFramework loads
  every `.pak` there in directory order with no sort of its own (`IntegrityCheckBypass.cpp`), and NTFS lists
  names in order, which is why the numbering works.
- Played as Warfarer (True Warfarer) with a sword; also works as plain Fighter.
- **Saves and online:** the sword's Magick / element and the Guise's chest bonus are written into the game's item
  data, which every copy of that item shares. While the game builds a save, or the pawn and owner data it uploads to
  Capcom's servers, the script puts the original values back and re-applies them afterwards (pre/post hooks on the
  builders; a 5 s watchdog lets go if no end comes). The author added the upload half because modded stats in that
  data may get the pawn banned from online pawn sharing. Read from the code; what the servers receive wasn't checked.
  Single player only: play with Network Features off (Options > Network) while the mod is installed.

## Route and why
`loader-api` (REFramework Lua on the managed type system). VSB gives the vocation slot and menu presence; all skill
behaviour (actions, warps, damage, effects, sounds) is Lua hooks. Data-only edits (`.user` paks) were ruled out: after
the DLC, edited `.user` files in paks crash the game. Effects are the one place where files are edited: new-path copies
of game `.efx` files, played by our own `via.effect.EffectPlayer`s or swapped in at request time.

## How the game works (what we had to learn)
- **Actions:** `app.ActionManager.requestActionCore(Priority, String, UInt32 layer)` requests any action by name for
  any character (Fighter can play `Job05_*`, `Job07_*` etc. as long as the motion bank is loaded). Hooking it (pre) is
  also how vanilla skills are swapped out or refused. Motion: `FullBodyLayer:changeMotion(bank, motion, startFrame,
  blendFrames, 1, 1)` for chained parts with a crossfade; `set_Speed` for speed-ups.
- **Skill slots:** `app.PlayerInputProcessorDetail.processCustomSkill(...)`; skill availability for slots a Fighter
  can't normally use (shield skills without a shield): post-hook `app.HumanSkillAvailability.isCustomSkillAvailable` /
  `...WithoutItemCondition(id)` and answer true for our id.
- **Input:** `app.CharacterInput.Flag` static fields (Jump, Interact = Examine/Circle, GimmickAction, Sheathe,
  Skill1-6...) with `CharacterInput:isButtonTrigger(flag)`.
- **Bind + Quik Fot (Mystic Spearhand):** the charged-bolt action `Job07_MagicBindComplete` fires the real Forbeding
  Bolt projectile itself; its hit opens `Job07ActionCtrl.MagicBindCtrl.get_IsJustMagicBindEnable()`. As a Fighter
  `processJustMagicBind()` never starts the leap - request `Job07_MagicBindJustLeap` yourself on Jump. The bound
  enemy is `MagicBindCtrl.get_MagicBindShellHitOwner()` (an `app.Character`); unbind via
  `<BindCtrl>.get_MagicBind():stop(false)`. To make the bolt hit reliably, move the bolt shell's transform onto your
  own projectile (or the target) each frame.
- **Damage:** `app.HitController.calcDamageValue(DamageInfo)` post: `info.Damage` can be set (attacker =
  `<AttackOwnerObject>`, victim = `<DamageGameObject>`). Knock-downs: post-hook `getReactionDamageType` (return a
  `DamageTypeEnum`, e.g. Slam_L 15) and scale `DamageReaction` in `calcDamageReaction`. Direct area damage:
  `app.HitManager.directDamage(DamageInfo{Damage}, targetHit, attackerGO, false, attackerHit)`. Poison:
  `reqStatusConditionApplyCore(Poison, ...)`. Heal: `HitController.recoverHp(Single, Boolean, Int32, Boolean)`.
- **Effects:** `via.effect.script.ObjectEffectManager2.requestEffect / requestEffectInternal(EffectID, ...)`
  (EffectID = DataContainerIndex / ContainerID / ElementID). A container index points into
  `mgr.ExternalDataContainers[i].DataContainer` (a `*_Ref.pfb`); in that prefab the container id is the child
  GameObject's number prefix (`15_EXSkill_DLC` = 15) and each element lists its `.efx` Resources. One EffectPlayer per
  GameObject (a second `createComponent` returns nil) - one child anchor per effect. `via.effect.PlayerState` = low 32
  bits of `get_State()`: Idle 0, Start 1, Running 2, ForceStop 3, Finish 4, Finished 5, Restart 6. Freeze an effect
  on a frame with `set_PlaySpeed(0)` after it has run that long.
- **efx files (DD2New, version 5965310):** colours sit in several places: RgbCommon attributes (id 248, bytes 4 and
  24), TypeNoDraw's light colour (@4 and @68), TypeMesh material vec4 records (hash `f20fbe80` = colour), and for
  fluid-sim effects (FluidParticle2DSimulator, e.g. Frost Boon's shimmer) inside the simulator block (two RGBA colours
  with an f32 intensity between them). Layers whose name contains `inv` draw INVERTED colours (orange in the file shows
  teal) - bake them with the opposite hue. A layer is hidden by scaling its Transform3D to 0.001.
- **Body glows** (Mystic Spearhand's teal outline etc.) are material modes:
  `MaterialInterpolationRequestManager.requestMaterialMode(mode, category, -1, -1)`, RimLight = category 8; recolour
  `RimLight_Emissive_Color_A/B` (`getMaterialVariableIndex(m, StringExtension.hash(name))`) in BeginRendering.
  Mode definitions live in the component's `UserDatas[i]._ModeDataList` -> `_ModeList` -> `Mode._ModeValue` ->
  `_MaterialList` (`_MaterialHash`, `_VariableFList` / `_VariableF4List`: `_VariableHash`, `_Value`) - readable by
  plain field access.
- **Sounds:** `app.WwiseContainerApp` on a character; load a `soundlib.SoundBankListData` and a
  `soundlib.SoundTriggerInfoListData` with `create_userdata` + `loadContainableUserData` DIRECTLY on the container (a
  container list wrapping them adds nothing), find the `SoundTriggerInfo` in `AllTriggerInfoListData`, then
  `createRequestInfo` + `trigger(RequestInfo)`. Re-check every few seconds: the game rebuilds the container (save
  load) and drops them. Wwise bank v140 accepts uncompressed PCM wems (fmt 0xFFFE, channel config 0x4101 mono).
  Bank ids = FNV-1 of the lowercase name.
- **Weapons:** the right-hand weapon = `Character:get_WeaponAndItemHolder():get_RightWeapon()` slot, field
  `<Weapon>k__BackingField` (`app.Weapon`); slot field `IsStartPrepare` = switching. Slot change hooks
  (`app.WeaponAndItemHolder.Slot` / `.WeaponSlot`: clear, release, equipPrepared, changeWeapon,
  setDirectAndDestroyOld, onStartPreparing...) fire BEFORE the old weapon object is deleted - and for every NPC too.
- **Directions:** a character's right = (-fz, 0, fx) of its flat forward (fx, fz). Yaw quaternion =
  `Quaternion.new(cos(yaw/2), 0, sin(yaw/2), 0)` with yaw = atan(dx, dz) (constructor order w, x, y, z).

## Build steps
1. Install REFramework, _DragonCore, VSB; copy `reframework/` from the repo (script + VSB pack).
2. Effect copies: extract the game efx with REE-Lib (`CachedMemoryPakReader`; the community unpacker silently skips
   files), edit colours / hide layers with a small REE-Lib tool, save under a NEW path
   (`vfx/effects/pactblade/...`), pack with `ree-pak-cli pack -i <dir> -o pak_mods/x000N-Name.pak` (game closed, or a
   new pak number - running games lock their paks).
   Upstream REE-Lib reads the DD2New version number (0db16c3c), but its attribute tables have no DD2New entries, so
   reading a DD2New effect throws `Unknown DD2New EFX attribute type`. The author's local patch (two files,
   unpublished): `EfxAttributeTypeRemapper` aliases DD2New to Pragmata (5965300) for type ids and layouts, and
   `EfxFile` reads each sized attribute inside its own buffer with a strict end-of-stream check and keeps any
   attribute whose layout doesn't match as raw bytes (`EFXAttributeRaw`), written back unchanged. Effects
   round-trip, and only the attributes you edit need to decode.
3. Sounds: clone a small monster bank (events/actions/sounds) with new ids and PCM wems (the author's
   `tools/build_bank.py`, not in the script-only repo), copy the game's trigger/bank list `.user` files with new
   paths/ids, pack.
4. In game: pick Pactblade for Fighter in VSB.

## Verification
- Every build was played by the human (screenshots, short descriptions); the script writes a trace
  (`reframework/data/Pactblade_trace.json`) of every decision (target picked or why not, effect swaps, hits, warps).
- Crashes: REFramework's `reframework_crash.dmp` + the exception log in `re2_framework_log.txt`. The decisive clue
  was always the burst of caught `Exception thrown in REMethodDefinition::invoke for <method>` lines minutes before
  the crash.
- Not verified: online / pawn-share side effects, other vocations' weapons in Warfarer for every skill, performance on
  low-end machines.

## Gotchas
1. **Crash a few minutes after weapon switches, in random parallel-job code (AI planning, quest manager, effect
   culling).** Cause: our sword look requested an enchant MATERIAL MODE
   (`MaterialInterpolationEnchant.requestMaterialModeSub`) on the weapon and blocked the game's own requests there;
   when the game deleted the weapon mid-mode (or mid-fade after we finished it),
   `MaterialInterpolation.updateMatarial` touched freed memory. **Fix:** never request material modes on weapons.
   Read what the mode sets (UserDatas, see above - for Frost Boon's blade glow one float var `2797575560` = 0.15
   plus `Enchant_Color1/2`) and write those material values directly on the weapon in hand only.
2. **The same crash class from `WeaponElementController.getWeapon(false)` called every frame.** It throws inside the
   game during a vocation change (~180 caught exceptions in 2 s, crash 14 s later). **Fix:** read the weapon from the
   holder slot field (above); nothing is called on the game.
3. **Crash from effects:** destroying a GameObject that a GAME effect container uses as its parent, or `destroy()` on a
   GenerateManager-spawned gimmick, leaves a zombie in the EffectManager -> crash later. **Fix:** game effects never get
   our anchors as parents; to move a game effect, read its file paths (`getAllPlayers` -> `get_ResourcePath`),
   `killAll` it and play the file on our own EffectPlayer.
4. **Our replacement effect copies were randomly the original colour (teal).** Cause: copying the game player's look
   (`ExternParameters` / `GroupParameters`) onto our copy also copied its colour values - only when the game's player
   was already loaded that frame. **Fix:** copy only EmitMaskBit, MaskName, GroupEnabled, GroupNames.
5. **Effect hook stacks out of step.** A pre/post hook pair that pushes one entry per call onto 2-3 stacks must pop
   ALL of them before any early `return` in the post hook - one early return made every later effect get another
   one's colour/kill decision.
6. **Mystic Spearhand's skills played by a Fighter use different effect elements** (SkyDive: 14/7/10 + 14/7/11 as a
   Fighter, 14/7/20 + 14/7/21 as Mystic Spearhand). Record what plays in YOUR setup before baking copies.
7. **`is_alive`-style checks (`get_Valid` then HP) rejected every enemy** in one picker - read the HP directly from
   `<Hit>k__BackingField:get_Hp()`.
8. **Teleporting from `re.on_frame` (render time)** left the afterimage clone stuck and the body "detached". Do warps
   in `re.on_pre_application_entry("UpdateBehavior")`; refuse `*Jump*` requests for ~0.4 s after a warp triggered by
   the Jump button.
9. **Warp above an enemy into an air attack: the controller kept sliding/launching.** Setting the Transform alone isn't
   enough - also `<CharaController>:warp()` (clears its speed); hold X/Z each frame in UpdateBehavior and
   LateUpdateBehavior, cap the height, release the lock at the enemy's head (standing on it -> the game's execution
   animation sank the player into the ground).
10. **Lua main chunk hits the 200-locals limit** in big scripts - put features in `;(function() ... end)()` blocks and
    expose cross-feature functions through a table; code earlier in the file can't see locals defined later.
11. **"Head" height:** the character controller's height is far below a monster's real size - use the highest joint
    whose name contains "head" (bounded to a box around the creature).
12. **VSB forgets the vocation pick on "Reset scripts"** while its game integration is off (VSB's boot guard turns it
    off after a crash in the first 10 s of a session). Re-pick through `VSB_API.app:set_vocation_pick("Job01", id)`
    from a file written in `re.on_script_reset`.

## Assets
No generated art. The effects are recoloured copies of game `.efx` files, and the three custom sounds (cut from the
author's own audio) sit in a bank cloned from a game bank, next to copied `.user` lists. None of that is in the repo
or the script-only release: each player builds the effect copies and the sound lists from their own install (Build
steps 2-3).

## Cost and time
About 6 days of sessions (2026-10-19 to 10-24), ~300 test builds.

## Open questions
- A data-driven way to give VSB vocations their own effect files without paks.
- Hex's follow-ups (Onslaught/Empale teleport in front/behind) and skill stamina costs.
