---
kind: game
title: "Telekinesis powers (rip, hold, throw, push) as a ZHMModSDK plugin"
game: "HITMAN World of Assassination"
games_also: []
game_version: "Steam PC, HITMAN3.exe from the 2026-08-27 patch (app 1659040)"
platform: windows
engine: unknown
route: native-hook
tools: ["ZHMModSDK 4.1.1 (DevPkg)", "Peacock 8.9.1", "Simple Mod Framework 2.33.42", "MSVC 14.51 + CMake + Ninja + vcpkg", "um win", "dbghelp"]
anti_cheat: "none in offline play; the game is online-connected, so it ran only under Peacock (offline server, leaderboards=false) and never against IOI's servers"
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: ["@skurtyyskirts"]
date: 2026-10-10
links: ["https://github.com/OrfeasZ/ZHMModSDK", "https://github.com/thepeacockproject/Peacock", "https://github.com/atampy25/simple-mod-framework"]
tags: ["glacier-2", "zhmmodsdk", "peacock", "telekinesis", "physics", "ragdoll", "imgui", "powers"]
---

# Telekinesis powers (rip, hold, throw, push) as a ZHMModSDK plugin

A C++ ZHMModSDK plugin gives 47 Control-style powers in HITMAN World of Assassination (Glacier 2): Launch rips
a brick out of the wall (or grabs a loose prop near the crosshair), holds it floating beside 47 and throws it
(knocking down or killing NPCs), and Push ragdolls the NPCs in a cone. It runs in the real game under Peacock.
Rip, hold, throw, aim-assisted kill ("NON-TARGET KILLED"), a 2-NPC Push and a 10-minute soak were checked in game
with logs and screenshots. A light-throw knockdown was not checked end to end, and neither was grabbing an
IOI-placed level item on camera.

## Setup
- HITMAN WoA, Steam, Windows 11, the 2026-08-27 patch. Plain `steam://rungameid/1659040` launches it when
  Steam's launch options pass `-SKIP_LAUNCHER`. `steam://run/1659040//-skip_launcher/` hangs on a hidden Steam
  "launch arguments" prompt.
- **Offline only, under Peacock 8.9.1** (the community server replacement). HITMAN WoA keeps progression,
  challenges and leaderboards on IOI's servers, and this plugin changes how NPCs die, so it was only ever run
  under Peacock and never against IOI's servers. Keep it that way: start the server, then `PeacockPatcher.exe`,
  then the game, and take the plugin out of `Retail\mods.ini` before any session on the official servers.
- Set `leaderboards=false` in Peacock's `options.ini`. It defaults to `true`, which submits your times to
  Peacock's shared leaderboards, and modded runs don't belong there.
- **ZHMModSDK 4.1.1:** extract the release zip into `Retail\`. It installs `dinput8.dll`, `ZHMModSDK.dll` and
  `mods\`. Enable a plugin with a `[<name>]` section in `Retail\mods.ini`. Uninstall by deleting those files.
- Build: the SDK's DevPkg with CMake/Ninja/vcpkg (MSVC 14.51). The plugin must also link `implot`, because
  `IPluginInterface::CleanupUI` uses it. The DevPkg's `ZHMModSDK.dll` is byte-identical to the release loader's,
  so installing only adds `mods\<plugin>.dll`.

## Route and why
`native-hook` through ZHMModSDK. The SDK already exposes what the powers need: raycasts, kinematic transforms
on physics objects, ragdoll + impulse, `ZActor_KillActor`, `ZItemSpawner`, per-frame updates, a `ClearScene`
hook and an ImGui overlay. An SMF content mod (QuickEntity) cannot run per-frame logic like this.

## How the game works (what we had to learn)
- **Frame updates** registered with `eUpdatePlayMode` also tick in the main menu, because the menu is a scene.
  Gate gameplay on your own "engine ready" check (`EngineFunction::Exists()` for every function you call).
- **Spawning:** `ZItemSpawner` plus `RequestContentLoad`. The spawned item shows up in
  `WorldInventory->m_aItems` in the same frame. `Archmesh1h Rock` is IOI's placeholder proxy cylinder. A real
  brick is `Melee_Brick` (`5cc4d1ea-b4fa-4667-ba3a-b6e859f03059`).
- **Moving items:** setting the kinematic transform works on both the `geom` and the `root`. A level item moved
  up 1 m stayed there, and physics did not pull it back. The SDK has no call that adds an impulse to a dynamic
  prop, so thrown objects fly on a trajectory the plugin computes, and impacts are resolved by proximity
  (`ActorsNear`) first.
- **NPCs:** ragdoll + pelvis impulse gives a knockdown, which is temporary because NPCs get back up after a few
  seconds. `ZActor_KillActor(eDE_DeadlyThrow, eDB_IMPACT_ANIM)` kills, and the game credits it as a non-target
  kill.
- **Raycasts** classify hits as `Surface` (with a normal) or `Prop` (with its id). `SDK()->WorldToScreen` returns
  physical pixels, and "visible" means inside the frustum, not unoccluded.
- **Third-person camera:** the camera sits behind and to the right of 47. Measure aim cones from the camera and
  ranges from 47. Otherwise NPCs under the crosshair fall outside a 47-centred cone.
- **Log:** `ZHMModLoader.log` is in the game root, not `Retail`. It stays 0 bytes until flushed, and killing
  the game loses the buffer. The plugin flushes through the exported `GetLoggers()`.
- **Input:** read keys and mouse side buttons through the SDK's input bindings (tokens `kb,1`, `mouse,mb4`,
  `mouse,mb5`), and only while HITMAN has focus.

## Build steps
The plugin source is not published, so there is no repository to link. These steps rebuild it against the SDK's
DevPkg, and the outline below lists the SDK calls each power uses.

1. Install Peacock and ZHMModSDK as above, and back up saves (`um backup`) and `Retail\mods.ini`.
2. Write one `IPluginInterface` class, modelled on the mods bundled with the SDK. Add `implot` to the vcpkg
   manifest and to `target_link_libraries`, then build Release from an x64 MSVC prompt:
   `cmake -G Ninja -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE=<vcpkg>/scripts/buildsystems/vcpkg.cmake`
   and `cmake --build build`. Copy the DLL to `Retail\mods\`.
3. Add `[<plugin>]` to `Retail\mods.ini`. `~` opens the SDK overlay, where the plugin's menu items live.
4. Start Peacock, then launch.

### Plugin outline
- `OnEngineInitialized`: register one `eUpdatePlayMode` frame update and hook `ClearScene` to drop held state.
- Every frame: return until every `EngineFunction` used `Exists()`, then read the bound inputs.
- **Launch (rip):** raycast from the camera. A `Prop` hit within range is grabbed. A `Surface` hit spawns
  `Melee_Brick` with `ZItemSpawner` + `RequestContentLoad` at the hit point and grabs it once it appears in
  `m_aItems`.
- **Hold:** each frame, set the kinematic transform on the item's `geom` and `root` to a point beside 47.
- **Throw:** pick the target NPC by aim assist (camera cone, range from 47), move the item along a computed
  arc each frame, and on arrival check `ActorsNear`: ragdoll + pelvis impulse for a knockdown, or
  `ZActor_KillActor(eDE_DeadlyThrow, eDB_IMPACT_ANIM)` for a kill.
- **Push:** every NPC in a cone from the camera, within range of 47, gets ragdoll + an impulse away from 47.
- ImGui: menu toggles in the SDK overlay, and a reticle and energy bar in the HUD draw.

## Verification
- `um win` drove the game: keyboard menus, screenshots via gfxcapture, and crash events from `Get-WinEvent`
  (Application 1000).
- Test spots: ICA Facility Freeform Training for props (no NPC within 25 m of the start), and Paris "The
  Showstopper" for NPCs (two NPCs at the fountain near the start). The pause menu's Restart resets the scene.
- Checked in game: rip/hold/throw, an aim-assisted brick kill, Push hitting 2 NPCs, and a soft-lock grab of a
  loose brick. A 10-minute scripted soak (21 iterations) ran with no crash, but the restarts within it were not
  confirmed by the log.
- Not checked: a light-throw knockdown end to end, a hold on an IOI-placed level item on camera, and an NPC
  raycast (every NPC in range was occluded).

## Gotchas
1. **Crash in `QueryInterface` while scanning props.** **Cause:** `ZWorldInventory::m_aNonOwnedItems` (SDK
   header offset 0xC0) has the wrong layout for this build, and nothing in the SDK uses it. **Fix:** walk
   `m_aItems` and skip items parented under 47 or an NPC. Found by symbolizing the crash offset with dbghelp and
   the plugin's PDB.
2. **Crashes around scene changes with the SDK's `Outfits` mod enabled.** **Cause:** not proven, but the three
   crashes all happened with `[outfits]` in `mods.ini`, and none came back with it removed. **Fix:** leave it off.
   New suits don't need it (see the companion note on suits and pistols).
3. **Synthetic mouse clicks only hover HITMAN's menu items.** **Fix:** drive menus with the keyboard (Enter,
   arrows, PageDown for tabs, Esc). Clicks do work inside the SDK's ImGui overlay.
4. **Relative mouse moves turn the camera non-linearly** (acceleration). **Fix:** aim by target selection (aim
   assist), not by pixels. Side buttons need SendInput XBUTTON1/2, and keys need scan-code mode.
5. **Screenshots vs clicks at 150% DPI.** `um win shot` returns 3840x2160 physical pixels while clicks use
   2560x1440 client coordinates. **Fix:** divide by the DPI scale.
6. **SMF says "Unknown game version" after a game patch,** and the game silently runs vanilla. **Cause:** an old
   SMF writes `patchlevel` that the new `packagedefinition.txt` ignores. **Fix:** update SMF (2.33.42 supports
   the 2026-08-27 patch), then redeploy.
7. **SMF `Deploy.exe` hangs when piped in PowerShell** (idle `rpkg-cli -i` workers). **Fix:** `Start-Process`
   with stdin redirected from an empty file and stdout/stderr redirected to files. It then finishes in seconds.
8. **Peacock reads SMF's `deploySummary.json` only at startup.** **Fix:** deploy, restart Peacock, then launch.
9. **`um scan` reports "Unknown native engine"** and picks `launcher.exe`. Glacier 2 can be recognised by
   `Runtime\chunk*.rpkg` + `Runtime\packagedefinition.txt`, which is worth adding to the scanner.

## Assets
Bricks are vanilla items. The HUD is an ImGui reticle and energy bar.

## Cost and time
About one day from recon to a playable M1, including the in-game probes and the soak.

## Open questions
- Thrown props fly on a computed path because there is no impulse API for dynamic props. A native hook on the
  physics world could give real impulses.
- The scene-change crashes need a session-B control (plugin off) if they come back.
