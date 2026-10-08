---
kind: technique
title: "Wwise BNK versions: authoring-version → bank-version mapping and the open toolchain"
tags: [wwise, bnk, soundbank, bank-version, wwise-version, toolchain, wwise-audio-tools, wwiseutil, ww2ogg, revorb, watch-dogs, wdl]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - "https://github.com/WolvenKit/wwise-audio-tools"
  - "https://github.com/hpxro7/wwiseutil"
  - "https://github.com/audiokinetic/WwiseIncludes"
  - "https://www.audiokinetic.com/en/download"
  - "https://kaitai.io/"
---

# Wwise BNK versions: authoring-version → bank-version mapping and the open toolchain

> Which audio you can rebuild depends on matching the bank version the game expects to
> the Wwise authoring version that writes it — the same engine version will refuse to
> re-emit an older bank format. For Watch Dogs: Legion the WDL banks are **SoundBank
> v132 (0x84)**, and only the **2019.2.x** authoring line writes that version; the
> 2021.1 install writes a different one and is not interchangeable. This note records
> the confirmed version mapping and the author's local, **unpublished** toolchain (a C++
> port of two abandoned Wwise tools plus a Go reference) that reads/replaces BNKs and WEMs.
> For the container/HIRC/`.wschema` internals, see the companion generic note below.

Companion note (read first for the format itself): `techniques/wwise-soundbank-hirc-and-wschema.md` — it covers the `BKHD`/`DIDX`/`DATA`/`HIRC` chunk layout, the `HIRC` object framing, the per-version `.wschema` schema, and WEM→OGG. This note only adds the version mapping and the toolchain.

## When to use it

- You must *rebuild* a Wwise bank (edit/replace a WEM and re-emit a valid BNK), not just
  read one, and need to pick the authoring version that matches the target game.
- You are choosing which open tool handles a given game's banks/media, and want to know
  which of the available forks is a source tree vs. a binary bundle.
- You are unblocking loop editing or full HIRC object parse/serialise and want the current
  port status and the ordered next steps rather than re-deriving them.

## How

### 1. Version mapping (confirmed)

The bank version is a property of the Wwise *engine version* that authored it; the
authoring tool only re-emits the format of its own line. Confirmed locally:

| Wwise authoring | Build | Writes / matches |
|---|---|---|
| 2019.2.15.7667 | 7667 | **SoundBank v132 (0x84)** — matches WDL/WD3 banks |
| 2021.1.0.7575 | 7575 | a **different** bank version — not interchangeable with v132 |
| 2015.1.9 | 5624 | (older line; kept as an installer/SDK bundle, mapping not exercised) |

WDL (`Watch Dogs: Legion`, internal codename WD3) banks are v132; `BKHD.version == 132`
is the gate the whole downstream parse keys off (see companion note). The
2019.2.15.7667 install round-trips them; the 2021.1.0.7575 install does **not**.

### 2. Toolchain: what to actually use

The toolchain is the author's local, **unpublished** **port-and-merge** of two abandoned
tools into one C++ repo, with a Go tool kept as the authoritative spec:

- **`game-tools/openwwise-toolkit-git/wwise-audio-tools/`** — the C++/CMake **merge
  target** and the place new code goes. Fork of `WolvenKit/wwise-audio-tools`. Already
  has WEM→OGG, BNK extract/replace, the `w3sc` sound-cache reader/writer, Kaitai-
  generated parsers, and the header-only `.wschema` HIRC loader
  (`include/wwtools/schema.hpp`). License MIT; `ww2ogg`/`revorb` are vendored and built
  from source.
- **`.../wwiseutil/`** — Go fork of `hpxro7/wwiseutil`, part of the author's local,
  **unpublished** work. **Reference source only** (no `go.mod`; do not build). Its
  `DEFERRED.md` is the author's local, unpublished Go spec for the format, algorithms,
  and structs.
- **`.../wwise-unpacker-revamped/`** — a **binary bundle** (`bnkextr`/`quickbms`/`ww2ogg`/
  `revorb`/`vgmstream-cli`/`ffmpeg` + `.bat`/`.sh`). Not a source tree; do not port from
  it. Useful only as a reference for a `quickbms → bnkextr → ww2ogg → revorb → codec`
  bulk pipeline and for missing output formats (FLAC, OPUS, MP3).

Build the merge target (C++):

```sh
git -C wwise-audio-tools submodule update --init --recursive
cmake -B wwise-audio-tools/build -S wwise-audio-tools -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build wwise-audio-tools/build
```

On **CMake 4.x** the `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` flag is **required**, because
CMake 4.0 dropped compatibility with projects that declare `cmake_minimum_required(< 3.5)`
(the bundled `libogg` still does). System deps: `libogg-dev`,
`libvorbis-dev`, and Catch2 ≥ v3 for tests. Outputs: `build/bin/wwtools`,
`build/lib/libwwtools.{a,so}`. CLI subcommands: `wem`, `bnk`, `cache` (Go CLI instead uses
flag-style `-u/-r/-f/-o/-t/-v`).

### 3. Getting the authoring tool

The authoring installs are **licensed Audiokinetic software**. Obtain them through the
official **Wwise Launcher** (`audiokinetic.com/en/download`), not from leaked trees; the
Launcher's own network API can fetch public redistributables headlessly but the EULA
still governs use. For v132 targets, install **2019.2.x** specifically.

### 4. Current port status and next steps

Port is **paused after Phase 2a** (11 test cases / 618 assertions green). Done:
`Container`/`ReplaceWems`, `bnk::File::ReplaceWems`, util helpers, the `.wschema` loader.
Not started: `bnk/file.go::LoopOf`/`ReplaceLoopOf` (Phase 2b), full HIRC object
parse/serialise (2c), `pck::File` (Phase 3), GUI. Loop editing was GUI-only in the Go
tool; preferred future surface is Qt6 (LGPL-3.0, good Windows story) with a TUI
(FTXUI) fallback. Tests must run from the `wwise-audio-tools/` working dir against
`tests/testdata/...`.

## Gotchas

1. **Rebuilding with the wrong authoring line silently changes the bank version.**
   **Symptom:** a regenerated bank is rejected/not played by the game, or a downstream
   parser desyncs though the file "looks" valid. **Cause:** the authoring version writes
   the bank version of its own line, not the version you fed it — 2021.1.0.7575 does not
   emit v132. **Fix:** pin the authoring install to the version matching the target bank
   version (2019.2.15.7667 for v132), and check `BKHD.version` after a round-trip.

2. **`wwiseutil/` looks buildable and is not.** **Symptom:** `go build` fails on missing
   `go.mod` / unresolvable `github.com/hpxro7/wwiseutil/...` imports. **Cause:** the Go
   tree is vendored as a **reference**, not a maintained module. **Fix:** read
   `wwiseutil/DEFERRED.md` for the spec; do not `go mod init` and build it.

3. **`wwise-unpacker-revamped/` is a binary bundle, not a source tree.**
   **Symptom:** you try to "port" from it and find only `.exe`/`.bat`/`.sh` and vendored
   binaries. **Cause:** it is orchestration + prebuilt tools. **Fix:** do not copy its
   `Tools/` into the merge target; the C++ tree already builds `ww2ogg`/`revorb` from
   source. Keep it as a reference for the bulk-convert pipeline and missing codecs only.

4. **Catch2 tests can be silently disabled.** **Symptom:** the `tests` target never
   builds, no error, only a CMake info line. **Cause:** the `tests` target only builds if
   Catch2 ≥ v3 is found locally. **Fix:** install `catch2` (Arch gives `3.15.0-1.1`) or
   force `-DDOWNLOAD_CATCH2=ON` (pulls `v3.0.0-preview5`).

5. **The merge target is uncommitted work.** **Symptom:** `git log` does not reflect the
   current port state. **Cause:** Phase 2a changes (`container.hpp`, `bnk.hpp`,
   `bnk.cpp`, `CMakeLists.txt` and new `tests/`) are uncommitted. **Fix:** check
   `git status` in `wwise-audio-tools/` before assuming history.

6. **The exact bank version 2021.1.0.7575 writes is unverified here.**
   **Symptom:** you want a numeric mapping for the 2021 line and the table only says
   "different". **Cause:** only v132 = 2019.2.x was confirmed against a real bank; the
   2021.1 version number was not read from an actual bank in this work. **Fix:** dump
   `BKHD.version` from a 2021.1-authored bank before relying on it.

## Seen in

- **Watch Dogs: Legion / WD3** — banks are SoundBank **v132 (0x84)**; round-tripped by
  Wwise authoring **2019.2.15.7667**, not by 2021.1.0.7575 (see companion note for the
  chunk layout and the retail `sound.dat` packaging).
- **Local, unpublished toolchain** — `openwwise-toolkit-git` (C++ `wwise-audio-tools`
  merge target + Go `wwiseutil` reference + `wwise-unpacker-revamped` bundle); upstreams
  `WolvenKit/wwise-audio-tools`, `hpxro7/wwiseutil`, and the Apache-2.0
  `audiokinetic/WwiseIncludes` headers.
- **Local authoring installs** — `Wwise 2019.2.15.7667/` and `Wwise 2021.1.0.7575/`
  (both `Authoring/` + `Run.bat`), plus a `wwise 2015.1.9` build-5624 installer/SDK set.

## Open questions

- Read `BKHD.version` from a real 2021.1.0.7575-authored bank to complete the mapping;
  only v132 = 2019.2.x is confirmed numerically here.
- Which BNK version does the 2015.1.9 line write, and does the `.wschema` set (v34…v150)
  cover it?
- Does the WDL retail audio in `sound.dat` use the same v132 BNK framing once unpacked, or
  a different container that only references WEMs?
- Finish the WAV→WEM / OGG→WEM header-rewrap direction and the Audacity WEM plugin; then
  Phase 2b/2c (loop edit + full HIRC object parse/serialise) — all paused in the merge
  target.
