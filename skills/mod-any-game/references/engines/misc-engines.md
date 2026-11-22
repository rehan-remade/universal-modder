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
  - Project Zomboid: Lua mods plus Java;
  - Mindustry: a built-in mod loader, so don't patch the jar. `mod.hjson` (or `mod.json`) at the mod's root,
    content as `content/<type>/*.hjson|json` (`blocks`, `units`, `items`, `liquids`, ...), PNGs in `sprites/`
    (`sprites-override/` replaces vanilla sprites), JavaScript in `scripts/main.js`, and Java mods as jars built
    from Anuken's MindustryJavaModTemplate. Mods go in `%APPDATA%/Mindustry/mods`,
    `~/.local/share/Mindustry/mods`, or `<install>/saves/mods` on Steam, as a folder or a zip.
- Otherwise use a Java agent (`-javaagent`) with ASM/ByteBuddy, or Mixin.

## Dwarf Fortress (v50+, Steam and itch.io)
The game is native, but everything it shows comes from plain-text raws and PNG tile pages, so mods are data.
- A mod is a folder in `mods/` with `info.txt` (`ID`, `NUMERIC_VERSION`, `NAME`, ...) next to `objects/` and
  `graphics/` raws (vanilla's are in the install's `data/vanilla/*/` to read). `mods/` is in the user folder,
  `Bay 12 Games/Dwarf Fortress` under `%APPDATA%` or `~/.local/share`, or in the install in portable mode
  (`prefs/portable.txt`).
- Mods are picked and ordered when a world is created, then copied into `data/installed_mods/`; the world keeps
  that copy. Bump `NUMERIC_VERSION` after every edit and test in a new world. Raw errors go to `errorlog.txt`.
- Replacement graphics conventionally declare `[REQUIRES_ID_AFTER_ME:vanilla_creatures_graphics]` (load before
  vanilla). Same-ID graphics blocks merge across files.
- Scripting: DFHack (a separate Steam app; Lua scripts and C++ plugins), loaded through DF's `dfhooks` library.
- 0.47 and older (classic): edit `raw/objects/` in the install.

## Defold, Cocos2d-x, Haxe/OpenFL
- Defold: `game.arcd`/`.arci` archives, Lua scripts. Unpackers exist.
- Cocos2d-x: Lua/JS bundles (sometimes XXTEA-encrypted, with the key in the binary), otherwise native.
- HaxeFlixel/OpenFL: `assets/` overrides. Some games embed Polymod (hscript) mod support.

## Haxe / HashLink (HLB bytecode, Heaps `res.pak`)
HashLink games ship Haxe code as one bytecode blob, run by HashLink's JIT. The blob is embedded in the exe (an
`hl.exe` host; *Dead Cells* 1.0 keeps it as the PE resource `RT_RCDATA` `HLBOOT.DAT`) or kept in a separate
`hlboot.dat` (later and Linux builds).
Assets are usually in a Heaps `res.pak` (`PAK` + version byte, u32 header length, u32 data length, file tree,
`DATA`). Game data is often a CastleDB `data.cdb` (plain JSON) inside it.
- **Look first:** search the exe for `HLB` + version byte, and check for an official mod loader (some later
  builds ship their own mod tools). Data edits (CastleDB JSON in the pak, same length in place) are the cheapest route.
- **Read:** `hlbc` (Rust crate/CLI) disassembles and decompiles. With debug info (flag bit 0), every op has a Haxe
  file:line. Dump once to text and grep. findex = global function index; virtual calls take proto slots, not
  findexes.
- **Patch in place.** `hlbc`'s writer works (same size; object bindings come back reordered), but only if you
  write it back over the resource without cutting the file, and small same-size patches combine better. Same
  byte length,
  same op count per function (debug info is run-length over `nops`; drift gives `Outside range` at startup),
  register writes that match the declared types (else `JIT ERROR n (jit.c line m)`), backward jumps onto
  `Label`, and no reads of unwritten registers. Spare bytes: padded varints (`80 xx`), `Label`/`JAlways +0`.
  Room for new logic: never-called functions (dev/debug classes) used as helper slots.
- **Verify:** re-parse, then a headless boot (`xvfb-run wine game.exe` until the game's "assets loaded" line),
  then a live check. Under Wine/Proton, `/proc/<pid>/mem` + ptrace breakpoints on JIT'd entries work.
- Full rules and tooling: `knowledge/techniques/hashlink-in-place-bytecode-patching.md`. Worked game:
  `knowledge/games/dead-cells/dead-cells-v1-0-modding-reference.md`.
