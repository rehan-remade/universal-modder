"""Dump a Blitz3D .b3d with its skeleton, skin weights and keyframes to JSON (Blitz3D space, unconverted).

Keeps everything an animated viewmodel needs, not only the static pose:
node tree (rest pos / scale / rot as w,x,y,z), meshes (vertices, normals, uvs, triangles per brush),
BONE weights, KEYS, ANIM and the SEQS chunk (named frame ranges, an extension some SCP: CB fork models
carry: name, first frame, last frame, flags).

Usage:
  python -I b3d_skin.py MODEL.b3d OUT.json
"""
import json
import struct
import sys


class Reader:
    def __init__(self, data, pos=0, end=None):
        self.data, self.pos = data, pos
        self.end = len(data) if end is None else end

    def left(self):
        return self.end - self.pos

    def i32(self, n=1):
        v = struct.unpack_from("<%di" % n, self.data, self.pos)
        self.pos += 4 * n
        return v if n > 1 else v[0]

    def f32(self, n=1):
        v = struct.unpack_from("<%df" % n, self.data, self.pos)
        self.pos += 4 * n
        return list(v) if n > 1 else v[0]

    def cstr(self):
        z = self.data.index(b"\0", self.pos)
        s = self.data[self.pos:z].decode("latin-1")
        self.pos = z + 1
        return s

    def chunks(self):
        while self.left() >= 8:
            tag = self.data[self.pos:self.pos + 4].decode("latin-1")
            size = struct.unpack_from("<i", self.data, self.pos + 4)[0]
            start = self.pos + 8
            self.pos = start + size
            yield tag, Reader(self.data, start, start + size)


def read_texs(r):
    out = []
    while r.left() > 0:
        name = r.cstr()
        flags, blend = r.i32(2)
        pos, scale, rot = r.f32(2), r.f32(2), r.f32()
        out.append({"file": name, "flags": flags, "blend": blend, "pos": pos, "scale": scale, "rot": rot})
    return out


def read_brus(r):
    n = r.i32()
    out = []
    while r.left() > 0:
        name = r.cstr()
        rgba, shine = r.f32(4), r.f32()
        blend, fx = r.i32(2)
        texs = list(r.i32(n)) if n > 1 else ([r.i32()] if n == 1 else [])
        out.append({"name": name, "rgba": rgba, "shininess": shine, "blend": blend, "fx": fx, "textures": texs})
    return out


def read_mesh(r):
    mesh = {"brush": r.i32(), "verts": None, "surfaces": []}
    for tag, c in r.chunks():
        if tag == "VRTS":
            flags, sets, size = c.i32(3)
            pos, nrm, col, uv = [], [], [], []
            while c.left() > 0:
                pos.append(c.f32(3))
                if flags & 1:
                    nrm.append(c.f32(3))
                if flags & 2:
                    col.append(c.f32(4))
                coords = [c.f32(size) if size > 1 else [c.f32()] for _ in range(sets)]
                uv.append(coords[0] if coords else [0.0, 0.0])
            mesh["verts"] = {"pos": pos, "normal": nrm, "color": col, "uv": uv}
        elif tag == "TRIS":
            brush = c.i32()
            tris = []
            while c.left() > 0:
                tris.append(list(c.i32(3)))
            mesh["surfaces"].append({"brush": brush, "tris": tris})
    return mesh


def read_node(r):
    node = {"name": r.cstr(), "pos": r.f32(3), "scale": r.f32(3), "rot": r.f32(4), "children": []}
    for tag, c in r.chunks():
        if tag == "MESH":
            node["mesh"] = read_mesh(c)
        elif tag == "BONE":
            w = []
            while c.left() > 0:
                w.append([c.i32(), c.f32()])
            node["bone"] = w
        elif tag == "KEYS":
            flags = c.i32()
            keys = node.setdefault("keys", {})
            while c.left() > 0:
                k = {"frame": c.i32()}
                if flags & 1:
                    k["pos"] = c.f32(3)
                if flags & 2:
                    k["scale"] = c.f32(3)
                if flags & 4:
                    k["rot"] = c.f32(4)
                slot = keys.setdefault(str(k["frame"]), {"frame": k["frame"]})
                slot.update(k)
        elif tag == "ANIM":
            flags, frames = c.i32(2)
            node["anim"] = {"flags": flags, "frames": frames, "fps": c.f32()}
        elif tag == "SEQS":
            name = c.cstr()
            vals = list(c.i32(c.left() // 4))
            node.setdefault("seqs", []).append({"name": name, "first": vals[0], "last": vals[1], "rest": vals[2:]})
        elif tag == "NODE":
            node["children"].append(read_node(c))
        else:
            node.setdefault("unknown", []).append(tag)
    if "keys" in node:
        node["keys"] = sorted(node["keys"].values(), key=lambda k: k["frame"])
    return node


def main():
    data = open(sys.argv[1], "rb").read()
    top = Reader(data)
    out = {"texs": [], "brus": [], "root": None}
    for tag, r in top.chunks():
        assert tag == "BB3D", tag
        out["version"] = r.i32()
        for t, c in r.chunks():
            if t == "TEXS":
                out["texs"] = read_texs(c)
            elif t == "BRUS":
                out["brus"] = read_brus(c)
            elif t == "NODE":
                out["root"] = read_node(c)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(out, f)

    def walk(n, d=0):
        extra = []
        if "mesh" in n:
            extra.append("MESH %d verts, surfaces %s" % (len(n["mesh"]["verts"]["pos"]), [(s["brush"], len(s["tris"])) for s in n["mesh"]["surfaces"]]))
        if "bone" in n:
            extra.append("bone %d" % len(n["bone"]))
        if "keys" in n:
            extra.append("keys %d" % len(n["keys"]))
        if "anim" in n:
            extra.append("anim %s" % n["anim"])
        if "seqs" in n:
            extra.append("seqs %s" % [(s["name"], s["first"], s["last"]) for s in n["seqs"]])
        print("  " * d + n["name"], " | ".join(extra))
        for ch in n["children"]:
            walk(ch, d + 1)

    print("texs", [t["file"] for t in out["texs"]])
    print("brus", [(b["name"], b["textures"], b["blend"], b["fx"]) for b in out["brus"]])
    walk(out["root"])


if __name__ == "__main__":
    main()
