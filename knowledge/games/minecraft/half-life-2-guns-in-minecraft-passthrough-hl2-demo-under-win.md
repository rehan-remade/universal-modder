---
kind: game
title: Half-Life 2 guns in Minecraft (passthrough, HL2 Demo under Wine on macOS)
game: Minecraft
games_also:
- Half-Life 2 Demo
game_version: Minecraft Java 26.3 (demo account), Fabric Loader 0.19.5, Fabric API 0.161.0+26.3; Half-Life 2 Demo (Steam app 219) on the HL2 depot build 19307283, 32-bit hl2.exe with DXVK d3d9
platform: macos
engine: java
route: passthrough
tools:
- Fabric (Loom 1.18)
- Wine 10.0 (Sikarugir wrapper)
- ScreenCaptureKit (Swift helpers)
- imageio-ffmpeg via uv
anti_cheat: none in single-player (VAC only applies to HL2 multiplayer; nothing online was touched)
status: working
agents:
- Claude Code (Claude Opus 5.5)
humans: []
date: '2026-10-05'
links: []
tags:
- source-engine
- wine
- macos
- screencapturekit
- chroma-key
- console-bridge
---
# Half-Life 2 guns in Minecraft (passthrough, HL2 Demo under Wine on macOS)

> A live Half-Life 2 Demo (Steam, running under Wine on an arm64 Mac) renders and plays the sound of the real
> first-person weapon, while a Fabric mod for Minecraft Java 26.3 does the gameplay: hitscan, damage, grenades,
> gravity-gun punts. Minecraft input is forwarded to HL2's console through cfg files, and HL2's view, keyed down
> to just the weapon, is drawn over Minecraft's world. Verified in both real games with screenshots, frame
> timing traces and a recorded clip with HL2's audio. All 7 weapons the demo contains work.

## Setup
- macOS 27 arm64. Minecraft Java 26.3 on a **demo** account: the launcher's Installations tab still launches a
  modded Fabric installation (in demo mode), with its own game folder.
- HL2 Demo installed through Windows Steam inside a Sikarugir Wine wrapper. Native macOS HL2 is gone (the Mac
  builds are 32-bit x86), but the Windows build runs under Wine 10 with DXVK.
- Launch options: `-windowed -w 1728 -h 972 -novid -condebug +exec hl2craft`. `-insecure` is not needed offline.
- Java 25 for the build (`JAVA_HOME=/opt/homebrew/opt/openjdk@25/...`), Swift 6.4 for the capture helpers.

## Route and why
Passthrough. A content port (converting the HL2 VPK sounds and models) was the fallback. The user wanted the
real HL2 running, and HL2 drawing its own viewmodel gives the real animations, muzzle flashes and sounds for
free. Minecraft stays authoritative for gameplay. HL2 only renders and sounds the gun, so the two simulations
never have to agree about the world.

## How the game works (what we had to learn)
- **Console as the control channel.** Source has no remote console in this build (no `-netconport` in
  engine.dll). An alias loop does the job: `alias hc_poll "hc_next; wait 1; hc_poll"`, with
  `alias hc_next "exec hl2craft/hc_0"`. Each `hc_N.cfg` (written with an atomic rename) runs its commands,
  echoes `HL2CRAFT ack N`, then re-points `hc_next` at N+1, so every command runs exactly once. `-condebug`'s
  console.log is the back channel: acks, `getpos` output, and which N HL2 is waiting for (it survives HL2
  restarts).
- **`wait` inside an exec'd file does not hold a button.** `+attack; wait 4; -attack` presses and releases in
  the same frame, so nothing fires. Proven with `getpos`: the yaw didn't change for `+left; wait 60; -left`, and
  did when `+left` and `-left` came in separate files. Send `+x` and `-x` as two files about 80 ms apart.
- **HL2 keeps simulating and taking console input when unfocused**, if you set `snd_mute_losefocus 0` and
  `engine_no_focus_sleep 0`.
- **The demo has a map whitelist.** A self-compiled map (valid BSP v20, listed by `maps *`) fails with
  `map load failed: X not found or invalid`. The binaries carry the demo's own map list (d1_trainstation_01/02,
  d1_town_01/01a/02/03, background0x, ...). We didn't work around it.
- **"Viewmodel only" inside a demo map** (d1_town_01, developer console, single-player):
  - Turn off the world: `r_drawworld 0`, `r_drawstaticprops 0`, `r_drawdisp 0`, `r_drawbrushmodels 0`,
    `r_drawdetailprops 0`, `r_drawropes 0`, `r_drawparticles 0`, `r_3dsky 0`, `r_drawskybox 0`. HL2 then
    clears to black.
  - Fog whatever is left pure green: `fog_override 1` plus fog color 0 255 0 with start 0 and end 1.
  - Light the gun evenly with `mat_fullbright 1`.
  - The viewmodel is not fogged. `r_drawothermodels 0` hides the viewmodel as well, so leave it on.
  - Key out both black (soft ramp over max channel 6..24) and green-dominant pixels. Dark green blended with
    black goes fully transparent.
- **Demo weapons that load:** crowbar, pistol, smg1, shotgun, 357, frag, physcannon. rpg, ar2, crossbow,
  bugbait and alyxgun print "Error reading weapon data file" and have no viewmodel. `sv_infinite_ammo 1` works.
- **`getpos` prints `setpos 0 0 0` while a map is still loading.** Wait for a non-zero setpos before giving
  weapons.

## Build steps
Code: the user's repo `hl2craft-mod` (Fabric mod, Swift helpers, cfgs).
1. Copy `hl2cfg/hl2craft.cfg` and `hl2craft_stage.cfg` into `Half-Life 2/hl2/cfg/`.
2. Start HL2 with the launch options above.
3. Build and run `capture/hl2capture` (ScreenCaptureKit, Screen Recording permission). It captures the HL2
   window's 16:9 client area 1:1, keys it, and writes double-buffered RGBA into
   `~/Library/Caches/hl2craft/frame.rgba` (header: magic, size, seq, unix ms).
4. Install the mod jar plus Fabric API. The mod memory-maps the frame file, copies it into a DynamicTexture
   (RGBA in the file equals NativeImage's layout, so it's one memcpy), and draws it in a HUD layer before the
   crosshair. The vanilla held item is hidden with an item-model `select` on `display_context` →
   `minecraft:empty` in first person.
5. In-game: draw an HL2 weapon. The first time, the mod loads d1_town_01, waits for a real `getpos`, then runs
   the stage once.

## Verification
- Screenshots of all 7 HL2 viewmodels over the Minecraft world.
- A still zombie dies to 4 pistol headshots (2.0 × 3 vs 20 HP, matching HL2's 5 damage × 3 headshot scaled by
  50→20 health). The shotgun knocks back and kills wave zombies.
- **Latency trace** (`~/.hl2craft-trace`):
  - Minecraft input → bridge file: 3 ms.
  - Bridge file → first changed HL2 frame: ~110 ms.
  - HL2 delivers ~30 new full-res frames/s while behind Minecraft.
- A 54 s recording with HL2's real gunfire in the audio.
- **Not verified:** gravity-gun punt on a target (no zombie in reach during the test), SMG grenade impact
  explosions, behaviour after the Minecraft demo timer runs out.

## Gotchas
1. **Wine exits with 136 and prints nothing when started from a shell.** Cause: SIGFPE in ntdll (see the crash
   report). The client's sync mode differed from the wrapper's running wineserver. Fix: set the same
   `WINEESYNC=1 WINEMSYNC=1` as the wrapper's Info.plist, plus `DYLD_FALLBACK_LIBRARY_PATH` pointing at the
   wrapper's Frameworks.
2. **The capture helper grabbed the editor window.** Cause: VS Code's title also starts with "Half-Life 2".
   Fix: match the exact case-sensitive title prefix `HALF-LIFE 2 - ` and an owner app name containing `wine`.
3. **A command-line ScreenCaptureKit tool asserts `CGS_REQUIRE_INIT`.** Fix: call
   `NSApplication.shared.setActivationPolicy(.prohibited)` first.
4. **The recorder crashed with "NSWindow should only be instantiated on the main thread".** Cause:
   `SCRecordingOutput` adds a menu-bar status item. Fix: `NSApplication.shared.run()` instead of
   `dispatchMain()`.
5. **The recording was silent.** Cause: a window-only `SCContentFilter` records only that window's app audio,
   and HL2's sound comes from Wine. Fix: use a display filter including the Minecraft and Wine apps, with
   `sourceRect` set to the Minecraft window.
6. **"No shot" looked like a paused simulation.** Cause: the `wait` problem described above. Also, measuring
   frame differences over the whole frame hid the recoil (the gun is ~3% of pixels). Fix: separate press and
   release files, crop to the gun area, and read HL2's HUD ammo counter (`cl_drawhud 1`) as ground truth.
7. **SCK's frame-rate count looked like 58 fps when HL2 drew ~20.** Cause: SCK also delivers idle repeat
   frames. Fix: skip samples whose `SCStreamFrameInfo.status` isn't `.complete`.
8. **A `map` in the startup cfg was ignored.** Cause: the menu's background map loads after it. Fix: have the
   mod load the map later, through the bridge.
9. **god and notarget switched off after re-staging.** Cause: they're toggles. Fix: a self-disarming alias
   `hc_stage_run "exec stage; alias hc_stage hc_noop"`, re-armed with `hc_arm` after a map reload.
10. **HL2 switched away from the frag after every throw**, even with infinite ammo. Fix: re-send
    `use weapon_frag` about 1.2 s later.
11. **The kit wasn't re-given after respawn.** Cause: a Minecraft respawn keeps the entity id but makes a new
    LocalPlayer. Fix: compare the player object, not the id.
12. **Never shrink the shared frame file**, because the Java side keeps it mapped (SIGBUS). Only grow it, and
    remap when the header's size changes.
13. **macOS input driving:** `NSRunningApplication.activate` can't bring Wine to the front (System Events
    can). Synthetic keys only arrive after clicking into the game window. Typing into Minecraft chat with
    synthetic events dropped characters, so test through keybinds instead.
14. **console.log grows ~10 KB/s** from the poll's "not present" lines. `con_filter` doesn't keep them out of
    the `-condebug` log. Rotate the log between sessions.

## Assets
None generated. Item icons are placeholder pixel art drawn with PIL. Every HL2 visual and sound comes live
from the user's own HL2 install; nothing from HL2 is copied into the mod.

## Cost and time
One long session (~5 h wall-clock), including restarts of both games.

## Open questions
- Rotate or truncate console.log safely under Wine.
- Sync HL2 view angles with Minecraft's camera for true viewmodel sway (we fake sway in 2D).
- A smaller frame (crop to the viewmodel's bounding region) would cut memcpy and upload cost.
- The full HL2 (not the demo) could use the self-compiled chroma-key room instead of the fog trick.
