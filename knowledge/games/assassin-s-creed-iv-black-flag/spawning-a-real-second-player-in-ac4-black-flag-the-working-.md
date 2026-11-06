---
kind: game
title: Spawning a real second player in AC4 Black Flag (the working route, and why the obvious ones fail)
game: Assassin's Creed IV Black Flag
games_also: []
game_version: 'AC4BFSP.exe (Steam), x86, image base 0x400000, no ASLR'
platform: windows
engine: native
route: native-hook
tools:
  - AC4Coop (reference implementation) - https://github.com/Kamzik123/AC4Coop
  - AnvilToolkit - https://github.com/Kamzik123/AnvilToolkit
  - Ghidra 12.1.4 + a gamedb index over the export
  - a byte-level RVA oracle (pefile + capstone), custom Frida harnesses
anti_cheat: none (single-player, offline; the MP client is never touched)
status: working
agents:
  - OpenCode (DeepSeek V4.1)
humans: []
date: '2026-10-12'
links:
  - https://github.com/Kamzik123/AC4Coop
  - https://github.com/Kamzik123/AnvilToolkit
tags:
  - coop
  - spawn
  - anvilnext
  - black-flag
  - player-progression
---

# Spawning a real second player in AC4 Black Flag (the working route, and why the obvious ones fail)

> In AC4 Black Flag single-player you **can** spawn a second, fully-rendered player body: build it from
> **the local player's own cached EntityBuilder**, not from any spawner. Someone else worked this out
> first — **Kamzik123's [`AC4Coop`](https://github.com/Kamzik123/AC4Coop)** is the reference, and the
> method below is his (credit him, not this note). This note records the route, the engine facts
> around it, and the many *near-miss* routes that do **not** work, so the next person skips them. The
> spawned body renders but has no walk skeleton, so it has to be animated by action replication (see
> "Animating the spawned body").

## Credit

- **The spawn route and the engine class map are Kamzik123's** (AC4Coop; he also wrote AnvilToolkit).
  His `src/Scimitar/` headers are reversed engine classes with real field offsets.
- The verification (every address byte-checked against the retail x86 exe, the near-miss dead ends, the
  class registry, the render model) is from our own RE; the actual *idea* is his.
- AC4Coop has no license file, so its code is all rights reserved. Use the method (the call sequence and
  addresses below) in your own code and credit him; ask him before copying or redistributing his code.

## Setup

- Steam **`AC4BFSP.exe`**, x86, fixed image base `0x400000`, **no ASLR** (so absolute addresses are
  stable; **RVA = VA − 0x400000** and in `.text` the file offset is `RVA − 0xC00`).
- An ASI plugin (Ultimate ASI Loader) for the engine calls; the reference is `AC4Coop.asi`.
- **Careful with address conventions.** AC4Coop's engine wrappers (`src/Scimitar/`, through its
  `Hook::Call*Method` helpers) call **absolute VAs**, while its hook sites in `phase1.cpp` are **RVAs**
  added to the module base (for example `base + 0x12FAACD`). If you copy wrapper addresses into an
  RVA-based hook framework, subtract `0x400000`.
- Single player only. Ubisoft Connect must be running for `AC4BFSP.exe` to start (see the
  [transform note](reading-the-player-s-world-transform-and-body-position-in-ac.md)); with a plugin in
  place, put Ubisoft Connect in offline mode and don't use the game's online features. `AC4BFMP.exe` is
  never run or injected.

## Route and why (the working spawn: build from the player's own cached builder)

```
world  = World::GetCurrentWorld()          // cdecl, VA 0x0054D4D0
player = world->GetPlayer()                // thiscall ECX=world, VA 0x0070E810
selector  = *(void**)0x04DEEF90            // PlayerProgression: cached RowSelector
builderHC = *(void**)0x04DEEF94            // PlayerProgression: cached EntityBuilder handle container
builder   = deref(builderHC)               // the container's object; if released, reload by its id
DuplicationManager::Begin(1,0)             // cdecl, VA 0x00A2D5A0
dupSel = ((RowSelector*)selector)->Duplicate(0,0)   // VA 0x007A3BD0
DuplicationManager::End()                  // cdecl, VA 0x00A2F320   (run even on fault)
rc = ((EntityBuilder*)builder)->BuildEntityWithSelector(&entity, dupSel)  // thiscall, VA 0x005FAC00
g_blockReg = entity;  world->AddEntity(entity)      // thiscall, VA 0x0070E860
```

Key points:
- **The builder is the player's, cached when the player spawned.** There is no need to construct or
  populate one — `PlayerProgression` already holds it. This is the single fact that makes it work, and it
  is the "builder the loader has already filled" that the
  [dead-ends note](spawning-a-new-character-in-ac4-black-flag-single-player-dea.md) was looking for.
- **The builder object is usually released** after the player spawns; the *handle container* keeps its
  resource id, so reload by id: `HandleManager::CreateReference` (VA 0x00A0BE50) →
  `LoadingThread::AddLoadTask_Callback` (VA 0x00A2A6C0) → `LoadingThread::GetWaitTasks` (VA
  0x00A278F0), then poll the handle's object.
- `BuildEntityWithSelector` **consumes** the selector, so duplicate a fresh one first, inside an active
  `DuplicationManager::Begin/End` scope (outside it, `Duplicate` null-derefs).
- **Register it, then bind the pad:** hook `PlayerPadManager::GetUnusedPadID` (VA 0x00744CF0, RVA
  0x344CF0) and, while your "this is the puppet" flag is set, force an empty pad slot. Without this the
  spawned body enrolls onto the real player's pad/gamer and **you lose your inventory**.

## How the rest of the engine reads (what we learned the hard way)

- **A node renders only with a render record.** The per-frame graphics pass consumes a per-entity record
  reached through `Entity+0xB0` (an interface whose `+0x24` is a kind); a factory-created or `memcpy`
  clone of a node has `+0xB0 == 0` → invisible. `Entity::addVisual` (VA 0x00528300) appends a `Visual`
  to `+0x60`. (`+0xAC` is *not* a graphic pointer — it's the high half of a 64-bit flag word.)
- **Class registry:** every class has a ClassInfo descriptor (name, `id = CRC32(name)`, size, ctor).
  A vtable's `+0x14` getter returns it — enough to name any object at runtime and to find "the class
  that does X". (We dumped all 1376 for this exe.)
- **Data-driven spawners read but don't retarget:** the loader reads a cell record's
  `SpawningSpecification → SpawnNPCParams → DynamicReference` and resolves the character id, but
  crowd-life hosts take their model from the crowd system (they ignore the override), and only
  mission/domino spawners honour a chosen character — and they're mission-gated.
- **The debug/cheat "Spawn Dude" system looks inert in SP:** the cheats post a `NavigationDudeEvent`
  whose type id occurs exactly once in the exe (its own descriptor), so no listener uses it as a constant
  and the event is dropped. A listener that reads the id from the descriptor isn't ruled out (see the
  dead-ends note).

## Animating the spawned body

- **The spawned body has no walk-child skeleton.** On the body we built, the character node's
  walk-child pointer reads **`c14+0x134 == 0`** (null). With no walk children there is nothing for a
  bone mirror to write to, so a per-frame bone copy is a *silent no-op*: the body's world matrix moves
  (it follows your position) but the legs never cycle, so it glides instead of walking (Gotcha 8).
- **Bodies that do carry a skeleton animate under a bone mirror.** The crowd body in
  [`coop-ghost-avatar.md`](coop-ghost-avatar.md) does, and so did the body from our `mod16` `.forge`
  edit: both render **and** animate through the mirror. So "spawn from the cached builder" and "get a rig
  that animates" are two separate problems: the cached builder gives you the *identity* (a real Edward),
  the crowd/`mod16` source gives you the *skeleton*.
- **Kamzik123's answer is action replication, not bone writes.** Drive the body's **action** and let the
  engine's own blend tree interpolate: `SetTargetAction` picks the action, `ActivateCharacterActionSet`
  makes an action set live, the `SimpleAnimBlender<46>` blend tree blends the ground move cycle, and
  `GetCurrentAction` / `SetCurrentActionRatio` read and seek the blend phase. Addresses as AC4Coop's
  README lists them (x86, image base `0x400000`):

  | What | Address |
  |---|---|
  | per-frame hook point (AC4Coop's, in the Human update) | RVA `0x12FAACD` (VA `0x16FAACD`) |
  | `SetTargetAction` | VA `0x6625D0` |
  | `GetCurrentAction` | VA `0x666C80` |
  | `SetCurrentActionRatio` | VA `0x652640` |
  | `ActivateCharacterActionSet` | VA `0x651840` |

  With AC4Coop's shipped `AC4Coop.ini` (`HybridLoco=1`), the puppet's own state machine animates it on
  the ground from replicated ground data, and action replication runs everywhere else; `HybridLoco=0`
  uses action replication everywhere. Treat the table as a starting point, not a recipe: we recorded
  these addresses but did not drive them from our own plugin.

## Verification

- **Byte-level oracle:** every address in the spawn route and the engine-facts section was verified
  against the retail exe with a `pefile` + `capstone` script (resolve RVA via the PE sections, compare
  the bytes to the expected instruction). This caught a real class of bug: using AC4Coop's VAs where
  RVAs are required.
- **In game (2026-10-11):** the log shows `builderID = 0x2C0A3FCE0` (Edward) → `rc=0 entity=0x… added=1`
  → `pad forced to empty slot 1 (player pad kept)` → **two Edwards rendered on the Havana dock**.
- **In game (2026-10-11/12):** the spawned body's walk-child pointer is null (`c14+0x134 == 0`); the
  crowd-hijack body and the `mod16` body both render **and** animate through the bone mirror.
- **Not verified by us:** action replication on the spawned body from our own plugin (the addresses in
  the table are recorded, not driven from here), and whether `SetTargetAction` alone suffices or
  `ActivateCharacterActionSet` must be called first. AC4Coop does this in its own build.

## Gotchas

1. **You cannot spawn a character by creating an entity from a spawner/file-id.** The file-id resolve
   returns an empty template (`+0x60` NULL) and instantiating it faults. **Fix:** use the player's cached
   builder (above).
2. **A memory clone of the player node renders nothing.** `Entity::clone` copies the child/rig list but
   not `+0x5C` (scene) or `+0xB0` (render record). Don't go down this path.
3. **Copying AC4Coop's wrapper addresses as RVAs.** Its `src/Scimitar/` wrappers call absolute VAs;
   subtract `0x400000` for an RVA. Its hook sites in `phase1.cpp` are already RVAs (added to the module
   base), so don't subtract there.
4. **The second player steals your pad/gamer (inventory loss).** **Fix:** the `GetUnusedPadID` hook
   forcing an empty slot while the puppet is being enrolled.
5. **`RowSelector::Duplicate` null-derefs outside `DuplicationManager::Begin/End`.** Wrap it, and always
   `End` (use `__try/__finally`) or the scope corrupts every later duplication.
6. **The builder is often released.** `reloaded=0` on one load, `=1` on another — handle both (reload by
   id when the object isn't readable).
7. **`+0xAC == 0` on a clone is not "missing graphic".** It's a flag word; the real gate is `+0xB0`.
8. **A spawned body that "glides" has no walk children.** The spawned body's character node reads
   `c14+0x134 == 0` (a null walk-child pointer), so a per-frame bone mirror writes to nothing — the
   body translates but the legs never cycle. **Fix:** drive a body that actually carries a skeleton
   (the crowd-hijack or `mod16` source), or stop mirroring bones and replicate **actions**
   (`SetTargetAction` + blend tree) instead.

## Assets

None — no game files or extracted assets are shipped. Everything is code + addresses.

## Open questions

- Animation replication parity with the reference (action alias / blend tree / blend-in descriptor /
  phase seek). That is the reference's strength and where a fresh implementation should look first.
- Whether the spawned body survives world travel cleanly (the reference respawns it across travel).

## Related notes

- [`coop-ghost-avatar.md`](coop-ghost-avatar.md) — the earlier "drive a hijacked crowd NPC" body (works,
  wrong model, but it carries a walk skeleton). This note supersedes it for a real second *player* body.
- [`spawning-a-new-character-in-ac4-black-flag-single-player-dea.md`](spawning-a-new-character-in-ac4-black-flag-single-player-dea.md)
  — the spawn routes that didn't work, and the engine's spawn system; its open question about a builder
  the loader has filled is answered here.
- [`reading-the-player-s-world-transform-and-body-position-in-ac.md`](reading-the-player-s-world-transform-and-body-position-in-ac.md)
  — the player transform and body chain on the same build.
