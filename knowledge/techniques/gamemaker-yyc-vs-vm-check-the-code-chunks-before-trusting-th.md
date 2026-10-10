---
kind: technique
title: 'GameMaker YYC vs VM: check the code chunks before trusting the UndertaleModTool route'
status: working
agents:
- Claude Code (deepseek-flash[1m])
humans: ['@genericcooper']
date: '2026-10-06'
links: []
tags:
- gamemaker
- yyc
- data.win
- undertalemodtool
- scan
- detection
- chunk-table
---
# GameMaker YYC vs VM: check the code chunks before trusting the UndertaleModTool route

> `um scan` reports a GameMaker bytecode version for VM and YYC builds alike, and routes both to
> UndertaleModTool. On a YYC build that route is dead, because the GML was compiled into the executable and
> the data file has no code. Detect it in one pass over the chunk table before planning any work.

## When to use it

Immediately after `um scan` says `engine: gamemaker`, and before designing a mod around
UndertaleModTool. It costs one file read and it decides whether the project is a data edit or native
reverse engineering (`native.md`).

`um scan` currently reports `bytecode_version` for YYC builds too, because that field is read from the GEN8
chunk and GEN8 is present in both export types. Bytecode version is a build setting, not evidence that code
is editable. See Gotcha 1.

## How

Walk the FORM chunk table and look at the **`CODE` chunk** (`VARI` and `FUNC` travel with it; `FEAT` is GM2022.8+
feature flags, not code).

- **Present, length > 0** -> GML VM. UndertaleModTool can decompile, edit and recompile GML.
- **Absent (bytecode 17) or length 0 (bytecode <= 16)** -> YYC. The code is native, in the executable.

Chunk framing: at offset 8 the chunk list begins. Each chunk is a 4-byte ASCII name, a little-endian
`uint32` length, then `length` bytes of data, so the next chunk starts at `pos + 8 + length`. A correctly
walked table lands exactly on the file size.

```python
import struct

def gm_chunks(path):
    b = open(path, "rb").read()
    assert b[:4] == b"FORM", "not a GameMaker data file"
    pos, chunks = 8, []
    while pos + 8 <= len(b):
        name = b[pos:pos + 4]
        try:
            text = name.decode("ascii")
        except UnicodeDecodeError:
            break
        if not text.isalnum():
            break
        length = struct.unpack_from("<I", b, pos + 4)[0]
        chunks.append((text, length))
        pos += 8 + length
    return chunks, pos == len(b)          # ([(name, length)], walk was complete)

chunks, complete = gm_chunks(r"...\data.win")
is_yyc = not dict(chunks).get("CODE")   # absent, or empty in bytecode <= 16 YYC builds
```

Confirm with the tool itself. UndertaleModTool's `info` prints the verdict outright:

```
UndertaleModCli.exe info <data.win>
  Is GMS2 - True
  Is YYC - True
```

Measured on four GameMaker titles, 2026-10-06. All four walks completed exactly at file size:

| Game | CODE / VARI / FUNC / FEAT | Verdict | data.win | biggest .exe |
|---|---|---|---|---|
| Cook, Serve, Delicious! 3?! | all present | GML VM | 924,353,372 | 8,870,400 |
| Loop Hero | all absent | YYC | 6,892,268 | 25,232,896 |
| Katana ZERO | all absent | YYC | 95,226,204 | 29,023,232 |
| Tormentor X Punisher | all absent | YYC | 166,249,210 | 7,951,872 |

## Gotchas

1. **`um scan` gives the UndertaleModTool route for YYC builds.** **Symptom:** the scan says
   `engine: gamemaker`, `bytecode_version: 17`, route "UndertaleModTool: decompile/edit GML, sprites and
   rooms in data.win", with no warning. **Cause:** the detector reads the bytecode version out of GEN8,
   which exists in YYC exports as well. **Fix:** check the `CODE` chunk yourself (absent or zero-length = YYC); treat YYC as
   `native.md`. The playbook already says the right thing ("The YYC (compiled) export is native code, so
   treat that as native.md") - the gap is in detection, not in the knowledge.

2. **Executable size is not a discriminator.** The intuition is that YYC compiles code into the exe so the
   exe will be large. Tormentor X Punisher is YYC with a 7.9 MB exe, indistinguishable from Cook, Serve,
   Delicious! 3?!'s 8.9 MB VM runner. Use the chunk table, not sizes.

3. **`info` succeeding does not mean assets are moddable.** UndertaleModTool's `info` loads a YYC file and
   prints a full asset census (Loop Hero: 1,216 sprites, 10 rooms, 982 scripts; Katana ZERO: 2,193 sprites,
   193 rooms), which reads like asset modding is available. It is not, through the CLI: `dump --sprites`
   exits with *"The game was made with YYC (YoYo Compiler), which means that the code was compiled into the
   executable. There is thus no code to dump. Exiting."*, and `replace -c UMT_REPLACE_ALL` throws
   `System.NullReferenceException` at `Program.Replace`. **Cause:** the CLI's export and edit paths gate on
   code entries existing. **Fix:** on YYC, do not budget for CLI asset edits; go native, or drive
   `UndertaleModLib` directly from a custom C# script.

4. **Test on a copy.** The toolkit's rule stands: back up `data.win` first, and distribute mods as xdelta
   patches rather than a modified data file. A YYC `data.win` can still be large and slow to replace.

## Seen in

No game notes yet. This note came out of a Katana ZERO x Loop Hero mashup feasibility check, where both
guests turned out to be YYC and the intended UndertaleModTool route was unavailable for either. Versions
used: UndertaleModTool CLI 0.9.2.0 (Windows), GameMaker bytecode v17 across all four titles.
