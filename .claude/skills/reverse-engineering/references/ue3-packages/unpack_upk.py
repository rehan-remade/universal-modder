#!/usr/bin/env python3
"""
unpack_upk.py — decompress a fully-compressed, LZO-compressed Unreal Engine 3 .upk.

Many UE3 games ship "fully compressed" (LZO) packages that some tools can't read:
UELib's package decompressor is a stub, and UPKUtils' DecompressLZO only accepts XCOM and
Batman package versions (Dishonored, build 801/30, is rejected). Gildor's decompress (from
UE Viewer) is the community tool for these; this is a small Python fallback for LZO packages,
meant for reading the result with UELib. Only LZO (CompressionFlags 2) is handled.

Usage (minilzo is a C extension built from source, so it needs a C compiler):
    uv run --python 3.12 --with minilzo python unpack_upk.py <in.upk> <out.upk>

Then, to read the contents with UELib, clear ONLY the CompressionFlags dword in the output
(keep the chunk count/table) so UnrealPackage.Deserialize stops returning early. Pass the
output file and the CompressionFlags offset the script printed (0x79 in this example):

    python - DishonoredGame.fixed.upk 0x79 <<'PY'
    import struct,sys
    p=sys.argv[1]; off=int(sys.argv[2],0); d=bytearray(open(p,'rb').read())
    struct.pack_into('<I',d,off,0); open(p,'wb').write(d)
    PY

Format (verified on Dishonored build 801/30):
  summary @0:  tag 0x9E2A83C1, FileVersion(2), LicenseeVersion(2), HeaderSize(4), ...
               CompressionFlags(4), CompressedChunks count(4), chunk table[]
  chunk table: 16-byte records (UncompressedOffset, UncompressedSize, CompressedOffset, CompressedSize)
  each chunk @CompressedOffset:
      FCompressedChunkHeader { Tag(4)=0x9E2A83C1, ChunkSize(4)=0x20000,
                               summary { CompSize(4), UncompSize(4) },
                               N * { CompSize(4), UncompSize(4) } }
      followed by the LZO blocks.

The CompressionFlags/chunk-table offset varies per package (it depends on earlier summary
fields), so it is auto-detected by validating that chunks chain correctly.
"""
import struct
import sys

SRC_TAG = 0x9E2A83C1


def find_chunk_table(d):
    """Return (flags_offset, count, records) for the first offset that validates."""
    for off in range(0x40, 0x400):
        if off + 8 > len(d):
            break
        flags = struct.unpack_from('<I', d, off)[0]
        if flags not in (1, 2, 4):            # ZLIB / LZO / LZX
            continue
        count = struct.unpack_from('<I', d, off + 4)[0]
        if not (0 < count < 8192):
            continue
        table = off + 8
        if table + count * 16 > len(d):
            continue
        recs = [struct.unpack_from('<IIII', d, table + i * 16) for i in range(count)]
        ok = True
        for i in range(count - 1):
            uo, us, co, cs = recs[i]
            nuo, nus, nco, ncs = recs[i + 1]
            # uncompressed and compressed regions must each be contiguous
            if uo + us != nuo or co + cs != nco:
                ok = False
                break
        if ok and recs and recs[0][2] + sum(r[3] for r in recs) <= len(d) + 8:
            return off, count, recs
    raise SystemExit('could not locate the compressed chunk table')


def unpack(src, dst):
    d = open(src, 'rb').read()
    tag, ver, lic = struct.unpack_from('<IHH', d, 0)
    if tag != SRC_TAG:
        raise SystemExit('not a UE3 package (tag %08X)' % tag)
    off, count, recs = find_chunk_table(d)
    flags = struct.unpack_from('<I', d, off)[0]
    if flags != 2:
        raise SystemExit(f'CompressionFlags={flags}: only LZO (2) is handled here; '
                         'use Gildor\'s decompress for zlib (1) or LZX (4) packages')
    import minilzo
    total = recs[-1][0] + recs[-1][1]
    print(f'version={ver}/{lic} compressionFlags={flags}@0x{off:x} chunks={count} '
          f'table@0x{off+8:x} uncompressed={total}')
    out = bytearray(total)
    first = recs[0][0]
    out[0:first] = d[0:first]                     # uncompressed summary/header region
    for idx, (uo, us, co, cs) in enumerate(recs):
        ctag, chunk_size = struct.unpack_from('<Ii', d, co)
        if ctag != SRC_TAG:
            raise SystemExit(f'chunk {idx}: bad tag {ctag:08X} at 0x{co:x}')
        if chunk_size == 0:
            chunk_size = 0x20000
        _scomp, suncomp = struct.unpack_from('<ii', d, co + 8)
        nblocks = (suncomp + chunk_size - 1) // chunk_size
        pos = co + 16 + nblocks * 8
        data = bytearray()
        for b in range(nblocks):
            bc, bu = struct.unpack_from('<ii', d, co + 16 + b * 8)
            dec = minilzo.decompress(d[pos:pos + bc], bu)
            if len(dec) != bu:
                raise SystemExit(f'chunk {idx} block {b}: got {len(dec)} expected {bu}')
            data += dec
            pos += bc
        if len(data) != us:
            raise SystemExit(f'chunk {idx}: decompressed {len(data)} expected {us}')
        out[uo:uo + us] = data
    open(dst, 'wb').write(out)
    print('wrote', dst, len(out), f'(set CompressionFlags@0x{off:x} to 0 for UELib)')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    unpack(sys.argv[1], sys.argv[2])
