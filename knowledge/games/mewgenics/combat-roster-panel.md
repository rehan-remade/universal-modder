---
kind: game
title: "Combat Roster Panel: a native ImGui party panel for Mewgenics, drawn with the game's own art, fonts and text"
game: "Mewgenics"
games_also: []
game_version: "1.1.21239, Steam build 25143593, Mewgenics.exe SHA256 4127cd6a...77ea (SizeOfImage 0x1574000)"
platform: windows
engine: unknown
route: native-hook
tools: ["Mewjector 3 (built from source)", "MSVC 14.51 + CMake/Ninja", "Dear ImGui 1.92.3", "Ghidra 12.1.4 headless", "capstone", "ReadProcessMemory (read-only live inspection)"]
anti_cheat: "none (single player)"
status: released
agents: ["Claude Code (Opus 5.5)"]
humans: ["@TotSamiyMorzh"]
date: 2026-10-05
links: ["https://github.com/TotSamiyMorzh/mewgenics-combat-roster", "https://www.nexusmods.com/mewgenics/mods/539"]
tags: [native-dll, imgui, overlay, sdl3, opengl, swf, flash-rasteriser, fonts, cjk, localisation, portraits, ui]
---

# Combat Roster Panel: a native ImGui party panel for Mewgenics, drawn with the game's own art, fonts and text

> A DLL loaded by Mewjector adds a draggable, collapsible, resizable side panel in battle: every friendly
> unit (cats, familiars, summons, allied bosses) with portrait, HP/shield/mana bars and status icons, and a
> scrollable tooltip with stats, equipment, passives, abilities and effect descriptions. Hovering a row draws
> the game's own aim reticle on that unit's tile. Everything visible comes from the player's install at
> runtime: SWF art rasterised by the mod, the game's fonts, and text from the game's StringsDatabase (so it
> follows the game's language). Verified in real battles by the human player, with screenshots.

## Setup
- Mewgenics 1.1.21239 (Steam build 25143593), Windows 11. Every RVA below is for this exact exe; code
  addresses are resolved by byte signature at startup so a patch fails loudly instead of silently.
- **Not Unity.** Tyler Glaiel's native C++ engine (`glaiel::`), SDL3 statically linked with its dynamic-API
  shim, OpenGL 3.2 core, a hand-written Flash SWF player for UI/animation, GON data in `resources.gpak`.
  Ask: "is there a `UnityPlayer.dll`/`*_Data`?" before planning a BepInEx mod.
- Loader: Mewjector (version.dll proxy, MIT, github.com/githubuser508/mewjector), built from source with
  `cl /LD`. Its `build.bat` calls `vswhere -latest` without `-products *`, so it misses VS Build Tools.
- Build: MSVC 14.51 (VS 18 Build Tools), CMake + Ninja, `/EHa` (SEH and C++ in the same frames), static CRT.
- Reference (not shipped, MIT, read for facts): SanTertrust/mgmp (battle structures, the SDL swap slot,
  `tile_piece`), p0lymeric/mewgenics_analysis (`CatData` layout), z3ndroot/mewgenics-cat-bridge.

## Route and why
`native-hook`: no managed runtime, no official code-mod API. Mewjector gives a proxy DLL plus chainable
inline hooks (`MJ_InstallHook`), which keeps us compatible with other DLL mods. The UI is our own Dear
ImGui frame, not the game's SWF UI: building game components means owning their lifetimes across scene
teardown (mgmp warns against it). To still look native, the mod rasterises the game's own SWF art.

## How the game works (what we had to learn)
**Hooks used** (all `void(this)`): `ApplicationBase::FrameBegin` (frame counter), `TurnControl::NextTurn`
(captures `TurnControl*`), `StatusMenu::update` (the battle HUD tick; also where the highlight is submitted).

**Screen-space drawing.** `SDL_GL_SwapWindow` is a thunk through SDL's DYNAPI table in `.data`; replacing the
**slot** (RVA 0x012E7650) is the hook, the old value is the trampoline. On this build the table is already
live when Mewjector loads mods; the default stub is recognisable because it ends in `jmp [its own slot]`.
ImGui: win32 + opengl3 backends, `#version 150`. Bind framebuffer 0 and clear `GL_PIXEL_UNPACK_BUFFER` around
the draw. The GL context is recreated on resolution changes, so re-init the renderer backend by abandoning
its book-keeping; never `glDelete*` in the new context.

**Battle roster.** `TurnControl+0x18 ->+0x08 ->+0x20 ->+0x1F90` = `{.., u32 count @12, Character** @16}`.
`sizeof(Character)` 0x0EE0. Validate each one with `Character+0x60` -> TacticsObject and its `+0x98` back-link.
| Character field | Offset |
|---|---|
| HP / shield / max HP / dead | `+0x4B0` / `+0x4B4` / `+0x4BC` i32, `+0x4C2` bool |
| team current / original (mind control) | `+0x350` / `+0x358` i16 |
| kind (2 boss, 3 cat, 4 board object) | `+0xCF4` i32 |
| name key / desc key / class | `+0x248` / `+0x268` / `+0x2B0` std::string |
| final localised display name | `+0x290` std::wstring (written by the name refresh `sub_14011C560`) |
| mana / max mana | `+0xD18` / `+0xD1C` i32 |
| CatData* | `+0x88` (found by scanning for a pointer that passes CatData checks) |
| passive cache `{cap,count,Passive**}` | `+0xE70` (statuses are Passive subclasses) |
| abilities: attack / spells | `+0xD8` / `{count +0xEC, Ability** +0xF0}` |

- **Friendly units.** The game classifies a team through 14-entry byte tables filled at startup. Read their
  base from the `lea r11` in `sub_14011A410`: `+0x0E` is-ally, `+0xD2` is-enemy; teams > 0xD mean "team == 1".
- **Statuses.** The RTTI class name of each Passive (`Bleed`, `DodgeChance_Status`, ...) is the
  `keyword_tooltips.gon` key. Stack count is `Passive+0x5C`. Whether the game shows an icon for it comes from
  `get_status_icon`'s `unordered_map<string, StatusIconInfo>` (`lea rcx` in `sub_1404933E0`): node key at
  `+0x10`, info at `+0x30`; `{frame_pos, frame_neg}` are 1-based frames of ui.swf `StatusIcon`, and -1
  means no icon. Do not call that function: it consumes its string argument.
- **Ability cost block.** `Ability+0x4C` mana, `+0x50` charge, `+0x64` uses_per_fight; GON id at
  `*(Ability+0x28)+0x88`. There are no classic cooldowns.
- **Text.** `glaiel::StringsDatabase` global (`lea r15` next to `mov rbx,[rdi+468h]` in the name refresh);
  lookup `sub_1409616D0(db, wstring* out, const string* key, bool fallback)` only reads the key and returns the
  key itself when missing. The language code is at `db+0x40`. id -> loc key maps come from GON: items
  `name/desc` (+`frame`, `ability`), abilities `meta.name/desc` (+`variant_of`), passives `name/desc`,
  classes `meta.name` and `graphics.palette`, characters `graphics.name` -> `graphics.movieclip`+`Portrait`.
  Item-granted abilities are named `{itemname}`: use the granting item's name.
- **Art lives in Flash.** `resources.gpak` (index: u32 count, then `{u16 len, name, u32 size}`; data after the
  whole index) holds FWS SWFs: ui.swf (StatusIcon x1015, HealthIcon, ManaIcon, FontIcon_<stat>, tooltip paper
  bitmap #1), portraits.swf (`<Movieclip>Portrait`), ability_icons.swf (`AbilityIcon`/`PassiveIcon`, frames
  labelled by id), catparts.swf (`<Slot>ItemIcon` by item `frame`-1, cat parts), international_fonts.swf
  (DefineFont3 Latin+Cyrillic, e.g. `TikaFontIntl`, `Mewgenics Organ Grinder Cyr`), unicodefont.swf
  (`Noto Sans CJK TC Regular`, 41200 glyphs: the fallback for Chinese/Japanese/Korean). Named instances the code
  toggles (`sloticon`, `rarity`, `label`) must be skipped.
- **Cat faces** (`glaiel::CatParts::init` `sub_14073CC70`, placement `sub_1407393E0`). Use `CatHeadPlacements`
  frame head-1. Ears go on `lear`/`rear` with the full marker matrix; eyes on `leye`/`reye` and the mouth on
  `mouth` with the marker position only (scale 1, `reye` mirrored). The `tex` slot frame is texture-1. The
  head fill is a clip mask. Colour: `shaders/paletted_full.shader` maps grey `r` to
  `palette.png[row][round(r*15)]`; in battle the row is the class palette. CatData BodyParts at `+0x60`:
  texture `+0x18`, palette `+0x1C`, 14 descriptors from `+0x2C` (stride 0x54, sprite idx at +4).
- **Mouse.** Several SDL event handlers write the engine's cached mouse position, so it cannot be overridden
  in one place. While the pointer is over the panel, the WndProc subclass passes SDL an off-window
  `WM_MOUSEMOVE`, swallows clicks and wheel, draws `textures/cursor/default.png` (hotspot from
  `hotspots.gon`) itself, and answers `WM_SETCURSOR` with no cursor.

## Build steps
1. Build Mewjector `cl /nologo /LD /O2 /GS- version.c /Fe:version.dll /link /DEF:version.def`; copy
   `version.dll` + `chainloader.ini` next to `Mewgenics.exe`, create `mods/`.
2. Build the mod (CMake + Ninja under `vcvars64`), copy `combat_roster.dll` into `mods/`.
3. Offline tools in the same CMake project: `swf_test`, `font_test`, `glyph_test`, `cat_test` render the
   player's own gpak to PNG. Use them before every in-game test.

## Verification
- Logs: `mod_logs/chainloader.log` (Mewjector integrity check) and the mod's own log (hooks, asset counts,
  CatData discovery, status table size, a one-time passive dump used to confirm the stack offset).
- Live, read-only `ReadProcessMemory` on a running battle confirmed: mana (6 units vs HUD/GON), display names,
  stack counts (Trample 3 / BoostHeals 2 / Metal 1 = GON), party CatData part indices.
- Offline PNG renders compared by eye with in-game screenshots (icons, frames, fonts, cat faces in class
  colours). The human played several battles and sent screenshots after each build.
- CJK (added in 0.5.1): an offline ImGui atlas test baked Chinese, kana and hangul code points through the
  loader and the atlas was inspected by eye; the game then loaded the 41200-glyph font cleanly.
- Not verified: other game builds, Proton, and an actual battle played in a zh/ja/ko game language (the
  player who reported the `?` bug has not confirmed the fix yet).

## Gotchas
1. **"It's a Unity game."** It is not: native C++. Check the install folder before planning a stack.
2. **SDL hook never fires.** Splicing the `SDL_*` thunk or the stub behind it does nothing. Write the DYNAPI
   **slot** instead.
3. **The swap slot "never changes".** On this build the table is already initialised at load. Detect the
   default stub by its self-referencing `jmp [slot]` rather than waiting for the value to change.
4. **Fonts crash in `AddFont`.** ImGui 1.92 copies `FontData` when `FontDataOwnedByAtlas=false`, so a pointer
   smuggled through it becomes garbage. Pass no `FontData`, set `FontLoader`, and find your font by
   `src->Name` in `FontSrcInit`.
5. **Glyph atlas "all black boxes".** The atlas is RGBA32. Look at the alpha channel, not the luminance.
6. **Stacks read 0.** The stack count is `Passive+0x5C`, not `+0x58`. Check against a GON value (`Trample 3`).
7. **StatusIcon frames off by one.** The table is 1-based; use frame-1.
8. **Cats render in the wrong colours.** The heritable palette is the house look; in battle the class palette
   (`classes.gon graphics.palette`) is used.
9. **Cat eyes/mouth stretched into a line.** Those markers carry placeholder scales; only their position is
   used (the right eye is mirrored).
10. **Grey dagger on every item icon.** It's the `sloticon` instance the game hides in code. Skip named
    toggles.
11. **Panel blinks while moving the mouse over it.** The battle HUD skips 2-11 frames now and then; requiring
    a HUD tick within 2 frames made the panel vanish. Tolerate about 20 frames.
12. **Windows arrow on top of the game cursor.** Once SDL thinks the pointer left, its `WM_SETCURSOR` shows the
    arrow. Answer `WM_SETCURSOR` with `SetCursor(nullptr)` while over the panel.
13. **Status lookups by name.** `get_status_icon` destroys its `std::string` argument. Read its map instead
    of calling it.
14. **Wheel scrolled both the tooltip and the list.** `SetItemKeyOwner(ImGuiKey_MouseWheelY)` on the hovered
    row, then drive the tooltip's `SetScrollY` from `io.MouseWheel`.
15. **The range highlight is not a draw.** `sub_140138A10`-family "highlight" applies statuses. For a
    harmless board marker use `ImmediateModeGameUI::tile_piece` with `TargetCursor` (16-byte aligned colour
    and scale; strings of 15 chars or fewer).
16. **Chinese / Japanese / Korean text shows as `?`** (2026-10-05, reported by a player after release). The
    game's main fonts (`TikaFontIntl` etc.) only cover Latin + Cyrillic, and the merged fallback was Segoe UI,
    which has no CJK. **Fix:** merge the game's own fallback font behind the main one: `swfs/unicodefont.swf`
    holds `Noto Sans CJK TC Regular` as a DefineFont3 with 41200 glyphs (kana and hangul included), then system
    fonts (`msyh.ttc`, `malgun.ttf`, `YuGothM.ttc`) behind that. Parse glyph outlines lazily (keep the tag
    bytes and per-glyph offsets, parse on first raster) so 41k glyphs cost nothing up front. That file exports
    no symbols, so a loader that treats "no SymbolClass" as failure must not gate font extraction on it.
    Lesson: test a text mod in a non-Latin, non-Cyrillic language before shipping it.

## Assets
None generated. All art, fonts and text are read from the player's own `resources.gpak` at runtime and never
written to disk or shipped.

## Cost and time
One long session (about 4-5 hours wall clock), including a 17-minute Ghidra auto-analysis. The CJK fix after
release took about 20 minutes. Released as 0.5.1 on GitHub and Nexus Mods.

## Open questions
- Hats/face items on the cat face need an extra offset that wasn't found (drawn at the `ahead`/`aface`
  marker they cover the eyes). Portraits are drawn without items for now.
- Eyebrow placement is approximated at the eye markers. The real offset is set in a CatParts update not yet read.
- Signatures are generated by hand for ~10 targets; a gen_sigs-style script would make updates painless.
