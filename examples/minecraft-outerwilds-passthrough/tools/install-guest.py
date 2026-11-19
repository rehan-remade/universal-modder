#!/usr/bin/env python3
"""Copy the built guest mod into the Modrinth profile that the passthrough runs in.

The guest is a normal Fabric mod, so installing it is just a file copy - but the Modrinth App keeps
profiles under a Flatpak data dir, with spaces in the profile name, and the app has no CLI. Doing the
copy here keeps the agent from hand-typing that path (an earlier session copied a stale jar and the
guest silently never loaded).

    tools/install-guest.py                # copy build/libs/blockcraft-<version>.jar into the profile
    tools/install-guest.py --profile NAME # a different profile
    tools/install-guest.py --list         # show what is installed and whether it is current
"""
import argparse
import shutil
import sys
from pathlib import Path

APP = Path.home() / ".var/app/com.modrinth.ModrinthApp/data/ModrinthApp"
PROFILES = APP / "profiles"
LIB = Path(__file__).resolve().parent.parent / "mc" / "build" / "libs"


def newest_jar() -> Path:
    jars = sorted(LIB.glob("blockcraft-*.jar"), key=lambda p: p.stat().st_mtime)
    if not jars:
        raise SystemExit(f"no built jar in {LIB} (run ./gradlew build in mc/)")
    return jars[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="BlockCraft Passthrough")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    profile = PROFILES / args.profile
    if not profile.is_dir():
        raise SystemExit(f"no such profile: {profile}")

    if args.list:
        jar = newest_jar()
        print(f"built:   {jar}  ({jar.stat().st_size} bytes)")
        for p in sorted((profile / "mods").glob("blockcraft-*.jar")):
            same = p.read_bytes() == jar.read_bytes()
            mark = "current" if same else "STALE (differs from build)"
            print(f"profile: {p}  ({p.stat().st_size} bytes)  {mark}")
        return

    jar = newest_jar()
    dest = profile / "mods" / jar.name

    # Remove any other build of this mod first: two jars with the same mod id make Fabric refuse to
    # start, and the error is easy to miss in a 150-mod log.
    for old in (profile / "mods").glob("blockcraft-*.jar"):
        if old != dest:
            old.unlink()
            print(f"removed old {old.name}")

    shutil.copy2(jar, dest)
    print(f"installed {jar.name} -> {dest}")
    if dest.read_bytes() != jar.read_bytes():
        sys.exit("copy verification failed")


if __name__ == "__main__":
    main()
