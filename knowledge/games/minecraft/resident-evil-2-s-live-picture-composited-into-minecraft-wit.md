---
kind: game
title: "Resident Evil 2's live picture composited into Minecraft with depth"
game: "Minecraft"
games_also: ["Resident Evil 2"]
game_version: "Minecraft Java 26.3 + Fabric Loader 0.19.5 / Fabric API 0.161.0+26.3 (Loom 1.18.2, JDK 25); Resident Evil 2 (Steam app 883710, RE Engine, D3D12) + REFramework 1.5.9.1"
platform: windows
engine: java
route: passthrough
tools: ["REFramework 1.5.9.1 (native plugin + Lua probe)", "Fabric Loader 0.19.5 + Fabric API 0.161.0+26.3 (Loom 1.18.2, JDK 25)", "MSVC 14.44 (VS 2022 Build Tools)", "sheet preflight, fake_frame_producer.py, dump_live_frame.py", "um win (shot/drive)"]
anti_cheat: "none detected on re2.exe; both games single-player and offline only, never launched online"
status: working
agents: ["OpenCode (mimo-v2.6-flash)"]
humans: []
date: 2026-10-06
links: ["https://github.com/praydog/REFramework", "https://github.com/rehan-remade/universal-modder/tree/main/examples/minecraft-gta5-passthrough"]
tags: [mashup, passthrough, shared-memory, seqlock, depth-compositing, d3d12, frame-capture, reframework, fabric, mixin, reversed-z, camera-mirror]
---

# Resident Evil 2's live picture composited into Minecraft with depth

> Minecraft Java 26.3 is the visible game: Resident Evil 2's live rendered picture (colour **and** linear
> depth in metres) is drawn into Minecraft's view and depth-tested against Minecraft's own depth buffer, so
> Minecraft blocks occlude RE2's world and RE2's world shows through Minecraft's sky and gaps. RE2 keeps
> camera and input authority (Leon drives; his view is mirrored into Minecraft's camera). It runs in the
> real games: a two-game session verified the F8 fixture stone occluding RE2's picture and RE2's night sky
> replacing Minecraft's day sky through the probes and screenshots, with Minecraft's clouds and terrain
> still winning where nearer. Local prototype, not published.

## Setup
- **Host PC:** Windows 11 build 26200, NVIDIA driver 616.56 (GL 3.3.0 NVIDIA),
  `d3d12.dll` 10.0.26100.9278, `D3D12SDKLayers.dll` absent (no D3D12 debug layer - see the technique note).
- **Resident Evil 2:** Steam app 883710 at `...\steamapps\common\RESIDENT EVIL 2  BIOHAZARD RE2`, RE Engine,
  `re2.exe` x64, always DX12 (`Capability/TargetPlatform/PCDXver=DirectX12` in `re2_config.ini`), no
  anti-cheat detected. **REFramework v1.5.9.1** (official `RE2.zip`, SHA-256 verified) installed into the
  game folder with the user's approval; saves backed up first (`um backup`, 19 files / 56 MB zip).
  `re2_config.ini` backed up next to itself as `re2_config.ini.dx12.bak` and restored after the final run.
- **Minecraft:** Java Edition **26.3**, Fabric Loader **0.19.5**, Fabric API **0.161.0+26.3**, Loom
  **1.18.2**, JDK **25.0.4.1**, development client with its own run dir and an isolated single-player world
  (the player's normal profile and worlds are never touched). Java 25 FFM needs
  `--enable-native-access=ALL-UNNAMED` (from the sheet) for the Win32 shared-memory calls.
- **Bridge:** one MSVC-built native plugin (`leon_bridge_host.dll`, VS 2022 Build Tools, MSVC 14.44,
  `/std:c++20`) in `{game}/reframework/plugins`, one Lua probe in `{game}/reframework/autorun`, and a
  Fabric client mod. Design sheet (`design/sheets/vertical-slice.json`) is the source of truth:
  `tools/preflight_sheets.py --generate` emits the Java protocol constants **and** the C++ wire-struct
  header from it and validates every offset/width, so Java and C++ cannot drift.
- Credit: [REFramework](https://github.com/praydog/REFramework) (praydog) for the whole RE2-side hook
  surface; this repo's `examples/minecraft-gta5-passthrough` (MCPassthrough.fx depth maths, FrameExporter
  seqlock layout, GameRendererMixin injection points) was the port template - this note mirrors it with the
  games' roles reversed.

## Route and why
**Passthrough:** two unmodified games run side by side; a mod in each exchanges state over local shared
memory. Direction decided by the user: Minecraft visible, RE2 the picture source and the input/camera
authority (so the earlier camera-mirror slice was reused untouched). Alternatives considered:
- **ReShade compositor inside RE2** (archived design under `design/archive/`): wrong direction once RE2
  had to be the guest picture, and it would have shipped as an RE2-side screen overlay of Minecraft.
- **Wiring only `REFrameworkRendererData`'s D3D11 device:** our first capture path was D3D11-only, but RE2
  runs D3D12 - that path never fired once (see Gotcha 9). The SDK isn't D3D11-only (its example plugin
  branches on `renderer_type` for D3D11 and D3D12); the plugin now queries the swapchain.
- **A screen-in-world stepping stone** (RE2 on a monitor block first): skipped; the user wanted the full
  depth-aware composite as the first picture milestone.
- **Reimplementing either game:** never sensible for a picture-in-picture effect.

## How the game works (what we had to learn)
- **RE2 capture (D3D12).** Colour comes from the swapchain backbuffer (1920x1080, format 28 = `R8G8B8A8`
  sRGB); depth comes from a device-side `CreateDepthStencilView` wrap that keeps a DSV table and prefers the
  backbuffer-sized handle. RE2's depth renders at **2880x1620 = exactly 1.5x supersample** of the colour, so
  depth is accepted under an exact-match-or-uniform-supersample rule and nearest-mapped to picture
  dimensions. Three hardcoded command-list/device vtable slots do the hooking:
  **`ResourceBarrier`=26, `OMSetRenderTargets`=46, `CreateDepthStencilView`=21** (fixed by the D3D12 COM
  ABI, so RE2 updates can't move them).
- **Depth maths.** RE Engine is reversed-Z (1.0 = near, 0.0 = far); stored depth linearises to metres with
  `z = n*f / (n + d*(f - n))` using the clip snapshot the pose writer publishes (probe: near 0.01, far
  3000, fov 74.8). Published frames carry metres, flags `1|4` (bottom-up rows, reversed Z).
- **Transport.** Windows named mapping `Local\LeonRe2FrameV1` (199,069,696 bytes): 4096-byte header, three
  128-byte descriptors at `256 + 128*slot`, two RGBA8/r32f layers up to 3840x2160, seqlock (sequence odd
  while writing, reader re-checks after use), stale limit 250 ms, future allowance 50 ms. The 200-byte
  camera pose record uses the same seqlock idea on a second mapping at ~52 Hz. All constants are generated
  from the sheet - the fake producer and the dump tool read the same sheet so they cannot drift from the
  reader.
- **Minecraft internals (26.3).** The composite injects at `GameRenderer.renderLevel` just before
  `render3dHud` (world complete, hand not yet drawn). `GameRenderer.render()` works on `mainRenderTarget`'s
  **offscreen** textures; `GlSurface.blitFromTexture -> present()` rewrites default FBO 0 *after* the
  inject, so the pass draws into a private FBO built over main's colour+depth via `GlTexture.glId()`
  (identity-checked, recreated when the window resize swaps textures, 5 s retry, fail-closed).
  Minecraft 26.3's projection is ZERO_TO_ONE reversed-Z (`b = -1`, `func=GEQUAL`, ortho when `b == 0`); a
  fragment distance maps to window space with `window(dist) = (c - a*dist) / (d - b*dist)` - no `0.5(·+1)`
  GL shift. Minecraft's far clip is **1024 m** against RE2's real 3000 m (Gotcha 2). The hand is suppressed
  with a cancellable `renderItemInHand` HEAD mixin while the pass is active; RE2's frame carries Leon and
  his HUD.
- **Input.** Minecraft 26.3 key bindings use **SDL scancodes** (`KEY_F8 = 65`), not GLFW codes (Gotcha 5).
  The F8 fixture places one `minecraft:stone` three units ahead of the mirrored camera, refuses without a
  fresh RE2 pose, and never replaces a non-air block.

## Build steps
```powershell
# 1. Sheet -> generated Java + C++ protocol (validates cells, offsets, widths)
uv run --offline --with pillow tools\preflight_sheets.py --generate     # 63 cells, 0 unresolved

# 2. RE2 side: build the plugin with MSVC x64 (/std:c++20), then - WITH THE USER'S APPROVAL - install
#    hash-verified into {RE2}/reframework/plugins (+ the Lua probe in reframework/autorun).
#    Backup first: um backup (Steam remote saves), copy re2_config.ini -> re2_config.ini.dx12.bak

# 3. Minecraft side (development client, isolated run dir)
$env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.4.1"
.\gradlew.bat build --no-daemon
.\gradlew.bat runClient --no-daemon

# 4. Iteration tools (no RE2 needed for the first three)
uv run --offline tools\fake_frame_producer.py                 # synthetic colour+depth writer; stop it
                                                              # by exact PID before opening live RE2
uv run --offline --with pillow --with numpy tools\dump_live_frame.py   # live slot -> PNGs, stats, RANSAC
uv run --offline --project <universal-modder> um win shot --exe java out.png
uv run --offline --project <universal-modder> um win drive --proc java "focus" "key 0x1B"  # close MC's pause menu
```

## Verification
- **Harnesses first (no games):** Java decoder self-test 23/23 checks (torn/stale/future/malformed pose
  records); frame protocol self-test 41/41 (25 rejection paths); fake producer cross-process run accepted
  1409 frames / 0 torn / 0 rejected at ~29.6 fps, then correctly rejected as stale after the writer exited.
- **Capture, live RE2:** first-capture log line with geometry and `invalid=0`; 30 s heartbeats with
  `frame==total` (zero rejects); depth range 0.11..3000.00 m across a real session. Oracles: statue-room
  colour/depth silhouette pixel-aligned (Leon nearest ~1.34 m); eyeballed wall 2.6-2.7 m predicted vs
  ~2.9-3.1 m measured (wall angled); open-sky aim puts 49.0% of pixels at exactly 3000.000 m (an inverted
  reversed-Z would read ~0.01 m); floor plane fit rms 3.6 cm agreeing with the game's own camera height
  within 1.5 cm.
- **Composite, fake producer then live:** with the real depth test (`func=GEQUAL`, `glError=0x0`, private
  `main FBO` attached), the fake checkerboard fills sky/gaps and vanilla clouds/terrain occlude it; the
  stale path reverts to vanilla; the hand stays hidden. Live two-game run: pose connected and calibrated,
  frames ~30 fps, fov tracking the probe, F8 stones placed at `(47,78,-5)` and `(47,78,-6)`; sky probes
  `before=184,210,255` (Minecraft day blue) `after=15,19,23 / 13,17,20 / 7,8,8` (RE2 night), centre stone
  probe `68,68,69` unchanged through the draw (Minecraft wins), MC's day clouds and lit grass winning
  where nearer, HUD on top, no hand; window resize re-attached the FBO and kept working.
- **Not verified:** third-person avatar hand policy (out of the first-person slice); audio of either game
  in the mix; whether the sky-flag `ModifyArg` actually suppresses Minecraft's sky (the beyond-clip floor
  made it moot - probes show MC's sky colour present *before* our draw); long-session (>1 h) stability;
  other GPUs/drivers (one NVIDIA 616.56 machine); no showcase video; no release (no one-click install path
  for the Fabric side yet - stays local/draft-only).

## Gotchas
1. **Composite draws but the screen never changes.** Probes right after the draw show the right colours on
   `fbo=0`, the picture is still vanilla. **Cause:** `GameRenderer.render()` writes `mainRenderTarget`'s
   offscreen textures and `GlSurface.blitFromTexture -> present()` rewrites default FBO 0 *after* the
   `render3dHud` inject, erasing the draw every frame. **Fix:** build a private FBO over main's colour+depth
   textures (`GlTexture.glId()`), identity-check each frame, recreate on texture swap (resize), retry 5 s,
   fail closed.
2. **Guest sky never wins: open-sky pixels keep Minecraft's sky.** **Cause:** RE2's real depth reaches
   3000 m but Minecraft's far clip is 1024 m; `window(dist)` extrapolates *negative* past the clip (and can
   NaN), so every beyond-clip pixel lost `GEQUAL` against Minecraft's cleared/sky depth. The fake
   producer's 700 m sky sat inside the clip and hid this for days. **Fix:** floor the guest depth at
   `1e-6` (the far end of Minecraft's own clip) in the fragment shader - ordering stays correct for every
   distance Minecraft can render (view distance 16), because no host geometry exists past the clip.
3. **Depth comparison looks inverted/garbage with the textbook GL formula.** **Cause:** 26.3 uses
   ZERO_TO_ONE reversed-Z: the logged matrix decodes `a=4.883051E-5 b=-1.0 c=0.05000244 d=-0.0` (near 0.05
   -> 1.0, far 1024 -> 0), so the classic `0.5(·+1)` shift is wrong. **Fix:**
   `window(dist) = (c - a*dist) / (d - b*dist)`, `func=GEQUAL`, ortho guard `b == 0`; print `a,b,c,d` plus
   `fdNear/fdFar` from the shader once to decode any future matrix change.
4. **Camera publishes fov=2.0 and near=2.0 for 27 minutes while the probe reads 74.8.** **Cause:**
   REFramework's `InvokeRet` is one union (bytes[128] with `float f` / `double d` aliasing) and float-returning
   getters are widened to double by the invoke wrapper; reading the *float* view gets the low 4 bytes of the
   double. Values whose float bits end in `010` decode to exactly `2.0` - inside the plausible-magnitude
   window - and RE2's `74.8` (`0x4295999A`) and `0.01` (`0x3C23D70A`) both do; 7 of 8 bit patterns fall
   outside the window and happened to read correctly. **Fix:** read the double view first (matching
   REFramework's own parser), keep the float view only as fallback for genuinely raw-float returns (whose
   double view is denormal and fails the window).
5. **F8 does nothing although options.txt shows a binding.** **Cause:** Minecraft 26.3 input uses SDL
   scancodes (`InputConstants.KEY_F8 = 65`), while the saved binding and GLFW say `key.keyboard.297`;
   vanilla F-keys worked only because they use their own scancode constants (F3 = 60). **Fix:** sheet
   `triggerKeyCode` 297 -> 65 (source of truth; preflight regenerates the protocol), patch the saved
   binding, and keep a raw-poll fallback trigger while diagnosing. Disassemble the Loom-mapped jar to read
   the real constants.
6. **Minecraft boots with default options and a `NumberFormatException` on `key.keyboard.g`.** **Cause:**
   PowerShell 5.1 `Set-Content -Encoding UTF8` wrote a UTF-8 BOM; MC failed to parse `version:`, ran the
   legacy key datafixer, and misread the named format. **Fix:** never BOM-write Minecraft config files from
   PS 5.1 - no-BOM or line-scoped edits only.
7. **Writer runs for 9 minutes, guest never calibrates, no reason is logged anywhere.** **Cause:** publish
   gates early-returned silently (one-shot latch, silent world-matrix/forward early-outs) so the reader
   only ever saw "no record". **Fix:** log every blocked-publish reason *on change*, throttled to 5 s, with
   per-getter status and raw values; give the reader an `explainRejection` that re-reads seqlock misses and
   names the exact rejection (torn, timestamp, clip range, short forward).
8. **`E_INVALIDARG` creating what looks like a valid D3D12 readback texture.** **Cause:** D3D12 forbids
   textures on UPLOAD/READBACK heaps, and a `ROW_MAJOR` texture is only legal on a cross-adapter shared
   heap. **Fix:** buffer-based readback (`GetCopyableFootprints` + `CopyTextureRegion` into a READBACK
   buffer) - full rule matrix in the companion technique note. With no debug layer installed, the HRESULT
   was the only diagnostic: prove the rule matrix in a tiny harness against **WARP** first (it matched
   NVIDIA exactly, i.e. spec, not driver).
9. **Our D3D11 capture path never fires.** **Cause:** the first plugin only wired D3D11, but RE2 runs D3D12.
   The SDK isn't D3D11-only: REFramework's example plugin branches on `renderer_type` for D3D11 and D3D12,
   and `PluginLoader::init_d3d_pointers` sets it from the active hook every frame. **Fix:** branch on
   `REFrameworkRendererData::renderer_type` (as the example plugin does) or query the swapchain; on D3D12
   hook `ResourceBarrier=26`, `OMSetRenderTargets=46`, `CreateDepthStencilView=21` (fixed by the D3D12 COM
   ABI), track DSVs in a table, refuse MSAA/unsupported depth with bounded logs.
10. **First-person hand renders on top of the composite.** **Cause:** the inject point precedes
    `renderItemInHand`. **Fix:** a single cancellable `@Inject(method="renderItemInHand", at=HEAD)` mixin
    that cancels while the composite is active (screen effects keep running; third-person avatar untested).
11. **RE2 paused/minimized would freeze a ghost frame over Minecraft.** **Cause:** no new guest frames.
    **Fix (by design):** fail closed past the 250 ms stale limit - Minecraft renders completely vanilla,
    and recovers when frames resume; keep the stale reason logged so silence isn't misread as failure.
12. **Screenshots keep catching Minecraft's pause menu.** **Cause:** Minecraft opens its game menu within
    ~1 s whenever its window loses focus during these two-game runs (every switch away to RE2 or chat does
    it). **Fix:** focus the Minecraft window and send Esc in one `um win drive` invocation (only with the
    user's approval - input automation needs asking), then shoot immediately.
13. **`GL_COLOR_ATTACHMENT0` does not compile.** **Cause:** it lives in `GL30`, not `GL11`. **Fix:**
    reference `GL30`; keep a `glGetError` probe after every composite draw anyway.
14. **F8 on an occupied cell logs nothing at all.** **Cause:** the never-overwrite refusal path is silent
    (no placement happened - the safety rule holds - but the user can't tell a refusal from a dead key).
    **Fix:** add a bounded refusal log line (noted, not yet done).
15. **Depth picture is 1.5x bigger than colour.** **Cause:** RE2 renders depth at 2880x1620 while the
    swapchain is 1920x1080. **Fix:** accept exact-match or uniform-supersample ratios only, nearest-map depth
    to picture dimensions, and keep provenance flags from the source storage (values stay metres).

## Assets
No game assets are shipped or republished: RE2's picture is read at runtime and never leaves the machine,
screenshots stay outside the repo, and the only "art" is the synthetic checkerboard/depth ramp from
`tools/fake_frame_producer.py` plus F8-placed stones in the isolated dev world.

## Cost and time
Two calendar days (2026-10-05 to 2026-10-06), six logged combined game runs plus tool-only iterations, one
56 MB save backup, no API spend (everything local), no new hardware. Most time went to three root causes
(FBO present-order, InvokeRet union, far-clip extrapolation) that all hid behind "it looks fine but isn't".

## Open questions
- Third-person avatar policy (out of the first-person slice; presumably suppress like the hand).
- Whether the sky-flag `ModifyArg` is needed at all now that beyond-clip guest depth is floored.
- Audio mixing between the two games (RE2's audio is the natural choice but nothing is wired).
- One-click/launch story: there's no one-click install path for the Fabric side yet; the project stays
  local/draft-only until then.
- A showcase video (`um video` contact sheets / EDL) and a `media/` thumbnail for the note.
