---
kind: game
title: "TrackMania 2 custom content: where it lives, and how a skin/model pack is assembled"
game: "TrackMania 2 Canyon"
games_also: ["TrackMania 2 Stadium", "ShootMania Storm", "ManiaPlanet"]
game_version: "ManiaPlanet client (2011-era install layout; the same tree is still used by later ManiaPlanet builds)"
platform: windows
engine: unknown
route: data
tools: ["7-Zip", "any DDS viewer", "hex editor"]
anti_cheat: "none relevant — installing skins, models and packs is a supported client feature (launcher → Help → custom data)"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links: ["https://www.mania-creative.com/ (tutorials archive, Wayback)"]
tags: [file-locations, maniaplanet, gbx, dds, skins, personal-files, custom-content]
---

# TrackMania 2 custom content: where it lives, and how a skin/model pack is assembled

A map of the ManiaPlanet install: which folder holds which media, how the client imports
your own content, and what a community skin/model zip had to contain to be accepted by the
old Maniapark uploader. Everything here is client-facing asset packaging — no anti-cheat or
ownership checks are involved. I did **not** run the game against these paths; the layout
comes from a 2011 Mania-Creative tutorial and from Maniapark's own PHP upload validator. For the
older TrackMania Forever `.3ds` model pipeline (TMF uses older GBX classes than ManiaPlanet), see
`techniques/trackmania-forever-3ds-model-export-in-blender.md`.

## Setup
- Game: TrackMania 2 Canyon (and the whole ManiaPlanet family — Stadium, ShootMania share the client).
- OS the paths describe: Windows. The ManiaPlanet installer lets you split two roots:
  a **common** folder (`CommonFiles`, shared, large) and a **personal** folder (`PersonalFiles`,
  your own content). Choose both explicitly rather than accepting the default buried under `C:\`.
- Both root locations can be changed later from the launcher: **Help → move game data** /
  **move personal data**. The same Help menu has **custom data** for importing content.

## Route and why
Route: **data** (asset and container layout). There is no engine hook here and none is needed —
ManiaPlanet reads its content from fixed directories and from `.Gbx` pack files, so a mod is
files dropped in the right place. The point of this note is to make that "right place" findable
without digging through a 2011 forum thread.

## How the game works (what we had to learn)
- **Two roots.** `[CommonFiles]` holds shipped content; `[Personalfiles]` holds yours. The client
  searches both, so your content is not a patch over the game files — it lives beside them.
- **`.Gbx` is the Nadeo container** for meshes, maps, replays and many other resources.
  A `.Pack.Gbx` is a distributable bundle of a model plus its skins; it is a `NadeoPak` archive,
  not a `.Gbx` object graph (`techniques/trackmania-gbx-containers-and-mesh-extraction.md`).
- **`.dds`** textures are DDS; a skin is a set of DDS maps, a model is `.Gbx` meshes plus DDS maps.
- **Locators (`.loc`).** A small text file whose entire body is one URL; renamed `<content>.loc`
  it tells the game "fetch/download this content". They exist so other players can see your skin
  without the game transferring the actual asset peer-to-peer. The URL must start with `http://`.
- **Common content layout** (`[CommonFiles]/PacksCache/*.zip`):
  - `ManiaPlanet_extras.zip`, `ManiaPlanet_Painter.zip` (Painter stencils/stickers),
    `ManiaPlanet_Skins.zip` (advertisement signs, avatar flags, horn sounds).
  - `Titles.zip` — title definitions and menu media (e.g. Canyon icon, `Menu/TitlesMedia/TMCanyon`).
  - `TMCanyon_HD.zip` — the Canyon HD texture/audio pack: `Canyon/Media/Texture/...`,
    `Canyon/Media/Moods/{Day,Night,Sunrise,Sunset}`, `Canyon/Media/Texture Decal/...`,
    `Vehicles/Media/Audio/Sound/WavData/CanyonEngine/`, and the default car skin
    (`Canyon/GameCtnObjectInfo/Vehicles/CanyonCarDefaultSkin.zip`).
  - `TMCanyon_skins.zip` — race music (`Media/Musics/Canyon/Race/*.ogg`) and painter layers
    (`Media/Painter/Vehicles/Canyoncar/Layers/Dirt`, `.../Layers/PreLight`, `.../SubObjects/Body`, `.../SubObjects/Rims`).
- **Personal content layout** (`[Personalfiles]/`):
  - `Blocks/` and `Blocks/Solid/` — custom 3D blocks; `Maps/`, `Maps/Downloaded/`, `Maps/My Maps/`.
  - `Media/{Images,Musics,Painter,Sounds}/` — Mediatracker images/sounds, challenge music, custom
    painter stencils and stickers.
  - `Packs/` — your own `.Gbx` packs; `Replays/{Autosaves,CreatedGhosts,Downloaded,Mediatrackerghosts,Replays}/`.
  - `Scripts/Editorplugins/` — custom track-editor scripts.
  - `Skins/` — `Any/Advertisement/` (track signs), `Avatars/` (user avatars), `Canyon/Mod/` (Canyon mods),
    `Horns/` (user horns), `Vehicles/CanyonCar/` (car skins).

## Build steps
To install a downloaded skin or mod, or to build your own pack:
1. Put a **Canyon car skin** in `[Personalfiles]/Skins/Vehicles/CanyonCar/`.
2. Put a **Canyon mod** in `[Personalfiles]/Skins/Canyon/Mod/`.
3. Put a **track sign** in `[Personalfiles]/Skins/Any/Advertisement/`.
4. Put an **editor script** in `[Personalfiles]/Scripts/Editorplugins/`.
5. Or use the in-client path: launcher → **Help → custom data** (import).
6. To make a distributable pack, build a zip/`.Pack.Gbx` whose entries follow the naming rules in
   the Gotchas below (a model plus its skin together), and optionally a `.loc` file containing the
   download URL.

## Verification
- The folder names, common/personal split, and launcher "move"/"custom data" menu items are from the
  Mania-Creative tutorial *Trackmania 2 – File locations* (author TStarGermany, last updated 2011-09-15).
- The upload acceptance rules (required zip entries) and the `.loc` behaviour are from Maniapark's own
  PHP validator, `Class/Ressource.php` (`analyse()` and `makeLocator()`), which is the code that decided
  whether a community upload was valid — a real, if historical, oracle.
- **Not verified:** I did not open the game, did not confirm later ManiaPlanet builds kept every path
  unchanged, and did not test a pack in-client.

## Gotchas
1. **Skin shows up but the car looks untextured/wrong.** **Cause:** a "skin" is a paintjob
   (`SkinDiffuse.dds` + `DetailsDiffuse.dds`), while the 3D shape comes from a *model* (`.Gbx` meshes).
   **Fix:** ship both together — a model and its skin belong in the same zip, in the same directory.
2. **"Wrong media type" / pack rejected.** **Cause:** the zip does not contain the minimum pieces.
   **Fix:** a valid model pack needs `Model.Pack.Gbx` **or** `MainBodyHigh.Solid.Gbx` (the 3D mesh)
   *plus* `Icon.dds` *plus* `Diffuse.dds`/`SkinDiffuse.dds`. Allowed file extensions are only
   `jpg`, `jpeg`, `zip`, `gbx`, `txt`; entry names must be lowercase.
3. **Others never see your skin.** **Cause:** without a locator, the asset stays local/peer-to-peer and
   may not propagate. **Fix:** add a `<content>.loc` text file whose whole body is one URL starting
   `http://` (name it e.g. `MyAwesomeSkin.zip.loc`, or `MyAwesomeMod.Skin.Pack.Gbx.loc` for a pack).
4. **`.loc` file does nothing.** **Cause:** the URL scheme is checked, and relative or `https://` URLs
   are/were rejected. **Fix:** use a full `http://…` URL, and name the file after the content it locates.
5. **Content works for you, not for the person who receives your pack.** **Cause:** a pack can carry a
   Planets price and a moderator/"free key" (`pak_key`) in the community site metadata. **Fix:** when
   handing a pack to someone, ship the `.Pack.Gbx`; a priced or keyed pack must be obtained by the
   recipient themselves, so do not pass a `pak_key` on.
6. **Thumbnail rejected by the uploader.** **Cause:** the site enforced a 4:3-ish aspect (±0.1) and a
   minimum of 200×150. **Fix:** export the preview at close to 4:3 and at least 200×150.

## Assets
Skins are DDS paintjobs (`SkinDiffuse.dds`, `DetailsDiffuse.dds`, plus `Icon.dds`); models are `.Gbx`
meshes plus DDS maps; signs use the same DDS packing under `Skins/Any/Advertisement/`. Audio (horn
sounds, challenge music `.ogg`) is optional extra content in the same tree.

## Cost and time
Small: one source tutorial plus one PHP validator read, plus a Docusaurus/site survey. No in-game session.

## Open questions
- Which of these paths still hold in the final ManiaPlanet/Nations Forever builds, and how they map on
  Linux via Proton.
- Whether `.Pack.Gbx` has a documented binary grammar beyond its `NadeoPak` header.
- The exact `.loc` fetch/verification flow between clients (who serves the asset, and how conflicts resolve).
- Later title (Stadium/ShootMania) skin directories beyond the Canyon ones listed here.
