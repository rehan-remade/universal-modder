"""2D sprite tools: turn generated art into the exact frames a game expects.

    um sprite info in.png                               # size, mode, alpha coverage, bbox, colours
    um sprite cutout in.png out.png                     # flat background -> transparent (flood fill from the border)
    um sprite fit in.png out.png --size 64x26           # trim + nearest-neighbour fit into a frame (pixel art)
    um sprite fit in.png out.png --size 38x34 --anchor bottom --smooth
    um sprite pixelate in.png out.png --size 32x32 --colors 16 --outline
    um sprite palette in.png out.png --from ref.png     # snap colours to a game's palette
    um sprite sheet out.png f1.png f2.png ... --cols 4  # pack frames (grid); --vertical for a Terraria-style strip
    um sprite slice sheet.png outdir --frame 32x32      # split a sheet into frames
    um sprite frames in.png outdir --n 3 --kind bob     # quick idle animation from one frame (bob/squash/wobble/flash)
    um sprite team-mask in.png out.png --hue blue       # saturated accent -> player-colour mask (+ desaturated sprite)
    um sprite seamless in.png out.png                   # make a texture tile (offset + cross-blend)
    um sprite tile-preview in.png out.png               # 3x3 tiling preview to check seams
    um sprite preview in.png out.png --scale 4          # checkerboard + scale, for looking at it

Rules of thumb (learned the hard way): generate on a flat background or with real transparency, cut
out with a border flood fill (keeps interior whites like eyes), trim, then scale ONCE with nearest
neighbour to the engine's frame size. Keep facing directions consistent with the engine's convention
(e.g. Terraria items point right, NPC sprites face left). Frame layout comes from the engine's draw code.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path

from um.common import die, need, parse_size


def _pil():
    need("PIL", "pillow")
    from PIL import Image
    return Image


def load(path) -> "Image.Image":
    Image = _pil()
    return Image.open(path).convert("RGBA")


# --------------------------------------------------------------------------- core ops


def border_color(im, k: int = 4):
    """Median colour of the four corners (k x k each): the flat background colour."""
    w, h = im.size
    px = im.load()
    samples = [px[x, y][:3] for cx, cy in ((0, 0), (w - k, 0), (0, h - k), (w - k, h - k)) for x in range(cx, cx + k) for y in range(cy, cy + k)]
    return tuple(sorted(c[i] for c in samples)[len(samples) // 2] for i in range(3))


def cutout(im, tol: int = 28, bg=None, grey: int | None = None, spread: int = 24, holes: bool = False, keep_top: float = 1.0):
    """Flood-fill the background from the image border. tol: colour distance to the background (auto-detected
    from the corners). grey: also treat light unsaturated pixels (min channel >= grey) as background, e.g. a soft
    drop shadow. holes: also clear enclosed background-coloured areas. keep_top < 1 drops the bottom part
    (a shadow under the object)."""
    im = im.copy()
    if im.getextrema()[3][0] < 250 and bg is None:
        # already has transparency: just clear near-invisible pixels
        return im.crop(im.getbbox() or (0, 0, 1, 1))
    im = im.crop((0, 0, im.width, int(im.height * keep_top)))
    bg = bg or border_color(im)
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)

    def is_bg(c):
        r, g, b = c[:3]
        if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) <= tol * 3:
            return True
        return grey is not None and min(r, g, b) >= grey and max(r, g, b) - min(r, g, b) < spread

    q = deque([(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)])
    while q:
        x, y = q.popleft()
        i = y * w + x
        if seen[i]:
            continue
        seen[i] = 1
        c = px[x, y]
        if not is_bg(c):
            continue
        px[x, y] = (c[0], c[1], c[2], 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx]:
                q.append((nx, ny))
    if holes:
        for y in range(h):
            for x in range(w):
                c = px[x, y]
                if c[3] and is_bg(c):
                    px[x, y] = (c[0], c[1], c[2], 0)
    return im.crop(im.getbbox() or (0, 0, 1, 1))


def hard_alpha(im, thresh: int = 128):
    """Binary alpha (pixel art, BC1 punch-through): >= thresh opaque, else clear."""
    r, g, b, a = im.split()
    a = a.point(lambda v: 255 if v >= thresh else 0)
    return _pil().merge("RGBA", (r, g, b, a))


def trim(im, pad: int = 0):
    bbox = im.getbbox()
    if not bbox:
        return im
    im = im.crop(bbox)
    if pad:
        out = _pil().new("RGBA", (im.width + 2 * pad, im.height + 2 * pad))
        out.paste(im, (pad, pad))
        return out
    return im


def fit(im, w: int, h: int, anchor: str = "center", smooth: bool = False, allow_upscale: bool = True):
    """Trim, scale to fit inside w x h (nearest neighbour unless smooth), place on a transparent frame."""
    Image = _pil()
    im = trim(im)
    s = min(w / im.width, h / im.height)
    if not allow_upscale:
        s = min(s, 1.0)
    small = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS if smooth else Image.NEAREST)
    frame = Image.new("RGBA", (w, h))
    x = (w - small.width) // 2
    y = {"center": (h - small.height) // 2, "bottom": h - small.height, "top": 0}[anchor]
    frame.paste(small, (x, y))
    return frame


def pixelate(im, w: int, h: int, colors: int | None = 16, outline: tuple | None = None, alpha_thresh: int = 110):
    """Area-average down to w x h (fit, keeps aspect), hard alpha, optional palette + 1px outline."""
    Image = _pil()
    im = trim(im)
    s = min(w / im.width, h / im.height)
    tw, th = max(1, round(im.width * s)), max(1, round(im.height * s))
    # premultiply so transparent pixels don't bleed their colour into edges
    np = need("numpy")
    a = np.asarray(im).astype(np.float32)
    a[..., :3] *= a[..., 3:4] / 255.0
    pm = Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA").resize((tw, th), Image.BOX)
    b = np.asarray(pm).astype(np.float32)
    alpha = b[..., 3:4]
    b[..., :3] = np.where(alpha > 0, b[..., :3] * 255.0 / np.maximum(alpha, 1), 0)
    small = Image.fromarray(b.clip(0, 255).astype(np.uint8), "RGBA")
    small = hard_alpha(small, alpha_thresh)
    if colors:
        rgb = small.convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
        small = Image.merge("RGBA", (*rgb.split(), small.getchannel("A")))
    if outline:
        small = add_outline(small, outline)
    frame = Image.new("RGBA", (w, h))
    frame.paste(small, ((w - small.width) // 2, (h - small.height) // 2), small)
    return frame


def add_outline(im, color=(20, 16, 24, 255)):
    """1px outline around opaque pixels (inside the canvas; crops if the sprite touches the edge)."""
    Image = _pil()
    w, h = im.size
    src = im.load()
    out = im.copy()
    dst = out.load()
    for y in range(h):
        for x in range(w):
            if src[x, y][3]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and src[nx, ny][3]:
                    dst[x, y] = tuple(color)
                    break
    return out


def palette_from(ref, max_colors: int = 64):
    """Distinct opaque colours of a reference sprite/sheet (most frequent first)."""
    cols = [c for n, c in sorted(ref.getcolors(1 << 20) or [], reverse=True) if c[3] > 0]
    return [c[:3] for c in cols[:max_colors]]


def snap_palette(im, pal):
    np = need("numpy")
    a = np.asarray(im).copy()
    P = np.array(pal, np.int32)
    rgb = a[..., :3].reshape(-1, 1, 3).astype(np.int32)
    idx = ((rgb - P[None]) ** 2).sum(-1).argmin(-1)
    a[..., :3] = P[idx].reshape(a.shape[:2] + (3,)).astype(np.uint8)
    return _pil().fromarray(a, "RGBA")


def sheet(frames, cols: int | None = None, pad: int = 0, vertical: bool = False):
    Image = _pil()
    fw, fh = max(f.width for f in frames), max(f.height for f in frames)
    if vertical:
        cols = 1
    cols = cols or len(frames)
    rows = -(-len(frames) // cols)
    out = Image.new("RGBA", (cols * (fw + pad) - pad, rows * (fh + pad) - pad))
    for i, f in enumerate(frames):
        out.paste(f, ((i % cols) * (fw + pad), (i // cols) * (fh + pad)))
    return out


def slice_sheet(im, fw: int, fh: int, pad: int = 0):
    frames = []
    for y in range(0, im.height - fh + 1, fh + pad):
        for x in range(0, im.width - fw + 1, fw + pad):
            f = im.crop((x, y, x + fw, y + fh))
            if f.getbbox():
                frames.append(f)
    return frames


def simple_frames(im, n: int = 3, kind: str = "bob"):
    """Cheap idle animation from one frame: bob (1px up/down), squash (slime), wobble (rotate), flash (brighten)."""
    Image = _pil()
    from PIL import ImageChops, ImageEnhance
    out = []
    for k in range(n):
        if kind == "bob":
            out.append(ImageChops.offset(im, 0, (0, -1, 0, 1)[k % 4]))
        elif kind == "squash":
            s = 1 + 0.08 * ((-1) ** k) * (k > 0)
            w, h = round(im.width * s), round(im.height / s)
            sq = im.resize((w, h), Image.NEAREST)
            f = Image.new("RGBA", im.size)
            f.paste(sq, ((im.width - w) // 2, im.height - h))
            out.append(f)
        elif kind == "wobble":
            out.append(im.rotate((0, -5, 0, 5)[k % 4], resample=Image.NEAREST))
        elif kind == "flash":
            out.append(ImageEnhance.Brightness(im).enhance(1 + 0.35 * (k % 2)))
    return out


def team_mask(im, hue: str = "blue", sat_lo: float = 0.25, val_lo: float = 0.15):
    """Saturated accent pixels (blue/red/green/magenta) -> 0-255 mask; the sprite with those areas turned into
    grey shading - how RTS engines (AoE2's SLD player layer, many others) store player colour."""
    np = need("numpy")
    a = np.asarray(im).astype(np.float32)
    r, g, b = a[..., 0] / 255, a[..., 1] / 255, a[..., 2] / 255
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    sat = (mx - mn) / (mx + 1e-6)
    sel = {"blue": (b >= r * 1.25) & (b >= g * 0.9), "red": (r >= g * 1.4) & (r >= b * 1.4),
           "green": (g >= r * 1.25) & (g >= b * 1.1), "magenta": (r >= g * 1.4) & (b >= g * 1.4)}[hue]
    m = np.clip((sat - sat_lo) / 0.35, 0, 1) * sel * (a[..., 3] > 0) * (mx > val_lo)
    lum = (0.3 * a[..., 0] + 0.59 * a[..., 1] + 0.11 * a[..., 2])[..., None]
    k = m[..., None]
    out = a.copy()
    out[..., :3] = a[..., :3] * (1 - k) + np.clip(lum * 1.15, 0, 255) * k
    Image = _pil()
    return Image.fromarray(out.clip(0, 255).astype(np.uint8), "RGBA"), Image.fromarray((m * 255).astype(np.uint8), "L")


def seamless(im, blend: float = 0.25):
    """Tileable texture: offset by half and cross-fade the seams with the original (works well on noisy
    textures; for hero textures prefer `um fal texture`, which generates tiling directly)."""
    np = need("numpy")
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    h, w = a.shape[:2]
    shifted = np.roll(np.roll(a, h // 2, 0), w // 2, 1)
    yy, xx = np.mgrid[0:h, 0:w]
    dx = np.minimum(xx, w - 1 - xx) / (w * blend)
    dy = np.minimum(yy, h - 1 - yy) / (h * blend)
    wgt = np.clip(np.minimum(dx, dy), 0, 1)[..., None]   # 0 at the original's edges -> use the shifted copy there
    out = a * wgt + shifted * (1 - wgt)
    return _pil().fromarray(out.clip(0, 255).astype(np.uint8), "RGBA")


def tile_preview(im, n: int = 3):
    Image = _pil()
    out = Image.new("RGBA", (im.width * n, im.height * n))
    for y in range(n):
        for x in range(n):
            out.paste(im, (x * im.width, y * im.height))
    return out


def preview(im, scale: int = 4, checker: int = 8):
    """Scaled-up view on a checkerboard so transparency and pixel edges are visible."""
    Image = _pil()
    big = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    bg = Image.new("RGBA", big.size, (200, 200, 200, 255))
    px = bg.load()
    c = checker * max(1, scale // 2)
    for y in range(big.height):
        for x in range(big.width):
            if ((x // c) + (y // c)) % 2:
                px[x, y] = (150, 150, 150, 255)
    bg.alpha_composite(big)
    return bg


def info(im) -> dict:
    a = im.getchannel("A")
    hist = a.histogram()
    total = im.width * im.height
    colors = im.getcolors(1 << 20)
    return dict(size=im.size, bbox=im.getbbox(), opaque=round(sum(hist[250:]) / total, 3), clear=round(hist[0] / total, 3),
                partial=round(1 - sum(hist[250:]) / total - hist[0] / total, 3), colors=len(colors) if colors else ">1M",
                corner_color=border_color(im))


# --------------------------------------------------------------------------- CLI


def _color(s: str | None):
    if not s:
        return None
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + ((int(s[6:8], 16),) if len(s) == 8 else (255,))


def main(a):
    c = a.cmd
    if c == "info":
        for p in a.inputs:
            print(p, info(load(p)))
        return
    if c == "sheet":
        frames = [load(p) for p in a.frames]
        sheet(frames, a.cols, a.pad, a.vertical).save(a.output)
        print(a.output)
        return
    if c == "slice":
        fw, fh = parse_size(a.frame)
        out = Path(a.outdir)
        out.mkdir(parents=True, exist_ok=True)
        for i, f in enumerate(slice_sheet(load(a.input), fw, fh, a.pad)):
            f.save(out / f"frame_{i:03d}.png")
        print(out)
        return
    if c == "frames":
        out = Path(a.outdir)
        out.mkdir(parents=True, exist_ok=True)
        for i, f in enumerate(simple_frames(load(a.input), a.n, a.kind)):
            f.save(out / f"{Path(a.input).stem}_{i}.png")
        print(out)
        return
    im = load(a.input)
    if c == "cutout":
        im = cutout(im, a.tol, _color(a.bg), a.grey, a.spread, a.holes, a.keep_top)
    elif c == "fit":
        w, h = parse_size(a.size)
        im = fit(im, w, h, a.anchor, a.smooth, not a.no_upscale)
        if a.hard_alpha:
            im = hard_alpha(im)
    elif c == "pixelate":
        w, h = parse_size(a.size)
        im = pixelate(im, w, h, a.colors or None, _color(a.outline_color) if a.outline else None)
    elif c == "palette":
        im = snap_palette(im, palette_from(load(getattr(a, "from")), a.max_colors))
    elif c == "team-mask":
        im, mask = team_mask(im, a.hue)
        mask.save(Path(a.output).with_name(Path(a.output).stem + "_mask.png"))
    elif c == "seamless":
        im = seamless(im, a.blend)
    elif c == "tile-preview":
        im = tile_preview(im, a.n)
    elif c == "preview":
        im = preview(im, a.scale)
    elif c == "outline":
        im = add_outline(im, _color(a.color))
    elif c == "hard-alpha":
        im = hard_alpha(im, a.thresh)
    elif c == "flip":
        from PIL import ImageOps
        im = ImageOps.mirror(im) if not a.vertical else ImageOps.flip(im)
    elif c == "rotate":
        im = im.rotate(a.degrees, expand=True, resample=_pil().NEAREST)
    im.save(a.output)
    print(a.output, im.size)


def register(sub):
    import argparse
    p = sub.add_parser("sprite", help="cut out, fit, pixelate, recolor and pack 2D sprites",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cs = p.add_subparsers(dest="cmd", metavar="<cmd>")

    def cmd(name, help_, io=True):
        q = cs.add_parser(name, help=help_)
        if io:
            q.add_argument("input")
            q.add_argument("output")
        q.set_defaults(func=main)
        return q

    q = cs.add_parser("info", help="size, alpha coverage, bbox, colour count")
    q.add_argument("inputs", nargs="+")
    q.set_defaults(func=main)
    q = cmd("cutout", "flat background -> transparent (border flood fill)")
    q.add_argument("--tol", type=int, default=28, help="colour distance to the background (0-255 per channel)")
    q.add_argument("--bg", help="background colour hex (default: corners)")
    q.add_argument("--grey", type=int, help="also clear light greys (soft shadows) with min channel >= this")
    q.add_argument("--spread", type=int, default=24)
    q.add_argument("--holes", action="store_true", help="also clear enclosed background-coloured areas")
    q.add_argument("--keep-top", type=float, default=1.0, help="keep this fraction from the top (drop a floor shadow)")
    q = cmd("fit", "trim + scale into a WxH frame (nearest neighbour)")
    q.add_argument("--size", required=True)
    q.add_argument("--anchor", default="center", choices=["center", "bottom", "top"])
    q.add_argument("--smooth", action="store_true", help="Lanczos instead of nearest (painted/HD art)")
    q.add_argument("--no-upscale", action="store_true")
    q.add_argument("--hard-alpha", action="store_true")
    q = cmd("pixelate", "downscale to true pixel art with a limited palette")
    q.add_argument("--size", required=True)
    q.add_argument("--colors", type=int, default=16, help="0 = keep all colours")
    q.add_argument("--outline", action="store_true")
    q.add_argument("--outline-color", default="#141018")
    q = cmd("palette", "snap colours to a reference sprite's palette")
    q.add_argument("--from", required=True)
    q.add_argument("--max-colors", type=int, default=64)
    q = cs.add_parser("sheet", help="pack frames into a sheet")
    q.add_argument("output")
    q.add_argument("frames", nargs="+")
    q.add_argument("--cols", type=int)
    q.add_argument("--pad", type=int, default=0)
    q.add_argument("--vertical", action="store_true", help="one column (Terraria NPC/projectile strips)")
    q.set_defaults(func=main)
    q = cs.add_parser("slice", help="split a sheet into frames")
    q.add_argument("input")
    q.add_argument("outdir")
    q.add_argument("--frame", required=True, help="WxH")
    q.add_argument("--pad", type=int, default=0)
    q.set_defaults(func=main)
    q = cs.add_parser("frames", help="make a small idle animation from one frame")
    q.add_argument("input")
    q.add_argument("outdir")
    q.add_argument("--n", type=int, default=3)
    q.add_argument("--kind", default="bob", choices=["bob", "squash", "wobble", "flash"])
    q.set_defaults(func=main)
    q = cmd("team-mask", "player-colour mask from a saturated accent colour")
    q.add_argument("--hue", default="blue", choices=["blue", "red", "green", "magenta"])
    q = cmd("seamless", "make a texture tile")
    q.add_argument("--blend", type=float, default=0.25)
    q = cmd("tile-preview", "NxN tiled preview")
    q.add_argument("--n", type=int, default=3)
    q = cmd("preview", "checkerboard + nearest scale-up for viewing")
    q.add_argument("--scale", type=int, default=4)
    q = cmd("outline", "1px outline")
    q.add_argument("--color", default="#141018")
    q = cmd("hard-alpha", "binary alpha")
    q.add_argument("--thresh", type=int, default=128)
    q = cmd("flip", "mirror horizontally (or --vertical)")
    q.add_argument("--vertical", action="store_true")
    q = cmd("rotate", "rotate by degrees (counter-clockwise), nearest")
    q.add_argument("degrees", type=float)
