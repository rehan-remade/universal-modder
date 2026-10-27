---
kind: game
title: 'Deadlock''s movement suite in Hytale: server plugin + client-predicted interactions'
game: Hytale
games_also: [Deadlock]
game_version: 'Hytale server 0.7.2 (rev d769dc3d, release patchline); Deadlock client/server 6779 (Steam build 25917577) as the data source'
platform: linux
engine: java
route: loader-api
tools: [Hytale server plugin API, Gradle 9.8, JDK 25, 'ValveResourceFormat CLI built from source at 1b229d5']
anti_cheat: none kernel-level; server-authoritative with client prediction
status: working
agents:
- GitHub Copilot (Claude Opus 5.5)
humans: [Dale]
date: '2026-10-14'
links:
- https://youtu.be/qWrUCAHnvYg
- https://docs.hytale.com/api/
- https://hytalemodding.dev/en/docs/guides/plugin/setting-up-env
- https://support.hytale.com/hc/en-us/articles/45326769420827-Hytale-Server-Manual
- https://deadlock.wiki/Movement
tags: [movement, dash, slide, wall-jump, double-jump, interactions, hud, telemetry]
---
# Deadlock's movement suite in Hytale: server plugin + client-predicted interactions

A Hytale server plugin (Java) plus a small asset pack recreates Deadlock's movement: ground and air dash,
dash-jump, air jump, wall jump with fatigue, steerable slide, dash-slide, slide-jump, down dash, mantle glide,
3-pip stamina with a curved HUD under the crosshair, and a dash trail. All tuning numbers come from Deadlock's
own `scripts/heroes.vdata` and `scripts/abilities.vdata` (read from the owner's install). It runs on a local
dedicated server with the unmodified client; verified by per-packet server telemetry plus many human playtests.

## Setup
- Hytale standalone launcher on Linux, patchline `release`; server `HytaleServer.jar` 0.7.2 (bytecode Java 25).
- JDK 25 (`/usr/lib/jvm/java-25-openjdk`), Gradle 9.8.1 (toolchain 25). Compile-only dependency on the installed
  `HytaleServer.jar`; no third-party Gradle plugin needed.
- Manifest `ServerVersion: ">=0.7.2 <0.8.0"`, `IncludesAssetPack: true` (asset pack = `Server/...` at the
  jar root).
- Lab: `java -jar HytaleServer.jar --assets Assets.zip --bind 127.0.0.1:5520 --disable-sentry`, console fed by a
  FIFO opened read-write (`exec 3<>fifo; java ... <&3`) so the agent can send `/auth`, `/op`, `/plugin reload`.
- Server auth: `auth login device`; the first code never completed until the human pressed the final confirm on
  the site. Credentials persist encrypted (`OAUTH_STORE`) across restarts.
- Deadlock data: Source2Viewer 20.0 failed on this Deadlock build (unknown KV3 type 26); building
  ValveResourceFormat from source (KVType 26/27 added upstream the day before) worked. Source2Viewer 20.1
  (2026-10-15) includes that change, so a release build should now do.

## Route and why
Server plugin + asset pack (`loader-api`). The client is NativeAOT and client mods are unsupported. Pure server
velocity control (per-tick `ChangeVelocity`) feels laggy and fights client friction, so anything that must feel
instant is a **client-predicted interaction** shipped as assets (dash), and the server handles what assets can't
express (air/wall jump decisions, slides, dash-jump, HUD, settings).

Deadlock is only the design reference. Its tuning numbers were read from the `.vdata` files in the owner's
install with ValveResourceFormat: file reads only, with nothing injected into the Deadlock client (VAC-protected)
or sent to its servers. No Deadlock files or assets are in the mod or in this note.

## How the game works (what we had to learn)
- Inbound `PacketAdapters.registerInbound(PlayerPacketWatcher)` sees every `ClientMovement`: nullable
  `movementStates` (only sent on change), `velocity`, `lookOrientation` (radians; forward = (-sin yaw, -cos yaw),
  from `Transform.getDirection(pitch, yaw)`), `absolutePosition`. `wishMovement` is never sent, so input
  direction is not visible to the server.
- Interaction starts arrive as `SyncInteractionChains` (`initial`, `interactionType`): a reliable key-press signal
  for bound interactions.
- Server → client motion: `ChangeVelocity(x, y, z, Set|Add, VelocityConfig)`. With a `VelocityConfig` it writes a
  separate "split" velocity that the client decays by per-client-tick resistance (ground/air, linear/exp); gravity
  stays untouched. Without one it writes the base velocity.
- Per-player tuning: `MovementManager.getSettings()` (protocol `MovementSettings`) then `update(PacketHandler)`.
  `BaseSpeed` is m/s; gravity is a constant 32 blocks/s^2 (`PhysicsConstants`).
- Mid-air jumps exist only via an armor item's `MovementSettings.ExtraJumpCount` (`ItemArmor.movementSettings`,
  an `ItemMovementSettings` in the protocol, not the player's `MovementSettings`); the client applies it, the
  server only sees `MovementStates.extraJumpsUsed` increase.
- Interaction assets: `MovementCondition` (8 input directions, client-side), `GroundedCondition` (`Tolerance`),
  `ApplyForce` (`Duration`, `RunTime`, `VelocityConfig`), `StatsCondition`, `ChangeStat`, `ApplyEffect`,
  `EffectCondition`, `Parallel` (forks, waits for all, needs 2+). `--generate-asset-schema <dir>` dumps JSON
  schemas for every asset type: far better than guessing codecs.
- Held-item input routing: unarmed fallbacks (`UnarmedInteractions` `Empty`/`Item`/`Block`) only apply with empty
  hands; with an item the client uses `Item.interactions`.
- HUD: `CustomUIHud` + `HudManager.addCustomHud(playerRef, hud)` (multiple keyed HUDs built in). Build a
  `UICommandBuilder` with `appendInline(null, doc)` at the root and `set("#Id.Prop", value)`, then send it with
  `hud.update(false, cmd)`. No element rotation, so arcs are built from small dots.
- Effects (`EntityEffect.ApplicationEffects`): `EntityAnimationId`, `MovementEffects` (`DisableJump`, `Disable*`
  directions), `Particles` attached to body nodes (`Hip`, `Chest`, ...).

## Build steps
1. `gradle jar` (sources compile against the installed server jar).
2. `python3 tools/gen_assets.py` regenerates all interaction/effect/item JSON from the Deadlock numbers.
3. Drop the jar in the server's `mods/`, restart (asset changes need a restart; code-only changes hot-reload with
   `plugin reload <group>:<name>`).
4. Players bind "Use Ability 4" to Shift and Crouch to Ctrl, and keep Sprint off Shift/W.

## Verification
- Oracle: the plugin's per-packet CSV telemetry (state bits, position, velocity, look) plus event lines, read after
  every human playtest (KDE Wayland, so no input automation). Examples: ground dash measured 9.9-10.8 m against
  Deadlock's 10 m; dash detection fires 10-28 ms before the velocity onset; jump apex and airtime; slide decay.
- Root causes were found from telemetry each time (see Gotchas), not by guessing.
- Final check: the human recorded a 27 s showcase take on the lab server (OBS, 3440x1440 at 60 fps) exercising
  dash, dash-jump, slides, wall jumps and the HUD: https://youtu.be/qWrUCAHnvYg
- Not verified: remote-server latency feel, multiple simultaneous players, controller input.

## Gotchas
1. **Dash on Sprint only fired running forward on the ground.** **Cause:** `sprinting` state only turns on for
   forward ground movement; the client sends nothing for Shift otherwise. **Fix:** dash as a client-predicted
   interaction on an ability input.
2. **Per-tick server `ChangeVelocity Set` made ledges float and lost distance.** **Cause:** `Set` without config
   overwrites vertical velocity too; client friction fights the 30 Hz updates. **Fix:** client-side `ApplyForce`.
3. **Unarmed interaction patch failed asset validation at boot.** **Cause:** patching on the initial
   `LoadedAssetsEvent` ran before RootInteractions loaded. **Fix:** patch in `start()`; re-patch only on
   non-initial events.
4. **Client crash "X: value NaN is not finite" when sprinting.** **Cause:** `forwardSprintSpeedMultiplier` exactly
   1.0 (client divides by multiplier - 1). **Fix:** keep it > 1.
5. **Slides only forward; crouch ignored while sprinting.** **Cause:** the native slide needs the sprint state, and
   crouch is dropped while sprinting. **Fix:** disable the native slide (`MinSlideEntrySpeed` 999) and run a server
   slide: split-velocity `ChangeVelocity` + effect with the `Slide` animation + `MovementEffects` disabling input.
6. **Looping effect animation stuck after removal.** **Cause:** removing the effect doesn't stop a looping
   animation. **Fix:** apply a short non-looping animation effect at the end.
7. **`ApplyForce` with `Duration` cancels gravity.** **Cause:** it sets the whole velocity every frame. **Fix:** a
   flat `Serial` of one-shot `Set` steps (0.05 s `RunTime`) each behind `GroundedCondition`.
8. **Server OutOfMemoryError at boot.** **Cause:** nesting steps under `ApplyForce.Next` makes the interaction
   compiler expand branches exponentially. **Fix:** a flat `Serial`.
9. **Dash-jumps flattened 15-50 ms after launch.** **Causes:** takeoff can arrive a packet before the jump flag;
   `GroundedCondition`'s default tolerance passes just after takeoff; a queued step could still fire. **Fix:** wait
   0.1 s for the jump flag, `Tolerance: 0`, and cancel the dash chain server-side
   (`InteractionManager.cancelChains`).
10. **Lingering push after slides/dashes.** **Cause:** the split velocity keeps the last `VelocityConfig`'s ground
    resistance (near 1) after the move ends. **Fix:** always send a final split packet with fast ground resistance,
    and re-send it shortly after to beat in-flight steps.
11. **Air jump random super-launch.** **Cause:** correction computed from the last reported vy, which sometimes
    predated the client's own extra jump. **Fix:** `Add` relative to the native jump force.
12. **Disabling jump mid-rise killed the jump.** **Cause:** `MovementEffects.DisableJump` counts as releasing jump;
    variable jump height cuts it. **Fix:** only lock jump while falling and 0.35 s after takeoff.
13. **Slide-jump loops gained speed.** **Cause:** Hytale air control stacks run speed on top of split momentum.
    **Fix:** credit max(leftover split, run speed), never the sum; Deadlock's leap penalty and post-jump drag.
14. **No input reaches the server during a mantle.** **Cause:** the client suppresses crouch and interaction input
    for the whole ~1 s mantle (verified with an extra Ability binding). **Fix:** mantle glide on a crouch press
    within 0.6 s after the mantle.
15. **Dash missing with an item in hand, even after patching every `Item.interactions`.** **Causes:** joining
    clients get prebuilt packets (`HytaleAssetStore.cachedInitPackets`, `Item.cachedPacket`), and the client
    never starts **Ability2** chains for held items. **Fix:** clear both caches after patching; use **Ability4**
    (works empty-handed and with items; only crossbows define their own). Neither cache is in the public API
    reference (docs.hytale.com/api), so this fix depends on server internals that can change between versions.
16. **Interaction root `BlockedBy` wasn't the problem.** The server-side item packet was verified
    (`Item.toPacket()` contained the binding) before blaming the client.
17. **Air/wall jumps without an armor item.** **Fix:**
    `InventoryComponent.Armor.ensureCapacity((short) 5, remainder)` adds a fifth slot (the list collects items
    that don't fit); slots past the four `ItemArmorSlot`s get `SlotFilter.DENY` for adds, so players can't use it;
    the server fills it with `setItemStackForSlot(slot, stack, false)`. The client counts its `ExtraJumpCount`
    and shows nothing.
18. **Duplicate cores in the inventory after rejoining.** **Cause:** the armor container reloads at four slots and
    the saved fifth item overflows into the inventory. **Fix:** sweep all inventory sections for strays every
    second.
19. **Ribbon trails never disappear.** **Causes:** attached to `Entity` they are never removed (cancelling the
    chain or a client-owned fork doesn't help); on the default part they attach to the held item until its next
    action; server-started chains play trails but never end them on the client. **Fix:** a timed `EntityEffect`
    with trail particles on `Entity`/`Hip` (vanilla `Dagger_Pounce` pattern).
20. **Particle `Color` doesn't tint vanilla trails.** **Cause:** spawners hard-code keyframe colours. **Option:**
    child spawners with `Parent` and their own `Particle.Animation` colours.
21. **Duplicate plugin at boot.** **Cause:** an old version's jar left in `build/libs` was copied too. **Fix:**
    delete old jars in the `jar` task and deploy only the newest.

## Assets
No generated art. Assets are JSON only: interactions, effects, a stamina stat override, two items, a
language file. Vanilla animations, particles and textures are referenced by ID/path, never copied. A
generator script (`tools/gen_assets.py`) holds all Deadlock-derived numbers.

## Cost and time
One long session (~9 hours wall-clock) with about 40 human playtest rounds.

## Open questions
- Gravity can't be changed per player; heights match Deadlock, airtime is ~20% shorter.
- Deadlock's `sv_gravity` was assumed to be 800 hu/s^2 (not in its data files).
- The dash streak is the vanilla orange; a blue `Parent`-inherited spawner was built but not adopted.
- Behaviour on a remote server with real latency is untested.
