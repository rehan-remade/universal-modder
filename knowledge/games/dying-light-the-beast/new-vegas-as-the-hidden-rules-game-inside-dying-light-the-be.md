---
kind: game
title: 'New Vegas as the hidden rules game inside Dying Light The Beast: FNV''s own hits, deaths, VATS and menus on stand-ins'
game: 'Dying Light: The Beast'
games_also:
- 'Fallout: New Vegas'
game_version: 'The Beast 1.7.1 (Steam 3008130, pinned after Steam pushed 1.8.1); FalloutNV.exe 1.4.0.525 (Steam 22380, 4GB-patched); Windows 11 (Shadow cloud PC)'
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
anti_cheat: none in single player; co-op never used
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-05'
links:
- ../../techniques/bridge-contracts-ownership-units-and-lifecycle.md
- ../../techniques/collision-and-combat-bridging.md
tags:
- passthrough
- hidden-game
- rules-engine
- stand-in-actors
- xnvse
- asi-loader
- vats
- pip-boy
- version-pinning
---
# New Vegas as the hidden rules game inside Dying Light The Beast: FNV's own hits, deaths, VATS and menus on stand-ins

The player plays Dying Light: The Beast; Fallout: New Vegas runs hidden next to it and decides the numbers. Every hit
Kyle lands becomes a hit by the player's own FNV Courier on an FNV stand-in actor (an existing FalloutNV.esm record
chosen per Beast enemy type), computed by FNV's own hit function; FNV's result is applied back to The Beast's enemy.
FNV's real Pip-Boy, level-up, loot and VATS menus are shown over The Beast while it is frozen. Verified live on 11-05
and 11-06 (numbers in Verification); a one-click start/stop was dry-run on a copy of the player's profile.

## Setup
- The Beast 1.7.1. Steam pushed 1.8.1 mid-project and the plugin's offsets went passive; the old build came back
  with Steam's `download_depot` (the 1.7.1 manifests) and the game is started from its exe directly, so Steam never
  checks for an update. Keep the newer files aside if you'll want them later.
- FNV through MO2 with the Viva New Vegas stability set (the linked note). Two MO2 profiles: a test profile with a
  copy of the player's save, and the player's own (never used for probes). FNV runs hidden: `bAlwaysActive=1`,
  Stewie's `bNoAltTabPause=1`, `bDisableAutoVanityMode=1` (else FNV's idle camera blocks the Pip-Boy), and the
  plugin sleeps FNV down to 40 fps while hidden.
- Three processes talk through a local hub: the Beast ASI (hits, kills, enemy types, its clock, button requests),
  the xNVSE plugin (FNV's rules), and a viewer that shows FNV's hidden window over The Beast for FNV's menus.

## Route and why
Pass-through, never a rebuild: no formula, table or menu of ours imitates FNV. Rebuilding FNV's damage, crit, DT/DR,
limb, XP, loot and VATS rules would drift from the real game and from the player's own character. Where The Beast
has a rule that would compete with FNV's decision (gore kills), that rule is switched off, not reproduced.

## How the game works (what we had to learn)
- **The Beast's enemy types:** max HP can't tell enemies apart (the health presets of biters, humans and others
  overlap, then a session-wide multiplier, x1.4 here, scales them). The HumanAI's actor tag name (HumanAI +0x2518,
  e.g. `infected.volatile.apex`, `human.rifle.base`) can; the death-hint field holds the player-facing name. The
  FNV side keys a data table on the tag's dotted prefix to pick the stand-in record.
- **FNV's hit, without a fight:** the xNVSE plugin places the stand-in in a private interior cell from a tiny ESP
  (the hidden Courier is moved there for the session and back at the end), then calls FNV's own raw weapon damage
  (0x644CE0, cdecl, 8 arguments: the actor-value owner, weapon, condition, a multiplier, two zeros, the inventory
  entry, has-ammo) and `CalculateHitDamage` (0x9B5A30) with a hit-data block (source = the player, target = the
  stand-in, hit location, weapon). DT/DR, perks, criticals and limbs are FNV's. The stand-in's health fraction goes
  back to The Beast, whose enemy health is held and then brought to that fraction (measure, correct, repeat).
- **FNV's unarmed weapon:** with nothing equipped the player's process has no weapon entry, so the call above can't
  run. FNV's own default unarmed weapon is a global pointer at 0x11CA278 (JIP calls it `g_fistsWeapon`; Johnny
  Guitar `pDefaultUnarmedWeapon`); FNV's hit math puts it into hits that have no weapon. FNV's own unarmed raw
  damage is the same raw-damage function called with a NULL weapon and a NULL inventory entry (one of its callers
  does exactly that, with condition and multiplier 1.0): the function null-checks both, takes the Unarmed skill
  (actor value 0x2D) for a NULL weapon and reads UnarmedDamage (0x38). So the pass-through unarmed hit is that call;
  wired in, a Courier with nothing equipped hit a Feral Ghoul stand-in for 3.75 per punch (60 -> 52.5 HP in two).
  The `fHandDamage*` settings only appear in setup and teardown code in 1.4.0.525.
- **Deaths:** The Beast's gore system kills on its own thresholds (63 lethal damage actions in a script table inside
  `data0.pak`). A `data2.pak` with the same entry and those thresholds at 0% (built from the player's own pak at
  install time, nothing shipped) leaves deaths to FNV; FNV's death is then dealt to The Beast's enemy.
- **Freezing The Beast for an FNV menu:** `IGame::FreezeTimersOnLevels`; music and sfx are ducked through the
  player's own audio levels and given back. The focus-loss pause is a separate path (the game's
  `OnGameConstrained`, a GameDI_PH virtual), so it can be skipped without touching Esc/Start.
- **FNV's menus on demand:** FNV's own commands through its console interface (for example `ShowLevelUpMenu`); the
  Pip-Boy opened in 33 ms. A pad hook on FNV's `XInputGetState` hands hidden FNV a neutral pad except while its
  menu is up and The Beast has muted its own input (a handshake with a 0.3 s timeout).
- **Saves:** autosaves are off during a session; at the end the Courier goes back to the stored place and FNV saves
  into a NEW slot, never over an existing save.

- **Incoming hits (FNV decides the damage Kyle takes):** FNV's own "attacker hits target" is 0x899CB0, a
  `__thiscall` on the attacker with (target, bool, projectile, hit type); FNV's melee code calls it with no
  projectile. Called on the attacker's stand-in with the hidden Courier as the target, FNV builds the hit from
  the stand-in's own weapon, runs its hit math and applies it (`target->0x89A760`). Never call it on a stand-in
  placed in the same frame: its process and 3D aren't ready, and FNV's code faults.
- **Heals:** the Courier uses one of its own Stimpaks through FNV's EquipItem (0x88C650), the same path as the
  Pip-Boy, so Medicine and Hardcore's heal-over-time are FNV's.
- **The Beast's damage categories:** a biter's bites and claws arrive as category 0 in the damage info (+0x31);
  1 is a projectile. Filtering on 2/3 only (the player-side melee categories) missed every bite.
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
- **Damage categories (SDamageInfo +0x31):** a biter's bites 0, the player's melee 2/3, a rifleman's shots 4 (not 1);
  a filter on "projectile = 1" missed every gunshot. Kicks are damage source 34, and the grab-escape push arrives at
  the enemy's DamageModule::OnDamage (gamedll 0x14d23c0) with the player as attacker and no hit event.
- **An NPC's shot, decided by FNV:** FNV has no to-hit roll for NPC fire outside VATS (only spread). Spawning the
  attacker's own projectile (Projectile::Spawn 0x9BCA60; its init 0x9BBEF0 takes the shooter's weapon entry and ammo)
  60 units in front of the target lets FNV's own impact (0x9C30D0 -> 0x899CB0) decide damage, location and limbs; the
  reply arrived ~15-110 ms after the shot. Calling 0x9C30D0 directly also works, without a body part.
- **First hits:** a stand-in created on the shooter's first hit faults FNV's hit code in the same call; placing
  stand-ins from the host's enemy list (only enemies whose own target is the player) at least 1.2 s ahead makes
  every first hit FNV's.
- **FNV's HUD by capture:** cut FNV's own HUD pieces from its hidden window and key its amber colour
  (smoothstep(0.12, 0.30, r - b)); the grey arena drops out. xNVSE's `GetUIFloatInherited "HUDMainMenu/<tile>/x"`
  gives each tile's place by FNV's own locus rule.

## Build steps
1. Pin The Beast (above) and install the ASI loader; deploy the Beast plugin plus flag files next to it.
2. MO2 + the Viva New Vegas set; enable the bridge's xNVSE plugin, the arena ESP and the play-flag files.
3. Build and deploy `data2.pak` from the player's `data0.pak` (The Beast closed).
4. Start: the hub, FNV hidden on the player's newest save, the viewer, then The Beast's exe. Stop: close The Beast
   first (the session end makes FNV move the Courier home and write its checkpoint), then close FNV.

## Verification
- Live (11-05): FNV's level-ups and perk menus, kill XP through FNV's death path, the loot menu with the pad, VATS
  with The Beast frozen through FNV's playback, FNV's Pip-Boy over The Beast, the first hit held for FNV, enemy
  types mapped (a Volatile becomes a Deathclaw stand-in).
- DT-1 (11-06): FNV's 10mm hits brought the Beast enemy to FNV's numbers within 0.25% of its max HP.
- Dry run (11-06), on a copy of the player's profile: one-click start in 42 s; 59.9 fps with the plugin costing
  0.03-0.06 ms per frame; F2 -> FNV's Pip-Boy in 33 ms; stop wrote FNV's checkpoint in a new slot; the player's real
  profile hash-identical afterwards.
- Live (11-06): FNV's death dealt as the kill blow (DT-2); FNV's unarmed hit through the whole bridge; enemy melee
  hits on Kyle decided by FNV's own hit on the hidden Courier (bites at FNV's 20 per hit); a Beast medkit = one of
  the Courier's own Stimpaks, and none left = no heal.
- Live (11-06, later): an enemy FNV killed mid-grab dies through The Beast's own escape + kill; kicks and the
  grab-escape push = FNV's unarmed attack (3.75 at level 1); every first bite FNV's; a host rifleman's shots = the
  stand-in's own FNV gun (34 / 12 / 34), Kyle following; a soak with the combat pilot: no stuck deaths, no drift.
- NOT verified yet: food (it heals through a different controller than medkits), grenades, bows.

## Gotchas
1. **The plugin went passive one morning.** **Cause:** Steam auto-updated The Beast. **Fix:** `download_depot` the
   old manifests and start the exe directly, never through Steam's Play.
2. **The Beast's main menu ignored automated mouse input.** **Cause:** the "modified data" warning can be pending
   without showing. **Fix:** press Enter first; then relative mouse moves (-1500,-1500 twice, then +900,+1260 at
   1920x1080) put the cursor on Continue, and a click works.
3. **"WARNING: Your game appears to be using modified data" at every start.** **Cause:** a CRC list of the paks
   (`[AuthenticateData] Bad crc data2.pak!` in its log). **Fix:** expected with any data2.pak; tell the player to
   press Enter.
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
9. **A startup task of another app renamed the ASI loader (`winmm.dll` -> `.melty-off`).** **Fix:** the launcher
   renames it back before each start.
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
    encrypted on disk. **Fix:** read code from the running process; don't strip the DRM.
16. **Medkit presses and shots did nothing during a test fight.** **Cause:** a biter's repeated "bites" are a grab
    (The Beast's tap-F mini-game); while grabbed the player can't use items or shoot. **Fix:** test heals with no
    enemy (a developer-only op that sets the player's HP) and hold the medkit key through its animation.
17. **An enemy FNV had killed kept biting at 0 HP.** **Cause:** FNV's death was dealt while the biter held the
    player in a grab; The Beast defers a grabbing AI's death until the grab ends. **Fix:** count an enemy dead only
    on The Beast's own kill, hold every hit from an attacker FNV says is dead, and press The Beast's own grab escape
    for the player; the deferred death then runs (live: ~1.2 s).
18. **An item given by the game's own quest-reward call never reached the quick slot.** **Cause:** it went to the
    player's stash. **Fix:** test with items the save already carries.

## Assets
None: every menu, number and item is FNV's own; The Beast's art is untouched.

## Cost and time
Two days of sessions (11-04 to 11-06) with a main agent and up to three helper agents on a Pro plan.

## Open questions
- Which other host hits arrive as category 4 (grenades?), and whether bows / shotguns can use FNV's own weapons.
- FNV's UI units for the HUD tile rects (the menu root reports no width), so the capture can be cut at FNV's rects.
- The D3D12 fatal after spawns: the spawned AI's streaming, or the cloud PC's GPU?
