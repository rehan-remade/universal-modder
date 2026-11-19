---
kind: game
title: "StreetPass Mii Plaza: one game, three title IDs (the app in NAND, its patch and paid games on SD)"
game: "StreetPass Mii Plaza"
games_also: []
game_version: "EUR system app 00040010-00022800 on my own 3DS, with an SD patch (0004000e-00022800, ~94 MB) and SD add-on content (0004008c-00022800)"
platform: console
engine: native
route: data
tools: ["Nintendo 3DS console", "SD card file listing"]
anti_cheat: "none relevant; StreetPass is local wireless and no online feature was touched"
status: in-progress
agents: ["OpenCode (Big Pickle)"]
humans: ["GeoffreyMba"]
date: 2026-10-16
links:
  - "https://www.3dbrew.org/wiki/StreetPass_Mii_Plaza"
  - "https://www.3dbrew.org/wiki/Title_list"
  - "https://www.3dbrew.org/wiki/Extdata"
  - "https://www.3dbrew.org/wiki/SD_Filesystem"
  - "https://github.com/LumaTeam/Luma3DS/wiki/Optional-features"
tags: [nintendo-3ds, ctr-sdk, system-app, sd-install, dlc, extdata, encrypted-content, layeredfs, romfs]
---

# StreetPass Mii Plaza: one game, three title IDs (the app in NAND, its patch and paid games on SD)

> What a system-bundled 3DS title looks like from the SD card. The plaza itself is a system app in the console's
> NAND, so the card only holds its patch title, a *separate* add-on-content title for the paid games, and an
> extdata slot. Read-only look at my own console's SD card; nothing was decrypted and nothing on the card was
> changed.

## Setup
- **Copy used:** my own 3DS (EUR). StreetPass Mii Plaza comes preinstalled on every 3DS as the system
  application `00040010-00022800` in NAND. Its patch and add-on content are on the SD card. I looked at the SD
  card's folder layout from a PC; no decryption keys were used.
- **Tools:** the console and a plain SD-card file listing. No homebrew was run and no title content was read.
- **On the card** (under `Nintendo 3DS/<ID0>/<ID1>/`): the patch in `title/0004000e/00022800` (about 94 MB), the
  paid content in `title/0004008c/00022800`, and one small extdata slot, `extdata/00000000/00000228`, with
  roughly a dozen files. There is no `title/00040000/00022800`: the plaza app itself never appears on the card.

## Route and why
Route: **data**, not tried. The plaza's content is sealed like any installed title, so the community route for
changing it is to replace files at runtime with a RomFS overlay: Luma3DS's LayeredFS ("Enable game patching",
replacement files in `/luma/titles/<title ID>/romfs/`), which needs custom firmware on the console. Editing the
card directly was dropped on sight: everything under `Nintendo 3DS/<ID0>/<ID1>/` is encrypted per console, so
there is nothing to read or patch there without the console's keys.

## How the game works (what we had to learn)
- **Three titles, one product, two storage places.** The plaza is a system application (`00040010-...`) in NAND.
  Since system update 6.0.0-12, the last one to change the app itself, it is updated through an SD patch title
  (`0004000e-...`), and the paid games come as a separate add-on-content title (`0004008c-...`). Each has its own
  ID and its own sealed content. "How big is this game" has three answers, and only two of them are on the card.
- **The paid games are add-on content, not a patch.** They're bought inside the plaza and arrive as the
  `0004008c-...` title. Add-on content can't contain code (3dbrew's title list marks the type
  `CannotExecution`), so their code has to ship with the app or the patch. What exactly the add-on title holds
  wasn't checked.
- **The progress is split between NAND and the SD card.** According to 3dbrew, the plaza's system save in NAND
  (`meet.dat`) holds your Mii, the Miis you met, the StreetPass count, achievements and the puzzle tiles you
  own. Its extdata holds progress for the paid games, and a SpotPass extdata archive holds the downloaded puzzle
  images. So the `00000228` slot on the card is only part of the user's state.
- **The content is per-console encrypted.** Everything under `Nintendo 3DS/<ID0>/<ID1>/` is AES-CTR encrypted
  with console-unique keys (3dbrew, SD Filesystem). A copied title folder is opaque: no readable code, textures
  or strings.
- **Engine:** Nintendo first-party, built on the 3DS SDK (CTR SDK).
- **RomFS is the modding surface, for the app and the patch only.** Luma3DS's LayeredFS presents replacement
  files ahead of the game's own RomFS at runtime, but its documentation says DLC patching isn't supported, so
  the add-on title is out of its reach.

## Build steps (reproduce this pass)
1. On a PC, open the SD card's `Nintendo 3DS/<ID0>/<ID1>/` folder. Titles are in `title/<ID high>/<ID low>/`,
   SD extdata in `extdata/00000000/<extdata ID>/`.
2. Find the patch (`title/0004000e/00022800`) and the add-on content (`title/0004008c/00022800`), and note their
   sizes. These are the EUR IDs; the USA plaza is `...00021800` and the Japanese one `...00020800` (3dbrew).
3. Find the extdata slot (`extdata/00000000/00000228`; USA `00000218`, JPN `00000208`) and count its files.
4. Record the IDs and the extdata slot so you can tell patch, add-on content and user state apart before touching
   anything.
5. Confirm the wall: open the largest file in the patch folder in a hex viewer; there is no plaintext.

## Verification
- **Verified:** on my own console's SD card, the patch folder `title/0004000e/00022800` (about 94 MB), the
  add-on-content folder `title/0004008c/00022800`, the extdata slot `00000228` with about a dozen files, and
  that the stored files aren't readable without the console's keys.
- **From 3dbrew, not measured here:** the app's own ID (`00040010-00022800`, in NAND), the split of progress
  between `meet.dat` and extdata, and that add-on content can't hold code.
- **Not verified:** nothing inside the sealed content was read: no code, textures, strings or file lists. The
  minigame roster is eShop knowledge, not a measurement. No overlay was built, installed or tested.

## Gotchas
1. **Symptom.** You look for the plaza on the SD card and find only a patch and an add-on folder, or you size it
   up from those and it looks far too small. **Cause.** The plaza is a NAND system app (`00040010-00022800`);
   only its patch and paid content are on the card. **Fix.** Don't treat the missing `title/00040000/...` folder
   as a broken install; count NAND app + patch + add-on content before drawing conclusions.
2. **Symptom (expected, not tested).** A plaza retexture works but a paid minigame still looks stock. **Cause.**
   If that minigame's files live in the add-on-content title, Luma3DS's LayeredFS can't reach them: its
   documentation says DLC patching isn't supported. **Fix.** Check which title owns the file before you start;
   the add-on title needs another approach.
3. **Symptom.** You back up the SD card, and the plaza's Miis and achievements still aren't in the backup.
   **Cause.** They're in the plaza's system save in NAND (`meet.dat`); the SD extdata only has the paid games'
   progress. **Fix.** Back up both. 3dbrew notes that NAND saves like this one had no easy way out until
   homebrew save managers (JKSM, 2016). An SD copy only restores on the same console.
4. **Symptom.** You open the biggest file on the card looking for assets. **Cause.** Per-console encryption on
   everything under `Nintendo 3DS/<ID0>/<ID1>/`. **Fix.** Don't expect plaintext from the card; the community
   route is a runtime LayeredFS overlay, which needs custom firmware.

## Assets
None - reconnaissance only; nothing was authored, decrypted or written.

## Open questions
- What the add-on-content title actually holds: the paid games' assets, or little more than what unlocks them.
- How much of the ~94 MB patch replaces the NAND app's files versus adding the newer plaza versions' content.
- Whether Luma3DS's LayeredFS applies to a system app like the plaza at all (`/luma/titles/0004001000022800/`).
