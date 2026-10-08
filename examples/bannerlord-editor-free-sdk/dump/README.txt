Crash dump and reverse-engineering helpers for TaleWorlds.Native.dll
=====================================================================
These are the tools behind knowledge/techniques/bannerlord-native-crashes-and-hangs.md: they turn a Windows minidump of a
frozen or crashed Bannerlord into a short list of "which function, which data, which bone". Nothing here touches the game.

Minidump helpers (python 3, `pip install minidump`; no pefile needed)
  Native DLL addresses are printed Ghidra-style (image base 0x180000000), so they can be pasted into RE.java commands.
  threads.py <dmp> [tid ...]      threads by user time, the module of each RIP; stack return addresses that point into
                                  TaleWorlds.Native (a call-before check against the DLL on disk)
  unwind.py <dmp> <tid>           a real x64 unwind (.pdata of the modules on disk) until the first JIT frame
  loc.py <dmp> <entryRSP> local_XXXX[_len] ...   a frame's Ghidra locals (entryRSP = address of its return address)
  rd.py <dmp> addr:len ...        hex / int / float dump of captured memory
  huge.py <dmp>                   captured segments holding float triples of 1e9..1e15 (garbage frames: a non-unit
                                  quaternion or a position that exploded shows up here)
  vt.py <dmp> <vtable addr>       objects with that vtable in captured memory (find the runtime address of a skeleton or
                                  an agent object from the vtable address you read in Ghidra)

How to get a dump: Task Manager (Details, right click the frozen Bannerlord.exe, "Create dump file") for a hang, or the
Windows Error Reporting LocalDumps registry key for a crash. Dumps of a running game contain your save data and paths: do not
publish them.

The DLL on disk must be the build the dump came from. The helpers read it from the path recorded in the dump.

RE.java: batch commands for headless Ghidra (one JVM load runs many commands)
  strings <regex>            defined strings matching, with referencing functions
  funcs <regex>              functions whose name matches
  decomp <target> [depth]    decompile to RE_DECOMP_DIR (default re_out/decomp), callees to depth
  xrefs <target>             callers and callees of a function, references to an address
  rename <addr> <name>       name the function at addr (creates one if needed); saved at exit
  label <addr> <name>        primary label at addr
  scalar <hex> [max]         instructions with that scalar operand
  bytes <hex> [max]          byte pattern search in memory (references listed)
  dump <addr> <len>          hex dump of memory
  callers <target> <depth>   caller tree
  target = 0xADDR, ADDR hex, or an exact function name.

re.ps1 <commands.txt> [out.txt] [-Client]
  Runs RE.java with analyzeHeadless. Needs JDK 21 (JAVA_HOME), Ghidra (GHIDRA_HOME) and a Ghidra project per build that holds a
  COPY of TaleWorlds.Native.dll (never the file in the game folder), analysed once. See the header of re.ps1. About 10 s per
  scripted query once the project is analysed.
  Two builds exist: the Modding Kit editor build (bin\Win64_Shipping_wEditor, project twnative) and the client build
  (bin\Win64_Shipping_Client, project twclient). Their addresses differ; crash offsets are for the client build. After a game
  update treat every address you saved as stale and derive it again.

Keep decompiler output out of version control and out of anything you publish: describe the logic in your own words and name
the symbols (the repository's contribution rules ask for exactly that).
