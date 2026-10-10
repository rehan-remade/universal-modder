---
kind: game
title: "OpenTDU — decompilation-based source port of Test Drive Unlimited (MC 1.66A)"
game: "Test Drive Unlimited"
games_also: []
game_version: "MC 1.66A"
platform: windows
engine: unknown
route: reimplementation
tools:
  - opentdu_assetExtractor
  - opentdu_savedecryptor
  - opentdu_zcuncompressor
  - vmf_to_swf.py
  - CMake >= 3.15
  - C++17 compiler (clang / gcc / MSVC)
  - Vulkan SDK >= 1.3.204
anti_cheat: "none relevant to this offline source-port work"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links:
  - https://github.com/opentestdriveunlimited/OpenTestDriveUnlimited
  - https://github.com/opentestdriveunlimited/opentestdriveunlimited/releases
  - https://github.com/orgs/opentestdriveunlimited/projects/1
  - https://github.com/orgs/opentestdriveunlimited/projects/6
tags:
  - test-drive-unlimited
  - tdu
  - source-port
  - decompilation
  - reverse-engineering
  - ghidra
  - vulkan
  - x86
  - flash
  - swf
  - tea
  - zlib
---

# OpenTDU — Test Drive Unlimited source port

OpenTDU (`opentestdriveunlimited/OpenTestDriveUnlimited`) is an open-source **decompilation-based source port of Test Drive Unlimited PC (MC 1.66A)**. It reconstructs the original 32-bit x86 game — structs, classes and functions — in C++17 with Ghidra and reimplements the runtime on Vulkan. It ships **no game assets** and requires the user's own legal copy (`README.md:10`). It is explicitly **work in progress** (`README.md:6`); progress is tracked per game mode (VideoBumper and CarShowCase done; **FreeRide in progress**, `README.md:33-37`).

## Setup

- Clone recursively (third_party is a submodule): `git clone --recursive git@github.com:opentestdriveunlimited/OpenTestDriveUnlimited.git`.
- Prerequisites: CMake ≥ 3.15, a C++17 compiler, Vulkan SDK ≥ 1.3.204 (`README.md:17-20`, `CLAUDE.md:23`).
- Own a legal copy of TDU PC MC 1.66A; the port reads the original `TestDriveUnlimited.exe` to extract packed config and shaders and cannot run without it.
- Run `opentdu_assetExtractor` **once before the first game run**; it pulls shaders + `.ini` from the original executable and generates SPIRV (`README.md:26-28`).

## Route and why

- **Route: decompilation-based reimplementation.** Not a binary patch, DLL proxy or emulator. The authors decompile the original with Ghidra and rewrite it in modern C++ (Vulkan instead of D3D9), reconstructing each function from P-Code (`CLAUDE.md:7`). It is not a clean-room reimplementation — it is derived from the retail binary.
- Engine is left `unknown`: the repo never names one. TDU1 predates the named Eden branding of later titles. (Disrupt and Anvil are Ubisoft engines used by the Watch Dogs and Assassin's Creed lines; they are unrelated to TDU.)
- TDU1 counterpart to the TDU2 NULL-pointer crash work elsewhere in this workspace; the two share RE conventions.

See also `games/test-drive-unlimited/savegame-and-config-formats.md` for the TDU1 `tdudec` XTEA variant, `commondt.sav`/`playersave` offsets and the `XMBF` container — independent RE of the same game's save/config data.

## How the game works

### RE workflow conventions

- Ghidra P-Code is cleaned **first**, then translated to the project's C++ style (`.clang-format`).
- Every reconstructed function carries its original address as the first body line, a `FUN_01234567`-style comment, to cross-reference Ghidra and the port (`CLAUDE.md:13`).
- `OTDU_UNIMPLEMENTED` marks a stub awaiting decompilation — asserts in dev builds, no-op in release (`CLAUDE.md:14,76`).
- `OTDU_SIZE_MUST_MATCH(Type, n)` statically asserts that a struct read directly from a disk asset exactly matches the on-disk byte size; required for any such struct (`CLAUDE.md:77`). E.g. `OTDU_SIZE_MUST_MATCH( FlashTag, 0x8 )` (`source/flash/implementation/flash_tags.h:30`).

### x86 pointer emulation

- The original TDU binary is 32-bit, and many asset formats embed 32-bit pointers fixed up at load time (`CLAUDE.md:82-84`).
- On 64-bit hosts, `x86Pointer_t` / `OTDUPointer` (`source/x86_pointer_emulation.h`) stores a 32-bit `ID` and resolves the real pointer through a runtime pointer cache (`gPointerRegister`). A static assert pins it to 4 bytes: `static_assert( sizeof( x86Pointer_t ) == 4, "Must match to ensure correct assets loading!" )` (`x86_pointer_emulation.h:87-88`).
- The copy operator deliberately copies the **pointed-to value**, not the cache ID, so two pointers don't alias one register slot — matching the 32-bit build (`x86_pointer_emulation.h:23-30`).
- Asset pointers migrate to a widened native layout via `AssetPtr<T>`, `GeoPtr<T>` (3DG meshes: `3dg.h`, `geometry_buffer.h`) and `ScenePtr<T>` (3DD scenes: `3dd.h`), each gated by its own `OTDU_NATIVE_MATERIAL` / `OTDU_NATIVE_3DG` / `OTDU_NATIVE_3DD` flag (`x86_pointer_emulation.h:90-139`). An "asset upgrader" will repack 32-bit-pointer blobs into native layout so `x86Pointer_t` can be retired.

### Flash / SWF UI (`.vmf`)

- `source/flash/` reconstructs an SWF runtime: tags, sprites, ActionScript interpreter, display list (`CLAUDE.md:86-94`). Header reference: `https://www.m2osw.com/swf_tags` (`flash_tags.h:10`).
- Historical quirk: during `.vmf` parsing the original 32-bit build **overwrote the 32-bit tag-ID field with a vtable pointer and the tag-size field with a `pNextTag` pointer in place** (`flash_tags.h:13-17,32-37`). Because those had to fit 32-bit fields, the vtable could not be a C++ vtable — it is a hand-built `FlashTagVTable` struct of explicit function pointers (`Execute`, `Draw`, `Initialize`, `Destroy`, `GetType`) (`flash_tags.h:38-63`).
- Current x64 code instead **keeps** the on-disk `TagId`/`TagSize` (8-byte header) and derives the vtable and next tag at access time via `getVtable()` and `getNextTag()` (`flash_tags.h:18-29`). `OTDUPointer::reset()` clears a stale emulation ID before the first assignment onto raw asset bytes overlaid as a tag (`x86_pointer_emulation.h:13-19`).

### Filesystem and formats

- `source/filesystem/` holds the virtual filesystem and bank/archive readers. `bank.h` defines groups keyed by subfolder under `EURO/BNK/` (e.g. `AG_Vehicle = 9 → EURO/BNK/Vehicules`, `AG_Common = 0xe → */common_*.bnk`) and types `AT_3DD=0`, `AT_3DG=1`, `AT_TireProfile=2`/`AT_2DM`, `AT_2DB=3`, `AT_PhysicsBinary=4` (`source/filesystem/bank.h:4-30`).
- `source/player_data/` holds `Savegame { uint32_t saveIndex; SavedProfile profile; SavedCarReserve carReservations; }` (`source/player_data/save_game.h:6-15`), plus profiles, garage, eBay state and a save-game manager (`saved_garage.*`, `saved_ebay_state.*`, `save_game_manager.*`).
- `source/core/` holds CRC32/CRC64 hashing, TEA crypto, BCPL random and threading (`CLAUDE.md:50`); `source/physics/` is a **Jolt** integration (`CLAUDE.md:56`).
- `opentdu_assetExtractor` (`tools/asset_extractor/main.cpp`) walks a compiled-in master shader table, seeks each entry to `OffsetInExecutable - 0x400000` (PE image base), validates the D3D9 `CTAB` marker and reads 16-bit words until the `0xffff` end marker (`main.cpp:390-413`); translates each DXSO shader to SPIRV via bundled DXVK `dxso`, optionally to GLSL via SPIRV-Cross with `-gen_shader_source` (`main.cpp:427-522`; `imgui`/`dbg_font` load from precompiled `.dxso` `.bin`, `main.cpp:352-384`); and unpacks six XOR-obfuscated `.ini` blobs baked into the exe (`readByte ^= currentByte`, `main.cpp:91-104`) at `SystemPC.ini @0x00f9c460`, `GamePC.ini @0x00f9c7b8`, `DevicesPC.ini @0x00f9dc68`, `Audio.ini @0x00f9f1b0`, `Replay.ini @0x00fa0418`, `Physics.ini @0x00fa0820` (`main.cpp:72-88`). Args: `-executable`, `-asset_output_path`, `-skip_glsl`, `-force`, `-gen_shader_source` (`main.cpp:123-138`).

## Build steps

```sh
./build_unix.sh                 # Linux / macOS: builds third_party, then port
build_win.bat x64               # Windows x64 (value passed to CMake -A)
```

- `build_unix.sh:2-16` builds `third_party` via `build_thirdparty.sh`, then runs `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release` and `cmake --build . --parallel=12`.
- Incremental: same cmake configure then `cmake --build build -j$(nproc)` (`CLAUDE.md:31-35`).
- Output lands in `build/bin/` (`OTDU_BIN_FOLDER`, `CMakeLists.txt:9`; `CLAUDE.md:37`). Port binary is `opentdu_<platform>_vulkan` (or `opentdu_unix_vulkan` / `opentdu_darwin_vulkan`) (`CMakeLists.txt:761-765`).
- Tools are separate CMake targets added at `CMakeLists.txt:805-807`: `opentdu_assetExtractor` (`tools/asset_extractor/CMakeLists.txt:13`), `opentdu_savedecryptor` (`tools/save_decryptor/CMakeLists.txt:5`), `opentdu_zcuncompressor` (`tools/zc_uncompressor/CMakeLists.txt:7`); flavours append `_${CMAKE_GENERATOR_PLATFORM}` / `_unix` / `_darwin`.
- There is **no test suite** (`CLAUDE.md:37`).

## Verification

Verified by **reading source** on 2026-10-05: project shape, prerequisites, build scripts and output dir (`README.md`, `CLAUDE.md`, `build_unix.sh`, `build_win.bat`, `CMakeLists.txt:9,690,805-807`); tool names, CLI args and behaviour (`tools/*/main.cpp`, `tools/*/CMakeLists.txt`); `x86Pointer_t` layout, 4-byte assert, value-copy semantics and migration flags (`source/x86_pointer_emulation.h`); Flash tag header handling and hand-built `FlashTagVTable` (`source/flash/implementation/flash_tags.h`); zlib load path and reversed-magic check (`source/filesystem/file_direct_access.cpp:281-320`, `file_direct_access.h:43`); bank groups/types (`source/filesystem/bank.h:4-30`); save struct (`source/player_data/save_game.h:6-15`); TEA schedule (`source/core/crypto/tea.h:3-22`).

**NOT run:** I did not build, launch or run any tool or the game, and no game assets, binaries or the original executable were executed. Args and addresses above are as read from source, not confirmed at runtime.

## Gotchas

1. **Black screen / missing shaders on first run** → asset extractor never run → run `opentdu_assetExtractor` once (extracts shaders + config from the original exe and generates SPIRV; `README.md:26-28`).
2. **Stale assets used instead of fresh ones** → existing outputs are skipped → pass `-force` to overwrite (`main.cpp:57-61,169`).
3. **Garbled pointers reading asset structs on 64-bit** → an on-disk struct with embedded 32-bit pointers was treated as native → use `x86Pointer_t` / `AssetPtr<T>` and keep the 4-byte static assert (`x86_pointer_emulation.h:87-88`).
4. **Flash UI crashes / aliased ActionScript pointers** → copying an `OTDUPointer` by cache ID aliased two pointers into one register slot (e.g. advancing `FlashAction::pActions` moved `pCurrentAction`) → the copy operator copies the pointed-to value, and `reset()` must precede the first assignment onto raw `.vmf` bytes (`x86_pointer_emulation.h:13-30`, `flash_tags.h:32-37`).
5. **No backend fallback** → the renderer is **Vulkan-only** (`CLAUDE.md:98`).
6. **No regression net** → there is **no test suite** (`CLAUDE.md:37`); changes are validated by running the game.
7. **`-skip_glsl` confusion** → GLSL is optional and only emitted with `-gen_shader_source`; omitting it does not break the Vulkan path (`main.cpp:50-55,234-245`).
8. **`opentdu_savedecryptor` writes to a hardcoded path** `D:/playersave_out.sav` (`tools/save_decryptor/main.cpp:64`); on systems without a `D:` drive the write can fail — the tool still demonstrates the TEA block logic.

## Assets

- **None distributed.** The port deliberately ships no game assets (`README.md:10`). Shaders and six packed `.ini` configs are extracted from the user's own `TestDriveUnlimited.exe`; everything else is read from the user's installed copy (banks under `EURO/BNK/`, save files).
- `vmf_to_swf.py` (`tools/`) converts the game's `.vmf` UI files to standard SWF for inspection.

## Cost and time

- The first build compiles the third-party tree (SDL, JoltPhysics, DXVK pieces, Vulkan-Headers, VMA, zlib, SPIRV tooling) — the bulk of the time; rebuilds are incremental (`CLAUDE.md:31-35`).
- `opentdu_assetExtractor` is a one-time step per install (unless `-force`); it translates every shader in the master table, so expect a few minutes (`main.cpp:336-339` logs progress every 100 shaders).
- A Vulkan SDK ≥ 1.3.204 and matching drivers are mandatory.

## Open questions

- **Which engine is TDU1?** The repo never names one; left `unknown`.
- **Asset-upgrader plan**: the per-type flags (`OTDU_NATIVE_MATERIAL`, `OTDU_NATIVE_3DG`, `OTDU_NATIVE_3DD`) are transitional; no unified flag or completed rewriter exists (`x86_pointer_emulation.h:90-139`).
- **`FlashTagVTable` retirement**: the code comments wish for a `.vmf`/`.2db`/`.2dm` asset rewriter so x86 pointer emulation can be dropped (`flash_tags.h:36-37`) — not implemented.
- **ZC magic value / `getZCMagic()`**: the reversed-bits check is present (`file_direct_access.cpp:305-312`) but the constant itself was not traced.
- **FreeRide completeness**: only VideoBumper and CarShowCase are Done; FreeRide is in progress (`README.md:33-37`).
- **Savegame coverage**: unclear from headers alone how much of `Savegame`/`SavedProfile` is implemented vs `OTDU_UNIMPLEMENTED`.
