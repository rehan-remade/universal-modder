---
kind: game
title: "A new civilization with an animated 3D leader scene on a stock leader rig in Civilization V"
game: "Sid Meier's Civilization V"
games_also: []
game_version: "1.0.3.279 (final patch), Brave New World, Steam app 8930, Windows 11; DX9 and DX11 renderers"
platform: windows
engine: native
route: data
tools: ["Civilization V SDK (CvGameCoreSource, Nexus Firaxis.Framework.Granny DLLs)", "gr2tool (custom C# on the SDK's Granny wrappers, x86 + x64 builds)", "Blender 5.2", "Python (numpy, pillow, lupa)", "xatlas", "ffmpeg", "um win (launch/shot/drive/record)"]
anti_cheat: "none; all testing single-player"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["@blackhellvelz-prog"]
date: 2026-10-06
links: []
tags: [civilization, leaderhead, granny, gr2, animation-retargeting, light-rig, dx11, lua, xml, sql, sound, ui]
---

# A new civilization with an animated 3D leader scene on a stock leader rig in Civilization V

> A playable civilization ("Demons") with:
> - Lua gameplay systems: mid-game emergence, a terrain plague, a unique building and a unit;
> - its own 2D art, ground decals, and a unit model on a stock skeleton;
> - a fully animated 3D diplomacy leader. The leader is a user-supplied model retargeted onto Nebuchadnezzar's
>   stock leader rig, using all 39 of his animations, his voice slowed down, and a user-supplied 3D throne and
>   location.
>
> It's a pure data/Lua/art mod (no DLL). It's verified in the real game on DX9 and DX11 at max settings:
> screenshots, video, a game-only audio recording, and Lua.log.

## Setup
- **Game:** Steam build 1.0.3.279 (2014-11-19), all DLC. It's 32-bit, with three exes:
  - `CivilizationV.exe` (DX9);
  - `CivilizationV_DX11.exe`;
  - `CivilizationV_Tablet.exe`.
- **SDK:** "Sid Meier's Civilization V SDK" (Steam). We used:
  - `CvGameCoreSource` (the C++ of the shipped gameplay DLLs);
  - `Nexus\x86\Firaxis.Framework.Granny*.dll` (managed wrappers around RAD Granny, with the native Granny inside).
- **Our tools:**
  - **gr2tool**, a C# tool compiled with `csc` against those DLLs. It's built twice, x86 and x64, each next to its
    own copy of the Nexus DLLs.
  - **Blender 5.2** (FBX/GLB import, bakes, previews).
  - **Python** for packing, textures, retargeting maths and the validator.
  - **lupa** (Lua 5.1) for headless Lua tests of the mod scripts.
- **User data:** `Documents\My Games\Sid Meier's Civilization 5\`:
  - `MODS\`;
  - `Logs\` (needs `LoggingEnabled = 1` in `config.ini`);
  - `cache\Civ5DebugDatabase.db`, the merged SQLite of the loaded ruleset;
  - `ModdedSaves\`.

## Route and why
A **data mod**: XML/SQL for the database, Lua addins for the gameplay, and art loaded by name from the mod's VFS.
- **No DLL:** the official GameCore source in the SDK answered every rules question, so no DLL was needed.
- **No exe patching:** the renderer and the asset loader live in the closed exe and were never touched.
- **Art on stock templates:** all art goes into copies of stock `.gr2` files whose meshes/materials are swapped. The
  game's leader shaders, state machines and animation graphs are then reused by name.

## How the game works (what we had to learn)

### Layers
- **Gameplay rules** live in `CvGameCore_Expansion2.dll`. The SDK source matches the shipped DLLs: each
  `CvDllVersion.h` GUID is present byte-for-byte in its DLL.
- **Game data** is XML/SQL merged into a SQLite cache.
- **UI** is Lua 5.1 + XML.
- **Art and audio** are in `.fpk` packages under `Resource\{Common,DX9,DX9_Low}`. There is **no DX11 asset set**:
  only the shader path differs.

### Packages and models
- **`.fpk` layout:**
  - header: `u32 6, "FPK_", u16 0, u32 count`;
  - per entry: `u32 namelen, name, pad to 4, u64, u32 size, u32 offset`;
  - data stored uncompressed.
- **`.gr2`:** RAD Granny revision 7 (Oodle1-compressed sections). Strings in stock files are 32-bit hashes of entries
  in the package's `.gsd` string database: CRC-32 without the final inversion.
  - The SDK's managed loader reads models.
  - It **refuses files without meshes or animations** (cameras, light rigs). Read those natively instead:
    `GrannyReadEntireFileFromMemory` + `GrannyGetFileInfo`.
  - To write such a file: `GrannyBeginFile` → `BeginFileDataTreeWriting` → `WriteDataTreeToFileBuilder` →
    `EndFile`, with the source's magic and type tag.
- **x86 vs x64 saves:** files saved by the x64 Granny library are **invisible as units**. Ground decals load them
  fine. Save unit and leader art with the x86 build.
- **Unit art** is one `.fxsxml` (Mesh, Animations with event codes, Textures, BoneUsage, TimedTrigger `.ftsxml`,
  AnimGraph `.dge`, StateMachine `.fsmxml`). Animations are found by name in the game's packages.
- **Texture names are stored twice in materials:**
  1. in the Granny texture maps;
  2. as strings in the material's FGX shader-parameter data (ExtendedData).

  The game binds the **second**. Change both, or the model draws with the template's textures.

### Leader scenes
- **The scene XML:** `Leaders.ArtDefineTag` names it. Its root is
  `<LeaderScene lights= camera= ColorKey= cubemap_prefix= FallbackImage=>`, with these children:
  - `LineLightSettings`: flicker for line lights;
  - `HackLightSettings`: one extra directional light;
  - one `LeaderObject`;
  - any number of `BackgroundObject`.

  Each child names an `.fxsxml`. `lights=` may name a light-rig `.gr2` directly.
- **FallbackImage** is shown instead of the 3D scene when "leader quality" is minimum (`UseScreenShots = 1`).
- **ColorKey:** a 1024x576 `.tga` whose top 32 rows hold a 32-tile LUT (x = red, y = blue, tile = green).
- **Cube maps:** `<prefix>_Environment_diffuse/reflection.dds`, DXT1, 128x128, 8 mips. The diffuse one is the
  scene's ambient term, bound per material ("Civ5LightingTextures").
- **Background meshes:** copies of stock scene meshes keep their shaders:
  - lit: shader "Leader", maps Diffuse/Normal/SREF/Irradiance/Environment;
  - matte cards: "Leader_Opaque_Matte".

  One mesh holds at most 65,536 vertices (uint16 indices). Split large models.
- **Camera rig:** bone 1 is the camera; its ExtendedData holds the horizontal FOV in radians. Frames are 16:9.
- **Light rig:** one skeleton per light. The record is the bone's ExtendedData `LightInfo`, a 3ds Max export: near/far
  attenuation, shadow flags, colour, intensity…
  - **Line lights** are lights under a dummy parent. `LineLightSettings` must only name those (see Gotcha 4).
  - **Adding a light:** deep-copy an existing light's model + skeleton (with its record), rename it, and append it to
    the file's Models and Skeletons arrays. The game uses it.
- **InitialPlacement:** a leader model's `InitialPlacement` (in `granny_model`) places it in the scene. A stock leader
  rig can sit anywhere: we used translation, Z rotation and uniform scale.

### Leader animation and props
- **Animations** are per-bone curves bound by bone name (track group = model name). The stock
  `LEADER_FULL_STATE.fsmxml` and `*_GRAPH_LEADER.dge` drive them by the event codes listed in the leader's
  `.fxsxml`.
- **Retiming:** works by scaling every curve's knots plus Duration/TimeStep, per curve format:
  - K16u/K8u: the uint16 `OneOverKnotScaleTrunc`, the top half of a float;
  - D4n: real32 `OneOverKnotScale`;
  - K32f: the knot array.

  The stock state machine still drives the retimed files.
- **Proportions:** Nebuchadnezzar's rig is a baked control rig.
  - Lengths are constant x-translations of driver bones.
  - Chain roots (`ARM_<s>_PARENT_jor`, `HEAD_SPOT_PARENTER_jor`) carry animated world positions.
  - Apply the same deltas to the model's rest pose and to every animation, and the stock animations drive the new
    proportions.
- **Skinning a rigid slot:** a mesh can take another mesh's vertex type and get new bone bindings. That turns a rigid
  slot (his helmet) into a skinned one: our head with jaw/mouth bones.
- **Props:** a leader's prop (his chalice) is a **separate model** (`CUP_Point`) with one bone and a rigid mesh.
  - Only the INTRO animation moves it: held, thrown, landed.
  - Every other animation keeps it constant on the floor.
  - Its track is independent of the hand. Retarget it yourself (Gotcha 10).
  - It needs its own `InitialPlacement`.
- **INTRO plays only at first contact:** the AI's first greeting when it meets the human (`Team:Meet(t, false)`). A
  player-opened diplomacy screen right after meeting replaces it with the default greeting.

### Sound
- **Speech:** `Audio_Sounds` (`SoundID`, `FileName`, `LoadType DynamicResident`) + `Audio_2DSounds` (`ScriptID`,
  `SoundType GAME_SPEECH`) rows in mod XML, `.mp3` files in the VFS, and `ReloadAudioSystem` 1 in the `.modinfo`.
- **Triggers:** the leader's `TimedTrigger` plays ScriptIDs by event code and time.

### Gameplay facts (all from the SDK source, verified in game)
- **Combat death:** `UnitPrekill` then `UnitKilledInCombat`. There is no `CombatResult` event.
- **`CityCaptureComplete`** fires only if the city survives.
- **Saved state:** `Player`/`Plot:SetScriptData` are saved; `City` has none.
- **Optional args:** `luaL_optint` flags (`City:CanConstruct`, `CanTrain`) need numbers, not booleans.
- **Reviving a slot:** a dead player slot can be revived with `Player:InitCity` (its first city gets the palace).
  `Game.AddPlayer` is never safe. `Game.SetAIAutoPlay` kills the active player's units without an observer slot.
- **Diplomacy text:** `GetDiploResponse` pools a leader's rows with GENERIC ones weighted by Bias, and finds tags only
  through `Language_en_US`. An en_US row is required even in a Russian game.
- **Civ list:** the front end's `UniqueBonuses.lua` breaks the list for a civ with fewer than two unique items. A
  building class without a default building, overridden by one civ, counts as one.
- **Ground decals:**
  - the game binds their textures from the material's FGX parameters (`BaseTextureMap`/`HeightTextureMap`);
  - `ArtDefine_Landmarks.Scale` is honoured;
  - they need `ReloadLandmarkSystem` 1;
  - hex row neighbours are 64 units apart.

## Build steps
1. **Rules:** XML/SQL rows (Civilizations, Leaders, Traits, Units, Buildings, Diplomacy responses, art defines) plus
   Lua addins. A Python build script writes the `.modinfo` with MD5s and deploys the mod to `MODS\`.
   - Stamp the `.modinfo` mtime on every deploy (Gotcha 12).
   - Put a version in the folder name so the human can see which build is installed.
2. **Unit and leader art:**
   1. Skin the model to a stock skeleton in Blender (fit the bones, transform vertices fit-bone → stock-bone).
   2. Pack raw vertex/index buffers in the template mesh's own layout (e.g. stride 42/53 skinned, 34 rigid).
   3. In gr2tool, `replace-meshes` a **copy of the stock .gr2**. Spec lines include `mesh`, `blank`, `vertextype`,
      `bindings`, `bonepos`, `placement` and `material` (a mesh gets its own deep copy of a shared material).
   4. Retexture both the maps and the FGX strings.
3. **Leader animations:** `stretch-anim` (retime + bone-position edits + time-varying track offsets) on every stock
   animation. The leader `.fxsxml` = the stock one with our model, animations, textures and trigger file.
4. **Light rig:** `lights` (move, recolour, re-range, add lights) on a stock rig.
5. **Scene:**
   - throne/location meshes go into copies of the stock lit scene meshes;
   - the painting goes on a matte card;
   - the scene XML sets camera, lights, cube maps (tinted copies of a stock pair) and a ColorKey.
6. **Test** before every in-game run (see Verification).

## Verification
- **Before the game:**
  - the validator applies the mod's XML to copies of the game databases and resolves every model/texture reference
    in the scene;
  - Lua unit tests run under lupa: 4 suites, 355 tests.
- **In game:** driven with `um win drive/shot/record` in a 1600x900 window.
  - Settings are backed up and restored around every test.
  - Every check is on high/max settings: the human plays DX11 at max, and that path differs (Gotcha 1).
- **Seen in game:**
  - scene neutral and at war;
  - first-contact INTRO (video, 2 fps frames: prop in hand → thrown → on the floor);
  - two stock leaders after ours;
  - save → full exit → load;
  - `Lua.log` with 0 Runtime Errors.
- **Speech:** a game-only audio recording was cross-correlated with our `.mp3` files (0.93–0.98) to prove the mod's
  voice plays, not the stock one.
- **Animation edits:** sampled back through Granny itself (`GrannySampleModelAnimations` + `GrannyBuildWorldPose`)
  and compared with the intended curves (≤ 0.4 in).
- **Not verified:**
  - multiplayer;
  - the Tablet exe;
  - DX9 at max settings after the last lighting change.

## Gotchas
1. **Scene fine on DX9, mostly black at max settings.**
   - **Cause:** DX11 with `EnableShadows = 1` (max) casts shadows from the rig's lights, and DX9 tests had shadows
     off. A shadow-casting light left every background model black. That happened even after the light was moved to
     an unobstructed spot; the leader object itself stayed lit.
   - **Fix:** no shadow-casting lights on scenes whose background is your own meshes. Before that, the light also
     sat inside the throne's crest: check light visibility with ray casts whenever a light moves.
2. **Background barely lit in either renderer.**
   - **Cause:** the scene's ambient comes from the diffuse cube map, and a dark tint leaves far geometry at the
     colour key's black level.
   - **Fix:** add dedicated low lights near that geometry (copies of an existing rig light). Don't brighten
     everything.
3. **DX11 exe started directly comes up as DX9.**
   - **Cause:** the exe hands over to Steam, which starts the default launch option.
   - **Fix:** `steam://launch/8930/dialog` starts the last chosen option (DX11 once chosen) without asking.
     `steam://rungameid/8930` starts the default.
4. **Every light in the scene went out.**
   - **Cause:** `LineLightSettings` named a root light (one without a dummy parent).
   - **Fix:** only name line lights there.
5. **A light near a model lit nothing close to it.**
   - **Cause:** 3ds Max-style near attenuation fades light *in* from the source.
   - **Fix:** turn near attenuation off.
6. **Unit model invisible in game.**
   - **Cause:** saved by the x64 Granny library.
   - **Fix:** save with an x86 build.
7. **Model drew with the template's textures.**
   - **Cause:** the material's FGX parameter strings still named the old files.
   - **Fix:** replace those strings too.
8. **Prop got the head's textures.**
   - **Cause:** the prop mesh and our head (a re-used helmet slot) shared one material object.
   - **Fix:** give the mesh a deep copy of the material before retexturing.
9. **Retargeted leader: hands off the armrests.**
   - **Cause:** the stock seated pose puts the hands ~20 cm beyond a short armrest.
   - **Fix:** measure the forearm/hand undersides over the idle animations and fit the throne. Stretch the armrests
     forward, raise them per side, keep the throne symmetric.
10. **Thrown prop floats beside the hand, then lands off-screen.**
    - **Cause:** the prop's track was authored for the stock body. Our proportions moved the hand (here by a constant
      2–3 in), and the stock landing spot fell below our lower camera's frame.
    - **Fix:** a time-varying offset on the prop's position curve:
      - the hand delta while held;
      - a blend over the flight;
      - a resting offset chosen by ray-casting a screen point onto the platform.

      Quantized curves (D3K16uC16u) must be re-quantized after editing.
11. **INTRO never seen in tests.**
    - **Cause:** it plays only at first contact, and opening diplomacy right after `Meet` replaces it.
    - **Fix:** a debug button that only calls `Team:Meet(t, false)`.
12. **Rebuilt mod hidden from the Mods screen.**
    - **Cause:** the game caches mods by `.modinfo` file time.
    - **Fix:** touch the `.modinfo` on every deploy.
13. **Mod types missing in addins after an unmodded game in the same process.**
    - **Cause:** state from the earlier ruleset.
    - **Fix:** restart the game process between tests.
14. **"Retargeted" mesh shows dark patches around the mouth.**
    - **Cause:** a Meshy FBX imports flat-shaded, and the facets were baked into the normal map.
    - **Fix:** set `use_smooth = True` before baking.
15. **Blotchy textures at a distance on AI-generated models.**
    - **Cause:** ~20k tiny UV islands bleed at the mip levels the scene samples.
    - **Fix:** re-unwrap into large charts (xatlas on a smoothed copy) and re-bake the supplied PBR maps.
16. **Old screenshot fooled an automated wait.**
    - **Cause:** a file left over from the previous run satisfied the check while the game never started.
    - **Fix:** delete the file before waiting for a new one.
17. **Blender 5 can't open a supplied `.dae`.**
    - **Cause:** its Collada importer is gone.
    - **Fix:** an Assimp export is simple XML (one triangle list, all inputs on one index, Y up, `<unit meter>`), so
      read it in Python and weld positions to recover topology.

## Assets
- **Supplied by the human:**
  - the leader (a Meshy model with a Mixamo rig);
  - two thrones;
  - a location;
  - a unit model;
  - the 2D art sheets (generated images);
  - a demon-skull ring model, cut to a skull for the thrown prop.
- **How we treated the models:** never decimated. Re-unwrapped and re-baked where their atlases were unusable.
- **Voice:** the stock leader's lines through ffmpeg: slowed with `asetrate`, a rubberband sub-voice, bass, and a short
  echo. The animations were stretched by the same factor so the mouth stays in sync.

## Cost and time
About four days of agent sessions over the whole mod. The animated leader alone took two (retargeting, voice,
lighting, then the DX11 and prop fixes).

## Open questions
- **Why do shadow-casting lights blacken background models in DX11?** Hypothesis: the shadow cube map's depth range
  doesn't fit a scene this size (~24 units per metre).
- **Can a prop's rest *orientation* be changed?** That needs editing the D4n quaternion curves and the constant
  orientation in every other animation. Our prop lands showing its back.
- **Can the leader be lit for both renderers at once?** DX9's ambient makes the same rig brighter than DX11's.
