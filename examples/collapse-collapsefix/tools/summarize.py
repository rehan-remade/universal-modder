"""Summarize runs/<prefix>* into a markdown table (one row per run) plus totals.

    python summarize.py D1_
"""
import glob, json, os, sys
from collections import Counter

RUNS = r'D:\collapse-re\runs'
prefix = sys.argv[1] if len(sys.argv) > 1 else 'D1_'
LAA = '767cb5ec39b1a9fafed38ffad08c4f84ea23b7a53721455d26cc4fa65e6829cc'

rows, agg = [], Counter()
for d in sorted(glob.glob(os.path.join(RUNS, prefix + '*'))):
    p = os.path.join(d, 'result.json')
    if not os.path.exists(p): continue
    r = json.load(open(p, encoding='utf-8'))
    ev = [json.loads(l) for l in open(os.path.join(d, 'events.jsonl'), encoding='utf-8')]
    ticks = [e for e in ev if e.get('tag') == 'tick']
    tail = ticks[-5:]
    fps = round(sum(e.get('presents', 0) for e in tail) / (2 * len(tail)), 1) if tail else 0
    cmd2 = next((e for e in r.get('va_cmdline') or [] if e['tag'] == 'GetCommandLineA#2'), {}) or {}
    cd = r.get('va_at_create_device') or {}
    fen = r.get('va_after_fence_release') or {}
    crashed = bool(r.get('detached')) and r['detached'].get('t', 99) < r['secs'] - 1
    ok = r.get('create_device_hr') == '0x0' and not crashed and fps > 0
    variant = 'V1' if r['exe_sha256'] == LAA else 'V0'
    agg[(variant, ok)] += 1
    rows.append('| %s | %s | %s | %s | %s/%s | %s | %s/%s/%s | %s | %s |' % (
        os.path.basename(d), variant, r.get('create_device_hr'), 'crash' if crashed else 'ok',
        cmd2.get('free_loMB'), cmd2.get('largestBelow2GMB'), fen.get('free_loMB'),
        cd.get('free_loMB'), cd.get('free_midMB'), cd.get('free_hiMB'), fps, len(r.get('raises') or [])))
print('| run | exe | CreateDevice | process | after CRT: free<0x70000000 / largest<2G (MB) | after fence release: free<0x70000000 | at CreateDevice: free lo/mid/hi (MB) | menu FPS (last 10 s) | engine raises |')
print('|---|---|---|---|---|---|---|---|---|')
print('\n'.join(rows))
print('\nOK runs: ' + ', '.join('%s %d/%d' % (v, agg[(v, True)], agg[(v, True)] + agg[(v, False)]) for v in ('V0', 'V1')))
