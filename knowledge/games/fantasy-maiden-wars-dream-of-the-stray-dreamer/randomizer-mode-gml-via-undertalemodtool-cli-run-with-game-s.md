---
kind: game
title: Randomizer mode (GML via UndertaleModTool CLI, run with -game so the install stays vanilla)
game: Fantasy Maiden Wars Dream of the Stray Dreamer
games_also: ["Fantasy Maiden Wars DoSD", "幻想少女大戦"]
game_version: "Steam 3575980, build 25976175, fmw_dosd.exe 1.1.0.0 (x64), as of 2026-11-09"
platform: windows
engine: gamemaker
route: managed-patch
tools: ["UndertaleModTool CLI 0.9.2.0 (03c7048)", "Python 3 (own data/cipher tools)", "PowerShell (loader setup)"]
anti_cheat: none (offline single-player, Steamworks only)
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: ["SophiaUrabe"]
date: '2026-11-15'
links: ["https://github.com/UnderminersTeam/UndertaleModTool"]
tags: [gamemaker, gms2, data-win, utmt, randomizer, srpg, touhou]
---
# Randomizer mode (GML via UndertaleModTool CLI, run with -game so the install stays vanilla)

We added a full Randomizer mode to Fantasy Maiden Wars: Dream of the Stray Dreamer (a GameMaker tactics RPG):
- two extra route-picker entries;
- seeded ally/lead shuffle, with enemies and bosses scaled to the chapter;
- stat archetypes or "Chaos" rolls, ability and unique randomization, permadeath and story skip;
- QoL extras: an enemy danger zone, pre-battle damage boxes, and terrain info in the hover window.

GML scripts are imported into a copy of `data.win` with the UndertaleModTool CLI. The game runs that copy through
`fmw_dosd.exe -game`, so the Steam install stays byte-identical to vanilla. The human played many runs and confirmed
most features in game. Several late fixes are built but not yet seen in game, hence `in-progress`.

## Setup
- Steam 3575980, build 25976175, `fmw_dosd.exe` 1.1.0.0, x64.
- `data.win` (33 MB) is FORM/GEN8 with **bytecode 17**: the modern GMS2 VM, not YYC, so the GML decompiles cleanly
  ([the YYC-vs-VM technique note](../../techniques/gamemaker-yyc-vs-vm-check-the-code-chunks-before-trusting-th.md)
  has the check).
- UndertaleModTool CLI 0.9.2.0 (`UndertaleModCli.exe load <data.win> -s <script.csx> -o <out.win>`).
  The GUI build was used for browsing.
- Saves: `%LOCALAPPDATA%\fmw_dosd\savedata`. Config: `<game>\options.ini`. The game sandbox only allows relative
  file names for `file_text_*`, which land in `%LOCALAPPDATA%\fmw_dosd\` (our log goes there).
- No community mods or tools existed when we started (2026-11-07).

## Route and why
- **GML patching of `data.win`** (UTMT). All game logic (route picker, unit joins, enemy creation, battle UI,
  dialogue) is GML, so the randomizer lives in new global scripts plus hooks in existing ones.
- **Data-only edits were rejected.** The game tables live in encrypted/compressed external files, and the
  randomizer must be per run (seeded at New Game), not baked into the files.
- **`-game` loader instead of replacing `data.win`.** The install stays vanilla and Steam "verify" never fights
  the mod.

## How the game works (what we had to learn)
- **External data:**
  - `data\` holds 338 files (1.8 GB) named by md5 hash. Each is a chain of concatenated zlib streams: CSV/INI/JSON
    text (unit, stage and weapon tables, map grids) and raw RGBA pixel buffers.
  - `meta\dat.meta` is a plain index: u32 count, then `name\0 file\0 u32 offset u32 size`.
  - `meta\data*.meta` (20 files) are **encrypted** (magic `3a a5`, power-of-two sizes) with `buffer_encode_ext`
    and a password string. `buffer_encode_ext` is the game's own GML function, not a GameMaker built-in (the
    manual's buffer functions have no such name). The password and loader are in the GML; search the decompile
    for `.meta`.
    - The game's own hex parser (`hex_to_dec_fast`) has a quirk that a re-encoder must reproduce, or a round trip
      differs.
  - Tables are `ds_grid_write` hex strings: a 0x25B header, w, h, then column-major cells (type 0 double /
    type 1 string).
  - The face index `_face.json` uses a simpler byte+shift cipher (shift starts at 128 and decreases).
- **Key tables:** `data_unit_all` (machine rows, e.g. `Youmu01`; enemy rows `<Char>_enNN`), `data_char_all`
  (pilots), `data_weapon_all`, `Data_Updates`/`Data_Change` (upgrades), `Data_IsIN` (roster per stage) and
  `Data_Bonus` (scripted joins: INIT_UNIT/INIT_CHAR/UNIT_IN/UNIT_OUT/ADD_EXP..., run by `bonus_init`).
- **Route picker:** `start_select_player` (two `ObjTitleRoute`) and `UI_title_route_draw` set `global.route`.
  `title_start(0)` runs `bonus_init(0)` (the opening joins) right away, so a randomizer must seed *before* it.
- **Identity vs data:** enemies keep `unit_code`/`char_code` (stage scripts call `find_unit(1,"Rumia_en")`) while
  `unit_data` can point at another row.
  - Swapping the data row and keeping the code makes stage scripts keep working.
  - Battle sprites and dialogue follow the *data* row's character, not the code.
- **Pilot growth:** `get_status(type, stat, 1, cost, code)` returns per-level growth and receives the pilot code.
  It's the single hook point for per-character growth changes.
- **Spell cards:** `spell_start` resets boss HP from that card's own `BulHP[card]` (unscaled). A swapped boss needs
  its cards rescaled, and padded to the original's card count when stage victory chains wait for a spell break.
- **Stage scripts** (`st_ev_*`, `st_start_*`, `st_end_*`) and event checks (`ev_check_general`) hard-code
  characters, stages and weapon slots. Most randomizer crashes came from these assumptions (see Gotchas).
- **Saves:** we store the run seed and options in the save's version string (`#RANDO|<ver>|...`). Old tags still
  parse, and vanilla saves are untouched. Mid-battle saves write `repl@orig` for swapped enemies so loads don't
  re-roll.

## Build steps
1. Back up the vanilla `data.win`. Decompile with the UTMT CLI to get every code entry (3005 here) as text.
2. Write new scripts as `gml_GlobalScript_*.gml`, and copy the vanilla scripts you hook (keep pristine copies to diff).
   The decompile and those copies are the game's code: keep them private, outside any repo.
3. Build: Python generators turn the tables into GML data scripts, then
   `UndertaleModCli.exe load data.win.orig -s import.csx -o out/data.win -f < /dev/null`
   (`-f` overwrites an existing `out/data.win`; without it 0.9.2.0 refuses and exits 1).
   The csx imports every `src/*.gml`. **Check the log for the import result.** The CLI exits 1 only when the script
   throws (`CodeImportGroup.Import()` does on compile errors); a failure the script catches or reports with
   `ScriptError` still exits 0 and saves the file.
4. Run without touching the install: `<game>\fmw_dosd.exe -game <path>\data.win`.
   - The working directory becomes the folder holding that `data.win`, so it needs `data\` and `meta\` (we use
     directory **junctions** to the game's folders), the two Steam DLLs, `options.ini` and any custom sprite folder.
   - Simpler: put the modded `.win` in the game root under another name and pass `-game <name>.win`. Then the
     working directory is already the game root.
   - Steam's restart-through-Steam keeps the `-game` argument.
5. **Sharing:** the built `.win` contains the game's code. Ship a binary patch (e.g. xdelta against the vanilla
   `data.win`), not the file.

## Verification
- Oracle:
  - an in-game mod log (`rando_log.txt`) recording every roll and swap (actor maps, kits, card scaling, "empty map
    win", ...);
  - screenshots of status screens and the map;
  - the human's play sessions, including their quicksaves loaded to reproduce crashes.
- Round trips: the meta cipher and the grid format re-encode byte-identical.
- Verified in game: route menu and settings screen, the shuffle (status, portraits, names rewritten in dialogue),
  enemy/boss swaps, save/continue keeping the seed, stat modes with up/down markers, danger zone, hover EXP and
  terrain, battle-quote faces, the ch3 soft-lock fix, the revive-vs-defeat fix.
- Not yet verified: permadeath of an actual unit, several late fixes (summon scaling, danmaku lockout removal,
  spell-card padding in other stages, the weapon-slot guard), custom battle sprites for a character without art.

## Gotchas
1. **The UTMT CLI hangs forever in scripts.** **Cause:** when stdin is redirected, the 0.9.2.0 CLI reads it to end
   of file before it does anything (`Program.Main`), so a shell whose stdin never closes hangs it (as in the
   [DELTARUNE reskin note](../deltarune/creator-driven-reskin-and-russian-chapter-1.md)). **Fix:** feed it empty
   stdin (`< /dev/null`, or `< NUL` in cmd), and grep the log for the import result: the exit code only catches a
   script that throws (Build step 3).
2. **`obj.rando` was truthy on objects that never set it.** **Cause:** a script asset named `rando` exists, and GML
   resolves an unknown instance variable to the asset index. **Fix:** never name a script like any instance variable.
3. **The randomizer seeded too late, so the opening party was vanilla.** **Cause:** `title_start(0)` runs the
   opening joins immediately. **Fix:** seed before it.
4. **Dialogue `dialog_set` arg4 is the opponent, not the speaker.** Bosses got the wrong portrait. **Fix:** record the
   speaker yourself before each call.
5. **Swapped "goal runner" enemies soft-locked stages** (an enemy reaching a tile = defeat): the replacement had more
   Move. **Fix:** keep `min(own, original)` Move for runners; freeze one specific runner whose spell debuffs still broke it.
6. **A swapped boss with no spell cards soft-locked chapter 3.** **Cause:** the victory chain waits for a spell break.
   **Fix:** pad cards to the original count, plus an "empty map at turn start = win" safety net. The ending script
   also needs guards for the missing original boss.
7. **Crash: "Data structure with index does not exist" when a character with no dialogue files entered battle.**
   **Fix:** check the file lookup and fall back to a stub dialogue map.
8. **Crash: unique moves keyed on the role code vs the graphic's actor code** (Satori's move in another slot).
   **Fix:** key both sides on the actor, and add a guard that plays the move normally if data is missing.
9. **Crash: `icon_add_weapon` "Index [3] out of range".** **Cause:** a stage script reveals a hidden 3rd weapon that
   only the original boss has. **Fix:** bounds-check the weapon arrays.
10. **A "defeat if any ally reaches 0 HP" stage event fired before the revive skill ran.** **Fix:** make the HP check
    ignore units with a revive charge left.
11. **Summon spells hard-code their home stage.** On early stages they summoned late-game minions: scale them by
    chapter curve.
12. **`global.EXP` values are int64.** `is_real()` returns false; use `real()`.
13. **Clock-based seeds:** runs started close together had nearly equal *first* draws (same lead archetype every
    time). **Fix:** discard a couple of draws after seeding, or hash the seed.
14. **New game wipes autosave slots 1-2.** Back up `savedata` before automated test runs.
15. **Input automation:** keys sent during screen transitions get dropped. Boot takes ~45 s, so drive menus by hand or
    with long waits.
16. **Never `rm -rf` a folder that holds junctions into the game install;** it deletes the game's data.

## Assets
- One character with no battle art got user-provided PNG frames, loaded at runtime with `sprite_add` from a mod
  folder.
- His dialogue lines were user-written and compiled into a GML data script by a generator.
- A release can carry those frames and lines only if they're the user's own work, or used with the artist's
  permission.

## Cost and time
About five sessions (2026-11-07 to 2026-11-09), with the human testing between builds.

## Open questions
- Permadeath and several late fixes still need real-combat confirmation.
- Stat redistribution for base stats *and* growths (via the `get_status` hook) is designed but not built.
- A public release needs an xdelta-style patch installer.
