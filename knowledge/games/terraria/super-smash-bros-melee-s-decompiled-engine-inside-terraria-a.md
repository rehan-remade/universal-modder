---
kind: game
title: "Super Smash Bros. Melee's decompiled engine inside Terraria: a native DLL under tModLoader, 3D fighters, its engine replayed bit-exact against Slippi Dolphin recordings"
game: "Terraria"
games_also: ["Super Smash Bros. Melee"]
game_version: "Terraria 1.4.4.9 on tModLoader 2026.08.3.0 (Steam, Windows 11, .NET 8, FNA 23.10); guest: Super Smash Bros. Melee NTSC-U 1.02 (GALE01, revision 2) with Slippi's $Required codes, minus UCF"
platform: windows
engine: xna-fna
route: decomp-recomp
tools: ["tModLoader 2026.08.3.0", "melee-pc (PC port of doldecomp/melee)", "mingw-w64 GCC 13 (posix) in WSL Ubuntu 24.04", "CMake 3.28 + Ninja", "Slippi Dolphin 3.6.4", "libmelee 0.47.3", "DolphinTool", "HSDRaw (HSDLib)", "FNA 23.10", "own PowerPC disassembler and interpreter", "own read-only Dolphin RAM reader", "Grok"]
anti_cheat: "none. Terraria single player in a separate lab save folder; Melee runs only offline, in a lab copy of Slippi Dolphin used as the oracle, never on Slippi online or netplay"
status: in-progress
agents: ["Claude Code and agents", "Grok"]
humans: ["DarkameMaster"]
date: 2026-10-10
links:
  - https://github.com/999sian/melee-pc
  - https://github.com/doldecomp/melee
  - https://github.com/Ploaj/HSDLib
  - https://github.com/project-slippi/Ishiiruka
  - https://github.com/project-slippi/slippi-ssbm-asm
  - https://github.com/altf4/libmelee
  - https://dolphin-emu.org/
  - https://github.com/tModLoader/tModLoader
  - https://github.com/FNA-XNA/FNA
  - https://www.mingw-w64.org/
  - https://github.com/rehan-remade/universal-modder
tags: [mashup, decomp, native-dll, pinvoke, trace-replay, bit-exact, float32, fma, slippi, libmelee, gamecube, 3d, cpu-skinning, lighting, xinput, hit-bridge, multi-agent]
---

# Super Smash Bros. Melee's decompiled engine inside Terraria: a native DLL under tModLoader, 3D fighters, its engine replayed bit-exact against Slippi Dolphin recordings

> The Melee decompilation's PC port (`melee-pc`) is built as a headless x64 DLL with a small C API and loaded by
> P/Invoke into tModLoader. Melee's own code moves the fighters, one engine frame per Terraria tick, and Terraria
> draws them as 3D models, lit by the world. In a headless bench all 26 fighters replay their real-Melee
> recordings bit for bit (29 recordings, both ports). Inside Terraria, real runs re-run by a second agent cover
> Mario's and Link's movement and 3D drawing for 17 fighters. Since then the coordinator ran 116 scripted beats on
> the then-current build and, on the integrated build, a 27-scenario in-game test suite (whose collision failures
> were mostly the test checker's) and a recorded 5,524-frame CPU-versus-CPU match that Terraria replays identically
> to the headless engine and to the original recording. Attacks against Terraria enemies, the pad path, sound, effects,
> the character select screen, the match modes, terrain collision and the Terraria lockout have second-agent
> verification that is synthetic or by reading IL only; a release and online play are not done.

## Setup
- **Host:** Terraria 1.4.4.9 on tModLoader 2026.08.3.0 (Steam), on the .NET 8.0.0 runtime tModLoader ships. FNA
  23.10.0.0 with SDL2 2.28.2: read from the DLLs, because FNA's folder name `1.0.0` is not its version. Windows
  11 Pro x64, one desktop machine.
- **Guest code:** [melee-pc](https://github.com/999sian/melee-pc) at commit
  `e83383539a4fd06e9bd8b28c270b3d1ecc7d3be3` (2026-09-29), the [doldecomp/melee](https://github.com/doldecomp/melee)
  decompilation plus a PC platform layer. Built in WSL Ubuntu 24.04: gcc 13.3.0 and CMake 3.28.3 for Linux
  probes, `x86_64-w64-mingw32-gcc` **13-posix** for the Windows DLL (the port's graphics layer uses
  `std::thread`, which needs the posix variant even though the DLL doesn't link that layer).
- **Guest data:** the game's files (Melee NTSC-U 1.02), extracted with DolphinTool to a folder outside the mod.
  The DLL reads them at runtime; nothing from the game is in the mod or its repository. Every player needs their
  own copy of Melee NTSC-U 1.02, dumped from a disc they own; don't download disc images.
- **Target rules (user's decision):** Melee 1.02 **plus Slippi's `$Required` codes**, the way Melee is played
  online today, **minus UCF** (the community controller fix, which ships inside the same required block).
- **Oracle:** Slippi Dolphin 3.6.4 (the official portable build of
  [Ishiiruka](https://github.com/project-slippi/Ishiiruka)) driven by [libmelee](https://github.com/altf4/libmelee)
  0.47.3 on Python 3.12.10, in a lab copy whose game settings have the 9 UCF 0.84 code blocks removed. The user's
  own Dolphin configuration is untouched (hash checked).
- **Lab:** tModLoader started with `-tmlsavedirectory <lab folder>` and `-skipselect`, saves snapshotted with
  `um backup` first, a flat test floor, daytime forced while the lab flag is set. The DLL lives in a folder
  outside the mod, so it is never packed into the `.tmod`. The lab runs while the player keeps using their own
  tModLoader, so a classifier tells lab processes from the player's and only the lab's can be closed, by exact
  PID; extra labs run from their own copy of the install
  (`running-several-isolated-tmodloader-test-instances-in-parall.md`).
- **Process:** an orchestrator assigned every task to one agent and its verification to a different one, which
  re-ran or re-measured it; up to 12 Claude agents ran in parallel at the peak, plus smaller ones for
  mechanical work and verification. Grok drafted and reviewed designs read-only as a second model.

## Route and why
`decomp-recomp`, embedded as a library: the libsm64 / Elden Ring Mario pattern
(`techniques/rebuilt-guest-engine-inside-a-host.md`). Melee's state and rules cross into Terraria; **nothing of
Melee's renderer crosses** (the port's GX/WebGPU layer, Dawn and SDL are not linked). Terraria draws.

Considered and dropped:
- **A C# reimplementation from the `.dat` data** came first, about 2,500 lines: movement, attacks, defence,
  knockback and generated tables. Against real Melee on the same 116 scripted beats, judged on position only, it
  matched 52; the embedded engine matched 110 (a second agent's comparison). Every special move would have
  needed hand-written logic: about 34 distinct movement specials and 18 projectile moves across the roster.
- **Pre-rendered sprite sheets** of each fighter (Blender, about 90 sheets per fighter): an estimated 1.5 to 20
  hours of unattended rendering for the roster (the estimates differ in how many frames are rendered), lighting
  baked in, and parts whose visibility depends on the action missing. They were replaced by real-time 3D models
  posed by the engine.
- **Running the whole game headless and bridging it** (a passthrough) stayed an unused fallback. Embedding only
  the simulation turned out cheaper than expected: from the first build to Mario moving inside Terraria took
  under a day.

## How the game works (what we had to learn)

### Loading Melee's engine into tModLoader
- melee-pc's CMake already builds the game as a static library separate from the port. The DLL is that library
  plus a small glue layer: generated stubs for console hardware (graphics, audio, memory card, disc, network),
  a 96 MB arena at a fixed address below 4 GB, a crash guard that turns a game panic or an access violation into
  an error code, and a reset that copies the game's statics back from a snapshot. It imports only KERNEL32 and
  msvcrt. Recipe and traps: `techniques/hosting-a-decompiled-console-engine-as-a-native-dll-inside-a.md`.
- The mod binds it with `NativeLibrary.Load` from a configurable path outside the mod and never frees it. A mod
  reload unloads the C# side, but the DLL and its state stay in the process, so every session starts with
  `mtb_reset` and then `mtb_init`.
- **The C API (`mtb_*`).** It is versioned (magic `MTBR`, major version 2 with a handshake, a minor version for
  additive features) and made of fixed-size, pointer-free blocks pinned with `_Static_assert` in C and offset
  checks in C#. Core calls: `init(files_dir)`, `reset`, `load_collision`, `set_slot`, `create_fighters`,
  `step_pads`, `read_state_slot`, `read_items`, RNG seed get/set, `last_error`. Optional, bound by name when
  present: pose, stage points, camera, sub-entity pose (Nana), hitboxes and hit injection, audio, effects.
- **What a fighter needs from the game's files:** `LbRb.dat`, `PlCo.dat` (common fighter data) and its `Pl??.dat`.
  Final Destination's collision, blast zones (−246, 246, 188, −140) and camera bounds come from `GrNLa.dat`.

### How frames cross: one engine frame per Terraria tick
- Both games run at 60 Hz. In `ModPlayer.PreUpdate` the mod builds the pads and calls `mtb_step_pads` once; in
  `PostUpdateRunSpeeds` it writes the engine's position into the `Player` (feet anchored, velocity zeroed,
  Terraria's own movement suppressed for that tick). Two agents' real runs measured 0.031-0.036 ms per step on
  average.
- **Units:** 3.5 px per Melee unit, so Mario's 11.98 units are the Player's 42 px; Melee's Y points up, Terraria's
  down; the origin is local (the tile edge under the fighter's feet when it was created). One conversion
  function owns all of this.
- **Terrain:** Terraria tiles in a window around the fighter (120×68 tiles) become Melee collision lines. A line
  has the solid on its right (floors left to right, right walls top to bottom, ceilings right to left, left
  walls bottom to top), with `0x100` for a pass-through platform and `0x200` for a grabbable ledge. The first
  version treated slopes and half blocks as full blocks and had no ledges. A later version adds slopes, half
  blocks and platforms, ledge stubs at floor ends, one collision joint per connected solid (with a single joint
  the fighter could grab a ledge through a wall), and live reloads that remap every fighter's stored line
  indices. A second agent verified it in three rounds with synthetic tests and fire runs (bench 29/29, no floor
  panic over 26 fighters × 11 buttons, a cap on a loop that also hangs the original port's build); one rare
  recoverable panic is left.
- **When Terraria owns the player** (mount, grappling hook, pulley, bed, death, teleports), the engine doesn't
  step. When it ends, the fighter is recreated at the player's feet: `reset` + `init` + `create`, which replays
  Melee's entry animation (Gotcha 3).
- **What a headless Melee match needs besides fighters** (each found by a divergence or a crash): a stage-class
  object whose only job is to tick the collision counter every frame (airborne floor checks depend on it), the
  crowd-reaction setup the match scene runs, Final Destination's stage points, and Melee's combat camera computed
  without drawing (off-screen logic depends on it).

### How input crosses: XInput → a raw GameCube pad → Melee
- Melee reads pads in two stages. **Stage A** is the controller library: a radial clamp of radius 80 with `s8`
  truncation, direction bits from radius 30, and scaling (sticks /80, triggers /140). **Stage B** runs inside the
  fighter code (`Fighter_procInput`): dead zones from the common fighter data, Z synthesis, and a digital L/R
  press that forces the analog value to 1.0. The DLL's step takes stage-A output; the mod does stage A in C#
  (`EnginePad.FromRaw`, transcribed from the decomp's `controller.c`) and must never apply stage B itself.
- A second agent replayed 6 real recordings through `EnginePad` plus the decomp's `Fighter_procInput`: equal to
  Slippi's recorded processed input in 30,557 of 30,557 frames (4,198 with the stick moving). Real data never
  exercised the clamp beyond radius 80, the C-stick, digital L/R or raw trigger values.
- **The pad.** XInput read directly for 4 pads (the system DLLs only), with no dead zone. FNA's one-argument
  `GamePad.GetState` adds its own dead zone on top of Melee's; `GamePadDeadZone.None` is the fallback path.
  Floats become raw GameCube values with `(int)(axis * 80)` and `(int)(trigger * 140)`, truncated towards zero,
  with no second Y flip.
- **The layout only decides which GameCube button each Xbox button writes**, so everything after it stays
  bit-exact. Default: Nintendo/Switch positional (B = A attack, A = B special, Y/X = jump, RB/LB = Z, triggers =
  analog L/R, a full press = digital L/R); presets for a GameCube/Dolphin layout and a custom one. Start opens
  Terraria's pause menu and never reaches the engine. The implementing agent's synthetic test (94 checks) drove
  the real DLL and saw it react to every button on frame 1. A second agent confirmed the mapping and the path to
  the engine the same way, found that a single pad at XInput index 1 left port 0 dead and a short window in which
  the temporary 16:9 resolution could reach the user's `config.json`, and re-verified the fixes (any single pad
  now drives the fighter; the 2+ pad logic survived 3.38 million fuzzed frames with 0 violations). All synthetic;
  no physical pad has been tested.

### How the animation was matched, frame by frame
The engine publishes joint matrices and mesh visibility; the mod skins the user's converted models on the CPU,
renders them into a render target in `Main.OnPreDraw` and pastes that as a player layer. Four checks, each
re-run by a second agent: the simulation is bit-exact (so the action and frame are Melee's); drawing changes no
engine field; the pose equals the animation tracks decoded straight from the `.dat`; and the pose equals real
Melee's RAM, read from Dolphin every frame. The last one showed that tails, capes and hair in Melee only move
right because the game *draws*: Slippi's `DynamicsFix` code plus a graphics-free "draw-effects" step at the end
of each engine frame reproduce it. Details, numbers and gotchas:
`techniques/skinned-3d-models-inside-tmodloader-posed-by-an-external-eng.md`.

### Melee ↔ Terraria: hits, the lockout and the screen
- **Fighter vs fighter and items stay inside the engine** (exact). The translation happens only at the border,
  the "hit bridge", in both directions. Designed by Grok and reviewed by a separate Grok session over three
  rounds against the decomp and tModLoader; implemented by a Claude agent and verified by second agents in two
  rounds (after a second implementation: bench 29/29 byte-identical, one hit per Terraria tick holds over about
  2.3 million checks, reads pure, launch direction right; integrable together with an engine fix for a hit
  flash). **Synthetic tests only until the first in-game suite (see Verification).**
  - *Melee → Terraria:* each frame a pure read returns the active hitboxes; the mod sweeps each one as a capsule
    from its previous position against `NPC.getRect()`, applies one hit per hitbox group per activation per NPC
    (Melee's own victim-list rule), and turns it into a single `StrikeNPC` through `HitModifiers`. Knockback comes
    from Melee's own knockback function with a fixed weight of 100; the mod never writes `npc.velocity` or
    `npc.immune`.
  - *Terraria → Melee:* NPC contact, projectile, spike and trap hits are queued with a new `mtb_apply_hit` and
    drained inside the step, right before Melee resolves that fighter's hits, as a synthetic item hit through
    the game's own item-hit path. Melee computes percent, knockback, hitstun and hitlag. Damage goes through a
    configurable curve (`25·d/(d+40)` percent, at least 1). On the Terraria side, `ImmuneTo` returning true plus a
    detour on `Player.Hurt` keeps Terraria's dodges, debuffs and life loss away from the fighter.
  - Measured synthetically: a jab gives 3% and a knockback of 33.4 on a weight-100 target, bit-equal to the game
    function; an injected 3.7% hit adds exactly 3.7% with hitstun 15 and hitlag 4; the 29-recording bench stays
    byte-identical with the new reads called every step.
- **The Terraria lockout.** While the player is a Melee fighter, Terraria's player tools are off: items, mounts,
  hooks, every teleport, doors, chests, town-NPC chat, hotbar and quick keys; Esc opens the options menu.
  Enemies, bosses and traps still interact. Rules: block the effect, never the raw input (the engine reads the
  pad in `PreUpdate`, before `TriggersSet.CopyInto` fills the `control*` fields); block entering, not leaving;
  leave world-forced events alone. The first review found seven escapes (the gravity globe flips the screen,
  Esc with Autopause leaves the game paused, right-click on portable banks opens them, the return portal is
  consumed, the step stool, two rare ones), later rounds a few regressions and about fifteen passive ones (a second
  model's review); after the third attempt a second agent's IL sweep of 2,691 methods found none left, with 15
  symmetric detours and a clean exit. **Build and IL reading only; not run in game.**
- **16:9.** Writing `Main.PendingResolutionWidth/Height` does nothing outside the options menu;
  `Main.SetDisplayMode` applies at once. A detour on `Main.SaveSettings` keeps the temporary resolution out of
  the user's `config.json` (a second agent found a window of up to 120 ticks where it could still reach it; fixed
  and re-verified); on a non-16:9 fullscreen monitor the mod draws into a centred 16:9 viewport instead.
  Synthetic tests and the build only.
- **Added since the first version of this note** (second-agent verdicts in brackets): sound through Melee's own
  audio mixer running headless inside the DLL [verified synthetically; hardening against corrupt sound files
  delivered, not yet verified]; Melee's particles and effect models read from the engine and drawn [partly
  verified]; the character select screen with its countdown [verified in three rounds, ending with 2.4 million
  fuzzed frames and corrupted images or music that no longer crash]; Melee's stamina (HP) and 200% modes, stocks,
  and an "arena anchor" with blast zones and 16:9 bars [partly verified, integrable; three narrow carry-over
  gaps]; Melee's camera driving both the view and the model, with a jitter fix [partly verified: the jitter fix
  holds]. Still being worked on: the HUD, the rest of the match flow, and fixes for what the first in-game suite
  found.

## Build steps
1. In WSL Ubuntu 24.04, install CMake, Ninja and `mingw-w64` (posix variant). melee-pc's preflight script lists
   the X11/Wayland headers SDL3's configure step wants. `-DCMAKE_OPTIMIZE_DEPENDENCIES=ON` stops the static
   library from waiting on the whole graphics stack (1,934 → 1,080 build steps). `ninja melee_game` builds the
   library (13.5 MB, 48 s on 16 threads).
2. Build your own core target next to it: the `mtb_*` API, the allocator, a printing `OSPanic`/`OSReport`,
   and **generated** stubs for the remaining hardware symbols, with value-returning ones classified. Repeat the
   game target's forced include (`-include src/pc/compat.h`) on your target.
3. Apply the floating-point and Slippi fixes as build-time patches (on by default):
   `techniques/bit-exact-decomp-ports-reproduce-the-original-compiler-s-and.md`.
4. Link it as a DLL with the C and C++ runtimes static and the guest's panic and abort wrapped
   (`--wrap=OSPanic --wrap=abort`), and copy `melee_core.dll` to a folder outside the mod. Point the mod's config
   at it and at your extracted files; the data path goes in through `mtb_init`, never an environment variable.
5. Convert your fighters' models with your own converter (on HSDRaw) into a folder outside the mod.
6. In the mod: the P/Invoke binding, tiles → collision lines, the pad path, the session lifecycle, the 3D
   renderer, and a config toggle. Note that a normal `dotnet build` of a tModLoader mod also packs the `.tmod`
   into your `Mods` folder (`tMLMod.targets` runs `BuildMod` after `Build`). Check compilation on a private copy
   without the pack target, and pack with tModLoader's own `-build` into a lab folder (hosting note, Gotcha 10).

## Verification
**Oracle.** Melee 1.02 in the lab Slippi Dolphin plays scripted input "beats" (walk, dash, jumps, every attack,
shield, rolls, specials) from the same beat file the mod's lab script plays in Terraria; a comparator diffs the
two per frame. For the engine itself, a headless bench replays each real recording's inputs through the DLL and
compares every state field bitwise. Trace replay is described in `techniques/oracles-how-agents-know-a-mod-works.md`.
- **Recording the truth:** one scripted recording per fighter (26, plus a Link pilot), 2,952 compared frames each,
  plus two earlier Mario recordings: 29 in all. The 27 per-fighter recordings ran unattended in 32.8 minutes with
  no retries (implementing agent's figure; a second agent's re-recording of two fighters took the same 72-73 s
  each). Port 2 is an idle second Mario that walks away from the action.
- **Contamination is marked per frame** (P2 disturbed, P1 past the stage edge, a KO): 10 recordings are clean end
  to end, and 12 contain KOs. Comparisons in Terraria cut at the beat before the first dirty frame.
- **Determinism of the truth** is shown for Mario only (3 runs with 3 seeds identical). Peach's forward smash
  pulls a random item, so her re-recording differs.

| Claim | Evidence level | Result |
|---|---|---|
| All 26 fighters bit-exact | Bench host (not Terraria) replaying real recordings; re-run by a second agent with its own host, `.slp` reader and comparator | **29/29 recordings, 58/58 ports**, every compared field, every frame. Whole recordings went 0 → 7 → 18 → 23 → 27 → 29 as the fixes landed (the first two counts on the 22 recordings that existed then); removing any fix brings its divergence back |
| Pad stage A | Derived comparison against 6 real recordings | 30,557/30,557 frames |
| Mario moving in Terraria | **Real run** in the lab tModLoader, re-run by a second agent | 2,892/2,892 frames with the exact action against real Melee (with an idle rival present, as in the recording); max error 0.0002 units in x, 0.0001 in y; two agents' traces identical in 38 fields |
| Link moving in Terraria | **Real run**, re-run by a second agent | 2,892/2,892 actions; position error ≤ 0.012 px in x, ≤ 0.008 px in y |
| 3D drawing changes nothing | **Real run**: Mario and Link (second agent), 14 fighters in a later batch | 0 engine-field differences (37 fields × 2,892 rows) against runs without 3D |
| 3D fighters in game | **Real run**, captures looked at | 17 fighters; 12 of the 15 in the batch matched real Melee on every comparable row (the other 3 differ at a stage edge or by a random item) |
| World lighting | **Real run**, Link only, second agent | daylight equals Melee's own light rig; dark room readable in mixed mode; torches tint the facing side |
| Dynamic bones and visibility | Real Melee RAM dumps (6 fighters), re-derived by a second agent | dirty bits 0 mismatches, visibility 0 failures, Fox tail median 3.6e-5 units |
| Nana | Synthetic, second agent with its own DLL | 29/29 byte-identical bench; pure reads checked with 4 positive controls; the Zelda/Sheik rule holds; not run in the game |
| Hit bridge (both directions) | Synthetic tests, second agents in two rounds | after a second implementation: bench 29/29 byte-identical; one hit per Terraria tick holds over about 2.3 million checks; reads pure; integrable only with an engine fix for a hit flash |
| Pads and 16:9 | Synthetic, second agents | mapping and path to the engine confirmed against the real DLL; a single pad at any index drives the fighter; 3.38 million fuzzed frames of the 2+ pad logic, 0 violations; no physical pad |
| Terrain collision v2.7 | Synthetic tests and fire runs, second agent in three rounds | partial: bench 29/29; 0 floor panics over 26 fighters × 11 buttons; hangs capped (the original port's build hangs there too); one rare recoverable panic left |
| Engine crash fixes (a strong hit, Pikachu's Thunder, star KO, and two more) | Second agent, soak | 734 match pairs (about 276 hours of Melee), 0 crashes, deterministic under stack and register perturbation, bench 29/29 |
| Sound | Synthetic, second agent | bench 29/29 byte-identical in 8 configurations; an independent waveform check; sound events on the exact frame (16/16); hardening for corrupt sound files delivered, not yet verified |
| Effects (particles, effect models) | Synthetic, second agent | partial: bench 29/29, reads pure, 4-player fire runs clean, three small fixes at integration |
| Character select screen | Synthetic and fuzz, second agent in three rounds | screen, music, ids and layout right; corrupted images or music no longer crash (2.4 million fuzzed frames on the real FNA device) |
| Stamina and 200% modes, stocks | Synthetic, second agent | partial, integrable: hundreds of synthetic KOs, respawns, resets and snapshots; three narrow carry-over gaps |
| Terraria lockout | Build + a second agent's IL reading | no vanilla escape left after the third attempt (2,691 methods swept, 15 detours symmetric); not run in the game |
| Seven engine patches merged into one DLL | Bench + combined soak (implementing agent), independent soak | 53 exports; bench 29/29 identical; 8.3 million steps with everything on, 0 failures; an independent 10-minute soak of the integrated DLL: 268 matches (about 89 hours of Melee), 0 crashes, 15,186 rollback checks without differences |
| First lab run of the then-current build (engine v2.5) | **Real run** (coordinator, not re-run) | 116/116 scripted beats, no crash, 3D frame 0.25 ms, steady 16.67 ms; against an uncut real-Melee truth the moving beats had median error 0.0 px, mean 1.0 px, worst 23.5 px (specials; the last four are known truth contamination) |
| In-game test suite, 27 scenarios | **Real run** on the integrated build (coordinator) | 11 PASS, 13 FAIL, 3 inconclusive. A second agent re-derived the floor-break and ramp failures from raw traces: ledge grabs by the fighter, test-checker errors and a scenario built one row off, not mod bugs (`when-the-first-real-run-fails-suspect-the-oracle-re-deriving.md`); the five floor-break scenarios pass under the corrected checker on the same data, but it has not been re-run in the game. The other failures (damage accounting for multi-segment bosses, a stamina buff, one blast zone, very complex terrain) are real findings under repair |
| Recorded match replayed in Terraria | **Real run** (coordinator, not re-run) | a recorded CPU-versus-CPU match of 5,524 frames: identical to the headless engine over the whole match, and equal to the original recording in action, frame, percent and stocks on all 5,524 frames (largest position difference 0.009 units); re-run after a renderer fix with the same result. Before the collision lock (Gotcha 18) it diverged after 55 s |
| The bench tool that gates every engine build | Synthetic, second agent with 12 broken builds | all 12 broken builds fail; four false greens and two false reds found, fixed on a copy and re-run on the real tool except the final soak (`prove-your-replay-bench-can-fail-mutant-builds-exposed-four-.md`) |

The in-game runs up to and including the first lab run used earlier engine builds (v2.5 and before); the next two
rows used the integrated build (engine v2.16).

**Not verified:**
- 9 fighters never drawn in the lab (Zelda, Sheik, Young Link, Pikachu, Jigglypuff, Mewtwo, Mr. Game & Watch,
  Marth, Roy) and Nana; movement inside Terraria was traced only for Mario and Link and, in the recorded match,
  Fox and Samus;
- the hit bridge in play: the first in-game suite exercised it and found damage-accounting problems (several worm
  segments added into one hit; an arrow's damage not matching what the target lost), which are being repaired;
- physical pads, keyboard play, the lockout and 16:9 in game; live terrain edits only through the first suite;
- sound content (the checks are synthetic), Melee's effects, the HUD, the camera, blast zones and stocks, damage
  modes and the character select screen, beyond the recorded replay and the first suite;
- local multiplayer, online play, rollback with Terraria events;
- coexistence with other mods, hot reload, a second machine.

No release has been attempted.

## Gotchas
1. **The user had been playing the old engine all along.** **Symptom:** "sprite Mario every so often" in the
   user's own game. **Cause:** the engine toggle defaulted to off and the user had never saved the mod's config,
   so their game always ran the C# fallback. **Fix:** check the default a user actually gets, and log which engine
   is running.
2. **No pad button did anything.** **Cause, three parts:** the mod read buttons only through `ModKeybind`s, and a
   keybind's default binding reaches a player's input profile only when they press "reset" in the controls menu,
   so the user's profile had none; Terraria kept reading the pad itself (A mounted, B grappled, which handed the
   player back to Terraria and recreated the fighter 17 times in under half a minute); and FNA's dead zone sat on
   top of Melee's. **Fix:** read XInput directly, detour `PlayerInput.GamePadInput` while the fighter owns the pad
   (not `Main.SettingBlockGamepadsEntirely`, which `Main.SaveSettings` writes to `config.json`), and fall back to a
   keybind's default key. (Implementing agent's diagnosis; a second agent confirmed the button path synthetically
   and found the index-1 pad case.)
3. **On slopes the model squashed and popped back.** **Cause:** slopes were full blocks to the engine, the spawn
   landed inside a solid, the engine and Terraria positions drifted more than 16 px apart, and the fix-up recreated
   the fighter, which replays Melee's entry animation. **Fix:** real slope geometry, lifting the spawn out of
   solids, remapping line indices on reload; recreating without the entry animation is suggested. (Two agents
   explain the same loop differently; neither is proven.)
4. **Fighters landed on Final Destination's ledge vertex instead of being pushed off it.** **Cause:** stage
   objects tick a collision counter every frame, and airborne collision uses the floor routine that extends floors
   into a neighbouring wall only when its per-fighter copy equals that counter. The DLL had no stage object, so
   the counter never moved. **Fix:** a stage-class object whose only job is that tick. A build without it brings
   back the 5 ledge failures (verified causally).
5. **10 of 116 beats (grabs and pushes) diverged in Terraria.** **Cause:** the real recording had an idle second
   Mario nearby (Melee won't start a Vs match with one port), which the grab connected on and which pushed Mario;
   the lab had no rival. Confirmed from the `.slp`. **Fix:** the same idle rival at the same spot gave 2,892/2,892;
   later truths walk the rival far away first.
6. **The first beats of every recording were lost and the whole truth shifted.** **Cause:** Melee spends about
   100 entry frames ignoring the pad. **Fix:** replay nothing until the fighter is standing. A walk-distance "bug"
   with a correct top speed was this shift: fix the instrument before tuning physics.
7. **The truth wasn't vanilla Melee.** **Cause:** Slippi's required code block includes UCF 0.84 (dashback,
   shield drop, SDI, cardinals) and other gameplay codes. **Fix:** a lab copy of Dolphin with exactly the 9 UCF
   blocks cut, the rest reproduced in the engine as switchable tags. Edit the settings file byte-exactly: `sed -i`
   rewrote the line endings of the whole file.
8. **Slippi and libmelee plumbing.**
   - Slippi's Dolphin is based on an older Dolphin and exits silently (code 3) on a `.rvz` image:
     `DolphinTool convert -f iso` first.
   - libmelee raises `Unknown path` unless the Dolphin folder name contains `netplay`.
   - libmelee's `speed_*` fields are twice the per-frame displacement: compare positions.
   - libmelee 0.47.3 can't decode an unfinalised `.slp`; its stick conversion differs from the game's on 29 exact
     tie values; its action-frame convention is one frame off the engine's in looping states.
   - Port 2 must be a human port that picks a fighter and idles: a CPU walks over and attacks.
   - Re-seed the RNG every frame from the `.slp` pre-frame seed; common code and items use it for every fighter.
9. **A special the script pressed never happened.** **Cause:** the beat landed while the fighter was still in a
   grab or another special, so the recording has no such move. **Fix:** wait for an actionable state before
   every special.
10. **A dirty truth compared whole, exit code 0.** **Cause:** the per-recording contamination cut was looked up
    by the fighter named on the command line instead of the truth file's own, and nothing checked that the mod
    played the truth's fighter; later, a lowercase file name missed its key on a case-insensitive file system.
    **Fix:** key the cut by the truth file and check the fighter in the trace against the truth (verified). The
    lowercase case is still open.
11. **A fix looked identical to no fix.** **Cause:** the one-command compare script copied the `.tmod` but never
    rebuilt it. **Fix:** build inside the script and refuse to compare when any `.cs` file is newer than the
    `.tmod`.
12. **The extracted audio was a mix of regions.** **Cause:** a flat extraction keeps the first file-system entry
    for duplicate names (Japanese `.ssm` files next to English ones), and DolphinTool's `-o` once produced *folders*
    named `Pl??.dat`. **Fix:** extract preserving directories, and list duplicate base names before trusting the
    files.
13. **Dolphin took the foreground by itself during an unattended oracle run**, even launched minimized and not
    activated. See `recording-game-footage.md`, Gotcha 10.
14. **Second-model research drafts came back in 80 s with invented citations.** **Cause:** an API key in the
    environment overrode the subscription login and selected a non-reasoning default model. **Fix:** unset the key
    for that child process only, pin the model, and check every quoted code line mechanically against the source.
15. **Terraria → Melee hits planned on `ModifyHurt` would have missed some hits.** **Cause:** Terraria's dodges
    run before it. **Fix (design review, synthetic tests only):** `ImmuneTo` returns true and a detour on
    `Player.Hurt` records the raw damage first.
16. **The workflow's linear phase model blocked new work.** **Symptom:** adding four features reopened phase 1
    of the project's ledger, which modelled Universal Modder's 10-step loop as one global phase counter, and the
    validator rightly refused to close phase 3. **Fix:** per-track phases: a core track plus one per fighter and
    one per component, each with its own steps 1-10.
17. **The first in-game test suite failed 27 of 27, then 13 of 27, and neither was mostly the mod.** **Cause:**
    first, a relative scenario path resolved against the game's install folder, so no scenario loaded; then a test
    checker that did not know the original game's edge grabs, a helper that returned a cell inside a solid mass, and
    one scenario built a row off. **Fix:** absolute paths checked by the launcher
    (`running-several-isolated-tmodloader-test-instances-in-parall.md`, Gotcha 3); a second agent re-derived
    each failure from raw traces and mutated real data to prove the corrected checker still fails real
    fall-throughs (`when-the-first-real-run-fails-suspect-the-oracle-re-deriving.md`).
18. **A recorded match replayed in Terraria agreed with the original for 55 s, then diverged.** **Cause:** the mod's
    own terrain-to-collision streaming replaced the replay's stage collision one tick after it was created.
    **Fix:** a collision lock during replays (hosting note, Gotcha 13).
19. **The bench that gated every engine build had four false greens.** **Cause:** nobody had tried to make it fail.
    **Fix:** twelve fabricated broken builds found the holes, and a diff closed them
    (`prove-your-replay-bench-can-fail-mutant-builds-exposed-four-.md`).

## Assets
None are shipped. The 3D models are converted on the player's machine, from their own copy of the game, with an
own converter built on HSDRaw into a compact format kept outside the mod; the mod contains code only. The earlier
Blender sprite sheets were dropped. No generated (fal) assets were used.

## Cost and time
About three days (2026-10-08 to 2026-10-10) of orchestrated sessions. The embedded-engine route, from the first
library build to Mario moving inside Terraria, took under one day. Per-fighter cost became recording and checking
rather than code: one unattended recording session for all 26, and a replay of all 29 recordings through the DLL in
seconds.

## Open questions
- In-game runs of the hit bridge, pads, lockout, 16:9 and Nana (second-agent verification exists for all of them, but
  only synthetic or by reading IL).
- The hit bridge's rollback case (Terraria hits are lost if the engine re-simulates), players 2-4, shield
  damage, the attacker's hitlag, clanks.
- The remaining Slippi gameplay codes, and new recordings that exercise them.
- In-game checks of sound content, effects, the HUD, the camera, blast zones, damage modes and the character select
  screen, beyond the recorded replay and the first in-game suite.
- The Marth/Roy cape during their neutral special; the camera's remaining jitter (a second agent confirmed that the
  engine-driven camera removed the fighter's jitter, at most 1.02 px for the fighter and 0.5 px for the world
  against 110 px before, but damage numbers and health bars still jump up to 6 px at high zoom).
- Distribution: the DLL contains the decompiled game and is not distributable, and neither are the converted
  models, audio or anything else read from the disc. A source-only release, where each player builds the engine
  and supplies their own copy of Melee NTSC-U 1.02, is the option under study; the licence questions are open.
  The build-time patches (routines transcribed from `main.dol`, such as MSL's trig and `PSMTXConcat`) are
  derived from the game's executable too. Shipping only your own code and having each player bring their own
  disc lowers the risk but doesn't remove it: Nintendo has taken down projects that shipped no Nintendo files.
  Keep Nintendo's names and art off any mod page and its thumbnail, and run `um publish check` on a release
  (`skills/publish-mod/SKILL.md`). The rollback snapshot and determinism suggest online play is feasible; it's
  untested.

## Credits
- [melee-pc](https://github.com/999sian/melee-pc): the PC port this is built on, and its rollback snapshot, file
  cache and library split.
- [doldecomp/melee](https://github.com/doldecomp/melee): the decompilation, by its contributors.
- [HSDLib / HSDRaw](https://github.com/Ploaj/HSDLib) by Ploaj: reading the HSD archives for the model converter.
- [Project Slippi](https://github.com/project-slippi): Slippi Dolphin, the `.slp` replay format and the Gecko
  codes ([slippi-ssbm-asm](https://github.com/project-slippi/slippi-ssbm-asm)) that define the target rules;
  [libmelee](https://github.com/altf4/libmelee) by altf4 drove the oracle.
- [Dolphin](https://dolphin-emu.org/) (and DolphinTool), [tModLoader](https://github.com/tModLoader/tModLoader),
  [FNA](https://github.com/FNA-XNA/FNA), [mingw-w64](https://www.mingw-w64.org/).
- [Universal Modder](https://github.com/rehan-remade/universal-modder): the loop, the safety rules and the
  knowledge-base notes the agents followed.
- Built with AI agents: Claude Code and its agents implemented and verified, each result re-run by a different agent;
  Grok drafted and reviewed designs read-only. Human direction and in-game testing: DarkameMaster.
