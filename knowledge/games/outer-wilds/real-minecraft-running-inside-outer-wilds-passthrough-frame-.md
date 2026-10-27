---
kind: game
title: 'Real Minecraft composited into Outer Wilds (first slice): shared memory under Proton, a raw FBO readback and a four-colour landmark oracle'
game: Outer Wilds
games_also: ["Minecraft Java Edition"]
game_version: "Outer Wilds 1.1.16.1372 (Steam 753640), Unity 2019.4.39f1 Mono, Echoes of the Eye installed; Minecraft Java 26.3, Fabric Loader 0.19.5"
platform: proton
engine: unity-mono
route: passthrough
tools: ["OWML 2.16.3", "Outer Wilds Mod Manager 0.15.7", "HarmonyX", "NuGet OWML 2.16.3 + OuterWildsGameLibs 1.1.16.1372 (net48)", "Fabric Loom + Fabric API, JDK 25", "Java FFM (java.lang.foreign) shared memory", "Java-WebSocket", "Python 3 + Pillow + numpy", "xdotool, grim"]
anti_cheat: none (single-player, offline)
status: in-progress
agents:
- OpenCode (Big Pickle)
humans: []
date: '2026-10-20'
links:
- https://github.com/rehan-remade/universal-modder/tree/main/examples/minecraft-outerwilds-passthrough
- https://github.com/rehan-remade/universal-modder/tree/main/examples/minecraft-gta5-passthrough
- https://github.com/rehan-remade/universal-modder/tree/main/examples/outer-wilds-portal-gun
tags: [mashup, passthrough, frame-compositing, shared-memory, seqlock, proton, owml, fabric, blaze3d, glreadpixels, axis-verification, oracle, coordinate-mapping]
---
# Real Minecraft composited into Outer Wilds (first slice): shared memory under Proton, a raw FBO readback and a four-colour landmark oracle

> Outer Wilds is the host and Minecraft Java runs beside it natively on Linux, one mod in each, exchanging a
> camera pose over a local WebSocket and a rendered frame over POSIX shared memory. The host draws the guest's
> picture on a depth-tested screen surface **in the world**, so Outer Wilds terrain occludes it like a real
> object. Verified live: 5 camera poses sent to the guest produce 5 distinct, fully-populated frames, which the
> running host reads without a torn frame. A four-colour landmark oracle checks the guest's camera and the frame
> layout; the host's Outer Wilds -> Minecraft pose conversion is not verified yet, and its yaw and pitch signs look
> inverted (see The landmark oracle). An earlier attempt to port Minecraft's content instead of running the game
> was replaced by this route.

## Setup
- **Host:** Outer Wilds **1.1.16.1372** from Steam (AppId **753640**), Unity **2019.4.39f1 Mono**, Echoes of the
  Eye installed, on Linux. The Windows `OuterWilds.exe` runs under **Proton 11.0-100** — this matters for every
  filesystem and window interaction below.
- **Guest:** Minecraft Java **26.3** with **Fabric Loader 0.19.5**, built with Loom against **JDK 25**
  (`/usr/lib/jvm/java-25-openjdk`; the system default `javac` can stay 21 because only the FFM shared-memory API
  the exporter uses needs 22+). Minecraft is **native Linux**, not Wine: the guest window is Wayland/SDL.
- **Host mod runtime:** OWML **2.16.3** via Outer Wilds Mod Manager **0.15.7**. Build with `net48` against NuGet
  OWML 2.16.3 + **publicized** `OuterWildsGameLibs` 1.1.16.1372; HarmonyX comes with OWML.
- **Guest profile:** a *copy* of a "Fabulously Optimized" Modrinth profile ("BlockCraft Passthrough"), so the
  user's own worlds and account are untouched.
- **Tooling that actually ran:** `xdotool` and `grim` for window handling and capture, Python + Pillow + numpy
  for frame analysis, and a mod-side command file inside the OWML mod (`dev_commands.txt` → `dev_log.txt`) as
  the test harness (see `techniques/driving-a-game-from-a-mod-side-command-file-lab-profile-wake.md`).
- **Single-player, offline.** Nothing leaves `127.0.0.1`.

## Route and why
In `techniques/choosing-a-mashup-route.md` terms this is **frame compositing** (picture transport) with a little
state exchange: both real games run, the guest's frame crosses through shared memory, and the host's camera pose,
ground columns and keys cross over a WebSocket. It is pattern 2 (passthrough) in `skills/mashup-mods/SKILL.md`, the
GTA V example's route (`games/gta-v/minecraft-passthrough.md`; code from `examples/minecraft-gta5-passthrough`).

The first plan was a **content port** (BlockCraft 1.0.0: Minecraft *styled* blocks and mobs rebuilt inside
OWML). It was dropped because the user wanted **real Minecraft** — its own world, its own simulation, its own
updates — not a lookalike. The moment the requirement is "the real game, running", passthrough is the only
route that keeps both games' own code alive.

Considered and set aside:
- **Rebuilding Minecraft in Unity** — the thing the content port already was, and it can never track Minecraft's
  own behaviour.
- **Host-drawn stand-in geometry** (what the BeamNG note does with its 7-box Steve): also a lookalike.
- **Running Minecraft under Wine** to make one window: rejected, the user owns the Linux build and wants it used.
- **Letting Minecraft own the camera:** the host must own the player and the camera, because the point is
  Minecraft appearing *inside Outer Wilds'* world. Minecraft's player is hidden and its camera is driven by the
  host. This is the ownership choice in `techniques/bridge-contracts-ownership-units-and-lifecycle.md`, and it is
  written down in `docs/CONTRACT.md` before the bridge code.

## How the game works (what we had to learn)
Engine facts specific to this route. The OW *internals* (camera, `VisibleToPlayer`, loop reset, profiles,
`OWRigidbody`) are in the sibling note `games/outer-wilds/portal-2-portal-gun-in-outer-wilds-1-1-16-owml-see-through-p.md`
and were relied on here; what follows is what passthrough adds.

- **Proton filesystem bridge:** a host mod can map the guest's POSIX shared memory by opening
  **`Z:\dev\shm\blockcraft-frame`** as an ordinary file (`FileStream`) and mapping it
  (`MemoryMappedFile.CreateFromFile`, a Win32 file mapping underneath). The guest creates the object as a file
  under `/dev/shm` (`java.lang.foreign` FFM in Java 22+); Proton's `Z:` drive makes it visible. This was probed
  before any bridge code was written, because if it did not work the whole transport design changed.
- **Renderer hooks:** the composite is drawn from `Camera.onPreCull` on the player `OWCamera`, using the same
  `UI/Default` shader the portal-gun note found. Two passes: a depth-tested quad over the placement surface
  writes stencil ref 61 with `_ColorMask 0`, then a near-plane screen quad (`nearClipPlane * 1.05`, the
  portal-gun example's trick) paints the guest texture only where stencil equals 61. `LessEqual` depth test, so
  OW terrain in front occludes the picture exactly as it occludes real geometry.
- **Scene gating:** passthrough must **not** start at mod load. It starts in the `SolarSystem` branch of
  `LoadManager.OnCompleteSceneLoad`, because before that the camera, player body and profiles do not exist. This
  is the same class of trap as gotcha 3 in the portal-gun note.
- **`OWML.Config.json` and `forceExe`:** OWML's validator rejects a mod whose config does not match the DLL.
  `forceExe: true` only changes how OWML's own launcher starts the game: the exe directly instead of
  `steam://rungameid/753640` (`OWML.Launcher/App.cs`). Here the game was started from Steam, with OWML already
  patched into `Assembly-CSharp.dll`, so it's unclear the setting matters for this route. Keep exactly one writer
  for that file (here, `tools/fix-owml-config.py`).
- **Minecraft's own readback returned black here** — the single most expensive thing learned. See gotcha 1. In
  short: `GpuTexture` -> `copyTextureToBuffer`, and even vanilla's own screenshot path, returned **black** while
  the exporter was also reading depth through that path; raw `glReadPixels` into a self-bound FBO works.
- **Minecraft camera override:** the guest applies the host pose through a `Camera` mixin. MC yaw `0` faces
  `+Z`; building the rotation is `rotationYXZ(pi - yaw)`, and after writing the rotation the mixin must set
  `matrixPropertiesDirty |= 3` or the change is not used.
- **Wayland focus:** the guest window is native Wayland, so `grim -l 0` cannot capture it and `xdotool
  windowactivate/windowfocus` do nothing on KDE Plasma/Wayland. Capture OW through the host mod's own `shot`
  command; to focus the Proton window, use a KWin D-Bus script matching `resourceClass ==
  "steam_app_753640"`. Outer Wilds **pauses on focus loss**, which silently freezes any test that depends on it.

## Build steps
The code ships with this note as `examples/minecraft-outerwilds-passthrough`, a sibling of the GTA V and
portal-gun examples. Layout: `mc/` (Fabric), `ow/src/` (OWML), `tools/` (Python), `docs/CONTRACT.md` as
`CONTRACT.md`. Both halves were built from that folder before publishing.
1. Guest: `cd mc; ./gradlew build`, then deploy the jar into the passthrough profile's `mods/`
   (`tools/install-guest.py` does this). Gradle needs **JDK 25**; `mc/gradle.properties` points at it via
   `org.gradle.java.home`.
2. Host: `cd ow/src; dotnet build -c Release`. Note that this writes **directly into the live OWML mod folder**,
   so a rebuild changes the installed mod — there is no separate deploy step, and no staging to get wrong.
3. Launch order matters less than it seems: the host retries the WebSocket every second while the guest is
   absent, so either can start first. Launch OW with `DISPLAY=:0 steam -applaunch 753640`
   (`tools/launch-ow.sh`, which runs OWML's launcher under Proton directly, did not start the game here).
4. Guest readiness gate: grep `client started` in the profile's `logs/latest.log` (about 2.5 minutes with 149
   mods), then wait ~20 s more before sending it anything, or the client thread is not ready.
5. Host readiness gate: the dev log must show `scene 'SolarSystem' loaded True` before the bridge exists.

## Verification
Oracle: the mod-side command file (host `dev_commands.txt` -> `dev_log.txt`) plus Python probes over the guest's
WebSocket, and `tools/oracle.py` for the axis work below.

**The pipeline works end to end.** `tools/pose-sweep.py` freezes the live host's bridge (dev command
`oracle on`), sends 5 different camera poses straight to the guest in Minecraft coordinates, and hashes the
exported colour layer, checking the seqlock on every read:

```
yaw0 pitch40     md5 dce80f15927c  nonzero 921600
yaw90 pitch40    md5 1d151f7204b3  nonzero 921600
yaw180 pitch40   md5 31437870119c  nonzero 921600
yaw270 pitch40   md5 42b3e1947a7d  nonzero 921600
move +30x        md5 98970920c462  nonzero 921600
VERDICT: 5 distinct frames from 5 poses - the camera override works.
```

`nonzero 921600` is every pixel of a 1280x720 RGBA layer, so no layer is blank. Host-side, `reader: reads 5225
torn 0 missed 0` across a session. A screenshot of the running game (`shots/slice1-live.png`) shows real
imagery (mean `(24,19,15)`, a sky-to-ground gradient) where the earlier broken run was all black.

**The guest's camera and the frame layout check out** with the landmark oracle in the next section, the part
with the most reusable value. The host's Outer Wilds -> Minecraft conversion is not verified (see there).

- **Not verified:** the host's pose conversion (`HostBridge.SendCamera`): every check above sent Minecraft-frame
  poses straight to the guest. Any surface the screen should really be pinned to (the slice places it by dev
  command); the guest depth layer, which is exported but not yet composited; multiple monitors and non-1280x720
  guest sizes; Minecraft worlds other than the one used; anything at all beyond the first slice's static picture.
- **Not verified on other hardware:** this was one machine (Linux/Wayland, AMD RX 6600, Mesa). The readback
  finding in gotcha 1 was reproduced there and nowhere else.

## The landmark oracle (reusable method)
`techniques/bridge-contracts-ownership-units-and-lifecycle.md` says to check the axis map and handedness against
the two games' *documented* facts and marks the GTA V line's `yaw = 180 - heading` **unchecked**, because no
source gives GTA V's axes. Source inspection has no method to offer when the documentation is silent. This is a
method that does not need it, and it caught three separate bugs that each produced a confident, wrong answer.

**Build a four-colour landmark cross in the guest's world and read back where each colour lands.**

- Four landmarks on the axes, each a colour the sky cannot produce: **north `-Z` magenta, south `+Z` black, east
  `+X` yellow, west `-X` orange.** Four colours identify a rotation *and* a mirror by themselves; two would only
  prove that something moved.
- Hold the guest camera at a known pose, read the exported frame, and compare each colour's centroid with the
  contract's prediction.
- **Look straight down** (`pitch 90`). The landmarks are 90 degrees apart around the camera, so a horizontal view
  can show at most two.

Result, camera at `(0,120,0)` looking straight down at a cross 3 blocks out and 4 down:

| landmark | world | expected in the raw buffer | measured centroid |
|---|---|---|---|
| magenta | `-Z` north | up the screen | (640, 30) |
| black | `+Z` south | down the screen | (640, 671) |
| yellow | `+X` east | left | (142, 360) |
| orange | `-X` west | right | (1120, 360) |

The four centroids sit on a square centred at (631, 350) against a frame centre of (640, 360). Two things decide
what this proves:
- **The pose went straight to the guest, in Minecraft terms.** `tools/oracle.py` sends `cam` messages with MC yaw
  0 and pitch 90; the host converts Outer Wilds poses in `HostBridge.SendCamera`, and it wasn't in the loop. So
  the run checks the guest's camera override and the exported frame, not the Outer Wilds -> Minecraft mapping.
- **The rows are bottom-up** (`glReadPixels`; contract flag 2), and the oracle reads row 0 as the top. A camera
  facing `+Z` and looking down has south at the top of the screen, so "north up" holds for the raw buffer, not
  for the screen. Flip the rows before judging a frame against the screen.

The contract's mapping, still to be checked through the host:

```
MC = (OW.x, OW.y, -OW.z)      # Z mirror
MC.yaw   = 180 - OW.yaw
MC.pitch = -OW.pitch          # OW positive pitch looks up, MC positive looks down
```

By Unity's conventions (euler `y` turns `+Z` toward `+X`, clockwise seen from above; positive euler `x` looks
down, which is why a top-down Unity camera is `(90, 0, 0)`) and Minecraft's (yaw 0 faces `+Z`, 90 faces `-X`;
positive pitch looks down), a Z mirror gives `MC.yaw = 180 + OW.yaw` and `MC.pitch = OW.pitch`. Both signs above
look inverted (`180 - heading` is the GTA V formula, for a heading that turns the other way); they agree only at
yaw 0 and 180 with level pitch. Check it in game: turn right in Outer Wilds and see which way the Minecraft
picture turns, or run the cross through the host.

Four rules make the difference between a verdict and a confident lie, and they generalise to any landmark
oracle:
1. **The probes hold the *rendered* colours, not the textures'.** Yellow concrete renders at about
   `(143,105,13)` in this scene rather than its texture's `(240,200,40)`. Texture-valued probes matched almost
   nothing and reported "no landmarks found" from a frame that clearly contained all four.
2. **A match must be near *and* clearly nearer than the runner-up**, or a dark scene makes every pixel "nearest
   black". See gotchas 2-4.
3. **Refuse to judge a flat frame.** A frame that is one colour contains no geometry and cannot settle
   anything — but the old classifier happily read 17430 "landmark" pixels out of a sky-only frame, because every
   pixel is *nearest* to something.
4. **Put the code under test in the loop.** A pose sent straight to the guest checks the guest; only a pose that
   goes through the host's conversion checks the mapping.

## Gotchas
1. **The exported frame is permanently black, and nothing in Minecraft's own readback agrees.** **Symptom:**
   every frame hashed identically; a "frozen" picture that never changed with the camera. **Cause:** on this
   stack `GpuTexture` -> `copyTextureToBuffer` returns zeros. Checked against ground truth: vanilla's own
   `Screenshot.takeScreenshot` on `mainRenderTarget` returned pure black (hash `9139525410424356864`) at every
   hook point, while a **raw FBO read of the same texture at the same moment returned 921600/921600 non-black
   pixels**. Minecraft's reader uses a cached `readFbo` and is unreliable here; the default framebuffer is also
   unreadable (Wayland/SDL surface). **Fix:** don't use the engine's readback. Bind **your own FBO** to
   `GlTexture.glId()` (`glFramebufferTexture2D`; for depth, `GL_DEPTH_ATTACHMENT` **and** `glReadBuffer(GL_NONE)`,
   since a depth-only FBO must have no colour attachment), check `GL_FRAMEBUFFER_COMPLETE`, and raw
   `glReadPixels` into a direct `ByteBuffer`. Also: capture **colour and depth synchronously** at the world hook
   and the overlay at the `render` TAIL. Two synchronous reads beat three fenced async ones, and dropping the
   encoder/buffer API entirely removed a whole class of timing bugs. (An earlier note in that session blamed
   `submit()` ordering; that was wrong and was superseded.) **Likely cause (not re-tested here):** gotcha 1 of
   `games/gta-v/minecraft-passthrough.md`, on the same Minecraft 26.3: a depth `copyTextureToBuffer` leaves the
   backend's cached read framebuffer with its read buffer at `GL_NONE`, so every later colour copy through it
   fails, vanilla's screenshot included. This exporter read depth that way every frame. The GTA V example restores
   the read buffer with one mixin (`GlCommandEncoderMixin`); a framebuffer of your own, as here, avoids it too.
2. **A landmark oracle confidently reports an inverted axis from a frame with no landmarks in it.**
   **Symptom:** a calm `south(+Z) is in the UPPER half ... PITCH SIGN IS INVERTED`, 217512 px of "match".
   **Cause:** the classifier picked the *nearest* probe colour with no absolute-distance limit and no separation
   from the runner-up, so a near-black frame made every pixel "nearest black"; the 217512 px were dark rock.
   **Fix:** require the match within a distance **and** the runner-up to be clearly farther (`MATCH_DIST = 30*30*3`,
   `MATCH_MARGIN = 1.6`), plus a `MIN_LANDMARK_PIXELS` floor so stray matches can't stand in for a landmark.
3. **The oracle never analysed most of the frame, and said "not visible" about a landmark that was there.**
   **Symptom:** `south not visible` while a direct count of the *same* buffer found 31776 south pixels.
   **Cause:** the loop ran `for i in range(0, w*h, 4)` and indexed `pixels[i]` as **bytes**. `w*h` counts
   *pixels*, so the walk covered only the first quarter of the RGBA buffer. **Fix:** `range(0, w*h*4, 4)`. The
   general lesson: when a diagnostic count and the analysis disagree, suspect the analysis' index arithmetic,
   not the frame.
4. **`setblock` silently refused the landmarks.** **Symptom:** the cross was never built and the oracle judged
   an empty frame. **Cause:** since 1.20.5 `setblock` fails on an occupied cell unless told `replace`, and the
   oracle used a bare `setblock`; wherever a landmark landed in solid ground the game answered "Could not set
   the block" and the oracle carried on. **Fix:** `replace` on every `setblock`, and **clear the arena first**.
   Read the command output — it was saying so all along.
5. **Ground level is a terrible place to put a landmark cross.** **Symptom:** the judged frame was a dark rock
   tunnel with sky at the bottom (mean `(61,52,48)`, 21 coarse colours) that no colour classifier could read.
   **Cause:** the guest camera ends up inside whatever terrain is there. **Fix:** build the cross in a cleared
   volume **high in the air** (y=116 here) with a laid floor, so only floor, four colours and sky are in view.
6. **`fill ... 122.0 ...` is rejected and the clear never happens.** **Symptom:** the camera stayed buried in
   terrain the arena was supposed to lift it out of. **Cause:** `CAM_Y + 2` with `CAM_Y = 120.0` produced a
   float; `fill` takes integers. **Fix:** keep every coordinate an `int` — the failure is easy to miss because
   the game answers "Invalid integer" and the next command still succeeds.
7. **A floor fill that filled a sliver instead of a floor.** **Symptom:** the camera looked at bare sky despite
   a `Successfully filled 25 block(s)`. **Cause:** the ground level was in the **x** slot
   (`fill 115 115 -12 12 115 12`). **Fix:** build corner arguments from named bounds, not inline arithmetic.
8. **Every host-side dev command wedges the game after the first one.** **Symptom:** the dev bridge stopped
   responding; the game looked fine. **Cause:** the WebSocket pump blocked. **Fix:** `Socket.Poll(50_000,
   SelectMode.SelectRead)` before reading, so an idle link costs nothing.
9. **The guest stops publishing when it loses focus, and the picture silently freezes.** **Symptom:** a stale
   frame that does not respond to any pose — easy to misdiagnose as a broken exporter. **Cause:** the
   `dynamic-fps` mod throttles a backgrounded Minecraft; OW pauses on focus loss, so a test that alt-tabs away
   sees a frozen frame. **Fix:** set `frame_rate_target` for the `invisible` and `unfocused` states in the
   profile's `config/dynamic_fps.json` (in **both** `config/` and `config/modpack_defaults/config/`), and keep
   the host focused. The oracle now **sends its own pose before checking publishing**, because it freezes the
   host and the host's pose timeout is 2 s — the old check always saw an idle guest.
10. **A `pin` message is worth having in the guest for its own sake.** **Symptom:** every probe that wanted a
    fixed camera had to race the live host for the 2 s pose timeout. **Cause:** the host overwrites the pose
    every frame. **Fix:** a guest dev message `{"t":"pin","p":[x,y,z,yaw,pitch,fov]}` that holds a pose locally
    and bypasses the timeout; an empty `p` clears it. It is how the readback fix was proved, and it stays
    useful.
11. **OWML logs and marshalling from a network thread.** **Symptom:** nested exceptions from logging off the
    main thread. **Fix:** queue log lines from the link thread and drain them in `Update` on the main thread.
    Repeat link failures use a quiet path, or a disconnected guest floods the log.
12. **A long-running diagnostic is indistinguishable from spam.** The bridge tick, pre-cull and poll counters
    were bounded (`<= 20`, `<= 200`) so they self-terminated, but one was still printing hundreds of lines into
    the dev log of the *current* session and made real output hard to find. **Fix:** delete startup diagnostics
    once the bug they found is fixed; a bounded counter is not the same as a temporary one.

## Assets
None at this stage — the slice composites the guest's own rendered frame, so no art was generated.

## Cost and time
Multiple sessions. The dominant cost was gotcha 1 (the frame readback), which masqueraded as a dozen different
bugs before ground truth (`Screenshot` vs raw `glReadPixels` on the same texture at the same instant) settled it.

## Open questions
- Pin the screen to a real surface (a ship panel, a Nomai wall) instead of a dev-placed quad.
- Consume the exported **depth** layer for per-pixel compositing, so guest geometry the host does not know about
  is occluded correctly.
- Whether vanilla's readback works on this stack once nothing leaves the read buffer at `GL_NONE` (gotcha 1's
  likely cause). If it does, the failure isn't specific to Mesa/AMD.
- The host's pose conversion: run the landmark cross through `HostBridge.SendCamera` and settle the yaw and pitch
  signs (The landmark oracle).
