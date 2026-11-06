---
kind: game
title: Posed corpses with gear on them, and a script-placed museum display, from generated plugin records
game: Skyrim Special Edition
games_also: []
game_version: '1.7.104 (Steam), Creation Kit 1.7.99 for placement only, SKSE64 2.3.1, powerofthree''s Papyrus Extender 6.5.2'
platform: windows
engine: creation
route: data
tools:
- Python plugin writer (own)
- own NIF reader and patcher (Python)
- Creation Kit (layout plugins only)
- Papyrus Compiler (Creation Kit)
- Mod Organizer 2
anti_cheat: none (single-player)
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-29'
links:
- https://en.uesp.net/wiki/Skyrim:Under_Saarthal
- https://en.uesp.net/wiki/Lore:Saarthal
tags:
- corpses
- ragdoll
- havok
- nif
- collision
- mannequin
- script-placed
- papyrus
- crosshair
- dragon-font
- message-box
- dialogue
- voice-files
- copied-records
- compatibility
---
# Posed corpses with gear on them, and a script-placed museum display, from generated plugin records

> The second part of a College of Winterhold questline overhaul, for Under Saarthal (MG02). It adds:
> - the dead of two old battles in Saarthal's inner ruin, with crowns on skulls, a sword through ribs and arrows in
>   a body;
> - twelve graves whose names show in the dragon alphabet on the crosshair;
> - a Miscellaneous objective to bring the Snow Elves' armour to Tolfdir, who answers in his own recorded voice;
> - a mannequin wearing what was handed in, placed by script in the College's Hall of the Elements, with a plaque;
> - Tolfdir's research notes, placed by script.
>
> The plugin is written by a Python script; the human placed things in Creation Kit layout plugins that the build
> reads. It took 66 dev builds over five days, each tested in game on a new game, and was packaged as a release
> after a run on an unmodded profile, which found the last bug (gotcha 11). The reward spell has its own note,
> `loot-detection-spell-papyrus-call-costs-and-lights.md`; the first part (the bridge) is
> `rebuilding-a-cut-gatekeeper-with-generated-plugin-records-di.md`.

## Setup
- **Game:** Skyrim SE 1.7.104 (Steam, Windows 11), run through Mod Organizer 2.
- **Requirements:** SKSE64 2.3.1 and powerofthree's Papyrus Extender 6.5.2, for the spell. What's in this note
  uses vanilla Papyrus only.
- **Creation Kit 1.7.99, for placement only.** The human placed references in two layout plugins of their own,
  one for Saarthal's inner ruin and one for the College. The build reads positions, rotations, scales and
  ragdoll poses from them, maps their form IDs to its own, and ignores the stray edits the CK makes to vanilla
  references nearby (it made several, every session).
- **The plugin:** ESL-flagged, masters Skyrim.esm and Dawnguard.esm, not localized, written by a Python builder
  that copies vanilla records and edits them. Meshes are patched by a small NIF reader and writer of our own,
  from your own game files at build time (see Assets for what a release may include).

## Route and why
- **Saarthal: references in the cell itself.** A ragdoll's pose is the placed reference's `XRGD`, so only a
  reference saved in the cell keeps it. The plugin carries Saarthal02's CELL record unchanged, as USMP and Ryn's
  Saarthal do, plus its own references in the cell's temporary group.
- **The College: no cell edits.** Several popular College mods rebuild those interiors, so everything there is
  placed by script, measured from a persistent vanilla reference (the Eye of Magnus's, MGEyeCollegeRef 00025224).
- **Voices: only Tolfdir's own recordings.** One of them is a Dragonborn.esm line recorded in his voice type. Its
  text and voice file are copied, so Dragonborn.esm isn't a master. The voice file is Bethesda's, so a release
  copies it from the player's own install at install time, as the cut-gatekeeper note's build step 4 describes.

## How the game works (what we had to learn)

### Things on and in posed corpses
Every model involved has collision: weapons' world models, the 1st-person sword (byte-identical), an arrow's
world model and its projectile, and the crown, cuirass and helmet ground models. Put a crown on a skull or a sword
through ribs, and the item and the ragdoll overlap:
- **If the item can move,** the body pushes it out: it floats, or falls to the floor.
- **If the item is held** (keyframed by vanilla's `defaultDisableHavokOnLoad`, which calls
  `SetMotionType(Motion_Keyframed)` on load), it pushes the body out of its pose.
- **Don't Havok Settle** (reference flag `0x20000000`) only skips the settle pass at load. The overlap still
  pushes. Vanilla does set it on about one posed skeleton in five, and the bodies need it anyway.
- **`ForceRemoveRagdollFromWorld`** throws the `XRGD` pose away (bodies upside down and through the floor) and
  makes the body unsearchable.

**What works:** show a copy, keep the real item inside the body.
- **The look:** a STAT whose model is a copy of the item's world model with collision removed. Clear every node's
  collision link and every collision object's target, and drop BSXFlags' Havok, Dynamic and Articulated bits.
  An ARMO's world model is its `MOD2`.
- **Arrows:** an AMMO's world nif (`DraugrArrow.nif`) has an `ArrowQuiver` node beside the arrow. The engine
  hides it for a placed arrow, and a STAT shows it, so set its hidden flag in the copy.
- **The item:** the real item sits in the corpse's inventory, on the corpse's own NPC_ copy with Respawn off.
- **The script** on the corpse (linked to its copies by a keyword chain):
  - `OnItemRemoved` hides as many copies as were taken;
  - `OnHit` hides them all and `DropObject()`s the real ones;
  - `OnLoad` shows only as many copies as the body still holds, which covers a cell reset.
- Items merely lying beside a body stay ordinary items with Don't Havok Settle.

### Copied vanilla records bring their own behaviour
Three times a copy kept doing what the original did:
- **`TreasCorpseSkeleton` is templated** on a live skeleton with Use Base Data (`0x80`). Our name ("Fallen
  Battlemage") and Respawn-off were ignored: the corpses said "Skeleton". The ACBS template flags are a u16 at
  **offset 18** (22 is the bleedout override). Clear `0x80` to use the copy's own name and flags.
- **A ragdoll pose fits only its own race.** `TreasCorpseSkeleton` and `TreasCorpseSkeletonRigid` (own race) each
  need their own copy.
- **`PlayerHouseMannequin`'s only package, MannequinStay (000D7510),** is a Travel to the editor location, and its
  begin, end and change fragments call `MoveToMyEditorLocation()`. A script-placed actor's editor location is
  where `PlaceAtMe` made it, so a package restart can send it back there. Our copy's only package is a copy of
  `MQ105DoNothing` (0006AF41): DoNothing template, no fragments, conditions or location.
- **A copied spell's own description and menu art** came along too: see the spell note.

### Placing things by script in a cell the player isn't in
- **A builder-filled script property can't hold a non-persistent reference.** The CK flags a reference persistent
  when a property is filled with it; our builder doesn't, so the property reads None whenever that cell isn't
  loaded. Look references up with the cell loaded, or anchor on one that's already persistent.
- **Placing in an unloaded cell didn't stick.** From Saarthal, we placed the display from the Eye and moved each
  piece to its spot with `MoveTo(anchor, dx, dy, dz)`:
  - the disabled plinth (an activator) read back still at the anchor;
  - the mannequin (an actor) read back on its spot, but stood 150 units off when the player arrived.

  Tolfdir's notes are placed the same way and were found on their spot, but no run showed that hall unloaded at
  the time. Don't count on it.
- **The placed actor's own `OnLoad` didn't fix it up on arrival** (no log line at all; whether it never came or
  its handler stalled is unknown). What worked:
  - **The player alias's `OnLocationChange`** into the cell's own location (the hall has one:
    `WinterholdCollegeHallofElementsLocation`, 0001EB7A; check the CELL's `XLCN`);
  - plus `OnPlayerLoadGame` when the game loads in that cell;
  - each waiting until the player's cell is the object's and `Is3DLoaded()`, then settling once a visit.
- **Move actors with `MoveTo`** to an `XMarkerHeading` on the spot, as vanilla's mannequins `MoveTo` their linked
  marker, and only when off it: a `MoveTo` can reload the 3D and fire `OnLoad` again. An early log had
  `SetPosition` not moving the actor, but MannequinStay may have sent it back, so that's unproven.
- **Small objects placed flush with a floor fall through it.** Start them a few units up.
- **Other College mods move furniture and change owners.** Immersive College moves Tolfdir's bed upstairs;
  Ultimate College keeps it there but gives it to Arniel; a third mod moves him to another hall. Fixed spots in his
  room, or spots measured from his bed or chest, landed in the wrong room or the wrong cell. The notes ended up
  in the hall where the display is, measured from the Eye.

### Mannequins and click boxes
- **A mannequin (ManakinRace) shows no crosshair prompt,** although activating it does fire its `OnActivate`.
  Vanilla gives each one `MannequinActivateTrig`, a primitive box on the placed reference, which a script can't
  create.
- **Our prompt:** activators placed around it with an invisible box mesh. `Clutter\WeaponRack\WRSingleTrigger02.nif`
  has **no collision at all** (a fade node, BSXFlags, one shape and its effect shader), so the crosshair passes
  through it. `WRSingleTrigger01.nif` is the same 32 x 16 x 128 box with a static-layer rigid body. Vanilla's
  named activators (the house weapon rack, Riften Jail's loose brick) use 01.
- **Solid boxes around an actor can push it,** so they're disabled whenever its AI is on (to pose it) and placed
  again after.
- **Whether `SetScale` scales collision at runtime** wasn't settled: place unscaled pieces.

### Text in the UI
- **The dragon alphabet on the crosshair:** an activator named `<font face='$DragonFont'>ASVALD</font>` draws
  runes on the crosshair. `$DragonFont` maps to `Dragon_script` in vanilla's `fontconfig.txt`.
  - Digraphs are digits (`2` is EI), and there's no C.
  - A message box shows the tags as text. A book page renders the font.
  - A blank verb (`RNAM` of one space) and no script make a stone that names itself and nothing more.
- **A message box's text has a length limit, about 1050 characters** (likely, not proven). A menu opened fine at
  about 1040 and crashed the game on opening at 1066. The build now asserts under 800.
- **Papyrus's string table ignores case, game-wide.** "Boots" in a property came out "boots", cased as some other
  script in the load order has it. Player-facing text is built whole by the build (every combination of pieces as
  one string), never joined from short words in Papyrus.
- **A note whose world model was a tombstone most likely crashed the game** when read: the reading menu shows the
  note's own model. Not proven (no crash logger).

### The hand-in
- **A Miscellaneous quest** (QUST type 6, start game enabled) with one objective whose text shows a global
  (`<Global=...>/4`, with the global in `QTGL`). The script counts with `ModObjectiveGlobal`.
- **Dialogue conditions read globals** that a player alias keeps current: an inventory event filter on a FormList
  of the four pieces, `OnItemAdded` and `OnItemRemoved`.
- **A random group of replies:** Random (`0x2`) on each INFO and Random End (`0x20`) on the last, with the same
  conditions, as vanilla's MG02 hellos do.
- **Check vanilla first:** Arniel already has a turn-in for Saarthal's rings
  (MG02ArnielTurnInItemsBranch). Ours for him was built, then removed.

## Build steps
1. **Layouts:** the human places references in the layout plugins in the CK. The build asserts the base of every
   reference it relies on, and stops if the layout changes under it.
2. **Saarthal:** corpse NPC_ copies (template flags fixed), still copies of the worn items (collision stripped),
   the real items in the corpses' inventories, the grave activators (`$DragonFont` names, blank verb), and the
   references in Saarthal02's temporary group.
3. **The College:** the mannequin (DoNothing package), the plinth activator ("Read Plaque"), the click-box
   activator, the display copies of the armour (non-playable, worth 0), the notes, and the quest's properties.
   Nothing in the College's cells.
4. **Form IDs:** new records are allocated after every existing one, so saves keep working across dev builds.
5. **Stage** into a Mod Organizer 2 mod and test on a new game.

## Verification
- **The oracle:** a custom Papyrus user log (`Debug.TraceUser`), switched on by a global. It says where each
  placed piece ended up and why it moved ("the player came into the hall, moved from 625, -2481, 0, settled at
  723, ...").
- **A dev-only test power** made each run short: buttons that start Under Saarthal, give the finds, hand them in
  from anywhere, and move the player into Saarthal or the hall.
- **The human tested every build in game** on a new game, and played the packaged release on an unmodded profile
  (the game plus SKSE, the Papyrus Extender and Address Library), which found gotcha 11.
- **The test matrix that matters for anything placed by script:** placed while the player is in the cell, placed
  while away and then walked into, left and re-entered, and a save loaded in the cell. Dev tests only did the
  first for about 20 builds.
- **Not verified:** the message box's exact limit; `SetScale` on collision; `SetPosition` on actors; whether the
  mannequin's `OnLoad` came at all on arrival; the tombstone-note crash's cause.

## Gotchas
1. **The corpses were called "Skeleton", and Respawn-off did nothing.** **Cause:** the template's Use Base Data,
   with the flags read at the wrong ACBS offset (22 instead of 18). **Fix:** clear `0x80`.
2. **A posed elf rolled out of his pose; his arrows hung in the air.** **Cause:** only the items had Don't Havok
   Settle. **Fix:** the corpses too. It didn't fix the overlap (gotchas 3-5).
3. **The sword and arrows lay on the floor instead of in the bodies.** **Cause:** a havok item inside a ragdoll's
   collision wakes and drops. Activator props showing the same models fell too (the record type doesn't decide
   physics; the model's rigid body does), and the arrow prop showed a quiver (`ArrowQuiver`).
4. **With the items held in place, the skeletons were out of pose on arrival.** **Cause:** keyframed items with
   collision push the ragdoll. (It looked like the CK saving unsettled poses; the human pointed out the items.)
5. **Freezing the bodies with `ForceRemoveRagdollFromWorld`:** upside down, through the floor, unsearchable.
   **Fix for 2-5:** collision-free still copies on the bodies, the real items inside them ("Things on and in posed
   corpses").
6. **The mannequin appeared in mid-air at the hall's centre.** **Cause:** it's placed from the Eye, which floats
   at the centre, and enabling it in the loaded hall fired `OnLoad` before the quest had given it its spot.
   **Fix:** give it its spot before enabling it, then settle it once its 3D is loaded.
7. **No "Read Plaque" prompt on the mannequin, through two builds of click boxes.** **Cause:** a mannequin shows
   no prompt, and the first box's mesh had no collision. The log showed every activation reaching the mannequin
   itself, never the box. **Fix:** four unscaled `WRSingleTrigger01` boxes.
8. **Notes placed by Tolfdir's bed worked once, then never.** **Cause:** the bed, a non-persistent reference, in a
   builder-filled property: None while his hall was unloaded. The first run only worked because the hall was still
   in memory.
9. **The notes landed in Arniel's room, then in the wrong building.** **Cause:** College mods move his bed and its
   owner. **Fix:** anchor on the Eye instead.
10. **The test menu crashed the game on opening.** **Cause:** its text grew past about 1050 characters. **Fix:**
    shorter text, and an assertion in the build.
11. **On the unmodded profile, the display stood in the middle of the hall, plinth and all.** It had been handed
    in from Saarthal; every dev test had handed it in inside the hall. **Cause:** nothing settled it when the player
    came in (gotcha 6's fix only ran in the loaded hall, and `OnLoad` didn't do it). A first fix blamed
    MannequinStay alone, which didn't explain the plinth: ask where every piece is before shipping a theory.
    **Fix:** settle on the player's `OnLocationChange` into the hall (and on a game loaded there), plus the
    DoNothing package.
12. **The plaque said "and boots".** **Cause:** the case-insensitive string table. **Fix:** whole strings from the
    build.
13. **Shipped script sources said "the user's call".** **Cause:** dev notes in comments, which ship (sources, and
    `{}` doc text inside the `.pex`). **Fix:** a scan of the release zip before upload, and neutral comments.

## Assets
None generated. Vanilla models are copied with their collision stripped at build time from your own game files.
Those still copies are edited Bethesda meshes: fine in your own build, but a published mod must not include them.
A public release builds them at install time, with the same NIF patcher run on the player's own game files,
instead of shipping them. All voice is Tolfdir's own recordings, and the copied Dragonborn line comes from the
player's install the same way (Route and why).

## Cost and time
66 dev builds in five days: 16 on the corpses (8 of them on gotchas 2-5), about 20 on the spell (its own note),
10 on the display, 7 on the notes and the test menu, 4 on the grave names, and the rest on text, voice and the
hand-in.

## Open questions
- **Why the placed actor's `OnLoad` didn't settle it on arrival:** never sent, or its handler stalled. The log now
  writes `OnLoad` on its own line.
- **`MoveTo(anchor, offsets)` into an unloaded cell:** does it ever stick? The plinth's didn't, and the read-back
  came right after the call.
- **`SetPosition` on an actor:** untested without MannequinStay in the way.
- **The message box's exact length limit,** and whether it counts characters or bytes.
