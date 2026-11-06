---
kind: game
title: "Save files: SOM3 decryption (AES-256-CBC) and marking collectible quest lines complete"
game: 'Middle-earth: Shadow of War'
games_also: []
game_version: 'Steam build 3095001 (public branch, unchanged since 2018-09-05), Windows 10 22H2'
platform: windows
engine: unknown
route: data
tools: ["Python 3.12 + cryptography (AES-CBC)", "Ghidra 12.1.4 (headless, analysis only)"]
anti_cheat: "none; single-player save file edited offline (the game ran with the offline-mode DLL from the earlier note). Load edited saves only offline, never signed in to WB. Back up both save copies first."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["DeimozZarco"]
date: '2026-10-15'
links:
  - "knowledge/games/middle-earth-shadow-of-war/goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md"
  - "knowledge/games/middle-earth-shadow-of-war/offline-mode-and-local-garrison.md"
tags: [save-edit, encryption, aes, crc32, quests, collectibles, inventory, chunks, reverse-engineering]
---
# Save files: SOM3 decryption and marking collectible quest lines complete

> Shadow of War saves are AES-256-CBC encrypted, with a key built from a fixed string, the Steam account id and the
> plaintext's CRC32. Decrypting and re-encrypting round-trips byte for byte. Inside is a tagged chunk stream. With
> it we marked the **Gondorian Artifacts** and **Web of Fate** collectible lines complete: the quest states are set
> to completed, the pickups go into the player's inventory and are removed from the world. The edited save loads
> and both categories show 100% (user, in game, 2026-10-15).

## Setup
- Steam build 3095001, Windows 10. Steam Cloud off during the edits.
- **The save exists twice:** `Steam\userdata\<account>\356190\remote\<accid8>_ShadowOfWar.sav` and
  `%LOCALAPPDATA%\WB Games\Shadow of War\` (plus rotating `_1`…`_5` backups). The game writes both. **Edit
  both**, after backing both up.
- **Scope (keep it this way):** your own saves, played offline.
  - Load an edited save only with the [offline-mode DLL](offline-mode-and-local-garrison.md) installed, never
    signed in to WB. Online Conquest and the Vendettas put your fortresses and captains in other players' games.
  - Don't edit `PC_Mirian`. When signed in, the game pushes it to WB's online wallet (`vc-earned`; see the
    offline-mode note).
  - Add only what the game awards through play, like the collectibles here. Don't add DLC items, or War Chests,
    boosts and other items from WB's online inventory: those were sold or are earned online, and adding them would
    be a purchase/ownership bypass.

## Route and why
- Edit the save data directly; there is no mod loader route for save state. The writer (found with Ghidra in the
  exe's save code) uses plain OpenSSL AES and a standard CRC32, so a small Python tool can decrypt, edit and
  re-encrypt.
- The other route is a trainer or quest console. We didn't need either; the edit is permanent and offline.

## How the game works (what we had to learn)
- **File header:** `'SOM3'`, `u32 crc32(plaintext)`, `u32 len(ciphertext)`, `u32 len(plaintext)`, then the
  ciphertext. The checksum is standard CRC32.
- **Cipher:** AES-256-CBC with PKCS#7 padding (OpenSSL EVP in the exe's save writer).
  - **IV** (16 ASCII bytes): `yuwgb@oftv@gx$t3`.
  - **Key** (32 ASCII bytes): `ad@210766@vac94Cd_?dVt5$alivjz$e`, with eight bytes overwritten:
    - the Steam account id as 4 little-endian bytes (it is also the hex prefix of the save file name) → key
      indices 10, 30, 22, 2;
    - the plaintext CRC32 as 4 little-endian bytes → key indices 26, 11, 18, 17.
  - So to re-encrypt an edited save: compute the new CRC32, patch the key, encrypt, write the new header.
- **Plaintext layout:**
  - `SAVE` v2 header, with the total size at +0x0C and again at +0x10 (= file size − 20);
  - global chunks;
  - `u32 3` (slot count), then per slot `06000000 <u32 len> 00000000` and a `SAVE` v31 block. Its u32 at +0x43 =
    the bytes left in the slot. Slot 1 = main campaign, slot 3 = DLC story.
  - Inside a slot: chunks `<4CC> <u32 ver> <u32 size> <u32 0> <u32 size-4>`.
  - **Every size field above changes when a chunk grows.** Fix all of them, or the load fails.
- **Value tags** inside chunks: `04` = u32, `00` = 32-bit name hash, `0c` = bool byte, `10` = length-prefixed blob.
  The hash is the gamedb AttrHash (`h = h*0x397 + map[c]`, see the
  [Goblins of War note](goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md)).
- **QSTD** (quest states): `04 <count>`, then per quest `00 <hash> 02 <lead> (0c <bool>)×9`, sorted by hash.
  - **Completed** = lead 1 and flags `0,1,x,0,1,0,0,1,0`.
  - `1,1,x,1,0,0,0,0,1` = only unlocked or available (looks done in the data, isn't in the UI).
- **IIUC** (world collectibles): ends with the list of pickups **still lying in the world**, `04 <n>` + n × `04 <hash>
  0c 01`. The game prunes owned items from it on load.
- **IVMG** (inventories): `04 <entities>`, then per entity `00 <id> 0c <has> 10 <u32 len> <blob>`.
  - The player blob opens with a record `00 c9b7c7b7 04 a 04 <entryCount>`. **entryCount = item records + the
    trailing `0c xx` pairs + 1.**
  - Item record: `00 <item hash> 04 <count> 04 <a> 04 <b> 0c <flag>`; collectibles use count 1.
  - IVMG's inner size u32 sits at chunk offset +33.
- **Quest lines → names:**
  - Gondorian Artifacts = items `Col_GondorPickup_01..54`. The counter item `GondorCollectableReward_CombinedItem`
    = the number owned.
  - Web of Fate = quests `ShelobPuzzle_<region>_01..03` + `ShelobPuzzle_MtnPass_Final`, and items
    `Col_SpiderPickup_01..15` + `Final`.

## Build steps
1. Back up both save copies. Decrypt; check that re-encrypting the untouched plaintext gives the same bytes.
2. QSTD: set each quest of the line to the completed pattern.
3. IVMG: append the missing pickup item records to the player blob, raise entryCount by the number added, and fix
   the blob length, the IVMG inner size and the chunk size.
4. IIUC: remove those pickups from the "still in the world" list and fix its sizes.
5. Fix the slot size, the slot's +0x43 field and the two top-level sizes. Re-encrypt and write to **both** paths.

## Verification
- In game: the save loads, and Gondorian Artifacts and Web of Fate show complete.
- Not verified: rewards. Skill-point and upgrade rewards for finishing a line are **not** granted by the edit.

## Gotchas
1. **The categories still show partial after the edit.** **Cause:** the "unlocked" quest pattern was mistaken for
   "completed", and pickups were added to IIUC, which lists items still in the world, not owned ones. **Fix:**
   use the completed pattern above, put the pickups in the IVMG inventory, and remove them from IIUC.
2. **The game crashes while loading the edited save.** **Cause:** item records were added without raising the
   player inventory's entryCount. **Fix:** entryCount = records + trailing `0c` pairs + 1.
3. **The game crashes after adding skill unlock items** (`PS_*_UNLOCK`) through IVMG. **Cause:** unknown; skills
   aren't plain inventory items. **Fix:** don't add skills this way. Collectible items are safe.
4. **Shadows of the Past (the statues) stays incomplete** with the same edit. **Cause:** its completion is
   stored somewhere else (not found). **Fix:** none yet.

## Open questions
- Where statue (Shadows of the Past) completion and line rewards are stored.
