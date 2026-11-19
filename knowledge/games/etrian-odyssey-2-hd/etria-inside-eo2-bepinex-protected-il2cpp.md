---
kind: game
title: "Etrian Odyssey 1's labyrinth and battles running inside Etrian Odyssey 2 HD (BepInEx on a protected IL2CPP build)"
game: "Etrian Odyssey II HD"
games_also: ["Etrian Odyssey HD"]
game_version: "Steam builds of Oct 2026 (EO2 app 1868170, EO1 app 1868180), Unity 2020.3.1f1, IL2CPP"
platform: windows
engine: unity-il2cpp
route: managed-patch
tools: ["BepInEx 6.0.0-be.788 (Unity.IL2CPP win-x64)", "Il2CppInterop 1.5.3 (patched)", "Il2CppDumper 6.7.46", ".NET 8 SDK", "Harmony"]
anti_cheat: "none (single-player). Both games ship with Denuvo (Steam store DRM notice); it stays in place and is never unpacked or removed. The lab copy runs with steam_appid.txt through the owning Steam account"
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-12
links: []
tags: [bepinex, il2cpp, protected-gameassembly, denuvo, il2cppinterop, addressables, cross-game, mashup, harmony, save-redirect]
---

# Etrian Odyssey 1's labyrinth and battles running inside Etrian Odyssey 2 HD

> A BepInEx plugin in a lab copy of EO2 HD loads EO1 HD's Addressables content at runtime and swaps it into
> EO2's systems: EO1's floors, events, text, world state and enemies run inside EO2's engine. Verified in game
> by screenshots (walking EO1's first floor, EO1 town/quest events, a won battle against EO1 monsters). The
> hard parts were getting BepInEx to start at all on EO2's protected GameAssembly, and loading a second game's
> Addressables catalog without breaking the host. The protection stays in place throughout: the game unpacks its
> own code at run time, and the plugin side only follows the resulting jump stubs in the running process.

## Setup
- Windows 11, Steam installs of both games. Both are Unity 2020.3.1f1 IL2CPP, metadata v27, Addressables with
  JSON `catalog.json`.
- Lab copy of the game folder + `steam_appid.txt` (never the Steam install). Steam still has to be running and
  signed in to the account that owns both games: the file only lets the copy start outside the library, and
  changes nothing about ownership or DRM. BepInEx 6.0.0-be.788 Unity.IL2CPP win-x64 unzipped into it. .NET 8
  SDK (user-local `dotnet-install.ps1`). Il2CppDumper 6.7.46 (.NET Framework build) for reading types.

## Route and why
`managed-patch`: Harmony patches on existing game methods from a BepInEx plugin. Both games share ~8,466
script types, so the host engine already contains almost every code path the guest needs; the work is
feeding it the guest's data and assets. Full reimplementation would have been far larger.
- In the terms of [`choosing-a-mashup-route.md`](../../techniques/choosing-a-mashup-route.md), this is content
  ported into a sibling host, loaded from the user's own guest install at run time. The closest earlier case is
  [Pre-Sequel assets in Borderlands 2](../../techniques/loading-pre-sequel-assets-in-borderlands-2.md), also two
  games on one engine branch.

## How the game works (what we had to learn)
- **Protected GameAssembly.dll (EO2):** both games' Steam pages list Denuvo. EO2's GameAssembly has scrambled
  section names, a ~300 MB `.link` section, and every il2cpp export is a stub
  `call <spin-wait-until-unpacked>; jmp <thunk>` with `thunk: jmp <real body>`. Some exports have their callee
  inlined (`il2cpp_field_static_get_value` contains `Field::StaticGetValue`). Nothing in this note unpacks,
  dumps or removes the protection.
- **Interop namespaces** are real C# namespaces that Il2CppDumper's dump.cs doesn't show (`Master.MasterManager`,
  `MasterData.MasterDataTypes`, `Common.TextLabelDataManager`, `DungeonData.*`, `EventScript.EventObjCombine`).
  Obfuscated member names (BB obfuscator) differ between the two games' builds.
- **Master data:** `MasterManager` holds `MasterData.bin` + `MasterOffset.bin` (u32 offsets ÷ 4, indexed by a
  `DataEnum`) as byte[] fields; events actually run from a separate `EventObjCombine` ScriptableObject
  (per data file: index table + script bytes), so swapping the blob alone changes nothing.
- **Floors** are `DungeonDataScriptableObject` assets (35×30 cell grid, model layout, placed prefabs), kept in
  memory and selected by `DungeonDataManager.DgLoadFloor(int)` — overwriting the host asset's fields in a prefix
  swaps the floor.
- **Saves:** `SaveDataManager` is a `SingletonWithoutMonobehaviour<T>` (not a Unity object); the folder comes
  from `Environment.GetFolderPath(ApplicationData)`.
- **Per-frame hooks:** `InputManager.Update` runs in town/dungeon but not on the title screen; there is no
  patchable per-frame game code on the title screen at all (input goes through InControl).

## Build steps
1. Lab copy, BepInEx, first launch to generate `BepInEx/interop`.
2. Set `[Logging] UnityLogListening = false` in `BepInEx.cfg`.
3. Rebuild Il2CppInterop.Runtime at the exact commit of the bundled DLL (its file version contains the hash)
   with two changes in `InjectorHelpers`: `TryGetIl2CppExport` unthunks the protector's two shapes only
   (`E8 rel32 E9 rel32` → target; then `E9 rel32 CC` → target), and `Setup()` applies each injector hook in a
   try/catch that logs and continues. Copy over `BepInEx/core/Il2CppInterop.Runtime.dll`, keep the original.
4. Plugin csproj (net6.0) referencing `BepInEx/core/*` and `BepInEx/interop/*` with `Private=false`, output
   straight into `BepInEx/plugins/<name>/`. Close the game before building (the DLL is locked).
5. First patch: redirect `Il2CppSystem.Environment.GetFolderPath` (both overloads) so the lab copy saves into
   its own folder.
6. Cross-game assets: rewrite a copy of the guest's `catalog.json` (`{...RuntimePath}` → absolute guest
   `StreamingAssets/aa`, new `m_LocatorId`), load it with `Addressables.LoadContentCatalogAsync`, then
   immediately `Addressables.RemoveResourceLocator(locator)` and look up guest keys via that locator only.

## Verification
- Oracle: screenshots of the real game plus BepInEx and Unity `Player.log`. Verified: chainloader starts;
  Harmony postfix fires on `MasterManager.GetMasterDataSize` (in-memory MasterData size = file size);
  guest music plays; guest floor 1 renders and is walkable with the guest's automap; guest town menu and
  quest events run; a random battle shows the guest's monsters and is won; lab saves land in the lab folder
  and the real save folder stays untouched.
- Not verified: guest enemy AI (all guest enemies use one host script), FOEs, treasure, later floors.

## Gotchas
1. **`Sequence contains more than one element` in `GenericMethod_GetMethod_Hook`, chainloader dead.**
   **Cause:** the protector's export stubs break Il2CppInterop's xref scans (`JumpTargets(...).Single()`).
   **Fix:** `UnityLogListening = false` gets the chainloader up; for class injection, the unthunk + tolerant
   hooks patch above.
2. **Unthunk too eager → a different hook breaks.** Following every `jmp` also "unwraps" exports that are
   legitimately one-jump wrappers. **Fix:** match only the protector's exact byte shapes.
3. **Class injection still crashes (AccessViolation in `Class_FromName_Hook`).** **Cause:** with tolerant hooks a
   scan can "succeed" on the wrong function. **Fix:** no injected classes, no `DelegateSupport.ConvertDelegate`,
   no custom MonoBehaviours; patch existing methods only.
4. **AccessViolation a scene after writing ~1,700 entries into the host's native text-label dictionary.**
   **Cause:** managed-created strings stored in a native IL2CPP container. **Fix:** postfix `TextAsset.text` and
   serve merged CSVs so the host builds its own dictionary.
5. **Crash after hooking `TryGetTextLabelData` (a non-blittable struct `out` param).** Don't hook methods with
   non-blittable struct out/ref parameters.
6. **"An item with the same key has already been added" at boot after loading the guest catalog.**
   **Cause:** registered globally, the host's label-wide load (tutorial images) also returned the guest's
   same-named assets. **Fix:** remove the guest locator right after loading; query it directly.
7. **Guest enemy sprites "No Location found for Key".** The host loads them via generic
   `LoadAssetAsync<T>(object)`, which can't be patched. **Fix:** `Addressables.AddResourceLocator(guest)` only
   after the host's boot-time loads are done (on entering the labyrinth); host locators stay first for
   shared keys.
8. **Patched `TitleMenu.Open` never fires.** Small methods are inlined by IL2CPP. Poll state or use a
   background thread instead.
9. **`Resources.FindObjectsOfTypeAll<SaveDataManager>` returns nothing.** It's a plain C# singleton; call
   `get_Instance` via reflection.
10. **Plugin build fails "file is locked by the game".** Close the game; MSBuild retries then fails.
11. **The first lab run rewrites the real settings save.** It happens before any plugin loads (BepInEx
    interop generation run). Back up the real save folder before the very first launch of the lab copy.

## Assets
None generated; all guest assets are loaded from the user's own installed copy of the guest game at runtime.

## Cost and time
Roughly two long sessions for M0–M4 (plugin running → guest floors, events, text, battles).

## Open questions
- Converting the guest's table-driven enemy AI to the host's flowscript AI.
- Whether the tolerant-hook Il2CppInterop patch generalises to other protectors; upstreaming a safer xref
  fallback.
