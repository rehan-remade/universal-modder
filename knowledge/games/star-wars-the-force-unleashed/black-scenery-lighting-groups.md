---
kind: game
title: "Fixing solid-black scenery in Star Wars: The Force Unleashed (PC): objects in lighting groups no light reaches"
game: "Star Wars: The Force Unleashed"
games_also: []
game_version: "Ultimate Sith Edition PC 1.2.94564, Steam (SWTFU.exe x86)"
platform: windows
engine: native
route: data
tools: ["REA 6.7.0 + Ghidra 12.1.4", "MSVC 14.44 (dev-only D3D9 tracer and memory bridge plugin)", "Python 3.12"]
anti_cheat: "none (single-player)"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-24
links: ["https://github.com/morluto/rea", "https://github.com/NationalSecurityAgency/ghidra"]
tags: [lighting, spherical-harmonics, level-data, markerset, asset-override, ronin-engine, d3d9]
---

# Fixing solid-black scenery in Star Wars: The Force Unleashed (PC)

> Some level objects render pitch black although their textures are fine. The best-known case is the big canopy pods
> on the Felucia clone battle site (Felucia_Act2_C). The level data puts these objects in lighting groups that no light
> reaches, so the engine lights them with nothing. An override of the level's markerset (level layout XML) that adds
> the right lighting group fixes them: 65 objects on 6 levels. Each fixed level was checked in the running game with
> and without the override, by render-node light counts read from memory and by screenshots.

## Setup
- Steam build 1.2.94564 (Ultimate Sith Edition), Windows 11, 32-bit D3D9 executable.
- A dinput8.dll plugin loader plus a loose-file override plugin that hooks ScumLib `AssetCatalog::LoadRawAssetData`:
  any asset path in the packs can be replaced by a loose file under `DK_Mods\<mod>\<asset path>`. Any equivalent
  loose-file override works; the fix itself is pure data. The loader, the override hook and the Lua bridge are
  written up in the companion note, [Modding surface of SWTFU](ronin-engine-modding-surface.md) (its Build steps).
- Level layout lives in plain-XML `*.markerset.xml` files inside `LevelPacks\<level>_pc.lp`.
- For research and testing: a dev-only plugin with a named-pipe bridge that runs Lua in the game and reads memory, a
  scripted test runner that loads levels and takes screenshots, and a dev-only D3D9 tracer.

## Route and why
- `data`: override the level's markerset XML. It is a data bug, so no engine patch is needed, and the change stays
  scoped to the objects that were proven black.
- Rejected: restoring the missing IBL probe files. Five levels miss `Shared/IBLProbes/<world>.ibl`, but static scenery
  has castsIBL set and never receives IBL. A test probe file loaded fine and changed nothing.
- Rejected: a runtime hook that gives every unlit node ambient light. Some unlit nodes are intentional (silhouettes,
  helpers, objects lit by direct light only), and a blanket hook would change their look.
- Rejected: patching group masks in memory. The engine rebuilds them every frame (gotcha 4).

## How the game works (what we had to learn)
- **Lighting groups.** Every light and every placed object has ATTRIB_GROUP_LIGHTING_GROUPS_RUNTIME / Group_0..Group_31
  in its marker's `mMarkerAttribs`.
  - No attribute means Group_0 only.
  - With the attribute, the object is in exactly the groups set to 1. An empty list means no light at all.
  - Inner actors of a prefab without their own attribute inherit the prefab marker's list. Inner actors with their
    own list keep it.
- **Assignment** (`Light_AssignToNode`, 0xB51350 in 1.2.94564). A light reaches a render node when three tests pass:
  - the channel masks overlap;
  - the group masks overlap (node +0xE0/+0xE4 against light +0x28/+0x2C);
  - the light's range reaches the node's bounds. Directional lights have no range.
- **Two light lists per node.**
  - Lights flagged approximated (`mLightOptions/mApproximated = 1`, flag 0x20 at light +0x24) go into the node's SH
    list: pointers at node +0x20, count byte at +0x5D.
  - All other lights go into the direct list: pointers at node +0x00, count byte at +0x5C.
- **Shading.** Static scenery is shaded from the SH ambient (9 coefficients, pixel shader constant
  `gSHLightingCoefficient`) plus its direct lights. With both lists empty, the object is black except where a spot
  light happens to fall on it.
- **Render nodes.** Slot table at 0x2850C00 (stride 0x100), high-water count at 0x3850C9C. Useful fields:
  - +0x90: world translation, which equals the marker position;
  - +0xEC: flags (0x108 = freed or hidden);
  - +0x138: geometry pointer;
  - +0xE0: groups.
  The lists and groups are filled only when the node is drawn.
- **What the designers got wrong.** Three patterns:
  - the object sits in a group whose only light is a rim spot (the Felucia pods: Group_31);
  - the group list is empty or names a group without lights (the Felucia wrecks);
  - the object's groups hold lights that do not reach its position (the Raxus Prime underground barricades and
    barrels: the Group_0 lights there are out of range).

## Build steps
1. **List candidates statically.** Parse every markerset in a level pack (lights and objects with their group masks)
   and list the objects whose groups share no light. This over-reports, because lights inside prefabs and lightmapped
   meshes are not counted.
2. **Confirm each one live.**
   - Load the level from the front end: `ronin.LoadWorld("<level>")`, with names from `PC_LevelSelectList.txt`.
   - Point a scripted camera at the object: `camera.SetUpScriptCamera(eye, at, 0)`.
   - Read the drawn render nodes at the marker position. nLightsSH + nLightsDirect == 0 is the bug.
   - Look for an identical copy of the asset elsewhere in the level that is lit.
3. **Choose the group.** Read the group masks and assigned lights of lit nodes right next to the object, and add those
   groups. A level's directional fill group lights whole areas.
   - Where the designer kept a rim light on purpose (the pods), add the object's group to the area's ambient fill
     lights instead. That keeps the rim light, and no object gets the same light twice.
4. **Edit the markerset textually.** Keep CRLF and tabs, and insert or extend the marker's `mMarkerAttribs` block.
   Then re-parse the file and assert that only the named markers changed, and only by the added groups.
5. **Install the edited files** as loose overrides. They apply the next time the level loads, also from a save or a
   checkpoint. An edited markerset is still the game's own level data with a few groups added, so a release ships the
   edit itself (marker names and added groups, plus the step 4 script) and builds the files from the player's own
   level packs at install time. The edited XML files themselves are never published.

## Verification
- **Oracle.** For each fixed object, take the maximum nLightsSH + nLightsDirect over its own drawn nodes at the marker.
  - "Own" nodes are filtered by the added group bits, so a lit object at the same spot does not count.
  - With the fix, every object must have at least one light: 27 objects sampled across all 11 rules (one rule per
    fix: the markers it edits and the groups it adds), all lit.
  - With the override disabled, every level with a measurable object must show at least one unlit object: 5 of 6
    levels did.
  - The sixth level (two doubled doors) is proven by an A/B of node data instead: zero-SH draws at the door dropped
    from 3 and 2 to 0.
- **Pods: draw-level proof.** A D3D9 tracer hooked SetPixelShaderConstantF and DrawIndexedPrimitive. It counted draws
  whose shader has `gSHLightingCoefficient` while the uploaded SH is all zero, keyed by the world translation, which
  matches the marker positions. Those draws went from 4-5 per view to 0.
- **Screenshots** before and after: pods, wrecks, the Felucia_Act1 bulb plant, underground barricades and barrels,
  the dropship barricade, the proxy-battle lamp stands, the Death Star crate.
- **Not verified:** areas that were never streamed in during the survey (see Open questions), and other builds than
  Steam 1.2.94564.

## Gotchas
1. **Zero SH almost everywhere, yet the level looks fine.** **Cause:** many levels (TIE Factory, the Felucia_Act1
   grove interior, the Shaak Ti arena) are lit by direct lights only, and zero SH is not the same as black.
   **Fix:** count both lists. Black is a drawn node with SH count 0 and direct count 0, ideally with a lit copy of the
   same asset elsewhere.
2. **Group_0 was added, and the object stayed black.** **Cause:** each light is also range-tested, and the Group_0
   lights did not reach that spot. **Fix:** take the groups from the lights assigned to lit nodes next to the object.
   A directional fill group (no range) is the safe choice for a whole area.
3. **The prefab marker has the right groups, but parts of the prefab are black (or the reverse).** **Cause:** inner
   actors inherit the prefab marker's list only when they have no list of their own. **Fix:** edit the prefab marker
   or the inner actor, whichever list the part actually uses.
4. **Writing a node's group mask (+0xE0) in memory changes nothing.** **Cause:** the engine rebuilds it every frame.
   **Fix:** test a group choice by rebuilding the markerset and reloading the level.
5. **`ronin.LoadWorld(<current level>)` does nothing.** **Cause:** loading the level that is already loaded is a no-op.
   **Fix:** `ronin.AbortLevel()` to the front end first, then load the level (the modding-surface note's gotcha 7).
6. **A node reads groups FFFFFFFF and 0 lights.** **Cause:** groups and lists are filled only when the node is drawn.
   Right after a level start a node can also be drawn unlit for about 5 s while sections activate. **Fix:** point the
   camera at the object, wait about 1 s, and retry from other sides for a few seconds.
7. **A fixed object still reads "lit" with the fix disabled.** **Cause:** another lit object shares the position: a
   doubled door on top of the original, or a lamp stand on its pipe base. **Fix:** filter the nodes by the added
   group bits.
8. **The player falls through the world after a teleport.** **Cause:** the area's collision is not streamed in yet.
   **Fix:** teleport 1.5 m above the spot and wait about 2.5 s. The scripted camera keeps rendering the area for a few
   seconds either way.
9. **Test objects (barrels) vanish during a run.** **Cause:** nearby enemies shoot them. **Fix:** clear enemies within
   about 40 m before looking.
10. **The game dies with an unknown exception after about 8 level loads in one session.** **Cause:** the 32-bit address
    space runs out (the modding-surface note's gotcha 6). **Fix:** restart the game between batches, and load the
    heaviest level first.
11. **One object has several render nodes at its position** (LODs, shadow meshes). **Fix:** take the maximum light
    count among them.
12. **Statically suspicious objects that are fine.** Some door and elevator markers on the TIE Factory, Death Star
    hangar doors and Felucia drip effects show up in the static scan but turned out lit in game, or dark by design.
    **Fix:** confirm each candidate live (step 2) before adding a rule.

## Open questions
- The live survey only sees sections streamed in near each test position, so a remote corner of a level can still
  hide an unlit object.
- A full sweep would stream each section in turn, for example by teleporting along the level's trigger volumes, and
  repeat the live check there.
