---
kind: game
title: 'BG3-style controller support for Underrail: stick movement, context interaction, menus, bars and combat via a Cecil-patched input layer'
game: Underrail
games_also: []
game_version: 1.3.1.2, Steam build 21973456 (underrail.exe sha256 c76248ff...daa8a7c)
platform: proton
engine: xna-fna
route: managed-patch
tools:
- ilspycmd 8.2
- Mono.Cecil 0.11.6
- .NET 8 SDK
- Pillow
anti_cheat: none (single-player, no integrity checks; Dotfuscator rename-only)
status: working
agents:
- Claude Code (claude-opus-5-5)
humans: []
date: '2026-10-04'
links: []
tags:
- controller
- gamepad
- xinput
- steam-deck
- xna
- dotfuscator
- cecil
- input-redirection
- pathfinding
- obfuscated-names
---
# BG3-style controller support for Underrail: stick movement, context interaction, menus, bars and combat via a Cecil-patched input layer

> A full gamepad layer for Underrail (XNA 4, .NET 4, x86, Dotfuscator-renamed) aimed at the Steam Deck:
> left-stick direct movement outside combat, nearest-object highlight + one-button interaction, a stick/D-pad
> cursor for every menu, L2/R2 bar navigation, console-style window switching, a stick cursor in turn-based
> combat, and an Options > Controller tab with a drawn DualSense schema. A Cecil installer injects one call
> into the game loop and redirects all mouse/keyboard polls into the mod. Play-tested in the real game on
> macOS through CrossOver with a DualSense; the Steam Deck run is not yet verified.

## Setup
- Game: Underrail **1.3.1.2**, Steam, build 21973456. `underrail.exe` is a 32-bit IL-only .NET Framework 4
  assembly (8.5 MB); XNA 4.0 comes from the GAC (installed by Steam's redist), SFML is only used for audio.
- Dev box: macOS, game in a CrossOver bottle. No Homebrew: .NET 8 SDK via `dotnet-install.sh` into
  `~/.dotnet`. `ilspycmd` latest needs a newer runtime: `dotnet tool install -g ilspycmd --version 8.2.0.7535`
  and run with `DOTNET_ROLL_FORWARD=Major`.
- Mod: C# `net40`, x86, references `underrail.exe` (always the clean `underrail.orig.exe`) plus
  `Microsoft.Xna.Framework{,.Game,.Graphics}.dll` from the bottle's `windows/Microsoft.NET/assembly/GAC_32`.
  `Microsoft.NETFramework.ReferenceAssemblies` makes `net40` build on macOS.
- Controller: XNA `GamePad.GetState` (XInput). Wine/CrossOver presents a DualSense as XInput; on the Deck use a
  Steam Input "Gamepad" layout (not "Keyboard (WASD) and Mouse").

## Route and why
`managed-patch`: decompile with ILSpy, write a separate mod DLL compiled against the game exe, and patch the
exe with Mono.Cecil. No loader exists for Underrail; BepInEx has no supported path for plain .NET Framework XNA
games; Harmony would still need a bootstrap. Two patches cover everything:
1. `call PadMod.Tick(this)` at the top of `tb.Update` (the `Game` subclass's Update).
2. Every parameterless `Mouse.GetState()` / `Keyboard.GetState()` call in the exe (7 + 23 sites) retargeted to
   the mod's `VirtualInput.GetMouse()/GetKeyboard()`, which return the real state merged with controller-made
   buttons/keys. The GUI then sees ordinary clicks, drags, double-clicks and key presses everywhere.
The patched exe is never distributed: the release ships an installer that verifies the exe hash, keeps
`underrail.orig.exe`, and patches the player's own copy.

## How the game works (what we had to learn)
Names are Dotfuscator-renamed but stable per build; string literals are plain (no string encryption), no
tamper checks, exe not strong-named.
- **Loop/input:** `tb : Game`; `tb.Update` polls Mouse/Keyboard into a per-frame context `e6d`; Draw polls
  separately (latch virtual state per frame). GUI manager `bso` (service `d1a`/`bcm`): `aau()` root screen,
  `aa7()` focus, `aa8()` control under mouse, `aam()` text capture. Controls derive from `euz`
  (`Controls`, `Visible`, `Enabled`, `Ghost`, `IsShadow`, `at()` absolute pos, `Size` (`esj`)); clickables
  from `cao`. Clicks fire on release if the press started on the same control; double-click = 350 ms.
- **Player and movement:** player data `bpo.GetService<cnk>().aqu().v()` (don't use `ces.c()`, it throws
  at the main menu); entity `c5x`, `Location` in tile units. Move = trekker aspect `ale.a(tile, stopDist,
  retries, delayMs)` → action queue → path request in a time-sliced path processor. Tile lookup
  `aud.b(x,y)` (null outside). Vanilla click walkability: `tile.a(player.a().d)` (tile flags vs movement
  mask). Isometric 2:1 diamond tiles: screen right = tile (+1,-1), screen down = (+1,+1).
- **Modes:** turn-based combat `dz6.e()`; dialog/busy via the `ps` service (`dka`): `alc()`, `alg()`.
  In-game windows are `LocaleSubInterfaceController<,>` fields on `dka`: `j()` open, plus open/close
  methods the hotkey handler calls (`alv/alw` inventory, `al3/z` character, `al8/al9` map, ...).
  Pending ability target: `bpo.GetService<bi3>().aij() != null`.
- **Interaction:** `ps.aln(entity)` returns the command a left-click would issue (talk, use, disarm, attack);
  `cmd.io() && cmd.a(ent)` then `cmd.f1(cnk.aqw())` runs it exactly like a click. Right-click options:
  usable aspect `bim.jz()`; menu via `bc.a(screen, screen.n(), bim, point)`.
- **Picking:** per-pixel over last frame's sprite list (`a7m` private `List<cy5>`); the private
  `a7m.a(int x, int y, out bool)` is the real hover pick and stops at fade-able walls in front.
- **HUD:** bottom bar `ci3.n()` (`ek7`): action slots `cqn`, weapons `tt`, shield `efq/dvx`, belt `boq/dho`.
  Window buttons `ci3.m()` (`e60`, `cep` buttons). Speed/zoom are `doz` buttons on `ci3` (first four
  `doz` fields: speed up, slow down, zoom out, zoom in); clicking them via `euz.a(eoo.b)` runs the game's
  own handlers. Camera `an9()` (`c5m`) has 8 scroll methods used by edge scrolling; playfield settings
  `dnx` toggle mouse edge scrolling.
- **UI building:** options screen `t1` uses a tab control `dpg` (`n()` tab list of `cvh` pages,
  `b(esj)` tab size); `bg1` draws a `Func<Texture2D>`; `bnr.a(...)` is a one-call message box.

## Build steps
1. Decompile outside the repo: `ilspycmd -p -o ~/underrail-decomp underrail.exe`.
2. Build the mod DLL (`net40`, x86) against `underrail.orig.exe` + XNA GAC assemblies.
3. Patcher/installer (net8, Mono.Cecil): back up to `underrail.orig.exe`, verify sha256, insert
   `ldarg.0; call PadMod.Tick` before the first instruction of `tb.Update`, retarget the GetState calls,
   write `underrail.exe`. Always patch from the backup so reruns are idempotent; detect a Steam update by
   "current exe has no AssemblyRef to the mod but differs from the backup" and drop the stale backup.
4. Release: `dotnet publish -r win-x64|linux-x64 --self-contained -p:PublishSingleFile=true
   -p:PublishTrimmed=true -p:TrimMode=partial` (11 MB; full trimming isn't needed, partial keeps Cecil
   working) zipped with the DLL and assets; `um publish check` passes.

## Verification
- Oracles: a mod log (`UnderrailPad.log`) with mode transitions, each move order (`moved`, `offLine`,
  probed tiles ok/x), each selection (entity type + command), bar slot lists, and errors; a mouse-click
  calibration logger proved `Location` == tile index; a dry-run patch on a copied folder diffed with Cecil
  (types/methods/resources identical) and PE `.rsrc` intact; the installer was exercised end-to-end
  (install, rerun, simulated game update, uninstall) and its output is byte-identical to the dev patch.
- Real-game playtests on macOS/CrossOver with a DualSense across ~15 iterations: walking, interaction,
  menus, dialogue, loot, save/load, bars, windows, combat cursor.
- NOT verified: the Steam Deck/Proton run, native Windows, the Linux installer binary on Linux (the same
  code was run as an osx-arm64 build), vehicles, very long sessions, GOG (different exe; refused).

## Gotchas
1. **Mod dies at the main menu.** `ces.c()` throws when no game is loaded and the error budget ran out in a
   second. **Fix:** walk `bpo.GetService<cnk>()?.aqu()?.v()` with null checks; isolate optional features.
2. **Reflection by field name finds nothing.** ILSpy shows `m_h` etc. when a field collides with a method
   name; the IL name is `h`. **Fix:** look fields up by type (each window controller type is unique).
3. **C# can't bind obfuscated members.** A field and a method share a name (`c5x.k`, `esj.c/d`, `dnn.d`),
   so the compiler picks the method group. **Fix:** use helpers (`esj.b()` returns size as Vector2),
   `GetAspect<T>()`, or reflection by type.
4. **Stick walking stutters.** Each re-issued move cancels the path and the time-sliced path processor answers
   a frame or more later; the character idles meanwhile. **Fix:** after `ale.a(...)` call
   `Playfield.PathProcessor.a()` (drains the queue synchronously; the game does this before saving).
5. **Most directions "blocked".** `ale.a(ak1)` is not the click walkability test. **Fix:** use
   `tile.a(player.a().d)` (what the move cursor uses).
6. **Character drifts to neighbouring lines / wrong angle.** Re-aiming from the current position accumulates
   grid-path error. **Fix:** lock a line per stick direction (anchor + direction, keep under ~12° wobble),
   aim 3 tiles ahead along it, re-steer every ~250 ms.
7. **Releasing the stick walks back a tile.** Stopping at round(position) can be behind. **Fix:** stop on the
   nearest walkable tile not behind the walking direction.
8. **Doors only highlight with the Highlight key.** The hover picker walks sprites front-to-back and a
   fade-able wall sprite in front ends the pick with nothing. **Fix:** choose cursor pixels with the game's
   own pick method (`a7m.a(int,int,out bool)` via reflection) so the door really is hovered; run the
   interaction command directly so even fully hidden doors work.
9. **Square moves the camera.** Right-click on an object without options selects it (camera focus).
   **Fix:** only open `bim.jz()` options when there are any.
10. **Context menus not detected as menus.** They are plain controls added to the root (`exj`/`bys`), not
    modals. **Fix:** search the root for visible `exj`/`bys`.
11. **"Real mouse moved" false positives under Wine.** `Mouse.SetPosition` reads back a pixel off.
    **Fix:** 3 px tolerance.
12. **Stick cursor scrolls the map at screen edges.** **Fix:** turn off `dnx` mouse edge scrolling while a pad
    is connected; restore on disconnect.
13. **D-pad up/left re-snaps to the same button.** Snap points are nudged down-right of centre, so the current
    button counts as "up-left". **Fix:** skip the control under the cursor.
14. **Speed/zoom mapping.** `ci3` has 5 `doz` fields; the first four (declaration order) are speed up, slow
    down, zoom out, zoom in.
15. **Single-press loot/save-load.** Items and save rows act on double-click. **Fix:** a scripted
    down/up/down/up over four Update frames (well inside 350 ms) when the hovered control is a `cqy` inside
    the loot window `c15` or a save row `afg`.
16. **A custom overlay caused graphical artifacts** during gameplay (an `ec9` frame + ghost label added to the
    game screen root). Cause not isolated; removed the overlay. Help lives in an Options tab instead.
17. **Loaded PNG has dark fringes.** XNA blends premultiplied alpha; `Texture2D.FromStream` doesn't
    premultiply. **Fix:** premultiply the pixel data once after loading.
18. **Patched exe is ~390 KB smaller.** Cecil compacts heaps; type/method counts, resources and `.rsrc`
    are identical. Not a problem.
19. **Repo tooling on macOS system Python 3.9.** `um kb new/index` fail (`write_text(newline=)`, PEP 604
    types at runtime in places); `um publish check` works. Use Python 3.10+ (uv) for the kb commands.

## Assets
The DualSense schema is vector-drawn with Pillow (`Tools/make_schema.py` in the mod source: Bézier body
outline, glow pass, leader-line callouts laid out per column) rather than AI-generated, so every callout lands
on its button. Style: thin amber (the game's accent is `(174, 87, 0)`) on transparent, DIN/Avenir Next
Condensed.

## Cost and time
One long session (~3 hours wall clock) with ~15 play-test iterations; research delegated to a sub-agent that
read the decompile and answered targeted questions (movement, input, UI, picking, windows).

## Open questions
- Steam Deck/Proton verification (XInput through Steam Input, performance of per-frame reflection).
- Root cause of the overlay artifacts (draw order vs the game's render targets?).
- Native combat polish: snapping the combat cursor to enemies/tiles, End Turn/target cycling on the D-pad.
- A version-independent build: resolve the obfuscated names by signature/strings at install time so game
  updates don't need a mod release.
