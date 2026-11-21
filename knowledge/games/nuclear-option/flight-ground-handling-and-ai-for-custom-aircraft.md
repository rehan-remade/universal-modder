---
kind: game
title: "Making custom Nuclear Option aircraft fly, taxi, take off and land like stock: flight model, taildragger ground handling, carrier spawns and the AI"
game: "Nuclear Option"
game_version: "Early Access 0.34.6 (Steam app 2168680, public build 26327221); first findings on 0.34.3"
platform: windows
engine: unity-mono
route: loader-api
tools: ["Blueprinter 2.1.1 (.nobp packs)", "BepInEx 5.4.23.5", "HarmonyX", "Unity 2022.3.62f2 (batch mode, also used as an offline PhysX bench)", "ILSpy (decompile of Assembly-CSharp, reference only)", "Python 3 (offline flight / ground stubs)"]
anti_cheat: "none found; single player only, never on public servers (see the overview note)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-11-22
links:
  - "https://github.com/riseofthewolfremake-lgtm/HeritagePairs-NuclearOption"
  - "https://github.com/nikkorap/NOBlueprinter-Releases"
  - "https://github.com/BepInEx/BepInEx"
tags: ["aircraft", "flight-model", "fly-by-wire", "taildragger", "ground-handling", "landing-gear", "carrier", "spawn", "wing-fold", "ai", "physx", "joints", "airbrake", "blueprinter"]
---

# Making custom Nuclear Option aircraft fly, taxi, take off and land like stock

This note follows the overview
[new-aircraft-with-blueprinter-nobp-b25h-ga25x-nimrod.md](new-aircraft-with-blueprinter-nobp-b25h-ga25x-nimrod.md),
which covers building the aircraft themselves. Here the subject is behaviour: flaps and ailerons that act as
airbrakes, a fly-by-wire that lets a taildragger's nose sink, taildraggers that veer or drift on the runway,
wings that kink at their joints, aircraft that spawn inside a carrier lift, folding wings, and an AI that flies
too low, taxies too fast or goes around on every landing. The six released aircraft of the Heritage Pairs
addon (B-25H, GA-25X, Nimrod Mk I, FD-32, B-17G, MSB-17/80) fly, take off, land and taxi in game with these
fixes, and the user accepted the ground handling after flying it. The wing fold and the AI taxi cap are working
in game on an aircraft that is still in development and not released yet.

## Setup
- Game: Nuclear Option 0.34.6 (Steam, Windows 11), Unity 2022.3.62f2, Mono, no anti-cheat. The ground and
  flight work started on 0.34.3; the decompile we checked against is of the installed 0.34.6 Assembly-CSharp.
- Loaders: BepInEx 5.4.23.5 and Blueprinter 2.1.1. The aircraft are a Blueprinter `.nobp`. The behaviour fixes
  that a prefab can't carry live in a small BepInEx/Harmony plugin shipped in the same mod folder.
- The `.nobp` is built by editor scripts in the Blueprinter Unity project (see the overview note). The public
  source is on GitHub (link above); paths below are relative to that repo.
- Test tooling: a throwaway in-game test helper plugin (command file in, CSV logs out). Never ship it, and
  remove it after every session.

## Route and why
`loader-api`: everything that is data (airfoils, gear, joints, AI parameters, spawn offset) goes into the prefab
and the definition built for Blueprinter. Only behaviour the game has no field for goes into Harmony patches:
the airbrake threshold, the taildragger ground grip, the wing fold and the AI taxi cap. Every patch:
- is filtered on our own `definition.jsonKey` values, so stock aircraft are untouched;
- has a config switch (Auto / On / Off) and turns itself off for the session on any exception;
- keeps its maths in a small static class with a Python mirror, so the law is tested offline first.

## How the game works (what we had to learn)
Symbol names are from the 0.34.6 decompile. The behaviour is described in my own words.

**Engines.** Superchargers and turbochargers aren't modelled. A piston engine's power is a single number, so a
"realistic sea-level power" figure is wrong for a turbocharged aircraft. Our B-17G at its real sea-level power
couldn't take off. Tune power until the take-off run, climb and top speed match the historical figures (within
about 10 %).

**Control-surface parts and their airfoil.** A flap, aileron or elevator built as its own `AeroPart` sees the
wing's angle of attack *plus* its full deflection, looked up on its own airfoil curve.
- On the wing airfoil, a speed-scheduled 35° flap sat at about 42° AoA, deep post-stall: lift coefficient
  about 0.95, drag coefficient about 0.79. On the B-17G that was about 27 kN of the 46 kN drag at 50 m/s.
  The aircraft stopped accelerating at 51 m/s and overran the runway.
- Give flaps their own curve (CL about 2.0 near 33° part AoA, low drag) and ailerons a flap-like curve, so they
  never pass CLmax. Without it, ailerons reverse roll at moderate wing AoA (overview Gotcha 9).
- In the public repo, `unity/Editor/B17GBuild.cs` has the `OwnFlapAirfoil` and `OwnAileronAirfoil` switches.

**Fly-by-wire.** Two different `takeoffSpeed` fields exist.
- `ControlsFilter.FlyByWire.takeoffSpeed` is the FBW's own. While the gear is down and the wheels are on the
  ground (`radarAlt` under 0.1): under 1.5 × this value, with weight on the nose gear, the target pitch rate is
  clamped so the FBW never resists a nose-down rotation; under the value itself, the FBW's accumulated pitch
  correction is bled away every step.
- A taildragger's tail comes up long before lift-off, so with the default (40, ours had 46) the FBW let the nose
  sink to 2–5.5° and the B-17G couldn't lift off below about 70 m/s. Setting it to 15 lets the FBW hold the
  attitude (the B-17G also needed a bigger elevator before the stick stopped saturating).
- `alphaLimiter` there limits the *root* (fuselage) AoA only; wing incidence adds on top of it.
- `AircraftParameters.takeoffSpeed`, `takeoffDistance`, `PIDReferenceAirspeed` and `maxSpeed` are separate
  fields that the AI states and autopilot read.

**Airbrake.** The stock `Airbrake` component opens only while `ControlInputs.throttle` is *exactly* 0. Its
`Update` moves `openAmount` toward open or closed at `openSpeed`. Its `FixedUpdate` applies drag in proportion to
air density × V² × `openAmount`. There is no ground test. `ThrottleGauge.UpdateThrottleDisplay` shows the
"AIRBRAKE" text under the same exact-zero rule.
- To open it under a threshold (we use 5 %, on the ground and in the air alike), a Harmony prefix on
  `Airbrake.Update` adds twice the closing step to `openAmount` when 0 < throttle < threshold.
- The stock code then subtracts one step and clamps, so the net result is exactly the stock opening, with the
  stock drag, panels and sound. A postfix on the gauge shows the matching text.
- Public repo: `src/B25H.Instruments/AirBrake1912.cs`.

**Wheels.** A `LandingGear` leg applies a side force from its slip angle. The law is a clamp of slip × a response
factor × (0.2 + 0.01 × wheel speed), times the friction coefficient, times the wheel load. Legs can castor, using
`steering`, `aligningStrength` and `steeringLock`. A castoring leg turns toward its own track and gives no side
force inside its lock angle. Velocities are taken relative to the contact collider's rigidbody (and any
`AnimatedPhysicsSurface`), so a wheel on a moving carrier deck behaves as on land.

**Taildragger directional stability.** With grippy main wheels ahead of the CoM, the aircraft is directionally
unstable once the tail wheel unloads. Any yaw makes the mains' side force push the yaw further: the "veer off
the runway after about 100 m".
- Castoring mains remove the instability but leave nothing holding the aircraft sideways, so it drifts.
- What worked: keep the castoring mains and add a lateral force at the rigidbody CoM. That force uses the
  game's own wheel side-force law on the CoM's sideways velocity, with N = the summed gear loads (so it fades
  to 0 at lift-off). A force at the CoM has no yaw moment, so the velocity follows the heading without the
  destabilising moment.
- Add a small ground yaw damper (only with no yaw input), and taxi-turn values: the castor lock
  speed-scheduled from 25° at low speed to the built 6° by 20 m/s, and a tail-wheel lock capped at the angle
  that rolls without slip in a 0.9 rad/s turn.
- On a carrier, every velocity in that stack must be deck-relative. With world velocity, a deck moving at
  10–15 m/s reads as side slip, and the grip force beat the wheels' own friction and slid the aircraft off.
- Public repo: `src/B25H.Instruments/GroundGrip189.cs` (`GroundGripMath`, `DeckMath`) and
  `src/B25H.Instruments/TaxiTurn1811.cs` (`TaxiTurnMath`).
- Friction stays at the stock 0.8. Our earlier "low main-wheel friction to stop nose-overs" was the cause of the
  spin-outs, not a fix. Moving the CoM was studied and rejected for our aircraft: the propeller force acts at
  the prop part's CoM, a lower CoM tips the aircraft over in brake run-ups, and a lower thrust line pitches
  take-offs up. Some stock and community aircraft do place mass with `UnitPart.centerOfMass` (FastBomber1, EW1,
  SmallFighter1, QuadVTOL1), and it's worth checking before building your own force.

**Multi-part wings.** In full-detail physics every `AeroPart` is its own Rigidbody, joined by FixedJoints
(`AeroPart.CreateJoints`, break force × 10). The default `PartJoint.solverIterations` is 6.
- A value other than 6 is written to the owning part's `rb.solverIterations`. PhysX uses the island's maximum
  (PhysX rule, inferred, not read in the game). Stock uses 12 on the A-19's outer wing joints.
- A light part between heavy ones (a 32 kg biplane centre section) keeps joint error that looks like a hinge
  at the break line: 2.2° and 99 mm at 8 g.
- In-game sweep of the iterations on those joints: 20 left a 17–18 mm step, 40 a hairline, 100 gave
  0° / 0 mm. Frame time didn't change measurably at 100 for one aircraft.
- Blueprinter keeps the field in the `.nobp`. An offline bench rebuilds the bodies and joints in Unity's PhysX
  at the game's 1/60 s step: public repo `unity/Editor/WingFlexPhysX.cs`.

**Spawns and carrier lifts.** `def.spawnOffset` is applied in the spawn transform's frame: `y` along its up
axis, `z` along its forward axis (`Hangar`, and `Aircraft` for remote aircraft). Stock uses it: the CI-22 has
+0.42 m forward, helicopters about +1 m.
- On the carrier lifts, a "backstop" BoxCollider stands behind each lift spot. A taildragger with a long tail
  and no forward offset spawned with its rudder 0.06–0.16 m *inside* that box, and the collision tore it off.
- Our rudder also had impact damage switched on, where every stock rudder has it off
  (`ImpactDamage` threshold 0 and multiplier 0, so `AeroPart.OnCollisionEnter` returns early).
- Fix: a forward offset (1.2 m and 0.7 m on our two biplanes), stock-style rudder impact damage off, and a
  build-time check. The check reads the
  Hangar `spawnTransform` and every "backstop" collider from Blueprinter's placeholder carrier prefabs, and
  needs at least 0.3 m plan-view clearance from the rudder's aft-most point. It fails if fewer than two
  backstops are found, so it can't silently pass. Public repo: `unity/Editor/LiftSpawn1911.cs`.

**Folding wings.** 0.34.6 has no fixed-wing fold component. Only two things fold or sweep:
- `RotorShaft` (helicopter rotor blades): after a ground spawn it starts folded, waits about 1 s, keeps waiting
  in 1 s steps while the body's vertical speed is above 1 m/s (a lift still moving), then unfolds with the hinge
  at fold angle × SmoothStep of the remaining amount;
- `SwingWingController` (FastBomber1), which is a Mach-driven sweep, not a spawn fold.

We reused the `RotorShaft` law in a plugin:
- a postfix on `Unit.InitializeUnit`, the same moment the rotor's initialise handler runs;
- fold the tip hinges 90° on a ground spawn;
- unfold with SmoothStep once the aircraft has settled. Polling in 1 s steps was too slow: an AI drove off the
  lift with its tips still folded;
- hold the AI's throttle at 0 with the brake on while folded;
- the hinge only moves the render mesh; colliders and joints stay put.

Find the hinges through `Aircraft.partLookup` as well as the hierarchy: a detached `AeroPart` has no parent
transform, so `GetComponentsInChildren` on the aircraft doesn't see it. The aircraft that uses this isn't
released, and its plugin file isn't in the public repo yet. Lesson: decompile the build you're running before
saying "the game can't do it". Our first answer, from an older study, was wrong.

**AI.** Fixed-wing aircraft share one combat state (`AIPilotCombatModes`). The value an aircraft gets is only its
`AircraftParameters`.
- `minimumRadarAlt`: for fixed-wing aircraft, only the combat state reads it, as a floor for its target height
  (`ManageAltitude`, radar-warning reactions). Helicopter states read it too.
  - A level bomber with 150 cruised at 140–150 m AGL. With 3000 it climbed out and bombed from about 1.5–1.9 km.
  - Landing and taxi don't read it.
  - A bombing run starts its climb from radarAlt × 2 + 5 km out.
- Gun use on ground targets follows the gun's `WeaponInfo` target requirements (`minAltitude`). Our own
  air-only gun infos (minAltitude 150) meant the AI never strafed. The stock A-19 cannon has minAltitude 0 and
  strafes fine, because `UseFixedGuns` breaks every pass off 2 s before the target and keeps the dive shallow.
  Give a heavier aircraft room with `minimumRadarAlt` instead.
- `AIPilotTaxiState` sets a target speed of up to about 30 m/s on a straight leg, from the waypoint angle and
  the steer distance, with throttle up to 0.5 and bang-bang brakes.
  - That suits tricycles. A light taildragger is near lift-off by then; its tail-wheel load falls off from
    about 13 m/s at taxi thrust and is gone by 26 m/s. Ours hit revetment walls at 32 m/s and once lifted off
    still in the taxi state. (One log showed throttle 1.00 in this state where the code caps 0.5; not
    explained.)
  - Fix: a postfix on the taxi state's `FixedUpdateState` caps the speed (throttle limited above 9 m/s, idle and
    brake above 12 m/s), plus a lower throttle while the take-off state lines up across the deck. The stock
    steering and hand-over are untouched.
- The taxi autopilot pushes the stick forward while braking, which lifts a taildragger's tail. We left it as
  stock.
- `AIPilotLandingState` has no real flare. It flies the glideslope at a speed scaled from `landingSpeed`; in the
  last 2 s (unless it is hooking an arrestor) it cuts the throttle and raises its aim point 5 m. It counts
  "touched down" at radarAlt < 0.1 m and aborts if radarAlt goes above 1 m afterwards.
  - Stiff, under-damped mains plus a flat (3°) wheel landing bounced the aircraft over 1 m: endless go-arounds.
  - Our offline model said it stays down only if it touches down at a pitch of at least about 6°. A lower
    `landingSpeed` plus more main-gear damping fixed it; neither alone did.

## Build steps
1. Set airfoils per part type: wing, flap (own curve), aileron and elevator (flap-like curve). Don't run a
   scheduled flap on the wing curve.
2. Set `ControlsFilter.FlyByWire.takeoffSpeed` low (about 15) on a taildragger. Set the `alphaLimiter` so that
   limiter + wing incidence = the wing's CLmax angle.
3. Tune piston power for the historical take-off run, climb and top speed. Read the numbers back in game.
4. Write every `AircraftParameters` value the AI uses (`takeoffSpeed`, `takeoffDistance`, `PIDReferenceAirspeed`,
   `maxSpeed`, `minimumRadarAlt`, `landingSpeed`, `groundTurningRadius`). Add a build check that each one has
   the value you meant (Gotcha 9).
5. Gear: stock-like friction (0.8), stiffness and damping. On a taildragger: castoring mains plus the CoM grip
   plugin, with deck-relative velocity.
6. Joints: `solverIterations` 100 on the joints of light parts that sit between heavy ones.
7. Set `spawnOffset` and run the lift-backstop check against the placeholder carrier prefabs.
8. Plugin patches filtered by `jsonKey`, each behind its own config switch, with a Python mirror of the maths.
9. Test in game in this order: no-input full-throttle take-off, taxi turns, deck runs, AI sortie, then AI
   landings.

## Verification
- **Oracles in game** (test-helper plugin, logs read after each run):
  - **No-input full-throttle take-off:** heading change and lateral drift (∫ v·sin(track − start heading)) up
    to wheels-off. Pass: under 1° and under 5 m.
    - MSB-17 at 34 t: 0.5° / 1.9 m with the stack. At 42 t: 0.9° / 7.7 m with it (a fail at that build)
      and 2.3° / 17.2 m without it; a later build gave 0.1° / 0.07 m at 38 t.
    - The in-development fighter: 6.8 s, 137 m, 155 km/h, 1.2° on repeated runs.
  - **Taxi turns:** crab angle at 5 and 10 m/s under full rudder.
  - **Deck runs:** taxi, hold and take-off on a carrier.
  - **Joint read-back:** every body's solver iterations, read in game, confirmed that Blueprinter keeps the
    field.
  - **Wing joints:** pose error per physics step during 8 g pulls, at iteration counts 20 to 100.
  - **Frame time:** A/B in 10 s windows with vsync off.
  - **AI:** parameter read-back (caught Gotcha 9), whole sorties, and landing state logs.
  - **Lift spawns:** wing fold and AI hold lines in the plugin log.
- **Offline:**
  - Python stubs of the game's own laws (taildragger track model, deck model, touchdown model, B-17G lateral
    and flight-model stubs), with sync tests that keep the C# constants equal to the stub constants;
  - Unity build checks (lift clearance, joint values, parameter values);
  - the Unity PhysX wing bench.
- **The user** flew the three taildraggers (B-17G, Nimrod Mk I, FD-32) with the taxi-turn stack on and
  accepted them: no veer and no drift on taxi, take-off or landing. The MSB-17 was checked with the oracle
  above, not in a separate user review.
- **Not verified:**
  - multiplayer (all plugin behaviour runs only on the aircraft we simulate locally; never tried online);
  - game versions after 0.34.6, including 0.35;
  - the carrier catapult;
  - deck pitch and roll in heavy seas;
  - the wing fold on the Cursor-class carrier's elevator, seen in the log but not on camera;
  - an AI landing of the in-development fighter on a carrier.

## Gotchas
1. **A heavy bomber accelerated to about 51 m/s and then stopped, overrunning the runway.**
   - **Cause:** speed-scheduled flaps on the wing airfoil sat about 42° past the wing's AoA, deep post-stall:
     they were an airbrake.
   - **Fix:** a separate flap airfoil, and flap-like airfoils for ailerons and elevators.
2. **A taildragger's nose sank during the take-off roll and it couldn't lift off.**
   - **Cause:** `FlyByWire.takeoffSpeed` 46. On the ground below that speed the FBW bleeds its own pitch
     correction away, and below 1.5 × it never resists a nose-down rotation.
   - **Fix:** 15.
3. **Taildraggers veered off the runway about 100 m into a hands-off full-throttle run.**
   - **Cause:** grippy mains ahead of the CoM are directionally unstable once the tail unloads (worse with the
     low friction we had set).
   - **Fix:** see Gotcha 4.
4. **After castoring the mains, the aircraft drifted sideways at every speed ("floaty").**
   - **Cause:** a castoring leg gives no side force inside its lock angle.
   - **Fix:** a lateral force at the CoM using the game's wheel law on the CoM velocity, plus the taxi-turn
     lock schedule (`GroundGrip189.cs`, `TaxiTurn1811.cs`).
5. **On a moving carrier, the taildraggers slid off the deck.**
   - **Cause:** the grip used world velocity, so the ship's 10–15 m/s read as side slip.
   - **Fix:** take all velocities relative to the contact collider's rigidbody, like `LandingGear` does.
6. **Biplane upper wings "shifted" at their break lines in hard pulls.**
   - **Cause:** the default 6 solver iterations on FixedJoints between parts of very different mass.
   - **Fix:** `PartJoint.solverIterations` 100 on those joints. There was no measurable cost.
7. **Rudders tore off on carrier lift spawns.**
   - **Cause:** with no forward `spawnOffset`, the tail spawned inside the lift's backstop BoxCollider, and
     our rudder took impact damage where stock rudders don't.
   - **Fix:** a forward offset, rudder impact damage off as on stock, plus the build-time plan-view clearance
     check (`LiftSpawn1911.cs`).
8. **The AI flew its bomber at 140 m AGL into the defences.**
   - **Cause:** `minimumRadarAlt` 150. Only the combat state reads it, and that's its whole altitude floor.
   - **Fix:** 3000 for a level bomber. Landing and taxi are unaffected.
9. **AI take-off and landing were wrong after a change that "only touched the g-limit".**
   - **Cause:** in the generated parameter code, a comment at the end of one line swallowed the assignments that
     followed it (`PIDReferenceAirspeed`, `maxSpeed`, `takeoffSpeed`, `takeoffDistance`). The game ran with the
     template aircraft's values (180 / 215 / 80 / 500). It happened twice.
   - **Fix:** read the parameters back in game, and add a build check row per value.
10. **The AI never used its cannon or guns on ground targets.**
    - **Cause:** our own gun `WeaponInfo`s had a 150 m `minAltitude` target requirement.
    - **Fix:** the stock rule, minAltitude 0 like the A-19's cannon. The combat state already breaks a pass off
      in time; give the airframe room with `minimumRadarAlt`.
11. **A light taildragger AI hit the revetment walls, or lifted off while still in the taxi state.**
    - **Cause:** the stock taxi target speed of up to about 30 m/s.
    - **Fix:** a postfix speed cap on `AIPilotTaxiState`, plus a line-up throttle limit on the take-off state.
12. **The AI went around on every landing.**
    - **Cause:** a 3° wheel landing bounced it over radarAlt 1 m, the abort limit.
    - **Fix:** a lower `landingSpeed` (so it touches down nose-high) together with more main-gear damping.
13. **The wing-fold plugin logged "0 hinges found".**
    - **Cause:** the fold parts are detached `AeroPart`s with no parent transform, so a hierarchy search misses
      them.
    - **Fix:** also search `partLookup`.
14. **The AI taxied off the lift with its wings still folded.**
    - **Cause:** the stock rotor law waits in 1 s steps while the lift rises.
    - **Fix:** unfold as soon as the aircraft has settled, and hold the AI's throttle and brake until the unfold
      ends.
15. **The airbrake was "dead" on landing at idle throttle.**
    - **Cause:** stock opens it only at a throttle of exactly 0, and a player's idle isn't always exactly 0. An
      intermediate version of ours also closed it on the ground, which was wrong: the landing roll is where it
      matters.
    - **Fix:** a threshold prefix (5 %, ground and air) that reuses the stock opening.

## Assets
None for this part of the work: it's parameters, plugin code and build checks. Model and texture work is in
the overview note.

## Cost and time
Spread over about three weeks of sessions (2026-11-02 to 2026-11-21), alongside the art work. The taildragger
ground stack alone took four in-game rounds (veer → castor drift → CoM grip → taxi turns → deck mode).

## Open questions
- Multiplayer: the plugin forces act only on aircraft we simulate locally. Their effect on remote clients is
  untested.
- 0.35 (expected newer Unity): re-check every symbol named here before reusing the patches.
- A stock-component way to do taildragger grip without a plugin, for example `UnitPart.centerOfMass` placement
  as some stock aircraft use it, wasn't tried in game.
- The AI taxi autopilot's tail-lift under braking is left as stock.
