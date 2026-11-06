---
kind: game
title: "Falmer tribe: a Skyrim creature imported as a Nemesis tribe, with titles, wild grunts/prisoners and Skyrim audio (mesh conform, MMSH/texture/bundle format, body-replacement items, grunt body loading, Wwise PCM bank replacement)"
game: 'Middle-earth: Shadow of War'
games_also: ["The Elder Scrolls V: Skyrim Special Edition"]
game_version: 'Steam build 3095001 (public branch, unchanged since 2018-09-05), Windows 10 22H2; Skyrim SE (Steam) as the asset source'
platform: windows
engine: unknown
route: data
tools: ["Blender 3.6.23 + blender_niftools_addon 0.1.1 (NIF import)", "own Wwise SoundBank v118 reader/writer (Python, PCM WEMs; no Wwise authoring tool)", "Blender 4.2.3 (conform script, headless)", "Python 3.12 + numpy (own MMSH/.tex/.bndl/.arch06 tools, BSA reader)", "custom C# gamedb/strdb reader-writer (PowerShell Add-Type)", "QuickBMS + aluigi shadow_of_mordor.bms 0.4", "Ghidra 12.1.4 (headless, analysis only)"]
anti_cheat: "none; loose data + an extra archive, exe untouched. All testing ran offline through the offline-mode DLL and its local Garrison (never signed in to WB)."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["DeimozZarco"]
date: '2026-10-20'
links:
  - "knowledge/games/middle-earth-shadow-of-war/goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md"
  - "knowledge/games/middle-earth-shadow-of-war/offline-mode-and-local-garrison.md"
  - "https://github.com/niftools/blender_niftools_addon"
tags: [nemesis, tribe, creature-import, skyrim, falmer, mmsh, mesh, skinning, textures, tex0, bundles, archive, gamedb, garrison, corpse, ragdoll, body-replacement, titles, grunts, ambient-spawns, prisoners, wwise, audio, soundbank]
---
# Falmer tribe: a Skyrim creature imported as a Nemesis tribe

> Skyrim SE's **Falmer** are a working Nemesis tribe in Shadow of War: they have their own tribe name, 80 roles
> (Act 2+), and the Falmer body and head on slim, stocky and buff orcs, with real Skyrim skin textures and
> Deranged non-verbal voices. They can be dominated and recruited, they never come back from death, and their
> corpses stay on the ground. They can also go to the Garrison and be deployed back out. The pipeline: conform the
> Skyrim mesh onto a stock **body-replacement** template (the Infested body), write it as the game's MMSH, pack it in
> our own archive, and wire it in through game.gamedb **on the stock Infested body item**. That last part is what
> makes corpses and the Garrison work. Verified in game by the user over many sessions (2026-10-13 to 10-15).
> **Update 2026-10-20** (user-tested): the captain body moved to
> the base orc `body001` template with a bending neck; five Falmer-orc-only **titles**; **wild Falmer** mixed into
> every orc grunt class in the field and outposts, and Falmer **prisoners**; the captains' voice replaced with
> **Skyrim Falmer sounds** by rewriting Wwise banks with PCM media. The Garrison refusals that remained turned out to
> be duplicate offline NPC ids (fixed in the [offline-mode note](offline-mode-and-local-garrison.md)). Skyrim
> animations were dropped (the wild Falmer use the orc rig).

## Credits and prerequisites
- **Bethesda**: the Falmer meshes and textures come from the user's own Skyrim SE install. **No Skyrim or
  Shadow of War files are in this repo.** Anyone repeating this extracts them from their own copies.
  - The built `.arch06` holds Bethesda's meshes and textures, converted, and since 2026-10-20 Skyrim's Falmer sounds
    inside the game's own voice banks, rebuilt. It's a **private install**: don't upload or share it (Nexus
    included). A public release would need a body and sounds made from your own or licensed assets, run through the
    same pipeline.
- **niftools** (blender_niftools_addon) for NIF import.
- Built on our earlier notes:
  - [Goblins of War](goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md) for the gamedb format, AttrHash, the
    sort rule and tribe/role wiring;
  - [offline mode and local Garrison](offline-mode-and-local-garrison.md). **Every test here ran with that DLL
    installed**, so the game never talked to WB. Its local Garrison is where the Falmer Garrison problem showed
    up, and where the fix was confirmed (store, list and deploy a Falmer captain).

## Setup
- Shadow of War Steam build 3095001 with the offline-mode DLL; Goblins of War installed (the Falmer build runs
  after it on the same gamedb).
- **Play the modded game offline**, as in the Goblins of War note. Keep the offline-mode DLL installed while the
  Falmer archive is in `default.archcfg`, and don't use Online Conquest, Online Vendettas, Friend Vendettas or
  WB's own Garrison (the DLL removed). A Falmer captain stored on WB's server, met in someone's vendetta or
  defending an Online Conquest fortress references records their unmodded database doesn't have.
- Skyrim SE (Steam). Its BSA v105 archives were read with our own reader (LZ4 frames): `falmer_male.nif`,
  textures `falmer*.dds`.
- Blender 3.6 + niftools to import the NIF into a `.blend` (68-bone armature). Blender 4.2 headless runs the
  conform script.
- A single-player trainer (invisibility, one-hit kills, time advance), offline like every test here, was used
  only to find and kill test captains quickly. No currency.

## Route and why
- **New tribe in gamedb** (as in Goblins of War), not a DLL. The tribe's roles carry the body/head items that swap
  the orc's look, the way stock `Role_Infested` does.
- **Swap the whole body through a body-replacement slot**, rather than editing orc meshes. The stock game already
  replaces entire bodies this way (the Infested, Machine and Flint bodies...).
- Ologs can roll Falmer roles too. They have no Falmer body picker, so they keep their own body with the gear
  emptied ("naked olog"). The user kept this on purpose.

## How the game works (what we had to learn)
**Appearance pipeline (gamedb):**
- Role → item list → `Inventory/Items` → `ItemBuilder` → `ArmorData`. ArmorData `2FA68885` = equipment slot:
  0 helmet/hair, 1 shoulders, 2 chest, 3 arms, 4 pants, 5 legs, **10 body replacement**, **11 head replacement**.
  Stock `IT_empty_*` items blank slots 0–5.
- ArmorData has a list of **model pickers**: (BodyType, SimpleModelPiece). BodyType 2 = slim, 4 = stocky,
  3 = buff. **Body type is chosen per class, not per tribe**, so every tribe needs all three pieces. With no
  picker for a body type, nothing is drawn (an invisible captain).
- SimpleModelPiece → `Model` (path to the piece's `.skel`; the `.mesh`/`.anix` share its base name) + MaterialSet
  (`.mat` paths) + geometry bundle. The ArmorData has the materials bundle.
- **Corpses and the Garrison depend on the body item being a stock record.** `Faction/Global` keeps a ModelFixUp
  list (slot, pieces → item; e.g. the Infested pieces → `Infested_Body`). A **cloned** body item chain
  (IT/IB/AD clones of Infested_Body, even with its own FixUp entry) makes the body piece vanish the moment the
  character dies, and makes the Garrison refuse the captain ("You cannot send this Follower to the Garrison"; the
  `ReassignmentOrders_GUID` / `HasNPCGUID` check fails). **Putting our pickers and materials on the stock
  `AD_Infested_Body`, pointing the stock FixUp entry at our pieces, and giving the roles the stock
  `Infested_Body` item fixes both.** Side effect: any stock Infested captain would look Falmer too (none spawned
  in the user's game).

**Mesh files (MMSH v0x11):**
- Header: per-part tables (vertex bytes, index bytes, palette sizes), a bone table (world bind pose), and **a
  40-byte record per part**: `vertexCount, 0, indexCount, 0, paletteCount, f32, f32, materialIndex`. **The counts
  must match the data**: the game sizes the vertex streams from them.
- Per part: positions (16 bytes: f16 xyz + w, 4 weights, 4 palette indices), then attributes:
  - stride 48: `u16x2 uv0, u16x2 paint uv1, f32 normal/tangent/bitangent, u8 flags[4]`;
  - stride 52 (stocky/buff LOD0): **`f32x2 uv0`**, then u16x2 uv1, frame, flags;
  - stride 44: thin overlay shells (scar/paint/far LOD) with their own materials.
- Each piece has its own `.skel`. Palette indices point into that skeleton's bone list.
- **How uv0 is read depends on the template part.** On base orc body (body001) parts the game reads u16 uv0 as
  **2 × stored**. On the Infested body parts it reads them **as stored** (the f32 stride-52 UV = actual on both).
  Find out with a checker texture before trusting a template.
- The last 4 attribute bytes are flags (byte 3 = body-region bits). On our parts `255,255,255,0` everywhere
  looked right; copying the Infested template's region flags streaked the torso. The paint UV (uv1) is one
  constant: an unpainted spot of the template.

**Textures and bundles:**
- `.tex` = `TEXR` header + DDS. The header names `<path>.tex0`, a companion holding the **top 3 mips**
  (normally in `highmip.arch06`). Without it, only the blurry low mips ever show. Ship it loose next to the `.tex`.
- Bundles: `.bndl` (load list + type) + `.embb` (data). A bundle's size must fit its type budget (`Flair_1MB`,
  `Flair_2MB`, ...). The stock Infested geometry bundles are ~1.2 MB under Flair_1MB; ours were ~1.35 MB, so we
  used Flair_2MB.
- **File names must be unique.** While a bundle streams in, a same-named stock file (e.g. `orc_body001_d.tex`) is
  drawn on your UVs. We renamed everything `orc_*` → `fal_*` (same length, internal paths patched).
- Our own `.arch06` with loose files + bundles, added to `x64\default.archcfg` after Goblins of War.

**Tribe behaviour (gamedb):**
- Roles: 80 clones of stock roles, `Marker_Falmer` + `Marker_Deranged`, Act 2 gate, forced personality cycling
  through the non-verbal `Damaged8xx` Deranged voices (not the undead ones: undead block Dominate).
- **No comebacks:** a `Marker_Falmer` rule with chance 0, first in all 14 `Faction/Resurrection/Chance` lists.
- Tribe display name through the strdb string tables (all 28 languages).

**Captain body, second version (2026-10-19/20):**
- The final captain body sits on the base orc **`body001`** template (Falmer `_d` 2048×1024, own `_s`), still
  wired through the stock `Infested_Body` item and FixUp entry so corpses persist.
- **Neck:** stock body001 skins the neck (y ≈ 54–72) to **`Spine4_joint`** at 0.8–1.0, the bone that carries most
  of the neck bend; the head and helmet follow `Neck` → `Head`. A conformed mesh that leaves the throat on
  `Upper_Torso` stretches the strip under the jaw into a long dark sheet whenever the head looks up. Fix: move the
  throat's `Upper_Torso` weight to `Spine4_joint` with a ramp (none at y 50, full from y 57, fading out sideways).
- **Helper bones:** some orc gear `.skel`s carry helpers (`L_Thigh`/`R_Thigh`) that only that gear's own `.anix`
  drives. Gear conformed onto those bones and then shown without that anix collapses to the origin (a black slab
  from the waist to the ground). Keep conformed vertices on the main skeleton bones (`L_Legu`, `Pelvis`).
- **Separate gear never stays on a body-replacement corpse.** A dead body-replacement captain keeps only slot 10.
  Stock item records, ArmorData break values and extra FixUp entries for gear slots all failed (the FixUp
  attempt also broke the Garrison). Baking armour into the body mesh keeps it on the corpse.
- Stock orc chest pieces with high collars or scarves are shaped for the thick orc neck; on the slimmer Falmer the
  collar floats. Cosmetic.

**Titles = roles (2026-10-20):**
- A captain's epithet ("the Poet") is the role's string key (role attr `0x1D4D2940`, e.g. `Orc_Title_Poet`, text
  in strdb). A new title = a clone of an already Falmer-adapted role with a new key + strdb text; only
  Falmer-tribe roles carry it, so only Falmer bodies roll it. Listed wherever the stock base role is listed.
- The game avoids duplicate epithets among living captains. A test that made every Falmer slot one of five
  titles starved Falmer generation (once all five existed, other tribes filled the slots).
- **Role gear vs the gear roll:** a role item with item replace priority 2 (attrs `0x8A4035A9` and `0xB2EDA81E`;
  the value on stock armour such as the Torturer chest) is swapped out by the captain gear roll. Stock
  `*_DoNotRemove` items use 10, and that survives the roll. (`Infested_Body` uses 50 and `*_Reference` items 100.)

**Wild Falmer: grunts and prisoners (2026-10-20):**
- Ambient gang data: `AI/SpawnAmbient/AITypes` (`GangType_*`, `Enemy_*`, `Owner_*`) → entry structs →
  `AI/Templates` → `Character/Models` (body model, skeleton, `.bvr` behaviour graph, combat tree, AI type, anim and
  sound set names). Placement (`Locations`/`Areas`) is named anchors; the spots themselves are map data.
- **Appending an entry to a gang type's template list did nothing** (ghûl nests and orc field gangs never picked
  it). **Pointing a template at a new `Character.Models` worked** (a diagnostic turned every templated Berserker
  into a Falmer).
- What works for a mix: each grunt class model (`Model.SimpleModel:Orc_{Infantry,Defender,Berserker,Spearman,
  Archer}`) lists body entries {piece, body type, weight, head list}; **appended Falmer entries are picked**. The
  class keeps its AI, moves and gear. Repeating the orc entries changes the share (9 orc : 3 Falmer ≈ 1 in 4).
- **Grunt bodies load only through their head's bundle.** Stock grunt and creature body pieces have no bundle
  (resident). A piece's own bundle (`ArmorDataDynamicBundle`) is only loaded by the armour system, so our grunt
  bodies were visible only when a Falmer captain had loaded them. Grunt heads load through the loader group
  `DynamicResource.DynamicHeads:NPCHead`. Fix: an empty head (stock `Empty_Slot`, which draws `Smp_Empty_Set`)
  whose bundle definition is a clone of a stock **`_G` head**'s (`Orc_Buff_Head01_G`: group NPCHead, type
  **`Cha_Head_G`**, 9 MB slots), holding all three body sizes' geometry + the skin textures (5.8 MB) in **one**
  bundle shared by every Falmer grunt.
- **Prisoners:** the `Orc_Prisoner` template → a `Falmer_Prisoner` character model with the Falmer bodies. The
  prisoner gang types also hand out orc look items (attrs `0xC0C196CF` / `0xD6E6BEC9`): `orc_sauron_brand` (head
  brand), `Slave_BodyPaint` / `Slave_HeadPaint` (overlays in orc UV layout → patchy, orc-green skin on the
  Falmer), `IT_Orc_Body_LOD` / `IT_Orc_Body_Slave_LOD` (orc bodies for the distance LOD → "orcs from afar").
  Strip those five; keep the gameplay tags (`Resistance_Prisoner_Unarmed`, `I_Am_SlOrc`).

**Audio (2026-10-20):**
- Voices are Wwise SoundBanks (version 118) with **embedded** Vorbis WEMs (48 kHz mono, plugin `0x00040001`,
  held in memory). Chunks: BKHD, DIDX (id, offset, size; 16-byte aligned), DATA, HIRC. A HIRC Sound object
  (type 2) holds `pluginID, streamType, sourceID, inMemoryMediaSize, bits`.
- Of the non-verbal "Damaged8xx" captain voices only **Damaged813** has its own combat banks
  (`sound\vx_orc{melee,meleehvy,pain,run,taunt}damaged813.bnk`, loose files listed by small `Sound_5` bundles).
  Every non-verbal voice also has encounter lines in the per-language presentation archives (one bank per
  `.embb`, type `Presentation`; Oodle-compressed, so extract with QuickBMS).
- **No Wwise authoring tool is needed:** the runtime also plays **PCM** WEMs. Per media, write a RIFF/WAVE with a
  24-byte `fmt ` (`0xFFFE`, 16-bit, the original Wwise channel config `0x00004101` = mono/front centre) + `data`,
  re-lay out DIDX/DATA, and set each Sound's plugin to `0x00010001` and its in-memory size. Then update the size in
  the `.bndl` that lists the bank. PCM banks are ~10–25× larger. Check the bundle type budgets: Sound_5 = 5 MB,
  Presentation = 10 MB.
- Skyrim SE's `sound\fx\npc\falmer\` WAVs (PCM 16-bit mono 32/44.1 kHz; aggrowarning, attack, attackpower,
  injured, death, idle) resample cleanly to 48 kHz. All Falmer roles were given the Damaged813 voice; stock orcs
  rolling that voice sound Falmer too. Wild grunts keep orc vocals (they share the orc class character).

**Skyrim armour on human skeletons (built, not shipped):**
- niftools imports human-armour bones as `NPC Calf [Clf].L`; normalise to `NPC L Calf` to reuse a Falmer bone map.
  Armour NIFs only hold the bones they skin to; fill missing joints (neck, head, toes) from Skyrim's
  `actors\character\character assets\skeleton.nif`, which imports as empties at the same scale.
- Dragonborn chitin light "cuirass" is a full bodysuit. On a chest slot it needs leg and forearm bones added to the
  palette (the chest `.skel` holds all 77 orc bones), or the legs ride on the pelvis.

## Build steps
1. **Extract** the Falmer NIF + DDS from Skyrim's BSAs; import the NIF into Blender (niftools).
2. **Templates:** extract the stock Infested body pieces (`orc_{slim,stk,buff}_infested_body.mesh/.skel/.anix`)
   from their bundles. Parts holding the full body: slim 4–6, stocky 8–10, buff 0–2. The rest is a worm-growth
   overlay and far shells.
3. **Conform** (Blender script, per body type): map Falmer bones to orc bones (pelvis/spine/neck/head, clavicle →
   shoulder, arms, fingers, legs). Give each mapped bone a segment transform: rotate the Falmer bone vector onto
   the orc one, stretch it to the orc length, keep the Falmer thickness. Blend vertices with their Falmer weights,
   re-skin to the template part's own bone palette, write UVs for that template's convention, and compute
   tangents. Write the result into the body parts, then collapse every other part (indices → 0).
4. Set the vertex flags to `255,255,255,0`. Copy the Infested `.skel`/`.anix`, re-pointing the anix path inside
   the skel to your file (pad with zeros to keep the length).
5. **Textures:** Falmer DDS → `.tex` (copy a stock header layout) + `.tex0` (top 3 mips).
6. **Pack:** rename to unique names, build the geometry bundles (Flair_2MB) and the materials bundle, write the
   `.arch06`, add it to archcfg.
7. **gamedb** (after Goblins of War): Models = clones of `Smp_Orc_*_Infested_Body` (our skel path; the Infested
   MaterialSet with its two body mats → ours); pieces + bundle definitions; stock `AD_Infested_Body` → our pickers
   + materials bundle; stock FixUp Infested entry → our pieces; head item = a head-replacement (slot 11) clone with
   an empty piece (the Falmer mesh has its own head); tribe, roles, resurrection rule; strings.
8. Test at a raised role weight (roles listed N times) so Falmer spawn often, then drop to 1 (or the rate you want;
   3 felt right in play).
9. **Titles:** clone Falmer roles with new epithet keys + strdb text (see Titles). Give title gear priority 10.
10. **Wild grunts:** per body size, an `Empty_Slot` head clone; one bundle with all sizes' geometry + skin mats,
    defined as a clone of the `Orc_Buff_Head01_G` bundle def (NPCHead, Cha_Head_G); append Falmer body entries to
    each grunt class `SimpleModel` (repeat the orc entries to set the share).
11. **Prisoners:** `Orc_Prisoner` template → a Falmer character model on the same entries; strip the five orc look
    items from the six prisoner gang types.
12. **Audio:** extract the voice's banks, rebuild them with PCM media from your own Skyrim's WAVs, put the banks +
    updated `.bndl`s (and the presentation `.embb`/`.bndl` pairs) in your private mod archive (never shared: it
    holds Skyrim's sounds and the game's own banks), and set every Falmer role's forced personality to that voice.
    Mount order matters: the mod archive goes at the bottom of `default.archcfg`.

## Verification
- In game (user, screenshots reviewed every round): the Falmer body and head with correct skin on slim and stocky
  close up and at range; Dominate, Recruit, Shame and fight-to-the-death; dead Falmer stay dead. Corpses persist
  after player kills, a Brutalize, two pit fights, and a save reload. A Falmer captain went into the local Garrison
  and deployed back as a captain.
- 2026-10-16 to 10-20 (user, screenshots reviewed): neck bends without stretching on a bodyguard head-tilt; titled
  Falmer (e.g. "the Skulker") dominated, garrisoned, deployed and garrisoned again; Falmer grunts of every class and
  size visible in field groups and outposts, also at range, with ordinary grunts loading normally; Falmer prisoners
  visible up close with clean skin, dominate/drain working; a new captain playing the Skyrim Falmer sounds in an
  encounter and in combat, then dominated and garrisoned.
- Not verified: every finisher type (sever finishers such as Cleave); performance with many Falmer on screen; a
  second PC; other game languages (only the English presentation lines were replaced).

## Gotchas
1. **Sheared, scrambled skin ("chrome" chevrons).** **Cause:** the per-part header records kept the template's
   vertex counts, so the game read the attribute stream at the wrong offsets. **Fix:** rewrite the records from the
   real data on every save.
2. **Stocky/buff untextured up close, fine at range.** **Cause:** stride-52 LOD0 parts store uv0 as f32. **Fix:**
   write f32 there.
3. **Blurry, blotchy skin.** **Cause:** no `.tex0`, so only low mips. **Fix:** ship the 3-mip `.tex0`.
4. **Stock orc patterns flicker on the new body while loading.** **Cause:** same-named files. **Fix:** unique names.
5. **A beige panel / streaks / magnified texture.** **Cause:** the wrong uv0 scale for the template part. **Fix:**
   use a checker texture to find the convention (2 × stored on body001 parts, as stored on Infested parts).
6. **The body vanishes the instant the captain dies (head and gear stay), and the Garrison refuses the captain.**
   **Cause:** the cloned body item chain. **Fix:** put the pieces on the stock `Infested_Body` item and its FixUp
   entry (see How the game works). Old saves heal themselves: captains holding the stock item pick up the new body
   when the game refreshes them.
   - **2026-10-20 correction:** the body-item fix is right for corpses, but the Garrison refusals that came and went
     afterwards (blamed in turn on body art, gear, weapons and a roaming-captains plugin) were **duplicate offline
     NPC ids**: `HasNPCGUID == False` = the captain's id is shared with another captain. See the
     [offline-mode note](offline-mode-and-local-garrison.md), Gotcha 11.
7. **An invisible captain.** **Cause:** no picker for its body type, while the head and gear empties still apply.
   **Fix:** build all three body types.
8. **The orc head still shows.** **Cause:** `IT_empty_head_NoHair` only blanks helmet/hair (slot 0). **Fix:** a
   slot-11 head-replacement item.
9. **Captains generated before a build keep the old look.** **Cause:** items are stored per captain at creation.
   **Fix:** test on newly generated captains.

10. **A black chin-to-chest sheet when the head tilts up.** **Cause:** throat on `Upper_Torso`, none on
    `Spine4_joint`. **Fix:** ramp the throat weight onto `Spine4_joint` like stock body001.
11. **A black slab from the waist to the ground.** **Cause:** conformed vertices on gear-only helper bones
    (`L_/R_Thigh`). **Fix:** keep them on main bones.
12. **Title gear (or any role armour) replaced by random orc gear.** **Cause:** item replace priority 2. **Fix:**
    priority 10 (both attrs), like the stock `*_DoNotRemove` items.
13. **Nothing happens after appending a template entry to a gang type** (no Falmer at ghûl nests or in orc gangs).
    **Fix:** add the bodies to the grunt class `SimpleModel` entries, or repoint a template.
14. **Wild grunt bodies invisible (only their gear floats), or visible only for the body size Falmer captains
    use.** **Cause:** grunts never load a piece's ArmorData bundle. **Fix:** load the body through the head's bundle
    in the `NPCHead` group (see Wild Falmer).
15. **Far fewer grunts, many unloaded or invisible, after putting big bundles in the head loader.** **Cause:**
    six 4–7 MB bundles under the non-head type `Cha_10MB`. **Fix:** a real head pool type (`Cha_Head_G`) and one
    shared bundle.
16. **A 7 MB second head bundle (baked-armour prisoner body) stayed invisible** even under `Cha_Head_G`. Not solved;
    the prisoners use the normal body from the shared bundle.
17. **Prisoners look like orcs at range and patchy/orc-green up close, with a head brand.** **Cause:** the
    prisoner gang types' look items. **Fix:** strip them (see Wild Falmer).
18. **A build tree suddenly packs extra files and folders.** **Cause:** the agent's shell working directory sat
    inside the archive source tree, and the agent harness created its own session folder there. **Fix:** never
    leave the shell's cwd inside a build tree; re-pack and compare file counts before installing.
19. **A test change "fixes" a random-looking bug.** The Garrison refusals stopped after removing a plugin, which
    was only a new launch with fresh ids. Retest on a captain created after the change, and when it recurs,
    look for state that differs per captain (ids, stored items).

## Open questions
- Skyrim animations for wild Falmer: SoW animations are `.anix` (codec `SV01SQ03`), not Havok; a writer and
  behaviour graph would be needed. Dropped for now.
- Wild Falmer grunt vocals: they share the orc class character, so a separate voice needs its own class models.
- Falmer gear that stays on corpses: only baking it into the body worked; a baked body for grunts would need a
  second head-pool bundle that actually loads (Gotcha 16).
- Presentation (encounter) lines for languages other than English.
