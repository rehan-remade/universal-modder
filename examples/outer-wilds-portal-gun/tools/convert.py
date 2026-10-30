"""Convert the portal gun from the user's own Portal 2 install into files the Outer Wilds mod loads.

    python convert.py [--portal2 "<...>/steamapps/common/Portal 2"] [--out <dir>]

Default output: %LOCALAPPDATA%/OWPortalGun (outside any repo; nothing of Valve's is redistributed).
Writes:
  portalgun.owpg   skinned viewmodel: bones, mesh, attachments, sequences baked to per-frame bone poses
  textures/*.png   gun textures, portal rim colour ramp, masks, crosshair
  sounds/*.wav     firing, portal open/enter/exit, invalid surface, fizzle, draw
  manifest.json    what was written (for the mod's log and for checks)
"""
import argparse
import json
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from source_mdl import Model  # noqa: E402
from vpk import SourceFS  # noqa: E402
import vtf  # noqa: E402

INCH = 0.0254
# Source (X forward, Y left, Z up, right-handed) -> Unity (X right, Y up, Z forward, left-handed)
C = np.array([[0, -1, 0], [0, 0, 1], [1, 0, 0]], dtype=np.float64)

GUN = "models/weapons/v_portalgun"
GUN_TEX = "materials/models/weapons/v_models/v_portalgun/"
TEXTURES = {
    "v_portalgun": GUN_TEX + "v_portalgun",
    "v_portalgun_blue": GUN_TEX + "v_portalgun_blue",
    "v_portalgun_orange": GUN_TEX + "v_portalgun_orange",
    "v_portalgun_glass": GUN_TEX + "v_portalgun_glass",
    "v_portalgun_normal": GUN_TEX + "v_portalgun_normal",
    "portal-blue-color": "materials/models/portals/portal-blue-color",
    "portal-orange-color": "materials/models/portals/portal-orange-color",
    "portal_mask": "materials/models/portals/portal_mask",
    "noise-blur": "materials/models/portals/noise-blur-256x256",
    "portal_crosshairs": "materials/sprites/hud/portal_crosshairs",
    "portal_1_particle": "materials/effects/portal_1_particle",
    "portal_2_particle": "materials/effects/portal_2_particle",
}
SOUNDS = [
    "weapons/portalgun/wpn_portal_gun_fire_blue_01", "weapons/portalgun/wpn_portal_gun_fire_blue_02",
    "weapons/portalgun/wpn_portal_gun_fire_blue_03", "weapons/portalgun/wpn_portal_gun_fire_red_01",
    "weapons/portalgun/wpn_portal_gun_fire_red_02", "weapons/portalgun/wpn_portal_gun_fire_red_03",
    "weapons/portalgun/portal_open_blue_01", "weapons/portalgun/portal_open_red_01",
    "weapons/portalgun/portal_open_red_02", "weapons/portalgun/portal_open1", "weapons/portalgun/portal_open2",
    "weapons/portalgun/portal_open3", "weapons/portalgun/portal_enter_01", "weapons/portalgun/portal_enter_02",
    "weapons/portalgun/portal_enter_03", "weapons/portalgun/portal_exit_01", "weapons/portalgun/portal_exit_02",
    "weapons/portalgun/portal_invalid_surface_01", "weapons/portalgun/portal_invalid_surface_02",
    "weapons/portalgun/portal_invalid_surface_03", "weapons/portalgun/portal_invalid_surface_04",
    "weapons/portalgun/portal_fizzle_01", "weapons/portalgun/portal_fizzle_02",
    "weapons/portalgun/portal_close1", "weapons/portalgun/portal_close2",
    "weapons/portalgun_powerup1", "weapons/portalgun_powerdown",
    "weapon_ambient/wpn_portalgun_activation_01",
]


def default_portal2():
    for steam in (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)") + r"\Steam",
                  os.path.expanduser("~/.steam/steam"), os.path.expanduser("~/.local/share/Steam")):
        p = os.path.join(steam, "steamapps", "common", "Portal 2")
        if os.path.isdir(p):
            return p
    return None


def quat_to_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def mat_to_quat(m):
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        q = ((m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, 0.25 * s)
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = (0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s, (m[2, 1] - m[1, 2]) / s)
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = ((m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s, (m[0, 2] - m[2, 0]) / s)
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = ((m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s, (m[1, 0] - m[0, 1]) / s)
    q = np.array(q)
    return q / np.linalg.norm(q)


def conv_pos(p):
    return C @ np.asarray(p, dtype=np.float64) * INCH


def conv_rot(q):
    return mat_to_quat(C @ quat_to_mat(q) @ C.T)


def conv_mat34(m):
    """Source 3x4 (rotation|translation, inches) -> Unity 4x4 (meters)."""
    out = np.eye(4)
    out[:3, :3] = C @ m[:, :3] @ C.T
    out[:3, 3] = C @ m[:, 3] * INCH
    return out


class Writer:
    def __init__(self):
        self.b = bytearray()

    def i(self, *v):
        self.b += struct.pack(f"<{len(v)}i", *v)

    def f(self, *v):
        self.b += struct.pack(f"<{len(v)}f", *[float(x) for x in v])

    def s(self, text):
        raw = text.encode("utf-8")
        self.i(len(raw))
        self.b += raw

    def arr(self, a, dtype):
        self.b += np.ascontiguousarray(a, dtype=dtype).tobytes()


def write_model(m, path, log):
    w = Writer()
    w.b += b"OWPG"
    w.i(1)

    # bones (bind local pose + bindpose matrix)
    w.i(len(m.bones))
    for b in m.bones:
        w.s(b["name"])
        w.i(b["parent"])
        w.f(*conv_pos(b["pos"]))
        w.f(*conv_rot(b["quat"]))
        w.f(*conv_mat34(b["pose_to_bone"]).reshape(-1))

    # mesh: body part 0 only (the potatOS bodygroup is off by default)
    keep = [s for s in m.submeshes if s[0] == m.submeshes[0][0]]
    used = np.unique(np.concatenate([s[3].reshape(-1) for s in keep]))
    remap = -np.ones(len(m.positions), dtype=np.int64)
    remap[used] = np.arange(len(used))
    pos = (m.positions[used] @ C.T) * INCH
    nrm = m.normals[used] @ C.T
    uv = m.uvs[used].copy()
    uv[:, 1] = 1.0 - uv[:, 1]  # Source V is top-down
    bones = np.zeros((len(used), 4), dtype=np.int32)
    weights = np.zeros((len(used), 4), dtype=np.float32)
    bones[:, :3] = m.weight_bones[used]
    weights[:, :3] = m.weights[used]
    for k in range(3):
        weights[m.weight_count[used] <= k, k] = 0
    weights /= np.maximum(weights.sum(1, keepdims=True), 1e-6)

    # A mirror (det C = -1) flips winding; pick the order whose face normals agree with vertex normals.
    agree = 0
    tris_all = []
    for _bp, _mn, mat, tris in keep:
        t = remap[tris]
        tris_all.append((mat, t))
        a, b_, c = pos[t[:, 0]], pos[t[:, 1]], pos[t[:, 2]]
        fn = np.cross(b_ - a, c - a)  # Unity front face: clockwise, normal = cross(b-a, c-a)
        vn = nrm[t[:, 0]] + nrm[t[:, 1]] + nrm[t[:, 2]]
        agree += int((np.einsum("ij,ij->i", fn, vn) > 0).sum()) - int((np.einsum("ij,ij->i", fn, vn) < 0).sum())
    flip = agree < 0
    log["winding_flipped"] = bool(flip)

    w.i(len(pos))
    w.arr(pos, "<f4")
    w.arr(nrm, "<f4")
    w.arr(uv, "<f4")
    w.arr(bones, "<i4")
    w.arr(weights, "<f4")
    w.i(len(tris_all))
    for mat, t in tris_all:
        if flip:
            t = t[:, [0, 2, 1]]
        w.s(os.path.basename(m.textures[mat].replace("\\", "/")).lower())
        w.i(t.size)
        w.arr(t.reshape(-1), "<i4")

    # attachments
    w.i(len(m.attachments))
    for a in m.attachments:
        mm = conv_mat34(a["local"])
        w.s(a["name"])
        w.i(a["bone"])
        w.f(*mm[:3, 3])
        w.f(*mat_to_quat(mm[:3, :3]))

    # sequences
    w.i(len(m.sequences))
    log["sequences"] = {}
    for s in m.sequences:
        ad = m.anims[s["anim"]]
        p, q = m.anim_frames(s["anim"])
        nf, nb = p.shape[:2]
        up = (p.reshape(-1, 3) @ C.T * INCH).reshape(nf, nb, 3)
        uq = np.array([conv_rot(x) for x in q.reshape(-1, 4)]).reshape(nf, nb, 4)
        w.s(s["name"])
        w.s(s["activity"])
        w.i(int(s["looping"]))
        w.f(ad["fps"])
        w.i(nf)
        w.arr(np.concatenate([up, uq], axis=2), "<f4")  # [frame][bone][px py pz qx qy qz qw]
        log["sequences"][s["name"]] = dict(frames=nf, fps=ad["fps"], loop=s["looping"])

    with open(path, "wb") as f:
        f.write(w.b)
    log["vertices"] = int(len(pos))
    log["triangles"] = int(sum(len(t) for _m, t in tris_all))
    log["bones"] = len(m.bones)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--portal2", default=default_portal2(), help="Portal 2 install folder")
    ap.add_argument("--out", default=os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                                                  "OWPortalGun"))
    args = ap.parse_args()
    if not args.portal2 or not os.path.isdir(os.path.join(args.portal2, "portal2")):
        sys.exit("Portal 2 not found; pass --portal2 <install folder>")
    p2 = args.portal2
    fs = SourceFS([os.path.join(p2, d, "pak01_dir.vpk") for d in ("portal2_dlc2", "portal2_dlc1", "portal2")]
                  + [os.path.join(p2, "portal2")])
    os.makedirs(os.path.join(args.out, "textures"), exist_ok=True)
    os.makedirs(os.path.join(args.out, "sounds"), exist_ok=True)
    log = {"portal2": p2, "textures": [], "sounds": [], "missing": []}

    m = Model(fs.read(GUN + ".mdl"), fs.read(GUN + ".vvd"), fs.read(GUN + ".dx90.vtx"))
    write_model(m, os.path.join(args.out, "portalgun.owpg"), log)

    for name, path in TEXTURES.items():
        data = fs.read(path + ".vtf")
        if data is None:
            log["missing"].append(path)
            continue
        vtf.decode(data).save(os.path.join(args.out, "textures", name + ".png"))
        log["textures"].append(name)

    for snd in SOUNDS:
        data = fs.read("sound/" + snd + ".wav")
        if data is None:
            log["missing"].append(snd)
            continue
        name = os.path.basename(snd) + ".wav"
        with open(os.path.join(args.out, "sounds", name), "wb") as f:
            f.write(data)
        log["sounds"].append(name)

    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump(log, f, indent=2)
    print(f"wrote {args.out}: {log['vertices']} verts, {log['triangles']} tris, {log['bones']} bones, "
          f"{len(log['sequences'])} sequences, {len(log['textures'])} textures, {len(log['sounds'])} sounds"
          + (f", missing {log['missing']}" if log["missing"] else ""))


if __name__ == "__main__":
    main()
