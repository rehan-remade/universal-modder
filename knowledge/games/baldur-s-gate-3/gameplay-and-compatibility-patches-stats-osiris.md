---
kind: game
title: "Gameplay and compatibility patches in stats and Osiris: level-gated armour tiers, Extra Attack on a modded cantrip, crit immunity, stacking damage reduction, feats from items, removing equipment glow, a class vs starting-equipment fix"
game: "Baldur's Gate 3"
games_also: []
game_version: "Patch 7 era (Apr 2026) to Patch 8 hotfix (Aug 2026), Steam, Windows"
platform: windows
engine: unknown
route: data
tools: ["LSLib Divine 1.20.4", "vanilla stats dump (BG3 Modders Multitool)", "Python (stats parsing, override generators, level simulators)"]
anti_cheat: "none; single-player"
status: working
agents: ["Claude Code (Opus 4.7)", "Claude Code (Opus 5)", "Claude Code (Opus 5.5)"]
humans: [RedSuper]
date: 2026-10-04
links: []
tags: [stats, passives, statuses, boosts, armour-class, damage-reduction, critical-hits, extra-attack, osiris, override, patch-mod, starting-equipment, vfx, amp-ultra, dialogue]
---

# Gameplay and compatibility patches in stats and Osiris: level-gated armour tiers, Extra Attack on a modded cantrip, crit immunity, stacking damage reduction, feats from items, removing equipment glow, a class vs starting-equipment fix

> A collection of small, data-only changes to a heavily modded game, split across two of our own mods: an
> item mod (stats for our own gear) and a patch mod that loads last and overrides entries of other mods.
> Most were tested in game by the human; the Verification section lists which ones were not reported back.
> The recurring lesson: copy the exact form of a shipped item that already does the thing, and check what
> working mods do before declaring a form invalid because vanilla never uses it.

## Setup
- BG3 on Steam, Windows; ~520 mods, Script Extender present but not needed by these patches.
- A full vanilla stats dump to grep (`Shared`/`SharedDev`/`Gustav` `Stats/Generated/Data/*.txt`) and the game's
  condition scripts (`Scripts/thoth/helpers/CommonConditions.khn` inside the Shared pak).
- Patch mod: own `meta.lsx` copied from a working mod with an **empty** `Dependencies` node, registered at the
  end of the load order.

## Route and why
`data`: stats overrides, root templates, progressions, Osiris goals. **A stats override only wins if its mod
loads after the mod it overrides**, so patches to other mods live in a separate mod placed last, not in the
item mod (which loaded before the mods it needed to patch). The override idiom is a self-referential entry:
`new entry "X"` / `type "<same>"` / `using "X"` / then only the changed `data` lines; every other field is
inherited from the earlier definition.

## How the game works (what we had to learn)
- **Armour class.** `data "ArmorClass"` is a static number. The only AC boost functors in vanilla are `AC(n)`
  (a bonus) and `ACOverrideFormula(n, dexFlag, ability)` (replaces the base formula; Barkskin, Mage Armor,
  Unarmored Defence use it, highest wins). Neither behaves like a real base AC: Barkskin stacks under `AC()`,
  and `ACOverrideFormula` swallows bonuses that should sit on top. An armour whose base AC grows with level
  therefore has to be **separate items** (we made three tiers: AC 16/18/20, Rare/Very Rare/Legendary).
- **Heavy armour needs three fields:** `ArmorType "Plate"` (family), `"Armor Class Ability" "None"` (a robe
  parent adds the wearer's Dexterity to AC otherwise) and `"Proficiency Group" "HeavyArmor"` (draws the
  "Heavy Armour" badge and gates proficiency). Plate's `Disadvantage(Skill,Stealth)` is on `ARM_Plate_Body`, so a
  robe-derived parent does not give it. Walk the full `using` chain before assuming what is inherited.
- **Level-gated boosts:** `IF(CharacterLevelGreaterThan(N)):<boost>` works inside `data "Boosts"` (34 installed
  mods use it), with `and` / `not` combinations, e.g. a "level requirement" penalty
  `IF(not CharacterLevelGreaterThan(4)):AC(-10);IF(not CharacterLevelGreaterThan(4)):Disadvantage(SavingThrow,
  Strength)`. Conditions do not nest: `IF(a):IF(b):boost` is invalid, fold them into one `IF(a and b)`.
- **Flat damage reduction stacks:** the game converts every reduction (resistance as half the damage, rounded)
  to a flat value, sums, floors at 0; Heavy Armour Master plus a plate passive both apply. The combat-log line
  "Damage: 4 - 3 (Heavy Armour Master)" names one contributor, not the total.
- **"Attackers cannot land critical hits"** is `CriticalHit(AttackTarget,Success,Never)`. Vanilla puts it bare
  in the armour's own `Boosts` (adamantine armour) or on a status; in a PassiveData it did nothing for us.
- **Extra Attack** chains a spell only if its `SpellRoll` **text** contains `WeaponAttack`, `UnarmedAttack` or
  `ThrowAttack` (the game's condition does a literal substring match; a few spells are allow-listed by id).
  `IsDefaultWeaponAction` is not what gates it.
- **Passive presentation:** `data "Properties" "IsHidden"` hides a passive from the item tooltip (it still
  applies); a "Unlocks the following passives" list is plain loca text on one highlighted dummy passive with
  `<LSTag Type="Passive" Tooltip="<PassiveName>">Name</LSTag>` rows (BG3 generates nothing). Omitting the
  passive's `Icon` line makes its text start flush left; the tooltip adds its own colon after the name.
- **Status icons** go through the same item-icon atlas and folders as item icons (see the outfits note in this
  folder). Passives listed on an item's tooltip did not show custom icons in our tests.
- **Vanilla XP per level** (XP to go from level N to N+1, N = 1..12): 300, 600, 1800, 3800, 6500, 8000, 9000,
  12000, 14000, 20000, 24000, 30000. The table is split across two paks (`Shared` holds levels 1-5, `SharedDev`
  6-12), so reading one pak gives half of it. Useful when tuning a level-cap mod: vanilla 5→12 costs 93,500 XP and
  a full campaign ends around 100,000 total.
- **Osiris goals in a mod** (`Mods/<Mod>/Story/RawFiles/Goals/*.txt`): `INITSECTION` runs only on a new game.
  To affect existing saves, assert from `KBSECTION` on `SavegameLoaded()` and `LevelGameplayStarted(_, _)`;
  re-asserting a fact is a no-op. Check every call against vanilla goals before shipping: a wrong call breaks
  story compilation (we nearly shipped `ObjectToPlayer`, which does not exist).

## Build steps (one recipe per patch)
1. **Three-tier level armour.** Three stats entries differing only in name, root template, rarity and
   `ArmorClass`; each equips only its own rank passives (Strength floor via `AbilityOverrideMinimum(Strength,N)`,
   damage reduction via bare `DamageReduction(All, Flat, N)`, identical in form to vanilla
   `ARM_MagicalPlate_2_Passive`); shared unlocks (web/grease immunity at 4, crit immunity) and a hidden level
   requirement penalty on the higher tiers. Simulate every tier at every level in a script before shipping:
   the first simulator's own regex broke on nested parentheses and reported false overlaps.
2. **Extra Attack for a modded cantrip** (5e Spells' Green-Flame Blade). Its `SpellRoll` was a helper call
   `SCAGtrips()` defined in the mod's own `.khn` as a melee weapon attack; the roll worked but the text lacked
   `WeaponAttack`. Override only `SpellRoll` to `Attack(AttackType.MeleeWeaponAttack)`; the container variants
   inherit it. The same mod's Booming Blade has the same pattern.
3. **A feat from a usable item** (Dual Wielder). A feat is its passives (`DualWielder_PassiveBonuses` +
   `DualWielder_BonusAC`). Deliver them from a permanent BOOST status with `data "Passives"` (pattern of vanilla
   `ENABLE_AOO`) and hide it with `StatusPropertyFlags "DisableOverhead;DisableCombatlog;
   DisablePortraitIndicator;DisableInteractions;IgnoreResting"`. The item is a scroll-type root template whose
   use action (`ActionType=12`, `Consume=True`, `SkillID=<spell>`) casts a standalone Shout that applies it.
   It grants the mechanics, not a feat entry on the character sheet.
4. **"Bound weapon" on a dagger:** a passive with `CannotBeDisarmed();ItemReturnToOwner()` and the vanilla
   WEAPON_BOND loca handles; vanilla `ImmuneToDisarm` ("Bound") is a different, weaker effect.
5. **Remove equipment glow without touching stats.** Glow is a status with `StatusEffect` = a MultiEffectInfo
   GUID. For gear it is mostly applied by the **root template's `StatusList`** (122 statuses in one loot mod),
   rarely by stats `StatusOnEquip` (~15). Override each status with `data "StatusEffect" ""` and nothing else
   (gate: no other field may be set). Bulk-convert the mod's root templates with
   `divine -a convert-resources -i lsf -o lsx` (one file at a time times out). Skip world objects (chests,
   stations) and vanilla condition statuses you still want to see (Wet), because the override is global.
   The other route, a stub `MultiEffectInfo` with only Name and UUID, kills that effect everywhere.
6. **Turn off a difficulty mod's boss reinforcements** (Ancient Mega Pack "Ultra" mirror spawns). Three callers
   reach the spawn procedure: a status applied by two hidden watcher passives, an "anti-turtle" Osiris rule with
   no status at all, and a debug text event. The mod's own Training Ring only flags 2 of 8 pool entries.
   Patch: override the two watcher passives to a never-true condition, and an Osiris goal that asserts the
   mod's own "pool entry disabled" fact for all 8 entries on `SavegameLoaded`/`LevelGameplayStarted`.
7. **A targeted toggle spell for a dialogue mod** (Everyone in Dialogue 2 reads only the status
   `EID_EXCLUDED`, so a spell that applies or removes it from a camp companion is equivalent to its hotbar
   toggle, which only works on the controlled character). Copy a working manually cast ally-target spell from a
   mod (it needs `SpellFlags` with `IsSpell`, animation and sound fields); `IF(HasStatus(...)):` functors in
   `SpellProperties` work (vanilla `Target_Help` uses them). Grant it with `AddSpell` from an Osiris goal.
8. **A modded class stuck on "Choices Pending" with Starting Equipment Selection (ECC).** ECC auto-satisfies an
   equipment group only by toggling an entry whose translated name is exactly "Null" or "Default". Vanilla's
   bard instrument list has none, and ECC deletes that selector from the vanilla bard row. The Sword Dancers
   class copied the vanilla row, so its four subclass rows kept an unsatisfiable selector. Fix: override those
   progression rows **by their own UUIDs** with `SelectEquipment(<ECC's instrument list with NULL entries>,1,
   SE_Instrument)` plus a `DefaultValues` row (`Add=NONE_Instrument`, same level). Verified: the class can be
   created.

## Verification
Reported working by the human in game:
- the armour tiers' damage reduction stacking with Heavy Armour Master after the condition wrapper was
  removed; the Strength floor and web/grease immunity applying; the under-level case showing the bug in
  Gotcha 3 (then fixed);
- the feat item (its status even showed in the condition bar until the hide flags were added);
- the starting-equipment fix: the class can be created ("all works");
- the dialogue toggle spells appearing (after the first version could not be cast, Gotcha 5).
Shipped but not reported back from play (treat as unverified): crit immunity on the armour `Boosts`, Extra
Attack chaining for Green-Flame Blade after the `SpellRoll` override (the earlier `IsDefaultWeaponAction`
patch was confirmed to do nothing), the bound-weapon passive, the AMP spawn switch, the second version of the
dialogue toggle, and glow removal beyond the two items the human named.

## Gotchas
1. **Our damage reduction applied but did not stack.** **Cause:** wrapped in `IF(CharacterLevelGreaterThan(N))`;
   no mod or vanilla entry wraps `DamageReduction` in a condition. **Fix:** split tiers into items and use the
   bare vanilla form. A detour "fix" that published `n + 3` when Heavy Armour Master was present would have
   double-counted.
2. **"`IF(CharacterLevelGreaterThan())` is invalid in Boosts" was wrong.** Vanilla only uses it in spell fields,
   but mods use it in Boosts successfully. Absence from vanilla is a style, not a rule; check working mods.
3. **Higher tier gave lower-rank effects at level 3.** **Cause:** the tier listed all ranks with level bands.
   **Fix:** list lower ranks in the text only; equip only the tier's own rank.
4. **Armour showed as "Clothing", added Dex to AC.** Inherited from a robe parent; set the three fields above.
5. **Spell from a usable item could not be cast, auto-deselected.** **Cause:** modelled on a follow-up spell
   (fired by other spells, never clicked), `SpellFlags ""`. **Fix:** clone a working player-cast spell.
6. **A marker spell kept its parent's status and cast effect** when built with `using` a vanilla spell.
   **Fix:** standalone spell, no `using`.
7. **Earlier spell lessons (Patch 7):** `Attack(...)` with `SpellCastingAbility.Intelligence` gave 0% to hit;
   item `UnlockSpell` has no casting-ability binding (the class context decides); `AddSpells` as a status boost
   made the spell vanish; a bare self-cast Shout with `Self()` and empty `UseCosts` "unpressed" until it was
   built on a working Shout. Spell Sniper's threshold form is
   `IF(IsSpell() and IsSpellAttack()):ReduceCriticalAttackThreshold(1)`.
8. **Glow patch blanked visuals of vanilla spells too.** Statuses like Fire Shield or Feather Fall are shared
   with spells; blanking them from an item's list hid the spell's visual. **Fix:** delete those overrides; only
   blank `*_VFX`/`*_TECHNICAL` statuses that exist just for the look.
9. **First glow scans found almost nothing.** They only read stats `StatusOnEquip` and did not resolve `using`;
   the real source was the root template layer.
10. **Starting-equipment fix attempts that did nothing:** a parallel progression row with a new UUID (does not
    merge), a Compatibility Framework selector config, adding ECC's 64 selectors, removing all selectors. Only
    replacing the class mod's own bad selector worked.
11. **Patch mod not loading at all.** **Cause:** its `modsettings.lsx` entry was inserted outside
    `/root/Mods`. See the mod-setup note in this folder.

## Open questions
- Whether `DamageReduction(All, ...)` and per-type reductions combine differently from two `All` reductions.
- The unverified items listed under Verification.
