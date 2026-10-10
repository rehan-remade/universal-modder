---
kind: technique
title: "Static-address native hooks from an INI-driven DLL (LINK/2012 injector pattern)"
tags: [native-hook, x86, injector, link2012, code-cave, game-mod, no-source, static-addresses, ini]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - "https://github.com/thelink2012/injector"
  - "https://github.com/ThirteenAG/Ultimate-ASI-Loader"
---

# Static-address native hooks from an INI-driven DLL (LINK/2012 injector pattern)

> When a shipped PC game has no source, no loader API and no script hook, the pragmatic route is a DLL
> that overwrites known instructions at fixed addresses and reads its settings from an INI.
> LINK/2012's `injector` header makes that safe enough to be maintainable: `WriteMemory`, `MakeNOP`,
> `MakeJMP`/`MakeCALL` and hand-written naked code caves that return to a saved exit address. This is
> the pattern behind NFS Most Wanted (2005)'s *Extra Options* mod.

## When to use it

- A **32-bit, statically-based** executable (no source, no plugin API) where you need to change magic
  numbers, limits, or control flow — e.g. lap/opponent counts, a heat level, windowed mode, starting cash.
- You can find the addresses reliably (debugger with symbols/PDB, or by hash-pattern scanning), and the
  values you want sit at fixed addresses or in fixed globals.
- You do **not** want to reimplement or patch the exe on disk; the DLL is loaded at boot and reverts
  nothing persistent.

Do not use it where an official script/mod API exists, and stay away from multiplayer/anti-cheat builds.

## How

1. **Establish the image base.** A shipped 32-bit x86 exe usually loads at `0x400000` with ASLR off, so a
   debugger address *is* the runtime address. NFSMW Extra Options relies on exactly this.
2. **Pin the addresses you care about.** Name them as constants, ideally with the symbol the debugger
   showed (`GRaceDatabase_GetRaceParameters = 0x5DC930`, `Game_SetWorldHeat = 0x612660`,
   `Game_SetCopsEnabled = 0x604F40`, FE string hasher `bStringHash = 0x460BF0`). Where the game addresses
   front-end objects by **32-bit string hash** (the same `stringhash32` used to look up menu entries), you
   can resolve FE strings/objects by computing the hash rather than hardcoding a pointer.
3. **Patch with the injector.** Use typed writes and instruction helpers, always keeping the game's
   original bytes in mind:

   ```cpp
   // dllmain.cpp pattern (LINK/2012 injector.hpp)
   injector::WriteMemory<unsigned char>(0x7AC3EC, minLaps, true);   // overwrite a compare's operand
   injector::WriteMemory<DWORD>(0x8F5790, 0x0BE6E0, true);          // grow an engine memory pool size
   injector::MakeNOP(0x551455, 7, true);                            // erase a call/check
   injector::MakeJMP(0x5ACBFA, SomeNakedFunc, true);                // detour into a code cave
   ```

   `MakeJMP`/`MakeCALL` to a `__declspec(naked)` function lets you run custom asm and then `jmp` back to a
   saved **cave-exit** address. The mod keeps a table of those exits (`CameraNamesCodeCaveExit = 0x51C98C`,
   `HeatLevelsCodeCaveExit = 0x443dc9`, …) so each cave returns exactly where the overwritten instruction
   would have continued. `MakeRangedNOP(at, until)` handles multi-byte NOPs across instruction boundaries
   (it takes an **end** address, not a length).
4. **Configure from a file.** Settings live in `NFSMWExtraOptionsSettings.ini`, read with a tiny
   `CIniReader`; the DLL reads the INI once in `DllMain` (or a worker thread, `DWORD WINAPI Thing(LPVOID)`),
   then installs the patches. This keeps every magic number out of the binary and makes the mod a single
   redistributable DLL + INI.
5. **Guard the risky bits.** A repeatedly-hit hook should set a "once" flag, and hooks that call back into
   the game need the correct calling convention and stack cleanup.

## Gotchas

1. **Crash on an address that used to work.** **Cause:** game version/executable differs, or ASLR is on, so
   `0x400000`-relative addresses shifted. **Fix:** verify the image base and ideally scan for a byte signature
   instead of trusting a bare address.
2. **Hook runs but the game does nothing.** **Cause:** patched the wrong copy of an instruction (the same
   compare appears in several controller functions). **Fix:** patch every site the debugger showed — the mod
   writes the lap value at four separate addresses for exactly this reason.
3. **Freeze / stack corruption after a code cave.** **Cause:** missing or wrong cave-exit `jmp`. **Fix:**
   record the continuation address of the original instruction and jump there, preserving registers/flags the
   original code expected.
4. **Settings silently ignored.** **Cause:** INI next to the wrong module (working directory vs DLL dir).
   **Fix:** resolve the INI relative to the DLL/`GetModuleFileName`.
5. **NOP too short.** **Cause:** erasing fewer bytes than the instruction occupies, leaving a partial
   instruction. **Fix:** measure the instruction length; use `MakeRangedNOP(at, until)` with the **end**
   address.
6. **"Modded game check" style guards.** Some builds verify their own files/save integrity. Clearing such a
   check is a game-integrity tweak, not an ownership/DRM bypass — decide deliberately whether it is in scope
   for your mod, and never touch anti-cheat or licence checks.

## Seen in

- **NFS Most Wanted (2005) — *NFSMW Extra Options*** (https://github.com/ExOptsTeam/NFSMWExOpts;
  `NFSMWExtraOptions/dllmain.cpp`, 1500+ lines): lap/opponent/traffic limits, heat override, rain parameters,
  vinyl categories, hidden cameras, split-screen, windowed mode, starting cash, car scale, memory-pool growth.
  Uses `includes/injector/injector.hpp` (LINK/2012), `includes/IniReader.h`, `includes/CPatch.h` and
  `DialogInterfaceHook.h`.
- Same pattern (different games/harness) recurs across the ThirteenAG ecosystem's ASI mods.
