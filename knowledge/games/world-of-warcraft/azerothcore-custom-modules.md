---
kind: game
title: 'Custom AzerothCore modules for a solo-with-bots WotLK server: offline gathering, auction payout and restock, mail and progression fixes'
game: World of Warcraft
games_also: []
game_version: 'AzerothCore WotLK (3.3.5a) Playerbot fork, 2026-09 source; mod-individual-progression; client 3.3.5a build 12340'
platform: linux
engine: native
route: loader-api
tools: [AzerothCore module API (C++), MySQL 8.4, TradeSkillMaster price data]
anti_cheat: 'not applicable: the user''s own server'
status: working
agents:
- Claude Code (Opus 5.5)
humans: [RedSuper]
date: '2026-10-04'
links: ['https://github.com/azerothcore/azerothcore-wotlk', 'https://github.com/ZhengPeiRu21/mod-individual-progression']
tags: [azerothcore, modules, loot, mail, auction-house, progression, aq-war, pets, dbc-overrides, private-server]
---
# Custom AzerothCore modules for a solo-with-bots WotLK server: offline gathering, auction payout and restock, mail and progression fixes

> A set of server modules and core patches for a server played by one human with bots: an NPC who runs
> "farmhands" that gather while you're away and deliver crates by mail; auction proceeds paid without mail; an
> auction house that refills itself while the server runs; a mail-count fix; manual raid progression (and what the
> progression module's Ahn'Qiraj war really does); a demon pet for an NPC companion; DBC changes through the
> server's override tables. Each was built as an AzerothCore module or a small core patch and is live on the server.

## Setup
- AzerothCore module layout: `src/mod_<name>.cpp` with `Addmod_<name>Scripts()` → script registration, a
  `conf/<Name>.conf.dist`, no CMake edits (folders are auto-discovered, but adding one triggers a near-full
  rebuild).
- Script types used: `CreatureScript` (gossip), `WorldScript` (startup/update/config), `PlayerScript`,
  `AuctionHouseScript`.

## Route and why
Module API wherever a hook exists; a core patch only where the bug is in the core (mail counts, a threat bug,
progression guards).

## How the game works (what we had to learn)
**Loot tables, as the core reads them**
- Loot rows with a `GroupId` form groups where exactly one item drops; `Chance = 0` rows in a group share the
  remainder equally (8,579 of 18,025 gameobject rows rely on this). `Reference` rows expand recursively into
  `reference_loot_template` (gems live there).
- Skinning loot is keyed by `creature_template.skinloot`, not by creature entry.
- Item class 12 (quest items) appears in gathering tables; filter it out of anything you hand out.

**Crates and mail**
- Per-item stored loot (`item_loot_storage`) lets an item act as a crate, but `LoadStoredLoot` only runs when an
  `item_loot_template` row exists for that item (give it one near-zero-chance row; chance 0 + group 0 is rejected).
- The loot window shows at most 18 items (`MAX_NR_LOOT_ITEMS`); stack counts are 8-bit (255 max).
- `MAX_MAIL_ITEMS` is 12 per mail: split bigger deliveries.
- `MailReceiver(guid)` hard-codes no player, so an online recipient is never notified; use the
  `MailReceiver(player, guid)` form.
- The unread-mail counter only goes down in "mark as read"; mail taken or deleted unread (addons that "open all")
  leaves a phantom mail icon. Fixed in the core: decrement on delete/return of an unread mail and skip deleted mail
  when recounting.
- The client inbox shows 50 mails.

**Database**
- `CharacterDatabase.Execute()` is asynchronous: an INSERT followed by a SELECT for its id reads 0. Use
  `DirectExecute()` when you need the row now.
- DBC override tables (`spell_dbc`, `skillraceclassinfo_dbc`, `charstartoutfit_dbc`, `creaturefamily_dbc`, …) add
  or replace rows by id at startup; the client still needs the matching DBC rows in a patch MPQ when it reads them
  (e.g. `CharBaseInfo` for new race/class combinations lives in the locale archive).

**Auction house**
- `AuctionHouseScript` hooks can suppress the sale-pending, successful and won mails (`sendMail = false`), and
  `OnAuctionSuccessful` runs right after: enough to pay sellers directly instead of filling a 50-mail inbox.
- Auctions live in server memory and are written back at shutdown: editing the auction tables on a running server
  is silently undone. To add listings live, do what the core does: `Item::CreateItem` (clone mode avoids random
  suffixes), `SaveToDB`, `sAuctionMgr->AddAItem`, `AuctionHouseObject::AddAuction`, then the entry's `SaveToDB`, in
  one transaction.
- Our stock comes from roster tables (item, stack size, count) seeded at boot. A buyer bot that pays up to a
  percentage of a **separate** market-price table only buys what that table prices high enough: two price tables
  that drift apart mean player auctions at the seed price never sell.

**Pets**
- A creature family maps to its pet spells (`CreatureFamily` → skill lines → abilities); warlock summons use the
  summon-pet effect, vanity pets another.
- The pet's nameplate comes from the creature query (`creature_template.name`), not the family.
- `Pet::InitStatsForLevel` switches on the creature entry: an unknown entry gets no stat-scaling auras.

**Progression module (mod-individual-progression)**
- Tiers are stored as rewarded hidden quests 66001–66018; raising a tier back-fills every lower one.
- In the build we had, boss kills still advanced tiers although `DisableDefaultProgression = 1` (the guard was
  commented out), and `.ip set` couldn't set tier 0. Patched: kills only advance with default progression on;
  tier 0 clears all tiers.
- Its per-player AQ war effort: a "Complete the War Effort" quest (1,000 commendation signets, after every
  collection quest once) gates both the Scepter questline start and the module's own gong quest.
- **Ringing the gong** ("Bang a Gong!") moves the player to tier 4 only when default progression is on; with
  `DisableDefaultProgression = 1` nothing moves and tiers stay manual.
- The gong plays the gate opening (roots, glyphs, door) and **closes the gate again about five minutes later**, so it
  can be replayed; the module's "war" step is an empty wait. Clicking the gong again reopens it. The gate objects
  are shown to characters below tier 5.
- **The outdoor AQ war is phased to tier 4 only** (a phase aura in Silithus, Darkshore and the Scarab Wall): the
  three Colossi (Zora, Regal, Ashi, with kill quests from the gong's NPC), Lieutenant General Nokhor with Supreme
  Anubisath Warbringers, Colossal Anubisath Warbringers, a low-level Darkshore part and crystal formations. Counting
  only spawns that carry a script name finds almost none of it; the phase mask is what places them.
- The Colossi (about 2 million health, immune to interrupts and stuns) cast Colossal Smash 60 seconds into the
  fight and every minute after: a 5-second cast hitting everyone within 100 yards for 3,125 physical damage plus a
  knockback of 50 yards/s outward and 50 up. That throws players about 260 yards on flat ground and 65 up: the fall
  costs about 92% of maximum health, and since the Colossi only attack targets within their 200-yard visibility
  override, they evade at full health when everyone lands outside it.
- In this build the war bosses' loot tables hold level-70 items (a TBC sword, Living Ruby gems).

## Build steps
1. **Offline gathering ("FarmSim"):** an NPC sells farmhand contracts by race and tier; a world-update tick works
   out each farmhand's yield over elapsed time from the real loot tables (groups, references, skinning loot,
   fractional race bonuses rolled probabilistically), and mails crates (stored loot) in 12-item mails. Rates were
   anchored to human gathering speeds and priced from auction data.
2. **Auction payout:** suppress the auction mails, pay gold directly in `OnAuctionSuccessful`, pay first and never
   lose gold at the money cap.
3. **Mail unread fix:** the two core functions above (no header changes, a one-minute build).
4. **Progression:** the two guards in the module plus a reversible SQL for tier changes.
5. **Companion demon pet:** clone a warlock summon without its reagent, add a pet stat case for the new entry,
   rename via the creature row.
6. **Auction restock:** a timer in our market module (every 30 minutes, at most 500 listings per pass, first pass one
   interval after boot) counts the bot's live listings per (item, stack) and creates the missing ones in memory with
   the same rules as the boot seed (price × stack capped at 2 billion copper, bid 80%, one-year expiry).

## Verification
- Time-jump tests for gathering (six simulated hours → tiered yields, real gem rarity, no quest items).
- In-game checks with the human for every live change; DB row checks for crates, mail and progression.
- Restock: the listing count after boot matched the roster, and a live pass re-posted exactly what had sold
  (4 listings, none left short).
- The AQ war facts come from the module's code and data plus the human's play (the closing gate, the Colossi
  resetting); the knockback distance and fall damage were computed from the spell data, not measured in game, and the
  war bosses' loot was read from the tables, not seen drop.

## Gotchas
1. **Paid upgrades were never saved.** **Cause:** async INSERT then SELECT id → 0, so every save ran `WHERE id=0`.
   **Fix:** `DirectExecute`, plus a guard refusing id 0 and a refund.
2. **A crate opened empty and destroyed its contents.** **Cause:** no `item_loot_template` row, so stored loot never
   loaded. **Fix:** one near-zero-chance row per crate item.
3. **Gems never showed up in yields.** **Cause:** reference loot not expanded. **Fix:** recursive expansion.
4. **Most gathering nodes yielded nothing.** **Cause:** `Chance = 0` rows treated as never-drop. **Fix:** the core's
   group semantics.
5. **Deliveries silently short.** **Cause:** the 12-item mail cap. **Fix:** split into several mails.
6. **Mail arrived but the player wasn't told.** **Cause:** the guid-only `MailReceiver`. **Fix:** the player form.
7. **A phantom unread-mail icon.** **Cause:** the counter only drops on mark-as-read. **Fix:** the core patch above.
8. **Raid progression moved by itself.** **Cause:** the module's kill guard was commented out. **Fix:** restore it.
9. **A cloned pet spell failed with "missing reagent".** **Cause:** the original's soul-shard reagent came along.
   **Fix:** clear the reagent in the override row.
10. **Auction listings added in the database vanished.** **Cause:** auctions are in memory and rewritten at
    shutdown. **Fix:** seed before the world server starts, or create them in memory through the auction manager.
11. **The player's own auctions never sold.** **Cause:** the buyer bot priced from a different table than the seed;
    615 items were listed above its limit. **Fix:** sync the buyer's prices from the seed table (the module re-reads
    them on a config reload).
12. **"The AQ gate keeps closing."** **Cause:** the progression module resets it five minutes after the gong.
    **Fix:** click the gong again, or hide the gate objects from tier 4 instead of tier 5.
13. **The Colossi can't be beaten by a bot raid.** **Cause:** Colossal Smash's knockback throws everyone out of the
    boss's attack range every minute (see above). **Fix:** none in the module; a smaller knockback through a server
    spell override would make it a fight.

## Open questions
- The AoE-loot module mishandles quest items and conditional drops; not fixed yet.
