# Minecraft x GTA V: a passthrough mod

Real Minecraft Java 26.3 running next to GTA V (story mode) and drawn into it. GTA's camera drives Minecraft's,
GTA's ground becomes invisible collision in Minecraft, Minecraft's picture (colour + depth, plus the hand/HUD) is
composited into GTA's frame against GTA's depth buffer, and what happens in Minecraft happens in GTA too.

- **Build** with Minecraft blocks in Los Santos. Placed blocks become invisible GTA props, so people and cars stop
  at your walls.
- **TNT and creepers** blow up in both games: each Minecraft explosion is also a GTA explosion.
- **Minecraft weapons with GTA effects.** Crossbow fireworks burst as GTA rockets where they hit, arrows that hit
  a person or a car land as GTA bullets, a sword swing sends people flying and shoves cars, and an ender pearl
  moves GTA's player.
- **Elytra flight.** Minecraft's physics fly Steve and GTA follows with a chase camera. Once flight is armed,
  Space or a fall from anything tall takes off, the mouse steers, fireworks boost, and touching down lands you
  back on foot.
- **Mobs vs police.** Minecraft's hostile mobs hunt GTA's people, GTA's police shoot back, and damage crosses over
  both ways.
- **The Nether.** Walk through a lit nether portal and the ground around it turns into the Nether, nether mobs
  pour out, GTA's sky goes red while the clock races to midnight, and people and cars on lava or fire burn.

It was built and tested in GTA V Legacy (Steam, game build 3889) with ScriptHookV 3889.0 and ReShade 6.8.0 in
September 2026. This folder is that code with its paths made configurable. A few shot configs from the demo
videos are included.

## How it works

```
GTA V (story mode)                                    Minecraft 26.3 + Fabric (mc/)
  MCPassthrough.asi (gta/src)                           dev.rehan.passthrough
    script.cpp  -- WebSocket 127.0.0.1:25599 ------->     HostLink: cam / ground / key / slot / cmd
                <------------------------------------     explosion events
    compositor.cpp (ReShade add-on)  <-- shared memory --  FrameExporter: world RGBA + depth, overlay RGBA
    MCPassthrough.fx: depth test + overlay                 "Local\MCPassthroughFrame"
```

Coordinates: 1 GTA metre = 1 block; GTA (x, y, z) -> Minecraft (x, z + yOffset, -y); Minecraft yaw = 180 - heading,
pitch = -pitch. The script picks yOffset so the ground where the player stands lands on a whole block (F8 re-levels).

- **Every GTA frame**, the ScriptHookV script (`gta/src/script.cpp`) sends the camera GTA rendered with and the
  player's feet and heading (`cam`). Minecraft renders from that camera with no sky, fog or clouds, and Steve
  stands where GTA's player (hidden) stands.
- **Ground.** The script probes GTA's ground in the columns around the player (40 blocks out, 160 probes a
  frame) and sends them as `ground`. The mod fills them with barrier blocks, so blocks, mobs and items rest on
  GTA's world. Each block you place or break comes back as a GTA prop (at most 400 of them; GTA crashes at
  around 1500 script objects).
- **Frames.** The mod copies Minecraft's world colour and depth just before the hand is drawn, then the hand,
  HUD and screens as a separate overlay, into a named shared-memory mapping (three slots, asynchronous GPU
  readback). The ReShade add-on (`compositor.cpp`) uploads the newest frame into textures. `MCPassthrough.fx`
  then draws Minecraft wherever it is nearer than GTA's depth buffer and puts the overlay on top. Before that,
  the effect re-projects Minecraft's frame from the pose it was rendered with to GTA's current camera,
  which hides the link's latency. It also relights the frame from GTA's blurred picture, gives it GTA's colour
  grade and haze, and softens the edges.
- **Events back.** Explosions, projectiles in flight (traced through GTA's world), sword swings, ender pearls,
  mobs and the Nether's hot blocks go to the plugin, which acts them out in GTA.
- **Input.** GTA has the focus, so the plugin forwards the mouse buttons, the wheel and the number keys to
  Minecraft and keeps GTA from acting on them.

## Files

| path | what it is |
|---|---|
| `mc/` | the Fabric mod (Java 25, Loom): `HostLink` (WebSocket server), `FrameExporter` + `SharedMemory` (the frames), `PlayerSync`, `WorldBridge` (barriers, block sync, explosions, projectiles), `MobWar`, `Nether`, and the mixins |
| `gta/src/script.cpp` | the ScriptHookV script: camera, ground, input, explosions, director ops, flight, mobs vs police, the Nether |
| `gta/src/compositor.cpp` | the ReShade add-on: uploads Minecraft's frame and sets the effect's uniforms |
| `gta/src/natives.h` | the GTA natives the script calls, by hash |
| `gta/src/ws.cpp` | a small WebSocket client |
| `gta/shaders/MCPassthrough.fx` | the ReShade effect: depth test, re-projection, relighting, haze, edges, glow, overlay |
| `gta/fetch_deps.sh`, `build.sh`, `build.bat`, `install.sh` | fetch ScriptHookV and ReShade, build with MSVC, install into the game folder |
| `gta/tests/` | `fakegta.cpp` (a GTA stand-in) and `ws_test.cpp` (the WebSocket client against the running mod) |
| `host/` | tests without GTA (`fakehost.py`, `place_test.py`, `tnt_test.py`), `mcframe.py` (reads the shared memory), `cmd.py` (runs Minecraft commands) |
| `video/` | the director (scripted shots) and the recording and cutting scripts, plus shot configs |
| `gradle.sh` | runs Gradle on Windows from WSL |

## Requirements

- **Windows 10/11 with WSL.** The scripts are bash (run them in WSL) and batch.
- **Minecraft Java Edition 26.3**, Fabric Loader 0.19.5 or newer, and Fabric API 0.161.0+26.3.
- **GTA V Legacy** on Steam, story mode. It must be the Legacy edition (`GTA5.exe`); the Enhanced edition isn't
  supported here.
- **ScriptHookV** and its ASI loader (`dinput8.dll`), by Alexander Blade. ScriptHookV only runs on the game
  builds it supports, so after a GTA update, wait for a new ScriptHookV and run `fetch_deps.sh` again.
- **ReShade 6.8.0 with add-on support.** Both ReShade and ScriptHookV are downloaded by `gta/fetch_deps.sh`.
- **MSVC**: Visual Studio 2022 or newer with the C++ desktop tools (x64).
- **JDK 25**, for example Temurin 25. `gradle.sh` wants a Windows one; `./gradlew` on its own takes any.
- **Python 3.12 for the host tools.**
  - Windows Python with `websockets` runs the director and the host tools; `fakehost.py` also needs `numpy`
    and `Pillow`.
  - WSL Python with `Pillow` and a Linux `ffmpeg` cut the videos.
  - Recording needs a Windows ffmpeg with gfxcapture: `um win setup` downloads one.

Paths come from environment variables, with these defaults:

| variable | default | used by |
|---|---|---|
| `PASSTHROUGH_WIN_DIR` | `C:\dev\passthrough` | everything: the Windows working folder with the `mc\` and `gta\` build mirrors, `gradle-home\`, `jdk25\`, `pyenv\`, `mcgame\`, `takes\`, `shots\`, `gta_save\` |
| `PASSTHROUGH_JDK` | `<PASSTHROUGH_WIN_DIR>\jdk25` | `gradle.sh` |
| `PASSTHROUGH_MC_DIR` | `<PASSTHROUGH_WIN_DIR>\mcgame` | `gradle.sh install`: the game dir of your Minecraft launcher profile |
| `GTA_DIR` | GTA V Legacy (Steam app 271590), found in your Steam libraries | `gta/install.sh` |
| `RUNTIME`, `BUILD` | `gta/third_party/runtime`, `<PASSTHROUGH_WIN_DIR>\gta\build` | `gta/install.sh` |
| `VCVARS` | the newest Visual Studio with C++ tools (vswhere) | `gta/build.bat`, `gta/tests/build_fakegta.bat` |
| `PASSTHROUGH_PY` | `<PASSTHROUGH_WIN_DIR>\pyenv\Scripts\python.exe` | `video/take.py`, `video/go.py`: the Windows Python the director runs with |
| `UM_FFMPEG_WIN` | um's download, or `ffmpeg` on PATH | `video/record.py`, `video/director.py scout` |
| `MC_CLIENT_JAR` | the client jar Loom cached when `mc/` was built | `video/titles.py` (the Minecraft font) |
| `GTA_SAVE_DIR` | `<PASSTHROUGH_WIN_DIR>\gta_save` | `video/go.py save` |

## Build, install, run

1. **The mod.** From WSL, `./gradle.sh build` mirrors `mc/` to `<PASSTHROUGH_WIN_DIR>\mc` and builds it there
   with the Windows JDK. Anywhere with JDK 25, `cd mc && ./gradlew build` builds the same jar, at
   `mc/build/libs/passthrough-0.1.0.jar`.
2. **A Minecraft launcher profile with its own game dir.** The mod changes options: no clouds, no view bobbing,
   a 120 fps cap, and it keeps running unfocused. It also creates a void creative world called `passthrough` and
   opens it by itself. So give it a game dir apart from your own worlds.
   - Install Fabric Loader for 26.3 with the Fabric installer.
   - In the launcher, add an installation with the `fabric-loader-0.19.5-26.3` version and a game directory of
     its own, for example `C:\dev\passthrough\mcgame`. If the installer can't add the profile itself (it failed
     with the Microsoft Store launcher), add it by hand.
   - Put Fabric API in `<game dir>\mods`. `./gradle.sh install` builds the mod and copies it there too
     (`PASSTHROUGH_MC_DIR`).

   For development, `./gradle.sh runClient` starts a dev client instead (game dir `mc\run` in the mirror, offline
   account).
3. **The GTA side**, from WSL:
   ```bash
   gta/fetch_deps.sh   # ScriptHookV SDK + ReShade headers into gta/third_party/, the runtime DLLs into third_party/runtime/
   gta/build.sh        # mirrors gta/ to <PASSTHROUGH_WIN_DIR>\gta and builds build\MCPassthrough.asi with MSVC
   gta/install.sh      # copies it all into the GTA V folder
   ```
   `install.sh` adds `ScriptHookV.dll`, `dinput8.dll` (the ASI loader), `MCPassthrough.asi`, `args.txt`
   (`-nobattleye -noBE`) and ReShade. ReShade goes in as `ReShade64.asi`, so the ASI loader loads it: GTA
   loads the system `dxgi.dll` ahead of a proxy in its folder, so the usual `dxgi.dll` install never runs. It
   also writes `ReShade.ini` (if there is none), `ReShadePreset.ini`, and the effect in
   `reshade-shaders\Shaders\`.
   - It stops rather than replaces a `dinput8.dll`, `ReShade64.asi` or `args.txt` that isn't its own
     (`FORCE=1` overrides).
   - `install.sh --remove` deletes exactly the files it adds.
   - `build.bat` also works from a Windows prompt, in a copy of `gta/` with `third_party/` fetched.
4. **GTA settings.** The demo ran GTA windowed at 1920x1080, with "Pause game on focus loss" off, depth of field
   off, and post FX lowered. Minecraft's window is resized to GTA's picture, up to 1080p worth of pixels. Depth
   of field and heavy post effects blur GTA's picture but not Minecraft's.
5. **Run.**
   - Start Minecraft with that profile. Leave its window open: it renders slowly when minimized.
   - Start GTA V from Steam with BattlEye off. The `-nobattleye` in `args.txt` does it, or the BattlEye toggle
     in the Rockstar Games Launcher settings. That also keeps GTA Online out.
   - Pick Story Mode on the landing page yourself.
   - In story mode the plugin connects ("Minecraft passthrough connected"), sizes Minecraft's window to GTA's
     picture and starts sending the ground. The two can start in either order, because the plugin keeps
     reconnecting.

## Controls

| key | what it does |
|---|---|
| F7 | turns the passthrough off and on |
| F8 | re-levels Minecraft's ground to where you stand (it also happens by itself when nothing is built nearby) |
| left mouse | Minecraft's attack: break blocks, swing the sword |
| right mouse | Minecraft's use: place blocks, light TNT, shoot, throw pearls, boost with fireworks |
| mouse wheel, 1-9 | Minecraft's hotbar |
| Tab | gun mode (experimental): GTA's carbine rifle, minigun and RPG in Steve's hands, then back to Minecraft |
| Space | while flight is armed: take off with the elytra |

Everything else (walking, driving, the camera, the view key) is GTA's own, and Minecraft follows. GTA's own
attack, aim, weapon wheel and weapon keys are disabled while Minecraft has the mouse.

The mod sets up the hotbar when you join:

1. ender pearls
2. a diamond sword
3. a crossbow (multishot, quick charge)
4. a bow (power, infinity)
5. TNT
6. flint and steel
7. creeper eggs
8. grass blocks
9. fireworks

Your off hand holds explosive fireworks for the crossbow, and you get 64 arrows.

- **Elytra flight.** Flight is armed from the director: `python video\director.py op armdrive "{\"user\":1}"`.
  Then Space, or a fall from anything tall, opens the elytra.
- **The Nether.** Get obsidian (`python host\cmd.py "give @a minecraft:obsidian 64"`), build a portal, light it
  and walk through it. The director's `portal` step builds and lights one 10 m in front of you
  (`video/nether_cfg.json`).
- **Mobs vs police.** Hatch creepers, or spawn waves with `spawnmobs`. The director's `cops` op brings a
  police squad; `video/mobwar_live.py` keeps both coming while you play.

## Tests without GTA

- **`host/fakehost.py`** runs with Windows Python while Minecraft runs:
  `python host\fakehost.py [seconds] [outdir] [fp|tp]`. It flies Minecraft's camera round a few test blocks
  and gives it a flat ground. It then composites the exported frames over a synthetic scene rendered for the
  same pose, a checkerboard and a red pillar that only the "host" has. The PNGs it writes (default
  `<PASSTHROUGH_WIN_DIR>\fakehost_out`) show whether alignment and occlusion are right. `tp` tests third
  person.
- **`gta/tests/fakegta.cpp`** is the whole GTA half except GTA's natives. It is a D3D11 window with a
  reversed-Z depth buffer and GTA's camera conventions, with the compositor and WebSocket client compiled in.
  - Build it with `gta/build.sh tests` (`tests\fakegta.exe`).
  - To run it, put ReShade next to it as `dxgi.dll`. For a normal program the folder's `dxgi.dll` does load.
    Copy `third_party/runtime/ReShade64.dll`, and add a `ReShade.ini`, `ReShadePreset.ini` and the three
    shader files the way `install.sh` writes them.
  - `fakegta.exe [seconds] [1]` orbits the test blocks (the `1` swings the camera fast to show latency).
  - While it runs, `python video\director.py shoot video\fake_steps.json` (or `fake_cfg.json`) drives its
    stand-in player like the real plugin.
- **`gta/tests/ws_test.cpp`** checks the plugin's WebSocket client against the running mod: the handshake, a
  60 Hz camera, ground columns, a TNT command, and the explosion event coming back.
- **`host/tnt_test.py`, `host/place_test.py`** are the same kind of check from Python.

## Director and video pipeline

- **The director.** `video/director.py` (Windows Python, because Minecraft's link is on Windows' 127.0.0.1)
  scripts shots through Minecraft's link.
  - GTA ops (`{"t":"gta","op":...}`) are relayed by the mod to the plugin: teleport, walk, face, view, look,
    time, weather, ped (with a scenario or a looped animation), car, explode, drive/armdrive/flylook (flight),
    cops/mobfit (mobs vs police), and more (see `handle_director` in `script.cpp`).
  - Minecraft input (hotbar, clicks) and commands go to the mod.
  - Shot lists are JSON: `elytra_cfg.json`, `mobwar_cfg.json`, `nether_cfg.json`, and the fakegta dry runs.
    Positions are GTA coordinates, or relative to an origin and heading.
  - `director.py scout [x y z]` takes screenshots in four directions.
  - `director.py op <op> '{json}'` sends one op and prints GTA's state.
- **Takes.** From WSL, `python3 video/take.py <name> video/mobwar_cfg.json` records GTA's window while the
  director runs the shot list.
  - Audio comes from GTA and Minecraft separately, each from its own process (the repo's
    `um/ps1/ProcLoopback`).
  - It writes `<PASSTHROUGH_WIN_DIR>\takes\<name>.*` with an event log.
- **Cuts.** `video/cut.py <name> out.mp4 [head] [length] [title]` and `video/cut_segments.py` cut a take to
  1080p with one-line titles in Minecraft's font. The font sheet is Mojang's, so `titles.py` reads it from
  your own Minecraft jar.
- **Helpers.**
  - `video/go.py` waits for GTA and the link, installs a save, backing the old one up, and scouts.
  - `video/backup_rec.py` records until a `STOP` file appears.
  - `video/mobwar_live.py` keeps mob waves and police coming while you play.

## Safety

- **Story mode only; never GTA Online.** BattlEye protects GTA Online. This runs with BattlEye off, which also
  keeps Online from starting, and ScriptHookV closes the game if it goes online anyway. Don't try to get a
  modded game near Online.
- **Never automate clicks on GTA's landing page while someone is at the keyboard.** During development a script
  focused GTA and clicked Story Mode while the user was typing in another window. Their keystrokes landed in
  GTA, which showed "attempting to access GTA Online servers with an altered version". ScriptHookV blocked it,
  but don't risk it. Pick Story Mode by hand. `go.py` never clicks.
- **The game folder.** `install.sh` lists what it adds, won't replace another mod's loader or ReShade, and
  `--remove` takes it all out again.
- **Saves.** `go.py save` keeps your save files as `.bak` before it replaces them.
- **Processes.** Scripts stop GTA by its exact PID, never by name pattern.
- **The link.** It listens on 127.0.0.1:25599 only, with no token, so any program on the machine can send it
  commands. Close Minecraft when you're done.
- **Redistribution.** ScriptHookV and ReShade are fetched from their own sites and aren't redistributed here,
  and neither is anything from Minecraft or GTA.

## Credits

- [ScriptHookV](https://www.dev-c.com/gtav/scripthookv/) and its ASI loader by Alexander Blade.
- [ReShade](https://reshade.me) and its add-on API by crosire, with `ReShade.fxh` from
  [crosire/reshade-shaders](https://github.com/crosire/reshade-shaders).
- [Fabric](https://fabricmc.net): Fabric Loader, Fabric API and Loom.
- The GTA V native names and hashes in `natives.h` come from alloc8or's
  [native DB](https://github.com/alloc8or/gta5-nativedb-data) and the NativeDB authors.
- [Java-WebSocket](https://github.com/TooTallNate/Java-WebSocket) by TooTallNate is bundled in the mod for the
  link.
- **Inspiration:** chasm's Minecraft-in-Skyrim passthrough, and TobynJacobs' Minecraft-in-Elden-Ring.
- Written with Claude Code.
- Minecraft belongs to Mojang Studios and Microsoft, and GTA V to Rockstar Games and Take-Two. This is a fan
  project.

## Lessons

The non-obvious things this took (Minecraft 26.3's depth readback bug, why ReShade has to load as an ASI,
camera timing, flight, mobs vs police, the landing-page incident) are written up in
[`../../knowledge/games/gta-v/minecraft-passthrough.md`](../../knowledge/games/gta-v/minecraft-passthrough.md).
