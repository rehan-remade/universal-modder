---
kind: game
title: Porting a skinned StarCraft II character onto the SWBF2 (2005) infantry skeleton
game: 'Star Wars: Battlefront II (2005)'
games_also: ["StarCraft II"]
game_version: "Steam appid 6060, buildid 6217431 (post-2017 GOG Galaxy multiplayer build, menu shows v1.1); StarCraft II 5.0.17.98310"
platform: windows
engine: native
route: data
tools: ["SWBF2 Mod Tools SDK 2020 (ModDB repack of the Pandemic mod tools)", "Blender 4.5.9 LTS + Blender 5.2", "SWBF-msh-Blender-IO 1.5.3 (Calrissian97 fork)", "m3studio (Solstice245, commit bef1b08)", "CascLib .NET (WoW-Tools/CASCExplorer, built for net8.0)"]
anti_cheat: "none; tested only in single-player Instant Action, nothing touches online play"
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-12'
links: []
tags: [zero-engine, character-port, skinning, retarget, msh, m3, casc, localization, addon]
---
# Porting a skinned StarCraft II character onto the SWBF2 (2005) infantry skeleton

> A private, personal mod for Star Wars Battlefront II (2005, Steam): a StarCraft II "story mode" Marine model,
> read from the player's own SC2 install, replaces the basic clone trooper on a stock map, fully animated by the
> stock `human` animation bank. Route: data/addon (official mod tools + Blender), no game file modified.
> Verified in the real game (Instant Action, spawn screen and 3rd-person screenshots, running/strafing/aiming).
> No assets are shared here, only the method. The converted Marine is Blizzard's model and textures, so the addon
> stays on the user's own machine (see Assets).

## Setup
- SWBF2 Steam appid 6060, buildid 6217431 (`Galaxy.dll` present = the 2017 GOG Galaxy multiplayer update).
  `um scan` does not recognise the Zero Engine ("Unknown native engine") and proposes a native-hook route: ignore
  it, the community route is the official mod tools + `GameData\addon\<3-letter ID>\`.
- Mod tools: "SWBF2 Mod Tools SDK 2020" (ModDB, `BF2_ModTools.1.zip`, 562 198 681 bytes, MD5 published on the
  page). ModDB blocks scripted downloads (HTTP 403), a real browser works. Extract to `C:\BF2_ModTools` (no
  spaces, short path: the zip holds 18k files, 1.4 GB).
- Blender: `SWBF-msh-Blender-IO` 1.5.3 (Calrissian97 fork; it states Blender 5.0+ support) for .msh import/export.
  `m3studio` (no releases, use the repo) for StarCraft II .m3 import: **it does not run on Blender 5.x**
  (about 20 lines use `Action.fcurves`, which Blender 5.0 removed), so a portable Blender 4.5 LTS is needed for
  the m3 side.
- Reading SC2 data: CASC storage with an MNDX root. `CascView` is GUI-only; the .NET `CascLib` from
  WoW-Tools/CASCExplorer supports SC2 (`CASCGameType.S2`) and builds for net8.0 with
  `-p:TargetFrameworks=net8.0` (pass a NuGet source explicitly if none is configured).

## Route and why
Data/asset route. A new side lvl containing one class whose `ClassParent` is the stock clone class, loaded by a
custom mission (stock world + stock sides + the new side) registered from `addme.lua`. Everything lives in the
addon folder; nothing in `GameData\data` is touched. A native route makes no sense here: the toolchain already
does everything.

Other ports of a skinned character onto a host skeleton in the KB: the per-bone fit onto Risk of Rain 2's Commando
rig (`games/risk-of-rain-2/helldiver-survivor.md`) and Halo 3 characters rigid-skinned to their dominant bone
(`games/halo-3-mcc/halo-3-weapons-covenant-vehicles-and-maps-ported-into-minecr.md`).

## How the game works (what we had to learn)
- **Class inheritance across lvl files works at runtime.** `ReadDataFile("dc:SIDE\\scb.lvl", "<class>")` after
  `ReadDataFile("SIDE\\rep.lvl", ..., "rep_inf_ep3_rifleman", ...)`: a class whose `ClassParent` is
  `rep_inf_ep3_rifleman` inherits weapons, sounds, animation bank, etc. The side lvl only carries the odf, the
  .msh files and the textures (9 MB). Load the parent lvl first.
- **Infantry skeleton** (from `rep_inf_ep3trooper.msh`): 43 bones (`bone_root`, `bone_pelvis`,
  `bone_a_spine`/`b_spine`/`ribcage`, `bone_neck`/`head`, `bone_{l,r}_{clavicle,upperarm,forearm,hand,thigh,calf,
  foot,toe}`, `hp_weapons` + `root_*`/`eff_*` helpers). Bind pose is a **T-pose facing +Y** (in Blender after
  import), 2.08 m tall. The animations drive the bone translations too, so a new mesh must match the clone's
  proportions; you cannot ship a bigger skeleton for the `human` bank.
- **Skinning**: the clone mesh uses exactly one bone per vertex (21 vertex groups). The msh addon docs note that
  SWBF2 PC only appears to honour one weight; rigid skinning to the dominant bone works fine for armour.
- **Soldier .msh.option**: `-lodgroup soldier -nocollision` (the clone also has `-keepmaterial override_texture`).
  `GeometryLowRes` in the odf points to a second, low-poly msh.
- **Localization files** (`Common\Localize\<lang>.cfg`): nested `VarScope("...")` blocks with `VarBinary("key")`
  entries holding `Size(n)` and `Value("hex")` lines (64 hex digits per line). The payload is a 4-byte prefix
  followed by UTF-16LE text, `Size` counts both, and every byte is written as two hex digits **with the nibbles
  swapped** (0x53 -> "35"). What the prefix holds varies: this port found the first 4 letters of the top-level
  scope (`enti`, `mapn`, `leve`), while community cfg files (e.g. the Gametoast un-official patch's
  `CustomLVL/localize/English.cfg`) have `00000000` or small integers there. Keys: unit name
  `entity.<side>.<rest of class name>` (class `scb_inf_marine` -> `entity.scb.inf_marine`), map name
  `mapname.name.<map id>`, `mapname.description.<map id>`.
- **SC2 story-mode models** (`Assets/StoryModeCharacters/...`): control bones `<PREFIX>Ctrl_<Joint>_SkinPoint`
  (prefix varies per model, e.g. `MPT_` vs `MR3_`), up to 4 weights per vertex, ~0.8 units tall, A-pose. They do
  **not** share a facing (one looked down -Y, another down +X). Their diffuse **alpha is not team colour**: the
  material binds it as an ambient-occlusion layer read through the **second UV set (UV1)**. Normal maps store X
  in alpha and Y in green. The m3 importer adds an `EDGE_SPLIT` modifier on every mesh.

## Build steps
1. Copy `BF2_ModTools\data` to `data_<ID>` and the `TEMPLATE` folder into it, replacing `@#$` with the ID in file
   names and contents (what VisualMunge does). Fix the localization files (Gotcha 2).
2. Mission: copy the stock mission script you want (mod tools `assets\scripts\<world>\`), add the new side read
   and swap the class in `SetupTeams`. `Common\mission.req` lists it under `"lvl"`. `addme.lua` adds a
   `sp_/mp_missionselect_listbox_contents` entry and `AddDownloadableContent("<ID>", "<mission>", 4)`.
3. Side: `Sides\<ID>\odf\<class>.odf` (`ClassParent`, `GeometryName`, `GeometryLowRes`, movement tweaks),
   `req\<class>.req` (`"class"`), `<ID>.req` (`"lvl"`), msh + tga; `_BUILD\Sides\<ID>\munge.bat` =
   `@call ..\munge_side.bat <ID> %1`.
4. Character conversion in Blender 4.5 (scripted):
   - import the m3 with rig; keep the body pieces by their M3 material name, drop rifle/flare meshes;
   - rotate the rig so ankle->toe points +Y (snap to 90 degrees), scale ~2.5;
   - on the SC2 pose bones: `COPY_LOCATION` to the matching clone bone heads, `STRETCH_TO` (no volume) per limb
     segment, `inherit_scale = NONE` on every bone, shoulder pads without rotation inheritance, a `DAMPED_TRACK`
     on the wrists along the clone forearm; lift ankle/toe targets per side until each sole is at z = 0;
   - bake the evaluated meshes in world space, carry corner normals over as custom normals, assign each vertex to
     one BF2 bone from its dominant SC2 group (pads -> clavicle, fingers -> hand, helmet/visor -> head);
   - parent to the clone `skeleton`, delete the clone body and its `sv_` mesh, export with triangle strips on and
     modifiers off. Low LOD: decimate ~0.08, then re-rigidify the weights.
5. Textures: Cycles `EMIT` bake into UV0 of `diffuse.rgb(UV0) * diffuse.a(UV1)`, then multiply in a fixed key
   light computed from the normal map, put the specular map in alpha, 1024 x 1024 TGA.
6. Munge: `munge.bat /COMMON` and `munge.bat /SIDE <ID>` from `data_<ID>\_BUILD` (Gotcha 1), scriptmunge
   `addme.lua -platform pc`. Copy `addme.script`, `_LVL_PC\mission.lvl`, **`_LVL_PC\core.lvl`** and
   `_LVL_PC\SIDE\<id>.lvl` into `GameData\addon\<ID>\` (+ `data\_LVL_PC\...`).

## Verification
- In Blender before munging: apply stock `.msh` animations (`human_0\human_rifle_stand_runforward.msh`, shoot,
  sprint) to the converted rig with the addon's "Import Animation(s)" and render frames. Control: the same
  harness on the stock clone msh, so a broken render is known to be our mesh, not the harness. Round-trip:
  re-import the exported .msh and animate it again.
- In game: retail exe windowed (`/win /resolution 1280 720`, or via `steam://rungameid/6060`), Instant Action,
  screenshots of the spawn screen (front view) and of 3rd-person running/strafing. The new map name and the
  French UI strings were read off the screenshots.
- Not verified: performance with many units on screen beyond a short playtest, multiplayer, shadow volumes,
  normal-mapped rendertypes on skinned soldiers.

## Gotchas
1. **`munge.bat` "is not recognized" although it exists.** **Cause:** the environment had
   `NoDefaultCurrentDirectoryInExePath=1`, so cmd does not run programs from the current folder and every nested
   `call munge.bat` fails. **Fix:** `cmd /c "set NoDefaultCurrentDirectoryInExePath=&& cd /d ...\_BUILD && munge.bat /COMMON ..."`.
2. **mission.lvl builds but does not contain your mission; log shows "Could not open munged\pc\core.files".**
   **Cause:** in the SDK 2020 repack, the six `Common\Localize\<lang>.cfg` files (english, french, german,
   italian, spanish, uk_english) lack the final closing `}`, localizemunge fails, core.lvl is not packed, and
   every mission levelpack that uses `-common core.files` is skipped. **Fix:** append `}` to each file (count the
   braces first).
3. **Re-munging does not fix a broken output.** **Cause:** `-checkdate` keeps the earlier failed outputs
   (8-byte core.lvl/common.lvl). **Fix:** delete `_BUILD\Common\MUNGED` and `_LVL_PC` (and the side's `MUNGED`)
   before rebuilding.
4. **Every text in an addon mission shows as raw keys (`ifs.SpawnDisplay.Spawn`, `0x1274B8E0`, `[NULL]`)** while
   stock maps are fine. **Cause:** the addon shipped no `core.lvl`; VisualMunge normally copies one.
   **Fix:** copy the munged `_LVL_PC\core.lvl` (it contains every language from the mod tools localization plus
   your own keys) to `addon\<ID>\data\_LVL_PC\` and add
   `ReadDataFile("..\\..\\addon\\<ID>\\data\\_LVL_PC\\core.lvl")` at the top of `addme.lua` for the menu.
5. **The mod tools' `BF2_modtools.exe` (debug console + `BFront2.log`) asks for "CD 1" with the Steam install.**
   We didn't work around the disc check: that would be a DRM bypass. **Fix:** test with the retail exe and
   screenshots instead. The game rewrites `GameData\bf2cmd.txt` with its command line on every
   launch (original content was a lone CRLF): restore it if you keep a manifest of the game folder.
6. **Launching `BattlefrontII.exe` directly sometimes exits silently** (Steam relaunch). **Fix:**
   `steam://rungameid/6060`; the window mode/resolution from a previous `/win` launch was remembered.
7. **Menus ignore synthetic mouse clicks.** **Cause:** DirectInput mouse with its own cursor. Relative moves
   (`rel dx dy`) move the game cursor 1:1 and a click only lands when the game cursor is already on the target;
   Enter works with scancode input. **Fix:** let the human click through Instant Action, or navigate with
   relative moves.
8. **Converted character animates with long spikes everywhere.** **Cause:** the m3 importer's `EDGE_SPLIT`
   modifier changes vertex count/order (2 758 -> 2 764, 245 -> 287), so dominant-bone lookups done on the source
   mesh indices were shifted. **Fix:** read the vertex groups from the **evaluated** mesh
   (`bpy.data.meshes.new_from_object(..., preserve_all_data_layers=True)` keeps the deform weights).
9. **"Camouflage" blotches on the armour in game.** **Cause:** the SC2 story-mode diffuse alpha was treated as a
   team-colour mask; it is ambient occlusion bound to UV1, so sampling it with UV0 makes random patches.
   **Fix:** bake `rgb(UV0) * alpha(UV1)` into UV0 (Cycles emission bake) and drop team colour. Also check the
   actual RGB before choosing a model: one story Marine was steel-grey, another blue.
10. **Model faces backwards after conversion.** **Cause:** SC2 story models are not all oriented the same way.
    **Fix:** compute the facing from ankle -> toe bone heads instead of a fixed 180 degree turn.
11. **Hands sink into the chest and the legs rub when running.** **Cause:** a bulky armoured mesh driven by the
    slim clone's animations. **Fix (partial):** flatten the front of the torso (~70 %), slim forearms/gauntlets
    across the limb axis (~85 %), slim only the inner half of each leg (~70 %) and push the legs outwards a few
    cm. Too much leg slimming made the legs look thin; small residual contacts remain.
12. **`git clone` / portable Blender fail in the agent's working folder** ("Filename too long", "$GIT_DIR too
    big", "side-by-side configuration is incorrect"). **Cause:** a desktop app's sandboxed scratch folder was
    redirected to a very long path. **Fix:** move the project to a short real path (e.g. under Documents).
13. **`um scan` misdetects StarCraft II as a .NET game** (because of a third-party campaign launcher in the
    folder). Harmless for read-only extraction.

## Assets
All art comes from the user's own StarCraft II install (read-only, never redistributed): one story-mode character
model and its body textures, converted as described above. No generated assets. The converted model and textures
are still Blizzard's, so keep the built addon private: don't upload it (ModDB, Nexus) or hand it to other players
for a multiplayer match. A shareable version needs original art in its place. Movement was tuned in the odf
(MaxHealth 550, MaxSpeed 6, MaxStrafeSpeed 4.5, MaxTurnSpeed 4, JumpHeight 1.1, Acceleration 30,
SprintAccelerateTime 0.6; stock values live in the mod tools' `data\Common\odfs\com_inf_default.odf`).

## Cost and time
About 4 h 35 for the first character including tool setup and three visual iterations; the pipeline is now
scripted.

## Open questions
- Weapon: the character still holds the clone rifle; a custom weapon msh and the grip pose are next.
- Shadow volume (`sv_`) and normal-mapped rendertypes on skinned soldiers were not tried.
- Converting the SC2 model animations into SWBF2 animation banks would remove the residual clipping and unlock
  non-humanoid creatures; not attempted yet.
