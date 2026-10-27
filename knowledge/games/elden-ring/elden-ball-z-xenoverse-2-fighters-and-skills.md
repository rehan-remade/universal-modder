---
kind: game
title: "Elden Ball Z: Dragon Ball Xenoverse 2 fighters, animations and skills in Elden Ring (native Rust DLL via ModEngine2)"
game: Elden Ring
games_also: ["Dragon Ball Xenoverse 2", "Dragon Ball Z: Kakarot"]
game_version: "Elden Ring 1.17.1 (exe 2.7.1.0, Steam build 25080141), Dragon Ball Xenoverse 2 (Steam, 2026-10 install with DLC CPKs), Dragon Ball Z: Kakarot (Steam, UE 4.21, pak v7), Windows 10 22H2"
platform: windows
engine: fromsoft
route: native-hook
tools: ["ModEngine2 2.1.0 (external_dlls)", "fromsoftware-rs (rev 6933967b, Ww2710 RVA table)", "hudhook (DX12 ImGui overlay, MinHook)", "glam", "Rust stable x86_64-pc-windows-msvc, crt-static", "XV2-Tools / Xv2CoreLib (LazyBone152, MIT) on .NET 10", "CUE4Parse + CUE4Parse-Conversion 1.2.2.202610 (Apache-2.0, EGame.GAME_UE4_21)"]
anti_cheat: "EasyAntiCheat: never touched. ModEngine2 starts eldenring.exe directly, without EAC, so the modded game runs offline and never goes online; online play only through the plain Steam launch, which loads nothing of the mod"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["Grolli"]
date: 2026-10-17
links: ["https://github.com/soulsmods/ModEngine2", "https://github.com/vswarte/fromsoftware-rs", "https://github.com/veeenu/hudhook", "https://github.com/LazyBone152/XV2-Tools", "https://github.com/FabianFG/CUE4Parse"]
tags: [mashup, asset-conversion, d3d12-overlay, imgui, cpu-skinning, retarget, animation-sampling, skills, bac, bsa, eepk, flight, hud, xinput-hook, unreal, cue4parse, cascade-particles]
---

# Elden Ball Z: Dragon Ball Xenoverse 2 fighters, animations and skills in Elden Ring

> Elden Ring played as Goku (and, in earlier versions, Vegeta, Gohan SSJ2, Ultra Instinct Goku) with the
> fighter's real Xenoverse 2 model, animations and skill set: Kamehameha and the other supers run from XV2's own
> BAC/BSA/BDM/EEPK data, a creator-made "Warp Kamehameha", an XV2-style skill palette, Kakarot-style flight and
> HUD. Since 0.5.0, when Dragon Ball Z: Kakarot is installed, Goku's model, animations (locomotion, flight,
> combos, Kamehameha) and skill particles come from the player's Kakarot paks instead, timed to the XV2 skill
> timelines. A native Rust DLL loaded by ModEngine2 draws everything over the game; .NET setup tools convert the
> player's own XV2 CPKs and Kakarot paks at install time, so nothing from any game is shipped. Only Elden Ring
> runs: the other two games are read from disk at setup time.
> Verified by an in-game test mode (10 self-checks) plus recorded runs reviewed frame by frame.

## Setup
- Elden Ring exe 2.7.1.0 = fromsoftware-rs `Ww2710` table. ModEngine2 2.1.0 (`modengine2_launcher -t er -c <toml>`,
  `external_dlls`). TOML paths must be single-quoted literals ('C:\...'), double quotes treat `\U` as an escape.
  ModEngine2 is discontinued; its README points to me3, its successor, which the CS2 and Sunless notes here use.
- **Offline only.** `modengine2_launcher` starts `Game/eldenring.exe` itself with `SteamAppId` set, not
  `start_protected_game.exe`, so EasyAntiCheat never loads and the game runs offline. The modded process never goes
  online: to play online, quit it and start the game from Steam, which loads nothing of the mod.
- **Saves.** ModEngine2 has no save-file option, so the modded game uses the normal `ER0000.sl2`. Back it up
  (`um backup create`) before the first modded launch, and don't take a save played with the mod online. me3's
  `savefile` option keeps a separate save.
- XV2: CPKs read in place with Xv2CoreLib's CPK_Reader (base + every `data*.cpk`, descending order so DLC wins).
  Xv2CoreLib needs its parent folder literally named `XV2 Tools` to build.
- Kakarot: `AT/Content/Paks` read in place with CUE4Parse (`DefaultFileProvider`, `EGame.GAME_UE4_21`); the pak
  index is not encrypted (footer: version 7, encrypted-index flag 0, zero key GUID), compression zlib.
  Goku = `AT/Content/Art/MDL/Cpl/Cpl001/Model/Cpl001p1c01s1` (338 bones, LOD1 20.5k tris), animations in
  `Art/ANM/cpl/C001A` (Goku) and `C000A` (shared), skill montages `Blueprints/Character/C001A/BTL/SKL/AM_*`
  (they name the sequences: Kamehameha = `C001A_S_SKL001_Bgn_01ST/02LP` then `Sht_01ST/02LP/03ED`), particles
  `Art/EFF/e/skill/a/Cpl001/Particles/PS_*` (Cascade) and `PS_skill_cmn_kidan_*` (Ki blast).
- Setup output: `%LOCALAPPDATA%\DBZRing\fighters\<CODE>.dbzm|.fx|.skills.json|.portrait.dds` + `ready.txt`
  (versioned marker, bump it whenever the export changes so existing installs re-run).

## Route and why
`native-hook` plus install-time conversion. It isn't a passthrough in the sense of
`knowledge/techniques/choosing-a-mashup-route.md`: XV2 and Kakarot never run, their files are converted once and
the DLL draws the result. The XV2 fighter is skinned on the CPU every frame and drawn as textured ImGui triangles
on the DX12 overlay, while the Tarnished's model is hidden (`ChrIns.chr_flags1c5.enable_render`) and keeps
providing physics, collision, hitboxes and ER's animation state. Rejected: converting to FLVER/TPF and swapping
the player model (needs bone-compatible rigs and per-armour parts; XV2 skeletons differ), and Sparking! ZERO
as the source (IoStore containers are encrypted, the key is behind SteamStub: not circumvented).

## How the game works (what we had to learn)
- Bone world matrices: `chr_model_ins +0x150 -> +0xb8 -> (+0x20 count u32, +0x28 3x4 rows, stride 48)`. Node names
  and parents in the same order: `chr_model_ins +0x10 -> +0x68 (flver data) -> +0x18 count, +0x20 array (0x30 each;
  UTF-16 name ptr +0x20, parent i16 +0x28)`; bind pose at flver data +0x70. Read the whole block with one
  readability check: a VirtualQuery per bone per frame stalled loading screens at 80%.
- Both games' character spaces face -Z with +X left: no axis conversion. XV2 stances float (fights are mid-air):
  snap the lowest Foot/Toe bone to its rest height every frame.
- Current animation: `time_act.anim_queue[read_idx]` (id, play_time, length). Useful ids: idle 0, move 20120/22100,
  roll 2020xx/2021xx, light combo `<weapon>0300n0`, guard 19000/19100, jump 6920xxxxx.
- UI states (CSMenuManImp.ui_states visible): gameplay [5,7,8]; loading 6 and 9; 19 is ALSO the "rest at grace"
  prompt in the world (don't treat it as a menu). Grace sitting:
  `lua_event_proxy.control_flags.bonfire_sitting_loop_active`.
- Hide ER's HP/FP/stamina: `CSFeManImp.hud_state = HideAll` (restore `Default`).
- Flight: `ChrInsFlags1c4.no_gravity`, write `physics.position` + `chr_proxy_pos_update_requested`. Make the mod's
  last written position authoritative (ER keeps a jump's upward push with gravity off). Collision rays:
  `CSPhysWorld::cast_ray` filter 0x2000058 = map collision only; 0x0 also sees objects (doors) and the player's own
  capsule (cast from outside it). Indoors (`block_id.is_overworld()` false) many roofs have no collision: cap
  altitude.
- Input: hook `XInputGetState` in xinput1_4.dll; remap only in gameplay, keep the raw state for the mod.
- XV2 skills: custom_skill.cus Skillset I_08..I_22 = super1-4, ult1-2, evasive, blast; names in
  `msg/proper_noun_skill_{spa,ult,esc,met}_name_<lang>.msg` keyed `_<ID2:D4>`. Real folder names come from the CPK
  file table (the owner code can differ: 1080_CMN_POW). Per skill: `_PLAYER.bcm` (first ButtonInput entry gives
  BacEntryPrimary/Airborne/Charge, KiRequired), `.bac` (Type0 anim, Type4 timescale, Type9 projectile with bone
  and frame, Type1 hitbox, Type2 movement, Type8 effect, Type15 fn4 take/give Ki), `.bsa` (I_22 lifetime, Expires =
  next entry, Type6 effects, Type3 hits), `_PLAYER.shot.bdm` (DamageAmount), `.eepk` (EMO models + PBIND
  particles).
  Shared data for Ki blasts: `data/skill/CMN/CMN.bsa`, `data/chara/CMN/CMN.bdm`, `data/vfx/cmn/BTL_CMN.eepk`.
  Effect textures are additive: brightness -> alpha when drawing with ImGui's alpha blend; tint by EMM MatCol2.

## Build steps
1. `dbzring-setup.exe --prepare --xv2 <XV2> --out %LOCALAPPDATA%\DBZRing\fighters --roster characters.json`.
2. `cargo build --release` (crt-static) -> dbzring.dll; ModEngine2 config with `external_dlls`.
3. Back up the save (see Setup), then launch with Steam running: `modengine2_launcher -t er -c config.toml`
   (offline, no EAC).

## Verification
In-game test mode (activated by a JSON file) presses Enter through menus, then checks in-world, fighters-ready,
fighter-drawn, hud-drawn, xv2-animation, ki-blast, super, flight, kakarot-hud, xv2-palette and appends pass/fail
lines; recorded 2-10 min runs were reviewed as contact sheets (caught: black void after flying through a door,
floating feet, HUD over loading tips). Kakarot conversion: offline renders of bind pose and sampled clips (preview
script) before any game run, then the same in-game test (10/10 pass with the Kakarot Goku, 8931 triangles drawn).
Not verified: the warp-behind-enemy (no enemy near the test grace), controller input on real pads (keyboard only),
EMA/EMP effect animations (static models and sprites for now).

## Gotchas
1. **Game exits 1-2 s after launch from the agent's shell.** Cause: the Claude desktop app runs as an MSIX package;
   its child processes get a redirected %LOCALAPPDATA% and can't reach Steam. Fix: start the launcher through
   `explorer.exe launch.bat`, keep dev files outside AppData, pass the data folder via an env var.
2. **Black screen after flying.** Cause: map-only rays don't see doors; flew into the unloaded void. Fix: also cast
   with filter 0x0 from outside the capsule; cap altitude indoors.
3. **Effects as black blobs filling the screen.** Cause: XV2 effects are additive and animated (EMA scale curves);
   drawn statically at full size. Fix: brightness as alpha, clamp radii, skip when the camera is inside.
4. **Ki blast invisible.** Cause: it lives in the common BSA/EEPK and is a particle (EMP), 10 cm base scale.
   Fix: export common data; draw particles as sprites with a minimum size.
5. **Fighter floats above the ground.** Cause: XV2 stances are airborne poses. Fix: foot snap per frame.
6. **Black waist flaps (Vegeta).** Cause: physics parts have no DYT entry. Fix: fall back to the parent part's DYT.
7. **Skill mods (.x2m).** Readable (zip: SKILL/NNNN_CCC_SSSS.* + x2m.xml); they can be mounted over the CPK view.
   An x2m is its creator's work and usually carries files derived from XV2's own: changing MOD_AUTHOR in x2m.xml
   doesn't change who made it. Don't ship one; ship only the tools that build skills from the player's own game
   data.
8. **DRAGON BALL Z KAKAROT is readable.** UE 4.21, pak v7, index not encrypted: CUE4Parse (GAME_UE4_21) loads
   meshes, animations and Cascade particles in place. Convert UE (x, y, z) cm to XV2 (x, z, -y) m, quats
   (x, z, -y, w); rename body bones to XV2 names so the same retarget sheet works. Use LOD1 (ImGui draws with
   16-bit indices).
9. **Kakarot animations left the arms in bind pose.** Cause: the animation skeleton spells bones with other case
   (Pelvis, UpperArm_L) than the mesh. Fix: match bone names case-insensitively (FName semantics).

## Assets
None generated: every model, texture, animation and effect is converted at setup time from the player's own
Xenoverse 2 and (since 0.5.0) Dragon Ball Z: Kakarot install; HUDs are drawn procedurally.

## Related and credits
- `cs2-conversion-of-elden-ring-offline-native-rust-dll-via-me3.md` (same folder) uses the same stack
  (fromsoftware-rs `Ww2710`, hudhook, a native Rust DLL) under me3, with its own D3D12 renderer for converted
  models.
- `porting-dark-souls-remastered-enemies-into-elden-ring.md` covers ModEngine2's limits (sound banks, no separate
  save) and the FLVER conversion route (a new character ID), which this note rejected for the player model.
- [ModEngine2](https://github.com/soulsmods/ModEngine2),
  [fromsoftware-rs](https://github.com/vswarte/fromsoftware-rs) (vswarte),
  [hudhook](https://github.com/veeenu/hudhook) (veeenu, MIT),
  [XV2-Tools / Xv2CoreLib](https://github.com/LazyBone152/XV2-Tools) (LazyBone152, MIT) and
  [CUE4Parse](https://github.com/FabianFG/CUE4Parse) (Apache-2.0).

## Open questions
- EMA (effect model animation) and EMP (particle) playback; camera events; victim reactions; melee rush skills.
- Kakarot assets: done in 0.5.0 (see Gotchas 8-9); per-emitter particle playback is still approximated.
- Public release: none is linked yet. Once one is public, link it in `links` and set `status: released`.
