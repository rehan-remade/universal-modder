---
kind: game
title: 'AI companion in Fallout: New Vegas through an xNVSE + JIP file bridge, and the batch-script traps that crash NVSE'
game: 'Fallout: New Vegas'
games_also:
- Valheim
game_version: steam 22380, buildid 1510068, FalloutNV.exe 1.4.0.525 (32-bit, not 4GB-patched)
platform: windows
engine: creation
route: loader-api
tools:
- xNVSE 6.4.9
- JIP LN NVSE 57.30
- Ollama (qwen3-abliterated 4B)
- kokoro-onnx (Kokoro-82M)
- onnx-asr (Parakeet TDT 0.6B v2)
- s2.cpp (Fish S2 Pro q6_k, optional voice)
anti_cheat: none (single-player); new character, saves backed up before the first modded launch
status: working
agents:
- Claude Code (Opus 5.5)
humans:
- Culp
date: '2026-10-18'
links:
- ../../techniques/bridge-contracts-ownership-units-and-lifecycle.md
tags:
- ai-companion
- llm
- tts
- speech-recognition
- file-bridge
- xnvse
- jip-ln
- batch-script
- crash
---
# AI companion in Fallout: New Vegas through an xNVSE + JIP file bridge, and the batch-script traps that crash NVSE

> A talking AI companion (a Large Dog called Cult) in Fallout: New Vegas. He perceives nearby actors, knows the
> player's location, time, quest and objectives, takes spoken orders (follow, stay, attack, defend, flee), chats
> in character and speaks. Script-extender scripts and an external Python process share files. The same
> companion runtime already ran in Valheim (BepInEx HTTP bridge), so New Vegas only needed an adapter: perceive,
> act, say, world. The human verified it by voice in game. Most of the effort went into silent script-compile traps,
> one of which crashed NVSE repeatedly. They are listed under Gotchas.

## Setup
- Steam build above, Windows 11, RTX 5070 12 GB. New character; saves zipped before the first modded launch.
- xNVSE 6.4.9 (GitHub release) and JIP LN NVSE 57.30 (Nexus). No other mods, no 4GB patch, no engine fixes.
- **Launch through `nvse_loader.exe`.** Starting from Steam didn't load NVSE in this setup, and the only symptom
  was `GetNVSEVersion` being unknown in the console. Point the desktop shortcut at the loader. (xNVSE's README
  says a Steam launch works when Steam's in-game overlay, its "Steam Community" option, is enabled, or after the
  4GB patch.)
- `Data\NVSE\nvse_config.ini`: `bAlwaysPrintScriptCompilationError=1`, or compile errors stay invisible.
- The external side: Python 3.11, Ollama, the kit's own venv. Nothing else is installed into the game.

## Route and why
A loader-API file bridge. JIP's main-loop callback runs a batch script every 15 frames. It writes perception
files and runs one pending command line that the Python side drops in a file. Considered: a native NVSE plugin
with a socket (more work in a 32-bit C++ toolchain, and the files were fast enough); an ESP made with the GECK
(not needed: everything is done with runtime commands on existing forms). The prior-art repos found
([chasm](https://github.com/chasmlol/chasm) / [chasm-bridge-fnv](https://github.com/chasmlol/chasm-bridge-fnv))
carry no licence, so they were used for ideas only.

## How the game works (what we had to learn)
- **JIP Script Runner:** text files in `Data\NVSE\plugins\scripts\` run on game events, chosen by name prefix.
  `gr_` runs at game start (once per launch) and `ln_` on every load or new game; there are also `gl_`, `gn_`,
  `gs_`, `gx_` and `xm_`.
- `SetGameMainLoopCallback (begin function {} ... end) 1 15` runs a lambda every 15 frames. **Main-loop callbacks
  survive loading a save**, so an `ln_` script that registers one adds another on every load (see Gotchas).
  JIP's source drops a callback before a load only when its mode flag (4th argument, default 3 = GameMode +
  MenuMode) includes 8, so `... 1 15 11` should also give one loop per load. That variant wasn't tested here.
- `RunBatchScript "<path>"` (JIP) compiles a text file and runs it. It **caches by file name once compiled**, until
  the game restarts. The key is the bare file name, not the path, so two `tick.txt` in different folders share one
  entry. A file that FAILS to compile is not cached and is re-parsed on every call.
- In our tests `RunScriptSnippet` ran only the first statement of a multi-line string (CRLF, LF and literal `\n`
  all tried), so here it was only used for one-liners such as `RunBatchScript "...cmd_123.txt"`.
- `ReadStringFromFile` / `WriteStringToFile` (with `%r` newline, `%i` form id, `%n` name, `%g` number, `%z`
  string) are the whole transport.
- Perception: `GetFirstRef 200 1` / `GetNextRef` walk the actors around the player. Per actor:
  `GetDead`, `GetCombatTarget`, `GetShouldAttack player`, `GetPlayerTeammate`, `GetAV Health` / `GetBaseAV Health`,
  `GetDistance player`. 1 game unit ≈ 0.01428 m.
- World: JIP's `CCCLocationName` on the player gives readable places ("at Goodsprings", "SE of Goodsprings"), plus
  `GameHour`, `GetActiveQuest`, `GetActiveObjectives` (an array) and `GetObjectiveText quest id`, and `GetLevel`.
- Commands on refs: `BuildRef <loadIndex> <low 24 bits as decimal>` makes a ref from a runtime form id, and it
  works for `FF` (player-placed) refs too. Follow/wait use Rex's companion packages with `AddScriptPackage`.
  The dog is `PlaceAtMe` of the Large Dog base form, then `RemoveFromAllFactions` and `SetPlayerTeammate 1`.
  `SetRefName` changes the HUD name but not what `%n` prints.

## Build steps
1. Install xNVSE + JIP, switch the shortcut to `nvse_loader.exe`, and turn on compile errors in `nvse_config.ini`.
2. `gr_` script: write a `registered` flag file with 0. `ln_` script: if the flag is not 1, write 1 and register
   the main-loop lambda that runs the tick batch file. That gives one loop per launch, however many loads.
3. Tick batch file: heartbeat file; `RunBatchScript` of the perception file; read the command file, blank it to
   `" "` (an empty format string does not compile), then `RunScriptSnippet` of what was read.
4. The external side writes each command as a NEW batch file `cmd_<n>.txt` (new name = fresh compile) and puts
   the single line that runs it into the command file. It requests the world script every 3 s the same way.
5. Before an adapter calls any script repeatedly, run it once through the live bridge and check its output file
   appears (a probe script that writes a result file only if it compiled and ran).

## Verification
- The human played with it for about 15 minutes in Goodsprings. Orders by voice worked (follow, defend, flee),
  answers used the real quest state ("talk to Sunny", the bottle and gecko objectives) and places. The dog
  defended the player against geckos.
- `perceive.txt` refreshed every tick (about 14 actors); the command file was consumed and blanked; `world.txt`
  tracked objective changes live.
- After the gotcha fixes below: zero script errors in `nvse.log` / `falloutnv_error.log` in a full session.
- NOT verified: hours-long sessions. The vanilla engine still crashed once after about 8 min (in FalloutNV.exe,
  with audio-sync warnings). We chose not to install stability fixes (4GB patch, NVTF, a crash logger), so that is
  unresolved.

## Gotchas
1. **A whole batch script silently does nothing.** **Cause:** a variable named `r`. NVSE: "Invalid variable name
   r: Command with that name already exists." Every array/foreach test also used `ref r`, which made arrays look
   broken. **Fix:** never name a variable `r` (`who`, `tgt` work). Arrays and foreach then work fine.
2. **Literal ids and editor IDs don't compile at runtime.** `0015EF63.GetDistance player` and
   `PlaceAtMe VCrTier1DogLargeNR` both fail; New Vegas drops most editor IDs after loading. **Fix:**
   `let x := BuildRef <index> <low24>` for both refs and base forms.
3. **The game crashes in `nvse_1_4.dll` at the same offset, 3–25 min in, every session.** **Cause:** a world
   script with `if (ar_Size objs) > 0`, which the legacy `if` parser rejects ("Mismatched brackets"). It never
   compiled, so it was re-parsed on every 3 s request (58 errors in `nvse.log`) until NVSE crashed.
   **Fix:** compute into a variable first (`let cnt := ar_Size objs` / `if cnt > 0`). The caller backs off to one
   request a minute when the script's output file stops changing.
4. **A crash a minute or two after loading a save (a jump into freed memory).** **Cause:** loops registered from
   the console and from `ln_` kept running across loads, and two of them were failing compiles every tick (6,800
   errors). **Fix:** the `gr_`/`ln_` flag file (one loop per launch); never register test loops from the console.
   Mode flag 8 (above) is the untested alternative.
5. **A changed batch file still behaves like the old one.** **Cause:** `RunBatchScript` caches by name until
   restart. **Fix:** a new file name for every version (and for every command).
6. **Only the first line of a snippet runs.** **Cause:** in our tests `RunScriptSnippet` executed one statement
   (see Open questions). **Fix:** multi-line code goes in batch files; snippets only call them.
7. **An inline lambda fails to compile.** **Cause:** a 512-character limit inside parentheses. **Fix:** the lambda
   only calls `RunBatchScript` on a file.
8. **`playerRef` is unknown in batch scripts.** **Fix:** use `player`.
9. **Typing into the console from automation does nothing.** **Cause:** Unicode keyboard events, which the
   DirectInput console ignores. **Fix:** send one scan-code key press per character (Shift for symbols); the
   console pauses the game, so close it to let the loop run.
10. **`GetActiveObjectives` errors between quest steps.** **Cause:** with no active objective no array is made, so
    foreach on it fails. **Fix:** guard on the size, written as in gotcha 3.
11. **The companion's voice reply never plays after an order.** **Cause:** the instant bark was still playing and
    the reply was dropped. **Fix:** a one-line waiting slot for the newest line (an issue in the external voice
    code, not the game).

## Assets
None from the game. The companion's voice is Kokoro (am_fenrir, instant). Fish S2 Pro (s2.cpp, q6_k, in WSL with
CUDA 13.1 for the RTX 5070) was tried as an expressive voice: a voice designed from text, acting tags written by
the LLM. It sounded better but took about 4–5 s per line (RTF ~1.3 on this card), so the human went back to Kokoro.

## Cost and time
About one long day for both the bridge and the companion features, all local and free. Most of the time went
into gotchas 1–4.

## Open questions
- Stability: whether the remaining engine crash goes away with the usual fixes (4GB patch, NVTF) plus a crash
  logger to name it. Not attempted.
- A `goto` order (move to a spot) is not implemented. Perception does not report the companion's custom name.
- Whether `RunScriptSnippet` runs several statements when the lines are joined with `%r` in its format string.
  JIP replaces LF with CR before compiling a snippet, which suggests multi-line snippets are meant to work.
- A small LLM (4B) holds a tone but not depth. A bigger model or a faster expressive voice competes with the
  game for the same 12 GB of VRAM.
