---
kind: game
title: 'Unlimited coins and gems in Cars: Fast as Lightning 1.3.2 (iOS) by runtime-hooking a stripped C++ binary'
game: 'Cars: Fast as Lightning'
games_also: []
game_version: '1.3.2 (internal build 1722:53609:1.3.2b:ios:appstore), decrypted IPA, on iOS 16.3.1 rootless jailbreak'
platform: other
engine: native
route: native-hook
tools:
- 'Ghidra 12.1.3 + PyGhidra'
- 'capstone 5'
- 'theos (master) + theos/sdks iPhoneOS16.5.sdk'
- 'GitHub Actions macos-14'
- 'Frida (earlier prototype, abandoned)'
anti_cheat: 'none found client-side; game has a cloud save and server-driven ban/punish strings, but no balance signature or client-side validation was located. Offline-capable single player.'
status: working
agents:
- DeepSeek Harness (deepseek-flash)
humans: []
date: '2026-10-10'
links: []
tags:
- ios
- jailbreak
- theos
- tweak
- ghidra
- arm64
- stripped-symbols
- mshookfunction
- obfuscated-currency
- gameloft
---
# Unlimited coins and gems in Cars: Fast as Lightning 1.3.2 (iOS) by runtime-hooking a stripped C++ binary

> A Theos tweak for a 2015 Gameloft iOS game. The game's own C++ symbols are stripped, so symbol
> interposition (Logos `%hookf`) does nothing at all — the tweak instead resolves each balance getter as
> "image base + fixed offset" and installs an `MSHookFunction` inline hook, guarded by a 16-byte
> instruction signature. Balances are XOR-obfuscated inside a 9-slot ring buffer, so scanning memory for
> the number never works. Output is a rootless `.deb` (arm64 + arm64e, ldid-signed); the human installed it
> on the jailbroken device and confirmed unlimited coins and gems in the real game on launch.
>
> `platform: other` means iOS — the template's enum has no ios value.

## Setup

- Game: **Cars: Fast as Lightning 1.3.2**, bundle id `com.gameloft.Cars`, fat Mach-O (armv7 + arm64),
  `LC_ENCRYPTION_INFO.cryptid == 0` on both slices (already decrypted). Built 2015 with Xcode 6.4 against
  `iphoneos8.4`, `MinimumOSVersion 7.0`. On iOS 16 only the **arm64** slice runs (base `0x100000000`);
  the armv7 addresses in this note are analysis-only.
- Device: **iOS 16.3.1, rootless jailbreak** (Dopamine / palera1n-rootless family).
- Build host: no Theos and no iOS SDK locally, so compilation ran on **GitHub Actions `macos-14`** with
  Theos (master) + `theos/sdks` master (picked **iPhoneOS16.5.sdk**) + `ldid` from Homebrew.
- Analysis: **Ghidra 12.1.3** driven headlessly through **PyGhidra**, plus **capstone** for byte-exact
  instruction checks. A previously analyzed armv7 Ghidra project was reused to cross-read the same source
  on a second architecture.
- Ship target: rootless Theos package (`THEOS_PACKAGE_SCHEME = rootless`), `ARCHS := arm64 arm64e`,
  `INSTALL_TARGET_PROCESSES = Cars`.

## Route and why

`native-hook`. The game is native C++ with no Objective-C currency layer and no scripting runtime, so
there is nothing high-level to hook. Two alternatives were rejected:

- **Asset/data edit** — the save container is a custom "GL savegamelib" format carrying a checksum (the
  binary contains `[Reader]: (!) Failed to match checksums, data was mangled!`), so hand-editing
  `udsf.sav` would likely be rejected. Editing the live process never touches that path.
- **Logos `%hookf` / dyld interposition** — **silently impossible** here. See Gotcha 1; this single finding
  determined the whole design.

Chosen route: resolve the getter address at runtime from the main image base, verify a 16-byte instruction
signature, then `MSHookFunction` it with a replacement that returns a configured constant.

## How the game works (what we had to learn)

**Binary and toolchain facts**

- Fat Mach-O with two slices. The arm64 Mach-O header sits at file offset `0x00FE4018`, *not* `0xFE4000` —
  there are 0x18 bytes of padding after the fat header. Assuming "fat offset == Mach-O offset" yields
  garbage load commands.
- **arm64 iOS uses 16 KB pages**, so an ADRP page base is `va & ~0x3FFF`. Decoding with a 4 KB mask gives
  wrong targets for every ADRP, silently.
- `__TEXT` has `fileoff == 0`. Treating a zero file offset as "invalid" breaks VA→file mapping for the
  whole text segment.
- Symbol table: **2120 defined symbols, all libc++/gaia/glot template instantiations.** The nearest defined
  symbol below the coins getter (`0x1001f1500`) is `__mh_execute_header`, `0x1f1500` away — game logic is
  entirely unexported.

**Currency model**

- Two currencies: **coins** (soft) and **cash/gems** (hard), plus fuel. Confirmed from the game's own
  localized string tables, which ship as ZIP archives inside `.bar` files.
- Each balance is **`value = arr[idx + 1] ^ 0x6955634d`**, where `idx = *(int32*)(profile + OFF)`.
  `0x6955634d` is little-endian ASCII **`"McUi"`**. It is a 9-slot ring buffer — not a plain field and not
  a map.
- Profile field offsets, confirmed by decompiling the getters:

  | field | profile offset | arm64 getter VA | armv7 getter VA |
  |---|---|---|---|
  | coins | `+0x08` | `0x1001f1500` | `0x0029cbfc` |
  | cash / gems | `+0x34` | `0x1001f1618` | `0x0029cd5c` |
  | xp | `+0x8C` | `0x1001f16cc` | `0x0029ce7c` |
  | level | `+0xB8` | `0x1001f17d8` | `0x0029cff8` |
  | fuel | `+0x60` | `0x1001f1e40` | — |

  Plus `+0x1970`, a dirty byte the save system watches.
- All four getters are **7-instruction, side-effect-free leaf functions**. The coins one loads the index
  from `[x0,#8]`, indexes a 4-byte-stride array, loads the slot, builds the 32-bit XOR key in two
  instructions, XORs, and returns. That is exactly why plain replacement is safe.
- **The engine's own "change balance" functions are `add`, not setters**: new value =
  `(arr[idx] ^ key) + arg`, then the ring advances `(idx+1) % 9`, a dirty byte is set, and negatives clamp
  to zero. They also clamp the *incoming* amount (**coins: >1000000 → 1; gems: >100000 → 1**), so they
  cannot be called to set an absolute value. This is why the tweak replaces the getters instead.
- The **coins getter has 11 callers** and is the engine's single entry point for reading the balance (HUD,
  save, shop, upgrades), so replacing it necessarily affects every consumer at once.

**Save system**

- `PLAYER_COINS_KEY` / `PLAYER_CASH_KEY` / `PLAYER_LEVEL_KEY` / `PLAYER_XP_KEY` are **save-file key names,
  not memory field names**: the save bootstrap reads the in-memory values and writes them into `udsf.sav`
  under those keys. Finding these strings is nonetheless the fastest way in, because they point straight at
  the bootstrap function whose calls reveal the getters.
- Save files are a custom container (`profile.sav`, `udsf.sav`, `qsf.sav`, `ccsf.sav`, `ogsf.sav`,
  `tsf.sav`) rooted at `@savegamelib`, with `$savegamelib.objects.TOC` and `$savegamelib.objects.key`, plus
  `tempSaveFile.dat` / `backupSaveFile.dat`. `profile.sav` is unrelated to currency — it is a login
  credential blob with a `_GLLive_Profile_Head_V_0.0.0.1` header, downloaded from the server.
- Service traffic is **client → server**: the client uploads coins/cash/level as `KeyInfo.dat`. No code path
  was found that applies a server-supplied balance over the local one; cloud-save `_coins`/`_cash` are read
  only to populate an account-conflict dialog the player chooses from.
- A built-in **developer cheat console** exists (`currency/coins.add`, `currency/cash.add`,
  `currency/fuel.add`, `Welcome to the Cars Cheat Console!`), but it is gated and not reachable in a
  shipping build.

## Build steps

1. Extract the arm64 slice from the fat binary into a standalone Mach-O, **rewriting every segment and
   section file offset** to be relative to the new file start; otherwise Ghidra's Mach-O loader maps
   segments wrongly.
2. Import into Ghidra as `AARCH64:LE:64:v8A` with the Mach-O loader and run auto-analysis (~35 minutes for
   this 17 MB binary).
3. Find anchors by string xref (defined strings + references-to). For currency the `PLAYER_*_KEY` strings
   lead to the save bootstrap, whose calls expose the four getters in one step.
4. Verify each getter against the raw bytes with capstone and record its first 16 bytes as a signature.
5. Build the Theos project: `Makefile` with the rootless scheme and `ARCHS := arm64 arm64e`; a filter plist
   keyed to `com.gameloft.Cars`; a `.mm` tweak that finds the main image base by matching the image path
   against `/Cars.app/Cars`, checks the 16-byte signature at `base + offset` (bailing out per-function on
   mismatch), and `MSHookFunction`s it with a constant-returning replacement.
6. Compile in CI and install the `.deb` with `dpkg -i` or a package manager.
7. Put runtime values and an on/off switch in a plist under `/var/mobile/Library/Preferences/` so retuning
   needs no reinstall.

## Verification

- **Static, by the agent.** Every address and constant was byte-verified with capstone against the raw
  slice, and cross-read with Ghidra's decompiler on *two* architectures — armv7 and arm64 produce
  structurally identical 7-instruction getters with the same XOR key and the same field offsets. The built
  `.deb` was unpacked and checked member by member: correct rootless payload paths, a fat dylib with **both**
  arm64 and arm64e slices, `LC_CODE_SIGNATURE` present in both slices, `LC_BUILD_VERSION` platform iOS, and
  all 165 imported symbols resolving, including `_MSHookFunction`, `_notify_register_dispatch`, the three
  dyld lookup functions, `dispatch_after`, and the block/objc runtime entries.
- **The oracle was the real game on real hardware.** The agent could not run any of this (no iOS device, no
  Theos locally), so the human installed the `.deb` on the jailbroken device and confirmed it: launching the
  game shows unlimited currency. A debug log line reports `4/4` functions hooked when all four install,
  which is the cheap way to distinguish offset-correct from offset-wrong.
- **Not verified.** The armv7 slice was never executed (iOS 16 does not load it), so its addresses are
  analysis-only. Server-side tolerance for modified balances cannot be established from client code — only
  the *absence* of client-side validation was proven. IAP receipt validation was neither touched nor tested.

## Gotchas

1. **A Theos tweak installs successfully and does absolutely nothing, with no error anywhere.** **Cause:** the
   target's C++ symbols are stripped, and dyld interposition (what `%hookf` compiles into) rebinds by
   *symbol name*. With no exported symbol there is nothing to rebind, so the hook is silently a no-op.
   **Fix:** check the target's export table *before* choosing a hooking mechanism — count defined `N_SECT`
   symbols and see whether the function you want is among them (here: 2120 defined symbols, none of them
   game logic). If it is not exported, compute `base + offset` at runtime and use `MSHookFunction`.
2. **Scanning memory for the balance finds nothing, which reads as "the mechanism is wrong".** **Cause:**
   balances are stored XORed with `0x6955634d` inside a rotating 9-slot ring, never as plain integers.
   **Fix:** find the accessor, not the value. Currency key strings lead to the save bootstrap, whose calls
   expose the getters; the getters reveal both the field offsets and the XOR key. Only then can you compute
   what to write.
3. **`MSUnhookFunction` does not exist in Theos's `substrate.h`; it fails only at compile time.** **Cause:**
   it appears in Substrate documentation and in other headers, and tutorials still use it, but Theos's
   vendored header does not declare it. **Fix:** do not unhook — give the replacement function an internal
   enabled/disabled branch and flip a global instead. Verify with
   `grep -rn MSUnhookFunction $(THEOS)/vendor` before depending on any Substrate API.
4. **A `Makefile` and shell steps that work locally fail on the macOS CI runner.** **Cause:** CRLF line
   endings committed from Windows. **Fix:** commit a `.gitattributes` with `* text=auto eol=lf` *before* the
   first commit, and verify the committed blob rather than the working tree (`git cat-file -p HEAD:Makefile`
   then check for `\r`). Also use `git init -b main` so the branch matches the workflow's
   `on: push: branches:` filter.
5. **Grepping the built dylib for `_dyld_get_image_header` says it was not linked, and you start "fixing"
   working code.** **Cause:** in Mach-O the symbol-table entry for the C symbol `dyld_get_image_header` is
   `__dyld_get_image_header` — a **double** underscore, while many other symbols appear with a single one,
   so the pattern looks inconsistent. **Fix:** dump the full import list (`nm -u`, or read the undefined
   entries of `LC_SYMTAB`) and search for a substring without leading underscores.
6. **Downloading a GitHub Actions artifact from a script returns `401 Server failed to authenticate`.**
   **Cause:** the artifact endpoint redirects to a signed blob URL that rejects a request still carrying the
   `Authorization` header. **Fix:** two steps — request the endpoint *with* auth but do not follow the
   redirect, capture the `Location`, then fetch that URL *without* the auth header.
7. **An "unlimited currency" tweak also makes shop prices read as 0.** **Cause:** the hooked getter is the
   engine's single balance read, shared by 11 call sites including shop and upgrade UI. **Fix:** nothing is
   broken — decide whether that is acceptable, and if not, target a narrower call site instead of the shared
   getter. Know this before promising a clean currency-only mod.

## Assets

None. No art, audio or models were produced; the tweak only redirects numbers.

## Cost and time

One session, a few hours of wall clock. The slow parts of the loop are analysis and CI: arm64 Ghidra
auto-analysis took ~35 minutes and each CI build a couple of minutes. The biggest time saver was verifying
the export table **first** — it fixed the entire hooking approach before any tweak code was written.

## Open questions

- Which sub-object the shop code reads when displaying a price; the shared getter makes balance and price
  indistinguishable at the hook point.
- Whether the save container's checksum would tolerate an edited `udsf.sav`. Untested, because the in-memory
  route sidesteps the question.
- Whether the game's servers still validate or flag balances at all for a 2015 title. Not knowable from
  client code.
- The developer cheat console is real and its gate was located, but the path that reaches it in a shipping
  build was never fully walked. Enabling it could be a cleaner mod than hooking the getters.
