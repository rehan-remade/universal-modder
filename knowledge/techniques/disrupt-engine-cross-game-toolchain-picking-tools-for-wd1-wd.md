---
kind: technique
title: 'Disrupt engine cross-game toolchain: picking tools for WD1, WD2 and Legion'
status: working
agents:
- OpenCode (MiMo-V2.6-Flash)
- OpenCode (DeepSeek V4.1 Flash)
humans:
- '@Selene0623'
date: '2026-10-06'
links: []
tags: [disrupt, dunia, watch-dogs, far-cry, archives, reverse-engineering, toolchain, ubisoft]
---
# Disrupt engine cross-game toolchain: picking tools for WD1, WD2 and Legion

> Which tool to reach for when modding a Disrupt title (WD1 / WD2 / Legion), and the gotchas that
> silently corrupt your data. Disrupt is a Dunia 2 (Far Cry 3) fork, so tool conventions and the
> compiled-XML object serialization run through Far Cry 3–6 too — but the container and the details
> fork per game (WD1/WD2 pack `Depload`, WDL packs `BigFile`; Dunia uses `FAT2`/BigFile v11), so never
> assume a tool or an offset carries across. Distilled from a community documentation site for Disrupt and
> Far Cry formats; no unpack→repack cycle was run by this agent for
> this note, and the per-claim source is marked in the text.

## When to use it
Any session on a Disrupt game: unpacking/repacking `.dat`/`.fat` archives, converting binary objects,
porting XBG meshes or XBT textures across titles, or deciding where a mod file should live so it loads.

## How
- **Unpack:** `UnpackLegion.exe` for WDL; `UnpackWD2.exe` for WD2; Gibbed.Disrupt for WD1 (archives
  under 4GB only).
- **Pack:** `Gibbed.Disrupt.Packing.dll [OPTIONS]+ <output.fat> <input_dir>+` is the tool that actually
  works. Its upstream is [gibbed/Gibbed.Disrupt](https://github.com/gibbed/Gibbed.Disrupt), but the fixes
  below are **not upstream yet** — they live on a downstream fork, and readers should apply them to
  upstream. The fork stays under the **same zlib license as upstream, with
  each set of changes attributed to its respective author**. Major changes, by commit:
  - **Archive formats:** the old BigFileV5 decoder split into BigFileV11 (WD2) + BigFileV13 (WDL), plus
    a working V13 **packer** (`80d5320`); X360 FAT2 entry decode on branch `x360-fat2-unpack-fix`
    (`311b25f`), where `fieldB = (uncompressedSize << 3) | scheme`.
  - **Compression correctness:** LZ4LW emits the offset before the match-length extension — archives
    packed without it are corrupt (`f0a8be0`); PS4/Orbis big-file support with LZ4LW + LZMA decompression
    (`5b1a51f`); the Troplo-fork merge that integrates the XNA compression path so pack/unpack actually
    works (`96b7a68`, `c60ddf7`).
  - **Robustness:** `EntryDecompression` skips entries whose XMemCompress frame fails instead of aborting
    the whole unpack (`be88090`) — that is a **workaround, not the proper fix**; a real fix should still
    decode why those frames fail and repair or retry them.
  - **Path/extension parity:** Modifier path lowercase-sanitize for Dunia parity (`da06273`); file-extension
    mapping fixes (`fd58623`, `430cc41`).
  - **Build/infrastructure:** net8.0-only submodule builds (`0dc7488`) — **major, not noise: the Linux
    build depends on it**; CI broken-symlink fix (`5a1719b`); GitHub Actions v4→v5 (`9e84628`).
  - **Data:** WDL animation filelist (24,982 entries), WD2 469K-line filelist, WD2 debug-dialog filelist
    (`e55b033`, `13558df`, `c46195b`); HashList collision detection in the ProjectData submodule
    (`0788c76`).
  - **Minor but worth knowing:** dead LZO1x decompression branch removed and the `-c` flag docs corrected
    (`b16b80b`).

  Options that
  matter: `-c/--compress` (WDL scheme 3 = LZ4LW), `--pv` (pack version), `--cv` (compression version),
  `--nhv` (name hash version). It also **writes the `.nfo` next to the `.fat` itself** — do not hand-roll
  one. `--cv`, `--nhv`, LZ4LW `-c`, `--jobs`, the `dotnet` entry point and the `.nfo` writing are the fork's:
  upstream ships per-game `Gibbed.WatchDogs*.Pack.exe` packers with `-c` (LZO1x), `--pv` and `--pt`, and writes
  no `.nfo`. DisruptManager (rootCBR) is the older WDL packer; it packs only into `patch*` archives and skips
  `installpackage/`, so prefer Gibbed.
- **Binary objects:** `Gibbed.Disrupt.ConvertBinaryObject.exe` — use the **WD2 build**, it is the one
  that handles WDL's binary objects.
- **Where files load from — per game, not shared:** the priority list is hardcoded per title
  (decompiled from `DisruptManager.Model.GameInfos.*`): WD1 = `patch1` > `patch` > `common` >
  `worlds\windy_city\windy_city`; WD2 = `patch2` > `patch1` > `patch` > `common` >
  `worlds\san_francisco\san_francisco`; WDL = `patch` (+ `patch0`, `patch1`) > `common` >
  `worlds\london\london`. `installpackage` exists in all three but is unused by default; the DLL hex
  edit gives it top priority so a loose `installpackage/` folder wins permanently. The two byte
  patterns are identical across WD1 `Disrupt_b64.dll`, WD2 `Disrupt_64.dll` and WDL
  `DuniaDemo_clang_64_dx11/_dx12.dll` and unchanged since 2021 — but the resulting order is per game.
- **Hash namespaces differ per title:** WDL/WD2 key off a 64-bit hash; the one tools call `CRC64_WD2`
  is *not* a CRC — it is FNV-1 64 (same prime/offset as FNV64) with `/`→`\` normalization, lowercase,
  a low-61-bit fold (`& 0x1FFFFFFFFFFFFFFF`) and a namespace tag (`| 0xA000000000000000`); a plain
  FNV64 row exists too, and a case-preserving variant skips the lowercase. WD1's "FNV32" is just the
  **low 32 bits of that 64-bit value**, not a standalone FNV-1a 32, so IDs never carry across games.
  `CBR.Disrupt.dll` gets all three of these wrong (it ships a polynomial CRC64 and an unnormalized
  FNV1a64) — use `hash_tool.py` output, not the CBR classes.
- **Multiplayer with mods (community-reported):** it works, but the mod set has to match. The WD modding
  multiplayer server is a NexusTools variant, not the vanilla game — players must run the *exact same* mods,
  or all enable the mixed-mod option, otherwise each is locked to their own mod hash, and NexusTools
  otherwise keeps multiplayer off. Some mods carry their own rule on top of that: WD2 Extended requires both
  players to have it, and a mismatch has been seen to drop one player out of the session (crash or
  disconnect — the mechanism is not established). Reported by @Selene0623 (2026-10-03, extended 2026-10-05),
  not from the reference docs, so re-verify before relying on it. What the docs do confirm: NexusTools is a
  WD1 mod-delivery layer (ASI loader plus a `workspace/` overlay), and delivering a whole archive as one pack
  shadows every file beneath it. Weight this accordingly: WD2's public/competitive multiplayer is largely
  dead at the time of writing, so the mod-set rules matter for arranged sessions on that community server,
  not for matchmaking.
- **Anti-cheat status:** WD1 ships none. WD2 shipped EasyAntiCheat: while EAC's service ran, modded files
  tripped it and the only way past the check cost multiplayer, so the launch flag people passed around was
  never a free bypass, it disabled multiplayer and nothing else. That service lapsed earlier in 2026
  (reported by @Selene0623, 2026-10-05), so nothing anti-cheat-related gates mods there now, which leaves
  the flag pointless as a workaround and useful only as a multiplayer toggle. Modded multiplayer is gated by
  mod-set compatibility instead. WDL shipped BattlEye, whose modified-file check trips on a patched DLL;
  BattlEye was removed in the final WDL update, so the check no longer applies there. Online behaviour is
  nowhere in the reference docs, it is community-reported only. Circumventing an anti-cheat client stays out
  of scope for anything published here, and no flag is named.

## Gotchas
1. **Symptom:** unpacked WDL files are garbage. **Cause:** UnpackWD2 or Gibbed.Disrupt was used on
   WDL archives — both break there. **Fix:** UnpackLegion for WDL.
2. **Symptom:** repacked archive is wrong/ignored. **Cause:** PackLegion and ManageLegion are
   outdated. **Fix:** DisruptManager (or the loose `installpackage/` route) instead.
3. **Symptom:** unpacker dies mid-archive. **Cause:** Gibbed.Disrupt breaks above 4GB. **Fix:** skip
   it for big archives; WDL patch archives can exceed the limit.
4. **Symptom:** WDL binary object won't convert. **Cause:** wrong converter build. **Fix:** the WD2
   `Gibbed.Disrupt.ConvertBinaryObject.exe`.
5. **Symptom:** FCBastard crashes mid-run on WD2/WDL entity data. **Cause:** a Vector3 buffer overflow
   on `colorColor` in the stock build; the upstream release is effectively WD1-only (its WD1 build also
   breaks on a WLU FCB repack, losing road data). **Fix:** for WDL use the overflow-fixed Legion build —
   `FCBastard_Legion_Dist/FCBastard.exe`, "Encrypted's Update", run under wine with `z:\` absolute
   paths; it round-trips `entitylibrary` FCB ↔ XML byte-faithfully. For WD1 keep the WD1 build and check
   the round trip.
6. **Symptom:** a cross-game ID silently misses (mesh lookup, entity UID, playlist entry). **Cause:** the
   hash namespace differs — WD1's hash is the low 32 bits of the same 64-bit computation WD2/WDL mask
   and tag. **Fix:** recompute in the target game's namespace with `hash_tool.py --crc64wd2`, never with
   the `CBR.Disrupt.dll` classes.
7. **Symptom:** ported XBG/XBT is rejected. **Cause:** format forks per game (XBG chunk chain and
   vertex-stride encoding differ FC5 vs FC6 — FC5 states a 40-byte stride, FC6 infers it from vertex
   size; WDL geometry is MOEG with its own version pair; XBT version u16 at +0x04 is platform-specific,
   `0x0092` = PC). **Fix:** convert through the target game's importer rather than byte-copying. The
   Blender addon's XBG import is the practical route for static props (WD2 headers 0x89/0x46, WDL
   0x95/0x46); character-model import is the weak spot — the addon's own known-issues list records WD2
   character files crashing while another tool note claims support landed 2026-09-05, so test it on the
   actual file before promising anything.

8. **Symptom:** `dotnet Gibbed.Disrupt.Packing.dll out.fat dir/` dies with *Nullable object must have a
   value*. **Cause:** `--pv` was omitted (`Pack.cs` reads `Version = version.Value`). **Fix:** pass the pack
   version explicitly — WD1/WD2 `--pv 8`, WDL `--pv 13 --cv 8 --nhv 70`.
9. **Symptom:** unpack invocation errors with `Could not locate FAT file '8.fat'` (or any bare number).
   **Cause:** `--jobs` was abbreviated to `-j`, and the value was parsed as the archive path. **Fix:** spell
   it `--jobs=8` (or `--jobs 8`).
10. **Symptom:** unpacking a retail archive throws `System.IO.FileNotFoundException: Could not load file or
    assembly 'XCompression, Version=1.0.0.0'` from `EntryDecompression.DecompressXMemCompress`. **Cause:**
    the archive's entries are XMemCompress-compressed and the `XCompression` dependency is missing/stale in
    the build you are running (an uncompressed mod archive never hits this, so it can hide for a while).
    **Fix:** rebuild Gibbed.Disrupt from source (the dependency is part of the solution), do not fall back to a global tool
    install.
11. **Symptom:** a repacked archive is accepted but the game renders nothing / boots into a black screen.
    **Cause:** the container format is fine — pack/unpack was verified byte-for-byte; the *content* was
    wrong (e.g. a whole-archive shader pack carrying bytecode the engine rejects silently). **Fix:** verify
    by repacking the unmodified retail files through your own pipeline and testing that control pack before
    blaming the packer.

## Seen in
- No `knowledge/games/` note exists for WD1, WD2 or Legion yet. A Watch Dogs: Legion game note referenced by
  the first revision of this file is no longer in the tree (it was never committed), so its link is gone.
- Source material: a community documentation site for Disrupt and Far Cry reference docs (no stable link
  published here); the per-claim source is noted in the text above.

---

**Corrections (2026-10-05, @Selene0623 with OpenCode/DeepSeek V4.1 Flash):** the first revision generalised
WDL's archive order to all three games, described `CRC64_WD2` as a CRC, stated the FCBastard limit as a total
WD1-only tool, and reported Blender character-model import as working. All four were checked against the
reference docs and rewritten: priorities are per game, `CRC64_WD2` is FNV-1 64 with a fold and a tag, the
overflow-fixed Legion FCBastard build round-trips WDL entity libraries, and the addon's own known-issues list
still records WD2 character files crashing.

**Clarified after review (2026-10-05, same session):** the anti-cheat and multiplayer bullets were rewritten
once @Selene0623 filled in the online side. Mods do reach multiplayer, through a community NexusTools server;
skipping the anti-cheat check only disables multiplayer, it bypasses nothing; per-mod compatibility rules exist on top of
the same-mod requirement (WD2 Extended needs both players to have it, mismatch drops someone out of the
session); and WD2's EAC service lapsed earlier in 2026, so nothing anti-cheat-related gates mods there any
more. The earlier "mods and multiplayer do not work together" line was the pre-lapse state, not the current
one.

**Corrections (2026-10-06, @Selene0623 with OpenCode/DeepSeek V4.1 Flash):** the pack/unpack story was
rewritten against the fork that carries our fixes. `Gibbed.Disrupt.Packing.dll` is the working packer and it
writes its own `.nfo`; `--pv` is mandatory (WD1/WD2 `--pv 8`, WDL `--pv 13 --cv 8 --nhv 70`); unpack takes
`--jobs=N` (`-j 8` is parsed as an archive named `8.fat`); and `XCompression` missing from the build breaks
unpacking of any compressed retail archive. Gotchas 8-11 were added for those. The fixes referenced here
are on a downstream fork's `main` — the full fork-vs-upstream change list (with the zlib-license /
per-author attribution) is in the Pack entry above — not upstream on
gibbed/Gibbed.Disrupt. The pairing of jobs and (prefer gibbed) tool is the same engine contract the WD1
shader-pack work (see the WD1 shader notes) relies on. No anti-cheat bypass is named here.

**Credits:** distilled from a community documentation site for Disrupt and Far Cry reference docs, compiled
by @Selene0623 from XeNTaX archive threads and the WD/Disrupt/Dunia
Discord communities, with in-doc confirmations credited to Pesky Fly, qstlijku, and rootCBR. NexusTools multiplayer behaviour reported by
@Selene0623 (2026-10-03) and marked unverified above.
