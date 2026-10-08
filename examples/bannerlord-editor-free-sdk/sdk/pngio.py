"""A small PNG reader and writer on numpy and zlib, so the SDK needs no imaging library.

  read_png(path)      -> {"rgba": (h, w, 4) uint8, "mode": "L" | "LA" | "RGB" | "RGBA" | "P", "alpha": bool, "size": (w, h)}
  write_png(path, a)  a = (h, w), (h, w, 3) or (h, w, 4) uint8
  resize(rgba, w, h)  area average when shrinking (what mip chains use), bilinear when enlarging

Reads non-interlaced PNGs of 1, 2, 4, 8 and 16 bits (16 bit keeps the high byte). Interlaced (Adam7) files are refused.
"""
import struct, sys, zlib
import numpy as np


def _unfilter(raw, h, stride, bpp):
    """Undo PNG scanline filters. raw = h rows of (1 filter byte + stride bytes)."""
    out = np.zeros((h, stride), np.uint8)
    prev = np.zeros(stride, np.uint8)
    mv = memoryview(raw)
    for y in range(h):
        base = y * (stride + 1)
        f = mv[base]
        line = np.frombuffer(mv[base + 1:base + 1 + stride], np.uint8)
        if f == 0:
            cur = line.copy()
        elif f == 1:   # Sub: running sum along the row, per channel
            cur = np.empty(stride, np.uint8)
            for c in range(bpp):
                cur[c::bpp] = np.cumsum(line[c::bpp], dtype=np.uint8)
        elif f == 2:   # Up
            cur = (line + prev).astype(np.uint8)
        elif f == 3:   # Average
            cur = bytearray(line.tobytes()); p = prev.tolist()
            for i in range(stride):
                a = cur[i - bpp] if i >= bpp else 0
                cur[i] = (cur[i] + ((a + p[i]) >> 1)) & 255
            cur = np.frombuffer(bytes(cur), np.uint8)
        elif f == 4:   # Paeth
            cur = bytearray(line.tobytes()); p = prev.tolist()
            for i in range(stride):
                a = cur[i - bpp] if i >= bpp else 0
                b = p[i]
                c = p[i - bpp] if i >= bpp else 0
                pa = abs(b - c); pb = abs(a - c); pc = abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                cur[i] = (cur[i] + pr) & 255
            cur = np.frombuffer(bytes(cur), np.uint8)
        else:
            raise ValueError("PNG filter type %d" % f)
        out[y] = cur
        prev = cur
    return out


def read_png(path):
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG: " + path)
    o = 8; idat = []; plte = None; trns = None; ihdr = None
    while o < len(data):
        n, = struct.unpack_from(">I", data, o); tag = data[o + 4:o + 8]; body = data[o + 8:o + 8 + n]; o += 12 + n
        if tag == b"IHDR": ihdr = struct.unpack(">IIBBBBB", body)
        elif tag == b"PLTE": plte = np.frombuffer(body, np.uint8).reshape(-1, 3)
        elif tag == b"tRNS": trns = body
        elif tag == b"IDAT": idat.append(body)
        elif tag == b"IEND": break
    if ihdr is None: raise ValueError("PNG without IHDR")
    w, h, depth, ctype, _, _, interlace = ihdr
    if interlace: raise ValueError("interlaced PNG (re-save it without interlacing)")
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bits = depth * chans
    stride = (w * bits + 7) // 8; bpp = max(1, bits // 8)
    raw = zlib.decompress(b"".join(idat))
    rows = _unfilter(raw, h, stride, bpp)
    if depth == 8: px = rows.reshape(h, w, chans)
    elif depth == 16: px = rows.reshape(h, w * chans, 2)[:, :, 0].reshape(h, w, chans)
    else:
        bitsarr = np.unpackbits(rows, axis=1)[:, :w * depth * chans].reshape(h, w * chans, depth)
        vals = np.zeros((h, w * chans), np.uint16)
        for k in range(depth): vals = (vals << 1) | bitsarr[:, :, k]
        px = (vals if ctype == 3 else vals * (255 // ((1 << depth) - 1))).astype(np.uint8).reshape(h, w, chans)
    if ctype == 0:
        mode = "L"; rgba = np.concatenate([np.repeat(px, 3, 2), np.full((h, w, 1), 255, np.uint8)], 2); alpha = False
        if trns: alpha = True   # colour-key transparency is not applied; the flag only tells the writer to keep an alpha channel
    elif ctype == 2:
        mode = "RGB"; rgba = np.concatenate([px, np.full((h, w, 1), 255, np.uint8)], 2); alpha = bool(trns)
    elif ctype == 3:
        mode = "P"; pal = np.zeros((256, 4), np.uint8); pal[:, 3] = 255
        pal[:len(plte), :3] = plte
        if trns: pal[:len(trns), 3] = np.frombuffer(trns, np.uint8)
        rgba = pal[px[:, :, 0]]; alpha = trns is not None
    elif ctype == 4:
        mode = "LA"; g = px[:, :, :1]; rgba = np.concatenate([np.repeat(g, 3, 2), px[:, :, 1:]], 2); alpha = True
    else:
        mode = "RGBA"; rgba = px.copy(); alpha = True
    return {"rgba": np.ascontiguousarray(rgba), "mode": mode, "alpha": alpha, "size": (w, h), "depth": depth}


def write_png(path, a):
    a = np.asarray(a)
    if a.dtype != np.uint8: a = np.clip(a, 0, 255).astype(np.uint8)
    if a.ndim == 2: a = a[:, :, None]
    h, w, c = a.shape
    ctype = {1: 0, 2: 4, 3: 2, 4: 6}[c]
    raw = b"".join(b"\x00" + a[y].tobytes() for y in range(h))
    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def _weights(n, m):
    """(m, n) float32 resampling matrix along one axis."""
    W = np.zeros((m, n), np.float64)
    if m <= n:   # area average
        s = n / m
        for j in range(m):
            lo, hi = j * s, (j + 1) * s
            for i in range(int(lo), min(n, int(np.ceil(hi)))):
                W[j, i] = max(0.0, min(hi, i + 1) - max(lo, i))
        W /= W.sum(1, keepdims=True)
    else:        # bilinear, pixel centres
        for j in range(m):
            x = (j + 0.5) * n / m - 0.5
            i0 = int(np.floor(x)); t = x - i0
            W[j, min(max(i0, 0), n - 1)] += 1 - t
            W[j, min(max(i0 + 1, 0), n - 1)] += t
    return W.astype(np.float32)


def resize(img, w, h):
    """img (H, W, C) uint8 -> (h, w, C) uint8. Rounds half up like the usual imaging libraries. A 4-channel image is resized
    with its colour weighted by alpha (premultiplied), so transparent pixels do not bleed into the mips."""
    img = np.asarray(img)
    H, W, C = img.shape
    if (W, H) == (w, h): return img.copy()
    Wy, Wx = _weights(H, h), _weights(W, w)
    f = img.astype(np.float32)
    if C == 4:
        a = f[:, :, 3:4] / 255.0
        f = np.concatenate([f[:, :, :3] * a, f[:, :, 3:4]], 2)
    out = np.einsum("iw,jwc->jic", Wx, np.einsum("jh,hwc->jwc", Wy, f))
    if C == 4:
        alpha = out[:, :, 3:4]
        rgb = np.where(alpha > 1e-6, out[:, :, :3] / np.maximum(alpha / 255.0, 1e-6), 0.0)
        out = np.concatenate([rgb, alpha], 2)
    return np.clip(np.floor(out + 0.5), 0, 255).astype(np.uint8)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    r = read_png(sys.argv[1]); print(r["size"], r["mode"], "alpha" if r["alpha"] else "opaque")
