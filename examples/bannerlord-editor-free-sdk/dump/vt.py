import sys, struct
from minidump.minidumpfile import MinidumpFile
m = MinidumpFile.parse(sys.argv[1]); r = m.get_reader()
segs = m.memory_segments.memory_segments if m.memory_segments else m.memory_segments_64.memory_segments
pat = struct.pack('<Q', int(sys.argv[2],16))
for s in segs:
    if s.size > 0x1000000: continue
    try: d = r.read(s.start_virtual_address, s.size)
    except Exception: continue
    i = d.find(pat)
    while i >= 0:
        a = s.start_virtual_address + i
        tail = d[i:i+0x40]
        q = [struct.unpack_from('<Q', tail, j)[0] for j in range(0, len(tail)-7, 8)]
        print(hex(a), ' '.join(hex(x) for x in q))
        i = d.find(pat, i+8)
