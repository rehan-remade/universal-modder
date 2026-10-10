# MODLOG: Portal 2 portal gun in Outer Wilds

## Intake (2026-10-10)
- Host: Outer Wilds, Steam 753640, buildid 20230391, game version 1.1.16.1372, Unity 2019.4.39f1 Mono,
  Echoes of the Eye installed. No anti-cheat. Saves: `%USERPROFILE%\AppData\LocalLow\Mobius Digital\Outer Wilds`.
- Guest: Portal 2, Steam 620 (Source 1). Only read as an asset source (portal gun viewmodel, textures, sounds).
- Spec agreed with the user:
  - key 5 toggles the gun, in every save, from the first second of each loop, with or without the suit;
  - LMB = blue portal, RMB = orange; equipping another tool puts the gun away;
  - Portal-style portals: see-through, momentum preserved, on any solid surface, parented to the body they hit
    (planets, ship, islands), cleared at loop reset; dream world not required;
  - player, physics objects, the scout probe and the ship can go through;
  - model and sounds converted from the user's Portal 2 install (no Valve files in the repo).
- Done = works in the real game, verified with screenshots + OWML log; field notes + PR (ask before publishing).

## Lab
- Save backup: `um backup create ".../Mobius Digital/Outer Wilds" --name outer-wilds-saves`
  -> `~/.universal-modder/backups/outer-wilds-saves/20261010-012235.zip`. Restore: `um backup restore outer-wilds-saves`.
- Original managed DLLs copied to `~/outer-wilds-decomp/managed-orig` (Assembly-CSharp sha256 0ef96f7f...ace87);
  decompile in `~/outer-wilds-decomp/acs` (ilspycmd 9.1, 1759 files). Never in the repo.
- Outer Wilds Mod Manager 0.15.7 (GUI, `C:\Program Files\Outer Wilds Mod Manager`, silent NSIS `/S`) and its CLI
  `owmods.exe` 0.15.7; `owmods --analytics false setup` installed OWML 2.16.3 to
  `%APPDATA%\OuterWildsModManager\OWML` (manifest: game 1.1.15.1018 - 1.1.16.1388; Steam expects 1.1.16.1372).
  Settings: `%APPDATA%\ow-mods\ow-mod-man\data\settings.json`. OWML patches the game's Assembly-CSharp at launch;
  uninstall = Steam "verify integrity".

## Route
Loader API + managed patching: an OWML mod (C#, `ModBehaviour`, HarmonyX bundled with OWML), plus a Python converter
that reads Portal 2's VPKs (Source MDL v49 + VVD + VTX, VTF, WAV) into a simple runtime format under
`%LOCALAPPDATA%\OWPortalGun`. No community portal gun mod exists for Outer Wilds (searched 2026-10-10).

## Converter (tools/convert.py) - works
- Portal 2 assets: `portal2/pak01_dir.vpk` (VPK v2, 10 archives). Gun: `models/weapons/v_portalgun.{mdl,vvd,dx90.vtx}`,
  MDL v49, 31 bones (`ValveBiped.*`, two roots), 11543 VVD verts; body part 0 (gun) 7242+48 tris, body part 1 = potatOS
  (skipped). 14 sequences at 30 fps (fire1, fizzle, draw, holster, idle 180 f, dryfire, pickup...), no events (sounds
  come from code). Skins: [0..4], [1,..], [2,..] -> skin 1/2 swap `v_portalgun` for `v_portalgun_blue/_orange`.
- VTX in Portal 2 has the extended strip-group (33 B) and strip (35 B) headers; reader tries both.
- Axis map Source -> Unity: (x,y,z) -> (-y, z, x), inches * 0.0254. det = -1 but winding did NOT need flipping
  (normal vote). Bind poses = converted `poseToBone`. Viewmodel origin = eye.
- Textures VTF 7.2-7.5 (DXT1/5 via Pillow "bcn", BGR888, BGRA8888). All 28 WAVs are PCM16.
- Software render of idle frame 0 matched Portal 2's framing before touching the game.

## Game facts learned (decompile + runtime)
- Player camera: `PlayerCamera`, deferred, HDR, near 0.1, far 50000, fov 70; OWCamera renders the skybox from a command
  buffer (`SkyboxRenderer.activeSkyboxRenderers`), `clearStencilAfterLightingPass = true` -> stencil free in forward.
- Tools render with `Outer Wilds/Utility/View Model (Cutoff)` + `View Model Prepass` on layer `VisibleToPlayer`
  (cloned from the Signalscope renderers); `_VIEWMODEL_OVERRIDE` + `_ViewmodelMatrixVP` (fixed viewmodel fov 70).
- Shaders available by name: Standard, UI/Default, Sprites/Default, Legacy Shaders/Particles/Additive.
- Input: TOOL_PRIMARY (= probeLaunch) equips the scout launcher when nothing is held -> consume it in a
  `ToolModeSwapper.Update` prefix. Key 5 is only read by ScreenshotController together with the screenshot key.
- ToolModeSwapper keeps reporting the old tool mode until it has finished stowing it.
- Player ground detection is a SphereCast validated in `PlayerCharacterController.IsValidGroundedHit` - IgnoreCollision
  doesn't affect it; postfix it to drop hits inside the portal hole.
- Unity forgets IgnoreCollision when a collider is re-enabled (player's anti-sinking collider) -> re-apply every step.
- `PlayerBody.WarpToPositionRotation` fires "WarpPlayer" (trigger volumes re-evaluate) and "PlayerRepositioned"
  (CenterOfTheUniverse recentres). `ShipBody.SetPosition/SetRotation` carry a player walking inside the ship.
- Mono enforces field access at JIT time even when compiling against the publicized OuterWildsGameLibs: private
  fields (e.g. `TitleScreenManager._resumeGameAction`) need reflection, or the whole calling method fails to JIT.

## Dev bridge (test oracle) - how to drive a run without touching the user's input
- `dev.enabled` in the mod folder; commands in `dev_commands.txt`, results in `dev_log.txt`, screenshots in `shots/`.
- Start sequence that works: `waitfor profiles` -> `profile PortalLab` (TryCreateProfile/SwitchProfile) -> `resume`
  (resume action: SetSceneToLoad(GAME) + ConfirmSubmit by reflection, then LoadManager.EnableAsyncLoadTransition
  because the hidden button's Update normally does it) -> `waitfor wakeready` -> `wake` (what the "[E] Wake up"
  prompt does) -> `waitfor control`.
- Dead ends: LoadSceneAsync straight from the title before profiles initialise = NREs and input stuck at None;
  TryCreateProfile before init = NRE (_profiles null); resume on a 1-loop save opens "are you sure?"; new-game action
  resets the save (never used).

## Verified in game (2026-10-10, PortalLab profile, loop 1, Timber Hearth village)
- Gun appears with the game's viewmodel shading, draw animation, skins switch blue/orange on firing.
- Portals placed on BatchedMeshColliders_5 (TimberHearth_Body), rims animate, closed (static) until both exist,
  then each shows the other side (stencil + oblique camera).
- Walking onto a floor portal: falls in, exits the other floor portal upwards, endless Portal-style loop
  (rel speed 6.5 -> 6.3 -> 5.4 m/s), player upright, view continuous.
- Bugs found and fixed: equip key parsed as LeftCtrl (Key.Digit0 is after Digit9); stowed probe got teleported
  (only launched probe travels now); player came out upside down (now upright for exit gravity, eye kept on the
  mapped point); hovering over floor portals (ground cast filter).

## Session 2 (same night): walls, ship, scout, input, HUD, performance
- Wall portals were mostly rejected on rock: new fit = 16 samples, averaged plane, <= ~1 m unevenness (35 % of height
  for ship size), retry samples from 3x higher (start points inside hills see nothing), portal on the most protruding
  sample, every collider under the portal recorded (`Portal.Walls`).
- Wall->floor exit lost its speed: removed the planar "frame" collider (it caught the capsule at the rim) and made the
  ground filter reject every hit behind the plane inside the ellipse. Exits now keep speed (in 2.5 -> out +2.5 m/s).
- After a player warp: MakeUngrounded + `_wasGrounded=false` + `_lastJumpTime=now` (no ground snap into the caves),
  eye placed 3 cm in front of the exit, crossing test `prev.z >= 0`, prev sample frozen during the 0.15 s cooldown.
- Ship: ignore zone scaled by body radius (ship 7.6 m); bodies bigger than the portal also ignore the static ground of
  the same body within reach. Dropped 30 m into a person-size floor portal -> out of a wall portal at 25.8 m/s.
  (The village clearing has a tree canopy; big 8x13 m floor portals don't fit Timber Hearth's slopes/lake edge.)
- Scout: anchors via its own raycast (`ProbeAnchor.AnchorToObject`) -> prefix sends it through. 48 m/s floor->wall.
- Loop reload (`LoadManager.ReloadSceneAsync`): portals gone, gun re-added and usable.
- Real input with the user's OK (um win drive, SendInput): key 5 equip/holster, left click blue, right click orange,
  scout launcher not taken out, wheel message. OW binds right mouse = tool primary, left = lockOn, R = tool secondary;
  the gun reads Mouse.current directly and consumes those in prefixes.
- HUD: Portal 2 crosshair (IMGUI, atlas cells of 42 px at +3) and messages in English/Spanish by game language;
  OW's NotificationManager only shows on the helmet HUD.
- Holster only when hands are busy (console, conversation, dream world, death, game tool out); menus/map just ignore
  input.
- Performance at 3440x1440: 121 FPS without portals, 69 with one portal view at full screen, 93 after scissoring the
  view camera to the portal's screen rect (82 with both portals visible).
- Lint: `um publish check` PASS against both games. Repo tests: 76 passed, 1 failed (`test_compile_small_edl`,
  WinError 6 from ffmpeg in this environment; um/ untouched).

## Not verified
Loose physics props (none free in the village; same code path as the ship), moving islands / Brittle Hollow fragments,
other planets, gamepad buttons, other resolutions, portals while the player rides inside the ship.

## Cleanup on the user's machine
- Lab profile `PortalLab` in `SteamSaves` (Steam cloud) - ask before deleting. User's `Laraa` save untouched
  (data.owsave still dated 2025-10-29). Backup: `~/.universal-modder/backups/outer-wilds-saves/20261010-012235.zip`.
- `dev.enabled` removed from the mod folder after testing. OWML + Mod Manager stay installed (requested).
