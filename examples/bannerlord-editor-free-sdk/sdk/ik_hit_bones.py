"""Hit bones that freeze the game (a native hang found in a minidump; see knowledge/techniques/bannerlord-native-crashes-and-hangs.md).

A blow that plays no hit-reaction action makes the engine start a type-5 IK chain (an inverse-kinematics anim node) on
Blow.BoneIndex. It first walks up past bones whose body part is none / shoulder / arm. The IK solver then walks from the
last chain bone that has a joint (bone +0x110) up to the next one; when the end bone has no joint that start is -1,
parent[-1] is -1 again, and an anim worker thread loops forever while the main thread spins in parallel_for. Native
human bones are never like that; a custom skeleton with hit capsules on jaws, toes, capes or panels whose parent has a
joint is.

  python ik_hit_bones.py check [tpac ...]    list the hang bones (exit 1 when any); default: the skeleton packages of the
                                             module's Assets folder. Only bones WITH a hit capsule count (--all-bones:
                                             every bone, what the table holds)
  python ik_hit_bones.py table [tpac ...] --out FILE
                                             write "<skeleton> <bone>><safe ancestor> ..." (bone indices) for a runtime guard
                                             in your own C# module that moves the blow's bone to the safe ancestor right
                                             before the native call (the guard itself is not part of this SDK)
  python ik_hit_bones.py --stage DIR         read the skeleton packages under DIR instead of the module
"""
import sys, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402
import sdk_skeleton as s  # noqa: E402

CHAIN = 8  # the engine's chain length for this IK
# BoneBodyPartType: none -1, head 0, neck 1, chest 2, abdomen 3, shoulder_left 4, shoulder_right 5, arm_left 6,
# arm_right 7, legs 8. The engine moves up past -1 and 4..7.
SKIP = {"", "none", "shoulder_left", "shoulder_right", "arm_left", "arm_right"}


def analyse(bones, ud, hit_only=False):
    """{hit bone index: safe target index or -1} for every bone the engine could hang on.
    hit_only: only bones that HAVE a hit capsule (the second capsule of the body, radius > 0): the only bones a blow can name. The guard table
    is written with every bone (a superset: a bone without a capsule is never hit), the data rule (hit_fit.ik_safe, validate.py) and `check` use hit_only."""
    names = [b["name"] for b in bones]
    par = [b["parent"] for b in bones]
    idx = {n: i for i, n in enumerate(names)}
    ik = {idx[j["child"]] for j in ud["joints"] if j["type"] == "ik" and j["child"] in idx}
    joint = {idx[j["child"]] for j in ud["joints"] if j["child"] in idx}  # +0x110 may be any joint: count all as constrained
    group = {idx[b["bone"]]: (b.get("group") or "") for b in ud["bodies"] if b["bone"] in idx}
    hit = {idx[b["bone"]] for b in ud["bodies"] if b["bone"] in idx and b["cap2"][2] > 0}

    def start(b):  # the bone the IK is put on
        while b >= 0 and group.get(b, "") in SKIP:
            b = par[b]
        return b

    def safe(b):
        j = start(b)
        if j < 0 or j in ik:
            return True
        k, n = par[j], 1
        while k >= 0 and n < CHAIN:
            if k in joint:
                return False
            k, n = par[k], n + 1
        return True

    # +0x110 is most likely the ik joint only (the d6 joints build the ragdoll): a target must have an ik joint.
    # Bones that are unsafe only if d6 joints counted too and have no ik ancestor (Warrior, Terramorphous,
    # tentacles: skeletons without ik joints) keep their bone: there is no better target and -1 would drop the hit.
    out = {}
    for b in range(len(names)):
        if (hit_only and b not in hit) or safe(b):
            continue
        t = par[b]
        while t >= 0 and not (safe(t) and start(t) >= 0 and start(t) in ik):
            t = par[t]
        if t >= 0:
            out[b] = t
    return out, names


def find_skeleton_packages(root):
    """Skeleton packages (any *_geo.tpac whose metadata holds a skeleton resource) under a folder."""
    out = []
    for p in glob.glob(os.path.join(root, "**", "*_geo.tpac"), recursive=True):
        if s.SKEL_TYPE in tpac_meta(p): out.append(p)
    return out


def tpac_meta(path):
    import tpac
    return tpac._metadata(path)


def skeletons(paths):
    for p in sorted(paths):
        try:
            r = s.read_skeleton(p)
        except Exception as e:  # not a skeleton package
            print("skip", os.path.basename(p), e)
            continue
        yield p, r[0], r[2], r[3]


def main(argv):
    mode = argv[0] if argv[:1] in (["check"], ["table"]) else "check"
    if argv[:1] in (["check"], ["table"]):
        argv = argv[1:]
    if "-h" in argv or "--help" in argv:
        print(__doc__); return 0
    all_bones = "--all-bones" in argv
    argv = [a for a in argv if a != "--all-bones"]
    out = stage = None
    for flag in ("--out", "--stage"):
        if flag in argv:
            i = argv.index(flag); val = argv[i + 1]; del argv[i:i + 2]
            if flag == "--out": out = val
            else: stage = val
    if argv:
        paths = argv
    else:
        roots = [stage] if stage else [config.ASSETS, os.path.join(config.MODULE, "AssetsLoose")]
        paths = [p for r in roots if os.path.isdir(r) for p in find_skeleton_packages(r)]
    if not paths:
        print("no skeleton packages found (pass package paths, --stage DIR, or set BANNERLORD_MODULE_DIR)")
        return 2
    lines, total = [], 0
    for p, name, bones, ud in skeletons(paths):
        m, names = analyse(bones, ud, hit_only=(mode == "check" and not all_bones))
        total += len(m)
        print("%-40s %3d bones, %2d hang bones%s" % (name, len(bones), len(m),
              (": " + ", ".join("%s->%s" % (names[a], names[b] if b >= 0 else "none") for a, b in sorted(m.items()))) if m else ""))
        if m:
            lines.append(name + " " + " ".join("%d>%d" % (a, b) for a, b in sorted(m.items())))
    print("total hang bones:", total)
    if mode == "check":
        return 1 if total else 0
    if not out:
        print("table needs --out FILE")
        return 2
    with open(out, "w", newline="\n") as f:
        f.write("# generated by ik_hit_bones.py from %s\n" % (stage or "the module's skeleton packages"))
        f.write("# <skeleton> <hit bone>><safe ancestor> ... : a blow on the left bone is moved to the right one (native IK hang)\n")
        for l in lines:
            f.write(l + "\n")
    print("wrote", os.path.normpath(out), len(lines), "skeletons")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
