# CONTRACT — Minecraft 26.3 inside Outer Wilds (passthrough bridge)

Route: **Pattern 2, passthrough (frame compositing + state exchange)**, per
`skills/mashup-mods/SKILL.md` and `knowledge/techniques/choosing-a-mashup-route.md`.
Every fact here that crosses a process boundary is stated once, in one place; code on both sides
must match this file, and a change here is a protocol version bump.

## Parties

| Role | Process | Build | Runs as |
|---|---|---|---|
| **Host** | Outer Wilds (Unity 2019.4.39f1 Mono) + OWML 2.16.3 mod | Steam 753640, `OuterWilds.exe`, game 1.1.16.1372 | Windows PE under **Proton 11.0-100** |
| **Guest** | Minecraft Java 26.3 + Fabric Loader 0.19.5 + Fabric API | Modrinth App profile (copy of "Fabulously Optimized") | **Native Linux** JVM, Zulu 21 |

Neither process is modified at the binary level. Both are ordinary mods:
an OWML C# mod (host) and a Fabric mod (guest).

## Ownership

- **Outer Wilds owns:** the camera, the player's body, gravity volumes, the ship, the solar system,
  the 22-minute loop, and all rendering of the composited frame.
- **Minecraft owns:** its own world simulation — blocks, mobs, inventory, crafting, damage, and the
  rendering of its own world layer.
- **Who drives movement:** *Outer Wilds.* The host sends its camera pose and its ground; Minecraft
  renders from that pose with its own player hidden or standing in. Minecraft may drive its player
  locally only in an explicitly flagged mode (`drive: true`), used for e.g. flying.
- **Control hand-back:** when the guest is detached (no host message within `TIMEOUT`), Minecraft
  returns to normal first-person play on its own camera, and the host stops compositing and shows
  only its own frame. No half state.

## Units and axes

- **Scale: 1 Outer Wilds metre = 1 Minecraft block.** (BlockCraft 1.0.0 already defaulted to 1.00 m;
  this keeps that.)
- **Axes:** Outer Wilds is Unity, left-handed, Y-up. Minecraft is Y-up but Z is inverted relative to
  Unity (MC `+Z` = "south"), and MC yaw `0` faces `+Z`, increasing clockwise seen from above.
  - Position: `MC = (OW.x, OW.y, -OW.z)` — i.e. a mirror in Z.
  - Yaw: `MC.yaw = 180° - OW.yaw` (heading convention, as in the GTA V example).
  - Pitch: `MC.pitch = -OW.pitch` (OW positive pitch looks up; MC positive pitch looks down).

  These three lines are **not verified yet**, and by Unity's and Minecraft's conventions the yaw and
  pitch signs look inverted (a Z mirror gives `MC.yaw = 180 + OW.yaw` and `MC.pitch = OW.pitch`; see the
  field note). `tools/oracle.py` builds a four-colour landmark cross in the guest's world at known offsets
  and reads back where each colour lands in the exported frame, but it sends its pose straight to the guest
  in Minecraft terms, so the run below checks the guest's camera and the frame, not this mapping.
  Holding a camera directly above the cross at `(0,120,0)`, yaw 0, pitch 90 (straight down):

  | landmark | world | expected in the raw buffer | measured centroid |
  |---|---|---|---|
  | magenta | `-Z` north | up the screen | (640, 30) |
  | black | `+Z` south | down the screen | (640, 671) |
  | yellow | `+X` east | left | (142, 360) |
  | orange | `-X` west | right | (1120, 360) |

  The four centroids sit on a square centred at (631, 350) against a frame centre of (640, 360), so the
  cross is centred. The rows are bottom-up (flag 2) and the oracle reads row 0 as the top, so "north up" is
  the raw buffer; on screen, a camera facing `+Z` and looking down has south at the top.
- **Depth:** Unity's reversed-Z (`1` = near, `0` = far) with `zZeroToOne = true`. The guest declares
  its own convention per frame in the slot `flags` field; the compositor converts.
- **Time:** all timestamps use a monotonic nanosecond clock. On Linux both sides share
  `CLOCK_MONOTONIC`, so `System.nanoTime()` on the JVM and the host's own monotonic clock are
  comparable in principle — but the bridge treats them as **per-side counters only** and never
  compares absolute times across processes. Frame identity is by `frame` number.

## Transport

Two channels, both local-only. Nothing ever leaves `127.0.0.1` or the machine.

### 1. State/control — WebSocket on `127.0.0.1:25599`
JSON, one object per message, UTF-8. Guest runs the server (as the GTA V example does); host
connects as client. Versioned handshake.

Host → Guest:
| `t` | Payload | Meaning |
|---|---|---|
| `cam` | `f` frame, `p` [x,y,z], `r` [yaw,pitch,roll], `fov`, `fp`, `pl` feet, `h` body yaw | host camera + pose, already converted to MC coordinates |
| `ground` | `c` [x,z,yLow,yHigh, ...] | solid columns near the player → barriers in MC |
| `clear` | — | drop the barrier set |
| `cmd` | `c` | a Minecraft server command |
| `key` | `k`, `down` | synthetic key state |
| `hello` | `v`, `shm`, `pid` | handshake reply |

Guest → Host:
| `t` | Payload | Meaning |
|---|---|---|
| `hello` | `v`, `shm`, `pid` | the mapping name and the guest's PID |
| `explosion` | `pos`, `r` | MC explosion → host effect |
| `projhit` | `id`, `pos`, `stick` | arrow/firework hit |
| `mobs` / `mobhit` / `mobdmg` | — | mob events |
| `bye` | `reason` | guest leaving |

**Late/absent handling:** if no `cam` arrives for 2 s, Minecraft reverts to its own camera. If the
socket drops, both sides detach fully (`clear` barriers, hide the composite). A reconnect starts a
fresh handshake; no state is assumed across it.

### 2. Frames — POSIX shared memory
Object name: `blockcraft-frame` (i.e. `/dev/shm/blockcraft-frame`), opened by the guest as a file
and by the host through **`Z:\dev\shm\blockcraft-frame`** inside the Proton prefix.

The layout is the GTA V example's, which already exports exactly the three layers this needs:
world colour RGBA8, world depth float32, and an overlay (hand + HUD) RGBA8. Triple-buffered slots,
seqlock per slot, header magic `"MCPT"` → renamed `"BCFF"` (BlockCraft Frame Format) for this
project so the two never collide.

```
header 4096 bytes, little-endian
  0  u32 magic "BCFF"       4  u32 version (1)      8  u32 header bytes 4096   12 u32 slot count 3
  16 u64 slot stride        24 u32 max width        28 u32 max height
  32 u64 publish counter    40 i32 latest slot (-1) 44 i32 guest pid
  256 + 128*i: slot i
    +0  u64 seq (odd while being written)
    +8  u64 guest frame      +16 u64 host frame
    +24 u32 width            +28 u32 height
    +32 f32 near             +36 f32 far            +40 f32 vertical fov (deg)
    +44 u32 flags: 1 = depth in [0,1], 2 = rows bottom-up, 4 = reversed Z
    +48 f64 cam x  +56 y  +64 z   +72 f32 yaw  +76 pitch  +80 roll   +84 i32 first person
    +88 u64 capture nanos   +96 u64 publish nanos
slot i pixels at 4096 + i*stride; each layer is width*height*4 bytes:
  world colour RGBA8 | world depth f32 | overlay RGBA8
```

**Byte order:** little-endian on both sides (x86-64).
**Torn frames:** the reader takes `seq`, reads, re-reads `seq`; a changed or odd `seq` discards the
slot. The guest bumps the header `publish counter` *after* the slot is complete.
**Timeouts:** a frame older than 1 s is treated as stale. The composite hides on a stale frame or
an open host menu, never showing an old picture over Outer Wilds' pause menu.
**Size cap:** the guest never exports above the header's max (3840×2160); the compositor scales by
area to about 1080p, per `knowledge/techniques/frame-compositing-depth-and-pose-sync.md`.

## Lifecycle

1. **Host starts** (OWML mod loads in SolarSystem). Host opens the WebSocket client; retries every
   second while the guest is absent.
2. **Guest starts** (Fabric mod, local world only). Guest creates `/dev/shm/blockcraft-frame`,
   listens on 25599, announces `hello` with the name and its PID.
3. **Attach.** Host receives `hello`, maps the frame file via `Z:\`, and starts sending `cam` every
   host frame. Composite appears once the first valid frame is read.
4. **Detach.** Either side closing → host clears barriers, stops compositing, keeps playing normally;
   guest returns to its own camera. No residue.
5. **Loop reset** (Outer Wilds supernova / reload): the host mod re-registers when the SolarSystem
   scene loads again. The guest stays connected; the frame mapping survives. Barriers are rebuilt
   from the next `ground` message.
6. **Crash.** If the guest dies, the host sees the socket close and a stale frame → composite off.
   If the host dies, the guest times out and returns to its own camera.

## Guardrails (hard rules for this project)

- Outer Wilds: **single-player, offline.** Minecraft: **local world (or LAN at most) in the
  passthrough profile only**; the profile copy exists so the user's own worlds and account are not
  used.
- Never copy Minecraft or Outer Wilds game files into this repo. Guest textures come from the user's
  own jar at install time or are drawn as lookalikes in code. Decompiles stay out of the repo.
- Kill by exact PID. Back up Outer Wilds saves before every modded launch (`um backup create`).

## Open items to settle against the running games

- [ ] Exact Z-mirror and yaw/pitch signs. **Not settled**: the landmark cross in `tools/oracle.py`
      only checked Minecraft-frame poses sent straight to the guest. Run it through
      `HostBridge.SendCamera`; the yaw and pitch signs look inverted (see "Units and axes").
- [x] Whether Wine's `CreateFileMappingA` on a `Z:\dev\shm\...` file works in the *game's* prefix
      under Proton 11: **probe passed**, and the host's `FrameReader` does exactly this.
- [ ] Whether the host should read the frame on the render thread at `Camera.onPreCull`, and how the
      read (up to ~24 MB for RGBA+depth+overlay at the cap) is budgeted; may need a smaller export
      size than the max. **Current implementation** reads at `Camera.onPreCull` and uploads the
      colour layer to a `Texture2D`; the depth layer is read but not yet used.
- [ ] Gestalt/flat-rock layers: what Inner Wilds `VisibleToPlayer` and `physicalMask` mean for a
      composited layer that must be occluded by terrain but drawn over the sky.

## Compositor (host side), as implemented

The picture is a **screen surface in the world**, not a copy of the guest's whole view:

1. A depth-tested quad over the placement surface (game's `UI/Default` shader) writes stencil ref 61
   where it is visible, with `_ColorMask 0`. Depth test `LessEqual`, so Outer Wilds terrain in front
   of the surface occludes the picture exactly as it occludes a real object.
2. A screen-aligned quad just past the near plane (`nearClipPlane * 1.05`, the portal-gun example's
   trick) paints the guest's texture only where the stencil equals 61.

The guest's **depth layer is read but not yet consumed**: occlusion on this slice is the host's own
depth buffer, which is what the first slice is for. Per-pixel guest-depth compositing
(drawing guest geometry the host does not know about) is later work.

Currently the screen is placed by the dev bridge (`place` / `at` / `size`); which real surface it ends
up pinned to (a ship panel, a Nomai wall, a screen the player builds) is still open.
