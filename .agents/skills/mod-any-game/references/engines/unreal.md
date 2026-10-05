# Unreal Engine (4 / 5)

**Identify.** `<Project>/Binaries/Win64/<Project>-Win64-Shipping.exe` and `<Project>/Content/Paks/*.pak`.
- **UE 4.26+ and UE5:** assets live in IoStore `.utoc`/`.ucas` next to a small `.pak`.
- **Engine version:** `um scan` greps the exe for `++UE5+Release-5.x`.
- **Saves:** `%LOCALAPPDATA%\<Project>\Saved\SaveGames`. Config is in `...\Saved\Config\Windows\*.ini`, and
  many tweaks are ini-only (`Engine.ini`: `[SystemSettings]` cvars).

## Route 1: UE4SS (scripting and hooks, no engine recompile)
RE-UE4SS (github.com/UE4SS-RE/RE-UE4SS) injects into the game. Put its `dwmapi.dll` (newer builds) or
`xinput1_3.dll` proxy plus the `ue4ss/` folder next to the shipping exe.

**What you get:**
- **Lua mods** (`ue4ss/Mods/<Mod>/Scripts/main.lua`, enabled in `mods.txt`):
  - `RegisterHook("/Script/Engine.PlayerController:ClientRestart", fn)`
  - `NotifyOnNewObject`
  - `FindFirstOf("PlayerCharacter")`
  - read and write any UProperty, call UFunctions
  - `ExecuteInGameThread`
- **C++ mods** for heavier work.
- **The Live View** (object dumper/inspector, in the GUI console): find the class and property you need.
- **SDK/header generator:** dumps a UHT-compatible SDK. Dumper-7 is an alternative.
- **Blueprint mods:** loads `LogicMod` blueprint paks from `Content/Paks/LogicMods`.

Check the game's UE4SS compatibility (custom engine forks may need a UE4SS config override for AOBs), and
read the UE4SS example mods before prompting for features. Many are already there.

## Route 2: pak mods (asset and blueprint replacement)
- **Browse** with FModel (CUE4Parse). It needs the right UE version and the AES key if paks are encrypted.
  Keys are public for most games; AESDumpster extracts them from the exe.
- **Edit `.uasset`** with UAssetGUI / UAssetAPI (JSON round trip), or cook replacements in a matching UE
  editor version with the same project name and paths.
- **Pack** with repak (`repak pack --version V11 mymod_P/`) or retoc for IoStore. Name it `*_P.pak` so it
  outranks originals, and put it in `Content/Paks/~mods/`.
- **New content (meshes, materials, BPs):** cook in the UE editor of the same version (Epic launcher / source
  build), then pak only your cooked files. The mount point and paths must mirror the game's (`/Game/...`).

## Route 3: VR / camera / engine tweaks
- UEVR (praydog) injects stereo VR into most UE4/UE5 games, with profiles per game.
- Console unlockers (Universal Unreal Console Unlocker, or UE4SS) enable `stat fps`, `slomo`, `r.*` cvars.
  They are great for showcase shots: freecam, slow motion, hide HUD.

## Read the game
- The UE4SS dump, or Dumper-7 → class/property/function names with offsets.
- Ghidra/IDA on the shipping exe for native gameplay code. Match UE source (github.com/EpicGames, with
  account linking) to name engine functions.
- `fmodel-mcp` lets an agent browse assets.

## Pitfalls
- **Anti-cheat:** EAC/BattlEye titles (Fortnite and most online UE games) → no.
- **Version mismatch:** paks cooked for the wrong UE version crash on mount. Blueprint mods break on game
  updates.
- **Signatures:** games with `.sig` files verify paks. Community bypasses exist only for specific
  single-player games; don't bypass them where it's used as anti-tamper for online play.
- UE5 games that stream everything through IoStore need retoc, not repak.
