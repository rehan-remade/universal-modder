---
kind: game
title: 'Original Metro 2033: m2033fix (in-memory crash, fullscreen, V-Sync and frame-limiter fixes), VFI/UPK archives, QuickLZ and the crc32-keyed scripts.bin'
game: Metro 2033
games_also: []
game_version: 'Original 2010 Steam build (app 43110), metro2033.exe 1.0.0.1, PE timestamp 2010-08-27'
platform: windows
engine: native
route: native-hook
tools: ["Python 3 + pefile (static PE/RTTI/strings)", "own VFI/UPK lister + pure-Python QuickLZ 1.5 L3 decoder", "MetroTools source (format reference)", "MetroDeveloper 1.2.2 (hangs this build)", "Ghidra 12.1.4 on a read-only memory image", "Frida 17.24.3", "capstone + minidump (Python)", "Zig 0.17.0 (x86-windows-gnu, no CRT)", "PresentMon 2.6 (console)", "GOG 1.01 v5 build (DRM-free reference)", "Application Verifier + cdb (Windows SDK 10.0.26100)"]
anti_cheat: "none (single-player). The exe is SteamStub-wrapped; it was not unpacked and the file is never patched (m2033fix patches the code in memory after the stub has decrypted it)."
status: working
agents:
- Claude Code (Opus 5.5)
humans: ["wh1tem0nst3r"]
date: '2026-10-21'
links:
  - "https://github.com/tsnest/MetroTools"
  - "https://github.com/tsnest/MetroDeveloper"
  - "https://github.com/tsnest/MetroDeveloper/releases"
  - "examples/metro2033-m2033fix"
tags: [4a-engine, steamstub, rtti, vfi, vfs0, upk, quicklz, scripts-bin, crc32, level-bin, cvars, metrodeveloper, gog, dxgi, vsync]
---
# Original Metro 2033: m2033fix (in-memory crash, fullscreen, V-Sync and frame-limiter fixes), VFI/UPK archives, QuickLZ and the crc32-keyed scripts.bin

This is a static, read-only reverse of the 2010 Steam release. The exe's code section is SteamStub-encrypted
on disk, so the engine was mapped from RTTI and strings, which are not encrypted. The archives were decoded
fully, patch packs included.
- The pure-Python extractor reproduces an earlier, independent extraction byte for byte.
- `content\scripts.bin` turned out to be a crc32-keyed bundle of config files; 90 of its 277 names were
  recovered.
- A dynamic pass then read the running process, read-only. It recovered the cvar table and the config
  loader, and found that the installed MetroDeveloper hangs this build (Gotchas 8–11).
- A 26 KB `dinput8.dll` proxy (m2033fix, kernel32 only) patches the game in memory after SteamStub has
  decrypted the code, and nothing else. Verified in the game (0.1–0.3):
  - a vanilla race that crashed half of all starts on an RTX laptop (P1, verified with an A/B soak,
    Gotcha 14);
  - the display-mode buffer, 512 → 1024 modes, byte for byte as the GOG build (P4, Gotcha 17);
  - `Present`'s SyncInterval, which now follows `r_vsync` (P5, Gotcha 18);
  - an exact frame limiter driven by `target_fps`, and `target_fps` saved (P8, Gotcha 23).
- 0.4 (2026-10-25; 21 Steam starts, a 37-minute play session and 5 starts under Application Verifier on the
  desktop, all clean) adds fixes for Gotchas 20–22 (fullscreen without focus,
  empty display-mode list, 1024+ character `user.cfg` line), GOG's "press any key" and driver-popup changes,
  and a log of the engine's `!!! STOP` reason (Gotcha 24).
  The full list with addresses and bytes is in the example's README.
- 0.1 also set the save flag of `mouse_inertion` (Gotcha 13). 0.2 dropped that, along with an unproven
  exit-time patch.

## Setup
- **Install:** Steam app 43110 (a secondary Steam library), Windows 11, started from the Steam client with
  its SteamStub intact. The 2010 original has been off sale on Steam since Redux (2014); GOG sells it again.
- **GOG reference:** the author's own install of GOG's release of the original (1.01, GOG v5 of
  2026-06-02), read on disk and also run for comparison (Gotcha 17).
- **Exe:** `metro2033.exe` 1.0.0.1, PE32 i386, VS2005 runtime (MSVCR80), PhysX 2.8 (PhysXLoader),
  d3dx9_42, D3D11 path present. The PDB path string is `x:\bin_x86\metro2033.pdb`.
- **Loader:** MetroDeveloper 1.2.2 was installed: a single `dinput8.dll` + `MetroDeveloper.ini`.
  Since 1.2.1 there is no separate `.asi` file. The game imports `DirectInput8Create`, which is why the
  proxy loads. It hangs this build (Gotcha 8) and was disabled.
- **Tooling:**
  - static part: Python 3.14 via `uv`, `pefile`;
  - dynamic part: Ghidra 12.1.4 on a read-only memory image (raw blob at `0x400000`), Frida, capstone,
    minidump;
  - the fix: Zig 0.17.0.
- **Hardware:** RTX 3050 Ti laptop with an AMD iGPU (the game forced to the dGPU), then a desktop with a
  Ryzen 7 7800X3D, RTX 4060 and a 3840×2160 @ 240 Hz monitor (same Steam build and Steam Cloud config).
- **Benchmark exe:** the separate `metro2033benchmark.exe` is a .NET app. Ignore it when choosing a
  route.

## Route and why
The investigation started on the data route. Gameplay lives in data (`scripts.bin`, `level.bin`), and
most option changes need only `user.cfg` (Gotchas 9–13).
- **The crash fix had to be native.** The bug is a race in engine code, so it is fixed by a byte patch in
  memory from a `dinput8.dll` proxy (`examples/metro2033-m2033fix`).
- **The community loader wasn't usable.** MetroDeveloper 1.2.2 hangs this build (Gotcha 8).
- **Unpacking the exe:** not done. SteamStub counts as DRM under the toolkit's safety rules. The code was
  read from a read-only memory image of the running game, and the patch is applied only after the stub
  has decrypted `.text` itself. The memory image and the crash dumps stay private, outside any repo.

## How the game works (what we had to learn)
- **SteamStub:**
  - The entry point is in a `.bind` section, and `.text` (about 5.3 MB) has Shannon entropy 8.0, so a
    disassembler on the file shows noise.
  - `.rdata`/`.data` are plain. They yield 1,622 MSVC RTTI type names (`.?AV...@@`) and about 45k ASCII
    strings.
- **Engine map from RTTI:**
  - `visual` (renderer/models, ~300 classes).
  - `vs` (~300): visual-scripting blocks, i.e. `action_*`, `trigger_*`, `entity_*`, logic gates,
    `drezina_*` (handcar), `kulemet_*` (mounted gun).
  - `as`: animation state graph with blenders and transitions.
  - `vfs`: package registry and pack readers.
  - `uskeleton`, `umainmenu`, AI classes (`commander`, `cover`, `speech`).
- **Leftover multiplayer:** `network_client`/`network_server`, RakNet interfaces, a `-server -map %s`
  argument and messages such as "only server can change levels".
- **Console:** about 325 cvar names in strings (`g_*`, `r_*`, `ph_*`, `s_*`, `dbg_*`), e.g. `g_god`,
  `g_unlimitedammo`, `g_player_speed_scale`, `ph_gravity`, `r_base_fov`. The console itself needs
  MetroDeveloper.
- **Launch arguments in strings:** `-editor`, `-map`, `-save`, `-cfg`, `-test`, `-trace`, `-logflush`,
  `-nogpu`, `-force_physx`, `-openautomate`. Their behaviour is untested.
- **`content.vfi`:**
  - It is a stream of `(u32 id, u32 size)` chunks. Id `0xFFFFFFFF` is the header (u32 version 0 +
    16-byte GUID).
  - Every other chunk is one pack. Sub-chunk 0 holds the pack's file name and size. Sub-chunk 1 holds the
    file records: u32 key, offset, size, packed size, name length, then the name XOR-ed with the key's low
    byte.
  - 46,165 entries across `content.vfs0`, `textures.vfs0/1`, 7 `sounds*.vfs0` and `videos.vfs0`.
- **`content.upk0..3` (patch archives):**
  - Chunk 0 is the blob, chunk 1 the TOC (same record layout), chunk 2 four unknown bytes, chunk 3 the
    GUID.
  - **TOC offsets are absolute in the `.upk` file.**
  - upk1 carries the patched `scripts.bin`, `anims.bin`, all 9 `.lng` files, every `level.bin` /
    `level.add.bin`, and the whole `l08_market_launch` level. upk0 is one texture; upk2/upk3 hold only
    `scripts.bin`.
  - The patch order upk0 < upk1 < upk2 < upk3 is assumed from the names, not proven.
- **Compression:** QuickLZ 1.5.0, level 3, `QLZ_STREAMING_BUFFER 0x20000`.
  - Packets sit back to back. Each has a 1-byte flag (bit 0 = compressed, bit 1 = 9-byte header), then
    packed and unpacked sizes.
  - Back-references can reach into earlier packets, so decode all packets into one contiguous buffer.
  - Entries whose packed size equals their size are stored raw.
- **`level.bin`:** the magic `levl`, then u32 unpacked size, then a QuickLZ stream. Example:
  `l02_exhibition` unpacks from 384,197 to 1,467,910 bytes. It contains entities and script data.
- **`content\scripts.bin`:**
  - A sequence of `(u32 key, u32 size, body)` records that tile the file exactly (277 records in the
    patched copy).
  - **key = crc32 (zlib) of the lowercase path `content\scripts\<name>.bin`.**
  - Recovered names include `gamedata`, `game_materials`, `hud_manager`, `mainmenu`, `environments`,
    `color_anim_lib`, `speech_manager`, `dynamic\human\human`, `dynamic\monsters\<m>\<m>`, `fonts_<lang>`
    (9 languages), and one record per level `lNN_<name>`.
  - Bodies carry no field names (positional, per class), so editing values needs the class layouts.

## Build steps
1. `python vfi_list.py "<game dir>" files.tsv` lists every entry with its pack, offset and sizes.
2. `python vfi_extract.py "<game dir>" <out dir> <substring>...` extracts matching entries, applying the
   upk patches in order.
3. Brute-force `scripts.bin` names as `crc32("content\\scripts\\" + candidate + ".bin")`. Draw candidates
   from archive path components, exe strings and the strings inside `scripts.bin`, under folders such as
   `dynamic\<cat>\<name>\<name>`.
- `vfi_list.py` and `vfi_extract.py` are the author's own and not in the KB. The layout above is enough to
  rewrite them in about 150 lines of Python.
- Keep the output outside the game folder and the repo.

**Crash-fix proxy (m2033fix).**
- Source, build, install and uninstall scripts: `examples/metro2033-m2033fix` (README has the full patch
  list and test tables).
- Build:
  1. Compile with headers: `zig cc -target x86-windows-gnu -O2 -c m2033fix.c`.
  2. Link without the CRT: `zig cc ... -shared -nostdlib -Wl,--entry=DllMain@12 m2033fix.o dinput8.def -lkernel32`.
     `-nostdlib` drops the Windows headers too, hence the two steps.
  3. Provide your own `memcpy`/`memset`/`strlen` and avoid 64-bit division.
  4. The `.def` is required, otherwise the export is `DirectInput8Create@20`.
- Behaviour:
  - `DllMain` only records the module path and starts one thread for P12. That thread checks the same exe
    identity, polls 8 bytes until SteamStub has decrypted them, then writes one jump (Gotcha 22).
  - The first `DirectInput8Create` loads `GetSystemDirectoryW()\dinput8.dll`, checks the exe (base
    0x400000, SizeOfImage 0xB64000, TimeDateStamp 0x4C7775B7) and the exact bytes at each site, applies
    the other patches, logs them, then forwards the call.
  - If anything mismatches, the proxy stays a pure pass-through.
- Rollback: delete `dinput8.dll`.

## Verification
- **Decoder:** checked against an independent earlier extraction of `l02_exhibition` (`level.portals`,
  `level.environment`); the files are byte-identical. Every unpacked size matches the TOC.
- **`scripts.bin`:** the record walk ends exactly at EOF. Name matches are crc32 hits, so they are
  certain once found.
- **m2033fix in the game (0.1–0.3):** A/B soaks (Gotcha 14), Frida/PresentMon checks of P4/P5 (17, 18) and P8
  (23), long play sessions (2 h, 15 levels; 49 save loads; resolution changes up to 4K, Alt+Tab, sleep), race
  amplifiers (game on 2 cores, 20/20 clean) and Application Verifier (light PageHeap + Handles, 0 entries).
  Tables in `examples/metro2033-m2033fix/README.md`. 0.4 passed the same kind of runs on the desktop; P10
  turned the borderless window into real fullscreen on the first try once the window was clicked.
- **Not verified:**
  - loose-file override and most launch arguments (`-logflush` writes nothing in retail, Gotcha 24);
  - the upk priority order;
  - the record body schema;
  - m2033fix P13 with a gamepad, and P11/P12/P14/P17 on the failures they handle (none occurred, so only
    their log lines and normal play were checked);
  - a long 4K session (the largest free address block fell from 158 to 118 MB in 30 minutes, no crash;
    example README).

## Gotchas
1. **Disassembly of `metro2033.exe` is garbage.** **Cause:** SteamStub; `.text` is encrypted and the
   entry point is in `.bind`. **Fix:** use RTTI/strings statically. For code, inspect the running
   process read-only. Don't run unpackers on the exe.
2. **`um scan` says ".NET application".** **Cause:** it scores `metro2033benchmark.exe`, the managed
   benchmark launcher. **Fix:** the game is native x86; use the native/data routes.
3. **`um scan` says "loaders: none".** **Cause:** MetroDeveloper is just a `dinput8.dll` + ini, which the
   scan doesn't know. **Fix:** look for `MetroDeveloper.ini` in the game root.
4. **UPK entries decompress into nonsense or index errors.** **Cause:** TOC offsets were treated as
   relative to the blob chunk. **Fix:** they are absolute file offsets.
5. **QuickLZ decode fails after the first packet.** **Cause:** the streaming buffer (0x20000) lets
   matches point into earlier packets. **Fix:** decode into one growing buffer, not per packet.
6. **`scripts.bin` keys don't match crc32 of bare names.** **Fix:** hash the full lowercase path with
   the `content\scripts\` prefix and the `.bin` suffix.
7. **No `uengine.log` although `[log] enabled = yes`.** **Cause:** the game simply hasn't been launched
   since MetroDeveloper was installed. Expect the log next to the exe after the first run; the game
   needs write access there. (Later, see 8: on this build the loader itself hangs.)
8. **The game sits windowless forever with MetroDeveloper 1.2.2 installed.** **Cause:** a WOW64
   thread-stack snapshot shows the main thread sleeping inside the `dinput8.dll` proxy's init. Steam is
   not yet initialised at that point, `steamclient.dll` never loads, and `uengine.log` stays at 0 bytes.
   **Fix:** rename `dinput8.dll` away, and vanilla shows its `_uengine_` window in about 5 s. Retry with a
   newer MetroDeveloper or report it upstream. Per its release notes, 1.2.2 itself fixed Steam copies that
   1.2.1 broke, and 1.2.3 (2026-04-30) lists only Redux multiplayer fixes; 1.2.3 was not tried here.
9. **Edits to `%LOCALAPPDATA%\4A Games\Metro 2033\user.cfg` are ignored.** **Cause:** `config_load` reads
   the **Steam Cloud** copy first (`SteamRemoteStorage` FileRead). It falls back to the local file, then
   to the archives. **Fix:** edit `<Steam>\userdata\<id>\43110\remote\user.cfg`.
   - Every line is executed as a console command with no filter.
   - So cvars the game never saves still apply, e.g. `r_base_fov` (default 45, range 1–90) and
     `mouse_inertion` (mouse smoothing, default 0.9). Both were verified by reading them from memory.
10. **Windowed 1280x720 opens as a blurry 1024x576 client area.** **Cause:** the exe is not DPI-aware, and
    Windows scales it at 125%. **Fix (untested):** the per-exe compatibility option "High DPI scaling
    override: Application".
11. **Cvar table.** The cvars are static objects in `.data`, typed by vtable: float, int, flag bit, enum,
    and commands.
    - Float layout: `{vtable, name, flags, ?, *value, min, max}`.
    - Flag bit `0x01000000` marks a cvar that is written back to user.cfg.
    - The console singleton registers a cvar through vtable+8 and executes a line through vtable+0x1c.
    - About 250 cvars are recoverable by scanning `.data` of a memory image for (vtable, name) pairs.

12. **FOV set with `r_base_fov` disappears after a session.** **Cause:** `sick_fov` (a "motion sickness"
    option) and `r_base_fov` share one value, at `0x9f2824`. Only `sick_fov` carries the save flag.
    **Fix:** write `sick_fov <deg>` instead.
    - The game keeps it across a menu exit (verified).
    - It travels with Steam Cloud, so every PC on the account gets the same FOV.
    - 60 felt too wide on a 16:9 laptop panel.
13. **`mouse_inertion` is not saved, and 0.01 does not mean less smoothing.** Players advise `0.01` for crisp
    aiming; the line is also gone after a menu exit.
    **Cause:** on exit the game rewrites user.cfg with only flagged cvars, and `mouse_inertion` has no
    flag.
    - The mouse code (`0x726260`) uses `k = sick_mouse + (1 - sick_mouse) * mouse_inertion` (defaults 0
      and 0.9). The saved `sick_mouse` only moves `k` towards 1.
    - **Direction:** `k` (times a 0..1 ramp at `+0x850`) is passed as the blend factor to the camera's virtual
      turn functions (`0x7266dc`..`0x726747`, targets `+0xAB8`/`+0xABC`), i.e. the share of the way to the
      target covered per frame. So 0.9 (default) is nearly direct and 0.01 is maximum smoothing. Confirmed in
      play: with 0.01 held in memory all session (read-only watcher) the mouse floated for a long time. The
      callee's body was not read (virtual, resolved at run time). The GOG build changes nothing in the mouse
      code either.
    - **Fix options** (for a value above the default, if wanted):
      - re-apply the line before each launch, e.g. a Steam launch-option wrapper;
      - from a runtime patch, set the cvar's save flag (`flags |= 0x01000000` on the object at
        `0x9f3710`), so the game saves it itself. m2033fix 0.1 did this (byte `0x9F371B`, `00` → `01`).
        It worked, but 0.2 dropped it: `mouse_inertion` is in none of the original configs, so it is a
        preference, not a fix.

14. **Random access violation about 25–35 s after start, or at exit (`c0000005` reading `0xC` at
    `0x84F72A`), then "Previous launch was unsuccessful. Start in safe mode?" on the next start.**
    **Cause:** a race in the text-language switch.
    - `FUN_0085B090` nulls the charmap global `DAT_00A14F88` and frees it before installing the new one.
    - Meanwhile another thread converts text with `FUN_0084F6E0`. It loads the global once, into `edi` at
      `0x84F6F5`, and faults at `0x84F72A` (`mov eax,[edi+0xC]`) when that load saw NULL. The 46 callers of
      `0x84F510` load it into `edi` the same way; that is the write-to-0 site at `0x84F53C`.
    - Only five instructions write the global: `0x85B0A8` (NULL, the switch), `0x85B0C2` (the new table),
      `0x84F6CB` (NULL + free at exit), and `0x84F8D5` / `0x84F8E3` in the loader `0x84F830` (called once,
      from `0x85A359`; `0x84F8E3` stores NULL only when loading fails).
    - The switch happens on **every** start at about 24–27 s, even when the Steam game language matches
      `lang_text`. An earlier guess that matching the languages avoids it was wrong: the charmap pointer
      still changed once per start in all 20 soak runs.
    - The crashing thread is always a late worker thread. A call-validated stack scan of 5 dumps shows
      `0x85EDA2 → 0x7A40C3 → FUN_00846E10 → FUN_00846010 → FUN_008456E0 → FUN_0084F6E0`.
    - One dump hit the same race at `0x84F53C` instead (a write to 0 via `FUN_00846E10 → 0x84F510`).
    - How often it hits depends on the machine: 5/10 starts on the RTX 3050 Ti laptop, 4/41 on a
      Ryzen 7 7800X3D + RTX 4060 desktop with the same Steam Cloud config. The delay Frida adds hides it.
    - **Fix (in-memory patch, exe untouched):** NOP the 15 bytes `C7 05 88 4F A1 00 00 00 00 00 E8 A9 0F
      BB FF` at `0x85B0A8`.
      - The global is then replaced by one aligned store at `0x85B0C2` and is never NULL.
      - The old table is leaked (a few KB once per start), so readers holding it stay valid.
    - **Measured:** 10×130 s Steam launches with the patch gave 0 crashes; without it, 5/10 crashed at
      26–28 s (Fisher p = 0.016). Menu exits with the patch were clean, and the next start showed no
      safe-mode prompt.
    - **Desktop, without the patch:** smoke 1/2 (2026-10-22), then 0/9 and 3/30 (2026-10-23), all at 26–27 s
      at `0x84F72A` or `0x84F53C`. In all three new dumps the global already held the new table: the worker
      had loaded it inside the `0x85B0A8`..`0x85B0C2` window.
    - **Desktop, P1 only (m2033fix 0.2 with P4/P5 off):** 0/30. Against 4/41 that is p = 0.10, consistent
      with the fix but not significant alone at this machine's crash rate.
15. **Where the saves are.** `user.cfg` is in Steam Cloud (`remote\`). The campaign saves (`lNN_*.player`,
    `auto_save`) are Steam Auto-Cloud files under `Documents\4A Games\Metro 2033`. If OneDrive redirects
    Documents, they are under the OneDrive copy.
    - `um scan` and the first recon missed them.
    - `user.cfg`'s `xbox_state_data (...)()` line is game state the game rewrites itself; it went empty
      after an accidental new-mission start, so back it up before any session that starts missions.
16. **A proxy that does work in `DllMain` hangs this build** (see 8). A `dinput8.dll` proxy is reliable if it
    defers everything to the game's first `DirectInput8Create` call: on the main thread, about 2–4 s
    after start, with `.text` already decrypted by SteamStub.
    - The one exception in m2033fix 0.4 is P12, which has to beat the first `user.cfg` read (Gotcha 22).
      `DllMain` only starts a thread for it; the thread starts after `DllMain` returns and waits for
      SteamStub to decrypt the bytes before it writes.
17. **The GOG release (1.01 GOG v5) is the same exe build, without SteamStub.** Same PE timestamp
    `0x4C7775B7`, version 1.0.0.1, PDB path and section sizes. `.rdata`, `.data` and `.rsrc` are
    byte-identical to the Steam file.
    - GOG has sold the 2010 original since 2026-05-14 (its Preservation Program). The store page's
      changelog lists the changes below: a high-resolution frame limiter, V-Sync, more resolutions and
      controller support in v1; mouse and keyboard on pause screens with a controller connected and no
      Intel Arc warning in v5 (2026-06-02). The copy compared here is the author's own GOG install.
    - Its `.text` is plain on disk, so it is a clean static reference for the Steam build's addresses.
      No memory dump is needed.
    - It also ships a Galaxy `steam_api.dll` wrapper (it implements `SteamRemoteStorage` and
      `GetCurrentGameLanguage`) and a gamepad-remapping `xinput1_3.dll` (`goginput.ini`).
    - GOG patched 11 places in `.text` (132 bytes) plus two stubs in the section's alignment padding
      (`0x94E555`–`0x94F000`):

      | Where | Steam build | GOG build |
      |---|---|---|
      | `0x7A1733`, `0x7A1D71` (stubs) | `swapchain->Present(0, 0)` | `Present(1, 0)`: vsync forced on |
      | `0x7A1F1B`, `0x7A1F41`, `0x7A1F53`, `0x7A1F79` | `GetDisplayModeList(fmt, DXGI_ENUM_MODES_SCALING)` into a 512-mode stack buffer (`0x3840` B) | 1024 modes (`0x7080` B) |
      | `0x85370C` (109 B in place) | FPS above `target_fps` → `Sleep(ms)` | QPC busy-wait to 8.333 ms after the frame start (`[0xA13BD8]` = ticks per ms): a fixed 120 FPS cap |
      | `0x8543D7`, `0x8543E2` | the "press any key" screen after a load: waits about 1 s, and with a gamepad (Steam Input too) present accepts only gamepad codes `0x105`/`0x10B` | both checks removed; m2033fix 0.4 P13 takes only the `0x8543E2` byte (`74 0B` → `EB 0B`), not tested with a gamepad |
      | `0x938F2C`, `0x938F71` | "Unsupported graphics card" and "video driver needs to be upgraded" popups | both popups disabled |

    - The charmap race (14) is **not** patched in GOG: the bytes at `0x85B0A8` are the same.
      Even so, GOG passed 10×130 s launches with 0 crashes. The charmap still switched on every start.
      That run used `lang_text us` and Galaxy's language. Why it does not crash is open.
18. **`r_vsync` does nothing under DX11 in the Steam build.** Proven with a Frida hook in `dxgi.dll`'s
    `Present`. With `r_vsync off` and with `on` (bit `0x10` of `0x9F2820` set), the only per-frame call
    sites, `0x7A1738` and `0x7A1D76`, pass `SyncInterval = 0`. The GOG build passes 1 from the same
    sites. PresentMon agrees.
    - **Fix (m2033fix P5):** at each site, a 5-byte `jmp` to a stub in the proxy DLL. The stub pushes
      `([0x9F2820] >> 4) & 1` as SyncInterval, calls `Present` and jumps back.
      - The jump is written with one `lock cmpxchg8b` on the aligned qword around it.
      - The stubs return through a variable, so the DLL may be rebased.
      - Before writing, check the `r_vsync` registration code (`0x93A778`, `0x93A7A9`, `0x93A7B3`, string
        `0x976748`). That code is plain `.text`, while the cvar object is built later.
    - **Measured:** the hook then sees 0 with `off` and 1 with `on` (from the first frame, and after the
      bit is set live). 10×130 s with `on` and 10×130 s with `off`: 0 crashes.
    - **Not measured:** a visible difference. On the hybrid laptop GOG's `Present(1, 0)` and Steam's
      `Present(0, 0)` give the same frame times, probably because of the compositor.
    - A stub in the exe's `.text` padding at `0x94E560` (GOG's place) passed the same tests. It was not
      kept: it is 43 hand-encoded bytes in the game's code, and a crash in it would look like a game crash.
19. **A Frida `Interceptor` on the game's own `.text` crashed a worker thread** (`c0000005` at `0x4163AD`,
    a refcount decrement on a garbage pointer). A rerun without Frida, and one hooking `dxgi.dll` instead,
    were clean.
    - Hook system DLLs, not game code.
    - PresentMon (2.6 console) gotchas:
      - it writes no CSV, and can misreport `SyncInterval`, when it loses ETW events;
      - a killed run leaves a session behind (`logman stop <name> -ets`);
      - a non-ASCII output path passed from Python failed.

20. **The game starts in "fullscreen" but shows a borderless window (Composed: Flip, +4–5 ms) when launched
    with Steam's "Play" button and not clicked.** **Cause:** without focus, `CreateSwapChain(Windowed = 0)`
    returns `DXGI_STATUS_OCCLUDED` (`0x087A0001`), a success code. The game never checks it and never calls
    `SetFullscreenState` again; Alt+Enter does nothing either. Started from a shortcut, it gets real fullscreen.
    Skipping the intro looked like the trigger, but focus is.
    - **Fix (m2033fix 0.4 P10; a Frida prototype worked):** note the result after `0x7A1EE1`; from a per-frame
      point on the main thread (`0x85B523`), once the game window is in front, call
      `SetFullscreenState(TRUE)` under the renderer lock `0xA2E5B0`.
    - A safe-mode dialog at start takes the focus the same way.
21. **Access violation about 8 s after start, reading `0xFFFFFFF8` at `0x7B379E`.** **Cause:** `0x7A1F17`
    ignores the HRESULT and count of `GetDisplayModeList`, and `0x7B3740` takes the last entry of the sorted
    list without checking it has one. Seen once under Application Verifier; the conditions for an empty list
    in normal use are unknown. **Fix (0.4 P11):** on an empty list, return with the desktop's aspect ratio.
22. **A `user.cfg` line of 1024+ characters ends the game at start** (a plausible cause of "it won't start
    until I delete `user.cfg`"). **Cause:** `config_load` (`0x422580`) copies each line with
    `strncpy_s(buf[1024], len)`, and MSVCR80's invalid-parameter handler exits.
    - The first `user.cfg` read is at about 1.95 s, before the game's first `DirectInput8Create` (about 2.2 s),
      so a fix there is too late. m2033fix 0.4 P12 polls from a thread started in `DllMain` and writes its
      jump 0.3 s after SteamStub has decrypted the bytes (decryption takes about 0.24 s; the test logs show
      the jump in at about 0.7 s).
    - Not fixed: after the copy, `buf[line_length] = 0` is written unchecked, so a file without line breaks
      (e.g. zeros after a failed write) writes past the stack buffer.
23. **`target_fps` does not cap the frame rate and is not saved.** **Cause:** the vanilla limiter
    (the code GOG replaces at `0x85370C`) sleeps whole milliseconds and does nothing when the GPU is the
    bottleneck: 129 FPS average at `target_fps 120`. The cvar has no save flag. High FPS is reported to
    break collisions.
    - **Fix (m2033fix P8):** a jump at `0x8536FB` to a deadline wait on QPC (sleep, then spin for the last
      600 µs). 120.0 / 60.0 FPS exactly, input-to-photon latency 7.9 / 8.9 ms, like uncapped and better than
      the NVIDIA driver cap (11.0 / 12.1 ms). Setting the save flag (byte `0xA1BE03` `00` → `01`) keeps
      `target_fps` in `user.cfg`, and so in Steam Cloud.
    - PresentMon's `DisplayLatency` misleads here: it starts at the previous `Present`, so a wait before
      `Present` counts and a driver wait inside it does not. Compare `AllInputToPhotonLatency`.
24. **The retail game log exists only in memory, and `!!! STOP` crashes on purpose.** `-logflush` writes no
    file. Log lines go through `0x85E0F0` into a buffer at `0xA456E0`; a Frida hook there gives the full
    engine log. The STOP handler `0x9316BB` (cdecl: reason, file, function, line) keeps its text in that
    buffer and then writes to address 0, so the dump shows only an access violation. m2033fix 0.4 P17 writes
    the reason to its own log first.
    - Steam's `GameOverlayRenderer.dll` is injected and hooks about 75 functions (input, message loop, DXGI
      `Present`, DLL loading, the proxy's `DirectInput8Create`) even with the overlay disabled. Early Frida
      hooks on `dxgi.dll` get overwritten by it; hook the game's own call sites after `DirectInput8Create`
      instead (read-only).

## Open questions
- Does `unlock_content_folder` let a loose `content\scripts\<name>.bin` override the record inside
  `scripts.bin`, or only loose files that exist as real archive entries?
- What are the class layouts of `scripts.bin` record bodies? The next step is to find the reader in the
  running process (read-only debugger) via xrefs to the `content\scripts.bin` string.
- 187 unnamed `scripts.bin` records remain, mostly visual-script sequences and hand/weapon setups.
- What is the 4-byte UPK chunk 2? Is the upk order really numeric?
- Why does the GOG build survive the charmap race (17)? GOG 0/50 against Steam vanilla 9/51 across both
  PCs, with the same race code, so the environment differs (Steam overlay/steamclient, GOG's busy-wait
  limiter or its config); not resolved.
- Answered: a 512-mode list is exceeded in practice (553 modes on a 3840×2160 @ 240 Hz monitor; vanilla
  then loses every 4K mode). The limiters were compared in gameplay (Gotcha 23).
