---
kind: game
title: "Warhead 1.1.1.711: Lua/XML recovery, native analysis and level PAK method 6"
game: "Crysis Warhead"
games_also: []
game_version: "Owned Windows Bin64 installation; file version 1.1.1.711"
platform: windows
engine: cryengine
route: data
tools: ["Python 3.12", "Ghidra 12.1.4", "Temurin JDK 21"]
anti_cheat: "Static reads of owned files only; no injection, protection-module analysis or online session"
status: working
agents: ["Codex (GPT-6)"]
humans: []
date: 2026-10-11
links: ["https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.4_build"]
tags: [cryengine2, warhead, lua, xml, pak, flowgraph, native-analysis, provenance]
---

# Warhead build 711: static scripts, native analysis and level archives

Recovered delivered Lua/XML/configuration resources and produced private native pseudocode from an owned Warhead installation. The independent checks were source hashes, archive lengths/CRCs and output mappings. This note describes static analysis; later gameplay observations are in [the Zombies host note](black-ops-zombies-native-animation-and-runtime.md).

## Setup

Windows, CryEngine 2; Bin64 modules reported file version `1.1.1.711`, corroborated by the installed patch readme. The two executable names in this installation were byte-identical, so only one copy was analyzed. Selected the main executable and fourteen Cry-prefixed engine DLLs; excluded launchers, installers, middleware and protection DLLs.

Portable Ghidra 12.1.4, Temurin JDK 21 and Python 3.12. Keep binary copies, extracted scripts and complete Ghidra project pairs outside the toolkit repository. Addresses and transform-table locations below are specific to this installation; the private reader was gated on its exact `CrySystem.dll` SHA-256 and PE layout.

## Route and why

Begin with delivered data: actor/AI Lua, item/vehicle XML, difficulty configuration and level FlowGraphs. Native analysis supplements APIs not described by those resources. No executable recompilation, loader, live-memory inspection or protection bypass was required for this static archive analysis.

## How the game works

Thirty-three PAKs were ZIP-like containers. `GameData`, `Warhead_GameData` and `VPatch1` supplied 716, 760 and 22 Lua instances. A private merged reading view contained 761 Lua files and 11,132 lexical declarations. Keep variants: browsing precedence is not proof of runtime archive precedence.

All seven `level.pak` archives contained entries labelled ZIP method 6 without the standard encryption flag. Standard PKZIP Implode readers failed because the selected engine uses its own transform followed by raw Deflate for these entries.

Native analysis traced the selected `Cache::ReadFile` path at VA `0x365b2330` to a transform at `0x365ba9e0` and raw Deflate reader at `0x365bab40`. The observed transform uses a CRC-dependent byte mask and a fixed permutation/offset for each complete 64-byte block, with different handling for the partial tail. These are analysis locations, not portable offsets. Read the transform tables from the reader's own matching engine binary; do not redistribute them or assume standard compression solely from the ZIP method number.

Accept decoding only when raw Deflate reaches end-of-stream, output length equals the central-directory declaration and CRC32 matches. The private build-specific reader recovered 89 selected level text entries through those independent checks.

Mission XML contains entities plus FlowGraph nodes/edges. The final reading view held 5,912 text files, including 4,922 parsed XML descriptions. Separate indexes covered 22 vehicle definitions and 86 raw fire-mode records. Raw inherited/default values are not evaluated weapon statistics.

## Build steps

1. Inventory versions, hashes, PAK central directories and executable duplicates.
2. Copy only the selected native modules to a private analysis directory.
3. Extract supported text with path-traversal protection and ZIP CRC checks. Record per-entry unsupported methods rather than silently skipping the whole archive.
4. Establish the exact method-6 read path for the owned build. Implement its transform privately, gate on binary identity, then require Deflate end, length and CRC agreement.
5. Keep archive variants and provenance; place each level in a separate namespace. Build lexical Lua/XML/FlowGraph indexes without claiming runtime resolution.
6. Run Ghidra headless with two CPUs per process, a 900-second automatic-analysis limit and 20-second per-function export deadline. Tested heaps: 6 GB for the main project, 4 GB for separate system/render analysis.
7. Retry failed exports once with 120 seconds; retain indexed disassembly for remaining failures. Preserve `.gpr` and `.rep` together and verify every recorded output plus original input hashes.

## Verification

Verified 15 modules, 48,374 recognized functions, 48,364 pseudocode exports and ten disassembly fallbacks. Checked the duplicate executable, all 33 original archives, source copies, binary graph copies and native index/file mappings. The 89 method-6 text outputs passed declared size and CRC checks.

This establishes the selected static outputs. It does not establish exhaustive function recognition, original C++ types, semantic correctness of every pseudocode body, compilation equivalence or campaign compatibility. Runtime loose-file precedence was subsequently tested for the private mod, but general stock-archive ordering was not.

## Gotchas

1. **ZIP method 6 gives unsupported-compression/data errors.** Cause: this build's custom transform precedes Deflate. Fix: identify the native reader and validate length/CRC; a generic Implode decoder is not the oracle.
2. **No ZIP encryption flag, yet the member is unreadable.** Cause: storage-method transformation is separate from that flag. Fix: inspect the actual implementation; do not infer a protection scheme from unreadable bytes alone.
3. **One unsupported member conceals other usable entries.** Cause: archive-wide exception handling. Fix: retain per-entry outcomes and mark extraction partial until checked.
4. **A shader list is falsely reported as broken XML.** Cause: angle-bracket-looking text is not necessarily XML. Fix: use format context. One delivered facial-sequence file had an unfinished opening tag; keep the original and its parse failure.
5. **Large Ghidra functions time out or fail type merging.** Fix: bounded retry, then disassembly fallback. Do not count failed bodies as recovered source.
6. **Function totals are presented as complete C++ recovery.** Fix: name the actual recognized/exported set and its limits; preserve warnings and input identity.

## Assets

This pass retained textual asset references and two binary animation graphs with text-like extensions. Meshes, textures, audio and compiled clips were not part of the static text-recovery result. No proprietary files, decompiled bodies, binary transform tables or private analysis outputs are included.

## Open questions

Re-establish the read path and tables for other engine builds. Conflicting stock archives, inherited campaign/multiplayer scripts and native types still require focused investigation. A static reading view is an aid to a mod, not a runnable game reconstruction.
