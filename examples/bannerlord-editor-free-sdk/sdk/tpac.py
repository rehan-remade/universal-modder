# Command-line .tpac toolkit: write Bannerlord asset packages (.tpac) and runtime caches (.rdc) without the Modding Kit editor.
# Layouts were mapped against files the editor wrote and Native's own packages; see
# knowledge/techniques/editor-free-bannerlord-assets.md in the universal-modder repo.
# Paths come from config.py (BANNERLORD_DIR, BANNERLORD_MODULE_DIR, MODULE_ASSET_SUB); --out stages elsewhere.
#   python tpac.py anims <file_anims_geo.tpac>                 list skeleton animations (name, guid, owner)
#   python tpac.py owner <file_anims_geo.tpac> [...] [--skeleton <guid hex>]
#                                                              set Owner Skeleton on every animation (default human_skeleton)
#   python tpac.py clip <name> <anim name> <frames> [fps] [--out DIR] [--template <clip.tpac>]
#                                                              write <name>_anm.tpac (clip on that animation; the record is
#                                                              a plain Native clip record unless --template is given)
#   python tpac.py material <name> --shader <guid|name> --diffuse <tex> [--specular <tex>] [--normal <tex>]
#                   [--blend <mode>] [--flags a,b] [--static|--skinned] [--alpha-ref f] [--force] [--template <mtl.tpac>]
#                                                              write <name>_mtl.tpac (see the material layout below)
#                   [--out DIR]                               --out: stage elsewhere (textures looked up there first)
#   python tpac.py mtl <file_mtl.tpac>                        print a material file's fields
#   python tpac.py retex <material> --diffuse <tex> [--normal <tex>] [--specular <tex>] (--out DIR | --force)
#                                                             an installed material with only its texture slots changed
#   python tpac.py texture <png> [--name N] [--format bc1|bc3|bc4|bc5|bc7|rgba8] [--usage albedo|normalmap|specularmap|
#                   heightmap | --srgb | --linear] [--no-mips] [--flags a,b] [--out DIR] [--rdc DIR] [--inline] [--force]
#                                                             write <name>_tex.tpac + RuntimeDataCache/<package>.rdc
#                                                             (texture layout below); defaults by suffix: _d albedo bc1
#                                                             (bc3 if the PNG has alpha), _n bc5, _s bc1, _h bc4
#   python tpac.py anim <fbx> [...] [--out DIR] [--force]      FBX single take -> <fbx name>_geo.tpac (no editor import)
#   python tpac.py clip-cache <clip glob> [--clips DIR] [--rdc DIR] [--dry]
#                                                             build clips' RuntimeDataCache .rdc (no editor load needed)
#   TPAC_STAGE=<dir>[;<dir>]                                  staged package folders also searched for animations
#   python tpac.py optanim <file_anm.tpac> [--rdc DIR]        print a clip cache's channels
#   python tpac.py tex <file_tex.tpac> [out.png] [--mip k] [--compare <other_tex.tpac>]
#                                                             print fields, check hashes, decode a mip, diff two textures
#   write_material_record(name, record)                       library: write a parsed record as is (Native-name overrides)
#
# Package file (one resource): "TPAC", u32 2, package guid, u32 count 1, u32 payload length (metadata size - 0x24), u32 0,
# then per resource: type guid, resource guid, u32 0, name (u32 length + ascii), record, xxh64 of the record (8 bytes,
# seed 0, over the record from its length field on; checked on every editor and Native material), 8 zero bytes.
# Material record (type guid 9313b01d...0717, mapped on the editor's and Native's material records, all parse):
#   +0 u32 byte count from +8 to the record end, +4..+35 constant (u32 2 at +28), then
#   material flags list (u32 count + strings: two_sided, no_modify_depth_buffer, no_depth_test, ...), u32 0,
#   vertex layout list (skinning, bumpmap, doubleuv), alpha blend mode string (no_alpha_blend, modulate, add_alpha,
#   multiply, add, add_modulate_combined), shader resource guid (16), texture list (u32 count + per entry u32 slot
#   (0 diffuse, 2 normal, 4 specular) + texture resource guid), f32 alpha test reference (0.5 on banner icons),
#   shader flags list (alpha_test, use_specular, ...), 28 f32 parameters (copied from the template).
# The u32 0 after the record hash is the resource's data entry count, the last u32 0 a per-resource trailer. With data
# entries (u32 count, then 69 bytes each): u64 file offset, u64 raw size, u64 stored size (< raw: LZ4 block), owner
# resource guid, data type guid, xxh64 of the raw data, u32 type value (engine table: 4 import settings, else 0), u8 1.
# The blobs follow the metadata: the header's payload length covers only up to the trailer. Records patched without
# a new hash (tpac.py owner) loaded in the editor without warnings, so the record hash looks unenforced.
# Texture record (type cbcb74c9...c2e8; 166 editor-made textures parse and 161 rebuilt byte-identical, the other 5
# differed only in the LZ4 choice of one blob): +0 u32 length, u32 0, u32 3, 20 zero bytes, source path ("$BASE/" +
# path under the game folder), xxh64 of the source file bytes, 5 zero bytes, import flags list (dont_degrade,
# for_colorgrade, ...), u32 2, u8 2, u32 width, u32 height, u32 depth 1, u8 mips (full chain = bit length of the larger
# side), u16 faces 1 (6 on cubemaps), format string (DXT1, DXT5, BC4, BC5, BC7, R8G8B8A8_UNORM, BC6H_UF16, ...),
# u32 0, texture flags list (has_alpha, is_cubemap), platform string "none", 5 zero bytes, u64 pixel hash
# (xxh64 of all mips, seed 0x41c64e6d; the editor only needs it non-zero), two vec4 (x, y, z, 1; the editor leaves stack garbage in xyz).
# No sRGB field exists: the usage string below is the only colour space hint.
# Texture data entries: "Texture import settings" e25b477c... (usage string albedo/normalmap/specularmap/heightmap,
# then 104 bytes, 01 01 at the start for Do Not Compress + no mips), "Source file info" a781b98a... (u32 w, h, 1, 1, 1,
# source format string B8G8R8 / B8G8R8A8_UNORM / R8_UNORM, u64 source file size). The pixels ("Texture pixel data"
# 2c4eee70...) are not in the module package but in RuntimeDataCache/<package guid as text>.rdc (Native editor
# packages carry them inline instead). Mips largest first, each max(1,w/4)*max(1,h/4) blocks (8 bytes DXT1/BC4,
# 16 DXT5/BC5/BC7) or w*h*4 bytes RGBA (byte order R, G, B, A), no padding. Decoded editor textures match their PNGs
# (PSNR DXT1 median 46 dB, DXT5 53, BC4 54, BC5 44, RGBA8 exact).
# RDC file (engine rules, written by tw_formats.pack_rdc_exact): "RDC0", u32 0, u32 entry count, u64 145 * count, then
# 145-byte entries sorted by (owner, id, type) bytes: owner resource guid, data id (texture: the resource again; mesh:
# the submesh), data type guid, u64 offset, u64 raw, u64 stored, u32 = the data type's version (textures 0, mesh vertex
# stream 1, clips 2), 64-byte hash block (h1, h2, zeros), FA FA FA FA, u8 = 1 when the stored copy is LZ4; data follows.
# Texture h1 = the record's source hash, h2 = xxh64 of the import settings blob. Mesh h1 = xxh64 of the package's
# "Mesh edit data" blob, h2 = 0. The game looks entries up by (owner, id, type) only; the editor also checks hashes.
# Skeleton animation package (<fbx>_geo.tpac of an FBX import; no .rdc): resources in guid byte order, each type,
# guid, u32 flag, name, record, xxh64, entries, u32 0. Import source (7936ba3e, "<fbx>.fbx"): u32 0, u32 1, FBX path,
# xxh64 of the FBX, u32 n + n x (type, guid) produced, u32 0; data f83d7de9 (value 4): fixed settings head, u32 take
# count, per take name + 0 byte. Skeleton animation (07b0faba): u32 0, u32 1, import source guid, u8 0, owner skeleton
# guid, u32 bones, u32 keys, u32 0; data 6d817dd0: name, u32 bones, per bone rotation channel + empty position
# channel, root position channel, empty channel; channel = u32 0, u32 16, u32 n, n f32 times, n x 4 f32 (w,x,y,z;
# root x,y,z,0). Keys from the FBX (fully evaluated node transforms): see fbx_take(). 8 editor imports rebuild with identical metadata.
# Clip cache (type 6f131e6c "Optimized animation", compression 2 = LZ4, flag 1; owner = id = clip resource; h1 =
# xxh64 of the source animation's data blob, h2 = the clip record's hash slot as stored). All 103 editor clip caches
# re-pack byte-identical; tpac.py clip-cache rebuilds them with the same keys and header, rotations within 0.006.
#   u32 2, u32 1, u32 end key, u32 end key, u32 bones (28), u32 0, then per bone a rotation channel: u16 key count,
#   u8 bits, u8 time bits (bit length of the end key), f32 max, f32 min, then per key LSB-first: 3 bits (index of the
#   dropped largest component << 1 | negate-after-rebuild), three components at `bits` (min + q / (2^bits-1) *
#   (max-min), w,x,y,z order minus the dropped one, which is rebuilt positive), the key time (absolute source key);
#   padded to 8-byte words, then 16 zero bytes (12 after the last bone). Keys are reduced (first = start, last = end
#   key). Root channel (pelvis x, y, z): same header, per key three components then time, 8-byte words, 4 zero bytes.
#   Then u32 start key, u32 frame count, u8 bones, u8 index bits, a frames x bones table of key indices (last key at or
#   before start + frame), 2 zero bytes, padding to 4, u32 runtime size = blob size + 50 x bones + 90 (28 bones: + 1490).
import os, re, struct, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from config import ASSETS, RDC_DIR, MODULE, GAME, PACKED, NATIVE, NATIVE_MTLS
HUMAN_SKELETON = bytes.fromhex("86357fddea10d547880ea0c263862217")
ANIM_TYPE = bytes.fromhex("07b0faba3f7e3f45bac6e7640043112b")
KEYS_PER_SECOND = 12.548   # the editor resamples imported animations (measured: 56 frames at 30 fps -> keys 0..23)

def _metadata(path):
    """Header and metadata block of a package (the data blobs are not read)."""
    with open(path, "rb") as f:
        h = f.read(0x24)
        if h[:4] != b"TPAC": return b""
        return h + f.read(struct.unpack_from("<I", h, 0x1c)[0])

def anims(path):
    """Skeleton animations in an anims file: name -> (resource guid, owner offset, owner guid)."""
    b = _metadata(path); out = {}
    for m in re.finditer(re.escape(ANIM_TYPE) + rb"(.{16})(.{4})(.{4})", b, re.S):
        guid = m.group(1); n = struct.unpack("<i", m.group(3))[0]
        name = b[m.end():m.end() + n].decode("ascii", "replace")
        if not re.fullmatch(r"[A-Za-z0-9_.\-]{1,127}", name): continue
        o = re.search(re.escape(name.encode()) + rb"1\x00{7}\x01\x00{3}.{16}\x00(.{16})", b, re.S)
        out[name] = (guid, o.start(1) if o else None, o.group(1) if o else None)
    return out

_ANIM_INDEX = {}   # (dirs) -> {anim name: guid}; rebuilt once on a miss (a package may have been written since)

def find_anim(name):
    # one scan per process instead of re-reading every animation package for every clip (a build that writes thousands
    # of clips spent most of an hour here)
    dirs = tuple([x for x in os.environ.get("TPAC_STAGE", "").split(";") if x] + [ASSETS])   # staged packages first
    for attempt in (0, 1):
        idx = _ANIM_INDEX.get(dirs)
        if idx is None or attempt:
            idx = {}
            for d in reversed(dirs):   # earlier dirs win, as the old first-match search did
                if not os.path.isdir(d): continue
                for f in sorted(os.listdir(d), reverse=True):
                    if f.endswith("_geo.tpac"):   # the editor names an FBX import's package <fbx>_geo
                        idx.update({k: v[0] for k, v in anims(os.path.join(d, f)).items()})
            _ANIM_INDEX[dirs] = idx
        if name in idx: return idx[name]
    raise KeyError(name)

def set_owner(path, skeleton=HUMAN_SKELETON):
    """Set the Owner Skeleton of every animation in a package (an editor import leaves it empty). Returns the count."""
    b = bytearray(open(path, "rb").read()); n = 0
    for name, (guid, off, owner) in anims(path).items():
        if off is not None and owner != skeleton:
            b[off:off + 16] = skeleton; n += 1
    open(path, "wb").write(b)
    return n

# Movement clips need what Native's run_forward_1h has (without it the game crashes at the first spawn of an agent
# whose run action uses the clip): record size 0xc9, two phase values at +56, the "make_walk_sound" flag and the
# "bip_mov_ik" entry with its eight values (copied).
MOVE_PHASES = struct.unpack("<ff", bytes.fromhex("cdcccc3ee6e5653f"))   # 0.4, 0.898
MOVE_TAIL = (struct.pack("<i", 1) + struct.pack("<i", 15) + b"make_walk_sound"
             + struct.pack("<i", 1) + struct.pack("<i", 10) + b"bip_mov_ik"
             + bytes.fromhex("00000000 00004040 a4703d3f 8fc2753e 5c8f423e 7b142e3e cdcccc3d ae47213f".replace(" ", "")))
LISTS_AT = 136   # after the name: flags list count, then the parameter list count (both 0 in the template)

# Attack clips. The record after the name, mapped on Native clips: +0 u32 = byte count from +8
# to the end of the parameter list (0x88 empty, 0xc9 with the movement lists), +12 duration, +16/+20 source range,
# +24 params, +40 animation guid, +56 four phase floats, then strings sound, voice, facial, blends-with action,
# 12 bytes, the combat parameter id (combat_parameters.xml: the hit window as clip progress), blend in/out + 5 bytes,
# the paired animation name, 15 bytes, flag names, parameter list. An attack clip copies all of it from the Native
# release clip it replaces, except animation, source range and (optionally) the blend pairing: Native release clips
# blend with their _balanced twin by weapon balance, so a clip on another skeleton must either keep a partner that
# exists in its action set or clear the field (see keep_blend in write_clip).
CLIP_TYPE = bytes.fromhex("c809655063e5a44cb166a53b92e913a7")

def _str(b, o):
    n = struct.unpack_from("<i", b, o)[0]
    if not 0 <= n < 512: raise ValueError("string length %d at %d" % (n, o))
    return bytes(b[o + 4:o + 4 + n]), o + 4 + n

def parse_clip(b, o):
    """Clip record fields, o = first byte after the clip name."""
    r = {"fixed": bytearray(b[o:o + 72])}
    q = o + 72
    # continue_with: the follow-up action (act_ready_continue_crossbow on ready_crossbow), usually empty
    for k in ("sound", "voice", "facial", "blends_with", "continue_with"): r[k], q = _str(b, q)
    r["ints"] = bytes(b[q:q + 8]); q += 8
    r["combat"], q = _str(b, q)
    r["blend"] = bytes(b[q:q + 13]); q += 13
    r["anim2"], q = _str(b, q)
    r["misc"] = bytes(b[q:q + 15]); q += 15
    # flag names, then named parameter blocks whose float count depends on the kind (bip_mov_ik 8, displacement 6):
    # kept raw up to the record end given by the leading byte count
    end = o + 8 + struct.unpack_from("<I", b, o)[0]
    n = struct.unpack_from("<i", b, q)[0]
    if not (0 <= n < 64 and q + 4 <= end): raise ValueError("clip layout differs")
    r["lists"] = bytes(b[q:end])
    return r

def pack_clip(r):
    S = lambda x: struct.pack("<i", len(x)) + x
    mid = bytearray(r["fixed"]) + S(r["sound"]) + S(r["voice"]) + S(r["facial"]) + S(r["blends_with"]) + S(r.get("continue_with", b"")) + r["ints"] \
        + S(r["combat"]) + r["blend"] + S(r["anim2"]) + r["misc"] + r["lists"]
    struct.pack_into("<I", mid, 0, len(mid) - 8)
    return mid

_native_clips = None

def native_clip(name):
    """Parsed record (parse_clip) of the Native clip of that name; reads the metadata of Native's animation packages once."""
    global _native_clips
    import glob, tw_formats
    if _native_clips is None:
        config.require_game(); _native_clips = {}
        for p in sorted(glob.glob(os.path.join(NATIVE, "EmAssetPackages", "animations", "*", "*.tpac"))):
            for it in tw_formats.read_package_index(p):
                if it["type"] == CLIP_TYPE: _native_clips.setdefault(it["name"], bytes(it["record"]))
    if name not in _native_clips: raise KeyError(name)
    return parse_clip(_native_clips[name], 0)

def hit_window(combat_id):
    """(start, end) clip progress of a combat parameter's damaging collision window."""
    import xml.etree.ElementTree as ET
    root = ET.parse(os.path.join(NATIVE, "ModuleData", "combat_parameters.xml")).getroot()
    c = next(c for c in root.iter("combat_parameter") if c.get("id") == combat_id)
    start = max(float(c.get("collision_check_starting_percent")), float(c.get("collision_damage_starting_percent") or 0))
    return start, float(c.get("collision_check_ending_percent"))

def fit_attack(frames, contact, dur, window, fps=30.0, first_key=0, kpf=None):
    """Source key range that puts the animation's contact frame at 42% of the hit window while staying close to real speed.
    kpf = stored keys per source frame (default the editor's 12.548 keys/s resampling assumption; an import that keeps
    one key per frame has kpf 1). Keys are counted from the sequence's first frame.
    Returns (s, e, progress at contact, speed = source seconds played per clip second)."""
    import math
    a, b = window; want = a + 0.42 * (b - a)
    if kpf is None: kpf = KEYS_PER_SECOND / fps            # old behaviour, first_key in keys
    else: first_key = int(math.ceil(first_key * kpf - 1e-6))  # with kpf given, first_key is a source frame
    K = int((frames - 1) * kpf + 1e-6); kc = contact * kpf
    best = None
    for s in range(first_key, int(kc) + 1):
        for e in range(int(math.ceil(kc)), K + 1):
            if e - s < 3 or not s < kc < e: continue
            p = (kc - s) / (e - s); speed = (e - s) / kpf / fps / dur
            # anywhere in the middle 70% of the window hits; beyond that, prefer real speed over the exact spot
            inner = a + 0.15 * (b - a) <= p <= b - 0.15 * (b - a)
            cost = 1.5 * abs(p - want) / (b - a) + abs(math.log(speed)) + (0 if inner else 10)
            if best is None or cost < best[0]: best = (cost, s, e, p, speed)
    return best[1:]

def write_clip(name, anim, frames, fps=30.0, move=False, attack=None, out_dir=None, src_range=None, move_distance=None,
               pair_self=False, keep_blend=True, template=None):
    """Write <name>_anm.tpac: a clip that plays the skeleton animation `anim` (looked up by name) for `frames` frames.
    The record starts from a plain Native clip record (templates.clip_template; `template` = a clip package that wins).
    move: movement clip (Native run_forward_1h's lists). attack = (parsed Native clip, source start key, source end key):
    copy that clip's settings. Returns (path, duration, end key)."""
    # pair_self: paired-animation string = the clip's own name, which registers the clip in all 10 slots of the
    # engine's weapon-balance table (Native release_thrust_2h does this); every melee release/blocked clip must be in
    # that table or the first lookup crashes
    # keep_blend: the blends_with ACTION of the Native clip the copy is modelled on stays (Native defend_shield_*_down ->
    # its act_..._up twin, release / ready / blocked -> their balanced twin, lance couch, brace). The engine's action start
    # reads that action unchecked when the request has a blend factor (shield block: 0.5 always), and -1 crashed in the
    # native client. RULE: never clear it for a clip a shield wielder or a lance rider can play; the target must be an
    # action of every set that uses the clip (clip_partners.py check).
    import templates
    rec = bytearray(templates.clip_template(template)["record"])
    # fields after the name: +12 duration, +16 source1, +20 source2 (floats); +40 the source animation guid
    dur = (frames - 1) / fps
    end_key = float(int((frames - 1) / fps * KEYS_PER_SECOND))
    if src_range: end_key = float(src_range[1])   # a segment of a single-take animation
    struct.pack_into("<fff", rec, 12, dur, float(src_range[0]) if src_range else 0.0, end_key)
    rec[40:56] = find_anim(anim)
    if move:
        assert rec[LISTS_AT:LISTS_AT + 8] == bytes(8)
        struct.pack_into("<ff", rec, 56, *MOVE_PHASES)
        tail = bytearray(MOVE_TAIL)
        if move_distance is not None: struct.pack_into("<f", tail, 45, float(move_distance))   # bip_mov_ik value 1: m per cycle
        rec[LISTS_AT:LISTS_AT + 8] = tail
        struct.pack_into("<I", rec, 0, len(rec) - 8)
    if attack:   # attack = (parsed Native release clip, source start key, source end key)
        nat, s, e = attack
        r = dict(nat, fixed=bytearray(nat["fixed"]), blends_with=nat["blends_with"] if keep_blend else b"",
                 anim2=name.encode() if pair_self else b"")
        dur = struct.unpack_from("<f", r["fixed"], 12)[0]; end_key = float(e)
        struct.pack_into("<ff", r["fixed"], 16, float(s), float(e))
        r["fixed"][40:56] = rec[40:56]
        assert rec[LISTS_AT:LISTS_AT + 8] == bytes(8)
        rec = bytearray(pack_clip(r))
    out = os.path.join(out_dir or ASSETS, name + "_anm.tpac")
    # a rewrite keeps the clip's ids: the editor caches each package as RuntimeDataCache/<package guid>.rdc, and an
    # orphaned cache with the same clip name crashes the game at the first agent spawn. A staged clip (out_dir) takes
    # the ids of the installed one, so copying it over later keeps them too.
    keep = out if os.path.exists(out) else os.path.join(ASSETS, name + "_anm.tpac")
    old = open(keep, "rb").read(0x44) if os.path.exists(keep) else None
    package = old[0x08:0x18] if old else uuid.uuid4().bytes
    resource = old[0x34:0x44] if old else uuid.uuid4().bytes
    # one-item package: header, the clip, its record hash, no data entries, no dependencies
    head = b"TPAC" + struct.pack("<I", 2) + package + struct.pack("<IQ", 1, 0) + CLIP_TYPE + resource + bytes(4)
    body = bytearray(head + _S(name) + bytes(rec) + struct.pack("<Q", xxh64(bytes(rec))) + bytes(8))
    struct.pack_into("<I", body, 0x1c, len(body) - 0x24)  # payload length
    if out_dir: os.makedirs(out_dir, exist_ok=True)
    open(out, "wb").write(body)
    return out, dur, end_key

# ---- materials (layout in the header) ----
MTL_TYPE = bytes.fromhex("9313b01d0269194f83bab37a39830717")
TEX_TYPE = bytes.fromhex("cbcb74c91c5ff6499a322b5b6c92c2e8")
SHADER_TYPE = bytes.fromhex("df2865b44403f94f80f2e30cd6c4fcc3")
# names seen in the material flags list of Native materials; any other --flags name goes to the shader flags list
MATERIAL_FLAGS = {"two_sided", "no_modify_depth_buffer", "dont_draw_to_gbuffer", "no_depth_test", "render_after_postfx",
                  "needs_forward_rendering", "cull_front_faces", "dont_optimize_mesh", "dont_cast_shadow",
                  "alpha_blend_sort", "disable_streaming"}
SLOTS = {"diffuse": 0, "normal": 2, "specular": 4}

def xxh64(data, seed=0):
    P1, P2, P3, P4, P5 = 11400714785074694791, 14029467366897019727, 1609587929392839161, 9650029242287828579, 2870177450012600261
    M = 0xFFFFFFFFFFFFFFFF
    rotl = lambda x, r: ((x << r) | (x >> (64 - r))) & M
    rnd = lambda acc, v: (rotl((acc + v * P2) & M, 31) * P1) & M
    n = len(data); i = 0
    if n >= 32:
        v = [(seed + P1 + P2) & M, (seed + P2) & M, seed & M, (seed - P1) & M]
        while i + 32 <= n:
            for k in range(4): v[k] = rnd(v[k], struct.unpack_from("<Q", data, i + 8 * k)[0])
            i += 32
        h = (rotl(v[0], 1) + rotl(v[1], 7) + rotl(v[2], 12) + rotl(v[3], 18)) & M
        for k in range(4): h = ((h ^ rnd(0, v[k])) * P1 + P4) & M
    else:
        h = (seed + P5) & M
    h = (h + n) & M
    while i + 8 <= n:
        h = (rotl(h ^ rnd(0, struct.unpack_from("<Q", data, i)[0]), 27) * P1 + P4) & M; i += 8
    if i + 4 <= n:
        h = (rotl(h ^ (struct.unpack_from("<I", data, i)[0] * P1 & M), 23) * P2 + P3) & M; i += 4
    while i < n:
        h = (rotl(h ^ (data[i] * P5 & M), 11) * P1) & M; i += 1
    h ^= h >> 33; h = h * P2 & M; h ^= h >> 29; h = h * P3 & M; h ^= h >> 32
    return h

def _list(b, o):
    n = struct.unpack_from("<i", b, o)[0]; o += 4
    if not 0 <= n < 64: raise ValueError("list count %d at %d" % (n, o))
    out = []
    for _ in range(n):
        s, o = _str(b, o); out.append(s.decode())
    return out, o

def parse_mtl(b, o):
    """Material record at o (its length field). Returns fields and the end offset (start of the xxh64)."""
    L = struct.unpack_from("<I", b, o)[0]
    r = {"head": bytes(b[o + 4:o + 36])}; q = o + 36
    r["mflags"], q = _list(b, q)
    r["u0"] = bytes(b[q:q + 4]); q += 4
    r["vlayout"], q = _list(b, q)
    s, q = _str(b, q); r["blend"] = s.decode()
    r["shader"] = bytes(b[q:q + 16]); q += 16
    n = struct.unpack_from("<i", b, q)[0]; q += 4; r["tex"] = []
    for _ in range(n):
        r["tex"].append((struct.unpack_from("<i", b, q)[0], bytes(b[q + 4:q + 20]))); q += 20
    r["alpha_ref"] = struct.unpack_from("<f", b, q)[0]; q += 4
    r["sflags"], q = _list(b, q)
    r["params"] = bytes(b[q:q + 112]); q += 112
    if q != o + 8 + L: raise ValueError("material layout differs (%d != %d)" % (q - o - 8, L))
    r["hash_ok"] = struct.unpack_from("<Q", b, q)[0] == xxh64(bytes(b[o:q]))
    return r, q

def pack_mtl(r):
    S = lambda x: struct.pack("<i", len(x)) + x.encode()
    Lst = lambda l: struct.pack("<i", len(l)) + b"".join(S(x) for x in l)
    rec = bytearray(4) + r["head"] + Lst(r["mflags"]) + r["u0"] + Lst(r["vlayout"]) + S(r["blend"]) + r["shader"] \
        + struct.pack("<i", len(r["tex"])) + b"".join(struct.pack("<i", s) + g for s, g in r["tex"]) \
        + struct.pack("<f", r["alpha_ref"]) + Lst(r["sflags"]) + r["params"]
    struct.pack_into("<I", rec, 0, len(rec) - 8)
    return bytes(rec) + struct.pack("<Q", xxh64(bytes(rec))) + bytes(8)

def read_mtl_file(path):
    b = open(path, "rb").read()
    if b[:4] != b"TPAC" or b[0x24:0x34] != MTL_TYPE: raise ValueError("not a material package: " + path)
    n = struct.unpack_from("<i", b, 0x48)[0]
    r, q = parse_mtl(b, 0x4c + n)
    if q + 16 != len(b) or b[q + 8:] != bytes(8): raise ValueError("unexpected bytes after the record")
    if struct.unpack_from("<i", b, 0x1c)[0] != len(b) - 0x24: raise ValueError("payload length wrong")
    r["name"] = b[0x4c:0x4c + n].decode(); r["package"] = b[0x08:0x18]; r["resource"] = b[0x34:0x44]
    return r

def native_materials():
    """Native editor-format material records: name -> fields."""
    b = open(NATIVE_MTLS, "rb").read(); out = {}
    for m in re.finditer(re.escape(MTL_TYPE) + rb".{16}\x00\x00\x00\x00(.{4})", b, re.S):
        n = struct.unpack("<i", m.group(1))[0]
        out[b[m.end():m.end() + n].decode()] = parse_mtl(b, m.end() + n)[0]
    return out

def find_shader(s):
    if re.fullmatch(r"[0-9a-fA-F]{32}", s): return bytes.fromhex(s)
    root = os.path.join(NATIVE, "EmAssetPackages", "core", "shaders")
    pat = re.escape(SHADER_TYPE) + rb"(.{16})\x00\x00\x00\x00" + re.escape(struct.pack("<i", len(s)) + s.encode())
    for d, _, fs in os.walk(root):
        for f in fs:
            m = re.search(pat, open(os.path.join(d, f), "rb").read(), re.S)
            if m: return m.group(1)
    raise KeyError("shader " + s)

def find_texture(name, extra_dir=None):
    p = os.path.join(ASSETS, name + "_tex.tpac")
    if extra_dir and os.path.exists(os.path.join(extra_dir, name + "_tex.tpac")): p = os.path.join(extra_dir, name + "_tex.tpac")
    b = open(p, "rb").read(0x4c + len(name))
    if b[0x24:0x34] != TEX_TYPE or b[0x4c:0x4c + len(name)].decode() != name: raise ValueError("not texture %s: %s" % (name, p))
    return b[0x34:0x44]

def write_material(name, shader, textures, blend=None, flags=None, skinning=None, alpha_ref=None, force=False, out_dir=None,
                   template=None):
    """Clone the closest Native material: for pbr_shading the plain Native pbr record of templates.material_template
    (or the package `template`), else the Native editor-package material with the same shader (and blend mode / flags,
    if any matches), then patch. Returns (path, record, template name).
    out_dir: write there instead (staging); textures are looked up there first."""
    import templates
    out = os.path.join(out_dir or ASSETS, name + "_mtl.tpac")
    if os.path.exists(out) and not force: raise FileExistsError(out + " exists (use --force)")
    sg = find_shader(shader)
    mod, msrc = templates.material_template(bool(skinning), template)
    if mod["shader"] == sg:
        t, tname = mod, msrc
    else:
        cands = [(k, r) for k, r in native_materials().items() if r["shader"] == sg]
        if not cands: raise KeyError("no editor material uses shader " + sg.hex())
        def score(kr):
            r = kr[1]; f = set(flags or [])
            return (r["blend"] == blend) + (set(r["mflags"]) | set(r["sflags"]) == f) * 2 + kr[0].startswith("custom_banner_icons")
        tname, t = max(sorted(cands), key=score)
    r = dict(t, mflags=list(t["mflags"]), vlayout=list(t["vlayout"]), sflags=list(t["sflags"]), tex=list(t["tex"]), shader=sg)
    if blend: r["blend"] = blend
    if flags is not None:
        r["mflags"] = [f for f in flags if f in MATERIAL_FLAGS]
        r["sflags"] = [f for f in flags if f not in MATERIAL_FLAGS]
    if skinning is not None:
        r["vlayout"] = [v for v in r["vlayout"] if v != "skinning"] + (["skinning"] if skinning else [])
    if alpha_ref is not None: r["alpha_ref"] = alpha_ref
    for slot, tex in textures.items():
        g = find_texture(tex, out_dir); s = SLOTS[slot]
        r["tex"] = [e for e in r["tex"] if e[0] != s] + [(s, g)]
    r["tex"].sort()
    return write_material_record(name, r, out_dir), r, tname

def write_material_record(name, r, out_dir=None):
    """Write a parsed material record (parse_mtl fields) as Assets/<name>_mtl.tpac. A rewrite keeps the package and
    resource ids; a new file gets fresh ones (also for a same-name override of a Native material: the engine logs
    "Overriding item" for a later module's item with the same name and type). A staged copy (out_dir) takes the
    ids of the installed material of that name, so copying it over keeps them."""
    out = os.path.join(out_dir or ASSETS, name + "_mtl.tpac")
    if out_dir: os.makedirs(out_dir, exist_ok=True)
    head = bytearray(b"TPAC" + struct.pack("<I", 2) + bytes(16) + struct.pack("<IQ", 1, 0) + MTL_TYPE + bytes(16) + bytes(4))
    keep = out if os.path.exists(out) else os.path.join(ASSETS, name + "_mtl.tpac")
    old = open(keep, "rb").read(0x44) if os.path.exists(keep) else None
    head[0x08:0x18] = old[0x08:0x18] if old else uuid.uuid4().bytes
    head[0x34:0x44] = old[0x34:0x44] if old else uuid.uuid4().bytes
    body = head + struct.pack("<i", len(name)) + name.encode() + pack_mtl(r)
    struct.pack_into("<i", body, 0x1c, len(body) - 0x24)
    open(out, "wb").write(body)
    return out

def show_mtl(r):
    sh = {bytes.fromhex("71b6a0ce4f381142a1a648a29a083c8f"): "pbr_shading",
          bytes.fromhex("31fd6eb92771ec468648b28d23ece108"): "gui_color_and_stroke"}
    print("  material flags %s | vertex layout %s | blend %s | shader %s %s" % (
        r["mflags"], r["vlayout"], r["blend"], r["shader"].hex(), sh.get(r["shader"], "")))
    print("  textures %s | alpha ref %g | shader flags %s | hash %s" % (
        [(s, g.hex()) for s, g in r["tex"]], r["alpha_ref"], r["sflags"], "ok" if r["hash_ok"] else "WRONG"))
    print("  params", ["%g" % v for v in struct.unpack("<28f", r["params"])])

# ---- textures (layout in the header) ----
TEX_SETTINGS = bytes.fromhex("e25b477c8d7c1d43b0e153218d047fb9")   # data type "Texture import settings"
TEX_SRCINFO = bytes.fromhex("a781b98aa06b0849960691ad341d19a9")    # data type "Source file info"
TEX_PIXELS = bytes.fromhex("2c4eee70e4792d4b8d54d53ecd2a559c")     # data type "Texture pixel data"
DATA_KIND = {TEX_SETTINGS: 4, TEX_SRCINFO: 0, TEX_PIXELS: 0}       # u32 after each entry (engine type table value)
MODULE = os.path.dirname(os.path.dirname(ASSETS))
GAME = os.path.dirname(os.path.dirname(MODULE))
RDC_DIR = os.path.join(MODULE, "RuntimeDataCache")
TEX_FORMATS = {"bc1": ("DXT1", 8), "bc3": ("DXT5", 16), "bc4": ("BC4", 8), "bc5": ("BC5", 16), "bc7": ("BC7", 16),
               "rgba8": ("R8G8B8A8_UNORM", 0)}
USAGE_BY_SUFFIX = {"d": "albedo", "n": "normalmap", "s": "specularmap", "h": "heightmap"}

def _S(s):
    s = s.encode() if isinstance(s, str) else s
    return struct.pack("<i", len(s)) + s

def _L(l): return struct.pack("<i", len(l)) + b"".join(_S(x) for x in l)

def lz4_compress(src):
    """LZ4 block, greedy like LZ4_compress_default (byte-identical to the editor's on 327 of 332 small blobs)."""
    n = len(src); out = bytearray(); table = {}; anchor = i = 0
    def emit(lit, mlen, off):
        L = len(lit); out.append(min(L, 15) << 4 | (min(mlen - 4, 15) if mlen else 0))
        if L >= 15:
            r = L - 15
            while r >= 255: out.append(255); r -= 255
            out.append(r)
        out.extend(lit)
        if mlen:
            out.extend(struct.pack("<H", off))
            if mlen - 4 >= 15:
                r = mlen - 19
                while r >= 255: out.append(255); r -= 255
                out.append(r)
    if n >= 13:
        while i <= n - 12:   # no match starts in the last 12 bytes, the last 5 stay literals
            k = src[i:i + 4]; j = table.get(k); table[k] = i
            if j is None or i - j > 65535: i += 1; continue
            s = i
            while s > anchor and j > 0 and src[s - 1] == src[j - 1]: s -= 1; j -= 1
            e = i + 4; jj = j + (e - s)
            while e < n - 5 and src[e] == src[jj]: e += 1; jj += 1
            emit(src[anchor:s], e - s, s - j)
            anchor = i = e
            table[src[i - 2:i + 2]] = i - 2
    emit(src[anchor:], 0, 0)
    return bytes(out)

def lz4_decompress(src, raw_size):
    """LZ4 block decoder (the format is by Yann Collet; this is a small pure-Python implementation)."""
    dst = bytearray(raw_size); s = 0; o = 0; n = len(src)
    while s < n:
        tok = src[s]; s += 1
        L = tok >> 4
        if L == 15:
            while True:
                b = src[s]; s += 1; L += b
                if b != 255: break
        dst[o:o + L] = src[s:s + L]; s += L; o += L
        if s >= n: break
        off = src[s] | (src[s + 1] << 8); s += 2
        M = tok & 15
        if M == 15:
            while True:
                b = src[s]; s += 1; M += b
                if b != 255: break
        M += 4; p = o - off
        if off >= M: dst[o:o + M] = dst[p:p + M]
        else:
            for k in range(M): dst[o + k] = dst[p + k]
        o += M
    return bytes(dst[:o])

def parse_tex_record(b, R):
    """Texture record fields at R (its length field), in a module or a Native editor package. Returns (fields, end)."""
    r = {}
    L = struct.unpack_from("<I", b, R)[0]; E = R + 8 + L
    if b[R + 4:R + 32] != bytes(4) + struct.pack("<I", 3) + bytes(20): raise ValueError("texture record head differs")
    path, q = _str(b, R + 32); r["path"] = path.decode()
    r["source_hash"] = b[q:q + 8]; q += 8
    if b[q:q + 5] != bytes(5): raise ValueError("texture field at +%d" % (q - R))
    r["import_flags"], q = _list(b, q + 5)
    if b[q:q + 5] != bytes.fromhex("0200000002"): raise ValueError("texture field at +%d" % (q - R))
    r["w"], r["h"], r["depth"], r["mips"], r["faces"] = struct.unpack_from("<IIIBH", b, q + 5); q += 20
    s, q = _str(b, q); r["format"] = s.decode()
    if b[q:q + 4] != bytes(4): raise ValueError("texture field at +%d" % (q - R))
    r["flags"], q = _list(b, q + 4)
    s, q = _str(b, q); r["group"] = s.decode()
    if b[q:q + 5] != bytes(5): raise ValueError("texture field at +%d" % (q - R))
    r["unk8"] = b[q + 5:q + 13]; r["vec"] = struct.unpack_from("<8f", b, q + 13); q += 45
    if q != E: raise ValueError("texture layout differs (%d != %d)" % (q - R, E - R))
    return r, E

def parse_tex(b):
    """Texture package fields: record, data entries (with their blobs), offsets. Raises on any layout surprise."""
    if b[:4] != b"TPAC" or b[0x24:0x34] != TEX_TYPE: raise ValueError("not a texture package")
    n = struct.unpack_from("<i", b, 0x48)[0]; R = 0x4c + n
    r, E = parse_tex_record(b, R)
    r.update(name=b[0x4c:R].decode(), package=b[0x08:0x18], resource=b[0x34:0x44])
    r["hash_ok"] = struct.unpack_from("<Q", b, E)[0] == xxh64(bytes(b[R:E]))
    q = E + 8; cnt = struct.unpack_from("<I", b, q)[0]; q += 4; r["entries"] = []
    for _ in range(cnt):
        off, raw, st = struct.unpack_from("<QQQ", b, q)
        e = {"off": off, "raw": raw, "stored": st, "owner": b[q + 24:q + 40], "type": b[q + 40:q + 56],
             "hash": b[q + 56:q + 64], "kind": struct.unpack_from("<I", b, q + 64)[0], "flag": b[q + 68]}
        e["blob"] = lz4_decompress(b[off:off + st], raw) if st < raw else bytes(b[off:off + st])
        e["hash_ok"] = struct.pack("<Q", xxh64(e["blob"])) == e["hash"]
        r["entries"].append(e); q += 69
    if b[q:q + 4] != bytes(4) or q + 4 != 0x24 + struct.unpack_from("<I", b, 0x1c)[0]: raise ValueError("texture trailer")
    return r

def pack_tex_record(r):
    rec = bytearray(4) + bytes(4) + struct.pack("<I", 3) + bytes(20) + _S(r["path"]) + r["source_hash"] + bytes(5) \
        + _L(r["import_flags"]) + bytes.fromhex("0200000002") \
        + struct.pack("<IIIBH", r["w"], r["h"], r.get("depth", 1), r["mips"], r.get("faces", 1)) + _S(r["format"]) \
        + bytes(4) + _L(r["flags"]) + _S(r.get("group", "none")) + bytes(5) + r["unk8"] \
        + struct.pack("<8f", *r.get("vec", (0, 0, 0, 1, 0, 0, 0, 1)))
    struct.pack_into("<I", rec, 0, len(rec) - 8)
    return bytes(rec)

def pack_package(type_guid, package, resource, name, record, entries):
    """One-resource package: header, resource, record + xxh64, data entry table, then the (LZ4) data blobs.
    entries = [(type guid, raw blob)]; returns the file bytes."""
    head = b"TPAC" + struct.pack("<I", 2) + package + struct.pack("<II", 1, 0) + bytes(4) \
        + type_guid + resource + bytes(4) + _S(name) + record + struct.pack("<Q", xxh64(record)) + struct.pack("<I", len(entries))
    meta = len(head) + 69 * len(entries) + 4
    table = b""; data = b""
    for ty, blob in entries:
        c = lz4_compress(blob); c = c if len(c) < len(blob) else blob
        table += struct.pack("<QQQ", meta + len(data), len(blob), len(c)) + resource + ty + struct.pack("<Q", xxh64(blob)) \
            + struct.pack("<IB", DATA_KIND.get(ty, 0), 1)
        data += c
    out = bytearray(head + table + bytes(4) + data)
    struct.pack_into("<I", out, 0x1c, meta - 0x24)   # payload length = metadata only, the blobs follow it
    return bytes(out)

def _pixel_hash(pix):
    import tw_formats   # record pixel hash: xxh64(all mips, seed 0x41c64e6d), engine rule
    return tw_formats.texture_pixel_hash(pix)

def rdc_path(package, rdc_dir=None):
    return os.path.join(rdc_dir or RDC_DIR, str(uuid.UUID(bytes_le=bytes(package))).upper() + ".rdc")

def read_rdc(path):
    """RuntimeDataCache file: entries with owner, data id, type, offset, sizes, compression, two hashes, flag, blob."""
    b = open(path, "rb").read()
    if b[:4] != b"RDC0": raise ValueError("not an rdc file")
    cnt, tl = struct.unpack_from("<II", b, 8); out = []
    if tl != 145 * cnt: raise ValueError("rdc table size")
    for k in range(cnt):
        o = 0x14 + 145 * k
        off, raw, st, comp = struct.unpack_from("<QQQI", b, o + 48)
        if b[o + 92:o + 140] != bytes(48) or b[o + 140:o + 144] != b"\xfa" * 4: raise ValueError("rdc entry layout")
        out.append({"owner": b[o:o + 16], "id": b[o + 16:o + 32], "type": b[o + 32:o + 48], "off": off, "raw": raw,
                    "stored": st, "comp": comp, "h1": b[o + 76:o + 84], "h2": b[o + 84:o + 92], "flag": b[o + 144],
                    "blob": b[off:off + st]})
    return out

def pack_rdc(entries, comp=0, flag=0):
    """entries = [(owner, data id, type, blob, h1, h2)]; comp: try LZ4 (kept only when it shrinks the blob). Written by
    tw_formats.pack_rdc_exact (engine rules: sorted by (owner, id, type), u32 = data type version, u8 = LZ4 stored).
    flag is ignored (kept for old callers)."""
    import tw_formats
    return tw_formats.pack_rdc_exact([(o, d, t, b, [h1, h2], bool(comp)) for o, d, t, b, h1, h2 in entries])

def mip_bytes(w, h, fmt):
    bs = dict(TEX_FORMATS.values()).get(fmt, 0)
    return w * h * 4 if not bs else max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * bs

def tex_pixels(path, rdc_dir=None):
    """(fields, pixel bytes): the inline "Texture pixel data" entry if there is one, else the package's .rdc."""
    r = parse_tex(open(path, "rb").read())
    for e in r["entries"]:
        if e["type"] == TEX_PIXELS: return r, e["blob"]
    here = os.path.dirname(os.path.abspath(path))   # an installed package reads the module cache, a staged one its own
    dirs = (RDC_DIR,) if os.path.normcase(here) == os.path.normcase(os.path.abspath(ASSETS)) else (here, rdc_dir, RDC_DIR)
    for d in dirs:
        p = rdc_path(r["package"], d) if d else None
        if p and os.path.exists(p):
            for e in read_rdc(p):
                if e["type"] == TEX_PIXELS and e["owner"] == r["resource"]:
                    r["rdc"] = p; r["rdc_h1_ok"] = e["h1"] == r["source_hash"]
                    st = [x for x in r["entries"] if x["type"] == TEX_SETTINGS]
                    r["rdc_h2_ok"] = bool(st) and e["h2"] == struct.pack("<Q", xxh64(st[0]["blob"]))
                    return r, e["blob"] if e["stored"] == e["raw"] else lz4_decompress(e["blob"], e["raw"])
    raise FileNotFoundError("no pixel data for %s (no inline entry, no %s)" % (path, rdc_path(r["package"])))

BLOCK = {"DXT1": 8, "BC1": 8, "DXT5": 16, "BC3": 16, "BC5": 16, "ATI2": 16, "BC4": 8, "ATI1": 8, "BC7": 16}

def _bc1_colors(c0, c1, np):
    def rgb(c): return np.stack([(c >> 11 & 31) * 255 // 31, (c >> 5 & 63) * 255 // 63, (c & 31) * 255 // 31], -1)
    a, b = rgb(c0.astype(np.int32)), rgb(c1.astype(np.int32))
    four = (c0 > c1)[:, None]
    c2 = np.where(four, (2 * a + b) // 3, (a + b) // 2)
    c3 = np.where(four, (a + 2 * b) // 3, 0)
    return np.stack([a, b, c2, c3], 1)   # (n, 4, 3)

def _alpha8(blk, np):
    a0 = blk[:, 0].astype(np.int32); a1 = blk[:, 1].astype(np.int32)
    bits = np.zeros(len(blk), np.uint64)
    for k in range(6): bits |= blk[:, 2 + k].astype(np.uint64) << np.uint64(8 * k)
    pal = np.zeros((len(blk), 8), np.int32); pal[:, 0] = a0; pal[:, 1] = a1
    big = a0 > a1
    for k in range(1, 7): pal[:, 1 + k] = np.where(big, ((7 - k) * a0 + k * a1) // 7, 0)
    for k in range(1, 5): pal[:, 1 + k] = np.where(big, pal[:, 1 + k], ((5 - k) * a0 + k * a1) // 5)
    pal[:, 6] = np.where(big, pal[:, 6], 0); pal[:, 7] = np.where(big, pal[:, 7], 255)
    idx = np.stack([(bits >> np.uint64(3 * t)) & np.uint64(7) for t in range(16)], 1).astype(np.int64)
    return np.take_along_axis(pal, idx, 1)   # (n, 16)

def decode_blocks(data, w, h, fmt):
    """RGBA uint8 (h, w, 4) of one mip stored in an engine format: DXT1/BC1, DXT5/BC3, BC4, BC5, R8G8B8A8_UNORM.
    BC7 (eight block modes with partition tables) is not decoded here; it still round-trips byte for byte."""
    import numpy as np
    if fmt == "R8G8B8A8_UNORM": return np.frombuffer(data[:w * h * 4], np.uint8).reshape(h, w, 4)
    if fmt == "BC7": raise NotImplementedError("BC7 decode is not implemented")
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4); n = bw * bh; bs = BLOCK[fmt]
    blk = np.frombuffer(data[:n * bs], np.uint8).reshape(n, bs)
    out = np.zeros((n, 16, 4), np.uint8); out[..., 3] = 255
    if fmt in ("DXT1", "BC1", "DXT5", "BC3"):
        cb = blk[:, -8:]
        c0 = cb[:, 0].astype(np.uint16) | cb[:, 1].astype(np.uint16) << 8
        c1 = cb[:, 2].astype(np.uint16) | cb[:, 3].astype(np.uint16) << 8
        pal = _bc1_colors(c0, c1, np)
        bits = cb[:, 4].astype(np.uint32) | cb[:, 5].astype(np.uint32) << 8 | cb[:, 6].astype(np.uint32) << 16 | cb[:, 7].astype(np.uint32) << 24
        idx = np.stack([(bits >> (2 * t)) & 3 for t in range(16)], 1).astype(np.int64)
        out[..., :3] = np.take_along_axis(pal, idx[..., None].repeat(3, 2), 1)
        if bs == 16: out[..., 3] = _alpha8(blk[:, :8], np)
    elif fmt in ("BC4", "ATI1"):
        v = _alpha8(blk, np); out[..., 0] = out[..., 1] = out[..., 2] = v
    elif fmt in ("BC5", "ATI2"):
        out[..., 0] = _alpha8(blk[:, :8], np); out[..., 1] = _alpha8(blk[:, 8:], np); out[..., 2] = 255
    else:
        raise NotImplementedError(fmt)
    img = out.reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)
    return img[:h, :w]

def decode_mip(r, pix, k=0):
    """RGBA uint8 array of mip k."""
    fmt = r["format"]; o = 0
    for j in range(k): o += mip_bytes(max(1, r["w"] >> j), max(1, r["h"] >> j), fmt)
    w, h = max(1, r["w"] >> k), max(1, r["h"] >> k)
    return decode_blocks(pix[o:o + mip_bytes(w, h, fmt)], w, h, fmt)

def _blocks(img):
    """(h, w, c) uint8 -> (n, 16, c) float32 4x4 blocks in row order, edges padded by replication."""
    import numpy as np
    h, w, c = img.shape; H, W = (h + 3) // 4 * 4, (w + 3) // 4 * 4
    if (H, W) != (h, w): img = np.pad(img, ((0, H - h), (0, W - w), (0, 0)), mode="edge")
    return img.reshape(H // 4, 4, W // 4, 4, c).transpose(0, 2, 1, 3, 4).reshape(-1, 16, c).astype(np.float32)

def _axis(x):
    """Principal axis of each block's colours, power iteration started at the farthest point from the mean."""
    import numpy as np
    d = x - x.mean(1, keepdims=True)
    cov = np.einsum("nki,nkj->nij", d, d)
    v = np.take_along_axis(d, (d ** 2).sum(2).argmax(1)[:, None, None], 1)[:, 0] + 1e-3
    for _ in range(8):
        v = np.einsum("nij,nj->ni", cov, v); v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)
    return v

def _nearest(x, pal):
    return ((x[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(-1).argmin(2)

def _to565(c):
    import numpy as np
    c = np.clip(c, 0, 255)
    return (np.rint(c[:, 0] * 31 / 255).astype(np.uint32) << 11) | (np.rint(c[:, 1] * 63 / 255).astype(np.uint32) << 5) \
        | np.rint(c[:, 2] * 31 / 255).astype(np.uint32)

def _bc1_fit(x, c0, c1):
    import numpy as np
    sw = c0 < c1; c0, c1 = np.where(sw, c1, c0), np.where(sw, c0, c1)   # four-colour mode needs c0 > c1
    rgb = lambda c: np.stack([(c >> 11 & 31) * 255 // 31, (c >> 5 & 63) * 255 // 63, (c & 31) * 255 // 31], -1).astype(np.float32)
    a, b = rgb(c0), rgb(c1)
    pal = np.stack([a, b, (2 * a + b) // 3, (a + 2 * b) // 3], 1)
    idx = _nearest(x, pal); idx[c0 == c1] = 0
    return c0, c1, idx, ((x - np.take_along_axis(pal, idx[..., None], 1)) ** 2).sum((1, 2))

def enc_bc1(x):
    """(n, 16, 3) -> (n, 8) uint8: range fit on the principal axis, then two least-squares endpoint refits."""
    import numpy as np
    n = len(x); m = x.mean(1); v = _axis(x)
    t = np.einsum("nki,ni->nk", x - m[:, None], v)
    c0, c1, idx, err = _bc1_fit(x, _to565(m + v * t.max(1)[:, None]), _to565(m + v * t.min(1)[:, None]))
    W = np.array([0, 1, 1 / 3, 2 / 3], np.float32)
    for _ in range(2):
        w = W[idx]; u = 1 - w
        A, B, C = (u * u).sum(1), (u * w).sum(1), (w * w).sum(1)
        det = A * C - B * B; ok = np.abs(det) > 1e-6; det = np.where(ok, det, 1)
        X, Y = (u[..., None] * x).sum(1), (w[..., None] * x).sum(1)
        a = (C[:, None] * X - B[:, None] * Y) / det[:, None]; b = (A[:, None] * Y - B[:, None] * X) / det[:, None]
        n0, n1, nidx, nerr = _bc1_fit(x, _to565(a), _to565(b))
        bt = ok & (nerr < err)
        c0, c1 = np.where(bt, n0, c0), np.where(bt, n1, c1); idx = np.where(bt[:, None], nidx, idx); err = np.where(bt, nerr, err)
    bits = (idx.astype(np.uint32) << (2 * np.arange(16, dtype=np.uint32))).sum(1, dtype=np.uint64).astype(np.uint32)
    out = np.zeros((n, 8), np.uint8)
    out[:, 0], out[:, 1], out[:, 2], out[:, 3] = c0 & 255, c0 >> 8, c1 & 255, c1 >> 8
    out[:, 4:8] = bits.astype("<u4").view(np.uint8).reshape(n, 4)
    return out

def enc_bc4(x):
    """(n, 16) one channel -> (n, 8) uint8, eight-value mode (a0 = max > a1 = min)."""
    import numpy as np
    n = len(x); a0 = np.rint(x.max(1)).astype(np.int32); a1 = np.rint(x.min(1)).astype(np.int32)
    w = np.array([0, 7, 1, 2, 3, 4, 5, 6])   # weight of a1 for index 0..7
    pal = ((7 - w[None]) * a0[:, None] + w[None] * a1[:, None]) // 7
    pal[:, 0], pal[:, 1] = a0, a1
    idx = np.abs(x[:, :, None] - pal[:, None, :]).argmin(2).astype(np.uint64); idx[a0 == a1] = 0
    bits = (idx << (3 * np.arange(16, dtype=np.uint64))).sum(1, dtype=np.uint64)
    out = np.zeros((n, 8), np.uint8); out[:, 0] = a0; out[:, 1] = a1
    for j in range(6): out[:, 2 + j] = (bits >> np.uint64(8 * j)) & np.uint64(255)
    return out

BC7_W4 = (0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64)

def enc_bc7(x):
    """(n, 16, 4) -> (n, 16) uint8, mode 6 only: one subset, RGBA 7-bit endpoints + p-bit, 4-bit indices."""
    import numpy as np
    n = len(x); m = x.mean(1); v = _axis(x); Wt = np.array(BC7_W4)
    t = np.einsum("nki,ni->nk", x - m[:, None], v)
    q, p, full = [], [], []
    for c in (np.clip(m + v * t.min(1)[:, None], 0, 255), np.clip(m + v * t.max(1)[:, None], 0, 255)):
        best = None
        for pb in (0, 1):   # one p-bit per endpoint, shared by its four channels
            cq = np.clip(np.rint((c - pb) / 2), 0, 127).astype(np.int32); err = ((cq * 2 + pb - c) ** 2).sum(1)
            if best is None: best = (cq, np.full(n, pb), err)
            else:
                lt = err < best[2]; best = (np.where(lt[:, None], cq, best[0]), np.where(lt, pb, best[1]), np.minimum(err, best[2]))
        q.append(best[0]); p.append(best[1]); full.append(best[0] * 2 + best[1][:, None])
    a, b = full
    pal = (((64 - Wt)[None, :, None] * a[:, None, :] + Wt[None, :, None] * b[:, None, :] + 32) >> 6).astype(np.float32)
    idx = _nearest(x, pal)
    sw = idx[:, 0] >= 8   # the anchor index is stored with 3 bits: swap the endpoints, invert the indices
    idx = np.where(sw[:, None], 15 - idx, idx)
    q0, q1 = np.where(sw[:, None], q[1], q[0]), np.where(sw[:, None], q[0], q[1])
    p0, p1 = np.where(sw, p[1], p[0]), np.where(sw, p[0], p[1])
    fields = [(np.full(n, 64), 7)] + [(qq[:, ch], 7) for ch in range(4) for qq in (q0, q1)] + [(p0, 1), (p1, 1), (idx[:, 0], 3)] \
        + [(idx[:, k], 4) for k in range(1, 16)]
    lo = np.zeros(n, np.uint64); hi = np.zeros(n, np.uint64); pos = 0
    for val, nb in fields:
        val = val.astype(np.uint64)
        if pos + nb <= 64: lo |= val << np.uint64(pos)
        elif pos >= 64: hi |= val << np.uint64(pos - 64)
        else:
            lo |= (val << np.uint64(pos)) & np.uint64(0xFFFFFFFFFFFFFFFF); hi |= val >> np.uint64(64 - pos)
        pos += nb
    return np.concatenate([lo.astype("<u8").view(np.uint8).reshape(n, 8), hi.astype("<u8").view(np.uint8).reshape(n, 8)], 1)

def encode_mip(img, fmt):
    """img (h, w, 4) uint8 RGBA -> bytes in the engine format (DXT1, DXT5, BC4, BC5, BC7, R8G8B8A8_UNORM)."""
    import numpy as np
    if fmt == "R8G8B8A8_UNORM": return np.ascontiguousarray(img, np.uint8).tobytes()
    x = _blocks(img)
    if fmt == "DXT1": out = enc_bc1(x[:, :, :3])
    elif fmt == "DXT5": out = np.concatenate([enc_bc4(x[:, :, 3]), enc_bc1(x[:, :, :3])], 1)
    elif fmt == "BC4": out = enc_bc4(x[:, :, 0])
    elif fmt == "BC5": out = np.concatenate([enc_bc4(x[:, :, 0]), enc_bc4(x[:, :, 1])], 1)
    elif fmt == "BC7": out = enc_bc7(x)
    else: raise ValueError(fmt)
    return out.tobytes()

def write_texture(png, name=None, fmt=None, usage=None, mips=True, flags=(), force=False, out_dir=None, rdc_dir=None,
                  inline=False, size=None, image=None, tex_flags=None, resource_guid=None):
    """Encode a PNG into <name>_tex.tpac (+ RuntimeDataCache/<package guid>.rdc holding the mips, as the editor does;
    with inline=True the mips go into the package as a "Texture pixel data" entry like Native's editor packages).
    A rewrite or a staged copy (out_dir) keeps the ids of the existing package of that name, so its .rdc name holds.
    size = (w, h) resamples the picture; image = RGBA array used as the picture instead of the PNG's pixels (the PNG
    still gives the source path, hash and info); tex_flags overrides the texture flags list (has_alpha, ...).
    resource_guid: use this resource id (a Native texture's, to override it by guid as well as by name).
    Returns (tpac path, rdc path or None, fields)."""
    import numpy as np, pngio
    name = name or os.path.splitext(os.path.basename(png))[0]
    out = os.path.join(out_dir or ASSETS, name + "_tex.tpac")
    if os.path.exists(out) and not force: raise FileExistsError(out + " exists (use --force)")
    src = open(png, "rb").read(); im = pngio.read_png(png)
    alpha = im["alpha"]
    srcfmt = "R8_UNORM" if im["mode"] == "L" else "B8G8R8A8_UNORM" if alpha else "B8G8R8"
    usage = usage or USAGE_BY_SUFFIX.get(name.rsplit("_", 1)[-1], "albedo")
    key = fmt or {"albedo": "bc3" if alpha else "bc1", "normalmap": "bc5", "heightmap": "bc4"}.get(usage, "bc1")
    efmt = TEX_FORMATS[key][0]
    sw, sh = im["size"]
    rgba = im["rgba"] if image is None else np.asarray(image, np.uint8)
    if size and tuple(size) != (rgba.shape[1], rgba.shape[0]):
        rgba = pngio.resize(rgba, size[0], size[1])
    h, w = rgba.shape[:2]
    n_mips = max(w, h).bit_length() if mips else 1
    chain = []
    for k in range(n_mips):
        m = rgba if k == 0 else pngio.resize(rgba, max(1, w >> k), max(1, h >> k))
        chain.append(encode_mip(m, efmt))
    pix = b"".join(chain)
    assert len(pix) == sum(mip_bytes(max(1, w >> k), max(1, h >> k), efmt) for k in range(n_mips))
    ap = os.path.abspath(png)
    # the editor stores the source path relative to the game folder; a PNG outside it gets the module's AssetSources path
    inside = ap.lower().startswith(GAME.lower() + os.sep)
    srcpath = "$BASE/" + os.path.relpath(ap, GAME).replace(chr(92), "/") if inside else config.source_base(os.path.basename(png))
    # import settings: usage string, then 104 bytes; the editor's "Do Not Compress" + "no mips" import wrote 01 01
    # (which byte is which is not pinned down: [0] = do not compress, [1] = no mips assumed)
    settings = _S(usage) + bytes([key == "rgba8", not mips]) + bytes(102)
    srcinfo = struct.pack("<IIIII", sw, sh, 1, 1, 1) + _S(srcfmt) + struct.pack("<Q", len(src))
    r = {"path": srcpath, "source_hash": struct.pack("<Q", xxh64(src)), "import_flags": list(flags), "w": w, "h": h,
         "mips": n_mips, "format": efmt,
         "flags": list(tex_flags) if tex_flags is not None else ["has_alpha"] if alpha and key in ("bc3", "bc7", "rgba8") else [],
         "group": "none", "unk8": _pixel_hash(pix)}
    keep = out if os.path.exists(out) else os.path.join(ASSETS, name + "_tex.tpac")
    old = open(keep, "rb").read(0x44) if os.path.exists(keep) else None
    package = old[0x08:0x18] if old else uuid.uuid4().bytes
    resource = old[0x34:0x44] if old and len(old) == 0x44 else uuid.uuid4().bytes   # an empty package has no resource
    if resource_guid: resource = bytes(resource_guid)
    entries = [(TEX_SETTINGS, settings), (TEX_SRCINFO, srcinfo)] + ([(TEX_PIXELS, pix)] if inline else [])
    data = pack_package(TEX_TYPE, package, resource, name, pack_tex_record(r), entries)
    rp = None
    if not inline:
        rp = rdc_path(package, rdc_dir)
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        open(rp, "wb").write(pack_rdc([(resource, resource, TEX_PIXELS, pix, r["source_hash"], struct.pack("<Q", xxh64(settings)))]))
    if out_dir: os.makedirs(out_dir, exist_ok=True)
    open(out, "wb").write(data)   # after the cache, so the package is never newer than a missing .rdc
    r.update(name=name, usage=usage, package=package, resource=resource)
    return out, rp, r

def show_tex(r):
    st = {e["type"]: e for e in r["entries"]}
    s = st.get(TEX_SETTINGS); si = st.get(TEX_SRCINFO)
    print("  %dx%d %s mips %d depth %d faces %d | flags %s | import flags %s | group %s | record hash %s" % (
        r["w"], r["h"], r["format"], r["mips"], r["depth"], r["faces"], r["flags"], r["import_flags"], r["group"],
        "ok" if r["hash_ok"] else "WRONG"))
    print("  source %s (xxh64 %s)" % (r["path"], r["source_hash"].hex()))
    if s: print("  import settings: usage %s, bytes %s" % (_str(s["blob"], 0)[0].decode(), s["blob"][_str(s["blob"], 0)[1]:][:4].hex()))
    if si:
        f, q = _str(si["blob"], 20)
        print("  source info: %dx%d %s, %d bytes" % (*struct.unpack_from("<II", si["blob"], 0), f.decode(), struct.unpack_from("<Q", si["blob"], q)[0]))
    print("  entries", [(DATA_NAMES.get(e["type"], e["type"].hex()), e["raw"], e["stored"], "ok" if e["hash_ok"] else "WRONG") for e in r["entries"]])

DATA_NAMES = {TEX_SETTINGS: "import settings", TEX_SRCINFO: "source info", TEX_PIXELS: "pixel data"}

# ---- clip caches: "Optimized animation" in RuntimeDataCache/<clip package>.rdc (layout in the header) ----
OPT_ANIM = bytes.fromhex("6f131e6cb7d0ff41bb7a275f3630db25")

def _bitfield(fields):
    v = p = 0
    for x, n in fields: v |= (int(x) & ((1 << n) - 1)) << p; p += n
    return v, p

def parse_optanim(d):
    """Fields of an Optimized animation blob (all 103 editor clip caches re-pack byte-identical)."""
    ver, one, end1, end2, nb, z = struct.unpack_from("<6I", d, 0)
    if ver != 2 or not 0 < nb <= 256: raise ValueError("not an Optimized animation this reader knows (version %d, %d bones)" % (ver, nb))
    o = 0x18; bones = []
    for b in range(nb):
        n, bits, tb = struct.unpack_from("<HBB", d, o); mx, mn = struct.unpack_from("<2f", d, o + 4)
        nbits = n * (3 + 3 * bits + tb); v = int.from_bytes(d[o + 12:o + 12 + (nbits + 7) // 8], "little"); p = 0; keys = []
        for _ in range(n):
            a = v >> p & 7; p += 3; c = []
            for _ in range(3): c.append(v >> p & ((1 << bits) - 1)); p += bits
            keys.append((v >> p & ((1 << tb) - 1), a, c)); p += tb
        bones.append(dict(n=n, bits=bits, tb=tb, mx=mx, mn=mn, keys=keys))
        o += 12 + 8 * ((nbits + 63) // 64) + (16 if b < nb - 1 else 12)
    n, bits, tb = struct.unpack_from("<HBB", d, o); mx, mn = struct.unpack_from("<2f", d, o + 4)
    if n == 0: raise NotImplementedError("clip cache without a root channel (only caches with a root position channel are read)")
    nbits = n * (3 * bits + tb); v = int.from_bytes(d[o + 12:o + 12 + (nbits + 7) // 8], "little"); p = 0; keys = []
    for _ in range(n):
        c = []
        for _ in range(3): c.append(v >> p & ((1 << bits) - 1)); p += bits
        keys.append((v >> p & ((1 << tb) - 1), c)); p += tb
    root = dict(n=n, bits=bits, tb=tb, mx=mx, mn=mn, keys=keys)
    o += 12 + 8 * ((nbits + 63) // 64) + 4
    A, B = struct.unpack_from("<II", d, o); nt, w = d[o + 8], d[o + 9]; o += 10
    if B > 1 << 20 or nt != nb: raise ValueError("frame table does not fit (%d frames, %d bone columns for %d bones)" % (B, nt, nb))
    v = int.from_bytes(d[o:o + (B * nt * w + 7) // 8], "little")
    table = [[v >> ((f * nt + b) * w) & ((1 << w) - 1) for b in range(nt)] for f in range(B)]
    return dict(ver=ver, one=one, end1=end1, end2=end2, z=z, bones=bones, root=root, A=A, B=B, w=w, table=table,
                last=struct.unpack_from("<I", d, len(d) - 4)[0])

def pack_optanim(r):
    nb = len(r["bones"])
    out = bytearray(struct.pack("<6I", r.get("ver", 2), r.get("one", 1), r["end1"], r["end2"], nb, r.get("z", 0)))
    for b, B in enumerate(r["bones"]):
        v, p = _bitfield([f for t, a, c in B["keys"] for f in [(a, 3)] + [(x, B["bits"]) for x in c] + [(t, B["tb"])]])
        out += struct.pack("<HBB2f", B["n"], B["bits"], B["tb"], B["mx"], B["mn"]) + v.to_bytes(8 * ((p + 63) // 64), "little") \
            + bytes(16 if b < nb - 1 else 12)
    R = r["root"]
    v, p = _bitfield([f for t, c in R["keys"] for f in [(x, R["bits"]) for x in c] + [(t, R["tb"])]])
    out += struct.pack("<HBB2f", R["n"], R["bits"], R["tb"], R["mx"], R["mn"]) + v.to_bytes(8 * ((p + 63) // 64), "little") + bytes(4)
    out += struct.pack("<IIBB", r["A"], r["B"], nb, r["w"])
    v, p = _bitfield([(x, r["w"]) for row in r["table"] for x in row])
    out += v.to_bytes((p + 7) // 8, "little")
    out += bytes((len(out) + 2 + 3) // 4 * 4 - len(out))
    out += struct.pack("<I", len(out) + 4 + 50 * len(r["bones"]) + 90)   # runtime size: blob + 50 x bones + 90 (28 bones: 1490)
    return bytes(out)

def decode_anim_blob(d):
    """Editor skeleton-animation data: name, per bone (key times, w,x,y,z quaternions), root (times, x,y,z,w)."""
    import numpy as np
    n = struct.unpack_from("<i", d, 0)[0]; name = d[4:4 + n].decode(); o = 4 + n
    nb = struct.unpack_from("<I", d, o)[0]; o += 4
    def channel(o):
        _, es, k = struct.unpack_from("<III", d, o); o += 12
        t = np.array(struct.unpack_from("<%df" % k, d, o)); o += 4 * k
        v = np.array(struct.unpack_from("<%df" % (k * es // 4), d, o)).reshape(k, es // 4) if k else np.zeros((0, 4)); o += es * k
        return (t, v), o
    rot = []
    for _ in range(nb):
        r_, o = channel(o); p_, o = channel(o)
        if len(p_[0]): raise NotImplementedError("bone position channels")
        rot.append(r_)
    root, o = channel(o)
    return name, rot, root

_anim_data_cache = {}
def find_anim_data(guid):
    """(raw animation data, its xxh64 bytes, package path) of a skeleton animation in the *_geo.tpac packages (staged folders first, then the module).
    Memoised per process; an entry is reused only while its package file is unchanged (size and mtime)."""
    hit = _anim_data_cache.get(bytes(guid))
    if hit:
        st = os.stat(hit[2])
        if (st.st_size, st.st_mtime_ns) == hit[3]: return hit[:3]
    r = _find_anim_data(guid); st = os.stat(r[2])
    _anim_data_cache[bytes(guid)] = tuple(r) + ((st.st_size, st.st_mtime_ns),)
    return r

def _find_anim_data(guid):
    pat = re.compile(rb"\x01\x00\x00\x00(.{8})(.{8})(.{8})" + re.escape(guid) + rb"(.{16})(.{8})", re.S)
    # staged packages first: a rebuilt animation keeps its guid, so the installed (older) copy must not win
    for f in [os.path.join(d, x) for d in [x for x in os.environ.get("TPAC_STAGE", "").split(";") if x] + [ASSETS]
              if os.path.isdir(d) for x in sorted(os.listdir(d))]:
        if not f.endswith("_geo.tpac"): continue
        p = f
        with open(p, "rb") as fh:
            h = fh.read(0x24)
            if h[:4] != b"TPAC": continue
            meta = h + fh.read(struct.unpack_from("<I", h, 0x1c)[0])
        if ANIM_TYPE + guid not in meta: continue
        m = pat.search(meta, meta.index(ANIM_TYPE + guid))
        if not m: continue
        off, raw, st = (struct.unpack("<Q", m.group(k))[0] for k in (1, 2, 3))
        with open(p, "rb") as fh:
            fh.seek(off); s = fh.read(st)
        return (lz4_decompress(s, raw) if st < raw else s), m.group(5), p
    raise KeyError("animation " + guid.hex())

def _sample(ch, t, quat):
    import numpy as np
    ts, vs = ch
    if t <= ts[0]: return vs[0]
    if t >= ts[-1]: return vs[-1]
    i = int(np.searchsorted(ts, t, side="right")) - 1; a = (t - ts[i]) / (ts[i + 1] - ts[i])
    if not quat: return vs[i] * (1 - a) + vs[i + 1] * a
    q = vs[i] * (1 - a) + vs[i + 1] * (1 if np.dot(vs[i], vs[i + 1]) >= 0 else -1) * a
    return q / np.linalg.norm(q)

def _reduce(times, vals, tol, quat):
    """Greedy key reduction: keep a key when interpolating across it errs more than tol (first and last kept)."""
    import numpy as np
    keep = [0]
    for i in range(1, len(times) - 1):   # pure Python on purpose: tracks are short and the early break wins (measured)
        a, b = keep[-1], i + 1
        for j in range(a + 1, b):
            u = (times[j] - times[a]) / (times[b] - times[a])
            q = vals[a] * (1 - u) + vals[b] * u
            if quat: q = q / np.linalg.norm(q)
            if np.abs(q - vals[j]).max() > tol: keep.append(i); break
    if len(times) > 1: keep.append(len(times) - 1)
    return keep

def encode_optanim(rot, root, s, e, rot_tol=2e-4, pos_tol=1e-4):
    """Optimized animation for source keys s..e (the clip's source range) of a decoded animation."""
    import numpy as np, bisect
    A, end = int(s), int(round(e)); frames = list(range(A, end + 1)); tb = max(1, end.bit_length())
    bones = []
    for ch in rot:
        q = np.array([_sample(ch, f, True) for f in frames])
        for i in range(1, len(q)):   # one hemisphere along the track
            if np.dot(q[i], q[i - 1]) < 0: q[i] = -q[i]
        keep = _reduce(frames, q, rot_tol, True)
        rows = []
        for i in keep:   # smallest three: drop the largest component, flag 1 = negate after rebuilding
            k = int(np.argmax(np.abs(q[i]))); neg = bool(q[i][k] < 0); qq = -q[i] if neg else q[i]
            rows.append((frames[i], k << 1 | int(neg), [qq[j] for j in range(4) if j != k]))
        allc = [x for _, _, c in rows for x in c]; mn, mx = float(np.float32(min(allc))), float(np.float32(max(allc)))
        bits = int(min(16, max(1, np.ceil(np.log2((mx - mn) / rot_tol + 1)))))
        M = (1 << bits) - 1; sc = M / (mx - mn) if mx > mn else 0
        keys = [(t, a, [min(M, max(0, int(round((x - mn) * sc)))) for x in c]) for t, a, c in rows]
        bones.append(dict(n=len(keys), bits=bits, tb=tb, mx=mx, mn=mn, keys=keys))
    p = np.array([_sample(root, f, False)[:3] for f in frames]) if len(root[0]) else np.zeros((len(frames), 3))
    keep = _reduce(frames, p, pos_tol, False)
    mn, mx = float(np.float32(p[keep].min())), float(np.float32(p[keep].max()))
    bits = int(min(20, max(1, np.ceil(np.log2((mx - mn) / pos_tol + 1)))))
    M = (1 << bits) - 1; sc = M / (mx - mn) if mx > mn else 0
    rk = [(frames[i], [min(M, max(0, int(round((x - mn) * sc)))) for x in p[i]]) for i in keep]
    root_ch = dict(n=len(rk), bits=bits, tb=tb, mx=mx, mn=mn, keys=rk)
    table = [[bisect.bisect_right([t for t, _, _ in B["keys"]], A + f) - 1 for B in bones] for f in range(len(frames))]
    w = max(1, (max(B["n"] for B in bones) - 1).bit_length())
    return dict(end1=end, end2=end, bones=bones, root=root_ch, A=A, B=len(frames), w=w, table=table)

def optanim_values(r):
    """Decoded {(bone, time): w,x,y,z} and {time: x,y,z} of an Optimized animation."""
    import numpy as np
    out = {}
    for b, B in enumerate(r["bones"]):
        M = (1 << B["bits"]) - 1
        for t, a, c in B["keys"]:
            cc = [B["mn"] + x / M * (B["mx"] - B["mn"]) for x in c]
            q = cc[:]; q.insert(a >> 1, np.sqrt(max(0.0, 1 - sum(x * x for x in cc)))); q = np.array(q)
            out[(b, t)] = -q if a & 1 else q
    R = r["root"]; M = (1 << R["bits"]) - 1
    root = {t: np.array([R["mn"] + x / M * (R["mx"] - R["mn"]) for x in c]) for t, c in R["keys"]}
    return out, root

def clip_fields(path):
    """(name, package, resource, animation guid, source start, source end, record hash slot) of a clip package."""
    b = open(path, "rb").read()
    if b[0x24:0x34] != CLIP_TYPE: raise ValueError("not a clip package: " + path)
    n = struct.unpack_from("<i", b, 0x48)[0]; R = 0x4c + n
    L = struct.unpack_from("<I", b, R)[0]; E = R + 8 + L
    s, e = struct.unpack_from("<ff", b, R + 16)
    return b[0x4c:R].decode(), b[0x08:0x18], b[0x34:0x44], b[R + 40:R + 56], s, e, b[E:E + 8]

_optanim_cache = {}
def write_clip_cache(path, rdc_dir=None):
    """Build a clip's RuntimeDataCache/<package>.rdc from its animation, as the editor does on load. Cache keys: h1 =
    xxh64 of the animation data, h2 = the clip record's hash slot (as stored, stale or not)."""
    name, package, resource, anim, s, e, slot = clip_fields(path)
    raw, h1, _ = find_anim_data(anim)
    key = (bytes(h1), s, e)      # many clips play the same animation range (copy-mode combat clips): encode once
    if key not in _optanim_cache:
        _, rot, root = decode_anim_blob(raw)
        r = encode_optanim(rot, root, s, e)
        _optanim_cache[key] = (r, pack_optanim(r))
    r, blob = _optanim_cache[key]
    rp = rdc_path(package, rdc_dir); os.makedirs(os.path.dirname(rp), exist_ok=True)
    open(rp, "wb").write(pack_rdc([(resource, resource, OPT_ANIM, blob, h1, slot)], comp=2, flag=1))
    return rp, r, len(blob)

# ---- skeleton animation import without the editor (FBX -> <fbx>_geo.tpac; layout in the header) ----
IMPORT_TYPE = bytes.fromhex("7936ba3ebdde7a4c8634f121f6325e33")   # import source resource (<fbx>.fbx)
ANIM_SETTINGS = bytes.fromhex("f83d7de95742db409f421436e339d581")  # its import settings data (value 4)
ANIM_DATA = bytes.fromhex("6d817dd0ed3c1c42a6afb793e75dc2be")      # skeleton animation keys (value 0)
DATA_KIND.update({ANIM_SETTINGS: 4, ANIM_DATA: 0})
ANIM_SETTINGS_HEAD = bytes.fromhex("0e00000061735f7665727465785f616e696d0101040000006e6f6e650300000000000100000100000000")
FBX_TICKS = 46186158000
EXTRA_ASSETS = [d for d in os.environ.get("TPAC_STAGE", "").split(";") if d]   # staged package folders also searched

def _euler_xyz(e):
    import numpy as np
    x, y, z = np.radians(np.asarray(e, float))
    cx, sx, cy, sy, cz, sz = np.cos(x), np.sin(x), np.cos(y), np.sin(y), np.cos(z), np.sin(z)
    return np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]) \
        @ np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])

def _mat_quat(m):
    """w,x,y,z, largest component computed first and positive (matches the editor's signs on all keys checked)."""
    import numpy as np
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = np.sqrt(tr + 1) * 2; return np.array([s / 4, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s])
    i = int(np.argmax([m[0, 0], m[1, 1], m[2, 2]]))
    if i == 0:
        s = np.sqrt(1 + m[0, 0] - m[1, 1] - m[2, 2]) * 2; return np.array([(m[2, 1] - m[1, 2]) / s, s / 4, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s])
    if i == 1:
        s = np.sqrt(1 + m[1, 1] - m[0, 0] - m[2, 2]) * 2; return np.array([(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, s / 4, (m[1, 2] + m[2, 1]) / s])
    s = np.sqrt(1 + m[2, 2] - m[0, 0] - m[1, 1]) * 2; return np.array([(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, s / 4])

def fbx_take(path):
    """Keys of a single-take skeleton FBX as the editor stores them: one key per frame at the file's frame rate, per
    bone (bip01_<name>_<index>, index = channel) the rotation of parent bone^-1 x bone from fully evaluated node
    transforms (rotation order, pre/post rotation, pivots, offsets: sdk_mesh.FbxNodes, like the importer's
    EvaluateGlobalTransform), the pelvis in its global frame; root = pelvis global position minus its first frame.
    Returns (take name, rotations [(times, quats)] by bone index, root (times, x,y,z,0 rows))."""
    import numpy as np
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from fbx_bones import load, find, props70
    import sdk_mesh
    ver, top = load(path)
    gs = props70(find(top, "GlobalSettings")[0]); fps = float(gs.get("CustomFrameRate", [30.0])[0])
    objs = find(top, "Objects")[0][2]; conns = find(top, "Connections")[0][2]
    byid = {n[1][0]: n for n in objs}; nodes = sdk_mesh.FbxNodes(top); models = nodes.models
    stacks = [n for n in objs if n[0] == "AnimationStack"]
    if len(stacks) != 1: raise ValueError("%s: %d takes (one expected)" % (path, len(stacks)))
    take = stacks[0][1][1].split("\x00")[0]; sp = props70(stacks[0])
    t0, t1 = sp.get("LocalStart", [0])[0], sp.get("LocalStop", [0])[0]
    frames = int(round((t1 - t0) / FBX_TICKS * fps)) + 1
    cn_of, curves = {}, {}
    for c in conns:
        k = c[1]
        if k[0] == "OP" and k[2] in models and byid.get(k[1], ("",))[0] == "AnimationCurveNode": cn_of[(k[2], k[3])] = k[1]
        if k[0] == "OP" and byid.get(k[1], ("",))[0] == "AnimationCurve": curves.setdefault(k[2], {})[k[3]] = byid[k[1]]
    def track(mid, prop, default):
        base = nodes.props[mid].get(prop, default); cn = cn_of.get((mid, prop)); out = []
        tt = (t0 + np.arange(frames) * (FBX_TICKS / fps)) / FBX_TICKS
        for i, ax in enumerate("XYZ"):
            cv = curves.get(cn, {}).get("d|" + ax) if cn else None
            if cv is None: out.append(np.full(frames, base[i])); continue
            kt = np.array([c for c in cv[2] if c[0] == "KeyTime"][0][1][0]) / FBX_TICKS
            kv = np.array([c for c in cv[2] if c[0] == "KeyValueFloat"][0][1][0])
            out.append(np.interp(tt, kt, kv))
        return np.stack(out, 1)
    bones = {}
    for mid, m in models.items():
        nm = m[1][1].split("\x00")[0]
        if nm.startswith("bip01_") and not nm.endswith("notused"): bones[int(nm.rsplit("_", 1)[1])] = mid
    if sorted(bones) != list(range(len(bones))): raise ValueError("bone indices not 0..n-1")
    times = np.arange(frames, dtype=float)
    anim = [mid for mid in models if any(cn_of.get((mid, p)) for p in ("Lcl Translation", "Lcl Rotation", "Lcl Scaling"))]
    tr = {mid: (track(mid, "Lcl Translation", [0, 0, 0]), track(mid, "Lcl Rotation", [0, 0, 0]), track(mid, "Lcl Scaling", [1, 1, 1])) for mid in anim}
    bone_of = {mid: i for i, mid in bones.items()}
    Q = np.zeros((len(bones), frames, 4)); O = np.zeros((frames, 3))
    for f in range(frames):
        L = {mid: nodes.local(mid, T=t[0][f], R=t[1][f], S=t[2][f]) for mid, t in tr.items()}
        G = {mid: nodes.global_(mid, L) for mid in bones.values()}
        for i, mid in bones.items():
            p = nodes.parent.get(mid)
            M = G[mid] if p not in bone_of else np.linalg.inv(G[p]) @ G[mid]
            Q[i, f] = _mat_quat(sdk_mesh.rotation_only(M))
        O[f] = G[bones[0]][:3, 3]
    rot = [(times, Q[i]) for i in range(len(bones))]
    root = (times, np.concatenate([O - O[0], np.zeros((frames, 1))], 1))
    return take, rot, root

def pack_anim_blob(name, rot, root):
    """Skeleton animation data: name, bone count, per bone a rotation channel and an empty position channel, the
    root position channel, one more empty channel. Channel: u32 0, u32 16, u32 n, n f32 times, n x 4 f32."""
    import numpy as np
    ch = lambda t, v: struct.pack("<III", 0, 16, len(t)) + np.asarray(t, "<f4").tobytes() + np.asarray(v, "<f4").tobytes()
    out = _S(name) + struct.pack("<I", len(rot))
    for t, v in rot: out += ch(t, v) + struct.pack("<III", 0, 16, 0)
    return out + ch(*root) + struct.pack("<III", 0, 16, 0)

def pack_resources(package, resources):
    """Multi-resource package. resources = [(type, guid, flag, name, record, [(data type, raw blob)])]; each resource:
    type, guid, u32 flag, name, record, xxh64, u32 entry count, 69-byte entries, u32 0. Blobs follow the metadata.
    Resources go in guid byte order (all 84 editor _geo packages)."""
    resources = sorted(resources, key=lambda r: r[1])
    meta = 0x24 + sum(40 + len(n.encode()) + len(rec) + 8 + 4 + 69 * len(ents) + 4 for _, _, _, n, rec, ents in resources)
    head = b"TPAC" + struct.pack("<I", 2) + package + struct.pack("<II", len(resources), meta - 0x24) + bytes(4)
    body = b""; data = b""
    for ty, g, fl, name, rec, ents in resources:
        body += ty + g + struct.pack("<I", fl) + _S(name) + rec + struct.pack("<Q", xxh64(rec)) + struct.pack("<I", len(ents))
        for dt, blob in ents:
            c = lz4_compress(blob); c = c if len(c) < len(blob) else blob
            body += struct.pack("<QQQ", meta + len(data), len(blob), len(c)) + g + dt + struct.pack("<Q", xxh64(blob)) \
                + struct.pack("<IB", DATA_KIND.get(dt, 0), 1)
            data += c
        body += bytes(4)
    assert len(head) + len(body) == meta
    return head + body + data

def write_anim_package(fbx, out_dir=None, force=False, ids=None, owner=HUMAN_SKELETON):
    """<fbx name>_geo.tpac with the FBX's single take as a skeleton animation (owner skeleton set), as the editor's
    import writes it. ids = (package, import source, animation) guids to reuse; else the installed or staged package
    of that name gives them, else fresh ones. Returns (path, take name, key count)."""
    base = os.path.splitext(os.path.basename(fbx))[0]
    out = os.path.join(out_dir or ASSETS, base + "_geo.tpac")
    if os.path.exists(out) and not force: raise FileExistsError(out + " exists (use --force)")
    take, rot, root = fbx_take(fbx)
    if ids is None:
        ids = (uuid.uuid4().bytes, uuid.uuid4().bytes, uuid.uuid4().bytes)
        for p in (out, os.path.join(ASSETS, base + "_geo.tpac")):
            if os.path.exists(p):
                b = open(p, "rb").read(); meta = b[:0x24 + struct.unpack_from("<I", b, 0x1c)[0]]
                i, a = meta.find(IMPORT_TYPE), meta.find(ANIM_TYPE)
                if i > 0 and a > 0: ids = (b[8:24], meta[i + 16:i + 32], meta[a + 16:a + 32])
                break
    package, src, anim = ids
    src_rec = bytearray(4) + struct.pack("<II", 0, 1) + _S(config.source_base(base + ".fbx")) \
        + struct.pack("<Q", xxh64(open(fbx, "rb").read())) + struct.pack("<I", 1) + ANIM_TYPE + anim + bytes(4)
    struct.pack_into("<I", src_rec, 0, len(src_rec) - 8)
    anim_rec = bytearray(4) + struct.pack("<II", 0, 1) + src + b"\0" + owner + struct.pack("<III", len(rot), len(rot[0][0]), 0)
    struct.pack_into("<I", anim_rec, 0, len(anim_rec) - 8)
    settings = ANIM_SETTINGS_HEAD + struct.pack("<I", 1) + _S(take) + b"\0"
    data = pack_resources(package, [(IMPORT_TYPE, src, 0, base + ".fbx", bytes(src_rec), [(ANIM_SETTINGS, settings)]),
                                    (ANIM_TYPE, anim, 0, take, bytes(anim_rec), [(ANIM_DATA, pack_anim_blob(take, rot, root))])])
    if out_dir: os.makedirs(out_dir, exist_ok=True)
    open(out, "wb").write(data)
    return out, take, len(rot[0][0])

def write_anim_takes(base, takes, owner, out_dir=None, force=False, src_hash=bytes(8)):
    """<base>_geo.tpac with several skeleton animations (a multi-take import), keys given directly.
    takes = [(name, rot [(times, w x y z quats)] per bone, root (times, x y z 0 rows))]. Animation ids are kept per
    name when the package exists (installed or staged). Returns the path."""
    out = os.path.join(out_dir or ASSETS, base + "_geo.tpac")
    if os.path.exists(out) and not force: raise FileExistsError(out + " exists (use --force)")
    old = {}; package = src = None
    for p in (out, os.path.join(ASSETS, base + "_geo.tpac")):
        if os.path.exists(p):
            b = open(p, "rb").read(); meta = b[:0x24 + struct.unpack_from("<I", b, 0x1c)[0]]; package = b[8:24]
            i = meta.find(IMPORT_TYPE); src = meta[i + 16:i + 32] if i > 0 else None
            for m in re.finditer(re.escape(ANIM_TYPE) + rb"(.{16})(.{4})(.{4})", meta, re.S):
                n = struct.unpack("<i", m.group(3))[0]; old[meta[m.end():m.end() + n].decode("ascii", "replace")] = m.group(1)
            break
    package = package or uuid.uuid4().bytes; src = src or uuid.uuid4().bytes
    ids = [(t[0], old.get(t[0]) or uuid.uuid4().bytes) for t in takes]
    src_rec = bytearray(4) + struct.pack("<II", 0, 1) + _S(config.source_base(base + ".fbx")) + src_hash \
        + struct.pack("<I", len(ids)) + b"".join(ANIM_TYPE + g for _, g in ids) + bytes(4)
    struct.pack_into("<I", src_rec, 0, len(src_rec) - 8)
    settings = ANIM_SETTINGS_HEAD + struct.pack("<I", len(takes)) + b"".join(_S(t[0]) + b"\0" for t in takes)
    res = [(IMPORT_TYPE, src, 0, base + ".fbx", bytes(src_rec), [(ANIM_SETTINGS, settings)])]
    for (name, rot, root), (_, g) in zip(takes, ids):
        rec = bytearray(4) + struct.pack("<II", 0, 1) + src + b"\0" + owner + struct.pack("<III", len(rot), len(rot[0][0]), 0)
        struct.pack_into("<I", rec, 0, len(rec) - 8)
        res.append((ANIM_TYPE, g, 0, name, bytes(rec), [(ANIM_DATA, pack_anim_blob(name, rot, root))]))
    if out_dir: os.makedirs(out_dir, exist_ok=True)
    open(out, "wb").write(pack_resources(package, res))
    return out

def help_text():
    """The command list from this file's header comment."""
    head = open(__file__, encoding="utf-8").read().split(chr(10) + "# Package file")[0]
    return chr(10).join(l[2:] if l.startswith("# ") else l.lstrip("#") for l in head.splitlines())

def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(help_text())
        return 0 if len(argv) > 1 else 2
    sys.argv = argv; cmd = argv[1]
    if cmd == "anims":
        for n, (g, off, own) in sorted(anims(sys.argv[2]).items()):
            print("%-32s %s owner=%s" % (n, g.hex(), "human_skeleton" if own == HUMAN_SKELETON else (own.hex() if own else "?")))
    elif cmd == "owner":
        a = sys.argv[2:]; sk = bytes.fromhex(a[a.index("--skeleton") + 1]) if "--skeleton" in a else HUMAN_SKELETON
        for p in [x for x in a if x.endswith(".tpac")]: print(os.path.basename(p), "owners set:", set_owner(p, sk))
    elif cmd == "clip":   # tpac.py clip <name> <anim name> <frames> [fps] [--out DIR] [--template clip.tpac]
        a = [x for x in sys.argv[2:]]; opt = lambda k: a[a.index(k) + 1] if k in a else None
        pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] not in ("--out", "--template"))]
        fps = float(pos[3]) if len(pos) > 3 else 30.0
        out, dur, ek = write_clip(pos[0], pos[1], int(pos[2]), fps, out_dir=opt("--out"), template=opt("--template"))
        print("wrote %s  duration %.3f s  keys 0..%d" % (os.path.basename(out), dur, ek))
    elif cmd == "material":
        a = sys.argv[3:]; opt = lambda k: a[a.index(k) + 1] if k in a else None
        tex = {s: opt("--" + s) for s in SLOTS if opt("--" + s)}
        flags = opt("--flags").split(",") if opt("--flags") else None
        skin = False if "--static" in a else True if "--skinned" in a else None
        ar = float(opt("--alpha-ref")) if opt("--alpha-ref") else None
        try: out, r, tname = write_material(sys.argv[2], opt("--shader") or "pbr_shading", tex, opt("--blend"), flags,
                                            skin, ar, "--force" in a, opt("--out"), opt("--template"))
        except FileExistsError as e: sys.exit(str(e))
        print("wrote %s (template %s)" % (os.path.basename(out), tname))
        show_mtl(read_mtl_file(out))
    elif cmd == "mtl":
        for p in sys.argv[2:]:
            r = read_mtl_file(p); print(r["name"], "package", r["package"].hex(), "resource", r["resource"].hex())
            show_mtl(r)
    elif cmd == "retex":   # tpac.py retex <material> [--diffuse T] [--normal T] [--specular T] [--out DIR] [--texdir DIR] [--force]
        # an installed module material with only its texture slots changed (same ids, everything else kept)
        a = sys.argv[3:]; opt = lambda k: a[a.index(k) + 1] if k in a else None
        r = read_mtl_file(os.path.join(ASSETS, sys.argv[2] + "_mtl.tpac"))
        for slot, s in SLOTS.items():
            if opt("--" + slot):
                g = find_texture(opt("--" + slot), opt("--texdir") or opt("--out"))
                r["tex"] = sorted([e for e in r["tex"] if e[0] != s] + [(s, g)])
        if not opt("--out") and "--force" not in a: sys.exit("this rewrites an installed material: pass --out DIR to stage, or --force")
        out = write_material_record(sys.argv[2], r, opt("--out")); print("wrote", out); show_mtl(read_mtl_file(out))
    elif cmd == "clip-cache":   # tpac.py clip-cache <clip glob> [--clips DIR] [--rdc DIR] [--dry]: build clip caches without the editor
        import glob
        a = sys.argv[3:]; rdc = a[a.index("--rdc") + 1] if "--rdc" in a else None
        files = sorted(glob.glob(os.path.join(a[a.index("--clips") + 1] if "--clips" in a else ASSETS, sys.argv[2] + "_anm.tpac")))
        for f in files:
            name, package, *_ = clip_fields(f)
            if "--dry" in a: print("would write", name, rdc_path(package, rdc)); continue
            try: rp, r, n = write_clip_cache(f, rdc)
            except KeyError as ex: print("SKIP %s: %s not in the staged or installed packages" % (name, ex)); continue
            print("wrote %-44s %s  keys %d..%d, %d bytes" % (name, os.path.basename(rp), r["A"], r["end1"], n))
    elif cmd == "optanim":   # tpac.py optanim <file_anm.tpac> [--rdc DIR]: print a clip cache's channels
        a = sys.argv[2:]; rdc = a[a.index("--rdc") + 1] if "--rdc" in a else None
        name, package, *_ = clip_fields(a[0]); rp = rdc_path(package, rdc)
        E = read_rdc(rp)[0]; r = parse_optanim(lz4_decompress(E["blob"], E["raw"]) if E["stored"] < E["raw"] else E["blob"])
        print(name, rp, "keys %d..%d (%d frames), key index bits %d, h1 %s h2 %s" % (r["A"], r["end1"], r["B"], r["w"],
              E["h1"].hex(), E["h2"].hex()))
        for b, B in enumerate(r["bones"]):
            print("  bone %2d: %3d keys, %2d bits, range %.4f..%.4f" % (b, B["n"], B["bits"], B["mn"], B["mx"]))
        R = r["root"]; print("  root:    %3d keys, %2d bits, range %.4f..%.4f" % (R["n"], R["bits"], R["mn"], R["mx"]))
    elif cmd == "anim":   # tpac.py anim <fbx> [...] [--out DIR] [--force]: FBX single take -> <fbx name>_geo.tpac
        a = sys.argv[2:]; out_dir = a[a.index("--out") + 1] if "--out" in a else None
        for f in [x for i, x in enumerate(a) if x.lower().endswith(".fbx")]:
            try: out, take, nk = write_anim_package(f, out_dir, "--force" in a)
            except FileExistsError as e: print(e); continue
            print("wrote %-44s animation %s, %d keys" % (out, take, nk))
    elif cmd == "texture":   # tpac.py texture <png> [--name N] [--format bc1|bc3|bc4|bc5|bc7|rgba8] [--usage U | --srgb |
        # --linear] [--no-mips] [--flags a,b] [--out DIR] [--rdc DIR] [--inline] [--force]
        a = sys.argv[3:]; opt = lambda k: a[a.index(k) + 1] if k in a else None
        usage = opt("--usage") or ("albedo" if "--srgb" in a else None)
        if "--linear" in a and not usage:   # no colour space field exists: the usage string is the only hint
            sfx = USAGE_BY_SUFFIX.get((opt("--name") or os.path.splitext(os.path.basename(sys.argv[2]))[0]).rsplit("_", 1)[-1])
            usage = sfx if sfx and sfx != "albedo" else "specularmap"
        if opt("--format") and opt("--format") not in TEX_FORMATS: sys.exit("format: " + "|".join(TEX_FORMATS))
        try: out, rp, r = write_texture(sys.argv[2], opt("--name"), opt("--format"), usage, "--no-mips" not in a,
                                        opt("--flags").split(",") if opt("--flags") else (), "--force" in a, opt("--out"),
                                        opt("--rdc"), "--inline" in a)
        except FileExistsError as e: sys.exit(str(e))
        print("wrote %s%s  (%s, usage %s, package %s)" % (out, "\n  and " + rp if rp else "", r["format"], r["usage"],
                                                          str(uuid.UUID(bytes_le=r["package"])).upper()))
        r2, pix = tex_pixels(out, opt("--rdc")); show_tex(r2)
    elif cmd == "tex":   # tpac.py tex <file_tex.tpac> [out.png] [--mip k] [--rdc DIR] [--compare other_tex.tpac]
        a = sys.argv[2:]; opt = lambda k: a[a.index(k) + 1] if k in a else None
        r, pix = tex_pixels(a[0], opt("--rdc"))
        print(r["name"], "package", str(uuid.UUID(bytes_le=r["package"])).upper(), "resource", r["resource"].hex())
        show_tex(r)
        if "rdc" in r: print("  pixels in %s (source hash %s, settings hash %s)" % (r["rdc"], "ok" if r["rdc_h1_ok"] else
                                "DIFFERS", "ok" if r["rdc_h2_ok"] else "DIFFERS"))
        k = int(opt("--mip") or 0); img = decode_mip(r, pix, k)
        if len(a) > 1 and a[1].lower().endswith(".png"):
            import pngio
            pngio.write_png(a[1], img); print("  mip %d -> %s" % (k, a[1]))
        if opt("--compare"):
            import numpy as np
            r2, pix2 = tex_pixels(opt("--compare"), opt("--rdc"))
            same = [f for f in ("path", "source_hash", "import_flags", "w", "h", "depth", "mips", "faces", "format", "flags", "group")
                    if r[f] == r2[f]]
            print("  same fields:", same)
            print("  differing:", {f: (r[f], r2[f]) for f in ("name", "path", "source_hash", "import_flags", "w", "h", "mips",
                                    "format", "flags", "unk8", "vec") if r[f] != r2[f]})
            for e, e2 in zip(r["entries"], r2["entries"]):
                print("  entry %s: blob %s, stored %d vs %d" % (DATA_NAMES.get(e["type"]), "same" if e["blob"] == e2["blob"]
                                                               else "DIFFERS", e["stored"], e2["stored"]))
            for j in range(min(r["mips"], r2["mips"])):
                x, y = decode_mip(r, pix, j).astype(float), decode_mip(r2, pix2, j).astype(float)
                ch = {"BC4": [0], "BC5": [0, 1], "DXT1": [0, 1, 2]}.get(r["format"], [0, 1, 2, 3])
                mse = ((x[..., ch] - y[..., ch]) ** 2).mean()
                print("  mip %d %dx%d PSNR %.2f dB" % (j, x.shape[1], x.shape[0], 10 * np.log10(255 ** 2 / max(mse, 1e-10))))
                if x.shape[0] < 64: break
    else:
        print("unknown command " + cmd + " (python tpac.py --help)"); return 2
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
