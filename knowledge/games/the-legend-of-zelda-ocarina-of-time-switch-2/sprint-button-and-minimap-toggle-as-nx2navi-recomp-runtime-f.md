---
kind: game
title: "Sprint button, minimap toggle, mouse-style gyro aim and DualSense HD rumble as NX2navi runtime features (OoT Switch 2 1.1.1)"
game: "The Legend of Zelda: Ocarina of Time (Switch 2)"
games_also: []
game_version: "1.1.1 (main build id E0F3CCFAF50065AE) via the NX2navi static recompiler 0.9.1 to 0.10.1, Windows"
platform: windows
engine: unknown
route: decomp-recomp
tools: ["NX2navi (static ARM64 to C recompiler + Vulkan runtime)", "capstone", "numpy", "mmh3", "zstandard", "MSYS2 UCRT64 clang", "SDL3 (audio + gamepad sensors)"]
anti_cheat: "none (single-player, offline recompiled exe)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["Kendoismebutmaybenot"]
date: 2026-11-14
links: ["https://github.com/tangerineturtle1/NX2navi", "https://github.com/tangerineturtle1/NX2navi/pull/752", "https://github.com/tangerineturtle1/NX2navi/pull/870", "https://github.com/tangerineturtle1/NX2navi/pull/887", "https://github.com/tangerineturtle1/NX2navi/pull/892", "https://gamebanana.com/mods/737688", "https://github.com/trzz1214/RenHDrum"]
tags: [static-recompilation, switch-2, patch-sets, hud, minimap, sprint, input, eui, ainb, gamedata, murmur3, gyro, player-space, haptics, dualsense, memory-snapshot]
---

# Sprint button, minimap toggle, mouse-style gyro aim and DualSense HD rumble as NX2navi runtime features (OoT Switch 2 1.1.1)

> The Switch 2 Ocarina of Time remake runs on PC through NX2navi, a static recompiler (ARM64 to C to x86-64)
> with its own runtime. NX2navi cannot load exlaunch/subsdk code mods, so I rebuilt two quality-of-life mods as
> runtime features that hook the recompiled game through its patch-set mechanism:
> - **Sprint button:** sprint without rolling first, as a toggle or while held. It started as a port of an
>   exlaunch mod and shipped upstream in NX2navi 0.10.0.
> - **Minimap toggle:** D-pad down shows or hides the minimap whatever the In-Game Interface mode does. It
>   gives Pro a minimap, and Normal can go without. Open as PR #870.
> - **L3 in conversations:** the sprint button no longer swallows L3 while the game uses it to hide the text box
>   (PR #887).
> - **Player-space gyro (mouse-style):** the gamepad gyro turns the camera, and the hookshot aim, through the
>   runtime's direct-mouse path, following JoyShockMapper's PLAYER_TURN maths. It has no dead zone or smoothing,
>   unlike the game's own gyro aiming. It can run always or only while the game aims, and has separate horizontal
>   and vertical sensitivity. Local branch, not yet a PR.
> - **DualSense HD rumble:** the game's two-band HD vibration is played on a USB DualSense's voice-coil actuators
>   as audio on its 3rd and 4th channels (PR #892).
>
> The user played every feature in the real game, and each also has a stand-in unit test.

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

**Camera input, aiming and gyro**
- **Camera input update:** `main+0x37c300`, with x20 = the camera input object and the flags in w21 (bit 0 camera
  input off, bits 1/2 invert X/Y). NX2navi's direct mouse hooks it at `main+0x37c45c` (`str s1,[x20,#0x538]`),
  after the stick's dead zone, clamp and exponent.
  - The processed stick is at `+0x538` (x) and `+0x53c` (y). `+0x5e0` is the camera-reset timer (R3).
  - Nothing after that point curves or clamps it. One unit sideways turns the camera about 1.78° per 60 Hz frame,
    scaled by the game's own sensitivity option.
- **Aim flag:** the settings word at camera input object `+0x218`. Measured from a per-frame recording:
  - **bit 32** is set exactly while ZR holds the hookshot aim, and while the chain flies;
  - **bit 30** is set only for the moment of a shot (Link state 5 HookshotShoot);
  - **bit 47** is lock-on.
  - Link's state id stays 40 (Wait) or 1 (Walk) while aiming, so the state id can't detect aiming. The hookshot
    aim is an upper-body layer.
- **Hookshot aim input:** while bit 32 is set, the same processed stick (`+0x538`/`+0x53c`) turns Link and the
  aim, one frame later. It's linear, about 110°/s per unit (1.83° per frame), so anything added there in degrees
  reaches the aim 1:1.
  - The raw right stick's turn rate follows a squared curve (about 17°/s at 38% deflection, 30°/s at 52%,
    113°/s at full), applied before `+0x538`.
  - Link's facing lives as a rotation matrix in the actor (`actor+0x328..`, about 3×4). `link+0x102c` (and
    `+0x18c4`) is a radians copy that an animation update rebuilds with `atan2` from the matrix each frame
    (`main+0xc03618` to `0xc03678`). Writing it does nothing.
- **The game's own gyro:** `GetSixAxisSensorStates` is called at `main+0x346970c` into device `+0x298`. Players
  feel it as gyro converted to a stick: a dead zone, smoothing and the stick curve.
- **Red herring:** the string `PlayerHookshotAimStick` is passed to `main+0xa44760` together with the actor,
  strength 1.0 and duration −1. It's a vibration request (the aim rumble), not an input mode.

**Vibration**
- On 1.1.1 the game sends HD-rumble values tuned for the Switch 2's actuators
  (`IsOunceVibrationDeviceMounted` returns true). Most amplitudes are under 0.05, so a plain amp → motor map feels
  weak, and they need the Switch 2 lift curve first.

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
   - Once the kit holds several of your features, merge each new commit three ways with `git merge-file`
     (base = the parent commit, ours = the kit file, theirs = the commit), after normalising the kit's BOM and
     CRLF. Fix real conflicts by hand: `cfg.c`'s long key lists conflict every time.
   - The launcher only rebuilds on a fresh launch, so the player must close the game fully and relaunch. Check
     the exe's timestamp before reading a test log.
7. **Player-space gyro:**
   - The sensor thread (`input.c` `motion_main`, 250 Hz) feeds each sample with the Mahony fusion's up vector.
   - Yaw is computed in player space: `worldYaw = up·(0, gy, gz)`, then `sign(worldYaw) * min(|worldYaw| * 2,
     hypot(gy, gz))`, with pitch = gx. These are JoyShockMapper's PLAYER_TURN defaults: relax 2.0, no cutoff, no
     smoothing. GamepadMotionHelpers' own helper defaults to 1.41.
   - The degrees accumulate under a mutex. Each camera update takes them, multiplies by the horizontal and
     vertical sensitivities and adds them to `+0x538`/`+0x53c` divided by (frames stepped × NX2navi's stick speed),
     so the frame rate and the stick setting cancel out.
   - Bias is learnt only while the accelerometer reads 1 G and the rate stays slow for a second.
   - While it runs, the game's six-axis read is handed a controller at rest, so the game's own gyro adds nothing.
8. **DualSense HD rumble:**
   - The DSP is adapted from RenHDrum (MIT/Apache-2.0); keep its copyright line and add a third-party notice.
   - Over USB a DualSense is also a 4-channel 48 kHz audio device; channels 3 and 4 drive the left and right
     actuators.
   - For each side, play the game's two bands as two sines at the game's frequencies (clamped to 20–1000 Hz),
     with amplitude = sqrt(Switch 2 lift curve), plus a short accent and dip at a vibration's start.
   - Use 256-frame slots with peak hold so a one-update tick isn't lost, a 4 ms glide, and a 0.8 ceiling.
   - Open the SDL audio device on its own thread with a generation counter, retry every 2 s, and stop the motors
     once when it opens. Find it by name: "DualSense" or "Wireless Controller".

## Verification
- **In game:** the user played on 1.1.1 on Windows.
  - Sprint: toggle and hold on L3 and B.
  - Minimap: Normal hides it, Pro shows it, it stays as chosen through menus, and the pause big map draws.
  - One bug report each led to the fixes in Gotchas 6 to 8.
- **Unit tests:** `tests/sprint_check.py` and `tests/minimap_check.py`, against stand-in Link and screen
  objects. Each in-game bug was first reproduced as a failing test case, then fixed.
- **Patch tables:** checked against the real `main` with the generator's own checker, every NX2navi version.
- **Gyro:** the user played the hookshot aim with the gyro in "only while aiming" mode, and it works.
  - A 50 s per-frame memory recording (below) gave the aim flag and the 1:1 linear response, with numbers.
  - `tests/gyro_mouse_check.py` checks the player-space yaw held flat, upright and between, pitch, both
    sensitivities, bias learning and the turn dropped during menus.
- **HD rumble:** played on a USB DualSense ("works very well"). `tests/rumble_haptics_check.py` checks the curve,
  sines, ceiling, glide, accent and peak hold.
- **Not verified:** the bow and slingshot setting the same aim bit (only the hookshot was recorded), whether the
  game's sensitivity option scales the aim as well as the camera, and HD rumble over Bluetooth (the motors are
  kept there). Also whether `+0x2359` (the event display flag) is meaningful on Pro, the latest
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
12. **The sprint on L3 stopped L3 hiding the text box in conversations.** **Cause:** Link's update keeps running
    during a talk, so the press counted as gameplay. **Fix:** also require no running event
    (`[[main+0x4c7e090]]+0x68 == 0`). Hiding the box only while L3 is held is the original game's behaviour.
13. **"Gyro only while aiming" never turned the hookshot aim.** **Cause:** the gate tested bit 30 of the camera
    settings word, which only flashes at the shot. Narrow log lines kept catching that 0.07 s flash and made it
    look like the aim, and an earlier gate on Link's state id failed because aiming keeps Link in Wait/Walk.
    **Fix:** bit 32.
14. **Five rounds of narrow diagnostics didn't find the aim; one recording did.** **Cause:** each round logged
    one guess, needing a full play-test, and the guesses were shaped by the previous wrong answer. **Fix:** a
    host-side recorder hooked on Link's per-frame update. From a trigger (a right-stick flick) it writes one
    record per frame for 3 minutes: sticks, buttons, the gyro turn, and raw copies of Link (0x2000), his actor,
    input block, component table, state and the camera input object. That's about 18 KB a frame, 60 MB for 50 s.
    Then answer offline with numpy:
    - **Flags:** bits set in *every* frame of a labelled window and in *no* frame outside it (lock-on included).
    - **Inputs:** floats whose per-frame change correlates with the turn, and which lag.
    - **Angles:** fields whose change equals the turn in radians, degrees or 16-bit units.
    Ask the player for a scripted sequence (still, aim, slow/fast stick each way, wave the controller, lock-on).
15. **A "turn input" field turned out to be an animation copy.** **Cause:** the only exact radians match for
    Link's yaw (`link+0x102c`) is rebuilt from the actor matrix by an animation update. **Fix:** check what writes
    a field (read → compare → write next to an `atan2` means a copy) before treating it as the source.
16. **The game's gyro aim feels like a stick.** **Cause:** the gyro goes in before the dead zone, smoothing and
    stick curve. **Fix:** add degrees after the curve (the processed stick), divided by that point's linear rate.
    That's mouse-like, not a virtual stick.
17. **HD rumble on a DualSense felt weak or missed short ticks.** **Cause:** Switch 2-tuned tiny amplitudes, and
    single-update values falling between audio callbacks. **Fix:** the lift curve plus sqrt, and peak hold per
    256-frame slot.

## Assets
None.

## Cost and time
Several sessions over 3 days, including a cheat-cave prototype, a native rewrite and three NX2navi version
moves. The gyro aim took about 8 play-test rounds, 5 of which a full recording would have saved.

## Open questions
- The meaning of `+0x2359` on Pro, and whether respecting it would be a cleaner event gate.
- A shared "gameplay" signal in NX2navi (sprint and minimap each keep their own Link-update heartbeat).
- The minimap's contents when force-opened on Pro looked right in the user's tests, but they are not checked
  in every area type (indoors, dungeon floors).
- Whether the bow, slingshot and other aimed items set the camera's bit 32 like the hookshot.
- The aim's vertical rate per unit of `+0x53c` (only the horizontal was measured), and the ~3% gap between the
  aim (1.83°/frame) and camera (1.78°/frame) rates.
