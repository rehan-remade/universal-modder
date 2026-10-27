---
kind: game
title: 'A Viewpoint companion HUD end to end: sonar ring mod, ISUI drawing, ModOptions, translations, mod.info and the Kahlua
  gotchas'
game: Project Zomboid
games_also: []
game_version: 'Build 42.21.0 (Steam 108600), Windows 10. Companion mod for Viewpoint 0.1.6.1 (workshop 3809306528) on its ZombieBuddy Java loader; the mod itself is pure client Lua'
platform: windows
engine: java
route: loader-api
tools: ["PZ Lua (Kahlua 5.1) mod API", "ISUI (ISUIElement)", "PZAPI.ModOptions", "javap over projectzomboid.jar", "Viewpoint Lua surface (Viewpoint.View/Keys/Pads/Loot/Mouse)", "Events.OnWorldSound", "IsoGameCharacter:getDetectionRange"]
anti_cheat: "none on the client (servers run their own checks, Lua checksums included). The ring shows zombies the character can't see, so it's for single player; on a server only when the server's own mod list gives it to every player"
status: released
agents:
- ZCode (GLM-5.3)
humans: [Replactionap]
date: '2026-10-26'
links:
- "https://steamcommunity.com/sharedfiles/filedetails/?id=3826427697"
- "https://steamcommunity.com/sharedfiles/filedetails/?id=3809306528"
tags: [b42, viewpoint, first-person, hud, isui, drawrect, modoptions, translations, mod-info, kahlua, events, onworldsound, detection-range, workshop, luaparser]
---
# A Viewpoint companion HUD end to end: sonar ring mod, ISUI drawing, ModOptions, translations, mod.info and the Kahlua gotchas

> Built and shipped Hearing Radar (workshop item 3826427697): a client-side Lua HUD for Project Zomboid B42 that
> draws a sonar ring around the crosshair showing zombies within the character's hearing range (the game's own
> `getDetectionRange()`, plus a 1-tile bonus by default) behind walls and on other floors too, designed as a
> single-player companion for the Viewpoint first/third person camera mod. Route: pure Lua over the game's own
> event and Java API surface — no Java classes, no loaders. Verified in the real game across all three camera
> modes by the human playtesting; the log lines and several bytecode dives confirmed the engine facts below.

## Setup
- Project Zomboid **42.21.0** from Steam (app 108600), Windows 10. User data in `%USERPROFILE%\Zomboid\`
  (`console.txt`, `Logs\<date>_DebugLog.txt`, `Saves\`, `mods\`, `Workshop\`).
- Viewpoint **0.1.6.1** (workshop 3809306528) with its **ZombieBuddy** Java loader (`require=\ZombieBuddy`,
  `javaJarFile=media/java/client/Viewpoint.jar`). Not required to run Hearing Radar, but the mod was designed
  around its cameras.
- Mod dev folder during work: `Zomboid/mods/<id>/42/...`; upload folder `Zomboid/Workshop/<name>/` with
  `workshop.txt` + `preview.png` (256x256) + `Contents/mods/<id>/`. Published item: 3826427697.
- Tooling: JDK 21 `javap` over `projectzomboid.jar` for every engine fact below; `luaparser` (pip) to
  syntax-check Lua offline; `um publish check` to lint the mod folder.
- **Multiplayer: single player is the intended use.** The scan keeps every zombie in the cell within
  `getDetectionRange()` plus the bonus (1 tile by default, 0-10 in the options), with no line-of-sight check and
  2D distance. So the ring also shows zombies behind walls and closed doors (silent ones too), zombies on other
  floors, and (with the default bonus) zombies past the game's own perception radius: information the
  character doesn't have. The mod doesn't turn itself off in multiplayer. On a server, the server's `Mods=` list
  decides which mods load for the session (seen on B41 in the
  [B41 server note](b41-modpack-fix-mods-and-linux-dedicated-server.md); not re-checked on B42), so there it only
  runs when it's in that list for every player. Add it only to a server you run, with the players agreeing, and
  never side-load it onto a server that doesn't list it.

## Route and why
Loader API via pure client Lua (`42/media/lua/client/<Mod>/`): the game IS the mod loader, all needed surface is
exposed to Kahlua, and a Lua-only mod ships on the Workshop without any bytecode patching. Considered a Java
companion jar (Viewpoint-style) for camera access but didn't need it: Viewpoint already exports a Lua surface,
and the vanilla API covers positions and angles. Considered an `OnWorldSound`-only design (v0.1) — replaced by
periodic scans (v0.2) after playtesting showed event-driven pings didn't match what the trait actually hears.

## How the game works (what we had to learn)

### Viewpoint's Lua surface and its view cycle
- Viewpoint exposes a global Lua table `Viewpoint` with sub-tables `Keys`, `Pads`, `Loot`
  (`Viewpoint.Loot.setEnabled(bool)`), `Mouse` (`Viewpoint.Mouse.worldX()/worldY()` or nil) and `View`
  (`Viewpoint.View.next()` / `cycle()`). It wraps `ISCoordConversion.ToWorld` for its own mouse picking.
- **`Viewpoint.View.next()` returns the view the next cycle press WOULD switch to, not the current one** (from
  `viewpoint.FP.nextView` bytecode): `!View.enabled` → `"first"`, `View.thirdPerson` → `"isometric"`, else
  `"third"`. Translated to the current view: `next()=="third"` means first person NOW, `"isometric"` means third
  person NOW, `"first"` means the vanilla isometric camera (Viewpoint off).
- Camera math per mode: first and third person are 3D cameras that follow the character's facing — pings placed
  relative to `player:getDirectionAngle()` with the ring at screen centre are correct in both. The vanilla
  isometric camera keeps a fixed orientation: directions there must come from `ISCoordConversion.ToScreen`
  (project player and zombie, take the difference vector — it is immune to zoom and camera offsets). `ToScreen`
  is an isometric projection; using it in a Viewpoint 3D mode gives wrong centres AND wrong directions.

### Hearing: what "Keen Hearing" really is
- `IsoGameCharacter:getDetectionRange()` (public, Lua-callable) is the game's whole hearing formula:
  `(DEAF ? 2 : 3.5) + (KEEN_HEARING ? 3 : 0) - (HARD_OF_HEARING ? 1 : 0)`, clamped to min 2, `+ 2 *
  getWornItemsHearingMultiplier()`, `- FATIGUE`, `- INTOXICATION * 0.01`. So Keen Hearing ≈ 6.5 tiles live,
  no trait ≈ 3.5. A mod should call this instead of re-implementing the numbers.
- The trait id: `player:hasTrait(CharacterTrait.KEEN_HEARING)`; the Java constant's string is `"KeenHearing"`
  while B42 script ids look like `base:keenhearing` — `registerBase` maps legacy names, `CharacterTrait.KEEN_HEARING`
  is the right Lua handle.

### World sounds (the AI noise system)
- Every noise the zombie AI reacts to (footsteps via `IsoGameCharacter.DoFootstepSound`, attacks via
  `IsoLivingCharacter.DoAttack`, thumps, generators, radios/TVs) goes through
  `WorldSoundManager.instance:addSound(...)`, whose `WorldSound.init` triggers Lua event
  **`OnWorldSound(x, y, z, radius, volume, source)`** — `source` is the emitting Java object, so
  `instanceof(source, "IsoZombie")` filters exactly "sounds made by zombies". This is separate from what the
  player hears (FMOD).
- Zombie groans are NOT per-event sounds here; they surface through
  `WorldSoundManager:getSoundZomb(zombie)` / repeating sounds — event-based capture sees groans rarely, which is
  why the sonar scans positions instead.

### ISUI drawing without textures
- A transparent HUD: `ISUIElement:derive("Name")`, override `render()`, `addToUIManager()` once (create on
  `OnGameStart`, guard against re-registration), `drawRect(x, y, w, h, a, r, g, b)` — alpha comes FIRST. A filled
  circle is cheap horizontal slices of `drawRect` (a 4.5 px circle is ~10 rects); the whole ring (36 guide dots +
  16 pings + tails) stays under ~230 rects per frame, with an early return when there is nothing to draw.
- Override the mouse handlers (`onMouseDown` etc.) to return false so the full-screen HUD panel never eats
  clicks. The UI element must be resized on `OnResolutionChange`.

### ModOptions (PZAPI)
- `PZAPI.ModOptions:create(modID, title)` (Lua-side id, independent of mod.info id) → `page:addTickBox`,
  `addSlider(min, max, step, value)`, `addButton(id, label, tooltip, onclick)`; options expose
  `getValue()`/`setValue()` (setValue also updates the on-screen control — a reset button is trivial).
- Values are only written back on OK. `MainOptions` then calls each page's `apply()` hook — override it to pull
  values into live settings; without it, settings need a save reload to take effect.
- The button onclick fires immediately, before OK — it mutates the option values but is only persisted if the
  user then presses OK (engine behaviour, not a bug).

### Translations (B42 JSON)
- Files live at `media/lua/shared/Translate/<LANG>/<TYPE>.json` and are loaded **by type name** — `UI.json`,
  `IG_UI.json`, `ContextMenu.json`... The language is the folder (`EN/`, `RU/`), NOT a filename suffix. B41-style
  `UI_EN.json` is silently never read and every `getText` shows the raw key. Vanilla and working workshop mods
  name files exactly by type; no `language.json` is needed for a mod.
- `getText("Key")` falls back to English when the current language's file lacks the key (vanilla RU files are
  themselves partial and the game ships fine). Keys route by prefix (`UI_`, `IGUI_`, `ContextMenu_`, ...) inside
  the Translator; a flat JSON object per type file is the format.
- Missing key or invalid JSON ⇒ the raw key is displayed — which is exactly how you notice.

### mod.info: what the engine actually parses (42.21.0)
- `ChooseGameInfo.readModInfoAux` parses, per line (contains-match): `name=`, `id=`, repeatable `description=`,
  `poster=`, `icon=`, `url=`, `author=`, `category=`, `modversion=`, `versionMin=`, `versionMax=`, repeatable
  `require=`, `incompatible=`, `loadModAfter=`, `loadModBefore=`, `pack=`, `tiledef=` (two args), `type=`
  (only value `ui` is recognised; anything else logs a Mod warning). **Anything else is silently ignored**
  (`changes=`, `tags=`, `priority=`, `supportedGameBuild=` do nothing, however sensible they look).
- `mod.info` may live in the version folder (`42/mod.info`) or in `common/mod.info` (the modern layout shipped
  by Viewpoint); `ZomboidFileSystem.getModInfoForDir` finds it either way. `poster=` and `icon=` resolve against
  the version dir first, then `common/`; `preview.png` at the workshop upload root is NOT visible to the game
  (it is only the Steam item image).
- **`id=` is not auto-derived from the folder name.** Without it the mod id is the internal default
  `"undefined_id"`. Two working conventions exist: a plain id (`id=Viewpoint` with workshop 3809306528) or the
  workshop item id as the mod id (`id=3826427697`, shipped deliberately by Hearing Radar) — both work, but saves'
  `mods.txt` reference the mod by this id, so changing it after publication orphans saves until the mod is
  re-enabled in the world's mod list.
- The first Workshop upload adds `id=<item>` to `workshop.txt` (and rewrites tags semicolon-separated);
  re-uploading from the same folder updates that item. Upload a folder whose workshop.txt has no `id=` and you
  create a NEW item — keep exactly one upload folder per mod.

### Kahlua (the Lua runtime) quirks that hit real code
- **No global `next()`**: `next(t)` fails with "Object tried to call nil" (an error every render tick if used in
  a draw path). Track a count instead of testing table emptiness.
- **`Events.OnExitGame` does not exist** — registering it fails at file load with "attempted index: Add of
  non-table: null" and the whole mod file dies. The 42.21 event list (from `LuaEventManager` bytecode) includes
  `OnDisconnect`, `OnTick`, `OnTickEvenPaused`, `OnWorldSound`, `OnGameStart`, `OnGameBoot`, `OnCreateUI`,
  `OnResolutionChange`... check before registering.
- Load order is alphabetical per folder: a mod folder named before `PZAPI` loads before the ModOptions API
  exists; `OnGameBoot` has usually already fired by the time a save re-runs mod Lua. Create the options page in
  `OnGameStart` as well (guarded by a `page or return` check) — that is the reliable spot.
- `math.atan2/deg/rad/sin/cos/sqrt/floor`, `table.sort`, `pcall` with closures over Java objects all work;
  world angles are `atan2(dy, dx)` degrees, +x east, +y south.
- `zlist:size()` / `zlist:get(i)` on `getCell():getZombieList()` is the Lua-safe way to iterate zombies; wrap
  every Java call chain in `pcall` because a Kahlua error inside a tick/render handler silently kills that call
  (and spams console.txt).

## Build steps
1. `Zomboid/mods/<id>/42/media/lua/client/<Mod>/<Mod>.lua` (one file; `require "ISUI/ISUIElement"` at top).
2. Events (guarded by a module-level `registered` flag): `OnWorldSound` to mark recently-noisy zombies,
   `OnTick` for the periodic scan (every `scanPeriod` s, iterate the zombie list, keep those within
   `getDetectionRange() + bonus`, nearest 16), `OnGameStart` to create the HUD and options page, plus
   `OnResolutionChange`/`OnDisconnect` cleanup.
3. Draw: `ISUIElement` subclass, ring centre at screen centre, ping direction from facing (Viewpoint 3D modes)
   or `ToScreen` difference (isometric), distance mapped linearly to ring radius (0 = crosshair, edge = hearing
   edge), alpha-faded until the next sweep.
4. Options page via `PZAPI.ModOptions` with an `apply()` hook; translations in `Translate/EN|RU/UI.json`.
5. Upload folder `Zomboid/Workshop/<name>/{workshop.txt, preview.png, Contents/mods/<id>/{common|42}/...}`;
   publish from the main menu, re-upload to update.
6. `changelog.txt`, `README.md` etc. at the upload root are for humans/GitHub; the game reads only
   `Contents/`, `preview.png` and `workshop.txt`.

## Verification
- Oracle 1 — playtest across all three cameras: the human confirmed ring position and ping directions in first
  person, 3D third person and zoomed isometric; that was the acceptance test for every camera-math revision
  (three were needed — see Gotchas 6–8).
- Oracle 2 — logs: unconditional `[HearingRadar] v... loaded` / `HUD attached` lines plus debug-only lines
  (view changes, one-shot `player=... keenHearing=... detectionRange=6.5`, raw sound dumps) in
  `console.txt` / `Logs/*_DebugLog.txt`. The raw-event dump is what proved the `OnWorldSound` argument order
  (radios and TVs arrived as sources first — an easy early sanity check that the hook fires at all).
- Oracle 3 — engine facts from `javap` over the exact installed jar (42.21.0), not from memory or wikis: event
  names, `getDetectionRange` formula, `View.next()` semantics, `readModInfoAux` key list.
- Offline checks: `luaparser` syntax gate before every game launch; a script asserting EN/RU key parity and that
  every `T("...")` key in the Lua exists in both JSONs; `um publish check` on the mod folder.
- Not verified: multiplayer beyond "the base ring works" (the heard-highlight depends on client-side sound
  events); performance under extreme hordes (analytically bounded, not measured); dedicated servers;
  controllers; the `DEAF`/`HARD_OF_HEARING` branches were reasoned from bytecode, not exercised.

## Gotchas
1. **Mod file fails to load: `attempted index: Add of non-table: null`.** Cause: registering
   `Events.OnExitGame`, which does not exist in 42.21 (the stack trace points at the `Events.X.Add` line).
   Fix: `OnDisconnect`; check the event list from `LuaEventManager` bytecode before registering anything.
2. **`Object tried to call nil` every frame in render.** Cause: `next(t)` — Kahlua has no global `next`.
   Fix: keep a counter updated where the table is written, test the counter.
3. **Options page silently missing and debug logs never appear.** Cause: the mod folder sorts before `PZAPI`
   alphabetically, so `PZAPI.ModOptions` is nil at file-load time, and `OnGameBoot` has already fired by the
   time a save re-runs the Lua. Fix: create the page (guarded) in `OnGameStart` too.
4. **Every `getText` shows the raw key.** Cause: translation files named `UI_EN.json` (B41 habit). B42 loads
   `Translate/<LANG>/<TYPE>.json` by type name. Fix: rename to `UI.json` in each language folder.
5. **The published mod shows a different id than intended / saves can't find it.** Cause: a `mod.info` without
   `id=` gets `undefined_id`, and a first upload may end up with the workshop item id substituted; saves bind to
   whatever the id is at first enable. Fix: set `id=` explicitly before publishing; if it changes afterwards,
   re-enable the mod in each world's mod list.
6. **First-person directions wrong after adding projection code.** Cause: `Viewpoint.View.next()` returns the
   NEXT view, not the current one — mode detection was off by one press. Fix: translate (`"third"`→first,
   `"isometric"`→third, `"first"`→isometric) and re-check against `FP.nextView` bytecode.
7. **Third person wrong with isometric math.** Cause: `ToScreen` is an isometric projection; a Viewpoint 3D
   camera follows the character's facing, so facing-relative math with the ring at screen centre is correct
   there. Fix: use projection only for the fixed-orientation isometric camera.
8. **In isometric the ring drifts when zooming.** Cause: anchoring the ring centre to a `ToScreen` position,
   which does not account for zoom. Fix: keep the ring at screen centre in every mode (every PZ camera keeps the
   character centred) and use the projection only as a difference-vector for ping directions.
9. **Settings changed in the menu do nothing until reload.** Cause: values are snapshotted at `OnGameStart`.
   Fix: implement the page's `apply()` hook (called by MainOptions on OK) to refresh live settings.
10. **A zombie stays highlighted after dying/despawning.** Cause: the engine recycles `IsoZombie` objects, so a
    "heard" timestamp keyed by object can be inherited by a fresh zombie. Fix: accepted as cosmetic (2 s window);
    a stronger fix would key on `getOnlineID()`.
11. **In a cursor-driven mode the whole UI freezes: the mode can't be toggled off, inventory clicks dead.**
    Cause: a full-screen `ISUIElement` HUD panel is the topmost element, and clicks reach UI through the
    consume path (`UIManager.updateMouseButtons` → `onConsumeMouseButtonDown/Up`), whose Java wrapper falls
    back to the `consumeMouseEvents` field (default: consume) around the Lua handlers — the sheet swallowed
    every click. In camera-driven modes the game handles the mouse itself, so weeks of testing never showed
    it. Fix (three layers): Lua-override ALL input handlers to return false, including the `onConsume*`
    family; switch the flags off (`setConsumeMouseEvents(false)`, `setCapture(false)` — feature-detect them:
    public in Java does NOT mean callable from Kahlua, a blind pcall prints "Object tried to call nil" to the
    log); and keep the panel no bigger than what it draws (the ring's bounding square, re-laid-out on
    resolution change and option apply) instead of a full-screen sheet. Drawing then becomes panel-local,
    which is simpler anyway.

## Assets
No external assets: everything is drawn with `drawRect` (no textures), the poster/preview are generated
Pillow images, sounds are the game's own. `icon.png`/`preview.png` at 512/256 px are ordinary PNGs referenced by
`mod.info` (`poster=`/`icon=`) and the upload root.

## Cost and time
One working day (2026-10-24) across ~8 game-launch test cycles plus one bytecode-archaeology pass; AI session
time only, no API spend beyond the assistant subscription.

## Open questions
- Does `type=ui` in mod.info (the only parsed `type=` value) change how the game lists a mod?
- Whether `MoodleType.register` or a real minimap-API exists that would make the ring a first-class UI element.
- MP: how reliably `OnWorldSound` fires client-side for server-simulated zombies (would need a dedicated
  server session).
