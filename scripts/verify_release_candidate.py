#!/usr/bin/env python3
"""Require two independently built Python distribution directories to be byte-identical and safe."""
from __future__ import annotations

import hashlib
import json
import stat
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and "\\" not in name and ".." not in path.parts


def inspect(path: Path) -> list[str]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or any(not safe_name(name) for name in names):
                raise SystemExit(f"unsafe or duplicate wheel member in {path}")
            for info in archive.infolist():
                kind = stat.S_IFMT(info.external_attr >> 16)
                if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise SystemExit(f"non-regular wheel member: {info.filename}")
            return names
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)) or any(not safe_name(name) for name in names):
            raise SystemExit(f"unsafe or duplicate sdist member in {path}")
        if any(not (m.isfile() or m.isdir()) for m in members):
            raise SystemExit(f"non-regular sdist member in {path}")
        return names


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_release_candidate.py BUILD_A BUILD_B")
    left, right = map(Path, sys.argv[1:])
    def distributions(directory: Path) -> dict[str, Path]:
        return {p.name: p for p in directory.iterdir() if p.is_file() and (p.suffix == ".whl" or p.name.endswith(".tar.gz"))}

    a = distributions(left)
    b = distributions(right)
    if set(a) != set(b) or len(a) != 2 or sum(name.endswith(".whl") for name in a) != 1 or sum(name.endswith(".tar.gz") for name in a) != 1:
        raise SystemExit("distribution file sets differ or do not contain exactly one wheel and one sdist")
    receipt = {}
    for name in sorted(a):
        if digest(a[name]) != digest(b[name]):
            raise SystemExit(f"non-reproducible distribution bytes: {name}")
        members = inspect(a[name])
        receipt[name] = {"sha256": digest(a[name]), "bytes": a[name].stat().st_size, "members": len(members)}
    wheel_members = next((inspect(p) for p in a.values() if p.suffix == ".whl"), [])
    required = ["um/fonts/SpaceGrotesk-Bold.ttf", "um/ps1/WinDrive.ps1", "um/blender/render_sprites.py"]
    missing = [item for item in required if item not in wheel_members]
    if missing:
        raise SystemExit("wheel is missing packaged resources: " + ", ".join(missing))
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
