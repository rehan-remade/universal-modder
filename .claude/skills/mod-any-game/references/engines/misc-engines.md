# Other engines, quick routes

## GameMaker (`data.win`, `game.unx`)
- **UndertaleModTool (UTMT):** opens `data.win`. You get GML decompile/recompile, sprites, rooms, sounds
  and fonts, plus C# scripts for batch edits (a CLI build exists for automation). It covers Undertale,
  Deltarune, Pizza Tower and most GMS2 games. The YYC (compiled) export is native code, so treat that as
  native.md.
- Back up `data.win`. Distribute mods as xdelta patches, never the modified `data.win`.

## RPG Maker
- **MV/MZ (NW.js + JavaScript):**
  - Plugins are JS files in `js/plugins/`, registered in `js/plugins.js`.
  - The database is `data/*.json` (actors, items, maps, events).
  - Encrypted assets (`.rpgmvp`/`.png_`) use a key in `data/System.json`; decrypters exist.
  - Press F12/F8 for devtools in playtest builds, or enable them via `package.json`.
- **XP/VX/VX Ace (Ruby RGSS):**
  - Scripts live in `Data/Scripts.rxdata/.rvdata/.rvdata2` (Marshal-serialized, zlib-compressed Ruby).
  - Encrypted archives are `Game.rgssad/.rgss2a/.rgss3a`; extractors exist.
  - For 2000/2003, see EasyRPG's liblcf.

## Ren'Py (`renpy/`, `game/*.rpa`)
Read with `unrpa` (archives) and `unrpyc` (compiled scripts). Mods are extra `.rpy` files dropped in
`game/`: new labels and screens, `config` overrides, `init` blocks with higher priority. The Ren'Py console
(Shift+O) is enabled via `config.developer = True`.

## Paradox (Clausewitz/Jomini: EU4, CK3, HOI4, Stellaris, Victoria 3)
Plain-text script mods in `Documents/Paradox Interactive/<Game>/mod/<mod>/` with a `.mod` descriptor, or
`.metadata/metadata.json` in newer games. Everything is data: events, decisions, units, GUI. Error log:
`logs/error.log`. The official wikis document every trigger and effect.

## id Tech / Doom family
- **Classic Doom:** WAD/PK3 mods on a source port (GZDoom/UZDoom) with ZScript/DECORATE. Edit maps with
  Ultimate Doom Builder, and inspect files with SLADE.
- **Quake:** `pak0.pak` + QuakeC. Quake 2/3 source releases allow total conversions.
- **Newer idTech (DOOM Eternal):** community tools only, offline.

## HTML5 / Electron / NW.js games
- Electron: `resources/app.asar`. Extract with `npx @electron/asar extract app.asar app/`, patch the JS, and
  either repack or rename so the folder `resources/app/` is used.
- NW.js: `package.nw` or loose files. Open devtools by setting `"chromium-args": "--remote-debugging-port=9222"`
  in `package.json`, or via `nw.Window.get().showDevTools()`.
- Construct (`c3runtime.js`), Phaser, PixiJS: the logic is plain JS. Construct's event sheets are compiled
  into the runtime JSON.
- Browser games you control: the devtools console is your mod loader.

## LÖVE (Lua)
The game is a zip, either a `.love` file or zip data appended to the exe. Unzip it and read the Lua. For
mods without repacking, use injection frameworks: Balatro uses **lovely** (Lua patch injection) +
Steamodded.

## Java games (non-Minecraft)
- Decompile jars with Vineflower/CFR/Procyon, or Recaf (edit + decompile).
- Community loaders:
  - Slay the Spire: ModTheSpire + BaseMod, `@SpirePatch`;
  - Starsector: official mod API;
  - Project Zomboid: Lua mods plus Java.
- Otherwise use a Java agent (`-javaagent`) with ASM/ByteBuddy, or Mixin.

## Defold, Cocos2d-x, Haxe/OpenFL
- Defold: `game.arcd`/`.arci` archives, Lua scripts. Unpackers exist.
- Cocos2d-x: Lua/JS bundles (sometimes XXTEA-encrypted, with the key in the binary), otherwise native.
- HaxeFlixel/OpenFL: `assets/` overrides. Some games embed Polymod (hscript) mod support.
