---
kind: game
title: "Every Space Marine 2 class on one soldier armour constructor, and glTF-to-USF rebuilds in minutes instead of an hour"
game: "Warhammer 40,000: Space Marine 2"
games_also: []
game_version: "Steam build 25799387 (Patch 15.1, Oct 2026). Mod Tools app 3856330: game-folder ModelConverter v13.0.0, Mod Tools ModelConverter release + ToolsSource v14.0.0, UsfExporter, CDTConverter"
platform: windows
engine: unknown
route: asset-only
tools: ["Saber SM2 Mod Tools (ModelConverter, UsfExporter convert_tpl.py, CDTConverter)", "ModelConverter rebuilt from Saber's GPL ToolsSource (.NET 11 preview SDK, offline, against the shipped SharpGLTF/Newtonsoft DLLs)", "Python 3 (json, hashlib, struct)", "PowerShell build scripts"]
anti_cheat: "EasyAntiCheat. Everything here uses Saber's official mods folder (client_pc/root/mods), which flags the session 'Mods Detected' (private lobbies, separate progression). No injection, no EAC interaction, PvE only."
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-29
links: []
tags: [space-marine-2, saber, swarm-engine, tpl, usf, gltf, modelconverter, usfexport, constructor, armour, customization-library, build-speed, incremental-build, byte-identical, shader-cache]
---

# Every Space Marine 2 class on one soldier armour constructor, and glTF-to-USF rebuilds in minutes instead of an hour

> All seven playable classes' armour was merged into the soldier constructor tpl, so any class can wear any piece
> while each class still sees only what it should, with its own animation set, cloth and jiggle physics kept. The
> build runs in game (several versions played), with an open shader crash on the Techmarine tab and armoury cloth
> issues on two classes. The second half is how the 62-minute glTF -> USF ModelConverter step for that 8.4 GB model
> was cut to 5-10 minutes, two ways, both proven byte-identical to the stock converter's output. Builds on
> [the models note](sm2-models-tpl-format-modelconverter-and-textures.md) (tpl format, round trip, shader cache,
> per-class visibility) and [the foundations note](sm2-modding-foundations-paks-tools-and-crash-triage.md).

## Setup
- Steam build 25799387 (Patch 15.1). Re-export every retail class constructor after a patch: Patch 15 changed them.
- Class -> retail constructor: Tactical `cc_sm_constructor_soldier`, Assault `_raider`, Vanguard `_berserk`, Bulwark
  `_tank`, Sniper `_sniper`, Heavy `_support`, Techmarine `_engineer`. `_medic` (library section `PVE_PVP_MEDIC`) is a
  stub with 27 objects and a 12-line section, not a class: skip it.
- Starting point: a soldier constructor that already carried Tactical + Assault + a Tactical-clone class (the merge
  described in the models note).
- Machine for the timings below: 32 GB RAM, glTF and USF on a 7200 rpm HDD, pagefile on a SATA SSD.
- Fast-build parts: Python 3 for the splice; the .NET 11 preview runtime for the rebuilt converter.

## Route and why
Asset route, glTF round trip (models note, route 1): export each retail class constructor to glTF, merge them into
the soldier glTF, convert, export, ship the tpl family plus the edited library and class files.

- **Why one tpl:** library items bind to tpl objects BY NAME inside the tpl the class loads, so a piece can only be
  offered to classes whose constructor contains it. Copying pieces into seven constructors means seven ~1-hour
  rebuilds per change. One shared tpl turns cross-class armour into library edits.
- A published third-party mod does the same for every class but switches all classes to one animation set and
  deletes cloth/jiggle from the class files. We kept each class's own `animSet`, cloth and jiggle; that is why the
  physics and library work below exists.
- Build speed: the round trip of an 8.4 GB USF took ~90 min per mesh change (62 convert, 13 export, rest post +
  pack). Options checked: more RAM (removes the paging only), stripping the glTF (not measured; every dropped object
  changes the tpl), hidden incremental switches in the tools (none: ModelConverter's whole CLI is `--no-skin`,
  `--keep-tangent-orientation`, `--map_mode`, `--install_lwi` plus positional paths; UsfExport has no merge-into-tpl
  mode and its `--help` hangs; CDTConverter takes ~1 s). Chosen: splice changed groups into a cached USF, and a
  low-memory rebuild of the converter from Saber's own source for full rebuilds.

## How the game works (what we had to learn)

### What merges cleanly between class constructors
- Skeletons match; the only extra bones are namespaced `*_cdt` collision nodes. Inverse bind matrices are identical
  across all skins in one file.
- Names shared with the soldier tpl (raider 533 of 742 objects, tank 465/623, support 343/624, berserk 256/559,
  sniper 251/501, engineer 148/372) do not mean the same mesh: torso fillers differ per constructor. Dedupe by
  geometry + material; after that the real conflicts were 12 (Vanguard), 5 (Bulwark), 8 (Sniper), 24 (Heavy) and
  7 (Techmarine) groups. Rename those with a class prefix and rewrite that class's library sections and physics
  entries from the same rename map.
- ~528 jiggle / servo-arm bones had to be grafted into the soldier `ROOT` tree. They animate because each class's own
  jiggle, damper and cloth entries came along in its class files (the models note's grafted-bones rule).
- Result size: `.tpl_data` 985 MB (retail soldier ~511 MB, class constructors 291-526 MB), 15,916 objects (ids are
  int16), 19,605 splits, 1,277 skin joints; the library grew from 1.9 to 4.3 MB (~1,450-2,000 hidden names per
  section). No hard limit was hit.
- **Skin joint ids above 1023 work.** Retail constructors top out at 659; the third-party one-constructor mod ships
  1,246; ours reaches 1,276 and loads and renders. The 30 joints above 1,246 were not checked one by one.
- Memory: in missions every class `.cls.resource` now links only the soldier tpl, so mixed squads load less (a
  three-class squad went from 1.26 to 0.99 GB; an all-Tactical squad pays +528 MB). In the lobby the armoury dummy
  factory's `.sso.resource` `linksTpl` **preloads every linked tpl even if no factory entry names it** (~2.5 GB of
  retired class tpls): prune it to the tpls the entries use.
- **One tpl has one `.cdt` and one `.tpl_markup`.** Per-class hit hulls are lost (Techmarine loses its 9 servo-arm
  hulls; Vanguard/Sniper/Heavy hulls differ by up to 0.38 m); markup `objectInfos` allow one entry per object name;
  the markup's `materialCustomizations` must list every group the classes use (`ANTENNA`, `MANIPULATOR`, `VANITY`,
  `JUMPPACK` were missing; without them those parts lose paint customization, no crash). The armoury doll's foley is
  keyed by tpl name (`ssl/view/character_view_controller_doll_type.sso`), so every class now gets the soldier sound.

### Library rules (`ssl/body/customization/character_customization_library.sso`)
- Per-class visibility via `isHidden` regions as in the models note, plus these:
- **Shared items become per-class copies with the same uid** (a pattern retail itself uses for one pre-order set),
  so each class's copy lists only its own meshes; 247 items were split this way.
- **Keep unowned what retail draws unowned.** The Assault/Bulwark power fists (toggled by
  `prop_power_fist_customizer_by_melee_state`) and the Heavy's 17 backpacks, feed tubes and connectors (toggled per
  weapon by the blueprint `MARINE_BACKPACK_TUBE_FIREARM`) must never go into a hidden region; hidden, they never come
  back.
- **`STORY_<CLASS>` sections are not yours.** They drive the campaign ally NPC marines
  (`npc_marine_pve_<c>_client.cls`), which load `cc_sm_<c>_story` tpls, not constructors. Leave the sections and the
  dummy factory's STORY entries as retail.
- **Siege-mode NPC marines read the PVE_PVP sections** (`npc_siege_marine_<c>_client.cls`,
  `auto_interplay_npc_siege_marine_*`, `characterSet PVE_<C>`) but load the retail class constructor: retarget their
  class files with the player classes or they look up objects their tpl lacks.
- **Never split a region that a script or graph tests as a shared outfit part.** A helmet-off animation graph checked
  57 helmet regions with `IsGeomRegionVisible(isSharedOutfitPart = True)`; making those regions per-class broke it.
  Keep such regions shared (trim their meshes instead).
- **Insert keys at the item's own level.** Adding `appearanceUids` "before the first `__type`" of an item block put
  it inside a nested lock struct (`dlcLock` and similar) on 16 items: duplicate offers in the menu.
- **Hide passes run last.** A "hide everything a class does not own" pass that runs before later steps assign new
  objects hides those objects in their own class too (new pieces were invisible in game). Run it last, or unhide each
  late object's descendants in its owning section.
- Renamed heads must be renamed in every hide list too (`meshesToHide` of helmet-off slots, helmet `headObjects`).

### Mesh-level traps of a seven-way merge
- **Duplicate joint names freeze a rig part.** The servo-arm skeleton was in the tpl twice (a leftover copy under
  `backpack_jiggle` exists in the retail Tactical tpl too). The animation rig binds joints by NAME and the first id
  wins; the leftover copy had the lower ids for the main hinges while the meshes were skinned to the other copy, so
  the arm stayed in its bind pose (pointing forward over the head). Retail's duplicate is harmless until a merge skins
  meshes to one of the copies. Fix built: rename the unused copy's 43 joints (in-game result not yet reported). After
  every merge, list duplicate joint names in `obj_list.json`.
- **Joint-index width (u8 vs u16) is NOT proven harmless in general.** Retail Techmarine and NPC chaplain materials
  live on an FVF family with 8-bit joint indices (`...1e...00`); on the soldier constructor everything becomes 16-bit
  (`...1c...40`). The chaplain materials have run that way for weeks. The Techmarine ones crash on opening the
  Techmarine armoury tab (`vid_sdr_cache.cpp`, glt vertex shader, defines `GLT_SFX_HIGHLIGHT`, `RENDERBLOCK_COLOR`,
  `GEOM_TWISTING`, `USE_CUSTOMIZATION_TEXTURES` on FVF `47008b1c02420020000040`), and the crash survived retargeting
  every material to a feature set that retail pairs with that FVF. Cause still open (one lead: the key may have to
  exist in the SOLDIER tpl specifically, for objects the armoury can hover-highlight). The same define set also
  crashed once when hovering a custom head in the Head slot.
- **A paint-mask stream without colour data is a layout no retail asset has.** The Heavy plasma backpack came out with
  a mask stream but no COLOR0. Fix: give the mesh colour sets (a material text with colour sets through
  `mesh.extras.materials`, models note), then set `colorSetIdx` PER SPLIT: retail uses 1/2/3/0 on its plasma split and
  -1 on its common split. A restore keyed on (object name, FVF) cannot choose for such objects and leaves them at -1;
  and decals must stay -1 (an over-eager restore set 72 decal records to 1/2/3/0).
- **A jiggle helper promoted to a skin joint must hang off the bone its chain rides on.** A padlock skinned to a
  `lock_jiggle` whose parent swung on another chain floated away from its chain; the fix reparents it to the chain's
  arm bone (built, not yet confirmed in game). Its own jiggle exists only in the dummy factory; in missions it simply
  follows its parent.
- Unnamed `Obj<id>` parents above the damper/cloth capsule end points must get their retail matrices back (models
  note); on this merge 46 of 67 were restored and every capsule point is within 1 cm of retail.

### The USF file (what ModelConverter writes and UsfExport reads)
Saber ships the C# that defines it with the Mod Tools (`ModelConverter/ToolsSource/SaberTools/USF/`: `Usf.cs`,
`UsfScene.cs`, `UsfNode.cs`, `UsfNodeMesh.cs`, `UsfPses.cs`, `UsfSaberActor.cs`). It is a plain depth-first
serialisation: no offsets, section sizes, hashes or checksums anywhere, only per-array counts and one child count per
node. Little-endian; a string is an `i32` length followed by UTF-8 bytes (all ASCII in practice). Shape, as read from
ModelConverter-written files (Saber's Maya-exported samples use extra node features this layout does not cover):

```
file   : i32 ver | str sourcePath | str type ("tpl") | str options (ps text) | scene
scene  : u32 ver | u8 hasRoot | node
node   : i32 ver | i32 uid | str name | str modelName | str affixes | i32 psesVer | str pses
         3 x mat4 (local, world, localOriginal; 2 on old versions) | str sourceId
         optional blocks, each behind a u8 flag: lwi, MESH, animation, ACTOR, then nine more flags
         that ModelConverter always writes as 0 | str mayaNodeId | i32 childCount | child nodes
mesh   : i32 ver
         positions, normals: i32 n + n x vec3, one per triangle CORNER (not indexed)
         colour sets: i32 sets, each i32 n + n x u32
         uv sets: i32 sets, each i32 n + n x vec2 + str name
         tangent sets: i32 sets, each i32 n + n x vec4
         faces: i32 n + n x u32 (material index in the low bits, edge flags in the top 3)
         materials: i32 n, each (i32 ver, u32 vertexColorUsage, str material ps text)
         skin: i32 bonesPerVertex, i32 n, n x (indices, weights)  | u8 skinningMethod
         bones: i32 n, each (i32 boneNodeUid, mat4 inverseBind) | i32 pairs + pairs | i32 blendShapes (0)
actor  : i32 ver | str type | str tplName | i32 anims (0) | i32 n + n x i32 sourceUsfUids | str ref | flagged extras
```

Character layout:

```
.root. (uid 0)
 +- skinned_geometry (uid 4)
 |   +- <group>_grp            synthetic node, one per glTF child of skinned_geometry
 |       +- <part> -> <part>_LOD1..5     the glTF skin nodes
 +- s3dSaberDxTechnicalNode
 +- characterBuilderExportTplDesc        actor; sourceUsfUids = [ROOT uid, 4]
 +- ROOT                                 bones + the merged hierarchy (locators, cdt nodes)
```

- **Uids:** a glTF node gets `6 + its depth-first index in the glTF`; the synthetic group nodes get
  `6 + total glTF node count + k`. Meshes reference bones only by uid (with their own inverse bind matrix). Nothing
  else points at another node, and materials live inside each mesh as text, so meshes are self-contained.
- **Size:** ~82.7 bytes per triangle corner (position 12, normal 12, UV 8, tangent 16, skin 32, face 4/3). The
  8.4 GB all-class USF is ~100 M corners (~33 M triangles); UsfExport welds the corners back together.
- **Groups convert independently.** Converting {A}, {A, B} and {B} subsets of a constructor: every node of A was
  byte-identical in AB except the two synthetic group uids (shifted by B's node count), and the non-skin part
  (hierarchy, ROOT, technical node, actor) depends only on the hierarchy + ROOT. A changed material changes only that
  group's meshes.
- **Group order is part of the output.** The same groups in a different order give a different tpl (object order;
  124 bytes longer in the test) and an identical `.cdt`.
- UsfExport and CDTConverter are deterministic: the same USF gives byte-identical `.tpl`, `.tpl_data`, `.cdt`,
  `.geom_dbg`, `.lods_base` and `obj_list.json` run to run.

### Why the stock glTF -> USF step takes an hour
Measured passively on the real conversion (167 MB glTF JSON + 4.0 GB of bins -> 8.41 GB USF):

| phase | wall |
|---|---|
| glTF load, node typing, first mesh conversion of every node | ~15 min |
| second conversion of every skinned mesh while building `skinned_geometry` | ~39 min |
| writing the USF (incl. a 4.5 min stall) | 7.5 min |
| total | 62.7 min, 2,999 CPU-s, 32-33 GB private on a 31.9 GB machine |

- The source explains it: every triangle corner becomes several small heap objects, the converter runs its mesh
  conversion on EVERY node and then again on every skinned node (the first result is thrown away), and the whole USF
  is built in memory before it is written. Past physical RAM every full GC pages the heap in and out.
- On inputs that fit in RAM the same converter scales linearly at ~30-34 s wall per GB of USF (retail Techmarine
  constructor and its 25/50 % subsets), which predicts ~5 min for 8.4 GB: >90 % of the hour is paging.

### The low-memory converter (full rebuilds)
- The Mod Tools ship the converter source (GPL). It builds offline for .NET 11 against the SharpGLTF and Newtonsoft
  DLLs that ship next to the converter; no downloads.
- **`DOTNET_EnableAVX2=0` is required for identical output:** with AVX2 the runtime's vectorised `Matrix4x4` maths
  makes node world matrices differ by 1 ULP. With it set, the unpatched source build matched the shipped converters
  byte for byte on every test.
- The patch (~60-70 lines) does two things: skip the throw-away first conversion of skinned-group meshes, replaying
  its single side effect (adding the `map2` UV set to the materials), and build each skinned mesh lazily while writing
  its node, dropping it right after. Peak memory becomes about "glTF in memory + one mesh": -46 % peak and -26 % CPU on
  the retail Techmarine constructor; on the full model ~5 GB private mid-run instead of 33 GB.
- **v13 vs v14:** the source is v14 and behaves like the Mod Tools release; the game-folder converter the pipeline
  had always used is v13. They write the same USF format, but v14's second-layer code (`gotSecondLayer` /
  `hasSecondUvMap`) adds a second material layer and a `map2` UV set whenever a material's extras name a second
  texture: 279 meshes in 40 groups here (the v14 USF was 47 MB larger). That changes material shapes (shader-cache
  risk), so the patched build gates that code behind an environment switch, `MC_V13=1`, which reproduces v13.
  A side effect worth knowing: v13 silently ignores second textures that custom pieces ask for.

### The splice (small changes)
For a change inside `skinned_geometry` (a head, an armour piece, a seal, a material, an affix), only the changed
groups are converted and the rest is copied from the last USF.

1. **Fingerprint** every group of the new glTF: a hash over each node's JSON (children by name, without mesh/skin
   indices), the mesh JSON, each primitive's material JSON and attribute names, the raw de-interleaved bytes of every
   accessor and index buffer, the skin's joint names and inverse bind matrix bytes. Compare with the fingerprints
   stored for the glTF behind the cached USF.
2. **Cut a donor glTF**: the full `hierarchy` + `ROOT` + only the new and changed groups, with a compacted `.bin`.
3. **Convert the donor** with the same converter behaviour as the cache (seconds).
4. **Write the output** as: donor file header + donor `.root.` header; the `skinned_geometry` header with the new
   child count; the cached groups in cached order (a changed group swapped for the donor's copy, a removed group
   left out); the new groups appended; then the donor's technical node, actor and `ROOT` verbatim, so skeleton,
   locators and `Obj<id>` matrices always come from the new glTF.
5. **Patch only uids and bone references:** renumber skin and group uids exactly as ModelConverter numbers them
   (this assumes `skinned_geometry` is the last top-level glTF node, true for retail exports and the merge), and remap
   every bone uid in the copied meshes from the old skeleton to the new one **by full node path**. The merged hierarchy
   repeats ~1,400 bone names (one joint name appears 3 times); a leaf-name map picked the wrong node on the first
   full-size run.
6. Write to a temp file and rename it over the output.

Fall back to a full conversion when: groups were reordered or inserted mid-list (new groups must be APPENDED), the
top-level layout changed, a bone the copied meshes use is missing from the new skeleton or its path is ambiguous, or a
changed group shares a converter "groupName" with another group. The converter links `_sim`, `_lod`, `_decal` and
`_rend` nodes across the WHOLE scene by that name (lower-cased node name cut at those tokens), so such a group is not
independent. Hierarchy renames are fine: the donor always carries the new hierarchy, and a group whose skin joints
were renamed fingerprints as changed. If the inverse bind matrices change, every group using them is re-converted
(correct, but close to a full run).

Cache layout used:

```
<cache>/base/<model>.usf   last good USF (same file name: UsfExport derives the tpl name from it)
<cache>/manifest.json      per-group fingerprints + top-level layout + groupName map of that glTF
<cache>/pending.json       exists only between a splice and its promotion
```

Promote only after the whole build (UsfExport, post passes, pack) succeeded; a failed build never touches the cache.
Promotion can hardlink the new USF into the cache (instant on one volume; a copy of 8.4 GB took 10+ min on the HDD),
which is safe only if every writer of the output path deletes the file first and the splice writes by rename.

## Build steps
All-class constructor (one full build):
1. Export every retail class constructor to glTF; fix the anonymous mesh nodes and copy the `Obj<id>` matrices
   (models note).
2. Compare each class glTF with the soldier glTF by geometry + material; rename real conflicts with a class prefix
   and keep the rename map.
3. Merge into the soldier glTF: groups appended to `skinned_geometry`, missing bones grafted into `ROOT`, uint16
   joints, own `extras` per copy, duplicate joint names checked.
4. Add new pieces by appending their groups at the END of `skinned_geometry` (keeps the splice possible).
5. Split the buffers so each `.bin` is under 2 GB.
6. Convert (splice, or the full converter; below), then UsfExport + CDTConverter in a private exporter project.
7. Post passes on the tpl: all-zero stream check, unshrink, per-split `colorSetIdx` restore (decals -1), material
   check against RETAIL tpls only, any byte-level patches that must be re-applied after every rebuild.
8. Text: library (per-class copies of shared items, hidden regions last, retail-unowned objects left unowned,
   STORY untouched), class files of every class and the Siege NPCs (`nameTpl` + `.cls.resource` links, merged physics
   entries), dummy factory entries + pruned `linksTpl`, markup (merged `objectInfos`, all customization groups), retail
   `.tpl.resource` + your links.
9. Pack the WHOLE tpl family + text as ZIP_STORED in one pak that sorts first.

A text-only change (library, class files, markup) needs no conversion: rebuild the text and repack in ~2 min, with a
guard that refuses when the glTF is newer than the tpl.

Fast mesh rebuild loop:
1. After a full conversion: seed the cache with that glTF + USF.
2. On a mesh change: run the splice; on its "fall back" exit code run the full converter instead.
3. After the pack succeeded: promote the new USF to the cache base (or re-seed after a full conversion).
4. For full conversions use the patched converter with `MC_V13=1` and `DOTNET_EnableAVX2=0`.
5. Spot-check now and then: full-convert a copy of the same glTF and compare the files byte for byte.

## Verification
- **Byte-identical proofs (all with `cmp` / md5):**
  - patched converter (`MC_V13=1`, AVX2 off) on the full model vs the game converter's 8.41 GB USF: identical, 9.5 min
    instead of 62.7 (218 vs 2,999 CPU-s);
  - splice no-op at full size (the model's glTF against its own cached USF; 1,199 groups, 1,281 bones remapped):
    identical;
  - small inputs (subsets of the retail Techmarine constructor, 30-50 MB USFs): add a group, change a material,
    remove a group, change + add, a hierarchy-only rename, a splice chained on a promoted base: each identical to a
    full conversion; UsfExport + CDTConverter outputs of a spliced USF identical to those of a converted one;
  - production: two consecutive builds were spliced (6.4 and 8.7 min), the second chained on the first; a full
    conversion of the second build's glTF with the patched converter (4.6 min) was byte-identical to the spliced USF
    (8,444,878,640 bytes), which proves both splices.
  - a full-size "add one head" splice exported cleanly with exactly the 7 new objects added and all 15,916 existing
    objects unchanged (engine ids masked).
- **In game:** the all-class constructor loads, renders and plays across several builds, with per-class visibility
  working (each class shows its own armour). Seen broken in game: a helmet-off feature (fixed, gotcha 5), the Techmarine-tab crash,
  one head-hover crash, Bulwark robe / Sniper coat cloth exploding on the armoury figure, late-added pieces hidden by
  an early hide pass (fixed in the text, not re-tested), a servo arm frozen by duplicate joint names (fix built, not
  re-tested), a padlock floating off its chain (fix built, not re-tested).
- **Found by a read-only audit of the data, not seen in game** (fixed in the text before anyone hit them): the
  STORY_* and Siege NPC problems, the hidden Heavy backpacks, the duplicate shared-item offers, the lobby preload,
  the missing markup customization groups, the paint-mask stream without colours. Gotchas 2-4, 6, 10 and 11 are
  marked "(audit)".
- Not verified: joints 1,247-1,276 individually; the capsule-point restore in game (offline: within 1 cm of retail);
  the cloth root causes; the Techmarine crash cause.

## Gotchas
1. **The armoury servo arm sticks out straight over the head.** Cause: the servo-arm joints exist twice; the rig binds
   by name and the unused copy has the lower ids. Fix: rename/remove the duplicate joints (built, not yet re-tested in
   game); list duplicate joint names after every merge.
2. **(audit) A class's backpacks and feed tubes would vanish (Heavy), likewise fists (Assault/Bulwark).** Cause: retail draws them
   unowned and a blueprint/property toggles them; a hide pass put them in an `isHidden` region. Fix: keep exactly what
   retail leaves unowned out of every hidden region.
3. **(audit) Campaign squadmates would lose heads, fillers and backpacks.** Cause: `STORY_*` sections edited; campaign NPC marines
   read them with their own `cc_sm_<c>_story` tpls. Fix: leave `STORY_*` and the factory's STORY entries retail.
4. **(audit) Siege-mode NPC Sniper/Heavy would look wrong.** Cause: they read the edited PVE_PVP sections but still load their retail
   tpl. Fix: retarget their client and interplay class files to the shared tpl.
5. **A helmet-off feature stops working after the merge.** Cause: its graph tests helmet regions as shared outfit parts;
   the merge split them per class. Fix: keep regions that any graph checks with `isSharedOutfitPart` shared.
6. **(audit) Every class is offered the same shared item twice.** Cause: the new `appearanceUids` list was inserted inside a
   nested lock struct of the item. Fix: insert at the item's own `__type` level.
7. **New pieces are invisible in their own class.** Cause: the global hide pass ran before the steps that assigned them.
   Fix: hide last, or unhide late objects' descendants in the owning section.
8. **A merged build passes the shader check, then crashes on one armoury tab.** Cause: the reference set included an
   earlier build that only "worked" because nobody opened that tab. Fix: check against retail tpls only.
9. **Techmarine tab crash (`GEOM_TWISTING`, `GLT_SFX_HIGHLIGHT`) persists after retargeting every material.** Cause:
   open; retail Techmarine materials live on 8-bit joint-index FVFs and the merge makes them 16-bit. Do not assume the
   index width is harmless just because other materials survived it.
10. **(audit) The lobby preloads ~2.5 GB of tpls no armoury entry uses.** Cause: the dummy factory `.resource` still
    links the retired class tpls and preloads them. Fix: prune `linksTpl` to the tpls the entries name.
11. **(audit) Painted parts of the moved classes lose their colour options.** Cause: the soldier markup lacks those classes'
    `materialCustomizations` groups. Fix: add `ANTENNA`, `MANIPULATOR`, `VANITY`, `JUMPPACK` (empty blocks).
12. **A spliced USF is not what a full conversion gives.** Cause: groups reordered or inserted mid-list, or a bone map
    by leaf name in a skeleton with repeated names. Fix: append only; map bones by full path; refuse (fall back) on an
    ambiguous path.
13. **The cached base USF is suddenly truncated.** Cause: it is a hardlink of the output and a script overwrote the
    output in place. Fix: every writer deletes the output first; the splice writes temp + rename.
14. **Spliced and full outputs differ only in a few groups after a converter change.** Cause: base and donor came from
    different converter behaviour (v13 vs v14 second layers). Fix: one behaviour for both (`MC_V13=1` with the
    patched build, or the game-folder converter).
15. **A source build of the converter differs from the shipped one by tiny matrix values.** Cause: AVX2-vectorised
    `Matrix4x4` maths in the newer runtime (1 ULP). Fix: `DOTNET_EnableAVX2=0`.
16. **A size check in a PowerShell build script fails above 2 GB.** Cause: `[math]::Max($x, ...)` with `$x = 0`
    starts as Int32 and overflows. Fix: start it as `[long]0`.
17. **The full conversion takes an hour and the PC is unusable.** Cause: ~33 GB peak on a 32 GB machine (two passes
    over every skinned mesh, whole USF in memory). Fix: splice, the low-memory build, or free RAM before starting.
18. **A cape stays rigid although its mesh, pins, remap reach, sim object and class entries all match a working coat.**
    Cause: unknown (open). The piece was dropped rather than debugged further.

## Assets
Only the game's own constructors and custom pieces made for private builds were merged; nothing from the game is
attached to this note. The tools are small Python scripts written for this (USF indexer, splice, glTF subset cutter,
fingerprint driver) and a locally rebuilt converter; the patched binary was not published.

## Cost and time

| step | before | after |
|---|---|---|
| glTF -> USF, full model | 62.7 min (stock, paging) | 9.5 min patched (4.6 min on a later run); ~5 min floor in v14 mode |
| glTF -> USF, one head added | 62.7 min | 5.2 min splice (3.3 min warm no-op); 6.4-8.7 min in production |
| UsfExport + CDT | 11-13 min | unchanged (the new floor) |
| mesh change end to end | ~90 min | ~20-31 min (31 min measured for a whole spliced build) |
| text-only change | - | ~2 min |

Splice at full size: fingerprinting 1,199 groups (4.0 GB of bins) 170-185 s cold / 36 s warm; donor cut + convert
5-6 s; indexing the 8.4 GB base 7-93 s; writing 8.4 GB to the HDD 112-153 s (about 1 min on an SSD). Fingerprinting
could be faster by hashing whole bufferView byte ranges instead of de-interleaving in Python.

## Open questions
- The Techmarine-tab / head-hover shader crash: which key the hover-highlight permutation needs.
- Bulwark robe and Sniper coat exploding on the armoury figure with data identical to retail.
- Why the all-class input needed ~3x more converter memory per GB than retail inputs (vertex-colour sets that only the
  merged glTF has, or the ~6x larger node count feeding quadratic scans in the converter's node collection).
- Whether the splice could also skip UsfExport by editing the tpl in place for one changed group (not attempted).
