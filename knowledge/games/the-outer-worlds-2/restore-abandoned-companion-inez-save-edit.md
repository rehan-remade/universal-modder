---
kind: game
title: "Restore an abandoned companion (Inez) by editing a Game Pass save"
game: "The Outer Worlds 2"
games_also: []
game_version: "Microsoft Store / Game Pass PC package Microsoft.OE-Arkansas 1.299.4920.0; saves written by game builds 1.0.3.0, 1.0.4.1 and 1.0.5.0"
platform: windows
engine: unreal
route: data
tools: ["Python 3 (stdlib zlib, struct, ctypes)", "oo2core_8_win64.dll from another installed game (read-only Oodle decoding, not redistributed)", "gh"]
anti_cheat: "none (single-player)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-11-12
links: []
tags: [save-editing, companions, quests, global-variables, xbox-wgs, game-pass, iostore, oodle, unreal-5]
---

# Restore an abandoned companion (Inez) by editing a Game Pass save

> The player missed Inez's recruitment window on Paradise Island, so the game marked her abandoned and later
> put her body on the island. We edited a late-game Game Pass save so that she is a recruited crew member,
> her recruitment quest is complete and her companion questline (`CQ_Inez1_FindDoctor` onward) is untouched.
> Loaded in the real game, she was on the ship, talkable and in the party. The game's own autosaves kept the
> state, and the Ortiz courier who starts her first companion quest appeared on the ACS Undisputed Claim.

## Setup
- Windows 11, Xbox app / Game Pass install. Files live at `<drive>:\XboxGames\The Outer Worlds 2\Content\`.
  The `Arkansas\Content\Paks` folder is readable and writable. The shipping exe
  (`Arkansas\Binaries\WinGDK\TheOuterWorlds2-WinGDK-Shipping.exe`) is **not readable** (permission denied),
  so we did no code RE.
- Saves are Xbox "wgs" containers: `%LOCALAPPDATA%\Packages\Microsoft.OE-Arkansas_8wekyb3d8bbwe\SystemAppData\wgs\<xuid>_<...>\`.
  After a reinstall they only came back once the Xbox app had synced the cloud saves.
- Python 3 with the standard library only. To read game data we loaded an `oo2core_8_win64.dll` that another
  installed game ships, via ctypes. Oodle 2.8 decoded this UE5 IoStore without problems.
- No mod loader, no console enabler, nothing installed into the game folder.

## Route and why
- **Console:** the community console (Nexus "Console Enabler and BP ModLoader") lists item, perk, trait and
  combat commands. No guide we found shows a quest-stage, global-variable or add-companion command. Two
  unverified sites mention `QuestStart`/`QuestComplete`.
- **Existing save editors:** none edit quest or companion state. The Nexus "Character Editor" covers only
  appearance, skills and perks.
- **Chosen route: a save edit with a donor save.** We needed a reference for "Inez recruited". It existed
  because the player had replayed from an early Paradise Island save (same character) and recruited her
  there. We transplanted her companion record and her recruitment quest record from that replay into the
  late save, then cleaned up the flags the abandonment had set.
- Game data (names for the GUIDs) came from the unencrypted IoStore. We read it but redistribute none of it.

## How the game works (what we had to learn)
**Xbox wgs container (Game Pass saves).**
- `containers.index`:
  - header: `i32 ver`, `i32 count`, `i32`, `str16 package`, 12 bytes, `str16 guid`, 8 bytes;
  - per entry: `str16 name`, `str16 name2`, `str16 etag`, `u8 containerNum`, 4 bytes, `GUID folder`,
    `u64 FILETIME mtime`, 8 bytes, `u64 totalSize`.
  - `str16` = `i32 charCount` + UTF-16LE.
- `<folder>\container.<num>`: `i32`, `i32 fileCount`, then per file 64 UTF-16 chars of name, a 16-byte
  cloud GUID and a 16-byte local GUID. The local GUID's hex is the blob's file name.
- Each OW2 save holds three blobs: `Metadata.dat`, `SaveGameScreenshot.png` and `SavedState.dat`.
  `totalSize` in the index equals the sum of their sizes.
- Manual-save container names are 32-hex hashes; autosaves are `Autosave00..02`.

**`Metadata.dat`** (magic `GMHF`). It holds the character name, the player level (a `u32` right after the
name), the build string (e.g. `1.0.4.1`) and a zlib blob. **`u32` at 0xF7 = decompressed length of
`SavedState.dat`.** There is no hash of the state.

**`SavedState.dat`** is a single zlib stream. Decompressed, it is a flat archive:
```python
def parse(raw):  # raw = zlib.decompress(SavedState.dat)
    n = struct.unpack_from('<I', raw, 0)[0]; p = 4; ents = []
    for _ in range(n):
        nl = struct.unpack_from('<i', raw, p)[0]; p += 4
        name = raw[p:p+nl-1].decode(); p += nl
        dl = struct.unpack_from('<I', raw, p)[0]; p += 4
        ents.append([name, raw[p:p+dl]]); p += dl
    return ents  # round-trips byte-exact; any zlib level is accepted on load
```
- **Entries:** `Player.dat`, `LevelRefs.dat` (the first `/Game/Maps/...` string is the level the save was
  made in), `GlobalVars.dat`, `Quests.dat`, `Conversations.dat`, `CompanionManager.dat`,
  `Companion7.dat`..`Companion12.dat`, one `<map>_<hash>.dat` per visited level and many `FOW_*.blob`.
- Most sub-blobs start `01 05 00 00 00 <4cc> 00 01 00 00 00 27 00 0a 02 00 00 f4 03 00 00` (24 bytes).

**`GlobalVars.dat`** (`GVHF`): after the 24-byte header, `u32 count` then `count × (GUID[16], i32 value)`.
Unset variables are simply absent.

**Mapping the GUIDs to names (IoStore).**
- `Arkansas-WinGDK.utoc` v6: container flags `0x09` (compressed + indexed, **not encrypted**), one method
  `Oodle`, 64 KiB blocks.
- The directory index sits right after the compression-method names. Remember the perfect-hash seeds
  (`u32` at header offset 84) and the no-perfect-hash count (`u32` at 96) when computing offsets.
- `Exported/BaseGame/Design/GlobalVariables/game.uasset` holds every global (about 5,800) as records:
  `80 07 <type>`, an FString name, an optional default byte, then the 16-byte GUID.
- `Exported/BaseGame/Design/Quests/quests.uasset`: each quest's FString name is followed directly by its
  GUID. A quest's own data comes *before* its name in the file.
- Quest data references globals by raw GUID bytes. Conversations reference them as **32-char uppercase hex
  text** (`%08X` of the FGuid's four `u32`, little-endian), so a raw-byte search misses them.

**`CompanionManager.dat`** (`CPHF`): after the 24-byte header and one byte (`0a`), there are **7 lists**,
each `u32 n` followed by `n` `u8` companion ids.
- The ids are the `CompanionN.dat` numbers: 7 Niles, 8 VALERIE, 9 Azahelia (Aza), 10 Marisol, 11 Tristan,
  12 Inez.
- List order: [0] unlocked/recruited, [1] dismissed?, [2] active party (empty while on the ship),
  [3] last party, [4] ?, [5] wants-to-talk, [6] ?.
- The script functions in conversations match these lists: `AddCompanionToParty "Companion12"` (how Inez is
  recruited, in `g_companion_inez_paradiseisland`), `IsCompanionUnlocked`, `IsCompanionDismissed`,
  `IsCompanionInActiveParty`, `ReplaceCompanionInSlot "Companion12" "Slot1"`, `SetCompanionWantsToTalk`.

**`CompanionN.dat`** is the companion actor's saved components. A recruited record contains
`Trait_<Name>_Combat_C` / `Trait_<Name>_NonCombat_C` (only while in the active party) and team
`T_Player`. Inez's abandoned record had neither. The same record copied from a recruited save loads fine in
a later save.

**`Quests.dat`** (`QMHF`): after the 24-byte header, `u8 4`, `u32 count` (153), then per quest:
- `GUID[16]`, `i32`, `u32 subCount` (0 for the Inez quests; other quests have nested data we did not decode);
- 5 bitsets, each `u32 nbits` + `ceil(nbits/32)` `u32` words;
- `u32 nA` + `nA×8`;
- `u32 nB` + `nB×8` (objective index/state pairs);
- `i32`, then **`u8 status`** (0 not started, 2 complete, 3 failed);
- `u32 nC` + `nC×12` (node id + FDateTime of completed nodes).

The node count of `CQ_Inez0_InezAcquisition` changed between builds (94 nodes → 102). The game loads both,
so copying a record from a newer save works.

**Inez-specific state.**
- Quest GUIDs as saved: `CQ_Inez0_InezAcquisition` `d9897bd6d7411449e6c756badbadba12`,
  `CQ_Inez1_FindDoctor` `5ffd16dc4447582df90bb89c3c1cb0cf`. In this save the Inez1 record directly follows
  the Inez0 record.
- When you leave Paradise Island without her, `Companion12.dat` changes and she joins the wants-to-talk list.
- After the save was played on build 1.0.4.0 (the patch that "makes her fate clearer"), `CQ_Inez0` flipped
  to status 3 partway through a session, ending on nodes 89 and 91, and her armour/body appeared in the
  `0201_PI` level data.
- Later in the playthrough, while she was absent, the game also set these globals, which pre-resolve her
  content:
  - `WTT_CE_Inez_QuestEnd=3`, `Inez_WTT_NewPath=4`, `Inez_WTT_ReformWrapUp=1`, `Inez_WTT_ZlabMarisolMet=1`;
  - `Inez_ExplainedGraft=1`, `0308_InezBroughtToHelpGraft=1`, `03_Inez_GD_ShipDeath=2`, `InezHostile=1`;
  - `0502_RE_InezNilesTalk_Ready=2`, `0502_RE_InezGraft_Fired=1`;
  - `0503_InezPresentDuringPeaceTalks=1`, `0803_InezPresentDuringAuntieReveal=1`.
- Her first companion quest is started by a courier on the ACS Undisputed Claim (globals
  `Inez_MessageFromDownAndOuter`, `CE_Inez_CompanionQuest_HasDiscussedOrtiz`, `0803_InezCourier_Move`, ...).
  None of those were set, so the questline had never been consumed.

## Build steps
1. Close the game and snapshot the whole `wgs` folder.
2. Find the target container in `containers.index`. Pick a save made **before** landing on Halcyon Prime;
   see Gotcha 4. The save we edited was made on the player ship (`LevelRefs.dat` →
   `0502_PlayerShip_P`).
3. Decompress `SavedState.dat` from the target and from the donor (a save where Inez is recruited), then
   parse both archives.
4. Replace `Companion12.dat` with the donor's.
5. In `CompanionManager.dat`, add id 12 to list 0, set the last-party list 3 to `[12, 9]` (leave the active
   list 2 empty when the save is on the ship) and remove 12 from the wants-to-talk list 5.
6. In `GlobalVars.dat`:
   - remove the abandonment globals listed above;
   - copy `0209_MetInez`, `0209_ToldInezMilverstreetsOrder`, `0209_InezCompletesMilverstreetTask` and
     `Inez_BarkedLeavingPIWarning` from the donor;
   - rewrite the count.
7. In `Quests.dat`, replace the `CQ_Inez0` record (from its GUID to the `CQ_Inez1` GUID) with the donor's
   record (status 2). Leave `CQ_Inez1`, `CQ_Inez2A_EndGraftingProgram` and `CQ_Inez2B_ReformGraftingProgram`
   as they are (status 0).
8. Rebuild the archive and zlib-compress it. Write `SavedState.dat`, patch `Metadata.dat` @0xF7 with the new
   decompressed length, and in `containers.index` set the entry's `totalSize` and bump its `mtime` to now.
9. Launch through the Xbox app and load the save. The Xbox app did **not** overwrite the edited blobs from the
   cloud.

## Verification
- **Oracle 1: the running game.** It loaded the edited ship save. Inez was walking around the ship, could be
  talked to, and went out as a party member.
- **Oracle 2: the game's own saves.** The autosaves it wrote after the load still had Inez in the unlocked
  list and the party, `CQ_Inez0` at status 2 and Inez1/2A/2B at status 0. Her Crabble graft accessory from
  the donor was still equipped.
- **Oracle 3: the trigger.** The Ortiz courier on the ACS Undisputed Claim appeared, so the companion
  questline's trigger works.
- **Not verified:**
  - completing `CQ_Inez1`/`2A`/`2B`;
  - the end slides;
  - whether her level scales properly (her record came from an early-game save);
  - a second edit, adding her straight to the active party in the point-of-no-return save on Halcyon Prime
    (never loaded).

## Gotchas
1. **Symptom:** `PermissionError` reading the Game Pass shipping exe. **Cause:** that file's ACL blocks reads
   by the user (the paks are fine). **Fix:** work from save data and the IoStore. You don't need the exe for
   this.
2. **Symptom:** no reference for what a recruited companion looks like, because the player never recruited
   her. **Cause:** a missed-recruitment save simply has no such state. **Fix:** recruit her in any early save
   of the same character (or ask the player whether old autosaves exist). Here, autosaves from an abandoned
   replay held a perfect donor. Diff the replay's globals against its branch-point save to tell recruitment
   flags from everything else.
3. **Symptom:** globals saying Inez was at the peace talks or the Auntie reveal, or that her quest ended,
   though she was never in the party. **Cause:** the companion systems pre-resolve content for an absent
   companion. **Fix:** clear them (list above) or her WTT topics and quests may stay closed.
4. **Symptom:** you'd like to use the "point of no return" save. **Cause:** `G_PointOfNoReturn` is already 1
   from the prologue, so it is not the endgame lock. The real marker is being on `0901_HP_P`, with globals
   such as `0901_Landed_On_HP` set. From there you can't fly anywhere, so companion quests can't be played.
   **Fix:** edit the last save made before landing on Halcyon Prime.
5. **Symptom:** right after loading the edited save, the game sets `InezKilledByHostile=1`. **Cause:**
   probably the leftover body in the Paradise Island level data. **Fix:** none needed. Only
   `g_companion_inez_paradiseisland` reads it, so the main questline is unaffected; her Paradise Island
   barks may be off.
6. **Symptom:** searching assets for a global's GUID finds it in quests but never in conversations.
   **Cause:** conversations store GUIDs as uppercase hex text. **Fix:** search for both forms.
7. **Symptom:** a generic sequential `Quests.dat` parser breaks on the second quest. **Cause:** a non-zero
   `subCount` after the GUID brings nested data we didn't decode. **Fix:** for the Inez quests (`subCount`
   0), compute the record end from the fields and assert it lands on the next quest's GUID before splicing.
8. **Symptom:** worry that the cloud copy would replace the edit. **What happened:** after bumping the
   index entry's `mtime` and fixing `totalSize`, the Xbox app kept the local edit and the game loaded it.

## Assets
None.

## Cost and time
About one session. Most of the time went into the wgs and archive formats, then mapping GUIDs through the
IoStore.

## Open questions
- The nested part of `Quests.dat` records (`subCount` > 0) and the meaning of the bitsets.
- The meaning of `CompanionManager` lists 1, 4 and 6.
- The trailing 8 bytes after the zlib blob in `Metadata.dat`.
- Whether an Inez added straight to the active party on a Halcyon Prime save behaves in the final mission.
