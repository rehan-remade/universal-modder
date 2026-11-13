---
kind: game
title: "Native per-frame actor mover for Oblivion Remastered: ProcessEvent from a plain DLL loaded by UE4SS Lua"
game: "The Elder Scrolls IV: Oblivion Remastered"
games_also: ["Red Faction: Guerrilla Re-Mars-tered"]
game_version: "Oblivion Remastered 1.512.105 (UE5.3.2)"
platform: proton
engine: unreal
route: native-hook
tools: ["RE-UE4SS 3.0.1", "mingw-w64 (x86_64)", "Proton 11.0", "Binary Ninja", "gamescope"]
anti_cheat: "none (single-player, lab copy of the game)"
status: in-progress
agents: ["Claude Code (Sonnet 5.5; written by Claude, audited claim by claim on 2026-11-05, see docs/kb-drafts/AUDIT.md)"]
humans: []
date: 2026-11-05
links: []
tags: ["ue4ss", "native", "processevent", "package-loadlib", "interpolation", "mingw", "actors", "performance"]
---

# Native per-frame actor mover for Oblivion Remastered: ProcessEvent from a plain DLL loaded by UE4SS Lua

> A small C library, built with mingw and loaded with `package.loadlib` from a UE4SS Lua mod, moves about 250 to 800 actors every frame by calling the actor's own `ProcessEvent` for `K2_TeleportTo`. It cost 0.41 microseconds per call against 6.4 from Lua. Lua keeps decoding game state at 10 Hz and the DLL smooths between targets every frame. Real run (lab copy, house-collapse scene, three runs): 44.1 to 46.3 fps with smoother motion, against 36.7 to 38.5 fps for all-Lua variants of similar smoothness. Not tested across a real level unload. Labels used below: [real run] the game ran it and an evidence file records it; [synthetic] a host-side test; [source] code read; [reasoned] argued, not run.

## Setup

- Oblivion Remastered 1.512.105 (UE5.3.2 shipping), Proton 11.0 on Linux, RE-UE4SS 3.0.1 (embedded Lua 5.4), lab copy of the game only.
- Workload: 1,479 hidden-then-shown static mesh actors that follow rigid-body states from a second game process (Red Faction: Guerrilla) through a shared-memory file. Native calls per second: "14,000 to 17,000 peak" in the first draft is [unverified] (the stress runs logged 672,663 to 705,455 calls in total, `evidence/native-stress-run2.txt`).
- Build: `x86_64-w64-mingw32-gcc -O2 -s -shared -o geomod_native.dll geomod_native.c -lkernel32 -lm`. No UE headers and no UE4SS C++ ABI are needed.

## Route and why

- UE4SS Lua alone is slow per call: `K2_SetActorLocationAndRotation` costs 23 to 33 microseconds from Lua because of its `FHitResult` out parameter; `K2_TeleportTo` (no out parameter) costs 6.4. Raising the Lua update rate to smooth motion cost frame rate (per-frame Lua: GeoPass 170 to 183 ms per second, minimum fps 20 to 31).
- A plain DLL can be loaded with `package.loadlib("...\\geomod_native.dll", "*")` (a guard DLL already ran this way) and its exported functions come back as Lua functions with `package.loadlib(path, "name")`.
- UE4SS.dll does NOT export the raw Lua C API (`objdump -p` shows C++ mangled symbols and two plain C names, `execute_lua_in_mod` and `get_lua_state_by_mod_name`). So the DLL cannot push arguments or results through the Lua stack. The route that works: exported functions take the `lua_State*`, ignore it, return 0, and all data travels through a shared file that Lua writes with `string.pack` and the DLL maps (`CreateFileMapping` on `Z:\dev\shm\...` under Proton).

## How the game works (what we had to learn)

- **Finding ProcessEvent.** Read an actor's vtable (`*(void***)actor`) and look at slots 70 to 90. In this build slot 77 is the actor-level override (a small function taking `(this, UFunction*, Parms*)`) that calls the base `UObject::ProcessEvent` (image offset 0x10F3EA0). No slot holds the base function itself. Verify structurally: scan the slot's first 256 bytes for an `E8` or `E9` relative call to the base function. [real run, `evidence/native-n1n2-PASS.txt`]
- **Calling it.** `typedef void (*pe_fn)(void*, void*, void*)`; `pe(actor, ufunction, params)`. The `UFunction*` and the actor pointers come from Lua's `UObject:GetAddress()`. For `AActor::K2_TeleportTo` the parameter block (doubles, UE5 large world coordinates) is `FVector DestLocation` at 0, `FRotator DestRotation` at 0x18 (pitch, yaw, roll), `bool ReturnValue` at 0x30. Offsets come from the UE4SS object dump. [real run: 7,500 calls in `native-n1n2-PASS.txt`]
- **Interpolation.** Each slot keeps the displayed position and a quaternion built from the rotator with Unreal's own formula; on a new target it glides from the displayed transform to the target over the time since that slot's last update (clamped 30 to 150 ms [source, `geomod_native.c`]), lerp for position and normalised lerp for rotation, and arrives on the exact target rotator. A settled piece costs nothing. `FRotator::Quaternion` and `FQuat::Rotator` were checked by a 200,000 sample round trip (worst 3.8e-13 degrees) [synthetic: `src/GeoPass/native/test_math.c`, re-run on the host on 2026-11-05; it checks the code against itself, not against the engine; the placement audit below [real run] is what compares with the engine].

## Build steps

1. Lua writes a header (magic, UFunction address, slot count, enabled flag, generation) and 64-byte slots (actor address, sequence number, active flag, six doubles) into a shared file, unbuffered (`setvbuf("no")`).
2. The mod calls the exported `native_tick` once per game frame from the player pawn's `ReceiveTick` hook (game thread). The function maps the file read-only, finds ProcessEvent once, and applies the interpolated transform of every moving slot.
3. Lua releases a slot (flag 0) before it destroys an actor, bumps the generation on a level change, and falls back to its own moves if the DLL reports `failed or refused`, or if targets were written for 3 seconds and the DLL made no calls.

## Verification

- Probe (1,500 hidden cubes x 5 rounds): ProcessEvent found at slot 77, 7,500 calls in 3,096.7 microseconds (0.41 per call), [real run, `evidence/native-n1n2-PASS.txt`]. The Lua-side figures (6.4 and 23 to 33 microseconds per call) are from `evidence/bench-teleport.txt` [real run].
- Three full collapse runs with the mover on (the first draft listed a fourth, 44.6 (35), with no source): 44.7 (min 34), 46.3 (36), 44.1 (33) fps; GeoPass 49, 44 and 52 ms per second; frozen frames 19.3 to 19.7 percent, stutter 0.97 to 1.03; Lua at 10 Hz: 74 to 75 percent frozen, stutter 2.4 [real run, `docs/PERFORMANCE_PLAN.md` final table; files `evidence/perf-native-N0`, `N1`, `perf-final-native`]. Single-run noise is about 2 fps.
- Placement audit every 2 seconds on settled pieces: 1,063 pieces, worst position error 0.000 cm, worst true angle between orientations 0.039 degrees. Per-axis rotator differences of up to 177 degrees were the same orientation written near pitch 90, not an error; compare orientation as a quaternion angle [real run, `docs/NATIVE_PLAN.md`].
- Stress: teleport 4 km away and back during a collapse; 400 actors destroyed with `K2_DestroyActor` behind the mover's back (a flag guard on `UObject::ObjectFlags` skipped 120 dead actors); no crash [real run, `evidence/native-stress*.txt`; the 120 skipped dead actors are from `docs/NATIVE_PLAN.md`].
- Refusal test: with a DLL whose expected offset is wrong the DLL refuses at its first tick and Lua takes the moves back within a second. The first version of this fallback FAILED: the DLL's status text said `map ok` after refusing and Lua never noticed, so pieces froze while the frame rate looked fine [real run, `evidence/native-refuse-run1-fallback-failed.txt`, `native-refuse-run2-PASS.txt`; fixed].

## Gotchas

1. **A wrong digit in an expected address (`0x1400F3EA0` instead of `0x1410F3EA0`) made the first probe say "not found"** [real run, `evidence/native-n1n2-first-wrong-constant.txt`]. Print what you found near the expected address, and check constants against the decompile before reading a negative.
2. **Do not trust a worker's or note's "ProcessEvent is at X, vtable index N".** One report gave the base function's address as the vtable entry; the live vtable corrected it.
3. **A fallback only counts once tested by making the primary fail.** Ours had two faults (misleading status, no check for "writing but nothing applied").
4. **A local function used before its definition is a nil global in Lua.** It silently disabled an unrelated feature for hours; check `luac -l -l` for unexpected `_ENV` reads after every edit.
5. **Level-unload test is not possible with `GameplayStatics:OpenLevel`.** It stalled the lab game with the mover on and off alike. The mover runs only inside the player pawn's tick hook, so it stops when the pawn stops ticking; this was [reasoned], not tested. The one unload attempt and its control with the mover off are in `evidence/native-unload*.txt` (both stalled).
6. [real run, no corruption seen; the no-locking reason is reasoned] A shared file written by Lua with unbuffered I/O is visible to a read-only mapping of the same file in the DLL under Proton (both on `Z:`). No locking was needed because Lua and the tick hook run on the same game thread.

## Assets

None shipped. The DLL contains only generic engine access (vtable, ProcessEvent, math). It is pinned to build 1.512.105 and refuses to run on any other build.

## Cost and time

Elapsed time is [unverified] (the first draft said about 6 hours); the work ran across the 2026-11-03 and 2026-11-04 sessions. Source: `src/GeoPass/native/geomod_native.c` and `mover_math.h` in the project repository.

## Open questions

- A real level unload or save load with the mover active (the lab cannot trigger one safely).
- A game update that moves ProcessEvent: the DLL should refuse and Lua should take over; only the refusal path was tested, with a deliberately wrong offset.
- Whether calling from the pawn tick hook stays valid when several native movers or other mods call ProcessEvent in the same frame.
