---
kind: game
title: 'Domino (Phantasmal Link) past 4 targets: a 5-byte exe patch'
game: Dishonored 2
games_also: []
game_version: 'GOG (DRM-free), Dishonored2.exe 42,591,232 bytes, PE timestamp 0x5c050611 (2018-12-03), x64'
platform: windows
engine: idtech
route: native-hook
tools: [python 3.15, pefile, capstone, numpy, Cheat Engine, universal-modder um]
anti_cheat: 'none (single-player, GOG build has no DRM)'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-14'
links:
- https://github.com/chipolux/disrev
tags: [void-engine, idtech5, domino, phantasmal-link, hard-coded-limit, idlist, fixed-pool, exe-patch, resources-index]
---
# Domino (Phantasmal Link) past 4 targets: a 5-byte exe patch

Raises Dishonored 2's Domino power above its hard-coded 4 linked targets while the limit stays driven by the
attribute `ARK_ATTRIBUTE_PHANTASMAL_LINK_EXTRA_NODES` (limit = 2 + attribute, now clamped to 6 instead of 4).
Delivered as an on-disk exe patcher (stdlib Python, backup + undo), because the user already runs other
dinput8.dll proxy mods. Verified by the user in the real game: with the attribute set to 3 and 4 (via Cheat
Engine), 5 and 6 targets link, the next mark drops the oldest, effects propagate to all, and every target's
glow clears afterwards. No crash.

## Setup
GOG Dishonored 2 at `C:\Games\Dishonored2`, run directly from the exe, Windows 10 Pro 22H2. Static analysis
only: Python 3.15 with pefile + capstone + numpy (no Ghidra/IDA, no compiler on the machine). The user tested
in game; the attribute was raised with Cheat Engine (the skill tree only writes `ARK_ATTRIBUTE_*` values, and
the vanilla tree stops at EXTRA_NODES = 2 via the upgrades `domino_link_3` / `domino_link_4`, +1 each).

## Route and why
- Data only: impossible. The attribute is already data, but the clamp and the container sizes are in code.
- dinput8 proxy (in-memory patch at startup): clean, but the user runs other dinput8 proxies and there was no
  compiler; chaining proxies was more risk than value for 5 bytes.
- Cheat Engine table: works, but has to be re-applied every launch.
- Chosen: on-disk exe patch. A Python patcher locates each byte by its own pattern, refuses unless every
  pattern matches exactly once, writes via a temp file, keeps `Dishonored2.exe.domino-backup`, and has `undo`.
  A game update or GOG "verify files" reverts it; re-run `apply`.

## How the game works (what we had to learn)
VAs below are for this GOG build (image base 0x140000000; .text file offset = VA - 0x140000000 - 0xC00).
Classes: `arkCpntPowerPhantasmalLink`, `arkCpntPhantasmalNetwork`, `arkCpntPlayerSensorPhantasmalLink`,
`arkPlayerStateUsePhantasmalLink`, nested `arkPhantasmalNetwork::plug` and `::connexion`.

- **The attribute is read once per add.** A static initializer resolves the attribute name into a handle;
  the network's init caches the attribute index at `network+0x2640`. AddTarget (0x14059b080) computes
  `max = min(attr + 2, 4)` (a `mov eax, 4` + `cmova`), then removes the oldest plug (by a timestamp at
  `plug+0x7c`) only when `count == max` (a `jne`).
- **The 4 is a design-wide size, not one constant.** Raising the clamp alone is not enough:
  - The network's list of *marked* plugs (`+0x28` data ptr, `+0x30` count in the low 24 bits, `+0x34`
    `cap << 8 | flags`, inline storage `+0x38`) is constructed as a fixed 4-slot inline list
    (`mov dword [rcx+0x34], 0x440`).
  - Two stack lists in the reachability/prune check (0x14059aa70, run from Connect) are also capped at 4.
- **idList mode bits.** In this engine's idList, flag bits 6-7 select the storage mode. `0x40` = fixed inline:
  the generic append (0x14000cbc0) silently does nothing when full. `0xC0` = inline that spills to the heap
  when full (helper 0x14000bb30 allocates, copies, rewrites flags). The destructors already free heap-owned
  buffers, so switching a list from 0x40 to 0xC0 is a one-byte, leak-free change.
- **Fixed pools.** The network embeds a plug pool (16 x 0x150 bytes) and a connexion pool (32 x 0x80 bytes).
  Connect (0x14059b8c0) creates 2 connexions between the new plug and each marked plug. CreateConnexion
  (0x14059b640) recycles connexions in state 2 (closing) when the pool is full, and returns null otherwise,
  which the caller dereferences. So n marked targets need n(n-1) connexions: 4 -> 12, 5 -> 20, 6 -> 30,
  **7 -> 42 > 32 = crash**. 6 is the hard ceiling without enlarging the pool (which would change the object's
  size and every offset after it).
- FX: the "plugged" glow handle lives per plug (`plug+0x90`, spawned/removed by 0x1405bf130 / 0x1405bf280);
  the network decl names `phlink_validated_01.fx`. Decls also set `m_connexionMaxLength = 20` and
  `m_connexionMaxOpenedDuration = 15`. The FX files impose no instance limit.
- Decls were read from `base/game1_patch.index` / `.resources` with the layout from chipolux/disrev and the
  [bonecharm note](black-and-corrupt-bonecharm-traits-learnable-and-ng-persistent.md) (entry count is a BE u32 at 0x20, entries start at 0x24; zlib wbits 10).

## Build steps
1. Locate and patch these 5 bytes (file offsets for this build; the patcher finds them by pattern):

   | name | file offset | vanilla -> patched | meaning |
   |---|---|---|---|
   | cap | 0x59a4c5 | 04 -> 06 | clamp `min(attr+2, 6)` |
   | demark | 0x59a4e0 | 75 -> 77 | `jne` -> `ja`: drop the oldest when count >= max |
   | list | 0x597d88 | 40 -> C0 | marked list: fixed inline 4 -> growable |
   | reach1 | 0x599f2b | F1 -> E9 | `btr ecx,7` -> `bts ecx,7`: prune list growable |
   | reach2 | 0x59a066 | F2 -> EA | `btr edx,7` -> `bts edx,7`: second prune list growable |

   Patterns (one capture = the byte): cap/demark share
   `B8 ?? 00 00 00 F3 48 0F 2C C8 83 C1 02 3B C8 0F 47 C8 8B 47 30 25 FF FF FF 00 3B C8 ?? 5C`;
   list `48 8D 41 38 48 89 41 28 C7 41 34 ?? 04 00 00 48 89 79 58`;
   reach1 `48 8D 45 0F 48 89 45 FF 0F BA ?? 07 83 C9 40`;
   reach2 `48 8D 45 DF 48 89 45 CF 0F BA ?? 07 83 CA 40`.
2. Raise `ARK_ATTRIBUTE_PHANTASMAL_LINK_EXTRA_NODES` to 3 or 4 (Cheat Engine, or extra skill-tree levels).

## Verification
- Static: each pattern unique in the exe; patched code disassembled with capstone and read back; scratch
  copies tested for vanilla -> patched, v1 -> v2 upgrade, and undo byte-identical to the original
  (sha256 compared); cap 7 refused by the patcher.
- In game (user, both limits): EXTRA_NODES 3 -> 5 targets and the 6th mark drops the oldest; EXTRA_NODES 4 ->
  6 targets and the 7th drops the oldest; kill/knock-out propagates to every linked target; all glows clear;
  no crash.
- Same patcher later grew into a combined patcher for many other fixes; see
  [the exe-fixes note](gog-exe-fixes-with-an-added-code-section.md).
- Not verified: save/load with 5-6 marks active, the HUD with more than 4 marks (nothing looked wrong to the
  user), the Steam build (the bonecharm note's exe is a 2025 Steam build; the patterns may or may not match).

## Gotchas
1. **Patching only the compare: infinite marking, crash at the 7th target.** (The user's original Cheat
   Engine edit.) **Cause:** the oldest-target removal uses `count == max`, and the marked list can never hold
   more than 4, so the count never reaches a higher max; meanwhile every extra plug still opens 8 connexions
   to the 4 listed plugs (12, 20, 28, 36 > 32 pool slots). **Fix:** make the lists growable (gotcha 2) and cap
   at 6.
2. **Clamp raised + `==` -> `>=`, but no de-mark at the limit, and targets 5-6 keep the glow after the effect.**
   **Cause:** the marked list is a fixed 4-slot inline idList (flags 0x40); appends 5+ silently fail, so those
   plugs are connected (they do get the effect) but never recorded, never counted and never cleaned up.
   **Fix:** flags 0x40 -> 0xC0 in the network constructor, and the same mode change for the two 4-slot lists
   in the reachability check.
3. **Don't go above 6.** The connexion pool is 32 slots embedded in the network object; 7 targets need 42.
   Enlarging it would shift every later field offset. The patcher refuses `--cap 7`.
4. **The visible limit is 2 + attribute, not the attribute.** Vanilla tops out at 4 because the tree gives
   EXTRA_NODES = 2; to see 5 or 6 the attribute must be 3 or 4.
5. **Tooling on Windows:** run your own pefile/capstone scripts with `python -P`, not `-I` (that drops the
   user site-packages); never name a script `dis.py` (it shadows the stdlib module and capstone's import
   breaks).

## Assets
None.

## Cost and time
One long session of static analysis (two context compactions), plus two in-game tests by the user.

## Open questions
- Does the same pattern set match the current Steam exe? Run the patcher's `status`: it reports
  "not supported" and changes nothing if any pattern isn't found exactly once.
- A 7+ cap would need a larger connexion pool (moving the network's later fields) or a heap-backed pool.
