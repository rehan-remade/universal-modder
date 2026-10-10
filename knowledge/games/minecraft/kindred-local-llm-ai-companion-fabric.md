---
kind: game
title: "Kindred: Local LLM AI companion with Ollama, bounded inference, autonomy, and memory"
game: "Minecraft"
games_also: []
game_version: "Minecraft Java 1.20.1, Fabric Loader 0.15.11, Fabric API 0.92.2+1.20.1"
platform: windows
engine: java
route: loader-api
tools: ["Fabric Loader 0.15.11", "Fabric Loom 1.6.12", "Yarn mappings 1.20.1+build.10:v2", "Gradle 8.7", "Java 17", "Ollama (local LLM inference)"]
anti_cheat: "none (single-player and private servers only; never tested against or designed for online anti-cheat environments)"
status: working
agents: ["Claude Code (Sonnet 5)"]
humans: []
date: 2026-10-07
links: []
tags: [fabric, ai-companion, npc, local-llm, ollama, autonomy, bounded-inference, navigation, raycasting, atlas, memory, reflexes, utf8-journal, gametest]
---

# Kindred: Local LLM AI companion with Ollama, bounded inference, autonomy, and memory

> A Fabric 1.20.1 mod that adds a living AI companion NPC to Minecraft, powered by local LLMs through Ollama. The companion executes tasks (gather/craft/smelt/build), navigates autonomously, maintains a bounded atlas with resource landmarks, reacts to danger with model-free reflexes, and persists inventory, mood, home, and 12 recent events in NBT. Verified through 17 Minecraft GameTests and 19 unit tests covering recipes, movement, sensors, map persistence, and the Ollama HTTP client against a local mock server.

## Setup
- **Minecraft:** Java 1.20.1
- **Fabric Loader:** 0.15.11
- **Fabric API:** 0.92.2+1.20.1
- **Fabric Loom:** 1.6.12
- **Yarn mappings:** 1.20.1+build.10:v2
- **Java:** 17 (release target)
- **Gradle:** 8.7
- **Ollama:** Any version with loopback HTTP API at `http://127.0.0.1:11434` (configurable endpoint)
- **OS:** Windows 10 (developed and tested on Ryzen 5 5600X, RTX 3060 12GB, 32GB RAM)
- **Mod version verified:** 0.1.0-alpha.4 (139,877 bytes JAR)
- **Test environment:** Dreamcraft [FABRIC] modpack (CurseForge instance with ~100 mods including KubeJS, FancyMenu, DML:Refabricated, Charmony)

## Route and why
`route: loader-api`. A pure Fabric mod implementing a custom `LivingEntity` subclass (`KindredEntity`) with local LLM integration. The companion is a real in-world entity with inventory, NBT persistence, sensors, and actions—not a passthrough, not a reimplementation of another game. Minecraft's own navigation, crafting system (`RecipeManager`), and furnace mechanics are used directly.

**Why this route:**
- **Local-first:** No cloud API, no API key. Ollama runs on localhost; the mod serializes inference across all companions to respect VRAM limits.
- **Bounded by design:** Sensors scan a budget of positions per interval (raycasting, 96-block vision, 8-block radius), atlas limited to 4096 chunks and 512 landmarks, memory capped at 12 events in NBT, journal rotates at 4 MiB with 3 archives.
- **Reflexes over inference:** Attack/retreat, item pickup, eating when hungry all happen without LLM calls. Only high-level planning and conversation go to the model.
- **Actor surrogate:** Uses an unconnected `ServerPlayerEntity` for vanilla interaction hooks (mining drops, tool damage, crafting grids) but never registers it as an online player. Modded machines requiring authenticated players may need adapters.

## How the game works (what we had to learn)
**Execution boundaries**
- `KindredEntity` is a `LivingEntity` ticked by Minecraft. It owns inventory, mood, home position, bounded memory (12 events), sensors, and a job executor.
- The local model receives a compact observation and returns an `Intent`—an allowlisted data object, never arbitrary code. Each game action re-checks prerequisites before executing.
- `Actor` is a fake `ServerPlayerEntity` (no network, no operator rights, survival mode) used only for vanilla hooks around single interactions. Inventory is synced immediately before/after use. It cannot handle player-stage systems or machines that require session authentication.

**Local inference (`LocalModels`, `Brain`)**
- Accepts **loopback HTTP only** (127.0.0.1 or ::1), disallows redirects, bounds response bytes, applies timeouts, serializes inference across all companions.
- Ollama requests disable thinking output, use JSON schema for action turns, bound context/output tokens.
- `Brain` builds observations on the server thread, runs inference in a daemon executor, dispatches completion back to server thread. Generation IDs and config-revision checks discard stale replies.
- Model roles: only the primary model (actions + chat) is wired in alpha.4; `plannerModel` and the legacy `socialModel` are config fields that aren't used yet (Gotcha 7).
- Failed services use exponential cooldown; deterministic actions (reflexes, Scout search) continue working offline.

**Sensors (`Senses`)**
- Visits a **budget** of nearby positions each interval. Raycasts exclude occluded blocks.
- Vision: 96 blocks range, 8-block radius scan, item/hostile queries bounded in count.
- No scanner loads chunks. Navigation uses Minecraft's ground pathfinder, throttled to ≤1 attempt/second for nearby goals. Stuck jobs stop instead of retrying expensive paths.

**Actions**
- Small jobs: gather (mining with gradual survival breaking, checks harvestability), craft (2×2 or 3×3 grid, tentative transaction → recipe match → capacity check → commit), smelt (real furnace with ingredients/fuel), place, use, equip, follow, wait.
- Reflexes pre-empt jobs: attack/retreat from hostiles, item pickup (0.65-block radius), eat when hungry.
- Autonomy mode: progression goal is a stone pickaxe, returns home when tired.
- Detects and remembers damage source for 100 ticks (5 seconds at 20 TPS). Tamed pets of the same owner (`TameableEntity`) are allies; their aggro toward the companion is canceled, damage from them rejected.

**Atlas and Scout**
- `Atlas`: owner-scoped persistent world state, dimension-separated. Holds up to **4096 chunks** (16×16 cells) and **512 landmarks** (resources, crafting tables, furnaces). Crafting table/furnace marks survive eviction; the companion prefers visiting a known station over crafting a duplicate.
- `Scout`: deterministic search without LLM. Explicit "explore" or "find tree" commands route through `Orders`; local waypoints prefer less-visited cells, use reachable vanilla paths, stay within loaded chunks and 64 blocks of owner/home.
- Placed blocks enter sensors/atlas immediately in the same tick.

**Memory and Journal**
- **NBT:** persists 12 recent events, inventory, equipment, owner UUID, mood, home, mode. A `PersistentState` roster retains owner/body IDs and last location even after chunk unload (prevents duplicate spawn).
- **Journal (`logs/kindred/events.jsonl`):** UTF-8 JSONL, 4 MiB rotation, 3 archives. Events include request context, raw model replies, accepted/rejected intents, task transitions, paths, inventory deltas, damage, failures. Game-thread snapshots queue to a daemon writer; response-body deadlines release the shared inference slot even if the body stalls after headers.

**Recipes and crafting**
- `Recipes` rebuilds its index after datapack reload. Standard grid recipes work; other types described as needing station adapters.
- Autonomous prerequisite search bounded by depth, ingredient alternatives, allocation attempts (early-game helper, not a full modpack solver).
- `PackKnowledge` reads installed mod IDs and FTB Quests titles (advisory hints only, not unlock truth).

**Config persistence**
- `Config` publishes validated snapshots. `WatchService.take()` blocks until file edits, applies debounce. Invalid JSON leaves previous values. File save uses temp + atomic rename. Identical watch event doesn't advance revision.

## Build steps
1. Clone or extract the mod source.
2. Build with Gradle:
   ```bash
   cd kindred-source/kindred
   ./gradlew build
   ```
   - Requires JDK 17, uses Gradle 8.7 wrapper.
   - Output: `build/libs/kindred-0.1.0-alpha.4.jar` (139,877 bytes).
   - Build time: ~1m 42s on first clean build.
   - Warnings: deprecated Gradle features (non-critical).

3. Install:
   - Place JAR in `<instance>/mods/`.
   - Ensure Fabric Loader 0.15.11+ and Fabric API 0.92.2+ are installed.

4. Ollama setup:
   - Install Ollama, pull a model (e.g., `qwen2.5:7b`).
   - Start with `ollama serve` (binds to `http://127.0.0.1:11434` by default).
   - Or use the mod's built-in Ollama launcher (client menu, starts only the installed executable with `serve` args, no-cloud mode).

5. In-game:
   - Press K → Компаньон → Создать (Create Companion) or `/kin spawn`.
   - Configure model endpoint in `config/kindred.json` if not using default.
   - Companion spawns near the player, persists across sessions via NBT.

## Verification
**19 unit tests** (pure Java, no Minecraft):
- Config loopback validation, JSON intent parsing, RTX 3060 profile budget, Russian-language search routing, UTF-8 journal with queue flush, local mock HTTP Ollama transport, request/download sequencing, download cancellation, response size limit, timeout on stalled body after headers.
- Result: 0 failures.

**17 Minecraft GameTests** (`runGameTestServer`):
- 12 original: inventory, recipes (2×2/3×3 grid), smelting, mining (harvestability checks), visibility (raycasting occlusion), allied wolves.
- 5 new (alpha.4): atlas NBT save/load (owner/dimension separation, 512 landmark cap, crafting table prioritized in short context), duplicate station blocking (placed crafting table immediately known, repeat craft/place blocked without material loss, second companion instance finds station in atlas), base tool prerequisite (wooden pickaxe chosen before mining stone when materials visible), birch search (chat → Scout without model, birch recognized, `find_wood` completes), real movement (normal Minecraft navigation physically moves body, search stays active, model request count unchanged).
- Result: all 17 pass, 0 failures.

**Manual verification**:
- Alpha.2 user logs decoded (CP1251): model responses and duplicate-station symptoms present, but raw intents/action results missing (exact plan at moment not recoverable).
- Alpha.4: shipped JAR tested in user's Dreamcraft instance (a CurseForge Fabric pack with ~100 other mods). Two short play sessions; no crashes reported from Kindred itself.

**Oracle**: GameTest assertions for entity state, NBT round-trip, recipe matching, sensor output; mock HTTP for transport; real `latest.log` inspection for runtime behavior. Full model inference quality (actual Ollama weights, real-world task success rate, FPS/VRAM under load) verified only by end user in live play.

**Not verified**:
- Windows client UI, Lucky Blocks interaction, full Dreamcraft compatibility under heavy load, RTX 3060 FPS/VRAM measurements, industrial mod machines (Create, Mekanism, etc.), portals, full FTB Quests graph integration, multiplayer (companion ownership across server restarts).

## Gotchas
1. **Wolves killed the companion (alpha.2 symptom).** **Cause:** `Senses` only classified `HostileEntity` as threats; neutral mobs (`WolfEntity`) that turn hostile were ignored. No registration of direct attacker. **Fix (alpha.3):** Mobs targeting the companion or its actor are recognized as threats if visible. Damage source remembered for 100 ticks (5s). Tamed pets of same owner (`TameableEntity`) treated as allies: their aggro canceled, damage rejected. Other players and their pets cause retreat without retaliation. Wild attacking animals trigger normal defense. Defense runs as reflex every 5 ticks, no LLM call.

2. **"Explore the world" command → companion stands still.** **Cause:** Chat → intent → Scout routing not traced in code; `Scout` exists but command path unclear. **Fix (alpha.4):** Orders system routes explicit "explore" / "find tree" to Scout; local waypoints prefer less-visited cells. GameTest confirms birch search completes without model.

3. **Infinite crafting table loop.** **Cause (alpha.2):** Autonomy could craft and place duplicate stations. **Fix (alpha.4):** Station deduplication: checks `knownStation()` before crafting. Placed block enters atlas immediately (same tick). Second companion instance of same owner finds station in atlas, chooses `visit` when beyond crafting distance. GameTest: placed table known, repeat blocked without material loss.

4. **Doesn't pick up resources.** **Symptom:** Items nearby but not collected. **Cause:** `pickup` reflex works in 0.65-block radius; may need timing check. **Status:** Reflex present, range confirmed, but real-world delay/priority not fully traced. Investigate tick budgeting if items consistently ignored.

5. **AFK without explanation (companion idles indefinitely).** **Cause:** No navigation stuck-detection for Scout; only `Actions.stuckTicks` for job executor. **Status:** Partial fix (stuck jobs stop after threshold), but no fallback recovery or user notification when perpetually stuck. Open issue for Scout/Actions coordination.

6. **Companion dismantles base walls ("mineable" is global).** **Cause:** No protected zone around home; any block in range is harvestable if needed. **Fix (planned):** `baseProtectionRadius` config to exclude blocks near home from mining consideration. Not yet implemented in alpha.4.

7. **No separate navigator model (dual-role architecture not used).** **Cause:** `plannerModel` field exists but not wired; all roles use primary model. **Status:** Single-model mode works; dual-role mode (brain + navigator) and economy mode (shared model) are unimplemented extension points.

8. **Gradle build cache issues in temporary environment (validation-only gotcha).** **Symptom:** Forbidden Unix socket probe, missing authentication key service. **Cause:** Gradle/Loom accessing unavailable Minecraft services. **Fix (external to mod):** Temporary local Maven init-script, socket probe workaround. Not needed for normal user builds. Autonomous GameTests ran fine despite unavailable auth service.

9. **One GameTest had wrong crafting distance (fixture design bug).** **Symptom:** Station exactly 4 blocks away; unclear if in range. **Fix:** Moved fixture beyond crafting range, added explicit condition checks. Test now unambiguous; assertions not weakened.

10. **Journal may lose events on crash (queue in memory).** **Cause:** Daemon writer flushes queue at rotation or shutdown, but sudden JVM kill loses unflushed events. **Status:** Accepted tradeoff for performance. UTF-8 JSONL survives rotation; worst case is last few seconds of events lost.

11. **Unicode in logs breaks Windows console output (external tool issue).** **Symptom:** `UnicodeEncodeError` in `um kb search` on Windows CP1251 console. **Cause:** Python's stdout encoding, not the mod. **Fix:** Redirect to file or use UTF-8 console (`chcp 65001`). Mod's own journal is UTF-8 JSONL, no issue.

12. **Companion re-spawns for same owner after chunk unload.** **Fix:** `PersistentState` roster retains owner/body ID + last location even after chunk unload. Prevents duplicate spawn on same owner. Verified in GameTest.

## Assets
None generated. The companion uses default Minecraft entity rendering (no custom model in alpha.4). Future versions may add custom models/textures.

## Cost and time
- **Development:** Multiple alpha iterations (alpha.2 → alpha.3 → alpha.4) across several weeks.
- **Alpha.4 verification:** ~1 day for 19 unit tests + 17 GameTests, log analysis, architecture docs.
- **Agent:** Claude Code (Sonnet 5) for codebase audit, test design, architecture documentation.
- **Gradle build time:** ~1m 42s clean build, <30s incremental.
- **Test execution:** `runGameTestServer` completes all 17 tests in <5 minutes.

## Open questions
- **Dual-role architecture:** `plannerModel` (separate navigator) and economy mode (shared model) are designed but not wired. Which improves task success rate vs. VRAM cost?
- **Base protection radius:** Config key designed but not enforced. What's the right default (8 blocks? 16?)?
- **Industrial mod integration:** Tested with DML:Refabricated, Charmony in instance, but no custom adapters for Create/Mekanism machines, AE2 terminals, or Botania rituals.
- **FTB Quests unlock truth:** `PackKnowledge` reads quest titles as advisory hints but doesn't query actual completion state or rewards. Real FTB Quests API adapter is an extension point.
- **Multiplayer ownership:** Companion persists owner UUID and respects it, but cross-server or realm behavior untested.
- **Performance profiling:** RTX 3060 VRAM, FPS impact, Ollama inference latency under heavy modpack load not measured. User anecdotes only.
- **Scout recovery from perpetual stuck:** Currently stops but doesn't notify user or attempt alternate path. Needs telemetry + fallback.
