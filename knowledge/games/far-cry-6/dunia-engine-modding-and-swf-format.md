---
kind: game
title: "Far Cry 6 — Dunia engine modding and the SWF/FEU UI format"
game: "Far Cry 6"
games_also: ["Far Cry 5", "Far Cry New Dawn", "Far Cry 4", "Watch Dogs (Disrupt, shared formats)"]
game_version: "see note"
platform: windows
engine: unknown
route: data
tools: ["FCBConverter", "Gibbed.Dunia", "FC6Model.exe", "FC6.Hook", "FCModInstaller", "Sandbox2Package.exe", "blender-io-dunia", "JPEXS FFDec", "base64 SWF Texture Tool", "wwiser", "DuniaTools"]
anti_cheat: "No kernel-level anti-cheat is reported. All work is offline against local archive and UI data; mods ship as .a3 packages installed by FCModInstaller. Ubisoft Connect account-binds save files (UPC ID); that is noted, not circumvented."
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links:
  - "https://github.com/JakubMarecek/FCBConverter"
  - "https://github.com/jindrapetrik/jpexs-decompiler"
  - "https://open-flash.github.io/mirrors/swf-spec-19.pdf"
tags: ["far-cry-6", "dunia", "swf", "feu", "weapon-wheel", "vehicles", "archive", "asset-modding"]
---
# Far Cry 6 — Dunia engine modding and the SWF/FEU UI format

> Far Cry 6 runs on Dunia (the engine line that also produced Disrupt / Watch Dogs), and ships its HUD and menu UI as Adobe Flash movies wrapped in Ubisoft's `.feu` container. Mods are data edits: unpack the BigFile v11 archive, change markup, textures, meshes or UI, and repack — definition files are merged, never replaced. The weapon-wheel icons are a good end-to-end example, because they live as Base64-encoded descriptors inside the FEU movie. Vehicle identity is expressed as 64-bit entity IDs, listed per class in unpublished working notes.

See `techniques/dunia-swf-file-format.md` for the engine-agnostic SWF/FEU container spec (signature swap, byte layout, compression), and `games/watch-dogs/engine-fundamentals-and-native-patching.md` for the sibling Disrupt/Shadow engine.

## Setup

- Retail Far Cry 6 on Windows (Ubisoft Connect or Steam). No specific build number is recorded (unpublished workspace notes).
- A working copy of the game archives. Archives are BigFile v11 (magic `FAT2`, version `0x0b`; entries carry a CRC64 name hash and an LZO1x/LZ4 compression flag).
- **FCBConverter** (https://github.com/JakubMarecek/FCBConverter) — the archive tool that actually handles FC6 (v11). Gibbed.Dunia2 only covers v5–v9; Gibbed.Disrupt does not handle v11.
- **JPEXS FFDec** (`ffdec-cli.jar`, Java) — opens Flash `.swf` and can be coaxed to open the `.feu` container and `.gfx`.
- **base64 SWF Texture Tool** — a small unpublished C# tool that encodes/decodes the icon descriptor blobs. Build: `dotnet build "base64/base64 crap.sln"` (verified, 0 errors).
- On Linux, run the Windows tools under Wine; Gibbed.Dunia needs `-p/--install-path` to skip registry detection.

## Route and why

- **Route: data.** FC6 ships its content inside BigFile v11 archives, and the UI is Flash inside `.feu` files. That makes archive unpack → edit → repack the natural route, and it needs no native code hook and no anti-cheat interaction.
- **Definition/source files are sacred.** Binary objects, filelists and material descriptors must be *merged or updated*, never replaced wholesale. This is the single most important rule from the engine RE notes.
- Mods are distributed as `.a3` packages, which are ordinary ZIP archives and are installed by FCModInstaller / ModInstallerCMD.

## How the game works (what we had to learn)

**Archive.** FC6 uses BigFile v11. Header: `FAT2` magic, version `0x0b`, a sub-FAT count, and a total file count. Each entry is 20 bytes: a raw CRC64 name hash, an uncompressed size whose low 2 bits are the compression flag (`>>2` gives the size), an unresolved offset, and a compressed size. The offset is reconstructed as `((compressedSize >> 29 | unresolvedOffset << 3) << 4)`; the compression flag is read first from the raw size, then `compressedSize &= 0x1FFFFFFF`. Compression: None = 0, LZO1x = 1, LZ4 = 2. Because names are hashes, you need a hash→name table (unpublished FC6 filelist snapshots are kept for this).

**UI is Flash.** `.feu` is a **Flash Export Unit**: a standard Adobe Flash SWF whose 3-byte signature `FWS` has been replaced by `UEF` (bytes `55 45 46`). Byte 3 is the SWF version `0x08` (Flash 8); bytes 4–7 are a little-endian u32 file length; the rest is an unmodified SWF (zlib per the normal SWF rules). Converting is a one-byte-region edit:

```
# FEU -> SWF (edit the first three signature bytes)
sed -i '1s/UEF/FWS/' file.feu
# SWF -> FEU is the reverse: FWS -> UEF
```

The movie contents are Flash movieclips driven by ActionScript 2 classes (names like `driver.LoadableContainer`, `driver.gamehud.Gh_*`), built from ordinary tags — `DefineShape`, `DefineSprite`, `DefineEditText`, `DoAction`, `SymbolClass` — and they reference engine resources by string path (fonts `*.ffd`, supertextures `*.bfd`). The full Adobe SWF structure is summarized in the companion technique note.

**Weapon-wheel icons.** In the FEU XML, each icon is a Base64 blob inside `<UnknownTag id="0xF6">`. Decoding a blob yields a character ID plus a texture path. The community workflow (BIRDdude12's tutorial) is: decode the blob, duplicate the neighbouring `DefineShape` block, point the inner `ClippedBitmap2 objectID` at the new character ID and the outer `DefineShape objectID` at `charID - 1`, add a `FrameLabel` / `PlaceObject2` / `ShowFrame` block (and duplicate it in the store section), recompile XML → SWF → FEU, then set the weapon `itemdescriptor`'s `icon` field to the new `FrameLabel` name. The texture path must be `.png`, not `.xbt`.

**Icon blob binary layout** (little-endian):

```
0x00  u16  Character ID
0x02  u16  Width
0x04  u16  Height
0x06  ...  null-terminated UTF-8 texture path
```

The whole struct is Base64-encoded into the FEU XML. FC5 notes on the same workflow: the blob needs trailing `AAAA` padding (4+ bytes), sometimes one or two `=`; a 22-character texture filename is the safe length; a Flash decompiler is the fallback when the tool mis-parses.

**Vehicles.** Vehicle identity is a 64-bit entity ID. Unpublished workspace notes list 293 of them, grouped by class (Land — quads, coupes, compacts, sedans, off-roads; Marine; Aircraft), named like `<CLASS>.<VEH_* variant>[.Civilian|Police|Taxi|Hero|DLC_*|MIS####|DO_NOT_USE_*]`. Examples (decimal u64): `VEH_Pegasus.Flying` = 9015384182121694, `VEH_Quad` = 9015224056227292, `COUPE.VEH_Coupe_Old.Civilian` = 9015398120832740. An unpublished fandom-wiki dump is the human-readable roster (~150 named vehicles and variants).

**Other formats worth knowing.** Meshes are XBG, magic `HSEMI` ("IMESH") in FC6 (FC5 is `HSEMG`). No shader source ships; compiled shaders live in `d3d12/shadersobj.dat` and decompile through a `sarb → DXBC → SPIR-V → HLSL` pipeline. Physics is Havok 2017.2.0.

## Build steps

1. Unpack the target archive with FCBConverter; keep the original untouched.
2. Edit the desired data. For UI work: convert `.feu` → `.swf`, open in JPEXS FFDec, make the change, recompile SWF → FEU.
3. For icons, edit the Base64 descriptor with the SWF Texture Tool and follow the `DefineShape` duplication workflow above.
4. Repack the archive / build the `.a3` package with FCModInstaller, **merging** changed entries into the existing definition rather than replacing it.
5. Install the `.a3` and launch the game.

## Verification

- The SWF Texture Tool build was verified locally (unpublished tooling): `dotnet build "base64/base64 crap.sln"` completes with 0 errors.
- The BigFile v11 decode math and the FCBConverter behaviour are recorded from the tool's own source (`FCBConverter/Program.cs`).
- **The SWF/FEU icon workflow itself is a community tutorial captured in unpublished notes, not independently reproduced by this agent.** Treat the exact `DefineShape`/`objectID` steps and the Base64 padding rules as community-verified, pending a first-hand round trip. Honest status: in-progress.

## Gotchas

1. **Never replace definition/source files** — merge or update binary objects, filelists and material descriptors.
2. `.a3` mod packages are just ZIP files; rename and extract if you need to inspect them.
3. The FC6 string dump and the DLC-trials file list contain **no `.swf`/`.feu` filenames**, so FEU assets are reached by hash→name tables, not by browsing a directory listing.
4. Icon texture paths must end in `.png`; `.xbt` will not load.
5. The `.mab` animation format is a known community blocker for FC6; do not assume animation editing is solved.

## Assets

Local, unpublished working files (not distributed with this note):

- `FC6/FC6_Vehicle_IDs.txt` — 293 vehicle entity IDs with comments, grouped by class.
- `farcry-fandom-com-wiki-Far-Cry-6-vehicles.md` — human-readable vehicle roster.
- `weapon_wheel_tutorial.txt` — BIRDdude12's icon-replacement walkthrough.
- `swf-file-format-spec.md` / `.pdf` — local conversion of the Adobe SWF v19 reference (2012); original at the link above.
- `base64/` — the SWF Texture Tool source.

## Cost and time

- Not recorded. No session timing data was kept for the FC6 work.

## Open questions

- Exact FC6 build/version used for this research — **not recorded** (frontmatter says "see note").
- Do FC6 base archives actually ship `.feu` files under hashed names? The available filelist snapshots do not list any, so this is unconfirmed.
- FC6 save-file crypto: FC5+ binds saves to the Ubisoft account (UPC ID); FC6's exact scheme is unknown and needs RE against the binary.
- `.mab` animation editing remains unsolved for FC6.
