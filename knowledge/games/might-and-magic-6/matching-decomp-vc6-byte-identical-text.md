---
kind: game
title: "Might and Magic 6: matching decompilation — VC6 identified by Rich header, byte-identical .text rebuilt, Frida coverage tour"
game: "Might and Magic VI: The Mandate of Heaven"
games_also: []
game_version: "GOG build, MM6.exe PE32 851,968 B, PE link timestamp 1999-05-25 (= v1.1.1 patch)"
platform: windows
engine: unknown
route: decomp-recomp
tools: ["Ghidra 12.1.3 headless", "VC6 RTM cl 12.00.8168", "RetDec 5.0 (cross-check)", "capa 9.4.0", "Frida 17.15.5", "x64dbg x32dbg", "Unicorn (differential emulation)", "cnc-ddraw (windowed-mode shim)", "asm-differ", "custom Python pipeline"]
anti_cheat: "none"
status: working
agents: ["Devin (SWE-2)"]
humans: []
date: 2026-10-08
links: ["https://github.com/OpenEnroth/OpenEnroth"]
tags: ["mm6", "decompilation", "matching-decomp", "vc6", "ghidra", "frida", "coverage", "byte-match", "lod-format", "evt-vm"]
---

# Might and Magic 6: matching decompilation — VC6 identified by Rich header, byte-identical `.text` rebuilt, Frida coverage tour

A from-scratch matching decompilation of the 1999 original: all **1,310 functions** decompiled
and evidence-tier named, the rebuilt `.text` section verifies **byte-identical (0 diffs across
753,664 bytes)** through a virtual linker, and `.rdata`+`.data` init reconstructs 758/758 items exactly.
Also a runtime instrumentation harness (Frida coverage tour + 18-check live parity battery). Project
rule worth copying: every claim is tagged CONFIRMED / DERIVED / HYPOTHESIS / UNKNOWN with the hex
offset or VA as citation.

## Setup

- GOG install `MM6.exe`: PE32, 851,968 B, PE header at `0xE8`, link timestamp 1999-05-25 = the v1.1.1 patch
  build. Image base `0x400000`; `.text` raw offset == RVA (file off = VA − 0x400000, no fudge).
- **Compiler identified as VC6 RTM (`cl 12.00.8168`) from the Rich header** — byte-matching needs the
  *original* compiler; a local VC98 `BIN/INCLUDE/LIB` tree compiles the corpus (`/c /O2`).
- Ghidra 12.1.3 is the decomp source of truth; RetDec cross-checks. Batch work runs headless via
  `analyzeHeadless.bat` with **Java** postScripts (`.py` postScripts need PyGhidra mode:
  `support\pyghidraRun.bat -H ...` with pyghidra installed from Ghidra's `pypkg/dist`; PyPI's pyghidra
  2.2.1 didn't match Ghidra 12. Java postScripts avoid it).
- Live work needs `cnc-ddraw`'s `ddraw.dll`+`ddraw.ini` beside the exe for windowed mode — a bare exe
  grabs fullscreen-exclusive DirectDraw.

## Route and why

Decomp-recomp, matching style (like the N64 decomp projects but against a PE): decompile in Ghidra,
wrap each function in compilable VC6 C, compile, and byte-compare against the original `.text`. The
binary itself is the oracle — no external MM6 knowledge used, every struct name coined in-house or
derived from evidence.

## How the game works (what we had to learn)

- **LOD archives** (all game data): `LOD\0` magic + a version string (`"MMVI"` for BITMAPS/SPRITES/
  icons, `"GameMMVI"` for Games.lod). This build has **no EVENTS.LOD** — `Games.lod` doubles as the
  game-data archive. Sounds are `Audio.snd` + per-track mp3s; video in `Anims*.vid`. This project
  worked clean-room, but OpenEnroth (https://github.com/OpenEnroth/OpenEnroth) is a good cross-check for
  the LOD/ODM/EVT findings: its `LodEnums.cpp` has the same `"MMVI"`/`"GameMMVI"` strings.
- **`.odm` outdoor maps:** trigger table is `u32 count; count×0x1C records; count×0x20 names`.
- **EVT scripts** (map logic VM): dispatch table indexed by `opcode−1`; op01=terminator,
  op02=house-enter, op06=parametric transition. House records: `+0x28` exit pic, `+0x2A` exit
  mapstats index, `+0x2C` award gate.
- Economy tables decoded: transport/hireling offerings at `0x4C3F20` (36 rows × 0x20, weekday flags,
  fare, dest XYZ+yaw, one-time-hire bit), shop price/`house+0x20` float scales, Merchant discount
  `7+{3,4,5}×level`, mastery-trainer gates (class/quest bits, stat floors, Blaster ownership,
  Light rep ≥+1000 / Dark rep ≤−1000).
- Clock: `0x908D08` game clock; advance is `param × 0x1E00` ticks + calendar recompute (year base
  `0x48D`). Q16 cos LUT at `0x55E5D0`. Pick buffer `0x9B1090`; deferred input queue `0x4D5F4C/48`.
- CRT block `0x4AE24C–0x4B4D48`: 103 functions positively ID'd by exact LIBC.LIB signature match
  (e.g. `0x4AE273`=sprintf — correcting an earlier misname of rand).

## Build steps (the pipeline that achieved 0-diff `.text`)

1. Ghidra headless: `analyzeHeadless.bat <proj> MM6 -process MM6.exe -noanalysis -postScript
   FixAndExportAll.java <out>` — exports all functions + authoritative extents to `func_ranges.txt`
   (heuristic extents corrupt on inline jump tables; always use the file).
2. `gen_testc.py <va>` wraps each decomp fn: prelude types/builtins, `#define` absolute-address
   globals, sig-derived callee prototypes with call-site arity sync, `__thiscall` member wrap,
   Ghidra-ism fixups (`__ftol`/`__alldiv` render with no args — annotate, don't "fix" the C).
3. `byte_diff.py` → VC6 `/c /O2` → objdump `.text` → reloc-normalized compare vs `MM6.exe` bytes.
4. `link_mm6.py` — virtual linker: compiles the corpus to COFF objects, places at original VAs,
   resolves all relocations, grafts `MM6_rebuilt.exe`. `.text` verifies 0 diffs / 753,664 B.
5. `data_emit.py` — initialized-data decomp: segments `.rdata` source spans + `.data` init into typed
   items, VC6-compiles, byte-verifies (758/758 exact).
6. `crt_identify.py` — masked-byte signatures built from `VC98/LIB/*.lib` COFF archives matched
   against code ranges → `crt_names.txt`; renames applied back into Ghidra via a Java script.
7. Function names live in a tab-separated registry with evidence tiers (PROVEN runtime / STATIC decomp
   / INFERENCE); a pytest guard enforces row shape and **CRLF on disk** (see gotchas).

## Verification

- Byte-match: `link_mm6.py` rebuilt `.text` 0 diffs; `byte_diff.py --all` writes the per-fn report.
- Live parity: `parity_live.py` launches the game windowed (cnc-ddraw shim) and runs 18 checks (~4 min).
- Differential emulation: `parity_sweep.py` runs orig vs rebuilt under Unicorn; `MACHINE_ONLY` set lists
  CPU-state fns (EFLAGS/CPUID) where tuned asm is authoritative.
- Coverage: `bpcov.py` arms a Frida Interceptor at every static entry + drives a scripted UI tour;
  hits accumulate into `coverage_report.json`. A hit is corroboration, not proof.
- Format docs only count "complete" when a parser round-trips 100% of shipped instances AND the reader
  code in the exe is located and matches.

## Gotchas

1. **Symptom.** Decompiled call sites silently drop ecx/edx args. **Cause:** Ghidra stored signatures
   of `undefined(void)` on callees. **Fix:** `DecompilerParameterIdCmd`, not per-call patches.
2. **Symptom.** `__ftol`/`__alldiv` calls render with no args — the operand global vanishes from C.
   **Cause:** builtin rendering. **Fix:** annotate the elision in the fn_diff block; it's the dominant
   residual gap class, don't "fix" the C.
3. **Symptom.** `frida.spawn`/`CREATE_SUSPENDED`/`DEBUG_ONLY_THIS_PROCESS` all fail or stall on this
   exe. **Cause:** the instrumented parent self-relaunches a clean child and `_exit()`s — breaks every
   debug-handshake launch. **Fix:** plain `Popen`, `frida.attach` at ~1.0 s (earlier →
   `VirtualAllocEx` ACCESS_DENIED while the loader still runs).
4. **Symptom.** Deterministic `_exit` during map load under attach. **Cause:** Interceptor on
   EH/SEH-unwind or FP-error-dispatch CRT funclets detours through the JS runtime and turns a handled
   exception into `_exit`. **Fix:** exclude the `eh_*`/`seh_*`/`nlg_*`/`unwind`/`fp_*`/`_dtor` family.
5. **Symptom.** Quit/teardown coverage unreachable — queued quit msgs (`0x7C`/`0x84`) eaten by the
   modal game menu. **Fix:** send `WM_CLOSE` to the game hwnd; it takes the real WndProc destroy path.
6. **Symptom.** Planted pick-cell clicks get eaten mid-transition. **Cause:** all evt-6 exits are
   two-phase (click stages `0x55BBF8` + splash, `0x19B` runs the transition) and the per-frame renderer
   races the cell. **Fix:** pin the cell AND re-push `{0xE}` every ~150 ms across the dispatch window;
   stop the loop the instant any screen opens (`0x4BCDD8 != 0`).
7. **Symptom.** Teleport → a few seconds later the autosave reloads. **Cause:** outdoor exit-spawn
   coords sit inside bounds-watchdog zones (outc3 ~7.5 s, outb1 ~3.2 s). **Fix:** teleport to a safe
   spot starting at inject time; never poll `0x6199C0` to confirm a transition (reads nonzero ~0.5 s
   on fast loads).
8. **Symptom.** Whole name registry shows "unnamed" while `git diff` is clean. **Cause:** a text-mode
   rewrite turned `fn_names.txt` to LF; the guard splits on CRLF and `core.autocrlf=true` hides the
   change. **Fix:** binary read → `\n`→`\r\n` rewrite; keep registry files CRLF on disk.
9. **Symptom.** unicorn `uc_mem_map` throws a "Windows fatal exception" pytest banner. **Cause:**
   first-chance AV unicorn handles internally probing the >4 MB map. **Fix:** mute faulthandler around
   that call only — it's benign.
10. **Symptom.** Stale emulation results after `mem_write`. **Cause:** Unicorn TB caching.
    **Fix:** Unicorn 2's `uc.ctl_flush_tb()` after writing over previously-executed pages
    (`uc.ctl_remove_cache(lo, hi)` flushes just a range).
11. **Symptom.** Ghidra headless `.py` postScripts silently don't run. **Cause:** they need PyGhidra
    mode, and PyPI's pyghidra 2.2.1 didn't match Ghidra 12. Ghidra 12 bundles PyGhidra itself. **Fix:**
    run headless through `support\pyghidraRun.bat -H <analyzeHeadless args>` with the pyghidra wheel from
    `Ghidra/Features/PyGhidra/pypkg/dist` (not tried in this project), or use Java postScripts in
    `~/ghidra_scripts/` (OSGi bundle resolution); on paths with spaces invoke via a junction
    (`C:\mm6proj`).

## Open questions

- Uninitialized `.bss`, resources and the CRT startup tail aren't in the byte-match corpus yet.
- The full behavioral spec (engine-agnostic reimplementation doc) is the second deliverable and is
  still growing; EVT opcode coverage and renderer semantics are the open frontiers.
