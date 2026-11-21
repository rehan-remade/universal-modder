---
kind: game
title: "Publishing a Blueprinter aircraft addon plus BepInEx plugin for NOMM via NOMNOM: release layout, manifest rules and the EULA"
game: "Nuclear Option"
game_version: "Early Access 0.34.6 (Steam app 2168680, public build 26327221); Blueprinter 2.1.1; BepInEx 5.4.23.5"
platform: windows
engine: unity-mono
route: loader-api
tools: ["Blueprinter 2.1.1", "BepInEx 5.4.23.5", "HarmonyX", ".NET SDK 8.0.318 (-deterministic)", "UnityPy (pack audit)", "gh CLI", "NOMNOM at ee196e9", "NOMM (NuclearOptionModManager) at 8786356"]
anti_cheat: "none found; the addon is client+host (everyone in a lobby needs it), nothing gives a multiplayer advantage"
status: released
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-11-22
links:
  - "https://github.com/riseofthewolfremake-lgtm/HeritagePairs-NuclearOption"
  - "https://github.com/KopterBuzz/NOMNOM"
  - "https://github.com/KopterBuzz/NOMNOM/blob/main/Docs/SCHEMA.md"
  - "https://github.com/Combat787/NuclearOptionModManager"
  - "https://github.com/nikkorap/NOBlueprinter-Releases"
  - "https://store.steampowered.com/eula/2168680_eula_0"
tags: ["publishing", "nomnom", "nomm", "blueprinter", "github-releases", "manifest", "eula", "asset-audit", "ship-gate"]
---

# Publishing a Blueprinter aircraft addon plus BepInEx plugin for NOMM via NOMNOM

The "Heritage Pairs" addon (six new aircraft in one Blueprinter `.nobp`, plus a small BepInEx plugin DLL) was
published as a public GitHub repo with GitHub Releases and listed in NOMNOM, the manifest catalogue that the NOMM mod
manager reads. Releases 1.9.10 to 1.9.14 went out this way (2026-11-14 to 2026-11-18); the first one needed a pull
request to NOMNOM, which was merged, and every later release was picked up by NOMNOM's updater with no further PR.
This note covers what NOMM does with your zip, what NOMNOM wants, how the pack was audited for game assets, and the
EULA points. The model-building side is in
[new-aircraft-with-blueprinter-nobp-b25h-ga25x-nimrod.md](new-aircraft-with-blueprinter-nobp-b25h-ga25x-nimrod.md).

## Setup
- **Game:** Nuclear Option 0.34.6 (Steam, Windows 11), Unity 2022.3.62f2 Mono. Loader BepInEx 5.4.23.5,
  Blueprinter 2.1.1 (`com.nikkorap.blueprinter`).
- **Sources read (local clones, cited as read on 2026-11-13):** NOMNOM at `ee196e9` (README "Mod Submission
  Acceptance Policy", `Docs/SCHEMA.md`, `ValidationSchema.json`, `Validate-JsonContent.ps1`,
  `Validate-JsonSchema.ps1`, 284 existing manifests); NOMM at `8786356` (`Installer.kt`, `LocalMods.kt`,
  `RepoMods.kt`); Blueprinter runtime source (`BundleRegistry.cs`, `Plugin.cs`, `Patches/VersionGetter.cs`);
  the game EULA page, Section 5, updated 2026-09-19.
- **Our public repo:** [HeritagePairs-NuclearOption](https://github.com/riseofthewolfremake-lgtm/HeritagePairs-NuclearOption)
  (MIT for code, CC0 for our own art). Worth reading there: `docs/publishing/HOW_TO_RELEASE.md` (the full
  release checklist), `docs/publishing/HeritagePairs.json` (our NOMNOM manifest), `RELEASE_NOTES_*.md` (release
  description pattern), `docs/publishing/pack_asset_report_1.9.14.txt`, and `tools/make_release_zip.py`,
  `tools/pack_asset_report.py`, `tools/nomnom_schema_check.py`, `tools/make_public_tree.py`. The compliance
  write-up itself stayed private; its content is summarised here.
- **Install layout NOMM produces** (and the one to use by hand):
  `<GameDir>/BepInEx/plugins/com.nikkorap.blueprinter/addons/<id>/` holding the `.nobp`, the DLL and NOMM's own
  `meta.json`.

## Route and why
- **GitHub Releases + NOMNOM manifest** is the only route into NOMM's list: NOMM shows what NOMNOM's catalogue
  lists, and NOMNOM only accepts mods released as GitHub Releases, one mod per repo.
- **Plugin DLL inside the addon zip** rather than as a separate NOMM mod: the plugin only touches our own aircraft,
  so it ships with the pack and a single manifest entry of type `addon` that `extends` Blueprinter.
- **Public repo built from a staging tree with fresh history** instead of making the private repo public: the
  private history held GBs of renders, decompile-derived study docs and developer test tools (spawn/damage
  commands). A script (`make_public_tree.py`) copies an allow-list into an empty folder and blocks on known-bad
  paths; that folder is committed and pushed as the public `main`.

## How the game works (what we had to learn)
**NOMM install (NuclearOptionModManager, `Installer.kt` / `LocalMods.kt`):**
- Downloads the asset named in the manifest, checks its sha256 against the manifest `hash` (`sha256:<hex>`), and
  refuses a mismatch.
- Extracts the archive **as it is** (no folder flattening) into `BepInEx/disabledPlugins/<id>/`, then writes its own
  `meta.json` there.
- On enable, an artifact of type `addon` that `extends` `com.nikkorap.blueprinter` is moved to
  `BepInEx/plugins/com.nikkorap.blueprinter/addons/<id>/`. Disabling moves it back to `disabledPlugins`.
- Consequence: the zip holds exactly the `.nobp` and the DLL **at its root**: no wrapper folder, no `meta.json`,
  no readme or licence file.
- NOMM uses `disabledPlugins` as its "off" switch. A plugin found there was put there by NOMM (or the user through
  NOMM); never "fix" it by moving it back.

**Blueprinter loading (`BundleRegistry`):**
- Finds packs by a recursive `*.nobp` search under `BepInEx/plugins`, so the folder name does not matter to it, and
  BepInEx loads DLLs from any sub-folder.
- Groups packs by mod and keeps the highest `modVersion`; on a tie it logs "Skipping duplicate" and loads **none**.
  Keep one copy.
- `CheckOutdatedMods` compares only major.minor of the pack's internal `gameVersion` with the running game.
- Blueprinter postfixes the `Application.version` getter (`VersionGetterPatch`) and appends its own version and a
  signature of every loaded bundle (name + version), hashed when over 100 characters. The game filters and checks
  Steam lobbies by `Application.version` (`SteamLobby`, `DedicatedServerManager`), so host and clients must have
  the same set of addon versions to see each other. Declare `isClientOrServer: "Both"`.

**NOMNOM (catalogue + hourly updater):**
- First listing: a PR adding `modManifests/<id>.json`. `id` must equal the file name. Fields that mattered:
  `isAiAssisted` (required since `ee196e9`), `isClientOrServer`, `githubOwner` / `githubRepoName`,
  `autoUpdateArtifacts`, and per artifact `fileName`, `version`, `category`, `type: addon`, `gameVersion`,
  `downloadUrl`, `hash`, and `extends: {id: com.nikkorap.blueprinter, version: 2.1.1}`.
- The release must exist before the PR: URL and hash in the manifest are real.
- After the merge, the updater (`Get-GitHubReleases.ps1`, `Get-ModReleaseArtifact.ps1`) adds any release with a
  higher version on its own, copying file name, URL and hash from GitHub and gameVersion / type / extends from
  the newest entry it already has. A changed game version goes through NOMNOM's issue template; a changed
  Blueprinter version needs a manifest PR.
- It takes `Assets[0]` of the release, so the zip must be the **only** asset.
- A GitHub pre-release lands in category `preRelease`; a draft is skipped.
- The tag is parsed as a version after stripping `v` (and `-pre`, `_IL2CPP`): use `v` + plain numbers.
- Entries are only ever added. Deleting a GitHub release breaks the download but leaves the entry; withdraw a
  version by publishing a higher one or by a PR that removes the entry.
- 2026-11-22: a newer NOMNOM clone (automated commit of 2026-11-13, after `ee196e9`) has optional
  `releaseAssetName` and `releaseTagPrefix` manifest fields that pick a named asset / strip a custom prefix. We did
  not use them; with neither set, `Assets[0]` still applies.

**NOMNOM acceptance rules, and how we met them:**
- Custom DLL source-available, not obfuscated, and the released DLL must match the source: the plugin is built with
  `-deterministic` from the tagged commit, and the README records the DLL sha256 with the compiler, BepInEx and
  game versions. `[BepInPlugin]` version = pack version = manifest version (`X.Y.Z`), and `AssemblyVersion` is the same as `X.Y.Z.0`.
- No malicious or unwarranted changes: no file, registry, network or process calls; the plugin writes only its own
  BepInEx config. Every Harmony patch returns at once unless the aircraft is ours (checked by
  `definition.jsonKey`).
- AI assistance declared (`isAiAssisted: "True"`, README section, CREDITS listing the generation endpoints).
- Credit third-party work and its licence (Blueprinter MIT, BepInEx, Harmony, tools) in CREDITS.md.
- No ripped assets (see the pack audit below); no unfair multiplayer advantage.

**Pack audit (`pack_asset_report.py`, UnityPy over the built `.nobp`):**
- Lists every Mesh, Texture2D, Sprite, Material, AudioClip, Shader, MonoScript, TextAsset with type, name, size and
  origin: `ours:<aircraft>` (under the pack's own folders), Blueprinter `*_PLACEHOLDER` stubs, script-name refs,
  Unity's own URP shaders, or `UNKNOWN` (must be 0).
- Stock parts must be **placeholder references that point out of the pack** (non-zero file id); 1.9.10 had 26 mesh
  filters, 116 audio sources and 146 renderer materials pointing out, 0 audio clips, 3 Unity shaders, and 0 of
  1,471 meshes / 465 textures matching a game mesh or texture by name or content (checked against our own private
  AssetRipper export, which never ships).
- The limit: the report does not see inside components. Our generators clone stock component settings with
  `EditorUtility.CopySerialized`, and 105 of 107 particle systems were byte-identical to stock ones (about 0.77 MB,
  0.3 % of the pack); audio-source and material parameter blocks are largely stock values. This is said openly in
  CREDITS, README, LICENSE-ASSETS and the report, and left as a judgement point for the owner.

**EULA, Section 5 (Shockfront, store EULA page 2168680, updated 2026-09-19), paraphrased:**
- Mods are allowed if free, non-standalone, without distributed base game assets, decompiled code or original
  DLLs, and without an unfair multiplayer advantage or third-party infringement. Donations are fine, paywalls are
  not.
- A mod using game assets, code or trademarks must "prominently display" a fixed unofficial-mod notice. We copy it
  word for word under the README title and into every release description (the zip itself can't hold it: NOMM
  needs the two-file layout).
- Section 1 forbids reverse engineering except as law or Section 5 allows; Section 5 does not explicitly authorise
  decompiling or code plugins. Decompiling for private study and shipping a Harmony plugin is how the catalogue's
  plugin mods are made, but whether that is "authorised" is a reading. We wrote this down as a judgement call for
  the repo owner, who decided to publish.

**Ship gate for unreleased aircraft:** an aircraft still in development stays out of every release by three
independent checks: the Unity build (`FamilyBuild.Pack`) refuses its assets and deletes a pack listing it unless a
dev switch is set (which writes to a separate dev output folder); `make_public_tree.py` excludes its paths; and
`pack_asset_report.py` exits non-zero when any of its assets are in the pack.

## Build steps
1. Set the version in three places: the pack version in the Unity build script, the `[BepInPlugin]` version, and
   `AssemblyVersion` / `AssemblyFileVersion` (`X.Y.Z.0`) / `AssemblyInformationalVersion`. Keep the plugin GUID
   fixed (players' config file is named after it).
2. Build the DLL deterministically, build the pack in Unity batch mode, run the tests, try it in game.
3. Freeze `.nobp` + DLL in a folder that never changes; make the zip deterministically (fixed entry order and
   timestamps, both files at the root) and record its sha256.
4. Run the pack audit and keep the report; check the ship-gate line is 0.
5. Regenerate the public tree into an empty folder, sync it into the staging clone, commit, push `main`.
6. `gh release create vX.Y.Z <zip> --target main --title ... --notes-file ...` with the zip as the **only** asset;
   the notes carry what changed, requirements, the zip sha256, known issues, the EULA notice and the AI
   declaration. Not draft, not pre-release (unless you want `preRelease`).
7. Compare GitHub's asset digest with your sha256.
8. First release only: fork NOMNOM, add `modManifests/<id>.json`, run `Validate-JsonContent.ps1`, open the PR.
   Later releases: nothing; the hourly updater adds them.

## Verification
- **Oracles used:**
  - NOMNOM's own `Validate-JsonContent.ps1` on the manifest in Windows PowerShell: every check true, id unique
    among the 284 mods, `com.nikkorap.blueprinter` known.
  - `Validate-JsonSchema.ps1` needs PowerShell 7 (`Test-Json -Schema`), not installed; a small draft-07 stand-in
    validator was used and proved by rejecting a deliberately broken copy of the manifest.
  - GitHub's asset digest equal to our local sha256 for every release (1.9.10 to 1.9.14).
  - The NOMNOM PR's own workflow passed and the PR was merged; later releases appeared in the catalogue without
    a PR.
  - Blueprinter log after install through the NOMM layout: one "[BundleRegistry] Loaded ..." line for the pack,
    one plugin "Loading [...]" line, no duplicate-mod line, 0 errors.
  - Pack audit exit code 0 on release packs, 1 on a dev pack (ship gate).
- **Not verified:** how NOMM handles a `preRelease` entry (we never published one); multiplayer between modded
  players (single player only); whether the EULA reading on decompiling / code plugins / cloned component
  settings holds (owner's call, not tested with Shockfront).

## Gotchas
1. **A second file on a release can become "the mod".** **Cause:** NOMNOM's updater takes `Assets[0]`; a `.sha256`
   file or screenshot uploaded with the zip may be first. **Fix:** upload the zip only; put the sha256 as text in
   the release notes. (A risk we designed around, not one we hit.)
2. **NOMM refuses an install or shows the wrong version.** **Cause:** a replaced release zip (NOMNOM recorded the
   old hash) or a stale `meta.json` from a manual install. **Fix:** never replace a published zip, ship a new
   version; when installing by hand, use the `meta.json` the build writes (version + `sha256:<hash>` current), or
   let NOMM write its own.
3. **The `.nobp`'s internal manifest says gameVersion 0.34.3 while the game is 0.34.6.** **Cause:** Blueprinter's
   editor writes the version its project's game assemblies were imported from. **Fix:** nothing needed:
   `CheckOutdatedMods` compares major.minor only, so no warning. The NOMNOM manifest carries the real 0.34.6.
4. **Modded and unmodded players don't see each other's lobbies, or two modded players with different addon
   versions don't.** **Cause:** Blueprinter appends the loaded bundle list to `Application.version`, which the
   game uses to filter Steam lobbies and compare with the host. **Fix:** declare `isClientOrServer: "Both"` and
   tell players everyone needs the same version.
5. **Logo-like marks in AI-generated placard art.** **Cause:** the image model drew company-logo-like emblems on
   instrument placards. **Fix:** painted out before the first public release (a script edits just those
   texture regions); review generated art for marks before publishing.
6. **`gh release create --target <sha>` was rejected.** **Cause:** gh/GitHub would not take the commit sha as the
   target in our run. **Fix:** push first and use `--target main`.
7. **"Skipping duplicate" in the Blueprinter log and the aircraft are missing.** **Cause:** two copies of the same
   pack version anywhere under `BepInEx/plugins` (e.g. a manual copy plus NOMM's). **Fix:** keep exactly one;
   a lower version next to a higher one is ignored but still clutters.

## Assets
None made for publishing. The pack audit reads names, sizes and counts only (no pixels or vertices), and the game
export it compares against stays private on the build PC.

## Cost and time
The first release took one long session for the compliance audit (NOMNOM rules, NOMM code, EULA, asset report,
public tree) plus the PR; each later release is a build, a zip, a push and one `gh release create`.

## Open questions
- Would removing the cloned stock particle-system settings (rebuilding them at run time from the game's own
  emitters, or authoring our own) be expected by Shockfront or NOMNOM? Not done.
- How NOMM presents a `preRelease` artifact next to a `release` one.
- When the game moves to 0.35 (expected newer Unity), the gameVersion change has to go through NOMNOM's issue
  template, and Blueprinter's `extends` version may change too.
