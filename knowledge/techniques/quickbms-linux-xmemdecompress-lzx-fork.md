---
kind: technique
title: "QuickBMS on Linux: the XMemDecompress/LZX buffer-reuse bug and three local patches"
tags: [quickbms, lzx, xmemdecompress, xbox360, myalloc, buffer-reuse, openssl3, mingw, nfs-shift, bff, linux, patches]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - "https://aluigi.altervista.org/quickbms.htm"
---

# QuickBMS on Linux: the XMemDecompress/LZX buffer-reuse bug and three local patches

> QuickBMS (aluigi, v0.12.0, unmaintained since 2022) reliably extracts Xbox 360 XMemDecompress/LZX
> containers on Windows because the official build statically links Microsoft's XDK
> `XMemDecompress`. Built from source on Linux, or used with its bundled libmspack fallback, it hits a
> **buffer-reuse bug**: `myalloc()` returns a reused buffer without updating `*currsize`, so the LZX
> decoder reads a stale (too-large) size and aborts with
> `uncompressed data (-1) bigger than allocated buffer`. Three local patches (against aluigi's
> official 0.12.0 source) fix that plus two build
> blockers (OpenSSL 3.x, x86-only Makefile guards). This note records the bug mechanism and the exact
> patches.

## When to use it

When you need QuickBMS working **on Linux** (or building from source at all) for **LZX/XMemDecompress**
archives — the concrete case here is NFS Shift `.BFF` archives, whose entries are TYPE=2
XMemDecompress (LZX window 17, 512K partitions). If you can run the Windows `quickbms.exe` under Wine,
its statically-linked XDK `XMemDecompress` usually works and you may not need the source fix — but the
Linux-native build does.

## How

### The bug: myalloc() reuse without refreshing currsize

`u8 *myalloc(u8 **data, QUICKBMS_int wantsize, QUICKBMS_int *currsize)` in `src/utils.c` has two
early-return paths that reuse an existing buffer when it is already big enough. Before the fix both
paths jumped to `quit` **without updating `*currsize`**:

```c
// src/utils.c (pre-fix)
if(currsize && (wantsize <= *currsize)) {   // wantsize is rounded
    if(*currsize > 0) goto quit;            // *currsize left stale
}
...
if(currsize && (ows <= *currsize)) {
    if(!*data) { /* must allocate */ }
    else {
        if(*currsize > 0) goto quit;        // *currsize left stale
    }
}
```

The caller (the XMemDecompress path) sizes its decompression from `*currsize`. When a *previous*
larger allocation left `*currsize` larger than the current `wantsize`, the reused buffer is fine but
the recorded size is wrong; the LZX decoder then believes the destination can hold more than it can
and fails:

```
uncompressed data (-1) bigger than allocated buffer
```

**Fix** (the `myalloc` patch): on both reuse paths set `*currsize = ows` (the *original* requested size,
before `MYALLOC_ZEROES` padding / 4096 rounding) before `goto quit`:

```c
if(currsize && (wantsize <= *currsize)) {   // wantsize is rounded
    if(*currsize > 0) { *currsize = ows; goto quit; }
}
...
if(*currsize > 0) { *currsize = ows; goto quit; }
```

`ows` is captured at the top as `ows = wantsize;` before `wantsize += MYALLOC_ZEROES;` — the padding
is exactly what XMemDecompress needs, but the *reported* size must be the caller's real request.

### Workaround without patching

Use single-file extraction: `-f "{}filename_part{}"` allocates a clean buffer per call and dodges the
reuse path. Useful to confirm the diagnosis before rebuilding.

### Three local patches (against upstream v0.12.0)

Local patches on top of aluigi's official v0.12.0 source; not upstreamed, no CI, no tests.

| # | Change | File | Detail |
|---|--------|------|--------|
| 1 | `myalloc` buffer reuse | `src/utils.c:2966,2975` | set `*currsize = ows` on the two reuse early-returns (above) |
| 2 | OpenSSL 3.x compat | `src/perform.c:1542` | `RSA_SSLV23_PADDING` was removed in OpenSSL ≥3; the RSA decrypt chain is now guarded by `#ifdef RSA_SSLV23_PADDING`, with an `#else` branch omitting that padding mode |
| 3 | Makefile portability | `src/Makefile` | remove the x86-arch-only guard on `-msse2` / `EXTRA_TARGETS`; add `libs/lzma/CpuArch.c` to the build |

### Build

```sh
cd src && make
```

Monolithic single-command compile: ~88 bundled libs all compiled into one binary; no shared-library
use. System deps: `lzo bzip2 zlib openssl` (plus `lib32-*` variants for 32-bit).

- `-m32` is the **default** for script compatibility; add `-DQUICKBMS64` for 64-bit file offsets.
- If `-m32` trips C23 warnings on a new GCC with K&R-style bundled libs:
  ```sh
  make CFLAGS="-O2 -DQUICKBMS64 $(sed 's/-m32//' <<< "$CFLAGS")"
  ```
- Arch/CachyOS: `paru -S quickbms` — the AUR PKGBUILD carries patches 2 and 3 (OpenSSL 3.x and the
  Makefile fixes) but **not** the `myalloc` buffer-reuse fix.
- Key files: `src/quickbms.c` (entrypoint), `src/utils.c` (`myalloc`), `src/unz.c`
  (`unxmemlzx()` — XMemDecompress entry, ~11.5K lines), `src/compression/unmspack.c`
  (`appDecompressLZX()`, libmspack wrapper), `src/perform.c` (RSA/OpenSSL glue).

### libmspack caveat

Even patched, `src/libs/mspack/lzxd.c` has inherent limits against some Xbox 360
XMemDecompress variants that Microsoft's XDK handles. Microsoft's XMemDecompress is **not**
implemented by Wine, so the Windows exe's success there is the linked XDK DLL, not Wine. If more edge
cases appear, a custom LZX decoder may be needed.

## Gotchas

1. **`uncompressed data (-1) bigger than allocated buffer` on Linux builds (or with libmspack).**
   **Symptom:** extraction aborts mid-archive on LZX/XMemDecompress entries; Windows exe succeeds.
   **Cause:** `myalloc()` reused a sized buffer without refreshing `*currsize`, so the LZX decoder read
   a stale oversized size. **Fix:** the patch (`src/utils.c`), or `-f "{}filename_part{}"` as a
   workaround.
2. **`RSA_SSLV23_PADDING` undefined compile error on OpenSSL ≥3.** **Symptom:** build fails at
   `src/perform.c`. **Cause:** OpenSSL 3 removed that padding constant. **Fix:** guard with
   `#ifdef RSA_SSLV23_PADDING` and provide an `#else` that drops the mode (patch 2).
3. **`-msse2` / x86-only guard blocks non-x86 or 64-bit builds; linker misses CpuArch.** **Symptom:**
   build fails on arch-specific flags or undefined LZMA symbols. **Cause:** upstream Makefile assumed
   32-bit x86 and omitted `libs/lzma/CpuArch.c`. **Fix:** drop the arch guard, add the source (patch 3).
4. **C23 warnings on new GCC with `-m32`.** **Symptom:** flood of K&R/old-C warnings, sometimes hard
   errors. **Cause:** modern GCC defaults + classic bundled libs. **Fix:** build 64-bit with
   `-DQUICKBMS64` (and strip `-m32` from CFLAGS), or patch the offending libs.
5. **Windows `quickbms.exe` works under Wine but the Linux binary doesn't.** **Symptom:** confusion
   about "using Wine". **Cause:** the exe statically links Microsoft's XMemDecompress, which Wine does
   **not** implement natively — so the exe's success isn't a Wine decoder. **Fix:** for a native build,
   rely on the patched libmspack path (or link an XDK-equivalent); don't expect Wine to supply the
   XMemDecompress primitive.
6. **Diagnosing a suspected reuse bug.** **Symptom:** you are not sure whether the failure is the
   buffer-reuse path or a genuine LZX variant. **Cause:** both surface as size/`-1` errors. **Fix:**
   run the same archive with `-f "{}filename_part{}"`; if it extracts fully, it was the reuse bug.

## Seen in

- NFS Shift / Shift 2 `.BFF` archives — `CommonVehicleTextures.bff` (338 files, all TYPE=2
  XMemDecompress, LZX window 17, partition 512K) and `dodge_vipersrt10_Cockpit.bff` (87 files, all
  TYPE=2); BFF offset `0x12d` is `0x00` (no encryption). Script `nfsshift.bms` covers Shift 2,
  Project CARS 1/2 and TDFRL (the bundled repo copy is Shift-oriented).
- The local QuickBMS source patches (unpublished; against upstream v0.12.0).
