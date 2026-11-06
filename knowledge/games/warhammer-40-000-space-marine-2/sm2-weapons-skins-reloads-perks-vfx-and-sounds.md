---
kind: game
title: "Space Marine 2 weapons: skins, new melee weapons, reload and hip-fire animations, perks, VFX, sounds and crosshairs"
game: "Warhammer 40,000: Space Marine 2"
games_also: []
game_version: "Steam build 25799387 (Patch 15.1, Oct 2026); earlier findings on Patch 14.x (Aug-Oct 2026). Mod Tools app 3856330 build 25506153"
platform: windows
engine: unknown
route: data
tools: ["Saber SM2 Mod Tools (ModEditor, ModelConverter, UsfExporter)", "Python 3 (zipfile, struct, numpy)", "own Morpheme .nmb network reader/patcher", "own .sani clip codec", "own sslbin disassembler", "own Wwise bank reader/writer"]
anti_cheat: "EasyAntiCheat. Everything here uses Saber's official mods folder (client_pc/root/mods), which flags the session 'Mods Detected' (private lobbies, separate progression). No injection, no EAC interaction, PvE only."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-15
links: []
tags: [space-marine-2, saber, weapons, weapon-skin, melee, firearm, reload, active-reload, morpheme, animation-network, perks, damage, burning, vfx, sound, crosshair, hud, equipment]
---

# Space Marine 2 weapons: skins, new melee weapons, reload and hip-fire animations, perks, VFX, sounds and crosshairs

> What we learned building weapon mods for Space Marine 2: a revolver skin for the heavy bolt pistol with its own
> reload, shot sound and a hip-fire "fanning" animation; a pump-action shotgun as a custom melta version; a new
> one-handed melee weapon; a power sword that sets enemies on fire; frost VFX on a chainsword; an active-reload
> mechanic with a jam animation and HUD markers. All through data (text `.sso`/`.cls`), tpl models and careful binary
> edits of the Marine's Morpheme animation network. Builds on
> [the foundations note](sm2-modding-foundations-paks-tools-and-crash-triage.md),
> [the models note](sm2-models-tpl-format-modelconverter-and-textures.md) and, for the `.nmb` / `.sani` formats,
> [the NPC/animation note](sm2-new-enemies-npc-classes-and-morpheme-animation.md). Verified in game unless marked
> otherwise.

## Setup
- Steam build 25799387 (Patch 15.1). Patch 15/15.1 changed a lot of weapon data (new frost VFX, one-handed thunder
  hammer and melta tuning, melee skin variants, new float resets in `anim_table_primaris`); merge your edits onto the
  CURRENT retail files, or stale copies break other weapons' animations.
- Gameplay text lives in `default_other.pak` on BOTH `client_pc` and `server_pc`; perks only on the server side.
  Animations in `default_animation.pak`; the Marine network is `morpheme/primaris/primaris.nmb`.
- Read `client_pc/root/tools/meta_descs/meta_desc_ssl.ps` for every blueprint node's pins and defaults before
  wiring anything.
- A testing arena (`test_scene_mod` from [Testing Menu](https://www.nexusmods.com/warhammer40000spacemarine2/mods/233)
  by Hypexs777 (Nexus Mods)) and screen recordings were the oracle; for timing problems we stepped through recorded
  video frame by frame.

## Route and why
Data route. Weapon behaviour, skins, VFX and sound hookups are text files; models are tpls (see the models note).
Compiled code (`.sslbin`) cannot be replaced, so anything that looks like "new logic" is built from existing node
types, existing perk/flag types and network parameters. The Marine's animation selection is compiled into the Morpheme
network, which we patched in place (the engine loads an edited `primaris.nmb` from a mod pak).

## How the game works (what we had to learn)

### Firearm data chain
- `ssl/weapons/creator/customization/firearm_versions_library.sso`: versions of a firearm (`modificatorsGroupName`,
  default skin, perks). `firearm_modificators_library.sso`: per-version presets (the "godlike" preset carries
  `descriptionOverride` with `actorName` and `sightPreset`), `clipsSettings`, `reloadTimeLength`, the dropped-magazine
  tpl, `reloadAnimSpeedScale`, `shootSettings.fireRateAffectShootAnim`, `barrelSwitcherSettingsAim` (e.g. single fire
  on hip, burst when zoomed).
- Actor classes (`hgun_*`, `arifle_*` ... `_client.cls` / `_authority.cls`) carry `prop_firearm_type_settings.wpnType`
  and the shot/reload blueprints. Version classes override `wpnType` in BOTH client and authority cls.
- **wpnType is the only thing the Marine's animation network sees.** Values seen: heavy bolt pistol 0, bolt
  pistol/carbine 0.1, plasma pistol 0.2, assault bolter client 0.3, volkite 0.4, inferno pistol 0.5, bolt rifle 1.0,
  auto bolt rifle 1.01, melta versions 1.4 (chaos 1.41), 1.6 for another rifle branch. Network switches select by
  FLOOR thresholds, so 1.01 takes the 1.0 branch. A new wpnType value cannot get new animations without editing the
  network, and replacing a `.sani` changes EVERY weapon on that wpnType.
- **A reload has two halves.** The Marine clip is chosen by wpnType. The weapon's own moving parts (magazine, slide,
  cylinder, hammer) are tpl-baked animations `IDLE`, `RELOAD_FULL`, `SHOOT_1`, `SHOOT_2` on nodes like
  `mag_spawn_loc`, `mag_spawn_loc_dropped` and the slide pivot, with frame events in the root node's glTF
  `extras.actions` (`&ReloadClipOut`, `&clip_start_drop`, `&clip_end_follow`, `&clip_in_hand`, `&ReloadClipIn`).
  ModelConverter round-trips all of it. Firearms play `SHOOT_1`/`SHOOT_2` on every shot with no extra wiring (that is
  how a revolver cylinder indexes and a hammer falls).
- **The gameplay reload is a timer**, not the animation: entering the full reload starts `RELOAD_FULL` and a timer,
  the ammo is credited at the commit point (`timePercentToReload`, default 50 in `firearm_base.cls`), the reload ends
  when the timer does. The network may play your clip, but ammo refills on the retail timeline: make a custom reload
  clip and `RELOAD_FULL` the same length as the retail reload it replaces. Some versions set `reloadAnimSpeedScale`
  0.9, so the clip clock can drift from the reload bar.
- `ClipSettings.magazineType` (a float, hint "Will be passed to morpheme") feeds the network control parameter
  `wpn_magazine_type`. `prop_firearm_type_settings.wpnMagazineType` does NOT. No retail weapon sets it, which makes it
  a free per-version flag for network routing.
- `fireRateAffectShootAnim = False` stops `SHOOT_1` being stretched to the fire interval;
  `prop_firearm_animation.shootAnimationPlaybackType = "clamp"` stops a short shot clip replaying.

### Firearm skins
- Skin = `firearm_skins_library` `FirearmSkin` (`geomCustomizerRegions` = the tpl objects that stay visible,
  `overridedActorName`) + a pack in `weapon_appearance_library_pve` (no lock + cost 0 = free) + a name in
  `ui_firearms_library`. Region names come from `geom_customizer_preset_firearm` (`base_01`, `base_01_01`,
  `base_01_02`, `bolt_01` ...): extra objects must use one of those names. A two-material mesh is split by
  ModelConverter into `<name>_$p0/$p1` children, which are not region names - one object, one material.
- The dropped magazine tpl and reload time belong to the VERSION, not the skin.
- A brand-new actor `.cls` needs a compiled class declaration (every retail `.cls.resource` links an `.ssc.resource`
  -> sslbin), so we borrowed an existing actor (a Chaos-faction PvP variant of the same gun) and rewrote its text and
  `.cls.resource` `linksTpl`. Saber's newer `noSsl` CLS route (foundations note) may remove this need; untested for
  weapons. Armoury preview = `dummy_library.sso` entry keyed by actor name, with its own `linksTpl`.
- **A cosmetic skin's actor supplies the model and wpnType, but the shot blueprint runs from the VERSION's class.** A
  skin can't change the shot sound by itself (see Sounds).

### Melee data chain
- A melee actor is just an inline entry in `ssl/melee/weapon_actors/melee_actor_factory.sso`:
  `<actor> = { type = { properties = { geom = { nameTpl = "..." } } __type = "wpn_melee_<weapon>" } __type =
  "WpnMeleeActorDesc" }` on an existing compiled class, so new actor NAMES need no sslbin (add the tpl to the
  factory's `.resource` `linksTpl`). `geom = { scale = X }` resizes a weapon (retail precedent exists); reach is
  unchanged.
- Cosmetic melee skin: `melee_skins_library` (skin -> `meleeActorOverride`), a pack in
  `weapon_appearance_library_pve` (lib `MELEE`, `meleeSkinUids.PLR_LOYALIST`, cost 0), `ui_abilities_library`
  `MeleeUiSkinData` + strings, `dummy_library` entry keyed `"<meleeActors key> : <skinUid>"`.
- Versions: `melee_versions_library.sso` (`skinUid`, `modifierUid`, `perkUids`). Example chain: the Salamanders power
  sword is `melee_power_sword` version `05_a` -> skin `05_a` -> actor `power_sword_challenge_02` -> its own tpl and
  `heat` sfx; its end effects come from `melee_end_effects_library` -> `ssl/end_effect/ee_lists/*.sso`.
- Behaviour: `ssl/weapons/melee/weapon_descriptions/melee_weapon_descs/<weapon>_desc.sso` (strikes, detectors, damage,
  `stackManagerDesc`). Per-mode overrides live in `melee_descriptions_library_pvp/_story.sso`; the `_pve` entries are
  empty, so the base file IS PvE. Version-gated logic exists only inside `stackManagerDesc`
  (`ConditionWeaponVersion`). Perk-only strikes (e.g. a heroic 5th slash) are effectively exclusive to that version.
- Melee geom customizer region = the object NAME, so keep one object / one material. One-handed hammer tpls: grip at
  the origin, weapon along +z, LOD1-4 children, an object holding `sfx_hit`/`sfx_trail` locators and four
  "charge shell" meshes whose SCALE the tpl anims animate (the glow per charge). Keep retail node order so animation
  indices hold.
- **New melee weapon** (not a skin): Saber pre-registered ability uids `melee_mod_1..5` with
  `for_modders/wpn_melee_mod_N.cls` and `melee_mod_desc_N.sso` (brands already listed in the melee descriptions
  library). Clone an existing weapon: `ability_library` entry (`meleeDescLink` -> the modder desc), the desc with
  `weaponActorUid` changed, the factory actor (can keep the donor's class), versions (reuse donor modifier uids),
  mastery / perk-tree / heroic / combo-move blocks keyed by ability uid, `ui_weapon_parameters` `matchedAbilities`.
  Class availability = `weapon_loadout_skills_library` `weaponSkillPacks.<Pack>.meleeWeapons` (+ a `meleeAbilities`
  entry with the spawn perk); the pack per class comes from the same file's `masteryPacks`.
- Perks are defined only in the SERVER pak: `server_pc/.../default_other.pak` `ssl/player/perks/perk_server_factory.sso`
  (data-driven `PerkDesc` triggers + applications on compiled types). `SpawnWithX` perks are
  `PerkApplicationSetAbility(abilityUid)`: clone one for a new uid. Perks keyed on `MeleeStrikeWeaponType` carry over
  if the new weapon keeps the type.

### Perks, flags and damage side effects
- There is no way to condition damage on a weapon version outside `stackManagerDesc`, and skins are invisible to the
  damage system. Strikes are gated by `BlueprintNodeCheckModifierFlag` on named flags, and flags come from perks.
- **Perk transplant (verified in game):** a version's `perkUids` accepts a perk from ANOTHER weapon. Adding the heroic
  power fist's melta perk to the Salamanders sword version gave it `MELEE_FIST_HEROIC_MELTA`, a flag no power sword
  perk grants - a private flag. Cloned strikes with a `CheckModifierFlag -> If` gate in front (rerouting the combo
  start handlers) then fire only on that version. Other borrowable flags: `POWER_AXE_WHIRLWIND_CHAIN`,
  `MELEE_HALBERD_*`, `MELEE_THUNDER_HAMMER_POLEAXE_WHIRLWIND`, `HEROIC_CHAINSWORD_NEW_HEAVY`. `COMBO_1/2_ADDITIONAL_STRIKE`
  come from ordinary mastery perks, so they are not exclusive.
- **Elemental side effects** on any damage block (`MeleeDamageSettings`, `MeleeExtraDamageSettings`, firearm
  `ShotCreatorSettings`, `DamageInfo` in damager descs):

```
sideEffects   =   [
   {
      type   =   "BURNING"
      value   =   100
   }
]
```

  Enum (from `damage_side_effect` in `default_ssl.pak`): `FIRE`, `TOXIC`, `PSIONIC`, `CORRUPTION`,
  `VOLKITE_EXPLOSION`, `BURNING`. The `.sso.resource` of the file that uses it must list
  `res://ssl/damage/damage_side_effect.ssl.resource` in `linksDesc`.
- BURNING feeds the single heat status effect (`HeatUntilBurning` in `ssl/status_effects/.../status_effects.sso`;
  thresholds fodder 10 / common 25 / elite-boss 100, heat decays) which applies `Burning` (5.5 s DoT, -50 % move
  speed, a guardbreak pulse). **In game `value` did not matter**: 100 and 500 both needed four hits on a majoris and one
  hit never ignited, consistent with a fixed ~25 heat per application. Retuning `Burning` retunes every fire weapon
  (one shared chain). Fire visuals without damage: add `sfx_flamethrower_ee_enemy` (an `sfx_end_effect` class) to the
  weapon's end-effect list.

### Weapon VFX
- VFX added to an actor block in `melee_actor_factory.sso` is scoped to that actor, so it follows the SKIN.
- `isAutoStart = True` does not work on these actors. Drive effects with `BlueprintNodeVfxRestart` / `VfxStop`; for
  always-on, hook `BlueprintNodeSubscribeOnEquipmentUserChanged` `OnUserSet` + `OnUserAttached` (fires on draw).
  Hanging it on a stack-count event restarts it (visible pop) on every change.
- **Two stop lists must both list the effect**: the actor's own `ignoreSfxList` and the SHARED one in
  `ssl/weapons/controllers/melee_controller/combo/blueprint_wpn_melee_effects_<weapon>.sso`, else it dies in one blade
  mode but not the other.
- Big `sfx_group` effects built for character hands (thousands of lines, many sub-effects) silently fail to render on
  a weapon; simple single-emitter effects work. Bisect by swapping in a known-good effect with the same wiring.
- Placement: an entry's `transform` translation (index 14 = along the blade) for whole effects; sub-effects with a
  `nameParent` attach to that tpl object and inherit its scale - a scaled `sfx_trail` locator moved an aura to
  mid-blade. Parent to an unscaled locator. An emitter's `geomPrimitive` cube `scale` is FULL extent (verified).
- Per-skin colours: a `WpnMeleeActorDesc` can carry `properties.sfx.list` overrides with `__onlyOn = "visual"`
  (swap fx classes, inline colours). **SSL colours are A,R,G,B** (constant expressions, `ColorCtrl`) and keyframes are
  (t,A,R,G,B); a "gold" Chaos example turned out purple.
- Some flashes (charge gain, shock explosions) are spawned by the MARINE's weapon blueprint with a team switch, not by
  the weapon actor, so a per-weapon override can't recolour them.
- Patch 15 frost axe: `blueprint_vfx_wpn_power_axe_frost.sso` overrides the axe's VFX blueprint; trails/whirls fire on
  Morpheme duration events (`vfx_frost_cw/ccw`) that exist only in the axe whirlwind anims; the "stack gain" effect is
  a few dark projected decals on the axe blade (invisible on other weapons). A finisher-kill burst can be triggered
  from `BlueprintNodeSubscribeOnDealDamage` -> `IsLethalDamage` -> damage-type string compare (string assumed
  `dmg_type_finisher`, unverified).
- Blueprint nodes must sit at the exact sibling indent; brace balance does not catch a node nested inside a field.

### Sounds on weapons
- Shot sounds are in the CLIENT actor `.cls` (the authority's `shootSound` is empty):
  `prop_blueprints.blueprints.SoundFirearmShootSingle.nodes.PlaySoundClientOrAuthority_2` with `soundClientDesc` (3D,
  heard by others) and `soundAuthorityDesc` (2D, the shooter's own). Auto weapons use `SoundFirearmShootAuto`. Event
  names `wpn_firearm_shoot_{3d,2d}_<weapon>`.
- An event loads only if the `.cls.resource` lists it: `linksSound: - res://sounds/events/<event>.sound_event.resource`.
  Retail precedent: a suppressed heavy-pistol version overrides only that one node (keep every `__type` line).
- Changing the two event names in the BASE weapon's client cls (+ the resource links) works for every skin of that
  weapon. For one skin only, add a `BlueprintClient` graph in the base cls: `SubscribeOnFirearmShootEvents` (subscribe on
  init) -> `If` on `BlueprintNodeGeomHasObject` (an object name only your skin's tpl has) -> two
  `PlaySoundClientAuthority` nodes (user from `BlueprintNodeEquipmentGetUser`), with the stock node's events blanked.
  Verified in game. If the graph breaks, every variant of that weapon goes silent.
- Crashed: a brand-new actor for the sound; injecting `prop_blueprints` into a child actor; the base cls edit without
  the resource link.
- Weapon-exclusive media can also be replaced inside the retail `wpn` bank (same event ids, new media) - scope is
  every version that uses those media. The bank format and how to judge loudness are in the
  [voices/Wwise note](sm2-voices-talkers-and-wwise-audio.md): compare against retail guns recorded in the same scene.

### Crosshairs and the reload HUD
- Chain: the firearm description's `sightPreset` (enum: AUTO, SINGLE, HEAVY_AUTO, SHOTGUN, PRECISE_AUTO, SNIPER,
  PLASMA, UNIQUE) -> `ssl/ui/systems/sight_system/libraries/ui_sight_presets_library.sso` (`sightDefaultPresets`,
  `uniqueFirearmSightPresets` keyed by base firearm uid) -> per state (MINI_ZOOM, AUGMENTED_ZOOM, BLIND) a module
  `brackets = "<key>"` -> a child of the `bracket` UiSwitcher in
  `ssl/ui/fusion/hud/crosshair/assets/ui_hud_sight_brackets.sso` -> `UiElementBitmap`s on a 1920x1080 layout (view
  centre 960,507), white art tinted by `advancedTintMult`.
- Per-version reticle: set the version's preset `descriptionOverride.sightPreset = "UNIQUE"`, add
  `uniqueFirearmSightPresets.<base uid>`, add a switcher child that reuses an existing sight class and overrides its
  children inline (a new class would need code). Textures: `.texture.asset` + `.pct.resource` (format 0, 1 mip) + a
  mip of raw premultiplied BGRA, listed in the brackets `.sso.resource` `dynamicLinks`. (Built, not tested in game.)
- The ammo/reload arc under the crosshair is `ui_hud_crosshair_clip_size_bar` (state `reload` runs over a fixed frame
  range; the fill is a rotating mask). Elements without a `colorEffect` inherit the crosshair colour; a fixed colour
  needs `colorEffect "ADVANCED"` + `advancedTintMult`. `UiElementShapeWipe` (start angle, arc angle, inner width)
  draws real arcs. A gold marker slice inside that bar worked in game.
- The clip-bar script only accepts ammo / reload progress / low-ammo; there is no data path from gameplay to its
  colour. What worked for a red/gold overlay: a hidable team-status widget instance with inline view overrides, shown
  by `BlueprintNodeOverrideWidgetsVisibility` -> `WidgetVisibilityRuleOverrideEnabled` string rules (custom override
  ids are free strings). Hide rules win (the first active Hide stops evaluation). Extra `UiSightWidget` copies can NOT
  be hidden by rules (the sight logic re-shows them): don't use them. Fades come from the view's
  `animFadeIn/animFadeOut` states (frames are overridable inline).

### Equipment and holsters
- Visibility is the equipment system, not animation: `ssl/weapons/weapon_user/loadout_system/equipment_preset_marine.sso`
  maps item descs to slots. A one-handed melee is active in `right_hand` (locator `GUN_R`) and inactive in a hidden
  holster slot (`melee_weapon_pivot`, `isDeactivatedItemHidden = True`), so rifle users' swords are hidden, never
  holstered. `melee_weapon_pivot` is a hidden point ~43 cm off the right hip: animating `GUN_R` onto it floats the
  sword.
- **Pistols are held in the LEFT hand** (`Gun_pose` == `GUN_L`, child of `HANDL`); the melee weapon is on `GUN_R`.
- Script hide: `BlueprintNodeEquippedItemSetVisibility` (item desc key, hide flag, a visibility-request enum such as
  `EQUIPMENT_SLOT`, `ITEM_CARRY`, `MORPHEME`). From a firearm's blueprint reach the holder the way retail's finisher
  VFX stop does: `SubscribeOnEquipmentUserChanged` -> actor variable -> `SubscribeToBodyStateCondition`. Body states:
  `AIM_BLIND` (hip fire), `AIM_ZOOM`, `SHOOT`, `RELOAD`, `MELEE_*` (enum in the body-state module). Derived weapon
  classes MERGE `prop_blueprints` with the base.
- From the decompiled equipment logic: a geom follows its attach slot's tracker, but visibility comes from the slot
  stacks; activation deactivates whatever is in the new item's locked slots. Inactive-slot offsets are keyed by the
  melee actor uid (the factory key), so skin actors do NOT get the base weapon's offset. Weapon switching is driven by
  network events `put_old_wpn_away` / `get_new_wpn`.
- Un-hiding holsters (another mod's approach) exposes a retail quirk: the five pistol/melee-to-rifle switch clips move
  `melee_weapon_pivot` into the right hand for frames 1-5, so a fast switch can leave the sword "glued" in the hand.
  Pinning the pivot channel to its rest value in those clips reduced it, but it still happens (second cause open).

### The Marine animation network (`primaris.nmb`) for weapon animations
- Animation selection is compiled into the Morpheme network. `ssl/animation/categories/anim_table_primaris.sso` only
  maps gameplay events to network parameters/requests; ordinary shooting and reloading are not in it. The table's
  only swappable clip slots are `AnimationSlot_Melee` and `AnimationSlot_Finisher` (full-body). Weapon scripts can
  order table entries (`BlueprintNodeOrderMorphemeAnimation`, `animTableLinkRef` like
  `Primaris.Melee.AdditivePreLight1`).
- The `.nmb` container (assets with 40-byte headers, global asset IDs, hashed and sorted string tables) is described
  in the NPC/animation note. Inside the network asset we decoded the node table, node definitions, name table,
  children, control-parameter (CP) connections,
  Saber's Expression bytecode (compare-equal, compare-not-equal, move, jump; operands are input indices or constants)
  and state-machine transition conditions (CP-in-range with a NOT flag, CP > a). Useful anim-node attributes: additive
  flag, loop flag, clip index into the network's own anim list (NOT the `.mr.resource` order), duration. All of these
  can be patched in place.
- Hip fire: a random "shot pulse" weight blends the per-shot clip; arm-pin expressions hold the off arm; `GunAimIK`
  aims the gun; a joint-modify node rotates `Gun_pose` about its ORIGIN for aim convergence and adds recoil; the hand
  IK pulls the hands onto `Left/Right_hand_hold`. Pistols never play the per-shot clip in hip fire unless the pulse
  weight is forced; standing hip fire sits in `loco/idle/aim/tacticus_wpn0_blind_idle_closed`; moving hip fire is a
  separate path. Setting the weight to 1 and the arm pin off made the shot clip drive the whole right arm.
- **Rules for any custom Marine weapon clip** (each one cost a test round):
  1. `Left/Right_hand_hold` exactly on the hands every frame (retail: <= 0.1 mm).
  2. `Gun_pose` == the gun bone's frame every frame (pistol: `GUN_L`); hands sit at the grip only relative to `Gun_pose`.
  3. Put `GUN_ANIM` ON the gun in the stance orientation: aim corrections rotate it, and the fire gate
     (`angleAimedCheck` 40 deg on `GUN_ANIM`) refuses to shoot if it points away from the target.
  4. Re-solve the pauldron channel `shoulder_R` per frame from retail data: Saber animates it in most clips (a baked
     pad-aim rig); keeping the stance value makes the pad ride the upper arm into the helmet.
  5. Keep retail offsets between twin joints (e.g. forearm vs glove) - IK that copies one onto the other twists the glove.
  6. The additive stream is relative to the clip's OWN frame 0 (`R(t) * R(0)^-1`, `p(t) - p(0)`).
  7. Frame 0 must equal the LIVE retail clip's frame 0: reload networks subtract a SingleFrame of frame 0 for their
     additive layers. Extract templates from the current `default_animation.pak` - an older extraction differed by
     90-114 deg on some channels.
- **Adding clips to the network**: an anim-list entry plus the clip's `.sani.resource` and a link in
  `morpheme/primaris/primaris.mr.resource` (identical client/server copies); the anim-list layout and the boot crash
  without the manifests are in the NPC/animation note. New nodes: clone a same-type node over a node
  in a never-entered debug tree, keeping each Expression's unique index; or append whole records at the end of the
  asset and repoint the node-table offsets (verified working; the node COUNT was not grown).
- **Slots hijack lookups by name**: the server resolves finisher and other gameplay animations by anim-node LEAF name,
  and the namesake that comes first in the network's name table wins. Reusing a debug anim node that was the first
  namesake of a finisher made the finisher read a reload clip and crash the server (missing `smart_target` bone).
  Only reuse a slot whose name has an earlier namesake.
- **A Blend2 at weight 1 passes NO events** (neither child's), so wrapping a clip in a Blend2 silently kills its
  markers; use a Switch as the wrapper. **Never put a Blend2 under a SingleFrame** (client crash in the sync-event
  combine).
- Reload layout (rifle): the live reload users are the wpn_reload switches that feed the regular and `sani+` paths;
  two sibling switches only feed SingleFrame subtraction references (never wrap those). The `anim|special` state
  `wpn_reload` is entered while CP `wpn_reload_type` > 0.5; gameplay writes 2.0 at reload start and 0 at commit/exit,
  so a blueprint can drive it too. The network has an unused CP (`Debug_Float1`) that a blueprint can set with the
  set-Morpheme-parameter node: a mod-driven router input.
- Reload clips carry a network `checkExit` duration window that ends ~0.77-0.84 of the clip on rifles and 0.5 on
  pistol aim reloads; keep custom duration events before it.

### Input during actions (what an active-reload mechanic needed)
- `actions/filter_rules/action_filter_rule_reload.sso` whitelists Game.Reload during a reload, so a second press
  arrives. In `actions/action_controller_project.sso`, a `ConditionsActionCommandBinding` with Game.Reload + body state
  RELOAD + `ConditionTriggerMorphemeEventRecently(<clip marker>, ms)` -> `CommandInterruptCommand RELOAD` ends a
  reload early; `commandDescOnRelease = CommandReload` restarts it. Both verified. Markers are just extra events
  appended to the reload clips' event tracks.
- If the ammo must stay after an early finish, the commit point (`timePercentToReload`) has to lie before the window.
- The action filter keeps only the highest-priority action per input link: a binding at priority 200 swallows Shoot
  (priority 110) - a way to block firing during a custom animation.
- `ConditionInvert(ConditionTriggerMorphemeEventRecently)` (no retail use) behaved as always TRUE. Build conditions
  from positive triggers and NOT-body-state only.
- Nodes proven to fire in the Marine client blueprint: Morpheme event / duration-event subscriptions (a duration
  event's deactivate fires when the clip is cut - good for "the player interrupted here"), If, variables, set Morpheme
  parameter, WaitOneFrame, CheckBodyStateCondition, Delay (duration can come from a float variable via the
  `<Delay>/duration/cb` pin pattern), CommandReload, story-voiceover playback. `BlueprintNodeInputHold` fires only
  after its HOLD time, so a tap never triggers it. A body-state OnExit subscription never fired there.
- Every node type a blueprint uses must be declared in its `.sso.resource` `linksDesc` (library nodes via their
  `.ssolib.resource`).
- Vanilla "Reloading!" chatter is `VoiceoverTriggerReloading` in `ssl/sounds/voiceover/prop_voiceover_marine_client.prop`
  (an `ownerCondition` can suppress it).

### Abilities (cloned war cry)
- With Saber's enum extension (foundations note) a cloned ability on a new `AbilityUid` works. Server logic is keyed by
  the controller's `factoryUid`, damage keeps the original `abilityType`. Uid-keyed files that need the clone:
  `ability_library`, `ui_abilities_library`, `ability_view_library` (+ category), `action_controller_project`
  (`castTypeToTryPerAbility`, `excludedAbilitiesFromBodyStateCheck` - without it the key may not cast), the far-aim and
  smart-abort bindings, `action_filter_rule_ability_cast`, `command_filtration_character`, the VO trigger prop, the
  ability-ready chatter list in the base server cls, the granting perk and the HUD mastery ability.
- An ability can override ONE node of a shared controller inside `ability_library` (retail does it for a grenade).
- An ability animation task cannot start an emote; the war-cry controller leaves `OnFail` unwired, so the cast hung
  (charge kept, shooting blocked). Wire `OnFail` before experimenting. Emotes are smarts: a class can start one with
  the server node `BlueprintNodeEnterSmart` and an INLINE `smartDesc` (retail does this for NPC prayers).

### Worked examples (SM2 mechanics only)
- Revolver skin on the heavy bolt pistol: cylinder = the magazine under `mag_spawn_loc` reusing the inferno pistol's
  reload (its `RELOAD_FULL` flings the canister and snaps it back); hammer = the slide slot; per-shot cylinder index =
  `SHOOT_1/2` rotating `mag_spawn_loc` one flute. The pose resets after each shot, so the visible jump is hidden on the
  shot frame (rest pose = one flute ahead) - an uneven cylinder or texture otherwise "pops". A retail `.td`/material
  linked from our tpl (a retail emblem mesh with its retail material) rendered fine.
- Hip-fire hammer fanning: the revolver version sets `magazineType = 1`, the network routes magazineType 1 to its own
  clip slot with full shot weight; everything else stays retail.
- Pump shotgun: a custom Heroic version of the melta rifle with its own model; shots on the rifle shot clip, the
  reload clip shows seven shell inserts within the retail reload length, `magazineType = 1` shares the full-weight
  router. In ADS, single fire at ~50 rpm made the aim shot state ping-pong and replay a short clip (double pump) -
  hold the shot clip to the fire interval and clamp playback.

## Build steps
1. Extract the current retail files you touch (libraries, cls, `primaris.nmb`, `.mr.resource`, clips).
2. Model: tpl with retail node names/region names and tpl-baked `IDLE/RELOAD_FULL/SHOOT_1/SHOOT_2` (models note).
3. Data: version/skin/pack/UI entries; for melee, a factory actor; for a new weapon, a `melee_mod_N` slot + server perk.
4. Sounds: base-class event names or a `GeomHasObject` switch graph + `linksSound`.
5. Animations: clips that obey the seven rules, `.sani.resource` + `.mr.resource` links, network edits with a
   name-lookup assert, a frame-0 diff against the live clip.
6. Merge every shared library with whatever installed mod currently wins it (first alphabetical pak), ship ZIP_STORED.

## Verification
- In game: revolver skin incl. reload, cylinder/hammer, the per-skin shot-sound graph and a retail material on our
  tpl; burning sword (perk transplant, side effect, hits-to-ignite); frost VFX on a chainsword actor; active-reload
  press windows, early finish, restart penalty, jam animation routed through the network, gold marker and red/gold HUD
  overlays; hip-fire fanning (edited network loaded from a mod pak); appended network records; the boot crash without
  manifests; the finisher hijack crash; the Blend2 crashes; cloned war-cry ability with new bank events; the new
  Crozius-style melee weapon on `melee_mod_1` (2026-10-15, user-confirmed: equips and attacks using the retail
  one-handed hammer animations).
- Not verified: the UNIQUE crosshair swap, the finisher damage-type string, whether fresh event-track GUIDs matter for
  cloned clips, the remaining holster glue cause.

## Gotchas
1. **New shot sound on a skin does nothing.** Cause: cosmetic skins don't run their actor's shot blueprint; the
   version's class does. Fix: edit the base class (all skins) or a `GeomHasObject` switch graph.
2. **New sound event silent.** Cause: event not in `linksSound` of the `.cls.resource`. Fix: add the link.
3. **Changing `wpnMagazineType` routed nothing.** Cause: the CP comes from `ClipSettings.magazineType`. Fix: set it in
   the version's clip settings.
4. **Edited a `.sani` and another weapon changed too.** Cause: clips are shared per wpnType. Fix: give the weapon its
   own network slot gated on a flag.
5. **Reload events fire ~22 frames late on the weapon.** Cause: converter offsets events by the clip's position on
   the concatenated timeline. Fix: `RELOAD_FULL` first.
6. **Mag flies out at the wrong time / ammo refills mid-animation.** Cause: the gameplay reload is a timer on the
   retail schedule. Fix: match clip lengths to the retail reload; play anything longer outside a gameplay reload.
7. **Shot animation stretched or replayed twice.** Cause: fire rate scales `SHOOT_1`; ADS single fire ping-pongs shot
   states. Fix: `fireRateAffectShootAnim = False`, `shootAnimationPlaybackType = "clamp"`, hold the clip.
8. **Burning `value` 500 ignites no faster than 100.** Cause: fixed heat per application. Fix: tune hit counts, not value.
9. **Side effect ignored / load issue.** Cause: missing `damage_side_effect.ssl.resource` link. Fix: add it to `linksDesc`.
10. **Weapon effect never shows.** Cause: `isAutoStart`, a huge hand-built `sfx_group`, or only one stop list. Fix:
    VfxRestart on equip, simple effects, list it in both ignore lists.
11. **Aura sat mid-blade and drifted sideways.** Cause: sub-effects parented to a scaled locator. Fix: parent to an
    unscaled locator.
12. **"Gold" effect came out purple.** Cause: SSL colours are A,R,G,B. Fix: write alpha first.
13. **Server crash at boot inside finisher init, with a reload clip's duration under a finisher's name.** Cause: a
    reused network slot was the first namesake of a finisher anim. Fix: only reuse slots with an earlier namesake;
    assert it.
14. **Markers in a wrapped clip never arrive; the rifle stays raised.** Cause: Blend2 at weight 1 passes no events. Fix:
    Switch wrappers.
15. **Client crash after wrapping a reload path.** Cause: a Blend2 under a SingleFrame (subtraction reference). Fix:
    never wrap those.
16. **Custom reload twists joints in game but looks right offline.** Cause: template clip from an older patch, frame 0
    differs from the live clip. Fix: extract from the live pak and diff frame 0.
17. **Custom hip-fire clip: arm stretched sideways, gun never fires.** Cause: hold bones off the hands and `GUN_ANIM`
    swung > 40 deg. Fix: rules 1-3.
18. **Fanning hand 45 cm off the hammer.** Cause: `GUN_ANIM` at the stance aim point, so runtime aim rotation swung the
    IK'd gun hand. Fix: put `GUN_ANIM` (and `Gun_pose`) on the gun / the contact point.
19. **Shoulder pad clipping the helmet in a custom clip.** Cause: `shoulder_R` is an animated pad channel. Fix:
    re-solve it per frame from retail.
20. **Sword floats near the hip or stays in the hand.** Cause: `melee_weapon_pivot` is a hidden holster point; switch
    clips move it into the hand. Fix: don't animate `GUN_R` onto it; pin the pivot in custom clips.
21. **"Press during the window" never triggered the blueprint.** Cause: `InputHold` needs a hold. Fix: detect via
    duration-event deactivate + body-state check.
22. **Inverted "recently" condition always true; reload swallowed for seconds.** Cause: `ConditionInvert` on
    `ConditionTriggerMorphemeEventRecently`. Fix: positive conditions only.
23. **Client crash at scene load with a new blueprint graph.** Cause: a link to a pin that doesn't exist, an undeclared
    node type, or a debug-print node in a client+authority blueprint. Fix: validate pins against `meta_desc_ssl.ps`,
    declare every node type.
24. **Melee skin crashed in the armoury, then showed a white wedge.** Cause: exporter strips `rb_*` collider streams
    and writes all-visible `.lods_base`. Fix: see the models note.
25. **Cloned ability cast hangs (charge kept, can't shoot).** Cause: ability anim task pointed at an emote (emotes
    only play through the smart / level-sequence path), and `OnFail` unwired. Fix: keep the retail anim; start emotes
    with a server `BlueprintNodeEnterSmart` and an inline smart desc; wire `OnFail` before experimenting.
26. **Red/gold HUD copies visible from the start.** Cause: extra `UiSightWidget` instances ignore Hide rules. Fix: use
    a hidable team-status widget with rule overrides.
27. **Custom HUD element in the wrong colour.** Cause: no `colorEffect`, so it inherits the crosshair tint. Fix:
    `colorEffect "ADVANCED"` + `advancedTintMult`.
28. **Cross-weapon perk accepted?** Yes - a version's `perkUids` takes any perk; use it to get an exclusive flag.

## Assets
Weapon models from AI 3D generation (Tripo) plus retail parts reused from the game's own tpls; textures baked or
repainted (models note). Animation clips were authored offline (IK posing on decoded retail clips) and written with
our own `.sani` writer. No game files are attached to this note. Saber's mod rules forbid AI-generated content in
mods (see the foundations note's Setup), so keep builds with the Tripo models private.

## Open questions
- Second cause of the holster "glue" after fast weapon switches.
- Whether event tracks of cloned clips resolve globally by track-GUID hash (fresh GUIDs were given as a precaution).
- A data path from gameplay to the reload bar's own colour.
- Whether the `noSsl` CLS route allows genuinely new firearm actor classes.
