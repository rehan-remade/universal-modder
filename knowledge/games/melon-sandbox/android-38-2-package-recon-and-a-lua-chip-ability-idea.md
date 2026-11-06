---
kind: game
title: Android 38.2 package recon and a Lua Chip ability idea
game: Melon Sandbox
games_also: []
game_version: "38.2 (versionCode 445; armeabi-v7a split; inspected as an APKPure XAPK, never installed)"
platform: other
engine: unity-il2cpp
route: other
tools: ["melon-lua 5.2.5 (third-party simulator only)", "Python 3.12", "Android SDK command-line tools"]
anti_cheat: "Not assessed; the package was not installed or run"
status: idea
agents: ["GitHub Copilot (model not recorded)"]
humans: []
date: "2026-10-10"
links:
- "https://www.gamedeveloper.com/press-release/code-your-way-to-chaos-with-the-lua-chip-in-ragdoll-sandbox-game-melon-sandbox-"
tags: ["android", "il2cpp", "lua-chip", "melsave", "unverified"]
---
# Android 38.2 package recon and a Lua Chip ability idea

Melon Sandbox on Android is a Unity IL2CPP build, so desktop Mono/MelonLoader routes don't apply. The game
ships its own scripting surface instead: the Lua Chip, added in update 36.0. This note records what the 38.2
package shows and an untested idea for a scripted ability (a fire button that launches a purple orb item along
an aim joystick, plus a time-scale slider) built from the game's own Lua Chip. Nothing here ran in the game:
it was never installed or launched.

## Setup
- **Use the Google Play build.** The package inspected for this note was an APKPure XAPK of 38.2, and a mirror
  build isn't guaranteed to be unmodified. To inspect the official APKs, install the game from Google Play on
  your own phone or emulator, run `adb shell pm path com.studio27.MelonPlayground`, then `adb pull` each path.
- What the inspected package shows: package `com.studio27.MelonPlayground`, version 38.2 / versionCode 445, a
  base APK plus an `armeabi-v7a` configuration split, min SDK 25 in the manifest, and Unity IL2CPP metadata
  (`global-metadata.dat`) with no managed C# game assemblies.
- Host: Windows 10 Pro. No Android device or usable emulator was available: Android Studio required elevation,
  and the command-line SDK could not retrieve package manifests. The package was inspected as an archive only,
  never installed, launched or modified.

## Route and why
Start from the game's own Lua Chip. PlayDucky's press release of 21 July 2026 (in `links`) calls the Lua Chip
the cornerstone of update 36.0, available on iOS, Android and browser: players paste Lua into the chip, and it
can modify any object connected to it. No loader is needed. Place a chip in a sandbox, connect the objects it
should drive, paste the Lua, and test it in the game.

Not taken:
- **IL2CPP code loaders.** The Unity playbook and the knowledge base have no Android IL2CPP loader route, and
  desktop Unity loader advice doesn't carry over to this ARMv7 build.
- **Patching the APK.** Don't replace, patch or re-sign it.
- **Generating a save offline.** Whether the Lua Chip and the UI controller are free in the game isn't known,
  so a generated save could hand paid content to a free install. Build in the game instead.

## How the game works (what we had to learn)
- The Android package is IL2CPP: metadata, not managed assemblies a desktop Mono/MelonLoader patch could load.
- The `.melmod` examples looked at describe spawnable items (assets, visual and collider properties). They hold
  no script, so an ability's logic has to live in a Lua Chip. People Playground C# code doesn't port.
- The Lua Chip exists from update 36.0 (press release above).
- Everything below comes from a third-party Python package, `melon-lua` 5.2.5, which models the chip API and
  runs Lua in a standalone simulator. None of it was checked against the game:
  - chip functions `spawn.getMods()`, `spawn.createMod()`, an `OnSpawned` callback, entity velocity and gravity
    setters, and `env.setTimeScale()` (clamped to 0-2);
  - `.melsave` files modeled as a document of placed objects (for example a Lua chip and a UI controller), the
    wires between them, and app-version metadata (the package writes 36.0).

## Build steps
Nothing was built in the game. The planned first slice, untested:
1. Install Melon Sandbox from Google Play (36.0 or later for the chip). Check that the Lua Chip and any UI
   controller are available without a purchase, and write down which.
2. In a sandbox, place a Lua Chip and connect a fire button, an aim joystick and a slider, if the game offers
   them.
3. Paste Lua that:
   - looks up a mod item whose name contains "Hollow Purple" (falling back to "Purple");
   - spawns it on a rising fire-button edge;
   - when it spawns, sets its velocity along the aim direction and its gravity to zero;
   - maps the slider to the time scale.
4. Record what happens, including failures and their causes. If it fails, stop there rather than patching the
   APK.

## Verification
Nothing ran in the game. The ability's Lua ran only in `melon-lua`'s standalone simulator, against a made-up
`hollow_purple_test` catalog entry: it spawned a mock projectile with the requested velocity and zero gravity,
and the slider set the simulator's time scale to 1.5. With no Purple entry it logged a warning and spawned
nothing. The simulator is not the game.

Not verified:
- that 38.2 runs on a device or emulator;
- whether the Lua Chip and the UI controller are free or paid;
- the chip's real API (the function names and callback above come from the third-party package);
- whether imported `.melmod` items are visible to a chip;
- the real `.melsave` format and its version handling;
- visuals, collision, effects and performance.

## Gotchas
1. **No managed game DLLs to patch.** **Cause:** this Android package is IL2CPP and contains metadata rather
   than managed game assemblies. **Fix:** don't apply desktop Mono/MelonLoader instructions as if they were an
   Android route; use the game's Lua Chip.
2. **A purple `.melmod` is only a visual/spawnable item.** **Cause:** the format holds item data, not ability
   code. **Fix:** put the firing logic in a Lua Chip that spawns the item.
3. **A third-party save builder reports success without proving the game will load it.** **Cause:** its
   templates write app version 36.0, and rewriting a version field doesn't update the format or validate it.
   **Fix:** build and save in the game itself.
4. **Faster simulation is not an FPS optimization.** **Cause:** time scale advances the simulation faster and
   can add CPU work. **Fix:** treat the slider as a gameplay-speed experiment, not a performance fix.
5. **A simulator run is not a game test.** **Cause:** the test seeded a synthetic catalog name, and
   `createMod` returned a generic mock entity. **Fix:** verify catalog lookup, spawn callbacks, projectile
   appearance and interaction in the real game before claiming an ability.

## Assets
No new assets were generated or included. The idea assumes a visual-only purple orb `.melmod` item; none was
available here, so no exact item name is assumed.

## Cost and time
N/A.

## Open questions
- Does the Lua Chip run on 38.2 for Android, and are the chip and the UI controller free?
- What are the chip's real function names and callbacks, and can a chip see imported `.melmod` items?
- Does `env.setTimeScale` (or the game's equivalent) exist in the chip API?
