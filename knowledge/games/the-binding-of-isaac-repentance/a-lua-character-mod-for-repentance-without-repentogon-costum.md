---
kind: game
title: 'A Lua character mod for Repentance+ without REPENTOGON: costumes, custom NPC and familiar AI, sounds, Birthright'
game: 'The Binding of Isaac: Repentance+'
games_also: []
game_version: 'Steam, Repentance+ (save/log folder "Binding of Isaac Repentance+"); changelog.txt top entry still reads v1.7.9b, so check the in-game version string'
platform: windows
engine: native
route: loader-api
tools:
- built-in Lua mod API (no REPENTOGON)
- Python + Pillow/numpy (sprites, WAV conversion, spectrograms)
- faster-whisper small (transcribing Japanese and Russian voice lines, word timestamps)
- demucs htdemucs_ft (separating voice from music in anime clips)
- imageio-ffmpeg (an ffmpeg binary from PyPI when none is installed)
anti_cheat: none (single-player; online co-op not touched)
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-24'
links:
- https://wofsauge.github.io/IsaacDocs/rep/
tags:
- isaac
- lua
- custom-character
- familiar
- custom-npc
- sounds
- anm2
- subtitles
- voice-lines
- mod-config-menu
---
# A Lua character mod for Repentance+ without REPENTOGON: costumes, custom NPC and familiar AI, sounds, Birthright

A custom character (Yoshikage Kira from JoJo) for The Binding of Isaac: Repentance+, built only with the vanilla
Lua API (no REPENTOGON): wig and jacket null-costumes, a custom hurt frame, custom hurt voice lines, an active item
that summons a friendly ground NPC with its own pathfinding AI, a toggleable stand familiar with a Brimstone-style
charge bar, and a switchable Birthright. It runs in the real game; the human played it and reported bugs with
screenshots and `log.txt`. The newest fixes (see Verification) haven't been retested yet.

## Setup
- Steam, Windows 10, Repentance+. Mods live in `<game>\mods\<folder>` (`content/` for XML, `resources/` for
  gfx/sfx, `main.lua` at the root). The log is `Documents\My Games\Binding of Isaac Repentance+\log.txt`.
- The game ships its Lua enums as `<game>\resources\scripts\enums.lua`. Grep it to confirm that every
  `SoundEffect.*`, `ModCallbacks.*` and `UseFlag.*` name you use exists in *this* build.
- Unpacked vanilla data (`entities2.xml`, `sounds.xml`, `gfx/*.anm2`) was already in `<game>\extracted_resources`
  (it comes from the ResourceExtractor in the game's `tools` folder). It's handy for copying animation names, pivots and XML attributes.
- The "Debug Console Enabler" mod gives the `~` console: `giveitem c619` gives Birthright.
- No local Lua interpreter was available; `uvx --from lupa python -c "...load(src)..."` was a quick syntax check
  (Lua 5.4 parser, close enough for 5.3 code).

## Route and why
Plain Lua mod API (`loader-api`). REPENTOGON would add APIs (custom Birthright text, costume queries, rewind),
but the human didn't have it and wanted a mod that runs on stock Repentance+. Everything below works around the
missing APIs.

## How the game works (what we had to learn)
- **Character:** `content/players.xml` (`skin=`, `hp`, `armor` = soul hearts, `nameimage`, `portrait`), with menu
  art in `content/gfx/characterportraits.anm2` / `charactermenu.anm2`. The animation name inside them must equal
  the player `name`. `Isaac.GetPlayerTypeByName(name, false)` gives the player type.
- **Costumes:** `content/costumes2.xml` + `Isaac.GetCostumeIdByPath("gfx/characters/x.anm2")`, worn with
  `player:AddNullCostume(id)`. A costume anm2 needs one animation per player animation it should show in
  (`HeadDown/Right/Up/Left`, `WalkDown...`, `ShootDown...`). Player animations it doesn't cover (pickup/lift, Hit,
  Death) simply hide the costume.
- **Hurt frame:** the player's Hit pose is one cell of the skin sheet (layout from `001.000_player.anm2`). Editing that
  cell in a copy of the skin and pointing `players.xml skin=` at it is far more reliable than swapping costumes
  on damage. The same cell is reused by Death, FallIn, JumpOut and DeathTeleport.
- **Custom NPCs:** an `entities2.xml` entry with an unused `id` (777 worked; vanilla tops out around 967 plus
  1000/9001) gives an NPC with no built-in AI. It's driven entirely by `MC_NPC_UPDATE` filtered on that type.
  `npc.Pathfinder:FindGridPath(pos, speed, 900, true)` + `HasPathToPos` give ground pathfinding that avoids rocks
  and pits when `GridCollisionClass = GRIDCOLL_GROUND`. `FLAG_FRIENDLY` + `CanShutDoors = false` keep it out of
  room clearing.
- **Custom familiars:** `id="3"` with a new `variant` gives a familiar with no AI, driven by `MC_FAMILIAR_INIT/UPDATE`
  with a variant filter. `Isaac.Spawn(3, variant, 0, pos, v, player)` works. The entity can vanish across rooms,
  so keep an `EntityPtr` in the player's `GetData()` and respawn it when it's gone.
- **Custom effects:** `id="1000"` + a new variant + your own anm2 make a purely Lua-driven visual (`MC_POST_EFFECT_UPDATE`).
  Effects move by `Velocity`.
- **Sounds:** `content/sounds.xml` `<sounds root="sfx/">` → files in `resources/sfx/`; `<sample weight="1" path=.../>`.
  Several samples in one `<sound>` = a random pick each play. `Isaac.GetSoundIdByName`, `SFXManager():Play(id, vol, 0, loop, pitch)`.
- **Explosions:** `Game():BombExplosionEffects(pos, dmg, TearFlags.TEAR_NORMAL, Color.Default, source, radiusMult, lineCheck, damageSource, DamageFlag.DAMAGE_EXPLOSION)`
  behaves like a bomb: it breaks rocks, pots and doors, and it hurts players. For a blast that only hurts enemies, spawn
  `EffectVariant.BOMB_EXPLOSION` as a visual (set `SpriteScale`) and apply damage yourself with
  `Isaac.FindInRadius(pos, r, EntityPartition.ENEMY)` + `TakeDamage`.
- **Input:** the keyboard Ctrl key is `ButtonAction.ACTION_DROP`. `MC_INPUT_ACTION(entity, hook, action)` can swallow it for
  one player (`return false`, or `0.0` for `InputHook.GET_ACTION_VALUE`). Wrap your own `Input.IsActionTriggered`
  read in a guard flag so the callback doesn't block you as well. `player:GetShootingJoystick()` gives the aim
  vector even while tears are firing.
- **Charge bar:** load the vanilla `gfx/chargebar.anm2` into a `Sprite()`: `Charging` (frames 0-100, use
  `SetFrame`), `StartCharged`, `Charged` (loop), `Disappear`. Update it at 30 Hz in `MC_POST_PLAYER_UPDATE`, render in
  `MC_POST_PLAYER_RENDER`, and skip `RenderMode.RENDER_WATER_REFLECT`.
- **Rewind:** there's no direct rewind API, but `player:UseActiveItem(CollectibleType.COLLECTIBLE_GLOWING_HOUR_GLASS, flags, -1)`
  triggers the Glowing Hourglass effect (back to the previous room, with health as it was on entering the current one).
  2026-10-24, later builds of this mod: on vanilla Repentance+ that call did not move the player back a room in our
  tests; `Isaac.ExecuteCommand("rewind")` (the console command) did. It also silences every playing sound (gotcha 25).
- **Subtitles / custom text:** a mod font is a BMFont (binary v3 `.fnt` + `_0.png`) loaded with `Font():Load(path)`;
  `DrawStringScaledUTF8` / `GetStringWidthUTF8` handle Cyrillic. The path that worked is
  `mods/<mod folder>/resources/font/x.fnt` (gotcha 27). Draw in `MC_POST_RENDER` with `CallbackPriority.LATE` so text
  sits above the mod's own full-screen effects.
- **Mod Config Menu (optional dependency):** register settings in `MC_POST_GAME_STARTED` only if the global
  `ModConfigMenu` exists. `OptionType.BOOLEAN`, `NUMBER` (use it as an enum) and `KEYBIND_KEYBOARD` cover toggles,
  languages and hotkeys. Its font has no Cyrillic, so labels are Latin. Persist the values yourself through `SaveData`.
- **Damage interception:** `MC_ENTITY_TAKE_DMG` on players; `return false` cancels the hit. Use `amount` (half
  hearts) against `GetHearts() + GetSoulHearts()` to detect a lethal hit; skip it when `GetBoneHearts() > 0` or the
  Holy Mantle effect is up.

## Build steps
1. Make `mods/<name>/metadata.xml`, `content/players.xml`, the skin in `resources/gfx/characters/costumes/`, and
   the menu anm2s in `content/gfx/`.
2. Costumes: an anm2 per costume with Head*/Walk*/Shoot* animations, registered in `costumes2.xml` and added in
   `MC_POST_PLAYER_INIT` and `MC_POST_NEW_ROOM`. Don't add them every frame (Gotcha 3).
3. Custom NPC / familiar / effect: one `entities2.xml` entry each, and AI in `main.lua` keyed by
   `Isaac.GetEntityTypeByName` / `GetEntityVariantByName`.
4. Sounds: convert to WAV 44100 Hz 16-bit mono with a clean 44-byte header (Gotcha 4), and register them in `sounds.xml` with `root="sfx/"`.
5. Write one `Isaac.DebugString("[Mod vN] ...")` line at load time with every ID the mod resolved. When the human
   sends `log.txt`, it shows at once whether the XML was picked up (`-1` or `nil` means it wasn't).
6. Keep a numbered changelog in the mod folder and copy the whole mod folder before each change. The human tests
   between iterations, so being able to roll back any stage was used more than once.

7. Voice lines with subtitles: one `<sound>` per phrase (so the code knows exactly which line played and can show its
   text), a table `key -> speaker -> variants`, an optional `weight` per variant, and one line at a time per speaker
   (urgent keys interrupt, an idle monologue yields to anything). A line without a registered sound
   (`Isaac.GetSoundIdByName` returns -1) still shows as a subtitle, so text can ship before audio.

## Verification
- **Oracle:** the human played each stage and reported back. The agent read `log.txt` (the load line with all IDs,
  plus Lua errors of the form `Error in "<Callback>" call: <file>:<line>: ...`) and looked at the screenshots the human sent.
- **Confirmed in game:**
  - character, menu art, costumes and hurt frame;
  - hurt sounds (after the `sounds.xml` crash fix);
  - the active-item NPC hunting, sticking and exploding;
  - the stand familiar charging, dashing and exploding without breaking rocks (once the conflicting mod was disabled, Gotcha 14);
  - Stray Cat bubbles.
- **Not yet verified:**
  - the charge-bar camera fix (Gotcha 12);
  - hiding the hourglass lift animation (Gotcha 15);
  - random spread on the bubbles.
- The agent never ran the game itself; every "works" above is the human's report.

## Gotchas
1. **`player:GetPlayerIndex()` crashes the callback** ("attempt to call a nil value"), and nothing after it runs (in our
   case the wig never went on). **Cause:** not in this build's API. **Fix:** use `player.ControllerIndex` as the key.
2. **"Is this costume worn?" checks always fail.** **Cause:** `player:GetCostumeSpriteDescs()` returns nil here.
   **Fix:** don't query costumes. Keep your own state and re-add costumes on init and on new room.
3. **The wig always faces forward and flickers.** **Cause:** calling `AddNullCostume` every frame recreates it. **Fix:** add it on
   `MC_POST_PLAYER_INIT`, `MC_POST_GAME_STARTED` and `MC_POST_NEW_ROOM` only (`TryRemoveNullCostume` first to avoid doubles).
4. **The game crashes on load after adding sounds.** **Cause, confirmed by bisection** (the human swapped files one at a time): `content/sounds.xml`
   was missing `root="sfx/"`. Also OGG was used for an sfx, and 48 kHz WAVs sounded distorted. **Fix:**
   `<sounds root="sfx/">` and WAV 44100 Hz 16-bit mono. ffmpeg-made WAVs carry a `LIST` chunk between `fmt` and `data`.
   We rewrote them with a bare 44-byte header to be safe; whether that was needed is unconfirmed.
5. **A sound or effect stops working after restarting the run (R).** **Cause:** `Game():GetFrameCount()` restarts at 0, so
   cooldowns stored as absolute frame numbers become "forever". **Fix:** reset them in `MC_POST_GAME_STARTED` and
   whenever `frame < stored`.
6. **A costume swapped inside `MC_ENTITY_TAKE_DMG` gets reverted.** **Cause:** the game resets player visuals while it
   processes the hit. **Fix:** do it next frame in `MC_POST_PLAYER_UPDATE`. For a hurt face, edit the skin's Hit cell instead (see above).
7. **The vanilla Isaac grunt still plays over a custom hurt voice.** **Cause:** the game plays sounds 55-57 after the
   damage callback. **Fix:** in `MC_POST_UPDATE`, `SFXManager():Stop()` them for about 12 frames after the hit. Note that this mutes them for every player in co-op.
8. **The character's legs vanish with a jacket costume.** **Cause:** a costume layer named `body` replaces the body.
   **Fix:** name the layer `body0` (it draws on top), and copy the timing from the player's Walk animations.
9. **A side-facing sprite looks the wrong way.** **Cause:** the art was already drawn facing left and the anm2 also
   mirrored it (`XScale=-100`). **Fix:** check which way the sheet faces before adding a mirror.
10. **A friendly NPC "reaches" an enemy but takes ages to trigger.** **Cause:** entity collision pushes the two apart,
    so a centre-distance check rarely passes. **Fix:** trigger in `MC_PRE_NPC_COLLISION` (return `true` to skip the
    push), keep a distance check (sizes plus about 10 px) as a fallback, then attach to the enemy (copy its position and
    velocity each frame, and set `ENTCOLL_NONE` / `GRIDCOLL_NONE` while attached).
11. **The NPC's own bomb explosion hurts the player.** **Cause:** `BombExplosionEffects` damages players. **Fix:** in the
    player's `MC_ENTITY_TAKE_DMG`, return `false` for `DAMAGE_EXPLOSION` whose `source.Type`/`Variant` is your
    entity, plus a 2-frame window stamped just before the call (in case the source ref is lost).
12. **The charge bar draws far from the player in big rooms.** **Cause:** `Isaac.WorldToScreen()` already includes
    the camera scroll, and adding the `offset` passed to `MC_POST_PLAYER_RENDER` counts it twice. In 1x1 rooms the
    offset is zero, so the bug hides there. **Fix:** `WorldToScreen(player.Position) + player.PositionOffset + yourOffset`.
13. **Familiar hits feel unreliable.** **Cause:** the familiar draws 36 px above its real `Position`
    (`PositionOffset`), so the visible fist and the hit point don't match. A fast dash can also step over a small
    enemy. **Fix:** check 2-3 points along the per-frame path with `FindInRadius` and a slightly larger radius.
14. **The stand's punch never explodes, with no error from our mod.** **Cause:** an old Afterbirth+ mod ("JoJo's Kira
    and DIO", Workshop 1147968105) was also enabled. On Repentance+ it throws a Lua error in its PostRender/PostUpdate
    every frame (hundreds per minute in `log.txt`), and with it enabled our familiar's punch logic didn't fire. Exact
    mechanism not isolated. **Fix:** disable it. Lesson: when a feature silently doesn't work, grep `log.txt` for
    errors from *other* mods before debugging your own.
15. **Glowing Hourglass shows the item-lift animation even with `UseFlag.USE_NOANIM`, and costumes disappear during it.**
    **Cause:** the lift is an extra animation that costumes don't cover. **Fix (unverified):** call
    `player:StopExtraAnimation()` right after `UseActiveItem` and for about 45 frames (and on `MC_POST_NEW_ROOM`), when
    `not player:IsExtraAnimationFinished()`.
16. **Ctrl on a character with a stand also drops trinkets.** **Cause:** Ctrl is `ACTION_DROP`. **Fix:** swallow it
    for that character in `MC_INPUT_ACTION` (with the guard flag described above).
17. **Another mod's Workshop entity is named like yours.** Custom entity names are global. Prefix every
    `entities2.xml` name with your mod/character (`"Kira Killer Queen"`, not `"Killer Queen"`).

18. **A "once per floor" ability works again after Exit → Continue (found by the human).** **Cause:** state kept only in
    Lua variables or `GetData()` is wiped when the run is saved and resumed. **Fix:** persist it with
    `mod:SaveData(json.encode{...})` (`local json = require("json")` ships with the game), both right when it's used
    and in `MC_PRE_GAME_EXIT`. Load it in `MC_POST_GAME_STARTED` when `isContinued`, and only if the saved run seed
    (`Game():GetSeeds():GetStartSeed()`) and `Level:GetStage()/GetStageType()` match. On load the order is
    `MC_POST_NEW_LEVEL` → `MC_POST_NEW_ROOM` → `MC_POST_GAME_STARTED`, so a "reset on new floor" in
    `MC_POST_NEW_LEVEL` must not save, or it overwrites the file before you load it. Also, Glowing Hourglass used in
    the first room of a floor can rewind to the previous floor and fire `MC_POST_NEW_LEVEL`. Ignore new-level resets for a
    few seconds after your own rewind.
19. **A modded item's icon never shows (empty active slot next to the charge bar, no pedestal sprite), and the log has no error.**
    **Cause:** `gfx=` in `content/items.xml` is only a file name. The game always looks in
    `resources/gfx/items/collectibles/` (with `gfxroot="gfx/items/"`), so `gfx="collectibles/x.png"` silently resolves
    to `collectibles/collectibles/x.png`. **Fix:** `gfx="x.png"` with the file in `resources/gfx/items/collectibles/`,
    which is what vanilla `items.xml` and other mods do. Compare against another mod's XML before trusting your own path.
20. **A body costume (a jacket on `body0`) is barely visible and doesn't animate with walking.** **Cause:** on a
    stock Isaac-sized character the head covers rows ~13..17 of the 32x32 body cell, so only a 3-4 px strip of
    torso shows. A costume is one static frame per direction, while the legs animate under it. **Fix:** recolor the
    body directly in your copy of the skin sheet. Torso rows (<= 19 relative to the walk pivot 16,25) become the
    jacket and leg rows become trousers, in every cell the player anm2's `body` layer uses: 20 walk cells of 32x32,
    plus the 64x64 "carry item overhead" cells with pivot 32,44, where you keep the raised hands skin-colored. Keep
    only small details (shirt, tie, buttons) in the costume, placed in the strip below the head. Map the three skin
    shades 1:1 to three cloth shades so the original shading survives.
21. **A feature dies with "attempt to call a nil value" although the function exists in main.lua.** **Cause:** in a
    single big `main.lua`, a `local function` is visible only BELOW its declaration. A function defined higher up
    that calls it sees an undefined global instead. A syntax check (luaparser) passes, and the error only appears when
    that code path runs in game. Patching new helpers into a long file makes this easy to miss. **Fix:** declare
    shared helpers before their first caller. Also run a check that lists top-level locals used above their
    declaration: strip strings and comments, record the line of each `local` name, then regex-search earlier lines.
    This caught a charged-punch crash in this mod that had shipped unnoticed for five versions.
22. **The carry-item pose ("PickupWalk*") looks like a shapeless blob of clothing over the chin.** **Cause:** those
    animations draw the 32x32 arms-up body cells (`extra` layer) ON TOP of the head, so recoloring the whole cell
    covers the lower face. **Fix:** recolor only the outer sleeves with a darker inner edge, make the middle of the
    cell transparent so the head's chin shows through, and put the collar on the first row below the chin. Also,
    in "UseItem" (64x64 cell 64,192) the wig sits over the upper arms: the visible hands start lower than in the
    vanilla sheet.
23. **The whole mod silently stops working: no character, no items, while `luaparser` says the syntax is fine.**
    **Cause:** Lua allows at most 200 `local` names in one function, and the main chunk of `main.lua` counts as one. Each
    tuning constant (`local KQ_X = ...`) used one slot, and the file reached 271. The log says
    `main.lua:NNN: too many local variables (limit is 200) in main function`, and the game runs none of the file.
    **Fix:** move constants into one table (`local K = {}` then `K.NAME = ...`, uses become `K.NAME`), or split the
    code into several files with `include`. Check `log.txt` after the first launch of every build, and count top-level
    locals in CI. A side benefit: table fields resolve at call time, so constants can't hit the
    "used above its declaration" problem from gotcha 21.

24. **Voice lines keep playing in the pause menu, and loops (engine hum, heartbeat) run forever while paused.**
    **Cause:** `SFXManager` has no pause or seek, and `MC_POST_UPDATE` stops running while paused, so nothing stops
    them. `Game():IsPaused()` is also true for a few frames during room transitions. **Fix:** in `MC_POST_RENDER`
    (it keeps running while paused) count paused frames; after ~30 render frames stop your voice and loop sounds,
    and after unpausing replay the current phrase from its start (loops are restarted by their own update code).
    Split long monologues into one sound per phrase so a resume repeats one sentence, not a minute of audio. Stop
    everything in `MC_PRE_GAME_EXIT` too. (Reported by the human; the fix itself is not yet re-tested.)
25. **A voice line started right before `Isaac.ExecuteCommand("rewind")` fades out at once.** **Cause:** the rewind
    is a room transition and silences all sounds. **Fix:** say only a short shout before it and queue the rest; play
    the queued line once the room index has changed (we poll after the rewind and play it when nothing is speaking).
26. **A hotkey toggles on and straight back off in some rooms.** **Cause:** in rooms with water reflections the game
    calls `MC_POST_RENDER` a second time for the reflection (`Room:GetRenderMode() == RenderMode.RENDER_WATER_REFLECT`).
    **Fix:** return at the very top of the callback in that render mode, before reading keys or advancing timers.
27. **Subtitles never appear; the log has no error.** **Cause:** `Font:Load("font/x.fnt")` resolves to the game's own
    font folder, not the mod's `resources/font/`. **Fix:** try `mods/<mod folder>/resources/font/x.fnt` (confirmed
    in `log.txt` by logging which path loaded), and fall back to a vanilla font with Cyrillic
    (`font/pftempestasevencondensed.fnt`, drawn at 2x) so text still shows if the custom font fails.
28. **WAV size.** 22050 Hz 16-bit mono WAVs play correctly: the vanilla game ships a couple itself (e.g.
    `spewer death scream 1.wav`), and it also has 48 kHz stereo files, so the distortion in gotcha 4 was probably the
    file header, not the rate. Converting only speech to 22050 Hz cut this mod's sounds from 15 to 7.5 MB with no
    audible loss; keep explosions and clicks at 44100 Hz.

## Assets
- **Sprites:**
  - The wig, jacket, hurt head, menu art and portraits were supplied by the human and cut and fitted with Pillow (nearest-neighbour).
  - The bubble effect is procedural (Pillow: an ellipse with rim and highlight, 4 float frames and 4 pop frames), with the anm2 written by a script.
  - The stand sprite came from another Workshop mod, for personal use only. Don't publish someone else's sprites without permission.
- **Voice lines:**
  - The human supplied rips of the character's voice pack (206 files) and a sound-effect pack. The agent transcribed
    every line locally with faster-whisper `small` (`language="ja"`) to find usable lines. It used spectrograms
    (numpy FFT → PNG) to tell processed robot-voice lines and engine/tread loops from clean speech.
  - Gotchas from that pipeline: newer faster-whisper calls `av.open(..., metadata_errors=...)`, so pin
    `av==12.3.0`. `python -I` ignores `PYTHONIOENCODING`, so call `sys.stdout.reconfigure(encoding="utf-8")` in the script
    or Japanese output crashes on Windows cp1251.
  - No ffmpeg was on the machine. WAVs were resampled with an FFT resample in numpy and written with a hand-built
    44-byte header. A seamless loop was made by crossfading the last 0.3 s into the start.
- A second pack (the character's later form, 216 files) had the lines the Birthright needed. A line remembered from the
  anime turned out not to exist in the game at all: check the transcripts before promising a specific quote.
- When the fal balance ran out mid-session, the agent drew the art procedurally instead (Pillow, a few hundred
  lines): a 3-view tank (front/side/back, side mirrored with `sprite.FlipX`, view picked from velocity with a 1.2x
  hysteresis so diagonals don't flicker), a 32x32 item icon, and a bubble effect. Recipe: per-part shapes, a
  "light from top-left" ramp of 3-4 shades per material, then an automatic 1-px dark outline around every opaque
  pixel. The human liked this chunky look, and every iteration stays a one-line edit in the script.
- Later voice lines and a Russian dub option were cut from anime episodes the human supplied (Japanese release and a
  Russian voice-over dub). Pipeline, all local:
  - find the line from subtitle timestamps (± a few seconds: releases drift), cut a window with ffmpeg
    (`imageio-ffmpeg` provides a binary), separate voice from music with demucs `htdemucs_ft --two-stems=vocals`,
    then transcribe with faster-whisper `word_timestamps=True` and cut on word boundaries;
  - background songs with lyrics stay in the "vocals" stem and can't be removed; a noise-gate in pauses (−32 dB)
    helps only between words;
  - a voice-over dub keeps the original Japanese audio quietly underneath, and demucs keeps both voices: mute
    everything outside the dub's word spans. Whisper sometimes puts a word start 0.1–0.3 s late (cuts the first
    letter) or glues a sob/the other language onto the first word, so fix those cuts by hand from the loudness curve;
  - re-transcribe every finished file to check nothing is clipped. The human still caught the rest by ear.
  - Demucs did not install through `uv run --with` on Windows (a scanner held the cache files); a normal venv with
    `UV_LINK_MODE=copy` and pinned `torch==2.5.1 torchaudio==2.5.1 numpy<2` worked. It fails on mono input: duplicate the channel.
- None of the game's own files, the voice rips or the episode audio go into this repo.

## Cost and time
About 60 numbered stages over several sessions (many were small art/offset tweaks); this agent did roughly the last 15 (stages 46-59), with the human testing between them.
No API spend: all asset processing ran locally.

## Open questions
- Is ~30 render frames the right debounce between a real pause and a room transition for `IsPaused()`?
- Can a modded character's Birthright pickup text be customised without REPENTOGON? We show our own
  `HUD:ShowItemText` when Birthright is first detected, as a stand-in.
- Is the hourglass animation fix enough, or does the rewind itself re-add the lift animation in the destination room?
- Which part of the old JoJo mod broke the familiar (a shared global? its `MC_INPUT_ACTION`?) is still unknown.
