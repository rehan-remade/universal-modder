---
kind: game
title: "Native-looking in-game Mods settings tab (and performance knobs that actually moved VR frames)"
game: "CONVRGENCE"
games_also: []
game_version: "1.1.0, Steam BuildID 26164481"
platform: windows
engine: unity-il2cpp
route: loader-api
tools: ["MelonLoader 0.7.3", "AssetRipper GUI (headless web)", "UnityPy", "ilspycmd (ILSpy CLI)", "WPR/WPA (Windows Performance Recorder/Analyzer)", "HarmonyX"]
anti_cheat: "none (single-player VR survival shooter; keep clear of any online flow)"
status: working
agents: ["OpenCode (GLM)"]
humans: ["Arttu (full VR verification, patience through ~35 game restarts)"]
date: 2026-10-31
links: ["local project: D:/UniversalModder/Projects/convrgence-lab-v2"]
tags: ["vr", "settings-ui", "pause-menu", "in-game-menu", "melodloader-ui-clone", "volumetric-fog", "aura2", "force-close", "field-write-vs-method-call"]
---

# Native-looking in-game Mods settings tab (and performance knobs that actually moved VR frames)

> Two deliverables, both working in the real game (verified by the human in headset, sound-logged and
> screenshot-checked through MelonLoader logs): (1) a performance Mod (`ConvrgencePerfV2`) that raises the
> spawn-shop floor from 64 fps to ~70 and the shop-keeper view to 80-84 fps at 144 Hz target WITHOUT
> touching any visual setting, and (2) a separate Mod (`ModsMenu`) that injects a fifth "MODS" tab into the
> game's own pause-menu settings window, rendered exclusively from clones of the game's own UI objects,
> with a mod-list page wired to the mod loader and a keyboard/controller-safe force-close when the pause
> context ends. The in-game tab survived every in-game graphics preset switch and both scenes tested.

## Setup
Windows 11, Steam game (AppID 2609610), Quest 3 through SteamVR/Virtual Desktop. Unity 2019.4.2f1 with
IL2CPP; MelonLoader 0.7.3 already installed by an earlier session (see the sibling note
`proof-melonloader-plugin-loads-on-convrgence.md`). A working MelonMod needs to reference:
`MelonLoader\net6\MelonLoader.dll`, `Il2CppInterop.Runtime.dll`, `0Harmony.dll` (all net6), the game's
dumped stubs at `MelonLoader\Il2CppAssemblies\*.dll` (UnityEngine.X modules AND `Il2Cpp*-` prefixed
classes live here; BNG/InGameMenu root `Il2Cpp` namespace is inside `Assembly-CSharp.dll` - there is no
separate Il2CppBNG.dll), plus any interop types you touch (ParticleSystemModule, AudioModule, ...)
and `Il2CppAura2_Core.dll` for Aura 2 volumetrics. Save data lives in
`%UserProfile%AppData/LocalLow/Monkey-With-a-Bomb/CONVRGENCE` (a JSON progress file + backup) -
back that up before any Mod run.

## Route and why
loader-api (MelonMod + HarmonyX into interop wrappers) because the game has no native modding hooks and
mono assembly is absent. Two non-routes worth recording: `UnityEngine.XR`/`XRSettings.renderScale` is a
dead end (the game runs on OpenVR/SteamVR plugin; XRSettings reported `isDeviceActive=false` and never
moved scale), and Unity AssetRipper-based *asset* swaps were not needed since the UI could be cloned
from live scene objects. Decompile-recompile of the menus would also have worked but replaces behavior;
cloning preserved it.

## How the game works (what we had to learn)
- **Pause/system object model.** The pause window is a world space UGUI canvas named `PauseMenu`
  (Resume / ExitRaid / Controls / Settings buttons), with page canvases `SettingsMenu` (the Game tab),
  `ControlsMenu`, `CosmeticsMenu`, each a `Scroll View > Viewport > Content` structure. Their scene
  parent name is NOT stable: `Menu` in intro/menu scenes, `PlayerAdvanced Variant/Inventory` in
  gameplay scenes - anchor on object names, never on parent names. A separate central controller
  `Il2CppBNG.InGameMenu` (attached next to the PauseMenu canvas) holds a serialized bool
  `GameIsPaused` - the authoritative state; also ~200 fields wiring sliders/buttons (loaded via
  reflection in its native code). The pause menu reads `InputBridge.Instance` (BNG) - specifically its
  `StartButton`/`BackButton` and an instance field `MenuButtonPressed - to decide whether to open/close.
- **Where the UI's real pixel values live.** The run's `LogPrefix`-free facts worth keeping: the pause
  menu's intent is to hide scroll overflow withrush-hides. From AssetRipper YAML of the serialized buttons,
  row geometry: `Difficulty` row = 465 x 48 units in Content (content 1600 units tall); row
  templateusdPosition `(5.1, 255.6)`; and the exact tab palette: selected pill border rgba(118,94,75) =
  #765e4b; unselected #2f2f2f. A "Bar Underlay" element copies the translated scrollbar column.
- **A "Localization" component on each labeled row** holds RUS/ENG GameObject refs; our clones strip
  it and hide the Rus label - otherwise both stacked texts glow double-bright.
- **Performance truths (from two WPR traces + SteamVR vrcompositor totals):** CPU-paced (~9.3-9.9 ms
  vs a 6.94 ms budget at 144 Hz); inside UnityPlayer, NOT game scripts (GameAssembly total < 1% of
  samples). What measurably worked: Aura2 volumetric resolution 75% (state: `playerBase.AuraCamera ->
  frustumSettings.qualitySettings.frustumGridResolution`), volumetric far clip 30 m (the game sets 128 m
  at world scale) - these two are screenshot-invisible indoors.

## Build steps
1. Run `melondloader` scanner first: set every page object Inject on 'MODS' clone: find the three
   top bars by transform name (`TopBarGame|TopBarControls|TopBarCosmetics` regardless of scene parent),
   clone whole `Cosmetics` child button object as the pill (whole-object clone, strip interactive comps),
   relabel 'MODS', shift `Back` 47.5 units right at 0.76 child scale, then rebuild even-spaced pill row.
2. Page: clone `SettingsMenu` canvas (brings OVRRaycaster/camera config), DESTROY its copied
   `Scroll View` first, then clone the SOURCE `Scroll View` in our name (viewport/mask/anchoring
   exact), clear `Viewport/Content` with `DestroyImmediate` (leave Back row), add rows cloned from
   the game's own row template anchored with `anchoredPosition` stepping.
3. Show/Hide: hide all page canvases + `ControlScheme` + `InventoryScheme` (the game's own tab
   wiring toggles these side panels), show our page, restore on exit; force close at 0.5 s cadence.
4. Every DECOMPILE or check is done by *reading game UI state*; no textual guesses - see MODLOG for
   a 15-line summary of every stage logged at each run.

## Verification
Human verified: mods list identical to the native menu flow in three launch checks, pill behavior,
force close works through controller menu button press AND Resume, and the pause window itself stays
open through the background (only switch-off points left). Performance: A/B runs with synchronized
SteamVR compositor totals (GUI + MelonLoader timed patches). Not solely verified: keyboard-only
mouse system (no keybinds tested), Ultra-quality GPU stat under WPR was never re-examined after the
Aura/knob fixes.

## Gotchas
1. **Unity called straight from native code.** Harmony patches on interop *wrapper* methods do not see
   native-to-native calls (game C++ calling `BNG.InGameMenu.Menu` bypasses the C# wrapper). **Fix:**
   write to serialized fields (field writes share memory with native reads). Zeroing the raw menu-button
   fields while our page is open killed the entire controller-button path; method call patches are just
   defensive.
2. **Any `Destroy` and later re-Add on SAME object must be `DestroyImmediate`.** `Destroy` defers to
   end of frame: adding a fresh `Button` on a frame where the old was still scheduled to die threw
   NullReference in `AddComponent<Button>`. The `strip`/re-add stages must pair `DestroyImmediate`.
3. **New clones of prefab instances in the scene must restore relaxation.** Scene files reference prefab
   internals: the child rows visible in VR could render despite a fully "cleared" cloned Content in the
   serialized uncloned originals; the fix was cloning the *whole Scroll View object* from the instanced
   page then clearing via `Viewport/Content` chain (never search by row name - the row node layout has
   ancestor-relative sweepers).
4. **Page canvases spawn with parent objects from different scene roots per scene.** Anchor ONLY on
   object names (`TopBar *`, `SettingsMenu`, ...). At build time the cloned canvas is deactivated
   BEFORE the child Scroll View clone pages are prepared, otherwise a ScanId-to-Content 1:1 mismatch
   makes the mods rows appear LEFT-of-screen (anchored position mapping is scene-local).
5. **Localization**: every settings row has RUS + ENG variants rendered one on top of the other until
   the game's pair-state hides one; our clones hide RUS explicitly, else double-bright text.
6. **Native object tree references need persistent pointer stores** (Dictionary keyed by
   `transform.Pointer.ToInt64()`), not `.Equals` of interop objects - interop wrappers regenerate.
7. **Set the anchored pill Position Colors from the game's own state**: 0.0849 (base) vs accent
   (0.898, 0.725, 0.588, a=0.06) matches hover overlay vs correct state pair (measured from game files
   in our session; from screenshots: #2f2f2f / #765e4b).
8. **AssetRipper headless web API for static UI state:** load the game folder through `POST /LoadFolder`,
   get YAML / details via `/Assets/Yaml/:Path` (JSON path %@). Do NOT press Export (primary content
   export fills disk with GLB at gigabyte scale; use per-asset YAML).

## Final performance results (2026-11-02 close-out)
Measured with in-mod telemetry (below) + SteamVR compositor stats, Quest 3 / Virtual Desktop / 144 Hz:

- **Banked gains (real, one-time):** heavy-scene fog/particle cuts gave floor 64→70 and
  shop-keeper 72–76→80–84 fps. These come from Aura 2 fog quality/distance and particle pool caps
  in scenes where those systems actually cost.
- **The shop's worst spot is draw-submission-bound.** At the user's fixed worst-looking spot,
  the FULL aggressive profile (fog quality 30 %, fog far-clip **0.3 m**, particles 20 %, physics
  20 Hz, audio propagation off, reproj on) scored **identical to stock** (68.7 vs 68.8 fps p50).
  Volumetric fog, particles and physics are NOT the cost there; nothing runtime-tunable moved it.
  The only known fix (SPI stereo, halved draw submission) breaks this game's shaders (both eyes
  dark). Targeted spot-fps differences (80 at shop-keeper vs 68 elsewhere) are view-dependent
  draw cost, not tunable state.
- **Stock fog already runs temporal reprojection** (enabled, factor 0.95) — a "fog reproj" lever
  must cache/restore that, not assume off.
- Practical ceiling for a zero-visual-loss runtime mod on this title: ~10 % in heavy scenes,
  ~0 % in draw-bound spots. 144 Hz lock is not reachable without shader-level work.

## Reusable technique: epoch-tagged activity telemetry
The thing that finally made A/B data trustworthy (after a session where stock ran unnoticed for
200 s because the mod had loaded disabled): the mod appends one CSV
(`UserData/<Mod>/activity.csv`), schema
`utc, elapsed_s, epoch, scene, event, setting, detail, fps_before_avg, fps_before_p50, fps_avg,
p50_ms, p95_ms, max_ms, n`. Events: `session` (settings snapshot), `scene`, `change` (diff-based —
one row per changed field, a shared epoch bumped per batch, `fps_before` = mean of clean windows
in the same scene over the last 45 s), `window` (every 10 s, epoch-tagged), `quit`. Change
detection is a config-snapshot diff hooked into Save() + config hot-reload, so menu drags AND
hand-edited settings.json land in the same log. A ~60-line analyzer replays the timeline and
prints per-scene per-epoch fps with deltas. Rules learned:
- **Tag every measurement with the settings epoch**, else on/off comparisons ride a moving baseline.
- **Require a minimum sample count per window** (n >= 100) — loading frames poison short windows.
- **Master-off must mean truly stock everywhere**, including scene-settle apply paths (ours
  silently applied physics/CCD on scene entry while disabled — fixed in v2.5.0).

## Assets
No external art needed - the whole theme is cloned from the game's own widgets. Screenshots of states:
`Projects/convrgence-lab-v2/Evidence/*.png`.

## Cost and time
~8 wall-clock hours for performance reader + in-game tab, ~35 game restarts total. If we rerun:
AssetRipper-first + UnityExplorer live inspection would halve it (~15 restarts, ~4 h).

## Open questions
- RESOLVED M2: the in-page Perf controls route is abandoned (UI cloning of OVRRaycaster world-space
  canvases never stabilized; the MODS page stays as a mod list only, v0.6.4, `ModsMenu.dll` since
  removed from the game). M2 shipped instead as an **F8 IMGUI settings menu** inside PerfV2 v2.4.0 —
  master toggle, CCD, physics 20–90 Hz, fog quality/distance sliders, particle density, audio
  propagation off, Aura temporal reprojection, stereo readout, FPS meter. All live-applied, persisting
  to `UserData/ConvrgencePerfV2/settings.json`.
- RESOLVED stereo mode: `XRSettings.stereoRenderingMode` is read-only at runtime (CS0200), and a
  UnityPy typetree patch of `m_StereoRenderingPath` 0→2 (SinglePassInstanced) in `globalgamemanagers`
  rendered BOTH eyes dark — the game's shader set (Aura 2, Beautify, weapon shaders) lacks instancing
  variants. Reverted; multi-pass is required for this title.
- The 0.5 s force-close + per-frame menu-field zeroing has a theoretical one-frame race where a LEFT
  menu press can still flip the pause state; current builds tolerate it via the `ExitModspageLite`
  safe exit, but a native detour (not wrapper Harmony) would remove the race entirely.
- A couple of one-frame lag on the bar reservation: the pill can get click-against-hover in first
  0.2 s if pointer was already hovering before the page built (visual only).
- Untested/unfinished levers (project closed 2026-11-02 before raid A/B): audio propagation off in
  raids, Aura reproj delta (stock already on at 0.95 — lever likely useless), frustum-margin
  component throttler (designed, not built). Final verdict: shop worst-spot is draw-bound; heavy
  scenes hold the only real wins and those are banked in the default profile.
