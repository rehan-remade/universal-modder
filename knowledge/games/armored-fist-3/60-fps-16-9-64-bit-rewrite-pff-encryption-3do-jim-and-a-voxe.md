---
kind: game
title: '60 fps + 16:9 + 64-bit rewrite: PFF, encryption, 3DO/JIM and a VoxelSpace renderer'
game: Armored Fist 3
games_also: []
game_version: v1.00.20 (retail/Steam; AF3.EXE 2,433,024 bytes, SHA-256 52ED80CC8F0282F050789EFB384342DC888200997F26BDD2EBF706D814B97EA7)
platform: windows
engine: native
route: native-hook
tools: [rustup 1.99 GNU host, WinLibs MinGW-w64 i686+x86_64, cdb x86, Ghidra 12.1.3, windows-mcp]
anti_cheat: none found by um scan
status: in-progress
agents:
- opencode (deepseek-v4.1-flash)
humans: [thetunguskaevent]
date: '2026-10-08'
links:
- "https://github.com/Novahq-net/NovaResearch"
- "https://github.com/Novahq-net/NHQTools"
- "https://github.com/Novahq-net/Nova3di"
- "https://codecs.multimedia.cx/2024/08/looking-at-nova-logic-fmv-formats"
tags: [novalogic, voxel-space, pff, 3do, jim, terrain, native-hook, rust, reimplementation]
---
# 60 fps + 16:9 + 64-bit rewrite: PFF, encryption, 3DO/JIM and a VoxelSpace renderer

> Armored Fist 3 (NovaLogic Voxel Space 32, 1999) was taken from a 4:3/30 fps
> engine to **60 fps with game speed unchanged** in the real game, using a Rust
> 32-bit launcher + injected payload (runtime hooks only; the on-disk game is
> never touched). That's verified at 1152x864 by counters/readback (loop
> 59.8/s, world renders 59.4/s, sim tick 30.25/s unchanged, 62% of one core,
> 60+ s soak); at 1920x1080 the 32-bit game is render-bound at about 42
> renders/s, with a 16:9 HUD fixed up. In parallel, a 64-bit program written
> from scratch in Rust reads the user's own PFF archives and renders the
> terrain plus the placed scenario objects in its own VoxelSpace renderer at
> 60 fps at 1920x1080, checked by rendered frames against the game's own.

## Setup

- Windows 11 x64, retail AF3 **v1.00.20** (Steam/retail; `AF3.EXE` 2,433,024
  bytes, SHA-256 `52ED80CC...7EA7`), complete install with `*.PFF` and the real
  `AF3INTRO.BIK` (336,378,083 bytes).
- The game is still sold on Steam (app 32710). The 1999 disc release had a
  simple disc check; PCGamingWiki lists v1.00.20 among its retail patches.
- The game is 32-bit, software-rendered, DirectDraw; no anti-cheat, no loader.
  It had NovaWorld online play; everything here was tested single-player,
  offline.
- Toolchain that worked:
  - Python 3.12 + `keystone-engine`/`capstone` (cave builders + probes).
  - `cdb.exe` x86 (Windows SDK Debuggers) for live readback.
  - Rust 1.99 `stable-x86_64-pc-windows-gnu` + targets `i686-pc-windows-gnu`
    and `x86_64-pc-windows-gnu`.
  - **MinGW linker:** rustc's `*-windows-gnu` targets need `libgcc`/`libgcc_eh`;
    LLVM-MinGW ships compiler-rt instead and **fails to link** rustc output.
    Use WinLibs GCC (real MinGW-w64): i686 build extracted locally, x86_64 via
    winget `BrechtSanders.WinLibs.POSIX.UCRT`. (Rust's separate
    `*-pc-windows-gnullvm` targets are the ones meant for LLVM-MinGW.)
  - `windows-mcp` (real mouse/keyboard; the game only reads input with the
    cursor inside its window) driven through its stdio JSON-RPC client.
  - Ghidra 12.1.3 + JDK 21 for static reading (read-only).
- Format references, credited: the Novahq-net community's
  [NovaResearch](https://github.com/Novahq-net/NovaResearch) docs (PFF, 3DO,
  AI, RTXT), [NHQTools](https://github.com/Novahq-net/NHQTools) (C# parsers and
  the SCR cipher), [Nova3di](https://github.com/Novahq-net/Nova3di) (3DI and AI
  composition, including the AF3 attachment tables), and
  [a post on NovaLogic's FMV formats](https://codecs.multimedia.cx/2024/08/looking-at-nova-logic-fmv-formats)
  (KDV). The mod's own code is in the author's private repo.

## Route and why

Two tracks:

1. **Runtime patcher + injected payload (32-bit).** AF3 has no loader and the
   existing project already proved byte patches + hand-assembled caves applied
   to a `CREATE_SUSPENDED` process. The new deliverable keeps that model but
   moves it to Rust: `af3full.exe` validates the EXE, spawns it suspended,
   applies the base byte patches and injects `af3full_payload.dll`, which
   installs a single frame-pacing hook. Nothing is written to disk in the game
   folder and the DLL lives beside the launcher.
2. **64-bit rewrite from scratch (`af3modern`).** The binary cannot be "ported":
   it is 32-bit machine code with self-modifying MMX and 32-bit pointers. The
   64-bit path reads the user's own archives (PFF/3DO/JIM/terrain) and renders
   with a modern Rust renderer. It also sidesteps the MMX rasterizer's cost at
   1080p+ (replacing that rasterizer inside the 32-bit game is still open).

Rejected: a proxy DLL (`winmm.dll` or a DirectInput DLL) in the game folder.
Loaded in-process, it would have the same access as the injected payload (and
Rust can build one), but the launcher keeps the game folder untouched. Also
rejected: patching the frame rate by halving the tick (it doubles game time —
measured, see Gotchas).

## How the game works (what we had to learn)

**Timing.** The engine is a 33 ms fixed-step loop. The tick rate is governed by
a synthetic clock constant (`add [0x5D1D00],0x21`, immediate at file
`0x16A03A`), not by the divisor at `0x569F71`: patching only the divisor does
nothing, and patching the clock constant to 16 doubles the tick rate **and
doubles tick-derived game time** (the displayed mission clock ran 2.09 s/s).
Keep the sim at 33 ms; raise only the render rate.

**Render pacing.** The render throttle compares `now - last_render` against 33
ms (`cmp eax,0x21` at VA `0x56A494`, immediate at file `0x16A496`); with the
stock loop period (~24 ms: `Sleep(11)` + ~13 ms render) terrain only redraws
~21/s against a 30/s simulation. The `Sleep(11)` helper at `0x40F51B` has
exactly **one caller: the main loop at `0x569CF0`**.

**Loading is timing-sensitive.** The main loop runs during mission load; making
it spin (Sleep 0/4, or even a wait that only engages when the loop is slow)
breaks the load with a `MEMMGR: Undefined Memory pointer` modal. A hook must
reproduce stock behavior until the mission is actually live. The frame counter
`[0x5D1CF4]` and the framebuffer pointer `[0x651838]` are both 0 through the
whole load and flip together at mission start — that pair is a reliable
"mission live" gate.

**Renderer.** World renderer entry `0x632930` → band generator `0x633FCD` →
MMX rasterizer `0x63472C` (~12.8 ms at 1152x864). The rasterizer is
**self-modified at runtime** (live code uses `shr eax,0x1e` and a per-run heap
table), so static disassembly of that address is stale; hook the indirect call
site `0x63460C` or read live memory. Band culling breaks when
`(height-1)*pitch*2048` overflows signed 32-bit (`0x6342C6`, `jns` → `jmp` when
it does).

**Archive format (PFF).** 20-byte header (header length, `"PFFx"`, entry count,
entry length, entry-table offset), data blobs, entry table, footer. Entries are
32 bytes (PFF3 variant 1: `DeadSpaceFlags, DataOffset, DataSize, Timestamp,
Name[16]`) or 36 bytes with a trailing CRC; PFF2 reuses the first dword as a
CRC. `AF3.EXE` uses PFF3 for TERRAIN/RESOURCE/MENUS/NORMAL/VOICE/AF3MED and
PFF2 for MISSIONS/CORE/MAPS. (NovaResearch and NHQTools list AF3 as PFF3 only
and describe PFF data as unencrypted, so the PFF2 archives and the pad below
are this note's own finding.)

**The encryption (the unlock for all mission data).** Every entry of a **PFF2
archive is XOR-padded with a fixed 32-byte repeating key**; PFF3 archives are
plain. The pad was derived from 170 files stored plain in RESOURCE and padded
in MISSIONS (identical sizes; every twin XORs to the same sequence) and
verified on all 1729 `3DO` entries in the padded archives (they decrypt to
`"3DO1"`), both KDV movies
(`"xVDK"` header) and all JIM files. Pad:
`00 78 2e 7c 70 07 c2 77 e7 80 3c 17 be 38 03 e1 bb f3 c0 1e 0b df 9c 01 f0 5d
f9 e0 0f 85 ef ce`. The NHQTools SCR/ARX cipher does **not** apply to AF3
(brute-forced all 2^32 keys — no match).

**Terrain.** Per map `<NAME>_D.R16` = `"R16a"` + u32 width + u32 height +
w*h u16 LE heightmap (1024x1024, heights ~2761..15958); `<NAME>_C.TGA` =
1024x1024 24bpp bottom-up colormap; `<NAME>_M.PCX` = 8bpp RLE material map;
`<NAME>_CM.CAL` = text class table (`Adt1`, `Cdt3`, `Ags3`, ...). The two
`MAPS.PFF` `KDV` blobs are not terrain: they are NovaLogic FMV videos
(decrypted header `"xVDK"`, 640x480).

**3DO models.** 92-byte header (`"3DO1"`, name, bbox, counts, offsets), then
textures (28 B), vertices (44 B), triangles (32 B), normals (16 B), mesh
entries (12 B), hardpoints (16 B). Triangle vertex/normal/texture references are
**byte offsets into their arrays**, not indices. Standalone models are shifted
left by 7 at load. Textures carry a 12-byte name, an alpha byte, a flat colour
and render flags. **Axes: z-up, x mirrored** — Nova3di's converter maps
`(-x, z, -y)` into its y-up OBJ space, i.e. `world = (-x, y, z)` for a z-up
renderer; the palm trunk / tank height run along z (check the vertex
distribution, not the header bbox). Mesh-entry offsets beyond the body's
bounding diagonal are sentinels and must be ignored, or AI composites grow
giant stray planes. AI parts are one LOD tier each (`_H*`/`_M*`/`_L*`); the
`_L` parts are coarse boxes, so pick a single tier.

**AI manifests.** ASCII: a type-id header line, then environment blocks
(`>G` green, `>D` desert, `>S` snow, `>N` night, `>R`/`>B` team) each listing
child `.3DO` parts, then `>IDOV` (id), a 5-line `>DATA` block (LOD cutoffs in
metres + collision flags) and an optional `>LEAF` count. Part names are **LOD
variants** (`..._L01/_H02/_L03/_H04` pairs + shared parts), not additive
pieces; composing a full vehicle needs the engine's per-type assembly tables
(solved later, see Open question 2 and the Update section). The first line may be a comment with the type on the next line
(`;TANKJACK` / `43 ;type`), and part lines can carry a trailing comment
(`TRAP_L.3DO ;SINGLE ?`).

**JIM missions.** After the PFF2 pad: 9-byte header (a start record), then fixed
9-byte records `[tag u8][x u16 LE][y u16 LE][value u8][00 00 00]`, zero
padding, then a NUL-separated ASCII object table. Tags: `0x7f` objectives
(the `value` indexes the numbered labels), `0x07` units, `0x11`/`0x12` spawns,
`0x01` start. `C6M7.JIM` resolves to `1-START POINT`, `2-CP ALPHA`,
`3-OBJ ACKERMAN`, `4-OBJ HAINES`, `5-CP BRAVO`, `6-RELEASE POINT` plus unit
records. All 85 missions parse (1569 records; `C2M9.JIM` is a 1-byte
placeholder). JIMs turned out to be mission-editor documents that the game
never loads (Open question 1); the game's missions are the BMS scenarios below.

**CORE.PFF** holds the same JIMs plus `.ORD` per-mission briefing text
(`>TEXT`-style markup) and per-map `.INF` info text (94 maps `MP01..MP94`) and
`.POS` binary position tables. Each scenario's map comes from its own TRN file
(`dg2_dy03.trn` -> `AFDG2`, Open question 1).

**BMS scenarios (the mission text/placement files).** `*.BMS` in MISSION.PFF /
UPDATED.PFF are **not** PFF2-padded: they are stored raw and end with a clear
`NoVa` tag. Decrypt with the NovaLogic 8-byte block transform (AF3.EXE VA
`0x570845`, mission manager): per 8-byte block `eax = rol(eax, 9)` (seed
`0xfade2bad`, `+0x1abb09` when the sign bit is set), `ebp = ror(ebp, 1)` (seed
`0xace4dead`), then `dword0 = xchg bh,bl(u32le ^ eax)` and
`dword1 = ror16(u32le ^ ebp)`; only `(len-4)/8` blocks are processed. The
payload is ASCII scenario text (`;v1.xx AF3MED`, `;Mission:`, `>WPNT`
waypoint lists, `{mission}` triggers, object placements) followed by a binary
trailer. Coordinates are 32-bit **21.11 fixed point**; the engine's HUD
formatter (`AF3.EXE` VA `0x5481a8`) divides the player's world position by
`0x280000` = 2^21 * 1.25, so the map is **1280 world units across** and the
heightmap pixel is `value / 2,621,440` (not `value / 2^21`; the HUD's second
number is the **negated** y, a UI flip only). Headings are 32-bit turn
fractions (`value * 360 / 2^32` degrees). Object lines are
`NAME.AI,variant,id,x,y,heading,...` (scenery omits the id); `stpl` lines are
route segments and `stid` labels the next unit. **v1.21 battle scenarios**
(UPDATED.PFF `F3RBGM*`/`F3CTFM*`/`F3TDMM*`) have **no `OBJECTS included`
marker**: their placements follow the trigger block directly after
`END`/`0,1`. Bare tokens (`stlm`, `sttk`, `STCN`, `stac`) are markers, not
models — only names with `.AI`/`.3DO` are placements. Sibling `*.BIN` briefings are
an `RTXT` container (stored plain) with the title and the in-game messages.
Sibling `*.INF` audio scripts use the **same block cipher** (raw + `NoVa`):
`>SC01` sections of `.SQUAK`/`.DELAY,N`/`<file>.wav ; radio line`; scenario
triggers reference them as `EVENT,14,SCxx` (kind 8 is the `MSxx` text message).
All 71 MISSION.PFF INF decode (some have `;Shipped Dialog For AF3` comment
headers and lowercase `.squak`).

**3DI v7 models (AF3MED.PFF scenery/units).** 124-byte header (`3DI\x07`,
12-byte name, `lod_count` at +0x14), `u32 texture_count`, then a 184-byte LOD
header (`lod_data_size` +0x14; vertex/normal/face counts at
+0x80/+0x88/+0x90; mesh/hardpoint/material/volume counts at
+0x98/+0xA0/+0xA8/+0xB0). LOD data order: vertices (8 B: i16 x,y,z + u16
mesh), normals (8 B), faces (72 B: `u[3]` i32 +4, `v[3]` i32 +16, `vi[3]` i16
+28, `ni[3]` i16 +34, material u32 +0x44), meshes (112 B), hardpoints (12 B),
volumes (140 B), materials (120 B: 12-byte name, flags +0x10, flat RGB +0x28).
Face `vi` are **mesh-relative**: resolve with the per-mesh vertex counts in
order. AF3 stores `texture_count = 0`; the **material names are the texture
names** (`FROND01` -> `FROND01H.PCX` in RESOURCE.PFF). Cut-out foliage uses
palette entry 0 as a color key (purple-ish); remap it to a sentinel and skip
those texels, or the trees render their key color.

## Build steps

32-bit (in the game folder, nothing installed into it):

```text
rust/build.ps1 full        # builds af3full.exe + af3full_payload.dll (i686)
rust/target/i686-pc-windows-gnu/release/af3full.exe
```

The launcher reads `AF3_GAME_DIR` (defaults to the repo folder), validates the
EXE bytes, patches, injects, resumes, prints the pid. `AF3_NO_PAYLOAD=1` skips
injection for A/B tests; `AF3_FRAME_WAIT_MS` (payload) sets the frame target
(default 16; 0 disables); `AF3_RENDER_GATE_MS` (launcher) sets the render gate
byte (default 0).

64-bit rewrite:

```text
rust/build.ps1 modern      # builds af3modern.exe (x86_64)
af3modern pff list <archive.pff>
af3modern terrain TERRAIN.PFF AFD1 --out preview.ppm
af3modern render TERRAIN.PFF AFD1 --x 300 --y 200 --follow --heading 90 --out frame.ppm
af3modern run    TERRAIN.PFF AFD1 --width 1920 --height 1080
af3modern model  MISSIONS.PFF BMP2B_M1.3DO --out model.ppm --obj model.obj
af3modern jim    MISSIONS.PFF C6M7.JIM
af3modern ai     RESOURCE.PFF MLRS.AI --out composite.ppm
af3modern scene  TERRAIN.PFF AFD1 MISSIONS.PFF BMP2B_M1.3DO --obj-x 330 --obj-y 200 --out scene.ppm
af3modern trn    MISSION.PFF DG2_DY03.TRN
af3modern bms    MISSION.PFF F3C01M01.BMS --text
af3modern 3di    AF3MED.PFF PALM.3DI
af3modern run    TERRAIN.PFF AFDG2 --scenario MISSION.PFF F3C01M01.BMS \
                 --models MISSIONS.PFF --med AF3MED.PFF --resource RESOURCE.PFF \
                 --tex RESOURCE.PFF --trn MISSION.PFF DG2_DY03.TRN \
                 --font NORMAL.PFF AF3FNT8.FNT
af3modern bench  TERRAIN.PFF AFD1 --width 1920 --height 1080
```

Verification harness (Python, in the private repo's `AF3_Mod/scripts/`): `AF3_VerifyMode.py` (the
27-assertion acceptance gate), `AF3_TimeProbe.py` (sim tick / render stamp /
accumulator), `AF3_RustStats.py` (named-mapping stats from the payload),
`AF3_DriveToMission.py` (menus → mission via windows-mcp), `AF3_LoadWatch.py`
(load-state timeline).

## Verification

- **32-bit, mode 6 (1152x864), 60+ s soak:** payload hook calls 59.8/s, world
  render stamp 59.1-59.4/s, sim tick `[0x5D1CF4]` 30.25-30.34/s (unchanged),
  62% of one core, process responsive, no modal, no access violation.
- **A/B:** with `AF3_NO_PAYLOAD=1` the same launcher reaches a mission, proving
  the patch set is byte-identical to the old Python launcher's.
- **Render gate:** with the gate left at 16 ms the loop (16.7 ms) only rendered
  39.5/s (2 of 3 loops); gate 0 gives ~59-60/s.
- **64-bit:** headless bench 1.72 ms/frame at 960x540, 3.79 ms at 1920x1080;
  the interactive window reports **60 FPS at 1920x1080** in its title; the
  numeric gate `AF3_ModernVerify.py` sustains min 56-57 / mean 59.5 fps at
  1080p (render 7-10 ms + copy ~1 ms + present ~1 ms). 2560x1440 is
  render-bound (18.6-21.9 ms -> ~42 fps).
- **32-bit at 1080p with the Rust payload:** 41.7 world renders/s (render-bound;
  the frame-wait hook rarely sleeps). RDTSC pass profile of the world entry
  (~24 ms): **terrain draw `0x633417` = 76.5% (18.35 ms)**, sprite/object pass
  `0x56ED20` = 23.5% (5.64 ms), everything else ~0. That 18.35 ms is the exact
  target for real-game 60 fps at 16:9.
- **Formats:** PFF parse validated by re-reading every archive (entry counts,
  live byte coverage ~100%); the pad by decrypting all 1729 3DOs to `"3DO1"`;
  3DO/JIM/AI parsers have unit tests plus real-file round-trips (OBJ export,
  wireframes, scene renders, material histograms).
- **Later sessions (see Update):** vehicle composition from the typed AI
  manifests (wireframes for M1A2, BMP, BRDM, OLIFANT and 2S6M), and the 16:9
  HUD in the 32-bit payload (window fit, strip text, minimap, vehicle/status
  icon) with the 4:3 mode gate still 27/27.
- **NOT verified:** 60 fps at 1080p in the 32-bit game (about 42 renders/s, see
  above); 2560x1440 in the 32-bit payload; 3DO/3DI scale against the engine's
  world units (Open question 3).

## Gotchas

1. **Halving the tick doubles game time.** The synthetic clock constant
   (`add [0x5D1D00],0x21`) governs the tick rate; setting it to 16 raised sim
   ticks to 62.5/s and the mission clock to 2.09 s/s. **Fix:** keep 33 ms and
   raise only the render rate. (The old project's two-site `AF3_TICK_MS` knob
   only changed the divisor, so it silently did nothing.)
2. **A frame-wait hook that engages during loading breaks the load** with
   `MEMMGR: Undefined Memory pointer`. The loader needs the stock loop cadence.
   **Fix:** a hand-built stub that calls the original `Sleep(11)` helper unless
   `[0x5D1CF4] != 0 && [0x651838] != 0` (mission live), then waits to the
   16.6 ms target; preserve all registers with `pushfd/pushad`.
3. **The render gate must be 0** (or well under the loop period): a 16 ms
   threshold against a 16.7 ms loop skipped every third render (39.5/s).
4. **The PFF2 XOR pad is per-archive-version, not per-file:** PFF2 archives
   (MISSIONS/CORE/MAPS) are padded, PFF3 are not. Apply
   `plain[i] = cipher[i] ^ PAD[i % 32]`.
5. **3DO references are byte offsets** (vertex 44 B, normal 16 B, texture 28 B);
   dividing by the stride is required, and out-of-range refs must be rejected.
6. **JIM record scanning must stop at printable ASCII**, otherwise the `Player`
   string parses as a bogus record (tag `0x50`); also handle the 1-byte
   placeholder mission.
7. **KDV is a video**, not a terrain/map blob (NovaLogic FMV, 4x4 block modes).
8. **Hot-loop integer division is the killer:** `rem_euclid` per sample made the
   renderer ~30x slower; power-of-two bitmask wrapping plus hoisted span
   strides took 960x540 from 32 fps to ~580 fps headless.
9. **`Sleep(1)` is 15.6 ms** until the process calls `timeBeginPeriod(1)`; 60
   fps pacing needs it (and an absolute per-frame schedule).
10. **rustc GNU targets + LLVM-MinGW do not link** (`-lgcc`/`-lgcc_eh` missing).
    Use real MinGW-w64 (WinLibs) for both i686 and x86_64.
11. **The MMX rasterizer's static bytes are stale** (self-modified at runtime):
    always read the live code/table before touching it.
12. **`AF3INTRO.BIK` is load-bearing** for the wrapper's validation; the intro
    spawns a `BINKPLAY.EXE` child that can zombie and hang the boot wait — kill
    it by its exact PID (`um win kill`), never by image name.
13. **At 16:9 the engine still draws its own strip text** at 640-space x~0
    (clipped left), coloured by whatever palette entries the mod last wrote.
    The glyph cave's band guard (cursor y >= 429*pitch/640) does not catch the
    message row. The mod's own strip is the centred 2.25x copy; skip-engine
    variants are unreliable.
14. **Some AI-shared 3DO parts store coordinates relative to a ±2^29 origin**
    (e.g. `MLRX_L` y ~ -2^29 + real); shift the whole axis back when the
    bounds are all beyond ±2^28 or the composite collapses to a dot.
15. **BMS scenarios are the trap:** neither raw nor pad-removed bytes are text,
    and XOR of two BMS files looks *text-like* (their shared header cancels),
    which reads like a shared stream cipher. It is really the weak 8-byte
    block transform above; the give-away is that the ciphertext XOR of two
    files stays text-like everywhere, and the derived "keystream" only agrees
    while the plaintexts agree.
16. **AI manifests use lowercase `>g`/`>d`/`>s` markers**, and HUT/PALM-style
    files declare all environments first and then list **one shared parts
    list** (`>g >d >s` then parts, terminated by `<<`); M1A2-style files list
    per-environment parts separated by `<`. Infantry (`INFENM/INFUS`) parts
    are animation frames, so use one part, not the LOD grouping.
17. **Scenario object names are editor aliases** (`TREPALM`, `Bana1`, `SHACK7`,
    `infenm`, ...). Resolve them by hand: 3DI in AF3MED.PFF (`PALM.3DI`,
    `BANA1.3DI`, `OLIFANT.3DI`, `BMP-2.3DI`, `SSIGN2.3DI`, ...), else AI/3DO in
    MISSIONS.PFF (`PALM1.AI`, `AFSHK7.AI`, `ELEPHANT.AI`, ...), else
    RESOURCE.PFF (`INFENM.AI`, shared AI parts). The `;NN` comment on each
    line is an editor type index, not a filename.
18. **PCX textures can be non-square and color-keyed** (64x256 trunks); the
    key is palette entry 0 and its RGB varies per texture
    ([141,22,181], [95,42,122], [128,0,128]), so detect it by "red and blue
    dominate green", not a fixed color.
19. **The live scenario buffer is the ground truth for cipher work:** the
    decrypted text of the running battle can be dumped from process memory
    (scan for `;Owner` / `;v1.`), and its fixed-point placements match the
    engine's globals byte-for-byte. `AF3_ScanScenario.py` does the scan.
20. **Scenario coordinates are not `value/2^21` map pixels:** the engine HUD
    divides by `0x280000` (2^21*1.25), i.e. the map is 1280 world units across
    with 1.25 units per heightmap pixel. Using 2^21 places every object 25%
    too far out (and pushed some past the 1024 map edge). The HUD's y is
    negated for display only; the terrain/renderer y is not flipped.
21. **With hundreds of placed objects the object pass dominates at 1080p**
    (41 ms single-threaded before culling). Per-object frustum culling,
    backface culling, hoisted barycentric reciprocals and a power-of-two
    texture-wrap mask take it to ~20 ms; splitting the frame into horizontal
    bands with one thread each (disjoint row writes into the same frame/zbuf)
    takes it to ~7 ms — the full scenario then runs at 60 fps at 1920x1080.

## Assets

No new art yet. The rewrite reuses the game's own terrain textures (TGA/R16)
and 3DO models; the model previews and scene renders are generated PPM/PNG.
`um fal` was not needed.

## Cost and time

One long session (~6 h). Toolchain installs: rustup + WinLibs + gh via winget
(~200 MB). All measurements are in the project `MODLOG.md`.

## Open questions

1. ~~Mission→map association and the JIM world-unit → map-pixel scale~~ —
   **resolved: JIMs are mission-editor documents, not game data.** `AF3.EXE`
   has no `.JIM` literal; live scans of a running campaign (briefing and
   in-mission) find neither the file bytes nor its string table; a 2-point
   RANSAC similarity fit (rotation/reflection allowed, scale 0.2..1.6) between
   JIM records and every fixed-point coordinate pair in the compiled scenario
   never reaches 4 inliers. JIM overlays are now normalized over their own
   bounding box (relative layout only). The mission→map association comes from
   the scenario's own TRN (`dg2_dy03.trn` -> `AFDG2`).
2. ~~Full vehicle composition~~ — **solved via the engine's per-type assembly
   tables.** The *typed* manifests live in `RESOURCE.PFF` (header number, e.g.
   `BMP.AI` type 4, `M1A2.AI` type 1, `BRDM.AI` type 20); `MISSIONS.PFF` copies
   are editor documents (no type, but plot routines like `tank,0,10` /
   `2sa6,5,32` / `1prt,8`). The per-type attachment table (Nova3di
   `af3_assemblies`, extracted from the engine) is implemented with its exact
   semantics: slot/parent/mesh index, `mesh -1/-2/-3`, body-diagonal sentinels,
   first-attachment-per-slot offsets, per-part LOD substitution
   (`BMP2B_L1` -> `BMP2B_H1`), X (destroyed) part splitting and flat
   shadow/decal skipping. Plot-routine manifests compose through the routine
   tables with their `base_part` offsets.
3. 3DO/3DI model orientation/scale calibration against the engine's world
   units (the rewrite normalises each model to a per-name target size).
4. 16:9 in the 32-bit payload: **window fit and the doubled strip text are
   done**, and so are the minimap and the vehicle/status icon (see the Update
   section); the SSE2 /
   multi-threaded terrain rasterizer for the 32-bit path is still open (18.35 ms
   at 1080p).
5. The rewrite's HUD/cameras/simulation and mission loading from JIM (moot now
   that JIMs are editor-only).
6. ~~Animated materials/texture frames~~ — **moot**: all 4140 3DO models
   (27,112 texture entries) have `frame_count == 0`; AF3 animates effects and
   model parts, never texture frames. The engine's exact object render flags
   remain open.

## Update (later sessions)

**AI composition (RESOURCE typed manifests).** See open question 2 above; the
implementation lives in `af3full-core/src/ai.rs` (attachment tables + plot
routines + X-split + LOD helpers) and `af3modern` (`compose_ai_model`).
Verified wireframes for M1A2/BMP/BRDM/OLIFANT (typed) and 2S6M (plot routine).

**32-bit wide HUD.**

- **Window fit**: the Rust payload (`af3full_payload.dll`) now runs a watcher
  that converts the game window to borderless topmost at the monitor origin
  when the mode exceeds the desktop work area (1080p mode + taskbar), sizing
  from the engine's framebuffer globals (`[0x65188C]`/`[0x651890]`) so the 1:1
  blit survives; restores the saved style when a smaller mode fits.
  `AF3_WINDOW_FIT=0` disables.
- **Doubled strip text fixed**: the glyph cave now scales by `height/480`
  (was `pitch/640`) including the advance helpers, and the strip band guard
  threshold is `429*height/480` (the old `429*pitch/640` computed 1287 px at
  1080p and never fired). At 4:3 both are mathematical no-ops. The 4:3 gate
  stays 27/27.
- **Minimap fixed at 16:9**: the wide HUD layout is an element-id grid at
  `[0x613200]` with dims `[0x613224]x[0x613228]`, set to pitch x height at
  mode init (`0x412C39`/`0x45ECD0`); element rects are the bounding boxes of
  each id (`0x56F680`/`0x56F818`, written into the slot struct by `0x5416FE`).
  The grid zones are the native 640x480 zones scaled x*pitch/640,
  y*height/480 - the anisotropy every wide element inherits. The minimap is
  id `0xF7`, its bbox computed at call site `0x542614`, written to slot
  `+0xFC`. A 100-byte cave (`build_minimap_rect.py`, `patch_minimap_rect`)
  hooks that call, preserves CF, and rewrites x as
  `x*(4*height)/(3*pitch) + (3*pitch-4*height)/6`; at 4:3 it is a
  mathematical no-op. Verified: the minimap moves from `(12,686,580,261)` to
  `(249,686,435,261)` - square, at the pillarbox edge - with the compass
  letters and the player marker inside the square; mode gate 27/27.
  (The grid itself is decoded from a resource by `0x612FC2 -> 0x404A46`; the
  per-element rect transform avoids touching that pipeline.)
- **Vehicle/status icon fixed at 16:9**: element id `0xFB`, bbox computed at
  call site `0x542500` (calculator `0x56F818`), written to slot `+0x88`. It
  gets the same x transform from its own cave at that call site
  (`build_hud_rect.py` / `patch_hud_rect` build one cave per call site).
  Verified: the icon moves from `(1761,963,147,110)` into its centred panel;
  mode gate 27/27.

**Batch tooling.** `AF3_Mod/scripts/AF3_ScenarioSheet.py` renders the showcase
mission list headlessly (terrain map auto-resolved from each TRN prefix) and
builds a titled `contact_sheet.png` in one command; verified on 8 missions
(148-378 objects each, 5 different maps).
