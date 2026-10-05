# Retro and console games: decomps, recomps, emulators

The user must own the game and dump it themselves. Never download ROMs, ISOs, leaked source or leaked builds.
Knowledge from leaks is fine to use, but some projects refuse anything built on leaked material ("leak
poisoning"; clean decomps such as libsm64 get adopted), so check a project's rules before contributing.

## Is there already a decompilation or port?
Many classics have matching decompilations (C source that compiles back to the identical ROM) and native PC
ports built on them:
- Super Mario 64: `sm64` decomp, `sm64coopdx` (Lua mods, online co-op), libsm64 (SM64 as a library other
  engines embed; G64 embeds it into Garry's Mod);
- Ocarina of Time / Majora's Mask: decomps, Ship of Harkinian, 2 Ship 2 Harkinian;
- Zelda64Recomp;
- Twilight Princess (Dusklight);
- Super Mario Sunshine, Mario Kart 64, Pokémon (pret: pokered, pokeemerald...), Sonic, Metroid...

Search "<game> decomp" / "<game> recomp" / "<game> pc port" first. Modding a decomp means editing C (or the
port's Lua API) and building with your own ROM as the asset source. Examples: Minecraft inside Mario 64 was
built on sm64coopdx, and a new Majora's Mask area was built by Opus on the MM recomp.

## Static recompilation (no source, still native)
Recompilers translate machine code into C that links against a runtime reimplementing the console:
- N64: N64Recomp + N64ModernRuntime (+ RT64 renderer);
- Xbox 360: XenonRecomp / ReXGlue;
- PS2: PS2Recomp;
- GameCube/Wii: DolRecomp;
- PS1: psxrecomp / RecompOne.

A recomp is also the best **oracle** for a clean reimplementation: run or read it to get ground truth, then
write an idiomatic engine (the Skate 3 Rust engine was built this way).

## Starting a decompilation with agents
Tools:
- splat splits the ROM into asm/data;
- m2c gives a first-pass C decompile;
- asm-differ / objdiff compare your compiled function to the original;
- decomp-permuter searches for matching code shapes;
- decomp.me shares scratches.

The agent loop that worked in public write-ups (one N64 game: 2,145 functions in 84 days):
- one function at a time, with a `build-and-verify` script that says exactly how close it is;
- each attempt in its own file, with a hard cap (about 10 attempts), then move on and log it;
- commit every match, and keep a shared `LEARNINGS.md`;
- rank candidates cheapest first (instructions, branches, jumps);
- run several worktrees in parallel, and try another model on the hard ones.

"Pure mechanical decompilation first; modernization/portability afterwards." Budget for it: a large
decomp can take billions of tokens.

## Emulator-based mods (no source needed)
- **Memory scripting:** BizHawk Lua, mGBA Lua/scripting, Dolphin Memory Engine, PCSX2 PINE, RetroArch
  cheats. Find addresses with RAM search. mgba-mcp / PCSX2-MCP expose this to agents.
- **ROM hacks:**
  - patch code or data in the ROM and distribute an IPS/BPS/xdelta patch, never the ROM;
  - existing editors: Lunar Magic (SMW), Wiimm's SZS tools (Mario Kart Wii tracks), Pokémon hacking tools.
- **Dolphin:** texture packs, Gecko/AR codes, Riivolution patches for GameCube/Wii.

## Pitfalls
- Some recomp/decomp communities ban AI-generated contributions. Respect each project's rules and disclose
  AI use.
- Publishers do DMCA recomps and ports even without assets. Keep projects non-commercial; ship patches and
  tools only.
