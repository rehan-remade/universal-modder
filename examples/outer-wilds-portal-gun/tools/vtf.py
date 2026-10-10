"""Decode the top mip of a Valve Texture Format (VTF 7.0-7.5) file to a Pillow RGBA image."""
import struct

from PIL import Image

# format id -> (bytes per 4x4 block or per pixel, is_block, decoder)
DXT1, DXT3, DXT5 = 13, 14, 15
PIXEL = {0: ("RGBA", 4), 1: ("ABGR", 4), 2: ("RGB", 3), 3: ("BGR", 3), 5: ("L", 1), 6: ("LA", 2),
         12: ("BGRA", 4), 16: ("BGRX", 4), 11: ("ARGB", 4)}


def _size(fmt, w, h):
    if fmt == DXT1:
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 8
    if fmt in (DXT3, DXT5):
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 16
    if fmt in PIXEL:
        return w * h * PIXEL[fmt][1]
    raise ValueError(f"unsupported VTF format {fmt}")


def decode(data, frame=0):
    if data[:4] != b"VTF\0":
        raise ValueError("not a VTF")
    major, minor, header_size = struct.unpack_from("<III", data, 4)
    w, h, flags, frames, _first = struct.unpack_from("<HHIHH", data, 16)
    hi_fmt, = struct.unpack_from("<i", data, 52)
    mips = data[56]
    lo_fmt, = struct.unpack_from("<i", data, 57)
    lo_w, lo_h = data[61], data[62]
    faces = 6 if flags & 0x4000 else 1  # envmap
    depth = struct.unpack_from("<H", data, 63)[0] if minor >= 2 else 1
    depth = max(1, depth)

    if minor >= 3:
        nres, = struct.unpack_from("<I", data, 68)
        off = None
        for i in range(nres):
            tag, rflags, roff = struct.unpack_from("<3sBI", data, 80 + 8 * i)
            if tag == b"\x30\x00\x00":
                off = roff
        if off is None:
            raise ValueError("VTF without image resource")
    else:
        off = header_size + (_size(lo_fmt, lo_w, lo_h) if lo_fmt >= 0 and lo_w else 0)

    # mips are stored smallest first; skip down to mip 0
    for m in range(mips - 1, 0, -1):
        mw, mh = max(1, w >> m), max(1, h >> m)
        off += _size(hi_fmt, mw, mh) * frames * faces * depth
    one = _size(hi_fmt, w, h)
    off += one * faces * depth * min(frame, frames - 1)
    raw = data[off:off + one]

    if hi_fmt in (DXT1, DXT3, DXT5):
        n = {DXT1: 1, DXT3: 2, DXT5: 3}[hi_fmt]
        bw, bh = (w + 3) // 4 * 4, (h + 3) // 4 * 4
        img = Image.frombytes("RGBA", (bw, bh), raw, "bcn", n)
        if (bw, bh) != (w, h):
            img = img.crop((0, 0, w, h))
        return img
    mode, _bpp = PIXEL[hi_fmt]
    if mode in ("RGBA", "RGB", "L", "LA"):
        return Image.frombytes(mode, (w, h), raw).convert("RGBA")
    if mode == "BGR":
        return Image.frombytes("RGB", (w, h), raw, "raw", "BGR").convert("RGBA")
    if mode == "BGRX":
        return Image.frombytes("RGB", (w, h), raw, "raw", "BGRX").convert("RGBA")
    return Image.frombytes("RGBA", (w, h), raw, "raw", mode)
