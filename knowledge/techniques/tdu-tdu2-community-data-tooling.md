---
kind: technique
title: "TDU/TDU2 community data tooling: filename hashing, .bnk inspection, 2DB textures, terrain heightmap editor"
tags: [test-drive-unlimited, test-drive-unlimited-2, tooling, file-hash, bnk, texture, heightmap, modding]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links: []
---

> Credits: Knyazev's TDU2 tools.

# TDU/TDU2 community data tooling: filename hashing, .bnk inspection, 2DB textures, terrain heightmap editor

> Map of the *remaining* TDU/TDU2 community utilities that sit around the container/model formats already documented in the KB: the 64-bit filename-hash generator every `.map`/`.bnk` lookup depends on, four thin .bnk inspection GUIs, the TDUMT II `.2DB`↔DDS texture converter/viewer, and an OpenGL terrain/heightmap editor. Each entry states what it actually is, how it was identified, and whether the knowledge is grounded in code/README or merely inferred from the binary. Tools whose knowledge is already covered by an existing note are listed only as pointers so this does not duplicate them.
>
> Tool folders below are named only; they are **unpublished local copies** of third-party community tools, not part of this repository, and are credited by name.

## When to use it

- You have a `.map`/`.bnk` and want to know what the 16-hex keys mean, or need to generate the 64-bit hash for a filename you are adding.
- You are inspecting a KNAB `.bnk` and want a quick viewer/locator before writing your own parser.
- You need to convert TDU/TDU2 `.2DB` textures to/from DDS outside Blender.
- You are editing terrain/sector heightmaps and data (the `hmeditor` tool).
- You want to know which of these is already covered elsewhere in the KB before re-documenting it.

## How

**Filename hash generator (`TDU2-HashGen`).** Two files: `tdu2.dll` (4096 B, native PE32 i386) and `TDU2 HashGenerator.exe` (VB.NET `v2.0.50727`, WinForms). The exe P/Invokes `tdu2.dll`'s `GenerateHash` export (also exports `Function02`; RVAs `0x100e` / `0x100c`). This is the tool that produces the 64-bit filename hashes used as keys in `.map` sidecars and `.bnk` lookups (the archive note already documents those as "64-bit name hashes"). **Grounded facts from static inspection:** the hash is 64-bit, seeded with `esi = 0x0CD5E44A` / `edi = 0xFAC432B1`, and the DLL `.data` is `0x800` bytes = 256 × 8-byte table — consistent with a CRC-style byte-driven 64-bit hash. **Where the algorithm is recoverable:** the DLL `.text` is only `0x5f` bytes and is a self-modifying/obfuscated stub (entry does `call`/`pop`, `and eax,0xffffff00`, then `add [eax+0x74],eax` / `add [eax+0x7d],eax` into the section gap); the byte loop is truncated, so it cannot be read straight off this stub. The same 64-bit hash is, however, implemented in open tool source — `TDU2.BIG.Tool`'s `BigHash.cs` (see the archive note in this KB) — so the algorithm is recoverable from that source and can be checked against real `.map` keys. The seed constants (`0x0CD5E44A`/`0xFAC432B1`) and a 256×8-byte table are the grounded anchors in the DLL itself.

**`.bnk` inspection family (`TDU2-BNK-Finder/`, `TDU2-BNK-File-Locator/`, `TDU2-BNK-Guts-Viewer/`, `TDU2-Bin-Renamer/`).** Four tiny VB.NET `v2.0.50727` WinForms assemblies. Namespaces: `TDU2_Bnk_Extractor` (Finder and File-Locator), `TDU2_bnk_guts_viewer` (Guts Viewer), `TDU2_Bin_Renamer` (Bin Renamer). They are thin GUI wrappers (no format logic beyond the .bnk already described in the archive note) — useful as reference implementations for chunk walking and for confirming which filename hashes resolve to which `.bnk` entries. The Finder/File-Locator share a namespace and are near-identical builds; File-Locator additionally references `InternalXmlHelper`/`WeakReference`. Only the class/namespace layout is grounded; behaviour is inferred from names.

**TDUMT II Texture Tools (`TDUMT2_Texture_Tools`).** Knyazev's toolset, v1.0 dated 2017-01-29, C# requiring .NET Framework 3.5 SP1. Two apps: `Texture_Converter.exe` converts `.2DB` ↔ `.DDS` (single and batch), and `Texture_Viewer.exe` views `.2DB`. README-sourced features: RGB-palette support, alpha channels, detailed 2DB info, error log. Bundles third-party libraries `Fesersoft.Hashing.Crc32` (Fesersoft) and `DjeFramework-1` / `TduModdingLibrary-1` (Djey) — the Dje/TDUMT libraries are the same lineage referenced by other TDU mod tools. The `.2DB` layout itself is already documented in the model/texture note; this tool is only a converter/viewer.

**Terrain heightmap editor (`hmeditor`).** `main.exe` (Windows, ~4.5 MB, 2026) plus `glew32.dll`, `glfw3.dll`, `libwinpthread`, and a `gfx/` folder — an OpenGL editor. README-sourced operation: copy an `ibiza` folder beside `main.exe`; `SLASH` switches map/world; `Q`/`D` pan left/right, `Z`/`S` front/back, `L` saves, `Enter` toggles the bounding box; in map view `A` dezooms, `Z` zooms, left-click navigates ("go to"). `settings.ini` has `[Textures] reduce terrain texture by half`/`reduce textures by half`, `[World] load sector hm texture / objects / pmis at start`, and `[Editor] raycast size = 512`. It edits heightmap/sector data (`hm`), objects and `pmis`. No source shipped, so all behaviour is README/ini-sourced and unverified.

**Pointers to knowledge already in the KB (do not re-document):** `.BIG` bigfiles + `.map` (XMBF, XOR) and the C# `.NET` unpacker → `test-drive-unlimited-2/tdu2-archive-and-container-formats.md`; `.3DG/.3DD/.2DM/.2DB` mesh + texture layouts, the MaxScript import/extract scripts and Blender `io_scene_tdu2` → `test-drive-unlimited-2/tdu2-model-and-texture-formats.md`; Havok vehicle physics in KNAB → `test-drive-unlimited-2/reading-tdu2-vehicle-physics-havok-packfiles.md`; `tdudec`, TDU1 save offsets, CarVST audio → `test-drive-unlimited/savegame-and-config-formats.md`; the PP2 launcher/server → `test-drive-unlimited-2/playing-tdu2-online-with-project-paradise-2.md`. The `TDU2-BIG-Unpacker/` (`TDU2BIGUnpacker.exe` + `TDU2Lib.dll`) and `TDU2.BIG.Tool/` (C# .NET 8 source; `FileNames.list` = 12908 hash→path lines) are the same `.BIG` tooling as the archive note.

## Gotchas

1. **Reimplementing the hash from the DLL stub alone gives wrong keys.** *Symptom:* generated `FileNameHy` hashes don't match `.map` entries. *Cause:* `tdu2.dll` is a self-modifying/obfuscated stub; the static disassembly is truncated and the round function is not visible *there*. *Fix:* use the open implementation in `TDU2.BIG.Tool`'s `BigHash.cs`, and confirm against real `.map` keys. The DLL's seed constants (`0x0CD5E44A`/`0xFAC432B1`) and a 256×8-byte table are the grounded anchors.
2. **Tool reads nothing / can't find data.** *Symptom:* `.bnk` GUIs or `hmeditor` open empty. *Cause:* these tools assume a sibling data folder (`main.exe` needs an `ibiza` folder; converter expects files on disk). *Fix:* stage the expected layout beside the executable before launching; for `hmeditor`, also set the `[World] load sector …` flags in `settings.ini` if sectors load lazily.
3. **.NET runtime mismatch.** *Symptom:* converter/viewer/GUI fails to start. *Cause:* the `.bnk` GUIs are VB.NET `v2.0.50727` and TDUMT II wants `.NET Framework 3.5 SP1`. *Fix:* install the matching legacy framework, or run under Wine with that runtime available.
4. **Assuming the four `.bnk` tools differ meaningfully.** *Symptom:* wasted effort reverse-engineering each. *Cause:* they share namespaces and are near-identical thin GUI builds. *Fix:* treat them as one family; read one and use the rest only for a second opinion on field names.

## Seen in

- `TDU2-HashGen/` (`tdu2.dll`, `TDU2 HashGenerator.exe`)
- `TDU2-BNK-Finder/`, `TDU2-BNK-File-Locator/`, `TDU2-BNK-Guts-Viewer/`, `TDU2-Bin-Renamer/`
- `TDUMT2_Texture_Tools/` (`Texture_Converter.exe`, `Texture_Viewer.exe`, `ReadME.txt`, `Changelog.txt`)
- `hmeditor/` (`main.exe`, `readme.txt`, `settings.ini`, `gfx/`)
- Duplicate/superseded siblings: `TDU2.BIG.Tool/`, `TDU2-BIG-Unpacker/`, `TDU2-Mesh-Import/`, `TDU-Mesh-Extractor/`, `blender-io-tdu-series/`.

## Open questions

- **Hash algorithm:** the round function is implemented in `TDU2.BIG.Tool`'s `BigHash.cs` and should be reconciled with the DLL's seeds (`0x0CD5E44A`/`0xFAC432B1`); confirm any case-folding/terminator rules against real `.map` keys.
- Do `TDU2-BNK-Finder` and `TDU2-BNK-File-Locator` differ beyond the XML/weak-reference helpers, or are they the same tool rebuilt?
- `hmeditor`'s `pmis` unit type and the meaning of "reduce terrain texture by half" are undocumented; are these engine-side types (matching `.2DB`/sector data) or editor-internal?
- Are the Dje/TDUMT libraries in TDUMT II the same ones used by the mesh tools, i.e. can one shared TDU file-format library be extracted from all of them?
