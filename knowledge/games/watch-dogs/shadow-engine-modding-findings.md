---
kind: game
title: "Watch Dogs Shadow Engine: practical modding findings (shadows, vehicles, world, Lua)"
game: "Watch Dogs"
games_also: []
game_version: "see note — findings are per RuntimeProfile (Global/04DF, Shev/A4EE, VMPless, Complete Edition, Asia/Miru; VMPless is a shipped build without VMProtect packing, not a cracked dump); policy controls are Global .12–.15"
platform: windows
engine: unknown
route: native-hook
tools: ["NexusTools host/loader", "Ghidra", "Python (offline harnesses)", "TinyCC 0.9.27 (win64)", "custom population/workload capture", "ETW/DXGI presentation capture"]
anti_cheat: "No anti-cheat interaction is documented. Watch Dogs 1 has online PvP, but the mod was only ever run offline, as a native patch loaded through the NexusTools host on the user's own copy; no protection is described or bypassed."
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links: ["https://github.com/temdah/Shadow-Engine", "https://github.com/temdah/Watch_Dogs_OKF"]
tags: ["disrupt", "shadow-engine", "shadows", "vehicle-lights", "world-streaming", "lua", "nexustools", "measurement"]
---
# Watch Dogs Shadow Engine: practical modding findings

> The Shadow Engine mod raises WD1's shadow-map capacity, caps vehicle-headlight
> shadow quality, and adds a headlight limiter, all driven from a NexusTools Lua menu.
> This note collects the practical findings: how admission/residency/quality actually
> behave, how vehicle lights can and cannot be identified, how world data and streaming
> gates visibility, and where the Lua host interfaces. It also records the failed
> approaches and the measurement methods that keep claims honest.

## Setup

- Game: Watch Dogs 1 (PC, x64), loaded via the NexusTools host. WD1 has online PvP, but this mod was only run offline.
- The mod is a native patch plus a Lua menu and a file-mailbox bridge. It changes
  shadow capacity, vehicle-light quality caps and a headlight limiter.
- Policy values in this note are from the Global profile .12–.15 experiments; other
  profiles share the same policy code but have their own RVAs.
- Runtime controls: the mod exports a small API and reads a bounded settings file;
  the Lua menu sends requests through a native-owned file mailbox.

## Route and why

- Native hook is required because admission, residency and pass registration are
  compiled into the engine; there is no data-side switch for them.
- The mod deliberately keeps policy shared across profiles and puts all build-specific
  knowledge in immutable `RuntimeProfile` data.
- Quality capping is applied at the queue/resource boundary so it cannot accidentally
  upscale: every capped dimension is `min(native, cap)`.
- Vehicle-light suppression is gated behind an owner-aware classification because the
  renderer type alone cannot distinguish a vehicle headlight from a world spotlight.

## How the game works (what we had to learn)

### Shadow admission, residency and quality

- The manager (`0x002E9B60` in Global) reconciles each cached owner's identity against
  the admitted set, marks unmatched owners unused, and evaluates each candidate's
  descriptor type, intensity factor and coverage before binding.
- Admission predicates (Global): descriptor type `0` appends without consuming the
  ordinary count; type `2` appends without consuming it only when `L+0x40 & 0x84000000`
  is non-zero; type `4` is skipped; type `3` requires config `+A48` non-zero. The
  ordinary ceiling is `B4 - (A8 != 0) + A8`; with B4=21 and A8=4 that is 24 light
  records. The first 20 ordinary bindings take the dynamic lane; later ones seek
  cached owners.
- `B4` controls the fully-dynamic lane (ordinary dynamic positions ≈ B4−1). `A8`
  bounds cached owners rotating through a shared low-resolution refresh lane — these
  are not extra high-resolution maps.
- Residency: the manager increments each owner's age, selects the greatest age, marks
  the binding for update, resets the age and sets the owner's update flag. With
  `manager+B0` enabled, every newly assigned owner can get an immediate update,
  suppressing the usual oldest-refresh for that call.
- `B4` is scene-adaptive, not a backpressure controller: it initialises to 4, changes
  by at most one per manager call, and its deciding branch reads candidate/descriptor
  fields — it does not consume frame time, GPU time, requested faces or backlog.
- Vehicle quality caps only exact recent vehicle-owned type-1/type-3 requests at
  512/1024/2048/4096 and preserves native otherwise. The `.83` change removed a
  temporary driven-car exemption, so the cap now applies to every exact vehicle-owned
  request including the driven car; limiter protection is separate.
- Quality publication is atomic and token-owned: the batch publisher commits ≤64
  validated observations after the native batch returns, one non-waiting token per
  epoch, so readers cannot observe an intermediate state. A lock miss preserves native.
- Queue builder `0x0030A570` writes requested dimensions at entry `+0x20A4/+0x20A8`
  and the face count at `+0x20A0`. The renderer (`0x00306E60`) passes those dims as the
  shared-texture request words and stores the resource at entry `+0x20B0`. An existing
  backing resource bypasses the lookup even though the request dims still feed
  parameters — so a capped request does not by itself prove a new allocation.

### Vehicle identity and light ownership

- Vehicle headlights and world spotlights converge before the generic renderer path,
  so renderer type 3 is not safe vehicle identity. Flag `0x80`, direction-matched
  pairs, adjacent IDs, descriptor pointer equality and spatial-tuple similarity all
  fail to authorise suppression.
- A reliable vehicle identity comes from the CVehicle/CVehicleHeadLights chain, not
  the renderer record: class getter `0x009B6630` names `CVehicle`; factory
  `0x009F0A00` allocates `0x3F0`; the update path `0x009AB5C0 -> 0x0099E5D0 ->
  0x0093D730` traverses the light array at `+0x148`/count `+0x150`, stride `0x130`.
  Component virtual `+0x30` is invoked at `0x0093D8E7`.
- Driver identity (`.82`, Global only): a direct CPawn predicate at `0x00948370`
  reads CPawn `+0x90`, requires the vehicle entity `+0x60` bit16 set and bit3 clear,
  and compares the first role-1 seat occupant's full ID against the pawn ID. This
  replaced `.80`/`.81` keyed association, which failed pawn-owner equality in all four
  lookups. Only `supported-04DF` has the optional `DriverIdentityProfile`.
- Selection guarantees (`.68`): four 512-slot selection banks with a derived
  full-handle index; allocator `0x025B0530` issues 32-bit slot+generation handles and
  teardown `0x025B84D0` increments the generation before reuse. Primaries use squared
  distance with a 0.9 incumbent weighting (~5.1% linear margin); outgoing retention is
  ≤1000 ms; predictions use a 200 ms bounded approach within ≤8 world units.
- Incoming readiness (`.66`): extra-slot ordering is actual nearby candidates within
  8 world units by current distance, then outgoing retention, then forecast arrivals.
- The native per-vehicle batch float is camera-derived, not a safe read-only getter:
  parent `0x0099E5D0` resolves the first controller at global `0x03B78508`, calls
  `0x006A5480`, and subtracts the returned `+0x0C/+0x10/+0x14` from the vehicle XYZ.
- Player position comes from `GetLocalPlayerEntityId` registration `0x02EF3620`
  (string `0x02EF3370` -> `0x006F1D80`); `0x006F1D95` reads the root array's first
  controller -> `+8` data -> `+0x10` entity reference -> `+0` full ID.
  `GetEntityPosition` registration `0x03002CD0` pairs `0x02FFDA18` with `0x01422D60`,
  which resolves the reference, reads `+8`, calls `0x0082E610`, and copies entity
  `+0x50/+0x54/+0x58`.

### World data and streaming

- Entity readbacks are not graphics transforms or visibility. A graphics component is
  constructed by `0x7E13B0`; the render object is created later. In one capture, 534 of
  545 spawned authored meshes had zero render groups and entity flag `0x22049280`,
  while only 10 reached `A2179284`; the difference was entity `+0x60` bit2. Bit2 clear
  in every failure and set in every success means the failure is before drawable
  render-object creation.
- Loading category gates streaming: appended prototypes inherited
  `wlucatLoadingUnitCategory=2` (Near) from a blood-prop, so they were only streamed
  near the player. Correcting 15 sky-stage prototypes from category 2 to World0
  (name table `0x3626970`) was exactly 15 byte changes in the entity library; the other
  1,909 archive inputs were identical. This was not yet visually accepted.
- World0 constructs a single world-wide loading unit (`0x6E15E0`/`0x6B7790`) and its
  query `0x6AF700` checks overlap with the unit's world rectangle via `0x6F0430`, not
  player distance. Near2 constructs local grid providers (`0x6E6AF0`).
- A world-quality pass caps world-light shadow dimensions while preserving native for
  unknown/ambiguous identities. It keeps a bounded per-call region cache (128 slots)
  to collapse repeated region queries; dense regions dropped 60 queries to 1–2,
  fragmented regions stayed at 60.

### Lua and mod interfaces

- The captured Global Lua runtime truncates a prototype's frame size to five bits
  (Proto byte `0B`). A constructor needing 51 registers can declare 19; the VM then
  exposes only 19 slots to stack marking, so a later table child built in R24 falls
  outside GC visibility and a subsequent access can crash. This is a register/GC
  contract defect, not a menu-item limit. It exists in a working configuration too;
  allocation/GC timing can expose it elsewhere.
- The `.57` experimental repair is 17 sites, Internal/Global only, excluded from
  Release, and has outstanding startup-synchronisation, metadata-ownership and
  lifecycle gates. Do not make other mods silently depend on it.
- The mod's exported control API (not a native Disrupt API), version 2 at `.87`:
  `ShadowEngine_GetControlApiVersion(void)`,
  `ShadowEngine_GetVehicleHeadlightLimiterEnabled(void)`,
  `ShadowEngine_SetVehicleHeadlightLimiterEnabled(int enabled)`.
  The setter returning 1 means the worker accepted the request — not that it was
  saved, applied, admitted or visible. The getter returns the last applied state.
  No file I/O happens inside the export.
- File request format: `SES2 pid session sequence mask limit vehicleQuality
  worldQuality`. Lua keeps one request in flight, coalesces later edits, and retries
  the same sequence; status separates receipt, result, saved revision and applied
  revision. Boolean API: 0 disables suppression, 1–9 finite traffic count, 10
  Unlimited; enabling a remembered count of 10 through the Boolean setter is rejected.
- Settings persistence: `SESAVE2 revision policy world` with an exact trailing LF.
  The parser rejects overflow, bad token counts, NULs, signs, trailing bytes, unknown
  bits, invalid cap-count combinations and non-positive revisions. The worker writes a
  bounded temp sibling, checks write/flush/close, then atomically replaces. The two
  policy words are separately atomic, not one transaction. Limiter changes reset
  mod-owned residency; quality-only edits do not.
- Menu host: the NexusTools host image inspected was 15,337,984 bytes, SHA256
  `8120389BA4D144DC465E9FED2648B5690A6BBF0CDF5B052EF6EE3B738BE5DCFC`, PE timestamp
  `6A82F9AC`, preferred base `0x180000000`; those RVAs apply only to that host.
- Ambient-traffic caveat: the Lua `ChangeVehiclesBudget(0)`/`RestoreBudgets` functions
  affect ambient moving-traffic spawning, not existing, parked or scripted vehicles.
  Two mods restoring the global budget can undo each other. This is separate from
  native headlight selection and shadow capacity.

## Build steps

1. Pick a policy: current fixed policy is 30 physical maps, 31 queue entries, B4=21,
   A8=4, with 8 pre-reserved owner records.
2. Apply the capacity contract (see the engine note) and the shared admission/quality
   policy; do not branch feature code on profile number.
3. Wire the control API and the settings file; keep one request in flight in Lua.
4. Register the menu through a single menu-registration owner with collision-resistant
   command IDs; register added native passes during the native registration phase.
5. Validate with offline harnesses and the runtime corpus gate before any in-game run.

Recorded policy variants: `.12` 30/31 B4=25 A8=4; `.13` 24/25 B4=16 A8=4;
`.14` 30/31 B4=16 A8=4 (no reported flicker, slightly more pop-in, 9998 balanced
results); `.15` 30/31 B4=21 A8=4.

## Verification

- **Population observer (P-A).** Distinguishes candidate presence, patch keep
  decisions, copied native eligibility inputs, native bindings, cached update
  decisions and submitted queue work. It changes no policy and installs no extra
  detour. Action 14 starts a 60 s whole-pass recording; each stream has 1,200 absolute
  50 ms buckets. File `ShadowEnginePopulation-<pid>-<UTC-filetime>-<serial>.bin`,
  schema 1, magic `SEPOP01`/`SEPOEND`, CRC32/IEEE, max 108,221,056 bytes. Global `.87`
  whole-pass: 2,400 records, 31,705,344 bytes, CRC32 `43749EB8`.
- **`.87` admission census.** Across 1,200 manager calls the first 24 ordinary-eligible
  + 2 special were bound every time; 165,520 candidate occurrences (47–297 per call);
  76,597 ordinary-eligible, 28,244 bound, 48,353 eligible/kept/unbound (63.13%);
  56,583 coverage rejections, 26,285 candidate-factor rejections, 3,655 excluded
  type-4. One light stayed outside the frontier for 238 samples / 11.8488 s.
- **Workload capture.** Three-second lead-in, five-second recording, 50 manager + 50
  queue slots at 10 Hz. It times the original native manager, renderer submission and
  candidate-list restoration separately; these are CPU wall intervals including waits,
  not GPU completion or frame time, and may nest. ETW presentation capture reports
  application successful-Present cadence, not displayed FPS or GPU duration.
- **External-result lifecycle.** Native SliceExecute keeps indices 0–16 in 17 qwords at
  record `+0x70..+0xF0`; indices 17+ would overwrite independent fields at
  `+0xF8/+0x100/+0x108/+0x110/+0x118`, so only higher indices are redirected to
  patch-owned storage. `.11` balanced 293,410 results (266,980 non-null + 26,430 null)
  with zero failures; `.75` balanced 214,151.
- **Whole-mod overhead.** Sampled wall intervals only, never additive; manager/renderer
  envelopes pause the native call and nested intervals must not be summed. `.72`/`.73`
  used 0/4096/4096 with 320 valid samples. World pass mean was ~29.8 µs (median 28.8,
  p95 41.9). ETW access error 5 prevented any FPS result in these runs.
- **Honest limits.** Balanced references do not prove GPU completion. Admission does
  not prove an acquired, visible or GPU-completed shadow. A clean run that never uses
  high indices cannot establish high-index safety.

## Gotchas

1. **Symptom.** More cached owners did not produce more high-resolution shadows
   (v1.2.8 with A8=8 produced only 9 of 24 physical faces).
   **Cause:** A8 bounds owners rotating through a shared low-resolution refresh lane;
   it is not a high-res map count.
   **Fix:** Treat A8 as the cached refresh budget, not a capacity lever.
2. **Symptom.** A nearer vehicle's parked-car shadow disappears during passing traffic.
   **Cause:** Distance-only residency; a nearer candidate evicts a visible incumbent.
   **Fix:** Use the owner-aware selection with incumbent weighting and outgoing
   retention, not raw distance.
3. **Symptom.** Suppression count rises but frame rate and face count do not improve.
   **Cause:** A suppression count is not admission, physical occupancy or savings;
   limits 0 and 10 can both average 26 faces (`.69`).
   **Fix:** Measure faces, queue owners and native intervals separately; never infer
   FPS from suppression counts.
4. **Symptom.** Type-3 renderer records look like they identify vehicle headlights.
   **Cause:** Vehicle headlights and world spotlights converge before the generic path.
   **Fix:** Classify through the CVehicle/CVehicleHeadLights chain; treat unknown
   identity as unknown, never as world or vehicle.
5. **Symptom.** Authored/added graphics never become visible although the entity
   readback looks correct.
   **Cause:** Entity readbacks are not graphics transforms or visibility; streaming
   category (Near vs World0) gates whether the object is ever streamed near the player.
   **Fix:** Set the loading category correctly and confirm entity `+0x60` bit2 and the
   render-object creation, not just the entity transform.
6. **Symptom.** Menu works once, then a later table access crashes inside the Lua VM.
   **Cause:** Five-bit frame-size truncation drops a register outside GC visibility.
   **Fix:** Keep frames ≤31 registers, publish each child before building the next,
   and split large table construction. Do not disable GC, force GC, or swallow access
   violations with `pcall`.
7. **Symptom.** A live menu toggle appears to do nothing.
   **Cause:** Archive-backed `.lib`/`.dat`/`.fat` changes are static for the running
   session; a menu Boolean cannot mutate already-loaded database objects.
   **Fix:** Only expose a live control when a proven reversible runtime backend exists;
   otherwise show archive features as status.
8. **Symptom.** FPS appears to crash during an experiment.
   **Cause:** Observer effect — an early renderer lookup experiment synchronously
   logged hundreds of thousands of null probes (report described >200 FPS to ~30).
   **Fix:** Bound and selectively arm observation; use atomic sparse gates for
   expected-frequent events.
9. **Symptom.** Rejecting a non-null SliceExecute result without releasing it drops a
   resource.
   **Cause:** SliceExecute acquires the primary before publication, so every rejected
   non-null completion owns one acquisition to release.
   **Fix:** Match every rejected result with a native-wrapper release carrying the
   exact resource context.

## Assets

- No game files, binaries, dumps or installable mods are distributed here. Mod source:
  https://github.com/temdah/Shadow-Engine — KB: https://github.com/temdah/Watch_Dogs_OKF
- The KB identifies undistributed evidence by stable IDs and hashes.

## Cost and time

- Multi-revision effort across dozens of experiments (`.12`–`.15` policy, `.57`–`.88`
  diagnostics). Most time goes to population/workload capture, offline harnesses and
  in-game validation windows, not to code.
- Many experiments produced negative results; see the failed approaches below.

### Failed approaches (recorded honestly)

- `.80`/`.81` keyed driver association failed pawn-owner equality in all four lookups
  (`pawnOwner/entityMismatch`, `driverValid=0`); replaced by the `.82` direct CPawn
  predicate.
- Distance-only residency counterexample: a nearer vehicle removed a visible parked
  car's shadow.
- `A8=8` full passthrough gave only 9 of 24 physical faces (v1.2.8).
- Distance-quality tiers (`.41`–`.49`) showed no FPS benefit and were removed in `.50`;
  a 512 tier was visibly coarser, 2048/4096 similar.
- `.31` strict-current ranking was invalid (local increment always 1); `.34` a
  global-gap latch disabled all later filtering.
- Late resource/pass construction crashed (v1.2.9, v1.2.13); v1.2.5 traversed transient
  post-admission pointers; v1.2.6 gating did not eliminate the crash.
- Several external-result placements were rejected: post-ExecuteFrameGraph hung (1002);
  record-release `0x003C1350` produced 20,130 stale/11 late; first wrapper batch 25,945
  stale/13 late; pre-finalizer `0x003E19E3` 17,496 stale/10 late.
- Cloth high-FPS experiments: broad owner 60 Hz stutter/ghosting, shared-context wall
  dt mixed simulations, a private solver context crashed (`0xC0000005` at
  `0x00C14A3D`), direct output replay crashed; only a narrow nested replay was accepted.
- Player-movement high-FPS experiments: hooking `0x0272EAC0` fixed at 30 Hz, sharing
  the delta, or hooking primary `0x027292F0` alone each crashed or broke collision;
  the movement module was removed in v2.0.22 and the circle-radius defect is unresolved.
- The external WD_DTCLAMP comparison (commit `b09e900e160f8a90f5f3837e507344030760ab8e`)
  targets RVA `0x026E2C50`, but the Global mapped image there is `48 8B 07 8B D3`, not
  the expected `F3 0F 58 51 20`; its trampoline layout also has errors. It was never
  built or executed.

## Open questions

- Which exact admission/residency transitions cause a late or missing shadow (producer
  ordering vs visible-refresh adequacy) — unresolved as of `.87`.
- Whether a stable runtime CVehicle field can bridge `bPolice`/`bEmergency` tags into
  the owner token; police priority stays disabled.
- Whether the world-quality region cache helps on fragmented mappings (it stayed at 60
  queries there) and whether it ever yields an FPS gain.
- GPU completion and visible-shadow verification: no method yet proves a shadow reached
  the screen.
- Lua frame repair remains Internal/Global-only with startup and lifecycle gates open.
- Movement/cloth fixes for high-FPS behaviour are unresolved.
