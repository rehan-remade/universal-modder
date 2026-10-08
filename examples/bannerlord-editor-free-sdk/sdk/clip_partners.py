# Clip partner check: does every clip of your action sets keep the action reference its Native counterpart has?
#   python clip_partners.py check [--sets FILE ...] [--clips DIR ...] [--model SET=NATIVE_SET ...] [--list N]
#       --sets   action_sets.xml files to check (default: <module>/ModuleData/action_sets.xml); later files win by set id
#       --clips  folders holding <clip>_anm.tpac, searched in order (staged folders first, then the module's Assets)
#       --model  which Native set a set of yours is modelled on (as_mything=as_human_warrior). Without it the base_set
#                chain is followed to a Native set; a quadrupedal set falls back to as_camel.
#       --list N print the first N problems
#   python clip_partners.py native                       rebuild the cache of Native's clip partners (reads package metadata only)
#   python clip_partners.py clip <clip name> [--clips DIR ...]   one clip's blends_with / continue_with (yours, then Native)
#
# Format: a clip record holds two ACTION names after the facial string: `blends_with` (the partner: the clip's `_up` twin,
# the `_balanced` twin of a release / ready / blocked clip, lance couch, brace) and `continue_with` (follow-up action). The
# engine resolves the name to an action id and, when the request has a blend factor (agent_set_defend_action: 0.5 with ANY
# shield in the off hand), reads that action's clip UNCHECKED: -1 = a heap word used as a clip index = a native crash
# (see knowledge/techniques/bannerlord-native-crashes-and-hangs.md). Rule: never clear it; the target must be an action of
# every set that plays the clip.
# What is checked, for each action of each set (its own actions; a derived set's targets are looked up in the set with its
# base_set chain): when the Native clip of the same action type in the modelled Native set has a blends_with, your clip must
# have one that is an action of the set (problem kinds: no partner / dangling partner). Any blends_with or continue_with your
# clip names must be an action of the set, whatever Native does (dangling). A clip that exists nowhere is reported too.
# Info counters (not problems): your target differs from Native's; a Native follow-up (continue_with) was not copied.
import collections, glob, json, os, re, struct, sys
import xml.etree.ElementTree as ET
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import config, tpac, tw_formats

CACHE = os.path.join(config.SDK_STAGE_DIR, "_cache", "native_clip_partners.json")
MODULE_SETS = os.path.join(config.MODULE_DATA, "action_sets.xml")


def native_partners(rebuild=False):
    """{Native clip name: [blends_with action, continue_with action]} (cached under SDK_STAGE_DIR)."""
    if not rebuild and os.path.exists(CACHE):
        return json.load(open(CACHE))
    config.require_game()
    out = {}
    for p in sorted(glob.glob(os.path.join(config.NATIVE, "EmAssetPackages", "animations", "*", "*.tpac"))):
        for it in tw_formats.read_package_index(p):
            if it["type"] != tpac.CLIP_TYPE:
                continue
            try:
                r = tpac.parse_clip(bytes(it["record"]), 0)
            except Exception:
                continue
            out[it["name"]] = [r["blends_with"].decode(), r["continue_with"].decode()]
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(out, open(CACHE, "w"))
    return out


def sets_of(path):
    return {s.get("id"): s for s in ET.parse(path).getroot()}


def expanded(sets, sid, seen=()):
    """{action type: clip} of a set including its base_set chain (a derived set's own actions win)."""
    s = sets.get(sid); out = {}
    if s is None or sid in seen:
        return out
    if s.get("base_set"):
        out.update(expanded(sets, s.get("base_set"), seen + (sid,)))
    for a in s.findall("action"):
        out[a.get("type")] = a.get("animation")
    return out


def movement(sets, sid, seen=()):
    s = sets.get(sid)
    if s is None or sid in seen:
        return None
    return s.get("movement_system") or (movement(sets, s.get("base_set"), seen + (sid,)) if s.get("base_set") else None)


def native_model(sid, ours, native_sets, models):
    """The Native set a set of yours is modelled on: --model, else the first Native set in its base_set chain,
    else as_camel for a quadrupedal set, else None (only the dangling checks apply)."""
    if sid in models:
        return models[sid]
    k, seen = sid, set()
    while k and k not in seen:
        seen.add(k)
        s = ours.get(k)
        if s is None:
            break
        k = s.get("base_set")
        if k in native_sets:
            return k
    return "as_camel" if movement(ours, sid) == "quadrupedal" and "as_camel" in native_sets else None


def clip_index(dirs):
    """{clip name: path}; the first folder that holds a clip wins."""
    idx = {}
    for d in reversed([d for d in dirs if d and os.path.isdir(d)]):
        for f in os.listdir(d):
            if f.endswith("_anm.tpac"):
                idx[f[:-9]] = os.path.join(d, f)
    return idx


_rec = {}
def record(path):
    if path not in _rec:
        b = open(path, "rb").read(); n = struct.unpack_from("<i", b, 0x48)[0]
        r = tpac.parse_clip(b, 0x4c + n); _rec[path] = (r["blends_with"].decode(), r["continue_with"].decode())
    return _rec[path]


def analyse(set_files, clip_dirs, models=None, show=0):
    """Returns (counters, problems). problems = [(set id, action type, text)]."""
    models = models or {}
    nat = native_partners(); nsets = sets_of(os.path.join(config.NATIVE_DATA, "action_sets.xml"))
    ours = {}
    for f in set_files:
        ours.update(sets_of(f))
    idx = clip_index(clip_dirs)
    st = collections.Counter(); problems = []; nexp = {}
    for sid, s in ours.items():
        if sid in nsets:   # a Native set id (an override or merge): its own clips are Native's
            continue
        acts = s.findall("action")
        if not acts:
            continue
        st["sets"] += 1
        nid = native_model(sid, ours, nsets, models)
        if nid and nid not in nexp:
            nexp[nid] = expanded(nsets, nid)
        nex = nexp.get(nid, {}); ex = expanded(ours, sid)
        for a in acts:
            t, cn = a.get("type"), a.get("animation")
            if cn in idx:
                bw, cw = record(idx[cn]); mine = True
            elif cn in nat:
                bw, cw = nat[cn]; mine = False      # a Native clip: Native's own fields
            else:
                st["clip missing"] += 1; problems.append((sid, t, "clip %s exists nowhere" % cn)); continue
            st["actions"] += 1; st["own clips" if mine else "native clips"] += 1
            nclip = nex.get(t); nb, nc = nat.get(nclip, ["", ""]) if nclip else ("", "")
            if nb:
                st["need partner"] += 1
                if not bw:
                    st["no partner"] += 1; problems.append((sid, t, "no partner (Native %s -> %s); clip %s" % (nclip, nb, cn))); continue
                if bw not in ex:
                    st["dangling partner"] += 1; problems.append((sid, t, "partner %s is not an action of the set; clip %s" % (bw, cn))); continue
                st["partner ok"] += 1
                if bw != nb:
                    st["target differs from Native"] += 1
            elif bw:
                if bw not in ex:
                    st["dangling partner"] += 1; problems.append((sid, t, "partner %s is not an action of the set (Native has none); clip %s" % (bw, cn)))
                else:
                    st["partner where Native has none"] += 1
            if cw and mine and cw not in ex:
                st["dangling follow-up"] += 1; problems.append((sid, t, "follow-up %s is not an action of the set; clip %s" % (cw, cn)))
            elif nc and not cw:
                st["follow-up not copied (info)"] += 1
    return st, problems


PROBLEM_KINDS = ("no partner", "dangling partner", "dangling follow-up", "clip missing")


def check(set_files=None, clip_dirs=None, models=None, show=0):
    set_files = set_files or [MODULE_SETS]
    clip_dirs = clip_dirs or [config.ASSETS]
    missing = [f for f in set_files if not os.path.exists(f)]
    if missing:
        sys.exit("action set file not found: %s (pass --sets FILE)" % missing[0])
    st, problems = analyse(set_files, clip_dirs, models)
    print("sets %d, actions %d (own clips %d, Native clips %d), need partner %d, partner ok %d" % (
        st["sets"], st["actions"], st["own clips"], st["native clips"], st["need partner"], st["partner ok"]))
    print("problems: no partner %d, dangling partner %d, dangling follow-up %d, clip missing %d" % tuple(st[k] for k in PROBLEM_KINDS))
    print("info: target differs from Native %d, partner where Native has none %d, follow-up not copied %d" % (
        st["target differs from Native"], st["partner where Native has none"], st["follow-up not copied (info)"]))
    for sid, t, why in problems[:show]:
        print("  %s %s: %s" % (sid, t, why))
    n = sum(st[k] for k in PROBLEM_KINDS)
    print("%d problems" % n)
    return n


def stage_problems(set_files, clip_dirs, models=None):
    """The same rule as `check`, as a list of strings (validate.py calls it for a stage)."""
    st, problems = analyse(set_files, clip_dirs, models)
    return ["partner: set %s action %s: %s" % p for p in problems]


def main(a):
    if a[:1] == ["check"]:
        opts = {"--sets": [], "--clips": [], "--model": []}; show = 0; i = 1
        while i < len(a):
            if a[i] in opts: opts[a[i]].append(a[i + 1]); i += 2
            elif a[i] == "--list": show = int(a[i + 1]); i += 2
            else: sys.exit("usage: python clip_partners.py check [--sets FILE ...] [--clips DIR ...] [--model SET=NATIVE_SET ...] [--list N]")
        models = dict(m.split("=", 1) for m in opts["--model"])
        return 1 if check(opts["--sets"], opts["--clips"] + [config.ASSETS], models, show) else 0
    if a[:1] == ["native"]:
        d = native_partners(True)
        print(len(d), "Native clips,", sum(1 for v in d.values() if v[0]), "with a partner,", sum(1 for v in d.values() if v[1]), "with a follow-up")
        return 0
    if a[:1] == ["clip"] and len(a) > 1:
        dirs = [a[i + 1] for i in range(len(a) - 1) if a[i] == "--clips"] + [config.ASSETS]
        nat = native_partners(); p = clip_index(dirs).get(a[1])
        if p:
            print("yours", p, record(p))
        if a[1] in nat:
            print("Native", nat[a[1]])
        return 0
    print(open(__file__, encoding="utf-8").read().split(chr(10) + "import collections")[0])
    return 0 if a[:1] in (["-h"], ["--help"]) else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
