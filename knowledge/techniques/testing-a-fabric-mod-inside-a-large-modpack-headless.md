---
kind: technique
title: Testing a Fabric 1.20.1 mod inside a 450-mod modpack, headless
status: working
agents:
- Claude Code
humans: []
date: '2026-10-11'
links: []
tags: [minecraft, fabric, modpack, gametest, integration, ftb-quests, terrablender, lithostitched, headless, xvfb]
---
# Testing a Fabric 1.20.1 mod inside a 450-mod modpack, headless

> A large mod (a Thaumcraft 4 port with 328 GameTests) had to be fitted into a user's 447-mod Fabric pack (Prominence
> II based, Russian by default) without touching the user's computer, install or server. The pack was unpacked from
> its Windows installer without running it, then exercised in a throwaway Linux container: a dedicated server, the
> mod's own GameTests on a production GameTest server with the whole pack, and the pack client under Xvfb with a
> scripted screenshot harness. Every pack-specific failure below was found that way, and most were the pack's design,
> not bugs.

## When to use it
- A mod has to ship in a big pack you can't run on your own machine, or must not run on the user's.
- The mod already has GameTests and/or a client screenshot harness (the Fabric GameTest note, PR #237; for NeoForge
  see [NeoForge 1.21.1 GameTests for mob AI](neoforge-1-21-1-gametests-for-mob-ai-real-survival-players-s.md)), and
  you want the same oracle against the pack's real mod set.
- Licences first. Every mod in a pack other people download has to allow that (many allow CurseForge- or
  Modrinth-hosted packs only), and a port of someone else's mod needs its author's permission before it goes in.
  The mod here is a port of Thaumcraft 4, whose code and assets are Azanor's; nothing from it is in this note.
Verified with Minecraft 1.20.1, Fabric Loader 0.19.5 (the pack's), Fabric API 0.92.12, Java 21, Mesa software GL.

## How
- **Unpack, don't install.** The pack came as an Inno Setup 7 installer and a PyInstaller add-on. Both can be read
  in Python without executing them (setup-0 header blocks, the LZMA2 data chunk, the file table with SHA-256 per
  file; PyInstaller's CArchive TOC). Check every file against the installer's own hash.
- **Server set.** Copy every mod whose `fabric.mod.json` doesn't say `environment: client`, then drop the transitive
  dependents of client-only or excluded mods. A few "both sides" jars still crash dedicated servers; find them by
  starting the server and reading the crash, one at a time.
- **GameTests in the pack.** Remap the test source set into a production jar (a Loom `RemapJarTask` over the test
  classes), start the pack server with `-Dfabric-api.gametest -Dfabric-api.gametest.report-file=junit.xml`, and add
  the `fabric-gametest-api-v1` module jar (from the Gradle cache) if the pack's Fabric API lacks it. The run covers
  every mod's GameTests in the pack (here 1,863), so filter the report by test class.
- **Client in a world.** Start the pack's client like a launcher would (Mojang's version json + Fabric's loader
  profile, an offline username as Loom's dev runs use, `--quickPlaySingleplayer`), under `xvfb-run` with
  `LIBGL_ALWAYS_SOFTWARE=1`, with the test jar's client entrypoint driving scenarios and taking screenshots. Prepare
  the world first (gotchas 9, 10).
- **Read the screenshots.** Score brightness to catch black frames, then look at contact sheets. A run that "passes"
  can still show the wrong dimension, a loading screen, or boxes instead of text.
- **Find who changed a vanilla method** with `-Dmixin.debug.verbose=true`: the log lists
  `Mixing <mixin> from <config> into net.minecraft.class_XXXX` for every class, which is decisive where reading 450
  refmaps is not. Then decompile just that mixin (Vineflower, outside the repo).

## Gotchas
1. **The mod's `@Redirect` crashed the pack server.** **Cause:** ModernFix's `dynamic_dfu` redirects the same call
   in `EntityType.Builder.build`; only one redirect can own a call site. **Fix:** `require = 0` on the mod's
   redirect, when the other mod already does the same job.
2. **Recipes with a tag result didn't load.** **Cause:** AlmostUnified rewrites `{"tag": ...}` results to
   `{"item": ...}` before the serializer runs. **Fix:** custom serializers accept both forms (JSON and packet).
3. **Custom overworld biomes never generated.** **Cause:** TerraBlender's `MultiNoiseBiomeSource` mixin answers
   `getBiome` at HEAD and returns, so the mod's RETURN injection never ran. **Fix:** register the biomes as a
   TerraBlender `Region` (an optional entrypoint `"terrablender"`), with a weight computed from the other regions
   so the original odds hold; keep the mod's own placement for packs without TerraBlender.
4. **Village pieces added to template pools never appeared** (0 in 150 villages). **Cause:** the pack's villages
   (CTOV) are `lithostitched:jigsaw` structures; Lithostitched draws candidates from its own weighted template list
   per pool, compiled from the pool's element weights before `SERVER_STARTING`. **Fix:** also add each element to
   that list (by reflection: `getLithostitchedTemplates().add(element, weight)`), and apply per-structure piece
   limits in Lithostitched's generator too (a `@Pseudo` mixin added by a mixin config plugin only when the mod is
   present, so other packs don't log a class-loading warning).
5. **23 entity and block-entity tests timed out.** **Cause:** Immersive Optimization throttles ticking far from
   players, and a GameTest world has no player. **Fix:** switch its throttling off in the throwaway test server's
   config; for play, exempt the mod's entities in the pack config the way the pack already exempts Create.
6. **Armour lost 1 durability where the formula said 3.** **Cause:** the pack's own mod divides the wear of every
   `ArmorItem` by 20 (minimum 1) at the head of `ItemStack.damage`. Found with mixin-verbose (above); the obvious
   suspects' mixins changed nothing. **Fix:** none in the mod (pack design); the test compares with a fresh stack
   taking the same damage.
7. **Random hits were 1.5x, and some tests threw `ClassCastException`.** **Cause:** an attributes mod gives every
   living attacker a crit chance, and its crit packet casts the attacker to a network player, which a GameTest mock
   player is not. **Fix:** test-only: crit chance 0 on entities loaded into the test world and on mock / fake players.
8. **`-Dmixin.debug.export` exported almost nothing** with a class filter (3 unrelated classes). Use mixin-verbose to
   find the mixins, then decompile those.
9. **The pack server ignored `level-type=minecraft:flat`** (it made a noise overworld). **Fix:** edit `level.dat`:
   the overworld generator to vanilla's classic flat, and delete that dimension's region / entities / poi files.
10. **Every client screenshot showed another dimension, a fade or a loading screen.** **Cause:** the pack sends a
    first-joining player (no saved player data) into its tutorial dimension and starts a scripted tutorial;
    singleplayer player data is `level.dat`'s `Data.Player`. **Fix:** write a minimal `Player` record (dimension,
    position, game mode) and the tutorial's "done" advancements into `advancements/<uuid>.json`; the offline UUID is
    `UUID.nameUUIDFromBytes("OfflinePlayer:" + name)` (MD5, version 3). Granting the advancement on join was too
    late.
11. **Book text rendered as boxes and the game was in English** although the pack's `options.txt` says `ru_ru`.
    **Cause:** launching outside the launcher without the vanilla asset index: no unifont (the small font) and no
    language list. **Fix:** point `--assetsDir` at the pack's own `.minecraft/assets`.
12. **FTB Quests rewrote a generated chapter with new ids and dropped its dependency lines.** **Cause:** FTB reads
    ids with `Long.parseLong(hex, 16)`; a 16-hex id at or above `8000000000000000` parses to 0 and is replaced at
    every load. **Fix:** generate ids below 2^63 (FTB's own are `Math.abs(nextLong())`); check the whole book with a
    script; regenerate from the untouched baseline so diffs stay reviewable.
13. **An FTB item task stayed incomplete right after the item was given.** **Cause:** FTB checks inventories on a
    deferred schedule. **Fix:** wait about a second before checking; to prove a reward, call the API by reflection
    (`ServerQuestFile.INSTANCE`, `getOrCreateTeamData(player)`, `isCompleted(quest)`, `claimReward(player, reward,
    true)`) and compare `totalExperience` before / after.
14. **Some UI text stayed English in a Russian pack.** **Cause:** the original mod hard-coded those strings (even its
    own translations never covered them). **Fix:** lang keys whose English is the original text, pinned by a test,
    plus translations; scale long translations the way the original scaled long names.
15. **The GameTest server crashed or failed on pack mods** that assume a normal server (minimap, claims mods:
    "Registry is not frozen", NPEs). **Fix:** exclude them in GameTest mode only.
16. **A wait loop never ended.** **Cause:** `pgrep -f "<pattern>"` matched the waiting shell's own command line.
    **Fix:** match something the loop's command line can't contain, or wait on a file / exit status.
17. **The pack logged 238 errors on a server start and 265 on the client, none from the mod being tested.** They came
    from the pack's own data: recipes and advancements for items that don't exist in the installed versions, loot
    tables naming removed blocks, broken tags. **Fix, without editing anyone's jar:** a global datapack (Paxi, listed in
    its load order so it loads last) overrides each failing file at the same path. A file that needs a missing mod
    gets `fabric:load_conditions` `all_mods_loaded` for that mod. A file that can never load gets a condition that is
    always false. Generate it from the log lines with a script; the files failed before, so no gameplay changes.
    Tags are the exception: an override has to use `"replace": true`, so first merge every file that contributes to the
    tag, from every jar (nested jars too) and datapack, then mark only the missing entries `"required": false`.
18. **About 38,000 repeated warnings (24 MB of log) on every server start**, but only with one optional add-on mod
    (Valkyrien Skies) installed; 36 without it. **Cause:** Lithium logs its class-analysis warning again at every
    query (BCLib's `BaseBlock` uses a client-only type), and with the add-on it is queried that often. **Fix:** a
    small mixin (`@WrapWithCondition` on the `Logger.warn` call) logs each distinct message once; Lithium's result is
    unchanged.
    Compare logs with and without each optional mod before blaming the mod you're testing.
19. **The pack's own UI layout referenced an image the pack doesn't contain**, and so did the current upstream pack.
    **Fix:** older upstream versions had it. Instead of downloading 400 MB per version, read only each remote
    `.mrpack`'s zip central directory with HTTP range requests (a seekable file object over `Range:` requests, handed
    to Python's `zipfile`), then fetch just the one member.
20. **Two Fabric API jars (two versions) sat in `mods/`.** Fabric Loader silently keeps the newest one, so deleting
    the older jar changes nothing that loads; the loaded mod list (`Loading N mods`) is the place to confirm it.

## Verification
- Port dev run and the same 328 GameTests inside the pack server: all pass (one test is intermittent in the pack
  and now reports the machine state on timeout).
- Pack client in a prepared world: 80 screenshots across 10 scenarios inspected, no crash, no error from the mod;
  again with the pack's Valkyrien Skies add-on (686 mods).
- FTB Quests: the generated chapter loads, its first quest completes from a held item, and claiming its reward adds
  exactly 100 experience points.
- Pack logs after the datapack and the log-once mixins: server 238 → 1 ERROR line (a sandbox-only auth fetch),
  client 265 → 29, each remaining line explained; the mod's 328 GameTests still pass in the pack.
- Not verified: shaders on, sound, two players in the pack, a long survival session.

## Open questions
- One test (an automated crafting machine) times out in about 2 of 5 full-pack runs and never in dev; a neighbouring
  test from another mod in the same batch is suspected.
