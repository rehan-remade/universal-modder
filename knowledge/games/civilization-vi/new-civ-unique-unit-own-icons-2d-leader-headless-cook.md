---
kind: game
title: "New civilization with a unique unit, own icons and a 2D leader, cooked headless with the SDK"
game: "Civilization VI"
games_also: []
game_version: "Civ VI 1.0.12.68 (Steam 289070, build 15296837), Gathering Storm ruleset, Polish UI"
platform: windows
engine: native
route: data
tools: ["Civilization VI Development Tools (Civ6AssetCooker_FinalRelease, no SDK Assets pantry)", "Python 3 + Pillow", "sqlite3 (Python)", "ComfyUI 0.42.1 + SDXL base 1.0 (local)", "SendInput mouse (PowerShell)"]
anti_cheat: "none; single player only"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-20
links: []
tags: [custom-civ, unique-unit, 2d-leader, fallback-leader, ui-icons, blp, asset-cooker, headless-sdk, dds, comfyui, offline-db-check, test-harness]
---

# New civilization with a unique unit, own icons and a 2D leader, cooked headless with the SDK

> A data mod adding one civilization: a leader, a civ ability, a leader ability and a unique unit that
> replaces Infantry and reuses its 3D model. It also has its own civ icon, unit icon, unit portrait, leader
> icon and a 2D leader image instead of a 3D leader scene. The art is built by scripts and the SDK's
> asset cooker, with no ModBuddy or GUI tools. Everything listed under Verification was checked in the
> running game with screenshots and logs. The art was a fan theme (a sci-fi franchise) kept as a private
> build, so no art is linked here; the pipeline does not depend on it.

## Setup
- **Game:** Windows 11, Civ VI 1.0.12.68 (Steam build 15296837), Base + Rise and Fall + Gathering Storm + civ packs.
  - Played on the GS ruleset; UI language pl_PL.
  - 4K display at 125% Windows scaling: logical screen 3072x1728, screenshots 3840x2160.
- **SDK:** "Sid Meier's Civilization VI Development Tools" from Steam (about 360 MB, installed as `...\Sid Meier's Civilization VI SDK`).
  - The "SDK Assets" pantry was not installed; icons and 2D images don't need it.
- **Mod location:** `Documents\My Games\Sid Meier's Civilization VI\Mods\<Mod>\`. A small deploy script copies the project folder there, but only while the game is closed.
- **Logs:** `%LOCALAPPDATA%\Firaxis Games\Sid Meier's Civilization VI\Logs\`:
  - `Modding.log` (which actions loaded);
  - `ArtDef.log` (art packages; the key one);
  - `Database.log`, `Lua.log`.
- **Cache DBs:** `...\Cache\DebugConfiguration.sqlite`, `DebugGameplay.sqlite`, `DebugLocalization.sqlite`.
  - These are the merged databases of the last game loaded.

## Route and why
- **Data mod** (`.modinfo`):
  - FrontEnd and InGame `UpdateDatabase` (SQL), `UpdateText`, `UpdateIcons`, `UpdateColors`;
  - `UpdateArt` with a `.dep` file.
- `um scan` reports "unknown native engine" and suggests proxy-DLL hooks. That's wrong for this game; see the [Middle-earth note](total-conversion-middle-earth-trees-civs-2d-leaders-custom-3.md), which explains the same.
- **No ModBuddy:** the `.dep`, artdefs, `.tex` and `.xlp` files are plain XML written by scripts, and the cooker runs from the command line.
- **Reference used:** Firaxis DLC folders shipped with the game, mainly Australia (Digger = an Infantry replacement) and Poland (own `LeaderFallbackImages.blp`).

## How the game works (what we had to learn)
**Civ, leader, abilities**
- **Setup screen:** the leader is selectable once there are `Players` rows in the Configuration DB for each domain:
  - `Players:StandardPlayers`, `Players:Expansion1_Players`, `Players:Expansion2_Players`;
  - plus `PlayerItems` rows for the unique unit card.
- **Abilities:** existing modifier types are enough.
  - Science per city: `MODIFIER_PLAYER_CITIES_ADJUST_CITY_YIELD_MODIFIER`.
  - Military production per city: `MODIFIER_PLAYER_CITIES_ADJUST_MILITARY_UNITS_PRODUCTION`.
  - XP: `MODIFIER_PLAYER_UNITS_ADJUST_UNIT_EXPERIENCE_MODIFIER`.
  - The base requirement `REQUIRES_CITY_HAS_CAMPUS` can be put into your own requirement set as `SubjectRequirementSetId`, so the bonus applies only to cities with that district.

**Unique unit**
- Copy the Infantry `Units` row with `INSERT ... SELECT` and override a few columns.
- Add `UnitReplaces`, copy `UnitUpgrades`, `UnitAiInfos` and `TypeTags`.
- If the new unit gets **no `Units_XP2` row**, it needs no Oil and the SQL stays valid in every ruleset (that's what the Digger does).

**3D unit art without the SDK**
- `ArtDefs/Units.artdef` holds one `Units` element copied from the base `UNIT_INFANTRY` element and renamed.
- A hand-written `.dep` lists it under a "Units" consumer.
- `ArtDef.log` then says "Added art file '<Mod>' to the ArtDefProvider", and the unit renders with the Infantry model.
- "Unable to resolve Package 'units/units.blp' from Project '<Mod>'" also shows up, but Firaxis DLCs get the same line, so it is harmless.

**2D leader instead of a 3D scene**
- A new leader without any leader art shows the **first 3D leader scene in `Leaders.artdef`** (Cleopatra) on the leader and diplomacy screens. `LEADER_DEFAULT`'s scene is a different leader, so it is not what you see.
- The fix is a `FallbackLeaders.artdef` element for the leader whose BLP entry points into **your own** `Platforms/Windows/BLPs/LeaderFallbackImages.blp`.
- With that in place, the engine shows the 2D image and no 3D scene.
- Pointing the element at the base game's image does **not** work, see Gotcha 2.
- **Image size:** the fallback image is scaled to the screen height and centred at 3/4 of the screen width (`DiplomacyActionView` sets this up; `FallbackLeaderImage` is filled from C++).
  - A 2:1 image (2048x1024) leaves a black strip on the left of a 16:9 screen.
  - 3:1 (3072x1024) covers the whole screen, including under the left text panel.

**UI icons**
- **Own atlases:** `UpdateIcons` XML with `IconTextureAtlases` rows (`IconsPerRow="1" IconsPerColumn="1"`, `Filename` = BLP entry name) and `IconDefinitions`.
- **Textures:** they live in a cooked UITexture package, e.g. `Platforms/Windows/BLPs/UI/<Pkg>.blp`.
- **Wiring:** the `.dep` gets a consumer "UI" with library `UITexture` and that package.
- **FrontEnd:** for the setup and load screens, also add `UpdateArt` to FrontEndActions.
- **Icon names the UI looks up:**
  - unit flags use `"ICON_" .. UnitType`;
  - the load-game screen uses `"ICON_" .. HostLeader` at **45 px**, but first tries a leader image **stored in the save file** (`UI.ApplyFileQueryLeaderImage`).
- **Sizes** (the same sets as the base game and DLC):
  - civ icons: 22–256;
  - unit icons: 22/32/38/50/80/256 (FOW reuses 32);
  - unit portraits: 38/50/70/95/200/256;
  - leader icons: 32/45/48/50/55/64/80/256.
- **Portraits** are not clipped by the game's round frames. Bake a circular alpha into the texture.

**Cooking headless**
- All the class settings are in the SDK's `AssetModTools/Cooker/Civ6.cfg`.
- **UI icons:** texture class `UserInterface`, XLP class `UITexture`.
- **2D leader images:** texture class `Leader_Fallback`, XLP class `LeaderFallback`.
- **`.tex` file:** a `TextureInstance` with `PF_R8G8B8A8_UNORM`, `eExportMode` `TEXTURE_2D`, `m_ClassName`, `m_Width`/`m_Height` and a DDS data file. The SDK example "CivV ColorMod" is a usable template.
- **Command:**
  ```
  Civ6AssetCooker_FinalRelease.exe --platform Windows --mode XLP --no_mt --pantry . --stewpot BLP --config <SDK>\AssetModTools\Cooker\Civ6.cfg --log_path logs XLPs/<Pkg>.xlp
  ```
  - Run it in a folder holding `Textures/*.tex|dds` and `XLPs/<Pkg>.xlp`.
  - On success it prints "XLP cook completed with success" and writes one BLP.
  - `--no_mt` makes the output byte-identical between runs.
- **Package names:** BLP entry names are stored as plain text in the BLP, so an offline check can grep for them.

## Build steps
1. **Write the data:** SQL for config, civ, leader, traits and unit; text as one XML with `<Replace Tag Language>` for en_US and pl_PL, generated from a Python table.
2. **Check offline before every launch.** Copy the three cache DBs, register a stand-in `Make_Hash()` SQL function (the game's `Types` trigger needs it), remove rows a previous version of the mod left behind (by exact IDs, not by pattern; see Gotcha 7), apply the SQL with `PRAGMA foreign_keys=ON`, then check:
   - foreign keys;
   - that the modifier types exist;
   - that text tags exist in both languages;
   - that every icon atlas `Filename` is inside a listed BLP;
   - that every artdef reference resolves in the base artdef or the mod's BLPs.
3. **Make the art images**, then run the cooker as above. One cook folder per package; copy the BLPs into `Platforms/Windows/BLPs/...` and list them under `<Files>`.
4. **Deploy** with the game closed (the script refuses otherwise), start a new game, check logs and screens.

## Verification
- **The game was the oracle.** Real mouse input via SendInput (Gotcha 9), screenshots via window capture, logs. Nothing was queued or bought during checks.
- **Setup and Civilopedia:** the leader is selectable; the Civilopedia shows the civ icon, ability texts in Polish and the unit ("unique to", "replaces Infantry").
- **City yields:** in a city with the district, the science tooltip shows "+10% from modifiers"; a city without it shows none. Military production: a Trebuchet took 7 turns in the district city (8 without the bonus), 13 elsewhere, which matches ceil(cost / production × 1.15).
- **Unit:** the production list shows the unique unit instead of Infantry (16 turns) and no Oil. A dev-only Lua script (`UnitManager.InitUnitValidAdjacentHex` next to the capital, removed before release) spawned it; it rendered with the Infantry model.
- **Icons:** civ icon (Civilopedia, city banner, setup), unit icon (production list), round unit portrait (city panel), leader icon (top bar, load-game screen with a new save).
- **Leader screen:** the 2D image replaced the Cleopatra scene; the 3:1 image covers the full 16:9 screen.
- **Logs:** `Lua.log` 0 errors; `Database.log` only base-game duplicate-text errors (Gotcha 8); `ArtDef.log` loads both own BLPs.
- **Not verified:** the diplomacy screen with another civ, the load screen art (LoadingInfo), the +25% XP (no combat), AI playing the civ, multiplayer, Workshop upload, non-16:9 screens.

## Gotchas
1. **New leader shows another leader's 3D model** (Cleopatra) on the leader and diplomacy screens.
   - **Cause:** no leader art; the engine falls back to the first scene in `Leaders.artdef`.
   - **Fix:** a FallbackLeaders.artdef element plus your own cooked `LeaderFallbackImages.blp`.
2. **"Unable to resolve Package 'LeaderFallbackImages.blp' from Project '<Mod>'"** when the fallback element points at a base image (`ART_LEADER_DEFAULT`).
   - **Cause:** packages are resolved per project. Adding the base art project (from `Base/Civ6.dep`) to `RequiredGameArtIDs` did not change that.
   - **Fix:** ship the package in the mod (Firaxis Poland does the same).
3. **Red and blue swapped after cooking** (a red-striped portrait came out blue). White icons hid it.
   - **Cause:** Pillow's DDS writer stores 32-bit pixels as B,G,R,A (with matching masks), while the cooker reads raw bytes as R8G8B8A8 and ignores the masks.
   - **Fix:** write the DDS yourself with bytes in R,G,B,A order (128-byte header + raw RGBA).
4. **Garbled icon in sizes like 45/55/22/30/50/38/70/95 px** (horizontal stripes). It was seen on the load-game screen, where the game copies the leader icon into the save.
   - **Cause:** a texture side not divisible by 4. `IsScalable=true` in the `.tex` cook params changed the cooker's stats but **not** the result.
   - **Fix:** put the icon top-left on a canvas rounded up to a multiple of 4 (45→48), with the rest transparent, and keep `IconSize=45`. Base atlases are always multiples of 4.
   - Saves made with the broken texture keep the broken image.
5. **Round portrait shows square corners** sticking out of the gold frame.
   - **Cause:** the frame doesn't clip.
   - **Fix:** bake a circular alpha (supersampled) into portrait and leader-icon textures.
6. **Black strip under the left text panel** on the leader screen.
   - **Cause:** a 2:1 fallback image scaled to screen height and centred at 3/4 width ends at about 19% of a 16:9 screen.
   - **Fix:** make the image 3:1 (3072x1024) and darken the left third a little for the text.
   - This refines Gotcha 9 of the [Middle-earth note](total-conversion-middle-earth-trees-civs-2d-leaders-custom-3.md), which used 2:1 (2048x1024) images.
7. **An offline check deleted base-game rows** when stripping old mod rows with `GLOB '*_ME_*'`. Base tags such as `..._NEAR_ME_...` matched.
   - **Fix:** delete by the exact identifiers parsed from the mod's SQL, and prove it removes 0 rows from clean DBs.
8. **`Database.log` error count grows between runs** with no change to the mod.
   - **Cause:** base-game duplicate text tags (`LOC_CHALLENGE_*`, `LOC_CLICKOUT_*`) repeat on every DB reload.
   - **Fix:** compare by message, not by count.
9. **Clicks from a cursor-jump tool are ignored** (Gotcha 1 in the [Middle-earth note](total-conversion-middle-earth-trees-civs-2d-leaders-custom-3.md), confirmed).
   - Use SendInput absolute moves with a glide and a dwell.
   - The city production gear button sometimes needs a second click: the first only shows its tooltip.
10. **The "Modern" start era doesn't give Replaceable Parts.** It is a Modern-era tech, about 60 turns away. Start in the Atomic era to test an Infantry replacement.
    - Polish UI names: "Współczesność" = Modern, "Epoka atomu" = Atomic.

## Assets
- **Leader:** a painted waist-up portrait from a local ComfyUI (SDXL base 1.0, text-to-image 832x1216, dpmpp_2m karras, 30 steps, CFG 6; then img2img at 1.5x with denoise 0.4), queued through ComfyUI's HTTP API from a script (`/prompt`, `/history/<id>`, `/view`, `/upload/image`).
  - The leader icon is a head crop of the same render; the 2D image is the render composited in the centre of a wide background.
- **Unit icon:** the letters "N7" in a system font, italic shear.
- **Civ icon:** an emblem cut from a flat-coloured source by colour distance. Below 36 px it uses a simplified variant with interior holes filled, so it stays readable.
- **Private build:** some sources were images from the user's own copy of another game, so that build is private. A checker flag refuses a public build that contains them. None of that art is in this note.

## Cost and time
- About three sessions over three days. No paid APIs; the images were made on a local GPU (RTX 5080, about 10 s per SDXL image).

## Open questions
- **Load screen (`LoadingInfo` foreground/background) and setup-screen portrait** were not made yet.
- **Does the 2D fallback also show on the diplomacy screen** with another civ, or does it need a separate entry? Not tested yet.
- **Why `IsScalable` didn't help for non-/4 sizes** (Gotcha 4) — not investigated further.
