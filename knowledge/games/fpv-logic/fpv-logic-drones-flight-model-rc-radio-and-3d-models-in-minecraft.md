---
kind: game
title: FPV LOGIC drones (flight model, RC radio and 3D models) ported into Minecraft 26.3 (Fabric)
game: FPV LOGIC
games_also: ["Minecraft Java Edition"]
game_version: "FPV LOGIC (Steam 2398030), UE 5.3.2 (++UE5+Release-5.3, CL 29314046), 18 legacy paks v11, Oodle; Minecraft Java 26.3 + Fabric Loader 0.19.5 + Fabric API 0.162.0+26.3"
platform: windows
engine: unreal
route: reimplementation
tools: ["own Python pak v11 reader (Oodle via ctypes)", "own cooked-UE5.3 uasset/FField/unversioned-property reader", "own Kismet bytecode disassembler", "own GVAS SaveGame reader", "own cooked StaticMesh / Texture2D (DXT1/DXT5) / MaterialInstanceConstant readers", "own meshoptimizer-style edge-collapse simplifier (pure Python)", "Fabric Loom 1.18 (JDK 26 as Gradle JVM)", "um scan / um publish check"]
anti_cheat: "none; FPV LOGIC is only read from disk (paks + SaveGames), never launched or hooked"
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-06'
links: []
tags: [content-port, mashup, unreal, blueprint, kismet, gvas, unversioned-properties, oodle, simple-construction-script, static-mesh, texture2d, dxt, material-instance, lod, mesh-simplification, fabric, sdl3, joystick, rc-transmitter, camera-mixin, spectator, mannequin, post-effect, custom-geometry, performance-mods, distant-horizons, chunky]
---
# FPV LOGIC drones (flight model, RC radio and 3D models) ported into Minecraft 26.3 (Fabric)

> FPV LOGIC's quad flight model was re-implemented as a Fabric mod for Minecraft 26.3, read from the game's own
> Blueprint bytecode and drone DataTable.
>
> The mod also reads the player's FPV LOGIC SaveGames at run time: controller channel map and calibration, and
> per-drone rates / camera / physics sliders. Their RadioMaster flies the same drone with the same setup.
>
> A key toggles between two modes:
> - Flying: FPV camera and OSD. The player rides along as an invisible spectator while a mannequin of them stands at
>   the launch spot.
> - The normal player, who builds race tracks from checkpoint blocks.
>
> A second pass rebuilt all 15 flyable drones as real 3D models on the player's PC, from their install:
> - meshes, textures and FPV LOGIC's paint scheme;
> - each drone placeable as its own item, flying with its own physics;
> - detail levels so 17 drones 14 m away cost about 0.4 ms per frame, and your own drone in chase view about
>   1.7 ms.
>
> A performance pack was added too: Sodium, Distant Horizons, Chunky auto pre-generation, and others.
>
> Verified with a headless sim bench and two scripted in-game autotests with screenshots. The player then
> confirmed a RadioMaster TX15 over USB and an Iris shader pack in their own install.

## Setup
- Windows 11. FPV LOGIC on Steam:
  - UE 5.3 unversioned cook.
  - Legacy `.pak` v11 (no IoStore), unencrypted index, Oodle-compressed entries.
  - No anti-cheat. SDL2.dll ships next to the exe (its joystick backend).
- Oodle: FPV LOGIC has no DLL of its own. Another installed game's `oo2core_8_win64.dll`, loaded with ctypes
  (`OodleLZ_Decompress`), decodes its UE 5.3 blocks fine.
- Minecraft Java 26.3: unobfuscated, needs Java 25, ships LWJGL 3.4.3 including `lwjgl-sdl` (SDL3). Official
  launcher, MS Store build.
- Fabric example-mod branch `26.3`:
  - Loom `1.18-SNAPSHOT` (`net.fabricmc.fabric-loom`, no remap), Gradle 9.7.1, Loader 0.19.5, Fabric API
    0.162.0+26.3.
  - Gradle ran on an Oracle JDK 26 via `org.gradle.java.home`.

## Route and why
Pattern 1 of mashup-mods (port the logic). Minecraft is the host; FPV LOGIC is only a data source.
- Passthrough was pointless: the user wants a Minecraft drone flying over Minecraft blocks.
- FPV LOGIC's flight model is small enough to port exactly.
- Its numbers and models come from the user's install. A converter writes a JSON drone table and a `models/` folder
  (meshes, PNGs, JSON) into the instance's config; the mod parses FPV LOGIC's SaveGames itself.
- Nothing from the game is shipped.

## How the game works (what we had to learn)

### Packages and data
- **Cooked packages are unversioned:** the summary has UE4/UE5 versions = 0. Read them as UE4 522 / UE5 1009 (5.3).
  With `PKG_FilterEditorOnly`, import entries have no PackageName (5 FNames → 4) and the summary has no
  LocalizationId.
- **DataTables with UserDefinedStruct rows are decodable without .usmap:**
  - The UDS export carries its own FField list: name, flags, ArrayDim, ElementSize, PropertyFlags, RepIndex,
    RepNotifyFunc, BP replication byte, plus type extras.
  - Rows use unversioned property serialization: uint16 fragments (skip 7 bits, has-zeroes, is-last, value
    count), then a zero mask, then values in schema order.
  - UDS field names carry a `_<n>_<32 hex GUID>` suffix to strip.

### Flight logic
- **The drone is all Blueprint:** a `Pawn` BP with a physics-simulating static mesh as root.
  - One parent BP holds all the logic; drone variants are subclasses.
  - A function library loads a drone class by ID.
  - Physics values per drone live in the DataTable: mass in kg, thrust in UE force units, max speed in cm/s,
    drag/damping per second, attenuation factors, propwash power and speed range, boost, camera FOV/tilt range.
  - The SaveGame holds per-drone percent sliders on top of them.
- **Tick logic (from `ExecuteUbergraph` via the ReceiveTick entry):** a Sequence of ~20 branches.
  - **Rotation is kinematic:** `AddLocalRotation` by stick rate × dt. Torque only applies for 0.2 s after a slow hit.
  - **Rates and feedforward:** the four classic rate models (Betaflight with a slightly different expo term, Actual,
    RaceFlight, KISS) plus a feedforward term: the frame-to-frame stick delta scaled by stick deflection.
  - **Thrust:** `AddForce` along the body up vector, scaled by a throttle curve asset (cubic keys over stick
    −1..1), motor idle (more when level) and a short "punch" boost from throttle rate. Only the world-horizontal
    components are attenuated, by throttle, near top speed, and by velocity-vs-thrust angle.
  - **Damping:** linear and angular damping lerp with throttle. Velocity is clamped to max speed, with an extra
    vertical damping per frame.
  - **Propwash:** random per-frame roll/pitch kicks when descending into the wash.
  - **Extra gravity:** a "gravity slider" adds a constant downward force.
  - **Project config:** `DefaultGravityZ` is −1170 (not −980). Physics substeps at 0.033 s max.
  - **Angle mode:** RInterpTo toward a curve-shaped target attitude. Mode 2 adds altitude hold: a throttle offset from
    vertical speed while the throttle stick is centred.
  - **Switches:** the reset switch flicked = flip upright in place; held 1 s = reset to the launch pad. The mode and
    camera switches cycle on each flick. Slow-mo eases global time dilation down to 1/N.
- **Kismet disassembly:** jump targets are in-memory offsets. Track disk vs memory sizes: object pointer 4→8,
  FName 8→12 (FScriptName), FField path (count + names + owner) → 8. With that, a straightforward disassembler
  printed every function readably on the first try.
- **SaveGames (GVAS):** plain tagged properties (unlike cooked assets). The controller save stores, per axis:
  SDL2 GUID, name, VID/PID, axis index per function (roll/pitch/yaw/throttle/reset/mode/cam/slow), deadband %,
  inversion, half-throttle, and Low/Mid/High calibration.
- **Minecraft 26.3 SDL3:** Minecraft only inits SDL video (`SDL_Init(32)`). `SDL_InitSubSystem(JOYSTICK|GAMEPAD)`
  from the render thread works. Disable joystick events and call `SDL_UpdateJoysticks` yourself.
  `SDL_GetJoysticks` must be freed with `SDLStdinc.SDL_free`.

### Drone assembly (for the models)
- **One component tree for every drone.** The base drone BP's SimpleConstructionScript holds the whole tree:
  - `Base_mesh` (the physics body, hidden) is the parent of `Frame_A/B/C`, `Motor_stator_1-4`, `Rotor_1-4`, `Cam_model`,
    `Battery`, `Strap_1/2`, `FC`/`ESC`/`RX`/`VTX` boards, antennas, `GoPro`, `LED_A/B`, `Wire`, `Screw`, `Add_1-3`.
  - `Rotor_n` is the parent of `Prop_n`, `Propcircle_n` (the blur disc) and `Nut_n`.
  - The base templates set no meshes. Each variant BP (a child class) sets mesh, override materials and relative
    transform per component, as `<Component>_GEN_VARIABLE` exports in its own package. Compose the transforms down
    the tree.
- **Unversioned schema indices (UE 5.3):**
  - SCS_Node: 0 ComponentClass, 1 ComponentTemplate, 3 AttachToName, 4 ParentComponentOrVariableName,
    7 ChildNodes, 9 VariableGuid, 10 InternalVariableName.
  - StaticMeshComponent:
    - 0 ForcedLodModel (int32).
    - 4 StaticMesh (obj).
    - 11 a bool (1 byte).
    - 33 OverrideMaterials (int32 n + n obj refs; a null entry keeps the mesh's material).
    - 148/149/150 RelativeLocation/RelativeRotation/RelativeScale3D (3 doubles each; rotator is pitch, yaw, roll).
- **Some motors are mirrored with a negative scale (1, 1, −1).** Flip the winding for parts whose final determinant
  is negative.
- **Paint ("Refresh Color" in the BP).** Only material slot 0 of each part gets a dynamic material instance.
  - Integer CDO variables `CustomColor_<group>` pick colour A (0) or B (1). The groups are Frame_A/B/C, CAM, Motor
    (stators + rotors), VTA, Nut, Gopro, Strap, ADD1-3.
  - Props take the prop colour through `Drone_Custom_color`; prop-blur discs through `Custom_color`.
  - One LED part takes the LED colour through `COLOR`. Only one LED material has that parameter; the others keep
    their colour.
  - Special case for the Volador family when a colour is pure white: the frame shows its stock colourful diffuse
    texture, and the motors a fixed grey.
- **Materials.** Instance parameters are arrays of {FName, association byte, index −1, value, expression GUID}, so
  they can be found by the FName.
  - Generic drone material: Diffuse, Mask, MRA, Normal, `Drone_Custom_color`.
    - Ported as lerp(diffuse, colour, mask). On many frames the diffuse is black under the mask and the mask
      carries the shading.
  - A second material family, used on the Volador frames, adds a `C_POW` parameter.
    - Ported as diffuse × lerp(1, colour, mask^C_POW), with a separate white `*_W_D` diffuse used for tinting.
  - Props: a flat colour. Prop-blur discs: a colour × an opacity map whose blade sweeps are in the DXT5 alpha.
  - Also: glass, battery heat-shrink (diffuse + colour mix + opacity), and LED (emissive colour, optional flash
    speed).
- **Armed vs disarmed.** Armed drones hide `Prop_n` and show `Propcircle_n`; disarmed drones do the reverse.
  `Cam_model` relative rotation is set to (pitch = camera tilt, 0, 0).
- **Cooked Texture2D layout.**
  - Before the pixel-format FString: SizeX, SizeY, PackedData.
  - After it: FirstMipToSerialize, NumMips, then per mip [bulk-data index][inline payload if not in bulk][SizeX,
    SizeY, SizeZ].
  - The large mips sit back to back in `.ubulk`, starting at mip 0. Sizes follow from the block size (DXT1 8 bytes
    / DXT5 and BC5 16 bytes per 4×4).
  - Formats seen: DXT1, DXT5, BC5 (normal maps, not needed).
- **Cooked StaticMesh LOD layout.** Locate each LOD by its buffers rather than parsing the mesh's own properties:
  - [sections: n × 40 bytes][MaxDeviation][cooked-out flag][inlined flag][2-byte strip flags]
  - Then the position buffer (stride 12, n, 12, n + floats).
  - Then the static-mesh vertex buffer (UV count, full-precision UV flag, high-precision tangent flag; tangents
    bulk with the normal as the second packed vector, SNORM; UV bulk).
  - Then the colour buffer, then the index buffer (32-bit flag + bulk).
  - Later LODs follow the previous LOD's index buffer. Many newer meshes have only LOD0.

## Build steps
1. **Converter:** `python tools/import_fpvlogic.py --out "<instance>/config/fpvcraft"`.
   - Reads the drone table, palette and curves from the paks into one JSON.
   - Then rebuilds every drone into `models/` (about 2 minutes, about 30 MB):
     - per drone, a JSON of parts with body-frame matrices, rotors, camera mount, colour slots, materials and
       bounds;
     - mesh `.bin` files (5 detail levels);
     - PNG textures (≤512 px for frames, ≤256 px otherwise).
2. **Mod:** Fabric 26.3 template, `./gradlew build`. To install:
   - Put Fabric's version JSON in `.minecraft/versions/fabric-loader-0.19.5-26.3/` (plus an empty jar).
   - Add a launcher installation with its own `gameDir`. Edit `launcher_profiles.json` with the launcher closed,
     after a backup.
   - Put the mod, the Fabric API bundle jar and the performance pack (Modrinth API, SHA-1 checked) in `mods/`.

## Verification
- **Headless bench** (fixed 240 Hz substeps, frame-based terms at frame rate): hover stick %, punch-out time, top
  speed (matches the table's own top-speed column), full-stick rate, drop and settle, angle-mode attitude, propwash.
- **Flight autotest** (`-Dfpvcraft.autotest=flight`):
  - Creates a flat test world from the client (no server EULA needed) with `WorldOpenFlows.createFreshLevel` +
    `WorldPresets::createTestWorldDimensions`.
  - Builds a 3-gate course with commands, summons a drone and starts the session.
  - An angle-mode autopilot flies out and back for a lap (lap event logged).
  - Then an acro flip (inverted in 7 ticks), chase and LOS cameras, and a hold-reset (0.00 m from the pad).
  - Taking the goggles off restores creative mode at the same spot, with 0 mannequins left.
  - Screenshots via `Screenshot.grab(gameDir, name, gameRenderer.mainRenderTarget(), 1, cb)` at
    START_CLIENT_TICK, all looked at.
- **Models autotest** (`-Dfpvcraft.autotest=models`, 1600×900):
  - Summons all 17 drone types on a bench and takes close / 4 m / 14 m shots.
  - Logs CPU time spent writing drone vertices per frame:

    | View | Cost | Vertices |
    |---|---|---|
    | Close-up | 2.3 ms | 106k |
    | Bench at 4 m | 1.5 ms | 41k |
    | Bench at 14 m | 0.4 ms | 12k |
    | Chase view | 1.7 ms | 53k |

  - Flies one drone item: its own physics, prop blur, and landing height = the model's real bottom (0.024 m).
  - Checks the item icons.
- **Confirmed by the player in their install:**
  - A RadioMaster TX15 (EdgeTX, USB joystick mode) steers the drones with the channel map from FPV LOGIC's
    Controller save. SDL2 (FPV LOGIC) and SDL3 (Minecraft) report the axes in the same order.
  - The models render correctly with an Iris shader pack.
- **Not verified:** dedicated servers, and the frame cost of the models with a shader pack.

## Gotchas
1. **`/summon` from the test failed: "Incomplete (expected 3 coordinates)".**
   - **Cause:** a Polish locale formatted `9.50` as `9,50`.
   - **Fix:** `String.format(Locale.ROOT, …)` everywhere text is machine-read.
2. **The pilot's mannequin body vanished as soon as it spawned.**
   - **Cause:** `ServerEntityEvents.ENTITY_LOAD` fires inside `addFreshEntity`, and the "remove leftover bodies after
     a crash" handler saw a tagged body not yet in the session map.
   - **Fix:** add the tag after spawning (or register the session first).
3. **No way to set a Mannequin's profile.**
   - **Cause:** `setProfile`, `setImmovable` and `setHideDescription` are private.
   - **Fix:** an `@Invoker` mixin; `ResolvableProfile.createResolved(player.getGameProfile())` gives the skin.
4. **The player must fly along, or chunks never load at the drone.**
   - **Fix:** put the player in SPECTATOR while flying. Vanilla then skips "moved wrongly", collisions and the floating
     kick. Cancel `LocalPlayer.aiStep` and set the player's position to the drone each frame; vanilla movement
     packets do the rest.
   - Persist a session attachment to restore the game mode and position after crashes/disconnects.
5. **The camera needs roll.**
   - **Fix:** cancel `Camera.alignWithEntity`. Set the `rotation` quaternion and recompute `forwards`/`up`/`left` from
     the private static `FORWARDS`/`UP`/`LEFT`. Set `xRot`/`yRot` from the forward vector and
     `matrixPropertiesDirty |= 3`.
   - Override `calculateFov` for the FPV FOV (convert FPV LOGIC's horizontal FOV to vertical).
6. **Prop spin was wrong on all four props.**
   - **Cause:** submit-based entity rendering is deferred, so mutating a shared `ModelPart` rotation between submits
     only keeps the last one.
   - **Fix:** rotate with the PoseStack and submit parts with no own rotation.
7. **26.3 API renames that cost a build each:** `InputConstants.Type.KEYBOARD` (not KEYSYM),
   `PoseStack.rotate(Quaternionfc)`, `GameRenderer.mainRenderTarget()`, `gui.hud.isHidden()`,
   `LevelSettings.DifficultySettings`, `Entity.setPermanentlyInvulnerable`,
   `Entity.interact(Player, InteractionHand, Vec3)`, `BlockBehaviour.Properties.isViewBlocking` taking 4 args.
8. **Translucent block textures:** 26.3 picks the chunk layer from texture alpha
   (`ChunkSectionLayer.byTransparency`); no render-type registration is needed.
9. **A lens effect needs no Java shader code.** Post effects are data (`post_effect/*.json` + `.fsh`).
   - Add your id to `GameRenderer.getRequestedPostEffects()` each frame (after `update()` cleared it, e.g. at
     `extract` HEAD).
   - Uniform values are static in the JSON, so make a few strength variants.
10. **The HUD while flying:** `HudElementRegistry.replaceElement` wrappers that skip vanilla elements while
    flying, plus `addLast` for the OSD. Cancel `Minecraft.handleKeybinds` but call `gui.handleKeybinds()` so chat
    and F1 still work. Another mod's HUD element (Xaero's `xaerohud:hud`) only exists after that mod's init: wrap it
    at `ClientLifecycleEvents.CLIENT_STARTED`, in a try/catch for when the mod is absent.
11. **Materials landed on the wrong sections of multi-material meshes.**
    - **Cause:** a package's imports are sorted by name, not in the mesh's StaticMaterials order.
    - **Fix:** order the material imports by where each is first referenced in the StaticMesh export data. That is
      its StaticMaterials array.
12. **Prop-blur discs rendered solid.**
    - **Cause:** the opacity is in the DXT5 alpha channel; the RGB is almost white.
13. **The simplifier stalled at ~60% on CAD parts** (frame plates, motors).
    - **Cause:** with seam-aware edge collapse (meshoptimizer's vertex kinds), hard-edged meshes have three or more
      wedges per corner, so nearly every vertex is locked.
    - **Fix:** for the far detail levels, collapse on positions only. Then give each surviving corner the wedge
      whose normal (then UV) best matches the original corner. Errors stayed at 1–3 mm while reaching 8% of the
      triangles.
14. **FPV LOGIC's own LODs are not enough for a voxel game's distances.** Its LOD2 of a frame is still ~2,400
    triangles for a drone a few pixels wide. Add far levels of your own; pick levels by projected radius (pixels);
    skip parts under ~1.5 px.
15. **26.3 custom entity geometry cost ~50 ns per vertex at first.**
    - The model transformed each emitted vertex, but meshes share vertices about 3×. Fix: store each section with its
      own compact vertex list, transform each vertex once per frame into scratch arrays, then write with the
      11-argument `VertexConsumer.addVertex(x, y, z, color, u, v, overlay, light, nx, ny, nz)`. That is
      BufferBuilder's entity-format fast path. ~27 ns per vertex with Sodium and ImmediatelyFast.
    - Entity render types are QUADS. Pair triangles that share an edge into one quad (a,b,c,d draws a,b,c + c,d,a),
      and write unpaired ones as a,b,c,c. About 2.1 vertices per triangle instead of 4.
16. **`DynamicTexture` has no mipmaps** (and NEAREST sampling), so tiny drones shimmered.
    - **Fix:** a small `AbstractTexture` subclass: `device.createTexture(label, 5, RGBA8_UNORM, w, h, 1, mips)`,
      `writeToTexture(tex, image, level, 0, 0, 0)` per level, and `getSamplerCache().getRepeat(LINEAR, true)`.
    - Compose and mip on worker threads; upload at the start of the next frame (`GameRenderer.extract` HEAD), not
      mid-render.
17. **A child Blueprint's own variables come first in its schema.** One drone variant adds a component (a point
    light), so its CDO's unversioned indices were all shifted by one, and parsing produced garbage colour slots.
    Count the child BPGC's own property list and offset by it. Structs with nothing serialized
    (`PointerToUberGraphFrame`, `TimerHandle`) are a bare 2-byte unversioned header.
18. **Drones floated after landing.** The sim used a cube collider sized from the prop span.
    - **Fix:** take bottom and top from the model's bounds. Use the vertical reach of that box as rotated by the
      drone's attitude, so it rests on the frame when level and on the battery when upside down.
19. **Dev runs default to an 854×480 window,** so "close-up" screenshots looked far away. Pass
    `--width 1600 --height 900` to the run config.
20. **A user clicking into the autotest window can hit the drone under the crosshair** (creative attack removes it)
    and fail the run. Make failures quit, and suspect focus clicks when an entity vanishes mid-test.

## Assets
- Original pixel art generated by a Python PNG writer: checkpoint panels with digits, launch pad, items. The 17
  drone items share one two-layer icon tinted per drone by the item definition.
- The fallback drone model is boxes built in code, tinted per part with the colours from the player's FPV LOGIC
  palette.
- The real models are converted on the player's machine from their own install into the game's config folder.
  The mod jar contains no FPV LOGIC data.
- Keep the converter output in `config/fpvcraft/` (drone table, meshes, textures) on your own PC: it is FPV
  LOGIC's content, so don't share or upload it, and leave `config/fpvcraft` out of modpack and instance exports.
  Each player runs the converter on their own install.
- The motor whine is synthesized with ffmpeg `aevalsrc` (seamless 2 s loop of integer-Hz partials, mono Vorbis).
- Wind, gate and lap sounds reference vanilla sound files through `sounds.json`.

## Cost and time
| Pass | Wall-clock | What |
|---|---|---|
| Flight model | ~3 h | Recon and reverse engineering about 1 h, mod and in-game tests about 2 h. |
| Models and performance pack | ~3.5 h | Mesh/texture/material readers and drone assembly about 1.5 h; simplifier, renderer and performance work about 1.5 h; pack install and tests 0.5 h. |

## Open questions
- **Torque after slow hits.** Exact behaviour of FPV LOGIC's 0.2 s torque mode (depends on Chaos inertia from the
  collision mesh); approximated as a first-order rate response.
- **Fixed-wing.** The fixed-wing drone (`Wing-A`) shares the BP but needs its own aerodynamics; not ported.
- **Material formulas.** The base materials' node graphs aren't in the cook (only compiled shaders). The two
  colour-mask formulas above were inferred from the textures and parameter names, and match the look; not proven
  from shader code.
- **Shader packs.** They work, but drones are drawn again in the shadow pass; the extra cost was not measured.
