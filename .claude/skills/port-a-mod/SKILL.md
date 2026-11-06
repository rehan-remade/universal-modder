---
name: port-a-mod
description: Port an existing mod to a newer game version or another mod loader while keeping its behaviour, values and quirks. Typical cases are an old Forge 1.7.10 or 1.12 Minecraft mod moving to modern Fabric or NeoForge, a Skyrim LE plugin moving to SE/AE, or a tModLoader 1.3 mod moving to 1.4. It covers pinning one source version, a private decompiled reference, an adaptation matrix, extracting the mod's data with scripts instead of retyping it, porting unit by unit with tests that catch drift, real-client checks, audits against the original, and keeping a long port resumable across sessions and agents. Use when the user wants to update, port, revive or re-implement a mod that already exists, or to continue such a port.
---

# Port a mod faithfully

When porting an existing mod, the original is the spec. A port rarely fails for lack of code. It fails by
**drift**:
- values recalled from memory or a wiki;
- mechanics borrowed from a later rewrite of the same mod;
- quiet "improvements";
- renderers that look roughly right;
- checks that the original made on the client and the port forgot.

The method below carried a Thaumcraft 4.2.3.5 port from Minecraft 1.7.10 Forge to 1.20.1 Fabric:
- 859 original classes became about 77,000 lines of port code;
- 323 GameTests cover it, and scripted real-client scenarios check what tests can't reach;
- the work spanned many sessions and two agent accounts.

The field note `knowledge/games/minecraft/porting-thaumcraft-4-1-7-10-forge-to-minecraft-1-20-1-fabric.md` has
its gotchas. Minecraft-specific mappings are in `references/minecraft-1-7-10-forge-to-1-20-fabric.md`.

Run the **mod-any-game** loop around this skill (intake, recon, lab, verify, publish, field note). This
skill replaces its "vertical slice" step with a long series of slices, one per unit of the original.
Bringing one game's content or mechanics into another game is the **mashup-mods** skill, not this one.

## Before you start: the license
The original's code and assets belong to its author. A port is built from them, often from a decompile of
them, so the original's license decides what of the port can be published. (This isn't legal advice; when
in doubt, ask the author.)
- **Find the license** of the release you will port: the mod's repository (`LICENSE`), its mod page, the files in
  the jar, or the author's release post. Write it into the status document (section 7), with the link.
- **An open license** (MIT, LGPL, GPL, a Creative Commons license): follow its terms. Keep the copyright
  notices, credit the author, and use the same license where it requires that (GPL, LGPL, CC BY-SA).
- **All rights reserved, no license at all, or a "no ports" clause:** publishing anything of the port (a
  jar, a public repository, the original's textures or sounds) needs the permission of the author or the
  current rights holder. Ask them, and keep their answer (a link or a quote) in the status document. With no
  permission, the port stays private.
  - Thaumcraft 4, the worked example here, is closed source. In 2014 its author had a decompiled copy taken
    off GitHub
    ([DMCA notice](https://github.com/github/dmca/blob/master/2014/2014-08-08-Thaumcraft.md)).
- **Tell the user which case it is before starting.** A private port for their own pack is their call.
- **Credit the original author** in the port and in any release, and don't present the port as an official
  version.

## 0. Pin one source of truth
- **Pin the exact release:** the jar, its hash (SHA-1), where it came from and its changelog. For a dead mod
  line, the last release is usually the right one.
- **Use one version as the reference, and only one.** A later rewrite with the same name (Thaumcraft 5 and 6
  against 4, a "Reborn" or "Legacy" fork) is a different mod.
  - The Thaumcraft port started from the wrong base and switched mid-way.
  - Weeks later, TC5 meshes, textures, an input handler and a swing hook were still in the code, although
    every audit had compared gameplay with TC4.
  - If the base ever changes, archive the old state, sort every area into keep / adapt / replace / remove,
    and grep comments and identifiers for the old version's name.
- **Write the rule where every future agent reads it:** the project's `AGENTS.md` (point any
  agent-specific instructions file at it). Example:
  "<mod> <version> is the only gameplay source. Keep its values, quirks and observable bugs. Later versions
  are not references. Do not silently improve gameplay. Never claim a build or test passed unless it ran."

## 1. Build a private reference
- **If the original's source is published** (its repository, a sources jar), work from the source at the
  pinned release's tag, and decompile the jar only to check that the two match.
- **Decompile** with Vineflower first. Fall back to CFR for the classes it fails on, and count those
  classes. The reverse-engineering skill has the tools.
- **Remap to readable names:**
  - 1.7.10 Forge jars ship SRG names (`func_12345_a`, `field_1234_b`). Remap them with the MCP `stable_12`
    CSVs (`methods.csv`, `fields.csv`); a token-replacing script is enough. 1.12 uses `stable_39`.
  - On the target side, read the mapped game jar from the loader's cache with `javap`. It shows names,
    lambda names and local-variable slots for mixins. Loom's `genSources` gives readable source.
- **Extract the original assets** (textures, models, lang, sounds) next to the decompile, so asset audits
  can hash against them.
- **Keep it private.** The decompile never ships, and is never committed to a public repo (hard rule).
  - Do keep it reachable by every future session: a separate private repository, or a fixed folder outside
    the port's repository.
  - Keep it out of the port's own history. A repository made public later publishes its whole history.
  - The Thaumcraft port kept `reference/` in its private repository, so every fresh cloud session could
    read the original before changing anything.

## 2. Inventory and adaptation matrix
- **List every subsystem of the original:** registries, event handlers, packets, GUIs and screens,
  renderers, world generation, loot, config, commands, public API, compat hooks.
- **Write the matrix:** for each area, the original classes, the port classes, and a verdict (keep / adapt /
  replace / remove / missing). Port code that came from another base gets the same treatment.
- **Order the milestones by dependency:**
  1. data foundations: ids, the item and block registry, the mod's core data (aspects, research);
  2. core mechanics;
  3. devices, crafting, world generation and mobs;
  4. rendering and FX;
  5. compat.
  Keep a status document from day one (section 7).

## 3. Extract data; don't retype it
- **Registration code is data in disguise** (`ConfigItems`, `ConfigResearch`, recipe classes):
  - Parse the decompiled call chains with a small tokenizer script, and write JSON into the port's
    resources.
  - Note the source line numbers in the script.
  - Re-run the script instead of hand-editing its output.
  - In the Thaumcraft port this produced the 48 aspects, 457 object-aspect registrations, the research tree
    with its pages and warp, and every recipe.
- **Legacy ids.** Old items are often `(item, metadata)` pairs, and newer engines have no metadata.
  - Give each pair one flattened id.
  - Have each ported item register the legacy reference it replaces.
  - Resolve references in data files through that map.
  - Fail at startup when a catalogue entry is left unregistered.
  - For the base game's own renamed ids, use the target's data fixer.
- **Count everything:** a test that every original item and metadata variant exists catches silent gaps
  (225 items + 119 block items in the Thaumcraft port).
- **Keep the original order.** Lookups in old mods are often first-match: the first matching recipe wins, and
  the first matching category. Values can also accumulate (an aspect added twice in one registration). An
  extractor that sorts entries or overwrites map keys changes behaviour.
- **Track what can't be resolved yet.** Count the unresolved references after each pass (101 → 47 → 24 in
  the Thaumcraft port as content arrived), so nothing waits silently.
- **Check that the original ever calls the code before porting it.** Find its call sites and send sites in
  the decompile, and record the dead code so later audits don't count it as missing. Thaumcraft 4 shipped
  7 FX classes that were never called and 3 packets that were never sent.

## 4. Port unit by unit
Each unit (a block, a device, a mob, a mechanic) follows the same steps:
1. Read the original classes.
2. Port them.
3. Mark kept quirks.
4. Write a test.
5. Run it.
6. Log the unit in the status document.
7. Commit.

- **Keep observable quirks and bugs,** with a comment that names the original class or line, so the next
  agent does not "fix" them. Examples from the Thaumcraft port:
  - holding a key stops every block's right-click, because the original's key answered "handled" for every
    block;
  - bosses roll champion modifiers with the option off;
  - an ingredient with a container item adds no aspects.

  Don't reproduce crashes or client desync glitches, though. List each such case.
- **Document every forced deviation** (an engine limit, a removed API) with its reason, in the status
  document's "known deviations" list.
- **Use two labels in the log:**
  - "quirk kept": an original bug, preserved on purpose;
  - "deviation": something the new engine cannot or should not reproduce, always with the reason.
  A later reader can then tell a kept bug from a port bug.
- **The original inherited code from the old engine.** A subclass of a vanilla mob, a vanilla tree
  generator, the old movement code: the new engine's versions differ. Port the old engine's parts too, and
  switch off what the new superclass adds (in Minecraft, a 1.20 zombie subclass gains drowned conversion).
- **Mark recalled platform behaviour.** The mod's decompile does not contain the old engine or loader
  (Forge, vanilla 1.7.10). Mark anything taken from memory of them UNVERIFIED, or decompile them too.
- **Use stand-ins for content that doesn't exist yet.** Give each missing dependency a named hook or tag,
  list it as pending, and wire it when its unit lands.
- **Keep the server authoritative.** Re-validate client requests the original trusted. Still port the
  original's client-side pre-checks and messages.
- **Fidelity against playability is the user's call.** A site check that almost never passes on new
  terrain, a fallback the new ecosystem makes redundant, art beyond the original: log each as an open user
  decision. Don't settle it silently.
- **Map engine concepts deliberately.** Event order, ticking, metadata, rendering and world generation all
  changed between versions. The Minecraft table is in `references/minecraft-1-7-10-forge-to-1-20-fabric.md`;
  write one for your engine as you go.
- **Never port from memory.** When the wiki and the decompile disagree, the decompile wins.

## 5. Oracles, from cheap to real
The general method is in `knowledge/techniques/oracles-how-agents-know-a-mod-works.md`. For a port, from
cheap to real:
1. **Headless tests on the real server** (Minecraft GameTests: `runGametest`) for logic. Parse the JUnit
   XML; don't trust the console. Setup and traps:
   `knowledge/techniques/fabric-1-20-1-gametests-as-the-oracle-of-a-large-mod-port.md`.
   - **Write tests that can fail.** Pick inputs where the wrong behaviour gives a different answer, and read
     the original's values before writing the assertion.
   - Each test cleans up the global state around its own position (shared state leaks between tests).
2. **A scripted real client** for the click path, screens, rendering, natural world generation and a second
   player: `knowledge/techniques/a-scenario-harness-in-a-minecraft-fabric-dev-client-real-cli.md`.
   - Server tests call the item code directly. They can't see that the port dropped the original's
     client-side pre-check and its message.
3. **The release jar on a real server, and the real modpack's jars.** Remapping, jar-in-jar and dependency
   clashes only show up there.
4. **A human playthrough** for what nothing above covers. Ask for it; don't claim it.

Report evidence levels honestly, per system:
- implemented;
- tested;
- seen in a real client;
- unverified.

Never write "passes" for a run that did not happen. If a host or tool is unreachable, say what was not run.

## 6. Audit against the original, by layer
Feature-by-feature work leaves systematic drift that no single test sees.
- **Audit one layer at a time** once features exist:
  - event handlers, packets, items, blocks, entities, GUIs;
  - world generation, loot, research and recipes, config;
  - renderers, split into tile, block, entity and item.
- **Run each audit as a read-only review.** It compares every original class in the layer with its port
  line by line and returns ranked findings with file and line.
  - Several reviewers in parallel, one per group, cover a layer in one pass.
  - Fix the queue, then re-run the matching visual scenario.
  - The Thaumcraft renderer audit found about 60 differences, after every gameplay test was already green.
- **Run a leftover audit** after any change of base or source version: grep for the old version's name,
  and hash every texture and model against the original jar.
- **Look for checks the original ran on the client:** refusals with a chat message, tooltips, a cancelled
  swing. Ports often keep only the server re-check, which refuses silently.

## 7. Keep the port resumable
A big port outlives any one session's context. Make the repo carry the state, and **build before trusting
it**. A session left half-converted code in the Thaumcraft port: calls to methods of the old base, old enum
values. Build at the start of every session, and re-port broken calls from the reference instead of
stubbing them.
- **Status document** (`docs/MIGRATION_STATUS.md`):
  - the original's license, and the author's permission if one was needed;
  - the fixed versions and the adaptation matrix;
  - a per-unit log: what was ported, the original classes, kept quirks, deviations, tests;
  - known bugs and deviations;
  - known unverified areas;
  - the exact next task;
  - a completion estimate by evidence level, not by commit count.
- **A short handoff document** (`docs/HANDOFF.md`): where things are, the non-negotiable decisions, the
  commands, the latest real test result, and the open questions for the user.
- **Agent instructions** (`AGENTS.md`) with the source-of-truth and verification rules.
- **One commit per unit,** pushed every session (to a private remote unless the port may be published).
  Ephemeral cloud containers lose anything not pushed.
- **Build prerequisites written down.** A cloud environment needs the loader's Maven and the game vendor's
  download hosts allowed. For Minecraft that is `maven.fabricmc.net`, `piston-meta.mojang.com`,
  `piston-data.mojang.com`, `libraries.minecraft.net` and `resources.download.minecraft.net`, plus each
  dependency's Maven. Without them, the first Gradle build can't run.
- **Field notes as you go** (`docs/field-notes/`): one fact per note, with its evidence. They become the
  knowledge-base notes at the end.

## 8. Share
- Write one game note per port (`um kb new`): versions, route, the original's license and whether the port
  is public, gotchas.
- Write technique notes for methods that apply to other mods: render-state mapping, test harnesses,
  data extraction.
- See the share-field-notes skill. Ask the human before any PR.

## Hard rules (on top of mod-any-game's)
- The decompiled reference and the original's assets never ship unless the original's license allows it.
- A port of someone else's mod is published only if its license allows it or its author (or the current
  rights holder) has given permission. Otherwise it stays private. Credit the original author either way.
- Don't import mechanics from a different version of the mod because they are easier to implement.
- Don't claim a test, build or visual check that did not run.
