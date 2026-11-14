---
kind: game
title: 'Porting Dishonored 2 exe fixes to Death of the Outsider, plus Displace and Blink marker smoothing (GOG)'
game: "Dishonored: Death of the Outsider"
games_also: ["Dishonored 2"]
game_version: 'GOG (DRM-free), Dishonored_DO.exe 43,757,056 bytes, PE timestamp 0x5c0584aa (2018-12-04), x64'
platform: windows
engine: idtech
route: native-hook
tools: [python 3.15, pefile, capstone, keystone-engine, Cheat Engine, universal-modder um]
anti_cheat: 'none (single-player, GOG build has no DRM)'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-14'
links: []
tags: [void-engine, idtech5, exe-patch, pe-section, port, displace, blink, fx-markers, results-chart, sliding, live-probe]
---
# Porting Dishonored 2 exe fixes to Death of the Outsider, plus Displace and Blink marker smoothing (GOG)

Death of the Outsider (DOTO) is the same Void engine as Dishonored 2, but a different build: every address
had to be found again. These fixes were ported from
[the Dishonored 2 exe-fixes note](../dishonored-2/gog-exe-fixes-with-an-added-code-section.md): sprint FOV,
DoF, no pause on focus loss, quiet physics contacts, street-musician sync, Snap Reaction at awareness and
Blink re-press. DOTO-only fixes were added for Displace and Blink markers, the results chart and the sprint
slide. They ship as one generated on-disk patcher with its own section `.dotomod`. The user tested
every listed feature in game.

## Setup
- GOG DOTO, Windows 10, run from the exe. Python 3.15 + pefile + capstone + keystone-engine.
- Kept in a separate workspace from the DH2 work: both games export loose files with identical flat names.
- Vanilla backup made before any patch; the patcher refuses other builds (patterns must match once).

## Route and why
- Same as DH2: on-disk exe patch (the user runs other dinput8 proxy mods), pattern per spot (vanilla |
  patched + context), new code in an appended PE section (`.dotomod`, RVA 0x445A000, raw 0x29BAE00; no ASLR,
  checksum 0, one free section-header slot). RWX (0xE0000020) for latch and slot bytes.
- The patcher is **generated**: a builder script assembles each stub with keystone at its section offset,
  checks it against the vanilla exe, and writes the patcher from a template. Re-running the builder after a
  change rebuilds every stub consistently.

## How the game works (what we had to learn)
### Porting method
- `port.py`: take the DH2 code bytes around a site, wildcard displacements and call targets, search DOTO.
  Most sites match once; when they don't, compare whole functions by instruction similarity
  (`fdiff.py`) and find the site by its neighbours.
- Struct offsets often move. Re-check every field against code that reads it in DOTO (or a vtable slot that
  uses it), never by assuming the DH2 offset.
- Cvars: find by name (registration `lea`s and readers); the same two-`lea` registration pattern as DH2.

### Address map (DOTO vs DH2)
| thing | DOTO | DH2 |
|---|---|---|
| game singleton / player | `[0x1427fb818]` / `+0x327668` | `[0x142710d68]` / `+0x312ff8` |
| player attributes | `[player+0x430]` | `[player+0x408]` |
| sprint FOV branch | 0x1409e0b33 (additional FOV decl +0x120) | 0x14095daf3 (+0x108) |
| `r_skipDofBck` int | 0x143cd0e98 | 0x143be4b58 |
| Havok contact handler / hook | 0x140a50f70 / 0x140a50f8b | 0x1409ca930 / 0x1409ca94b |
| Sfx midnight track vtable | 0x141f8c558 | 0x141eec488 |
| Wwise ExecuteActionOnEvent | 0x14133e880 | 0x141294530 |
| combat-begin Snap Reaction handler | 0x1409e7030 | 0x140963c10 |
| state request / sm offset | 0x1409f2610(sm+0x260) | 0x14096e710(sm+0x220) |
| player state machine vtable | 0x141f8a3f8 | 0x141eea278 |
| awareness HUD score write | 0x1406d7182 (10-byte hook) | 0x14066e72b (8 bytes) |
| Blink CanUse | 0x1407a75f0 (vtable 0x141f55b08 slot 32) | 0x14073c170 |
| Blink cpnt physics / controller / sm | +0xb0 / +0xb8 / +0xc8 | +0x150 / +0x158 / +0x168 |
| player controller vtable | 0x141f894d8 | 0x141ee94e8 |
| USE_POWER CanUse call returns to | 0x140a5597f | 0x1409cf356 |
| results chart PLAYEREXPOSED read | 0x140648562 | 0x1405e3713 |

Same in both: controller held mask `+0x98`, power button bit 20 (`ACTION_POWER_WEAPON` 0x14), awareness HUD
layout (civilian +0x28/+0x30, state machine +0x58/+0x60, score +0x6c), BRISKEYE 0x24.

### Displace (`arkCpntPowerSwapper`, vtable 0x141f0c048)
- Its marker setter is vtable slot 56, 0x14046c420. 0x14055f7b0 is the shared marker base of
  Clone/Swarm/Doppelganger/Mesmerize, so a hook there sees the wrong objects.
- Sensor result `[obj+0xc8]`: `+0x60` = decoy point from a body-clearance shape cast from the crosshair (stays
  about 0.3 m off walls), `+0x94` = landing point (on a ledge = ledge top). The shown marker = decoy x,y + a
  camera-based lift, clamped to >= ground + 1.5 m (decl `m_targetFxMinHeightStand/Sneak/Crouch`). On a ledge
  the ground is the ledge top, so the marker jumps 2-3 m.
- Marker FX update 0x14055f100 writes FX instance positions (`inst+0x38`) directly: handle `+0xd8` ground
  ring, `+0xdc` marker, beam between. In mantle state those handles are -1, and the shown marker is a
  separate mantle FX (handle `obj+0x23c`, positioned each frame at 0x14046ddbf).
- FX handle -> instance: FX manager hash buckets at `mgr+0xfef60` (mask `+0xfef70`), node {handle, u16 idx,
  next +8}, instance = `[mgr] + idx*0x140`.
- Camera block for eye/view vector: `[[obj+0x110]+0x368] + 0x252ac / +0x252b8` (Blink: `[rdi+0xc0]`).

### Blink in DOTO
- Restructured vs DH2: marker update 0x1407a6230, FX moves at 0x1407a66ec (fog), 0x1407a6704 (bottom),
  0x1407a6718 (mantle arrow). The DH2 raw-hit field has no direct counterpart, so the DH2 marker patch
  isn't a byte port.

### Other DOTO facts
- Sliding decl gained `m_minSprintDuration` and `m_sprintSlideCooldown` (durationTime_t
  `{ m_seconds = x; }`, both default 0.75 s, set in the constructor). Billie only slides after 0.75 s of
  sprint; set the first to 0 in her sliding decl.
- Mission stats record per chapter is 0xc0 bytes (DH2 0xbc: DOTO adds stat 46, rat whispers).

## Build steps
1. Port each DH2 feature: locate the site (pattern or function diff), re-check offsets, rebuild the stub with
   the DOTO addresses, add it to the builder.
2. DOTO-only features:
   - **swapfx** (Displace): hook the common exit of 0x14055f100 (only when the object is the Swapper).
     Project the crosshair point onto the view ray: `P = eye + V*t`, `t = dot(aim - eye, V) / dot(V, V)`.
     Ease the depth (when |dt| <= 1 m keep 25 % per frame) and write P as the marker. The ground ring goes
     to (P.x, P.y, ground z) and the beam from P to the ring. A second hook writes P into the mantle FX
     position too.
   - **blinkfx** (Blink): wrap the three FX-move calls with the same projection and easing. The bottom marker
     takes the fog x,y and its own z; hidden markers (1e30) pass through.
   - **chartstealth**: stat 21 -> 15 in the chart's read (`+0x58` -> `+0x40`).
3. Build the patcher, test on scratch copies, apply.

## Verification
- Static: per-feature apply/undo round trips on scratch copies; full apply + undo == vanilla (sha256); no
  RIP-relative operands in any stub.
- Live diagnostics (removed afterwards): a hook storing the Swapper object pointer into the section plus a
  Python watcher logging decoy/ground/landing points and the real FX instance positions at about 50 Hz.
  This showed which positions the visible pieces actually use.
- In game (user): sprintfov, dof, nofocuspause, contactquiet, songsync (+ musician decls), Displace markers
  incl. mantle ("just like Blink now"), Blink markers, chartstealth (ghost run and a no-kill run with
  knockouts both land at the right tip), Billie's slide, snapearly at 0.6, blinkrepress.
- Not verified: the chart's assault side.

## Gotchas
1. **Displace diagnostic hook logged nothing useful.** **Cause:** hooked the shared marker base (used by
   other powers), not the Swapper's own slot 56. **Fix:** check `[obj] ==` the Swapper vtable, or hook the
   class's own slot.
2. **First Displace ledge fix: log showed the value changed, the screen didn't.** **Cause:** the visible
   marker comes from FX instance positions written elsewhere, and from a separate mantle FX in mantle state.
   **Fix:** resolve FX handles to instances and log the real positions before deciding what to patch.
3. **keystone `mov rcx, qword ptr [0x14...]` assembled RIP-relative.** **Fix:** `movabs` + load; scan
   stubs for `rip`.
4. **Upgrading a stub with the new patcher failed to match.** **Cause:** patterns know only vanilla and the
   current bytes. **Fix:** undo with the old build, apply with the new one.
5. **Mantle arrow can't face the wall:** the sprite orientation modes (`VELOCITY_PLANAR`, `VECTOR_*`) in the
   particle decl get turned toward the camera by the renderer, and the arrow bends with marker motion.
   Gave up (data and exe).
6. **Raising `mdnt_minDistanceForLod` did nothing** for musicians cutting out at 10-20 m (DH2 does it too).
7. **Promo patch from DH2 had no effect:** DOTO moved `PromotionScreen_main` into its own
   `ui/lib_promotion.iggy` (see [the UI note](../dishonored-2/iggy-ui-bytecode-patches-and-decl-findings.md)).
8. **Adding a new map component** (a cloned pickable for placed pistols under a new number) loads fine. DH2
   work never needed that.

## Assets
None.

## Cost and time
About four days of sessions, interleaved with the DH2 work.

## Open questions
- Displace and Blink mantle arrows facing the wall (renderer-side orientation).
- Musician cut-off at mid range (cause not found).
