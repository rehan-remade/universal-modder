# Exact asset format details read from the engine (TaleWorlds.Native.dll, Modding Kit editor build), as a library
# tpac.py / sdk_mesh.py can import. The reasoning is in knowledge/techniques/editor-free-bannerlord-assets.md.
#   python tw_formats.py selftest          check every rule below against the module's installed files (read only; needs
#                                          BANNERLORD_MODULE_DIR; selftest.py checks the same rules against Native)
#   python tw_formats.py texhash <file_tex.tpac> [--fix]   show / rewrite a texture's pixel hash (the "8 opaque bytes")
import os, struct, sys, glob, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tpac

def _g(h): return bytes.fromhex(h)

# ---- data types: guid -> (name, version). The version is the u32 after each package data entry and the u32 in each
# RDC entry; the engine rejects a cache entry whose version differs from the current one.
DATA_TYPES = {
    _g("5f98413dd224c14f82e46a6e0da3f4e2"): ("Mesh edit data", 0),
    _g("97f81dbb4f587047abf2663fe449f247"): ("Mesh vertex stream", 1),
    _g("f6304064428a864cb9359b9daa9391c2"): ("Metamesh Editmode Misc", 0),
    _g("3e6141af4dbdec468284debb56c042dc"): ("Cloth map", 0),
    _g("100f7eb949df66468f1dada6630d4b4e"): ("Cloth cook", 1),
    _g("6f131e6cb7d0ff41bb7a275f3630db25"): ("Optimized animation", 2),
    _g("2afcc38fc94bc5468525f33a6e257b72"): ("Shortened optimized animation", 2),
    _g("6d817dd0ed3c1c42a6afb793e75dc2be"): ("Animation definition", 0),
    _g("e25b477c8d7c1d43b0e153218d047fb9"): ("Texture import settings", 4),
    _g("2c4eee70e4792d4b8d54d53ecd2a559c"): ("Texture pixel data", 0),
    _g("a781b98aa06b0849960691ad341d19a9"): ("Source file info", 0),
    _g("f83d7de95742db409f421436e339d581"): ("Fbx import settings", 4),
    _g("8fa0673e80c4334e99e34c849aa20307"): ("Metamesh import settings", 3),
    _g("bbcb8382793aea40aead7f5a2ceb747f"): ("Physics sphere static cook", 3),
    _g("2fd127df74d0b845a4ed8068c0f4988d"): ("Physics sphere dynamic cook", 3),
}
def type_version(type_guid): return DATA_TYPES.get(bytes(type_guid), ("?", 0))[1]

# ---- texture record ----
TEX_PIXEL_HASH_SEED = 0x41c64e6d   # record u64 after the platform string = XXH64(all mips, this seed)
def texture_pixel_hash(pixels):
    return struct.pack("<Q", tpac.xxh64(pixels, TEX_PIXEL_HASH_SEED))

TEX_IMPORT_FLAGS = {"dont_degrade": 0x2, "dont_compress": 0x20, "dont_delay_loading": 0x80, "dont_resize_in_atlas": 0x100,
                    "ignore_alpha": 0x80000, "for_colorgrade": 0x100000, "for_terrain": 0x200000, "is_bumpmap": 0x400000,
                    "is_specularmap": 0x800000, "is_envmap": 0x1000000, "for_skybox_background": 0x4000000,
                    "for_skybox_cloud": 0x8000000, "for_skybox_sun": 0x10000000}
TEX_FLAGS = {"has_alpha": 0x8000, "is_cubemap": 0x2000}   # written in table order: has_alpha, is_cubemap
TEX_IMPORT_FLAG_ORDER = ["dont_degrade", "dont_delay_loading", "is_envmap", "is_specularmap", "is_bumpmap", "for_terrain",
                         "for_colorgrade", "for_skybox_background", "for_skybox_cloud", "for_skybox_sun", "dont_compress",
                         "ignore_alpha", "dont_resize_in_atlas"]   # the engine writes set flags in this order
TEX_PLATFORMS = ["none", "orbis", "prospero", "durango", "scarlett"]

# ---- "Texture import settings" blob, version 4 (engine reader 180455d80, writer 180455a00) ----
TEX_USAGE = {"albedo": 0, "albedo_hq": 1, "normalmap": 2, "specularmap": 3, "hdr": 4, "heightmap": 5}
_TIS = [("no_mips", "B"), ("dont_compress", "B"), ("b6", "B"), ("b7", "B"), ("normalize_luminance", "B"), ("b10", "B"),
        ("u12", "5I"), ("block32", "64s"), ("u96", "I"), ("b8", "B"), ("resize_width", "I"), ("resize_height", "I"),
        ("b11", "B")]
def parse_tex_import_settings(blob):
    s, o = tpac._str(blob, 0); d = {"usage": s.decode()}
    for k, f in _TIS:
        v = struct.unpack_from("<" + f, blob, o); o += struct.calcsize("<" + f)
        d[k] = v if len(v) > 1 else v[0]
    if o != len(blob): raise ValueError("import settings: %d bytes left" % (len(blob) - o))
    return d

def pack_tex_import_settings(d):
    out = tpac._S(d["usage"])
    for k, f in _TIS:
        v = d[k]; out += struct.pack("<" + f, *(v if isinstance(v, tuple) else (v,)))
    return out

# ---- "Fbx import settings" blob, version 4 (engine reader 1804231e0 + 180422ad0, names from its QSettings keys) ----
FBX_BLEND_SHAPES = ["as_vertex_anim", "as_morph_anim", "as_separate_meshes", "ignore"]
FBX_UNITS = ["none", "mm", "dm", "cm", "m", "km", "Inch", "Foot", "Mile", "Yard"]
FBX_NORMALS = ["default", "weighted"]
_FBX_FLAGS = ["import_meshes", "import_skeletons", "import_skeletal_animations", "import_morph_animations",
              "import_physics_shapes", "order_polygons_by_2nd_uv"]
def parse_fbx_import_settings(blob):
    d = {}; s, o = tpac._str(blob, 0); d["blend_shapes_import_operation"] = s.decode()
    d["convert_to_z_up"], d["remove_shape_type_names"] = blob[o], blob[o + 1]; o += 2
    s, o = tpac._str(blob, o); d["convert_to_unit"] = s.decode()
    d["tail_version"] = struct.unpack_from("<I", blob, o)[0]; o += 4
    for i, k in enumerate(_FBX_FLAGS): d[k] = blob[o + i]
    o += 6
    n = struct.unpack_from("<i", blob, o)[0]; o += 4; d["meshes"] = []
    for _ in range(n):
        s, o = tpac._str(blob, o); m = {"name": s.decode(), "b": bytes(blob[o:o + 6])}; o += 6
        s, o = tpac._str(blob, o); m["normals"] = s.decode()
        m["u"] = struct.unpack_from("<4I", blob, o); o += 16; d["meshes"].append(m)
    n = struct.unpack_from("<i", blob, o)[0]; o += 4; d["takes"] = []
    for _ in range(n):
        s, o = tpac._str(blob, o); d["takes"].append((s.decode(), blob[o])); o += 1
    if o != len(blob): raise ValueError("fbx settings: %d bytes left" % (len(blob) - o))
    return d

def pack_fbx_import_settings(d):
    out = tpac._S(d["blend_shapes_import_operation"]) + bytes([d["convert_to_z_up"], d["remove_shape_type_names"]]) \
        + tpac._S(d["convert_to_unit"]) + struct.pack("<I", d["tail_version"]) + bytes(d[k] for k in _FBX_FLAGS) \
        + struct.pack("<i", len(d["meshes"]))
    for m in d["meshes"]: out += tpac._S(m["name"]) + m["b"] + tpac._S(m["normals"]) + struct.pack("<4I", *m["u"])
    out += struct.pack("<i", len(d["takes"]))
    for name, flag in d["takes"]: out += tpac._S(name) + bytes([flag])
    return out

# ---- package walker (engine tpac_read_package 1800718e0) ----
def walk_package(b):
    """Items of a .tpac: type, guid, flag, name, record (with its u64 size), record hash, data entries, dependencies."""
    if b[:4] != b"TPAC": raise ValueError("not a package")
    ver, = struct.unpack_from("<I", b, 4); n, meta = struct.unpack_from("<II", b, 0x18); o = 0x24; out = []
    for _ in range(n):
        it = {"type": b[o:o + 16], "guid": b[o + 16:o + 32]}; o += 32
        if ver > 1: it["flag"] = struct.unpack_from("<I", b, o)[0]; o += 4
        s, o = tpac._str(b, o); it["name"] = s.decode("latin-1")
        L = struct.unpack_from("<Q", b, o)[0]; it["record"] = b[o:o + 8 + L]; o += 8 + L
        it["hash"] = b[o:o + 8]; o += 8
        k = struct.unpack_from("<I", b, o)[0]; o += 4; it["entries"] = []
        for _ in range(k):
            off, raw, st = struct.unpack_from("<QQQ", b, o)
            e = {"off": off, "raw": raw, "stored": st, "owner": b[o + 24:o + 40], "type": b[o + 40:o + 56],
                 "hash": b[o + 56:o + 64], "version": struct.unpack_from("<I", b, o + 64)[0], "flag": b[o + 68]}
            e["blob"] = lambda e=e: tpac.lz4_decompress(b[e["off"]:e["off"] + e["stored"]], e["raw"]) \
                if e["stored"] < e["raw"] else bytes(b[e["off"]:e["off"] + e["stored"]])
            it["entries"].append(e); o += 69
        k = struct.unpack_from("<I", b, o)[0]; o += 4; it["deps"] = [b[o + 48 * i:o + 48 * i + 48] for i in range(k)]; o += 48 * k
        out.append(it)
    return out

# ---- RDC (engine rdc_write_entry 180479730) ----
def rdc_sort_key(owner, data_id, type_guid): return bytes(owner) + bytes(data_id) + bytes(type_guid)

def pack_rdc_exact(entries, lz4=None):
    """entries = [(owner, data id, type guid, raw blob, [u64 hashes as 8-byte values], compress)]. Like the engine: entries
    sorted by (owner, id, type) bytes, u32 = the data type's version, u8 = 1 only when the LZ4 copy is stored (the
    engine keeps the raw blob when LZ4 does not shrink it), up to 8 hashes in the 64-byte block."""
    lz4 = lz4 or tpac.lz4_compress
    entries = sorted(entries, key=lambda e: rdc_sort_key(e[0], e[1], e[2]))
    data_at = 0x14 + 145 * len(entries); table = b""; data = b""
    for owner, did, ty, blob, hashes, comp in entries:
        st = lz4(blob) if comp else blob
        packed = comp and len(st) < len(blob)
        if not packed: st = blob
        hb = b"".join(hashes).ljust(64, b"\0")
        table += owner + did + ty + struct.pack("<QQQI", data_at + len(data), len(blob), len(st), type_version(ty)) + hb \
            + b"\xfa" * 4 + bytes([1 if packed else 0])
        data += st
    return b"RDC0" + struct.pack("<IIQ", 0, len(entries), 145 * len(entries)) + table + data

# ---- clip cache "Optimized animation" (engine optanim_serialize 180b9e300) ----
def _bits_bytes(bits, round_to): return ((bits - 1) // round_to + 1) * round_to // 8 if bits > 0 else 0

def optanim_layout(v):
    """Walk an Optimized animation blob with the engine's exact sizes. Returns header fields, per-bone channels and
    the trailer, and the size_in_bytes the engine would write."""
    q = 0; u = lambda f: struct.unpack_from(f, v, q)
    fmt, flags, last_key, end_key, bones = u("<5I"); q += 20
    size = 0x60; raw_keys = 0; chans = []
    def chan(per_key_extra):
        nonlocal q
        n = struct.unpack_from("<H", v, q)[0]; q += 2
        if not n: return (0, 0, 0, 0)
        bits, tb = v[q], v[q + 1]; q += 10
        D = _bits_bytes(((bits + per_key_extra) * 3 + tb) * n, 64) + 4; q += D
        return (n, bits, tb, D)
    for _ in range(bones):
        for k in range(3):
            n = struct.unpack_from("<I", v, q)[0]; q += 4 + 20 * n; raw_keys += n
            if k == 0: c = chan(1); chans.append(c); size += c[3]
    root = chan(0); size += root[3]
    start, frames = struct.unpack_from("<II", v, q); nb, ib = v[q + 8], v[q + 9]; q += 10
    T = _bits_bytes(nb * ib * frames, 32); q += T + 2
    size += T + 0x2a + 0x4a * bones + 20 * raw_keys
    trailer = struct.unpack_from("<I", v, q)[0]; q += 4
    return {"format": fmt, "flags": flags, "last_key": last_key, "end_key": end_key, "bones": bones, "channels": chans,
            "root": root, "start": start, "frames": frames, "index_bits": ib, "trailer": trailer, "size_in_bytes": size,
            "consumed": q, "length": len(v), "raw_keys": raw_keys}

def optanim_size_in_bytes(v): return optanim_layout(v)["size_in_bytes"]

# ---- tolerance the editor uses for clip caches (skeleton_bone_error_angle 1808c5640) ----
def bone_error_angle(reach, family_bones):
    """Angle (rad) whose chord at radius `reach` (bone length + child chain) is 1 cm / family_bones; key reduction uses
    0.8 of it, quantisation 0.2 of it."""
    import math
    d = 0.01 / family_bones
    if reach <= 1.1754943508222875e-38: return math.pi / 2
    if 2 * reach <= d: d = reach
    c = (2 * reach * reach - d * d) / (2 * reach * reach)
    return min(max(math.acos(max(-1.0, min(1.0, c))), 1.1920928955078125e-07), math.pi / 2)

# ---- skeleton resource ----
SKELETON_TYPE = _g("d5a335c6bbeadd45883eaa57e4196113")
SKELETON_DEF = _g("377dd01120e76b40ab67c846f96a8771")    # "Skeleton definition", version 0
SKELETON_USER = _g("6dc06a9b46a5af40a55540d301ab4b2f")   # "User data", version 3 (physics, ragdoll, body parts)
DATA_TYPES.update({SKELETON_DEF: ("Skeleton definition", 0), SKELETON_USER: ("User data", 3)})
BIPED_BONE_TYPES = ["biped_" + n for n in ("abdomen thigh_l calf_l foot_l toe_l thigh_r calf_r foot_r toe_r spine_1 "
    "spine_2 thorax neck head shoulder_l upperarm_l upperarm_twist1_l forearm_l forearm1_l hand_l item_l shoulder_r "
    "upperarm_r upperarm_twist1_r forearm_r forearm1_r hand_r item_r").split()]
BODY_PARTS = {"none": 0xff, "head": 0, "neck": 1, "chest": 2, "abdomen": 3, "shoulder_left": 4, "shoulder_right": 5,
              "arm_left": 6, "arm_right": 7, "legs": 8, "bipedal_arm_left": 6, "bipedal_arm_right": 7, "bipedal_legs": 8,
              "quadrupedal_arm_left": 6, "quadrupedal_arm_right": 7, "quadrupedal_legs": 8}

def parse_skeleton_definition(d):
    """-> (name, [(bone name, parent, 16 floats: x axis, y axis, z axis, origin as vec4 rows, local to parent)])"""
    s, o = tpac._str(d, 0); n = struct.unpack_from("<i", d, o)[0]; o += 4; bones = []
    for _ in range(n):
        nm, o = tpac._str(d, o); par = struct.unpack_from("<i", d, o)[0]; o += 4
        bones.append((nm.decode(), par, struct.unpack_from("<16f", d, o))); o += 64
    if o != len(d): raise ValueError("skeleton definition: %d bytes left" % (len(d) - o))
    return s.decode(), bones

def pack_skeleton_definition(name, bones):
    out = tpac._S(name) + struct.pack("<i", len(bones))
    for nm, par, m in bones: out += tpac._S(nm) + struct.pack("<i", par) + struct.pack("<16f", *m)
    return out

def parse_skeleton_user_data(d):
    """Head and per-bone part of the "User data" blob; the joint list is kept raw ("joints_raw")."""
    o = 0; u = {}
    u["f0"], = struct.unpack_from("<f", d, o); o += 4
    u["v1"] = struct.unpack_from("<4f", d, o); o += 16; u["v2"] = struct.unpack_from("<4f", d, o); o += 16
    s, o = tpac._str(d, o); u["body_type"] = s.decode(); s, o = tpac._str(d, o); u["s2"] = s.decode()
    u["v3"] = d[o:o + 16]; o += 16
    n = struct.unpack_from("<i", d, o)[0]; o += 4; u["bones"] = []
    for _ in range(n):
        b = {}; s, o = tpac._str(d, o); b["name"] = s.decode(); b["flag"] = d[o]; o += 1
        s, o = tpac._str(d, o); b["bone_type"] = s.decode(); s, o = tpac._str(d, o); b["body_part"] = s.decode()
        b["mass"], = struct.unpack_from("<f", d, o); o += 4
        b["ragdoll_capsule"] = struct.unpack_from("<4f4ff", d, o); o += 36
        b["collision_capsule"] = struct.unpack_from("<4f4ff", d, o); o += 36
        b["extra"], = struct.unpack_from("<f", d, o); o += 4; u["bones"].append(b)
    u["joints_raw"] = d[o:]
    return u

def pack_skeleton_user_data(u):
    out = struct.pack("<f", u["f0"]) + struct.pack("<4f", *u["v1"]) + struct.pack("<4f", *u["v2"])         + tpac._S(u["body_type"]) + tpac._S(u["s2"]) + u["v3"] + struct.pack("<i", len(u["bones"]))
    for b in u["bones"]:
        out += tpac._S(b["name"]) + bytes([b["flag"]]) + tpac._S(b["bone_type"]) + tpac._S(b["body_part"])             + struct.pack("<f", b["mass"]) + struct.pack("<4f4ff", *b["ragdoll_capsule"]) + struct.pack("<4f4ff", *b["collision_capsule"])             + struct.pack("<f", b["extra"])
    return out + u["joints_raw"]

# ---- metamesh record (engine metamesh_md_write 1804337b0 / submesh_md_write 180435030) ----
META_TYPE = _g("978b8fa07c19ea4bb95b53846cae834e")
EDIT_DATA = _g("5f98413dd224c14f82e46a6e0da3f4e2")
VERTEX_STREAM = _g("97f81dbb4f587047abf2663fe449f247")

def _flags(b, o):
    z, n = struct.unpack_from("<II", b, o); o += 8; out = []
    for _ in range(n):
        s, o = tpac._str(b, o); out.append(s.decode())
    return out, o

def parse_metamesh_record(rec):
    """Fields of a metamesh record (with its u64 size). Submeshes: guid, name, flags, material guid, factors, counts,
    bbox, radius, bone count, raw tail parameters."""
    L = struct.unpack_from("<Q", rec, 0)[0]; o = 8; m = {}
    m["version"], = struct.unpack_from("<I", rec, o); o += 4
    m["source"] = rec[o:o + 16]; o += 16
    m["f0"], = struct.unpack_from("<f", rec, o); o += 4
    s, o = tpac._str(rec, o); m["s0"] = s.decode()
    m["cloth_mesh"] = rec[o:o + 16]; o += 16
    m["flags"], o = _flags(rec, o)
    n = struct.unpack_from("<I", rec, o)[0]; o += 4; m["submeshes"] = []
    for _ in range(n):
        sm = {"pre": rec[o:o + 25], "lod": struct.unpack_from("<I", rec, o + 1)[0]}; o += 25
        sm["version"], = struct.unpack_from("<I", rec, o); o += 4
        sm["guid"] = rec[o:o + 16]; o += 16
        s, o = tpac._str(rec, o); sm["name"] = s.decode()
        sm["flags"], o = _flags(rec, o)
        sm["material"] = rec[o:o + 16]; sm["material_off"] = o; o += 16
        sm["factor"] = struct.unpack_from("<4f", rec, o); sm["factor2"] = struct.unpack_from("<4f", rec, o + 16); o += 32
        sm["u9"] = struct.unpack_from("<9I", rec, o); o += 36
        sm["positions"], sm["faces"], sm["vertices"], sm["weighted"], _ = struct.unpack_from("<5I", rec, o); o += 20
        sm["bbox_min"] = struct.unpack_from("<4f", rec, o); sm["bbox_max"] = struct.unpack_from("<4f", rec, o + 16)
        sm["centre"] = struct.unpack_from("<4f", rec, o + 32); o += 48
        sm["radius"], sm["bones"] = struct.unpack_from("<fI", rec, o); o += 8
        k = struct.unpack_from("<I", rec, o)[0]; o += 4; sm["strings"] = []
        for _ in range(k):
            s, o = tpac._str(rec, o); sm["strings"].append(s.decode())
        t0 = o; o += 4; s, o = tpac._str(rec, o); o += 4 * 10 + 2 + 8 + 1
        sm["params"] = rec[t0:o]; m["submeshes"].append(sm)
    m["tail16"] = rec[o:o + 16]; o += 16
    k = struct.unpack_from("<I", rec, o)[0]; o += 4; m["variants"] = [rec[o + 16 * i:o + 16 * i + 16] for i in range(k)]; o += 16 * k
    m["b0"], m["b1"] = rec[o], rec[o + 1]; o += 2
    if o != 8 + L: raise ValueError("metamesh record: parsed %d of %d bytes" % (o - 8, L))
    return m

def read_package_index(path):
    """Items of a (possibly huge) .tpac without reading the blobs: reads the metadata block only."""
    with open(path, "rb") as f:
        h = f.read(0x24); n, meta = struct.unpack_from("<II", h, 0x18); b = h + f.read(meta)
    ver = struct.unpack_from("<I", b, 4)[0]; o = 0x24; out = []
    for _ in range(n):
        it = {"type": b[o:o + 16], "guid": b[o + 16:o + 32]}; o += 32
        if ver > 1: it["flag"] = struct.unpack_from("<I", b, o)[0]; o += 4
        s, o = tpac._str(b, o); it["name"] = s.decode("latin-1")
        L = struct.unpack_from("<Q", b, o)[0]; it["record"] = b[o:o + 8 + L]; o += 16 + L
        k = struct.unpack_from("<I", b, o)[0]; o += 4; it["entries"] = []
        for _ in range(k):
            off, raw, st = struct.unpack_from("<QQQ", b, o)
            it["entries"].append({"off": off, "raw": raw, "stored": st, "owner": b[o + 24:o + 40], "type": b[o + 40:o + 56],
                                  "hash": b[o + 56:o + 64], "version": struct.unpack_from("<I", b, o + 64)[0],
                                  "flag": b[o + 68]}); o += 69
        k = struct.unpack_from("<I", b, o)[0]; o += 4 + 48 * k
        out.append(it)
    return out

def _read_blob(f, e):
    f.seek(e["off"]); d = f.read(e["stored"])
    return tpac.lz4_decompress(d, e["raw"]) if e["stored"] < e["raw"] else d

def find_packed_metamesh(name):
    """(package path, item) of a metamesh in any Modules/*/AssetPackages/*.tpac (first hit, Native first)."""
    root = os.path.dirname(tpac.NATIVE)
    pk = sorted(glob.glob(os.path.join(root, "*", "AssetPackages", "*.tpac")), key=lambda p: "Native" not in p)
    for p in pk:
        for it in read_package_index(p):
            if it["type"] == META_TYPE and it["name"] == name: return p, it
    raise KeyError(name)

def read_packed_mesh(name, package=None, lod0_only=True, edit=False):
    """A metamesh from a packed AssetPackage. Packed packages store per submesh a "Mesh edit data" and a "Mesh vertex
    stream" entry inline (owner = submesh guid, LZ4 block, version 1), the stream in the same layout as a module .rdc
    (sdk_mesh.stream_blob). Returns {"name", "package", "record": parse_metamesh_record(...), "submeshes": [{name,
    guid, material, tris (n,3), pos (v,3), uv0 (v,2, v un-flipped), normal (v,3), streams (14 raw), edit}]}."""
    import numpy as np, sdk_mesh
    if package:
        it = next(i for i in read_package_index(package) if i["type"] == META_TYPE and i["name"] == name)
    else:
        package, it = find_packed_metamesh(name)
    m = parse_metamesh_record(it["record"]); out = {"name": name, "package": package, "record": m, "submeshes": []}
    ents = {(e["owner"], e["type"]): e for e in it["entries"]}
    with open(package, "rb") as f:
        for sm in m["submeshes"]:
            if lod0_only and ".lod" in sm["name"]: continue
            e = ents.get((sm["guid"], VERTEX_STREAM))
            if e is None: raise FileNotFoundError("no inline vertex stream for %s (module packages keep it in the .rdc)" % sm["name"])
            tris, S = sdk_mesh.parse_stream(_read_blob(f, e))
            r = {"name": sm["name"], "guid": sm["guid"], "material": sm["material"], "tris": tris, "streams": S,
                 "pos": np.frombuffer(S[4], "<f4").reshape(-1, 3), "normal": np.frombuffer(S[6], "<f4").reshape(-1, 3)}
            uv = np.frombuffer(S[2], "<f4").reshape(-1, 2).copy(); uv[:, 1] = 1 - uv[:, 1]; r["uv0"] = uv
            if edit and (sm["guid"], EDIT_DATA) in ents: r["edit"] = sdk_mesh.parse_edit(_read_blob(f, ents[(sm["guid"], EDIT_DATA)]))
            out["submeshes"].append(r)
    return out

def pack_items(package_guid, items):
    """A package from items [(type, guid, flag, name, record with its u64 size, [(data type, raw blob, owner)])], sorted
    by guid bytes like the editor; blobs LZ4 packed when that helps; entry u32 = data type version."""
    items = sorted(items, key=lambda r: r[1])
    meta = 0x24 + sum(36 + 4 + len(n.encode()) + len(rec) + 8 + 4 + 69 * len(ents) + 4 for _, _, _, n, rec, ents in items)
    head = b"TPAC" + struct.pack("<I", 2) + package_guid + struct.pack("<II", len(items), meta - 0x24) + bytes(4)
    body = b""; data = []; pos = meta
    for ty, g, fl, name, rec, ents in items:
        body += ty + g + struct.pack("<I", fl) + tpac._S(name) + rec + struct.pack("<Q", tpac.xxh64(rec)) + struct.pack("<I", len(ents))
        for dt, blob, owner in ents:
            c = tpac.lz4_compress(blob); c = c if len(c) < len(blob) else blob
            body += struct.pack("<QQQ", pos, len(blob), len(c)) + owner + dt + struct.pack("<Q", tpac.xxh64(blob))                 + struct.pack("<IB", type_version(dt), 1)
            data.append(c); pos += len(c)
        body += bytes(4)
    return head + body + b"".join(data)

def pack_items_stored(package_guid, items):
    """Like pack_items, but the data entries are copied as stored (already LZ4 packed or raw) with their own raw size,
    hash, version and flag: [(type, guid, flag, name, record, [(data type, owner, raw size, stored bytes, hash, version,
    entry flag)])]. No recompression, so a 200 MB Native metamesh is copied in seconds."""
    items = sorted(items, key=lambda r: r[1])
    meta = 0x24 + sum(36 + 4 + len(n.encode()) + len(rec) + 8 + 4 + 69 * len(ents) + 4 for _, _, _, n, rec, ents in items)
    head = b"TPAC" + struct.pack("<I", 2) + package_guid + struct.pack("<II", len(items), meta - 0x24) + bytes(4)
    body = b""; data = []; pos = meta
    for ty, g, fl, name, rec, ents in items:
        body += ty + g + struct.pack("<I", fl) + tpac._S(name) + rec + struct.pack("<Q", tpac.xxh64(rec)) + struct.pack("<I", len(ents))
        for dt, owner, raw, stored, h, ver, ef in ents:
            body += struct.pack("<QQQ", pos, raw, len(stored)) + owner + dt + h + struct.pack("<IB", ver, ef)
            data.append(stored); pos += len(stored)
        body += bytes(4)
    return head + body + b"".join(data)

def material_guid(name, extra_dirs=()):
    """Resource guid of a module material <name>_mtl.tpac (staged dirs first, then the installed Assets folder)."""
    for d in list(extra_dirs) + [tpac.ASSETS]:
        p = os.path.join(d, name + "_mtl.tpac")
        if os.path.exists(p): return tpac.read_mtl_file(p)["resource"]
    raise KeyError("material " + name)

def write_override_metamesh(name, materials, out_dir, mtl_dirs=(), keep=None, found=None, native_names=None, stored=False):
    """A module package that overrides the Native metamesh <name> BY NAME (new item guid; a module item reusing the
    Native guid is dropped by the engine) with the same geometry, LODs and submesh guids but other materials.
    materials: {native material name or submesh name: module material name}; unmapped submeshes keep the Native
    material guid. Like Native packed packages it carries the edit data and the vertex streams inline, so no .rdc is
    needed (the loader reads package entries first). Returns the written path.
    found = (package, item) and native_names = {material guid: name} skip the package scans (batch use);
    stored=True copies the data entries as stored (no LZ4 round trip)."""
    package, it = found or find_packed_metamesh(name)
    m = parse_metamesh_record(it["record"]); rec = bytearray(it["record"])
    want = {sm["material"] for sm in m["submeshes"]}
    if native_names is None:
        native_names = {}
        for p in sorted(glob.glob(os.path.join(os.path.dirname(tpac.NATIVE), "*", "AssetPackages", "*.tpac"))):
            for i2 in read_package_index(p):
                if i2["type"] == tpac.MTL_TYPE and i2["guid"] in want: native_names[i2["guid"]] = i2["name"]
    report = []
    for sm in m["submeshes"]:
        nat = native_names.get(sm["material"], "?"); new = materials.get(sm["name"], materials.get(nat))
        if new:
            g = material_guid(new, mtl_dirs); rec[sm["material_off"]:sm["material_off"] + 16] = g
        report.append((sm["name"], nat, new))
    import uuid as _u
    old = os.path.join(out_dir, name + "_geo.tpac")
    if os.path.exists(old):   # a rewrite keeps the package and item ids (and so any cache names)
        with open(old, "rb") as f: pkg = f.read(24)[8:24]
        g = read_package_index(old)[0]["guid"]
    else: pkg, g = _u.uuid4().bytes, _u.uuid4().bytes
    with open(package, "rb") as f:
        if stored:
            ents = []
            for e in it["entries"]:
                if keep and e["type"] not in keep: continue
                f.seek(e["off"]); ents.append((e["type"], e["owner"], e["raw"], f.read(e["stored"]), e["hash"], e["version"], e["flag"]))
        else:
            ents = [(e["type"], _read_blob(f, e), e["owner"]) for e in it["entries"]]
            if keep: ents = [e for e in ents if e[0] in keep]
    if stored: data = pack_items_stored(pkg, [(META_TYPE, g, it.get("flag", 1), name, bytes(rec), ents)])
    else: data = pack_items(pkg, [(META_TYPE, g, it.get("flag", 1), name, bytes(rec), ents)])
    os.makedirs(out_dir, exist_ok=True); open(old, "wb").write(data)
    return old, report

def packed_mesh_to_obj(mesh, path):
    """Write read_packed_mesh output as OBJ (one group per submesh, z up as in the engine)."""
    lines = ["# %s from %s" % (mesh["name"], os.path.basename(mesh["package"]))]; base = 1
    for sm in mesh["submeshes"]:
        lines.append("g " + sm["name"])
        lines += ["v %.6f %.6f %.6f" % tuple(p) for p in sm["pos"]]
        lines += ["vt %.6f %.6f" % tuple(t) for t in sm["uv0"]]
        lines += ["vn %.6f %.6f %.6f" % tuple(n) for n in sm["normal"]]
        for a, b, c in sm["tris"]:
            a += base; b += base; c += base
            lines.append("f %d/%d/%d %d/%d/%d %d/%d/%d" % (a, a, a, b, b, b, c, c, c))
        base += len(sm["pos"])
    open(path, "w").write("\n".join(lines) + "\n")

def packed_obj_main(name, out):
    import numpy as np
    m = read_packed_mesh(name); packed_mesh_to_obj(m, out)
    P = np.concatenate([s["pos"] for s in m["submeshes"]]); rb = [s for s in m["record"]["submeshes"] if ".lod" not in s["name"]]
    lo = np.min([s["bbox_min"][:3] for s in rb], 0); hi = np.max([s["bbox_max"][:3] for s in rb], 0)
    print("%s: %d submeshes, %d vertices, %d triangles, from %s -> %s" % (name, len(m["submeshes"]), len(P),
          sum(len(s["tris"]) for s in m["submeshes"]), os.path.basename(m["package"]), out))
    print("  vertices     min %s max %s" % (np.round(P.min(0), 3), np.round(P.max(0), 3)))
    print("  record bbox  min %s max %s" % (np.round(lo, 3), np.round(hi, 3)))
    return m

# ---- self test on installed files ----
def selftest():
    ok = True
    def report(name, good, bad, extra=""):
        nonlocal ok; ok &= not bad
        print("%-46s %4d ok %4d bad %s" % (name, good, bad, extra))
    rdc_dir = tpac.RDC_DIR; A = tpac.ASSETS
    rdcs = {}
    for p in glob.glob(os.path.join(rdc_dir, "*.rdc")): rdcs[os.path.basename(p)[:-4].upper()] = p
    # textures: pixel hash, import settings round trip
    g = b_ = sg = sb = 0; bad_ex = []
    for p in sorted(glob.glob(os.path.join(A, "*_tex.tpac"))):
        b = open(p, "rb").read()
        if len(b) < 0x60: continue
        items = walk_package(b)
        for it in items:
            for e in it["entries"]:
                if e["type"] == _g("e25b477c8d7c1d43b0e153218d047fb9"):
                    blob = e["blob"]()
                    if pack_tex_import_settings(parse_tex_import_settings(blob)) == blob: sg += 1
                    else: sb += 1
        r, E = tpac.parse_tex_record(b, 0x4c + struct.unpack_from("<i", b, 0x48)[0])
        rp = rdcs.get(str(uuid.UUID(bytes_le=b[8:24])).upper())
        if not rp: continue
        for e in tpac.read_rdc(rp):
            if e["type"] == tpac.TEX_PIXELS:
                pix = e["blob"]
                if texture_pixel_hash(pix) == r["unk8"]: g += 1
                else: b_ += 1; bad_ex.append(os.path.basename(p))
    report("texture pixel hash (xxh64 seed 0x41c64e6d)", g, b_, " ".join(bad_ex[:5]))
    report("texture import settings parse/pack", sg, sb)
    # fbx import settings
    g = b_ = 0
    for p in sorted(glob.glob(os.path.join(A, "*_geo.tpac"))):
        for it in walk_package(open(p, "rb").read()):
            for e in it["entries"]:
                if e["type"] == _g("f83d7de95742db409f421436e339d581"):
                    blob = e["blob"]()
                    try: good = pack_fbx_import_settings(parse_fbx_import_settings(blob)) == blob
                    except Exception: good = False
                    g += good; b_ += not good
    report("fbx import settings parse/pack", g, b_)
    # rdc files: order, version, flag; clip caches: trailer
    g = b_ = cg = cb = 0; ex = []; rex = []
    for p in sorted(rdcs.values()):
        es = tpac.read_rdc(p); keys = [rdc_sort_key(e["owner"], e["id"], e["type"]) for e in es]
        raw = open(p, "rb").read()
        good = keys == sorted(keys)
        for k, e in enumerate(es):
            o = 0x14 + 145 * k
            good &= struct.unpack_from("<I", raw, o + 72)[0] == type_version(e["type"])
            good &= raw[o + 144] == (1 if e["stored"] < e["raw"] else 0)
            if e["type"] == _g("6f131e6cb7d0ff41bb7a275f3630db25"):
                v = tpac.lz4_decompress(e["blob"], e["raw"]) if e["stored"] < e["raw"] else e["blob"]
                L = optanim_layout(v)
                if L["trailer"] == L["size_in_bytes"] and L["consumed"] == L["length"]: cg += 1
                else: cb += 1; ex.append(os.path.basename(p))
        g += good; b_ += not good
        if not good: rex.append(os.path.basename(p))
    report("rdc entry order, type version, lz4 flag", g, b_, " ".join(rex[:5]))
    report("clip cache size_in_bytes trailer", cg, cb, " ".join(ex[:5]))
    # skeletons: Native editor packages round trip
    g = b_ = 0
    nat = os.path.join(tpac.NATIVE, "EmAssetPackages")
    for pk in ("human/human.tpac", "cat/cat.tpac", "cow/cow.tpac", "Dog/Dog.tpac"):
        p = os.path.join(nat, pk)
        if not os.path.exists(p): continue
        for it in walk_package(open(p, "rb").read()):
            if it["type"] != SKELETON_TYPE: continue
            for e in it["entries"]:
                blob = e["blob"]()
                if e["type"] == SKELETON_DEF: good = pack_skeleton_definition(*parse_skeleton_definition(blob)) == blob
                elif e["type"] == SKELETON_USER: good = pack_skeleton_user_data(parse_skeleton_user_data(blob)) == blob
                else: continue
                g += good; b_ += not good
    report("Native skeleton definition/user data round trip", g, b_)
    return ok

def main(a):
    if not a or a[0] == "selftest": sys.exit(0 if selftest() else 1)
    if a[0] == "packedobj": packed_obj_main(a[1], a[2]); return
    if a[0] == "texhash":
        p = a[1]; r, pix = tpac.tex_pixels(p); h = texture_pixel_hash(pix)
        print("stored %s  engine rule %s  %s" % (r["unk8"].hex(), h.hex(), "ok" if h == r["unk8"] else "DIFFERENT"))
        if "--fix" in a and h != r["unk8"]:
            b = bytearray(open(p, "rb").read()); R = 0x4c + struct.unpack_from("<i", b, 0x48)[0]
            r2, E = tpac.parse_tex_record(b, R); r2["unk8"] = h; rec = tpac.pack_tex_record(r2)
            if len(rec) != E - R: sys.exit("record size changed")
            b[R:E] = rec; b[E:E + 8] = struct.pack("<Q", tpac.xxh64(rec)); open(p, "wb").write(b); print("fixed", p)
        return
    sys.exit(__doc__ or "usage: tw_formats.py selftest | texhash <file> [--fix]")

if __name__ == "__main__": main(sys.argv[1:])
