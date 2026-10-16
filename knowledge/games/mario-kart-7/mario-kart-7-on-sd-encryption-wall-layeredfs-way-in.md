---
kind: game
title: "Mario Kart 7 on SD: encryption wall, LayeredFS way in"
game: "Mario Kart 7"
games_also: ["CTGP-7"]
game_version: "SD install on my own 3DS (title 00040000-00030700) + 5 MB update"
platform: console
engine: native
route: data
tools: ["Nintendo 3DS console (software list)", "SD card file listing"]
anti_cheat: "Nintendo NEX netplay exists; nothing online was touched"
status: in-progress
agents: ["OpenCode (Big Pickle)"]
humans: ["GeoffreyMba"]
date: 2026-10-16
links: []
tags: [nintendo-3ds, ctr-sdk, sd-install, extdata, encrypted-content, layeredfs, romfs]
---

# Mario Kart 7 on SD: encryption wall, LayeredFS way in

> What an installed Mario Kart 7 looks like from outside the console: one encrypted app title plus a
> separate update, a per-console extdata slot, and no readable content. That is exactly why the community
> CTGP-7 mod works by LayeredFS RomFS replacement instead of editing files on the card. Read-only
> inspection of my own 3DS install; nothing was run beyond the console's own listings.

## Setup
- **Copy used:** my own 3DS - the title is installed on the console (SD install, title `00040000-00030700`) with a 5 MB update. It was inspected through the console's own software list and the SD card's folder layout; no decryption keys were used.
- **Tools:** the 3DS itself (software list) and a plain SD-card file listing. Nothing was executed and no title content was decrypted.
- **On the card:** the base app (about 638 MB, the largest install on this card after Animal Crossing NL:WA), an update under the `0004000e-00030700` title slot, and three files of extra data under extdata `00000307`.

## Route and why
Route: **data** - the practical way to touch an installed first-party title is to replace its data at runtime, so this note is about the SD layout and the RomFS route. Static file editing was considered and dropped immediately: the content is encrypted per console, so there is nothing to read or patch on the card without keys. That is also why CTGP-7, the community track mod for this game, ships a `gamefs/` RomFS overlay instead of a patched game.

## How the game works (what we had to learn)
- **An installed 3DS title is three things, not one.** The app lives under the SD card's Nintendo 3DS title tree; an update is a *separate* title (the `0004000e-...` range); and DLC, when present, is another (`0004008c-...`). Sizes quoted online usually cover all of them, so a single folder can look wrong when it is only the base app.
- **Save and extra data are separate as well** (extdata): per-title, per-user state in its own slot - here a small three-file store, not the game's content.
- **The content is per-console encrypted.** A copied title folder is an opaque container: no readable code, model or string data. Reading it needs the console's keys, which is out of scope here.
- **The base engine is Nintendo first-party on the 3DS SDK family (CTR SDK).** The DS-era "NitroSDK" label that appears in older notes is the wrong generation for any 3DS title.
- **RomFS is the modding surface.** Because code and content are sealed, the workable route is a layered filesystem: a loader presents replacement files ahead of the game's own RomFS at runtime. CTGP-7 does exactly this for Mario Kart 7 - custom courses ship as RomFS-path overrides, with the base game untouched.

## Build steps (reproduce this pass)
1. On the console, note the title's ID and installed size in the software list.
2. On a PC, open the SD card's Nintendo 3DS tree and find the title folder, the update folder and the extdata folder for the same title.
3. Compare sizes and slots so you can tell app, update, DLC and extdata apart.
4. Confirm the wall: open the title's main container - there is no plaintext inside without console keys.

## Verification
- **Verified:** that the title is installed on my own console; its title ID and roughly 638 MB install size; that a separate ~5 MB update exists; that a small extdata slot exists; and that the content is encrypted (nothing plaintext is readable).
- **Not verified:** nothing inside the encrypted content was read - no code, textures, strings or file lists. No mod was built and no LayeredFS layer was installed or tested. The engine internals are platform-level knowledge, not read from this install.

## Gotchas
1. **Symptom.** You copy the title folder to a PC and find nothing human-readable. **Cause:** per-console encryption on installed 3DS titles. **Fix:** work on the console or use a runtime LayeredFS overlay; do not expect plaintext from the card.
2. **Symptom.** The install size looks smaller than the "size on card" you expected. **Cause:** the update and any DLC are separate titles with their own IDs. **Fix:** add app + update (+ DLC) together.
3. **Symptom.** You change a file on the SD card and the game ignores it. **Cause:** the game reads its own sealed RomFS, not the loose file. **Fix:** override it through LayeredFS at runtime.
4. **Symptom.** A modded track or asset does not appear. **Cause:** the overlay is only active when the game is launched through the mod's loader with CFW enabled. **Fix:** launch via the loader, not the home-menu icon.

## Assets
None - reconnaissance only; nothing was authored or changed on the card.

## Open questions
- Whether the RomFS path layout can be recovered without decrypting the title, purely from a mod's overlay paths.
- How much of the update changes the base install, beyond the size difference.
