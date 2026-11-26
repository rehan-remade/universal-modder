---
kind: game
title: Add a new player rifle with an XML data mod (AUG A3)
game: Door Kickers 2
games_also: []
game_version: Steam build 20072026 (exe dated 2025-09-22) (steam 1239080)
platform: windows
engine: native
route: data
tools: []
anti_cheat: none found by um scan
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-26'
links:
- https://gamepretty.com/door-kickers-2-how-to-mod-2022-step-by-step-tutorial/
- https://gamepretty.com/door-kickers-2-how-to-create-weapon-mods/
- https://inthekillhouse.com/doorkickers2
- https://www.nexusmods.com/doorkickers2/mods/top
tags: [xml, weapons, steam-workshop, data-mod, devmode]
---
# Add a new player rifle with an XML data mod (AUG A3)

> Door Kickers 2 got a new player rifle, a Steyr AUG A3, through the official XML data-mod system. It needed
> no code and no new art. The mod reuses the stock enemy-only AUG model plus the M4's ammo, optics, sounds and
> effects. A human tested it in the real game: it shows up in the Rangers Assault/Medic loadout, and the
> model, optics and firing look right.

## Setup
- Door Kickers 2, Steam (appid 1239080), build 20072026, Windows 11, 64-bit `DoorKickers2.exe`.
- Nothing installed first. The game ships its own mod system, Steam Workshop upload, a mission/level editor,
  and model exporters in `<install>\tools\` (3ds Max exporter, Blender 3.1 `.khm` plugin, model and
  animation guidelines).
- `um scan` reports "Unknown native engine". It is KillHouse Games' own C++ engine. The bundled readme
  lists PhysX, OpenAL Soft, FFmpeg, ImGui, tinyxml2, FreeType, miniz and stb.

## Route and why
- **Data mod (taken).** Nearly all game content is loose XML under `<install>\data\`, and the game loads mod
  folders from `<install>\mods\`. Equipment, firearms, ammo, attack types, scopes, units, classes,
  doctrines, trooper upgrades, AI behaviours, gameplay settings, XP tables, random map generator, campaigns,
  GUI and localization are all editable. That reaches a new weapon directly.
- **Native hooks (not needed).** The exe has no scripting VM (no Lua/AngelScript/etc. strings), and no
  community code loader exists. New mechanics would need a proxy DLL plus function hooks. Unusually,
  `DoorKickers2.pdb` (about 52 MB of full symbols) ships next to the exe, so Ghidra/IDA would show real
  function and class names. Single-player, no anti-cheat.

## How the game works (what we had to learn)
- **Mod folder.** `<install>\mods\<ModFolder>\` with a `mod.xml` (attributes: `title`, `description`,
  `image`, `author`, `tags`, `gameVersion`, `changeNotes`, `languageMod`). The stock template comments say
  `title` is the Workshop identity and can't change after publishing. The rest of the folder mirrors
  `data\` (`equipment\`, `entities\`, `localization\`, `models\`, `sounds\`, ...).
- **Loading is additive.** Mod XML loads after the stock files. Give mod files a unique name, such as
  `equipment\firearms_<yourmod>.xml`, and don't copy stock files. Equipment XML has an `<Equipment>` root.
- **A weapon is two elements.**
  - A `<Bind eqp="Name">` with `<to name="..."/>` children. One `Bind` lists the classes that may carry the
    weapon (`Assault`, `Medic`, ... from `data\units\`) and the ammo and scope entries it accepts.
  - A `<Firearm name="Name" inventoryBinding="PrimaryWeapon" category="rifle" unlockCost="N" ...>` that
    holds:
    - `<MobilityModifiers>`
    - `<RenderObject3D model=... attachSlot="prop_front_rifle" diffuseTex=...>`
    - `<ModifiableParams>` (magazine, reload/ready/guard times, accuracy)
    - `<Params>` (caliber/operation text keys, shell and magazine entities, AI ranges, `hasLaser`,
      optional `suppressedSwitch` to a suppressed twin)
    - `<AttackTypes>`, `<MuzzleFlash>`, `<Sounds>`
  - Binds are additive, so you can attach existing ammo/scopes to a new gun or new gear to an old class
    from any file.
- **Accuracy is a cone.** A higher value is *more* accurate. 100 means the cone is the size of the enemy.
  Stock rifles run from about 200 (short carbine) through about 230 (M4) to 300 (20" rifle). The value is
  interpolated between `accuracyStart`/`accuracyEnd` over `accuracyStartDist`/`accuracyEndDist`.
- **Ammo is per weapon by convention.** Stock ammo entries are named `<load>_<weapon>` and carry
  `roundsPerSecond`, damage, crit and armor-pen curves. A new gun can bind an existing weapon's ammo
  entries and fire at that weapon's rate. Make your own `<Ammo>` entries if you want a different rate of
  fire or damage.
- **Localization.** `localization\<anything>.txt` in the mod, with `@key=value` lines and `#` comments.
  Reference keys as `tooltip="@key"`.
- **Reusable stock assets.** Models (`.khm`), textures (`.dds`), sounds (by name from
  `data\sounds\sounds_library.xml`), particles and lights can all be referenced by name or path without
  copying them. `data\models\weapons\` has models for enemy-only guns (AUG among them) that players can't
  normally use.
- **Dev help files.** `data\equipment\!help_equipment.txt` and `data\entities\!help_entities.txt` document
  many attributes (the devs say they may be stale).
- **Dev mode.** In Options, click the OPTIONS title 10x, then restart. You get a debug console with XML
  errors, an ImGui debug tool and hot reload: Ctrl+T textures, Ctrl+R UI, Ctrl+Shift+R models/entities.
  Test keys: insta-win F4, spawn enemy `,`, first-person F1, UI edit mode F6.
- **Old builds ship in the install.** `v0.36`, `v1.06` ... `v1.11` folders each hold an exe plus `data.zip`.
  Probably for older mods' `gameVersion`; not verified. Installed mods declare `gameVersion` values from 15
  to 124, and a mod with an old value (35) still loads in the current build.

## Build steps
1. Make `mods\<YourMod>\mod.xml` with a `title`, `description`, `tags="Weapons"` and `gameVersion`.
2. Add `mods\<YourMod>\equipment\firearms_<yourmod>.xml` with an `<Equipment>` root holding one `<Bind>` and
   one `<Firearm>`. The quickest start is a stock player rifle (the M4 in `firearms_rifles.xml`) as the
   pattern. Change the name, text keys, model/texture paths, stats, and the ammo/scope list.
3. Add `mods\<YourMod>\localization\<yourmod>.txt` with the `@..._name` and `@..._desc` keys.
4. Before launching, check that every `name=`/`particles=`/`lightTemplate=` you reference exists in
   `data\**\*.xml`, and that every model/texture path exists. A grep loop over the mod file does it.
5. Start the game, enable the mod in the Mods menu, open the Rangers loadout.

## Verification
- **Oracle:** a human tested it in game. The rifle appeared in the Rangers Assault and Medic primary-weapon
  list with its localized name and description. The optics and the three ammo types could be picked. In a
  mission it showed the AUG model and fired and reloaded normally.
- **Before launch:** the XML parsed (Python `xml.etree`), and every referenced name and asset path was
  found in stock `data\`.
- **Not verified:**
  - the dev-mode console output;
  - Workshop upload;
  - how the `v1.xx` builds are chosen;
  - balance against stock rifles;
  - whether rail optics clip with the AUG model's integral scope (the tester reported no visual problem).

## Gotchas
1. **A new weapon's ammo choice looks like it needs new `<Ammo>` entries.** **Cause:** stock ammo is named
   per weapon (`..._M4`), which suggests a 1:1 link. **Fix:** a `<Bind>` can list another weapon's ammo
   entries, and it works. Make your own only if you need a different rate of fire or damage.
2. **The accuracy number reads backwards at first.** **Symptom:** the 20" M16A4 has a *higher* value than the
   MK18 carbine. **Cause:** the value is target size relative to the cone, so higher means tighter.
   **Fix:** a longer barrel or more precision means a bigger number.
3. **Enemy-only weapon models aren't in player loadouts.** **Cause:** they are only bound to enemy
   entities. **Fix:** reference the model/texture path from your own `<Firearm>`. Nothing needs to be
   copied into the mod.
4. **`gameVersion` value.** **Symptom:** no obvious place shows the current number. **Cause:** not exposed
   in the files we read. **Fix:** we used the highest value among installed Workshop mods (124). Older
   values also loaded, so the number seems mostly informational.

## Assets
None made. The mod reuses stock `data\models\weapons\aug.khm`, `aug.dds` and `aug_ui.dds`, and the M4's
sounds and muzzle effects.

## Cost and time
One session. Recon plus the mod took well under an hour of agent time. One in-game test pass by the human.

## Open questions
- The current `gameVersion` number, and how the bundled `v1.xx` builds are picked.
- A suppressed twin via `suppressedSwitch` plus its own `...Sup` ammo (silenced, shorter sound radius).
- New art: export a custom `.khm` with the shipped Blender 3.1 plugin.
- The native-hook route using the shipped pdb, for mechanics XML can't reach.
