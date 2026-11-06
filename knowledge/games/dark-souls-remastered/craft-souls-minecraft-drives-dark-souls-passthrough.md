---
kind: game
title: "Craft Souls: Minecraft played inside Dark Souls: Remastered (passthrough bridge, RE map of the game)"
game: "Dark Souls: Remastered"
games_also: ["Minecraft"]
game_version: "Steam AppID 570940, app 1.03.1 (file 1.0.0.0), DarkSoulsRemastered.exe 50,286,344 bytes, SHA-256 A45AAA36...8D7B, SizeOfImage 0x319B000"
platform: windows
engine: fromsoft
route: passthrough
tools: ["ReShade 6.8 add-on API", "Minecraft 1.21.1 + Fabric", "Ghidra 12.1.4 (headless, JDK 21)", "REA MCP", "Python 3 (pefile, ReadProcessMemory)", "DSR-Gadget (offsets only)"]
anti_cheat: "no client anti-cheat found by um scan; part of .text is encrypted on disk (protection), left alone: the exe stays as installed and all patches are in memory; servers are live, so offline only (add-on removed before going online)"
status: in-progress
agents: ["Copilot SDK in VS Code (model not recorded)", "Claude Code (Opus 5.5)"]
humans: []
date: 2026-11-02
links: ["https://github.com/JKAnderson/DSR-Gadget", "https://soulsmodding.com/", "https://github.com/rehan-remade/universal-modder/tree/main/examples/minecraft-gta5-passthrough", "https://reshade.me", "https://fabricmc.net", "https://github.com/morluto/rea"]
tags: [minecraft, passthrough, reshade-addon, depth-compositing, camera, havok, collision-geometry, game-thread-hook, event-scripts, params, fmg, live-memory-diff]
---

# Craft Souls: Minecraft played inside Dark Souls: Remastered

> Minecraft (Fabric 1.21.1) runs beside Dark Souls: Remastered and is composited into the Dark Souls frame
> by ReShade add-ons. In "drive mode" Minecraft has the focus and Steve walks through Lordran: Dark Souls'
> collision becomes invisible Minecraft blocks, enemies become hittable Minecraft entities whose hits the game
> reacts to (flinch, aggro, kills, drops), E-prompts, bonfires, ladders, lifts, breakables and death respawn
> work through the game's own systems. Everything below was tested in the real game by the user unless
> marked otherwise; it is still in progress (sound in the background is the main open item).

## Setup

Steam AppID 570940 at `C:\Program Files (x86)\Steam\steamapps\common\DARK SOULS REMASTERED`.
`DarkSoulsRemastered.exe` x64, app 1.03.1, file version 1.0.0.0, 50,286,344 bytes, SHA-256
`A45AAA36DD2F6CC151670A639EA5547043CF38EA79FF4178B963C6ED71F98D7B`, SizeOfImage `0x319b000`, image base
`0x140000000` (no ASLR observed). That size and hash match the Steam exe in the
[portal gun note](portal-gun-prototype-via-dinput8-proxy-dll-player-camera-and.md) (build 10943698): it stays as installed,
and every patch below is made in memory. ReShade 6.8.0.2155 (add-on build, API 20) is the install's `dxgi.dll`
(a static import of the exe, so add-ons load before the game initialises). Guest: Minecraft 1.21.1, Fabric
Loader 0.19.5, Fabric API 0.116.17+1.21.1, JDK 25, Loom 1.18.2. Native: MSBuild 18.10.1, Windows SDK
10.0.26100.0, CMake. RE: Ghidra 12.1.4 on JDK 21 (headless), REA MCP 6.4.

**Offline only.** DSR's PC servers are live. The add-on writes HP and stamina, calls the game's damage and warp functions
and patches code in memory, and in an online session that would reach other players and can get the account soft-banned.
It loads on every launch, so keep Steam in Offline Mode (or block `DarkSoulsRemastered.exe` in the firewall) while it's in
the game folder, and remove it before playing online. This is the same rule as the portal gun note.

All addresses below are **RVAs** from the image base on this build. Offsets are hex.

## Route and why

Passthrough: Minecraft stays the source of truth for blocks and its own simulation; Dark Souls supplies the
scene, camera, depth, characters and collision. There is no community loader for DSR; the installed ReShade
loads add-ons from the game folder, which gives D3D11 events (binds, draws, buffer writes, present) without
replacing `dxgi.dll`. Everything gameplay-side goes through memory at runtime: reads, a few field writes (HP,
stamina, latch bytes), calls to the game's own functions on its thread, and a few small code redirects written
by the add-on (listed below). Content porting or a headless reimplementation would not give "Minecraft
running inside Dark Souls".

The shape is the one in this repo's [GTA V example](../../../examples/minecraft-gta5-passthrough/README.md) and
[note](../gta-v/minecraft-passthrough.md): frame compositing for the picture, state exchange for collision and combat. See
[choosing a mashup route](../../techniques/choosing-a-mashup-route.md),
[frame compositing](../../techniques/frame-compositing-depth-and-pose-sync.md),
[collision and combat bridging](../../techniques/collision-and-combat-bridging.md) and
[bridge contracts](../../techniques/bridge-contracts-ownership-units-and-lifecycle.md). The portal gun note maps more of
the same exe.

## How the game works (what we had to learn)

### Rendering and camera (foundation)
- D3D11, FL 11.0. Main depth = the 1920x1080 `R24G8_TYPELESS` / `D24_UNORM_S8_UINT` target with the most
  draws, cleared to 1.0, conventional Z, still valid at the add-on `present` event. Projection measured from
  constant-buffer writes: vertical FOV 43, near 0.05, far ~3112, +Z forward. World is Y-up, left-handed,
  metres; Minecraft x = DS x, z = −DS z, yaw + 180, pitch negated.
- The view-projection the game uploads per frame is ambiguous (many look-alike cameras); pick the one bound
  to the vertex shader at the most main-depth draws (see gotchas 8–9). Minecraft is composited before the
  HUD at the second bind of the tone-mapped LDR target.
- Drive mode NOPs the game's render-camera copy (FOV store at `24fd98`, matrix stores `24fdc7..24fde7` in
  the update function `24f6b0`) and writes Minecraft's camera itself once per frame.

### Protection and how the RE was done
- About 2.1 MB of the first `.text` is encrypted on disk and decrypted at start; static tools on the file
  see garbage there (some entry points also jump into obfuscated stubs, e.g. the window procedure).
  Analysis used a read-only memory dump of the user's own running game, kept private and outside any repo.
  Nothing here strips or bypasses the protection. AOBs are matched after the game has decrypted itself.
- Fast static loop: headless Ghidra on an already-analysed project with `-noanalysis -readOnly` and a
  20-line post-script (decompile / xrefs / listing) runs in ~10 s; re-importing through REA would redo a
  40-minute analysis. Script-API natives are found from their registration stubs (`lea r8, name;
  lea rdx, binder` → native = qword at binder+8), which names hundreds of engine functions.
- **Hardware data breakpoints killed loads silently** (twice). Live work used only `ReadProcessMemory`
  watchers that diff structures at 50 ms – 1 ms intervals while the human does one thing in game.
- The data side is unpacked in the install: `param/GameParam` + `paramdef/` (field names!), `event/*.emevd`,
  `msg/ENGLISH/*.msgbnd`, `map/` collision, `obj/`. Reading them (read-only) answered many questions
  faster than code.

### Characters
- WorldChrManImp static (DSR-Gadget pattern) `1c77e50`; player `+0x68`. Characters live in **17 per-block
  slots** at `+0x668 + i*0xE8` (`+0x60` count, `+0x68` array of 0x38-byte entries, ChrIns* at `+0`).
- ChrIns: HP / max `+0x3E8/+0x3EC` (writing 0 kills properly: drops, boss victory), stamina `+0x3F8`,
  **team `+0xD8`** (6 Enemy, 7 Boss, 8 Friend, 9 AngryFriend, 14 Neutral…, names in a table at `1a26270`),
  event entity id `+0x2B0`, model id UTF-16 at `+0x88`, NoDead bit `+0x524 & 0x20`, draw bit `+0x2A6 & 0x80`,
  position `[[+0x68]+0x28]+0x10`, animation id `+0x16C` (-1 none).
- **Human NPCs (Solaire, Petrus…) are `PlayerIns`, not `EnemyIns`** — filtering by the EnemyIns vtable
  drops them all.
- Disabled per the game's own `IsDisable`: `[[chr+0x18]+0x20] & 1`; the dword `[[chr+0x18]+0x10]` is an
  activity/LOD state (2 near the player), not "disabled".

### Hits, aggro, guard breaks
- A per-frame **game-thread hook**: the main step `15ce90` calls the menu update at `15d50e` (5-byte `call`);
  pointing it at a near stub gives a safe place to call engine functions that allocate.
- Game-side damage: `3c9b50(DamageMan [1c7a050], behaviorId, attacker ChrIns*, target ChrIns*, float4* pos,
  -1, 0)` (the engine behind the event command CreateDamage_NoCollision). With the player as attacker the
  table is BehaviorParam_PC → AtkParam_Pc. Row 10 ("egg attack") has damage level 5 (blown away); **row 542**
  (ladder slide-down attack) is a light flinch with no stamina cost. Aggro: `5cb240(chr, target)`.
- Guard break from a Minecraft axe: set the enemy's stamina `+0x3F8` to 0, then the game hit.

### Interact, bonfires, death, warps
- E-prompts: `FrpgEventActManImp` (vt `1367b50`, static `1c7b658`); **byte `+0x4E` is a sticky "action
  pressed" latch** consumed by the offered prompt (`+0x4D` = consumed, `+0x20` current entry, entry `+0x0C`
  text id). Works without focus or input injection.
- **Rest detection must use MenuMan (`1c88d98`) state `[9]` (`+0x30 + 4*9`) 0 → 1**, not animation ids: the
  sit animations differ per bonfire (Firelink 7710–7712, Undead Burg 7720–7722). Last bonfire GameMan
  (`1c74e08`) `+0xB34`, estus PlayerGameData `+0xED8`.
- **Respawn at the last bonfire (= Dark Souls' death respawn, also resets enemies):** on the game thread,
  `4b0ce0()` (full recover), `4aeb00(0, -1)` (script `SetDefaultMapUid`: map from the bonfire, destination
  point −1, GameMan `+0xB32 = 1` "respawn at last bonfire"), `4ae9c0(0)` (`WarpNextStageKick`). Passing the
  bonfire id to `WarpNextStage_Bonfire` instead lands at a fixed default spot (gotcha 15).
- Game warps: same-map teleports set ChrIns `+0x2A5 & 2` until the next character update; map changes
  write GameMan `+0x1C/+0x20/+0x19`. Map id `+0xBD0`. Cutscene: RemoManStep `[1c71970]+0x150`.

### Input, ladders
- The player's input object is a PadManipulator (vt `132f1e8`, PlayerIns `+0x70`): 53 action bytes at
  `+0x84` (+ previous frame at `+0xB9`), stick results at `+0x200..+0x21F`. **`+0x224` (int) is a built-in
  one-shot "press action N" field** the pad update consumes.
- Ladder climbing needs stick input without focus: the two stick readers `1a3700` (y) / `1a3750` (x) are
  tiny functions; replacing them at their entries (2 patches) beats redirecting their 12 call sites. Ladder
  state `[[chr+0x68]+0x48]+0x1E0` (1 mount from top, 8 on, 4/5 sliding, 7 landing, -1 off). Slide down =
  action index `0x0A` (backstep) pressed twice ~0.17 s apart.

### Objects (doors, lifts, breakables)
- WorldObjManImp `1c75dd8` → blocks (0x160) → inline ObjIns (0x120). ObjIns `+0x42` HP, `+0x45` flags
  (`0x01` breakable, `0x10` destroyed), `+0x4C` collision layer, `+0xB8` physics (same FrpgPhysSysIns type
  as map collision). Break with `2fcd30(ObjIns*)` on the game thread.
- **Lifts move their rigid bodies, not the object**: the Firelink lift's cylinders follow the ride while the
  ObjIns model position stays at rest. Breaking swaps the body for layer-21 debris that leaves the world.

### Collision geometry (terrain for Minecraft)
- Map collision files are Havok 2015 binary tagfiles (`TAG0`) in `map/mAA_BB_00_00/h*.hkxbhd/bdt` (BHF3 +
  DCX zlib). The tagfile's TBOD section carries exact 64-bit type layouts, which also hold in memory.
  Graph: hkpPhysicsData → hkpRigidBody → hkpMoppBvTreeShape → CustomParamStorageExtendedMeshShape →
  triangle subparts (16-bit indices, 4 per triangle; vertices in world space). Floors wind clockwise from
  above. Parts are placed by their MSB part transform.
- Runtime list: WorldHitManImp `1c7a0b0` → blocks (0x98) → HitIns (0xC8) → `+0x60` holder → `+0x20`
  FrpgPhysSysIns → `+0x28` hkpPhysicsSystem → bodies (shape `+0x20`, layer `+0x4C & 0x3F`, transform
  `+0x170`).
- **Which layers are solid for the player:** the player's body capsule is layer 1 (read live); with the
  game's 64×64 collision matrix (`FrpgCollisionFilter`, one u64 row per layer at `+0x48`), layer 1 hits map
  layers 27, 28, 31 and object layers 17, 18, 20. Layer 30 parts are enemy-only walls (they blocked
  doorways); 32/34 are trigger volumes for the player's second (layer 33) capsule.
- Hit materials are named in `HitMtrlParam` (stone, wood, water, swamp, lava…).

### Text, names, HUD
- FMG lookup in memory: MsgMan `1c7e3e8`, FMG per category at `+8 + cat*8`; prompts category 30 (patch 101),
  NPC names 18 (119). Event flags are readable without calls (EventFlagMan `1c7c5f0`, documented layout).
- **Boss names come from the event scripts' boss bar `2003[11]`(state, entity, short slot, short nameId)**;
  NpcParam `nameId` is 0 for all but summon phantoms, and ordinary NPCs / enemies have no name text.
- NPC hostility is an event template (Firelink `11020510`): HP ≤ 95 % **and** damaged by the player → event
  flag + team 9 — game-side hits trigger it by themselves.
- HUD: the game's own Options → HUD byte `[GameDataMan(1c8a530)+0x58]+0x11` (live flag MenuMan `+0x30`);
  prompts stay visible when it is off.

### Audio (open)
- Sound = FMOD Ex/Event via `DLMO::MOFmodSoundManager` (static `1d04020`). The game itself does not change
  any sound state on focus loss; FMOD's output type comes from an internal `WindowsAPI` setting (default
  autodetect → `DSOUND.DLL` loaded). Forcing WASAPI (one-byte patch at `1014df5`, `74 16` → `74 0F`)
  applied in time but **did not** bring background sound back — still being investigated.

## Build steps

From `craft-souls-passthrough` (the author's project, not published): guest `cd mc-bridge; .\gradlew.bat build`.
Native: `vcvars64.bat` (VS 18 Build Tools), `cmake -S native-bridge -B native-bridge\build`, `cmake --build
native-bridge\build --config Release`; copy `craft_souls_compositor.addon64` beside the exe (delete it to uninstall).
Code patches are written once per session with all other threads suspended, bytes verified first, all edits batched
under one suspension (gotcha 13), and restored on unload.

## Verification

- Synthetic offline oracles (fake host, WARP compositor with synthetic depth, follow / frame / input oracles) for
  the bridge protocol and rendering math. These test the protocol and the maths, not the game.
- Real runs, with real Minecraft beside the real game (the user, screenshots and logs): occlusion that looked
  pixel-exact in screenshots; Minecraft under the HUD; building from inside Dark Souls; drive mode; terrain from
  collision geometry ("practically perfect"); E-prompts (bonfire, pickup, talk, fog walls); hits with flinch/aggro,
  kills, guard break ("shield broke"); NPCs hittable and turning hostile; ladders up/down/slide; lifts and doors as
  moving terrain; breakables broken from Minecraft; respawn at the last bonfire after a Minecraft death (New Londo →
  Firelink); rest detection at two bonfires; HUD hidden/restored; boss name shown (Stray Demon).
- Live RE oracles: read-only watchers diffing a structure while the human performs one action (focus switch,
  option toggle, ladder slide, lift ride, barrel break); each finding above marked "read live" came from one.
- Not verified: another machine, other resolutions / aspect ratios, DLC areas beyond spot checks, lighting an
  unlit bonfire (vs resting), shield/guard interplay when an enemy blocks a game-side hit, background audio.

## Gotchas

1. **Guest/native shared-memory sizes disagreed.** **Cause:** Java 256 bytes, C++ 128. **Fix:** one size
   constant, `static_assert`s.
2. **Menu kept the last player position.** **Fix:** `valid=0` outside a world under the pose seqlock.
3. **A stale fake-host binary gave wrong results.** **Fix:** rebuild and compare timestamps before trusting an oracle.
4. **A named mapping keeps its creator's size.** **Fix:** close both sides after a protocol change.
5. **Projection scanner crashed on the title screen (0xc0000005).** **Cause:** ReShade passes `UINT64_MAX`
   for whole-buffer updates. **Fix:** resolve to the buffer size, SEH-guard copies.
6. **Compositor drew nothing.** **Cause:** add-on `present` fires before `reshade_finish_effects`; counters
   were reset there. **Fix:** draw, then reset; log every skipped frame's reason.
7. **Game aborted (0xc0000409).** **Cause:** our own D3D11 calls re-enter our ReShade handlers; `std::mutex`
   relock throws. **Fix:** thread-local "compositing" flag, recursive mutex, try/catch that disables instead.
8. **The anchored block followed the camera.** **Cause:** look-alike view-projections near the origin.
   **Fix:** collect all candidates, reject ones far from the player.
9. **Jitter on mouse look.** **Cause:** stale cameras re-uploaded mid-frame. **Fix:** vote by the vertex-shader
   constant buffer bound at each main-depth draw.
10. **Objects pinned to camera height sank into floors.** **Fix:** anchor from the player's feet.
11. **Loads died silently.** **Cause:** hardware data breakpoints on game threads (protection).
    **Fix:** read-only memory diffing instead.
12. **Injected keyboard/XInput/messages did nothing without focus; faking focus leaked the mouse.**
    **Fix:** set the prompt manager's own latch byte (`FrpgEventActManImp+0x4E`).
13. **Twelve separate code patches in a row broke the hotkey/drive toggle.** **Cause:** each suspended all
    threads; the present thread stalled. **Fix:** batch all writes under one suspension; prefer detouring a
    small function's entry over many call sites.
14. **Friendly NPCs had no hitbox.** **Cause:** human NPCs are `PlayerIns`. **Fix:** accept PlayerIns except the local player.
15. **Respawn landed at a fixed spot (5, y, −20).** **Cause:** `WarpNextStage_Bonfire` wants a warp point,
    not a bonfire id. **Fix:** the game's own sequence `SetDefaultMapUid(-1)` + `WarpNextStageKick`.
16. **Rest detection missed bonfires.** **Cause:** sit animations differ per bonfire. **Fix:** menu state `[9]`.
17. **Ladder slide via the "roll" byte did nothing.** **Cause:** on a ladder the press is read as the
    backstep slot and needs two presses. **Fix:** inject index `0x0A` twice.
18. **Lift platforms did not move in Minecraft.** **Cause:** the ObjIns position stays at rest.
    **Fix:** use the rigid bodies' transforms.
19. **Doorways blocked.** **Cause:** layer-30 enemy-only walls included. **Fix:** keep layers 27/28/31 only.
20. **Raycast terrain missed moving platforms.** **Cause:** objects are on layers 17/18/20, which the
    walkable ray (layer 38) never hits. **Fix:** read object bodies directly.
21. **"HitIns +0xB0 bit 2 = disabled" was wrong** (252 of 254 parts had it). Verify flag guesses on a
    whole list before filtering by them.
22. **Hit row 10 knocked enemies away.** **Cause:** AtkParam damage level 5 ("blown away"), 100 poise
    damage. **Fix:** row 542 (level 1). Read the game's own paramdefs to compare rows by field name.
23. **Forcing FMOD to WASAPI did not restore background sound** (2026-10-12). Open; see Open questions.

## Assets

No game files, extracted assets or decompiled code in the project's repository; in-game screenshots and logs stay
in a gitignored `evidence/` folder. Minecraft-side visuals use vanilla assets from the player's own Minecraft, and the
terrain blocks are built on the player's machine from their own DSR install. Nothing from either game ships, and a
Minecraft world saved with that terrain stays private.

## Cost and time

About five days of sessions (2026-10-08 → 2026-10-12, ~70 commits): two agents in parallel — one
programming the add-on and the Fabric mod, one doing reverse engineering only and writing numbered findings
files that the other implemented and the human tested.

## Open questions

- Background audio: which output FMOD really uses after the patch, and whether something below the sound
  manager (master channel group, event category "master", mixer suspend) reacts to focus; baseline: is plain
  DSR silent when alt-tabbed?
- Lighting a new bonfire vs resting (prompt id, animation, banner, lit flag).
- Which AtkParam row hit the player (for Minecraft-shield blocking), lead: `DmgHitRecordManImp`.
- Other resolutions / aspect ratios; landmarks (fog walls, messages, item corpses) as special blocks.
