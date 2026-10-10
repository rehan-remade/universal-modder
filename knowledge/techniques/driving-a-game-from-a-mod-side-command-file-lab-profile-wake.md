---
kind: technique
title: 'Driving a game from a mod-side command file: lab profile, wake-up and oracle without touching input'
status: working
agents:
- Claude Code (Opus 5.5)
humans:
- charlystereo
date: '2026-10-10'
links: []
tags: [oracle, test-harness, automation, dev-bridge, unity, owml, outer-wilds]
---
# Driving a game from a mod-side command file: lab profile, wake-up and oracle without touching input

> Put a tiny command interpreter inside the mod: the agent writes lines to a file, the mod runs them in order on
> the game's main thread and appends results to a log. It gets an agent from the title screen to a repeatable test
> in a lab save, and back, about 25 times in a session, without moving the user's mouse or keyboard.

## When to use it
- The game needs menus, prompts or a save before anything testable happens.
- You need exact, repeatable setups (aim here, fire, walk 1 s, drop the ship over that portal) and numbers, not
  just screenshots.
- The user is at the PC, or input injection is unreliable for the action (sub-frame clicks, raw input).
- Keep a short real-input pass at the end (with the user's OK) to prove the actual bindings.

## How
- **Switch:** off unless a marker file exists (`dev.enabled` in the mod folder), so release builds behave normally.
- **Protocol:** read `dev_commands.txt` each frame, enqueue its lines, delete it; run them from a coroutine. Results,
  errors (with stack) and every `>` command go to `dev_log.txt` with time and frame number. The agent polls the log
  with `until grep -q "<marker>" dev_log.txt; do sleep 1; done`, then reads screenshots it requested.
- **Flow control:** `wait <s>` (realtime), `waitfor <condition> <timeout>` (title ready, profiles ready, scene loaded,
  wake prompt waiting, player has control), and background commands (`trace <s>` logging positions and velocities at
  20 Hz in each portal's frame while the next commands run).
- **Getting into the game (Outer Wilds 1.1.16):** `waitfor profiles` (`StandaloneProfileManager.isInitialized` and a
  `TitleScreenManager` exists) → `profile PortalLab` (TryCreateProfile or SwitchProfile) → `resume` (the title's
  private `_resumeGameAction`: `SetSceneToLoad(GAME)`, `ConfirmSubmit` by reflection to skip "are you sure?", then wait
  for `LoadManager.IsAsyncLoadComplete()` and call `EnableAsyncLoadTransition()` because the hidden button's Update
  normally does it) → `waitfor wakeready` → `wake` (exactly what `PlayerCameraEffectController` does when the
  "Wake up [E]" prompt is answered: clear `_waitForWakeInput`, unpause, remove the prompt, call `WakeUp`) →
  `waitfor control`.
- **Acting:** call the mod's own methods (equip, fire), set view directly (body yaw + `SetDegreesY`), `face` a target,
  `walk` (set velocity along the ground relative to the ground body, only while grounded), warp bodies (player, ship
  over a portal), launch the scout through its private method, `reload` (what a loop end does).
- **Observing:** `dump` (scene, input mode, tool, positions relative to points of interest, counters),
  `ScreenCapture.CaptureScreenshot` (includes IMGUI), `contacts` (colliders touching the player capsule),
  `skyscan` (ground spots with open sky, via sphere casts from above).
- **Hygiene:** a separate lab profile; the user's save checked untouched by timestamp; game killed by exact PID
  between builds (`um win kill`); contact sheets of screenshots at reduced size.

## Gotchas
1. **One private member breaks the whole command switch.** **Cause:** Mono checks field access when it JITs a method,
   even against publicized references. **Fix:** reflection for private members; keep the big switch free of them.
2. **"Scene loaded" ≠ "player can act".** **Cause:** the wake-up prompt and fade keep input at None. **Fix:** wait for
   the input mode, not the scene.
3. **The bridge's own test motion was the bug.** A synthetic walk that added speed every step while airborne launched
   the player at 180 m/s and looked like a mod bug. **Fix:** emulate the real control's rules (grounded only, relative
   to the ground body) and log velocities, not just positions.
4. **Short injected clicks are missed.** **Cause:** the game polls button state per frame. **Fix:** hold ≥ 60 ms
   (`um win drive ... "click x y"`), and know the game's real default bindings before blaming the mod.

## Seen in
- `games/outer-wilds/portal-2-portal-gun-in-outer-wilds-1-1-16-owml-see-through-p.md`
