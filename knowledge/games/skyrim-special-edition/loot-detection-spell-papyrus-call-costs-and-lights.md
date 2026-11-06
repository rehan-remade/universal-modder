---
kind: game
title: 'A fast loot-detection spell with SKSE and po3: Papyrus call costs, threads, and lights on items'
game: Skyrim Special Edition
games_also: []
game_version: 'Skyrim SE 1.7.104 (Steam 489830), SKSE64 2.3.1, powerofthree''s Papyrus Extender 6.5.2'
platform: windows
engine: creation
route: loader-api
tools:
- SKSE64 2.3.1
- powerofthree's Papyrus Extender 6.5.2
- Papyrus Compiler (Creation Kit)
- Mod Organizer 2
- own Python plugin and NIF writers
anti_cheat: none found by um scan
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-26'
links:
- https://github.com/ianpatt/skse64
- https://github.com/powerof3/PapyrusExtenderSSE
- https://en.uesp.net/wiki/Skyrim:Detect_Life
- https://ck.uesp.net/wiki/Category:Non-delayed_Native_Function
- https://ck.uesp.net/wiki/Papyrus_Compiler_Reference
tags:
- papyrus
- skse
- po3
- performance
- threading
- art-object
- visual-effect
- effect-shader
- nif
- spell
---
# A fast loot-detection spell with SKSE and po3: Papyrus call costs, threads, and lights on items

> **Tolfdir's Appraisal** is an Apprentice Alteration spell for a College of Winterhold questline overhaul. Cast it
> once, and every valuable within Detect Life's range, in sight, lights up for 20 seconds:
> - **things lying about** glow at their middle;
> - **containers** get a blue orb circling them;
> - **people and bodies** get a Candlelight-style orb that follows them.
>
> "Valuable" means enchanted, a scroll, or worth 100 gold or more. Taking the valuables out of a container, body or
> person puts its light out. The spell runs on SKSE64 and po3's Papyrus Extender, called from Papyrus.
>
> The human played it through Saarthal on dev build 0.1.108 and called it "genuinely quite useful", especially
> for small things on the floor. Getting there took about twenty dev builds in one day. Most of what's below is
> what those builds taught about how slow Papyrus calls are, and how art objects behave on items.

## Setup
- **Game:** Skyrim SE 1.7.104 (Steam, Windows 11), run through Mod Organizer 2.
- **Script Extender:** SKSE64 2.3.1 (`skse64_1_7_104.dll`), with Address Library 13 (po3 needs it).
- **powerofthree's Papyrus Extender** 6.5.2. Its `.psc` sources sit in the mod's `Source/scripts`, and the
  compiler needs them as an import folder.
- **Papyrus Compiler** (Creation Kit), with imports in this order: your own, then po3's, then SKSE's, then the
  vanilla sources. The compiler uses the first copy of a script it finds and ignores the rest (CK wiki, Papyrus
  Compiler Reference), and SKSE replaces vanilla scripts such as `Form.psc` and `ActiveMagicEffect.psc`, so its
  folder has to come before vanilla's, unless SKSE's sources are installed over vanilla's in the same folder.
- **The plugin and meshes are written by the mod's own Python build script**, not the Creation Kit: records are
  copied from Skyrim.esm and edited, and meshes are patched with a small NIF writer. That's why everything below
  names record fields and byte offsets rather than CK tabs.

## Route and why
**SKSE plus po3's Papyrus Extender**, called from Papyrus, with no DLL of our own. Without them the job can't be
done well:
- **Vanilla Papyrus can't find references by type** around the player.
- **It can't read an item's enchantment.** `Form.GetGoldValue()` is vanilla; `GetEnchantment` comes with SKSE.
- **It can't list a container's contents.**

**The earlier SKSE-free version** (a Detect Life-style concentration spell) had to do without all of that:
- a pre-built FormList of the game's ~5,800 enchanted items;
- a finder quest capped at 32 of each kind.

It missed every mod's items and showed nothing on objects.

**Considered and dropped:**
- **Invisible stand-in actors carrying Detect Life's glow,** so finds would show through walls. This works (see
  How the game works), but the design wanted the spell to work in sight only, to stand apart from the other
  detect spells.
- **Invisible anchors** carrying each thing's orb. See gotcha 6.

## How the game works (what we had to learn)

### Almost every Papyrus native call waits for the next frame
**The rule:** a native function call made from Papyrus usually doesn't run at once. It's queued for the game's
main thread and comes back on a later frame, so one script thread manages roughly one native call per frame (about
60 a second).
- **SKSE64** marks some of its functions no-wait (`kFunctionFlag_NoWait` in its sources; 373 in 2.3.1):
  - the Register.../Unregister... functions and `SendModEvent` on Form, Alias and ActiveMagicEffect;
  - Utility's `Create...Array`, `Resize...Array` and `GetINI...`;
  - ModEvent, StringUtil, SKSE's Math additions, UI and Input;
  - getters and setters on records (MagicEffect, Spell, Potion, ActorBase...).

  `Form.GetType`, `IsPlayable`, `Armor.GetEnchantment` and `ObjectReference.GetEnchantment` all wait, as does
  everything SKSE adds to ObjectReference, Armor and Weapon.
- **po3's Papyrus Extender** registers functions with a `BIND` macro, and only `BIND(fn, true)` is no-wait (the
  `true` is CommonLibSSE's callable-from-tasklets flag, SKSE's no-wait). In 6.5.2, 46 of its 376 `BIND`s have it,
  all small getters; in `Functions/ObjectReference.cpp` and `Functions/Game.cpp` just three do
  (`GetPapyrusExtenderVersion`, `IsSurvivalModeActive`, `IsPluginFound`). `FindAllReferencesOfFormType`,
  `AddAllItemsToArray`, `HasArtObject` and `UpdateHitEffectArtNode` all wait a frame.
- **Vanilla natives wait too:** `GetBaseObject`, `IsDisabled`, `GetGoldValue`, `GetWidth`, `PlaceAtMe`,
  `VisualEffect.Play`, `EffectShader.Play` and so on. The CK wiki's "Non-delayed Native Function" category lists
  the 57 vanilla ones that don't (Math, `Debug.Trace`/`TraceUser`, `GlobalVariable.GetValue`/`SetValue`, alias
  `GetReference`/`ForceRefTo`, the update and LOS registrations, `EnableNoWait`/`DisableNoWait`...).
- **What it cost:** the first version made two or three such calls for every reference of nine item types in
  range, plus a few for each new kind of item. In a College hall that came to about 6 s from cast to the first
  light (measured with timestamps in a custom log).
- **Arrays:** array `Find` and Papyrus arithmetic don't wait. SKSE's `Utility.CreateFormArray(n)` can make arrays
  longer than 128 (the limit only applies to `new`).

### Threads from mod events
**The pattern:** an `ActiveMagicEffect` can send itself mod events, and each delivered event runs on its own
Papyrus stack:
- `RegisterForModEvent(name, "OnWork")` in `OnEffectStart`;
- then `SendModEvent(name, tag, i)` fifteen times.

**Why it speeds things up:** a script object runs one thread at a time. But a thread waiting on a native call
lets the others in. With 16 stacks, about 16 calls finish per frame instead of one.

**Taking jobs safely:** take the next job by reading and incrementing a shared index, with no native call between
the two. A thread can't be interrupted there, so no two take the same job.

```papyrus
Function Work()
	busy += 1
	while phase == 1 && nextFind < KINDS && !finished      ; the eleven searches, one call each
		int k = nextFind
		nextFind += 1
		Keep(k, PO3_SKSEFunctions.FindAllReferencesOfFormType(me, TypeOf(k), searchRadius))
	endwhile
	while phase == 2 && nextJob < nJobs && !finished       ; judging, lighting finds as they're judged
		int j = nextJob
		nextJob += 1
		Process(jobs[j] as ObjectReference, jobKind[j])
	endwhile
	busy -= 1
EndFunction
```

- **The dispatcher** does `Work()` itself, then waits with `Utility.Wait(0.05)` while `busy > 0`, with a timeout.
  Late-arriving threads find no work and leave.
- **Tag each cast's events** with a string unique to the cast, and check `finished`. Once the effect is gone,
  `SendModEvent` on it fails ("no native object bound").
- **Result:** the first light comes 0.16-0.5 s after the cast, and a whole search takes about 1-3 s. Lights go
  up one by one as finds are judged, rather than all at the end.

### The searches and the judging
- **`PO3_SKSEFunctions.FindAllReferencesOfFormType(origin, formType, radius)`:**
  - matches the reference's own type or its base object's;
  - only returns references whose 3D is loaded, so disabled ones are already left out and `IsDisabled` is
    redundant;
  - takes one call per type. Run them in the threads too.
- **Types used** (SKSE form type numbers): Armor 26, Weapon 41, Scroll 23, SoulGem 52, Potion 46, Book 27, Misc
  32, Ingredient 30, Ammo 42, Container 28, NPC 43. NPC matches both the living and the dead.
- **`PO3_SKSEFunctions.AddAllItemsToArray(ref, false, false, false)`** lists a container's or actor's items, worn
  ones included.
- **Value:** `Form.GetGoldValue()` is the stored value. An enchanted item's stored value leaves the enchantment
  out (a Staff of Fireballs stores 5 while the game shows 1,309), so "enchanted" is tested separately:
  - with `GetEnchantment()` on the base `Armor`/`Weapon`;
  - with `IsPlayable()`, to skip creature hides.

  A loose item the player enchanted is caught by `ObjectReference.GetEnchantment()`. Inside a container only the
  base item is seen.
- **Cache verdicts by base form.** Most of a room is the same clutter.

### Lights on things: art objects, effect shaders, and sleeping items
- **Art objects:** a `VisualEffect` (RFCT) wraps an `Art` (ARTO).
  - **Where it attaches:** to the target's 3D, at the root, or at a named node given by the nif's `AttachT`
    extra data. Candlelight's `LightSpellActorFX` uses `NamedNode&MagicEffectsNode`, which is an actor's chest;
    on items it falls back to the root.
  - **It moves with its target.**
- **Membrane shaders (EFSH):** for a glow on an object, use one made for items, such as the weapon-enchantment
  glows (`EnchBlueFXShader`). They draw on the item's own surface. Detect Life's `LifeDetected` glow is particles
  only (EFSH flags `0x10001`: No Membrane Shader, Particle Grayscale Color) and shows nothing on objects.
- **Through walls:** setting a membrane's Z test (offset 12 of the DATA) to Always Show (8), the value Detect
  Life's particle Z test has at offset 104, makes it draw over everything. Detect Life's particle EFSH played by
  script on an actor shows through walls even with the actor at `SetAlpha(0)`, so an invisible stand-in actor can
  carry it. Mysticism - The Lost Art does the same with a rabbit scaled to 0.001.
- **Sleeping items:** a havok item that has come to rest isn't updated. Art put on it doesn't show until it's
  bumped, and an animated art on it freezes once it settles again. Containers and actors don't have the
  problem.
  - **Fix for showing:** a tiny upward impulse as it's lit, `ApplyHavokImpulse(0, 0, 1, 0.05)`. Never on posed
    corpses.
  - **Fix for the freeze:** don't animate the art on items. See gotcha 6 for why.
- **Timed lights:** `VisualEffect.Play(ref, seconds)` and `EffectShader.Play(ref, seconds)` take a duration, and
  the game removes them by itself. A one-shot spell needs no cleanup script and leaves nothing behind across
  saves.
  - **Stop before replaying** (`Stop` then `Play`), or a recast stacks a second copy.

### po3's `UpdateHitEffectArtNode`: fitting an art to each find
`PO3_SKSEFunctions.UpdateHitEffectArtNode(ref, art, nodeName, float[3] translate, float[3] rotateDegrees, scale)`
does the following, from its source (`src/Papyrus/Functions/Graphics.cpp`):
- **It finds the model effect** on `ref` playing `art`.
- **With an empty `nodeName`** it keeps the attach point. It then sets the local transform of **every direct child
  of the art's root**, as a main-thread task.
- **With a node name** it re-parents the art to that node.

**What follows from that:**
- **Give the nif a single child under its root** (Candlelight's has one, `Mover`), and you can place and scale it
  per find.
- **The translation is in the target's own frame,** so it tilts with an item lying on its side.
- **A playing animation overrides the rotation;** translation and scale stay if the sequences have no
  translation or scale keys for that node.
- **It does nothing until the art is attached,** so call it after about 0.2 s and once more a little later.
- **We used it for:** a container's orbit at half its height with a radius just clear of its sides (`GetWidth`,
  `GetLength`, `GetHeight`), and a thing's glow lifted half its height. Most meshes stand on their origin, and a
  sword's runs along its blade, so half the height lands mid-object. Papyrus has no bounds-centre function.

### Editing Candlelight's orb (`LightSpellActorFX.nif`)
- **Its structure:** `Mover` → `LagBone` (with a `BSLagBoneController`) → the glows. It has sequences `mBegin`
  (clamp, 1.3 s), `mLoop` (loop, 7.33 s) and `mEnd`. Its sprites start at alpha 0, and controllers fade them in.
- **To make it circle:** give `Mover`'s rotation linear quaternion keys spinning about Z in the loop sequence, put
  `LagBone` out at the radius, and unhook the lag controller (set its controller link to -1). Otherwise it drags
  the orb out of the circle.
- **To make it sit still at its target:** the same, with zero turns and `LagBone` at the origin.
- **To keep Candlelight's follow-the-actor behaviour:** leave the animation alone and only recolour.
- **Never null a sequence's interpolator** to stop a node moving. The sequence becomes unplayable and the orb
  never shows. Rewrite its keys instead.
- **The sprites are soft particles** (a soft-falloff depth after the base colour). They fade wherever scene
  geometry is in front, so clearing the shader's Z-test flag can't make them show through walls. Setting that
  depth to 0 makes them invisible everywhere.
- **Speeding up the fade-in:** multiplying `mBegin`'s `NiControllerSequence` frequency by 4 was meant to make the
  orb appear four times faster. Not checked in game (see Open questions).

### The spell's records
- **Fire and forget on self.** Two effects:
  - **A visible, instant effect** (MGEF flag No Duration `0x200`). It carries the description, the cast art and
    sounds (copied from Candlelight's `LightFFSelf`), and the cost. With no duration, the cost is just its base
    cost: 120 here, more than Magelight's 84.
  - **A hidden script effect** (flag `0x8000`) lasting as long as the lights (20 s). The player sees no effect.
- **The cost formula:** for an effect with a duration, the game's cost is base x (duration / 10)^1.1.
- **MGEF DATA offsets used** (SSE):
  - flags `0x00`, base cost `0x04`, minimum skill `0x28`;
  - archetype `0x40` (1 = Script), actor value `0x44`;
  - casting type `0x50`, delivery `0x54`;
  - casting art `0x5C`.
- **SPIT** (spell data): cost `0`, flags `4`, charge time `12`, cast type `16`, delivery `20`, half-cost perk `32`.
- **Spotting an emptied container:** register for `"ContainerMenu"` (SKSE's `RegisterForMenu` works on an
  `ActiveMagicEffect`). Containers, looting bodies and pickpocketing all use that menu. In `OnMenuOpen`, take
  `PO3_SKSEFunctions.GetMenuContainer()`, falling back to `Game.GetCurrentCrosshairRef()`. In `OnMenuClose`,
  recheck it and stop its lights if nothing valuable is left.

## Build steps
1. **Records:** the spell, its two effects, its tome, the item membrane shader, and three ARTO+RFCT pairs (circling
   orb, still glow, following orb). They're copied from Skyrim.esm (Detect Life, Candlelight, `EnchBlueFXShader`,
   `LightSpellActorFX`, `FXWitchlightMeshEffect`) and edited as above.
2. **Meshes:** three patched copies of `LightSpellActorFX.nif`, recoloured blue with the `GradBlueLightEnch.dds`
   palette on its greyscale swirl. They're written into the mod's own `Meshes/` and built at build time from your
   own game files. They're edited copies of Bethesda's meshes: fine in your own build, but a published mod must not
   include them. Give a release an install step that runs the same patcher on the player's own game files, as the
   cut-gatekeeper note's build step 4 does for its voice files. No game files are kept in any repository.
3. **The script:** one `ActiveMagicEffect` script, compiled with the SKSE and po3 sources as imports. It searches
   with the threads, judges, and lights each find with a timed `Play`, then fits it.
4. **Staging:** into a Mod Organizer 2 mod folder, then tested on a new game.

## Verification
- **The oracle:** a custom Papyrus user log (`Debug.TraceUser`), switched on by a global. It logs each search:
  references in range, finds lit, when the first light came and how long it all took.
- **Papyrus.0.log** was used for engine errors. It's how gotchas 5 and 6 were found.
- **The human tested every dev build in game** on a new game, and played the final one (0.1.108) through Saarthal.
- **Not verified:**
  - the `mBegin` frequency speed-up;
  - performance in the busiest exteriors (Solitude);
  - how the circle and glow sit on unusual meshes;
  - in 0.1.108 specifically, putting a light out by emptying its container. The human's Saarthal run didn't
    single it out.

## Gotchas
1. **The spell took about 6 s to light anything.** **Cause:** every native call waits a frame, and the search made
   several per reference. **Fix:** cache verdicts by base form, drop redundant calls (`IsDisabled`; see "The
   searches and the judging"), share the work across 16 mod-event threads, and light each find as soon as it's
   judged. The first light now comes after 0.16-0.5 s.
2. **A log line cost a frame even with logging off.** **Cause:** the message string, with `GetBaseObject()` in it,
   was built before the logging check. **Fix:** no calls inside log arguments.
3. **Detect Life's glow showed on people but not on a robe on the floor, a chest or a corpse.** **Cause:** it's a
   particle shader given off by an actor's body. **Fix:** a membrane shader made for items (`EnchBlueFXShader`).
4. **An orb on an item sometimes needed a bump to appear, and later stopped moving once the item settled.**
   **Cause:** a resting havok item isn't updated, so its attached art isn't either. **Fix:** a 0.05 impulse to wake
   it as it's lit, and no animation on item lights.
5. **Orbs on freshly placed anchors never showed:** "has no 3d and so cannot have a visual effect applied to it".
   **Cause:** a `PlaceAtMe` reference gets its 3D a moment later, and `VisualEffect.Play` refuses it instead of
   queueing. **Fix:** wait for `Is3DLoaded()`. In the end, the anchors went entirely.
6. **An anchor's orb vanished when its item was moved.** **Cause:** `MoveTo` reloads the reference's 3D and wipes
   the attached art. `TranslateTo` keeps it. **Fix:** we used `TranslateTo`, then dropped anchors for a still glow
   on the item itself.
7. **"Unable to call RegisterForSingleUpdate / SendModEvent - no native object bound".** **Cause:** calling self
   functions after the effect had ended (a cast released mid-search). **Fix:** check a `finished` flag set in
   `OnEffectFinish` before any self call, and let the search thread clean up.
8. **The orb disappeared entirely after "pinning" its animation.** **Cause:** the controlled block's interpolator
   had been set to -1, which leaves the sequence unplayable. **Fix:** rewrite the keys, never null the link.
9. **Clearing the depth test didn't make the orb show through walls; zeroing soft depth made it vanish.**
   **Cause:** soft particles fade wherever geometry is in front, and a depth of 0 is invisible. **Fix:** accept
   in-sight only, or use an invisible stand-in actor with an EFSH.
10. **A recast doubled every light.** **Cause:** `Play` adds another copy. **Fix:** `Stop` then `Play`.
11. **Papyrus is case-insensitive about every name.** A variable `ammo` clashes with the `Ammo` script, `holders`
    with a function `Holders`, and `WORTH` with `worth`. **Fix:** rename, and read the compiler's "cannot name a
    variable ... the same as a known type" error literally. (The cut-gatekeeper note's gotcha 21 hit the same with
    `action` and `shout`.)
12. **For weeks, the magic menu showed Detect Life's description and turning art,** though the visible effect had
    its own description. **Cause:** the spell is a copy of Detect Life's SPEL, and two of its fields came along.
    - **SPEL `DESC`** is the spell's own description, and the menu shows it in place of the effects' `DNAM` texts.
      Detect Life has one; Candlelight's is empty.
    - **`MDOB`** (menu display object) is the art turning in the menu, on the SPEL and on each MGEF: Detect Life's
      is `MAGInvDetectLife` (00104F70).

    **Fix:** set `DESC` to the spell's text, and every `MDOB` to Candlelight's `MAGINVLightSpellArt` (000A0E7F).
    When copying any vanilla record, decide every subrecord the copy keeps, not just the ones you set.

## Assets
None generated. Vanilla Candlelight orb, weapon-enchantment shader and gradient, copied and recoloured at build
time from your own game files. The patched meshes are game files, so a public release builds them from the
player's own install at install time instead of shipping them (build step 2).

## Cost and time
One long day: about twenty dev builds, from a held Detect Life-style spell to the final one-shot spell.

## Open questions
- **The fade-in:** does the game honour an `NiControllerSequence` frequency change on a hit-effect art's `mBegin`?
  If not, shorten the sequence's keys instead.
- **Item centres:** a reliable bounds centre for any item, rather than "half its height in its own frame".
- **Real light:** a real light (not just a glowing sprite) on people, as Candlelight gives its caster, without too
  many lights in a crowd.
- **Value mods:** how it behaves with mods that rebalance item values. Verdicts are read at run time, so it should
  follow them.
