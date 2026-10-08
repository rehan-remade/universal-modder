---
kind: technique
title: "Analysing PS3 ELF/PRX binaries in Ghidra: TOC/r2, NID and syscall resolution"
tags: [ps3, ps3elf, prx, ghidra, powerpc, big-endian, cell, fNID, syscall, relocations, decompilation, console]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - "https://github.com/Clienthax/Ps3GhidraScripts"
  - "https://github.com/kakaroto/ps3ida"
  - "https://github.com/NationalSecurityAgency/ghidra"
  - "https://www.psdevwiki.com/ps3/"
---

# Analysing PS3 ELF/PRX binaries in Ghidra: TOC/r2, NID and syscall resolution

> PS3 executables (`.elf`) and PRX modules (`.prx`/`.sprx`) are 64-bit big-endian Cell PPU
> code (VMX/AltiVec; the SPU is a separate ISA), loaded as `PowerISA-Altivec-64-32addr`. Stock Ghidra loads them but leaves
> imports, the TOC pointer (`r2`) and linker-provided library calls unresolved, so the decompiler
> output is full of bogus pointers. The `Ps3GhidraScripts` extension adds three scripts that fix
> that: it locates the OPD/TOC and sets `r2`, it names NIDs from a lookup table, and it resolves the
> `syscall` stubs. This note records the exact run order, the language/cspec setup, and the known
> limits.

## When to use it

- You have a PS3 `.elf`/`.prx`/`.sprx` and want readable decompilation in Ghidra.
- Library calls show up as anonymous, or as the PowerPC syscall instruction `sc`
  (`44 00 00 02`) with the syscall number in `r11`.
- You need to map a function address back to a `sce*` API name via its NID.

If the binary is a plain PowerPC ELF with no Cell/PS3 relocations, vanilla Ghidra may be enough;
these scripts target the PS3 ABI specifically.

## How

### Setup

- Ghidra processor/language: **`PowerISA-Altivec-64-32addr` (BIG endian)**. Little-endian variants
  cause the scripts to error; PS3 is big-endian.
- Edit `Ghidra/Processors/PowerPC/data/languages/ppc_64_32.cspec` and add `<register name="r2"/>` to
  the `<unaffected>` list — without this the decompiler treats `r2` (the TOC base) as clobbered and
  the output degrades.
- Build the extension: set `GHIDRA_INSTALL_DIR` and run `./gradlew`; the installable zip lands in
  `dist/`. CI builds against Ghidra 11.2–12.1 with Java 21.

### Run order (matters)

1. **`AnalyzePs3Binary.java` — before auto-analysis.** Parses imports/exports, sets the TOC and `r2`,
   and defines the entry point.
2. **Run Ghidra auto-analysis.**
3. **`DefinePS3Syscalls.java` — after auto-analysis.** Resolves the syscall trampoline calls to names.

### What `AnalyzePs3Binary` does

- **PRX:** recognises the format and builds a module-info structure (`handlePrx` → `createModuleInfo`).
- **EXEC:** reads `e_entry` from the ELF header, then finds the **OPD** section heuristically — the
  section immediately before the one whose virtual address is greater than `e_entry` (entry point
  sits in the OPD). It writes `tocPtr` at `OPD + 4`, defines the entry as a pointer, and creates a
  `_start` function at the resolved address. When several TOCs exist, the one named by the OPD is the
  correct `r2` value (see also `AssignPs3R2FromOpd.java`).
- Helper classes: `Ps3ElfUtils` (ELF/section walking), `ElfSection`, `FnidUtils` (NID handling),
  `Ps3DataStructureTypes` (PS3 structs), plus `FindPs3JumptableTargets.py` for jump tables.

### What `DefinePS3Syscalls` does

- The PS3 syscall trampoline is the PowerPC `sc` instruction (bytes
  `0x44 0x00 0x00 0x02`), with the syscall number in `r11`. The script scans for that
  pattern. (A `CALL dword ptr GS:[0x10]` in Ghidra output is left over from the x86
  script, not the PS3 form.)
- It uses Ghidra **overriding references** plus the **symbolic propagator** to recover the syscall
  *number* passed in a register at each call site, then binds the function to the name from
  `data/syscall.txt` (`<number> <name>`), so `sys_process_*`, `sys_net_*`, etc. resolve.
- NID → name lookups come from `data/nids.txt` (`0x<FNID> <sceName>`); a NID is the 32-bit hash of a
  library export's signature string, and the tables cover the common `sce*` modules.

### Bundled data

| File | Format | Size |
|---|---|---|
| `data/nids.txt` | `0x<FNID> <name>` | ~9,100 entries |
| `data/syscall.txt` | `<number> <name>` | ~798 entries |

These are public PS3 ABI tables; keep them next to the scripts rather than hand-typing NIDs.

## Gotchas

1. **Scripts throw on load / analysis errors out.** **Cause:** wrong endianness — PS3 is big-endian.
   **Fix:** select `PowerISA-Altivec-64-32addr`, not the little-endian variant.
2. **Decompilation produces nonsense around `r2`.** **Cause:** `r2` (TOC base) treated as clobbered.
   **Fix:** add `<register name="r2"/>` to `<unaffected>` in `ppc_64_32.cspec`.
3. **`r2` is wrong / pointers resolve to garbage in EXEC files.** **Cause:** the TOC/OPD was not set,
   or an OPD other than the entry's was used. **Fix:** run `AnalyzePs3Binary` **before** auto-analysis
   so it can pick the OPD from `e_entry`; use `AssignPs3R2FromOpd` when a second TOC is needed.
4. **Syscalls stay unnamed.** **Cause:** `DefinePS3Syscalls` was run before auto-analysis, so the
   symbolic propagator has no call graph to work with. **Fix:** run it **after** auto-analysis.
5. **Cell PPU VMX/AltiVec vector instructions fail to decompile (`lvlx`, etc.).** **Cause:** Ghidra
   does not implement some Cell-specific vector ops. **Fix:** no clean fix — expect those functions
   to decompile poorly; read the disassembly instead.
6. **Relocated references are unresolved.** **Cause:** the PS3 ELF relocation formats are not
   supported by these scripts. **Fix:** none here — accept unresolved pointers, or resolve the
   specific relocation manually.
7. **Wrong API names from NIDs.** **Cause:** a NID collides or the table is stale for the firmware
   build. **Fix:** cross-check against psdevwiki / the module's own export table rather than trusting
   the name blindly.

## Seen in

- `Ps3GhidraScripts` (unpublished local copy) — Ghidra extension by Clienthax: `AnalyzePs3Binary.java`,
  `DefinePS3Syscalls.java`, `AssignPs3R2FromOpd.java`, `FnidUtils.java`, `Ps3ElfUtils.java`,
  `Ps3DataStructureTypes.java`, `ElfSection.java`, `FindPs3JumptableTargets.py`, `data/`, and a built
  `dist/ghidra_12.0.4_DEV_20260517_Ps3GhidraScripts.zip`.

## Open questions

- The scripts were not exercised against a real PS3 binary in this session — the run order and quirks
  are taken from the extension's own `AGENTS.md` and source comments, not from a live analysis.
- Whether the NID table covers the firmware build you care about; a stale table silently mislabels
  exports.
- The OPD heuristic assumes a section layout where the OPD sits just below the entry section; other
  linkers/builds may need the address supplied by hand.
