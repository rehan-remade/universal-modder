#!/usr/bin/env python3
"""Stop the guest Minecraft that tools/launch-mc.py started, safely.

The hazard that makes this worth a script: a shell `pkill -f launch-mc.py` (or a `pgrep` whose pattern
also appears in the command you are running) matches *your own shell*, because the pattern is part of
its command line. That killed the agent's shell twice in one session. Nothing here matches on a
pattern for the kill itself - it finds the java process, prints what it is about to kill, and signals
those exact PIDs.

    tools/stop-guest.py              # SIGTERM, then SIGKILL anything still alive
    tools/stop-guest.py --list       # just show what would be stopped
"""
import argparse
import os
import signal
import subprocess
import sys
import time

KNOT = "net.fabricmc.loader.impl.launch.knot.KnotClient"


def find_pids():
    """PIDs of guest JVMs, via /proc so nothing has to parse another process's arguments."""
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as fh:
                cmd = fh.read().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        # Match the launch main class, which a shell command line never contains verbatim.
        if KNOT in cmd:
            pids.append(int(entry))
    return pids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    pids = find_pids()
    if not pids:
        print("no guest running")
        return

    for pid in pids:
        try:
            started = time.strftime("%H:%M:%S", time.localtime(os.stat(f"/proc/{pid}").st_mtime))
        except OSError:
            started = "?"
        print(f"  pid {pid}  (started {started})")

    if args.list:
        return

    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for _ in range(20):
        time.sleep(0.5)
        if not find_pids():
            print("stopped")
            return
    for pid in find_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    time.sleep(1)
    print("still alive after SIGKILL" if find_pids() else "stopped (SIGKILL)")
    sys.exit(0)


if __name__ == "__main__":
    main()
