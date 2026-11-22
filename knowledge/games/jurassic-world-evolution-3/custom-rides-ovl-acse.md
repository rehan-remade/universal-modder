---
kind: game
title: "Custom rotating rides in Jurassic World Evolution 3 (carousel and Ferris wheel)"
game: "Jurassic World Evolution 3"
games_also: ["Planet Coaster 2"]
game_version: "Historically pinned JWE3 1.5.5.0, Steam app 2958130, manifest build 25967550 (2026-10-25 and still cited 2026-11-04). Local appmanifest buildid on 2026-11-15 was 26407273; whether that is still 1.5.5.0 was not re-verified. ACSE 0.730 required."
platform: windows
engine: unknown
route: loader-api
tools: ["Cobra Tools (user tree, declared 2026.10.11 / commit metadata fe5d39d34 as of 2026-10-25)", "Blender 5.2.2 LTS bundled Python 3.13.13", "luacheck lua53c", "ACSE 0.730"]
anti_cheat: "None engaged in this work. Additive ContentPacks under Win64/ovldata only. Do not hook the process, patch the exe, install a loader other than the already-present ACSE 0.730, or touch Content0/GameMain."
status: in-progress
agents: ["Grok Bot (work through 2026-11-15)", "Claude (2026-11-16 to 2026-11-22: rider textures solved, autonomous in-game testing)"]
humans: []
date: 2026-11-22
links: []
tags: ["JWE3", "ACSE", "OVL", "MS2", "ferris-wheel", "carousel", "custom-scenery", "texture-streams", "seated-guests"]
---

# Custom rotating rides in Jurassic World Evolution 3

Additive ACSE 0.730 ContentPacks that appear under Scenery → Planters → Concrete 2. A dinosaur carousel with continuous rotation and twelve independently bobbing mounts is owner-confirmed in-game (Phase 8B, 2026-11-04). A Tiny Eye-style Ferris wheel with locked cabin attaches and hanger pins is owner-accepted as "success" (FW3Y, 2026-11-13). Static baked official JWE3 seated guests with their own textured faces, hair and clothes are confirmed in game in all six cabins (FW3ZA, 2026-11-22). This is personal-use only; do not redistribute Frontier or Planet Coaster 2 assets.

The long project audit is `HANDOFF/JWE3_MODDING_AUDIT.md`. This note is the short field-note form. **Do not `um kb pr` this file without the owner's OK, and never attach game files, DDS, MS2, OVL, or decompiled dumps.**

## Setup

- OS: Windows 11, the owner's gaming PC.
- Game: Steam install `C:\Program Files (x86)\Steam\steamapps\common\Jurassic World Evolution 3`. Mods: `Win64\ovldata\`.
- Required and protected: ACSE 0.730 (already installed). Hooks used: `AddContentToCall`, `AddLuaPrefabs`, `AddLuaComponents`, `api.entity.CompilePrefab`.
- Cobra Tools: `%USERPROFILE%\Downloads\cobra-tools-master\cobra-tools-master` (master tree). Pack with `Compression.OODLE` and `update_aux=False` on reload. Cobra uses its own bundled Oodle 8; do not swap it with the game's Oodle 9.
- Python used for pack scripts: `C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe`. Apply `integration\scripts\numpy_compat.py` in-memory before Cobra MS2 I/O (this runtime is Python 3.13 + current NumPy; Cobra metadata declared 3.11 and NumPy < 2.0).
- Luacheck: cobra's `luacheck.exe --std lua53c --globals module`.
- Project root: `C:\AI-Assistant\projects\JWE3-Modding`. Ferris work: `integration\ferris\`. Archive: `archive\ferris_tests_2026-11-13`.
- Standing discipline: never launch the game; abort an install if JWE3 is running; new ovldata folder only; back up first; owner tests in-game and sends screenshots.

## Route and why

**Chosen route: loader-api + packed assets.** Each test is a new `ContentPack` folder (`Manifest.xml`, `Init.ovl`, `Main.ovl`, an asset OVL, one or more `*_.aux` texture streams). Catalogue registration is inherited from the donor planter `AS_Planter_Concrete_01_Circle_2x2m` (UIData: Planters / Concrete 2). Runtime motion is an ACSE Lua component on a rotor child (`RotatedAroundR` / `SetOrientation`), not a stock MotionGraph autoplay (that path stayed unproven).

Considered and not taken for in-game motion: offline BANIS/MANIS banks as the first runtime driver; scenery MotionGraph autoplay; patching stock Content0. A custom ACSE component named in the C71A style crashed the game on launch (2026-10-27) and was rolled back; later B-series bisects produced the working B2-KB / Phase 8B rotor style, which Ferris reused.

Riders: official JWE3 Warm crowd guests, statically baked as cabin children (the Phase 9A approach). Live `GuestInteractionPoint` seating is unproven on airborne rotating cabins. Planet Coaster 2 guest rigs were researched (Phase 9E/9F) and then **forbidden by the owner** for this wheel; they are also a 114- vs 140-bone mismatch.

## How the game works (what we had to learn)

- Packs are additive under `ovldata`. Duplicate prefab names can replace earlier ones — unique names per pack are mandatory.
- Lua is Frontier Lua 5.3. Retail `api.debug.Trace` is a no-op, so logs cannot certify runtime; use a visible change and a screenshot.
- MS2 for JWE3 is v55. Guest MS2 LOD streams must be collapsed (`pool_index=0`, `lod.stream_index=0`) before packing baked riders. Cobra has a 65535-vert MS2 limit (this blocked full-body dinosaurs in one mesh during Phase 8).
- Coordinates: `pack_native = (−dec_x, dec_z, −dec_y)`, so **game X = −decoded X**. Cabin child game X = −dec_x + AttachX. Mixing decoded X with packed X reversed the 3X pin; 3Y flipped it.
- Ferris AttachX is locked at **−0.348097**. Do not reshape or move cabins to close hanger gaps; close gaps with pins/pads.
- Cobra packs every texture that shares one `texel` ID into one `.aux`. The known-good wheel/cabin/stand stream is **14,797,824 bytes**, SHA-256 `e8d0cdb580d5ea2c79e820b6e9ff364643234050eca95b8221c1f6462fec5610`. Putting guest textures on that texel merged the aux (3Z2: 21,450,240 bytes) and blackened the wheel.
- **Rider texture recipe that works (FW3ZA):** every rider material is a uniquely named `Opaque_Weather` FGM. Its normal and roughness slots are replaced with constant neutral values (normal (127,127,255), roughness-packed (0,77,127)), because an FGM cloned from the wheel inherits the wheel's maps. Its base colour is our own re-encode of the official 256² albedo at the **stock texture layout: 1024×1024 BC1_UNORM_SRGB, 11 mips, `num_mips_low` 7 / `num_mips_high` 9**, with the DDS header and .tex copied from a working cabin texture. Official white tops (tinted at runtime by the game) are multiplied by a chosen colour. Guest textures live on several unique texels, about 10 textures each, so no aux outgrows the wheel aux. No official names or texel IDs are packed.
- Scenery shader `Metallic_Roughness_MaterialCustomisation_Opaque_Weather` works with uniquely packed textures (the wheel; 3Z6 AM flats). Character shader `Metallic_Roughness_MaterialCustomisation_Pattern_Opaque` does **not** reliably bind uniquely named textures on a new scenery texel (both sexes black in 3Z4). Official AF maps packed under official names/texels rendered correctly on women in 3Z, and official FGMs without those maps went uniform deep brown in 3Z5 (Crowd_AF_Shared is not resolved by name reference alone on scenery-child meshes). Official AM maps packed under official texel IDs (`vsdloikvhgllowgf`, `qxewyborql/sxmfn`) made the men black in 3Z (incomplete auxes likely replacing Crowd_AM_Shared).
- Cabin `paint001` is flat red (189, 40, 41), not tan and not an atlas. Sample the DDS; do not trust texture names or preview palettes.
- Prefix length is part of binary MS2 name replacement: `ct_fw3y` is 7 characters; `ct_fw3z4` and later are 8. Same-length replace only.
- Saves that still reference a removed custom object can crash. Prefer a disposable unsaved park for tests.

## Build steps

From a Ferris pack folder (copy a previous one, change `common.py` constants, unique GUID / PREFIX / TEXEL):

```bat
set PYTHONIOENCODING=utf-8
"C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" prepare.py
"C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" pack.py
"C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" install.py
```

`prepare.py` writes `source\`. `pack.py` luachecks, builds `candidate\<PACK>\`, and asserts the wheel aux hash when the 19 wheel textures are unchanged. `install.py` refuses if the game is running or the destination exists, snapshots watched packs, exclusive-creates the ovldata folder, and never launches the game. Scripts live in `integration\ferris\fw3y\` through `fw3za\` (`fw3za` is the current textured-rider build). The in-game test driver is `integration\automation\jwe3auto.py`; it launches the game but `install.py` never does.

Do not install over 3Y, 3ZA, Phase 8B, or the carousels. A new experiment is a new `CT_*` folder.

## Verification

- Packing assertions (unique names, wheel aux SHA/size, luacheck, watched-pack hashes) are necessary but not sufficient.
- The oracle is the owner's in-game screenshot of a **freshly placed** instance, after a game restart if packs were just removed.
- Previews (`preview_render.py`) can confirm geometry and can lie about character colours.
- Since 2026-11-16 the agent can run in-game tests itself through `integration/automation/jwe3auto.py`, only while the owner has been idle for 15 s and only in the `CT AutoTest Park` save, judging from its own screenshots.
- Not verified as of 2026-11-22: live guest occupancy on rotating cabins; decor-from-blueprint baking.

## Gotchas

1. **Pin or prop comes out mirrored.** **Cause:** mixing decoded-space X with packed/game X. **Fix:** convert in one space only (`pack_native`); 3Y is the settled pin direction.
2. **Wheel goes black after adding textures.** **Cause:** a second texture group shared the wheel texel, so the 14.8 MB aux was replaced (3Z2). **Fix:** never put guest textures on the wheel texel; assert the known SHA and size.
3. **Two installed test packs smash materials; black wheel and rainbow speckles.** **Cause:** shared official or reused names and texel IDs (3Z3; 3Z6 while 3Z4/3Z5 were still installed). **Fix:** unique prefixes and texels; archive older experiments; test one rider pack at a time.
4. **Self-packed unique guest textures render black.** **Cause (best supported):** `Pattern_Opaque` does not bind uniquely named maps on a new scenery texel (3Z4; decoded albedos were valid). **Fix:** do not retry that path without a new explanation. Opaque_Weather + unique flats worked for the men in 3Z5/3Z6 (colours were wrong in 3Z5 for a different reason).
5. **Official AM maps under official texel IDs make the men black.** **Cause (best supported):** incomplete official AM auxes replacing Crowd_AM_Shared, which is not reliably resident. **Fix:** do not pack official AM textures under `vsdloikvhgllowgf` or `qxewyborql/sxmfn`.
6. **Official AF FGMs without packed textures go deep brown.** **Cause:** scenery-child meshes do not pick up Crowd_AF_Shared by name alone (3Z5). **Fix:** the 3Z look required the official AF files inside the pack, which reintroduces official-stream risk (the open 3Z6 question).
7. **“Tan” cabin paint was red.** **Cause:** `paint001` is flat (189, 40, 41). **Fix:** sample the DDS. For solid character colours use full-size unique textures on a separate texel (see 11).
11. **Riders render as rainbow noise or patchy colours.** **Cause:** 16×16 flat textures (5 mips) do not stream or bind like stock textures (3Z6–3Z8). **Fix:** use the stock layout, 1024×1024 BC1, 11 mips, low 7 / high 9 (3Z9 clean flats; 3ZA textured).
12. **Whole wheel goes black when official crowd AF textures are packed.** **Cause:** packing official AF textures under their official texel IDs (3Z6 alone vs 3Z7, confirmed 2026-11-21). **Fix:** never pack official AF or AM textures under official texel IDs; ship your own re-encoded copies under unique names.
13. **Riders have an iridescent, oily sheen.** **Cause:** rider FGMs cloned from the wheel's Opaque_Weather FGM keep the wheel normal/roughness maps (3Z7). **Fix:** point those slots at constant neutral textures (3Z8).
8. **Cabin half-missing, smashed, or shrunken after a “clearance” edit.** **Cause:** moving or reshaping cabins (3F–3P), including a 3I AttachX change. **Fix:** keep the 3Q/3Y cabin meshes and AttachX −0.348097; use pins, not cabin edits.
9. **Game crashes on launch after a custom ACSE component pack.** **Cause (C71A, 2026-10-27):** custom component / `CompilePrefab` path was the strongest suspect. **Fix:** roll back the new folder; do not iterate in place. Later B-series bisects found a working rotor style.
10. **Binary prefix replace corrupts or misses names.** **Cause:** prefix length changed from 7 (`ct_fw3y`) to 8 (`ct_fw3z4`). **Fix:** same-length replace only; rebuild names properly when lengths differ.

## Assets

Wheel and cabin art started from a Planet Coaster 2 Tiny Eye reconstruction, rebuilt as original scenery on the JWE3 rotor/scenery base (personal use). Riders are official JWE3 Warm seated guests (`sittingbench01` frame 0), statically baked, facing each other on 0.44 m benches in all six cabins. FW3ZA riders use 47 re-encoded copies of the official crowd albedos (1024² BC1) on five unique texels; white tops are tinted teal, coral, blue, gold, purple, green, pink, sky and orange. Do not vendor those official guest files in a public repo.

## Cost and time

Not billed here. The carousel/rotor path ran from late October 2026 through 2026-11-04 (8B confirmed). The Ferris cabin/pin path ran through 2026-11-13 (3Y accepted). Rider texture work ran 2026-11-13 through 2026-11-22 (3Z9 clean flats 2026-11-21; 3ZA textured 2026-11-22).

## Open questions

1. Can in-game decor the owner places on the wheel be baked into the base model from a blueprint or save? Deferred by the owner until riders were done; riders are now done.
2. Can live `GuestInteractionPoint` seating work on airborne rotating cabins instead of baked riders? Unproven.
3. Would 512² guest textures (less aux space) bind as reliably as 1024²? Untested; the stock crowd albedo is 256² inside the base game's own streams, but self-packed sizes below 1024² have only been tried at 16².
