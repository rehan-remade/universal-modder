---
kind: technique
title: Decompiling DXBC / DX9BC shader bytecode to HLSL with 3Dmigoto's HLSLDecompiler
tags: [shader, dxbc, hlsl, decompilation, 3dmigoto, renderdoc, graphics-re]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - https://github.com/etnlgd/HLSLDecompiler
  - https://github.com/bo3b/3Dmigoto
  - https://renderdoc.org/
---

# Decompiling DXBC / DX9BC shader bytecode to HLSL with 3Dmigoto's HLSLDecompiler

> A small Windows console tool from the 3Dmigoto project that parses DXBC (Shader
> Model 4/5) container bytecode back into editable HLSL, and can also disassemble
> with either its own `fxc`-style backend or Microsoft's. It is most useful wired
> into RenderDoc as a Custom Tool so you can decompile, edit and hot-refresh a
> shader while looking at the pipeline state. The output closely mirrors the
> disassembly rather than original source.

## When to use it

- You have a captured `.dxbc`/shader blob (Shader Model 4+) and want HLSL you can
  edit and re-validate, not just read.
- You want an in-RenderDoc workflow: decompile a live shader stage, tweak the
  HLSL, hit Refresh, and observe the rendering change.
- You need both a decompiler and a round-trip assembler/disassembler in one CLI
  (3Dmigoto's Flugan backend plus an option to shell out to Microsoft's).

## How

Paths below are relative to the tool checkout at
https://github.com/etnlgd/HLSLDecompiler.

1. Build (Windows only, MSBuild / Visual Studio):
   - Platform toolset `v142` (VS 2019), Windows SDK 10.0; platforms Win32 and x64
     only. Configurations: `Debug`, `Release`, `Zip Release`.
   - Solution `StereovisionHacks.sln`. Build all, e.g.
     `msbuild StereovisionHacks.sln /p:Configuration=Release /p:Platform=x64`.
   - One project, e.g.
     `msbuild HLSLDecompiler\cmd_Decompiler\cmd_Decompiler.vcxproj /p:Configuration=Release /p:Platform=Win32`.
   - External dependency `crc32c-hw-1.0.5`: not present in this checkout, but 3Dmigoto
     vendors `crc32c-hw` (https://github.com/bo3b/3Dmigoto).
2. Run the CLI `cmd_Decompiler.exe`. Flags (from `cmd_Decompiler.cpp`):

   | Flag | Action |
   |---|---|
   | `-D`, `--decompile` | Decompile DXBC to HLSL (primary use) |
   | `-d`, `--disassemble`, `--disassemble-flugan` | Disassemble with Flugan's disassembler |
   | `--disassemble-ms` | Disassemble with Microsoft's disassembler |
   | `-a`, `--assemble` | Assemble with Flugan's assembler |
   | `-V`, `--validate` | Validation pass after decompile/disassemble |
   | `-S`, `--stop-on-failure` | Stop on first error |
   | `-v`, `--verbose` | Debug logging to stderr |

   The output file is the input basename with `.hlsl` appended in place of the
   extension (`shader.bin` → `shader.hlsl`). Commented-out flags in the parser
   (`-C/--compile`, `-f/--force`) are not implemented.
3. RenderDoc integration: keep `hlsl_decompiler_wrapper.bat` beside
   `cmd_Decompiler.exe`. The batch runs `cmd_Decompiler.exe -D "%1"` then `type`s
   the generated `.hlsl` to stdout. Register it in RenderDoc → Tools → Settings →
   Shader Viewer → Add as Tool Type "Custom Tool", Executable = the `.bat`,
   Command Line = `{input_file}`, Input/Output = `DXBC/HLSL`. Then Pipeline State
   View → pick a stage → Edit → "Decompile with <name>", edit, Refresh.

Code layout (functions described, not reproduced):

- `HLSLDecompiler/cmd_Decompiler/cmd_Decompiler.cpp` — CLI entry: manual POSIX-style
  argument parsing (getopt is absent on Windows), `--` terminator, then drives
  decode/decompile/disassemble/assemble per file.
- `HLSLDecompiler/DecompileHLSL.cpp` — the core engine (~5479 lines). Builds an
  internal IR from decoded instructions, tracks a `DataType` classification (bool,
  floatN, floatNxM, int/uint variants), recovers constant-buffer layouts into a
  `CBufferData` map keyed by `register << 16 + offset`, and emits HLSL.
- `BinaryDecompiler/decode.cpp` — DXBC container parsing: `DXBCContainerHeader`
  (fourcc `DXBC`, chunk count/offsets), `DXBCChunkHeader`, and FOURCC chunk types
  `SHDR`/`SHEX` (SM4/SM5 code), `ISGN`/`ISG1` (input signature), `OSGN`/`OSG1`
  (output signature), `RDEF` (resource/constant-buffer definitions), `IFCE`
  (interface, dynamic linking). `DecodeDXBC()` walks chunks and hands signature
  and resource chunks to reflection.
- `BinaryDecompiler/reflect.cpp` — extracts shader reflection data (signatures,
  resources, interfaces) used to name inputs/outputs/CBs.
- `D3D_Shaders/Assembler.cpp` — assembler/disassembler; the Microsoft path calls
  `D3DDisassemble(...)` with `D3D_DISASM_ENABLE_DEFAULT_VALUE_PRINTS`.

## Gotchas

1. **Build fails: `crc32c-hw` missing.** Symptom: unresolved external / include
   not found for crc32c. Cause: not present in this checkout. Fix: take
   `crc32c-hw` from 3Dmigoto (https://github.com/bo3b/3Dmigoto), which vendors it,
   and place it where the projects expect it before building.
2. **Nothing builds off Windows.** Symptom: missing MSBuild/`.sln` toolchain on
   Linux. Cause: `.vcxproj`/MSBuild, toolset `v142`, Windows SDK — not
   cross-platform. Fix: build on Windows or in a Windows VM/CI with VS 2019.
3. **DX9/SM1-3 shader blob yields no HLSL.** Symptom: function returns nothing for
   an old shader. Cause: `DecodeDXBC()` checks the `DXBC` fourcc; on failure it
   only runs `DecodeShaderTypeDX9(data[0])` to detect the SM1/2/3 token and then
   returns `0` — the source carries a `:todo: run standard DX9 decompiler from
   microsoft` marker. Fix: treat this tool as DXBC (SM4+) for reliable
   decompilation; DX9BC token tables (`tokensDX9.h`) exist but the DX9
   decompile path is unfinished. Do not assume full DX9BC support despite the
   repo name.
4. **Output looks like disassembly, not original source.** Symptom: HLSL reads as
   register-level ops. Cause: this is a decompiler, not a source recovery tool —
   it reconstructs from bytecode. Fix: expect and work with that style; it is
   designed to be edit-and-revalidate rather than byte-exact source.
5. **RenderDoc "Decompile with" does nothing.** Symptom: custom tool reports no
   output. Cause: wrapper and exe must be in the same directory, and the tool
   returns via stdout (`type *.hlsl`). Fix: co-locate both files and confirm
   Executable points at the `.bat`, not the `.exe`.

## Seen in

- https://github.com/etnlgd/HLSLDecompiler — the 3Dmigoto shader-decompiler
  subtree. Read-only grounding for this note: `README.md`,
  `hlsl_decompiler_wrapper.bat`, `HLSLDecompiler/cmd_Decompiler/cmd_Decompiler.cpp`,
  `HLSLDecompiler/DecompileHLSL.cpp`, `BinaryDecompiler/decode.cpp`.

## Open questions

- Does the DX9 path ever get implemented upstream, or is DX9BC permanently a
  token-detection stub here?
- Exact SM5/SHEX edge cases the engine fails to decompile cleanly — not
  benchmarked here; no tests exist in the repo to establish coverage.
- Not verified: I did not build the tool, run `cmd_Decompiler.exe`, or decompile a
  real shader. Facts above are from reading the sources.
