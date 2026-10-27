---
kind: game
title: 'Scraping the Batmobile: umodel PSKX, native class offsets and Wwise banks'
game: 'Batman: Arkham Knight'
games_also: ['Just Cause 3']
game_version: 'GOG Premium Edition, version.txt 1.999, buildId 57731640734362250, Season Pass + all DLC; cooked packages report UE3 Ver 863/227, Engine 10246, Game 800016'
platform: windows
engine: unreal
route: asset-only
tools: ['UE Viewer (umodel)', 'vgmstream-cli', 'custom Python UE3 package, WWAD and AkBank parsers', 'BmSDK-AK generated class bindings (class dump)', 'Blender 5.2']
anti_cheat: 'none — single-player, offline extraction from the user''s own install'
status: working
agents:
- 'OpenCode (space-bunny-free)'
- 'OpenCode (muse-spark-1.3)'
- 'Claude Code (Opus 5.5)'
- 'OpenCode (deepseek-v4.1-flash-free)'
- 'Freebuff (Buffy, model not recorded; wrote the note)'
humans: ['@NotTrevino']
date: '2026-10-22'
links:
- https://github.com/gildor2/UEViewer
- https://github.com/vgmstream/vgmstream
- https://github.com/Team-BmSDK/BmSDK-AK
tags: ['umodel', 'pskx', 'ue3', 'cooked-packages', 'wwise', 'bank-extraction', 'materials', 'textures', 'batmobile', 'native-classes', 'property-offsets', 'class-dump']
---

# Scraping the Batmobile: umodel PSKX, native class offsets and Wwise banks

> Extracting Batman: Arkham Knight's Batmobile is solved: umodel opens
> `Playable_Batmobile_SF.upk`, and its export gives a 299,837-triangle skeletal mesh, 25 material
> assets with full property dumps, and 56 textures. The engine audio is a second job — the WWAD
> containers and the embedded Wwise banks need your own parsers, but the event→media graph resolves
> completely. The handling numbers were the wall: the cooked property tags carry values but no
> names, and three attempts to read the native class layout from the shipped files each failed for a
> different reason. A generated scripting SDK broke it — **414 of the Batmobile's 422 named fields
> now resolve by class plus absolute offset**, and the eight that don't are one nested screen-shake
> bool block. Everything here was done for a Just Cause 3 vehicle port, but the extraction lessons
> are game-side, not destination-side.

## Setup

- **Game:** Batman: Arkham Knight, GOG Premium Edition. `version.txt` in the install root reads
  `1.999`; the GOG manifests are `goggame-1881970704.info` (base game, `buildId`
  `57731640734362250`, `gameId 1881970704`) and `goggame-1863845756.info` (Season Pass). All DLC
  installed. This is the *only* version the numbers below were measured on.
- **Engine:** heavily modified UE3. The Batmobile package reports `Ver: 863/227`, `Engine: 10246`,
  `Game: 800016` — umodel's game id for Batman: Arkham Knight.
- **Where the assets are:** `BmGame\CookedPCConsole\` holds the cooked `.upk` packages.
  `Playable_Batmobile_SF.upk` is 17,916,421 B and holds the Batmobile mesh, its materials and its
  textures. `GlobalPersistentCookerData.upk` (109,590,691 B) sits beside it and holds the engine's
  property schema: 40,380 records over 3,431 classes (gotcha 11). Audio is separate, under
  `SFX\*.wad`.
- **Extractor:** [UE Viewer (umodel)](https://github.com/gildor2/UEViewer), built locally from
  commit `a0bfb46` (2024-02-23). The binary used was `umodel.exe`, 1,468,928 B, built 2026-10-06.
  Its `umodel.cfg` had an explicit export path, `ExportDdsTexture = false`, and
  `SkeletalMeshFormat = 0`.
- **Audio:** a portable `vgmstream-cli`. No Wwise authoring install was needed, and nothing was
  installed system-wide.
- **What ships:** nothing from Arkham Knight. The umodel export, the carved banks and WEMs, and any
  Just Cause 3 build that contains them are game content from your own install: they stay private,
  outside any repository, as the
  [JC3 note](../just-cause-3/vehicle-mesh-editing-added-geometry-loads-with-matching-toc.md)'s
  Assets section says too. What can be shared is the method and your own tools.

umodel's directory scan of the install reports **4,260 game files (1,981 skipped) in 35 folders**.
That does not mean 4,260 usable assets; it means umodel found that many package candidates and
skipped the ones it could not classify.

## Route and why

Three routes exist for "get the Batmobile out of Arkham Knight":

1. **umodel export, then parse the export.** Chosen. It gives the skeletal mesh, every material's
   property tree and every texture in one pass, with no game code needed.
2. **Write a UE3 package reader first** and skip umodel. This is what the *audio* needed (no general
   tool exposes Wwise banks usefully), but it is unnecessary for meshes and materials. umodel already
   had the package format cracked for this engine build.
3. **Read the game's tuning values out of native class defaults.** Attempted three ways from the
   shipped files and closed each time, then reopened by a class dump generated from the running game
   (see "The negative result, and how it fell"). This is the route that names the handling values.

The split matters: **umodel solves geometry, materials and textures; your own parsers solve audio;
and the native numbers need a class layout the install does not ship.** Any plan that assumes one
source covers all three spends a day discovering otherwise.

## How the game works (what we had to learn)

### The package and its export classes

umodel loads `BmGame/CookedPCConsole/Playable_Batmobile_SF.upk` with
`Names: 3151 Exports: 5490 Imports: 649`. Exporting it writes four class folders:

| Folder | Files | What it is |
|---|---:|---|
| `SkeletalMesh3` | 2 | `Batmobile_V2.pskx` (17,357,622 B) + `Batmobile_V2.props.txt` (21,294 B) |
| `Material3` | 24 | 12 material masters, each with a `.props.txt` sidecar |
| `MaterialInstanceConstant` | 26 | 13 material instances, each with a `.props.txt` sidecar |
| `Texture2D` | 56 | `.tga` textures (DDS export was off) |

The mesh's own `MATT0000` chunk lists **19 material slots**; the 25 material *assets* include
masters that instances inherit from, plus materials not used by this mesh.

### PSKX is a chunked container

This is the single most expensive mistake to make. A PSKX is umodel's ActorX PSK with 32-bit
faces: umodel writes `.pskx` instead of `.psk` when a LOD has more than 65,536 wedges, and the
faces then go in `FACE3200` instead of `FACE0000` (`ExportPsk.cpp`). Both are a sequence of
32-byte chunk headers (`VChunkHeader` in umodel's `Psk.h`), each followed by its records:

```
offset 0x00  id[20]        ASCII, NUL-padded ("ACTRHEAD", "PNTS0000", ...)
offset 0x14  u32 version   20100422 (umodel's PSK_VERSION) on ACTRHEAD
offset 0x18  u32 stride    bytes per record
offset 0x1C  u32 count     number of records
offset 0x20  data          stride * count bytes
```

Then the next header follows immediately, and the walk must land **exactly** at end of file. The
Batmobile file contains:

| Chunk | Stride | Count | Meaning |
|---|---:|---:|---|
| `PNTS0000` | 12 | 201,338 | unique positions (`float3`) |
| `VTXW0000` | 16 | 253,163 | wedges: point index `u32`, `u`/`v` floats, material `u8`, reserved `u8`, pad `u16` |
| `FACE3200` | 18 | 299,837 | triangle: 3 × `u32` wedge index, material `u8`, aux `u8`, smoothing `u32` |
| `MATT0000` | 88 | 19 | material name `char[64]`, then six 4-byte fields (texture index, flags, LOD bias, ...) |
| `REFSKELT` | 120 | 180 | bone: name `char[64]`, flags, child count, parent, quat, position |
| `RAWWEIGHTS` | 12 | 202,698 | `float weight`, `u32 point index`, `u32 bone index` |
| `VERTEXCOLOR` | 4 | per wedge | an `FColor`; greyscale on this mesh, not a mask |
| `EXTRAUVS0` | 8 | per wedge | second UV set (two floats); half-float garbage on some materials |

A minimal, dependency-free walk (the tool that produced the table above):

```python
o = 0
while o + 32 <= len(b):
    cid = b[o:o + 20].split(b"\0")[0].decode("ascii", "replace")
    stride, count = struct.unpack_from("<II", b, o + 24)
    yield cid, o + 32, stride, count
    o += 32 + stride * count
assert o == len(b), "chunk walk did not land on EOF"
```

**Geometry is indexed by wedge, not by point.** 201,338 positions become 253,163 wedges because
positions split at UV and material seams. A parser that treats `PNTS0000` as the vertex buffer and
`FACE3200` as point triples will read out of range; the correct check is
`max(wedge.point) < point_count` and `max(face.wedge) < wedge_count`.

### Units and axes

The PSKX is in **centimetres**. At scale 0.01 the Batmobile measures **3.495 × 2.271 × 7.026 m**
over all non-wheel materials, with tyre radius **0.683 m**, wheelbase 5.029 m, front track 2.416 m
and rear track 2.569 m. The independent check is the tyre: 0.683 m radius → Ø1.37 m against the
1.40 m figure quoted for the real prop.

Axes are Unreal's: **X = length, Y = width, Z = up**, left-handed. Rendering all nine axis pairs as
orthographic grids is what settled that; reasoning about which axis "must" be length is not proof.
A destination engine with a different convention needs an explicit map and sign flip — this project
mapped PSK `(x, y, z)` to a Y-up, front-at-−Z frame as `(y, z, −x)`.

### Materials: the property dump is the truth

Two facts save a lot of time:

1. **umodel's `.mat` role labels are guesses and some are wrong.** It labelled `Wheel_V2_N` as
   "Diffuse"; it is a normal map. Do not build a texture pipeline on those labels.
2. **The `.props.txt` sidecar is authoritative.** It is a textual UE property tree: the
   `MaterialInstanceConstant` names its `Parent`, then lists `ScalarParameterValues`,
   `VectorParameterValues` and `TextureParameterValues` with **parameter names**. Masters carry
   anonymous `Collected{Scalar,Vector,Texture}Parameters` (defaults with `Name=None`), which is why
   following the parent chain is mandatory.

Inventory over the Batmobile materials: **48 scalar parameters, 24 vector parameters, 24 texture
parameters**. The scalars are the interesting half —
`MaterialN_{Reflectivity,Roughness,Metalicity,Microdetail_Size}`, `Mud*`, `Rain*`, `Wetness`,
`Glass_{Opacity,Reflectivity,Roughness}`, `Emissive_*`, `EMP*`, `Damage_dirt*`,
`Vector_Displacement_*`. The vectors include `MaterialN_BaseColour` (Material0 ≈ 0.026 grey,
Material3 ≈ 0.326 gunmetal), `Roughness_per_material`, `Roughness_Base_Level`, `Mud_Colour`,
`Damage_Dirt_Colour`, `CodeHeadlightColor` and `LightGroup1234/5678`.

**The body has no diffuse map.** `Mainbody` binds `Normal_Map = Body_N` and
`Damage_Chapter_Mask`, and nothing else. The matte-black look comes from scalar reflectivity and
roughness, so hunting for a missing `_D` texture is the wrong quest — the material genuinely does
not have one. Wheels and tyres bind nothing in their properties: they use shared tyre textures.
Glass is the one material with a full `Mask`/`Normal`/`Opacity` set.

### Audio: WWAD containers and embedded AkBanks

The two audio systems look alike from the folder listing and are completely different inside.

**`SFX\*.wad` are WWAD containers** — a flat table of `%08X` hashes to WEM payloads. A census of
**498 entries** found *all* of them Wwise Vorbis (`fmt 0xFFFF`), 48 kHz, 1–6 channels, and all RIFF.
Extraction by hash is exact: one 8 MB entry round-tripped byte-identically.

- **The hashes are not Wwise FNV-1/1a.** A 329-candidate hash search (FNV variants and seeds)
  produced zero matches. Without the Wwise project you cannot name an entry from its hash.
- **`INT_*.wad` is a different container.** It holds **BKPK** bundles of dialogue banks (2,734
  entries, 2,725 mono, 40 KB median), not RIFF. `WADZ` entries are `u32 size` + zlib-compressed
  WWAD. Test magic bytes; do not trust the extension.

**Banks live in the packages, not the WADs.** `.bnk` files that ship loose are ID-only HIRC objects;
the useful banks are `AkBank` exports inside cooked `.upk` packages. The chain that resolves
event→media is:

```
AkEvent (by name) → FNV-1(lowercase(name)) → HIRC event object → action (+6 bytes = target)
→ container → sound → DIDX entry → DATA offset/length → RIFF WEM
```

The hash was calibrated on a serial whose name is in the export table:
`Play_BattlemodeEngine = 0x388710DB`, which is FNV-1 of `play_battlemodeengine`. The second pair the
project recorded, `Transition_In = 0x102067E6`, does not check out (FNV-1 of `transition_in` is
`0xE9A427F2`), so either the id was miscopied or the event's full name differs. In a bank, an event
record is `id` + `u32 count` + the ids at `+8`. For `BML_Engine` this resolved **17/17 events to
media**, and the extracted loops were auditioned by ear before being used.

### The package container, for when a tool cannot open a pack

UE3 packages here are block-compressed. Two codecs ship: **zlib** for vehicle, object and animation
packs; **LZO1X** for level and city packs. The block table is `magic`, `0x20000`, totals, then
`(compressed_size, uncompressed_size)` pairs whose uncompressed sizes must sum to the total. The
decompressed image is `file[0:NameOffset] + decompressed stream`.

A zlib-only reader appears to work — until it hits a city pack and fails on the first block. Port
LZO1X rather than concluding the file is corrupt; it is roughly a page of code and needs no install.

### The native class layout, from a generated SDK

The tuning lives in two untagged native streams (`RVehicleBatmobile` 3,905 B,
`RVehicleSimBatmobile` 2,328 B): a run of `[u16 type][u16 offset][payload]` rows whose offset is
relative to the object the row belongs to. The **values** are all there; the **names** are not, and
neither is the layout that would let you read a row's slot kind. What finally supplied both is
**BmSDK-AK** (`Team-BmSDK/BmSDK-AK`, MIT), a scripting platform whose build step reflects over the
**running game** and emits C# with one absolute offset per property:

```csharp
/// FloatProperty: AirControlYawTorqueFactorMax
public unsafe float AirControlYawTorqueFactorMax
{
    get { return BmSDK.Framework.MarshalUtil.ToManaged<float>(Ptr + 1192); }   // 0x4A8
    set { BmSDK.Framework.MarshalUtil.ToUnmanaged(value, Ptr + 1192); }
}
```

Structs come out with `[StructLayout(LayoutKind.Explicit, Size = 112)]` and an offset per member.
`Ptr + 1192` is `0x4A8`, exactly the number space of the cooked tag, so a field resolves by
**class + absolute offset + slot kind** with no base to guess. 34 classes of the Batmobile's chain
(2,351 properties, 42 structs) were vendored from that public dump (`src/BmSDK/Generated` in the
repo), with its MIT notice; nothing from the game's own files is copied.

Why it is the same build, measured: `RVehicleSimBatmobile`'s dump size is 1,220, and the upk walk
lands on `0x104 + 0x3C0 = 0x4C4` = 1,220 with all 165 declared rows on the matching offset (147 by
name, the rest bools sharing one bitfield word). `RVehicleSimCar` 456 B, 37/37 names;
`RBatmobileMissileLauncher` 30/30; `RBatmobileEMPMissile` 36/36; `RBatmobileAllegianceSwitcher`
21/21; `RBatmobileBooster` 2/2; `RBatmobileMissile` 23/23. The native code anchors agree:
`SetDriveMode` writes the byte at `0x3B0` and `SkidToStop` at `0x3B1`, which is where the dump puts
`DriveMode` and `SkidToStopDir`. For the 195 object fields carrying a referent, the declared type
matches the class the reference points at every time (13 look like misses and are subclasses).

**Layout rules, all measured rather than fitted:**

- `UProperty::ArrayDim` sits at byte 6 of the property export. A static array is **one** property
  with N slots, not N properties — `GearRatios[6]`, `BoostCooldown[3]`, `VehicleWeapons[10]`.
- Every type aligns to **4** in this build, pointer slots included.
- `FInterpCurve<T>` is a **20-byte** slot (16-byte `TArray` + 4-byte-rounded mode), whatever `T` is.
- `ComponentProperty`, `InterfaceProperty` and `DelegateProperty` are real property classes and take
  real slots. Dropping them shifts everything after them by 8 or 16 bytes.

That last rule is what the earlier walk got wrong, and it is why the names had looked unrecoverable.
The `AirControl*` run sat one slot early, so the 8,000 float that read as `AirControlTimeInAir` is
really `AirControlYawTorqueFactorMax`; `AirControlTimeInAir` is at `0x4BC` and the class ends at
`0x4C4`. `0x318` is `RInventoryGadget.Mesh`, not `XrayMaskMaterial`; `0x1334` is
`VehicleWeapons[0]` (referent `Weapons.Batmobile_Cannon_V2`); `0x2AC` is `DriftingBoostCooldown`;
and `VehicleTransmission` is 112 bytes, not 92.

**Residue.** 8 of the 422 fields stay unnamed: the nested screen-shake bools, where the flattened
offset is ambiguous between `BMScreenShakeStruct` and its `AdvancedOptions` child. They are recorded
by offset and not guessed. Separately, seven classes (`RBatmobileCannon`, `RBatmobileHeavyCannon`,
`RBatmobileSonar`, `RBatmobileWinch`, `RVehicle`, `RVehicleBatmobileBase`, `RInventoryGadget`)
cannot be regenerated from the *shipped* declaration — that copy is a different build. That does not
affect the names, which come from absolute offsets in the dump.

## Build steps

1. **Point umodel at the install** (`E:\Games\Batman - Arkham Knight`). It scans the tree and
   detects the game itself; confirm the package line says `Ver: 863/227 ... Game: 800016`.
2. **Open `BmGame/CookedPCConsole/Playable_Batmobile_SF.upk`** and export the `SkeletalMesh3`,
   `Material3`, `MaterialInstanceConstant` and `Texture2D` folders. With DDS export off, textures
   land as `.tga`. Keep the export tree outside any repository — it is game content.
3. **Parse the PSKX by chunk id**, then validate the walk ends at EOF and every record index is in
   range. Never index faces by point id.
4. **Resolve materials from `.props.txt`**, walking each instance's `Parent` chain and letting the
   nearest named override win. Do not use umodel's `.mat` role labels.
5. **Scale by 0.01** into metres and apply an explicit axis map. Verify the result with two
   independent measurements (overall length and tyre diameter), not one.
6. **For audio**, extract WEMs from WWAD by hash and decode with vgmstream. For banks, dechunk the
   package, dump its name table and export table, carve the `AkBank` export, then walk HIRC. Calibrate
   the event-name hash on a serial whose name you already know before trusting any lookup.
7. **For the native values**, index a class dump of the running build by class + offset, then resolve
   each cooked tag row against it, walking superclasses. Prove the index on a class you can also
   re-derive from the shipped declaration (`RVehicleSimBatmobile`, 1,220 B) before trusting a name.

## Verification

What was measured, and how:

- **PSKX structure** — the chunk walk lands exactly at EOF; `max(wedge.point)` and
  `max(face.wedge)` are both exactly in range; face count and material count agree with the chunk
  table. The layout census, the parts classifier and the mesh exporter read those numbers
  independently.
- **Units** — the 0.683 m tyre radius comes from the mesh, and matches the 1.40 m quoted diameter
  within 2%. The same 0.01 scale then produced a 7.026 m body, consistent with the prop.
- **Materials** — every exported material's props parsed into named parameters; 19 material slots
  resolved along their parent chains with **0 unhandled factors** in the final translation pass.
- **Audio** — byte-exact WWAD extraction on an 8 MB entry; bank carving verified on 10 packages;
  `BML_Engine` resolves all **17/17** events to media; the user identified the engine loops by ear.
- **Textures** — 56 textures exported and cross-checked against material bindings, not just counted.
- **Native field names** — 414 of 422 cooked fields resolve; the class-size arithmetic lands on
  exactly 1,220 B for `RVehicleSimBatmobile` with all 165 declared rows on their dump offset, and
  37/37 on `RVehicleSimCar`. Native write offsets agree (`0x3B0` `DriveMode`, `0x3B1`
  `SkidToStopDir`) and all 195 object referents match their declared classes.

What is **not** verified, and must not be claimed:

- That any named handling, mass, damage or armour **value** behaves as its name in the destination
  game — the names are measured, the in-game behaviour is the port's still-open job.
- The eight undecidable screen-shake bools (see below); they are recorded by offset only.
- That the `BML_Battlemode` bank exists in a form reachable from shipped files at all.
- That other Arkham Knight vehicles export as cleanly. Only the Batmobile package was worked.

## Gotchas

1. **Your PSK parser reports 20,100,422 vertices.** **Cause:** it read the file as a flat layout
   (`char[20]`, then `int32` counts). The first `int32` after the id is the root chunk's version
   field, which umodel sets to 20100422 (`PSK_VERSION`) on `ACTRHEAD`. **Fix:** walk 32-byte chunk
   headers, and assert the walk ends at EOF.
2. **You grep for four-letter all-caps ids, find only the root and points, and conclude "there are
   no triangles".** **Cause:** chunk ids are 8–16 characters and include digits (`PNTS0000`,
   `FACE3200`, `EXTRAUVS0`), so a strict four-character scan misses them and every later hit is float
   data that happens to look like ASCII. **Fix:** parse the chunk table; do not decide a file's
   contents from a string scan. This cost a wrong "the mesh is a point cloud" finding that survived
   several days.
3. **Your mesh exports, but every face index is out of range or the UVs are garbage.** **Cause:** you
   indexed `FACE3200` against points. Faces index **wedges**, and wedges index points.
   **Fix:** `face → wedge → point`; check each hop against its own count.
4. **You pick textures using umodel's `.mat` labels.** **Cause:** they are heuristic role guesses, not
   data. One normal map was labelled "Diffuse". **Fix:** read `TextureParameterValues` from the
   `.props.txt` sidecar.
5. **You look for the Batmobile's missing body diffuse and find nothing.** **Cause:** it does not
   have one. The body is matte black by scalar reflectivity/roughness, with only a normal map and a
   damage mask. **Fix:** port the scalars and vectors, not just textures. Treating "no diffuse" as a
   failed export sends you hunting for a file that was never shipped.
6. **A material's colours appear absent from its property dump.** **Cause:** colours are *vector*
   parameters (`MaterialN_BaseColour`), and masters store them as anonymous
   `CollectedVectorParameters` with `Name=None`. **Fix:** read vectors, and walk the parent chain;
   the named override may live on a parent instance, not the leaf.
7. **Your Wwise hash lookup never matches.** **Cause:** WWAD hashes are not Wwise FNV-1 or FNV-1a;
   a 329-candidate hash search produced zero hits. **Fix:** do not try to name WWAD entries. Shortlist
   by measurable properties (channel count, duration, spectral centroid, harmonicity) and audition.
   Name lookup works only inside banks, where you can calibrate against an `AkEvent` serial you can
   already read.
8. **`ww2ogg` and `ffmpeg` both fail on the extracted WEMs.** **Cause:** these are Wwise Vorbis with
   no `vorb` chunk — the codebooks are not inline. **Fix:** use `vgmstream`, which handles Wwise
   Vorbis directly.
9. **A bank name appears in a dozen packages, and none of them defines it.** **Cause:** those are
   **import** references. A package that *uses* `Play_BattlemodeEngine` is not the package that
   *ships* `BML_Battlemode`. **Fix:** distinguish imports from exports before concluding a bank is
   present. An exhaustive sweep of 3,266 packages found references only; the definer is still
   unlocated.
10. **Your zlib decompressor works on vehicles and dies on city packs.** **Cause:** UE3 uses two
    codecs — zlib for object/vehicle packs, LZO1X for level/city packs. **Fix:** detect per block, and
    validate `sum(uncompressed) == total` before decompressing anything.
11. **You reconstruct native class layouts from `GlobalPersistentCookerData.upk` and the offsets are
    nonsense.** **Cause:** GPCD does carry 40,380 property records across 3,431 classes with
    fully-qualified names and types — but its trailing `u32` per record is neither a unique offset nor
    an offset at all (`SVehicle.Wheels` and `SVehicle.bUpdateWheelShapes` share one value), and floats
    read there are denormal garbage (`1.5e-36`). **Fix:** use GPCD for **names and types only** and
    take offsets from a class dump of the running build (native-class section above). GPCD is also the
    *editor's* schema for a different build, so it never had this game's layout to give.
12. **You find the Batmobile's native tuning blobs and every value is anonymous.** **Cause:**
    `RVehicleBatmobile` (export 5280, 3,905 B) and `RVehicleSimBatmobile` (export 5281, 2,328 B) are
    untagged native CDO streams of repeated `[u16 type][u16 offset][payload]` entries. Type 4 is a
    float at an object offset, type 13 an `FString`, and offsets restart inside each nested struct.
    The blobs contain **zero** property-name strings — a full printable-run scan of the Sim blob finds
    none. **Fix:** values are unattributable *from the file*, but not unattributable in principle:
    resolve `(class, offset, type)` against the dump. A magnitude that looks like mass is still not
    mass until that lookup names it.
13. **umodel warns `Unknown class "RVehicleSimBatmobile"` and you assume the package failed.** **Cause:**
    umodel loaded the package fine; it simply has no layout for the game's native vehicle classes.
    **Fix:** read the warning as a boundary for *umodel*, not for the file: mesh, materials and
    textures come out; the layout has to be obtained elsewhere (a class dump, above). Concluding "the
    package is closed" from it is what cost this project its first three attempts.
14. **You look for handling values in the ini files.** **Cause:** `BmGame.ini`, `DefaultGame.ini` and
    `PCGame.ini` hold keybinds (`pGlideSteer` and friends), not vehicle tuning. **Fix:** stop. The
    values are native class defaults, and gotcha 12 is why the file alone does not name them.
15. **Your texture folder contains assets the Batmobile never uses.** **Cause:** an umodel package
    export pulls in referenced textures, including shared or unrelated ones (`AceBridgeStatue_Detail`
    was in this set). **Fix:** drive texture selection from material bindings, never from a folder
    listing.
16. **A converted material looks flat and lifeless even though every texture landed.** **Cause:** the
    source renderer's look lives in scalar/vector parameters as much as in maps — reflectivity,
    roughness, metalness, microdetail and per-material base colour. **Fix:** inventory the parameter
    interface first and translate it input by input, tagging each value's source. Texture-only
    conversion cannot reproduce a material.
17. **A whole run of fields reads one slot early, and an 8,000 value lands where a time should be.**
    **Cause:** the layout walker had no slot for `ComponentProperty`, `InterfaceProperty` or
    `DelegateProperty`, so it dropped 8 or 16 bytes each and every later field slid forward. That is
    what put `AirControlYawTorqueFactorMax` under the name `AirControlTimeInAir`; the true
    `AirControlTimeInAir` is at `0x4BC`, and the class ends at `0x4C4`. **Fix:** lay out **every**
    property class the engine defines, then re-derive the whole class size and compare it with a known
    total (here 1,220 B for `RVehicleSimBatmobile`) before reading a single value.
18. **Your static arrays look like one float, and everything after them is shifted.** **Cause:** a
    static array is one property with N slots, not N properties; the count is `UProperty::ArrayDim` at
    byte 6 of the property export, which the walker was ignoring. `BoostCooldown[3]`,
    `GearRatios[6]` and `VehicleWeapons[10]` are the three in this package; counting `BoostCooldown` as
    a float is what renamed `DriftingBoostCooldown` at `0x2AC`. **Fix:** read `ArrayDim` and reserve
    `N × slot size` bytes for the property.
19. **Scalars line up but pointers and curves do not.** **Cause:** two alignment assumptions. Every
    type in this build aligns to **4**, pointer slots included; and `FInterpCurve<T>` is a **20-byte**
    slot (16-byte `TArray` + a 4-byte-rounded mode) whatever the point type. Assuming 8-byte pointer
    slots or a 16-byte curve misplaces fields without changing the total enough to notice. **Fix:**
    align 4, and treat every `FInterpCurve` as 20 bytes; verify with a struct whose size you can check
    independently (`VehicleTransmission` is 112, not 92).
20. **The dump disagrees with itself on bools — dozens of properties share an offset.** **Cause:** not
    a mismatch: bools are packed into one bitfield word, and the generated accessor reports the
    word's first bool for every sibling. **Fix:** compare the word, then order the bools by
    declaration; a shared offset with the same word size is agreement, not drift.
21. **Seven classes cannot be reproduced from the shipped declaration, so you start doubting the
    dump.** **Cause:** the copy of those classes in `BmGame.upk` is a different, smaller build than the
    one the engine linked. **Fix:** this affects re-derivation offline, not naming: the names come from
    absolute offsets in the running build's dump. Record the mismatch and move on.

## Assets

What was extracted, for scale. All of it is game content from the author's own install and stays
private (Setup, "What ships").

- **Mesh:** 201,338 positions, 253,163 wedges, 299,837 triangles, 19 material slots, 180 bones,
  202,698 skin weights. 17,357,622 B as exported PSKX.
- **Materials:** 12 masters + 13 instances; interface of 48 scalars, 24 vectors, 24 textures.
- **Textures:** 56 TGA files (DDS export was disabled).
- **Audio:** 498 WEMs in the `SFX` WADs; `BML_Engine` (7.3 MB) with 17 events mapped to media;
  `BML_Burnout`, `BML_AUX` and `MK2_Engine` carved with the same tools.
- **Native layout:** 34 classes, 2,351 properties, 42 structs from the generated dump; 422 cooked
  fields resolved, 414 named, 8 undecidable by offset.

## The negative result, and how it fell

For most of this project the note said the Batmobile's **handling, mass and damage numbers are not
readable from the shipped files**. The three measurements behind that were real:

1. The native CDO streams contain values but no names (gotcha 12).
2. `GlobalPersistentCookerData.upk` supplies names and types but no usable offsets (gotcha 11).
3. umodel cannot derive a property layout without the cooked script packages, which are compressed
   (gotcha 13), and a full-disk string census found the mass-member names only in GPCD, once each.

What they add up to is narrower than "not obtainable": the install was **never shipping the name
table this build needs**. GPCD is the *editor's* schema, and the copy in the package is a different,
smaller build than the classes the engine linked — which is exactly why the layout walk could not be
closed from it. The missing input was a class declaration from the build that was actually running.

That is what a generated SDK is. BmSDK-AK's build reflects over the running game's `UClass` chain and
writes every property with the offset the engine itself linked it to, so "the field at object+0x4A8"
becomes a name without any struct walking. With it, **414 of the 422 Batmobile fields resolve**; the
eight exceptions are the flattened screen-shake bools, recorded by offset and not guessed. The slot
rules could then be checked instead of fitted (native-class section above), which is how the
`AirControl*`, weapon-array and `0x318` errors were caught.

What is still not established: the *values* are named but have not been driven in the destination
game — that is the port's job, not the extraction's. And the seven classes listed above cannot be
reproduced from the shipped declaration, so a future offline re-derivation of those is blocked until
a dump of that exact build exists. A derived real-world estimate (power, top speed, 0–60) remains a
sanity band, not the game's internal number.

## Open questions

- **Where does `BML_Battlemode` load from?** It is referenced by name in vehicle packs but defined in
  none of the 3,266 packages swept, and its `Turbo`/`BattlemodeEngine` event bytes appear nowhere on
  disk outside the referencing serials. The remaining test is runtime file-access observation, not
  more static scraping.
- **The eight screen-shake bools.** Their flattened offset is ambiguous between `BMScreenShakeStruct`
  and its `AdvancedOptions` child. One disassembly of the accessor, or one in-game bit test, settles it.
- **Do the named values hold in game?** The names are measured; whether `AirControlYawTorqueFactorMax`
  drives yaw the way the port assumes is a driving test on the destination side.
- **Do other vehicles export as cleanly?** Only the Batmobile package was worked. The dump route is
  asset-generic (any class in the running game), but that is unproven for another vehicle.

## Related and credits

- [BmSDK-AK](https://github.com/Team-BmSDK/BmSDK-AK) (Eli Kramer / Team-BmSDK, MIT) — a scripting
  platform that generates C# bindings from the running game; its class dump is what turned the cooked
  offsets into names. Only the generated class declarations were used, and only for offline analysis.
- [UE Viewer / umodel](https://github.com/gildor2/UEViewer) (Gildor) — the package reader that made
  the mesh, material and texture half of this cheap.
- [vgmstream](https://github.com/vgmstream/vgmstream) — decodes Wwise Vorbis without codebook surgery.
- The destination-side work lives in the Just Cause 3 note on
  [vehicle mesh editing](../just-cause-3/vehicle-mesh-editing-added-geometry-loads-with-matching-toc.md).
