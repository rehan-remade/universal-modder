# Skeletons without the editor: the package the editor's "Import skeleton" writes (knowledge/techniques/editor-free-bannerlord-assets.md).
# Mapped on Native's editor packages (human_skeleton in human/human.tpac, horse_skeleton in pack_horse_customrig,
# camel_skeleton in camel/camel.tpac); all three parse and re-pack byte-identical (python sdk_skeleton.py verify).
#   Skeleton resource (type d5a335c6...6113): record u32 0, u32 0, u8 0 (1 on the editor's leftover "_notused"
#   skeletons), import source guid; data "Skeleton definition" (377dd011, value 0) and "User data" (6dc06a9b, value 3).
#   Skeleton definition: name, u32 bones, per bone: name, i32 parent (-1 root), local frame as 4 rows x 4 f32: side,
#   forward, up (the rotation's columns) and origin, each row's 4th value unused (garbage in Native, 0 0 0 1 here).
#   Bones in parent-first order; world = parent world x local. Units metres, Z up, humans face -Y, left side -X.
#   User data (physics): 9 f32 header (0.2, 0, 0, 0, 1, 0, 0, 0, 1), skeleton type ("human" = biped, "horse" = the
#   quadruped animals, "other"; parse key "name"), empty string + vec4 (20 bytes, "pre"), u32 bodies, per bone: bone
#   name, u8 ragdoll flag, bone type ("body": biped_* / quadruped_* / ""), body part ("group": hit location), f32 mass,
#   capsule (vec4 p1, vec4 p2, f32 radius; -1 none; the first capsule is the ragdoll body), second capsule, f32;
#   then u32 0, u32 joints, per joint: u32 0, type ("d6" ragdoll joint or "ik"), name, child bone, parent bone,
#   frame (quaternion w x y z + position x y z 1, at the child's origin), d6: 6 motion strings (x, y, z, twist,
#   swing1, swing2: locked / limited / free) + 5 f32 limits; ik: 5 f32.
#   python sdk_skeleton.py verify                     round-trip the Native skeletons
#   python sdk_skeleton.py show <skeleton name>       print a Native skeleton's bones and physics
import os, re, struct, sys, uuid
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, tpac

SKEL_TYPE = bytes.fromhex("d5a335c6bbeadd45883eaa57e4196113")
SKEL_DEF = bytes.fromhex("377dd01120e76b40ab67c846f96a8771")      # "Skeleton definition"
USER_DATA = bytes.fromhex("6dc06a9b46a5af40a55540d301ab4b2f")     # "User data"
tpac.DATA_KIND.update({SKEL_DEF: 0, USER_DATA: 3})
NATIVE_EM = os.path.join(tpac.NATIVE, "EmAssetPackages")
NATIVE_SKELETONS = {"human_skeleton": "human/human.tpac", "horse_skeleton": "pack_horse_customrig/pack_horse_customrig.tpac",
                    "camel_skeleton": "camel/camel.tpac"}

def _S(b, o):
    n = struct.unpack_from("<I", b, o)[0]; return b[o + 4:o + 4 + n].decode(), o + 4 + n

# ---- skeleton definition ----
def parse_definition(d):
    name, o = _S(d, 0); nb = struct.unpack_from("<I", d, o)[0]; o += 4; bones = []
    for _ in range(nb):
        bn, o = _S(d, o); par = struct.unpack_from("<i", d, o)[0]
        rows = np.frombuffer(d, "<f4", 16, o + 4).reshape(4, 4)
        bones.append(dict(name=bn, parent=par, R=rows[:3, :3].T.astype(np.float64), o=rows[3, :3].astype(np.float64),
                          pad=d[o + 4:o + 68]))
        o += 68
    if o != len(d): raise ValueError("skeleton definition layout differs")
    return name, bones

def pack_definition(name, bones, keep_pad=False):
    out = tpac._S(name) + struct.pack("<I", len(bones))
    for b in bones:
        rows = np.zeros((4, 4), np.float32); rows[:3, :3] = np.asarray(b["R"]).T; rows[3, :3] = b["o"]; rows[3, 3] = 1
        raw = bytearray(rows.tobytes())
        if keep_pad and "pad" in b:   # Native files keep stack garbage in the unused 4th values
            for k in range(4): raw[16 * k + 12:16 * k + 16] = b["pad"][16 * k + 12:16 * k + 16]
        out += tpac._S(b["name"]) + struct.pack("<i", b["parent"]) + bytes(raw)
    return out

def world_frames(bones):
    W = []
    for b in bones:
        if b["parent"] < 0: W.append((b["R"], b["o"]))
        else:
            PR, Po = W[b["parent"]]; W.append((PR @ b["R"], PR @ b["o"] + Po))
    return W

# ---- user data (physics bodies, ragdoll and IK joints) ----
def parse_userdata(d):
    hdr = struct.unpack_from("<9f", d, 0); name, o = _S(d, 36); pre = d[o:o + 20]; o += 20
    nb = struct.unpack_from("<I", d, o)[0]; o += 4; bodies = []
    for _ in range(nb):
        bn, o = _S(d, o); fl = d[o]; o += 1; body, o = _S(d, o); grp, o = _S(d, o)
        f = struct.unpack_from("<20f", d, o); o += 80
        bodies.append(dict(bone=bn, ragdoll=fl, body=body, group=grp, mass=f[0], cap1=(f[1:5], f[5:9], f[9]),
                           cap2=(f[10:14], f[14:18], f[18]), extra=f[19]))
    z, nj = struct.unpack_from("<II", d, o); o += 8; joints = []
    for k in range(nj):
        flag = struct.unpack_from("<I", d, o)[0]; o += 4
        ty, o = _S(d, o); jn, o = _S(d, o); child, o = _S(d, o); parent, o = _S(d, o)
        frame = struct.unpack_from("<8f", d, o); o += 32; motions = []
        if ty == "d6":
            for _ in range(6): m, o = _S(d, o); motions.append(m)
        lim = struct.unpack_from("<5f", d, o); o += 20
        joints.append(dict(flag=flag, type=ty, name=jn, child=child, parent=parent, frame=frame, motions=motions, limits=lim))
    if o != len(d): raise ValueError("user data layout differs (%d of %d)" % (o, len(d)))
    return dict(header=hdr, name=name, pre=pre, bodies=bodies, z=z, joints=joints)

def pack_userdata(u):
    out = struct.pack("<9f", *u["header"]) + tpac._S(u["name"]) + u.get("pre", bytes(20)) + struct.pack("<I", len(u["bodies"]))
    for b in u["bodies"]:
        out += tpac._S(b["bone"]) + bytes([b["ragdoll"]]) + tpac._S(b["body"]) + tpac._S(b["group"]) \
            + struct.pack("<20f", b["mass"], *b["cap1"][0], *b["cap1"][1], b["cap1"][2], *b["cap2"][0], *b["cap2"][1], b["cap2"][2], b["extra"])
    out += struct.pack("<II", u.get("z", 0), len(u["joints"]))
    for j in u["joints"]:
        out += struct.pack("<I", j.get("flag", 0)) + tpac._S(j["type"]) + tpac._S(j["name"]) + tpac._S(j["child"]) + tpac._S(j["parent"]) \
            + struct.pack("<8f", *j["frame"]) + b"".join(tpac._S(m) for m in j["motions"]) + struct.pack("<%df" % len(j["limits"]), *j["limits"])
    return out

# ---- Native skeletons ----
def native(name):
    """(record, definition blob, user data blob) of a Native skeleton from its editor package."""
    p = os.path.join(NATIVE_EM, NATIVE_SKELETONS[name])
    with open(p, "rb") as f:
        h = f.read(0x24); meta = h + f.read(struct.unpack_from("<I", h, 0x1c)[0])
        m = re.search(re.escape(SKEL_TYPE) + rb"(.{16})(.{4})" + re.escape(tpac._S(name)), meta, re.S)
        R = m.end(); L = struct.unpack_from("<I", meta, R)[0]; E = R + 8 + L; rec = meta[R:E]
        out = {"guid": m.group(1), "record": rec}
        for k in range(struct.unpack_from("<I", meta, E + 8)[0]):
            q = E + 12 + 69 * k; off, raw, st = struct.unpack_from("<QQQ", meta, q)
            f.seek(off); s = f.read(st); out[meta[q + 40:q + 56]] = tpac.lz4_decompress(s, raw) if st < raw else s
    return out

# ---- writer ----
def skeleton_record(src_guid, leftover=False):
    rec = bytearray(4) + struct.pack("<II", 0, 0) + bytes([1 if leftover else 0]) + src_guid
    struct.pack_into("<I", rec, 0, len(rec) - 8)
    return bytes(rec)

def write_skeleton(name, bones, userdata, out_dir=None, force=False, source_name=None):
    """<source>_geo.tpac holding an import source and the skeleton resource. bones: [dict(name, parent, R, o)] in
    parent-first order (local frames). userdata: parse_userdata-style dict. Rewrites keep the ids of an existing
    package of that name (installed or staged). Returns (path, skeleton guid)."""
    base = source_name or name
    out = os.path.join(out_dir or tpac.ASSETS, base + "_geo.tpac")
    if os.path.exists(out) and not force: raise FileExistsError(out + " exists (use --force)")
    ids = None
    for p in (out, os.path.join(tpac.ASSETS, base + "_geo.tpac")):
        if os.path.exists(p):
            b = open(p, "rb").read(); meta = b[:0x24 + struct.unpack_from("<I", b, 0x1c)[0]]
            i, s = meta.find(SKEL_TYPE), meta.find(tpac.IMPORT_TYPE)
            if i > 0 and s > 0: ids = (b[8:24], meta[s + 16:s + 32], meta[i + 16:i + 32]); break
    package, src, skel = ids or (uuid.uuid4().bytes, uuid.uuid4().bytes, uuid.uuid4().bytes)
    src_rec = bytearray(4) + struct.pack("<II", 0, 1) + tpac._S(config.source_base(base + ".fbx")) \
        + bytes(8) + struct.pack("<I", 1) + SKEL_TYPE + skel + bytes(4)
    struct.pack_into("<I", src_rec, 0, len(src_rec) - 8)
    data = tpac.pack_resources(package, [(tpac.IMPORT_TYPE, src, 0, base + ".fbx", bytes(src_rec), []),
                                         (SKEL_TYPE, skel, 0, name, skeleton_record(src), [(SKEL_DEF, pack_definition(name, bones)),
                                                                                         (USER_DATA, pack_userdata(userdata))])])
    if out_dir: os.makedirs(out_dir, exist_ok=True)
    open(out, "wb").write(data)
    return out, skel

def read_skeleton(path):
    """(name, guid, bones, userdata) from a skeleton package we wrote (or any one-skeleton package)."""
    import sdk_mesh
    for r in sdk_mesh.walk(open(path, "rb").read()):
        if r["type"] == SKEL_TYPE:
            blobs = {e["type"]: e["blob"] for e in r["ents"]}
            return r["name"], r["guid"], parse_definition(blobs[SKEL_DEF])[1], parse_userdata(blobs[USER_DATA])
    raise ValueError("no skeleton in " + path)

# ---- skeleton from an FBX or glTF file ----
MAX_BONES = 64                                          # engine limit (rgl_max_bones)
GLTF_AXES = {"umodel": np.array([[0.0, 0, 1], [1, 0, 0], [0, 1, 0]]),  # UModel (Unreal) glTF export -> Bannerlord
             "yup": np.array([[1.0, 0, 0], [0, 0, -1], [0, 1, 0]])}    # plain Y-up glTF -> Z-up

def _local_bones(names, parents, G):
    """[dict(name, parent, R, o)] from world 4x4 matrices (scale removed), parents as indices."""
    import sdk_mesh
    out = []
    for i, n in enumerate(names):
        Rw = sdk_mesh.rotation_only(G[i]); ow = G[i][:3, 3]
        if parents[i] < 0: out.append(dict(name=n, parent=-1, R=Rw, o=ow.copy())); continue
        Rp = sdk_mesh.rotation_only(G[parents[i]]); op = G[parents[i]][:3, 3]
        out.append(dict(name=n, parent=parents[i], R=Rp.T @ Rw, o=Rp.T @ (ow - op)))
    return out

def _order(names, parents):
    """Parent-first order (stable)."""
    done, order = set(), []
    while len(order) < len(names):
        for i in range(len(names)):
            if i not in done and (parents[i] < 0 or parents[i] in done): done.add(i); order.append(i)
    m = {o: k for k, o in enumerate(order)}
    return [names[i] for i in order], [m[parents[i]] if parents[i] >= 0 else -1 for i in order], order

def bones_from_fbx(path):
    """LimbNode bones of an FBX at their bind (property) pose, fully evaluated transforms, Z-up as the mesh import."""
    import sdk_mesh
    from fbx_bones import load, find, props70
    ver, top = load(path); nodes = sdk_mesh.FbxNodes(top)
    C = np.eye(4); C[:3, :3] = sdk_mesh.axis_conv(props70(find(top, "GlobalSettings")[0]))
    ids = [mid for mid, m in nodes.models.items() if m[1][2] == "LimbNode" and not nodes.name(mid).endswith("notused")]   # nubs: no bone
    names = [nodes.name(mid) for mid in ids]; parents = []
    for mid in ids:
        p = nodes.parent.get(mid)
        while p is not None and p not in ids: p = nodes.parent.get(p)
        parents.append(ids.index(p) if p is not None else -1)
    G = [C @ nodes.global_(mid) @ C.T for mid in ids]
    names, parents, order = _order(names, parents)
    return _local_bones(names, parents, [G[i] for i in order])

def bones_from_gltf(path, axes="yup"):
    """Joints of the first skin of a glTF (node TRS / matrix), parent-first."""
    import json
    g = json.load(open(path)); nodes = g["nodes"]; joints = g["skins"][0]["joints"]
    par = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}
    def local(n):
        if "matrix" in n: return np.array(n["matrix"], float).reshape(4, 4).T
        x, y, z, w = n.get("rotation", [0, 0, 0, 1]); M = np.eye(4)
        M[:3, :3] = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                              [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                              [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]) @ np.diag(n.get("scale", [1, 1, 1]))
        M[:3, 3] = n.get("translation", [0, 0, 0]); return M
    def world(i):
        M = local(nodes[i])
        while i in par: i = par[i]; M = local(nodes[i]) @ M
        return M
    C = np.eye(4); C[:3, :3] = GLTF_AXES[axes]
    names = [nodes[j].get("name", "bone_%d" % j) for j in joints]; parents = []
    for j in joints:
        p = par.get(j)
        while p is not None and p not in joints: p = par.get(p)
        parents.append(joints.index(p) if p is not None else -1)
    G = [C @ world(j) @ C.T for j in joints]
    names, parents, order = _order(names, parents)
    return _local_bones(names, parents, [G[i] for i in order])

def auto_userdata(bones, kind="other", total_mass=70.0):
    """Minimal ragdoll: a capsule along each bone that has a child (to its farthest child), d6 joints (twist and swing
    limited, as the human spine) from each body to the nearest ancestor body; other bones carry no body."""
    none = ((0.0, 0, 0, 1), (0.0, 0, 0, 1), -1.0); kids = {}
    for i, b in enumerate(bones):
        if b["parent"] >= 0: kids.setdefault(b["parent"], []).append(i)
    length = {i: max((np.linalg.norm(bones[c]["o"]), c) for c in kids[i]) for i in kids}
    length = {i: v for i, v in length.items() if v[0] > 0.02}
    total = sum(v[0] for v in length.values()) or 1.0; bodies = []
    for i, b in enumerate(bones):
        if i not in length:
            bodies.append(dict(bone=b["name"], ragdoll=0, body="", group="none", mass=0.0, cap1=none, cap2=none, extra=-1.0)); continue
        L, c = length[i]; e = bones[c]["o"]; r = float(np.clip(0.18 * L, 0.02, 0.3))
        p1 = tuple(0.1 * e) + (1.0,); p2 = tuple(0.9 * e) + (1.0,)
        bodies.append(dict(bone=b["name"], ragdoll=1, body="", group="chest", mass=round(total_mass * L / total, 2),
                           cap1=(p1, p2, r), cap2=(p1, p2, r), extra=r * 1.4))
    joints = []
    for i, b in enumerate(bones):
        if i not in length: continue
        p = b["parent"]
        while p >= 0 and p not in length: p = bones[p]["parent"]
        if p < 0: continue
        joints.append(dict(flag=0, type="d6", name="joint_%s_%s" % (bones[p]["name"].lower(), b["name"].lower()), child=b["name"],
                           parent=bones[p]["name"], frame=(1.0, 0, 0, 0, 0, 0, 0, 1),
                           motions=["locked", "locked", "locked", "limited", "limited", "limited"], limits=(0.01, -0.436, 0.436, 0.349, 0.349)))
    return dict(header=(0.2, 0, 0, 0, 1, 0, 0, 0, 1), name=kind, pre=bytes(20), bodies=bodies, z=0, joints=joints)

def skeleton_from_file(path, name=None, out_dir=None, force=False, physics="auto", kind="other", axes="yup"):
    """install.py skeleton: FBX or glTF -> <name>_geo.tpac (skeleton resource). Returns (path, guid, bones, userdata)."""
    bones = bones_from_gltf(path, axes) if path.lower().endswith((".gltf", ".glb")) else bones_from_fbx(path)
    if len(bones) > MAX_BONES: raise ValueError("%d bones: the engine takes at most %d" % (len(bones), MAX_BONES))
    if not bones: raise ValueError("no bones in " + path)
    name = name or os.path.splitext(os.path.basename(path))[0] + "_skeleton"
    u = auto_userdata(bones, kind) if physics == "auto" else \
        dict(header=(0.2, 0, 0, 0, 1, 0, 0, 0, 1), name=kind, pre=bytes(20), z=0, joints=[],
             bodies=[dict(bone=b["name"], ragdoll=0, body="", group="none", mass=0.0, cap1=((0.0, 0, 0, 1), (0.0, 0, 0, 1), -1.0),
                          cap2=((0.0, 0, 0, 1), (0.0, 0, 0, 1), -1.0), extra=-1.0) for b in bones])
    p, g = write_skeleton(name, bones, u, out_dir, force, source_name=name)
    return p, g, bones, u

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(open(__file__, encoding="utf-8").read().split(chr(10) + "import os, re")[0]); sys.exit(0 if a else 2)
    if a[0] == "verify":
        for nm in NATIVE_SKELETONS:
            x = native(nm); d, u = x[SKEL_DEF], x[USER_DATA]
            name, bones = parse_definition(d); U = parse_userdata(u)
            print("%-15s bones %2d bodies %2d joints %2d  definition re-pack %s  user data re-pack %s  record %s" % (
                nm, len(bones), len(U["bodies"]), len(U["joints"]), pack_definition(name, bones, keep_pad=True) == d,
                pack_userdata(U) == u, x["record"].hex()))
    elif a[0] == "show":
        x = native(a[1]); name, bones = parse_definition(x[SKEL_DEF]); U = parse_userdata(x[USER_DATA]); W = world_frames(bones)
        for b, w in zip(bones, W): print("%-22s parent %-22s world origin %s" % (b["name"], bones[b["parent"]]["name"] if b["parent"] >= 0 else "-", np.round(w[1], 3)))
        for b in U["bodies"]: print("body %-20s ragdoll %d %-22s %-14s mass %5.1f r %.3f/%.3f" % (b["bone"], b["ragdoll"], b["body"], b["group"], b["mass"], b["cap1"][2], b["cap2"][2]))
        for j in U["joints"]: print("joint %-3s %-40s %s <- %s %s %s" % (j["type"], j["name"], j["child"], j["parent"], j["motions"], [round(x, 3) for x in j["limits"]]))
