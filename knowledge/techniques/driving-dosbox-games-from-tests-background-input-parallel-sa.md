---
kind: technique
title: 'Driving DOSBox games from tests: background input, parallel sandboxed instances and screen-state checks'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-25'
links: ["https://www.dosbox.com/"]
tags: [dosbox, dos, automation, testing, background-input, postmessage, parallel, sandbox, screenshots, midi, overlays, memory-pressure, windows, guest-memory, readprocessmemory, conventional-memory, focus-stealing, wmi, flaky-tests, retries, orphan-processes, job-objects, host-ram, stack-depth, near-heap, umb, bios-clock]
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
- **Fast:** copy the window's client area (`PrintWindow`/`BitBlt`) and scale it to 320x200: about 5 ms. The process
  doing the copy must be DPI-aware, like DOSBox's window (gotcha 6). Check the copy once per window size **without
  sending a key**: sample each game pixel's block at 1/4 and 3/4 as well as the centre and require them to agree
  (99.5 % here), i.e. a plain block-scaled picture; warn and carry on if not. The first version compared with a Ctrl+F5
  capture instead, and under load that put a stray F5 into the game (gotcha 22). Keep Ctrl+F5 for a minimised window
  or an explicit "exact capture" mode.

### One sandbox per test process
Give every test process its own folder (e.g. `work/run/<run id>/`) holding:
- a copy of the game folder it launches (saves, autosaves, high-score files and the EXE never collide);
- its own DOSBox conf, written from a template by replacing the `mount c:` and `captures=` **lines** (gotcha 9);
- its own capture folder.

Remember the PID of the DOSBox you started and make every helper (find window, input, capture, kill) act on
that PID only; never "the first DOSBox window" and never kill by process name. A runner script then starts N
tests as separate processes. Remove the sandbox at exit, but first move any screenshot a test saved under its
own name to a shared results folder (gotcha 10).

### Find where a hang is: the guest CPU's registers
Guest RAM shows the state, not the code that is looping. DOSBox 0.74 (32-bit) keeps the emulated CPU's
registers in its own data segment, so a host script can sample CS:IP read-only too:
- the segment registers are a global array of eight 16-bit values followed by their eight 32-bit
  physical bases (in real mode base = value x 16): find it by that pattern in the DOSBox module's
  data with `ReadProcessMemory`; the general registers (eax ... edi, then eip and flags) sit at a fixed
  offset after it in a given build (E0h in GOG's 0.74-2; check it against the flags word);
- a hang detector then waits until the frame has been unchanged for N seconds (90 here) and saves a few
  dozen CS:IP samples, the guest RAM and a screenshot: the samples show which routine it loops in.

### A machine-wide cap
Parallel test runners, agents and git worktrees all launch DOSBox, so cap the total, not per runner:
- N lock files in a fixed folder (e.g. `~/.coltest-dosbox-slots/slot0..N.lock`); `launch()` takes one with an
  OS byte lock (`msvcrt.locking(..., LK_NBLCK, 1)` on Windows), which is released automatically if the process
  dies; it waits when all are taken.
- Plus a load gate: beyond the first two games, wait while total CPU is over ~80 % or free RAM under ~1 GB
  (psutil).
- Measured on an Intel Core Ultra 7 155U laptop (14 threads, 15.5 GB): each DOSBox at `cycles=max` costs about
  9 % total CPU and 80 MB; 10 at once was the useful ceiling. CPU, not RAM, limits one suite.
- **RAM still runs out when several suites or agents overlap.** Each test is also a Python process, and a
  parallel suite of in-game tests runs next to a pool of emulated (CPU-only) tests. On 2026-10-26 two full suites at
  once (2 x 3 games plus their Python processes) ran the 15.5 GB laptop out of memory; the agent host then
  killed the test runs, and the DOSBoxes survived them (gotcha 23). What is in place since:
  - a machine-wide lock so only one full suite runs at a time, whichever checkout or worktree starts it (an OS byte
    lock on a file in the home folder; the second suite waits);
  - an automatic `-j`: 4 games when no DOSBox is running and at least 6 GB is free, else 3;
  - for the agents: at most 3-4 parallel work streams of 2 games each, fewer while a full suite runs, checked against
    free physical memory (about 3.8 GB was typical with everything running);
  - emulated tests run below normal priority, so the timing-sensitive games keep their CPU.

### Test DOSBoxes must end with their test
Started through WMI, DOSBox is not a child of the test, so killing the test (Ctrl+C, `taskkill /F`, an agent host
stopping a run) leaves it running, minimised and undriven. Three layers, all by exact PID:
- **Job object:** after the launch, put the DOSBox into a kill-on-close job held by the test process; Windows
  ends it however the test ends. Nested jobs work (the WMI-started process is already in the WMI host's job). No
  extra process, no memory.
- **Watchdog fallback** if the job can't be assigned: a windowless `pythonw` started through WMI waits on both
  process handles and terminates DOSBox when the owner ends (about 7 MB; a hidden PowerShell `Wait-Process` would
  cost 60-80 MB each).
- **Sweep at start:** each sandbox gets an `owner.json` (owner PID and creation time, DOSBox PID and creation
  time). Before launching, and when a runner starts, terminate DOSBoxes whose `-conf` is in one of your own
  sandboxes and whose owner is gone. Decide "gone" by PID **and creation time** (PIDs are reused within minutes) and
  re-check the creation time on the handle you terminate through. Never touch other confs (the human's own DOSBox),
  manual sessions or unknown run ids.
- Python children outlive a killed parent on Windows too, `ProcessPoolExecutor` workers included: runners that start
  test processes put themselves in a kill-on-close job as well, or a killed runner leaves tests (and their games)
  running.
Measured: DOSBox gone 0.0 s after `taskkill /F` of its owner with the job, 0.1 s with the watchdog.

### Retries and flaky tests
After the main pass, retry each failed test up to 3 times, one at a time per test (different tests in parallel).
- A pass on a retry counts, but is printed and recorded as `[FLAKY] name (passed on retry N)` in the run's record,
  so flakes stay visible and get fixed later.
- Stop retrying a test once it fails **identically** twice in a row: same exit code and same failure lines with
  every number replaced by `#` (times, addresses, counts differ between tries). That is a real failure.
- Keep every attempt's log (`name_try1.log` ...).
- Record the failures of each full run, so you can rerun only those; such a rerun counts as a full pass only for
  the same EXE, data files and test code.
- What counts as a failure line: here a line starting with `[FAIL]` **or containing `Error`**, which catches
  tracebacks a test forgot to turn into a failure. The price: a passing check whose name contains "Error" fails the
  suite (gotcha 25).
- Every run gets a private copy of the scenario saves folder (an environment variable points the tests at it),
  removed afterwards, so parallel runs never read each other's half-written saves and never change the tracked
  ones.

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
- When you follow computer-player units across autosaves, match them by identity, never by slot or list position
  (gotcha 27): units get deleted, the list renumbers, new units are appended, and the AI may move or merge the very
  units the test watches. A try where the AI made the case untestable is inconclusive: reload and retry it, don't
  pass or fail it.
- Original vs patched (or several cases) run as parallel processes, not one after another.

### Read the game's state from guest RAM
When a run hangs, the screen alone rarely says why. DOSBox keeps the guest's conventional memory in one private
block of its own process, so a host-side script can read it without touching the game:
- `OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION)`, walk the regions with `VirtualQueryEx`, and find
  the guest RAM block by a signature string from the game's data segment (or by its size); read the first
  1 MB + 64 KB with `ReadProcessMemory`. Read-only: no input, no focus, the game keeps running.
- In DOSBox 0.74-2 (32-bit) guest address 0 is 0x20 bytes into that block (a heap-block header comes first).
  Don't hard-code it: try offsets in steps of 16 and take the one where the BIOS data area's memory size word
  (0040:0013) reads 640 KB and the MCB chain walks.
- The same handle (with write access) can move the BIOS tick count at 0040:006C, the one write worth doing: see
  gotcha 14.
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
- turn the result into a budget with a margin and an automated test that fails when a build exceeds it (here an
  8 KB margin plus the launcher's 4,992 bytes);
- sample from a thread every 0.25 s during the session and save a frame at each new low-water mark and each refused
  allocation, so you see which screen costs most (here a native leader's greeting, which allocates a 49,128-byte buffer).
Two more limits that patches eat silently, both readable from guest RAM:
- **Stack depth.** If the program zero-fills its stack area at start (this game's main does, from the MSC stack-limit
  word up to the initial SP), the lowest non-zero byte above the limit is the deepest the stack has ever been. Report the room left
  and fail under a threshold; a patch that adds a big local buffer or deeper calls shows up at once.
- **Near heap.** Walk the C runtime's near-heap blocks from its descriptor in the data segment (MSC: a header word
  per block, size with the low bit set when free, `FFFE` as the end marker). Since the heap allocates from the
  bottom, the end of the highest used block seen is its high-water mark. If you take part of the heap for your own
  tables, give it a rule (here: the measured peak stays under half of what is left) and test it in the heaviest
  sessions.
- If the patch moves code into upper memory, add the UMB to the same picture: see
  [Upper memory for patched DOS games in DOSBox](upper-memory-for-patched-dos-games-in-dosbox-code-in-a-umb-e.md).

### Silence
`[mixer] nosound=true` silences DOSBox's mixer (Sound Blaster, OPL, PC speaker, CD audio). MIDI bypasses it
(gotcha 4): also set `[midi] mididevice=none`, and keep `mpu401=intelligent` if the game is configured for
MIDI.

### Make rare overlay and memory bugs deterministic
Many DOS games use an overlay manager that swaps code in and out of conventional memory. A stress conf with
`[dos] xms=false ems=false umb=false` makes it swap constantly; a bug that showed up once in 10-20 normal runs
then fails every time (gotcha 3). Run the tests that touch your patched code under both confs.
That conf only works while the game starts without upper memory. When this project moved its new code into a UMB
(DOSBox 0.74 gives one only with `xms=true`), the stress conf was dropped; the overlay rules are now checked by an
emulated test of every call site, and long soak runs (40 turns) look for rare crashes instead. Run the unpatched
EXE with `umb=false` when you compare original and patched (see the upper memory note, gotcha 6).

## Not verified
Only DOSBox 0.74-2 (SDL 1.2) on Windows 11, driving one game. DOSBox Staging and DOSBox-X's SDL2 builds have no
`windib` or `directx` video driver (SDL2's is `windows`), so the input section won't carry over to them as written.
The project ships player confs for Staging 0.83 and DOSBox-X 2026.10 but never ran either (not installed); the
guest-RAM offset (0x20) was measured on the 32-bit 0.74-2 build only. The RAM figures are from one 15.5 GB laptop.

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
    retrying a random event. **Update (2026-10-26): the pause was not enough.** A probe that set the guest clock
    to fixed values at the title screen showed the outcome followed the tick count's low 15 bits at load time, so
    the wall clock gave losing windows of about 11 minutes, and six retries with 0-2 s pauses (under 40 ticks) all
    lost. Now each retry moves the guest's BIOS tick count (0040:006C) forward by a random 1-32768 ticks at the
    title screen, through `WriteProcessMemory` on DOSBox's guest RAM: forward only, so no delay loop waits longer, and
    re-read in case the emulator's own tick overwrote it. The write is refused within an hour of the midnight count
    (0x1800B0; 0.74-2 has no wrap of its own, its `INT8_Handler` only adds 1, so past that int 21h 2Ch would report
    hour 24), and DOSBox starts its clock from the host's local time, so after 22:00 host time the
    harness starts DOSBox with `TZ` set 6 hours behind (2026-10-27: a run at 23:1x replayed the same roll on every
    retry until it ran out of tries).
15. **Saves rebuilt by parallel tests could be read half-written.** (2026-10-24.) **Cause:** several tests
    rebuild the same scenario save before running. **Fix:** skip the write when the bytes are identical, else
    write a temp file and `os.replace` it, retrying while another process has it open. Since 2026-10-30 each run
    also gets a private copy of the saves folder (see "Retries and flaky tests"), and a builder that writes a save in
    stages writes the stages to a per-process file: under `--repeat` a parallel run had loaded a first stage.
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
22. **Under a busy suite, the intro was skipped before the test sent any input.** (2026-10-27.) **Cause:** the
    fast-grab self-check posted Ctrl+F5 to compare with DOSBox's own capture; under load DOSBox's key mapper
    sometimes missed the Ctrl, F5 reached the game as a key, and the intro skips on any key. Any test could get that
    stray key. **Fix:** the keyless block-scaling check (see "Screenshots"); 18 of 18 load-repro runs passed after.
    Trade-off: it no longer compares with DOSBox's capture, so a grab wrong in some other way would pass.
23. **After the test runs were killed for low memory, 10 DOSBoxes (about 670 MB) kept running.** (2026-10-26.)
    **Cause:** the WMI launch (gotcha 21) makes DOSBox a child of the WMI host, not of the test, so nothing ended it.
    **Fix:** job object, watchdog fallback and owner-checked sweep (see "Test DOSBoxes must end with their test").
24. **The PC ran out of memory with two full suites running.** (2026-10-26.) **Cause:** two checkouts each
    started a full suite (2 x 3 games plus their Python test processes); neither the 10-game cap nor the 1 GB
    free-RAM gate stopped it. **Fix:** a machine-wide "one full suite at a time" lock and an
    automatic `-j` that looks at free RAM (see "A machine-wide cap").
25. **A new, passing test failed the suite.** (2026-11-01.) **Cause:** the runner counts any output line containing
    `Error` as a failure, and the names of several passing checks contained "Error" (they tested an assembler's
    error retry). **Fix:** renamed the checks. Either avoid the word in passing output or match failure lines more
    strictly (e.g. `Traceback` and `[FAIL]` only); this project kept the broad rule.
26. **A single test failed in a full suite and passed on a rerun, and the full run had to be redone by hand.**
    (2026-10-25 to 10-28; e.g. one menu test in a 94-test suite.) **Cause:** rare load-dependent flakes (lost
    clicks, late menus) that the screen checks don't catch every time.
    **Fix:** automatic retries, logged as flaky, that stop when a test fails identically twice (see "Retries and
    flaky tests"); fix the flakes the log lists rather than living with them.
27. **A test of a computer player's behaviour failed now and then with an index error, or checked the wrong units.**
    (2026-11-02: passed only on retry in one full suite, an index error in the next.) **Cause:** the test took "the AI's first
    four land units in slot order" as the units it watched. Between autosaves the AI sometimes shipped some of them
    to its colony, where they joined it and stopped being units, and other units (a new soldier, a veteran from the
    New World) took their slots. **Fix:** align the AI's units from one autosave to the next by identity (a monotonic
    matching on profession, then type and map square, allowing for deletions and appended units), and when the AI
    removed the units the case needs, reload the scenario with a shifted guest clock (gotcha 14) and try again, up to
    4 times.
28. **One click in a test was missed now and then under a loaded suite, at a different click each time.**
    (2026-11-03: 1 run in 3 of one test, in a full suite of 358.) **Cause:** a single 100 ms click while 4 DOSBoxes
    shared the machine; the game polls the mouse only in its idle loop and sometimes didn't see the button down.
    Run alone, 20 of 20 even shorter clicks registered. **Fix:** a `click_until` helper: click, wait for the
    expected guest state, and click again (up to 3 times, 3 s each) only while that state is not reached. Use it
    only for idempotent clicks; the end-state check still fails if the result is wrong.
29. **Reference-screenshot tests failed after a feature changed how the map is drawn.** (2026-11-03: a fog of war
    dimmed the ocean behind popups; 3 tests.) **Cause:** the reference shots were taken without the overlay, and
    the differing pixels were outside the dialog being checked but inside the compared area. A fourth test failed
    because its scenario's foreign units now stood out of sight and the fog rightly hid them. **Fix:** a helper
    that turns the overlay off by its key and waits until its state byte in guest RAM reads off (no blind sleep;
    it does nothing on the original EXE), called before the shot; give the scenario a unit next to the ones the
    test must see.
30. **After fixing a few failed tests, the runner refused to finish the full run with only those tests.**
    (2026-11-03.) **Cause:** the run record keeps a hash of the test code; changed tests make the record stale, so
    a rerun of the failed tests can't complete it and the whole suite (90 minutes) must run again. **Fix:** this is
    the right rule (a test fix could hide a regression elsewhere), so gather every test fix from a failed full run
    before starting the next one. Also cap paired variant runs (here an environment variable sets one variant job)
    when rerunning a few tests next to another suite, so the DOSBox count stays in budget.
31. **Integration conflicts in generated files that are committed to git.** (2026-11-04.) **Cause:** two branches
    regenerated the same build output (the patch list, a generated game text file). **Fix:** never hand-merge
    them: take either side and run the generator on the merged tree; check afterwards that the regenerated file
    contains both branches' additions.
32. **A cross-branch omission was caught at build time, not in the game.** (2026-11-05.) Two branches added
    professions and a report page that lists professions; neither knew about the other. The report's generator
    refused any build in which a profession in the game had no line in its table, so the integration build
    stopped with the missing ids. **Fix / pattern:** for every data-driven table that must cover a growing set
    (goods, professions, buildings), add a completeness check to its generator.

22. **A suite entry pointed at a file that didn't exist ("unknown test").** (2026-10-27.) **Cause:** the
    PowerShell test list (CRLF, Windows paths like `tests\f1_test.py`) was edited with sed/printf-style
    tools, which turned `\f` and `\r` in the paths into a form feed and a carriage return. **Fix:** edit
    such files as bytes (Python, `rb`/`wb`), keep CRLF, and check each changed line's repr.
23. **Twice as many DOSBoxes as planned.** (2026-10-27.) **Cause:** each in-game test runs the original and
    the patched EXE in parallel by default, so N agents "each using one DOSBox" used 2N. **Fix:** a
    variant-jobs setting (1 when several agents share the machine), on top of the machine-wide cap.

## Seen in
- Sid Meier's Colonization 3.0 (DOS, GOG release; VICEROY.EXE, an RTLink-overlaid executable) binary-patching
  project (no public game note yet).
- Related: [Driving real games safely](driving-real-games-safely.md) (input and focus rules for any game) and
  [Running several isolated tModLoader test instances in parallel](running-several-isolated-tmodloader-test-instances-in-parall.md)
  (the same sandbox-per-instance idea for Terraria).
