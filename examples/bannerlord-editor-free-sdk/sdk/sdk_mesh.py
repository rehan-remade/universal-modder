# Static and skinned meshes without the editor: FBX -> <fbx name>_geo.tpac + RuntimeDataCache/<package>.rdc, laid out
# like the editor's FBX import (Convert to Z-up, no skeleton). Mapped on 71 editor-made mesh packages and their FBX
# sources (knowledge/techniques/editor-free-bannerlord-assets.md):
#   package: import source resource (<fbx>.fbx: path, xxh64 of the FBX, produced metamesh, import settings blob) and
#   a metamesh resource (type 978b8fa0, resource flag 1) named after the FBX mesh node. Metamesh record: u32 0, u32 1,
#   import source guid, f32 FLT_MAX, 28 zero bytes, u32 submesh count, u32 1, then per submesh: 00 02 00 00 + 16 zero,
#   00 02 00 00 00, submesh guid, name, 8 zero, material resource guid, 8 x f32 1, 36 zero, u32 positions, u32 faces,
#   u32 vertices, u32 weighted positions, u32 0, bbox min (x,y,z,1), bbox max, centre = bbox middle, f32 radius = half
#   the bbox diagonal, u32 bones (28 skinned, 0 static), fixed parameters, 00 and u32 1 (another submesh follows) or
#   u32 0 + 16 zero + 01 01 after the last. Data: per submesh "Mesh edit data" (owner = submesh), and f6304064 (owner
#   = metamesh): u32 count, per submesh its name and its material name.
#   Mesh edit data: u32 n + n x (x,y,z,1) positions (the FBX control points the submesh uses, in index order), u32 0,
#   u32 m + m x 92-byte vertices (u32 position, normal, tangent, bitangent, normal again: 4 f32 each with w = 1, uv0,
#   uv1, u32 colour, u32 0xffffffff), u32 k + k x 3 u32 triangles (FBX order), u32 0, u32 w + w x (4 f32 weights,
#   4 u8 bones) for skinned meshes, u32 0. Vertices = unique (position, normal, uvs, colour) corners in FBX order.
#   Vertex stream (.rdc, LZ4, h1 = xxh64 of the edit data): u32 index count, u16 indices (Forsyth-ordered), a table of
#   14 (offset, size) pairs, 14 attribute streams (see stream_blob).
#   python sdk_mesh.py mesh <fbx> [--name N] [--material A[,B]] [--out DIR] [--rdc DIR] [--force]
#   python sdk_mesh.py obj <file_geo.tpac> <out.obj> [--rdc DIR]         decode a mesh package (positions, uv, normals)
#   python sdk_mesh.py verify [names...]                                 rebuild editor meshes from their FBX and compare
import math, os, struct, sys, uuid
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, tpac
from fbx_bones import load, find, props70

META_TYPE = bytes.fromhex("978b8fa07c19ea4bb95b53846cae834e")
EDIT_DATA = bytes.fromhex("5f98413dd224c14f82e46a6e0da3f4e2")    # "Mesh edit data"
VERTEX_STREAM = bytes.fromhex("97f81dbb4f587047abf2663fe449f247")  # "Mesh vertex stream"
SUBMESH_NAMES = bytes.fromhex("f6304064428a864cb9359b9daa9391c2")
tpac.DATA_KIND.update({EDIT_DATA: 0, SUBMESH_NAMES: 0})
MESH_SETTINGS_HEAD = bytes.fromhex("0e00000061735f7665727465785f616e696d0101040000006e6f6e650300000001000000000101000000")
MESH_SETTINGS_TAIL = bytes.fromhex("0000000000010700000064656661756c740000000000000000000000000000000000000000")
SUB_HEAD = bytes.fromhex("00020000") + bytes(16)
SUB_PARAMS = bytes.fromhex("00000000" "0000803f" "00000000" "0000803f" "0000803f" "0000803f" "0000803f" "3333733f"
                           "0000803f" "0000003f" "0000003f" "0000803f" "78000000" "0000" "000080bf" "0000803f")
VERT = np.dtype([("pi", "<u4"), ("n", "<f4", 4), ("t", "<f4", 4), ("b", "<f4", 4), ("n2", "<f4", 4), ("uv0", "<f4", 2),
                 ("uv1", "<f4", 2), ("c0", "<u4"), ("c1", "<u4")])
WEIGHT = np.dtype([("w", "<f4", 4), ("b", "u1", 4)])

# ---- FBX ----
# ---- FBX node transforms, as the FBX SDK's EvaluateGlobalTransform (what the editor's importers call) ----
# local = T * Roff * Rp * Rpre * R(order) * Rpost^-1 * Rp^-1 * Soff * Sp * S * Sp^-1; Rpre / Rpost / the rotation order
# only count when RotationActive is set (as the SDK and Blender's importer do); missing properties come from the
# file's Model property template; global = parent global * local (non-uniform parent scale with InheritType RSrs
# is not modelled; none of the test files has it). Geometry is placed by global * geometric transform.
_ORDERS = {0: "XYZ", 1: "XZY", 2: "YZX", 3: "YXZ", 4: "ZXY", 5: "ZYX", 6: "XYZ"}

def euler_matrix(e, order=0):
    """3x3 rotation of FBX Euler angles (degrees); order 0 XYZ = X applied first (Rz Ry Rx)."""
    x, y, z = np.radians(np.asarray(e, float))
    M = {"X": np.array([[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]]),
         "Y": np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]]),
         "Z": np.array([[math.cos(z), -math.sin(z), 0], [math.sin(z), math.cos(z), 0], [0, 0, 1]])}
    R = np.eye(3)
    for ax in _ORDERS.get(int(order), "XYZ"): R = M[ax] @ R
    return R

def _euler(e): return euler_matrix(e, 0)

def fbx_model_template(top):
    """Default Model properties from the file's Definitions (FbxNode property template)."""
    for d in find(top, "Definitions"):
        for ot in d[2]:
            if ot[0] == "ObjectType" and ot[1] and ot[1][0] == "Model":
                for pt in ot[2]:
                    if pt[0] == "PropertyTemplate": return props70(pt)
    return {}

class FbxNodes:
    """Model nodes of a loaded FBX with their parents; local / global 4x4 matrices with optional animated T, R, S."""
    def __init__(self, top):
        objs = find(top, "Objects")[0][2]; conns = find(top, "Connections")[0][2]
        self.models = {n[1][0]: n for n in objs if n[0] == "Model"}
        tmpl = fbx_model_template(top); self.props = {}
        for mid, m in self.models.items():
            p = dict(tmpl); p.update(props70(m)); self.props[mid] = p
        self.parent = {}
        for c in conns:
            k = c[1]
            if k[0] == "OO" and k[1] in self.models and k[2] in self.models: self.parent[k[1]] = k[2]
    def name(self, mid): return self.models[mid][1][1].split("\x00")[0]
    def _v(self, mid, key, default):
        v = self.props[mid].get(key)
        return np.array(v[:3], float) if v is not None and len(v) >= 3 else np.array(default, float)
    def local(self, mid, T=None, R=None, S=None):
        p = self.props[mid]; v = lambda k, d=(0, 0, 0): self._v(mid, k, d)
        active = bool(p.get("RotationActive", [0])[0])
        order = int(p.get("RotationOrder", [0])[0]) if active else 0
        def m4(R3=None, t=None):
            M = np.eye(4)
            if R3 is not None: M[:3, :3] = R3
            if t is not None: M[:3, 3] = t
            return M
        T = v("Lcl Translation") if T is None else np.asarray(T, float)
        R = v("Lcl Rotation") if R is None else np.asarray(R, float)
        S = v("Lcl Scaling", (1, 1, 1)) if S is None else np.asarray(S, float)
        Rp, Sp = v("RotationPivot"), v("ScalingPivot")
        pre = euler_matrix(v("PreRotation")) if active else np.eye(3)
        post = euler_matrix(v("PostRotation")) if active else np.eye(3)
        return (m4(t=T) @ m4(t=v("RotationOffset")) @ m4(t=Rp) @ m4(pre) @ m4(euler_matrix(R, order)) @ m4(post.T)
                @ m4(t=-Rp) @ m4(t=v("ScalingOffset")) @ m4(t=Sp) @ m4(np.diag(S)) @ m4(t=-Sp))
    def geometric(self, mid):
        M = np.eye(4); v = lambda k, d=(0, 0, 0): self._v(mid, k, d)
        M[:3, :3] = euler_matrix(v("GeometricRotation")) @ np.diag(v("GeometricScaling", (1, 1, 1))); M[:3, 3] = v("GeometricTranslation")
        return M
    def global_(self, mid, locals_=None):
        """locals_: {model id: 4x4 local} overrides (animated frames); others use the static properties."""
        M = np.eye(4); n = mid
        while n is not None:
            L = locals_.get(n) if locals_ else None
            M = (self.local(n) if L is None else L) @ M; n = self.parent.get(n)
        return M

def rotation_only(M):
    """Rotation part of a 3x3 (or 4x4) matrix with scale removed (polar decomposition)."""
    A = np.asarray(M, float)[:3, :3]; U, _, Vt = np.linalg.svd(A); R = U @ Vt
    if np.linalg.det(R) < 0: U[:, -1] *= -1; R = U @ Vt
    return R

def axis_conv(gs):
    """Convert to Z-up as the editor does it on Blender exports: Y-up files get Rz(180) Rx(90), Z-up stay."""
    up = gs.get("UpAxis", [1])[0]
    if up == 2: return np.eye(3)
    if up == 1: return np.array([[-1.0, 0, 0], [0, 0, 1], [0, 1, 0]])
    raise ValueError("X-up FBX not supported")

def _layers(g, kind, idx_name, data_name):
    out = []
    for c in g[2]:
        if c[0] == kind:
            d = {cc[0]: cc[1] for cc in c[2]}
            out.append(dict(map=d["MappingInformationType"][0], ref=d["ReferenceInformationType"][0],
                            data=np.array(d[data_name][0]), index=np.array(d[idx_name][0]) if idx_name in d else None))
    return out

def _corner_values(L, width, cp, ci, poly):
    data = L["data"].reshape(-1, width)
    key = {"ByPolygonVertex": ci, "ByVertice": cp, "ByVertex": cp, "ByControlPoint": cp, "ByPolygon": poly,
           "AllSame": np.zeros_like(ci)}[L["map"]]
    if L["ref"] == "IndexToDirect" and L["index"] is not None: key = L["index"][key]
    return data[key]

def read_fbx(path):
    """Mesh nodes of an FBX with geometry, per-corner layers, materials and skin weights."""
    ver, top = load(path)
    gs = props70(find(top, "GlobalSettings")[0]); nodes = FbxNodes(top)
    objs = find(top, "Objects")[0][2]; conns = find(top, "Connections")[0][2]
    byid = {n[1][0]: n for n in objs}
    geoms = {n[1][0]: n for n in objs if n[0] == "Geometry" and n[1][2] == "Mesh"}
    models = {n[1][0]: n for n in objs if n[0] == "Model"}
    g2m, mats, links = {}, {}, {}
    for c in conns:
        k = c[1]
        if k[0] != "OO": continue
        a, b = k[1], k[2]
        if a in geoms and b in models: g2m[a] = b
        if byid.get(a, ("",))[0] == "Material" and b in models: mats.setdefault(b, []).append(byid[a][1][1].split("\x00")[0])
        links.setdefault(b, []).append(a)
    out = []
    for gid, g in geoms.items():
        m = models[g2m[gid]]
        ch = lambda name: next((c[1][0] for c in g[2] if c[0] == name), None)
        weights = None
        for d in links.get(gid, []):
            if byid.get(d, ("",))[0] == "Deformer" and byid[d][1][2] == "Skin":
                weights = [[] for _ in range(len(ch("Vertices")) // 3)]
                for cl in links.get(d, []):
                    cn = byid[cl]; bones = [x for x in links.get(cl, []) if x in models]
                    dd = {x[0]: x[1][0] for x in cn[2] if x[0] in ("Indexes", "Weights")}
                    if not bones or "Indexes" not in dd: continue
                    bname = models[bones[0]][1][1].split("\x00")[0]
                    try: bi = int(bname.rsplit("_", 1)[1])
                    except ValueError: raise ValueError("bone %s: expected bip01_<name>_<index>" % bname)
                    for i, w in zip(dd["Indexes"], dd["Weights"]): weights[i].append((bi, w))
        idx = [x[1][1].split("\x00")[0].rsplit("_", 1)[1] for x in models.values() if x[1][1].startswith("bip01_")]
        nbones = 1 + max([int(i) for i in idx if i.isdigit()] or [-1])
        out.append(dict(name=m[1][1].split("\x00")[0], props=props70(m), M=nodes.global_(g2m[gid]) @ nodes.geometric(g2m[gid]), nbones=nbones, V=np.array(ch("Vertices"), float).reshape(-1, 3),
                        PVI=np.array(ch("PolygonVertexIndex")), normals=_layers(g, "LayerElementNormal", "NormalsIndex", "Normals"),
                        uvs=_layers(g, "LayerElementUV", "UVIndex", "UV"), colors=_layers(g, "LayerElementColor", "ColorIndex", "Colors"),
                        mat=_layers(g, "LayerElementMaterial", "_", "Materials"), materials=mats.get(g2m[gid], []), weights=weights))
    return gs, out

# ---- tangents (MikkTSpace-style: angle-weighted, per-corner projected; matches the editor within float noise) ----
def tangents(P, pi, N, uv, F):
    nr = len(pi); T = np.zeros((nr, 3)); B = np.zeros((nr, 3)); uvf = np.c_[uv[:, 0], 1 - uv[:, 1]]
    for tri in F:
        p = P[pi[tri]]; t_ = uvf[tri]
        e1, e2 = p[1] - p[0], p[2] - p[0]; d1, d2 = t_[1] - t_[0], t_[2] - t_[0]
        r = d1[0] * d2[1] - d2[0] * d1[1]
        if abs(r) < 1e-20: continue
        t = (e1 * d2[1] - e2 * d1[1]) / r; bb = (e2 * d1[0] - e1 * d2[0]) / r
        for j in range(3):
            k = tri[j]; n = N[k]
            u, v = p[(j + 1) % 3] - p[j], p[(j + 2) % 3] - p[j]
            u = u - n * (n @ u); v = v - n * (n @ v)
            w = math.acos(max(-1.0, min(1.0, (u @ v) / max(np.linalg.norm(u) * np.linalg.norm(v), 1e-20))))
            tt = t - n * (n @ t); bt = bb - n * (n @ bb)
            T[k] += w * tt / max(np.linalg.norm(tt), 1e-20); B[k] += w * bt / max(np.linalg.norm(bt), 1e-20)
    T = T - N * np.sum(N * T, 1, keepdims=True); ln = np.linalg.norm(T, axis=1, keepdims=True)
    T = np.where(ln > 1e-12, T / np.maximum(ln, 1e-20), [1.0, 0.0, 0.0])   # no UV area: the editor writes (1, 0, 0)
    c = np.cross(N.astype(np.float32), T.astype(np.float32))   # the editor's bitangent is exactly +-cross(n, t)
    return T, c * np.where((np.sum(B * c, 1, keepdims=True) < 0) & (ln > 1e-12), -1.0, 1.0)

def _color(c):
    c = np.clip(np.rint(np.asarray(c) * 255), 0, 255).astype(np.uint32)
    return (c[:, 3] << 24) | (c[:, 0] << 16) | (c[:, 1] << 8) | c[:, 2]   # assumed A8R8G8B8 (all test sources: 0 or none)

def submeshes(path):
    """FBX -> [(metamesh name, [submesh dict])]: one metamesh per mesh node, one submesh per material name."""
    gs, meshes = read_fbx(path); C = axis_conv(gs); out = []
    for m in meshes:
        Mx = C @ m["M"][:3, :3]                               # node global x geometric transform, Z-up
        V = m["V"] @ Mx.T + C @ m["M"][:3, 3]
        PVI = m["PVI"]; cp = np.where(PVI < 0, ~PVI, PVI); ci = np.arange(len(PVI))
        ends = np.where(PVI < 0)[0]; starts = np.r_[0, ends[:-1] + 1]; poly = np.repeat(np.arange(len(ends)), ends - starts + 1)
        if not m["normals"]: raise ValueError("%s: no normals" % m["name"])
        Nraw = _corner_values(m["normals"][0], 3, cp, ci, poly)
        N = Nraw @ (C @ rotation_only(m["M"])).T; N /= np.linalg.norm(N, axis=1, keepdims=True)   # rotation only, as the importer
        UV = [_corner_values(L, 2, cp, ci, poly) for L in m["uvs"][:2]]
        if not UV: UV = [np.zeros((len(PVI), 2))]
        if len(UV) < 2: UV.append(np.zeros((len(PVI), 2)))   # the editor writes zeros for a missing second UV set
        COL = _color(_corner_values(m["colors"][0], 4, cp, ci, poly)) if m["colors"] else np.full(len(PVI), 0xffffffff, np.uint32)
        pm = np.asarray(m["mat"][0]["data"]).astype(int)[poly] if m["mat"] and m["mat"][0]["map"] == "ByPolygon" else np.zeros(len(PVI), int)
        N32 = N.astype(np.float32); UV32 = [u.astype(np.float32) for u in UV]
        mats = m["materials"] or [m["name"]]
        groups = []
        for slot in sorted(set(pm.tolist())):
            nm = mats[slot] if slot < len(mats) else mats[-1]
            g = next((g for g in groups if g[0] == nm), None)
            if g: g[1].append(slot)
            else: groups.append((nm, [slot]))
        subs = []
        for gi, (mname, slots) in enumerate(groups):
            sel = [k for k in range(len(ends)) if pm[starts[k]] in slots]
            used = sorted({int(cp[c]) for k in sel for c in range(starts[k], ends[k] + 1)})
            local = {v: i for i, v in enumerate(used)}
            keymap, corners, faces = {}, [], []
            for k in sel:
                ids = []
                for c in range(starts[k], ends[k] + 1):
                    key = (local[int(cp[c])], N32[c].tobytes(), UV32[0][c].tobytes(), UV32[1][c].tobytes(), int(COL[c]))   # float32 values, as the editor compares
                    if key not in keymap: keymap[key] = len(corners); corners.append(c)
                    ids.append(keymap[key])
                for j in range(1, len(ids) - 1): faces.append((ids[0], ids[j], ids[j + 1]))
            rc = np.array(corners); pi = np.array([local[int(cp[c])] for c in rc], np.uint32); F = np.array(faces, np.uint32)
            Pl = V[used]; Nl = N[rc]
            T, B = tangents(Pl, pi, Nl, UV[0][rc], F)
            W = None
            if m["weights"] is not None:
                W = np.zeros(len(used), WEIGHT)
                for i, v in enumerate(used):
                    inf = m["weights"][v]
                    if len(inf) > 4: inf = sorted(inf, key=lambda x: -x[1])[:4]; s = sum(w for _, w in inf); inf = [(b, w / s) for b, w in inf]
                    ws = np.array([w for _, w in inf], np.float32); ws = ws / np.sum(ws, dtype=np.float32)   # normalised in float32
                    for j, (b, _) in enumerate(inf): W[i]["w"][j] = ws[j]; W[i]["b"][j] = b
            subs.append(dict(name=m["name"] if len(groups) == 1 else "%s.%d" % (m["name"], gi), material=mname, P=Pl, pi=pi, N=Nl, nbones=m["nbones"],
                             T=T, B=B, uv0=UV[0][rc], uv1=UV[1][rc], c0=COL[rc], F=F, W=W))
        out.append((m["name"], subs))
    return out

# ---- edit data ----
def edit_blob(s):
    n = len(s["P"]); P = np.c_[s["P"], np.ones(n)].astype("<f4")
    V = np.zeros(len(s["pi"]), VERT); one = np.ones((len(V), 1))
    V["pi"] = s["pi"]; V["n"] = np.c_[s["N"], one]; V["t"] = np.c_[s["T"], one]; V["b"] = np.c_[s["B"], one]; V["n2"] = V["n"]
    V["uv0"] = s["uv0"]; V["uv1"] = s["uv1"]; V["c0"] = s["c0"]; V["c1"] = 0xffffffff
    W = s["W"] if s["W"] is not None else np.zeros(0, WEIGHT)
    return struct.pack("<I", n) + P.tobytes() + struct.pack("<II", 0, len(V)) + V.tobytes() + struct.pack("<I", len(s["F"])) \
        + np.asarray(s["F"], "<u4").tobytes() + struct.pack("<II", 0, len(W)) + W.tobytes() + struct.pack("<I", 0)

def pack_edit(E):
    """Re-pack parsed edit data (parse_edit) as is."""
    return struct.pack("<I", len(E["P"])) + np.asarray(E["P"], "<f4").tobytes() + struct.pack("<II", 0, len(E["V"])) + E["V"].tobytes()         + struct.pack("<I", len(E["F"])) + np.asarray(E["F"], "<u4").tobytes() + struct.pack("<II", 0, len(E["W"])) + E["W"].tobytes() + struct.pack("<I", 0)

def parse_edit(d):
    n = struct.unpack_from("<I", d, 0)[0]; P = np.frombuffer(d, "<f4", 4 * n, 4).reshape(n, 4); o = 4 + 16 * n
    z0, m = struct.unpack_from("<II", d, o); o += 8
    V = np.frombuffer(d, VERT, m, o); o += VERT.itemsize * m
    k = struct.unpack_from("<I", d, o)[0]; F = np.frombuffer(d, "<u4", 3 * k, o + 4).reshape(k, 3); o += 4 + 12 * k
    z1, w = struct.unpack_from("<II", d, o); o += 8
    W = np.frombuffer(d, WEIGHT, w, o); o += WEIGHT.itemsize * w
    z2 = struct.unpack_from("<I", d, o)[0]; o += 4
    if (z0, z1, z2) != (0, 0, 0) or o != len(d): raise ValueError("edit data layout differs")
    return dict(P=P, V=V, F=F, W=W)

# ---- vertex stream ----
def forsyth(F, nv, cache=32):
    """Triangle order for the vertex cache (Forsyth: cache 32, decay 1.5, last 0.75, valence 2 x n^-0.5, float32,
    swap-remove; equals the editor's order on most meshes, differs only in some dead-end picks)."""
    T = [tuple(int(x) for x in t) for t in F]; nt = len(T); f = np.float32
    vt = [[] for _ in range(nv)]
    for i, t in enumerate(T):
        for v in t: vt[v].append(i)
    rem = [len(x) for x in vt]; pos = [-1] * nv; added = [False] * nt
    def vs_(v):
        if rem[v] == 0: return f(-1.0)
        s = f(0.0); p = pos[v]
        if p >= 0: s = f(0.75) if p < 3 else f((1.0 - (p - 3) / (cache - 3)) ** 1.5)
        return f(s + f(2.0) * f(rem[v] ** -0.5))
    vs = [vs_(v) for v in range(nv)]
    ts = [f(vs[a] + vs[b] + vs[c]) for a, b, c in T]
    best, bs = -1, None
    for i in range(nt):
        if bs is None or ts[i] > bs: best, bs = i, ts[i]
    cachel, out = [], []
    while len(out) < nt:
        if best < 0:
            bs = None
            for i in range(nt):
                if not added[i] and (bs is None or ts[i] > bs): best, bs = i, ts[i]
        t = T[best]; added[best] = True; out.append(t)
        for v in t:
            L = vt[v]; j = L.index(best); L[j] = L[-1]; L.pop(); rem[v] -= 1
        cachel = list(t) + [v for v in cachel if v not in t]
        ev = cachel[cache:]; cachel = cachel[:cache]
        for i, v in enumerate(cachel): pos[v] = i
        for v in ev: pos[v] = -1
        for v in cachel + ev: vs[v] = vs_(v)
        best, bs = -1, None
        for v in cachel:
            for ti in vt[v]:
                a, b, c = T[ti]; ts[ti] = f(vs[a] + vs[b] + vs[c])
                if bs is None or ts[ti] > bs: best, bs = ti, ts[ti]
        for v in ev:
            for ti in vt[v]: a, b, c = T[ti]; ts[ti] = f(vs[a] + vs[b] + vs[c])
    return np.array(out, np.uint32).reshape(-1, 3)

def _pack_n(v, xbits, sign=None):
    v = np.asarray(v, np.float32); h = np.float32(.5)
    x = np.floor((v[:, 0] * h + h) * np.float32((1 << xbits) - 1)).astype(np.uint32)
    y = np.floor((v[:, 1] * h + h) * np.float32(2047)).astype(np.uint32); z = np.floor((v[:, 2] * h + h) * np.float32(1023)).astype(np.uint32)
    out = (x << 21) | (y << 10) | z
    if sign is not None: out |= (sign.astype(np.uint32) << 31)
    return out.astype("<u4")

def _qtangent(n, t, b, hand):
    out = np.zeros((len(n), 4), np.float32); f = np.float32
    for i in range(len(n)):
        m = np.stack([n[i], t[i], b[i] * f(hand[i])], 1).astype(np.float32)
        tr = m[0, 0] + m[1, 1] + m[2, 2]
        if tr > 0:
            s = np.sqrt(tr + f(1)) * f(2); q = [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, s / f(4)]
        else:
            k = int(np.argmax([m[0, 0], m[1, 1], m[2, 2]]))
            if k == 0: s = np.sqrt(f(1) + m[0, 0] - m[1, 1] - m[2, 2]) * f(2); q = [s / f(4), (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s, (m[2, 1] - m[1, 2]) / s]
            elif k == 1: s = np.sqrt(f(1) + m[1, 1] - m[0, 0] - m[2, 2]) * f(2); q = [(m[0, 1] + m[1, 0]) / s, s / f(4), (m[1, 2] + m[2, 1]) / s, (m[0, 2] - m[2, 0]) / s]
            else: s = np.sqrt(f(1) + m[2, 2] - m[0, 0] - m[1, 1]) * f(2); q = [(m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, s / f(4), (m[1, 0] - m[0, 1]) / s]
        q = np.array(q, np.float32); q /= np.sqrt(np.dot(q, q))
        if q[3] < 0: q = -q
        if q[3] < f(1 / 32767): q[3] = f(1 / 32767)
        out[i] = -q if hand[i] > 0 else q
    return np.trunc(out * np.float32(32767)).astype("<i2")

def stream_blob(E, tris=None):
    """Vertex stream from edit data: u32 index count, u16 indices, then 14 attribute streams behind a table of
    (offset, size) pairs (offsets from the table start, table = 28 u64): 0 colour, 1 second colour, 2 uv0 (u, 1-v),
    3 uv1, 4 and 5 position f32x3, 6 normal f32x3, 7 tangent f32x3 + handedness, 8 weights u8x3 + 0, 9 bones u8x4,
    10 normal 11:11:10, 11 position half4, 12 tangent 10:11:10 + handedness bit, 13 QTangent i16x4."""
    V = E["V"]; P = E["P"]; nv = len(V)
    if tris is None: tris = forsyth(E["F"], nv)
    n, t, b = V["n"][:, :3], V["t"][:, :3], V["b"][:, :3]
    d = np.einsum("ij,ij->i", np.cross(n.astype(np.float64), t), b)
    hand = np.where(d > 0, 1.0, -1.0); neg = d < 0
    W = np.zeros((nv, 4), np.uint8); Bn = np.zeros((nv, 4), np.uint8)
    if len(E["W"]):
        w = E["W"]["w"][V["pi"]].astype(np.float32); W = np.trunc(w * np.float32(255)).astype(np.uint8); W[:, 3] = 0
        Bn = E["W"]["b"][V["pi"]]
    pos = P[V["pi"]]
    S = [V["c0"].astype("<u4").tobytes(), V["c1"].astype("<u4").tobytes(),
         np.c_[V["uv0"][:, 0], 1 - V["uv0"][:, 1]].astype("<f4").tobytes(), np.c_[V["uv1"][:, 0], 1 - V["uv1"][:, 1]].astype("<f4").tobytes(),
         pos[:, :3].astype("<f4").tobytes(), pos[:, :3].astype("<f4").tobytes(), n.astype("<f4").tobytes(),
         np.c_[t, hand].astype("<f4").tobytes(), W.tobytes(), np.ascontiguousarray(Bn).tobytes(), _pack_n(n, 11),
         pos[:, :4].astype("<f2").tobytes(), _pack_n(t, 10, neg), _qtangent(n, t, b, np.where(d < 0, -1, 1)).tobytes()]
    S = [s if isinstance(s, bytes) else s.tobytes() for s in S]
    idx = np.asarray(tris, "<u2").reshape(-1)
    table = []; off = 0xe0
    for s in S: table += [off, len(s)]; off += len(s)
    return struct.pack("<I", len(idx)) + idx.tobytes() + struct.pack("<28Q", *table) + b"".join(S)

def parse_stream(v):
    nidx = struct.unpack_from("<I", v, 0)[0]; o = 4 + 2 * nidx; t = struct.unpack_from("<28Q", v, o)
    return np.frombuffer(v, "<u2", nidx, 4).reshape(-1, 3), [v[o + t[2 * i]:o + t[2 * i] + t[2 * i + 1]] for i in range(14)]

# ---- records ----
def meta_record(src_guid, subs):
    out = bytearray(4) + struct.pack("<II", 0, 1) + src_guid + struct.pack("<f", 3.4028234663852886e38) + bytes(28) \
        + struct.pack("<II", len(subs), 1)
    for i, s in enumerate(subs):
        P = s["P"]; mn, mx = P.min(0).astype(np.float32), P.max(0).astype(np.float32)
        c = (mn + mx) * np.float32(0.5); r = np.sqrt(np.sum((mx - c) ** 2, dtype=np.float32), dtype=np.float32)   # float32 as the editor
        out += SUB_HEAD + bytes.fromhex("0002000000") + s["guid"] + tpac._S(s["name"]) + bytes(8) + s["material_guid"] \
            + struct.pack("<8f", *[1.0] * 8) + bytes(36) \
            + struct.pack("<5I", len(P), len(s["F"]), len(s["pi"]), len(s["W"]) if s["W"] is not None else 0, 0) \
            + struct.pack("<4f", *mn, 1) + struct.pack("<4f", *mx, 1) + struct.pack("<4f", *c, 1) + struct.pack("<f", r) \
            + struct.pack("<I", s.get("nbones", 28) if s["W"] is not None else 0) + SUB_PARAMS + b"\0" \
            + (struct.pack("<I", 1) if i + 1 < len(subs) else struct.pack("<I", 0) + bytes(16) + b"\x01\x01")
    # the next submesh's 00 02 00 00 + 16 zero follows the u32 1 (written at the top of the loop)
    struct.pack_into("<I", out, 0, len(out) - 8)
    return bytes(out)

def names_blob(subs):
    return struct.pack("<I", len(subs)) + b"".join(tpac._S(s["name"]) + tpac._S(s["material"]) for s in subs)

def find_material(name, extra=None):
    for d in [extra, tpac.ASSETS] + [x for x in os.environ.get("TPAC_STAGE", "").split(";") if x]:
        if not d: continue
        p = os.path.join(d, name + "_mtl.tpac")
        if os.path.exists(p): return open(p, "rb").read(0x44)[0x34:0x44]
    return None

def metamesh_owner(name, skip=None):
    """Installed package that already holds a metamesh of that name (same-name items of one type clash)."""
    import glob
    pat = struct.pack("<I", 1) + tpac._S(name)
    for p in glob.glob(os.path.join(tpac.ASSETS, "*_geo.tpac")):
        if skip and os.path.basename(p) == skip: continue
        with open(p, "rb") as f:
            h = f.read(0x24); meta = h + f.read(struct.unpack_from("<I", h, 0x1c)[0])
        i = meta.find(META_TYPE)
        while i >= 0:
            if meta[i + 32:i + 32 + len(pat)] == pat: return p
            i = meta.find(META_TYPE, i + 1)
    return None

def write_mesh(fbx, out_dir=None, rdc_dir=None, materials=None, force=False, ids=None, mtl_dir=None, name=None):
    """<fbx name>_geo.tpac + RuntimeDataCache/<package>.rdc from an FBX (one mesh node). materials: list of material
    names per submesh (default: the FBX material names). Returns (tpac path, rdc path, [submesh summaries])."""
    base = os.path.splitext(os.path.basename(fbx))[0]
    out = os.path.join(out_dir or tpac.ASSETS, base + "_geo.tpac")
    if os.path.exists(out) and not force: raise FileExistsError(out + " exists (use --force)")
    metas = submeshes(fbx)
    if len(metas) != 1: raise ValueError("%s: %d mesh nodes (one expected)" % (fbx, len(metas)))
    mname, subs = metas[0]
    return write_metamesh(base, mname, subs, open(fbx, "rb").read(), out_dir, rdc_dir, materials, force, ids, mtl_dir, name)

def write_metamesh(base, mname, subs, source_bytes=b"", out_dir=None, rdc_dir=None, materials=None, force=False, ids=None,
                   mtl_dir=None, name=None):
    """Package + vertex cache from prepared submeshes (dicts as submeshes() makes them: name, material, P, pi, N, T,
    B, uv0, uv1, c0, F, W, nbones). Used for FBX and for other sources (glTF, PSK)."""
    out = os.path.join(out_dir or tpac.ASSETS, base + "_geo.tpac")
    if os.path.exists(out) and not force: raise FileExistsError(out + " exists (use --force)")
    if name and name != mname:   # rename the metamesh (and its submeshes) instead of using the FBX node name
        for sb in subs: sb["name"] = name + sb["name"][len(mname):]
        mname = name
    clash = metamesh_owner(mname, skip=base + "_geo.tpac")
    if clash: print("WARNING: metamesh %s already exists in %s (same-name items clash; use --name)" % (mname, os.path.basename(clash)))
    if ids is None:   # reuse the ids of an installed or staged package of that name (its .rdc name stays valid)
        ids = {}
        for p in (out, os.path.join(tpac.ASSETS, base + "_geo.tpac")):
            if os.path.exists(p):
                ids = package_ids(open(p, "rb").read()); break
    package = ids.get("package") or uuid.uuid4().bytes
    src_guid = ids.get("source") or uuid.uuid4().bytes
    meta_guid = ids.get("meta") or uuid.uuid4().bytes
    for i, s in enumerate(subs):
        s["guid"] = ids.get("subs", {}).get(s["name"]) or uuid.uuid4().bytes
        if materials: s["material"] = materials[min(i, len(materials) - 1)]
        g = find_material(s["material"], mtl_dir)
        if g is None: print("WARNING: material %s not found, submesh %s gets a zero guid" % (s["material"], s["name"]))
        s["material_guid"] = g or bytes(16)
    edits = [edit_blob(s) for s in subs]
    src_rec = bytearray(4) + struct.pack("<II", 0, 1) + tpac._S(config.source_base(base + ".fbx")) \
        + struct.pack("<Q", tpac.xxh64(source_bytes)) + struct.pack("<I", 1) + META_TYPE + meta_guid + bytes(4)
    struct.pack_into("<I", src_rec, 0, len(src_rec) - 8)
    settings = MESH_SETTINGS_HEAD + tpac._S(mname) + MESH_SETTINGS_TAIL
    data = pack_mesh_package(package, [(tpac.IMPORT_TYPE, src_guid, 0, base + ".fbx", bytes(src_rec), [(tpac.ANIM_SETTINGS, settings, src_guid)]),
                                       (META_TYPE, meta_guid, 1, mname, meta_record(src_guid, subs),
                                        [(EDIT_DATA, e, s["guid"]) for e, s in zip(edits, subs)] + [(SUBMESH_NAMES, names_blob(subs), meta_guid)])])
    rp = tpac.rdc_path(package, rdc_dir)
    entries = [(meta_guid, s["guid"], VERTEX_STREAM, stream_blob(parse_edit(e)), struct.pack("<Q", tpac.xxh64(e)), bytes(8)) for e, s in zip(edits, subs)]
    os.makedirs(os.path.dirname(rp), exist_ok=True)
    open(rp, "wb").write(tpac.pack_rdc(entries, comp=1, flag=1))
    if out_dir: os.makedirs(out_dir, exist_ok=True)
    open(out, "wb").write(data)
    return out, rp, [(s["name"], s["material"], len(s["P"]), len(s["pi"]), len(s["F"]), s["W"] is not None) for s in subs]

def pack_mesh_package(package, resources):
    """Like tpac.pack_resources, but each data entry carries its own owner guid (edit data: the submesh)."""
    resources = sorted(resources, key=lambda r: r[1])
    meta = 0x24 + sum(40 + len(n.encode()) + len(rec) + 8 + 4 + 69 * len(ents) + 4 for _, _, _, n, rec, ents in resources)
    head = b"TPAC" + struct.pack("<I", 2) + package + struct.pack("<II", len(resources), meta - 0x24) + bytes(4)
    body = b""; data = b""
    for ty, g, fl, name, rec, ents in resources:
        body += ty + g + struct.pack("<I", fl) + tpac._S(name) + rec + struct.pack("<Q", tpac.xxh64(rec)) + struct.pack("<I", len(ents))
        for dt, blob, owner in ents:
            c = tpac.lz4_compress(blob); c = c if len(c) < len(blob) else blob
            body += struct.pack("<QQQ", meta + len(data), len(blob), len(c)) + owner + dt + struct.pack("<Q", tpac.xxh64(blob)) \
                + struct.pack("<IB", tpac.DATA_KIND.get(dt, 0), 1)
            data += c
        body += bytes(4)
    return head + body + data

# ---- reading packages ----
def walk(b):
    q = 0x24; res = []
    for _ in range(struct.unpack_from("<I", b, 0x18)[0]):
        ty, g, fl = b[q:q + 16], b[q + 16:q + 32], struct.unpack_from("<I", b, q + 32)[0]
        n = struct.unpack_from("<i", b, q + 36)[0]; name = b[q + 40:q + 40 + n].decode(); R = q + 40 + n
        L = struct.unpack_from("<I", b, R)[0]; E = R + 8 + L; ne = struct.unpack_from("<I", b, E + 8)[0]; q2 = E + 12; ents = []
        for _ in range(ne):
            off, raw, st = struct.unpack_from("<QQQ", b, q2)
            blob = tpac.lz4_decompress(b[off:off + st], raw) if st < raw else bytes(b[off:off + st])
            ents.append(dict(owner=b[q2 + 24:q2 + 40], type=b[q2 + 40:q2 + 56], hash=b[q2 + 56:q2 + 64], blob=blob)); q2 += 69
        res.append(dict(type=ty, guid=g, flag=fl, name=name, rec=b[R:E], ents=ents)); q = q2 + 4
    return res

def package_ids(b):
    res = walk(b); ids = {"package": b[8:24], "subs": {}}
    for r in res:
        if r["type"] == tpac.IMPORT_TYPE: ids["source"] = r["guid"]
        if r["type"] == META_TYPE:
            ids["meta"] = r["guid"]
            for e in r["ents"]:
                if e["type"] == SUBMESH_NAMES:
                    k = struct.unpack_from("<I", e["blob"], 0)[0]; o = 4; names = []
                    for _ in range(k):
                        a = struct.unpack_from("<I", e["blob"], o)[0]; names.append(e["blob"][o + 4:o + 4 + a].decode()); o += 4 + a
                        o += 4 + struct.unpack_from("<I", e["blob"], o)[0]
            edits = [e["owner"] for e in r["ents"] if e["type"] == EDIT_DATA]
            for e in edits:
                i = r["rec"].find(e); n = struct.unpack_from("<I", r["rec"], i + 16)[0]
                ids["subs"][r["rec"][i + 20:i + 20 + n].decode()] = e
    return ids

def read_mesh(path, rdc_dir=None):
    """[(submesh name, edit data dict, triangles from the stream, streams)] of a mesh package."""
    b = open(path, "rb").read(); res = walk(b); out = []
    here = os.path.dirname(os.path.abspath(path))
    cands = [tpac.RDC_DIR] if os.path.normcase(here) == os.path.normcase(os.path.abspath(tpac.ASSETS)) else         [d for d in (rdc_dir, here, os.path.join(os.path.dirname(here), "RuntimeDataCache")) if d]
    rp = next((tpac.rdc_path(b[8:24], d) for d in cands if os.path.exists(tpac.rdc_path(b[8:24], d))), tpac.rdc_path(b[8:24], cands[0]))
    rdc = {e["id"]: e for e in tpac.read_rdc(rp)} if os.path.exists(rp) else {}
    for r in res:
        if r["type"] != META_TYPE: continue
        for e in r["ents"]:
            if e["type"] != EDIT_DATA: continue
            i = r["rec"].find(e["owner"]); n = struct.unpack_from("<I", r["rec"], i + 16)[0]
            E = parse_edit(e["blob"]); tris = S = None
            if e["owner"] in rdc:
                x = rdc[e["owner"]]; v = tpac.lz4_decompress(x["blob"], x["raw"]) if x["stored"] < x["raw"] else x["blob"]
                tris, S = parse_stream(v)
            out.append((r["rec"][i + 20:i + 20 + n].decode(), E, tris, S))
    return out

def to_obj(path, out, rdc_dir=None):
    lines = []; base = 1
    for name, E, tris, S in read_mesh(path, rdc_dir):
        V = E["V"]; P = E["P"][V["pi"]]
        lines.append("o " + name)
        lines += ["v %.6f %.6f %.6f" % tuple(p[:3]) for p in P]
        lines += ["vt %.6f %.6f" % (u, 1 - v) for u, v in V["uv0"]]
        lines += ["vn %.6f %.6f %.6f" % tuple(n[:3]) for n in V["n"]]
        F = tris if tris is not None else E["F"]
        lines += ["f " + " ".join("%d/%d/%d" % (base + int(i), base + int(i), base + int(i)) for i in t) for t in F]
        base += len(V)
    open(out, "w").write("\n".join(lines) + "\n")

def triangle_soup(path, rdc_dir=None):
    """{submesh name: set of triangles as rounded (position, uv0) corner triples, rotation-normalised} + normals."""
    out = {}
    for name, E, tris, S in read_mesh(path, rdc_dir):
        V = E["V"]; P = E["P"][V["pi"]][:, :3]
        F = tris if tris is not None else E["F"]
        key = lambda i: tuple(np.round(P[i], 4)) + tuple(np.round(V["uv0"][i], 4))
        soup = set()
        for t in F:
            k = [key(int(i)) for i in t]; r = min(range(3), key=lambda j: k[j]); soup.add(tuple(k[r:] + k[:r]))
        out[name] = (soup, E, F)
    return out

def compare(editor_path, ours_path, rdc_dir=None):
    """Geometry equivalence of two mesh packages: per submesh triangle soup overlap, counts, normal/tangent error
    (vertices matched by position + uv)."""
    a, b = triangle_soup(editor_path), triangle_soup(ours_path, rdc_dir); rows = []
    for name in a:
        if name not in b: rows.append((name, "missing")); continue
        sa, Ea, Fa = a[name]; sb, Eb, Fb = b[name]
        Va, Vb = Ea["V"], Eb["V"]
        ka = {}
        for i, v in enumerate(Va): ka.setdefault(tuple(np.round(Ea["P"][v["pi"]][:3], 5)) + tuple(np.round(v["uv0"], 5)), []).append(i)
        dn = dt = 0.0; m = 0; dts = []
        for i, v in enumerate(Vb):
            c = ka.get(tuple(np.round(Eb["P"][v["pi"]][:3], 5)) + tuple(np.round(v["uv0"], 5)))
            if not c: continue
            j = min(c, key=lambda j: float(np.abs(Va[j]["n"][:3] - v["n"][:3]).max()))
            m += 1; dn = max(dn, float(np.abs(Va[j]["n"][:3] - v["n"][:3]).max())); dts.append(float(np.abs(Va[j]["t"][:3] - v["t"][:3]).max()))
        dt = float(np.percentile(dts, 99)) if dts else 0.0
        rows.append((name, len(sa & sb) / max(len(sa), 1), len(Ea["P"]), len(Eb["P"]), len(Va), len(Vb), len(Fa), len(Fb), m / max(len(Vb), 1), dn, dt))
    return rows

if __name__ == "__main__":
    a = sys.argv[1:]; opt = lambda k: a[a.index(k) + 1] if k in a else None
    if not a or a[0] in ("-h", "--help"):
        print(open(__file__, encoding="utf-8").read().split(chr(10) + "import math")[0]); sys.exit(0 if a else 2)
    if a[0] == "mesh":
        mats = opt("--material").split(",") if opt("--material") else None
        for f in [x for x in a[1:] if x.lower().endswith(".fbx")]:
            o, rp, info = write_mesh(f, opt("--out"), opt("--rdc"), mats, "--force" in a, name=opt("--name"))
            print("wrote", o, "\n  and", rp)
            for s in info: print("  submesh %-28s material %-24s positions %d vertices %d triangles %d%s" % (s[0], s[1], s[2], s[3], s[4], " skinned" if s[5] else ""))
    elif a[0] == "verify":   # rebuild editor-made meshes from their FBX into a scratch folder and compare geometry
        import glob, tempfile
        tmp = opt("--tmp") or tempfile.mkdtemp(prefix="sdk_mesh_")
        names = [x for x in a[1:] if not x.startswith("--") and x != opt("--tmp")]
        for p in sorted(glob.glob(os.path.join(tpac.ASSETS, "*_geo.tpac"))):
            b = open(p, "rb").read(); res = walk(b)
            if not any(r["type"] == META_TYPE for r in res): continue
            src = [r for r in res if r["type"] == tpac.IMPORT_TYPE][0]; base = src["name"][:-4]
            if names and base not in names: continue
            fbx = os.path.join(config.ASSET_SOURCES, src["name"])
            if not os.path.exists(fbx) or struct.pack("<Q", tpac.xxh64(open(fbx, "rb").read())) not in b:
                print("%-24s skipped: FBX changed since the editor import" % base); continue
            try: out, rp, info = write_mesh(fbx, tmp, tmp, force=True)
            except Exception as ex: print("%-24s ERROR %s" % (base, ex)); continue
            for r in compare(p, out, tmp):
                if len(r) == 2: print("%-24s %s %s" % (base, r[0], r[1])); continue
                print("%-24s %-22s triangles same %.4f  positions %d/%d vertices %d/%d triangles %d/%d  matched %.4f  normal err %.1e tangent err (99%%) %.1e"
                      % ((base,) + r))
    elif a[0] == "obj":
        to_obj(a[1], a[2], opt("--rdc")); print("wrote", a[2])
