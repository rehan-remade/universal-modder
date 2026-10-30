# Big games with community frameworks

These AAA engines have no official mod kit, but the community built one. Use the framework; don't
reinvent it. Check each one's GitHub/Nexus page for the version matching the game build.

## Capcom RE Engine (Resident Evil 2/3/4/7/8, Monster Hunter Rise/Wilds, Devil May Cry 5, Street Fighter 6, Dragon's Dogma 2)
- **REFramework** (praydog) goes in the game folder as `dinput8.dll` plus `reframework/`. You get:
  - Lua scripting (`reframework/autorun/*.lua`) with full access to the managed type system:
    `sdk.find_type_definition`, `sdk.hook`, `sdk.call_native_func`;
  - an in-game object explorer;
  - a free camera;
  - VR for many titles.
- **Asset replacement:** files in `natives/` loose paths (with pak priority), via Fluffy Mod Manager or
  loose-file loading. Browse with RE_RSZ / RETool; extract paks with a file list.
- `REFramework-MCP` exposes the game to an agent.
- Online components (SF6 ranked, MH lobbies): cosmetic-only local mods are the norm. Never gameplay-affecting
  mods online.

## Capcom MT Framework (Resident Evil 5/6, Devil May Cry 4, Dragon's Dogma: Dark Arisen, Dead Rising, Lost Planet)
- **Archives:** game data lives in `.arc` files under a `native*` folder named per port: `nativePC/` (Dragon's
  Dogma: Dark Arisen), `nativePC_MT/` (Resident Evil 5), `nativeDX10/` (Devil May Cry 4 Special Edition),
  `nativeWin64/` (Dead Rising). Most content mods replace or repack `.arc` files.
- **Tools:** FluffyQuack's ARCtool unpacks and repacks `.arc` (and converts textures and some data formats) for
  most PC MT Framework games, and Fluffy Mod Manager installs `.arc` mods for the games it supports; both are at
  [fluffyquack.com/tools](https://www.fluffyquack.com/tools/). Dead Rising has an unofficial patch and SDK,
  [DeadRisingEx](https://github.com/grimdoomer/DeadRisingEx).
- **Code:** no official SDK; native mods are DLL hooks. Read the exe with Ghidra/IDA, verify with Cheat
  Engine, same as any native target (`native.md`).
- The 2008 Devil May Cry 4 ships separate DX9 and DX10 exes; mod against the one you actually launch.

## FromSoftware (Elden Ring, Dark Souls, Sekiro, Armored Core 6, Nightreign)
- **Loaders:** ModEngine2 (archived but widely used) or its successor **me3**. They load mods from a folder
  and launch the game **offline with EAC off**. That is the only acceptable way; never online.
- **Data and params** (weapons, enemies, spEffects): Smithbox (successor of DSMapStudio) edits params, maps,
  text and models. WitchyBND unpacks and repacks BND/DCX/BDT containers.
- **Code:** DLL mods loaded by the mod engine (hooks via MinHook). Seamless Co-op is its own separate
  network.
- The "Minecraft inside Elden Ring" and "creepers in Dark Souls" clips (Sept 2026) were built with
  Claude/Opus. Their method wasn't published.

## Rockstar RAGE (GTA V Legacy/Enhanced, RDR2)
- **Story mode only.** BattlEye protects GTA Online; ScriptHookV refuses to run online, and mods must never
  go near GTA Online.
- **Scripts:** ScriptHookV (and ScriptHookVDotNet for C#) + Ultimate ASI Loader (`dinput8.dll`, `*.asi`
  plugins). Natives DB (NativeDB) lists callable game functions. RDR2 uses ScriptHookRDR2 + Lenny's Mod
  Loader.
- **Assets:** OpenIV (with a `mods/` folder copy of RPFs; never edit originals), and CodeWalker for maps.
- LSPDFR-style frameworks exist for specific genres.
- **From the Minecraft × GTA V project** (`knowledge/games/gta-v/minecraft-passthrough.md`):
  - **Launch:** launch story mode with BattlEye off (`-nobattleye` in `args.txt`, or the launcher's toggle).
    That also keeps Online from starting.
  - **ReShade:** it has to load through the ASI loader. GTA loads the system `dxgi.dll` ahead of a proxy in
    its folder.
  - **Downloads:** dev-c.com (ScriptHookV) rejects scripted downloads without browser headers.
  - **Script lifecycle:**
    - the pause menu stops ScriptHookV scripts;
    - the idle cinematic camera starts after about 30 s (call `INVALIDATE_IDLE_CAM` every frame);
    - explosion camera shake isn't reported by `IS_GAMEPLAY_CAM_SHAKING`.
  - **Camera timing:** a script reads the camera for the frame being prepared, one frame ahead of what's on
    screen.

## Sonic Team's Hedgehog Engine (Unleashed, Generations, Lost World, Forces, Frontiers)
- **Mod manager:** [Hedge Mod Manager](https://github.com/hedge-dev/HedgeModManager) installs mods (folders with
  a `mod.ini` and loose replacement files, plus code mods) through HE1ModLoader (Generations, Lost World) or
  HE2ModLoader (Forces, Frontiers, Sonic X Shadow Generations). Guides and tools:
  [HedgeDocs](https://hedgedocs.com).
- **Archives:** Unleashed and Generations use split `.ar` files with `.arl` lists (e.g. `#ActD_Africa.ar.00` +
  `#ActD_Africa.arl`); Generations on PC packs them inside CRI `bb*.cpk` packfiles. Lost World and the HE2
  games use `.pac` (PACx). HedgeArcPack ([HedgeLib](https://github.com/Radfordhound/HedgeLib)) unpacks and
  repacks both.
- **[Unleashed Recompiled](https://github.com/hedge-dev/UnleashedRecomp)** (the Xbox 360 game statically
  recompiled for PC, from the user's own copy) installs `game/`, `update/`, `dlc/` and `patched/` next to its
  exe. Saves go to `%APPDATA%\UnleashedRecomp\save` (`~/.config/UnleashedRecomp/save` on Linux), or to `save/`
  next to the exe when a `portable.txt` is there; back them up with `um backup` before modded launches. Its
  built-in loader reads Hedge Mod Manager's mod list, so prefer loose file replacement over repacking archives.
- **Animation:** HKX packfiles across these generations, see
  `knowledge/techniques/havok-hkx-chunked-packfile-family.md`.

## Black Rock Studio's engine (Split/Second)
- Black Rock Studio's in-house engine for Split/Second (2010); Pure (2008), the studio's previous game, likely
  shares it (not checked). It has no public name, so `um scan` calls it `blackrock`. The studio closed in 2011:
  no official tools and no community framework.
- **Layout** (as reported from a Split/Second PC install): level packs as `.ark` files under `data/` (e.g.
  `docks.ark`), assets as `.model` + `.textures` with `.shaderinst`/`.shaders`/`.fxc` shaders, and plaintext
  `.params` config (e.g. `splitsecond.params`).
- **Modding:** `.params` tweaks and asset replacement inside the packs; native code via DLL hooks
  (`native.md`). Expect to reverse the formats yourself and prove each one with a round trip.

## CD Projekt REDengine
- **Cyberpunk 2077:**
  - REDmod (official): archives and tweaks;
  - Cyber Engine Tweaks: Lua, console, overlay;
  - RED4ext: native plugins;
  - ArchiveXL / TweakXL: new items and records;
  - [WolvenKit](https://github.com/WolvenKit/WolvenKit): projects, asset export/import;
  - the [REDmodding wiki](https://wiki.redmodding.org/cyberpunk-2077-modding) documents all of them.
- **The Witcher 3:** REDkit (official editor), script mods (`.ws` merged with Script Merger).

## Larian (Baldur's Gate 3)
Official mod.io toolkit + Script Extender (Norbyte) for Lua + LSLib/BG3 Modder's Multitool for `.pak`.

## Paradox, Total War, XCOM and the rest
Many strategy games ship official tools:
- Paradox: plain-text script mods (see misc-engines.md);
- Total War: RPFM (Rusted PackFile Manager);
- XCOM 2: the WOTC SDK;
- Cities: Skylines and Cities: Skylines II: C# mods, documented on the official wikis
  ([CS1](https://skylines.paradoxwikis.com/Modding), [CS2](https://cs2.paradoxwikis.com/Modding)).

Search "<game> modding wiki" before reverse engineering anything.

## Frostbite (Battlefield, Mass Effect Andromeda, Dragon Age, FIFA)
Frosty Tool Suite supports specific single-player titles. Most modern Frostbite games ship EA Javelin
kernel anti-cheat: offline single-player only, if at all.

## Avalanche engine (Just Cause 3; same archive family: theHunter: Call of the Wild, Just Cause 4, Generation Zero)
Verified first-hand on Just Cause 3 only: read
`knowledge/games/just-cause-3/vehicle-mesh-editing-added-geometry-loads-with-matching-toc.md` before touching
any Avalanche title. The other titles share the texture and archive family per ApexToolset's docs
(`github.com/PredatorCZ/ApexToolset`, archived), not by test.
- **Route: the `dropzone/` folder.** Files at their VFS path under `<game>/dropzone/` override the archives;
  no loader or DLL. An entity (e.g. a vehicle) is one `.ee` archive (AAF-compressed SARC) plus a **`.ee.toc`**
  index beside it.
- **Tools:** Gibbed.JustCause3 (`Unpack` for `.tab`/`.arc` archives with `-f <regex>`, `SmallUnpack`/
  `SmallPack` for `.ee`, `ConvertAdf` for `.vmodc`/ADF modules, `ConvertProperty` for `.epe`/RTPC,
  `ConvertTexture` for `.ddsc`, `HashName`), Deca (browser), the Gibbed `*.filelist` name lists.
  Gibbed's public `ConvertTexture` only exports (element 0 to `.dds`); the
  `tim42/gibbed-justcause3-tools-fork` build also imports `.ddsc` (round-trips byte-identically,
  one element only; `write-to-hmddsc` import threw in the JC3 test), and ApexToolset's `ddscConvert`
  converts both ways and writes `.hmddsc`. `jc3-console-thingy` (an `xinput9_1_0.dll` proxy) spawns
  entities. JC Model Renderer v0.12.3 reads, renders and exports vehicle models but can't import into
  them (the `develop` rewrite has no vehicle blocks); `Brooen/RBM-Exporter` (Blender) writes plain
  CarPaint, Window and CarLight blocks.
- **Rules that cost the most to learn:**
  - Regenerate the `.ee.toc` for any size-changing build; a stale one makes the game read garbage and crash.
    A `.toc` offset of 0 means "take the current copy from the archives", so a modified file left at 0 is
    silently ignored.
  - The `.ee` often carries **stale pre-patch copies** of files whose live version is in `patch_win64`.
    Find the newest copy by the path's name hash in the `.tab` indexes before editing.
  - New mesh (`.rbm`) paths aren't loaded; new texture (`.ddsc`) paths are. At vanilla texture paths, the
    archives' streamed `.hmddsc` high mips override the `.ee`.
  - `settings/asset_memory_budgets.bin` caps texture and model memory per asset class. Over the hard cap,
    a whole vehicle silently disappears.
  - The property writer zeroes alignment padding that the game fills with `0x50`; diff against the original
    and restore it before shipping an `.epe`.
- **Formats worth knowing:** RBMDL models (blocks closed by `0x89ABCDEF`; the vehicle paint block
  CarPaintMM's constants match its shader cbuffers byte for byte), Havok 2014 `.physicsc` (class names in
  `__classnames__`), ADF `.vmodc` modules readable by name via `ConvertAdf`.
