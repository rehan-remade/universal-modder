---
kind: game
title: "Red Faction Guerrilla destruction passthrough into Oblivion Remastered"
game: "The Elder Scrolls IV: Oblivion Remastered"
games_also: ["Red Faction: Guerrilla Re-Mars-tered"]
game_version: "Oblivion Remastered 1.512.105 (UE5.3.2); RFG Re-Mars-tered Steam app 667720"
platform: proton
engine: unreal
route: passthrough
tools: ["RE-UE4SS 3.0.1", "Proton 11.0", "retoc 0.1.5", "Blender (headless)"]
anti_cheat: "none"
status: in-progress
agents: ["Antigravity (Gemini 3.8 Flash High, first draft of the Setup, Route, How-the-game-works, Build, Verification, Gotchas and Assets text)", "Claude Code (Sonnet 5.5; wrote the ground sections and, on 2026-11-05, audited every claim against repo evidence, see docs/kb-drafts/AUDIT.md)"]
humans: []
date: 2026-11-13
links: []
tags: ["passthrough", "cross-process", "havok", "destruction", "shared-memory", "seqlock", "ue5", "lua"]
---

# Red Faction Guerrilla destruction passthrough into Oblivion Remastered

> A cross-process passthrough mod: Red Faction: Guerrilla Re-Mars-tered (RFG, 32-bit) runs hidden beside Oblivion
> Remastered (64-bit UE5.3.2 under Proton) and computes building destruction with its own Havok solver, while Oblivion
> draws the fractured house pieces. State crosses through a shared file (`/dev/shm/geomod_bridge.bin`) with a
> sequence counter (odd while writing). Evidence labels in brackets: [real run] = the game(s) ran it and an evidence file
> records it; [source] = code read, not run; [stub] = host-side test; [design] = planned; [unverified] = no evidence found.
> Real runs so far: stages 1 to 5, 7, 8 and 9 in lab copies, plus one user play-test of the 1,479-piece house
> (2026-11-04). The build is not finished: pieces rest on the wrong ground (see "Two grounds").

## Setup

- **Host (Oblivion Remastered):** Steam build 1.512.105, Unreal Engine 5.3.2, Win64 running under Proton on Linux.
  Scripting through RE-UE4SS v3.0.1 Beta (Git SHA bc66bb1, from the loader's own log) [real run]. Lab runs are headless
  under gamescope [real run].
- **Guest (Red Faction Guerrilla):** Steam app 667720, Re-Mars-tered 32-bit executable (`rfg.exe`), Proton 11.0,
  run headless with a proxy DLL that blocks the network [source: the lab launcher requires it]. The player starts at
  `-1863.6, 22.2, -1447.2` (RFG metres) [real run, `evidence/stage2-bridge.txt`]. (An earlier draft said the player is
  "parked" there to keep the zone active: the position is measured, the reason is [unverified].)
- **Inter-Process Transport:** a file in `/dev/shm`, mapped by RFG through the Wine `Z:` drive (`CreateFileMapping`
  in `src/rfg/bridge.h`) and read by Oblivion's Lua with ordinary file I/O [real run, `evidence/stage2-bridge.txt`].
- **Asset Pipeline:** convex hulls computed with headless Blender (`hulls_blender.py`); meshes cooked versioned
  (unversioned cooks crashed) on Linux and packed with `retoc 0.1.5 to-zen --version UE5_3` into IoStore files under
  `Paks/~mods/` [real run, `DECISIONS.md`, `tools/gc-build.sh`]. The fracture method itself: see Assets.

## Route and why

- **Route:** Passthrough (two processes, host draws guest geometry).
- **Choice:** the user chose passthrough on 2026-11-03 (`DECISIONS.md`); the earlier in-process work (Chaos
  GeometryCollection shards driven from Lua) was moved to `prototypes/lua-geomod/`.
- **Fallback on paper only:** `docs/PASSTHROUGH_PLAN.md` keeps a plan to rebuild the solver on a 64-bit Jolt helper
  if the two games cannot run together [design]. The helper's 44 of 44 checks ran under Wine [stub, no game].
- **Rejected options removed:** the first draft listed reasons for rejecting Chaos, ReShade-style compositing and DLL
  injection. No evidence for any of them exists in the repo [unverified], so they are not repeated here.
- **Why passthrough works, as measured:** RFG's own solver broke a custom 1,479-piece house under rockets (stage 7) and
  under hammer and arrow hits on a wall (stage 9) while Oblivion drew it [real run].

## How the game works (what we had to learn)

### Ownership Separation
- **Host (Oblivion):** Authoritative over player, camera, combat traces, NPCs, and UI. Renders all visible meshes.
- **Guest (RFG):** Authoritative over piece transforms, link graphs, stress yield, and fracture. Receives zero direct input.
- **Handoff [source: `do_swap` triggers in `src/GeoPass/Scripts/main.lua`; real run: `SWAP: real house hidden (1 actors),
  1479 prebuilt pieces shown (blast requested)` in `evidence/perf-final-native.txt`]:** the real house stays until the
  first hit, a blast request, a test request, or the attached-piece count dropping more than 40 below its maximum.
  Then Oblivion hides the real house and shows the prebuilt piece actors in one step. Pieces are built hidden in advance
  once the player is within range (the play-test built 402 of 1,479 by the first hit, `docs/PLAN_STATE.md`).
  "If RFG terminates, Oblivion freezes pieces" is a contract rule [design, `docs/CONTRACT.md`]; stage 2 shows each side
  surviving the other dying [real run].

### Units and Coordinate Space Transformation
- **Oblivion:** centimetres, Z up. **RFG:** metres, Y up, left-handed (observed at stage 3, `CHECKPOINT.md`).
- **Coordinate mapping [source + real run]:** `Oblivion_X = RFG_z*100 + site_X`, `Oblivion_Y = RFG_x*100 + site_Y`,
  `Oblivion_Z = RFG_y*100 + site_Z` (`docs/CONTRACT.md`; the same expression in `main.lua`). It is a cyclic swap, so it does
  not mirror. In use in every run; the stage 9 frame check put missing bricks a median 2.3 m from the blast
  (`evidence/stage9-hits.txt`). A dedicated asymmetric-block test is not recorded [unverified].

### RFG Mover Tracking
- Object slots live in an array at `0x2F984F4`; two index lists point into it: `0x2F98864` (`rfg_mover`, count at
  `0x2F9886C`) and `0x2F98854` (`general_mover`, count at `0x2F9885C`). Both are checked by type at run time
  [source: `src/rfg/bridge.h`; real run: stage 3]. They are arrays of 16-bit object indices, not linked lists (an earlier
  draft said "doubly linked": contradicted by `bridge.h`).
- Attached pieces: mover `+0x14C` is a shape; shape `+0x40` is a list head of 0x24-byte records (next at `+0x0C`), count at
  `+0x48`, chunk data at `+0x3C`. Every list walked matched its stored count (888 and 419, 0 mismatches)
  [real run, `evidence/piece-census.txt`].
- **Not confirmed [unverified]:** that a severed piece becomes a `general_mover` with its index at `+0x100`; nearby crates
  and shelves are also general movers and no owner link is known (`CHECKPOINT.md`). The first draft stated it as fact.

### Chunk Replacement Hook
- Custom buildings go in through an in-memory hook on the chunk-receive function at `0x936860` (`src/rfg/chunkswap.h`),
  not by rebuilding packs, so pack and `asm_pc` size limits do not apply. The hook serves chunk files from a 48 MB buffer
  reserved at DLL load, replacing `0105safehousegarage_camo` (the stock hut at the stage 3 site). RFG verifies no chunk
  checksums at load [source, and real run: a byte-identical rewrite loaded and 10 rockets broke it, `evidence/stage4-swap.txt`].
  The replacement keeps the stock zone's 46 ground-anchor indices (`docs/PASSTHROUGH_PLAN.md`).

### Two grounds: RFG's and Chorrol's do not match (2026-11-04)
- **Symptom [MEASURED, user play-test, bridge file]:** of 785 loose pieces at rest, 56% lie on a flat pad 3.6 m below the
  site centre, 31% more than 8 m below it (mean 11.7 m, down to 26 m). In the 1920x1080 film at t = 34 s large slabs
  hang in the air above the steps (`evidence/film-hq-crop-floating-slabs.png`). Cause: RFG simulates on RFG's terrain,
  Oblivion draws on its own, and the two differ outside the house footprint.
- **How the two grounds were sampled [MEASURED]:** Oblivion: 31 x 31 downward `LineTraceSingle` grid, 2 m cells, centred on
  the scene origin, 961 traces in 26 ms (`tests/ground-grid.sh`, `evidence/ground-grid-rows.txt`). RFG: its own terrain
  query (next section), same lattice, published as a bridge block (`evidence/bridge-terrain-block.bin`).
- **Ground-only filter [MEASURED, host test]:** the trace also hits roofs, trees and walls (+5 to +24 m). A 3x3 median rule
  (reject cells more than 3 m above the median of their 8 neighbours, iterate) alone replaced only 148 cells and left
  every roof wider than two cells. Adding a grey-opening rule (3 m above an erosion-then-dilation with a 13 x 13 window)
  replaces 224 of 961 cells; rejected cells are refilled from neighbour medians. A Python tool and a C header give the
  same result on the real grid. Weak spot [INFERRED]: two rows of 5.7 m on the grid edge are removed as non-ground;
  if they are a real hill the delta there is off by up to 8 m.
- **The join [MEASURED, offline, filtered; corrected 2026-11-04]:** delta = Oblivion minus RFG ground, in metres: +1.2 over
  the pad (median; +0.96 to +1.88), +3.0 on one side edge, -2.5 on the opposite edge, -8.2 and -15.4 on the two walls and
  -17.8 at the corner where RFG's ground rises 17 to 21 m while Chorrol's stays near flat. Share of cells with |delta| <= 4 m:
  100% within 10 m of the site centre, 99% within 14 m, 86% within 20 m, 66% over the whole 60 m lattice. (An earlier
  version read the RFG block 8 bytes early, since its header is 56 bytes, and shifted every RFG height by two cells; the tool
  now cross-checks the heights against the header min and max.)
- **Terrain warp (design, host-tested, NOT run in game) [MEASURED on the host only]:** draw each piece at
  `z' = z + delta(x, y) * w`, with w falling from 1 on RFG's ground to 0 at a blend height above it. The first version was
  not monotonic when |delta| exceeded the blend height (a piece rising out of an 8 m pit would be drawn sinking); the blend
  must be at least 2 x |delta|. At the walls that needs up to 43 m, so a bounded mode clamps |delta| to 4 m (blend at most 8 m,
  slope of drawn z against z at least 1/2). Cost [MEASURED on the host]: where |delta| exceeds the clamp a resting piece is
  still drawn off the ground, worst 15.6 m on the two walls. A game test of the warp has not been run.
- **The pad offset is real ground [MEASURED, `evidence/house-floor.txt`]:** `GetActorBounds` of the real house gives a
  bottom of -400 cm relative to the scene origin, and the lowest of the 1,479 pieces is also -400 cm (top +1565 for both),
  so the piece mapping has no vertical error. The frame floor is at -369.5 cm and Oblivion's traced ground at the house
  centre is -261 cm, so the real house base is buried about 1.4 m in Chorrol's terrain and the +1.20 m pad delta is real
  ground, not a trace artefact. Traces started inside the house (+150 cm) reach the same ground as with the house ignored:
  the house has no floor collision above the terrain at the centre.

### Reading RFG's terrain height (`0x83b3f0`) [MEASURED]
- `get_terrain_height` at `0x83b3f0` in RFG Re-Mars-tered (`rfg.exe`, Steam app 667720) is `cdecl` with five stack
  arguments: `float* out, float x, float z, char flag, int64_t* material`. Evidence [source]: about 107 call sites in the decompiler
  dump, all with five arguments. (The claim "56 followed by `add esp, 0x14`" was not re-checked [unverified].) It zeroes `*out` first and returns a success flag in AL,
  so a miss must be detected from the return value, not from a preloaded NaN (a host test with a stub that zeroes the output
  caught that design error before it reached the game). Most callers pass flag 0 and a null material.
- **Live result:** called from the game thread inside the bridge tick, 3 s after the site is known, it found 961 of 961
  cells in under 1 ms. RFG's ground around the site: a flat 15.0 m pad ringed by 18 to 19 m ground on two sides and hills
  of 30 to 60 m at the far corners, i.e. a pit with walls where Chorrol is flat.
- Published as a seqlocked block at bridge offset `0x70000` (magic, seq, centre, step, 31 x 31 floats in RFG metres).

### RFG static floor: the recipe WORKS [real run, 2026-11-05]; the rest below was the study
A live test created the box with this recipe (valid handle, filter `0x00010002`, quality 0, motion 5, no crash; `evidence/floor-box.txt`). It did not stop the pieces, because the hull frame was wrong, not the floor (chunk note, gotcha 5). The text below is the original study.
A static invisible box under the pad would stop pieces falling into pits. Two research reports named different RFG
functions; reading the decompile (not running it) gives this candidate recipe, **none of it tried in the game**:
a zeroed 0x104-byte descriptor, `0x8168f0` (fastcall) to set defaults, shape type 3 (box, full sizes) with fixed motion
and quality values copied from the road collider caller `0x91b210`, then `0x83dba0` (cdecl, one argument) which
creates the rigid body and adds it to the Havok world. Field meanings (quality 0, motion 5) are inferred from Havok's enums;
the collision layer and filter value are unknown; no live caller creates a static type-3 box; it must run on the game
thread (Havok allocator in thread-local storage). A flat floor fills pits only: on walls where RFG's ground is higher
pieces would still rest on the slope. Details and probes: `docs/RFG_FLOOR_RECIPE.md` in the project repo.

## Build steps

Labels as above. The generators are in the project repo; none of the game's data is in it.

1. **Fracture and piece export [real run, `CHECKPOINT.md` stage 6].** The 46 house meshes (216,058 triangles) were exported
   from Oblivion's packages; 29 of 63 meshes match the live bounds exactly, the rest are Nanite fallbacks up to 9 cm smaller.
   The house is fractured into 1,479 pieces; convex hulls are computed per piece (about 1% of hulls are strongly
   non-convex). The piece table is `site_pieces.lua`. The fracture algorithm is not documented in the repo
   [unverified]; an earlier draft said "Voronoi" and "convex pieces with broken-stone inner faces".
2. **Chunk generation [real run, stages 5 and 7].** `src/chunk/gen/genchunk.py` and `src/chunk/house/make_house.py` write the
   replacement chunk files (1,479 pieces, convex hulls, 5,078 links, 46 anchors) to match the stock chunk's layout.
3. **Cook for Oblivion [real run].** Cook the piece meshes versioned for UE5.3.2 and pack with `retoc to-zen`.
4. **Deploy and launch [real run, `tools/rfg-lab.sh`].** Start RFG headless with the DLL pointed at the chunk files; its menu
   appears about 45 s in and the level load must wait until 50 s; confirm the bridge counters advance; start Oblivion with
   UE4SS and the `GeoPass` mod.
5. **Play [real run].** `GeoPass` builds the piece actors hidden before the first hit, about 10 ms of game-thread time per
   Lua pass (`docs/REALTIME_PLAN.md`). A hit or blast triggers the swap.

## Verification

Evidence is in `evidence/`; every result is a lab copy of both games, headless under gamescope unless noted. Nothing here
was reproduced on a second machine.

- **Stages 1 and 2, transport (`evidence/stage2-bridge.txt`) [real run]:** frame counters in both directions; both survive an
  Oblivion teleport and a save load. The 2.0 s heartbeat timeout in the first draft is [unverified]: the only heartbeat code
  found belongs to the older helper protocol.
- **Stage 3, motion (`evidence/stage3-stream.txt`, `stage3-rfg-vs-blocks.mp4`) [real run, with caveats]:** a stock building hit by
  RFG rockets; the stream rose from 34 to 50 movers after 12 rockets in one run and from 161 to 286 after 7 in another;
  Oblivion drew them as axis-aligned boxes, floated 180 m up.
- **Stages 4 and 5, custom chunk (`stage4-swap.txt`, `stage5-wall.txt`) [real run]:** a byte-identical rewrite of the stock hut
  loaded; a generated 900-brick wall then loaded as `rfg_mover 4a020006`, and 14 rockets broke it into 167 to 314 streamed
  pieces with no crash or dialog. Caveat from the notes: RFG's own picture of the generated pieces is misplaced.
- **Stages 7 and 8, house (`stage7-house.txt`, `stage8-swap.txt`) [real run]:** the 1,479-piece house replaced the stock
  building in RFG; 12 rockets brought it down; Oblivion hid the real house and showed 1,479 cooked pieces on the first hit
  (stage 7 was filmed with bounds boxes). Pieces read slightly darker (a stage 8 caveat).
- **Stage 9, combat coupling (`stage9-hits.txt`, `stage9-knock.txt`) [real run, on the 900-brick WALL, not the house]:** 7 of 8
  hammer swings hit; the first 3 took the wall from 894 to 730 attached bricks and it collapsed after the 7th (9 left); 5 of 6
  spawned arrows hit (not a bow); spells are not verified. The hit kind is `mp_commando_melee`. Knockdowns passed in 2 of 3
  runs (`CHECKPOINT.md`); the 400 cm radius is from `CHECKPOINT.md`. The first draft said the war hammer and arrows broke the
  1,479-piece house: that combination has no evidence file; the house fell to rockets and to a bridge blast request.
- **User play-test, 2026-11-04 [seen by the user, log in `docs/PLAN_STATE.md`]:** the house swapped and collapsed with the
  ground problems described below.
- **Not verified:** a second machine, spells, regrowth, the terrain warp and floor in game, and the lighting match.

## Gotchas

1. **RFG draws generated pieces in the wrong places in its own view.** Seen at stages 5 and 7 [real run]. Cause not
   identified [unverified]; the first draft's explanation about "internal world-position assumptions" had no evidence.
   Harmless here because Oblivion draws and RFG is hidden.
2. **Crash in a deintersect routine (`0x14486db30`, `exe+352fa7a`, `exe+486e0a5`).** [real run, `CHECKPOINT.md`,
   `DECISIONS.md`] A component tick sweeps, then calls `GetBodyInstance` (vtable `+0x7c8`) on hits without a null check; a
   GeometryCollection component returns null. **Fix that worked in the older GeometryCollection route:** `geomod_guard.dll`
   points the GC vtable slot `0x14731d280` at the base `GetBodyInstance` (`0x14357a320`); one strict regression run passed.
   Scope: this was found on the shard route; the current piece actors are static meshes, and no crash evidence from them
   is recorded. `DECISIONS.md` writes the function once as `0x14486db40`: one of the two is a typo.
3. **Pieces read slightly darker than the intact house.** Seen in stage 8 and the 34 s film [real run]. The first draft's cause
   (missing vertex ambient occlusion and lightmap UVs) is [unverified]; the lighting measurement was retracted on 2026-11-04
   because the swap had not run. What is known: the wall material `MIC_chorrolhouseupper01_01` (root `M_Layered_Base`)
   renders on cooked pieces and cut faces use `MIC_Rubble01` (`DECISIONS.md`, `CHECKPOINT.md`).
4. **Loose pieces vanish or run out.** The first draft blamed a load balancer that culls outside the camera frustum
   [unverified; the frustum part is not in the decompile notes]. What the notes do show [source, `research/RFG_STRESS_SOLVER.md`]:
   the object balancer works from a step-time pressure, and pools are fixed (`rfg_mover` 4000, `general_mover` 3072,
   `object_debris` 500; an empty pool returns null and evicts nothing). Persistent rubble is implemented in the lab DLL (hold
   `destruction_sweep` off while the render pool has room, `src/rfg/proxy.c`) [source; kept-rubble runs in
   `docs/PERFORMANCE_PLAN.md`]. A Lua "lingering piece cache" was not found in `main.lua` [unverified].
5. **Two Proton prefixes.** The plan assumed normal Windows shared memory might not cross prefixes
   (`docs/PASSTHROUGH_PLAN.md`); a file in `/dev/shm` through the `Z:` drive does cross [real run, `DECISIONS.md`]. Named
   pipes and named mappings were not tested [unverified].
6. **Pieces sink below the ground or float in the air.** Cause, partly open: RFG's terrain differs from Chorrol's outside
   the house footprint (see "Two grounds"). Separately [real run, `evidence/r1-terrain.txt`, bridge-replay report]: RFG's
   terrain under the pad is solid (heightfield and ray both 14.98 m), yet 41% of loose pieces (293 of 713 in the captured end
   state) end more than 3 m below RFG's ground at their own x,z; the lowest seen mid-run was 21.8 m below, the end-state pile is
   about 10 m deep. Root cause not proven (suspect: the collision-layer matrix between loose-piece and terrain layers).
   **Update 2026-11-05: root cause found [real run].** The generated pieces' collision hulls were in chunk-local instead of piece-local
   coordinates, so pieces fell through terrain and through a fixed test box alike; the sunk share fell from 35/63/88/81% by height bin to
   about 11% (`evidence/hullfix-sink-bins.txt`, `convex-sink-bins.txt`). The layer matrix, terrain streaming, a terrain hole,
   initial penetration and tunnelling were all measured and ruled out; full story in gotcha 5 of the chunk-generation note.
   The remaining 10% are thin pieces that fall below about y -17.5, where RFG deletes them. Display-side fixes (terrain warp, floor clamp)
   stay on for the ground mismatch, not for sinking.
   A raw line-trace grid is not ground: roofs, trees and walls need a filter.
7. **First in-engine film washed out or hung.** [real run, `docs/PLAN_STATE.md`, `evidence/film-hq.out`] On-demand
   `CaptureScene()` stopped after 62 frames and came out washed out (no exposure history; a second try hung after 3
   frames). Capturing every frame gave 287 frames in 53.5 s at 1920x1080 (5.3 fps, median gap 183 ms).
8. **A "valid" test that never swapped.** [real run, `docs/PLAN_STATE.md` 2026-11-04 retraction] A global set from the lab eval is
   invisible to the game's Lua (separate Lua states). Fix: request the swap through the bridge file (u32 at `0x7F000`) and
   require the `SWAP: real house hidden` line. An earlier similar failure: a nil global in `do_swap` hid the swap in every
   perf run from commit 227f785 until its fix (`CHECKPOINT.md`).

## Assets

- 46 original house meshes, 216,058 triangles, exported from Oblivion's packages [real run, `CHECKPOINT.md`].
- 1,479 piece meshes with convex hulls (Blender used for hulls) [real run]; fracture algorithm [unverified].
- Cooked into IoStore files under `Paks/~mods/` via `retoc 0.1.5` [real run].

## Cost and time

- Work spanned 2026-11-02 to 2026-11-05 over many sessions [git history]. No external service costs recorded.
  "Zero external network dependencies" from the first draft is [unverified]; some research was done on the web.

### 2026-11-13: where this route went
Since 2026-11-05 the project no longer passes RFG's simulation through. RFG's rules are rebuilt in our own code inside
Oblivion and Unreal moves the pieces; the passthrough described here is kept as the measuring oracle (the same house as a
chunk in the real RFG, the same rockets). What that taught us is in the note "Red Faction Guerrilla's destruction rules
rebuilt inside Oblivion Remastered, measured against the real game". Everything above is as audited on 2026-11-05.

## Open questions

- **Smoothness:** Lua decodes snapshots at 10 Hz (not 9); a native interpolator now moves pieces every frame and was the
  best measured variant, with 19 to 20% frozen frames still measured (`docs/REALTIME_PLAN.md`, `docs/PERFORMANCE_PLAN.md`).
  The "60 ms in the past" figure was a proposal ("about 0.6 of a snapshot interval") [design].
- **Spells:** not verified; the hook point is not chosen.
- **Ground match:** the terrain warp and the RFG floor are host-tested or read-only studies; both need live probes
  (settled pieces within 20 cm of traced ground, no floating slab in the 34 s film frame, fps unchanged).
- **Rubble persistence:** a lab-DLL patch exists and is on by default in the lab; its effect on the full pool limits
  (`object_debris` 500) is not separately measured [unverified].
