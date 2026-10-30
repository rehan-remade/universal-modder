---
kind: game
title: "Archaon-style subjugation for Valkia the Bloody: a script-only Warscape mod that reuses CA's own dilemmas"
game: "Total War: WARHAMMER III"
games_also: []
game_version: "9.0.4.0 (Warhammer3.exe), Steam build 25961564, Immortal Empires"
platform: windows
engine: native
route: loader-api
tools: ["campaign Lua (script/campaign/mod)", "twtool.py (agent-written PFH5 pack reader/writer)", "lupa (offline Lua 5.1 tests)", "uv"]
anti_cheat: "none (EOS SDK ships for crossplay only); single-player campaign"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-20
links: []
tags: [warscape, total-war, campaign-script, lua, dilemma, confederation, vassal, legendary-lord, archaon, warriors-of-chaos, khorne]
---

# Archaon-style subjugation for Valkia the Bloody: a script-only Warscape mod that reuses CA's own dilemmas

Valkia the Bloody (Warriors of Chaos) gets a version of Archaon's subjugation mechanic, limited to the Khorne
factions. Beat Skarbrand, Skulltaker or Arbaal and a dilemma offers to take the Legendary Lord into her
recruitment pool and make their faction her vassal. If someone else destroys one of those factions, its lord
later challenges her to a forced battle for the same prize. It's one campaign Lua file with no database
tables, because CA's Archaon dilemmas turned out to be generic enough to reuse. Both features were played
through in the real game (new Immortal Empires campaign, test pack forcing each scenario on turn 1-2).

## Setup
- Total War: WARHAMMER III, Steam app 1142710, `Warhammer3.exe` file version 9.0.4.0, Steam build 25961564,
  Windows 11. Immortal Empires campaign (`main_warhammer`). Needs the DLC that adds Valkia and the
  Champions of Chaos / Archaon rework content (the factions and dilemmas named below).
- Mods are PFH5 `.pack` files. A mod pack can sit in the game's `data\` folder (or a Workshop folder) and is
  enabled in CA's launcher, which writes `used_mods.txt`.
- No RPFM needed for a script-only pack: any PFH5 writer that stores the `.lua` file raw at
  `script\campaign\mod\<name>.lua` works. We used an agent-written Python pack tool; CA's vanilla packs
  are zstd-compressed (u32 uncompressed size, then a zstd frame), so reading them needs `zstandard`.

## Route and why
- **Campaign Lua in `script/campaign/mod/`** (the game's official mod-script hook). Every file there is
  loaded at campaign start; register work with `cm:add_first_tick_callback`.
- `um scan` reports "unknown native engine" for this game and suggests proxy-DLL hooks. That is the wrong
  route: Warscape exposes almost everything a campaign mechanic needs through its Lua campaign manager and
  the DB tables in packs. Nothing here needed native code.
- Considered and rejected:
  - **Exactly copying Archaon** (a hidden per-god "vassal owner" faction that absorbs the beaten faction):
    those factions are in the start position, so a new one for Valkia needs CA's Assembly Kit. Sharing
    Archaon's (`wh3_dlc29_khorne_vassal_owner`) would feed his victory objectives.
  - **Direct cross-culture confederation** (Warriors of Chaos absorbing a Daemons of Khorne faction): CA
    deliberately avoids it, so it's unproven. We used direct vassalage instead, built only from operations
    CA's script already performs across cultures.

## How the game works (what we had to learn)
- **Reading CA's scripts:** unpack the `.lua` files from `data\data_script.pack` (about 1,080 files) and grep.
  For DB rows without a schema, searching `db.pack`'s raw bytes for a key shows which tables reference it
  and the neighbouring string fields.
- **Archaon's mechanic** lives in `script/campaign/wh3_dlc29_archaon_subjugation.lua` and is started from
  `campaign/main_warhammer/wh_start.lua` (Immortal Empires only). Its config maps culture to a subjugation
  type: other Warriors of Chaos factions are **confederated**, the four daemon cultures are **vassalised**
  (lord moved to Archaon, faction merged into the hidden vassal-owner faction). So "Archaon confederates the
  god factions" is not literally true.
- **Trigger 1, beaten in battle:** `cm:add_immortal_character_defeated_listener(name, battle_condition,
  callback(winner_fm, loser_fm), fire_if_faction_destroyed)`. The battle condition checks the pending-battle
  cache (`pending_battle_cache_faction_won_battle`, `..._is_attacker/defender`, `..._get_defender_faction_name`).
  The callback compares the loser's `character_subtype_key()` with the faction's Legendary Lord subtype.
  Immortal lords "die" and respawn, which is why the library hands you family members, not characters.
- **Trigger 2, the battle also destroyed the faction:** the defeat listener doesn't fire for a dead faction
  (with the last argument false), so a `FactionDeath` listener checks `context:killer()` plus the battle
  cache's subtypes and offers the no-leader variant of the dilemma.
- **Taking the lord:** `cm:kill_character(lookup, true)` if alive, `cm:reassign_character(cqi, faction_cqi)`,
  `cm:stop_character_convalescing(cqi)`. The lord lands in the new faction's lord recruitment pool. This works
  across cultures (a Bloodthirster into a Warriors of Chaos faction).
- **Making the vassal:** `cm:force_make_vassal(master, vassal, true)`. First move the target's own vassals
  (`force_break_vassalage` + `force_make_vassal` to the new master) and free it from any master. This works
  across cultures too.
- **Dead faction, lord only:** `cm:awaken_faction_from_death_with_region(faction, region_key)` brings the
  dead faction and its characters back, then take the lord and `cm:kill_faction` it again. Suppress the
  re-death in your own FactionDeath listener with a flag.
- **The reusable dilemmas.** All three only display text, have generic wording and are gated only by a
  `GEN_TARGET_MODEL` condition (no faction condition), so any faction can be sent them:
  - `wh3_dlc29_chs_archaon_vassalize_chaos_faction` (title "Champion Defeated"). Its choices FIRST/SECOND are
    "Subjugate Champion" / "Dismiss Weakling", and its tooltip text already describes "recruitment pool +
    vassal".
  - `wh3_dlc29_chs_archaon_vassalize_chaos_faction_no_leader`, the same for a dead faction.
  - `wh3_dlc29_chs_archaon_fight_dead_chaos_faction` ("Challenge the Champion"), built at runtime with
    `cm:create_dilemma_builder`. Its targets are `default` (your force) and `target_military_1` (the
    challenger force), and its payloads are `text_display("dummy_archaon_fight_dead_chaos_faction_accept" /
    "..._reject" / "..._reject_warning")`.

  Send the first two with `cm:trigger_dilemma_with_targets(faction_cqi, key, target_faction_cqi, 0,
  character_cqi, 0, 0, 0, on_trigger)`, which returns `false` if it didn't trigger. Register the
  `DilemmaChoiceMadeEvent` listener inside `on_trigger`. `context:choice()` is 0 for FIRST.
- **The challenge flow** (Archaon's "fight dead Chaos faction", reimplemented):
  1. On a target faction's death by someone else, `cm:add_turn_countdown_event(your_faction, 3..10, "MyEvent",
     faction_key)`. The campaign manager saves pending countdowns in the savegame. Listen for "MyEvent" and
     read `context.string`.
  2. Delay a turn if your lord is in a settlement, besieging, wounded or has no force.
  3. Revive the faction, find its lord, build units with `random_army_manager` (`new_force`, `add_unit` with
     weights, `generate_force(name, count, false)` returns a comma list), and
     `cm:create_force_with_existing_general(lookup, faction, units, region, x, y, cb)` at a spot from
     `find_valid_spawn_location_for_character_from_character`.
  4. `force_declare_war`, `disable_movement_for_character`, `set_force_has_retreated_this_turn`.
  5. On accept, lock the "retreat" UI override and `cm:force_attack_of_opportunity(your_mf_cqi,
     enemy_mf_cqi, false, true, true)`.
  6. A `BattleCompleted` listener cleans up with `cm:kill_all_armies_for_faction`. Winning then flows into
     trigger 1 or 2 above.
- **State:** `cm:add_saving_game_callback` / `cm:add_loading_game_callback` with `save_named_value` /
  `load_named_value`. Tables are serialised as Lua source, so string keys and booleans survive.
- **Logs:** `ModLog()` writes to `lua_mod_log.txt` in the game folder, next to the loader's own
  "Executing mod function ..." lines. `out()` goes to `script_log_*.txt` when script logging is on.

## Build steps
1. Write `script/campaign/mod/valkia_khorne_subjugation.lua`:
   - Config: Valkia's key `wh3_dlc20_chs_valkia`, and the targets `wh3_main_kho_exiles_of_khorne` →
     `wh3_main_kho_skarbrand`, `wh3_dlc26_kho_skulltaker` → `wh3_dlc26_kho_skulltaker`,
     `wh3_dlc26_kho_arbaal` → `wh3_dlc26_kho_arbaal_the_undefeated`.
   - Listeners and functions as described above.
   - A first-tick callback gated on `cm:get_campaign_name() == "main_warhammer"` and the faction being human.
2. Pack it as a PFH5 mod pack with the file at `script\campaign\mod\valkia_khorne_subjugation.lua`. No db/
   or text/ entries are needed.
3. Drop the pack into `data\` (quit the game first; it locks packs) and enable it in the launcher.
4. For testing, build a second pack with a first-tick script that sets up the scenario (see Verification).
   Never ship it.

## Verification
- **Offline:** CA's API was stubbed in Lua 5.1 (lupa), and the real script ran through 15 cases: accept,
  dismiss, a non-LL lord beaten, Valkia losing, AI Valkia, the wrong campaign, faction wiped in the
  battle, the challenge accepted / rejected / delayed, an already-subjugated faction dying later,
  both listeners reporting the same battle, both battle-end orders, and a save/load round trip.
- **In game, subjugation in battle:** the test pack stripped Skarbrand's army, teleported him next to Valkia
  on turn 1 (`teleport_to`, `remove_unit_from_character`) and declared war. Attacking and winning gave
  "Champion Defeated". Subjugating put Skarbrand in Valkia's recruitment pool and made Exiles of Khorne her
  vassal (checked on the diplomacy screen). The human player confirmed it.
- **In game, challenge:** the test pack `kill_faction`'d Exiles of Khorne on turn 1, set the countdown to
  1 turn and the challenger to 4 units. On turn 2 "Challenge the Champion" appeared with Skarbrand's army
  next to Valkia. Accepting and winning led to subjugation, and Skarbrand joined her pool. The human player
  confirmed it.
- **Not verified:** Skulltaker and Arbaal specifically (same code path, different keys), multiplayer
  (a human Archaon and a human Valkia in one campaign), the faction left without a leader when its only
  lord moves, and save/load with a dilemma open (the choice listener is not persistent, the same as CA's).

## Gotchas
1. **`um scan` says "unknown native engine" and recommends DLL hooks.** **Cause:** the scanner has no
   Warscape signature. **Fix:** ignore that route; mod with packs (DB tables, loc, Lua).
2. **"Archaon can confederate the god factions" sends you looking for a confederation call that isn't
   there.** **Cause:** the daemon cultures are vassalised through hidden vassal-owner factions that live in
   the start position. **Fix:** read the culture → subjugation-type table in his config before designing.
   For another faction, use direct `force_make_vassal`.
3. **New dilemmas look like they need four DB tables plus loc** (`dilemmas`, `cdir_events_dilemma_option_junctions`,
   `cdir_events_dilemma_choice_details`, `cdir_events_dilemma_payloads`). **Cause:** that's true for new keys.
   **Fix:** first check whether a CA dilemma's text is generic and its options carry only a GEN_TARGET_MODEL
   condition and TEXT_DISPLAY payloads. Archaon's three are, so we reused them with zero tables.
4. **After a challenge battle you win, the subjugation dilemma can silently never appear.** **Cause:** CA's
   cleanup sets a "suppress the next FactionDeath" flag before killing the challenger's remaining armies.
   If your victory already destroyed the faction, that flag swallows the death from your win (or a later
   unrelated one). **Fix:** set the flag only when the cleanup itself kills a still-living faction.
   Separately, dedupe dilemmas per faction, because the defeat listener and the FactionDeath listener can
   both report the same battle.
5. **A subjugated faction that later dies keeps triggering challenges.** **Cause:** its lord is already
   yours, so reviving it finds no lord, the spawn fails, and the countdown retries every turn. **Fix:** keep
   a saved set of subjugated faction keys and skip them when scheduling.
6. **The challenge never comes.** **Cause:** it is deliberately delayed while your lord is in a settlement,
   besieging or wounded. **Fix:** in tests, end the turn with the army in the open.
7. **Test overrides vanish on reload.** **Cause:** values set at runtime on the config table aren't saved.
   **Fix:** don't save and reload between setting up a test scenario and playing it.
8. **A pack copy into `data\` fails or keeps old content.** **Cause:** the game locks installed packs while
   running. **Fix:** quit first and compare checksums after copying.

## Assets
None. All text is CA's existing localisation.

## Cost and time
One session: about an hour of reading CA's scripts, then two build-and-test rounds, each with a human
playing one or two turns.

## Open questions
- Is cross-culture `form_confederation` (Warriors of Chaos absorbing Daemons of Khorne directly) safe? It
  wasn't tried.
- AI Valkia using the mechanic (Archaon's AI subjugates without a dilemma). It's easy to add, but could snowball.
- Generalising: a small config-driven library could give any Warriors of Chaos lord the same mechanic for
  their god (Festus → Nurgle, Azazel → Slaanesh, Vilitch → Tzeentch) with the same reused dilemmas.
