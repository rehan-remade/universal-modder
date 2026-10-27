---
kind: game
title: Adding a new element (radiation) to guns, grenades and shields in Borderlands 2
game: Borderlands 2
games_also: ["Borderlands 3"]
game_version: "Borderlands 2, Steam 49520 (exe v8639); Willow2 Mod Manager v3.8 (unrealsdk 3.2.0, pyunrealsdk 1.10.0, Python 3.14)"
platform: windows
engine: unreal
route: loader-api
tools: ["Willow2 Mod Manager v3.8 (pyunrealsdk)", "pure-Python LZO1X package reader and a small package writer (to carry particle systems)", "um scan", "PrintWindow screenshot bursts"]
anti_cheat: "none; single player only"
status: working
agents:
- Claude Code (Sonnet 5.5)
humans: ["@Pherdee-boi"]
date: '2026-10-19'
links: []
tags: [borderlands, gearbox, ue3, pyunrealsdk, elements, damage-types, status-effects, particles, explosions, effect-collections, shields, grenades, item-parts, saves, persistence, test-harness]
---
# Adding a new element (radiation) to guns, grenades and shields in Borderlands 2

> A Python SDK mod gives Borderlands 2 a fifth element, radiation (after Borderlands 3): guns drop with it, the
> Maliwan element switch can pick it, enemies burn for damage over time and hurt the ones around them, and
> grenade mods and shields can be radiation too. Everything is a runtime copy of BL2's corrosive objects plus a
> small carried particle package. It runs in the real game; the look was judged from screenshots of a scripted
> test instance, and the damage numbers by script on real enemies.

## Setup
Willow2 Mod Manager v3.8 (pyunrealsdk) with a Python mod; a second, own game instance for tests. It's the same setup
as [BL3 weapons and movement in Borderlands 2](bl3-weapons-and-movement-in-borderlands-2-willow2-sdk-mods.md), whose
Setup covers the install, `sdk_mods/`, `unrealsdk.log` and hooks. A tiny launcher/harness that drops a Python file into
a watched folder and reads the result from the log makes a 30-second edit-test loop. It runs whatever lands in that
folder, so it's a dev-only tool: keep it out of anything you release. Screenshots are taken from the background window
with `PrintWindow` in bursts (no focus change).

## Route and why
Pure SDK route: no game file is edited. Anything a script builds at run time is a clone (`construct_object` with a
template), so it vanishes when the game closes and every mod start rebuilds it. The only extra file is a small
`.upk` with copies of BL2's own particle systems, cut out of the game's package with a reader/writer (the format is in
[reading UE3 Gearbox games offline](../../techniques/reading-ue3-gearbox-games-offline.md)), because runtime-built
particle materials draw as solid blue squares and a carried package avoids that. That package is game content: build it
from the player's own install, as this mod does at start (see Assets), and never redistribute the `.upk` itself.

## How the game works (what we had to learn)
- **An element is several objects.** A damage type (with a damage-number colour and the "effective against" card
  line), a status effect with its own damage type, and per gun type an elemental part that points at the damage
  type. Cloning corrosive's objects and re-pointing the copies is enough for damage and cards. The damage type keeps
  a byte that says which built-in element it is: element attributes that compare names ignore it.
- **Guns pick effects from collections, not from the part.** The muzzle flash, the tracer, the rocket trail and the
  explosion of a gun come from `EffectCollection`/`ExplosionCollection` lists whose entries test attributes
  named `WeaponDamage_Is_<Element>` (compared by damage-type *name*). The shot lists and five explosion lists
  (default, Maliwan launcher, E-tech pistol/shotgun/SMG) hold only corrosive/incendiary/shock/slag: a new element
  matches nothing, so the gun gets the plain effect or, for explosions, the last entry (slag: a radiation rocket dealt
  "slag damage"). Fix: clone the Is_Corrosive attribute with your damage-type names and add an entry to each list.
- **An explosion's look lives in its size tiers.** An ExplosionDefinition has three tiers by radius, each with its
  own particle template and particle-scale range; the template at the top is unused. Clone the definition, set the damage
  type, and replace the template and cap the scale of every tier.
- **Projectile guns read a damage-type override from the elemental part's behaviours.** The part's behaviour
  provider adds an instance-data entry named DamageTypeOverride; a cloned part still points at the *same* provider,
  so a clone dealt corrosive damage until the provider and its one behaviour were cloned too.
- **Grenade mods and shields get their element from one part** (a grenade's "Accessory_<element>", a shield's
  Nova/Spike accessory). A grenade part's provider sets the damage type, explosion and in-flight effect as
  instance data; a shield part activates a skill whose behaviours explode, cause damage or spawn particle systems.
  Clone the part, a corrosive provider (edited) and, for shields, the skill.
- **Saves drop runtime parts.** A save keeps an item's parts as places in BL2's part lists; a part made at run time
  is silently left out and the item comes back with an empty slot (guns lose their element, grenades their accessory).
  So the mod flags items by their unique number, remembers the *original* part's path for gear, and converts again
  whenever an item is named, shown on a card or equipped.
- **Item text.** Names come from script functions that can be hooked (before-hook, call the original with hooks
  suppressed, return the edited text). The card's description lines are generated natively; rewrite them in the card
  GFx call that receives the finished text.
- **Colour tables** in particle modules are two header numbers followed by r,g,b triples. Reading from index 0 shifts every
  channel (yellow came out aqua, then magenta).
- **Carrying particle systems:** objects keep their original names inside the new package group (the path you ask for is
  only the group); anything the copies reference that is not carried must be listed as an import to a BL2 object, or it
  silently becomes None (flat dark squares, invisible beams).

## Build steps
1. Build the element objects from corrosive's (damage type, status, per-type parts, own behaviour providers).
2. Carry the particle systems you need into a package; dress them (colour tables, plain materials) at start.
3. Add your entry to each effect/explosion list at start and on every map arrival (lists reload with maps).
4. For gear: clone the element part, an edited corrosive provider and the skill; swap the part into the item's
   definition data; remember the original part by the item's unique number.
5. Hook names and card text for flagged items; convert equipped items from a once-a-second tick.

## Verification
Scripted instance: guns of every type (plain and E-tech) were converted and fired with screenshot bursts; the explosion
definition returned by the list was logged for a Maliwan launcher after element switches; gear was equipped, a
nova was triggered, the game was saved (by dying), restarted and the items checked again. Not verified: long real
fights, co-op, and a thrown grenade's explosion on real enemies (the in-flight trail and message were seen).

## Gotchas
1. **A cloned part deals the source's damage type.** Cause: it shares the source's behaviour provider and its
   DamageTypeOverride entry. Fix: clone the provider and the behaviour, edit the entry.
2. **Radiation gun, slag/incendiary explosion.** Cause: no list entry matches, the game uses the last or a stale one.
   Fix: add an entry per explosion list (and per shot list).
3. **The explosion still looks corrosive after setting the template.** Cause: the tiers hold the real templates. Fix:
   set every tier and cap the particle scale (a Maliwan nova goes to 10x).
4. **Flat dark squares instead of a muzzle flash.** Cause: references the package did not import became None. Fix: list
   them as kept imports and rebuild.
5. **Aqua/magenta instead of yellow.** Cause: tables start after two header numbers. Fix: rewrite triples from index 2;
   also swap corrosive's green materials for BL2's plain ones.
6. **Items come back without their element.** Cause: runtime parts are not saved. Fix: remember the original part per
   unique number and convert on sight; guard the equip swap when the backpack is full (the item would be dropped).
7. **A flag that outlived its reason.** A flag rolled for an item without an element part named it "radiation" for
   good; treat a flag as valid only while the item can be converted.
8. **A test instance writes the player's save.** It loads the last save and autosaves on load and every respawn; test loot
   and loadout swaps land in the real character. Copy a clean save out of any rotating backup before testing and
   restore it byte for byte afterwards.
9. **Equip tests:** setting the current weapon puts it in the hand but it will not fire; ready it into a quick slot
   through the inventory manager and equip the slot. Never pass an old definition-data struct to such calls
   after the item was swapped (access violation inside the SDK).
10. **Native functions can't be hooked** from script: pick the script-level caller (the card GFx call) instead.

## Assets
The gas, bubbles and smoke sprites were made by script (PIL) and the Geiger-counter blast sound is the player's own
file, loaded as a Wwise event by a small audio mod. No game assets ship with the mod: the particle package is cut
from the player's own install at start (see Route), so a release needs only the code that builds it.

## Cost and time
About three weeks of sessions; the last day was a long unattended test-and-fix run.

## Open questions
Hornet-style guns that name a default tracer in their firing mode keep a white tracer. Spike shield visuals were
only checked by conversion, not in a fight. The shield break burst and the death-cloud gas could be unified.
