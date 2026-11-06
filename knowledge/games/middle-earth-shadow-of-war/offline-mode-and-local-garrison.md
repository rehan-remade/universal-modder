---
kind: game
title: 'Offline mode and local Garrison: a winhttp stand-in for WB''s Hydra server'
game: 'Middle-earth: Shadow of War'
games_also: []
game_version: 'Steam build 3095001 (public branch, unchanged since 2018-09-05), Windows 10 22H2'
platform: windows
engine: unknown
route: native-hook
tools: ["MinGW-w64 GCC 16.2 (w64devkit)", "Ghidra 12.1.4 (headless, analysis only) + Temurin JDK 21", "custom C# read-only process-memory reader (PowerShell Add-Type)", "Python 3.12 + capstone (string/RTTI/xref scans)"]
anti_cheat: "none. SteamStub/Denuvo on the exe is untouched: the mod is a proxy winhttp.dll next to the exe and patches no code."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["DeimozZarco"]
date: '2026-10-20'
links:
  - "examples/shadow-of-war-offline-mode"
  - "knowledge/games/middle-earth-shadow-of-war/goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md"
  - "https://www.nexusmods.com/middleearthshadowofwar/mods/99"
  - "https://www.nexusmods.com/middleearthshadowofwar/mods/49"
tags: [offline, online-services, hydra, agora, winhttp, proxy-dll, garrison, nemesis, local-server, binary-protocol, reverse-engineering, testing-prerequisite, npc-id, save-edit]
---
# Offline mode and local Garrison: a winhttp stand-in for WB's Hydra server

> A proxy `winhttp.dll`, placed next to `ShadowOfWar.exe`, answers the game's WinHTTP requests to WB/Agora's
> domains inside the game process, so the game never reaches WB. It still signs in locally and keeps the Garrison
> working: you can store orcs, list them, view Details, **Deploy** them to an empty captain slot and **Destroy them
> for gear**. Orcs persist as local files, and the Mirian wallet the game moved online in 2018 is kept in a local
> file. Verified in the real game by the user over several sessions on 2026-10-10 and 2026-10-12. Source:
> `examples/shadow-of-war-offline-mode`.
>
> **For every later Shadow of War mod:** install and run this first. The game still has online modes and a WB
> Garrison backend. Testing a modded database (new tribes, creatures, gear) while signed in to WB would be online
> testing, and the universal-modder rules say to stay offline or on servers you control. With this DLL in place,
> nothing goes to WB, and the Garrison still works for storing and moving test captains. It is a single-player
> helper, not a server: see the scope under Route and why. The Goblins of War
> note ([goblin-tribe...](goblin-tribe-a-new-nemesis-tribe-via-game-gamedb.md)) was tested before this existed;
> new work should start here.

## Setup
- **Game:** Steam, build 3095001, Windows 10 22H2. Steam Overlay and Steam Cloud were off for the tests (that was
  unrelated to the mod; it just made saves local-only).
- **Install:** `winhttp.dll` and `OfflineMode.ini` in `<game>\x64\`.
  - The game loads `winhttp.dll` from its own folder before System32.
  - `install.ps1` / `uninstall.ps1` are in the example.
- **No mod loader is needed.** Neither **Packet Loader** nor the **Dll Loader** (both by survivalizeed, Nexus 49
  and 99) is used or required.
  - The Dll Loader (a `bink2w64.dll` proxy) was installed during all tests and coexists fine.
  - Packet Loader G2 v3.1 was disabled for every test, because it crashes at startup about half the time on this
    build (see the goblin note). Whether the mod runs alongside it was not tested.
- **Build:** any MinGW-w64 GCC. `build.cmd` runs
  `gcc -O2 -shared ... offline.c agb.c responder.c stubs.S winhttp.def -static-libgcc -s`.
- **Credits:**
  - Ghidra (NSA) for analysis.
  - w64devkit (Christopher Wellons) for the compiler.
  - QuickBMS and `shadow_of_mordor.bms` (Luigi Auriemma) for archive research in the earlier goblin work.
  - survivalizeed's loaders were present on the test PC but aren't used.

## Route and why
- **Route:** `native-hook`, but only as a DLL search-order proxy. No game code is patched or hooked. Since v0.12
  the DLL also writes one data field in the game's heap, the Nemesis id prefix (see How the game works);
  `NpcGuidPrefix=0` turns that off.
  - `winhttp.dll` forwards all 70 WinHTTP exports to the System32 DLL. Assembly stubs and a `.def` file are
    generated from the real export list.
  - It intercepts only sessions, connects and requests whose host matches `BlockedDomains`: `wbagora.com`,
    `agoragames.com`, `wbgames.com`, `turbine.com`, `wbplay.com`, `wbidams.com`, including subdomains.
  - For those it builds the reply locally and plays it back through the game's async WinHTTP callback (send,
    headers, data available, read). Every other host, Steam included, passes through untouched.
- **Rejected options:**
  - **Hosts-file redirect to a local HTTPS server.** It needs a trusted certificate for WB's domains, it changes
    the OS, and it affects other programs.
  - **Firewall block.** It works for "offline", but the Garrison and the Mirian wallet then stay locked or are lost
    (see Gotcha 4).
  - **Patching the exe.** It's DRM-wrapped, which is out of scope.
- **Scope (keep it this way):** the stand-in is a single-player helper, not a server.
  - It runs inside the game process and opens no port, so nothing else can connect to it.
  - It grants nothing: no catalog products, Gold, War Chests, boosts, entitlements, DLC or reimbursements.
  - The store gets one inert placeholder item and product (count 0, no price, on no shelf). The store logic needs
    both lists non-empty before it counts as open.
  - The wallet changes only through the game's own `set_count`/add/remove commands. Don't add slugs to
    `OfflineWallet.txt` by hand (the DLL re-reads it when it changes). War Chests, boosts and the other items in
    WB's online inventory were sold for Gold or are earned online, and serving them from a stand-in would be a
    purchase/ownership bypass, which the knowledge base doesn't accept.
  - Online Conquest, Online/Friend Vendettas and Market purchases aren't emulated. The `game-settings` reply says
    `vendettas_enabled: false`, every unmodelled request gets an empty map, and in testing the online button timed
    out (see Verification).
  - Don't carry this approach over to a game that still sells currency or items through its server, or whose
    online client has anti-cheat.
  - Removing the DLL puts the game back online. The goblin note's rule still applies: no Online Conquest or
    Vendettas while a data mod is installed.

## How the game works (what we had to learn)
Addresses are for build 3095001, image base `0x140000000`. They were read from the running game's memory, in a
private image kept outside any repo.
- **Transport:**
  - The online code is WB/Agora's **Hydra SDK** (`Hydra-Cpp/1.50.1`, namespaces `hydra::` and `apiframework::`). It
    uses WinHTTP in async mode.
  - Hosts: `kraken-api.wbagora.com` (API), `prod-event.wbplay.com` (telemetry). Both are answered locally.
- **Wire format `application/x-ag-binary`** (decoder `0x1409F6940`): a type byte, then a big-endian payload.
  - `02`/`03` are true and false. `10`–`17` are the integers i8..u64. `20`/`21` are f32 and f64. `30`–`32` are
    strings with a u8/u16/u32 length.
  - `40` is a date: a u32 of epoch seconds. `50`–`52` are arrays and `60`–`62` maps, with a u8/u16/u32 count.
  - **Hydra's integer reader (`0x140A01460`) only accepts int64 (`16`) values.** Ints of any other width read as 0.
  - Value classes report a type id: String 3, Map 4, List 5. Reply parsers check these, so a `{}` where a list is
    expected is silently ignored.
- **Sign-in:**
  - `POST auth` returns `{token, type}`.
  - `POST access` returns
    `{token, account{id, wbplay_identity{email}, opt_ins}, profile{id, data{}, server_data{telemetry_settings}}}`.
  - The game counts itself signed in only if both `account` and `profile` are maps (`0x141B5229C`).
  - `ssc/invoke/get_server_time` needs `{server_time (ms), query_start_MS (echoed)}`. Otherwise the game polls it
    about 1,600 times.
- **Kill switch:** the `game-settings` broadcast channel. Timelines are a cursor container
  `{cursor, start, count, total, results[]}`, and each message is
  `{slug, message_id, message, start_at, end_at, data{}}`.
  - The game reads **`data.store_enabled`**, not the `content` text (`0x1418368B0`).
  - When it's false, the game shows "We have temporarily disabled the Garrison".
- **Store "accessible"** (`0x141893780`) requires all of these:
  - signed in;
  - a storefront layout (`store-front` channel `data{version:2, title, act_i, act_ii, racks[]}`, builder
    `0x1418633BC`);
  - non-empty `GET inventory/items` and `GET commerce/catalog/me/products`. Both must be **lists**:
    `hydra::InventoryItem{count, item_slug, account_id}` and
    `hydra::CatalogProduct{name, description, tags[], payment_options{}, items[]}`.
  - Otherwise the Garrison shows "Currently updating Garrison data".
- **Garrison objects:**
  - **Listing:** `GET objects/types/user-garrison/search_queries/garrison-get-collection/run` returns a cursor
    container with `results[{score, result: object}]`.
  - **Object shape:**
    `{id, type, owner_id, created_at, updated_at, data{FactionMember, Searchable, sys_creator, sys_name}}`.
  - **Sending an orc:** `POST objects/user-garrison` with the whole `data` (about 5 KB: gear, appearance, traits).
  - **Reading one:** `GET objects/user-garrison/<id>`.
  - **Removing one:** `DELETE objects/user-garrison/<id>`.
  - **Gotcha in the reader:** it iterates `data` without a null check (`0x14097D7F0`), so every object reply must
    carry a `data` map.
- **Deploy and Destroy for gear share one state machine.** Its state names are in the exe:
  1. `WaitForValidConnection`
  2. `WaitForSave`
  3. `CreateGarrisonMemberRemoval`, which is the DELETE
  4. `WaitForGarrisonMemberRemoval`
  5. `WaitForCurrentNotifications`
  6. `WaitForNewNotifications`
  7. `AwardLoot`
  8. `RemoveNotification`
  9. `Done` or `Failed`
  - After the DELETE, the game waits for the **server to confirm** with a notification. Its header is
    `garrison_removal`, and its `data.obj` is the removed object's id (checks at `0x141C508A0` for deploy and
    `0x141C509EC` for destroy).
  - **Deploy** then rebuilds the captain from the record it already fetched, and places it in the chosen slot
    (`0x141C5132C`).
  - **Destroy** rolls the gear reward **locally from the orc's own equipment**, then grants it (`0x141C51884`).
  - Neither needs anything else from WB. Without the confirmation, both go to `Failed`, but the orc has already
    been deleted.
- **Notifications:**
  - `GET accounts/me/notifications/unread` must be a **list** of `hydra::Notification`, which has `id`, `data`,
    `server_data` (from the base model), `cmd`, `header`, `payload`, `state` and `consumed` (fromValue
    `0x14529A910`).
  - A notification without `cmd` is dropped.
  - The game's own notification manager (`0x141868A74`) keeps only `id`, `header` and `data` of each entry whose
    `consumed` is false. That's why the object id must sit in **`data`**, not `payload`.
  - The game dismisses a notification with `DELETE accounts/me/notifications/<id>` (`0x14098F5F0`). Bulk dismissal
    is `.../bulk/`.
- **Wallet:** since the July 2018 Market shutdown, the game migrates the save's Mirian into an online item
  `vc-earned`.
  - It sends `PUT profiles/<id>/inventory {modifications:[{command:"set_count", slug, count}]}`, then sets the
    save's `PC_Mirian` to 0, then reads the list back.
  - Afterwards the save's `PC_Mirian` is authoritative: the game pushes `set_count vc-earned = PC_Mirian` and
    ignores a higher wallet value.
- **Menu gating:** the Market and Garrison need `StoreAvailable` (social available, not age-restricted), Act 2 or
  later, and no active quest.
  - Assigning from the Garrison also needs `Player:HasDominationAvailable`.
- **Nemesis ids (added 2026-10-20, v0.12):** every faction member gets a string id at member+0x3D0, written only
  while it's empty, as `"<prefix>_NPC_<n>"`. The prefix is a 32-hex session GUID at analytics-manager+0xA81
  (manager = `*(*(exe+0x26FFAA8)+0x6D18)`, Ghidra base 0x140000000), and the manager only sets it when online.
  `n` is a global counter that restarts at 0 each launch. The id is assigned when the member is created or first
  reported in telemetry (the `NPCProfile` events carry it).
  - Offline the prefix stays empty, so every session hands out `_NPC_0`, `_NPC_1`... again. One long offline save
    had 359 bare ids, with `_NPC_0` on 36 captains.
  - The Garrison's reassignment check (`Faction/Contracts/Failure:ReassignmentOrders_GUID`, predicate
    `HasNPCGUID == False`) refuses a captain whose id another captain also has. Captains with a still-unique
    number pass, which made the refusals look random.
  - **Fix in the DLL:** after the game's first WinHttp request + 10 s, once the manager pointer has been stable for
    5 s and the whole 64-byte prefix area is zero, write a random 32-hex prefix. New captains get
    `<prefix>_NPC_<n>`, unique across sessions.
  - **Fix for existing saves:** ids are 1-byte-length-prefixed strings in the decrypted save (see the
    [save note](save-format-decrypt-and-collectible-quests.md)), and each id appears once per member. Rewriting
    every duplicated `_NPC_<n>` to a unique same-length string (e.g. `_A0c_<n>`) made the affected captains
    garrisonable again; the length must not change.

## Build steps
1. **Build.** Run `examples/shadow-of-war-offline-mode/build.cmd`, with `GCC=` pointing at a MinGW-w64 `gcc.exe`.
   It produces `winhttp.dll`.
2. **Install.** Close the game, then run `install.ps1 -Game "<install folder>"`. Or copy `winhttp.dll` into `x64\`
   and `OfflineMode.ini.txt` there as `OfflineMode.ini`.
3. **Check it's running.** Start the game. `x64\OfflineMode.log` should start with
   `Shadow of War Offline Mode, mode=emulate`, and WB Play should show a white dot.
4. **Open the Garrison.** It's under the Market, from Act 2. Send a dominated orc there, restart the game, and
   check the orc is still listed.
5. **To add an endpoint:** every unmodelled request is logged with its decoded body and gets 200 + `{}`. Find its
   parser with the RTTI vtable's `fromValue` (vtable slot 2), then model the reply in `responder.c`. Stay within
   the scope under Route and why: nothing that grants items or emulates the online modes.

## Verification
- **In game (the user, 2026-10-10 and 2026-10-12):**
  - Offline sign-in works, and the online button times out.
  - The Garrison opens. Orcs can be stored, listed and opened in Details, and they survive a full restart.
  - The wallet mirrors the save.
  - **Deploy** put a Garrison orc into an empty captain slot.
  - **Destroy for gear** granted a weapon (a dagger) with no error.
  - The log shows the full removal handshake for each orc: DELETE, then the notification served, then the game's
    DELETE dismissing it. No access violations.
- **Harness:** a C test harness links `responder.c` and `agb.c` and round-trips each endpoint: create, list, get
  and delete objects, the notification lifecycle, wallet commands, and re-encoding an object rebuilt from the log.
- **Crash reporter:** the DLL installs a vectored exception handler. It logs up to 20 access violations inside the
  exe, with exe-relative return addresses, and never handles them. This is how the placeholder-schema crashes were
  found.
- **Not verified:**
  - other builds, and the GOG/Epic versions;
  - Online Conquest and Vendettas with the DLL removed again;
  - more than 2 orcs in the Garrison at once;
  - Deploy into an occupied slot;
  - a `PUT objects/<type>/<id>` with a shape other than `{data}`. The game never sent one; it's logged, not
    applied.

## Gotchas
1. **The Garrison said "We have temporarily disabled the Garrison".** **Cause:** WB's remote kill switch. The
   `game-settings` broadcast's `data.store_enabled` is read, not the JSON `content`. **Fix:** serve one
   `game-settings` message with `data{store_enabled:true, garrison_size}`.
2. **"Currently updating Garrison data" forever.** **Cause:** the store isn't accessible until a storefront layout
   exists **and** both the item and catalog lists are non-empty **lists**. **Fix:** an empty storefront
   (`version 2`, `racks: []`), plus one inert placeholder in each list.
3. **The placeholder build crashed at save load** (AV inside the Hydra map iterator). **Cause:** the placeholders
   used guessed fields. **Fix:** read the real schemas from RTTI. `hydra::InventoryItem` and
   `hydra::CatalogProduct` have their `fromValue` in vtable slot 2. Also give every object reply a `data` map.
4. **Mirian dropped to 0 when the store first opened.** **Cause:** the game migrates Mirian into the online wallet
   and zeroes the save. A stand-in that answers `{}` loses it. **Fix:** a local wallet file, updated only by the
   game's own commands. Back up saves before the first run; a lost amount can only be restored in the save.
5. **The wallet still read 0 after the fix.** **Cause:** counts were sent as int32. Hydra's count reader only
   accepts int64. **Fix:** encode every integer as int64, and normalise stored objects the same way (f32 becomes
   f64).
6. **Stored orcs showed an icon but no gear, model or commands.** **Cause:** the POST was answered `{id, data:{}}`.
   **Fix:** echo the full record back, and serve it on `GET objects/user-garrison/<id>`. The game reads objects
   through the `objects/<type>/<id>` path, not `objects/<id>`.
7. **Deploy said "failed to assign", Destroy said "Data error encountered", and the orc was gone either way.**
   **Cause:** after the DELETE, the game waits for a `garrison_removal` notification, and `notifications/unread`
   returned `{}`. Replying to the DELETE with `{}` or with the full object made no difference. **Fix:** after a
   Garrison DELETE, queue a notification and serve it as a list. Drop it when the game dismisses it.
8. **The notification was fetched but never matched.** **Cause:** the game's notification manager keeps only `id`,
   `header`, `data` and `consumed`. The object id was in `payload`. **Fix:** put `data:{obj:<id>}`,
   `header:"garrison_removal"`, `cmd` and `consumed:false` on the notification.
9. **The log looks garbled around non-ASCII names** (for example "Târz"). **Cause:** the log prints decoded strings
   as raw bytes through the ANSI code page. **Fix:** map them back through cp1252 when rebuilding objects from the
   log (`tools/log_to_object.py`). That script recovered orcs lost to Gotcha 7 from the logged POST, byte for byte.
10. **Ghidra's headless `.bat` ate `=` in script arguments.** **Fix:** pass exact function entries as `e0x...`,
    with no `=`.
11. **"You cannot send this Follower to the Garrison" on some captains, apparently at random** (added 2026-10-20).
    **Cause:** duplicate offline Nemesis ids (see How the game works). It looked tied to modded tribes and to a
    roaming-captains plugin, because new test captains were created in new sessions with low, colliding numbers.
    **Fix:** v0.12's prefix + the save id rewrite. Check with the `NPCProfile` telemetry in the log: a bare
    `_NPC_<n>` that another captain also has is the culprit.
12. **The Garrison showed a red lock and the log stopped right after `WinHttpOpen`** (v0.11, 2026-10-20).
    **Cause:** v0.11 wrote the id prefix (and called `VirtualProtect`) as soon as the manager pointer existed,
    before the game's first request; that session made no online requests at all. **Fix:** v0.12 waits for the
    first request, a stable pointer and an all-zero field, and uses a plain store.

## Assets
None.

## Cost and time
Two long sessions: about 6 hours on 2026-10-10 (sign-in to Garrison storage), and about 1.5 hours on 2026-10-12
(Deploy and Destroy). Most of the time went on static analysis to find the reply schemas.

## Open questions
- **Clicking WB Play** still opens a sign-in or registration screen. It's harmless, but the cause hasn't been
  looked into.
- **Other imports.** The exe also imports WinINet and Winsock, and nothing seen so far uses them. If a later
  feature uses them, they would need the same treatment.
- **Other loaders.** It hasn't been checked whether the mod coexists with Packet Loader on builds where Packet
  Loader is stable.
- **Next use:** this is the base for injecting a creature from another game into the Nemesis system on top of the
  Goblins of War tribe framework. The local Garrison stores and moves those custom captains.
