# Source (1) and Source 2

## Source 1 (Half-Life 2, Portal 2, TF2, L4D2, Garry's Mod, CS:S...)
**Identify.** `<mod>/gameinfo.txt`, `*_dir.vpk`, and `bin/engine.dll`.
- **Content without code:**
  - `custom/` or `addons/` folders take loose files or VPKs that override by path;
  - maps with Hammer (`.vmf` → vbsp/vvis/vrad → `.bsp`);
  - models via Crowbar (decompile/compile `.mdl` with `.qc`);
  - materials `.vmt`/`.vtf` via VTFEdit.
- **Scripting:**
  - VScript (Squirrel) in Portal 2, L4D2, TF2 and CS:GO-era games: `scripts/vscripts/*.nut`, entity
    I/O;
  - Garry's Mod: Lua addons (`lua/autorun/...`);
  - SourceMod + Metamod:Source for **servers you run** (plugins in SourcePawn).
- **Code:** Source SDK 2013 (github.com/ValveSoftware/source-sdk-2013) builds your own mod (a new game
  folder under `sourcemods/`). It's the official, fully legal route for new mechanics in HL2-era games.
- **Browse:** GCFScape / VPKEdit to open VPKs; Crowbar for models; BSPSource to decompile maps.

## Source 2 (CS2, Dota 2, Half-Life: Alyx, Deadlock)
**Identify.** `game/bin/win64/engine2.dll` and `game/<mod>/gameinfo.gi`.
- **Official tools:** the Workshop Tools DLC (Hammer 2, Material Editor, ModelDoc, Particle Editor). Addons
  go in `game/<mod>_addons/<addon>/`, and `-tools` launches the editors.
  - Half-Life: Alyx: VScript Lua.
  - CS2: map workshop and VScript successors. Check the current state; Valve changes it.
  - Dota 2: custom games (Lua + Panorama UI).
- **Read assets:** Source 2 Viewer / ValveResourceFormat (VRF) decompiles `_c` resources: models, maps,
  textures, even collision. `um`'s authors used VRF to export CS2 map collision for a movement clone.
  Derived data stays out of git.

## Rules
- VAC: modified clients on VAC-secured servers get banned. Test with `-insecure` on a local listen server
  and never inject into CS2/Dota/Deadlock/TF2 on official matchmaking.
- The Workshop, maps, custom games and VScript are the sanctioned routes for the multiplayer titles.
- Demos (`.dem`) are a great oracle for gameplay work. DemoFile.Net and the demoparser libraries extract
  per-tick state.
