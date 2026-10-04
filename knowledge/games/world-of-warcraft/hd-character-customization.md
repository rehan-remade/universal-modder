---
kind: game
title: 'Retail faces, hairstyles and hair colours on the 3.3.5a HD human: CharSections, skin-section and compositor rules'
game: World of Warcraft
games_also: []
game_version: 'Wrath of the Lich King client 3.3.5a (build 12340) with an HD character model pack; source data from the retail 12.x client; AzerothCore server'
platform: windows
engine: native
route: data
tools: [Python 3.12 (CASC/DB2 readers, BLP writer, M2/skin editor), numpy, scipy, Pillow, wow.export (reference for the makeup blend)]
anti_cheat: 'none touched: client data files on a private server'
status: working
agents:
- Claude Code (Opus 5.5)
humans: [RedSuper]
date: '2026-10-02'
links: ['https://wowdev.wiki/DB/CharSections', 'https://wowdev.wiki/M2/.skin', 'https://github.com/Kruithne/wow.export']
tags: [character-customization, charsections, barbershop, hair, faces, skin, compositor, blp, retail-port]
---
# Retail faces, hairstyles and hair colours on the 3.3.5a HD human: CharSections, skin-section and compositor rules

> A retail (12.x) human female face and skin, three retail hairstyles (Side Part, Long, Bald) and all 19 retail hair
> colours, added to the 3.3.5a HD human female for character creation and the barber, with matching server rows.
> It works in game after one broken first attempt, whose three failures are the rules below.

## Setup
- Client 3.3.5a with an HD model pack (the HD human female: 219 bones, one skin with 65,427 of 65,535 indices used).
- Source: retail customization tables and textures read from the retail install (CASC, WDC5 tables found by name
  hash).
- Output: one patch MPQ (plus its locale copy for the DBCs) and server override rows.

## Route and why
Data only: new hair geometry appended to the body model's skin, new `CharSections` / `CharHairGeosets` /
`BarberShopStyle` rows, textures in the client's own formats. No code.

## How the game works (what we had to learn)
**Customization tables**
- `CharSections.dbc`: type 0 skin, 1 face, 2 facial hair, 3 hair, 4 underwear; a variation index, a colour index,
  up to three textures. **Each (race, sex, type) block must be one contiguous run sorted by (variation, colour)**:
  rows appended at the end left the creator showing one face and everyone on the skin's default face. A later run
  replaces an earlier one.
- `CharHairGeosets` maps a hairstyle to a hair geoset; `BarberShopStyle` lists barber options. Both tolerate split
  runs.

**The body model's skin**
- Section starts must be ≤ 65,535; only the last section may run past it. Index ranges and vertex ranges must be
  contiguous and ascending **in section order**. Moving just the face section's index range broke every face and
  made a hairstyle spray spikes.
- The HD body has room for only about 4,460 more indices (with its largest base section moved to the end), which is
  why only three hairstyles fit.

**Textures**
- **Everything the character compositor builds from must be palettised BLP (encoding 1, 8-bit alpha)**: skin, face,
  underwear, extra. DXT1 drew green there. (World and model textures are the opposite: they must be DXT.)
- The HD face slot uses a WoD-era layout (256×192 at (0, 320) of the 512 body texture), not retail's; transfer goes
  through the 3D surface. The HD face mesh is retail's face-shape geoset 3202 apart from the eyeballs (687 of 819
  vertices identical).
- The skin's "extra" texture uses retail's face-region layout; it textures the ears and mouth.
- HD scalp textures are fully transparent.
- Hair UVs are retail's plus whole-number offsets on a repeating texture; retail ships three hair texture sets, one
  per hairstyle group, each with the same 19 colours.
- Makeup layers blend like wow.export's overlay mode: the branch is on the layer's colour, not the base.

**Server**
- This AzerothCore build doesn't validate appearance at character creation; only the barber checks
  `BarberShopStyle` ids. The `charsections_dbc` / `barbershopstyle_dbc` override tables load at startup.
- Random bots roll a face (which also sets the skin colour) and a hair row from the server's CharSections,
  ignoring flags. To give bots the new hair but never a personal face, ship only the hair rows to the server.

## Build steps
1. Read retail's `ChrCustomizationOption/Choice/Element/Material` and the model's texture layer layout; pick the
   choices to port.
2. Hair: retail hair geometry mapped onto the HD skeleton by bone CRC, appended as new hair geosets at the end of the
   skin, sections kept in order.
3. Faces and skins: bake retail textures into the HD layouts through the surface; write palettised BLPs.
4. Insert CharSections rows **inside** their blocks in sorted order; add `CharHairGeosets` and `BarberShopStyle`
   rows; pack; add the server rows; restart.

## Verification
- Offline: read-back of the skin (section order, ranges), texture decode checks, renders of each face and style.
- In game with the human: the creator, the barber, existing characters, random bots.

## Gotchas
1. **One face left in the creator; everyone on the default face.** **Cause:** CharSections rows appended outside
   their block. **Fix:** insert into the block, sorted by (variation, colour).
2. **Every face broken and a hairstyle spiking.** **Cause:** a skin section moved out of order. **Fix:** keep sections,
   index ranges and vertex ranges ascending together; remap batches.
3. **Skin and face drew green.** **Cause:** DXT1 in the compositor. **Fix:** palettised BLP with an 8-bit alpha plane.
4. **Hair textures didn't line up in a first comparison.** **Cause:** retail UVs differ by whole numbers. **Fix:**
   compare modulo 1 and check the repeat flags.
5. **Retail tables couldn't be found by file name.** **Cause:** DB2 files are by id. **Fix:** match each WDC5 file's
   table hash against the hash of the table name (upper-cased).
6. **Makeup colour wrong.** **Cause:** overlay branched on the base colour. **Fix:** branch on the layer, as
   wow.export does.

## Open questions
- More hairstyles need the index budget a DLL-attached hair model would give.
