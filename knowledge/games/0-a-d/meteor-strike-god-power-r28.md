---
kind: game
title: Meteor strike god power for temples in 0 A.D. R28
game: 0 A.D.
games_also: []
game_version: '0.28.0 (Release 28 "Boiorix", build a2cae4d69f), standalone Windows installer'
platform: windows
engine: unknown
route: data
tools: ["Python zipfile (to read public.zip)", "Pillow (procedural textures)", "um win (screenshots, input)", "pyrogenesis -autostart"]
anti_cheat: "none; open-source game. Kept to single-player; multiplayer only works if every player has the mod."
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-18'
links: []
tags: [pyrogenesis, god-power, area-damage, projectile, gui-command, targeting, particles, pyromod, javascript]
---
# Meteor strike god power for temples in 0 A.D. R28

> Temples gain a **Call Meteor** button: click any explored spot and a flaming boulder falls ~2.4 s later.
> It does quadratic-falloff crush damage (friendly fire), spawns a fireball, dust and a burning crater, and
> has a cost and a cooldown. It's a pure JS + XML folder mod with no engine changes. It runs in a real
> single-player match: a human fired it through the GUI and the logs showed 30/30 units killed and a barracks
> at 2000 → 1444 HP.

## Setup
- 0 A.D. 0.28.0 on Windows 10. Game data lives in `binaries/data/mods/public/public.zip` (3.5 GB). The release
  ships XML/JS as plain zip entries and textures only as `*.cached.dds`. User mods go in
  `Documents\My Games\0ad\mods\<name>\` with a `mod.json` (`"dependencies": ["0ad=0.28.0"]`).
- To read the source, extract only `.js/.xml/.json/.txt/.rnc` from public.zip and mod.zip with Python
  `zipfile`, outside the repo. That's roughly 2-3 minutes; skip `maps/`.
- Dev install: a directory junction from the mods folder to the git working copy. Launch with
  `-mod=public -mod=<yours>`.

## Route and why
`data`: the whole gameplay layer is SpiderMonkey JS (simulation components and helpers) plus XML entity
templates and a JS/XML GUI, all overridable or extendable from a mod folder. There was no reason to touch the
C++. The other option, a ranged "attack" with a huge range on a building, can't target ground and can't have
a cost or cooldown button, so a custom command was the right shape.

## How the game works (what we had to learn)
- **Load order.** `simulation/components/interfaces/`, then `simulation/helpers/`, then
  `simulation/components/` are all loaded into one global, alphabetically per folder. Mod files merge into the
  same folders, so `helpers/MeteorStrikeCommands.js` runs after `Commands.js`, and a component named `M…` runs
  after `GuiInterface.js`. The mainlog prints every "Loading simulation script …" line, which confirms it.
- **Commands.** `helpers/Commands.js` declares global `var g_Commands = {…}`. `ProcessCommand` puts the
  entities of `cmd.entities` that the player can control into `data.entities` (`cmd.entities` stays as sent),
  then calls `g_Commands[cmd.type](player, cmd, data)`, so a handler reads `data.entities`. Adding
  `g_Commands["meteor-strike"]` from a helper is enough; the GUI sends it with `Engine.PostNetworkCommand`.
  It's network-synced and replay-safe. Treat `cmd.x/z` as untrusted: check finite, in map bounds, and LOS.
- **Area damage.** `AttackHelper.CauseDamageOverArea({type, attackData: {Damage: {Crush: n, …}}, attacker,
  attackerOwner, origin: Vector2D, radius, shape: "Circular", friendlyFire})` applies quadratic falloff,
  resistances and death. With `friendlyFire` it hits all players.
- **Visual projectile.** System component `ProjectileManager.LaunchProjectileAtPoint(launch3D, target3D,
  horizSpeed, gravity, actorName, impactActorName, impactLifetime)` returns an id. Flight time is
  `horizontal distance / horizSpeed`, and gravity only bends the arc. Call `RemoveProjectile(id)` at impact.
  The actor can be any mesh actor with particle props. Particles are emitted in world space, so a trail
  forms by itself.
- **Delayed impact that survives the caster.** Make your own scripted system component
  (`Engine.RegisterSystemComponentType`; it's auto-instantiated on `SYSTEM_ENTITY`) and call
  `Timer.SetTimeout(SYSTEM_ENTITY, IID_X, "Impact", ms, data)`. The data object (Vector3D included) is
  serialised with the timer, so a save mid-flight should keep the strike (not tested; see Verification).
- **Feeding state to the GUI.** The GUI only sees `GuiInterface.GetEntityState`. Wrapping
  `GuiInterface.prototype.GetEntityState` from a later-loaded component file works because instances share
  that prototype. New GUI-callable functions need `GuiInterface.prototype.exposedFunctions.Name = 1`.
- **GUI command button and targeting.** `gui/session/session.xml` loads every `.js` in `gui/session/`
  alphabetically. `unit_actions_meteor.js` sorts right after `unit_actions.js` (`.` < `_`). Steps:
  1. Add `g_UnitActions["x"]` with `execute`, `getActionInfo` and only a `preSelectedActionCheck`. An
     `actionCheck` would hijack normal right-clicks.
  2. Rebuild `g_UnitActionsSortedKeys`, which is computed at load.
  3. The button is `g_EntityCommands["x"]` with `getInfo` (tooltip, icon from
     `art/textures/ui/session/icons/`, `count`, `enabled`). Its `execute` sets
     `inputState = INPUT_PRESELECTEDACTION; preSelectedAction = <your const>`.
  4. The next left click calls `execute(Engine.GetTerrainAtScreenPoint(…), action, …)`.
  5. The command row shows at most 6 buttons, so put yours first (`g_EntityCommands = Object.assign({x: …},
     g_EntityCommands)`).
- **Throwaway visuals.** `Engine.AddLocalEntity("special/foo")` with a template whose parent is
  `special/actor`, plus a `Decay` block (`DelayTime` = lifetime, `SinkRate` 10000). This is the same trick
  as `special/target_marker`. When the entity dies, particles already emitted keep fading out, so a
  `<start_full/>` emitter on a 0.3 s entity gives a one-shot burst.
- **Actor limits.** A decal (`<decal width depth …/>`) can be a *prop* of a mesh actor (see the campfire),
  but decal-only and particle-only actors can't hold props. Hang everything off a mesh. The rubble burn
  decal `props/decal_destruct_medium.png` makes a ready-made scorched crater.
- **Sound.** `SoundManager.PlaySoundGroupAtPosition(group, pos)` needs **mono** files: a stereo file in a
  group without `<Omnipresent>1</Omnipresent>` logs a warning and isn't positioned.
  `PlaySoundGroupForPlayer(group, player)` plays the group at the map origin, so it's only heard everywhere
  when the group sets `<Omnipresent>1</Omnipresent>`; it's limited to that player only when the group sets
  `<HeardBy>owner</HeardBy>`, otherwise every client plays it on every call.
- **Cheats are off under `-autostart`.** For a test scene, a dev-only mod with a system component's
  `OnInitGame` can spawn entities (`Engine.AddEntity` + `Position.JumpTo` + `Ownership.SetOwner`), add
  resources, reveal the map (`RangeManager.SetLosRevealAll(-1, true)`) and set diplomacy.

## Build steps
1. Mod folder with `mod.json`, then add:
   - `simulation/components/interfaces/MeteorStrike.js` (`Engine.RegisterInterface` for both components);
   - `simulation/components/MeteorStrike.js` (the per-building component, the system manager, and the
     GuiInterface wrap);
   - `simulation/helpers/MeteorStrikeCommands.js` (the `g_Commands` entry);
   - `gui/session/unit_actions_meteor.js` (the action and the button).
2. Copy `template_structure_civic_temple.xml` into the mod and add a `<MeteorStrike>` block (schema: Cooldown,
   Cost via `Resources.BuildSchema("nonNegativeInteger")`, FallTime, Radius, FriendlyFire, Damage). All 19
   civ temple templates inherit it.
3. Add actors under `art/actors/props/meteor/` (meteor = a gaia stone-mine mesh plus flame/smoke particle
   props; crater = the same mesh plus the destruct decal and fires), particles in `art/particles/` with
   wrapper actors in `art/actors/particle/`, and three `special/meteor_*` Decay templates.
4. Test with `pyrogenesis -mod=public -mod=meteor_strike -mod=meteor_testbed -autostart=skirmishes/acropolis_bay_2p
   -autostart-civ=1:athen -autostart-civ=2:pers`. Add `-autostart-nonvisual` for a headless sim and log check.
5. Package: `git archive --format=zip` of the mod folder, renamed `.pyromod`, with `mod.json` at the zip root.

## Verification
- The oracle was the game logs. `interestinglog.html` holds warnings and errors only; `mainlog.html` holds
  everything plus your `log()` lines. The testbed logged the HP of all 31 targets before and after every
  impact, wrapping `MeteorStrikeManager.prototype.Impact`.
- Sim path, auto-strike: 16/20 dead at the first tuning; later 30/30 dead and the barracks at 2000 → 1492.
  It was re-run headless after the sound change, with no errors.
- GUI path: a human selected a temple, saw the tooltip and the countdown, clicked the button and then the
  ground. The log showed impacts from both temples, 30/30 dead and the barracks at 2000 → 1444 → 545.
  Screenshots confirmed the button, the cooldown number and the tooltip.
- **Not verified:** the `.pyromod` installing through the game; multiplayer sync with two real clients;
  saving and loading mid-flight; how the final mono "incoming" roar sounds (headless runs have no audio).

## Gotchas
1. **The game failed to start a match with "Registered component has unrecognized 'OnImpact' message handler
   method".** **Cause:** any component method named `On…` is treated as a message subscription and checked
   against the known messages. **Fix:** never name helpers `On*` (renamed to `HandleImpact`). The failed
   start also left the setup screen able to crash the game (access violation) when Start was pressed again.
2. **"OpenAL: stereo sounds can't be positioned: …thunder_10.ogg".** **Cause:** the thunder files are
   stereo, and positional playback needs mono. **Fix:** play stereo groups with `PlaySoundGroupForPlayer`
   for every player (it became a global "omen"); give that group `<Omnipresent>1</Omnipresent>` and
   `<HeardBy>owner</HeardBy>` (see Sound above). Use mono files (`audio/attack/fire/sz*.ogg`, destruction
   sounds) at the impact position. Check the channel count in the Vorbis identification header: it's the
   byte at offset 11 from the start of `\x01vorbis`.
3. **Test units already damaged before the strike.** **Cause:** the defender's towers and civic centre were
   shooting the staged army. **Fix:** set players 1 and 2 to neutral in the testbed (`Diplomacy.SetNeutral`).
   Meteor friendly fire still hits everyone.
4. **`CauseDamageOverArea` appends ".Splash" to `data.type` once per target.** It's harmless unless you rely
   on the type string. Pass a fresh object per call.
5. **`-conf=windowed:true -conf=xres:… -conf=yres:…` didn't give a fixed-size window,** and full-screen
   captures sometimes came back as a 160×28 frame. **Fix:** check the client rect (`um win drive … rect`)
   and re-capture once the window is in the foreground.
6. **In Git Bash, `um` picked the WindowsApps `python3` stub, which has no Pillow.** **Fix:**
   `PYTHONPATH=<plugin root> python -m um …`.
7. **Driving input while the human plays clashes.** They selected things, moved the camera and closed the
   game mid-setup. Check `um win drive --proc pyrogenesis idle`, and agree on a hands-off window before a
   scripted take.

## Assets
No generative models. The command icon (64×64) and the warning-ring decal were drawn procedurally with
Pillow. Everything else is the game's own meshes, textures, particles and sounds, referenced by path rather
than copied.

## Cost and time
About 1.5 h of agent wall-clock for recon, reading the source, the slice, verification and packaging.

## Open questions
- Teach Petra (the AI) to use it: `simulation/ai/petra` would need a "god power" decision.
- A tech or phase requirement instead of plain cost, and a hotkey.
- A screen shake or flash would need engine (C++) support. The particle flash is the closest in pure data.
