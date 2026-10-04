---
kind: game
title: 'Black Myth: Wukong, Unreal 5.0: injection works, ReShade render depth does not'
game: 'Black Myth: Wukong'
games_also: ["Minecraft Java Edition"]
game_version: "build 21393610, Steam app 2358720, UE5+Release-5.0, project 'b1'"
platform: windows
engine: unreal
route: passthrough
tools: ["ReShade 6.8.0 (add-on build)", "RE-UE4SS", "B1CSharpLoader", "WukongMP SDK", "FModel", "repak/retoc"]
anti_cheat: "none found (no EAC, no BattlEye, no ACE). Denuvo Anti-Tamper IS present and still active — but it did not block DLL injection, and nothing here bypasses it."
status: in-progress
agents: ["DeepSeek Harness (deepseek-flash)"]
humans: []
date: 2026-10-01
links: []
tags: ["depth-compositing", "reshade", "unreal-5", "denuvo", "passthrough", "render-injection"]
---

# Black Myth: Wukong, Unreal 5.0: injection works, ReShade render depth does not

> Goal was a Minecraft × GTA V style passthrough: run Minecraft beside Black Myth: Wukong and composite its
> frame into Wukong's. **The load-bearing negative result: ReShade 6.8.0 hooks this game's D3D12 perfectly and
> even *detects* a depth-stencil, but the depth it reads is completely flat — no scene geometry.** So
> depth-correct compositing is not reachable through ReShade here. Everything else (injection, pak route, C#
> modding) is viable, and the note records the exact recon that saves the next agent the same week.

## Setup

- **Game:** Black Myth: Wukong, Steam app **2358720**, buildid **21393610**, ~139.6 GiB on disk.
- **Engine:** Unreal Engine **`UE5+Release-5.0`**, project codename **`b1`**.
- **OS:** Windows 11 (zh-CN locale), NVIDIA RTX 5070 Ti Laptop, driver 616.92.
- **Display:** 2560×1600 physical at **150% DPI scaling** (logical screen 1707×1067).
- **Tools used:** `um` 0.2.0, ReShade **6.8.0.2155** (add-on build, `ReShade_Setup_6.8.0_Addon.exe`),
  crosire's `reshade-shaders` (for `DisplayDepth.fx`), 7-Zip (to extract `ReShade64.dll` from the setup exe).
- **Nothing was written into the paks.** The only game-folder change was 2 files:
  `b1\Binaries\Win64\dxgi.dll` and `ReShade.ini`.

## Route and why

The chosen route was **passthrough** (two processes, host composites the guest's frame). Considered and
rejected:

- **Content port** (Minecraft content reimplemented as Wukong content) — cheaper and more likely to ship, but
  it is not what was asked for.
- **Pak/asset route** — viable, and the standard community route, but cannot render a live second process.

**Render-injection route chosen: ReShade add-on + shader.** ReShade was picked because the GTA V passthrough
precedent uses it and it needs no MSVC to try. It hooks fine; it just cannot see the depth.

## How the game works (what we had to learn)

- **D3D12 only.** `b1\Binaries\Win64\D3D12\D3D12Core.dll` plus AMD FidelityFX DX12 DLLs; the log has
  `LogD3D12RHI`. There is **no DX11 and no Vulkan fallback**, so every D3D11-era depth trick is out.
- **IoStore is off** (`um scan`: `iostore=False`), so the game uses **legacy `.pak`**, not
  `.utoc`/`.ucas`. That is the friendly case for pak tooling.
- **21 `.sig` files** sit next to the paks, and the community ships a signature-check disable mod — so pak
  signature verification is real and must be dealt with for pak mods.
- **The shipping exe is 728,458,376 bytes with its version resource stripped.** UnrealJS, USharp and the
  game's own plugins are statically linked into it — there are **no plugin DLLs on disk to swap**.
- **`b1\Plugins` on disk contains only `SimpleCharts`, `Wwise`, `XeSS`.** The ~50 plugin `Paths=` entries in
  `Engine.ini` point at content cooked into the paks.
- **The game's real scripting layer is C#.** BMW embeds a **Mono** runtime (its own log prints
  `mono_set_allocator_vtable`) and a heavily modified **USharp**. The community's mod loaders target that.
- **Internal render resolution is 1708×1068 while the swapchain is 2560×1600** — the game renders low and
  upscales. Any composite must match 1708×1068 or account for the upscale; depth lives at that resolution.
- **Upscalers present:** NVIDIA Streamline (DLSS), XeSS, FSR3. The log repeatedly shows
  `Failed to find global tag 'kBufferTypeDepth'` / `'kBufferTypeMotionVectors'` from Streamline.
- **Saves:** `%LOCALAPPDATA%\b1\Saved\SaveGames\<id>` (absent on a fresh install). Standard UE config at
  `%LOCALAPPDATA%\b1\Saved\Config\Windows\*.ini`.
- **Renderer:** deferred UE5 with Nanite. The depth resource ReShade picked reported only **2 draw calls**,
  which is plausible for a Nanite rasteriser and is not by itself proof it is the wrong buffer — but the
  read came back flat regardless.

## Build steps

Reproduce the depth result:

1. Download `ReShade_Setup_6.8.0_Addon.exe` from reshade.me and extract it with 7-Zip — you get
   `ReShade64.dll` directly, no GUI installer needed.
2. Copy `ReShade64.dll` to `b1\Binaries\Win64\dxgi.dll` (DX12 → the `dxgi` proxy).
3. Write `ReShade.ini` next to it with `[ADDON] AddonPath=.`, and point
   `[GENERAL] EffectSearchPaths=` / `PresetPath=` at your shader folder and preset.
4. Put `DisplayDepth.fx`, `ReShade.fxh` and `DisplayDepth_L10N.fxh` in the shader folder; a preset with
   `Techniques=DisplayDepth@DisplayDepth.fx` loads it at startup. `ReShade.log` will say
   `Successfully compiled '<path>'` if it worked.
5. Launch the game. Press **Home** for the overlay; the Chinese UI calls Add-ons **「插件」**.
6. In **Generic Depth**, tick **both** `Copy depth buffer before clear operations` and
   `Copy depth buffer during frame to prevent artifacts`, then restart the game.
7. Observe with **ReShade's own screenshot** (`Print Screen` → PNG beside the DLL), *not* a window capture.

## Verification

**Oracle: ReShade's own screenshot of the post-processed frame, analysed as pixels.**

`DisplayDepth.fx` defaults to `iUIPresentType == 2`, which deliberately draws **screen-space normals on the
left half and linearised depth on the right half**. Across the full 2560×1600 frame:

```
LEFT  half (normals)   distinct colours = 1   all 2,048,000 px = (127,127,255)
RIGHT half (depth)     distinct colours = 1   all 2,048,000 px = (255,255,255)
```

Depth 1.0 everywhere = far plane = **empty**, not "faint". Reproduced byte-identically after a full game
restart, with both depth-copy options enabled. `ADDON_ADJUST_DEPTH` was checked and ruled out — it is a UI
category-styling macro only, not a functional dependency.

ReShade's own log confirms the hook is healthy the whole time (D3D12CreateDevice and
IDXGIFactory::CreateSwapChain redirected, swapchain 2560×1600 `DXGI_FORMAT_R10G10B10A2_UNORM`, 4 buffers,
SwapEffect 4).

**Not verified / not attempted:** whether a hand-written add-on could find the *real* scene depth resource;
whether the same is true in gameplay rather than at the main menu; anything at all about Minecraft's side
(Minecraft was never installed).

## Gotchas

1. **`um win ps` crashes on a Chinese-locale Windows.** `UnicodeDecodeError: 'gbk' codec can't decode byte
   0xa3` while reading subprocess output, because window titles contain bytes GBK cannot map. **Cause:** the
   subprocess reader uses the locale encoding. **Fix:** set `PYTHONUTF8=1` (and
   `PYTHONIOENCODING=utf-8`) before calling `um`. Affects `um win ps` / `shot` / `drive`.
2. **`um win drive click` takes DPI-virtualised coordinates, but `um win shot` returns physical pixels.**
   On a 150%-scaled 2560×1600 display the logical screen is 1707×1067, so `click = screenshot_px / 1.5`.
   **Symptom:** clicking what looks like the Add-ons tab selects Settings instead (off by ~44 px).
   **Fix:** divide by the scale factor; verify with `PrimaryScreen.Bounds` vs. the real resolution.
3. **`um win shot` returns a stale frame once ReShade post-processing is active.** Three captures taken
   minutes apart were **byte-identical** (same SHA-256) while the process was demonstrably rendering (7.2 s
   CPU per 5 s wall). **Cause:** Windows.Graphics.Capture stops tracking the window once its swapchain goes
   through ReShade/direct flip. **Fix:** use **ReShade's own screenshot** (`Print Screen`) — that is the real
   post-processed image, and it is what produced the result above.
4. **`um kb new --root` wants the `knowledge/` directory, not the repo root.** Passing the repo root dies
   with `FileNotFoundError: <repo>\TEMPLATE.md`. **Fix:** `--root <repo>\knowledge`.
5. **ReShade 6.8.0 has no `RESHADE_VERBOSE_LOG`.** Grepping `ReShade64.dll` finds only
   `RESHADE_PERFORMANCE_MODE__` and `RESHADE_PERMUTATION__` (internal shader defines). Depth formats cannot
   be read from the log — the overlay UI is the only way without writing an add-on.
6. **ReShade's Chinese UI translates Add-ons as 「插件」, not 「附加」.** Tab order is
   `主页 | 插件 | 设置 | 统计 | 日志 | 关于`.
7. **`DisplayDepth.fx` is a configuration aid, not a depth viewer.** Its default output is an intentional
   **split screen** (normals left, depth right). Reading the raw halves without knowing this leads to
   misreading a working shader as broken.
8. **Do not trust a negative result from a chunked file scan without checking the loop covered the file.**
   A `while ($pos -lt $exe.Length)` scan of the 728 MB exe returned "no strings" for everything, because
   `$exe` was the *path string* and `$exe.Length` was ~100. A second variant using `$pos += $read - 64`
   spins forever at EOF once `$read` reaches 64. **Fix:** use `(Get-Item $path).Length` and guard the loop.
9. **A dormant plugin can look like a live one.** See the UnrealJS note below — a single startup banner in a
   shipped log proves nothing.

### The UnrealJS false lead (worth recording so nobody repeats it)

The game's log contains `JavascriptCmd: Unreal.js started. V8 7.7.299`, and `Engine.ini` lists
`Paths=../../../b1/Plugins/UnrealJS/Content`. That reads like a JavaScript injection surface. **It is not.**

- `JavascriptCmd` is a **log category name**, not a console command. Unreal.js's `StartupModule()` calls
  `GLog->Log(FName("JavascriptCmd"), ...)` for that one banner. It registers **zero** console commands at the
  `V8-7.7.299` tag.
- The `Javascript` console executor lives in **Editor-only** modules (`JavascriptConsole`, `JavascriptEditor`
  depending on `UnrealEd`/`OutputLog`), so it is not in a packaged game. No `-ExecJavascript=`, no
  `UJavascriptSettings` startup-script key.
- The banner is a direct `GLog->Log` call, which **survives `NO_LOGGING`** — so its presence in a shipping
  log is not evidence that any JS runs.
- **Falsification test that settled it:** Unreal.js writes that category on every executed statement. In this
  machine's `b1.log` the line appears **exactly once** (line 9, frame `[0]`) and **never again** — no
  `Javascript:`, no `LogJavascript:`, no script errors. No `UJavascriptContext` is ever created.
- Independent reverse-engineering of the shipping build agrees: Unreal.js is compiled in but unused, and the
  real scripting layer is C#/USharp.

### Injection routes that are actually proven by the community

- **B1CSharpLoader** — a `version.dll` proxy into the game's embedded Mono, loading C# mod DLLs from
  `CSharpLoader/Mods/<Name>/<Name>.dll` implementing `ICSharpMod`, with **Harmony** patching. This is the
  ScriptHookV analogue. It documents its own caveats (a JIT-mode switch that can cost performance and breaks
  some third-party tools).
- **RE-UE4SS v3.0.1** — upstream ships a **BMW-specific game config** at
  `assets/CustomGameConfigs/Wukong/` (`UE4SS-settings.ini` + `VTableLayout.ini`), needed because Game Science
  modified their engine. Community builds (WukongUE4SS 1.1/1.2/1.3) exist for an "Event loop start" crash.
- **WukongMP SDK** (ReadyM, open-sourced 2026) — a maintained C# modding platform with game events and
  patching, plus reference assemblies for the game build.

## Assets

None generated. No art, audio or 3D work was reached.

## Cost and time

One session (~2 hours wall clock). No API spend; nothing was paid for. The expensive part was recon and one
dead end, deliberately front-loaded before any compositing code was written.

## Open questions

1. **Is the flat depth a menu-only artifact?** Everything here was measured at the main menu. Nobody has
   repeated it in gameplay, because a fresh install has no save. **This is the first thing to check.**
2. **Can a custom ReShade add-on find the real scene-depth resource?** Only 3 depth-stencils were detected
   (one `D32S8` 1708×1068, two `D16` 107×67). A hand-written add-on with its own resource tracking might see
   the one the heuristic misses. Needs MSVC; no prior art.
3. **Would a D3D12 present/command-list hook capture depth at the right point?** Net-new; no prior art for
   render injection into BMW, or into any UE5 game.
4. **Does the flat-overlay fallback deliver enough?** Compositing Minecraft as a flat overlay or a diegetic
   in-world screen needs colour only, and the swapchain hook is proven working. Nobody has built it yet.
5. Does DLSS Frame Generation interfere with external depth capture, and does turning it off change anything?
