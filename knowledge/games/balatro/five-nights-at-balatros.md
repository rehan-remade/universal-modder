---
kind: game
title: "Five Nights at Balatro's: a FNaF night shift as a Balatro deck"
game: "Balatro"
games_also: ["Five Nights at Freddy's"]
game_version: "Balatro 1.0.1o (Steam 2379780) + lovely 0.10.0 + Steamodded 26.829.0; FNaF 1 (Steam 319510, Clickteam Fusion 2.5 build 284)"
platform: windows
engine: love2d
route: loader-api
tools: ["lovely 0.10.0", "Steamodded 26.829.0", "CTFAK 2.0 (master f38ba79, built locally)", ".NET 8 SDK (portable)", "Python + Pillow", "luaparser (syntax check)"]
anti_cheat: "none (Balatro single-player; FNaF is only read from disk, never launched or patched)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-11
links: ["https://github.com/Steamodded/smods", "https://github.com/ethangreen-dev/lovely-injector", "https://github.com/CTFAK/CTFAK2.0"]
tags: [mashup, total-conversion, steamodded, lovely, love2d, clickteam, ctfak, fnaf, deck, blinds, shop, deck-skin, main-menu, audio]
---

# Five Nights at Balatro's: a FNaF night shift as a Balatro deck

> A Steamodded mod that turns a Balatro run into a FNaF night shift: pick the "Night Guard" deck, every round is a
> night from 12 AM to 6 AM, animatronic cards hide in the deck and move a room closer when drawn, and poker hands are
> office actions (lights, cameras, doors, power) instead of scoring. The office, cameras, jumpscares, Phone Guy calls
> and music are converted at install time from the player's own FNaF; nothing from FNaF ships. It runs in the real
> game: played by the human through five nights, the shop, the custom title screen and every crash fix below.

## Setup
- Windows 11, Balatro 1.0.1o (Steam). lovely v0.10.0 (the Windows binary is now **`winmm.dll`**, not `version.dll`)
  in the game folder; Steamodded 26.829.0 in `%APPDATA%\Balatro\Mods` (26.829 added custom Small/Big Blinds and the
  RunSelectPage run-setup screen, both used here).
- Five Nights at Freddy's 1 (Steam): one 231 MB `FiveNightsatFreddys.exe`, Clickteam Fusion 2.5, build 284, 17 frames.
- Asset extraction: CTFAK 2.0 (archived; built from master) with a **portable** .NET 8 SDK
  (`dotnet-install.ps1 -InstallDir`), no system install. Python 3 + Pillow for the converters.
- Balatro's Lua source is a zip appended to `Balatro.exe` (unzip it to read `game.lua`, `functions/*.lua`).

## Route and why
Balatro hosts (Steamodded API + plain Lua hooks), FNaF is the guest, as converted content. FNaF can't host: it's a
native Clickteam runtime with no loader. Rather than a content pack (Jokers/Blinds), the human wanted "a whole new
experience leaning FNaF", so the mod keeps Balatro's card handling and run flow (blind select → round → cash out →
shop) and replaces what a round *means*: scoring is swapped for office actions while a night is on.

## How the game works (what we had to learn)
**The design, as built.**
- **Deck:** a Night Guard deck (`SMODS.Back`) adds animatronic cards (`SMODS.Enhancement`, no rank, no suit,
  never score, `in_pool` false).
  - Copies double every night from each one's first night.
  - When one is drawn (mod-level `calculate`, `context.hand_drawn`), it may move a room closer.
  - Drawn at a door: door shut → it retreats; door open → jumpscare.
- **Hands are office actions:** High Card waits; Pair = door light; Two Pair = cameras; Three of a Kind = one door;
  Full House/Four of a Kind = both doors; Straight = +power; Flush = the suit's animatronic goes back
  (♠ Bonnie, ♥ Chica, ♦ Foxy, ♣ Freddy); Straight Flush and up = everyone back.
  - Black cards work the left side, red the right.
  - Each hand is +15 min and each discard +5 min; doors, lights and cameras drain power.
- **The four animatronics:** Foxy builds up in Pirate Cove and then runs (cameras slow him). Freddy is invisible to
  the door light. At 0% power the doors open and Freddy comes after a music box.

**Balatro / Steamodded facts that made it possible:**
- **Scoring has one choke point:** wrap `G.FUNCS.evaluate_play` and, while a night is on, run the action from
  `G.FUNCS.get_poker_hand_info(G.play.cards)` instead. The rest of the hand flow (play → discard pile → redraw) is
  untouched.
- **Round end is a score check:** `Game:update_hand_played` goes to NEW_ROUND when `G.GAME.chips >= blind.chips` or
  `hands_left < 1`.
  - Win at 6 AM: set chips = blind.chips.
  - Lose: zero chips and hands. Outside HAND_PLAYED, also set `G.STATE = NEW_ROUND`; Balatro's own game-over screen
    follows.
- **Drawing:** `Game:draw` draws `G.SPLASH_BACK` first and `G.SPLASH_FRONT` above cards and UI, all under the CRT
  shader.
  - Swap them per frame for objects with `translate_container()`/`draw()`: the office goes behind the cards, the
    HUD/cameras/jumpscares in front.
  - The canvas' logical size is `G.CANVAS:getDimensions() / G.CANV_SCALE`. Hide the run HUD by sliding
    `G.HUD.alignment.offset.x` (HUD_blind is bonded to it).
- **Blinds are slot-based in Steamodded 26.829:** `Blind:get_type()` returns `G.GAME.blind_on_deck`, so custom blinds
  can sit in Small/Big/Boss slots. All three slots are filled by `SMODS.reset_blind_choices(choices)` (run start + each
  ante); wrap it to place Night 1..5 (ante a → nights 3a-2..3a).
- **The shop is pools:** wrap the global `get_current_pool`.
  - Joker pool → unowned upgrades of the *rolled rarity*. Steamodded rolls the rarity first, and a pool of just
    `"empty_rarity"` means none.
  - Voucher pool → Fazbear vouchers; the second of each pair only after the first.
  - Packs off: `G.GAME.starting_params.boosters_in_shop = 0`; Tarots/Planets: rates 0.
  - Shop sign: swap `G.ANIMATION_ATLAS.shop_sign` (113x57, 4 frames) only while `G.UIDEF.shop` builds.
  - Panel colours: wrap `ease_background_colour_blind`.
- **Text and tooltips:**
  - Blind panel: wrap `create_UIBox_blind_choice` and walk its UI tree (score text → "Clock in for your shift").
  - Poker hand rows: wrap `create_UIBox_current_hand_row`, rewrite level/chips/mult and `on_demand_tooltip.text`.
  - Playing card hover: wrap `generate_card_ui`, clear `specific_vars.nominal_chips`/`bonus_chips`, add a
    `main_end` line.
  - Deck "how to play" side panels: Steamodded's run-select hover calls the Back's `loc_vars(info_queue)`; each
    `{set = "Other", key = ...}` entry becomes a side tab (text in the mod's `localization/en-us.lua` and
    `default.lua`).
- **Deck skin:**
  - `SMODS.DeckSkin` with `pos_style = 'deck'` takes Balatro's layout: columns 2..10, J, Q, K, A; rows Hearts, Clubs,
    Diamonds, Spades.
  - To force it in one deck's runs without touching the player's setting, wrap the global `get_front_spriteinfo`.
  - Opaque dark fronts cover the white base card.
- **Title screen:** swap `G.SPLASH_BACK` and hide `G.SPLASH_LOGO` when `G.STAGE == G.STAGES.MAIN_MENU`; title cards
  come from `MOD.menu_cards`.
- **Music:** `SMODS.Sound` with `select_music_track` (highest number wins).
- **Long voice clips:** Phone Guy's calls are minutes long; play them as a `love.audio` stream Source so they can be
  muted, paused with `G.SETTINGS.paused` and stopped. Balatro's sound thread can't stop one sound.
- **Images from the mod folder:**
  `love.graphics.newImage(love.filesystem.newFileData(SMODS.NFS.read(path), name))`. Use nativefs as `SMODS.NFS`:
  Steamodded 26.829's preflight still sets a global `NFS`, but only for backwards compatibility.

**Clickteam (FNaF) facts:**
- CTFAK's Sorted Image Dumper writes `Sorted Images/[n] <frame>/<object>/Animation N/_k.png`. Gameplay is frame
  `[3] Frame 1`.
  - Its background object holds the office **and** every camera feed and jumpscare as animations (1600x720).
  - The doors are separate objects: 223 and 248 px wide; closing 16 frames, closed 1, opening 16. They sit at x=72
    and x=1270 in the office.
  - The Custom Night portraits in `[12] customize` are the clearest animatronic art.
  - The title frame has the twitching Freddy, static and the scanline bar.
- The Sound Dumper gives 52 WAVs. Names are Clickteam's own (e.g. `XSCREAM`, `voiceover1c..5`, `ColdPresc B` is
  the deep building drone).

## Build steps
1. Install lovely (`winmm.dll` into the Balatro folder) and Steamodded (into `%APPDATA%\Balatro\Mods`).
2. Build CTFAK with a portable .NET 8 SDK. Copy the `Dumper` and `CTFAK.Decompiler` plugin DLLs into
   `<cli>/Plugins`, and `x64/zlibwapi.dll` + `CTFAK-Native.dll` from CTFAK's `ctfakrequirements.zip`. Apply the
   headless patches in Gotchas 1–3.
3. Dump FNaF:
   `DOTNET_ROLL_FORWARD=Major dotnet CTFAK.Cli.dll -path "<FiveNightsatFreddys.exe>" -tool "Sorted Image Dumper" -closeonfinish`,
   then the same with `"Sound Dumper"`.
4. Convert the dump into the mod folder (scenes scaled to 2/3, card atlases, deck skin, night blind chips, shop sign,
   sounds) with a Python/Pillow script. Keep the output out of any repo.
5. Copy the mod's `.json`, `.lua` and `localization/` into `Mods/<mod>`, then start Balatro and pick the deck.

## Verification
- **Load check (agent):** launch Balatro, wait about 25 s, read the lovely log for errors and Steamodded's
  `Injected <Type>` counts (they rise by exactly the new content), then kill by PID. This only covers mod load and the
  main menu.
- **Hang check (agent):** poll the process CPU every 5 s. A hang shows as about 1 CPU-second per second with no menu;
  normal is about a quarter of that. This is how the `menu_cards` hang was found and bisected.
- **Gameplay (human):** every feature was played in the real game: nights 1–5, Foxy, Freddy, power-out, shop,
  vouchers, deck skin, Blind panel, Run Info, phone calls, title screen. Each crash was diagnosed from the lovely
  log's stack trace.
- **Not verified:** balance of nights 4–5 with doubled cards; non-English languages (the side tabs fall back to
  `default.lua`); other mods' interaction beyond Steamodded + BMM-Compat.

## Gotchas
1. **Symptom:** CTFAK finds "0 tools" and dumps to an empty `Dumps` folder in the .NET install dir. **Cause:**
   `Program.cs` sets the working directory to the *process* exe's folder; run via `dotnet CTFAK.Cli.dll` that's
   dotnet.exe's folder, so `Plugins/` isn't found. **Fix:** use `AppContext.BaseDirectory` instead.
2. **Symptom:** CTFAK crashes with "The handle is invalid" when output is redirected. **Cause:** it draws ASCII art
   using `Console.WindowWidth` and calls `Console.Clear`/`Title`. **Fix:** skip the art when
   `Console.IsOutputRedirected`, and wrap Clear/Title in try/catch.
3. **Symptom:** CTFAK won't start: "Microsoft.AspNetCore.App 6.0.0 not found", then a missing `x64\zlibwapi.dll`.
   **Fix:** run under the .NET 8 host with `DOTNET_ROLL_FORWARD=Major`, and add the two native DLLs from
   `ctfakrequirements.zip`.
4. **Symptom:** the game crashes in `engine/sound_manager.lua: attempt to perform arithmetic on field 'dt'`.
   **Cause:** Balatro treats any sound whose key contains "music" as a music track (it fades it using `args.dt`);
   a one-shot `fnb_musicbox` matched. **Fix:** never put "music" in a sound-effect key. Conversely, real music tracks
   *must* contain it (`music_night`, `music_shop`).
5. **Symptom:** cash out paid about $950. **Cause:** a night sets hands/discards to 999, and Balatro pays per leftover
   hand. **Fix:** set `G.GAME.modifiers.no_extra_hand_money = true`, clear `money_per_discard`, and zero
   `hands_left`/`discards_left` at end of round.
6. **Symptom:** the game hangs on Steamodded's "LOADING: savemanager" screen (busy loop). **Cause:** `menu_cards`
   returning `{ key = "m_<enhancement>" }` goes through `SMODS.create_card` → `create_card`, which rerolls forever
   because that enhancement is `in_pool` false. **Fix:** return `{ remove_original = true, func = ... }` and build the
   cards with `Card(...)` into `G.title_top` yourself.
7. **Symptom:** "attempt to call global 'set_night_blinds'" when starting a run. **Cause:** a top-level `local
   function` was declared below the `SMODS.Back` whose `apply` calls it; Lua resolves the name as a global. **Fix:**
   declare helpers above their first use. Scan for any top-level local used on a line above its declaration.
8. **Symptom:** a hook copied from vanilla crashes inside `type(node)`. **Cause:** vanilla's
   `create_UIBox_blind_choice(type, run_info)` names its parameter `type`, which shadows the builtin. **Fix:** rename
   the parameter in your wrapper.
9. **Symptom:** a stake icon floats in a corner after rewriting the Blind panel. **Cause:** that row's UI node holds a
   live `Sprite`; dropping the node leaves it unparented and still drawn. **Fix:** call `:remove()` on node objects
   you discard.
10. **Symptom:** in Night Guard runs, a dead animatronic card's tooltip said "lures Bonnie". **Cause:**
    enhancement-only cards still sit on a real front (here the Ace of Spades). **Fix:** skip `_c.replace_base_card`
    centers when adding suit text.
11. **Symptom:** `um win shot` / gfxcapture times out on Balatro's menu but works on its loading screen. **Cause:**
    Balatro stops presenting frames while unfocused (even borderless and not minimized). **Fix:** focus the window
    first (with the human's OK), or don't rely on capture for checks.
12. **Symptom:** the converter scripts found no files when run from Git Bash with Windows Python. **Cause:** MSYS
    mangles `/c/...` and backslash paths passed as arguments. **Fix:** pass `C:/...` with `MSYS_NO_PATHCONV=1`, or
    convert with `cygpath -m`.

## Assets
- All from the player's own FNaF via CTFAK, converted locally:
  - office states and camera feeds;
  - jumpscare frames for all four animatronics;
  - door animations and static;
  - the title screen;
  - Custom Night portraits for the animatronic cards and the deck skin's Kings;
  - camera feeds and jumpscare frames for the Queens and Jacks.
- Generated by the converter: the Night 1–5 blind chips, the neon FAZBEAR'S shop sign and the title logo
  (Windows fonts).
- Sound: FNaF's own effects, calls and music. The animatronic "close" sound is the strongest 3.5 s of the
  `ColdPresc B` drone, cut and faded. It was picked by spectral centroid (~156 Hz) because the agent can't listen.
- Nothing from FNaF can be redistributed: a personal install package (installer + generated assets) is fine for the
  owner's own PCs. A shareable release would ship code plus the converter only.

## Cost and time
About one long evening of iterative play-testing with the human, roughly 15 build→test rounds. No API spend
(no generated art).

## Open questions
- Balance of later nights with doubled animatronic cards (hands get clogged).
- A shareable installer that runs CTFAK + the converter on each player's own FNaF automatically.
- Foxy's "run" resolves after the next action; FNaF's real-time pressure is only approximated by the turn clock.
