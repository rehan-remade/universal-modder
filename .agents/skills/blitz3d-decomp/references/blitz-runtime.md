# Blitz3D runtime behaviour for ports

What decompiled Blitz3D code means, where a straight transcription goes wrong. Verified on CB2's P90 port
(ADS dot on the screen centre to 4 px, bone positions exact, fire rate to the tick).

## Clock

- CB-family games count time in **70ths of a second**. CB 1.3: a variable `FPSfactor` per frame. CB2/UERM: a
  fixed step. `EntryPoint` adds `elapsed_ms * 70 / 1000` to an accumulator; `UpdateGame` runs one step per
  `1.147541` taken off it (61 steps per second) with `fps\Factor[0] = 1.147541`.
- Timers drop by the factor each step: `t = Max(t - Factor, 0)`. A shot delay of 5 waits for 0 at the
  start of a step, so it fires every `ceil(5 / 1.147541) = 5` steps = 82 ms, not 71 ms.
- `UpdateWorld(1.0, ...)` once per step advances animations by `speed` frames per step.
- Port it as a fixed-step loop with render interpolation between the last two steps: `acc += dt * 70;
  while acc >= 1.147541 do step() end`.

## CurveValue

`CurveValue(target, old, smooth) = old + (target - old) * (1 / smooth * Factor)`, clamped so it never passes
the target. In CB2 it is a runtime builtin with a fourth argument (0).

## Trig and angles

- `Sin`, `Cos`, `ATan2` take and return **degrees**. `Sin(t * 0.0001)` with t in microseconds is a 3.6 s
  period, not 63 ms.
- Euler angles: pitch + looks **down**, yaw + turns **left**, roll + counter-clockwise as seen. `RotateEntity
  p, y, r` is yaw x pitch x roll. In Roblox camera space (x right, y up, -z forward):
  `CFrame.fromEulerAnglesYXZ(math.rad(-p), math.rad(y), math.rad(r))`.
- Quaternions stored in `.b3d` files are applied as their **conjugate** (w, -x, -y, -z). Test: a child node
  placed through its parent's rotation must land on the geometry it marks (the P90's `weaponfire` node
  lands on the muzzle only with the conjugate).
- Coordinates are left-handed (x right, y up, z forward). To Roblox: (x, y, -z), and reverse each
  triangle's vertex order.

## Entities

- `MoveEntity e, x, y, z` moves along the entity's own axes, ignoring its scale. `TranslateEntity` moves along
  world axes. `PositionEntity e, x, y, z, 0` is in the parent's space, so a child's position is multiplied by
  the parent's scale.
- `ScaleEntity` on a pivot scales its children: a viewmodel pivot scaled 0.005 means child offsets are in
  model units and the pivot's own moves are in world units.
- `EntityPick(cam, range)`: anything within range straight ahead. `LinePick` + `PickedX/NX` for bullets.
- `RenderEntity(cam, entity, tween)` (CB2 runtime): draws one entity with a camera, used for viewmodels with
  a depth hack instead of a second camera.

## Animate

`Animate entity, mode, speed, sequence, transition`, with sequences cut by `ExtractAnimSeq(first, last)`:

- mode 1 loops, 2 ping-pongs, 3 plays once and stops on the last frame (`Animating` turns false).
- speed is frames per `UpdateWorld` unit; a negative speed plays from the last frame back to the first.
- transition > 0 blends from the pose captured at the call to the sequence's start pose over `transition`
  update units; the sequence time doesn't advance until the blend finishes.
- `AnimSeq(entity)` is the sequence playing now, which can lag a game's own "queued" sequence variable.

## Rnd

Park-Miller (48271 mod 2^31 - 1, Schrage) keeping the low 16 bits; `Rnd(a, b) = rnd() * (b - a) + a` in
float32, `Rand(a, b) = Int(rnd() * (b - a + 1)) + a`, `SeedRnd s` (0 becomes 1), `RndSeed()` is the state.
Games reseed it for deterministic sequences: CB2 replays a fixed recoil pattern per burst
(`SeedRnd recoilseed`) and draws each bullet's spread from `SeedRnd shotIndex + 128`, so a server can
recompute both. A Luau implementation: the SCP-Roblox project's `ReplicatedStorage/CBMap/Blitz.luau`.

## Ints and floats

Float to int rounds to nearest, ties to even (x87 `fistp`), not truncation. Blitz floats are 32-bit: route
values through float32 where results feed comparisons or indices.
