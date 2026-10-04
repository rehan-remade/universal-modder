# Big games with community frameworks

These AAA engines have no official mod kit, but the community built one. Use the framework; don't
reinvent it. Check each one's GitHub/Nexus page for the version matching the game build.

## Capcom RE Engine (Resident Evil 2/3/4/7/8, Monster Hunter Rise/Wilds, Devil May Cry 5, Street Fighter 6, Dragon's Dogma 2)
- **REFramework** (praydog) goes in the game folder as `dinput8.dll` plus `reframework/`. You get:
  - Lua scripting (`reframework/autorun/*.lua`) with full access to the managed type system:
    `sdk.find_type_definition`, `sdk.hook`, `sdk.call_native_func`;
  - an in-game object explorer;
  - a free camera;
  - VR for many titles.
- **Asset replacement:** files in `natives/` loose paths (with pak priority), via Fluffy Mod Manager or
  loose-file loading. Browse with RE_RSZ / RETool; extract paks with a file list.
- `REFramework-MCP` exposes the game to an agent.
- Online components (SF6 ranked, MH lobbies): cosmetic-only local mods are the norm. Never gameplay-affecting
  mods online.

## FromSoftware (Elden Ring, Dark Souls, Sekiro, Armored Core 6, Nightreign)
- **Loaders:** ModEngine2 (archived but widely used) or its successor **me3**. They load mods from a folder
  and launch the game **offline with EAC off**. That is the only acceptable way; never online.
- **Data and params** (weapons, enemies, spEffects): Smithbox (successor of DSMapStudio) edits params, maps,
  text and models. WitchyBND unpacks and repacks BND/DCX/BDT containers.
- **Code:** DLL mods loaded by the mod engine (hooks via MinHook). Seamless Co-op is its own separate
  network.
- The "Minecraft inside Elden Ring" and "creepers in Dark Souls" clips (Sept 2026) were built with
  Claude/Opus. Their method wasn't published.

## Rockstar RAGE (GTA V Legacy/Enhanced, RDR2)
- **Story mode only.** BattlEye protects GTA Online; ScriptHookV refuses to run online, and mods must never
  go near GTA Online.
- **Scripts:** ScriptHookV (and ScriptHookVDotNet for C#) + Ultimate ASI Loader (`dinput8.dll`, `*.asi`
  plugins). Natives DB (NativeDB) lists callable game functions. RDR2 uses ScriptHookRDR2 + Lenny's Mod
  Loader.
- **Assets:** OpenIV (with a `mods/` folder copy of RPFs; never edit originals), and CodeWalker for maps.
- LSPDFR-style frameworks exist for specific genres.
- **From the Minecraft × GTA V project** (`knowledge/games/gta-v/minecraft-passthrough.md`):
  - **Launch:** launch story mode with BattlEye off (`-nobattleye` in `args.txt`, or the launcher's toggle).
    That also keeps Online from starting.
  - **ReShade:** it has to load through the ASI loader. GTA loads the system `dxgi.dll` ahead of a proxy in
    its folder.
  - **Downloads:** dev-c.com (ScriptHookV) rejects scripted downloads without browser headers.
  - **Script lifecycle:**
    - the pause menu stops ScriptHookV scripts;
    - the idle cinematic camera starts after about 30 s (call `INVALIDATE_IDLE_CAM` every frame);
    - explosion camera shake isn't reported by `IS_GAMEPLAY_CAM_SHAKING`.
  - **Camera timing:** a script reads the camera for the frame being prepared, one frame ahead of what's on
    screen.

## CD Projekt REDengine
- **Cyberpunk 2077:**
  - REDmod (official): archives and tweaks;
  - Cyber Engine Tweaks: Lua, console, overlay;
  - RED4ext: native plugins;
  - ArchiveXL / TweakXL: new items and records;
  - WolvenKit: projects, asset export/import.
- **The Witcher 3:** REDkit (official editor), script mods (`.ws` merged with Script Merger).

## Larian (Baldur's Gate 3)
Official mod.io toolkit + Script Extender (Norbyte) for Lua + LSLib/BG3 Modder's Multitool for `.pak`.

## Paradox, Total War, XCOM and the rest
Many strategy games ship official tools:
- Paradox: plain-text script mods (see misc-engines.md);
- Total War: RPFM (Rusted PackFile Manager);
- XCOM 2: the WOTC SDK;
- Cities: Skylines: C# mods.

Search "<game> modding wiki" before reverse engineering anything.

## Frostbite (Battlefield, Mass Effect Andromeda, Dragon Age, FIFA)
Frosty Tool Suite supports specific single-player titles. Most modern Frostbite games ship EA Javelin
kernel anti-cheat: offline single-player only, if at all.
