---
kind: game
title: "Napoleon's France as a playable faction in Shogun 2, replacing Otomo"
game: "Total War: SHOGUN 2"
games_also: ["Napoleon: Total War"]
game_version: "Shogun 2 build 6262 (v1.1.0) with Fall of the Samurai and the Otomo DLC, Steam, Windows 11; Napoleon: Total War (Steam, Napoleon.exe of 2026-10-15)"
platform: windows
engine: native
route: data
tools: ["Python 3.14 (own PFH3 pack, DB, loc and ESF codecs on RPFM's schemas)", "capstone", "Frida 17", "um win", "um backup", "Runcher (the owner's launcher, by Frodo45127)"]
anti_cheat: "none (single player); Frida hooks only in offline single-player sessions"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-26
links: ["https://github.com/Frodo45127/rpfm", "https://github.com/Frodo45127/runcher"]
tags: [total-war, warscape, faction-port, db-tables, loc, startpos, esf, voices, sound, naval, runcher]
---

# Napoleon's France as a playable faction in Shogun 2, replacing Otomo

> Napoleon: Total War's France replaces the Otomo clan in Shogun 2's Sengoku campaign. It has 57 units
> (infantry, cavalry, generals, artillery, 17 ships) with Napoleon's stats, cards, models, uniforms,
> equipment and horses, and Napoléon himself leads it. It also has French unit voices, French campaign
> text and the N on every banner.
>
> It is one generated data pack (DB tables, loc, art, models and a startpos edit), built from the
> player's own Napoleon and Shogun 2 installs. It is playable: verified in new campaigns and in land
> and naval custom battles, with screenshots, unit statistics and Frida probes.
>
> Some limits are hard-coded in the engine and stay: ambient soldier chatter is Japanese, and some
> ships' bow guns stall. They are listed below.

## Setup
- **Shogun 2:** build 6262 (v1.1.0), Steam app 34330, 32-bit `empire.retail.dll`. Fall of the
  Samurai and the Otomo DLC (Steam 223180) are installed. France takes Otomo's slot, so the DLC must
  stay installed.
  - This is the classic release. *Total War: SHOGUN 2 - Complete Edition* (Steam app 3846830, out
    2026-10-13) is a separate game to RPFM (`shogun2_complete_edition.exe`, schema `sho2_ce`, PFH3
    packs), so the addresses, row orders and schemas here are untested on it.
- **Napoleon: Total War:** Steam, read only. Its packs are read in load order: boot, data, buildings,
  battleterrain, media, rigidmodels, variantmodels(2), sound, local_en(_patch).
- **Tools:**
  - our own Python codecs for packs (Napoleon's are PFH0, Shogun 2's own PFH2, the mod pack PFH3, per
    RPFM's `supported_games.rs`), DB tables (the `sho2` and `nap` schema files from Frodo45127's
    [RPFM](https://github.com/Frodo45127/rpfm)), loc and ESF, all round-trip tested;
  - capstone for reading `empire.retail.dll`;
  - Frida 17 for live hooks;
  - `um win` for launching, screenshots and input; `um backup` for saves and config.
- **Mod loading:** one PFH3 *mod*-type pack in `data/`. It is enabled by `mod "<pack>";` in
  `%APPDATA%\The Creative Assembly\Shogun2\scripts\user.script.txt` (UTF-16 LE with BOM) and by
  Runcher's own list (see Gotchas).

## Route and why
- **Data route:** a generator writes every DB table, loc file, model, texture and the startpos edit
  into one pack. Nothing patches the executable.
- **Replace a clan instead of adding one:**
  - The Sengoku clan list and the startpos are fixed. Replacing Otomo keeps its starting provinces,
    armies, characters, AI records and DLC slot.
  - Adding a 13th clan would mean rebuilding the startpos and the campaign AI layer.
- **Bring your own game files:** everything is converted at build time from the player's own installs;
  no game files are distributed.
- **Not taken:**
  - Retargeting Napoleon's animations wholesale: the Empire skeleton has 41 bones and an older `.anim`
    version. Only the rocket and mortar crew clips were retargeted. Everything else uses Shogun 2/FotS
    animation sets.
  - Executable patches. Three limits below can only be lifted that way.

## How the game works (what we had to learn)
- **DB tables from every pack load and merge by key.** Vanilla loads first, then the mod; the mod wins
  per key. Leaving a row out of a shipped table does not delete the vanilla row.
- **Runtime row order is open-addressing slot order.**
  - The order is not file order. Shipping a table (even unchanged rows plus new ones) renumbers its
    rows at runtime.
  - `sounds_packed/sound_bank_database` stores unit, explosion, building-level, season, sea-surface and
    subculture conditions as those runtime row numbers. Renumber it at build time.
  - Detail: [Fixing silent and wrong unit sounds after adding units to Shogun 2](shogun-2-sound-bank-row-numbers.md).
- **A new culture blanks culture-keyed text.**
  - Building names (`building_culture_variants_name_<building><culture>`), message event titles
    (`message_event_strings_title_<event><campaign><culture>`) and event-movie titles
    (`movie_event_strings_title_<event><culture>`) are keyed by culture.
  - A cloned culture needs copies of all of them: 1,131 here. Otherwise buildings, events, the Arts
    tree's building lists and mission objectives show blank names.
- **Unit voices (Sengoku battles):**
  - A unit speaks through `units.voice`, a category. `unit_voice_events_junctions` maps (category,
    voice event) to a record name in `sounds_packed/sound_events`. `audio_*` fields in the unit stats
    give the selection and combat lines.
  - **An event a category has no junction for falls back to the record named like the event**
    (`0x102dd2b0`): a generic Japanese take. Vanilla ships play Japanese "move" lines this way. Give a new
    category a line for every voice event whose same-named record speaks (some are deliberately
    `no_sound`).
  - **Playback swaps the first folder of the file path for the battle's voice language.** The voice
    request is `0x103052d0`; the folder is replaced in `0x10f6dfd0`. It is "Uk" in Sengoku battles:
    `sound.pack` keeps the Japanese takes under `uk/`. FotS's French takes live under `english/` in
    `local_en.pack`, so they failed to start (error 7) until copies were added under `uk/` in the mod pack.
    Key-starts-with-"Boshin" units try "English" first.
- **Ambient chatter goes by nationality, and nationality is hard-coded.**
  - Soldiers' and crews' random chatter (`land_flavour_*`, `naval_flavour_*`, picked in `0x10301ef0` →
    `0x10cc5d70`) uses a nationality only six FotS unit keys get. The predicates start at `0x10c28a60`:
    Royal/French/US marines, HMS Warrior, L'Ocean, USS Roanoke.
  - `VO_actor_numbers` and `audio_language` play no part. Every other unit chatters in Japanese.
- **The sound bank holds no voice lines.** Its candidates' events are `sound_events` record numbers.
  The second class with unit lists (`0x11672c3c`) is musicians (European snare signals for FotS's
  Infanterie de marine), not voices.
- **Startpos ships carry their crew by role.**
  - In `campaigns/jap_shogun/startpos.esf` a naval unit has `SHIP_DAMAGE_INFO`: nine damage floats,
    then marines, seamen and gunners (current), then the same three (maximum). These match
    `unit_stats_naval` on every vanilla starting ship.
  - Swapping the unit key and men without these leaves the old ship's crew.
- **Ship weapons:** six engine rules about hull mount names, the 20 m front-battery reach, gun
  placement, reload task points and detonators. See
  [Making ported Napoleon ship weapons work in Shogun 2](shogun-2-ship-mortars-rockets-mount-names.md).
- **Abilities cannot fire ship guns.** FotS's torpedo button (`BCQ_FIRE_TORPEDOS`, handler
  `0x102a7910`) launches a projectile row bound by key (`boshin_naval_torpedo`), and no gun is
  involved. Napoleon's mortars and rockets fire as ordinary guns.
- **Campaign map agent markers** draw from the atlas
  `rigidmodels/flags/textures/agent_faction_ids0.dds` (index `agent_faction_ids.tai`), not from
  `ui/flags/<faction>/`.

## Build steps
1. Read Napoleon's and Shogun 2's packs with the RPFM schemas.
2. Clone Otomo's faction, culture and subculture data under new keys.
3. Port each unit: units row from a Shogun 2 template of the same class, stats, cards and names from
   Napoleon.
4. Convert models: VMPF parts retargeted joint by joint onto `man_shogun`, guns to
   `.rigid_model_v2`, ships to Shogun 2 hulls.
5. Write the culture text copies, the voice categories and junctions, the `uk/` voice copies and the
   sound bank renumbering.
6. Edit the startpos: faction colours, characters, armies, and ship crews from `unit_stats_naval`.
7. Write one PFH3 mod pack and validate it. The validator checks every rule in this note: references,
   culture text, voices, the sound bank, startpos crews and ship batteries.
8. Install it under a fixed name (`data/napoleonic_france.pack`). Enable it in `user.script.txt` and
   tick it in Runcher.

## Verification
- **In game, by screenshots read back:**
  - France in the clan list with Napoleon's figure.
  - A new campaign starting in Bungo.
  - Building, event, Arts and mission names after the culture text fix.
  - Banners, agent icons.
- **Land custom battles:** kills per unit in the results screen, volleys and bayonet melee.
- **Naval custom battles, one ship plus one target each:** launch logs, deck impacts, and unit
  statistics.
- **Voices:** Frida on `mss32.dll` (`AIL_set_named_sample_file`, `AIL_load_sample_buffer`)
  logged every file Miles loaded. Files were matched to pack entries by size and the first 64 bytes.
  French units loaded only French takes for selection, orders, alerts and combat lines; before the
  `uk/` copies, nothing loaded.
- **Starting frigate crew:** read back from the built startpos (16/16/64). A validator check catches
  the 30/5/0 case.
- **Not verified:**
  - The starting-frigate fix in a new campaign.
  - Launch sounds of the ported ship weapons.
  - Rocket hit rates over many shots.
  - How the trimmed ship collision shapes affect ramming and AI spacing.

## Gotchas
1. **Silent or wrong unit sounds after adding units.** **Cause:** the sound bank stores runtime row
   numbers, and shipping a table renumbers rows. **Fix:** renumber the bank at build time
   ([Fixing silent and wrong unit sounds after adding units to Shogun 2](shogun-2-sound-bank-row-numbers.md)).
2. **Blank building, event, mission and Arts names for the new faction.** **Cause:** culture-keyed loc;
   the cloned culture had none. **Fix:** copy every Japanese-culture key to the new culture.
3. **"French voices" set up, yet the units spoke Japanese or nothing.**
   - **Causes:**
     - The voice language folder swaps `english/` for `uk/`, and the files were missing there.
     - Events without junctions fall back to generic Japanese records.
     - `VO_actor_numbers` is ignored in Sengoku battles.
   - **Fix:** copy the takes under `uk/`, cover every speaking fallback event, and check in game with a
     Miles file hook. A config probe proved nothing; the first claim of "French voices" was false.
4. **Ambient chatter stays Japanese.** **Cause:** nationality is hard-coded for six FotS keys.
   **Fix:** none from data.
5. **The starting ship has 0/N guns, but recruited and custom-battle copies are fine.** **Cause:** the
   startpos `SHIP_DAMAGE_INFO` kept the replaced kobaya's crew (30/5/0, no gunners). **Fix:** write the
   new ship's marines, seamen and gunners into the six crew fields. It only applies to new campaigns.
6. **Ship guns disabled from the start in every battle.** **Cause:** Shogun 2 needs at least two
   gunners per gun. **Fix:** `num_gunners ≥ 2 × guns`.
7. **Cannonballs falling into the sea after about 20 m.** **Cause:** `high_air_resistance` copied from
   Napoleon; Shogun 2 sets it only on fragments. **Fix:** clear it.
8. **Mortar shells acting as solid shot, rockets bursting in the air.** **Cause:** Napoleon's `fuse`
   explosions never burst after striking something. **Fix:** `percussive`, as FotS's naval shells use.
9. **Bomb ketch mortars and rocket launcher never firing.** **Cause:** a hull mount whose name contains
   "mortar" or "rocket" gets a dead gun. **Fix:** rename the mounts
   ([Making ported Napoleon ship weapons work in Shogun 2](shogun-2-ship-mortars-rockets-mount-names.md)).
10. **Coats lose their tint by triangle or by distance.** **Cause:** six Napoleon textures had only one
    mip level. **Fix:** write full mip chains.
11. **Agent icons kept the old clan's mon.** **Cause:** they come from the agent atlas, not `ui/flags`.
    **Fix:** repaint the clan's cell (Otomo's is at 640,768, 128 px).
12. **Props through the hand.** **Cause:** Napoleon models fingers relaxed, so Shogun 2's grips bent
    them a second time. **Fix:** straighten each finger to Shogun 2's rest pose before retargeting.
13. **The mod "stopped loading" through Runcher: the old clan back, no sound.**
    - **Causes:**
      - Each build had a new file name, and Runcher keeps a tick per file name and adds new names
        unticked.
      - Another agent had left `user.script.txt` naming a deleted pack.
    - **Fix:** install under one fixed file name. Check Runcher's
      `%APPDATA%\FrodoWazEre\runcher\config\game_config\game_config_shogun_2.json` and
      `user.script.txt`; don't edit Runcher's file while it runs.
14. **Testing cost.** Multi-hour test loops with several ships at once proved little. Test one unit
    plus one target, cap the rounds, and work out the cause offline before each in-game round.

## Assets
None generated. Everything is converted from the player's own Napoleon and Shogun 2 installs at build
time: models, textures, cards, voice takes and loc. The mod ships no game files.

## Cost and time
About five days of agent sessions (2026-10-22 to 10-26): 32 numbered builds (r0 to r31) plus test
variants.

## Open questions
- Whether an executable patch is worth it for the three engine limits: ambient chatter nationality,
  ability-fired ship weapons, and the Indiaman's bow-gun reload.
- Ambient chatter for non-FotS units could perhaps reuse one of the six hard-coded keys, but only by
  replacing that FotS unit.
