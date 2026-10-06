---
name: game-automation
description: Launch, see and drive a real game so an agent can test its own mods. Covers launching via Steam or the exe, windowed mode at a fixed size, screenshots of the game window (GPU-safe capture), clicking and typing into menus, holding keys, relative mouse, crash-reporter cleanup, killing by PID, reading logs, scripted test scenes, and an in-game JSON bridge that lets an agent observe and act. Windows-first (also from WSL), with notes for Linux and macOS. Use when a mod must be verified in game, when navigating menus automatically, or when building a repeatable test or demo scene.
---

# Game automation: the agent's hands and eyes

The real game is the oracle. The loop is launch → navigate → set up the scene → act → **screenshot and read
logs** → decide. Build it once per game, then every change you make can be checked in a minute.

## Windows (native or from WSL): `um win`
```bash
um win setup                                   # once: PowerShell tools + an ffmpeg with gfxcapture, picks NVENC/AMF/QSV/x264
um win ps                                      # windowed processes: pid, name, title
um win launch --steam 105600                   # or: um win launch "C:\Games\Foo\Foo.exe" -- -windowed
um win shot --exe Terraria.exe shot.png --scale 0.33   # full frame + a 1/3 copy that's cheap to look at
um win drive --proc Terraria "focus" "click 640 360" "key 0x1B" "type hello" "hold 0x44 1500"
um win drive --proc Terraria idle              # seconds since the user last touched mouse/keyboard
um win kill <pid>                              # exact PID only
um win reg get "HKCU\Software\..."             # registry (reg set backs the key up first)
```
From Python (for longer scripts), `from um.win import Drive, shot, Recorder`, then `d = Drive("AoE2DE_s")`,
`d.focus()`, `d.click(x, y)`, `d.key("0x0D")`.

**WinDrive commands** (`um/ps1/WinDrive.ps1`; stdin protocol, one reply per line). Coordinates are in
the game window's **client area**.
- Mouse: `move x y`, `click x y [right]`, `mdown`/`mup`, `drag x0 y0 x1 y1`, `rel dx dy` (FPS cameras /
  raw input), `wheel 120`.
- Keyboard: `key <vk> [tap|down|up]`, `hold <vk> <ms>`, `type <text>`, `scanmode on` (DirectInput /
  raw-input games that ignore virtual-key events).
- Window: `focus`, `rect`, `size <w> <h>` (sets the client size), `title`, `fg`, `idle`, `untop`.
- Virtual-key codes: Esc 0x1B, Enter 0x0D, Space 0x20, W/A/S/D 0x57/0x41/0x53/0x44, F1 0x70, Shift 0x10,
  Ctrl 0x11, arrows 0x25-0x28.

**Rules of the road**
- **Never focus a game with an online mode while the human is typing.** It happened with GTA V: the agent
  focused GTA to click Story Mode, the human's keystrokes hit GTA's landing page, and GTA warned about
  "accessing GTA Online servers with an altered version". ScriptHookV blocked it; don't rely on that.
  Check `idle`, ask the human to click, and launch with the anti-cheat off so online can't start. See
  `knowledge/techniques/driving-real-games-safely.md`.
- **Input only goes to the game.** WinDrive refuses to send while another app is in the foreground. The one
  exception is when nothing is and the cursor is over the game, which windowed games cause by dropping the
  foreground on clicks.
- **The user may be at the PC.** If `idle` is under a minute, ask before driving, and keep sessions short.
  Unattended runs are fine once the user says so.
- **Screenshots cost tokens.** Look at `--scale 0.33` copies. Multiply coordinates back ×3 for clicks, and
  keep a table of menu click points in MODLOG.md, measured once.
- **Why gfxcapture:** GPU-rendered games come out black with GDI capture. gfxcapture (Windows.Graphics.Capture)
  grabs one window's real frames, even when covered. It can't capture minimized windows.
- **HDR displays:** with Windows Auto HDR on for an SDR game, captures come out washed out (2-3x brighter,
  cyan-shifted), so colours can't be judged. `um win shot`/`record` warn when it's on; turn it off for the game
  while capturing (Settings > System > Display > Graphics > the game > Auto HDR), and back on after if the user wants.

## Make the window predictable
- **Windowed mode at a fixed client size.** Every game hides this setting somewhere:
  - an ini (`[/Script/Engine.GameUserSettings]` in UE `GameUserSettings.ini`, Unity's
    `Screenmanager Fullscreen mode` / `Resolution` registry values under `HKCU\Software\<company>\<product>`);
  - a launch flag (`-windowed -w 1920 -h 1080`, Unity `-screen-fullscreen 0 -screen-width 1920 -screen-height 1080`,
    Source `-sw -w 1920 -h 1080`);
  - or the game's own registry (AoE2: `Mode Display` 0 + `Windowed Width/Height`).
  - `um win drive --proc X "size 1920 1080"` also resizes most windowed games.
- **Skip intros:** launch flags (`-skipintro`, `-nosplash`, Unity `-popupwindow`), or delete/rename intro
  videos in a **copy** of the game.
- **Jump straight in:** loader flags (tModLoader `-skipselect Player:World`), a save made for testing,
  scenario auto-load, a dev console command.
- **Background throttling:** many games throttle or pause unfocused. Find the setting (Terraria:
  `Main.instance.InactiveSleepTime = TimeSpan.Zero`; Unity: `Application.runInBackground = true`; UE:
  `t.IdleWhenNotForeground 0`).

## Better than clicking: a scripted scene or a bridge
- **Chat or console commands in your mod** give items, spawn enemies and teleport. They make tests one line
  (`/arsenal`, `/mothership`).
- **Test scenes:** a mod-side timeline (spawn waves at frame N, fire at N+30), a scenario with triggers
  (AoE2 via AoE2ScenarioParser), a dedicated test world with a pristine backup.
- **Agent bridge:** a JSON-lines socket inside the mod on `127.0.0.1` (see
  `examples/terraria-tmodloader/reference/AgentBridge.cs`).
  - Commands like `observe` (menu options or world state as text), `click <id>`, `controls`, `step`.
  - Handle every request on the game's main thread after an update, so replies are consistent.
  - Read menus generically from the UI tree, so the agent sees what a player would. Leave destructive
    buttons (delete) out.
  - An agent can then play without pixels at all.
- **Out-of-process backend:** keep the in-game part thin and put the brains outside (HTTP/file-drop). That
  pattern scales to AI NPCs and cross-game mashups.

## Crashes and cleanup
- **Crash reporters** (BugSplat `BsSndRpt64.exe`, `CrashReportClient.exe`, `UnityCrashHandler64.exe`) can
  linger and make Steam say "already running". `um win ps` to spot them, `um win kill <pid>` to clear
  them.
- Never `pkill -f` or wildcard `taskkill /IM`. The pattern can match your own shell or other apps.
- After a crash, read the loader or game log first (the mod-any-game skill lists them), then the Windows
  Event Viewer (Application log) for native crashes.

## Linux and macOS
- **Linux (X11):** `xdotool search --name "Game" windowactivate --sync key Escape`, `xdotool mousemove
  --window $W 640 360 click 1`. Screenshots: `import -window $(xdotool search --name Game) shot.png`, or
  ffmpeg `x11grab`.
- **Linux (Wayland):** ydotool + `grim`. Proton games are Windows games under Wine: launch options
  (`WINEDLLOVERRIDES`, `PROTON_LOG=1`) go in Steam.
- **macOS:** `screencapture -l <windowid> shot.png` (window id via `GetWindowID` or AppleScript),
  `osascript` / `cliclick` for input. Input and screen recording need Accessibility and Screen Recording
  permission for the terminal.
