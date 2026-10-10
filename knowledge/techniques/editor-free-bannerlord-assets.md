---
kind: technique
title: 'Editor-free assets for Mount & Blade II: Bannerlord: writing .tpac packages, skeletons and animation clips offline'
status: in-progress
game: "Mount & Blade II: Bannerlord"
games_also: ["Borderlands 2"]
game_version: "v1.4.8.119303 (Steam, Windows); client TaleWorlds.Native.dll 14,185,944 bytes, PE timestamp 0x6a732505"
platform: windows
engine: unknown
route: data
tools: ["Python 3.10 + numpy (own LZ4 and xxHash64)", "Ghidra 12.1.4 headless + JDK 21", "Blender 4.2 headless", "ilspycmd", "dotnet 8 SDK", "python minidump package", "dbghelp MiniDumpWriteDump"]
agents:
- Claude Code (Opus 5.5)
- Claude Code subagents (Sonnet 5.5)
humans: ["@theartur2000"]
date: '2026-10-05'
links: []
tags: [bannerlord, tpac, rdc, runtimedatacache, packing, load-time, hang, ik, skeleton, ragdoll, animation, clip, action-set, project-mbproj, bone-limit, hit-capsule, minidump, asset-pipeline, total-conversion, custom-race, quadruped]
---
# Editor-free assets for Mount & Blade II: Bannerlord: writing .tpac packages, skeletons and animation clips offline

> Bannerlord's asset packages (`.tpac`) and runtime caches (`.rdc`) can be written directly by a script, with
> the Modding Kit editor never opened. Over four days one project did this for textures, materials, static
> and skinned meshes, skeletons with ragdoll physics, skeletal animations, animation clips and their caches,
> then used it to put whole Borderlands 2 races and creatures on their own non-human skeletons. The formats
> were proven by byte-identical re-packs of the editor's own output and by recorded battles in the real game.
> Packing 34,000 assets into 26 packages was measured in the game (package phase 25.7 s warm / 280 s cold
> down to 5.6 s). Two newer fixes (clip partners, the hit-bone hang guard) and the hit-capsule refit are built
> and checked offline but were not yet run in the game: the "Not verified" section lists exactly which.

## When to use it
- You need many assets (hundreds to tens of thousands) and the editor's Resource Browser import is too slow,
  needs a mouse, or loses data (multi-take animation import, see gotcha 5).
- You want a skeleton that is not `human_skeleton` (a robot, a monster, a quadruped) with its own animations,
  and need to know the hard rules the client enforces by crashing instead of by error messages.
- You are debugging a native crash in `TaleWorlds.Native.dll` from a clip, skeleton or action-set file you wrote.
- You want to check your own format reading against a reference: every layout below was cross-checked by
  re-packing the editor's and the game's own files byte for byte.

## Setup
- **Game:** Mount & Blade II: Bannerlord v1.4.8.119303 on Steam, Windows 11. The Modding Kit (Steam tool, build
  `Win64_Shipping_wEditor`) is installed only as a source of ground-truth packages and an `editor` build of the
  native DLL to read; it was never needed to produce an asset in the end.
- **Native DLL pin:** all crash offsets and addresses below are for the client build
  `bin\Win64_Shipping_Client\TaleWorlds.Native.dll` of that version, 14,185,944 bytes, SHA-256
  `2A5E0E0B15513EBB7052D747A621B82C50EE834553EBA283B33BBBC33766E12A`. The editor build's addresses differ.
  After a game update, treat every `0x18...` address as stale and re-derive it.
- **Writers:** Python 3.10 with numpy. LZ4 and xxHash64 are small pure-Python implementations in the project's own
  code, so there is no native dependency. Textures use numpy-only block compressors (BC1, BC3, BC4, BC5,
  BC7 mode 6, RGBA8).
- **Reading the engine:** Ghidra 12.1.4 headless with JDK 21 on a COPY of `TaleWorlds.Native.dll` (Java
  GhidraScripts only, about 10 s per scripted query once the project is analysed). The client and editor builds
  differ: use the client build for crash offsets. The managed side was read with `ilspycmd` into a local scratch
  folder (never committed).
- **Managed module:** a normal C# submodule built with the .NET 8 SDK against the game's own assemblies, with
  Harmony (`Bannerlord.Harmony` from the Workshop, referenced and never shipped) for guards in front of native
  crashes. The asset side needs none of it.
- **Source art:** Borderlands 2 content was exported locally from the user's own install and converted by our
  scripts into FBX / glTF / PNG. None of that content, and no instructions to obtain it, is part of this note.
- **Layout of a module** (what the game reads): `<game>\Modules\<YourModule>\Assets\<folder>\*.tpac`,
  `...\RuntimeDataCache\<package guid>.rdc`, `...\ModuleData\*.xml` and `ModuleData\project.mbproj`. The game
  uses the `Assets` route (with caches) when both `Assets` and `AssetSources` exist, otherwise the
  `AssetPackages` route (data inline, no caches), which is how the Native module ships.

## Route and why
Four routes were tried in order. Only the last one scaled.
1. **Runtime assembly in C# (no package at all).** Cut a foreign mesh into rigid pieces and hang them on the
   human skeleton's bones at runtime. Worked for a first screenshot; seams at joints, no real skinning, no new
   skeleton, no new animations. Dead end for a total conversion.
2. **Drive the Modding Kit editor's GUI with UI automation** (Resource Browser clicks, dialog answering). It
   worked and produced valid assets, but each import takes seconds to minutes, needs the mouse and the
   foreground window, depends on editor prompts, and the multi-take animation import silently corrupts data
   (gotcha 5). An in-editor command bridge was built and dropped.
3. **Look for a command-line import.** There is none for assets: the editor's console command list has
   `export_meta_mesh_as_obj`, `pack_folder` and `compile_external_module_cache`, nothing for FBX, textures or
   animations. The compilers are internal functions of the editor build. One automatic path exists: when the
   editor (not the game) registers a module, it rebuilds every stale or missing cache entry from package data.
4. **Write the engine's own formats directly (chosen).** Seconds per asset, no editor, scriptable in bulk.
   It needs the formats, which were mapped in three layers: parse and re-pack the editor's output until
   byte-identical (what is stored), read the editor build of the native DLL in Ghidra (what each field means
   and what is validated), read the client build (what the game actually checks, which is much less).

Why not just patch the engine for the limits we hit (64 bones)? Static analysis showed the limit is a data
layout constant spread over about 140 functions; see "Engine limits" and gotcha 17.

## How the formats work (what we had to learn)
Everything here was derived from the editor's output, the Native module's shipped packages and the DLL; none of
it is TaleWorlds documentation. Layouts are given at the level the project's writers use.

### Packages (`.tpac`)
- **Container.** Magic `TPAC`, u32 version 2, 16-byte package guid, u32 item count, u64 metadata size. Then per
  item: type guid, item guid, u32 flag, name (u32 length + ASCII), a **record** (u32 byte count, then a
  type-specific body), an 8-byte xxHash64 of the record (seed 0), a u32 data-entry count with one 69-byte entry
  each (u64 absolute offset, u64 raw size, u64 stored size, owner guid, data-type guid, xxHash64 of the raw
  blob, u32 data-type version, u8 flag), and the dependency list (48 bytes each). Blobs follow the metadata.
  A stored size smaller than the raw size means an LZ4 block.
- **One item or many.** The editor writes one item per package (`<name>_tex.tpac`, `_mtl.tpac`, `_anm.tpac`,
  `<fbx>_geo.tpac`, skeleton `_geo.tpac`). Native ships about 150 packages holding about 40,000 items, in item
  guid byte order, blobs contiguous to the end of the file. Both are the same format: all 150 Native packages
  re-pack byte-identical from their parsed items.
- **Ids.** Every item has a guid; dependencies and references inside records (material to texture, mesh to
  material, clip to animation, animation to owner skeleton) name **item guids, never packages**.
- **The record hash is not checked on load.** Clips written with a stale hash loaded fine. But the hash is used
  as a cache key for clips and physics shapes, so a stale value keeps matching its cache.
- **Overrides work by name, not by guid.** Registering an item inserts it into a per-type map keyed by guid. A
  second item with an already-registered guid is dropped entirely and logged as `... already added from
  package ...`. A later module's item with the same name and type replaces the name entry and takes over the
  Native item's runtime object. References resolve guid -> item -> name -> current name winner, so a name
  override reaches referring items in other packages.
- **Registration order.** Items of a folder are sorted by name before registering, so which package an item
  sits in does not change who wins a name or guid clash.

### Runtime data caches (`.rdc`)
- File `RuntimeDataCache\<package guid>.rdc`, one per package, holding the heavy blobs: texture pixels, mesh
  vertex streams, optimized animation keys. Header `RDC0`, u32 0, u32 entry count, u64 metadata size
  (145 bytes per entry).
- Entry: owner guid, data id, data type, u64 offset, u64 raw size, u64 stored size, **u32 = the data type's
  version** (texture 0, mesh vertex stream 1, clip 2) whether or not the blob is compressed, a 64-byte hash block
  (up to eight u64: source hash, settings hash), a fixed `FA FA FA FA` marker, u8 = 1 only when the LZ4 copy is
  what is stored. Entries and blobs are sorted by (owner, id, type) bytes.
- **The game client does not validate or rebuild caches.** It looks entries up by (owner, id, type) and uses
  whatever is there: a stale cache loads as is; a missing one fails with `Unable to find data <owner>::<id>`
  (meshes: `Cannot read render buffers of mesh ...`). Only the editor build checks hashes and versions and
  rebuilds. Consequence: if you write packages yourself you also own cache correctness, and the game will not
  tell you when you got it wrong.
- Package data entries win over the cache: textures written with their pixels inline load without any `.rdc`.

### Textures, materials, meshes
- **Texture.** The package holds a record (source path, source file hash, size, mip count, format string,
  import flags, platform, a pixel hash) plus two small data entries (import settings with the usage string
  albedo / normalmap / specularmap / heightmap, and source file info). Pixels, largest mip first, sit in the
  cache. Formats in use: DXT1 diffuse and specular, DXT5 with alpha, BC5 normal, BC4 height, RGBA8 exact. No
  sRGB flag exists anywhere; colour handling is in shaders and the usage only steers compression.
- **Pixel hash.** The 8 "opaque" bytes in the record are xxHash64 of all mips with seed `0x41c64e6d`. The game
  never reads it; the editor needs it non-zero.
- **Material.** Flags list, vertex layout list (skinning, bumpmap, doubleuv), blend mode, shader guid, texture
  slots (0 diffuse, 2 normal, 4 specular), alpha-test reference, shader flags, 28 float parameters. Without the
  `skinning` vertex layout a skinned mesh renders black and frozen in bind pose.
- **Metamesh (mesh).** A record with per-submesh counts, bounding box, centre, radius, bone count and flags,
  plus data entries "mesh edit data" (positions, vertices, triangles, skin weights) and, in the cache, one
  "mesh vertex stream" per submesh (14 attribute streams, packed normals, half-float positions, QTangents,
  vertex-cache-ordered u16 indices). Native packed meshes carry the same blobs inline instead of in a cache.
- **Vertex welding follows the FBX's own index arrays**, not float equality: the editor merges corners only
  when the FBX normal, tangent and UV index arrays agree, so a layer without an index array never merges.
- **Animations from FBX.** One key per FBX frame; per bone the local rotation as a quaternion (largest
  component positive), root translation from the pelvis relative to its first frame. The engine takes the
  evaluated global transform of each node per frame, so pivots, pre-rotation and rotation order are honoured;
  an Euler-only reader is right only for FBX files that use none of those.

### Skeletons and their "User data"
A skeleton package holds one skeleton resource with two data entries.
- **Skeleton definition:** name, bone count, then per bone: name, parent index (-1 for the root; parents come
  first), local frame as four vec4 (three axes and an origin, relative to the parent).
- **User data (version 3):** skeleton type string (`human` = biped, `horse` = the quadrupeds, `other`) and per
  bone, in skeleton order:
  - a flag byte (the engine's name is `lowerbody`, see gotcha 20);
  - a **bone type** (`biped_*` for a human-type skeleton: 28 fixed names such as `biped_thorax`, `biped_item_r`;
    `quadruped_*` for horse-type skeletons; empty otherwise);
  - a **body part** (hit location: head, neck, chest, abdomen, shoulders, arms, legs, ...);
  - a mass;
  - two capsules (two points in bone space plus a radius, -1 = absent). **The first capsule is the ragdoll
    body, the second is the collision (hit) capsule** that weapons and missiles test against. They are
    independent: a bone can take hits and not ragdoll, or the reverse;
  - then the **joint list**: `d6` (ragdoll constraint with per-axis locked / limited / free and limits),
    `hinge`, and `ik` joints, each naming a child and parent bone and a frame.
- **Ragdoll build.** Every bone with a ragdoll radius above zero gets a body attached to its nearest ancestor
  that has one; then each joint creates a constraint. No joints: the corpse falls apart into loose capsules
  (ugly, not a crash). **No ragdoll body on the root bone: a null dereference when the agent dies** (read from
  the death path, see gotcha 15).
- **Agent movement capsules** come from `monsters.xml`, not from the skeleton.
- Native check: the three Native skeleton packages (human 28 bones, horse 32, camel) re-pack byte-identical,
  and so do all 34 skeleton entries of the human, cat, cow and dog packages for the data layout.

### Clips, actions and action sets
- A **skeleton animation** holds raw keys and an owner skeleton guid. A **clip** (`_anm.tpac`) references an
  animation and a key range and carries the gameplay settings. Clips are what action sets name.
- **Clip record.** After the name: duration, source range (start and end key, in the animation's key units; the
  editor's own resampling was about 12.5 keys per second, our single-take import writes one key per FBX frame),
  the source animation guid, four "step point" floats, a flag list, then a named
  **parameter list**, two action-name strings (**`blends_with`** and **`continue_with`**), and a dependency list.
  The first u32 of the record is a byte count, not flags.
  - Parameter entries by type: 0 displacement, 1 `quad_movement`, 2 `bip_mov_ik`, 3 blend, 4 mount change,
    5 hand switch, 6 particle. Entry sizes differ per type, so a parser needs a per-type size table. The
    runtime keeps only the **first two** entries of a clip; later ones are dropped at load with a log line.
  - `bip_mov_ik`: eight floats; value 1 is the distance covered in one clip cycle in metres (Native walk
    1.8 m in 1.4 s, run 3.0 m in 0.8 s); values 2 to 7 are per-foot step phases for foot IK.
  - Step points mean different things per action: foot steps on movement clips, the missile launch moment on
    ranged releases, and the item-switch progress as the 4th value on equip and unequip clips.
  - Combat clips name a **combat parameter** (hit window as clip progress, bow and crossbow release rules). A
    melee release without one never hits: the parser's default window start is 1.0, i.e. empty.
- **Clip cache ("Optimized animation").** Per clip, the animation key range re-encoded: smallest-three
  quaternions with per-bone bit depth, key-reduced with a tolerance of about 1 cm of chord at the bone's reach
  (80 percent to key reduction, 20 percent to quantisation), a pelvis channel, and a frame-to-key table. The
  cache's trailing runtime size is `blob size + 50 x bones + 90`. All 103 editor caches re-pack byte-identical;
  rebuilt ones match keys and headers and rotations within 0.006.
- **Action sets** (`action_sets.xml`): action type name -> clip name, a `skeleton=` attribute, optional
  `base_set`. A set's skeleton is what an agent actually uses for its visuals (not the skin's `skeleton=`).
  Same-id sets merge by appending, so a module file carries only the changed actions.
- **Monsters** (`monsters.xml`): every bone field (head look, pelvis, hands, weapon bones, spine chain,
  ragdoll check bones, IK end effectors, 50+ fields) is a bone **name** resolved by managed code on the action
  set's skeleton and handed to the engine as an index. A missing attribute inherits the **base monster's
  index**, which is a wrong bone on a different skeleton.
- **`project.mbproj`** decides which XML files the engine merges. **The engine only asks for canonical ids**
  (`soln_action_sets`, `soln_monsters`, `soln_skins`, `soln_monster_usage_sets`, ...). A file registered under
  any other id is simply never loaded and nothing is logged (gotcha 8). The native loader reads these files as
  raw XML: no XSL, no existence check. Only one skin file per module is read.
- **Same-named `.xslt` beside an engine file** is applied to the document merged so far BEFORE the file is
  merged. That is how a module adds rows to Native's usage sets (rider mounting rows for a new mount) without
  rewriting Native's rows. Rows merged by `@action` would overwrite Native's.

### What the engine assumes about a "human"
- **Bone order.** `item_holsters.xml` holster bones, the monster's item bones, hit-chain bone indices, the
  UI's human-set preview and C# `HumanBone` lookups all use **human_skeleton's index order**: index i is
  biped type i for the first 28 bones (0 abdomen, 11 thorax, 14/21 left/right shoulder, 18 forearm1_l, 20
  item_l, 27 item_r). A non-human skeleton that wants soldiers to behave must put its bones in that order and
  append extras after index 27.
- **Skin and face.** The face builder runs for every visual (battle, conversation, portraits, tableaus). It
  reads the first submesh of `face_meta_mesh` unchecked, applies every deform key, and indexes face, mouth,
  eyebrow and tattoo lists unchecked. A no-facegen race keeps every list at the human count with nameless or
  stand-in entries, a placeholder face mesh with at least one submesh, and empty `<deform_keys />`.
- **Release client versus editor.** Bone-count equality, clip owner equals action-set skeleton, null clips,
  action index -1: all of these are `assert`s in the editor build and nothing at all in the client. The client
  reads garbage instead of complaining.

### Engine limits: 64 bones
- 64 is a **layout constant**, not a validation. Bone counts are signed bytes in about ten structures (hard
  ceiling 127), the animation result is a fixed 0x1050-byte struct with 64 transform slots and two u64 per-bone
  masks (`1 << (bone & 63)`, so bone 64 aliases bone 0), stack arrays are `float[64]`, the ragdoll holds
  `bones_[64]`, and the GPU skinning shader has `groupshared float4x3 gs_bone_frames[64]`.
- A mesh's bone indices are **skeleton** indices; there is no per-mesh palette. A mesh using only bones 70 to 80
  still needs palette slots 70 to 80.
- The full site list for the client DLL is 139 functions and 1002 instruction sites; widening to 128 needs 52
  function rewrites (about 166 KB of machine code) plus shader work, estimated 70 to 100 days, redone every
  game update, with silent memory corruption as the failure mode. A side-channel for extra bones (reserve frame
  pool slots after the skeleton, write them each tick, give meshes a 64-bone window) was designed at 10 to 15
  days and never built. **What worked instead:** keep the agent skeleton at 63 or 64 bones carrying everything
  the engine reads by index, and make extra parts separate skeletons attached to bones.
- Rule used everywhere in our pipelines: **<= 64 bones, human biped order for the first 28, helper bones to
  fill gaps, extras after.** A source rig with 69 bones had its eight finger tips dropped.

### Hit capsules (the second capsule)
- Weapons and missiles test only the agent skeleton's collision capsules. A visible part with no capsule over
  it cannot be hit.
- First fit: radius = median distance of the bone's dominant vertices, capsule over 10 to 90 percent of the
  bone, only for bones with more than 30 vertices. Measured on 20 staged bodies: **31 to 67 percent of vertices
  (about 51 on average) inside any hit capsule**, so about half of every monster could be shot through.
- Refit (`hit_fit.refit`): radius = **92nd percentile** of the vertex distances to the whole bone segment
  (extended 8 percent past both ends), clipped to a minimum and to 15 percent of the body's bounding-box
  diagonal (and 1.5 x bone length), every bone with at least 12 dominant vertices and 3 cm of length gets one,
  and a second pass raises bones that still leave more than 10 percent of their own vertices outside (97th
  percentile, same cap). Ragdoll capsules, masses, joints and body parts stay untouched.
- Result on the same 20 bodies: **90 to 97 percent coverage** (mean 1.4 to 2.6 capsules per covered vertex, the
  largest radius 5 to 22 percent of the diagonal). Measured offline against bind-pose vertices only.

### Hit bones and IK joints
- A hit capsule on a bone is not enough on its own: when a blow plays no hit-reaction animation, the engine puts a
  small "flinch" IK on the bone that was hit, and its solver assumes that bone is part of an IK chain, i.e. has an
  `ik` joint (gotcha 30). The human skeleton's hit capsules all sit on bones with IK joints; toes, jaws and
  capes of a custom rig usually do not. Rule: every bone with a hit capsule needs an `ik` joint, or no `ik`
  joint may sit above it within 8 bones (or give the bone no capsule, or body part none).
- Find the offenders offline from the skeleton's user data (hit capsule present, no `ik` joint, an ancestor
  with one). On 14 of our skeletons that was 146 bones.

## Packing
One asset per package is what the editor writes, and it does not scale: the game's start-up cost is per file.
- **Cost.** At start-up the engine opens every `.tpac` in the module's `Assets` folder (header and metadata) and
  its `RuntimeDataCache\<package guid>.rdc` (header and entry table), whether or not that cache file exists. For
  34,265 packages that is about 63,000 file opens at 6 to 8 ms each when cold. Measured from the engine's own
  log between "Loading packages" and "Registering items": 25.7 s with a warm file cache, 280 s cold (Native, 150
  packages, about 1 s). The time is the file count, not the bytes (4.2 GB of packages, 2.2 GB of caches).
- **Layout.** Same format, many items per package: items in guid byte order, blobs contiguous to the end of the
  file, as Native ships them. We packed into 26 packages of about 256 MB (about 3.9 GB), grouped by kind and
  alphabetical runs (animations 1, meshes 17, textures 7, materials 1), plus 10 merged caches. Each merged package
  gets ONE cache named after its own package guid, holding every entry of its members' caches unchanged, sorted by
  (owner, id, type). Package guids are derived from the group name, so a repack keeps the cache names.
- **Why a merge keeps every lookup.** References between assets go by item guid, never by package (dependencies,
  material to texture, mesh to material, clip to animation). Registration sorts a folder's items by name, so which
  package an item sits in changes neither the name winner nor the guid clash. The "local" flag (a same-package
  guid lookup first) is not stored in the file at all. The cache is found only by its package guid and the
  entries inside by key.
- **Proof, offline.** The writer re-packs all 150 Native packages byte-identically from their parsed items; 77
  Native packages were split into one-item packages and merged back through the same code, byte-identical. For our
  set a verifier reads every merged package and cache back and compares each loose item, data entry and cache entry
  with the original, plus the layout rules: 34,265 packages, 35,948 assets, 108,871 data entries, 28,720 caches,
  0 problems.
- **Result, measured in the game (2026-10-05).** Package read plus register 5.6 s, of which about 5 s is override
  registration that packing does not touch; launch to main menu about 65 s. The log's error and warning counts
  equal the baseline run: 0 missing data or meshes, 86 "Unable to find item to add dependency" (unchanged), 4,581
  "Overriding item" (unchanged).
- **Keep the module packed.** Never leave a loose copy in `Assets` (it loads next to the packed one). Our installs
  write to a loose set kept outside `Assets` (the game never reads it) and then repack only the groups whose
  members changed (usually one to three groups), verify, and copy over; a revert command restores the loose
  layout. The editor sees only the merged packages, so unpack first if it is ever needed again.
```
python tpac_pack.py scan | pack | verify | status | repack | unpack | native-check | logcheck
```

## Build steps
A condensed session. `bl2sdk.py` is our CLI; it stages everything and touches the module only on `install`.
```
cd scripts
python bl2sdk.py texture my_gun_d.png               # suffix picks usage: _d albedo, _n normalmap, _s specular, _h height
python bl2sdk.py material my_gun --diffuse my_gun_d --normal my_gun_n --static
python bl2sdk.py mesh my_gun.fbx --name my_gun --material my_gun      # skinned when the FBX has a skin
python bl2sdk.py anim my_run_take.fbx                                   # one take per FBX file
python bl2sdk.py skeleton rig.gltf --name my_skeleton --type human      # <= 64 bones, root gets a ragdoll body
python bl2sdk.py clips my_clips.txt --single                            # clips on the staged animations
python bl2sdk.py clip-cache "my_clip_*"                                 # their runtime caches
python bl2sdk.py verify true-race my_race_stage                         # NaN, bone-count, capsule, joint rules
python bl2sdk.py install --dry
python bl2sdk.py install                                                # game closed; backup + manifest
python bl2sdk.py revert                                                 # undo the last install
```
- A whole race is one script run (`true_race.py <race>`, about 7 minutes after the animation lookup is
  cached); a creature is `true_creature.py build|verify|gen`. Each builds skeleton, mesh, material, textures,
  animations, clips, caches and the XML (action sets for every suffix, monster, race, troop), stages them, and
  runs its validators before anything is installed.
- `install` refuses to run while the game is running, copies stage files into the module with a backup and a
  manifest, and `revert` restores. Install also refuses a stage whose `project.mbproj` ids are not canonical.
- Clip rules the writers enforce, all found by crashes: movement-slot clips carry `bip_mov_ik` (decided by the
  action slot, not the clip name); quadruped gait clips carry `quad_movement` as the first parameter entry;
  combat, equip and defend clips are written in **copy mode** (the Native clip of the same action is copied and
  only animation, source range and blend pairing come from the foreign sequence); every clip name is at most 63
  characters; `blends_with` and `continue_with` are preserved.
- The partner rule, simplified from our own checker:
```python
def partner_problems(sets, clips, native_partner, native_counterpart):
    """sets: {set id: {action type: clip name}}. A clip modelled on a Native clip that has a partner must
    keep one, and every action it names must exist in every set that plays it."""
    bad = []
    for set_id, actions in sets.items():
        for action, clip_name in actions.items():
            clip = clips.get(clip_name)
            if clip is None:
                bad.append((set_id, action, "missing clip")); continue
            if native_partner.get(native_counterpart(set_id, action)) and not clip["blends_with"]:
                bad.append((set_id, action, "no partner"))
            for field in ("blends_with", "continue_with"):
                if clip[field] and clip[field] not in actions:
                    bad.append((set_id, action, f"dangling {field}"))
    return bad
```
- Run the checker with every build that writes clips. On the project's 14 races it reported 6,202 actions
  without a partner before the fix and 0 after, on staged data.

## Verification
- **Byte-identical re-pack is the main oracle.** Parse every file the editor or the game wrote, rebuild it
  from the parsed fields, compare bytes. Results: 161 of 166 editor textures identical (the 5 differ only in
  how one tiny blob was LZ4-packed); all 103 editor clip caches; 95 of 95 mesh edit blobs; 67 of 71 metamesh
  records; Native's human, horse and camel skeleton packages; all 150 Native asset packages. Where a file does
  not re-pack (our mesh welding, the editor's stack garbage in two vec4 fields, our simpler key reduction), the
  differences were measured and bounded (positions identical, normals within 2e-7 except welded vertices,
  rotations within 0.006).
- **Decode and look.** Textures decode to PNG, meshes to OBJ, skinned meshes render with a clip frame. Every
  picture was viewed at full size, not trusted from a number.
- **Validators before install** (`verify true-race`, `true-creature`, `creature-stage`, `registration`): reject
  every data-side source of NaN (zero or negative clip duration, source range past the animation, non-finite
  parameters, step points outside range, bad `bip_mov_ik`, non-unit quaternions, bone-count mismatches,
  non-orthonormal bind frames, zero-mass ragdoll bodies, joints without bodies, weights not summing to 1,
  monster bones missing from the skeleton, non-canonical project ids). Deliberately broken variants are each
  rejected.
- **In-game, silent, recorded.** A test harness spawns the content in a custom battle or campaign encounter,
  records the game window (video only, game audio muted), cuts contact sheets and reads the log. A probe samples
  per-agent clip names and foot positions. The first 1:1 race (the Loader) passed two full battles with no
  crash, upright, with correct gait, after the movement and face fixes; 13 variant skins x 2 passed in one run
  (0 crashes, same peak memory as a plain 1:1 battle); a quadruped skag with riders galloped without a crash once
  registration was canonical.
- **Crash triage.** Every crash was handled the same way: Windows Error Reporting event for the faulting
  offset, `%LOCALAPPDATA%\CrashDumps\*.dmp` read with the python `minidump` package (registers, the request
  struct, stack return addresses), then Ghidra on a copy of the DLL for the function at that offset, then a data
  or C# fix, then a validator rule so it cannot come back. For "Faulting module unknown, 0xc0000005": the
  exception context in the dump is the WER handler, so scan the stack for the fault address; WER keeps 256 bytes
  of code around it, enough to decode by hand and match a managed method. Often it is a vanilla managed
  `NullReferenceException` inside a native callback, not your native crash.
- **Hangs are not crashes.** A frozen game writes no crash report. Two ways to get a dump of the live process:
  an external `MiniDumpWriteDump` (Task Manager's "create dump file" does the same), and an in-process watchdog
  thread that notices the main thread has not ticked for 30 s and writes ONE dump of its own process (flags:
  thread info, indirectly referenced memory, process thread data, unloaded modules, memory info; stacks and what
  they point at, no heap, tens of MB), on a short-lived thread with a join timeout. Read it with the python
  `minidump` package: take every thread's registers and stack, find the thread that is busy in native frames,
  and note which thread the main thread is waiting on (gotcha 30 was found this way).
- **Probe artefacts.** Off-screen agents' bone frames are stale or NaN (the skeleton is not ticked while
  culled). Filter samples where both feet report the same point or five consecutive samples are identical
  before believing a "foot snap" number.

## Gotchas
Each is symptom, cause, fix. Addresses are for the client build pinned in Setup.
1. **A module texture with a Native item's guid never shows.** Cause: guid clashes are dropped, not
   overridden (log: `already added from package`), and Native loads first. Fix: keep the Native NAME, use a NEW
   guid. Name overrides replace the name entry and rebind the runtime object.
2. **Name-overriding a Native material or texture changes nothing on town houses.** Cause: not fully
   explained: by the registration code a name override should reach the house's materials (they live in other
   packages), yet 62 material overrides gave no visual change. Fix that worked: override the **metamesh itself
   by name** (scenes reference meshes by name): new item guid, the Native record with the material guids
   swapped, all LODs, edit data and vertex streams copied inline exactly like Native's packed packages. Proven
   in a town scene, then applied to every settlement building.
3. **`Unable to find data X::Y` or `Cannot read render buffers of mesh` at load.** Cause: the cache entry is
   missing and the game never rebuilds. Fix: write the cache with the package, key it (owner, id, type), sort
   the entries, store the data type's version in the u32 (not 0 for everything) and set the LZ4 flag only when
   the stored copy is compressed.
4. **Crash at first agent spawn after rewriting a clip.** Cause (seen once, mechanism not traced): a rewritten
   clip got new ids, leaving the old cache, named after the old package guid, next to a clip of the same name.
   Fix: a rewrite keeps the package and item guids so the cache name stays valid.
5. **Every animation plays the same death pose.** Cause: the editor's multi-take FBX import stores the first
   take's keys under every take name. Fix: one take per FBX file (or one combined take addressed by key ranges,
   which then needs its own care, see 6).
6. **Soldiers slide with frozen feet, later drift and snap each cycle.** Cause, in three steps. Locomotion baked
   fully in place froze the feet (a clip on Native's own run animation cycled fine, so the clip files were not at
   fault); pelvis travel matched to the stride unfroze them. A combined multi-sequence take then drifted (baked
   travel of 1.35 m/s over a 1.3 s cycle) and snapped back every cycle. Decoding Native's run and walk clips
   showed no travel in their root channel at all. Fix: clips in place, one single-take file per sequence, and
   `bip_mov_ik` value 1 = metres per cycle, measured as the planted ankle's backward speed times the duration;
   turns get 0.
7. **Crash at the first walking agent, `+0x759c47`.** Cause: the movement-set code reads each movement slot's
   clip `bip_mov_ik` entry with no null check (reads distance from address 8); clips written as plain clips
   have none. Native gives the entry to every clip in slots forward through rotate. Fix: decide by action slot,
   not clip name: every clip used in a forward, backward, strafe or rotate slot of any movement set is a
   movement clip. Do not put an idle clip in a movement slot (distance 0 makes every direction speed 0).
8. **Crash while spawning own-skeleton quadrupeds, `+0x760967`, then `+0x636b6e`, even for an exact copy of
   Native's horse set on Native clips.** Cause (very probably; the fix changed several things at once, see
   Not verified): our `project.mbproj` entries used made-up ids
   (`soln_<mymod>_action_sets`, ...). The engine only merges canonical ids, so our sets and usage set were never
   loaded and the monster named sets that did not exist. About a day went into native-RE theories about pace
   tables (including a plausible "lookup miss on pace 1" story) before this was found by reading how two big
   mods (The Old Realms, Shokuho) register theirs. Fix: canonical ids only, append your sets to the
   engine files under those ids, add the one genuinely new file (usage sets) with its own line, and put a
   validator in `install` that rejects non-canonical ids. At runtime log whether each monster's action set and
   usage set exist (`IsValid`) at every mission start. Lesson: before reverse-engineering a crash that involves
   a new id, prove the file loaded.
9. **Quadruped gait clips: `quad_movement` entry.** The movement code reads it unchecked. Copy the Native
   horse clip's entry for the same action, as the FIRST parameter entry (the runtime keeps only two), with your
   own loop displacement. Not sufficient alone (see 8), and Native has a few clips (backward walk, dash, one
   jump end) that lack it.
10. **Crash at melee contact, `+0x66d5a9`, and in AI melee decisions.** Cause: melee release, blocked and
    quick variants are looked up in a weapon-balance table keyed by clip index; a clip not registered in it
    yields a null entry. Registration happens when a clip's paired-animation string names the clip itself (175
    Native clips do). Copy mode had cleared the string, so none of the 284 table actions had a registered clip.
    Fix: set the paired string to the clip's own name.
11. **Process dies at startup in "Initializing items", ucrtbase `0xc0000409`.** Cause: after fix 10, the
    registration copies the clip name into a 64-byte buffer with `strcpy_s`; a name of 64 characters or more
    fails fast (420 of our clips were 64 to 78). Native's longest is exactly 63. Fix: every clip and animation
    name at most 63 characters (abbreviate systematically, add a hash tail for uniqueness); the validator
    rejects longer.
12. **Crash when an agent on a custom skeleton raises a shield, `+0x669cc5`.** Cause: the engine requests the
    defend clip with a blend factor of 0.5 whenever the off hand holds a weapon that can block ranged (every
    shield), then looks up the clip's `blends_with` action unchecked; -1 reads a heap word as a clip index. Native
    `defend_*_down` clips name their `_up` twin (345 Native clips have a partner: defend, ready, release,
    blocked, lance, brace). The writer copied Native records but set `blends_with` to empty on every clip (one
    line, 6,384 defend clips affected). Fix: always preserve `blends_with` (and `continue_with`); the
    target must be an action of every set that plays the clip; run the partner check (0 problems) before
    install. Proof: two minidumps with the same stack, request on a `..._shield_..._down` action, factor 0.5,
    partner -1. **Not run in the game yet** (see Not verified).
13. **Crash about 7 seconds after a custom race spawns, `+0x584fec`.** Cause: the face builder applies the
    skin's deform keys to a face mesh that has no morph targets (a placeholder), reading half-floats near
    address 0. Fix: empty `<deform_keys />` on every skin of a no-facegen race; keep the other lists at the
    human count.
14. **NaN bone frames, eye position NaN, damage `int.MinValue`, only on AI agents.** Cause (inferred from the
    code, then confirmed by the data fix): the monster's `spine_lower_bone` was the skeleton root, which has no
    joint; the anim-system init walks from the head-look bone up to that bone reading a per-bone record with
    index -1 and no check, producing garbage look-rotation shares. Fix: no bone from `head_look_direction_bone`
    down to `spine_lower_bone` may be the root or lack a ragdoll joint to its parent; give the rig a real
    chain (pelvis, spine, chest, neck, head) with joints. Measured: 15 of 84 eye-position samples were NaN before
    the fix and 0 of 84 after, with sane damage; forcing bone-frame updates on culled agents had not helped,
    which is how it was shown to be data and not culling.
15. **A skeleton whose root bone has no ragdoll capsule.** Read from the death path: once an agent ragdolls the
    code calls bone 0's ragdoll body with no null check. Fix: always a ragdoll capsule on the root. (Reasoned
    from the code, not reproduced as a crash.)
16. **Holstered items on the wrong bone, human-index UI code reading past the bone array, hit chain
    misaligned.** Cause: engine and managed code resolve holsters, item bones and melee hit bones by
    **human biped index** and apply that index to the agent's own skeleton. Fix: bones 0..27 in human biped
    order (11 thorax, 20 left item bone, 21 right shoulder, 27 right item bone), extras after 27, and each hit
    shoulder an ancestor of its hit bone. Skeletons under 28 bones read past the array.
17. **65+ bones load and then corrupt memory.** Cause: the layout constants listed under Engine limits; the
    client has no check (the editor asserts). Fix: do not exceed 64; split extras into attached part
    skeletons. Do not attempt a binary patch (estimates in Engine limits). (From static analysis; a 65-bone
    skeleton was never loaded on purpose.)
18. **Monster bones wrong, or weapons in the wrong hand, on a non-human race.** Cause: a missing bone
    attribute inherits the base monster's bone index. Fix: name every bone field explicitly (55 on the human
    monster), or do not derive from `human`; make the validator reject names missing from the skeleton.
19. **Managed `throw` in the campaign UI, map or conversations for a custom race.** Cause: managed code builds
    action-set names as `as_<monster>[_female]<suffix>` (`_warrior`, `_facegen`, `_map`, `_map_with_banner`,
    `_poses`, settlement suffixes) and throws on a missing one. Fix: generate the whole suffix family for each
    race (copies of the race's warrior set are enough); 88 sets with 7,649 actions in our case.
20. **Feet cross or slide while aiming.** Cause (hypothesis; the rule has been applied since the first 1:1 race
    and feet crossing measured 1.2 percent on the first 1:1 Goliath, but it was not A/B tested): channel 1
    (aim, release, reload, defend) can drive every bone except those with the skeleton's `lowerbody` flag; the
    first rig had the flag on bones with a human analog only, so the thigh parents and heels followed the
    full-body aim clip. Fix: set the flag on the root and on every bone whose path to the root runs only through
    hip and leg bones. There is no per-clip bone mask.
21. **No damage from AI with new combat clips, or weapon swaps undone.** Cause: plain clips on attack, aim and
    equip actions: no combat parameter (empty hit window), no step points (item switch at 0), no flags such as
    `keep` on ready clips. Fix: copy mode from the Native clip of the same action (parameter, flags, sound,
    blend times, follow-up action, step points), keeping only animation, range and pairing from the new
    sequence; fit the contact frame of a melee swing inside the combat parameter's window; use a short motion
    cut to the Native duration for equip.
22. **A clip on the wrong skeleton plays garbage or crashes.** Cause: the client has no check on bone count or
    owner skeleton. Fix: keep every clip on its own skeleton; Native clips cannot drive a custom skeleton whose
    bone order or parents differ (measured: median 7 to 28 degrees of bind rotation, up to 175).
23. **About 1 in 3 battles crashed at deployment end, `+0x6feb3f`.** Cause: our own probe called
    `GetActionAnimationName` with action index -1 (`act_none`); the native side skips every check for -1 and
    indexes a table with a heap word. Fix: never call action-indexed APIs with -1; check `Index >= 0`.
24. **Riders float 0.45 m above a custom mount's back, legs straight.** Cause: the rider plays the same action
    name as its mount and rider clips are absolute from the mount's origin; `rider_sit_bone` does not lift or
    lower the rider. Fix: base the mount on the horse sets (horse rider clips seat the pelvis at 1.69 m) when
    the creature's back is at horse height, not on the camel's.
25. **Quadruped creature troops crash in many places, `+0x6f45a6`, `+0x6fca17`, `+0x6a1004`.** Cause: Native
    builds a non-humanoid agent only from a horse item; a troop on a quadruped monster goes through
    character-only steps (weapon component null at agent +0xad8, no facial controller past the quadruped anim
    object, conversation tableau reads the leader as humanoid, AI target scoring reads the target's weapon
    component). Fix: C# guards (skip the wield call, `SetSetupMorphNode(false)` and no voice for non-humanoid
    skin builds, an empty weapon component, a humanoid stand-in in conversation tableaus), or avoid the path by
    letting the creature be a mount with an invisible rider.
26. **Crash at module load, `+0x730550`.** Cause: a `project.mbproj` entry pointing at an XSL-transformed or
    non-existent file. The native loader reads these files as raw XML. Fix: real XML files that exist; use an
    `.xslt` only beside a canonical engine file (see "same-named .xslt").
27. **Builds took an hour, or ran out of memory.** Cause: the animation lookup rescanned every package for each
    clip; and a 2048 x 2048 DXT1 encode with numpy needs about 1 GB per process. Fix: index packages once per
    process; run texture builds in small batches (one process per four textures) while the game is running.
28. **34,000 small packages: start-up of 26 s warm, 280 s cold.** Cause: the game opens every `.tpac` and, for
    `Assets` packages, its cache file at start-up, missing or not (about 63,000 file opens at 6 to 8 ms cold
    each). Native ships 150 big packages. Fix: see Packing: 26 multi-asset packages plus 10 merged caches named
    after the merged packages; the loose originals move outside `Assets`. Measured in the game: 5.6 s. Never also
    leave a loose copy in `Assets`.
29. **Hit capsules covering half the mesh.** See Hit capsules; the median radius fit was the cause, the 92nd
    percentile refit the fix. Measure coverage with a script, not by looking.
30. **The game freezes (not a crash) when a jaw, toe, heel, cape or claw is hit.** Symptom: frame frozen, CPU
    busy, no crash report; a watchdog sees the main thread stuck with an empty managed stack. Cause (from a
    minidump of the frozen process): the main thread spins in the engine's parallel-for, waiting for the
    parallel animation update; one worker thread never finishes its chunk. When a blow plays no hit-reaction
    animation, the engine's blow handler posts an animation event with the blow's bone, and a helper walks up
    from that bone past bones whose body part is none, shoulder or arm and puts a small hit IK (chain length 8)
    on the bone it stops at. The IK solver then walks from the last chain bone that has an IK joint up to the
    target, following parent indices. With no IK joint on the hit bone the start is bone -1, and the parent of -1
    reads back as -1: an endless loop on a worker. The worker's registers showed bone -1, the target bone (jaw,
    index 28) and, in the skeleton object, our skeleton's name. Native bones with hit capsules all have IK joints
    (toes have no capsule); on our skeletons jaws, toes, heels, capes, claws and robot arms had capsules without
    IK joints (146 bones on 14 skeletons). Functions named in the dump (client build 1.4.8.119303, image
    addresses): `rgl_parallel_for` 0x1801f2de0, blow handler 0x1805ff470, hit-impulse IK 0x1805f5de0, chain-5 IK
    solver 0x180768b60. Fix, data: give those bones IK joints, drop their hit capsules, or set their body part to
    none, when the skeleton is built. Fix, runtime (what we installed because the skeletons were already
    installed): a Harmony prefix on `Agent.HandleBlow` that remaps the blow's bone to the nearest safe ancestor
    (jaw to head, toe to foot, cape to spine) before the engine handles it, from a table generated from the
    skeletons; damage and body part are already decided at that point. Regenerate the table after any
    skeleton change. **Guard built and compiled, not yet run in the game.** The same freeze had also appeared in
    three cavalry fights with couched lances (riders' feet have toe capsules); that link is a fit, not proven.

## Not verified
- **Clip partner fix** (gotcha 12): staged and checked offline (0 problems on all staged clips, 4,830 clip
  packages differ from the installed ones in exactly the `blends_with` string); **not installed and not run in
  the game**. Unknown: how the engine looks when it blends 50 percent of a BL2 `_down` clip with its `_up` twin
  (a frozen or odd pose is possible; the fallback is to point the partner at the clip's own action), and
  whether release and ready clips with twins behave differently now that they have partners. The crash
  analysis itself rests on two minidumps and static reading, not on a deliberate repro.
- **Hit capsule refit:** coverage is measured offline on bind-pose vertices. Not run in the game: time to kill
  with more and fatter hit bodies, and how the engine behaves with radii up to 15 percent of the body diagonal.
- **Packing:** measured in the game once (5.6 s, same error and warning counts as the baseline). Not measured:
  the cold-cache time after packing (only the warm run was timed), and long campaign sessions with the packed
  set; the 4,581 "Overriding item" lines were unchanged but not examined one by one.
- **IK hit guard** (gotcha 30): the dump analysis and the code path rest on registers, the skeleton name and a
  decompile; the guard is compiled but **not yet run in the game**. Unknown: whether every route that posts the
  hit animation event goes through the patched method, whether the remapped bone changes where hit reactions
  appear, and whether the lance-cavalry freezes are the same bug.
- **Overrides:** that a metamesh override with inline vertex streams works was proven in a town scene; the
  reason the earlier material-name overrides had no effect was not found (gotcha 2).
- **Quadruped crash history:** the final working setup changed registration, set contents and usage handling
  at once; which single change removed crashes 4, 4b and 4c was not isolated. The native-RE explanations in
  our notes for those three were built on files that were never loaded and should not be trusted.
- **Skeleton details:** the `lowerbody` rule (20) was never A/B tested, prebaked-animation entries for custom
  clips were not tried, and the code path that picks the missile start point was not traced (measured instead:
  missiles leave from the eye position on every skeleton, human 1.9 m, 1:1 races 1.7 m). Which of the two import-settings bytes is "do not compress" and which "no
  mips" was never separated. Texture `--inline` packages and BC7 beyond mode 6 are untested in game.
- **Bone-limit options** are estimates from static analysis. No 65-bone skeleton was loaded on purpose, no
  patch was written, the side-channel design was never built, and the attached part-skeleton plan is untested.
- **No other game version:** everything is v1.4.8.119303. Offsets are stale on any update. Multiplayer and
  anti-cheat were never involved (single player only); do not assume any of this is safe there.

## Credits
- **TaleWorlds Entertainment** for Bannerlord and the Modding Kit. Every format here was reverse-engineered from
  files and binaries the user's own install holds; nothing from the game is included.
- **TpacTool** (szszss, MIT) showed that `.tpac` is a readable container and had no writer; our own reader and writer
  were written from the editor's output.
- **The Old Realms (TOR)** and **Shokuho** were decompiled locally to see how large total conversions register
  action sets, usage sets and mounts: that is where the canonical-id finding and the rider-rows-by-XSLT pattern
  came from. Nothing from them is copied.
- **Harmony** (Andreas Pardeike) and the **Bannerlord.Harmony** module (BUTR) for the managed guards.
  ButterLib, UIExtenderEx and MCM were studied and not adopted.
- **Ghidra** (NSA), **ILSpy** (`ilspycmd`), **Blender**, and the python **minidump** package, for reading the
  engine, the managed code, converting source art and reading crash dumps. **LZ4** and **xxHash** (Yann Collet)
  for the compression and hashing the formats use. **MinHook** was considered for a native patch and not used.
- **UE Viewer (umodel)** for the Borderlands 2 export on the user's own machine.
- Written up by Claude Code (Opus 5.5) with Claude Code subagents (Sonnet 5.5) from the project's journal, for
  the human credited in `humans:`.

## Seen in
- A Borderlands 2 total conversion for Bannerlord (races, creatures, bosses on their own skeletons): Loader,
  Goliath, Nomad, Marauder, Psycho, Handsome Jack, Claptrap, Skag, Varkid, Stalker, Spiderant, Bullymong and
  flying bosses. Not published.

## Open questions
- Does the shield-block partner fix hold in a long campaign fight with many shield users? What does a 50 percent
  blend of two BL2 clips look like?
- Can `monster_usage` ids be extended further (a sixth usage set) without touching rider rows in `human`?
- Can the engine's hit-IK helper be disabled or given a safe default for bones without IK joints (a data flag),
  instead of remapping the bone in managed code?
- Which engine function computes the missile start point (measured to be the eye position, not traced)?
- Is the side-channel design for more than 64 bones (frame pool reservation plus mesh windows) workable, and
  would an agent with an attached part skeleton animate it in step from C#?
- Packing: what is the cold-cache start-up time now, and do smaller groups than 256 MB load faster?
