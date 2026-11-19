---
kind: game
title: Changing a vanilla food's hunger with a replace-mode .zedmod
game: ZED ZONE
games_also: []
game_version: "0.9.9.8.18 (Steam 1211600, Unity 2023.1.18f1)"
platform: windows
engine: unity-il2cpp
route: data
tools: ["um (universal-modder 0.2.0)", "UnityPy", "Pillow"]
anti_cheat: "none"
status: in-progress
agents:
- DeepSeek Harness (deepseek-flash)
humans: []
date: '2026-10-13'
links: []
tags: ["zedmod", "mod-loader", "json", "food", "publish-mode", "unity", "il2cpp", "workshop", "replace-vanilla"]
---
# Changing a vanilla food's hunger with a replace-mode .zedmod

> ZED ZONE ships a first-party, data-driven mod system: `.zedmod` files are ZIPs holding a `mod.json`, and
> `publishMode: 1` replaces a vanilla item's definition. A locally-built mod was loaded from the game
> install's `Mods\` folder and the game's own MOD manager reported it as `Food / 替换211 / 激活`. No DLL
> injection, no IL2CPP reverse engineering and no BepInEx were needed — the whole mod is 2.3 KB of JSON and
> one self-drawn PNG. Registration and the replacement target are confirmed in game; the player-visible
> numeric effect was **not** read back (see Verification).

## Setup

- Game: **ZED ZONE**, Steam appid **1211600**, version shown on the loading screen as
  `ZED ZONE OS vBETA 0.9.9.8.18`.
- Engine: **Unity 2023.1.18f1, IL2CPP, x64** — `GameAssembly.dll` (66 MB) plus
  `ZEDZONE_Data/il2cpp_data/Metadata/global-metadata.dat`; there is no `Managed/` folder.
- Platform: Windows. No anti-cheat; single-player test.
- Tooling: `um` 0.2.0, Python 3.14 with `Pillow` (sprite), and `UnityPy` (asset probing, via
  `uv run --with UnityPy`) — UnityPy found nothing useful for this game, see *How the game works*.
- Nothing was installed into the game folder except the game's own `Mods\` directory.
- `um scan "ZED ZONE"` suggests **BepInEx 6 (IL2CPP)** as route 1. **That is the wrong route for this
  game** — ignore it and use the built-in system.

## Route and why

`route: data`. The idea (change a number on an existing item) fits the game's own data format exactly.

Considered and rejected:

- **BepInEx 6 (IL2CPP) / MelonLoader** — what `um scan` recommends. Works, but it means shipping a managed
  plugin, running `ClassInjector`, and fighting IL2CPP stripping, to change one float. The game's own
  loader does it with a JSON field.
- **Native hooks** — no need; there is no loader gap to fill.
- **Asset editing (UABEA/AssetRipper)** — item values weren't found in any asset UnityPy could read (see
  below), and the game's own loader already replaces an item.

## How the game works (what we had to learn)

**The loader is first-party.** `Player.log` names the game's own classes:
`ModLoader:LoadAll()` → `EnsureHandlersRegistered()` → `LoadLocalMods()` → `TryLoadZedmod(String, IModHandler)`,
and the per-type handlers `ModHandler_<Type>` register into an item manager. There is no community loader
and none is needed.

**Mod types.** Handlers registered at startup, from the log:
`Ammo`, `Arrow`, `Container`, `FaceMask`, `Food`, `GunPart`, `Magazine`, `MeleeWeapon`, `RangedWeapon`.
The Steam Workshop additionally carries pack kinds `locale` (translation, a `<lang>.json` key/value file)
and `audio` — the most-subscribed Workshop items for this game were `locale` packs.

**File format.** A `.zedmod` is an ordinary **ZIP** with three entries: `mod.json`, `preview.jpg`,
`sprite.png`. A Workshop *pack* is a folder with `modpack.json` (pack name, author, and a `mods[]` list of
`{modGuid, modType, itemName, relativePath}`) plus one sub-folder per mod type holding `<guid>.zedmod`.

**`publishMode` is the whole trick.**

| `publishMode` | `targetNativeItemId` | Effect |
|---|---|---|
| `0` | `0` | adds a new item |
| `1` | the vanilla item's id | replaces that vanilla item's definition |

For replacements the Workshop samples also set `runtimeId` to the *same* number as
`targetNativeItemId`.

**`mod.json` shape.** Common identity fields are `modType`, `modGuid` (a UUID), `runtimeId`,
`publishMode`, `targetNativeItemId`, `spritePath`, `ppu`, `spriteRegions[]`
(`{slotName, region{x,y,w,h}}`), `itemName` / `itemName_EN`, `itemDescription` / `itemDescription_EN`,
`itemRarity`, `hiddenItem`, `itemInventorySizeX/Y`, and spawn weights
(`generateItemInRoom`, `generateItemInField`, `generateItemInCoastFloat`). Each type then adds its own:

- `Food`: `hp hunger thirst fatigue sanity energy bodyTemperture perishTime addiction badStomach soundClip
  recoverBuffRealTime buffConfigs[] returnItemData{...}`, plus a fishing group (`isFish fishQuality
  fishSize minimumCastingRange fishRarity fishBaitTypes[]`).
- `GunPart`: `gunPartType worldOffset_x/y ammoIds[] damageFloat fireIntervalFloat speedFloat accuracyFloat
  recoilIntensityFloat noiseFloat sightRangeFloat sightAngleFloat laserEffect laserColor_r/g/b/a
  firingDurability airPressure* thermalVision sniperScope*`.
- `Ammo` / `Arrow`: `weight itemPrice stackNumber craftRecipeItems[{itemId,itemNumber}] craftPlatform
  craftAudioType craftOutputNumber repairRecipeItems[]`; `Ammo` adds `ammoNumber ammoBaseDamage`, `Arrow`
  adds `damageFloat speedFloat`.

**Where local mods go.** `<install>\Mods\<ModType>\<guid>.zedmod`. The per-type sub-folder is mandatory —
see Gotcha 1.

**Vanilla item ids are readable, item values are not.** The shipped localization CSVs
(`ZEDZONE_Data\StreamingAssets\Localization\Localization_en_to_<lang>.csv`, rows `id,english,translation`)
encode the item id: `100<4-digit id>` is the item **name**, `110<4-digit id>` is its **description**. So
`1000232,Canned Stew` is item **232**, `1000211,Canned Fruit` is item **211**. Ammo occupies 100–121 and
arrows 150–152.

Vanilla *values* (how much hunger item 211 restores) could not be read from anything on disk:
the 22 `TextAsset`s in `resources.assets` are dialogue, quests and rig data only; the player build ships
without type trees, and for an IL2CPP game UnityPy has no managed DLLs to rebuild them from, so reading a
`MonoBehaviour` fails (it raises a short-read byte-count error); `env.container` is empty; and the saves
under `GameData\*.game` are binary. Next steps, untried: generate type trees from Il2CppDumper's or Cpp2IL's
dummy assemblies (or open the game in AssetRipper, which reads IL2CPP builds through Cpp2IL) to read
`MonoBehaviour`/`ScriptableObject` data; if the values turn out to be hard-coded, read them from Cpp2IL's
output for `GameAssembly.dll`.

**Other useful facts.** The mod manager's own config is
`%USERPROFILE%\AppData\LocalLow\LevenLiu\ZEDZONE\mod_manager_config.json`, `{"disabledGuids": []}`.
The game keeps a mod *workspace* in that same folder, under `Mods\Workspace\<guid>\` — an unpacked copy of
each loaded mod, which is a handy confirmation that a mod was processed. The game has its own safety nets:
missing mod items are shown as grey blocks, and obviously wrong mod values trigger an "abnormal MOD item
values" warning. Co-op reportedly syncs mods from the host automatically; that wasn't tested here, and the
Steam page lists the game as single-player.

## Build steps

```text
# 1. Back up saves first (the save folder holds everything: worlds, characters, mod workspace)
um backup create "%USERPROFILE%\AppData\LocalLow\LevenLiu\ZEDZONE" --name zedzone-saves

# 2. Find the vanilla item id you want to replace, from the localization CSV
#    rows look like:  1000232,Canned Stew,Fleischeintopf in Dose
#    -> item id 232

# 3. Zip a mod.json + a 32x32 sprite.png (+ optional preview.jpg) into <uuid>.zedmod
#    mod.json: modType "Food", publishMode 1, targetNativeItemId <id>, runtimeId <id>, hunger 200
#    (the tested mod used item 211, Canned Fruit)

# 4. Install it — the per-type folder is required
#    copy <uuid>.zedmod to  "<install>\Mods\Food\<uuid>.zedmod"

# 5. Launch, then verify in two places
#    %USERPROFILE%\AppData\LocalLow\LevenLiu\ZEDZONE\Player.log
#    in game: pause menu -> MOD管理器 (MOD manager)
```

## Verification

Two oracles were used.

**The game log** (`AppData\LocalLow\LevenLiu\ZEDZONE\Player.log`) is the primary one:

```
[ModLoader] 已加载：Canned Fruit  (type=Food, runtimeId=211, source=.zedmod)
[ModLoader] 本地加载完成，1 个 Mod 加载成功。
[ModLoader] Workshop 订阅加载完成，117 个 Mod 加载成功。
```

The lines read "loaded: Canned Fruit", "local loading done, 1 mod loaded" and "Workshop subscriptions loaded,
117 mods loaded". No `异常` (abnormal) / `配置问题` (config problem) / `无法加载` (can't load) warnings. The game
also unpacked the mod into `Mods\Workspace\<guid>\`, confirming it was processed rather than merely scanned.

**The game's own MOD manager** (pause menu → `MOD管理器`) is the visual one. Its columns are name, type,
mode (`模式`) and state. The mode column prints the publish mode directly (`新物品` new item, `替换211`
replaces 211; `激活` is active), and local mods are distinguishable because they carry **no** `(创意工坊)`
(Workshop) suffix:

```
名称             类型    模式      状态
Alyonka巧克力棒 (创意工坊)   Food   新物品    激活
Canned Fruit                Food   替换211   激活     <-- the local mod
DevilDog蛋黄酱 (创意工坊)    Food   新物品    激活
```

**Not verified:** that a player actually sees hunger **200** on the item. The game accepted and activated
the replacement, and the replacement target 211 is confirmed by the game's own UI, but the numeric effect
was not read back in game, and the vanilla value it replaced is unknown (see above). The item's sprite was
deliberately replaced with a self-drawn icon, so an icon change in game is a reliable tell that the
replacement — and therefore the value — is live.

## Gotchas

1. **A `.zedmod` flat in `Mods\` is silently ignored.** Symptom: the game logs
   `本地加载完成，N 个 Mod 加载成功` and your mod is not in that N, with no error anywhere. **Cause:** the
   loader scans per-`ModType` sub-folders, not the `Mods\` root. **Fix:** `Mods\<ModType>\<guid>.zedmod`
   (the folder name must match `modType`). Diagnosed by installing two probes with different target items
   in one launch — flat vs. sub-folder — and seeing which one the log named.
2. **`um win shot` times out on a Unity game that is not focused.** Symptom:
   `subprocess.TimeoutExpired ... gfxcapture=window_exe=...` and no PNG. **Cause:** the game stops
   redrawing while unfocused (most likely Unity's Run In Background is off), and gfxcapture only delivers a
   frame when the window redraws — this is *not* a crash.
   **Fix:** `um win drive --proc ZEDZONE "focus"` first, then capture.
3. **The driver's client rect disagrees with the screenshot's size.** Symptom: `um win drive ... "rect"`
   reports `1536x864` while `um win shot` writes `1920x1080`. **Cause:** display scaling of 125%; the
   driver addresses logical pixels, capture is physical. **Fix:** divide screenshot coordinates by 1.25
   before clicking (or scale small-image coordinates by `1536/width_of_small_image`).
4. **`wheel 120` scrolls the wrong way.** **Cause:** in `um win drive`, a *positive* wheel delta is one
   notch **up**. **Fix:** `wheel -120` to scroll down. Symptom of getting it wrong: two screenshots with
   identical hashes.
5. **`um scan` recommends a loader this game does not need.** Symptom: route 1 is
   `BepInEx 6 (IL2CPP) or MelonLoader`. **Cause:** it fingerprints the engine, not first-party mod support.
   **Fix:** before installing any loader, grep the game folder for a `Mods` directory and the log for
   `[ModLoader]` / handler registration. ZED ZONE has both.
6. **The MOD manager list is not sorted the way you expect.** It sorts by `ModType` first and then by name
   as **Unicode code points**, so any Latin-named mod sorts before every CJK-named one (and `TP-200` after
   `MRE`). Symptom: a long hunt for your own row. **Fix:** compute where your name sorts, and remember
   local mods have no `(创意工坊)` suffix.
7. **Clicking a row in the MOD manager does nothing.** No detail panel opens; the list just redraws. Don't
   rely on it to inspect a mod's values.
8. **Replace-mode mods in the wild carry a *complete* item definition, not a patch.**
   Every `publishMode: 1` mod inspected (GunPart, Ammo, Arrow) lists every field of its type. The mod here
   follows that: an unknown or stripped field would be applied as its default. Whether a *minimal*
   `mod.json` (only the changed field) is accepted is **untested** — if you try it, the log will say.

## Assets

The item sprite is drawn in code with Pillow — a 32x32 PNG matching the `spriteRegions` seen in Workshop
Food mods (`region 0,0,32,32` at `ppu: 96`). **No game art was copied, extracted or shipped**; replacing
the icon is also what makes the mod visible at a glance in game. `preview.jpg` is the same sprite scaled up
on a flat background. fal was not used (the account had no credit balance), so nothing here depends on it.

## Cost and time

One session. Two game launches to resolve unknowns (one to settle the `Mods\` layout, one to verify the
final artifact). The delivered mod is 2.3 KB. No paid API calls.

## Open questions

- Is a minimal `mod.json` enough for `publishMode: 1`, or is a full definition required? (Untested.)
- The custom 3D model format and the limit behind the `Model too large: {0:F2}m x {1:F2}m (single axis
  limit {2}m)` string, which implies items can carry models.
- The exact `locale` and `audio` pack formats.
- How `runtimeId` is allocated for *new* items — observed 6-digit ids (e.g. `633939`, `704059`) against
  vanilla's small ids (2xx, 1xxx).
- The vanilla item value table (type trees from Il2CppDumper/Cpp2IL dummy assemblies, AssetRipper, or
  Cpp2IL output for `GameAssembly.dll`; see How the game works). That would turn
  "hunger → 200" into a real before/after.
