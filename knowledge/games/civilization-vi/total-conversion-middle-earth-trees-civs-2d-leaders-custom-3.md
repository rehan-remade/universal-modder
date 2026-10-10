---
kind: game
title: 'Total conversion (Middle-earth): trees, civs, 2D leaders, custom 3D wonders, victory reskin'
game: Civilization VI
games_also: []
game_version: 'Civ VI 1.0.12.68 (Steam 289070, build 15296837), Gathering Storm ruleset'
platform: windows
engine: native
route: data
tools: ['Civilization VI Development Tools (SDK + SDK Assets, Steam)', 'Civ6AssetCooker_FinalRelease', 'FbxImporter_Release.dll (from the Asset Editor)', 'Blender 5.2', 'fal (nano-banana-2, trellis-2, birefnet/v2)', 'ffmpeg gfxcapture', 'sqlite3', 'custom SendInput mouse (PowerShell)']
anti_cheat: 'none (EOSSDK is Epic Online Services for 2K accounts, not anti-cheat); single player only'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-10'
links: ['https://forums.civfanatics.com/forums/civ6-creation-customization.538/']
tags: [total-conversion, data-mod, modinfo, sqlite, lua, tech-tree, custom-civ, 2d-leader, fallback-leader, wonder-3d, granny, fgx, asset-cooker, headless-sdk, victory-screen, autoplay, test-harness]
---
# Total conversion (Middle-earth): trees, civs, 2D leaders, custom 3D wonders, victory reskin

> "Ages of Arda" turns Civ VI (Gathering Storm) into Middle-earth with a plain `.modinfo` data mod:
> - nine eras, restructured tech and civic trees;
> - 8 civilizations with 14 leaders, shown as painted 2D portraits;
> - gunpowder and air units locked;
> - city-states, Great People, governors, religion, Eurekas and victories reskinned;
> - 52 of 53 world wonders with their own 3D models.
>
> The wonder models went concept image → image-to-3D → Blender, then into Firaxis' Granny `.fgx` format with no
> GUI, by calling the SDK's FBX importer DLL directly.
>
> All of it was checked in the running game, using real mouse input, screenshots, `Lua.log` and `Modding.log`, a
> 100-turn AI autoplay, and scripted test scenes that place wonders and force a victory.

## Setup
- **Game:** Windows 11, Civ VI 1.0.12.68 (Steam), Base + Rise and Fall + Gathering Storm, played on the GS ruleset.
  - Windowed at a 1920x1080 client size; every click coordinate below assumes it.
- **SDK:** Civilization VI Development Tools from Steam (Library → Tools).
  - "Sid Meier's Civilization VI SDK" holds `Civ6AssetCooker_FinalRelease.exe` and the Asset Editor.
  - "...SDK Assets" holds the pantries. The real pantry is `SDK Assets\Civ6\pantry`; DLC pantries are under
    `Civ6\DLC\*\pantry`.
- **Art and checks:**
  - Blender 5.2 (headless, `--background --python`).
  - ffmpeg for image work.
  - `sqlite3` for offline database checks.
- **Mod location:** `Documents\My Games\Sid Meier's Civilization VI\Mods\<Mod>\`. The game picks it up from there;
  enable it under Additional Content.
- **Logs:** `%LOCALAPPDATA%\Firaxis Games\Sid Meier's Civilization VI\Logs\`, mainly `Modding.log`, `Database.log`
  and `Lua.log`.
- **Debug database:** after a game starts, `...\Cache\DebugGameplay.sqlite` holds the merged gameplay database.
  Query it to confirm what really loaded.

## Route and why
- **The route:** an official data mod.
  - A `.modinfo` whose actions are UpdateDatabase (SQL/XML), UpdateText, UpdateIcons, UpdateColors and UpdateArt
    (a cooked `.dep`).
  - Plus ImportFiles and AddGameplayScripts for Lua.
- **Proxy-DLL hooks: no.** `um scan` reports "unknown native" and suggests them; that's wrong for this game,
  because data and Lua reach every system needed here.
- **ModBuddy: no.** The cooker is a command-line tool, so the whole pipeline is scripts. A generated modinfo
  (`dev/gen_modinfo.sh` from a manifest) avoids hand edits.
- **Custom 3D wonders:** the documented path is the Asset Editor importing from 3ds Max/Maya. The headless DLL
  route below replaces both.

## How the game works (what we had to learn)
**Databases and load order**
- There are two SQLite databases.
  - **Configuration** (FrontEnd) drives game setup. The civ and leader picker reads `Players` rows in the domains
    `Players:StandardPlayers`, `Players:Expansion1_Players` and `Players:Expansion2_Players`, with Portrait and
    PortraitBackground columns for the 2D art.
  - **Gameplay** (InGame) holds rules and text.
- Each action has a LoadOrder, and later wins. Text is one `LocalizedText` table keyed by (Language, Tag).
  `<Replace Tag Language>` rows override base text.

**Tech and civic trees**
- Layout is derived, not stored: the column is the node's cost rank within its era, and the row is `UITreeRow`.
- Prerequisites must cost less than the node that needs them.
- **Never delete base TECH_/CIVIC_ rows.** Boosts, AI and modifiers reference them. Re-link the prerequisites and
  rename the text instead.

**Units**
- Gunpowder and air units can be locked by giving them a `TraitType` that no civ has (e.g. `TRAIT_ARDA_DISABLED`).
  Then fix `ObsoleteTech` / `MandatoryObsoleteTech` on the units left playable, so nothing upgrades into a locked
  unit.
- New units: `INSERT ... SELECT` from a base unit, and clone its `Units.artdef` entry for the art.

**Civs and leaders**
- New civs and leaders can reuse existing trait kits.
- To have only your own civs in setup, delete the other `Players` rows in all three domains. The game then offers
  only yours.
- Civs need citizen names (male and female, classic and modern; base civs have 10 of each). See Gotcha 6.

**2D leaders (no 3D)**
- An entry in `ArtDefs/FallbackLeaders.artdef` per leader points at a BLP texture.
- The diplomacy screen draws it with an `Image` control (`FallbackLeaderImage`), centred at 3/4 of screen width and
  scaled to screen height.
- The 3D leader scene is absent, so anything the image doesn't cover is **black** (Gotcha 9).
- Loading screen and setup use `LoadingInfo.ForegroundImage` / `BackgroundImage` and `Players.Portrait` /
  `PortraitBackground` (UI textures by name).

**Cooking 2D art without ModBuddy**
- PNG → DDS (a small C# writer: uncompressed RGBA plus mips) → `.tex` / `.xlp` / `.artdef` / `.Art.xml`.
- Then `Civ6AssetCooker_FinalRelease.exe` in its three modes: `XLP` → BLP, `ArtDef`, `Dependency` → one generated
  `<Mod>.dep`, listed under UpdateArt.
- The cooker accepts several `--pantry`; pass the SDK Assets pantries so cloned base assets resolve.

**Wonder models**
- A wonder model is a `WonderMovie` asset: `.geo` (XML mesh list) + `.fgx` geometry, and `.anm` + `.fgx`
  animation (the build-up, 500 frames at 30 fps), plus `.ast`, `.mtl` and textures.
- The element is keyed by `BUILDING_*` in `WonderMovie.artdef`. Overriding that element in your own artdef/package
  swaps the model for the map, the build-up and the completion cinematic.
- `.fgx` is binary **Granny 3D** (GR2: Oodle-compressed sections, Firaxis string remapping). Blender can't write it
  and there is no open writer.

**The headless .fgx route**
- The Asset Editor's managed `Firaxis.CivTech.Impl.dll` has an FBX interface whose export only P/Invokes
  `FbxImporter_Release.dll!ExportFBXScene(fbx, node, out.fgx, ShowInterface, ShowProgress, hWnd)`.
- Call it directly with `ShowInterface=false`, `ShowProgress=false`, `hWnd=0` and it converts an FBX scene to
  `.fgx` with no window.
- Defaults omit tangents: you get `Position3 Normal3 TextureCoordinates0x2`. The shipped layout is
  `Position3 Normal3 Tangent3 Binormal3 TextureCoordinates0x3`. Patch the vertex data afterwards: the SDK's own
  Granny wrapper can load and save the file.
- Missing tangents cook to zeros (black/flat shading); see Gotcha 11.
- **Expansion/DLC wonders** (Etemenanki, Statue of Zeus, Angkor Wat, Torre de Belém, Bolshoi, Venetian Arsenal...)
  have **no SDK pantry asset**. Clone the `.ast`, camera, sounds and footprint from a similar base-game pantry wonder,
  and keep the artdef element from the DLC.
- **Coastal wonders** (Colossus, Great Lighthouse, Torre de Belém, Venetian Arsenal, Sydney Opera House) sit on a
  `TERRAIN_COAST` water tile next to land, not on coastal land. A self-contained diorama model makes the facing
  irrelevant.

**End-game screen**
- The base `UI/EndGame/EndGameMenu.lua` ends with `include("EndGameMenu_", true)` (a wildcard include).
- So an ImportFiles Lua named `EndGameMenu_<yours>.lua` loads inside that context and can patch the global
  `Styles` table:
  - `Background` (a UI texture name);
  - `Movie` (set it to nil to drop the base cinematic; the replay button hides itself);
  - ribbons.
- No Firaxis file is replaced. Expansion files can add styles after yours, so patch again in a wrapper around the
  global `View(data)`.
- Several other base screens end with the same kind of wildcard include. Grep for `include(".*_", true)` before
  reaching for ReplaceUIScript.

**Testing hooks (Lua)**
- In gameplay scripts (AddGameplayScripts):
  - `cities:Create(x, y)`, `UnitManager.Kill(unit)`;
  - `capital:GetBuildQueue():CreateIncompleteBuilding(buildingIndex, plotIndex, 100)` places a finished wonder
    and plays its completion view;
  - `WorldBuilder.CityManager():SetPlotOwner(plot, city)` claims tiles;
  - `PlayersVisibility[0]:ChangeVisibilityCount(plotIndex, 1)` reveals them.
- In a UI script: `UI.LookAtPlot`, `UI.SetMapZoom`, and
  `UI.RequestAction(ActionTypes.ACTION_ENDTURN, { REASON = "UserForced" })`. The last one is what shift-clicking
  End Turn does, and it ignores the "choose production / research / unit needs orders" blockers.
- `AutoplayManager` (`SetTurns`, `SetReturnAsPlayer`, `SetObserveAsPlayer(PlayerTypes.OBSERVER)`, `SetActive`)
  runs AI-only turns for soak tests.
- `UserConfiguration.TutorialLevel(-1)` plus `LuaEvents.TutorialUIRoot_AdvisorLower()` on
  `LuaEvents.TutorialUIRoot_AdvisorRaise` silences advisor popups for the session.

## Build steps
1. **Back up.** Back up `Documents\My Games\Sid Meier's Civilization VI` (`um backup create`). Make a copy of the
   stock gameplay database for offline checks: let a game start, then copy `Cache\DebugGameplay.sqlite`.
2. **Write the data.** One SQL file per era for the trees; units, civs (gameplay) and civs (configuration) SQL.
   Text as `TAG|Text` lists turned into `<Replace>` XML by a script.
3. **Generate the `.modinfo`** from a manifest:
   - FrontEnd: configuration SQL, text, icons, colours, art.
   - InGame: gameplay SQL, text, icons, colours, art, ImportFiles.
   - Text at LoadOrder 5000 (Gotcha 7).
4. **Check offline before every launch.** Apply the gameplay SQL in manifest order to a copy of the stock database
   with `PRAGMA foreign_keys=ON` and check for:
   - foreign-key violations;
   - unreachable tree nodes;
   - prerequisites that cost more than their dependants;
   - XML that doesn't parse;
   - text tags that don't exist in the game;
   - a modinfo that doesn't match the manifest.

   This catches most mistakes in seconds; a game launch takes minutes.
5. **2D art.** Leader cut-outs and civ landscapes → PNG inputs (ffmpeg) → DDS → cook (XLP, ArtDef, Dependency) →
   install BLPs under `Platforms/Windows/BLPs/` plus the `.dep` and artdefs; list them under `<Files>`.
6. **Wonders**, one at a time:
   - concept image → image-to-3D GLB;
   - Blender: clean up, decimate to about 25k tris, bake one texture set, level the albedo to the base wonders'
     brightness, cut into height bands and keyframe a rise-up build animation;
   - FBX → `ExportFBXScene` → `.fgx` → patch tangents → `.geo` → clone `.ast`/camera from the base wonder;
   - write the WonderMovie artdef → cook all wonders into one package.
7. **Victories.** Text, plus `UI/EndGameMenu_<Mod>.lua` (ImportFiles) and UI textures for the end-game backgrounds.

## Verification
- **The game is the oracle.** Each step was launched for real.
- **Tech and civic trees:** opened and screenshotted (gfxcapture).
- **New games:** started as several leaders; checked setup, the loading screen and the diplomacy view.
- **Logs:** `Modding.log` for "Error Loading" lines (anything not ours was already there before the mod).
  `Lua.log` for runtime errors and the harness `print`s.
- **Soak test:** 100 turns of AI autoplay as several civs. 0 Lua errors; the Database.log error count stayed at
  the pre-mod baseline.
- **Wonders:** a test scene places them at 100% next to the capital and frames the camera; each screenshot was
  reviewed. In game, I checked the Argonath, Orthanc, the Tower of Ecthelion and five coastal wonders. The other 44
  were only reviewed from Blender renders taken from the game's camera angle. Loads of a game with all 52 models
  were fine; low-memory machines were not tested.
- **Victory screen:** a harness removes the rival civs' units on turn 1 and force-ends the turn. Victory of Arms
  showed with the new background, no movie and the new ranking list. The other victory types were not triggered,
  but they share the patched code path.
- **Not verified:** multiplayer, Steam Workshop upload, non-English languages (English only), other rulesets
  (vanilla / Rise and Fall).

## Gotchas
1. **`um win drive click` is ignored by Civ VI.**
   - **Cause:** it sets the cursor position and sends button down/up with no move events; Civ needs real moves.
     Two bugs in my own replacement followed: an x64 `INPUT` struct padded to 48 bytes (SendInput returns 0,
     error 87; it must be 40), and a PowerShell `-File` script with `param([int[]]$a)` that bound only the first
     number.
   - **Fix:** SendInput with ABSOLUTE|VIRTUALDESK moves, gliding about 25 steps to the target, a 300 ms dwell,
     then down/up, with separate int parameters.
2. **Autoplay or tests hang on "the AI's turn".**
   - **Cause:** an advisor popup is waiting (first wonder, volcano, historic moment...).
   - **Fix:** in a dev UI script, `UserConfiguration.TutorialLevel(-1)` and lower or clear raised advisors.
     Do this in every harness, before anything else.
3. **The new civ or leader is missing from setup, or setup shows base civs only.**
   - **Cause:** the Configuration database is a separate FrontEnd action.
   - **Fix:** put `Players` rows in all three domains, in a FrontEnd UpdateDatabase.
4. **Removing a tech/civic crashes or breaks boosts and the AI.**
   - **Cause:** many tables reference the base IDs.
   - **Fix:** keep every ID, re-link prerequisites, rename by text only.
5. **Tree columns come out wrong.**
   - **Cause:** the column is the cost rank within the era.
   - **Fix:** costs must rise along each prerequisite chain. Check this offline against the stock database.
6. **The game freezes for good after a particular AI's turn** (turns 25 and 49 in two runs).
   - **Cause:** a male leader reused Catherine de Medici's ability. Its modifier `UNIQUE_LEADER_ADD_VISIBILITY`
     uses `SourceType = DIPLO_SOURCE_FEMALE_ONLY`, and the custom civ had **no female citizen names**, so the
     engine looped forever looking for one.
   - **Fix:** set that modifier argument to `DIPLO_SOURCE_ALL_NAMES` and give every civ full citizen-name lists
     (male and female, classic and modern).
   - **Method:** bisect abilities with **new** games. A loaded save keeps the modifiers attached at game start.
7. **Some of your text reverts to base names in game** (e.g. city-states, other `LOC_CITY_NAME_*`).
   - **Cause:** another enabled mod sets the same tags later. Yet (not) Another Maps Pack sets about 11k
     `LOC_CITY_NAME_*` at LoadOrder 2000.
   - **Fix:** load your text at a higher LoadOrder (5000). Check with `Locale.Lookup` in a test script.
8. **A cook step "succeeded" but the art never changed.**
   - **Cause:** the cooker's error was swallowed by `| tail` in a script.
   - **Fix:** check each mode's exit status and log. Also:
     - pass every needed `--pantry`;
     - don't put commas in PowerShell `-File` arguments;
     - PowerShell variables are case-insensitive, so a local `$extraArtDefs` overwrote the `-ExtraArtDefs`
       parameter.
9. **2D leaders stand on a black screen in diplomacy.**
   - **Cause:** there is no 3D scene; the fallback image is only as wide as the portrait.
   - **Fix:** a **2048x1024** fallback with the portrait centred on a dimmed civ landscape. The game centres it at
     3/4 screen width and scales it to screen height, so it reaches under the left panel.
   - **Cost:** 2.5x the texture memory when the DDS is uncompressed (14 leaders: 63 → 157 MB). Use BC compression
     if you can.
10. **Custom wonders render nearly black in game** while the Blender preview looks fine.
    - **Cause:** the AI textures' mean linear albedo was about 0.03–0.07. Base wonder textures are 0.15–0.33, and
      UV padding was black.
    - **Fix:** fill the padding, then level the albedo towards about 0.18 (capped gain).
    - **Check:** compare against the base wonder's own textures before cooking. Very dark sources (a black cliff)
      stay dark by design.
11. **Custom geometry cooks with flat/odd shading.**
    - **Cause:** the headless Granny export has no tangents, and the cooker copies the zeros.
    - **Fix:** add tangents and binormals (and a third UV set) to the `.fgx` vertex data after export.
12. **`ArtDef` element not found / "not in any pantry" for an expansion wonder.**
    - **Cause:** expansion/DLC wonders have no SDK asset.
    - **Fix:** stand in a base wonder's asset (Colosseum; Great Lighthouse for coastal ones) and keep the DLC
      artdef element.
13. **A coastal test wonder found "no valid plot".**
    - **Cause:** these wonders go on coast **water** tiles next to land, and a new city owns only one ring.
    - **Fix:** claim tiles in the test with `WorldBuilder.CityManager():SetPlotOwner`, and reveal them, or the
      camera looks at unexplored parchment.
14. **The end-game screen never opens during autoplay.**
    - **Cause:** the victory fires (`Events.TeamVictory`), but the menu does not show while the AI drives player 0.
    - **Fix:** in a test, force-end the local player's turn with `REASON = "UserForced"` instead.
15. **A text file stops parsing after a harmless edit.**
    - **Cause 1:** `--` inside an XML comment (generated from `# --- heading`).
    - **Cause 2:** writing `&lt;&lt;` into a source that is escaped again on generation; grammar markers like
      `{LOC_GRAMMAR_CIVNAME << {1_CivName}}` must end up as a single `&lt;&lt;`.
    - **Also:** some tags really have no `LOC_` prefix (e.g. `ADVISOR_LINE_LISTENER_*`).
16. **The paid asset budget burned on failures.**
    - **Cause:** several parallel agents shared one scratch folder and overwrote each other's batch scripts. About
      20 image-to-3D calls failed with HTTP 422 `file_download_error` on bad input URLs, and others were
      duplicated.
    - **Fix:** a single serial generator. At most one paid call per item, and only if its output is missing.
      Stop at the first API error. Price the batch and ask before spending. After that, 39 image-to-3D runs in a
      row had 0 failures.

## Assets
- **Leaders:** 14 leader portraits (painted, original designs) from `fal-ai/nano-banana-2`, cut out with
  `fal-ai/birefnet/v2`.
  - Head crops for circular icons.
  - Leader-select 748x1024 foregrounds.
  - 2048x1024 diplomacy images.
- **Civs:** 8 civ symbols, generated white-on-black, with alpha taken from luminance (gpt-image-2 refused a
  transparent background in the size needed). 8 civ landscapes (16:9) serve as loading, diplomacy and end-game
  backgrounds.
- **Wonders:**
  - 53 concept images (nano-banana-2): one isometric diorama per wonder on a round or hex plinth, neutral grey
    background, no text.
  - 52 GLBs from `fal-ai/trellis-2`, processed in Blender as in Build steps 6.
  - Weak results came from busy concepts (big trees, thin spires); one clear silhouette per concept works best.
- **Movies:** none are generated. The base victory movies are simply not played.
- **Records:** prompts and request ids are kept in each folder's `fal_manifest.jsonl`. The README discloses that
  the art is AI-generated.

## Cost and time
- About two long days of agent time across several context compactions.
- Each wonder takes about 2–4 minutes of Blender and cooker time, run one at a time because of memory use.
- **fal:**
  - Image-to-3D was the main spend: about 39 good runs plus the wasted ones in Gotcha 16.
  - 2D art was a few dozen image calls.
  - Check prices with `um fal price` before a batch.
- **Size:** the cooked mod is about 500 MB (wonder package ~225 MB, uncompressed leader images ~157 MB).

## Open questions
- **Leader portraits:** a few look too much like the film actors. Regenerate them for a public release, with
  prompts that steer away from actor likeness.
- **Texture size:** add BC1/BC3/BC7 compression to the DDS writer to shrink the BLPs.
- **Units:** still use base-game 3D models. The same headless `.fgx` route should work for units, but unit assets
  need rigs and an animation state graph; not tried.
- **Rulesets and languages:** only English and Gathering Storm were tested.
