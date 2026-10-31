---
kind: game
title: 'Reading the whole vehicle fleet: archive names, RTPC values, mesh payloads and Havok collision'
game: 'Just Cause 3'
games_also: []
game_version: 'Steam build 20206564 (2025-12-17), JustCause3.exe timestamp 0x5787641c; every mesh declares RBMDL 1.16.0, every physics file Havok 2014.1.0-r1'
platform: windows
engine: native
route: asset-only
tools: ['Gibbed.JustCause3.SmallUnpack', 'Gibbed.JustCause3.ConvertProperty', 'Gibbed.JustCause3.ConvertAdf', 'custom Python readers: archive index (Jenkins lookup3), ADF v4, RBMDL blocks, Havok 2014 packfiles']
anti_cheat: 'none (single-player, offline, read-only)'
status: working
agents: ['Freebuff (DeepSeek V4.1 1017; ran the grab passes and wrote the first version)', 'Claude Code (Opus 5.5)']
humans: ['@NotTrevino']
date: '2026-10-30'
links:
- https://github.com/aaronkirkham/jc-model-renderer
- https://github.com/aaronkirkham/ava-format-lib
- https://github.com/tim42/gibbed-justcause3-tools-fork
tags: ['archives', 'rtpc', 'adf', 'rbm', 'havok', 'vehicles', 'reverse-engineering', 'jenkins-hash', 'fleet-data', 'read-only']
---

# Reading the whole vehicle fleet: archive names, RTPC values, mesh payloads and Havok collision

> A Just Cause 3 vehicle is not a folder of meshes: it is one `.ee` bundle inside an archive whose
> filenames exist only as hashes. This note is the read-only grab that opened all of it — **81,952 of
> 81,953 archive entries named, 6,045 vehicle modules decoded to 3.1 million named values, all
> 77,611 render blocks decoded, and 35,499 Havok compound instances wired to 25,769 part
> indices**. A second pass then read every vehicle *system* the port needed from the same files:
> weapons, turrets, doors, audio, damage, water, interaction, spawning and registration ("Vehicle
> systems, read from the same files"). It was built to answer "what is a good donor for a 7 m Batmobile, and what does its
> handling actually do", so every table is fleet-wide and every script has a `check` that re-reads the
> game and fails on drift. Nothing here writes a file or launches the game.

## Setup

- Windows, single-player, offline. The game is owned on Steam; the install matches Steam build
  20206564 (2025-12-17), and `JustCause3.exe` still carries its 2016 timestamp `0x5787641c`. The
  vehicle content is the base game plus the DLC under `dlc_win64/`: Sky Fortress, Mech Land Assault
  and Bavarium Sea Heist, plus the pre-order and bonus packs (`v0300_preorder`, `v0604_preorder`,
  `v1401_preorder`, `v0805_sportmech`, `w142_preorder`, `w163_preorder`, `w901_scorpiongun`,
  `skin_flame`). The DLC archives are only read for the fleet tables: a donor or part taken from a
  DLC vehicle is only for players who own that DLC.
- No loader, no anti-cheat, no online services. The work is **read-only**: archives and bundles are
  unpacked in memory or to a scratch folder, and nothing is written back.
- [Gibbed's Just Cause 3 tools](https://github.com/tim42/gibbed-justcause3-tools-fork) for the
  property container and ADF conversions (`SmallUnpack`, `ConvertProperty`, `ConvertAdf`). The parts
  module defeats the stock converter, so the grab grew its own ADF v4 reader (gotcha 5).
- Four Python readers written for this: an archive index (Jenkins lookup3 over two name sources), an
  ADF v4 object-graph decoder, an RBMDL block decoder and a Havok 2014 packfile reader. They live in
  the project's own tools folder; this note describes them rather than linking to them.
- Output policy from day one: **derived tables in the repository, raw payloads outside it.** The
  decoded positions alone are 440 MB, and the game's bytes never enter the tree. If the repository is
  public, keep the full value dumps (the module and effect value rows) out of it too: they are the
  game's data in another encoding. Publish the readers, counts, digests and summaries, and let `check`
  regenerate the rest from the player's own install.

## Route and why

Three routes were available, and the choice is the whole note:

1. **Probe in game, one value at a time.** Slow, and it cannot tell you a fleet range: an ordering
   question such as "which vehicle is least wrong for this body" needs all 233 bundles measured the
   same way.
2. **Convert each file with the stock tools and read the XML.** This is how the editable vehicle was
   handled before. It is per-file, it fails outright on the parts module, and 135,283 inner files
   across the fleet is not a loop you want to rerun after every patch.
3. **One read-only grab per payload family.** Chosen. Each family gets a reader, a table and a
   `check`. It answers fleet-wide questions offline, it is re-runnable when the game updates, and it
   cannot break a build because it never writes.

The index is not a convenience: **modules do not exist as separate archive entries**. You cannot ask
the filesystem for `land_global.vmodc`; you have to name the bundle first, unpack it, and enumerate
what is inside. That is why the index came first and everything else joins against it.

## How the game works (what we had to learn)

### The archives: 88 pairs, 81,953 entries, and how a path becomes a row

Every payload sits in a `.arc`, indexed by a matching `.tab`. The install has **88 pairs**: 56 base,
7 patch and 25 under `dlc_win64/*/`. Together they hold **81,953 entries**, and a lookup needs two
things the game never writes down together: the hash of the path, and the payload.

- The hash is **Jenkins lookup3** (the same one Gibbed's tools use). It is not FNV, not CRC, and not
  a truncated SHA; the filelists that ship with the tools only work because they were built with the
  right one.
- Two name sources close the set: Gibbed's filelists (**55,811** rows) and the
  `assets/jc3/dictionary.json` that ships with
  [jc-model-renderer](https://github.com/aaronkirkham/jc-model-renderer) (**26,051** rows). The second
  is what names the DLC.
- First pass: **81,862 of 81,953 entries named (99.9%)**. The other **91** sat in four archives:
  86 in `patch_win64/game0`, 2 in `patch_win64/game1`, 2 in `patch_win64/game4` and 1 in
  `archives_win64/game67`. They were censused by magic byte first; a name that does not hash to the
  entry is worse than an unnamed entry.
- Second pass: **90 of the 91 named from the data**, each one hashing to its entry. 88 are navmesh
  tiles whose names follow a grid (`ai/tiles/<x>_<y>.navmeshc`). One `.hmddsc` was named from the
  archive's write order. One Polish `.wavc` was named from a token in its FSB5 name table, which is
  the same in every language. **81,952 of 81,953**; the last one is a dialogue take
  (`patch_win64/game4`, hash `016DE9D1`) that no filelist, dictionary, string or candidate search
  names.
- Two filelist traps: 63 "paths" that never resolved were Gibbed's `; <hit>/<total>` trailer lines
  read as paths, and the DLC has no filelists at all (the base game alone resolves 47,555 of 47,557
  from them).
- A path can exist in several mounts. `MOUNT_RANK` (patch > dlc > base) decides which copy loads, and
  the index records it per row, so a later join cannot silently read the wrong build.
- Vehicle space: **5,435 indexed paths** and **233 `.ee` bundles**.

The hash input is the path *inside* the bundle, extension included (`models/...` for model files,
`editor/...` for entity files), not the archive path. That distinction is what makes an inner-file
lookup possible at all (gotcha 2).

### Bundles and ADF v4: the container under every module

A `.ee` is a SARC/AAF bundle. Vanilla content is large: the Serpente is **566 inner files / 13.6 MB**
un-AAFed (5.5 MB archived). There is no per-file access — enumerate the bundle and read what it holds.

Almost every inner payload is **ADF v4** (`' FDA'`): a typed object graph with a class table, member
metadata and a payload block. The vehicle modules (`.vmodc`) exercise only a handful of kinds, which
is why the stock converter looks sufficient until it is not:

- **pointer** (type code 2), a data-relative offset to another object;
- **String** (`0x8955583E`), a data-relative offset to a NUL-terminated string;
- **StringHash** (code 9), resolved through the same lookup3 space as archive names;
- **inline arrays of primitives** (`IA[float]`, and arrays of `int8`/`int16`), which are stored with
  no self-describing length when their extent has to be inferred from the remaining payload.

Across the fleet: **6,045 `.vmodc` files, 6,045 decoded (100%), 52 module types, 1,421 member paths,
3,111,689 value rows.** Two traps survive into every join: module **instance** names truncate at 32
characters, and every land vehicle ships an `*_ai` twin of several modules with *different* values
(gotcha 3 and 4).

### The entity graph: parts, lights, effects and weapon points

The `.epe` is an RTPC property container, readable with `ConvertProperty`. Across the fleet it uses
**103 classes**; the useful counts are **11,041 `CPartProp`** (3…161 per entity, median 48),
**3,972 `SVehicleLight`** (4…54, median 16), **5,342 + 4,344 attached/dynamic effects**, and
**300 / 57 / 25 `SWeaponPoint` / bullet weapon / missile weapon** entries.

Two things this settled that had been inference:

- **A light rig is data, not a guess.** Each vehicle carries its `SVehicleLight` list with
  `preset_id`, `diffuse`, `radius`, `spot_angle`, `spot_inner_angle`, `near_cap`,
  `volumetric_mode`, `volume_intensity`, `enabled` and `multiplier`. The fleet's preset vocabulary is
  countable from the same pass.
- **Parts are named and ordered.** The `.epe` lists 40 `CPartProp` for the donor, indices 0…40 with
  one gap; `DeformPoints` names **42** parts for the same vehicle, adding `hood_signature` (index 25)
  and `missile_base_signature` (41). The 40 shared indices agree **40/40**. The graph is the tree; the
  parts module is the roster.

`*_vehicle_parts.vmodc` is the same ADF format and the one file the converter refuses (gotcha 5).
DeformPoints already names every part it touches, and a reader that knows the format gets the rest:
part index, damage type, behavior, model, collision body, light flag, children and wheel slots for
**11,643 parts across 233 vehicles**.

### Render blocks: four decoders and one sentinel

An `.rbm` is an RBMDL container: header, then blocks, each ending in a `0x89ABCDEF` checksum. Every
vehicle mesh in the game is version **1.16.0**, so header reading is uniform.

The header field that reads **9 on every vehicle file** is the tag (`m_Tag`, default 8, 9 on JC3
vehicles), not the block count. `m_NumberOfBlocks` comes first and varies from 1 to 9. Reading them
in the wrong order is what made "every vehicle mesh has 9 blocks" look like a rule. The Serpente
body really does have 9 `CarPaintMM` blocks, which are deform and damage zones (flags `0x1000`,
`0x1004`, `0x101F`), while the Mugello body has 3.

The fleet holds **56,136 meshes in 77,611 blocks**. The first pass decoded four block families:

| decoder | blocks | how it is read | oracle |
|---|---:|---|---|
| `CarPaintMM` | 52,902 | published layout | byte-exact re-encode |
| `Window` / `CarLight` | 23,395 | published layout | byte-exact re-encode |
| `GeneralMkIII` | 940 | quantised, see below | its own AABB, axes within 1% |
| framed, no vertex layout | 374 | materials + faces; vertices opaque | index buffer ends at the checksum |

`GeneralMkIII` is the interesting one. Its header is `u8 version=5`, an `Attributes` block (`0x68`)
that **ends in the block's own AABB** at `+0x4C`/`+0x58` and `pristine_index_count` at `+0x64`, then
`MaterialConsts2` (70 floats) and a texture table. Positions are `u32 count` followed by
`{s16 x, s16 y, s16 z, s16 32767}` records — but the record is **8 or 16 bytes** depending on whether
the vertex format interleaves a second 8-byte attribute. The sentinel is the test, so the stride is
detected, never assumed.

One scale per block maps the `s16` span onto the block's own AABB; across 940 blocks the non-degenerate
axes agree to **0.29%** worst case. The **header** AABB is the wrong oracle — it is the union over all
blocks — and using it is what produced the earlier 5% errors and 253 refusals (gotcha 6).

jc-model-renderer's `master` (`renderblockgeneralmkiii.cpp`) reads this block differently, and the two
were not compared here. It picks the stride from the block's flags rather than a sentinel: `IS_SKINNED`
(`0x20`) means 16-byte float `x, y, z, w` positions, anything else 8-byte `s16 x, y, z, pad`. And it
dequantises with a scale the block stores (`m_Packed.m_Scale`, `Attributes` +0x28) instead of fitting
one to the AABB. The AABB and `pristine_index_count` above sit in bytes it leaves as padding.

The 374 framed blocks were decoded in a later pass: they are `General`, `GeneralJC3`,
`BavariumShield`, `WaterDisplacementOverride` (`0xF99C72A1`, which the exporter calls "WaterHull"),
`Prop` and one family known only by its hash, `0x90FE086C`. Name block types from the published
enum, not from a word list.

First-pass totals: **77,237 decoded + 374 framed, 0 failed** (now 77,611 decoded, 0 framed), **20,797,479 vertices**, **19,197,927 triangles**,
**806,529 material slots**. Decoded positions and indices are written per entity as float32 ×3 and
u16/u32 pairs — outside the repository.

### Collision: Havok packfiles, not property files

Every `.physicsc` starts `57E0E057` and carries `__classnames__` / `__types__` / `__data__`, with
`hk_2014.1.0-r1` in the file. That is a **Havok 2014.1 packfile**; `ConvertProperty` cannot open it,
which is why the earlier work only knew the four wheel-station quads by their values.

Once read structurally, the fleet gives **233 entities / 234 files, 18,865 convex hulls, 4,791
collision meshes and 9,582 `hkGeometry` objects**. Every hull block sums to its extent and every
plane is the supporting plane of its vertex set — that is the oracle, not a visual check.

Two layers are worth separating:

- **Stations.** `land_global.vmodc` carries `base_wheel_hardpoint_positions[0..3]`. The same four
  quads appear a *second* time inside `.physicsc`, in **17 bundles across five vehicle families**, as
  four `float4 (x, y, z, 1.0)` sharing one `y`, one `|x|` with both signs and two `z` with both signs.
  All 17 agree with their `land_global` **to the last digit**, which is what proves the reading rather
  than fitting it. (The modded mesh's own station edits already relied on this.)
- **Shapes.** A compound's `hkArray` at `+0x60` holds 128-byte `hknpShapeInstance` records: a 3×3
  basis as three `float4` rows (`w` carries a per-row norm marker), translation at `+0x30`, scale at
  `+0x40`, child shape at `+0x50`. Placement is **`p' = Mᵀp + t`**; the untransposed form puts
  rotated children outside their compound's AABB (gotcha 9). The array is inline at `+0xD0` on the
  static class and a separate allocation on the dynamic one.

That yields **6,382 compounds and 35,499 instances**, of which **25,769 carry a
`CPfxPartIndexProperty` part index**, all 25,769 resolved to a part name by joining the parts table.
"18,865 hulls somewhere in the file" becomes a per-part collision layout.

### Effects, cameras and trim are the same container

The last payload family is not a format of its own: every `.effc`, `.ctunec` and `.trim` is ADF v4.
Extending the module reader with pointers, strings, hashes and inline arrays decoded **57,187 files
and 62,504,473 value rows with 0 failures**: 25,025 effects, 6,455 camera tunes, 25,707 trim files,
104 of them standalone archive entries and the rest inside bundles. Roots are `EffectRTSystem`,
`EffectTrimData` and 20+ camera tune classes. The `check` re-reads every file and compares a **row
digest and an object census**, so a decode that stopped early cannot pass.

### Vehicle systems, read from the same files

The second pass (2026-10-26 to 10-28) asked the port's questions of the decoded tables, one record
per system. Each record is generated by a script whose `--check` re-reads the archives and diffs
the page, and each check was tamper-tested once (change one number, expect a FAIL). The donor
throughout is the Serpente, `v0300_car_kensington_sportsmuscle_civilian_01`.

- **Weapons.** 25 vehicle weapon ids in three ADF classes (`WeaponTuning` 22 ids, `AutoAim` with 11
  shared presets). Every root class (`CCar`, `CAirPlane`, `CBoat`, `CHelicopter`, `CTrain`) has
  **four weapon slots** as object-id pointers, `00000000` when unused: `main_weapon` (`851CAABE`), a
  second driver slot `00568A74` that no shipped name table names (a 1.1-million-string search found
  nothing), `mounted_weapon`, and `mounted_weapon_2` (`AC0BC788`). Property names hash with the same
  Jenkins lookup3 as archive paths. 53 armed entities are wired.
- **Turrets.** A turret is two parts and two Havok hinges. On the medium tank, `mediumtank_turret`
  (behaviour `Turret`) yaws about +Y within ±179°, and its child `mediumtank_cannon` (`Cannon`)
  pitches about +X from −5° to +20°. The fire point names both parts in two unnamed string
  properties.
- **Doors.** A door is three pieces: a behaviour name (`FrontLeftDoor`, `Hood`, `MissileHatch` …), an
  index in `door_parts[]`, and a `hkpLimitedHingeConstraintData` in the `.physicsc`. The part itself
  holds no angle or speed. There are 224 door rows in 56 modules. Every hood hinges about X.
- **Moving parts.** Only hinged and rotating parts name a driving variable (`steering_roll`,
  `flaps_T`, `hatches_T`, `main_rotor_rpm`, `weapon_rpm` …). Every hinged row reads its variable as
  a 0..1 position except `SteeringFork`, which reads it as an angle. `rotoscope_rpm_per_cycle` is
  20 on 7 rows and 50 on the 5 rotor rows.
- **EMP.** The EMP truck's pulse is an entity-level `CForcePulse` that does 100 damage over a full
  25 m radius (the ordinary car blast does 500 in 5 m). It has no duration, target class or
  "disable" member, so "disables vehicles" is not in the data.
- **Damage.** Immunity is an entity field, not a module member: the vehicle root carries `health`
  (float 100) and `invulnerable` (int32, 0 on all 233 roots), 4 bytes at `epe+1167`. It is an
  all-or-nothing gate, so armour that should take 24 tank shells has to come from `max_health` and
  the armour channel split instead.
- **Water.** 189 entities sink (`will_sink` 1), 8 float and 35 boats carry `BoatBuoyancy`. No member
  anywhere makes a vehicle drive underwater.
- **Traffic and registration.** The donor is ordinary traffic, so replacing it puts NPC-driven
  copies on the roads. A new standalone `.ee` loads with **no** global registry edit on every route
  that names the entity by path (9 spawn tables). Only the Rebel Drop item keys on a 32-bit leaf
  hash. `BaseName` is `hash_jenkins(<vehicle family prefix>)` on 45 of 45 vanilla items.
- **Interaction.** 85 prefixed objects in the donor graph (`entry` 29, `exit` 26, `transition` 12 …);
  only 15 carry their own transform. Exits pick a state by the parent's speed: below 5 the normal or
  fall exit, above 5 a roll-out or the parachute exit. 4,832 exit objects across the fleet have no
  velocity or launch member, so no vehicle can eject its driver upwards.
- **Seat.** The vehicle places the driver only through its interaction graph. The pose is chosen on
  the character side (`rico_base.afsmb`, its IK targets and 36 `MOD_*` selectors), not by any
  vehicle module.
- **Audio.** `.ee.fmod_guids` lists the vehicle's 45 FMOD events across three banks. In a bank, every
  `TLNB` body is `[16-byte tune GUID][16-byte owning event GUID]`, so event → tune is stored on both
  sides (257/257). Tune → wave is not stored (0 of 649).
- **Strings and icons.** The display name is `profile/online.stringlookup`, keyed by
  `hash_jenkins(leaf)`, in 11 languages.
- **Writing `.physicsc`.** The packfile reader gained a writer. A round trip is byte-identical (2/2
  files, 54 hulls re-emitted), and remapping, uniform scaling and hull replacement pass their checks.
  A brand-new hull is still blocked: the face table has a prefix nobody has named yet.

## Build steps

1. **Index the archives.** For each `.tab`/`.arc` pair, read the flat hash → offset/size table, look
   the hash up in both name sources, and write one row per entry with its mount rank and archive.
   Census the unnamed ones by magic byte.
2. **Decode modules.** Unpack each `.ee` in memory, enumerate its inner files, decode every `.vmodc`
   with the ADF reader, and emit `(entity, type, instance, member, value)` rows. Group by
   `type-name`, not by the truncated instance string.
3. **Read the entity graph.** Convert each `.epe` with `ConvertProperty`; record class, name, depth
   and named values. Decode every `.rbm` header from **bytes**, not a path — these meshes never exist
   as files.
4. **Build the parts table.** Read `DeformPoints` for indices and names, then decode
   `*_vehicle_parts.vmodc` with the ADF reader for the fields the graph does not carry. Assert that
   the shared indices agree with the graph before writing anything.
5. **Decode render blocks.** Re-encode `CarPaintMM`/`Window`/`CarLight` byte-exactly as the oracle;
   decode `GeneralMkIII` with the sentinel stride and its own AABB; frame the remainder and mark it
   framed rather than failed. Write positions and indices outside the tree.
6. **Read the Havok packfiles.** Walk the class/type tables, then shapes, geometries and compounds.
   Place instances with the transposed basis and join each part index to the parts table.
7. **Extend the ADF reader for effects** (pointer, string, string hash, inline arrays) and decode
   every `.effc`/`.ctunec`/`.trim`.
8. **Give every step a `check`.** Each one re-reads the game and compares counts or digests against
   the table it produced. A grab with no drift check is a snapshot, and snapshots rot silently.
9. **Derive, don't probe.** The per-vehicle table (length, width, height, wheelbase, track, tyre
   radius, mass, top speed, steering time) is computed from these reads, and donor ranking is a
   scored sort over it.

## Verification

| what | oracle |
|---|---|
| archive names | both dictionaries hash to their entries; 81,952 of 81,953 named, every derived name hashes to its entry |
| modules | 6,045 of 6,045 decoded; row count and member paths regenerated by `check` |
| meshes | 52,902 + 23,395 blocks re-encode byte-exactly; 940 quantised blocks agree with their own AABB to 0.29% |
| formerly framed blocks | all 374 now decoded; at framing time, the texture table was self-locating and the index buffer ended at the checksum |
| `.physicsc` writer | round trip byte-identical on 2/2 files (54 hulls); the read-side gate is unchanged |
| wheel stations | 17 of 17 `.physicsc` copies equal `land_global` to the last digit |
| collision shapes | every hull block sums to its extent; every plane supports its vertex set |
| part wiring | 40 of 40 shared part indices agree between the `.epe` and `DeformPoints` |
| effects | 57,187 files with 0 failures, checked by row digest + object census |

What is **not** verified, and must not be claimed:

- **Non-position vertex streams.** Normals, UVs and the third stream are framed with their stride but
  not dequantised, so a re-import from these tables alone is not possible.
- **Quantised collision vertices.** The `hknpExternMeshShapeData` counts and AABBs are exact; the
  `3 × u16` positions are not dequantised.
- **Face-table semantics.** The `hknpConvexPolytopeShape` face records read plausibly as
  `u16 first, u8 count, u8 min`; only the index block is validated.
- **Body → shape wiring.** The 80-byte body and 64-byte motion entries are counted and sized, but
  their fields are not pinned. Part wiring comes from the compound instances, which is what the port
  needed.
- **Writing new collision.** The `.physicsc` writer can round-trip, remap, scale and replace
  existing hulls. It cannot add a new hull, and no written file has been tried in game yet.
- **Behaviour.** The systems section reads what the files carry. None of it has been driven in game.

## Gotchas

1. **Your lookup finds the archive entry but the file is garbage.** **Cause:** you hashed the archive
   path instead of the path *inside* the bundle, with its extension and its `models/` or `editor/`
   prefix. **Fix:** hash the inner path; verify against a file you can also read by name. (The same
   rule as the mesh-editing note's Gotcha 13.)
2. **99% of entries resolve and the last 91 look hopeless.** **Cause:** that is not a hash bug. They
   are in neither name source. **Fix:** census them by magic, then derive names from the data
   itself, never from guessed strings: grid patterns (88 navmesh tiles), archive write order, and
   tokens in the payload's own name table. Accept a name only when it hashes to the entry, and
   record what is left (1 here) as `unnamed`.
3. **A module join produces duplicated, conflicting rows.** **Cause:** module instance names truncate
   at 32 characters, so two instances can collide in the string. **Fix:** group by `type-name` and
   keep the full identity as the key, not the truncated label.
4. **The vehicle's handling looks wrong in a way no value explains.** **Cause:** you picked the
   `*_ai` twin. Most land vehicles ship two versions of several modules, and their values differ
   (a steering time of 1.2 against the AI's 2.0 on the same car). **Fix:** select by instance name,
   and record which twin a row came from.
5. **`ConvertAdf` dies with a `NullReferenceException` on `*_vehicle_parts.vmodc`.** **Cause:** the
   crash is inside its inline-array extent guess, not a missing type: the 31-type dictionary and the
   metadata block are byte-identical in 80 of 80 sampled files, and only the payload differs. String
   members are deduplicated, so an inline `A[int8]`/`A[int16]` block has no self-describing length.
   **Fix:** write the reader (or use `DeformPoints`, which converts for all 233 and names every part
   it touches). Do not conclude the format is unknown.
6. **A mesh decodes but its vertices are 5% off, or 253 blocks refuse outright.** **Cause:** the
   header AABB is the union over all blocks, not the block's own. **Fix:** use the per-block
   `Attributes` AABB at `+0x4C`/`+0x58`; the quantisation then agrees to 0.29% instead of chasing a
   scale that was never global.
7. **`GeneralMkIII` positions read as noise on some meshes.** **Cause:** the vertex record is 8 bytes
   on some meshes and 16 on others; a fixed stride reads the interleaved attribute as coordinates.
   **Fix:** find the `s16 32767` sentinel and derive the stride from its spacing — the test is in the
   data, so detect it.
8. **`ConvertProperty` cannot open `.physicsc`, and the extension misleads you.** **Cause:** it is a
   Havok 2014.1 packfile (`57E0E057`, class/type/data sections), not an RTPC container. **Fix:**
   write a packfile reader; treat `__classnames__` and `__types__` as the schema.
9. **Rotated collision children sit outside their compound.** **Cause:** the instance basis is stored
   row-major and the placement is `p' = Mᵀp + t`, not `M p + t`. **Fix:** transpose, then check that
   every child's corners fall inside the compound's own AABB — one direction passes, the other does
   not.
10. **You move a wheel hardpoint and the car shakes, even though `land_global` is correct.**
    **Cause:** the stations exist twice, and the Havok copy is the one the simulation uses. The copy
    is present in only 17 bundles, which makes it easy to assume it is absent. **Fix:** patch both
    from one stations file; absence of the second copy is a fact about that vehicle, not permission
    to skip the check. (The mesh-editing note's Gotcha 15 has the in-game symptom.)
11. **A value you just read does not match the running game.** **Cause:** the path exists in base,
    patch and DLC, and you read the wrong mount. **Fix:** resolve every lookup through `MOUNT_RANK`
    (patch > dlc > base) and keep the chosen archive in the row.
12. **The grab's tables stop fitting in the repo.** **Cause:** derived rows are cheap (a few MB) but
    decoded payloads are not: 440 MB of positions, 266 MB of module JSON, 141 MB of packfile dumps.
    **Fix:** keep raw payloads outside the tree, ship summaries and hashes inside it, and let
    `check` regenerate the rest from the install.

## Assets

None. This is a read pass: the only outputs are derived tables (index, value rows, entity graphs,
geometry summaries, collision wiring, effect rows) and the readers that produce them. No game bytes
are stored in the repository, and the full value dumps stay out of public ones (Setup).

## Cost and time

One pass per payload family, no game launches, no builds. The expensive part was not the reading; it
was the three formats that had to be pinned first (ADF's inline arrays, `GeneralMkIII`'s sentinel
stride, Havok's instance basis). Each one is now a fixed rule with an oracle, and each `check`
re-runs the whole grab against the install in minutes.

## Open questions

- **Dequantise the remaining vertex streams.** Positions are enough for measurement and ranking;
  normals and UVs are needed before these tables can regenerate a mesh.
- **`GeneralMkIII` against jc-model-renderer.** Does the 16-byte stride line up with `IS_SKINNED`, and
  does the stored `m_Packed.m_Scale` reproduce the AABB fit exactly? jc-model-renderer reads skinned
  positions as floats, which doesn't fit an `s16` sentinel in 16-byte records.
- **Quantised collision vertices.** The hulls are exact; the extern-mesh vertices are `3 × u16` and
  not yet mapped back to metres.
- **Face-table semantics.** One validated field out of four is not a decoded record.
- **Body and motion entries.** Pinning their fields is the step from "which part owns this shape" to
  "how the vehicle assembles".
- **A new hull.** The writer handles existing hulls. Adding one needs the face table's unnamed prefix.
- **The last unnamed entry.** One dialogue `.wavc` (`016DE9D1`).
- **`invulnerable` and the damage model in game.** Whether damage is applied as flat hit points or
  as a percentage changes the `max_health` a given armour ratio needs by exactly 2×. One in-game
  probe decides it.

## Related and credits

- The destination-side work, and what these tables were for, is in the Just Cause 3 note on
  [vehicle mesh editing](vehicle-mesh-editing-added-geometry-loads-with-matching-toc.md).
- The source vehicle and its native class layout are in the Batman: Arkham Knight note on
  [scraping the Batmobile](../batman-arkham-knight/scraping-the-batmobile-umodel-pskx-wwise.md).
- [Gibbed's Just Cause 3 tools](https://github.com/tim42/gibbed-justcause3-tools-fork) (Gibbed, fork
  by Timothée Feuillet) — the archive and property tooling this started from.
- [jc-model-renderer](https://github.com/aaronkirkham/jc-model-renderer) (aaronkirkham) — its shipped
  `dictionary.json` is the second name source, and its block headers are a reference for the RBMDL
  layouts.
- The grab passes were run in this project's agent sessions from 2026-10-22 to 2026-10-29 and
  recorded in the project journal; this note condenses those records. How the Batmobile's values
  were mapped onto these carriers is in the Just Cause 3 note on
  [translating the Batmobile](translating-the-batmobile-row-ledger.md).
