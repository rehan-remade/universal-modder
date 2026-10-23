# SCP: Containment Breach 2: what is already known

Decompiled 23 Oct 2026 for a Roblox port. Everything here was read from the decompile, not guessed.

## The game

- Steam app 3257000, Early Access, by Euclid Labs, the UE team, Undertow Games and Third Subdivision Studios,
  built on SCP: CB Ultimate Edition Reborn. Store page: CC BY-SA 3.0.
- **Not open source.** Public: the dedicated server and its AngelScript API (github.com/Ne4to-podobnoe/cbmrserver;
  `scripts/include/uerm.as` has the weapon ids). The client `uerm.exe` is x86 Blitz3D with hashed names;
  `uemp.dll` is proprietary and its licence forbids decompiling it. No anti-cheat (`um scan`).
- Assets are loose files: `GFX/Items/Weapons/<Name>/` (viewmodel `.b3d` + PBR textures),
  `GFX/Items/<name>_wm.b3d` (world models), `SFX/Weapons/<Name>/` (`shoot0..n.ogg`, `reload.ogg`,
  `deploy.ogg`), `GFX/Items/Weapons/MuzzleFlash/`, `GFX/Items/Weapons/Hands_textures/`.

## Decompile (convention `~/cb2-decomp/`)

`uerm_disasm/` (raw), `names.json` (b3dnames.py recover with ancestor sources + `cb2-runtime-sigs.txt`,
stubs `_fTX68FZ68264=UnknownCB2A _fTXZ2F2FDF6X=UnknownCB2B`), `uerm_named_disasm/`, `uerm_named_decomp/`
(1298 functions; `UpdateGUI` and `TXFB22FF044` fail), `weapons.json` (cb2_weapon_table.py on
`Code/_fTXZD02FB0ZX.txt`). Function files keep the hash without `_f` (`Functions/T808422X82.bb`).

## Function map

| Hash | What it is |
|---|---|
| `EntryPoint` / `updategame` | 70ths accumulator; one game step per 1.147541 (61 Hz) |
| `TXZD02FB0ZX` | Creates every weapon template (stats, anim table) |
| `TXDDB62DBZ(id, path, ...)` | New weapon: loads the viewmodel |
| `TX4XFD0X0BB(id, attach)` | Its third-person attach model id |
| `X628F22202(id)` | The weapon's stats template (type `X0442B862F`) |
| `TBB4Z82Z6F` | Weapon system init: pivot `ScaleEntity scale`, `ExtractAnimSeq` per slot, flash meshes, `CameraBone` lookup, counts `shoot*.ogg` |
| `TXFD66FZ84B` | Addon JSON loader: **names every template field** (below) |
| `T808422X82` | First-person weapon update, every step: anim slots, fire, recoil, ADS, sway, bob, lag, reload, wall |
| `TBZXD06BBZ(slot, mode, transOffset, delay, speedMul)` | Queues an animation slot |
| `TX0Z8FFZ8Z0(weapon, item, ...)` | Equip (deploy sound, draw) / unequip (holster slot) |
| `T446DBF2FZ` | First-person muzzle flash and its light |
| `TZXXF4882Z(shooter, damage, pitch, yaw, stats)` | Bullet: LinePick from the camera, player damage, headshots |
| `TB4DZ8FBX2` | Bullet impact: decals, particles, hit sounds |
| `TXFDFX4XDB2` / `XZD248D24X` | Reload started (network) / ammo moved from spare to magazine |
| `XFFDZ8Z2ZX` | Third-person weapon of other players (world flash `Mflash.b3d`) |
| `updatemouselook` | Camera: zoom formula, CameraBone and kick terms |
| `CFZD40FDB` / `TD2D2BFZF` / `YXDZX2480` | CameraBone pitch / yaw / roll added to the camera |
| `FZ486D2BB` / `TZD06B2ZF8` | Viewmodel render (`RenderEntity`, depth hack) |

Globals: `DZ64X028` first-person weapon state (`Field18` weapon, `Field46` queued slot, `Field22` ADS 0-255,
`Field15`/`Field30` vertical kick / its camera share, `Field49`/`Field70` sideways kick, `Field32` shot timer,
`Field58` flash timer, `Field61` held item: `Field15` magazine, `Field3` spare). `XZ0260X8X2` player
(`Field13` zoom term, `Field1` camera shake, `Field25` crouched, `Field76` speed). `TDD0Z6BXB6` input
(`Field8` right mouse, `Field1` fire, `Field11`/`Field4` smoothed mouse speed). `YX08Z0F62D` timing
(`Field3[0]` factor, `Field7` accumulator). `BX840BX0X` camera. `TXXD604X6XF` player pitch.

## Weapon template fields (type `X0442B862F`, offset = 4 x field number)

`Field21/31/53` offsetx/y/z, `Field37/35/19` offset pitch/yaw/roll, `Field47` scale (viewmodel pivot),
`Field13` muzzleflashscale, `Field24` muzzleflashyaw, `Field50` recoil, `Field18` spread (degrees),
`Field32` shootrate (70ths), `Field57` recoilseed, `Field58` damage, `Field52` maxammo (magazine),
`Field6` maxclipammo (spare), `Field22` reloadtime (70ths), `Field51` shootrange (units, default 30),
`Field25` shootsound (folder or file), `Field12` reloadsound, `Field1` deploysound, `Field8` shootstartsound,
`Field54` misssound, `Field59[]` hitsounds, `Field41/43` sightoffsetx/y, `Field2` sightmultiplier,
`Field26` isviewmodel, `Field17` pump, `Field60` pellets, `Field42` combat, `Field39` shootafteranim,
`Field20[slot]` anim frame range (packed first/last), `Field34[slot]` anim speed, plus shell fields
(`Field10` shellbone ... `Field62` shellaction).

Anim slots: 1 idle, 2 draw, 3 shoot, 4 lowered at a wall (EntityPick 0.2 every 8/70 s), 5 reload, 6 sprint
(after a 60-80 delay), 7 holster (draw played backwards), 8 walk. Weapon ids (server API `uerm.as`): M4A1 1,
Glock 2, M60 3, SR556 4, MP5 5, FiveSeven 6, Vector 7, P90 10, MP7 11, M134 12, Remington 18, RPG 19, G36 20,
AK74 21; every gun's numbers are in `weapons.json`.

## Rules of the weapon code

- Fire: hold to fire; a shot when the shot timer reaches 0; damage `Rnd(damage +- 0.1)`, x2 above 0.9 of the
  victim's collider, a player dies at 8 injuries; spread `Rnd(+-spread)` on pitch and yaw, x0.2 aiming
  (ADS > 128) or crouched, seeded `shotIndex + 128`.
- Recoil per shot: vertical kick `Max(Rnd(recoil*2.2*1.1, recoil*2.3*1.1), kick)` and sideways
  `Rnd(-recoil*0.44, recoil*0.495)` from the recoil seed (reset at each burst); the player's pitch climbs
  `kick * 0.05` every step, the camera adds `-CurveValue(kick)`; viewmodel kick `Rnd(+-recoil*4)` clamped 2.
- ADS: right mouse; viewmodel moved by sightoffset (CurveValue 6), ADS amount to 255 (5);
  zoom = (1 + ADS * sightmultiplier / 400) / tan(hfov / 2), the FOV option being 60 degrees vertical.
- Camera: pitch, yaw, roll += the viewmodel's `CameraBone` local angles (reload shake), - kick.
- Impacts: walls `bullet_hole_decal(2).png` 0.028-0.034 units for 2100/70 s, smoke `smoke(0).png`, sound
  `SFX/Character/BulletHitCement.ogg`; bodies `BulletHit2/3.ogg`.
- Flash: first person `MuzzleFlash_FP.b3d` (quad, ScaleMesh 0.85) at `weaponfire`, size muzzleflashscale x
  Rnd(0.6, 1.2), random roll, 2/70 s, light range 4 colour (306, 216, 0); world `Mflash.b3d` on the world
  model's `fire` node (scale 1.6752), alpha 0.8, 3/70 s.

## P90 (weapon 10)

offset (0, 0, -0.01), scale 0.005, muzzleflashscale 0.02, muzzleflashyaw 6, recoil 2.1, spread 3.2,
shootrate 5 (732 rpm at the 61 Hz step), recoilseed 543, damage 1.725, magazine 50, spare 200,
reloadtime 210, sightoffset (-0.017, -0.0017), sightmultiplier 1.3 (1.83x). Anim slots (frames, speed):
idle 45-50 x0.6, draw 1-44 x0.7 (1.03 s), shoot 181-200 x0.5, wall 201, reload 56-180 x0.7 (2.90 s),
sprint 201, holster 1-44 x-0.9 (0.80 s).

## Roblox port (the SCP-Roblox project, journal `MODLOG.md`)

Where it was written, the project sits next to this repo: `../SCP-Roblox`. MODLOG sections
"P90 from SCP: Containment Breach 2" and "slimmer player body" record ids, checks and gotchas.
`game/ReplicatedStorage/Weapons/CB2/`: `Stats.luau` (template values under CB2's field names, slot timing),
`FirstPerson.luau` (T808422X82 + T446DBF2FZ, step for step), `Viewmodel.luau` (rig driver), `P90Anim.luau`
(generated keyframes). Server ammo, spread, damage and impacts: `ServerScriptService/Weapons.server.luau`.
A next weapon needs its stats table, its viewmodel converted (`scripts/roblox/`), its sounds and a
WeaponConfig entry pointing at the stats (`CB2 = "<Name>"`).
