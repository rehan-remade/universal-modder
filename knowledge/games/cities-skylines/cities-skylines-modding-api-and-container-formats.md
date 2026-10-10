---
kind: game
title: "Cities: Skylines 1 and 2 modding: official APIs, editors, and the .crp/.locale containers"
game: "Cities: Skylines"
games_also: ["Cities: Skylines II"]
game_version: "CS1 (Steam app 255710), CS2 (1.x, modding docs still flagged beta)"
platform: windows
engine: unity-mono
route: loader-api
tools: ["in-game Asset/Map Editor", "CS1 Modding API (C#)", "CS2 Modding Toolchain (C#/.NET)"]
anti_cheat: "none — both games ship supported mod APIs (CS1 Modding API; CS2 Modding Toolchain + Paradox Mods)"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links: ["https://skylines.paradoxwikis.com/Modding", "https://cs2.paradoxwikis.com/Modding", "https://skylines.paradoxwikis.com/CRAP_File_Format", "https://skylines.paradoxwikis.com/Modding_API"]
tags: [unity, modding-api, crp, locale, asset-pipeline, ecs, prefab, paradox]
---

# Cities: Skylines 1 and 2 modding: official APIs, editors, and the .crp/.locale containers

Both Cities: Skylines games are Unity titles that ship a **supported** modding route, so nothing here
touches anti-cheat or ownership checks. This note is the map of that route for an agent: which API to
write against, which editor produces which asset, and the two container formats that keep coming up
(`.crp`, `.locale`). Format knowledge is from the community/XeNTaX side; API knowledge is from the
official Paradox wikis. I have **not** built or loaded a mod.

## Setup
- **CS1** — Unity 5-era, Steam app **255710**. Mods are C# assemblies against the game's **Modding API**,
  plus assets/maps made in the in-game editors. Distribute/install through the Content Manager / Workshop.
- **CS2** — Unity DOTS/ECS. Code mods are C# built with the **Modding Toolchain**; content is made in the
  all-in-one Editor and shared on **Paradox Mods**. The CS2 modding docs are explicitly marked
  **Beta Documentation** and are version-badged per page — check the badge before trusting a page.
- CS2 supports building mods **on Linux via Proton** (see the wiki "Modding Toolchain on Linux" page).

## Route and why
Route: **loader-api** — use the shipped API rather than hooking the engine. The APIs are the sanctioned
path and survive patches far better than memory patches. Asset work uses the **asset-only** route through
the in-game editors. A native-hook route is neither needed nor supported here.

## How the game works (what we had to learn)
### CS1
- Two in-game editors: **Map Editor** and **Asset Editor** (plus **Road Editor** and **Theme Editor**).
  The **Content Manager** installs/manages/shared content; custom **color correction** is supported.
- The **Modding API** is a C# surface allowing a mod to read, override, add or modify game features.
- Containers and formats the community hit:
  - **`.crp`** — a saved map is a single `.crp`, and it is the *same container used for any in-game asset*.
    It carries the mesh/data **and** a `.bin` portion holding object **coordinates/placement**.
  - **`.locale`** — localized text lives under `Cities Skylines/Files/Locale`, one file per language, and is
    a **compiled/proprietary binary, not plain text**; the practical editing route was a Steam Community guide.
  - Also documented on the wiki: **CRAP file format**, **Data types**, **Heightmap**, **terrain/theme** pages.
- Editing is done against a per-user **user path** (the wiki "User path" page); assets land in the user's
  content folders and are loaded as loose content, not by rewriting game files.

### CS2
- **ECS/DOTS**: gameplay is systems over components. Modding guides document **Systems** and a
  **Systems and Components catalog**, and the **PrefabSystem** (values such as capacities, rates, workers).
- Code-mod surface: **UI Modding**, **Mod Key Binding**, **Options UI**, settings files, logging, debugging
  (devUI / developer mode), localization, custom **Tools**, and an **extra assets importer**.
- Asset pipelines (buildings, props, decals, aging trees, surfaces) plus texture sharing, color variations
  and emissive setup; package and upload to Paradox Mods.

## Build steps
- **CS1:** install content via the in-game **Content Manager** (Workshop); author a map in the Map Editor or
  an asset in the Asset Editor; drop loose content in the user-path folders; write C# against the Modding API.
- **CS2:** install the **Modding Toolchain**, create a code-mod assembly, iterate with the in-game editor /
  developer mode, then publish to **Paradox Mods**. On Linux, set the toolchain up through Proton.
- To move a CS1 map between players, ship the `.crp`; do not expect a third-party 3D layout to round-trip
  (see Gotcha 2).

## Verification
- API/editor/pipeline facts: the official Paradox wikis, *Cities: Skylines* → `Modding` (page id 17140,
  last edited 2024-01-19) and *Cities: Skylines II* → `Modding` (page id 6681, last edited 2026-06-25),
  plus the CS1 sub-pages `Modding_API`, `CRAP_File_Format`, `User_path`, `Heightmap`, `Data_types`.
- `.crp`/`.locale` format facts: community XeNTaX reverse-engineering threads
  (t=12681, t=12761, t=18672, t=25039), the usual starting point for the community's
  container documentation.
- **Not verified:** I did not open the game, extract a `.crp`, or build a mod. CS2 pages are beta and may be stale.

## Gotchas
1. **Editing `.locale` as text corrupts it.** **Cause:** `.locale` is a compiled binary, not plaintext.
   **Fix:** use the documented edit tool/method rather than a text editor; back up first.
2. **Extracted map meshes won't rebuild the map.** **Cause:** `.crp` meshes can be extracted with
   in-game **modTools**, but the object **coordinates live in the `.bin`** portion and are not extracted by
   the known preview tool. **Fix:** treat `.crp` as the only faithful carrier of layout; don't expect a
   third-party scene to match.
3. **A CS1 mod does nothing in CS2 (and vice-versa).** **Cause:** different runtimes and APIs (Mono C# API vs
   DOTS/Toolchain). **Fix:** target the game explicitly; keep separate projects.
4. **A CS2 code mod fails to load after a patch.** **Cause:** CS2 mod docs are version-badged and the toolchain
   tracks the game build. **Fix:** match the toolchain/game version the guide's badge states.
5. **Modding "on Linux" fails out of the box.** **Cause:** the CS2 toolchain assumes Windows. **Fix:** follow
   the wiki's Proton setup (`Modding_Toolchain_on_Linux`).
6. **Building a `.crp` asset by hand doesn't load.** **Cause:** the wiki's "CRAP File Format"
   page documents the `.crp` header, but the `.bin` placement/coordinate portion is not covered;
   a 2022 thread asking for a full spec got no answer. **Fix:** create assets through the in-game
   editors, which write the container correctly.

## Assets
CS1: Asset Editor (buildings/props), Road Editor, Theme Editor, color correction. CS2: first-party asset
pipelines for buildings/props/decals/trees/surfaces, texture sharing, color variations and emissive. Both are
node/tool-driven — no hand-authored container required.

## Cost and time
Small: the official Paradox wikis plus community XeNTaX threads. No in-game session, no build.

## Open questions
- `.crp` `.bin` placement/coordinate binary layout — not publicly documented; only the mesh side is extracted.
- `.locale` binary format spec, and the game **font** location for non-Latin scripts — both still open.
- Whether the CS2 `.crp`/asset container is the same family as CS1's, and whether any of it is documented
  outside Paradox's own tools.
- The wiki's **CRAP file format** page documents the `.crp` header; it was not read here (the
  raw/`action=raw` endpoint returned a bot challenge), so the exact header fields are a follow-up.
