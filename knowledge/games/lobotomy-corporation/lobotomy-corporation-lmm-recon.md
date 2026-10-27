---
kind: game
title: 'Modding Lobotomy Corporation: LMM/BaseMod Harmony mods, and why Mirror''s MelonLoader setup can''t run with them'
game: Lobotomy Corporation
games_also: []
game_version: '1.0.2.13f, Steam app 568220, buildid 7641517 (Unity 2017.4.7f1, x64)'
platform: windows
engine: unity-mono
route: loader-api
tools:
- Lobotomy Mod Manager (LMM) 1.3.8/1.3.9 (abcdcode, kygi123, tinue)
- Harmony 1.0.9.1 (0Harmony.dll shipped by LMM)
- LobotomyBaseModLib.dll (shipped by LMM)
- MelonLoader 0.7.1 Open-Beta (Mirror multiplayer route only)
- dnSpyEx / ILSpy
- AssetStudio
- Nexus Mods GraphQL v2 API (research)
anti_cheat: none (single-player; Steamworks only, no EAC/BattlEye/Denuvo; saves are unencrypted)
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-24'
links:
- https://lobotomycorporationmodded.wiki.gg/wiki/Lobotomy_Mod_Manager
- https://lobotomycorporationmodded.wiki.gg/wiki/Troubleshooting
- https://lobotomycorporationmodded.wiki.gg/wiki/Code
- https://lobotomycorporationmodded.wiki.gg/wiki/GettingStarted
- https://www.nexusmods.com/lobotomycorporation/mods/1182
- https://github.com/CTristan/lobotomy-corporation-mods
- https://github.com/Rowrow620/FastForwardSpeed
- https://docs.google.com/document/d/1xQHffu-QQCqWJ26WadJGj4qEa_10c4-q7xnoNMavXIs
tags:
- unity-2017
- mono
- net35
- harmony-1
- basemod
- lmm
- melonloader
- multiplayer
- binaryformatter-saves
- steam-cloud
---
# Modding Lobotomy Corporation: LMM/BaseMod Harmony mods, and why Mirror's MelonLoader setup can't run with them

> This note maps how Lobotomy Corporation (Project Moon, 2018) is modded in 2026. It comes from a read-only
> inspection of a real Steam install, the open-source mods and the community wiki. Nothing was built or tested
> in game yet, so `status: in-progress`. The main route is the community's **Lobotomy Mod Manager (LMM)**. LMM
> patches `Assembly-CSharp.dll` once and then loads Harmony 1 DLLs from `LobotomyCorp_Data/BaseMods/`. A second,
> incompatible ecosystem runs the **Mirror** co-op multiplayer mod on MelonLoader 0.7.1.

## Setup
- **Game:** Steam app 568220, patch **1.0.2.13f** (last Steam patch note 2021-11-02), local buildid 7641517.
  The game has not changed since 2021, so game updates do not break mods. Changes between mod-loader
  generations do.
- **Engine/runtime** (from the MelonLoader log on that install): `Unity Version: 2017.4.7f1`,
  `Game Type: MonoBleedingEdge`, `Runtime Type: net35`, x64. `boot.config` has no `scripting-runtime-version`,
  so the game uses the legacy 3.5 scripting profile. There is no `GameAssembly.dll`, so it is not IL2CPP.
- **LMM:** 21 GitHub releases, from `Update` (2024-03-16) to `Update1.3.9` (2025-09-27), each with
  `Lobotomy.Mod.Manager.<ver>.zip` and `Updater.<ver>.zip`. The inspected copy contains only the string `1.3.8`.
  LMM is a separate Unity app (`LobotomyModManager.exe`) that runs from its own folder, outside the game, and it
  needs Steam running to find the game path. The download carries a modified copy of the game's
  `Assembly-CSharp.dll` and some of its story and stat files (`LobotomyModManager_Data/PatchFiles/`), so this
  note links the community wiki's LMM page instead of the download, and a mod you publish never includes those.
- **What LMM puts in `LobotomyCorp_Data/Managed/`:** a patched `Assembly-CSharp.dll` (4,318,208 bytes, versus
  4,164,096 bytes vanilla), `0Harmony.dll` (FileVersion **1.0.9.1**), `LobotomyBaseModLib.dll`, `NAudio.dll`,
  `Facepunch.Steamworks.Win64.dll`, `steam_api64.dll`, and a `BaseMod/` folder. That folder holds `BackUp.dll`
  (the vanilla assembly), `BaseCreatureGen.xml` and `BaseEquipment.txt`. LMM also creates
  `LobotomyCorp_Data/BaseMods/BaseModList_v2.xml`.
- **Build toolchain used by working open-source mods:** an SDK-style class library. CTristan's mods target
  **net35** with the NuGet package `Microsoft.NETFramework.ReferenceAssemblies.net35`. Rowrow620's mods target
  net472 and also load. References are `Assembly-CSharp`, `0Harmony`, `UnityEngine.CoreModule`/`UnityEngine.UI`
  and optionally `LobotomyBaseModLib`, all with `Private=false`.

## Route and why
- **loader-api through LMM.** Nexus lists about 980 mods for the game, the LMM tool is maintained (by abcdcode,
  kygi123 and tinue, per the wiki), and the wiki documents it. LMM continues abcdcode's BaseMod (5.x). It
  supersedes the Nexus "Basemod" v4.13 page (mod 2), which another user uploaded in 2019 (last updated 2020) and
  which is very outdated.
- **Not plain BepInEx/MelonLoader** for normal mods: none of the content mods would load. MelonLoader 0.7.1 is
  only worth it for the **Mirror** multiplayer mod (Nexus 1182, v0.06ex2, 2026-10-16). Mirror rewrites large
  parts of the game for netcode. Its FAQ says BaseMod mods do not work with it, and it asks you to remove
  BaseMod's `0Harmony.dll` and verify the game files first. Mirror-compatible ports are shared on its Discord.
  In a Mirror lobby a gameplay mod changes the game for everyone in it, so use one only in a lobby you host,
  with friends who agreed and run the same mods.
- **Not assembly replacement** (shipping a whole edited `Assembly-CSharp.dll`). LMM rewrites the assembly on
  every launch, and the wiki lists replacements (Kaizo Corp, an older Memory Leak Fix) as incompatible.

## How the game works (what we had to learn)
- **The vanilla game has no mod loader.** The vanilla assembly contains no `Harmony`, `BaseMods` or `ModInfo`
  names. It does contain a debug console (`ConsoleScript`, `ConsoleCommand`). Abnormality mods publish
  "console spawn IDs" for it. The patched assembly adds `ConsoleCommand_Mod`.
- **Mod entry point:** the patched assembly contains the string `Harmony_Patch`, and every studied mod exposes a
  `public class Harmony_Patch`. The loader appears to construct that class, and the constructor creates a
  `HarmonyInstance` and applies its patches. Harmony is the 1.x API (namespace `Harmony`, `HarmonyInstance`,
  `HarmonyMethod`), not Harmony 2. Classes and members must be `public` (BaseMod readme).
- **Mod discovery:** every folder under `BaseMods/` is a mod. Its DLL must be at the folder's top level.
  `Info/GlobalInfo.xml` holds `<ID>`, and `Info/<lang>/Info.xml` holds the name and descriptions. Mods without
  info show as "Unknown", which does no harm. Load order is the order in `BaseModList_v2.xml`, set by dragging
  mods in LMM.
- **Content folders** a mod can carry (Ziv's Modding Documentation): `Creature/` (CreatureGen,
  CreatureInfo/<lang>, CreatureList, Creatures stats, Portrait 256×256), `CreatureAnimation/` (Spine exports
  renamed `atlas.txt` + `json.txt`, loaded as `Custom/<name>`), `AgentAnimation/`, `Equipment/` (Sprite, txts,
  xmls/<lang>), `BaseModAudioClip/`, `BaseModAssetBundle/`, `BaseModImage/`, `Localize/<lang>/`. An
  Abnormality's behaviour is a class deriving from `CreatureBase`, and its name must match the `<script>` value
  in the stat file. Equipment IDs share the Abnormality ID's digits, with a type prefix: 2 for weapon, 3 for
  armor, 4 for gift.
- **Vanilla data:** gameplay data is TextAsset XML inside `resources.assets`: about 303 `<?xml` documents, with
  301 `<creature` and 448 `<equipment` tags. The code loads them by names such as `xml/CreatureList`,
  `xml/creatureStats/…`, `xml/CreatureGenInfo`, `xml/Equipment/Equipment`, `xml/Research` and
  `xml/Story/StoryList`. All localized text is **loose** XML in
  `LobotomyCorp_Data/ExternalData/xml/Language/<lang>/` (13 languages, 2,121 files), so text and translation
  mods need no tools. `LobotomyCorp_Data/CustomData/{Face,Hair}` is a vanilla folder for agent cosmetics as PNG.
- **Saves:** `%USERPROFILE%\AppData\LocalLow\Project_Moon\Lobotomy\saveData170808.dat`, `saveGlobal170808.dat`
  and `etc170808.dat` (each with a `.backup`), plus `agentData/` and `creatureData/`. The header is
  `00 01 00 00 00 FF FF FF FF 01…`, which is .NET **BinaryFormatter**, a serialized
  `System.Collections.Generic.Dictionary`, not encrypted. Steam Cloud syncs this folder (`steam_autocloud.vdf`).
- **Useful game symbols:** `GameManager` (`gameSpeedLevel`, `state`, `UpdateGameSpeed`), `WorkerModel` →
  `AgentModel`, `CreatureBase`, `CreatureModel.metaInfo` → `CreatureTypeInfo`, `CreatureTypeList.instance`,
  `CustomizingWindow.Confirm`.
- **Logs:** gameplay errors go to `LocalLow\Project_Moon\Lobotomy\LobotomyBaseMod\Log.txt`. Load errors go to
  `LobotomyCorp_Data\BaseMods\*error.txt` (`LMMerror`, `Herror` for Harmony, `DllError`, `LTDerror` for
  localization, `Glerror` for save read). LMM's own errors go to `<LMM>\LobotomyModManager_Data\Log.txt`, which
  is in Korean (`패치 성공!` means "patch success"). Hard crashes go to
  `LocalLow\DefaultCompany\LobotomyModManager\Player.log`. Every launch overwrites these logs.

## Build steps
1. Turn off Steam Cloud for the game, and copy `LocalLow\Project_Moon\` somewhere outside the game folder.
2. Extract the LMM zip to a folder **outside** the game. Start Steam, run `LobotomyModManager.exe`, check
   *Set Game Path*, then **Start Game**. Success looks like this: the title screen shows the BaseMod/LMM version
   in the top-left corner, and `Managed/` has the files listed under Setup.
3. Make the project: `dotnet new classlib -f net35`, add the reference-assemblies NuGet package, and reference the
   game's `Managed` DLLs with `Private=false`. The minimal entry class looks like this (written for this note,
   not taken from game code):
   ```csharp
   public class Harmony_Patch {
       public Harmony_Patch() {
           var h = Harmony.HarmonyInstance.Create("MyFirstMod");
           var target = typeof(GameManager).GetMethod("UpdateGameSpeed",
               BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
           h.Patch(target, null, new Harmony.HarmonyMethod(typeof(Harmony_Patch).GetMethod("Post")));
       }
       public static void Post(GameManager __instance) {
           if (__instance.gameSpeedLevel == 3) UnityEngine.Time.timeScale = 6f;
       }
   }
   ```
4. Deploy to `LobotomyCorp_Data/BaseMods/MyFirstMod/MyFirstMod.dll` with `Info/GlobalInfo.xml` and
   `Info/en/Info.xml`. Always launch through LMM. Quit with **Options → Quit Game**, because only that exit
   makes LMM's save backup (`Managed\BaseMod\BackUp`).
5. Compare with the readable sources: `Rowrow620/FastForwardSpeed` (under 50 lines) and
   `CTristan/lobotomy-corporation-mods` (MIT, net35, unit-tested patches, shared common package).

## Verification
- **Verified, read-only on a real install:** the Unity version and runtime (MelonLoader log), the vanilla vs
  patched assembly sizes and which names each contains, the files LMM adds (LMM's own patch log lists each copy),
  the Harmony FileVersion, the save header bytes and location, the counts of loose language XML and embedded XML.
- **Verified from sources:** the mod layout and entry class (three public repos), the LMM release dates
  (GitHub API), and mod counts and activity (Nexus GraphQL v2: 982 mods, more than 20 updated 2026-10-17…24).
- **NOT verified:** that the build steps above load in game, the exact rule the loader uses to find
  `Harmony_Patch`, the console hotkey and commands, a stand-alone BinaryFormatter round-trip of the saves, and
  LMM 1.3.9 behaviour (the inspected copy says 1.3.8).

## Gotchas
1. **Title screen shows "BaseMod 5.2" and later mods don't run.** **Cause:** one mod threw during load (an
   "AddOn Init error"), and loading stops there. A common trigger is calling an API that is not in Unity
   2017's .NET 3.5. **Fix:** check `BaseMods\*error.txt` and remove mods one at a time. Target net35, or avoid
   newer APIs even if you build for net472.
2. **The mod is in `BaseMods` but never loads.** **Cause:** a double folder
   (`BaseMods\Mod-608-1-0-…\Mod\Mod.dll`), files extracted loose into `BaseMods` (you see `Info/`,
   `Equipment/` at the top), or a GitHub source zip (`.sln`/`.cs`). **Fix:** keep exactly one folder level, with
   the DLL at the top. LMM 1.3.6+ extracts only `.zip`; use Manual install for `.rar`/`.7z`.
3. **Edits to `Managed/Assembly-CSharp.dll` disappear.** **Cause:** LMM patches the assembly again on every
   launch through `LobotomyModManager.exe`. **Fix:** never edit the assembly. Use Harmony from a BaseMods DLL.
   LMM ships a patch assembly in `LobotomyModManager_Data\PatchFiles` for reference.
4. **Mirror multiplayer and LMM mods break each other.** **Cause:** Mirror needs MelonLoader 0.7.1 and a clean
   `Managed/` without BaseMod's `0Harmony.dll`, while LMM needs a patched assembly and that same Harmony.
   **Fix:** choose one per install. Switching means LMM install/uninstall (Steam *Verify integrity* restores
   vanilla), or keeping a second game copy for multiplayer.
5. **Saves "come back wrong" after removing mods, or a new game stalls.** **Cause:** Steam Cloud restores
   saves that reference content you removed. **Fix:** turn Cloud off for the game while modding, and restore
   from your own copy of `LocalLow\Project_Moon\`.
6. **"Unexpected binary element" popup on load.** **Cause:** a corrupt `ModOptionData.dat`. **Fix:** delete it,
   and LMM regenerates it (wiki Troubleshooting).
7. **A mod works for some players only.** **Cause:** it needs the old unofficial `12Harmony.dll` (from BaseMod
   5.2.1), which some installs still have and others don't. **Fix:** for private members, depend on
   `LobotomyBaseModLib.dll` (always installed by LMM) instead: its `ExtenionUtil_Lib` extension methods
   (`GetFieldValue<T>`, `SetFieldValue`, `Invoke`) reach them by reflection. The wiki's other fix is to ship
   `12Harmony.dll` in your mod's folder.
8. **A research snapshot of the install went stale.** **Cause:** the human was switching loaders (MelonLoader
   removed, LMM patched in) while the agent was hashing files, and `Assembly-CSharp.dll` changed size between
   two reads a few minutes apart. **Fix:** list the mtimes of `Managed/` and the game root before drawing
   conclusions, and re-check after any surprise. LMM's `Managed/BaseMod/BackUp.dll` is a reliable vanilla copy
   for decompiling.
9. **The Nexus web page returns 403 to fetch tools.** **Fix:** the keyless GraphQL endpoint
   (`POST https://api.nexusmods.com/v2/graphql`, `mods(filter:{gameDomainName:{value:"lobotomycorporation"}})`,
   `legacyModsByDomain` for descriptions) returned everything needed.

## Assets
None made. For reference: art is extracted with AssetStudio from `resources.assets`/`sharedassets*.assets`.
Extracted art stays on your machine; a published mod carries its own art.
Abnormality animations are Spine 2D (the trial version cannot export). Audio is `.mp3` in `BaseModAudioClip/`.
AssetBundles need the Unity **2017.4.7f1** editor (Ziv's doc says it needs modification to build them).

## Credits
- Lobotomy Mod Manager and BaseMod: abcdcode, with kygi123 and tinue maintaining LMM (per the community wiki).
- Mirror multiplayer mod: Clair (Clairidze on Nexus).
- Ziv's Modding Documentation (the Google Doc in `links`) and the Lobotomy Corporation Modded wiki on wiki.gg.
- CTristan's `lobotomy-corporation-mods` and Rowrow620's `FastForwardSpeed` (both MIT), the readable sources in
  Build step 5.

## Cost and time
About one session of research: web, GitHub API, Nexus API and read-only local inspection. No API spend.

## Open questions
- Build and load the minimal `Harmony_Patch` mod in game to confirm the net35 build steps and the entry rule
  (decompile the patched assembly's loader; the wiki's Code page names `Add_On` as the class that loads mods).
- The console hotkey and command list (`ConsoleScript` / `ConsoleCommand_Mod`).
- A save editor: deserialize the BinaryFormatter `.dat` files outside the game, with `Assembly-CSharp.dll`
  referenced for the game types.
- A clean way to switch between the Mirror (MelonLoader) and LMM setups, or to keep them side by side.
- Mirror's internals (it bundles its own Steam/LAN transport) if a BaseMod port ever ships.
