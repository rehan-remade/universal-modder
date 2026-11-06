---
kind: game
title: "New selectable suits (one with cloth-simulated hair and its head on every disguise) and a replacement default pistol from custom meshes (SMF, rpkg PRIM rebuild, binary PRIM edits)"
game: "HITMAN World of Assassination"
games_also: []
game_version: "Steam PC, HITMAN3.exe from the 2026-08-27 patch (app 1659040)"
platform: windows
engine: unknown
route: data
tools: ["Simple Mod Framework 2.33.42", "rpkg-cli 2.34.0", "HMTextureTools (bundled with SMF)", "HMLanguageTools (bundled with SMF)", "GlacierKit 1.12.15", "Peacock 8.9.1", "Blender 5.2", "io_scene_glacier 0.7.2 (reference only)", "fal (trellis-2, hi3d multi-view)", "Python 3 + numpy (own PRIM/cloth editor)", "uv", "um win", "um backup"]
anti_cheat: "none in offline play; tested only under Peacock (offline server)"
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: ["@skurtyyskirts"]
date: 2026-10-22
links: ["https://github.com/atampy25/simple-mod-framework", "https://github.com/glacier-modding/RPKG-Tool", "https://github.com/atampy25/glacierkit", "https://github.com/thepeacockproject/Peacock", "https://github.com/glacier-modding/io_scene_glacier"]
tags: ["glacier-2", "smf", "quickentity", "prim", "rpkg", "textures", "materials", "outfit", "weapons", "peacock", "cloth", "hair", "colliders", "disguise", "head-swap", "retarget", "gpu-hang", "tdr"]
---

# New selectable suits (one with cloth hair and its head on every disguise) and a replacement default pistol

An SMF content mod for HITMAN World of Assassination adds a new selectable female character suit and replaces
the default concealed pistol (the ICA19) with a custom model. The suit appears in planning with its own image,
renders in missions with its head, hair and clothes, and keeps IOI's facial rig. The pistol equips, aims and fires,
and shows its own name, planning image and HUD icon. Both were checked in game under Peacock (Paris, The
Showstopper). Most of the work was making rpkg-rebuilt PRIMs, textures and materials stop crashing or rendering
black. This note is the list of repairs.

A second, later suit (2026-10-22) is **not working yet**: a film-inspired female agent look with long straight black
hair and a blunt fringe on IOI's own cloth solver and an open black trench coat, plus a companion mod that puts
that suit's head and hair onto 47's head meshes so they show in every disguise. It builds, deploys and passes every
offline check, but it hangs the GPU 15-30 s into a mission. Two fixes (collider clearance, then cloth counts inside
IOI's limits) were tried in game and both still hung; the cause is not found. The sections marked **(second
suit)** cover it: the decoded cloth data, outfit cloth roots and colliders, the head retarget onto disguises, and
the crash hunt.

## Setup
- HITMAN WoA, Steam, Windows 11, the 2026-08-27 patch. **SMF 2.33.42** (older SMF says "Unknown game version"),
  **Peacock 8.9.1**, **rpkg-cli 2.34.0**, HMTextureTools from SMF, GlacierKit 1.12.15, Blender 5.2.
- Peacock reads SMF's `deploySummary.json` only at startup: deploy, restart Peacock, then launch.
- **Offline only.** Everything here was tested under Peacock and never against IOI's servers, which hold the
  online profile, inventory and progression. Play the modded install under Peacock only, with `leaderboards=false`
  in Peacock's `options.ini` (it defaults to `true`, and modded runs don't belong on Peacock's shared leaderboards;
  the load order below includes a gameplay mod, RealisticAI).
- **(second suit)** Same install and tool versions. SMF load order at the end: `Atampy26.RealisticAI`, the pistol,
  the first suit, the second suit, the disguise-head mod. HMLanguageTools.exe is the copy bundled with SMF 2.33.42.
- **Deploy wrapper (the project's own Python, not published):** refuse to run while `HITMAN3.exe` is up; copy each
  mod folder plus its game-derived files (a JSON map of `content/chunk0/<hash>.<TYPE>` -> a file outside the repo,
  never published: they are IOI's files, edited or as-is) into SMF's `Mods`; run
  `Deploy.exe --useConsoleLogging --doNotPause` with stdin from an empty file and stdout/stderr to a log file
  (Gotcha 19); then restart Peacock: kill only Peacock's own `node.exe` / `PeacockPatcher.exe` by PID and start
  `nodedist\node.exe chunk0.js` and `PeacockPatcher.exe` from the Peacock folder.
- **Backups before every deploy** (`~/.universal-modder/backups/hitman3-runtime-*`): SMF `config.json`,
  `Runtime\packagedefinition.txt`, `Runtime\chunk0patch300.rpkg` (SMF's generated package) and a zip of Peacock's
  `userdata`. Restoring those three files and restarting Peacock rolls a deploy back.
- **Watching a test run:** launch with `steam://rungameid/1659040`, drive the menus with `um win drive` (it takes
  over the keyboard: ask the human first) and look with `um win shot <file> --scale 0.33` (2560x1440 window; Page
  Down opens Destinations). A PowerShell check reads `Get-WinEvent` System `nvlddmkm` (153 = TDR, a GPU reset),
  Application 1000 for `hitman3`, and the newest Peacock log (HeroSpawn, ContractStart, "Mission started", and the
  `SaveAndSynchronizeEvents4` heartbeat).

## Route and why
`data` through SMF: `.entity.json` / `.entity.patch.json` (QuickEntity), `.repository.json`,
`.unlockables.json`, `.JSON.patch.json` (ORES), and raw `<hash>.<TYPE>` + `.meta` resources for meshes,
textures and materials. No code. Meshes go: model → Blender → GLB with the vanilla PRIM's object names →
`rpkg-cli -rebuild_prim_in` → our repair pass → a new hash, with the meta retargeted to the new material.

**(second suit)** Still `data`, but no rpkg rebuild for anything with cloth or skin that must stay IOI's: the hair,
the fringe and the disguise heads are vanilla PRIMs edited in binary by our own Python (move vertices, append
meshes, rewrite skin and cloth tables), so IOI's vertex data, UVs, normals, tables and LODs stay byte-identical
except where we changed them. An rpkg round trip requantises every mesh and copies the container's cloth rows
(Gotcha 9). Clothes are vanilla PRIM bytes under our hashes with metas pointing at our MATIs.

## How the game works (what we had to learn)
### A new suit
- A charset (Actor, HeroA, Nude; only HeroA filled), plus a `ZGlobalOutfitKit` patched into globaldata, plus
  repository + unlockables entries, plus an ORES patch adding the token to `PACKAGE_STARTING_PACKAGE`. The suit
  shows in planning with its image (`images/unlockables_override/...jpg`).
- Outfit root: a hero aspect dummy (linked proxy + cloth character + hero idle network aspect) with
  `m_pBonesAndCollisionResource` set to the female rig. Body parts are plain `zbodypartentity` entries pointing
  at PRIMs.
- NPC part-library templates under a hero root crash at mission load. An NPC outfit TEMP as the charset target
  falls back to 47's suit. NPC disguises keep 47's head, so only the suit itself shows the new character.
- Building on IOI's female parts (`fem_reg` rig) instead of one fused generated mesh keeps IOI's facial rig
  (103 bones), LODs and skin shaders. The female body parts share one material atlas (`fem_reg_body.mi`), and
  vanilla head neck rings match vanilla body parts, so no seam work is needed.
- Hair colour on IOI hair materials lives in `ConstantColorRGB_02_Value`.

### A replacement default pistol
- The default concealed pistol is the ICA19 (`FIREARMS_HERO_PISTOL_TACTICAL_ICA_19`), not the Silverballer.
- Clone the ICA19 repository entry under a new GUID (same stats), redirect the starting token's `RepositoryId`,
  and override Name/Description with localisation keys.
- New parts: append `zbodypartsetupentity` + `zbodypartentity` to the model template's part collections and
  select them with `ModelBodyPartSelections`.
- **HUD icon:** `HudIcon` is the runtime ID of a GFXI, which is a plain DDS (808x328 DXT5, 1 mip) at
  `[assembly:/_pro/ui/common/icons_inventoryitems/item_left_<item GUID>_0.png].pc_gfx`. Keep the vanilla
  128-byte header and splice new DXT5 data after it.
- Freeform Training issues its own vanilla ICA19, so test a token-redirected pistol in a mission with planning.

### PRIM layout facts
- **Linked (weapon) PRIMs** keep the part's bone index in every vertex's position w (pos_scale.w 32767,
  pos_bias.w 0). On the ICA19 the parts are frame 1, mag 2, hammer 3, slide 4, trigger 5.
- **Linked collision (H3):** `u16 size, u16 1, u16 chunks rounded up to 4, u16 16, u32 tris, u32 0`, then
  `u16 chunks, u16 32` and one 6-byte box per 32 triangles, rounded to the sub-mesh bounds. Weighted PRIMs use
  the older layout without the 16-byte header, and also carry per-bone vertex lists (bone accel).
- A weighted PRIM's per-bone triangle list has a **u16 count**. 40k triangles on one bone overflow it, and
  about 20k fits.
- **Cloth:** IOI hair PRIMs carry per-vertex cloth rows (`cloth_id` at mesh+96, `cloth_offset` at
  sub-mesh+68, 20 bytes per vertex: neighbour indices plus constraints, 0xFF.. = pinned).
- **Texture tonymeta** (16 bytes): byte 0 is 0 for colour and 1 for normal. Byte 8 is the format: 0x5A BC7,
  0x55 BC5, 0x49 BC1. Bytes 11 and 12 are the size code: 2=512, 3=1024, 4=2048, 5=4096.
- **Weighted PRIM vertex data (second suit):** four blocks, each covering every vertex before the next one starts
  (RPKG-Tool 2.34.0's `prim_weighted_sub_mesh` reads them in this order): all positions (12 bytes per vertex
  high-res, 8 quantised), then all skin records (12 bytes: six influences, weights summing to 255), then all
  normal/tangent/binormal + UV records (`12 + 4 x uv_count` bytes), then all colours (4 bytes). A writer that
  interleaves them per vertex corrupts the PRIM. A mesh's PrimObject min/max (mesh+20/+32) and its sub-mesh's
  (sub+20/+32) are both the exact vertex extents; `pos_scale` = half extent, `pos_bias` = centre (w lanes 0.5 on
  weighted meshes). IOI writes its blocks in a fixed order with no unreferenced bytes, and every constant-colour
  mesh still carries the colour stream (5,821 of 6,092 vanilla ones filled with 0xFF). A re-serialiser following
  those rules reproduced all 1,227 vanilla weighted PRIMs byte for byte.

### Cloth in PRIMs (second suit; decoded from the bytes, channel meanings partly inferred)
- A cloth PRIM carries a coarse **sim mesh** object (16-2,058 particles in vanilla; our hair 174) that the solver
  moves. It gets cloth id `0x80 | group` and lodmask 0xFF; the render meshes it drives carry the group id (1).
- Each render vertex has a cloth row: 4 particle indices (-1 = unbound, the vertex just follows its skin), 4 u16
  bilinear weights, and two u16 values: t0 (the sim blend, from vertex colour B) and t1 (from colour G, scaled by
  `t1_min`). Rows sit at the sub-mesh's `cloth_offset` (sub-mesh+68); `cloth_id` is the u32 at mesh+96.
- Particles have an 8-slot neighbour table (regenerating it from the quads gave IOI's bytes exactly) and pins
  painted in the sim mesh's colours (blue read as "free amount", inferred from height ramps). Each sim has a
  parameter block (rate in Hz, damping, gravity, stiffness); the word meanings are guesses.
- IOI paints cloth intent into render vertex colours even on hairs it never simulated: `hair_l_midpart` already
  ramps colour B from 0 on the crown to 1 below z 1.45, like `hair_long_01`.
- Most hairs simulate LOD0 only (`hair_long_01` binds LOD0); Spider Lily's hair and fringe bind every LOD. No
  physics at all on `hair_long_dynamics` (despite the name), `hair_l_midpart`, `fringe_hairstyle`, the bob/fringe
  styles or crowd hair.
- **Vanilla envelope** (all 474 cloth PRIMs): objects <= 38, sims <= 4, particles <= 2,058, render meshes with
  cloth rows <= 12 per PRIM and <= 6 per cloth group, <= 3 per (group, LOD) (430 files have 1), bound vertices per
  group <= 18,479 (next 12,573, p99 7,706).

### Outfit cloth roots and colliders (second suit)
- The two Knight HeroA outfits (00F6518ED0D7BF28, 00B5DA9238EFBDC3) are the only female playable-style outfits:
  same `fem_reg` rig 0097F69B78D93F12, simulated hair, IOI `outfit_base` cloth values on the root (damping 0.5,
  60 Hz, 2 iterations, shear/bend 0.5, bend type Stick, per-vertex stiffness/damping off, skinning normal
  constraints off, global colliders off, wind 0.1), and root `m_LocalColliders` -> a plain composite
  `ClothCollidersHeroFemale` (18 `zclothsphere` + `zboneattachaspect` spheres, 4 sphere chains, 1 group).
- The first suit's root was copied from 47's sneaking suit (damping 1, 90 Hz, stiffness 1, gravity -13, per-vertex
  on, **no colliders**), which is why its braid went through the body.
- Collider entities can be copied inline under our aspect-dummy root with fresh ids, `m_linkedEntity` and
  `m_eidParent` pointing at our root. Don't reference part-library templates (they crash under a hero root).
  Other sets: five ellipsoids (head, neck, both clavicles, spine2) inside the `hair_l_ponytail_loose_braid`
  part-library template, and presets under `cloth_templates/` (`Fem_Heels_LongDress_Collider` for `hair_long_01`).
- Hair material `base_hair`: shader `basic_hair_pixeldepthoffset`, opaque, two-sided, a 2048 white strand atlas
  whose alpha is coverage, tinted by `ConstantColorRGB_02`. An outfit can recolour (Spider Lily even re-textures) a
  hair with an override entity on the material. The haircap is a decal: its alpha is how much near-black covers
  the scalp.
- Clothes used: `coat_trench_open` 004BDF9809A07EBF (open, knee length, its own 140-particle sim), top
  `sweater_uneck_pshdslv_tkd` 008EE99AC468ED65, `pants_dress_slim` 00C3943F0711CD44, `belt_thin`
  00428575492577A1, `shoes_boots_military` 00F7132C33A48436, with Hands + Torso_Neck (the vanilla pairing for that
  coat, top and trousers). The `head_of_security` belt sinks into the waistband (trousers show through 49% of it).

### 47's heads under every disguise (second suit)
- `ZHitman5::SetOutfit` swaps the hero outfit. HeroA disguise bodies are all male (`male_reg` / 47's rigs); only the
  Knight's two outfits are female. So "the suit's look in a disguise" means a head on a male body.
- 47's heads are shared PRIMs (counts are reverse dependencies, rpkg `-hash_depends`): `agent47_head` 006AA90A54C589B9
  through the `Head_47` template 00537D16B5CE7286 (1,071 TEMPs), the season 1 `regmale_agent47` head
  001FA83D69D89B24 baked into 765 TEMPs, `agent47_head_neck` 0014C7C6091DC2AD (34), `_neck_s2` 00C0B6C10657825B
  (33), `_se1_unlocks` 00B56DB95950BD5E (39) and the cutscene head 00DF2AB1D3CC2BE0 (2). All live in chunk0 (+
  patches), so an override in a mod's chunk0 content wins. Not covered: the S2 head 002F5293D4F41A8D (chunk9 /
  chunk1patch2, 3 TEMPs) and the VR/legacy heads.
- IOI rigs share bone names: `fem_reg` 235 joints, 47's head rigs 233 (S3, cutscene) or 231 (season 1 family, no
  `fa_teeth_up/dw`); male rigs lack `xtra_phy_breast_l/r`. 47's head bone is 7.6 cm above `fem_reg`'s. A GLB's skin
  joint order equals the PRIM's joint indices. Every neck cut has 37 vertices on LOD0-2 (19 or 17 below). The S3
  heads share Diana's base mesh (LOD1/2 identical vertices, UVs and indices).

## Build steps
1. Export the vanilla PRIMs, materials and textures you build on (rpkg / GlacierKit) to a private folder outside
   the repo.
2. Edit or generate meshes. Name the objects as the vanilla PRIM's, weld before decimating, and keep each linked
   part under the vanilla per-LOD vertex counts.
3. `rpkg-cli -rebuild_prim_in`, then repair every rebuilt PRIM. The repair pass and the TEXT/TEXD builder were
   one-off Python scripts and are not published, so the steps they performed are spelled out here:
   - Linked PRIMs: write each vertex's bone index back into position w with pos_scale.w 32767 and
     pos_bias.w 0 (Gotcha 1, PRIM layout facts).
   - Linked PRIMs: regenerate the collision block in the H3 layout above, one box per 32 triangles over the
     new triangles (Gotcha 2).
   - Hair and other cloth PRIMs: zero `cloth_id` and the sub-mesh `cloth_offset` and drop the cloth rows, unless
     the vanilla topology is kept (Gotcha 9).
   - Characters: copy the container's COLOR_0 into the new vertices (Gotcha 7).
   - Check the vertex budget per linked part and the u16 per-bone triangle count before shipping (Gotcha 10).
4. Build TEXT/TEXD yourself instead of letting SMF convert:
   - Encode the mips with any BC encoder (BC7 colour, BC5 normal, BC1 masks). TEXD holds the full mip chain and
     TEXT a downscaled copy, as in the vanilla pair you start from.
   - Copy the vanilla texture's meta and set the tonymeta format and size code (PRIM layout facts).
   - Set video memory to the sum of the TEXD mips at the format's block size (16 bytes per 4x4 block for BC7/BC5,
     8 for BC1), and TEXD `hash_size` to 0 (Gotchas 4 and 5).
   - Build only MATIs and keep the source's MATT/MATB (Gotcha 6).
5. Write the entity, repository, unlockables and ORES files. Deploy with SMF, restart Peacock, and launch.

### Second suit: cloth hair, clothes, colliders
6. **Hair** (one script, every number in a JSON config):
   - Start from `hair_l_midpart` 00DE4394D8CAABAE (no physics) and append `hair_long_01`'s 174-particle sim mesh as
     object 0 with IOI's colours, head-bone weights and parameter block.
   - Move the free particles along their normals into midpart's lengths (each particle takes the weighted mean
     offset of the render points whose closest quad uses it, smoothed over its neighbours, capped at 40 mm).
     Median render-to-sim distance went 15.9 -> 4.4 mm, as vanilla `hair_long_01` on its own hair.
   - Bind render vertices to the lattice (4 particles, bilinear weights) and fade the blend (t0) to 0 between 25
     and 45 mm from the lattice so no vertex is half-bound.
   - Fringe: Spider Lily's bangs 007C821292C592C2 (cloth, vanilla bytes) with the tips moved down and rebound. Its
     bone rig 005595FB1EBB93B3 lives in chunk13, so it goes in the manifest `dependencies` for SMF to port.
   - Fit to the head: push hair out of the head surface with a smooth field, skip points deeper than 12 mm and on
     ear folds, and weld UV-seam splits first (Gotcha 22).
   - Filler card copies (behind the ears, the nape seam, the temples) close gaps; merge them into each LOD's own
     hair mesh, never as separate objects (Gotcha 17).
   - Our own haircap texture with the decal alpha raised (x3, gamma 0.7), so scalp between strands reads as hair.
   - Gate: fail the build if the PRIM leaves the vanilla envelope above (gate per group <= 6, per group+LOD <= 2,
     per PRIM <= 12, bound per group <= 12,000, particles <= 2,058, objects <= 38), then re-serialise in IOI's
     block order with no dead bytes.
7. **Clothes and root:** vanilla PRIM bytes under our hashes, our MATIs on vanilla MATT/MATB (diffuse/spec/gloss
   recolours, a brass buckle masked from the belt mesh's buckle UV islands); Knight cloth values on the root;
   collider composites inlined (each set switchable); every id derived (entity ids `"feed" + md5(name)[:12]`, GUIDs
   uuid5, resource hashes from a mod path), so a rerun writes identical files.
8. **Dry run before deploy:** assemble the mod into a scratch folder, parse every JSON, check the entity graph is
   closed and every PRIM/MATI/TEXT reference resolves to our files or vanilla (`rpkg-cli -filter <hashes>
   -hash_probe <Runtime>`), and that anything outside chunk0 is in the manifest `dependencies`.

### Second suit: the head on every disguise (a separate mod, loaded after the suit)
9. For each of the six 47 head PRIMs above, build a replacement under the **same hash** from the suit's head, hair
   and fringe (42 objects, 32 once the hair copies are merged; vanilla heads go to 52):
   - **Joints by name**, a missing bone falling back to its nearest ancestor (rig-to-rig table, then rewrite each
     mesh's joint indices).
   - **Placement:** a similarity transform fitted on the two eye bones (scale 1.023-1.026, 1.4 deg head-frame
     rotation; facial bones then land a median 7 mm from 47's).
   - **Neck:** find the lowest open loop on both meshes, pair the two 37-vertex rings 1:1 in angular order (polyline
     snap where counts differ), move the cut onto 47's (0.0 mm on LOD0-2) and fade that move out over 7 cm up the
     neck; blend skin weights to 47's nearest vertex with the same fade; copy his normals on the cut.
   - **Hair:** parts weighted to the head follow the face placement; long lengths weighted to spine/clavicles follow
     47's bind pose; smooth the difference over 5 cm (an unsmoothed first try left a 4-5 cm shelf at the nape);
     push out of the blended head by 2 mm; lift lengths off 47's suit jacket/shirt only where < 15 mm inside and
     > 8.5 cm from the neck axis (the open collar flips inside/outside). LOD0 hair inside the jacket: 284 -> 74 of
     15.6k vertices.
   - **Hair is plain skin on disguises** (cloth stripped): disguise outfits carry no colliders for it.
   - Meta: 47's bone rig plus the suit's head and hair materials. Check every output: indices, weight sums, joints
     below 231/233, material ids, no cloth, bone tables = geometry.

## Verification
- Paris → The Showstopper → Planning showed the suit and the pistol with their images. In the mission, the
  suit rendered and the pistol equipped (`I` inventory, Enter), aimed and fired.
- Crash checks via `Get-WinEvent` (Application 1000). The crashes here were **intermittent**, so run each
  configuration 3+ times and keep a no-mod control. Controls: 3/3 clean.
- Not checked: hit detection on the new character. Weighted PRIMs keep the donor's collision and bone-accel
  data (in bounds, but stale).
- **Second suit, offline:** 183 unit tests on synthetic meshes (no game bytes); the dry run clean; every PRIM
  inside the vanilla envelope; Blender renders through a one-heavy-job-at-a-time gate, including a "red-skin" pass
  (skin and ears painted red, so any red pixel is scalp showing through the hair) from HITMAN's third-person camera
  (~0.9 m behind, 0.35 m above the head); a crude position-based cloth preview (not IOI's solver) showing nothing
  mis-pinned or resting inside the head or torso.
- **Second suit, in game (Dartmoor, starting in the suit):** GPU hang every time: v0.1 at 12:38 (~20 s in), the
  collider fix at 14:24 (~15 s in), the cloth-envelope rebuild at 15:37 (~30 s in). The disguise-head mod was
  deployed for the last two runs, but nobody looked at a disguise; its in-game look is unverified.

## Gotchas
1. **An rpkg-rebuilt *unmodified* weapon magazine crashed the menu.** **Cause:** rpkg 2.34 writes position w
   32767 at scale/bias 0.5, losing the per-vertex bone index on linked PRIMs. **Fix:** restore w (see PRIM
   layout facts).
2. **Crashes from rebuilt meshes with changed triangle counts.** **Cause:** rpkg copies the container's
   collision blocks verbatim. **Fix:** regenerate collision in the layout above. A generator reproduced 21 of 22
   vanilla ICA19 blocks byte for byte.
3. **Intermittent crashes at boot, load or pause (~half the runs) with no custom binaries at all.** **Cause:**
   `ModelBodyPartSelections` selected past the end of part collections, as vanilla ICA19 does for Rails.
   **Fix:** never select past the end; append explicit empty setups (null mesh) at those indices.
4. **Textures stream in wrong or get evicted.** **Cause:** SMF/HMTextureTools declare video memory at the BC1
   rate for BC5/BC7, which is half of what the GPU needs, and SMF caches conversions by the TGA alone (a changed
   `.meta` keeps the stale TEXT/TEXD). **Fix:** build TEXT/TEXD yourself. Video memory = the TEXD mips at the
   format's block size.
5. **The character rendered black with coloured specks.** **Cause:** a TEXD meta with `hash_size` 0x80000000
   (XOR'd). TEXT has that flag, vanilla TEXD does not. **Fix:** TEXD `hash_size` 0.
6. **`rpkg -json_to_material` makes 0-byte MATT/MATB files for new hashes (crash),** or rewrites vanilla ones
   with different bytes (black render). **Fix:** keep the source's MATT/MATB, build only the MATI, ship only
   the MATI.
7. **Arms rendered wrong.** **Cause:** vertex colour matters on characters (the `fem_reg` arms carry white
   COLOR_0). **Fix:** copy the container's COLOR_0.
8. **A character shader (`basic_fabric`) on gun parts crashed.** **Fix:** a textured `basicmaterial` (retarget
   of an ICA19 receiver material) works on linked PRIMs.
9. **Hair glitched: the braid went over the shoulder, and strips hung to the knees.** **Cause:** rpkg keeps the
   container's cloth rows when the vertex order or count changes, so the solver drives the wrong vertices.
   **Fix:** strip the cloth rows (or keep vanilla topology).
10. **Linked parts with more vertices per LOD than the vanilla part crashed 2 of 3 runs.** Cause unknown. **Fix:**
    stay under the vanilla counts (frame ~2019, slide 638, hammer 222, trigger 218, mag 762 at LOD0), and weld
    generated meshes before decimating or the LODs turn spiky.
11. **A replacement hammer swung sideways.** **Cause:** its pivot was 17 mm from the ICA19 hammer bone's.
    **Fix:** join the hammer into the frame and ship a hidden 3-vertex stub for the hammer part.
12. **GLBs from rpkg keep raw Z-up accessor data, but Blender's importer applies different axis fixes** to
    vanilla and re-exported files. **Fix:** edit accessor data directly and write GLBs without a Blender round
    trip.
13. **Dark flecks on the ears, and baked hair on the neck.** **Cause:** masking ears by a z box missed the lobes.
    **Fix:** mask by the rig (`fa_ear_*` weights).
14. **The SDK's `Outfits` mod** was the main suspect in scene-change crashes, and isn't needed for new suits.
    Leave `[outfits]` out of `Retail\mods.ini`.
15. **(second suit) The game freezes ~15-30 s into a mission and closes about a minute later.** The Application log
    shows `hitman3.exe` 0x80000003 (breakpoint) at offset +0x11e9c4d; the System log shows `nvlddmkm` 153 (TDR) one
    to three times before it. **Cause of that signature:** all 40 breakpoint crashes at +0x11e9c4d since 10-05 had
    GPU TDRs 67-78 s earlier, the access-violation crashes had none: it is the engine giving up after a GPU hang.
    Earlier ones came from mesh data that hung the GPU (a bad rpkg bone remap, out-of-range part arrays). **Fix:**
    none yet for this suit (Gotchas 16-17 were not enough). Ruled out offline: indices, skin joints, weight sums,
    bone tables, cloth tables and row weights of all shipped PRIMs; texture video-memory sizes; a bone-rig mismatch
    of the transplanted lattice (it only uses joint 7 = head, the same in every rig); hands and coat PRIMs are
    vanilla bytes. The first suit (no cloth hair) never hung on the same PC and settings. Next probe planned: the
    same build with the hair cloth stripped (bangs and coat kept), then with hair, bangs and coat all removed.
16. **(second suit, hypothesis 1, did not fix it)** Most free hair particles started inside the root's colliders
    (up to 49 mm into the long-hair set's spine2 ellipsoid, 41 mm into the Knight shoulder spheres, plus our own
    bust ellipsoid). IOI's own pairs sit at most ~21-23 mm inside. Measure it by placing the collider entities on
    the bind pose from a rig GLB and testing every sim particle. Changes: long-hair set and bust ellipsoid off, and
    the lattice pushed 8 mm outside the remaining colliders after the head fit. Still hung.
17. **(second suit, hypothesis 2, did not fix it)** The hair's cloth counts were outside every vanilla file: 14
    render meshes with rows in one cloth group (vanilla max 6), 6 per (group, LOD) (max 3), 18,481 bound vertices
    per group (max 18,479). The cause was filler card copies appended as separate bound meshes. Changes: fillers
    merged into each LOD's hair mesh, only LOD0 bound (like `hair_long_01`): 10 objects, 1 bound mesh, 8,596 bound
    vertices. Still hung, 30 s in.
18. **SMF's Deploy.exe hangs at "Localising text".** **Symptom:** `Deploy.log` stops after `Executing command
    "Third-Party\HMLanguageTools" rebuild H3 LOCR ...`; Deploy.exe sits at 0 CPU with ~40 idle `rpkg-cli -i`
    children; HMLanguageTools has already exited (run by hand, the same command finishes in a second). By then
    SMF has deleted `Runtime\chunk0patch300.rpkg`, so the install is half-deployed. **Fix:** kill Deploy.exe by PID
    with its tree (`taskkill /PID <pid> /T /F`) and redeploy at once; never launch the game in between. It was
    intermittent at first (one retry worked), then hung 3+ times in a row the same afternoon, also with Deploy.exe
    started by hand; that run was left unresolved.
19. **Deploy.exe also hangs when its output goes into a console pipe.** **Fix:** start it with stdin from an empty
    file and stdout/stderr redirected to a log file.
20. **An "orange strand" at the back of the hair.** **Cause:** neck skin showing through the seam where
    `hair_l_midpart`'s left and right halves meet at the nape (IOI's hair atlas is neutral grey, at most 9/255
    chroma). **Fix:** two shifted, tucked copies of the seam cards; warm pixels in the HITMAN camera 175 -> 0.
21. **Appending meshes from another PRIM left dead bytes and a missing colour stream.** **Cause:** our first
    append dropped the 4-byte colour stream vanilla always keeps. **Fix:** always write it; re-serialise in IOI's
    block order and gate on overlapping or unreferenced blocks.
22. **The hair fit skipped hair over the middle of the scalp.** **Cause:** game heads split vertices along UV seams
    and one runs down the scalp, so the fit took it for an open edge like the neck. **Fix:** weld seam vertices
    before computing open edges.
23. **(disguise heads) Expected limits:** hats and helmets clip the hair; outfits with their own masked or special
    heads keep them; the female neck base flares to meet a man's collar.
24. **rpkg-cli waits on stdin and some modes are picky about argument order.** **Fix:** always give it stdin from
    an empty file, and pass `-filter <hash,hash,...>` before `-hash_probe <Runtime>` / `-hash_depends <Runtime>`
    (otherwise it treats the hash as the folder to search).

## Assets
- Pistol: hand-modelled in Blender by script from public reference photos, baked high→low (normal, AO, masks)
  into one 2048 atlas, with five named parts at real scale anchored on the trigger centre.
- Suit: IOI `fem_reg` parts (head, arms, gloves, tank top, shorts, belt, legs, boots), morphed and recoloured,
  with a procedural hair cap and braid. Holsters and straps were generated with fal (image edit → trellis-2).
  Trellis-2 GLBs put textures under `EXT_texture_webp`, and their UV v runs the other way from rpkg's.
- The head was morphed toward a multi-view reconstruction (fal `hitem3d` multi-view-to-3d) with MediaPipe
  landmarks, a thin-plate warp and a shrink-wrap, then baked into the head's UVs. The skin PBR stays IOI's;
  only the diffuse is replaced.
- Second suit: the head is a custom head built on IOI's Diana S3 head (same `fem_reg` rig, 4096 skin set), so the
  facial rig and IOI's eyes, teeth, lashes and skin maps stay; body skin (Hands, Torso_Neck) recoloured with a Lab
  shift on the vanilla `fem_reg_body` diffuse to match the head's neck. Hair and clothes are IOI's own parts
  (above). Planning image: a 693x517 three-quarter render, like the first suit's.

## Cost and time
Several sessions over two days for the first suit and pistol. The second suit: one long session (02:45-08:15)
with parallel helper agents (survey, cloth, outfit, head), then two sessions on the crash and the disguise heads;
the last ended on a usage limit mid-diagnosis.

## Open questions
- Regenerating collision and bone-accel tables for weighted (character) PRIMs, so hit detection matches the new
  mesh.
- Why linked parts with more vertices crash, since the vertex budget is a workaround and not an explanation.
- What in the second suit hangs the GPU (Gotcha 15). The no-cloth hair build exists and is the next probe.
- Which cloth parameters win in game: the PRIM's parameter block or the outfit root's values.
- Whether the disguise heads look right in game, and the season 2 / VR heads they don't cover.
