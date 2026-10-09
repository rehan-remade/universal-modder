---
kind: technique
title: "REDengine container and asset formats across Witcher 2/3 and Cyberpunk 2077 (CR2W, .bundle/.cache, RDAR/KARK)"
tools: ["Gibbed RED Tool", "QuickBMS (w2_dzip_unpack.bms, witcher3.bms, cyberpunk_2077.bms)", "Lua-utils-for-Witcher-3", "witcher2_texture_converter", "CP77Tools (rfuzzo)", "Wolven-kit / WolvenKit (Traderain)", "W3SavegameEditor (Atvaark)", "Noesis fmt_CP77mesh.py (alphaZ)", "OodleSharp (Crauzer)"]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - "https://github.com/gibbed/Gibbed.RED"
  - "https://github.com/WolvenKit/WolvenKit"
  - "https://wiki.redmodding.org/"
tags: ["redengine", "cr2w", "witcher2", "witcher3", "cyberpunk2077", "rdar", "kark", "oodle", "xbm", "w3strings", "save", "archive", "file-format"]
---

# REDengine container and asset formats across Witcher 2/3 and Cyberpunk 2077 (CR2W, .bundle/.cache, RDAR/KARK)

> Three CDPR games share a format lineage: Witcher 2 (REDengine 2) uses `.dzip`
> archives with CR2W asset files; Witcher 3 uses `.bundle` + `.cache` with CR2W
> version 162; Cyberpunk 2077 (REDengine 4) swaps to `.archive` with `RDAR`
> v12 + `KARK`/Oodle. Across all three, textures are CR2W-wrapped DDS-without-header,
> and the readable path is: unpack archive → decompile CR2W. Knowing which
> generation a file belongs to explains most "tool says unsupported version" failures.

## When to use it
- You are extracting or editing any CDPR game asset (models, textures,
  localization, saves) and need the container + CR2W layout.
- You need to pick the right generation's tool: `.dzip` (W2), `.bundle`/`.cache`
  (W3), `.archive`/RDAR (CP2077).
- You hit a version-gated tool (REDkit, CR2W viewers) and need to know the
  version numbers involved.

## How

### Archives by generation
| Game | Container | Notes |
|------|-----------|-------|
| Witcher 2 | `.dzip` (`pack0.dzip`) | Gibbed RED Tool, QuickBMS `w2_dzip_unpack.bms` |
| Witcher 3 | `.bundle` (data) + `.cache` (bulk textures) | QuickBMS `witcher3.bms` handles `.bundle`; `.cache` needs Lua-utils |
| Cyberpunk 2077 | `.archive` (`RDAR` v12) | Oodle-compressed entries behind `KARK`; CP77Tools/QuickBMS |

CP2077 `.archive` header (IceReaper 010 template):
```
struct Header {
  char  RDAR[4];
  int   version;          // 12
  int64 fileSystemOffset;
  int64 fileSystemSize;
  int64 unk2;
  int64 fileSize;
  int   unk3[33];
};
```
Compressed entries start with `KARK`; decompress with **Oodle** via the game's
`oo2core_<version>_win64.dll` or `oo2ext_7_win64.dll`. QuickBMS uses
`comtype oodle`; OodleSharp wraps the DLL for C#.

Witcher 3 texture cache extraction (hhrhhr):
`lua unpack_textures.lua texture.cache output_dir` (Lua 5.3 + lua-zlib), then add
DDS headers with `mod_dds_header.lua`.

### CR2W assets
`.xbm` (textures), `.w2mesh`/`.w2ent` (W2 models), `.w2mesh`/`.mesh` (W3/CP77
models) are all **CR2W** files: magic `CR2W`, a version, and a string table that
names the struct and its fields. W3 assets are **version 162 (0xA2)**; W2 REDkit
supports only up to **115 (0x73)**.

A `.xbm` is CR2W wrapping **DDS data with no DDS header** (DXT1/DXT5). The
shortcut is to strip the CR2W header and add a DDS one. Documented
`CBitmapTexture` fields: `width` (Uint32), `height` (Uint32), `compression`
(`ETextureCompression` = `TCM_DXTNoAlpha`), `textureGroup` (`CName`, e.g.
`CharacterDiffuse`), `residentMipIndex` (Uint8), `textureCacheKey` (Uint32).
In W3, `.xbm` files themselves hold only a small preview — the real textures are
in `content?/texture.cache`.

### Localization and voice
- `.w3strings` (W3) is obfuscated UTF-16 with HTML tags, described as "almost
  clean text" but **not a simple XOR** (fixed vs increment key undetermined).
  Haoose published an unpacker/repacker.
- `.w2speech` (W2) audio reads as MPEG layer 2 @ 48000 Hz; VO names follow
  `VO_<voiceTag>_<scene>_<line>` (e.g. `VO_TRIS_300202_0343`).
- W3 `.w3speech` (per-language, e.g. `enpc.w3speech`) differs entirely from W2
  and is **not** in `.cache`.

### Save files (`.sav`)
REDengine saves are **one file split into 1,048,576-byte (0x100000) parts**, each
**LZ4-compressed** (LZ4 r131 worked for both directions at default settings). The
header "checksum" is actually the **uncompressed file length in bytes**. The
decompressed payload resembles **binary XML**. Editing works but breaks the game
easily. Tools: `W3SavegameEditor`; W2 refs Gibbed.RED and 13xforever's SaveFormat.

### CP2077 model stack
| Ext | Role |
|-----|------|
| `.mesh` | CR2W mesh definition (external data refs + file links) |
| `.buffer` / `.mesh.N.buffer` | Oodle-decompressed vertex/index blocks; Noesis auto-loads the matching one |
| `.rig` | skeleton/bone hierarchy (a mesh may use several rigs) |
| `.morphtarget` | facial morph targets under `.../player_base_heads/` |
| `.mi` / `.mt` / `.ml*` | material instance / material / layers |

**Unbundle vs uncook** (CP77Tools): `unbundle` extracts `.mesh` files but the
vertex data stays inside Oodle blocks *within* them; `uncook` decompresses that
into sidecar `.buffer` files that Noesis needs. `--forcebuffers` helps some
meshes. CP77Tools v1.0+ stopped writing buffers (use 0.2.0.1 with old Noesis scripts).

### CP2077 audio (Wwise)
- `.wem` format tags: `0x0001` PCM and `0xFFFE` WAVE_EXTENSIBLE → WEMConverter/
  vgmstream; `0xFFFF` non-standard Ogg Vorbis → ww2ogg.
- Some files have a PCM RIFF header but contain **Opus** — detect `"OggS"`
  (`4F 67 67 53`) at offset `0x2C` and strip everything before it.
- `.opuspak` archives → OpusUnpack (ninearts) → playable `.wem`.
- `.bnk` car-sound banks use a **new Wwise variation** that Wwise Extractor,
  bnkextr/ww2ogg/revorb and vgmstream could not decode.

### Filenames are hashed
CP2077 archives store filenames as hashes (as do Watch Dogs, Hitman, RE Engine).
Tools need a hash→name dictionary: eprilx mapped ~600k names (~50k missing);
Ekey mapped **1,307,466** hashes across archives (e.g. `basegame_3_nightcity`
99%, `lang_en_text` 100%). Merged into WolvenKit/CP77Tools.

## Gotchas
1. **QuickBMS `witcher3.bms` extracts nothing for textures.** **Cause:** it does
   not handle `.cache` files; most `.xbm` files hold only a preview image.
   **Fix:** extract `.cache` with Lua-utils-for-Witcher-3.
2. **Lua-utils fails with `bad argument #2 to 'unpack'` / `'=' expected near 'skip'`.**
   **Cause:** requires **Lua 5.3** (`string.unpack`, `goto`), and on 64-bit
   platforms `"<L"` is wrong for 4-byte LE ints. **Fix:** run Lua 5.3 and use `"<I4"`.
3. **REDkit refuses a W3 asset: "Version 162 is not supported."** **Cause:** W2
   REDkit caps at version 115. **Fix:** use Wolven-kit/RedTools, not W2 REDkit;
   do not fake the version (`0xA2` → `0x59`/`0x73` crashes REDkit).
4. **Noesis: "Wrong buffer file" / can't preview or export a CP77 mesh.**
   **Cause:** you only unbundled; vertex data is still inside Oodle blocks in the
   `.mesh`. **Fix:** uncook (with the game's Oodle DLL) and keep the `.buffer`
   next to the `.mesh`.
5. **CP77 mesh has no `.buffer` after extraction.** **Cause:** CP77Tools v1.0+
   stopped producing buffers. **Fix:** use CP77Tools 0.2.0.1 for old Noesis scripts.
6. **CP77 normal maps look wrong / RG-only.** **Cause:** the engine stores normal
   maps with no blue channel and flips the green channel. **Fix:** expected
   behaviour; invert/flip green on FBX round-trips.
7. **CP77 texture repack crashes before the start screen.** **Cause:** repacking
   without uncooking. **Fix:** uncook first; the later official toolkit handles textures.
8. **Witcher save edits break the game.** **Cause:** binary-XML payload with
   interdependent state; header "checksum" is really uncompressed length.
   **Fix:** prefer in-game state changes; back up before editing.
9. **W3 `.w3speech` tools fail / W2 tools do nothing.** **Cause:** W3 voice format
   differs entirely from W2 and is not in `.cache`. **Fix:** use W3-specific tools
   on `enpc.w3speech`-style files.

## Seen in
- The Witcher 2 (REDengine 2): `.dzip`, `.w2ent`/`.w2mesh`, `.xbm`, `.w2speech`, `.usm`.
- The Witcher 3 (CR2W v162): `.bundle`/`.cache`, `.xbm`, `.w3strings`, `.w3speech`, `.sav`.
- Cyberpunk 2077 (REDengine 4): `.archive` (RDAR/KARK/Oodle), `.mesh`/`.buffer`/`.rig`/
  `.morphtarget`, `.xbm`/`.mi`, Wwise `.wem`/`.opuspak`/`.bnk`.
