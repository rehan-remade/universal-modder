---
kind: game
title: In-game ImGui trainer and save-queue item delivery for LET IT DIE Offline Edition (UE3)
game: LET IT DIE
games_also: []
game_version: 'LET IT DIE Offline Edition 5.0.1 (Steam, Offline Key DLC), Windows x64 (BrgGame-Steam.exe, PE timestamp 0x6A94FD6E), D3D9 renderer'
platform: windows
engine: unreal
route: native-hook
tools: ["MSVC 2026 Build Tools (cl, x64)", "MinHook", "Dear ImGui 1.91.5 (DX9 + Win32 backends)", "Ghidra 12.1.4 (headless, Java scripts)", "UELib 1.13.7 + lzo.net (custom C# dumper)", "Python 3.14 (sqlite3, zlib, Pillow)"]
anti_cheat: "none: the online service ended on 2026-09-01 and the Offline Edition has no servers; only in-exe '[cheat]' clamps on part durability/ammo at load (single-player, offline only)"
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-11'
links: ["https://github.com/TsudaKageyu/minhook", "https://github.com/ocornut/imgui", "https://github.com/EliotVU/Unreal-Library"]
tags: [overlay, imgui, d3d9, dinput8-proxy, ue3, processevent, processinternal, save-editing, sqlite, cheats, item-spawner, icons]
---
# In-game ImGui trainer and save-queue item delivery for LET IT DIE Offline Edition (UE3)

> A `dinput8.dll` proxy that hooks D3D9 `EndScene` and draws an ImGui mod menu inside LET IT DIE Offline Edition, the
> paid single-player release that replaced the online game (custom Unreal Engine 3, "BrgEngine"). It has infinite
> durability, ammo and stamina (done by skipping specific UnrealScript functions in `ProcessInternal`), currency
> buttons (calling script through `ProcessEvent`), an icon item picker, and permanent item and fighter-stat
> delivery. Delivery works through a save-edit queue that a helper process applies after the game exits. All of it
> is verified in the real game (play-tested 2026-10-11), except that one delivered part, Demon Gun 1, never shows
> up in the locker (Gotcha 17).

## Setup
- Game: LET IT DIE **Offline Edition 5.0.1**, Windows 11 x64.
  - **What "offline" means here.** GungHo ended LET IT DIE's online service on 2026-09-01 and released the Offline
    Edition the same day: the base game plus the $19.99 "Offline Key" DLC (Steam and PS4). It has no servers and no
    microtransactions. Death Metals (the paid currency) are gone, and Kill Coins, earned in game, replaced them.
  - That is why a trainer and save edits are fine here: they only touch your own local save and process. Nothing
    in this note touches the Offline Key ownership check; keep it that way. Don't carry this over to a game that
    still sells currency or items, or still talks to a server.
  - `BrgGame\Config\BrgEngine.ini` has `AllowD3D11=False`, so the live renderer is **D3D9**. Hook `EndScene` (vtable 42)
    and `Reset` (16).
- Toolchain:
  - **Build:** MSVC Build Tools (x64, `/MT`), MinHook and Dear ImGui 1.91.5.
  - **Static analysis:** Ghidra 12.1.4 running headless on JDK 21, with the scripts in Java. Ghidra 12 made PyGhidra
    the default Python; Jython scripts still run with a `# @runtime Jython` header.
  - **Save tools:** Python 3.14.
- **Ghidra import crash:** importing `BrgGame-Steam.exe` crashes in the exception-directory parser. Import a copy with
  PE data directory #3 zeroed instead.
- **Script dump:** UnrealScript bytecode came from `BrgGame.u` via UELib, after decompressing the package yourself (see
  Gotchas). The dump is kept outside the mod repo and is never shared.

## Route and why
- **Native hook (proxy DLL + MinHook)**, because there is no community loader.
  - UE4SS and similar tools don't apply: this is UE3, x64, with a heavily customised engine.
  - Cheat Engine tables don't cover item spawning or a menu.
- **Data-only first.** Editing `masters.db` (SQLite) and the save was tried first. It does change prices and the stats of
  *newly created* items. It cannot stop durability or ammo from draining, and owned items keep their saved values.
- **Live item spawning** through the game's debug exec `BrgGameInfo.DebugPartEquip` only works as a temporary preview
  (see Gotchas). Permanent items therefore go through **save editing with the game closed**, automated by a queue.

## How the game works (what we had to learn)
- **Offline edition = bundled backend.**
  - The save `Savedata\<steamid>.sav` is a JSON copy of what used to be server data.
  - Master data is a local SQLite file `BrgGame\Content\masters.db`. The exe opens it by bare name.
  - There is also a native in-memory save database that mirrors parts of the JSON.
- **Save format:**
  - Header: `"BRG\0"`, `u32 version` (2), `u32 total_uncompressed`, `"ZLIB"`.
  - Then chunks of `[u32 usize][u32 csize][zlib]`, which concatenate into UTF-8 JSON.
  - Then a 4-byte zero terminator.
  - **No checksum or signature.** It round-trips byte-exact apart from float formatting (`0.0000` vs `0.0`), which the
    game accepts.
- **Save JSON landmarks:**
  - `soul.free_money` / `soul.spirit`: Kill Coins in the Buffalo Bank and SPLithium in the SPLithium Tank. Their caps
    come from `master_safe_level.limit` / `master_spirit_tank_level.limit` for the current `soul.safe_level` /
    `spirit_tank_level` (500,000 at level 1). What a fighter carries is in `soul.chr.chrs[...].money/spirit`.
  - `soul.bloodnium_point` (account Bloodnium, max 999,999) and `soul.tdm_point` (TDM points).
  - `part.pts["1"]`: owned parts. Each record is
    `{uid, eid(GUID), gettime, owner USER|COIN_LOCKER, created, modified, ptid, rest, spare, grade, dur, lvl}`.
  - `item.items`: materials and consumables, `{eid, gettime, itemid, owner}`.
  - **Coin Locker = `soul.cl`:** 30 slots `{slot, type, eid}`, with type 0 = part, 3 = item, -1 = empty.
    `gameflg.cl` is unrelated.
  - Fighters: stat levels in `bodyuser["1"][i]` (`lvl, hp, str, dex, vit, stm, luk`). Level = 1 + stat points spent.
    XP pool and HP in `soul.chr.chrs["1"][i]` (`gain_exp, start_exp, total_exp, rest_exp, hp, type, grade, limit_break`).
- **masters.db:**
  - `master_part`: per-part `dur`, `dur_hit/shoot/rage` (drain), `capacity/spare` (ammo), and `lvllmttp/lvllmt`
    (equip requirement).
  - `master_item`: `itemtype ITTP_MATERIAL` covers the 106 R&D materials.
  - `master_body_detail.param_lv_max` is the per-stat cap (5 for grade-1 BAL fighters).
    `master_bodylvl_status_value` maps stat level to HP and other values.
  - `master_text (sct, id, lang, txt)` holds names. Join using the `sct.id` split of the `name` column, not the id alone.
- **Engine internals (RVAs, ASLR on):**
  - `UObject::ProcessEvent` 0x10E770, `UObject::ProcessInternal` 0x10EC70, `UObject::CallFunction` 0x103610,
    `FString::operator=` 0x19850.
  - `GNames` 0x2949C98. Entries hold the name at +0x14 and flags at +0x08 (bit 0 = wide).
  - `GObjects` is found at runtime by scanning writable sections for a `TArray` whose entries' `Index` (+0x38) equals
    their position.
- **Object layouts (x64):**
  - UObject: Index +0x38, Outer +0x40, Name +0x48, Class +0x50.
  - UField::Next +0x60, UStruct::Children +0x80.
  - UFunction: PropertiesSize +0x88, FunctionFlags +0xD0, iNative +0xD4, Func +0xF0.
  - UProperty: PropertyFlags +0x70, Offset +0x94.
  - FFrame: Node +0x14, Object +0x1C, Code +0x24, Locals +0x2C.
- **Script dispatch:** `CallFunction` calls `ProcessInternal` **directly** for script functions. Swapping
  `UFunction::Func` therefore misses script-to-script calls. Hooking `ProcessInternal` and comparing `FFrame.Node` catches
  every script function body.
- **Drain functions** (all void and decrement-only):
  - Durability: `BrgCommonPawn_CustomChara.WeaponDurabilityDown`, `WeaponShotDurabilityDown` and `ArmorDurabilityDown`.
    They run on the per-character helper object, so the owner is its `mPawn` property.
  - Ammo: `BrgWeapon_*.BulletConsumption` (9 overrides). The owner is `BrgWeapon_Base.mOwnerPawn`.
  - Stamina: `BrgPawn_CustomCharaPlayer.StaminaConsumption`.
  - Repairs use the separate `PartDurabilityRecovery*` functions.
- **Currency:** `BrgUserData` natives through ProcessEvent: `Get/AddMoney` and `Get/AddSpirit(..., cindex=-1)`
  (carried by the current fighter), `Get/SetSafeMoney` + `GetSafeLimit` (Bank), `Get/SetSafeSpirit` +
  `GetSpiritTankLimit` (Tank), `Get/SetUserBloodnium` + `GetBloodniumLimit`, `Get/SetTdmPoint`. Read, clamp to the
  game's limit (never lowering a balance already above it), then set. Bloodnium needs one more step (see Gotchas).
  The live objects are `PlayerController.WorldInfo.Game` (the GameInfo) and its `.mUserData`.
- **Icons:**
  - Every item has its own package `CookedPCConsole\UI_Icon_<id>_SF.upk`, holding one inline Texture2D (108x132, mostly
    A8R8G8B8).
  - The game has **no icon fallback**: a part without its own package has no icon in game.
- **Packages:** the cooked `.upk` files are fully LZO-compressed. Bulk-data headers use **64-bit size/offset** (24-byte
  header), which stock UE Viewer (umodel) can't read.

## Build steps
1. Build `dinput8.dll` with the exports `DirectInput8Create`, `DllCanUnloadNow`, `DllGetClassObject`, `DllRegisterServer`
   and `DllUnregisterServer`, each forwarding to `System32\dinput8.dll`. Place it next to `BrgGame-Steam.exe`
   (`Binaries\Win64`).
2. Worker thread:
   - Make a throwaway D3D9 device to read the vtable, then MinHook `EndScene`/`Reset`.
   - MinHook `ProcessEvent` and `ProcessInternal`.
   - Hook `IDirectInputDevice8::GetDeviceState`/`GetDeviceData` (vtable 9/10, both the A and W interfaces), so the game
     gets blank mouse/keyboard input while the menu is open.
3. Queue game-thread work, and run it from inside `ProcessEvent` only when the event is `PlayerTick`.
   - Resolve targets in one pass by FName index.
   - Read property offsets from the UProperty objects themselves (`Offset` at +0x94).
4. **Cheats:** in the `ProcessInternal` hook, compare `FFrame.Node` against the resolved drain functions. If the owner is
   the local `BrgPawn_CustomCharaPlayer`, return without running the body.
5. **Permanent items and stats:**
   - The overlay appends lines to `lid_mod\save_queue.txt`.
   - At launch the DLL starts a detached `pythonw` helper that waits on the game PID. After exit it takes a lock file,
     backs up the save and applies the queue (new locker records shaped exactly like the game's own, or a stat max).
   - It writes atomically (tmp → decode-verify → fsync → `os.replace`) and leaves a result file for the next launch.
6. **Item icons:** extract the `UI_Icon_*` textures with a custom UELib-based exporter (LZO + 64-bit bulk data + DXT
   decode). Then build a 64 px atlas plus a TSV index, which the overlay loads with WIC into a managed-pool D3D9 texture.

## Verification
- **Oracles used:**
  - Screenshots of the live overlay.
  - The game's own `BrgGame\Logs\Launch.log`. Engine asserts are logged there, e.g. `body_lvl distribute failed! ...`.
  - Windows Application event log entries 1000/1001 (exception code 0x1 in KERNELBASE = engine `appError`).
  - Decoding the save before and after each change.
  - A file-based RPC in the DLL (command/result text files) to drive scans and calls from the agent.
- **Verified in game:**
  - The overlay and Insert toggle.
  - Currency adds through the `BrgUserData` natives.
  - The live `DebugPartEquip` preview.
  - Locker delivery of six gear parts through the queue (shown in the locker after relaunch).
  - Fighter stat max (level 1 → 25).
  - Recovery from a launch crash caused by a stale RPC command.
  - Play-tested 2026-10-11: the `ProcessInternal` cheats in their final form (durability, ammo, stamina), input
    blocking while the menu is open, and R&D material delivery to the Coin Locker.
- **Also tested on a scratch copy of the save:** the queue helper, including the lock file, stale-lock takeover,
  structured retry, one bad entry not blocking the rest, and material (`item`) delivery.

## Gotchas
1. **Edited `masters.db` but nothing changed in game.** **Cause:** owned items keep the values stored in the save; the DB
   only seeds newly created items. Drain also has a flat `MaintenanceValue` term on top of `dur_hit`, and an exe check
   (`[cheat]part dur/rest/spare over!`) clamps saved values to the DB maximum on load. **Fix:** skip the drain script
   functions live instead; DB edits only for prices and new items.
2. **Live "add XP" crashed the stat screen** (`body_lvl distribute failed! ... exp=14, nec_exp=138`, then an assert).
   **Cause:** `AddExp` raised the script-side value only; the native stat-distribute check uses the saved XP pool. The GM
   tool natives (`DebugGmTool*_NT`) are compiled-out stubs in this build. **Fix:** edit stat levels in the save
   (`bodyuser`) with the game closed; level = 1 + points spent, capped by `param_lv_max`.
3. **Spawned item vanished on hand switch or reload.** **Cause:** `DebugPartEquip` mints a debug entity id (empty or
   leading `-`), which the save code skips. Forcing a real GUID made it persist briefly, but the game then crashed going up
   the tower: an integrity pass looks the part up in the native save DB and null-derefs because it was never registered.
   **Fix:** treat live spawn as a preview only; deliver permanent items by save injection.
4. **Item injected with `owner: COIN_LOCKER` didn't appear.** **Cause:** the locker also needs a `soul.cl` slot entry
   (type 0 part / 3 item) pointing at the `eid`. **Fix:** fill the first `type -1` slot.
5. **Hooking `UFunction::Func` didn't catch script calls.** **Cause:** `CallFunction` calls `ProcessInternal` directly
   for non-native functions. **Fix:** hook `ProcessInternal` and match `FFrame.Node`.
6. **Durability hook never fired** (caught in code review). **Cause:** the drain functions run on the
   `BrgCommonPawn_CustomChara` helper object, not the pawn, so a class check on `this` never matched the player. **Fix:**
   follow the helper's `mPawn` property; for weapons, `mOwnerPawn`.
7. **Game wouldn't launch after an update.** **Cause:** a leftover RPC command file was executed before the module base
   was known. **Fix:** ignore any command already present at startup, and initialise the base lazily.
8. **UELib saw 0 exports.** **Cause:** the cooked packages are LZO-compressed as a whole. **Fix:** decompress first,
   using the chunk table in the summary (this build reports engine version 9953, cooker version 135).
9. **umodel fails on every Texture2D ("Serializing behind stopper").** **Cause:** bulk-data headers are 24 bytes (flags,
   count, i64 size, i64 offset). **Fix:** a custom exporter.
10. **Mouse invisible in the overlay.** **Cause:** the game hides the OS cursor, and `SetCursor` from the render thread
    doesn't apply. **Fix:** `io.MouseDrawCursor = true` plus `ImGuiConfigFlags_NoMouseCursorChange`.
11. **Mouse still turned the camera with the menu open.** **Cause:** the game reads input through DirectInput, not
    window messages. Counters in the hooks showed it uses **buffered** `GetDeviceData` only (about 100k calls, zero
    `GetDeviceState`, zero `SetCursorPos`). A first filter that kept "releases" by offset (`dwOfs >= DIMOFS_BUTTON0`)
    let mouse motion through, because UE3 sets its own mouse data format whose axis offsets are not the standard
    `DIMOFS_*`. **Fix:** classify each device once with `GetDeviceInfo` (vtable 15; mouse/keyboard only, never
    joysticks, whose zeroed axes read as full deflection). While the menu is open, keep only buffered events whose
    value says "released": `dwData == 0` for the mouse, `(dwData & 0x80) == 0` for the keyboard. Nothing stays stuck
    down after the menu closes.
12. **Threading hazards** (code review). `EndScene` runs on UE3's render thread, not the window thread:
    - ImGui input must be queued from the WndProc. Capture Ctrl/Shift/Alt there, because `GetKeyState` is per-thread.
    - `SetWindowPos` for borderless must run on a separate worker thread; on the render thread it can deadlock against
      the game thread's `WM_SIZE` handler.
13. **Script-call parameter buffers.** `ProcessEvent` copies `ParmsSize` bytes in *and back out*, so use generous zeroed
    buffers. String parameters must be engine-allocated (`FString::operator=`), because script may reassign them
    (`DebugPartEquip` does) and would then free a caller-owned buffer.
14. **`DebugPartEquip` side effects.** It sets `GameInfo.mbDeadInfoOutputCancel` (a debug flag affecting death
    bookkeeping), adds to the Death Bag, and treats unknown slot names as Head ("All" wipes the inventory). **Fix:**
    whitelist the slot names and restore the flag's DWORD after the call.
15. **Adding Bloodnium, then levelling up, crashed** (`body_lvl distribute failed! ... bloodnium=0,
    nec_bloodnium=13`). **Cause:** the stat screen shows `GetUserBloodnium() + GetBloodnium()` from `BrgUserData`, but
    the native stat-distribute check (`FUN_141366480` → `FUN_14133f7c0`) takes its pool from the native save-store soul
    record (static object at `DAT_14f89ef80`, Bloodnium at +0xB4) plus the current chara record (+0x5C), and spends
    from those. `SetUserBloodnium` updates only the script-side copy, so the UI allowed an upgrade the native check
    rejected with an assert. Adding to the per-fighter pool through `AddBloodnium(cindex)` has the same problem.
    **Fix:** after the `BrgUserData` add, also write the new total into soul+0xB4. Verify first: the right exe build
    (PE timestamp), the field equal to what the game reports, and the neighbouring replica cap (+0xB8) being -1 or not
    below it. Undo the UI-side add if the native write fails. Same lesson as Gotcha 2: anything spent through a native
    check must be written to the native store.
16. **Death Metals.** The Offline Edition replaced them with Kill Coins, so `Get/SetMedal` still exists but does nothing
    useful; leave it out.
17. **Demon Gun 1 (`PT_ARM_WP017_0A1`) injected into the locker never showed** while GLIDER 2 (`PT_ARM_WP025_0K3`) did.
    Both have no icon package. Unresolved; see Open questions.

## Assets
None generated. Item icons are extracted at build time from the user's own install into a local atlas (64 px cells,
40 per row) and a TSV index. They are never committed or redistributed.

## Cost and time
One long session (about a day of wall-clock), including Ghidra/UELib tooling setup and two automated code-review passes
(30 findings, all addressed).

## Open questions
- Why some injected locker parts (`PT_ARM_WP017_0A1`) don't display. Candidates: no `UI_Icon_` package, or a native
  filter on `master_part.platform`.
- Where the native save-DB insert for parts lives. Finding it would make live spawning permanent.
- Whether `BeginGunBulletConsumptionDisable` (a native flag) is a cleaner infinite-ammo route.
- R&D blueprints (`ITTP_RMAP`, about 1,900 entries) are not in the picker yet.
