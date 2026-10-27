---
kind: game
title: "Fixing silent and wrong unit sounds after adding units to Shogun 2"
game: "Total War: SHOGUN 2"
games_also: ["Napoleon: Total War"]
game_version: "Shogun 2 build 6262 (v1.1.0), Steam, Windows 11"
platform: windows
engine: native
route: data
tools: ["capstone", "Frida 17", "Python (own pack/DB tools)"]
anti_cheat: "none in single player; Frida only on offline single-player sessions"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-24
links: ["https://github.com/Frodo45127/rpfm"]
tags: [sound, db-tables, warscape, total-war, data-order]
---

# Fixing silent and wrong unit sounds after adding units to Shogun 2

> A Napoleon France port for Shogun 2 adds 57 units by shipping a full copy of the units table. One
> 18-pdr battery fired silently. The cause: Shogun 2's sound bank refers to units (and explosions) by
> runtime row number, and shipping a units table renumbers every row. Renumbering the sound bank at
> build time fixed it; in game the battery now picks the same cannon report as an audible battery.

## Setup
- Shogun 2 build 6262 (Steam), the 32-bit `empire.retail.dll`: the classic release (app 34330), not the
  2026 Complete Edition (see the [faction port](shogun-2-napoleon-france-faction-port.md)).
- The mod is a PFH3 "mod" pack enabled through `user.script.txt`. It's generated on the player's machine
  from their own Shogun 2 and Napoleon installs and never distributed, the sound bank included.
- Analysis tools:
  - capstone for disassembly;
  - Frida 17 to spawn the game suspended and hook the DLL as it loads.
- Tests ran single player and offline only.

## Route and why
- Data only: the build rewrites one shipped data file.
- **Considered and rejected:**
  - Keeping the vanilla row order. Impossible, because the order is a hash-map slot order.
  - Patching the engine to look units up by key.

## How the game works (what we had to learn)
- **Sound conditions are row numbers.** `sounds_packed/sound_bank_database` (sound.pack) stores
  sound-event conditions as u32 count + u32 values. Units, projectile explosions, building levels,
  seasons, sea surfaces, subcultures and factions are stored as **row numbers** in the runtime table.
  - Seven condition readers each read a u32 and index the table getter's array.
  - No other engine code reads table rows from a file.
- **Every copy of a table loads.** Every pack's copy of `db/<table>/*` is loaded, in pack order, even
  when the mod's copy has the same path as vanilla's.
  - Rows merge by key and the later row wins.
  - A row left out of a mod's copy still exists.
- **How the runtime order is built:**
  - Each fragment grows the table's open-addressing key map to (keys so far + fragment rows) slots.
  - It re-inserts the existing keys in slot order, then inserts the fragment's rows in file order.
  - Probing is linear with wrap. The hash is a simple XOR-shift over the key's UTF-16 units.
  - Rows are numbered in slot order.
  - The model reproduced 163 of 165 single-key vanilla tables, and the modded units (489) and
    explosions (37) tables, exactly.
- **So re-shipping reorders.** Shipping a table copy, even with unchanged rows, doubles the map and
  reorders every row. Every vanilla sound condition on that table then points at other rows.

## Build steps
1. **Capture the offsets.** Spawn the unmodded game under Frida with entry hooks on the seven
   condition readers. Each hook reads the stream's cursor and end (the file is buffered whole).
   - Record the file offset of every row number.
   - Keep the vanilla file's SHA-256 with the offsets.
2. **At build time, compute two orders for each referenced table the mod ships:**
   - the vanilla order (vanilla fragments only);
   - the modded order (vanilla fragments + the mod's).
3. **Rewrite and pack.** Rewrite each stored number from `vanilla[old]` to its modded row number and
   put the file in the mod pack (rebuilt from the player's own `sound.pack` on every build). The mod's
   own rows end up in no condition list and take default events.
4. **Validate.** The shipped file must equal a fresh remap of the shipped tables.

## Verification
- **Live order:** read in the running game by scanning for the generic DB table objects. Checked
  against the model both unmodded and modded.
- **Selector probe:** an entry hook on the projectile-sound selector logged each candidate's
  conditions and the event returned.
  - Before the fix, the battery sat in a no_sound candidate's unit list.
  - After it, the battery is in no list and picks the same event as an audible 12-pdr battery.
- **Not verified:**
  - The audio itself (the owner tests by ear).
  - Picks for infantry and cavalry. Replays with swapped units never brought them into range.

## Gotchas
1. **An added unit fires in silence, or vanilla units sound wrong, with a units-table mod on.**
   - **Cause:** the sound bank stores row numbers, and the mod reordered the table.
   - **Fix:** renumber the sound bank for the mod's exact table set. Any other mod that adds units
     scrambles it again.
2. **"My copy of the table replaces vanilla's."**
   - **Cause:** it does not. Both load and merge by key.
   - **Fix:** never count on removing rows by leaving them out.
3. **A Frida hook placed mid-function crashed the game.**
   - **Cause:** a branch targeted the patched bytes.
   - **Fix:** hook function entries only, and watch for the process exiting while waiting on a log.
4. **Changing `unique_index` did nothing.**
   - **Cause:** that is not the id the sound bank uses.

## Assets
None.

## Later: making added units sound like a vanilla unit
- **Add twins to the lists.** The bank's unit lists are a u32 count plus indices in a plain stream (no
  offsets), so an added unit can be appended to every list holding a chosen vanilla "twin". It then
  gets that twin's launch layers and musician signals (drums), not voice lines.
  - In game the unit reads rose by exactly the number added, and every read matched the built file.
- **Voices are not in the bank, and not chosen by actor.**
  - A unit's lines come through `unit_voice_events_junctions`. An event with no row falls back to
    the generic (Japanese) record named after the event.
  - The take's first folder is swapped for the battle's voice language: `Uk` in Sengoku battles.
    FotS's French takes sit under `english/`, so added units need them under `uk/` too.
  - Ambient chatter goes by a nationality hard-coded for six FotS unit keys. `VO_actor_numbers`
    plays no part.
  - Details, with addresses, are in the mod's `docs/shogun2_battle_voices.md` (not published).
- **Agent icons.** The campaign map's agent icons come from
  `rigidmodels/flags/textures/agent_faction_ids0.dds` (`.tai` index), not from `ui/flags`.
- **Swap replays.** Swapping a unit key in a replay's ESF string table makes a cheap test battle. Only
  swap like for like: infantry into an artillery slot crashes the game on load.

## Open questions
- Which events the other condition-driven sounds (voices, footsteps, melee) pick for added units.
- Whether giving added units a vanilla "sound twin's" list memberships is worth the file insertions.
