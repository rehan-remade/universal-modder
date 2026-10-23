"""Build CB2's P90 world model (GFX/Items/p90_wm.b3d) as Roblox parts in the existing gun space.

The world model is the viewmodel gun's own mesh (same triangle counts per texture) stored with another
vertex order (a vertex-by-vertex fit failed: residual 2.6 units), so the gun is taken from the viewmodel:
  1. the viewmodel's gun brushes (p90, Optic) in its Base bone frame,
  2. the magazine split out by the viewmodel's Mag bone weights (the reload moves it in third person),
  3. express it in gun space as WeaponConfig documents it (-Z down the bore, +Y up, X right), scaled to the
     template's length (2.4776 studs at body scale 1) with the bore on the template's muzzle line, so the
     procedural third-person poses keep fitting,
  4. write one OBJ (objects P90Body, P90Mag, P90Sight) + textures and a points JSON (muzzle, optic, grips).

Usage:
  python -I tools/cb2/wm_build.py out/cb2_p90/p90_vm.json out/cb2_p90/p90_wm.json out/cb2_p90/wm --tex-dir "<CB2>/GFX/Items/Weapons/P90"
"""
import argparse
import json
import math
import os
import shutil

import numpy as np

LENGTH = 2.47763991355896  # template P90Body length (studs, scale 1)
MUZZLE_TEMPLATE = np.array([-0.00313, -0.03565, -1.21736])  # template Muzzle attachment


def quat_conj_matrix(q):
    # Blitz3D applies the conjugate of the stored (w, x, y, z) quaternion.
    w, x, y, z = q[0], -q[1], -q[2], -q[3]
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def local(n):
    m = np.eye(4)
    m[:3, :3] = quat_conj_matrix(n["rot"]) * np.array(n["scale"])
    m[:3, 3] = n["pos"]
    return m


def find(n, name, parent=np.eye(4)):
    w = parent @ local(n)
    if n["name"] == name:
        return n, w
    for c in n["children"]:
        r = find(c, name, w)
        if r:
            return r
    return None


def similarity(src, dst):
    # dst ~ s R src + t (Umeyama)
    ms, md = src.mean(0), dst.mean(0)
    a, b = src - ms, dst - md
    u, sig, vt = np.linalg.svd(b.T @ a)
    d = np.sign(np.linalg.det(u @ vt))
    D = np.diag([1, 1, d])
    r = u @ D @ vt
    s = (sig * np.diag(D)).sum() / (a ** 2).sum()
    return s, r, md - s * r @ ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vm")
    ap.add_argument("wm")
    ap.add_argument("out")
    ap.add_argument("--tex-dir", required=True)
    a = ap.parse_args()
    vm = json.load(open(a.vm, encoding="utf-8"))
    wm = json.load(open(a.wm, encoding="utf-8"))
    os.makedirs(a.out, exist_ok=True)

    vroot = vm["root"]
    vmesh = vroot["mesh"]
    _, base_w = find(vroot, "Base")
    base_inv = np.linalg.inv(base_w)
    vpos = np.array(vmesh["verts"]["pos"])
    vpos_base = (base_inv @ np.c_[vpos, np.ones(len(vpos))].T).T[:, :3]

    def used(mesh, brush_names, data):
        ids = []
        for s in mesh["surfaces"]:
            if data["brus"][s["brush"]]["name"] in brush_names:
                ids += sorted({i for t in s["tris"] for i in t})
        return ids

    # The world model is this same gun mesh (same triangle counts per texture) but stored with another
    # vertex order, so the gun is taken from the viewmodel, in its Base bone frame: exact, and the magazine
    # split comes straight from the Mag bone's weights.
    wm, wmesh = vm, vmesh
    wbase = vpos_base
    mag_node, _ = find(vroot, "Mag")
    mag_v = {vid for vid, w in mag_node.get("bone", []) if w > 0.5}
    is_mag = np.array([i in mag_v for i in range(len(vpos))])
    r = base_inv[:3, :3]
    wmesh = dict(vmesh, surfaces=[s_ for s_ in vmesh["surfaces"] if vm["brus"][s_["brush"]]["name"] in ("p90", "Optic")])

    # Gun space from Base space: bore = towards weaponfire, up = towards the optic.
    fire_node, fire_w = find(vroot, "weaponfire")
    fire_base = (base_inv @ fire_w)[:3, 3]
    optic_ids = used(wmesh, ("Optic",), wm)
    optic_c = wbase[optic_ids].mean(0)
    body_ids = [i for i in used(wmesh, ("p90",), wm) if not is_mag[i]]
    # bore line: through the muzzle point along the gun's long axis (principal axis of the body)
    body = wbase[body_ids]
    _, _, vt = np.linalg.svd(body - body.mean(0))
    fwd = vt[0] if np.dot(vt[0], fire_base - body.mean(0)) > 0 else -vt[0]
    up = optic_c - fire_base
    up = up - fwd * np.dot(up, fwd)
    up /= np.linalg.norm(up)
    # Blitz is left-handed: there the physical right of a viewer facing fwd with up is up x fwd. Gun space
    # is right-handed (X right, Y up, -Z forward), so rot is a reflection (det < 0).
    right = np.cross(up, fwd)
    rot = np.array([right, up, -fwd])  # rows: gun axes in Base space
    g = (rot @ (wbase - fire_base).T).T
    gun_ids = sorted({i for s_ in wmesh["surfaces"] for t_ in s_["tris"] for i in t_})
    length = g[gun_ids, 2].max() - g[gun_ids, 2].min()
    k = LENGTH / length
    g = g * k
    # muzzle tip at the template's muzzle (bore line and z)
    g = g + MUZZLE_TEMPLATE
    print("length %.3f vm units -> %.4f studs/vm unit; bounds" % (length, k), g[gun_ids].min(0).round(3), g[gun_ids].max(0).round(3))

    def to_gun(p):
        return (rot @ (np.asarray(p) - fire_base)) * k + MUZZLE_TEMPLATE

    # Points for WeaponConfig: optic eyepiece/objective along the sight's axis, magazine seat (centroid).
    o = to_gun(optic_c)
    opt = g[optic_ids]
    points = {
        "Muzzle": MUZZLE_TEMPLATE.tolist(),
        "OpticCentre": o.tolist(),
        "OpticRear": [o[0], o[1], float(opt[:, 2].max())],
        "OpticFront": [o[0], o[1], float(opt[:, 2].min())],
        "MagCentre": g[is_mag].mean(0).tolist(),
        "MagBounds": [g[is_mag].min(0).tolist(), g[is_mag].max(0).tolist()],
        "BodyBounds": [g[body_ids].min(0).tolist(), g[body_ids].max(0).tolist()],
        "Scale": k,
    }
    # The sight's optical axis: the glass and the green dot sit on it (viewmodel-only brushes).
    for key, brush in (("GlassCentre", "glass"), ("GreenDot", "green_dot")):
        ids = used(vmesh, (brush,), vm)
        points[key] = to_gun(vpos_base[ids].mean(0)).tolist()
    json.dump(points, open(os.path.join(a.out, "p90_wm.points.json"), "w"), indent=1)
    print(json.dumps(points, indent=1))

    # OBJ: Roblox/OBJ space is right-handed Y-up, which gun space already is.
    uv = wmesh["verts"]["uv"]
    nrm = np.array(wmesh["verts"]["normal"])
    # normals: Blitz -> Base frame (rotation part, mirrored like the positions are by the similarity), -> gun
    n_base = (r @ nrm.T).T
    n_gun = (rot @ n_base.T).T
    tex = {"p90": "p90.png", "Optic": "sight_1.png"}
    for f in tex.values():
        shutil.copy(os.path.join(a.tex_dir, f), os.path.join(a.out, f))
    with open(os.path.join(a.out, "p90_wm.mtl"), "w") as m:
        for name, f in tex.items():
            m.write("newmtl %s\nKd 1 1 1\nmap_Kd %s\n\n" % (name, f))
    # A reflection (Blitz left-handed -> gun space right-handed) reverses each triangle, as in b3d2obj.py.
    flip = np.linalg.det(rot) * np.linalg.det(r) < 0
    with open(os.path.join(a.out, "p90_wm.obj"), "w") as f:
        f.write("mtllib p90_wm.mtl\n")
        for p in g:  # every viewmodel vertex is written (unused ones are harmless) so indices stay
            f.write("v %.6f %.6f %.6f\n" % tuple(p))
        for u in uv:
            f.write("vt %.6f %.6f\n" % (u[0], 1 - u[1]))
        for n in n_gun:
            f.write("vn %.6f %.6f %.6f\n" % tuple(n / (np.linalg.norm(n) or 1)))
        groups = {"P90Body": [], "P90Mag": [], "P90Sight": []}
        for s_ in wmesh["surfaces"]:
            bname = wm["brus"][s_["brush"]]["name"]
            for tri in s_["tris"]:
                if bname == "Optic":
                    groups["P90Sight"].append((bname, tri))
                elif all(is_mag[i] for i in tri):
                    groups["P90Mag"].append((bname, tri))
                else:
                    groups["P90Body"].append((bname, tri))
        for gname, tris in groups.items():
            f.write("o %s\n" % gname)
            last = None
            for bname, tri in tris:
                if bname != last:
                    f.write("usemtl %s\n" % bname)
                    last = bname
                order = (tri[0], tri[2], tri[1]) if flip else tuple(tri)
                f.write("f " + " ".join("%d/%d/%d" % (i + 1, i + 1, i + 1) for i in order) + "\n")
        print("tris", {k_: len(v) for k_, v in groups.items()}, "flip", bool(flip))


if __name__ == "__main__":
    main()
