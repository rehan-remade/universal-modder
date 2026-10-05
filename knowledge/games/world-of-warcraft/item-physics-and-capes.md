---
kind: game
title: 'Retail item physics and cape motion on the 3.3.5a client: a Box2D-style solver driven by retail PHYS data'
game: World of Warcraft
games_also: []
game_version: 'Wrath of the Lich King client 3.3.5a (build 12340); physics data from the retail 12.x client'
platform: windows
engine: native
route: native-hook
tools: [MinGW-w64 i686 gcc (in WSL), Python 3.12 (PHYS exporter), wowdev.wiki PHYS documentation]
anti_cheat: 'none touched: a private server the user runs; purely cosmetic motion of worn items'
status: working
agents:
- Claude Code (Opus 5.5)
humans: [RedSuper]
date: '2026-10-02'
links: ['https://wowdev.wiki/PHYS', 'https://box2d.org/']
tags: [physics, box2d, soft-constraints, capes, cloth, tassels, plumes, retail-port, solver]
---
# Retail item physics and cape motion on the 3.3.5a client: a Box2D-style solver driven by retail PHYS data

> Modern WoW item models carry a PHYS block (rigid bodies, shapes, joints) that makes tassels, plumes, chains and
> hanging maces swing. The 3.3.5a client has no such system. Inside the same client DLL that attaches per-item
> add-ons, a small solver steps retail's own physics data for every worn retail-ported item (275 models), and
> capes follow retail's cloak-dampening rows. It runs in the real client; most behaviour was matched to retail
> by reading the documented engine rules and replaying the data offline in tests.

## Setup
- Same DLL and toolchain as the per-item add-on note (proxy `version.dll`, MinGW i686, tests run on Windows).
- An exporter (Python) reads retail item M2s (`PHYS` chunk) and writes one compact data file: bodies, shapes,
  joints, masses from densities, placement scale, per item and per race/sex model.

## Route and why
Use this DLL only with a server you run: on other servers, Warden can scan the client for hooks like these.
Retail's engine ("Domino") is documented on wowdev.wiki as Box2D v2 in 3D: same slops, same soft-constraint
springs, same solver order. So the route was to reimplement Box2D v2.4's scheme in 3D and feed it retail's data
as stored, instead of tuning a home-made spring system per item (which was tried first and needed per-item hand
fixes).

## How the game works (what we had to learn)
**Retail physics semantics (from wowdev PHYS "client behaviour" + our replays)**
- Bodies: dynamic, kinematic or static; shapes: capsules, spheres, convex polytopes; joints: weld, spherical
  (cone + twist limits), revolute, all soft (frequency in Hz + damping ratio).
- One step per frame, `dt = min(frame, 1/30)`, 8 velocity and 2 position iterations (12 for one model type), no
  substeps. Gravity (0, 0, -10) yd/s², linear slop 0.005.
- Damping: `v *= max(0, 1 - h*d)` (not Box2D's divide).
- Kinematic bodies chase their target: they move a fraction `t` at once and the rest becomes velocity, with
  `t = max(follow, share(|v|), share(|ω|))` ramping with speed; dynamic bodies hanging off them are carried
  rigidly. For the common model types (62 of our 72 retail files) the kinematic body follows the **model**
  transform, not its bone.
- A dynamic body's transform replaces its bone's transform. A joint frame's z axis is the twist / hinge / cone axis
  (all 193 retail shoulder joints with a child run along z with symmetric twist).
- Cone angles are stored as-is and clamped to 10°–170° on load.
- Weld damping is stored as ratio × frequency (e.g. 3.243 at 2.162 Hz = ratio 1.5).
- A model's own bodies collide with each other except the two bodies of a joint.

**Capes**
- Retail drives capes with per-model rows (cloak dampening: angles and dampening per bone for walk/run/jump/fall,
  tabard angle/dampening, tail angles). The cape is a chain of five bones (fixed name CRCs).
- Both the HD and retail capes are only ~30% weighted to those bones, so the rows alone move the cape end 1–3 cm.
- Retail keeps the cloak under sheathed weapons (small angles, damped swing).

**Engine plumbing in 3.3.5a**
- The physics step runs inside the attachment pass, which runs on several threads: locks are required.
- An attached model's own world field is not its placement; its root bone matrix (`+0x98`) is. The character's
  world comes from the parent's model-view and world matrices.
- Weapon roots on the back jump 0.1–0.2 yd in single frames (their bones are a frame behind the body).

## Build steps
1. Export retail PHYS per item into the data file: real polytope inertia from the hull (an equal-volume sphere
   gives ~1/3 of it), frames normalised for per-race scale (0.8–1.4), mirrored shoulders made right-handed
   (`z = x × y`).
2. Solver: warm starting; no Baumgarte in the velocity pass; non-linear Gauss-Seidel position pass with v2's slops
   and caps; speculative limits and contacts; springs as Box2D's soft constraints with the full effective mass;
   a soft weld with a rigid point solved as a 6×6 block against the rotational mass about the anchor.
3. Contacts: friction on two tangents; dynamic-vs-kinematic and very unequal mass pairs soft.
4. Per frame: build the character's motion frame (turning carries parts round, running keeps its swing), hold
   weapon roots steady relative to their attachment bone, step, write body transforms back into the add-on's
   bone matrices.
5. Capes: apply retail's rows; a "tuck" keeps every cape bone in front of sheathed items (never past straight
   down), easing in and out; tabard back flaps get the tabard dampening and are tucked under the cape.

## Verification
- An offline test runs all 275 physics models standing and running and checks settling, limits and drift
  ("measure settling by pose change, not velocity": soft contacts leave phantom velocity with zero motion).
- Unit tests for each joint type, the 6×6 weld, contacts and the chase.
- In-game rounds with the human after each version; a frame-trace log (frame time, raw character move, part
  angles) settled the arguments about what was moving and when.
- Not verified: worn-item vs unit collisions (not implemented).

## Gotchas
1. **Parts fell ~40% faster than retail.** **Cause:** substeps at 1/120 s. **Fix:** retail's one step per frame,
   `dt = min(frame, 1/30)`.
2. **A plume stuck up rigidly.** **Cause:** we halved retail's cone angle, guessing it was a full apex angle.
   **Fix:** use cones as stored (clamped 10–170). Never reinterpret a retail value to get a look.
3. **A hanging mace lagged and crept.** **Cause:** weld damping read as a plain ratio (3.0) instead of ratio ×
   frequency. **Fix:** divide by the frequency in the exporter.
4. **Hanging parts bounced for seconds.** **Cause:** Box2D's centre-inertia row for a soft weld with a rigid point.
   **Fix:** solve the weld as a 6×6 block with the Schur-complement mass about the anchor.
5. **Shoulder pieces exploded at 30 fps.** **Cause:** polytopes approximated as spheres had a third of the real
   inertia. **Fix:** hull inertia from the polytope data.
6. **Other characters' capes stretched (one bend moved a cape end 42 yd).** **Cause:** a pass mixing cape bones and
   a parent from different moments, then a thread race on a static buffer. **Fix:** skip out-of-sync passes, refuse
   absurd bends, one lock per module.
7. **The cape stuck out and zig-zagged.** **Cause:** push-out and drape experiments on bounding boxes and the wrong
   matrix. **Fix:** retail rows + a tuck measured on the items' mesh vertices placed by their root bone.
8. **A weapon on the back kicked its chain while running.** **Cause:** the weapon root jumps a frame behind the body.
   **Fix:** hold the root's offset from its attachment bone steady.
9. **Tight cones never settled with warm starting removed.** **Cause:** removing warm starts made it worse; the real
   limit was one step of 8 iterations down a 5-body chain. **Fix:** retail stepping; extra substeps only for a
   deliberately custom-shaped piece (later removed at the human's request).

## Open questions
- Worn-item vs unit collisions; tabard and tail angles from the cloak rows are only partly used.
