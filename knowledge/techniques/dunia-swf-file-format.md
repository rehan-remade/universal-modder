---
kind: technique
title: "Adobe SWF and Ubisoft FEU (Flash Export Unit) format"
game: "Far Cry 6"
games_also: ["Far Cry 5", "Far Cry 4", "Watch Dogs (Disrupt)", "Far Cry New Dawn"]
game_version: "see note"
platform: windows
engine: unknown
route: data
tools: ["JPEXS FFDec", "FCBConverter", "base64 SWF Texture Tool"]
anti_cheat: "Format reference only; no anti-cheat interaction."
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links:
  - "https://open-flash.github.io/mirrors/swf-spec-19.pdf"
tags: ["swf", "feu", "flash", "dunia", "disrupt", "ui", "file-format"]
---
# Adobe SWF and Ubisoft FEU (Flash Export Unit) format

> Ubisoft's Dunia and Disrupt engines render in-game UI with Adobe Flash. The shipped container is `.feu` (Flash Export Unit): an ordinary SWF with its signature bytes renamed. Understanding the SWF container — header, tag stream, and dictionary — is what makes UI modding possible. This note summarizes the format at the level needed to convert, edit, and repack.

## Setup

- The Adobe SWF specification (v19, 2012) is the authoritative reference: https://open-flash.github.io/mirrors/swf-spec-19.pdf (a converted copy is kept locally, unpublished).
- A Flash decompiler/compiler: **JPEXS FFDec** (`ffdec-cli.jar`) opens `FWS`/`CWS` SWF, `.gfx`, and the `.feu` container.
- A repacker for the surrounding archive: **FCBConverter** (see the Far Cry 6 game note).

## Route and why

- The UI is data, so the route is **data**: convert the container, edit the movie, recompile. No code hook is required.
- The `.feu` wrapper is trivial (three bytes), so the real work is understanding the SWF tag stream — which is exactly what the spec provides.

## How the format works

**The FEU wrapper.** A `.feu` file is a standard SWF whose 3-byte signature `FWS` is replaced by `UEF` (bytes `55 45 46`). Byte 3 is the SWF version (`0x08`, Flash 8); bytes 4–7 are a little-endian u32 uncompressed length; everything after is an unmodified SWF, compressed per the normal SWF rules. Convert with a one-region byte edit:

```
sed -i '1s/UEF/FWS/' file.feu    # FEU -> SWF
sed -i '1s/FWS/UEF/' file.swf    # SWF -> FEU
```

**SWF header.** Signature UI8 (`F` = uncompressed `FWS`, `C` = zlib `CWS` from SWF 6, `Z` = LZMA `ZWS` from SWF 13) followed by `W` and `S`, then Version UI8, FileLength UI32 (uncompressed size), FrameSize RECT (twips; `Xmin`/`Ymin` are 0, `Xmax`/`Ymax` give width/height), FrameRate UI16 (8.8 fixed-point fps), and FrameCount UI16. Tagged data blocks follow.

**Tags.** Each tag begins with a `RECORDHEADER`: a `TagCodeAndLength` UI16 whose upper 10 bits are the type and lower 6 bits the length. When the length needs to exceed 62, the low 6 bits are set to the marker `0x3F` and a UI32 Length follows (long form). Two tag families matter:

- **Definition tags** (`DefineShape`, `DefineSprite`, `DefineEditText`, …) create an object and register it in the dictionary under a unique **CharacterId**.
- **Control tags** (`PlaceObject`, `PlaceObject2/3`, `ShowFrame`, `RemoveObject`, …) place and manipulate instances on the display list.

A definition must appear before any control tag that references its CharacterId. For SWF 8 and later the **FileAttributes tag must be first**, and the **End tag is always last**. The player processes tags until a `ShowFrame`, at which point it renders the current display list.

**Dunia-specific content.** FEU movies are Flash movieclips driven by ActionScript 2 classes (names such as `driver.LoadableContainer`, `driver.gamehud.Gh_*`). They reference engine resources by string path — fonts `*.ffd`, supertextures `*.bfd`. UI state that a modder cares about (for example weapon-wheel icons) is carried either in normal definition tags or in a custom `<UnknownTag id="0xF6">` whose payload is a Base64-encoded descriptor.

**Base64 icon descriptor** (little-endian), as decoded by the (unpublished) SWF Texture Tool:

```
0x00  u16  Character ID
0x02  u16  Width
0x04  u16  Height
0x06  ...  null-terminated UTF-8 texture path
```

## Build steps

1. Convert `.feu` → `.swf` (byte edit above).
2. Open in JPEXS FFDec; edit shapes, labels, actions, or the custom `0xF6` payload.
3. Recompile `.swf` → `.feu` (reverse byte edit) and merge back into the archive.

## Verification

- The header and tag structure are taken directly from the Adobe SWF specification (v19, 2012; link above).
- The FEU wrapper and the Base64 descriptor layout come from community notes (Ekey on XeNTaX, BIRDdude12) and the SWF Texture Tool source.
- **Not independently reproduced end-to-end by this agent.** Status: in-progress; a first-hand FEU round trip is still owed.

## Gotchas

- `UEF` replaces **all three** signature bytes of `FWS`, not just the first.
- A definition tag must precede any control tag that uses its CharacterId; inserting a `PlaceObject` before its shape will fail.
- `FileAttributes` must be the first tag on SWF 8+; `End` must be last.
- The custom icon payload is Base64 with padding quirks (see the Far Cry 6 note): trailing `AAAA`, occasional `=`, and a 22-character filename works best.

## Assets

- A local conversion of the Adobe SWF v19 spec (unpublished; original at the link above).

## Cost and time

- Not recorded.

## Open questions

- Which SWF version(s) the various Dunia/Disrupt titles actually emit (FEU observed at version `0x08`).
- Whether all UI is FEU, or some titles use plain `.swf` / `.gfx` alongside it.
