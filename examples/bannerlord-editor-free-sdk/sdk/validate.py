# Validators for what this SDK writes: they reject data that crashes or hangs the native client, or turns into NaN in the
# engine's animation evaluation. Read only.
#   python validate.py stage <stage folder or name> [--sets FILE ...] [--model SET=NATIVE_SET ...] [--bones N]
#   python validate.py skeleton <skeleton_geo.tpac> [...]
#   python validate.py clip <clip_anm.tpac> [...]
#   python validate.py registration <project.mbproj> [extra dir ...]
#   python validate.py monsters <monsters.xml> [--sets FILE ...] [--stage DIR]
# Checks
#   skeleton  at most 64 bones (the engine's rgl_max_bones), parents first, bind rotations orthonormal (det +1) and finite,
#             user data finite and following the bones, ragdoll bodies with mass > 0 and a capsule of real size, a ragdoll body
#             on the root, joint frames finite unit quaternions, joint bones exist, d6 joints only between bones with bodies,
#             and the IK rule: a hit capsule on a bone without an ik joint freezes the native hit-IK solver (ik_hit_bones.py)
#   clips     name at most 63 characters (the engine copies a self-paired clip's name into a 64-byte buffer), duration > 0 and
#             finite, source range finite and inside the animation's keys, parameter floats finite, step points -1 or 0..1,
#             blend times finite and >= 0, bip_mov_ik eight finite floats, combat parameter id known to Native's
#             combat_parameters.xml, a self-paired clip pairs with itself
#   caches    every clip has its Optimized animation entry, built from the staged animation (h1), the size trailer follows the
#             engine rule, quaternions finite and unit, bone count equals the skeleton's
#   anims     every take: finite unit quaternions, increasing key times, bone count equals the owner skeleton's, finite root,
#             owner skeleton set, name at most 63 characters
#   meshes    finite positions, vertex stream present, weights sum 1, bone indices below the skeleton's bone count
#   partners  clip_partners.py rule for the action sets given with --sets (blends_with partners are actions of the set)
#   balance   every clip on a melee release / blocked action is paired with itself (the engine's weapon-balance table)
#   registration  every project.mbproj id is one Native registers (the engine never merges another id), with Native's type
#   monsters  body_rotation_reference_bone is not a root, ragdoll_* bones have ragdoll bodies, look-at chain has d6 joints,
#             IK chains have real bone lengths, eye offsets finite, heights > 0, fall_blow_damage_bone below 28
import collections, glob, os, re, struct, sys, uuid
import xml.etree.ElementTree as ET
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import config, tpac, sdk_mesh, sdk_skeleton, ik_hit_bones

MAX_BONES = 64
RIDER_BONES = 28   # Native human_skeleton (every rider); a mount's fall_blow_damage_bone must index below it


def finite(*v):
    return all(np.all(np.isfinite(np.asarray(x, float))) for x in v)


def _errs():
    errors = []
    return errors, (lambda *m: errors.append(" ".join(str(x) for x in m)))


def combat_ids():
    r = ET.parse(os.path.join(config.NATIVE_DATA, "combat_parameters.xml")).getroot()
    return {c.get("id") for c in r.iter("combat_parameter")}


def clip_record(path):
    b = open(path, "rb").read()
    n = struct.unpack_from("<i", b, 0x48)[0]; R = 0x4c + n
    return b[0x4c:R].decode(), tpac.parse_clip(b, R), b


def mov_ik(lists):
    i = lists.find(b"bip_mov_ik")
    return None if i < 0 else struct.unpack_from("<8f", lists, i + 10)


# ---------------------------------------------------------------------------------------------------------------- skeleton
def validate_skeleton(name, bones, U):
    errors, err = _errs()
    names = [b["name"] for b in bones]; nb = len(bones)
    if nb > MAX_BONES: err(name, "bones", nb, ">", MAX_BONES)
    for b in bones:
        Rm = b["R"]
        if not finite(Rm, b["o"]): err("bone", b["name"], "non-finite bind")
        elif np.abs(Rm.T @ Rm - np.eye(3)).max() > 1e-3 or abs(np.linalg.det(Rm) - 1) > 1e-3: err("bone", b["name"], "bind not orthonormal, det", np.linalg.det(Rm))
    if bones[0]["parent"] != -1 or any(b["parent"] >= i for i, b in enumerate(bones)): err(name, "parents not first")
    bodies = {x["bone"]: x for x in U["bodies"]}
    if len(U["bodies"]) != nb or [x["bone"] for x in U["bodies"]] != names: err(name, "user data bodies do not follow the bones")
    for x in U["bodies"]:
        vals = [x["mass"], x["extra"], *x["cap1"][0], *x["cap1"][1], x["cap1"][2], *x["cap2"][0], *x["cap2"][1], x["cap2"][2]]
        if not finite(vals): err("body", x["bone"], "non-finite")
        if x["cap1"][2] > 0 and x["mass"] <= 0: err("ragdoll body", x["bone"], "mass", x["mass"])
        for cap in (x["cap1"], x["cap2"]):
            if cap[2] > 0 and cap[2] < 0.005: err("capsule", x["bone"], "radius", cap[2])
    if U["bodies"] and U["bodies"][0]["cap1"][2] <= 0: err(name, "root bone has no ragdoll capsule")
    # IK rule: a hit capsule on a bone without an ik joint freezes the native hit-IK solver when a blow lands there
    # (hit_fit.ik_safe fixes it)
    hang, _ = ik_hit_bones.analyse(bones, U, hit_only=True)
    if hang: err(name, "ik rule: %d hit bones without an ik joint (native hang): %s" % (len(hang), ", ".join(names[b] for b in sorted(hang)[:8])))
    for j in U["joints"]:
        q = np.array(j["frame"][:4])
        if not finite(j["frame"], j["limits"]): err("joint", j["name"], "non-finite")
        elif abs(np.linalg.norm(q) - 1) > 1e-3: err("joint", j["name"], "frame quaternion not unit", q)
        if j["child"] not in names or j["parent"] not in names: err("joint", j["name"], "bone missing"); continue
        if j["type"] == "d6" and not (bodies[j["child"]]["cap1"][2] > 0 and bodies[j["parent"]]["cap1"][2] > 0):
            err("d6 joint", j["name"], "between bones without ragdoll bodies")
    return errors


def find_skeletons(roots):
    """{skeleton name: (guid, bones, user data, path)} of the skeleton packages under the folders (later roots win)."""
    out = {}
    for root in roots:
        if root and os.path.isdir(root):
            for p in ik_hit_bones.find_skeleton_packages(root):
                try: name, guid, bones, U = sdk_skeleton.read_skeleton(p)
                except Exception: continue
                out[name] = (guid, bones, U, p)
    return out


def native_skeletons():
    """The three skeletons Native ships (human, horse, camel): {name: (guid, bones)}."""
    out = {}
    for nm in sdk_skeleton.NATIVE_SKELETONS:
        try:
            x = sdk_skeleton.native(nm); out[nm] = (x["guid"], sdk_skeleton.parse_definition(x[sdk_skeleton.SKEL_DEF])[1])
        except Exception: pass
    return out


# ------------------------------------------------------------------------------------------------------------------ clips
def validate_clip_file(path, ids, takes=None, rdc=None, nbones=None):
    """Checks of one clip package. takes = {animation guid: (name, rot, root, h1)} of staged animations; rdc = {PACKAGE GUID: path}."""
    errors, err = _errs()
    cn, r, b = clip_record(path); f = r["fixed"]
    if len(cn) > 63: err("clip", cn, "name is %d characters (engine buffer: 63 max)" % len(cn))
    if r["anim2"] and r["anim2"].decode() != cn: err("clip", cn, "paired with another clip", r["anim2"].decode())
    dur = struct.unpack_from("<f", f, 12)[0]; s, e = struct.unpack_from("<ff", f, 16)
    params = struct.unpack_from("<3f", f, 24); steps = struct.unpack_from("<4f", f, 56)
    guid = bytes(f[40:56])
    if not (finite(dur) and dur > 0.01): err("clip", cn, "duration", dur)
    if not finite(s, e) or e - s < 1: err("clip", cn, "source range", s, e)
    if not finite(params): err("clip", cn, "param floats", params)
    if any(not (x == -1 or 0 <= x <= 1) for x in steps): err("clip", cn, "step points", steps)
    bl = struct.unpack_from("<2f", r["blend"], 0)
    if not finite(bl) or min(bl) < 0: err("clip", cn, "blend", bl)
    cid = r["combat"].decode()
    if cid and ids is not None and cid not in ids: err("clip", cn, "unknown combat parameter", cid)
    ik = mov_ik(r["lists"])
    if ik is not None and (not finite(ik) or ik[1] < 0 or any(not 0 <= x <= 1 for x in ik[2:])): err("clip", cn, "bip_mov_ik", ik)
    if takes is None: return errors
    if guid not in takes:
        errors.append("WARN clip %s: animation not in the stage (range and cache checks skipped)" % cn); return errors
    tn, rot, root, ahash = takes[guid]; last = max(float(t[-1]) for t, v in rot if len(t))
    if e > last + 1e-3 or s < 0: err("clip", cn, "range", s, e, "beyond animation keys 0..%g" % last)
    if rdc is None: return errors
    pk = str(uuid.UUID(bytes_le=b[8:24])).upper()
    if pk not in rdc: err("clip", cn, "no cache"); return errors
    ents = [x for x in tpac.read_rdc(rdc[pk]) if x["type"] == tpac.OPT_ANIM]
    if len(ents) != 1: err("clip", cn, "cache entries", len(ents)); return errors
    x = ents[0]
    if x["h1"] != ahash: err("cache", cn, "built from another copy of the animation (stale: rebuild the cache from the stage)")
    v = tpac.lz4_decompress(x["blob"], x["raw"]) if x["stored"] < x["raw"] else x["blob"]
    import tw_formats
    Lo = tw_formats.optanim_layout(v)
    if Lo["trailer"] != Lo["size_in_bytes"] or Lo["consumed"] != Lo["length"]:
        err("cache", cn, "size_in_bytes trailer %d, engine rule %d (blob + 50 x bones + 90)" % (Lo["trailer"], Lo["size_in_bytes"]))
    o = tpac.parse_optanim(v); q, rt = tpac.optanim_values(o)
    Q = np.array(list(q.values()))
    if not finite(Q) or not finite(list(rt.values())): err("cache", cn, "non-finite"); return errors
    if len(Q) and np.abs(np.linalg.norm(Q, axis=1) - 1).max() > 1e-2: err("cache", cn, "non-unit quaternion")
    if nbones and len(o["bones"]) != nbones: err("cache", cn, "bones", len(o["bones"]), "!= skeleton", nbones)
    return errors


def balance_actions(native_set="as_human_warrior"):
    """Action types whose clip must be in the engine's clip balance table: every melee release / quick release / blocked /
    quick blocked action (not ranged or thrown) and every action whose Native clip has a paired animation."""
    import clip_partners as CP
    nsets = CP.sets_of(os.path.join(config.NATIVE_DATA, "action_sets.xml"))
    melee = re.compile(r"^act_(quick_)?(release|blocked)_"); ranged = re.compile(r"bow|crossbow|musket|pistol|sling|throw|javelin|stone|knife|axe_t")
    out = set()
    for t, cn in CP.expanded(nsets, native_set).items():
        if melee.match(t) and not ranged.search(t): out.add(t); continue
        try:
            if tpac.native_clip(cn)["anim2"]: out.add(t)
        except KeyError: pass
    return out


def validate_balance(set_files, clip_dirs):
    import clip_partners as CP
    errors, err = _errs()
    bal = balance_actions(); idx = CP.clip_index(clip_dirs); nsets = CP.sets_of(os.path.join(config.NATIVE_DATA, "action_sets.xml")); recs = {}
    for f in set_files:
        for st in ET.parse(f).getroot():
            if st.get("id") in nsets: continue
            for a in st.findall("action"):
                if a.get("type") not in bal: continue
                cn = a.get("animation")
                if cn not in recs: recs[cn] = clip_record(idx[cn])[1]["anim2"].decode() if cn in idx else None
                if recs[cn] is not None and recs[cn] != cn: err("balance table: action", a.get("type"), "in", st.get("id"), "plays", cn, "paired with", repr(recs[cn]))
    return errors


# ------------------------------------------------------------------------------------------------------------------ stage
def validate(stage, set_files=(), models=None, bones=None):
    """A stage folder (Assets, RuntimeDataCache). Returns a list of problem strings; entries starting with WARN are advisories."""
    S = stage if os.path.isdir(stage) else os.path.join(config.SDK_STAGE_DIR, stage)
    A, R = os.path.join(S, "Assets"), os.path.join(S, "RuntimeDataCache")
    os.environ["TPAC_STAGE"] = A
    errors, err = _errs()
    skels = find_skeletons([config.ASSETS, A])
    by_guid = {v[0]: (k, len(v[1])) for k, v in skels.items()}
    for k, (g, b) in native_skeletons().items(): by_guid.setdefault(g, (k, len(b)))
    staged = find_skeletons([A])
    for name, (guid, bn, U, p) in staged.items():
        errors += validate_skeleton(name, bn, U)
    nb_default = bones or (len(next(iter(staged.values()))[1]) if len(staged) == 1 else MAX_BONES)
    # meshes
    for p in glob.glob(os.path.join(A, "*_geo.tpac")):
        if sdk_mesh.META_TYPE not in tpac._metadata(p): continue
        try: subs = sdk_mesh.read_mesh(p, R)
        except Exception as ex: err("mesh", os.path.basename(p), ex); continue
        for snm, E, tris, St in subs:
            if St is None: err("mesh", snm, "no vertex stream")
            if not finite(E["P"]): err("mesh", snm, "non-finite positions")
            W = E.get("W")
            if W is not None and len(W):
                s = W["w"].sum(1)
                if np.abs(s - 1).max() > 1e-3: err("mesh", snm, "weights do not sum to 1 (max err %.4f)" % np.abs(s - 1).max())
                if int(W["b"].max()) >= nb_default: err("mesh", snm, "bone index", int(W["b"].max()), ">= bones", nb_default)
    # animations
    takes = {}
    for p in glob.glob(os.path.join(A, "*_geo.tpac")):
        if tpac.ANIM_TYPE not in tpac._metadata(p): continue
        for r in sdk_mesh.walk(open(p, "rb").read()):
            if r["type"] != tpac.ANIM_TYPE: continue
            for e in r["ents"]:
                if e["type"] != tpac.ANIM_DATA: continue
                an, rot, root = tpac.decode_anim_blob(e["blob"]); takes[r["guid"]] = (r["name"], rot, root, struct.pack("<Q", tpac.xxh64(e["blob"])))
                # animation record: u64 size, u32 1, import source guid, u8 0, owner skeleton guid, u32 bones, u32 keys, u32 0
                own = bytes(r["rec"][29:45])
                if own == bytes(16): err("anim", r["name"], "owner skeleton not set (python tpac.py owner <file>)")
                elif own in by_guid:
                    if len(rot) != by_guid[own][1]: err("anim", r["name"], "bones", len(rot), "!= owner skeleton", by_guid[own][0], by_guid[own][1])
                else: errors.append("WARN anim %s: owner skeleton %s is neither staged, installed nor Native" % (r["name"], own.hex()))
                for bi, (t, v) in enumerate(rot):
                    if not finite(t, v): err("anim", r["name"], "bone", bi, "non-finite"); break
                    if len(t) and (np.diff(t) <= 0).any(): err("anim", r["name"], "bone", bi, "key times not increasing"); break
                    if len(v) and np.abs(np.linalg.norm(v, axis=1) - 1).max() > 1e-3: err("anim", r["name"], "bone", bi, "non-unit quaternion"); break
                if not finite(*root): err("anim", r["name"], "root non-finite")
                if len(r["name"]) > 63: err("anim", r["name"], "name longer than 63 characters")
    # clips + caches
    ids = combat_ids() if os.path.isdir(config.NATIVE_DATA) else None
    rdc = {os.path.basename(p)[:-4].upper(): p for p in glob.glob(os.path.join(R, "*.rdc"))}
    n = 0
    for p in sorted(glob.glob(os.path.join(A, "*_anm.tpac"))):
        n += 1
        errors += validate_clip_file(p, ids, takes, rdc, nb_default if len(staged) == 1 else None)
    if set_files:
        import clip_partners as CP
        errors += CP.stage_problems(set_files, [A, config.ASSETS], models)[:40]
        errors += validate_balance(set_files, [A, config.ASSETS])
    mb = os.path.join(S, "ModuleData", "project.mbproj")
    if os.path.exists(mb):
        errors += validate_registration(mb, [os.path.join(S, "ModuleData"), config.MODULE_DATA])
    hard = [e for e in errors if not e.startswith("WARN")]
    print("%s: %d skeletons, %d takes, %d clips checked, %d problems, %d advisories" % (
        os.path.basename(S), len(staged), len(takes), n, len(hard), len(errors) - len(hard)))
    return errors


# ----------------------------------------------------------------------------------------------------------- registration
# The engine builds each kind of its XML from MBObjectManager.GetMergedXmlForNative("<fixed id>"): only project.mbproj entries
# whose id is one Native uses are ever merged, so a file under a made-up id (my_mod_action_sets ...) is never loaded and
# whatever points at it (a monster naming its action set or usage set) hands the engine an object that does not exist.
OFFICIAL_MODULES = ("Native", "NavalDLC", "SandBoxCore", "SandBox", "StoryMode", "CustomBattle", "Multiplayer")


def canonical_ids():
    """{project.mbproj id: file type} of Native and the other official modules: the only ids the engine asks for."""
    out = {}
    for m in OFFICIAL_MODULES:
        p = os.path.join(config.MODULES, m, "ModuleData", "project.mbproj")
        if not os.path.exists(p): continue
        for f in ET.parse(p).getroot().iter("file"):
            out.setdefault(f.get("id"), f.get("type"))
    return out


def validate_registration(mbproj, search_dirs=()):
    """Every <file> of a module's project.mbproj: canonical id, the type Native uses for it, an existing file, no duplicates,
    one skin file per module (the engine reads one)."""
    errors, err = _errs()
    canon = canonical_ids(); seen = set(); skins = 0
    dirs = [os.path.dirname(os.path.dirname(mbproj))] + list(search_dirs)
    for f in ET.parse(mbproj).getroot().iter("file"):
        i, n, ty = f.get("id"), f.get("name"), f.get("type")
        if i not in canon: err("project.mbproj: id", repr(i), "(%s) is not an id Native registers: the engine never merges it (%s)" % (n, ", ".join(sorted(canon)[:6]) + " ..."))
        elif canon[i] != ty: err("project.mbproj: id", i, "type", repr(ty), "but Native registers type", repr(canon[i]))
        if (i, n) in seen: err("project.mbproj: duplicate entry", i, n)
        seen.add((i, n)); skins += i == "soln_skins"
        if not any(os.path.exists(os.path.join(d, n)) for d in dirs): err("project.mbproj: file", n, "does not exist (the native loader crashes on a missing XML)")
    if skins > 1: err("project.mbproj: %d soln_skins files (the engine reads one skin file per module)" % skins)
    return errors


# ------------------------------------------------------------------------------------------------------------------ monsters
# Monster.cs DeserializeBoneIndex(..., validateHasParentBone: true); the check is compiled out in the shipped game.
PARENT_FIELDS = ["head_look_direction_bone", "thorax_look_direction_bone", "neck_root_bone", "main_hand_bone", "off_hand_bone",
                 "main_hand_item_bone", "off_hand_item_bone", "right_foot_ik_end_effector_bone", "left_foot_ik_end_effector_bone",
                 "right_foot_ik_tip_bone", "left_foot_ik_tip_bone", "body_rotation_reference_bone"]
SLOPE = "bones_to_modify_on_sloping_ground_"
HANG_FIELDS = {"body_rotation_reference_bone"}   # proven in a minidump: the horse adjustment node turns that bone in the space
                                                 # of its PARENT; on a root the parent is -1 and the bone gets a garbage quaternion


def _resolved(mid, mons, depth=0):
    """attributes of a monster with its base_monster chain applied (base first)."""
    m = mons.get(mid)
    if m is None or depth > 10: return {}
    a = dict(_resolved(m.get("base_monster"), mons, depth + 1)) if m.get("base_monster") else {}
    a.update(m.attrib)
    return a


def validate_monsters(monster_files, set_files, skeleton_roots=()):
    """Monster attributes against the skeleton the monster's action set names. Returns (checked, errors, warnings)."""
    mons = {}
    for p in monster_files:
        for m in ET.parse(p).getroot().iter("Monster"):
            if m.get("id"): mons[m.get("id")] = m
    sets = {}
    for p in set_files:
        for a in ET.parse(p).getroot().iter("action_set"):
            if a.get("id") and a.get("skeleton"): sets[a.get("id")] = a.get("skeleton")
    skels = find_skeletons(skeleton_roots)
    errors, warns, seen = [], [], 0
    for mid in sorted(mons):
        a = _resolved(mid, mons); sk = sets.get(a.get("action_set", ""))
        if sk is None or sk not in skels: continue   # a Native skeleton (human, horse, camel) or a set we cannot see
        seen += 1
        _, bones, U, _ = skels[sk]; names = [b["name"] for b in bones]; idx = {n: i for i, n in enumerate(names)}
        fields = [(f, a.get(f)) for f in PARENT_FIELDS if a.get(f)]
        k = 0
        while a.get(SLOPE + str(k)): fields.append((SLOPE + str(k), a.get(SLOPE + str(k)))); k += 1
        for f, bn in fields:
            if bn not in idx:
                if not f.startswith(SLOPE): warns.append("%s: %s=%s is not a bone of %s (engine index -1)" % (mid, f, bn, sk))
                continue   # an unknown slope bone ends the list (count 0, slope adjustment off)
            if bones[idx[bn]]["parent"] < 0:
                (errors if f in HANG_FIELDS else warns).append("%s: %s=%s is the ROOT of %s (no parent)" % (mid, f, bn, sk))
        fb = a.get("fall_blow_damage_bone")
        if fb in idx and idx[fb] >= RIDER_BONES:
            warns.append("%s: fall_blow_damage_bone=%s is bone %d of %s, past the rider's %d bones (the fall bone index is handed to the rider's skeleton unchecked)" % (mid, fb, idx[fb], sk, RIDER_BONES))
        # ragdoll_* bone lists go through the bone -> ragdoll body table without a null check: each needs a ragdoll body
        rag = {x["bone"] for x in U["bodies"] if x["cap1"][2] > 0}
        for k2, v in a.items():
            if k2.startswith("ragdoll_") and re.search(r"_bone_\d+$", k2) and v in names and v not in rag:
                errors.append("%s: %s=%s has no ragdoll body (native crash)" % (mid, k2, v))
        # look-at chain: every bone from head_look_direction_bone up to spine_lower_bone is not the root and has a d6 joint to its parent
        hl, sl = a.get("head_look_direction_bone"), a.get("spine_lower_bone")
        if hl in names and sl in names:
            jt = {(j["child"], j["parent"]) for j in U["joints"] if j["type"] == "d6"}
            i = names.index(hl); chain = []
            while True:
                chain.append(names[i])
                if bones[i]["parent"] < 0: errors.append("%s: look chain %s -> %s reaches the root" % (mid, hl, sl)); break
                if (names[i], names[bones[i]["parent"]]) not in jt: errors.append("%s: look chain has no d6 joint %s <- %s" % (mid, names[i], names[bones[i]["parent"]]))
                if names[i] == sl: break
                i = bones[i]["parent"]
            if sl not in chain: errors.append("%s: spine_lower_bone %s is not an ancestor of %s" % (mid, sl, hl))
        # IK chains walk foot_num_bones_for_ik / hand_num_bones_for_ik bones up from their end effectors; every segment needs a
        # real length (a zero-length helper bone makes the 2-bone solve degenerate) and the chain must not run past the root
        for eff, num in (("right_foot_ik_end_effector_bone", "foot_num_bones_for_ik"), ("left_foot_ik_end_effector_bone", "foot_num_bones_for_ik"),
                         ("main_hand_bone", "hand_num_bones_for_ik"), ("off_hand_bone", "hand_num_bones_for_ik")):
            if a.get(eff) not in idx or not a.get(num): continue
            i = idx[a.get(eff)]
            for _ in range(int(a.get(num)) - 1):
                if bones[i]["parent"] < 0: errors.append("%s: %s chain from %s runs past the root" % (mid, num, a.get(eff))); break
                if np.linalg.norm(bones[i]["o"]) < 0.005: errors.append("%s: %s chain from %s: zero-length bone %s" % (mid, num, a.get(eff), names[i]))
                i = bones[i]["parent"]
        for k2 in ("eye_offset_wrt_head", "first_person_camera_offset_wrt_head"):
            if a.get(k2) and not finite([float(x) for x in a.get(k2).split(",")]): errors.append("%s: %s not finite" % (mid, k2))
        for k2 in ("standing_eye_height", "standing_pelvis_height", "standing_chest_height", "weight"):
            if a.get(k2) and not float(a.get(k2)) > 0: errors.append("%s: %s=%s" % (mid, k2, a.get(k2)))
    return seen, errors, warns


# ------------------------------------------------------------------------------------------------------------------ CLI
def _opts(a, names):
    out = {n: [] for n in names}; rest = []; i = 0
    while i < len(a):
        if a[i] in out: out[a[i]].append(a[i + 1]); i += 2
        else: rest.append(a[i]); i += 1
    return out, rest


def main(a):
    if not a or a[0] in ("-h", "--help"):
        print(open(__file__, encoding="utf-8").read().split("\nimport collections")[0]); return 0 if a else 2
    cmd = a[0]; o, rest = _opts(a[1:], ("--sets", "--model", "--bones", "--stage"))
    config.require_game()
    if cmd == "stage":
        errs = validate(rest[0] if rest else "work", o["--sets"], dict(m.split("=", 1) for m in o["--model"]), int(o["--bones"][0]) if o["--bones"] else None)
        for e in errs[:80]: print("  " + e)
        return 1 if [e for e in errs if not e.startswith("WARN")] else 0
    if cmd == "skeleton":
        bad = 0
        for p in rest:
            name, guid, bones, U = sdk_skeleton.read_skeleton(p); errs = validate_skeleton(name, bones, U)
            print("%s: %d bones, %d problems" % (name, len(bones), len(errs)))
            for e in errs[:40]: print("  " + e)
            bad += len(errs)
        return 1 if bad else 0
    if cmd == "clip":
        ids = combat_ids(); bad = 0
        for p in rest:
            errs = [e for e in validate_clip_file(p, ids) if not e.startswith("WARN")]; bad += len(errs)
            for e in errs: print("  " + e)
        print("%d clips, %d problems" % (len(rest), bad)); return 1 if bad else 0
    if cmd == "registration":
        errs = validate_registration(rest[0], rest[1:])
        for e in errs[:80]: print("  " + e)
        print("%d problems" % len(errs)); return 1 if errs else 0
    if cmd == "monsters":
        roots = o["--stage"] + [config.ASSETS]
        sets = o["--sets"] + [os.path.join(config.NATIVE_DATA, "action_sets.xml")] + [os.path.join(config.MODULE_DATA, "action_sets.xml")]
        n, errors, warns = validate_monsters(rest, [s for s in sets if os.path.exists(s)], roots)
        for w in warns: print("warning:", w)
        for e in errors: print("ERROR:", e)
        print("%d monsters on custom skeletons checked, %d errors, %d warnings" % (n, len(errors), len(warns))); return 1 if errors else 0
    print("unknown command", cmd); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
