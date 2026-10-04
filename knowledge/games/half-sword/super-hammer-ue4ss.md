---
kind: game
title: 'Super Hammer: a 1-coin merchant item that hits 9.9x harder, via UE4SS Lua'
game: Half Sword
games_also: []
game_version: Half Sword Early Access 0.6.1.5 (Steam 2397300, build 24185754), UE 5.4
platform: windows
engine: unreal
route: loader-api
tools:
- UE4SS experimental v3.0.1-1152-ge3ba1016 (2026-09-29)
- Dumper-7 SDK from lambor590/Half-Sword-Enhancer (read on GitHub, nothing installed)
anti_cheat: none (single player)
status: working
agents:
- Claude Code (Opus 5.5)
humans:
- '@Fraydo23'
date: '2026-10-03'
links:
- https://github.com/UE4SS-RE/RE-UE4SS
- https://github.com/lambor590/Half-Sword-Enhancer
- https://github.com/massclown/HalfSwordModdingResources
- https://github.com/massclown/HalfSwordTrainerMod
tags: [ue4ss, lua, shop, merchant, weapon-passport, damage-multiplier, blueprint-post-hook, asset-registry, campaign]
---
# Super Hammer: a 1-coin merchant item that hits 9.9x harder, via UE4SS Lua

> In the campaign the tavern merchant sells a new "Super Hammer" for 1 coin. It is the merchant's
> ordinary tool hammer, marked through its weapon passport, and every hit deals about 9.9x normal damage
> (5x the impact of the heaviest melee weapon). It's one UE4SS Lua file: no paks, no editor, no new assets.
> Verified in the real game: it shows in the shop, can be bought and equipped, and an NPC hit test
> confirmed the extra damage. The human then played it in the campaign.

## Setup
- **Game:** Half Sword Early Access 0.6.1.5, Steam build 24185754, Windows 11, UE 5.4.
  - One `pakchunk0-Windows.pak` (pak v11, encrypted index, no IoStore). It was never extracted.
- **Loader:** UE4SS experimental-latest `v3.0.1-1152-ge3ba1016`. Put `dwmapi.dll` plus `ue4ss/` next to
  `HalfswordUE5/Binaries/Win64/HalfSwordUE5-Win64-Shipping.exe`. It loads fine when started from Steam.
- **Class and property names:** taken from the public Dumper-7 SDK in lambor590/Half-Sword-Enhancer
  (updated 2026-09-22), then confirmed live. Dumper-7 shows names with underscores, but the real
  UFunction/UProperty names contain spaces (see Gotcha 1).
- **Saves:** `%LOCALAPPDATA%\HalfSwordUE5\Saved\SaveGames\GameProgress.sav`, with Steam Cloud on.
  Snapshot it with `um backup` before every launch (see Gotchas 3 and 4).

## Route and why
- **Taken: UE4SS Lua (loader-api).** The merchant stock, the item objects, the weapon passports and the
  damage function are all reachable from Lua at runtime.
- **Not taken: a pak mod (a new weapon Blueprint and DataTable edits).** It would need the AES key,
  `.usmap` mappings and a matching UE 5.4 editor project.
- **Not taken: a C++ UE4SS mod.** It would allow a true pre-hook on the Blueprint damage function, but the
  Lua workaround in "How the game works" was enough.

## How the game works (what we had to learn)
- **Merchant stock lives in the game instance.**
  - It's `GI_Settings_C["Merchant Inventory"]`, a `Str_Inventory` struct whose
    `WeaponPssports_6_…` field (sic) is a `TArray<Str_Passport_Weapon1>`. The player's items are in
    `["Player Inventory"]` with the same layout.
  - `GI_Settings_C:Renew Merchant` rebuilds the stock, for example after a fight.
  - The test lists `BP_ShopItems` / `BP_TestTraderItemsList` / `BP_ItemPrices` hold only 4 test armour
    pieces. The real shop doesn't use them.
- **Shop UI:** the tavern merchant is `UI_Shop_Frank_C` (it opens via `UI_Dialog_Widget_Merchant_C`).
  - Its `Trader_Items_List` holds `BP_GameItem_Weapon_C` / `BP_GameItem_Armor_C` objects built from the
    passports when the widget is created.
  - **Clicking a row buys it immediately.** There's no confirm step.
- **Weapon passport (`Str_Passport_Weapon1`):** user-struct fields such as `WeaponClass_54_…`,
  `ID_70_…`, `Name_57_…` (FName), `Price_60_…`, `Tier_67_…`, the module classes and the
  custom mass scales.
  - The shop displays `Name` when it's set; prebuilt tools carry `None`.
  - The passport travels into the player inventory and on to the spawned weapon actor
    (`AModularWeaponBP_C["Weapon Passport"]`). That makes it a reliable per-item marker.
  - The game resets the Price field after purchase, so match on name plus ID.
- **Prices:**
  - Armour shows its `BP_GameItem.Price` as is.
  - Weapons show and charge about 2x the passport price: Hafted 13 → 26, Mace 24 → 47, 1.0 → 2,
    0.5 → 1.
  - Tools with passport price 0 get their price from somewhere else; we didn't look into it.
- **Damage:**
  - Victims take damage in `Willie_BP_C:Get Damage(Impulse, Velocity, Location, Normal, bone, Raw_Damage,
    Cutting_Power, Inside, Damaged_Mesh, Dism_Blunt, Lower_Threshold, Shockwave, Hit_By_Component, Stab,
    Hit_Box, Pain_Rate, Hit_Flesh, Draw_Cut, out Damage_Out)`.
  - Raw_Damage arrives already computed from the hit physics.
  - HP loss is roughly linear in Raw_Damage, with a per-bone factor: torso/neck about 0.008 HP per raw
    point, limbs much less.
  - `Hit_By_Component:GetOwner()` is the weapon actor.
- **No damage stat per weapon:**
  - Damage comes from physics, and raw/velocity per hit varies 0.01..1+ with angle and contact point.
  - So "strongest weapon" was defined as impact mass.
  - Built weapons weld all their parts into one body, so `GetMass()` of any part is the total.
  - Spawning every prebuilt class from `/Game/Assets/Weapons/Blueprints` (found through the asset
    registry) and weighing it gave:
    - heaviest melee weapon: `ModularWeaponBP_BaronBeak` at 2.72 kg;
    - the merchant's `BP_Weapon_Tool_Hammer_A` at 1.37 kg;
    - so 5x the BaronBeak relative to the hammer = 9.93x.
  - Passport-based modular weapons (e.g. `ModularWeaponBP_GreatSword`) spawn as empty 1 kg shells unless
    they're given a passport. Weigh those from NPCs in a fight instead (a Greatsword passport weighed
    2.69 kg).

## Build steps
1. Install UE4SS as described in Setup. Create `ue4ss/Mods/SuperHammer/Scripts/main.lua` and an empty
   `enabled.txt`.
2. **Stocking the hammer:** on `NotifyOnNewObject("/Script/UMG.UserWidget")` for `UI_Shop_Frank_C`, on a
   post-hook of `GI_Settings_C:Renew Merchant`, and on `ClientRestart`:
   - if the merchant array has no passport with our name/ID, append a copy of the `BP_Weapon_Tool_Hammer_A_C`
     passport (`arr[#arr + 1] = arr[i]` copies the struct);
   - set `Name` to "Super Hammer", `ID` to 4242 and `Price` to 0.5.
3. **The damage:**
   - Register a post-hook on `/Game/Character/Blueprints/Willie_BP.Willie_BP_C:Get Damage`.
   - When raw or cut > 0 and the hitting component's owner has the marked passport (and isn't the wielder
     itself), call `victim["Get Damage"](...)` again with the same arguments, `raw*(M-1)` and
     `cut*(M-1)`, and `{}` for the out param.
   - Guard against re-entry with a flag.
4. Play: Tavern → Handel → Handel. The Super Hammer is the last row. Buy it, then equip it from the chest
   (Dextra slot).

## Verification
- **Oracle:** UE4SS log lines from the mod plus screenshots via `um win shot`. A file bridge (Lua dropped
  into a watched file, run on the game thread, output appended to a text file) let the agent query and
  poke the live game without restarts.
- **Shop (campaign):**
  - The row "Super Hammer | 1.36 kg | 1" appears.
  - Buying took money from 1 to 0 and put the passport (name + ID kept) into `Player Inventory`.
  - Equipping it gave the dress-up Willie a `Weapon R` with the marked passport.
  - The merchant restocked it after `Renew Merchant`.
- **Damage (free mode):**
  - An NPC got the passport through `Set Up Right Hand Weapon` in a free-for-all.
  - The second Get Damage call cost about 8.8-9x the HP of the original hit (lowerarm 0.13 → +1.17,
    upperarm 0.22 → +1.94), so the total is about 9.9x.
- **Human:** the player then used it in the campaign; it works.
- **Not measured:** the multiplier on the player's own hits with logs on. It's the same code path.

## Gotchas
1. **Property and function names have spaces.** `w.Weapon_R` returns a TrivialObject and `#gi.Available_Weapons_1H`
   errors. **Cause:** Dumper-7 swaps spaces for underscores, but the real FNames are `Weapon R`,
   `Merchant Inventory`, `Get Damage`, `Renew Merchant`. **Fix:** use `obj["Weapon R"]` and
   `victim["Get Damage"](victim, ...)`. User-struct fields keep their `_NN_GUID` suffix.
2. **A UE4SS hook on a Blueprint function can't change its inputs.** **Cause:** for non-`/Script/` paths the
   RegisterHook callback runs after the function. **Fix:** call the game's own function a second time with
   the extra amount, behind a re-entry guard. Calling a BP function from Lua works; out params come back in
   the table you pass (`{["Damage Out"]=...}`).
3. **"Fortschritts Modus" (campaign) can load straight into a running arena fight.** It did with this save.
   NPCs killed the idle player while the agent was querying, and the game wrote GameProgress.sav.
   **Fix:** snapshot saves before launch, never idle in the campaign, do recon in free mode, and restore
   the snapshot afterwards.
4. **Free mode also rewrites GameProgress.sav** when the tavern loads. Restore after every test session.
5. **`Invulnerable = true` on the player does not stop Health reaching 0.** Don't rely on it as test
   protection.
6. **Access violations kill the game; pcall can't catch them.** It crashed on `o:GetClass()` with a null
   object from an empty passport field. **Fix:** call `IsValid()` before any method on a UObject.
7. **Modular weapons spawned with plain `SpawnActor` are empty shells.** Their head, guard and grip come
   from the passport. Measure them as built weapons in someone's hand.
8. **The merchant doubles weapon prices.** Passport price 1 showed and cost 2; 0.5 shows and costs 1.
9. **`FindFirstOf("UI_Shop_Frank_C")` can return an old, closed shop.** Use `FindAllOf` and pick the one
   where `IsInViewport()` is true.
10. **The campaign merchant only exists in "Fortschritts Modus".** The free-mode tavern has no Handel.
    For tests the agent killed the arena NPCs (Health 0 + `Death()`), which gives "You won! Hold G", then
    restored the save.

## Assets
None. It reuses the game's own hammer.

## Cost and time
One long session of about 3 hours, with no paid API calls.

## Open questions
- **Where tool prices come from:** passport price 0 still shows 2..16. Probably a class default or a table
  inside the UI graph.
- **Physical knock-back:** extra impulse on super hits would make the "Kraft" visible as well as the damage.
- **Pre-hooks:** a C++ UE4SS mod (ProcessLocalScriptFunction pre-hook) could scale Raw_Damage before the
  game uses it, instead of the second call.
