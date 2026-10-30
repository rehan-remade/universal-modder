---
kind: game
title: "Decoding a Clickteam Fusion 2.5 (build 296) data file and patching its events"
game: "Padre Got A Gun"
games_also: []
game_version: "V1.3, itch.io standalone (V1.2 decoded too). Clickteam Fusion 2.5 runtime build 296.9 (Modules/mmfs2.dll 3.0.296.9), 32-bit exe"
platform: windows
engine: native
route: data
tools: ["Python 3 (standard library only)", "NebulaFD September 2026 Update (commit a24d4d1)", "ilspycmd", "um scan"]
anti_cheat: "none: offline single-player, DRM-free. The .dat's Protection chunk holds only a 4-byte checksum of the event, object and frame data (Gotcha 6), with no key, serial or licence data, so it isn't DRM or an ownership check"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-29
links: []
tags: [clickteam-fusion, fusion-2.5, build-296, ccn, pamu, chunk-encryption, events, protection-checksum, nebulafd, conpty, data-mod, itch-io]
---

# Decoding a Clickteam Fusion 2.5 (build 296) data file and patching its events

> Padre Got A Gun is a small Clickteam Fusion 2.5 game sold on itch.io. With our own standard-library Python
> tools we decrypted its data file and decoded all 12,745 events in its 80 frames, including build 296's
> compact forms. We then built a mod that adds two title-screen keys jumping to the developer's unused test
> frames. It runs in the real game, but only once the patcher also updates Fusion's Protection checksum:
> without it, a modified .dat quits silently.

## Setup
- **Game:** Padre Got A Gun V1.3, the DRM-free standalone build from jollyjack.itch.io/padre-got-a-gun, on
  Windows 11. V1.2, the launch build, decodes the same way. The Nebula dump below was made from V1.2; V1.3
  changed none of the images or sounds.
- **Engine:** Clickteam Fusion 2.5, runtime build 296.9. `Modules\mmfs2.dll` has FileVersion 3.0.296.9, and the
  data header says build 296. The exe is 32-bit.
- **Our tools:** Python 3, standard library only (`struct`, `zlib`, `ctypes`). No Fusion editor. CTFAK and
  Anaconda were read as references, never run.
- **NebulaFD**, the "September 2026 Update" (CI build of commit a24d4d1, github.com/AITYunivers/NebulaFD), for the
  asset dump.
  - It ran on the plain .NET 6 runtime (Microsoft.NETCore.App 6.0.16); the Desktop runtime wasn't needed.
  - It writes its config, logs and `Dumps\` next to itself, so keep it in a writable tools folder.
  - The event layouts come from its `Nebula.Core` readers. Their source is public on GitHub; we read them from the
    release build with ilspycmd.
- Everything ran on a copy of the exe, the .dat and `Modules\`, never on the install.

## Route and why
`data`. The exe is Clickteam's stock runtime. The game itself (levels, objects and the event sheets that hold its
logic) is data in the .dat, so the mod edits the .dat.
- **Native hooks**, which `um scan` suggests, would hook a generic interpreter to change data it reads: much harder
  for the same result.
- **Rebuilding from Nebula's .mfa in the Fusion editor** depends on Nebula's build-296 event output, which its own
  notes list as imperfect (Gotcha 10). Patching the .dat changes only the bytes we touch.
- **CTFAK 2.0** (archived Nov 2024) predates build 296. **Anaconda**'s README lists builds 284-293 and sends
  Fusion 2.5+ games to Nebula. We used their source only as references for the cipher and the checksum.

## How the game works (what we had to learn)
**Fingerprint and layout**
- `um scan` prints `Unknown native engine [10%]  evidence: no known engine signature`. The tell is a `Modules\`
  folder holding `mmfs2.dll`, Fusion extensions (`.mfx`; here `KcArray.mfx` and `kcwctrl.mfx`) and sound filters
  (`.sft`).
- It is an "Unpacked EXE" build. The 965 KB exe has nothing appended (no overlay, no `wwww` header), and all
  content is in the 211 MB `<game>.dat` beside it.
- The .dat starts with a 32-byte `wwww` pack header. The `PAMU` (Unicode) game header follows at 0x20, with the
  build number at 0x2C. Chunks start at 0x30.
- A chunk is `u16 id, u16 flags, u32 size`, then the payload; id `0x7F7F` ends the list. Flags bit 0 = zlib,
  bit 1 = encrypted. A zlib-only payload is `i32 unpacked size, i32 packed size`, then the stream.
- Chunk order in this file:
  1. app metadata: header, name (0x2224), author, copyright (0x223B), target filename (0x222F), editor filename
     (0x222E), icon, extension list;
  2. the 904 object definitions (0x2229) and the frame-handle table (0x222B);
  3. the 80 frames (0x3333, each a container of sub-chunks);
  4. Protection (0x2242);
  5. the image, font and sound banks. The sound bank (all 24 sounds, music included, as zlib WAVs) is 99% of the
     file.

**Encryption (standard Fusion 2.5, as in CTFAK 2.0's `Decryption.cs`)**
- The key comes from three strings stored zlib-only, so readable, in the same file: app name, copyright and
  editor filename (the developer's .mfa path).
  - Each string contributes the non-zero bytes of its UTF-16 units.
  - Builds above 284 use the order name, copyright, editor; older builds use editor, name, copyright.
- These bytes become a 256-byte key (magic byte 54), then an RC4-like permutation table. Each chunk is decrypted
  with a fresh RC4-style keystream. CTFAK's names for the steps: `KeyString`, `MakeKeyCombined`,
  `InitDecryptionTable`, `TransformChunk`, `DecodeMode3`.
- Mode 3 (flags 3, compressed and encrypted) payloads:
  - a `u32 unpacked size`, then the encrypted bytes;
  - for an odd chunk id, XOR the first encrypted byte with `(id & 0xFF) ^ (id >> 8)` before decrypting;
  - the result is a `u32 packed size` plus a zlib stream.
- Mode 3 covers every frame's header, palette, layers, instances and events, every object's header and
  properties, the frame-handle table and the serial number. Protection is flags 2 (encrypted, not compressed).
- A missing string just adds nothing to the key. The developer's older game has no copyright string and
  decrypts fine.

**Build-296 events** (per frame, sub-chunk 0x333D)
- Tagged sections, in file order (all 80 frames): `ER>>` (header), `ERop`, `ERes`, `ERev` (a byte size, then the
  events), and `<<ER` right after the events, at the end of the chunk. `ERes` is easy to mistake for an event
  count, but it holds the same byte size as `ERev` in all 80 frames. Update both when you add events.
- Event header, 8 bytes: `i16 size` (stored negated; all 12,745 here), `u8 conditions`, `u8 actions`,
  `u16 flags`, `u16 event id`. The id is unique within the frame.
- Condition and action header, in order:
  - `size` (i16 for conditions, u16 for actions), `i16 object type`, `i16 number`;
  - `u16 object-info handle`, **only** for object types ≥ 0 and the player (-7). Here 13,060 of the 47,246
    conditions and actions have no such field;
  - `u8 flags` (bit 7 = negated, per Nebula) and `u8 parameter count`.

  A parameter is `i16 size, i16 code`, then the value.
- **Compact forms:** some entries have zero parameters and carry a packed payload instead.
  - The payload is an `i32` index plus a constant. The constant is an `i32` in every compact entry here; Nebula's
    action reader also accepts an f64 when 8 bytes remain.
  - This game uses four: "compare alterable value" (condition -42, with an `i16` comparison before the index; the
    classic form is -27) and "set", "add" and "subtract alterable value" (actions 31, 32 and 33).
  - They make up 7,778 of the 47,246 entries (16%), so a classic parser breaks on most frames.
  - "Activate group" and "Deactivate group" (126 here) also drop the parameter list and carry only a `u16`
    group id.
  - Nebula's readers handle more, and none of it occurs in this game: compact global-value forms, a compact
    "group is activated" condition, shader ids, and "would overlap at X,Y" conditions that reuse the plain
    overlap numbers.
- Handy ids for patching:
  - "Upon pressing key": object type -6, number -1, one parameter with code 14 (`i16` virtual-key code).
  - "Jump to frame": type -3, number 2, one parameter with code 26 (`i32` frame handle).
  - A frame handle isn't the frame's position in the file. Each frame stores its own handle in its 4-byte sub-chunk
    0x334C, and the frame-handle table (0x222B) maps handles to file positions. For example, Cutscene_Testbed is
    the 5th frame in the file but has handle 28.

**The integrity check (Protection, chunk 0x2242)**
- The tools call this chunk "Protection", but it holds nothing except a 4-byte checksum: no key, serial or licence
  data.
- The checksum covers the **raw stored bytes** from the start of the 0x222F chunk header to the start of the
  0x2242 chunk header. The payload is encrypted with the game key (flags 2, so no zlib; the id is even, so no XOR
  byte).
- Here that range is 95 chunks, including the target and editor filenames, the extension list, the object
  definitions, the frame-handle table and all 80 frames. Any edit to events, objects or frames changes the
  checksum. The app header, name, author and copyright before the range, and the banks after it, are outside.
- The formula is what Anaconda calls the "pame" checksum (`make_pame_checksum` in `mmfparser/data/checksum.py`,
  github.com/fnmwolf/Anaconda). It rotates a 32-bit sum left by one and adds each little-endian dword, then each
  leftover byte the same way. Finally it XORs the low byte with 13. Our version:

```python
import struct

def pame_checksum(data: bytes) -> int:
    r = 0
    n = len(data) & ~3
    for (w,) in struct.iter_unpack("<I", data[:n]):
        r = (((r << 1) | (r >> 31)) + w) & 0xFFFFFFFF
    for b in data[n:]:
        r = (((r << 1) | (r >> 31)) + b) & 0xFFFFFFFF
    return (r & 0xFFFFFF00) | ((r & 0xFF) ^ 13)

# value = pame_checksum(dat[offset_of_0x222F_header:offset_of_0x2242_header])
```

- It matches the shipped V1.2 and V1.3 files, our patched file, and Dance of the Goatman, an earlier Fusion game
  (build 292) by the same developer. In all four files, no other chunk boundary works as a start point.
- If the value is wrong, the runtime exits at once with code 0: no window and no message.

**Save file**
- `padresavedata.arr` sits in the game folder, not AppData. It's a KcArray "CNC ARRAY" v2.0 file:
  - a 30-byte header: magic plus NUL; `i16` major and minor version; `i32` X, Y and Z sizes; `i32` flags
    (13 = numeric + base-1 + global);
  - then int32 cells with X varying fastest. 20 x 20 x 1 cells make 1,630 bytes.
- The Array object rewrites it at area intros and on the death screen. The cells hold ammo, the kill total,
  unlocked areas and other progress; we read their meaning from the events that write them.

## Build steps
1. Close the game. Copy the exe, the .dat and `Modules\` to a work folder.
2. **Decode.** Walk the chunks, build the key, decrypt the mode-3 chunks, and parse objects, frames, instances and
   events as above. Our `fusion_game.py` does this. `events_text.py` writes one readable text file per frame, with
   lines like `IF Upon pressing key T -> Jump to frame 'Testbed'`.
3. **Patch** with `dat_patch.py <source.dat> <output.dat>`, which never writes in place:
   1. Decrypt the Title frame's events.
   2. Take an existing "Upon pressing key" condition and "Jump to frame" action from that frame as templates.
      Set the key codes ('T', 'C') and the target frames' handles (from each frame's 0x334C).
   3. Give the two new events ids max + 1 and max + 2, and append them at the end of `ERev`. Add their byte count
      to both `ERes` and `ERev`.
   4. Re-compress with zlib level 6, re-encrypt with the same key (odd-id XOR included), and rewrite the frame
      chunk's size.
   5. Recompute Protection over the new bytes and write the output file.
4. **Before trusting the patcher**, check two things on the untouched source. First, re-encoding a chunk must give
   its original bytes. Second, the stored Protection must equal your formula. `dat_patch.py` asserts the second and
   prints the first for the Title events. The byte-exact re-encode held with CPython 3.12.9's zlib 1.3.1. Another
   zlib build may pack differently, which is harmless once Protection is recomputed.
5. Run the copy from its own folder. It keeps its own save there.

Our scripts aren't published. The facts above, plus the NebulaFD and CTFAK sources, are enough to rewrite them.
A patched .dat contains the whole game, so share a patcher, never the file.

## Verification
- **Round trip:**
  - all 2,368 mode-3 chunks decrypt and inflate to exactly their declared sizes; zlib's Adler-32 check makes a
    false pass practically impossible;
  - building the key in the old order decrypts none of them;
  - the 2,366 mode-3 chunks in frames and objects re-encode byte for byte with zlib level 6 and the same key.
- **Parser:** every one of the 12,745 events and 47,246 conditions and actions ends exactly on its size field.
- **Patched file** (re-checked 2026-10-29 for this note):
  - it decodes to 12,747 events;
  - its decoded text differs from the source only in the Title frame, by the two new events;
  - outside the Title frame chunk, the two files differ only in the 4 Protection bytes.
- **In game** (2026-10-29), launching the patched copy:
  - the title screen loads;
  - T opens Testbed, the developer's 2000x2000 sandbox, with the player's debug hitbox drawn;
  - Escape opens Testbed's placeholder menu, and its QUIT returns to the title;
  - C plays Cutscene_Testbed, an unused cutscene template.

  Afterwards the real install and its save were byte-compared: unchanged.
- **Diagnosing the silent exit:** the oracle was whether the process was still running shortly after launch.
  Before we knew about the checksum, two test builds both died:
  - one changed a single key code, keeping the size;
  - one kept the event content identical and only re-compressed it at zlib level 1.

  So the check covers the stored bytes, not the decoded content.
- **Not verified:**
  - the Protection rule on other developers' games or on other builds;
  - edits to the image or sound banks (outside the range, but untested);
  - patching a packed build, where the data sits inside the exe;
  - edits that add objects or qualifiers to a frame. The `ER>>` header counters were left unchanged, because the
    new events only reuse condition and action types the Title frame already had;
  - Nebula's .mfa, which we never opened.

## Gotchas
1. **`um scan` says "Unknown native engine" and suggests proxy-DLL hooks.**
   - **Cause:** `um scan` has no Clickteam Fusion signature.
   - **Fix:** look for `Modules\mmfs2.dll` with `.mfx` and `.sft` files. mmfs2.dll's FileVersion gives the build
     (3.0.296.9 = build 296). The logic is event data, so take the data route.
2. **The exe contains no game data.**
   - **Cause:** an "Unpacked EXE" build: the exe is the stock runtime, and everything is in `<game>.dat`.
   - **Fix:** parse the .dat (`wwww`, then `PAMU` at 0x20). NebulaFD, given the exe path and Auto-Detect, found the
     .dat and read it as CCN data (its log says `Fusion Build: 296`).
3. **Frame events, layouts and object properties look like noise.**
   - **Cause:** standard Fusion mode-3 encryption.
   - **Fix:** build the key from name + copyright + editor filename, in that order for builds above 284. Test a
     key by inflating: only the right one gives the declared size and a valid Adler-32.
4. **After a game update, every encrypted chunk differs on disk.**
   - **Cause:** the editor filename is part of the key. V1.3's project file was renamed, so the key changed.
   - **Fix:** diff the decrypted content. V1.2 to V1.3 turned out to be one level's object placement and the
     version text.
5. **A classic Fusion event parser overruns or misreads events.**
   - **Cause:** build 296's shorter headers (an 8-byte event header, no object-info field for system objects) and
     its zero-parameter compact forms.
   - **Fix:** follow Nebula.Core's build-296 readers, and assert that every event, condition and action ends on
     its size field.
6. **A modified .dat won't start until its integrity checksum is updated.** It exits at once with code 0, and shows
   no window or error.
   - **Cause:** the Protection checksum (0x2242) over the raw bytes from 0x222F to 0x2242. Even re-compressing
     identical content changes it.
   - **Fix:** after all edits, recompute pame over that range, encrypt the 4 bytes with the game key and write them
     back. First check that your formula reproduces the untouched file's value.
7. **Nebula never gets past its first prompt when an agent runs it.**
   - **Cause:** it's driven by interactive Spectre.Console menus (arrow keys, space, Enter), and we didn't find a
     headless mode.
   - **Fix:** host it in a Windows pseudo-console (ConPTY).
     - Our `ctypes` driver keeps a minimal VT screen model and waits for each prompt.
     - After moving to each choice, it checks that the highlighted line is the one it wants before toggling or
       confirming. In multi-select menus it also checks the ticked set before Enter.
     - There's no visible window.
     - Choices: Auto-Detect, then Asset Dumper (images, sounds), then MFA Parser.
8. **Under ConPTY, the child still talks to the driver's pipes.**
   - **Cause:** when the driver's own stdio is redirected, the child inherits those handles instead of the
     pseudo-console.
   - **Fix:** set `STARTF_USESTDHANDLES` with null std handles in the `STARTUPINFOEX`.
9. **Nebula opens its input read/write.**
   - **Cause:** its file reader defaults to read/write access (NebulaFD issue #61, open on 2026-10-29). It fails on
     write-protected folders, and it holds write access to whatever you point it at.
   - **Fix:** point it at a writable copy. Ours was hash-identical after the run.
10. **Nebula's build-296 output is reliable for assets, not for events.**
    - **Cause:** its notes and issues list known build-296 limits:
      - group names become "Group N" and loops get numbered names;
      - some events come out wrong, and global events aren't written;
      - odd-width images can break in the .mfa (#60).
    - **Fix:** take images and sounds from the dump, and decode the events yourself. Here that gave 1,760 PNGs and
      24 WAVs, all structurally valid (PNG CRCs and pixel counts, WAV headers).
11. **The dump has no fonts.**
    - **Cause:** the 3 fonts are LOGFONT references to Windows' raster "Terminal" font, not embedded files.
    - **Fix:** there's nothing to extract. To render that font, use GDI; PIL, GDI+ and browsers can't draw .fon
      fonts.

## Assets
None. The two new events are built from bytes of the Title frame's own events.

## Cost and time
Recon took one session on 2026-10-28. A second session, from that evening until past midnight, made the Nebula
dump, the decoder and the mod; the mod was tested in game at 00:55 on 2026-10-29. No paid APIs.

## Open questions
- Does the Protection range hold for other Fusion games? So far it is checked on builds 292 and 296, both by this
  developer.
- Does the runtime ignore edits to the image and sound banks after Protection?
- Unknown chunks, which Nebula also logs as unknown:
  - 0x2251 holds 2057, probably the en-GB locale id;
  - 0x224D, 0x225C and 0x225D are unidentified.

  0x224F, which starts with the build number, is Nebula's `EngineVer`.
- `um scan` could learn a `clickteam-fusion` key from `mmfs2.dll` with `.mfx` and `.sft` files.

Credits: NebulaFD (AITYunivers) for the build-296 event layouts and the asset dump. CTFAK 2.0 for the cipher.
Anaconda for the pame checksum.
