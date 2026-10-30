# Unpacking fully-compressed UE3 `.upk` packages

Some UE3 games ship **fully compressed** packages: an uncompressed summary, then the rest of the file in
compressed chunks (LZO here). Tools that can't decompress them stop at the header:

- **UELib** parses the header but its package decompressor is a stub (`CompressedChunkBlock.Decompress`
  just returns the size), so `UnrealPackage.Deserialize` returns early and you get `Exports=0`. UE Explorer
  is built on UELib.
- **UPKUtils `DecompressLZO.exe`** only accepts the XCOM and Batman package versions. Others fail with
  "Bad package version!" (Dishonored, build 801/30, included).

**Try the community tool first:** Gildor's
[Unreal Package Decompressor](https://www.gildor.org/downloads) (`decompress`, from UE Viewer;
[source](https://github.com/gildor2/UEViewer/tree/master/Tools/PackageUnpack)). It handles LZO, zlib and
LZX for the games UE Viewer supports, and writes a clean package with the compression table removed. UE
Viewer lists Dishonored as supported; the decompressor wasn't tried on it for this reference.

`unpack_upk.py` is a small Python fallback for **LZO** packages (`CompressionFlags` 2; it refuses zlib and
LZX), written to get a package UELib can read. The same chunk layout, and what to do when LZO C extensions
won't build, are in the field note `knowledge/techniques/reading-ue3-gearbox-games-offline.md`
(`um kb search ue3`).

## Format (verified: Dishonored, build 801/30)

```
header @0:  tag 0x9E2A83C1 | FileVersion | LicenseeVersion | HeaderSize | ... tables
            CompressionFlags(4) | CompressedChunks count(4) | chunk table[]
chunk table: 16-byte records — (UncompressedOffset, UncompressedSize, CompressedOffset, CompressedSize)
each chunk @CompressedOffset:
    FCompressedChunkHeader { Tag(4)=0x9E2A83C1, ChunkSize(4)=0x20000,
                             summary { CompSize(4), UncompSize(4) },
                             N * { CompSize(4), UncompSize(4) } }
    then N LZO blocks (CompressionFlags 2 = LZO; 1 = ZLIB; 4 = LZX).
```

The `CompressionFlags`/chunk-table offset **varies per package** (it depends on earlier summary
fields), so the script auto-detects it by checking that chunks chain correctly.

## Use

Work on copies outside the game folder.

```bash
uv run --python 3.12 --with minilzo python unpack_upk.py <in.upk> <out.upk>
```

Then, to read it with UELib, clear **only** the `CompressionFlags` dword (leave the chunk
count/table in place) so `UnrealPackage.Deserialize` no longer returns early:

```python
import struct
p = 'DishonoredGame.fixed.upk'; OFF = 0x79   # printed by the script
d = bytearray(open(p, 'rb').read()); struct.pack_into('<I', d, OFF, 0)
open(p, 'wb').write(d)
```

After that, `Exports` populates and you can dump classes and functions with UELib or browse them in UE
Explorer. The output keeps the original summary and its chunk table, so treat it as input for UELib. For a
package other tools can load, use Gildor's decompressor.

## Notes

- Depends on the PyPI `minilzo` package (GPL-2.0), which `uv` fetches at run time. It's a C extension
  published only as source, so `uv` builds it and needs a C compiler (on Windows, the MSVC Build Tools).
- Extracted assets/scripts are the user's own game data — do not redistribute.
