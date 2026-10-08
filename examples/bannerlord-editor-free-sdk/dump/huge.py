import sys, numpy as np
from minidump.minidumpfile import MinidumpFile
m = MinidumpFile.parse(sys.argv[1]); r = m.get_reader()
segs = m.memory_segments.memory_segments if m.memory_segments else m.memory_segments_64.memory_segments
for s in segs:
    if s.size > 0x400000: continue
    try: d = r.read(s.start_virtual_address, s.size)
    except Exception: continue
    n = len(d)//4*4
    f = np.frombuffer(d[:n], dtype='<f4')
    a = np.abs(f)
    idx = np.where((a > 1e9) & (a < 1e15))[0]
    # need >=3 consecutive-ish (vec3)
    good = [i for i in idx if (i+1 in set(idx)) and (i+2 in set(idx))]
    if good:
        print(hex(s.start_virtual_address), hex(s.size), len(idx), [ (hex(s.start_virtual_address+4*i), float(f[i]), float(f[i+1]), float(f[i+2])) for i in good[:6]])
