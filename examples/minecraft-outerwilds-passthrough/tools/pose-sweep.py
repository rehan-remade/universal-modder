#!/usr/bin/env python3
"""Sweep camera poses and report the exported frame's md5 for each.

The point is to answer one question decisively: does the picture the guest exports *change* when the
host's pose changes? A frame that is byte-identical across very different poses means the camera
override is not reaching the render, whatever the descriptor says.

The host bridge is frozen for the run (dev command `oracle on`) so the pose sent here is the one that
renders, and Outer Wilds is re-focused throughout because it pauses when it loses focus, which stops
its Update loop and silently ends the pose stream.

    uv run --with Pillow python3 tools/pose-sweep.py
"""
import hashlib
import importlib.util
import json
import os
import struct
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SHM = "/dev/shm/blockcraft-frame"
HEADER = 4096

spec = importlib.util.spec_from_file_location("pf", HERE / "probe_guest_lib.py")
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)

POSES = [
    ("yaw0 pitch40",   (0.5, 8.0, 0.5,   0.0, 40.0)),
    ("yaw90 pitch40",  (0.5, 8.0, 0.5,  90.0, 40.0)),
    ("yaw180 pitch40", (0.5, 8.0, 0.5, 180.0, 40.0)),
    ("yaw270 pitch40", (0.5, 8.0, 0.5, 270.0, 40.0)),
    ("move +30x",      (30.5, 8.0, 0.5,  0.0, 40.0)),
]


def dev(command):
    subprocess.run([str(HERE / "slice1.sh"), command], cwd=REPO,
                   env={**os.environ, "BLOCKCRAFT_NOWAIT": "1"}, capture_output=True, timeout=30)


def focus_ow():
    """Outer Wilds pauses on focus loss, which stops the pose stream; keep it in front."""
    out = subprocess.run(["xdotool", "search", "--name", "Outer Wilds"],
                         capture_output=True, text=True).stdout.split()
    if out:
        for verb in ("windowactivate", "windowfocus"):
            subprocess.run(["xdotool", verb, out[0]], capture_output=True)


def cam(sock, frame, x, y, z, yaw, pitch):
    pf.send_text(sock, json.dumps({
        "t": "cam", "f": frame, "p": [x, y, z], "r": [yaw, pitch, 0.0],
        "fov": 70.0, "fp": True, "pl": [x, y - 8, z], "h": yaw,
    }))


def grab(f, sock, label, pose, hold=1.5):
    x, y, z, yaw, pitch = pose
    frame = 0
    t0 = time.time()
    while time.time() - t0 < hold:
        focus_ow()
        cam(sock, frame, x, y, z, yaw, pitch)
        frame += 1
        time.sleep(1 / 60)
    time.sleep(0.4)

    for _ in range(50):
        f.seek(0)
        h = f.read(HEADER)
        stride, = struct.unpack_from("<Q", h, 16)
        latest, = struct.unpack_from("<i", h, 40)
        o = 256 + 128 * latest
        s0, = struct.unpack_from("<Q", h, o)
        w, hh = struct.unpack_from("<II", h, o + 24)
        gx, gy, gz = struct.unpack_from("<ddd", h, o + 48)
        gyaw, gp, _gr = struct.unpack_from("<fff", h, o + 72)
        f.seek(HEADER + latest * stride)
        px = f.read(w * hh * 4)
        f.seek(0)
        s1, = struct.unpack_from("<Q", f.read(HEADER), o)
        if s0 == s1 and (s0 & 1) == 0:
            break
        time.sleep(0.02)

    md5 = hashlib.md5(px).hexdigest()[:12]
    nonzero = sum(1 for i in range(0, len(px), 4) if px[i] or px[i + 1] or px[i + 2])
    print(f"  {label:16s} desc yaw {gyaw:6.1f} pitch {gp:6.1f} "
          f"pos({gx:6.1f},{gy:6.1f},{gz:6.1f})  md5 {md5}  nonzero {nonzero}")

    return md5


def main():
    dev("oracle on")
    time.sleep(0.5)
    sock = pf.connect()
    f = open(SHM, "rb", buffering=0)

    print("frame md5 for different poses (Outer Wilds kept focused):")
    seen = {}
    for label, pose in POSES:
        m = grab(f, sock, label, pose)
        seen.setdefault(m, []).append(label)

    f.close()
    sock.close()
    dev("oracle off")

    print()
    if len(seen) == 1:
        print("VERDICT: every pose produced the SAME frame — the camera override is not reaching the render.")
    else:
        print(f"VERDICT: {len(seen)} distinct frames from {len(POSES)} poses — the camera override works.")
        for m, labels in seen.items():
            print(f"  {m}: {', '.join(labels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
