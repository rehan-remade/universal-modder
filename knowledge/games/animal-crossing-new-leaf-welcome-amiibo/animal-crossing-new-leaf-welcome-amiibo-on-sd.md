---
kind: game
title: "Animal Crossing: New Leaf - Welcome amiibo on SD"
game: "Animal Crossing: New Leaf - Welcome amiibo"
games_also: ["Animal Crossing: New Leaf"]
game_version: "SD install on my own 3DS (title 00040000-00198f00 plus a 14 MB update)"
platform: console
engine: native
route: data
tools: ["Nintendo 3DS console (software list)", "SD card file listing"]
anti_cheat: "none relevant; the online service was not used"
status: in-progress
agents: ["OpenCode (Big Pickle)"]
humans: ["GeoffreyMba"]
date: 2026-10-16
links: []
tags: [nintendo-3ds, ctr-sdk, sd-install, extdata, encrypted-content, layeredfs, romfs, update]
---

# Animal Crossing: New Leaf - Welcome amiibo on SD

> The largest install on the card, an update slot a fraction of its size, and an extdata slot with only a couple
> of files - a useful reminder that extdata size says nothing about where a big game keeps its save. Read-only
> inspection of my own console; nothing was decrypted and nothing on the card was changed.

## Setup
- **Copy used:** my own 3DS. Animal Crossing: New Leaf - Welcome amiibo is installed under title `00040000-00198f00`, with a small update in the `0004000e-00198f00` slot. Inspected through the console's software list and the SD card's folder layout; no decryption keys were used.
- **Tools:** the console's software list and a plain SD-card file listing. Nothing was launched from outside the console and no title content was read.
- **On the card:** a ~935 MB base app - by a wide margin the biggest single title on the card - an update around 14 MB, and an extdata slot (`0000198f`) holding just a couple of files.

## Route and why
Route: **data** - the title is sealed, so the workable surface is a LayeredFS RomFS overlay that presents replacement files at runtime. Editing the card directly was dropped immediately: the content is encrypted per console, so there is nothing to read or patch on the card without keys. Two details shape any work here: the title is huge (so an overlay should replace single assets, not whole archives), and the update is a *separate* title that can itself be overlaid.

## How the game works (what we had to learn)
- **The update is a title, not a patch file.** It has its own ID in the `0004000e-...` range and its own sealed content. Anything you change in the base app can be silently superseded if the update also ships that file, so know which title owns the file you care about.
- **A small extdata slot is normal for a large game.** Here extdata is only a couple of files; the game's own save area is not extdata. Do not infer "no save here" from a small extdata folder, and do not assume extdata is where a big game's progress lives.
- **The "Welcome amiibo" revision is its own identity.** The install here identifies as the Welcome amiibo title ID, not as the 2012 original. The same content reached players two ways - a standalone expanded release and a free update for existing owners - so the same revision can look like a base app or like an update depending on how it was obtained. Worth knowing before you compare notes with another owner.
- **The content is per-console encrypted.** Title and update folders are opaque; reading them needs the console's keys, which is out of scope here.
- **The engine is Nintendo first-party on the 3DS SDK family (CTR SDK).** "NitroSDK" is the DS SDK and the wrong generation for a 3DS title.
- **RomFS is the modding surface.** A loader presents replacement files ahead of the game's own RomFS, so the installed game stays untouched and the mod stays removable.

## Build steps (reproduce this pass)
1. On the console, note the title ID and the installed size in the software list.
2. On a PC, find the title's folder in the SD card's Nintendo 3DS tree and confirm it is the largest single install on the card.
3. Find the update folder for the same title and compare sizes - the update is small here, which is not the same as "unimportant".
4. Find the extdata slot for the same title and note how few files it holds.
5. Confirm the wall: open the largest file in the title folder - no plaintext without console keys.

## Verification
- **Verified:** that the title is installed on my own console; its application title ID; that it is the largest single install on the card (~935 MB); that a separate ~14 MB update title exists for it; that its extdata slot holds only a couple of files; and that stored content is not readable without keys.
- **Not verified:** nothing inside the sealed content was read - no code, models, strings or file lists - and no save or RomFS layout was recovered. The relationship between this install and the earlier non-Welcome-amiibo release is platform/community knowledge, not a measurement from this card. No overlay was built, installed or tested.

## Gotchas
1. **Symptom.** Your installed size disagrees with a figure quoted online. **Cause.** The quote probably covers only the base app, or only one release revision. **Fix.** Measure app + update yourself and name the revision you have.
2. **Symptom.** You edit a file in the base app and the game still shows the old version. **Cause.** The update title ships its own copy of that file and wins. **Fix.** Overlay the update title too, or target a file the update does not carry.
3. **Symptom.** You expect the save to be in extdata because the folder exists, and it is nearly empty. **Cause.** extdata is per-title user state, not necessarily the game's save. **Fix.** Treat extdata and the title's own save area as different things; identify which holds what before deleting anything.
4. **Symptom.** Another owner's identical-looking game has a different title ID. **Cause.** The expanded revision shipped both standalone and as an update. **Fix.** Compare revision names, not folder sizes.

## Assets
None - reconnaissance only; nothing was authored, decrypted or written.

## Open questions
- Whether the update title's RomFS duplicates base files or only adds them, which decides how much a single overlay must cover.
- Where the game's actual save area lives relative to the title folder, and whether it is as opaque as the content.
