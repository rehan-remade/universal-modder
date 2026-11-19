---
kind: game
title: "GHPC tanks in Nuclear Option: integration findings and unresolved runtime gaps"
game: "Nuclear Option"
games_also: ["Gunner, HEAT, PC!"]
game_version: "Nuclear Option Steam build 24724372; GHPC Steam build 24952526"
platform: windows
engine: unity-mono
route: managed-patch
tools: ["BepInEx 5.4.23.5", "Harmony", "Roslyn 5.3.0", "ILSpy", "UnityPy 1.25.4", "REA 6.4.0"]
anti_cheat: "No anti-cheat found in the bounded installation scan; private hosted sessions only"
status: in-progress
agents: ["Codex (GPT-6)"]
humans: []
date: 2026-10-17
links:
  - "https://github.com/morluto/rea"
  - "https://github.com/Rap3/NuclearOption-PlayableVehicles/tree/ab174e98a094d18b222f01bfdf7e927cf98dbc2e"
tags: ["coop", "survival", "armor", "unity", "server-authority", "local-conversion"]
---

# GHPC tanks in Nuclear Option: integration findings and unresolved runtime gaps

An independently authored plugin integrates privately converted GHPC vehicles into a Nuclear Option
survival scenario. Earlier host runs established visible M1 geometry, powered movement, cannon/coax
firing, localized damage and native aircraft flight/firing. Later sight, audio and firing-performance
corrections have compiled and passed offline checks, but still require manual gameplay acceptance.
Two independent players have not been verified; this is an in-progress integration.

This 17 October consolidation corrects earlier local journal claims: normalized bundle headers did
not establish runtime loading, and the autoloader teardown method is OnDestroy, not OnDisable.

## Setup

| Component | Pinned reference |
|---|---|
| Host | Nuclear Option, Steam app 2168680, build 24724372 |
| Guest | Gunner, HEAT, PC!, Steam app 1705180, build 24952526 |
| Both Unity players | 2022.3.62f2, managed Mono, Windows |
| Host loader | BepInEx 5.4.23.5, Harmony patches |
| Networking | Shipped Mirage 158.3.5.0 |
| Guest audio ABI | FMOD 2.1.11 |

Compile against the installed host assemblies. GHPC's managed files are under `Bin/GHPC_Data/Managed`; see the
[private decompilation workflow](../gunner-heat-pc/private-mono-decompilation-and-source-navigation.md).
Keep source exports, original dependencies and converted content in a private lab outside Git.
Back up profiles/configuration before modded launches and retain original-file hashes.

## Route and why

Use native host GroundVehicle entities for host integration, a private renamed drivetrain dependency
island, and independently written simulation/adapters informed by the owned guest's code and data.
No second GHPC process is involved. The five admitted vehicle profiles are M1, T72M, T55A, BMP1 and BMP2.

Every intended peer must own and locally convert both games. This note contains findings, not the
plugin or converter implementation; build steps below describe the established workflow, not a
self-contained downloadable mod. Game assemblies, assets and reconstructed source are not included.

Control intents go to the authoritative host. The playable-vehicles reference in the metadata was
useful for native API patterns; its client-authored pose approach does not establish server authority.

Nuclear Option has public servers and online PvP. Use the plugin only in private sessions where every player
owns both games and runs the same plugin; this work used a private host. Don't load it when joining public
servers or any session whose players don't run it. No anti-cheat was found in the install.

## How the game works

### Host lifecycle, cameras and networking

The default early Application static-constructor loader entry caused a native Mono/Harmony crash
in this installation. The tested entry was `Assembly-CSharp.dll / GameManager / PreSetupGame`, with
patch installation deferred until the host's menu/resource initialization boundary. This is a
build-specific observation, not a general Unity prescription. BepInEx 5 takes its entry from the `Assembly`,
`Type` and `Method` keys of `[Preloader.Entrypoint]` in `BepInEx/config/BepInEx.cfg` (default
`UnityEngine.CoreModule.dll`, `Application`, `.cctor`).

Disabling native GroundVehicle control also skips inherited Unit.OnEnable bookkeeping and can leave
Unit.rb null. Preserve the required inherited initialization while excluding native driving. Remove
the airdrop ImpactDetector only from owned prefab clones.

CameraOrbitState treats movement while following a non-aircraft unit as a request to abandon that
target. Taking over the final camera pose alone cannot prevent this. Scope state/input suppression
to tank possession, retain native environment/floating-origin updates, and restore ownership on exit.
Respect focus, map, chat and menu gates; synchronize actual cursor lock without erasing modal flags.

A native Player attribution field does not grant Mirage transport ownership. Messages built outside
the host weaver need explicit serializers. The shipped string limit is strictly below 1300 encoded
bytes; the adapter uses 1024-byte UTF-8 chunks with digest, bounded assembly and mission-epoch checks.
Authenticate messages against the current server and pace sends. Snapshot inventory must precede
dynamic interior identities; restore current loops without replaying historical one-shot effects.

### Geometry and source identities

Qualify object identities with their serialized file/CAB as well as numeric path ID. Different files
can contain the same path ID. Retain hierarchy, mesh triangles, bone weights, collider cooking flags,
source PhysicMaterial and per-body settings. Optimized single-influence skinning can imply weight one;
an exporter that expects ordinary weight arrays can silently lose those weights.

Source layer-23 group bounds activate child damage queries; they are not opaque armor. A
ShotDetectionZone notification does not constitute an impact or arm the projectile. Stored
ammunition creates additional collider/charge/flammable identities, so inventory changes affect
damage geometry and snapshot admission.

Mass/inertia depend on the participating colliders and source lifecycle. The M1 detaches certain
source-layer-7 branches, whereas BMP2 retains its detection sphere. Serialized identity tensors
and approximate box dimensions cannot replace that lifecycle. Original FrictionPreset constructors
also mutate a registry; do not invoke them casually during data restoration.

Configure source wheel nodes before WheelController.Awake caches its visual references.
Keep source-only tag/classification metadata private rather than modifying global host tags or
aircraft physics.

### Gunner sight and the opaque white view

The M1 gunner station is crew position 2. Follow the actual CameraSlot, UsableOptic and FCS binding.
Its FcsRange sight aligns to the uncorrected aiming vector and current range; it does not simply
follow the superelevated barrel. Original FOVs are approximately 9.52 and 3.472 degrees.

Default source smooth aiming accumulates raw Rewired mouse input at 0.005, clamps it, then applies a
signed-square response. Palm release uses slowdown 1.5; powered yaw/elevation rates are 40/60 degrees
per second, versus 5/10 unpowered. The adapter uses Shift for palm/smooth aiming and V for view
switching. User-customized GHPC mappings and controllers are not imported.

Apply palm state before a same-frame laser request. Read setter side effects: the short-hit
RangeInvalid assignment is immediately cleared by TargetRange's setter, while a laser miss
preserves the previous range/lead. Property names alone suggested the wrong behavior.

The reported white first-person image came from M1 Optic Fade Transition and FLIR Scanline helper
quads. Both use source layer 11, Thermals Only, excluded by BufferedCameraFollow's normal camera.
Remapping all imported nodes to the host Default layer exposed their opaque fallback materials.
The helper pose/width matched the screenshot's narrow visible landscape strip.

The importer now preserves this exclusion for normal rendering; camera placement, FOV and near
clip were not the remedy. Inventories found two helpers on M1, one on T55 and none on the other
three profiles. This restores exclusion, not the guest's thermal/CRT rendering functionality.
The corrected installed build still needs a new manual visual check.

Reticle angular geometry and TMP glyph metrics were independently reconstructed from local data.
Native mspace uses metric widths rather than atlas dimensions. HDR bloom, original filtering and
full FLIR/weather/scorch shaders remain incomplete.

### Machine-gun effects and firing cost

The source M240 belt contains four M80 rounds followed by one M62 tracer. Both ammunition types
have zero TNT yield and no always-produced blast. The adapter's impact events carried ammo identity
but omitted a supplemental flag; presentation selected a heavy-cannon donor for coax impacts.

Classify effects by actual ammunition identity/category/calibre. The corrected adapter uses the
host's nonexplosive Gun7.5mm dust/hit presentation and disallows explosive fallback for zero yield.
Visual donors do not define authoritative damage.

Cloning, scanning and scheduling destruction of a muzzle hierarchy for every bullet created avoidable
work. The inspected small-gun muzzle contains particle/render components and is suitable for the
native ParticleEffectManager pool. Cache ammunition, tracer and donor metadata outside the shot path.

Another hot path copied mesh vertices/indices, transformed geometry, validated it and sorted all
intersections for each query. The adapter now caches immutable topology and world vertices/bounds,
invalidating on exact changes to any of the 16 transform-matrix values, mesh replacement, box
dimensions or dynamic removal. Preserve the original intersection math and distance/triangle-index
tie rules when selecting the closest hit; backface thickness still needs its separate logic.

Do not interpret MaximumRange = 1000 m as projectile lifetime: observed usages belong to AI/weapon
range doctrine. LiveRound.DoUpdate retires rounds before movement at age over 60 s, spall over 1 s,
or local Y below -300. Nonguided ordinary rounds also retire at speed at most 20 m/s, spall below
10 m/s. Retirement does not detonate the round. These rules replace the adapter's older 90-second
retention of slow projectiles.

### Audio and bundle compatibility

Read the shipped FMOD wrapper ABI. Its 2.1.11 PARAMETER_DESCRIPTION has seven fields, occupies
40 bytes on x64 and has no GUID. A newer SDK structure is not interchangeable.

Engine audio follows NWH RPMPercent/Load and original selector/ramp rules, including initial
written-state flags; vehicle speed is not an RPM oracle. Track audio reads the assigned left/right
wheel velocity, and turn audio reads actual hull angular velocity. Turret sound combines virtual
local rotation with physical acceleration/inertia. Apply per-peer view/interior parameters locally,
using actual CameraSlot.IsExterior and only the owned FMOD system.

Weapon sound delay origin can differ from emitter position. Preserve ClipDepleted/StopFiring order,
the source stop retry and per-route event watermarks. Current loops may need timeline/parameter
resynchronization even if a late initial snapshot is older than an already seen event watermark.

AmmoFeed.OnDestroy stops its autoloader; OnDisable does not. The exclusive AZ autoloader stage branch
returns before ordinary pending-stage stop logic, whereas legacy Unity and ordinary FMOD stage sounds
may coexist. M1 released stage tails continue at their last pose after feed destruction. Clip-stage
thresholds omit ReloadMultiplier although round stages include it; total reload time remains affected.

Four legacy emitters belong to BMP1 main/guided, BMP2 guided and T55 main weapons. They are not coax
emitters. Original encoded clips and AudioSource settings were retained privately; host master/effects
volume mapping is an explicit adaptation.

Some original shaders had no AssetBundle container entries and were invisible to LoadAllAssets.
Adding discoverable entries exposed them, but isSupported alone does not prove URP pass compatibility.
Likewise, private particle/legacy-audio bundles passed serialized-header and payload-preservation
checks yet still failed actual LoadFromFile with a newer-Unity-version compatibility error.
Normalizing advertised version/platform headers did not establish a working conversion. That
compatibility issue remains unresolved; no successful current particle/legacy playback is claimed.

## Build steps

1. Search the KB, pin both builds and retain hashes of original executable, managed assemblies and
   UnityPlayer. Back up the host profile/configuration.
2. Create private ILSpy/REA references outside Git. Record serialized values as well as code defaults.
3. Convert file-qualified vehicle/weapon graphs, retaining source hierarchy, layers, physics, skins,
   dynamic inventory identities and resource provenance in private sidecars.
4. Prepare the private drivetrain dependency island and compile independently authored adapters
   against the actual host/Unity/Mirage references.
5. Check equations, collision rules, inventory order, snapshot admission and serializers offline.
   Validate resource provenance separately from runtime loading.
6. Install only the approved loader and owned plugin payloads with the game closed; archive previous
   plugin builds and verify original game-file hashes.
7. Create a distinct survival scenario through the normal private-host mission picker. Copying a
   mission can retain unwanted production/objectives; the original restart route switches to offline
   single-player. Validate spawn footprints against real terrain, not merely upward-facing roofs.
8. Ask the human to check sight, weapons, audio and sustained-fire performance. Validate two
   independent authenticated peers, late join and reconnect separately before claiming coop success.

## Verification

| Evidence | What it establishes | Limit |
|---|---|---|
| Earlier real host logs/screenshots and human reports | Boot, visible M1, movement, firing, localized damage; aircraft flight/firing | Does not accept every later patch |
| Human white-view screenshot plus source layer/camera records | Specific helper-quad visibility error | Corrected build needs a new visual check |
| Current pre-fix host log | FixedUpdate stalls of 203, 222 and 1020 ms; Update stall of 2403 ms | No post-fix CPU/FPS measurement |
| Product compilation and existing offline suites | Build compatibility and bounded equations/protocol/mesh behavior | Not Unity rendering, pooling or multiplayer proof |
| Private extraction receipts | Object identity, topology, encoded-resource provenance | Not successful Unity loading/playback |
| Current LoadFromFile errors | Particle and legacy-audio compatibility failure persists | Complete compatibility repair not found |

The latest focused build passed existing suites with 216 simulation, 21 lifecycle, 24 projectile-order,
282 bridge and 1149 source-mesh assertions. These results were recorded during the implementation;
they were not rerun as game tests for this documentation contribution. Original host hashes and
private candidate/install digests were checked. No automatic gameplay control was used for the latest
fixes. Human acceptance and a real second peer remain outstanding.

## Gotchas

1. **Early native crash.** Cause: patching at the loader's early Application entry. Remedy in this build:
   defer through the tested GameManager initialization boundary.
2. **Tank follow breaks on movement.** Cause: native spectator state abandons non-aircraft targets.
   Remedy: scope state/input ownership to possession while retaining native camera maintenance.
3. **Opaque white gunner view.** Cause: technical-layer helpers became ordinary visible geometry.
   Remedy: preserve their normal-camera exclusion, then request manual visual acceptance.
4. **Explosive-looking coax hits.** Cause: incomplete cosmetic classification selected a cannon donor.
   Remedy: route by actual ammunition and forbid explosive presentation for zero yield.
5. **Expensive sustained fire.** Causes found in the adapter: per-shot clones and repeated mesh
   reconstruction/all-hit sorting. Remedy implemented: pooling and exact-invalidated geometry caches;
   the remaining performance result still needs measurement.
6. **Correct-looking bundle headers, failed runtime load.** Cause: header/payload checks were treated
   as compatibility evidence. Remedy: keep the failure explicit and require actual LoadFromFile proof.
7. **Autoloader stops at the wrong lifecycle edge.** Cause: OnDestroy was misread as OnDisable.
   Remedy: preserve the original finish/destruction behavior and let released one-shot tails finish.
8. **Late join or reloading depends on missing identities.** Cause: dynamic ammunition geometry was
   applied after dependent state, or a first snapshot failed to resynchronize an active sound.
   Remedy: restore inventory first and reconcile current phase per route.
9. **Static source defaults disagree with behavior.** Cause: serialized overrides and setter/constructor
   side effects. Remedy: inspect both data and method bodies before choosing runtime values.

## Assets

Only prose findings are contributed. Models, textures, audio, original dependencies, decompiled code,
resource banks and generated asset graphs remain outside the repository. No game content is attached.
Converters and independently authored adapters would require their own review before distribution.

## Open questions

- Confirm the latest sight exclusion and nonexplosive coax presentation manually.
- Measure sustained-fire CPU/allocation/frame time after pooling and geometry caching.
- Resolve actual Unity loading of the particle and legacy-audio bundles.
- Complete compatible FLIR/weather/scorch rendering, original reticle filtering and remaining audio.
- Compare damage/ballistics/physics numerically against the running guest, including aircraft impacts.
- Verify independent peers, authenticated ownership, late join, reconnect and later survival waves.
