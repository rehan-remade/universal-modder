---
kind: game
title: 'Portal gun prototype via dinput8 proxy DLL: player, camera and angle offsets'
game: 'DARK SOULS: REMASTERED'
games_also: []
game_version: 'Steam build 10943698; DarkSoulsRemastered.exe 50,286,344 bytes, SizeOfImage 0x319B000'
platform: windows
engine: fromsoft
route: native-hook
tools:
- Zig 0.17.0 (zig cc, x86_64-windows-gnu)
- Ghidra 12.1.4
- Python 3 ctypes (ReadProcessMemory) and capstone
- DSR-Gadget source (reference only)
- Paramdex DS1R defs and names (soulsmods/Paramdex, reference)
anti_cheat: 'no client anti-cheat found by um scan; servers are live, so offline only (proxy removed before going
  online)'
status: in-progress
agents:
- Claude Code (Sonnet 5.5)
humans: []
date: '2026-10-08'
links:
- https://github.com/JKAnderson/DSR-Gadget
- https://soulsmodding.com/
tags:
- proxy-dll
- dinput8
- memory-map
- teleport
- overlay
- rtti
- havok
- projectiles
- bullet-param
- inline-hook
- raycast-by-projectile
---
# Portal gun prototype via dinput8 proxy DLL: player, camera and angle offsets

A hotkey-driven portal prototype for Dark Souls Remastered: two portals (blue and orange) are drawn over the
game, and walking into one moves the player to the other with the facing rotated. It runs in the real game
(offline) and works on open floor, as confirmed by the user and by the log. Teleports are sometimes accepted by the game only
after a delay (see "Why the teleport lags"). The session then moved on to the game's own projectile ("bullet")
system, because a projectile is the natural in-world object and trigger for a portal: from our own code we can now
spawn a real Prism Stone projectile, and a fast ownerless projectile fired along the camera ray works as a ray cast: its stopping
point places an upright portal flat on a wall. This note is mostly a verified memory map for this build plus the traps we hit.

## Setup
- Game: Steam app 570940, build id 10943698, `DarkSoulsRemastered.exe` 50,286,344 bytes (SHA-256
  `a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b`), PE `SizeOfImage` 0x319B000. This size is
  not in DSR-Gadget's version table; DSR-Gadget treats unknown sizes as newer than 1.03 and applies all its boosts.
- Windows 10, no MSVC. Built with portable Zig: `zig cc -target x86_64-windows-gnu -shared -O2 -o dinput8.dll
  proxy.c dinput8.def -lgdi32 -luser32`.
- The game folder already had a ReShade `dxgi.dll`; `dinput8.dll` was free, so the proxy uses that name.
- Offline only. DSR's PC servers are live again (since November 2022), and teleports or in-memory param edits in an
  online session would reach other players and can get the account soft-banned. The proxy loads on every launch, so
  keep Steam in Offline Mode (or block `DarkSoulsRemastered.exe` in the firewall) while `dinput8.dll` is in the game
  folder, and remove it before playing online.
- The image base is fixed at 0x140000000 (no ASLR relocation was observed).

## Route and why
A dinput8 proxy DLL (forwards `DirectInput8Create`, starts a thread) plus direct memory access. Params alone
cannot express portals; ModEngine2 never supported DSR (its README lists it as unsupported, and it's discontinued
in favour of me3, which doesn't list DSR either); and DSR-Gadget is a separate external process (and GPL-3.0). Item
and projectile work (params via Soulstruct, Smithbox or DSMapStudio with Paramdex) is the planned item side; the
projectile system itself has been located and a spawn from our own code verified (see below).

## How the game works (what we had to learn)
The executable on disk is protected: there is an extra large, high-entropy `.text` section after `.idata` and the
entry point is in a stub, so static Ghidra analysis of the file gives mostly garbage. The running process holds
decrypted code. Dumping the main module's image from inside the process (a hotkey in the proxy that walks the
image pages with `VirtualQuery` and writes them to a flat file) gives a clean image that disassembles normally
and still contains RTTI. We did not strip or bypass the protection; we only read the game's own memory while it
runs, for analysis.

Addresses below are offsets from the module base (0x140000000), verified live in the Undead Asylum. Pointers
change every launch, the chains do not.

- **RTTI / vtables** (image VAs): WorldChrManImp 0x141328210, PlayerIns 0x1413251f0, ChrFollowCam 0x1412f1db8,
  PadMan 0x1412de4d0, CameraMan 0x1412edf98. Finding a singleton: scan the `.data` section (rva 0x1a25000 to
  0x1d0b000) for any pointer whose target's first qword equals the class vtable.
- **WorldChrManImp** global pointer at exe+0x1c77e50. `PlayerIns = [WorldChrMan + 0x68]` (DSR-Gadget calls this
  ChrData1; same offset). PadMan global at exe+0x1c6aea0.
- **Position, authoritative:** `PlayerIns + 0x7b8 -> +0x2e0 -> +0x120` is float x, y, z and a w of about 1.0. Y is
  up. A second chain reaches the same address: `PlayerIns + 0x18 -> +0x28 -> +0x2c0 -> +0x120`.
- **Position, copy:** `PlayerIns + 0x2c0` holds the same triple but is rewritten every frame, so writes there
  vanish in milliseconds. Many other objects also hold copies; only the physics-owned one is honoured.
- **Facing angle:** `ChrPosData = *(*(PlayerIns + 0x18) + 0x28)`; angle (radians) at `ChrPosData + 0x4`, and x, y, z
  at +0x10, +0x14, +0x18 (matches DSR-Gadget's PosAngle and PosX/Y/Z). Forward is (-sin a, cos a) in (x, z), so
  a = 0 faces +z and `a = atan2(-fx, fz)`. Verified over 83 samples covering a full circle. Writing it persists,
  but the character model only turned partway in place, so it behaves like a logical heading.
- **Camera:** global `CameraMan` pointer at exe+0x1c6e188. The world matrix is four float4 rows at +0x30 right,
  +0x40 up, +0x50 forward, +0x60 position (w = 1). At +0x70: vertical FOV in radians (0.75), aspect (2.389 for a
  3440x1440 window), near plane 0.05, far plane 3100. At +0x120 the viewport size. It is called CameraMan, so
  it is likely the active camera, but it was not tested with the bow aim camera.
- **Overlay rendering without a graphics hook:** a topmost, click-through, layered window (`WS_EX_LAYERED |
  WS_EX_TRANSPARENT | WS_EX_NOACTIVATE`, magenta colour key) positioned over the game's client area, drawing with
  GDI. World to screen: d = P - camPos, z = d.fwd, x = d.right, y = d.up, then
  screenX = W/2 + x / (z * tan(fovY/2) * W/H) * W/2, screenY = H/2 - y / (z * tan(fovY/2)) * H/2. The rings stayed
  glued to world positions, so the maths and the FOV field are right. Needs windowed or borderless.
- **Teleport:** detect the player's body point (feet + 0.9) crossing a portal plane from the front inside an
  ellipse; write the physics position to the linked portal with local x mirrored; rotate the angle by
  `yaw(nB) - yaw(-nA)`, where `yaw(x, z) = atan2(-x, z)`; keep re-writing the destination for about 0.3 s.

## Why the teleport lags: the Havok character capsule
Tracing the position every tick during the destination hold (reading BEFORE each write, with QPC time) showed the game
keeps the old position for roughly 10 to 40 ticks (about 0.2 to 0.7 s) before accepting the write; in one older run it
never accepted it for the whole 75-tick hold. So the position field we write is not the one the game trusts.
- The character's physics is a Havok `hkpCharacterProxy` (RTTI present, vtable 0x141469648). Found by a read-only
  pointer-graph scan from PlayerIns (depth 3, vtable match): `PlayerIns + 0x7b8 -> +0x58` (also reachable via
  `+0x18 -> +0x188 -> +0x38` and `+0x38 -> +0x3c8 -> +0x508`).
- Two float triples inside it equal the player position exactly: `(*(proxy + 0x80)) + 0x120` and
  `(*(proxy + 0x180)) + 0x320` (the second lags by about 0.001). Writing both together with the player position during
  the hold made every teleport land near the target (offsets 0.00 to 2.4), none pinned at the start, but the delay before
  acceptance remained. The real teleport entry point has not been found (DSR-Gadget's bonfire-warp signature, which does
  match this build, only reloads you at your last bonfire; it is not a position teleport).
- `ChrCtrl` (vtable 0x14132aab0) is `PlayerIns + 0x18`: `ChrCtrl + 0x28` is ChrPosData, `+0x18` is the motion/proxy
  driver (accumulated move vector at +0x140/+0x170), and the per-frame update is vtable slot 30 (exe+0x37c250).
- A walking player moves roughly 0.1 units per tick, and `Sleep(4)` on Windows sleeps about 15.6 ms, so "ticks" are not
  4 ms. Use real time (`GetTickCount64`, QPC) for cooldowns. A tick-based cooldown of 150 became about 2.3 s and made the
  trigger feel much smaller than the drawn ring, because crossings during it were silently ignored.

## The game's projectile ("bullet") system
Found by RTTI plus Ghidra headless on the runtime dump. All addresses are relative to base 0x140000000.
- **BulletMan** singleton: global at exe+0x1c7a488 (constructor 0x140429440). Pools: 0x80 x 0x360-byte entries at `+0x00`
  (an emitter-like object), 0x40 x 800-byte `BulletIns` at `+0x20`, and 4 x 0x318 bytes at `+0x40`. In-use `BulletIns`
  objects hang on a list: head `[BulletMan + 0x28]`, next `[obj + 0x308]`; `obj + 0` is the bullet handle. Handles look
  like 0xff02ff00. Unresolved: the aimed-shot section below polls a different list (head `[BulletMan + 0x08]`, next at
  +0x348, 0x360-byte objects), and this note does not say which one the current code uses (see Open questions).
- **BulletIns** (vtable 0x141342a70, 0x320 bytes): position vec4 at +0x10, orientation at +0x20, velocity at +0x30,
  state at +0x88 (1 wait, 2 fly, 3 explosion, 4 none; classes BulletWaitState, BulletFlyState, BulletExplosionState),
  timer at +0x1f4, BulletParam id at +0x94, owner at +0x9c. The update function is exe+0x1404246a0. Movement is
  kinematic (position += velocity * dt), not a Havok body. Each tick the bullet pushes its transform to a hit-volume
  manager (global exe+0x1c7a050, a pool of 0x80 entries of 0x230 bytes keyed by the handle at BulletIns+0x54). Those
  hit volumes are capsules between two points, mostly bone-attached to an owning character; a bullet with
  `atkId_Bullet = 0` (all three Prism Stone rows) does no hit test at all.
- **Spawn API:** `exe+0x429ba0 = BulletMan::Spawn(BulletMan*, BulletCreateInfo*)` returns the bullet handle or -1. It
  builds a 328-byte spawn info (0x14042a1c0), takes a BulletIns from the free list (0x14042a920), initialises it
  (0x140420ef0) and positions it (0x1404241d0). The game calls it from a bullet emitter (0x14031d380) and for child
  bullets on explosion (0x140427380), which passes owner = -1, so ownerless bullets are a normal case.
- **BulletCreateInfo** (recorded from a real Prism Stone throw by hooking Spawn; byte offsets): +0x00 owner ChrIns
  handle (the player was 0x10044000 in every capture; 0xffffffff = none), +0x0c BulletParam id (direct), +0x10 goods id
  (370 for the Prism Stone), +0x1c dummy-poly/placement id (-1 = owner default), +0x30 byte flag 1, +0x40..+0x6f spawn
  transform, +0x70..+0x9f owner transform (+0xa0..+0xcf a copy), +0xd0 -1, +0xd8 a float, +0xdc 1. Transforms are
  row-major 3x4: rows `[cos 0 -sin | tx]`, `[0 1 0 | ty]`, `[sin 0 cos | tz]` for a yaw rotation, so local +z maps to the
  same forward vector as the facing angle. Spell casts use the same 0x100-byte shape with their own bullet ids (3040 and
  6000 seen) and the player as owner.
- **Spawning from our own code works.** A hook on the player's `ChrCtrl::Update` (exe+0x37c250, 16 stolen bytes) runs
  queued spawn requests on the game's own thread. A key press that queued a replay of the captured create-info with
  bullet 130 and a new transform 3 units ahead produced a real Prism Stone that fell to the floor (seen by the user), with
  no crash. With owner = 0xffffffff the call also returned a valid handle, but nothing visible appeared where expected;
  where an ownerless bullet's position comes from is not yet known. Unresolved: the aimed shot below fires ownerless
  bullets and reads their impact (verified), and the collision-probe section says ownerless bullets simulate and collide
  normally with no visual effect, so this "unknown position" may be out of date (see Open questions).
- **Why this matters for portals:** a spawned projectile is a real object the game simulates and removes; its impact
  gives a world position (used by the aimed shot below), and a bullet that carries an attack param with a marker SpEffect
  could act as a collision trigger. The trigger is not done yet. Unresolved: this section and Gotcha 7 take the impact
  when the state turns 3, while the aimed-shot section and Gotcha 14 take it when the state turns 4 (see Open questions).

## Param access at runtime and the Prism Stone rows
- Param manager global at exe+0x1c7e000: `file(type) = [man + 0x18 + (type * 9) * 8]`, row table `t = [file + 0x38]`, id
  table at `t + (([t - 0x10] + 0xf) & ~0xf)` holding sorted `{u32 id, s32 rowIndex}` pairs, `n = *(u16*)(t + 10)`,
  row = `t + *(u32*)(t + 0x34 + rowIndex * 0xc)`. BulletParam is type 0xb. This lets the DLL read (and edit, since it is
  heap memory) any row at runtime. The row layout matches Paramdex `DS1R/Defs/BulletParam.xml` (size 0xa0): +0x00 atkId,
  +0x04 sfxId_Bullet, +0x08 sfxId_Hit, +0x10 life, +0x14 dist, +0x1c/+0x20 gravity, +0x28 initial velocity, +0x44 hit
  radius, +0x60 SpEffect for the shooter, +0x68 HitBulletID, +0x6c..+0x7c SpEffect 0 to 4, +0x92 isPenetrate, +0x9a bits
  0 to 2 FollowType (0 or above 2 = fly state, 1 to 2 = wait state), +0x9b bit 1 isHitBothTeam.
- Prism Stone: goods id 370; bullets 130 (flying stone, life about 2 s, speed 2, gravity 9.8, atk 0), 131 (hit marker,
  life 0.04) and 132 (lingering light, life 1.0 s). All have no attack, no SpEffect and FollowType 0.

## Reading and hooking at runtime (what worked)
- A 14-byte absolute-jump inline hook (`FF 25 00 00 00 00 <addr>`) with a trampoline of the stolen instructions is enough.
  Refuse to patch unless the prologue bytes match what the dump shows (protects other builds). Both hooks (Spawn at
  exe+0x429ba0 with 20 stolen bytes, ChrCtrl::Update at exe+0x37c250 with 16) installed from the mod thread without
  crashes. Do not call game functions from your own thread; queue the request and run it from a game-thread hook.
- Ghidra headless against the dump project: `analyzeHeadless <projdir> <proj> -process -noanalysis -scriptPath <dir>
  -postScript DecompAt.java <hex addrs>`, with a small GhidraScript that decompiles the function at each address. A
  "callers of" script and a "functions referencing this address" script (for a singleton's global) were the fastest way from
  a singleton to the code that uses it. Pass the project directory and the project name separately.
- Community data helps: Paramdex (soulsmods/Paramdex, `DS1R/Defs` and `Names`) gives param layouts and row names and
  matched the offsets we decompiled. `gh api -H "Accept: application/vnd.github.raw"
  repos/soulsmods/Paramdex/contents/DS1R/...` fetches them.


## Aimed shot: using a spawned projectile as the ray cast
Instead of writing a collision query, fire a bullet along the camera ray and read where it stops. Verified in the real game
(offline), repeatable (same aim gave identical numbers), no crashes.
- Spawn an ownerless Prism Stone bullet (id 130) with the replayed create-info, using the camera position + 1 m and the camera
  forward as direction. (The projectile section, Verification and Gotcha 10 still call an ownerless bullet's position
  unknown; unresolved, see Open questions.) The bullet's BulletParam row is edited in memory only for the shot and
  restored afterwards: life 1.5 s, gravity in and out of range 0, distance 500, initial/max/min velocity 40,
  accelerations 0. Rows are heap memory, so a crash or restart reverts them.
- Spawn-transform convention (found because the first replays flew backwards): a bullet's velocity is `M * (0, 0, -1)` where
  M is the row-major 3x4 at create-info +0x40. To fire along direction d use columns `[right, up, -d | t]` with
  `right = normalize(cross(worldUp, -d))` and `up = cross(-d, right)`.
- Detect the hit: poll the in-use `BulletIns` list (`[BulletMan + 0x08]`, next at +0x348, 0x360-byte objects; param id +0x94 and
  owner +0x9c identify yours). State 2 is flying, state 4 means finished. The position at +0x10 when it turns 4 is the impact.
  Do this once per frame inside the player's `ChrCtrl::Update` hook, because 30 ms polling from another thread can miss the
  single frame the bullet sits in state 4. Unresolved: the projectile section above (and Gotcha 9) puts live `BulletIns`
  (0x320 bytes) on a list at `[BulletMan + 0x28]` with next at +0x308, and calls the 0x360-byte pool "emitter-like"; it
  also takes the impact at state 3, not 4. This note does not say which list and state the working code uses (see Open
  questions).
- Accuracy: at 40 m/s a frame moves about 0.67 m, so the impact can overshoot the surface by up to that (measured 0.60 m and
  0.10 m). Two stages fix it: after the fast scouting hit, fire a slow shot (6 m/s, about 0.1 m per frame) from 1.2 m before
  the scouting impact along the same ray and use its impact. The user judged portals placed this way as nearly flush with
  the wall (slightly raised, like messages or bloodstains).
- The surface normal is not stored in the bullet. For upright portals use the horizontal part of the reversed flight direction
  and skip steep (floor/ceiling) hits. This is exact only for shots that hit the wall squarely.

## Wall portals need a touch trigger
A portal drawn on a wall cannot be entered by the plane-crossing test, because the wall stops the player before the plane is
crossed (the log simply had no "crossed" lines). The trigger for wall portals is: body point within 0.6 m in front of the plane,
inside the ring ellipse, and moving toward the wall; reappear 0.9 m in front of a wall destination (must exceed the trigger
distance, or you bounce straight back). This trigger is built but was not yet confirmed in the game at the time of writing.

## Live param tables (this build)
Table index (the `type` in the param-manager lookup) with row counts read from the running game; the type-name string is at
`table + 0xC`, the row count is a u16 at `table + 0xA`, and row entries are `{u32 id, u32 dataOffset, u32 nameOffset}` starting
at `table + 0x30`: 0 EQUIP_PARAM_WEAPON 1245, 1 PROTECTOR 324, 2 ACCESSORY 41, 3 GOODS 272, 4 REINFORCE_WEAPON 469,
5 REINFORCE_PROTECTOR 17, 6 NPC 556, 7 ATK_PARAM (NPC) 2164, 8 ATK_PARAM (PC) 1397, 9 NPC_THINK 476, 10 OBJECT 947,
11 BULLET 632, 12 and 13 BEHAVIOR (NPC and PC), 14 MAGIC 141, 15 SP_EFFECT 850, 16 SP_EFFECT_VFX 232, 19 ITEMLOT 1536,
0x21 HIT_MTRL, 0x22 KNOCKBACK. Row layouts match Paramdex `DS1R/Defs`. AtkParam (0x80 bytes): hit radii at +0x00 to +0x0c,
knockback +0x10, SpEffect ids 0 to 4 at +0x18 to +0x28, damage (phys, magic, fire, thunder, stamina) as u16 at +0x50 to +0x58,
dmgLevel +0x72, mapHitType +0x73. There are many zero-damage, zero-knockback, no-effect attacks, for example NPC table ids
3108, 3109, 3113, 3119, 3120, 3128, 3129, 3134, 3136, 3137, 3144 and 3146 (hit radius 1.6), and PC table ids 222 and 322.

## Collision-trigger probe: what is known
Goal: a world-fixed hit volume that reacts to the player, using the game's own hit manager (global exe+0x1c7a050) instead of
coordinates. Results so far, from logs:
- A bullet created with FollowType 1 (wait state) follows a transform belonging to its OWNER (a dummy poly). Owned by the
  player it hovers 0.3 to 1.0 m from the player's body and moves with them; ownerless it snaps to the world origin within about
  a second and stays there. So a fixed trigger must use FollowType 0 (fly state) with zero velocity.
- Ownerless wait-state bullet with an NPC-table attack (3146) ended in 16 to 30 ms, with its position jumping 20 m down;
  with a PC-table attack (222) it stayed alive (at the origin). Which AtkParam table an ownerless bullet reads is still open.
- Ownerless bullets are simulated and collide with the world exactly like owned ones, but show no visual effect (the owned stone
  shows its effect). An overlay marker is a workable stand-in for testing. (This conflicts with the "position unknown" reading
  in the projectile section, Verification and Gotcha 10; unresolved, see Open questions.)
- Untested at the time of writing: the fly-state zero-speed probe walking into the player.


## Build steps
1. Back up your saves, put Steam in Offline Mode (or block `DarkSoulsRemastered.exe` in the firewall) and keep it
   offline for as long as the proxy is in the game folder, and find the module base (fixed 0x140000000).
2. Build the proxy (forward `DirectInput8Create` from the system `dinput8.dll`, start a thread in `DllMain`),
   and copy it into the game folder. Close the game before replacing it (a loaded DLL cannot be overwritten).
3. In the thread, read the chains above with `VirtualQuery` guards and do the camera projection and teleport.
4. For analysis, add a hotkey that dumps the module image, then import it into Ghidra as a raw binary at base
   0x140000000 (x86:LE:64:default, windows cspec).
5. Undo: delete `dinput8.dll` from the game folder. Do this before playing online again: the proxy loads on every
   launch, online ones included.

## Verification
- Position chain: read on two launches; the 2-unit "pop up" write was confirmed visually by the user, and a
  +/-4 unit horizontal write was confirmed visually.
- Camera: found by diffing memory reachable from the game's globals before and after a 90 degree camera turn,
  then confirmed the orthonormal basis and the position about 3 units behind the player. The overlay rings
  staying fixed while turning and walking is the oracle for the matrix and FOV.
- Teleport: the log (`teleport ... hold done: offset 0.00`) and the user confirming they were moved and rotated,
  on open floor.
- Projectile spawn: hooked BulletMan::Spawn while the user threw a Prism Stone and cast spells (create-info bytes logged),
  then replayed it from our own hook on the player's ChrCtrl::Update; the user saw the stone appear and fall, the log shows
  a valid handle each time. The ownerless variant returned a valid handle but its position is unverified (this conflicts
  with the verified aimed shot below, which fires ownerless bullets; unresolved, see Open questions).
- Aimed shot: F3 and Ctrl+F6 at the same aim gave identical impacts; the two-stage refine measured the fast shot overshooting the
  surface by 0.60 m and 0.10 m in two shots; the user confirmed the rings sit nearly flush on the wall (log: SHOT HIT / SHOT refine).
- Havok capsule: the two triples equal the player position exactly during normal play; per-tick traces with and without
  writing them show teleports landing near the target in 5 of 5 runs (earlier version: one run pinned at the start).
- NOT verified: the bow aim camera, fall velocity and momentum, behaviour after loading a different map, the
  camera after a teleport, and anything online (never tested; play offline).

## Gotchas
1. **Symptom.** Writing the player's position works only briefly or not at all. **Cause:** the first triple found
   (PlayerIns+0x2c0) is a per-frame copy. **Fix:** write the physics-owned position at `PlayerIns+0x7b8 -> +0x2e0
   -> +0x120`. Test any candidate by writing y+2 and watching whether the player's copy follows and the character
   then falls back.
2. **Symptom.** A teleport written while the character is walking gets undone, while the same write standing still
   sticks. **Cause:** the game's own per-frame move writes back over a single mid-frame write. **Fix:** hold the
   destination and angle for about 0.3 s (re-write every tick) after the crossing.
3. **Symptom.** The game exits about one second after writing DSR-Gadget's Warp fields (ChrMapData + 0x108, 0x110
   to 0x124) and setting the warp flag. **Cause:** not known. This build's size is not in DSR-Gadget's version
   table, but DSR-Gadget does not skip unknown builds: it treats them as newer than 1.03 and applies all its boosts
   (including `ChrData1Boost1 = 0x20`), so on this build it reads ChrMapData from `[PlayerIns + 0x68]` (0x48 + 0x20)
   and writes the warp fields at that object + 0x108 to 0x124. This note does not record which base the crashing
   test wrote to. Worth checking: if it was `[PlayerIns + 0x48]` or ChrCtrl (`[PlayerIns + 0x18]`), retry with
   `[PlayerIns + 0x68]`; that is not confirmed as the cause. **Fix:** until that is checked, use direct position and
   angle writes, which are safe.
4. **Symptom.** Hotkeys do nothing in a proxy DLL. **Cause:** F12 is Steam's screenshot key and is swallowed, and
   an exact-HWND foreground check plus the `GetAsyncKeyState & 1` edge flag were unreliable. **Fix:** avoid F12 if Steam's
   screenshot hotkey is bound (on the author's PC F12 reached the game and worked in a later session, so check your Steam
   settings), treat the game as focused when the foreground window belongs to the game's process, and track key edges with
   the high bit.
5. **Symptom.** Static analysis of the exe shows "Failed to disassemble" and decompiler "Unable to resolve
   constructor" everywhere. **Cause:** the code is protected on disk. **Fix:** analyse a runtime dump (see above).
6. **Symptom.** Teleporting fails or snaps back in some spots but works on open floor (hold-end position is back near
   the start). **Cause:** the written position is not the authoritative one: the game keeps a Havok character-proxy capsule and takes
   our write only after a delay, sometimes none. It is not a wall sweep (per-tick traces showed the position staying
   near the start, not stopping at a wall). **Fix (partial):** also write the two capsule triples (see "Why the teleport
   lags"); all teleports then landed, with a delay. The game's real teleport function is still unknown.
7. **Symptom.** A blind "N units ahead" portal placement lands in walls. **Cause:** no collision query.
   **Fix:** use the game's own projectile impact position (done: see "Aimed shot"); the surface normal is not stored
   there (approximate it from the flight direction). Unresolved: this gotcha reads the impact at BulletIns state 3
   (position at +0x10), while the aimed-shot section and Gotcha 14 read it at state 4 (see Open questions).
8. **Symptom.** A test write landed in unrelated memory. **Cause:** a scan result went stale after the player object
   was reallocated. **Fix:** re-resolve the chain from the global each time and only write to addresses that
   currently match the expected values.
9. **Symptom.** A watcher for a spawned bullet logged "not in pool" forever. **Cause:** it scanned the 0x80 x 0x360 pool at
   BulletMan+0; spawned bullets are 0x320-byte objects on the in-use list at BulletMan+0x28. **Fix:** walk that list.
   Unresolved: the aimed-shot section polls `[BulletMan + 0x08]` (next at +0x348, 0x360-byte objects) instead (see Open
   questions).
10. **Symptom.** A bullet spawned with no owner appeared nowhere visible. **Cause:** unknown (the position probably comes from
    the owner's dummy poly, with a default when there is none). **Fix:** not found yet. Unresolved: the aimed shot fires
    ownerless bullets and reads their impact, and the collision-probe section says they simulate normally with no visual
    effect, so this may be out of date (see Open questions).
11. **Symptom.** Replayed spawn fires the projectile backwards. **Cause:** velocity is the spawn matrix times (0, 0, -1), not +z.
    **Fix:** build the 3x4 with the third column equal to the negated direction.
12. **Symptom.** A shot-placed wall portal can never be entered. **Cause:** a wall stops the player before the plane is crossed.
    **Fix:** a touch trigger within about 0.6 m in front of the plane (see "Wall portals need a touch trigger").
13. **Symptom.** A wait-state (FollowType 1 or 2) bullet teleports to (0, 0, 0) or hugs the player. **Cause:** it follows its
    owner's dummy-poly transform. **Fix:** use FollowType 0 with zero velocity for a fixed volume.
14. **Symptom.** The impact reading is 0.6 m inside the wall. **Cause:** a 40 m/s bullet moves 0.67 m per frame and state 4 is
    seen after the step. **Fix:** refine with a slow shot (6 m/s) fired from just before the first impact. Unresolved:
    the projectile section and Gotcha 7 say the impact state is 3, not 4 (see Open questions).

## Assets
None generated. The portals are GDI-drawn rings.

## Cost and time
One long session (about a day of wall-clock with many launch cycles, each needing a DLL copy and relaunch).

## Open questions
- The game's own position-teleport function (or the correct warp-field offsets for this build), to remove the acceptance delay.
  Worth checking first: DSR-Gadget's warp fields with ChrMapData at `[PlayerIns + 0x68]` (see Gotcha 3).
- The bullet section contradicts itself in three places, and this note cannot say which reading the current code uses:
  - the in-use `BulletIns` list: head `[BulletMan + 0x28]`, next at +0x308, 0x320-byte objects, with the 0x360-byte pool at
    +0x00 "emitter-like" (projectile section, Gotcha 9), or head `[BulletMan + 0x08]`, next at +0x348, 0x360-byte objects
    (aimed shot);
  - the state that marks the impact: 3 (projectile section, Gotcha 7) or 4 (aimed shot, Gotcha 14);
  - whether an ownerless bullet's position is known: unknown or unverified (projectile section, Verification, Gotcha 10),
    or simulated normally with no visual and used by the verified aimed shot (aimed shot, collision-probe section).
- Does a fly-state, zero-speed, zero-damage bullet with an attack param react to the player (state 3 or 4 near the player)? If yes it
  is a true collision trigger; if not, the hit manager's overlap and team test (exe+0x1c7a050, candidates 0x1403b8400, 0x1403b7290,
  0x1403e6450) has to be read or hooked, or a Havok phantom with a contact listener used instead.
- Which AtkParam table (NPC or PC) an ownerless bullet reads, and how to give an ownerless bullet a visible effect (or whether a
  non-player owner such as a nearby NPC is the answer).
- The bullet impact surface normal (only the position is directly readable from BulletIns).
- Velocity and fall speed offsets, to keep momentum through a portal.
- Whether CameraMan is also the bow aim camera.
- The item itself: giving it at runtime (DSR-Gadget lists an ItemGet signature that also matches this build) and defining
  pyromancy and sorcery shots through params.
