# Hit (collision) capsule fitting for a custom skeleton. A first, naive fit (the MEDIAN distance of a bone's skinned vertices
# over 0.1 to 0.9 of the bone, only on bones with > 30 vertices) left about half of a mesh outside every capsule, so shots at
# the visible creature passed through it. This fit covers the mesh instead.
# refit(bones, phys, subs) is called on the finished user data dict just before it is written; it only touches the SECOND capsule (the hit volume), the body part of a bone
# that had none, and `extra`; the ragdoll capsule (first), types, masses, joints stay as the pipeline made them.
#   radius  = PCT-th percentile of the distance of the bone's vertices to its segment, clipped to [R_MIN, rmax(bone)]
#   segment = the whole bone, a little past both ends (END), so the joints and the tips are covered too
#   which   = every bone that had a hit capsule, plus every bone with >= MIN_VERTS dominant vertices and a bone vector of >= MIN_LEN m (its body part: the nearest ancestor's)
import numpy as np
import sdk_skeleton
import ik_hit_bones

PCT = 92.0           # percentile of the vertex distances (was the median, 50)
END = 0.08           # the capsule runs from -END to 1 + END of the bone vector (was 0.1 to 0.9)
MIN_VERTS = 12       # dominant vertices for a bone that had no hit capsule to get one (was: > 30, creature path only)
MIN_LEN = 0.03       # shortest bone vector that gets a new capsule, metres (was 0.08)
R_MIN = 0.03
BLOB = 0.15          # max radius as a fraction of the body's bounding box diagonal (no huge overlapping blobs)
GAP = 0.10          # second pass: a bone with more than this fraction of its own vertices uncovered ...
GAP_PCT = 97.0      # ... gets a radius up to this percentile of them (capped at BLOB x diagonal)
LEN_K = 1.5          # ... and as a multiple of the bone's own length (+ R_MIN)
FLOOR = 0.90         # ik_safe: the body keeps at least this fraction of its vertices in a hit capsule (or its coverage before minus FLOOR_DROP, if lower)
FLOOR_DROP = 0.03
MAX_EXT = 1.0        # ik_safe: an absorbing capsule is stretched at most this many bone lengths past either end


def refit(bones, phys, subs, pct=PCT, end=END, min_verts=MIN_VERTS, min_len=MIN_LEN, blob=BLOB):
    names = [b["name"] for b in bones]; idx = {n: i for i, n in enumerate(names)}
    W = sdk_skeleton.world_frames(bones)
    P = np.concatenate([np.asarray(s["P"], float)[:, :3] for s in subs if s.get("W") is not None])
    Wt = np.concatenate([s["W"] for s in subs if s.get("W") is not None])
    dom = Wt["b"][:, 0].astype(int); strong = Wt["w"][:, 0] > 0.5
    diag = float(np.linalg.norm(P.max(0) - P.min(0)))
    kids = {}
    for i, b in enumerate(bones):
        if b["parent"] >= 0: kids.setdefault(b["parent"], []).append(i)
    count = np.bincount(dom[strong], minlength=len(bones))
    sub_count = count.astype(float).copy()            # vertices of the bone and everything below it
    for i in range(len(bones) - 1, -1, -1):
        if bones[i]["parent"] >= 0: sub_count[bones[i]["parent"]] += sub_count[i]
    by = {b["bone"]: b for b in phys["bodies"]}
    def group_of(i):                                   # the body part of the nearest ancestor that has a real one
        while i >= 0:
            b = by.get(names[i])
            if b and b["group"] not in ("", "none"): return b["group"]
            i = bones[i]["parent"]
        return "chest"
    fitted = {}   # bone index -> (segment a, segment d, own vertices, the radius cap used)
    for bd in phys["bodies"]:
        i = idx.get(bd["bone"])
        if i is None: continue
        had = bd["cap2"][2] > 0
        sel = (dom == i) & strong; v = P[sel]
        R, o = W[i]
        # the segment (bone space) = the whole bone, a little past both ends: from the capsule the pipeline made (0.1 to 0.9 of the bone vector, 0 to 1 on an end bone, or a
        # free fit along the vertices), else along the main child, else to twice the vertex centroid
        s1 = s2 = None
        for cap in (bd["cap2"], bd["cap1"]):
            if cap[2] <= 0: continue
            q1, q2 = np.asarray(cap[0][:3], float), np.asarray(cap[1][:3], float); dq = q2 - q1; n = float(np.linalg.norm(dq))
            if n < 1e-4: continue
            if np.linalg.norm(q1 - 0.125 * dq) < 0.02 * n + 1e-6: c = dq / 0.8; s1, s2 = -end * c, (1.0 + end) * c
            elif np.linalg.norm(q1) < 1e-6: s1, s2 = -end * q2, (1.0 + end) * q2
            else: s1, s2 = q1 - 0.3 * dq, q2 + 0.3 * dq
            break
        if s1 is None:
            ch = [k for k in kids.get(i, []) if np.linalg.norm(bones[k]["o"]) > 1e-3]
            if ch: c = np.asarray(bones[max(ch, key=lambda k: (sub_count[k], np.linalg.norm(bones[k]["o"])))]["o"], float)
            elif len(v): c = R.T @ (v.mean(0) - o) * 2.0
            else: continue
            s1, s2 = -end * c, (1.0 + end) * c
        length = float(np.linalg.norm(s2 - s1)) / (1.0 + 2 * end)
        if not had and (len(v) < min_verts or length < min_len): continue
        if len(v) == 0: continue
        a = o + R @ s1; b = o + R @ s2; d = b - a
        t = np.clip(((v - a) @ d) / max(float(d @ d), 1e-12), 0, 1)
        dist = np.linalg.norm(v - (a + t[:, None] * d), axis=1)
        rmax = max(R_MIN * 2, min(blob * diag, LEN_K * length + R_MIN))
        r = float(np.clip(np.percentile(dist, pct), R_MIN, rmax))
        bd["cap2"] = ((*s1, 1.0), (*s2, 1.0), r)
        bd["extra"] = max(bd["extra"], r * 1.4)
        if bd["group"] in ("", "none"): bd["group"] = group_of(i)
        fitted[i] = (a, d, sel, bd)
    # second pass, close the gaps: a bone whose own vertices are still > GAP outside every capsule (a flat plate or a fat torso on a short bone, a claw on an end bone) gets its
    # radius raised to the GAP_PCT-th percentile, at most the body-size cap (blob x diagonal)
    inside = np.zeros(len(P), bool)
    def hit_mask(a, d, r):
        t = np.clip(((P - a) @ d) / max(float(d @ d), 1e-12), 0, 1)
        return np.linalg.norm(P - (a + t[:, None] * d), axis=1) <= r
    for i, (a, d, sel, bd) in fitted.items(): inside |= hit_mask(a, d, bd["cap2"][2])
    for i, (a, d, sel, bd) in sorted(fitted.items(), key=lambda kv: -int((kv[1][2] & ~inside).sum())):
        own = int(sel.sum()); miss = int((sel & ~inside).sum())
        if own < min_verts or miss < GAP * own or miss < 6: continue
        v = P[sel]; t = np.clip(((v - a) @ d) / max(float(d @ d), 1e-12), 0, 1)
        dist = np.linalg.norm(v - (a + t[:, None] * d), axis=1)
        r = float(np.clip(np.percentile(dist, GAP_PCT), bd["cap2"][2], max(bd["cap2"][2], blob * diag)))
        if r <= bd["cap2"][2] * 1.01: continue
        bd["cap2"] = (bd["cap2"][0], bd["cap2"][1], r); bd["extra"] = max(bd["extra"], r * 1.4)
        inside |= hit_mask(a, d, r)
    ik_safe(bones, phys, P, dom, strong, diag, W, pct=pct, blob=blob)
    return phys


def _seg_dist(P, a, d):
    t = np.clip(((P - a) @ d) / max(float(d @ d), 1e-12), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * d), axis=1)


def ik_safe(bones, phys, P, dom, strong, diag, W, pct=PCT, blob=BLOB, floor=FLOOR):
    """The IK rule. Every bone with a hit capsule that ik_hit_bones.analyse(hit_only=True) calls a hang bone:
       1. loses its hit capsule (cap2 radius -1, extra -1: the form of a body without one);
       2. its vertices that fell out of every capsule go to the nearest ancestor that still has a hit capsule: that capsule is stretched along its bone (at most MAX_EXT bone
          lengths past either end) and widened to the pct-th percentile of the vertices it now holds (at most blob x diagonal);
       3. while the body is under the coverage floor, the bone with the most lost vertices gets its capsule back and the body part arm_left / arm_right (also on every
          ancestor up to the first one with an ik joint): the engine's hit IK walks up past arm bones, so its start is that ancestor.
    Raises when the result still has hang bones. Returns {bone name: 'removed' | 'arm'}."""
    names = [b["name"] for b in bones]; idx = {n: i for i, n in enumerate(names)}; par = [b["parent"] for b in bones]
    by = {b["bone"]: b for b in phys["bodies"]}
    m, _ = ik_hit_bones.analyse(bones, phys, hit_only=True)
    if not m: return {}
    ik = {idx[j["child"]] for j in phys["joints"] if j["type"] == "ik" and j["child"] in idx}
    NONE = ((0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.0), -1.0)

    def world(i, cap):
        R, o = W[i]; return o + R @ np.asarray(cap[0][:3], float), R @ (np.asarray(cap[1][:3], float) - np.asarray(cap[0][:3], float))

    def live(i):
        return by[names[i]]["cap2"][2] > 0

    def union(skip=()):
        u = np.zeros(len(P), bool)
        for bd in phys["bodies"]:
            i = idx.get(bd["bone"])
            if i is None or i in skip or bd["cap2"][2] <= 0: continue
            a, d = world(i, bd["cap2"]); u |= _seg_dist(P, a, d) <= bd["cap2"][2]
        return u

    R_ = sorted(m)
    cov0_mask = union(); cov0 = float(cov0_mask.mean())
    orig = {i: (by[names[i]]["cap2"], by[names[i]]["extra"], by[names[i]]["group"]) for i in R_}
    dist0 = {}   # distance to each removed capsule, minus its radius
    for i in R_:
        a, d = world(i, orig[i][0]); dist0[i] = _seg_dist(P, a, d) - orig[i][0][2]
    for i in R_:
        by[names[i]]["cap2"] = NONE; by[names[i]]["extra"] = -1.0
    inside = union()
    lost = ~inside & cov0_mask
    # each lost vertex belongs to the removed capsule it was deepest in
    owner = np.full(len(P), -1)
    best = np.full(len(P), np.inf)
    for i in R_:
        better = lost & (dist0[i] <= 0) & (dist0[i] < best); owner[better] = i; best[better] = dist0[i][better]
    # absorber of each removed bone: the nearest ancestor that is not removed and has a hit capsule
    absorber = {}
    for i in R_:
        k = par[i]
        while k >= 0 and not (live(k) and k not in m): k = par[k]
        absorber[i] = k if k >= 0 else None
    def absorb(t, own_idx):
        V = P[np.isin(owner, own_idx)]
        if not len(V): return
        bd = by[names[t]]; s1 = np.asarray(bd["cap2"][0][:3], float); s2 = np.asarray(bd["cap2"][1][:3], float)
        a, d = world(t, bd["cap2"]); L = float(d @ d)
        if L < 1e-10: return
        tt = ((V - a) @ d) / L
        lo = max(min(0.0, float(np.percentile(tt, 2))), -MAX_EXT); hi = min(max(1.0, float(np.percentile(tt, 98))), 1.0 + MAX_EXT)
        n1, n2 = s1 + lo * (s2 - s1), s1 + hi * (s2 - s1)
        R, o = W[t]; na = o + R @ n1; nd = R @ (n2 - n1)
        pts = np.concatenate([V, P[(dom == t) & strong]])
        r0 = bd["cap2"][2]
        r = float(np.clip(np.percentile(_seg_dist(pts, na, nd), pct), r0, max(r0, min(blob * diag, LEN_K * float(np.linalg.norm(nd)) + R_MIN))))
        bd["cap2"] = ((*n1, 1.0), (*n2, 1.0), r); bd["extra"] = max(bd["extra"], r * 1.4)
    groups = {}
    for i in R_: groups.setdefault(absorber[i], []).append(i)
    for t, own in groups.items():
        if t is not None: absorb(t, own)
    inside = union(); cov = float(inside.mean())
    target = min(cov0, max(floor, cov0 - FLOOR_DROP))
    result = {names[i]: "removed" for i in R_}
    def side(i):
        n = names[i]
        if n[:1] in "lL": return "arm_left"
        if n[:1] in "rR": return "arm_right"
        return "arm_left" if W[i][1][0] < 0 else "arm_right"
    while cov < target:
        cand = [i for i in R_ if result[names[i]] == "removed" and int(((owner == i) & ~inside).sum()) > 0]
        if not cand: break
        i = max(cand, key=lambda k: int(((owner == k) & ~inside).sum()))
        bd = by[names[i]]; bd["cap2"], bd["extra"] = orig[i][0], orig[i][1]; result[names[i]] = "arm"
        k = i
        while k >= 0 and k not in ik:
            g = by[names[k]]
            if g["group"] not in ik_hit_bones.SKIP: g["group"] = side(i)
            k = par[k]
        inside = union(); cov = float(inside.mean())
    left, _ = ik_hit_bones.analyse(bones, phys, hit_only=True)
    if left: raise RuntimeError("hit_fit.ik_safe: %d hang bones left: %s" % (len(left), ", ".join(names[b] for b in sorted(left))))
    return result
