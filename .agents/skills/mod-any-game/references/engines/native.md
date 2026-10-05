# Native engines without a mod loader (C/C++, custom engines)

Use this when `um scan` says "unknown native engine" or the loader can't reach your idea. It's the most work,
and it's where agents and reverse-engineering MCPs pay off the most. Single-player, offline or servers the
user runs; never on anti-cheat-protected games (see safety.md).

## 1. Get code into the process
- **Proxy DLL:** drop a DLL named like one the game loads from its own folder (`version.dll`,
  `dinput8.dll`, `winmm.dll`, `dxgi.dll`, `d3d9.dll`, `xinput1_3.dll`). It forwards the real exports and
  runs your code in `DllMain` (spin up a thread; do almost nothing under the loader lock). Check the game's
  imports first with `dumpbin /imports` or PE-bear.
- **Ultimate ASI Loader** (ThirteenAG) is a ready-made proxy that loads `*.asi` (renamed DLL) plugins from
  the game folder or `scripts/`. Many older games already use it.
- **Other hosts:** script extenders, or a framework the community built (see big-frameworks.md). A launcher
  that starts the game suspended and injects is the last resort.
- **Proton/Linux:** `WINEDLLOVERRIDES="dinput8=n,b" %command%`.

## 2. Find what to hook
- **Static analysis:** Ghidra or IDA, driven by an agent through MCP (reverse-engineering skill). Start from
  strings (UI text, log messages, asset names) and imports (D3D, XInput, file APIs). Follow cross-references
  to the function that handles the thing you want to change. Name functions and structs as you go, and write
  them into MODLOG.md.
- **Dynamic analysis:**
  - Cheat Engine: scan for values (health, ammo, position), find what writes them, then walk back to the
    struct and its owner.
  - x64dbg: breakpoints, trace.
  - ReClass.NET: rebuild structs from live memory.
  - MCP versions of CE, x64dbg and Frida let an agent do this. Bind them to localhost.
- **Signatures, not addresses:** find functions by AOB/byte-pattern scan at startup (with wildcards for
  relocations) so the mod survives game updates. Keep a fallback: log clearly when a pattern isn't found.

## 3. Hook
- MinHook, SafetyHook or Microsoft Detours: detour the function, call the original through the trampoline.
  Match the calling convention exactly (x64 is one convention; x86 needs `__thiscall`/`__stdcall` care).
- Mid-function hooks (SafetyHook `MidHook`) change registers at a single instruction.
- Keep hooks tiny. Do heavy work on your own thread or out of process.

## 4. Draw and interact
- **Overlay / UI:** hook `IDXGISwapChain::Present` (D3D11/12) or `vkQueuePresentKHR` (Vulkan), then render
  Dear ImGui. Kiero is a small helper for finding these. The ReShade addon API gives you `present`,
  `draw_indexed`, render-target and depth events without writing the hooks yourself.
- **Inject 3D content into the game's own pass:** use the game's view-projection matrices (find them in
  constant buffers with RenderDoc) and its depth buffer. The ReShade addon examples cover depth access and
  buffer inspection. RenderDoc (+ renderdoc-mcp) shows exactly which pass draws what.
- **Input:** hook the game's input handling, or raw input / XInput.

## 5. Reimplementation instead of patching (for total control)
Once enough of the game is understood, some projects rewrite the engine (IW4L for MW2 in Rust). They read
the user's own game files, and the original binary acts as the oracle. Others decompile function by function
with a byte-matching harness. See retro-decomp.md and the mashup-mods skill.

## Pitfalls
- ASLR: compute addresses from the module base at runtime; never hard-code absolute addresses.
- Threads: engines expect calls on their main thread. Queue work and run it from a hooked per-frame
  function.
- Crashes: log to a file with flushes. Install an unhandled-exception filter that writes a minidump.
- Game updates move everything. Pin the game version for development and document which build you support.
