---
kind: technique
title: "Geometry transfer: the host draws the guest's meshes"
tags: [mashup, passthrough, geometry-transfer, mesh-export, texture-atlas, render-state, depth, lighting, digging, emulator]
date: 2026-10-07
agents: ["Claude Code (Opus 5.5)"]
humans: ["LeiiLo"]
links: ["https://github.com/chasmlol/SkyCraft", "https://github.com/mrborghini/libertycraft", "https://github.com/SawyerTheNerd/Minecraft-X-HalfLife", "https://github.com/M0uidev/GalaxyCraft"]
---

# Geometry transfer: the host draws the guest's meshes

> Both games run, but the guest sends meshes, texture atlases and collision, and the host renders them with
> its own renderer, so guest blocks get the host's lights, shadows and depth. In exchange the bridge works
> inside the host renderer's timing and state, and has to keep a stream of geometry fresh. This note covers
> three bridges ([SkyCraft](https://github.com/chasmlol/SkyCraft), [Minecraft × Half-Life](https://github.com/SawyerTheNerd/Minecraft-X-HalfLife) and [GalaxyCraft](https://github.com/M0uidev/GalaxyCraft)) plus
> LibertyCraft's port.

## When to use it
When the guest's world has to look native in the host (lit, shadowed, hidden behind host walls) and you can
draw through the host's renderer, by hooking or patching it. If only the picture matters, frame compositing
(`frame-compositing-depth-and-pose-sync.md`) is less work. Pick the route first with
`choosing-a-mashup-route.md`.

## How

### What the guest exports
- **Use the guest's own mesh builders.** SkyCraft's Fabric exporter runs Minecraft's block and fluid
  renderers and models to produce triangles and texture-atlas updates. It also sends held items, arrows,
  block outlines, lights, a bitset of solid cells and a bitset of dug cells.
- **Give the exporter a per-frame budget.** It sends at most 12 changed sections with a scheduling deadline
  of about 3 ms per frame, recent edits first, and retries a section when the ring buffer is full. That is a
  work budget per frame, so it says nothing about end-to-end latency.
- **Bound the stream.** SkyCraft's render stream is a fixed 64 MB channel next to a 32 MB collision stream.
  Decide what happens when either is full (see `bridge-contracts-ownership-units-and-lifecycle.md`).
- **Overlays can sit alongside.** SkyCraft's shared-memory header has room for up to three full-screen RGBA
  overlays for the hand, HUD and screens. An overlay channel doesn't make the world a flat picture, so read
  the renderer code before classifying a bridge.

### Where the host draws it
| Bridge | Host renderer | How guest geometry gets in |
|---|---|---|
| SkyCraft 0.1.2 | Skyrim, D3D11 | an SKSE plugin draws the exported meshes in Skyrim's own world pass with Skyrim's lights, replacing some of Minecraft's baked directional brightness |
| Minecraft × Half-Life | GoldSrc, OpenGL | modified client and server DLLs pass Minecraft geometry through Half-Life's own pipeline; only the HUD is a pasted image |
| GalaxyCraft | Super Mario Galaxy 2 in Dolphin | Minecraft data becomes GameCube display lists, textures and KCL collision, so the original renderer draws it; a native module inside the game handles rendering, gravity and collision |
| [LibertyCraft](https://github.com/mrborghini/libertycraft) | GTA IV, D3D9, under Wine | keeps SkyCraft's guest side and rewrites only the host renderer and collision sampling |

LibertyCraft shows which half carries over. The guest-side export stays the same, and each new host is its
own renderer and collision work.

### Restore the host's render state
Drawing inside another game's frame means sharing its GPU state. [HL2-RS](https://github.com/kvalls/hl2-rs) (a Rust recreation of
Half-Life 2, not a mashup) documents two leaks that apply here. A pipeline left bound by an earlier pass can
stop a depth clear from working, and depth test and depth write are separate switches (transparent surfaces
often need the test without the write). Set what your draw needs, then restore the host's state.

### Edits go both ways
When the player digs, SkyCraft's guest records the dug cells and supplies replacement interior walls, and
the host removes the matching render and collision surfaces. Collision representations, host terrain
cutting and refilled holes are in `collision-and-combat-bridging.md`.

## Gotchas
1. **"Mine anything" isn't literal.** SkyCraft's 0.1.1 code declines triangles marked non-diggable, such as
   protected buildings. **Fix:** write down which host geometry the guest may change.
2. **Destruction only near the host player.** SkyCraft destroys host terrain only where the host knows native
   geometry, so explosions far from the player leave Skyrim untouched. **Fix:** document limits like this
   next to the feature.
3. **Blast checks can take over the server thread.** SkyCraft 0.1.2 keeps nearby triangles and prunes
   distant ones when classifying blast material. The commit cites a profile in which the old probe took 86%
   of server-thread time (creator profile). **Fix:** limit material checks to the area the blast can reach.
4. **Interiors share coordinates.** In SkyCraft, blocks placed in one interior can show up in another.
   **Fix (not built there):** key guest data by host worldspace or cell as well as position.
5. **Multiplayer shares only the guest.** SkyCraft shares one Minecraft world between players while each
   runs their own Skyrim, so host quests, NPCs and saves aren't shared. A player count in a README isn't a
   stress test.
6. **The design doc isn't the shipped design.** An earlier SkyCraft draft proposed GPU colour/depth textures
   and separate interior slots; the shipped code exports meshes. Read the code for the version you use.

## Verification
Build and check in this order (the route note's first-slice table has the short form):
1. One guest cube, drawn by the host at a known position.
2. A host wall hides it and a host light lights it.
3. The host's render state is the same after your draw as before it.
4. A guest edit (dig a block) shows up in the host within a stated number of frames. Log that number.

Versions are in `skills/mashup-mods/references/mashup-cases.md`. The 86% profile is the creator's report.
