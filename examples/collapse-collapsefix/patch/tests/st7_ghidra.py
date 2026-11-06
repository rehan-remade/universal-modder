"""ST7: an independent Ghidra re-analysis finds the same functions the RE notes rely on.

    python st7_ghidra.py <st7_funcs.txt> [first_run_decomp.c]
st7_funcs.txt comes from a small Ghidra script, not included (one "addr name size" per line), on a fresh headless
import. first_run_decomp.c is the first run's private decompile, kept outside any repo.
"""
import re, sys

KEY = {  # entry -> role
    0x5e5840: 'init_heap', 0x5e5780: 'free-region finder', 0x5e5ab0: 'engine allocator',
    0x414150: 'package map', 0x4db940: 'Direct3DCreate9 loader', 0x4dc460: 'device setup/reset',
    0x5e6b90: 'database_init', 0x462aa0: 'save enumeration', 0x57d400: 'setup.ini reader',
    0x57e210: 'setup.ini writer', 0x5e12d0: 'projection', 0x425940: 'cutscene FOV blend',
    0x5e2b30: 'main loop (dt)', 0x5e2880: 'frame limiter', 0x5e7dd0: 'startup', 0x426080: 'input init',
}

funcs = {}
for line in open(sys.argv[1], encoding='utf-8'):
    a, name, size = line.split()
    funcs[int(a, 16)] = (name, int(size))

ok = True
for a, role in KEY.items():
    hit = a in funcs
    ok &= hit
    print('ST7  %-5s %-24s @%#x %s' % ('PASS' if hit else 'FAIL', role, a, funcs.get(a, ('missing',))[0]))

if len(sys.argv) > 2:
    first = {int(m, 16) for m in re.findall(r'(?m)^// ==== \S+ @ ([0-9a-f]+)', open(sys.argv[2], encoding='utf-8').read())}
    second = set(funcs)
    only1, only2 = first - second, second - first
    print('ST7  info  first run %d functions, re-run %d, only-first %d, only-second %d'
          % (len(first), len(second), len(only1), len(only2)))
print('ST7 %s' % ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)
