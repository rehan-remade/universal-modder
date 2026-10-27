---
kind: game
title: "Physics Accelerator: a multi-core replay of Teardown's island solver, two PhysX 5.9 remaps, and a flight recorder (native dsound.dll)"
game: "Teardown"
games_also: []
game_version: "2.1.0, Steam app 1167630, buildid 25295735 (teardown.exe 30,555,208 bytes, 2026-09-17), D3D12, Windows 11"
platform: windows
engine: unknown
route: native-hook
tools: ["MinHook", "NVIDIA PhysX 5.9.0 (built from source, GPU + CPU)", "CUDA 13.4", "Visual Studio 2026 18.10.4 (MSVC)", "CMake 3.24+", "Ninja", "Python + capstone + pefile + numpy (uv)", "rea-agents 6.5.0 (REA MCP)", "Ghidra 12.1.4", "Eclipse Temurin JDK 21.0.12", "Node.js 24.15.0", "um backup", "um win", "um publish"]
anti_cheat: "none. Teardown 2.x has multiplayer; the PhysX path switched itself off in multiplayer and every test was a single-player sandbox (Lee, Marina, Mansion, Mall)"
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: ["@skurtyyskirts"]
date: 2026-10-22
links: ["https://github.com/NVIDIA-Omniverse/PhysX", "https://github.com/TsudaKageyu/minhook", "https://github.com/morluto/rea", "https://www.npmjs.com/package/rea-agents", "https://github.com/NationalSecurityAgency/ghidra/releases", "https://adoptium.net/"]
tags: ["physics", "performance", "physx", "cuda", "gpu", "multithreading", "solver", "graph-colouring", "particles", "dsound-proxy", "minhook", "aob-signatures", "lua-api", "ghidra", "rea", "flight-recorder", "safety"]
---

# Physics Accelerator: a multi-core replay of Teardown's island solver, two PhysX 5.9 remaps, and a flight recorder (native dsound.dll)

The goal was to make Teardown's physics use more of the PC: an i9-14900K (8P+16E, 32 threads) and an RTX 5090. The
mod is a `dsound.dll` proxy that hooks the engine with MinHook through AOB signatures, plus a small Lua mod. Five
designs were tried over three nights. A CUDA debris co-processor was rejected for feel. A full PhysX 5.9 remap (v1)
ran 10x slower than stock. A **multi-core replay of Teardown's own island solver** replays the engine's job
bit-exactly when run serially (12/12 islands identical); its parallel graph-coloured pass doubled fps on a debris
pile (36 -> 71) but is **not** bit-exact (velocities differ by 0.01-0.08 m/s on average, up to ~4 m/s on single
bodies during impacts). A GPU PhysX remap (v2) reached 83 fps on the pile, but in an
explosion it **froze the whole PC and forced a hard restart**. The current 0.2 restarts from measurement: a flight
recorder, plus exact speed-ups that check themselves against the engine in game. In the user's first 0.2 session
both speed-ups switched themselves off and the game ran no faster. 0.2.1 is committed as WIP, untested and not
installed. The project lives in the user's own local git repo and has not been released.

> **Safety lesson, read this first.** PhysX v2 mirrored the static level as greedy voxel boxes, streamed around
> every awake body. In an automated explosion benchmark that mirror grew to **349,141 static shapes**. One GPU step
> then ran for about **207 s**, the Teardown process hung inside the NVIDIA driver, `taskkill /F` couldn't end it,
> the graphics-driver reset (Win+Ctrl+Shift+B) didn't release it, and the user had to **hard-restart the PC**.
> Anything that streams geometry or work to the GPU from game state needs hard caps that act **before** a step is
> submitted: a cap on shapes, a cap on awake bodies, and a time budget, with a fallback to the engine's own
> physics. A timeout measured after the step returns is too late, because a runaway GPU step may never return
> while the PC is still usable. See Gotcha 1 and the `[physx]` limits under Build steps.

## Setup
- **Game:** Teardown 2.1.0, Steam, buildid 25295735. It renders with D3D12 (`options.xml` gfxapi=1) and scripts in
  Luau. There's no anti-cheat. The exe carries SteamStub (a `.bind` section, and `.text` encrypted on disk). The mod
  never edits the exe on disk; it hooks the decrypted image in memory after the game has started.
- **Machine:** i9-14900K (logical 0-15 are P-core HT pairs, 16-31 are E-cores), RTX 5090 32 GB (driver 617.42), 64 GB
  RAM, Windows 11 build 26200. 35-40 Steam Workshop mods were active in every session; the user asked to keep them
  for benchmarks.
- **Build:** Visual Studio 2026 Community 18.10.4 (MSVC, C++20, static CRT so the proxy needs no runtime DLLs),
  CMake 3.24+ and Ninja through a `build.cmd` that finds `vcvars64.bat` with `vswhere`. MinHook is vendored
  (`third_party/minhook`; the version wasn't recorded).
- **PhysX (v1/v2 only):** NVIDIA PhysX 5.9.0 built locally from the public source, with the prebuilt `PhysXGpu_64.dll`
  fetched by PhysX's own packman. It ships next to the mod as `tpa_physx\` (`PhysX.dll`, `PhysXCommon.dll`,
  `PhysXFoundation.dll`, `PhysXGpu_64.dll`, plus the mod's `tpa_physx.dll` backend and PhysX's licence). Building
  against CUDA 13.4 (sm_120) needed two source patches; see Gotcha 9.
- **CUDA co-processor (abandoned):** CUDA 13.4 toolkit, CUB sort.
- **Reverse engineering:**
  - [REA](https://github.com/morluto/rea) as an MCP server (`rea-agents@6.5.0` from npm), with Ghidra 12.1.4 PUBLIC
    as its analysis provider, on Eclipse Temurin JDK 21.0.12 and Node.js 24.15.0.
  - It was registered for Claude Code with `npx -y -p rea-agents@6.5.0 rea-agents setup --client claude_code --yes`.
    That writes a user-scope stdio server (`cmd.exe /d /c npx -y rea-agents@6.5.0 mcp`, env `GHIDRA_INSTALL_DIR`
    and `JAVA_HOME`) and installs REA's `reverse-engineer-anything` skill.
  - Ghidra came from the official zip, checked against its published SHA-256, with `GHIDRA_INSTALL_DIR` set as a
    user environment variable. `rea-agents doctor` passes every Ghidra check. Hopper, IDA and JADX show as missing,
    which is expected on Windows.
  - On Windows, REA's Ghidra access is read-only: decompile, xrefs and calls, but no renames.
  - Two small Python tools did most of the day-to-day work (run with `uv run --with capstone --with pefile --with
    numpy`):
    - a disassembler with `dis <rva> [n]`, `calls <rva>` and `callers <rva>` over a private dump of the code
      section;
    - `sigmake`, which returns the shortest byte pattern unique in that dump, with `??` for rel32 and
      RIP-relative operands.
- **universal-modder:** `um backup create` for `%LOCALAPPDATA%\Teardown` and `Documents\Teardown` before every
  modded launch, `um win launch --steam 1167630`, `um win kill <pid>` and `um publish check` on the release folder.
  A `MODLOG.md` plus a handoff file kept the project resumable across sessions.

## Route and why
- **Native hooks through a `dsound.dll` proxy.**
  - The physics is native C++ with no plugin API, and Lua can't change scheduling or reach the GPU.
  - `teardown.exe` imports only `DSOUND.dll` ordinal 1, it's not a KnownDLL, and so a proxy next to the exe loads
    first. The proxy forwards to the system DLL.
  - All signature scanning is deferred to a "late init", once the game is running and `.text` is decrypted.
  - A global Lua mod (`mods\PhysicsAccelerator`) marks level loads and draws a HUD.
- **Rejected or parked:**
  - CPU scheduling tweaks alone (priorities, P-core placement, EcoQoS off, 0.5 ms timer): no measurable change.
  - The CUDA co-processor: it measured faster, but debris didn't feel like Teardown.
  - PhysX v1 and v2: see Verification.
- **What stands now:** exact replacements of engine hot spots, each verified against the engine in game before it
  takes over.

## How the game works (what we had to learn)
All addresses are RVAs from the `teardown.exe` base, for build 25295735. Every RVA used in code is found through a
signature that is unique in the code section, and an offline self-test checks every signature against a private
dump (75-77 signatures by 0.2.1).

**Job system** (platform layer 0x500000-0x512500):
- Init 0x501000 creates ncpu-1 = 31 "job manager: worker #%d" threads (proc 0x502170) plus one extra worker and a
  pool of 64 fibers. The job queue is a Vyukov MPMC of 0x2000 entries. The global manager pointer is at 0x1e57488.
- Workers run at BELOW_NORMAL priority (0x5121d0 maps level 1 to -1), with affinity 0xffffffff (no pinning). They
  park on a semaphore through 0x5111d0.
- 0x501b20 executes a job: vtable slot 1 (run), state 4, signal the waiter, release continuations.
- Other functions: 0x502310 push (runs the job inline if the queue is full), 0x501e30 wake, 0x5025e0 wait, 0x5024a0
  add continuation.
- Job object: +8 state (1 waiting, 2 queued, 3 running, 4 done), +0xc prerequisites, +0x10 waiter, +0x40 payload.
- MSVC RTTI is present, so every job class has a name: `TSolver::TSolverJob`, `BroadPhaseJob`,
  `NearPhaseCollectJob`, `NearPhaseAddContactJob`, `ParticleSystem::FluidSetupJob` and more.
- Jobs run on fibers that can migrate between threads mid-job.

**Main loop and profiler:**
- The global game object is at 0x1c6e270: game+0x50 is the scene, game+0x8d8 the profiler, game+0x23c the timestep.
- The frame function is 0x71ce0, and the scene update is 0xf2640.
- Timed sections go through 0x45bcf0(profiler, category, seconds). Categories: 1 destruction, 2 particle, 3 path
  planning, 4 physics, 5 rendering, 6 screen, 7 script (server), 8 script, 9 water.
- The built-in profiler opens with Shift+Alt+F3.

**Physics step 0xb20a0** (world = scene+8, dt):
1. A ParallelFor 0xb4000 over bodies does the velocity pre-pass:
   - angular w *= 0.996, clamped to ±40 rad/s;
   - touching bodies get a further w *= 0.999, and tiny debris (inverse inertia > 100) w *= 0.93;
   - linear velocity is not damped;
   - **when wind is on (world+0xa51), every awake body's v is blended toward the wind field 0xd8ad0.**
2. Broadphase: six dbvt tree pairs by body class (static large and small, sleeping, sleeping debris, awake, awake
   debris), one `BroadPhaseJob` per pair (run 0xad920). The pair rules:
   - no pairs within one body, and none between two statics;
   - debris (shape flag 0x08) collides only with statics;
   - layer and mask bytes at shape+0xca/+0xcb must match both ways;
   - equal nonzero groups at +0xcc don't collide, and neither do no-collide joints.
3. Nearphase: `NearPhaseCollectJob` 0xadb40 calls the voxel collide 0xaf740, which calls 0xae130 both ways.
   - It tests surface voxels of A against B's occupancy grid, at both the current and the predicted pose.
   - It sweeps in 0.1 m steps when a voxel moves more than 0.12 m (built-in CCD).
4. Solve (`TSolver` at world+0x180c0), detailed below.
5. Sleep: the per-island threshold is 0.02 × (clamp((n-8)·0.2, 0, 2) + 1); the awake counter goes up to 60.

**TSolver** (0x5fd110, main thread):
- It gathers constraints, builds islands 0x5f80a0 (table +0x88418 of {c0, nc, b0, nb}), quicksorts each island's
  constraints serially (0x5f5920), runs body setup 0x5fa2e0 and fills a compact velocity array at +0x70 (24 bytes
  per slot: v, w).
- It then hands **whole islands** to `TSolverJob`s (vtable 0xa9cb68, run 0x5f7ae0), greedily by load.
- Per island, a job runs:
  - body setup;
  - prepare by constraint type (0: 0x5fa5e0, 2: 0x5f9c10, 3: 0x5fb280, 4: 0x5f99a0, 5: 0x5fb670);
  - gravity;
  - **8 × {sequential-impulse pass 0x5fdd60, linear velocity clamp 0x5f77e0}**;
  - integrate 0x5fc050.
- Each prepared constraint touches only the two body slots at record +4/+8. Static bodies have zero inverse mass and
  form singleton islands.
- **One debris pile is one island, so it runs on one core while 30 workers idle.** That is the whole case for
  `solver_mt`.

**Bodies, materials and damage:**
- Body fields:
  - +0x40 pose (pos and quat), +0xd8 v, +0xe4 w;
  - +0xf0 inverse inertia, +0xfc **inverse** mass (not mass), +0x100 local centre of mass;
  - +0x138 dynamic flag, +0x140 awake counter (a wake sets 60), +0x144 gravity scale;
  - +0x148 friction (default 0.8), +0x14c restitution (0.1), +0x150/+0x151 combine modes (same order as
    `PxCombineMode`).
- A voxel (x, y, z) maps to shape-local ((x+.5)s, (y+.5)s, (z+.5)s). Vox: +0/+4/+8 dims, +0x10 palette bytes,
  +0x20 scale.
- Materials (names at 0xbef1b0): 0 none, 1 glass, 2 wood, 3 masonry, 4 plaster, 5 metal, 6 heavymetal, 7 rock,
  8 dirt, 9 foliage, 10 plastic, 11 hardmetal, 12 hardmasonry, 13 ice, 14 unphysical.
- Density table 0xbefa50: 1.0, 1.5, 0.8, 2.0, 2.0, 3.0, 3.0, 3.0, 1.5, 0.7, 0.7, 3.0, 2.0, 0.8, 1.0. Mass per voxel
  = density × 500 × s³ × shape+0xd0.
- Impact damage (contact creation 0xacb40):
  - Strength table 0xbef708: glass 0.2, wood 1, masonry 2, plaster 1, metal 3, dirt 3, foliage 0.2, plastic 0.6,
    ice 0.5, the rest 0 (unbreakable).
  - A damage record is made only above 6 m/s relative velocity. S = strength × 1200 × shape+0xd4.
  - The solver clamps the contact's normal impulse at min(S_A, S_B), so a heavy body punches through a weak wall
    and keeps the rest of its momentum.
  - After the solve, holes go through 0x137d60, with radii 1.2× and 0.8× of impulse/strength.
  - Impact and slide sounds come from records at world+0xa3060.
  - A physics replacement that bypasses the engine's contacts loses all of this unless it rebuilds it. PhysX v1 had
    no impact damage at all.

**Luau binding** (needed for the mod's own `TPA_*` functions and for an in-process test bridge):
- API nodes are `{thunk, const char* name, next}` in two linked lists: 490 game functions (head 0x1e53e70) and 77
  core ones such as GetTime, StartLevel and Input*.
- The walker 0x4a8520 registers each node on a script.
- C API addresses:
  - `lua_gettop` 0x628f00, `lua_pushstring` 0x629930, `lua_pushnumber` 0x629910, `lua_pushboolean` 0x629700;
  - `lua_pushcclosure` 0x629720 with the trampoline 0x6372c0, `lua_setfield` 0x62a040, `lua_pcall` 0x629670;
  - `lua_tolstring` 0x62a4c0, `lua_type` 0x62a690.
- Engine argument helpers: bool 0x631a00, int 0x631b80, float 0x631a30, string 0x631c90. Return helper: float
  0x630650.
- Game API thunks go through the dispatcher 0x4a9050, which checks client and server permission. Per-script
  callbacks are 0x46b160 (update), 0x46a830 (tick) and 0x469b90 (screen).
- The engine string (TString, 32 B) is inline unless byte 0x1f is nonzero, in which case it's a heap pointer.
- The stock menu calls `GetTime()` every frame. Wrapping `GetTime`'s node therefore gives a hook into every script,
  the menu included. The bridge runs queued Lua chunks there, from a named pipe `\\.\pipe\tpa_bridge` (local
  clients only).

**Particles** (category 2, 0x42fb50, manager at scene+0x18):
- Smoke systems use a 1 m uniform grid with u16 cell counts, so each system tops out at about 65.5k particles.
- `FluidSetupJob`s (run 0x4340d0) pack up to 32 cells per job, but **cut a job as soon as it holds more than 32
  primary particles**. A dense smoke cell is therefore one job, however many particles it holds.
- Inside that job, the neighbour pass 0x4365d0 (pair list 0x4314b0) is O(n²). In the five-explosion demo, one such
  job took 88.8 ms of a 101 ms particle update.
- Particle-vs-voxel collision goes 0x433b50 → 0x4ddfe0 → 0x106a80, a brute-force nearest-surface-voxel scan of
  about (2r/voxel)³ voxels per particle-shape pair.
- The main thread sleeps on the job group (0x5025e0) and doesn't help.

## Build steps
The project is local-only; this is the order that reproduces it.

1. **Proxy core.**
   - `dsound.dll` exports the same ordinal as the system DLL and forwards to it.
   - Hooks go on kernel32 imports. The first call from the exe into one of them triggers late init: the signature
     scan, then MinHook on every target.
   - Logs go to `tpa.log` next to the exe, and settings come from `tpa.ini` (`GetPrivateProfileIntW`).
2. **Signatures.**
   - Generate them with `sigmake` from the code-section dump. Keep a self-test exe (`tpa_selftest <dump>`) that
     asserts each one matches once at the expected RVA, and run it after every change. A Steam update to the game
     breaks it first.
3. **solver_mt (keep: serial replay exact, parallel pass approximate).** Hook `TSolverJob` run 0x5f7ae0.
   - For a normal island, replay the same per-island sequence by calling the engine's own functions: setup →
     prepare by type → gravity (gravity vector rotated by 0x30d40, v += gscale·dt·g) → copy v/w into the compact
     array → 8 × {pass, clamp} → copy back → integrate.
     - The first in-game check compared 12 islands against the engine's own job on the same snapshot; all 12 were
       bit-identical.
   - For a big island, run setup, prepare and gravity on the mod's own thread pool. Run each pass as greedy
     **graph-coloured batches**:
     - a task is a run of constraints on one body pair, grouped through a hash, because one pair's contacts aren't
       adjacent in the engine's order;
     - no two tasks of one colour share a dynamic body;
     - colours run in order, so this stays Gauss-Seidel; only the order inside a pass changes;
     - batches are sorted by body slot to avoid false sharing on the 24-byte compact entries;
     - colours smaller than `min_batch=48` run on the calling thread;
     - tasks that find no free colour run serially afterwards.
   - The parallel result is not bit-exact (8 iterations aren't converged). Mean |dv| was 0.01-0.08 m/s, up to about
     4 m/s on single bodies during impacts. Piles looked the same in screenshots.
4. **0.2 gating for solver_mt.**
   - Only one island per step goes to the pool: the biggest, and only if it has at least `min_constraints=2048`
     constraints and at least `dominance=50` % of the step's constraints. Everything else runs the original job.
   - A **self A/B** alternates pool and engine on dominant steps and compares ms per 1000 constraints. The pool
     stays on only if it is at least 15 % faster, and it retries 3600 dominant steps after losing (900 in 0.2.1).
   - Resetting the A/B state from the bridge thread was a use-after-free race. The reset is now a flag that the main
     thread applies.
5. **C1, the smoke neighbour pass (keep: exact).** Hook 0x4365d0.
   - For each primary particle k of a heavy cell, in parallel over k: walk the other primaries in the engine's
     order (earlier ones reversed, then later ones), then the ghosts. Apply the engine's 16-slot "keep the
     strongest" update verbatim:
     - `minss` semantics for the running minimum;
     - replace the **last** slot equal to the minimum;
     - the slot index starts at 16, so a full record can overflow 0x14 bytes into the next particle's record. Keep
       that overflow.
   - Then the second pass: +0x10 = 1/(sum + 2⁻²³). Leave out the pair list and its allocations.
   - It's exact only with `/fp:precise` and no FMA contraction, so don't build with `/arch:AVX2`.
   - A verify mode runs on the first 48 heavy cells: run the engine on a snapshot, run ours, compare byte for byte.
     The hook switches `on` only if every cell matches and ours is faster; otherwise it reports `off-mismatch` and
     leaves the engine's result in place.
6. **Flight recorder (0.2).**
   - Game threads push small records into per-thread rings:
     - frames, through the frame hook 0x71ce0;
     - jobs, through 0x501b20, named by their RTTI class;
     - API calls, through 0x4a9050;
     - profiler categories, forwarded by the telemetry hook (MinHook can't hook one function twice).
   - A sampler thread suspends the main thread at 1 kHz, and two workers per tick, then walks their stacks with
     `RtlVirtualUnwind` and no locks.
   - A recorder thread rewrites `tpa_flight\<date-time>\summary.txt`, `seconds.csv` and `worst_frames.csv` every
     few seconds. The cost measured offline was 1.4-1.5 % of the main thread.
7. **Install and uninstall** (PowerShell, Teardown closed):
   - `deploy.ps1` refuses to run if Teardown is running, snapshots `%LOCALAPPDATA%\Teardown` with `um backup`, and
     copies the native files and the Lua mod to two different places:
     - `dsound.dll` and `tpa.ini` (an existing one is kept as `tpa.ini.old`) go **next to `teardown.exe`** in the
       game folder; the proxy only loads from there, and `tpa.ini`/`tpa.log` live there too;
     - the Lua mod goes into `Documents\Teardown\mods\PhysicsAccelerator`.
   - `remove.ps1` moves every installed file, logs included, into a timestamped folder in the repo rather than
     deleting it.
   - Deleting `dsound.dll` alone uninstalls the native part.
8. **PhysX v2 safety limits, if you build a GPU path anyway.** These are the user's own `tpa.ini` keys from the
   guarded build. Past any limit, every body goes back to Teardown's physics until the next level load:

   ```ini
   [physx]
   ; Safety: past any of these limits (or a PhysX step slower than max_wait_ms) every body goes back to
   ; Teardown's own physics until the next level load, and the game keeps running.
   max_static_shapes=60000
   max_shapes=100000
   max_awake=6000
   max_wait_ms=250
   ```

   The shape and awake checks run before the step is submitted. `max_wait_ms` only catches a slow step after it
   returns, which is why the counts matter more. An offline harness run with the limit forced to 300 shapes showed
   the bail handing all 450 bodies back without a crash.

## Verification
The user played and the agent read logs afterwards. From 2026-10-22 the agent did not launch the game at all; the
user runs every test. All numbers come from the real game unless marked offline.

**CUDA co-processor (2026-10-17):** a 2000-box pile ("storm2000") in the Lee sandbox cost 2.1-2.7 ms of CPU per step
against 10.1 ms vanilla. In play, though, explosion debris felt unlike Teardown: one-way coupling, 64-sample
approximations, and 1818 takeovers against 1331 hand-backs. The user rejected it.

**PhysX v1 (all bodies on PhysX GPU, 2026-10-18 00:30-01:13, Mansion and Mall):**
- At rest on Mansion and Mall it ran 11-18 ms per step.
- A live A/B on the same Mall scene (2168 bodies, about 780 awake): PhysX on gave 15.6 fps and a 26.4 ms step;
  PhysX off gave **91.2 fps and a 2.5 ms step**.
- After a big explosion: 4185 bodies, a 113 ms step, 52 ms of sync and 53 ms of fetch.
- The GPU sat at 15 %. The cost was the single-threaded sync plus the fetch round trip.
- Uninstalled, packaged with PhysX off (`um publish check`: 13 files, 0 failures), and Steam verified the game
  files with nothing re-downloaded.

**solver_mt (Lee sandbox, the user's 36 mods):**
- Serial replay: 12/12 islands bit-identical in verify mode.
- Parallel pass (approximate, see Build step 3): storm2000 step 9.9 → 5.7 ms, solve 6.8 → 3.1 ms, **fps 36.5 →
  70.8**.
- Five size-4 explosions on buildings ("demo"): step 30.9 → 22.5 ms in one A/B, but 16.9 → 18.4 ms (slower) in a
  later run. It's unproven on destruction.

**PhysX v2** (async step a frame ahead, no per-pair reports, force-threshold impacts driving the engine's own damage
and sounds, Teardown's damping and sleep rules mapped onto PhysX, speculative CCD):

| Scene | Teardown physics | solver_mt | PhysX v2 (GPU) |
|---|---|---|---|
| storm2000 pile | 9.7 ms, 41.5 fps | 6.5 ms, 56.7 fps | 3.6 ms, 83 fps |
| demo, 5 explosions | 16.9 ms, 4.7 fps | 18.4 ms, 3.8 fps | 760 ms (max 1568), 1.6 fps, then the PC froze |

- Offline, v2 handled 3000 thrown debris pieces at about 3 ms of main thread per step, against about 55 ms for v1.
  Real content was the difference.
- With the guard installed, the user's own Marina session ran about 90-110 fps for 50 s. Then one PhysX step took
  **1389 ms** and tripped the bail, and the rest of the session averaged about 66 fps on stock physics.
- Because the bail re-arms at every level load, expect at least one freeze per level.

**Where explosion frames really go** (four demo runs): particles 41-44 %, the user's mod scripts 27-32 %, physics
13-15 %, destruction 3-6 %. About 5 of 32 threads were busy and the GPU sat at 20-35 %. Even free physics would only
take the demo from 4.7 to about 5.5 fps. This review (2026-10-22) is why PhysX was archived and 0.2 began.

**0.2 (installed 2026-10-22, user session at Marina with a building explosion):** "about 15 fps ... not any better
at all". The recorder showed why:
- Both speed-ups had switched themselves off:
  - C1 reported a false `off-mismatch` in the menu (Gotcha 6);
  - solver_mt lost its A/B by ×1.19 (Gotcha 7).
- Heavy frames averaged 87 ms: physics 47.9 (2 steps per frame, the cap, so the game ran in slow motion), scripts
  16.8, particles 2.6. Smoke was not the problem in that scene.
- Physics stayed at about 24 ms per step for over 50 s after the explosion. Wind was on (Gotcha 8).
- One step is a chain of single-thread stages:
  - broadphase, one job of 6-7 ms;
  - nearphase, one heavy pair of 6-9 ms (0xae130);
  - about 6 ms serial on the main thread (island build, quicksort, body setup);
  - the solver's biggest island, 13-22 ms (0x5fdf80, the contact solve, is 71 % of solver samples);
  - breakage, 3-8 ms.
  Meanwhile the workers were about 6 % busy.
- Mods on the main thread: `QueryAabbBodies` 5 ms, `LoadLoop` + `LoadSound` 8.5 ms per heavy frame (some mod
  reloads sounds every frame), and 1 s hitches from one huge AABB query in Lua.

**Offline tests (pass at 0.2):** the signature self-test (77/77), the unwinder (2000/2000 full chains), the flight
recorder against a fake engine, solver_mt against a race-detecting fake TSolver (serial == parallel, no overlap,
win/lose gating), and C1 (60 random cells identical to a transcription of the engine's sequence, about 14× on a
3000-particle cell). 0.2.1 has **not** been re-tested.

**Not verified:** C1 taking over in game (it matched 21 heavy cells, then hit the false mismatch of Gotcha 6, so
it never switched on); solver_mt with P-core
pinning; whether disabling the weather mods lets debris sleep; PhysX v2 vehicles and `GetBodyHit` lists.

## Gotchas
1. **The PC froze and needed a hard restart during an automated explosion benchmark with PhysX v2.**
   - **Cause:** the static world was mirrored into PhysX as greedy boxes per voxel brick, streamed around every
     awake body. In destruction that has no bound: 349k static shapes and one GPU step of about 207 s. The process
     then hung in the NVIDIA driver, where `taskkill /F` couldn't end it and Win+Ctrl+Shift+B didn't free it. A
     Ghidra/REA Java session was also still running and had to be killed.
   - **Fix:**
     - cap static shapes, total shapes and awake bodies, and check the caps **before** submitting each step;
     - hand everything back to the engine on a trip;
     - keep `max_wait_ms` as a second line only;
     - never run a GPU-heavy benchmark alongside other heavy jobs;
     - ask before every launch.
   - The real fix is a static representation that doesn't grow with destruction: build it once per level and sync
     only what changed. That was never built.
2. **A PhysX step stalls 1.4 s even with the guard.** **Cause:** a time-based bail fires only after a slow step has
   already happened, and it re-arms at every level load. **Fix:** the count-based limits above, or leave the GPU
   path off. It was archived in 0.2.
3. **PhysX was 10x slower than stock in game, yet fast offline.** **Cause:** Teardown's own voxel solver over 31
   workers is very fast (2.5 ms on the Mall scene). The PhysX cost was the single-threaded sync of thousands of
   bodies and the `fetchResults` round trip, not the simulation. Offline scenes lacked real static content.
   **Fix:** measure in the real game with real mods before building out a design. Profile first (the 0.2 recorder).
4. **Crash at startup, 0xC06D007E on the PhysX init thread.** **Cause:** `PhysX.dll` delay-loads `PhysXCommon.dll` on
   its first call, after the code had already reset the DLL search directory, so only the game folder was searched.
   **Fix:** preload `PhysXCommon.dll` from `tpa_physx\` explicitly, and test from the installed folder layout.
5. **Access violation in `NpScene::getFlags` (via `isSleeping`) on the bridge thread.** **Cause:** a stats report
   ran without the step lock while `set_parts` removed an actor and re-added it, so the actor had no scene. **Fix:**
   take the step mutex in every report, and skip actors that have no scene.
6. **C1 switched itself off in the main menu, with "MISMATCH ... foreign overflow bytes".** **Cause:** the slot-16
   overflow can write into a record owned by another cell's job, and that write races in the engine itself, so
   comparing those bytes isn't deterministic. **Fix:** 0.2.1 compares only the cell's own records.
7. **solver_mt lost its in-game A/B (×1.19 slower), though it won 2× offline and on piles.** **Cause:** its 12 pool
   threads were unpinned and spun in barriers on E-cores, contending with 63 other solver jobs and the engine's 31
   workers. In 0.1, every big island also took one pool mutex, so islands the engine solves side by side queued.
   **Fix:**
   - gate the pool to one dominant island per step;
   - drop the 3 ms keep-awake spin;
   - pin the pool to P-cores with at most nfast-1 threads (0.2.1);
   - in 0.2.1, also move any engine job that has run more than 1 ms on an E-core to the P-cores
     (`SetThreadAffinityMask`, at most 6 at once, undone when the job ends). This changes only placement, so it
     stays exact, and it's kept only if a main-thread A/B shows it at least 5 % faster.
8. **Debris never goes to sleep after an explosion, so physics costs 24 ms per step for over a minute.** **Cause
   (suspected):** wind was on (world+0xa51), and the velocity pre-pass blends every awake body's velocity toward
   the wind field, so pieces never settle under the sleep threshold. The user's weather mods are the suspects
   (Hurricanes & Blizzards, Weather editor, Vortexes and Tornadoes). **Fix:** untested. Repeat the same explosion
   with those mods off.
9. **PhysX 5.9 doesn't build or run against CUDA 13.** **Cause:** API changes. **Fix:** in the local PhysX build:
   - patch `CudaContextManager`'s `cuCtxCreate` call to the CUDA 13 signature;
   - stub `__cudaGetKernel` and `__cudaLaunchKernel` in `CudaKernelWrangler` (PhysX launches through the driver
     API).
10. **PhysX on the CPU produced no impact sounds or damage.** **Cause:** the CPU TGS solver writes no force-threshold
    stream, so `eNOTIFY_THRESHOLD_FORCE_FOUND` never fires. **Fix:** use `eNOTIFY_TOUCH_FOUND` on the CPU and
    threshold events on the GPU.
11. **A motorised slider fell asleep under PhysX.** **Cause:** the Teardown sleep rule ran on bodies a motor was
    driving. **Fix:** a motor drive sets the awake counter to 60 and wakes the body.
12. **The documented live kill switch (`pset active 0`) didn't stick.** **Cause:** the Lua mod's tick set `active`
    again every frame. **Fix:** switch through the mod's savegame key instead (`SetBool('savegame.mod.physx_off',
    true)` in the client realm).
13. **PhysX warnings and overflows were invisible.** **Cause:** PhysX's default error callback writes only to
    `OutputDebugString`. **Fix:** route the error callback to `tpa.log`.
14. **Mouse and keyboard injected with SendInput never reach Teardown's menus.** **Fix:** drive the game through the
    in-process Lua bridge. The splash screen also ignores `StartLevel`, so call `Menu()` first.
15. **A bridge payload that spawned 2000 bodies crashed the proxy.** **Cause:** the Lua stack was reallocated inside
    `lua_pcall`, so saved raw stack pointers dangled. **Fix:** keep offsets from `L->stack` (L+0x40), not pointers.
16. **REA's in-session Ghidra server timed out on the 30 MB exe.** **Cause:** the default startup deadline is 330 s,
    and the first analysis took 6.8 min. **Fix:** one persistent REA process that every call goes through:
    - `REA_GHIDRA_STARTUP_TIMEOUT_MS=14400000`, `GHIDRA_HEADLESS_MAXMEM=16G`;
    - `REA_GHIDRA_DISABLED_ANALYZERS=WindowsResourceReference,Embedded Media`;
    - below-normal priority, pinned to the E-cores, forwarding tool calls over a localhost socket.
17. **A helper script named `dis.py` broke Python imports.** **Cause:** it shadowed the standard-library `dis`
    module. **Fix:** rename it (`tdis.py`).
18. **`claude mcp add-json` rejected every server with "Invalid input" on Windows.** **Cause:** the JSON quoting was
    mangled by the Windows shim. **Fix:** use `claude mcp add --scope user <name> -- <command> <args...>`.
19. **The first `script_update` signature matched twice.** **Cause:** two near-identical functions share every
    prefix. **Fix:** use sigmake's longer signature, which runs past the function's end.
20. **MSVC refused `__try` in the sampler helpers.** **Cause:** SEH isn't allowed in functions that need C++ object
    unwinding. **Fix:** move guarded reads into small plain helper functions.
21. **Worker stack samples were filed under the wrong job class.** **Cause:** fibers migrate between threads
    mid-job, so a per-thread "current class" goes stale. **Fix:** keep a worker sample only if its walked stack
    contains the job hook's own frame. Mark the hook `noinline`, and match on its start address, because the
    optimizer splits it into fragments.
22. **Function names in the report attached to the wrong DLL.** **Cause:** samples were keyed by module index, and
    the module table re-sorts when DLLs load later. **Fix:** key samples by absolute address and keep an append-only
    base → name map.

## Assets
None. The HUD is plain `UiText` in the Lua mod.

## Cost and time
- Agent work on 2026-10-17, 10-18 and 10-22, across five sessions. One of them only set up Ghidra and REA. Total
  hours and spend weren't recorded.
- One hard PC restart (Gotcha 1).

## Open questions
- Does debris settle with the weather mods off? If it does, wind is most of the post-explosion cost.
- Test and install 0.2.1, and read its per-script API attribution: which Workshop mod calls `QueryAabbBodies` and
  reloads sounds every frame?
- Exact speed-ups that remain:
  - split the heavy nearphase pair (0xae130) by voxel ranges, concatenating in order;
  - a parallel per-island sort and island build;
  - parallel broadphase tree traversal (pair order matters downstream);
  - C2, an exact pruned nearest-voxel search for 0x106a80;
  - C3, splitting the particle collision pass.
- A GPU path would need a static world built once per level with incremental sync, and limits checked before
  submission. Even then it can only speed up the physics share of a frame.
