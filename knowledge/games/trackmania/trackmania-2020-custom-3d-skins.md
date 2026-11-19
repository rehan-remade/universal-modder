---
kind: game
title: "Custom 3D car skins in Trackmania (2020) with Blender, Blendermania and gbx-py"
game: "Trackmania"
games_also: ["ManiaPlanet"]
game_version: "Trackmania (2020), live build; the tutorial does not pin a build, and none was tested here"
platform: windows
engine: unknown
route: asset-only
tools: ["Blender 4.x", "Blendermania addon", "NadeoImporter (ships with Blendermania)", "NICE (ships with Blendermania)", "gbx-py (skinfix)", "Openplanet"]
anti_cheat: "none for this route: it is client-side cosmetic meshes and textures, and online visibility only needs the skin uploaded to your own Club. The tutorial still warns that console players can crash on custom 3D skins and that Nadeo is not enthusiastic about them, so it asks for restraint."
status: idea
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-10
links: ["https://github.com/skyslide22/blendermania-addon", "https://github.com/schadocalex/gbx-py", "https://github.com/drunub/tm-pf-converter", "https://openplanet.dev/file/119", "https://bmx.sh/3dskindiscord"]
tags: [trackmania, gbx, 3d-skins, blender, nadeo-importer, blendermania, lod, vertex-groups, decal-uv, openplanet]
---

# Custom 3D car skins in Trackmania (2020)

> This is a write-up of a third-party route, not of work done here: nothing below was executed by us.
> Trackmania (2020) accepts custom car meshes as **GBX** assets plus DDS textures, authored in Blender
> with the Blendermania add-on, exported by **NadeoImporter**, then repaired/converted for the live
> build by **gbx-py**'s `skinfix`. The write-up follows bmx22c's June 2024 tutorial and its pinned
> corrections; every step is second-hand until someone runs it on a real install.

## Setup
- **Blender** (the tutorial era is Blender 3.2–4.x) with the **Blendermania** add-on, which bundles
  **NadeoImporter** and **NICE** — install them from inside Blendermania, not separately, so the
  add-on's own copies are not overridden.
- **gbx-py** (schadocalex) with **drunub's `skinfix` script** next to it. Newer builds merge gbx-py
  and the script into one `skinfix.exe` (Openplanet file 119): drag the produced `.gbx` onto it.
  gbx-py needs `python-lzo`; drunub's tm-pf-converter README says it has to be compiled from source on
  Python 3.14 and that build fails, so use Python 3.11 or `skinfix.exe`.
- **Openplanet** if you want to pull apart an existing skin.
- Folders that matter, under the Trackmania user folder (`Documents\Trackmania\`, or
  `Documents\Trackmania2020\` on some installs; drunub's example config shows both): the FBX and its
  `.MeshParams.xml` go in `Work\Skins\Models\<SkinName>\`, and the finished ZIP goes in
  `Skins\Models\CarSport\`.
- An existing skin to start from, or a template. `.Solid.Gbx` opens directly in Blender through NICE;
  `.Pack.Gbx` does not (see gotcha 11). Someone else's skin is for learning from: don't upload it, or a
  conversion of it, without its author's permission (drunub's converter README asks the same).

## Route and why
`route: asset-only`. The game loads a **GBX model** and **DDS textures** from a ZIP in the user's
`CarSport` folder; nothing in the executable is patched and no DLL is injected, so this stays inside
the "own assets, own client" line. The two alternatives the tutorial mentions and does not use are a
converter for existing TM2 skins (drunub's tm-pf-converter in `links`; its README says it only takes skins
built with TM2's NadeoImporter, not TMNF meshes) and a map-to-Blender ripper — both aimed at *porting
existing* content, not at authoring a new skin.

The container half of this route is already covered in this base by
[*Reading TrackMania GBX containers and getting meshes out without Nadeo tooling*](../../techniques/trackmania-gbx-containers-and-mesh-extraction.md),
and the ManiaPlanet folder layout that gotcha 11 relies on by
[*TrackMania 2 custom content*](../trackmania-2/maniaplanet-content-locations-and-custom-pack-layout.md);
this note is the TM2020 authoring half.

## How the game works (what the tutorial explains)
- **Two container shapes.** `.Solid.Gbx` is the simple mesh and converts straight to Blender. `.Pack.Gbx`
  is a package whose members (`.Solid.Gbx` and textures) have to be extracted first.
- **Materials are named by convention, not by path.** The four the tutorial creates, as transcribed:
  `SkinDmg_Skin` → `Skin_D.DDS`, `DetailsDmgNormal_<name>` → `Details_B.DDS`,
  `DetailsDmgNormal_Details` → `Details_D.DDS`, `GlassDmgCrack_<name>` → `GlassO_T.DDS`. Extra
  materials are allowed as long as the prefix matches. drunub's converter template uses the same models
  as `SkinDmg_Skin`, `DetailsDmgNormal_Details`, `DetailsDmgNormal_Wheels` and `GlassDmgCrack_Glass`
  (plus `...Decal` variants), with textures named after the part after the underscore (`Skin_*`,
  `Details_*`, `Wheels_*`).
- **`SkinDmg_Skin` carries no normal map.** If a part needs normal detail, put it in
  `DetailsDmgNormal_*`. TM2020 skin textures take the same `_R` (roughness) and `_N` (normal)
  suffixes as other TM2020 textures. drunub's README adds that the TM2-style `_D` texture only works on
  the skin material (details and wheels take `_B` plus an optional `_R`) and that `Skin_B` needs a
  `Skin_R`, so check the `Details_D` mapping above on a real build.
- **Textures do not tile.** A model whose UVs run outside the texture limits loses the texture, so
  fitting the UVs to the image is part of modelling, not an afterthought.
- **LODs are duplicated meshes with a bone/skeleton binding.** The usual count is three, up to five
  for complex cars; the exported name carries `_lod0`, `_lod1`, … and the skeleton stops being usable
  from LOD 4 upward.
- **A `.MeshParams.xml` sits next to the FBX** (`MeshType="Vehicle"`, `SkelSocketPrefix="_"`,
  `Collection="Stadium"`, plus the material list). NadeoImporter needs it and reports a collection
  error when it is missing or wrong.
- **Visibility online is not the same as visibility in your own garage.** Other players see the skin
  only when it is uploaded to your Club, and only if it respects the vertex budget.

## Build steps
Second-hand, in the tutorial's order:

1. Build the four textures, or reuse the template's, and keep every one inside the model's UVs.
2. Start from the template `.blend`; delete the **FakeShad** plane if you are not using a custom fake
   shadow.
3. For each part, select the part, go into edit mode, select all, return to object mode, Ctrl+click the
   matching LOD object, then Ctrl+J to join.
4. Assign each part to its body vertex group, then move the group's bone to the part's origin. Wheels:
   `Reactor` and `Guard` share the same position, and the bone's rotation must match the mesh's.
   Bones can be added or removed as long as the matching vertex groups come and go with them.
5. Exhaust flames: use the `TwoCorExhaust` bones (one bone if you only want one flame).
6. Keep the model inside the template's bounding box; otherwise other players do not see it.
7. Extra LODs: duplicate the previous LOD, unparent it with Alt+P → *Clear and Keep Transformation*,
   rename to `_lod2` (then `_lod3`…), reselect the correct **skeleton modifier** and the correct
   materials. A name Blender has suffixed with `.001` will not work.
8. Trigram / player-position meshes: copy them from the supplied Blender file, place them, and **do not
   modify their UVs**. Their material is `SkinDmgTrigram_Skin` → `SkinD.DDS`, and each decal material
   needs a second UV layer named `Decal`, identical to the `BaseMaterial` layer.
9. Export FBX with **Add Leaf Bones unchecked**, as
   `Documents\Trackmania\Work\Skins\Models\<SkinName>\<SkinName>.fbx`, and copy
   `<SkinName>.MeshParams.xml` beside it.
10. Run `NadeoImporter.exe Mesh Skins\Models\<SkinName>\<SkinName>.fbx` from the Trackmania install
    folder (a PowerShell window opened there).
11. Repair/convert with `python skinfix.py <path>\<SkinName>.gbx`, or `--fakeshad` when you supply a
    FakeShad DDS. The script writes `MainBody.Mesh.Gbx` next to `<SkinName>.Mesh.Gbx`.
12. ZIP the textures together with `MainBody.Mesh.Gbx` into
    `Documents\Trackmania\Skins\Models\CarSport\<SkinName>.zip`.
13. In game: plugins → classic menu → editors → **paint a car** → pick the skin. Refresh the garage
    with M (stops the car spinning) then Ctrl+R. Check bone rotations in Cam 7 with the camera locked
    to the car. Upload to your Club to let other players see it.

## Verification
**Nothing here was run by us.** The route above is transcribed from bmx22c's tutorial (19 June 2024)
and the four corrections pinned in its description, plus the comments' workarounds. The oracle the
tutorial itself uses: the skin appears in *paint a car*, the car stops spinning on M, Ctrl+R reloads
it, and Cam 7 shows whether the bones are rotated correctly. The vertex budget message is the other
oracle — the top-left corner says only "build …" unless you open the detailed overlay.

## Gotchas
1. **NadeoImporter prints only its banner and produces no `.gbx`.** **Cause:** the `.MeshParams.xml`
   is missing or misnamed next to the FBX. **Fix:** copy `<SkinName>.MeshParams.xml` beside the FBX,
   in the same `Work\Skins\Models\<SkinName>\` folder.
2. **`collection Common not found`.** **Cause:** the collection in `.MeshParams.xml` does not match
   what the importer expects (the template uses `Collection="Stadium"`). **Fix:** use the template's
   file rather than hand-rolling the XML.
3. **`Mesh : not enough UvLayers for material (1 < 2)` on the trigram or player-position mesh.**
   **Cause:** the decal material needs two UV layers. **Fix:** add a second UV layer named `Decal`,
   identical to `BaseMaterial`.
4. **The skin is invisible to other players.** **Cause:** a LOD exceeds the vertex budget (the game
   silently keeps the default skin), or the skin was never uploaded to the Club. **Fix:** open
   system → scene explorer → viewport overlays index 4 → *frame* → *vehicle* → *profile menu* →
   *frame instance* → *frame content*, uncheck *frame Vehicles* to read the real message, cut the LODs'
   vertex counts, re-export, and upload the skin to your Club.
5. **A duplicated LOD loses its materials or skeleton.** **Cause:** Blender renamed the copies to
   `.001`, which the game does not match. **Fix:** in the duplicated LOD, reselect the correct
   skeleton modifier and the exact materials.
6. **Skeleton binding stops working on the highest LODs.** **Cause:** the tutorial's own warning that
   skeletons do not work from LOD 4 up. **Fix:** for those LODs bind everything to the body bone and
   reduce the vertex count until the budget complains no more.
7. **A part is invisible or misplaced for other players.** **Cause:** it sits outside the bounding box
   the game checks, or its bone was never moved to the mesh origin (wheels: `Reactor`/`Guard` share a
   position and the bone rotation must match the mesh). **Fix:** re-check the box and the bone
   transforms.
8. **Parts end up in the wrong LOD.** **Cause:** the join was done without selecting the target LOD
   object first. **Fix:** Ctrl+click the LOD object, then Ctrl+J.
9. **Trigram or player position renders as a smear.** **Cause:** their UVs were modified. **Fix:**
   paste the supplied meshes and leave their UVs alone.
10. **A custom normal map changes nothing on the main body.** **Cause:** `SkinDmg_Skin` has no normal
    slot. **Fix:** put normal detail on `DetailsDmgNormal_*` instead.
11. **`.Pack.Gbx` will not open in Blender.** **Cause:** it is a package, not a mesh. **Fix:** pull
    the `.Solid.Gbx` and textures out first — either with Ninja Ripper, or, from ManiaPlanet, by
    unpacking the skin ZIP into `ManiaPlanet\Skins\Models\StadiumCar\<SkinName>\` and using Openplanet
    (developer mode) in the garage: F3 → System → Folders → MemoryTemp → PackDescContents →
    `_user__Skins_Models_StadiumCar_<SkinName>` → `Model.Pack.Gbx` → *Preload Nod* each member →
    *Extract*.
12. **Console players crash.** **Cause:** custom 3D skins, per the tutorial's own warning. **Fix:**
    treat this as a reason to keep custom skins private or limited, not as a bug to solve.

## Open questions
- Does the live build still accept the same `.MeshParams.xml` schema and material prefixes? Nothing
  here was validated against a current build.
- Which vertex budget actually applies per LOD today, and is it per-LOD or per-model?
- The Windows-only NadeoImporter is the one hard dependency; NICE and gbx-py are the parts that might
  run natively on Linux under Blender's own Python. Worth testing before assuming the route is
  Windows-only.
