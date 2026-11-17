---
kind: game
title: 'SkyCraft-style mob mirror: Valheim creatures punched from Minecraft through a two-mod bridge'
game: Valheim
games_also:
- Minecraft Java
game_version: 'Valheim 1.0 (l-1.0.16, buildid 25527674, steam 892970)'
platform: windows
engine: unity-mono
route: passthrough
tools:
- BepInEx 5 (denikson pack)
- Fabric Loader 0.19.5
- fabric-api 0.162.0
- Loom 1.18.4
anti_cheat: none found by um scan
status: working
agents:
- OpenCode (GLM-5.3 Flash Free)
humans: []
date: '2026-11-17'
links:
- https://github.com/chasmlol/SkyCraft
tags:
- minecraft-26.3
- skycraft
- actor-proxy
- cross-game-bridge
- textdisplay
---
# SkyCraft-style mob mirror: Valheim creatures punched from Minecraft through a two-mod bridge

Valheim is the master: a BepInEx 5 plugin streams its nearby creatures at 5 Hz over a JSON-lines
TCP bridge, and a Fabric mod for Minecraft 26.3 renders each creature as a vanilla client-side
`Display.TextDisplay` floating label (the SkyCraft actor-proxy model). A left click on a label in
Minecraft resolves that exact Valheim creature by stable id and the master applies its own damage.
Verified live: `hit Boar (z678278839_329708)` in the BepInEx log from a plain click in a real MC
world while Valheim ran next to it; the previous boar died to the damage.

## Setup

- **Valheim 1.0** (l-1.0.16, network 40), Steam appid 892970, buildid 25527674,
  **Unity 6000.0.75f1, Mono backend**, Windows 11. BepInEx 5 from the denikson pack;
  plugin is net472, references `assembly_valheim.dll` (game code in 1.0 — `Assembly-CSharp.dll`
  is empty), built with dotnet SDK 11.
- **Minecraft Java 26.3** (ships unobfuscated — no remapping), **Fabric Loader 0.19.5**,
  **fabric-api 0.162.0+26.3**, Prism Launcher 11.1.1 portable. Mod built with
  Loom 1.18.4 on **JDK 25** (Prism's `java-runtime-epsilon`). See
  [Fabric mods for 26.x without mappings](../../techniques/fabric-mod-for-26-x-without-mappings.md).
- Transport: JSON lines on `127.0.0.1:24590`, Valheim hosts the listener (master owns world
  truth), MC connects and auto-reconnects. State frames ≤10 Hz both ways, `cmd` frames V→MC,
  `event` frames MC→V.

## Route and why

Live state exchange (both games running for real, one mod each), not frame compositing —
the goal is gameplay bridging. For the mob mirror specifically, SkyCraft's actor-proxy model was
adopted instead of a "cone search": the master streams entity positions, the slave renders local
proxy entities, and a hit on a proxy maps back to the exact entity by id. The alternative
(a look-direction cone resolved on the master) is kept only as a fallback for labelless punches.

## How the game works (what we had to learn)

**Valheim side:**

- `Character.Instances` is a `List<IMonoUpdater>`; cast entries to `Character`. Filter
  `character == Player.m_localPlayer` and `GetHealth() <= 0f`. `GetHealth()/GetMaxHealth()`
  work in 1.0. A creature's stable identity is its ZDOID: `z<UserID>_<ID>`, available via
  `ZNetView.GetZDO()`; `m_uid.IsNone()` marks entities without one (raw-spawned ones — key them
  by instance id instead).
- `ZNetScene.GetPrefab(name)` is **case-sensitive**; working spawn prefabs: `Boar`, `Deer`,
  `Neck`, `Greyling`, `Chicken`, `Gull`.
- Damage is just `Character.Damage(...)`; a boar (10 HP) dies to a single 40-damage hit.

**Minecraft 26.3 side:**

- Client-only entities work fine in a `ClientLevel`: construct the entity, **call `setId(int)`
  before `level.addEntity(...)`**, then it renders and is pickable. 26.3 has **no shared entity
  id counter to borrow** (`javap` shows no `ENTITY_COUNTER`/AtomicInteger field on `Entity`) —
  assign your own ids; descending from a high base (2_100_000_000) avoids colliding with ids
  the integrated server hands out.
- `Display.TextDisplay`'s text is a private synched property: get `DATA_TEXT_ID` via reflection
  and `d.getEntityData().set(accessor, Component)`.
- The type comes from `net.minecraft.world.entity.EntityTypeIds.TEXT_DISPLAY` (a `ResourceKey`)
  resolved through `BuiltInRegistries.ENTITY_TYPE.getValue(key)` — in 26.3 the constants moved
  off `EntityType`.
- **Vanilla crosshair picking (`Minecraft.crosshairPickEntity`, public in 26.3) only reaches
  player arm reach (~5 m)**, and creative reach is still 5 — floating labels hovering over mobs
  at 9–10 m are never picked by it. Own ray-vs-proxy-position pick with an angular tolerance is
  the way.
- `WorldRenderEvents` is gone in fabric-api 0.162 (26.3) — that's why the proxies are real
  entities rather than a hand-drawn overlay.
- Rotating the camera at a world point from a client command: `player.setYRot(yaw)`,
  `player.setXRot(pitch)` are public (`setRot` is protected); MC yaw 0 faces +z,
  `look.x = -sin(yaw)`, `look.z = cos(yaw)`, positive pitch is down.
- MC 26.3 +y is up, +z is south; Valheim x/z map 1:1 (1 m = 1 block) with z negated
  (`vz = anchor.z - (mcz - anchorMcz)`), and Y is mapped relative to a player-set anchor
  because the two worlds' ground heights differ.

## Build steps

Repo layout (link, not inline): `examples/valheim-minecraft-bridge/` in the universal-modder
repository — `valheim/ValheimBridge/src/{BridgePlugin,BridgeServer,MobTracker,McCommandApplier,JsonLite}.cs`,
`mc/src/main/java/dev/um/valheimbridge/{MobMirror,ValheimInbound,McInteraction,ValheimCommands,BridgeConnection}.java`,
one mixin (`MinecraftMixin`) injecting into `Minecraft.tick` and `Minecraft.startAttack`.

1. `dotnet build -c Release valheim/ValheimBridge/ValheimBridge.csproj` (csproj references the
   game's own DLLs via a `GameDir` property).
2. `cd mc && gradlew.bat build` (JDK 25).
3. `powershell -File scripts/install.ps1` deploys the DLL into
   `Valheim\BepInEx\plugins\ValheimBridge\` and the jar into the Prism instance's mods folder
   (this instance's game root is `...\instances\26.3(1)\minecraft\`, so the mods folder is
   inside the game root).
4. Start both games, enter a world in each, then `/vbridge anchor` in MC to set the shared
   origin. `/vbridge spawn Boar` asks the master to spawn; `/vbridge aim` turns the camera at
   the nearest label; `/vbridge smack` attacks the nearest label by id without aiming.

## Verification

- The live bridge was the oracle on both sides at once: Valheim's
  `D:\...\BepInEx\LogOutput.log` and the Prism instance's `logs/latest.log`. Evidence lines:
  `[mobs] mirror: 2 creatures (Character.Instances 21)` at 5 Hz; MC
  `mob mirror: Boar -> z678278839_...`; and after a click, Valheim
  `[MC] attack: hit Boar (z678278839_329708) at (148.7, 28.4, -203.6)`. The boar hit earlier
  (`..._329395`) died to the 40 damage — the stream then carried a fresh id.
- Screenshots confirmed labels render over the MC beach (`artifacts/mc_break.png`,
  `artifacts/slice3_hit_proof.png`) and F3+B showed their entity boxes.
- A synthetic Python peer (`tests/synthetic_peer.py`) exercised the MC half alone before the
  live run.
- Not verified: many mobs at once (only 1–2), the `i<instanceId>` raw-spawn id path, death
  cleanup on the MC side beyond the 5 Hz upsert, multiplayer beyond a single local client.

## Gotchas

1. **Labels never appear in MC although Valheim streams them.** Cause: the bridge's tiny JSON
   writer serialized `List<object>` as a *quoted string*, so the whole `mobs` array arrived
   unparsable. Fix: recursive encoding for nested lists/objects. Lesson: when a mirror shows
   nothing, dump the raw wire bytes before touching the renderer.
2. **`Tried to access entity ID before ID assignment` on every label spawn (MC 26.3).** Cause:
   client-added entities must have an explicit id before `ClientLevel.addEntity`, and 26.3 has
   no shared counter to copy. Fix: `entity.setId(...)` first — descending ids from a high base
   so they can't collide with server ids.
3. **Punching straight down never hits ("no target in the cone").** Cause: the legacy cone
   dropped the look vector's Y, so a downward punch resolved as "forward" and the point-blank
   mob below was outside the cone. Fix: full 3D look (`(dir.x, dir.y, -dir.z)`, MC +z south →
   Valheim −z) plus a point-blank pass (≤1.2 m) that skips the cone entirely.
4. **Every click at a label yields the cone fallback, never the exact-id hit.** Cause: vanilla
   `crosshairPickEntity` is limited to player reach (~5 m); the labels hover at 9–10 m where
   creatures stream. Fix: at `Minecraft.startAttack` HEAD, ray-pick the nearest proxy label
   within 6° of the look ray (labels update at 5 Hz and the creatures wander — the tolerance
   absorbs that), send `cmd attack {id}`, and only fall through to the legacy cone when no
   label is near the ray.
5. **`/vbridge aim` then a click still misses.** Cause: between the aim command and the click
   the boar wanders and the 5 Hz label moves a few degrees. Fix: keep the gap small (aim →
   click within ~0.3 s) and the 6° tolerance does the rest; `/vbridge smack` is the
   deterministic path when the game is being driven by a script.
6. **Driving the games for verification: `key 0x01` does nothing in Minecraft.** Cause: 0x01 is
   the *keyboard* VK_LBUTTON; MC ignores it. Fix: use real mouse clicks — `um win drive "click x y"`
   with coordinates in **physical** frame pixels (capture frame was 854×480 while the window
   rect reported logical units). Valheim's menus ignore mouse clicks and need Enter/Esc.

## Assets

None — labels are vanilla text (`Component.literal(name)`), no art was generated.

## Cost and time

One long session for slices 1–3 (state exchange, block place/break, mob mirror + punch);
the slice-3 punch landed on the second approach after the cone fallback proved flaky.

## Open questions

- Visible avatars instead of text (an `ItemDisplay` proxy holding a mob model, or rendered
  frames from Valheim's own camera like SkyCraft does) — `WorldRenderEvents` is gone in
  fabric-api 0.162, so entity proxies are the natural carrier either way.
- HP in the label text (the `mobs` frame already carries `hp`).
- Heartbeat → safe-state: Valheim pauses/hides mobs when MC's state frames stop, so a dead
  MC client can't leave ghost labels.
- Config for the 40 damage / 4 s⁻¹ rate; behaviour when two labels overlap inside the 6° ray
  tolerance (currently nearest wins).
