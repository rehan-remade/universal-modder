---
kind: game
title: "CBBE OSD/TRI validation, isolated BodySlide builds, and a tested morph/physics baseline"
game: "Skyrim Special Edition"
games_also: []
game_version: "Runtime test: 1.6.1170.0 with SKSE 2.2.6; separate inspected Steam executable metadata: 1.7.104.0"
platform: windows
engine: creation
route: asset-only
tools: ["BodySlide/Outfit Studio 5.8.1.0", "MO2 2.5.2", "Node.js readers", "RaceMenu AE 0.4.20.0", "CBPC 1.6.2", "local CBBE directory labelled 2.0.3", "local XPMSSE directory labelled 5.06"]
anti_cheat: "Single-player research profiles only; no online client, anti-cheat bypass, DRM removal or ownership-check change involved"
status: working
agents: ["OpenCode (GPT-6.1 Sol)", "OpenCode (GPT-6.1 Sol Fast)", "OpenCode (GPT-6 Astra Fast)"]
humans: ["Kokuru"]
date: 2026-10-28
links:
  - "https://github.com/ousnius/BodySlide-and-Outfit-Studio/tree/v5.8.1"
  - "https://github.com/ousnius/BodySlide-and-Outfit-Studio/blob/38139d40f74bc675a093db705fe7f4c0151d01ec/src/components/DiffData.cpp"
  - "https://github.com/ousnius/BodySlide-and-Outfit-Studio/blob/38139d40f74bc675a093db705fe7f4c0151d01ec/src/files/TriFile.cpp"
  - "https://github.com/ousnius/nifly/blob/6cb15fb5da71527b33cea8ff7913be8790e1c633/src/Skin.cpp"
  - "https://github.com/ianpatt/skse64/blob/25b72352adb6543fa6d0bd3795780672b2e238e0/skse64/PluginAPI.h"
  - "https://github.com/ianpatt/skse64/blob/25b72352adb6543fa6d0bd3795780672b2e238e0/skse64/PluginManager.cpp"
  - "https://github.com/ousnius/BodySlide-and-Outfit-Studio/wiki/Conversion-references-and-using-them"
  - "https://github.com/DaymareOn/hdtSMP64/tree/2215ec3ba09adf0843a3291ed0437a6ca6d385e2"
  - "https://github.com/Acro748/CBPCSSE/tree/fabd56ce8f8ac10cde17325f0bd61ecc8cbcda20"
tags: [cbbe, bodyslide, osd, tri, nif, morphs, isolated-build, mo2, skse, physics-routing, verification]
---

# CBBE OSD/TRI validation and an isolated Skyrim runtime baseline

> Two real BodySlide builds verified the local project's 137 morphs against its
> authoring deltas. A separate single-player profile subsequently demonstrated a
> restored morph through RaceMenu and basic secondary motion through CBPC, with
> human assistance. This is a working, scoped reference-validation result, not
> verification of every runtime slider, contact collision, or another game's port.

**Read this before** debugging a BodySlide slider that appears in a menu but does
nothing, writing an OSD/body-TRI reader, or setting up a morph/physics test without
overwriting an active MO2 profile. The most reusable result is the distinction
between authoring datasets, baked shape and runtime morph availability.

## Setup

- Windows; BodySlide/Outfit Studio executable metadata **5.8.1.0**, MO2 **2.5.2**.
- Runtime tests used an existing compatible **Skyrim 1.6.1170.0 / SKSE 2.2.6**
  installation in a separate research instance. A different installed executable
  inspected earlier reported **1.7.104.0**. These were separate inputs, not a claim
  that the same plugin stack runs on both versions. No downgrade recipe is provided.
- Source directories were labelled **CBBE 2.0.3** and **XPMSSE 5.06**. Their original
  release manifests were not authenticated: file counts below describe the inspected
  local collection, not every release with those labels.
- The runtime baseline used supplied **RaceMenu AE 0.4.20.0** and **CBPC 1.6.2**.
  The extended source study inspected **3BA 2.48** and **Faster HDT-SMP 4.1.1**;
  those were not required for the basic CBPC test.
- Saves, settings and profiles were backed up. Asset inspection, authoring outputs,
  logs and any private binary-analysis material stayed outside the contribution.

## Route and why

Use the existing authoring tool and installed plugins before implementing another
morph engine. The initial task was to establish what the actual mesh/delta files
contain and whether BodySlide exports them correctly, without changing the active
modlist. Runtime morph and physics tests then ran in separate research profiles.

This note shares format facts and observed results in original prose. It does not
ship a body, preset, generated TRI/NIF, third-party DLL, or replacement runtime.

## How the game works (what we had to learn)

### Replacement topology is not a vanilla-vertex morph

CBBE replaces geometry. The inspected vanilla body had **1,353 vertices / 2,412
triangles**, plus a separate **676-vertex / 688-triangle** underwear overlay.
The local Slim, Curvy and Vanilla CBBE bodies each had **13,554 vertices / 26,286
triangles** with identical triangle indices across those three options. The name
"CBBE Vanilla" does not mean vanilla vertex correspondence.

The examined SSE NIFs used stream version **100**. Resolve skin-instance references
and their `NiSkinPartition` buffers, shape transforms and parent transforms before
comparing positions. Comparing raw coordinates had mistaken stored translation
for a body-shape difference.

The supplied **Vanilla To CBBE** conversion reference likewise uses CBBE topology
in vanilla-like proportions. It is a correspondence carrier, not evidence that a
replacement body was created by adding deltas to the original game's vertex IDs.
The official [conversion workflow](https://github.com/ousnius/BodySlide-and-Outfit-Studio/wiki/Conversion-references-and-using-them)
separates conforming the outfit, baking, loading the intended reference body,
weight copying and exporting with that body. A successful nearest-reference query
does not by itself establish fit, clearance or equivalent proportions.

### OSD authoring data and body TRI are different formats

The following describes the inspected BodySlide body formats, not facial TRI or
every file with a `.tri` extension. Public implementation references are
[`DiffData.cpp`](https://github.com/ousnius/BodySlide-and-Outfit-Studio/blob/38139d40f74bc675a093db705fe7f4c0151d01ec/src/components/DiffData.cpp)
and [`TriFile.cpp`](https://github.com/ousnius/BodySlide-and-Outfit-Studio/blob/38139d40f74bc675a093db705fe7f4c0151d01ec/src/files/TriFile.cpp).

| Property | OSD v1 | BodySlide body TRI |
|---|---|---|
| On-disk magic bytes | `00 44 53 4F` | `50 49 52 54` (`PIRT`) |
| Top level | uint32 version and dataset count | position section, then UV section when present |
| Names | uint8 byte length, then that many bytes | uint8 byte length for shape and morph names |
| Counts | uint16 records per dataset | uint16 shape, morph and affected-vertex counts |
| Position entry | uint16 vertex index and three float32 components, packed to 14 bytes | uint16 vertex index and three signed int16 components |
| Scale | none per entry | float32 multiplier per morph |
| UV entry | dataset meaning comes from its project | uint16 index and two signed int16 components |

TRI displacement is **signed component times the morph multiplier**. It contains
neither base topology nor a NIF filename. In this project, `BaseShapeHR` was the
OSP data target, while the exported shape was named `CBBE`. NIF shape metadata
`BODYTRI` associated the output with its morph file.

BodySlide baking and runtime morph availability are separate: changing the preset
changes the exported NIF, but an all-zero preset need not remove the TRI's morphs.
Compare missing entries as zero across the union of source/export vertex IDs;
checking only the intersection can conceal an export mismatch.

For the inspected Windows files, multi-byte numeric fields are little-endian.
Position TRI entries occupy 8 bytes; UV entries occupy 6. The pinned writer chooses
each nonzero morph's multiplier from its maximum absolute component divided by
32767, then converts scaled components to integers by truncation toward zero.
A round-to-nearest assumption (half a multiplier of error) is therefore unsuitable:
allow one quantization step plus an explicitly stated floating-point allowance,
and report the worst component error per morph. This describes the public writer,
not a new measurement of every possible export.

Keep **byte round-trip** and **semantic comparison** as separate tests. A lossless
reader must retain stored ordering, counts and quantized values, including explicit
zero records; the public reader can omit zero offsets in its in-memory maps.
Decoding and rebuilding those maps is not automatically a byte-preserving round-trip.
When implementing a reader, reject truncated fields and out-of-range indices against
the associated mesh; do not silently treat a partial UV section as an absent one.

### A short diagnosis for a non-working slider

Follow the complete name/resource chain: **menu label → internal morph ID → OSP
target/dataset → exported NIF shape → `BODYTRI` resource → TRI shape and morph**.
In this case, `Legs - 7B Legs` mapped to `7BLeg_v2`; `BaseShapeHR` and `CBBE`
belonged to different stages, so comparing their strings alone would misdiagnose it.
First compare the intended export with MO2's effective file. If the morph is absent,
rebuild the correct project; if present, compare its decoded deltas; only then test
runtime loading and an isolated slider. A populated menu proves none of those later
links. This is a diagnostic ordering derived from the investigation, not a claim
that every possible failure in that chain was reproduced.

### Runtime compatibility and physics ownership

The examined `skee64.dll` declared explicit compatibility with **1.6.1170** and no
version-independence flags. The [SKSE plugin contract](https://github.com/ianpatt/skse64/blob/25b72352adb6543fa6d0bd3795780672b2e238e0/skse64/PluginAPI.h)
explains why that particular binary is not compatible with the separately inspected
1.7.104 executable. An Address Library installation does not override that declared
version contract. Use a supported combination; do not patch the compatibility check.
On 1.7.x there is a second check: the Address Library encoding changed in 1.7.99, and
SKSE 2.3.1 (the build for 1.7.104) disables an Address Library plugin built before
2025-05-26 without the `kVersionIndependentEx_AddressLibraryV5` flag ("must be
recompiled for new address library", [`PluginManager.cpp`](https://github.com/ianpatt/skse64/blob/25b72352adb6543fa6d0bd3795780672b2e238e0/skse64/PluginManager.cpp)).

The ordinary inspected CBBE body referenced **26 bones**; its Physics counterpart
referenced **30**, adding positively weighted breast/butt nodes. Matching physics
weights, skeleton nodes and one simulator's node mapping are all required. A DLL
successfully loading is not proof of visible secondary motion.

The four added weighted nodes were `NPC L Breast`, `NPC R Breast`, `NPC L Butt`
and `NPC R Butt`. In this collection, the ordinary and Physics bodies had identical
base positions and triangle indices. This made retaining their morph vertex IDs
valid; verify that correspondence for another body rather than assuming it from
the word "Physics". A skeleton's named-node count is not its weighted-bone count.

Extended static research found six weighted breast joints on the main 3BA body and
an additional collision-object project. Commented XML blocks are not active bodies
or constraints. Manager scripts also perform explicit CBPC/SMP ownership handoff.
Public FSMP source writes solved world transforms, whereas a local-offset system
must be interpreted through its own hierarchy. Do not accumulate a solved parent's
motion a second time. These source findings were not a live full-3BA/contact test.

## Build steps

1. Inventory exact game, SKSE, plugin and BodySlide versions. Keep the original
   working configuration and source hashes. Back up saves and settings.
2. Copy the existing BodySlide executable/resources and the intended project into
   an external lab. Use a fresh configuration with lab-only project/data/output
   paths and an empty lab game-data directory; disable archive texture scanning.
3. Use a one-project group containing only `CBBE Body`, avoiding outfit output
   conflicts. Create an explicit all-zero preset and a second preset with only
   `7BLeg_v2` at 100 at both weight endpoints.
4. Run the copied **5.8.1** executable twice with the tested release's interface:

   ```text
   BodySlide.exe -gbuild LabBody -p LabZero -t <lab-zero-output> -tri
   BodySlide.exe -gbuild LabBody -p LabProbe -t <lab-probe-output> -tri
   ```

   `LabBody`, `LabZero` and `LabProbe` are names you assign to the lab group and
   presets; they are not downloadable files supplied by this note.
5. Inspect actual output NIF/TRI files, not just the success message. Verify
   positions, topology, shape names, morph names, quantization and `BODYTRI` links.
   Recheck original input/config hashes.
6. For a separately authorized runtime test, use a compatible game/SKSE/plugin
   combination in a separate MO2 research instance. Check **effective** virtual
   file hashes and local settings/save redirects before launching.
7. Test a restored morph first. Preserve that morph-only baseline before adding
   a matching Physics body, skeleton and CBPC mapping in another profile. Leave
   colliders and multi-engine handoff out until they have their own test.

## Verification

Private test records establish the following; the underlying proprietary/mod files
and captured menus are deliberately not attached to this contribution.

| Check | Observed result | Scope limit |
|---|---|---|
| Read and re-encode local morph corpus | 469 OSD and 429 body TRI files round-tripped byte-for-byte | Local corpus, not universal format coverage |
| Original bundled body TRI | 97 position morphs and 1 UV morph; 39 local project names absent | Historical reason for the mismatch unknown |
| Fresh zero/probe BodySlide builds | Both exited successfully; 136 position morphs and 1 UV morph | Export validation, not 137 independent gameplay tests |
| Fresh TRI vs OSD | All 137 morphs agree within quantization tolerance across the union of indices | No claim of historical source-to-DLL equivalence |
| Zero/probe NIFs | Zero matches source positions; 3,243 probe vertices change by exact float32 base-plus-delta | Tested project and preset only |
| Zero/probe TRI files | Byte-identical | Preset values did not limit morph availability in these builds |
| RaceMenu test | User-operated `Legs - 7B Legs`, mapped to restored `7BLeg_v2`; visible change reported and menu screenshot inspected | Another lower-body slider was nonzero; not isolated quantitative parity |
| Separate CBPC baseline | Effective files/logs checked; user reported working third-person secondary motion | No contact-collision or multi-engine acceptance |

## Gotchas

1. **Symptom: OSD dataset names turn into random printable text.** Cause: treating
   names as NUL-terminated or guessing an offset chain. Fix: length-prefixed names,
   uint16 record counts and packed 14-byte position records.
2. **Symptom: a TRI parser treats its header as unrelated version/mesh fields.**
   Cause: using another TRI family. Fix: follow the actual shape/morph hierarchy,
   signed-short components and per-morph multiplier in the pinned reader.
3. **Symptom: a menu slider exists but does nothing.** Cause in this collection:
   its local project data existed, but the bundled TRI lacked that name. Fix:
   rebuild from the intended project and compare both names and actual deltas.
4. **Symptom: an all-zero preset is assumed to export no morphs.** Cause: confusing
   NIF baking with TRI availability. Fix: inspect a real export; the two tested
   zero/probe TRIs were identical.
5. **Symptom: a plugin labelled AE fails to load.** Cause: the archive label hides
   an exact runtime ABI requirement. Fix: inspect plugin compatibility metadata
   and use a supported game/SKSE/plugin combination, not a bypass.
6. **Symptom: profile-local flags exist, but the game reads shared INIs.** Cause
   in the trimmed research instance: its bundled INI-mapping component was omitted.
   Fix: retain MO2's required `inibakery.dll` and check effective INI API values and
   virtual file hashes, not just files on disk. This is not a diagnosis for every
   MO2 isolation failure.
7. **Symptom: adding a physics engine gives no body motion.** Cause: missing
   weighted receiver nodes, missing skeleton nodes or mismatched mappings. Fix:
   establish the body/skeleton/one-engine baseline before adding contact or a
   second simulator; never let two engines drive the same nodes accidentally.

## Assets

No game meshes, extracted textures, presets, morph datasets, generated NIF/TRI,
third-party binaries, decompiled code or private dumps accompany this note. The
BodySlide outputs are built from CBBE's project data, and the vanilla body was read
from the game's own files, so both stay in the user's own install.
BodySlide/Outfit Studio (Ousnius and Caliente) and nifly (ousnius) are credited as
the public implementation references; their licenses remain their own. CBBE
(Ousnius and Caliente), XPMSSE (Groovtama), RaceMenu (expired6978), CBPC (Shizof),
CBBE 3BA (Acro748) and Faster HDT-SMP (DaymareOn) are separate dependencies with
their own permissions, not material relicensed by this contribution.

## Open questions

- Why the local bundled TRI and local authoring project had different morph sets.
- Individual runtime coverage of all 137 sliders and quantitative motion traces.
- Contact collision, full 3BA/FSMP integration and safe runtime ownership handoff.
- Generality across other mod versions, projects and outfits.

The separate [Bloodlines field note](../vampire-the-masquerade-bloodlines/longhair-outfit-proportions-from-skyrim-cbbe-3ba-source-data.md)
describes the later target-game investigation; it is not evidence that Skyrim
assets or native plugin binaries can simply be copied into another engine.
