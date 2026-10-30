---
kind: game
title: "Visible Arsenal: all six equipped weapons shown on the character, through native cosmetic model parts"
game: "Dark Souls II: Scholar of the First Sin"
games_also: []
game_version: "Steam SotFS x64; tested EXE SHA-256 0045931B8914504531B7864A9488D396DC50CBAF524964016E1D69C3D1173131; displayed version not recovered"
platform: windows
engine: fromsoft
route: native-hook
tools: ["Mod Engine (Katalash, dinput8.dll)", "llvm-mingw-20261006-ucrt-x86_64", "clang 23.1.3", "C++20", ".NET 8 diagnostic tools", "Smithbox parameter definitions", "DS2AnimToolset"]
anti_cheat: "no client anti-cheat, but the game has online play: offline only, with Mod Engine blockNetworkAccess=1 on for every run; nothing tested online"
status: in-progress
agents: ["Codex (GPT-6)"]
humans: ["jkjkj2805"]
date: 2026-10-13
links: ["https://www.nexusmods.com/darksouls2/mods/978", "https://www.nexusmods.com/darksouls2/mods/1146", "https://github.com/vawser/Smithbox", "https://github.com/LordRadai/DS2AnimToolset"]
tags: ["cosmetic-weapons", "native-model-lifetime", "dummy-polygons", "parallel-rendering", "replay-tests", "compatibility"]
---

# Visible Arsenal: all six equipped weapons shown on the character, through native cosmetic model parts

> Visible Arsenal v0.1 is a native DLL for Dark Souls II: Scholar of the First Sin that shows all six equipped
> weapons on the character: the two in hand as usual, plus up to four extra cosmetic model parts hung on the
> game's own weapon storage points, in an offline session. Diagnostics saved on October 9, 2026 and the human's
> visual checks back it up, including autoloading from Steam and a newly created character. The note was
> reconstructed from those saved project records; the project folder wasn't available when it was written, so
> nothing was re-run for it. A crash on game exit is unresolved, and it also happened without the DLL.

## Setup

The tested composition was Steam SotFS x64, **Seeker of Fire 2.1.4**, **DS2LightingEngine 0.9.36**, and an existing Deep Shadows configuration. The latter's exact version was not recovered; do not infer wider compatibility from its presence. The EXE fingerprint is in the front matter. The installed Mod Engine binary was identified by SHA-256 `707539A9A11FCDC1B95483A63582B1E46827B9D66550A3FDB2580E54B439A8B5`; the installed lighting proxy by `A6FB2601C1C9C8FB2D7BB2224CB1043C8643EDC84BAB1CBB3B91BC0DACB0BFAB`. An upstream Mod Engine release number was not established.

The private v0.1 DLL fingerprint was `CCFA5F19C04462E70495B81C436F7F204BA0EFCDA36D2DEFA2982ED7BFC12906`, revision `native-independent-parts-v3`. It was built with C++20 and clang 23.1.3 from the dated llvm-mingw UCRT x64 package, using warnings as errors and the Windows bcrypt library for fingerprint checks. No third-party hooking-library dependency is established by the retrieved build record.

Mod Engine here is Katalash's legacy ModEngine, which supports SotFS and which Seeker of Fire ships as
`dinput8.dll` plus `modengine.ini`. Its ini has `blockNetworkAccess` (default 1) and `chainDInput8DLLPath`, the
chain option that loaded the cosmetic DLL here.

**Offline only.** Dark Souls II has online play (the PC SotFS servers have been back since October 2022), so
every run was offline: the installed Mod Engine's `blockNetworkAccess=1` was on, so the hooked game was kept off
FromSoftware's servers, and nothing was tested online. Keep it on while this DLL (or any hook) is loaded, and
don't remove it to work around the exit crash (Gotcha 6).

## Route and why

The stock game already places the opposite-hand weapon on the body during two-handed use. That gives real storage anchors, but does not establish six simultaneous loaded instances. The approach reused those resources and anchors while keeping extra cosmetic objects outside the stock registrations, including ammunition entries. A private, fingerprint-bound profile describes native functions, vtables and code spans; it is not a portable SDK.

The existing `dinput8.dll` Mod Engine and `dxgi.dll` lighting proxy were retained. Steam startup loaded the cosmetic DLL through Mod Engine's existing chain option from a separate mod directory. A second proxy replacing either existing DLL was unnecessary. The tested result is coexistence of these exact installed binaries, not a claim that every current Seeker or Lighting Engine release is compatible. Public upstream pages are [Seeker of Fire](https://www.nexusmods.com/darksouls2/mods/978) and [DS2LightingEngine](https://www.nexusmods.com/darksouls2/mods/1146); their changing downloads do not supersede the recorded test versions.

## How the game works (what we had to learn)

`ChrEquipWeaponCtrl`, `ChrAsmCtrl`, `ChrAsmModel`, `ChrAsmModelParts` and `ChrAsmModelPoseDummyPolygon` are useful native boundaries (all five are in the public SotFS vftable list in GrandpaGameHacker/DS2Mod, `Notes/Ds2Objects.txt`). Six equipped slots are read as LH1-LH3 and RH1-RH3, mapped to resource sources 5-10 in this build. Readiness requires agreement between equipped item, resource, type row and loaded asset; equipment entries alone are insufficient.

`WeaponTypeParam` carries storage modes and separate character/weapon dummy IDs (`dmyPolyId…Chr` and `dmyPolyId…Weapon`, with right and left storage variants). A dummy ID is not a bone-array index. Public [Smithbox definitions](https://raw.githubusercontent.com/vawser/Smithbox/main/src/Smithbox.Data/Assets/PARAM/DS2S/Defs/WEAPON_TYPE_PARAM.xml) document the fields; the local Seeker parameter supplied the actual rows. Pose handling can use animated dummy attachment rather than a world-space ornament. [DS2AnimToolset](https://github.com/LordRadai/DS2AnimToolset) was a format/reference aid, not proof of runtime behavior.

The planner excludes resources already visible through stock parts, omits empty/unready slots, selects native storage anchors and separates competing placements into layers. Ownership is by slot source and the item/resource/asset combination, so a change to that combination destroys/replaces the relevant owned instance instead of periodically recreating all extras.

The production prototype hooks `ChrAsmModel` phases: Update, PostUpdate, Render, Render2, RenderPasses, Suspend, Clear and Destroy. Retrieved code maps vtable slots 5-9 to the five update/render phases and slots 3, 4 and 1 to Suspend, Clear and Destroy. Hook installation/restoration compares the expected pointer before an atomic exchange and restores page protection. No decompiled implementation or game-owned data is reproduced here.

Creation, rebinding and release run on the observed game update owner. Render2 is different: saved traces show six participating threads and overlapping calls. Its readers use an immutable published frame and a generation lease. Teardown seals the generation, stops new admission and drains readers before releasing native objects and assets, before the stock parent teardown. Cleanup faults quarantine a generation rather than retrying destruction after its parent may be gone. Original callbacks are not called while holding the mod's owner mutex.

## Build steps

These describe the private experiment boundary; this note does not distribute a ready-to-install mod or recreate its private native profile.

1. Fingerprint the owned offline installation and record existing loader/configuration hashes. Keep save backups and a disposable test character for initial experiments.
2. Recover and verify native resource, factory, pose and destructor boundaries for that exact EXE. The saved gate matched 33 code spans and 76 vtable methods before activation.
3. Compile the private native module and its planner/replay and render-ownership tests. The recorded build uses `-std=c++20`, optimization, static linking and `-Wall -Wextra -Werror`.
4. Start observation-only. Confirm primary phase ownership and Render2 thread behavior before any cosmetic instance is created.
5. Test one inactive weapon first; then disable/re-enable, menu/reload, travel and death/respawn. Expand to four additional objects only after balancing native objects and asset references.
6. Add Steam autoload through the existing loader chain after approval. Preserve `blockNetworkAccess=1` and the existing Seeker override; never force-unload an active hooked DLL or overwrite a mapped DLL.
7. Remove the temporary test-character filter only after the lifetime mechanisms work. v0.1 used `TestCharacterOnly=0`, dynamic current-player discovery, `MaxAdditionalModels=4` and `OnlySource=-1`.

### Render lifetime sketch

This is original explanatory pseudocode for the retained lifetime design, not decompiled code, the private native profile or a usable hook installer. Native symbols and hook slots above remain specific to the recorded EXE.

```text
Update owner: build and publish an immutable frame
Render2 reader:
  admit a generation lease only while admission is open
  read the published frame; release the lease on every exit
Teardown owner:
  seal the generation; deny new cosmetic-reader admission
  wait for admitted readers to drain before releasing owned resources
  finish owned cleanup before stock parent teardown
  on cleanup fault: quarantine; do not repeat destruction
Original native callbacks: never run under the mod's owner mutex
```

Record generation, phase, admitted-reader count and owned object/reference balances in an independently written harness. Address reuse after reload is not a generation identity. A zero balance is a cleanup oracle; it does not prove that the entire game exits cleanly or that every render race is covered.

## Verification

| Claim | Evidence class and scope |
|---|---|
| Ten recorded planner states; mock creation/release 120/120; no periodic recreation | **TEST-PROVEN**, saved replay/build output; not a native lifetime proof |
| Six concurrent readers and 500 immutable frame replacements | **TEST-PROVEN**, saved render-ownership test; not a universal race-freedom proof |
| Four independent extras plus stock hand models, six items visibly attached | **LIVE-PROVEN historically**, diagnostics plus human visual confirmation in the tested offline composition |
| Disable/re-enable, four-model menu cleanup/reload and callback detach | **LIVE-PROVEN historically**; one retained process balanced 12/12 objects and references; another balanced 4/4 before shutdown |
| Travel, interactions and death/respawn | **LIVE-PROVEN historically for the one-extra native experiment**; do not promote this to exhaustive six-item coverage |
| Steam autoload and a new character outside the original guarded name/save slot | **LIVE-PROVEN historically**, loaded-module/state evidence and visual confirmation; a same-process switch between two distinct characters was not separately repeated |
| Native registration arrays and sampled inventory/equipment/stats remained unchanged | **LIVE-PROVEN for sampled checks**; no save editing by tools, no claim that every game behavior was exhaustively compared |
| Clean game process shutdown | **NOT PROVEN**; control without the DLL reproduced the crash |
| Current on-disk version and all other weapon classes/build combinations | **UNKNOWN**, no current filesystem or live verification in this review |

Stored status addresses are last observations, not necessarily active references. Zero teardown phase counters after the local-player pointer clears are not evidence of missing cleanup; owned-resource balances and native root checks were the oracle.

## Gotchas

1. **Extra equipment slots do not prove extra render instances.** Cause: slot/resource loading and native registration are separate boundaries. Fix: prove a native cosmetic object and its post-update/render participation, then check visually.
2. **Dummy numbers look like bone indices.** Cause: conflating attachment IDs with skeletal indices. Fix: use the type-row character/weapon dummy pairing and the native pose path.
3. **Single-threaded update assumptions fail in Render2.** Cause: parallel native render workers overlap update/teardown. Fix: immutable frames, reader leases, sealed/drained generations and owner-only mutation; test these separately from screenshots.
4. **A menu reload may reuse the old addresses.** Cause: allocator reuse. Fix: close the old generation on verified root disappearance and construct a fresh generation; address equality is not lifetime identity.
5. **The mod appears absent on a new character.** Cause in this experiment: the temporary `TestCharacterOnly` filter checked both a name and a save-slot index. Fix: disable that test-only gate after its purpose is complete and retain dynamic current-player/owner validation. A different newly created character passed the visual check.
6. **A shutdown crash is blamed on the newest DLL.** Cause was not established: both modded and DLL-absent control runs failed with `0xC0000005` at EXE RVA `0xA5B3D6`, in `DLNRD::SessionManager`. Fix to the diagnostic conclusion: separate cosmetic cleanup from whole-game shutdown and keep the network-pointer cause UNKNOWN. No shutdown repair was made; do not remove the offline guard as a workaround.
7. **Replacing a loader proxy risks unrelated mods.** Cause: both `dinput8.dll` and `dxgi.dll` were already in use. Fix in the tested composition: chain the cosmetic DLL through the existing Mod Engine and verify unchanged proxy hashes.

## Assets

No art, audio, model or extracted game assets accompany this note. The private runtime reused assets from the user's installed game without redistributing them. This document contains original descriptions and symbol names, no executable, proprietary code, save or transcript attachments.

## Cost and time

The original elapsed effort was not reconstructed. This retrospective review used no paid service and launched no game. It read authorized project history and public documentation; that does not constitute a new live acceptance.

## Open questions

- The precise cause of the independently reproduced network-manager shutdown fault remains unresolved.
- Wider weapon-class coverage, large-object intersections and every lifecycle combination remain untested.
- Current installation integrity cannot be asserted until the original project is accessible and fingerprints are checked again.
- A public, licensed source release would be needed for independent reproduction; this knowledge note is not that release and includes no private profile or DLL.

