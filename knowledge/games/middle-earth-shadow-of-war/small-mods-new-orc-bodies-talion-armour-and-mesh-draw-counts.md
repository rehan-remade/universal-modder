---
kind: game
title: "Small mods: two new orc body types for grunts and captains, a Talion armour/sword replacer, and the engine facts behind their bugs (MMSH draw counts, armour cloth in .skel, captain body items, save orc records)"
game: 'Middle-earth: Shadow of War'
games_also: ["The Elder Scrolls V: Skyrim Special Edition", "Solo Leveling: Arise Overdrive"]
game_version: 'Steam build 3095001 (public branch, unchanged since 2018-09-05), Windows 10 22H2; Skyrim SE and Solo Leveling: Arise Overdrive (Steam) as asset sources'
platform: windows
engine: unknown
route: data
tools: ["Python 3.12 + numpy/Pillow (own MMSH/SKEL/.tex/.bndl/.arch06 tools)", "Blender 3.6.23 + blender_niftools_addon 0.1.1 (NIF import)", "Blender 4.2.3 (conform + texture-projection scripts, headless)", "UnityPy (Solo Leveling skinned mesh export)", "custom C# gamedb reader-writer (PowerShell Add-Type)", "texconv", "QuickBMS + aluigi shadow_of_mordor.bms 0.4"]
anti_cheat: "none; extra archives + game.gamedb, exe untouched. All testing offline through the offline-mode DLL and its local Garrison (never signed in to WB)."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["DeimozZarco"]
date: '2026-10-29'
links:
  - "knowledge/games/middle-earth-shadow-of-war/falmer-tribe-a-skyrim-creature-as-a-nemesis-tribe.md"
  - "knowledge/games/middle-earth-shadow-of-war/offline-mode-and-local-garrison.md"
  - "knowledge/games/middle-earth-shadow-of-war/save-format-decrypt-and-collectible-quests.md"
tags: [nemesis, grunts, captains, body-types, body-replacement, garrison, mmsh, mesh, draw-count, havok, cloth, skel, player-armour, replacer, textures, glow, save-editing, gamedb, role-weights]
---

# Small mods: new orc bodies, a Talion armour replacer, and the engine facts behind their bugs

> A batch of small mods on top of the Falmer tribe framework (see the Falmer note), all working in the real game:
> two new orc **body types** (a Skyrim SE orc and Solo Leveling's High Orc) that grunts **and captains of every tribe**
> can roll, which survive Dominate and the Garrison; a **Talion replacer** (Skyrim Daedric armour on the T4 Black
> Númenórean armour, the Ebony Blade on the T4 sword) with the Daedric red glow repainted Ringwraith green; ten
> pool weapons. This note keeps only what was **new** compared with the earlier notes: four engine facts that each
> cost a test round. The mods are personal (for the user and friends) and not published; the hope is that the
> framework and these facts help other modders.

## Setup
- Game: Steam build 3095001, Windows 10 22H2, OfflineMode DLL (see the offline note), tested on the user's
  long-running campaign save (Act 3+, Udûn imported as a region).
- Sources: Skyrim SE (`Skyrim - Meshes0/1.bsa`, `Textures2/5/7.bsa`: Daedric cuirass/gauntlets/boots, Ebony Blade,
  NPC orc FaceGen head), Solo Leveling: Arise Overdrive (Unity; High Orc skinned mesh via UnityPy).
- Our tools (Python unless noted): MMSH reader/writer, SKEL Havok stripper, LTAR packer, bundle builder, a C#
  gamedb editor, a save decrypt/encrypt helper.

## Route and why
Data only, same as the Falmer tribe: converted meshes and textures in extra `.arch06` archives listed in
`x64\default.archcfg`, and edits in `game.gamedb`. Captain bodies hijack **stock** body items, because the corpse
and Garrison paths only accept stock item records (Falmer note). The Talion replacer overwrites one stock player
gear set (route A: same model paths, bundle pairs rebuilt) instead of adding new gear items.

## How the game works (what we had to learn)
### 1. MMSH per-part draw counts (new)
- Besides the per-part records already known (vertex count, index count, palette count), the MMSH header has a
  second per-part block, 48 bytes per part: `u32 vertexBytes, u32 indexBytes, u32 paletteCount, u32 1`, then
  **16 × u16 triangle counts** (one per draw state; stock: every slot = the part's triangle count, except the T4
  armour's body part, which has 0 and a smaller count in the first two slots).
- Find it by its signature: for every part, `indexBytes == 6 × max(slot)`. The game **draws that many
  triangles**. If a part is smaller than the stock template it was written over, the draw reads the *next parts'*
  indices against this part's vertices.
- That is invisible when a mesh's LOD parts are copies of one model (the over-read redraws the same triangles),
  which is why the Falmer bodies, armour and weapons never showed it. On a mesh with different parts (Talion's armour:
  body, cloth stub, gauntlets, glow shells) it draws long black slabs from the arms, lines on the chest and a sheet
  joining the legs.
- Fix: the writer now updates the block (a slot holding the old full count gets the new count; smaller slots are
  capped). A header-only patcher fixes existing archives (same sizes; loose meshes and meshes inside `.embb`
  bundles). **Run it last on every archive before installing**, since raw-byte mesh tools bypass the writer.

### 2. Player armour cloth lives in the `.skel` (new)
- 30 of 32 player armour `.skel` files carry Havok data: tagged block `04 ff dc dc`, holding `u32 count`, count × u32,
  then count × (`ed fe ef be`, `u32 size`, TAG0 blob). Cloth-free skels (Celebrimbor's) store count 0.
- The Black Númenórean armour's blob is an `hclClothContainer` whose mesh-deform operators move **render vertices by
  index**. On a replacer mesh that drags random vertices.
- Stripping the sections (count → 0, rest of the file byte-identical: bones, anix list) removes the cloth safely. In
  our case it was not the slab cause (that was fact 1), but a replacer needs it either way.

### 3. Captain body items: what makes the generator hand one out (new)
- An orc in the save has an item list and an appearance record (fact 4). Falmer-body captains of **every** tribe
  carried the hijacked `Infested_Body` item. High Orc / Skyrim orc captains, on the hijacked story items
  `Flint_Body` / `Tinder_Body`, carried **no body item**: the body lived only in the appearance record.
- The next body-slot roll then replaced it. Tark Slayer promotions (an orc that kills Talion) rolled `Infested_Body`
  (the orc came out Falmer, which looked like "it joined the Falmer tribe") or `IT_Body_Scar` (stock scarred body).
- Where the items differed (gamedb attribute hashes): `29D1CBB4` character type list (`Trait_AllBut_Olog` vs empty),
  `B2EDA81E` (50 vs 20 / 0), `E512B887` own LOD body item (none vs `Flint_BodyLOD`), appearance tags
  `C06541A5` / `44009124` (`Right_Shoulder` vs `Right_FullArm` / `Left_FullArm`).
- Copying Infested's values onto the hijacked items fixed it. On the next load the game gave the body items to the
  existing new-body captains by itself, and new captains kept their bodies through Dominate and the Garrison.
- Not fixable by data: **role-forced scars**. Titles whose role items use `IB_Body_Scar` → `AD_Body_Scar`
  (Face-Eater, Blood Axe, Who Devours, Battle-Forged, gluttons) swap any body for `Orc_<Size>_Body_Scar`, stock
  and Falmer included. `AD_Body_Scar` pickers key only on body type (2 slim, 3 buff, 4 stocky, 5 olog).

### 4. Orc records in the save (new detail)
- Decrypted with the save tool from the save note. Name references are 4-byte name hashes.
- An orc's **item list**: entries 69 bytes apart; the body item sits right after `IT_Orc_Body_LOD`, the head item
  after it.
- Then its **role** (`Faction/Roles/Definitions`), then the **appearance record**: grunt class model at −12, head
  entry (`<Name>_<Size>_Body_WildHead`) at 0, then 5-byte fields: body piece +5, head piece +10, quiver +20,
  helmet +40, shoulders +45, chest +50, arms +55, pants +60, legs +65, body LOD +70. Some orcs have two appearance
  records after one item list.
- The save stores the resolved **pieces**, so a db change to a head entry does not reach existing orcs. Our old
  "headless" captains kept `Smp_Empty_Set` as their head piece.
- Same-length hash swaps (body piece, head piece, body item) repaired them; the swapped pieces stuck on load.

### Smaller facts
- Custom grunt head bundles must be in `NPCHead.StaticBundles`, a `DynamicResource/ResourceGroup/DynamicHeads`
  field next to MaxLoaded 100, DynamicSlots 45 and DynamicBundleCandidates. Otherwise they compete for the 45
  streamed slots: invisible grunts (only intel/loot markers) and walking stutter.
- Tribe share = role entry count. The Falmer build listed each Falmer role N times in all 128 role lists that hold
  them. At 3×: 24 % of `All_DLC3_Roles` (goblins at 1×: 8 %), and 62 % of one DLC5 list. Dedupe to 1× for "same
  odds as any tribe".
- A `wraith_game.fxo` material on an extra part of an opaque player armour model never drew (3 tests). Painting the
  glow instead worked: rasterise the armour parts in texture space, measure each texel's bind-pose distance to
  Skyrim's glow shells (BVH nearest), paint green with the shell's vapour pattern, and mark those texels dielectric
  in `_s`. It read as glowing in lit scenes.
- Plugins for the ME ModLoader (`OnPluginLoad(api)`) run under a tiny loader shim of our own. Nemesis Recurrence
  dereferences the API object, so the shim must pass a dummy object (vtable of no-ops), not null.

## Build steps
1. Bodies: export the skinned source mesh, conform it onto the stock orc rig (Falmer note's segment method), write
   per-LOD MMSH on the `body001` templates, and build head-only copies for the WildHead entries. Add grunt-list
   entries; hijack a stock body item per new body (pickers for slim 2 / stocky 4 / buff 3, ModelFixUp pieces, mats
   bundle) **and make the item generator-valid (fact 3)**. Add the head bundle to `NPCHead.StaticBundles`.
2. Talion: conform Skyrim armour onto the T4 armour template (keep its 4-part layout and part-name hashes), strip
   the `.skel` cloth, paint the glow, then rebuild both bundle pairs from the newest stock `.bndl` entry list. Ship
   the loose `.tex` + `.tex0` pairs too: a `.tex0` beats the highmip stream.
3. Every archive: run the MMSH draw-count patcher (fact 1), then install. Close the game first and back up the
   saves, archcfg and db.

## Verification
The oracle was the real game, played by the user, with screenshots read after every test, plus read-only decrypts
of the live autosave (safe while the game runs) to see what orcs actually stored.
- Talion: no slabs or stretching after fact 1, Daedric armour fits, the green paint reads well, and the Ebony Blade
  edge faces forward.
- Bodies: High Orc and Skyrim orc grunts appear (~1 in 6 each). A captain made after the fact 3 fix kept its body
  through Dominate and in the Garrison.
- Save repair: repaired captains showed their bodies after reload.

Not verified:
- the exact meaning of the 16 draw-count slots;
- which of the four item fields matters most (all four were copied);
- a captain made **before** the fact 3 fix: repaired, dominated and accepted into the Garrison, but it showed a stock
  body there;
- long-term save stability.

## Gotchas
1. Long black slabs from a replacer mesh → stale MMSH per-part triangle counts (fact 1) → write/patch the draw
   block. Not the cloth, not the skinning (both checked first: weights normalised, palettes in range, only stock bones).
2. A mesh reader that infers vertex counts from the max index reads collapsed (hidden) parts as 1 vertex → read
   counts from the template's records; never "fix" the records of hidden parts from such a read.
3. New-body captains keep the head but lose the body → no body item (fact 3) → make the hijacked item generator-valid.
   The same symptom on a titled orc can be a role-forced scar, which is stock behaviour.
4. A captain promoted for killing Talion "turned Falmer" → it rolled `Infested_Body` because it had no body item; it
   did not change tribe. Check the role in the save before blaming tribe weights.
5. Old headless captains stay headless after a db fix → the save stores the head piece → hash-swap repair.
6. Invisible grunts and stutter after adding body types → head bundles not in `NPCHead.StaticBundles`.
7. `archcfg` is LF-only on this install (it was CRLF earlier): keep whatever line ending the file uses.
8. Windows PowerShell 5.1 `Add-Type` compiles C# 5: no `out var`. A `Nullable<uint>` field unwraps in PowerShell,
   so `.HasValue` is always false: test against `$null` instead.

## Assets
Converted Skyrim SE and Solo Leveling assets stay on the user's machine; nothing is redistributed. Tools are the
user's own scripts. No game files are in this note.

## Cost and time
One long session (2026-10-29), about eight in-game test rounds by the user.

## Open questions
- The meaning of the 16 draw-count slots (hide states? the T4 armour body part uses 0 / fewer in slots 0-1).
- Whether a real emissive glow is possible on player armour (`talion_armor.fxo` has no emissive input; the weapon
  shader has one).
- Next project (planned): two new human factions on the Easterling / Gondorian soldier bases, one hostile to all
  and one friendly to Talion, with dominatable captains.
