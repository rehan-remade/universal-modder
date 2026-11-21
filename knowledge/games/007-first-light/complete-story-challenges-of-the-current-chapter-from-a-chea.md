---
kind: game
title: Complete story challenges of the current chapter from a Cheat Engine table
game: 007 First Light
games_also: []
game_version: Steam 3768760, Retail\007FirstLight.exe PE timestamp 0x6aeafdda (2026-11-04)
platform: windows
engine: unknown
route: native-hook
tools: [Cheat Engine, Python pefile, Python capstone, Python ctypes]
anti_cheat: none found (no Steam stub or Denuvo-looking sections); challenges are validated by IOI's online service
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-21'
links:
- https://github.com/cheat-engine/cheat-engine
tags: [007-first-light, glacier-2, ioi, challenges, cheat-engine, rpkg, single-player]
---
# Complete story challenges of the current chapter from a Cheat Engine table

> 007 First Light (IO Interactive, Glacier 2) tracks story challenges per chapter through IOI's online service.
> This Cheat Engine table marks the story challenges of the chapter you are playing as completed: it calls the
> game's own "complete this challenge" entity method on a fake entity holding each challenge GUID, so the normal
> request goes out from the game. It only affects your own single-player progression. Verified by the user for
> chapter 1 (challenges show as done in the main-menu list); global/career counters are not affected.

## Setup
- Steam app 3768760, Windows 10 22H2 x64. `Retail\007FirstLight.exe`: 62 MB, PE timestamp 0x6aeafdda,
  image base 0x140000000, **no ASLR** (addresses below are absolute VAs for this build). No other mods installed.
- Cheat Engine 7.x (the table uses Lua `executeCodeEx`).

## Route and why
- Data route (RPKG edits): the packages are RPKG v2 (`2KPR`, Hitman 3 style) and `packagedefinition.txt` /
  `thumbs.dat` are XTEA-encrypted with a key **different from Hitman 3's**, so the usual Glacier 2 tools don't open
  them out of the box. Also, challenge state lives on the server, not in data files.
- Code SDK route (ZHMModSDK-style DLL proxy): possible, but the user preferred a CE table for this game.
- Chosen: call the game's own completion method from CE, so the game builds and signs the request as usual.

## How the game works (what we had to learn)
- Middleware: D3D12 + DirectStorage, PhysX, Wwise, Scaleform UI, DLSS/FSR, Steam API.
- Backend: IOI's `KntSessionService` (`<base>/KntSessionService/<call>`; calls GetChallenges,
  CompleteActiveChallenge, CompleteCachedChallenges, StopSession, GetChallengeMosaic). GetChallenges returns JSON
  (Definition / State / KntDefinition with Tags like `story_<codename>`), which stays readable in process memory.
- `ZKntEventMissionCompleteChallengeEntity` (vtable 0x142f7c688): 0x28-byte objects `{vtable, ptr, ptr, GUID @ +0x18}`,
  one per challenge of the game (217 in a chapter). Its vtable slot 23 (0x142452500) checks a feature flag and
  that the GUID is not null, then calls the CompleteActiveChallenge request builder (0x14245b6e0), which builds the
  body from the session id and the challenge GUID. **It only reads `[rcx+0x18]`**, so a fake object
  `{vt, 0, 0, GUID}` is enough; no entity scan is needed.
- Chapter codenames (story tags): 1 clover "Against the Odds", 2 lotus_advanced_training "A New Home",
  3 rose "All the Time in the World", 4 dahlia "The Past Never Dies", 5 pepper "Uninvited", 6 bluebell
  "Knightfall", 7 magnolia "Time to Die", 8 orchid "Wave of the Future", 9 ivy "For England".
- Other useful vtables: ZKntOnlineChallenges 0x142f76ce0 (sends CompleteCachedChallenges), ChallengeDefinition
  0x142f798a0, ChallengeState 0x142f7bb08.

## Build steps
1. Build a CE table with one script per chapter. Each script holds that chapter's challenge GUIDs and, for each,
   allocates `{vt, 0, 0, GUID}` and runs `executeCodeEx` on 0x142452500 with the fake object, 150 ms apart.
2. Check the function prologue at 0x142452500 first, so the table refuses to run on another build.
3. Optional (table v2): on each tick also AOB-scan memory for the live GetChallenges objects tagged
   `story_<chapter>`, add GUIDs missing from the list and skip ones whose CompletionState is already 2.
4. Load a chapter, open the table, tick that chapter's entry.

## Verification
- Oracle: the in-game challenge list in the main menu after leaving the chapter (user-checked), plus the
  challenge JSON in memory switching to CompletionState 2.
- Test 1: one challenge (CLOVER_09 "Scenic Route") from inside chapter 1 -> completed. Then all of chapter 1.
- Test 2: a chapter-7 challenge sent from the main menu -> NOT completed (see Gotcha 1).
- Not verified: chapters 2 to 9 one by one (same mechanism; ids taken from the live JSON).

## Gotchas
1. **Completion requests from the main menu or another chapter are ignored.** **Cause:** the server only accepts
   challenges of the chapter currently being played. **Fix:** run each chapter's entry while in that chapter.
2. **Global story challenges (counts of smoke, shockwave, bluff... and "completionist") don't complete.**
   **Cause:** they are server-side counters; CompleteActiveChallenge is ignored for them. **Fix:** none; play them.
3. **The main-menu memory holds only part of a chapter's challenges** (pepper: 5 of 30). **Fix:** read the GUIDs
   while inside the chapter (table v2 scans the live JSON objects).
4. **Hitman 3's XTEA key does not decrypt `packagedefinition.txt` / `thumbs.dat`.** Same header and cipher
   structure, new key. Not needed for this mod, so the key was not looked for.

## Assets
None.

## Cost and time
One session (2026-11-12).

## Open questions
- The XTEA key for packagedefinition/thumbs.dat (needed for RPKG data mods).
- Whether later patches keep the same function (the table checks the prologue; the VAs will move).
