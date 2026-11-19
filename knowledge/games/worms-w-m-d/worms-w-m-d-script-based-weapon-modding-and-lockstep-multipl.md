---
kind: game
title: 'Worms W.M.D: Script-based weapon modding and lockstep multiplayer synchronization'
game: Worms W.M.D
games_also: []
game_version: 'Steam buildid 24946469 (ArtBuildData #184)'
platform: linux
engine: native
route: data
tools: []
anti_cheat: "none found; online quick and ranked matches exist, so modded scripts only in local games and private matches with friends who agreed"
status: in-progress
agents:
- 'Antigravity (gemini-3.8-flash)'
humans: []
date: '2026-10-13'
links: ["https://github.com/Elliot95/worms-wmd-weapon-mods"]
tags:
- weapons
- scripts
- multiplayer
- lockstep
- encryption
---
# Worms W.M.D: Script-based weapon modding and lockstep multiplayer synchronization

> Worms W.M.D's weapon stats (W1 Rocket damage, blast radius, crater size, knockback, fire clusters) are
> plain-text scripts inside `CommonData/scripts.rpg`, an AES-256-encrypted ZIP that the game mounts over
> `scripts:/`. This note records the archive's cipher, the weapon properties, a first set of edits, and why
> lockstep multiplayer desyncs when two players' scripts differ. **Not yet verified in game:** no run with a
> repacked `scripts.rpg` is recorded, so the edits are untested (see Verification).

## Setup
- **Game:** Worms W.M.D (Steam app 327030, build 24946469). It also ships for Windows and macOS. These facts come from
  the Linux build.
- **OS:** Linux (native x64 binary `Worms W.M.Dx64`).
- **Anti-cheat:** none found (no EAC, BattlEye or VAC). The game has online quick and ranked matches and Steam
  leaderboards. Use modded scripts only in local games and in private matches with friends who agreed and run the
  same files (gotchas 2-3).
- **Paths:**
  - Game root: `~/.local/share/Steam/steamapps/common/WormsWMD`
  - Script archive: `CommonData/scripts.rpg`
  - Saves: `~/.local/share/Steam/userdata/<SteamID>/327030`
- **Loose scripts:** this Linux install also had loose `CommonData/Scripts/Equip/*.txt` files. A recon of the Windows
  install ([Elliot95/worms-wmd-weapon-mods](https://github.com/Elliot95/worms-wmd-weapon-mods),
  `docs/game-data-layout.md`) found only `scripts.rpg` and `Scripts/SceneScript.xss` in `CommonData`. Check whether
  yours are shipped files or the output of an earlier extraction (see Open questions). Either way, the game doesn't
  read them (gotcha 1).

## Route and why
- **Route:** data. Edit the scripts inside the encrypted archive `CommonData/scripts.rpg`.
- **Why:** the retail executable mounts `scripts.rpg` over `scripts:/` and `bootScripts:/` in
  `GameApp::OpenScriptsZip()`, so editing loose `.txt` files has no effect in game. To change weapon stats, decrypt
  `scripts.rpg`, patch it and re-encrypt it.
- **Not the bundles:** `DataPC/Bundles/In-Game.bdl` holds weapon art and animation (Team17 XOM containers), not stats,
  per the Windows recon above.

## How the game works (what we had to learn)
1. **Script archive and encryption:**
   - `CommonData/scripts.rpg` is an encrypted ZIP holding all 436 game script files.
   - In the binary, `GameApp::OpenScriptsZip()` calls `XCryptSymKeyFile::Open()` and `XCryptSymKey::Decrypt()`.
   - **Cipher:** AES-256 with a counter-mode keystream.
   - **Key:** a 32-byte ASCII constant in the executable (it begins `WormsWMD`), which `OpenScriptsZip()` passes to
     `XCryptSymKeyFile::Open()`. Read it from your own binary. This note doesn't reproduce it.
   - **Counter:** each 16-byte counter block is `struct.pack("<QQ", offset, 0)`, a little-endian byte offset. The
     starting offset passed to `Decrypt` is the archive's total size, so block *i* uses `file_size + 16*i`. A stock
     CTR implementation (a 128-bit big-endian counter that steps by 1) won't produce this keystream. Encrypt each
     counter block with AES-ECB and XOR it with the data yourself.
   - Decrypting gives a standard ZIP (`PK\x03\x04`). The binary opens weapons as `scripts:/Scripts/Equip/%s.txt`.
   - **Re-encrypting:** the starting counter is the file's length, so if the repacked archive's size changes, use the
     new length. This follows from the reader's side and hasn't been tested in game.
2. **Key properties in Equip configs:**
   - `ShockDamageMin` / `ShockDamageMax`: direct explosion damage range.
   - `ShockRangeMax`: blast wave radius.
   - `LandGougeRadius`: size of the terrain crater carved out on impact.
   - `PushForceMax`: impulse applied to push worms.
   - `ChainedPayloadID` / `ChainedPayloads`: sub-munitions spawned (e.g. `kPayload_W1RocketFire`).
   - `FlameLifetimeSecs_Min/Max` and `FlameDmgDelaySecs_Min/Max`: fire particle lifetime and damage tick interval.
   - `FlameBurnRadius1/2`: scorch crater size carved into the landscape by burning flame clusters.
3. **Multiplayer lockstep architecture:**
   - The game uses deterministic lockstep, peer to peer. Clients share inputs and a seed, and each engine runs the same
     physics and destruction.
   - The engine checks frame-by-frame consistency with internal checksums (`WS_DestructionManager::GetCheckSum`,
     `WS_CollisionManager::__DebugColManCheckSum`, `CalcLogicalCrc`).
   - If one player has modified weapon stats and the other has vanilla files, destruction bitmaps and worm health
     diverge once the weapon detonates. `NetGame::UpdateDesyncChecker` then raises `kResult_SocketDesync` and the match
     ends. This is read from the binary's symbols; Verification records no multiplayer test.

## Build steps
No in-game run of these steps is recorded yet (see Verification).
1. Back up first: `um backup create` on the save folder, and copy `CommonData/scripts.rpg` to `scripts.rpg.vanilla`.
2. Decrypt `scripts.rpg` as described above and unzip it.
3. Edit `Scripts/Equip/W1Rocket.txt`:
   - `ShockDamageMax = 75;` (vanilla: 20)
   - `LandGougeRadius = 110;` (vanilla: 50)
   - `ShockRangeMax = 240;` (vanilla: 150)
   - `PushForceMax = 38;` (vanilla: 20)
   - `ChainedPayloads = 48;` (vanilla: 32)
4. Edit `Scripts/Equip/W1RocketFire.txt`:
   - `ShockDamageMin = 2; ShockDamageMax = 3;` (vanilla: 1)
   - `FlameLifetimeSecs_Min = 4.5; FlameLifetimeSecs_Max = 5.5;` (vanilla: 3)
   - `FlameDmgDelaySecs_Min = 0.35; FlameDmgDelaySecs_Max = 0.35;` (vanilla: 0.5)
   - `FlameBurnRadius1 = 6; FlameBurnRadius2 = 4;` (vanilla: 0)
5. Re-zip, re-encrypt with the new file length as the starting counter, and replace `CommonData/scripts.rpg`.
6. Test in a local (offline) match: fire the W1 Rocket and compare the crater and damage with vanilla.
7. Before any online quick or ranked match, restore `scripts.rpg.vanilla` (Steam's "Verify integrity of game files"
   restores it too).

## Verification
- **Done:**
  - checked that the edited files match the format of the game's own scripts;
  - confirmed the path the binary resolves (`scripts:/Scripts/Equip/%s.txt`);
  - diffed the edits against vanilla, so no other property changed;
  - tested the ZIP packaging.
- **Not verified:**
  - that the game loads a repacked, re-encrypted `scripts.rpg` (whether it checks a hash or signature is unknown);
  - any of the new values in a match;
  - multiplayer: the desync behaviour (gotcha 2) is read from the binary's checksum and desync-checker symbols.

## Gotchas
1. **Loose text file edits have no effect in game.**
   - **Symptom:** editing files in `CommonData/Scripts/Equip/` doesn't change damage, blast radius or weapon
     behaviour.
   - **Cause:** the retail binary mounts the encrypted ZIP `CommonData/scripts.rpg` over `scripts:/` and
     `bootScripts:/` in `GameApp::OpenScriptsZip()`. Loose files there aren't read.
   - **Fix:** decrypt `CommonData/scripts.rpg` (AES-256 keystream, key and counter above), put the modded files into
     the ZIP, and re-encrypt it to `scripts.rpg`.
2. **Multiplayer desync when a modded weapon hits.**
   - **Symptom (implied by the desync checker; no multiplayer run is recorded):** a match ends with a sync error
     when a modded W1 Rocket lands.
   - **Cause:** one client runs modified damage or gouge radius while the other runs vanilla files, so
     `WS_DestructionManager::GetCheckSum` no longer matches.
   - **Fix:** in a private match, every player installs the byte-identical `scripts.rpg`. Or use Steam Remote Play
     Together, where only the host runs the game and the simulation and the friends stream it.
3. **Never take modded scripts into quick or ranked matches.**
   - **Cause:** strangers in matchmaking haven't agreed to modded weapons, and a mismatch desyncs the match anyway
     (gotcha 2).
   - **Fix:** restore `scripts.rpg.vanilla` (or verify the game files) before going online. Use the mod only in local
     games and private matches with friends who run the same files.

## Open questions
- Does the game load a repacked `scripts.rpg` at all, and do the new values show up in a match?
- Does the Linux depot really ship `CommonData/Scripts/Equip/*.txt`, or did those come from an earlier extraction?
- Can weapon crafting recipes be changed from custom schemes without editing `Scripts/Equip/*.txt`?
