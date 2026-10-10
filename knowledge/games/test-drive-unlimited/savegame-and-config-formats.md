---
kind: game
title: "TDU savegame encryption (tdudec XTEA) and the CarVST/XMBF audio-config container"
game: "Test Drive Unlimited"
games_also: ["Test Drive Unlimited 2"]
game_version: "TDU1 PC 1.66a (hash addresses referenced); TDU2 PC release"
platform: windows
engine: unknown
route: data
tools: ["tdudec (Luigi Auriemma)", "tdu_savegame_account_editor (Rust/iced)", "xmbf_convert.py (local, unpublished)", "XmbfEditor.java (local, unpublished)", "Ghidra"]
anti_cheat: "None relevant. All work is on files the player owns; analysis is read-only and edits are made on copies. No online-service spoofing."
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links: ["http://aluigi.altervista.org/papers.htm#others-file", "https://github.com/Kethen/TDU_savegame_account_editor"]
tags: ["savegame", "file-format", "xtea", "encryption", "xmb", "audio", "config", "tdu1", "tdu2"]
---

# TDU savegame encryption and the CarVST/XMBF container

> Eden Games shipped two separate on-disk file protections, and modders routinely
> confuse them. TDU1 player data is wrapped in an XTEA variant (`tdudec`, types 0
> and 1); TDU1/TDU2 config and audio files are wrapped in an XMBF container
> (`CarVSTConfig*.xmb`, `SystemDefault`). This note records the algorithms, the
> key layout, the file paths per game, and the byte-level offsets that are known.
> Status is deliberately **in-progress**: the XTEA and XMBF formats are solved and
> tools exist, but TDU2's PC save layout is still undocumented.

## Setup

- **TDU1 (Atari / Eden Games, 2006) PC.** Save directory:
  `%USERPROFILE%/Documents/Test Drive Unlimited/savegame/`. Contains
  `commondt.sav` (account data), `playersave` (character/progress), and
  `ProfileList.dat` (plaintext profile-name registry).
- **TDU2 (Eden Games, 2011) PC.** Save directory:
  `%USERPROFILE%/Documents/Eden Games/Test Drive Unlimited 2/savegame/`.
  Layout differs: profiles are directories `<Profile>/PLAYERSAVE/{DATA,KEYMAP,OPTIONS}`
  plus `ProfileList.dat` at the root. The PC `PLAYERSAVE/DATA` is **not** XTEA
  ciphertext — see "TDU2 differences" below.
- Building the reference tool (`tdudec`): `gcc tdudec.c -o tdudec`. Single C file,
  no deps, GPL-2.0. A prebuilt `tdudec.exe` ships alongside it for Windows.
- The Rust editor (`tdu_savegame_account_editor`) is a separate cargo project
  (`TDU_savegame_account_editor/`); build with `cargo build --release`. It ports
  the XTEA core to `src/tdudec.rs` and the hashing to `src/util.rs`.
- The XMBF tools (workspace-local `carvst editor/`, unpublished) need only Python 3
  stdlib, or JDK 8+ for the Swing GUI.
- All analysis was read-only; save/config edits are done on copies.

## Route and why

- **Route: `data`** — pure on-disk file-format work. The algorithms are public
  (`tdudec`) and the container is reversible, so the shortest path is
  decrypt → edit bytes → re-encrypt, with no executable patching.
- **Why not a native hook:** the encryption key is static and shipped in the
  executable; there is no runtime check worth defeating. Decryption is a
  stdlib-style transform, so a standalone tool is enough.
- The one place a hook *is* justified (TDU2 gauges, TDU1 savedata integrity-hash
  mismatch) is documented in the sibling note and `offsets_and_formats.md` but is
  out of scope here.

## How the game works (what we had to learn)

### 1. Save/config encryption — `tdudec` (XTEA variant)

The algorithm is **standard XTEA with 32 rounds** and the canonical delta
`0x9E3779B9`. The `tdudec` code expresses the delta as `0x61C88647` added per
round on encrypt; since `0x61C88647 == -(0x9E3779B9)` mod 2^32, adding it is the
same as subtracting `0x9E3779B9` — i.e. standard XTEA. Data is processed as
independent 8-byte blocks (`u32 y, z` in little-endian). There is no per-block
chaining in type 0.

`tdudec.c` holds a single 32-byte key buffer holding **two 16-byte keys
concatenated**. The raw bytes are public in the source; they are deliberately not
reproduced here — the key *layout* is what matters:

- **`SAVE_KEY`** (first 16 bytes) — used for `type 0`, TDU1 savegame/playersave files.
- **`OTHERS_KEY`** (second 16 bytes) — used for `type 1`, everything else
  (`.btrq`, `.db`, `.cpr` config files, and the "special type").

| | type 0 — savegame | type 1 — others |
|---|---|---|
| key used | first 16 bytes | second 16 bytes (offset +16) |
| header | none | 8-byte header skipped on decrypt |
| block select | `y=d[0], z=d[1]` | `y=d[2], z=d[3]` (XOR-chain) |
| decrypt write | `d[0]=y, d[1]=z` | `d[0]^=y, d[1]^=z` |

Type 1 is **XOR-chained**: block *i*'s first 8 bytes are used as an IV/feedback
for the ciphertext that follows, so tampering with one block corrupts the next.
Type 0 has no such coupling — a plain XTEA decrypt of the whole file.

**Encrypting a type-1 file** prepends the 8-byte header that decrypt strips:
`u32 timestamp` followed by `u32 ~timestamp` (bitwise NOT), both little-endian.
The C tool uses `time(NULL)`; the Rust port writes the constants `42` and `!42`
(see Gotchas). Because the header is a plain timestamp, re-encrypting an unmodified
file still produces a different byte stream than the original even when the body
is identical.

Round-trip note: `tdudec d` then `tdudec e` does **not** reproduce the original
bytes for type 1 (new timestamp) and, in the Rust port, may pad (see Gotchas 3).

Config files that go through type 1 (`.txt` ↔ `.cpr`):
`Physics`, `Quality_Settings`, `Shadows`, `SystemPC`, `GamePC`.
`./tdudec e Physics.txt Physics.cpr 1`.

### 2. Account hashing (TDU1)

`playersave` stores a CRC-32-family digest of the nickname/email/password so
`commondt.sav` and `playersave` must agree. `src/util.rs::hash_byte_string`
reimplements it: a 256-entry CRC table generated with polynomial `0xEDB88320`
(the reflected CRC-32 polynomial), an update loop
`uVar1 = uVar1 >> 8 ^ pad[(byte ^ uVar1) & 0xff]`, then the final value is
bitwise-NOT-ed and emitted **big-endian**. The comments pin the original
locations in the **TDU 1.66a** executable: table build at `0x00622f50`, update
loop at `0x00624440`. On disk the hashes are stored little-endian-at-offset as
`u32` (the tool writes `to_be_bytes()` into the save — the two disagree on paper;
trust the tool output, see Gotchas 5).

### 3. TDU1 decrypted layout (offsets)

`commondt.sav` (decrypted with tdudec type 0):

| Offset | Size | Field |
|--------|------|-------|
| `0x91` | 1 | `01` = online, `00` = offline |
| `0x98`–`0xB7` | 32 | nickname (null-padded, ≤30 bytes usable) |
| `0xBA`–`0xED` | 52 | email (≤50 bytes) |
| `0xF0`–`0x10F` | 32 | password (≤30 bytes) |

`playersave` (decrypted with tdudec type 0):

| Offset | Size | Field |
|--------|------|-------|
| `0x06`–`0x07` | 2 | sensitive to nickname + online state; purpose unresolved |
| `0x08`–`0x0B` | 4 | nickname hash |
| `0x0C`–`0x0F` | 4 | email hash (`0` when offline) |
| `0x10`–`0x13` | 4 | password hash (`0` when offline) |
| `0x1A`–`0x39` | 32 | nickname (plaintext) |

`ProfileList.dat` is **plaintext**, not encrypted: a sequence of length-prefixed
profile names, each `<u16_le len><bytes>`, terminated by an `0xFF`-sentinel
trailer (`write_profile_list` emits `ff ff 00 00 00 00 00 00 00 00` after the
last name). The two bytes that follow the trailer encode the active profile
(`0x96 0x8B` = first active, `0xF7 0x0C` = second) and appear to be a hash of the
active name — writing `00 00` is accepted.

Memory-side (from Ghidra/x64dbg, for the optional hook route):
`0x0089A730` parses and checks playersave against nickname/email/password;
`0x0089A79E` reads the three hashes from the decrypted buffer; `0x00624880`
computes them. The hash check can be NOP-ed so any playersave pairs with any
commondt.

### 4. The XMBF container (CarVST/TDU audio config)

`CarVSTConfig*.xmb` (sampled: `CarVSTConfig.xmb`, `CarVSTConfig3.xmb`,
`CarVSTConfig5.xmb`; a standalone copy also lives at `TDU-CarVST-Config/CarVSTConfig.xmb`)
is the per-car vehicle-audio config. Format name "XMBF", version `0x00000101`,
all little-endian.

Header (28 bytes):

| Offset | Size | Field |
|--------|------|-------|
| `0x00` | 4 | magic `"XMBF"` |
| `0x04` | 4 | version `0x00000101` |
| `0x08` | 4 | string-pool offset (always `0x1C`) |
| `0x0C` | 4 | schema-table offset |
| `0x10` | 4 | data-section offset |
| `0x14` | 4 | count1 |
| `0x18` | 4 | count2 |

Three sections follow the header: a **string pool** (null-terminated Latin-1
strings), a **schema table** (8-byte entries pairing a name-string index and a
type-flags word; first 5 entries are typedefs), and the **data section**.

Data section header: `+0` `wav_count u32`, `+12` `bank_count u32`, then
`wav_count` u32 WAV-pointer entries; records start at
`data_off + 24 + wav_count*4`.

Records are a fixed **82-byte stride**: `GAP(30) + BankBody(40) + CurveSet(12)`.
Each bank record carries an identity block (`nCarID`, `nWaveIndex`,
`nReverbInternal`, `fBaseVolume`, `bIsTrigger`, `nMustBeLooped`), clipping/tracking
factors (`fClipNear/Far`, `fRefractionFactor`, and `fTracking*`), and pointers into
the event data. `Bank` tag is `1` at record+30; `CurveSet` tag is `6` at record+70.

**Event blocks** are `[13 volume floats][EventName\0][descriptor bytes]` — the 13
floats sit *before* the name, not after. Indices 10/11/12 are Road/Tarmac, Grass and
Dirt volumes (confirmed); 0–9 are unlabelled. Event names follow the rule "first
char uppercase, second lowercase" (`RollingRoadExternal`, `EngineLoad_0`), which
is how the scanner separates event names from `SLIP_idle.wav`-style WAV filenames
and from schema strings. Descriptor bytes after the name are raw u32 pointers/ints;
for Engine events they chain RPM→pitch curves.

The same `XMBF` magic appears outside CarVST: TDU2's `SystemDefault` engine-settings
blob is also XMBF. So XMBF is a **shared Eden serialization container** across both
games, not audio-specific.

TDU1 controller/game configs also use this family — `DevicesPC.cpr` maps USB
VID/PID to per-device `.xmb` profiles.

### 5. TDU2 differences (why tools must not be crossed)

- TDU2 saves are **not** TDU1 saves. Different directory, different on-disk
  layout; running the TDU1 account editor on TDU2 saves corrupts them.
- TDU2's PC `PLAYERSAVE/DATA` is **not** tdudec XTEA ciphertext: it has no STFS
  (`CON`/`LIVE`/`PIRS`) or XMBF magic, and tdudec type 0 with the shipped key
  yields garbage. The retail TDU2 executable does contain an XTEA
  decrypt/encrypt pair (VA `0x95EA60`/`0x95EAD0`, ImageBase `0x400000`; initial
  sum `0xC6EF3720`, delta `0x61C88647` — the *same* variant), but its 16-byte key
  matches TDU1's `tdudec` key #1 and is used for `.btrq`/`.db` files, not the save.
- TDU2 save editors that exist are for the **Xbox 360 STFS** container (money at
  `0x4362`, etc.); those offsets land on random bytes in the PC `DATA`.

## Build steps

```sh
# 1. Reference decrypt/encrypt tool
cd game-tools/TDU/tdudec
gcc tdudec.c -o tdudec

# 2. Decrypt a TDU1 save (type 0, default)
./tdudec d savegame/playersave playersave.dec
./tdudec d savegame/commondt.sav commondt.dec
# Re-encrypt after editing
./tdudec e playersave.edited playersave 0

# 3. Config files (type 1) — CRLF and trailing binary bytes required
./tdudec e Physics.txt Physics.cpr 1
./tdudec e Quality_Settings.txt Quality_Settings.cpr 1

# 4. XMBF audio config round-trip (local, unpublished carvst editor/ tools)
cd "<local carvst editor dir>"
python xmbf_convert.py verify CarVSTConfig.xmb   # byte-perfect check
python xmbf_convert.py to-xml CarVSTConfig.xmb
python xmbf_convert.py patch  CarVSTConfig.xmb  CarVSTConfig.xml out.xmb
```

## Verification

- **XTEA:** round-trips on TDU1 saves in the editor's dev helpers
  (`test_commondt_*`, `test_playersave_write`) and community use of upstream
  `Kethen/TDU_savegame_account_editor`. The type-0/type-1 split and 8-byte
  timestamp header are confirmed by reading `tdudec.c` and its Rust port side by
  side.
- **Hashing:** the two exe addresses (`0x00622f50`, `0x00624440`) were located in
  TDU 1.66a; the port matches observed save behaviour when renaming a profile.
- **XMBF:** `xmbf_convert.py verify` asserts a **byte-perfect** `xmb → xml → xmb`
  round-trip; bank stride (82) was confirmed by measuring 5 consecutive records,
  and Road/Grass/Dirt float indices by user confirmation.
- **Not verified / open:** the PC TDU2 `PLAYERSAVE/DATA` struct layout; where
  CarVST event-float indices 0–9 point; whether edited TDU1 saves survive any
  server-side account check; and the Rust `encrypt_others` padding correctness
  (see Gotchas).

## Gotchas

1. **Symptom:** config file edited in a text editor, re-encrypted with tdudec,
   game then crashes or silently ignores the setting. **Cause:** LF-only line
   endings and/or the trailing binary bytes after the last text line were
   stripped. **Fix:** keep CRLF (`unix2dos`), never strip the trailing bytes
   (inspect with `xxd` before/after), edit as raw bytes so French accents and
   trailing blobs survive.
2. **Symptom:** `tdudec e file.txt out.cpr 1` differs from the original `.cpr`
   even though the plaintext is unchanged. **Cause:** type 1 prepends a fresh
   8-byte `timestamp`/`~timestamp` header and XOR-chains from it. **Fix:** expected;
   compare *decrypted* bodies, not ciphertext.
3. **Symptom:** Rust `encrypt_others` output is larger/different than expected, or
   a re-encrypted config fails to decrypt cleanly. **Cause:**
   `src/tdudec.rs` pads with `input.len() % 32` bytes (remainder, only when ≥1
   block) instead of the exact `32 - (len % 32)` needed for alignment, and writes
   a fixed `42`/`!42` header rather than a timestamp. **Fix:** for byte-exact
   configs prefer the C `tdudec`; treat the Rust port as save-oriented. Re-check
   against the C tool before trusting it on type 1.
4. **Symptom:** TDU2 save corrupted after using a TDU1 tool. **Cause:** the two
   games use different save containers (TDU2 PC `DATA` is not XTEA-wrapped).
   **Fix:** never run `tdudec`/the account editor on TDU2 saves; use the TDU2
   notes (`tdu2-savegame-and-gauge-formats.md`).
5. **Symptom:** nickname/email/password edit accepted in the editor but the game
   rejects the profile. **Cause:** `playersave` and `commondt.sav` hash fields
   disagree. **Fix:** update **both** files together (`patch_commondt` +
   `patch_playersave`); offline saves use zero email/password digests. The
   byte-order comments in `util.rs` (`to_be_bytes` written into the save) are the
   reference — trust the tool, not a naïve re-derivation.
6. **Symptom:** XMBF `patch` throws "Missing `<RawSections>`" or produces a
   non-matching file. **Cause:** the XML was hand-written instead of produced by
   `to-xml`; field editing requires preserving the base64 raw blobs.
   **Fix:** always `to-xml` first, edit only the decoded field nodes, then `patch`.
7. **Symptom:** event names or banks missed in the XMBF decode. **Cause:**
   naïve scanning picks up float bytes that look like ASCII (e.g. `1.0` =
   `0x3F800000` leaks `?`), or matches WAV names as events. **Fix:** use the
   strict whitelist + "uppercase-first/lowercase-second" event rule and the
   82-byte stride scanner already in `xmbf_convert.py`; don't re-anchor on `?`.
## Assets

No art/audio generated. Relevant reference material:

- `tdudec.c` — canonical XTEA implementation + key layout (GPL-2.0, Luigi
  Auriemma, 2009); raw key bytes intentionally not reproduced in this note.
- `tdu_savegame_account_editor/TDU_savegame_account_editor/src/tdudec.rs` — Rust
  port (`SAVE_KEY`, `OTHERS_KEY` u32 arrays) and `src/util.rs` — CRC-32 hash,
  `commondt`/`playersave`/`ProfileList` read-write, plus
  `offsets_and_formats.md`.
- Workspace-local, unpublished `xmbf_convert.py` (1125 lines) — XMBF ↔ XML converter
  with a full format reference in its docstring; `XmbfEditor.java` GUI;
  `XMBF_Format_Reference.docx`.
- Sample files: `VSTs/CarVSTConfig{1,3,5}.xmb`, `TDU-CarVST-Config/CarVSTConfig.xmb`.
- `tdudec/savegame/` — sample TDU2 save files (ciphertext/text pairs) for testing.

## Cost and time

Not recorded in the workspace. `tdudec` dates to 2009 (upstream); the Rust editor
port and offsets notes are 2023–2026; the XMBF RE and tool are 2026.

## Open questions

- TDU2 PC `PLAYERSAVE/DATA` field offsets / struct layout (`DB_Base.cpp`,
  `GSFile.cpp` internals).
- Do CarVST event-float indices 0–9 map to positions/occlusion modes, and are they
  documented anywhere?
- Is the Rust `encrypt_others` padding (Gotcha 3) an actual bug, and does it ever
  corrupt configs in practice?
- Does TDU1 perform an online account check that edited saves must satisfy, beyond
  the local hash agreement?
- Can the XMBF container be generalized into one reader shared by CarVST and
  TDU2 `SystemDefault`, given they share the magic?
