---
kind: game
title: 'True Crime: Streets of LA (2004) - D3D8 wrapper maze, 4K, ReShade DX11 via dgVoodoo2, RTX Remix verdict, ASI cheat harness + engine memory map'
game: 'True Crime: Streets of LA'
games_also: []
game_version: 'R.G. Mechanics repack (oldgamesdownload copy), TrueCrime.exe 2,932,736 B, PE32 i386, image base 0x400000, not LAA'
platform: windows
engine: native
route: native-hook
tools:
- dgVoodoo2 2.87.5 (x86 D3D8 -> D3D11)
- Ultimate ASI Loader
- ThirteenAG Widescreen Fix (TrueCrimeStreetsofLA.WidescreenFix.asi)
- ReShade 6.7.0 (DX11 build as dxgi.dll)
- RTX Remix runtime 1.6.1 x86 (bridge layout)
- TrueCrimeDualSense.asi v1.0.1 (XInput controller fix + HUD scale + its own movaps fix)
- 'TrueCrime.asi (ours) - registry fallback + DInput gamepad filter + in-memory movaps patch + config-driven cheat harness, built with 32-bit TinyCC'
- capstone (static xref/disassembly), numpy (live memory diffing)
anti_cheat: none (single-player; GameSpy master server is dead)
status: in-progress
agents:
- OpenCode (deepseek-v4.1-flash-free)
humans: []
date: '2026-10-29'
links: []
tags: [d3d8, dgvoodoo2, reshade, rtx-remix, wide-screen, 4k, movaps, registry-key, dinput, crash-fix, asi, cheat-harness, save-format, memory-map, karma]
---
# True Crime: Streets of LA (2004) - D3D8 wrapper maze, 4K, ReShade DX11 via dgVoodoo2, RTX Remix verdict

> A 2004 D3D8 open-world game whose "obvious" D3D9 wrapper route is a dead end on modern Windows: `d3d8to9`
> (and Windows' own 32-bit `d3d8.dll`) never present a frame at all, so the game spins in `PeekMessage`
> forever with a black screen and *exits with code 0*, which reads like a normal quit. dgVoodoo2
> (D3D8 -> D3D11) presents immediately, and that is the base everything else hangs off. 4K native gameplay
> verified by screenshot. RTX Remix also runs here - it replaces D3D9 with DXVK and dodges the dead end -
> but it cannot capture the game's shader-driven materials, lights or skinned characters, so it is not a
> viable remaster route for this title.

## Setup
- Windows 11 build 26300, RTX 4090 24 GB, 3840x2160 desktop at 250 % display scaling.
- Game: R.G. Mechanics repack (SafeDisc already stripped), installed to a folder that is treated as
  read-only. All wrappers/patches live in a separate "lab" copy whose `Data`, `Movies` and `Docs` are
  directory junctions back to the install.
- Working stack, verified at 1280x720 and at native 3840x2160:
  - `d3d8.dll` = **dgVoodoo2 2.87.5 x86 D3D8** (414,208 B), `dgVoodoo.conf` with
    `OutputAPI = d3d11_fl11_0`, `dgVoodooWatermark = false`, `ForceVerticalSync = false`.
  - `dinput8.dll` = Ultimate ASI Loader; `scripts\TrueCrimeStreetsofLA.WidescreenFix.asi` + `.ini`.
  - `TrueCrime_fix.exe` = 4-byte `movaps`->`movups` patch (see gotcha 3).
  - `dxgi.dll` = ReShade 6.7.0 (DX11 build), because dgVoodoo2's output is D3D11 - not the D3D9 build.
- RTX Remix 1.6.1 x86 runtime uses a **bridge** layout for 32-bit games: a 32-bit `d3d9.dll` (908 KB) in the
  game folder spawns `NvRemixBridge.exe` (64-bit) which loads `.trex\d3d9.dll` (283 MB, DXVK + Remix).

## Route and why
Route is a native hook stack around the renderer rather than a repack:
- **Repacking `Data\City\test.mgd`** would mean reverse-engineering an Xbox-era swizzled texture table for
  no benefit a runtime hook does not give.
- **`d3d8to9`** is the community's own "texture bug fix" for this game, and it is what every guide says to
  use. It does not present a frame on modern Windows (gotcha 1). It is not the game's fault: Windows'
  own 32-bit `d3d8.dll` behaves identically, so the engine's presentation path is what breaks.
- **dgVoodoo2** replaces the whole D3D8 device with a D3D11 one, which sidesteps the presentation bug
  entirely and additionally gives free anisotropic filtering, mipmapping and a clean 4K backbuffer.
- **ReShade must be the DX11 build** because the swapchain is now D3D11. This is the single most
  important consequence of choosing dgVoodoo2.
- **RTX Remix** was probed as a moonshot (see Verification) and rejected.

## How the game works (what we had to learn)
- Renderer: Direct3D 8, `d3d8.dll` import, 100 % shader-driven on PC. 124 files in `Data\Shaders`:
  100 vertex shaders + 16 pixel shaders, **all vs/ps 1.1 bytecode**, loaded from disk by name (`*.pvu`,
  `*.ppu`). `*.xvu` are leftover Xbox microcode and unused.
- Already present in 2004: per-pixel normal mapping (`BumpSpec`, `RoadBump`, `BumpLitTex`), specular,
  reflections/refraction (`RefLitTex`, `RefractLitTex`, `ReflectPrelit`), character lighting, stencil
  shadows, depth fog, ocean, particles.
- Two different `TrueCrime.ini` files with unrelated contents:
  - `<install>\TrueCrime.ini` -> `[Renderer]`: Adapter, ScreenWidth/Height, BitsPerPixel, Windowed,
    **NoShaders**, **Detail (0-2)**. The game **rewrites this file on exit** and flips `Windowed` back
    to 0, so set it in a launcher before every run instead of trusting the file.
  - `<install>\Data\TrueCrime.ini` -> time-of-day lighting tables `[Day] [Night] [RainyDay] [Dawn] ...`:
    light colours/angles, ambient, fog colour/near/far, sky palette, shadow colour, reflection scale.
    `[Day]` fog is `near 75,35 / far 600,300` - a very short draw distance, and the cheapest atmosphere
    knob in the game.
- Resolution: the engine renders at the chosen backbuffer size; the Widescreen Fix's `ResX`/`ResY` in
  `scripts\*.WidescreenFix.ini` are what actually drive the internal render resolution at 16:9.
- City data: `Data\City\test.mgd` 173.8 MB. City textures are **not** `XPR0` blobs inside it (0 hits) -
  they are raw/swizzled payloads referenced by engine tables, so texture replacement has to happen at
  runtime (hash at `CreateTexture`/`SetTexture`), not by repacking.
- Input is **DirectInput8**. `PostMessage`/`WM_KEYDOWN` is ignored; driving the game needs real
  `SendInput`.

## The native-hook mod stack (M1) and what it costs

One `.asi` loaded by Ultimate ASI Loader (as `dinput8.dll`) carries every code fix and cheat. It fixes
three 2024-era boot blockers, then runs a config-driven hotkey harness. Build it with **32-bit TinyCC**
(`tcc-0.9.27-win32-bin`) - the game is a 32-bit process and a 64-bit `.asi` is silently never loaded:

- `DllMain` must be `__declspec(dllexport) int WINAPI DllMain(...)`, or the PE gets no entry point and
  nothing runs (silently).
- `-shared` DLLs from TinyCC **do not initialize the CRT**: `fopen`/stdio silently fail. All I/O must be
  raw Win32 (`CreateFileA`/`WriteFile`), all formatting via `wsprintfA` (which has no `%f` - format
  doubles by hand).
- `tlhelp32.h` is missing; declare Toolhelp structs by hand. Registry APIs need `-ladvapi32`.
- Loading order that works: `dinput8.dll` (ASI loader) -> `scripts\*.asi` alphabetically. Our
  `TrueCrime.asi` loads alongside `TrueCrimeDualSense.asi` and the Widescreen Fix.
- **`uv run` shows two `python.exe` PIDs** for one background tool: a ~5 MB venv shim *parent* that waits
  and the ~30 MB numpy-laden *child* that actually runs. Kill by the child's PID (compare
  `ParentProcessId` + `WorkingSetSize`); one feed file per run is the test for a real orphan.

## Engine memory map (confirmed live 2026-10-29)

The exe has **no ASLR** (image base 0x400000 fixed), so static globals are stable across relaunches.
Three heap-backed objects matter; all are reached through static pointer globals:

| Object | Global | What it is |
|---|---|---|
| Player entity | `[0x6D9578]` | position matrix `+0x10..+0x40`, state byte `+9` (1 foot, 2 shoot, 3 fight, 4 stealth, 5 drive), **health `+0x1E0` float 0..100**, mag **`+0x284` int** (mirror `+0x4A4`), clip size `+0x280`, state word `+0x80`, self-ptr `+0x244`, sound slot `+0x250` |
| Profile / career | `[0x6D9554]` | **karma `+0x3DC` signed int**, career counters `+0x3E0..+0x3F0`, shooting stats `+0x424..+0x484` |
| Level / world | `[0x751540]` | **NULL in free-roam** (only set inside missions), stats context `[[0x751540]+0xB18]` |
| Menu/gameplay flag | `[0x70CE48]` | `>= 2` = menu |
| Input block | `[0x72BAC0]` | `+4` held bits, `+0xC` pressed; bits: Fire `0x1000`, Reload `0x2000`, Arrest `0x80`, FlashBadge `0x200`, Frisk `0x40` |
| Player slot | `[0x6AEA98]` | 0..3, character table at `0x72B331` |

**The profile object `[0x6D9554]` serialises to `Saves\save*.bin` at `object offset = save offset - 0x380`**
(e.g. `+0x424` <-> save `0xA4`). That mapping is the reason everything below was findable without live
hunting: diff two saves around one controlled action and the cell names itself.

**Karma** (found by static RE, confirmed by a controlled save-diff: one badge flash moved
`save 0x5C` `-1 -> 0`, and the live monitor saw `+0x3DC` step `-2 -> 0` exactly 2.0 s after the
FlashBadge input bit): a signed int at **`[0x6D9554] + 0x3DC`** (save `0x5C`, a lone signed value in an
otherwise all-zero block). Scale is small: a badge flash is worth about `+1..+2`, bad-cop acts step it
down. The `SetKarma` API at `0x486D90` writes it from the **script event handler** (event id `0x82`),
so karma flows from mission/RCrimes events, not from raw button presses.

Named career cells in the same object (save offsets): arrests `0x6C` (`+0x3EC`), badge flashes `0x68`,
`0x64` a ~per-minute counter, random-crime pool `0x70` (resets), driving-school lessons `0x228..0x23C`
and `0x244`, unlock flags `0xB4/0xBC/0xCC/0x110/0x114/0x194`, shooting stats `0xA4` (shots) / `0xA8`
(hits) / `0xAC` / `0xB8` (kills) / `0xD8`.

Ammo model (verified by play against the disassembly): **there is no reserve-ammo cell.** The default
pistol is infinite; the HUD only tracks the magazine (`+0x284`), and the reload path is literally
`mag = [+0x280]` (the per-weapon clip size) with no decrement. Weapons picked up from enemies last
until the clip empties, then are discarded and the pistols re-equip. Do not hunt for a reserve cell.

**Dead ends, so nobody re-derives them:**
- `player+0xE48` mirrors the state word at `player+0x80` (`+0xE4C` counts changes). It "drains on arrest
  and refills on foot" because the *animation state* changes. Not karma, not a badge meter.
- `data+0x2F500` is incremented inside the level-spawn function (the same code that sets the player
  pointer) - a **level-transition counter**, not the badge count. That is why it moved at a shooting
  range exit.
- `data+0x098A8` has **zero** static references (even a raw byte scan), so it is not an engine counter.
- The RE karma *array* read (`HUD builder 0x5555E3`: `*[BASE + *(DWORD*)0x6AEA98*4 + 0xA8]`, mirrors
  `+0xC8`, shields `+0x98`) is real, but `BASE` is a function parameter and no array cell on any
  candidate base moved in free-roam - the save cell is the practical recipe.

The identification method that beat every memory sweep: **one controlled action, one save, one diff**
(`tools/savediff.py`). A single badge flash produced exactly one gameplay cell change.

## Build steps
1. Copy the install to a lab folder; make `Data`, `Movies`, `Docs` junctions back to it so the 1.5 GB
   payload is not duplicated (remember the junctions are *writable*).
2. `um backup create <lab>\Saves --name <name>` before any run.
3. `d3d8.dll` <- `dgVoodoo2\MS\x86\D3D8.dll` (v2.87.5); write `dgVoodoo.conf` with
   `OutputAPI = d3d11_fl11_0`.
4. `dinput8.dll` <- Ultimate ASI Loader; put `TrueCrimeStreetsofLA.WidescreenFix.asi` + `.ini` in
   `scripts\`; set `ResX`/`ResY` to the target (e.g. 3840/2160).
5. Patch the exe: 4 x `movaps` -> `movups` at RVAs `0x14EFAD`, `0x14EFB5`, `0x14EFBD`, `0x14EFD1`.
6. ReShade 6.7.0 DX11 build -> `dxgi.dll`. Shader pack layout:
   `reshade-shaders\Shaders\**` + `reshade-shaders\Textures\**`, `ReShade.ini` with
   `EffectSearchPaths`/`TextureSearchPaths`/`PresetPath`, and a preset whose `Techniques=` line names
   the entry points (e.g. `MartysMods_MXAO@MartysMods_MXAO.fx,SSR@qUINT_ssr.fx,...`). ReShade loads
   `PresetPath` at startup, so the whole stack can be brought up with no overlay interaction at all.
7. Capture: `ffmpeg -f lavfi -i ddagrab=output_idx=0:framerate=30 -vf "hwdownload,format=bgra"
   -frames:v 1 -update 1 out.png`, then crop to the window rect obtained from a **DPI-aware** process.

## Verification
- Gameplay, not just menus: NEW GAME -> opening -> on foot on Broadway St, 3840x2160 windowed,
  buildings/vehicles/pedestrians/HUD all present. This is the frame the visual work is judged against.
- RTX Remix probe: `bridge64.log` shows `Loaded D3D9 from .trex\d3d9.dll`,
  `Version of d3d9 loaded is DXVK`, `Server side D3D9 Device created successfully!`;
  `NvRemixBridge.exe` resident at ~3.9 GB with GPU active. So Remix **does** run this game.
- RTX Remix verdict: **runs, but not usable.** In the open world it captures the city geometry (7th St /
  Francisco St buildings are clearly present) yet renders no usable lighting or materials - surfaces are
  near-black or blown-out white - and **skinned characters are not captured at all**; in cutscenes only
  floating eyes remain, because the eyes are separate unskinned quads. `[RTX-Compatibility-Info] ...
  Falling back to rasterization` also appears, so the look is not consistent frame to frame. Killed on
  the plan's own criterion (skinned geometry unusable). Making it shippable would mean hand-authoring
  USD materials and lights per asset - a total conversion, not a graphics mod.
- Also observed for Remix: `Insert` did not open the overlay, and **alt-tabbing the game in Remix
  fullscreen crashes it** - plan on config-layer options and timed screenshots instead of the UI.
- ReShade 6.7 hooks dgVoodoo2 correctly (`Redirecting RegisterClassExA({ "DGD3D11ROOT" })`,
  `Redirecting CreateDXGIFactory1`, `D3D11CreateDevice -> D3D11CreateDeviceAndSwapChain`,
  `Using feature level b000`) and compiles the whole stack cleanly, but a usable frame through it was
  not obtained in this session.
- Not verified: whether depth is exposed to ReShade through dgVoodoo2's D3D11 swapchain (the open
  question the whole RTGI/SSAO/SSR stack depends on).

## Gotchas
1. **Black screen, one core spinning, "exit code 0".** With `d3d8to9` as `d3d8.dll`, the game reaches a
   `PeekMessage` loop and spins forever at ~1 core / 44 MB, zero GPU, zero I/O, never presenting.
   **Cause:** the engine's presentation path is broken against any *Microsoft* D3D9 runtime; Windows'
   own `SysWOW64\d3d8.dll` fails the same way, so this is not a d3d8to9 defect.
   **Fix:** dgVoodoo2 (D3D8 -> D3D11). First frame within a second.
2. **Instant AV `0xc0000005` at RVA `0x21D63B` on any 16:9 mode.** 640x480/800x600/1024x768 render fine;
   1280x720 and 1920x1080 die within a second. **Cause:** a 2004 4:3-only assumption - a setter does
   `mov eax,[esi]` on a pointer that a widescreen mode leaves null/garbage.
   **Fix:** ThirteenAG Widescreen Fix, which patches exactly this; its `ResX`/`ResY` also set the
   internal resolution.
3. **AV at `0xFFFFFFFF` on startup, before any frame.** **Cause:** a texture row-copy loop stores with
   `movaps [edx], xmm0` (4 x 16 bytes) into a lock pointer that modern drivers only guarantee 8-byte
   aligned -> `#GP(0)`, surfaced as an AV. **Fix:** patch the 4 `movaps` to `movups` (see build step 5).
   Do not bulk-patch every `movaps` in the binary - a 35,299-site sweep is what a naive attempt does.
4. **`Get-Process ....Modules` and `tasklist /m` lie about this process.** They report 7 modules for a
   WOW64 process that really has 87 loaded (`d3d8`, `d3d9`, `nvd3dum`, `dsound`, `binkw32` ...). Use a
   minidump + a module walk instead.
5. **Wrong crop rectangles at 4K.** PowerShell 5.1 is DPI-unaware, so `GetWindowRect` returns 1536x864
   for a real 3840x2160 window on a 250 % desktop, and every crop built from it is wrong.
   **Fix:** call `SetProcessDpiAwarenessContext(-4)` (fall back to `SetProcessDPIAware`) *before* any
   window API, then rects are physical pixels and line up with `ddagrab`.
6. **`PrintWindow`, `BitBlt`, window-DC GDI all return pure black** for this title, and
   Windows.Graphics.Capture times out. `ddagrab` works, but needs `hwdownload,format=bgra` or ffmpeg
   fails on a `d3d11 -> auto_scale` format error. The game changes the display mode, so grab the whole
   output and crop.
7. **`Insert` does not open the Remix overlay, and alt-tabbing the game in Remix fullscreen crashes it.**
   Plan around it: drive Remix from `rtx.conf`/`dxvk.conf`/`user.conf` option layers instead of the UI,
   and capture on a timer so the player never has to leave the window.
8. **The game vanishes with no crash record and the exe is gone from disk.** **Cause:** Windows Defender
   quarantines the patched exe as `Trojan:Win32/Bearfoos.A!ml` - an ML false positive on a binary whose
   only difference from stock is 4 patched bytes. It fires a few seconds after launch, so it looks like a
   silent quit. **Fix:** add a Defender exclusion for the lab folder
   (`Add-MpPreference -ExclusionPath <lab>`, elevated). Confirm with `Get-MpThreatDetection`, and
   re-verify the exe hash after restoring it.
9. **The original install gets modified even though the modded exe runs from a copy.**
   **Cause:** the lab's `Data`/`Movies`/`Docs` are directory junctions back to the install, and the game
   resolves its install root through them, so it rewrites `<original>\TrueCrime.ini` (both on start and
   on exit). **Fix:** before any asset work, replace the junctions with real copies or accept that the
   game owns that file. Sweep the install by mtime to check what else it touched.
10. **The game exits with `0x80070002` about 1.2 s after D3D init, before the menu, and nothing is
    logged.** **Cause:** the engine opens `HKLM\Software\Activision\True Crime` at startup and treats a
    missing key as fatal. This is documented nowhere (not even on PCGamingWiki) and repacks do not
    always create it. **Fix:** mirror the key under `HKCU` at runtime and duplicate the handle when the
    game's `HKLM` open fails - no admin needed. Once present the game creates its own values there
    (`Game_UnlockedExtras`, `Game_SandwichIcons`, `Renderer_Windowed`).
11. **Fatal exit before the menu on *some* controllers, fine with none attached.** The 2004 controller
    init enumerates `IDirectInput8A` game devices, identifies them by a product-name whitelist, then
    probes with `GetProperty` and treats **any negative `HRESULT` at that probe as fatal** (the
    identification step tolerates `0x80070002`; the probe does not). Modern pads (e.g. Razer
    `VID_3537`) return `0x80070002` there and the game dies. **Fix:** wrap `DirectInput8Create` (IAT
    hook), proxy the `IDirectInput8A` object, and make `EnumDevices` report **zero** devices for the
    game controller class. Keyboard and mouse are created directly and are unaffected; feed controllers
    through a separate XInput mod instead. When writing such a proxy: the object's first field must be a
    **pointer** to the vtable array - an inline array makes `call [vtable+slot]` jump to garbage.
12. **Patching the exe on disk gets it quarantined** (gotcha 8). The workaround that avoids the fight
    entirely: apply the `movaps`->`movups` patch **in memory at load time** from the `.asi`, so the
    on-disk exe stays byte-identical to stock and Defender has nothing to flag. Defer to another mod's
    identical fix when it is already installed (check for the file) so two patches do not fight.
13. **The game silently dies ~11 s in when its exe is not at the classic desktop-root lab path.**
    Sublime symptom: the mod log shows `CreateDevice failed (hr 0x8876086C)` x100 then
    `display 3840x2160@60 | pp 1536x864 ... windowed 0` before the process exits (`0x8876086C` is
    `D3DERR_INVALIDCALL`). **Cause:** the game picks **1536x864 = the desktop as seen by a
    DPI-unaware process** (3840 x 2160 at 250 % scaling) and then asks for an invalid exclusive
    fullscreen backbuffer. It only picks the real 3840x2160 when its exe path is the path it has
    always run from; rename or nest the lab and it breaks. **What does NOT fix it** (all tried): a
    DPI manifest beside the exe (the exe has no embedded one, so the external applies, yet the
    process still measures awareness = 0); inheriting awareness from the launching process;
    dgVoodoo's `DesktopResolution = 3840x2160`; and refreshing the game's own `InstallPath`
    registry value, though a mod should still keep that value fresh because the game writes it once
    at key-creation time and then goes stale on any folder move. **Working fix:** keep the lab at a
    path-free-of-nesting **junction** placed at the path the game expects, and launch through it
    (<desktop-root lab path>\TrueCrime.exe here). Diagnose this one from the mod's
    own log - `TrueCrimeDualSense.log` prints the CreateDevice parameters that name the cause.

## Assets
None yet, but the save/career layer is now known well enough to build one: `Saves\save*.bin` (3,600 B,
10 slots) is a flat profile dump whose mapping to the live object is `save offset = object offset - 0x380`
(see the memory map above), and the mission/lesson/unlock tables at `0x24..0x44`, `0x228..0x244`,
`0x650..0x778` are plain int arrays - a save editor is a data task, not an RE task. Textures still need
the runtime route (hash at `CreateTexture`/`SetTexture` -> DDS) because the city payload cannot be
repacked cheaply.

## Cost and time
Six sessions. 1: recon + the `movaps` crash. 2: the presentation bug, the 16:9 AV, dgVoodoo2.
3: first gameplay frame, RTX Remix verdict, ReShade staging. 4: boot blockers (registry key, gamepad
probe) fixed in one `.asi`, live monitor infrastructure. 5-8 (same day, iterative): health/ammo/karma
located and verified, the profile object identified, save format mapped, dead ends closed. The single
highest-leverage idea of the whole project: **diff two saves around one controlled in-game action** -
it named karma in one 30-second test that memory sweeps had failed to find across three sessions.

## Open questions
- Is a usable depth buffer exposed to ReShade through dgVoodoo2 (needed by RTGI/MXAO/SSR)?
- Do city textures arrive via `LockRect` (dumpable) or through a path that bypasses it?
- How many unique textures, at what sizes, within a 32-bit address space even after LAA?
- Where are the LOD/draw-distance constants, given that `Data\TrueCrime.ini` fog is only ~600 units?
- **Answered:** the `save*.bin` format (flat profile dump, mapping above); karma (`[0x6D9554]+0x3DC`);
  reserve ammo does not exist for any weapon (the pistol is infinite, pickups end at clip empty).
- **Still open:** the HUD badge number. It is not in the save as a balance (a badge flash does not move
  it, and it is spent directly on driving-school/mode entry), and `data+0x2F500` is a level counter, so
  it is either a derived display value or lives outside the profile object.
- **For the rebalance work (M3):** what thresholds does the engine apply to karma (`SetKarma` is called
  from script events, so the good/bad-cop rating logic is script-side or in the `.RES` data)?
- Weather state machine (which code state selects `[RainyDay]` in `Data\TrueCrime.ini`)?

