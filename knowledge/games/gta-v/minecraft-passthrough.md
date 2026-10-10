---
kind: game
title: "Minecraft inside GTA V (passthrough mod)"
game: "Grand Theft Auto V"
games_also: ["Minecraft Java Edition"]
game_version: "GTA V Legacy (Steam, game build 3889, story mode) + ScriptHookV 3889.0 + ReShade 6.8.0; Minecraft Java 26.3 + Fabric"
platform: windows
engine: rage
route: passthrough
tools: ["ScriptHookV + ASI loader", "ReShade 6.8 add-on API", "Fabric Loader + Fabric API (Loom, JDK 25)", "MSVC", "Python (director, recorder)", "um win / um video"]
anti_cheat: "BattlEye guards GTA Online only: story mode, launched with BattlEye off (-nobattleye), never online"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["@rehan_shei"]
date: 2026-09-30
links: ["https://github.com/rehan-remade/universal-modder/tree/main/examples/minecraft-gta5-passthrough"]
tags: [mashup, passthrough, shared-memory, websocket, depth-compositing, reshade-addon, scripthookv, fabric, mixin, reprojection, camera-sync, director, prism-launcher, amd]
---

# Minecraft inside GTA V (passthrough mod)

> Real Minecraft Java 26.3 runs next to GTA V story mode and is drawn into GTA's frame: Steve walks, builds,
> flies an elytra over Los Santos, and his TNT, arrows and fireworks become GTA explosions and bullets, while
> Minecraft mobs fight the LAPD. GTA's camera drives Minecraft's. GTA's ground becomes invisible collision in
> Minecraft, and Minecraft's colour + depth are depth-tested against GTA's depth buffer. It runs in the real
> game (recorded for a demo video). Code: `examples/minecraft-gta5-passthrough`.

## Setup
- GTA V **Legacy** from Steam (appid 271590, game build 3889), story mode. ScriptHookV 3889.0 + its ASI
  loader. ReShade **6.8.0 with add-on support**, loaded through the ASI loader as `ReShade64.asi` (see
  Gotchas).
- Minecraft Java **26.3** with Fabric Loader + Fabric API, built with Loom on **JDK 25**. It runs from a
  separate launcher profile with its own game dir, so the player's own worlds and options are never touched.
- MSVC (Visual Studio Build Tools) for the ASI; Windows Python for the host test tools and the video
  director.
- One Windows PC with an NVIDIA GPU (agent working from WSL2). Running both games at once was fine.

## Route and why
**Passthrough:** two unmodified games run side by side, and a mod in each exchanges state. Alternatives
considered:
- **Reimplementing Minecraft inside GTA:** far too much work, and it would never feel like real Minecraft.
- **FiveM (the GTA multiplayer platform):** it needs a Cfx.re key and a server, and it may block ReShade
  add-ons.
- **Rendering Minecraft into a flat overlay:** it can't be occluded by GTA's buildings, and it doesn't
  sell the effect.

The design:
```
GTA V story mode                                   Minecraft 26.3 + Fabric
  MCPassthrough.asi (ScriptHookV script) -- WebSocket 127.0.0.1:25599 -->  camera / ground / keys / slot / commands
                                         <--------------------------------  explosions, arrow/firework hits, mob events
  ReShade add-on compositor  <-- named shared memory "Local\MCPassthroughFrame" --  world RGBA + depth, hand/HUD overlay
  MCPassthrough.fx: depth test vs GTA's (reversed-Z) depth, overlay on top
```

## How the game works (what we had to learn)
- **Coordinates:** 1 GTA metre = 1 block.
  - Position: GTA (x, y, z) → Minecraft (x, z + yOffset, −y).
  - Angles: Minecraft yaw = 180 − GTA heading; pitch = −pitch.
  - `yOffset` is picked so the ground under the player lands exactly on a block boundary. There's a re-level
    key, and an automatic re-level when nothing has been built nearby.
- **World sync:**
  - GTA's ground near the player is probed each tick (a floor-finding probe also works indoors) and sent as
    **barrier blocks**, so Steve collides with GTA's world.
  - Minecraft block changes go back as **invisible GTA collision props**, so peds and cars stop at your
    builds.
- **Frames:** each Minecraft frame exports colour + depth for the world and a separate overlay (hand + HUD)
  into shared memory. The compositor converts Minecraft's depth onto GTA's view axis and depth-tests it
  against GTA's buffer. So a lamppost correctly hides part of a Minecraft house, and the house hides the car
  behind it.
- **Latency:** Minecraft always renders slightly behind GTA's camera. The compositor re-projects:
  1. rotation first: each GTA pixel's view ray is rotated into the pose Minecraft rendered with;
  2. then full 6-DoF: ray-marched depth re-projection, so strafing and third-person swings don't make blocks
     swim or Steve drop out.
- **Lighting:** Minecraft is relit from a blurred copy of GTA's light, so a night street tints the blocks.
- **Interaction instead of guns:**
  - Steve holding GTA guns looked wrong (GTA's aim cam, hands and animations don't fit a blocky model).
  - What works is Minecraft weapons with GTA effects. The plugin traces Minecraft arrows and crossbow
    fireworks through GTA's world:
    - a firework hit → a GTA rocket explosion;
    - an arrow hit on a ped or car → a GTA bullet;
    - a sword swing ragdolls peds and launches cars.
- **Mobs vs police:**
  - Minecraft mobs and GTA peds exchange positions and hits (`peds` / `mobs` / `mobhit` / `mobdmg`
    messages).
  - GTA cops appear in Minecraft as invisible proxy entities that mobs can target, and mob hits become GTA
    damage.
  - A director op builds a police barricade that keeps the fight in frame.
- **The Nether:** walking through a lit portal turns the surrounding ground into the Nether, nether mobs pour
  out, GTA's sky goes red while its clock races to midnight, and GTA people and cars on lava or fire burn.
- **Director:** repeatable video takes are JSON shot lists run by the plugin. Ops include teleport, walk,
  face, view, look, time, weather, spawn peds/cars, explosions, `police {stars}`, pose-lag tuning and more.
  A recorder takes the GTA window plus game-only audio, and a cut script titles it in the Minecraft font.

## Build steps
1. **Minecraft side:** build the Fabric mod (`./gradlew build`, JDK 25) and put the jar next to Fabric API
   in the passthrough profile's `mods/`.
2. **GTA side:**
   1. Run `fetch_deps.sh` to get the ScriptHookV SDK, the ReShade add-on headers and `ReShade.fxh`, then
      `build.bat` (MSVC) builds the `.asi` + add-on.
   2. `install.sh` copies it into the GTA folder (and `--remove` undoes it).
   3. Install ReShade with add-on support **via the ASI loader**.
3. **Run:**
   1. Launch GTA with BattlEye off (`-nobattleye` in `args.txt`, or the launcher toggle) and enter
      **Story Mode**.
   2. Start Minecraft from the passthrough profile; it opens a void creative world by itself.
   3. Press F7 in GTA to toggle the passthrough.
4. **Without GTA:** `host/fakehost.py` flies Minecraft's camera and composites over a synthetic scene, and
   `gta/tests/fakegta.cpp` is a D3D11 app with a reversed-Z depth buffer, ReShade and the compositor, i.e.
   the whole GTA half except the natives.

## Verification
- **Alignment and occlusion, before GTA was even installed:**
  - `fakehost.py` renders known geometry and checks Minecraft's blocks land on it.
  - `fakegta.cpp` runs the real compositor and shader against a synthetic reversed-Z depth buffer, with a
    fast-shake mode and outlines of Minecraft's blocks drawn host-side.
- **Camera sync in the real game:** a measurement scene with a gold wall (Minecraft-only) against the
  skyline (GTA-only). The offset between them, frame by frame, found the one-frame pose lead and verified
  the fix.
- **Real game:** every feature was checked in story mode with the director's scripted shots, recorded, and
  reviewed frame by frame.
- **Not verified:** other GTA builds (Enhanced), ultrawide aspect ratios other than the ones used, Intel GPUs,
  and on AMD the in-game features one by one (see the second-PC run below).
- **Reproduced on a second PC (2026-10-09, Claude Code (Opus 5.5) with a different human):**
  - Setup: Windows 11 Pro 26200, **AMD Radeon RX 9060 XT**, GTA V Legacy `GTA5.exe` 1.0.3889.0 (Steam buildid
    24129523), ScriptHookV 3889.0.1158.13, ReShade 6.8.0.2155 add-on build, Minecraft 26.3 in **Prism
    Launcher** (Fabric Loader 0.19.5, Fabric API 0.161.0+26.3), portable Temurin JDK 25.0.4.1, VS 2022 Build
    Tools, Gradle 9.7.1 / Loom 1.18.3. The example code built unchanged on the first try.
  - `fakehost.py` (20 s orbit): 2354 frames over shared memory, one host frame behind; blocks land on the
    synthetic ground and occlude / are occluded by the host-only pillar correctly. So Minecraft's GL readback
    path works on AMD.
  - Real game: logs show the ASI loader loading both ASIs, ScriptHookV starting the script, ReShade compiling
    `MCPassthrough.fx` and the add-on reporting "connected to Minecraft's frame export", and Minecraft logging
    "host connected". The human played in story mode and reported it working; a window capture
    (`um win shot`) showed Minecraft's hand and hotbar composited over GTA. Not checked feature by feature
    (TNT, projectiles, mobs vs police, elytra, Nether), and no recording was made.

## Gotchas
1. **Colour readback returns garbage after a depth readback (Minecraft 26.3).**
   - **Cause:** the GL backend's depth `copyTextureToBuffer` sets the read FBO's read buffer to `GL_NONE`
     and never restores it.
   - **Fix:** a mixin on the GL command encoder restores the read buffer after the copy.
2. **Setup commands on join match nobody (`@a` is empty).**
   - **Cause:** Fabric's `ServerPlayConnectionEvents.JOIN` fires before the player is in the player list.
   - **Fix:** run them 10 ticks later.
3. **`fabric-installer -launcher microsoft_store` fails.**
   - **Cause:** the file `launcher_profiles_microsoft_store.json` doesn't exist.
   - **Fix:** add the profile to `launcher_profiles.json` by hand (back it up first). Give it its own
     `gameDir` so the player's worlds and options are untouched.
4. **ScriptHookV's download fails from scripts.**
   - **Cause:** dev-c.com rejects clients without browser headers.
   - **Fix:** send a browser User-Agent/Accept (the example's `fetch_deps.sh` does).
5. **The ReShade proxy DLL never loads in GTA.**
   - **Cause:** GTA loads the system `dxgi.dll` ahead of a proxy in its folder.
   - **Fix:** load ReShade through the ASI loader instead.
6. **Flicker, then a crash, when toggling the effect.**
   - **Cause:** the effect was toggled from inside the begin-effects callback.
   - **Fix:** gate it with a uniform (`McActive`) and never toggle techniques from that callback.
7. **Squashed HUD and skewed angles.**
   - **Cause:** Minecraft's window followed the monitor size (32:9), so the frame was squeezed into GTA's
     16:9.
   - **Fix:** size Minecraft's window to GTA's real backbuffer, and restore (un-maximize) it before
     resizing.
8. **Blocks lead the GTA picture by one frame, and explosion shake can't be stopped.**
   - **Cause:** the script reads GTA's camera for the frame being prepared, not the one on screen. GTA's
     explosion shake isn't reported by `IS_GAMEPLAY_CAM_SHAKING`, so `STOP_GAMEPLAY_CAM_SHAKING` can't
     cancel it.
   - **Fix:** re-project to the previous pose (a pose-lag of 1 frame in the compositor). Measure it with
     the gold-wall scene.
9. **The chase cam judders.**
   - **Cause:** timing used `GetTickCount` (16 ms steps) or Python `sleep` on Windows.
   - **Fix:** time everything with Minecraft's `System.nanoTime`, which is the same clock as
     `QueryPerformanceCounter` on Windows.
10. **Elytra glides are cancelled; a "dive" is really a free fall.**
    - **Cause:** with `noPhysics`, Minecraft's `onGround` never updates and can stick at true, so the server
      cancels every glide.
    - **Fix:** force `setOnGround(false)` in flight mode.
11. **A full-screen view of Steve's face.**
    - **Cause:** GTA pulls its camera in against walls, which puts Minecraft's camera inside Steve's head.
    - **Fix:** hide Steve when the camera is that close.
12. **After a restart, Steve glides into the void.**
    - **Cause:** Minecraft was closed mid-flight.
    - **Fix:** strip the elytra on join; auto-respawn on death with `keep_inventory`.
13. **Proxy entities become visible.**
    - **Cause:** Minecraft 26.3 resets an entity's Invisible flag on its first network sync unless it has an
      effect.
    - **Fix:** give proxies a hidden, infinite INVISIBILITY effect.
14. **Mobs ignore the proxies.**
    - **Cause:** invulnerable entities can never be targeted, and target goals test invisibility and line of
      sight.
    - **Fix:** leave proxies vulnerable but cancel their damage in a `hurtServer` mixin. Give target goals no
      invisibility or line-of-sight test.
15. **GTA's cinematic idle camera cuts in mid-take.**
    - **Cause:** it starts after about 30 s without input.
    - **Fix:** call `INVALIDATE_IDLE_CAM` every frame.
16. **The last Minecraft frame stays on screen over GTA's map.**
    - **Cause:** GTA's pause menu stops ScriptHookV scripts, so nothing clears the overlay.
    - **Fix used:** cut around it in the edit. Detecting the pause from outside the script and clearing the
      overlay would be the real fix; not built yet.
    - 2026-10-09, second PC: reproduced; a capture of GTA's pause-menu map still showed Minecraft's hand and
      hotbar on top.
17. **Hidden frozen "double" peds still take cop bullets.** `SetEntityVisible(false)` doesn't make them
    immune. Keep invisible stand-ins out of the line of fire.
18. **Walking off the Maze Bank Tower slides instead of dropping.** The tower's sides are sloped glass.
    **Fix:** take off with Space.
19. **Story Mode needs two clicks.** On the landing page the first click only highlights it.
20. **Don't auto-click GTA's landing page while the human is at the keyboard.**
    - **What happened:** the agent's click script focused GTA while the user was typing in another app.
      Their keystrokes landed on GTA's landing page, and it showed "ALERT: attempting to access GTA Online
      servers with an altered version".
    - ScriptHookV blocked it, and no session started. It was still a close call for the account.
    - **Fix:** auto-click only when the human is away (check `um win drive --proc GTA5 idle`). Otherwise ask
      them to click Story Mode. Keep BattlEye off so Online can't start at all.
21. **Guns held by Steve look bad.**
    - **Cause:** GTA's aim camera, hands and animations don't fit a blocky model.
    - **Fix:** use Minecraft weapons with GTA-side effects (see above).
22. **Prism Launcher: a hand-made instance folder is never listed (2026-10-09).**
    - **Cause:** Prism rescans `instances/` when the folder changes. If the instance folder (or its `mods/`)
      appears before `instance.cfg` is written, the rescan finds no instance and doesn't look again.
      `--launch "<name>"` then fails with "resolves to nothing" in Prism's log.
    - **Fix:** write `instance.cfg` and `mmc-pack.json` first, or rename the folder afterwards to trigger a
      rescan. Use a folder name without spaces as the instance ID (`--launch gta-passthrough`). Fabric adds two
      components to `mmc-pack.json`, after `net.minecraft` 26.3: `net.fabricmc.intermediary` 26.3 and
      `net.fabricmc.fabric-loader` 0.19.5.
      Prism's per-instance `JavaPath` can point at a portable JDK 25.
23. **PowerShell 5.1 writes a BOM.** `Set-Content -Encoding utf8` / `ConvertTo-Json | Set-Content` puts a BOM
    in `mmc-pack.json`. Write it with `[IO.File]::WriteAllText(..., UTF8Encoding($false))`.
24. **Prism can hang on "logging in with Microsoft account" during a scripted launch.** The token refresh
    needs the human (Accounts > Refresh, or sign in again). The agent must not handle the sign-in.
25. **The example's shell scripts fail in WSL with CRLF line endings.** A Windows checkout (or the plugin
    cache) can give `gradle.sh`, `gta/*.sh` and `mc/gradlew` CRLF endings, which WSL bash can't run. Convert
    them to LF (`sed -i 's/\r$//'`) and pin it with `.gitattributes` (`*.sh text eol=lf` and
    `gradlew text eol=lf`: `mc/gradlew` has no `.sh` extension).
26. **No WSL.** `fetch_deps.sh` runs as-is in Git Bash (curl + unzip); `build.bat` and `mc\gradlew.bat` run
    natively. `install.sh` needs `wslpath`: under Git Bash use `cygpath -u` and `/c/...` instead of
    `/mnt/c/...`, and point `BUILD` at `gta/build`. With WSL, a `PASSTHROUGH_WIN_DIR` inside the project
    (for example its `tools\`) keeps the build mirrors, JDK and venv in one place.
27. **Piping a script into `wsl.exe bash -s` stops after the first `cmd.exe` call.** `cmd.exe` (gradlew) reads
    the rest of the script from the shared stdin. Run the script from a file with `< /dev/null`.
28. **winget installs the C++ Build Tools unattended:**
    `winget install Microsoft.VisualStudio.2022.BuildTools --override "--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"`
    (one UAC prompt). `build.bat` then finds vcvars through vswhere.

## Assets
None generated. Steve uses the classic skin while a host is attached. Titles in the demo use the Minecraft
font, with the video cut by the repo's director/recorder pipeline and `um video`.

## Cost and time
About two days of agent sessions (Claude Code, Opus 5.5) with one human directing and doing the clicks
the rules reserve for humans. The fake host and fake GTA let most of the work happen before the 125 GB
game finished installing.

## Open questions
- **Enhanced edition:** GTA V Enhanced (DX12) needs a different ReShade/compositor path.
- **Multiplayer Minecraft:** it works in principle, since it's just another client. It's untested.
- **Latency:** Minecraft could render at the predicted pose, so re-projection is only a fallback.
- **Check these with a real install before relying on the example.** See also
  `knowledge/techniques/frame-compositing-depth-and-pose-sync.md`.
  - **Pose lag:** the gotcha above says a lag of 1 frame, but the compositor defaults to 0 (a code comment
    says 0 measured best) and only the director's `poselag` op changes it. Record the value used per capture.
  - **`install.sh --remove`** deletes `ReShade.ini` unconditionally, including one the user had before
    installing (install itself preserves it). 2026-10-09, second PC: a local patch (not in the example yet)
    writes a marker file when install creates `ReShade.ini`, and `--remove` deletes `ReShade.ini` only when
    the marker is there.
  - **Save helper:** it copies its two saves into every discovered profile.
  - **Cleanup scope:** detach forgets barrier tracking without removing the barriers; fighter cleanup removes
    every matching hostile or proxy in the Overworld, and hot-block cleanup can remove player-placed fire or
    lava; any invisible villager counts as a proxy.
  - **Frame reader:** it validates the magic but not every header size/capacity or the capture timestamps,
    and checks the slot sequence after the GPU upload, which can't undo a partly overwritten image.
  - **`ws_test.cpp`** passes when any received message contains `explosion`; it doesn't assert camera, depth,
    ground columns or reconnects.
