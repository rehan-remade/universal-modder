---
kind: game
title: 'Naruto Storm 4: free-for-all for 4-6 teams with native UI, by controlling the duel''s side/role lookups'
game: 'Naruto Shippuden: Ultimate Ninja Storm 4'
games_also: []
game_version: 'NSUNS4.exe 1.09 (Road to Boruto)'
platform: windows
engine: native
route: native-hook
tools:
- UltimateStormAPI proxy (d3dcompiler_47.dll) with a hot-reloadable plugin DLL
- MinHook
- Ghidra 12 headless (xref export + decompile), capstone, pefile, python minidump
- JPEXS Free Flash Decompiler 26.3 (Scaleform GFx / AS3 edits)
- um win (launch, drive, shot), um backup
anti_cheat: 'none touched: offline Free Battle only, never used in online modes'
status: working
agents:
- Claude Code (claude-fable-5-1)
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-05'
links: []
tags:
- cyberconnect2
- fighting-game
- free-for-all
- call-site-audit
- hot-reload
- game-thread
- scaleform
- native-ui
- memory-arena
---
# Naruto Storm 4: free-for-all for 4-6 teams with native UI, by controlling the duel's side/role lookups

> A plugin turns the Free Battle duel into a free-for-all of 4, 5 or 6 teams (one hero plus up to two supports each; one human, the
> rest COM), started from its own entry in the mode list, with a native multi-participant character select, a native HUD plate per
> fighter, the native lock cursor, and throws / ultimates that play in the world without taking the camera. Route: native hooks loaded
> through a proxy DLL, plus one edited Flash list movie. It runs in the real game: every pass was driven and checked by the agent
> (keyboard automation, log, screenshots it looked at), and the human then played it on a gamepad.

## Setup
Windows 11, game exe 1.09, borderless window. Proxy DLL `d3dcompiler_47.dll` (UltimateStormAPI fork) loads `moddingapi\ff4p.dll`
through a copy, and reloads it when a flag file appears (build -> copy -> flag: 10 s turnaround without restarting the game).
The proxy is a static import of the exe, so its `DllMain` runs before the game's `main()` (used in the fifth pass).
MSVC v143 x64, MinHook. Ghidra 12 headless for xrefs and decompiles; capstone/pefile for scripted disassembly; JPEXS for the Flash UI.
Everything is offline single player. The plugin and the enlarged memory arenas are active for the whole process, so do not take a
modded process into online modes.

## Route and why
The engine is a 2-team duel. Two carriers were considered: the boss "group battle" (rejected: full player-type enemies only work for
boss subclasses, ordinary roster characters crash on a missing vtable slot) and the ordinary duel, where all six characters are
complete objects. In the duel a team member has a role (0 leader, 1-2 supports) and nearly everything is found through
"member of side S with role R" lookups. Two designs are possible: keep unique roles and fake "is leader" (not enumerable: the checks
are virtual calls spread over the player class), or give every fighter role 0 and control the lookups (enumerable: direct calls).
The second one works. A first prototype promoted the sleeping supports in the middle of a running battle and patched every crash as it
came; it proved the idea and was then replaced by "create the fighters as leaders + a static audit of every lookup call site".

## How the game works (what we had to learn)
All addresses are virtual addresses in exe 1.09 (image base 0x140000000, no symbols).

### Engine and data
- In-house CyberConnect2 engine, x64 native. Class names carry a `cc` prefix (ccPlayerMain, ccCollisionManager, ccUiFlash...). The
  exe's strings still hold about 850 engine source file names and about 930 Lua binding names: the cheapest map of the code.
- Data lives in CRI CPK archives that hold XFBIN containers (models, animations, parameter tables, DDS textures, Lua 5.1
  bytecode for story and boss scripts). The archive payloads are encrypted; see the note on porting ASBR characters in this
  folder. This note does not cover unpacking them: what is described here comes from the exe, from files that are loose on
  disk, and from the running game.
- Loose files (this answers the open question of the ASBR note): a request for `data/<path>` is tried as `data_win32/<path>`
  first (the prefix is replaced, not appended; the file path resolver is FUN_140a467b0). Seen working for an XFBIN settings file. Flash `.gfx` files under `data\ui\flash` are read from `data\` itself; their textures (`*_I<n>.xfbin`) come
  straight from the CPK.
- UI is Scaleform GFx with AS3. `ccUiFlash*` classes load a movie, invoke AS3 methods by path, and receive AS3 callbacks through
  ExternalInterface handlers registered with a user-data value.
- Scenes: a table of 465 scene factories and a scene manager that takes requests by id. Free Battle has a root scene with a vector
  of child scene ids (mode list, settings, character select 409, tournament select 449, stage select); a battle runs through
  Begin 403, Main 405, NextRound 406, End 404.
- Memory: fixed TLSF arenas created at the start of `main()`; characters and player objects each have their own arena.
- Threads: game logic runs on its own thread; the loader's per-frame callback runs on another one.

### The duel
- One global duel object (`*0x14161c8c8`) with two teams. A team is a `std::map` of members; the HUD and the support gauge read
  per-member records from the map nodes. The duel also has 32 character slot records (character code, costume), but the engine's
  loops are written as "2 sides x 3": load (FUN_14073f800), create (FUN_14074dfec), teardown by role (FUN_14074e04c).
- A member is created by FUN_14074ddb8(duel, side, role, slot): factory by character code (FUN_1407c5f34), Init, insertion into
  the team, role. A member with a role other than 0 is sent to sleep off the field. A support is the same class with the same full
  resources as a leader; slot and role are independent arguments.
- The player object has a member sub-object (role, team slot), an id, position, target id, side, character code, an "on field"
  flag, a lock-on flag, an "update enabled" flag (freeze / unfreeze are virtuals), hide / show virtuals and a model with a
  visibility flag.
- State machine: 0x145 named states with one handler each. `ChangeState` only queues a request; the player's own update consumes
  it when the object is active and on the field. Consuming a request from outside while the object is frozen crashes.
- Leader switch swaps the roles of the leader and the partner; for a moment two members are mid-swap.

### Lookups (the centre of the mod)
- leader(side) FUN_14085b548, member(side, role) FUN_14085b574, support(side, i) FUN_14085b588, own-side leader FUN_14079b950,
  opponent leader FUN_14079b664 (a player virtual), plus 33 per-member data accessors of the team class. All of them end in
  FUN_14074b36c(team, role), which walks the team map and returns the first member whose role matches. Hooking that choke point and
  returning another member's map node redirects both object lookups and by-role data access.
- The wrappers tail-jump into each other. With nested hooks only the outermost one sees the real engine call site; inner hooks see
  a return address inside the plugin.
- There are about 3700 call sites. The battle setup, the per-member sound slots, the camera mode selection and the teardown all
  enumerate members BY ROLE (0, 1, 2); the direction manager and the ultimate controller put every (side, role 1..2) member away.
- Engine code relies on invariants of the answers ("leader(side) has role 0") and may loop until it gets one.

### Targets and AI
- A fighter's target is a stored id, but state handlers keep resetting it to "leader of the other side", supports copy their
  leader's target, and there is no "nearest opponent" logic anywhere.
- The COM object (leader AI class) does not read the stored id: it asks the opponent-leader virtual. Retargeting therefore needs a
  hook of that virtual, not a write to the field. The AI writes a virtual pad that is copied into the player's pad every frame.
- A leader AI calls its supports by itself (actions 0x19 / 0x1a) when a support exists and the gauge is full.
- Object ids are running numbers, not 0..5.

### Collisions
- A collision manager (`*0x1416bda48`) holds all volumes. Each has an owner, a type, a four-dword group mask and a four-dword
  target mask; a pair is processed when one's group meets the other's target, and the hit record is delivered to the victim's box.
- The player's boxes use fixed per-side bits in the first dword (hurt boxes, attack boxes, push boxes), which is why team mates
  cannot hit each other. A free-for-all adds one bit per team in an unused dword: group gets the own bit, target gets everyone else's.
  The owner of an attack box is a sub-object of the player, not the player.
- Jutsu volumes are separate objects owned by a skill object. They do not hit the hurt boxes but a second box type of the fighter,
  and the skill's hit callback (FUN_140547864) marks fighters of its own side as "already hit" before the real test.

### Jutsu objects, throws, ultimates, camera
- A skill object stores its owner as (side, role, slot, id) and resolves it by side and role, so with several role-0 members it
  finds the first one; an instance limiter retires the oldest object of the same side.
- Throws and grabs are "direction" attacks: the hit is processed at the victim, the attacker is looked up by the (side, role) stored
  in the hit record, and the pair enters matching attacker / victim states. A wrong attacker leaves the victim waiting forever.
- An ultimate creates a demo direction (create FUN_1407dc1f4, controller FUN_14076bc08, release FUN_1407dc784). The controller
  freezes and hides "the leader of the victim's side" and later shows "the victim": the same object in a duel, two different
  fighters in a free-for-all. Most of the damage is applied by animation events of the cinematic, not by the triggering hit.
- A "cinematic" is the duel camera in another operator mode (mode select FUN_140740de4), not a scene; the world stop around it is
  gated by "a direction is running" predicates (FUN_14076c79c, FUN_14076c770). The duel camera frames leader(0) and leader(1); a
  close-up camera (start FUN_1404b07b8) takes a side leader whose flag is set and otherwise keeps a null or stale subject.

### Battle end
- The duel has a result field (0 running, 1 time over, 2 / 3 a side won) that the Free Battle root scene polls. A per-frame judge
  (FUN_14074d248) compares the leaders of the two sides, so the battle goes on while the lookup answers a living fighter.

## Build steps
1. Hook player creation: for the side that becomes "all fighters", swap the member's settings sub-block into the role-0 slot and
   create it with role 0.
2. Hook the choke point; answer by policy: site class from a generated table (ITER = member enumeration -> fighter number `role`;
   SUPPORT = null; ATTACKER = resolve by the engine id stored in the hit record; JUDGE = first living fighter), then by context
   (inside a fighter's own update: my side -> me, other side -> my target; camera -> the human's target; else a primary fighter).
3. Build the table: Ghidra xrefs of every lookup (+ a byte scan for `jmp` thunks), argument features by scripted disassembly,
   a live census from the choke-point hook (which sites run, with which arguments, in which context), then a code review of the
   role-variable sites (325 of 3700).
4. Per-battle glue: park the extra fighters during the two-leader intro, force one round, target table + nearest-target choice,
   collision group/target bits per fighter so that team mates can hit each other.
5. Run every tick and command on the game thread (from a per-frame engine hook), never from the host's update thread.

## Verification
The agent launched the game, drove the menus with scan-code key presses (confirming each step against the plugin log), and ran
seven FFA battles in one process: mode start at creation, all bots active for a whole battle (hit matrix and AI-pad activity in the
log), throws and ultimates between team mates, deaths without battle end, win when the last COM fighter dies, loss when the human
dies, time over, five "repeat battle" restarts, hot reload mid-battle, and a vanilla battle afterwards. A second pass added scripted keyboard input for the human (combo, jutsu, throw start, support calls, ultimate), a 4-panel HUD, spectating
until one team is left, single battles and duplicate characters. After the later passes (native UI, six fighters, enlarged arenas) the human played the mode on a physical gamepad and found three problems (crash on leader switch, camera leaving on other fighters' ultimates, blank support icons); the fixes of the sixth pass were re-run by automation only. Not verified: the leader switch by the physical stick after the fix, a second human, more than one round, sessions longer than about ten battles in one process, languages other than Russian for the new list entry.

## Gotchas
1. **Random crashes and frozen fighters that moved around with every change.** Cause: the plugin's tick ran on the host's update
   thread while the game logic ran on another thread; every engine call from the tick raced the game. Found with a hardware write
   watch (DR0 via SetThreadContext) that never fired for a field the engine demonstrably wrote. Fix: run ticks from an engine
   per-frame hook; print both thread ids in the diagnostics.
2. **Everything indexed by player id silently stopped working after a restart.** Cause: the id is a running object id. Fix: use a
   stable index (side * 3 + team slot) and convert at the engine boundary.
3. **Crash on "restart battle" after a modded battle.** Cause: teardown destroys members by role; extra role-0 members leaked and
   stayed in the team map. Fix: the teardown call sites are enumeration sites in the table, and the policy keeps answering them while
   the members are being destroyed.
4. **A throw started on the wrong fighter and the world stayed paused.** Cause: nested lookup hooks reported a call site inside the
   plugin, so the "attacker by id" rule did not apply. Fix: the outermost hook records the site, inner ones leave it.
5. **Null dereference in demo sound code during the first ultimate of an extra fighter.** Cause: per-member sound slots are assigned
   by (side, role) at battle setup; roles 1/2 returned null. Fix: mark the setup site as enumeration.
6. **Fighters vanished and went passive after a cinematic** (earlier prototype). Cause: "put the supports away" loops were answered
   with real fighters. Fix: support-semantics sites get null; only reviewed enumeration sites get fighters.
7. **Virtual call on a freed player at restart.** Cause: cached pointers used by the logger after destruction. Fix: hook the player
   destructor and drop every cached pointer until the next creation.
8. **Blind menu automation entered the wrong mode.** Cause: key presses sent before the title was ready. Fix: wait for a log line
   per step, take a screenshot before the one irreversible confirm; back the save folder up first and diff it afterwards.
9. **A value-preserving "skip the cinematic" hook removed most of the ultimate's damage.** Cause: the damage lives in the
   cinematic's animation events. Fix: apply a replacement amount through the engine's damage function one tick later.
10. **A custom HUD drawn with the loader's ImGui landed off-screen.** Cause: ImGui's DisplaySize was the window size while the game's back buffer was smaller and stretched. Fix: lay out in swap-chain (back buffer) pixels. Passing a plain command list (rects/text, normalized coordinates) from the hot-reloadable plugin to the proxy keeps HUD iteration at one reload.
11. **Loading screen hung after changing a team member's character in the battle settings.** Cause: the character select had already preloaded that slot and the battle loader skips loaded slots. Fix: only fill slots that are still empty (single battles); the same character several times loads fine.
12. **"Human died" ended the match although bots were still fighting.** Fix: do not call the per-frame round judge while the human is dead and two or more bot heroes live; answer the camera's two leader lookups with a living fighter and its target.

## Native UI pass (2026-10-04): mode list entry, 4-entrant select, 4 native plates, lock cursor, bot supports
All of this was run in the game (keyboard-driven automation, screenshots); a physical pad was not used.

- **Flash (Scaleform GFx, AS3) is editable with JPEXS**: `ffdec-cli -export script`, `-replace <in.gfx> <out.gfx> <class> <file.as>` (recompiles one class), `-swf2xml` / `-xml2swf` for timeline edits. The GFX signature survives. Loose `.gfx` files in `data\ui\flash\OTHER\...` are read from disk (replace in place, keep originals); `data_win32` is NOT consulted for them. Flash textures (`*_I<n>.xfbin`, one DDS inside) are read straight from the CPK by `ccUiFlashXfbinParser` (FUN_1409a9d28 load, FUN_1409aa010 parse): hook the parse and swap the buffer to override one.
- **New entry in a Flash-driven list**: the list logic lives in AS3 (`script.freebtl_top.all_nut`), the scene mapping in a C++ table. Rewrite the AS3 with an order array, give the new entry an id past the table and translate it in the list's ExternalInterface callback (FUN_14069efbc) to an existing id + a plugin flag. Captions are frames of a per-language sprite; a new caption can be composed from the game's own glyphs (connected components of the atlas) and written into a free area of the same DXT5 texture.
- **Multi-entrant select for free**: the tournament character select scene (449) runs one picker N times with a player badge and an entrant list; it only depends on the shared select UI, `BattleSelectParam` and two tournament-manager fields. Swapping the child scene id in the VS root's child vector (409 -> 449) and composing the two side blocks in its DecideEnd (FUN_14071d8ac) gives a native 4-participant select inside the normal VS flow. `BattleSelectParam+0x424`: 1 = team, 2 = single.
- **More HUD plates without asset edits**: a second instance of the HUD movie under another name (`ccUiFlash::LoadMovie` FUN_14060759c) + the engine's own AS3 invokes (FUN_140607ba0) driven from a hook of the gauge update; register the AS3->C++ callbacks with your own user-data values and answer them in a hook of the handler. `SetMember` through the GFx ObjectInterface (vt+0x28) reaches `x`, `y`, `scaleX`, `scaleY`, `alpha`, `visible` of AS3 display objects, so whole movies can be scaled and moved. If a target function is already inline-hooked by the loader, hook the vtable slot instead.
- **Native lock cursor**: class `TargetCursor` (ctor FUN_140463c58, init FUN_140463e10) with movie `duel_boss2/duel_lock.swf`; request the movie through the Scaleform manager (FUN_1409a7d18), create the object with the game allocator, feed the lock point (FUN_14079a404) every frame, hide when FUN_14086717c says off screen.
- **Extra team members as native supports**: SlotLoad (FUN_14074f4ac) + FUN_14074ffc8 into slot records 6+, original creator FUN_14074ddb8(duel, side, role 1/2, slot), then vt+0xaf0 / vt+0x1340, own teardown (vt+0xae0, FUN_14074ae5c, registry delete). Answer "support i" only at the call sites of the support call / AI / put-away functions with "support i of the acting hero". The COM AI then calls them without further work. Block the "special action" branch of FUN_1407e1c20 (+0x156a0) or the COM swaps leader with the support.
- **Hard limit found**: engine heaps are fixed TLSF arenas (vector at 0x1416b6338, objects with vt 0x1411100b8, arena base at +0x18, free bytes at base+0x20). Characters live in a 270 MB arena; six characters + stage leave 56..108 MB, a character costs 1..26 MB. Loading many extra characters in parallel or ten extra in total ends in a null allocation. Load extras sequentially, watch the free counter, release your slots when unused (the engine releases slots 6+ only on some exits).

### Failures of this pass
13. **Crash at the first COM PlayerInit, looked random.** Cause: an old logging hook on a tiny function that begins with a loop header (FUN_1407f1054); every call through the trampoline crashed, but the function is only called for a few characters. Fix: do not hook it. Lesson: grep the log for one successful call of every logging hook.
14. **Loading eleven different characters crashed in the animation reader.** Cause: fixed arenas (above). Fix: sequential load + budget.
15. **Memory "leak" across battles.** Cause: a support slot whose support was skipped kept the previous battle's character. Fix: track own slots and release them.
16. **COM hero swapped places with its support.** Cause: the support-call function has a leader-change branch. Fix: clear the action type for the call.
17. **Own supports hit their hero.** Cause: per-fighter collision bits; supports had their own bit. Fix: team bit.
18. **Hot reload on the select screen lost a plugin flag and the vanilla code path ran with half-set data.** Fix: derive "our flow" from game state (the child vector), keep flags in process environment variables.
19. **Menu automation walked into other modes.** Cause: 200 ms key holds repeat on list cursors. Fix: 80 ms holds for arrows and a screenshot check before every confirm that leaves a menu.

## Fourth pass (2026-10-04): cinematics without the camera, more plates, six fighters
- **A "cinematic" in this engine is the duel camera in another operator mode, not a scene.** The mode select (FUN_140740de4) polls a per-player predicate (FUN_140783950: "my animation carries a camera track"); answering 0 for the running pair keeps the normal camera while the whole ultimate sequence still plays. Everything else that makes the world stop is gated by two "a direction is running" predicates (FUN_14076c79c(type), FUN_14076c770()); answer 0 to every caller except the pair, the direction manager and the ultimate code. The camera and HUD also ask them - excluding only "other fighters" froze the camera.
- **Throws** are direction type 3 started by one call (FUN_14076ba88(side, 3)); skipping that call leaves the two fighters playing the throw in place.
- **Reusing a UI clip for more owners**: a second / third instance of the support icon movie inside the engine's own UI object, initialised with our member count and our callbacks, gives native support icons for fighters the engine does not know as "leaders".
- **A select UI that fixes its form at creation** can be re-created mid-flow with the scene's own create sequence; do it a few frames after the triggering input.
- **More than three members on a side**: the engine's creator accepts any slot record; members beyond the by-role loops need update-task registration, CPU creation and teardown by hand, and every plugin table sized "2 x 3" must grow.

## Fifth pass (2026-10-04): the "hard" memory limit was two immediates
- The fixed arenas are created at the start of `main()` with sizes as 32-bit immediates in the exe. A proxy DLL that is a static import runs its `DllMain` before `main()`, so patching the immediates there (byte-checked) enlarges the arenas for the whole process; a plugin loaded from a bootstrap thread is too late. Character arena 270 -> 768 MB and player-object arena 27 -> 96 MB made 18 full characters in one battle stable (five battles in a row, about 430 MB still free). The engine's own 760 MB arena was the evidence that the allocator copes with that size.
- Lesson: before designing around a memory budget, find where the budget is set.

## Sixth pass (2026-10-04): a stack overflow from a lookup answer, and a blank icon clip
- When a hook answers engine lookups, keep the engine's invariants: here "leader(side) has role 0". Engine code recursed on that lookup until it found a role-0 member; an answer that was right a frame earlier (attacker by stored id) became a non-leader after a leader switch and the recursion never ended. Enforce the invariant at the single choke point, and add a stack-depth guard there (a call counter gives false alarms: some states poll a lookup thousands of times per frame).
- A stack overflow leaves no room for a vectored handler: reserve it with SetThreadStackGuarantee on the game thread. In the dump, the repeated return address with a fixed frame size is the recursing function; the top frames are only where the stack ran out.
- Scaleform icon clips may attach all loaders on COMPLETE of the last one: one wrong file name blanks the whole clip, which looks like a random loading problem. Check requested names against the archive listing.

## Assets
No generated art. The Russian and English captions of the new mode-list entry are composed from the game's own glyphs and stay on
the machine as a local override; nothing from the game is shipped.

## Cost and time
About ten agent sessions over four days. The first three went into the mid-battle prototype; the rebuild (audit, thread fix,
automated testing) took one long session; native UI, bot supports, six fighters and the memory work took one session each.

## Open questions
- About once per battle the victim of a throw or ultimate stays in its victim state after the attacker has finished; a watchdog
  releases it after 2.5 s. The cause is not found. The watchdog decides "the attacker is gone" from the victim's current target,
  which in a free-for-all is not always the attacker, so its timeout cannot simply be shortened.
- A second human (the tournament select binds pad 1 for every pick), battles with more than one round, the new list entry in
  languages other than Russian and English.
- COM heroes never switch leader and have no team ultimates. Six plates in one row are small at 1440p.
- Several supports share one engine sound slot; voices were not checked by ear.
