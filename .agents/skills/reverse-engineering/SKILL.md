---
name: reverse-engineering
description: Read how a game actually works so a mod can hook it. Decompile .NET/Mono (ILSpy), IL2CPP (Cpp2IL, Il2CppDumper), Java (Vineflower) and native code (Ghidra, IDA, via MCP servers); dump data and asset formats; reverse-engineer a binary file format and prove it with a round trip; read live memory (Cheat Engine, Frida, x64dbg); find render passes (RenderDoc). Use when a mod needs game internals, e.g. "how does the boss AI work", "find the damage function", "what format is this .sld/.pak/.dat", "where is the player position in memory".
---

# Reverse engineering for mods

Rule zero: **read the real thing, don't guess.** Decompiled code, the actual data, a live memory view or a
GPU capture is the spec. Write what you learn into `MODLOG.md` (names, IDs, offsets, formats) as you go.

Keep all decompiled output and extracted assets **outside** the mod repo (e.g. `~/<game>-decomp/`) and never
publish them. Single-player, offline or servers the user runs. Never attach debuggers or scanners to games
with anti-cheat (see `skills/mod-any-game/references/safety.md`).

## Pick the tool by what the code is (`um scan` tells you)

**Managed .NET** (XNA/FNA, Unity Mono, most indie C#)
- `dotnet tool install -g ilspycmd`, then `ilspycmd -p -o ~/<game>-decomp <Game>.exe` (or
  `Assembly-CSharp.dll`). This gives a full C# project you can grep.
- dnSpyEx: step through with a debugger, set breakpoints, edit methods.
- MCP: ILSpy-MCP / dnspy-mcp let an agent query types and methods directly.

**Unity IL2CPP**
- Cpp2IL (or Il2CppDumper) on `GameAssembly.dll` + `global-metadata.dat` gives types, fields, method
  signatures and addresses, plus dummy DLLs for ILSpy.
- Method bodies are native: load `GameAssembly.dll` in Ghidra/IDA and apply the generated script to name
  functions.
- Live: UnityExplorer, or `il2cpp-frida-mcp`.

**Java** (Minecraft, Slay the Spire...)
Vineflower / CFR / Recaf. For Minecraft, use Loom `genSources` with Mojang mappings.

**Native C/C++** (custom engines, Unreal game code, console recomps)
- Ghidra (free) or IDA, driven through MCP so the agent can decompile, rename, retype and follow
  cross-references:
  - Ghidra: GhidraMCP (LaurieWired), pyghidra-mcp (headless, with a run-script tool; code-capable tools beat
    hundreds of tiny ones), ReVa.
  - IDA: the official Hex-Rays IDA MCP (IDA 9.4+ Pro/Home; "code mode" runs IDAPython), or ida-pro-mcp.
  - Binary Ninja and radare2 have MCP servers too.
- Workflow:
  1. Strings, then cross-references, then the function.
  2. Name and type everything you understand. Renames accumulate into a readable program.
  3. Confirm dynamically (below) before building on a guess. Agents can confidently misidentify things.
- Unreal: dump the reflection data first (UE4SS dumper or Dumper-7); it names most gameplay classes and
  properties for free.

**Dynamic / live**
- Cheat Engine: value scans → "find out what writes to this address" → struct → owner. CheatEngine MCP
  servers exist.
- x64dbg: breakpoints and tracing (x64dbg-mcp; bind it to 127.0.0.1, since some default to 0.0.0.0).
- Frida (frida-mcp, frida-game-hacking-mcp): hook functions from JavaScript, log arguments.
- ReClass.NET rebuilds structs from live memory.

**Graphics**
- RenderDoc (renderdoc-mcp) captures a frame and shows every draw, the render targets, the constant buffers
  (view/projection matrices) and the depth buffer.
- That's how you find where to inject geometry or effects (mashup-mods), and which texture holds a sprite
  atlas.

## Data files and asset formats
Use the community tool first:
- Unity: UABEA, AssetRipper
- Unreal: FModel, UAssetGUI
- Bethesda: xEdit, BSArch
- GameMaker: UndertaleModTool
- Genie: genieutils
- Source: VRF, Crowbar
- FromSoft: WitchyBND, Smithbox
- Godot: GDRE Tools

Before reversing a format yourself, search the community archives. Most game formats from the 2000s and
2010s were worked out there:
- **XeNTaX** (closed in 2023): the [forum](https://archive.org/details/forum.xentax.com_2023-08-15),
  [wiki](https://archive.org/details/wiki-wikixentaxcom_202305) and
  [attachments](https://archive.org/details/Xentax-forum-attachments-archive) are on archive.org, with a
  [public backup on GitHub](https://github.com/XeNTaXBackup/XeNTaXBackup.github.io);
- **[ZenHAX](https://zenhax.com/index.php.html)**: game file research and QuickBMS scripts (posts up to
  early 2023);
- **[The definitive guide to exploring file formats](https://archive.org/details/definitive-guide-to-exploring-file-formats)**
  (Mr. Mouse, XeNTaX): the classic tutorial on reading an unknown format.

Use them for format knowledge and tools, whatever its origin (betas, leaked SDKs). Don't download game files,
leaked code, SDKs or license keys from them.

For an **undocumented format**:
1. Collect several stock files. Compare sizes, and hex-dump the headers (`xxd | head`). Look for magic
   numbers, counts, offsets and tables of fixed-size records.
2. Form a hypothesis for the header, then the frame/record layout, then the compression. Check it by
   parsing every stock file without errors.
3. Write a reader that decodes to something viewable (PNGs, JSON) and **look at it**.
4. Write the writer, and **prove it with a round trip**: decode → encode → decode, compared against the
   original. The AoE2 SLD sprite writer was accepted only when it round-tripped the stock knight at
   0.9/255 mean error (`examples/aoe2-de-civ/sld.py`).
5. Only then write new files. Test them in game with one asset before batch-converting.

## Make it an oracle
- **Engine logic you port** (for a simulator, a trainer, a reimplementation): record real traces from the
  game (positions, velocities per tick) and replay them against your port. In the Terraria Eye of Cthulhu
  work, the Eye's velocity matched 99.9% once the port used the action applied on frame t+1. Float32
  constants mattered too (`0.2f` ≠ `0.2`). A leftover mismatch was traced to a hidden buff (Happy!, x1.21
  move speed). Replays find what reading the code misses.
- **For long RE runs:**
  - a journal file;
  - small verified steps;
  - cap attempts per problem (about 3 identical failures, then change approach);
  - commit every confirmed fact.
