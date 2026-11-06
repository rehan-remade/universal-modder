---
kind: technique
title: 'Driving DOSBox games from tests: background input, parallel sandboxed instances and screen-state checks'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-25'
links: ["https://www.dosbox.com/"]
tags: [dosbox, dos, automation, testing, background-input, postmessage, parallel, sandbox, screenshots, midi, overlays, memory-pressure, windows, guest-memory, readprocessmemory, conventional-memory, focus-stealing, wmi]
---
# Driving DOSBox games from tests: background input, parallel sandboxed instances and screen-state checks

> How to run a DOS game in DOSBox as a test oracle on Windows: input posted to a background window (no focus,
> no real mouse), exact-frame screenshots, several sandboxed instances in parallel under a machine-wide cap,
> every step checked against the screen, and silence. Built while binary-patching a 1994 DOS strategy game
> (Sid Meier's Colonization 3.0, GOG release) with an 85-test suite that runs in about 10 minutes at 4-10
> instances on a laptop.

## When to use it
- You patch or mod a DOS game and want in-game regression tests that run while the human keeps using the PC.
- You need many game runs (flaky bugs, random events, original vs patched comparisons) and one DOSBox at a
  time is too slow.
- Setup used: DOSBox 0.74-2 (the build GOG bundles), SDL 1.2, Windows 11, Python 3 with `ctypes`, Pillow,
  numpy, psutil.
- Ask the human before the first long run: a suite puts up to 10 DOSBox windows on their desktop and takes most
  of the CPU. Posted messages never move the real mouse or keyboard, but a DOSBox started as an ordinary child
  process can still take the foreground while they type (gotcha 21). Launch it through WMI (below); if you have
  to fall back, check `um win drive --proc dosbox idle` first and don't launch while they're typing. The general
  rules are in [Driving real games safely](driving-real-games-safely.md).

## How

### Input without focus
- Launch DOSBox with `SDL_VIDEODRIVER=windib` in its environment. When the variable is unset, DOSBox 0.74 on
  Windows switches SDL 1.2 to its DirectX driver (SDL's own default has been `windib` since 1.2.10), and that
  driver reads the keyboard and mouse through DirectInput instead of window messages (the keyboard only while the
  window is in the foreground). `windib` reads ordinary window messages, so posted ones reach the game.
- Post `WM_KEYDOWN`/`WM_KEYUP` (and `WM_SYSKEYDOWN` with Alt) to DOSBox's window with `PostMessage`, about 80 ms
  between down and up (shorter than a frame and the game misses it), and set the extended-key bit for arrows,
  Ins/Del/Home/End/PgUp/PgDn. Before input, post `WM_ACTIVATE` (wParam 1) to DOSBox only: SDL drops input while
  it thinks it is inactive, and the real focus never moves.
- Mouse: `autolock=false` in `[sdl]` (otherwise DOSBox drops mouse motion until the mouse is locked). Post
  `WM_MOUSEMOVE` in a few small steps, then button down/up at the target, in client coordinates scaled from
  320x200. Unlocked, DOSBox 0.74 sets the DOS cursor from the window position in graphics modes, but the mouse
  driver's motion counters, which some games read instead, only get the moves between events.
- **Start DOSBox outside the terminal's process tree**, or each new DOSBox window can take the foreground from
  the human (gotcha 21). On Windows, create it through WMI (`Win32_Process.Create`): the new process's parent is
  `WmiPrvSE.exe`, not your test runner. A plain child process (`subprocess.Popen`, `Start-Process`,
  `CreateProcess`) of a test started from the active console is not enough, even with a "don't activate" show
  flag. From Python, through PowerShell's CIM cmdlets:

  ```python
  q = lambda t: "'" + str(t).replace("'", "''") + "'"
  env = dict(os.environ, SDL_VIDEODRIVER="windib")      # WMI does NOT inherit your environment: pass it
  envlist = ",".join(q(k + "=" + v) for k, v in env.items() if "\n" not in v and "\0" not in v)
  ps = ("$si = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property "
        "@{ShowWindow=[uint16]7; EnvironmentVariables=[string[]]@(" + envlist + ")}; "
        "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
        "@{CommandLine=" + q(subprocess.list2cmdline([dosbox, "-conf", conf, "-noconsole"])) + "; "
        "CurrentDirectory=" + q(dosbox_dir) + "; ProcessStartupInformation=$si}; "
        "Write-Output $r.ReturnValue $r.ProcessId")
  out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, text=True, timeout=60).stdout.split()
  pid = int(out[1]) if len(out) >= 2 and out[0] == "0" else None   # ReturnValue 0 = started
  ```

  `ShowWindow=7` is `SW_SHOWMINNOACTIVE`. Set `CurrentDirectory` explicitly (otherwise it is the WMI host's, not
  yours) and pass every environment variable DOSBox needs explicitly. The process isn't your child, so track it
  by the returned PID: find its window by PID, and kill it by PID. A job object or "kill my children" won't reach
  it. Keep a plain child-process launch only as a fallback for when WMI fails, and log when you use it.

  The snippet puts your whole environment on PowerShell's command line, where other programs (process lists,
  logging and security tools) can read it. If it holds secrets (API keys, tokens), pass a short list instead:
  `SDL_VIDEODRIVER` plus what DOSBox needs, such as `SystemRoot`, `PATH`, `TEMP` and `TMP` (not tested here).
- Launch minimised without activation (`SW_SHOWMINNOACTIVE`, above), then
  `ShowWindow(hwnd, SW_SHOWNOACTIVATE)` once the window exists: screenshots need it restored, not minimised.
- `EnableWindow(hwnd, FALSE)` once it is shown: the human's stray clicks and keys no longer reach the game,
  while posted messages still do. Re-enable it (or skip this) when you want to play along.

### Screenshots
- **Exact frame, slow:** DOSBox's own capture (post Ctrl+F5); `captures=` in `[dosbox]` sets the folder. It
  writes a PNG of the emulated 320x200 frame, about 0.5 s per capture.
- **Fast:** copy the window's client area (`PrintWindow`/`BitBlt`) and scale it to 320x200: about 5 ms. Check it
  pixel for pixel against a Ctrl+F5 capture once per window size and fall back if they ever differ. The process
  doing the copy must be DPI-aware, like DOSBox's window (gotcha 6).

### One sandbox per test process
Give every test process its own folder (e.g. `work/run/<run id>/`) holding:
- a copy of the game folder it launches (saves, autosaves, high-score files and the EXE never collide);
- its own DOSBox conf, written from a template by replacing the `mount c:` and `captures=` **lines** (gotcha 9);
- its own capture folder.

Remember the PID of the DOSBox you started and make every helper (find window, input, capture, kill) act on
that PID only; never "the first DOSBox window" and never kill by process name. A runner script then starts N
tests as separate processes. Remove the sandbox at exit, but first move any screenshot a test saved under its
own name to a shared results folder (gotcha 10).

### A machine-wide cap
Parallel test runners, agents and git worktrees all launch DOSBox, so cap the total, not per runner:
- N lock files in a fixed folder (e.g. `~/.coltest-dosbox-slots/slot0..N.lock`); `launch()` takes one with an
  OS byte lock (`msvcrt.locking(..., LK_NBLCK, 1)` on Windows), which is released automatically if the process
  dies; it waits when all are taken.
- Plus a load gate: beyond the first two games, wait while total CPU is over ~80 % or free RAM under ~1 GB
  (psutil).
- Measured on an Intel Core Ultra 7 155U laptop (14 threads, 15.5 GB): each DOSBox at `cycles=max` costs about
  9 % total CPU and 80 MB; 10 at once was the useful ceiling. CPU, not RAM, is the limit.

### Check the screen before and after every step
Fixed sleeps followed by blind clicks are the main source of flaky and slow tests.
- Name what is on screen from small reference crops: title, load list, map, message box, menus, the game's
  own screens. Match text by its exact palette colour (DOS games draw text in a few fixed colours) with a
  tolerance for partly covered glyphs (gotcha 8).
- `wait_until(state, timeout)` polls the fast capture instead of sleeping; every action confirms the expected
  state first and the change afterwards; any timeout raises with a named screenshot.
- Stall detector: the same frame for 90 s with nothing to answer → fail at once with a screenshot, instead of
  waiting for a long overall timeout.
- Use the game's own files as the oracle where possible: the start-of-turn autosave tells you the turn
  advanced and holds the game state to assert on.
- Original vs patched (or several cases) run as parallel processes, not one after another.

### Read the game's state from guest RAM
When a run hangs, the screen alone rarely says why. DOSBox keeps the guest's conventional memory in one private
block of its own process, so a host-side script can read it without touching the game:
- `OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION)`, walk the regions with `VirtualQueryEx`, and find
  the guest RAM block by a signature string from the game's data segment (or by its size); read the first
  1 MB + 64 KB with `ReadProcessMemory`. Read-only: no input, no focus, the game keeps running.
- Decode the DOS memory picture from there: the MCB chain (DOSBox's List of Lists sits at 0080:0026, the first
  MCB segment two bytes before it), the game's blocks and the largest free block.
- Then read the game's own variables at their DGROUP addresses (turn phase, active unit, mode flags). In this
  project a "hang" turned out to be the game's view mode, waiting correctly for a key (gotcha 16).

### Measure free conventional memory before adding code
If you patch code or tables into the executable, every paragraph you add is 16 bytes less free DOS memory at
run time. Measure the worst case instead of guessing:
- read the game's allocator state from guest RAM (many DOS games record the largest free block after each
  allocation, or keep a low-water mark), across the heaviest scenarios (big late games, every report screen,
  save/load) and with EMS/XMS on and off;
- build test EXEs with a deliberately bigger block to see what fails first (here: large optional buffers were
  refused and the game fell back to smaller ones; nothing crashed until far past the budget);
- remember the store launcher: GOG starts this game through a front-end EXE that loads it into its own process
  and costs about 5 KB more than starting the game directly;
- turn the result into a budget with a margin and an automated test that fails when a build exceeds it.

### Silence
`[mixer] nosound=true` silences DOSBox's mixer (Sound Blaster, OPL, PC speaker, CD audio). MIDI bypasses it
(gotcha 4): also set `[midi] mididevice=none`, and keep `mpu401=intelligent` if the game is configured for
MIDI.

### Make rare overlay and memory bugs deterministic
Many DOS games use an overlay manager that swaps code in and out of conventional memory. A stress conf with
`[dos] xms=false ems=false umb=false` makes it swap constantly; a bug that showed up once in 10-20 normal runs
then fails every time (gotcha 3). Run the tests that touch your patched code under both confs.

## Not verified
Only DOSBox 0.74-2 (SDL 1.2) on Windows 11, driving one game. DOSBox Staging and DOSBox-X's SDL2 builds have no
`windib` or `directx` video driver (SDL2's is `windows`), so the input section won't carry over to them as written.

## Gotchas
1. **Posted keys did nothing; clicks did nothing.** (2026-10-22.) **Cause:** DOSBox 0.74 picks SDL 1.2's DirectX
   driver, which reads DirectInput instead of window messages, and SDL ignores input while it believes it is
   inactive. **Fix:** `SDL_VIDEODRIVER=windib` at launch and a posted `WM_ACTIVATE` before input;
   `autolock=false` for the mouse.
2. **Enter on the map "ended the turn" but sometimes skipped or moved units, and hid a real bug.** (2026-10-24.)
   **Cause:** pressing a default key blindly also answers popups you never looked at; a debug assertion box of
   the game's ("DANGER, WILL ROBINSON") was being dismissed by the test for days. **Fix:** recognise the screen
   and press Enter only on a recognised message box; click the game's own "end turn" control where it is.
3. **A test failed about 1 run in 10 with garbage prompts, random exits to DOS or a frozen screen.** (2026-10-25.)
   **Cause:** the patch entered new code through a stub the game's overlay (VM) manager didn't recognise as a
   call from an overlay, so it didn't protect the return address; when memory was tight and the overlay was
   swapped out, the hook returned into the wrong code. With EMS/XMS present that was rare. **Fix:** reproduce
   under the no-EMS/XMS/UMB conf (now every time), then fix the stub. Keep that conf in the suite.
4. **Games still played music with `nosound=true`.** (2026-10-25.) **Cause:** DOSBox sends MIDI straight to
   the Windows MIDI synthesizer, outside its mixer. **Fix:** `[midi] mididevice=none`.
5. **With `mpu401=none` the game hung on a black screen at start.** (2026-10-25.) **Cause:** the game was set up
   for General MIDI and waits for the MPU-401. **Fix:** keep `mpu401=intelligent`, silence it with
   `mididevice=none` (gotcha 4).
6. **The fast window copy returned only the top-left part of the picture.** (2026-10-25, 125 % display
   scaling.) **Cause:** DOSBox's window is DPI-aware and the capturing process wasn't, so it got DPI-virtualised
   coordinates. **Fix:** make the capturing process DPI-aware before calling `PrintWindow`/`BitBlt`.
7. **The test clicked where "End of Turn" usually is and kept toggling tile info instead.** (2026-10-24.)
   **Cause:** the side-panel text moves down when the panel lists a colony or units, and when a unit waits for
   orders the spot holds unit details. **Fix:** find the text by its glyphs and palette colour anywhere in the
   panel, click it there, and handle "a unit is waiting" separately (skip it with the game's key).
8. **Turn 1 worked, then the test waited until its timeout.** (2026-10-24.) **Cause:** after clicking, the
   (emulated) mouse pointer stayed on the text, so the next turn's exact glyph match failed. **Fix:** park the
   pointer in a neutral spot after every click, and accept about 85 % of a template's pixels.
9. **Tests in a git worktree silently played the main checkout's build.** (2026-10-25.) **Cause:** the conf
   template names the main checkout's game folder and the per-run conf replaced that exact path text; in a
   worktree the path differs, nothing was replaced, and DOSBox mounted the main folder. **Fix:** rewrite the
   `mount c:` and `captures=` lines by pattern and fail loudly if either is missing.
10. **Failure screenshots vanished.** (2026-10-24.) **Cause:** tests renamed captures inside the sandbox's
    capture folder, which is deleted at exit. **Fix:** on cleanup, move every capture not named like DOSBox's
    own (`<program>_NNN.png`) to the shared screenshots folder.
11. **A menu ignored Enter for minutes, about 1 run in 15.** (2026-10-25.) **Cause:** a click was still in
    progress when the menu opened; this game's menu loop then switched to mouse mode, where the highlight
    follows the pointer (outside the box) and Enter selects nothing. The unpatched game did the same. **Fix:**
    when a box ignores Enter and shows no highlighted row, press Down, then Enter; check for a highlight first so
    menus with a valid default aren't changed.
12. **Overlay programs need their own EXE folder.** (2026-10-22.) **Cause:** the overlay manager reopens the
    EXE by name from the current drive to load overlays, so a different EXE (original vs patched) in the same
    mount reads the wrong overlays. **Fix:** one game-folder copy per EXE variant, mounted as `C:`.
13. **A probe killed the running suite.** (2026-10-23.) **Cause:** the launcher killed every DOSBox before
    starting its own. **Fix:** PID-scoped kill (see "One sandbox per test process"); keep a separate "kill
    all" for manual clean-up only.
14. **Fast retries kept replaying the same battle.** (2026-10-25.) **Cause:** the game seeds its RNG from the
    BIOS clock; restarts within the same tick replay the same rolls. **Fix:** a short random pause before
    retrying a random event.
15. **Saves rebuilt by parallel tests could be read half-written.** (2026-10-24.) **Cause:** several tests
    rebuild the same scenario save before running. **Fix:** skip the write when the bytes are identical, else
    write a temp file and `os.replace` it, retrying while another process has it open.
16. **A game run "hung" with a unit waiting but no prompt, rarely and only under load.** (2026-10-25.) **Cause:**
    the test clicked "End of Turn" a second time; the click was made while the game was busy ending the turn,
    so the mouse driver's latched button state was read at the next turn's first input poll, where it put the
    game into view mode, waiting for a key. The unpatched game did the same. **Fix:** only act on *live* UI:
    click the end-turn text only while it blinks (stale text left on screen doesn't), and after a key wait for
    the screen to change before acting again. Clicks are latched, never just lost.
17. **Keys and clicks were lost under load (a menu didn't open).** (2026-10-25, 6-10 parallel instances.)
    **Cause:** the emulated game missed a posted key or click while busy. **Fix:** retry an action only if
    nothing at all happened (the screen is still the same, or still the plain map), and never retry a move,
    whose popup may just be slow; restart a menu sequence from the map if the menu closed without the item.
18. **Alt+G was ignored for a minute at the start of a turn.** (2026-10-25.) **Cause:** this game ignores
    keys while units make their automatic (goto/route) moves. **Fix:** keep retrying menu keys until the moves
    are over (bounded), instead of failing after a few seconds.
19. **A message box popped up just as the test opened a menu.** (2026-10-25.) **Cause:** the result of the
    last action arrived late. **Fix:** if a menu step finds a message box instead, answer it and redo the step.
20. **A full-screen "is the screen still?" check never finished.** (2026-10-25.) **Cause:** the selected unit
    and the end-turn text blink, so the frame never stays the same. **Fix:** compare screen *states* (what the
    screen shows) or masked regions, not whole frames.
21. **New DOSBox windows stole the focus from the human's terminal.** (2026-10-25.) A foreground watcher logged
    17 takeovers in about 3 minutes of a parallel suite run, each when a new DOSBox window appeared. **Cause:**
    the tests ran as descendants of the console program the human was typing into, and Windows lets processes
    started from the foreground process bring their first window to the front. The DOSBoxes were started with
    `SW_SHOWMINNOACTIVE`, which didn't stop it: SDL creates and shows its own window. It only happened while the
    human was using that console, so a test made while they weren't typing showed no steal. **Fix:** create
    DOSBox through WMI so it has no link to the console (see "Input without focus"). Afterwards a 15-minute
    watch across a full parallel suite logged none. **Check it:** poll `GetForegroundWindow()` every 100 ms
    during a suite run and log when the foreground window's process is a DOSBox. Two more traps: a test process
    that was already running (for example, one waiting for a free slot) keeps the launch code it imported, so
    restart runs before you measure. And when you swap the launch code, test the whole launch function, not
    just the new helper: a leftover `return p.pid` after the change failed every in-game test.

## Seen in
- Sid Meier's Colonization 3.0 (DOS, GOG release; VICEROY.EXE, an RTLink-overlaid executable) binary-patching
  project (no public game note yet).
- Related: [Driving real games safely](driving-real-games-safely.md) (input and focus rules for any game) and
  [Running several isolated tModLoader test instances in parallel](running-several-isolated-tmodloader-test-instances-in-parall.md)
  (the same sandbox-per-instance idea for Terraria).
