---
kind: game
title: "Running a 500+ mod load order by hand: modsettings.lsx rules, recovering a wiped order from a save, mod.io re-subscribes, game-folder files and conflict diagnosis"
game: "Baldur's Gate 3"
games_also: []
game_version: "Patch 8 / Patch 8 hotfix (Jun-Sep 2026), Steam, Windows; Script Extender v32; ~530 paks"
platform: windows
engine: unknown
route: other
tools: ["LSLib Divine 1.20.4", "Python (XML edits, save meta reader, backup/restore)", "Script Extender", "Native Mod Loader (bink2w64 proxy)"]
anti_cheat: "none; single-player"
status: working
agents: ["Claude Code (Fable 5)", "Claude Code (Opus 4.8)", "Claude Code (Opus 5)", "Claude Code (Opus 5.5)"]
humans: [RedSuper]
date: 2026-10-04
links: []
tags: [load-order, modsettings, meta-lsx, mod-io, saves, native-mod-loader, steam-verify, loose-files, kavt, photo-mode, animation-sets, ui-mods, troubleshooting]
---

# Running a 500+ mod load order by hand: modsettings.lsx rules, recovering a wiped order from a save, mod.io re-subscribes, game-folder files and conflict diagnosis

> How a ~530-mod Baldur's Gate 3 install was kept working without a mod manager: what `modsettings.lsx` and
> `meta.lsx` must look like, how the game identifies a module, how to rebuild a lost load order from a save,
> why the in-game manager and mod.io kept undoing changes, which files a modded game folder holds, and how
> two conflicts (photo mode poses gone, instruments interrupted) were traced to one mod each. Everything
> below happened on one machine; the Verification section says which fixes the human confirmed in game.

## Setup
- BG3 on Steam, Windows 10. No mod manager in the end: BG3 Mod Manager 1.0.11.1 did not see some mods and
  dropped them (newer releases reportedly handle mod.io paks; not tried), and the in-game mod
  manager cannot reorder. Load order edited directly in
  `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\PlayerProfiles\Public\modsettings.lsx`.
- Paks in `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Mods\`; saves next to them. The game folder holds
  Script Extender (`bin/DWrite.dll`), Native Mod Loader and loose-file mods (list below).

## Route and why
`other`: configuration and file management with scripts, not a mod. Every edit to `modsettings.lsx` goes
through an XML parser with a backup, anchors the new entry next to an existing one, and is verified by path.

## How the game works (what we had to learn)
- **`modsettings.lsx`**: one `ModuleShortDesc` per module under **`/root/Mods`**, in load order, with `Folder`,
  `MD5`, `Name`, `PublishHandle`, `UUID`, `Version64`. An entry anywhere else (e.g. directly under the root) is
  silently ignored. The MD5 field is not validated (stale MD5s load fine); it is bookkeeping.
- **A module is identified by UUID and Folder.** The game finds a module's files by `Folder`; if a mod update
  renames its folder (same UUID), the old entry no longer matches and the mod quietly stops loading.
- **Declared dependencies must load first.** A library loaded after the mod that needs it (MCM after its
  VolitionCabinet library; Goon's Library after `MusicPerformWorkaround`) misbehaves without an error.
- **`meta.lsx` of a self-made pak is validated.** In `ModuleInfo`: `UUID` is `FixedString` (`guid` only in
  `ModuleShortDesc`), `Author`/`Description`/`Folder`/`Tags` are `LSWString`, `GMTemplate` must exist. A wrong
  type or a badly filled `Dependencies` block makes the game reject the module and reset the whole order to a
  single `GustavX` entry on launch. An empty `<node id="Dependencies" />` is safe and does not affect order.
- **`Version64`** packs `major<<55 | minor<<47 | revision<<31 | build`; `1.0.0.0` = `36028797018963968`. Bump it
  on every rebuild of your own pak (it is how the game notices the change); never change UUIDs. An entry with a
  non-numeric `Version64` shows as `255.255.65535.2147483647` and flags on every load.
- **Saves record their module list** in the save's `meta.lsf` (Name, UUID, Folder, Version64, MD5, in order).
  A save whose recorded module is missing refuses to load; putting the pak back fixes it. The "Mod
  Verification" dialog lists modules whose version or MD5 changed since the save, and new ones.
- **That list is a recovery source.** The newest save holds the order the game last validated, including
  dependency corrections the game made itself; rebuilding `modsettings.lsx` from it fixed a broken dependency
  order that our own file backups had preserved.
- **The in-game mod manager only lists mod.io mods**, never manually installed paks, so "not listed there" says
  nothing about loading. mod.io subscriptions live on the account (local state in
  `%PUBLIC%\mod.io\<game id>\state.json`); unsubscribing in game did not always stick, and subscribed
  mods are downloaded and re-enabled on launch.
- **Loose files in `<game>/Data/` override paks** and survive disabling or uninstalling mods. Native mods load
  through Native Mod Loader, a `bink2w64.dll` proxy (the real one renamed `bink2w64_original.dll`).
- **UI mods conflict by root widget name**, not path: two mods that both declare `x:Name="CharacterCreation"`
  conflict (last loaded wins); a mod declaring `CharacterCreation_Equipment` does not.

## Build steps
**Installing or updating a mod**
1. Read its `meta.lsx` with an XML parser (`ModuleInfo` for identity; `Dependencies` is a sibling node).
2. Same UUID as an installed mod = an update even if the name changed: replace the pak (quarantine the old one),
   update `Folder`, `Name`, `Version64`, `MD5` in place, keep the position.
3. New mod: insert after an anchor entry of the right group; parse the result; assert the new node's path is
   `/root/Mods/ModuleShortDesc`, no duplicate UUIDs, every declared dependency earlier in the list.
4. Order we settled on: frameworks and libraries first (VolitionCabinet before MCM), appearance, the clothing
   block contiguous, content and class mods, gameplay overhauls (they should win shared entries; measure the
   overlap by intersecting stats entry names before deciding), patches after their targets, KAVT near the
   bottom, Compatibility Framework below class mods, a wardrobe generator after all clothing.

**Rebuilding a wiped or broken load order from a save**
1. Convert the newest good save's `meta.lsf` (inside the `.lsv`) and read its module list.
2. Write `modsettings.lsx` from it (same attribute set and types as above), keeping `GustavX` first.
3. Compare with the previous file: same module set, and look at where the orders differ. Keep the old files.

**Moving the game to another drive**
Steam → Properties → Installed Files → *Move install folder* moves modded files too. If reinstalling instead,
back up what a clean install lacks: `bin/DWrite.dll` + `ScriptExtenderSettings.json`; `bin/bink2w64.dll`
(proxy, tiny, an old file date) + `bink2w64_original.dll`; `bin/NativeMods/*.dll` + `*.toml`; loose
`Data/Generated/**`, `Data/Public/**` (including a loose `Shared/EquipmentTypes/EquipmentTypes.lsx` from a
hip-sheath mod) and `Data/SEMergedTileSet.gts`. Also hash every file in the old folder so a restore can list
anything missed while the old copy still exists.

## Verification
- Each install batch: the game started with all modules active; saves loaded; the human checked new items.
- The save-based rebuild became the working order for every later install batch.
- Instruments: confirmed fixed by the human after the fixer mod went in.
- Photo mode: a sweep of all paks showed exactly one mod defining the body animation-set resource; removing it
  was the fix applied, but the return of the poses was not reported back.
- Not verified: why the load order was sometimes reset with no change on our side (see Gotchas 2, 3).

## Gotchas
1. **Whole load order reset to one entry on launch, every time.** **Cause:** a self-made pak's `meta.lsx`
   (types, or a hand-filled `Dependencies` block with display names as folders, empty MD5s, guessed versions).
   **Fix:** copy a working mod's `meta.lsx`, leave `Dependencies` empty.
2. **Load order reset intermittently**, typically the first launch after a reboot. Ruled out: Steam Cloud (a
   stale cloud copy existed, but cloud sync was off), subfolders or non-pak files in `Mods/`, a duplicate pak
   (that would fail every launch). Not found. What helped: a backup plus a restore script, and later the
   save-based rebuild.
3. **Read-only `modsettings.lsx` is a trade-off, not a fix.** It stopped wipes, but it also stops the game's own
   legitimate writes: accepting Mod Verification never persisted, so a renamed mod showed as "new" on every
   load. Community reports also mention launch errors with it. A plain `copy` onto a read-only file fails
   silently. We ended unlocked, with backups and the save-based rebuild.
4. **A removed mod came back after every launch.** **Cause:** a mod.io subscription; deleting the pak or its
   entry cannot win. **Fix:** remove it on the mod.io side (and any collection holding it); the human's in-game
   unsubscribe did not always propagate.
5. **Photo mode pose list empty.** **Cause:** a hip-sheathing mod shipped full copies of the base body
   `AnimationSetBank` resources for every race under the vanilla resource UUIDs, frozen before Patch 8, so the
   18 newer entries (including the photo-mode poses) were missing. Overriding a resource replaces it whole.
   **Fix:** remove that mod. Find such overrides by searching every pak's Content banks for a vanilla resource
   UUID being *defined* (`<node id="Resource">` with that `ID`), not merely referenced.
6. **Playing an instrument stopped at once.** **Cause:** Goon's Library adds a hidden passive that applies a
   status on every spell cast; performing is a spell, and any status landing on a performer ends the
   performance. **Fix:** "Interrupted Music Performance Fixer" (Nexus 19451), loaded late; confirmed working.
7. **Steam "Verify integrity" removed the Native Mod Loader** (restored Larian's `bink2w64.dll`); WASD movement
   and camera tweaks silently stopped. **Fix:** back up `bin/` before verifying; reinstall the loader.
8. **A mod got flagged "new" on every save load.** **Cause:** its update renamed the module folder
   (`Goon's_Library` → `Goon's Library`) and only UUID/version/MD5 were updated in our file. **Fix:** compare
   Folder on every update.
9. **Removing a mod mid-playthrough blocks the save** until the pak is back. Check the save's module list
   before removing anything; test removals on a throwaway character.
10. **"Two UI mods replace the same page" was a false alarm** for different widget names; check the
    `x:Name` on the root element, not the file path.
11. **One body-tattoo choice wiped the selector's 19 designs.** Every loose body-tattoo mod writes the same
    atlas file over the tattoo-selector pak. The atlas is a 4x5 grid (20 slots, the grid is in the compiled
    shader); we merged chosen designs into free slots by copying compressed BC blocks so kept tiles stay
    byte-identical. Each tile also has R/G/B/A channels with separate colour parameters (vanilla packs 25
    tattoos into 20 tiles this way); the ecosystem uses only R. KAVT glowmaps ship as a library and only the
    file renamed to exactly `KVT_Body_Glowmap.DDS` is active.
12. **KAVT belongs near the bottom of the load order**, not the top: it, race mods and head mods write the same
    CharacterVisuals entries and the last one wins (its manual's own example has it at 197 of 204).
13. **Script Extender logging left on** wrote gigabytes of Osiris trace per session and made every action lag;
    turn `EnableLogging` off when done.
14. **Small install traps:** some older mods' `meta.lsx` has only a 32-bit `Version` (268435456 = 1.0.0.0) and no
    `Version64`; write the matching `36028797018963968` rather than inventing one or writing a null. Search
    `modsettings.lsx` by `Folder`, not `Name` (Mod Configuration Menu is `Folder=BG3MCM`, so a search for "MCM"
    by name finds nothing). Native mods keep user settings in a `.toml` next to the DLL; diff an update's `.toml`
    before overwriting (ours was a strict superset).
15. **Reading mod pages from scripts:** Nexus mod pages, bug and posts tabs return HTTP 403 to non-browser
    fetches. Wayback Machine snapshots of the page gave the real requirements list; the public GraphQL endpoint
    (`api.nexusmods.com/v2/graphql`) returns full descriptions; bug reports are only reachable logged in.
16. **Compressing the Mods folder for upload gains almost nothing**: paks are already LZ4-compressed. Use a fast
    or store level, split volumes, and a recovery record if the archiver has one.

## Open questions
- The cause of the intermittent load-order resets.
- A ~5 handles/second handle leak in `bg3_dx11.exe` during Act 2 (48,000+ handles), which made actions slow
  after an hour or two; handle type not identified.
