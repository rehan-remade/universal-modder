#!/usr/bin/env python3
"""Check or transactionally refresh the two physical skill mirrors."""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills"
TARGETS = [ROOT / ".agents" / "skills", ROOT / ".claude" / "skills"]


def inventory(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise SystemExit(f"symlink is not allowed in a skill tree: {root / rel}")
        if path.is_file():
            result[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def replace_tree(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.sync-", dir=target.parent))
    rollback = target.with_name(f".{target.name}.rollback-{os.getpid()}")
    shutil.rmtree(stage)
    shutil.copytree(SOURCE, stage, symlinks=False)
    moved = False
    try:
        if target.exists():
            os.replace(target, rollback)
            moved = True
        os.replace(stage, target)
    except BaseException:
        if moved and rollback.exists() and not target.exists():
            os.replace(rollback, target)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    if rollback.exists():
        shutil.rmtree(rollback)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = inventory(SOURCE)
    drift = [target for target in TARGETS if not target.is_dir() or inventory(target) != expected]
    if args.check:
        if drift:
            print("skill mirror drift: " + ", ".join(str(p.relative_to(ROOT)) for p in drift))
            return 1
        print(f"skill mirrors: {len(expected)} files, exact")
        return 0
    for target in drift:
        replace_tree(target)
    print(f"skill mirrors refreshed: {len(expected)} files x {len(TARGETS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
