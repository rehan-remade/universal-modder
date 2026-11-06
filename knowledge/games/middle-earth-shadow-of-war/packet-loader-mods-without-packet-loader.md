---
kind: game
title: "Packet Loader mods without Packet Loader: rewrite the newest .bndl load lists (cosmetics: no quiver, no sheaths, lightweight armour, mace replacer, no cloak/hood)"
game: 'Middle-earth: Shadow of War'
games_also: []
game_version: 'Steam build 3095001 (public branch, unchanged since 2018-09-05), Windows 10 22H2'
platform: windows
engine: unknown
route: asset-only
tools: ["Python 3.12 (own .bndl/.embb reader-writer)", "QuickBMS + aluigi shadow_of_mordor.bms 0.4 (extraction)", "Pillow (texture upscale for .texuhd)"]
anti_cheat: "none; loose data files only, the exe is untouched. Tested offline with the offline-mode DLL."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["DeimozZarco"]
date: '2026-10-15'
links:
  - "https://www.nexusmods.com/middleearthshadowofwar/mods/49"
  - "https://www.nexusmods.com/middleearthshadowofwar/mods/166"
  - "https://www.nexusmods.com/middleearthshadowofwar/mods/168"
  - "https://www.nexusmods.com/middleearthshadowofwar/mods/170"
  - "https://www.nexusmods.com/middleearthshadowofwar/mods/128"
  - "knowledge/games/middle-earth-shadow-of-war/offline-mode-and-local-garrison.md"
  - "knowledge/games/middle-earth-shadow-of-war/goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md"
tags: [packet-loader, bundles, bndl, embb, cosmetics, talion, conversion, loose-files, archcfg, no-dll]
---
# Packet Loader mods without Packet Loader: rewrite the newest .bndl load lists

> Several Shadow of War cosmetic mods on Nexus need **Packet Loader**, a DLL that intercepts bundle loads and
> skips ("remove") or swaps ("replace") individual files. The same result comes from plain data. The game decides
> what a bundle loads from its **newest `.bndl` load list**, so a rewritten `.bndl` without the unwanted entries
> works exactly like Packet Loader's "remove". A replacement file at the stock path, with its new size written into
> the `.bndl`, works like its "replace". We converted five mods this way, plus our own no-cloak/no-hood mod. All of
> them were confirmed in game: no cloaks, no sheaths, no quiver, lighter armour pieces, and Celebrimbor's hammer
> drawn as Belroth's mace. No DLL is loaded.

## Credits
The mods converted here belong to their authors. **Download them from Nexus; this note ships none of their
files.** It documents only the conversion method. A converted copy is for your own install; check each mod's
current permissions on Nexus before sharing one.
- **Nuzaki** (Nexus: Nuzaki1080): *No Sheaths* (mod 166; we used both the "No Scabbards (Swords)" and "No
  Scabbards (Wraith)" files), *Lightweight Armours* (168), *No Quiver* (170). Their permissions allow modification
  as long as Nuzaki is credited.
- **Aiden D** (Nexus: Aiden60000): *Spectral Belroth Mace* (128). Its page says that **modifying the files needs
  the author's permission**. We repackaged them for a private install only and redistribute nothing. Ask Aiden
  before releasing a converted copy.
- **survivalizeed**: *Shadow of War Packet Loader* (49) and *DLL Loader* (99), the tools these mods were made
  for. Its packet layout is what this method reads.

## Setup
- Steam build 3095001, Windows 10.
- The offline-mode DLL from [offline-mode-and-local-garrison](offline-mode-and-local-garrison.md) for testing.
  It is unrelated to this method, but its rule holds: no Online Conquest or Vendettas while a data mod is
  installed.
- Python 3.12. Archive listing/extraction as in the
  [Goblins of War note](goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md) (QuickBMS + aluigi's script, or our
  own `.arch06` lister).

## Route and why
- Packet Loader patches loading at run time from a DLL. The user wanted no dependencies, so we reproduced its
  effect with data the game already reads. On this build Packet Loader also crashed at startup about half the
  time (Goblins of War note, Gotcha 5).
- The engine already patches itself this way: game updates ship a **new `.bndl`** (with new sizes) plus loose
  files, and leave the old `.embb` data in place. We do the same.

## How the game works (what we had to learn)
- **Bundle = `.bndl` + `.embb`.**
  - The `.bndl` (`BNDL` v6) is the load list: entry count, a size per entry, the internal paths, and the bundle
    type string (e.g. `Bundles/Types:Flair_1MB`).
  - The `.embb` (`EMBB` v5) holds the data: a name table, then per entry a u32 size and the bytes.
- **The newest `.bndl` wins.** When several archives contain the same bundle path, the last one in
  `x64\default.archcfg` decides what loads. Files are then looked up **by name**: loose files at the stock path in
  any mounted archive first, then the `.embb`.
- **"Remove"** = an entry missing from the newest `.bndl`. The game never asks for it, so the piece never draws.
- **"Replace"** = a loose file at the stock path, plus its **new size** in every `.bndl` that lists it. A size
  mismatch breaks the load.
- **Packet Loader's packet layout** (survivalizeed): `PLG1Packets/<mod>/Find/` and `Replace/` hold numbered
  files named `<n>_<stockname>_0000000K.ext`, where K = the K-th copy of that file the loader saw.
  - `Config.ini` sections `[n]` set `mode = remove | replace | auto`.
  - The stock file name inside the packet name tells you which bundle entries to drop.
- **One stock file can sit in many bundles** (e.g. one weapon mesh in seven skin bundles). Patch every `.bndl` that
  lists it.
- **Textures** (`.tex`, `TEXR` header + DDS payload) can't be dropped in as raw `.dds`. Build a replacement from
  the stock `.tex` header plus the mod's DDS, which must have the same size and format. Also write the `.tex0`
  high-mip companion (the base header names `<path>.tex0`; it holds the top 3 mips) and the `.texuhd` 2× version
  if the stock texture has one, or the game shows its own high mips over yours.

## Build steps
1. List every archive's `.bndl` paths and keep the **newest copy per bundle** (the last archive in archcfg order
   wins). Extract those `.bndl` files.
2. For each mod, read its packets: map each "remove" file name to the stock name, and each "replace" file to its
   stock path.
3. For each newest `.bndl`: drop the removed entries. For replaced files, set the new size. Write the `.bndl` to
   the same path in a new folder. Merge all mods into **one** folder, because several mods edit the same bundles.
4. Put replacement files at their stock paths in that folder (meshes as is; textures rebuilt as above).
5. Add the folder as the **last line** of `x64\default.archcfg` (e.g. `..\TalionCosmetics`). Uninstall = remove
   that line.
6. Our own no-cloak/no-hood mod uses the same tool. It drops the `player_*_cloak*.mat` entries from every
   `player\cloaks\*` bundle (the cloth then never draws), and `player_talion_hood.mesh` from the skin bundles.

## Verification
- In game (user, 2026-10-15): Talion with no cloak, hood, quiver or sheaths, lighter armour, and Celebrimbor's
  hammer drawn as Belroth's mace, across several skins. Saves load and play normally.
- Not verified: every one of the 145 bundles we touched, on every skin; DLC skins outside the user's set; and how
  it interacts with other mods that ship their own `.bndl` for the same bundles (last in archcfg wins).

## Gotchas
1. **A patch archive's listing looks empty.** **Cause:** an older lister mis-parsed the patch archives. **Fix:**
   list them again with a lister that reads folder names as full paths.
2. **The replaced mesh loads in one skin but not another.** **Cause:** the file is listed in several bundles.
   **Fix:** search every newest `.bndl` for the name and update the size in all of them.
3. **The replacement texture shows the stock look up close.** **Cause:** the game streamed the stock `.tex0` /
   `.texuhd` high mips. **Fix:** ship your own `.tex0` (and `.texuhd`) next to the `.tex`.
4. **Two mods edit the same bundle and one loses.** **Cause:** two `.bndl` files with the same path; only the last
   one counts. **Fix:** merge the edits into one `.bndl`.

## Open questions
- A generic converter (any Packet Loader mod → folder) would need the "auto" mode resolved per file. We handled the
  five mods above by hand-checked rules.
