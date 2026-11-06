---
kind: game
title: "Cyberpunk 2077 native modding: address hashes for update-proof hooks, and which source wins"
game: "Cyberpunk 2077"
engine: redengine
platform: windows
route: native-hook
game_version: "Steam PC build; bin/x64/Cyberpunk2077.exe is 59,945,608 B (mtime 2026-08-07) and the shipped cyberpunk2077_addresses.json carries the linker-map stamp 68af45ea (2025-08-27)"
status: in-progress
date: 2026-10-10
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
tags: [cyberpunk2077, redengine, red4ext, redlib, redscript, address-hash, rva, relocations, native-hook, ida, agent-skills]
tools: ["Python 3.14","Ghidra/IDA","llvm-readobj"]
links: ["https://github.com/alphanin9/CP2077AgentSkills","https://github.com/wopss/RED4ext.SDK","https://github.com/psiberx/cp2077-red-lib","https://codeberg.org/adamsmasher/cyberpunk"]
---

Cyberpunk 2077 ships a **symbol table for its own executable**: `bin/x64/cyberpunk2077_addresses.json`, next to
`Cyberpunk2077.exe`. It maps linker-map offsets to address hashes that keep native hooks alive across game
patches. This note records how the lookup works, the source-priority ladder to use when writing a native or
Redscript mod, and what was actually run here.

The distillation source is [alphanin9/CP2077AgentSkills](https://github.com/alphanin9/CP2077AgentSkills) (MIT,
two Agent Skills: `cp2077-address-hash` and `cp2077-modding`). Its reference files carry the SDK, Redscript and
reverse-engineering guidance; the address-hash script was verified on the retail install here (see
Verification), and it needed a one-character-class fix to run on current Python (gotcha 1).

## Setup

- Install root: `<steam>/steamapps/common/Cyberpunk 2077/bin/x64/` — `Cyberpunk2077.exe` and, beside it,
  `cyberpunk2077_addresses.json`.
- That file's shape: top-level `Linker map timestamp`, `Preferred load address` (`0x140000000`) and
  `Code constant offset` (`0x1000`), then `Addresses`, a list of `{hash, secondary hash, symbol, offset}`.
  The copy here holds **987,479 entries over 606,577 distinct offsets**: section `0001` 424,911,
  `0002` 428,944, `0003` 133,575, `0005` 49. An `offset` looks like `0001:00101428`.
- The `cp2077-modding` skill expects its upstreams fetched, never vendored; its `scripts/fetch_sources.py`
  clones RED4ext.SDK (`wopss/RED4ext.SDK`), RedLib (`psiberx/cp2077-red-lib`) and the decompiled game
  scripts (`adamsmasher/cyberpunk` on Codeberg) into a cache and prints the paths.
- Python 3.14.7 here. The address-hash script as published fails on it; patching two help strings makes it
  run (gotcha 1).

## Route

1. **Get an RVA** from disassembly (subtract the image base first if the tool gave you a virtual address;
   the file itself reports `0x140000000`).
2. **Convert it** to the linker-map form `section:rva_from_section_base`. The section number is 1-based and
   follows PE section-table order; the right-hand side is relative to that section's start, not the image.
   `0x102428` in `.text` (base `0x1000`) becomes `0001:00101428`.
3. **Look it up** in `cyberpunk2077_addresses.json`. A hit gives the address `hash` and `secondary hash`
   plus the linker-map `symbol`, which is the readable name you actually wanted.
4. **Use the hash, not the RVA.** `RED4ext::UniversalRelocFunc` with an address hash is the update-agnostic
   form (`UniversalRelocPtr` and `UniversalRelocVtbl` do the same for data and vtables); a hardcoded RVA is
   version-sensitive and should be marked as such. A missing match is not a conversion failure — it usually
   means the database predates your build. RED4ext's resolver (`src/dll/Addresses.cpp`) reads only `hash`
   and `offset`, and only rebases sections `0001`-`0003`, matched by name to `.text`, `.rdata` and `.data`,
   so the 49 section-`0005` entries don't resolve to the right address through it.
5. **Pick the source that is authoritative for the question** (skill's ground-truth order): local project
   code, then fetched upstream trees, then **RED4ext.SDK** for native type names, layouts, RTTI and plugin
   lifecycle, then **RedLib** when it cleanly covers the task, then the **decompiled scripts** for script
   class/method names, hook targets and event flow, and only then the **binary** for implementation detail
   that no source has. Record which of script-confirmed / SDK-confirmed / RTTI-confirmed / binary-confirmed
   you are at.
6. **Native plugin shape**: `Query`, `Supports`, `Main`, `RegisterTypes`, `PostRegisterTypes`; register
   through `CRTTISystem::Get()->AddRegisterCallback(...)` / `AddPostRegisterCallback(...)`, or with RedLib
   definitions call `Red::TypeInfoRegistrar::RegisterDiscovered()` on `Load`. Search the SDK for
   `NAME = "scriptName"`, `ALIAS`, `RED4EXT_ASSERT_SIZE`, `RED4EXT_ASSERT_OFFSET` to map a script type to
   its C++ counterpart.
7. **Redscript**: `@wrapMethod` hooks should call `wrappedMethod(...)` unless the point is to change control
   flow around the original call.
8. **Style the SDK expects**: C++20, reversed types in namespace `RED4ext`, PascalCase functions/classes,
   `m_` members, `a`-prefixed parameters (`aValue`, `aContext`), camelCase locals, `RED4EXT_` macros.

## Verification

Run on 2026-10-10, Python 3.14.7, from the install's `bin/x64/`, against
`cyberpunk2077_addresses.json` (stamp `68af45ea`).

- **As published, the script does not start** — `python3 scripts/rva_to_address_hash.py 0x102428` ends in
  `ValueError: badly formed help string`, caused by `ValueError: unsupported format character 'C' (0x43) at
  index 65` in `argparse._expand_help → help_string % params`, reached from
  `rva_to_address_hash.py:42` (`parser.add_argument("--exe", …, help="… %CP2077_PATH%\\bin\\x64\\…")`).
  Exit code 1.
- **After escaping `%`** as `%%CP2077_PATH%%` in the two help strings, a real lookup returns:
  `RVA: 0x00102428` → `Section: 0001 .text (base 0x00001000)` → `Offset: 0001:00101428` →
  `Matches: 1` → `hash=887623293` `symbol=game::WorldBoundarySystem::Tick`. Exit code 0.
- An RVA in a valid section with no entry is reported as `Matches: none` (`0x2a8d123` →
  `Offset: 0002:00000123`) — not an error.
- An RVA outside every section is an error with exit code 2:
  `error: RVA 0x60000000 does not fall inside any PE section`.
- The section table was cross-checked with `llvm-readobj --sections`: `.text` base `0x1000`,
  `.rdata` `0x2A8D000`, `.data` `0x32E6000`, and the script's `span = max(VirtualSize, RawDataSize)` rule
  agrees with it.
- **Not verified**: that the symbols are correct (that needs disassembly, not a table lookup), and no plugin
  was built, injected or run. The table is stamped 2025-08-27 and the exe's mtime is 2026-08-07, but an
  mtime is when Steam wrote the file, not when it was linked. The comparison that matters is the table's
  `Linker map timestamp` against the exe's PE header `TimeDateStamp` (`llvm-readobj --file-headers`), and
  that wasn't checked here.

## Gotchas

1. **The published address-hash script is dead on arrival in Python 3.14.** `add_argument(help=…)` help
   strings are `%`-formatted by argparse, and 3.14 started checking them inside `add_argument`, so a
   literal `%CP2077_PATH%` raises `ValueError: badly formed help string` (from `unsupported format
   character 'C' (0x43) at index 65`) before any argument is read. On 3.13 and older the script runs and
   only `--help` crashes. Escape it as `%%CP2077_PATH%%`, or drop the `%` signs. (Found here; patched
   locally, not yet sent upstream.)
2. **The database is per-build.** Compare `Linker map timestamp` with your executable's PE header
   `TimeDateStamp` (not its file mtime); after a game patch a miss usually means the JSON is older than the
   exe, not that the conversion is wrong.
3. **Section-relative, 1-based.** The offset is `section index in PE order : RVA minus that section's base`.
   Feeding an image-relative value produces a plausible-looking offset that silently misses.
4. **Do not vendor the upstreams.** RED4ext.SDK, RedLib and the decompiled scripts are fetched into a cache;
   pasting them into a repo or a skill is a licensing and size problem.
5. **Read-only first on the executable.** Prefer IDA/decompiler inspection, xrefs and script sources over
   patching; treat hardcoded offsets as version-sensitive and label them.
6. **Native callbacks may run concurrently** (game threads, worker jobs, script paths). Protect shared
   state with locks or engine-safe queues, prefer immutable tables after init, and never block
   render/UI/input/hot paths.
7. **`@wrapMethod` without `wrappedMethod(...)` is not an error** — it silently replaces behavior, which is
   easy to mistake for "the hook fired and nothing changed".
8. **REDscript does run on multiple threads**, so a script mod sharing state with a native plugin needs the
   same discipline as native code.
9. **The skill's scope is deliberately narrow**: it says it focuses on native/Redscript rather than
   WolvenKit because LLM work there is harder. That is a statement about tooling maturity, not about
   WolvenKit being unnecessary for asset work.

For the archive and asset side (CR2W, RDAR/KARK, Oodle) see
[`techniques/redengine-container-and-asset-format-lineage.md`](../../techniques/redengine-container-and-asset-format-lineage.md).
