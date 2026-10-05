---
kind: game
title: 'Per-item skinned armour on the 3.3.5a client: a proxy-DLL engine extension (add-on models, body texture layers, tabards)'
game: World of Warcraft
games_also: []
game_version: 'Wrath of the Lich King client 3.3.5a (build 12340, enUS, 32-bit, Direct3D 9) on a self-hosted AzerothCore server'
platform: windows
engine: native
route: native-hook
tools: [MinGW-w64 i686 gcc (in WSL), capstone, Ghidra 12.1, Python 3.12, Blender]
anti_cheat: 'none touched: a private server the user runs; Warden is configured server-side; the DLL only changes how worn items are drawn'
status: working
agents:
- Claude Code (Opus 5.5)
humans: [RedSuper]
date: '2026-10-04'
links: ['https://wowdev.wiki/M2', 'https://github.com/Deamon87/WebWowViewerCpp']
tags: [m2, skinned-attachments, proxy-dll, inline-hooks, bone-matrices, character-component, body-texture, tabard, geosets]
---
# Per-item skinned armour on the 3.3.5a client: a proxy-DLL engine extension (add-on models, body texture layers, tabards)

> In 3.3.5a, body armour is texture paint plus geoset switches inside the character model; real 3D armour per
> item is impossible with data alone. A small `version.dll` proxy adds the one missing engine behaviour: models
> attached to the character that bend with its skeleton ("collections", as later expansions have). Each item gets
> its own add-on model, shown only while that item is worn. It runs in the real client (in-game milestones with
> the human after every step) together with retail armour ported straight from the modern client. Later versions
> also patch the body-texture layer table and the tabard geosets.

## Setup
- Client 3.3.5a build 12340, 32-bit, image base 0x400000; an HD character model pack (HumanFemale 219 bones,
  HumanMale 228). Server: AzerothCore (WotLK) the user hosts.
- Build: `i686-w64-mingw32-gcc` in WSL produces `version.dll`; unit tests are built the same way and run on Windows.
- Install: `version.dll` + an `.ini` next to `Wow.exe`. Undo: delete `version.dll`. Players without it see the
  textures only; nothing breaks.

## Route and why
Use this DLL only with a server you run: on other servers, Warden can scan the client for hooks like these.
**Native hook, because every data route failed in the client:**
- the skin section `Level` field (meant to address more than 65,535 indices) is not supported: using it scrambled
  the whole human female model for everyone, in both readings;
- the HD body's skin already uses 65,427 of the 65,535 indices a section can start at; only one section may start
  below 65,536 and run past it, so at most one custom 3D body set per body model;
- a model attached to the character does not inherit its animation (a helm carrying a full body skeleton and
  skinned thigh plates showed the plates frozen in the stand pose, moving only with the head).

The DLL keeps the data route for everything else: models, textures and DBC rows still ship in a patch MPQ.

## How the game works (what we had to learn)
All addresses are build 12340; every one was verified by disassembly (capstone, later Ghidra) before use, and the
DLL refuses to patch unless all of its byte signatures match.

**Model and attachment pass**
- `CM2Model::Animate` (`0x82F0F0`) ends with the attachment pass (`0x82E550`): it walks the model's children
  (first child `+0x58`, next sibling `+0x60`) and animates each one with the parent's bone matrix × the attachment
  offset.
- Model fields: shared data `+0x2C` (raw M2 header at `shared+0x150`), parent `+0x48`, attach id `+0x50`, bone
  states `+0x94` (stride `0xAC`), **bone matrices `+0x98`** (model→view, one per bone; the draw-time palette upload
  reads them through the bone lookup), world `+0xB4`, model→view `+0xF4`, frame stamp `+0x3C`.
- M2 bone records (stride `0x58`): parent `+0x08`, **name CRC `+0x0C`**, pivot `+0x4C`. Every HD body bone has a
  unique CRC; retail does its own collection matching by that CRC.
- `AttachToParent` (`0x831630`) with an unknown attach id and `keep = 1` sets flag `0x40000`: the child stays
  attached at the root.
- The model copy used by the character sheet (`0x834810`) re-attaches children with `keep = 0`, which drops
  root-attached add-ons.
- **Attachment passes run on several threads at once**: any static scratch buffer in a hook needs a lock.

**Character component (worn items)**
- `CCharacterComponent`: race `+0x18`, sex `+0x1C`, body model `+0x38`, display id per slot at `+0x428 + slot*4`.
- `AddItem` (`0x4F2640`) and `RemoveItem` (`0x4EE460`); but the game's unequip paths (`0x4EE6D0`, `0x4EEB30`) clear
  slots without calling `RemoveItem`.
- `ItemDisplayInfo` record copy: Model0 `+4`, Model1 `+8`, Icon1 `+0x18`, size `0x64`; `GetRecord` `0x4CFD90`.
- The geoset update (`0x4ED900`) reads each slot's display row **from the DB by id**, not from the record passed
  to `AddItem`; `SetGeosets` (`0x82C7C0`, thiscall(model, lo, hi, visible)) is what actually shows/hides groups.
- `ReplaceTexture` (`0x825260`, thiscall(model, type, texture)) swaps a model's replaceable texture; type 1 is
  the character's composited body texture.

**Body texture compositing**
- `int layer[12 slots][10 regions]` at `0x9F6A00`: -1 = the slot never paints that region, higher = on top
  (slots 2 shirt, 3 chest, 4 belt, 5 legs, 6 boots, 7 wrist, 8 hands, 9 tabard; regions 0 arm-up … 7 foot).
  Tabards are -1 on the upper-leg region, so no tabard can paint the waist band of the HD bodies.
- Each region's paint function walks a **fixed number of layers** (upper leg: 0–2), in two code paths (batched
  `0x4E8E70…`, direct `0x4F09D0…`). Raising a layer past that count makes the item vanish.
- Guild tabards are built by their own compositor (`0x4EC1C0`, cleared by `0x4EC0E0`) from fixed-name
  `GuildEmblems` files, torso only.

## Build steps
1. **Proxy:** export the 17 `version.dll` functions as jumps into the real system DLL; in any process that isn't
   the expected `Wow.exe`, do nothing else.
2. **Signatures:** check every byte pattern the hooks touch; one mismatch → no patching at all.
3. **Hooks** (hand-rolled inline detours with trampolines):
   - `AddItem`: if the slot's display row has `Model0` starting with a private marker (`TKC_`), attach
     `Collections\<Model0>_<race><sex>.m2` through the game's own attach function with a private attach id
     (marker + slot) and `keep = 1`; `Model1` lists which race/sex variants exist.
   - `RemoveItem` and both unequip paths: detach it.
   - `AttachToParent`: force `keep = 1` for the private ids (character sheet).
   - After the attachment pass: copy the body's bone matrices (`+0x98`) into each add-on, mapped by bone-name CRC.
     Copying after the pass (rather than during) removed a one-frame lag when turning.
4. **Add-on models** (built by our M2 writer): the body's bone records with CRCs intact and every track emptied;
   one embedded Stand sequence (`variationNext = -1`, frequency 32767); only that item's geometry, weighted to body
   bones, ≤ 53 bones per section; hard-coded textures; the body's bounding box for culling.
5. **Display rows:** stock rows stay stock except one marker in `Icon1` pointing at a companion row per race/sex
   (`TKC:<code>=<row>`); the companion row carries the add-on's look, so races without a variant get plain textures.
6. **Tabards** (later versions):
   - smoothed-chest add-on (retail's tabard chest geoset) textured live with the composited body texture
     (`ReplaceTexture` type 1 after the pass);
   - after the geoset update, `SetGeosets` hides the tabard flaps under belts marked to clip them (retail's flags
     `0x200` front / `0x200000` both);
   - waist strips: patch the layer table (tabard upper-leg 2, belt moved up) **and** widen both upper-leg paint
     loops; hook the guild compositor to add upper-leg layers for guild tabards.

## Verification
- Milestones checked in game by the human (attach without bones, bone copy, per-item show/hide, character select,
  dressing room, character sheet, a long soak for frame rate: no change).
- A per-session log (attachments, hooks, timing) truncated at each launch; unit tests for the CRC map, record
  parsing and add-on builder outputs; read-back renders of every built add-on.
- Not verified: other client builds (the signature check refuses them by design).

## Gotchas
1. **Add-ons vanished in the character sheet.** **Cause:** its model copy re-attaches children with `keep = 0`.
   **Fix:** hook `AttachToParent` and force `keep = 1` for the private attach ids.
2. **The chest piece stayed on after unequipping a tabard.** **Cause:** the game unequips through two functions
   that never call `RemoveItem`. **Fix:** hook both unequip paths.
3. **Hiding geosets through a modified display record did nothing.** **Cause:** the geoset update reads the row
   from the DB by display id. **Fix:** hook after it and call `SetGeosets` yourself.
4. **Tabard waist strips never drew, although the textures were right.** **Cause:** the layer table gives tabards
   -1 on the upper leg. **Fix:** patch the table at startup.
5. **Then every belt vanished, with or without a tabard.** **Cause:** the belt was moved to layer 3 while the
   upper-leg paint loops only walk layers 0–2. **Fix:** widen both loops; any layer change must check its region's
   loops in both paint paths.
6. **Other characters' add-ons got the wrong bone matrices.** **Cause:** attachment passes run on several threads
   and a hook used a static scratch table. **Fix:** one lock per hook module.
7. **One-frame lag when rotating.** **Cause:** copying matrices while the pass was still running. **Fix:** copy after
   the pass.
8. **Gauntlet plates lit dark.** **Cause:** inside-out faces in the source `.blend` (Blender's preview hides it).
   **Fix:** check winding against normals at build time and flip.
9. **Particles on an add-on stayed in the stand pose.** **Cause:** an emitter follows the add-on's own static
   skeleton. **Fix:** effects only on rigid attached models (helm, shoulders, weapons).
10. **Crash a Stand loop or two after equipping.** **Cause:** a single-sequence model whose Stand links a variation;
    the client's bounds read (`0x825750`) uses it unchecked. **Fix:** `variationNext = -1`, frequency 32767.
11. **Windows Defender quarantined old copies of the DLL.** **Cause:** a heuristic false positive on our unsigned
    proxy `version.dll` builds; any copy outside an excluded folder gets scanned when something reads it (a
    recursive search over the work folder was enough). **Fix:** don't add Defender exclusions or turn protection
    off yourself. Tell the human; they decide whether to restore the file or report the false positive.

## Assets
Add-on geometry comes from a hand refit (one set) and from retail's own collection models (Tier 2 and later sets,
converted by script); textures are retail's or recoloured locally. No generated art, no paid services.

## Open questions
- Collisions between worn items and other units (retail has a category for it) are not implemented.
- A male refit of the hand-made set needs a refit source matched to the HD male body.
