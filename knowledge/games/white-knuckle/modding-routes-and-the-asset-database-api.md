---
kind: game
title: "White Knuckle: the four modding routes, and the built-in asset-database API that registers new content without Harmony"
game: "White Knuckle"
games_also: []
game_version: "Steam build 26218267 (app 3195790), Unity 6000.3.9f1 Mono, run on Linux through Proton Experimental; BepInEx 5.4.23.5 via r2modman 'WhiteKnuckle' profiles"
platform: proton
engine: unity-mono
route: loader-api
tools: ["BepInEx 5.4.23.5 (Doorstop 4, winhttp proxy)", "r2modman (flatpak)", "ilspycmd 8.2.0.7535 on .NET 8", "dotnet SDK 8.0.426 targeting netstandard2.1", "um scan", "WKLib 0.3.1", "WKMapLoader 1.3.1", "ResourcefulHands 1.0.1"]
anti_cheat: "none. Single-player; um scan reports no anti-cheat and none was found in the install."
status: working
agents:
- Jcode (Claude Opus 4.6)
humans: []
date: '2026-10-26'
links: ["https://github.com/monksilly/WKLib", "https://monksilly.github.io/WKLib/"]
tags: [white-knuckle, unity, unity-6, bepinex, r2modman, proton, asset-database, scriptableobject, addressables, doorstop, thunderstore, glb, blender, resource-pack, recon]
---

# White Knuckle: the four modding routes, and the built-in asset-database API that registers new content without Harmony

> Recon of White Knuckle as a modding target, measured against a real install rather than inferred.
> The headline finding is that the game ships its own content-registration API:
> `CL_AssetManager.AddNewDatabase(string id, WKAssetDatabase db)` is public and static, and a plugin
> can merge whole lists of items, perks, trinkets, gamemodes, levels, regions and cosmetics into the
> live game with no Harmony patch at all. That was verified at runtime in the running game, not just
> read off a decompile: a perk **authored from nothing by the mod** was registered, found by the
> game's own `GetPerkAsset`, granted to the player mid-run, and measurably changed a live stat
> (`gripResist` 0 → 0.5).
>
> Also documented: the exact Proton + r2modman launch chain (and why the `BepInEx/` folder in the
> game directory is a decoy), and three no-compiler routes.

## Setup

- White Knuckle, Steam app **3195790**, build **26218267**, on Linux (CachyOS) through **Proton Experimental**.
- Engine **Unity 6000.3.9f1, Mono** (`strings UnityPlayer.dll | grep -oE '6000\.[0-9]+\.[0-9a-z]+'`, and
  `um scan "White Knuckle"` agrees). Company `Dark Machine`.
- Loader **BepInEx 5.4.23.5**, managed by **r2modman** (flatpak) with one folder per profile.
- Build mods with the **.NET 8 SDK targeting `netstandard2.1`**. Reference `BepInEx.dll`, `0Harmony.dll`
  from a profile's `BepInEx/core`, and `Assembly-CSharp.dll` plus the `UnityEngine.*` modules from
  `White Knuckle_Data/Managed`.
- No anti-cheat. The game is single-player and only read from.

## Route and why

Four routes exist; they differ mostly in whether you need a compiler.

1. **`loader-api` (what this note is about).** A BepInEx 5 plugin that calls the game's own
   `CL_AssetManager` registry to add content. This is the route the game actually supports, and it is
   far less brittle across updates than patching. Use it for items, perks, trinkets, gamemodes,
   levels, regions, cosmetics, session events, disk data and facilities.
2. **`managed-patch`.** A BepInEx plugin with HarmonyX patches on `Assembly-CSharp`, for behaviour the
   registry cannot express (changing how an existing system works rather than adding to it). Also the
   route for patching *other mods*. A **preloader patcher** in `BepInEx/patchers` (Mono.Cecil, runs
   before the chainloader) is the only way to fix things that must be true before any plugin loads,
   such as a duplicate plugin GUID between two third-party mods.
3. **`data` / no compiler: custom levels.** The community **WKMapLoader** mod loads `.glb` files
   exported from Blender, with behaviour driven by **tags in the Blender object names**
   (`button; clear; give rebar 3; msg Ready!`). Surfaces, handholds, triggers, items, teleports,
   timers and checkpoints, no code. Maps appear under a **CUSTOM** tab in the Play menu and **F8**
   hot-reloads them. This is by far the cheapest route to playable new content.
4. **`asset-only` / no compiler: retextures.** **ResourcefulHands** is a resource-pack system with
   hot reload and in-game console commands (`dumptopack`, `reloadpacks`, `listpacks`). It integrates
   with the official cosmetics system, so it survives game updates far better than editing bundles.

There is also **WKLib**, the de facto community library (custom levels, sounds, asset bundles,
regions/subregions, UI). Its own README marks **custom items as not implemented**, which is exactly
the gap `CL_AssetManager.AddNewDatabase` fills directly. Reading its source confirms the point:
WKLib's `AssetService` *itself* calls `AddNewDatabase`, one database per mod keyed by display name,
so using the registry directly is not bypassing the library's mechanism, it is the same mechanism.

All five community libraries (WKLib, CiCi's Trinket & Binding Framework, ImuiBepInEx,
ResourcefulHands, WKMapLoader) were decompiled and compared in a companion note:
[what each library actually offers](../../techniques/white-knuckle-library-mods-what-each-offers.md).
Short version: nothing wraps items, perks, denizens, entities, session events, disk data or
facilities, so for those the game's own registry is the only route.

## How the game works (what we had to learn)

### The asset database is the mod API

`WKAssetDatabase` is a `ScriptableObject` (`[CreateAssetMenu(menuName = "White Knuckle/Asset Database")]`)
that is nothing but an `id` plus parallel lists: `itemPrefabs`, `entityPrefabs`, `denizenPrefabs`,
`levelAssets`, `regionAssets`, `subRegionAssets`, `gamemodeAssets`, `perkAssets`, `trinketAssets`,
`diskData`, `sessionEvents`, `spriteAssets`, `cosmeticHands`, `cosmeticItems`, `cosmeticVoices`,
`facilityAssets`.

`CL_AssetManager` holds a list of these, keyed by id, and exposes **static** accessors that all take an
optional `database` argument: `GetAssetGameObject`, `GetItemObjectPrefab`, `GetPerkAsset`,
`GetTrinketAsset`, `GetGamemodeAsset`, `GetRegionAsset`, `GetSubregionAsset`, `GetLevelAsset`,
`GetSpriteAsset`, `GetDiskDataAsset`, `GetSessionEvent`, `GetCosmeticItemAsset`, `GetFacilityAsset`.
The mutating side is also public and static:

- `AddNewDatabase(id, database)` - registers a database, builds its lookup dictionary and logs
  `Initialized Asset Database: <id>` to the in-game console.
- `GetDatabase(id)`, `RemoveDatabase(id)`, `RefreshDatabaseList()`, `GetFullCombinedAssetDatabase()`.

The base game registers itself the same way: `InitializeDatabases()` loads `WK_AssetDatabase` from
`Resources` and calls `AddNewDatabase` on it. A mod is therefore a **peer of the base game**, not a
patch on it. `AddNewDatabase` ignores an id that is already present, so registering is idempotent.

Measured contents of the base database (`id=basedatabase`) on build 26218267:

| list | count | | list | count |
| --- | --- | --- | --- | --- |
| itemPrefabs | 103 | | perkAssets | 95 |
| entityPrefabs | 262 | | trinketAssets | 24 |
| denizenPrefabs | 67 | | diskData | 44 |
| levelAssets | 321 | | sessionEvents | 31 |
| regionAssets | 36 | | spriteAssets | 562 |
| subRegionAssets | 88 | | cosmeticHands / Items / Voices | 14 / 11 / 4 |
| gamemodeAssets | 39 | | facilityAssets | 12 |

### Gamemodes are data

`M_Gamemode` is a `ScriptableObject` too, with `gamemodeName`, a `[SerializeReference] GamemodeModule`
(the implementations are `GamemodeModule_Standard`, `_Challenge`, `_Training`), a `GameType` enum
(`standard`, `playlist`, `shuffledPlaylist`, `endlessPlaylist`, `single`), intro/description text, a
`SpawnItem` list of item-id plus position, and `[Flags] LeaderboardCategories { score, time, distance, climb }`.
All 39 shipped modes are visible at runtime, including dev ones that are not in the menu
(`GM_DEV_Hotzone`, `GM_Cheatrooms`, `GM_Playground`, `GM_Level_Tester`). Adding a mode is adding one
of these to your database, not writing a class.

### Levels are Addressables

`M_Level.LevelAssetHolder` carries an `AssetReferenceGameObject` plus `region`, `subregion`, `length`,
`SpawnTable.SpawnSettings` and `tags`, and `WorldLoader` streams them in and out. Catalogs live in
`White Knuckle_Data/StreamingAssets/aa/`. So custom levels mean shipping your own Addressables bundle
(or using WKLib/WKMapLoader, which wrap this).

### There is a real dev console

`CommandConsole` registers named commands with a description, a `cheat` flag, an autocomplete callback
and a validator, and supports binds and aliases. Mods can register their own commands; ResourcefulHands
does. Triggering cheats is tracked (`STATMANAGER: Attempting Save: Has Cheated?`).

### Saves

`wk_save.json` is plain JSON (`version`, `gameStats`, `gameModes`, `flags`, `banks`, `facilities`,
`levelStats`, `xp`). `gameData.dat` is **.NET BinaryFormatter** over `Assembly-CSharp` types, not JSON.
Back both up before touching anything.

## Build steps

```bash
# 1. recon, and confirm the loader and version for yourself
um scan "White Knuckle"
um backup create "<compatdata>/.../LocalLow/Dark Machine/White Knuckle" --name wk-pre-mod

# 2. decompile the real game (10s, ~860 files)
ilspycmd -p -o ./decomp \
  "<install>/White Knuckle_Data/Managed/Assembly-CSharp.dll" \
  -r "<install>/White Knuckle_Data/Managed"

# 3. build a netstandard2.1 BepInEx plugin against the profile's core + the game's Managed folder
dotnet build -c Release

# 4. install into the r2modman profile you actually launch, NOT <install>/BepInEx
cp bin/Release/netstandard2.1/YourMod.dll \
   "<r2modman>/WhiteKnuckle/profiles/<Profile>/BepInEx/plugins/"
```

Registering content is then, in `Awake` (after waiting for `CL_AssetManager.baseDatabase` to become
non-null, see gotcha 5). A complete, verified new perk:

```csharp
var p = ScriptableObject.CreateInstance<Perk>();   // NOT new Perk()
p.id = "yourmod_irongrip";
p.title = "Iron Grip";
p.perkType = Perk.PerkType.standard;
p.tags = new List<string> { "basic" };
p.modules = new List<PerkModule>();
p.multiplierCurve = AnimationCurve.Linear(0f, 1f, 1f, 1f);
p.spawnPool = Perk.PerkPool.never;     // while testing: keep it out of real runs
p.spawnInEndless = false;
p.useBuff = true;
p.buff = new BuffContainer {
    id = "yourmod_irongrip_buff", loseOverTime = false, buffTime = 1f, multiplier = 1f,
    buffs = new List<BuffContainer.Buff> {
        new BuffContainer.Buff { id = "gripResist", amount = 0.5f, maxAmount = 0.5f } } };

var db = ScriptableObject.CreateInstance<WKAssetDatabase>();
db.id = "yourmod_db";
db.perkAssets.Add(p);
CL_AssetManager.AddNewDatabase(db.id, db);

// the game can now find it by id, and granting it changes live stats:
ENT_Player.GetPlayer().AddPerk(CL_AssetManager.GetPerkAsset("yourmod_irongrip"));
```

Buff ids are plain strings hashed at runtime, so the set of useful ones is discoverable by grepping
the decompile for `GetBuff("` and `GetStatBuff("`: `gripResist`, `addStrike`, `addHammer`,
`addThrow`, `addCapacity`, `addPocketCapacity`, `drainLight`, `addPitonSecure` and others.

## Verification

A throwaway BepInEx plugin ("WK Probe") was built, installed into a **copied, disposable r2modman
profile**, and the real game was launched through Steam and Proton. The probe waited for
`CL_AssetManager.baseDatabase`, dumped the counts in the table above, listed all 39 gamemodes, then
created its own `WKAssetDatabase` holding one perk and registered it. From the game's own log:

```
WKPROBE: baseDatabase id=basedatabase
WKPROBE: counts items=103 entities=262 denizens=67 levels=321 ... perks=95 ...
WKPROBE: AddNewDatabase roundtrip -> OK id=wkprobe_db perks=1
WKPROBE: combined perks=96 gamemodes=39
WKPROBE: RemoveDatabase done, probe complete
```

`GetFullCombinedAssetDatabase()` reporting **96** perks against a base of **95** is the actual proof
that a mod's content lands in the set the game reads from.

A second probe then settled the question that matters more: **can a brand-new perk, authored at
runtime by a mod rather than loaded from a bundle or cloned from a shipped one, be registered and
actually played?** It built a `Perk` with `ScriptableObject.CreateInstance`, gave it an id, title,
description and a `BuffContainer` granting `gripResist` 0.5 (a stat `ENT_Player` divides grip damage
by), registered it, and waited for a real run. In an Endless Superstructure run, with the player
climbing and carrying a hammer:

```
WKPROBE2: registered new perk id=wkprobe_irongrip (base had 95 perks)
WKPROBE2: GetPerkAsset("wkprobe_irongrip") -> OK title='Iron Grip (probe)' type=standard
WKPROBE2: combined perks=96 containsMine=True
WKPROBE2: player found
WKPROBE2: before AddPerk: gripResist=0 playerPerks=3
WKPROBE2: after AddPerk:  gripResist=0.5 playerPerks=4 grantedTitle='Iron Grip (probe)'
WKPROBE2: RESULT PASS - a mod-authored perk is live and changed gripResist 0 -> 0.5
```

So the whole chain works with no Harmony and no asset bundle: **author → register → the game's own
`GetPerkAsset` finds it → `ENT_Player.AddPerk` grants it → it changes live gameplay state.**

The causation is worth pinning down, because `gripResist` also exists in shipped data and a trinket
could have supplied it. It did not: the run's only other perk, `Perk_Trinket_ClimbingShoes`, was
already initialised long before the measurement, and `gripResist` still read **0** at that point.
Between the two readings the log shows **no** other `Initializing Perk` line, `playerPerks` went
3 → 4 (exactly one perk added), and `AddPerk` returned the object titled `Iron Grip (probe)`.

Set `spawnPool = PerkPool.never` and `spawnInEndless = false` while testing so your perk cannot
appear in real runs. Both throwaway profiles were deleted and the `doorstop_config.ini` edits
reverted.

**Not verified:** custom Addressables bundles; whether a mod-added *gamemode* reaches the main menu
(registration works, menu population was not checked); icons and perk cards, which were left null
here, so the UI side of a perk is untested.

## Gotchas

1. **The `BepInEx/` folder inside the game directory is a decoy.** On this install it contains only
   `plugins/WKMultiMod-1.8.x.zip` and **no `core/`**, so nothing there can load. `um scan` still
   reports `bepinex/plugins` as a mod dir, correctly in general but misleadingly here. **Cause:**
   r2modman keeps a complete BepInEx per profile outside the game folder. **Fix:** find the profile
   that actually launches and install there. Dropping a DLL in `<install>/BepInEx/plugins` does nothing.

2. **Work out which profile launches before you debug anything.** **Symptom:** your plugin never
   appears in the log. **Cause:** the chain is Steam launch options → r2modman's `web_start_wrapper.sh`
   → `wrapper_args.txt` → `linux_wrapper.sh --r2profile <Name>`, and only that profile's BepInEx is
   used. **Fix:** read the `LaunchOptions` string for app 3195790 in Steam's `localconfig.vdf`, and
   read `BepInEx/LogOutput.log` *in the profile*, plus `Player.log` in the save folder. A
   `Registered hand pack at: Z:\...\profiles\<Name>\...` line names the live profile outright.

3. **Doorstop environment variables do not survive Proton's container.** **Symptom:** you export
   `DOORSTOP_TARGET_ASSEMBLY` in a Steam launch wrapper, the wrapper clearly runs, and BepInEx still
   never initialises; `/proc/<pid>/environ` of the game shows no `DOORSTOP_*`. **Cause:**
   pressure-vessel builds a fresh environment for the container. **Fix:** point the **game folder's
   `doorstop_config.ini`** `target_assembly` at the absolute `Z:\...` Windows-style path of the
   profile's `BepInEx\core\BepInEx.Preloader.dll`, and keep
   `WINEDLLOVERRIDES="winhttp,version=n,b"` in the launch wrapper. That combination works.

4. **r2modman's `wrapper_args.txt` wipes itself on every launch**, by design, so a second run is
   unmodded. **Fix:** write the file and start the game in the *same* command, or you will race it
   and silently test vanilla.

5. **`CL_AssetManager.baseDatabase` is null at plugin `Awake`.** **Cause:** the databases are built
   later in startup. **Fix:** poll in a coroutine until it is non-null before registering. Calling the
   static getters earlier logs `No databases found. Initialize databases before you attempt to call.`

6. **Build `WKAssetDatabase` with `ScriptableObject.CreateInstance<T>()`, never `new`.** Unity logs
   `WKAssetDatabase must be instantiated using the ScriptableObject.CreateInstance method` otherwise.
   Note the game's own `GetFullCombinedAssetDatabase()` trips this warning internally; it is harmless
   there but will bite you if you copy the pattern.

7. **Do not reference the game's `netstandard.dll`.** **Symptom:** a wall of
   `CS0518: Predefined type 'System.String' is not defined` and
   `CS0234: ... AssemblyTitleAttribute does not exist`. **Cause:** adding Unity's stripped
   `Managed/netstandard.dll` as a `<Reference>` displaces the SDK's reference assemblies. **Fix:**
   just leave it out; `netstandard2.1` as `TargetFramework` already provides it.

8. **Two third-party mods can ship the same BepInEx GUID**, and the chainloader then silently skips
   one. Seen here between `CeSeCh-CustomEndless` and `Severon_Filnir-Odds_And_Ends`, both declaring
   `com.severon.oddsandends` in an `OddsAndEnds.dll`. **Fix:** a preloader patcher in
   `BepInEx/patchers` that rewrites the GUID and assembly name with Mono.Cecil before the chainloader
   runs. Be aware this changes the *assembly name* your own code must then compile against, which is
   its own trap: source referencing the post-patch name while the `.csproj` references the pre-patch
   DLL will not build.

9. **Steam Workshop content for this game is not levels.** `steamapps/workshop/content/3195790`
   holds small JSON **run records and leaderboard score configs**
   (`gamemodeID`, `seed`, `activeTrinkets`, `scoreData`, `runData`, `perks`), e.g.
   `ea-v08-wk-endless-abyss-climb.json`. Do not plan a "workshop level pack" route around it; custom
   levels go through WKMapLoader or Addressables instead.

10. **The game updates often, and the decompile rots.** Between 2026-10-15 and 2026-10-26, 29 files
    changed and `DEN_Mask`, `ENV_BearTrap` and `BoundsExtensions` appeared. **Fix:** re-run `ilspycmd`
    (it takes ten seconds) rather than trusting a checked-in decomp, and diff it against the old one
    to see what moved.

11. **Touching `ENT_Player` drags in ALINE.** **Symptom:**
    `CS0012: The type 'MonoBehaviourGizmos' is defined in an assembly that is not referenced ... 'ALINE'`.
    **Cause:** the player class inherits from a base type in the shipped ALINE drawing library.
    **Fix:** add `Managed/ALINE.dll` as a reference (and often `UnityEngine.PhysicsModule`). The game
    is a *shipped* build, so its inheritance chains reach third-party DLLs you would not expect.

12. **`GetPerkAsset(id)` matches on `Contains`, not equality**, and lowercases both sides. A short or
    generic id will collide with a shipped perk and silently return the wrong one. **Fix:** prefix
    your ids with your mod name. Note the sibling lookups are *not* consistent with each other:
    `GetTrinketAsset` keys on the object's `.name` (`Trinket` has **no `id` field at all**), and
    `GetSpriteAsset`, `GetRegionAsset`, `GetSessionEvent`, `GetDiskDataAsset` and
    `GetCosmeticItemAsset` use exact `==` instead of `Contains`. All verified at runtime; full table
    in [the library survey](../../techniques/white-knuckle-library-mods-what-each-offers.md).

13. **A registered perk is live content, so keep it out of real runs while testing.** Set
    `spawnPool = Perk.PerkPool.never` and `spawnInEndless = false`, or your debug perk can roll in a
    player's actual game.

14. **Probing this game means *playing* it, and it autosaves.** To reach a player you must start a
    real run, and the game then writes `wk_save.json`, `gameData.dat`, `Run Records/` and a Steam
    autocloud entry; `GAMEMANAGER - Pulling 20 roaches from global bank` moves the player's
    currency. **Fix:** `um backup create "<compatdata>/.../LocalLow/Dark Machine/White Knuckle"`
    *before* the first launch, not after. (Checked here afterwards: no probe perk persisted into
    either save and the bank was unchanged, but that was luck rather than design, because
    `AddPerk` on a perk whose `canStack`/save data you got wrong would have.) This cuts deeper than
    tidiness: perks are saved by `id` through `Perk.PerkSaveData`, and the load path does
    `Instantiate(CL_AssetManager.GetPerkAsset(savedId))` **with no null check**. A save written while
    your mod was active therefore references an id that no longer resolves once the mod is removed,
    and loading it instantiates null. Ship a mod that grants perks and you have made your users'
    saves depend on your mod staying installed.

## Cost and time

One session, no API spend. The decompile is ~10s; the probe build-install-launch-read loop is about
two minutes per iteration, dominated by Proton startup.

## Open questions

- Icons, perk cards and frames were left null here, so the **UI side** of custom content is untested.
  A perk with no `icon`/`perkCard` may throw where the game draws it.
- Custom **Addressables** bundles for new levels: WKMapLoader and WKLib both wrap this, but shipping
  your own catalog was not attempted.
- WKLib lists custom items as unimplemented. Registering a database is clearly the missing piece, so
  it is probably worth contributing upstream rather than reimplementing this in each mod.

### Resolved: registering a gamemode does NOT put it in the menu

This was listed as open; it is now settled, and confirmed in-game rather than inferred. A gamemode
registered through `AddNewDatabase` *was* findable via `CL_AssetManager.GetGamemodeAsset`, but of the
**61** `UI_Gamemode_Button` instances live in the scene, none held it.

The reason is structural: `WKAssetDatabase.gamemodeAssets` is referenced **only** by
`CL_AssetManager`, and the menu is built from prefab `MonoBehaviour`s that each hold one
`M_Gamemode` (`UI_Gamemode_Button`, `UI_GamemodeScreen` and `UI_GamemodeScreen_Panel` all implement
the `GamemodeHolder` interface), laid out in the scene.

So `AddNewDatabase` makes a mode *findable by id*, but cannot make it appear in the Play menu. Every
library that shows custom content in a menu patches the UI to do it: WKMapLoader postfixes
`UI_TabGroup.Start` to inject its CUSTOM tab, and CiCi's framework prefixes
`UI_GamemodeScreen.Initialize`. **Registration is necessary but not sufficient for anything
menu-facing.** Content that the *game* looks up by id (perks, items, trinkets) works from
registration alone; anything a *player* must click needs a UI patch too.
