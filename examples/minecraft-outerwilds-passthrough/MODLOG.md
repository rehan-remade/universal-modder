# MODLOG — Minecraft inside Outer Wilds

Working folder for the mashup. Route: **Pattern 2 passthrough** (frame compositing + state
exchange). See `MODDING_PLAN.md` for the plan and `docs/CONTRACT.md` for the cross-process contract.

## 2026-10-19 — session 1 (recon, route pick, transport probe)

### Recon
- Outer Wilds (Steam 753640) on Arch, **Windows build under Proton 11.0-100** (prefix
  `compatdata/753640`). OWML 2.16.3 already installed; game `Managed/Assembly-CSharp.dll` already
  patched; mods live at `~/.local/share/OuterWildsModManager/OWML/Mods/` (native Linux path, exposed
  to the game as `Z:\...`).
- **BlockCraft 1.0.0 already exists and has run in the game** (`SvenTheRedPanda.BlockCraft`, source
  in `~/Downloads/blockcraft-outer-wilds-1.0.0/`, 763 lines C#). It is a Pattern 1 content port:
  Minecraft-style cubes placed/broken in the real Outer Wilds world. Verified load from
  `OWML/Logs/latest.txt` (2026-10-19 16:18): `BlockCraft loaded`, `block tool added to the loop`,
  `block tool ready: equip key Digit6, block size 1.00 m`.
- Minecraft Java is installed natively: Modrinth App 0.21.9 (flatpak), profile
  **"Fabulously Optimized" = Minecraft 26.3 + Fabric Loader 0.19.5** (48 mods). Zulu 17/21/25 JREs
  bundled; no JDK.
- Toolchain: `dotnet` 6.0.136 only (no SDK 8), `mono`/`mcs`/`csc`, Proton 9/10/11/Experimental.

### Decisions (Sven)
- Wants **real Minecraft gameplay** inside Outer Wilds, Outer Wilds as host, owns Java Edition.
- **Replace** BlockCraft 1.0.0 with the live passthrough.
- Minecraft stays **native Linux** (not Wine).
- Bridge uses a **copy of the Fabulously Optimized profile**.

### Route change vs the earlier plan
`~/Downloads/blockcraft-outer-wilds-1.0.0/MODDING_PLAN.md` rejected the live passthrough as "the
flakiest option by far" because the toolkit's examples are "Windows D3D shared memory end to end"
and the machine has "two Proton prefixes". That held only while both sides were assumed to be in
Proton prefixes. It does not hold:
- The **host's** compositing is a Unity `Camera.onPreCull` + RenderTexture + full-screen quad inside
  an OWML C# mod — no D3D, no ReShade, no swapchain hook, no native DLL. (The verified portal-gun
  example already does exactly this.)
- The **guest** is a native Linux JVM, so cross-process sharing is a POSIX mapping the Wine process
  reads through `Z:\dev\shm\...` — the same trick the CrossOver MHW/Elden Ring bridges used.

### Probes run
1. **Host C# toolchain:** `dotnet build src -c Release` in the BlockCraft source **succeeded**
   (net48, restored OWML 2.16.3 + OuterWildsGameLibs 1.1.16.1372, dropped `BlockCraft.dll` into the
   Linux mods folder). Host side is buildable on this box.
2. **Cross-boundary shared memory:** a native Linux writer created `/dev/shm/blockcraft-probe2`
   (1 MiB) and wrote a counter. A C# assembly run **under Proton 11's `wine`** with
   `WINEPREFIX=.../compatdata/753640/pfx` opened `Z:\dev\shm\blockcraft-probe2` and mapped it.
   Wine reports the correct file size (verified with `wine cmd /c dir`).
   - **Result: PASS — the transport works.** `tools/probe/probe2.out`: the Wine-side C# reader
     opened `Z:\dev\shm\blockcraft-probe2`, read `magic=0x42434B31` (raw read *and* mapped view) and
     followed the **live, changing** counter (416 → 583, values exactly `counter * 0.5`). So a native
     Linux JVM and a Wine/Proton process share a POSIX mapping through `Z:\dev\shm\...` with no
     Windows named objects, no pagefile mapping and no native DLL.
   - The first probe's "wrong magic" was a bug in the probe (it read at an offset past a 4096-byte
     object and hit stale bytes), not a Wine limitation. Wine reports correct sizes and content.
   - Files back this up: `/dev/shm/blockcraft-probe2` reads back `31 4b 43 42` = `0x42434B31` on the
     Linux side; the Wine reader saw the same.
3. `um backup create` of the Outer Wilds save folder: `ow-saves/20261019-121352.zip` (16 files).

### Next
- Confirm probe 2 (Wine reads the guest's live data).
- Get a JDK 25 (none installed; Modrinth ships JREs only) for the Fabric project.
- First slice per the plan: one Minecraft cube composited into Outer Wilds at a known spot,
  depth-tested and occluded, with the pose logged on both sides.

## 2026-10-19 — session 2 (guest mod builds; host reader/link in place)

### Toolchain
- `jdk25-openjdk 25.0.4.1.u1-1` installed (Sven ran pacman; the assistant cannot pass a sudo prompt).
  Arch's `extra` has it; the system default `javac` stays 21. Gradle is pointed at JDK 25 with
  `org.gradle.java.home=/usr/lib/jvm/java-25-openjdk` in `mc/gradle.properties`, because:
  - Minecraft 26.3 and its Fabric API are compiled for **Java 25** (class file 69), so javac 21
    cannot read them; and
  - `java.lang.foreign` (used by `SharedMemory` for `shm_open`/`ftruncate`/`mmap`) is only stable
    from **Java 22** up.
- The Modrinth-bundled Zulu 25 is a **JRE only** (no `javac`), so it could not build the mod.

### Guest (Fabric) — `mc/`
Forked from `examples/minecraft-gta5-passthrough/mc` and trimmed to what the contract needs.
**`./gradlew build` is green** (`blockcraft-0.1.0.jar`, 157 KB, Fabric Loom 1.18.4).

Files:
- `SharedMemory.java` — POSIX `shm_open`+`ftruncate`+`mmap` via the FFM API, replacing the example's
  Win32 `CreateFileMapping`. Maps `/dev/shm/blockcraft-frame`.
- `FrameExporter.java` — the GTA V example's three-layer export (world colour, world depth, overlay),
  3 slots, seqlock, magic renamed `"BCFF"` (`0x46464342`). Layout header matches `docs/CONTRACT.md`.
- `HostState.java` — the host's camera pose, Minecraft coordinates, 2 s timeout → detach.
- `HostLink.java` — WebSocket server on 127.0.0.1:25599 (`-Dblockcraft.port`). Handles
  `cam`, `ground`, `clear`, `cmd`; sends `hello` with the shm name and PID. Trimmed from the example's
  larger protocol (no GTA/Nether/MobWar cases).
- `WorldBridge.java` — host ground as `Blocks.BARRIER`, tracked so a reset only removes ours.
- `BlockCraftClient.java` — opens/creates the flat void world `blockcraft`, keeps the picture clean
  (no clouds/bob/effect FOV/vsync, 120 fps cap), auto-respawn.
- `ClientInput.java` — the handful of host keys (use/attack/pick/inventory/drop/swap), slot, scroll, hud.
- `mixin/CameraMixin.java`, `mixin/GameRendererMixin.java`, `mixin/KeyMappingAccessor.java` — host camera
  over the player's, no sky while attached, world/overlay frame split.

### Host (OWML C#) — `ow/`
- `FrameReader.cs` (maps `Z:\dev\shm\blockcraft-frame`, seqlock read) and `HostLink.cs` (WebSocket
  client) were written and **compile** against the real OW libs (`dotnet build`, net48, 0 errors).
- Compositor and the rest of `BlockCraft.cs` are still the original 1.0.0 content-port code; wiring
  them to `FrameReader` is the next step.

### Next
- Wire the host compositor (portal-gun `UI/Default` stencil + full-screen quad) to `FrameReader`.
- Send `cam`/`ground`/`clear` from the host every frame; add the dev command-file bridge.
- First slice: guest picture on a depth-tested surface in Timber Hearth, then the alignment oracle
  (gold-wall equivalent) to fix the unverified axes/yaw/pitch signs.

## 2026-10-19 — session 3 (host runtime + compositor; both sides build)

### Host (OWML C#) — now a passthrough, not a content port
All of `ow/src` builds (`dotnet build -c Release`, net48, 0 warnings).
New files:
- `Compositor.cs` — the guest's picture on a **depth-tested surface in the world**, two `UI/Default`
  stencil passes (ref 61): a `LessEqual`-depth-tested quad writes the ref where visible (so OW terrain
  occludes it), then a screen-aligned quad just past the near plane paints the guest texture where the
  ref is set. Reads the mapping at `Camera.onPreCull`, uploads the colour layer to a `Texture2D`.
  `PlaceInFront` / `SetSize` for testing. Depth layer is read but not yet consumed.
- `HostBridge.cs` — every frame sends `cam` (Unity pose → Minecraft coordinates per the contract:
  `MC=(x, y, -z)`, `yaw = 180 - owYaw`, `pitch = -owPitch`) and `ground` (vertical raycast per column,
  radius 12, every 0.5 s) → guest barriers. Drains the guest's `hello`/`bye`.
- `DevBridge.cs` — command-file oracle (`dev.enabled` gate), commands: `wait`, `waitfor
  {solarsystem,title,control,guest,frames}`, `place [d]`, `at x y z [nx ny nz]`, `size w h`, `pose`/`dump`,
  `shot <name>`, `clearground`, `cmd <text>`, `fov`.
- `BlockCraftMod.cs` — `ModFolder` set from the manifest; `StartPassthrough()` creates the link,
  compositor, bridge and dev bridge on SolarSystem load; disposes the link on destroy.
- `HostLink.cs` — added `ReceiveTimeout = 5000` so a partial frame can't wedge the socket thread.
- `manifest.json` — name/version → "BlockCraft – Minecraft inside Outer Wilds" 2.0.0.

The old 1.0.0 content-port files (`BlockTool.cs`, `BlockHud.cs`, `BlockTextures.cs`) are still present
and still load: the block tool stays as the "build blocks in Outer Wilds" feature alongside the
passthrough. Whether to keep it is Sven's call.

### Guest (Fabric)
`./gradlew build` green; `blockcraft-0.1.0.jar` (157 KB) has all classes + the bundled WebSocket dep.

### Next
- Deploy the host DLL, launch Outer Wilds + the Fabric client, and run the first slice:
  `waitfor solarsystem` → `place 6` → `dump` → `shot slice1`.
- Then the alignment oracle: put the guest camera at a known spot, screenshot both sides, and fix the
  `CONTRACT.md` axis/yaw/pitch signs against what is actually seen.

## 2026-10-19 — session 4 (deploy; transport proven with the real code; OWML launch is the blocker)

### Transport proven with the actual code paths
Ran the JVM's `SharedMemory` approach (JDK 25, FFM `shm_open`/`ftruncate`/`mmap`) as a standalone
program and had a C# reader run **under Proton 11's `wine`** open `Z:\dev\shm\blockcraft-ffmtest`:
- Wine read `magic=0x46464342` ("BCFF") and `version=1` written by the Java side.
- With both running, Wine **followed a live counter** the JVM was incrementing
  (`counter[0]=1022, 1024, 1026, 1028, 1030`).

So the exact magic, the exact FFM calls and the exact `Z:\dev\shm\...` access are all confirmed, not
just the earlier hand-rolled probe. Probe files: `/tmp/opencode/ffm/`.

### Deployed
- Host: `build/BlockCraft.dll` (47 KB, the 2.0.0 passthrough) → the live mods folder, with
  `manifest.json` renamed to "BlockCraft – Minecraft inside Outer Wilds" 2.0.0. The 1.0.0 DLL and
  manifest are saved as `backup-BlockCraft-1.0.0.dll` / `backup-manifest-1.0.0.json`.
- Guest: `blockcraft-0.1.0.jar` → a **copy** of the Fabulously Optimized profile named
  "BlockCraft Passthrough", registered in the Modrinth App's `app.db` (`instances`, `instance_links`
  as `unmanaged`, `instance_launch_overrides`, `instance_content_sets`) so the launcher lists it.
  Rebuilt against `fabric-api 0.162.0+26.3`, the version that profile actually ships.
- Tools written: `tools/slice1.sh` (dev-bridge driver + spectacle screenshots), `tools/install-mod.py`,
  `tools/fix-owml-config.py`, `tools/launch-ow.sh`, `tools/launch-mc.py`.

### The blocker is OWML's launcher, not the mod
`OWML.Launcher.exe` cannot start the game when run directly under Proton:
- Without `-consolePort` it dies in `SocketListener.Init()`;
- with it, `App.Run()` → `LocateGamePath()` → `UWPGameFinder.FindGamePath()` dereferences a null: it
  reads the registry key
  `Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages`,
  which does not exist under Wine. `OWML.Config.json`'s `gamePath` is **ignored** — the path is
  re-detected every launch.
- This happens regardless of the mod, so it is an OWML-on-Linux limitation. Sven launches the game
  himself (he has 1344 minutes on this install; the previous modded session's log proves it works).

### Gotchas learned the hard way
- **Never `pkill -f <pattern>`** where the pattern also appears in your own command line: it killed the
  agent's own shell three times. Kill by PID from a file.
- Running `OWML.Launcher.exe` **empties `Mods/`** (its patcher step recreates the folder). The mod had
  to be reinstalled from `build/` afterwards — `tools/install-mod.py` does it now.
- Writing `OWML.Config.json` with backslash paths from a shell mangles them (`Z:\home\...` became
  `Z:\home...` interpreted as escapes, once even `S://...`). `tools/fix-owml-config.py` writes it with
  an explicit escape and is the only way to touch it.
- Proton's bare `files/bin/wine` is not enough to run the game (exit 53); use the `proton run` script
  with `STEAM_COMPAT_DATA_PATH` set, which also surfaces real errors that bare `wine` swallows.

### Restored state
- `OWML.Config.json`: `gamePath`/`owmlPath` are correct `Z:` paths, `forceExe` true.
- Mod reinstalled with `dev.enabled` present, so `dev_commands.txt` will be polled once the game runs.
- Outer Wilds saves backed up: `ow-saves/20261019-123519.tar.gz` (25 files).

### Next
- Sven starts the game. Then: `tools/slice1.sh waitfor solarsystem`, `place 6`, `dump`,
  `tools/slice1.sh shot slice1`.
- Start the guest via `tools/launch-mc.py` (or the Modrinth App's "BlockCraft Passthrough"), then check
  the host log for `guest hello` and the first `frames` counter.

## 2026-10-19 — session 5 (guest RUNS; OWML config root-caused)

**The guest mod now loads and its bridge answers, for the first time.** Everything below was found by
running it, not by reading code.

### The guest never loaded because the launcher dropped Fabric's loader from the classpath
`tools/launch-mc.py` built the `-cp` list from the version JSON's `libraries`, keeping only entries
with a pre-resolved `downloads.artifact`. Modrinth's launcher metadata lists **8 libraries as bare Maven
coordinates** (`name: "group:artifact:version"` + a `url`, `include_in_classpath: true`, no artifact):

```
org.ow2.asm:asm:9.10.1            net.fabricmc:sponge-mixin:0.17.4+mixin.0.8.7
org.ow2.asm:asm-analysis:9.10.1   net.fabricmc:intermediary:26.3
org.ow2.asm:asm-commons:9.10.1    net.fabricmc:fabric-loader:0.19.5
org.ow2.asm:asm-tree:9.10.1
org.ow2.asm:asm-util:9.10.1
```

Those are exactly Fabric's loader stack and its ASM dependency, so all 8 were silently skipped and
java died with `Could not find or load main class net.fabricmc.loader.impl.launch.knot.KnotClient`.
`library_path()` now resolves the coordinate to `meta/libraries/<group path>/<artifact>/<version>/`
and honours `include_in_classpath`. **Second fault, same function:** the Minecraft game jar is not a
library at all - it comes from `downloads.client` and lives at `<version>/<version>.jar`. Without it
Fabric aborts with *"Minecraft game provider couldn't locate the game!"*.

Both are now on the classpath; `--print` shows `fabric-loader-0.19.5.jar` and `26.3-0.19.5.jar`.
A copy of the built jar also has to be **in the profile's `mods/`**: `install-guest.py` does that and
checks the copy against the build, and `--list` reports `STALE` if it drifts. (An earlier session had a
stale jar in the profile, which is a silent failure: Fabric simply does not load the mod.)

### Proof the guest is alive
```
[13:00:42] [Render thread/INFO]: blockcraft loaded
[13:00:54] [WebSocketSelector-84/INFO]: host link listening on 127.0.0.1:25599
```
and a raw upgrade from outside the JVM:
```
HTTP/1.1 101 Web Socket Protocol Handshake
Sec-WebSocket-Accept: +7sj8GVntiv6jzYay9HFUmEXSts=
Server: TooTallNate Java-WebSocket
```
Fabric lists it among 149 mods as `- blockcraft 0.1.0` with its nested
`\-- org_java-websocket_java-websocket 1.6.0` resolved. No mixin errors, no crash report.
The `401 Failed to fetch user properties` is the offline account and is harmless.

### The guest runs, opens the world, and exports real frames - verified
After the classpath and window-size fixes the whole guest pipeline was exercised on this machine:

```
[13:13:52] blockcraft loaded
[13:14:03] host link listening on 127.0.0.1:25599
[13:16:06] client started; opening the passthrough world
[13:16:06] opening world blockcraft
[13:17:34] System chat: Replaced 1 slot(s) on Passthrough with [Diamond Pickaxe]   <- the SETUP commands ran
```

The world-open gate was the long-standing blocker. It used to require
`minecraft.gui.screen() instanceof TitleScreen`, and in a 149-mod profile the title is wrapped or
replaced by main-menu mods, so the condition never became true: the guest sat on the menu and exported
nothing. It now opens from **`ClientLifecycleEvents.CLIENT_STARTED`**, with a relaxed tick fallback that
only needs "no level and no player".

`tools/probe-guest.py` (and `tools/probe-frame.py`) drive the link without Outer Wilds, because the
guest only exports while a host is sending `cam` (`HostState` times out after 2 s - so with no host there
is nothing in `/dev/shm`, which is correct, not a fault):

```
guest said: {"t":"hello","v":1,"shm":"blockcraft-frame","pid":3982289}
```

Streaming poses created `/dev/shm/blockcraft-frame` **after 6 poses**, at exactly the contracted size
(`4096 + 99532800*3 = 298602496` bytes). Header read straight from the guest:

```
magic=0x46464342 version=1 hbytes=4096 slots=3
stride=99532800 max=3840x2160 publish=885 latestSlot=2 pid=3982289
 slot 2: 1280x720 fov=70.0 flags=7 cam=(0.50,66.00,0.50) yaw=23.3 pitch=-5.0 fp=1
```

The camera values are the ones the probe sent, so the pose path works. Reading the newest slot *while*
poses flow (the only meaningful way - a read after the stream stops sees a detached guest):

```
pose 5: slot 0 frame 1207 1280x720 flags=7 nonblack=300/300 (seq 806->806)
sent 330 poses; best non-black coverage 300/300; torn reads 0
```

Full pixel coverage, **zero torn reads** across 330 frames: the seqlock is sound. `flags=7` is
depth-in-[0,1] + rows-bottom-up + reversed-Z, as the contract says.

### The window was not 1280x720 (second launcher fault)
`--width`/`--height` sit behind a launcher rule
(`features: {has_custom_resolution: true, is_quick_play_realms: null}`). The rule check compared the
feature dict with `!=`, and `null` means "this feature is off", so `False != None` silently dropped the
arguments and the window came up at the profile's `options.txt` size. `rules_allow` now treats a rule's
`null` as "absent". Verified: `--width 1280 --height 720` are in the live process's command line.

### Guest link hardening (found by probing it)
`HostLink.onOpen` sent `hello` unguarded, so a client that connected and immediately dropped (a port
probe) threw inside the callback; `onError` then printed a full stack trace per connection. Both are now
guarded and log one line, which keeps `latest.log` readable at 149 mods.

### The OWML config was broken three ways (Sven's "game path is not valid")
1. **`Z:` must not be stored.** `OWML.Common.dll`'s `OwmlConfig.get_GamePath` *prepends* it:
   `if (WineChecker.IsUsingWine()) return "Z:" + gamePath;`. `OWML.DefaultConfig.json` ships
   `"C:/Program Files (x86)/Steam/..."` - forward slashes, no drive. My session-4 write of
   `Z:\home\...` made OWML build `Z:Z:\home\...`.
2. **`~/.steam/steamapps/...` does not resolve.** `~/.steam` is a real directory; only `~/.steam/steam`
   symlinks to `~/.local/share/Steam`. The working path is
   `~/.local/share/Steam/steamapps/common/Outer Wilds/`.
3. **A stray `OWML.Config.json`** (4 bytes, the literal text `null`) was left in the game folder by a
   failed run - the launcher writes its config to its *working directory*. Removed, backed up.

`Managed/` does not exist at the game root in this install; the game is the **unspaced** layout
(`OuterWilds.exe` + `OuterWilds_Data/`), and OWML looks in `OuterWilds_Data/Managed/`, where it has
already installed `OWML.ModLoader.dll`, `OWML.ModHelper.dll` and friends, and replaced
`Assembly-CSharp.dll` (original preserved as `.bak`). So mod injection is complete.

### Launching Outer Wilds on this machine
Steam launches it through `SteamLinuxRuntime_4` (sniper) + **`Proton - Experimental`**, via a
`legacycompat/iscriptevaluator.exe` step - not Proton 11.0, which is what my script assumed. Sven
launches the game himself.

### Screenshots: use Spectacle, not grim
The desktop is **KDE Plasma on Wayland (`kwin_wayland`)**. `grim` needs wlroots' screencopy protocol and
fails with *"compositor doesn't support the screen capture protocol"*. `spectacle` is installed and
works: `spectacle --background --nonotify --fullscreen --output <file>` (or `--activewindow`).
`tools/slice1.sh shot <name>` now does that, with the flags spelled out - `-o` only writes a file in
background mode and Qt does not reliably accept combined short flags.

### Gotchas learned the hard way
- **Never `pkill -f <pattern>`** where the pattern also appears in your own command line: it killed the
  agent's own shell three times. Kill by PID from a file.
- Running `OWML.Launcher.exe` **empties `Mods/`** (its patcher step recreates the folder). The mod had
  to be reinstalled from `build/` afterwards - `tools/install-mod.py` does it now.
- Writing `OWML.Config.json` by hand mangles backslash paths; only `tools/fix-owml-config.py` touches it.
- Proton's bare `files/bin/wine` is not enough to run the game (exit 53); use the `proton run` script
  with `STEAM_COMPAT_DATA_PATH` set, which also surfaces real errors that bare `wine` swallows.
- `pgrep -af <pattern>` dumps entire command lines, and a Minecraft `-cp` is ~10 KB per line. Use
  `ps -eo pid,etimes,args | grep` and print only the fields wanted.
- Repeated backgrounded `launch-mc.py` runs leave **one live Minecraft per launch**; kill the older
  PIDs before testing, or two guests race for port 25599.

### Next
- Restart the guest with the **current** jar and check the host side: OWML log for `guest hello: shm
  ..., pid ...` and the `frames` counter climbing.
- Then the alignment oracle: guest camera at a known spot, screenshot both sides, fix the CONTRACT's
  axis/yaw/pitch signs.

### Status at the end of this session
- **Guest: proven on this machine.** Loads, opens the world, link answers, `hello` carries the shm name
  and pid, `cam` poses drive the camera, frames land in `/dev/shm/blockcraft-frame` with the contracted
  geometry, live pixels and no torn reads.
- **Host: builds and is deployed, not yet run against a live guest.** The remaining first-slice step is
  the host reading that buffer and compositing it onto a surface in Outer Wilds.
- Outer Wilds itself is launched by Sven (Steam -> sniper runtime + Proton Experimental); the OWML
  config is now correct, and the game's `Assembly-CSharp.dll` is already patched by OWML.

### The guest renders for real, on this GPU
Worth recording, because "does the guest actually draw?" was open until now:
```
[13:15:25] Using graphics backend OpenGL, using drivers: 4.6 (Core Profile) Mesa 26.2.5
[13:15:25] Using graphics device: AMD Radeon RX 6600 (radeonsi, navi23, ACO, DRM 3.64)
[13:15:26] Created window using SDL video driver: wayland
```
3 `/dev/dri` file descriptors open, a live `Render thread`, and the exported colour layer sampled at
`nonblack=300/300`. So the frame data is Minecraft's actual picture.

**The guest window is invisible to `xdotool`** - it is a native Wayland window (`SDL video driver:
wayland`), and `xdotool` speaks X11 only. That is why it never appeared in the window list and why a
full-desktop capture showed no game region. It is *not* a failure to create a window. Consequence for
tooling: anything that finds or drives the guest by X11 window (xdotool, `--activewindow` screenshots of
it) will not see it. Use full-screen captures, or run the guest under XWayland.

### The guest only draws while a host is attached (by design)
`HostState.TIMEOUT_NANOS = 2s`, and `FrameExporter.captureWorld` returns early when the pose is null.
Measured with no host connected: `publish counter 2692 -> 2692` over 6 s (delta 0). So an idle guest is
**not** a fault, and a read of the buffer without a host attached will look empty or stale. Read it while
streaming poses - that is what `tools/probe-frame.py` exists for.

### Shaders are ON in the profile - a real hazard for compositing
`config/iris.properties` has `enableShaders=true` and `shaderPack=BetterVoxels v1.8.zip`. Iris rewrites
the render pipeline, so it can change depth-buffer semantics and disturb the world/overlay split that
`GameRendererMixin` captures at `render3dHud`. The mixin still applies (no errors, and frames export with
`flags=7`, near 0.05, far 2048), so it is not broken - but when the host half is tested, **test with
shaders off as well**, and turn shaders off if the composite looks wrong. `enableShaders` is the switch.

### Host startup is scene-gated, not title-screen-gated
`BlockCraftMod.Start` only calls `StartPassthrough()` from the SolarSystem branch of
`OnCompleteSceneLoad`. So `BlockCraft loaded` proves the mod is in; `passthrough up: link on
127.0.0.1:25599` only appears after **loading a save**. Expecting the bridge on the title screen would
look like a silent failure. `docs/SLICE1-CHECKLIST.md` has the full expected log order and how to read
each field of `tools/slice1.sh dump`.



## Session: ring bug fixed, host "dead Update" myth debunked

### Guest: the two-of-three-slots-empty bug — SOLVED
Symptom: only shm slot 0 ever carried pixels; slots 1 and 2 read back zero on the host.

Ruled out by experiment, in this order:
- `CommandEncoder.submit()` missing — added it, no change. (submit() was in the built jar and called.)
- copy timing / reading a buffer before its own copy lands — tried counting all three copy
  completions before publishing, no change.
- ring/slot counter drift — slot is derived from the ring index, structurally cannot drift.

What actually located it: a control copy inside `publish` while publishing slot 1:
  ctlA: ring0's colour buffer -> slot 1 region -> 255  (destination offsets are fine)
  ctlB: THIS capture's colour buffer -> slot 0 region -> 0  (source buffer is empty)
So `copyTextureToBuffer` was only ever filling the FIRST of several capture buffer sets.

Fix: replace the 3-entry ring with a SINGLE capture buffer (`FrameExporter.capture`), with
`Capture.busy` throttling the export to the GPU's pace. Slots still rotate (`nextSlot`) so the
host never reads what is being written.
Result: all three slots non-zero, publish steady at 60 fps, gframes consecutive, seq in lockstep.

### Host: `updateRuns=2` was a red herring — nothing was ever dead
`ReportStateOnce` prints during the first frames of a scene load, so `updateRuns=2` just meant
"2 polls had happened when the line was written". It did NOT mean Update() stopped.
Heartbeats added to each drive path (poll/precull in DevBridge, compositor precull, bridge tick)
proved all of them run every frame at frame=2900+:
  poll # -> 200, precull # -> 200, compositor precull -> 20, bridge tick -> 20  (capped logs)
The host was alive throughout; earlier "freeze" readings were misread.

Changes kept anyway, because they are genuinely more robust:
- DevBridge now has its own `DontDestroyOnLoad` GameObject (was on OWML's own object).
- HostBridge + DevBridge subscribe to `Camera.onPreCull` in `Start` (as Compositor does), with
  `-=` before `+=` so a second subscription cannot double-tick.
- Both unsubscribe in `OnDestroy` — `Camera.onPreCull` is static and not cleared between scenes.

### Verified end to end this session
- `reader: reads 514 torn 0 missed 0` — seqlock holds under load.
- Host reads rotate across slots (`slot 1` observed), not just slot 0.
- `link: connected True sent 1570 recv 1 errors 0`.
- Full contract descriptor parses correctly from all three slots: 1280x720, consecutive gframes,
  pose + fov=70 + flags=7 written by the host.
- The picture renders stably on the screen surface with no flicker (confirmed visually by the user).

### Still open
- Alignment oracle: is the picture oriented correctly (not mirrored / upside-down)?
- The screen is a free-floating quad at a fixed world pose (`place 6`), not yet attached to a
  real surface, so it "floats" past as the player moves. That is expected for slice 1.
- Remove the one-off heartbeat/trace instrumentation once the alignment oracle passes.

## Session: the oracle's false results — a throttled guest, not a camera bug

### What happened
Ran the first alignment oracle. Every test returned a **byte-identical** colour layer
(`md5 d52a6d21e1c2`) no matter the pose: four headings held 2 s each, then four positions
including y=100 (above the world) and y=-30 (below it) — all identical.

That is impossible for a real 3D render, so it looked like the guest ignored every pose it was sent.
It did not. The guest was **not rendering at all**.

### Root cause: dynamic-fps freezes a backgrounded Minecraft
`config/dynamic_fps.json` shipped by the modpack had:

    "invisible": {"run_garbage_collector": true}          # no frame_rate_target -> render stops

The Minecraft window sits behind Outer Wilds, so it is "invisible" to the compositor and the mod
stops the render loop. The guest still *stamps* the received pose into the slot descriptor (that is
done on the network/render-entry path, not the render itself), so the descriptor looked correct while
the pixels were a stale leftover frame. `publish` sat at a constant value.

Verified with `publish` sampled over 5 s: **0 fps**.

### Fix
Set an explicit frame target for both backgrounded states, in **both** copies of the file
(the profile's `config/` and `config/modpack_defaults/`, since Modrinth can re-apply defaults):

    "unfocused": {"frame_rate_target": 60, "run_garbage_collector": false}
    "invisible": {"frame_rate_target": 60, "run_garbage_collector": false}

### Guard so this cannot mislead again
`tools/oracle.py` now **refuses to run** unless the guest is publishing frames
(`wait_for_publishing()`): it samples the publish counter over several seconds and aborts with an
explanation if it does not advance. A stale frame can no longer be mistaken for a camera result.

### Also learned (kept, and worth having)
- The host→guest→render pose maths is **self-consistent**. `HostBridge.SendCamera` sends `180 - ow_yaw`
  and `CameraMixin` builds the rotation with `rotationYXZ(pi - yaw, ...)`; those cancel exactly, so the
  guest ends up rendering at MC yaw == OW yaw. Earlier suspicion of a "double conversion" was wrong.
- `Camera.alignWithEntity(float)` does exist in MC 26.3 (private) and is called from `Camera.update`
  at offset 91, before `calculateFov` and `setupPerspective`; `Camera.extractRenderState` then copies
  position/xRot/yRot/rotation into the `CameraRenderState` that `renderLevel` draws from. The mixin
  targets a live method and sets the fields that matter — the wiring is correct.
- Added `oracle [on|off]` to the dev bridge: it holds `HostBridge` from sending poses, so an outside
  client can hold a fixed camera. Without it the host overwrites the oracle's pose every frame and the
  test silently measures the player's camera instead.
- Disabling Iris shaders (`enableShaders=false`) changed nothing: shaderpacks are **not** responsible
  for the identical frames.
- Host link recovery after a guest restart can take ~a minute and sometimes needs an OW restart; the
  socket settles into CLOSE-WAIT and the retry loop goes quiet for a while.

### Status when this session ended
- Guest: fixed and healthy (3 slots populated, 60 fps, seqlock clean).
- Host: reads clean (`torn 0`, rotates slots), picture renders stably.
- Oracle: written (`tools/oracle.py`), instrumented and guarded, **not yet run to a verdict** —
  it needs Outer Wilds in a save with the un-throttled guest so the frames actually move.

## Session: two real host/guest bugs fixed; the flat-sky mystery narrowed

### Fixed: host link wedged forever on a dead socket (HostLink.Pump)
Symptom: after a guest restart the host never reattached — the socket sat in CLOSE-WAIT and the
OWML log went quiet. Every guest restart needed a full Outer Wilds restart.

Cause: `Pump()` looped on `while (_running && s.Connected)`. .NET's `Socket.Connected` reflects the
**last I/O**, not the peer, so it stays true after the guest exits. With `s.Available == 0` the loop
took the `Thread.Sleep(1); continue;` branch forever: it never called `Receive()`, so `ReceiveTimeout`
never fired and it never returned to `Connect()`.

Fix: wait with `Socket.Poll(50ms, SelectMode.SelectRead)`. A readable socket with 0 available bytes
is a closed peer -> throw and let `Loop()` reconnect. Verified: killed the guest and the host logged
`socket closed by the guest` then reattached to the new guest within ~1 s, **with no OW restart**.

### Fixed: guest throttled to 0 fps while backgrounded (dynamic-fps)
`config/dynamic_fps.json` from the modpack had `"invisible": {"run_garbage_collector": true}` with no
`frame_rate_target`, so a backgrounded Minecraft stopped rendering. The guest still stamped the
received pose into the slot descriptor (done on the entry path, not the render), so the descriptor
looked right while the pixels were a stale frame. This produced byte-identical frames for every pose
and led to several false conclusions. Set to 60 fps for both `invisible` and `unfocused`, in the
profile's `config/` **and** `config/modpack_defaults/config/`. `tools/oracle.py` now refuses to run
unless the guest is publishing, so a stale frame cannot be mistaken for a result again.

### Removed a clear/copy race (FrameExporter.captureWorld)
`encoder.clearColorTexture(target.getColorTexture(), TRANSPARENT)` ran in the same encoder as the
`copyTextureToBuffer` of that same texture, and also wiped the texture before `captureOverlay()` read
it for the HUD. Removed (the clear was never needed). Overlay layer was always empty; not yet
re-verified after the change.

### The remaining bug: the exported colour layer is flat sky, whatever the pose
The oracle can now hold a pose and the descriptor confirms the pose is applied
(e.g. `rendered from pose (0.50,8.00,0.50) yaw 0.0 pitch 40.0`), and the guest publishes at 60 fps.
Yet the colour layer is **always** `(181,209,255)` regardless of pose — including:
- yaw 0/90/180/270 held 2 s each;
- straight down from y=15 onto a 7x7 gold plate at y=0 (gold pixels: 6);
- straight at a solid orange wall 2 m ahead (orange pixels: 20);
- straight down from y=64 onto a 41x41 gold platform with an orange wall ahead.

Whole frame is nonzero (all 1280x720), only ~29 distinct colours: a genuinely rendered but empty
scene, i.e. it reads as the render target's **clear colour**, not sky.

The guest world is **superflat/void**: `setblock` succeeds from y=-64 to y=100 (all air). So there is
no terrain, and the only things that should be visible are my own blocks — which never appear.

### Suspect: GameRendererMixin disables the WRONG boolean
`blockcraft$noSky` uses `@ModifyArg` on `LevelRenderer.render(...ZZ)V` at `index = 5` and treats it
as "should render sky". Disassembly of `GameRenderer.renderLevel` shows the two trailing booleans are:
- index 5 = `!bossOverlay.shouldCreateWorldFog()`  -> **fog**, not sky
- index 6 = `!appliedPostEffects.isEmpty()`        -> post-processing present

So with a host attached this mod turns **world fog off**, not the sky. (The 26.3 signature is
`render(GraphicsResourceAllocator, boolean, CameraRenderState, GpuBufferSlice, Vector4f, boolean, boolean)`.)
Whether that is what empties the picture is **not yet proven** — the next step is to disable the
mixin's ModifyArg entirely and re-run the gold-platform test, then bisect from there.

### Also confirmed this session (host side, all healthy)
- `reader: reads N torn 0 missed 0`, rotating slots; `link: connected True errors 0`; `guest: frames N, misses 0`.
- `Script error: OnPreCull` in OWML appears in every session, including ones where the picture rendered fine: benign OWML event-logging noise, not a fault.

## Root cause of the "frozen frame": Outer Wilds had no player camera, so the host sent no poses

**The flat/frozen colour layer was never a Minecraft rendering bug.** It was stale data in
`/dev/shm/blockcraft-frame` from an earlier session, being re-read by the compositor.

The chain, proven this session:

1. **The guest was not exporting at all.** `/dev/shm/blockcraft-frame` did not exist while the guest
   was running a world with `render3dHud` firing 2700+ times.
2. **`cam trace` showed `pose NULL` on every one of 2700 consecutive frames** — `HostState.frame()`
   was null, so `FrameExporter.captureWorld` returned before `ensureShm()` and never created the file.
3. **`HostBridge.Tick` was returning early at the camera check.** The dev bridge's `dump` printed
   `host: no camera`; `Locator.GetPlayerCamera()` was null.
4. **The host screenshot proves why:** `shots/owstate.png` is 86% near-black (`(2,4,6)`), i.e. Outer
   Wilds was on a black/menu/loading view, not in the solar system. No player body, no player camera.
5. The compositor meanwhile reported `frames 60116 ... publish 11916` — 60116 reads of a mapping last
   written 11916 publishes ago. **That is the frozen picture**: real pixels, captured once, long dead.

So every hypothesis that treated it as a rendering fault was chasing the wrong thing:

- the `ModifyArg` (`blockcraft$noSky`, `index 5` = reversible **fog**, not sky) was a real misuse but
  **not** the cause; it is now disabled in `GameRendererMixin` with a comment recording why;
- the `MainTarget`-colour-handle theory, the MSAA-resolve theory and the improved-transparency theory
  are all **disproven**: a direct probe of `mainRenderTarget.getColorTexture()` at both frame points
  shows `RGBA8_UNORM 1280x720`, a **stable identity**, and a hash that **changes every frame**
  (`nonzero 3686400/3686400 changedSinceLastFrame true`). The colour texture is live and correct.
- the colour texture is the same object at `render3dHud`-time and at `GameRenderer.render`-time
  (`colour id 1234747206 fmt RGBA8_UNORM` at both `worldHook` and `endHook`).
- `improvedTransparency` is `false` in the profile, so the composite theory is out too.

### Fix applied
`HostBridge.Tick` no longer caches the camera with `_cam ?? = Locator.GetPlayerCamera()`. A Unity
object that outlives a scene change is non-null in C# while destroyed in Unity, so reading its
transform throws and kills the rest of `Tick` — silently stopping every pose. It now re-resolves
`Locator.GetPlayerCamera()` every frame and adopts it.

A new dev command, `state`, prints the objective facts that gate pose sending:
`paused`, `timeScale`, active scene name + loaded, player body, camera, and whether the oracle hold
is on. This is the check to run first whenever the guest picture looks frozen.

### Correction to the earlier note in this file
The "flat sky, whatever the pose" section above is a **misreading of stale shm**. The colour layer was
not flat sky from a rendered-but-empty scene; it was an old capture of a working scene that stopped
being republished. The guest world being void/superflat is separately true and untested, because no
frame from that world was ever exported.

### Operational lesson
Before any frame-layer conclusion: **check `/dev/shm/blockcraft-frame` exists and its `publish`
counter is advancing.** If not, no conclusion about the picture is possible. `tools/oracle.py`'s
`wait_for_publishing()` guard does this; the ad-hoc scripts did not, and that is what produced hours
of false conclusions.

## The frozen colour layer: root cause is a premature `encoder.submit()`

**Found and fixed.** The captured colour layer contained a real world image that **never changed**,
however the camera moved, however long the guest ran, and even when a 13×3 block wall was built
directly in front of it. The descriptor was correct, `extractRenderState` logged the host pose exactly
`xRot`/`yRot`/position, the guest published at a steady 60 fps, and `arrive` fired reliably with no
`capture expired` warnings — so the fault was neither in the camera override nor in the capture
accounting.

### The proof that located it
Vanilla's own screenshot path was used as a control, called from the same injection point
(`GameRenderer.render` TAIL) with the same `mainRenderTarget` that `Screenshot.grab(Minecraft, …)`
uses for F2. Three shots at three very different camera poses came out **byte-identical and pure
black**, while the shm export at that same instant held a plausible world image. Vanilla and the
export disagreed about the same texture, which meant one of them was not reading the live frame.

### The cause
`GlDevice.createCommandEncoder()` returns `this.encoder` — the backend has **one shared encoder per
device**, not a fresh one per call. Vanilla's `Screenshot.takeScreenshot` gets that shared encoder,
queues `copyTextureToBuffer`, and **returns without submitting**; the render system submits the shared
encoder once, at the end of the frame, when the world really is in `mainRenderTarget`.

`FrameExporter` called `RenderSystem.getDevice().createCommandEncoder()` and then `encoder.submit()`
on it — which submits the *frame's* shared encoder early, in the middle of the frame, on every
capture. The copies were therefore executed as tiny standalone batches **before** the world had been
drawn into the texture. `copyTextureToBuffer`'s runnable still fired, `publish` still ran, and the
destination buffer simply kept whatever bytes a previous successful copy had left there. That is the
exact signature observed: a stale, plausible, unchanging image, published at full rate.

### Fix
Both `encoder.submit()` calls were removed — `FrameExporter.captureWorld` and
`FrameExporter.captureOverlay` now queue their copies and return, exactly like vanilla. The overlay
hook is back at `render3dHud` for the world layer and `GameRenderer.render` TAIL for the overlay, as
the two-layer split intends.

### How to catch this class of bug again
An un-submitted encoder is not a bug in this API — **submitting is**. When copying from a frame-owned
target, mirror `Screenshot.takeScreenshot` and never call `submit()` yourself.

### Operational note: Outer Wilds pauses on focus loss, and focus is Wayland
Outer Wilds drops its `Update` loop whenever it loses focus (launching Minecraft on top of it is
enough), so no poses are sent and the guest stops exporting. On this machine the session is KDE
Plasma on **Wayland**, where `xdotool windowactivate`/`windowfocus` do not work. Focus has to be
given by the compositor; a small KWin script run over D-Bus does it:

```
qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript /tmp/opencode/kwin-activate.js
qdbus6 org.kde.KWin /Scripting/Script$ID org.kde.kwin.Script.run
```

where the script walks `workspace.windowList()` and sets `workspace.activeWindow` for the window whose
`resourceClass` is `steam_app_753640`. X11 window ids from `xdotool search --name "Outer Wilds"` are
XWayland ids and are not what `_NET_ACTIVE_WINDOW` reports. Confirm the game is live before concluding
anything about a frame: the dev bridge's frame counter in `dev_log.txt` must be advancing.

## 2026-10-20 — the frozen frame, solved (it was never the guest's copy code)

### What was actually wrong
The frame export could not deliver a picture because **Minecraft's own readback path reads the wrong
framebuffer in this session**, and so did we while using it.

`CommandEncoder.copyTextureToBuffer` is not a deferred GPU copy. Disassembling
`GlCommandEncoder.copyTextureToBuffer` shows it is a **synchronous `glReadPixels`**, issued against a
**cached `readFbo`** owned by the device:

```
bindFrameBufferTextures(directStateAccess(), readFbo, ...)   // cached, may already be bound elsewhere
_glBindBuffer(GL_PIXEL_PACK_BUFFER, buffer.handle())
_readPixels(x, y, w, h, glFormat, glType, offset)
RenderSystem.queueFencedTask(runnable)                        // the runnable is a fence drain, not a copy
```

Whether `submit()` was called or not changed nothing, because the pixels were already read (or not
read) by then. Measured, on a live publishing guest: the colour buffer's hash was the **same value**
(`-7859556964388389703`, later `0`) on **every publish for 900+ frames**, while the descriptor was
correctly carrying five different camera poses.

### The control that settled it
`Screenshot.takeScreenshot(mainRenderTarget, ...)` — vanilla's own screenshot, called from the same
hook point — returned a **pure-black 1280x720 image with hash `9139525410424356864` on every frame**,
and so did a raw `glReadPixels` on the default framebuffer. Meanwhile the *same texture*, read at the
*same moment* through a framebuffer we bind ourselves, returned **921600 of 921600 non-black pixels**
with `GL_FRAMEBUFFER_COMPLETE`. So:

- the world **is** in `mainRenderTarget` at the hook point,
- the texture is fine,
- Minecraft's readback and the default framebuffer are both unreliable here.

This also means the earlier note "vanilla's own screenshot is black too, so it is an environment
problem" was right, but the wrong conclusion followed from it: the environment does not stop us
reading the texture, it only stops *Minecraft's* reader.

### Fix
`FrameExporter` no longer touches `GpuBuffer`, `CommandEncoder` or `copyTextureToBuffer` at all.
`FrameExporter.readTexture` generates a framebuffer, attaches the target's colour (or depth) texture
via `GlTexture.glId()`, checks completeness, reads with a raw `glReadPixels` into a
`BufferUtils`-allocated direct `ByteBuffer`, then restores and deletes the framebuffer. The layers are
read synchronously, so the capture is complete in the same frame and the seqlock publish is immediate.
`pending` is 2 (colour+depth at the world hook, overlay at the tail) instead of 3 fenced tasks.

### Proof
With the guest pinned to four different poses and **no host involved**, the export produced four
distinct frames:

```
A high down  y30 p40 : colour 3d96b9e10a35 depth 60407b8fbaca ovl ad7f5ec68742 mean (189,155,125)
B yaw180     y30 p40 : colour 81fedc1517b0 depth 200f64f6066b ovl f034808adeb6 mean (210,209,169)
C far away   x200    : colour becb40d4713a depth 78eb95bf2057 ovl 3d3ee4c7c0fa mean (177,206,254)
D low        y8  p0  : colour aa696b484bd7 depth 84ef95449924 ovl 6f3a5149cc59 mean (108,129,161)
distinct COLOUR frames: 4 of 4
```

Every layer is fully populated (`colour-nonblack 921600`, `overlay-nonblack 918342` — the overlay had
been all zero before). The means read as sky/ground/horizon, so the camera override is genuinely
reaching the render.

### Standing aid: `pin`
The exporter only runs while a pose is live, and `HostState.live()` times out after two seconds, so
the export could previously only be observed while Outer Wilds was focused and sending. The new
`{"t":"pin","p":[x,y,z,yaw,pitch,fov]}` message on the guest link holds a pose with no host attached
(`{"t":"pin"}` clears it). It makes the guest debuggable on its own and is how the fix was proved.

### Gotcha
`GlDevice.createCommandEncoder()` returning one shared device-level encoder is still true and still
worth knowing, but it was not the cause. The doc comment claiming that was removed.

## 2026-10-20 — the alignment oracle passes; the contract's axes are confirmed

The oracle was chosen as the next work item because the contract's position/yaw/pitch conversion was
still marked unverified, and a wrong sign still renders *a picture*. It is now settled.

### What the oracle had wrong
The oracle had produced a confident, entirely wrong verdict once before, and three separate defects all
pointed the same way:

1. **It judged black frames.** `classify` picked the nearest probe colour with no absolute closeness
   test and no separation from the runner-up, so a near-black frame made every pixel "nearest black" —
   one run reported a calm "south(+Z) is in the UPPER half ... PITCH SIGN IS INVERTED" from a frame
   with no landmarks in it at all.
2. **Its landmarks were never built.** It placed them with a bare `setblock`, and `setblock` refuses an
   occupied cell unless told `replace`, so wherever the cross landed in solid ground the game answered
   "Could not set the block" and the oracle carried on regardless.
3. **It only analysed a quarter of the frame.** `analyse` looped `range(0, w*h, 4)` and indexed
   `pixels[i]` as bytes. `w*h` counts *pixels*, so the walk covered the first quarter of the RGBA
   buffer and stopped. A landmark in the bottom of the frame was reported "not visible" while a direct
   count of the same buffer found 31776 of its pixels.

### What fixed it
- `classify` now demands the match be within 30 per channel *and* clearly nearer than the runner-up,
  and the probes hold the **rendered** colours rather than the block textures'. That distinction is
  large: yellow concrete renders at about (143,105,13) here, not (240,200,40), because the scene is
  dimly lit. Probes set from texture values matched almost nothing.
- `is_flat` rejects any frame that is one colour, and `analyse` refuses to run on one, so a sky-only
  frame can never carry a verdict again.
- `MIN_LANDMARK_PIXELS` stops a handful of stray matches from standing in for a landmark.
- The cross is built inside a **cleared arena in open air** at y=116, with the floor laid and each
  landmark placed with `replace`. Ground level is unusable: the camera ends up inside terrain, and the
  resulting frame — a black rock tunnel with sky at the bottom — is exactly the sort of thing the old
  classifier read as a landmark.
- The camera **looks straight down**. The landmarks sit on the axes, 90° apart, so a horizontal camera
  can only ever see two; an earlier attempt at yaw 0 / pitch 40 with the cross 6 blocks out and 4 down
  put every landmark 56° off the view axis against a 35° half-angle and saw nothing but sky.

Two more mundane bugs on the way, both worth remembering for the same reason — the command output was
there all along and nobody was reading it:
- `CAM_Y + 2` with `CAM_Y = 120.0` produced `fill ... 122.0 ...`, which the game rejected with
  "Invalid integer"; the arena was never cleared. Every coordinate is an `int` now.
- The floor fill had the ground level in the x slot (`fill 115 115 -12 12 115 12`), filling a sliver out
  at x=115 instead of the floor.

### The verdict
```
north centroid ( 639.6,  29.8)  -> centre, upper half   (20531 px)
east  centroid ( 141.7, 359.5)  -> left, middle half   (153587 px)
south centroid ( 639.5, 670.9)  -> centre, lower half   (31776 px)
west  centroid (1120.4, 359.5)  -> right, middle half  (167722 px)

  east(+X) is LEFT of west(-X): correct
  north(-Z) is ABOVE south(+Z): correct
  cross centre (631,350) vs frame centre (640,360): offset (-9,-10)px centred

CONTRACT CONFIRMED by the four-landmark cross.
```

So `MC = (OW.x, OW.y, -OW.z)`, `MC.yaw = 180 - OW.yaw`, `MC.pitch = -OW.pitch` are correct as written.
`docs/CONTRACT.md` has been updated from "unverified" to confirmed with the measured table.

### Note on the aspect ratio the verdict prints
The run also prints `landmark spread 979x641px, aspect 1.53` and does not fail on it. East and west are
3 blocks out to the sides, which subtends a wide angle, so those two landmarks run to the frame edges
and their centroid spread is wider than tall. The centroids are still in the right places, which is what
the checks use; the aspect line is reported for information rather than asserted.
