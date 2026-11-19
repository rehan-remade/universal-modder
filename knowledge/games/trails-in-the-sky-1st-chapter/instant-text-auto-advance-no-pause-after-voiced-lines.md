---
kind: game
title: Auto-advance with no pause after voiced lines (proxy XAudio2_9.dll)
game: Trails in the Sky 1st Chapter
games_also: []
game_version: 'Steam demo (app 3902570), sora_1st.exe PE timestamp 2025-11-07, Windows 11. User reports it also works on the full game (app 3375780, global build); exact full-game version not recorded.'
platform: windows
engine: native
route: native-hook
tools: ["MSVC 14.51 (VS 18 Build Tools: cl, ml64, rc, link)", "Python 3.14 + capstone 5.0.7 + pefile 2024.8.26", "ctypes ReadProcessMemory peeker (read-only)"]
anti_cheat: none found by um scan (single-player)
status: working
agents:
- Cursor (Claude Opus 5.5)
humans: []
date: '2026-10-18'
links: ["https://github.com/Hinkiii/sora1looseload"]
tags: [dialogue, auto-advance, quality-of-life, proxy-dll, xaudio2, aob-signature, call-site-retarget, falcom]
---
# Auto-advance with no pause after voiced lines (proxy XAudio2_9.dll)

> A proxy `XAudio2_9.dll` for Trails in the Sky 1st Chapter (Falcom's in-house C++ engine). It removes the
> pause after voiced lines when auto-advance is on. The game holds a voiced line 0.4 s after the voice ends
> and keeps every line up at least 1.8 s, both multiplied by an auto-speed factor. The hook advances once the
> voice has played and stopped and the text is fully shown. It runs in the real game (demo): while the user
> played, the DLL's own log recorded about 70 early advances. Typical lines saved 0.39 s; short ones up to 1.19 s.

## Setup
- Demo exe: x64 MSVC, ASLR, RTTI names intact, `.pdata` present, **no `.bind` section (no SteamStub)**.
  Engine source paths in strings (`...\sora\...`, `...\fdk\...`), i.e. Falcom Developer Kit.
- Data lives in FPAC archives (`pac\steam\*.pac`): `'FPAC'`, u32 count, u32 header size, u32 unknown, then
  count × {u64 hash, u64 name offset, u64 size, u64 offset}. Tables inside are plain `#TBL`.
- Saves: `%USERPROFILE%\Saved Games\Falcom\Trails in the Sky 1st Chapter\`. Back them up with `um backup`
  before the first modded launch.
- `um` wants `uv`. Without it: `python -m um ...` with `PYTHONPATH=<universal-modder repo>`. `um kb new` also
  needs PyYAML (install it in a venv).

## Route and why
`native-hook`. The data route was checked first: `table.pac` / `table_en.pac` hold no auto-advance timing.
The wait comes from two float constants in `.rdata`, read by one function.

Delivery is a proxy `XAudio2_9.dll`. The exe imports it statically (ordinals 2, 3, 4), it isn't a KnownDLL,
and the name is free: the community loose-file loader
([sora1looseload](https://github.com/Hinkiii/sora1looseload)) uses `xinput1_4.dll` and ReShade uses `dxgi.dll`. The
proxy forwards all 10 exports with the system DLL's exact names **and ordinals** (MASM `jmp [table]` stubs
plus a `.def` with `@n`).

Instead of an inline detour, the hook retargets the function's **single `E8` call site** to a relay page
allocated within ±2 GB (`FF 25` + absolute address). The original function stays byte-identical and is called
first.

## How the game works (what we had to learn)
Demo RVAs. The DLL derives every one of these from the matched signature bytes at runtime.
- **Message window update** (0x43ed40) runs every frame. It adds dt to a per-line timer (`msg+0x18`) while
  the line is active. The auto toggle (keyboard E) flips a global flag, plays a sound effect and resets that
  timer. It calls the **auto-advance check** (0x43f1f0, `bool(msg, speaker)`) from exactly one call site
  (0x43f15a, followed by `test al, al`). When that returns true it calls the advance vfunc (vtable +0x50).
- **Auto-advance check:** `s` is the speed factor (`G2+0x188`, 1.0 at the default setting).
  - While the voice plays, or while the speaker is busy (`speaker+0x2498 != -1`): deadline = timer + 0.4·s.
  - While the text is still typing: deadline = total chars × (0.07 or 0.14, chosen by a flag) × s.
  - The line advances only when the text is fully shown AND timer ≥ max(deadline, 1.8·s).
- **Voice query** (0x411310, `bool(unused, voiceId)`) goes through the XAudio2 audio implementation's
  vtable. It is read-only, so calling it again from the hook is safe.
- **Fields.** Globals: `G1 = *(exe+0x905e38)` with the auto flag at `G1+0x5dc23a`; `G2 = *(exe+0x905e50)`
  with the forced-auto flag at `+0x18d`. Message: voice id `+0x14` (-1 = none), timer `+0x18`, deadline
  `+0x1c`, a no-auto flag (`[+8] & 0x40`), text widget via vfunc +0x58 (a leaf getter of `+0xc8`). Text
  widget: chars shown `+0x474`, total chars `+0x38c`.
- **Line close** (0x43d3d0) fades the voice out over 0.1 s and sets the voice id to -1. The constructor and
  reset zero the timer and deadline together as one qword.

## Build steps
1. `src\build.cmd`: calls `vcvars64.bat`, then `ml64` (thunks), `rc` (version resource), `cl /O2 /MT`, and
   `link /DLL /DEF:exports.def`. It also builds `selftest.exe`.
2. Copy `XAudio2_9.dll` and `sky1st_instant_auto.ini` next to `sora_1st.exe`. Uninstall by deleting them.
3. Hook rule: call the original first. Only turn "wait" into "advance" when all of these hold: auto (or
   forced auto) is on, the line isn't flagged no-auto, the voice was **seen playing on this line**, the voice
   and speaker are now idle, and the text is fully shown. Per-line state is keyed by message pointer and
   reset when the voice id changes or the timer goes backwards.

## Verification
- Offline: the signature matches exactly once (Python and C++). `selftest.exe` copies the exe's sections
  into private memory without running any game code, runs the DLL's real locator on them (18 values
  checked), then drives the hook with fake message, speaker and global objects across 11 scenarios. It also
  simulates an exe whose code is unreadable at load and an unsupported build.
- In game (demo): the user played with `Log=2`. The log shows the install line, then about 70 lines like
  "advanced at 2.18 s; game would wait until 2.57 s". The savings match the model: about 0.39 s on long lines
  (the 0.4 s tail minus a frame) and up to 1.19 s on short lines (the 1.8 s minimum).
- **Build-equivalence oracle:** the loose-file loader (sora1looseload: Nexus mod 28, MIT, source on GitHub)
  targets the full game. Its three global-build signatures each match the demo exactly once; its CLE
  (Chinese/Korean) signature doesn't. So the demo is the same code as the full game's global build. Public signatures from another mod
  are a cheap way to check whether your build matches theirs.
- Full game: the user reports the mod works there. That's their report; the agent didn't see a full-game log
  or record the version.
- NOT verified: Proton/Steam Deck, the CLE build, and the retry path against a real SteamStub exe.

## Gotchas
1. **"About 1 s" is two rules.** Users notice roughly a 1 s pause. **Cause:** a 0.4 s tail after the voice
   ends, plus a 1.8 s minimum per line. **Fix:** override both, but only once the voice has finished.
2. **Voice clips can start a few frames after the line opens.** "Advance when nothing is playing" would skip
   a line before its clip starts. **Fix:** require the voice to have been seen playing on this line. Unvoiced
   lines (id -1) keep the game's timing unless the user opts in to scaling it.
3. **Two "voice active" signals.** The game's check treats the line as playing if either the speaker-busy
   field is set or the sound query says playing. Watching only the query could advance a line while the
   speaker is still busy. **Fix:** treat either one as playing, the same as the game does.
4. **Leaf functions have no `.pdata` entry.** The text getter is one. A lookup that only uses `.pdata` returns
   nothing for it. **Fix:** fall back to disassembling until `ret` or `int3`.
5. **Full game DRM is unknown.** A forum post says the full game "uses Steam DRM" (the demo is DRM-free). If
   the exe is SteamStub-wrapped, `.text` is encrypted during `DllMain`, so the scan would fail. **Fix
   (hedge):** if the signature isn't readable at load, a thread retries every 0.5 s for 60 s and patches once
   the stub has decrypted the code. The DRM itself runs untouched. Dialogue can't be open that early, so the
   4-byte patch can't race the call.
6. **Agent environment.** Cursor's Glob and Grep tools don't search outside the workspace, so use `rg` in the
   shell. PowerShell mangles `rg` patterns that contain `"` or `\(`, so filter in Python instead.
7. **Publishing on Nexus (2026 rules).** AI-written code needs the "AI-Generated Content" tag, and AI-written
   page text needs "AI Media". Claims must be backed by evidence or a technical explanation, so put the log
   numbers on the page. This game's Nexus section has a single category, Miscellaneous.

## Assets
None.

## Cost and time
One session. Static analysis (finding the check via RTTI class names, xrefs and the float constants it
reads) took most of it. Build, offline tests and release packaging were short.

## Open questions
- Is the full game's exe SteamStub-wrapped? It works there per the user, but a full-game log would show
  which path ran: "installed:" right after load, or after a "retrying" line. A hint: sora1looseload scans for
  its signatures once, from a thread started in `DllMain`, with no retry, and full-game mods depend on it. So
  the full game's code is probably readable at load, but only a log settles it.
- Proton needs `WINEDLLOVERRIDES="xaudio2_9=n,b"` (untested).
- Possible follow-ups: an instant-text option (skip the typing) and a per-speaker delay.
