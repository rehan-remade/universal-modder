---
kind: technique
title: "Driving real games safely: input, focus and the human at the keyboard"
tags: [automation, input, sendinput, focus, windowed-mode, crash-reporter, safety, online-guard, dpi-scaling]
date: 2026-10-01
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

## Seen in
- [Minecraft inside GTA V](../games/gta-v/minecraft-passthrough.md)
- [San Franciscans (AoE2)](../games/age-of-empires-ii-de/san-franciscans-civ.md)
- [Fal Arsenal (Terraria)](../games/terraria/fal-arsenal-tmodloader.md)
- [Black Myth: Wukong — ReShade depth dead end](../games/black-myth-wukong/reshade-depth-dead-end.md) (Gotchas 7 and 8)
