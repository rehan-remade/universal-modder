---
name: mashup-mods
description: Build cross-game mashups and total conversions, the "Minecraft inside Elden Ring" or "skateboarding in MW2" kind. Covers passthrough mods (two games running at once and exchanging state, rendering and collision), porting one game's content or mechanics into another, embedding a decompiled game as a library, and clean reimplementations that read the user's own game files. Use when the user wants to combine two games, bring an enemy, mechanic or world from one game into another, or rebuild a game's runtime, or reimplement the guest's rules headless inside a real host.
---

# Mashups: putting one game inside another

In September 2026 a wave of AI-built mashups went viral: skateboarding in MW2, Minecraft inside Skyrim,
Elden Ring and Mario 64, Black Ops 2 inside Minecraft. They use four patterns. Pick the lightest one that
delivers the idea, and plan the oracles before writing code: these projects fail by drifting, not by lacking
code.

## Pattern 1: port the content (lightest)
Bring an enemy, weapon or block type into the host as **new host content** that imitates the guest.
Examples: "Claude added creepers to Dark Souls", Minecraft blocks as Elden Ring items.
- Read the guest's behaviour from its source of truth: decompile or read the wiki's exact numbers (speeds,
  timers, damage). Reimplement it in the host's mod API (host AI state machine, host projectile).
- **Assets:** never copy the guest's files into your mod. Convert them from the user's install at runtime or
  install time (a converter script), or recreate lookalikes with fal.
- It's cheap and robust, with no IPC. It works with any host that has a loader.
- Worked converter: Bloons TD 6 assets (Unity 6) to a private Minecraft resource pack, see
  `knowledge/games/minecraft/bloons-td-6-in-minecraft.md` and asset-pipeline section 6.

## Pattern 2: passthrough (two games at once)
chasm's description of Minecraft-in-Skyrim: *"minecraft and skyrim run at the same time and you make a mod
for both that lets them communicate. Then you passthrough the things you want into the renderer in the
right place and feed stuff like collision data back to minecraft."* No code was published. The design below
is the standard way to build it.
1. **Guest process** (e.g. Minecraft with a Fabric mod, or a headless reimplementation): runs the simulation
   and publishes state every tick. That's entities/blocks near the player, or a rendered layer.
2. **Transport**, all on `127.0.0.1`:
   - state: a shared-memory ring buffer (`CreateFileMapping`) or UDP/named pipes;
   - control: JSON lines or HTTP;
   - GPU frames: DXGI shared handles (`CreateSharedHandle` / `OpenSharedResource1` + keyed mutex), Vulkan
     external memory, or Spout2.
3. **Host injection:** a host-side plugin (SKSE/xNVSE/UE4SS/REFramework/ReShade addon) draws the guest's
   geometry **inside the host's pass**. It uses the host's view-projection matrices (find them with
   RenderDoc) and depth buffer, or spawns host-native objects so host lighting and shadows apply. The
   Skyrim clip gave Steve Skyrim's lighting, which points to scene integration, not a flat overlay.
4. **Back-channel:** the host's collision near the player (raycasts, or exported nearby mesh) goes to the
   guest as solid blocks or colliders. Input routes to one process at a time.
5. **Sync:** timestamps on every message, tolerance for the two frame rates, and a watchdog when one side
   dies.
6. **Start small:** a cube from process A drawn in B at the right spot. Then positions every frame, then
   collision, and only then real content.

Bridge-plugin template in public: chasm-bridge-fnv (thin xNVSE plugin, file-drop/HTTP transport,
data-driven actions). The Terraria agent bridge in `examples/terraria-tmodloader/reference/` is the same
idea.

### Worked example: real Minecraft inside GTA V
Code: `examples/minecraft-gta5-passthrough`. Every lesson: `knowledge/games/gta-v/minecraft-passthrough.md`.
- **Minecraft (Fabric mod):** it takes camera, ground and input from the host over a WebSocket on
  `127.0.0.1`. Each frame it writes world colour + depth and a separate hand/HUD overlay into named shared
  memory.
- **GTA (ScriptHookV ASI + ReShade add-on):**
  - it sends GTA's camera and the ground under the player (as barrier blocks);
  - it composites Minecraft's colour against GTA's reversed-Z depth in a shader;
  - it turns Minecraft explosions, arrows and firework hits into GTA explosions and bullets.
- **Mapping:** 1 metre = 1 block. GTA (x, y, z) → MC (x, z + offset, −y); yaw = 180 − heading;
  pitch = −pitch.
- **Latency:** Minecraft's frame is re-projected onto GTA's camera, rotation then full 6-DoF with depth.
  Measure the pose lag with a scene where one side draws something the other doesn't (a gold wall vs the
  skyline).
- **Built without the game:** most of it was built before the host game was even installed, against a
  fake host (known geometry) and a fake D3D11 "GTA" that runs the real compositor.
- **What didn't work:** putting host-game guns in Steve's hands (the aim cam and animations don't fit).
  Guest weapons with host effects did.

## Pattern 3: embed a decomp as a library
libsm64 turns the Super Mario 64 decomp into a library: feed it collision and input, and it returns Mario's
state and mesh. G64 embeds it in Garry's Mod; the host feeds its collision into the guest sim. Any
decomp/recomp (see `skills/mod-any-game/references/engines/retro-decomp.md`) can be wrapped this way. The
user supplies their own ROM for assets.

## Pattern 4: reimplement, then fuse (heaviest, most control)
- **IW4L:** an LLM-written Rust MW2 runtime (Bevy + wgpu). It reads MW2's FastFiles from the user's install
  and translates the D3D9 shaders to WGSL.
- **The Skate 3 Rust engine:** built against a static recomp and an IDA database as oracles.
- **The mashup:** fuses both, plus a Minecraft Rust reimplementation, in one process. The skate sim is a
  worker that takes over the MW2 soldier. MW2 map collision feeds the skate world. Grind rails come from
  walkable collision edges. Skate bones are retargeted onto the MW2 skeleton.
- **What made it work:**
  - A **scriptable runtime as the oracle:** `spawn; wait 2s; screenshot; dump`, with blocking verbs and
    evidence files per run.
  - An **evidence journal** (`context/artifacts/<date>/<step>-FINAL|PART`). "Knowledge that is not in an
    artifact does not exist."
  - Owner-approved end-to-end tests only.
  - A **publish check** that greps for retail offsets and decompiler names before any push
    (`um publish check` does a version of this).
  - Converters that run on the user's files; game assets never committed.

## Pattern 5: reimplement the guest's rules headless, keep the host as the view
The host stays the real game (its weapons, mods and multiplayer); only the guest's *rules* are rewritten,
as a pure simulation that imports nothing from the host. Best for guests whose gameplay is numbers
(tower defense, card, puzzle, top-down 2D, turn-based) and for online-capable guests you must never
inject into. Example: Bloons TD 6 inside Minecraft
(`knowledge/games/minecraft/bloons-td-6-in-minecraft.md`).
- **The sim is the source of truth.** Run it at the guest's own step rate and units (BTD6: 60 steps/s,
  BTD6 units). Game speed changes the number of steps per host tick, never dt.
- **One frame-mapping function** between guest units and host coordinates (origin, scale, axis flips),
  shared by server and client.
- **Mirror entities for what the player must touch.** Host entities whose position is copied from the
  sim each tick and whose hurt/interact handler forwards into the sim. Strip everything the host would
  otherwise do to them: AI, gravity, knockback, potions, fire, pushing.
- **No host entity for high-volume things** (projectiles, particles). Send batched spawn records once per
  tick and run *the same motion code* on the client. Batch effects and sounds the same way, with caps.
- **Every UI button is a command.** Screens display a server snapshot and send commands back, so each
  action is testable without the screen.
- **Host features feed the sim, never bypass it.** Host weapons, blocks or potions become sim statuses
  and damage events; with none of them, the game must play out identically (check with a headless run).
- **Guest assets** come from a converter run on the user's own install into a local, private resource
  pack; the mod must stay playable with placeholders when the pack is missing.
- **Oracles:** the headless engine bench first (seconds, no host), then host-side benches (see
  `knowledge/techniques/oracles-how-agents-know-a-mod-works.md`).

## Guardrails
- Offline, single-player or servers the user runs. Never network into the real games' official online
  services.
- Everything guest-side comes from the user's own install or dump. Publish code and converters, not assets
  (`um publish check --game`).
- An online-capable guest (accounts, co-op, leaderboards) is read from its files offline only: never
  launched, patched or hooked by the mod or its tools.
- Be honest about what's AI-built. Creators who weren't got called out publicly.
