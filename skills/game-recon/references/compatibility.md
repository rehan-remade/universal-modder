# Compatibility: can this machine run the game?

`SKILL.md` step 1b sends you here when the game isn't native to the host (a Windows-only game on macOS or Linux,
an x64 game on an ARM CPU), or when a game that should run here won't start. A Windows game on Windows, or on
Windows from WSL, is native: you don't need this page. Layers and their versions move every few months, so take
versions from the field notes and the per-game reports below, not from here.

## 1. Compare both sides
**Host:** OS and build, CPU architecture, GPU, driver and graphics API. An unchecked host is the usual reason a
note's result doesn't repeat. `um scan` starts its report with `host:` (OS and version, CPU named like the exes'
`[x64]`, WSL noted; `host` in `--json`), which covers the first two. The GPU, driver and graphics API are still by
hand:
- macOS: `system_profiler SPDisplaysDataType` (chip and Metal support); `sw_vers` and `uname -m` for the rest.
- Linux: `vulkaninfo --summary` (GPU, driver, Vulkan version); `cat /etc/os-release` and `uname -m` for the rest.
- Windows: `dxdiag /t dxdiag.txt`; its "Feature Levels" line lists the Direct3D levels the GPU supports.

**Game:**
- `um scan` already gives each exe's CPU (`[x64]`, `[x86]` is 32-bit, `[arm64]`; `executables.<exe>.arch` in
  `--json`), the engine and the anti-cheat in the folder. A game inside a Wine prefix or a CrossOver bottle isn't
  in `um scan --list`: pass its folder.
- Graphics API: the store page or PCGamingWiki's API table, then the engine's own log, which names the API it
  picked (Unity `-logFile <path>`, Godot `--log-file <path>`), then the exe's imports:
  `objdump -p game.exe | grep "DLL Name"` (GNU objdump on x86-64 Linux, `x86_64-w64-mingw32-objdump` from
  mingw-w64 on macOS, `dumpbin /dependents` on Windows). Look for `d3d9`, `d3d11`, `d3d12`, `dxgi`, `vulkan-1`,
  `opengl32`. A protected exe, or one that only starts an engine DLL, may import none of them: use the log.
- Steam: `steam_api.dll` or `steam_api64.dll` in the folder usually means the game wants a running, logged-in
  Steam client.

## 2. Search before you research
Notes are ranked on title, tags and body, and the gotchas are in the body, so the situation, the layer or an
exact error message all find them:
```bash
um kb search "windows game on mac"      # on Linux the layer's name ranks better: "proton", "wine"
um kb search "directx apple silicon"    # spell the API out: "directx 11" hits where "dx11" misses
um kb search "<engine> <host OS>"       # "unity macos", "unreal wine"
um kb search "SteamAPI_Init() failed"   # an error message, copied exactly
```
- **A note for your host, engine and layer:** copy its setup and versions, run its verification, and only then
  deviate. What it lists as not verified is what you probe. A note on another game with the same engine and layer
  still helps: gotchas transfer.
- **Per-game reports from players**, with versions and dates:
  - Linux and Proton: ProtonDB (`https://www.protondb.com/app/<appid>`; the summary is JSON at
    `https://www.protondb.com/api/v1/reports/summaries/<appid>.json`, an unofficial endpoint) and the store
    page's Steam Deck rating.
  - Wine: WineHQ AppDB (`https://appdb.winehq.org`).
  - macOS: CodeWeavers' compatibility database (`https://www.codeweavers.com/compatibility`) and AppleGamingWiki.
  - Anti-cheat under Linux, Wine and Proton: `https://areweanticheatyet.com`.

## 3. Pick a route
Take the first rung that reaches the user's idea.
1. **A native build or port** for the host (the store page, an open-source port). Nothing to translate.
2. **A compatibility layer.** Name the layer for each concern, because they fail independently:
   - **CPU** (x86 code on ARM): Rosetta 2 on macOS (general-purpose through macOS 27, Apple says, then a subset
     for older games); Windows' own emulator, Prism, on Windows on Arm; FEX or Box64 on ARM Linux (Asahi Linux
     runs games with FEX inside a small `muvm` VM).
   - **Windows API:** Wine and what is built on it: Proton (Valve's, run by the Linux Steam client), CrossOver
     (CodeWeavers, paid, macOS and Linux), Apple's Game Porting Toolkit evaluation environment, wrappers such as
     Sikarugir.
   - **Graphics API:** on Linux, DXVK (Direct3D 8 to 11) and vkd3d-proton (Direct3D 12) over Vulkan. On macOS,
     D3DMetal (Apple, closed source, Direct3D 11 and 12), DXMT (open source, Direct3D 10 and 11) or DXVK; Vulkan
     goes through MoltenVK, which Khronos has deprecated in favour of KosmicKrisp on Apple Silicon, so check which
     one the layer ships. Wine's own wined3d is the fallback everywhere.
   - **Launcher:** under Proton the Linux Steam client serves the game. Under plain Wine or CrossOver, Windows
     Steam has to run in the **same** prefix (bottle) as the game.
3. **A virtual machine.** Real Windows, but the virtual GPU caps the Direct3D level, and on an ARM host it is
   Windows on Arm, so x64 games run under Prism anyway. Check first that the agent can still read the game's
   files, drive it and take screenshots from outside.
4. **Cloud streaming** runs the game elsewhere: no local files, nothing to mod.
5. **None works:** say so, and offer another game, an official tool, or a data-only or offline route.

## 4. Anti-cheat
A stop sign for injection (`skills/mod-any-game/references/safety.md`), and often for the layer too. Easy
Anti-Cheat (under Wine or Proton) and BattlEye (under Proton) run only for games whose developer turned it on, so
check the game on areweanticheatyet.com. Prism emulates user-mode code only, so on Windows on Arm a kernel-mode
anti-cheat needs an Arm64 driver from its vendor. Never bypass one; an official offline mode that ships without it
is the route (safety.md).

## 5. Same OS, still incompatible
A note's result holds for the versions it recorded. If yours differ on any of these, treat it as a hint and probe.
- **OS build and layer version.** Either can break a setup that worked. Record both before and after an update,
  change one thing at a time, and search the notes before changing a layer's version.
- **GPU and driver.** A Direct3D feature level, shader model or Vulkan version the GPU or driver lacks makes the
  game refuse to start, crash at load or fall back to another API. Compare `dxdiag` or the engine log with the
  store page's requirements. DXVK and vkd3d-proton state their minimum Vulkan version and drivers in their README
  and wiki, and the minimum rises with major versions.
- **Runtimes.** A missing .NET, Visual C++ or DirectX redistributable looks like a crash or a prerequisites
  dialog. Check which one the game wants before blaming the layer.
- **CPU features.** Rosetta 2 translates AVX and AVX2 but not AVX-512. Prism translates AVX and AVX2 for x64
  apps since an update to Windows 11 24H2. A game that needs an instruction set the translator lacks won't start.
- **The game's own API switch.** Many engines can be told to use an API the layer handles better, when the game
  ships it: Unity `-force-d3d11` or `-force-vulkan`, Godot `--rendering-driver <name>`, Unreal `-dx11` or `-dx12`.

## 6. Probe, then mod
- **Probe the layer on something tiny first:** a minimal graphics test that creates a device, draws and reads the
  pixels back (no screenshot permission needed), a hello-world exe, or the launcher alone. Read its log, not the
  clock. On a failure, search the notes with the exact error text, then the layer's issue tracker and release
  notes, before the forums, and write down the date and version of anything taken from the web.
- **Loaders that proxy a system DLL** (BepInEx's `winhttp`, MelonLoader's `version`, ASI loaders' `dinput8`)
  need a native-first override under Wine: `WINEDLLOVERRIDES="winhttp=n,b" %command%` in the Steam launch options
  under Proton, the prefix's DLL overrides elsewhere. The engine playbooks name the DLL.
- **Saves under Proton** live in the prefix, `steamapps/compatdata/<appid>/pfx/drive_c/users/steamuser/`
  (`AppData`, `Documents`), where `um scan`'s save hints don't look. Back that folder up with `um backup`.
- **Driving and screenshots:** `um win` works on Windows and WSL only; see the **game-automation** skill's
  "Linux and macOS" section.
- **Record** the `Host / compat` line of `MODDING_PLAN.md` (`SKILL.md` step 4) with exact versions. What the notes
  lacked (a version that works, a gotcha with its cause) goes into a field note (**share-field-notes**).

## Sources (checked 2026-10-16)
- Rosetta: https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment
- Prism: https://learn.microsoft.com/windows/arm/apps-on-arm-x86-emulation and (AVX, AVX2)
  https://techcommunity.microsoft.com/blog/windowsosplatform/-/4475631
- Easy Anti-Cheat under Wine and Proton:
  https://onlineservices.epicgames.com/en-US/news/epic-online-services-launches-anti-cheat-support-for-linux-mac-and-steam-deck
- CrossOver's graphics backends: https://codeweavers.helpjuice.com/en_US/advanced-settings-in-crossover-mac-26
- The READMEs of DXVK, vkd3d-proton, DXMT (3Shain/dxmt), MoltenVK, FEX, Box64 and Proton (its `proton` script
  for the prefix layout); Asahi Linux: https://asahilinux.org/2024/10/aaa-gaming-on-asahi-linux/
