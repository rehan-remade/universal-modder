---
kind: game
title: "CONTROL Resonant's Dylan as the player: control takeover, 217 retargeted clips, the Aberrant drawn in D3D11, no-despawn physics"
game: "Red Faction: Guerrilla Re-Mars-tered"
games_also: ["CONTROL Resonant"]
game_version: "Steam app 667720, rfg.exe build cs:4931 (SHA-256 0d52039e7f2d3f25a4be52a2aba83919456fb3f00e52e75051726247471a2df4, 32-bit, link timestamp 0x5B9B718A)"
platform: windows
engine: native
route: native-hook
tools: ["MinHook 1.3.4", "Dear ImGui 1.91.9b", "Ghidra 12.1.4 (headless)", "capstone + pefile (via uv)", "Janitor 2026.10.6.1", "vgmstream r2168", "XAudio2 2.9", "MSVC x86 (Visual Studio 18) + CMake + Ninja", "doctest", "numpy, scipy, Pillow", "d3dcompiler_47", "um backup"]
anti_cheat: "none; single-player only (the mod stays idle in multiplayer, read from the game's multiplayer flag)"
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: ["@skurtyyskirts"]
date: 2026-10-27
links: ["https://github.com/rfg-modding/RSL", "https://github.com/rfg-modding/RFGR_Types", "https://github.com/LostPhysx/RFG-VR", "https://github.com/rfg-modding/RfgToolsPlusPlus", "https://github.com/rfg-modding/RFGM.Formats", "https://github.com/TsudaKageyu/minhook", "https://github.com/ocornut/imgui", "https://github.com/vgmstream/vgmstream", "https://github.com/dtzxporter/Cast", "rf-gmod-gravity-gun-sandbox-and-armageddon-port.md"]
tags: ["dinput8-proxy", "control-takeover", "pose-override", "animation-retarget", "d3d11-overlay-draw", "despawn", "havok", "first-person", "god-mode", "wwise", "xaudio2", "cross-game-port", "northlight"]
---

# CONTROL Resonant's Dylan as the player: control takeover, 217 retargeted clips, the Aberrant drawn in D3D11, no-despawn physics

> A private mod that makes Red Faction: Guerrilla Re-Mars-tered play like CONTROL Resonant. Dylan Faden's PC
> control map replaces RFG's on-foot controls, his kit (powers, the Aberrant's melee forms) runs inside RFG's
> engine, 217 of his animation clips drive Mason's skeleton, his own Wwise sounds play through XAudio2, and his
> Aberrant weapon is drawn into RFG's D3D11 frame. A `dinput8.dll` proxy loads a native DLL of MinHook detours.
> Four builds ran in the human's own tests (logs read after each). The fifth build (the visible Aberrant, the
> damage fix, Resonant's key map) was deployed but **never run**: the mod was archived and uninstalled on
> 2026-10-26 to make room for [rf-gmod](rf-gmod-gravity-gun-sandbox-and-armageddon-port.md), which reuses its
> plumbing. All CONTROL Resonant data was read offline from the human's own install; none of it is published.

## Setup
- **RFG Re-Mars-tered, Steam app 667720**, `rfg.exe` with exactly the hash above. Windows 11. GOG addresses differ
  non-uniformly, so the tables below are Steam-only. The exe is ASLR-relocated: add (live base - 0x400000).
- **Build:** MSVC x86 from Visual Studio 18 (`vcvarsall x64_x86`), CMake + Ninja, `/W4 /WX`. CMake fetches
  [MinHook 1.3.4](https://github.com/TsudaKageyu/minhook) and [Dear ImGui 1.91.9b](https://github.com/ocornut/imgui)
  pinned by SHA-256. Tests: doctest (pure C++20 core) plus native logic tests and a smoke host.
- **Reverse engineering:** Ghidra 12.1.4 headless on the human's exe (one Ghidra at a time, BelowNormal priority:
  three parallel heavy jobs froze the PC once). Quick disassembly of single functions with capstone + pefile
  run through `uv`. Community references, cloned read-only: [RSL](https://github.com/rfg-modding/RSL) (the old
  script loader; its addresses were the starting point), [RFGR_Types](https://github.com/rfg-modding/RFGR_Types)
  (the engine's structs and enums), [RFG-VR](https://github.com/LostPhysx/RFG-VR) (render-path research),
  [RfgToolsPlusPlus](https://github.com/rfg-modding/RfgToolsPlusPlus) and
  [RFGM.Formats](https://github.com/rfg-modding/RFGM.Formats) (packfile formats).
- **CONTROL Resonant, read offline only and never launched:** Janitor 2026.10.6.1, a command-line
  extractor/exporter for Remedy's Northlight `.rmdtoc` packs, run at BelowNormal. Animation exports are
  [Cast](https://github.com/dtzxporter/Cast) files. The exact public source of the Janitor build used was not
  recorded. [vgmstream](https://github.com/vgmstream/vgmstream) r2168 decodes the `.wem` audio.
- **Python** tools run through `uv run --with numpy --with scipy --with pillow python -I ...`.
- **Backups first:** the original `misc.vpp_pc` and `table.vpp_pc` (the data patch edits them) were snapshotted
  with `um backup` into `~/.universal-modder/backups/rfg-resonant-originals`. The deploy script restores them byte
  for byte on uninstall and checks their hashes.

## Route and why
- **Native hooks through a `dinput8.dll` proxy.** RFG is native C++ with no gameplay mod loader. It imports
  `dinput8!DirectInput8Create`, so a proxy DLL in the game folder loads `resonant\resonant.dll`, then forwards to
  the system dinput8. A `resonant\disable.txt` file makes the proxy skip the mod (kill switch).
- **An address table with prologue fingerprints.** Every entry (function or global) carries a confidence (H/M/L)
  and a source. At build time a script hashes each function's first 16 bytes out of the human's own exe into a
  generated include (`RES_PROLOGUE(name, len, mask, hash)`). At startup the DLL checks the exe's SHA-256 and link
  timestamp, then each prologue, and turns off any feature whose entries don't match. A Steam update therefore
  switches the mod off instead of crashing it.
- **Control takeover at the action getters**, not at the key level (details below). Answering "not pressed" for
  RFG's on-foot actions hides them without racing the message pump; the kit injects the few it needs for N frames.
- **Pose override at the local-to-model step** instead of new animation assets: Resonant's clips are retargeted
  offline onto RFG's `mason.rig_pc` and written over the player's local pose on RFG's job threads.
- **The Aberrant drawn by the mod**: RFG has no mesh for it, so the mod skins and draws it into RFG's frame with
  D3D11, just before RFG's UI.
- Considered and rejected: RFG's camera mode 8 for first person (Gotcha 9), enlarging the object pools (Open
  questions), RFG's sound cues for Dylan (the human chose Resonant's own sounds, with RFG's impacts kept).

## How the game works (what we had to learn)
VAs below (image base 0x400000). Calling conventions are from the disassembly.

### Frame, player and input
- Hooks: `player::do_frame` 0xAD5A80 (and an alternate 0xAE66B0), `world::do_frame` 0x940AB0,
  `gameseq_get_state` 0x7BFCF0, `game_is_paused` 0x7C1690, `get_local_player` 0xA108D0, local player global
  0x3023874, multiplayer flag 0x2FEB588.
- **On-foot input** goes through five `cdecl(int action, int user)` getters: held 0x6FE970, pressed 0x6FEA30,
  pressed+consume 0x6FEAF0, down/repeat 0x6FE9D0, down+consume 0x6FEA90; analog 0x6F8E30 (and 0x6FEB50); relative
  mouse 0xC790B0. The action-name table at 0x12B81BC (16-byte records) matches RFGR_Types' `control_button_action`:
  20 attack, 21 melee, 22 jump, 23 sprint, 24 crouch, 25 reload, 26 zoom, 27 cover, 28 action, 29 detonate,
  0/50-57 weapon menu, 99/100 cycle weapons, 107 shoulder swap; 58 map, 86 pause and 61-85 menus (leave these
  alone). The mouse wheel's weapon cycle is analog axis 0xD, not an action.
- **Movement:** the character proxy update 0x837D90 (thiscall, `ret 0x1C`); proxy velocity at +0x40.
  `human_teleport` 0xA9A7A0, `rfg_snap_to_ground` 0xAEB8D0, `world_object_from_handle` 0x93C050, Havok body
  pointer 0x80E870, linear impulse 0x823C20.
- **Human state fields** (decoded from the first test's log against RFGR_Types' enums): +0x2F4 `cur_state`
  (0 standard, 1 jump, 2 fall, 4 dead), +0x2FC `cur_stance` (not "on ground"), +0x304 movement mode (1 direct,
  4 jump, 5 fall, 7 knockdown), +0x308 submode. Airborne = state 1/2 or mode 4/5.
- **Damage sink** 0xACED70: `float cdecl(human* victim, object* attacker, float amount, int type, ...)` for
  bullets, explosions, melee and vehicles. Hooking it gives god mode and lets the kit's hits go through RFG's own
  armour, death and hit-reaction code. NPCs have 300-600 HP; the sledgehammer deals 2000.
- **God-mode flags:** human `hflags` at +0xB4 (invulnerable: byte +0 bit 5; invulnerable_to_debris: +8 bit 2;
  disallow_flinches_and_ragdolls: +15 bit 5), player `pflags` at +0xDCC (never_die bit 4), hit points float
  +0x914, max int +0x910.
- **Explosion templates** live in an in-memory table; `Molotov Explosion` is not in it (Gotcha 5).

### Animation
- The player's pose lives in an anim entity: `human+0x32C` holds a handle; entity = 0x39ACBD0 +
  (handle % 0x164) * 0x410.
- **Local to model** runs in 0xC93230 (thiscall, `ret 0xC`) on job worker threads. Rows of RFG's `matrix43` are
  columns of the standard rotation matrix. Bone controllers (lean, IK) and a camera bone also feed the pose.
- The held item's alpha is set through 0xA65F80; the player's orient is rewritten every frame by 0xA0CE70.
- **Skeleton `mason.rig_pc`** is in `misc.vpp_pc` (not in `rfg_PC.str2_pc`): 53 bones (49 common, 4 virtual),
  18 tags. Y up, metres, a 1.72 m human in an A-pose facing +Z with his left at -X, so **left-handed**. Head (14)
  under neck (13), the eyes under the head, the camera bone (52) under the root, hand props under the hands.

### Camera, first person and the render frame
- **Camera update** 0x6DFFA0 (cdecl void, game thread) runs a per-mode update from a table at 0x12CFC84
  (5 pointers per mode, update at +0xC), then sets real pos/orient (+0x2C/+0x50 of the camera global 0x1DE4B50)
  from ideal, then shake. 0x6D0900 copies real into render (+0x10C). On foot is mode 10; vehicles 0. Aiming and
  the crosshair ray use real pos/orient. 0xAB2260 `cdecl(human*, vector* out, matrix* or null)` gives the eyes'
  midpoint.
- **The frame (Present thread, immediate context):** main view render 0x7CF730 → render begin → the 3D world
  0x4C74C0 (much of it recorded by a second thread into a deferred context) → 0x4F0F30 → **0x550830, the frame's
  2D primitive queue = the whole in-game UI**, `int thiscall(queue*, renderer*)`, which draws about 40 alpha
  quads onto the backbuffer. Menus with no 3D view draw their UI in 0x550480 instead, so 0x550830 runs only with
  a world on screen. Its prologue (`mov eax,[tls]; sub esp,18h; push esi; mov esi,ecx`) is a clean MinHook target.
- **Per-frame renderer state** = `*(renderer + 0x478)`: the camera setup 0x520D70 copies the view to state +0x400
  and the projection to +0x440 (row-vector D3D, left-handed, depth 0..1: proj[11] = 1, proj[15] = 0). Positions
  are relative to a world origin at state +0x80. Camera position = origin - (v12·r + v13·u + v14·f), with r/u/f
  the view's columns.
- At the UI stage the target is the 8-bit backbuffer after post-processing (shaders must gamma-encode
  themselves), and most likely no depth buffer is bound.

### Despawn and physics (the part no community source had)
- **The sweep** 0x724C90, run from the destruction driver 0x7250D0 about every 3 s, deletes or fades up to about
  10 pieces each time (more when the render-instance pool runs short). Its deleters, 0x724B90 (debris) and
  0x724A60(n, general_movers), take only pieces that are asleep, some distance from the camera and not
  destroyed. Off-screen pieces are deleted at once; on-screen ones fade over 1-2 s.
- **Most rubble is scheduled to vanish when it is born:** a building chunk flagged small fades 1-2 s after it
  breaks off (caller range 0x737CE0-0x7380B3), a part off a vehicle lives 30-210 s (0xB9EDD0-0xBA0C05), a wrecked
  vehicle's parts fade after 2 s (0xB78140-0xB782FF), and spawns clear a box of debris (0xBCD300-0xBCD4E6).
- Two fade starters carry all of it: 0xA175E0 `cdecl(debris*, delay_ms, fade_ms, bool from_nano)` and 0xA13D30
  `cdecl(mover*, delay_ms)`. Some fades are destruction itself: a chunk hit hard enough is pulverised and fades
  within 250 ms (0xA8ACF0), and the Nano Rifle dissolves debris (`from_nano`).
- **Fixed pools:** object_debris **500**, rfg_mover 4000, general_mover 3072, and a render-instance pool of 2100
  the sweep budgets against. Pool objects (debris 0x30C4F70, rfg_mover 0x1F595A0, general_mover 0x31A3A50, render
  free count 0x1514A74) hold a descriptor pointer whose +0x1C is the free count. A full pool is why chunks freeze
  in the air (they can't become physics pieces).
- **Havok (2010) solver** at hkpWorld+0x1F0: steps at world+0x31C (RFG ships 4), micro steps +0x320, then the
  inverses 1/micro +0x324 and 1/steps +0x328. tau 0.6, damping 1.0, friction tau 0.3 at +0x1F4..+0x1FC. The mod
  hooks `hkpWorld::stepDeltaTime` to write them. Offsets were compiled from RFGR_Types with MSVC x86 (`offsetof`)
  and cross-checked against RSL's panel defaults. Gotcha 7 is why all four step fields must be written together.

### CONTROL Resonant data (Northlight)
- Controls: Resonant's real PC map is in its `inputactions_game.json` (two key slots per action: Ctrl also
  dodges, arrows move, numpad `/`, C the loadout, G the Gap).
- Audio: Wwise bank version 154, one bank per event (5,786), no media inside the banks; every source is a loose
  `audio\media\<id>.wem` (Vorbis, 48 kHz for gameplay).
- Dylan's clips carry Resonant's own timing markers (`TrailActive`, `DamageWindow`, `lua_dlg_effort_*`,
  `PushRelease`, `ShieldExplosion`, ...), so sounds and damage windows can start on Resonant's frames.
- Janitor's Cast export is Y up, metres, **right-handed**, the character facing -Z with his left at -X. Clips are
  absolute curves at 30 fps (77 are additive and were never baked). Loops repeat their first frame at the end.
- The Aberrant's forms are separate weapon meshes animated by weapon joints in Dylan's clips. The weapon root
  rides `R_wrist_prop_JNT`, with curves relative to `C_animRoot_JNT`; left-hand forms use `L_wrist_prop`.

## Build steps
1. **Native:** a PowerShell build script runs `vcvarsall x64_x86`, CMake (Ninja) with the game exe path for
   fingerprints, then builds at BelowNormal with 8 jobs. Outputs: `dinput8.dll` (proxy) and `resonant.dll`
   (+ pdb). Run the core tests (153) and the native tests (56 plus a 12-check smoke host that loads the proxy the
   way rfg.exe does and must install nothing against an unknown exe).
2. **Animations** (pack `dylan.rpk`, 217 clips, 19 MB):
   1. Export Dylan's clips with Janitor. Run its `/names bones` in the same session as the export, or clip bone
      names don't resolve. Keep the filter tight (a broad wildcard pulled in 4 GB of face-capture clips).
   2. Read `mason.rig_pc` out of `misc.vpp_pc` and map bones. 42 are mapped: pelvis←C_body, spine←C_spine2,
      spine1←C_spine3, spine2←C_spine5, neck←C_neck2, head←C_head, clavicle←clavicle, upperarmtwist1←upArm,
      foretwist←loArm, hand←wrist, fingerN←Fing1 and fingerN1←Fing2, thumb1/thumb11←thumbFing1/2, thigh←upLeg,
      calf←loLeg, foot←ankle, toe0←ball. The other 11 (root, spinebend, camera, eyes, hand props, mid twists)
      keep identity.
   3. Retarget with rest-pose alignment through a Z mirror (C = diag(1, 1, -1), quaternions x y z w). Keep the
      root-motion travel **unscaled** and scale only the hips' own crouch and lean by the leg ratio (0.945).
      Aim Mason's rigid hand bone at Dylan's actual knuckle positions each frame (Dylan's palm bones animate).
   4. Bake RPK1: per clip, local rotations for the 53 bones plus a root track at 30 fps, a loop flag (off for
      wind-up/hold clips, which hold their last frame). The runtime maps 103 gameplay roles (idle/walk/run/sprint
      bands by speed, jumps, Elevate, dodges, each form's hits/charges/holds, 6 finishers, every power's start /
      hold / release, Execute, Reach, landings by fall speed) to clip names.
   5. Check: every mapped limb points where Dylan's does on every frame (min cosine 0.981, at the pelvis, where 3
      spine bones stand in for 5), planted feet within 2.8 cm, unit and sign-continuous quaternions, stick-figure
      preview PNGs side by side, and a core test that plays the real pack through 1,770 scripted frames.
3. **Sounds** (pack `dylan_sfx.rsfx`, 257 sounds / 791 variants / 196 cues, about 62 MB): extract banks and media,
   resolve each event's sources through the Wwise bank hierarchy, decode with vgmstream, normalise loudness, and
   write the mod's own RSFX v1 pack (named sounds, their variants, per-clip cue lists). Played with XAudio2 2.9
   (loaded at run time), 3D panned, with a watchdog on the Present thread that pauses the engine when the game
   tick stops (pause menu, alt-tab).
4. **The Aberrant** (pack `dylan_aberrant.rabr`, RABR v1, 40 MB, baked in 19 s): 14 meshes (handle, flurry R/L,
   slash, slice, crush, extend, drill, bludgeon R/L, cleave, split, execution R/L) mirrored into RFG's space and
   remapped to at most 32 weighted joints; 22 textures at 512 px with mips (albedo `_d`, glow `_e`); 167 clips of
   weapon-joint tracks **relative to Mason's r-hand (bone 26) / l-hand (25)**, plus show windows from the clip
   markers (a form shows only while its clip draws it; the handle otherwise, except in neutral, climb, vault,
   mantle and death clips). Layout: 64-byte header; 32-byte texture, 96-byte mesh, 96-byte clip, 16-byte track and
   16-byte window records; 40-byte vertices (pos 3f, normal 3f, uv 2f, 4 u8 joints, 4 unorm8 weights); tracks are
   frames x joints x 10 floats (pos, quat xyzw, scale).
5. **Data patch:** a small `tweak_table` xtbl edit in `table.vpp_pc` (higher fall-damage thresholds so a ground
   slam can't kill the player). Steam's "Verify integrity" undoes it but not the DLL.
6. **Deploy** with the game closed (the script refuses while `rfg.exe` runs): proxy, DLL, packs, data patch;
   `-DryRun`, `-Uninstall` (byte-for-byte restore), `-ResetIni`. The human's `resonant.ini` holds their loadout,
   so settings changes go through versioned migrations (v1 → v4), each leaving `resonant.ini.v<N>.bak`.

## Verification
The human ran every in-game test (the agent never launched RFG or Resonant) and the agent read
`<game>\resonant\resonant.log` afterwards; the log prints the exe check, every address with its confidence and
result, each hook, and probes.
- **Test 1 (first build, powers on Mason's controls):** all 60 addresses and 8 hooks up, overlay up. Movement
  broke: NaN velocity killed Mason (Gotcha 1). The human then asked for a full control and movement takeover.
- **Test 2 (takeover):** no crash; run 6 m/s, dodges 14 m/s, double-jump kicks +4.9..7.5 m/s, Elevate capped the
  fall, RFG's keys fully blocked. The human: "the player still has a hammer and moves as if it's the vanilla game".
- **Test 3 (Dylan's animations):** the pose hook matched the live rig (53 bones, 0 name mismatches); a 7-minute
  combat session with no crash.
- **Test 4 (god mode, no despawn, solver at 8 steps, first person, sounds):** no crash; the ini migrated. The human
  saw NPC physics off for the whole world, Dylan's weapons invisible and no damage (Gotchas 6-8).
- **Fifth build: not verified in game.** Checked offline only: the embedded HLSL compiles with `D3DCompile`
  from the system `d3dcompiler_47` (vs_5_0 2,868 bytes, ps_5_0 2,080 bytes, no warnings), 0x550830's first bytes
  are a clean thiscall prologue, the C++ reader loads the real pack (crush shows at frame 20 of
  `dylan_crush_attack1_01`, gone at 100), core 153 / native 56 + 12 smoke tests pass, plus an independent review.
- **Not verified anywhere:** whether the render state still holds the 3D matrices when 0x550830 runs, where the
  world's depth buffer is at that point, the despawn guard's thresholds, the first-person eye offset.

## Gotchas
1. **Test 1 killed Mason within seconds.** **Cause:** the proxy velocity reads NaN in components the game isn't
   driving (x/z at idle, y in the air); the mod kept those components, wrote NaN back, the position went NaN and
   the game killed the player (state 4, knockdown mode 7). Also +0x2FC, used as "on ground", is the stance.
   **Fix:** never write a non-finite component (core test first); airborne = `cur_state` 1/2 or mode 4/5.
2. **Powers bolted onto Mason's controls weren't what the human wanted.** **Cause:** "like playing CONTROL
   Resonant, but in Red Faction Guerrilla" means the whole on-foot scheme. **Fix:** take over the action getters
   (answer false for RFG's on-foot ids, keep menus/map/pause) and drive movement from the kit's own controller.
3. **The hammer still swung under Dylan's attacks.** **Cause:** the kit injected RFG's attack action so an
   animation would play; once the pose override existed, that only added the hammer's damage and sound.
   **Fix:** stop feeding attack/melee; the kit deals damage through the damage sink and breaks walls with small
   structural blasts. The hammer stays equipped (alpha 0 via 0xA65F80) but unseen.
4. **Two runtime clip names didn't exist in Resonant.** `dylan_combat_dodge_air_fwrd_01` is
   `dylan_neutral_dodge_air_fwrd_rlf_01` (or `_llf_01`), and `..._flinch_medium_frnt_01` is
   `..._flinch_med_frnt_01`. **Fix:** resolve every role's clip against the baked pack in a test.
5. **The Inferno power's blast did nothing.** **Cause:** `Molotov Explosion` is not in RFG's in-memory explosion
   table. **Fix:** use `exp_fiery_small`, fall back to the table's first entry, and log every template name at
   startup.
6. **Dylan's hits did almost no damage.** **Cause:** the kit's damage numbers were on Resonant's scale; RFG NPCs
   have 300-600 HP. **Fix:** `world.damage_scale` 4 on the kit's hits, with hit logging (first 30, then every
   50th, HP before and after).
7. **After "physics max", every NPC moved wrong, not just the player.** **Cause:** the solver write is
   world-wide, and it changed the step count (4 → 8) without the stored inverses (+0x324/+0x328), so bodies ran at
   twice real time while NPC character controllers didn't. (Found later in rf-gmod's offline RE.) **Fix:** off by
   default (ini v3 migration); if raised, write steps, micro steps and both inverses together, inside the
   `stepDeltaTime` detour (the world may be stepping on another thread), after checking RFG's defaults are there.
8. **Dylan's weapons were invisible.** **Cause:** RFG has no mesh for the Aberrant. **Fix:** draw it yourself at
   0x550830: after the camera update, build skin = player world x FK(hand) x track x inverse bind per joint and
   keep it with the camera position in a small ring; on the render thread draw the entry whose camera matches the
   frame's (within 5 cm, newest wins), with the frame's own view/projection, every pipeline state saved and
   restored, SEH-guarded (a fault turns it off for the session).
9. **RFG's camera mode 8 looks like a first-person mode but isn't playable.** **Cause:** it takes its view from
   the player's orientation and a camera-bone offset, not from the mouse. **Fix:** keep on-foot mode 10 and move
   real and render pos to the eyes (0xAB2260) after each camera update.
10. **Hiding the player with `human_hide` drops him through the ground** (RFG-VR found it). **Fix:** hide only
    the head by scaling the head bone (rig 14) by 0.001 in the pose override.
11. **Debris still vanished with the sweep's deleters disabled.** **Cause:** fades are scheduled when pieces are
    born. **Fix:** hook both fade starters and refuse only the despawn callers by return address
    (`_ReturnAddress()` inside a MinHook detour is the original caller): the caller ranges above. Let pulverise
    and Nano Rifle fades through.
12. **With deletion fully off, new debris stops spawning.** **Cause:** the fixed pools (object_debris holds 500).
    **Fix:** a guard that lets the game's own deleter run only when a pool's free count drops under a threshold
    (24 slots; render instances 48); the game then picks far, asleep, off-screen pieces itself.
13. **A key the mod owns stays swallowed after its tick stops.** **Fix:** tie key ownership to the takeover's own
    lapse timer inside the input layer, not to the tick.
14. **Retarget errors that looked like bugs:** scaling the whole root by the leg ratio left Mason 16-18 cm low on
    climbs (keep travel unscaled); `_90l/_90r/_180` clips turn the body by their end (don't also turn the
    character); the combat idle stands with the hips about 54° right (authored that way); vertical root motion
    (Elevate rises 2.5 m inside its clip, climbs 2.9 m) pulls the body away from the collision capsule unless the
    runtime applies only the pelvis's vertical bob on the ground.
15. **Windows shell traps on this machine.** Bash heredocs and `sed` fed Windows paths turned `\r`/`\f` into
    control characters (in a journal and an index file), and a PowerShell `"$AnimPack:"` parsed as a
    drive-scoped variable, so the deploy script failed and changed nothing. **Fix:** write files with an editor
    tool or a script file, scan journals for control characters, and use `${AnimPack}` in strings.

## Assets
No generated assets. Dylan's clips, sounds and Aberrant meshes come from the human's own CONTROL Resonant install,
are baked into packs that stay on that PC outside git, and are never published.

## Cost and time
Builds 1-4: about 15 hours of agent time (2026-10-19 and 2026-10-26); build 5: about 3.5 hours more. Sub-agents
built the animation export/retarget pipeline (about 34 minutes) and the sound pipeline.

## Open questions
- The fifth build's in-game result: the Aberrant's placement in the hand, occlusion (it likely shows through
  walls without the world's depth), brightness, the damage scale, the WeaponWheel-style layer.
- Dylan's mesh on `mason.rig_pc` (the same bone map would drive a mesh swap).
- Raising the debris pool past 500 means relocating a live pool (its descriptor is filled at run time): untested.
- Three mover-fade callers are not decoded (0xAA2770, 0x99CD30, 0x99C140) and are left alone.
- Whether streaming a zone out deletes its debris through another path.
