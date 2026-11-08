---
kind: game
title: "Black Ops 1 Zombies maps in Black Ops II: technique slot tables, lightmap formats and the crashes behind a working Kino port"
game: "Call of Duty: Black Ops II"
games_also: ["Call of Duty: Black Ops", "Call of Duty: World at War"]
game_version: "Black Ops II Zombies Steam build 24784239 via Plutonium T6 (launcher revision 5369 when written); source Black Ops Steam build 87954; tested October 2026"
platform: windows
engine: iw
route: data
tools: ["B2W (our BO1 fork)", "OpenAssetTools", "Ghidra headless", "Capstone", "fxc D3DDisassemble", "Python 3.13"]
anti_cheat: "Data only: converted mod zones, played solo. Sources are our own installs. No game files are distributed."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["AryaBlue"]
date: 2026-11-08
links:
  - https://github.com/AryaBlue/BO1-B2W
  - https://github.com/AryaBlue/CoD-RE/blob/main/shared/notes/bo1_to_bo2_porting.md
  - https://github.com/Ticass/B2W
  - https://github.com/Laupetin/OpenAssetTools
tags: [zombies, t5, t6, map-port, shaders, techniques, lighting, lightmap, light-grid, converter]
---

# Black Ops 1 Zombies maps in Black Ops II

> We extended the B2W World at War converter to take Black Ops 1 maps. Kino der Toten loads and plays in Black Ops II:
> collision, buyable doors, zombies, game over and reload all work. Compared by eye in game, the lighting looks 1:1
> with the original. Five and the World at War custom map Another Road also loaded in game. This note records what
> differed between the engines. Full research is in CoD-RE.

## Setup
- Sources: your own Black Ops 1 install. Target: Black Ops II Zombies through Plutonium T6.
- Converter: our public B2W fork, linked above.

## Credits
- [B2W](https://github.com/Ticass/B2W) is the converter this extends.
- [OpenAssetTools](https://github.com/Laupetin/OpenAssetTools) (Laupetin) provides the dumpers, linker and the T4/T5
  technique enums.

## Route and why
Data only. Black Ops 1 and Black Ops II are close enough that a data converter works, and no client patch is needed.

## How the game works (what we had to learn)
### Technique slots differ per game
A T6 material slot must read a different source index for each game. Telling the games apart is easy: World at War
has 59 techniques and Black Ops 1 has 130.

| T6 slot | Meaning | WaW index | BO1 index |
|---|---|---|---|
| 1 | build shadowmap depth | 2 | 2 |
| 4 | lit | 8 | 10 |
| 5 | lit sun | 10 | 11 |
| 6 | lit sun shadow | 12 | 12 |
| 7 | lit spot | 14 | 13 |
| 8 | lit spot shadow | 16 | 14 |
| 13 | lit omni | 18 | 15 |
| 14 | lit omni shadow | 20 | 16 |

Black Ops 1 also has dynamic-light techniques 31 to 37, which feed T6 slots 15 to 19, 24 and 25. On Kino, the correct
table took translated lit passes from 0 to about 1,100 materials.

### Lightmaps and light grid
- OpenAssetTools could not load D3D format 23 (R5G6B5, secondary page) or 34 (G16R16, secondary B page), and dropped
  them silently. Dumping them raw and decoding them in the converter fixed the missing pages.
- Black Ops 1 is linear like T6, so it needs no World at War gamma adapters.
- Static models read the light grid, not lightmaps. A magenta ambient probe separates the two quickly.

## Build steps
See the fork's README. The order is stage, build mod, compile scripts, link, audit, install.

## Verification
- **In game:** Kino loads, collision, doors, zombies, death and reload all work, with no bad-vector or runtime errors
  in the log. The green lighting is gone.
- **In game, other maps:** the World at War custom map Another Road and Black Ops 1's Five both load and play in
  Black Ops II through the same pipeline, after their own fixes. Those two builds predate the slot table fix above.
- **Not verified:** the corrected slot tables on a rebuilt World at War map or on Five. Foliage and dynamic lights had
  no specific in-game check.

## Gotchas
1. **Everything is lit green.** No lightmap pages reached T6, so a flat fallback page lit the map. **Cause:** the
   dropped D3D formats above. **Fix:** decode them yourself.
2. **Green streaks remain on red carpet stairs.** Each grid sample has a channel that can reach 0, so red-albedo
   models with no red light read green. **Fix:** desaturate each grid sample toward its own luma. We used a saturation
   of 0.4.
3. **Link fails after copying source pass states.** Black Ops 1 uses alpha test `ge255`, which the T6 linker rejects.
   **Fix:** map it to `ge128`.
4. **Crash drawing a door brush model.** The zone shipped one model because a C++20 range-for over a temporary JSON
   read an empty list. **Fix:** store the parsed JSON in a local. A correct Kino log says 445 brush models.
5. **Crashes in the spot shadow pass.** T6 appends to shadow lists at runtime and lists sized for Black Ops 1
   overflowed. **Fix:** ship those lists null with count 0.
6. **`EXE_CLIENT_FIELD_MISMATCH`.** Server and client registered different fields, from traps or powerups only one
   side includes. **Fix:** make the client bootstrap register the same set.
7. **Scripted animations silently do nothing.** WaW and BO1 `animscripted` take the notify first, and T6 does not.
   Our argument-reordering wrapper was built but not tested in game.

## Open questions
- Which remaining Black Ops 1 sky and animation notetrack features are worth porting?
