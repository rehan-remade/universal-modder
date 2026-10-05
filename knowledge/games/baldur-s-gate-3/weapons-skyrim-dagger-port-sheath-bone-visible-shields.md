---
kind: game
title: "Weapons: porting a Skyrim dagger and scabbard, fixing a modded sword's sheath height with a Dummy_Sheath bone, and visible stowed shields for modded shields"
game: "Baldur's Gate 3"
games_also: []
game_version: "Patch 7 era (Apr 2026) and Patch 8 hotfix (Aug 2026), Steam, Windows"
platform: windows
engine: unknown
route: asset-only
tools: ["Blender 3.6 LTS + niftools addon 0.1.1 (NIF import)", "Blender 4.0.2 + Norbyte dos2de_collada_exporter", "LSLib Divine 1.20.4 (convert-model, glTF and DAE)", "Blender Weapon Templates (Nexus 11600)", "texconv", "Python (glTF and lsx edits)"]
anti_cheat: "none; single-player"
status: working
agents: ["Claude Code (Opus 4.7)", "Claude Code (Opus 5)", "Claude Code (Opus 5.5)"]
humans: [RedSuper]
date: 2026-10-05
links: ["https://www.nexusmods.com/skyrimspecialedition/mods/107829", "https://www.nexusmods.com/baldursgate3/mods/23732", "https://www.nexusmods.com/baldursgate3/mods/443"]
tags: [weapons, gr2, sheath, dummy-sheath, equipment-types, skyrim-port, nif, gltf, conform, shields, patch-8, scabbard]
---

# Weapons: porting a Skyrim dagger and scabbard, fixing a modded sword's sheath height with a Dummy_Sheath bone, and visible stowed shields for modded shields

> Three weapon jobs in one personal mod. (1) The dagger and scabbard from the Skyrim SE mod "Hravna - Dagger
> of the North" by Danp (for personal use) became a usable BG3 dagger plus a worn scabbard that sits where the
> sheathed dagger lands on the hip, with the Bandit belt from wesslen's BG3 mod "Modular Equipment" as its strap.
> (2) The Deathwyrm longsword from the BG3 mod "Falazure (Clothing and Light Armor)" by onyx, naerys and mons
> was scaled up 25% and given a `Dummy_Sheath` bone so it hangs higher when stowed without moving the in-hand
> grip. (3) A generated patch converts 144 shields from three mods into the "visible when stowed" form that a
> community mod uses on Patch 8. The dagger, scabbard, sword and the converted shields of two of the three mods
> were confirmed in game by the human; the third mod's (random-loot) shields were not tried in play.

## Setup
- BG3 on Steam, Windows 10; Patch 7 era for the dagger, Patch 8 hotfix for the sword and shields.
- NIF import needs Blender 3.6 LTS with `blender_niftools_addon` 0.1.1 (it does not run in Blender 4.x). The
  portable 3.6 build failed with `STATUS_DLL_NOT_FOUND` (VC++ runtime); the MSI installer works.
- BG3 export stays in Blender 4.0.2 with the dos2de addon; LSLib `Divine.exe` 1.20.4 for `convert-model`
  between GR2, DAE and glTF (`-o gltf` / `-i gltf`).
- Source mods (credited above; links in the front matter): "Hravna - Dagger of the North" (Skyrim SE, Nexus
  107829, by Danp; the SE build with `DanpHravnaDagger.esp`), "Falazure (Clothing and Light Armor)" (BG3, Nexus
  23732, by onyx, naerys and mons; Deathwyrm is its longsword), "Modular Equipment" (BG3, Nexus 443, by
  wesslen; the Bandit belt mesh `HUM_F_ARM_Bandit_D_Body_Belt_B_MEQ_ForCorsetE`).
- "Blender Weapon Templates" (Nexus 11600) for a pre-rigged dagger skeleton; vanilla `WPN_HUM_Dagger_A_*.GR2`,
  `WPN_HUM_Longsword_A_0.GR2` and `HUM_F_Base.GR2` (the full 120-bone character skeleton) as references.

## Route and why
`asset-only`: new GR2s, visuals, materials, root templates and stats in a pak. The alternative for sheath
placement, editing `EquipmentTypes.lsx`, is per weapon **type** and would move every weapon of that type, so
per-item fixes go into the weapon's own GR2. BG3 has no scabbard mesh type; a scabbard is a worn item.

## How the game works (what we had to learn)
- **`EquipmentTypes.lsx`** (per weapon type) holds both sides of the attachment: `BoneMainUnsheathed`
  (character bone for the hand, `Dummy_R_Hand`), `BoneMainSheathed` (character bone when stowed, e.g.
  `Dummy_Sheath_Upper_R`, `Dummy_Sheath_Hip_L`) and **`SourceBoneSheathed = Dummy_Sheath`, a bone inside the
  weapon's GR2 used only when stowed.** A weapon GR2 without `Dummy_Sheath` hangs by its origin (the grip) in
  both poses, so any mesh translation moves the hand grip too. With the bone, moving the bone moves only the
  stowed pose. Vanilla daggers already sheathe on the hip (`Dummy_Sheath_Hip_L` / `_R`).
- `WeaponType_OneHanded` / `WeaponType_TwoHanded` in the same file pick the **animation set**. Hip-sheathing
  mods that only change bones are animation-neutral; one that retyped rapiers `Piercing1H → Small1H` changed
  how they are held and posed.
- **Character skeleton:** the body-mesh GR2 carries 82 deform bones; `HUM_F_Base.GR2` has 120 including the
  sheath dummies. `Dummy_Sheath_Hip_L` is parented to `Root_M` (pelvis), at about (0.194, -0.002, 1.073) in
  Blender world space, not to `Hip_L` (a thigh bone that swings with the leg).
- **Weapon GR2 shapes that render:** vanilla longsword = root dummy + `Dummy_Sheath`,
  `Dummy_Sheath_Versatile`, `Dummy_Attachment`, FX dummies, mesh + LOD tiers 0-4. A boneless modded sword =
  one mesh, model node `Unnamed`, 0 joints, 1 geometry. Both render; hybrids made by `--conform-path` did not
  (Gotcha 6).
- **Visual `Template` = `<GR2 path>.<model node>.0`** and the model node name is a real string in the GR2. On
  DAE→GR2 Divine logs `Generating dummy skeleton for model 'Unnamed'` for a boneless mesh. In glTF the same
  name sits at `scenes[0].extensions.EXT_lslib_profile.ModelName`.
- **Patch 8 ignores the Shield type's sheath-bone fields** (the author of the old "Visible Shield" mod says
  so; our test agreed), so no `EquipmentTypes` edit can show a stowed shield. "Visible Shields for Patch 8"
  instead re-issues each shield as an off-hand **weapon** (`type "Weapon"`, `using "WPN_Dagger"`,
  `Slot "Melee Offhand Weapon"`, `AC(2)`), converted from a real shield with a tool item through an
  `ItemCombination`, and patches vanilla passives to accept `HasVisibleShieldEquipped()`. The converted item's
  root template stays shield-family; only the stats make it a weapon.

## Build steps
**Skyrim dagger and scabbard**
1. Import the NIF in Blender 3.6. It held `KnifeBlade01_low` (blade), `Scb` (scabbard), blood-decal meshes and a
   bounding box. Export blade and scabbard separately (FBX) after scaling.
2. **Scale by measuring**, not by a published factor: compare against a vanilla dagger's length (0.594 m for
   `WPN_HUM_Dagger_A_2`). The often-quoted 0.0142875 gave a 5 cm blade for this mod; ~0.156 matched, and the
   human then set the final size by eye.
3. In Blender 4.0, swap the blade into the weapon template's dagger rig (all vertices weight 1.0 to the root
   bone `Dummy_WPN_HUM_Dagger_A_2`), **apply all transforms on the armature as well as the mesh**, export.
4. Optional `--conform-path` to a vanilla donor: rename your mesh to the donor's mesh name first
   (`WPN_HUM_Dagger_A_2_Mesh`) and pick a donor whose root bone matches the one you weighted to.
5. Textures: Skyrim `_d.dds` → BC1 basecolor with mips. Material cloned from a working weapon material; visual
   cloned from a working weapon visual; root template parented to the vanilla dagger base; stats
   `using "WPN_Dagger"`.
6. **Scabbard as a worn item:** parent to the HUM_F skeleton, weight 100% to **`Root_M`** so it moves with the
   stowed dagger, place it against an Empty at the `Dummy_Sheath_Hip_L` position, apply transforms, rename the
   mesh `HUM_F_NKD_Body_A_Mesh` and conform to `HUM_F_NKD_Body_A.GR2`. The human then nudged it over several
   export-and-look rounds. The strap (the Bandit belt from "Modular Equipment") was added to the same worn item the same way.

**Raising a modded sword's stowed position**
1. Convert the weapon GR2 to DAE or glTF and look for `Dummy_Sheath`. The modded sword had none.
2. Scale numerically (multiply the DAE `POSITION` floats by 1.25) so the file keeps its exact structure.
3. GR2 → glTF; add a node `Dummy_Sheath` as a **sibling** of the mesh node under the model root; give the mesh a
   minimal skin (`JOINTS_0` all 0, `WEIGHTS_0` all `[1,0,0,0]`, identity inverse bind) because LSLib cannot
   import a skinless glTF; keep `ModelName` unchanged; glTF → GR2.
4. When stowed the mesh shifts by **minus** the bone's local translation (bone Z -0.10 raises the sword 0.10
   along its axis). Moving along the blade axis gives "up and toward the hilt" together; a perpendicular move on
   a tilted blade also adds height.
5. Verify by converting back to glTF and reading the bone translation and the vertex bounds (unchanged).

**A steel-trim variant of a gold-trimmed modded sword (texture recolour)**
1. The sword's three materials bind plain basecolor/normal/physical maps with no colour parameters, so the gold
   is baked into the texture. Measure which maps carry it (guard 29% of pixels, grip 7%, blade 0%) and recolour
   only those basecolor maps; keep normal and physical maps as they are.
2. Recolour in HSV on warm, saturated pixels only: **snap** the hue to steel and blend only saturation.
   Interpolating hue from gold (~0.12) to blue (~0.58) passes through green and tints half-blended pixels.
3. The gold trim was exactly as bright as the blade and separated only by hue, so a neutral recolour needs to be
   noticeably darker (value gain ~0.66) to read as a separate part.
4. To deepen recesses, stretch value contrast about the median; the BC1 source had only ~21 distinct value levels
   in that region, so a hard stretch posterises into 4x4 block bands. Blur the value channel slightly first and
   dither after.
5. Write the DDS exactly like the source (here BC1, 2048x2048, 12 mips), keep `SRGB=True` in the texture bank,
   and clone the chain with **new** UUIDs (texture, material, visual, root template; stats `using` the original
   weapon so it keeps every passive). A cloned resource that keeps an original ID overrides the original
   item's asset too.
6. Compare previews at a **fixed** crop; auto-picking "the most interesting region" per render made the
   unchanged original look different between previews.

**Visible shields for other mods' shields (generator)**
1. Extract every candidate's stats; only entries that resolve to `using "_Shield"` / `ARM_Shield*` armour need
   it. Mods that already ship shields as `type "Weapon"` in the off-hand slot need nothing.
2. Per shield emit: a weapon stats entry copying its AC, rarity, weight, boosts and passives; a root template
   **parented to the original shield's root template** (inherits visual, icon, name; optional attributes only if
   the source sets them); a forward `ItemCombination` (shield + tool → visible version) and a reverse one that
   returns the original shield.
3. Fixed mod UUID and deterministic per-item UUIDs; `meta.lsx` with an empty `Dependencies` node; load order
   after every source mod and after the Patch 8 base mod (the patch parents to their templates).

## Verification
- Dagger: correct in hand and sheathed on the hip; scabbard confirmed "in perfect alignment" by the human after
  several export-and-look rounds (weighted to `Root_M`).
- Longsword: renders at 1.25x, stowed position raised and moved out of the armour by bone offsets, hand grip
  unchanged; human confirmed "perfect".
- Shields: 144 conversions (43 + 3 from two shield mods, 98 from a random-loot mod) generated, every stats
  name, root template MapKey and combination name unique; the pak loads (after the `meta.lsx` fix in Gotcha 14).
  The human converted and used the two shield mods' shields in play for a while: they work and show when
  stowed. Not tried in play: the random-loot mod's 98, whose root templates inherit their art one level
  further up.

## Gotchas
1. **Weapon or scabbard lying flat on the floor, "following the character like a windsock".** **Cause:** the
   armature imports rotated 90 degrees and only the mesh had transforms applied. **Fix:** Ctrl+A → All
   Transforms on the armature and the meshes before export.
2. **Scabbard far behind the character, underground.** **Cause:** the object's location was set to the hip
   position without applying it, so the skin transform added the offset a second time. **Fix:** apply location
   so the vertices hold the position and the object sits at the origin.
3. **Scabbard on the wrong hip.** The export mirrors X relative to what you expect: for this mesh, Blender +X
   came out on the character's left hip. A `bmesh` vertex-mirror script silently did not persist; use
   `scale=(-1,1,1)`, apply, and flip normals. Determine the side empirically once, then keep it.
4. **Scabbard and sheathed blade drift apart when walking.** **Cause:** scabbard weighted to `Hip_L` (thigh)
   while the blade hangs from `Dummy_Sheath_Hip_L` under `Root_M`. **Fix:** weight the scabbard to `Root_M`.
5. **Dagger invisible after conform.** **Cause:** the donor (`..._A_0`) had root bone `Dummy_WPN_HUM_Dagger_A_0`
   while the mesh was weighted to `..._A_2`; conform replaced the skeleton and the weights pointed at nothing.
   Conform also fails outright ("No matching mesh found") unless your mesh name equals the donor's.
6. **Sword invisible after conforming to a vanilla longsword "to borrow one bone".** **Cause:** conform grafts the
   donor's whole skeleton and layout (0 joints/1 geometry became 45 joints/11 geometries) and the engine draws
   nothing. **Fix:** keep the structure of a GR2 that renders; add the one bone through glTF instead.
7. **Sword invisible after adding a `Dummy_Sheath` JOINT in the DAE.** **Cause:** Divine dropped the joint
   ("Imported rigid mesh") but used its name for the model node, so `Template ...Unnamed.0` dangled. Round-trip
   checks showed 0 joints and looked fine. **Fix:** compare the GR2's name strings with a working copy
   (`b'Unnamed' in data`), and use glTF for bones.
8. **Bone moved the hand pose instead of the stowed pose.** **Cause:** vanilla parents the mesh **under**
   `Dummy_Sheath`; with that hierarchy the offset cancels when stowed. **Fix:** make `Dummy_Sheath` a sibling.
9. **Blender's Collada importer rotated the blade axis Z→Y and dropped an Empty** used as the bone. For a rigid
   weapon, edit the DAE or glTF numerically instead of round-tripping through Blender.
10. **Weapon vanished at distance after conform.** **Cause:** the conformed GR2 inherited the donor's non-zero LOD
    distances and LOD slots (as 1-vertex stubs) while the visual declared only LOD 0. **Fix:** declare all
    tiers the GR2 has and point each at the base mesh.
11. **Item missing from the game entirely, no error.** **Cause:** a "readable" hand-made GUID (`e207dw01-...`):
    `w` is not hex. Packs, converts and cross-references cleanly. **Fix:** regex-gate every GUID before packing.
12. **Stowed shields stay invisible with a visible-shield mod installed.** **Cause:** Patch 8 (see above).
    Also: the base mod's reverse combinations returned the converted item again (no way back), and its patch for
    another equipment mod was inert without that mod installed.
13. **Patch generator found 0 shields in a mod with 101.** **Cause:** it required an explicit `VisualTemplate`,
    but those root templates inherit it from their parent. **Fix:** parent to the source template and let it
    inherit.
14. **A generated patch made BG3 wipe the whole load order on launch.** **Cause:** its `meta.lsx`: `UUID` typed
    `guid` instead of `FixedString`, `LSString` instead of `LSWString`, no `GMTemplate`, and a hand-filled
    `Dependencies` block with display names as folders, empty MD5s and an assumed `Version64`. **Fix:** copy a
    working mod's `meta.lsx` and leave `Dependencies` empty (it does not affect load order).

## Assets
Textures from the Skyrim mod (Hravna, by Danp) converted with texconv (BC1 basecolor with mips; normal maps deferred). No new
art generated.

## Open questions
- Whether a separate "sheathed-only" scabbard mesh can be shown and hidden with the weapon state without
  Script Extender (we kept the scabbard as an always-visible worn item).
