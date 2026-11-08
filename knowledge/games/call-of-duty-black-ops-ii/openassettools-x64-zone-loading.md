---
kind: game
title: "OpenAssetTools can load T4, T5 and T6 zones in a 64-bit process"
game: "Call of Duty: Black Ops II"
games_also: ["Call of Duty: Black Ops", "Call of Duty: World at War"]
game_version: "Zones from Steam Black Ops II Zombies build 24784239 and our own World at War and Black Ops installs; tested 2026-10-31"
platform: windows
engine: iw
route: other
tools: ["OpenAssetTools as vendored in B2W (commit 7d027e8f)", "MSBuild"]
anti_cheat: "None involved: offline reads of our own zone files. No game process."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["AryaBlue"]
date: 2026-11-08
links:
  - https://github.com/Laupetin/OpenAssetTools
  - https://github.com/Ticass/B2W
tags: [fastfile, zones, x64, tools, openassettools, t4, t5, t6]
---

# OpenAssetTools can load these zones in a 64-bit process

> The belief that these tools must be 32-bit is wrong for this copy. It builds as Release x64 and its generated zone
> code fills 32-bit zone data into native 64-bit structs. That lets a modern 64-bit tool or engine read fastfiles
> in-process, with no 32-bit helper.

## Setup
B2W's vendored OpenAssetTools at commit 7d027e8f, MSBuild, Windows 11.

## Credits
[OpenAssetTools](https://github.com/Laupetin/OpenAssetTools) (Laupetin) and its zone code generator did this work.
We only built and tested it.

## Route and why
Tooling. Reading the original files in-process replaced a large converted cache.

## Build steps
1. Build RawTemplater, ZoneCodeGenerator, Common, ObjCommon, ZoneCode and ZoneCommon first.
2. Then build the libraries, using MSBuild on each `.vcxproj`. Solution-level targets failed.
3. Guard any 32-bit layout `static_assert` with `ARCH_x86`. B2W's `SoundAliasJsonDumperT4.cpp` has one.

## Verification
- x64 and x86 dump output matched byte for byte on `zm_tomb`, `mp_raid` and `nazi_zombie_prototype`, apart from one
  float differing in its last digit.
- **Not verified:** other zones, and whether upstream's current code behaves the same.

## Gotchas
1. **Layout asserts fail on x64.** They describe the 32-bit zone layout. **Fix:** guard them with `ARCH_x86`.
