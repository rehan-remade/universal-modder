---
kind: game
title: 'Minecraft inside BeamNG.drive (passthrough mod: WebSocket bridge + rendered Steve)'
game: BeamNG.drive
games_also: ["Minecraft Java Edition"]
game_version: 'BeamNG.drive 0.39.4.0.20972 x64 (Steam) + Minecraft Java 26.3 with Fabric'
platform: windows
engine: unknown
route: passthrough
tools: ["BeamNG's own MCP server (-enablemcp)", "Fabric Loader + Fabric API (Loom, JDK 26)", "PowerShell, fengari, luaparse"]
anti_cheat: none - offline single-player sandbox, no anti-cheat anywhere
status: working
agents:
- OpenCode (mimo-v2.6-flash)
humans:
- "@rehan_shei"
date: '2026-10-10'
links:
- https://github.com/rehan-remade/universal-modder/tree/main/examples/minecraft-beamng-passthrough
tags: [mashup, passthrough, websocket, beamng, lua-extension, tsstatic, walk-mode, camera-sync, fabric, mcp]
---
# Minecraft inside BeamNG.drive (passthrough mod: WebSocket bridge + rendered Steve)

> Real Minecraft Java 26.3 runs next to BeamNG.drive 0.39; a BeamNG Lua mod (a zip in `current\mods`)
> and a Fabric mod exchange state over a local WebSocket, and Steve is rendered inside BeamNG himself:
> a pooled 7-box TSStatic rig anchored to walk mode, with correct proportions, camera-relative facing,
> walk stride, a held item, hide-while-driving, and BeamNG's own snowman walk avatar hidden while he is
> up. It runs in the real game - verified live through BeamNG's built-in MCP server (status probes plus
> screenshots) and a 166-assertion headless Lua suite. Code: `examples/minecraft-beamng-passthrough`,
> forked from `examples/minecraft-gta5-passthrough` (the Minecraft half is reused almost unchanged).

## Setup
- BeamNG.drive **0.39.4.0.20972 x64** from Steam, Windows 11, RX 580. No anti-cheat, no loaders to
  install: BeamNG loads Lua mod zips natively from `%LOCALAPPDATA%\BeamNG\BeamNG.drive\current\mods\`.
- Minecraft Java **26.3** with Fabric Loader + Fabric API, built with Loom on **JDK 26**
  (`mc/` module, `runClient` dev config; the mod jar also installs into a vanilla `mods` profile).
- Tooling that actually ran: `npx luaparse` (syntax), `npx fengari-node-cli` (headless Lua test
  suite), PowerShell (`beamng/build.ps1` zips the mod), and **BeamNG's own MCP server** for all
  live testing (launch flag `-enablemcp`).

## Route and why
**Passthrough:** two real games side by side, one mod in each, talking over a local WebSocket
(127.0.0.1:25600). Considered and rejected: frame compositing with a ReShade add-on (the GTA V
route) - BeamNG 0.39's ReShade integration is blocked/unreliable, deferred entirely; and letting
Minecraft own the pose (would mean teleporting the walk unicycle every tick against BeamNG's own
physics). Decision: **BeamNG owns Steve's pose** (walk mode's anchor), Minecraft owns game logic
and streams the camera/held item. The Minecraft half of the GTA V example needed only one new
outbound message (held item); everything else carried over.

## How the game works (what we had to learn)
All facts below were verified in the installed game's Lua (full citations with `file:line` in
`examples/minecraft-beamng-passthrough/docs/BEAMNG_039_VERIFIED.md`).

- **Mod loading:** a zip in `current\mods` mounts at the VFS root; `scripts/modScript.lua` runs and
  calls `extensions.load('mcpassthrough')`, which resolves `lua/ge/extensions/mcpassthrough.lua`
  from inside the zip. The extension list at `lua/ge/main.lua:364` shows how game modules register;
  our module's global is `extensions.mcpassthrough`.
- **Hook frame order:** `update()` (`main.lua:920`, "after input and before physics") runs the
  WebSocket pump and game logic; physics runs; then `luaPreRender()` (`main.lua:820`, "right before
  rendering, after physics") dispatches `onPreRender` (`:823`) where every per-frame pose write must
  happen, followed by `onDrawDebug` (`:826`). Callbacks are **raw** (`extensions.lua:841,846`) -
  every hook body wraps itself in pcall.
- **Extension dispatch order is not alphabetical:** hooks run in a resolve order built by
  `table.sort` + swap-remove (`extensions.lua:111`, `:141-147`), so two extensions cannot assume
  their relative order - relevant for fighting another extension over a shared field (see Gotcha 7).
- **Walk mode is a vehicle.** `gameplay_walk` (module `lua/ge/extensions/gameplay/walk.lua`) spawns
  an actual `unicycle` vehicle from `content/vehicles/unicycle.zip`; `isWalking()` just checks the
  player vehicle's jbeam. Its pose getters (`getPosXYZ`, `getRotXYZW`) return **camera** rotation,
  because walking is camera-relative; outside walk mode they return nothing, so callers must
  nil-check. The unicycle spawns with a snowman avatar part (`unicycle_snowman` / flexbody
  `snowman_ball`) at the player's feet.
- **Rendering objects:** pool `TSStatic` objects exactly like the game's own
  `core/groundMarkerArrows.lua` (create a `SimGroup` pool, `createObject('TSStatic')` per part,
  `registerObject`, and per frame `setPosRot(x,y,z,qx,qy,qz,qw)` + `updateInstanceRenderData()`).
  There is no usable per-instance colour; colours come from a `main.materials.json` next to the
  art, discovered by `FS:findFiles('*.materials.json')` (`main.lua:1331-1339`). `shapeName` takes
  the **`.dae`** path - a raw Blender Collada with no prebuilt `.cdae` **compiles at load from the
  mod zip** (both halves of that pipeline were runtime-unknowns; both verified live).
- **Camera:** `core_camera.getPositionXYZ()` returns three values (not a table); `getYawPitchRoll()`
  returns `{yawDeg, pitchDown, rollDeg}` with yaw = `atan2(fwd.x, fwd.y)` and +Y = 0 (grows toward
  +X); FOV is vertical (65 default). World basis is Z-up right-handed; the Minecraft mapping is
  `mcPos = (x, z+yOff, -y)` and `mcYaw = wrap180(180 + yawDeg)` (not GTA's `180 - h`).
- **Vehicle render visibility:** `veh.hidden = true` is a pure render flag (nothing in `lua/ge`
  branches on it to deactivate anything); `setMeshAlpha(alpha, "", false)` is walk mode's own
  per-frame visibility lever.
- **MCP test harness:** launching with `-enablemcp` loads `mcp_server`
  (`lua/ge/extensions/core/settings/settings.lua:265-272`), a Streamable-HTTP MCP endpoint at
  `127.0.0.1:29292/mcp` (protocol 2024-11-05) with ready-made tools: `run_lua`, `load_level`,
  `get_vehicles`, `set_position`, `set_camera`/`set_free_camera`/`get_camera_state`, `toggle_ui`,
  `screenshot`, input injection, logs. This made the whole game scriptable for verification.

## Build steps
1. Minecraft side: `cd mc; .\gradlew.bat runClient` (dev, JDK 26) or `build` and drop the jar into
   a Fabric profile's `mods/`. It listens on `ws://127.0.0.1:25600`.
2. BeamNG side: `powershell -ExecutionPolicy Bypass -File beamng\build.ps1` builds
   `beamng\mcpassthrough.zip` (art + Lua + script); copy it to
   `%LOCALAPPDATA%\BeamNG\BeamNG.drive\current\mods\mcpassthrough.zip`.
3. Launch BeamNG: `Bin64\BeamNG.drive.x64.exe -enablemcp -gfx vk` (see Gotcha 1), load any level
   (we used `smallgrid`), **wait ~60 s** for late vehicle materialization (Gotcha 2), then enter
   walk mode (in-game key, or `extensions.gameplay_walk.setWalkingMode(true)` over MCP).
4. Start Minecraft; the bridge reconnects by itself (`phase: "up"` in the status probe).
5. Headless tests: `npx luaparse beamng\mod\lua\ge\extensions\mcpassthrough.lua` and
   `npx --yes --package=fengari-node-cli fengari tests\lua\test_ipc.lua` (166 assertions).

## Verification
- **Oracle:** BeamNG's own MCP server. `extensions.mcpassthrough.status()` over `run_lua` exposed
  the whole session (walking, shown, anchor, yaw, speed, stride phase, held item, `fpHidden`,
  `avatarHidden`, `avatarProbe`, `hookErrors`); `screenshot` + `get_camera_state` gave visual
  proof from commanded cameras. Screenshots cited in the example's docs (hero, mid-stride with the
  held item, fp with the rig suppressed, an A/B pair proving the snowman hide).
- **Unit suite:** 166 fengari assertions covering IPC state machine, pose/pivot math, stride
  contralateral swing, held-item visibility, avatar hide/restore, rig lifecycle.
- **Checked live:** text WebSocket frames, `''` subprotocol, mod-zip load, raw-`.dae` compile +
  materials, facing equals camera look direction (yaw 0 and 180 bearings), feet on the ground
  plane, stride advancing/settling, hide on `be:enterVehicle` and avatar restore, MC restart
  reconnect, level-reload survival, `hookErrors: 0` throughout.
- **NOT verified:** the gold-wall yaw-sign measurement (MC-bound yaw sign stays source-derived);
  pitch/roll pass-through into MC; MC-side Steve's facing; scale behaviour of the block pool (out
  of Phase 5 scope); any ReShade compositor (deferred); Steve has no physics/collision of his own
  (render rig anchored to the walk vehicle by design).

## Gotchas
1. **Symptom:** BeamNG crashed instantly on launch with `-gfx d3d12`. **Cause:** D3D12 backend is
   unstable on the RX 580 (driver). **Fix:** launch with `-gfx vk`; Vulkan ran stable for hours.
2. **Symptom:** entering walk mode right after `load_level` silently fails - seconds later the
   player is back in a car, `isWalking()` false. **Cause:** BeamNG's own late vehicle-ready logic
   switches the player vehicle ~10-40 s after load. **Fix:** wait 45-60 s after load before
   `setWalkingMode(true)`; verify with a status probe.
3. **Symptom:** scripted "toggle walking off" no-ops. **Cause:** `toggleWalkingMode()` only exits
   walk mode when a vehicle is in front of the player (`walk.lua:164-166`). **Fix:** enter with
   `setWalkingMode(true)`; exit by `be:enterVehicle` into a real car.
4. **Symptom:** first-person walk camera never engaged over MCP - `fpHidden` stayed false, the rig
   visible from inside. **Cause:** free cameras are sticky across vehicle switches. **Fix:** set a
   normal camera first (`set_camera {name='orbit'}`), then `setWalkingMode(true)` - the walk entry
   then switches to the `unicycle` camera at eye height = walk anchor + 0.8 m.
5. **Symptom:** `walk.getPosXYZ` is nil. **Cause:** the module global is `gameplay_walk` (auto-load
   list `main.lua:364`), and the getters return *nothing* when not walking (`walk.lua:332-337`).
   **Fix:** resolve via `extensions.gameplay_walk` and nil-check the result.
6. **Symptom:** WebSocket handshake rejected against the Java-WebSocket server. **Cause:** the
   subprotocol argument to `BNGWSClient.getOrCreate` must be a string, not nil. **Fix:** pass `''`.
7. **Symptom:** the snowman ball occluding Steve's legs would not go away despite calling
   `setMeshAlpha(0, "", false)` every frame from our `onPreRender` *and* `onUpdate`. **Cause:**
   walk mode re-sets the alpha every `onUpdate` (`walk.lua:274-283`) and dispatch order let its
   write land after ours - order between extensions is sort+swap-remove, not alphabetical.
   **Fix:** stop fighting over alpha; use the `hidden` field (Gotcha 8).
8. **Symptom:** hiding the unicycle via `veh.hidden = true` "did nothing" - the ball stayed, and
   probing `u.hidden` returned nil. **Cause:** the field **reads back nil on a fresh vehicle
   wrapper until Lua writes it** (writes do reach the vehicle) - and our nil-guard skipped the
   hide entirely; that guard silently cost two rebuild cycles. **Fix:** never nil-guard the read,
   just set it; report which guard last ran in a status field (`avatarProbe`) so a silent skip can
   never hide again. Restore is on us: save the id, `getObjectByID(id)` later, set `hidden = false`
   when the player drives.
9. **Symptom:** first-person screenshots were filled with the inside of Steve's head/torso boxes.
   **Cause:** our rig is visible to its own fp camera (walk's snowman solves this by distance
   fading). **Fix:** suppress *all* rig boxes while the camera sits inside the rig's local bounding
   column (a small X/Y radius, Z from feet to head); status field `fpHidden` proves the rule fired.
10. **Symptom:** MCP `screenshot` returned a path whose file didn't exist yet, or a frame from a
    camera commanded microseconds earlier. **Cause:** `screenshot` queues `createScreenshot2` and
    returns immediately; the file lands a few frames later (`mcp/tools/system.lua:66-77`).
    **Fix:** poll `get_camera_state` before the call and treat the capture as that frame; give
    async files a beat before copying them.
11. **Symptom:** `set_position` / `be:enterVehicle` silently did nothing. **Cause:** object ids
    change every session (and the late-vehicle switch re-creates vehicles). **Fix:** re-query
    `get_vehicles` before each id use; verify with `getPosXYZ` afterwards.
12. **Symptom:** fear that a raw `.dae` in a mod zip needs a prebuilt `.cdae`, and that mod-dir
    materials are ignored (both long-standing runtime unknowns). **Cause:** n/a - both work.
    **Fix:** none needed - ship the `.dae` + a `main.materials.json` with per-material
    `baseColorFactor`; the engine compiles and discovers them at load.
13. **Symptom:** an "Unknown app: skillChain" panel floats in the UI during tests. **Cause:** the
    userfolder's active UI layout references an app id it doesn't have - not from our mod zip (it
    ships no UI files). **Fix:** ignore it / reset the UI layout; not a mod bug.

## Assets
Steve is 7 boxes (head, body, 2 arms, 2 legs, item) authored procedurally by
`beamng/gen_steve_art.ps1` into Blender Collada: Minecraft palette colours via
`main.materials.json` `baseColorFactor`, 1 px = 1/16 m scaled to a 2.0 m figure, joint pivots
baked into each `.dae` origin (limbs span z = -0.75..0) so `setPosRot` is the joint transform with
no runtime offset math. No AI-generated art needed.

## Cost and time
Five phases over two days (~10 live two-game sessions); no API spend (no fal - procedural art).
Most of the live time went to the walk-avatar snowman fight (Gotchas 7-8) and to building an
evidence-grade screenshot set through the MCP harness.

## Open questions
- Block rendering scale: the pooled-TSStatic budget beyond Steve's 7 boxes (Phase 6).
- Full GTA-style frame compositing (colour + depth) needs a working ReShade add-on path in 0.39 -
  deferred (Gotcha-free area is only world-space rendering).
- Definitive gold-wall check of the MC-bound yaw sign; MC-side Steve facing comparison.
- Phase-scope leftovers: Elytra, TNT reactions, block placement, richer inventory.
