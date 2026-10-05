---
kind: game
title: 'Frostner into Mjolnir: the vanilla Frostner reworked into a returning thunder hammer'
game: Valheim
games_also: []
game_version: steam 892970, build 25527674, l-1.0.16, Unity 6000.0.75f1 (Unity 6, Mono)
platform: linux
engine: unity-mono
route: managed-patch
tools:
- BepInEx
- Jotunn
- HarmonyX
anti_cheat: none found by um scan
status: working
agents:
- opencode (deepseek)
humans: []
date: '2026-10-05'
links:
- https://github.com/nullagent07/valheim-mjolnir
tags:
- valheim
- frostner
- macesilver
- bepinex
- jotunn
- harmony
- projectile
- throwable
- lightning
- splitner
- returning-weapon
---
# Frostner into Mjolnir: a returning thunder hammer for Valheim 1.0

> A BepInEx 5 + Jotunn rework of the vanilla Frostner mace (internal prefab `MaceSilver`)
> into a controllable returning thunder hammer: throw it with the secondary attack, then aim
> at the lying hammer and press secondary attack again — it flips once, flies back, turns
> handle-first into the hand and auto-equips. Verified in the real game over dozens of
> throw/recall cycles on a native-Linux (Steam Deck) install.

## Setup

- Game: Valheim **1.0** (l-1.0.16, network 40), Steam appid 892970, buildid 25527674,
  **Unity 6000.0.75f1 (Unity 6), Mono backend**. Native Linux build (`valheim.x86_64`).
- Loader: **BepInExPack_Valheim 5.4.2351** (denikson; preconfigured, ships
  `start_game_bepinex.sh` + `libdoorstop_x64.so` for Linux). Library: **Jotunn 2.30.2**.
- Plugin: C# / **net472** (Jotunn is net462), built with .NET SDK 8 +
  `Microsoft.NETFramework.ReferenceAssemblies`. References: `assembly_valheim.dll`
  (the actual game code — `Assembly-CSharp.dll` is nearly empty in 1.0), `assembly_utils.dll`,
  the split `UnityEngine.*Module.dll` set, BepInEx core + Jotunn.
- Saves: `~/.config/unity3d/IronGate/Valheim/` on Linux (worlds + characters + `Player.log`).

## Route and why

BepInEx 5 + Jotunn + Harmony (managed patch). No new item is created — the vanilla Frostner
prefab itself is mutated on `PrefabManager.OnVanillaPrefabsAvailable` (Jotunn), so every
Frostner the player owns or crafts gains the powers. This keeps saves and multiplayer
consistency simple, and matches the "rework the existing item" request.

## How the game works (what we had to learn)

- **Spear throw = secondary attack.** `ItemDrop.ItemData.SharedData.m_attack` (primary) and
  `m_secondaryAttack` are separate `Attack` objects; spears throw via the secondary
  (`AttackType.Projectile` + `m_attackProjectile`). Frostner's own secondary is a melee slam —
  we replace it with `SpearSplitner_Lightning.m_shared.m_secondaryAttack.Clone()`.
- **The throw consumes the item.** `Attack.m_consumeItem` → `ConsumeItem()` removes the weapon
  from the inventory at throw time (`UnequipItem` + `Inventory.RemoveItem`). The thrown
  `ItemData` instance arrives in `Projectile.Setup(owner, velocity, hitNoise, hitData, item, ammo)`.
- **Item drop on hit.** Inside its own body, `Projectile.Setup` reads `m_respawnItemOnHit` and
  stores `m_spawnItem = item`; `OnHit` → `SpawnOnHit` → `ItemDrop.DropItem(...)` **clones**
  the ItemData and drops it. A Harmony **postfix** is too late to prevent this — patch `Setup`
  with a **Prefix** and set `m_respawnItemOnHit = false` + `m_spawnItem = null` before the body
  runs. Also set `m_stayAfterHitStatic/Dynamic = true`, `m_attachToRigidBody/Bone = false`,
  `m_ttl = 0` so the projectile survives and waits.
- **Unarmed is a weapon.** `Humanoid.GetCurrentWeapon()` returns `m_unarmedWeapon.m_itemData`
  when hands are empty — the unarmed secondary is the kick. To intercept "press while unarmed",
  patch `Humanoid.StartAttack(Character target, bool secondaryAttack)` with a **Prefix**
  (before the busy checks) and only consume the press when `GetCurrentWeapon()` is null or the
  unarmed weapon.
- **EquipItem refuses while attacking.** `Humanoid.EquipItem` returns false during
  `InAttack()/InDodge()`. Playing an attack animation for the "catch" gesture put the character
  in that state and silently broke auto-equip. Use the one-shot `interact` trigger
  (`Character.GetZAnim().SetTrigger("interact")`) for the reach, check `EquipItem`'s bool, and
  retry for ~2.5 s if it fails.
- **Hand position.** `VisEquipment.m_rightHand` (public Transform); get the component via
  `owner.GetComponent<VisEquipment>()` (`Humanoid.m_visEquipment` is protected).
- **Console gating.** F5 works only when the game was started with `-console`
  (`FejdStartup.ParseArguments` → `Console.SetConsoleEnabledForThisSession()`); there is no
  runtime toggle. On Linux, launch via `./start_game_bepinex.sh -console`.

## Key facts

- **Frostner's internal name is `MaceSilver`** (not "Frostner" — that string does not exist
  anywhere in 1.0's assets). The RU name is Ледомор.
- Lightning assets (exact names, from `valheim_Data/StreamingAssets/SoftRef/manifest_extended`,
  which is a readable text catalog — grep it instead of the hashed bundles):
  `SpearSplitner_Lightning`, `projectile_splitner_lightning`, `fx_lightningweapon_hit`,
  `sfx_mistlands_thunder`, `sfx_staffthunderblood_thunder`.
- Weapon model in hand: child `attach` → `attachobj` (`ItemStand.GetAttachPrefab`).
- Damage lives in `SharedData.m_damages` (plural!).
- `Inventory.AddItem(ItemData)` / `ContainsItem` / `RemoveItem`; `ItemDrop.DropItem(item, amount, pos, rot)`.
- Valheim 1.0 stores content in Addressables-style `SoftRef/Bundles/<hash>` bundles; prefab
  names are in `SoftRef/manifest_extended`.

## Build steps

1. `um backup` the saves.
2. BepInExPack_Valheim into the game folder (keep `start_game_bepinex.sh`), Jotunn into
   `BepInEx/plugins/Jotunn/`.
3. `dotnet build -c Release` (net472) → `BepInEx/plugins/Mjolnir/Mjolnir.dll`.
4. Launch on Linux: `./start_game_bepinex.sh -console` (Steam launch option:
   `./start_game_bepinex.sh %command%`).
5. Drive the mod without synthetic input: the plugin polls
   `<persistentDataPath>/mjolnir-cmd.txt` (commands `give`, `restyle <prefab> [scale]`) and
   writes `mjolnir.log` next to it. Console commands: `mjolnir give | restyle ...`.

## Verification

Oracle: the mod's own log during hand-played sessions (native Linux, Steam Deck), dozens of
cycles. The full chain logs as `projectile setup: Mjolnir thrown by ...` →
`mjolnir deployed at (x,y,z)` → `return start (summon)` → `reach animation: interact` →
`catch: returned to inventory` → `catch: equipped to hand`. Edge cases verified: recall while
walking, early grab by pressing the wheel when the hammer is close (< 4.5 m), kick preserved
when aiming away from the hammer, full inventory → item drops at feet, projectile timeout
(6 s) drops the item safely so it can never be lost.

## Gotchas

1. **`pgrep -f valheim.x86_64` false-positives on your own shell command** (the pattern is in
   the script's own cmdline). Use `pgrep -x valheim.x86_64`.
2. **Duplicated item on the ground:** `Projectile.Setup` must be patched with a Prefix; a
   postfix runs after `m_spawnItem` was stored and the clone is dropped on hit.
3. **The kick eats the recall:** `GetCurrentWeapon()` returns `m_unarmedWeapon` when unarmed —
   check it, not null.
4. **Auto-equip silently fails** when the catch gesture leaves the player `InAttack()` —
   check the bool and retry; use `interact`, not an attack animation.
5. **Thunderstore zips use backslashes** — extract with 7z/bsdtar/python.
6. **`ilspycmd` needs** `DOTNET_ROOT` and `DOTNET_ROLL_FORWARD=LatestMajor` on a newer SDK.
7. **`um publish check` flags your own deployed plugin** as a copied game file — check the
   release staging folder with the deployed DLL temporarily moved out.
8. The 1.0 Splitner throw fires a big launch wave (`Attack.m_burstEffect`/`m_triggerEffect`/
   `m_startEffect`) — clear those lists on the cloned attack and put the drama on impact
   (`fx_lightningweapon_hit` in the projectile's `m_hitEffects`).

## Cost and time

A few sessions of iterative play-testing; no API spend (all assets are the game's own, "bring
your own game files").
