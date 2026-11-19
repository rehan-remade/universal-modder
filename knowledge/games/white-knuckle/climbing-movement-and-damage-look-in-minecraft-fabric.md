---
kind: game
title: "White Knuckle's climbing, movement and damage look as a Minecraft Fabric mod (1.21.9, ported to 26.3), from your own install"
game: "White Knuckle"
games_also: ["Minecraft Java Edition"]
game_version: "White Knuckle Steam build 25612096 (Unity 6000.3.9f1, Mono, D3D11/D3D12), run on Linux through Proton Experimental; Minecraft Java 1.21.9 with Fabric Loader 0.19.5, Fabric API 0.134.1+1.21.9; ported to Minecraft Java 26.3 with Fabric Loader 0.19.5, Fabric API 0.162.0+26.3 (OpenGL and Vulkan)"
platform: proton
engine: unity-mono
route: reimplementation
tools: ["Fabric on 1.21.9 (Loom 1.12.7, Gradle 9.1, Mojang mappings, JDK 25)", "Fabric on 26.3 (non-remapping Loom 1.18-SNAPSHOT, Gradle 9.7.1, JDK 25)", "xdg-desktop-portal FileChooser through an own pure-Java D-Bus client", "LWJGL tinyfd (Windows folder dialog, 1.21.9)", "SDL3 SDL_ShowOpenFolderDialog (Windows folder dialog, 26.3)", "ilspycmd 8.2.0.7535 on .NET 8", "UnityPy + TypeTreeGeneratorAPI", "vkd3d-compiler.exe (Fedora mingw64-vkd3d) under Wine", "Python 3.10-3.14"]
anti_cheat: "none: White Knuckle is single-player and is never modified; only its files are read. Minecraft side tested in single-player, LAN and a Fabric dedicated server."
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-16'
links: ["https://github.com/Fizz12215/White-Knuckle-Climbing"]
tags: [white-knuckle, unity, unity-6, minecraft, fabric, climbing, physics-port, shader-disassembly, dxbc, fsb5, ima-adpcm, fmod, proton, kde-wayland, reference-capture, rewired, ledge-detection, camera, flatpak, xdg-desktop-portal, d-bus, windows-11, pip-pinning, '26.3', vulkan, sdl3, porting]
---

# White Knuckle's climbing, movement and damage look as a Minecraft Fabric mod (1.21.9, ported to 26.3), from your own install

> A Fabric mod that plays like White Knuckle's climber:
> - two-handed grip climbing on ledges, bars and ice, with per-hand grip;
> - the game's on-foot physics, camera, hands, sounds and health rules;
> - its damage look and hand-fatigue shader.
>
> The gameplay is reimplemented in Java from the decompiled C# (kept in a private folder, never
> shipped) and the serialized prefab values. The art and audio never ship: each player runs a Python
> tool that builds a private resource pack from their own install. The real game was the oracle
> throughout. Shaders were disassembled, and reference screenshots were captured by driving the
> game's dev console. The Minecraft side is checked by an automated client game test, including a
> dedicated server.
>
> Since 0.4.0 the mod builds that pack itself, from a setup screen in Minecraft that explains each
> step (folders, size, source, how to undo) and waits for the player's OK. It was verified on Linux,
> in a Flatpak launcher, and on Windows 11 by a second Claude Code session on the owner's dual boot.
>
> 0.5.0 (not released yet) ports it to Minecraft 26.3, unchanged in play. The same game test passes
> under both of 26.3's graphics engines, OpenGL and Vulkan. What moved in 26.3, and the traps that only
> showed at runtime, are in
> [Fabric mods for 26.x](../../techniques/fabric-mod-for-26-x-without-mappings.md)
> (*Porting a 1.21.x mod to 26.3*, Gotchas 8-12).

## Setup
- White Knuckle from Steam (app 3195790), on Fedora 44 (KDE Plasma, Wayland) through Proton
  Experimental.
- Minecraft side: the versions above, a Prism Launcher instance per Minecraft version. 1.21.9: JDK 25
  compiling with `--release 21`. 26.3: Java 25.
- Decompile: ilspycmd **8.2.0.7535** on .NET 8 (`DOTNET_ROLL_FORWARD=Major`). Newer ilspycmd builds
  want a newer runtime.
- Asset tool: UnityPy and TypeTreeGeneratorAPI (MonoBehaviour type trees are stripped, so they're
  regenerated from `Managed/*.dll`), Pillow, soundfile. On Windows, use only Python 3.10-3.14 with
  `--only-binary=:all:`; 3.15 had no wheels yet.

## Route and why
- **Reimplement, don't embed.** White Knuckle's movement is a small set of C# methods on the
  player (Movement, Hang, Jump, HandStamina, InteractCheck, FallingDamage) driven by values stored
  in the scene. Porting them to plain Java, at the game's own 50 Hz fixed step and in game units,
  gave a unit-testable core.
- **Minecraft's role:** the adapter runs 2-3 sim steps per 20 Hz tick and uses Minecraft only for
  collision (`Entity.move`), ray casts and input.
- **Assets:** built per player from their install (the "own copy" route): the mod jar has no game
  files. The pack is the game's own art and audio, so it stays with that player and isn't shared.
- **Related ports into Minecraft:**
  - [FPV LOGIC's drones](../fpv-logic/fpv-logic-drones-flight-model-rc-radio-and-3d-models-in-minecraft.md)
    rebuild another game's physics as a Fabric sim;
  - [Halo 3 from your own MCC install](../halo-3-mcc/halo-3-weapons-covenant-vehicles-and-maps-ported-into-minecr.md)
    builds its resource pack from the user's install the same way.

## How the game works (what we had to learn)
- **Data beats code.**
  - Many serialized prefab values differ from the C# field defaults: gravity -0.2 (not -9.81),
    drag 8 (not 0.1), interact distance 2.5 units.
  - The player is `ENT_Player` in `level3`. Handhold presets and icy handholds are in
    `sharedassets1.assets`.
  - Read values from the data (UnityPy + generated type trees), not just the code.
- **Units:**
  - The capsule is 2.25 units tall, so 1 unit = 0.8 Minecraft blocks.
  - `vel` is not m/s: displacement per step is `vel * dt * 175`.
  - Health is 5, so it was scaled x4 for Minecraft.
- **Grip:**
  - each hand drains on its own, at half rate while both hands hang (one flag set each frame in
    `Actions()`);
  - icy handholds slide down at 0.3 units/s, shake after 1 s and slip at 2 s.
- **Climbing details that are easy to port wrong** (found in a line-by-line review, 0.3.1):
  - `Hang()` picks how W/S pushes you from a wall probe of `cCon.radius * 2.5`. That reads the
    controller's own unscaled radius (0.3), so the probe is 0.75 units long; using the 1.5-scaled
    capsule radius gives 1.125.
  - Wall friction while hanging tests the sprint *state* (sprint key, input above 0.8, not
    crouched), not the raw key. Shift alone doesn't count.
  - Walking off an edge zeroes the downward speed (grounded at the last move, not now, falling), so
    the fall starts from rest. The post-move speed clamp uses the grounded flag from before the move.
  - The hang pull is measured from `transform.position`, the standing capsule's centre. Crouching
    shrinks the capsule but doesn't move it.
- **Input (Rewired):** the move vector is two independent axes and is *not* normalised, so W+D is
  (1, 1). `_digitalAxisSimulation` is 0, so keys are instant with no ramp. A host that normalises
  diagonals (Minecraft gives 0.71, 0.71) feeds about 30% less input into the climb push and
  one-hand climbing.
- **Camera and body:**
  - "Main Cam Target" sits 0.45 (local) above the capsule centre at the 1.5 player scale. The eye is
    1.8 units up, which is 1.44 blocks (Minecraft 1.62). Crouching (`ChangeHeight`, 0.25 s) lowers it
    by crouchHeight - standingHeight (1.0 - 1.5), to 1.05 units, which is 0.84 blocks (Minecraft
    1.27).
  - You can look 15 degrees past straight up (`camMinY` -105).
  - The CharacterController steps only 0.15 x 1.5 = 0.225 units (0.18 blocks; Minecraft 0.6).
- **Screen blood:**
  - FX_Player_BloodSplatter_Screen is a child of "Overlay Camera". That camera renders only layer 29,
    at depth 5 (last), with a fixed FOV of 90: `SetCameraFov` changes only the main and hand cameras.
    So the blood never follows the sprint FOV (+15) or the FOV setting, and it isn't touched by the
    post-processing.
  - The UI canvas holding the hurt vignette is Screen Space - Overlay, so the vignette covers the
    blood.
- **Looping sounds** (AudioSources on the player, volume set every frame):
  - windAudio "PlayerFalling" (pitch 1.2): volume max((-vy - 2) * 0.03, 0) for the fall speed in
    units/s. It restarts on each new fall.
  - damageAudio (heartbeat) and dyingAudio (mortal wound): volume `damageFXCurve` x 0.8 and
    `dyingAudioCurve` x 0.8 of health. They're two layers of one piece, playing from level load in
    step.
  - Past the 50-unit safe fall distance, the camera shakes by 0.1 per second for as long as the fall
    lasts.
  - Grabs play "handhold-<material>" when that set exists (chain, metafungus), else "handhold".
- **The damage look** is not URP volumes. The player queues an `FXData` zone weighted by
  `damageFXCurve(health/max)`, and `FXManager` lerps its fields into shader globals:
  - `damageFX.hsv.y` = 0.1;
  - `gamma` = 2;
  - a red `worldTint`, applied in the world lighting.
- **The post shader** ("Hidden/Dark Machine/Post Process WK"):
  - converts to HSV, scales saturation (keeping value, so pure green goes *white*), then multiplies
    by `0.25 + 0.75 * _GAMMA`;
  - `_GAMMA` = the player's brightness setting + damageFX.gamma, so getting hurt brightens the
    picture.
  - A UI "hurt" vignette sits on top. Its colour comes from `Color.Lerp(clear, colour, amount)`, so
    colour *and* alpha scale with amount (it grows like amount squared). It is blended in linear
    light.
  - Another post class, "Gamma Post Process", is referenced in code but its shader isn't shipped.
- **Hand fatigue red** (`SHDR_Base_Inventory`, `Item_Hand_Material`):
  - `_StaminaAmount` = 1 - grip/max.
  - Stepped mode is on (`_StaminaMaskRepeat` 8, `_StaminaLevels` 8, repeat intensity 0.5). With no
    mask texture assigned, Unity's default *black* mask applies, so the red strength works out to
    round(8a)/8 + ceil(8a)/16: fully red (5/8 + 6/16 = 1) once 8a passes 5, i.e. just over 62% used.
  - Pixels are multiplied toward red, in linear light.
  - The default hand *cosmetic* sets an outline mask colour (0.49 grey), which turns on a branch
    where outline pixels fade grey to red linearly.
  - Because even the default hands are a cosmetic, each hand gets its own material copy, so each
    hand shows its own grip. A shared material would show the same amount on both.
- **Audio:**
  - The clips are FSB5 in `.resS`/`.resource`, mostly IMA ADPCM (codec 7) plus some Vorbis.
  - IMA frames are 0x24 bytes per channel: a header predictor that is itself the first sample,
    then 63 samples from the first 63 of the 64 nibbles (4-byte interleave, low nibble first).
  - Decoding that way matches FMOD bit for bit.
- **The dev console** opens with Shift + backtick.
  - `cheats` enables the other commands.
  - `hurtplayer dontkill <n>` deals exact damage without killing (clamps to 0.1 health).
  - `setstamina <0-10>` sets both hands' grip.
  - The playground has pure white, green and black green-screen rooms, which make ideal
    colour-measurement backdrops.

## Build steps
1. Decompile `Assembly-CSharp.dll` (ilspycmd, above) to a private folder. Dump the serialized
   values you port with UnityPy and generated type trees.
2. Port the movement methods into a dependency-free sim class. Unit-test it against hand-worked
   numbers (grip timings, jump strain, ice).
3. Wire it into Fabric:
   - a `LivingEntity.travel` mixin for the local player; collision through `Entity.move`;
   - C2S state (hanging, wkMode) so the server stops fall distance and the fly kick;
   - health rules run server-side.
4. Damage look:
   - one post pass with a writable uniform buffer, rewritten every frame;
   - the screen blood goes through its own GUI pipeline, which applies only the hurt vignette (the
     game draws it after post-processing, under the UI);
   - the hands go through a custom GUI pipeline whose fragment shader applies the stamina red and
     the damage look per pixel (parameters ride in the vertex colour);
   - shared GLSL include via `#moj_import` (26.3: `#include`, under ShaderC's rules; see
     [Fabric mods for 26.x](../../techniques/fabric-mod-for-26-x-without-mappings.md)).
5. Asset tool (Python):
   - finds the game through Steam's `libraryfolders.vdf` (and the Windows registry `SteamPath`);
   - extracts the hand sprites, crosshair, blood sheet, sound sets and the player's looping
     AudioSources into a pack folder and zip;
   - one FMOD batch subprocess per game file for audio.
6. Ship a zip with the jar, the tool and per-OS scripts (`.bat` with CRLF; `.sh`), plus a
   step-by-step guide.
7. In-game build (0.4.0): the jar carries the extractor and a pinned `requirements.txt`. A screen at
   the title finds the game and a Python 3.10-3.14, then runs each step after its own confirmation
   page:
   - make a private venv (the same folder the scripts use, so either's setup is reused);
   - pip-install the pinned wheels (`--only-binary=:all:`);
   - run the extractor straight into `resourcepacks/`;
   - turn the pack on and reload.

   A `wk_pack_info.json` version inside the pack lets the mod offer a rebuild when it needs newer
   files. "Choose its folder" uses the desktop portal on Linux (Gotchas 22-23). On Windows it used LWJGL's
   tinyfd on 1.21.9, and SDL3's folder dialog on 26.3, which ships no tinyfd.
8. Port to 26.3 (0.5.0), with the 0.4.0 release tag as the source of truth and every 26.3 name checked
   with `javap`:
   - the build switch, then one commit per area until the client and the gametest compile;
   - every mixin target compared with the 26.3 class before the first launch (3 of 21 had changed);
   - the damage look joins 26.3's list of requested post effects every frame, keeping its writable
     uniform buffer;
   - pack format 97 and a new pack content version, so 0.4.0 packs get the rebuild offer.

## Verification
- **Oracle 1, the real game:**
  - Damage look: reference screenshots in the playground's white, green and black rooms at health
    5/4/3/2/1/0.1, taken with `hurtplayer dontkill 1`. A per-pixel model (HSV saturation keeping
    value, the brightness multiply, the vignette in linear light) fits all 15 frames at rms
    2.8/255.
  - The fitted vignette amounts matched 1 - health/max, and the fit recovered the player's
    brightness setting (1.97, actual 2.0) before it was looked up.
  - The disassembled shader then confirmed every term.
- **Oracle 2, FMOD:** every clip decoded by FMOD in a fresh process, compared with the IMA decoder:
  bit-identical.
- **Oracle 3, Minecraft client game test** (Fabric client gametest, about 3.5 min):
  - grabs, ledges, fatigue, ice, bars, health rules;
  - white/lime/black concrete walls at matching health levels, each frame within 0.25/255 of the
    model applied to the full-health frame;
  - left-hand stamina at 8 levels, all sprite values within 2/255 of the formula, with the right
    hand unchanged;
  - an in-process dedicated server (join, climb, hang 5 s, no kick);
  - run with and without the asset pack;
  - since 0.3.1:
    - eye height 1.44 / 0.84, and 1.62 with climbing off;
    - crouch-walking off a ledge drops you (the server doesn't pull you back);
    - the near-death loops at 2% health: 0.422 / 0.794 (the game's curves give 0.423 / 0.797);
    - the falling wind peaks at 0.77 on a 60-block fall;
    - ledges under one snow layer grab, while inner corners and four-block floor corners don't.
  - Each of the player-reported bugs (snow, inner corners, floor seams) was reproduced in a test
    scene before the fix and passes after it.
- **The in-game build (0.4.0):**
  - A gametest with an empty `XDG_DATA_HOME` clicks Continue through all four steps on the real
    install. It checks the pack is on and the hands load, that Stop changes nothing, and that an
    out-of-date pack brings back the offer with two steps.
  - Every page is screenshotted; long Windows paths wrap clear of the buttons.
- **Windows 11:**
  - A second Claude Code session on the owner's Windows dual boot ran the same tests and the real
    game (clicking automated with universal-modder's Windows tools), then pushed results to a private
    repo.
  - Checked: Python 3.13 installed by winget, tinyfd's dialog in front of Minecraft, fullscreen
    switching, the `.bat`.
  - It found the stale-cache bug (Gotcha 28) and sent the fix.
- **Flatpak:** the owner picked White Knuckle through the portal in the real Prism Flatpak, and the
  build ran from the document-portal path.
- **The 26.3 port (0.5.0), on Linux with an NVIDIA GPU:**
  - the full game test on OpenGL without the pack, and on OpenGL and Vulkan with a pack rebuilt for 26.3;
  - the damage look within 0.24-0.26/255 of the model at every health level, as on 1.21.9;
  - the in-game build on both engines (libraries, build, switch on, the out-of-date offer, Stop);
  - screenshots of the hands, blood, damage look and every setup page on both engines. They caught a
    screen with no text that every check had passed (Gotcha 30).
- **Also:** a standalone `runServer` boots clean.
- **Not verified:**
  - the "server without the mod" auto-off path against a real vanilla server;
  - on Windows, the `.bat`'s own venv setup and its install-Python branch (it ran with a venv already
    there);
  - `flatpak document-unexport` as the undo for the portal grant;
  - the 26.3 port on Windows (SDL3's folder dialog above all) and in a long manual play;
  - the red `worldTint` on lit surfaces, left out because the green-screen rooms are unlit.

## Gotchas
1. **Extraction took 285 s.** **Cause:** UnityPy's FMOD fails in the main process (first on IMA
   ADPCM clips, then on everything), and the workaround spawned one subprocess per clip, each
   re-reading a ~1 GB asset file. **Fix:** one `--decode-clips` subprocess per game file decodes
   every clip in a fresh process: 13 s total.
2. **Grab/let-go sounds had faint block-edge glitches.** **Cause:** an IMA decoder that skipped
   the header predictor and used all 64 nibbles was off by one sample per block (correlation
   0.997, so it sounded "almost right"). **Fix:** emit the predictor as sample 0, then decode only
   63 nibbles; verify against FMOD.
3. **The extractor died silently on Windows, leaving only `*.partial`.** **Cause:** libsndfile's
   Vorbis encoder puts buffers on the stack in proportion to frames per write, overflowing
   Windows' 1 MB main-thread stack. **Fix:** write 4096-frame chunks on a thread with a 64 MB
   stack. Reproduce on Linux with `ulimit -s 1024`.
4. **`.bat` crash checks missed failures.** **Cause:** a native crash gives a negative exit code,
   which `if errorlevel 1` doesn't catch. **Fix:** `if not "%errorlevel%"=="0"`, and check that the
   output file exists. `.bat` files also need CRLF line endings.
5. **The damage effect "didn't look like the game".** **Cause:** desaturating toward luma turns
   bright green grey, but the game keeps HSV value (green goes white) *and* brightens the picture.
   Its vignette also scales colour with amount, and Unity blends in linear light. **Fix:** do the
   grade and the vignette in one post pass in linear space. Minecraft GUI blending is sRGB, so a
   GUI-drawn vignette can't match (white would come out far too red).
6. **Shader uniform names looked stripped.** **Cause:** the DXBC only has `cb0[n]`. **Fix:**
   UnityPy's `m_ParsedForm.m_SubShaders[i].m_Passes[j].m_NameIndices` names them, and
   `progFragment.m_CommonParameters` gives each name's constant-buffer offset and texture slot.
   Decompress `compressedBlob` (LZ4) by `offsets`/`compressedLengths`, cut out the `DXBC`
   containers (size at offset 24), and disassemble with
   `vkd3d-compiler.exe -x dxbc-tpf -b d3d-asm` under Wine.
7. **TypeTreeGenerator reads fail with EOF on some classes.** **Cause:** a stray `references` node
   appears before subclass fields for classes with `[SerializeReference]` lists, and the hand
   cosmetic class doesn't read at all. **Fix:** drop the first `references` node. For the cosmetic,
   read the raw bytes by field layout: bools are 4-byte aligned, and colours are four floats.
8. **Driving the game on KDE Wayland (XWayland window via python-xlib XTEST) typed into the game
   instead of its console.** **Cause:** every *new* XTEST client triggers KDE's "Remote Control: X
   is asking to control input devices" popup, which steals focus. If the user clicks "Allow"
   instead of "Always allow", the next script asks again. The commands then landed as WASD and
   Space: the player jumped around, and that run's data was useless. **Fix:** send a harmless key
   first, screenshot, and check for the popup before typing anything. Ask the human to tick
   "Always allow".
9. **The dev console closes on Enter in some cases.** **Fix:** assume nothing; screenshot after
   each command, or reopen the console before each one.
10. **Reference frames come out brighter than "stock".** **Cause:** the player's brightness
    setting feeds the post shader's multiply (`settings.json` in the Proton prefix under
    `AppData/LocalLow/Dark Machine/White Knuckle`). **Fix:** read it and model it, or capture at
    the default (1.0).
11. **Minecraft 1.21.9 post-effect uniforms are fixed per JSON.** **Fix:** a mixin adds
    `COPY_DST` to the mod's own pass uniform buffers and rewrites them every frame. Keep uniform
    blocks to plain floats, because `Std140Builder` pads a `vec3` differently from GLSL's packing.
12. **A climbing client on a vanilla server gets kicked for flying.** **Fix:** on JOIN, if not the
    local server and `ClientPlayNetworking.canSend(<mod payload>)` is false, switch climbing off
    with a message.
13. **Client gametest: keybinds do nothing on the title screen.** Toggle state directly between
    worlds. Also, the framework resets options at test start, so re-apply the custom keybinds in
    the test.
14. **Unity 6 AudioSources came out silent.** **Cause:** the clip is in `m_Resource` (an
    AudioResource). The old `m_audioClip` field is still serialized, but as an empty reference
    (m_PathID 0), so "use `m_audioClip`, else `m_Resource`" picks the empty one. **Fix:** take
    whichever reference is non-zero.
15. **Snow-covered ledges couldn't be grabbed** (player report). **Cause:** the ledge probes tested
    blocks' *visual* shapes, and one snow layer has a 2-pixel visual shape but no collision box. It
    "covered" every ledge, and wasn't a handhold itself, so snowy biomes had almost nothing to grab.
    **Fix:** blocks without a collision box don't cover a ledge. The same applies to leaf litter,
    petals, rails and plants.
16. **Concave inner corners could be grabbed** (player report). **Cause:** a ledge was "open above,
    drop below". That passed a block's back edge under a block one up and one back, and a ledge's
    end pressed into a taller neighbour. **Fix:** also require open space outward *above* the edge
    (where the hand comes over), and room for a hand (0.1 blocks) either way along it.
17. **A flat floor could be grabbed where four blocks meet** (player report). **Cause:** the
    closest point on an edge is often its exact end, which lies on block boundaries. There, a
    strict "inside the shape" test calls the diagonal neighbour's face "outside". **Fix:** judge, and
    grab, a point 0.001 blocks inside the edge.
18. **Crouching held the player at ledges.** **Cause:** Minecraft's sneak guard
    (`Player.maybeBackOffFromEdge`) runs for `MoverType.SELF`. It also runs on the server's replay
    of client moves, so a client-only fix gets the player pulled back to the edge. **Fix:** a common
    mixin keyed on the mod's per-player mode, on both sides.
19. **The eye height change didn't take at first.** In 1.21.9 player sizes come from
    `Avatar.getDefaultDimensions(Pose)`. The cached `eyeHeight` is only refreshed on a pose change,
    so a player who joins or respawns standing keeps 1.62. **Fix:** refresh when it's stale.
    Fixed-angle test aims also had to look about 3 degrees higher from the lower eye.
20. **Screen blood slid and shrank while sprinting** (player report). **Cause:** the port projected
    the splats with the current FOV (they shrank about 23% at +15 degrees), but the game's Overlay
    Camera stays at 90. **Fix:** project at a fixed 90.
21. **A test passed for the wrong reason.** The game's 0.2 s grab memory let a hold from the view
    *before* aiming at a corner satisfy the check. **Fix:** wait out the memory after aiming.
    Separately, the client gametest's NetworkSynchronizer once reported "interfacing with packets at
    a lower level" and crashed the server. That's harness accounting; a rerun passed.

22. **A Flatpak launcher can't see the Steam folder.** Prism from Flathub (and most Steam Deck
    setups) runs Minecraft in its sandbox, where `~/.local/share/Steam` doesn't exist.
    - `flatpak override --filesystem=~/.local/share/Steam:ro` works, but it also exposes Steam's
      `config/` (its login and settings files; `config.vdf` was readable from inside) to every mod in
      the launcher.
    - **Fix:** the FileChooser portal with `directory: true`. The folder picked comes back as a
      document-portal path (`/run/user/<uid>/doc/<id>/White Knuckle`) the sandbox can read. It's
      remembered across restarts, and `flatpak document-unexport --doc-id=<id>` takes it away.
    - A fallback command should grant only the game folder.
23. **Nothing in Prism's sandbox could wait for the portal's answer.**
    - The sandbox's zenity is 3.44 (GTK3), whose dialog shows only the sandbox.
    - Its Python has no `gi`.
    - `gdbus call` gets the request handle and exits, which closes the request.

    **Fix:** about 300 lines of Java D-Bus client over the session socket: `UnixDomainSocketAddress`,
    SASL EXTERNAL with the uid from `/proc/self`, `Hello`, `AddMatch` on the request path,
    `OpenFile`, then wait for `Response`. It works through the sandbox's bus proxy
    (`unix:path=/run/flatpak/bus`).
24. **Switching away from fullscreen Minecraft froze it** (NVIDIA 615 driver, KDE Wayland, Flatpak
    Prism). About 8 s after the player opened a terminal, an Xid 31 MMU fault hit Minecraft's render
    thread, which then waited in `glClientWaitSync` forever. Minimizing and restoring in a gametest
    didn't reproduce it.
    - **Fix in the mod:** leave fullscreen before opening any other window (picker, installer), and
      go back after.
    - Never ask players to run commands while the game is open.
25. **Windows: never call a bare `python`.** It can be the Microsoft Store alias, or Store Python,
    whose AppData writes are redirected (a venv in `%LOCALAPPDATA%` lands elsewhere).
    - **Fix:** use `py -3.X` plus the known install paths (`%LOCALAPPDATA%\Programs\Python\...`,
      `%ProgramFiles%\Python3XX`), which also find a fresh winget install without a restart.
    - On Windows 11, `winget install Python.Python.3.13` installed per user with no UAC prompt.
26. **Steam's registry `SteamPath` is lower case with `/`** (`c:/program files (x86)/steam`), and
    Windows paths compare case-insensitively, so that spelling wins a dedupe and shows in the UI.
    `toRealPath()` gives the real one.
27. **pip evaluates `python_version` markers against the Python running it, not
    `--python-version`.** To check a pinned file for Python 3.10-3.14 on Linux and Windows from one
    machine:
    - resolve the markers per target with pip's own `packaging` first;
    - then `pip install --dry-run --python-version X --platform Y --report`.

    numpy needed three pins (2.2.6, 2.4.6, 2.5.4).
28. **A cached "is the pack there?" answer went stale**, so a pack switched on showed up late.
    - Cached resource checks must be dropped on every reload (Fabric API v1
      `ResourceLoader.get(CLIENT_RESOURCES).registerReloader`).
    - `Options.updateResourcePacks` only reloads when the selected list changed: call
      `reloadResourcePacks()` for a rebuilt pack that's already on.
29. **Java's `Properties` mangles Windows paths.** `store` writes `C\:\\...`, and `load` eats
    single backslashes typed by hand. Read that key's raw line, and write the file by hand with `/`.
30. **After the 26.3 port the setup screen showed only its title and buttons**, though every gametest
    check passed. Two 26.3 changes, both silent: a `ScrollableLayout` given its maximum height before its
    content was laid out stays 0 px tall, and a `Screen` now has `minecraft` from its constructor, so an
    `if (minecraft != null) rebuildWidgets()` built a second set of widgets. Causes and fixes:
    [Fabric mods for 26.x](../../techniques/fabric-mod-for-26-x-without-mappings.md), Gotchas 9-10. State checks
    can't see layout: look at the screenshots.

## Assets
None generated. All art and audio come from the player's own install through the asset tool. The
hurt vignette is a fitted analytic curve, `0.086 + 0.914 * (1 - exp(-(r/0.287)^2.75))`, within
0.02 opacity of the game's image, so the mod needs no game image for it.

## Cost and time
Several long sessions over about two weeks, mostly verification. The damage-look and hand-shader
investigation (capture, fit, disassembly, port, in-game check) took about one session.

## Open questions
- The red `worldTint` on lit surfaces, which needs a lit reference scene.
- Minecraft samples aim and buttons at 20 Hz (the game at 50 Hz or more), so a fast mouse flick can
  skip a ledge the game would catch. Sampling the aim every frame into the 0.2 s grab memory would
  close most of the gap.
- Looking 15 degrees past straight up, which Minecraft clamps at 90.
- Items, the inventory and perks are not ported (the public beta is climbing only). They come next,
  on 26.3 only (0.4.0 is the last 1.21.9 version).
- The server trusts the client's "hanging" flag (no fall damage or fly kick while set). It needs a
  server-side plausibility check before use on public servers.
