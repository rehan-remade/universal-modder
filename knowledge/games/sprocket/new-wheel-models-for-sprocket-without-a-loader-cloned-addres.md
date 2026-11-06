---
kind: game
title: 'New wheel models for Sprocket, by patching game data or from a BepInEx plugin: cloned Addressables bundles, binary
  catalog.bin keys and part icons on Unity 6000.3 IL2CPP'
game: Sprocket
games_also: []
game_version: "Steam 1674170: stable 0.2.55.5 (buildid 25392405) and experimental 0.2.56.x (buildid 25910892), both Unity 6000.3.21f1 IL2CPP, metadata v39, Addressables 2.9.1"
platform: windows
engine: unity-il2cpp
route: loader-api
tools: ["BepInEx 6 be.788", "Sprocket Mod Loader 1.2.3", "HarmonyX", "UnityPy 1.25.4", "AddressablesTools (nesrak1) @3dbc8210", "Blender 5.2 (bpy, Cycles bake)", ".NET 8 SDK", "Python 3.12"]
anti_cheat: "none found by um scan (single-player); editor/sandbox only. Data route: no game code touched. Plugin route: Harmony postfixes at run time, no game file changed"
status: working
agents:
- Claude Code (Opus 5.5)
humans: ["J1ND3R9"]
date: '2026-10-29'
links: ["https://github.com/nesrak1/AddressablesTools", "https://github.com/K0lb3/UnityPy", "https://github.com/Hans21223/Sprocket-Mod-Loader", "https://github.com/Hans21223/Sprocket-Quality-of-Life"]
tags: [vehicle-parts, wheels, engines, addressables, binary-catalog, unitypy, spriteatlas, icons, procedural-models, blender, bepinex, harmony, il2cpp-interop]
---
# New wheel models for Sprocket, by patching game data or from a BepInEx plugin: cloned Addressables bundles, binary catalog.bin keys and part icons on Unity 6000.3 IL2CPP

> Seven new track wheels (Tiger II, T-72 and M1 Abrams road wheels; BTR-152, BTR-90, Osa-AKM and M1128 Stryker tyred
> wheels) for the tank designer Sprocket, selectable under Tracks → Wheels with their own part icons. No mod loader:
> the mod clones the game's own wheel bundles with UnityPy, swaps in procedural Blender geometry and textures, adds
> keys to the binary Addressables `catalog.bin`, adds part JSON + localisation, and patches the part icon pack in
> `sharedassets0.assets`. Verified in the real game (editor, sandbox, photo mode) and packaged as
> install.bat/uninstall.bat.
>
> **Update 2026-10-30:** the same wheels now also run as a BepInEx plugin that changes no game file, built on the patched
> Sprocket Mod Loader, on the experimental branch. See "Moving to a BepInEx plugin" below. The data route above remains
> valid if you don't want a loader. The engine notes in this file are for experimental, where engines changed.

## Setup
- Sprocket, Steam app 1674170, Windows 11 x64: stable 0.2.55.5 (buildid 25392405, the public branch since 2026-09-21)
  for the data route; experimental buildid 25910892 (the branch's build since 2026-10-13; 0.2.56.2 going by Quality of
  Life's changelog) for the plugin. Unity **6000.3.21f1**, IL2CPP, `global-metadata.dat` version **39**, Addressables
  **2.9.1** with a **binary** catalog (`aa/catalog.bin`; `aa/settings.json` stays JSON). No anti-cheat; the data route
  installs no loader.
- **Multiplayer:** Sprocket has none at these builds (its Steam page lists Single-player only; small-scale multiplayer
  is on the developer's roadmap), so the mod only changes the user's own game. A design that uses the new wheels needs
  the mod wherever it's opened, community multiplayer mods included (not tested).
- UnityPy 1.25.4 (+ numpy, Pillow, etcpak for DXT/BC7), Blender 5.2 (`-b --factory-startup`), .NET 8 SDK for a small
  C# catalog tool referencing nesrak1's AddressablesTools source at commit 3dbc8210 ("add bin v3", 2026-08-09, which
  adds binary catalog version 3). The library is also on NuGet as `AssetsTools.NET.Addressables` (MIT per its
  nuspec), but the newest release there, 3.0.2 (2025-11-02), predates that commit: if it rejects a catalog with "Only
  versions 1 and 2 are supported", build from source.
- Game data: `Sprocket_Data/StreamingAssets/Parts/*.json` (≈259 open JSON part definitions),
  `StreamingAssets/Localization/en-UK/Parts/<name>.xml` (UTF-16), `StreamingAssets/aa/StandaloneWindows64/*.bundle`.
  Logs: `%USERPROFILE%/AppData/LocalLow/HD/Sprocket/Player.log`.

## Route and why
- **Asset-only first.** BepInEx 6 / Il2CppInterop were known-broken on metadata v39 / Unity 6000.3 at the time
  (BepInEx issues #1266/#1274, Il2CppInterop #283); the community QoL kit (Hans21223) notes the official be.788 freezes
  Sprocket 0.2.55.5 at the main menu and points to its own patched "Sprocket Mod Loader". A plugin for new wheels would
  still have to load extra bundles, register parts and add icons at runtime — the same work as the data route plus a
  dependency on an unofficial loader. The data route needs nothing installed in the game folder.
  2026-10-30, build 25910892: in practice the plugin turned out simpler to keep working than patching game files, because
  a game update no longer overwrites the mod. Pick it if your users accept installing the loader.
- Only-JSON (new part pointing at existing `meshGuid`s) gives no new models; replacing an existing wheel's bundle
  replaces instead of adds. Adding catalog keys is what makes truly new parts possible. Sprocket's own mod support
  covers part definitions, eras and technology limits so far; meshes, textures, audio and scripting are still to come
  (the developer's Roadmap Update #3, 2025-11-05). Once those land, the official route replaces this one.
- Not tried: [SprocketSDK](https://github.com/Neemogudmen/SprocketSDK) (MIT), another BepInEx kit, builds `VehicleMesh`,
  `Mesh` and `Texture2D` objects at run time from a mod's own `.obj` and `.png` files and serves them through a custom
  Addressables provider, so no cloned bundle is involved (its `docs/assets.md` and `docs/how-sprocket-works.md`; checked
  by its author on 0.2.55.5). Worth a look first for anything you plan to share (see "What ships").

## How the game works (what we had to learn)
- **Wheel part JSON** (`Parts/*.json`): tag `trackWheel` = road wheel palette (`sprocketWheel` = drive sprockets).
  Component `trackWheel.info`: `meshGuid`, `materialGuid` (Addressables keys, 32 hex), `toothed`, `diameter` (mm,
  usually 1000 = normalised), `width` (200 for most), axle/belt fractions; optional `iconModel`. `name` is the key for
  localisation XML and for the icon.
- **Mesh bundle** (`vehicle_assets_<x>mesh_<hash>.bundle`): one ScriptableObject `VehicleMesh` (`levelsOfDetail[3]`,
  `shadowProxy`, `interactionMesh` = shared 66-vertex `Roadwheel_Collider`, `damageModelMesh`=0) + the Mesh objects.
  Geometry is normalised: disc in XY, **radius 0.5**, axle along Z, **width 0..0.2**, **visible face at +Z**.
  Vertex layout: one stream, 12 floats (pos3, normal3, tangent4, uv2), 16-bit indices, one submesh.
  Unity 6 adds `m_MeshLodInfo` (left as in the template).
- **Material bundle**: ScriptableObject `VehicleMaterialConfiguration` (`flags`, `slot`, `materialSource`,
  `baseColourMap`, `armMap`, `normalMap`, `dpmMap`) + 4 textures: BaseColour 512² DXT1, ARM 512² DXT1
  (AO/roughness/…), Normal 1024² DXT5nm (X in A, Y in G), DPM 1024² BC7. **DPM.B is the paint mask** (rubber 0,
  painted metal 255 — checked by sampling the air-tyre wheel's textures at its mesh UVs). No shaders in the bundle.
  **`flags = 2` on every wheel that has rubber** (paint masked by DPM.B); the plain metal 6-hole wheel has 0.
- **Catalog**: every wheel asset has three keys — the GUID, the address (`6HoleWheelMesh`) and the bundle file name —
  a `BundledAssetProvider` location whose deps are its bundle plus the shared `..._monoscripts_...bundle`.
  Bundle locations carry `AssetBundleRequestOptions` (Hash, Crc, BundleName = AssetBundle name without `.bundle`).
  CRC 0 and Hash 0 work for local mod bundles.
- **Part icons are not rendered at runtime.** They are pre-baked 128² Sprites in the SpriteAtlas `IconAtlas`
  (`sharedassets0.assets`), and the game finds them through a MonoBehaviour **`CorePartIconPack`** in the same file:
  a folder string (`Assets/Textures/Icons/Parts`) followed by a list of `{string name, PPtr<Sprite>}` (193 entries).
  The file has no typetrees, so that MonoBehaviour must be patched as raw bytes (length-prefixed, 4-aligned strings,
  PPtr = int32 fileID + int64 pathID). A part whose name isn't in the list shows a white square.
- Mesh conventions in the game's own wheels: `cross(v1-v0, v2-v0)` points along the vertex normal for 100% of
  triangles, and `bitangent = cross(normal, tangent) * tangent.w`. Blender data maps 1:1 (same XYZ numbers, same
  triangle order, `w = loop.bitangent_sign`) — no axis swap or winding flip needed for this game's wheel space.

## Engines (experimental build 25910892)
Stable and experimental differ here: 0.2.56.1 added the inline and radial layouts (its Steam post). On stable the
model sits inside `combustionEnginePart.json` and is chosen through `enginePartGuid` on the `powertrain` parts (a new
`powertrain` part appears in Powertrain > System at once; JSON `width`/`height` act as divisors of a size the game
computes). On experimental neither applies:
- The model is its own part: `vEngineModel.json`, `inlineEngineModel.json`, `radialEngineModel.json`, component `engineModel`
  with `layout`, `materialGuid`, `cylinderSegmentMeshGuid`, `startMeshGuid`, `outputMeshGuid`, `baseCylinderCount`,
  `cylindersPerSegment`, `maxCylinderCount`, `cylinderDisplacement`, the three segment lengths, `output*Offset` and
  `centreOfMassHeight`. Cylinders per segment: V 2, inline 1, radial 1.
- Each mesh asset has 2-3 LODs, a shadow proxy and a collider; `interactionMesh` and `damageModelMesh` both point at the
  collider, so a new shape needs its own collider. Collider vertex stride differs (V 56, radial 40, inline 48).
- Layouts in the UI are closed: enum `Sprocket.Powertrains.Engines.EngineLayout { None, V, Inline, Radial }`, static
  `CombustionEngineComponentEditor.EngineLayoutOptions`, `EngineRules.*EngineLayoutTechName`, tech files of type
  `vEngineLayout` and so on. A fourth layout can't be added with data alone. Open: whether a plugin can (see Open questions).
- The engine is selected in the editor with X-ray on, then right mouse on it; the layout control is in its side panel.

## Moving to a BepInEx plugin
**Loader.** The official BepInEx be.788 crashes or hangs on Sprocket's Unity 6000.3.21f1 native code (the loader's
`WHY-THE-OLD-LOADER-FAILED.md`). Install be.788 (`BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.788+5b766a3`), then copy the
Patch folder of [Sprocket Mod Loader](https://github.com/Hans21223/Sprocket-Mod-Loader) 1.2.3 (LGPL-3.0, with source;
five DLLs for `BepInEx/core`) over it before the first start. Its README says it supports Sprocket builds on Unity
6000.3.21f1, finds its hook targets at each start and was tested on 0.2.55.5, 0.2.56.0 and 0.2.56.1. It also ran on
experimental 25910892: interop generated (261 assemblies), `Chainloader startup complete`, menu and sandbox fine, no
errors, normal frame rate. Plugins target net6.0 and compile against `BepInEx/core` and `BepInEx/interop`. Renaming
`winhttp.dll` to `winhttp.dll.disabled` turns the loader off.

**Plugin layout** (`BepInEx/plugins/<mod>/`), and how each piece reaches the game:
- `aa/`: the cloned bundles from build step 2. They're still clones of the game's bundles: see "What ships".
- `catalog.bin`: a catalog holding only the mod's keys, made by cloning the stock entries. Bundle InternalIds use
  `{UnityEngine.AddressableAssets.Addressables.RuntimePath}\..\..\..\BepInEx\plugins\<mod>\aa\<file>`, so no
  `InternalIdTransformFunc` is needed. Give it its own `LocatorId`, and set Crc 0 on the shared `*_monoscripts_*.bundle`
  dependency so a rebuild of that bundle under the same file name doesn't invalidate the catalog (see Open questions).
  Loaded with `Addressables.LoadContentCatalogAsync` inside the parts postfix below; status `Succeeded`, and the game's
  own key lookups find the assets. The
  [Etrian Odyssey 2 HD note](../etrian-odyssey-2-hd/etria-inside-eo2-bepinex-protected-il2cpp.md) loads a second catalog
  with the same call on Unity 2020.3 IL2CPP.
- Parts: postfix on `PartDefinitionIO.LoadAllPartDefinitions`, deserialize with `DeserializePartDefinitionJSON(text, __1)` and
  append to `__result`. Appending keeps stock parts first, so defaults don't change.
- Names: `PartLocalizationIO.GetPartLocalization` never fires. Postfix `Localizations.GetLocalizationFilePath` (return your XML)
  and `Localizations.Exists` (return true for your parts).
- Icons: postfix `GameIcons.GetOrDefault` and `GameIcons.TryGet` and return your sprite (`ImageConversion.LoadImage` +
  `Sprite.Create`, `hideFlags = HideAndDontSave`). Keys are bare part names.

**Scouting first paid off.** A read-only plugin with logging postfixes showed in one run which methods really fire on this
build. Fired: `LoadAllPartDefinitions` (once), `GameIcons.AddIcons`, `GetOrDefault`, `PartDefinitionDatabase.Get`,
`SetEngineLayoutRevertable`, `EngineModelDefinition.GetLayoutFromKey` (once per layout). Patched fine but never fired:
`LoadDefaultPartDefinitions`, `GetPartLocalization`, `GetLayoutKey`, `EngineRules.GetTechID`, `GetLayoutIndex`,
`ExtractPropertySettings`. These look inlined by IL2CPP, though some may simply not have been reached. A successful
`harmony.Patch` proves nothing about the patch ever running.

## Build steps
1. **Models** (Blender, procedural): lathe profiles for tyres/rims/discs, hubs as closed solids through the axis
   (a pole vertex, not a hole), tread rows lofted along the tyre profile and clamped to the tyre width, booleans only
   on closed disc solids before joining. Material index 0 metal / 1 rubber; smart UV; Cycles bakes an ID map and AO;
   LOD1 = decimate 0.4; LOD2 = drop faces flagged `detail` (tread, nuts) then decimate 0.25; Shadow = LOD1; export
   per-corner arrays (npz). Also render a 128² icon (ortho, beige, transparent) for the atlas.
2. **Bundles** (UnityPy): load the 6-hole wheel's mesh and material bundles from the user's install, write vertices/
   indices/AABBs into the four meshes, write textures with a full mip chain (inline, drop the `.resS` node), rename the
   CAB (`CAB-<md5>`), `m_Name`/`m_AssetBundleName`, `m_Container` path and the ScriptableObject names, set material
   `flags=2`. Validate winding and tangent conventions per LOD before saving.
3. **Catalog** (C# + AddressablesTools): read `catalog.bin`, clone the template asset's location under the new GUID
   and address, point dep[0] at a cloned bundle location (new file name, BundleName, size, Crc 0, Hash 0), add the
   bundle-file key, write it back. An unchanged round trip gives a byte-identical size and an identical dump.
4. **Parts**: copy `6HoleWheel.json`, new uuid/name/keys; add `Localization/en-UK/Parts/<name>.xml` (UTF-16).
5. **Icons**: in `sharedassets0.assets` add per wheel a Texture2D (RGBA32 128², inline) and a Sprite cloned from the
   6-hole sprite (full-rect quad, `m_RD.texture` = new texture, new `m_RenderDataKey`), append the sprite to the
   atlas (`m_PackedSprites`, `m_PackedSpriteNamesToIndex`, `m_RenderDataMap` entry pointing at the new texture), and
   append `{name, PPtr}` to `CorePartIconPack`'s list.
6. **Installer**: back up `catalog.bin` and `sharedassets0.assets` as `*.orig`, always rebuild both from the originals,
   copy bundles/JSON/XML, record sha1s of the patched files; if the game later replaces a file (update/verify), treat
   the new file as the original instead of restoring the old backup.

**What ships.** A cloned bundle is the game's own bundle file with our meshes and textures written in: everything we
don't overwrite (the `VehicleMesh` and `VehicleMaterialConfiguration` objects, the `Roadwheel_Collider` that
`interactionMesh` points at, `m_MeshLodInfo`) is still the 6-hole wheel's. So the clones stay on the machine they were
built on and aren't shared, friends included, like the patched `catalog.bin` and `sharedassets0.assets` and their
`*.orig` backups. That goes for the plugin's `aa/` folder too, and for engine models cloned from the game's engine
bundles, even with their own collider. The clones built for this note stayed on the author's machine and in their
private repository (public for about four minutes on 2026-10-29, with no downloads), so nobody else got them. A shared
installer or plugin carries only our own data (the npz arrays, textures, icons, part JSON and XML) and builds the
bundles from the player's own install (step 2), the way the installer already rebuilds the catalog and the icon pack,
or skips bundles altogether as SprocketSDK does.
`um publish check` won't catch a clone: it fails only files byte-identical to the game's, and warns only about engine
archives over 5 MB.

## Verification
- Oracle: the running game. Sandbox (Flat) → Tracks → right-click a road wheel (selects the track) → Wheels tab →
  pick each wheel; screenshots via `um win shot`, Player.log checked for exceptions (none). All six wheels of the first
  build (the M1128 Stryker wheel came later) load and render on the track; the game pairs road wheels itself (Per
  axle); icons show in the palette; photo mode (P) for outline-free close-ups. The user checked camouflage paint and
  wheel rotation in their own session.
- Offline oracles: catalog round-trip dump diff; winding/tangent statistics vs the game's meshes; texture channels
  sampled at the game mesh's UVs; installer uninstall → byte-identical originals; `um publish check` PASS.
- Not verified: battles/physics with the new wheels beyond the editor; other game builds; a design with the new wheels
  opened without the mod.
- Plugin (2026-10-30, experimental 25910892): the human checked parts, models, names, icons and a saved vehicle in game;
  the log showed the catalog `Succeeded` and all seven wheels added. Not verified: the plugin on the stable branch.

## Gotchas
1. **Wheels look hollow, tyres show only their tread.** **Cause:** triangle winding inverted (I reversed it assuming
   a mirror from Blender). **Fix:** compare against the game's meshes — `cross(v1-v0,v2-v0)` must agree with the
   normal (game: 100%, ours were 0%); keep Blender's order. Same check for tangent `w` (bitangent = cross(n,t)·w).
2. **Rubber painted like metal.** **Cause:** `VehicleMaterialConfiguration.flags` copied from a metal-only template (0).
   **Fix:** `flags = 2`, with DPM.B = 0 on rubber.
3. **White icon squares after adding sprites to IconAtlas.** **Cause:** the game looks icons up in
   `CorePartIconPack`, not by `SpriteAtlas.GetSprite`. **Fix:** also append `{name, PPtr<Sprite>}` there. Found by
   scanning every object's raw bytes for PPtrs to two known wheel sprites.
4. **Texture edits silently lost (7 KB bundle).** **Cause:** UnityPy `read_typetree()` after `save_typetree()` on the
   same object returns the original data, so a second edit overwrote the first. **Fix:** one read + one save per object.
5. **Holes vanished / a cutter stayed visible.** **Cause:** EXACT boolean on a joined, self-overlapping (non-manifold)
   mesh. **Fix:** cut holes in the closed disc solid before joining parts.
6. **All parts became metal after join.** **Cause:** joining objects without material slots resets `material_index`.
   **Fix:** add both slots to every part before `join`.
7. **Far LOD of tyres became slivers (80% winding agreement).** **Cause:** heavy decimation of hundreds of tiny tread
   blocks. **Fix:** delete faces flagged as detail (tread, nuts) for LOD2, decimate the rest.
8. **Tread stuck out sideways over the shoulder.** **Cause:** lug top offset along the shoulder normal. **Fix:** clamp
   Z to the tyre body and use low, separate blocks (matches real cross-country tyres).
9. **Cloned bundles need their own identity (precaution, not hit here).** **Cause:** Unity refuses to load a second
   bundle whose CAB name or `m_AssetBundleName` matches one already loaded, and a clone keeps the template's.
   **Fix:** we renamed both (`CAB-<md5>`, new 32-hex bundle name) from the first build, so this never failed for us;
   path IDs inside the bundle can stay the same.
10. **Editor automation:** select = right mouse; Esc opens the pause menu; the scroll wheel over a selected track
    changes fields in the side panel (it moved Wheel array → Forward; undo with Ctrl+Z); scroll-zoom only reacts after
    a real mouse move over the viewport; orbit is middle-drag (WinDrive has no middle button — use a tiny
    `mouse_event` helper); photo mode (P) hides selection outlines.
11. **White icons after writing to `GameIcons.lookup` from a plugin.** `lookup[key] = new GameIcons.Icon {...}` raises the
    dictionary count, but `GetOrDefault` returns null, even for a stock sprite. **Cause (not pinned down):** probably the
    interop write: `Icon` is a struct, and it doesn't seem to reach the native generic dictionary intact.
    **Fix:** don't write; postfix `GetOrDefault`/`TryGet`. Giving one part a stock sprite separated "lookup broken" from
    "my sprite broken" in a single run.
12. **`AsyncOperationHandle<T>` won't compile as a struct.** **Cause:** in interop it's a class.
    **Fix:** no `?`, no `.Value`.
13. **Parts doubled or stale after switching routes.** **Cause:** the patched-files install is still in place.
    **Fix:** remove it before the first plugin run.

## Assets
All geometry procedural (bpy/bmesh): lathe profiles, lofted tread rows, hex nuts, radial ribs, boolean holes.
Textures built from a baked material-ID map + AO and per-channel medians of the game's own wheel textures (painted
metal from the 6-hole wheel, rubber from the air-tyre wheel), plus light noise; flat normal map. Icons rendered in
Blender, cropped, contrast-stretched and colour-matched to the mean colour of the game's wheel icons.

## Cost and time
One long session (recon to the installer, three feedback rounds from the human).

## Open questions
- A game update overwrites `catalog.bin` and `sharedassets0.assets` on the data route; the installer rebuilds from the new
  files, but a format change (Addressables/Unity version) would need the tools updated. The plugin route avoids this.
- The plugin's catalog names the game's `*_monoscripts_*.bundle` by file name. Crc 0 covers a rebuild under the same
  name; if an update changes the hash in that name, the catalog needs the new name. Not tested.
- A fourth engine layout from a plugin is untested. The options array has a setter and `GetLayoutFromKey` can be patched, but
  the enum value must also survive `GetLayoutKey`, `GetTechID`, `GetLayoutIndex` and the model lookup, and those may be
  inlined. Fallback: replace the meshes of an existing layout from the plugin.
