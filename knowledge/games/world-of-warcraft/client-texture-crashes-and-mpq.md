---
kind: game
title: 'Hunting 3.3.5a client crashes in texture packs: BLP size and format limits, MPQ priority and safe patch building'
game: World of Warcraft
games_also: []
game_version: 'Wrath of the Lich King client 3.3.5a (build 12340, Direct3D 9 / d3d9ex, also under DXVK 3.1) with several third-party HD packs'
platform: windows
engine: native
route: data
tools: [StormLib / smpq (in WSL), Python 3.12 (BLP scanner, repair and encoder), a minidump parser, capstone]
anti_cheat: 'none touched: client data files on a private server'
status: working
agents:
- Claude Code (Opus 5.5)
humans: [RedSuper]
date: '2026-10-02'
links: ['https://wowdev.wiki/BLP', 'https://wowdev.wiki/MPQ']
tags: [blp, textures, crash, minidump, mpq, load-order, hd-pack, dxt, palettised]
---
# Hunting 3.3.5a client crashes in texture packs: BLP size and format limits, MPQ priority and safe patch building

> A 3.3.5a client with several HD texture packs crashed now and then, always during raids and after changing the
> texture resolution slider. The cause was two client limits that the packs ignore: textures over 1024 px and
> uncompressed textures. A scan of every texture header in all 35 archives found every instance; 29 proven-risk
> files were replaced in one small patch archive, and the crashes stopped. Along the way: which archive actually
> wins, and how to build patches that the client reads.

## Setup
- Client 3.3.5a, 35 MPQ archives (Blizzard's plus HD packs and our own patches), d3d9ex and later DXVK.
- Crash dumps: `%LOCALAPPDATA%\CrashDumps\Wow.exe.<pid>.dmp` (this client writes no Errors folder); parsed with a
  small minidump reader plus capstone around the faulting address.
- StormLib / smpq for listing, extracting and building archives.

## Route and why
Data only: find the bad textures, then override them with fixed copies in a later archive. Patching the client's
texture loader was not needed.

## How the game works (what we had to learn)
**Texture limits**
- **The client caps textures at 1024 px but copies rows at the file's size.** A 2048 px BLP is created one mip level
  smaller on the GPU and overrun by about half a megabyte: under d3d9ex the upload buffer ends at unmapped memory
  and it crashes (`Wow.exe+0x11ede`, the DXT row copy at `0x6ac040`); under plain d3d9 the same overrun corrupts
  memory silently.
- **Uncompressed BLPs (encoding 3)** overrun a `memcpy` in the BLP loader (`Wow.exe+0xCB6A`) when the texture
  resolution setting is lowered (a raid preset that drops a mip level triggers it).
- **Format must match the folder:** world, sky, liquid and model textures must be DXT (palettised copies of sky
  textures drew a green mess although they decoded correctly; Blizzard's own skies are all DXT); the character
  compositor is the opposite and needs palettised textures with an alpha plane (DXT1 drew green there). Pick the
  format the stock files in the same folder use, never by PSNR alone.
- Mip-table quirks (levels past the file end, absurd sizes on tiny tail levels) are common even in Blizzard's own
  files; only the ones on used levels matter.

**Archives**
- `Data\patch-<letter>.MPQ`: **a later letter wins** for models and textures, and beats the locale archives
  (`Data\enUS\patch-enUS-<letter>.MPQ`); DBC overrides do apply from the locale archives. Nothing sorts after `Z`,
  so making room means renaming a pack down a letter.
- Archives must be **MPQ format v1** (`smpq -c -M 1`); smpq's default (v4) is unreadable for 3.3.5a. File names
  may use `/` (the hash normalises to `\`).
- To know what the game really loaded: (1) a lock test (start to the login screen, then try to open each archive
  exclusively: loaded ones are locked); (2) a read-only scan of `Wow.exe` memory for strings that exist only in
  your files (texture names, DBC strings); (3) resolve which archive ships each file from the hash tables.

## Build steps
1. **Scan:** list every BLP in every archive (headers only, StormLib), then resolve which copy the client loads
   (213,796 entries, 162,477 actually loaded).
2. **Classify:** over 1024 px; uncompressed; broken mip tails on used levels.
3. **Fix only proven risks:** shrink by dropping top mip levels (lossless for what the client shows at the cap) and
   rebuild broken tails; re-encode uncompressed textures as DXT1 (opaque) or DXT5 (alpha).
4. **Pack** into an archive that loads after the HD pack (rename the pack down a letter if needed), on a Linux
   filesystem (packing straight onto a Windows drive from WSL ran at ~9 MB a minute), in one `smpq` call, then read
   every file back and compare.
5. **Install** only with the client closed (it locks every archive), with an MD5 guard on what's being replaced.
6. **Verify** with the same resolver: every fixed file now comes from the patch, and no oversized or uncompressed
   texture is left in any loaded non-Blizzard archive.

## Verification
- Crash signatures matched to the files by dump analysis (register values = remaining copy size of the exact
  texture); after the patch, no recurrence in the human's play.
- The resolver run after every archive change.

## Gotchas
1. **Crash only after changing the texture resolution, mid-raid.** **Cause:** the one 4 MB uncompressed texture in a
   water/sky pack. **Fix:** re-encode as DXT.
2. **Crash at full texture resolution after our own armour update.** **Cause:** a 2048 px texture we shipped.
   **Fix:** never ship a BLP over 1024; drop the top mip.
3. **The crash started only after switching to d3d9ex.** **Cause:** the same overrun now hit unmapped memory instead
   of silently corrupting the heap. **Fix:** remove the oversized textures.
4. **The fixed sky drew as a green mess.** **Cause:** palettised encoding where the folder uses DXT. **Fix:** DXT.
5. **New models never showed up from the locale archive.** **Cause:** `Data\patch-*` beats locale archives for
   models. **Fix:** ship models in a late `Data\patch-*` letter, DBCs where they apply.
6. **"Archive A beats Z" theory cost a test round.** **Cause:** guessing load order instead of asking what the human
   saw. **Fix:** lock test + memory scan; a later letter wins.
7. **Palettised BLPs decoded with alpha 0 in our checks.** **Cause:** Pillow reads the 8-bit alpha plane of palettised
   BLP2 as 0. **Fix:** our own palettised decoder.
8. **A WeakAuras glow sheet broke under DXVK.** **Cause:** a 2048 px uncompressed flipbook. **Fix:** 1024 DXT5.

## Open questions
- One unnamed texture in an older pack can't be overridden (no name to target).
