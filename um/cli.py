"""`um` command line: one entry point for every tool, so skills can say `um <group> <cmd>`."""
from __future__ import annotations

import argparse
import importlib
import sys

from um import __doc__ as DOC, __version__

GROUPS = ["scan", "fal", "comfy", "sprite", "render3d", "video", "win", "backup", "publish", "kb"]


def main(argv=None):
    # notes and game titles are UTF-8; a cp1252 console must not crash on them
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    ap = argparse.ArgumentParser(prog="um", description=DOC, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"universal-modder {__version__}")
    sub = ap.add_subparsers(dest="group", metavar="<group>")
    for g in GROUPS:
        importlib.import_module(f"um.{g}").register(sub)
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        # a group without a command: show that group's help
        if args.group:
            ap.parse_args([args.group, "--help"])
        ap.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
