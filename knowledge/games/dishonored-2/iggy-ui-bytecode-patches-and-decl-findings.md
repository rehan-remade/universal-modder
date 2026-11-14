---
kind: game
title: 'Iggy UI bytecode patches (same-length AVM2 rewrites) and decl, material and map findings'
game: Dishonored 2
games_also: ["Dishonored: Death of the Outsider"]
game_version: 'GOG (DRM-free), Dishonored2.exe PE timestamp 0x5c050611; DOTO GOG Dishonored_DO.exe 0x5c0584aa'
platform: windows
engine: idtech
route: data
tools: [python 3.15, own AVM2 disassembler and re-encoder, zlib, the user's resource export/import tool]
anti_cheat: 'none (single-player, GOG build has no DRM)'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-14'
links:
- https://github.com/chipolux/disrev
- https://www.nexusmods.com/dishonored2/mods/30
- https://www.nexusmods.com/dishonored2/mods/31
tags: [void-engine, idtech5, iggy, avm2, as3, flash-ui, decl, materials, dark-vision, resources-index, voidmod, physhape]
---
# Iggy UI bytecode patches (same-length AVM2 rewrites) and decl, material and map findings

The data side of a large Dishonored 2 mod set (the exe side is in
[the exe-fixes note](gog-exe-fixes-with-an-added-code-section.md)). The UI is RAD Iggy (Flash/AS3).
Behaviour changes were made by rewriting single AS3 method bodies in the exported `.iggy` files at the same
byte length. Examples: the Corvo Doppelganger icon, removing the main-menu promo, a 4-column / 4-row Powers
journal, two-digit rune costs, the mission-results picture. Plus the decl/material/map facts behind
several data-only fixes. All listed results were tested by the user in game. The results-screen patch runs in
both Dishonored 2 and Death of the Outsider.

## Setup
- GOG Dishonored 2 (and DOTO for the shared UI), Windows 10.
- Resources were exported and imported by the user with their own tool. It writes a `game1_voidmod` overlay
  in the Void Installer style (Nexus 31). Our scripts only read the exports and write patched copies.
- No JPEXS / Java on the machine. We wrote a small AVM2 (ABC) disassembler and a method-body re-encoder in
  Python (decode -> edit instruction list -> re-encode branches -> pad to the original length).

## Route and why
- Data only, by request. Every change is a same-length edit, so the file layout, string pools and offsets
  stay valid. Same-length matters because the Iggy file stores the ABC inside a larger binary with offsets.
- Growing a method body or adding pool entries would mean relocating the ABC block; not attempted.

## How the game works (what we had to learn)
### Resources and the overlay
- Containers: `base/gameN.index` + `.resources` (+ `_001..`, `_patch`) as described by chipolux/disrev and
  [the bonecharm note](black-and-corrupt-bonecharm-traits-learnable-and-ng-persistent.md).
- The engine inflates with a **1 KB zlib window** (header `28 15`). An earlier version of the user's import
  tool wrote that header but compressed with a 32 KB window. Small files survived by luck; a big map
  `.entities` crashed at half the loading bar. A one-file A/B proved it: original compressed bytes in the
  overlay loaded, the tool's bytes didn't. Python's `zlib.decompress` with wbits 15 hides the error; decode
  with wbits 10 to check. (The tool's author has since fixed it.)

### Which `.iggy` runs
- A screen loads the `.iggy` copies **inside its `iggyFile` container** (e.g. the power wheel container
  holds its own `quick_access_wheel.iggy` and `lib_wheel.iggy`), not the standalone file entries.
- The class that runs is usually the **library's** copy (`lib_*.iggy`), not the host screen's copy of the
  same class. Examples: `WheelItem` runs from `lib_wheel`; main-menu `PromotionData` runs from `lib_main`
  (DOTO: from a separate `lib_promotion.iggy`). Patch every copy, or find the running one with a forced
  diagnostic change (e.g. an unconditional icon swap) first.

### AVM2 rules that bit us
- **max_stack / local_count:** the method body header declares them, and the verifier rejects a body that
  needs more. The game then crashes at the screen. Raise them when the new code needs more.
- **Multinames:** a property name exists many times in the pool under different namespaces. The first
  `scaleX` was `com.ark.core:IDisplayObject`'s (a TextField doesn't have it -> ReferenceError, the whole
  tree failed); the first `length` was an interface's (undefined on a String). Use the **public QName**
  (namespace kind 22, empty name).
- **Names missing from an ABC** can be built at runtime from substrings of existing pool strings and read
  with a runtime multiname (used for `characterIndex` in `lib_wheel`).
- **Making room in a body:** drop `debug`/`debugline` that aren't branch targets, redundant casts
  (`astypelate` + `coerce`), dead debug-build blocks, redundant initialisers. Re-encode branch offsets.
  Pad with `nop`.

### Specific UI facts
- Power wheel: `itemIndex` is the icon frame **and** the slot order (`_itemsOrder[itemIndex]`) and the
  power/gadget test (`itemIndex > G_MAX`). Corvo's Doppelganger mask is an extra frame 25 in the icon clip.
  The AS3 `characterIndex` is CORVO=0, EMILY=1 (the native value minus 1).
- Main-menu promo: `PromotionData._initData` fills only if `active`. `PromotionScreen.playShowAnimation`
  hides the panel then calls super, and super shows it again; the opening tween also re-shows it.
- Powers journal: `PowersLayout` columns = `lastIndex < 6 ? 3 : 4`. Upgrade tree screen: tree height > 800
  -> y offset -75 and scale 0.905, else 1 (no size step for 4 rows).
- Rune cost labels: two Labels (`costLabel` white, `costLabelShad` black) owned by the cost clip's timeline
  (state frames set their matrices and hide one). Don't scale them.
- Results screen `GlobalStatPanel`: Pacifist/Ghost picture = bitmaps `mr_*_on/off` (the red cross is baked
  in); the frame comes from the achievement clip's `open_ON`/`open_OFF` timeline.
- Fonts (`lib_loc_<lang>_font.iggy`): 6 `ArkFont` slots bound by the Iggy export table. In Chinese only the
  Italic slot's font has the full CJK set; the other 5 are Latin stubs, so every CJK glyph falls back to it.
  Fill stub slots with other fonts (keep 6 fonts and their names); a 7th font is unbound.

### Decl, material and map facts
- **Dark Vision / highlight** is a material option: `rendering/darkVisionLayer N`. 0 = none, 1 = devices
  (the **default when the line is missing**), 2 = living, 3 = pickups, 4 = DV's own FX. The white pickup
  outline = `outlineable 1` + `passiveoutline 1`. Baked `.bwm` level geometry keeps its layer even if the
  material decl changes. DOTO reads the same layers for Foresight.
- **Potion pickup sound fails at random:** `bsp_ui_pickup_potion` is the only *spatialized* pickup UI sound,
  and its plays are delayed 100-150 ms on an entity that is removed on pickup. Fix: `m_Spatialized false`,
  `m_MaxDistance` 8 -> 150 (same in DOTO).
- **Street musicians:** `musician_*` soundevents `m_MaxDistance` 35 -> 150 (DOTO 40 -> 150), so the music
  joins when you arrive halfway (pairs with the exe songsync fix).
- **Bonecharm crafting level clamp:** `m_maxCraftingCorruptionLevel` defaults to 3 and the rune's
  `m_requiredLevel` to 4 in the decl constructor (neither is in the vanilla decl), so a level-4 corruption
  entry is ignored until the max is raised. Rune defaults: cost 9 whalebone, dismantle gain 8.
- **NG+ carry-over** obeys per-character `inventory_collection` decls: `m_maxQuantity = 0` blocks an item.
- **NPC pistols:** pointing the holster pickable at a generic inventory item (player max 99) makes stealing
  remove the gun without granting a bullet. Placed pistols: each map overrides the pickable; add
  `m_entityContext POSSESSED` to make them non-interactive. In DOTO the bullet item became Voltaic Gun ammo,
  and placed pistols share their map component with loose bullets: clone it, don't edit it in place.
- **Far Reach object snap:** `cpntplayersensorgrapple` `m_snapKinds[].m_snapMaximumAngle` per kind (pickup,
  movable, grenade, severed limb); `m_snapMaximumDistance` = range.
- **Spyglass zoom per weapon:** the masterwork upgrade's `m_upgradeInfo.m_spyglassZoomLevelFxs` replaces the
  FX manager's zoom list while that weapon is in hand.
- **Sound zones** are Havok physhape `.cvd` files (`maps/<map>/<name>.cvd._100_100_100.0`); moving a zone
  edge = editing the plane floats in place (same size). CE player coordinates equal `.entities` coordinates
  (metres).

## Build steps
1. Export the `.iggy` copies (standalone **and** the ones inside each `iggyFile` container) with your tool.
2. Disassemble the ABC, find the method, write the new instruction list, re-encode at the same length; raise
   max_stack/locals if needed. Check: the method decodes, every branch lands on an instruction, the length is
   unchanged.
3. Import with your tool (and, on older tool versions, recompress with zlib wbits 10).
4. Data edits are plain decl/material text edits in the exported files.

## Verification
- Offline: every patched body decodes and re-encodes; patched files differ only in the target bodies (and
  their header bytes).
- In game (user): Corvo/Emily icons correct everywhere (wheel, HUD, shortcuts); promo panel and header gone
  (3rd version); 4 columns and the 4-row tree size step (scale 0.72 above height 1000); two-digit costs
  `<font size=F*88%> <font size=F*70%>NN</font></font>` sit right; results picture moved, frame/cross
  hidden in both games; potion sounds; musicians; placed pistols; Dark Vision weapon highlights off;
  curator shaft zone edge.
- Not verified: Chinese font replacement (advice only).

## Gotchas
1. **Edited `.iggy` imported, no effect at all.** **Cause:** the screen runs the copy inside its container,
   and the running class is the library's. **Fix:** patch the container copies of the `lib_*` file; find
   the running one with a forced diagnostic edit.
2. **Results screen crashed both games after a UI patch.** **Cause:** the body needed max_stack 4, declared 3
   (verifier). **Fix:** raise the header byte.
3. **Tree failed to build (ReferenceError) after scaling a TextField.** **Cause:** the interface-namespaced
   `scaleX` multiname. **Fix:** the public QName.
4. **Scaling the rune-cost Labels showed the black label and shifted the white one.** **Cause:** the clip's
   timeline owns those Labels. Scaling the inner TextField clipped the first digit. **Fix:** set `htmlText`
   with `<font size>` (the label keeps its own size and alignment). A leading space at 88 % sets the
   baseline so the 70 % digits don't float.
5. **Promo panel came back after hiding it.** **Cause:** `super.playShowAnimation()` and the opening tween
   both re-show it. **Fix:** replace the method body with `visible = false`.
6. **Removing `darkVisionLayer` made weapons blue (devices).** **Cause:** the default layer is 1. **Fix:**
   write `rendering/darkVisionLayer 0`.
7. **Swapping a baked mesh's material didn't change its Dark Vision glow.** Baked `.bwm` surfaces keep the
   layer from build time. Dead end.
8. **Big map `.entities` import crashed at load, small files fine.** 32 KB-window zlib under a 1 KB header
   (see above).
9. **Enum values in decls are names only** (the parser string-compares), so a decl can't select an icon
   frame number that has no enum name.

## Assets
The user made their own pistol pickup icon (DDS) and recoloured the results frame. No generated assets.

## Cost and time
Spread over five days alongside the exe work; most UI patches needed two or three in-game rounds.

## Open questions
- Relocating or growing an ABC block inside an `.iggy` (would allow longer methods and new strings).
- Lean-hold tutorial variant isn't in `m_tutorials`, so it never shows as read (left as is).
