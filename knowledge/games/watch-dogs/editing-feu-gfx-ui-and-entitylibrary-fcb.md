---
kind: game
title: "Watch Dogs 1: editing .feu/.gfx UI components and rebuilding entitylibrary_rt.fcb"
game: "Watch Dogs"
games_also: []
game_version: "Watch Dogs 1 retail (PC)"
platform: windows
engine: unknown
route: asset-only
tools: ["hV WD Modding Kit (hV_WD1ModdingKit.exe, FCBastard.exe)", "JPEXS Free Flash Decompiler", "Gibbed.Disrupt (unpack/pack)", "Astrogrep"]
anti_cheat: "none on WD1; all edits go into a packed patch archive — play offline with edited entity libraries, since online invasions connect you to other players"
status: in-progress
date: 2026-10-06
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links: []
tags: ["watch-dogs", "disrupt", "ui", "flash", "fcb", "entity-library"]
---

# Watch Dogs 1: editing `.feu`/`.gfx` UI components and rebuilding `entitylibrary_rt.fcb`

Two community-proven WD1 edit loops that never touch code: moving/retexturing Scaleform UI elements
(`.feu` → `.gfx` → JPEXS → back), and rebuilding the world entity library
(`entitylibrary_rt.fcb` → XML → back). Distilled from community tutorials (hV's WD Modding Kit
Discord, 2022-2023) with screenshots and result videos; this note records the workflow, not a
re-run of it.

## Setup

- **hV WD Modding Kit** — provides `hV_WD1ModdingKit.exe` (the `.feu` ⇄ `.gfx` converter; use the
  copy inside `Tools/hardVatsuki Tools/`, not any "latest" build) and `FCBastard.exe` (the `.fcb`
  ⇄ XML converter; use the copy in the kit's `FCBastard` folder — the folder's `types.default.xml`
  and `strings.txt` ship next to it and are required).
- **JPEXS Free Flash Decompiler** for the `.gfx` (SWF-like) editing, plus a Java runtime to run it.
- **Gibbed.Disrupt** unpack/pack for the `.dat`/`.fat` archives you will place results into.
- **Astrogrep** (or any recursive text search) for finding which UI file to edit.

## Route

### Locating the file you need

There is no index of which `.feu` does what. Unpack the archives you care about (`patch`, `common`,
`windy_city`) with Gibbed, then search the unpacked tree for a distinctive string. The proven
example: searching NPC names that appear in the call UI (`clara`, `damien`, `rabbit`) lands on
`ui\fire\bin\gh_phonecall.feu`. If the string is inside a compiled `.gfx`, search the *converted*
text or the file names instead.

### `.feu` → `.gfx` → edit → `.feu` (UI position example)

1. Find the file, e.g. `\ui\fire\bin\gh_adrenaline.feu` (the focus/adrenaline HUD element).
2. Drag the `.feu` onto `hV_WD1ModdingKit.exe` → you get `gh_adrenaline.gfx`.
3. Open the `.gfx` in JPEXS. Click the `.gfx` root in the tree to see all shapes.
4. Click **Simple Editor**, then click the graphic element, then **Properties → Position and Size**.
5. Set **X / Y**. `X = 680, Y = 300` moves the element from the top-left corner to a roughly
   centered position (300 px down, 680 px right); the vanilla position is top-left.
6. Save, then drag the edited `.gfx` back onto `hV_WD1ModdingKit.exe` to produce the new `.feu`.
7. Place the new `.feu` into a `patch` archive at the same internal path and repack with Gibbed.

### Sprite-frame edits (removing a flicker effect)

- The portrait in `gh_phonecall.feu` flickers because sprite 132 carries noise frames alongside
  frame 1. In JPEXS: shape object 103 links to sprites 131/132/133/153; prune the non-portrait
  frames from sprite 132.
- **Use `DEL` ("Remove"), never `SHIFT+DEL` ("Remove with dependencies")** — dependencies removal
  breaks the phone-call UI entirely.
- Save the `.gfx`, re-drag it onto the kit to get the new `.feu`, repack.

### `entitylibrary_rt.fcb` (world entity library round-trip)

1. Drag `entitylibrary_rt.fcb` (lives in `patch\worlds\windy_city\generated\`) onto
   `FCBastard.exe`. Output: a `libraries/` folder of per-category `.xml` files
   (`Vehicle_Heavy.xml`, `Weapons.xml`, `Traffic.xml`, …) plus `entitylibrary_rt.xml`, which is the
   file list. Observed scale: **122 libraries, 464,264 nodes**.
2. Edit/replace the per-entity `.xml` files inside `libraries/`.
3. Drag the top-level `entitylibrary_rt.xml` back onto `FCBastard.exe` → it writes
   `bin/entitylibrary_rt.fcb`.
4. Replace `patch\worlds\windy_city\generated\entitylibrary_rt.fcb` with it, then pack the patch
   archive as usual.

## Verification

- **UI edits:** launch and look at the element — position changes and flicker removal are visible on
  sight (the source tutorials include before/after video). The source tutorial's result video shows
  the call portrait steady, no flicker.
- **FCB edits:** `FCBastard`'s own output is the check — it reports each library it loaded
  (`> Loaded library 'Weapons' via XML`) and writes the new `.fcb`; then confirm in-game that the
  entity changes took (spawn/traffic/weapon behavior).
- Round-trip safety: convert unmodified files first and diff; the tool is a re-serializer, so a
  no-op edit should produce a working (not necessarily byte-identical) `.fcb`.

## Gotchas

1. **`SHIFT+DEL` in JPEXS destroys dependent sprites.** Removing sprite frames with "Remove with
   dependencies" breaks `gh_phonecall`-style components; plain `DEL` removes only the frame.
2. **Pick the tool copy that ships with the kit.** The `FCBastard` folder's copy has its
   `types.default.xml`/`strings.txt` beside it; a lone `FCBastard.exe` (or a "latest" download)
   will not decode correctly.
3. **`entitylibrary_rt.xml` is the file *list*, not entity data.** Dragging the file list rebuilds
   the archive; dragging individual library files does not — the libraries folder must sit beside
   the file list when you rebuild.
4. **The rebuilt `.fcb` lands in a `bin\` subfolder**, not over the original; you must move it
   into `patch\worlds\windy_city\generated\` yourself.
5. **`.feu` ⇄ `.gfx` is a signature swap, not a real conversion.** A `.feu` is Flash with a `UEF`
   signature; the kit only rewrites the first three bytes (`UEF` ⇄ `GFX`), and JPEXS opens either
   form, so nothing is lost in the round-trip. Still keep a backup of the original `.feu` so you can
   fall back without re-converting.
6. **Search before you edit.** There is no UI-file manifest; the string-search-first method
   (Astrogrep over an unpacked tree) is the reliable way to find the responsible `.feu`.

**Credits:** hardVatsuki's hV Modding Kit, gibbed's Gibbed.Disrupt, jindrapetrik's JPEXS Free Flash
Decompiler, FCBastard's author, and the community tutorial authors (Discord, 2022-2023).
