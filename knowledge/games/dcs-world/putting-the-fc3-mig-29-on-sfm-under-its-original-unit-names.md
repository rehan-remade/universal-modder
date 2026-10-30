---
kind: game
title: Putting the FC3 MiG-29 on SFM under its original unit names
game: DCS World
games_also: []
game_version: DCS 2.9.30.28536 (Windows, MT build), Flaming Cliffs 3 MiG-29A/G/S
platform: windows
engine: native
route: data
tools: [mod manager (OvGME-style staging folder), Python lupa for Lua syntax checks]
anti_cheat: "none; single player and servers you run only. The DCS integrity check (pure clients) fails on the edited entry.lua, and on a server that doesn't check, a retuned SFM jet would be an unfair edge"
status: working
agents:
- Claude Code (claude-opus-5-5)
humans: []
date: '2026-10-08'
links: []
tags: [dcs, edge-engine, fc3, mig-29, sfm, unit-replace, add_aircraft, entry.lua, ejection-crash]
---
# Putting the FC3 MiG-29 on SFM under its original unit names

The user's mod already switched the Flaming Cliffs 3 MiG-29A/G/S to the simple flight model (SFM) by passing
`{nil, old = 50}` to `make_flyable`. What was missing was a place to edit the SFM weights and aerodynamics
while keeping the original unit names `MiG-29A`, `MiG-29G` and `MiG-29S`, so existing missions, payloads and
liveries keep working. The fix: a full aircraft definition loaded from the mod's `entry.lua` that calls
`add_aircraft` with the built-in name, which DCS treats as a replacement. In game, all three fly on the new SFM
numbers and Mission Editor weights match. One known problem remains: **ejecting from any of them crashes DCS**,
and it can't be fixed from Lua (gotcha 6).

## Setup
- DCS World 2.9.30.28536, Windows 11, with FC3 and the separate full-fidelity MiG-29A Fulcrum module installed.
  Naming trap: the FC3 jet's own plugin is called `MiG-29 Fulcrum by Eagle Dynamics` (the name in the log
  lines below); the full-fidelity module's is `MiG-29A by Eagle Dynamics`.
- The FC3 MiG-29 plugin lives in `Mods\aircraft\MiG-29\` (`entry.lua`, `bin\MiG29.dll`, `bin\MIG29CWS.dll`,
  `FM\` with the professional flight model's `.adb` data).
- The user's mod sat in an OvGME-style staging folder (`DCS World\AAA\<mod>\Mods\aircraft\MiG-29\`) that a mod
  manager copies over the live folder. Edit the staging copy, or the next enable overwrites your work. Both
  live under `Program Files`, so every write needs admin rights (UAC prompt).
- Single player and servers you run only. Don't fly the edited jets on other people's servers, even ones that
  don't enforce the integrity check: changed weights and aero are a performance edge there.
- No Lua interpreter on the machine. `pip install --target <scratch> lupa` plus `loadstring` gives a quick
  syntax check without installing anything system-wide. It only catches syntax; DCS is the real test.

## Route and why
- **Edit the original definition file:** impossible. The old `Scripts\Database\planes\*.lua` files (and
  `db_main.lua`) are now inside `Scripts\Database.edce`, which is encrypted (high-entropy header, no zip or
  Lua signature). Decrypting it would mean getting around Eagle Dynamics' file protection, so we didn't.
- **Patch `db.Units.Planes.Plane` from `entry.lua`:** inconclusive. The entry sandbox has no `pcall`, and a
  defensive probe placed after `plugin_done()` produced no output at all.
- **Clone under a new name** (what the user had already done as "MiG-29N"): works, but it isn't the
  original units.
- **Replace the unit by name (chosen).** Other installed mods log `plugin: <mod> unit replace <Unit>` at
  startup. Currenthill's Tu-95MS is a plain definition with the built-in `Name` and `add_aircraft(...)`. The
  same works for the MiG-29.

## How the game works (what we had to learn)
- **Where unit data lives now:** legacy ED units (FC3 jets and others) are compiled into `Database.edce`.
  The Mission Editor still loads it through `dofile("Scripts/Database/db_main.lua")` in `me_db_api.lua`, so
  the path is virtual.
- **Replacing a unit:** call `add_aircraft{ Name = "<built-in name>", ... }` from any plugin's entry. DCS logs
  `plugin: <plugin> unit replace <Name>`. It's a whole-definition replacement, not a field patch: shape,
  pylons, sensors, damage, lights and SFM all have to be supplied.
- **IDs:** use `WorldID = WSTYPE_PLACEHOLDER` and **no `index`** in `shape_table_data`. Put the real type
  constant (`MiG_29`, `MiG_29G`, `MiG_29C` from `Scripts\Database\wsTypes.lua`) in `attribute`. Hard-coded
  IDs collide with the stock shape entries (gotcha 2).
- **SFM switch:** `make_flyable(name, cockpit, {nil, old = 50}, comm)` makes a player aircraft use
  `SFM_Data` from its definition instead of the plugin's DLL flight model. The FC3 plugin must still load
  `MIG29CWS.dll` (gotcha 7).
- **The entry sandbox:** no `pcall`. `pairs`, `math` and plain loops work. Calling a missing global aborts the
  rest of that `entry.lua` and logs `attempt to call global '<name>' (a nil value)` in `dcs.log`.
- **Ejection fields:** `crew_members[n].ejection_seat_name` / `drop_canopy_name` take either a wsTypes object
  ID (`K36` = 9, `MIG_29_FONAR` = 28, `MIG_29C_FONAR` = 47, `MIG_29G_FONAR` = 48, ...) or the name of a shape
  that some module registers.
- **Damage tables:** cell numbers and names are in `Scripts\Aircrafts\_Common\Damage.lua`. Read the two
  warnings below carefully, because they mean opposite things.
- **Model per variant:** 9.12 = `MiG-29` shape, G = `MiG-29G`, 9.13 "hump" (MiG-29S) = `MIG-29C`. Livery
  folders are `Bazar\Liveries\mig-29a|g|s`, which match the shape table's `username`.

## Build steps
1. In the mod's staging copy, add `MiG-29_SFM.lua`. It holds one shared builder function, an `SFM_DATA`
   table, and a `VARIANTS` list with per-variant name, shape, type constant, input profile, wreck prefix,
   canopy ID and masses. A loop calls `add_aircraft(make_mig29(v))`. A complete community definition (the
   user's "MiG-29N") served as the base. 9.12 masses and sensors were cross-checked against the MiG-29
   Fulcrum module's own definition in `CoreMods\aircraft\MiG-29-Fulcrum\`.
2. Remove carrier-only parts from the base: launch bar, folding wings, carrier runway categories.
3. In `entry.lua`, add `dofile(current_mod_path..'/MiG-29_SFM.lua')` **before** the `make_flyable` calls.
   Keep `binaries = {'MiG29','MIG29CWS'}`.
4. Re-enable the mod in the mod manager, start DCS, check `dcs.log` for three `unit replace` lines and no
   `already declared` errors.

## Verification
- `dcs.log`: `plugin: MiG-29 Fulcrum by Eagle Dynamics unit replace MiG-29A` (and G, S) on every launch.
- The user flew it: handling matched their SFM tuning. Mission Editor empty and fuel weights matched the
  `VARIANTS` values for A/G (10922 + 3376 kg) and S (11222 + 3493 kg), but those are also the stock values, so
  they don't prove the replacement took; the `unit replace` lines and the handling do.
- Not verified in game: the damage-cell fix from gotcha 4 (the file was syntax-checked, but not flown after
  that change), payload presets for every variant, and visual damage arguments on the FC3 model.

## Gotchas
1. **No `planes\` folder, nothing to edit.** **Cause:** legacy unit definitions moved into the encrypted
   `Scripts\Database.edce`. **Fix:** replace the unit by `Name` from a plugin instead of editing it.
2. **`Object MIG-29 with id=2 already declared in table PlaneTable`** (and id 49/50). **Cause:** we set
   `WorldID` and the shape table `index` to the built-in IDs, which the stock shape entries already own.
   **Fix:** `WorldID = WSTYPE_PLACEHOLDER`, no `index`, type constant only in `attribute`. This is how
   Currenthill's Tu-95MS replacement does it.
3. **`attempt to call global 'pcall' (a nil value)` and the mod silently stops being SFM.** **Cause:** the
   entry sandbox lacks `pcall`, so a probe using it aborted `entry.lua` before `make_flyable` ran. **Fix:**
   keep diagnostics after `plugin_done()` and check that each function exists before calling it.
4. **`No cell for property records GUN TAIL_LEFT_SIDE ...` vs `No property record for cell "TAIL"`.**
   **Cause:** the first means the damage table has entries for cells the collision model doesn't have (they do
   nothing). The second means the model has cells the table lacks (those parts can't be damaged, including
   `CREW_1`, the pilot). **Fix:** for the FC3 MiG-29, drop cells 7/56/57/61 and add 19, 21, 22, 33, 34, 55, 58,
   83, 84, 85 and 90. The values came from the Fulcrum module's table, which uses the same draw-argument
   numbers wherever both define a cell.
5. **`Corrupt damage model` at spawn.** **Cause:** unknown, but harmless: it also appears for many stock
   aircraft (A-10A, Su-25T, Mi-8MT, KC-135) in sessions that don't crash. **Fix:** ignore it.
6. **Ejecting crashes DCS** (`ACCESS_VIOLATION` in `GraphicsVista.dll`, `DefResourceManager`), for every
   FC3 MiG-29 variant on SFM. **Cause:** not fully known. Ruled out by testing:
   - our definition (ED's own built-in MiG-29S crashes the same way with only `old = 50`);
   - the canopy (the stock 9.13 canopy, the 9.12 canopy, the Fulcrum module's canopy and an F-4 canopy all
     crash);
   - the cockpit scripts (byte-identical to a separately named clone that ejects fine).

   The remaining difference is that built-in MiG-29 types run through `MIG29CWS.dll`, and the clone doesn't.
   A `texture 'mig-29c_tex01_spec' not found` line before some crashes was a red herring: it comes from the
   9.13 canopy model and disappears when the canopy changes, but the crash stays. **Fix:** none from Lua. To
   eject safely, use a separately named clone. The user accepted the crash.
7. **Removing `binaries` makes the jet unflyable** (spawns as AI, spectator only, log: `Invalid Unit Module:
   "MiG-29S" CWS initialization failed`). **Cause:** the built-in FC3 MiG-29 types need the FC3 cockpit and
   weapon-system module. **Fix:** keep the DLLs. Don't try to bypass this check.
8. **Edits seem to vanish.** **Cause:** the mod manager re-copies the staging folder on enable. **Fix:**
   always edit the staging copy, and compare hashes of the staging and live copies before launching.

## Assets
None.

## Cost and time
One session, about ten DCS launches, most of them spent narrowing down the ejection crash.

## Open questions
- What exactly in `MIG29CWS.dll` crashes on ejection under SFM? Ejecting from a stock (PFM) FC3 MiG-29S
  would confirm the stock path is fine; that wasn't done.
- Can `entry.lua` patch fields of an existing unit in `db.Units.Planes.Plane` instead of replacing it whole?
  Our probe gave no output, so this is unresolved.
- Whether the Fulcrum draw-argument numbers for the added damage cells show visual damage on the FC3 model.
