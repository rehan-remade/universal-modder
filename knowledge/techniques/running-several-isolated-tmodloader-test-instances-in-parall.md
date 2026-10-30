---
kind: technique
title: "Running several isolated tModLoader test instances in parallel, and never touching the player's own"
status: in-progress
agents: ["Claude Code and agents"]
humans: ["DarkameMaster"]
date: 2026-10-10
links:
  - https://github.com/tModLoader/tModLoader
tags: [tmodloader, terraria, lab, parallel, process-classification, safety, automation, windows, harness]
---

# Running several isolated tModLoader test instances in parallel, and never touching the player's own

> An automated test lab for a tModLoader mod has to run while the person who owns the PC keeps playing their own
> modded Terraria. This note covers the part that is easy to get dangerously wrong: telling the lab's processes
> apart from the player's, closing only the lab's, and starting a second, third, ... lab in parallel. tModLoader
> keeps its log folder and its Steam detection relative to the working directory, so each extra lab runs from its
> own copy of the install with its own `-tmlsavedirectory`. The classifier is verified with about 190 synthetic
> cases; **a second lab has not yet been launched in the real game.**

## When to use it
- You test a tModLoader mod by launching the real game from scripts, on a machine where a human also plays.
- You want two or more test instances at once (parallel scenarios, or filming one while another runs a suite).
- You give agents permission to close processes. That permission must be narrow enough that a bug in a script
  cannot kill the player's game.
- Not needed on a dedicated test machine, where "kill every tModLoader" is fine.

## Setup (where this was built)
Terraria 1.4.4.9 on tModLoader 2026.08.3.0 (Steam, Windows 11 x64, .NET 8). Scripts in Git Bash driving
PowerShell 5.1 for the process queries. `<lab root>` below is any folder you own.

## How

### 1. Why a second lab needs its own copy of the install
Read from tModLoader's assemblies (source inspection of the IL, nothing executed) and from a real `client.log`:
- The log folder is the relative name `tModLoader-Logs`, assigned once in a static constructor, and no option moves
  it. Nothing in the assembly changes the working directory; the log prints the working directory it starts in.
- The native-library folder is built from the working directory.
- Platform and Steam detection depend on it too: the `-steam` flag, or a working directory that sits under a
  `steamapps` folder (as the real log says), plus a `steam_appid.txt` in the working directory.
- Two instances started from the same folder therefore share the log folder (the second one writes
  `client2.log`). A launcher that moves `client.log` aside and then waits for "entered the world" in it can accept
  **another instance's** entry as its own.

So lab 1 uses the Steam install as before, and every lab N from 2 up runs from **its own copy of the install**
(271 MB here, nothing downloaded), placed under a path that still contains `steamapps\common\tModLoader`:

| | lab 1 | lab N (2..999) |
|---|---|---|
| saves (`-tmlsavedirectory`) | `<lab root>\tmlsave` | `<lab root>\labs\N\tmlsave` (a copy of the player, world, `config.json`, input profiles, enabled-mods list, mod configs) |
| working directory | the Steam install | `<lab root>\labs\N\steamapps\common\tModLoader` |
| `client.log` | in the Steam install | in that copy |
| engine DLL, if the mod loads one | the one in its config | `<lab root>\labs\N\...`, set in that lab's own config, so swapping it never touches lab 1 |
| class reported by the classifier | `LAB` | `LAB<N>` |

Steam itself is shared: the copy uses the same `steam_appid.txt` and the player's Steam client, and ownership is
still checked by Steam. Nothing is bypassed.

### 2. A registry of labs, accepted only in its exact canonical form
A tab-separated file lists `N`, the save folder and the install folder. A line is accepted only if both paths are
**exactly** the canonical ones for that N (N between 2 and 999 with no leading zero, case-sensitive, no extra
fields, no trailing space). It cannot name the player's folder, another lab's folder, or redefine lab 1. Anything
else is ignored with a warning, and the PowerShell side validates every entry a second time. Environment
variables cannot extend it: the script reassigns them before use. Lab 1 does not depend on the registry.

### 3. The classifier: one function, built on the command line's argv, not on text
Every launch, close and watch uses the same function. For each `dotnet.exe` process (by image name, never by
window title) it splits the command line with `CommandLineToArgvW` and decides:
- **Not a tModLoader**: the first `.dll` after `argv[0]` is not `tModLoader.dll` (MSBuild, the compiler server,
  another tool that merely receives the name as an argument). Ignored.
- **BUILD**: has a `-build` key (a mod being packed). Launching aborts.
- **LAB / LAB<N>**: only if everything holds: the exact shape `dotnet tModLoader.dll ...` with no host options;
  exactly one `-tmlsavedirectory`, spelled exactly like that, and no `-savedirectory`; its value is an absolute
  drive path with no spaces and no trailing dot; the line contains no `""` or `\"` (where two parsers might
  disagree); and `GetFullPath(value)` without its trailing separator equals, case-insensitively, the lab's
  canonical folder. Arguments are grouped the way tModLoader's own parser groups them (a key starts with `-` or
  `+`, its value is the following tokens joined by spaces), so an unquoted path with spaces is read as the game
  would read it.
- **USER**: any other tModLoader, and any `dotnet.exe` whose command line is empty or unreadable (what a
  non-elevated process sees when the player's game runs elevated). Fail closed.

A launch **aborts** when it sees USER or BUILD. It never waits, never kills.

### 4. Closing a lab without races
To close lab N, the script opens a handle to the exact PID (`SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION`),
which stops Windows from handing that PID to another process while the checks run. Just before the kill it checks
that (a) the start time from CIM equals the start time the launcher announced, (b) the start time from the handle
differs from CIM's by at most a second, (c) the process re-classifies as **exactly this lab's class**, and (d) it
is still a tModLoader command line. Only then does it kill that PID and wait on the handle. Lab 2's script
refuses (a distinct exit code) a PID that classifies as lab 3, and lists other labs' processes as "another lab,
not touched". The test run's own wrapper closes the instance it launched from an exit trap, so a failed or
interrupted run still cleans up.

### 5. Creating a lab
One idempotent script: backs up lab 1's saves (read-only) and the new lab's, copies the install without its log
folder, copies the saves, writes the registry line through a temporary file and `mv`, warns when the copy's
`tModLoader.dll` differs from the Steam one (refresh after a tModLoader update), and refuses to touch a lab that
is open. The packed `.tmod` is shared by all labs; only the launch line differs.

## Verification
| Claim | Evidence level | Result |
|---|---|---|
| The classifier never calls the player's tModLoader a lab, and lab N only closes lab N | **Synthetic**: fake process objects with real command-line strings; an independent verifier agent | the author's 31 + 11 cases, then an independent adversarial campaign of about 190 cases in all: 0 counterexamples |
| The kill path | Synthetic: the real kill body with the kill switched off and the class function replaced by a fake | with classes {LAB, LAB2, LAB3} against the lab being closed {LAB, LAB2, LAB3}, only the diagonal passes; USER and BUILD always refused |
| Negative control | The old script run on the same cases | it fails exactly the 7 lab-N cases (it calls them USER, which would abort: safe) and no others |
| tModLoader's CWD behaviour | Source inspection + one real log | as described above |

Case families the verifier tried (all USER or ignored, never LAB): look-alike folders (`labs\20`, `labs\02`,
`labs\1000`, `tmlsave2`, a parent or child folder), the same folder spelled another way (`..`, double slashes,
upper case), trailing separators and spaces, 8.3 names, `\\?\` and UNC forms, NTFS stream names, wildcards,
environment-variable syntax, upper-case keys, a duplicated `-tmlsavedirectory`, a value hidden inside another
option's value, host-option variants, look-alike image names, invisible and full-width characters. A path that
resolves to the lab's folder by another spelling is correctly the lab.

**Known gaps (all fail closed):** a command line with a leading space parses to an empty `argv[0]` and is ignored
rather than called USER, so the abort would not fire for it (Windows does not produce this from Steam, a `.bat`
or a shell); an empty `LAB_ID` means lab 1; a registry file whose last line has no newline silently drops that
line.

**Not verified:**
- **No lab N >= 2 has been launched in the real game.** Whether Steam lets two processes of the same app run side
  by side is an open risk that only a real run can answer.
- The kill branch was exercised only with the kill disabled, and no tModLoader was running during the
  verification.
- Junctions or symlinks inside a lab folder (the comparison is textual).
- Load: two Terrarias plus other jobs can push a mod's own per-step time guard over its limit (see Gotcha 4).

## Gotchas
1. **A regex over the command line text called the wrong thing a lab.** **Symptom:** an independent
   verifier showed that a folder named like the lab's with " - Copy" appended (the name Explorer gives a copy)
   would have been classified as the lab, so a real run would have killed the player's tModLoader. The same text
   match also fired on a DLL that merely received `tModLoader.dll` as an argument, on a `-tmlsavedirectory` inside
   another option's value, and it missed `dotnet exec tModLoader.dll`. **Cause:** matching text instead of
   arguments. **Fix:** the argv-based classifier above; any doubt means USER.
2. **Two instances in one folder watched each other's log.** **Cause:** the log folder is relative to the working
   directory (see How, 1). **Fix:** one install copy per lab.
3. **A relative path given to the game through an environment variable resolved against the game's folder.**
   **Symptom:** all 27 scenarios of an unattended run (about 40 minutes) failed with the same
   `DirectoryNotFoundException`; no scenario was ever loaded. **Cause:** the launcher script passed the scenario
   file as `cygpath -w` of a relative path, which only flips the slashes; the game process starts in tModLoader's
   install folder, not in the script's. **Fix:** make every path handed to the game absolute (`cygpath -aw`) and
   check that the file exists in the launcher before starting the game. The re-run loaded the scenarios and ran
   their steps.
4. **Load can look like a mod bug.** **Cause:** two Terrarias and several agents can exceed a per-step time budget
   inside the mod (here, an engine step over 16.7 ms switches the engine off). **Fix:** when a failure says
   "step out of budget" while another lab runs, repeat it with a single lab before believing it; a replay mode that
   must not be switched off can ignore the budget, ordinary play and tests cannot.
5. **Steam's helper process looks like a second player.** tModLoader starts a helper
   (`dotnet tModLoader.dll -terrariasteamclient`, no `-tmlsavedirectory`) that classifies as USER while it lives, so
   a lab launching exactly while another one starts aborts. **Fix:** this is by design (safe); retry. (Read from
   the design; not seen in a live run.)

## Seen in
- [Super Smash Bros. Melee's engine inside Terraria](../games/terraria/super-smash-bros-melee-s-decompiled-engine-inside-terraria-a.md)
- Related: `driving-real-games-safely.md` (the general safety rules this narrows down for tModLoader),
  `oracles-how-agents-know-a-mod-works.md`.

## Credits
- [tModLoader](https://github.com/tModLoader/tModLoader), whose assemblies were read to find the working-directory
  dependencies.
- Built with AI agents: Claude Code and its agents implemented the multi-lab support; a different agent, Claude
  Code, verified the classifier. Human direction: DarkameMaster.
