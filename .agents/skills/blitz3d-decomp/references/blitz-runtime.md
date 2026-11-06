# Blitz3D runtime behaviour for ports

What decompiled Blitz3D code means, where a straight transcription goes wrong. Checked in one weapon port
(ADS dot on the screen centre to 4 px, bone positions exact, fire rate to the tick); the points that name a
source file match Blitz3D's source (blitz-research/blitz3d) or the open CB code.

## Clock

- CB-family games count time in **70ths of a second**. SCP: CB 1.3: a variable `FPSfactor` per frame
  (elapsed seconds x 70, clamped to 0.2-5, `Main.bb`). Ultimate Edition Reborn: a fixed step
  (`Main_Core.bb`). The main loop adds `elapsed_ms * 70 / 1000` to `fps\Accumulator` and sets
  `fps\Factor[0]` to `TICK_DURATION` (70/60); `UpdateGame` runs steps while the accumulator is above 0, taking
  `TICK_DURATION` off each time. SCP: Containment Breach 2 (CB2), built on Reborn, steps by `1.147541` (70/61,
  61 steps per second).
- Timers drop by the factor each step: `t = Max(t - Factor, 0)`. A shot delay of 5 waits for 0 at the
  start of a step, so at CB2's step it fires every `ceil(5 / 1.147541) = 5` steps = 82 ms, not 71 ms.
- `UpdateWorld(1.0, ...)` once per step advances animations by `speed` frames per step.
- Port it as a fixed-step loop with render interpolation between the last two steps: `acc += dt * 70;
  while acc > 0 do acc -= STEP; step() end` (the game calls `CaptureWorld` before the last step of a frame).

## CurveValue

`CurveValue(target, old, smooth) = old + (target - old) * (1 / smooth * Factor)`, clamped so it never passes
the target (SCP: CB's `Main.bb`, Reborn's `Math_Core.bb`). In CB2 it is a runtime builtin with a fourth
argument (0).

## Trig and angles

- `Sin`, `Cos`, `ATan2` take and return **degrees** (`bbruntime/bbmath.cpp`). `Sin(t * 0.0001)` with t in
  microseconds is a 3.6 s period, not 63 ms.
- Euler angles: pitch + looks **down**, yaw + turns **left**, roll + counter-clockwise as seen. `RotateEntity
  p, y, r` is yaw x pitch x roll (`rotationMatrix` in `blitz3d/geom.h`). In Roblox camera space (x right,
  y up, -z forward): `CFrame.fromEulerAnglesYXZ(math.rad(-p), math.rad(y), math.rad(r))`.
- Quaternions stored in `.b3d` files are applied as their **conjugate** (w, -x, -y, -z): `geom.h` builds the
  matrix with the usual rotation matrix's rows as its columns. Test: a child node placed through its parent's
  rotation must land on the geometry it marks (a gun's `weaponfire` node lands on the muzzle only with the
  conjugate).
- Coordinates are left-handed (x right, y up, z forward). To Roblox: (x, y, -z), and reverse each
  triangle's vertex order.

## Entities

- `MoveEntity e, x, y, z` moves along the entity's own axes, ignoring its scale. `TranslateEntity` moves along
  the parent's axes whatever the entity's rotation (world axes with `global` = 1, or for an entity with no
  parent). `PositionEntity e, x, y, z, 0` is in the parent's space, so a child's position is multiplied by
  the parent's scale.
- `ScaleEntity` on a pivot scales its children: a viewmodel pivot scaled 0.005 means child offsets are in
  model units and the pivot's own moves are in world units.
- `EntityPick(cam, range)`: anything within range straight ahead. `LinePick` + `PickedX/NX` for bullets.
- `RenderEntity` (not in stock Blitz3D: BlitzX3D has `RenderEntity entity, camera, tween`, CB2's runtime takes
  the camera first) draws one entity with a camera, used for viewmodels with a depth hack instead of a second
  camera.

## Animate

`Animate entity, mode, speed, sequence, transition`, with sequences cut by `ExtractAnimSeq(first, last)`
(`blitz3d/animator.cpp`):

- mode 1 loops, 2 ping-pongs, 3 plays once and stops on the last frame (`Animating` turns false).
- speed is frames per `UpdateWorld` unit; a negative speed plays from the last frame back to the first.
- transition > 0 blends from the pose captured at the call to the sequence's start pose over `transition`
  update units (lerp positions, slerp rotations); the sequence time doesn't advance until the blend finishes.
- `AnimSeq(entity)` is the sequence playing now, which can lag a game's own "queued" sequence variable.

## Rnd

Park-Miller (48271 mod 2^31 - 1, Schrage) keeping the low 16 bits: `rnd() = (state & 65535) / 65536 +
0.5 / 65536`. `Rnd(a, b) = rnd() * (b - a) + a` in float32; `Rand(a, b)` swaps a and b if b < a, then returns
`a + Floor(rnd() * (b - a + 1))` (a C++ cast inside the runtime: it truncates, unlike the conversion below);
`SeedRnd s` keeps the low 31 bits (0 becomes 1), the seed at startup is 0x1234, and `RndSeed()` is the state
(`bbruntime/bbmath.cpp`). Games reseed it for deterministic sequences: a pattern that replays the same way,
or values a server can recompute.

## Ints and floats

Float to int rounds to nearest, ties to even (x87 `fistp`, the compiler's cast in
`compiler/codegen_x86/codegen_x86.cpp`), not truncation. Blitz floats are 32-bit: route values through
float32 where results feed comparisons or indices.
