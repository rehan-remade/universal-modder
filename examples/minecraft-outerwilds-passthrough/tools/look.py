#!/usr/bin/env python3
"""Hold a fixed camera in the guest and print what its exported colour layer actually contains.

This is the debugging companion to tools/oracle.py: the oracle decides *which* landmark colour
landed *where*; this just shows the picture, so a run that sees no landmarks can be told apart from a
run whose frame is blank, torn, or stale.

Everything here goes through the dev bridge or the guest's own socket, and every slot read is
seqlock-checked, so a torn or already-republished slot is skipped instead of misreported.

    uv run --with Pillow python3 tools/look.py [--yaw 0] [--pitch 40] [--name shot]
"""
import argparse
import importlib.util
import json
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

SHM = "/dev/shm/blockcraft-frame"
HEADER = 4096

spec = importlib.util.spec_from_file_location("pf", HERE / "probe_guest_lib.py")
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)


def wait_for_publishing(f, timeout=8.0):
    """Block until the publish counter advances. A throttled or paused guest republishes the *same*
    frame, which reads as a frozen picture and has produced false conclusions more than once."""
    a = publish_count(f)
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.25)
        b = publish_count(f)
        if b > a:
            return (b - a) / (time.time() - t0)
    return 0.0


def dev(command):
    import os
    import subprocess
    subprocess.run([str(HERE / "slice1.sh"), command], cwd=REPO,
                   env={**os.environ, "BLOCKCRAFT_NOWAIT": "1"}, capture_output=True, timeout=30)


def header(f):
    f.seek(0)
    return f.read(HEADER)


def publish_count(f):
    return struct.unpack_from("<Q", header(f), 32)[0]


def read_stable_colour(f, w, h, tries=40):
    """Return (pixels, slot, gframe, pose) for the newest slot, or None if it never reads clean."""
    n = w * h * 4
    for _ in range(tries):
        hd = header(f)
        latest, = struct.unpack_from("<i", hd, 40)
        if not (0 <= latest < 3):
            time.sleep(0.02)
            continue
        o = 256 + 128 * latest
        s0, = struct.unpack_from("<Q", hd, o)
        stride, = struct.unpack_from("<Q", hd, 16)
        gframe, = struct.unpack_from("<Q", hd, o + 8)
        px, py, pz = struct.unpack_from("<ddd", hd, o + 48)
        yaw, pitch, roll = struct.unpack_from("<fff", hd, o + 72)
        f.seek(HEADER + latest * stride)
        buf = f.read(n)
        hd2 = header(f)
        s1, = struct.unpack_from("<Q", hd2, o)
        if s0 == s1 and (s0 & 1) == 0 and len(buf) == n:
            return buf, latest, gframe, (px, py, pz, yaw, pitch, roll)
        time.sleep(0.02)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yaw", type=float, default=0.0)
    ap.add_argument("--pitch", type=float, default=40.0)
    ap.add_argument("--x", type=float, default=0.5)
    ap.add_argument("--y", type=float, default=8.0)
    ap.add_argument("--z", type=float, default=0.5)
    ap.add_argument("--name", default="look")
    ap.add_argument("--no-hold", action="store_true",
                    help="do not freeze the host bridge (watch the player's own view instead)")
    args = ap.parse_args()

    if not args.no_hold:
        dev("oracle on")
        time.sleep(0.5)

    sock = pf.connect()
    f = open(SHM, "rb", buffering=0)
    # Send a pose first: the guest only publishes while a pose is live (HostState times out after 2 s),
    # so checking the counter before anything is sent would always see a frozen counter.
    pf.send_text(sock, json.dumps({
        "t": "cam", "f": 0, "p": [args.x, args.y, args.z],
        "r": [args.yaw, args.pitch, 0.0], "fov": 70.0, "fp": True,
        "pl": [args.x, args.y - 8, args.z], "h": args.yaw,
    }))
    fps = wait_for_publishing(f, timeout=8.0)
    print(f"guest publishing at {fps:.0f} fps" if fps > 0 else "guest is NOT publishing")
    if fps <= 0:
        f.close()
        if not args.no_hold:
            dev("oracle off")
        return 1

    frame = 0
    shot = None
    end = time.time() + 3.0
    while time.time() < end:
        pf.send_text(sock, json.dumps({
            "t": "cam", "f": frame, "p": [args.x, args.y, args.z],
            "r": [args.yaw, args.pitch, 0.0], "fov": 70.0, "fp": True,
            "pl": [args.x, args.y - 8, args.z], "h": args.yaw,
        }))
        frame += 1
        time.sleep(1 / 60)
        r = read_stable_colour(f, 1280, 720)
        if r:
            shot = r
    f.close()
    sock.close()
    if not args.no_hold:
        dev("oracle off")

    if shot is None:
        print("no clean slot read — the guest is not publishing stable frames")
        return 1

    px, slot, gframe, pose = shot
    x, y, z, yaw, pitch, _ = pose
    nz = sum(1 for i in range(0, len(px), 4) if px[i] or px[i + 1] or px[i + 2])
    opq = sum(1 for i in range(0, len(px), 4) if px[i + 3])
    print(f"slot {slot} gframe {gframe}  rendered pose ({x:.2f},{y:.2f},{z:.2f}) yaw {yaw:.1f} pitch {pitch:.1f}")
    print(f"  non-black {nz}/{1280*720}   non-transparent {opq}/{1280*720}")

    try:
        from PIL import Image
        from collections import Counter
        im = Image.frombytes("RGBA", (1280, 720), px).convert("RGB")
        path = f"/tmp/opencode/{args.name}.png"
        im.save(path)
        print(f"  wrote {path}")
        c = Counter(im.resize((160, 90)).get_flattened_data())
        print("  dominant colours:", [f"{col}x{n}" for col, n in c.most_common(6)])
        w, h = im.size
        for label, (sx, sy) in (("centre", (w // 2, h // 2)), ("top", (w // 2, 20)),
                                ("lower", (w // 2, h - 60)), ("left", (60, h // 2)),
                                ("right", (w - 60, h // 2))):
            print(f"  {label:7s} {im.getpixel((sx, sy))}")
    except ImportError:
        print("  (Pillow not available; skipped image dump)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
