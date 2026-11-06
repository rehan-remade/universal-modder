---
kind: game
title: "Modding surface of Star Wars: The Force Unleashed (PC): a dinput8 plugin loader, a Lua bridge, and the engine's dormant dev features"
game: "Star Wars: The Force Unleashed"
games_also: []
game_version: "Ultimate Sith Edition PC 1.2.94564, Steam (SWTFU.exe x86, SteamStub-wrapped)"
platform: windows
engine: native
route: native-hook
tools: ["REA 6.7.0 + Ghidra 12.1.4", "MSVC 14.44", "Python 3.12"]
anti_cheat: "none (single-player); SteamStub DRM on SWTFU.exe left in place: exe code read only from private runtime memory dumps kept outside any repository"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-24
links: ["https://www.nexusmods.com/starwarstheforceunleashed/mods/35", "https://github.com/ThirteenAG/Ultimate-ASI-Loader", "https://github.com/morluto/rea", "https://github.com/NationalSecurityAgency/ghidra"]
tags: [lua, asset-override, hot-reload, config, euphoria, ronin-engine, steamstub]
---

# Modding surface of Star Wars: The Force Unleashed (PC)

> Plugins (DK_*.dll) load through a dinput8.dll proxy loader, and a named-pipe bridge runs Lua inside the game for
> testing and tooling. This note records the engine facts that matter to the next modder: the Lua layer, asset
> hashing and packs, the config file trap, and developer features left in the retail build. The loader, the bridge,
> and asset overrides run in game every day in this project; the dormant features and the hooks learned from another
> mod are marked as not run here.

## Setup
- Steam build 1.2.94564, Windows 11. The game folder holds SWTFU.exe and four unencrypted native DLLs:
  ScumLibLEC_Retail.dll (asset catalog, packs, reflection), AWL_Release.dll ("Aspyr Windows Layer": Config.xml, Log.txt,
  crash filter), libScumEuphoria_win32_release_DLL.dll (NaturalMotion Euphoria ART + Havok) and mss32/binkw32. There is
  also a WPF launcher (SWTFU Launcher.exe, .NET + SlimDX).
- All the DLLs above ship with PDB paths and many exports, so they decompile well and their names come through.

## Route and why
- SWTFU.exe .text is SteamStub-encrypted on disk, so static tools see only the stub.
- We neither decrypt nor patch the exe file. A dinput8.dll proxy loads the plugins after the stub has decrypted .text
  in memory (trigger: the first exe call through a hooked KERNEL32 IAT slot such as GetStartupInfoA). Plugins
  byte-pattern-scan the live image.
- For static work on exe code, dump .text, .rdata and .data from your own running game into a private folder outside
  any repository, and disassemble the dumps.
- Data mods: override assets at the ScumLib import AssetCatalog::LoadRawAssetData (the exe's only raw asset read path).
  The companion note [Fixing solid-black scenery](black-scenery-lighting-groups.md) is a worked data mod on this
  route: markerset overrides that add lighting groups, verified in game.

## How the game works (what we had to learn)
- **Lua 5.0 drives gameplay.** There are about 2147 native bindings (ronin., game., player., ai., camera., display.,
  vfx., ...), and the standard libraries are complete (debug, io, os).
  - _G is strict: reading a missing global raises an error.
  - A Lua error outside pcall exits the game. Native code touching Lua must take the engine's Lua critical section and
    use lua_cpcall.
  - Any level starts from the front end with `ronin.LoadWorld("<name>")`, with names from `PC_LevelSelectList.txt` in
    the game folder. `ronin.AbortLevel()` returns to the front end.
- **The game tick pauses.** Game::Tick, and with it every command queued for the game thread, does not run during
  FMVs (the front end plays an attract video about every 69 s) or level loads.
- **Asset names are CRC32-hashed.** ScumLib `stricrc32`: the standard table, init 0, no final xor. Each byte is
  case-folded with `&0xDF` and `\` is mapped to `/`.
- **Packs.** Level packs are `.lp` ("kaPA" v5). ExternalPackList.txt lines read `%41s %15s 0x%x includes %15s`; a
  leading byte with bit 7 set means the whole file is bit-NOT encoded. The game root is also scanned for `*DLCList.txt`.
- **Dormant loose-file mode.** ScumLib has a "Sandbox" mode: `AssetCatalog::TryLoadAssetFromSandbox` checks
  `Sandbox\<name>` for every asset load, but returns at once unless the byte gpAssetCatalog+0x2518 is set (retail
  initialises it to 0).
  - The exe polls `Sandbox\SandBoxVersion.txt`. A higher number calls `ReloadAllSandboxAssets`, which hot-reloads
    meshes (.gto), materials, textures (.dds) and .vrd.
  - Not yet proven in game.
- **Config.xml.** It lives at `%LOCALAPPDATA%\Aspyr\Star Wars The Force Unleashed\Config.xml` as `<s id="K">v</s>`.
  - Every AWL process (the launcher and the game) loads the file once at start, then rewrites all of it from that
    snapshot on exit, on crash, and just before the launcher starts the game. External edits made while one of those
    processes is alive get overwritten.
  - Windowed mode is a hidden number key, `VideoWindowed`. The text "TRUE" parses as 0, which means fullscreen.
  - The exe reads numbers through the AWL export `?GetConfigNumber@Win@Aspyr@@YANPBDN_N@Z` (the result is a double in
    ST0). The third-party [SWTFU Advanced Configurator](https://www.nexusmods.com/starwarstheforceunleashed/mods/35)
    mod (Gametism) hooks it to answer `VideoWindowed` and other keys without touching the file. Not run here.
    PCGamingWiki points to the same mod for windowed and borderless mode, FOV, 60 FPS and skipping the intro videos.
- **Movies.** The same Configurator mod returns NULL from `binkw32!_BinkOpen@8` to skip the startup and attract
  movies. That would make boots faster and remove the attract-video tick stalls. Not run here.
- **Menus** are Anark Gameface. Lua can run menu script through `ui.doscript`.
- **Engine debug features left in retail:**
  - A `tweaks` Lua table of about 61 graphics knobs mapped to raw addresses (HDR, bloom, fog, DOF, motion blur,
    shadows, clip planes, framerate lock).
  - `camera.SetFlyMode`, `ronin.SetTimeScale`, `ronin.SetDebugDraw`, and the `display.Draw*` world-overlay API.
  - `debug.ProfileNextFrame` (Lua profiler) and `ronin.DumpLoadedAssets`.
  - The MicroConsole class is compiled in but never allocated, so it is dead code.
- **Euphoria.** The ARTContext is built with maxAgents 50, which is a hard cap on concurrently simulated ragdoll
  characters. Behaviour and parameter definitions are pack XML (Behaviors_*.xml), so they can be modded as data.
- **Reflection in ScumLib.** It can enumerate every definition type (`DefinitionEnumerateTypes`), get or set fields
  by dotted path, dump any definition to XML (`DefXMLWriteFile`), and list the enum symbol maps.

## Build steps
1. Build an x86 `dinput8.dll` proxy that exports `DirectInput8Create` and forwards it to the system dinput8.dll.
2. DllMain runs before the stub has decrypted .text, so do nothing there except hook a few early KERNEL32 IAT slots of
   SWTFU.exe (GetSystemTimeAsFileTime, which the CRT startup calls first, GetStartupInfoA, GetCommandLineA). On the
   first call from the exe's own code, load every `DK_*.dll` from the game folder. DirectInput8Create is the fallback
   trigger. [Ultimate ASI Loader](https://github.com/ThirteenAG/Ultimate-ASI-Loader) works the same way by default
   (its README: plugins load when the game's own code starts running, also behind a protection stub), so it is a
   ready-made alternative for `.asi` plugins; it wasn't tried on this game.
3. Plugins find exe code by byte patterns, never fixed addresses, and log clearly when a pattern is missing.
4. For loose-file asset mods, hook the exe's import of `AssetCatalog::LoadRawAssetData` and serve
   `DK_Mods\<mod>\<asset path>` when the file exists. Chain any hook that is already in the slot.
5. For tooling, redirect WinMain's Game::Tick calls through a frame hook, so plugins run work on the game thread between
   frames. A plugin then opens a named pipe and runs its commands there (Lua inside lua_cpcall under the engine's Lua
   lock, memory reads, screenshots).
6. Copy dinput8.dll and the plugins next to SWTFU.exe and start the game normally.

## Verification
- Ran in game (scripted scenario tests driven by the bridge, in a background windowed game): the loader, the bridge,
  Lua calls, the `tweaks` bindings, asset overrides, level starts from Lua.
- Static analysis only: the Sandbox mode, the Config.xml snapshot-overwrite explanation, the Euphoria limits and the
  debug input maps.
- Read from another mod, not run here: the GetConfigNumber hook and the Bink skip.

## Gotchas
1. **Symptom:** Ghidra or REA shows only a few functions in SWTFU.exe. **Cause:** SteamStub-encrypted .text. **Fix:**
   analyse private runtime memory dumps and the unencrypted DLLs. Do not decrypt the exe file.
2. **Symptom:** Config.xml edits for windowed test runs revert, and the game sometimes starts fullscreen.
   **Cause (inferred):** another AWL process rewrites its startup snapshot of the file. **Fix:** answer the config
   getters from a hook in the test process instead of editing the file (the Configurator mod's method; not run here).
3. **Symptom:** the game exits silently after a Lua call. **Cause:** a Lua error outside pcall, or a missing global
   under strict _G. **Fix:** wrap calls in pcall and test globals with rawget.
4. **Symptom:** a mod's asset override stops working after another mod hot-reloads. **Cause:** two plugins hook the
   same LoadRawAssetData import slot. **Fix:** chain whatever hook is already there, and refuse to unload while
   re-hooked.
5. **Symptom:** commands sent to the game thread time out at random on the front end or during a load. **Cause:** the
   game tick does not run during FMVs (the attract video starts about every 69 s) or level loads. **Fix:** retry after
   the movie or the load.
6. **Symptom:** after about 8 level loads in one session the game dies with an unknown exception in Log.txt.
   **Cause:** the 32-bit process runs out of address space. **Fix:** restart the game between batches of level loads.
7. **Symptom:** `ronin.LoadWorld(<current level>)` does nothing. **Cause:** loading the level that is already loaded
   is a no-op. **Fix:** `ronin.AbortLevel()` to the front end first.

## Open questions
- Do the exe's per-type loaders read the Sandbox path (load mode 8) correctly in retail?
- Are the shipped `debug` / `debugmenu` input maps usable in retail?
