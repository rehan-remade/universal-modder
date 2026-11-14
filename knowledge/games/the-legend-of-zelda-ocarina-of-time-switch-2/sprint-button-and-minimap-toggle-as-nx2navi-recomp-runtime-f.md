---
kind: game
title: "Sprint button and minimap toggle as NX2navi recomp runtime features (OoT Switch 2 1.1.1)"
game: "The Legend of Zelda: Ocarina of Time (Switch 2)"
games_also: []
game_version: "1.1.1 (main build id E0F3CCFAF50065AE) via the NX2navi static recompiler 0.9.1 to 0.10.1, Windows"
platform: windows
engine: unknown
route: decomp-recomp
tools: ["NX2navi (static ARM64 to C recompiler + Vulkan runtime)", "capstone", "numpy", "mmh3", "zstandard", "MSYS2 UCRT64 clang"]
anti_cheat: "none (single-player, offline recompiled exe)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["Kendoismebutmaybenot"]
date: 2026-11-14
links: ["https://github.com/tangerineturtle1/NX2navi", "https://github.com/tangerineturtle1/NX2navi/pull/752", "https://github.com/tangerineturtle1/NX2navi/pull/870", "https://gamebanana.com/mods/737688"]
tags: [static-recompilation, switch-2, patch-sets, hud, minimap, sprint, input, eui, ainb, gamedata, murmur3]
---

# Sprint button and minimap toggle as NX2navi recomp runtime features (OoT Switch 2 1.1.1)

> The Switch 2 Ocarina of Time remake runs on PC through NX2navi, a static recompiler (ARM64 to C to x86-64)
> with its own runtime. NX2navi cannot load exlaunch/subsdk code mods, so I rebuilt two quality-of-life mods as
> runtime features that hook the recompiled game through its patch-set mechanism:
> - **Sprint button:** sprint without rolling first, as a toggle or while held. It started as a port of an
>   exlaunch mod and shipped upstream in NX2navi 0.10.0.
> - **Minimap toggle:** D-pad down shows or hides the minimap whatever the In-Game Interface mode does. It
>   gives Pro a minimap, and Normal can go without. Open as PR #870.
>
> The user played both in the real game on Normal and Pro, and each feature also has a stand-in unit test.

## Setup
- **Game:** OoT Switch 2 1.1.1. The exefs `main` is an NSO (LZ4 segments, RELR relocations), and the romfs is a
  NX2navi-packed `romfs.bin` with an `index.json` (path, offset, size).
- **NX2navi:** the launcher keeps each version in `%LOCALAPPDATA%\Programs\NX2navi\app\<ver>`.
  - The `current.txt` and `previous.txt` pointers pick the version, so a downgrade means editing them, plus
    turning off `auto_install` in `data\launcher.json` or the old version re-installs the new one.
  - A kit holds `recomp/` (generator and patch tables), `runtime/` (C/C++ sources), `tools/make_game.py` and a
    bundled MSYS2 UCRT64 clang.
  - Editing `runtime/` invalidates the prebuilt `libnx2navirt.a` digest, so "Rebuild the Game" then compiles the
    whole runtime on the PC (slow).
- **Upstream repo:** `tangerineturtle1/NX2navi`. Its rules: no game data in the repo, comments that don't name
  other projects, credit in PR text only, plain-sentence commits, and `python tools/check_content.py --staged`
  before committing.
- **Analysis:** Python with capstone 5, numpy, mmh3 and zstandard on a decompressed `main` image. Game strings
  are found by scanning the image; pointers are plain image offsets because the binary uses RELR, see Gotchas.

## Route and why
- **Cheats:** NX2navi supports Atmosphere cheat files (`cheats/<first 8 bytes of build id>.txt`), ExeFS
  IPS/pchtxt and built-in **patch sets**. A cheat-code-cave port of the sprint mod worked, but it is limited to
  64 straight-line instructions, with no branches and no pc-relative instructions, and it cannot hide a button
  from the game.
- **Patch sets:** `recomp/patches-v111.txt` lines `set <name> <ENV> <default>` and
  `site <set> main <off> <orig> <repl...>`. The generator lifts both the original and the replacement code at
  each site, and a byte array picks one at run time, so sets switch live (`rt_patch_switch`).
  - A site can append `bl page+0xNNN`, where page = the first 4 KiB page after main (0x7004ea0000 here), and a
    host C function registered with `rt_register_host(RT_PATCH_PAGE + 0xNNN, fn)` runs with full access to the
    guest `Cpu` registers.
  - Host functions can call guest code through `rt_call(c, addr, n, args...)` from the game thread.
- **Input:** `runtime/ov_input.c` `npad_states` (the game's `GetNpadStates`, on the game thread, once per frame)
  is where a feature can read and mask buttons and make `rt_call`s.
- **Why not the others:** memory poking from another thread is unsafe for screen calls, and exlaunch is
  impossible in a recompiler.

## How the game works (what we had to learn)
Addresses are 1.1.1 `main` offsets (base 0x7000000000).

**Link and sprinting**
- Link's actor vtable is `main+0x4b4dfc0`. There is a second, non-controlled instance of the same class.
  - The controlled one is named by the actor manager `[[main+0x4c7e0d0]]` (class `main+0x4bdfe68`) at `+0x470`
    (class `main+0x4b49698`), whose `+0x18` equals Link's `+0x18`.
- **Input flags:** the 64-bit word at `*(Link+0x50)`. Bit 4 (0x10) is the dash input; the game sprints while
  it is set.
  - The movement update `main+0x4aaa80` loads the word at `main+0x4ae798` (`ldr x10,[x10]`).
  - The stance/camera update loads its low byte at `main+0xc07f3c`.
  - ORing bit 4 in after both loads makes the game's own sprint run, with its speed, animation and rules.
- **State id:** `[[[[Link+0x18]+0x270]+0x188]+0x1c0]+0x28`, or `+0x4c` when that reads 0x11a, a wrapper state.
  - Moving states: 1 Walk, 13 Jump, 32 Land, 33 Fall, 68 Clamber.
  - States that keep a sprint: 253 StepOn, 35 Slide, 36 SlideLand.
  - 40 Wait. Anything else ends a sprint.
- **Buttons:** HidNpadButton bits B=1<<1, StickL=1<<4, ZL=1<<8, Down=1<<15. The game's B is the bottom face
  button and puts the weapon away; it is not attack.

**Settings (GameData)**
- Flags are keyed by MurmurHash3 x86_32 (seed 0) of the name.
- `GameData/GameDataList.Product.110.byml.zs` is big-endian BYML, zstd-compressed with the `zs.zsdic`
  dictionary from `Pack/ZsDic.pack.zs`, a SARC. It lists every flag by hash with its type, default and
  SaveFileIndex.
  - Index 1 is `option.sav`.
- Option names use the prefix `OptionData.`, found by brute-forcing hashes. Examples: `OptionData.DisplayMode`
  (enum Normal/Pro/ProMaster, the In-Game Interface option), `OptionData.LockOnType`, `OptionData.IsUseGyro`
  and `OptionData.IsCameraUpDownReverse`. **There is no minimap option.**
- NX2navi's debug tools already read and set flags through the manager `**[main+0x4c7e180]` (`main+0x20d9c0`
  reads, `main+0x682b20` queues a set).

**UI screens (eui)**
- The screen manager is `**[main+0x4c7e098]`. `main+0xb25cd0(mgr, murmur3(name))` returns the screen cast to
  its class, or 0.
- The minimap is **`MapMenu_00`** (hash 0xc3332ad4, class `UIMapMenuScreen`, vtable `main+0x4be8300`) in its
  small form. The pause menu's big map is the *same screen* in its large form.
  - `+0x2350` is the IsMiniMap byte and `+0x2354` is IsDirect, both written by `SeqOneShotOpenMapMenu` before it
    opens the screen.
  - `+0x2359`, `+0x235a` and `+0x235b` are the event "display minimap / small key / boss key" bytes.
- Generic screen fields:
  - `+0x1a5` is the signed pending request: open takes the max, close the min.
  - `+0x1a6` is the state: 0 closed, 1 opening, 2 open, 3 closing.
  - `+0x1a8` is the **drawn** byte: the game's `SeqOneShotSetScreenVisible` only writes it.
  - vtable `+0x28` is open(prio, the game uses 3) and `+0x30` is close(prio, -4). Both only set the request
    byte; the manager acts later.
- **Interface modes:** Normal opens `MapMenu_00` small during gameplay, and Pro and Master never open it.
  - Hiding means clearing `+0x1a8` while `+0x2350==1`, so the screen's state machine still runs.
  - Showing on Pro means writing `+0x2350=1, +0x2354=0` and calling open(3), as `SeqOneShotOpenMapMenu` does.

**Events**
- The event manager is `**[main+0x4c7e090]`. An event (cutscene *or conversation*) is running while its `+0x68`
  is non-zero.
- That is what `SeqQueryIsEventRunning` returns through `main+0xbcc100(mgr, 0)`, which is a plain read for
  argument 0.

**AINB sequence nodes**
- Each node class has a vtable with the name function, the parameter-registration function at name slot +0x48
  (registering names like "IsMiniMap" with their struct offsets) and the execute function at name slot +0xa0.
- Find the name function through the xref to the node-name string, find the vtable by searching for that
  function's address as a qword, then read the slots. Some generic nodes dispatch through a shared exec
  instead.
- The romfs `AI/NodeDefinition` and `Sequence/*.module.ainb` files list which nodes a UI script uses, which is
  enough to see that leaving the pause menu runs `SeqOneShotOpenMapMenu(IsMiniMap)`.
- UI text: `Mals/USen.Product.110.sarc.zs`, then `LayoutMsg/SystemOption_00.msbt`, which gives the option names
  shown to players.

## Build steps
1. **Find the game facts statically:** string xref, then node vtable, then the exec function, then the fields it
   writes (see above). Check every site's original word against `main` with NX2navi's
   `recomp/patches.py` `load` and `check`.
2. **Add a patch set** in `recomp/patches-v111.txt`. Pick a site whose function saved x30 in its prologue,
   because the appended `bl` clobbers x30. Use a free page slot: +0xf00 to +0xff0 were taken, so +0xef0 and
   below.
3. **Write `runtime/<feature>.c`:** a constructor registers the host function, and a per-poll function is
   called from `ov_input.c` `npad_states`.
4. **Hook up settings:** add them to `runtime/cfg.c` (known keys, section, `{key, default, values, LIVE}` row),
   `ui_text.h/.c` and a row in `ui/menu.cpp` `tab_controls`. Only rows the menu draws are shown, but every
   `cfg_value` key needs a cfg row.
5. **Add a stand-in unit test** (`tests/<feature>_check.c` plus a `.py` that writes stand-in `layout.h` and
   `patches.h`) that `#include`s the runtime file and stubs `rt_call`, `cfg` and the patch API.
6. **Install locally:** `git diff vX..HEAD`, then `git apply --exclude=docs/* --exclude=tests/*
   --exclude=tools/build_game.py` into the *current* `app\<ver>` kit, and press Rebuild. The kit compiles every
   `runtime/*.c` itself.

## Verification
- **In game:** the user played on 1.1.1 on Windows.
  - Sprint: toggle and hold on L3 and B.
  - Minimap: Normal hides it, Pro shows it, it stays as chosen through menus, and the pause big map draws.
  - One bug report each led to the fixes in Gotchas 6 to 8.
- **Unit tests:** `tests/sprint_check.py` and `tests/minimap_check.py`, against stand-in Link and screen
  objects. Each in-game bug was first reproduced as a failing test case, then fixed.
- **Patch tables:** checked against the real `main` with the generator's own checker, every NX2navi version.
- **Not verified:** whether `+0x2359` (the event display flag) is meaningful on Pro, the latest
  conversation/event fix (pending a user re-test), and NX2navi versions other than 0.9.1, 0.9.2, 0.10.0 and
  0.10.1.

## Gotchas
1. **A subsdk/exlaunch mod shows "Not Usable".** **Cause:** a static recompiler has no loader for extra code
   modules. **Fix:** rebuild the mod as cheats (limited) or as a runtime feature with patch sets.
2. **Pointer slots in `main` look like small numbers, not addresses.** **Cause:** the NSO uses RELR
   (`DT_RELR`, tag 36), so pointer slots hold image offsets inline and `.rela.dyn` is nearly empty. **Fix:**
   search the image for the plain offset as a qword to find vtables.
3. **Option flags can't be found by name.** **Cause:** names are never stored, only murmur3 hashes, and the
   prefix is `OptionData.`. **Fix:** confirm the hash function on a known enum value (`Normal` = 0x390b012d),
   then brute-force candidates built from words in `main`'s strings.
4. **The appended `bl` broke a function's return.** **Cause:** the replacement `bl page+X` writes x30, so a site
   in a leaf function returning through x30 breaks. **Fix:** put sites after a prologue that saved x30, or in a
   caller.
5. **Refusing or force-closing a UI screen risks hangs.** **Cause:** UI scripts can wait on a screen's open
   state. **Fix:** hide through the screen's drawn byte (`+0x1a8`), never through its state machine.
6. **The pause menu's big map vanished after hiding the minimap.** **Cause:** the code saved the drawn byte
   before writing and "restored" it when the screen turned large. On Pro, or before first draw, that saved value
   was 0. **Fix:** hand the byte back as 1 when the screen is large or the feature is off.
7. **The forced minimap showed during a conversation.** **Cause:** "Link's movement update ran" was the
   gameplay signal, and it keeps running in talks. **Fix:** also require the event manager to be idle
   (`[[main+0x4c7e090]]+0x68 == 0`), and close a minimap you opened when an event starts. On Pro the game never
   closes a screen it didn't open.
8. **The minimap reopened over the pause menu at the moment it opened.** **Cause:** in steady gameplay Link's
   update runs exactly once between pad reads, so the read just after it stops still looked like gameplay.
   **Fix:** count only reads with zero polls since the update, and require about 20 such polls in a row
   (⅓ s) before force-opening.
9. **The feature vanished after an NX2navi update.** **Cause:** each version is its own `app\<ver>` folder,
   and the launcher builds from `current.txt`. **Fix:** re-apply to the current kit, or get it merged upstream.
   The maintainer may merge by hand, so a PR can stay "open" after the feature ships, as #752 did.
10. **Two features wanted the same patch-page slot.** **Cause:** page slots are a shared namespace (water
    ripples took +0xf50 in a later version). **Fix:** grep `RT_PATCH_PAGE + 0x` and the patch tables before
    picking a slot.
11. **The game's own D-pad action also fired on a toggle press.** **Cause:** the button reached the game too.
    **Fix:** latch a press that began in gameplay and mask it from the game until it is released. A press that
    began in a menu stays the game's.

## Assets
None.

## Cost and time
Several sessions over 3 days, including a cheat-cave prototype, a native rewrite and three NX2navi version
moves.

## Open questions
- The meaning of `+0x2359` on Pro, and whether respecting it would be a cleaner event gate.
- A shared "gameplay" signal in NX2navi (sprint and minimap each keep their own Link-update heartbeat).
- The minimap's contents when force-opened on Pro looked right in the user's tests, but they are not checked
  in every area type (indoors, dungeon floors).
