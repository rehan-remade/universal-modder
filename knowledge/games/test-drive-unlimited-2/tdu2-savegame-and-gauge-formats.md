---
kind: game
title: "TDU2 savegame layout and gauge bank (.bnk / HudGaugeBank) format"
game: "Test Drive Unlimited 2"
games_also: []
game_version: "see note"
platform: linux
engine: unknown
route: native-hook
tools: ["Ghidra", "xxd / hex editor", "HxD", ".NET decompiler (dnSpy-class)", "MiniBnkManager"]
anti_cheat: "None encountered for this offline file-format work. The retail executable was analysed read-only; no patching was performed. Save edits are done on copies."
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links: []
tags: ["savegame", "file-format", "crc", "stfs", "gauge", "bnk", "ghidra"]
---
# TDU2 savegame layout and gauge bank format

> Notes on TDU2's save container and its gauge bank system. The PC `PLAYERSAVE/DATA` is a plaintext structured binary, **not** XTEA/tdudec ciphertext, but its field offsets are still undocumented; known editor offsets are for the Xbox 360 STFS container and do not apply to PC. Gauges live in per-car `.bnk` banks (`HudGaugeBank`) whose layout and loader path were recovered from the executable.

## Setup

- Save files live under the game's savegame directory. Profiles are directories: `<Profile>/PLAYERSAVE/{DATA,KEYMAP,OPTIONS}` plus `AVATAR/PHOTO00`, and optionally `LICENCES/`, `PHOTOS/`, `STICKERS/`.
- `ProfileList.dat` is the profile registry at the savegame root; `SystemDefault` is a separate engine-settings blob (XMBF), not save data.
- Analysis was read-only (Ghidra + hex dump) plus decompiling third-party editor binaries; all edits done on copies.

## Route and why

- **Savegame:** static file-format analysis. No loader hook yet; the goal was to migrate progress between profiles and understand whether the PC `DATA` is encrypted.
- **Gauge bank:** a native hook is the intended route (a separate `gauge_hook.dll`), because gauge styles are hardcoded in the executable rather than in `db_data`. That hook is currently tabled.

## How the game works (what we had to learn)

### Save container layout

```
savegame/
  ProfileList.dat          profile name registry
  SystemDefault            engine settings (XMBF), not save data
  <Profile>/
    AVATAR/PHOTO00         character photo
    PLAYERSAVE/DATA        main save
    PLAYERSAVE/KEYMAP      key bindings
    PLAYERSAVE/OPTIONS     game options
    LICENCES/LIC_00..LIC_07  vehicle license unlocks (optional)
    PHOTOS/PHOTO0BX.JPG    in-game photo (optional)
    STICKERS/*.STI         cosmetic sticker unlocks (optional)
```

### ProfileList.dat

| Offset | Size | Contents |
|--------|------|----------|
| `0x00` | 2 | Unknown; observed `0x8593` (count or version) |
| `0x02` | 6 | Padding (zeros) |
| `0x08` | 2 | Marker `0xFFFF` |
| `0x0A` | varies | Profile name, ASCII, null-padded to `0x100` bytes |
| `0x10A` | 1 | Terminator `0xFF` |

Verified by hexdump: the observed file is 267 bytes and holds a profile name at `0x0A`, `0xFF` at `0x10A`. Renaming a profile requires both the directory name on disk and this 256-byte slot to change.

### PLAYERSAVE/DATA (PC)

- **Not encrypted.** `strings -n 4` finds ~2200 short printable runs but no player name in ASCII/UTF-16LE/UTF-16BE, and there is no STFS magic (`CON`/`LIVE`/`PIRS`) or XMBF magic. Bytes look noisy but are a structured binary format, not ciphertext. XTEA decrypt with the key found in the executable produces garbage.
- **Field offsets are not yet documented for PC.** Sizes vary with progress: profile A 149713 B, profile B 184433 B (difference 34720 = `0x87A0`, which appears once in the executable — possibly a related constant).
- The executable has an XTEA decrypt/encrypt pair (file offsets `0x55EA60`/`0x55EAD0`, VA `0x95EA60`/`0x95EAD0`, ImageBase `0x400000`; initial sum `0xC6EF3720`, delta `0x61C88647`) with 40 decrypt and 9 encrypt callers. The 16-byte key at VA `0x00F763AC` matches TDU1's `tdudec` key #1, so it is used for non-save files (`.btrq`/`.db`), **not** the PC save. The raw key bytes are intentionally omitted here.
- Source-file debug strings in the executable point at Eden Games internals (`DB_Base.cpp`, `GSFile.cpp`, `GSConfig.cpp`), which is where the PC struct/serializer would need to be decompiled.

### Xbox 360 STFS offsets (do NOT apply to PC)

Third-party editors (a SmartAssembly-obfuscated .NET editor, and a netz-packed one) work on Xbox 360 STFS saves (plaintext after STFS extraction). Decompiled reader offsets:

- `17250` (`0x4362`) — money
- `18872` (`0x49B8`) — casino chips
- `18451`, `18455`, `18459`, `18463`, `18467`, `18471`, `18475`, `18479`, `18483` — progress fields (`0x4813`–`0x4833`)

Applied to the PC `DATA`, those offsets land on random bytes (`u32` values in the billions), confirming the layouts differ.

### CRC / integrity

The executable contains many CRC code strings (`CRC_A_PROFILE_NAME`, `CRC_R_PROFILE_NAME`, `CRC_A_PROFILE_READ_ACHIEVEMENTS`, `CRC_E_SAVEGAME_SERVER`, `CRC_R_SAVEGAME_CASINO_*`, etc.), so the game likely validates save integrity on load. A community plugin (`tdu_andraste_playersave_validation_skip`) is a TDU1 1.66a plugin; no TDU2 equivalent is known.

### Migration workflow (profile B → profile A, rename)

1. Back up the whole savegame directory (work on copies; cross-profile mixing can corrupt saves).
2. Copy progress-bearing directories that the target profile lacks: `LICENCES/`, `STICKERS/`, `PHOTOS/`.
3. Rename the profile directory and update the `ProfileList.dat` slot at `0x0A`.
4. Check that no internal `DATA` reference points at the old profile string.
5. Handle CRC/integrity validation (the `tdu_andraste_playersave_validation_skip` plugin above is TDU1-only, so there is no known TDU2 equivalent).

### Gauge bank (`HudGaugeBank`)

Gauge styles (needle size, gauge size, screen position) are **hardcoded in the executable**, not in the `db_data` database, which is why adding styles needs executable patching or script hooking. Digital gauge rendering appears to be lazily initialized/cached: using a digital style on a car that shouldn't have one leaves the rev counter dark until you first switch to a car that legitimately uses a digital style, then switch back.

Loader flow (from decompilation, `HudGaugeBank.cpp`):

- Count/allocate (`thunk_FUN_00c9c800`): counts entries with `type=1, subtype=3`, allocates a bank-name pointer array at `+0x288` (count × 4 bytes), a 16-byte entry array at `+0x2a4`, count at `+0x2a8`, current index at `+0x2ac`. Each entry's vtable is `PTR_thunk_FUN_0068a140_0148bbbc`.
- Per-car path constructor (`thunk_FUN_00c9c700`):
  ```
  if (this+0x2b0 == 0) {                       // not yet loaded
      res  = (640.0 < resolution) ? "HiRes" : "LowRes";
      name = thunk_FUN_00511510(res, car_name);
      path = "{prefix}FrontEnd/{res}/Gauges/{name}.bnk";
      if (!thunk_FUN_004d8b60(path, 1))        // file exists?
          path = "{prefix}FrontEnd/{res}/Gauges/Hud01.bnk";  // fallback
      this+0x2b0 = thunk_FUN_004d4ed0(path, 1, 0, 0xc1200000);
  }
  ```
- Entry filter and dispatch live in `thunk_FUN_00c9c990` / `thunk_FUN_00c9c5c0`.

`.bnk` container (magic `KNAB` at offset `0x08`):

```
gauge.bnk/
  2Work/.../{CarName}/hud.ini              plain-text gauge config
  5prepared/.../{carname}/allres/needle.2db
  5prepared/.../{carname}/hires/{ext_rpm,int_kmh,int_mph,int_rpm}.2db
  5prepared/.../frontend/gauges/{carname}.2dm
```

`hud.ini`:

```ini
[HUD]
Style   "Audi_TTRS"
AddHud  "interior_kmh"  0  310  0  277  80  122
AddHud  "interior_mph"  0  190  0  277
AddHud  "interior_rpm"  0  8000 0  277
AddHud  "exterior_rpm"  0  8000 0  277
```

`AddHud` fields: type (`interior_kmh`/`interior_mph`/`interior_rpm`/`exterior_rpm`), `val_min`/`val_max` (value range), `ori_min`/`ori_max` (needle angle range in degrees), plus optional extra orientation offsets. `.2db` files are 2D bitmaps (magic `2DBBMAP`); `.2dm` files are 2D materials (magic `2DMATA`, sections `HASH`, `NEEDLE`, `INT_KMH`, `INT_MPH`, `INT_RPM`, `EXT_RPM`, `MAT`). Each car has its own bank (~272 KB typical; some, e.g. Aventador, ~1 MB).

### Car object offsets (for gauge/RPM hooks)

- `edICar` constructor RVA: `0x0100acc0`. Gearbox base at car-object `+0x9F0`.
- `+0x134` current gear (`u32`), `+0x234` requested gear (`u32`), `+0x258` RPM (`float`, ×10 for display), `+0x478` speed v300 (`float`, ÷3.0 for km/h), `+0x778` actual speed (`float`, km/h).

## Build steps

```bash
make gauge_hook        # -> gauge_hook.dll (32-bit, no CRT)
```

`gauge_hook.dll` is an IAT hook on `kernel32!CreateFileA`: when a `.bnk` open targets a path containing `Gauges/`, it consults `gauge_hook.ini` `[redirects]` (or a `gauge_banks/` folder) and redirects. The planned rewrite is to hook `thunk_FUN_00c9c700` directly to swap the `car_name` parameter.

## Verification

- `ProfileList.dat` offsets confirmed by hexdump of the 267-byte file (name at `0x0A`, `0xFF` at `0x10A`).
- "PC `DATA` is not encrypted" confirmed by the user and by the absence of STFS/XMBF magic and failed XTEA decrypt; the Xbox 360 offset mismatch was confirmed by comparing decompiled editor offsets against PC bytes.
- Gauge findings come from decompilation of the executable and from MiniBnkManager extraction of real `.bnk` files.
- **Not verified:** the PC `DATA` field offsets, the actual migration completing without a CRC failure, and the gauge hook against the live game. These are open.

## Gotchas

1. **Never run the TDU1 account editor on TDU2 saves** — different on-disk format and key schedule; it corrupts them.
2. No TDU2 PC save editor exists; the Xbox 360 STFS editors target a different container.
3. Profile rename touches both the directory name and `ProfileList.dat`; the name is null-padded to `0x100` bytes with a `0xFF` terminator.
4. `SystemDefault` is engine settings, not save data — do not edit it.
5. The `.bnk` fallback is `Hud01.bnk` when a car-specific bank is missing; the HiRes/LowRes choice is `resolution > 640.0`.
6. The gauge hook's `CreateFileA` intercept point may be wrong; the loader may need hooking at `thunk_FUN_00c9c700` (or the bank table at `thunk_FUN_00c9c800`) instead.

## Assets

Unpublished local work (not part of this repository; the `gauge_hook` DLL is only a draft):

- `savegame/AGENTS.md` — full savegame notes and open items.
- `savegame/ProfileList.dat` — 267-byte registry (observed).
- `gauge_edicar_notes.md` — gauge/edICar RE notes, `.bnk` structure, hook DLL docs.
- `src/gauge_hook.c` / `src/gauge_hook.def` — CreateFileA-hook draft (needs rewrite).
- `gauge_hook.ini` — redirect config template.

## Cost and time

Not documented in the workspace. Work spans savegame analysis (June 2026) and gauge/edICar RE (July 2026).

## Open questions

- Actual PC `PLAYERSAVE/DATA` field offsets and struct layout (`DB_Base.cpp` / `GSFile.cpp`).
- Whether PC `DATA` needs any encryption/decryption at all.
- Player-name field inside `DATA` (if any).
- Whether the migration survives CRC validation on load.
- Does the game call `thunk_FUN_00c9c700` for cars with no gauge bank table entry? If not, the table at `thunk_FUN_00c9c800` must be extended first.
- Whether the gauge hook should intercept `CreateFileA` or hook the loader function directly.
