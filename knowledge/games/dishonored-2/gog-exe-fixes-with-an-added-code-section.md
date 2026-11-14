---
kind: game
title: 'Seventeen hard-coded fixes as one on-disk exe patcher with an added code section (GOG build)'
game: Dishonored 2
games_also: ["Dishonored: Death of the Outsider"]
game_version: 'GOG (DRM-free), Dishonored2.exe 42,591,232 bytes, PE timestamp 0x5c050611 (2018-12-03), x64'
platform: windows
engine: idtech
route: native-hook
tools: [python 3.15, pefile, capstone, keystone-engine, numpy, Cheat Engine, universal-modder um]
anti_cheat: 'none (single-player, GOG build has no DRM)'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-14'
links: []
tags: [void-engine, idtech5, exe-patch, pe-section, code-cave, keystone, powers, blink, far-reach, wwise, occlusion, havok, cvars, ai-awareness, player-state-machine, live-probe]
---
# Seventeen hard-coded fixes as one on-disk exe patcher with an added code section (GOG build)

A collection of engine-side fixes and tweaks for Dishonored 2. They range from gameplay (Blink re-aim after a
cancel, Snap Reaction at awareness instead of combat, Domino past 4 targets) to camera, UI-state, sound and
physics bugs. All of them ship as one stdlib-style Python patcher that edits the exe on disk, adds its own PE
section for new code, and undoes byte-identically. The user tested every feature listed under Verification
in the real game. The same fixes were later ported to Death of the Outsider; see
[the DOTO port note](../dishonored-death-of-the-outsider/porting-dishonored-2-exe-fixes-to-death-of-the-outsider.md).

## Setup
- GOG Dishonored 2, run directly from the exe (`Galaxy64.dll` present, no DRM), Windows 10 Pro 22H2.
- Python 3.15 with pefile, capstone (disassembly), keystone-engine (assembling the new code), numpy.
  No Ghidra or IDA on the machine: everything was found with small pefile/capstone scripts (RIP-relative xref
  finder, linear sweep + grep, RTTI class-name -> vtable, reflection-table reader).
- Live measuring: Python `ctypes` with `ReadProcessMemory` / `WriteProcessMemory` / `VirtualProtectEx`
  against the running game (no debugger). Cheat Engine was the user's tool for setting attributes.
- Other user mods in the game folder at the same time (unaffected): a dinput8 high-FPS fix, ReShade.

## Route and why
- **Why not a dinput8 proxy:** the user already runs other dinput8 proxy mods and there was no compiler.
- **On-disk patch with a pattern per spot:** each patch location is found by its own byte pattern that must
  match exactly once as (vanilla bytes | patched bytes) + a little following context. So `status` can tell
  vanilla / patched / unknown per spot, `apply` and `undo` work per feature, and any other build is refused.
  The patcher writes via a temp file and keeps a vanilla backup.
- **Code caves first, then an own section:** the first features hid their code in dead logging blocks
  (`if (missing) print warning` blocks whose only entry is the conditional jump; each starts with a short
  jump over itself). That became fragile, so the patcher now appends a PE section `.dh2mod`
  (RVA 0x42F0000, 0x1000 bytes). The header had room for exactly one more section header; the exe has no
  DYNAMIC_BASE (fixed base 0x140000000), no Authenticode signature and checksum 0, so nothing else needs
  fixing. `undo` removes the section when no feature uses it, so a full undo is byte-identical to vanilla.
  The section is RWX (0xE0000020) because some features keep a latch or slot byte there.
- **Upgrade rule:** patterns know only vanilla and the current patched bytes, so a feature whose code
  changed is undone with the previous patcher version first, then applied with the new one.

## How the game works (what we had to learn)
VAs are for this GOG build (image base 0x140000000, `.text` file offset = VA - 0x140000000 - 0xC00).

### General engine facts
- **Game singleton** at `[0x142710d68]`; player entity `[game+0x312ff8]`; character `[player+0x3f0]`
  (1 Corvo, 2 Emily). Player attributes `[player+0x408]` (index at `+0x110` = Snap Reaction's attribute,
  value at `[[attrs+0x48] + idx*40 + 0x24]`).
- **Reflection tables:** each record has a name pointer and an offset, but the offset printed after a type
  belongs to the **previous** field name. Verify each offset with a reader in code or the record size.
- **Enum tables:** the static initializers store each value together with the **previous** name's interned
  string. Read naively, every enum is off by one (`PLAYER_STATE_BRISKEYE` is 0x24, not 0x23;
  `ARK_PLAYER_STATISTIC_BUSTED` 15).
- **idList storage modes** (flag bits 6-7 of the cap/flags dword): 0x40 = fixed inline, append silently
  fails when full; 0xC0 = inline that spills to the heap. See
  [the Domino note](domino-phantasmal-link-past-4-targets.md).
- **Cvars:** each cvar registration does `lea rsi, "<default>"`; changing the default means pointing that
  `lea` at another existing string ("1" -> "0"). The config file only overrides what it lists.
- **Frame graph:** render resource ids are FNV-1a of the name **including the trailing NUL**.
- **Shaders can't be modded:** renderprog decl edits crash at boot; the game uses a precompiled shader cache
  and doesn't compile at runtime.

### Powers, cooldowns and the player controller
- Base `CanUse` 0x140737580: allowed when the time since the last use >= the value from vtable slot
  +0x168 (the cooldown getter).
- Far Reach (`arkCpntPowerGrapple`, vtable 0x141e86ee8): cooldown = `m_cooldown` (decl +0x150) +
  `m_extraCooldownWhenFalling` (+0x314, **hidden default 0.5 s**, set in the decl constructor) while a
  falling flag at `cpnt+0xdb` is set. Its `CanUse` override 0x140500110 also refuses while its cast/pull
  player-state objects are active, which is why a 0 cooldown never re-casts by itself. It's a straight pull,
  not a pendulum, so cooldown 0 gives chained zips, not swinging.
- Blink (`arkCpntPowerBlink`, vtable 0x141eb9e18): `CanUse` 0x14073c170 (slot +0x100) has no such check.
  It is called every frame by a UI caller and by the `PLAYER_STATE_USE_POWER` can-enter test (call returns
  to 0x1409cf356). Blink cpnt +0x158 = player controller (`arkCpntPlayerController`, vtable 0x141ee94e8),
  +0x168 = player state machine.
- Controller button masks: `+0x88` pressed this frame, `+0x90` released, `+0x98` held (`m_buttonMask`).
  Bit = `eActions_t` value: `ACTION_POWER_WEAPON` = 0x14 -> bit 20; the cancel key is bit 22.
- Player state machine (`arkCpntPlayerStateMachine`, vtable 0x141eea278): request a state with
  0x14096e710(sm+0x220, {1, state, 0}). Fields: `m_controller` +0x2f8, `m_body` +0x300, `m_physics` +0x308.

### Snap Reaction (bone charm / "brisk eye") and AI awareness
- Vanilla trigger: the controller's handler 0x140963c10 for player message `ARK_MSG_PLAYER_COMBAT_BEGIN`:
  if the attribute is > 0 and `[sm+0x90] != 0`, request state 0x24 (BRISKEYE). Cooldown and duration are in
  the state decl.
- Per-NPC `arkCpntAIAwarenessHUDDisplay` (vtable 0x141ea8718) think 0x14066e3d0 writes the NPC's attention
  score towards the player (float 0..1) to `+0x6c` at 0x14066e72b. Meter 1 = 0..0.6 (search), meter 2 =
  0.6..1 (busted -> combat). Checked pointers `{id, ptr}`: civilian decision cpnt +0x28/+0x30, player state
  machine +0x58/+0x60.

### Camera, DoF, pause
- Sprint FOV: per-frame update 0x14095da70; when sprinting the target is `base * additional/80 + base`
  (`additional` = decl `+0x108`, default 10). Base = the Options FOV global. Blink/stab FOV kicks are a
  separate FX FOV system and are unaffected.
- DoF: Options write only `r_skipDofBck`; the pause-menu state Enter copies `r_skipDOF` into it and forces
  DoF on, Exit copies it back. Loading from the pause menu skips Exit, so the next pause saves "DoF on" over
  the user's choice. The render read (0x140419f3c) and the pause Enter read (0x1405db7fb) both get pointed at
  `r_skipDofBck` instead.
- Focus loss: `win_pauseOnFocusLoss` (read at 0x14012a621) and `s_enableAudioSuspendIfWindowed` default "1".

### Tutorials list
- `arkCpntPlayerTutorials` (vtable 0x141e92808): MarkRead 0x1405a16e0 appends to the read list without
  checking it (its second search looks at the new list twice), so the list grows with every selection move
  in the pause menu, and is saved. The pause menu sizes the AS3 list by new+read count but fills each
  tutorial once -> blank `_Tutorial_` rows with white thumbnails.

### AI cues and Stop Time
- `arkMsgRequestCue` (msg 0x73) -> `HandleRequestCue` 0x140520c90 -> spawn 0x140521290. Blink sends
  MAGIC_VANISH (6) and MAGIC_APPEAR (5) cues; Bend Time sends them on start/end. The cue's expiry runs on the
  world timeline, which is frozen in stopped time, so a cue created during Stop Time is noticed on resume.
- Time manager at `[game]+0x1f52e8`: world scale request list `{ptr, count}` of 12-byte `{id, scale, flag}`
  entries, sorted so the last is the effective (smallest) scale; Stop Time requests 0.0.

### Blink / Far Reach markers
- Blink per-frame aim 0x14073a810: `[blink+0x1e8]` = raw crosshair hit (eye + viewdir * hit distance);
  `[+0x1f4]` = hit pushed out along the surface normal and eased (the push-out direction flips at corners and
  chair edges, which is the vanilla jitter). The ledge branch copies the snapped ledge point into the arrow.
  FX are moved by 0x1409fc6b0(entity, handle, &pos, &axis).
- Far Reach targeting 0x140501b00: `[grapple+0xe4]` is **not** a surface hit. It's eye + viewdir *
  distance-to-the-snapped-target, i.e. a point on a sphere around the eye. A real surface point/normal needs
  your own ray: the sensor's trace helper 0x140465150 (ray eye -> end, returns hit position, normal, entity).
  Vanilla facing rules: normal z > 0.7071 -> up, < -0.7071 -> down, else horizontal.

### Midnight scenes (street musicians) and Wwise
- Dialog tracks (`arkMidnightTrackInstDialog`, vtable 0x141ef21f8) implement scene pause/resume
  (slots 14/15: stop speech / replay at the scene offset). Sfx tracks (vtable 0x141eec488) leave slots 14/15
  as the empty base, so instruments keep playing while the scene holds (it holds whenever its speech isn't
  ready, e.g. while streaming or out of range). That's why vocals and music drift apart.
- Wwise in this build: `PostEvent` 0x141294cc0, `ExecuteActionOnEvent` 0x141294530 (action 0 stop,
  1 pause, 2 resume), `SetObjectObstructionAndOcclusion` 0x141295b70.

### Sound occlusion (room windows)
- `arkCpntSoundVolumeControl` (vtable 0x141ed6388) on windows/doors writes `applied * max` into a sound
  volume. Many writers (spawn, apply, the open/close animation, ...) set a dirty flag consumed per frame at
  0x140105403. Several windows on one volume: **last writer wins**.
- Occlusion sent to Wwise = emitter room + listener room window value, even when both are the same room.
  Two call sites: direct path 0x1400ff901, portal path 0x1400ffa33.

### Physics contact sounds
- Havok contact handler `arkPhysicsWorldLocal` 0x1409ca930 (event type 2); body table `[world+0x28]`
  stride 0xb0; linear velocity via the motion table (getter 0x140e50ea0). Bodies moving together
  (keyframed room modules + loose dynamic props) start thousands of contacts per room transform; measured
  relative speeds: 85 % under 0.1 m/s, real impacts mostly above 0.25 m/s.

### Other
- Spyglass (`arkPlayerFXSpyglass`, vtable 0x141eec288): Start picks the main FX and zoom list, overridden by
  the right-hand weapon's first upgrade; Update never re-checks, so switching weapons while zoomed keeps the
  old reticle.
- Dark Vision vs Bend Time: `arkPlayerFXBendtime` mode select 0x140989fc0 ends with "Dark Vision active ->
  mode 0", which stops Bend Time's grey FX.
- Journal Powers tab: collected in inventory order (varies per launch) by 0x14072f740.
- Results chart stealth axis reads stat 21 (`PLAYEREXPOSED`, counts neutral NPCs too) instead of stat 15
  (BUSTED = "Detections"), so a ghost run lands mid-chart.
- Collectible totals on the results screen are dynamic: each pickable adds itself to MAX_* stats at level
  start (skipped when restored from a save); no totals exist in data.

## Build steps
Per feature: find the site, write the stub with keystone at its section offset, add a pattern entry, test.

| feature | site (VA) | what the patch does |
|---|---|---|
| domino | 0x14059b0c4 + 3 list ctors | see the Domino note (5 bytes) |
| sprintfov | 0x14095daf3 | `jmp` past the sprint branch: target FOV = base FOV |
| dof | 0x140419f3c, 0x1405db7fb | both `cmp` reads use `r_skipDofBck` |
| tutorials | 0x1405a1786/9b, 0x1408ddd19 | MarkRead's 2nd search checks the read list; list size = real fill count |
| stoptime | 0x140520d18 | drop MAGIC/APPEAR/VANISH cues (types 4..6) while the world scale is 0 |
| aimfx | Blink FX calls 0x14073b363/37b/38f, Far Reach marker | markers follow the raw crosshair with a depth smoother; Far Reach facing from an own ray with 2 side probes |
| songsync | Sfx track vtable slots 14/15 | pause/resume the track's Wwise events with the scene |
| samevol | 0x1400ff901, 0x1400ffa33 | same room + one-step path -> occlusion = listener floor |
| winocc | consumer 0x140105403 | volume value = min over all its live window controls |
| contactquiet | 0x1409ca94b | contact starts with relative speed < 0.25 m/s exit early |
| nofocuspause | 4 cvar `lea`s | both cvar defaults "1" -> "0" |
| chartstealth | 0x1405e3713 | chart reads stat 15 instead of 21 (+0x58 -> +0x40) |
| spyglassfx | Update entry 0x14098c350 | restart the FX when the wanted main FX changed |
| dvgrey | 0x14098a0d4, DV think 0x140577758, DV start 0x1405770c6 | Bend Time keeps its grey; Dark Vision's own FX is held off while Bend Time is active |
| powerorder | call 0x1406201d7 | stable sort of the collected powers by the decl's `m_powers` order |
| snapearly | 0x14066e72b | when a non-civilian's score crosses 0.6 upward, run the vanilla Snap Reaction request |
| blinkrepress | Blink CanUse entry | see below |

blinkrepress logic (for Blink cooldown 0): hook the CanUse prologue (13 bytes). If the power button isn't
held, clear a latch byte and run vanilla. If it's held and the caller is the USE_POWER can-enter (return
address check): latched -> return false; else run the original and set the latch when it returns true. Other
callers run vanilla. Result: after a cancel, Blink needs a fresh press, like Far Reach.

Data edits that go with some features (the user's own import tool, decl text):
- songsync: `musician_*` soundevents `m_MaxDistance` 35 -> 150 (game2 + game3).
- Blink cooldown 0 (for blinkrepress): the Blink power decl's `m_cooldown`.

## Verification
- Static, for every feature: the pattern is unique, the stub disassembles as intended and has no
  RIP-relative operands, and on scratch copies apply/undo per feature is byte-identical, a fresh full apply
  equals an incremental upgrade, and a full undo equals the vanilla exe (sha256).
- Measured live before patching, wherever behaviour wasn't obvious: tiny counters/loggers written into the
  section (hook -> store values -> jump back) plus a Python watcher reading them with `ReadProcessMemory`.
  This settled songsync (the scene clock stops while real time runs), samevol (all sounds in the shaft took
  the portal path with occlusion 0.9), contactquiet (speed histogram) and blinkrepress (held mask bit 20 and
  the two CanUse callers).
- In game (user), all confirmed: domino 5/6 targets; sprint FOV; DoF after load from pause; no blank
  tutorials; Blink in Stop Time unnoticed (Blink level 2 aim-stop still noticed, as vanilla); Blink and
  Far Reach markers; musicians in sync; shaft room sounds in every window state; Jindosh room transform quiet
  (also fixed railing footstep chatter, landings still sound); no pause on focus loss; spyglass reticle on
  weapon switch; Bend Time grey with Dark Vision; powers order; Snap Reaction at 0.6; Blink re-press.
- Not verified: chartstealth in DH2 (verified only in DOTO), the Steam build (patterns may or may not match;
  the patcher refuses if any pattern isn't unique).

## Gotchas
1. **Game crashed the moment Blink aimed (live hook).** **Cause:** the stub called the original function
   after `sub rsp, 8`; the callee's home-space writes (`[rsp+8..0x20]` on entry) overwrote the stub's own
   return address. **Fix:** reserve 0x28 (32 bytes home space + alignment) around any `call` from a stub.
2. **Data byte in the new section crashed / didn't stick.** **Cause:** an RX section. **Fix:**
   characteristics 0xE0000020 (RWX), or keep data elsewhere.
3. **keystone encoded `mov rcx, qword ptr [0x14...]` as RIP-relative (rip + abs).** **Fix:** `movabs` into a
   register, then load through it; scan every stub's disassembly for `rip` operands.
4. **Patcher status/undo hit the wrong feature.** **Cause:** spots keyed by short names ("site", "cave2")
   collided across features. **Fix:** key by (feature, name).
5. **An exe-side icon fix made the Doppelganger vanish from the power wheel.** **Cause:** the value sent to
   the UI (`itemIndex`) is also the wheel slot order and the power/gadget test, not just the icon frame.
   **Fix:** remap only in the UI's AS3 (see [the UI note](iggy-ui-bytecode-patches-and-decl-findings.md)).
6. **winocc v1 changed nothing.** **Cause:** hooked 2 of about 10 writers; the window animation writes the
   volume directly. **Fix:** hook the single per-frame consumer of the dirty flag.
7. **Marker smoothing froze markers forever.** **Cause:** hidden markers sit at 1e30; squaring overflows to
   inf, inf/inf = NaN is stored in the FX instance, and `comiss`/`ja` lets NaN through. **Fix:** guard large
   values and write comparisons so NaN takes the "don't touch" branch.
8. **A call-chain logger crashed on the first physics sound.** **Cause:** the stack scan read past a worker
   thread's stack. **Fix:** bound it by the TEB stack base (`gs:[8]`).
9. **songsync v1/v2 (start-offset fixes) did nothing.** **Cause:** the vocal is never restarted; the scene
   *holds* while its speech isn't ready, and only the instruments run on. Found only after logging the scene
   clock against real time. **Fix:** pause/resume the Sfx track with the scene.
10. **Shaft sounds muffled after a save/load (curator map).** **Cause:** two window controls sit 2 cm inside
    the wrong sound zone, plus last-writer-wins. **Fix:** winocc + samevol in the exe, and moving the zone
    edge in 14 physhape `.cvd` files (data). Even then the engine uses one propagation route per sound, so a
    door can't un-muffle voices when all windows are closed (left as is).
11. **Code caves in dead print blocks:** check that nothing jumps into the middle of the block and that the
    code after it doesn't use the print's result or a register you clobber. Several candidates were real
    logic or had mid entries; an own section is less risk.
12. **A first Snap Reaction plan pointed at the wrong controller.** `player+0x798` looks like a controller but
    is the black-market interaction (its trigger requests state 0x23).
13. **Scripts:** run pefile/capstone scripts with `python -P`, not `-I` (that drops user site-packages);
    never name a script `dis.py`.

## Assets
None.

## Cost and time
About five working days across many sessions; every feature went through one or more user tests in game.

## Open questions
- Far Reach facing still flips on a plinth ledge and on a board's side edge (v2 with more probes was worse and
  was rolled back).
- Street musicians cut off together about 10-20 m away when not in view (also in vanilla; `mdnt_minDistanceForLod`
  isn't the cause).
- Bend Time's grey also greys Dark Vision highlights; DV draws them straight into the scene, so a mask swap
  can't separate them.
