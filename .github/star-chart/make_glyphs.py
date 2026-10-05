"""Write glyphs.json, the type star_chart.py draws with, so the chart SVG needs no fonts.

Geist Pixel sits on a grid of 38 units per em, so its digits are stored as bitmaps, one cell per grid
unit. Sometype Mono is stored as outlines. Run it once when the brand type changes; it needs Pillow,
fontTools and the two font files from the brand kit:

    python3 make_glyphs.py "GeistPixel[ELSH].ttf" "SometypeMono[wght].ttf"

Both fonts are under the SIL Open Font License 1.1.
"""
import json
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image, ImageDraw, ImageFont

GEIST = '0123456789,.k'
MONO = 'abcdefghijklmnopqrstuvwxyz0123456789 ,.-:/+·×()'
NO_LIG = ['-liga', '-clig', '-dlig', '-calt']


def pixel_table(path, chars):
    """Bitmaps at one pixel per grid unit (1000/38 px), solid shape (ELSH 0, the default)."""
    font = ImageFont.truetype(path, 1000 / 38)
    asc, desc = font.getmetrics()
    out, top, bottom = {}, asc, 0
    for ch in chars:
        m = Image.new('L', (40, asc + desc), 0)
        d = ImageDraw.Draw(m)
        d.fontmode = '1'
        d.text((0, 0), ch, font=font, fill=255, features=NO_LIG)
        rows = [''.join('#' if m.getpixel((x, y)) else '.' for x in range(40)) for y in range(asc + desc)]
        ink = [y for y, r in enumerate(rows) if '#' in r]
        top, bottom = min(top, ink[0]), max(bottom, ink[-1])
        out[ch] = [round(font.getlength(ch, features=NO_LIG)), rows]
    for ch, (adv, rows) in out.items():  # keep only the rows any glyph inks, trim each row's right side
        out[ch] = [adv, [r[:adv + 2].rstrip('.') for r in rows[top:bottom + 1]]]
    return {'grid': 38, 'baseline': asc - top, 'glyphs': out}


def outline_table(path, axes, chars):
    font = instancer.instantiateVariableFont(TTFont(path), axes)
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    out = {}
    for ch in chars:
        pen = SVGPathPen(glyphs, ntos=lambda v: str(round(v)))
        glyphs[cmap[ord(ch)]].draw(pen)
        out[ch] = [glyphs[cmap[ord(ch)]].width, pen.getCommands()]
    return {'upm': font['head'].unitsPerEm, 'cap': font['OS/2'].sCapHeight, 'glyphs': out}


if __name__ == '__main__':
    geist, mono = sys.argv[1:3]
    data = {
        'about': 'Geist Pixel digits as grid bitmaps (solid shape) and Sometype Mono outlines (weight 500, font '
                 'units, y up), both under the SIL Open Font License 1.1. Written by make_glyphs.py.',
        'geist': pixel_table(geist, GEIST),
        'mono': outline_table(mono, {'wght': 500}, MONO),
    }
    out = Path(__file__).with_name('glyphs.json')
    out.write_text(json.dumps(data, separators=(',', ':'), ensure_ascii=False))
    print(out, out.stat().st_size, 'bytes')
