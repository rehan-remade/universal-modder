---
kind: game
title: "Native-looking in-game Mods settings tab (and which performance knobs moved VR frames)"
game: "CONVRGENCE"
games_also: []
game_version: "1.1.0, Steam BuildID 26164481"
platform: windows
engine: unity-il2cpp
route: loader-api
tools: ["MelonLoader 0.7.3", "AssetRipper GUI (headless web)", "UnityPy", "ilspycmd (ILSpy CLI)", "WPR/WPA (Windows Performance Recorder/Analyzer)", "HarmonyX"]
anti_cheat: "none found (single-player VR extraction shooter, Steam starts CONVRGENCE.exe directly); it has Steam leaderboards, so keep modded runs off them"
status: working
agents: ["OpenCode (GLM)"]
humans: ["Arttu (full VR verification, patience through ~35 game restarts)"]
date: 2026-10-31
links: ["https://github.com/LavaGang/MelonLoader", "https://github.com/AssetRipper/AssetRipper", "https://github.com/K0lb3/UnityPy", "https://github.com/BepInEx/Il2CppInterop"]
tags: ["vr", "settings-ui", "pause-menu", "in-game-menu", "melonloader-ui-clone", "volumetric-fog", "aura2", "force-close", "field-write-vs-method-call"]
---

# Native-looking in-game Mods settings tab (and which performance knobs moved VR frames)

> Two deliverables, both run in the real game (checked by the human in the headset, and through MelonLoader
> logs and screenshots): (1) a performance Mod (`ConvrgencePerfV2`) that lowers Aura 2 volumetric fog resolution
> and distance and caps particle pools, for a reported gain of about 10 % in the spawn shop (floor 64 -> ~70 fps,
> shop-keeper view 72-76 -> 80-84 fps, at a 144 Hz target) with no difference in indoor screenshots; nothing moved
> the shop's worst spot (see Final performance results for how far to trust those numbers); and (2) a separate Mod
> (`ModsMenu`) that injects a fifth "MODS" tab into the game's own pause-menu settings window, rendered
> exclusively from clones of the game's own UI objects, with a read-only mod-list page wired to the mod loader
> and a controller-safe force-close when the pause context ends. The in-game tab survived every in-game graphics
> preset switch and both scenes tested. Interactive controls on the cloned page never stabilized, so the settings
> moved to an F8 IMGUI menu, and `ModsMenu.dll` has since been removed from the game (Open questions). The code
> of both mods is private.

## Setup
Windows 11, Steam game (AppID 2609610), Quest 3 through SteamVR/Virtual Desktop. Unity 2019.4.2f1 with
IL2CPP; MelonLoader 0.7.3 already installed by an earlier session. A working MelonMod needs to reference:
`MelonLoader\net6\MelonLoader.dll`, `Il2CppInterop.Runtime.dll`, `0Harmony.dll` (all net6), the game's
dumped stubs at `MelonLoader\Il2CppAssemblies\*.dll` (UnityEngine.X modules AND `Il2Cpp*-` prefixed
classes live here; BNG/InGameMenu root `Il2Cpp` namespace is inside `Assembly-CSharp.dll` - there is no
separate Il2CppBNG.dll), plus any interop types you touch (ParticleSystemModule, AudioModule, ...)
and `Il2CppAura2_Core.dll` for Aura 2 volumetrics. Save data lives in
`%USERPROFILE%\AppData\LocalLow\Monkey-With-a-Bomb\CONVRGENCE` (a JSON progress file + backup) -
back that up before any Mod run.

**Leaderboards.** The game is single-player (Steam page), and these mods touch nothing online. It does have Steam
leaderboards ("Compete against other players and win unique rewards"), and the perf mod's menu can change the
physics rate and particle load. What feeds those boards wasn't looked at, so keep modded runs off them: Steam in
offline mode, or the mods out for any run that counts.

## Route and why
loader-api (MelonMod + HarmonyX into interop wrappers) because the game has no native modding hooks and
mono assembly is absent. Two non-routes worth recording: `UnityEngine.XR`/`XRSettings.renderScale` is a
dead end (the game runs on OpenVR/SteamVR plugin; XRSettings reported `isDeviceActive=false` and never
moved scale), and Unity AssetRipper-based *asset* swaps were not needed since the UI could be cloned
from live scene objects. Replacing the menus outright would replace their behavior; cloning preserved it.
The general recipe for a cloned settings tab is in
`techniques/an-in-game-settings-menu-in-an-il2cpp-unity-game-clone-the-g.md`, from a game where the cloned
buttons did stay clickable. Here the world-space `OVRRaycaster` pages didn't, so read that note with this one.

## How the game works (what we had to learn)
- **Pause/system object model.** The pause window is a world space UGUI canvas named `PauseMenu`
  (Resume / ExitRaid / Controls / Settings buttons), with page canvases `SettingsMenu` (the Game tab),
  `ControlsMenu`, `CosmeticsMenu`, each a `Scroll View > Viewport > Content` structure. Their scene
  parent name is NOT stable: `Menu` in intro/menu scenes, `PlayerAdvanced Variant/Inventory` in
  gameplay scenes - anchor on object names, never on parent names. A separate central controller
  `Il2CppBNG.InGameMenu` (attached next to the PauseMenu canvas; `BNG` looks like Bearded Ninja Games' VR
  Interaction Framework, an Asset Store package) holds a serialized bool
  `GameIsPaused` - the authoritative state; also ~200 fields wiring sliders/buttons (loaded via
  reflection in its native code). The pause menu reads `InputBridge.Instance` (BNG) - specifically its
  `StartButton`/`BackButton` and an instance field `MenuButtonPressed` - to decide whether to open/close.
- **Where the UI's real pixel values live.** From AssetRipper YAML of the serialized buttons, row geometry:
  `Difficulty` row = 465 x 48 units in Content (content 1600 units tall); row template position
  `(5.1, 255.6)`; and the exact tab palette: selected pill border rgba(118,94,75) = #765e4b; unselected
  #2f2f2f.
- **A "Localization" component on each labeled row** holds RUS/ENG GameObject refs; our clones strip
  it and hide the Rus label - otherwise both stacked texts glow double-bright.
- **Performance truths (from two WPR traces + SteamVR vrcompositor totals):** CPU-paced (~9.3-9.9 ms
  vs a 6.94 ms budget at 144 Hz); inside UnityPlayer, NOT game scripts (GameAssembly total < 1% of
  samples). What measurably worked: Aura2 volumetric resolution 75% (state: `playerBase.AuraCamera ->
  frustumSettings.qualitySettings.frustumGridResolution`), volumetric far clip 30 m (the game sets 128 m
  at world scale) - these two are screenshot-invisible indoors. Only indoor screenshots were compared, and
  how far the numbers carry is under Final performance results.

## Build steps
1. Inject the 'MODS' clone: find the three top bars by transform name
   (`TopBarGame|TopBarControls|TopBarCosmetics` regardless of scene parent), clone whole `Cosmetics` child
   button object as the pill (whole-object clone, strip interactive comps), relabel 'MODS', shift `Back` 47.5
   units right at 0.76 child scale, then rebuild even-spaced pill row.
2. Page: clone `SettingsMenu` canvas (brings OVRRaycaster/camera config), DESTROY its copied
   `Scroll View` first, then clone the SOURCE `Scroll View` in our name (viewport/mask/anchoring
   exact), clear `Viewport/Content` with `DestroyImmediate` (leave Back row), add rows cloned from
   the game's own row template anchored with `anchoredPosition` stepping.
3. Show/Hide: hide all page canvases + `ControlScheme` + `InventoryScheme` (the game's own tab
   wiring toggles these side panels), show our page, restore on exit; force close at 0.5 s cadence.
4. Every check is done by *reading game UI state* and logging it at each run; no textual guesses. The
   per-stage log is in the author's private MODLOG.

## Verification
Human verified: mods list identical to the native menu flow in three launch checks, pill behavior,
force close works through controller menu button press AND Resume, and the pause window itself stays
open through the background. Performance: A/B runs with synchronized SteamVR compositor totals (GUI +
MelonLoader timed patches), then the epoch-tagged telemetry below.

Not verified: keyboard and mouse (no keybinds tested); the Ultra-quality GPU stat under WPR was never
re-examined after the Aura/knob fixes; any A/B in a raid (Open questions); and whether the shop gains hold up in a
fixed-spot, epoch-tagged A/B (Final performance results).

## Gotchas
1. **Harmony patches on `BNG.InGameMenu.Menu` didn't stop the controller's menu button.** **Cause:** not pinned
   down. It isn't that patches only see calls from managed code: Il2CppInterop's Harmony support detours the
   method's native code (`Il2CppDetourMethodPatcher`), MelonLoader 0.7.3 turns it on, and the BRUTALISTICK VR mod's
   patches on `Button.OnPointerClick` and `MusicManager.StartMusic` fire on calls from native code. An inlined
   call, or the game acting on the fields without calling that method, would look like this. **Fix:** write to
   serialized fields (field writes share memory with native reads). Zeroing the raw menu-button fields while our
   page is open killed the entire controller-button path; method call patches are just defensive.
2. **Any `Destroy` and later re-Add on SAME object must be `DestroyImmediate`.** `Destroy` defers to
   end of frame: adding a fresh `Button` on a frame where the old was still scheduled to die threw
   NullReference in `AddComponent<Button>`. The `strip`/re-add stages must pair `DestroyImmediate`.
3. **Stock rows still show after the cloned page's Content is cleared.** **Cause:** scene files reference prefab
   internals, and the rows visible in VR were the uncloned originals. **Fix:** clone the *whole Scroll View
   object* from the instanced page, then clear via the `Viewport/Content` chain (never search by row name).
4. **Page canvases spawn with parent objects from different scene roots per scene.** Anchor ONLY on
   object names (`TopBar *`, `SettingsMenu`, ...). At build time deactivate the cloned canvas BEFORE the
   child Scroll View clone pages are prepared, otherwise the mods rows appear LEFT-of-screen (anchored
   position mapping is scene-local).
5. **Localization**: every settings row has RUS + ENG variants rendered one on top of the other until
   the game's pair-state hides one; our clones hide RUS explicitly, else double-bright text.
6. **Native object tree references need persistent pointer stores** (Dictionary keyed by
   `transform.Pointer.ToInt64()`), not `.Equals` of interop objects - interop wrappers regenerate.
7. **Set the pill colors from the game's own state**: 0.0849 (base) vs accent (0.898, 0.725, 0.588, a=0.06)
   match the game's hover overlay and selected state (measured from game files in our session; from
   screenshots: #2f2f2f / #765e4b).
8. **AssetRipper headless web API for static UI state:** load the game folder through `POST /LoadFolder`
   (form field `Path`), get YAML via `GET /Assets/Yaml?Path=<the asset's JSON path>`. Do NOT press Export (primary
   content export fills disk with GLB at gigabyte scale; use per-asset YAML). What you read stays on your machine.

## Final performance results (2026-11-02 close-out)
Measured with in-mod telemetry (below) + SteamVR compositor stats, Quest 3 / Virtual Desktop / 144 Hz:

- **Banked gains (one-time, not re-measured at a fixed spot):** heavy-scene fog/particle cuts gave floor 64→70
  and shop-keeper 72–76→80–84 fps. These come from Aura 2 fog quality/distance and particle pool caps
  in scenes where those systems actually cost. Treat them as indicative: the fixed-spot A/B below shows no gain,
  the view alone moves the shop from 68 to 80 fps, and the note doesn't record whether each before and after used
  one position and view.
- **The shop's worst spot looks draw-submission-bound.** At the user's fixed worst-looking spot,
  the FULL aggressive profile (fog quality 30 %, fog far-clip **0.3 m**, particles 20 %, physics
  20 Hz, audio propagation off, reproj on) scored **identical to stock** (68.7 vs 68.8 fps p50).
  Volumetric fog, particles and physics are NOT the cost there; nothing runtime-tunable moved it. "Draw
  submission" comes from that elimination plus the WPR time inside UnityPlayer; no render-thread or GPU capture
  at that spot confirmed it.
  The only known fix (SPI stereo, halved draw submission) breaks this game's shaders (both eyes
  dark). Targeted spot-fps differences (80 at shop-keeper vs 68 elsewhere) are view-dependent
  draw cost, not tunable state.
- **Stock fog already runs temporal reprojection** (enabled, factor 0.95) — a "fog reproj" lever
  must cache/restore that, not assume off.
- Practical ceiling on this evidence, for cuts that don't show in indoor screenshots: ~10 % where fog and
  particles cost, ~0 % in draw-bound spots. A 144 Hz lock doesn't look reachable without shader-level work.

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
  silently applied physics/CCD on scene entry while disabled — fixed in v2.5.0, so "stock" runs before
  that weren't fully stock).

## Assets
No external art needed - the whole theme is cloned at runtime from the game's own widgets, so nothing from the
game ships. Screenshots of states stay in the author's private lab folder.

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
  safe exit. Harmony patches already are native detours (Gotcha 1), so patching whatever reads those fields is
  the next thing to try.
- A one-frame lag on the pill row: the pill can show click over hover in the first 0.2 s if the pointer was
  already hovering before the page was built (visual only).
- Untested/unfinished levers (project closed 2026-11-02 before raid A/B): audio propagation off in
  raids, Aura reproj delta (stock already on at 0.95 — lever likely useless), frustum-margin
  component throttler (designed, not built). Final verdict: shop worst-spot looks draw-bound; the only wins
  seen are the ~10 % above, and they are in the default profile.
