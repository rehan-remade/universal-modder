---
kind: game
title: Elden Ring's real combat, AI, animation and bodies running inside the Halo CE decomp (OpenCE)
game: 'Halo: Combat Evolved'
games_also: ["Elden Ring"]
game_version: 'Halo: Combat Evolved (USA) Xbox disc data (default.xbe) run by OpenCE commit 76b1898 (2026-10-07, Windows build, MSVC + clang via ninja); Elden Ring 1.17.1 (eldenring.exe 2.7.1.0, Steam) read offline as the data/logic source'
platform: windows
engine: native
route: decomp-recomp
tools: ["OpenCE (Halo CE Xbox decomp source port)", "Lua 5.1.5 + LuaJIT 2.1 (embedded)", "DSLuaDecompiler (katalash, built with .NET 9)", "WitchyBND 3.0.1.0", "Nuxe 1.2.1 (only its BinderKeys)", "HKLib CLI v0.1.2", "Ghidra 12.1.4 headless + Temurin JDK 21", "vgmstream-cli", "Python 3.14 + Pillow"]
anti_cheat: "Elden Ring has EasyAntiCheat: never launched, patched or hooked. Its install is only read (read-only extraction of params, HKS scripts, Havok files, FLVERs, textures, sound banks); eldenring.exe is analysed as a COPY in Ghidra. Halo runs offline/LAN only in the user's own build."
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-10'
links: ["https://github.com/OfficerObese/OpenCE"]
tags: [mashup, decomp, hks, havok, behavior-graph, retarget, hitboxes, poise, ai-goals, wwise, co-op, skinned-mesh, lua-vm]
---
# Elden Ring's real combat, AI, animation and bodies running inside the Halo CE decomp (OpenCE)

> Elden Ring's own player controller script (c0000.hks, decompiled) and enemy AI goal scripts run unmodified in a
> Lua VM embedded in OpenCE, the Halo: CE Xbox decompilation ported to PC. They drive Halo bipeds through a
> reimplemented Havok behaviour graph, TAE events and Elden Ring param data, with its stamina, poise, guard,
> parry, ripostes, bullets, sounds, UI and co-op. Enemies (and allied Marines) are now drawn as their Elden Ring
> bodies with exact ragdoll capsules. It runs in the real game: verified by visible scripted test runs with
> screenshots, a 16-check headless Lua suite and a two-instance co-op test.

## Setup
- **Host:** OpenCE at commit 76b1898 (Windows build via `python -m ninja windows`), run against the user's own
  *Halo: Combat Evolved (USA)* Xbox disc data. The game is 32-bit, LARGE_ADDRESS_AWARE (4 GB).
- **Guest:** Elden Ring 1.17.1, exe 2.7.1.0, Steam. Its files are only read. Nothing extracted is committed;
  generated packs live in `%TEMP%` and in a private local copy of the game.
- **Tools** (each download was approved one at a time by the human):
  - WitchyBND 3.0.1.0 (params, binders; run it from PowerShell, see Gotchas);
  - Nuxe 1.2.1, used only for its `BinderKeys` file-name hash lists; my own `er_extract.py` does the reading;
  - DSLuaDecompiler, built locally with the .NET 9 SDK;
  - HKLib CLI v0.1.2 (v0.1.3-NR rejects Elden Ring's behaviour hash). Run it with `DOTNET_ROLL_FORWARD=Major`;
  - Ghidra 12.1.4 with Temurin JDK 21;
  - vgmstream-cli (Wwise Vorbis WEM → PCM);
  - Lua 5.1.5 (vendored into the port);
  - LuaJIT 2.1 (the Windows game's VM).
- **Windows 11.** The agent's session folder was MSIX-virtualized. Native exes (lua.exe, vgmstream) can't see
  files created there, so working outputs go to `%TEMP%`.

## Route and why
- **Host: a decomp, not a hook.** Halo CE has full C source via OpenCE, so the mod is plain C inside the game
  (`source/game/eldering.c` plus small hooks in units, objects, render, director and HUD). There's no injection
  and no IPC. Pattern 3/4 of the mashup skill: embed, then fuse.
- **Guest logic: its own scripts.** Elden Ring's character logic is largely HKS (Havok Script, a Lua 5.1
  dialect).
  - `c0000.hks` decompiles to about 24k lines of plain Lua 5.1 and runs unmodified once the host supplies the
    `env()`/`act()` functions and the `hkb*` behaviour calls.
  - Enemy AI goal scripts (`aiscript`) run the same way.
  - The rest (behaviour graph, TAE events, damage, poise, turning, camera, bullets) is reimplemented in Lua/C.
    Its numbers and rules come from the exe (Ghidra on a copy) and the params, not from wikis.
- **Rejected:**
  - Passthrough (two processes): Elden Ring can't be run or hooked under EAC.
  - A community env/act list: unverified for this version. Every id was mapped from the exe's dispatchers.

## How the game works (what we had to learn)
**Elden Ring scripting surface**
- The `env` dispatcher is at 0x140421310 and the `act` dispatcher at 0x14040d100. There are 119 env ids and
  about 70 act ids.
- Both were found without waiting for Ghidra's full analysis (which never finished on the 87 MB exe):
  1. a raw scan for RIP-relative `lea` instructions pointing at the name strings;
  2. a lookup of the containing functions in `.pdata`;
  3. headless Ghidra decompiles of those functions only, in a `-noanalysis` project.
- **Behaviour graph:** `c0000.hkx` goes through HKLib to XML, then becomes JSON (36k objects) and then Lua
  tables.
  - Implemented: state machines, CustomManualSelectorGenerator (its `offsetType` cases traced in the exe), layer
    blending control data and bone-weight arrays.
  - Bones past the end of a bone-weight array weigh 1.
- **TAE** (animation events) drives most combat timing: i-frames, hit windows, turn speed, cancel windows, sound
  and bullet spawns, weapon style.
  - Events are active over the frame interval (start ≤ t and end > previous t). Point-sampling misses windows
    that end as hits start.
- **Characters run at 60 Hz** (two Elden Ring steps per Halo 30 Hz tick). Input is sampled every render frame
  and split into two windows per tick.

**Combat rules, from the exe**
- **Defence and damage:** the defence curve is at 0x140691b40 (piecewise quadratic on the attack/defence
  ratio). CalcCorrectGraph evaluation is at 0x140691d80, and weapon AR scaling at 0x1406911e0 / 0x1406916c0.
- **Guard:**
  - Stamina cost is at 0x140685140 / 0x140685390. A guard breaks when the cost ≥ the defender's stamina.
  - The repel test is at 0x1404476e0. A guarded hit must be recorded as damage type GUARD (3), not 1000; 1000 is
    the attacker's repel.
- **Poise / super armour (0x14047e400):**
  - Each hit's poise damage is multiplied by the product of the target's SpEffect `saReceiveDamageRate`.
  - The maximum is the base plus the attack's bonus (the player's weapon `saDurability` while in an attack
    state).
  - At 0 the poise breaks: the hit's reaction plays and the poise is refilled.
  - Player recovery is GameSystemCommonParam `baseToughnessRecoverTime` (30 s) × `toughnessRecoverCorrection`.
  - NPC recovery appears to be 13 s × (1 + `superArmorRecoverCorrection`). This is **INFERRED**: every row's
    value is a thirteenth, and the function wasn't found.
- **Character collision (0x14045ff30):** NpcParam `chrHitHeight`/`chrHitRadius` form the character-vs-character
  capsule, with `weight` as its mass. `hitHeight`/`hitRadius` form the separate map proxy. Overlap is split by
  weight share; that's my model of Havok, not traced.
- **Hit detection:** AtkParam spheres at FLVER dummy polys, swept from the previous frame to this one, against
  the target's ragdoll capsules. Those are `hknpCapsuleShape` in chrbnd entry 300's physics HKX; polytope and box
  bodies become capsules.
- **AI distance:** `GetDist` (0x14030df70) is the 3D centre distance, not capsule-to-capsule.
- **Pathfinding:** Elden Ring's is a Havok navmesh per Elden Ring map, so none exists for Halo maps. The port
  answers the AI's navmesh queries with Halo's own actor pathfinder (which avoids objects), wall rays and a floor
  probe.
- **Turning, lock-on, camera, parry, criticals, bullets and sounds:** each rule came from a named exe function.
  The full list is in the project log; for example, turn speed priority TAE > act 2004 > NpcParam
  `turnVellocity`.

**Retargeting Elden Ring animation onto Halo skeletons**
- Halo node rotation = D·C·R0, with D = A·Re·Re0ᵀ·Aᵀ:
  - A maps Elden Ring axes to Halo's (x forward = −Z, y left = +X, z up = +Y);
  - C aligns the rest bone directions;
  - Re/Re0 are the Elden Ring bone's posed and rest world rotations.
- Halo quaternions are conjugates of the usual convention.
- Characters are scaled to Elden Ring size (object scale = 1/(3.048 × skeleton scale); 1 Halo unit = 3.048 m).
- **Elden Ring bodies:** FLVER `0x2001a` meshes (vertex attributes split across buffers) and albedo maps, found
  through `allmaterial.matbinbnd`. They're GPU-skinned onto the Elden Ring skeleton.
  - The skeleton is rebuilt each frame from the posed Halo nodes. Each mapped bone's world frame is the Halo
    node's rotation × a constant K = (C·R0)ᵀ·A·Re0. Unmapped bones follow their parents at rest offsets.
  - Ragdoll capsules sit on these exact Elden Ring bones, so hitboxes match the drawn body by construction.

**Halo side**
- These units and helpers are used:
  - `object_get_cached_render_lighting` for the custom meshes' lighting;
  - the actor pathfinder (`actor_path_input_new` / `path_state_find` / `build_path`);
  - `object_cause_damage` (Halo vitality stays the HP truth);
  - `encounter_create` (enemies respawn on rest).
- A hidden Halo model (`render_objects.c`) still owns lights. Darken them where Halo already does it for active
  camo.

## Build steps
1. **Extract** read-only from the Elden Ring install: `er_extract.py <Game dir> <Nuxe BinderKeys dir> <out>
   /chr/...`.
2. **Unpack** with WitchyBND from PowerShell (params need `--passive`).
3. **Decompile** HKS and AI scripts with DSLuaDecompiler.
4. **Convert** HKX (behaviour, skeleton, animations, physics) with HKLib CLI v0.1.2, then the project's
   `behavior_to_json` / `graph_to_lua` / `havok_anim` scripts.
5. **Build the pack** with `build_pack.py <tools> <pack dir> [--no-models]`. It runs, per character, the
   param/AI/TAE pack, `anim_bake` (retargeted poses), `hitboxes` (ragdoll capsules) and `chr_body` (skeleton,
   meshes, textures).
   - The output goes outside the repo, read by the game as `d:\eldering\...` from its data root.
6. **Build OpenCE** with `python -m ninja windows`. The Lua sources are embedded by `tools/embed_assets.py`.
7. **Run** with the Halo data root containing `eldering/`. Config section `[eldering]`; for example,
   `show_hitboxes = true` draws the capsule overlay.

## Verification
- **Headless Lua suite** (`tools_er/harness/run_all.sh`, also run under LuaJIT): 16 lines of output.
  - 11 PASS checks: repel, critical, wall bounce, bullets, two-VM co-op, sounds, bows, spells, Grunts, capsules,
    poise.
  - 5 measurement lines: duels vs knights, dodge timing, jump, flask, sprint drain.
  - It loads the real generated pack and the real HKS and AI scripts, without Halo.
- **In-game scripted runs.** Environment variables set a level, a bot input script, screenshots from frame N and
  an enemy placed at a distance (`HALO_ELDERING_TEST_MEET_*`, `_ALONE` clears other bipeds). Screenshots were
  inspected each time, with the hitbox overlay on and off. The runs are visible windows.
- **Co-op:** two game instances on loopback (127.0.0.2/.3). Hits were judged on the victim's machine and reported
  back.
- **Offline previews** (Pillow): capsules on posed skeletons, and Elden Ring bodies skinned to the rebuilt
  skeleton, checked against the Halo skeleton driving them.
- **Frame rate:** about 250–345 fps uncapped on b30 with LuaJIT (RTX 4070 SUPER).
- **NOT verified or still approximate:**
  - NPC poise recovery time (inferred);
  - character-push weight split;
  - the spell buff formula;
  - bow damage composition;
  - which hand `SoundIDOffsetType` 1/2 means;
  - throw defender placement (1 m in front, where Elden Ring uses sorb dummies);
  - body brightness: Elden Ring's PBR renderer isn't ported, so albedo is lit with Halo's model lighting × 2,
    Halo's double-multiply convention.

## Gotchas
1. **Ghidra full analysis never finishes on eldenring.exe.** **Cause:** 87 MB of code. **Fix:** scan raw bytes for
   RIP-relative references to the strings you need. Find the functions through `.pdata`, then decompile only
   those in a `-noanalysis` project (seconds each).
2. **`env(1000) <= 0` style checks misbehave.** **Cause:** an unknown env/act stub returned 0, and 0 is *truthy*
   in Lua. **Fix:** unknown predicates return `false`, and every id gets mapped from the exe.
3. **Player input silently dead under LuaJIT.** **Cause:** HKS and AI scripts call `math.mod`, which LuaJIT
   lacks. **Fix:** `math.mod = math.mod or math.fmod`.
4. **Entity handles corrupted (−424542201 became −424542208).** **Cause:** handles passed through a float helper.
   **Fix:** use `lua_Number` (double) everywhere a handle or WEM id crosses C↔Lua.
5. **Double backstep, −16 stamina.** **Cause:** a state's `onUpdate` ran in the same frame it was entered.
   **Fix:** a newly entered state updates next frame, per the exe's frame order.
6. **Hitboxes didn't move during a character's own tick.** **Cause:** the point lookup was gated on
   `pose->valid`, which is false while that character's Lua runs. **Fix:** don't gate on it.
7. **Capsule overlay invisible.** **Cause:** debug lines were depth-tested inside bulky Halo meshes. **Fix:** a
   custom line draw with no depth test.
8. **Capsules fitted to Halo limbs never looked right** (wrong lengths, belly gaps, weapons at the elbow).
   **Cause:** Elden Ring bodies have different proportions, and Halo's Grunt has no hand nodes. **Fix:** stop
   fitting. Draw the Elden Ring body itself and put the capsules on its rebuilt skeleton. Exact by construction.
9. **Grunt's weapon came out of its elbow.** **Cause:** a hand-less Halo model's weapon was measured from the
   Elden Ring hand but placed on the Halo forearm. **Fix:** measure forearm-held weapons from the Elden Ring
   forearm. The bake cache must be moved aside to re-bake.
10. **Elden Ring bodies rendered almost black.** **Cause:** the lighting values were correct, but Elden Ring
    albedos average ~30% (made for an HDR/tonemapped renderer). **Fix:** apply Halo's model-shader double
    multiply (×2, clamped). That's an approximation, labelled as one.
11. **Hidden Grunt's green lights still glowed on the Elden Ring body.** **Cause:** hiding a model doesn't hide
    its attached lights. **Fix:** zero the light's colour and flare scale where Halo's own active-camo code
    already scales them.
12. **Bake/pack silently missing clips.** **Cause:** TAE imports can be FULL ids (615040060 → `a615_040060`).
    **Fix:** the import name builder handles both forms.
13. **30 fps on Battle Creek only.** **Cause:** every multiplayer start was a grace, each running its own Lua
    particle sim per render frame (62 at once). **Fix:** 4 shared particle pools, Lua only on game ticks, culled
    quads. Test multiplayer maps for per-object costs.
14. **Random parries.** **Cause:** the triggers' adaptive analog threshold started at 0. **Fix:** XInput's
    threshold of 30.
15. **WitchyBND hangs or behaves differently from Git Bash.** **Fix:** run it from PowerShell. MSYS also rewrites
    `/chr/...` arguments, so use `MSYS_NO_PATHCONV=1`.
16. **Native tools can't see new files** (lua.exe, vgmstream). **Cause:** an MSIX-virtualized working folder.
    **Fix:** write their inputs/outputs under `%TEMP%`.
17. **Game blocked forever during tests.** **Cause:** stderr was redirected and never read, so the pipe filled.
    **Fix:** redirect to a file, or read it.
18. **Wrong screenshots, or none.** **Cause:** screenshot frame numbers are render frames, so a 45 s run at
    ~300 fps never reaches frame 14500. **Fix:** derive the start frame from the measured fps, or use tick-based
    triggers.
19. **Enemy dies, Halo corpse appears** (open). **Cause:** the Elden Ring character is released the moment Halo
    flags the unit dead, so its death animation never shows. **Planned fix:** keep the character animating its
    death with AI off, and keep drawing the body.

## Assets
None are shipped. Every Elden Ring asset is converted at build time from the user's own install by the project's
scripts:
- param tables;
- HKS/AI scripts;
- retargeted animation;
- capsules;
- FLVER meshes;
- albedo textures;
- UI Flash timelines and atlases;
- Wwise sounds decoded to PCM.

The output goes into a private local pack. Halo assets are the user's own Xbox disc.

## Cost and time
Four days of agent sessions (2026-10-07 to 2026-10-10), several context compactions. About 150 targeted Ghidra
decompile projects.

## Open questions
- Death: keep Elden Ring bodies and death animations, then Elden Ring's disappear behaviour (timing not yet
  traced).
- Characters not yet replaced: Flood infection and carrier forms, Sentinels (non-humanoid skeletons), crew,
  Keyes, and actorless cutscene units.
- Full-skeleton animation: only Halo-mapped bones animate; twist, finger, cloth and tail bones ride rigidly.
- Elden Ring's lighting model for bodies (PBR) instead of Halo's.
- The NPC poise recovery function, the spell buff formula and stance-break timing, all still to trace in the
  exe.
- Not done yet: title screen, Start during cutscenes, b30 load hitches.
