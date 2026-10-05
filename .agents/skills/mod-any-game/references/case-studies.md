# Case studies

This toolkit grew out of two projects: a Terraria mod and a new Age of Empires II civilization. Each
section below gives the route, the pipeline, and the facts that took time to find. The code is in
`examples/terraria-tmodloader` and `examples/aoe2-de-civ`.

## Terraria: homing missiles, a tactical nuke, new enemies, a boss

**Route: loader API (tModLoader).** Terraria is a .NET (XNA/FNA) game, and tModLoader is the official
community loader. It is a free Steam app, id 1281930. Content is written in C# as subclasses: `ModItem`,
`ModProjectile`, `ModNPC`, `ModSystem`, `ModPlayer`, `ModCommand`.

**Pipeline**
1. Recon: `um scan terraria` → XNA/FNA .NET, no anti-cheat, known route tModLoader.
2. Source of truth: decompile `Terraria.exe` with `ilspycmd` into `~/terraria-decomp`, outside git. Read
   vanilla AI there (e.g. `NPC.AI_004` for the Eye of Cthulhu, `aiStyle` numbers). tModLoader's own
   decompiled base (1.4.4.9) was diffed against vanilla 1.4.5.8 to confirm the logic matched. The only
   differences were refactors.
3. Lab: tModLoader launched with `-tmlsavedirectory C:\dev\tModLoader\lab` so the user's real characters and
   worlds are never touched. A lab character is created in code if missing. `-skipselect Char:World` jumps
   straight into a world.
4. Content: weapons as `ModItem` + `ModProjectile`, enemies as `ModNPC` with custom `AI()`, a boss with two
   phases, a boss bar, music and loot. A scripted showcase `ModSystem` spawns waves and runs the camera.
5. Art: fal `flux/dev` with a Terraria-style prompt ("16-bit pixel art game sprite in the style of Terraria,
   crisp dark outline, limited palette, plain flat white background"). Then border flood-fill cutout, then a
   nearest-neighbour fit to each frame size (`um sprite cutout` / `fit` / `sheet --vertical`).
6. Verify: the game's `client.log`, screenshots of the window, and a deterministic scripted scene.
7. Showcase: recorded from inside the mod (ffmpeg gfxcapture of its own window, with process-loopback audio),
   muxed with QPC timestamps, then cut to about 30 s.

**Facts that cost time**
- NPC frame height comes from `texture height / Main.npcFrameCount`, so any consistent frame size works.
  Vertical strips are the convention.
- **Sprite orientation:**
  - items point right;
  - NPC sprites face left, and the engine flips them;
  - a projectile's rotation 0 means pointing right, unless you draw it yourself in `PreDraw`.
- Vanilla "fighter" AI (aiStyle 3) flees in daylight. A daytime walker enemy needed custom AI.
- `Main.instance.InactiveSleepTime = TimeSpan.Zero` keeps the game at full speed when its window isn't
  focused, which matters for automated takes.
- **Recording:** don't read the back buffer from inside the game. FNA3D's D3D11 `ReadBackbuffer` leaked a
  full-size staging texture per call, 17 GB in one take. Capture the window from outside instead: ffmpeg
  `gfxcapture=hwnd=...`.
- FAudio talks to WASAPI directly, so `SDL_AUDIODRIVER` tricks do nothing. Use process-loopback capture of
  the game's PID (`um/ps1/ProcLoopback.ps1`).
- **Stopping ffmpeg:** never block the game's main thread while ffmpeg stops. gfxcapture stalls on a frozen
  window and never reads the 'q'. Send 'q', then wait off-thread.
- Write `.mkv` while recording: it survives a kill, where an mp4 would lose its index.
- Explosive takes crater the showcase world. Restore the pristine copy before each take (`um backup`).
- tModLoader refuses to start unless the free tModLoader app is in the Steam library. Install it; never
  patch the check.
- A float-exact port of game logic (for a simulator) must use float32 constants: `0.2f` isn't `0.2`.
- **Process safety:** never `pkill -f <pattern>` from an agent shell. The pattern matches the agent's own
  command line and kills it. Kill by exact PID.

## Age of Empires II DE: the San Franciscans civilization

**Route: data mod plus graphics.** AoE2 DE is the Genie engine. Its game data is one big `.dat`
(`resources/_common/dat/empires2_x2_p1.dat`), which `genieutils-py` reads and writes. Local mods go in
`%USERPROFILE%\Games\Age of Empires 2 DE\<steamid>\mods\local\<Mod>`.

**Pipeline**
1. Recon: `um scan "age of empires"` → Genie, no anti-cheat (ranked uses unmodded data anyway).
2. **Data:** clone the Britons' tech tree into the new civ. Add unique units by deep-copying a template unit,
   then changing stats, graphics and train location. Add unique techs with effects, bonuses, key-value
   strings, and a tech tree JSON.
3. **Units:**
   - fal concept art (white product render, saturated blue accents where player colour should go);
   - fal Trellis image-to-3D → GLB;
   - Blender renders from AoE2's camera: orthographic, 30° elevation, 16 headings clockwise from east, plus
     a shadow-catcher pass (`um render3d --preset aoe2 --shadows`);
   - blue accents hue-masked into the player-colour layer (`um sprite team-mask`);
   - packed into `.sld` sprites.
4. **SLD format:** reverse-engineered from the game's own files, with a reader and writer in
   `examples/aoe2-de-civ/sld.py`. Layers: BC1 main, BC4 shadow, BC1 damage mask, BC4 player colour.
   Frames are 4x4 blocks with skip/draw commands. It was validated by round-tripping the stock knight to
   0.9/255 mean error: decode → encode → decode, then compare.
5. **Demo:** a scenario built with AoE2ScenarioParser (units, triggers, camera). The game was driven through
   the lobby with WinDrive, recorded with gfxcapture plus process-loopback audio, and cut with one-line
   titles.

**Facts that cost time**
- A mod that contains a `.dat` is a **data mod**. It only applies when picked in the skirmish lobby's
  "Data Mod" dropdown. The Mod Manager shows local mods with a gear icon, not a checkbox.
- The civ picker only lists civs the executable knows. Its civ-id table ends at the last official civ, and
  the UI icon tables are index-based. A new civ must replace a slot (the Burgundians, 36). Extra civs load
  and play but never appear in the picker.
- DE key-value strings keep DLL help strings at `id - 79000`. For example, Knight help `105068` → key
  `26068`.
- In-game command-panel icons come from the base game's prebuilt `widgetui` atlas, which a local mod can't
  extend. Use stock icons in game, and your art in the menus, civ picker and tech tree.
- Tech 266 "Castle built" never fires for castles placed by a scenario. Castle unique units need
  `creatable_type` 2.
- NVENC H.264 is limited to 4096 px wide. For a 5120x1440 screen, capture the centre 2560x1440, or use HEVC.
- Registry `HKCU\Software\Microsoft\Microsoft Games\Age of Empires II DE`:
  - `Mode Display` 0 is windowed, 1 is full screen;
  - `Windowed Width/Height` accepts any size, bypassing the in-game list that stops at 1366x768.
    1936x1119 gives a 1920x1080 client area.
- A windowed game can drop the foreground on clicks. The input tool treats "nothing in the foreground, and
  the cursor is over the game" as safe.
- A crash leaves BugSplat's `BsSndRpt64.exe` running, and Steam then refuses to launch the game ("already
  running"). Kill it by PID before relaunching.

## Minecraft inside GTA V: a passthrough mashup

**Route: passthrough.** Real Minecraft Java 26.3 (a Fabric mod) runs next to GTA V story mode (a
ScriptHookV ASI + ReShade add-on). They exchange camera, ground, input and events over a local WebSocket, and
Minecraft's colour + depth frames over shared memory. The depth-tested composite happens in GTA's frame.
Code: `examples/minecraft-gta5-passthrough`.

**Facts that cost time** (the full list, with causes and fixes, is in
`knowledge/games/gta-v/minecraft-passthrough.md`):
- **Minecraft 26.3's GL backend:** it leaves the read buffer at `GL_NONE` after a depth readback. Colour
  readbacks fail until it's restored.
- **ReShade:** it must load through GTA's ASI loader, because the system `dxgi.dll` wins over a proxy.
- **Blocks one frame ahead:** the script reads the camera for the frame being prepared, so re-project
  Minecraft to the previous pose.
- **Timing:** everything is timed with the same high-resolution clock on both sides (Java `nanoTime` = QPC);
  `GetTickCount` judders.
- **Guns vs weapons:** host-game guns on a guest avatar looked wrong. Guest weapons with host-game effects
  (arrows → GTA bullets, fireworks → GTA explosions) worked.
- **The human at the keyboard:** never focus GTA's landing page while they're typing. Keystrokes there
  nearly started GTA Online with a modified game. ScriptHookV blocked it.

## What the 2026 AI mashup wave added

These projects appeared on X in September 2026: skateboarding in MW2, Minecraft inside Skyrim, Elden Ring
and Mario 64, Black Ops 2 inside Minecraft, a Majora's Mask recomp extended by Opus. See the
**mashup-mods** skill.
- **The biggest ones are reimplementations, not injection hacks.**
  - IW4L is a Rust MW2 runtime that reads the user's own MW2 files.
  - The Skate 3 Rust engine was built against a static recomp as its oracle.
  - Minecraft comes from a Rust rewrite.

  The fusion then happens in one process. Nothing from the original games is committed.
- **"Passthrough" mods** run both games at once, with a mod in each that talks over local IPC. The guest's
  geometry goes into the host's renderer; collisions go back to the guest.
- **Long agent runs survive through:**
  - hard oracles: scripted game runs with screenshots and dumps, byte-matching, build-and-verify;
  - an on-disk journal;
  - bounded attempts (circuit breakers);
  - a human for playtesting.
