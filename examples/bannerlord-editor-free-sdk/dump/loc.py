import sys, struct
from minidump.minidumpfile import MinidumpFile
m = MinidumpFile.parse(sys.argv[1]); r = m.get_reader()
E = int(sys.argv[2], 16)
for name in sys.argv[3:]:
    off = int(name.split('_')[1], 16); n = 16 if len(name.split('_'))<3 else int(name.split('_')[2],16)
    a = E - off
    d = r.read(a, n)
    f = [struct.unpack_from('<f', d, j)[0] for j in range(0, n, 4)]
    i = [struct.unpack_from('<I', d, j)[0] for j in range(0, n, 4)]
    print(f"{name:14} {a:#x} f " + " ".join(f"{x:.6g}" for x in f) + "  x " + " ".join(f"{x:08x}" for x in i))
