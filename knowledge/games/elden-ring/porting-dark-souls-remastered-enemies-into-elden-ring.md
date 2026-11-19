---
kind: game
title: "Porting a Dark Souls Remastered enemy into Elden Ring as a new character (Hollow c2500 -> c7250): skeleton, animations, ragdoll, params, AI and sounds"
game: "Elden Ring"
games_also: ["Dark Souls Remastered"]
game_version: "Elden Ring 1.17.1 (exe 2.7.1.0), Steam, Windows 10 22H2; Dark Souls Remastered (Steam, loose files unpacked) as the source"
platform: windows
engine: fromsoft
route: data
tools: ["ModEngine 2 (2024-10 dev build; the 2.1.0.0 release does NOT load sound banks)", "WitchyBND (Paramdex, TAE/BND/TPF repack)", "HKLib.CLI (Havok 2018 tagfile <-> XML, read-only use for physics)", "soulstruct (Python, patched hk2018 writer)", "BinderKeys (ER archive keys/names)", "texconv", "vgmstream-cli r2117", "Wwise 2019.2.15.7667 Authoring (WwiseConsole, free licence)", "Python 3.13 (Blender's bundled interpreter) + numpy/scipy"]
anti_cheat: "EasyAntiCheat never touched: ModEngine 2 starts eldenring.exe without EAC, so the game runs offline; no Seamless/online use with these files"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-11
links: []
tags: [enemy-port, cross-game, new-character, havok, ragdoll, tae, behaviorparam, atkparam, npcparam, throwparam, ai-lua, wwise, soundbank, modengine2]
---

# Porting a Dark Souls Remastered enemy into Elden Ring as a new character (Hollow c2500 -> c7250)

> The basic DS1 Hollow (sword variant) now exists in Elden Ring as its own character ID c7250: its own DSR
> skeleton, model, textures and animations, its own stats, hitboxes, AI (DS1's AI script ported), hit reactions,
> parry/riposte/backstab reactions and its own DS1 sounds. Only the ragdoll bodies are borrowed (Wandering Noble
> c4300, resized). Everything is built from the user's own DSR and ER installs by local scripts and loaded with
> ModEngine 2; the user tested every step in game (about 30 tests for the body and behaviour, 16 for sound).

## Setup
- Elden Ring 1.17.1 / exe 2.7.1.0, regulation from that build. DSR from Steam with loose files (`chr\c2500.*`,
  `param\GameParam\GameParam.parambnd.dcx`, `script\m10_01_00_00.luabnd.dcx`, `sound\frpg_c2500.fsb/.fev`).
  The DSR enemy randomizer had edited the live luabnds/params: use its `.bak` files as vanilla.
- ER archives read with the BinderKeys RSA keys + name lists (Data0-3, DLC, and `sd\sd.bhd`/`sd_dlc02.bhd` for
  sound; sound paths are relative to `sd\`).
- ModEngine 2: one profile per experiment (`config_*.toml` + `.bat`), mod folder with `chr\`, `action\script\`,
  `map\mapstudio\`, `script\`, `sd\`, `regulation.bin`. **Use a 2024 development build** (see Gotcha 1).
  ModEngine 2 is discontinued; its README points to me3, its successor (see Gotcha 1).
- Saves: ModEngine 2 has no save-file option, so it loads the normal `ER0000.sl2`. Back it up (`um backup`)
  before the first modded launch, and don't take a save used with these files online. me3's `savefile` option
  keeps a separate save.
- Wwise 2019.2.15 Authoring installed through the Audiokinetic Launcher (Authoring + Windows platform, no
  plug-ins); only `WwiseConsole.exe` is used, headless.

## Route and why
`data`: every change is a file the game already knows how to load (chr binders, TAE, behaviour, params, MSB, AI
Lua, sound bank). A first pass replaced the Wandering Noble's files (retargeting the Hollow onto the Noble
skeleton) to learn each format; the real port then gave the Hollow its own chr ID so it can coexist with every
vanilla enemy (goal: placing DS1 enemies with an Elden Ring enemy randomizer). No DLL needed.

ID scheme used: ER chr = 7000 + DS1 chr / 10 (c2500 -> c7250, Black Knight c2790 -> c7279), NpcParam/think
72500000, behaviour variation 72500, AtkParam_Npc 7250000 + judge, AI battle goal 725000, sound IDs 7250xxxxx.

## How the game works (what we had to learn)
**Character files for a new ID** (`chr\c7250.*`): chrbnd (FLVER + ragdoll HKX), anibnd (skeleton + TAE),
div00-02 anibnds (spline-compressed animations referencing the div's `.compendium`), behbnd (shared c9997
graph + character data), `_h`/`_l` texbnds, `action\script\c7250.hks`. Every string inside the behbnd that names
the old ID (project, character, skeleton path, hks name, clip paths) must be renamed. No ChrModelParam row is
needed.

**Skeleton and animations.** DSR uses Havok 2015, ER Havok 2018. A DSR skeleton can be used natively if the 6 ER
foot-IK target bones (`L/R_Foot_Target2/1/Target`, indices 1-6) are added and every animation moves that chain
onto the feet each frame (ER's leg IK pulls the feet to them). Animations: degree-1 splines, one control point
per frame, TCRF-referenced to the div's compendium; the slot list is the template enemy's (animation IDs come
from the shared behaviour graph's `CustomManualSelectorGenerator.animId`, e.g. 8030-8057 damage, 10000/10001
death/death idle, 11000/11001/11002 thrown, 5000-5003 battle turns, 2100 run).

**Matching DS1 clips to ER slots without names.** Profile each clip (duration, root motion incl. yaw, pelvis/head
height start->end) and read the DS1 TAE: DS1 JumpTable IDs and ER FlagTypes are the same numbers (5 hit, 23 AI
combo window, 78/79/86 cancel windows), and DS1 TAE spEffects name states (DSR SpEffectParam 30 "parry-broken
(throwable)" marks the parried clip, 35 "throws disabled" marks knock-downs). ER's ThrowDef 11000/11010 have
exactly DS1 2500/2510's durations, so backstab/riposte sync carries over.

**TAE.** For each slot that now plays a DS1 clip, the template's events are time-scaled by
DS1-duration / template-duration; attack slots get DS1's hit windows (type 1, behaviour judge = DS1 judge), and
DS1's own 23/78/79/86 windows replace the template's (combos chain at DS1 timing).

**Params** (regulation.bin): NpcParam (HP, poise = `superArmorDurability`, runes, capsule, behaviourVariationId,
model masks, `SoundBankId`/`SoundAddBankId`), BehaviorParam `(200000 + variation) * 1000 + judge` -> AtkParam_Npc
(DS1 damage, `dmgLevel` = DS1 ImpactLevel, hit capsules on DS1 dummy IDs, which the native FLVER keeps),
NpcThinkParam (`battleGoalID`), ThrowParam (rows keyed by **DefChrId** = the defender's model ID).
Paramdex defs work if you take the latest layout (skip `RemovedVersion` fields) and let bitfields share a unit
across same-size types (u8 and dummy8).

**AI.** ER AI scripts are Lua 5.0 bytecode in luabnds, but ER also loads plain-text Lua there. DS1 AI scripts are
Lua 5.0 too and keep local names, so the DS1 Hollow script disassembles readably. ER still has the same helpers
and goals (`Approach_Act`, `GOAL_COMMON_Attack/ComboAttack/ComboRepeat/ComboFinal`, `Damaged_Step`,
`MissSwing_Attack`, `DIST_Middle`, SpinStep 701/702). The port is a hand-written table goal in ER style with
DS1's odds/distances, the goal ID constant defined in the file itself, packed as `script\725000_battle.luabnd.dcx`
(the vanilla luabnd layout; `.luagnl` = u64 offsets, 0, UTF-16 global names, 16-byte padding). The template's
logic script reads `battleGoalID` from NpcThinkParam, so only the battle script is new.

**Ragdoll.** Borrowing another enemy's hknp ragdoll works if the anim<->ragdoll mappers and the anim skeleton in
the ragdoll file are rewritten **in place in FromSoft's bytes** (Gotcha 2), and the bodies are refitted
(Gotcha 6).

**Sound (Wwise 2019.2, bank v135).** A character's TAE sound event (SoundType 1, ID n) posts the Wwise event
`Play_c<n>` (FNV-1 32-bit of the lower-case name; names are not stored in banks). Chain: Event -> Play action
(0x0403, target + bank ID = FNV of the bank name) -> random container -> Sounds -> embedded WEMs (DIDX/DATA,
16-byte aligned), under an actor-mixer whose top ancestor routes to a bus in `Init.bnk`. Each character loads
`sd\cs_c<SoundBankId>.bnk` (+ an additional `sd\enus\cs_c<SoundAddBankId>.bnk`). Every shipped ER WEM sampled
(520) is Wwise Vorbis. We cloned the template enemy's own chain (event/action/container/sounds), re-parented it
to a clone of its *top-level* mixer, and added the Hollow's sounds to a loose copy of that enemy's bank.

## Build steps
1. Extract the needed ER files (chr, behbnd, MSB tile, regulation, the template's luabnds and sound bank) and the
   DSR files; keep vanilla copies for round-trip checks.
2. Skeleton: DSR skeleton + 6 ER foot-IK target bones. Animations: decode each DSR clip, add the target chain,
   encode as degree-1 splines with TCRF to the template div compendium, one file per template slot.
3. FLVER: DSR meshes on DSR bones + target bones + one root "part" bone the meshes anchor to; write per-bone AABBs
   and the oriented mesh boxes yourself (Gotcha 3); add the template's dummy points the DS1 model lacks
   (sound/ground/trace points) re-placed on matching bones.
4. Ragdoll: copy the template's physics HKX bytes, patch the anim skeleton and both mappers in place, resize
   joint pivots and capsules (Gotchas 2, 6).
5. TAE (WitchyBND XML): re-time the template's events per slot, insert DS1 hits/windows/sounds; repack.
6. Package: rename every internal ID string (behbnd, binder names); repack with WitchyBND.
7. Params: add rows (NpcParam, BehaviorParam, AtkParam_Npc, NpcThinkParam, ThrowParam) with a byte-exact PARAM
   writer, then replace only those entries inside regulation.bin (decrypt, ZSTD, patch BND4 headers, re-encrypt;
   check the other entries stay byte-identical).
8. AI: plain-text battle Lua packed as a luabnd; NpcThinkParam row pointing at its goal ID.
9. Map: patch one MSB enemy part in place (model name/sib, NpcParam, think) to place the enemy.
10. Sound: vgmstream decodes the DSR FSB4 to WAV; WwiseConsole `convert-external-source` (minimal new project,
    ShareSet "Vorbis Auto Detect High") makes WEMs; append Event/Action/Container/Sound objects + WEMs to a loose
    copy of the template's bank; set the new containers' props to neutral (Gotcha 15); NpcParam SoundBankId/
    SoundAddBankId = the template's existing banks.

## Verification
- Byte-level oracles before every in-game test: PARAM writer and Wwise bank parser reproduce the vanilla files
  byte for byte; regulation rebuild keeps all untouched entries identical; HKLib reads the raw-patched ragdoll and
  every patched value equals the intended one (joint pivot gap 0.000 mm at rest); animations decode back to the
  input within tolerance; TAE repack re-unpacked and compared; vgmstream decodes every new WEM from the bank.
- In game (the human played each build): spawn without crash, LOD/visibility at all angles, walk/run/turn, all
  DS1 attacks incl. leaps from range and the flurry, hits landing with DS1 damage, distinct light/heavy staggers,
  parry -> riposte, backstab, guard bounce (DS1 a00_3500), death, and every DS1 sound at DS1 volume/pitch.
- Not verified: other DS1 Hollow variants (torch, bow), the dying ragdoll's looks (still stretches on the floor;
  accepted for now), multiplayer (never used), whether a character's *own* new bank (`cs_c7250.bnk`) loads with
  the newer ModEngine (see Open questions).

## Gotchas
1. **Custom sounds silent for 15 tests, whatever we changed.** **Cause:** the ModEngine 2 release (2.1.0.0,
   modengine2.dll of 2023-08-31) does not load loose sound banks; the game kept using its own banks. Found via the
   soulsmodding.com "Elden Ring Soundbank Editing" guide, which requires a "Mod Engine 2 artifact" build. The
   Wwise hook that serves loose `.bnk` files arrived later (ModEngine2 PR #166, merged 2024-01-13), and no
   release followed it. **Fix:** a 2024 ModEngine 2 development build (we used the one shipped with the
   Convergence mod, dll dated 2024-10-18). me3, ModEngine 2's successor, has had Wwise overrides for ER since
   mid-2025 (me3 PR #128; `sd`, `sd/enus` and `sd/ja` paths); this port wasn't tested with it. A test that posts
   a *stock* event from the vanilla bank cannot tell you whether your bank loaded.
2. **Any HKX physics file re-serialised by HKLib crashes ER** (even an unmodified round trip, with type hashes
   restored). Behaviour HKX round-trips fine. **Fix:** edit FromSoft's original physics bytes in place: in a
   2018 tagfile, arrays and strings are a u32 item index in the owner and the ITEM table holds (type|flags, DATA
   offset, count), so arrays can be shrunk (overwrite + lower the count) and names written into existing string
   items. Keep the file size identical.
3. **New model invisible at some angles / stuck on low LOD.** **Cause:** the FLVER writer we used wrote empty
   per-bone bounding boxes; ER also wants the mesh box as an oriented box (half extents, XYZ rotation, centre) and
   each mesh anchored to a "part" bone (usage flag 4). **Fix:** write per-bone AABBs in bone bind space (all
   weight slots) and the oriented mesh boxes; anchor meshes to a root part bone; low-res textures named `<name>_l`.
4. **Crash when approaching the new character.** **Cause:** strings inside the behbnd still named the template
   ID. **Fix:** rename every internal reference (the Convergence mod's new enemies were the reference).
5. **Stiff, straight legs.** **Cause:** ER's leg IK pulls the feet to the Foot_Target chain, which the DS1 clips
   don't animate. **Fix:** move the target chain onto the feet every frame when building each clip.
6. **Dead body's limbs stretch apart.** **Cause:** the borrowed ragdoll's joint pivots are spaced for a larger body
   (forearm 0.39 m vs 0.26 m); once limp, the constraints pull the Hollow's bones to those spacings. **Fix:** move
   each parent-side pivot to where the child pivot sits on the new body; scale capsules per axis. (It still
   stretches somewhat once fully collapsed; deferred.)
7. **No hit reactions / stands still before dying.** **Cause:** damage and death slots still held a placeholder.
   **Fix:** map DS1 damage/death clips into the 8030-8191, 8500, 10000+ slots; a death idle = the clip's last
   pose held.
8. **No leaps or flurry, stops at mid range.** **Cause:** the template enemy's AI only requests its own few
   attacks; turn slots were placeholders. **Fix:** port the DS1 AI (above) and map DS1 turns/run/steps.
9. **Parry played a knock-down.** **Fix:** use the clip whose DS1 TAE applies spEffect 30 (DS1 Hollow: 2100).
10. **No backstab or riposte possible.** **Cause:** ThrowParam rows are keyed by DefChrId (defender model).
    **Fix:** copy the template's rows with DefChrId = the new model ID.
11. **Guard bounce turned the enemy 90 degrees.** **Cause:** DS1 2050/2051 rotate the root. **Fix:** the
    Hollow's real bounce clip is a00_3500 (found by the user in DS Anim Studio).
12. **regulation.bin repack fails silently with WitchyBND; soulstruct's binder doesn't round-trip it.** **Fix:**
    surgical BND4 edit: append the new .param, repoint its file header, recompress with the original DCX header.
13. **PARAM writer output differs from the game's.** **Cause:** rows with identical names share one string.
    **Fix:** de-duplicate names on write.
14. **We guessed what template sound IDs were and were wrong** (430001000 is a 0.15 s clank, not a swing). **Fix:**
    decode every WEM of the bank and hash candidate names `Play_c<chr><xx><yyy>` to list each event's clips,
    length and loudness before using one as a test sound.
15. **Ported sounds far too quiet and pitched down.** **Cause:** the cloned container carried the template's props
    (Volume -21 dB, Pitch -280 cents, random pitch +-100). **Fix:** after the parent id, the container holds a
    u8 bit vector, a prop bundle (u8 n, ids, f32 values; 0 Volume, 2 Pitch) and a ranged bundle; set them neutral.
16. **Cloned actor-mixer pointed at a parent that only exists in the template's bank.** **Fix:** clone the
    template's *top-level* mixer (parent 0, its output bus lives in Init.bnk). (Found while the bank wasn't loading
    at all; correct by Wwise's hierarchy rules but not isolated in game.)
17. **Wwise 2026 vs 2019.** Same Vorbis audio for every file; 2022+ adds a 16-byte `hash` RIFF chunk (we strip
    it). The u32 at fmt+0x3C varies with sample rate/setup; it is not an encoder version. "Auto Detect" lowers
    sample rates and trims silent tails.

## Assets
All art, animation and audio come from the user's own DSR install, converted at build time and kept local:
DDS textures via texconv (BC7 albedo/normal + quarter-size `_l` copies), sounds via vgmstream + WwiseConsole. No
generated assets.

## Cost and time
Four days (2026-10-08 to 10-11); about 30 in-game tests for the body, behaviour and params, 16 for sound (most
of the sound tests were spent on Gotcha 1).

## Credits
Built on community tools and knowledge: WitchyBND and its Paramdex / TAE templates (params, binders, TAE XML),
HKLib (Havok 2018 tagfiles), soulstruct (FLVER / HKX / DSR params), BinderKeys (ER archive keys and names),
DS Anim Studio (the user identified the bounce clip with it), vgmstream (FSB4 / WEM decoding), Audiokinetic Wwise
Authoring (Vorbis encoding), the soulsmodding.com tutorial index and its "Elden Ring Soundbank Editing" guide (the
ModEngine 2 artifact requirement), the Convergence mod (a reference for new character IDs and a working newer
ModEngine 2 build), and ModEngine 2.

## Open questions
- With the 2024 ModEngine build (or me3), does a new character's *own* bank (`sd\cs_c7250.bnk`, SoundBankId
  -1) load? If so, each ported enemy can ship its own bank instead of editing a template's. Our earlier
  conclusions that "missing banks silence a character" and "ER won't play PCM WEMs" were made with the old
  ModEngine and are unproven.
- Port DS1's common swing sound (it lives in DSR's shared bank, not the enemy's).
- Torch/bow Hollow variants (separate animation sets and AI), the dying ragdoll, then randomizer integration
  and more DS1 enemies (Black Knight c2790 -> c7279).
