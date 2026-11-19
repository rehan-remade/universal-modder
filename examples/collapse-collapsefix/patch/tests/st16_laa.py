"""ST16: the LAA-patched exe differs from the original by exactly one bit (IMAGE_FILE_LARGE_ADDRESS_AWARE).

    python st16_laa.py <original.exe> <patched.exe>
"""
import struct, sys
import pefile

orig, patched = (open(p, 'rb').read() for p in sys.argv[1:3])
ok = True
def check(name, cond, detail=''):
    global ok
    ok &= bool(cond)
    print('ST16 %-5s %s%s' % ('PASS' if cond else 'FAIL', name, ('  -- ' + detail) if detail else ''))

check('same size', len(orig) == len(patched))
diff = [i for i, (a, b) in enumerate(zip(orig, patched)) if a != b]
off = struct.unpack_from('<I', orig, 0x3C)[0] + 4 + 18
check('exactly one byte differs, at COFF Characteristics', diff == [off], ','.join(map(hex, diff)))
if diff == [off]:
    check('that byte differs only by bit 0x20', orig[off] ^ patched[off] == 0x20,
          '%#04x -> %#04x' % (orig[off], patched[off]))
p = pefile.PE(data=patched)
check('patched exe parses and is LAA', p.FILE_HEADER.Characteristics & 0x20,
      hex(p.FILE_HEADER.Characteristics))
check('PE checksum unchanged (0)', p.OPTIONAL_HEADER.CheckSum == pefile.PE(data=orig).OPTIONAL_HEADER.CheckSum)
print('ST16 %s' % ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)
