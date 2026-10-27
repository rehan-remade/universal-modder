---
kind: game
title: Mollie Macaw's chase from Indigo Park (UE 5.2) as a Minecraft 1.20.1 Fabric mob, from your own install
game: Indigo Park
games_also: ["Minecraft Java Edition"]
game_version: "Indigo Park Chapter 1, Steam app 2504480, project RaccoonCh1, UE5+Release-5.2 (install of 2026-10-25); Minecraft 1.20.1 + Fabric Loader 0.20.1, Fabric API 0.92.12+1.20.1"
platform: windows
engine: unreal
route: loader-api
tools: ["CUE4Parse 1.2.2 + CUE4Parse-Conversion 1.2.1 (.NET 8)", "RE-UE4SS v3.0.1 (mappings dump only)", "Epic-signed oo2core_9_win64.dll from a local UE 5.7 install", "Fabric Loom 1.7.4 / Gradle 8.10.2 on Java 17 (Mojang mappings)", "Python 3.12 + numpy + pillow (uv)"]
anti_cheat: "None. Single-player, offline. The game was launched once with UE4SS to dump mappings, then restored."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: '2026-10-26'
links: ["https://github.com/FabianFG/CUE4Parse", "https://github.com/UE4SS-RE/RE-UE4SS", "https://github.com/vgmstream/vgmstream", "https://fabricmc.net"]
tags: [content-port, mashup, unreal5, iostore, oodle, usmap, cue4parse, kismet, pawnsensing, ai-moveto, actorx, psk, psa, skinning, fabric, chase-ai, jumpscare, totem]
---
# Mollie Macaw's chase from Indigo Park (UE 5.2) as a Minecraft 1.20.1 Fabric mob, from your own install

> A Fabric 1.20.1 mod adds Mollie Macaw as a spawn-egg mob. Her model, textures and clips (run, crawl, jump,
> fall, land, jumpscare) are converted from the user's own install into a local resource pack. Her chase AI
> is rebuilt from the game's Blueprint bytecode: PawnSensing sight, a cone with a blind spot behind, a random
> long-range skip, line of sight, MoveTo that follows the player out of sight, and an oriented catch box.
> The rebuild runs on Minecraft pathfinding. A catch kills instantly with a custom death message, and a
> held totem teleports the player out of her sight range. Verified by 11 server gametests, 3 JUnit tests and
> a scripted dev-client run with in-game screenshots.

## Setup
- Windows 11.
- Indigo Park on Steam. In this case the Steam library folder was literally named ``Steam` `` (with a
  backtick); `um scan` didn't match the path until it was passed exactly.
- Paks: `RaccoonCh1/Content/Paks/RaccoonCh1-Windows.{pak,utoc,ucas}` (IoStore, 8.6 GB ucas) and
  `global.utoc`.
- .NET 8 SDK 8.0.427.
- CUE4Parse **1.2.2** with CUE4Parse-Conversion **1.2.1**. Releases from 1.2.2.2026xx target **net10.0** only.
- Prism's bundled Microsoft OpenJDK 17.0.15 includes `javac`, which is enough for Loom 1.7.4. Current Loom
  (1.18+) needs Java 25. The 1.20.1 branch of fabric-example-mod has moved to Loom 1.19 and Gradle 9.8, so
  pin Loom 1.7.4 and Gradle 8.10.2 yourself.

## Route and why
This is Pattern 1 of mashup-mods (port the content), the same as the
[Halo 3](../halo-3-mcc/halo-3-weapons-covenant-vehicles-and-maps-ported-into-minecr.md) and
[Left 4 Dead](../left-4-dead/left-4-dead-infected-and-tank-in-minecraft.md) notes:
- Minecraft is the host.
- The game is only a data source.
- The mod ships code only.

A UE-side mod or passthrough wasn't needed: the user wanted the characters in Minecraft.

## How the game works (what we had to learn)
**Archives**
- The IoStore TOC has the encryption flag off and a zero key GUID, so there is no AES key.
- **Every compressed block is Oodle.**
  - CUE4Parse 1.2.2's own download of `oo2core_9_win64.dll` (Warframe's CDN, then a third-party OodleUE build
    on GitHub) failed silently: `DownloadOodleDll` returns false instead of throwing, leaving an empty
    `oodle/` folder.
  - The local UE 5.7 install has an Epic-signed copy at
    `Engine/Binaries/DotNET/UnrealBuildTool/oo2core_9_win64.dll` (other engine versions weren't checked).
    Point `OodleHelper.Initialize` at it.

**Mappings and code**
- **The packages use unversioned properties**, and nobody had published a `.usmap`.
  - A minimal UE4SS 3.0.1 install produced one in 20 s: the two DLLs, `MajorVersion=5` /
    `MinorVersion=2`, `GuiConsoleEnabled=0`, and a Lua mod calling `DumpUSMAP()` from
    `ExecuteWithDelay(20000, …)`.
  - Then remove UE4SS and compare `Binaries/Win64` with a listing taken beforehand.
- **Blueprint-only project.** The exe has no `/Script/RaccoonCh1` classes, and there are no Behavior Trees or
  Blackboards.
  - The AI lives in BP event graphs.
  - `provider.ReadScriptData = true` makes CUE4Parse keep Kismet bytecode. Without it, `ScriptBytecode`
    serialises empty.
  - A 150-line pretty-printer over the JSON (`EX_LetObj`, `EX_CallMath`, `EX_JumpIfNot`, `EX_PushExecutionFlow`
    and so on) was enough to read the graphs.

**Where Mollie's chase lives**
- `/Game/BirdBPs/BP_MollieTube`, a `Character`:
  - `PawnSensing.OnSeePawn` → `AI MoveTo(TargetActor=player, AcceptanceRadius=5)` plus a 0.6 s
    `RetriggerableDelay` "can see" flag.
  - Catch: a `BoxComponent` (`EnemyCollisionMesh`) begin-overlap fires `JumpscareRedirect`, and the level
    script runs the kill screen.
- The `ChaseScene` level script also plays Level Sequences (cutscene set pieces) from trigger boxes, and sets
  `InPipe` (0/100) for the run/crawl blend space.

**Engine defaults matter.** Unversioned assets only store non-default values. Read the absent ones from engine
source; a launcher install has `Engine/Source/Runtime/...`.
- PawnSensing:
  - SightRadius 5000 and SensingInterval 0.5.
  - `CouldSeePawn` skips a check with probability 1 − 0.4R/d beyond 0.4R.
  - `InitializeComponent` recomputes the cone cosine from `PeripheralVisionAngle`. Mollie's is 585.9°, which
    gives cos −0.696, a 268° cone with a blind spot behind.
- `AController::LineOfSightTo` traces eye → target centre, then eye → top of capsule.
- MoveTo to an actor calls `SetGoalActorObservation(goal, 100)`. The path follows the player and repaths when
  they move 100 cm, so losing sight doesn't stop the chase. Only a failed or finished path does.
- Unversioned defaults also hid the player's speeds. Walk 300 and sprint 620 cm/s are on the player BP's
  default object, while Mollie's `MaxWalkSpeed` is 300: she moves exactly as fast as you walk.

**ActorX (PSK/PSA) from CUE4Parse-Conversion**
- 16-byte wedges with 16-bit point indices plus padding when there are ≤ 65,536 points.
- REFSKELT bones are 120 bytes. ANIMINFO is 168 bytes. ANIMKEYS are pos(3), quat(4), time.
- **Child-bone quaternions must be conjugated, the root's not.** The test that told the conventions apart was
  pose bounds: a "WingsIN" run clip only came out narrow with the right convention. The edge-stretch test
  could not separate them.
- The Y axis is mirrored against the engine.
- **Triangles are wound clockwise.** The reflection to Minecraft axes, (−x, z, −y), already makes them
  counter-clockwise. Check face normals against `VTXNORMS` rather than guessing.
- Cooked base Materials export as empty JSON. Read texture references from the material package itself
  (`Texture2D` imports), and flat colours from `CachedExpressionData.VectorValues`.

**Sounds**
- Audio comes out as `.binka` with magic `ABEU`, which is `UEBA` read little-endian.
- The header layout is in the UE install, at
  `Engine/Source/Runtime/BinkAudioDecoder/SDK/BinkAudio/Include/binka_ue_file_header.h`. It is 28 bytes:
  - tag, version u8, channels u8, pad u16
  - rate u32, sample_count u32
  - max_comp_space u16, flags u16 (BA2)
  - file_size u32, seek_entries u16, blocks_per_seek_entry u16
- Then come the u16 seek deltas, then blocks with a `0x9999` magic and a u16 size. Size `0xFFFF` means a
  trimmed block: it is followed by u16 size and u16 sample count.
- **FFmpeg 9.0.2 (gyan.dev build) can't decode it.** Its `binka` demuxer only knows RAD's `1FCB` layout and
  reads the padding as a 16-bit sample rate ("Invalid sample rate: 0").
- FFmpeg master has a `UEBA` branch (committed 2026-09-25, so not in 9.0.x). It passes extradata `'2'` so
  `binkaudio_dct` uses the Bink Audio 2 bitstream (7-bit quantiser indices). Rewriting only the header to
  `1FCB` would therefore decode BA2 frames as BA1.
- **vgmstream r2117 decodes them** (`ueba.c`, BINKA codec). All 21 files came out with exactly the header's
  sample count (48 kHz voice lines, 44.1 kHz effects). An auto-mode safety classifier refused to let the
  agent run the unsigned vgmstream exe, so the user ran the decode script. The UE SDK folder also has Epic's
  decoder source and static libs, if a compiler is available.
- Convert to **mono** OGG for Minecraft, so sounds attenuate with distance. Bake in the game's PlaySound2D
  volume multipliers where there is headroom: Minecraft volumes above 1 only extend range.

## Build steps
1. **Extract.** `ipextract <paks> export <out> <packages…>` (our own small console app on CUE4Parse, not
   published) writes the mesh as PSK, clips as PSA, textures as PNG and audio raw. `json` dumps any package
   with bytecode.
2. **Convert.** The PSK/PSA go into one `.ipm` file:
   - vertices with up to 4 weights,
   - per-material index lists,
   - per-clip, per-frame 3×4 skin matrices already in Minecraft axes, in game cm.

   This goes into a resource pack (`pack_format` 15) with the textures. 3.4 MB for a 25k-triangle,
   100-bone character with 7 clips.
3. **Mod.**
   - A `Monster` subclass does sensing on a random-phase interval and the MoveTo-like chase (repath beyond
     100 cm × scale, stop when the path ends). Every tick it checks for players overlapping the oriented catch
     box.
   - The renderer is a plain `EntityRenderer`. It does CPU skinning per frame and emits each triangle as a
     degenerate quad into `entityCutoutNoCull`.
   - Animation copies UE's 1D blend space: a shared normalised phase weighted by rate / length, and a crawl
     weight easing at 2.0/s.
4. **Scale.** Distances use the player-height ratio (game player 2.59 m vs 1.8 blocks, k = 0.695). Speed is
   matched relative to player walk speed. Clip rate follows actual ground speed, so the feet stay planted.

## Verification
- **Gametests (11/11).** These use a survival `ServerPlayer` subclass placed with
  `placeNewPlayer(new Connection(SERVERBOUND), p)`. The built-in mock player is creative. Tests:
  - sight in front, blind spot at 180° vs 120°, beyond the radius, through a wall, creative ignored
  - measured chase speed, catch kills (damage type and message), armour/resistance/absorption don't help
  - totem teleport ≥ sight radius, keeps chasing out of sight round a wall, gives up on an unreachable
    hidden player
- **Dev-client harness (6/6):**
  - creates a flat world with `createWorldOpenFlows().createFreshLevel`
  - films idle, run, crawl under a 0.625-high ceiling and the jumpscare clip
  - a real survival catch with the "was caught by Mollie Macaw" death screen
  - a real totem save
- The sound manager check passes: all 4 events resolve to the converted OGGs.
- The user launched the Prism instance with the mod installed.
- Not verified: a dedicated server, and how the sounds actually sound (an agent can't listen).

## Gotchas
1. **`um scan "<path>"` said no game matches.** **Cause:** the Steam library folder name contains a backtick
   (``Steam` ``). **Fix:** use `um scan --list` to see the real path. In PowerShell use `-LiteralPath`
   (backtick is PowerShell's escape character).
2. **`OodleException: not initialized`.** **Cause:** CUE4Parse's automatic Oodle download wrote nothing.
   **Fix:** use the signed DLL from any local UE install. An auto-mode safety classifier also refused to load
   a third-party Oodle build from GitHub, which is another reason to prefer the vendor copy.
3. **`Package has unversioned properties but mapping file is missing`.** **Fix:** dump a `.usmap` with UE4SS
   (`DumpUSMAP()`), then uninstall UE4SS.
4. **Every Blueprint function had empty bytecode in JSON.** **Fix:** set `provider.ReadScriptData = true`
   before `Initialize()`.
5. **`BP_MollieAnimatronic` looked like the enemy but is set dressing.** **Cause:** a scene root plus meshes,
   no movement component. **Fix:** find the `Character` BPs referenced by the chase level's actors.
6. **Most chase-named assets are Level Sequences** (`MollieChase`, `MollieChasePart2` and so on), not AI.
   **Fix:** read the level script to see what triggers what, and port only the AI pawn.
7. **The mesh rendered inside out** (face normals 0% outward). **Cause:** ActorX winds triangles clockwise and
   the axis change is a reflection. **Fix:** keep the file's order (the reflection flips it). Check against
   vertex normals.
8. **The jumpscare clip stopped early on the client.** **Cause:** the client compared the server's synced
   `tickCount` at the catch with its own `tickCount`, and the busy integrated server ticked slower. **Fix:**
   store the client's own tick in `onSyncedDataUpdated` when the catch value arrives.
9. **Harness screenshots showed a creative inventory and a turned camera.** **Cause:** the dev-client window
   on the user's desktop got key and mouse input. **Fix:** release the mouse and close non-death screens every
   tick, then shoot on a later tick.
10. **A harness "after the tunnel" check failed.** **Cause:** the move target was off the snow-layer floor
    that made the low tunnel, so the path ended inside it. **Fix:** extend the floor past the tunnel.
11. **The death message read back in a gametest as "… died".** **Cause:** `die()` resets the combat tracker.
    **Fix:** rebuild it from `getLastDamageSource().getLocalizedDeathMessage(p)`. The server broadcast was
    correct.
12. **Speed came out 2% slow (4.229 b/s) at the formula's attribute.** The formula is 44.05·s² b/s for a mob
    on normal ground, with zza = speed and moveRelative(speed). **Cause:** path following. **Fix:** measure
    in a gametest and scale the attribute by √(target/measured). The result was 0.3162 → 4.316 b/s.
13. **`@GameTest(templateNamespace=…)` doesn't compile on 1.20.1.** **Fix:** use
    `template = FabricGameTest.EMPTY_STRUCTURE`. Also, a record component can't be named `wait`.
14. **Loom's test source set had no Minecraft classes with `splitEnvironmentSourceSets()`.** **Fix:** add
    `sourceSets.main` compile and runtime classpaths to `sourceSets.test`.

**Resizing a ported mob.** The user then asked for Mollie at 2.5 × the player.
- Keep two scales: one for her body (model, hitbox, eyes, catch box) and one for distances (sight, repath).
  Keep speed matched to the player.
- Measure pose heights from the converted clips (idle 119.6, run 125, crawl 96 cm) rather than the bind pose.
- Gametests written for a small mob broke in useful ways:
  - A 4.3-block catch reach caught a "seen at 120°" player before the assertion ran.
  - A larger mob followed paths about 6% slower: 4.05 b/s, then 4.38 after recalibrating.
  - **Minecraft's A\* ran out of nodes on a 40-block detour round a wall.** Unreal's navmesh MoveTo would
    have found it. Raising FOLLOW_RANGE to 64 and `setMaxVisitedNodesMultiplier(3)` fixed it.
- The small-mob version had passed only because it caught the player before the detour mattered.
- Mojang mappings expose `getStandingEyeHeight(Pose, EntityDimensions)`. Without it a mob's eyes default to
  85% of the hitbox height.

## Assets
All Indigo Park assets are converted on the user's machine from their install. The mod jar contains code,
lang, damage-type data and a `sounds.json` that points at vanilla sounds as placeholders.

The resource pack is Indigo Park's own model, textures, clips and sounds, converted, so it stays private to
that machine: never in the jar or git, never in a modpack, and never served as a server resource pack. To
share the mod, ship the jar and the converter, and have each player build the pack from their own install
(Chapter 1 is free on Steam).

## Cost and time
One session of about 1.5 hours wall-clock, including one stop for the user to choose how to get mappings.

## Open questions
- Lloyd the Lion (skipped for now). Chapter 1 names (`la_lloydShelves*`, `LloydHides`,
  `LLoydJumpscareFail`) suggest a scripted hide encounter. Read his BPs before deciding what AI to build.
