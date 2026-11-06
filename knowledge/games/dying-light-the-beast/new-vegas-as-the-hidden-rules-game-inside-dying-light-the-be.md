---
kind: game
title: 'New Vegas as the hidden rules game inside Dying Light The Beast: FNV''s own hits, deaths, VATS and menus on stand-ins'
game: 'Dying Light: The Beast'
games_also:
- 'Fallout: New Vegas'
game_version: 'The Beast 1.7.1 (Steam 3008130, pinned after Steam pushed 1.8.1, public build 26402545, on 2026-11-05); FalloutNV.exe 1.4.0.525 (Steam 22380, public build 1510068, 4GB-patched); Windows 11 (Shadow cloud PC)'
platform: windows
engine: unknown
route: passthrough
tools:
- Ultimate ASI Loader 10.0.0 (winmm.dll) for the Beast plugin
- xNVSE 6.4.9
- JIP LN NVSE 57.30
- lStewieAl's Tweaks 10.05
- Mod Organizer 2.5.2 (portable)
- a Python 3 hub (TCP, JSON lines) between the two plugins and an overlay
- ViGEmBus virtual pad (tests only)
anti_cheat: 'none listed: Steam starts DyingLightGame_TheBeast_x64_rwdi.exe directly, and its store data shows no anti-cheat or third-party DRM. No step edits that exe. The game has online co-op, so this is single player only with the online setting off; co-op was never used'
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-06'
links:
- ../../techniques/bridge-contracts-ownership-units-and-lifecycle.md
- ../../techniques/collision-and-combat-bridging.md
- ../../techniques/choosing-a-mashup-route.md
- ../../techniques/evidence-levels-for-mashup-claims.md
- ../../techniques/rebuilt-guest-engine-inside-a-host.md
- ../fallout-new-vegas/ai-companion-in-fallout-new-vegas-through-an-xnvse-jip-file-.md
- https://vivanewvegas.moddinglinked.com/
- https://github.com/xNVSE/NVSE
- https://github.com/jazzisparis/JIP-LN-NVSE
- https://github.com/carxt/JohnnyGuitarNVSE
- https://github.com/ThirteenAG/Ultimate-ASI-Loader
- https://github.com/GooseMcGee/DyingLight-GMod
tags:
- mashup
- passthrough
- hidden-game
- rules-engine
- stand-in-actors
- xnvse
- asi-loader
- c-engine
- vats
- pip-boy
- version-pinning
---
# New Vegas as the hidden rules game inside Dying Light The Beast: FNV's own hits, deaths, VATS and menus on stand-ins

The player plays Dying Light: The Beast; Fallout: New Vegas runs hidden next to it and decides the numbers. Every hit
Kyle lands becomes a hit by the player's own FNV Courier on an FNV stand-in actor (an existing FalloutNV.esm record
chosen per Beast enemy type), computed by FNV's own hit function; FNV's result is applied back to The Beast's enemy.
The hits Kyle takes go the other way: the enemy's stand-in hits the hidden Courier, and Kyle's health follows FNV's.
FNV's real Pip-Boy, level-up, loot and VATS menus are shown over The Beast while it is frozen. Verified live on
2026-11-05 and 2026-11-06 with both real games running (numbers, and what isn't verified yet, in Verification); a
one-click start/stop was dry-run on a copy of the player's profile. It's for single player, offline, and nothing from
either game ships.

## Setup
- **Single player, offline.** The Beast has online co-op for up to four players (Steam page), and Techland's servers
  count what players do: its "Call of the Beast" events add up kills across the community. This mod changes damage and
  who dies, so keep it out of sessions with other people. While the loader and `data2.pak` are installed, keep the
  game's online setting on offline single-player (online, private and friends-only all open co-op). To go online, take
  both out and restart the game. Co-op with the mod was never run.
- The Beast 1.7.1. Steam pushed 1.8.1 mid-project and the plugin's offsets went passive; the old build came back
  with Steam's `download_depot` (the 1.7.1 manifests, on the account that owns the game) and the game is started from
  its exe directly, so Steam never checks for an update. Keep Steam running on that account: this skips the update
  check, not Steam's ownership check. The exe itself isn't edited (the ASI loader is a proxy DLL next to it). Keep the
  newer files aside if you'll want them later.
- FNV through MO2 with the [Viva New Vegas](https://vivanewvegas.moddinglinked.com/) stability set. That set's 4GB
  patch (Roy Batty and LuthienAnarion's FNV 4GB Patcher) edits `FalloutNV.exe` on disk, Steam wrapper included: the
  wrapper still runs and the code stays encrypted (gotcha 15), and the original is kept as `FalloutNV_backup.exe`.
  Every run here had it. Nothing in the bridge is known to need it, so try `nvse_loader.exe` on the exe as installed
  first (untested with this bridge), as in the
  [xNVSE file-bridge note](../fallout-new-vegas/ai-companion-in-fallout-new-vegas-through-an-xnvse-jip-file-.md), which
  runs the same xNVSE and JIP versions. Two MO2 profiles: a test profile with a copy of the player's save, and the
  player's own (never used for probes). FNV runs hidden: `bAlwaysActive=1` and `bDisableAutoVanityMode=1` in its INI's
  `[General]` (without the second, FNV's idle camera blocks the Pip-Boy), Stewie's `bNoAltTabPause=1`, and the plugin
  sleeps FNV down to 40 fps while hidden.
- Three processes talk through a local hub: the Beast ASI (hits, kills, enemy types, its clock, button requests),
  the xNVSE plugin (FNV's rules), and a viewer that shows FNV's hidden window over The Beast for FNV's menus. What this
  hub binds to wasn't recorded. Bind it to `127.0.0.1` with a token (`skills/mod-any-game/references/safety.md`):
  anything that reaches it can ask FNV for hits and menus.

## Route and why
Pass-through, never a rebuild: no formula, table or menu of ours imitates FNV. Rebuilding FNV's damage, crit, DT/DR,
limb, XP, loot and VATS rules (the [rebuilt-guest route](../../techniques/rebuilt-guest-engine-inside-a-host.md), or
the mashup skill's pattern 5) would drift from the real game and from the player's own character. Where The Beast
has a rule that would compete with FNV's decision (gore kills), that rule is switched off, not reproduced.

In [choosing-a-mashup-route.md](../../techniques/choosing-a-mashup-route.md)'s terms this is live passthrough (state
exchange) with a hidden guest, as in ValCraft and Killcraft (`skills/mashup-mods/references/mashup-cases.md`), plus a
separate viewer showing FNV's window for its menus. The nearest public relative on a Techland host is
[GModLight](https://github.com/GooseMcGee/DyingLight-GMod): Garry's Mod hidden next to the first Dying Light, with
stand-ins, through the same ASI loader. Who owns what, in the terms of the
[bridge contract note](../../techniques/bridge-contracts-ownership-units-and-lifecycle.md): The Beast owns Kyle,
movement, the camera and the world; FNV owns the hit numbers both ways (Kyle's hits, and bites, gunshots and shotgun
pellets on Kyle through the hidden Courier), medkit heals, deaths, XP, loot and its menus. Food, explosions, fire and
bows are still open (Verification, Open questions). Anyone running this needs both games, each from their own install.

## How the game works (what we had to learn)
- **The Beast's enemy types:** max HP can't tell enemies apart (the health presets of biters, humans and others
  overlap, then a session-wide multiplier, x1.4 here, scales them). The HumanAI's actor tag name (HumanAI +0x2518,
  e.g. `infected.volatile.apex`, `human.rifle.base`) can; the death-hint field holds the player-facing name. The
  FNV side keys a data table on the tag's dotted prefix to pick the stand-in record.
- **FNV's hit, without a fight:** the xNVSE plugin places the stand-in in a private interior cell from a tiny ESP
  (the hidden Courier is moved there for the session and back at the end), then calls FNV's own raw weapon damage
  (0x644CE0, cdecl, 8 arguments: the actor-value owner, weapon, condition, a multiplier, two zeros, the inventory
  entry, has-ammo) and `CalculateHitDamage` (0x9B5A30) with a hit-data block (source = the player, target = the
  stand-in, hit location, weapon). DT/DR and perks are FNV's rules. With JIP's `bIgnoreDTDRFix=1` (the default in
  `jip_nvse.ini`), 0x9B5A30 jumps to JIP's rewrite of that function, so the numbers are FNV's rules with JIP's fix;
  turn it off to compare with the game's original code. That rewrite has no critical roll and doesn't compute limb
  damage, so those come from elsewhere in FNV's hit path, and no run here measured them (Verification). The stand-in's
  health fraction goes back to The Beast, whose enemy health is held and then brought to that fraction (measure,
  correct, repeat).
- **FNV's unarmed weapon:** with nothing equipped the player's process has no weapon entry, so the call above can't
  run. FNV's own default unarmed weapon is a global pointer at 0x11CA278 (JIP calls it `g_fistsWeapon`; Johnny
  Guitar `pDefaultUnarmedWeapon`); FNV's hit math puts it into hits that have no weapon. FNV's own unarmed raw
  damage is the same raw-damage function called with a NULL weapon and a NULL inventory entry (one of its callers
  does exactly that, with condition and multiplier 1.0): the function null-checks both, takes the Unarmed skill
  (actor value 0x2D) for a NULL weapon and reads UnarmedDamage (0x38). All of that was read from the running process
  (gotcha 15). So the pass-through unarmed hit is that call: with FNV alone, a Courier with nothing equipped hit a
  Feral Ghoul stand-in for 3.75 per punch (60 -> 52.5 HP in two), and later the whole bridge carried it (Verification).
  The `fHandDamage*` settings only appear in setup and teardown code in 1.4.0.525.
- **Deaths:** The Beast's gore system kills on its own thresholds (63 lethal damage actions in a script table inside
  `data0.pak`). A `data2.pak` with the same entry and those thresholds at 0% (built from the player's own pak at
  install time, nothing shipped) leaves deaths to FNV. FNV's death is then dealt to The Beast's enemy (DT-2 in
  Verification); an enemy holding Kyle in a grab only dies once the grab ends (below).
- **Freezing The Beast for an FNV menu:** `IGame::FreezeTimersOnLevels`; music and sfx are ducked through the
  player's own audio levels and given back. The focus-loss pause is a separate path (the game's
  `OnGameConstrained`, a GameDI_PH virtual), so it can be skipped without touching Esc/Start.
- **FNV's menus on demand:** FNV's own menus, opened by commands through its console interface (for example xNVSE's
  `ShowLevelUpMenu`, which calls FNV's level-up menu); the Pip-Boy opened in 33 ms. A pad hook on FNV's
  `XInputGetState` hands hidden FNV a neutral pad except while its menu is up and The Beast has muted its own input (a
  handshake with a 0.3 s timeout).
- **Saves:** autosaves are off during a session; at the end the Courier goes back to the stored place and FNV saves
  into a NEW slot, never over an existing save.
- **Incoming hits (FNV decides the damage Kyle takes):** FNV's own "attacker hits target" is 0x899CB0, a
  `__thiscall` on the attacker with (target, bool, projectile, hit type); FNV's melee code calls it with no
  projectile. Called on the attacker's stand-in with the hidden Courier as the target, FNV builds the hit from
  the stand-in's own weapon, runs its hit math and applies it (`target->0x89A760`). Never call it on a stand-in
  placed in the same frame: its process and 3D aren't ready, and FNV's code faults.
- **Heals:** the Courier uses one of its own Stimpaks through FNV's EquipItem (0x88C650), the same path as the
  Pip-Boy, so Medicine and Hardcore's heal-over-time are FNV's.
- **The Beast's self-opening pause is an idle timer:** 300 s without input (LogicalPlayer m_State +0x704 bit 0,
  set when a +0x36cc accumulator passes 300.0); focus loss, a pad unplug or another window in front never pause it.
- **FNV's VATS only targets a stand-in in the Courier's view.** Place stand-ins where the host's enemies really
  are (a reader of the host's world feeding the placement); fixed spots ~40 deg off the facing never open VATS.
- **Telling The Beast's medkit apart from other heals:** medkits, food and other consumables all reach the player's
  `Heal()` from the same call site, and the healing tuples carry ids, not names. Logging the call stack in the heal
  callback (`RtlCaptureStackBackTrace`, return addresses as gamedll RVAs) and naming each frame's function (its
  `.pdata` bounds, then the RTTI class of any vtable slot that holds it) showed the medkit's path runs through
  `SelfHealingController` (vtable slot 143), the only caller of the next frame down; everything below is the
  generic item path with many callers. Two of those return addresses (1.7.1) are the medkit signature. Blocking that
  heal and asking FNV instead, a medkit became one of the Courier's own Stimpaks (9 -> 8; Hardcore healed it over
  ~6 s and Kyle's bar followed); with no Stimpak FNV refused and nothing healed.
- **The Beast's medkit is hold-to-use:** hold H (or the pad's X) for about 2.4 s, through the animation; taps and
  short holds do nothing (`_ACTION_USE_CONSUMABLE` in `data0.pak` `scripts/inputs/inputs_keyboard.scr`).
- **The Beast defers a grabbing enemy's death.** An enemy that holds the player in a grab (a sync action with the
  tap-F escape) does not die at 0 HP; The Beast runs its death by itself the moment the grab ends (the player's escape,
  UV light, or the player's death). To carry out an outside death mid-grab: hold that enemy's hits, then press The
  Beast's own escape (`_ACTION_TAP_MINIGAME`, F / pad X) through the input hook; its kill follows ~1.2 s later.
- **The Beast's damage categories (SDamageInfo +0x31):** a biter's bites and claws 0, the player's melee 2/3, a
  rifleman's shots 4 (not 1, as first assumed for projectiles). A filter on 2/3 only (the player-side melee categories)
  missed every bite, and one on "projectile = 1" missed every gunshot. Kicks are damage source 34, and the grab-escape
  push arrives at the enemy's DamageModule::OnDamage (gamedll 0x14d23c0) with the player as attacker and no hit event.
- **An NPC's shot, decided by FNV:** FNV has no to-hit roll for NPC fire outside VATS (only spread). Spawning the
  attacker's own projectile (Projectile::Spawn 0x9BCA60; its init 0x9BBEF0 takes the shooter's weapon entry and ammo)
  60 units in front of the target lets FNV's own impact (0x9C30D0 -> 0x899CB0) decide damage, location and limbs; the
  reply arrived ~15-110 ms after the shot. Calling 0x9C30D0 directly also works, without a body part.
- **A shotgun's pellets, decided by FNV:** FNV's own projectiles-per-shot getter (`TESObjectWEAP` 0x525B20, thiscall
  `(perks, skip_ammo, actor)`, `ret 0xC`: the weapon's +0x11E or its ammo's own count, then the perk entry point) gives
  the count; spawning that many of the shooter's own projectiles the way the single shot above is spawned lets FNV's
  impact decide every pellet (live: a Caravan Shotgun, 7 of 7 pellets, 38 per shot). Calling FNV's own
  `TESObjectWEAP::Fire` (0x523150) on the stand-in does not work for this: it takes the direction from a 3D node's
  world transform (the gun's barrel in the animation), so turning the reference first doesn't aim the pellets.
- **First hits:** a stand-in created on the shooter's first hit faults FNV's hit code in the same call; placing
  stand-ins from the host's enemy list (only enemies whose own target is the player) at least 1.2 s ahead makes
  every first hit FNV's.
- **FNV's HUD by capture:** cut FNV's own HUD pieces from its hidden window and key its amber colour
  (smoothstep(0.12, 0.30, r - b)); the grey arena drops out. xNVSE's `GetUIFloatInherited "HUDMainMenu/<tile>/x"`
  gives each tile's place by FNV's own locus rule.

## Build steps
1. Pin The Beast (above) and install the ASI loader; deploy the Beast plugin plus flag files next to it (the exe Steam
   starts is `ph_ft\work\bin\x64\DyingLightGame_TheBeast_x64_rwdi.exe`).
2. MO2 + the Viva New Vegas set; enable the bridge's xNVSE plugin, the arena ESP and the play-flag files.
3. Build and deploy `data2.pak` into `ph_ft\source` from the player's `data0.pak` (The Beast closed).
4. Start: the hub, FNV hidden on the player's newest save, the viewer, then The Beast's exe. Stop: close The Beast
   first (the session end makes FNV move the Courier home and write its checkpoint), then close FNV.

## Verification
The Live and DT runs are real runs with both real games going together, in the sense of
[evidence-levels-for-mashup-claims.md](../../techniques/evidence-levels-for-mashup-claims.md): The Beast 1.7.1 and
FalloutNV.exe 1.4.0.525 on the Shadow PC. A stand-in is a real FNV actor in the running game, not a fake peer.
- Live (2026-11-05): FNV's level-ups and perk menus, kill XP through FNV's death path, the loot menu with the pad, VATS
  with The Beast frozen through FNV's playback, FNV's Pip-Boy over The Beast, the first hit held for FNV, enemy
  types mapped (a Volatile becomes a Deathclaw stand-in).
- DT-1 (2026-11-06): FNV's 10mm hits brought the Beast enemy to FNV's numbers within 0.25% of its max HP.
- Dry run (2026-11-06), on a copy of the player's profile: one-click start in 42 s; 59.9 fps with the plugin costing
  0.03-0.06 ms per frame; F2 -> FNV's Pip-Boy in 33 ms; stop wrote FNV's checkpoint in a new slot; the player's real
  profile hash-identical afterwards.
- Live (2026-11-06): FNV's death dealt as the kill blow (DT-2); FNV's unarmed hit through the whole bridge; enemy
  melee hits on Kyle decided by FNV's own hit on the hidden Courier (bites at FNV's 20 per hit); a Beast medkit = one
  of the Courier's own Stimpaks, and none left = no heal.
- Live (2026-11-06, later): an enemy FNV killed mid-grab dies through The Beast's own escape + kill; kicks and the
  grab-escape push = FNV's unarmed attack (3.75 at level 1); every first bite FNV's; a host rifleman's shots = the
  stand-in's own FNV gun (34 / 12 / 34), Kyle following; a soak with the combat pilot: no stuck deaths, no drift.
- Live (2026-11-06, evening): a stand-in carrying FNV's Caravan Shotgun hit the Courier with 7 of 7 FNV pellets per
  shot (38 a shot); a scripted play session on a copy of the player's profile: all 46 hits on the player FNV's, none
  of the host's numbers, FNV's XP for kills, its loot menu and VATS over the host, medkits as FNV Stimpaks.
- NOT verified yet: food (it heals through a different controller than medkits), grenades, flamers, bows; criticals
  and limb damage on the enemies Kyle hits (DT-1 only measures 10mm numbers); a run on the unpatched FNV exe;
  anything in co-op or online (never run, and not what this is for).

## Gotchas
1. **The plugin went passive one morning.** **Cause:** Steam auto-updated The Beast (1.8.1 went live on 2026-11-05).
   **Fix:** `download_depot` the old manifests and start the exe directly, never through Steam's Play. Steam's per-game
   "Only update this game when I launch it" should also stop background updates (not tried here).
2. **The Beast's main menu ignored automated mouse input.** **Cause:** the "modified data" warning can be pending
   without showing. **Fix:** press Enter first; then relative mouse moves (-1500,-1500 twice, then +900,+1260 at
   1920x1080) put the cursor on Continue, and a click works. That's the player's real mouse: ask them first, and not
   while they're typing.
3. **"WARNING: Your game appears to be using modified data" at every start.** **Cause:** a CRC list of the paks
   (`[AuthenticateData] Bad crc data2.pak!` in its log). **Fix:** expected with any data2.pak; tell the player to
   press Enter. That isn't a go-ahead for co-op: in the first Dying Light this is the multiplayer check (the engine
   exports `IGame::AreDataAuthenticatedToPlayMultiplayer`, and players quote the warning there as limiting you to
   players with the same mods).
4. **Kyle died to "residents" right after an AI spawn.** **Cause:** Safe Haven's courtyard holds seven dormant
   biters that wake when something spawns. **Fix:** test elsewhere or clear them first.
5. **Every hit used The Beast's damage for the player's real character.** **Cause:** the Courier had weapons but
   none equipped, so FNV's weapon path had no entry. **Fix:** with no weapon entry, make FNV's own unarmed call
   (above); equipping a weapon in FNV's Pip-Boy still changes the numbers, as in FNV.
6. **The stop script missed FNV's checkpoint save.** **Cause:** The Beast ignored the first WM_CLOSE while its own
   pause was up (a virtual pad had just unplugged: "Controller Disconnected"). **Fix:** ask again every 20 s.
7. **A newly plugged virtual pad's first press did nothing in FNV.** **Cause:** the first press after a pad arrives
   is eaten. **Fix:** in tests, keep one pad plugged (a serve mode) and expect to press twice once.
8. **FNV's console stayed open after a scripted `load` and froze The Beast.** **Cause:** the closing key landed
   during the load; FNV's menu mode read 3. **Fix:** after a load, re-tap the console key until FNV reports no menu.
9. **A startup task of another app renamed the ASI loader (`winmm.dll` -> `.melty-off`).** **Cause:** that suffix is
   how the Melty mashup launcher switches off a game's proxy DLL. **Fix:** our start script renames it back before each
   start.
10. **The Beast crashed once, 4 s after a spawn ("D3D12 ... FAILED VALIDATE_HR").** **Cause:** a fatal the game
    raised itself (its crash reporter's own capture call in the stack; nothing in the plugin); unexplained. Crash
    reports were moved aside, never sent without the player's say.
11. **FNV crashed when the session ended during its VATS.** **Cause:** removing the VATS target and moving the
    Courier with VATS up (once because a tutorial box on top ate the single back-out press). **Fix:** press FNV's
    own B again every second and never end while VATS is open.
12. **VATS pressed right after a kill went nowhere.** **Cause:** FNV starts its kill camera a frame after the kill.
    **Fix:** refuse the VATS button while FNV's kill camera runs and for ~0.35 s after a kill.
13. **A background Python opened a visible console.** **Cause:** a venv's python.exe is a launcher; detached, its
    child got a new console window. **Fix:** start background readers with the venv's pythonw.exe.
14. **No save at the end of a session.** **Cause:** an FNV pop-up left open held the Courier's move home. **Fix:**
    the session end waits for the player to close it (nothing of ours presses OK).
15. **Byte-scanning FalloutNV.exe for known addresses found nothing.** **Cause:** the Steam exe's code is
    encrypted on disk (xNVSE's loader recognises that exe by its `.bind` section, and the 4GB patch doesn't change
    this). **Fix:** read code from the running process; don't strip the DRM. Any dump stays private, outside any repo.
16. **Medkit presses and shots did nothing during a test fight.** **Cause:** a biter's repeated "bites" are a grab
    (The Beast's tap-F mini-game); while grabbed the player can't use items or shoot. **Fix:** test heals with no
    enemy (a developer-only op that sets the player's HP) and hold the medkit key through its animation.
17. **An enemy FNV had killed kept biting at 0 HP.** **Cause:** FNV's death was dealt while the biter held the
    player in a grab; The Beast defers a grabbing AI's death until the grab ends. **Fix:** count an enemy dead only
    on The Beast's own kill, hold every hit from an attacker FNV says is dead, and press The Beast's own grab escape
    for the player; the deferred death then runs (live: ~1.2 s).
18. **An item given by the game's own quest-reward call never reached the quick slot.** **Cause:** it went to the
    player's stash. **Fix:** test with items the save already carries.
19. **A scripted play session froze for 19 minutes.** **Cause:** FNV's DLC notices ("Dead Money Loaded") can open ~30 s
    after a load, mid-play; the host stays frozen for FNV's menu, and the script pressed X / B on it. **Fix:** A (OK)
    on FNV's message boxes, never X / B.
20. **FNV's first VATS ignored the queue and fire presses.** **Cause:** FNV's one-time VATS tutorial opens on top
    ~0.7 s after VATS. **Fix:** close it (B), then queue (RT) and fire (A).
21. **The test pilot swung at air while a biter bit from behind.** **Cause:** a "swing at what's in front" goal, and
    spawns placed "ahead" of a player who had since turned (into the residents' pen). **Fix:** aim at the spawned
    enemy's id, and walk back to a known spot facing the open courtyard before each spawn.
22. **An automated Esc (to close the host's idle pause) stopped the combat pilot.** **Cause:** the pilot halts on Esc,
    taking it as a human taking over. **Fix:** re-arm it after an automated Esc.
23. **Medkits used during a fight never healed.** **Cause:** The Beast cancels its medkit when the player is hit
    while using it. **Fix:** heal away from attackers (in the player's notes too).
24. **Test runs could have changed the host's campaign save.** **Cause:** a respawn rewrites it, and it sits in the
    folder Steam Cloud syncs. **Fix:** tests end the host by its exact PID before its own respawn, back the save up
    first (`um backup create`) and check its hash after every run.

## Assets
None: every menu, number and item is FNV's own; The Beast's art is untouched. Nothing from either game ships and no
package goes with this note: the plugins, hub, viewer and ESP are the author's own, FNV's records and menus come from
the player's install at run time, and `data2.pak`, which holds Techland's script table, is built on the player's
machine and stays there. Any later release keeps to that: Techland's
[mod policy](https://techland.net/upload/Techland_Modpolicy.pdf) allows non-commercial mods of The Beast, but no
content that infringes someone else's rights.

## Cost and time
Two days of sessions (2026-11-04 to 2026-11-06) with a main agent and up to three helper agents on a Pro plan.

## Open questions
- Which other host hits arrive as category 4 (grenades?), and how explosions, fire and bows can be FNV's (FNV's own
  explosion would also reach the stand-ins around the hidden Courier).
- FNV's UI units for the HUD tile rects (the menu root reports no width), so the capture can be cut at FNV's rects.
- The D3D12 fatal after spawns: the spawned AI's streaming, or the cloud PC's GPU?
- Surviving patches: the plugin's fixed offsets are why The Beast is pinned. GModLight's
  [engine notes](https://github.com/GooseMcGee/DyingLight-GMod/blob/main/docs/ENGINE_ANALYSIS.md) (first Dying Light,
  the creator's report) find classes by exported names and RTTI, which may hold up better across patches. Not tried
  here.
- A co-op guard: the same notes plan to switch off when `IGame::AreDataAuthenticatedToPlayMultiplayer` says so or a
  session is active. Here it would be a safety net against joining by mistake, not a way to play online with the mod.

## Credits
[xNVSE](https://github.com/xNVSE/NVSE), [JIP LN NVSE](https://github.com/jazzisparis/JIP-LN-NVSE) and
[Johnny Guitar NVSE](https://github.com/carxt/JohnnyGuitarNVSE), whose sources name many of the FNV functions and
addresses used here (the others were read from the running game); lStewieAl's Tweaks; the [Viva New Vegas](https://vivanewvegas.moddinglinked.com/) guide;
[Ultimate ASI Loader](https://github.com/ThirteenAG/Ultimate-ASI-Loader);
[Mod Organizer 2](https://github.com/ModOrganizer2/modorganizer); [ViGEmBus](https://github.com/nefarius/ViGEmBus).
