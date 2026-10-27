---
kind: game
title: "A film-style Lara outfit pack: every player .drm rebuilt, per-outfit idles and walks, and a private drag-and-drop package tested in a clean room"
game: "Tomb Raider: Legend"
games_also: []
game_version: "Steam PC build, trl.exe MD5 bd846c8fb3223e53bee022bb307b21bc (NextGen renderer on), Windows 11"
platform: windows
engine: unknown
route: native-hook
tools: ["Ultimate ASI Loader + TR7-Menu-Hook 2.5 (the TRLAU-menu-hook v2.5 release zip)", "MinHook 1.3.4", "MSVC 19.51 x86 + CMake + Ninja", "Blender 5.2.1", "cdcEditor 0.1.1 (Blender add-on)", "Python 3 + numpy", "Ghidra 12.0.1 + GhidrAssistMCP", "capstone + pefile", "Windows PowerShell 5.1", "um backup / um publish check / um win"]
anti_cheat: "none (single-player; Steam copy, SteamStub left untouched: runtime hooks and mods\\ files only)"
status: in-progress
agents: ["Claude Code (Fable 5.1)", "Claude Code (Opus 5.5)"]
humans: ["@skurtyyskirts"]
date: 2026-10-27
links: ["https://github.com/TheIndra55/TRLAU-menu-hook", "https://github.com/ThirteenAG/Ultimate-ASI-Loader", "https://github.com/Raq1/cdcEditor", "https://aka.ms/vs/17/release/vc_redist.x86.exe"]
tags: ["outfits", "drm", "cdc-engine", "idles", "animation", "rig", "packaging", "clean-room", "uninstall", "native-hook"]
---

# A film-style Lara outfit pack: every player .drm rebuilt, per-outfit idles and walks, and a private drag-and-drop package

A pack that dresses Lara in 2001-film-style outfits everywhere Tomb Raider: Legend shows her (gameplay, cutscenes, the
main menu and every wardrobe slot) was rebuilt and extended: young Lara and the 19 wardrobe-only slots got film
outfits (40 DRMs), the Tokyo party gown was rebuilt on its own 96-segment rig with its own walks and idles, a torn
tactical dress family was rebuilt from the same garment, idles became per-outfit sets, and a wall-stop reaction was added.
The whole thing was then packaged as a drag-and-drop folder and installed, verified and uninstalled in a clean-room copy
of the game. Builds were deployed to the human's game and checked in game by them from 2026-10-12 on; the
package passed every offline test, but a launch from the clean room was still owed. The ASI, the loader, the reload
system and the DRM animation basics are in
[film-reloads-qa-bridge-physics-mags-asi.md](film-reloads-qa-bridge-physics-mags-asi.md); the strand hair on the two
dresses is in [physics-strand-hair-appended-bones.md](physics-strand-hair-appended-bones.md).

## Setup
- Steam Legend (trl.exe MD5 above), Windows 11. The ASI refuses to install on any other exe (GOG, discs, an unwrapped
  exe), checking byte signatures at every hook site (499 sites at 0.9.3).
- The loader pair from TRLAU-menu-hook's v2.5 release zip, unmodified: its `binkw32.dll` (Ultimate ASI Loader) and
  `TR7-Menu-Hook.asi`, which serves `pc-w\X.drm` from `<game>\mods\X.drm`. TR7-Menu-Hook needs the x86 Visual C++
  2015-2022 runtime.
- Blender 5.2.1 + cdcEditor 0.1.1 (export/import of player DRMs); the mod's own Python DRM parser and container writer
  (layouts from tr7.pdb; it reproduces all 82 extracted vanilla DRMs byte for byte); Ghidra 12.0.1 + GhidrAssistMCP.
- `um backup create` of the saves folder before every deploy; `um publish check` on the package folder.

## Route and why
Data plus a native ASI. Outfits are whole player DRMs bound by object name, so an outfit is a rebuilt DRM in `mods\`;
behaviour the data cannot express (which idles an outfit may play, the gown's walk shuffle, the wall stop, the reload
and ammo rules) lives in the ASI with byte-checked hook sites. The assembler is the mod's own: components (body,
outfit garments, gear, hair) are grafted onto a vanilla template DRM in Blender via cdcEditor, and only the changed
sections are spliced back.

## How the game works (what we had to learn)
- **Copies of every outfit.** Each look exists several times: the gameplay object (`lara_evening`), its cutscene copy
  (`cine_lara_evening`), main-menu copies (`title_lara_*`, nine title units) and wardrobe previews (`costume_*`). A pack
  that misses one shows the vanilla Lara in that place. A census of all 70 cutscene rows maps which copy each one uses;
  `lara_child` (the 9-year-old in the plane-crash and flashback scenes) was kept vanilla by design.
- **Texture ids are global and shared across DRMs.** The same id must carry byte-identical texels in every DRM that
  holds it, so outfits that share an id deploy together. Example: the party gown ids 0x401-0x40C live only in the gown
  and its cutscene copy, the dress fabric 0x34D-0x34F in all six evening DRMs, 0x341/0x342 in ten. A set-wide check
  that compares every shared id across the deploy set catches mixed builds.
- **The 96-segment gown rig.** lara.drm's skeleton raised 12.1 units (heels) and renumbered, plus an inserted upper-chest
  joint (4) between the chest and the neck/clavicles/breast bones; 10 = head; 36-40 a braid chain; 95 a handbag bone.
  A tool that folds the inserted joint into its parent (`R3' = R3 * R4`) and re-bases translations through the pivots
  maps clips 96 <-> 109 losslessly (round trip on all 15 gown clips: worst 0.0006 degrees).
- **How a 96-segment object is animated.** The gown's animList has 487 entries: indices 0-17 are its own 96-segment
  clips (846 bind pose, 847 the walk with root motion (0, -640, 0), 848/849 diagonals, 850 the idle base loop, 852-858
  turns/starts/stops, 859/860 the idle variations); everything after is lara's 109-segment clips, never valid on this
  rig. The player state machine addresses animList *indices*. The gown's PlayerProp (a DTP section at Object+0x60) holds
  three Idle records (860, 859 and the default 850).
- **Idles.** The ASI's idle director resolves `[Idle] Anims` ids on whatever object is current. Per-object sets
  (`ObjectAnims=<object>:<ids>;...`) keep 109-rig idles off the gown; `NeedsPistols` idles play only with a pistol
  instance and holster markers 4/6 on the model; `NoRepeatWindow=3` prevents back-to-back repeats.
- **Maintenance idles with the gun in hand.** A pistol follows a hand when `Instance.linkMarkerIndex` (+0xBE) names the
  hand's marker; the engine places a linked child at the parent's marker during the matrix rebuild (0x4DF43F /
  0x4DF44C), the same short its own MoveItemToReady writes through `INSTANCE_LinkToParent` (0x456E79).
- **Wall stop.** The engine's own stop at a wall comes from `UpdateGroundControlZone` (0x005A5830); holding the brace
  while the stick still pushes needed a detour there (speed gates 550 / 350 units/s; the gown walks at ~690).
- **Cutscene motion is fixed stream data;** only the model is yours. Cutscene-only corrections (the eye bones of the
  96 rig are 24-27, of the 109/149 rigs elsewhere) must be keyed per rig.
- **Rotation vectors are averaged without unwrap in blends** and lerped between keys after a 2 pi unwrap: a clip that
  ends on a full 360-degree rotation vector (the identity) blends into the next pose with one extra full turn. Author
  end keys at 0, or wrap each key into (-180, 180].

## Build steps
1. Back up saves (`um backup create`), the `HKCU\Software\Crystal Dynamics\Tomb Raider: Legend` key, and every file a
   deploy replaces (each deploy writes a backup list so one script can roll it back).
2. Build the components in Blender (one heavy job at a time), then each target DRM: graft the components onto the vanilla
   template with cdcEditor, splice only the changed sections, re-parse, and render the textured bind pose from front,
   3/4, back and close-up.
3. Check the set: every changed section accounted for, shared texture ids byte-identical across the deploy set, segment
   and bone counts as the spec says.
4. Host new idles/walks into the DRM (`animList` + DTP event lists, as in the reloads note) and list them per object in
   the ini.
5. Deploy with trl.exe closed: `mods\*.drm`, `mods\hair\*.hair`, the ASI and its ini.
6. Package: copy the deployed set into a folder laid out like the game folder (below), lint it, test it in a clean room.

### The package folder (drag and drop into the folder that holds trl.exe)
This is a **private, local package** for the user's own install: its DRMs keep vanilla sections (see Assets), so
it must not be uploaded as is. A public release needs a patcher that rebuilds the DRMs from the player's install.
- The loader pair unmodified, `trl_croft.asi`, its ini (logging and test switches off), `mods\`, a README (requirements,
  install, features, controls, settings, uninstall, troubleshooting, credits and licenses, AI-use disclosure), and a
  `Croft2001\` folder with `Verify.bat`, `Uninstall.bat`, a PowerShell 5.1 script, a sha256 manifest and the licence texts
  (UAL MIT, TRLAU-menu-hook GPL-3.0 with a source link, MinHook BSD-2, SMAA MIT). 401 files, 5.6 GB; zip 2.06 GB.
- No unmodified game file is in the folder, but the rebuilt DRMs carry vanilla sections (see Assets). The menu
  hook's `binkw32.dll` (the copy in its v2.5 zip) is an Ultimate ASI Loader build with RAD's Bink DLLs built in, so
  it can overwrite the game's Bink DLL with no `binkw32Hooked.dll` (the menu hook's own install does the same).
  Current Ultimate ASI Loader builds don't carry Bink: their Bink proxies need the original as `binkw32Hooked.dll`.
- Verify: trl.exe is the Steam build (MD5), every mod file present with the right hash, the x86 VC++ runtime installed,
  the classic mistakes (dropped one folder too deep, foreign files in `mods\`, other d3d9 wrappers).
- Uninstall: removes only files whose hash matches the manifest plus the ini, keeps the loader pair (other Legend mods
  use it), and deletes its own folder from a detached cmd.
- Clean room: a vanilla Steam Legend folder on the same volume as the real one, with the big read-only data (bigfile.*,
  `.bik`, tr7.pdb) hard-linked, the small files copied, and the *original* Bink DLL; 60 files, almost no disk used.
  Delete the folder afterwards; only the links go.

## Verification
- `um publish check` on the package folder against the clean room: PASS, 401 files, 0 failures, 0 warnings. It
  only catches files byte-identical to the game's, so it can't see the vanilla sections inside the rebuilt DRMs.
- Scripted clean-room test, all PASS: (A) a folder dropped one level too deep is explained by Verify; (B) a fresh
  install verifies; (C) the 392 installed files equal the deployed, play-tested build except the one ini line;
  (D) Uninstall returns the folder to vanilla plus the loader pair; (E) reinstall.
- In game (the human, 2026-10-12): the gown before the rip carries no weapons, the switch to the tactical dress happens
  at the rip cutscene and she has guns afterwards (checked on an earlier build); the dresses' crash and the shirt's
  z-fighting below were their finds.
- Not verified: a launch from the clean room (the only setup where the FMVs play through the loader's built-in Bink),
  the 70-row cutscene sweep, each new idle seen in game.

## Gotchas
1. **Idles on the party gown played with the legs driven by finger channels.** **Cause:** the gown is a 96-segment
   rig and the idle list named 109-segment clips, which also exist in its animList at shifted indices. **Fix:**
   per-object idle sets in the ASI and new 96-segment idles authored on the 109 rig, then remapped.
2. **The Classic shirt z-fought with the shorts on her back.** **Cause:** the top and shorts were cut at the same ease
   from the same skin, so the tucked hem lay flush on the waistband. **Fix:** sink every overlapped top vertex 0.4 units
   inside the shorts (1.0 from 3 units below the waistband), NextGen positions only. Re-run it after any rebuild until the
   garment generator uses a smaller ease for a tucked top.
3. **A walk authored with a tiled root dragged the IK hands out of reach.** **Fix:** author cyclic walks in place and
   let root motion carry them. Never route a hand gesture so the upper arm twists a full 360 degrees: the rotation
   vector wraps at the loop.
4. **The reload spun the pistol twice at the very end.** **Cause:** each spin's last keys sat at |v| = 360 degrees and
   the blend averages rotation vectors with no unwrap. Also: an inventory had read the grab joints' *translation*
   tracks as rotations in radians (28.5 units "= 1,634 degrees"). **Fix:** end keys at 0 (or keys wrapped into (-180,
   180]); check spins with the engine's own half-key interpolation.
5. **Old one-shot scheduled tasks re-fired at 23:59 and deployed a stale build over the game.** They were created with
   `schtasks /SC ONCE` and a future start time, run by hand, and left in place. **Fix:** roll back from the deploy's
   backup list; delete a one-shot task right after it runs (`schtasks /Delete /TN <name> /F`).
6. **Uninstall failed when started from a PowerShell 7 window** ("Get-FileHash" missing). **Cause:** cmd passes PS7's
   `PSModulePath` to Windows PowerShell 5.1, which then cannot load its own Microsoft.PowerShell.Utility. **Fix:** the
   `.bat` wrappers clear `PSModulePath` before calling `powershell -NoProfile -ExecutionPolicy Bypass -File ...`, and the
   script hashes through .NET (`[Security.Cryptography.SHA256]::Create()`).
7. **The deploy check failed on four ids after a rebuild.** **Cause:** a stale "unpatched" DRM copy kept from an earlier
   run was picked up. **Fix:** move stale copies out of the build tree; never keep the first copy silently.
8. **A detached deploy "waiter" died without a log line,** and a `cmd /c` launched from Git Bash did nothing (MSYS
   turned `/c` into `C:/`). **Fix:** `MSYS_NO_PATHCONV=1`; put the command in a script file rather than an inline
   `bash -c` with escaped quotes; log a line at every step.
9. **Bash heredocs written through the agent's shell mangled backslashes** (`\t` became a tab in a Windows path, `\n`
   a newline inside Python source). **Fix:** write scripts and edits with a file-writing tool, not heredocs.
10. **A Blender render step died with a Git Bash fork failure ("Resource temporarily unavailable")** after a long
    unattended chain, leaving unchecked DRMs in the delivery folder. **Fix:** re-run the checks before any deploy; the
    report must describe the bytes actually in the folder.
11. **The PC froze under several parallel Blender/GPU jobs.** **Fix:** a one-slot limiter for heavy jobs (lock file,
    idle priority, half the cores, Blender `-t 8`), and only one workflow at a time on the human's own machine.

## Assets
Garments, gear and textures are the mod's own (Blender bakes; garment pieces cut from the film-style body). The
rebuilt DRMs are whole files: besides the mod's meshes and textures they keep unchanged sections from the vanilla
templates (including original animation clips). So the user's local package is **not** a redistributable release.
To publish, ship only the mod's own data as a patch/installer that rebuilds each DRM from the recipient's own
install (the splice tools already work section by section), and run `um publish check --game <install>` on it.

## Cost and time
Sessions on 2026-10-11 to 2026-10-13 (passes 0.9.0 to 0.9.7), several running unattended overnight.

## Open questions
- A launch from the clean room to confirm the FMVs play through the loader's built-in Bink.
- The 70-row cutscene sweep (every cutscene with the new models) was planned and not run.
