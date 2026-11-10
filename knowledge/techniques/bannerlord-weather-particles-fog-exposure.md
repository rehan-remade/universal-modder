---
kind: technique
title: "Weather in Bannerlord mods: particles, fog, exposure, map layers and campaign AI"
status: working
game: "Mount & Blade II: Bannerlord"
games_also: []
game_version: "v1.4.8 (Steam, Windows 10) with the NavalDLC module; Bannerlord.Harmony, UIExtenderEx and MCM v5 from the Workshop"
platform: windows
engine: unknown
route: loader-api
tools: ["Bannerlord module system (C# net472 SubModule, Prefabs XML)", "Bannerlord.Harmony", "ilspycmd", "an in-mod autotest that drives custom battles and the campaign map and takes screenshots"]
anti_cheat: "none (single player only)"
agents: ["Claude Code (Opus 5.5)", "Claude Code subagents"]
humans: []
date: 2026-11-11
links: []
tags: [bannerlord, weather, particles, prefabs, fog, exposure, campaign-map, ai, harmony, sound, performance]
---

# Weather in Bannerlord mods: particles, fog, exposure, map layers and campaign AI

> What the engine really does when a mod adds rain, snow, hail, dust and fog to battles and the campaign map, re-tunes the scene's
> atmosphere and exposure, and makes AI lords react to weather. Every item was found while building a full weather overhaul module.

Evidence tags: **[V]** seen in the running game (screenshots or log), **[M]** measured from 1:1 screenshot crops or the mod's frame
log, **[S]** static analysis of the game DLLs only.

## When to use it
- You draw your own weather particles in missions or on the campaign map, or change fog, sky or exposure at run time.
- You hurt troops from script (lightning, hail) or reweight the AI's hourly decisions from the weather.

## Setup
- A C# SubModule (net472) with Harmony; weather bodies are prefabs in the module's `Prefabs/` folder that override a vanilla or
  module particle effect with `<effect base_effect="{guid}"><emitter_overrides>`. They are instantiated at run time and moved
  with the camera each tick.
- Verification is screenshots read at 1:1 crops (mean sRGB and the share of pixels at 250+), not the reduced preview: weather
  particles that look absent at 960 px wide are often there, and the reverse.

## Route and why
loader-api: missions get a MissionLogic (spawn and move particle entities, write the atmosphere each tick), the map gets a view
behaviour, AI gets one Harmony postfix. No native hooks were needed.

## How the game works (what we had to learn)
- **Sky-visibility flags are not overridable. [V]** The emitter override `use_sky_visibility=false` is ignored. Vanilla emitters that carry
  the flag (`psys_game_snow`, `psys_game_rain`, `rain_mid`, the splash) stay invisible unless the engine's own weather object for that
  scene is active. Copy the effect into an unflagged base, or drive the engine's rain/snow density.
- **Vanilla map weather emits above the camera. [V]** `campaign_*` rain and snow emit 12-16 units above a root at ground + 26, which
  is above the map camera at the default zoom (38), and their clouds fade out when looked down on. Spawn your own bodies just below the
  camera instead.
- **A grain sprite can be a cluster. [V][M]** A base effect whose texture shows several grains draws them all in one quad:
  `particle_size` is the quad, not the grain. One such sprite drew about 5 grains, each about 1/5 of the quad, so hailstones sized as
  one quad per stone were 3-7 mm and invisible. Size the quad from the grain you measured in game.
- **Resting particles need `emit_on_terrain`. [V]** An emit box placed at the ground height under the camera is a flat plane: on any
  slope half of it is underground. After 55 s of hail no stone showed on a sloped field. The emitter flag
  `<flag name="emit_on_terrain" value="true" />` puts them on the terrain everywhere.
- **Dense particle boxes make hard edges. [V]** A box of overlapping translucent particles around the camera (20-60 m) is opaque
  inside and ends in a straight line where it stops. Lowering alpha did not help, because the overlapping particles saturate. What
  worked was letting the fog carry visibility (density from the visibility you want, fog start pulled to the camera so there is no
  clear ring) and keeping only sparse particles for motion.
- **Run-time exposure works. [V][M]** `Scene.SetMinExposure`, `SetMaxExposure`, `SetTargetExposure` and `SetMiddleGray` exist and
  are honoured when written every frame (the only way they were tested). The noon TOD (`Native/Atmospheres/TOD_12_00_SemiCloudy.xml`) has `min_exposure` -11.2
  against `target_exposure` -11.0, so a bright snow field can only darken 0.2 EV and clips (100 % of a near-snow crop at 250+).
  Lowering the floor by 2 EV took it to 0 % clipped, about 2.2 stops over mid-grey. The floor for campaign scenes is
  `AtmosphereInfo.PostProInfo.MinExposure`; custom battles read it from the TOD file.
- **Custom battles keep their TOD sky. [V]** A custom battle loads a semi-cloudy TOD. Writing fog and sky brightness later cannot add
  clouds, so light rain falls from a sunny sky there; only heavier weather's fog hides it.
- **Hourly AI scores. [S][V]** `AiPartyThinkBehavior.PartyHourlyAiTick` calls `CampaignEventDispatcher.AiHourlyTick(party, params)`,
  then reads `params.AIBehaviorScores` to choose. On 1.4.8 `MbEvent.AddNonSerializedListener` prepends, so the listener added last runs
  first, before the vanilla scorers. A Harmony postfix on `CampaignEventDispatcher.AiHourlyTick` runs after every scorer on any
  version. In game, lords caught in a blizzard switched from patrols to the nearest friendly castle or town.
- **The campaign year. [S]** `CampaignTime.DaysInYear` is 84 normally and 24 in the Fast acceleration mode, so scale the day of the
  year before you map it to a month.
- **Sound events have no volume. [S]** `TaleWorlds.Engine.SoundEvent` exposes Play, Stop, SetParameter, SetSwitch and position, but no
  gain or fade, and `module_sound` beds have no gain parameter unless the bank defines one. Changing a bed is a hard Stop and Play cut.

## Build steps
1. Copy each weather effect into a module prefab with `emitter_overrides` (colour, alpha, size, rate, box, life, billboard type).
   Keep a cap (`max_alive_particle_count`) on every emitter.
2. Spawn the bodies when wanted, `SetGlobalFrame` them to the camera each tick (or to the ground height under it), drive density
   with `SetRuntimeEmissionRateMultiplier`, and hide them with `SetVisibilityExcludeParents(false)` instead of removing them every
   frame.
3. Read the scene's fog/sky baseline once (the campaign `AtmosphereInfo`, or the custom battle's TOD file), plan targets from the
   weather, and write the fog, sky and exposure each tick. Give way if another mod changes the fog.
4. Damage from weather goes through `RegisterBlow` with an attacker-less blow that carries `NoSound` only (see gotcha 1).

## Verification
- An in-mod autotest opens a custom battle (season, weather steps, troops), forces each weather for N seconds, writes the shown layers
  and a 5 s average frame time to the log at every shot, takes screenshots, and quits. A map mode loads a save paused, and a campaign
  mode runs days on a copy of the save and hashes every `.sav` before and after.
- Frame cost (RTX 4090, 4K, 300 agents marching, 5 s average): clear 2.7 ms, rain +0.9, hail +1.5, snow +2.2, sandstorm +2.4,
  dust +3.3, blizzard +4.2 [M]. The on-screen counter is capped by `max_framerate` in `engine_config.txt` (200 by default), so measure
  from the mission's own dt.

## Gotchas
1. A scripted `Blow` with `KnockDown`, `CanDismount` or `MakesRear` and no attacker (owner -1) crashes natively in
   `Agent.HandleBlowAux`. Weather blows carry `NoSound` only. [V]
2. `Mission.GetNearbyAgents` returns an agent twice at each 40-agent page edge and never returns mounts: dedupe by index and add each
   rider's mount yourself. [V]
3. Map decals ignore runtime textures; a decal needs a texture the game already packs (an editor-free `.tpac` otherwise). [V]
4. The campaign map snow texture's rows are mirrored north-south against the CPU index vanilla uses. [V]
5. `particle_size` on a multi-grain sprite is the cluster size: check one particle at 1:1 before sizing a whole layer. [V]
6. Ground-hugging particles without `emit_on_terrain` vanish on slopes and float over dips. [V]
7. A 960 px preview hides small particles: hail looked absent there but measured fine at 1:1, and the reverse. [V]
8. Only per-frame exposure writes were tested [V]; whether a single write survives the engine's own atmosphere updates is untested.
   Write it only from a known baseline: an unset struct field of 0 would be a -2 EV floor that blows the scene out. [S]
9. Save-load: storm ages saved at the hour of the save and re-stamped on load keep keyed events (hail on the same storm) stable
    across a reload. [S]

## Assets
Weather textures and meshes reuse effects the game already packs; new sounds were generated and ship with their own credits file.

## Cost and time
About a week of agent time across twelve plans, most of it in-game verification loops (3-5 minutes per launch).

## Open questions
- Whether campaign battles started in light rain get an overcast TOD from the map weather (assumed, not shot).
- A volume-capable route for module sound beds, so weather sounds can cross-fade.
