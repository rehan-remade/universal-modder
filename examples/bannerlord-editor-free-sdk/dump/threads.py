import sys, struct
from minidump.minidumpfile import MinidumpFile

DMP = sys.argv[1]
m = MinidumpFile.parse(DMP)
r = m.get_reader()
mods = [(x.baseaddress, x.baseaddress + x.size, x.name.split('\\')[-1]) for x in m.modules.modules]
nat = [x for x in m.modules.modules if 'TaleWorlds.Native' in x.name][0]
NB = nat.baseaddress
def mapimg(path):
    raw = open(path,'rb').read()
    pe = struct.unpack_from('<I', raw, 0x3c)[0]
    nsec = struct.unpack_from('<H', raw, pe+6)[0]; osz = struct.unpack_from('<H', raw, pe+20)[0]
    sizeimg = struct.unpack_from('<I', raw, pe+24+56)[0]
    img = bytearray(sizeimg)
    so = pe+24+osz
    for k in range(nsec):
        vs, va, rs, rp = struct.unpack_from('<IIII', raw, so+40*k+8)
        img[va:va+rs] = raw[rp:rp+rs]
    return bytes(img)
img = mapimg(nat.name)

def modof(a):
    for b, e, n in mods:
        if b <= a < e: return n, a - b
    return None, 0

def gh(a): return a - NB + 0x180000000

def call_before(off):
    # E8 rel32 (5), FF 15 (6), FF /2 reg (2..7)
    if off < 7 or off > len(img): return False
    b = img[off-7:off]
    if b[2] == 0xE8: return True
    if b[1] == 0xFF and (b[2] & 0x38) == 0x10: return True  # ff modrm(6 bytes incl disp32)
    for L in (2, 3, 4, 7):
        x = img[off-L:off]
        if x[0] == 0xFF and (x[1] & 0x38) == 0x10: return True
    return False

infos = {i.ThreadId: i for i in m.thread_info.infos}
rows = []
for t in m.threads.threads:
    ctx = t.ContextObject
    i = infos.get(t.ThreadId)
    rows.append((i.UserTime if i else 0, t, ctx, i))
rows.sort(key=lambda x: -x[0])
want = set(int(x, 16) for x in sys.argv[2:]) if len(sys.argv) > 2 else None
for ut, t, ctx, i in rows:
    rip = ctx.Rip
    n, o = modof(rip)
    sn, so = modof(i.StartAddress) if i else (None, 0)
    line = f"tid {t.ThreadId:#x} user {ut/1e7:8.1f}s kern {i.KernelTime/1e7:7.1f}s rip {rip:#x} {n}+{o:#x} start {sn}+{so:#x}"
    if n and 'Native' in n: line += f" GH {gh(rip):#x}"
    print(line)
    if want is not None and t.ThreadId not in want: continue
    if want is None and not (n and 'Native' in n): continue
    print("   regs: " + " ".join(f"{k}={getattr(ctx,k):#x}" for k in ['Rax','Rbx','Rcx','Rdx','Rsi','Rdi','Rbp','Rsp','R8','R9','R10','R11','R12','R13','R14','R15']))
    rsp = ctx.Rsp
    try:
        data = r.read(rsp, 0x6000)
    except Exception as e:
        try: data = r.read(rsp, 0x2000)
        except Exception as e2: print("   no stack", e2); continue
    cnt = 0
    for k in range(0, len(data) - 8, 8):
        v = struct.unpack_from('<Q', data, k)[0]
        mn, mo = modof(v)
        if mn and 'Native' in mn and call_before(mo):
            print(f"     [rsp+{k:#x}] {gh(v):#x}")
            cnt += 1
        elif mn and mn.lower() in ('clr.dll',) and cnt < 60:
            pass
        if cnt > 40: break
