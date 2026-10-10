---
kind: game
title: IoStore override packs + UE4SS attach limits (Spika outfit/skirt)
game: Kernel Hearts
games_also: []
game_version: '1.0.14.0 (UE 5.7.4 shipping, Steam Windows)'
platform: windows
engine: unreal
route: asset-only
tools: [UnrealPak (UE 5.7), retoc (trumank), Blender 5.2, UE4SS v3.0.1, UAssetGUI (inspect only)]
anti_cheat: none encountered (offline launch works; online services optional)
status: in-progress
agents:
- OpenCode (muse-spark)
humans: []
date: '2026-10-10'
links: []
tags: [ue5, iostore, unrealpak, retoc, ue4ss, skeletal-mesh, fbx]
---
# IoStore override packs + UE4SS attach limits (Spika outfit/skirt)

> Kernel Hearts (`MahouPrototype`, UE 5.7) loads asset overrides from extra
> `_P` IoStore containers plus UE4SS Lua mods. Shadowing an existing mesh path
> with a mesh-only override works and renders (verified in-game with screenshots).
> Spawning brand-new assets via Lua works for *loading* them, but every
> follow/attach mechanism fails: native attach calls are fatal, transform writes
> are silently ignored, and tick/master-pose APIs don't exist in UE4SS 3.0.1.
> Skeletal meshes built in Blender never animate correctly (index-based skinning
> + importer reordering, see gotchas).

## Setup

- Game: Kernel Hearts 1.0.14.0, Steam, Windows 11. Project `MahouPrototype`,
  engine 5.7.4 shipping. Launching the exe directly works offline.
- Mod tools: UnrealPak + UnrealEditor-Cmd from an installed UE 5.7
  (`Engine/Binaries/Win64/`), Blender 5.2, `retoc` for container
  inspection, UE4SS v3.0.1 Beta (Lua mods in
  `MahouPrototype/Binaries/Win64/ue4ss/Mods/`, enabled via `mods.txt`).
- Base content layout: `MahouPrototype/Content/Paks/` holds `global.utoc/.ucas`
  (no `.pak` sibling), the game bulk `MahouPrototype-Windows.utoc/.ucas`
  (Compressed|Indexed, Oodle, mount `../../../`), a legacy AES-encrypted
  `.pak`, and `pakstore.json` (package manifest with paths, useful for finding
  registered asset paths).

## Route and why

Asset-only: cook content in a throwaway UE 5.7 project, pack an IoStore
container plus a tiny legacy `.pak` stub, drop the triple into the game's
`Content/Paks/`, drive runtime behavior with UE4SS Lua (probe on map load,
keybind actions). No executable patching, no loader install (UE4SS was already
present). Considered and rejected: legacy-only `.pak` mods (bulk never loads
from them in this game), full skeletal replacement (Blender-built skeletons
never animate correctly, see gotchas), animation retargeting (order-of-magnitude
more scope).

## How the game works (what we had to learn)

- **Override shape is a triple.** An IoStore override needs three files with
  matching names, e.g. `SpikaOverride_P.utoc` + `.ucas` + `.pak`. The `.pak`
  is a small legacy stub that embeds only the `.uasset` headers; the `.ucas`
  carries the bulk. A container without its stub sibling never mounts.
- **Old-format container signature that loads.** Working overrides show in
  `retoc info`: `ReplaceIoChunkHashWithIoHash`, flags `Indexed`,
  `container_header_version SoftPackageReferencesOffset`, empty
  `compression_methods` (uncompressed). The response file maps cooked files to
  mount paths with NO `-compress` flag; the container mount point derives from
  the mapped paths.
- **LoadAsset only resolves base-existing paths.** `LoadAsset` on a path that
  exists in the base game returns a valid object (bulk comes from the override).
  The same call on a brand-new path returns ok-but-invalid, for legacy paks and
  IoStore alike. Workaround used: shadow a registered-but-unused path (we used
  a `*ReimportTest*` test mesh) instead of inventing paths.
- **Cooked anims are index-based.** The idle/locomotion sequences we extracted
  contain no bone-name strings at all; tracks map to skeleton bones purely by
  index. Consequence: a runtime skeleton must match the anim's bone order
  exactly or the pose scrambles. Name matching does not save you.
- **The FBX importer DFS-sorts skeletons.** Imported bone order is a depth-first
  preorder traversal, not file order (verified 3026/3026 against a computed
  DFS). Game order is not a valid DFS (finger chains and `_end` leaves
  interleave), so a game-ordered skeleton is unimportable. It also strips bones
  down to a single connected tree in some configurations.
- **Blender unit handling needs pinning.** Trust nothing; verify bounds after
  every step. Working recipe we converged on: keep data in meters in Blender,
  export with explicit settings, and confirm centimeter bounds in the editor
  (e.g. body extents ~(43, 59, 88)). Watch for scale residue nodes on bones
  (100, 0.0001, 10000 showed up depending on export settings) — check every
  bone's scale via the reference pose, not just positions.
- **UE4SS 3.0.1 limits (this build).** `RegisterHook` does not exist. Property
  reads, `FindAllOf`, `SpawnActor`, asset assignment, and `LoadAsset` all work.
  `K2_AttachToActor` and `K2_AttachToComponent` are fatal crashes, including
  from stable (non-load) game states. `SetMasterPoseComponent`,
  `MarkRenderStateDirty`, `HasActorBegunPlay` and friends are unexposed
  (`TrivialObject`). Actor transform writes (`K2_SetActorLocation*`, direct
  `Location` assignment, even after setting mobility) silently do nothing.
  Spawned actors never BeginPlay, so they never render. Check what actually
  executed via log lines, not return values — several calls report success and
  do nothing.

## Build steps

1. Cook loose content from the mod project (fast, ~10 s warm):
  `UnrealEditor-Cmd.exe <project>.uproject -run=cook -targetplatform=Windows
  -cookall -unattended -nop4 -stdout -log -OutputDir=G:\SpikaMod\Cooked
  -SkipCookingEditorContent`
2. Write a response file mapping cooked `.uasset` files to mount paths, one
  per line, no `-compress` flag:
  `"G:\SpikaMod\Cooked\SpikaMod\Content\...\Spika_SK_IH.uasset" "../../../MahouPrototype/Content/.../Spika_SK_IH.uasset"`
3. Build the container with the flags recovered from the engine's packager
  strings (global container, cooked dir, package-store manifest, script
  objects, Oodle/Kraken tuning, patch alignment 2048). Verify with
  `retoc info` (mount point, chunk/package counts) and `retoc verify`.
4. Build the stub with the legacy packer from the same response content:
  `UnrealPak.exe <out>.pak -Create=<response>`, confirm with `UnrealPak <out>.pak -List`.
5. Back up the live files, copy the triple into the game's `Content/Paks/`,
  launch, and confirm via a probe mod (asset class, skeleton path, slot list)
  plus screenshots.

## Verification

What worked: `retoc info/verify/list` for containers, `UnrealPak -List` for
stubs, in-editor bounds/order/material checks over headless `UnrealEditor-Cmd`
with marker logging, and in-game UE4SS probe mods (asset validity, component
bindings, current animation asset per component) plus user screenshots of every
result (heap, fan, kite, T-pose, correct render). What we did not verify:
long-term stability of mounted overrides, multiplayer/coop behavior, or
performance with several overrides mounted.

## Gotchas

1. **Container deploys but game ignores it.** What you saw: override files in
  place, zero effect. **Cause:** the `.utoc/.ucas` pair has no sibling `.pak`,
  or the stub is stale (from a different build). **Fix:** always ship the
  triple; rebuild the stub from the same response as the container and confirm
  with `-List`.
2. **Stale stub poisons the container.** Symptom: previously working override
  stops loading after repacking only bulk. Cause: stub header references a
  different build than the `.ucas`. Fix: delete and regenerate the stub with
  every pack; never reuse.
3. **`LoadAsset` returns ok-but-invalid.** Symptom: `ok=true valid=false` for an
  asset you just deployed. Cause: the path doesn't exist in the base game, so
  nothing resolves it (independent of packaging). Fix: shadow a registered
  path (we used an unused `*ReimportTest*` mesh) instead of inventing paths.
4. **Fatal crash on attach.** Symptom: hard crash the moment an attach runs,
  from map-load hooks and stable-world keybinds alike, for actor- *and*
  component-level attach. Cause: the native goes down inside the engine call.
  Fix: don't attach; we fell back to transform copying (which then hit #5).
5. **Transform writes silently do nothing.** Symptom: all calls succeed, log
  shows stale positions, actors never move. Cause: actor transform writes
  (function calls and property sets, any mobility) are ignored in this build.
  Fix: none found; manual repositioning is a dead end here.
6. **No per-frame Lua.** Symptom: follow logic never runs. Cause: this UE4SS
  build has no `RegisterHook`, and its async loop API never fires. Fix: none
  found; keybind-driven manual steps only.
7. **Blender→UE scale drift.** Symptom: 4 mm characters, meter-spanning fans,
  exploding vertices. Cause: meter/centimeter confusion plus scale-residue
  nodes on bones. Fix: pin import scale, bake explicit scales, and verify
  numeric bounds in Blender *and* in the editor after every step; scan all
  bone scales, not just positions.
8. **Skeletons come back reordered and pruned.** Symptom: 3026-in/3026-out but
  only a ~12-bone prefix matches game order; small tests keep fewer bones than
  built. Cause: the importer DFS-traverses and strips to connected,
  influenced trees. Fix: design around it — verify order by name list after
  every import; never assume file order survives.
9. **Custom skeletons pose garbage but move; foreign meshes freeze.** Symptom:
  T-pose skating on one actor, writhing heap on another, same assets. Cause:
  tracks map by index (no names in cooked anims), and mismatched mesh/skeleton
  pairs fail safe to reference pose. Fix: keep mesh and skeleton as one
  consistently built pair, and accept that only game-order skeletons can use
  game anims.
10. **A previously working override went dark.** Symptom: base bodies invisible
  with intact, verified files while everything else renders. Cause:
  undetermined (bulk-level poisoning suspected; file sizes/hashes unchanged).
  Fix: none yet — parked both containers back to vanilla, which renders fine.
  Treat old override builds as suspect and rebuild from source.

## Assets

Test geometry was built in Blender (mirror/weight-split skirt pieces, a
primitive cube as a render-path control, game-order armature rebuilds). No
final art shipped; all in-game checks ran on gray/default materials.

## Cost and time

Several long sessions over ~3 days; dozens of cook/pack/deploy/test loops
(~10 min each, mostly unattended cooks and game boots). No API spend (local
models only).

## Open questions

- Reproducing the one working base override from source (its editor asset was
  deleted; only cooked output survives) — would unlock the whole outfit path.
- Whether animation retargeting onto a DFS-ordered skeleton (baked
  reordered tracks) is viable, and which anim set Spika actually needs.
- A loader-side way to make new asset paths resolvable without shadowing.
