---
kind: game
title: Nuzlocke, in-game randomizer and QoL items via a TPDPHook-Extended fork
game: Touhou Puppet Dance Performance Shard of Dreams
games_also: ["幻想人形演舞-ユメノカケラ-", "TPDP SoD Extended"]
game_version: "SoD 1.103 + Shard of Dreams Extended V4 (SoD_Extended_Setup_V4.exe, data Sep 2022, dxgi.dll Aug 2022) + English translation patch; FocasLens' own release (not on Steam), with the base game installed"
platform: windows
engine: native
route: native-hook
tools: ["TPDPHook-Extended (php42) @ac012c3 forked", "TPDP-Dev-Tools 1.4.1 (php42)", "tpdp-randomizer 1.3.0 (php42, GPLv3)", "MSVC 14.44 / VS2022 BuildTools CMake (Win32)", "Python pefile + capstone", "innoextract 1.9", "ILSpy"]
anti_cheat: "none. The game has optional netplay (Extended V4 points it at its own community server); everything here is offline single-player, the network code was not touched, and fork saves stay out of netplay"
status: working
agents:
- Claude Code (Opus 5.5)
humans: ["SophiaUrabe"]
date: '2026-11-15'
links: ["https://github.com/php42/TPDPHook-Extended", "https://github.com/php42/TPDP-Dev-Tools", "https://github.com/php42/tpdp-randomizer", "http://fo-lens.net/enbu_ap/"]
tags: [touhou, focaslens, dxlib, x86, dxgi-proxy, nuzlocke, randomizer, event-script, save-format]
---
# Nuzlocke, in-game randomizer and QoL items via a TPDPHook-Extended fork

For Touhou Puppet Dance Performance: Shard of Dreams with the fan "Extended" V4 patch, we forked php42's
TPDPHook-Extended (the `dxgi.dll` proxy that Extended already ships) and added:
- a full Nuzlocke/Nuzlight ruleset;
- an in-game randomizer (php42's tpdp-randomizer core, re-run per save from a seed, with no game files changed);
- new key items: a post-battle full heal and an infinite capture thread;
- type-effectiveness arrows in battle, a level-cap/faint counter on the profile screen, and free PP respec.

New content (a mode-choice NPC conversation, a new options row) is served through a loose-file override layer
added to the hook. Every feature except the PP respec was tested in game by the human player (2026-11-08 to
2026-11-11).

## Setup
- Base install: SoD + Extended V4 + the English translation patch. Extended's own launcher is
  `SoD-Extended-EN.exe` (32-bit, DirectX 9, DxLib). The vanilla exe makes TPDPHook.log complain.
  - SoD is an add-on disc: FocasLens' SoD page says it won't run unless the base game, Touhou Puppet Dance
    Performance (幻想人形演舞, 2014), is installed. The game finds it through `InstallPath` in
    `%APPDATA%\FocasLens\幻想人形演舞\gn_enbu.ini`. Both are sold as downloads on DLsite (RJ179146 and RJ179149).
  - SoD -Extended- is Barudo's mod (a concept of Hanabi's, finished with a small team). The English translation
    patch is the community patch the TPDP wiki (tpdp.miraheze.org) announced in 2018.
  - **Netplay:** direct battles and Random Battle matchmaking (which Extended V4 points at its own community
    server through TPDPHook's `[network]` settings) are always against other people. This fork changes puppets,
    items and rules, so keep it offline: don't take a fork save into netplay or the PvP hub.
- Extended setups are Inno Setup 6.1; `innoextract` 1.9 unpacks them. Both setups contain a file called
  `patch.bin`: pre-create `tmp/patch.bin#patch/` and pass `--collisions=rename`.
  - `patch.bin` is a TPDP-Dev-Tools `diffgen` zip, applied with `diffgen -i <game> -o <patch> -p`.
  - The exe is identical between the 2022 ("v3") and V4 setups; the `dxgi.dll` and data differ.
- Hook source: TPDPHook-Extended HEAD (2025-09, @ac012c3) matches the **V4** dll's ini keys, not the 2021 one.
- Build: VS2022 BuildTools (MSVC 14.44), using the CMake bundled with BuildTools (not on PATH):
  `cmake -A Win32 -B build -S .` then `cmake --build build --config Release --target TPDPHook` gives `build/Release/dxgi.dll`.
- Saves: `save\enbu_ap.sav`. Logs: `TPDPHook.log`; `logging = trace` under `[general]` is the most detailed level
  (upstream already has it).

## Route and why
- **Native hook in the existing proxy DLL.** Extended already loads TPDPHook as `dxgi.dll`, and its source has
  hook helpers, game structs (`tpdp_data.h`) and an ini system. Forking it means no extra loader.
- **Rejected:** repacking archives with TPDP-Dev-Tools for every run. Randomizing per save and keeping the game
  folder untouched both need runtime serving of data.
- **Licensing:** linking php42's GPLv3 randomizer code makes the fork GPLv3 if published.

## How the game works (what we had to learn)
RVAs are for the V4 `SoD-Extended-EN.exe`. **The exe is ASLR-relocated** (we saw base 0x310000), so absolute
addresses baked into code bytes differ from the file. Compute them from the RVA at runtime.

**Data and files**
- Data lives in `dat\gn_dat1..6.arc` (encrypted; TPDP-Dev-Tools extracts them).
- All reads go through DxLib's `FileRead_*` functions:
  - open 0x1b69e0, size 0x1b3800, read 0x1b3c00, gets 0x1b3d00, eof 0x1b3c20, close 0x1dd200;
  - `fullyLoad` 0x1b6c50, `getImage` 0x1b40b0, `scanf` 0x1b6de0;
  - images: `LoadGraph` 0x1d5e90, `LoadDivGraph` 0x1d61e0;
  - map files go through an async queue (0x1b2570 / 0x1b2320).
- **Archives beat loose folders.** To override a file you must wrap those calls yourself; dropping loose files
  next to the archive does nothing.
- **Puppet and skill tables are filled by a static initializer before any hook runs** (puppet table RVA 0x8f20e8,
  512 × 497 bytes). Serving a randomized `DollData.dbs` later only reaches local re-reads. The fix: copy the
  randomized records into the live tables on the first frame.
  - The type chart (doubles at 0x6f9ab20, index atk*18+def) is lazy-loaded; clear bit 1 of 0x6f9b5d4 to force a reload.
  - The game also reads the base game's DollData, through `InstallPath` (see Setup), for a legitimacy check
    (0x17e560).
- Items are parallel arrays (name/desc std::string stride 0x1c at 0x8a50c0/0x8ac0c0, price 0x8b30c0,
  genre 0x8b40c0, ...).
  - Bag counts: u8[1024] at 0xd7bb45. add 0x17c280, remove 0x17c380.
  - **Bag tabs list items by ID range** (u16 lo/hi tables at 0x42e640/0x42e650: Heal 65-128, capture 513-576,
    Key 577-640), not by the genre byte. New items need an ID inside the right range.
  - The battle/field flags in ItemData are loaded but never read; usability is hard-coded by ID.
- Unused V4 placeholder IDs work as new items defined purely in memory (we used 80, 81, 535, 586).

**Saves**
- `enbu_ap.sav`: magic 幻想人形演舞AP, header 0xB8, payload 0x5BE33, 51 boxes.
- Checksum and scramble index arithmetic are **uint32 and wrap**. Ports to Python must mask, or they fail silently.
- Puppet records (0x9f bytes in the party, 149 in boxes) are ciphered on bytes `i*3` (i<48) only.
  Species (79/80), held item (103/104) and the HP tail are plain.
  - The game's decrypt is 0x25c0 (stdcall src,dst); encrypt + checksum is 0x24c0.
- The in-memory save image is at RVA 0xD214E0 (payload offset 0).
  - Event flag bits at 0xd431a6 (byte id>>3, bit 1<<(id&7)); defeated-trainer bits at 0xd435a6.
  - Party at 0xd436a8.
- Flags 7990-7996 are unused by every script, so we store per-save mode/randomizer choices there.
  They live inside the real save, so they follow save/load for free.

**Runtime state**
- Scene byte at 0xc47234: 0 boot (writing 0 returns to the title cleanly), 6 title, 8 **field** (not 7),
  12 party target, 17 bag, 19 profile, 20 battle.
- Game state u32 at 0x93c130: 100 = field, 0 = in battle. It is also 0 after a save load until the first battle,
  so don't use it alone as "on the field".
- Current map id u16 at 0x99688c. This is the same number puppets store as their caught location.
- Battle init is at 0x18ac0 (dl = 0 wild / 1 trainer). The no-catch byte 0x93c0dc also blocks running away.
- The grass encounter roll calls 0x197110 at 0x19e086 (only caller). Hook that call to turn wild encounters off per map.
- **After a battle, the game writes the battle party back into the save party a few frames *after* the field state
  returns.** Removing fainted puppets or healing too early gets overwritten: wait ≥60 frames, or heal twice
  (we heal at 60 and 180 frames).
- The game's own silent team heal (also used by event opcode 1D) is 0x17bbb0 (cdecl, no args): HP/SP to max and
  status cleared.
- Capture: battle item handler 0xcd00.
  - **A seal is a turn timer** (enemy side +0x4c3). The puppet joins only at the end of a *won* battle while the
    timer is > 0.
  - Our "Destiny Thread" seals, then sets the enemy's HP to 0, and returns 0 EXP for that battle.
- Frame limiter 0x1b2a70: an immediate 1000 at 0x1b2a82, patched to 1000/speed for a speed-up (music unaffected).
- The battle move menu uses a bitmap font, not DxLib text. Overlays go at fixed coordinates of the 960×720 frame,
  drawn after the scene dispatcher.
  - The game's multiplier function 0x2d8c0 is ability-aware and safe to call from UI code (it only touches
    static-init guards).

**Event scripts** (`.evs`, 32 records × 10 u16; event/talk ids are global, folder = id/100)
- op1/op2: turn the player / a map object.
- op5: yes/no prompt.
- op6: set a flag.
- op8: enable or disable an object (saved per map).
- op0C: scripted wild battle (species, lines, style, level); op45: same but uncatchable.
- op14: give item.
- op2F: show a list from a CSV (unlock flag, label, event to run).
- **op9 <flag> <n> = if the flag is SET, jump to record n, else continue.** TPDP-Dev-Tools' `EVS SCRIPT README.txt`
  had it backwards up to v1.5.0, including 1.4.1 (the version TPDPHook-Extended's submodule pins); v1.5.1
  (2026-03-02) fixed it.
- Map objects are fmf layer 10 plus `.obs` records (1024 × 20 bytes). An invisible step trigger is sprite 0,
  move 0, delay 255, arg = event id.

## Build steps
1. Install SoD + Extended V4 + the English patch in a **copy** of the game folder. Keep one clean folder as reference data.
2. Clone TPDPHook-Extended with submodules (TPDP-Dev-Tools 1.4.1). Give `misc_hacks.cpp` and `custom_skills.cpp`
   their real source charset (`/source-charset:utf-8` for upstream's files) and the target `/execution-charset:.932`
   (see Gotcha 1).
3. Rebuild the config: V4's dll embeds an internal config that the source build doesn't have (Gotcha 2). Extract it
   and merge it with V4's external `TPDPHook.ini`, using LF line endings.
4. Add the code:
   - the VFS wrapper (in-memory map, then a `<game>\nuzlocke_data\` folder, then the archives);
   - rule hooks gated by save flags, and a per-save state file under `save\` (committed when the game writes the save);
   - php42's randomizer core compiled into the dll, returning `path → bytes` (~975 files in ~0.33 s), then copied into
     live tables on save load.
5. Generate the new event/talk/list/map files with a script, put them in `nuzlocke_data`, then build and copy the
   `dxgi.dll` and ini into the game folder.

The fork isn't published; the RVAs above are what you need to redo it on V4.

## Verification
- Oracle: the human played a fresh run plus test saves and confirmed each feature in game:
  - first-encounter-per-route with the dupes clause, wild encounters turned off on used routes, permadeath to a
    view-only graveyard box, game over on a wipe;
  - hard level cap, no healing items in battle, the mode/world choice on the bus, the randomized world surviving a restart;
  - the post-battle heal charm, the capture thread, scripted encounters, the profile counters.
- Static checks:
  - `diffgen` results were byte-compared per file (V4 patch applied, translation untouched).
  - The save codec round-trips byte-identical.
  - A legality checker caught all 12 planted defects in a crafted test save.
- Dynamic RE: we diffed `.data` snapshots (ReadProcessMemory) taken at steps the human played, using a small
  always-on-top "press F9 at this step" window. This found the map id, capture, faint and save-image addresses.
- Not verified: the free-PP-respec patch (installed, untested), Dance Arena battles (skipped on purpose), netplay
  (never touched).

## Gotchas
1. **Japanese battle strings came out corrupted from a source build.** **Cause:** `misc_hacks.cpp` and
   `custom_skills.cpp` have no BOM, so MSVC reads them in the system code page, while the game needs Shift-JIS
   strings (the 11-byte `スペシャル` write in `misc_hacks.cpp` only fits its Shift-JIS form). At ac012c3 both files
   are UTF-8. A copy converted to Shift-JIS fails another way on a non-Japanese locale: the trail byte 0x5C reads as
   a backslash escape (warning C4129). **Fix:** `/execution-charset:.932`, plus the files' real source charset
   (`/source-charset:utf-8` for upstream's files, `.932` for a Shift-JIS copy). Then compare a literal against the
   official dll.
2. **The source-built hook boots, but every Extended custom skill/item/ability is silently OFF.** **Cause:** the
   official V4 dll embeds an internal config (skill animations, ID tables). Its external `TPDPHook.ini` only has
   `[general]`/`[network]`, and missing IDs default to "none". **Fix:** extract the internal config and put it in
   the external ini. The parser doesn't strip CR, so use LF endings.
3. **The randomized type chart made everything immune.** **Cause:** the chart is read with DxLib `FileRead_scanf`,
   which our VFS didn't wrap, so it read zeros. **Fix:** wrap `scanf` too (line-based vsscanf over the served bytes).
4. **Serving randomized DollData changed nothing.** **Cause:** the static initializer had already loaded the tables
   before the hook. **Fix:** memcpy the records into the live tables (bytes 32+; keep the names) on the first frame,
   and on every save load.
5. **Healing or removing puppets right after battle didn't stick.** **Cause:** the delayed party write-back.
   **Fix:** wait ≥60 frames on the field, or act twice.
6. **"Field" checks failed after loading a save.** **Cause:** the field scene is 8, and the game state stays 0 until
   the first battle. **Fix:** check scene 8.
7. **New items showed up in the wrong bag tab.** **Cause:** tabs filter by ID range. Old IDs also stayed in the
   per-genre slot list with count 0. **Fix:** pick IDs inside the tab's range; purge stale slots and compact.
8. **The event `op9` logic was inverted from the docs.** **Cause:** TPDP-Dev-Tools' README had it backwards until
   v1.5.1. **Fix:** treat it as "jump if set" (verified on the shrine gate).
9. **A healing item in battle healed for free before our cancel ran.** **Cause:** the battle opens the field bag and
   the party target screen heals immediately. **Fix:** block it at the bag Use dispatch, not in the battle item handler.
10. **Addresses taken from the file didn't match at runtime.** **Cause:** ASLR. **Fix:** RVA-only, and build expected
    bytes at runtime.
11. **A plain C++ wrapper around the text-draw function crashed at battle start.** **Fix:** use a naked,
    register-preserving hook.
12. **Short key taps sent by automation were missed** (50 ms). **Fix:** hold keys for ≥100 ms.

## Assets
- One options-row label image was rebuilt from glyphs lifted from the game's other labels, with a regenerated outline.
  It's made from the game's own art, so it stays in your install: a published fork would build it from the
  player's files at runtime or use a label you drew yourself.
- All text is the game's own style. No generated art.

## Cost and time
About four sessions over four days (2026-11-08 to 2026-11-11), with the human testing live.

## Open questions
- Free PP respec is untested.
- Dance Arena battle types were intentionally ignored.
- The source-built dll leaves out the official build's extras (an easter egg and cryptopp).
- A ready-to-use fork release would need GPLv3 compliance because of the randomizer core.
