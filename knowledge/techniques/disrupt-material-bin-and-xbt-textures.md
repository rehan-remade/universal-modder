---
kind: technique
title: Disrupt material (.material.bin) and texture (.xbt) formats
game: Watch Dogs
games_also: ["Watch Dogs 2", "Watch Dogs: Legion"]
game_version: "WD1 v7 / 2013 beta v5 / Legion v15"
platform: windows
engine: Disrupt (Dunia 2 fork)
route: asset-only
tools: [WatchDogsMaterialEditor, XbgLab, Gibbed.Disrupt, Blender]
anti_cheat: unknown
status: working
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links: []
tags: [disrupt, watch-dogs, material, shader, texture, xbt, dds, crc32, hashing]
---

# Disrupt material (.material.bin) and texture (.xbt) formats

> Disrupt materials are small header + name + shader + parameter blocks ending
> in a gradient; each parameter is identified by a CRC32 of its name and its
> value is typed. The material references `.xbt` textures, which are a short
> Ubisoft header wrapping a platform-specific payload that is raw DDS on PC.
> Knowing both lets you retarget shader parameters and swap textures without
> touching the engine.

## When to use it

- Changing a material's shader parameters (bloom, tint, gloss, emissive, etc.).
- Swapping or upscaling a texture while keeping the engine's wrapper header.
- Building the name hash needed to add or look up a material parameter.
- Diagnosing an in-game crash caused by a hand-exported `.material.bin`.

## How

### `.material.bin`

Magic `0x004D4154` ("TAM\0"), header size 68 bytes (17 × u32). Version and
endianness are sniffed from the magic *bytes*:

- v7 — WD1 retail, little-endian (bytes `54 41 4D 00`)
- v5 — 2013 beta, big-endian (bytes `00 4D 41 54`)
- v15 — Legion / leak, little-endian

After the 68-byte header:

1. **name** — u32 length, bytes, align to 4.
2. **shader** — u32 length, bytes, then a quirk: `mod = (4 - len % 4) % 4`, and
   if `mod >= 2` two bytes are *moved into* the following InitSettings block.
3. **InitSettings** — u16 plus optional 2 bytes, 2 bytes, u32, then 3 × i32.
4. two unknown bytes (`unk74`, `unk75`), then a u16 parameter count.

Per parameter: a type byte, 4 alignment bytes when the cursor is not 4-aligned,
padding, then `name_hash` = **CRC32(name)**, then the value. Type codes:

```
1  u32 (float stored as raw IEEE-754 bits)   7  enum (u32 CRC)
2  vec2                                      8/9/10  string
3  vec3                                      11  u32
4  vec4
5  i32
6  bool
```

Floats are raw bit patterns, not decimal text. After the parameters there is a
gradient block (aligned u32 flag; if 1: a gradient vector i32, N × 16-byte
vectors, a gradient id, and two unknown bytes), then a trailing u32 and any
remainder.

Names are resolved offline from a companion `materialNames.txt` table mapping
CRC32 → name, so keep that table beside the editor.

The engine's *size words* are strict: the header's words 8, 12 and 14 hold the
gradient-field offset `+ 4 − 32`, and word 9 holds total file size `− 32`. A
widely used `ConvertMaterials.exe` wrote these length words wrong, which caused
in-game crashes until a size-fixer tool corrected them.

### `.xbt` texture

Magic `TBX\0` at `0x00`.

| Offset | Meaning |
|--------|---------|
| 0x04 | u32 platform/build version (`0x92` Legion/BC7, `0x8F` WD1/DXT5) |
| 0x08 | header size (`0x34` / `0x2C`) |
| 0x10 | format id (`0x02000003` BC7, `0x01040401` DXT5, `0x01010101` DX10) |
| 0x14 | format hint |
| 0x18 | metadata; byte at 0x19 encodes mip level (`0xFF010101` high, `0xFF010301` med) |
| 0x1C | asset CRC |

On PC the payload after the header is a raw DDS; on Xbox 360 it is big-endian
and tiled. The safe edit workflow is: strip the header → edit the DDS in any
DDS tool → prepend the original header. Do **not** use a generic `dds2xbt`
utility; it writes a generic header the engine rejects. Treat the header as
opaque bytes you preserve, not regenerate.

## Gotchas

1. **Material loads then the game crashes on use** → header size words wrong →
   the engine reads words 8/12/14 as `offset + 4 − 32` and word 9 as
   `filesize − 32`; run a size-fixer or write those words correctly.
2. **Big-endian material misread** → endianness taken from the version field →
   sniff the magic bytes: `54 41 4D 00` = little-endian, `00 4D 41 54` = big.
3. **Shader name with length ≡ 2 or 3 (mod 4) shifts every later field** →
   the pad quirk moves two bytes into InitSettings → implement the
   `mod = (4 - len % 4) % 4; if (mod >= 2) move 2 bytes` rule.
4. **Parameter never changes anything in game** → wrong hash → the parameter id
   is CRC32 of the name (poly `0xEDB88320`), resolved from `materialNames.txt`.
5. **Texture appears all-white / wrong format** → generic header → preserve the
   original `.xbt` header and only replace the DDS payload; match the format id
   (BC7 vs DXT5).
6. **Floats come out as nonsense integers** → parameters are raw IEEE-754 bit
   patterns → reinterpret the u32 as f32 for types 1–4.

## Seen in

- `WatchDogsMaterialEditor` (`material_bin.py`) — 454-line parser covering all
  three versions and the size-word crash fix.
- `XbgLab` (`MaterialEditor.cs`) — material editing alongside mesh reading.
- `Gibbed.Disrupt` — XBT header facts and the DDS-strip workflow, including the
  "do not use dds2xbt" warning.
- Standalone `material_bin.py` at the Disrupt project root.
