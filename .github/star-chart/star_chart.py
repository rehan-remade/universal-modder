"""Draw the README's star chart in the universal-modder brand: an 800 x 300 SVG, nothing but paths.

A void panel holds the star count in Geist Pixel, the curve as 4 px cells over a dithered magenta glow,
the brand's magenta tile as the period at the latest point, and dates in Sometype Mono. The type
comes from glyphs.json, so the SVG needs no fonts and looks the same everywhere.

    python3 star_chart.py rehan-remade/universal-modder stars.svg

It reads every stargazer's starred_at with `gh api` (set GH_TOKEN in CI). The star-chart workflow
runs it every 6 hours and force-pushes the SVG to the star-chart branch. The stargazers API stops
paging at 40,000 stars; past that, sample the pages instead.
"""
import bisect
import calendar
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

VOID, BONE, ASH, ASH2, RULE, MISSING, GLOW = '#0E0C10', '#F2ECE2', '#8E8796', '#5D5765', '#2B2630', '#FF3CD2', '#4A1342'
W, H = 800, 300
CELL, X0, BOTTOM, COLS, ROWS = 4, 32, 252, 180, 36  # the curve: 180 x 36 cells of 4 px
BAYER = [[0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26], [12, 44, 4, 36, 14, 46, 6, 38],
         [60, 28, 52, 20, 62, 30, 54, 22], [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
         [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21]]
MONTHS = [m.lower() for m in calendar.month_abbr]
GLYPHS = json.loads(Path(__file__).with_name('glyphs.json').read_text())


def gh(*args):
    return subprocess.run(['gh', 'api', *args], capture_output=True, text=True, check=True).stdout


def stargazers(repo):
    out = gh('--paginate', '-H', 'Accept: application/vnd.github.star+json', f'repos/{repo}/stargazers?per_page=100',
             '--jq', '.[].starred_at')
    return sorted(datetime.fromisoformat(s.replace('Z', '+00:00')) for s in out.split())


class Cells:
    """Rects of one colour, merged into one path."""

    def __init__(self):
        self.d = []

    def rect(self, x, y, w, h):
        self.d.append(f'M{x} {y}h{w}v{h}h-{w}z')

    def path(self, fill):
        return f'<path fill="{fill}" d="{"".join(self.d)}"/>' if self.d else ''


def geist(cells, text, x, top, k):
    """Geist Pixel at k px per grid unit (52.632 px type at k = 2). Returns the right edge."""
    g = GLYPHS['geist']['glyphs']
    for ch in text:
        adv, rows = g[ch]
        for r, row in enumerate(rows):
            c = 0
            while c < len(row):  # one rect per run of inked cells
                if row[c] == '#':
                    e = c
                    while e < len(row) and row[e] == '#':
                        e += 1
                    cells.rect(x + c * k, top + r * k, (e - c) * k, k)
                    c = e
                else:
                    c += 1
        x += adv * k
    return x


def mono_width(text, size):
    t = GLYPHS['mono']
    return sum(t['glyphs'][ch][0] for ch in text) * size / t['upm']


def mono(text, x, baseline, size, fill, anchor='start'):
    """Sometype Mono from its outlines. anchor: start, middle or end."""
    t = GLYPHS['mono']
    if anchor != 'start':
        x -= mono_width(text, size) / (2 if anchor == 'middle' else 1)
    s, paths, pen = size / t['upm'], [], 0
    for ch in text:
        adv, d = t['glyphs'][ch]
        if d:
            paths.append(f'<path transform="translate({pen} 0)" d="{d}"/>')
        pen += adv
    return f'<g fill="{fill}" transform="translate({x:.1f} {baseline}) scale({s:.5f} -{s:.5f})">{"".join(paths)}</g>'


def nice_step(top):
    """The 1, 2, 2.5 or 5 x 10^n step whose gridlines (2 to 4 of them, or 1 for tiny counts) sit
    closest above the curve's top. Ties go to more gridlines."""
    options = []
    for e in range(10):
        for m in (1, 2, 2.5, 5):
            step = m * 10 ** e
            if step != int(step):  # no half stars
                continue
            lines = -(-top // step)
            if 1 <= lines <= 4:
                options.append((lines < 2, lines * step, -lines, step))
    return min(options)[3]


def count_label(v):
    if v >= 1_000_000:
        return f'{v / 1_000_000:g}m'
    return f'{v / 1000:g}k' if v >= 1000 else f'{v:g}'


def date_ticks(t0, t1):
    """Midnights (UTC) every 1, 2, 7 or 14 days, or month starts every 1, 2, 3, 6 or 12 months: at most 7."""
    span = (t1 - t0).total_seconds() / 86400
    for days in (1, 2, 7, 14):
        if span / days <= 7:
            t = datetime(t0.year, t0.month, t0.day, tzinfo=timezone.utc) + timedelta(days=1)
            out = []
            while t < t1:
                out.append((t, f'{MONTHS[t.month]} {t.day}'))
                t += timedelta(days=days)
            return out
    for months in (1, 2, 3, 6, 12):
        if span / (30.44 * months) <= 7:
            y, m, out, shown = t0.year, t0.month, [], None
            while True:
                m += months
                y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
                t = datetime(y, m, 1, tzinfo=timezone.utc)
                if t >= t1:
                    return out
                out.append((t, MONTHS[m] if y == shown else f'{MONTHS[m]} {y}'))  # the year once per year
                shown = y
    return []


def draw(times, now):
    total = len(times)
    t0 = times[0].replace(minute=0, second=0, microsecond=0) if times else now - timedelta(days=1)
    span = (now - t0).total_seconds() or 1
    step = nice_step(max(total, 1))
    ymax = -(-max(total, 1) // step) * step
    rule, glow, line, tile, big = Cells(), Cells(), Cells(), Cells(), Cells()
    labels = []

    # gridlines (dotted) with their values, and the axis
    v = step
    while v <= ymax:
        y = BOTTOM - round(v / ymax * ROWS) * CELL
        for x in range(X0, X0 + COLS * CELL, 8):
            rule.rect(x, y, 2, 2)
        labels.append(mono(count_label(v), X0, y - 6, 12, ASH2))
        v += step
    rule.rect(X0, BOTTOM, COLS * CELL + 4 * CELL, 2)

    # the curve: one top cell per column, joined vertically, with a dithered glow fading below it
    prev = None
    for c in range(COLS):
        t = t0 + timedelta(seconds=span * (c + 1) / COLS)
        n = bisect.bisect_right(times, t)
        r = round(n / ymax * ROWS)
        x = X0 + c * CELL
        lo = r if prev is None else min(prev + 1, r)
        for rr in range(lo, r + 1):
            line.rect(x, BOTTOM - (rr + 1) * CELL, CELL, CELL)
        for rr in range(0, r):
            d = r - 1 - rr
            if BAYER[rr % 8][c % 8] < 64 * 0.55 * max(0.0, 1 - d / 9):
                glow.rect(x, BOTTOM - (rr + 1) * CELL, CELL, CELL)
        prev = r
    # the period: the brand's magenta tile, 3 cells, one cell after the curve, sitting on its last cell
    tile.rect(X0 + COLS * CELL + CELL, BOTTOM - prev * CELL - 3 * CELL, 3 * CELL, 3 * CELL)

    # dates under the axis, kept inside the panel
    for t, text in date_ticks(t0, now):
        x = X0 + (t - t0).total_seconds() / span * COLS * CELL
        half = mono_width(text, 12) / 2
        x = min(max(x, X0 + half), W - X0 - half)
        labels.append(mono(text, x, 276, 12, ASH, 'middle'))

    # the header: the count in Geist Pixel, then 'stars' and when it was drawn
    right = geist(big, f'{total:,}', X0, 32, 2)
    base = 32 + GLYPHS['geist']['baseline'] * 2
    labels.append(mono('stars', right + 12, base, 16, ASH))
    labels.append(mono(f'updated {MONTHS[now.month]} {now.day} · {now:%H:%M} utc', W - X0, base, 12, ASH2, 'end'))

    when = f'{MONTHS[t0.month]} {t0.day} to {MONTHS[now.month]} {now.day}, {now.year}'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="universal-modder has {total:,} GitHub stars, {when}">'
            f'<path fill="{VOID}" d="M4 0h{W - 8}v4h4v{H - 8}h-4v4h-{W - 8}v-4h-4v-{H - 8}h4z"/>'
            f'<g shape-rendering="crispEdges">{rule.path(RULE)}{glow.path(GLOW)}{line.path(BONE)}{tile.path(MISSING)}'
            f'{big.path(BONE)}</g>{"".join(labels)}</svg>')


if __name__ == '__main__':
    repo, out = sys.argv[1], Path(sys.argv[2])
    times = stargazers(repo)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(draw(times, datetime.now(timezone.utc)))
    print(f'{out}: {len(times):,} stars, {out.stat().st_size:,} bytes')
