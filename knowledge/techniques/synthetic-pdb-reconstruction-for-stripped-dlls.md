---
kind: technique
title: "Synthetic PDB reconstruction for stripped Disrupt DLLs"
tags: [disrupt, ubisoft, watch-dogs, pdb, symbols, reverse-engineering, rtti, vftables, llvm-pdbutil, ghidra, ida]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links: []
---
# Synthetic PDB reconstruction for stripped Disrupt DLLs
> Retail Disrupt binaries (Watch Dogs 1/2/Legion) ship without a usable PDB, but the MSVC RTTI survives even when the binary is packed, and the Wii U build of the same engine kept a full symbol table. This note reconstructs a synthetic PDB from PE exports, RTTI type descriptors, complete-object locators, vftables and Lua native strings, optionally enriched by matching a leaked/dev PDB's class and method names onto the game's vftable order. The result loads in Ghidra/IDA and gives named classes, virtual methods and (where the dev PDB matches) real member offsets — clearly labelled as reconstructed, not official.

## When to use it
- You have a stripped Disrupt/Watch Dogs DLL (WD1 `Disrupt_b64.dll`, WD2 `Disrupt_64.dll`, WDL `DuniaDemo_clang_64_dx12.dll`) with intact RTTI but no PDB, and you want readable class/vtable names in Ghidra/IDA instead of `vftable_0x...` and `sub_...`.
- You also have a related **dev/leaked PDB** from the same engine branch (e.g. `DuniaDemo_r64_dx12.pdb`) whose class names you want to transfer onto the retail vftable ordering.
- You have cross-platform symbol dumps (Wii U SYMTAB) to use as name-only references when no dev PDB exists for that title.

## How

**1. Extract from the game DLL** (`tools/pdb/scripts/extract_dll_symbols.py <dll> <tag> [image_base_hex]`, ~1 min on a 570 MB DLL):
- `sections_<tag>.json`, `exports_<tag>.json` — PE sections and exports.
- `rtti_<tag>.json` — RTTI type descriptors and complete-object locators.
- `vftable_symbols_<tag>.json` — `Class::vftable` and `Class::vf<slot>` entries recovered from COLs.
- `extra_symbols_<tag>.json` — engine method-name strings.
- `lua_natives_<tag>.json` — Lua C-API natives located by NUL-terminated string against `globals.lua`.

**2. (Optional) Extract a dev PDB** (`extract_dev_pdb_types.py <pdb> <tag>`, needs `llvm-pdbutil` + `llvm-undname`):
- `dev_types_<tag>.json` (LF_STRUCTURE/CLASS/INTERFACE + LF_FIELDLIST + LF_ENUM), `dev_publics_<tag>.json` (S_PUB32, demangled), `dev_globals_<tag>.json` (S_UDT/S_CONSTANT).

**3. (Optional) Transfer dev names onto retail vftables** (`merge_dev_types.py <dev_tag> <game_tag>`):
- Matches the game vftable's class name to a dev-PDB class, then replaces `vf<slot>` placeholders with the dev PDB's ordered `LF_ONEMETHOD` names (its field list preserves vftable order) and member offsets from `LF_MEMBER`. Emits `enriched_vftable_<dev>_<game>.json` + `enriched_types_<dev>_<game>.json`.

**4. Build the YAML and compile it** (`build_pdb_yaml.py [--tag --dll --guid --age --pdb --yaml]` merges the JSONs → YAML; then `llvm-pdbutil yaml2pdb`):
- The RSDS GUID and age are copied from the target DLL's debug directory so the PDB is accepted as matching that exact binary. Defaults reproduce the WDL dx12 PDB; `--tag dx11` handles the dx11 build.
- Ready-made drivers: `rebuild_pdb.sh` (dx12), `rebuild_pdb_dx11.sh`, `rebuild_pdb_wd1.sh`, `rebuild_pdb_wd2.sh`.

**5. Load it.** Import the DLL into Ghidra/IDA and point it at the generated `.pdb`. **Load the PDB in the Ghidra GUI** — loading via headless scripts has API issues.

### Known-good invocations

```bash
cd ~/Documents/Code/re/tools/pdb/scripts
# WDL dx12 (default tag "main")
python3 extract_dll_symbols.py ../../WDL/DuniaDemo_clang_64_dx12.dll main
./rebuild_pdb.sh
# WDL dx11
python3 extract_dll_symbols.py ../../WDL/DuniaDemo_clang_64_dx11.dll dx11
./rebuild_pdb_dx11.sh
# WD1 / WD2 (paths + GUIDs are baked into the scripts)
./rebuild_pdb_wd1.sh
./rebuild_pdb_wd2.sh
```

## Gotchas

1. **Symptom.** Debugger/IDA rejects the PDB or matches it to the wrong image. **Cause:** the RSDS GUID/age in the YAML must equal the DLL's debug-directory GUID/age. **Fix:** copy the GUID/age from the target binary (per-title values below); never reuse another build's GUID.
2. **Symptom.** Wii U-derived symbols resolve to garbage addresses. **Cause:** Wii U entries with `rva=0` were assigned **fake RVAs** in `.text` — they are name-only references. **Fix:** treat those as name hints only; the `source` field in `extra_symbols_*.json` (`wiiu`, `dev_pdb_type`, `decompiled_c`, …) lets you filter, and don't trust their addresses.
3. **Symptom.** Enriched vftable names are wrong or almost nothing matches. **Cause:** `merge_dev_types.py` matches by class name; WDL↔WD1 naming differs, so `merge_dev_types.py dev wd1` matched only 1 vftable class. **Fix:** use the dev PDB closest to the target branch (e.g. `DuniaDemo_r64_dx12.pdb` for WD2), and expect manual class matching across titles.
4. **Symptom.** Duplicate or inflated symbol counts. **Cause:** `extra_symbols_*.json` overlaps with `vftable_symbols_*.json` / `rtti_*.json`. **Fix:** dedup on `(rva,name)` if PDB size matters (the WD1 enriched PDB is 33 MB / 291K publics).
5. **Symptom.** RTTI extraction finds nothing. **Cause:** the binary was built with RTTI stripped, or you used a runtime dump whose image base differs from the PE header. **Fix:** use the on-disk retail DLL (image base `0x180000000`); e.g. the WDL 1.5.6 dump DLL (612 MB) has an unreliable image base — use the 1.6.3 main DLL.
6. **Symptom.** dx11 PDB lacks Lua natives. **Cause:** Lua native/LUA_SYMS extraction is dx12-only and uses hardcoded real Lua C-API RVAs. **Fix:** build the dx12 PDB for Lua work; expect only RTTI/vftable names in dx11.
7. **Symptom.** `yaml2pdb` / extraction fails on missing tools. **Cause:** `llvm-pdbutil` and `llvm-undname` are external (LLVM/Clang packages). **Fix:** install the LLVM tools; they are not bundled.

### Per-title values

| Title | DLL | Debug GUID | Age | Notes |
|---|---|---|---|---|
| WDL dx12 | `DuniaDemo_clang_64_dx12.dll` | `{84BDE31D-654B-46B9-8B13-D60A27C33314}` | 2 | 1.6.3, Denuvo-packed, RTTI intact: 1,933 type descriptors, 1,577 COLs, 1,542 vftables |
| WDL dx11 | `DuniaDemo_clang_64_dx11.dll` | `{84E8439A-8917-4C7B-988D-AEF5139AA630}` | 2 | same RTTI counts, different section layout; no Lua natives |
| WD2 | `bin_plus/Disrupt_64.dll` (debug, preferred) | `{54015C37-3C0F-4A67-B31D-6C51D2CE0F0A}` | 1 | 427 MB debug; `bin/` retail is 349 MB, 0 PE exports; ~13.8K publics, 3,382 RTTI types, 8,886 vf methods; rt64 dev PDB renamed 4,148 `vfN` → real methods / 621 classes |
| WD1 | `Disrupt_b64.dll` (dlc01-pc) | `{BD60BA4E-6E5D-4844-A734-353E2ACF27EB}` | 1 | 62.4 MB; ~448 RTTI hits; enriched PDB 291K publics / 33 MB from 5 symbol sources |

**WD1 enrichment sources (286K symbols):** PC DLL RTTI/vftables (5,874); WDL dev PDB types from `DuniaDemo_r64.pdb` (32,761 names); Wii U demangled (204K); Hex-Rays `Disrupt_b64.c` (1,822 named PC functions); Domino Lua API calls (134).

**Wii U reference (why cross-platform helps):** the Wii U retail build retained a full SYMTAB/STRTAB (**317,063 symbols**) while PC/PS4/X360 were stripped. Tools: `rpx_to_elf.py`, `rpx_to_pdb.py`, `ghs_demangle.py`, `wiiu_crossref.py`; inputs `duniademo.elf`/`.rpx`/`.pdb`, `duniademo_symbols_demangled.txt`.

## Seen in

- **Watch Dogs: Legion** — WDL `DuniaDemo_clang_64_dx12.dll` (1.6.3, Denuvo-packed) and `DuniaDemo_clang_64_dx11.dll`; default dx12 + dx11 rebuild scripts.
- **Watch Dogs 2** — `WD2/bin_plus/Disrupt_64.dll` debug + `WD2/bin/Disrupt_64.dll` retail; `rebuild_pdb_wd2.sh` with dev PDB `DuniaDemo_r64_dx12.pdb` (`dev_fixed`).
- **Watch Dogs 1** — `Disrupt_b64.dll` (dlc01-pc); `rebuild_pdb_wd1.sh`; enriched from WDL dev PDB + Wii U symbols + Hex-Rays output.
- **Dunia lineage** — the same RTTI/vftable/PDB approach transfers to other Dunia 2 titles (Far Cry family), which share the class-naming and vftable conventions.
