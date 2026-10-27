---
kind: game
title: "Film-style pistol reloads, a JSON QA bridge and physics magazines through a native ASI"
game: "Tomb Raider: Legend"
games_also: []
game_version: "Steam PC build, trl.exe MD5 bd846c8fb3223e53bee022bb307b21bc (SteamStub-wrapped, image base 0x400000)"
platform: windows
engine: unknown
route: native-hook
tools: ["Ultimate ASI Loader (as binkw32.dll, from the TR7-Menu-Hook 2.5 zip)", "TR7-Menu-Hook 2.5 (mods folder)", "MinHook 1.3.4", "MSVC 19.51 x86 (CMake 4.4.3 + Ninja 1.12.1)", "capstone 5.0.7 + pefile 2024.8.26", "tr7.pdb (types only)", "cdcEditor 0.1.1 (Blender 5.2.1)", "ffmpeg 9.0.2 gfxcapture", "um win/qa"]
anti_cheat: "none (single-player; Steam DRM is a SteamStub wrapper, left untouched: everything is runtime hooks)"
status: working
agents: ["Claude Code (Fable 5.1)"]
humans: ["skurtyyskirts"]
date: 2026-10-09
links: ["https://github.com/TheIndra55/TRLAU-menu-hook", "https://github.com/ThirteenAG/Ultimate-ASI-Loader", "https://github.com/TsudaKageyu/minhook", "https://github.com/Raq1/cdcEditor"]
tags: ["animation", "reload", "native-hook", "qa-bridge", "physics", "weapons", "cdc-engine", "d3d9"]
---

# Film-style pistol reloads, a JSON QA bridge and physics magazines through a native ASI

Tomb Raider: Legend (PC, Steam) was modded with a C++ ASI (MinHook inline hooks, no on-disk exe edits) plus
replacement `.drm` files served from a `mods\` folder. (`.drm` is the cdc engine's data container for models,
animations and levels, not copy protection.) The mod adds new pistol models with extra rigid segments,
re-authored and newly added reload animations hosted on the weapon objects, a reload selector, pistol
slide/magazine/hammer motion, a slide-lock release mechanic, dropped magazines simulated by the mod, and a
JSON-lines QA bridge that lets an agent read game state and drive the game. The bridge, the reload selector and
the slide/magazine FX run in the real game (logs and screenshots). The animation variants, the magazine physics
and the slide lock ran in game the next morning: every variant played with its own animation id, the dropped
magazines fell, bounced and slept on the engine's own collision meshes (215 line-probe hits, no fallbacks), the
backpack tree deployed under the pack, and the slide lock engaged after every empty reload.

## Setup
- OS: Windows 11 Home 25H2 (build 26200), x64.
- Steam build of trl.exe (MD5 above). The `.text` section on disk is plain, so capstone disassembly of the file works;
  the Steam wrapper only means "never edit the exe".
- Loader: Ultimate ASI Loader renamed `binkw32.dll` (the original Bink DLL kept as `binkw32Hooked.dll`), because
  input is DirectInput8 over COM (a `dinput8.dll` proxy is never loaded) and `binkw32.dll` is a static import. The
  loader used is the copy shipped in `TR7-Menu-Hook.zip` from TheIndra55's TRLAU-menu-hook v2.5 release; its version
  resource only says 1.0.0.0, so identify it by hash (sha1 `9c349fc1c0d9bb721f1d28e6c77dee08f1a32abe`).
  TR7-Menu-Hook v2.5 (`TR7-Menu-Hook.asi`, sha1 `bcc67ed1642f32ff07da91313d42b0dcd7f7d668`) serves `pc-w\X.drm`
  from `<game>\mods\X.drm` by hooking archive init.
- That loader carries built-in Bink DLLs, so overwriting the game's `binkw32.dll` with it (the menu hook's own install)
  needs no `binkw32Hooked.dll`. A release can therefore be a pure drag-and-drop folder that never ships the game's Bink
  DLL; see [film-outfit-pack-drm-rebuild-idles-release.md](film-outfit-pack-drm-rebuild-idles-release.md).
- tr7.pdb (from a different build) gives struct layouts only; every address was re-derived from this exe and is
  checked at startup against byte signatures ("sites"), with the mod refusing to install on a mismatch.
- Tooling:
  - MinHook v1.3.4 (commit `c3fcafd`), vendored. Master had rewritten its disassembler, so the tag was used.
  - MSVC 19.51 (toolset 14.51.36231, x64-hosted x86), CMake 4.4.3 + Ninja 1.12.1, static CRT, `/Brepro` for
    deterministic binaries.
  - A self-check executable that maps the exe at its preferred base and runs the hook logic against fake engine
    globals.
  - capstone 5.0.7 + pefile 2024.8.26 (`uv run --with pefile --with capstone`) for the disassembly.
  - Blender 5.2.1 + cdcEditor 0.1.1 (commit `5f2d5ab`) for DRM models and animations, and our own Python codec for
    animation sections and event lists.
  - ffmpeg 9.0.2 (gyan.dev full build, `gfxcapture` input) for recordings.

## Route and why
Native hooks. The engine is native x86 with no scripting layer for the player's weapon logic; the community loader
only swaps files. Data-only edits could replace animations and models but cannot select among reload variants, drive
new segments, or add input handling, so a small ASI with proof-checked hooks was the cheapest route that reaches
the idea. Decompiling the whole game was never needed: eight hooked functions and ~170 proof sites cover it.

## How the game works (what we had to learn)
- **Reload state machine.** `playerCheckWeaponReload` enters inventory state 10 (only caller of
  `playerInvSetState(10)`), which plays the weapon object's AnimBlend named by `invProp.iPlayerReloadAnim` on
  Lara's layer 1 through `razRequestVAnimCharacterSwitch(player, blend, host, 1, -1, 0)`. The blend index is read
  once, unchecked, so swapping that one byte around the call selects a different hosted blend; the end of the
  reload is driven by the layer's DONE alarm, not by which blend played. Anim event 51 (type-2 player event)
  refills both clips mid-animation (`playerDoWeaponReload`), and a flag bit prevents the end-of-anim refill from
  running twice. Vanilla reload blends never carry event 51; the stock reload refills at the end.
- **Hosted animations.** Weapon objects host Lara's weapon animations: `AnimBlend` entries point into the host's
  `animList`, whose ids index one global resident table (first loaded copy of an id wins, 1,024 slots). Animation
  sections are keyed at 30 keys/s (timePerKey 100, 3,000 units per second); rotations are axis-angle vectors;
  LINEAR tracks must cover the whole animation. A new hosted animation = a new section id, an `animList` entry, an
  event list in its own DTP section (ids below 0x8000, global), and an AnimBlend table copied with one more entry.
- **Layer 1 bone set.** The weapon overlay drives segments 2..99 only; pelvis (1) and legs (100..108) stay with
  locomotion. Weight shift in a reload therefore has to be faked from the spine.
- **Segment matrices are world matrices.** `G2Instance_BuildTransforms` fills a double-buffered pool of per-segment
  world matrices; the NextGen draw and shadow passes read them as-is, and visibility uses a box over all segments
  rebuilt every frame, so extra rigid segments of a model can be placed anywhere in the world by rewriting their
  matrices after the build (that is how the backpack magazine tree, belt carrier magazines and a 16-entry pool of
  dropped magazines ride on the pistol model). Shadow casters still use the model's static sphere.
- **Terrain query.** `MULTIBODY_LineProbe(flags, start, end, result, exclude)` (cdecl, caller pops 0x14) probes the
  loaded collision meshes with flags = 3 and returns hit position and normal; start/end must be 16-byte aligned, it
  must not run with a NULL exclude while no player exists, and the multibody system global can be NULL between
  levels. Engine gravity is 3 units per frame^2 scaled by `timeMult` (1.0 per 1/30 s), about 2,700 units/s^2.
- **Mini-instances** (a 160-slot pool of lightweight engine instances, `MINIINSTANCE_BirthObjectNoParent`) are the
  engine's own host for debris and would give per-object culling and relocation; an unowned instance of a weapon
  object instead turns into a dropped rigid-body gun (family 0x27 installs the RBWEAPON behaviour), so never birth
  weapon-family instances for props.
- **Fire input.** `playerHandleWeaponsFire` reads the fire action's pressed bit (0x10) from the input mapper's
  `ActionResult` array inside the same call; a press can be consumed by clearing that bit in a pre-hook (the mapper
  re-derives the bits next frame), which is cleaner than forcing `bCanAttack`, a byte with 44 writers.
- **Outfits and copies.** Every outfit is a whole player DRM bound by name; chapters force outfits; most cutscenes
  animate the live player (so the gameplay DRM shows in them); texture ids are global and only 64 are unused, so
  new art needs fresh ids and byte-identical sections wherever an id is shared.

## Build steps
1. Back up first, then install the loader and menu hook:
   - Saves live in `<Documents>\Tomb Raider - Legend\` (`autosave.dat` and `Saved Games\`):
     `um backup create "$env:USERPROFILE\Documents\Tomb Raider - Legend" --name trl-saves` (PowerShell).
   - Settings live in `HKCU\Software\Crystal Dynamics\Tomb Raider: Legend` (subkeys `Graphics`, which holds
     `FullscreenModeID` and the resolution, and `Input`):
     `reg export "HKCU\Software\Crystal Dynamics\Tomb Raider: Legend" trl-registry.reg /y`
     (restore with `reg import trl-registry.reg`).
   - Keep the original `binkw32.dll` before the loader replaces it.
2. Build the ASI (`cmake` + ninja via `build.bat clean check`): the self-check must print all sites holding the
   vanilla bytes before anything is deployed.
3. Build models and animations into copies of the vanilla DRMs (cdcEditor exports, our splice/add tools), verify by
   re-parsing (only the intended sections change, byte for byte), re-import with cdcEditor.
4. Deploy: the ASI and ini next to trl.exe, DRMs into `mods\`; keep a pre-deploy copy of everything replaced.
5. QA: ini `[Test] Windowed=1 Bridge=1`, launch, then drive the bridge (`ping`, `boot`, `state`, `cam orbit`,
   `hold lock`, `outfit <name>` to reload a player DRM live) and screenshot with `um win shot`.

## Verification
- Static: every hooked prologue and proof site compared with the exe on disk; MinHook trampolines decoded; detours
  exercised in a self-check that maps the exe at its real base and fakes the engine globals (446 checks at the last
  count); a fake-host exe runs the startup path and the bridge end to end.
- In game (0.3.0): the bridge's 13 protocol checks, boot to gameplay, camera orbit and turntable screenshots, HUD
  and timescale overrides, `outfit` re-switch in gameplay, held actions and axes; the reload selector's log lines
  matched the animations seen in the user's recording; a 24k-vertex player model (vanilla is 15k) rendered.
- In game (0.5.0): the six reload variants (forced through the bridge) each entered the reload state with their own
  animation id; `MULTIBODY_LineProbe(3, ...)` returned real floor hits for every dropped magazine (12 asleep on the
  ground after 45 s, none on the fallback plane); the tree, carriers and pool segments drew from the pistol model's
  extra segments; `STREAM_RelocateUnit` fired five times while the level loaded; the slide lock engaged after every
  reload from empty and the release key cleared it; a 44k-vertex, 15-batch player model (vanilla 15k / 13) loaded
  and played. Not measured: frame time, a long soak, level changes with magazines on the ground.

## Gotchas
1. **"Failed to open BIGFILE.000" right after launch.** The exe was started with another working directory
   (older `um win launch` did that). **Fix:** start it from its own folder. `um win launch` now does this
   itself (`start /D <exe folder>`); with an older toolkit, use `Start-Process -WorkingDirectory <game>`.
2. **The level-start cutscene looks like gameplay.** `playerControl` is true but the player state is PuppetShow;
   fire/jump/teleport do nothing and `PLAYER_DebugSwitchPlayerCharacter` raised an access violation there and the
   game exited. **Fix:** skip the cutscene (Esc, Up, Enter) and require a non-PuppetShow state before switching
   outfits.
3. **Lara's position becomes NaN and the screen goes grey.** The bridge's animation `freeze` (speed 0) leaves
   section times NaN. **Fix:** never freeze; shoot turntables with the orbit camera only.
4. **Injected one-frame presses never fire.** The engine needs the press edge its own mapper derives from device
   state; injected pressed bits are wiped before it reads them, and SendInput mouse clicks only produce the held
   bit. **Fix:** test firing with real input, or add a test command that writes the magazine count.
5. **The idle counter reads 0 while the game runs**, so an "only when the user is idle" gate must be checked before
   launching, not after.
6. **The game stops at its own "Tomb Raider: Legend - Setup" dialog on every launch.** Its saved display mode no
   longer passed the game's validation (`0xEC6180`, called from WinMain through `0x405AD0`; the dialog is
   `DialogBoxParam` at `0xEC4FA0`), even though D3D9 listed every mode. It was not the display, the driver, the
   registry key or the mod (reproduced with the ASI removed). **Fix:** run `trl.exe -setup`, pick the real resolution
   and refresh rate (the refresh list repopulates after the resolution change, so select it second), press Ok; the
   game rewrites `FullscreenModeID` and starts normally. A black screen from an OLED-protection overlay looks the
   same in a GDI capture but is unrelated.
7. **Turntable yaw 0 shows the back of the head** for this model (its front is opposite to `rotation.z`): use the
   front offset of 180 degrees.
8. **Animation seats drift when accessory anchors move.** Hand targets that seat a gun on a magazine read the
   accessory's anchor file; rebuilding the accessory after the animations were authored moved the seats several
   units. **Fix:** regenerate the segment table/header and re-author from the current anchors; keep the anchor file
   versioned.
9. **A second `anim_add` on its own output silently lost the first added blend** (the blend count was not re-read).
   **Fix:** read the appended table back; a self-test now adds six blends in a row.
10. **The 8-frame blend-in performs your first move for you.** A hosted reload that starts far from the aim pose
    looks like it teleports into the first key; start and end every variant on the centre aim pose so the blend
    overlaps an authored rise.
11. **A twirl reload spins the pistol one extra full turn at the very end.** **Cause:** the spin's last keys sit at a
    360-degree rotation vector (the identity), and blends average rotation vectors component-wise with no unwrap, so
    360 -> 0 toward the ready pose is one more roll in a few frames. Between keys the engine lerps after unwrapping by
    whole turns along the previous key's own axis (0x472F0C-0x472FD9). **Fix:** end spins on 0, or wrap every key into
    (-180, 180]. An inventory that reads a grab joint's translation track as radians reports absurd "1,634-degree"
    spins: check which channel you are reading.

## Assets
Pistol models rebuilt from our own mesh (no game geometry shipped); magazines and the backpack tree are our meshes;
textures baked in Blender (CPU). No generated images were used for the character likeness, by decision.

## Cost and time
Two long sessions (one evening, one night) with up to six agents under a machine-wide heavy-job limiter after a
freeze from running three workflows at once.

## Open questions
- The slide lock drops when the engine auto-holsters right after a reload (no enemy, no fire input); keeping it
  through a holster/draw needs the draw-state interception the recon described.
- Whether far pool segments lose their shadow (static shadow sphere) and how often `STREAM_RelocateUnit` fires.
- A runtime head-look controller may override authored head and eye keys during a reload.
- Mini-instances as the host for dropped magazines (per-object culling, engine relocation) remain the upgrade path.
