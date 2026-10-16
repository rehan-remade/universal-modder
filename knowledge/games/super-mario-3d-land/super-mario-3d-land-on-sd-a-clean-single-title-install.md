---
kind: game
title: "Super Mario 3D Land on SD: a clean single-title install"
game: "Super Mario 3D Land"
games_also: []
game_version: "SD install on my own 3DS (title 00040000-00053f00, no update, no extdata)"
platform: console
engine: native
route: data
tools: ["Nintendo 3DS console (software list)", "SD card file listing"]
anti_cheat: "none relevant; nothing online was used"
status: in-progress
agents: ["OpenCode (Big Pickle)"]
humans: ["GeoffreyMba"]
date: 2026-10-16
links: []
tags: [nintendo-3ds, ctr-sdk, sd-install, encrypted-content, layeredfs, romfs]
---

# Super Mario 3D Land on SD: a clean single-title install

> The simplest installed-3DS footprint there is: one app title, no update, no add-on content, no extdata. A good
> baseline to compare the messier installs against. Read-only inspection of my own console; nothing was
> decrypted and nothing on the card was changed.

## Setup
- **Copy used:** my own 3DS. Super Mario 3D Land is installed on the console under title `00040000-00053f00`. Inspected through the console's software list and the SD card's folder layout; no decryption keys were used.
- **Tools:** the console's software list and a plain SD-card file listing. Nothing was launched from outside the console and no title content was read.
- **On the card:** a single app title around 290 MB, with no update slot and no extdata slot for this title.

## Route and why
Route: **data** - the content is sealed, so the lever is a LayeredFS RomFS overlay that presents replacement files at runtime, exactly the route the community Mario Kart 7 mod uses on the same console. Editing the card directly was dropped: the title content is encrypted per console, so a copied folder has nothing readable in it. This title is the clean case for that approach: because there is no update and no add-on content, there is exactly one RomFS to reason about.

## How the game works (what we had to learn)
- **A complete title can be a single folder.** Application, update and add-on content are separate title IDs, but none of the latter two are mandatory. Here only the application exists - no patch line, no paid content, no per-title user state. That is a normal, healthy install, not a trimmed or broken one.
- **The footprint is a useful yardstick.** Around 290 MB for a first-party 3D platformer is a reasonable mental anchor when you are trying to decide whether another title's folder looks suspiciously small or large.
- **The content is per-console encrypted.** The folder is opaque: no readable code, models or strings without the console's keys, which are out of scope here.
- **The engine is Nintendo first-party on the 3DS SDK family (CTR SDK).** Notes that say "NitroSDK" mean the DS SDK and are the wrong generation for any 3DS title.
- **RomFS is the modding surface.** A runtime overlay can replace level data, models, textures or UI without modifying the installed title, so the change is removable and survives as long as the file paths hold.

## Build steps (reproduce this pass)
1. On the console, note the title ID and installed size in the software list.
2. On a PC, find the title's folder in the SD card's Nintendo 3DS tree and confirm its size.
3. Look for a matching update folder and a matching extdata folder - both are absent for this title, which is the interesting part of the observation.
4. Confirm the wall: open the largest file in the title folder - no plaintext without console keys.
5. Compare this footprint with a title that does have update/extra-data folders, to calibrate what "normal" looks like.

## Verification
- **Verified:** that the title is installed on my own console; its application title ID; an install size of roughly 290 MB; that no update title and no extdata slot exist for it; and that stored content is not readable without keys.
- **Not verified:** nothing inside the sealed content was read - no code, level data, models or strings. The absence of update/extdata is from a single console listing at one point in time. No overlay was built, installed or tested.

## Gotchas
1. **Symptom.** You go looking for the update folder or extdata slot, do not find one, and assume the install is damaged. **Cause.** Neither is mandatory; this title simply has neither. **Fix.** Treat application-only as a valid shape.
2. **Symptom.** You plan a mod that also has to cover "the patch", then find there is no patch. **Cause.** Not every title has an update line. **Fix.** Check for the `0004000e-...` folder before designing around it - one RomFS is the easy case.
3. **Symptom.** You compare this install against a bigger first-party title and think something is missing. **Cause.** Titles differ hugely in content size; only the presence of extra folders is meaningful. **Fix.** Compare folder *roles*, not raw megabytes.
4. **Symptom.** You open the folder expecting readable files. **Cause.** Per-console encryption on installed titles. **Fix.** Work through a runtime LayeredFS layer; do not expect plaintext from the card.

## Assets
None - reconnaissance only; nothing was authored, decrypted or written.

## Open questions
- Whether a retail-installed title differs at all from an eShop-purchased one in folder layout, or only in the ticket behind it.
- How much of the RomFS layout could be inferred without decryption, purely from a community overlay's paths, as a way to skip the keys entirely.
