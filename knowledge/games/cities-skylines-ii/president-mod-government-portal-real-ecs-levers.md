---
kind: game
title: "A President mod for Cities: Skylines II: a government portal over the live city, real ECS levers, a court of real residents"
game: "Cities: Skylines II"
games_also: []
game_version: "1.6.2f1 (767.21d1), Steam app 949230 build 25127643 (public branch), Unity 2022.3.71f1 Mono, Entities 1.3.10"
platform: windows
engine: unity-mono
route: loader-api
tools: ["CS2 Modding Toolchain (in-game installer: Unity 2022.3.62f2, Burst 1.8.23, csiimod template, create-csii-ui-mod)", ".NET SDK 10 (mod targets net48; offline simulator net8.0)", "Node 24 + webpack 5.97.1", "ilspycmd 11.1.0.9782", "VS Code + C# Dev Kit + Unity extension 1.3.2", "Unity 2022.3.71f1 development Mono player (debugging, staged)", "Lib.Harmony 2.2.2 (toolchain smoke test only)", "Microsoft Edge headless (UI previews)", "fal (images, some SFX)", "um backup", "um kb"]
anti_cheat: "none: single-player city builder with an official mod API; nothing bypassed"
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: ["@skurtyyskirts"]
date: 2026-10-18
links: ["https://cs2.paradoxwikis.com/Modding_Toolchain", "https://cs2.paradoxwikis.com/UI_Modding", "https://cs2.paradoxwikis.com/Debugging", "https://cs2.paradoxwikis.com/Developer_mode", "https://cs2.paradoxwikis.com/Asset_Creation_Guide", "https://github.com/icsharpcode/ILSpy", "https://github.com/krzychu124/Traffic", "https://github.com/AlphaGaming7780/ExtraAssetsImporter"]
tags: [ecs, unity-dots, gameface, ui-mod, city-modifiers, district-modifiers, efficiency-factor, save-safety, puppets, culling, offline-simulator, headless-preview, dev-bridge, paradox-mods, toolchain-setup]
---

# A President mod for Cities: Skylines II: a government portal over the live city, real ECS levers, a court of real residents

> "Oval Office" makes the player the President of their own city. You govern from a photographed desk or a
> 14-tab Government Portal laid over the live city. Every action resolves to effects the game applies: taxes,
> budgets, fees, policies, held city and district modifiers, company and household cash, an owned efficiency
> factor, and real arrests. The mod also has a court built from real residents (61 case types), factions,
> protests, press, rumours, a 10-tier levelling ladder and eleven optional modules. Route: the official C# code
> mod plus an official UI mod, with every rule in plain C# tested offline against a stub city. v1 was checked in
> the real game by the agent through a dev bridge. v2 (the portal, levers, ladder, modules) is offline-tested
> only: it compiles against the game, is deployed to the local `Mods` folder, and waits for the human's
> in-game test.

Related notes: [the CS1/CS2 modding-API overview](../cities-skylines/cities-skylines-modding-api-and-container-formats.md)
(not verified in game; this note supersedes its CS2 toolchain part for 1.6.2f1) and
[the CS1 live city dashboard](../cities-skylines/read-only-live-city-dashboard-for-cities-skylines-1-an-http-.md)
(the same "read the city, show it in a browser-style UI" idea on CS1's `IUserMod`).

## Setup
- Cities: Skylines II **1.6.2f1 (767.21d1)**, Steam app 949230, build 25127643, public branch (no `BetaKey` in the
  app manifest). Windows 11. Unity **2022.3.71f1 (c9bf13b0b844)** Mono, DOTS/ECS with Entities 1.3.10, D3D11.
  The player's normal playset had 151 Paradox Mods subscriptions (managed with Skyve); the mod has no
  dependencies on them.
- **Official Modding Toolchain**, installed from the game: Options > Modding > Install. It installs Unity
  **2022.3.62f2** (the toolchain's editor, not the game's 2022.3.71f1), builds `UnityModsProject` under
  `%USERPROFILE%\AppData\LocalLow\Colossal Order\Cities Skylines II\.cache\Modding` (Entities 1.3.10 source
  generators, Burst 1.8.23), sets the `CSII_*` user environment variables (`CSII_TOOLPATH`, `CSII_USERDATAPATH`,
  `CSII_MODPUBLISHERPATH`, `CSII_MODPOSTPROCESSORPATH`, `CSII_UNITYVERSION=2022.3.62f2`, ...) and registers
  the `dotnet new csiimod` template. A free Unity Personal license is required (see Gotcha 1).
- The toolchain's own files live in the game folder under `Cities2_Data\Content\Game\.ModdingToolchain`:
  `Mod.props` / `Mod.targets` (net48, LangVersion 9.0), `ModPostProcessor`, `ModPublisher\ModPublisher.exe`,
  `npx-create-csii-ui-mod` (installed globally with npm as `@colossalorder/create-csii-ui-mod` 1.0.0) and
  `ExampleAssets` (13 example asset folders).
- **.NET SDK 10** (`dotnet build` for the net48 mod; the offline simulator in `tests/Sim` targets net8.0).
  **Node 24** for the UI template (it needs >= 18); webpack 5.97.1 comes with the template.
- **ilspycmd 11.1.0.9782** (`dotnet tool install -g ilspycmd`). `Game.dll` plus 12 `Colossal.*` assemblies were
  decompiled into a reference folder outside every repository (Game.dll alone is 4,416 files, about 17 s).
  Used only for reading APIs; none of it is in the mod or this note.
- Seven public CS2 mods were cloned (outside the repo) to read how real mods do things:
  [Traffic](https://github.com/krzychu124/Traffic), [CS2-MoveIt](https://github.com/Quboid/CS2-MoveIt),
  [ParkingLotTool](https://github.com/KruemelGames/ParkingLotTool),
  [ModularTransportStation](https://github.com/rodrigmatrix/ModularTransportStation),
  [Time2Work](https://github.com/ruzbeh0/Time2Work),
  [cs2-ecs-explorer](https://github.com/Captain-Of-Coit/cs2-ecs-explorer),
  [CS2-Modding-Instructions](https://github.com/rcav8tr/CS2-Modding-Instructions), plus
  [ExtraAssetsImporter](https://github.com/AlphaGaming7780/ExtraAssetsImporter).
- Debugging (staged, never applied for this mod): VS Code with C# Dev Kit and the **Unity** extension
  (`visualstudiotoolsforunity.vstuc` 1.3.2), and the **development Mono `UnityPlayer.dll` of the game's exact
  Unity build** (2022.3.71f1), which the [Debugging](https://cs2.paradoxwikis.com/Debugging) page says to copy
  into the game folder together with `player-connection-debug=1` at the end of `Cities2_Data\boot.config`. See
  Gotcha 3 for a 182 MB way to get that DLL.
- Saves snapshotted with `um backup create "<...>\Cities Skylines II\Saves" --name cs2-saves` (917 MB) before
  every modded launch and before every deploy that would load an existing presidency; `ModsSettings` too.

## Route and why
- **Official code mod + official UI mod, no Harmony in the mod.** Every lever the design needed is reachable
  from a `GameSystemBase` on the main thread through ECS components, buffers and public systems. The toolchain
  is supported and the mod publishes through Paradox Mods. `um scan` fingerprints CS2 as Unity Mono and
  suggests BepInEx; that is the outdated 2023 route (Gotcha 2).
- Harmony was considered for some levers and rejected: almost every simulation job is Burst-compiled, and
  Harmony patches only reach managed code, so patching a static helper would change what the UI shows, not what
  the simulation does. Levers write ECS state instead (stocks, held modifiers, an owned efficiency factor).
- **Three layers:**
  - `src/Core`: plain C# with no Unity references. Every rule lives here: the presidency, legislature, court,
    powers, consequences, sentiment, factions, protests, press, ladder and the modules. It is compiled into
    the net48 mod and also into a net8.0 console simulator (`tests/Sim`) that runs it against stub cities.
  - `src/Bridge`: ECS systems. Read ports fill an `ICity` snapshot (telemetry), and effect levers apply
    `EffectKind`s (Money, Tax, Budget, Fee, Policy, Modifier, DistrictModifier, PolicePosture, Wellbeing,
    HouseholdCash, CompanyCash, FirmEfficiency, FirmClose, Arrest, RoadRepair, RepairDamage, PollutionCleanup,
    CrimeReduction). The Bridge also holds the motorcade/crowd puppets and the save hook.
  - `ui/`: React 18 on Coherent Gameface. It renders JSON view models that the Core writes and sends actions
    back through bindings.
- **Persistence:** one `IDefaultSerializable` system writes a versioned block into the city save. The block
  holds the state as JSON plus a table of every entity it references; the game remaps those entities on load
  and the mod rewrites the ids in the JSON (including dictionary keys and group strings such as `district:`).
  A save loaded without the mod skips the block. The mod never adds its own component to a vanilla entity, and
  takes its efficiency factor and district modifiers off before every save, so removing it leaves a clean save.

## How the game works (what we had to learn)
- **Launch flags**, read from `GameManager.ParseOptions` in the decompiled Game.dll: `-developerMode` (Tab opens
  the dev menu, Home the add-object menu), `-uiDeveloperMode` (Cohtml DevTools at `http://localhost:9444`;
  port 9445 is only the fatal-error page), `-startGame=<id>`, `-startEditor`, `-logsEffectiveness=<level>`,
  `-disableCodeModding`, `-disableModding`, `-disablePdxSdk`.
- **Frame order:** `ModificationSystem` runs in `SystemUpdatePhase.MainLoop` every frame, even while paused. It
  runs Modification1..5 and ModificationEnd. Then come PreCulling (`PreRenderSystem`), UIUpdate, Rendering and
  Cleanup. Anything that must be seen by culling or batching has to be set up in ModificationEnd (Gotcha 5).
- **Time:** a game day is 262,144 simulation frames, about 72.8 real minutes at 1x. On the city's calendar one
  game day is one month. Systems with `kUpdatesPerDay` and 16 update groups touch each entity a few times a
  day, not every frame.
- **Stocks versus derived values:** some writes persist (company money in `Resources`, `BuildingCondition`,
  `CrimeProducer.m_Crime`, efficiency factors). Others are recomputed and a write vanishes on the next update
  (`PropertyRenter.m_Rent`, `CompanyStatisticData`, `Tourism`, land value). A lever must write a stock, hold a
  modifier or own a factor.
- **City modifiers** (the `CityModifier` buffer on the city entity) are rebuilt from policies regularly, so a
  held effect must be re-added after each rebuild. Types used, by enum value: Attractiveness 0,
  CrimeAccumulation 1, CriminalMonitorProbability 7, CrimeProbability 23, ImportCost 26, LoanInterest 27,
  ExportCost 29, CityServiceBuildingBaseUpkeepCost 38, TaxHappiness 40.
- **District modifiers** (the `DistrictModifier` buffer on a district) are rebuilt only when that district's
  policies change, with no periodic rebuild. `AreaUtils.ApplyModifier` applies a type only if the buffer is long
  enough, so pad the buffer. Readers exist for CrimeAccumulation, Wellbeing, LowCommercialTax and others;
  ProductConsumption and BuildingUpkeep have no reader in 1.6.2f1 (Gotcha 9).
- **Efficiency:** the `Efficiency` buffer on company and service buildings is a product of factors
  (`BuildingUtils.SetEfficiencyFactor`). Factor `MaterialSupply` (17) has no writer in 1.6.2f1, so the mod owns it
  for inspections. Never write a factor index of 32 or more: jobs index a 32-slot stackalloc.
- **`IPreSerialize`** on a system gives a `PreSerialize(Context)` call before every save. The lever system uses it
  to clear its efficiency factor and district modifiers, then marks itself dirty so the next pass (about every
  256 frames) puts them back.
- **Parameter singletons** (`EconomyParameterData`, `LeisureParametersData`, `PoliceConfigurationData`) are read by
  jobs every update. Writes are global and last for the session, and the game does not save them; restore the
  originals when the lever ends and when the city closes. Curfews raise `m_LeisureRandomFactor` during curfew
  hours and end leisure trips already under way.
- **Companies:** a company goes bankrupt after its worth stays below `m_CompanyBankruptcyLimit` for a quarter day.
  A forced closure adds `MovingAway`, but `CompanyMoveAwaySystem` only processes companies with `ProcessingCompany`
  and a `PropertyRenter` (Gotcha 10). Vanilla company tax is destroyed, not credited to the city, so a mod that
  fines a company must credit the treasury itself.
- **Arrests:** a resident inside a building can be sent to the nearest police station with
  `TravelPurpose.GoingToJail`. For a resident on the move the safe route is to queue the arrest until they stop.
  The mod's incident scanner then files that arrest as a court case the same way it files a vanilla arrest.
- **Trade:** `BudgetSystem.GetTrade(Resource)` and `GetTradeWorth(Resource)` are plain array reads refreshed on the
  main thread from the Trade statistic (+ import, - export, as far as the code shows; not confirmed in game).
- **Renaming:** `NameSystem.SetCustomName` renames a designated building (the White House, courthouse, council).
- **Puppets** (the motorcade, the Secret Service, protest crowds of up to 40) are render-only entities: a prefab's
  archetype minus its AI and navigation components. They are moved by writing `TransformFrame` slots in
  PreCulling along a path from the mod's own A* over the road graph. The slot math is
  `n = (R - u - 32) >> 4`, slot `n & 3`, checked against `ObjectInterpolateSystem.CalculateUpdateFrames`. Moving
  objects off lanes are culled by PreCullingSystem's query over `CullingInfo` + `Moving`, not by the moving
  search tree. Puppets are never written into the save.
- **Colours:** a `CustomMeshColor` buffer overrides a vehicle prefab's colour variations (black limo and SUV).
  Human colours come from `PseudoRandomSeed`; the mod re-rolls the seed until a suit jacket reads dark.
- **Gameface (the UI engine):** every element is a flex box and every text node is its own flex item.
  `var(--x, fallback)` computes to transparent, while a plain `var()` inherits fine. Emoji render as boxes, and
  Libre Baskerville has no arrow glyphs. UI mods are a webpack bundle (`<mod>.mjs`) that registers through the
  `ModRegistrar` default export; C# `ValueBinding`/`TriggerBinding` pair with `bindValue`/`trigger` from `cs2/api`.

## Build steps
1. Install the toolchain (Gotcha 1), then smoke-test it. Run
   `dotnet new csiimod -n Hello -I -In` and `dotnet build -c Release`: you should see ILPP, Burst for
   win/mac/linux, and a deploy to `...\Cities Skylines II\Mods\Hello`. Then run
   `create-csii-ui-mod --name=hello-ui --author=<you>` and `npm run build`, which writes `hello-ui.mjs` to `Mods\`.
   Delete both smoke deploys afterwards.
2. Structure the project as `src/` (the mod csproj from the template; the Core sources are included), `ui/` (the UI
   template) and `tests/Sim` (a net8.0 console app that compiles the same `src/Core` files against a stub `ICity`).
   Content (bills, case archetypes, phrases, powers, factions, ladder) lives in `data/*.json`, embedded as
   resources. Large or rule-heavy data files are generated by small Python scripts (`tools/make_powers.py`,
   `tools/make_ladder.py`), not typed by hand.
3. UI: `npm run build` in `ui/`. The C# build copies `ui/build` into the deploy folder.
4. Compile check that never touches the game folder:
   `dotnet build src/OvalOffice.csproj -c Release -t:Compile -p:IntermediateOutputPath=obj/check/`.
5. Deploy, only with the game closed (`tasklist /FI "IMAGENAME eq Cities2.exe"` shows nothing):
   `dotnet build src/OvalOffice.csproj -c Release --no-incremental`. It writes `Mods\OvalOffice` (DLL, the Burst
   `_win_x86_64.dll`/`.so`/`.bundle`, `.mjs`, CSS, fonts, images, sounds). Check that the deployed DLL contains its
   embedded data, for example by searching it for a string from `data/bills.json`.
6. Offline tests: `dotnet run -c Release --project tests/Sim -- test` (unit tests), `-- 30` (a 30-day integration run
   that fails on any swallowed exception and prints save size per state section), `-- ladder` (pacing bots), and
   `npm test` in `ui/` (pure helpers and a Gameface lint that flags `var()` fallbacks and similar pitfalls).
7. UI previews without the game: the simulator dumps every view model (`dotnet run -- dump ui/preview/fixtures 8`). A
   second webpack config aliases `cs2/api`, `cs2/modding` and `cs2/ui` to mocks, and headless Edge with a
   throwaway profile screenshots each page (`msedge --headless=new --screenshot --virtual-time-budget=6000`), so
   no window opens on the user's desktop.
8. Publishing: `ModPublisher.exe` from the toolchain reads `src/Properties/PublishConfiguration.xml` and signs in
   with the Paradox account the game is logged into. The project's `release.ps1` does steps 3, 6 and 5, then
   `PublishNewMod` the first time (or a new version afterwards). The listing's access level was set so only the
   author sees it; the ModId comes back in the log and goes into `<ModId Value=...>`. See Gotchas 12 and 13.

## Verification
- **v1, in the real game, driven by the agent** (13:30-14:45 on 2026-10-18, saves backed up first). A dev bridge
  is a folder the mod polls: the agent writes JSON lines to `ModsData/OvalOffice/bridge/cmd.jsonl` and reads
  `out.jsonl` and `status.json`. Commands: `act`, `page`, `speed`, and `eval` with `status`, `follow`, `desk`,
  `toast`, `load`, `save`, `app`, `puppets` and `redress`. The bridge acts on whatever lands in that folder, so it
  is a development aid: keep it out of public builds. Seen in game, with screenshots:
  - the oath; designating a White House, council and courthouse; a cabinet hire confirmed by a council vote (7-2);
  - executive orders changing the city (commercial tax 10 -> 7, garbage budget 100 -> 120 in the dashboard diff);
  - real arrests filed as court cases, and news written from real incidents;
  - save and load ("Saved presidency (139 KB, 94 entity references)"), which restored bills, cabinet, orders and
    held effects;
  - the desk UI over the city with every app opened; motorcade cars rendering and driving the roads.
  Test saves were written only under the name `OvalOffice-lab`; the player's own city save was never written.
- After that test the human took over in-game testing. The v1 fixes (fully dressed puppets, dark suits, curb
  parking, Gameface fixes) were deployed and **not** seen in game by the agent.
- **v2, offline only:** 113 simulator unit tests, the 30-day run, 12 ladder pacing runs (four play styles on three
  stub city sizes: tier 5 at 5-7.7 game days, tier 10 at 42-66 days active and 168-180 idle), 27 UI tests, headless
  screenshots of every page, and a 0-warning compile against the game's assemblies. Two review agents read the
  whole branch and a third read the fixes. A 120-day simulated presidency saves at 2.1 MB.
- v2 was deployed to the local `Mods` folder with the game closed and published to Paradox Mods (author-only).
  **Not verified in game:** every v2 lever (modifiers held through rebuilds, district modifiers, LoanInterest,
  ImportCost/ExportCost, the trade read, curfews, inspections), the v2 portal layout in Gameface, the migration
  of a v1 presidency, and performance in a large city.

## Gotchas
1. **Symptom.** Options > Modding > Install fails at "Unity Mod Project"; `Logs\Modding.log` shows
   `Unity.exe -projectPath ... -quit` exiting with code 1. **Cause:** Unity 2022.3.62f2 was installed but not yet
   licensed. **Fix:** sign in to Unity Hub and activate a Personal license first, then press Install again (the
   retry built `UnityModsProject`).
2. **Symptom.** `um scan` reports Unity Mono and suggests BepInEx + HarmonyX. **Cause:** that was the CS2 route
   before official mod support (Paradox Mods and code mods arrived with patch 1.1.0f1 in March 2024), and `um scan`
   has no CS2 entry yet. **Fix:** use the official toolchain; the `Cities2_Data\Content\Game\.ModdingToolchain`
   folder is the sign.
3. **Symptom.** You need the development player for breakpoints, but the Windows editor installer for 2022.3.71f1 is
   3.66 GB and the Windows "Mono Support" target installer returns 404. **Cause:** Unity only ships that target as
   part of an editor install. **Fix:** download the macOS editor's
   `download_unity/c9bf13b0b844/MacEditorTargetInstaller/UnitySetup-Windows-Mono-Support-for-Editor-2022.3.71f1.pkg`
   (182 MB) from `download.unity3d.com` and open it with 7-Zip: pkg > `TargetSupport.pkg.tmp\Payload` >
   `Payload~` (cpio) > `Variations\win64_player_development_mono\UnityPlayer.dll`. Its FileVersion
   (2022.3.71.13221651) matches the shipped player, and its Unity signature is valid. Swapping it in changes a
   game file, so back up the original first (Steam "Verify integrity" also restores it).
4. **Symptom.** Launching `Cities2.exe` directly fails with "A platform service integration failed to
   initialize"; `-startGame=<id>` and `-continuelastsave` fall back to the main menu ("Asset doesn't exist").
   **Cause:** without Steam's launch environment, the platform layer has no app id. The `.cid` next to a save is
   the package-asset id, not the `SaveGameMetadata` id. **Fix:** set `SteamAppId`, `SteamGameId` and
   `SteamOverlayGameId` to 949230 in the environment. Steam still has to be running and signed in to the account
   that owns the game (`SteamAPI_Init` checks the licence), so this only stands in for Steam's launch environment.
   Load saves through the dev bridge, which calls
   `GameManager.instance.Load(GameMode.Game, Purpose.LoadGame, <SaveGameMetadata>)`.
5. **Symptom.** Puppet entities created by the mod never render; `CullingInfo` stays at mask 0 / radius 0.
   **Cause:** culling (re)initialises only entities that carry `Updated`/`BatchesUpdated` when PreCullingSystem
   runs, and the end-of-frame cleanup strips both. Flags added from a UIUpdate system are gone before the next
   PreCulling. **Fix:** a `PuppetFlagSystem` scheduled right after `MeshGroupSystem` in ModificationEnd applies
   every pending flag, outfit, paint and visibility change.
6. **Symptom.** Secret Service agents in suits render as a floating head over trousers. **Cause:**
   `RequiredBatchesSystem` (ModificationEnd) creates batch groups only for `Updated`/`BatchesUpdated` entities,
   and only for garments someone wears. Nobody in town wore warm-weather suits while residents wore the cold set.
   `MeshGroupSystem` picks outfits from flags on the `Human` component, which a puppet cannot keep:
   `HumanMoveSystem` queries Human + UpdateFrame + TransformFrame and reads HumanNavigation by index. **Fix:** the
   puppet writes its own `MeshGroup` (one sub-mesh group per matching set, mesh and colour offsets, +8 colours
   for overlays) and copies the warm/cold choice from a real resident.
7. **Symptom.** A plain `dotnet build` while the game was running wiped the live mod's UI files.
   `-p:DeployDir=...` is ignored. A later build deployed a DLL that logged "Content: 0 bills". **Cause:** the
   template's deploy target deletes and recreates `Mods\<Mod>` and sets the deploy dir inside a target.
   `-t:Compile` alone writes a DLL without embedded resources into `obj`, and the next incremental build ships
   it. **Fix:** compile-check into `obj/check/` (Build step 4); deploy only with `--no-incremental` and the game
   closed.
8. **Symptom.** Gameface UI: buttons and selected tabs have no colour; "Appointed {when} · {n} actions" stacks one
   fragment per line; arrows and emoji show as boxes; a bare link after a button collapses. **Cause:** Gameface
   ignores `var()` fallbacks, makes every text node a flex item, and the font lacks those glyphs. **Fix:** plain
   `var(--x)` only; a custom `ui/src/jsx-runtime.ts`, aliased in webpack for `react/jsx-runtime`, joins adjacent
   string children; use « » instead of arrows, strip emoji from data, and wrap such links in a `span`.
9. **Symptom.** A district power could push a district modifier negative after the player changed that district's
   policies. **Cause:** the game rebuilds the `DistrictModifier` buffer on a policy change, and the mod then
   subtracted its old delta from the fresh buffer. **Fix:** remember the delta the mod last saw per
   (district, type) and skip the subtraction when the buffer changed underneath. When two postures hit one
   district, apply the strongest, not the sum.
10. **Symptom.** A business closed by decree stayed "closing" forever. **Cause:** `CompanyMoveAwaySystem`'s queries
    require `ProcessingCompany` and `PropertyRenter`; `MovingAway` on any other company is never processed.
    **Fix:** refuse the closure unless the company has both.
11. **Symptom.** Saves grew to 4.9 MB after 120 simulated days. **Cause:** closed court cases kept full transcripts
    and documents. **Fix:** after three days a closed case keeps only its record and judgment; closed cases are
    dropped after 20 days unless the player ruled. The same save is 2.1 MB. Cap every log list, and store
    absolute dates in logs: relative text like "today at 3 PM" goes stale once saved.
12. **Symptom.** After the first publish, git showed `PublishConfiguration.xml` fully rewritten. **Cause:**
    ModPublisher writes the new ModId back and re-serialises the file (tabs to spaces, CRLF, the BOM). **Fix:**
    restore the committed file and change only `<ModId Value="..."/>`, keeping the BOM.
13. **Symptom.** Two copies of the mod would load. **Cause:** the local deploy in `Mods\OvalOffice` and a
    Paradox Mods subscription both load. **Fix:** delete `Mods\OvalOffice` before subscribing to the published
    copy (in Skyve or the launcher). Until then the local deploy is what the game loads.
14. **Symptom.** Pacing bots that never campaigned stalled at tiers 7-8 after the out-of-office XP fix. **Cause:**
    they lost re-election at 40-50% approval (the challenger's strength term), and XP correctly stopped out of
    office. **Fix:** measure pacing with elections off; tell the player that re-election needs a campaign.
15. **Symptom.** A turn that was writing a large generated data file (the ladder table) was stopped by the agent's
    safety classifier with nothing saved. **Fix:** generate such files from a short script (`make_ladder.py`)
    instead of writing them out in one long response. The next session finished the ladder that way.
16. **Symptom.** Long bash heredocs with apostrophes ended in "unexpected EOF" on Windows Git Bash. **Fix:**
    write patch scripts to a scratch file and run them; each patch asserts its target text exists before
    replacing it.

## Assets
- Desk photographs and 79 evidence photographs were generated with fal; three that showed people were
  regenerated faceless. The exact fal endpoint ids were not recorded in the transcripts read for this note.
- Some sound effects came from fal; the other desk sounds were synthesised by a Python script
  (`tools/make_sounds.py`).
- Fonts: Libre Baskerville, Courier Prime, Caveat and Oswald (SIL Open Font License). All names, parties,
  states, businesses and organisations are fictional.
- An existing Paradox Mods mod with a similar theme was used only as a reference for breadth. Nothing was copied.

## Cost and time
One long day (2026-10-18) over four agent sessions:
- toolchain setup (04:27-04:45);
- v1 build and in-game test (05:05-14:49);
- v2 phases 0-5;
- v2 phases 6-7, three review rounds, deploy and publish (done at 21:40).

Two content subagents wrote 53 of the 61 court case types in parallel branches, which were then merged. The
build PC was limited to one heavy build and at most two subagents at a time.

## Open questions
- Does every v2 lever hold in a real city? Watch the central rate in the budget panel's loan interest, import
  costs under a trade pact, and a casino's attractiveness and district crime. The human is testing.
- Confirm the sign convention of the Trade statistic in game.
- Performance of the hourly and daily passes in a 100k-resident city. The work is time-sliced and designed for
  under 1.5 ms a frame, but this was never measured in game.
- The v1 puppet fixes (fully dressed agents, dark suits, curb parking) still need an in-game look.
