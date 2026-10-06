---
kind: game
title: "Half-Life 1's weapons and monsters as a Minecraft Fabric mod, from a GoldSrc model converter"
game: "Half-Life"
games_also: ["Minecraft Java Edition"]
game_version: "Half-Life 1 (Steam, GoldSrc, Studio model version 10), Minecraft Java 1.21.1 with Fabric Loader 0.19.5, Fabric API 0.116.17+1.21.1"
platform: windows
engine: unknown
route: loader-api
tools: ["Fabric (Loom 1.11-SNAPSHOT, Gradle 8.14.3, JDK 23)", "Python 3.12", "ffmpeg (wav to ogg)"]
anti_cheat: "none involved: single-player Minecraft; Half-Life is never launched or modified, only its files are read"
status: working
agents:
- Claude Code (Sonnet 5.5)
humans: []
date: '2026-10-05'
links: []
tags: [half-life, goldsrc, minecraft, fabric, weapons, hitscan, projectiles, mobs, content-port]
---

# Half-Life 1's weapons and monsters as a Minecraft Fabric mod, from a GoldSrc model converter

> A Fabric mod that adds Half-Life 1's crowbar, 9mm pistol, MP5, shotgun, .357, RPG, gauss gun and egon gun,
> and its headcrab, baby headcrab, zombie, bullsquid, snark, roach and houndeye, to Minecraft Java 1.21.1.
> Models, animations, textures and sounds are converted from the player's own install into a private resource
> pack and the gameplay is reimplemented in Minecraft. Everything was tested in the running game.

## Setup
- Half-Life 1 from Steam. Minecraft 1.21.1, Fabric toolchain above, Windows 11, Python for the converters.
- The pack builder reads the game folder and writes meshes (JSON), textures (PNG atlases) and sounds (ogg).
  The mod ships no Valve data; with the pack missing it draws plain boxes. Never publish the pack.
- Numbers (damage, health) were read from the game's own `skill.cfg` and then scaled for a 20 HP player.

## Route and why
A content port in Minecraft's own entity and item code, not a passthrough: Minecraft stays the authority and the
original game is only a source of art and numbers. A passthrough version for a different Source game exists in
the knowledge base; this note is the cheaper route.

## How the game works (what we had to learn)
- **Studio MDL v10 (GoldSrc).** Fixed header with counts and offsets: bones (112 bytes each, with default
  position and rotation plus scales), sequences (176 bytes), textures (80 bytes, an 8-bit palette image), body
  parts, skins. Each body part has one or more sub-models; each mesh uses triangle strips and fans stored as
  commands; vertices carry a bone number. UVs are in pixels.
- **Rotations.** The three rotation values are in the order roll, pitch, yaw. Using the Quake order puts a
  character lying down.
- **Animations.** Each bone channel is run-length encoded 16-bit values scaled by the bone and added to its
  default. The field that says which file holds a sequence's data is at offset 156 of the sequence record:
  a value above 0 means an external file (`name01.mdl`, `name02.mdl`) listed in the sequence-group table.
- **Textures live elsewhere.** Many monster models keep their textures, and the skin table that maps a mesh to
  a texture, in a companion `<name>t.mdl`. Reading the main file's table gives all body parts texture 0 and a
  see-through look.
- **Viewmodels.** The first-person weapon models include the arms and loose props (spare ammo, a speedloader,
  a magazine lying out of the gun) in other body parts or textures; drop them by texture name or by body part.
- **Aim blends.** Weapon-holding monsters use sequences with two blends (aim up, aim down). Averaging the Euler
  angles directly produces a flying leg; blend the rotations as quaternions.

## Build steps
1. Write a converter that bakes the chosen sequences into per-frame vertex positions (in Minecraft axes, 40 units
   to a block) plus one atlas of all the textures, and a builder that also converts the sound groups to ogg.
2. Mobs: a `Monster` per creature, goals for chase and attack, a renderer that picks a baked clip by state.
3. Held weapons: item models whose parent is the built-in entity model, drawn by a renderer that plays the
   weapon's idle, fire and charge clips; per-item display transforms place it in the hand.
4. Server logic per weapon (below), client packets for held-button weapons, particles for effects.

Weapon design that worked:
- **Hitscan guns** (pistol, .357, MP5, shotgun): a ray per shot or pellet, stopped by the first block; sum a
  shotgun's pellet damage per target and clear the target's hurt-invulnerability, or vanilla ignores most hits.
- **Full auto:** vanilla repeats right-click only every 4 ticks. Have the client send a small packet every
  2 ticks while the button is held and rate-limit on the server.
- **Charged shot (gauss):** a tap fires at once; sneak plus hold charges (the model's spin-up clips play), and
  release sends the charge time. Beams pierce every entity along the ray; the charged shot shoves the shooter back.
- **Continuous beam (egon):** hold-phase packets every 2 ticks; each pulse hits the first target; the beam is a
  line of dust particles.
- **Rocket:** a projectile that accelerates, explodes on contact, damages in a radius with linear falloff and
  never breaks blocks; damage to players is scaled down.
- **Return "consume" from a gun's use handler**, never "success": success triggers the vanilla arm swing, which
  throws the held model around.

## Verification
- Every model was previewed with a three-view silhouette renderer before it went into the game; every weapon and
  mob was then used in the real game with screenshots, and animations were checked by freezing the game and
  stepping ticks.
- Damage and health values were checked against the numbers in the game's own skill file (for example the
  gauss quick shot against a 50 HP zombie takes three shots, as in the original).
- Not verified: sound levels, ammo and reload (not implemented), multiplayer.

## Gotchas
1. **A monster's body looks patchy or see-through.** Cause: the skin table was read from the main model, which
   has none. Fix: read it from the texture companion file.
2. **A weapon appears with gloves, arms or a floating magazine.** Cause: viewmodels bundle them. Fix: skip the
   glove and prop textures by name and the prop body parts by index.
3. **A character is lying on the ground.** Cause: rotation order. Fix: roll, pitch, yaw.
4. **A monster's firing pose is a mess of limbs.** Cause: its sequence is in an external file, so the data was
   read from the wrong file. Fix: use the sequence-group table (offset 156 in the sequence record).
5. **A held gun slides around when fired.** Cause: the vanilla swing animation. Fix: return "consume".
6. **A gun in hand floats off the screen.** Cause: viewmodels are authored around the eye, not the hand. Fix:
   centre the mesh on the item and tune translation and scale per item.
7. **A mob goal's windup lasts twice as long as written.** Cause: goals tick every other game tick unless they ask
   for every tick. Fix: override `requiresUpdateEveryTick()` to return true.
8. **A houndeye or similar monster runs away from the player.** Cause: Minecraft's "move towards target" goal
   picks a random point in a cone and is unreliable. Fix: path straight to the target and hold at a set distance.

## Assets
Converted at build time from the player's install; none committed.

## Open questions
- Reload, ammo, the grenade launcher, the crossbow, grenades, mines, satchel, snarks as a weapon and the hornet gun.
- The gauss gun's wall penetration and the egon's textured beam.
