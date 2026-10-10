---
kind: game
title: "Rebuilding Dead Cells' core loop in libGDX, reading the game's own res.pak at runtime"
game: "Dead Cells"
games_also: []
game_version: "Steam macOS build, version string 35 (build date 2023-10-01)"
platform: macos
engine: haxe
route: reimplementation
tools: ["libGDX 1.14.2 (LWJGL3)", "hlbc", "python3 (pak/BTMX readers)", "JDK 21"]
anti_cheat: "none (single-player); nothing in the install is modified, the rebuild only reads res.pak"
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-09
links: []
tags: [reimplementation, heaps, hashlink, castledb, atlas, palette-swap, normal-maps, procgen, room-templates, platformer]
---

# Rebuilding Dead Cells' core loop in libGDX, reading the game's own res.pak at runtime

> A personal reimplementation of Dead Cells' first biome in Java/libGDX. Behaviour is reimplemented from
> study notes of a decompile; every asset (atlases, room templates, CastleDB data, sounds, music) is read at
> runtime from the user's own `res.pak`, and nothing is copied into the project. A generated Prison level is
> playable end to end (rooms, hero moveset, sword combo, Zombie and Archer AI, exit to the next depth). That
> was verified with an in-engine autoplayer and screenshots, not compared frame-for-frame with the real game.

## Setup
- Dead Cells, Steam, macOS. Everything needed is in `res.pak` next to the binary (about 7,055 entries).
  The game logic is HashLink bytecode in `hlboot.dat`; it was only used for study, through `hlbc`.
- libGDX 1.14.2, LWJGL3 backend, Gradle 8.14, JDK 21. On macOS the run task needs `-XstartOnFirstThread`.
- Two modules: `core` (game) and `lwjgl3` (launcher). The pak path is an env var with a default.

## Route and why
`reimplementation`. Dead Cells has an official mod system (pak overlays and CDB patches), but the goal was a
separate codebase in libGDX, not a mod of the running game. Reading `res.pak` at runtime keeps the project
free of game files: it only works for someone who owns the game, and nothing needs extracting to disk.

## How the game works (what we had to learn)
**Containers and formats** (all little-endian):
- **PAK** (Heaps): `"PAK"`, version byte, header size, data size, then (Dead Cells only) a **64-byte stamp**,
  then a recursive tree of entries. Each entry is a u8-length name and a flags byte. A directory (bit 0) has a
  u32 child count and its children; a file has its position (u32, or an f64 when bit 1 is set), size and
  checksum (Adler-32 in Heaps' own packer). Data offsets are relative to the header size.
- **BATL** atlases (`atlas/*.atlas`): `"BATL"`, then pages. Each page is a length-prefixed PNG name followed by
  entries: a length-prefixed name and nine u16 values (index, x, y, w, h, trimX, trimY, origW, origH), with an
  empty name ending the page and an empty page name ending the file. A trailing `_NN` in the name is the frame
  number; names without digits use the index field. `a/b/c` groups are also reachable as `c`. Each page
  `foo.png` may have a `foo_n.png` normal page with an identical layout.
- **Characters anchor their feet at the centre of the untrimmed box** (origW/2, origH/2), not at the bottom.
- **BTMX** room templates (`tiled/tmx/<folder>/<id>.tmx`): binary Tiled maps, always exactly three layers:
  `col` (collision ids 1–7), `lnk` (door and random-block tiles painted on the border), `markers` (typed objects).
  Layers are base64 text of zlib-compressed u32 GIDs. Subtract each file's own tileset firstgid.
- **data.cdb** is CastleDB JSON at the pak root: hero row (run speed, jump, roll), `weapon.strikeChain`, `mob`
  rows with `skill[]`, `room` (type, flags; bit 2 = NoFlip), `level.mobs` (spawn weights), `biome` (ambient,
  light colours, layer gradients).

**Rendering**, the part you will hit first:
- The **hero's pages are palette-indexed**. Red is a column and green×4 is a row into
  `atlas/<model>_<skin>_s.png` (256×4, e.g. `beheaded_default_s.png`). Row 1 holds the skin colours: it is the
  row that differs between `default`, `gold` and `retro`. Drawn raw, the hero is a flat orange silhouette.
- **Mob pages are flat albedo plus a magenta (#FF00FF) key.** The key is the glow, coloured by the mob row's
  `glowInnerColor`. The shading detail is in the `_n` pages.
- **Most level tiles (wall bodies, `dirt`) have black albedo.** Their look comes from normal maps under lights,
  and the front-wall layer goes through a 256×1 gradient (`gradients/<gradientName>.png`, named in
  `biome.layers`). hlbc doesn't decompile the HXSL shaders because they aren't functions: in Heaps, each
  shader class's `SRC` static is the shader serialized to Base64 (`hxsl.Serializer`). We didn't decode them,
  so the lighting here is our own.
- **Every `sfx/**/*.wav` is actually Ogg Vorbis** (magic `OggS`).

**Simulation** (numbers from CDB and the decompile study; behaviour reimplemented, not copied):
- 24 px cells. Timers run at 60 Hz, physics at a 30 Hz fixed step (accumulator ≥ 2 tmod).
  Velocities are in cells per step. Self and knockback velocities are separate, with frictions 0.3 and 0.82.
- The hero's single jump plus double jump only reaches about 3.5 cells with the CDB constants. The levels
  assume the assists: **rising into a one-way snaps you on top of it**, and ledge grabs reach to head height
  (hero is 2.25 cells tall). Without them some template pits are 6 rows deep and inescapable.
- Attacks are timers: the swing animation starts `hitFrame × 2` frames before the hit, and the hit is a
  one-shot area query.

## Build steps
1. Write a PAK reader (index once, then seek and read on demand). Feed PNG bytes to `new Pixmap(bytes, 0, len)`.
2. BATL → `TextureRegion`s, flipped once if you use a y-down camera. Load the `_n` page beside each page.
3. Sounds: wrap the bytes in a `FileHandle` subclass that overrides `read()`/`length()`, named `*.ogg` when the
   data starts with `OggS`. The music `.ogg` files under `music/` work the same way.
4. BTMX → collision grid. Doors are link-tile groups touching a border; the door cell is the edge cell with a
   solid floor below. Chain templates by aligning door cells, seal unused links, roll the random blocks.
5. Sprites: one shader handling palette lookup, normal-mapped point lights, glow-key replacement and
   gradient-mapped walls. Flush the batch when the bound normal page or the horizontal flip changes
   (negate the normal's x when flipped).

## Verification
- An autoplayer (BFS over standable cells with walk, fall, drop-through, jump and ladder edges) plays seeds
  unattended. Screenshots are written at given times and reviewed as contact sheets. Level 1 → 2 → 3 was
  cleared on seed 11; death, banner and restart were checked with a forced kill.
- The generator rejects layouts whose exit is unreachable on the same movement graph.
- Not verified: jump height and combat timing against the real game side by side, lighting fidelity (it's an
  approximation), anything past the first biome.

## Gotchas
1. **Hero drawn as an orange silhouette.** Cause: palette-indexed pages. Fix: look up `_s.png`, red = column,
   floor(green×4) = row.
2. **"Error reading WAV file" for every sound.** Cause: the `.wav` files are Ogg Vorbis. Fix: sniff `OggS` and
   give libGDX an `.ogg` name.
3. **Flat green mobs with magenta blotches.** Cause: magenta is a glow key. Fix: replace it with the mob's
   `glowInnerColor` in the shader.
4. **Walls render as black slabs, or flat blue when gradient-mapped.** Cause: black albedo, with the look coming
   from lights. Fix: drive the gradient index from point-light contribution only, and fade deeper wall cells
   toward black.
5. **`#iterator() cannot be used nested` from libGDX `Array`.** Cause: a mob loop inside a mob loop (attack
   stagger checks other mobs). Fix: `ArrayList` or index loops for entity lists.
6. **Pits you can't climb out of.** Cause: missing jump-through-up and ledge-grab assists, or ladders (1.7 % of
   template tiles). Fix: implement them, including grabbing a ladder whose bottom is above your head mid-air.
7. **Character sprites float or sink.** Cause: anchoring the trimmed frame bottom to the feet. Fix: anchor
   the centre of the untrimmed box.

## Assets
None generated. Everything is read from the user's install at runtime.

## Cost and time
One session, about 4,000 lines of Java.

## Open questions
- The exact lighting and gradient formula (we didn't decode the shaders' `SRC` strings). How Dead Cells maps
  light to the front-wall gradient is a guess here.
- The default skin renders red/tan/cyan, which seems plausible but wasn't compared with an in-game capture.
- Other mobs, items, scrolls, shops, bosses, saves, wall-run spots, slopes, parallax and fog are not rebuilt yet.
