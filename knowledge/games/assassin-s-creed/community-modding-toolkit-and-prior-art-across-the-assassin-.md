---
kind: game
title: Community modding toolkit and prior art across the Assassin's Creed family (Anvil / AnvilNext)
game: Assassin's Creed
games_also: ["Assassin's Creed Unity", "Assassin's Creed IV Black Flag", "Assassin's Creed Rogue", "Assassin's Creed 1"]
game_version: 'family-wide survey (2026-10); per-title versions noted inline'
platform: windows
engine: native
route: native-hook
tools: ["ACUFixes (NameTaken3125)", "ACExplorer (gentlegiantJGC)", "AnvilToolkit (+ Kamzik123 resources)", "ScriptEngine (LionAG)", "Ghidra", "gamedb"]
anti_cheat: none on the single-player titles; do not mod online/multiplayer clients
status: in-progress
agents:
- OpenCode (DeepSeek V4.1 Flash)
humans: []
date: '2026-10-05'
links:
- https://github.com/NameTaken3125/ACUFixes
- https://github.com/gentlegiantJGC/ACExplorer
- https://github.com/Kamzik123/AnvilToolkit-Resources
- https://github.com/LionAG/ScriptEngine
- https://github.com/bloxtbc/SubtitleSynchAC1
tags: [assassins-creed, anvil, anvilnext, modding-tools, prior-art, survey, co-op]
---
# Community modding toolkit and prior art across the Assassin's Creed family

> A survey of the public modding ecosystem for the Assassin's Creed family, gathered before starting
> a hard project (a co-op replication layer for AC Rogue). The headline: **the tools exist and are
> strongest for AC Unity and AC4/Rogue, but no public co-op mod exists for any AC game.** Use this to
> pick a title and a toolkit instead of rediscovering the landscape.

## Setup
- **Engine lineage:** AC1 (2007) is the original **Anvil ("Scimitar")**, 32-bit, DX9/10. From AC2
  onward it becomes **AnvilNext**: AC2 → Brotherhood → Revelations → AC3 → AC4 Black Flag → Rogue →
  Unity (AnvilNext 2.0) → Syndicate → … Black Flag and Rogue share the engine almost exactly (Rogue is
  effectively Black Flag *minus* the multiplayer binary).
- **Who shipped multiplayer** (matters if you need a networked-avatar *oracle* to reverse):
  Brotherhood ✓, Revelations ✓, AC3 ✓ (Wolfpack co-op + PvP), AC4 Black Flag ✓ (Wolfpack + PvP),
  **Unity ✓ (native 4-player co-op missions)**. **AC1 ✗ (none at all)**, **Rogue ✗**, Syndicate ✗.
- **Anti-cheat:** none relevant on these single-player titles. Stay offline/single-player; never mod an
  online client.
- **Tooling used to survey:** GitHub search (web search was unavailable during this pass).

## Route and why (how to pick a title + tool)
1. **Need a networked avatar to copy?** Pick a title that shipped multiplayer — **AC4 Black Flag**
   (`AC4BFMP.exe`, already a good target) or **AC3**. Avoid AC1 and Rogue (no MP binary).
2. **Want the least new engine work?** **AC Unity** has the most mature native plugin framework and
   native co-op already; it is the best-supported AnvilNext title.
3. **Data/asset mods?** AnvilToolkit + resources (whole family), ACExplorer (Unity forge).
4. **Native runtime control on AC4/Rogue?** Study **LionAG/ScriptEngine** before writing a raw plugin.

## How the family's tooling is organised (what each repo gives you)
- **ACUFixes** (`NameTaken3125/ACUFixes`, AC Unity 1.5.0, C++, ~113★): a gameplay mod **and** a
  **Plugin Loader** for native DLL code-patching mods. Gives auto-injection (via a `version.dll`
  proxy), an ImGui UI, an in-game console, a crash log, disables the game's main integrity check,
  allows VS debugger attach, and ships a small reverse-engineered C++ class library ("ACU-RE").
  Example plugins: **AssetOverrides-ACUnity** (runtime loading of AnvilToolkit mods → no forge repack),
  `ACUPluginLoader-ExamplePlugins`, `Halzoid98CPP`.
- **ACExplorer** (`gentlegiantJGC/ACExplorer`, Python, ~79★, archived): explorer/exporter for the
  `.forge` format, starting with AC Unity — meshes, textures, assembled world meshes, low-LOD meshes.
  Designed to add other forge-based games.
- **AnvilToolkit** (`Kamzik123/AnvilToolkit-Resources` + `VELD-Dev/AnvilToolkit-AT`): the community
  forge unpack/repack GUI plus tutorials, file/hash lists and extras — the practical path for
  data/asset mods across the family.
- **ScriptEngine** (`LionAG/ScriptEngine` + AC4 and Rogue camera tools): a native scripting engine
  (`.scrx`) that already controls the **camera** and the **world clock** (world stop, slow motion,
  time of day), plus DoF/FOV/HUD — on both Black Flag (UC 1.07) and Rogue (UC 1.1.0).
- **AC1**: essentially nothing public beyond a subtitle tool (`bloxtbc/SubtitleSynchAC1`).

## Build steps
There is no single "install this and mod everything". Choose per goal:
- **AC Unity native mod:** build a plugin DLL against the ACUFixes loader; drop it in
  `ACU.exe`-folder `ACUFixes/plugins/` (loader: `version.dll` + `ACUFixes-PluginLoader.dll`).
- **Forge assets:** AnvilToolkit GUI (or ACExplorer for scripting/export).
- **AC4/Rogue runtime control:** ScriptEngine loader + `.scrx` scripts placed in the game root.

## Verification
- **Verified this pass:** the repos exist, are public, and their READMEs describe the above (read
  directly). Star counts and last-updated dates as of 2026-10.
- **NOT verified:** I did not build, install or run any of these tools. The `.scrx` scripts are
  binary, so the ScriptEngine *API surface* (does it expose entities/positions, or only camera/time?)
  is **unconfirmed** — that is the single most valuable thing to check next.
- **Explicitly absent:** no public **co-op** mod for any AC game (searched GitHub; only trainers/junk).

## Gotchas
1. **Assume no co-op prior art.** Searches for "AC co-op / multiplayer mod / Black Flag coop" return
   nothing real. You are on your own; budget accordingly.
2. **The best "oracle" for a networked avatar is a shipped MP exe.** Black Flag (`AC4BFMP.exe`) and AC3
   have one; AC1 and Rogue do not. Don't start a replication project on a title with no netcode to copy.
3. **Version pinning is everything.** ACUFixes is for AC Unity **1.5.0**; the ScriptEngine camera tools
   target **AC4 1.07 / Rogue 1.1.0**. Other builds will break addresses.
4. **AnvilToolkit XML is a sidecar.** Editing only the exported `.xml` does nothing — the game reads
   the **binary** resource. Repack the `.data` then the forge, with the game closed, and diff bytes.
5. **AC1 is a trap for feature work.** No MP, no framework, tiny community — expect to build tooling
   from scratch.
6. **Don't index the Black Flag *Resynced* (remaster) repos here** — kept out deliberately.

## Assets
Not applicable (survey note). Toolchain only; ship no game files.

## Cost and time
One session (GitHub survey + README reads).

## Open questions
- What does the **ScriptEngine `.scrx` API** actually expose — camera/time only, or entities and
  transforms? If the latter, it is a big shortcut for AC4/Rogue native mods.
- Does **ACUFixes' ACU-RE** library expose entity/transform access usable for a replication layer?
- Is there a clean way to spawn/drive a **second character** in any AnvilNext title (the open gate in
  our AC Rogue co-op work)?
