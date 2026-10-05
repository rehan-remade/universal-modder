---
kind: game
title: 'Writing and fixing 3.3.5a addons: Lua 5.1 gaps, protected calls, the guild bank, macros and a test harness'
game: World of Warcraft
games_also: []
game_version: 'Wrath of the Lich King client 3.3.5a (build 12340, interface 30300); AdiBags, DialogUI, WeakAuras 5.22 backport, GearScoreLite'
platform: windows
engine: native
route: loader-api
tools: [Lua 5.1 / luac5.1 (in WSL), a stubbed WoW API harness, BugSack]
anti_cheat: 'none: the client''s own addon API'
status: working
agents:
- Claude Code (Opus 5.5)
humans: [RedSuper]
date: '2026-10-02'
links: ['https://wowpedia.fandom.com/wiki/World_of_Warcraft_API', 'https://www.lua.org/manual/5.1/']
tags: [addons, lua, ui, guild-bank, adibags, macros, testing, interface-30300]
---
# Writing and fixing 3.3.5a addons: Lua 5.1 gaps, protected calls, the guild bank, macros and a test harness

> Over a few weeks we wrote and patched a dozen addons for a 3.3.5a client: a loot feed, a dialogue UI fix pass, a
> guild-bank container for AdiBags (six tabs merged, cross-tab tidy), a bot-group controller, a battleground queue
> loop, GearScore colours that follow the raid phase, macro and settings migration from a modern client. Most
> bugs came from the 3.3.5a API being older than the docs people quote, and from testing outside the real client.

## Setup
- Client 3.3.5a, interface 30300. Addons in `Interface\AddOns\<Name>\` with a `.toc` whose `## Interface: 30300`.
- Offline testing: `lua5.1` in WSL with a stub of the WoW API (frames, events, a simulated clock). Syntax with
  `luac5.1 -p`. In game: BugSack for errors.

## Route and why
The client's own addon API (Lua + XML), plus a few server commands where the client API is protected.

## How the game works (what we had to learn)
**Loading**
- **A file added to a `.toc` needs a full client restart**; `/reload` re-runs only the files enumerated at launch.
  A whole debug round was lost to an addon file that had never loaded.
- SavedVariables are written on logout/reload: editing them while the game runs gets overwritten. Migrate data
  from inside the addon.
- Addon folders must match their `.toc` name (GitHub downloads add `-main`); installers must not hoist embedded
  libraries as top-level addons; check each addon's interface number (many "WotLK" downloads are later builds).

**Lua 5.1 as shipped in 3.3.5a**
- No `math.mod` (Debian's lua5.1 has it through a compat flag, so the harness must remove it), no `io`, `os`,
  `require`, `dofile`, `loadfile`, `string.gfind`.
- Unknown escape sequences are silently dropped, so `luac -p` passes a mangled path like `Interface\AddOns\…`.
- `and` binds tighter than `or`; `0` is truthy (`GetCreatureId`-style helpers return 0 when absent).
- `UnitName(unit)` returns two values (name, realm): `table.insert(t, UnitName(u))` becomes the 3-argument form.
- No PNG textures, no `MaskTexture`, no `GetItemIcon` (`GetItemInfo`'s 10th return is the icon), no `SetSize`
  (Cataclysm).

**Protected and hard-coded**
- `InteractUnit` is protected and silently does nothing for addons; `SetPartyAssignment` and `UninviteUnit` raise
  "Interface action failed because of an AddOn". Use server commands (e.g. `.group disband`).
- `SetRaidSubgroup` fails silently into a full subgroup; `SwapRaidSubgroup` works.
- Macros: 36 account + 18 character, enforced inside `Wow.exe` (`MAX_ACCOUNT_MACROS` is only a Lua constant). The
  cache format is `MACRO <slot> "<name>" <TextureName>`; **character macros use slot ids with high byte `0x01`**
  (`16777217` = character slot 1). Modern clients use `VER 3 <hex id> "<name>" "<file id>"`.
- Bags hold at most 36 slots (a client update-field limit).
- Creature GUIDs: the entry is hex digits 5–10 (24 bits); reading only four digits truncates big entries.

**Guild bank**
- 6 tabs × 98 slots; the client holds all six tabs once queried. `SetCurrentGuildBankTab(tab)` must precede
  `QueryGuildBankTab(tab)` (the reply is filed under the current tab).
- The server's swap takes both tabs, both slots and a count in one packet: cross-tab merges are one call.
- `GUILDBANKBAGSLOTS_CHANGED` fires **synchronously** inside `SplitGuildBankItem` / `PickupGuildBankItem`: a handler
  that acts inline recurses until a C stack overflow. Step on a timer instead.

**AdiBags internals (when adding a container)**
- Profile tables are keyed by the bag's display name with no wildcard; a missing `positions[name]` means the frame
  is never anchored and renders nothing, with no error.
- Adding slots one by one is quadratic (every add walks every slot); batch the work while hidden.
- A tooltip owner without `UpdateTooltip` loses its tooltip a frame later (`self.UpdateTooltip = self.OnEnter`).

**Server side of chat links**
- AzerothCore validates hyperlink colours by default: a quest link whose colour isn't one of the five quest
  difficulty colours makes the server drop the whole chat message silently.

## Build steps
1. Write the addon with the stub harness first (events, timers, the API calls you use), including the failure you
   expect (re-entrancy, a respec race, a full subgroup).
2. `luac5.1 -p`, then a harness run with Lua-5.1-as-shipped (compat functions removed).
3. Install with the client closed; full restart if the `.toc` changed.

## Verification
- Harness tests for every addon change (the guild-bank tidy reproduces the re-entrancy overflow and proves the
  fix); BugSack clean in game; the human's own checks in game.
- Profiling in game with `debugprofilestop()` around suspected handlers when "it still lags" (the human's numbers
  isolated `frame:Show` → `OnShow`).

## Gotchas
1. **"The fix doesn't work."** **Cause:** the new file in the `.toc` never loaded. **Fix:** full client restart; a load
   banner in each addon.
2. **`math.mod` nil in game, fine in tests.** **Cause:** the harness Lua had the compat layer. **Fix:** remove compat
   functions from the harness.
3. **Icon paths came out mangled.** **Cause:** backslashes eaten by a shell heredoc while generating Lua, and Lua 5.1
   dropped the unknown escapes silently. **Fix:** write files with an editor; build backslashes with `chr(92)`.
4. **Guild bank window opened then closed itself.** **Cause:** letting Blizzard's guild bank UI load and hooking its
   hide. **Fix:** stub the Blizzard UI's loader, as Bagnon does.
5. **No guild bank data ever arrived.** **Cause:** querying a tab without making it current. **Fix:** set the current
   tab first.
6. **C stack overflow during a tidy.** **Cause:** the synchronous bag-slots event. **Fix:** timer-only stepping with a
   busy flag and a no-progress check.
7. **Character macros invisible after migration.** **Cause:** written as slots 1–8. **Fix:** high byte `0x01`.
8. **Settings "copied" but reset on login.** **Cause:** the addon saw a newer config version stamp and reset.
   **Fix:** rewrite the version stamp to the installed addon's version; check that the addon accepted the data.
9. **Party loot showed up as the player's.** **Cause:** an unanchored fallback pattern on loot messages. **Fix:**
   match only the player's own message forms.

## Open questions
- None outstanding for these addons.
