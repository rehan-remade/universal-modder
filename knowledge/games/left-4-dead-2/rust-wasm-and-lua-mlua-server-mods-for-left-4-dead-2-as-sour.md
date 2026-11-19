---
kind: game
title: Rust/Wasm and Lua (mlua) server mods for Left 4 Dead 2 as SourceMod extensions, with a bridge between them
game: Left 4 Dead 2
games_also: []
game_version: "PatchVersion 2.2.4.3, Steam; Metamod:Source 1.12.0-dev+1219, SourceMod 1.12.0.7210, left4dhooks 1.166"
platform: windows
engine: source
route: loader-api
tools: ["Metamod:Source", "SourceMod 1.12", "left4dhooks", "Rust 1.100", "wasmi 2.0.1", "mlua 0.12.2 (Lua 5.4.9)", "zig (cargo-zigbuild)", "lua-language-server 3.19.2", "um win"]
anti_cheat: "VAC; local listen server only, always launched with -insecure"
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-19'
links: []
tags: [sourcemod, extension, webassembly, lua, mlua, scripting-runtime, interop, sandbox, hot-reload]
---
# Rust/Wasm and Lua (mlua) server mods for Left 4 Dead 2 as SourceMod extensions, with a bridge between them

> Three SourceMod extensions for Left 4 Dead 2. WasmHost runs sandboxed WebAssembly mods written in Rust, C or
> Zig. LuaHost runs Lua 5.4 scripts through mlua. RustLua connects the two, and SourcePawn plugins, with calls,
> pub/sub messages and a shared store. All three run in the real game: on a local listen server (c2m1_highway)
> a Rust mod called a Lua script, a SourcePawn plugin called Lua, Lua read a Rust mod's leaderboard, and one
> bounty event reached a Rust mod, a SourcePawn plugin and a Lua script. Checked from `console.log` and
> screenshots. The Linux `.so` builds pass a WSL smoke test but were never run on a real srcds.

## Setup
- Left 4 Dead 2 from Steam, `steam.inf` PatchVersion 2.2.4.3, on Windows 11 Pro 10.0.26200.
- Metamod:Source 1.12.0-dev+1219, SourceMod 1.12.0.7210, and the left4dhooks plugin 1.166 (used to spawn
  special infected at a valid position).
- Builds use the SourceMod SDK from the `1.12-dev` branch of alliedmodders/sourcemod (cloned, not committed).
- Rust 1.100 with the `i686-pc-windows-msvc` target (the game is 32-bit) and `wasm32-wasip1` for mods. C and
  Zig mods build with zig (`uvx --from ziglang`). Linux `.so` files come from cargo-zigbuild for
  `i686-unknown-linux-gnu.2.17`.
- Runtimes: wasmi 2.0.1 + wasmi_wasi, and mlua 0.12.2 with `lua54`, `vendored` and `serde`, building Lua
  5.4.9 from a patched copy of the lua-src crate (see Gotchas).
- Launch line: `left4dead2.exe -steam -novid -insecure -heapsize 1048576 -sw -noborder -w 1280 -h 720 -console -condebug +map c2m1_highway`.
  `-insecure` is required: the extensions are unsigned (the log should say "VAC secure mode disabled").

## Route and why
- **SourceMod extensions on the server.** L4D2 has no client mod API. SourceMod runs on dedicated servers and
  on the listen server that single player uses, so the same build covers solo play and hosted games. VScript
  was the other option, but it can't host a second language runtime.
- **A thin C++ shim, everything else in Rust.** One `extension.cpp` is the entire SourceMod-facing code; it
  is compiled twice (WasmHost, and LuaHost with a define). The shim never touches the engine: every game
  call goes to a SourcePawn bridge plugin, whose per-op code is generated. That avoids gamedata and
  signatures entirely, so game updates rarely matter.
- **One API definition** (a TOML list of ops: arguments, return type, permission, SourcePawn body). A
  generator writes the host imports, the Rust/C/Zig guest SDKs, both bridge plugins, the docs and LuaLS
  annotations. A new op reaches every language at once.
- **The bridge is a separate extension.** Each runtime publishes a C-ABI "port" (a function table) as a
  SourceMod sharesys interface. The bridge requests the ports and connects them, so either runtime works
  without it. Ports are polled every second, so load order doesn't matter.

## How the game works (what we had to learn)
- **Extension lifecycle (SourceMod 1.12 source, `core/logic/ExtensionSys.cpp`).** `sm exts unload` runs
  `UnloadExtension`: the extension's `OnExtensionUnload`, then plugins that require it are unloaded, then each
  extension that requested one of its interfaces gets `QueryInterfaceDrop` (return true to survive) and
  `NotifyInterfaceDrop`, then natives are unbound, then the DLL is freed. The extension being unloaded is still
  mapped while dependents are notified, so they can call into it one last time. `sm exts reload` skips all
  of this (Gotcha 1).
- **The dependency warning is conservative.** `sm exts unload` lists "will unload the following extensions"
  without asking those extensions; the real unload honours `QueryInterfaceDrop`.
- **Sharesys interfaces** are C++ classes deriving from `SMInterface` (name and version). Both DLLs need the
  same class layout, so use one shared header. `RequestInterface` records a dependency every time it
  succeeds, so don't call it again for an interface you already hold or have rejected.
- **The listen-server host can run root admin commands** from the console (`sm_lua`, `sm_wasm`), and plugin
  console commands are also chat commands (`sm_x` → `!x`).
- **Events.** Entity references from `EntIndexToEntRef` are serial-checked handles: a stale one fails
  instead of touching whatever reused the slot. Mods hold refs, never indexes. Events a mod causes while its
  own callback is running (killing a player fires `player_death` synchronously) are queued and delivered
  after it returns, without event fields.
- **Lua 5.4 internals that matter for a sandbox:**
  - The instruction-count hook (`lua_sethook` with a count) never fires inside C functions, so
    `string.find/match/gmatch/gsub` (one C call, backtracking matcher) can't be interrupted by fuel.
  - `__gc` finalizers run with hooks disabled (`allowhook = 0` during GC metamethods), so a looping
    finalizer can't be stopped either.
  - An object is only marked for finalization if `__gc` is already in its metatable when `setmetatable`
    runs.
  - Coroutines created from Lua inherit the creating thread's hook, so one global hook covers them.

## Build steps
1. Clone the SourceMod SDK (`1.12-dev`, with submodules) into the project's `third_party/`.
2. Build the three extensions for `i686-pc-windows-msvc` with `+crt-static` (no vcruntime dependency on the
   server). Compile the bridge plugins with the game's own `spcomp.exe`.
3. Copy into `left4dead2/addons/sourcemod/`:
   - `extensions/*.ext.dll` plus a matching `.autoload` file for each;
   - `plugins/*_bridge.smx`;
   - mods into `wasm/`, scripts into `lua/`.
4. Launch with `-insecure`. Mods and scripts hot-reload within a second of a file change, keeping their
   `persist` state.
5. Linux: cargo-zigbuild for `i686-unknown-linux-gnu.2.17` with libc++ linked statically. The same plugins,
   `.wasm` and `.lua` files work unchanged.

## Verification
- **Simulator first.** A fake L4D2 implements the same host interface (entities with serials, events,
  cvars, chat). It runs the real runtimes and the bridge hub with 72 tests, in both debug and 32-bit release
  builds. 32-bit release matters: a stack bug showed only there (Gotcha 7).
- **In game.** Each check was a console command typed into the game; results were read from
  `console.log` (`-condebug`) and from screenshots of the game window.
  - Calls across runtimes: `!wasmhello` printed "Lua says: ..." from a Lua export.
  - A Tank spawned with `z_spawn tank`: the Lua script buffed and later enraged it, and a Rust mod logged
    its death.
  - A Jockey incap became a bounty in the Rust mod. The claim message reached the SourcePawn plugin's
    forward and the Lua script.
  - Swapping a rebuilt DLL with unload/load reconnected through the bridge.
  - Sandbox fixes: a temporary script ran every check from one command (Gotchas 3-6): runaway pattern
    stopped, `persist` number keys survived a hot reload, device names refused, planted `__gc` ignored.
- **Linux.** A C harness loads all three `.so` files under WSL with a fake bridge, connects the ports
  through the hub and checks that a Rust → Lua call crosses all three libraries.
- **Static checks.** lua-language-server `--check` on the example scripts and the annotations.
- **Not verified:**
  - a real Linux srcds;
  - Versus mode or other players joining;
  - the bridge refusing a runtime built for a different interface version (simulator only).

## Gotchas
1. **The server crashed in `sourcemod.logic.dll` on `sm exts reload`** after installing a rebuilt extension.
   **Cause:** `CLocalExtension::Reload` calls `OnExtensionUnload`, closes and reopens the library, but skips
   `UnloadExtension`. The native cache keeps entries whose `sp_nativeinfo_t` pointers (with their names) point
   into the freed DLL, and the new DLL's `AddNatives` looks them up. The minidump showed the fault at a
   string compare reading `native->name`, with the new DLL mapped. Any extension with natives is affected
   once its binary changes. **Fix:** never reload a changed extension. Run `sm exts unload <n>`, then the
   confirm command it prints, then `sm exts load <file>`, then `sm plugins load <bridge>`.
2. **A rebuilt extension DLL can't be copied over while the game runs.** **Cause:** Windows locks loaded
   DLLs. **Fix:** rename the loaded file (renaming a mapped DLL is allowed), install the new one, then swap
   as in Gotcha 1 or restart the game.
3. **`string.find(s, "%a*%a*b")` over a 5000-byte string froze the server for about 3.5 minutes,** even
   with an instruction budget and a 1 s wall-clock check. **Cause:** the pattern matcher backtracks
   polynomially inside one C call, where the hook can't fire; the wall-clock check only ran after it
   returned. A Lua-side guard counting `.`-wildcards missed `%a*` and `[^x]*`. **Fix:** vendor the lua-src
   crate (`[patch.crates-io]`) and add a step budget to `match()` in `lstrlib.c` (5M calls per search;
   measured in game, a runaway search stops after 0.05 s, where 50M took 0.5 s). Running out raises an
   ordinary "pattern too complex" error. Declare the C sources in a `build.rs` (`rerun-if-changed`):
   Cargo doesn't treat them as inputs, so an edited budget was silently not rebuilt.
4. **A script could still create an unstoppable finalizer** despite a guarded `setmetatable`. **Cause:**
   the sandbox's own constructors (entities, vectors) used the raw `setmetatable` on metatables the script
   could reach (`Entity` is global, and `getmetatable(vec3())` returns the vector metatable). **Fix:**
   internal constructors strip `__gc` from the metatable before every use.
5. **Hot reload lost all state for tables like `persist.kills[userid]`.** **Cause:** state was saved
   through serde JSON, which needs string keys; one number key failed the whole save. **Fix:** keep reload
   state as an exact in-memory snapshot (any scalar key type, raw bytes). Use JSON only for `json.encode`,
   with its own converter: a dense 1..n table is an array, anything else an object with stringified keys.
6. **A file name could block the server.** **Cause:** a sandboxed file API that only rejected `..` and
   absolute paths still accepted Windows device names: opening `CON` reads console input. **Fix:** reject
   `CON`/`PRN`/`AUX`/`NUL`/`COM1-9`/`LPT1-9`/`CONIN$`/`CONOUT$` (with or without an extension), `:`, and
   trailing dots or spaces, on every platform.
7. **Longer Wasm callbacks crashed the 32-bit server** (stack overflow). **Cause:** wasmi's tail-call
   dispatch isn't compiled to real tail calls on 32-bit x86, so each executed instruction grew the native
   stack past the game's 1 MB main stack. **Fix:** enable wasmi's `portable-dispatch` on `target_arch =
   "x86"`, with a regression test in the 32-bit release run.
8. **Spawning an entity with a model that wasn't precached killed the server.** **Cause:** a fatal engine
   error, not a recoverable one. **Fix:** the spawn op precaches the model first.
9. **Buffs set in `tank_spawn` didn't stick.** **Cause:** another plugin on the server ("Tank HP 200%")
   sets Tank health after spawn. **Fix:** expect other plugins to overwrite health; apply buffs a moment
   later, or check what else is installed.
10. **`z_spawn hunter` did nothing.** **Cause:** the host player was spectating, so there was no crosshair
    position to spawn at. **Fix:** spawn through left4dhooks (`L4D_GetRandomPZSpawnPosition` +
    `L4D2_SpawnSpecial`), exposed as an API op.
11. **Long console commands were cut off** ("Encountered command which overflows the argument buffer..
    Clamped!"). **Fix:** define helper functions in the script REPL with one command, then call them with
    short ones.
12. **Idle time read as "active" right after driving the game.** **Cause:** `um win drive` uses
    SendInput, which resets the system's last-input time that `idle` reads. **Fix:** check `idle`
    *before* driving; after driving, ask the human instead of trusting the number.
13. **`console.log` keeps growing across launches** (`-condebug` appends). **Fix:** record the line count
    before a command and read only new lines.

## Assets
None. Server-side code only.

## Cost and time
Two days of agent sessions with a human checking in. The in-game checks took a few minutes each, using the
console and screenshots.

## Open questions
- Run on a real Linux srcds with SourceMod (only the WSL smoke test so far).
- A pre-damage hook (SDKHooks `OnTakeDamage`) as an API op, so scripts can change or cancel damage.
- Make script state survive an extension DLL swap (it lives in extension memory today).
