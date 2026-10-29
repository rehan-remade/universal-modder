---
kind: game
title: 'New wheel models for Sprocket without a loader: cloned Addressables bundles, binary catalog.bin keys and IconAtlas
  icons on Unity 6000.3 IL2CPP'
game: Sprocket
games_also: []
game_version: "Steam 1674170, buildid 25392405 (Sprocket 0.2.55.x), Unity 6000.3.21f1 IL2CPP, metadata v39, Addressables 2.9.1"
platform: windows
engine: unity-il2cpp
route: asset-only
tools: ["UnityPy 1.25.4", "AddressablesTools (nesrak1) @3dbc8210", "Blender 5.2 (bpy, Cycles bake)", ".NET 8 SDK", "Python 3.12"]
anti_cheat: none found by um scan; editor/sandbox only, no game code touched
status: released
agents:
- Claude Code (Opus 5.5)
humans: ["J1ND3R9"]
date: '2026-10-29'
links: ["https://github.com/nesrak1/AddressablesTools", "https://github.com/Hans21223/Sprocket-Quality-of-Life"]
tags: [vehicle-parts, wheels, addressables, binary-catalog, unitypy, spriteatlas, icons, procedural-models, blender]
---
# New wheel models for Sprocket without a loader: cloned Addressables bundles, binary catalog.bin keys and IconAtlas icons on Unity 6000.3 IL2CPP

> Six new track wheels (Tiger II, T-72, M1 Abrams road wheels; BTR-152, BTR-90, Osa-AKM tyred wheels) for the
> tank designer Sprocket, selectable under Tracks → Wheels with their own part icons. No mod loader: the mod clones
> the game's own wheel bundles with UnityPy, swaps in procedural Blender geometry and textures, adds keys to the
> binary Addressables `catalog.bin`, adds part JSON + localisation, and patches the part icon pack in
> `sharedassets0.assets`. Verified in the real game (editor, sandbox, photo mode) and shipped as install.bat/uninstall.bat.

## Setup
- Sprocket, Steam app 1674170, buildid 25392405, Windows 11 x64. Unity **6000.3.21f1**, IL2CPP,
  `global-metadata.dat` version **39**, Addressables **2.9.1** with a **binary** catalog (`aa/catalog.bin`;
  `aa/settings.json` stays JSON). No anti-cheat, no loader installed.
- UnityPy 1.25.4 (+ numpy, Pillow, etcpak for DXT/BC7), Blender 5.2 (`-b --factory-startup`), .NET 8 SDK for a small
  C# catalog tool referencing nesrak1's AddressablesTools source (commit 3dbc8210; the same code is on NuGet as
  `AssetsTools.NET.Addressables`, MIT).
- Game data: `Sprocket_Data/StreamingAssets/Parts/*.json` (≈259 open JSON part definitions),
  `StreamingAssets/Localization/en-UK/Parts/<name>.xml` (UTF-16), `StreamingAssets/aa/StandaloneWindows64/*.bundle`.
  Logs: `%USERPROFILE%/AppData/LocalLow/HD/Sprocket/Player.log`.

## Route and why
- **Asset-only.** BepInEx 6 / Il2CppInterop were known-broken on metadata v39 / Unity 6000.3 at the time
  (BepInEx issues #1266/#1274, Il2CppInterop #283); the community QoL kit (Hans21223) notes the official be.788 freezes
  Sprocket 0.2.55.5 at the main menu and points to its own patched "Sprocket Mod Loader". A plugin for new wheels would
  still have to load extra bundles, register parts and add icons at runtime — the same work as the data route plus a
  dependency on an unofficial loader. The data route needs nothing installed in the game folder.
- Only-JSON (new part pointing at existing `meshGuid`s) gives no new models; replacing an existing wheel's bundle
  replaces instead of adds. Adding catalog keys is what makes truly new parts possible.

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

## Verification
- Oracle: the running game. Sandbox (Flat) → Tracks → right-click a road wheel (selects the track) → Wheels tab →
  pick each wheel; screenshots via `um win shot`, Player.log checked for exceptions (none). All six wheels load and
  render on the track; the game pairs road wheels itself (Per axle); icons show in the palette; photo mode (P) for
  outline-free close-ups. The user checked camouflage paint and wheel rotation in their own session.
- Offline oracles: catalog round-trip dump diff; winding/tangent statistics vs the game's meshes; texture channels
  sampled at the game mesh's UVs; installer uninstall → byte-identical originals; `um publish check` PASS.
- Not verified: battles/physics with the new wheels beyond the editor; other game builds.

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
11. **`git push` / `gh` occasionally failed with `schannel: failed to receive handshake` / GraphQL `EOF`.** Transient;
    a plain retry worked.

## Assets
All geometry procedural (bpy/bmesh): lathe profiles, lofted tread rows, hex nuts, radial ribs, boolean holes.
Textures built from a baked material-ID map + AO and per-channel medians of the game's own wheel textures (painted
metal from the 6-hole wheel, rubber from the air-tyre wheel), plus light noise; flat normal map. Icons rendered in
Blender, cropped, contrast-stretched and colour-matched to the mean colour of the game's wheel icons.

## Cost and time
One long session (recon to release, three feedback rounds from the human).

## Open questions
- A game update overwrites `catalog.bin` and `sharedassets0.assets`; the installer rebuilds from the new files, but a
  format change (Addressables/Unity version) would need the tools updated.
- If a working BepInEx for this Unity version becomes standard, a runtime plugin could load a separate mod catalog
  (`Addressables.LoadContentCatalogAsync`) and add icon-pack entries without touching game files.
