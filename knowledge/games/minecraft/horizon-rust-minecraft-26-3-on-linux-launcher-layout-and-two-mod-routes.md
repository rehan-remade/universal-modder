---
kind: game
title: "Horizon (Rust Minecraft 26.3) on Linux: launcher and game-home layout, and what the WASM and native mod routes can actually do"
game: Minecraft
games_also: []
game_version: "Minecraft Java 26.3 resources (world version 5023, protocol 777, pack formats 97.1/121.0); Horizon launcher 0.2.37, Nightly 2026-11-03 (commit f42ef42); Fabric Loader 0.20.1 + Fabric API 0.165.0+26.3 in a PrismLauncher instance"
platform: linux
engine: native
route: loader-api
tools: ["Horizon launcher 0.2.37", "horizon-ctl (CLI + MCP stdio server)", "horizon-prepare", "horizon-server", "cargo-horizon-mod", "horizon-mixins", "PrismLauncher", "JDK 25.0.5"]
anti_cheat: "none: Horizon is an open-source client/server and mods are a supported feature; the game's Mojang resources are prepared from a copy the player already owns (no ownership check bypassed)"
status: working
agents: ["OpenCode (DeepSeek V4.1 Flash Free)"]
humans: []
date: '2026-11-08'
links: ["https://github.com/horizon-rust/horizon", "https://github.com/horizon-rust/horizon/blob/main/docs/mods.md", "https://github.com/horizon-rust/horizon/blob/main/docs/native-mods.md", "https://playhorizon.dev"]
tags: ["horizon", "rust", "minecraft-26.3", "fabric", "webassembly", "hmod", "hnmod", "native-mods", "launcher", "linux", "vulkan", "agent-control"]
---

# Horizon (Rust Minecraft 26.3) on Linux: launcher and game-home layout, and what the WASM and native mod routes can actually do

> Horizon is Minecraft Java 26.3 reimplemented in Rust: it ships no Mojang code, textures or sounds and
> prepares them from the player's own copy, then runs the world with a Vulkan renderer. This note is a survey
> of one Linux install (launcher 0.2.37, Nightly 2026-11-03) sitting next to a PrismLauncher Fabric 26.3
> instance, written to answer one practical question before any code is written: **which of Horizon's two mod
> routes can carry which idea**. The survey itself only read disk and ran read-only tools; the follow-up at the
> end built both routes and ran them in game, and every claim is tagged by how it was checked (see Verification).

## Setup

- Arch Linux x64, Ryzen 7 8845H + Radeon 780M (Mesa 26.2.6, RADV), 27.9 GB RAM. Horizon needs **Vulkan**; it
  ran at 16:25-16:29 on 2026-11-03 with HDR10 (PQ) output from the same machine.
- **Horizon launcher 0.2.37** from playhorizon.dev: one stripped 60 MB Rust ELF (winit/egui; links xcb and
  xkbcommon). Its data lives in `~/.local/share/horizon-launcher/`, the game home in
  `~/.local/share/horizon/` (on Windows those are `%APPDATA%\horizon-launcher` and `%APPDATA%\horizon`,
  matching the older field note on the WASM mods).
- Installed game: Nightly **2026-11-03, commit `f42ef42`**, under `horizon-launcher/versions/nightly-2026-11-03-f42ef42/`:
  `horizon-client` 84 MB, `horizon-server` 7.2 MB, `horizon-ctl` 1 MB, `horizon-prepare` 2.5 MB, 525 scripts in
  `tools/`, and `.local/` at 1.2 GB of prepared resources (the player's `client.jar`/`server.jar`, exported
  registries, worldgen JSON, models, sprites, fonts). A second, older nightly (`2026-10-28`) is still on disk.
- Modding toolchain already present: `cargo-horizon-mod` in `~/.cargo/bin`, and a Horizon source clone in
  `~/.cargo/git/checkouts/horizon-5a198cb72f4fbd36/2b294bb/` (2026-10-29), where `NATIVE_HOOKS_API` is **2**.
- JVM side of the same machine: **JDK 25.0.5.0.3** now on PATH (`javac`/`javap` at `/usr/sbin`), so a Fabric
  26.3 jar can be rebuilt here. The PrismLauncher instance `26.3_fabric` pins Minecraft 26.3, Fabric Loader
  0.20.1, LWJGL 3.4.3 and runs on the bundled JRE `java-runtime-epsilon` 25.0.1; its `mods/` holds
  `fabric-api-0.165.0+26.3.jar` and one local mod, and it has no world.
- Not installed here: the launcher's native build toolchain (`<data>/rust/`, `<data>/cargo/`,
  `<data>/native/` are all absent). That matters for Gotcha 1.

## Route and why

Horizon deliberately offers two, and they are not interchangeable:

| | `.hmod` (WebAssembly component) | `.hnmod` (native mod bundle) |
|---|---|---|
| what it is | a zip of `horizon-mod.toml` + `mod.wasm` (+ assets/data) | a zip of `horizon-native.json`, `mixins/<id>/horizon-mixin.toml` and `.rs` helpers, compiled **into** the game |
| isolation | wasmtime sandbox: no file, network, process or clock; memory cap, fuel per call | none: the player's rights, arbitrary Rust |
| API | 0.1 client (log, game-read snapshot, chat, hud, storage, command, ui; tick/frame/chat/command hooks), 0.2 content (blocks/items as data + assets), 0.3 server (world read/write, players, commands, block placed/broken) | named functions of the game via horizon-mixins (HEAD, BEFORE_CALL, RETURN, MODIFY_ARG, OVERWRITE), plus Horizon's stable `native_hooks.rs` points |
| lifecycle | drop into the game home, toggle; one file for every OS/arch | launcher downloads the pinned source, applies the mixins, compiles a whole new game build and installs it as `native-<commit>-<key>` |
| can it move the player, read raw input, draw geometry? | **no**: the snapshot is read-only and there is no input or physics capability | yes |

So the route follows the idea, not taste:

- **HUD, chat, `/commands`, new blocks and items, server rules** - WASM (content mod for blocks/items, server
  mod for per-tick logic, client mod for panels). Reuse of Java-mod data is possible to the extent it is plain
  data/assets: resource packs, datapacks, models and textures; Fabric/NeoForge code never runs.
- **Anything that changes movement, aiming, camera or world rendering** (flight physics, grappling, custom
  world geometry) - native only, because the WASM contract deliberately stops at a read-only snapshot.
- **Rejected here:** treating the Fabric jar as portable (Horizon has no Java classes), and patching the
  client by hand instead of packaging the change as an `.hnmod` (the launcher only builds bundles, and the
  registry only lists those).

## How the game works (what we had to learn)

- **Launcher data layout.** `settings.json` (selected version, `minecraft_dir`, appearance, accent,
  `native_mods_noticed`), `accounts.json` (uuid, name, skin URL + model, cape), `instances.json`
  (`played_secs`, `last_played` per instance), `versions/<nightly>/`, `linked-minecraft/`, `server-jars/`,
  `benchmarks/launcher-<timestamp>-session.json`, `mod-browser/` (index + images), `profile-heads/`,
  `cache/github/`. `versions/<nightly>/.installed` is a marker file (its content here is literally `test`).
- **`linked-minecraft/`** symlinks `assets` and `libraries` to the PrismLauncher install and holds a minimal
  `versions/26.3/26.3.json` + jar. That is how one machine's Mojang files serve both launchers.
- **Game home layout.** `options.txt` (`version:5023`), `saves/`, `logs/latest.log` + gzipped rotations,
  `crash-reports/`, `horizon-mods.txt`, `horizon-native-mods/`, `mod-browser.json`, `horizon-graphics.txt`,
  `.horizon-cache/` (`registry-v1.bin`, `behaviours-v2.bin`), `assets/skins/`, `telemetry/consent.json`.
- **Mod enabling.** `horizon-mods.txt` is one `mod.<id>:true|false` line per mod. `mod-browser.json` records
  installs: `source`, `project`, `slug`, `kind`, `version`, `file`, `checksum` (`SHA-256:...`), `page`,
  `dependency`, `verdict` (`Unsigned` here), so the Mods page can show provenance.
- **`.hnmod` anatomy** (from the installed `treefall` 0.3.0): `horizon-native.json`, plus
  `mixins/treefall/horizon-mixin.toml` and helpers (`runtime.rs` 84 KB, `native.rs` 19 KB, and small
  `mining.rs`, `drops.rs`, `speed.rs`, `command.rs`, `click.rs`, `tick.rs`, `list.rs`, `settings.rs`). The
  manifest carries:
  - `[mod]` id, version, `priority` (same-site hooks run highest first; the first `Break` cancels the rest);
  - `[compatibility] horizon_revision = "142388e1c136e622652ec7505af15d8ad195e041"` - a pin to one exact
    commit, used when the mod hooks game functions that are not stable hook points;
  - `[[module]]` entries mapping a helper file into a module planted in `crates/horizon-client/src/game.rs`;
  - `[[injection]]` entries: `id`, `kind` (HEAD/BEFORE_CALL/RETURN/MODIFY_ARG/OVERWRITE), `cancellable`,
    `target = "horizon_client::game::Game<'_>::break_block"`, `helper`, and `bindings` that pass game state
    (e.g. `game`, `pos`, `stack`) into the helper.
- **Native builds are per nightly.** A bundle either pins a commit or, if it only uses stable hook points,
  names `"hooks": N` in `horizon-native.json`. Every Nightly keeps its source tag `nightly-source/<date>-<short>`,
  so a pinned mod still builds after the launcher moves on; all mods in one build must pin the same commit.
- **The build itself** is the release command on the pinned source:
  `cargo build --locked --profile release --features horizon-client/mods -p horizon-client`, with the launcher's
  own Rust 1.99.1 and a separate Cargo home, then a new version folder `native-<commit>-<key>` and a
  `native-mods.json` describing commit, mods, horizon-mixins and Rust. First build ~7-10 min and ~2 GB of
  `target/`; a helper edit recompiles only `horizon-client` (~3 min).
- **`horizon-ctl` is the agent door.** It talks to a running client over a socket and prints JSON:
  session (`launch`, `wait-ready`, `screenshot`, `logs`, `status`, `memory`, `worlds`, `open`, `save`, `quit`),
  observation (`state`, `looking-at`, `entities`, `block`, `light`, `events`, `input-log`), actions, and
  `horizon-ctl mcp` as a stdio MCP server. This makes in-game verification scriptable without window-level
  input automation, which is a real advantage over the Java client.

## Build steps

Fabric side (unchanged by Horizon):

```bash
cd <fabric-mod-project>
./gradlew build                # JDK 25; no mappings on 26.x, so no remap step
cp build/libs/<mod>.jar ~/.local/share/PrismLauncher/instances/26.3_fabric/minecraft/mods/
```

WASM mod for Horizon:

```bash
cargo horizon-mod new my-mod --template code|content
cd my-mod && cargo horizon-mod check && cargo horizon-mod test && cargo horizon-mod build
# .hmod -> ~/.local/share/horizon/horizon-mods/ and mod.my-mod:true in horizon-mods.txt
```

Native mod for Horizon (the only route for physics/render changes):

```bash
# Bundle: horizon-native.json + mixins/<id>/{horizon-mixin.toml,*.rs}
horizon-launcher native-build [FOLDER] [--instance NAME] --trust-native-code
# or: Settings > Game > Native mods (experimental), then Build on the Mods page
```

Java mods, `.hmod` and `.hnmod` can coexist in the data folders, but a Fabric jar in Horizon's mod folders is
inert: there is no Java to run it.

## Verification

Checked by reading disk and running read-only tools, on 2026-11-04:

- `horizon-launcher --version` -> `horizon-launcher 0.2.37`; `file` -> stripped x86-64 ELF.
- `horizon-ctl --help` lists the session/observe/act command groups and the MCP server.
- `~/.local/share/horizon/logs/latest.log` shows a real Nightly 2026-11-03 run: Vulkan (RADV Phoenix), HDR10,
  1291 block sprites, 35 723 block states / 1658 items / 67 biomes, world opened 16:27, player `FourtT`.
- `~/.local/share/horizon/horizon-native-mods/treefall.hnmod` opened as a zip: the file list and
  `horizon-mixin.toml` above.
- `~/.local/share/PrismLauncher/instances/26.3_fabric/{instance.cfg,mmc-pack.json}`: 26.3 + loader 0.20.1;
  `mods/`: Fabric API and one local mod, both newer than the only launch in `latest.log`.
- **Not verified in this survey:** that any `.hnmod` builds on this machine (nothing was built), that
  `treefall` works, whether a native build of this Nightly compiles with the installed Rust, and any in-game
  behaviour. No game was launched during the survey. The follow-up below did all of that on 2026-11-05.

## Follow-up: both routes built and run (2026-11-05)

Checked on the same machine, Nightly `f42ef42` for the game and custom builds from source:

- **WASM code mods no longer run.** A `.hmod` built with `cargo horizon-mod build` loads, but the first world
  prints `Horizon mods are native now: <name> stopped running until they have a native version` and the mod
  does nothing (content-only `.hmod` still works). The `f42ef42` binary has zero occurrences of `wasmtime`,
  `cranelift` or `horizon:mods`; `set-blocks` is absent too, so server API 0.3 is not in this nightly. Writing
  a WASM shim for logic has no runtime to load into.
- **Native builds work from a pinned source + `horizon-mixins`.** Verified pair:
  Horizon `d91cab68ded29bd2b004f7050c468fb98c41a00b` (Nightly 2026-10-31, MC 26.3) and horizon-mixins
  `ddd9700b21997c95d95ac6ee5ecafe3830cf622a` (0.6.0, the `MIXINS_REV` the f42ef42 launcher uses).
  `horizon-mixins plan/apply` takes ~6 s; `cargo build --locked --profile fast --no-default-features -p
  horizon-client` took 2 m 44 s warm and 2 m 54 s with a cold `target/` on a 16-thread Ryzen 7 8845H; the
  binary is ~74.5 MB and `target/` is 1.2-2 GB. Source tarball: `codeload.github.com/horizon-rust/horizon/tar.gz/<sha>`.
- **A native mod really changes the game.** The community `horizon-veinminer` port (3 HEAD hooks on
  `Game::break_block`) broke a 32-block iron vein with one hit and left 32 `raw_iron` on the ground: every
  extra block goes through the game's own `break_block_as_player`, so loot, XP, tool wear and block updates
  match a hand-mined block.
- **Logic parameters can be lifted from the Fabric jar without a JDK.** A small constant-pool + `<clinit>`
  reader (`jarparams.py`) extracted `server-sided-vein-mine` 1.5.0's 20-block list, `maxBlocks = 64` and its
  8 deepslate-to-stone ore pairs; a generator emitted a matching native bundle, and the bundle built and ran
  in game (32 ore placed, one break, 0 left, `raw_iron` picked up).
- **A second rule shape was ported: tree felling.** `treecapitatorlite-1.0.2+26.3` felled a test tree of 8 logs
  with one diamond-axe hit and dropped 8 `oak_log`; a pickaxe and Shift+axe each broke only the hit log; the
  leaves were left in place and decayed on their own. Its defaults are assigned in `ModConfig`'s constructor
  (`putfield`), not in `<clinit>`, so the reader now scans both. The generated bundle is 1 injection + 1
  module and built in 2 m 38 s; screenshots in the project's `shots/tree-*.png`.
- **A third shape: sneak-triggered felling with a build guard.** `server-tree-feller` 1.3.0 (sneak + axe,
  26-neighbour fill, `MAX_LOGS = 512`, player-placed logs spared) generated a 2-injection bundle: HEAD
  `Game::break_block` for the felling and HEAD `Game::native_place_block` (the player's `BlockItem.place`) to
  remember placed logs. In game: an 8-log tree and a 9-log tree both fell to one sneak-hit with every `oak_log`
  dropped and leaves left standing; a placed log standing next to a tree survived while the tree fell; sneak on
  dirt or a non-sneak hit broke only the hit block; a 10x10x10 cube of 1000 logs broke exactly 512 and left 488.
  Build: 2 m 10 s warm. Screenshots `shots/sf-*.png`. Differences from the jar: it breaks the whole tree at once
  instead of 3 blocks per tick, keeps the placed-log set in memory instead of `treefeller_placed.log`, and reads
  Shift on the client (`self.keys`), which makes this "server" mod a client-side one here. Its first version had
  a real bug worth remembering (gotcha 17): the placed-log guard covered only the block that was hit.
- **Two logic mods need one hook, not two.** Putting the vein and the sneak-feller bundles side by side
  does not run both: cancelling HEAD hooks execute in priority-then-mod-id order and the first `Break`
  skips the rest, so only the alphabetically earlier `serverveinmine_shim` ran (the 27-ore vein fell, the
  8-log tree did not). `f2h.py combine` merges the bundles into one module with one `break_block` hook that
  walks the rules in order and gives the break to the first whose predicate matches; the same build then
  mined the 27-ore vein and felled a 9-log tree in one session (2 m 34 s, 2 injections, no panics).
  Rule order is the order given on the command line.
- **Packaging and the launcher route work.** `f2h.py package` writes the launcher's `.hnmod`: a
  `horizon-native.json` (schema 1, `game`/`horizon`/`id`/`mixins`/`version`) plus `mixins/<id>/` with the
  manifest and `.rs` files, exactly the shape of the installed `treefall.hnmod`. A packaged combined bundle
  still plans (`1 module, 2 injections`) and the launcher compiled it: `native-build <unpacked> --server-output
  DIR --version nightly-2026-11-03-f42ef42 --trust-native-code --profile dev` took 3 min 10 s (first build:
  it downloaded Rust 1.99.1 and Horizon's source **at the mod's pinned commit** `d91cab6`, not the instance's
  `f42ef42`) and produced `horizon-engine`. Run as a client against isolated dirs, that build felled the 9-log
  tree and mined the 27-ore vein, no panics. `--server-output` is the one launcher mode that reads no instance
  and writes no launcher config; installing into the real game still needs the player's OK.
- **One build can host many rules.** `f2h.py host` emits `f2h_host`: a single break hook that reads
  `./f2h-rules.json` (or `$F2H_RULES`) on first use and dispatches to `vein`/`tree` rules from it. The
  game's `--game-dir` becomes the working directory, so the file sits next to `saves/`. `f2h.py rules
  <bundles>` writes it from generated shims (same numbers as the jar). Verified: build 2 min 54 s, two
  rules, a 9-log sneak-fell and a 27-ore vein in one session, log line `f2h: 2 rule(s) from
  f2h-rules.json`, no panics. Adding a mod of these shapes is a JSON edit, not a rebuild; a new *shape*
  still needs a template and a build.
- **A right-click rule is a fourth shape in the host (2026-11-08).** A rule with `"on": "use"` is skipped by
  the `break_block` dispatcher and runs at `Game::native_right_click_block` (API 21) instead: the matching
  click is claimed (`canceled = true`, so a chest/door/axe use does not also run) and the tree is felled
  through the same `f2h_tree_break`; a pickaxe, a non-log or a Shift-disabled rule passes through to vanilla.
  Host bundle `f2h_host` 1.1.0 has three injections (`break`, `place`, right click) and still plans with
  `horizon-mixins` (1 module, 3 injections, `status ok`). Verified in a peaceful test world (`HostUse2`, a
  stone platform, three 9-log trees and a 27-ore vein): axe + right-click `changed: true`, 9 logs felled and
  gone after a relaunch; pickaxe + right-click `changed: false`, 9 logs intact after a relaunch; Shift+axe
  still felled 9 logs (`picked_up` 4 + 5 on the ground); pickaxe on the vein still mined 27 ore (10 picked + 17
  on the ground; the `drops` field said 32 - gotcha 18). 0 panics across four sessions, log
  `f2h: 3 rule(s) from f2h-rules.json`, screenshot `shots/host-use-vein2.png` in the f2h project.
- **Installed in the player's real instance and verified there (2026-11-08).** The instance `Horizon (horizon)`
  (`~/.local/share/horizon`) already had `treefall.hnmod` 0.3.0 (`horizon 142388e1...`, 2026-10-28;
  `mixins 0d6b103c...`), while the host pins `d91cab6...` (2026-10-31; `mixins ddd9700b...`). They cannot
  build together without `--allow-version-mismatch`, which would use the newest commit (`d91cab6`), and both
  are HEAD hooks on `break_block` (`treefall` priority 200, host 100), so a tree would be felled twice. The
  native tree mod was therefore backed up and removed, not overwritten: `treefall.hnmod` and the old
  `horizon-mods.txt` are in `<home>/native-mods-backup-2026-11-08/`, and `mods remove treefall --instance
  horizon` cleaned `mod-browser.json`. The host was copied into `horizon-native-mods/`, turned on with
  `mod.f2h_host:true` in `horizon-mods.txt`, and `f2h-rules.example.json` became `<home>/f2h-rules.json`
  (sneak-fell, vein, right-click axe). `horizon-launcher native-build --instance horizon
  --trust-native-code` made `versions/native-d91cab6-2a0a24e575cf` in 2 min 18 s (performance, first build),
  with `base: nightly-2026-11-03-f42ef42`, `profile: performance`, `target: client` and the host's SHA-256 in
  `native-mods.json`; the instance is pinned to it while the global `selected_version` stays the Nightly.
  Verified by running that installed binary with `~/.local/share/horizon` as its working directory in a fresh
  world `HostReal` (never opening the player's `Новый мир`): axe + right click `changed: true` and the section
  stayed empty after a relaunch; pickaxe + right click `changed: false` with all 9 logs intact after a
  relaunch; pickaxe on a 27-ore vein removed all 27 (9 picked up + 18 on the ground in 14 item entities;
  `drops` again over-reported, 34). 0 panics in both sessions (`logs/game-real-install*.log`), screenshot
  `shots/real-install.png`, script `work/real-install-check.py` in the f2h project. Rollback is two commands
  plus the backup: `instance version horizon nightly-2026-11-03-f42ef42`, remove the host `.hnmod`, restore
  `treefall.hnmod` and `horizon-mods.txt`.
- **What "porting logic" means here.** The shim is a reimplementation with the jar's own constants, not the
  jar. Only rules with a known shape can be generated; anything else is hand-written against Horizon's API.
  Native mods are unsandboxed code with the player's rights, and each nightly needs its own build.

## Gotchas

1. **A `.hnmod` in `horizon-native-mods/` plus `mod.treefall:true` is not an installed mod.** Symptom: the mod
   is listed as enabled, but no `[mod treefall]` line ever appears in `latest.log` and the game behaves vanilla.
   **Cause:** native mods are *source bundles* compiled into the game; Horizon never loads the zip at runtime.
   **Fix:** build it first (`horizon-launcher native-build ...`, or the Mods page Build button). Absence of
   `<launcher data>/native/`, `rust/` and `cargo/` is the tell that no native build ever happened here.
2. **The pin and the installed nightly disagreed.** `treefall` pins `142388e1...`, while the installed build is
   Nightly `f42ef42`. **Cause:** it hooks `break_block`, `destroy_progress` and `pop_resource`, which are not
   stable hook points, so it must pin. **Fix:** the launcher builds on the *pinned* commit (downloading that
   source) - correct but a different game than the one being played unless every mod pins the same commit, so
   check the pin before trusting a mixed set.
3. **Stale `minecraft_dir`.** `settings.json` points at
   `PrismLauncher/instances/26.3/minecraft`, which does not exist (the instance is `26.3_fabric`). **Cause:** an
   instance was renamed or removed after the launcher recorded it. **Fix:** harmless while `linked-minecraft`
   still resolves assets/libraries and resources are already prepared; re-point it before a re-prepare, or
   `horizon-prepare --prepare --minecraft-dir ...` will look in a missing folder.
4. **`libflite.so` errors in both clients.** Symptom: `Narrator$InitializeException` in the Fabric log and
   `Failed to load library flite: libflite.so.1` in Horizon's. **Cause:** the system lacks flite. **Fix:** ignore
   (narrator only), or install `flite`.
5. **"Prepare resources with the launcher".** Horizon's crash report with `No such file or directory (os error 2)`
   and that line means the prepared data (`.local/.../horizon-client/26.3`) is missing, not a mod problem.
   **Fix:** `horizon-prepare --prepare --server-jar <26.3 server.jar>` or let the launcher prepare.
6. **WASM is the wrong tool for movement.** Client mods get a read-only snapshot and no input access. **Cause:**
   capabilities are imports and the manifest cannot declare what the contract does not expose. **Fix:** use a
   native bundle for physics/camera/render, and keep the WASM part (HUD, commands) separate.
7. **Native code is unsandboxed by design.** The launcher refuses to build without `--trust-native-code` and
   warns before every build; a registry listing follows a human source review of the `.rs`/`.toml` (the `.hnmod`
   *is* the source). Do not enable one for a player who has not read it.
8. **`um scan` misreads launcher-managed instances.** A Prism instance keeps the game jar in the shared
   `libraries/`, so the scanner reports "Unknown native engine" and no loaders. Fingerprint by hand from
   `mmc-pack.json` + the shared `libraries/`, as the Fabric 26.3 plan does.
9. **`horizon-ctl launch` starts a real game.** It opens a window and an integrated server. Do not call it while
   the human is playing, and quit with `horizon-ctl quit` (saves first) rather than killing a PID you guessed.
10. **`horizon-mixins` refuses a staged source with any symlink.** Symptom: `E_INVALID_PATH: symlinks are not
    supported in staged inputs` on `CLAUDE.md` (the GitHub tarball ships it as a symlink). **Fix:** delete
    symlinks in the extracted source (`find <src> -type l -delete`). It also refuses to plan without a
    `<src>/.horizon-revision` file containing the exact 40-character commit.
11. **`--game-dir` and `--home` are new.** Nightly 2026-10-28 exits with `unknown option --game-dir` and writes a
    crash report into the real `~/.local/share/horizon/crash-reports/`; Nightly 2026-11-03 (`f42ef42`) accepts
    both, which is how a custom build is kept away from the player's real world.
12. **`--no-default-features` is fine for a test build.** It drops `audio` and `controllers` (no sound, no pad),
    which is the documented server build; the client still renders and `horizon-ctl` works, and it avoids the
    libasound/libudev link.
13. **A mod's defaults may live in the constructor, not `<clinit>`.** Symptom: `jarparams.py` reports
    `tree: null` for a jar whose `javap` output clearly shows the values. **Cause:** `ModConfig` assigns
    `maxTreeSize`, `axeOnly` and friends with `putfield` in `<init>`. **Fix:** scan both `<clinit>` (`putstatic`)
    and `<init>` (`putfield`) when lifting constants.
14. **A Fabric event has no Horizon equivalent.** TreeCapitator Lite listens to
    `PlayerBlockBreakEvents.AFTER`; Horizon exposes functions, not events. **Fix:** hook `break_block` at HEAD
    and break the extra blocks with `break_block_as_player` (what the game itself calls). Drops, XP, tool wear
    and block updates match a hand-mined block, but the shim replaces the player's break instead of following
    it - only fold an "after" effect in when it can be expressed that way.
15. **`BlockTags.LOGS`/`LEAVES` map 1:1 onto the prepared resources.** `block-tags.json` in the 26.3 resource
    folder has every tag, and `Items::block_in_tag` expands `#tag` entries recursively (depth 32), so a mod's tag
    test becomes `self.res.items().block_in_tag("minecraft:logs", name)`.
16. **An injection target id is the impl module's path, not the type's.** Symptom: `E_TARGET_NOT_FOUND: no source
    function 'horizon_client::game::Game<'_>::native_place_block'`. **Cause:** `native_place_block` is implemented
    in `crates/horizon-client/src/game/native_hooks.rs` (`impl Game` inside module `native_hooks`), and
    `horizon-mixins` builds the id from the module path: `horizon_client::game::native_hooks::Game<'_>::native_place_block`.
    `break_block` lives directly in `game.rs`, which is why the first hook used the short path. **Fix:** grep the
    source for the `impl Game` block that holds the function and use that module path.
17. **A "do not break what the player built" guard needs the check on every candidate, not just the origin.**
    Symptom: a log the player placed next to a tree survived when hit directly but was felled when the adjacent
    tree came down. **Cause:** the first version tested the placed set only for the block that was hit. **Fix:**
    test the placed set inside the "is this a log" predicate used by the flood fill, and forget an entry when that
    block is mined by hand; `BlockItem.place` is `Game::native_place_block`, which is where placed blocks can be
    recorded at all.
18. **`horizon-ctl break`'s `drops` field is not the number of blocks.** Symptom: an 8-log tree reports
    `drops {oak_log: 9}`, and a 27-ore vein reported `{raw_iron: 33}` while 27 blocks disappeared.
    **Fix:** verify with `blocks` (what is left), plus inventory, plus summing `count` over the item entities
    from `entities`; those agree exactly (27 ore gave 21 on the ground + 6 in inventory). A cap test is the
    same: a 10x10x10 cube of 1000 logs left 488, so exactly `MAX_LOGS = 512` broke.
19. **Two cancellable HEAD hooks on one function do not compose.** Symptom: with a vein shim and a tree-feller
    shim in the same build only one works, and which one depends on the mod ids. **Cause:** `horizon-mixins`
    runs same-site HEAD hooks by priority descending then mod id ascending, and *the first `Break` skips the
    later hooks and the original body* (docs/advanced-injections.md). **Fix:** merge the mods into one bundle
    with a single hook that dispatches to each rule's `applies` predicate (`f2h.py combine`).
20. **The control socket's block view lags after server-side writes.** Symptom: `fill`/`setblock` answer
    "Successfully filled N" but `blocks`/`block` still show the old world, and `break` refuses with "there is no
    block at ..." or times out at `ticks 0`; a shim's multi-block break does it too. **Cause:** the reply is
    read from a different view of the chunk than the one just written. **Fix:** poll `blocks` until it matches
    (a few seconds), or restart the client between building a test scene and breaking; do not teleport onto a
    block that was just filled in (the player suffocates).
21. **The rule host reads its file once, from the game folder.** Symptom: `f2h-rules.json` edited while the
    game runs does nothing, or a rules file next to the binary is ignored. **Cause:** `rules()` is a
    `OnceLock`, and the path is `./f2h-rules.json` after `--game-dir` chdirs (or `$F2H_RULES`).
    **Fix:** put the file in the game dir, restart after edits; a missing file is not an error, the mod then
    behaves like vanilla (the log says `f2h: <path>: No such file`).
22. **`horizon-ctl tp` moves only the client, and the integrated server may snap it back.** Symptom: `tp` answers
    `{"ok": true}` but the next `state` shows the old position (a longer jump usually fails, a short one may
    stick), and the log has `Player moved wrongly!`. **Cause:** the socket command writes the client player's
    position directly; the server thread owns the authoritative position. **Fix:** teleport with the game
    command - `horizon-ctl command "tp @s X Y Z"` - when moving more than a couple of blocks.
23. **A felling rule triggered by a right click does not belong on `break_block`.** Symptom: the mod claims
    `Item.useOn` in Fabric but the obvious Horizon hook (the break hook) never fires, or it fells on left click
    too. **Cause:** a right click goes through `ServerPlayerGameMode.useItemOn`, which Horizon exposes as
    `Game::native_right_click_block` (`&mut canceled`, once per hand) before the block or item acts. **Fix:**
    give the rule `"on": "use"` and let the host claim the click; keep the `tool` suffix check so a pickaxe or
    an empty hand passes through. `f2h.py rules` does not emit this field yet: none of the five target logic
    jars triggers on right click (all use `PlayerBlockBreakEvents`/`AttackBlockCallback`), so it is a manual
    JSON edit. The hook point is API 21, so pin the source rather than using `"hooks": N` if the bundle also
    touches pinned functions.
24. **A hand-copied `.hnmod` still has to be turned on, and `mods list` will not show it.** Symptom:
    `horizon-launcher native-build --instance horizon` answers `No native mod is turned on in
    <home>/horizon-native-mods: install one from the Mods page first` although the archive is right there;
    or the build sees it but `mods list` prints nothing for it. **Cause:** `horizon-mods.txt` holds
    `mod.<id>:true` for every turned-on mod (native ones included), and `mods list` is built from
    `mod-browser.json`, which only knows what the browser installed. **Fix:** append `mod.<id>:true` (the
    `id` from the bundle's `horizon-native.json`, here `f2h_host`) and let `native-build` read the folder;
    for a browser-installed mod use `mods remove`/`disable` instead of deleting its file, so both records
    stay in step.
25. **Mixing native mods with different pins is not a free `--allow-version-mismatch`.** Symptom: the launcher
    offers to build on the newest pinned commit; two mods then hook the same `break_block` HEAD and the
    first cancels, or the older mod's code does not match the newer API. **Cause:** pinned bundles are
    compiled against one source tree, and same-site HEAD hooks do not compose (gotcha 19). **Fix:** check
    every bundle's `horizon`/`mixins` pair first; to keep the older mod, build on its commit with only mods
    made for it. Two tree mods are redundant anyway: back the older one up (file plus its
    `horizon-mods.txt` line), remove it, and build the host alone.
26. **Minecraft 26.3 renamed the gamerules.** Symptom: `gamerule doMobSpawning false` answers "invalid
    argument" in a test session that used it before. **Cause:** `crates/horizon-client-core/src/gamerules.rs`
    lists `spawn_mobs`; the datafixer maps the old name to `minecraft:spawn_mobs`. **Fix:** use
    `gamerule spawn_mobs false` (and check `gamerules.rs` for other renamed ones) in test scenes.

## Assets

Nothing generated in this survey. For the WASM route the older note covers content-mod assets (vanilla layout
under `assets/<id>/`, 16x16 textures, en/ru lang); for native mods there is no asset pipeline change - it is
the game's own resource system.

## Open questions

- Does `treefall` 0.3.0 build cleanly against `142388e1...` with this launcher, and what does it do in game? Not
  tested: it was backed up and removed before any build because the host pins a newer commit (2026-11-08), and
  the two both hook `break_block`.
- Which nightly is the registry pinning for current native mods, and is `NATIVE_HOOKS_API` past 2 upstream?
- Can the useful half of a Java mod (its data/assets) be lifted into a content `.hmod` without its code - worth
  a concrete port test on a small Fabric mod.
