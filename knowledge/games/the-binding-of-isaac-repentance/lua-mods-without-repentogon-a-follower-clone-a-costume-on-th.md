---
kind: game
title: 'Lua mods without REPENTOGON: a follower clone, a costume on the back, an undroppable trinket, safe refactoring'
game: 'The Binding of Isaac: Repentance+'
games_also: []
game_version: 'Repentance+ v1.9.7.17 (Steam)'
platform: windows
engine: native
route: loader-api
tools: [ModUploader, Python + Pillow, lupa, luaparser]
anti_cheat: none (Steam Workshop mods; online co-op not touched)
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: [fareria]
date: '2026-11-07'
links:
- https://steamcommunity.com/sharedfiles/filedetails/?id=3828867916
tags: [lua, no-repentogon, clone, costume, trinket, refactoring, workshop]
---
# Lua mods without REPENTOGON: a follower clone, a costume on the back, an undroppable trinket, safe refactoring

> Patterns from two Isaac mods made on plain Repentance+ with no REPENTOGON: "Spare Me" (an active item whose
> translucent clone follows you and heals you) and parts of the "Kira Yoshikage" character mod (a trinket that
> sits on the player's back and can't be dropped, plus a large refactor of the stand code). Spare Me was played
> by the human in the real game on several characters and works; the costume and the no-drop trinket only passed
> load checks so far.

## Setup
- The Binding of Isaac: Repentance+ v1.9.7.17, Steam, Windows 10. REPENTOGON installed but deliberately not used:
  every feature must work without it.
- Game resources extracted with the game's own `tools/ResourceExtractor` into `extracted_resources/`; used only
  as a reference for file names and frame layouts (not shipped).
- Checks run outside the game: `luaparser` (syntax), a stub loader on `lupa` that runs `main.lua` with fake API
  tables (load order, missing globals), and the game's `log.txt` after a real launch.

## Route and why
Plain Lua mod API (`RegisterMod`, callbacks, `content/*.xml`). REPENTOGON would make several things one-liners
(reading a sprite's layer sheets, blocking a trinket drop), but many players don't have it, so every feature
here is built from the vanilla API only.

## How the game works (what we had to learn)
- **Item icons:** in `content/items.xml`, `gfxroot="gfx/items/"` plus `gfx="name.png"` resolves to
  `resources/gfx/items/collectibles/name.png` (trinkets: `.../trinkets/`). Putting `collectibles/` into
  `gfxroot` yourself doubles the folder and the icon is silently blank.
- **anm2 sheet paths** are relative to the anm2's own folder. `Path="totem_revive/totem.png"` inside
  `gfx/totem_revive/totem.anm2` points to `gfx/totem_revive/totem_revive/totem.png`: the sprite renders at the
  right size and position but invisible, with no error anywhere.
- **Player sprite layout** (`gfx/001.000_player.anm2`): body animations `WalkDown/Up/Left/Right` (20 frames)
  plus head overlay `HeadDown/...` (4 frames); 15 layers, the skin sheet on all but layer 13 (`ghost`). Body frame
  pivot (16,25) at y+2, head pivot (16,28) at y-5 from the entity point.
- **Character skins:** `players.xml` maps each character to a skin sheet in
  `gfx/characters/costumes/` (e.g. `character_001_isaac.png`, tainted ones `..._b_...`). The list order matches
  `PlayerType` 0..40, so a table indexed by `player:GetPlayerType()` gives the right sheet for every vanilla
  character. Modded characters' sheets can't be read without REPENTOGON.
- **Costumes** (`content/costumes2.xml`, `player:AddNullCostume(Isaac.GetCostumeIdByPath(...))`) follow the
  body animation by name: an anm2 with only `WalkDown/Up/Left/Right`, one keyframe with `Delay=20` each, is enough
  for a static attachment. Layer names map to the player's layers (`top0` draws over the head).
- **Callback rates:** `MC_POST_PEFFECT_UPDATE` runs at 30 Hz while the player moves at the render rate, so
  anything that copies the player's speed per update falls behind. Render-side smoothing fixes the stutter.
- **Keeper's hearts:** one coin heart is two half-heart units in `AddHearts`.

## Build steps
1. **Follower clone without an entity.** Keep the clone's state in Lua (position, trail, health pool) keyed by
   player index; draw it in `MC_POST_PLAYER_RENDER`.
   - Sprite: a separate `Sprite()` loaded from `player:GetSprite():GetFilename()`, sheet replaced on every skin
     layer from the `PlayerType` -> skin table, tinted blue and translucent via `Sprite.Color`.
   - Movement: record a trail point every few units the player moves and keep the clone a fixed number of points
     behind. It walks the exact path, stops when the player stops and never needs a speed of its own. Lerp the drawn
     position toward the logical one each render.
   - Animation: `SetFrame("Walk"..dir, step % 20)` and `SetOverlayFrame("Head"..dir, 0)` on the clone's own sprite.
2. **Swapping an active item's icon** (full jar / empty jar): two items in `items.xml`; each update, if the state
   says "clone out", replace the held item in its slot (`RemoveCollectible` + `AddCollectible(id, 0, false, slot)`,
   `SetPocketActiveItem` for pocket slots). Doing it in the use callback itself is unsafe.
3. **Per-character behaviour:** containers (`AddMaxHearts`), else bone hearts (The Forgotten), else soul hearts;
   The Lost gets a one-hit `HOLY_MANTLE` effect re-added each room; Keeper pays coins.
4. **Save across Continue:** `mod:SaveData(json.encode(state))` on `MC_PRE_GAME_EXIT` and new level, load on
   `MC_POST_GAME_STARTED` with `continued`.
5. **Undroppable trinket:** the engine's "can't drop" is hard-coded for Tick. Without REPENTOGON: each update, if
   the player held it last update and doesn't now (and it didn't consume itself), find the trinket pickup with
   that subtype (mask off the golden flag) spawned in the last few frames near the player, remove it and
   `AddTrinket` it back.
6. **Refactoring a 12k-line mod safely:** move code by exact line ranges with a script that asserts the first
   line of every range, rebuild each file's `local X = Kira.X` header from what the file actually uses, then check
   (a) the constants table dumped through the stub loader is byte-identical before and after, (b) every header
   name is defined in a file included earlier, (c) no accidental globals.

## Verification
- Spare Me: played by the human in the real game. Checked: the clone heals after damage (red and soul hearts),
  follows through rooms, The Lost shield, Keeper coins, icons, no player animation glitches after the fix.
- Refactor: constants dump identical (659 and 668 values), reference checker clean, the mod loads in the real game
  with no errors in `log.txt`. Per-item synergies after the move were not all replayed.
- Costume on the back and the no-drop trinket: only load checks and an offline preview composited on Isaac's real
  sprite; not seen in game yet.

## Gotchas
1. **The player turned blue and lost his walk animation.** **Cause:** drawing the clone by temporarily changing
   the real player's sprite (`SetFrame`, `Color`) and restoring it; `Sprite.Color` returns a live reference and
   the engine doesn't restart an animation it thinks is already set. **Fix:** never touch the player's sprite; use
   a separate `Sprite()` on the same anm2.
2. **The clone copied shooting, hurt, item-pickup animations and even the charge bar.** **Cause:** using
   `player:Render(offset)` to draw a second copy renders the player's full state. **Fix:** a separate sprite as in 1.
3. **The clone lagged further and further behind.** **Cause:** speed copied per `PEFFECT` update (30 Hz).
   **Fix:** follow a trail of points instead of chasing with a speed.
4. **Icon blank, animation invisible, no error.** **Cause:** a doubled folder in `gfxroot` or a sheet path relative
   to the wrong folder. **Fix:** see "How the game works"; when a sprite is invisible, log its scale and alpha: if
   they are sane, the sheet path is wrong.
5. **Split bubbles spammed `bad argument #1 to 'TakeDamage'` and circled forever.** **Cause:** the owner stored as
   `EntityPtr(...).Ref` is an `Entity`, so `.Damage` is nil on it. **Fix:** `:ToPlayer()` before reading player
   fields.
6. **Two mods with the same feature.** The human had another Workshop totem mod enabled; its animation hid the fact
   that ours never rendered. Check `mods/` for look-alikes before trusting an in-game check.
7. **Workshop upload stuck at a low percentage.** It finished in the background; the item page was correct.
   ModUploader keeps running and shows the game as "in game" in Steam: close it by exact PID.

## Assets
Icons, clone UI hearts and the back costume were hand-placed pixel grids (Python + Pillow) in a fixed palette.
For Cheap Trick, an image model (fal, Nano Banana 2.1 edit) turned an anime reference into pixel-art references
first; the final sprites were redrawn by hand from them, because direct downscaling lost detail and the outline.

## Cost and time
Spare Me v1: about 30 minutes from spec to a working, published mod, including three in-game test rounds by the
human.

## Open questions
- A clean way to show costumes (hair, item looks) on a clone without REPENTOGON.
- Whether the costume's `back` layer really renders behind the player when he faces down (not yet seen in game).
