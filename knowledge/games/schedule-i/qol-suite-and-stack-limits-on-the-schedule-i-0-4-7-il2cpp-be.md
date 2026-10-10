---
kind: game
title: QoL suite and stack limits on the Schedule I 0.4.7 IL2CPP beta with MelonLoader
game: Schedule I
games_also: []
game_version: "0.4.7f9 IL2CPP (Steam 3164500, beta branch, buildid 25698382); also read the Mono alternate-beta 0.4.7f6"
platform: proton
engine: unity-il2cpp
route: managed-patch
tools:
- MelonLoader 0.7.3
- HarmonyX
- ilspycmd 11.1
- umu-run + GE-Proton11-6
- rsvg-convert + Pillow (icons)
anti_cheat: "none found; co-op is FishNet over Steam P2P. Built and tested single-player only"
status: working
agents:
- Claude Code (Opus 5.5)
humans:
- Malekabokhatwa
date: '2026-10-05'
links:
- https://github.com/Malekabokhatwa/PocketPlug
- https://github.com/Malekabokhatwa/IncreasedStackLimit-Latest
tags: [il2cpp, melonloader, phone-app, compass, stack-size, ui, linux, proton]
---
# QoL suite and stack limits on the Schedule I 0.4.7 IL2CPP beta with MelonLoader

> These are two MelonLoader mods for the Schedule I 0.4.7 IL2CPP beta, both written as C# Harmony mods (the managed-patch route).
>
> - **IncreasedStackLimit-Latest** (based on froggy's original IncreasedStackLimit) raises stack limits for each item type.
> - **PocketPlug** is a QoL suite. It adds a deal compass with the customer's portrait, name and distance, plus Bank and Settings apps built from scratch on the phone. It also removes the weekly ATM deposit limit and adds dealer bank transfers, ready alerts, deal reminders and endless skating.
>
> Both run in the real game on Linux/Proton. Most pieces were checked with the MelonLoader log and with in-game screenshots taken by Unity itself, driven by a dev command file; the rest are listed as not verified under Verification.

## Setup
- **Game:** Steam, Linux, through GE-Proton11-6.
  - The `beta` branch is IL2CPP, 0.4.7f9 (buildid 25698382).
  - The `alternate-beta` branch is Mono, 0.4.7f6. It's the same C# as the matching IL2CPP build and decompiles to near-source, so use it as the readable reference.
- **Loader:** MelonLoader 0.7.3 (2026-05-14), installed as the `version.dll` proxy.
  - Steam launch option: `WINEDLLOVERRIDES="version=n,b" %command%`.
  - The first IL2CPP launch generates `MelonLoader/Il2CppAssemblies` with Cpp2IL and Il2CppInterop, which takes about 30 s. Expect "Failed to restore 885 methods / 3 fields"; it's harmless.
- **Build:** .NET SDK 10, targeting `net6.0`.
  - Reference `MelonLoader/net6/{MelonLoader,0Harmony,Il2CppInterop.Runtime,Il2CppInterop.Common}.dll` and `MelonLoader/Il2CppAssemblies/*.dll`.
- **Lab without Steam:** `umu-run` with `GAMEID=umu-3164500` and `PROTONPATH=<GE-Proton>`, plus `steam_appid.txt` in the game folder. Steam must be running.
  - Saves then land under `Saves/TempPlayer/` instead of your SteamID.
- **S1API (ifBars):** broken on 0.4.7 at the time of writing ([S1API#305](https://github.com/ifBars/S1API/issues/305)). These mods don't depend on it.

## Route and why
Harmony patches plus direct field writes through the Il2CppInterop assemblies. No asset bundles; all UI is built at runtime with uGUI.

## How the game works (what we had to learn)

### Stack limits
- The limit lives on the definition: `ScheduleOne.Core.Items.Framework.BaseItemDefinition.StackLimit` is a public int (it moved to `ScheduleOne.Core.dll` in 0.4.7).
- `BaseItemInstance.StackLimit` just reads `_definition.StackLimit`.
- Several systems read the **definition field directly**: `DeliveryInstance`, `DeliveryShop.WillCartFitInVehicle`, the shop `Cart`, `Supplier` dead drops and `SpecialCustomerLeader`. So patching only the instance getter (what older mods did) leaves those on vanilla sizes. Writing the definition field covers everything.
- **Where to write:** loop over `Registry.GetAllItems()`. `Registry` is a `PersistentSingleton` and is filled in `Awake`. Postfix `Registry.AddToRegistry(ItemDefinition item)` to catch definitions added at runtime.
- **New product mixes** are `Object.Instantiate(DefaultWeed)` (and the same for meth, cocaine and shroom). They copy the template's *current* `StackLimit`, so remember originals or multipliers compound.
- **Vanilla limits on 0.4.7f9:** only 1, 10 or 20, across 227 items.
- **Item classification:** use the definition class, since the `EItemCategory` buckets are coarse.
  - `ProductDefinition` (Weed, Meth, Cocaine and Shroom subclasses) derives from `PropertyItemDefinition`, which is also the mixer class, so check product first.
  - The other classes: `PackagingDefinition`, `QualityItemDefinition`, `SeedDefinition`, `SoilDefinition`, `AdditiveDefinition`, `SporeSyringeDefinition`, `ShroomSpawnDefinition`, `BuildableItemDefinition`.
- **Ammo has no type of its own.** Find it as `Equippable_RangedWeapon.Magazine` on `ItemDefinition.Equippable`; on 0.4.7f9 that's `shotgunshell`.
- **Guns and melee** are found the same way: `Equippable_RangedWeapon` / `Equippable_MeleeWeapon` on the equippable.

### Compass
- `CompassManager` (singleton) creates one `Element` per quest entry: `QuestEntry.CreateCompassElement` uses `ParentQuest.IconPrefab`.
- `Element.DistanceLabel` is a TMP `Text` child. The game only fills it within 50 m, using `UnitsUtility.FormatShortDistance`, which follows the Metric/Imperial setting.
- Deals are `Contract` quests (`Contract.Contracts`). `Contract.Customer` is a `NetworkObject`, so call `GetComponent<NPC>()` on it.
- The portrait the Contacts app shows is `NPC.MugshotSprite` (`RelationCircle.HeadshotImg`).
- Element children are `QuestElement(Clone)`, which contains `Text` plus the quest icon clone.
- The element container `Quests` is **800×30 with a `RectMask2D`**, so anything drawn under a marker is clipped unless you set `RectMask2D.padding` (we use `(0,-60,0,0)`).

### Phone apps
- Native apps are `App<T> : PlayerSingleton<T>`. You can't subclass that from an IL2CPP mod (injecting a generic-derived type isn't practical), so build an app by hand instead, the way [S1API's PhoneApp](https://github.com/ifBars/S1API) does:
  - Add a page under `HomeScreen.transform.parent/AppsCanvas`.
  - Clone `HomeScreen.appIconPrefab` into `appIconContainer`, then add it to `homeScreen.appIcons` and `homeScreen.uiPanel`.
  - Open and close by repeating `App.SetOpen`: `AppsCanvas.SetIsOpen`, `HomeScreen.SetIsOpen(!open)`, `Phone.ActiveApp = page`.
  - Hook `Phone.closeApps` and `GameInput.RegisterExitListener`. Convert the delegate with `DelegateSupport.ConvertDelegate<GameInput.ExitDelegate>`.
- AppsCanvas is 1201×655 (landscape). Portrait apps are 655×1201 pages rotated **90°**; the native Messages app does the same.
- To open the phone from code, call `GameplayMenu.Open()` then `SetScreen(EGameplayScreen.Phone)`. `Phone.SetIsOpen` alone only sets state.
- `NotificationsManager.SendNotification(title, subtitle, sprite, duration, sound)` shows the game's own notification toast.

### Money
- `MoneyManager.ChangeCashBalance(delta, visualize, sound)` changes cash. `CreateOnlineTransaction(name, unit, qty, note)` is a ServerRpc with `RunLocally`, and it changes the bank balance and appends to `ledger`.
- The ledger is session-only. It is not saved.
- The weekly deposit limit is `ATM.WeeklyDepositLimit = 10000` (a **const**), enforced only inside `ATMInterface`. `ATM.WeeklyDepositSum` (static) also triggers `Quest_CleanCash` once it reaches 10000.
- On IL2CPP, the online balance's SyncVar property can't be used from C#. Call `sync___get_value_onlineBalance()`.

### Dealers
- `Dealer.AllPlayerDealers`, `Dealer.Cash` and `Dealer.SetCash`.
- `NPC.MSGConversation.CreateSendableMessage(text)` adds a player message option with `onSent` (an `Il2CppSystem.Action`) and `ShouldShowCheck` callbacks.

## Build steps
1. Install MelonLoader 0.7.3 into the IL2CPP install and launch once to generate the assemblies.
2. Clone the mod repo and run `dotnet build src -c Release -p:GameDir="<Schedule I>" -p:DeployToGame=true`.
3. Launch from Steam. Settings are in `UserData/<Mod>.cfg`.

## Verification
- **Oracle:** the MelonLoader log (`MelonLoader/Latest.log`) plus a dev command file read by the mod. It only works when `UserData/PocketPlug.dev` exists. The commands:
  - `load` calls `LoadManager.StartGame(SaveGames[0])`.
  - `phone open`, `app <id>`.
  - `click <app> <path>` invokes a button's `onClick`.
  - `shot` calls `ScreenCapture.CaptureScreenshot`, which works even when the game window is on another Wayland workspace.
  - `dump <name>` writes the transform tree with rects, rotation, colors and fonts.
  - `fakedeal` adds a compass element on a real NPC.
  - `money` logs cash and bank.
- **Verified in game:**
  - Stack limits: 133 of 227 items raised; the shotgun shell is the only stackable item left unchanged; toggles and live config reload work.
  - Settings app toggles and +/- buttons write the config and reapply immediately.
  - Bank app deposit and withdraw conserve money (cash 1542→1442→1542, bank 0→100→0).
  - Notifications show.
  - The compass marker shows the portrait in a green ring, the name, and the game-unit distance ("45ft"), seen in a screenshot.
- **Play-tested by the user:** stack limits and bank app (which found a duplication bug, now fixed; see Gotcha 4).
- **Not yet verified in game:** ready alerts on real stations, deal reminders, dealer transfers (the save had no recruited dealer or active deal), endless skating, and the ATM no-limit patch at a physical ATM.

## Gotchas
1. **froggy's original IncreasedStackLimit "works" but deliveries ignore it.** Cause: it only postfixed the instance getter, and delivery, cart and dead-drop code reads `BaseItemDefinition.StackLimit` directly. Fix: write the definition field.
2. **Raising some stack limits causes bugs.** The user's report, not ours: ammo misbehaves above its vanilla limit. Fix: never touch weapons, ammo (detected from `RangedWeapon.Magazine`) or limit-1 items, and never lower a limit.
3. **Custom phone app opens, but the scroll list is empty.** Cause: the app page is rotated 90°, and `RectMask2D` clips in canvas space, so it clips everything. Fix: use a stencil `Mask` (an `Image` with alpha 1, `showMaskGraphic = false`).
4. **Bank app duplicated money on real clicks**, though `onClick.Invoke()` once was correct. Cause: a clicked uGUI `Button` becomes the selected object, and the game's Submit input then fires `onClick` again. Fix: set `navigation.mode = None` on the mod's buttons, plus a 0.3 s guard on money actions.
5. **`NPC.MugshotSprite` throws a NullReferenceException** for NPCs without appearance data, and it does so inside the IL2CPP getter. Fix: wrap it in try/catch.
6. **Name and distance under a compass marker are invisible.** Cause: the 30 px `Quests` container has a `RectMask2D`. Fix: extend `padding` downward.
7. **Harmony stacked `[HarmonyPatch]` attributes don't give multiple targets.** Fix: use `TargetMethods()` to mask the weekly sum around each `ATMInterface` method. The limit is a const, so it can't be patched directly; the mod temporarily swaps `ATM.WeeklyDepositSum` for a huge negative number and restores the real value plus any deposit afterwards.
8. **MelonPreferences does not reload `MelonPreferences.cfg` when it's edited under Wine.** Fix: `category.SetFilePath(own file)`, poll its mtime about once a second, and call `LoadFromFile`.
9. **The dev command file ran twice under Wine,** because the delete lags behind the read. Fix: remember the file's last-write time and skip a file you've already handled.
10. **Steam-launched Proton prefix `compatdata/3164500` doesn't exist** until the first Steam launch of that install. A fresh lab prefix saves under `Saves/TempPlayer/`. Moving a save between them is fine for the host, because `PlayerManager.TryGetPlayerData` loads `Player_0` for the host first.
11. **The lab was Mono, but an old mod in it was an IL2CPP build** (it referenced `Il2CppInterop` and `Il2CppScheduleOne.*`). Backend-mismatched mods fail at load, so check the references before trusting an installed mod.

12. **Regular ~200 ms freezes every 2 s.** Cause: polling with `Object.FindObjectsOfType<T>()` for seven station/pot types. In this IL2CPP scene each pass cost about 190 ms. Fix: walk `Property.OwnedProperties[i].BuildableItems` instead, cache each item's `TryCast` type once, and check 12 items per frame. Found with a dev perf probe that logs frames over 150 ms and features over 2 ms. After the fix: 0 hitches after load.

## Assets
- **Icons:** [Lucide](https://lucide.dev) SVGs (ISC), rendered with `rsvg-convert` and composited on gradient squares with Pillow (`scripts/make-icons.py` in the PocketPlug repo).
- **Compass ring and circle mask:** drawn procedurally. No generated art.

## Cost and time
About two working sessions, including recon, two mods and the in-game test loop. Each restart-to-in-game cycle takes about 2 minutes.

## Open questions
- The not-yet-verified features listed under Verification.
- Co-op behaviour. Both mods are single-player only. Stack limits would need the same config on every client.
- Whether `ATMInterface.ProcessTransaction`, a coroutine, needs anything more once the mask is in place. It reads the real sum, so it should be fine.
