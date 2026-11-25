---
kind: game
title: 'TMNT 2003 PC: porting campaign boss abilities to VS fighters with a d3d9 proxy DLL'
game: Teenage Mutant Ninja Turtles (2003)
games_also: []
game_version: 'Konami PC 2003, tmnt.exe 2,150,400 bytes (PCGamingWiki widescreen-fix exe), PE link time 2003-09-11, x86, image base 0x400000, no ASLR'
platform: windows
engine: native
route: native-hook
tools: [python 3, pefile, capstone, numpy, winlibs i686 GCC 16.2.0, Cheat Engine (not needed in the end), universal-modder um]
anti_cheat: 'none (offline single-player / local VS; no SafeDisc or SecuROM strings in the exe)'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-25'
links:
- https://www.pcgamingwiki.com/wiki/Teenage_Mutant_Ninja_Turtles_(2003)
- https://www.wsgf.org/dr/teenage-mutant-ninja-turtles/en
- https://tcrf.net/Teenage_Mutant_Ninja_Turtles_(GameCube,_PlayStation_2,_Xbox,_Windows)
tags: [renderware, d3d9-proxy, x86, vs-mode, boss-ai, hit-handler, hardware-breakpoint, afs]
---
# TMNT 2003 PC: porting campaign boss abilities to VS fighters with a d3d9 proxy DLL

In the VS mode of Konami's 2003 TMNT, the selectable bosses are separate, much weaker code from their campaign
versions. A `d3d9.dll` proxy (no exe patching) hooks the game at runtime and gives the VS fighters the boss
rules, read out of the boss code: Oroku Saki's armor, power-up and red phase; Hun's half-HP angry phase; Casey's
combo counter; Turtlebot's aimed laser; and Shredder's armor, homing dash, long aimed jump and lightning. The DLL
also forces windowed mode and adds god-mode / one-hit-kill hotkeys. Every feature was verified by the human
playing VS matches, and checked against per-hit decision logs written by the DLL. One extra experiment
(campaign character swap) crashed and was shelved; see Open questions.

## Setup
- Windows 10 x64. The game ran out of the box. The exe in use is the PCGamingWiki widescreen-fix replacement
  (file date 2018); the code addresses below are from that exe.
- Data: CRI AFS archives `TMNT.DAT` (756 entries), `TMNT_V00..V02.DAT`, `bgm.afs`, `se.afs`, `voice.afs`.
  Inside are RenderWare 3.5 streams (`.dff`, `.txd`, `.anm`) plus per-character `.chr` motion tables.
- Code: native x86, RenderWare 3.5 (RW35ActiveD3D9), Direct3D 9, CRI ADX/Sofdec. No ASLR, so every address is
  stable between runs.
- Toolchain: winlibs i686 GCC 16.2.0 (`-m32` on the x86_64 winlibs build does not work; get the i686 one), built
  with `-O2 -masm=intel -shared -static-libgcc` plus a `.def` exporting `Direct3DCreate9`.
- Offline RE in Python: pefile + capstone for disassembly and xrefs. Live RE used small ctypes scripts
  (ReadProcessMemory scans and a hardware-breakpoint "find what writes/executes" debugger, both described below).

## Route and why
- **Rejected: patching the exe.** The human wanted mods kept outside the exe.
- **Considered: a Cheat Engine table.** Fine for values, but the features change logic, so CE was only a
  stepping stone.
- **Chosen:** a `d3d9.dll` proxy in the game folder. The game imports only `Direct3DCreate9`. The proxy loads the
  system d3d9 and, at DllMain, patches code in memory. Two patch styles:
  - 5-byte `jmp` hooks with byte checks;
  - replacing callback pointers that live as `mov [ebp-x], imm32` in each character's "create" descriptor.
- The descriptor-pointer trick is the cleanest. A character's update, cleanup and init functions are passed to
  the entity creator (0x4a6313) as immediates, so changing one immediate wraps the update of exactly one
  character, with no trampoline.

## How the game works (what we had to learn)
**Entities and fighters**
- Every entity is created by 0x4a6313(parent, descriptor, ...). A fighter's object has `[obj+0x60]` = an
  "actor", whose `+0x154` points to a status struct. Its first ten-odd fields are the useful ones:
  - +0 character id; +4 player slot (VS); +0xc side; +0x10 state;
  - +0x2c max HP; +0x30 HP; +0x6c/0x70/0x74 velocity;
  - +0x94 combo count (consecutive hits landed; 60-frame timeout); +0x198 hits in the current attack.
- Just before the status struct sit the fighter's callback pointers (on-attack-landed, on-hit-flags,
  update...). Reading them for a live fighter tells you which code module the character runs, which is how
  boss and VS versions were told apart.
- The actor holds:
  - +0x20 current motion number;
  - +0x7c position (x, y, z);
  - +0x8 animation frame delta. The setter 0x4a3429(obj, k) writes (1/60)/k, so k < 1 means faster.
- Character ids:
  - Turtles 1–4; VS Hun 0x1d; VS Shredder 0x23; VS Splinter 0x33; VS Oroku 0x35; VS Yoshi 0x37;
    VS Turtlebot 0x38; VS Casey 0x39.
  - Boss Oroku 0x34; boss Casey 0x0a; boss Turtlebot 0x1f.
  - Boss Hun and boss Shredder **share** their VS ids (0x1d, 0x23) but run different modules.

**Hits**
- A fighter registers its hit handler every frame through 0x418618(obj, handler).
- Each handler calls a shared damage routine (0x419ea4 / 0x419f71 / 0x432245 families). That routine returns a
  generic reaction code r: 0 light flinch, 3 heavy, 2/5/7 push/launch, 8 always-knockdown, 9 death.
- The handler then maps r to a state through a jump table, calling the character's set-state function.
- Boss handlers are the same shape with extra conditions. Porting a boss rule therefore meant hooking the VS
  handler at the jump table (`cmp eax, 0xa; ja ...; jmp [table+eax*4]`) and returning a different table index.
- VS mode skips the team check (0x419c22: if 0x404969()==1, everyone can hit everyone). That is why VS
  Shredder's own energy wave hurt him while the boss's didn't.

**Motions**
- `.chr` files list the animation clips and then the motions. The motion number is the 0-based index of the
  motion definition, i.e. the "...ListN" label in the file minus one.
- 0x4a3486 / 0x438ed1 give the current clip within a motion (1-based; 0 when the motion has ended).
- The engine signals "motion finished" through [actor+4]=1, but only for non-looping objects. VS fighters never
  get it.

**Input**
- Per-pad words at 0x69f590 (held / pressed / released).
- Per-player controller slots at 0x638a80 + 0xac*i: +0xc held, +0x10 pressed.
- Raw bit 4 is the "special ability" button. Its only built-in VS use is Turtlebot's laser.

**Bosses and the rules ported**
- Most boss "abilities" are AI decisions, not stats. The ports therefore recreate the *condition* the AI would
  have set:
  - **Oroku:** the boss's armor needs an "engaged" flag his AI sets when it decides to fight. It became "VS
    Oroku is attacking, or the opponent is within the boss's 2.0-unit engage range".
- **Oroku boss** (module ~0x42f000–0x4318xx):
  - **Armor:** light hits are ignored while he is engaged and facing the hit (dot > 0.8); flinches play at 2x
    speed; a long combo (attacker combo > 3, cap at 8) or multi-hit chain breaks the armor.
  - **Phases:** a 1800-frame blue/red timer.
  - **Power-up:** state 0x1f with motion 0x27, roar sound 0x1df, aura recolour.
  - **Red phase:** animation k 0.75, or 0.5 while running.
  - **Aura:** 0x42f4dc(frame) creates it; 0x42f2c2(handle, 1 blue / 2 red / 3 fade) recolours it.
- **Hun boss:**
  - **Armor:** reacts only while his current motion is idle or walk; big hits trigger counter-combos rather than
    staggers.
  - **Angry:** the first reacting hit below half HP knocks him down. He turns angry in knockdown state 0x17,
    before standing. Angry adds a red tint and AI aggression only; his armor rules don't change.
- **Casey boss:** on a light hit, if the attacker's combo count is 3 or more, he turns to the attacker and
  starts his heavy attack instead of flinching.
- **Turtlebot:** the laser code is shared by the boss and VS versions. During the hover state the shared code
  turns toward 0x40456e's "nearest player". In VS that resolves to Turtlebot himself (distance 0), and the VS
  hover path doesn't even call it. The port turns VS Turtlebot toward the opponent at the boss's turn rate.
- **Shredder boss:**
  - **Armor:** heavy hits only flinch him; from combo hit 8 he doesn't react.
  - **Combo homing:** during his L×5 combo, the dash included, he turns toward the target every frame at
    rate 4.0.
  - **Jump attack:** an arc to the target. Apex height 3.0, from a constant at 0x58c980:
    y = 3·t·(2n−t)/n². Horizontal speed about 0.313 units/frame, measured.
  - **Lightning:** 0x4388a0(obj, size, effect, bone). It is gated per combo type and step by a small table:
    some steps draw every frame, others only while the hit connects.
- 0x4a3af7(obj, dir, rate) is a **turn** toward a direction, not a movement. Boss "4.0 / 8.0" values passed to
  it are turn rates, not speeds.

## Build steps
1. Install winlibs **i686** GCC. Build the proxy with `gcc -O2 -masm=intel -shared -static-libgcc -o d3d9.dll
   <sources> d3d9.def`; the `.def` exports `Direct3DCreate9=Direct3DCreate9@4`.
2. In `Direct3DCreate9`, load the real `d3d9.dll` from `GetSystemDirectory` (SysWOW64 for this 32-bit process).
   Patch IDirect3D9::CreateDevice (vtable index 16) to force windowed mode, and IDirect3DDevice9::Reset (16).
3. In DllMain, install the hooks:
   - byte-checked 5-byte jmps;
   - immediate swaps in character create descriptors;
   - naked stubs where the hook point is mid-function. Use pushad/popad, and return through `push target; ret`.
4. Copy `d3d9.dll` next to `tmnt.exe` with the game closed. The running game locks the file (see Gotcha 8).
5. Log everything to a text file next to the exe: each hit decision with its inputs, each state change, each
   hook install.

## Verification
- **Oracle 1: the human player.** They knew the bosses from about 100 hours of play, controlled both VS players,
  and reported behaviour after every build.
- **Oracle 2: the DLL's own decision log.** Each armor decision was logged with r, the heavy bit, the combo
  count, facing, distance, state and the outcome. Every report was matched against it.
- **Oracle 3: live measurement of the real boss** before porting:
  - a 60 Hz logger of the boss's state, combo step, motion, position and velocity (240 s in a campaign fight);
  - hardware-breakpoint traces of which code wrote a field or called a function, with stack and arguments.
    These traces caught the exact lightning calls and the input bit.
- Crash oracle: Windows Error Reporting offsets (Event 1000). Map them to the DLL with an unstripped build of the
  same source plus `objdump`.
- **Not verified:**
  - Boss Turtlebot Ver 2.0 (only 1.5 is in Boss Challenge).
  - CPU-controlled versions of every character (only Hun was checked with the CPU).
  - Any build of the exe other than the widescreen-fix one.

## Gotchas
1. **A framed 4K window made the game quit right after start.** **Cause:** the window plus its frame was larger
   than the screen when the backbuffer was 3840×2160. **Fix:** borderless WS_POPUP when the backbuffer fills
   the screen; a framed window only for smaller resolutions.
2. **A "position" function returned a unit vector.** **Cause:** 0x4a3a82 builds the facing direction from the
   yaw; the position is [actor+0x7c] (0x4a3a05). **Fix:** read the actor position directly.
3. **The boss's "4.0 → 8.0 red speed" did nothing when ported.** **Cause:** those numbers go to 0x4a3af7,
   which turns the fighter. The real speed-up is animation k (0x4a3429). **Fix:** scale the frame delta. Hook
   0x4a3429 itself, because the VS code rewrites the delta on every state change and every flinch frame.
4. **Code ran but its effect vanished.** **Cause:** the hook ran *before* the game's per-frame update, which
   overwrote the change. **Fix:** wrap the update callback; do pre-work before and post-work after the original.
5. **A power-up motion looped forever on a VS fighter.** **Cause:** VS fighters never get the engine's "motion
   finished" flag. **Fix:** end the motion after its real length, read from the RtAnim duration in the `.anm`
   headers inside the pack.
6. **The special-key hijack also fired on heavy attacks.** **Cause:** VS state 0x2c is the dash attack (input 4
   in locomotion 0x447684), not a special move. **Fix:** read the raw pad bit (controller slot +0xc, bit 4)
   instead.
7. **The second match crashed inside the DLL.** **Cause:** a cached opponent object from the previous match, or
   one torn down at KO, was read after the game freed it. **Fix:** never keep other fighters' pointers across
   frames. Re-find the opponent every frame via a hook on 0x418618 (every fighter calls it each frame), keep
   entries for 100 ms only, and check them with IsBadReadPtr.
8. **"It didn't work" twice, because the new DLL was never installed.** **Cause:** the running game locks
   `d3d9.dll` and the copy failed silently between turns. **Fix:** compare the installed file with the build
   output (`cmp`) and say "installed and verified" before every test.
9. **The boss's armor looked absolute in play but the code had many conditions.** **Cause:** the AI is almost
   always in its "engaged" attack mode, so the conditions rarely fire. **Fix:** port the conditions and supply
   the missing AI flag with a player-side equivalent (attacking, or within engage range).
10. **The half-HP trigger never fired on a CPU-controlled Hun.** **Cause:** it required Hun to be idle or
    walking when hit, and the VS CPU is almost always attacking. **Fix:** let the trigger fire in any state, and
    block reactions while the knockdown plays.
11. **Off-by-one in combo step mapping.** **Cause:** VS L×5 clips are numbered 1–5 like the boss's steps; the
    dash step was shifted by one. **Fix:** log motion and clip on every hit first, then map. Don't infer from
    `.chr` label text.
12. **GCC put a trap after a call through a function-pointer cast.** **Cause:** a naked trampoline was declared
    `void(void)` and called through a 5-argument type. **Fix:** give naked trampolines the real prototype.

## Assets
None. All visuals reuse the game's own effects, called with the boss's arguments.

## Cost and time
One long session, about a day of wall-clock time. Roughly 25 test builds, most in single-feature rounds.

## Open questions
- **Campaign character swap** (play the story Casey or Splinter slot as a VS boss). The game has by-id
  routines:
  - load files 0x493f05(id);
  - unload 0x493f8a(id);
  - story spawn 0x493d4e(a, b, id, c, d), which knows ids 1–4, 0x33 and 0x39;
  - VS spawn 0x493ff1(cpu, a, b, id, c, d).
  
  Story Casey and VS human Casey take identical spawn arguments. Redirecting the loads and spawns still crashed
  during stage load at tmnt.exe+0xfe2ae (a RenderWare stream read of a null stream), before any of the redirect
  hooks logged. Unknown: which loader feeds that stream, and whether story levels preload characters by
  another path. Shelved.
- The density of Shredder's VS dash lightning versus the boss's was matched by redirecting VS's spark burst.
  Effects of other VS characters weren't audited.
