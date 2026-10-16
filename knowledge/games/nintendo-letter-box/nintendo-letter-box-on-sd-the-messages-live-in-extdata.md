---
kind: game
title: "Nintendo Letter Box on SD: the messages live in extdata, not the app"
game: "Nintendo Letter Box"
games_also: ["Swapnote"]
game_version: "SD install on my own 3DS (title 00040000-00051800)"
platform: console
engine: native
route: data
tools: ["Nintendo 3DS console (software list)", "SD card file listing"]
anti_cheat: "none relevant; the online/SpotPass service is long dead and was not used"
status: in-progress
agents: ["OpenCode (Big Pickle)"]
humans: ["GeoffreyMba"]
date: 2026-10-16
links: []
tags: [nintendo-3ds, ctr-sdk, sd-install, extdata, encrypted-content, layeredfs, romfs, discontinued-service]
---

# Nintendo Letter Box on SD: the messages live in extdata, not the app

> The installed Nintendo Letter Box (Swapnote outside Europe) is a ~12 MB app whose interesting half is a large
> extdata store of user messages - not the title. Read-only inspection of my own console; nothing was decrypted
> and nothing on the card was changed.

## Setup
- **Copy used:** my own 3DS. Nintendo Letter Box is installed on the console under title `00040000-00051800`. Inspected through the console's software list and the SD card's folder layout; no decryption keys were used.
- **Tools:** the console's software list and a plain SD-card file listing. Nothing was launched from outside the console and no title content was read.
- **On the card:** a small app title (about 12 MB, no update title present) and a *disproportionately large* extdata slot (`00000518`) holding well over a hundred files - the stored notes and their attachments, not game content.

## Route and why
Route: **data** - if you want to change how the app looks or behaves you replace data at runtime through a LayeredFS RomFS overlay, because the title itself is sealed. But for this app that is mostly the wrong target: the part a user cares about (their notes) is *extdata*, so the more useful work is inspecting and backing up that store. Editing the card directly was dropped: the title content is encrypted per console, and the extdata store is only meaningful to the console that wrote it.

## How the game works (what we had to learn)
- **User-created content is extdata.** The title holds the app; the notes, drawings and attachments live in the per-title extdata slot. That is why the app is tiny and the extdata store is not - the opposite of the pattern people expect from an installed game.
- **A title has no idea how big "the game" is.** Application, update and add-on-content titles are separate IDs, and extdata sits outside all of them. Here there is no update title at all, which is normal and not a broken install.
- **The service is gone.** SpotPass delivery for this app was discontinued years ago after its attachment feature was abused, so anything that depended on the server is dead. The local app still opens, and the local extdata store survives.
- **The content is per-console encrypted.** The title folder is opaque; the extdata store is keyed to the console that created it. Neither is readable by copying files to a PC.
- **The engine is Nintendo first-party on the 3DS SDK family (CTR SDK).** "NitroSDK" is the DS SDK and the wrong generation for a 3DS title.
- **RomFS is the code-side modding surface; extdata is the data side.** Know which one a change belongs to before you start.

## Build steps (reproduce this pass)
1. On the console, open the software list and note the app's title ID.
2. On a PC, locate that title's folder in the SD card's Nintendo 3DS tree and note its size.
3. Locate the extdata folder for the same title and compare: the extdata store is where the user's notes are.
4. Back up the extdata slot, not just the title folder, if you care about the notes.
5. Confirm the wall: open the title's main container - no plaintext without console keys.

## Verification
- **Verified:** that the app is installed on my own console; its application title ID; that the app title is small; that a much larger extdata slot exists for the same title with well over a hundred files; that no update title is present; and that stored content is not readable without keys.
- **Not verified:** nothing inside the sealed content or the extdata store was read or parsed - no message format, no attachment structure. The exact file count and the "no update" observation are from a single console listing. No overlay was built or tested and no note was restored.

## Gotchas
1. **Symptom.** You back up "the game" and the user's notes are still lost after a restore. **Cause.** The notes are extdata, which lives outside the title. **Fix.** Back up the extdata slot separately; that is the part with the user's work in it.
2. **Symptom.** SpotPass/Swapnote features never work, and you assume a bad install. **Cause.** The service was discontinued; the client is fine. **Fix.** Treat server features as gone and work locally.
3. **Symptom.** You hunt for message files inside the title folder and find nothing. **Cause.** Wrong half of the app: the title is code and UI, the messages are extdata. **Fix.** Go to the extdata slot for the same title ID.
4. **Symptom.** You copy the extdata folder to another console and it refuses to load. **Cause.** Extdata is keyed to the console that wrote it. **Fix.** Keep the store with its console; a PC copy is only an opaque archive.

## Assets
None - reconnaissance only; nothing was authored, decrypted or written.

## Open questions
- The layout of the extdata store (whether notes and attachments are separate files or one container) without decrypting the title.
- How the app's own RomFS is organised, which would only matter for a UI retexture over LayeredFS.
