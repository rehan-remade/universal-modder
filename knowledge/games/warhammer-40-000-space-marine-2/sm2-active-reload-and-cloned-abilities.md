---
kind: game
title: "Space Marine 2 active reload (press window, jam, HUD flash) and cloned abilities via enum extension"
game: "Warhammer 40,000: Space Marine 2"
games_also: []
game_version: "Steam build 25799387 (Patch 15.1, Oct 2026); built Oct 8-16 2026, ability work Oct 8-23 2026. Mod Tools app 3856330 build 25506153"
platform: windows
engine: unknown
route: data
tools: ["Saber SM2 Mod Tools (ModEditor docs, enum extension sample)", "Python 3 (zipfile, struct, numpy, PyYAML)", "own Morpheme .nmb patcher", "own .sani clip writer and event-track codec", "own Wwise bank writer", "WwiseConsole 2019.2", "own sslbin disassembler (reading compiled logic only)"]
anti_cheat: "EasyAntiCheat. Everything here uses Saber's official mods folder (client_pc/root/mods), which flags the session 'Mods Detected' (private lobbies, separate progression). No injection, no EAC interaction, PvE only."
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-29
links: []
tags: [space-marine-2, saber, active-reload, reload, firearm, morpheme, animation-network, action-controller, blueprint, hud, wwise, abilities, enum-extension, war-cry]
---

# Space Marine 2 active reload (press window, jam, HUD flash) and cloned abilities via enum extension

> An active-reload mechanic for Space Marine 2's firearms: during a reload the player can press Reload again; a gold
> sweet spot drawn on the crosshair's ammo arc finishes the reload early with a faster tail animation, a press too early
> or too late plays a jam animation followed by a forced vanilla reload, with red/gold HUD flashes, sounds and a voice
> line. All of it is data: event markers added to the Marine's reload clips, action-controller bindings, the Marine
> client blueprint, HUD widget overrides and switches patched into the Marine's Morpheme network. It works in game on the
> bolt-rifle family; the extension to every reloading weapon is built but not yet confirmed. The second half lists what
> we learned since the first notes about cloning abilities on new enum values (including a boot crash from one bad
> indent). Base facts this note builds on (input during actions, the reload timer, crosshair chain, network rules) are in
> [the weapons note](sm2-weapons-skins-reloads-perks-vfx-and-sounds.md); `.nmb` / `.sani` formats in
> [the NPC/animation note](sm2-new-enemies-npc-classes-and-morpheme-animation.md).

## Setup
- Steam build 25799387 (Patch 15.1). Base every edit on the CURRENT retail `default_other.pak` /
  `default_animation.pak` / `resources.pak` copies, then merge with whichever installed mod wins each shared file (the
  first pak alphabetically, see the foundations note).
- Files touched: the 15 Marine reload clips (`tacticus_wpn<NNN>_..._reload*.sani`, event chunk only), weapon-change
  clips (event chunk only), `morpheme/primaris/primaris.nmb` + `.mr.resource`, `actions/action_controller_project.sso`,
  the Marine client blueprint `blueprint_marine_client_and_authority_sounds.sso` (+ its `.sso.resource`),
  `firearm_base.cls` (`timePercentToReload`), the crosshair clip-bar and HUD screen `.sso` files, an own sound bank.
- Oracle: a testing arena plus screen recordings stepped frame by frame; an on-screen `BlueprintNodeDrawModUiLog`
  line while wiring the blueprint.

## Route and why
The reload itself is compiled script (`reload_logic`): it starts the weapon's `RELOAD_FULL` and a timer, credits ammo at
`timePercentToReload` and ends on the timer. It cannot be replaced, so the mechanic is built around it:
- a second Reload press is let through by the retail reload action filter and turned into
  `CommandInterruptCommand RELOAD` by an action-controller binding conditioned on clip markers;
- the commit point is moved BEFORE the gold window, so an interrupted reload keeps its ammo;
- the outcome is classified in the Marine client blueprint and drives control parameters (CPs) of the Marine network,
  which routes to jam / clean / tail clips through patched switches.
A perk route (`PerkApplicationReloadFirearm` with 100 % refund, as a retail gun-strike perk does) was considered and
dropped: perks are server-only and cannot share a blueprint with client input, HUD and animation nodes.

## How the game works (what we had to learn)

### Event layout on each reload clip
- All timing is markers appended to the clip's EXISTING `event`/`Sound` payload track (the network only emits tracks
  its anim nodes cached; never add a new track and never use Footsteps). Per clip, as fractions of its own length:
  an arm marker near 0.08; one press marker every 1 % from 0.08 to the last window end (minus 80 ms, so a press binding
  "recently within 80 ms" reaches the end exactly); duration windows that TILE the clip: fail [0.08, 0.30], gold
  [0.30, 0.575] split into three sub-zones, late [0.575, end]; fire-block markers every 40 ms up to the clip's own
  `checkExit` end (2 % spacing left gaps on long clips).
- The drawn gold slice covers only 0.35-0.525: the hidden window is ~0.14 s wider on each side, because presses exactly
  at the edge of what you see felt "dead centre only".
- Commit: `firearm_base.cls` `timePercentToReload` 28 (retail 50). Side effect: any reload cancelled after 28 % keeps
  its ammo. Some versions run the reload clip at `reloadAnimSpeedScale` 0.9, so the clip can drift from the bar.
- Clip lengths range from 1.0 to 4.0 s, so a shared timer cannot fit every weapon. Each clip carries id markers at
  0.01/0.04/0.07 that write FLOAT blueprint variables (tail length, penalty length, sub-zone timings); the `Delay` nodes
  read them through the retail `GetVariable` -> `<Delay>/duration/cb` pin pattern.

### Bindings (action controller)
- One press binding: Game.Reload + body state RELOAD + recently(press marker, 80 ms) -> `CommandInterruptCommand RELOAD`,
  with `shouldCheckInputOnActivation = False` (with True, a key already held when the binding activates is used at once).
- Swallows at priority 200 (the filter keeps only the highest-priority action per input): block Fire during the jam
  and its follow-up; block Reload for a short time after a fail. Build them only from POSITIVE recently-conditions plus
  NOT body-state RELOAD: an inverted recently-condition reads as always true and held a swallow for 1.8 s.
- A priority-210 pass after a gold hit (recent gold marker AND NOT RELOAD -> `CommandReload`) removed the "R needs four
  presses after a perfect" lag. (Built, untested.)
- Weapon swaps must not count as a press: the 15 weapon-change clips carry a swap marker on their event track and the
  bindings require it NOT recent; the blueprint's busy list also holds jetpack hover/thrust, hanging, riposte, hook
  target and drop-pod states.

### Classifying the outcome (Marine client blueprint)
- The proven detector is a duration-event subscription's `OnDeactivate`: it fires when the clip is CUT, so "which
  window was active when the reload was interrupted" is the outcome. A window that ends naturally also deactivates;
  a busy/state check right after filters those. No pass/arm gating is needed once the windows tile the clip.
- Nodes that never fired for this in the Marine client blueprint: `BlueprintNodeInputHold` (fires only after its hold
  time), a body-state `OnExit` subscription, and logic on markers of the JAM clip itself (see Gotchas). Nodes proven:
  Morpheme event and duration-event subscriptions, If, variables, set Morpheme parameter, `WaitOneFrame`, check body
  state, `Delay`, `CommandReload`, story voice-over playback, `GetLocalPlayer` + `ActorsCompare` as a local-player guard,
  `BlueprintNodeOverrideWidgetsVisibility`.
- Outcomes: gold sub-zone k -> `Debug_Float1` = 3..5 (tail clip k); fail -> 1 (jam) plus `wpn_reload_type` = 2 to
  re-enter the network's reload state, a voice line and a fail sound; late fail -> a cosmetic clean reload (the magazine
  is already full past the commit, so a real `CommandReload` is cancelled by the "clip full" check). Delays then reset
  the CPs; `wpn_reload_type` 2 is held for min(0.45 s, half the shortest clip).

### Network side (`primaris.nmb`)
- Live users of each reload clip, found by walking the reload state: rifles play through one regular (`sani`) switch
  and two `sani+` switches (with nested sub-switches for some rifles); pistols through three switches plus a feather
  blend. Two sibling switches per family only feed SingleFrame subtraction references: never wrap those.
- Each live use gets a floor Switch wrapper (cloned from a never-entered debug switch, see the weapons note for the
  selection flags) with children [retail, jam, clean, tail1, tail2, tail3] keyed on `Debug_Float1` 0..5. Switches pass
  their active child's events; a Blend2 wrapper passes none.
- Capacity: only ~22 free same-size anim records existed. Appending full records at the end of the network asset and
  repointing the node-offset table (asset size grown, node COUNT untouched) loaded and worked in game. Recycling the
  never-entered debug tree's IDs this way gives ~300 anim nodes and ~90 switches: enough for 43 wrapped routes over
  15 clips.
- The jam is ONE clip: jam motion followed by the retail reload (the jam's last frame equals the retail reload's
  frame 0), so the follow-up reload is seamless. Its frame 0 equals the live retail clip's frame 0 (the additive layers
  subtract it). The "clean" child is an unmarked copy of the retail reload: a forced vanilla reload that cannot itself
  trigger active reload. Tail clips are the retail reload from the cut point at 1.3x speed.
- Weapon -> clip map (by `wpnType`, floor thresholds): wpn000 heavy bolt pistol, wpn050 inferno pistol, wpn10/103/17/151
  the bolt-rifle family (the auto bolt rifle at wpnType 1.01 takes the wpn10 branch), wpn102 heavy bolt rifle,
  wpn110-113/120/121 the other rifles, wpn140/141 melta. Heavy weapons and the plasma pistol have no reload clip, so no
  active reload.

### HUD
- The reload progress on most rifles fills the AMMO ARC under the crosshair (`ui_hud_crosshair_clip_size_bar`, state
  `reload`), not a ring. The gold slice is a piece of the arc's own texture between two copies of the rotating mask,
  visible only in the reload state; a 2x11 px tick keyed across the reload frames orbits with the fill.
- The red/gold flash is a hidable team-status widget instance with an inline view (the route that respects Hide rules,
  see the weapons note). Positions are in the 1920x1080 layout; the vertical box ignores the content pivot and does NOT
  re-anchor on content, so move the attach point, not the children. Custom 92x22 BGRA textures (same size as the arc
  texture) loaded fine. Fades: inline override of the view's `animFadeIn`/`animFadeOut` frames (12 in, 36 out worked);
  the widget host plays them on visibility changes and hides only at the end of the fade-out.
- The stock white bar cannot be hidden on its own (it is part of the sight widget), so the overlay covers it with a few
  slightly offset copies. A true recolour would mean a second sight instance, which ignores Hide rules: don't.

### Sound and voice
- Voice lines: story voice-over playback with `StopVoiceOver` first and the `esd_no_subs` category (voices note).
  Vanilla "Reloading!" chatter is a SKIP-category line, so padding our jam lines to ~2.6 s made the engine skip the
  vanilla line that followed. Verified.
- Gold-hit and fail stingers: an own bank that clones a retail Sound and its actor-mixer chain under NEW ids, with the
  cloned parents' child lists pruned to our objects; event ids are FNV-1 of the lowercase name (voices note). The same
  route later carried a weapon's custom burst sound (verified). Stingers first mixed at -23 LUFS were reported too
  quiet and went to ~-19 LUFS.

### Cloned abilities: what we learned since the first notes (2026-10-08..23)

#### Enum extension, practically
- Retail `ssl/abilities/ability_consts_library.ssl.resource` (in `resources.pak`) already has an empty `extension:`
  field: set it to `ability_consts_library.ext`; the `.ext` is YAML with SPACES only (Saber's sample:
  `ModEditor/documentation/samples/enum_extension.zip`). The `meta_desc_ssl.ps` edit in the tutorial is for the editor
  only; the runtime does not need it.
- **One bad indent drops the whole extension.** Adding a value at a 3-space indent under existing 4-space items is a
  YAML error; the engine silently ignores the entire `.ext`, and the first `ability_library` entry using ANY extended
  uid crashes the client at start (`error.yaml`: `gsCreateSslMain() failed ... 'null' object`; script stack
  `AbilityLibrary.ReloadAbilityDescriptions` > `StringToEnum("<uid>")`). Parse the file with a YAML loader after every
  edit and diff the value list. Several mods that add uids must share ONE merged `.ext` (the first pak wins it), so a
  rebuild of the winning mod without your values breaks your abilities.
- Fallback if the extension misbehaves: Saber's compiled modder uids `ultimate_mod_1..5`, `melee_mod_1..5`,
  `equipment_mod_1..5`.
- New uids also work for NPC abilities: a boss move on a new `AbilityUid` (an anim-table entry, a server ground-burst
  at a locator) loaded once the `.ext` parsed (see the NPC note's boss section).

#### Making the clone look and sound different
- Recolour the war-cry effect per class with a PARTIAL override in the class's sfx list:
  `<new fx name> = { ...changed colours... __type = "<retail fx name>" }`; skip distortion emitters and mask emitters.
  Built with the clone; the clone itself worked in game, the recolour was not separately confirmed.
- New sound events in an existing bank worked in game (event resource + `linksSound`, voices note). Earlier swapping the
  retail shout media also changed the shout for the retail class that shares it.
- A clip-driven shout (a Morpheme duration event in the emote clip -> the Marine sound blueprint) can be muted for one
  ability only with a `BlueprintNodeGate` opened/closed by `BlueprintNodeSubscribeOnAbility` OnActivated/OnDeactivated.
- One controller node can be overridden inside `ability_library` (retail precedent: a grenade). Swapping the ability's
  anim link to a new anim-table entry works only for ordinary clips: emotes play only through the smart / level-sequence
  path, and the war-cry controller leaves `OnFail` unwired, so a failed task hangs the cast. A `BlueprintTimeLibraryDelay`
  in such an override needs `blueprint_time_library` linked in the shipped `ability_library.sso.resource`.
- Other routes found but not tried: `AbilityModuleLogicSmart` (server module with `smartLinks` keyed by actor type,
  e.g. `Humans.Primaris.<smart>`); `factoryUid` is a free string, so a clone could get its own server logic; running the
  controller on `Delay` timers (effect, then complete-cast) while a server `BlueprintNodeEnterSmart` plays the emote.
- A different war-cry MOTION for one class only would need a private copy of the Marine network (all Marines share
  `primaris.nmb`), so we did not do it.

## Build steps
1. Extract the live reload clips, weapon-change clips, `primaris.nmb`, `.mr.resource`, action controller, Marine client
   blueprint and its resource, clip-bar and HUD files.
2. Append markers and duration windows per clip (lengths, `checkExit` end, per-clip id markers); keep track GUIDs.
3. Write jam (jam + reload), clean and tail clips with frame 0 equal to the live clip; `.sani.resource` + `.mr.resource`
   links for each.
4. Patch the network: switch wrappers on every live user (never the SingleFrame refs), appended anim records, a
   name-lookup assert so no new node becomes the first namesake of a finisher.
5. Bindings, blueprint (declare every node type in the `.sso.resource` `linksDesc`), commit point, HUD widgets, bank.
6. Ship ZIP_STORED; test the bolt rifle first, then one weapon per clip family.

## Verification
- In game on the bolt-rifle family (bolt rifle, auto bolt rifle): window press finishes the reload early and keeps the
  ammo; early press restarts the reload (first penalty design); gold slice on the ammo arc; jam routed through switch
  wrappers and ending on timers; seamless jam -> reload clip; voices cycling every time; red overlay aligned within
  ~1 px; team-status overlay with custom textures and fades ("look and fade OK"); appended network records loading; a
  tester verdict of "seems ok" on the complete rifle loop.
- Built, not confirmed in game: the all-weapon expansion (43 routes, per-clip float timers), the held-key fix, swap
  markers, the after-perfect pass, pistol alignment of the drawn slice (pistol windows end at clip 0.47).
- Personal-use limit: the jam motion was retargeted from a donor clip outside SM2, so that build stays private. The
  mechanic itself needs only retail assets (the clean retail reload works as the penalty; that is what pistols use).

## Gotchas
1. **The wrapped jam never ends; the rifle stays raised everywhere.** **Cause:** the wrapper was a Blend2, which at
   weight 1 passes no events, so no marker could reset the CPs. **Fix:** Switch wrappers, plus timer (`Delay`) backstops.
2. **Even under a Switch, markers placed on the jam clip never arrived.** **Cause:** unknown (suspect: events from the
   reload state only reach listeners during a gameplay reload). **Fix:** drive jam logic from the RETAIL reload clip's
   markers, blueprint variables and `Delay` timers, never from the jam clip.
3. **First jam crashed the server at boot.** **Cause:** a reused anim slot was the first namesake of a finisher anim
   (server lookups by leaf name). **Fix:** only reuse slots with an earlier namesake; assert it in the builder.
4. **Client crash after wrapping more paths.** **Cause:** a Blend2 under a SingleFrame subtraction reference. **Fix:**
   leave the reference switches alone.
5. **Manual reloads never jammed, empty-mag reloads did.** **Cause:** a RELOAD-exit reset in the blueprint cut the jam,
   not a separate manual-reload path (there is none). **Fix:** reset on timers, not on body-state exit.
6. **Random jams after reloads cut short by firing or dodging.** **Cause:** an "armed" flag lingered for seconds. **Fix:**
   classify by which duration window was cut, with a busy check.
7. **Next reload played the jam or tail clip.** **Cause:** `Debug_Float1` stayed set for the last ~0.3-0.4 s of a tail
   or jam. **Fix:** reset at clip end minus 0.05 s from the per-clip timer.
8. **Presses at the very edge of the gold slice did nothing.** **Cause:** the binding's marker zones and the
   blueprint's windows disagreed, leaving dead slivers. **Fix:** one press-marker run and windows that tile the clip.
9. **A late fail jammed but no reload followed.** **Cause:** the magazine was already credited, so `CommandReload` was
   refused. **Fix:** play the clean reload cosmetically instead.
10. **Pressing R right after a jam started another reload / the vanilla "Reloading!" line played over the jam line.**
    **Cause:** the retail Reload binding re-activated on the held key; the chatter line fired after ours. **Fix:** Reload
    swallow during jam + follow-up; pad the jam line so the SKIP-category chatter is skipped.
11. **Gold flash never showed while red did.** **Cause:** a game-mode name gate on the gold rule. **Fix:** remove the
    gate.
12. **Extra crosshair copies for the flash were visible from the start.** **Cause:** sight widgets re-show themselves.
    **Fix:** team-status widget host (weapons note).
13. **Weapon swaps counted as fails or perfects.** **Cause:** swap clips cut the reload windows. **Fix:** swap markers
    on the weapon-change clips + a NOT-recent condition and a two-frame gate.
14. **The hold-R press fired immediately on activation.** **Cause:** `shouldCheckInputOnActivation = True`. **Fix:** set
    it False (decompile-derived, fix not yet confirmed).
15. **Retargeted jam held the rifle up at the helmet.** **Cause:** the donor's gun motion (47 deg / 30 cm) kept 1:1.
    **Fix:** scale the gun motion (0.35-0.5) and the spine, and keep the gun body a minimum distance from the helmet.
16. **On some donor clips the rifle floated off the hands.** **Cause:** the donor's weapon bone was gun-rigid only in one
    clip; in others it locked rotation to one hand while sliding 19-40 cm. **Fix:** make the gun follow the holder hand
    (previews only so far). Donor data may also be left-handed (forward = up x left): check the basis determinant.
17. **Client crash at start in `StringToEnum` after adding one more uid.** **Cause:** wrong YAML indent; the whole `.ext`
    was dropped. **Fix:** spaces at the file's existing indent; validate with a YAML parser before packing.
18. **Your abilities break after another mod updates.** **Cause:** the merged `.ext` / `ability_library` are single-winner
    files and the other mod's rebuild lacks your entries. **Fix:** assert your values in the winning copy when building.

## Assets
HUD textures (arc flash body and core, 92x22) were generated procedurally from the retail arc's shape. Clips were
written with our own `.sani` writer from the live retail clips. The jam motion and the stinger sounds came from sources
outside SM2, so builds containing them stay private; nothing from any game is attached to this note.

## Open questions
- Why markers on the jam clip never arrive even under a Switch wrapper.
- Whether anim nodes resolve event tracks globally by GUID hash (cloned clips were given fresh GUIDs as a precaution).
- Whether the per-clip timers line up on the pistols, whose windows end at 0.47 of the clip.
- A data path from gameplay to the reload bar's own colour (still none).
