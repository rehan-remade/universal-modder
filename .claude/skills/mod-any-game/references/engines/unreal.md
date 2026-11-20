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

## Older Unreal: UE1 and UE2 (UnrealScript games: Unreal, UT99, UT2004, Deus Ex, Splinter Cell...)
These ship their game logic as UnrealScript bytecode in `System/*.u` and have an official mod route: write your
own package of classes that extend the game's.
- **Identify:** `System/<Game>.exe` with `Core.u`, `Engine.u` and `*.int` / `*.ini` beside it. Check
  `System/Build.ini` (OldUnreal patches) and the exe's PE machine (UT2004 3374 and UT99 469 are maintained by
  OldUnreal, with 64-bit builds).
- **Read the game:** `ucc batchexport <Pkg>.u class .uc <outdir>` exports a package's script. Keep it outside
  your repo; read it, don't copy it.
- **Build:** put your package's `Classes/*.uc` in `<Game>/<Pkg>/Classes/`, add `EditPackages=<Pkg>` (after the
  game's own packages) and run `ucc make`. A temporary ini (`ucc make -ini=Build.ini -userini=BuildUser.ini`) keeps
  the player's ini stock. Packages compile against the installed patch's script: build releases against what
  players have.
- **Entry points:** a mutator (`?Mutator=Pkg.Class` on the map URL, or the menus), a game type
  (`?Game=`), a replacement PlayerController/Pawn chosen by either, and the console class
  (`[Engine.Engine] Console=`), which is the only hook alive in the main menus. Default values live in
  `defaultproperties`; `config` variables are saved in the package's ini (`class X config(MyPkg)`).
- **Testing without input:** an exec chain read from your ini and run a command every few frames (ending in
  `exit`), plus log lines, gives a repeatable test; `-log` writes `System/<Game>.log` (flushed on exit).
- **Native side:** no headers for the 64-bit OldUnreal builds, so prefer UnrealScript plus a proxy DLL (e.g.
  `d3d9.dll`) over native packages. `IpDrv.UdpLink` on 127.0.0.1 talks to an external process.
- **Pitfalls:** `set <Class> <var>` on a `globalconfig` variable writes the ini at once; console execs with
  several float parameters may only receive the first (take a string and split it); `UdpLink.ReadText` can append
  leftovers of an earlier, longer datagram. Field note: `games/unreal-tournament-2004/`.
