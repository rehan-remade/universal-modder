---
kind: technique
title: "Runtime-patching TDU2 in memory via a version.dll proxy (tdu2-runtime-patch)"
tags: [test-drive-unlimited-2, runtime-patching, dll-proxy, code-cave, imgui, rust, fov, camera]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links: []
---

# Runtime-patching TDU2 in memory via a version.dll proxy (tdu2-runtime-patch)

> A Rust `cdylib` shipped as a proxy `version.dll` (hkAlice's `tdu2-runtime-patch`) that forwards twelve of `version.dll`'s exports to the system provider, then patches `TestDrive2.exe` **in memory** by `module_base + hardcoded_offset`. No game file on disk is touched. It is a clean worked example of proxy-DLL runtime patching: thread-off-main in `DllMain`, `VirtualProtect`+`FlushInstructionCache` writes, whole-region snapshots for reversible toggles, and an ImGui DX9 overlay bound to `F8`.

## When to use it

- You need to change TDU2 behaviour (FOV, camera jitter/bugs) on a retail install without shipping a modified executable.
- You want a template for proxy-DLL runtime patching of any 32-bit XInput/version/dinput-style proxy target, where offsets are build-specific but the load-and-patch flow is reusable.
- Note: SecuROM can close the game when it is patched at runtime. Working around that is out of scope for this KB; the technique description here is about in-memory patching, not about defeating the protection.

## How

Chain of control (all from `src/`):

1. **Proxy load.** The crate is `crate-type = ["cdylib"]` named `version`; `version.def` re-exports twelve of `version.dll`'s exports (`GetFileVersionInfoA/W`, `GetFileVersionInfoSizeA/W`, `VerFindFileA/W`, `VerInstallFileA/W`, `VerLanguageNameA/W`, `VerQueryValueA/W`); the `…Ex` and `ByHandle` variants are omitted. `src/proxy.rs` resolves each from `kernelbase`/`kernel32` via `GetProcAddress` and forwards. The game loads `version.dll` from its own directory, so the proxy wins the DLL search order.
2. **Main entry (`src/lib.rs`).** `DllMain(DLL_PROCESS_ATTACH)` only calls `DisableThreadLibraryCalls` and spawns `CreateThread(init_thread)` — never patch under the loader lock.
3. **`init_thread`.** Logs a banner, reads `tdu2-runtime-patch.ini`, sleeps `StartupDelaySeconds` (default 3), then `GetModuleHandleA("TestDrive2.exe")` → `base = module as usize`, and calls `initialize_runtime_patches(base, config)`.
4. **Patching primitives (`src/patch_utils.rs`).** `patch_bytes(addr, bytes)`: `VirtualProtect(PAGE_EXECUTE_READWRITE)` → `copy_nonoverlapping` → restore old protection. `patch_nop(addr, len)` writes `0x90`. `relative_jump_displacement(src,dst,5)` computes a `JMP rel32`. `flush_region` calls `FlushInstructionCache(GetCurrentProcess(), addr, len)` — always after code writes.
5. **Reversible toggles (`src/runtime_patches.rs`).** A `RuntimePatchController` holds one `ToggleState` per group. Before a group's first patch it captures whole 64 KiB-aligned `RegionSnapshot`s of the touched pages; disabling a group restores those bytes. The camera-related groups are FOV, camera fix and camera shake; each is independently toggleable.
6. **FOV hook (`src/features/fov.rs`).** Validates the six expected bytes at `base + 0x89260F` (`D9 5C 24 10 FF D2`); bails if they differ. Allocates a `VirtualAlloc(0x1000, PAGE_EXECUTE_READWRITE)` code cave and writes:

```asm
fmul dword ptr [multiplier]   ; D8 0D <imm32>
fstp dword ptr [esp+10]       ; D9 5C 24 10
call edx                      ; FF D2
jmp  return                   ; E9 <rel32>   -> base+0x892615
```

   The original six bytes at the hook site become `E9 <rel32> 90`. The multiplier lives in a `static mut f32` whose address is patched into the cave, so the overlay can change FOV live without re-hooking. `sanitize_fov_multiplier` clamps to `0.1 ..= 4.0`, default `1.2`.
7. **Camera fix (`src/features/camera.rs`).** A set of byte patches (all `base + offset`): zero phase accumulators at `0x7BCFBE`, `0x7BD001`, `0x7BD015` (`FLD → FLDZ` / `FSTP ST0`), NOP downstream writes at `0x7BDC44`/`0x7BDC4C`, force shake-LUT checks at `0x851244`/`0x851274`, zero amplitudes at `0x8A2281`/`0x8A229C` (`xorps xmm0,xmm0`), and replace a frame-independent `FMUL [const]` with frame-time `FMUL dword ptr [EBP+0xC]` at `0x881AA0`. `apply_camera_shake_patch` is the exterior-shake variant over region `0x880000`.
8. **Overlay.** `src/overlay/` hooks D3D9 (`imgui-dx9-renderer`, vendored in `third_party/`) plus dinput/wndproc; `F8` toggles a panel that reads/writes the same `PatchConfig` and calls the `set_runtime_*` functions; changes persist back to the ini via `persist_runtime_panel_options`.
9. **Config (`src/config.rs`).** `tdu2-runtime-patch.ini` with `[Patch]`, `[FOV]`, `[Overlay]`; booleans accept `1/0`, `true/false`, `yes/no`, `on/off`; `;` and `#` comments; a default file is written on first run.

## Gotchas

1. **Crash on a non-matching build.** *Symptom:* instant crash or undefined behaviour. *Cause:* every patch is a hardcoded `base + offset`; offsets are build-specific. *Fix:* the only validated binary is the Steam release `Update v034 DLC2 Build16 - EU`, `sha1 45bfdfe6cb600a32f9c9516bf34e62bea5af2a6` (39 hex digits — truncated upstream). On any other build you must re-derive offsets; the FOV hook at least self-checks its six expected bytes and skips on mismatch, but the other groups do not.
2. **Nothing happens / patch not applied.** *Symptom:* game runs unmodified, `tdu2-runtime-patch.log` shows `GetModuleHandleA(TestDrive2.exe) failed`. *Cause:* proxy not loaded, or the process name differs. *Fix:* place `version.dll` + ini next to `TestDrive2.exe`; under Proton ensure the local `version.dll` is actually preferred for the game module.
3. **Deadlock / stalled launch.** *Symptom:* game hangs at startup. *Cause:* doing real work inside `DllMain` (loader lock). *Fix:* copy the project's pattern — `CreateThread(init_thread)` in `DllMain`, patch on the worker thread after `StartupDelaySeconds`.
4. **Patched code not taking effect.** *Symptom:* bytes written but old instruction still executes. *Cause:* missing instruction-cache flush after a code write. *Fix:* always call `flush_region`/`FlushInstructionCache` after `patch_bytes`; the project flushes per region with a tag for logging.
5. **Toggle-off leaves the game broken.** *Symptom:* disabling a group crashes instead of restoring. *Cause:* no snapshot, or a partial one. *Fix:* snapshot the *entire* page-aligned regions *before* the first write (the project uses 64 KiB `RegionSnapshot`s), and if a snapshot is missing keep the group ON rather than guessing.
6. **FOV changes ignored at runtime.** *Symptom:* edits to `Multiplier` don't move the camera. *Cause:* the multiplier is read from a `static mut` whose address was baked into the cave; re-running the hook instead of updating the value reallocates. *Fix:* `set_fov_multiplier_value` writes the live f32 only; only the initial enable builds the cave.
7. **Wrong target arch.** *Symptom:* link/load errors. *Cause:* TDU2 is 32-bit. *Fix:* build `i686-pc-windows-msvc` (`rustup target add i686-pc-windows-msvc`; `cargo build --release --target i686-pc-windows-msvc`); `lib.rs` is gated `#![cfg(target_arch = "x86")]`.

## Seen in

- `hkAlice's tdu2-runtime-patch v0.7.0 (MIT)` — `src/lib.rs`, `src/proxy.rs`, `src/patch_utils.rs`, `src/runtime_patches.rs`, `src/config.rs`, `src/features/fov.rs`, `src/features/camera.rs`, `src/overlay/`, `version.def`, `build.rs`, `README.md`.
- Related KB context: the `version.dll` proxy pattern is the same mechanism the workspace uses for other titles (`opentdu2/` NULL-ptr fix, WDL save porting), but this one patches by `base + offset` at runtime rather than hooking an IAT entry.
- Existing KB notes that already cover TDU2 file formats (`.BIG`/`.map`, `.2DB`, KNAB) — this note only concerns in-memory behaviour.

## Open questions

- Are the camera/FOV offsets valid on the non-Steam / DLC1 / older builds, or is the whole group Steam-v034-only? Only one sha1 is listed as validated.
- The camera group mixes `FLD→FLDZ` (zero a value) with `FMUL [EBP+0xC]` (frame-time compensation). Which of the two mechanisms actually fixes which symptom (suspension-feed jitter vs frame-rate-dependent drift) is not documented; needs A/B on a real build.
- Could the `base + offset` scheme be replaced by a signature/AOB scan so the tool survives build changes? The FOV hook already demonstrates the expected-byte check that a scanner would generalise.
- Under Proton/Linux, does the game still resolve the local proxy `version.dll` without a `WINEDLLOVERRIDES` entry, and if so is the ini read from the same directory the game is launched from?
