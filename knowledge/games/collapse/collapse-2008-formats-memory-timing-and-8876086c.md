---
kind: game
title: 'Collapse (2008): data formats, the init_heap fence, the engine''s leaks and races, and the collapsefix 1.0.1
  fix'
game: Collapse
games_also: ['Collapse: Devastated World']
game_version: 'Steam app 289620, collapse.exe 2,392,108 B, SHA-256 3003600f…bded283, PE timestamp 2008-10-13 (has the 1.1 AA option, no fullscreen-vsync path)'
platform: windows
engine: native
route: native-hook
tools: ["Python 3 + pefile + capstone (via uv)", "Ghidra 12.1.4 headless (full decompile to text, twice for ST7)", "Frida 17.24.3 (spawn, system-DLL hooks only)", "own .table reader/writer and package v8 extractor (Python)", "Zig 0.17 (32-bit test host)", "um win shot (ffmpeg gfxcapture)", "WinDbg 1.2610 + ProcDump 12.02 (unhandled-exception dump)", "Python minidump (dump triage)"]
anti_cheat: "none. Single-player, Steam build has no SteamStub and no steam_api (DRM-free exe). Retail discs reportedly used StarForce."
status: working
agents:
- Claude Code (Opus 5.5)
humans: ["wh1tem0nst3r"]
date: '2026-10-28'
links:
  - "https://web.archive.org/web/20250811064700/https://www.playground.ru/collapse/file/patch_collapse_v1_1-863187"
  - "https://web.archive.org/web/20251022211914/https://www.wsgf.org/dr/collapse/en"
  - "https://web.archive.org/web/20260709041135/https://www.pcgamingwiki.com/wiki/Collapse"
  - "https://web.archive.org/web/20081120161419/http://creoteam.com/forum/"
  - "https://steamcommunity.com/app/289620/discussions/0/540743128682268318/"
  - "https://reshax.com/topic/18427-collapse-2008-t000-unpack/"
  - "https://web.archive.org/web/20170623084809/http://forum.xentax.com/viewtopic.php?f=10&t=11253"
tags: [creoteam, d3d9, vc6, table, package, dxt, init-heap, large-address-aware, gettickcount, frame-pacing, 8876086c, invalidcall, fov, setup-ini, frida]
---
# Collapse (2008): data formats, the init_heap fence, the engine's leaks and races, and the collapsefix 1.0.1 fix

Collapse (Creoteam, Kyiv, 2008) runs on an unnamed in-house C++/D3D9 engine, and nobody had documented its data
formats before. This note covers four things:
- **Data formats.** The gameplay `.table` files and the `package` containers are now fully readable. The tables
  round-trip byte-exactly (682/682) and the textures export as DDS.
- **Technical problems.** Static and dynamic RE of the Steam exe explains the game's crashes and stutter on
  modern PCs: the address-space crash on level loads, the "Cannot initialize video / 8876086c" error (a different
  cause than the community assumed), the GetTickCount judder, and, found in long play, a geometry-buffer leak, a
  navmesh freeze, a mouse race inside Windows' `dinput8.dll` and a bug in the game's own memory allocator.
- **What runs in the game.** collapsefix 1.0.1: a one-bit LAA patcher and a `dinput8.dll` proxy, in
  `examples/collapse-collapsefix` (see Open questions for what it does and what is left).
- **How it was verified.** Byte checks on the exe, a repeated decompile, launches without input measured with
  Frida and an external VirtualQueryEx sampler, a played session that reproduced the classic KERNELBASE
  0xC0000005 crash and pinned it to one 114 MB texture package, then the whole campaign played on the fix and a
  release regression (gotchas 17-21).

## Setup
- Steam build 289620, `collapse.exe` SHA-256 `3003600f…bded283`, x86, linker 6.0 (VC6). Loose `data\` tree of
  4.2 GB plus `video\*.wmv`.
- Test PC:
  - Windows 11 Pro 26300, ANSI code page 1251, a redirected Documents folder;
  - laptop with a Ryzen 5 5600H and an AMD iGPU (adapter 0 for D3D9, driver 31.0.21925.1001) plus an
    RTX 3050 Ti;
  - 1920×1080 @ 144 Hz panel (60 Hz on battery), 344×193 mm.
- Config and log: `%USERPROFILE%\Documents\Creoteam Collapse\setup.ini`, `collapse.log`, `saveGame\`.
  The game keeps a single-instance lock file `%LOCALAPPDATA%\{96BAE105-747B-424b-B6F5-5E55659032A5}`.
- Nothing needs installing to run the stock game here (d3dx9_31 and xinput1_3 are present; wmvcore exists
  on non-N Windows).

## Route and why
- **Data mods** (`.table` edits) go through the tree format below. No loader is needed because the files are
  loose.
- **Engine fixes** go through a proxy DLL. Every import except KERNEL32 is delay-loaded:
  - `VERSION.dll` loads first in WinMain (GetFileVersionInfoA);
  - `DINPUT8.dll` loads right after `Direct3DCreate9` and **before** the device is set up;
  - so a `dinput8.dll` proxy, as in the Metro 2033 fix, is early enough for everything except the heap.
- **The heap can't be fixed from a DLL.** `init_heap` runs from a CRT initializer (a pointer in the `.data`
  init table, before WinMain), and no proxy DLL loads that early. The options are the
  **Large Address Aware bit** (shipped as a patcher that changes one bit of the user's own exe) or a
  suspended-launch patcher.

## How the game works (what we had to learn)
**`.table` (all 682 of them, including balance, weapon, effect, key, state, event):**
- Each file is one recursive typed value. Every value starts with a u32 type:
  - `0`: a table, holding a u32 count, then that many keys (u32 length + cp1251 bytes), then that many values
    in key order. Empty keys are array slots;
  - `2`: f32;
  - `4`: string;
  - `8`: blob, such as 3-byte RGB colours;
  - `0x400`: an "expression" string, used for state-machine link conditions such as `action1+bk; …`.
- `balance.table` holds per-difficulty damage multipliers for every weapon and enemy (`easy/normal/hard`),
  Rodan's health per upgrade (30/40/50/60/70) and medkit values.

**`package` (the `.t000`/`.s000`/`.w000`/`.0000`… files) is not compressed.** The reader and writer
functions show this; the entropy of 6–7.6 that suggested compression is just DXT data. Layout:
- `"package"`, u32 version 8, u32 subtype (4 = textures, 0x14 = skeleton/animation), an 8-byte key and a
  FILETIME;
- u32 entry count, then padding (u32 length + bytes);
- u32 name count, then names (u32 length + bytes);
- u32 hash count, then u32 hashes;
- a subtype section, then padding;
- for each entry, (u32 offset, u32 size); then a u32 total and the raw data.
- Packages are memory-mapped whole, and only for the moment they are read: `data\laboratory.t000` is
  119,962,552 B (114 MB) and needs one contiguous free hole of that size each time.
- In texture packages the subtype section is `u32 0`, `u32 count`, then 28-byte records (width, height,
  mips, 16, FourCC, 3, -1). The payloads are raw DXT mip chains with no header, so adding a DDS header gives
  correct images.
- The ResHax 2025 dumper produced "grayscale" output because DXT5 is exactly one byte per pixel.
- `.v000` holds Ogg streams; the 2009 tool OggEx carves them out.

**Settings.** The engine object lives at `[0x64EE1C]`.
- setup.ini reader `FUN_0057d400`, `[display]` keys:
  - `Monitor`, `Screen W H` (ignored for the window size here; the window takes the whole work area);
  - `FOV` in degrees, converted to radians;
  - `Resolution W H` — **its mere presence switches on fullscreen**;
  - `ColorBits`, `Frequency`, `Brightness`, `Antialiasing`, `Details`, `TextureDetails`, `Exposure`.
- **The writer `FUN_0057e210` rewrites the whole file from a fixed key list that doesn't include `FOV`.**
  That is why the WSGF FOV line disappears unless the file is read-only.
- The FOV is horizontal, so wider screens get Vert- (the image is cropped top and bottom). The default is
  **73.74°**. Cutscene cameras bring their own FOV and ignore the ini value.
- The aspect correction also uses the panel's physical size in millimetres.

**Device setup (`FUN_004dc460`, CreateDevice at 0x4DCF6B):**
- fullscreen: back buffer = `Resolution`, 2 buffers, DISCARD, D24S8, the highest refresh rate ≤ `Frequency`,
  and **PresentationInterval IMMEDIATE always** (no V-Sync path, although the 1.1 notes promise
  "Fullscreen vsync");
- windowed: back buffer = the desktop mode, COPY, interval ONE;
- if CreateDevice fails, the game just tries again with the same parameters forever.

**Memory:**
- `init_heap` reserves 128 + 32 + 512 MB and then **every free region below 0x70000000** (up to 16 regions).
- Its allocator commits inside those reservations. When it runs out it logs `out of virtual memory` and
  calls `RaiseException(0xC0000005)` itself, which is why community crash reports point into KERNELBASE.
- About 0.5 s after start `FUN_005e5990` releases the "fence" reservations, roughly 1 GB.
- The exe has no LAA flag.

**Timing:**
- The main loop (`FUN_005e2b30`) computes `dt = ΔGetTickCount × 0.001`.
- The frame limiter (`FUN_005e2880`) sleeps while more than 5 ms remain, then busy-waits on GetTickCount
  (~100k calls/s).
- The exe has no winmm and no `timeBeginPeriod`, so dt and the limiter are quantised to the ~15.6 ms system
  tick.
- All 8 uses of GetTickCount go through IAT slot `0x603094`.

## Build steps
1. Read and write `.table` files with a parser built from the type list above. Check that dump → JSON →
   rebuild is byte-identical before editing anything.
2. Extract textures: parse a `package`, rebuild a 128-byte DDS header from each 28-byte record, and append
   the raw payload.
3. LAA: back up the exe, set bit 0x20 in the COFF Characteristics (file offset 0x126 in this build,
   `0x0e` → `0x2e`) and leave the checksum at 0.
   - Do it with a patcher that checks the exe hash and can restore the original.
   - Steam's "Verify integrity" also restores it.
4. Measuring in the game:
   - spawn the exe through Frida so the probe sees the CRT initializers;
   - hook only system DLLs: `GetProcAddress("Direct3DCreate9")` → IDirect3D9 vtable +0x40 (CreateDevice)
     → device vtable +0x44 (Present);
   - read the game's tick at `0x6379A4` on every Present;
   - sample the address space **from outside** with VirtualQueryEx.

## Verification
- **Static** (34 byte checks at first, on both the copy and the installed exe, 47 now): imports, the 8 GetTickCount
  sites, 12 patch-site signatures, every byte pattern the DLL uses matching once, constants, CRT init order and
  startup order.
  - A second, independent headless Ghidra run found the same 4985 functions and all 16 key ones at the same
    addresses.
  - The LAA patch differs from the original by exactly one bit.
- **Dynamic, no input:**
  - **20/20 cold starts** reached the menu (V0 = original, V1 = LAA; fullscreen and windowed).
  - At CreateDevice about 860 MB are free below 0x70000000.
  - The largest free block in the menu is **~355 MB with V0 and 2045 MB with V1**.
- **8876086c reproduced:** a fullscreen `Resolution` the adapter doesn't list (2560×1440 on a 1080p panel)
  gives CreateDevice = 0x8876086C and an endless retry loop.
  - Starving the address space before CreateDevice gives **0x8876086A** instead.
  - So the community's 8876086c is not a memory problem.
- **Judder measured:** over 8352 menu frames, 99.7% of the game's dt values are 15/16, 31/32 or 46/47 ms. The
  menu runs at 26 FPS with 31/47 ms alternation.
- **P1 crash reproduced (D2, the human played, original exe, no Frida in the process):**
  - external VA sampler every 2 s, mapped-file diff, ProcDump `-e` for unhandled exceptions;
  - the largest free block fell 415 MB (menu) → 156 MB (`intro`) → 148 MB (a checkpoint reload after death)
    → 122 MB (`laboratory`) → 102 MB;
  - at 37:04, **reloading the checkpoint after a death in `laboratory`**, the log shows
    `out of virtual memory: map size 07267BB8` → `exception at update phase` →
    `fatal exception: access violation at 771cbae4`;
  - `0x07267BB8` is exactly the size of `data\laboratory.t000`; the dump puts the exception at
    KERNELBASE+0x16BAE4 (the engine's own `RaiseException`), exit code 0xC0000005;
  - each reload also leaves the free space more fragmented (the `intro` reload alone cost ~100 MB below
    0x70000000), so deaths and reloads bring the crash closer.
  - A Cyrillic profile name works under ACP 1251.
  - The human also saw the original exe crash at the end of `intro`, which is the transition into
    `laboratory` and the same package (the next largest `.t000` is 76 MB).
- **LAA fixes it (D2 V1, same profile, 25 min, 4 `laboratory` loads including checkpoint reloads):** no
  `out of virtual memory`, clean exit. The hole below 2 GB again shrank to 107 MB, smaller than the package,
  while 2045 MB stayed free above 0x80000000. The sampler can't see where the short-lived view lands, but no
  low hole could hold it.
- **LAA is still needed after the leak fix (NL_1, original exe with collapsefix 0.5.7):** nine `laboratory` loads
  without a crash, and the largest free block stayed flat at 134 MB instead of falling with each reload. The
  package needs 114 MB, so the margin is 20 MB on one PC and driver: too thin to ship without LAA.
- **collapsefix 0.2 / 0.2.1 in the real game (2026-10-29, the human playing):**
  - **borderless:** one display init for the whole session, private memory flat at 1084 MB through an Alt+Tab
    series (against +80–90 MB per Alt+Tab before);
  - the menu screenshot fills 1920×1080 with no border or blur (DPI awareness declared before the game window
    exists);
  - an unsupported `Resolution 2560 1440` falls back to the desktop mode and the game starts (before: endless
    8876086c);
  - the Controlled Folder Access warning appears when CFA is on.
- **The whole campaign on LAA + collapsefix (2026-11-01/02, the human playing, about 10 hours in sessions of up to
  3 h):** no `out of virtual memory: map size`; it found a navmesh freeze, the geometry buffer leak, a crash in the
  system `dinput8.dll` and a DLL bug with per-device vtables, all fixed (gotchas 17-20). A later replay of Maydan
  crashed once in the game's allocator while loading a save; fixed in 1.0.1 (gotcha 22).
- **Not verified yet:**
  - whether the player-reported station crash is the `dinput8.dll` crash (ours was at a `station_02` load);
  - whether the writer strips FOV when settings are saved in the menu;
  - HUD scaling at 1440p and 4K.

## Gotchas
1. **The package payload looks compressed.** Entropy is 6–7.6 and there is no DDS magic. **Cause:** it is raw
   DXT; the dimensions and format live in a separate 28-byte record table. **Fix:** rebuild DDS headers; no
   codec hunt needed.
2. **The `.table` parser fails on all 51 state.table files with "type 1024".** **Cause:** 0x400 is a real
   type (expression strings), not a stray byte. **Fix:** treat 0x400 like a string type.
3. **The Frida probe froze the game on the publisher logo for 105 s.** Without it the menu appears at ~15 s.
   **Cause:** JS hooks on hot APIs (CreateFileA/VirtualAlloc/VirtualFree during WMV playback) starved the
   agent and the game. **Fix:** no hot JS hooks; make IO hooks opt-in; detach one-shot hooks.
4. **Frida CModule crashed a 32-bit process here,** even with an empty `onLeave` on kernelbase!GetTickCount.
   **Fix:** don't hook GetTickCount (the limiter calls it ~100k/s); read the engine's tick global on each
   Present.
5. **The Frida agent DLL distorts the memory picture.** It lands at ~0x5BA40000, inside init_heap's zone,
   and the game itself logs "These modules may cause memory allocation problems: …frida-agent.dll".
   **Fix:** measure the address space from outside with VirtualQueryEx, without injecting anything.
6. **The "after init_heap" snapshot was taken too early.** **Cause:** the VC6 CRT calls GetCommandLineA once
   **before** the C initializers. **Fix:** use WinMain's GetCommandLineA, the second call.
7. **A hook on `kernelbase!GetProcAddress` never saw `Direct3DCreate9`.** **Cause:** on Windows 11,
   `kernel32!GetProcAddress` has its own body and doesn't pass through kernelbase. **Fix:** hook the
   kernel32 export.
8. **The 8876086c theory "P1 starves the driver" was wrong.** **Cause:** the fence is released before
   CreateDevice, and starvation gives 86A. The real trigger is an unsupported fullscreen mode in setup.ini.
   **Fix (collapsefix `display_mode`):** validate against EnumAdapterModes and fall back to the desktop mode.
9. **No screenshots in fullscreen.** **Cause:** exclusive-mode D3D9 isn't capturable by Windows.Graphics.Capture.
   **Fix:** run windowed (a `[display]` with `Screen` and no `Resolution`). ffmpeg gfxcapture also writes the
   frame and then hangs until its timeout, so check for the file. **Later:** not always: in the 2026-11-02
   regression one exclusive-mode menu (1920x1080 at 144 Hz, NVIDIA) was captured fine. collapsefix's borderless
   mode is always capturable.
10. **WM_CLOSE doesn't quit the game, so setup.ini never gets written.** **Fix:** exit through the menu to
    get the game's own reference ini.
11. **A crash can be in a reload, not a level load.** `collapse.log` prints `loading scene …` for level
    transitions but nothing for a checkpoint reload, so the log alone made the crash look mid-gameplay.
    **Fix:** ask the human what happened at that moment; the mapped package size in the log names the level.
12. **Alt+Tab in exclusive fullscreen leaks a whole device every time** (~80–90 MB; after ~25 the game ends with
    "Cannot initialize video", 70 × `CreateDevice 8876086a`). The rebuild does **not** come through
    `TestCooperativeLevel`, so a TCL hook ("DEVICELOST → OK, wait") changed nothing. **Mechanism (device
    bookkeeping through the Release vtable slot):** while the game is in the background the engine re-runs display
    init every 1–4 s, each run ends in a successful `CreateDevice`, and the old device is never released (30 alive
    after three Alt+Tabs). `Reset` on the live device fails with 8876086C because the engine's DEFAULT-pool objects
    are still on it. **Fix used:** borderless (Windowed = TRUE plus a popup window over the monitor); a windowed
    device is never lost, and memory stayed flat. **Later:** the objects that kept the old device alive were the
    leaked batch buffers (gotcha 18); once they are released, the old device dies on each Alt+Tab in exclusive mode
    too (84 Alt+Tabs in three runs, process memory and the game's video memory flat). Before that was known, a leak-free exclusive mode looked like it needed resource tracking or a
    D3D9 wrapper.
13. **Diagnostics can cause the crash you're chasing.** Probing "is the old device alive?" with AddRef/Release
    after the engine had freed it crashed the game twice (0xC0000005). **Fix:** observe only. Keep a set of
    created devices, remove one when the Release hook returns 0, and never touch a pointer you don't own.
14. **Controlled Folder Access breaks the profile and saves with no message.** `SHGetFolderPath(CSIDL_PERSONAL |
    CREATE)` returns 0x80070005. The game then builds its base path from `GetModuleFileName`, the exe path itself,
    giving `…\collapse.exe\Creoteam Collapse\…`, so every write fails with error 3. Saves also fail silently in
    the writer (`CreateFileA` failure → skip, "game saved" was already shown). **Fix:** allow collapse.exe in
    CFA. collapsefix probes this at start and shows a MessageBox.
15. **A torn save is harmless here.** A kill in the middle of a save's 13 `WriteFile` calls leaves the JPEG plus
    header and no state. The game silently skips it and loads the previous checkpoint, because every checkpoint is
    its own `NN_level_K.jpg`. So "hero under the ground" reports are not caused by interrupted writes.
16. **`zig cc … -o /dev/null` on Windows creates a real file named `nul`** in the current folder, which then
    breaks `git add`. **Fix:** compile to a scratch path, or delete it with POSIX `rm`.
17. **A freeze with a moving mouse can be a data bug.** In Mark's Castle the navmesh has a ring of seven slope
    triangles, and the walk across them has no step limit. Replaying the walk from a full dump proved the ring, and
    finding the same neighbour links in the level file proved memory had no part in it. **Fix:** collapsefix sends the
    branch to the next triangle through a stub with a step limit, leaving by the mesh border exit. Tested by forcing
    the state, not yet met in play.
18. **Memory maps show where a leak lives, not who owns it.** Growth was in write-combine blocks, which looks like a
    driver. Counting live resources through the device's `Create*` calls and the classes' `Release` pointed at the game:
    in 52 minutes index buffers reached 351 live of 351 made and vertex buffers 351 of 471, about 750 MB of 1060 MB of
    growth, while textures were freed. In the code, `FUN_004edaf0` builds the mesh batches and teardown `FUN_004e86a0`
    frees the array without their buffers, and renderer init frees it the same way before each rebuild. **Fix:**
    both frees are one `call` with the renderer in `esi`; collapsefix sends them through a stub that releases each
    record's buffers first. To the end of the campaign (82 minutes, 44 loads) committed memory stayed at about 1.1 GB.
    **Trap:** each D3D9 device has its own vtable here, so hooks set once cover only the first device, and the count
    went silent at the first new device. Hook every new device's copy, and refuse a slot that points somewhere else.
19. **Long sessions find what short ones cannot.** Three sessions of about 3 hours each found the freeze, the
    leak and a crash in the system `dinput8.dll` during a scene load (seen once).
20. **A crash inside a Windows DLL can still be the game's to fix.** The game drops its mouse device and makes a new
    one at every scene load (and every ~2 s in the menu). All system mouse devices share one state in `dinput8.dll`;
    when the last is released, its table of fields is freed, while dinput8's own mouse thread reads that table with
    no lock. **Proof:** in the dump the device count is 0 and the table null; a short test program showed the count
    follows `CreateDevice` / `Release`; a Frida poll of the count in the game showed it hit 0 seven times a minute.
    **Fix:** the proxy creates one extra system mouse device with the game's first and never releases it, so the
    count stays at 1 or more. **Trap:** a crash seen once proves little; measuring how often the window opens (with
    and without the fix) is the test you can actually run.
21. **Players don't have Python, and a small patcher exe meets two Windows traps.** The LAA patcher was ported to
    a C console program for the release. (1) "Pause when double-clicked" by counting console processes fails
    under Windows Terminal, the Windows 11 default; checking that the parent is `explorer.exe` works. (2) An exe
    named `*patch*` (also setup, install, update) with no manifest is treated as an installer, and the Program
    Compatibility Assistant asks "This program might not have installed correctly" when it exits. **Fix:** embed a
    manifest with `requestedExecutionLevel asInvoker` and `supportedOS` entries (zig builds it from an `.rc` file).

22. **The game's own `munmap` can free half a block and say it failed.** A crash on a save load wrote into
    0x0B97001C inside `collapse.exe`: the dlmalloc-style allocator was putting a free segment back into its tree
    after its unmap (`FUN_005E5BB0`) returned -1. That unmap walks the range region by region and acts as it goes,
    so a check that fails on a later region leaves the start already freed. Worse, inside the `init_heap`
    reservation it decommits the whole region `VirtualQuery` reports, which can include a live neighbour, and the
    unsigned remainder then wraps. **Proof without the game:** map a copy of the exe with
    `LoadLibraryEx(DONT_RESOLVE_DLL_REFERENCES)` at its base (it has no relocations), fill the two import slots it
    uses, and call the function on made-up layouts (`tools/heapguard_test.c`). **Fix (`heap_guard`):** a jmp at its
    entry to a version that checks the whole range first and frees only when all of it can go.
23. **A save number names a place, not a stage.** In Maydan the menu's last save (14) put the player before
    checkpoint 13, and replaying overwrote save 13. Level triggers in `channels\checkpoint.table` give
    checkpoints 1-11; 12-14 come from the level script: three spots that can be cleared in any order each call
    `SaveCheckpoint` with a fixed constant. The save data (after the JPEG) stores the position, so reading it showed
    the real route 12 → 14 → 13. Not a bug; "Continue" picks the newest file by time.
24. **Cutscene actors can outlive their cutscene.** After the cutscene with Helen two dead swordmen stay black
    until the next load. They are the cutscene's own actors (no `id` binding in the developers' build report
    `data\<scene>\actions\*.html`), their model instances point into the cutscene's package, and they lose their
    textures when it ends: black in the normal view, flat untextured while aiming. The cutscene's machetes survive
    because it re-points them with `setModel` to level models. Re-running `SetTexture` on the game thread did not
    help (engine calls fail on Frida's thread: the allocator uses thread-local storage). Not fixed yet.

## Assets
None.

## Cost and time
One long session: recon → web research (Wayback snapshots, including the 2008 Creoteam forum) → static RE and
tests → LAA patch → 30+ instrumented launches → one 37-minute played session to the crash and a 25-minute one with LAA.
Then five days of DLL work (2026-10-29 to 2026-11-02), with the human playing every test route and finally the
whole campaign while the agent recorded and read the dumps.

## Open questions
- The geometry buffer leak is fixed for 82 minutes of play; a session of 3 hours or more is not done. Live textures
  still grew (556 to 1307) while committed memory did not; cause not read.
- The two black cutscene actors in the first level (gotcha 24): what drops their textures when the cutscene ends.
- In some late calls the live call window swaps the two names (the call log is right); the English text calls the
  professor "Professor Gorin" where the Russian has "Gorin". Both wait for a text patch.
- The `dinput8.dll` crash is fixed by mechanism (gotcha 20); the crash itself was seen only once, so its absence
  in later sessions is weak evidence.
- collapsefix 1.0.1 (1.0.0 packaged with `laa_patch.exe`; MIT; not yet published) (a dinput8 proxy; it hooks the d3d9 vtables of every device, dinput8 vtables and the game's IAT by name, plus call
  sites found by byte patterns that must match once) does borderless + DPI awareness, the display-mode fallback,
  the refresh rate, an optional V-Sync, the QPC GetTickCount, save-write warnings, configurable FOV, input logging, a whole-interface scale, English key names, a navmesh step limit, the release of leaked geometry buffers, a kept extra mouse device and a safe allocator unmap.
  - **FOV (tested in play):** replace the one call to the FOV blend function in the projection, run it with the stock
    angle, scale the tangent of the result. No setup.ini edit needed, and cutscene cameras widen by the same factor.
  - **Interface scale (tested in play at 1080p):** tell the scripts and the mouse the screen is smaller and stretch the
    interface projection back. Scaling text alone breaks layouts, because scripts place pieces for the stock size. The
    crosshair group and blood overlay read the screen rectangle directly and need the small rectangle too.
  - **Key names:** built once at startup from `DIPROP_KEYNAME`, by the keyboard layout of that moment. Bindings are
    scan codes, so answering with US names changes only the hints.
  - **Gamepad:** right stick dead zone is 13.3 %, left 24 %, triggers 30. A Frida hook on `XInputGetState` is enough to test a pad with no hardware or driver. The import is delay-loaded by ordinal.
  - **Stutter:** A/B in play: the stock timer judders, QPC doesn't. Sentinel QTE works in every mode tested; its arrows
    mean W/A/S/D. Over the whole campaign every QTE (many Wormboss fights, several unique bosses) worked with
    W/A/S/D while the "Action!" icon was lit. The Anchor boss uses a mouse click instead, and it worked. The Keeper was
    killed with weapons and no "Action!" prompt appeared; whether it has a QTE at all is unknown.
  - **Trap:** a desktop refresh change (a laptop plugged in: 60 to 144 Hz) resets even a borderless device, and the
    engine leaks one device.
  - **Trap:** don't assume the engine ignores input errors: it re-acquires after failed reads. It only skips checking
    CreateDevice, SetCooperativeLevel and that Acquire.

  Still open:
  - soft text after scaling: the font atlases are small, new fonts and HUD art are a later stage;
  - two bodies stay solid black after a cutscene in `intro`: also without the DLL and on both NVIDIA and AMD, cause not read;
  - no subtitles during calls (Russian voice, English brief afterwards);
  - the dead-mouse reports (not reproduced);
  - gamepad: left stick threshold 7849 (24 %), right stick not found yet;
  - whether the fight's difficulty depends on the timer (first impression only);
  - why the DLL's counter sees about 12 `DEFAULT`-pool textures per exclusive-mode Alt+Tab that are never released,
    while the game's video memory (read from outside, WMI GPU process memory counters) stays flat;
  - the RTX 40/50 "STOP: hardware acceleration not available" (GetDeviceCaps fails; not reproduced on an RTX
    3050 Ti with the same driver build).
- With input: whether LAA holds up through the whole campaign; the station-level crash after the elite
  shooters (reported on the Creoteam forum, not fixed by 1.1); loading-screen crashes (a race or P1?);
  Cyrillic profiles under ACP 1252; HUD at 4K.
- Why the DEP exception helped some users.
- The `.script` bytecode VM (`ScriptArgs::get` is exported), mesh/skeleton subtypes, and `.w000` text.
