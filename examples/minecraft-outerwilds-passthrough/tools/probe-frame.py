#!/usr/bin/env python3
"""Stream cam poses and read the exported frame *while* they flow.

Reading after the probe stops is misleading: HostState times out after 2 s, the guest detaches and the
frame stops updating, so a later read can show an empty or stale slot. This holds the link open and
samples the newest published slot continuously.

    tools/probe-frame.py --seconds 10
"""
import argparse
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_guest_lib import connect, send_text, cam_message  # noqa: E402

SHM = "/dev/shm/blockcraft-frame"


def read_slot(f):
    h = f.read(4096)
    f.seek(0)
    magic, version, hbytes, slots = struct.unpack_from("<4I", h, 0)
    if magic != 0x46464342:
        return None
    stride, = struct.unpack_from("<Q", h, 16)
    latest, pid = struct.unpack_from("<2i", h, 40)
    if not (0 <= latest < slots):
        return None
    o = 256 + 128 * latest
    seq, = struct.unpack_from("<Q", h, o)
    gframe, = struct.unpack_from("<Q", h, o + 8)
    w, hh = struct.unpack_from("<2I", h, o + 24)
    flags, = struct.unpack_from("<I", h, o + 44)
    base = 4096 + latest * stride
    return dict(slot=latest, seq=seq, gframe=gframe, w=w, h=hh, flags=flags, base=base,
                publish=struct.unpack_from("<Q", h, 32)[0])


def sample(f, info, n=300):
    """Count non-black pixels in the colour layer of the slot, without reading the whole 94 MB layer."""
    import random
    random.seed(1234)
    w, hh, base = info["w"], info["h"], info["base"]
    f.seek(0)
    hdr = f.read(4096)
    seq_before = struct.unpack_from("<Q", hdr, 256 + 128 * info["slot"])[0]
    non = 0
    for _ in range(n):
        x = random.randrange(0, w)
        y = random.randrange(0, hh)
        f.seek(base + (y * w + x) * 4)
        p = f.read(4)
        if len(p) == 4 and p[3]:
            non += 1
    f.seek(0)
    hdr = f.read(4096)
    seq_after = struct.unpack_from("<Q", hdr, 256 + 128 * info["slot"])[0]
    return non, n, seq_before, seq_after


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=10.0)
    args = ap.parse_args()

    sock = connect()
    print("connected; streaming cam poses")

    f = open(SHM, "rb", buffering=0)
    end = time.time() + args.seconds
    i = 0
    best = 0
    torn = 0
    while time.time() < end:
        send_text(sock, cam_message(i))
        i += 1
        info = read_slot(f)
        if info:
            non, n, s0, s1 = sample(f, info)
            if s0 != s1 or s0 % 2:
                torn += 1
            if non > best:
                best = non
                print(f"  pose {i}: slot {info['slot']} frame {info['gframe']} "
                      f"{info['w']}x{info['h']} flags={info['flags']} nonblack={non}/{n} "
                      f"(seq {s0}->{s1})")
        time.sleep(1 / 30)

    print(f"sent {i} poses; best non-black coverage {best}/300; torn reads {torn}")
    f.close()


if __name__ == "__main__":
    main()
