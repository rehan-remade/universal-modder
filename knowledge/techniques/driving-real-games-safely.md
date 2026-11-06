---
kind: technique
title: "Driving real games safely: input, focus and the human at the keyboard"
tags: [automation, input, sendinput, focus, windowed-mode, crash-reporter, safety, online-guard, dpi-scaling, menu-navigation]
date: 2026-10-12
agents: ["Claude Code (Opus 5.5)"]
humans: ["@rehan_shei"]
links: []
---

# Driving real games safely: input, focus and the human at the keyboard

> An agent that can launch the game, click through menus and play a test scene iterates far faster. It's
> also sharing a mouse and keyboard with a human, and some games have online modes one keystroke away.
> These rules come from real sessions, including one close call.

## When to use it
Whenever the agent sends input to a real game window.

## How
- **Input only reaches the game:**
  - send only while the game window is in the foreground (`um win drive` / WinDrive refuses otherwise);
  - windowed games may drop the foreground on click, so "nothing in the foreground and the cursor over the
    game" also counts as safe.
- **Check the human first:** `um win drive --proc <Game> idle` gives seconds since the last real input. If
  it's small, ask before driving, keep bursts short, or wait.
- **Stable coordinates:** force windowed mode at a fixed client size (registry, ini or launch flags; `size W H`
  in WinDrive). Measure menu click points once from scaled screenshots (x3 back to client coords) and keep
  them in the journal.
- **Skip the menus where you can:** launch flags into single player (tModLoader `-skipselect`), test
  scenarios, dev consoles.
- **Clean up by PID:** crash reporters, stuck ffmpeg, a hung game. Never kill by name pattern.

## Gotchas
1. **Keystrokes from the human land in the game.**
   - **What happened:** the agent focused GTA V to click Story Mode while the human was typing in another
     app. Their keystrokes hit GTA's landing page, and GTA showed "ALERT: attempting to access GTA Online
     servers with an altered version". ScriptHookV blocked the session.
   - **Fix:** never focus a game with an online mode while the human is active. Launch with the anti-cheat
     off (`-nobattleye` for GTA story mode), so online can't start at all.
2. **`pkill -f <pattern>` killed the agent's own shell.** The pattern matched the agent's own command line.
   Kill by exact PID.
3. **"Already running" after a crash.**
   - **Cause:** crash reporters (BugSplat `BsSndRpt64.exe`, `CrashReportClient.exe`,
     `UnityCrashHandler64.exe`) linger, and Steam refuses to relaunch.
   - **Fix:** list them with `um win ps` and kill them by PID.
4. **The game pauses when unfocused.** Find the engine's run-in-background switch (Terraria
   `InactiveSleepTime`, Unity `runInBackground`, UE `t.IdleWhenNotForeground 0`).
5. **The first click only highlights.** Some menus (GTA's landing page) need a second click to activate. Look
   at a screenshot after each click instead of assuming.
6. **A cinematic idle camera takes over.** GTA starts one after about 30 s without input; call
   `INVALIDATE_IDLE_CAM` every frame. Other games have attract modes too.
7. **Click coordinates are DPI-virtualised, screenshots are physical pixels.** (2026-10-01, Windows 11 at
   150% scaling, `um win drive` + `um win shot`.)
   - **Symptom:** clicking what is clearly the Add-ons tab in a ReShade overlay selected the tab next to it,
     consistently ~44 px off. Every click drifted the same amount in the same direction.
   - **Cause:** `um win drive click` goes through `ClientToScreen` in a DPI-unaware process, so its numbers
     are in the *logical* screen space, while `um win shot` / Windows.Graphics.Capture returns *physical*
     pixels. On a 2560×1600 panel at 150% the logical screen is only 1707×1067.
   - **Fix:** read the scale factor first — compare `[System.Windows.Forms.Screen]::PrimaryScreen.Bounds`
     (1707×1067) with the real resolution (2560×1600) — then `click = screenshot_px / scale`. Do not assume
     the screenshot and the click share a coordinate space just because the window is borderless fullscreen.
8. **`um win ps` dies on a Chinese-locale Windows.** (2026-10-01, zh-CN.)
   - **Symptom:** `UnicodeDecodeError: 'gbk' codec can't decode byte 0xa3 in position 264` and a Python
     traceback, from a command that has nothing to do with Chinese.
   - **Cause:** the subprocess reader decodes output with the locale encoding (GBK here) and window titles
     contain bytes GBK cannot map.
   - **Fix:** set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` in the environment before calling `um`.
     Affects `um win ps` / `shot` / `drive`.
9. **Keys sent from your own code don't register.** (2026-10-12, Etrian Odyssey 2 HD, Unity 2020.3.)
   - **Symptom:** a plugin's `SendInput` Enter was ignored, while `um win drive key` worked on the same screen.
   - **Cause:** down and up in one `SendInput` call — shorter than a frame, and the game polls key state per
     frame.
   - **Fix:** send down, sleep ~80 ms, send up.
10. **Enter works but arrow keys don't.** (2026-10-12.) **Cause:** arrows/navigation keys need
    `KEYEVENTF_EXTENDEDKEY` (0x1). **Fix:** set it for VK 0x21–0x28, Insert (0x2D), Delete (0x2E) and the right
    Ctrl/Alt (0xA3, 0xA5), as `um win drive` does.
11. **`SetForegroundWindow` silently fails for a freshly launched game.** **Cause:** Windows' foreground lock.
    **Fix:** tap Alt via `SendInput`/`keybd_event` right before it; never type if focus still isn't yours.
12. **Menu lists wrap and open on the most recent entry.** (2026-10-12, EO2 HD save list.) "Up ×12 to reach
    the top" landed on slot 7, and Down ×7 then on slot 5. **Fix:** don't count presses from an assumed
    start. Set the game's "recent item" (EO2: a byte in the system save) before boot, or read the cursor
    from a screenshot. Allow ~0.6–0.7 s per move or scroll animations eat presses.
13. **Brightness-based title detection fires on publisher logos.** They're bright too. **Fix:** require
    brightness for >3 s *and* a minimum time since launch (~30 s), and only press Enter to skip while the
    screen is dark.
14. **The shell waits for the game to exit.** (Git Bash.) `pid=$(script_that_launches_game)` hangs because the
    game inherits the output pipe. **Fix:** launch detached with output redirected:
    `(cmd //c start "" "<exe>" >/dev/null 2>&1 &)`.

## Seen in
- [Minecraft inside GTA V](../games/gta-v/minecraft-passthrough.md)
- [San Franciscans (AoE2)](../games/age-of-empires-ii-de/san-franciscans-civ.md)
- [Fal Arsenal (Terraria)](../games/terraria/fal-arsenal-tmodloader.md)
- [Black Myth: Wukong — ReShade depth dead end](../games/black-myth-wukong/reshade-depth-dead-end.md) (Gotchas 7 and 8)
- [EO1 inside EO2 HD](../games/etrian-odyssey-2-hd/etria-inside-eo2-bepinex-protected-il2cpp.md)
