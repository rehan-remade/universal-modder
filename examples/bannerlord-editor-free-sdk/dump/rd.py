import sys, struct
from minidump.minidumpfile import MinidumpFile
m = MinidumpFile.parse(sys.argv[1]); r = m.get_reader()
for spec in sys.argv[2:]:
    a, n = spec.split(':'); a = int(a, 16); n = int(n, 16)
    try: d = r.read(a, n)
    except Exception as e: print(hex(a), 'ERR', e); continue
    print(f"== {a:#x}")
    for k in range(0, n, 16):
        ch = d[k:k+16]
        q = [struct.unpack_from('<Q', ch, j)[0] for j in range(0, len(ch) - 7, 8)]
        i = [struct.unpack_from('<i', ch, j)[0] for j in range(0, len(ch) - 3, 4)]
        f = [struct.unpack_from('<f', ch, j)[0] for j in range(0, len(ch) - 3, 4)]
        print(f"  +{k:#05x} " + " ".join(f"{x:016x}" for x in q) + "  i " + " ".join(str(x) for x in i) + "  f " + " ".join(f"{x:.4g}" for x in f))
