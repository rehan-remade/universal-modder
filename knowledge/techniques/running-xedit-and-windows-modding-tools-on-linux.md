---
kind: technique
title: "Running xEdit (and other Delphi/Windows modding tools) on Linux: Wine/Proton patches"
tags: [wine, proton, xedit, sf1edit, delphi, riched20, win32u, syscall, starfield, bethesda, linux, tooling, patching]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - "https://gitlab.winehq.org/wine/wine"
  - "https://github.com/TES5Edit/TES5Edit"
  - "https://github.com/j00ru/windows-syscalls"
---

# Running xEdit (and other Delphi/Windows modding tools) on Linux: Wine/Proton patches

> xEdit ships as a Delphi VCL application, and its 64-bit builds (e.g. `SF1Edit64.exe`) hit two Wine
> gaps that are not fixed by swapping prefixes or Proton versions: the RichEdit control does not
> implement `tomCharFormat` range movement, and `win32u` leaves `NtUserSetMonitorWorkArea` (syscall
> `0x1570`) as a stub. This note records the fixes — a `riched20` patch for xEdit itself, a
> `win32u` patch for the Starfield Creation Club crash — plus the prefix, build and deploy steps
> that made them work. All of it is local Wine/Proton tooling; no game files or DRM are involved.

## When to use it

- A Delphi/Windows modding tool crashes under Wine/Proton with an access violation inside its own
  code (not an obvious missing DLL), and you want to know whether it is a Wine gap or a real bug.
- You need xEdit to build a table of contents from bold/italic runs (its `MoveEnd(tomCharFormat, 1)`
  path) and it faults.
- You are packaging a Wine patch for a friend or a Proton prefix (`win32u` syscall additions, PE-vs-Unix
  deployment) and want the pitfalls up front.
- Something raises an access violation at a *syscall index* (e.g. `0x1570`) in a DLL — that number is
  the tell that a `win32u` stub is being called.

If the tool runs fine stock, none of this is needed — try plain Wine and a `win64` prefix first.

## How

### Step 0 — get the prefix architecture right

A 64-bit exe run through a 32-bit (WoW64) prefix is the single most common cause of a page fault
that looks like a tool bug. Recreate the prefix as 64-bit:

```bash
WINEPREFIX=~/.wine-xedit WINEARCH=win64 wineboot -u
WINEPREFIX=~/.wine-xedit wine SF1Edit64.exe -SF1
```

That alone resolved a `page fault on read access to 0x00006ffffffee000 at address 0x5d6755` in
`sf1edit64` where the fault address sat in the WoW64/heap-translation range.

### Step 1 — patched Wine (riched20 + win32u)

Two patch sets are applied to a Wine *source* tree, built and deployed as system Wine **and** as a
Proton prefix runtime:

| Patch | Files | Fixes |
|---|---|---|
| `riched20-tomCharFormat.patch` | `dlls/riched20/richole.c` (+116 lines) | xEdit/SF1Edit crash in `ITextRange::MoveEnd(tomCharFormat, ±n)` |
| `ntusersetmonitorworkarea.patch` (11.10) / `-11.0.patch` | `dlls/win32u/sysparams.c`, `dlls/win32u/win32u.spec`, `dlls/win32u/win32syscalls.h` | Starfield Creation Club crash: `NtUserSetMonitorWorkArea` was a stub |

- **riched20.** `tomCharFormat` moves the range end to the end (positive count) or start (negative
  count) of the current character-formatting run. The implementation adds a `case tomCharFormat:` to
  `textrange_moveend()`, walking runs with `run_next_all_paras()` / `run_prev_all_paras()` and
  comparing `CHARFORMAT2W` fields. It ships a conformance test (`test_MoveEnd_charformat` in
  `dlls/riched20/tests/richole.c`). xEdit calls exactly this to assemble its TOC from bold/italic runs.
- **win32u.** The Starfield crash was an access violation at `0x1570` in `SFHighPriorityLauncher.dll`.
  `0x1570` is the syscall index of `NtUserSetMonitorWorkArea`, which Wine listed as
  `@ stub -syscall` in `win32u.spec` and as `SYSCALL_ENTRY( 0x1570, NtUserSetMonitorWorkArea, 0 )`.
  The patch implements it (`HMONITOR`, `const RECT *`) in `sysparams.c`, changes the spec line to
  `@ stdcall -syscall NtUserSetMonitorWorkArea(long ptr)` and the syscall entry's arg-size to `16`,
  and adds `test_SetMonitorWorkArea()` to `dlls/user32/tests/monitor.c`. Syscall numbers/ordering are
  cross-checked against the public per-Windows-build tables from the `windows-syscalls` project (j00ru).

### Step 2 — build and run the module tests

```bash
./configure && make -s -j"$(nproc)"
make -C dlls/riched20 && make -C dlls/riched20/tests
wine dlls/riched20/tests/x86_64-windows/riched20_test.exe richole
make -C dlls/win32u
```

Wine conformance requires the test to pass on real Windows first; run it under Wine after the fix and
keep the delta. CI uses `winetest.exe` (not `make test`) plus an X virtual framebuffer.

### Step 3 — deploy

- Patched artefacts live under `/opt/wine-patches/` (system Wine) and `/opt/wine-patches/proton/`
  (Proton): `win32u.so`, `win32u.dll`, `riched20.dll`.
- Stock originals are kept alongside as `.stock` files for rollback.
- A pacman hook (`/etc/pacman.d/hooks/99-wine-patches.hook` → `/usr/share/libalpm/scripts/deploy-wine-patches.sh`)
  re-copies the patched files after every Wine package update.
- **Always deploy a `win32u` `.so` and `.dll` together.** `riched20` is PE-only (`riched20.dll`, no
  Unix counterpart).

## Verification

- The `riched20` patch ships a conformance test (`test_MoveEnd_charformat`) that exercises
  `MoveEnd(tomCharFormat, ±1)` from the start, inside, and past a formatted run, forwards and
  backwards — the same call xEdit makes.
- The `win32u` patch ships `test_SetMonitorWorkArea()` (set, query, and restore a monitor work area).
- The end-to-end oracle is the tool: xEdit stops faulting while building its TOC, and Starfield's
  Creation Club launcher stops crashing.
- **Not verified here:** the upstream MR was not submitted; the 64-bit prefix fix was confirmed on the
  local machine only, not reduced to a minimal reproducer for a bug report.

## Gotchas

1. **`page fault … at address 0x5d6755 in sf1edit64`, faulting address in `0x00006fff…` range.**
   **Cause:** a 64-bit exe was launched through a 32-bit/WoW64 prefix. **Fix:** recreate the prefix
   with `WINEARCH=win64`.
2. **SF1Edit crashes in its TOC/bold-italic path.** **Cause:** Wine's `riched20` did not implement
   `tomCharFormat` in `ITextRange::MoveEnd`, so xEdit's `MoveEnd(tomCharFormat, 1)` faulted.
   **Fix:** `riched20-tomCharFormat.patch`; deploy `riched20.dll`.
3. **Starfield Creation Club crashes with an AV at `0x1570` in `SFHighPriorityLauncher.dll`.**
   **Cause:** `0x1570` is the `NtUserSetMonitorWorkArea` syscall index, which Wine stubbed.
   **Fix:** `ntusersetmonitorworkarea.patch` (+ the `-11.0` variant for Proton). The address value
   *is* the syscall index — useful symptom-to-cause shortcut.
4. **A patched Wine DLL loads but crashes immediately.** **Cause:** a PE `.dll` was deployed without
   its matching Unix `.so` (or vice-versa). **Fix:** deploy `win32u.so` **and** `win32u.dll` together;
   only `riched20` is PE-only.
5. **A Wine update silently reverts the patch.** **Cause:** the package manager overwrites the
   patched files. **Fix:** keep the pacman hook and the `.stock` backups; re-verify after updates.
6. **`fixme:richedit:editor_handle_message EM_SETMARGINS / EM_SETTYPOGRAPHYOPTIONS / EM_SETLANGOPTIONS:
   stub`, `IRichEditOle_fnSetHostNames stub`, `uxtheme:DrawThemeTextEx unsupported flags`,
   `BufferedPaintSetAlpha Stub`, `EnableNonClientDpiScaling stub`.** **Cause:** unimplemented cosmetic
   RichEdit/uxtheme/system calls that xEdit makes while drawing. **Fix:** ignore — these are noise in
   the log, not the crash. Look further down the log for the `Unhandled page fault` line and its
   backtrace.
7. **`fixme:oleacc:find_class_data unhandled window class: L"TButton"/"TPageControl"`.** **Cause:**
   Wine accessibility (oleacc) has no mapping for Delphi VCL window classes. **Fix:** cosmetic; ignore
   unless the tool is an accessibility client (it is not).

## Seen in

- A Wine development tree with local patches (unpublished): `pagefault_xedit.txt`,
  `riched20-tomCharFormat.patch`, `ntusersetmonitorworkarea.patch`,
  `ntusersetmonitorworkarea-11.0.patch`.
- xEdit source and build (local, unpublished): xEdit 4.0.0, Delphi 12 CE,
  `BethWorkBench.groupproj`, `LiteDebug` config without DevExpress.
- Syscall table reference: the public `windows-syscalls` tables (j00ru, nt + win32k, per Windows build).

## Open questions

- Upstream submission: the `riched20` and `win32u` patches were not sent to
  `gitlab.winehq.org/wine/wine` (MR or `wine-devel@lists.winehq.org`). Both need a conformance test
  that passes on real Windows first.
- Whether the Starfield `SFHighPriorityLauncher.dll` path needs anything beyond `NtUserSetMonitorWorkArea`
  (the CEF/Chromium component was suspected too) was not fully traced.
- The exact game-build/Proton-version combinations that require the `-11.0` vs `11.10` patch split.
