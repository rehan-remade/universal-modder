---
kind: game
title: 'Crash N. Sane: uncapped frame rate, Crash 3''s boss powers in Crash 1 and 2 live, and a quick boot'
game: Crash Bandicoot N. Sane Trilogy
games_also: []
game_version: 'Steam 731490, exe PE timestamp 2018-07-19 (sha256 170c61d3...6af3)'
platform: windows
engine: native
route: native-hook
tools: ["ReShade 6.8.0 add-on build", "MSVC 14.44", "Python 3.10 + numpy (ReadProcessMemory probes)", "Pillow"]
anti_cheat: none (Steam exe is SteamStub-wrapped; only the running process was touched, after start-up)
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-14'
links: ["croc-inside-crash-n-sane-live-two-engine-mashup.md"]
tags: [alchemy-engine, reshade-addon, frame-rate, timer-resolution, game-variables, save-progress, d3d11, overlay-ui, skip-intro, visual-script, bink]
---
# Crash N. Sane: uncapped frame rate, Crash 3's boss powers in Crash 1 and 2 live, and a quick boot

> Three runtime changes from a ReShade add-on, with no game files touched:
> - **Frame rate:** the game runs uncapped (~230–340 FPS on a 240 Hz display), and measured movement shows the
>   game still runs at native speed.
> - **Boss powers:** in Crash 1 and 2, a beaten boss hands over its Crash 3 power the moment the game marks the
>   boss beaten, with a Crash 3-style "new power" card (the game's own icon and wording).
> - **Quick boot:** the title screen is up ~4 s after the window appears, instead of ~50 s (no Activision video, no
>   Vicarious Visions intro cutscene).
>
> Verified in the real game:
> - **Frame rate:** the FPS counter in screenshots, and run speed and jump height measured at uncapped and at
>   60 FPS.
> - **Powers:** switched in memory, checked through their effect in game and in the saved file.
> - **Card:** shown in a boss arena.
> - **Quick boot:** three launches; screenshots show the title ~4 s after the window appears.
>
> No boss was actually fought: each kill was simulated by flipping the beaten flag in memory.

## Setup
- Steam build, Windows 11, borderless window, 240 Hz display.
- A ReShade 6.8 add-on loaded by the game (the same add-on as the
  [Croc mashup note](croc-inside-crash-n-sane-live-two-engine-mashup.md)). The SteamStub-wrapped exe is never
  changed on disk; every patch below is made in the running process after start-up.
- Crash 1 and 2 only use Crash 3's power variables after an archive patch removes the "Crash 3 only" checks. The
  author's personal mod did that; it is not part of this note.

## Route and why
- **Native hook (runtime):** the add-on reads and writes the game's own state each frame.
- **Rejected: archive edits to the boss maps.** Crash 3's way is a boss-manager component whose parameters name
  the power variable and a power-up collectible. In Crash 1/2 boss maps those slots are empty (except Crash 2's
  final boss), and filling them means adding external references and a collectible entity to each map. Too
  fragile.
- **Rejected: rewriting the save at the next launch** (what the existing mod did). The power arrives one
  restart late.
- **Quick boot, other ways (not used here):**
  - PCGamingWiki's [skip-intro fix](https://www.pcgamingwiki.com/wiki/Crash_Bandicoot_N._Sane_Trilogy#Skip_intro_videos)
    empties `archives\bumper_atvi.bk2`. That removes the Activision video only (the VV cutscene comes from the
    start screen's script, below), and it changes a game file, which Steam's file check puts back.
  - `--overridemap <map>` (same page) starts straight in one map, for testing; PCGamingWiki warns that the pause
    menu's statistics read lower. Not tried here.

## How the game works (what we had to learn)
- **Frame limiter:**
  - The game sleeps between frames. At Windows' default 15.6 ms timer tick it can't exceed ~64 FPS, whatever
    it asks for.
  - `timeBeginPeriod(1)` in the add-on lifts that.
- **Max FPS list (Graphics menu):**
  - Built at exe+0x3330a2: the display's refresh rate divided by 1, 2, 3 …, keeping only results from 30 to
    60 (`cmp eax, 60; ja` at exe+0x333102).
  - NOP the `ja` when the game creates its D3D device. The code is decrypted by then and the list isn't built
    yet. Check the bytes first.
  - The saved Max FPS is validated against the list at load and replaced by the list's highest entry when it
    doesn't fit.
  - VSync doesn't hold the frame rate in borderless mode, so the game then runs uncapped.
  - Lower choices do cap the game (120 → a steady 120 FPS with VSync off; the game's hint says VSync overrides
    Max FPS). The menu stays useful.
- **Native speed:** movement is frame-time based:

  | | run | jump | airtime |
  |---|---|---|---|
  | Uncapped (~232–320 FPS) | 13.2 u/s | 3.97 u | 0.62 s |
  | Capped at 60 | 13.2–13.6 u/s | 3.9 u | 0.63–0.64 s |

- **Game variables:**
  - `Upgrade_SuperChargedBodySlam`, `_DoubleJump`, `_DeathTornadoSpin`, `_FruitBazooka`, `_SpeedShoes`, `_SpeedShoesCrash2`.
  - Their defaults sit in `GameVariables.igz`, and the live values are elsewhere.
  - A manager object pointed to from exe+0x1a69a98 embeds at +0x1a0 a hash map (vtable exe+0x155f130):
    - +0x10: the key array's size in bytes.
    - +0x18: keys, the live value holders (vtable exe+0x155f090, bool at +0x10).
    - +0x28: values, pointers to the variable rows (name hash at +0x10, namespace hash at +0x20).
  - To find a power, walk the arrays in parallel and match the row's hash.
  - Writing the holder's byte takes effect immediately: double-jump height went 8.0 → 3.8 → 8.0 units.
  - The game's own Save writes it into `SAVE_n.sav`.
- **Level progress:**
  - One zone record per level and boss (vtable exe+0x13d18c8). +0x10 is the path, e.g.
    `crash1/bosses/b102_ripperroo/b102_ripperroo`.
  - +0x18 points at the loaded save's session object (vtable exe+0x13d1828), followed by 12 per-slot
    sessions.
  - Session flags at +0x50 hold the save's `CZoneInfoUserSession` field 13; 0x800 = boss beaten.
  - The session's other ints match the save field for field (time-trial times at +0x24.. were the fingerprint
    that found it).
  - Nothing references a zone record except a "current level" object, so they're found by scanning for the
    vtable. They share a heap block with the variable map: 157 MB, scanned in 10–25 ms.
- **Areas:** the game opens one archive per area (`l100_hub.pak`, `b106_drneocortex.pak`, lower case). Hooking
  the exe's CreateFileW/A imports gives the current area, and from it the game (digit after `l`/`b`).
- **Crash 3's power-up UI data:**
  - Icons: `ui/Crash/Collectibles/Ability_1..5` (BC3, 512², stored upside down) in `juicedomain_permanent.pak`.
  - Name and how-to: the boss map's `B30x_*_en.lng`, as two localized strings of the power-up collectible.
  - Button glyphs in the text are private-use code points:

    | Glyph | Action |
    |---|---|
    | U+E000 | Jump |
    | U+E001 | Crouch |
    | U+E003 | Spin |
    | U+E005 | Equip Bazooka |
    | U+E006 | Speed Shoes |

    Action names are from `guisystemdata_en.lng`.
- **The game's bitmap fonts** (`fonts/*.igz`):
  - Zoinks is the slanted Crash title face, GeekSpeak the menu body face, both with 4K versions in
    `4ktextures_essentialui.pak`.
  - Each is an `igBitmapFont` (line height in pixels at +0x18), one `igCharMetrics` per character (64 bytes:
    +0x10 code, +0x14 left bearing, +0x18 right bearing, +0x1c advance, +0x28/+0x2c cell size,
    +0x30 u0 v0 u1 v1, top-down) and an uncompressed RGBA atlas (`igImage2`: w/h u16 at +0x18, byte size at +0x38,
    data ref at +0x40 into the file's third section).
  - The `*_Outline` variants bake a black edge around white glyphs, so a tint can colour fill and edge
    separately. A second page holds the pad-button icons.
- **UI panels:** `juicedomain_permanent.pak` has the per-game menu materials as BC3 textures (stored upside down):
  - Crash 1: its wood Save/Load popup and plank signs.
  - Crash 2: its stone panel pieces.
  - Crash 3: its metal popup.
- **Boot sequence:**
  - The trilogy boots into Crash 1's start screen (`C1_StartScreen.pak`).
  - Its zone info (`chunkInfos.pak`, `CZoneInfo._loadMovieName` at +0x50) names a *loading movie*, `bumper_atvi`:
    the Activision video, played through Bink (`archives/bumper_atvi.bk2`, opened by bink2w64.dll, not by the
    exe's CreateFile).
  - The start screen's visual script `C1_StartScreen_Manager` calls `CProgressionNodes::previousLevel`:
    - nothing (a fresh boot): it plays the Vicarious Visions cutscene (`playEdc3`) before the title;
    - a level (back from a game): it fades straight in.
  - previousLevel (wrapper exe+0x274c60 → exe+0x767320) reads a path at +0xb0 of the game state
    (`*(exe+0x1a64690)`; +0xb8 is the current level) and resolves it through the zone manager
    (`*(exe+0x1a5b690)`, lookup exe+0x750ac0).
  - The title ("CLICK TO START") waits for the first input to pick the primary controller. It reads device state
    (Crash reads the keyboard through user32's key state; see the
    [Croc note](croc-inside-crash-n-sane-live-two-engine-mashup.md)), so posted key or mouse messages don't reach
    it; a key press does, an injected one too (gotcha 9). After it, a 6 s camera blend in the same script flies
    to the game-select menu.
- **Reading visual scripts in igz:**
  - An `igVscCppActionNode`'s `_metaFunction` (+0x38) is a named external reference (an RNEX fixup). Its value
    indexes the file's EXNM entries, counting only those without bit 31 of the second word; that bit marks the
    handle entries, which `igHandle` fields index instead.
  - The entry gives the native function's name, e.g. `CProgressionNodes::previousLevel_VSC`. kishimisu's
    [Crash-NST-Level-Editor](https://github.com/kishimisu/Crash-NST-Level-Editor) splits EXNM the same way
    (`FixupCollection.SetupNamedReferences`).
  - At runtime the reflected function's name string is followed (+8) by its code address.

## Build steps
1. **Add-on module (`host_powers.cpp`), every 0.25 s while the area is Crash 1 or 2:**
   - Find the holders through the map.
   - Validate or (re)scan the boss zone records, off the render thread.
   - Act only when two consecutive readings agree.
   - Beaten boss + power off → set the holder byte to 1.
2. **Card trigger:** queue the card if the beaten flag appeared while the area is that boss's arena, or while
   the area just before the current one was the arena (within 5 min). A boss win goes arena → outro cinematic →
   map, and the cinematic's archive is no area. Show the card once the game is in play (camera and player found,
   not frozen) for 0.8 s.
3. **Card art:** a Python script renders the cards from the user's archives into a local cache (premultiplied
   RGBA, 2160p scale):
   - Crash 1's wood popup, 9-sliced wide, with a plank sign "NEW POWER!" on its top edge.
   - The power's name in Zoinks (yellow to orange).
   - The how-to in GeekSpeak, keys in yellow brackets like the game's own prompts.
   - The first version used Windows fonts on a flat box; the user found it ugly next to the game's UI.
4. **Drawing:** at present, in its own `ID3DDeviceContextState`. The textures follow the back buffer's sRGB-ness
   and get mips for smaller screens. Unbind the render target before swapping the state back (gotcha 8).
5. **Frame rate (`host_fps.cpp`):**
   - `timeBeginPeriod(1)` once.
   - The `ja` NOP from `init_device`.
   - Optional own limiter: a high-resolution waitable timer to 0.5 ms early, then a spin.
6. **Quick boot (`host_boot.cpp`, at D3D device creation, in the running process like the `ja` NOP):**
   - Patch the running exe's `BinkOpen` import entry to return null when the path names `bumper_atvi`; the game
     carries on. The `.bk2` file stays as it is.
   - Replace the function at exe+0x767320 with a version that does the same lookup but, on its first call with no
     previous level, uses the current level's path (+0xb8). The start screen then takes its "back from a game"
     branch: no cutscene.
   - Check the original bytes first.

## Verification
- **Frame rate:** the FPS counter showed 230–340 in levels and menus. Run and jump measurements at uncapped and
  at 60 FPS: see the table.
- **Grant (silent):**
  - Crash 1 completed save on the island map.
  - Double jump switched off from outside: the add-on switched it back within 0.5 s, logging Koala Kong beaten.
- **Grant (live, with card):**
  - Inside Cortex's arena, Cortex's beaten flag and the speed shoes were cleared, then the flag set again.
  - Speed shoes came on, and the card rose in over the fight (screenshots).
  - The same flip after quitting from the arena to the map also showed the card.
  - A flip in Crash 2's warp room without coming from that arena granted silently, with no card.
- **Quick boot:** launched three times. The add-on's log shows `bumper_atvi` refused and the previousLevel
  fallback used once, and the screenshots show the title ~4 s after the window appears.
- **Persistence:**
  - An unused variable was set through its holder.
  - The game's Save/Load → Save wrote it to the slot's file (read back with an IGB parser).
  - The save was then restored from a snapshot.
- **Not verified:**
  - When a real boss win sets the flag (at the kill or at the level exit).
  - The Crash 2 card in play. Crash 2's records and silent grant were verified.
  - The current Crash 1 table (see Open questions). The grants above match the first table (Koala Kong → double
    jump, Cortex → speed shoes); the re-ordered one isn't recorded as re-run in game.

## Gotchas
1. **Max FPS stuck near 64 with every setting above 60.** **Cause:** the 15.6 ms Windows timer. **Fix:**
   `timeBeginPeriod(1)`.
2. **Rewriting the Max FPS list in the heap did nothing.** **Cause:** the list is rebuilt from code each time
   the menu opens. **Fix:** patch the comparison in code instead.
3. **Max FPS at the top entry (the refresh rate) doesn't cap, even with VSync on.** **Cause:** borderless
   ignores VSync, and the top entry leaves the limiter off. The validated-at-load fallback also picks that entry.
   **Fix:** pick a lower entry (it caps), or use a limiter of your own for values outside the list.
4. **The variable's object in `GameVariables.igz` never changes.** **Cause:** it holds the default only.
   **Fix:** the live value is in the holder found through the map.
5. **A zone record was invisible to pointer scans.** **Cause:** only one object references it. **Fix:**
   - Scan for its vtable.
   - Validate with the path string at +0x10.
   - Rescan when validation fails: a save load rebuilt them once, right after the first scan.
6. **Fresh records read "beaten" on load.** **Cause:** loading a save flips many flags at once. **Fix:**
   - Grant silently.
   - Show the card only for a flip seen while that boss's arena is the area.
7. **Wrong file restored from a saves snapshot.** **Cause:** the save folder also holds an older mod's
   `powers_mod_backup/SAVE_n.sav`, with the same file name. **Fix:** restore the root entry.
8. **The game crashed on Graphics → Apply, but only after the add-on had drawn a card.** **Cause:** the add-on's
   own `ID3DDeviceContextState` still had the back buffer's RTV bound after `SwapDeviceContextState(prev)`. That
   live reference made the game's `ResizeBuffers` fail with `DXGI_ERROR_INVALID_CALL` (in ReShade's log), and the
   game crashed. **Fix:** `OMSetRenderTargets(0, nullptr, nullptr)` before swapping back.
9. **Injected Enter presses through the intros once loaded a save.** **Cause:** the VV cutscene doesn't skip on
   Enter, and the title/menu logo fingerprints never matched the textures actually drawn. A press then landed on
   the main menu, where Enter means Continue: the last save loaded and a level started. **Fix:** don't skip by
   input; take the script's own no-intro branch (Build step 6). Any input-based automation on these menus needs
   a positive "this is the title" signal first.

## Assets
- No generated assets.
- **The card:** built from the user's own archives: Crash 3's icons and localized strings, the game's fonts and
  Crash 1's wood popup. The cache stays local.

## Cost and time
One afternoon session, including the frame-rate work.

## Open questions
- Does a real boss win set 0x800 at the kill or at the level exit? It only changes when the card appears.
- Crash 1 has six bosses for five powers, so one gives none. The first table skipped Papu Papu (Crash 1's slide
  and body slam are always on), and players then missed a power after the first boss. Now Crash 1 follows Crash
  3's order from the first boss (Papu Papu → super body slam … N. Brio → speed shoes), and Cortex, the final boss,
  gives none.
