# Age of Empires II DE: a new civilization

The San Franciscans: a complete civilization for Age of Empires II: Definitive Edition, with fal-generated
art rendered into the game's own sprite format and a data mod built with genieutils-py. It was tested
in game (DE, September 2026), and it is meant as a template for your own civ.

- **Robotaxi / Elite Robotaxi**: the unique unit, trained at the Castle. A fast self-driving car that rams.
- **Delivery Drone**: a hovering ranged unit at the Archery Range from the Castle Age.
- **Transamerica Pyramid**: the wonder.
- **Bonuses**: villagers work 10% faster, cavalry move 10% faster, Universities work 40% faster.
  Team bonus: Universities +20%.
- **Unique techs**: Series A Funding (Castle Age: +600 gold) and Move Fast and Break Things (Imperial
  Age: Robotaxis +25% speed, +8 attack vs buildings).

The civ takes over the Burgundians' slot (see Lessons). It only applies when you pick the mod in the
skirmish lobby, so the stock game is untouched otherwise.

## Pipeline

```
fal concept art (FLUX dev: white background, blue trim = player colour)      assets/gen.sh
      |  um fal model3d
      v
textured 3D model (Trellis)                                                   assets/gen/*.glb
      |  um render3d --preset aoe2: ortho 30 deg, 16 headings, shadow pass    make_sprites.py render
      v
PNG frames per animation and heading                                          build/frames/
      |  blue -> player-colour layer, burnt death frames, sld.py              make_sprites.py pack
      v
.sld sprites (BC1 main layer, BC4 shadow and player-colour layers)            build/graphics/
      |  + civ.py (slot, base civ, units, techs, bonuses) with genieutils-py  build_mod.py
      v
data mod: .dat + civilizations.json + tech tree + strings + icons             build/SanFranciscans/
      |  --install
      v
<profile>/mods/local/SanFranciscans  ->  skirmish lobby: Data Mod dropdown
```

The wonder is a single frame, so it skips the 3D step: fal paints it in AoE2's projection and
`make_wonder.py` fits it to the 5x5-tile footprint.

## Files

| file | what it does |
|---|---|
| `civ.py` | the civilization as data: names, slot, base civ, bonuses, units, techs, art. Edit this one |
| `build_mod.py` | the genieutils data mod: units, graphics, techs, effects, JSON, strings, icons; `--install` |
| `sld.py` | AoE2 DE `.sld` sprite reader and writer (reverse-engineered), plus `info`, `roundtrip`, `to-png` |
| `make_sprites.py` | `render`: GLB to frames with `um render3d`. `pack`: frames to `.sld` plus a preview sheet |
| `make_wonder.py` | the wonder art to `.sld`, fitted to the footprint |
| `make_scenario.py` | test and demo scenarios (AoE2ScenarioParser) |
| `aoe2paths.py` | finds the game install and your profile folder (Windows, WSL, Linux/Proton) |
| `assets/gen.sh` | the fal prompts, run with `um fal` |
| `assets/gen/` | the art the mod shipped with: unit concepts, the two GLBs, portraits, emblem, wonder |
| `demo_notes.md` | how the demo video was recorded and cut with `um win` and `um video` |

## Build and install

You need AoE2 DE (Steam) and Python 3.11+ (genieutils-py needs it). Blender (5.x, on `PATH` or set
`BLENDER=...`) is only needed to re-render the unit sprites, through the repo's `um render3d`.
Installing needs your profile folder: Windows or WSL (on Linux the Proton prefix is searched,
untested). Building works anywhere the game's files are readable (pass `--game`).

```bash
cd examples/aoe2-de-civ
pip install -r requirements.txt       # or put `uv run --no-project --with-requirements requirements.txt` before each python

python make_sprites.py all robotaxi drone   # Blender: 3712 small renders, then build/graphics/*.sld
python make_wonder.py                       # build/graphics/b_sf_wonder_x1.sld
python build_mod.py                         # build/SanFranciscans + build/ids.json; nothing is installed
python build_mod.py --install               # the same, then copied into <profile>/mods/local/SanFranciscans
python make_scenario.py demo --install      # optional: the demo map, into the profile's scenario folder
```

In the game: Single Player, Skirmish, then **Data Mod: San Franciscans Civilization**. The San
Franciscans are in the civ picker in the Burgundians' place. For the demo map, set Game Mode to Custom
Scenario and pick `sf_demo`.

Paths are found automatically, and every script takes overrides:

- `--game` or `AOE2DE_GAME`: the `AoE2DE` folder. Default: searched for in the Steam libraries
  (`libraryfolders.vdf`) on Windows, from WSL (`/mnt/c/...`) and on Linux.
- `--profile` or `AOE2DE_PROFILE`: `%USERPROFILE%\Games\Age of Empires 2 DE\<steam id>`. Default: the one
  account folder there (from WSL, `%USERPROFILE%` comes from `cmd.exe`; on Linux, from the Proton prefix).
  The game also keeps a `0` folder there, which is only used if it's the only one. With several
  accounts, pass `--profile`.
- `--out`: the build folder, default `build/` next to the scripts. Sprites are read from `<out>/graphics`.

`--install` copies the mod folder and adds it to `mods/mod-status.json`. To remove the mod, delete
`<profile>\mods\local\SanFranciscans` (and its entry in `mods\mod-status.json`). The Burgundians are
back as soon as the mod isn't picked in the lobby.

## Make your own civ

1. **`civ.py`.** Pick the slot to take over (`SLOT`, `SLOT_NAME`) and the base civ whose tech tree and
   architecture you start from (`BASE_CIV`). Then fill in the name and tagline, bonuses and team bonus
   (effect commands plus their description lines), `UNITS` (the first is the unique unit) and
   `UNIQUE_TECHS` (Castle Age, Imperial Age). Each unit names a stock `template` unit and only the
   stats you give change. New string ids must be unused in the stock tables.
2. **Art.** Edit the prompts in `assets/gen.sh` and run it (needs a fal key: `FAL_KEY` or `um fal key set`),
   or put your own files in `assets/gen/` under the names `civ.py` uses (`.png` or `.jpg`; the newest wins).
   You need a concept image per unit on white with the player-colour parts in saturated blue, a portrait per
   unit, a round emblem on white, and the wonder on white in AoE2's three-quarter view.
3. **Sprites.** `python make_sprites.py all <unit>`, then open `build/previews/<unit>_sheet.png`: one row
   per animation, 16 headings starting east and turning clockwise, player colour shown red. If the nose
   doesn't follow the headings, change `render.forward_yaw`. If the size is off next to stock units,
   change `render.length` (px at 1x). `python make_wonder.py` writes `build/previews/wonder_fit.png`
   with the footprint drawn in red.
4. **Build**: `python build_mod.py --install`. Then pick the mod in the lobby.

You don't have to look up the templates. `build_mod.py` derives them from the game data:

- each new animation copies the settings of the template unit's own graphics (idle, walk, attack,
  death, and its corpse's decay);
- the techs copy the base civ's own, from `civilizations.json`: its unique unit's availability tech,
  elite upgrade and two unique techs;
- the tech tree is the base civ's, with its unique entries swapped for yours (matched by node id).
  Extra units are added as copies of the unique unit's node;
- the replaced slot's own name and description strings get your text too.

Still specific to this example: the maps in `make_scenario.py` (hand-placed units and triggers), one
unique unit with one elite version, and exactly two unique techs.

### Rendering and the `um render3d` CLI

`make_sprites.py render` prints the `um render3d` command for each unit, for example for the Robotaxi:

```bash
um render3d assets/gen/robotaxi.glb build/frames/robotaxi --preset aoe2 --length 80 --forward-yaw -90 \
  --anims idleA:10:bob,walkA:12:walk,attackA:16:lunge,deathA:20:die,decayA:1:wreck --shadows --samples 40
```

`--anims` names a motion per animation, and each motion has fixed parameters. Both shipped units
tuned some of them, and the flag has no way to pass those values:

| unit | animation | shipped | the CLI's motion |
|---|---|---|---|
| Robotaxi | idleA | bob, amp 0.3 px | bob, amp 1.0 |
| Robotaxi | attackA | lunge, dist 14 px | lunge, dist 12 |
| Robotaxi | deathA, decayA | roll 85 deg | roll 80 |
| Drone | idle, walk, attack, death | hovers 34 px up (and falls from there when it dies) | on the ground |
| Drone | idleA / walkA | bob amp 2.0 / amp 1.5, pitch 8, 1 cycle | bob amp 1.0 / walk amp 0.8, pitch 0.8, 2 cycles |
| Drone | attackA | lunge dist -6 (backs off), pitch 10 | dist 12, pitch -3 |
| Drone | deathA, decayA | roll 60, sink 1 (death: speed 1.2) | roll 80, sink 3 (speed 1.4) |

So for these units the script calls `um.render3d.render()` from Python with the full motion per
animation. It runs the same Blender script (`um/blender/render_sprites.py`, ported from this mod's
original `render_unit.py`) with the same camera and light. Rendered this way, the first frame of every
heading matched the original renders to a mean difference under 0.01/255 (at most a few levels on a
few pixels, from GPU denoising). The drone's other differences (64 px, sun 6, 20 samples) are plain
flags, and its `brighten` is applied when packing, not rendering. `--cli` forces the command line
anyway, and a unit whose motions match the CLI's goes straight through `um render3d`.

## What the mod contains

```
SanFranciscans/
  info.json                                        Mod Manager title, author, description
  resources/_common/dat/empires2_x2_p1.dat         the game data with the new civ in slot 36
  resources/_common/dat/civilizations.json         slot 36: strings, emblem, unique unit and techs
  resources/_common/dat/CivTechTrees/BURGUNDIANS.json   its tech tree (the Britons', with our unique entries)
  resources/_common/dat/unitlines.json             + the Robotaxi line
  resources/_common/dat/futuravailableunits.json   slot 36's list of units still to come
  resources/_common/drs/graphics/*.sld             the sprites
  resources/_common/wpfg/resources/...             emblem, tech-tree picture, unit portraits (menus)
  resources/en/strings/key-value/key-value-modded-strings-utf8.txt   every new string
```

New units, graphics, techs and effects are appended to the stock data (every civ gets the unit
records, disabled), and only slot 36 is replaced. This folder holds no game files: the scripts read
your install and write the modified copies into `build/`. A shared data mod does carry a modified
`.dat`. Before sharing, run `um publish check build/SanFranciscans --game "<AoE2DE>"`. It finds no game
files copied verbatim, and warns that the mod folder has no README, so add one with credits to the
copy you share.

## Checks you can run without the game

- `python sld.py roundtrip "<AoE2DE>/resources/_common/drs/graphics/u_cav_knight_idleA_x1.sld"` decodes the
  stock knight, encodes it again and decodes that: 0.91/255 mean RGB error over 965,699 opaque pixels,
  no pixel changes opacity; shadow 0.97/255, player colour 0.74/255.
- `python sld.py info <file.sld>` and `python sld.py to-png <file.sld> out/` look inside any sprite,
  yours or the game's.
- `python build_mod.py --out /tmp/aoe2build` builds the whole mod without installing anything (about
  15 s, most of it parsing the 12 MB `.dat`).

Rebuilt from this folder, the mod matches the copy that was installed and tested in game byte for
byte, with one fix: `futuravailableunits.json` no longer turns the Town Watch tech into the Robotaxi
(see Lessons). (The game rewrites the installed `info.json` itself, adding `CacheStatus`.) Packing the
original renders gives the same `.sld` files byte for byte, and `make_scenario.py demo` writes the same
`sf_demo` that was recorded.

## Lessons

- A mod with a `.dat` is a **data mod**. It only applies when picked in the skirmish lobby's "Data
  Mod" dropdown. The Mod Manager shows local mods with a gear icon, not a checkbox.
- The civ picker only lists civs the executable knows. It has a hard-coded civ-id table ending at
  `DANES-CIV`, and the UI icon tables are index-based. So a new civ must **replace an existing slot**
  (here the Burgundians, slot 36). Extra civs load and play, but never show in the picker.
- DE's key-value strings hold the DLL help strings at **id - 79000** (Knight help 105068 is key 26068).
  The replaced slot's own name and description string ids need the new text too.
- In-game command-panel icons come from the base game's `widgetui` atlas, and a local mod can't extend
  it (`widgetui/` in the mod root and under `resources/_common` are both ignored). Use stock icons in
  game (here Siege Ram and Scorpion) and your own art in the menus, civ picker and tech tree.
- Tech 266 "Castle built" never fires for castles placed by a scenario. The stock unique units require
  it, so this civ's unique unit only requires the Castle Age. Castle unique units need `creatable_type` 2.
- `futuravailableunits.json` mixes unit and tech ids: `"ID": 8` is both the Longbowman and Town Watch.
  Swap ids only inside `Units` lists.
- AoE2's unit camera is orthographic, 30 degrees down (2:1 tiles). Units have 16 headings, from east
  turning clockwise in 22.5 degree steps, with the ground point at the canvas centre (the hotspot). An
  `.sld` holds 16 x frames + 1 trailing frame, a BC1 main layer with a hard alpha edge, and BC4 shadow and
  player-colour layers. Player-coloured parts are grey shading under the mask.
- A wonder's 5x5 footprint is a 480 x 240 px diamond at 1x, centred on the hotspot.
- NVENC H.264 is limited to 4096 px wide: capture the centre of a 5120x1440 screen (or use HEVC).
- Any window size: in the registry key `HKCU\Software\Microsoft\Microsoft Games\Age of Empires II DE`,
  `Mode Display` is 1 for full screen and 0 for windowed, and `Windowed Width/Height` take any size
  (1936x1119 gives a 1920x1080 client area). The in-game list stops at 1366x768.
- A crash leaves BugSplat's `BsSndRpt64.exe` open, and Steam then refuses to launch the game ("already
  running"). Kill it by PID.
- Local mods live in `%USERPROFILE%\Games\Age of Empires 2 DE\<steamid>\mods\local\<ModName>`.

## Credits

- [genieutils-py](https://github.com/SiegeEngineers/genieutils-py) by SiegeEngineers (LGPL-3.0): reads
  and writes the `.dat`.
- [AoE2ScenarioParser](https://github.com/KSneijders/AoE2ScenarioParser) by Kerwin Sneijders (MIT): the
  scenarios.
- Art generated with [fal](https://fal.ai): FLUX.1 [dev] by Black Forest Labs (`fal-ai/flux/dev`) for the
  concepts, portraits, emblem and wonder; TRELLIS by Microsoft (`fal-ai/trellis`) for the shipped 3D
  models. `assets/gen.sh` regenerates them with TRELLIS 2 (`fal-ai/trellis-2`).
- Rendered with Blender (Cycles).
- Age of Empires II: Definitive Edition belongs to Microsoft. This is a fan mod.
