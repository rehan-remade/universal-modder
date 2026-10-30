# Real Minecraft running inside Outer Wilds (passthrough)

Minecraft Java runs beside Outer Wilds, and Outer Wilds paints Minecraft's actual picture on a surface **in
the world**, depth-tested so OW terrain in front of that surface occludes it like any real object. Two real
games, one mod in each:

- **Host** — an OWML C# mod in Outer Wilds. Owns the player and the camera.
- **Guest** — a Fabric mod in Minecraft Java. Owns its own simulation, renders its own frame, hides its own
  player, and takes its camera pose from Outer Wilds.

They talk over a local WebSocket (camera pose, control, game commands) and POSIX **shared memory** (the
rendered frame: colour + depth + overlay, three seqlocked slots).

Built and tested in October 2026 on Linux (KDE Plasma / Wayland, AMD RX 6600) with Outer Wilds **1.1.16.1372**
(Steam AppId 753640, Echoes of the Eye) under **Proton 11.0-100**, OWML **2.16.3**, Outer Wilds Mod Manager
**0.15.7**, and Minecraft Java **26.3** with Fabric Loader **0.19.5** (native Linux). The field note has the
full story: `knowledge/games/outer-wilds/real-minecraft-running-inside-outer-wilds-passthrough-frame-.md`.

## State: a working first slice, not a finished mod

Working now, verified live:

- The guest's frame reaches the host and is **real imagery** (not a stale or black frame).
- The picture is drawn on a **depth-tested screen surface in the world** — OW terrain in front occludes it.
- The camera override works: 5 different camera poses, sent straight to the guest, produce 5 distinct, fully
  populated frames.
- The guest's player is hidden and its camera follows Outer Wilds'.
- The guest's camera and the frame layout are checked by a measurement, not by eye — see "The axis oracle"
  below. The host's Outer Wilds → Minecraft conversion is **not verified yet**.
- The host reconnects, detaches cleanly, and survives a loop reset.

Not done yet:

- The screen is placed by a **dev command**, not pinned to a real surface (a ship panel, a Nomai wall).
- The guest's **depth layer is exported but not composited**, so guest geometry the host does not know about
  is not yet occluded per-pixel.
- Tested at one guest size (1280x720) on one machine. Not tested: other GPUs/drivers, other resolutions,
  other Minecraft worlds.

The host still carries a **BlockTool** (blocks you can place in the world) from an earlier plan to port
Minecraft's *content* into Outer Wilds. That plan was dropped — the whole point is that the real Minecraft is
running — but the tool is live code the mod registers at scene load, so it is left in place rather than
half-removed. See `MODDING_PLAN.md`.

## Install

Needs: Outer Wilds (Steam) + the [Outer Wilds Mod Manager](https://outerwildsmods.com/) with OWML 2.16+, a
Minecraft Java profile you can add mods to (a **copy** of it, ideally), **JDK 25**, the **.NET SDK**, and
Python 3.

1. **Guest.** Build the Fabric mod and deploy it into a Minecraft profile:

   ```
   cd mc && ./gradlew build
   ```

   The exporter uses the Java FFM shared-memory API, which needs **JDK 25**; `mc/gradle.properties` points
   Gradle at it via `org.gradle.java.home` — change that line if yours lives elsewhere. Then point
   `tools/install-guest.py` at your profile (`APP` at the top of the file) and run it. Use a *copy* of your
   profile so your own worlds and account are untouched.

2. **Host.** Build the OWML mod. This writes **straight into the live OWML mods folder**, so there is no
   separate deploy step:

   ```
   cd ow/src && dotnet build -c Release
   ```

   On Linux, OWML stores its paths the Linux way and adds the `Z:` prefix itself, so a config with `Z:\...`
   makes the game report "Current game path is not valid". `tools/fix-owml-config.py` writes it correctly
   (and sets `forceExe: true`, which the passthrough needs):

   ```
   python3 tools/fix-owml-config.py --dry-run     # show what it would write
   python3 tools/fix-owml-config.py               # repair
   ```

3. **Run.** Guest first (the host retries until it appears), then Outer Wilds from Steam, then load a save.

   > **The passthrough starts on the `SolarSystem` scene, not the title screen.** Reaching the title screen
   > proves the mod loaded; loading a save proves the bridge works.

   `SLICE1-CHECKLIST.md` has the full ordered checklist, including the guest's ~2.5 minute startup and how to
   clear a stale Steam launch that would otherwise block a new one.

## How it works

- **Transport.** A local WebSocket on `127.0.0.1:25599` carries JSON: the host's camera pose each frame, plus
  ground columns, commands and key state. The rendered frame goes a different way — **POSIX shared memory**,
  `/dev/shm/blockcraft-frame`, which the Proton-side host opens as `Z:\dev\shm\blockcraft-frame`. Three
  seqlocked slots, each holding colour (RGBA8), depth (float32) and overlay (the hand and HUD), with a header
  carrying the pose that produced each frame. `docs/CONTRACT.md` is the authoritative layout.
- **The picture is a surface in the world, not a copy of the guest's whole view.** Two passes with the game's
  own `UI/Default` shader: a depth-tested quad over the placement surface writes stencil ref 61 with
  `_ColorMask 0` (`LessEqual`, so OW geometry in front hides it), then a near-plane screen quad paints the
  guest's texture only where the stencil is set. This is the same trick as the portal-gun example.
- **Ownership.** Outer Wilds owns the player and camera; Minecraft owns its own simulation. The guest's camera
  is driven from the host pose through a `Camera` mixin (`rotationYXZ(pi - yaw)`), and the guest's player is
  hidden. If no pose arrives for 2 seconds, Minecraft reverts to its own camera and the host stops compositing —
  no half state.
- **Reading Minecraft's frame** is the hard part, and the field note's gotcha 1 explains why: on this stack
  `copyTextureToBuffer` (and vanilla's own screenshot path) returns **black**. The exporter binds its **own FBO**
  to the GL texture and uses raw `glReadPixels`. If you reuse this code, do not "simplify" it back.

## The axis oracle (`tools/oracle.py`)

The contract's coordinate mapping — Outer Wilds (Unity, Y-up) to Minecraft:

```
MC = (OW.x, OW.y, -OW.z)      # Z mirror
MC.yaw   = 180 - OW.yaw
MC.pitch = -OW.pitch          # OW positive pitch looks up, MC positive looks down
```

A wrong sign still renders *a picture*, so this needs a **measurement**. The oracle builds a
four-colour landmark cross in the guest's world (north magenta, south black, east yellow, west orange — four
colours pin down a rotation *and* a mirror), holds the guest camera directly above it looking straight down,
and reads back where each colour lands in the exported frame:

| landmark | world | contract says | measured |
|---|---|---|---|
| magenta | `-Z` north | up the screen | (640, 30) |
| black | `+Z` south | down the screen | (640, 671) |
| yellow | `+X` east | left | (142, 360) |
| orange | `-X` west | right | (1120, 360) |

What this run proves is narrower than the mapping above. The oracle sends its pose straight to the guest
in Minecraft terms (yaw 0, pitch 90), so it checks the guest's camera and the exported frame, whose rows are
bottom-up (so "north up" is the raw buffer, not the screen); the host's conversion in `HostBridge.SendCamera`
isn't in the loop. By Unity's and Minecraft's conventions that conversion's yaw and pitch signs look inverted
(`MC.yaw = 180 + OW.yaw`, `MC.pitch = OW.pitch` for a Z mirror): see the field note before relying on it.
**This method is the reusable part** — it needs no
documentation of the other game's axes, and it caught three separate bugs that each produced a confident,
wrong answer. If you port this to another host, port the oracle with it.

`tools/pose-sweep.py` is the cheaper regression check: it sends different poses and hashes the exported frame,
so "the camera override still works" is one command.

## Developer test bridge

Create an empty `dev.enabled` file in the mod folder and the mod reads commands from `dev_commands.txt` and
logs to `dev_log.txt` (screenshots in `shots/`). Useful commands: `state`, `place`, `size`, `at`, `shot`,
`oracle on|off`, `control`. Delete `dev.enabled` to turn it off. This is how the whole slice was verified
without touching the mouse or keyboard — see
`knowledge/techniques/driving-a-game-from-a-mod-side-command-file-lab-profile-wake.md`.

The guest has matching dev messages over the same WebSocket (`cmd`, `pose`, `pin`, `oracle`), which is how
`tools/oracle.py` and `tools/pose-sweep.py` drive it.

## Credits

- Outer Wilds: Mobius Digital. OWML, HarmonyX and the Mod Manager: the Outer Wilds modding community.
- Minecraft: Mojang. Fabric Loader and Fabric API: the Fabric community.
- Built with an AI coding agent (OpenCode) working in the universal-modder toolkit.
- No game files ship with this folder. Nothing from either game is redistributed.
