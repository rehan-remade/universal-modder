---
kind: game
title: "Swapdoodle on SD: a small app with its lessons in a separate DLC title"
game: "Swapdoodle"
games_also: []
game_version: "SD install on my own 3DS (title 00040000-001a2e00 plus a 0004008c- DLC title)"
platform: console
engine: native
route: data
tools: ["Nintendo 3DS console (software list)", "SD card file listing"]
anti_cheat: "none relevant; no online service was used"
status: in-progress
agents: ["OpenCode (Big Pickle)"]
humans: ["GeoffreyMba"]
date: 2026-10-16
links: []
tags: [nintendo-3ds, ctr-sdk, sd-install, dlc, extdata, encrypted-content, layeredfs, romfs]
---

# Swapdoodle on SD: a small app with its lessons in a separate DLC title

> Swapdoodle is a free-to-start drawing app: a small base title, a separate add-on-content title for the paid
> lesson/stationery packs, and a per-title extdata store. Read-only inspection of my own console; nothing was
> decrypted and nothing on the card was changed.

## Setup
- **Copy used:** my own 3DS. Swapdoodle is installed on the console under title `00040000-001a2e00`, with add-on content in a `0004008c-001a2e00` title. Inspected through the console's software list and the SD card's folder layout; no decryption keys were used.
- **Tools:** the console's software list and a plain SD-card file listing. Nothing was launched from outside the console and no title content was read.
- **On the card:** a small base app (about 20 MB), an add-on-content title for the paid packs, and one extdata slot (`00001a2e`) with a few dozen files - the user's doodles and lesson state, not game content.

## Route and why
Route: **data** - the app is sealed, so any visual or text change goes through a LayeredFS RomFS overlay at runtime. Editing the card directly was dropped: the content is encrypted per console. And, as with other free-to-start apps, the interesting question is not "how do I patch the app" but "which title holds the thing I want to change".

## How the game works (what we had to learn)
- **Free-to-start means the content is split.** The base app is small on purpose; the lessons and stationery that users actually unlock live in a separate add-on-content title (`0004008c-...`) with its own ID and its own sealed RomFS. Two targets, not one.
- **The app, the DLC and the user state are three different things.** Application title, add-on-content title, and the extdata slot. Sizes quoted for the "game" almost never add these up, so a folder that looks too small is normal.
- **extdata holds the user's work** - the doodles and per-lesson progress - the same split seen in the related Nintendo Letter Box app. If you care about keeping drawings, that is the folder to copy, not the title.
- **The content is per-console encrypted.** Title folders and extdata are keyed to the console; copying them to a PC yields an opaque blob.
- **The engine is Nintendo first-party on the 3DS SDK family (CTR SDK).** Older write-ups say "NitroSDK"; that is the DS SDK and the wrong generation for a 3DS title.
- **RomFS is the modding surface.** A loader presents replacement files ahead of the game's own RomFS at runtime, leaving the installed title untouched.

## Build steps (reproduce this pass)
1. On the console, note the app's title ID and installed size.
2. On a PC, find the app folder in the SD card's Nintendo 3DS tree, then the add-on-content folder for the same title ID.
3. Find the extdata slot for the same title and count its files - that is the user's own content.
4. Confirm the wall: open the app's largest file - no plaintext without console keys.

## Verification
- **Verified:** that the app is installed on my own console; its application title ID; that an add-on-content title exists in the `0004008c-...` range for the same title; that a base app of about 20 MB is paired with a small extdata slot of a few dozen files; and that stored content is not readable without keys.
- **Not verified:** nothing inside the sealed content was read - no lesson data, no doodle format. The link between a specific paid pack and a specific DLC file was not measured. No overlay was built or tested.

## Gotchas
1. **Symptom.** You buy a lesson pack and the app's folder does not change. **Cause.** The pack is DLC, a separate title with its own ID. **Fix.** Look for the `0004008c-...` folder, not the app.
2. **Symptom.** A stationery or lesson retexture does nothing, while an app retexture works. **Cause.** You overlaid the wrong title's RomFS. **Fix.** Confirm which title owns the file you are replacing.
3. **Symptom.** The user's doodles are missing after moving "the game". **Cause.** The doodles are extdata, which lives outside the title. **Fix.** Copy the extdata slot with the title.
4. **Symptom.** Nothing human-readable appears when you open the folders. **Cause.** Per-console encryption on installed titles. **Fix.** Use a runtime LayeredFS layer; do not expect plaintext from the card.

## Assets
None - reconnaissance only; nothing was authored, decrypted or written.

## Open questions
- Whether the lesson packs are repacked archives holding first-party asset types, which would make them reachable with retail-format tooling under LayeredFS.
- How the cart-style "stationery" assets relate to the DLC title versus the base app.
