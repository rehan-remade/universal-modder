---
kind: game
title: "Creator-driven character reskin and a Russian Chapter 1 in the DELTARUNE Chapter 1&2 demo"
game: "DELTARUNE"
games_also: []
game_version: "Steam DELTARUNE Chapter 1&2 DEMO (app 1690940), single data.win, GMS2, bytecode 17, VM; Windows 11"
platform: windows
engine: gamemaker
route: data
tools: ["UndertaleModTool CLI 0.9.2.0", "Pixelbolt 0.9.0", "Python 3.12 + Pillow", "Codex CLI 0.164.0 (imagegen)"]
anti_cheat: "none (single-player; the free Steam demo, a separate copy with its own save folder)"
status: in-progress
agents: ["Claude Code (Opus 5.5)", "Claude Code subagents for the translation (model not recorded)"]
humans: []
date: 2026-10-25
links: ["https://github.com/UnderminersTeam/UndertaleModTool", "https://github.com/skulitom/Pixelbolt"]
tags: [gamemaker, data.win, undertalemodtool, sprite_assign, sprite_add, vessel-creator, localization, cyrillic, font-atlas, csx, parallel-translation]
---

# Creator-driven character reskin and a Russian Chapter 1 in the DELTARUNE Chapter 1&2 demo

> A data-route mod for the free Chapter 1&2 demo: the vessel creator gets an extra head/torso/legs option; choosing
> all three swaps Kris for a custom hero and Toriel for a custom robot at runtime (sprites, portraits, name in
> text). Chapter 1 is translated to Russian (6,127 of 6,242 strings) with Cyrillic added to all six fonts and the
> text-bearing sprites redrawn. The runtime sprite swap was confirmed in the real game from a screen recording;
> the creator option, translation, fonts and quick save were verified offline only.

## Setup
- DELTARUNE Chapter 1&2 DEMO from Steam (free), Windows 11. Not the paid full game: the layout differs (below; the
  full release's per-chapter layout is in [the Jevil practice note](jevil-practice-mod.md)).
- UndertaleModTool CLI 0.9.2.0 (official release `UTMT_CLI_v0.9.2.0-Windows.zip`), Python 3.12 + Pillow,
  Pixelbolt 0.9.0 for the pixel art.
- Work on a copy of the install; keep `data.win.orig` and always patch from it.

## Route and why
Data route: `UndertaleModCli load data.win.orig -s install.csx -o data.win` with `CodeImportGroup`
(`QueueReplace` a new global script, `QueueAppend`/`QueuePrepend`/`QueueFindReplace` hooks). The demo is VM (UTMT
`info`: `Is YYC - False`, 9,715 code entries; see
[the YYC-vs-VM technique note](../../techniques/gamemaker-yyc-vs-vm-check-the-code-chunks-before-trusting-th.md)),
so decompile/recompile is safe. New art is loaded at runtime from loose PNGs instead of packed into texture pages,
which keeps the patch small and the art editable without re-patching.

## How the game works (what we had to learn)
- **Demo layout:** one `data.win` holds both chapters; Chapter 1 copies of assets carry a `_ch1` suffix (most
  sprites exist twice). The demo ships `steam_api.dll`; a copy outside the Steam folder runs with
  `steam_appid.txt` = `1690940`. Saves go to `%LOCALAPPDATA%\<GeneralInfo.Name>`: rename it in the copy.
- **Vessel creator:** `DEVICE_CONTACT_ch1` runs the intro; events 16-27 create `DEVICE_GONERMAKER_ch1` three
  times. The chosen parts are stored in `global.flag[900]`, `[901]`, `[902]` (saved with the file); the part sprites
  are `IMAGE_GONERHEAD_ch1` / `BODY` / `LEGS` (21x22 / 21x15 / 21x9, origin 1,1, drawn at 2x), limits in
  `PARTMAX` (7/5/4). The typed vessel name lands in `global.name` and is never saved; "your own name" is
  `global.truename` (saved). The game's debug skip of the intro is `flag[6] = 0`, `snd_free_all_ch1()`,
  `room_goto(room_krisroom_ch1)`.
- **Chapter 2 inherits every Chapter 1 flag** from the completion save (`scr_load_chapter1` reads them all).
- **Player collision:** `obj_mainchara` has no `mask_index`, so walls use the walk sprite's bounding box.
- **Text:** Chapter 1 reads `lang/lang_<lang>_ch1.json` from disk (`scr_84_lang_load_ch1`) and looks strings up in
  `scr_84_get_lang_string_ch1`. Chapter 2's English is inline in code: `stringsetloc(text, key)` returns
  `stringset(text)` in English. Those two functions are the only funnels a name substitution needs.
- **Text writer (Ch1):** fixed advance per character, word wrap at 33 characters (26 when a face code `\E`/`\F` is
  present), 3 lines per page; codes: `^n` pause, `&` newline, `/` page, `%` end, `~n` substitution,
  `\E`/`\T`/`\F`/`\M`/`\C`/`\c` styling.
- **Fonts:** `fnt_main` (8bitoperator 12px, 6x13 cells), `fnt_mainbig` (exactly 2x of it), `fnt_dotumche` and
  `fnt_comicsans` (in this build both bold 2px pixel fonts on the same grid, baseline 1 and 2 rows lower),
  `fnt_small` (4x5 caps-only) and `fnt_tinynoelle` (4x8). All 1-bit atlases with only ASCII 32-127.
- **Text baked into sprites** = the sprites that have a `_ja_` variant (the game swaps them for Japanese):
  battle buttons, HP-box name labels, dark-menu captions and descriptions, quit message, area title card, the
  Thrash Machine logo and stats, and some backgrounds with painted signs.
- **Saving:** save points call `scr_save_ch1()` / `scr_save()` (slot `global.filechoice` + backup slot 9 +
  `dr.ini`); the stored room is `global.currentroom`, set to `room` by `obj_mainchara`'s Create. Loading is a
  `room_goto` to it.

## Build steps
1. Copy the demo; keep `data.win.orig`; add `steam_appid.txt`.
2. In the install script, `QueueReplace` a global script with the mod's functions and hook:
   - creator Create: raise `PARTMAX` by one per part (literal numbers, see Gotcha 1); creator Draw: route the
     three `draw_sprite_ext(img, …)` calls through helpers that return a runtime-loaded sprite (and subimage 0)
     when the index equals `sprite_get_number(img)`;
   - `obj_time_ch1` / `obj_time` Begin Step (prepend): the swap check and hotkeys; Draw GUI (append): notices;
   - `scr_84_get_lang_string_ch1` and `stringset`: wrap the return value in a text filter (name substitution);
   - new Game End events on both `obj_time` objects (`EventHandlerFor(EventType.Other,
     EventSubtypeOther.GameEnd, Data)`) for a save on exit.
3. **Runtime swap:** for each target sprite: `sprite_duplicate` it once as a backup; `sprite_add(png,
   sprite_get_number(orig), false, false, sprite_get_xoffset(orig), sprite_get_yoffset(orig))`;
   `sprite_collision_mask(added, false, 2, <orig bbox>, 0, 0)`; `sprite_assign(target, added)`; delete the added
   sprite. Re-assign the backup when the condition turns false. Strips must have exactly the original's frame
   count and size.
4. **Cyrillic:** per font, a new embedded texture = the old atlas with new glyphs packed below it, a new texture
   page item covering it, `font.Texture` pointed at it, extra `UndertaleFont.Glyph` entries, glyphs sorted, and
   `RangeEnd` updated. Old glyph coordinates stay valid because the old atlas sits at (0,0).
5. **Translation:** write the merged Russian into the copy's `lang/lang_en_ch1.json` (no language switch needed).
6. **Text sprites:** redraw them from the game's own (now Cyrillic) font atlases in colours sampled from the
   original and swap them with the same runtime mechanism, unconditionally.

## Verification
- In the real game (human's screen recording, 1 min 39 s): the reskinned walk sprites in the hero's room, the
  supply closet and the first Dark World rooms (light and dark variants), confirming `sprite_add` +
  `sprite_assign` on resource sprites works in this runtime. The current GameMaker manual says `sprite_assign`
  can't copy to a game resource (the target must come from `sprite_add`/`sprite_duplicate`), so re-check it on
  any other runner, such as the full release's.
- Offline, every build: decompiled the patched entries back out of the new `data.win`; re-exported swapped
  sprites; checked every strip is frames x width by height of its target; JSON validity; per-chunk translation
  checker (all keys, control-code counts, glyph coverage, simulated 3-line wrap, label lengths); merge rejected 0.
- NOT verified in game: the creator option, the robot replacement, the Russian text and fonts on screen, Ctrl+S /
  save-on-exit, the TAB intro skip, the recoloured Chapter 1 poses.

## Gotchas
1. **Macro compiled as a variable.** A `#macro` defined in the mod's global script was used in a `QueueAppend` to
   an object event; the decompile showed the macro name as an instance variable (it would crash at runtime).
   **Cause:** macros are not visible when CodeImportGroup compiles another entry. **Fix:** literals in hooks.
2. **CLI hangs.** `UndertaleModCli load file -s script.csx` sat waiting on stdin. **Cause:** when stdin is
   redirected, the 0.9.2.0 CLI reads all of it, up to end of file, before it does anything (`Program.Main`), so a
   shell whose stdin pipe never closes hangs it. It doesn't go interactive without `-i`, but without `-o` it runs
   the scripts and saves nothing. **Fix:** always pass `-o` (and `--overwrite`), and feed it empty stdin (`< NUL`
   in cmd, `< /dev/null` in a POSIX shell).
3. **`vk_tab` not found in decompiled code.** **Cause:** constants decompile as numbers (9). **Fix:** search for
   your own function names when verifying hooks.
4. **"Missing" sprites in cutscenes.** Swapping walk sprites leaves dozens of special poses (falls, kneeling,
   battle, frames shared with other characters). **Fix:** inventory every `spr_*kris*_ch1` referenced by `_ch1`
   code (54 sprites, 254 frames here) and cover each; for shared frames restrict recolouring to a box.
5. **Some shades differ per sprite** (e.g. dark-world lying pose uses (0,0,64)/(224,0,128) instead of the walk
   palette). **Fix:** collect colours per sprite before mapping.
6. **Text overflowing boxes.** Translations are longer than English. **Fix:** simulate the writer's wrap (33/26,
   3 lines) in the checker and shorten before testing.
7. **Glyph missing.** Translators used an em dash; the fonts have none. **Fix:** check every character against the
   glyph table.
8. **Input automation collides with the human.** Long `um win drive` key loops to get through the intro landed
   while the human was using the game. **Fix:** ask first, check idle, keep it short; prefer saves or skips.
9. **Background agents hit a usage limit mid-chunk.** **Fix:** resume them with a message instead of restarting;
   part files on disk kept their progress.

## Assets
- Hero walk set (19x38, 16 frames) and creator parts: Pixelbolt recipes, hand-authored grids.
- Robot (25x53 overworld, 35x33 white portraits with 10 expressions): Pixelbolt recipes generated by a Python
  script (rect/grid ops, hover bob, flame flicker).
- A 1024px reference portrait from Codex CLI `$imagegen` (ChatGPT plan), downscaled; noisy at 50px.
- Chapter 1 special poses: palette remap of the original poses onto the hero's palette (keeps the original
  silhouette).
- 66 Cyrillic glyphs drawn on the `fnt_main` grid, reused for mainbig (2x), dotumche (+1 row) and comicsans
  (+2 rows); separate hand-drawn sets for the 4x5 and 4x8 fonts.
- **What ships:** nothing is published yet. The art drawn for the mod (hero, robot, creator parts, the Cyrillic
  glyphs) is the mod's own. The recoloured Chapter 1 poses are Kris's own sprites, and the redrawn text sprites and
  extended font atlases are built from the game's sprites and fonts, so a release builds those at install time
  from the player's own `data.win` and never ships them, like the modified `data.win` itself.

## Cost and time
One long session (about two days of wall-clock with breaks). Translation: 10 parallel subagents, about
5,900 strings, roughly 120-160k tokens each.

## Open questions
- Chapter 2: about 13,000 inline strings (the `stringset` hook is ready for a text map) and Chapter 2-only poses.
- Signs painted inside backgrounds (classroom board, library, shop fronts) need hand-redrawn art.
- Whether the Game End event fires on every way of closing the window in this runtime.
