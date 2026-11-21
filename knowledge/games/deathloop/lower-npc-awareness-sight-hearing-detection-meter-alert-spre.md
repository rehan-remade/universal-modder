---
kind: game
title: Lower NPC awareness (sight, hearing, detection meter, alert spreading) as an ASI plugin with a live Cheat Engine table
game: DEATHLOOP
games_also: []
game_version: Steam 1252330, build 22517541, game version 1.820.5.1, Deathloop.exe PE timestamp 0x69b028fb
platform: windows
engine: idtech
route: native-hook
tools: [Ultimate ASI Loader, Cheat Engine, Python pefile, Python capstone, Python ctypes, C (MSVC or MinGW)]
anti_cheat: none for single-player; the exe is Denuvo-wrapped (not touched, see Setup)
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-21'
links:
- https://github.com/Pacifier89/deathloop-npc-awareness
- https://github.com/ThirteenAG/Ultimate-ASI-Loader
- https://github.com/cheat-engine/cheat-engine
tags: [deathloop, void-engine, arkane, stealth, ai-perception, npc-awareness, asi-plugin, cheat-engine, oodle, decl]
---
# Lower NPC awareness (sight, hearing, detection meter, alert spreading) as an ASI plugin with a live Cheat Engine table

> DEATHLOOP has no option for how sharp the NPCs are. This mod lowers human NPC sight (distance and cone width
> per alert state), hearing radii per sound type, the speed of the detection meter, the distance at which you
> are spotted instantly, and how far an alert spreads (NPC shouts for help, crew join range). It is a small ASI
> plugin (`dl_awareness.asi` + `.ini`) that finds the AI decl objects in memory and rewrites them once the game has
> finished loading them, plus a Cheat Engine table for tuning a live block exported by the plugin while you play.
> No game file and no exe byte is changed. The user played with it and verified each part in game, except the
> radio carrier broadcast range, which was never found.

## Setup
- DEATHLOOP on Steam (app 1252330), build 22517541, version 1.820.5.1, Windows 10 22H2 x64.
- `Deathloop.exe`: 510 MB, PE timestamp 0x69b028fb, Denuvo-wrapped, **ASLR on**: every address below is an RVA
  (`Deathloop.exe+RVA`). `.text` is plain readable code on disk, so static analysis with pefile/capstone works
  without a memory dump. The exe was never patched (Denuvo integrity, and the user's rule).
- Loader: Ultimate ASI Loader as `winmm.dll` in the game root (the game imports both `winmm.dll` and
  `dinput8.dll`; either proxy name loads `.asi` files). A 3.x x64 build copied from a Dishonored 2 install worked.
- Play single-player / offline (the game's Play Mode option), so nobody else's invasion session is affected.

## Route and why
- **Data edit of the decl container (tried, abandoned).** Gameplay decls live in `base\rsc_decl_0.resources`. Hearing
  floats patched in place loaded fine, but the edited vision decl doesn't fit its compressed slot, and appending
  it at the end of the container with an updated index entry crashed on level load (Gotcha 2). Also, a game
  update would overwrite the files.
- **Exe patch:** rejected (Denuvo, ASLR, user rule).
- **Chosen: ASI plugin that edits the decl objects in memory after they load**, plus an exported live struct the
  CE table writes to. It survives ASLR (finds objects by RTTI vtable RVA) and needs no game-file changes.

## How the game works (what we had to learn)
- **Engine:** Arkane's Void engine (idTech lineage, same family as Dishonored 2), but packaged differently:
  - `base\master.index` lists 112 container names; `base\master_resources.index` (`\x05SER`, BE u32 count at 0x20,
    323629 entries) holds **little-endian** entries: u32 id, three length-prefixed strings (type, name, path),
    u64 offset, u32 size, u32 zsize, 14-byte tail (container = BE u16 at tail+11). Dishonored 2 differs: big-endian,
    10-byte tail, per-container indexes.
  - Compression is **Oodle, not zlib**: `OOD\0`, u32 8, u32 raw size, then a Kraken stream. Decompress with the
    game's own `oo2core_8_win64.dll` (`OodleLZ_Decompress`). Kraken level 6 recompresses the vanilla vision decl
    byte for byte.
  - Materials and renderprogs are text decls; **gameplay decls are binary**: `{ edit = ` u32 count, then records
    `[u8 class level][u32 field index][raw value]`. Field indices count from 0 per level of the inheritance chain.
    Floats are 4 raw bytes, enums are an 8-byte hash + length-prefixed string, decl refs are 8-byte hashes (hash
    function not identified).
- **Reflection:** field names are registered by static-init code (`lea name / mov [rip], offset / size / type id`),
  so field names and offsets can be listed by scanning `.text` for that pattern.
- **Objects the plugin edits** (vtable RVAs for build 22517541; decl objects keep the decl name as `char*` at +8):
  - `arkDeclGameSoundProperties` (vt 0x25e7930), decls `npc/aisoundproperties/*`: hearing radius in metres, float at
    +0x60. Vanilla: gunshot 35, big calibre 50, muffled 15, NPC gunshot 20, run 11, sprint 14, hard landing 10,
    clear impact 15, breakage 15, combat_rally 16, search_rally 16.
  - `arkDeclCpntAIVisionConfig` (vt 0x265eec0), decl `npc/base/npc/cpnt/aivisionconfig_human` (the only human one):
    `[+0x80]` -> slot, `[slot+0x28]` = context array, `[slot+0x34]` = 4 contexts (Patrol, Search, Combat, Midnight).
    Context = 0x30 bytes: +0 name, +8 inner frustum, +0x1c outer frustum. Frustum = horFOV, vertUp, vertDown,
    maxViewDist (+0xc), focusedViewDist (+0x10). Vanilla inner sight: Patrol 32 m, Search 32 m, Combat 76 m,
    Midnight 15 m.
  - Per-NPC `arkCpntAIVisionConfig` (vt 0x265f018) keeps its **own copies** of the frustums (+0x80 / +0x90 lists).
    On each context change (RVA 0xfe3a80) it copies the decl's cones and multiplies distances and angles by the
    NPC attributes NPC_VISION_CONE_DISTANCE_FACTOR (0xb0) and _ANGLE_FACTOR (0xaf).
  - `arkDeclCpntAISensor_Vision` (vt 0x2716630), PlayerVisibilitySettings: playerMaxProximityDistance 8 (+0x40),
    **playerInstantDetectionDistance 4 (+0x44)**, visibilityMultiplyFinalResult 1 (+0x48, does NOT drive the meter).
  - **Detection meter speed = player attributes** `PLAYER_VISIBILITY_FACTOR` (0xe3) and
    `PLAYER_VISIBILITY_WHEN_MOVING_FACTOR` (0xe4) in the player's `arkCpntAttributes` (vt 0x26d4ea0):
    `[+0xb0]` array of 0x2c-byte entries (+0 id, +4 base, +8 min, +0xc max = 5, +0x24/+0x28 current). The player's
    component is the one with ~920 entries. Setting base and current 1.0 -> 0.25 made the meter fill clearly slower.
  - Alert spreading: NPC shouts are just sounds (`combat_rally`, `search_rally`, `_vs_player`, `_vs_npc`), so their
    hearing radii control who comes running. `arkDeclCpntAICrewCollector_Combat` (vt 0x271bc30, empty decl = code
    defaults) has floats 15 (+0x88) and 100 (+0x9c) that act like a crew join range (scaling them down helped).
  - `arkDeclCpntAIReasoner_CrossAlert` (vt 0x2702a70, the radio backup call): list of 0x3c-byte mode settings,
    +8 maxStressLevel (50/100), +0x18 collectRadius 20 m. Setting it to 0 did not stop mass alerts.
- **Load timeline:** 24 sound decls load about 30 s after start at the first main menu; the rest and the vision
  decl load with the level. While being parsed, values read -1 for a few seconds (Gotcha 3).
- **Save format (bonus finding):** the user's own exporter turns `save.dloop` into JSON. `commonState.Arsenals[]`
  per character (Colt = `arkPlayerCharacters_t@@1`); `items[]` with id = (character << 16) | counter, `itemId` =
  a u16 key into a runtime hash table of item decls (the save loader at RVA 0x13a1520 looks it up), type 1 trinket,
  2 weapon, 3 slab, 4 outfit, `entitlementId` = DLC bundle. Adding owned items round-trips byte-exact; DLC items
  were left out unless already owned.

## Build steps
Source, ini and CE table: [Pacifier89/deathloop-npc-awareness](https://github.com/Pacifier89/deathloop-npc-awareness) (build with `gcc -shared -O2 -s -o dl_awareness.asi dl_awareness.c`).

1. Install Ultimate ASI Loader x64 as `winmm.dll` in the game root.
2. Build the plugin (a single C file, no dependencies) as `dl_awareness.asi`; put it and `dl_awareness.ini` in the
   game root.
3. The plugin starts a thread that every 100 ms scans private RW memory for the vtables above, waits until each
   value is loaded and stable, saves the vanilla value, then writes vanilla x ini factor (or the ini metres).
   For vision it also rewrites NPCs' existing frustum copies by matching the old 20-byte cone.
4. It exports a live struct (`dl_live`, magic `DLAWARE6`, module offset 0x6040 in this build) with every setting
   and a `save_to_ini` flag; the CE table edits `"dl_awareness.asi"+offset` and the plugin re-applies within 250 ms.
5. The plugin writes `dl_awareness.log` listing what it found and changed.

## Verification
- Oracle: the user playing (sight, hearing, meter, alert spreading tested one at a time with extreme values,
  e.g. Patrol sight 0.3 and gunshot radius 0.5 m, then their own tuning), plus the plugin log and an RPM probe
  confirming the values in the decls and in all 21 NPC cone copies after a map load.
- Verified: sight per alert state, hearing per sound, meter speed (still and moving), NPC shout radii, crew join range.
- NOT verified / not found: radio carriers' broadcast range; field names of the crew collector floats;
  whether the plugin works on later builds (vtable RVAs and the live block offset will move).

## Gotchas
1. **Editing the vision decl in memory had no visible effect.** **Cause:** each NPC copies the cones on spawn and
   on alert state change. **Fix:** apply before the level loads, and also rewrite the per-NPC copies.
2. **Game crashed loading the level after a data-file edit.** **Cause:** the edited vision decl was appended raw at
   the end of `rsc_decl_0` with a new index offset/size; only in-place edits of the same size load.
   **Fix:** don't relocate entries (or use the plugin route).
3. **Plugin v1 crashed on map load.** **Cause:** it wrote into half-parsed decls (placeholder -1, clamped to 0.5).
   **Fix:** wait until a value is > 0 and unchanged across several polls before writing.
4. **Live-writing extreme values (all radii 0, sight 0.1 m) into a paused, running level crashed after unpausing.**
   **Fix:** clamp (minimum 0.5 m, multipliers x0.01) and apply moderate values; same values loaded fresh were fine.
5. **Vision layout read one level too shallow.** `[decl+0x80]` points to a slot, not to the contexts; the contexts
   are at `[slot+0x28]`. v2 read them directly and never applied.
6. **visibilityMultiplyFinalResult does nothing for the meter.** The meter is driven by the player attributes 0xe3/0xe4.
7. **The plugin's live block moved** (0x5040 -> 0x6040) when the C struct grew; regenerate the CE table after each build.
8. **Don't name a helper script `dis.py`** next to capstone code: it shadows a stdlib module capstone imports.

## Assets
None.

## Cost and time
One long session (2026-11-18), six plugin versions, each tested by the user in game.

## Open questions
- Radio carrier broadcast: arkDeclCpntAICrossAlert (vt 0x271f570) holds floats 1, 3 and 4 but no obvious radius.
- Names of the crew collector fields (no static lea refs found).
- Per-weapon sound mapping: weapon decls reference aisounds by hash, so which radius a given gun uses was assumed.
