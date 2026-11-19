"""Static tests ST1-ST6 for collapse.exe: the RE facts behind the fix, as checks.

Read-only. Never touches the game folder unless you point it there.
    uv run --with pefile python st_a.py [path\\to\\collapse.exe]
Default exe: D:\\collapse-re\\collapse.exe (a copy, outside the repo).
"""
import hashlib, json, os, re, struct, sys
import pefile

HERE = os.path.dirname(os.path.abspath(__file__))
SIG = json.load(open(os.path.join(HERE, 'signatures.json'), encoding='utf-8'))
EXE = sys.argv[1] if len(sys.argv) > 1 else r'D:\collapse-re\collapse.exe'
H = lambda s: int(s, 16)

results = []
def check(tid, name, ok, detail=''):
    results.append(ok)
    print('%-4s %-5s %s%s' % (tid, 'PASS' if ok else 'FAIL', name, ('  -- ' + detail) if detail else ''))

raw = open(EXE, 'rb').read()
pe = pefile.PE(data=raw)
base = pe.OPTIONAL_HEADER.ImageBase
text = next(s for s in pe.sections if s.Name.startswith(b'.text'))
tdata, tva = text.get_data(), base + text.VirtualAddress

def read(va, n):
    return pe.get_data(va - base, n)

def calls_to(target):
    out = []
    for i in range(len(tdata) - 5):
        if tdata[i] == 0xE8 and (tva + i + 5 + struct.unpack_from('<i', tdata, i + 1)[0]) & 0xffffffff == target:
            out.append(tva + i)
    return out

# ST1 identity
e = SIG['exe']
digest = hashlib.sha256(raw).hexdigest()
laa = digest == e['sha256_laa']  # same exe after laa_patch.py (one bit, see ST16)
check('ST1', 'sha256 (original or LAA-patched)', digest in (e['sha256'], e['sha256_laa']),
      'LAA-patched' if laa else ('original' if digest == e['sha256'] else digest))
check('ST1', 'size', len(raw) == e['size'], str(len(raw)))
check('ST1', 'PE timestamp', pe.FILE_HEADER.TimeDateStamp == e['timestamp'], str(pe.FILE_HEADER.TimeDateStamp))
check('ST1', 'Characteristics 0x10E (+0x20 if LAA)',
      pe.FILE_HEADER.Characteristics == e['characteristics'] | (0x20 if laa else 0),
      hex(pe.FILE_HEADER.Characteristics))
check('ST1', 'DllCharacteristics 0 (no NX/ASLR)', pe.OPTIONAL_HEADER.DllCharacteristics == e['dll_characteristics'])
check('ST1', 'entry point', base + pe.OPTIONAL_HEADER.AddressOfEntryPoint == H(e['entry']))

# ST2 imports
normal = {d.dll.decode().upper(): d for d in pe.DIRECTORY_ENTRY_IMPORT}
check('ST2', 'only KERNEL32 is a normal import', list(normal) == ['KERNEL32.DLL'], ','.join(normal))
gtc = [i for i in normal['KERNEL32.DLL'].imports if i.name == b'GetTickCount']
check('ST2', 'GetTickCount IAT slot', bool(gtc) and gtc[0].address == H(SIG['iat']['KERNEL32.dll!GetTickCount']),
      hex(gtc[0].address) if gtc else 'missing')
delay = {d.dll.decode().upper() for d in getattr(pe, 'DIRECTORY_ENTRY_DELAY_IMPORT', [])}
need = {'DINPUT8.DLL', 'XINPUT1_3.DLL', 'DSOUND.DLL', 'VERSION.DLL', 'D3DX9_31.DLL'}
check('ST2', 'proxy candidates are delay-loaded', need <= delay, ','.join(sorted(need - delay)))
check('ST2', 'no winmm / timeBeginPeriod anywhere',
      'WINMM.DLL' not in delay | set(normal) and b'timeBeginPeriod' not in raw)

# ST3 every GetTickCount slot reference
slot = struct.pack('<I', H(SIG['iat']['KERNEL32.dll!GetTickCount']))
found = sorted(tva + m.start() - 2 for m in re.finditer(re.escape(slot), tdata))
expect = sorted(H(r['va']) for r in SIG['gettickcount_refs'])
check('ST3', 'GetTickCount slot refs == %d known sites' % len(expect), found == expect,
      ','.join(hex(x) for x in sorted(set(found) ^ set(expect))))
bad = [r['va'] for r in SIG['gettickcount_refs'] if read(H(r['va']), 6).hex() != r['hex']]
check('ST3', 'each ref is call/mov/jmp through the slot', not bad, ','.join(bad))
check('ST3', 'no direct calls to the import thunk', calls_to(0x600d1a) == [])

# ST4 patch-site signatures
for s in SIG['sites']:
    got = read(H(s['va']), len(s['hex']) // 2).hex()
    check('ST4', '%s @%s' % (s['id'], s['va']), got == s['hex'], got if got != s['hex'] else '')

for s in SIG['patterns']:
    # hex string: a match may start only on a byte boundary
    n = sum(1 for m in re.finditer('(?=%s)' % s['regex'], tdata.hex()) if m.start() % 2 == 0)
    check('ST4', 'pattern %s matches once in .text' % s['id'], n == 1, str(n))

# ST5 constants
for c in SIG['constants']:
    v = struct.unpack('<d', read(H(c['va']), 8))[0]
    check('ST5', '%s @%s = %r' % (c['what'], c['va'], c['value']), abs(v - c['value']) < 1e-12, repr(v))

# ST6 load order: init_heap runs from a CRT initializer, before any proxy DLL can load
ci = SIG['crt_init']
check('ST6', 'CRT init table slot -> init_heap stub',
      struct.unpack('<I', read(H(ci['table_slot']), 4))[0] == H(ci['points_to']))
check('ST6', 'TLS callback list is empty', struct.unpack('<I', read(H(ci['tls_callbacks']), 4))[0] == 0)
callers = calls_to(0x5e5840)
check('ST6', 'init_heap called only from the two CRT stubs', callers == [0x5e5c40, 0x5e5c70],
      ','.join(map(hex, callers)))
st = SIG['startup']
f0 = H(st['function'])
pos = []
for o in st['order']:
    c = [a for a in calls_to(H(o['call'])) if f0 <= a < f0 + 0x1000]
    pos.append(c[0] if c else None)
check('ST6', 'startup order: database_init < VERSION < d3d9 < DINPUT8',
      None not in pos and pos == sorted(pos), ','.join(map(lambda p: hex(p) if p else 'none', pos)))

print('\n%d/%d passed' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
