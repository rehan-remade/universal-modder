---
kind: game
title: 'Ruby Rush: 220-talent Forge 1.20.1 mod - GUI, vein miner, bytecode-derived icon UVs'
game: Minecraft
games_also: []
game_version: '1.20.1 (Forge 47.4.10)'
platform: windows
engine: java
route: loader-api
tools: [javap, gradle, pillow, python]
anti_cheat: none
status: working
agents:
- OpenCode (mimo-v2.6-flash-free)
humans: []
date: '2026-10-06'
links: []
tags: [forge, gui, talents, vein-mining, icons, bytecode]
---
# Ruby Rush: 220-talent Forge 1.20.1 mod - GUI, vein miner, bytecode-derived icon UVs

> Built "Ruby Rush" (Рубиновая лихорадка): a content mod for Minecraft Java 1.20.1 with a 220-talent tree
> across 9 tabs, custom GUI, ore vein mining, full-tree felling, death chest and rubies, on the Forge
> loader route. It ships as a local v1.4.0 release; it runs in the real game — the human played it, and a
> 201-check Python suite verifies sources, jar and assets on every build.

## Setup
- Windows 11, Prism Launcher instances (`1.20.1`, `1.20.1(1)`), game **Minecraft Java 1.20.1**,
  loader **Forge 47.4.10** with official mappings (`_mapped_official_1.20.1`).
- JDK = Prism's bundled `java-runtime-gamma` (Java 17); Gradle 8.8 from the wrapper dist, invoked by
  absolute path with `JAVA_HOME` set inline; ForgeGradle pulls MC artifacts into
  `~/.gradle/caches/forge_gradle/`.
- Python 3.12 + Pillow for the icon pipeline and the `verify_*.py` build gate; user env `PYTHONUTF8=1`.

## Route and why
- **loader-api (Forge).** The target launcher already runs Forge instances, so a normal `mods/*.jar`
  mod was the shortest path. Datapacks/resource packs can't do a custom GUI with per-player talent
  state; a coremod/mixin route wasn't needed because everything (effects, events, packets, config)
  has supported Forge APIs. Anti-cheat never enters the picture: single-player only.

## How the game works (what we had to learn)
- **Mod shape:** `DeferredRegister` for items/blocks/effects/menus; talent effects as normal
  `MobEffect`s re-applied from an attribute recompute (stale attributes removed explicitly); config
  via `ForgeConfigSpec`; talent points/refund over a `SimpleChannel` with bounds-checked packets;
  per-player progress in Forge persisted player data (survives death/relog/restart);
  GUI = `AbstractContainerScreen`-style screen blitting one 16x16 PNG per talent from
  `textures/gui/talent_icons/<tab>.png` (220 files, 56 effect chains).
- **Using vanilla entity textures as GUI art needs exact box UVs.** For a box `texOffs(X,Y)` with
  dims `dx,dy,dz` (derived with `javap` from `net.minecraft.client.model.geom.ModelPart$Cube`):
  row 1 (`V = Y..Y+dz`) = [unused slot, DOWN, UP], row 2 (`V = Y+dz..Y+dz+dy`) =
  [WEST, NORTH, EAST, SOUTH]; north is the model's -Z side. In 1.20.1 there is **no `ModelChest`
  class** — the chest boxes live in `ChestRenderer.createSingleBodyLayer()` (bottom/lid/lock) and the
  dragon head boxes in `net.minecraft.client.model.dragon.DragonHeadModel`; the chest's front is the
  SOUTH face (lock at max Z). Composed icons: chest = lid-S + body-S + lock-S crops from
  `entity/chest/normal.png`, dragon face = NORTH crop of the upper head from
  `entity/enderdragon/dragon.png`.
- **Vein miner:** ores flood-fill 6 dirs through block tags (keeps adjacent non-ore untouched),
  logs flood 26 dirs but only while Shift is held, leaves drain through a gradual decay queue so big
  canopies don't pop 4k blocks in one tick.

## Build steps
```bat
cd <project>
del /q "build\libs\*.jar"
set "JAVA_HOME=<jdk17>" && <gradle-8.8>\bin\gradle.bat build --console=plain
python verify_v140.py   :: 201 checks: sources, lang, JSON, jar contents, bytecode strings
python deploy_v140.py   :: jar + instruction + doc -> Desktop, mods folders, backup
```

## Verification
- Oracle: `verify_v140.py` (201 assertions — talent/lang/effect counts, JSON validity, jar entries,
  bytecode strings like `ForgeConfigSpec`, icon count 220, no banned effects) re-run per round.
- In-game manual pass by the human every round: tree opens, points spend/refund, vein mining,
  death effects, tab layout.
- NOT verified: multiplayer/server play, non-Windows launchers, performance ceilings (vein cap is
  config'd to 4096 but stress-tested only casually).

## Gotchas
1. **Icon crops from entity textures were wrong whenever guessed visually.** **Cause:** box UV layout
   is non-obvious (row-1 first cell is unused, NORTH is the second cell, SOUTH is last) and chest/
   dragon models aren't where you'd expect (no `ModelChest` in mapped 1.20.1). **Fix:** derive rects
   from bytecode (`javap` on `ModelPart$Cube`/`ChestRenderer`/`DragonHeadModel`) and confirm with
   pixel dumps before shipping.
2. **The agent's image viewer returns stale/blank frames — visual checks lie.** **Fix:** dump images
   as ASCII/RGB text (Pillow → text file → read as text); raw channel probes settled ambiguous
   pixels (e.g. confirmed latch grey vs recess brown pixel-exact).
3. **Project files in `%TEMP%` vanished mid-project (root scripts, `build.gradle`, built jar gone,
   folders intact).** **Cause:** Windows Storage Sense cleans temp between sessions. **Fix:** keep the
   mod project in a permanent folder and treat any `%TEMP%` copy as disposable; release artifacts and
   backups live outside temp (kept sha256-verified copies of every jar).
4. **cp1251 console garbles Cyrillic output; PowerShell round-trips corrupt Russian text files.**
   **Fix:** never edit/read Russian-content files with PowerShell — use the editor tool or Python with
   explicit `encoding='utf-8'`; complex inline `python -c` (Cyrillic, `%TEMP%`, `\U` escapes) goes
   into a temp `.py` file instead.
5. **Long-running agent shell has a stale environment: user-PATH/PYTHONUTF8 additions apply only to
   new terminals** (`where blender` fails although user PATH has it; old sessions hit
   `UnicodeEncodeError` in `um kb`). **Fix:** set `PYTHONUTF8=1` and PATH entries inline per command
   or restart the session.
6. **pollinations free `gen` answers HTTP 402 for weapon words** ("sword", "weapon") while benign
   prompts succeed. **Fix:** rephrase to neutral items ("red ruby gem") or fall back to local
   `um comfy` (`--steps 15` ≈138 s CPU); rate limit is ~1 req/15 s with auto-retry on 429.
7. **Talent/effect drift between generator, lang files and jar.** **Fix:** one Python generator owns
   all 220 icon PNGs + effect chains and fails loudly on `MISSING SYMBOLS`; `verify` asserts the
   marker strings exist in the generator and counts PNGs inside the jar — cheap to run, catches
   half-edited rounds.

## Assets
Icons: 16x16 crops/compositions of vanilla textures (`gen_talent_icons.py`, Pillow, nearest-neighbour);
showcase banner/sprites: free `gen` (pollinations) with `--sprite` cutout; `gen_manifest.jsonl` kept
next to the images for seeds.

## Cost and time
Dozens of local build/deploy iterations over many rounds; money spend = 0 (free pollinations, local
ComfyUI, fal skipped — empty balance returns 403).

## Open questions
- Public hosting (Modrinth/GitHub) deferred — release stays local by owner's choice.
- The project's `build.gradle` was lost with the temp wipe; further development needs a rebuilt
  MDK-style build file (jar + sources backup are intact).
- Multiplayer balance and server-side behavior untested.
