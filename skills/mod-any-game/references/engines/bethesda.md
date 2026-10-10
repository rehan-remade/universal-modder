# Bethesda: Creation Engine / Gamebryo (Skyrim, Fallout 3/NV/4/76, Oblivion, Starfield)

**Identify.** `Data/*.esm` plus `*.bsa`/`*.ba2` archives next to `SkyrimSE.exe` / `Fallout4.exe` /
`Starfield.exe` and so on.
- Saves and INIs: `Documents/My Games/<Game>/` (`Skyrim.ini`, `SkyrimPrefs.ini`, `Saves/`).
- Fallout 76 is online-only: no client mods.

## Use a mod manager for isolation
Mod Organizer 2 (MO2) runs the game in a virtual file system with profiles. It never touches `Data/`,
unlike manual installs. Make an MO2 instance per project and a profile per experiment.
[Vortex](https://github.com/Nexus-Mods/Vortex) is the alternative, and on Linux
[Amethyst](https://github.com/ChrisDKN/Amethyst-Mod-Manager) manages mods natively. Get mod managers from these
official pages: look-alike repos with a zip in their releases are a common way to spread malware.

## Routes
1. **Plugins (`.esp`/`.esm`/`.esl`):** records for weapons, NPCs, quests, cells, leveled lists.
   - Edit in xEdit (SSEEdit/FO4Edit/xEdit), which is scriptable in Pascal.
   - The Creation Kit (from Steam) handles cells, navmesh, dialogue, quests.
   - ESL-flag small plugins to save load-order slots.
   - chasm generated and validated ESPs from Python scripts for Fallout NV. Plugins are structured records,
     so generating them is agent-friendly (e.g. via `esplugin`, `xelib`, or xEdit scripts).
2. **Papyrus scripts** (`.psc` → `.pex`): event-driven game logic attached to records. Compile with the
   Creation Kit's PapyrusCompiler.
3. **Script extender native plugins** for anything Papyrus can't do: new functions, hooks, UI, physics,
   passthrough rendering.
   - The extenders are SKSE64 (Skyrim SE/AE), F4SE, xNVSE, OBSE and SFSE.
   - Build with CommonLibSSE-NG (Skyrim) / CommonLibF4 in C++.
   - Address Library resolves version-independent function IDs.
   - Plugins go in `Data/SKSE/Plugins/*.dll`; logs in `Documents/My Games/<Game>/SKSE/`.
4. **Assets:**
   - meshes: NIF, edited with NifSkope; Blender with PyNifly for export;
   - textures: DDS BC1/BC3/BC7;
   - archives: BSArch / Archive2 to pack BSA/BA2.
   - Animation uses Havok behavior files (hard), so mods reuse existing behaviors.

## Agent workflow tips
- Read records rather than guessing: xEdit can dump plugins to text, and `xelib` automates it.
- Load order matters. Use LOOT for sorting, and check conflicts in xEdit (red = conflict).
- A bridge pattern works well: a thin SKSE/xNVSE plugin captures events and calls out over localhost
  (file-drop or HTTP) to a heavier out-of-process backend. It's the basis of AI-NPC mods and cross-game
  passthrough mods (see mashup-mods).

## Pitfalls
- Game updates break script-extender plugins. Pin the game version, or use Address Library.
- Save bloat: removing scripted mods mid-save can corrupt it. Test on a throwaway save.
- Creation Club / "Anniversary" content changes masters. Know your ESM list.
