# x64 unwinder over a minidump thread using the on-disk PE .pdata of loaded modules.
import sys, struct, os
from minidump.minidumpfile import MinidumpFile

DMP, TID = sys.argv[1], int(sys.argv[2], 16)
m = MinidumpFile.parse(DMP); r = m.get_reader()
mods = [(x.baseaddress, x.baseaddress + x.size, x.name) for x in m.modules.modules]
NB = [x for x in m.modules.modules if 'TaleWorlds.Native' in x.name][0].baseaddress

class PE:
    def __init__(s, path):
        raw = open(path, 'rb').read()
        pe = struct.unpack_from('<I', raw, 0x3c)[0]
        nsec = struct.unpack_from('<H', raw, pe + 6)[0]; osz = struct.unpack_from('<H', raw, pe + 20)[0]
        opt = pe + 24
        sizeimg = struct.unpack_from('<I', raw, opt + 56)[0]
        img = bytearray(sizeimg)
        so = opt + osz
        for k in range(nsec):
            vs, va, rs, rp = struct.unpack_from('<IIII', raw, so + 40 * k + 8)
            img[va:va + rs] = raw[rp:rp + rs]
        s.img = bytes(img)
        # data dir 3 = exception
        ea, es = struct.unpack_from('<II', raw, opt + 112 + 3 * 8)
        s.rf = [struct.unpack_from('<III', s.img, ea + 12 * i) for i in range(es // 12)]
        s.starts = [x[0] for x in s.rf]
    def find(s, rva):
        import bisect
        i = bisect.bisect_right(s.starts, rva) - 1
        if i >= 0 and s.rf[i][0] <= rva < s.rf[i][1]: return s.rf[i]
        return None

pes = {}
def pe_of(a):
    for b, e, n in mods:
        if b <= a < e:
            if n not in pes:
                try: pes[n] = PE(n)
                except Exception: pes[n] = None
            return b, n, pes[n]
    return None, None, None

def q(a): return struct.unpack('<Q', r.read(a, 8))[0]

REG = ['Rax', 'Rcx', 'Rdx', 'Rbx', 'Rsp', 'Rbp', 'Rsi', 'Rdi', 'R8', 'R9', 'R10', 'R11', 'R12', 'R13', 'R14', 'R15']

def unwind(pe, base, rip, regs):
    rva = rip - base
    f = pe.find(rva)
    if f is None:  # leaf
        regs['Rsp'] += 8; return q(regs['Rsp'] - 8)
    start, end, ui = f
    first = True
    while True:
        b = pe.img
        ver_flags, prolog, ncodes, fr = b[ui], b[ui + 1], b[ui + 2], b[ui + 3]
        flags = ver_flags >> 3
        freg, foff = fr & 15, fr >> 4
        codes = [struct.unpack_from('<H', b, ui + 4 + 2 * i)[0] for i in range(ncodes)]
        off_in = rva - start
        # frame register
        if freg and first:
            pass
        i = 0
        # if frame reg established, rsp = freg - foff*16
        fp_set = False
        while i < ncodes:
            c = codes[i]; co, op, info = c & 0xff, (c >> 8) & 15, c >> 12
            applies = (off_in >= co) or not first  # code applied only if prolog passed it
            if op == 0:  # PUSH_NONVOL
                if applies: regs[REG[info]] = q(regs['Rsp']); regs['Rsp'] += 8
                i += 1
            elif op == 1:
                if info == 0: sz = codes[i + 1] * 8; i += 2
                else: sz = codes[i + 1] | (codes[i + 2] << 16); i += 3
                if applies: regs['Rsp'] += sz
            elif op == 2:
                if applies: regs['Rsp'] += info * 8 + 8
                i += 1
            elif op == 3:
                if applies: regs['Rsp'] = regs[REG[freg]] - foff * 16
                i += 1
            elif op == 4:
                if applies: regs[REG[info]] = q(regs['Rsp'] + codes[i + 1] * 8)
                i += 2
            elif op == 5:
                if applies: regs[REG[info]] = q(regs['Rsp'] + (codes[i + 1] | (codes[i + 2] << 16)))
                i += 3
            elif op == 8: i += 2
            elif op == 9: i += 3
            elif op == 10:
                i += 1
            else: i += 1
        if flags & 4:  # chained
            n = ncodes + (ncodes & 1)
            start, end, ui = struct.unpack_from('<III', b, ui + 4 + 2 * n)
            first = False
            continue
        break
    ret = q(regs['Rsp']); regs['Rsp'] += 8
    return ret

t = [x for x in m.threads.threads if x.ThreadId == TID][0]
c = t.ContextObject
regs = {k: getattr(c, k) for k in REG}
rip = c.Rip
for depth in range(60):
    base, name, pe = pe_of(rip)
    tag = os.path.basename(name) if name else '?'
    gh = f" GH {rip - NB + 0x180000000:#x}" if name and 'TaleWorlds.Native' in name else ''
    print(f"#{depth:2} {rip:#x} {tag}+{(rip - base) if base else 0:#x}{gh}  rsp={regs['Rsp']:#x} rbx={regs['Rbx']:#x} rsi={regs['Rsi']:#x} rdi={regs['Rdi']:#x} r12={regs['R12']:#x} r13={regs['R13']:#x} r14={regs['R14']:#x} r15={regs['R15']:#x}")
    if pe is None: print('   no pdata (JIT/unknown), stop'); break
    try: rip = unwind(pe, base, rip, regs)
    except Exception as e: print('   unwind err', e); break
    if rip == 0: break
