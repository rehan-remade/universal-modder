# Genie engine: Age of Empires II DE (and AoE1 DE)

**Identify.** `AoE2DE_s.exe` and `resources/_common/dat/empires2_x2_p1.dat`.
- Profile: `%USERPROFILE%\Games\Age of Empires 2 DE\<steamid>\` holds `mods/local/`, `mods/subscribed/`,
  scenarios and saves.
- No anti-cheat for single player and lobbies. Ranked always uses unmodded data.
- **Worked example:** `examples/aoe2-de-civ/`, a new civilization with units rendered from 3D. The Lessons
  there are the fastest way to avoid a day of dead ends.

## Mod kinds (local mod = folder in `mods/local/<Mod>/` mirroring `resources/`)
- **Data mod:** a modified `resources/_common/dat/empires2_x2_p1.dat`. It only applies when chosen in the
  skirmish lobby's **Data Mod** dropdown; the Mod Manager shows a gear icon instead of a checkbox. Edit
  with `genieutils-py` (Python: units, techs, civs, effects, graphics, sounds) or the Advanced Genie Editor
  (AGE, GUI).
- **Graphics mod:** `resources/_common/drs/graphics/*.sld` sprites.
  - SLD is BC1/BC4 compressed layers: main, shadow, damage mask, player colour.
  - Read/write with `examples/aoe2-de-civ/sld.py`, round-trip verified against stock sprites.
  - Unit sprites have 16 headings (clockwise from east) and a canvas with a hotspot at the unit's ground
    point.
  - Render them from 3D with `um render3d --preset aoe2 --shadows`, and mask player colour with
    `um sprite team-mask`.
- **Menu art and tech tree:**
  - art: `resources/_common/wpfg/resources/` (`uniticons/`, `civ_emblems/`, `civ_techtree/`);
  - civ picker and tech-tree data: `resources/_common/dat/civilizations.json`, `unitlines.json`,
    `futuravailableunits.json` (copy the stock files and edit your civ's entries).
- **Strings:** `resources/en/strings/key-value/key-value-modded-strings-utf8.txt` (`id "text"`).
- **Scenarios:** `AoE2ScenarioParser` (Python) builds `.aoe2scenario` files with units, triggers and camera
  moves. Great for scripted test scenes and demo takes.

## Facts to know
- **The civ picker has hard-coded limits.** It lists only civs in the executable's civ table (index-based UI
  tables). To add a civ, **replace a slot** (e.g. Burgundians, 36): copy a base civ's tech tree and
  overwrite the name, strings and art. Extra civs load but never show in the picker.
- **Help strings:** DE keeps DLL help strings at `id - 79000` in key-value files (Knight help 105068 → key
  26068). New string ids must be unused in the stock tables.
- **Command-panel icons** come from the base game's prebuilt `widgetui` atlas, which a local mod can't
  extend. Use stock icon ids in game and your art in menus and the tech tree.
- **Castle unique units** need `creatable_type` 2. Tech 266 ("Castle built") never fires for
  scenario-placed castles, so gate on Castle Age instead.
- **Append, don't remove:** deep-copy template units, graphics and techs, and append them. Keeping indices
  stable means the other civs stay unchanged.
- **Windowed mode for automation:** set registry `HKCU\Software\Microsoft\Microsoft Games\Age of Empires II
  DE`, `Mode Display` = 0, then `Windowed Width/Height` to any size (1936x1119 → 1920x1080 client).
- **Crashes:** a crash leaves `BsSndRpt64.exe` (BugSplat) running, and Steam refuses to relaunch until you
  kill it by PID.
