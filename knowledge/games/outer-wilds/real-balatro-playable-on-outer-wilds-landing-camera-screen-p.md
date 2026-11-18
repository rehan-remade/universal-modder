---
kind: game
title: 'Real Balatro playable on Outer Wilds'' landing-camera screen (passthrough: shared-memory frames and mouse)'
game: Outer Wilds
games_also: ["Balatro"]
game_version: "Outer Wilds 1.1.16.1372 (Steam 753640), Unity 2019.4.39f1 Mono; Balatro 1.0.1o (Steam 2379780)"
platform: windows
engine: unity-mono
route: passthrough
tools: ["OWML 2.15.1", "Outer Wilds Mod Manager", "OuterWildsGameLibs 1.1.16.1372 (net48)", "lovely (version.dll build)", "Steamodded 1.0.0-beta-1224a (present, not needed)", "LuaJIT FFI", "ilspycmd 9.1", ".NET SDK 9.0.310", "Python 3 + Pillow"]
anti_cheat: "none (both single-player; Balatro is only ever started by the mod with its own Steam AppId)"
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-15'
links:
- https://github.com/ow-mods/owml
- https://github.com/ethangreen-dev/lovely-injector
tags: [mashup, passthrough, frame-compositing, shared-memory, seqlock, owml, lovely, love2d, landing-camera, render-texture, input-forwarding, focus]
---
# Real Balatro playable on Outer Wilds' landing-camera screen (passthrough: shared-memory frames and mouse)

> At the ship's controls in Outer Wilds, enter the landing-camera view and press B. Real Balatro starts beside the game,
> minimized, and its frames are painted onto the cockpit's landing-camera screen. The mouse is forwarded to Balatro;
> press B again to get the camera back. Two mods on one Windows machine: a lovely patch in Balatro and an OWML mod in
> Outer Wilds, joined by one named file mapping. It runs in the real game: driven by a mod-side command file, it showed
> 2,132 frames with 0 torn, opened Balatro's run setup with a forwarded click, and toggled off and back on to the same
> Balatro process.

## Setup
- Windows 11, Steam.
- **Host:** Outer Wilds **1.1.16.1372** (Unity 2019.4.39f1 Mono) with **OWML 2.15.1**.
  - That OWML build targets game 1.1.15.1018. On 1.1.16 it warns, and its own options menu logs an NRE in
    `TabbedNavigation.Awake`, but mods load and run.
  - The OWML mod builds `net48` against NuGet `OWML` 2.15.1 and `OuterWildsGameLibs` 1.1.16.1372.
    `dotnet build` writes straight into `%APPDATA%\OuterWildsModManager\OWML\Mods\<uniqueName>`.
- **Guest:** Balatro **1.0.1o** with lovely. This install had the older `version.dll` build; current lovely ships
  `winmm.dll` (see `../balatro/five-nights-at-balatros.md`).
  - The patch is `Mods/BalatroWilds/lovely.toml` plus `bridge.lua`, loaded from Balatro's save directory with
    `love.filesystem.load`. LÖVE mounts `%APPDATA%\Balatro` for reading, so a mod's Lua file can be loaded by
    relative path.
  - Steamodded was installed but isn't needed.
- **Reading the code:**
  - `ilspycmd` 9.1. The 11.x tool package refused to install on SDK 9.0.310 ("format version is higher than
    supported").
  - Balatro's Lua source comes from `unzip Balatro.exe`.
  - Both were kept outside any repo.
- **Single-player, offline.** Nothing leaves the machine.

## Route and why
Frame compositing, the picture-transport passthrough of `techniques/choosing-a-mashup-route.md`.
- The user wanted *real* Balatro playable, so both games run.
- A card game needs only a picture one way and a mouse the other. Nothing in Outer Wilds' world has to reach
  Balatro.
- It's the same shape as `games/outer-wilds/real-minecraft-running-inside-outer-wilds-passthrough-frame-.md`, but
  simpler: a fixed screen instead of a placed surface, no camera pose, no depth.
- **Transport:** one Windows named file mapping, `Local\BalatroWilds`. Both sides open it:
  - Outer Wilds with P/Invoke `CreateFileMappingW` and `MapViewOfFile`;
  - Balatro through LuaJIT FFI.
  It holds a 64-byte header plus one 960x720 RGBA8 frame behind a seqlock.
- **Not taken:**
  - **Window capture of Balatro** (Windows Graphics Capture or PrintWindow): WinRT capture from Unity 2019's
    Mono is painful, a minimized OpenGL window can't be read by BitBlt, and it would capture the OS cursor
    rather than the game's.
  - **WebSocket/UDP:** a ~2.7 MB frame 60 times a second has no reason to go through a socket on one machine.

## How the game works (what we had to learn)
**Outer Wilds (host)**
- **Landing view:**
  - `ShipCockpitController.EnterLandingView` (private) points the player camera down at the console screen
    (pitch -48.5°, FOV 24 over 0.5 s).
  - `LandingCamera.mode` is hard-coded to `Double`. The player camera stays on, and the `LandingCamera`'s
    `OWCamera` renders into its private `_targetTexture`.
  - That texture is a **1024x1024 ARGB32** RenderTexture, while the camera's aspect is 4:3. The cockpit
    screen's material stretches it back to 4:3, so content authored at 4:3 and blitted to fill the square
    displays correctly.
  - Disable `landingCam.owCamera` every `LateUpdate` while your content is up, or the landing camera
    overwrites it.
  - Restore with `owCamera.enabled = landingCam.enabled`.
- **The cockpit's own CRT/vignette material still applies** to whatever you put in the texture. Balatro looks
  like a landing-camera feed for free.
- **Taking the controls:**
  - `ShipCockpitController.Update` returns early unless the input mode includes `ShipCockpit|LandingCam`.
  - `OWInput.ChangeInputMode(InputMode.None)` therefore freezes thrust, look and exit while keeping the
    landing view.
  - `OWInput.RestorePreviousInputs()` gives everything back.
  - The cursor stays locked. Read `Mouse.current.delta` and the button states from the Input System and drive
    a virtual cursor.
- **Seating the player and entering the view from a test script:** reflection-invoke
  `ShipCockpitController.OnPressInteract` (what E at the seat does), then `EnterLandingView`.
- **Unity stops updating Outer Wilds when it loses focus** (`Application.runInBackground` is false). Anything
  that steals focus pauses the host. Set `runInBackground = true` while the guest is up, and restore it after.

**Balatro (guest)**
- **The frame:** `Game:draw` renders the whole frame into `G.CANVAS` (window size × `G.CANV_SCALE`), then draws
  it through the `CRT` shader to the screen or `G.AA_CANVAS`.
  - Drawing `G.CANVAS`, letterboxed and scaled, into your own 960x720 canvas and reading it back with
    `Canvas:newImageData()` + `ImageData:getFFIPointer()` + `ffi.copy` costs little.
  - Balatro stayed at ~144 updates/s while publishing ~48-60 frames/s.
- **The cursor:** `Controller:set_cursor_position` reads `love.mouse.getPosition()` in window coordinates.
  - Override that function while bridged.
  - Feed clicks to `love.mousepressed(x, y, 1)` and `love.mousereleased(x, y, 1)` from a `love.update`
    wrapper.
  - Call `love.mousemoved` on moves so the HID mode stays "mouse".
- **The cursor sprite:** in mouse mode `Controller:update` hides `G.CURSOR` because the OS cursor is used. The
  OS cursor is not in `G.CANVAS`, so set `G.CURSOR.states.visible = true` *after* `G:update`. Balatro's own
  cursor sprite then appears in the published frame at the forwarded position.
- **A safe hook point** for a lovely pattern patch is the line `G:start_up()` inside `love.load`. At that point
  `love.update` and `love.draw` exist and can be wrapped.

## Build steps
The code is not published yet; everything needed to rebuild it is described below (about 600 lines of C# and Lua).
1. **Balatro:** put `lovely.toml` + `bridge.lua` in `%APPDATA%\Balatro\Mods\BalatroWilds\`.
   - The patch inserts a `love.filesystem.load("Mods/BalatroWilds/bridge.lua")` after `G:start_up()`.
   - The bridge returns immediately unless `BALATRO_WILDS=1` is in the environment, so normal Balatro is
     unaffected.
2. **Outer Wilds:** build the OWML mod (`dotnet build -c Release`). It holds:
   - the mapping;
   - a `BalatroScreen` component that toggles on B in landing view, launches Balatro, blits frames and
     forwards the mouse;
   - a command-file dev bridge.
3. **Launching Balatro from the host** (`CreateProcessW`):
   - `STARTUPINFO.wShowWindow = SW_SHOWMINNOACTIVE`.
   - Command line `"Balatro.exe" --disable-console`.
   - Working directory = Balatro's folder.
   - An environment block built from the host's, with `SteamAppId`/`SteamGameId`/`SteamOverlayGameId` set to
     2379780, every `DOORSTOP_*` variable removed, and `BALATRO_WILDS=1`.
4. **Header words:**
   - Guest-owned (0-7): magic, version, width, height, frame seqlock, update counter, guest PID, menu-ready.
   - Host-owned (8-15): active, input counter, cursor u/v (float), buttons, heartbeat, host PID.
   - Pixels are top row first, so the host blits with scale (1,-1), offset (0,1).
5. **Lifecycle:** Balatro quits when the host *process* exits (`OpenProcess(SYNCHRONIZE)` +
   `WaitForSingleObject(h, 0)`, checked once a second). The host relaunches Balatro if it dies while the toggle
   is on.

## Verification
**Oracles:**
- **A stand-in host** (Python `mmap` with `tagname="Local\\BalatroWilds"`). It launches bridged Balatro without
  Outer Wilds, saves frames as PNG, and clicks by writing the input words. This proved the guest on its own:
  - intro and main-menu frames;
  - letterboxing;
  - the cursor sprite drawn at the sent position;
  - a click on PLAY opening the run-setup panel;
  - shutdown when the host exits.
- **In Outer Wilds, a mod-side command file** (`dev_commands.txt` → `dev_log.txt`, after
  `techniques/driving-a-game-from-a-mod-side-command-file-lab-profile-wake.md`) on a new lab profile:
  - steps: create profile → load SolarSystem → wake → seat → landing view → toggle → wait for "menu ready" →
    click PLAY → screenshot both the screen RenderTexture and the cockpit;
  - then toggle off → state dump → toggle on → state dump.
- **Results:**
  - 2,132 frames shown, 0 torn.
  - The PLAY click opened run setup on the cockpit screen.
  - After toggle off: input mode `LandingCam`, `runInBackground` restored, window focused.
  - After toggle on: the same Balatro PID.
  - The host kept updating through Balatro's start-up once the fixes below were in.

**Not verified:**
- a full hand played to the end with a physical mouse;
- the right mouse button and drag-to-reorder cards (both forwarded, neither checked);
- keyboard input (none is forwarded);
- gamepad;
- a damaged or unpowered landing camera;
- multiple monitors and DPI scaling;
- non-Steam Balatro;
- current lovely (`winmm.dll` build).

## Gotchas
1. **Balatro quit by itself a few seconds after every launch.**
   - **Cause:** Balatro's window took focus as it started. Unity stops updating an unfocused game, so the
     host's per-frame heartbeat froze, and the guest's "host gone if no heartbeat for 8 s" rule fired. The same
     happens on any alt-tab, which would throw away the player's run.
   - **Fix:** don't infer host death from a heartbeat. The host writes its PID and the guest waits on the
     process handle. Set `runInBackground` on the host while the guest is up.
2. **Forwarded mouse input never arrived, though frames flowed.**
   - **Cause:** `[DllImport("user32")]`, and also `"user32.dll"`, throws `DllNotFoundException` inside Outer
     Wilds' Mono. It probes `OuterWilds_Data/Plugins/x86_64/user32.dll`. `kernel32.dll` imports work. The
     exception fired every frame at the top of `Update`, silently skipping the input code below it. The only
     clue was the input counter in shared memory (5 writes in a minute) and 12,000 OWML log errors.
   - **Fix:** no user32 calls from the Unity side. Window work (minimize, focus handoff with
     `FindWindowA(nil, "Outer Wilds")` + `SetForegroundWindow`) moved into Balatro's LuaJIT FFI, where user32
     loads fine. Watch the OWML log after the first launch, not only your own log.
3. **The host still lost focus at every Balatro launch despite `SW_SHOWMINNOACTIVE`.**
   - **Cause:** lovely opens its own log console window, and that took focus.
   - **Fix:** launch with `--disable-console`. Focus then stayed on Outer Wilds the whole time.
4. **Scripted clicks did nothing, then the next one quit Balatro.**
   - **Cause:** with both games loading, Balatro's title intro (the logo assembling) runs well past 20 s, so a
     PLAY click landed before the buttons existed. The following click, aimed at a button of the run-setup
     panel that never opened, hit **QUIT** on the main menu.
   - **Fix:** the guest sets a menu-ready word once `G.STAGE == G.STAGES.MAIN_MENU and G.MAIN_MENU_UI` (or a
     run) is up, and scripts wait for it.
   - Hover the cursor for about a second before pressing.
   - Never script a click whose target depends on the previous click having worked.
5. **Balatro would start as Outer Wilds.**
   - **Cause:** a child process inherits the host's `SteamAppId=753640`, and Balatro's luasteam init would
     use it.
   - **Fix:** set Balatro's own ids (2379780) in the child environment. Also drop OWML's `DOORSTOP_*`
     variables, which have no business in a non-Unity child.
6. **Upside-down picture risk.**
   - **Cause:** LÖVE `ImageData` rows are top first; `Texture2D.LoadRawTextureData` treats the first row as
     the bottom.
   - **Fix:** flip in the blit (`Graphics.Blit(tex, rt, new Vector2(1,-1), new Vector2(0,1))`), not on the
     CPU.
7. **Stale OWML `gamePath`.**
   - **Cause:** `OWML.Config.json` still pointed at an old `C:` install after the game moved to another
     library.
   - **Fix:** OWML's game finder logged "Game found in D:/..." and launched anyway. The path was corrected
     by hand, with a backup.

8. **A script-seated player suffocated in space, and the screen's look changed between sessions.**
   - **Cause:** seating by reflection (`OnPressInteract`) from outside skips `HatchController.OnEntry`, so
     `EnterShip` never fires, `PlayerState.IsInsideShip()` stays false, and sitting removes the helmet. The
     cockpit was also lit as "outside" (dark, blue). That lighting is what had given the screen its tint and
     scanlines: the screen is a `Standard` material (`LandingCamScreen`) taking the texture as albedo and
     emission with a `_DETAIL_MULX2` detail map. In a normally lit cabin even the vanilla feed is flat grey.
   - **Fix:** in tests, warp into the cabin and invoke `HatchController.OnEntry(Locator.GetPlayerDetector())`
     before seating, and check `IsInsideShip()`.
   - Draw any "monitor" look into the guest frame itself (a small LÖVE shader), not through the cockpit's
     lighting. `LandingCamera._landingCamBlitMaterial` only greys the guest picture.

## Assets
None. Every pixel on the screen is Balatro's own frame, rendered live by the user's copy of Balatro.

## Cost and time
One session, about 1 h 45 min from install to verified, with six Outer Wilds launches.

## Open questions
- **Keyboard forwarding:** Balatro is mouse-first, but Escape for its pause menu and number keys would help.
  Outer Wilds' own Escape handling in `InputMode.None` needs checking.
- **Showing it in more places:** the same texture could go on a world-space screen (the probe launcher, a
  Nomai screen) with the compositing pass from the Minecraft note.
- **Shared audio:** Balatro's sound plays at full volume from its own process; ducking it with distance or
  ship state would need volume over the bridge.
