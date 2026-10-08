# Mount & Blade II: Bannerlord: an editor-free asset SDK

Python code that writes Bannerlord's asset formats directly, without the Modding Kit editor: textures,
materials, static and skinned meshes, skeletons with ragdoll physics, skeletal animations, animation clips and
their runtime caches, packed into `.tpac` packages and `.rdc` caches the game loads from your own module.
The editor's Resource Browser import takes seconds to minutes per asset and needs a person at the mouse; these
scripts take seconds per asset and run unattended over tens of thousands of assets.

It also carries the checks that matter once you build your own skeletons: validators for the faults the
native client turns into crashes or freezes, a safe installer (backup, manifest, revert, refuses while the
game runs), a packer that merges thousands of packages into a few (34,000 assets in 26 packages: package loading
measured at 25.7 s warm and 280 s cold before, 5.6 s after),
reference scripts for an unattended game test harness, and the minidump and Ghidra helpers used to find those
faults. The formats are explained in [the technique note](../../knowledge/techniques/editor-free-bannerlord-assets.md);
this folder is the code behind it.

**No game content is included.** Everything is read from, and generated against, your own install. The record
templates the writers patch are taken from your Native module at run time (see "Templates").

## Requirements
- Python 3.10+ and `numpy` (the only third-party package: `pip install -r requirements.txt`). LZ4 and
  xxHash64 are small pure-Python implementations, PNG reading and writing is in `sdk/pngio.py`.
- Mount & Blade II: Bannerlord on Windows. Developed against v1.4.8.119303 (Steam). The Modding Kit is **not**
  needed.
- For `dump/`: `pip install minidump`; Ghidra and JDK 21 only for `RE.java`.
- For `harness/`: PowerShell 5.1 and a matching C# part in your module (not included, see "Harness").

## Setup
The SDK reads its paths from `sdk/config.py`, which reads these environment variables:

| variable | meaning | default |
|---|---|---|
| `BANNERLORD_DIR` | the game install (holds `bin\` and `Modules\`) | the standard Steam path, if it exists |
| `BANNERLORD_MODULE_DIR` | the module you are building, `<game>\Modules\<YourModule>`; required by install, revert and pack commands | none |
| `MODULE_ASSET_SUB` | sub-folder of the module's `Assets` that holds this SDK's packages | `mymod` |
| `SDK_STAGE_DIR` | where writers stage output before install | `./stage` |
| `SDK_BACKUP_DIR` | where install keeps backups and manifests | `./backup` |
| `SDK_LOCK_FILE` | install, revert and pack refuse while it names another owner | `./GAME_LOCK` |

```powershell
$env:BANNERLORD_MODULE_DIR = "C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord\Modules\MyMod"
python sdk/config.py        # prints what the SDK resolved
python sdk/selftest.py      # needs only BANNERLORD_DIR
```

Every script runs from any folder (`python sdk/tpac.py ...`) or as a module from this folder
(`python -m sdk.tpac ...`). `python sdk/<script>.py` with no arguments prints its commands.

## Commands
`sdk/install.py` is the front door. Writers stage into `stage/<name>` (default `work`); `install` copies a stage
into the module.

```powershell
python sdk/install.py texture rock_d.png                       # BC1/BC3 by alpha; _n becomes BC5, _s BC1, _h BC4
python sdk/install.py material rock --diffuse rock_d --normal rock_n --skinned
python sdk/install.py skeleton creature.gltf --name creature_skeleton     # max 64 bones, minimal ragdoll; FBX works too
python sdk/install.py mesh creature.fbx --material rock        # skinned bones are named bip01_<name>_<index>
python sdk/install.py anim creature_walk.fbx                   # single-take FBX -> skeleton animation
python sdk/install.py owner stage/work/Assets/creature_walk_geo.tpac --skeleton <skeleton guid>
python sdk/install.py clip creature_walk_clip creature_walk 31 # clip on that animation, 31 frames at 30 fps
python sdk/install.py clip-cache "creature_walk_clip"          # its RuntimeDataCache entry, no editor load needed
python sdk/install.py verify stage                             # validators on the stage
python sdk/install.py install --dry                            # what would be copied where
python sdk/install.py install                                  # backup + manifest, then copy
python sdk/install.py revert                                   # undo the newest install
python sdk/install.py status
```

| script | what it is |
|---|---|
| `sdk/install.py` | stage writers, `verify`, `install`, `revert`, `status`, `inspect` |
| `sdk/tpac.py` | the `.tpac` / `.rdc` reader and writer: textures (BC1, BC3, BC4, BC5, BC7 mode 6, RGBA8), materials, animations from FBX, clips, clip caches; `texture`, `tex`, `material`, `mtl`, `retex`, `anim`, `clip`, `clip-cache`, `optanim`, `owner`, `anims` |
| `sdk/sdk_mesh.py` | FBX to metamesh packages and vertex-stream caches; `mesh`, `obj` |
| `sdk/sdk_skeleton.py` | skeleton packages from FBX or glTF, Native skeleton readers |
| `sdk/tpac_pack.py` | merge many packages into a few and prove the merge; `scan`, `pack`, `verify`, `install`, `unpack`, `native-check`, `logcheck` |
| `sdk/validate.py` | validators: stage, skeleton, clip, `project.mbproj` registration, monster bones |
| `sdk/clip_partners.py` | the clip partner rule against Native's clips |
| `sdk/ik_hit_bones.py`, `sdk/hit_fit.py` | the hit-IK freeze rule, and hit capsules fitted to a skinned mesh |
| `sdk/tw_formats.py` | engine-exact details (data type versions, cache rules, size trailers) and a second reader |
| `sdk/templates.py`, `sdk/config.py`, `sdk/pngio.py`, `sdk/fbx_bones.py` | templates from Native, paths, PNG, FBX reader |
| `sdk/selftest.py` | the self-test below |
| `harness/` | PowerShell scripts that drive the game unattended |
| `dump/` | minidump helpers and the headless Ghidra batch script |

## Templates
Two writers patch an existing record instead of building one from nothing. Both start from your own Native
module, read at run time and never written back:

- **Clips** (`clip`): a plain Native clip record, the most common shape among Native clips that have no sound,
  voice, facial, partner, follow-up or combat parameter and no lists (on the author's install: `chicken_run_gait`
  in `animations_animals`).
- **Materials** (`material`, static and skinned): head, parameters and alpha reference from a plain Native
  `pbr_shading` record without material flags and vertex layout (on the author's install: `weapons1.lod` in
  `EmAssetPackages\mat0\materials`); the vertex layout, blend mode and shader flags are then set by the SDK, so the
  result does not depend on which Native record was picked.

`python sdk/templates.py` prints what was picked on your install. If a future game version changes the shape
and nothing qualifies, the command stops and asks for `--template <package>`: a one-clip package or a material
package written by the editor or by this SDK. Nothing is shipped from the game or from the author's module.

## Self-test
`python sdk/selftest.py` needs only your install and writes only to `SDK_STAGE_DIR/_selftest`. Result on the
author's machine, game v1.4.8.119303, default settings (42 s), condensed:

```
PASS packages   200 of 200 sampled Native packages rebuild byte-identical (18495 items; AssetPackages 50/50, EmAssetPackages 150/150)
PASS textures   24 Native textures: record re-pack identical 24, size rule 24, pixel hash rule 20; re-encode PSNR min: BC4 46.9, BC5 51.2, DXT1 48.7, DXT5 52.6 dB, RGBA8 exact
PASS caches     297 Native clip caches: size trailer rule 297; 226 read by the SDK, 226 re-pack byte-identical; 71 are layout variants it does not read
PASS skeletons  3 of 3 Native skeletons re-pack byte-identical
PASS synthetic  14 of 14 checks
SUMMARY: 5 PASS, 0 FAIL
```

- `packages`: each sampled Native `.tpac` is parsed and written again with the SDK's package writer; the bytes
  must equal the file. `--full --max-package-mb 100000` does all of them: 1188 of 1188 (91,394 items, 86 s).
- `textures`: BC4, BC5, BC7, DXT1, DXT5 and RGBA8 textures with inline pixels. The pixel-hash rule fails on 4
  of 24 (BC4 and BC5 maps; the reason is unknown), so the check asks for 80 percent.
  BC7 has no decoder here, so only its record, hash and size are checked. Native also uses DXT3, BC6H, R8 and
  float formats, which the SDK does not write and the test skips.
- `caches`: Native clips that have no root channel (45) or carry raw key channels (26) use layouts the SDK does
  not produce; they are counted, not hidden.
- `synthetic`: a made-up skeleton, animation, clip, clip cache, texture, material and mesh are written, read back and
  validated; then four planted faults (65 bones, the IK rule, a 64 character clip name, a made-up `project.mbproj`
  id) must each be caught.

## What is verified and what is not
Verified, by byte-identical round trips and comparisons on the author's machine, **for game v1.4.8.119303 only**:
the container and cache formats, textures, materials, skeletons and clip caches (above, and in the technique
note: 161 of 166 editor textures, 103 of 103 editor clip caches, all 150 Native asset packages). The content
written by this packaged copy was compared with the author's original scripts on a clip, a movement clip, two
materials, a mesh and an animation: the same bytes apart from random ids and the source-path string for the
clips and materials, and the same decoded mesh and animation data. The record hash of a clip is now the correct
xxh64; the originals kept the template's stale one, which the engine does not check. Texture mips are an
area average: within one level of the original for opaque power-of-two sizes, further apart at other sizes and
with alpha, where the original's 8-bit premultiplied resize was the less accurate one.

Not verified: other game versions (offsets and layouts may move; treat every address in the notes as stale after
an update), this packaged copy running inside the game (the originals were), the harness scripts against a real
module (the dry run works), multiplayer and anti-cheat (single player only, never involved), and the items in
the "Not verified" section of the technique note.

Things that stay specific to a workflow rather than generic: skinned FBX bones must be named
`bip01_<name>_<index>`; the minimal ragdoll `skeleton` writes is a starting point, not a tuned one; clip caches
are written for clips with a root position channel.

## Harness
`harness/` is reference material. It drives the game through a module-side "autostart" file and test words,
and it needs a matching C# part in your module that this folder does not include; the knowledge notes
([custom races and creatures](../../knowledge/techniques/bannerlord-custom-races-and-creatures.md),
[native crashes and hangs](../../knowledge/techniques/bannerlord-native-crashes-and-hangs.md), and
[the Borderlands 2 conversion](../../knowledge/games/mount-and-blade-ii-bannerlord/bannerlord-borderlands-2-total-conversion.md))
describe what the original one did.

How it works: the game is launched with
`/singleplayer _MODULES_*Native*SandBoxCore*CustomBattle*<YourModule>*_MODULES_` so the launcher's saved mod
list is untouched. `night_test.ps1` writes the test words (`plain fight quit ...`) to an autostart file; your
module's C# reads it at startup, runs the scenario, writes an end marker (default `AUTOTEST_DONE`) to its log and
quits. The harness waits for that marker, collects the log lines of this run and the Windows crash events, runs
once more if the first attempt failed, and can record video through a script you pass in (`-Record`).
`bannerlord_test_config.ps1` switches the game to a silent windowed setup and restores the launcher config on
exit (`LauncherData.xml`, `engine_config.txt`, `BannerlordConfig.txt` byte for byte; the one exception is a
backup that itself holds a test leftover with sound off, which it repairs); `game_lock.ps1` holds a lock file so
two sessions never run the game at once, and the SDK's install and pack commands honour the same file.
`player_checks.ps1` runs named checks from a JSON file (`checks.example.json`) and prints PASS and FAIL lines.

```powershell
powershell -ExecutionPolicy Bypass -File harness\night_test.ps1 -Module MyMod -Words "plain fight quit" `
    -LogFile "$env:BANNERLORD_MODULE_DIR\mymod_log.txt" -DryRun       # without the game: checks the harness itself
```

The harness never sends input, stops only the process it started, and reports any change in the save folder
(new files are moved aside, never deleted). It does not answer game dialogs (the "enable safe mode" prompt after
a crash needs a person or a UI-automation helper).

## Crash dumps and reverse engineering
`dump/` holds the minidump helpers (`threads.py`, `unwind.py`, `loc.py`, `rd.py`, `huge.py`, `vt.py`) and
`RE.java` with `re.ps1`, a batch script for headless Ghidra. `dump/README.txt` has the usage. Keep decompiler output
out of version control; the repository rules ask for logic described in your own words.

## Files
```
sdk/            the library and command-line tools (listed above)
harness/        night_test.ps1, run_bannerlord_test.ps1, bannerlord_test_config.ps1, game_lock.ps1,
                player_checks.ps1, checks.example.json
dump/           minidump helpers, RE.java, re.ps1, README.txt
requirements.txt
```

## Credits
- **TaleWorlds Entertainment** make Bannerlord and the Modding Kit; the game and everything in it belong to them.
  Every format here was worked out from files and binaries a player's own install holds.
- **TpacTool** by szszss showed that `.tpac` is a readable container; the reader and writer here were written
  from the editor's output and Native's own packages.
- **LZ4** and **xxHash** are algorithms by Yann Collet; the block decoder and encoder and the 64-bit hash here are
  small independent implementations of the published formats.
- **Ghidra**, **ILSpy** and the python **minidump** package were used to read the engine and the dumps.
- Background: the code was written while converting Borderlands 2 content into Bannerlord, described in
  [the total conversion note](../../knowledge/games/mount-and-blade-ii-bannerlord/bannerlord-borderlands-2-total-conversion.md);
  none of that content is part of this folder.
- Packaged for this repository by Claude Code (Opus 5.5 with Sonnet 5.5 helpers) from the author's project, for
  the human credited in the notes.

See also: [the technique note](../../knowledge/techniques/editor-free-bannerlord-assets.md),
[custom races and creatures](../../knowledge/techniques/bannerlord-custom-races-and-creatures.md),
[native crashes and hangs](../../knowledge/techniques/bannerlord-native-crashes-and-hangs.md).
