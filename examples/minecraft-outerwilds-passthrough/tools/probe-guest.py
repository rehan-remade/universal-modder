#!/usr/bin/env python3
"""Talk to the guest's WebSocket link without Outer Wilds, to test the guest on its own.

The guest only creates its shared-memory frame buffer while a host is sending `cam` poses (HostState
times out after 2 s), so with no host running there is nothing in /dev/shm and nothing to read. This
client sends the same messages the mod sends, which lets the guest's receive path, the pose handling
and the frame export be checked in isolation.

    tools/probe-guest.py hello         # connect and print the guest's hello
    tools/probe-guest.py cam           # stream cam poses, watch for the frame buffer to appear
    tools/probe-guest.py raw '<json>'  # send one message and print any reply

Nothing here is part of the mod; it is a test client. See also tools/probe-frame.py, which reads the
exported frame while poses flow.
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_guest_lib import cam_message, connect, recv_frame, send_text  # noqa: E402

SHM = "/dev/shm/blockcraft-frame"


def shm_state():
    if not os.path.exists(SHM):
        return "absent"
    return f"present ({os.path.getsize(SHM)} bytes)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["hello", "cam", "raw"])
    ap.add_argument("message", nargs="?")
    ap.add_argument("--seconds", type=float, default=6.0)
    args = ap.parse_args()

    sock = connect()
    print(f"connected to 127.0.0.1:{socket_port()}")

    if args.mode == "hello":
        print("guest said:", recv_frame(sock))
        return

    if args.mode == "raw":
        if not args.message:
            raise SystemExit("raw needs a JSON argument")
        send_text(sock, args.message)
        for _ in range(3):
            m = recv_frame(sock)
            if m is None:
                break
            print("guest:", m)
        return

    # cam: stream poses and watch the frame buffer appear, then keep reading replies
    print("frame buffer before:", shm_state())
    end = time.time() + args.seconds
    i = 0
    seen = None
    while time.time() < end:
        send_text(sock, cam_message(i))
        i += 1
        if seen is None and os.path.exists(SHM):
            seen = time.time()
            print(f"frame buffer appeared after {i} poses: {shm_state()}")
        m = recv_frame(sock, timeout=0.2)
        if m:
            print("guest:", m[:200])
        time.sleep(1 / 30)
    print(f"sent {i} cam poses")
    print("frame buffer after: ", shm_state())


def socket_port():
    from probe_guest_lib import PORT
    return PORT


if __name__ == "__main__":
    main()
