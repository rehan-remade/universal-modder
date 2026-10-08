# Minimal binary FBX reader: print each bone Model's local transform (Lcl Translation / Rotation,
# PreRotation) and each skin Cluster's TransformLink, so two FBX files can be compared bone by bone.
#   python fbx_bones.py file.fbx [bone_substring]
import struct, sys, zlib

def read_nodes(f, ver):
    big = ver >= 7500
    nodes = []
    while True:
        if big:
            end, nprops, plen = struct.unpack("<QQQ", f.read(24))
        else:
            end, nprops, plen = struct.unpack("<III", f.read(12))
        nlen = f.read(1)[0]
        name = f.read(nlen).decode("ascii", "replace")
        if end == 0:
            return nodes
        props = [read_prop(f) for _ in range(nprops)]
        children = []
        if f.tell() < end:
            children = read_nodes(f, ver)
        f.seek(end)
        nodes.append((name, props, children))

def read_prop(f):
    t = f.read(1).decode()
    if t == "Y": return struct.unpack("<h", f.read(2))[0]
    if t == "C": return f.read(1)[0] != 0
    if t == "I": return struct.unpack("<i", f.read(4))[0]
    if t == "F": return struct.unpack("<f", f.read(4))[0]
    if t == "D": return struct.unpack("<d", f.read(8))[0]
    if t == "L": return struct.unpack("<q", f.read(8))[0]
    if t in "fdlib":
        n, enc, clen = struct.unpack("<III", f.read(12))
        data = f.read(clen)
        if enc == 1: data = zlib.decompress(data)
        fmt = {"f": "f", "d": "d", "l": "q", "i": "i", "b": "?"}[t]
        return list(struct.unpack("<%d%s" % (n, fmt), data))
    if t in "SR":
        n = struct.unpack("<I", f.read(4))[0]
        d = f.read(n)
        return d.decode("utf-8", "replace") if t == "S" else d
    raise ValueError("prop type " + t)

def load(path):
    with open(path, "rb") as f:
        assert f.read(21) == b"Kaydara FBX Binary  \x00"
        f.read(2)
        ver = struct.unpack("<I", f.read(4))[0]
        return ver, read_nodes(f, ver)

def find(nodes, name):
    return [n for n in nodes if n[0] == name]

def props70(node):
    out = {}
    for c in node[2]:
        if c[0] == "Properties70":
            for p in c[2]:
                out[p[1][0]] = p[1][4:]
    return out

def main(path, sub=""):
    ver, top = load(path)
    objs = find(top, "Objects")[0][2]
    gs = props70(find(top, "GlobalSettings")[0])
    print("FBX", ver, "UnitScaleFactor", gs.get("UnitScaleFactor"), "UpAxis", gs.get("UpAxis"), "FrontAxis", gs.get("FrontAxis"))
    for n in objs:
        if n[0] == "Model" and n[1][2] in ("LimbNode", "Root", "Null"):
            nm = n[1][1].split("\x00")[0]
            if sub and sub not in nm: continue
            p = props70(n)
            fmt = lambda v: "(" + ", ".join("%.4f" % x for x in v) + ")" if v else "-"
            print("MODEL %-28s %-8s T%s R%s Pre%s Post%s S%s" % (nm, n[1][2], fmt(p.get("Lcl Translation")), fmt(p.get("Lcl Rotation")),
                  fmt(p.get("PreRotation")), fmt(p.get("PostRotation")), fmt(p.get("Lcl Scaling"))))
    for n in objs:
        if n[0] == "Deformer" and n[1][2] == "Cluster":
            nm = n[1][1].split("\x00")[0]
            if sub and sub not in nm: continue
            tl = [c for c in n[2] if c[0] == "TransformLink"]
            if tl:
                m = tl[0][1][0]
                print("CLUSTER %-40s TL row3(origin) %s  row0 %s" % (nm, ["%.4f" % x for x in m[12:15]], ["%.3f" % x for x in m[0:3]]))

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        sys.exit(__doc__ or "usage: python fbx_bones.py file.fbx [bone_substring]   (prints each bone's local transform and each skin cluster's TransformLink)")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
