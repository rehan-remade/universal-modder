---
kind: game
title: "Syrian Warfare's maps, triggers, buildings and effects converted to run in Terminator: Dark Fate - Defiance"
game: "Terminator: Dark Fate - Defiance"
games_also: ["Syrian Warfare"]
game_version: "TDF 1.09.1223 (Steam) with DefianceLoader 1.9.0; Syrian Warfare 2018 x86"
platform: windows
engine: unknown
route: data
tools: ["Python 3", "IDA", "texconv", "TDF's own map editor", "TDF's Luac.exe"]
anti_cheat: "none seen; single player only"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-31
links: []
tags: [frontedge, cats-who-play, map-port, land-format, triggers, lua-bytecode, psyfx, mlms, detour]
---

# Syrian Warfare's maps, triggers, buildings and effects converted to run in Terminator: Dark Fate - Defiance

> Syrian Warfare (SW, 2018, x86) is the ancestor of the engine that runs Terminator: Dark Fate - Defiance (TDF). 28 SW maps
> were converted to TDF with Python: landscapes, objects, triggers, 990 building models, lights and 307 particle effects;
> units were replaced by TDF rows by role. All 28 maps load in the real game without a crash, and flag capture on one
> mission was confirmed by playing it. Mission text was left out, and the converted effects have not been seen in the game
> yet. See the [TDF engine note](defianceloader-plugins-data-mods-and-engine-facts.md) for mounting and tables.

## Setup
- TDF as in the engine note. SW's install was left unchanged, and its data was read from a work folder.
- `texconv` for textures, TDF's `basis\scripts\effects\Luac.exe` for effects, and TDF's own map editor for `.path` files.

## Route and why
`data`: every format is rewritten offline into what TDF already reads, with no plugin needed to load a map. The formats
are close relatives, so a converter is far less work than a loader. Units, weapons and vehicles were deliberately not
ported: each is mapped to an existing row by side and role.

## How the game works (what we had to learn)

### Landscape
- **TDF `.land`** (`MapImpl::load` `sub_180128AD0` in `world2.dll`): `LAND` + byte 7, then blocks:
  - `HEAD`: int size, float height scale (256);
  - `HGHT`: u32 length + zlib of u16[(size+1)^2], height = value / 65535 x scale;
  - `TMSK`: int resolution, byte layer count (32), u32 splats, each u32 length + zlib of RGBA8, 4 layers a splat;
  - `LAYR`: byte version, u32 count, each layer two names and 12 bytes; `textures/tiles/<name>` gives `_albedo`,
    `_normal`, `_rough` files;
  - `VIAL`, `TXTR`, `LGHT`: `VIAL` is optional, and the game makes its own.
- **SW `.land`** (`TERR` v9, `landscape.dll` `sub_100145C0`): tiles each with a palette of up to 5 texture numbers, a mask of
  weights per palette slot, texture names `tiles/<name>`, and a tail with sun, play bounds and fog.
- In SW a texel's colour sums texture[palette[k]] x mask[k] over the tile's palette, so in TDF the weight of mask k goes to
  layer palette[k], and layers pack by 4 into RGBA.
- **SW `.land.vt`:** u32 w, u32 h, float32 heights in metres on a 1 m grid. This is the height source.
- `.path` is the game's header (u32, map bounds) plus a Detour tile cache set (`TSET`, version 2). `.physx` is built by the
  game when missing.

### Objects
- `.sws` in both games: int 2, int count, each object int 1, `CWP` + version.
- SW version 0: a property is name, name, int type (0 int, 1 float, 2 string, 4 compound).
- TDF version 1: a property is name, byte type (0 int, 1 float, 2 string, 3 int4, 5/6 vec3, 7 quaternion, 8 uuid).
- TDF keeps units, zones and sounds in `.units.swp`, `.zones.swp`, `.sounds.swp`.
- TDF knows `$fence`, `$power_line`, splines, decals, `$water`, `$landscape`, `$bloom`. It has no `$passblock`, `$setpool`
  or `$pointsound`.
- Object ids: in TDF an id is a map prefix << 16 | counter. SW ids are small.

### Models and materials
- SW `.mld` is `MLMS` v2, a serialized object tree with a string table. TDF has no reader, so `MLMS` to `MODL` 7 is a
  full conversion: a node a frame, a mesh per (piece, material).
- SW draws alpha as a test above 128. A TDF opaque material cuts by alpha the same way. Four classes are needed: opaque,
  cutout, blend (glass) and mask (nearly all below 128: the alpha was a colour mask, so make it solid).
- SW landscape tiles: DXT1 plus `_bump` (DXT5, RGB normal, A gloss). TDF: BC7 albedo, BC5 normal, BC7 rough.

### Light
TDF's sun quaternion is stored `w,x,y,z` and turns +x into the light direction. In all 70 TDF maps +x points down by 10-41
degrees. SW's direction and colour come from the `.land` tail, ambient from `$bloom`, the grade from
`colorGradeTexture` (a 16-cubed volume, written as a 256x16 PNG with pixel (b*16+r, g)).

### Effects (`.psyfx`)
- SW files are Lua 5.0 bytecode (`\x1bLuaP`, 22-byte header, 4-byte size_t). TDF and GB use Lua 5.1 (`\x1bLuaQ`, 12-byte
  header, 8-byte size_t). TDF ships `Luac.exe`.
- These chunks are simple: 11 opcodes, no jumps or nested functions, local names preserved. A small reader turns them
  back into source.
- Recompiling is not enough. The engine holds no `.fx` names and has one `particles.shader`. Blending comes from a material
  key. Rules, confirmed on the later games' own files:
  - `_add` in the old shader name becomes `blend = "additive"` (316 of 316 in a sister game, 8 of 8 in TDF);
  - `_shd` becomes `shaded = 1`;
  - `diffuse@Name` becomes `diffuse@name`;
  - strip `.tga` from texture names;
  - drop `Pfx.PhaseFactor`, a channel that no longer exists.
- Of 165 effects with the same name in a later game, 156 matched its version exactly after these rules, and the other 9 had
  been changed by its developers. That is a strong offline oracle.

### Triggers
- `.swt` is XML, and the action and condition names survived. See Gotchas 1-3 for behaviour that differs.
- Action `a_spawn*ToZone` names unit rows, so the unit map must include what triggers spawn, not only what maps place.
- SW's player brings an army to a mission. TDF's `--loadtm` does not fill the army pool (engine note). Some maps start with
  no player units, and such a mission ends at once on `mission_fail`. A plugin that calls the pool's own loader for a map
  started alone solved this.

## Build steps
1. Unpack SW to a work folder. Never write into the game folder.
2. Convert the landscape, tiles, then models and materials, then objects, then triggers and units.
3. Copy a TDF `.path` of the same size (512 or 1024 m) so that the map opens at all. Open each map in TDF's editor and
   press "update the pathing map", and it writes the real one. It took about 1.5 minutes a map, scripted.
4. Add rows to `buildings.xml`, `spawns.xml` and the rest, and to the DLC's copies of those tables too.
5. Rebuild effects with `Luac.exe` and put them in `basis`. Add new rows after the building rows are written, or the
   building step puts the old values back.
6. Load each map with `--loadtm`, wait 40 s, take a screenshot and read `game.log`.

## Verification
- **All maps:** a scripted pass over 28 maps found no crash. Two maps looked wrong and were explained (a lost first start
  of Steam, and a mission failed by its trigger because the player starts with no units).
- **A mission played:** flag capture on `sw_city_test5` confirmed in a human play session.
- **Trigger probes:** triggers that on firing set a group `dbg_<probe>`, counted through `game.getEntitiesByGroupName`.
- **Effects, offline only:** 307 of 307 compiled and matched the expression tree after the rules. **Not seen in the game.**
  Most risky: `VectorFactor` (4 files), distortion (17), `ribbon` tracers (21 files).
- **Light** was converted and is not reviewed on every map.
- **Not done:** mission text and dialogue are not installed, so dialogues open empty.

## Gotchas
1. **A flag can never be captured.** **Cause:** TDF stops a trigger's action list at the action that deactivates the trigger
   itself. SW runs them all. In TDF maps self-deactivation comes first in 1 of 108 triggers and last in 78. In SW maps it
   comes first in 157 and in the middle in 67. **Fix:** move self-deactivation to the end: 216 triggers on 11 maps.
2. **Hero's car frozen: can't drive, can't get out.** **Cause:** AI `dummy` means "no own AI, the player drives" in SW and a
   frozen staged object in TDF. **Fix:** map `dummy` to `script`.
3. **Empty `Param` crashes a map.** See Gotcha 3 of the engine note. Write `prm=?`.
4. **Crash at load, `logic+0x3412c5`, `dtTileCache::addObstacle`.** **Cause:** a map with no `.path` has no tile cache. **Fix:**
   Build step 3. The editor will not open a map without one either.
5. **Crash at load, `logic+0x357d1a`, `PowerLineGeometryFacet`.** **Cause:** `$power_line` objects, which no TDF map uses. **Fix:**
   don't convert them.
6. **Crash at load, `world2+0x17e516`.** **Cause:** nodes are taken by parent index, and SW's `_burn` debris had many roots
   and parents out of range. **Fix:** one root, parents before children.
7. **Fences "starburst" across a village.** **Cause:** SW's small ids collide with ids the game gives its own entities. **Fix:**
   rewrite ids below 65536 as (1100 + map number) << 16, with references (`fence_link_id1/2`, `points_id`). Leave
   `tractor/trailer_link_id` alone: they are not entity ids.
8. **Buildings look like glass.** **Cause:** a material was marked transparent for any alpha below 200. **Fix:** the four alpha
   classes above.
9. **XAudio error every frame.** **Cause:** a stereo file on a point sound. **Fix:** convert to mono, and set `base_volume`
   on `$sound`, or every sound logs an error.
10. **The editor saves into a random mod.** Ctrl+S writes to the highest-priority mounted folder, while the `.path` goes
    straight to `dlc\Resistance\basis\spawns`. The editor also drops orphan road points and appends `VIAL` to `.land`.
    **Fix:** script it and move the results back. Keep only the `.path` and `.physx`.
11. **All maps look cold and blue.** They shared one TDF light setup. **Fix:** convert SW's own sun, ambient, fog and grade.
12. **`Logic box 'inside_boxNN' does not have support mesh`** on buildings. These are infantry places inside buildings. Not
    chased: the maps load and run with it.
13. **Particle errors `dszX` / `dszY`.** They come from 39 of TDF's own effect files, not from a port. Don't chase them.

## Assets
No SW or TDF files are in this note. A map pack made this way carries SW's assets, so it needs its owner's permission
before anyone else can get it. This port has not been released.

## Cost and time
Several long agent sessions, starting 2026-10-19, alongside the sibling notes.

## Open questions
- How the converted effects look in the game: building destruction on an SW map, then `game.log` for `Effect not found`
  and `Wrong particle`.
- Mission text.
