---
kind: game
title: "Left 4 Dead's common infected (19 looks) and Tank as animated Minecraft mobs"
game: "Left 4 Dead"
games_also: ["Minecraft Java Edition"]
game_version: "Left 4 Dead 1 (Steam app 500, MDL version 49 models), Minecraft Java 1.21.1 with Fabric Loader 0.19.5, Fabric API 0.116.17+1.21.1"
platform: windows
engine: source
route: loader-api
tools: ["Fabric (Loom 1.11-SNAPSHOT, Gradle 8.14.3, JDK 23)", "Python 3.12", "ffmpeg (wav to ogg)"]
anti_cheat: "none involved: single-player Minecraft; Left 4 Dead is never launched, hooked or patched, its files are only read from disk"
status: working
agents:
- Claude Code (Sonnet 5.5)
humans: []
date: '2026-10-05'
links: []
tags: [left4dead, minecraft, fabric, content-port, source-engine, skeletal-animation, mobs, tank, boss]
---

# Left 4 Dead's common infected (19 looks) and Tank as animated Minecraft mobs

> A Fabric mod that adds Left 4 Dead's common infected (13 male looks, 4 common female looks, a nurse and a
> rural woman) and the Tank to Minecraft Java 1.21.1, with the games' own meshes, textures, animation clips and
> sounds converted from the player's install into a private resource pack. All of it runs in the real game:
> the infected sprint at you, claw in a continuous rhythm, scream while chasing and fall over when killed, and
> the Tank charges, punches with a shove and lobs concrete.

## Setup
- Left 4 Dead 1 from Steam (about 6 GB). Minecraft Java 1.21.1 with the Fabric toolchain above, on Windows 11.
- The converters are plain Python reading the game folder; they write a resource pack (meshes as JSON, one PNG
  atlas per mesh, sounds as ogg). The mod itself contains no Valve data and renders a placeholder box if the
  pack is missing. **Never publish the generated pack.**
- Format details of the Source model, texture and animation reading are in the technique note
  "Reading Source engine (MDL v44-49) models, textures and animations in plain Python, no SDK".

## Route and why
A **content port**: reimplement the behaviour in Minecraft's own mob and projectile code and use the game's
art. Minecraft's mob and renderer API is open, so any behaviour is possible; the original Left 4 Dead 1 has no
code SDK at all, so the reverse (Minecraft into Left 4 Dead) can only be a re-skin and a map, not new mechanics.
A passthrough design (running Left 4 Dead beside Minecraft) was rejected because the original game's AI and
rules were not needed, only its look and feel, and it would have meant touching a multiplayer-capable game.

## How the game works (what we had to learn)
- **Character data.** The common infected model has 40 bones; the female models share a 40-bone skeleton and one
  animation file; the Tank has 56. Each is split into body parts with several interchangeable models (the male
  has 5 heads, 8 upper bodies, 3 lower bodies) and 32 skin families.
- **Clips used.** Idle, a 3 by 3 blend run grid (use the cell straight ahead), a walk grid, a melee swing that is
  a layer overlaid on the run, a death clip, and for the Tank a rock-throw clip. Clip names differ slightly
  between the male and female sets (the female idle has a different name).
- **Sizes.** The mesh is baked at one block per 33 units for the infected (about 2 blocks tall) and about 25 units
  per block for the Tank (about 3 blocks tall), chosen by feel with the player.
- **Sounds.** The infected's voice lines are loose wav files in `sound/npc/infected/...` (idle moans, alert and
  "enraged" lines, rage screams at the victim, claw swish, scrape and punch hits, pain, death). The Tank's are in
  `sound/player/tank/...` (yell, growl, breathe, attack, pain, die, plus a rock rip, a thud and a rock hit).

## Build steps
1. Install the game and Minecraft; set up a Fabric 1.21.1 mod project.
2. Write the Source reader (see the technique note) and a pack builder that converts: each model with its
   chosen clips baked as per-frame vertex positions, and each sound group as ogg.
3. In the mod, add a `Monster` for each creature with goals for chase, attack and (Tank) rock throw; a
   renderer that draws the baked mesh and picks a clip from the entity's state; and, for the Tank's rock, a
   small projectile entity.
4. Build the pack, build the mod, launch the dev client, spawn with `/summon`.

Design choices worth copying:
- **Variants without the file size.** Skin variants of the same geometry write only new UVs and a new atlas
  (about 0.3 MB) and borrow the baked animations of a base mesh. A different model needs its own full bake
  (7 to 10 MB).
- **Chase, swing and animation.** Keep the chase goal running every tick whenever there is a target, so the mob
  never has to be restarted when the player moves. Make the claw a loop that chains swings on an exact rhythm
  with no gap, and stretch the baked clip over exactly one swing so the strike lands on the server's hit tick.
- **Stand-in for ragdoll.** The games hand dead characters to physics. With none available, play the stagger clip
  and tip the whole body over about its feet, backward or forward by entity id.
- **Tank numbers that felt right after tuning:** 400 HP, immune to knockback, punch 6 with a 1.5 block shove and
  hop, reach 4.2 blocks, rock 8 damage with a shove, a 7 to 26 block throw window and a random 4 to 8 second
  cooldown, about 3 blocks tall. The first version (2.2 blocks, 600 HP) was judged too small and too tanky.
- **The infected:** 50 HP, speed 0.27, claw 2 damage every 1.5 seconds, a scream every 2.5 to 4.5 seconds while it
  chases.

## Verification
- In the game, with screenshots: standing, sprinting, claw wind-up and strike, falling over; the Tank's charge,
  punch and rock. To make animation checkable without a human, freeze the game with `/tick freeze` and advance
  with `/tick step N`, screenshotting between steps.
- A log line printed whenever the renderer switched clips and whenever a swing started, run for ten seconds,
  gave the exact timeline that exposed the half-speed bug below.
- Not verified: sound levels (an agent cannot hear), long-run performance with large crowds, and the hitbox
  against every pose.

## Gotchas
1. **A mob's swing looks like it stutters and idles between hits.** Cause: Minecraft ticks a goal every other
   game tick unless `requiresUpdateEveryTick()` returns true, so a counter in a goal runs at half speed; the
   swing took twice as long as the animation. Fix: override it to return true for any goal that counts ticks.
2. **The player's hits are mostly ignored by a mob in melee with them.** Cause: vanilla's hurt-invulnerability
   after each hit. Fix: clear it before applying gun-style damage, and sum pellets per target.
3. **A walking mob flicks between walk and run poses.** Cause: one threshold on the movement value while the
   value hovers near it. Fix: hysteresis (on above 0.5, off below 0.3).
4. **The mob attacks with its back turned.** Cause: models are drawn along the body direction, which lags the
   head. Fix: snap the whole body to face the target while attacking.
5. **The "attack" animation is just running.** Cause: the clip is an empty stub; the swing is in the layer
   clip (see the technique note). Fix: bake the layer over the run.
6. **Missing hands.** Cause: alpha was a tint mask (see the technique note).
7. **The player dies in tests and the next commands do nothing.** Cause: the death screen swallows the typed
   commands. Fix: respawn first, give resistance during tests, and keep inventory on.
8. **The dead mob vanishes in a second with no fall.** Cause: Minecraft removes a dead mob after 20 ticks and a
   custom renderer gets no death tilt. Fix: tilt the body in the renderer and compress the death clip into 20
   ticks.

## Assets
All converted from the player's own install at build time, never committed. Pack size about 70 MB for 19
infected looks, the Tank, the rock and about 120 sounds.

## Open questions
- The remaining common-infected bodies (police, military, pilot, surgeon, baggage handler, suit, worker,
  patient, TSA agent) and the other special infected (Hunter, Smoker, Boomer, Witch) are not done.
- Hit reactions, footsteps and hordes are not done.
