#!/usr/bin/env python3
"""Transactional, ownership-scoped installer for the GTA passthrough example."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import NoReturn

TARGETS = {
    "ScriptHookV.dll", "dinput8.dll", "MCPassthrough.asi", "ReShade64.asi",
    "reshade-shaders/Shaders/MCPassthrough.fx", "reshade-shaders/Shaders/ReShade.fxh",
    "reshade-shaders/Shaders/ReShadeUI.fxh", "args.txt", "ReShade.ini", "ReShadePreset.ini",
}
MANIFEST_NAME = ".universal-modder-mcpassthrough-owned"
JOURNAL_NAME = ".universal-modder-mcpassthrough-installing"


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_rel(value: str) -> str:
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or "\\" in value or path.as_posix() != value
            or any(part in {"", ".", ".."} for part in path.parts) or value not in TARGETS):
        fail(f"unsafe or unexpected ownership entry: {value}")
    return value


def destination(root: Path, rel: str, create_parents: bool = False) -> Path:
    rel = safe_rel(rel)
    current = root
    for part in PurePosixPath(rel).parts[:-1]:
        current = current / part
        if current.is_symlink():
            fail(f"refusing symlinked destination ancestor: {current.relative_to(root)}")
        if current.exists() and not current.is_dir():
            fail(f"destination ancestor is not a directory: {current.relative_to(root)}")
        if not current.exists() and create_parents:
            current.mkdir()
            _fsync_dir(current.parent)
    result = current / PurePosixPath(rel).name
    if result.is_symlink():
        fail(f"refusing destination symlink: {rel}")
    try:
        result.parent.resolve(strict=False).relative_to(root)
    except (OSError, ValueError):
        fail(f"destination escapes game directory: {rel}")
    return result


def _fsync_dir(path: Path) -> None:
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def write_json_atomic(path: Path, payload: dict) -> None:
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(tmp, flags, 0o600)
    try:
        data = (json.dumps(payload, sort_keys=True) + "\n").encode()
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def read_receipt(path: Path) -> list[dict]:
    if path.is_symlink() or not path.is_file():
        fail(f"ownership receipt is not a regular file: {path}")
    data: object = None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"invalid ownership receipt {path}: {exc}")
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list) or len(entries) > len(TARGETS):
        fail(f"invalid ownership receipt entries: {path}")
    seen: set[str] = set()
    clean = []
    for entry in entries:
        if (not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str)
                or not isinstance(entry.get("path"), str)):
            fail(f"invalid ownership entry in {path}")
        rel = safe_rel(entry["path"])
        digest = entry["sha256"]
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) or rel in seen:
            fail(f"invalid ownership entry in {path}: {rel}")
        seen.add(rel)
        clean.append({"path": rel, "sha256": digest})
    return clean


def rollback(root: Path, entries: list[dict]) -> bool:
    complete = True
    for entry in reversed(entries):
        target = destination(root, entry["path"])
        if target.is_file() and sha256(target) == entry["sha256"]:
            target.unlink()
            _fsync_dir(target.parent)
        elif target.exists():
            print(f"preserving changed file: {entry['path']}", file=sys.stderr)
            complete = False
    return complete


def recover(root: Path, journal: Path) -> None:
    if not journal.exists() and not journal.is_symlink():
        return
    entries = read_receipt(journal)
    if not rollback(root, entries):
        fail(f"interrupted install has changed files; receipt retained: {journal}")
    journal.unlink()
    _fsync_dir(root)
    print("recovered an interrupted passthrough install", file=sys.stderr)


def install(root: Path, pairs: list[str]) -> None:
    manifest = root / MANIFEST_NAME
    journal = root / JOURNAL_NAME
    recover(root, journal)
    if manifest.exists() or manifest.is_symlink():
        fail(f"already installed according to {manifest}; remove it first")
    if len(pairs) % 2:
        fail("internal installer source/target mismatch")
    planned = []
    for source_raw, rel_raw in zip(pairs[::2], pairs[1::2]):
        rel = safe_rel(rel_raw)
        source = Path(source_raw)
        if source.is_symlink() or not source.is_file() or not stat.S_ISREG(source.stat().st_mode):
            fail(f"missing or unsafe install source: {source}")
        target = destination(root, rel)
        source_hash = sha256(source)
        if target.exists():
            if not target.is_file() or sha256(target) != source_hash:
                fail(f"refusing to replace existing file: {rel}")
            print(f"preserving identical pre-existing file: {rel}")
        else:
            planned.append({"path": rel, "sha256": source_hash, "source": str(source)})
    if not planned:
        print("nothing new was installed")
        return
    public_entries = [{"path": item["path"], "sha256": item["sha256"]} for item in planned]
    write_json_atomic(journal, {"format": 1, "state": "installing", "entries": public_entries})
    try:
        for item in planned:
            target = destination(root, item["path"], create_parents=True)
            tmp = target.with_name(f".{target.name}.um-part-{os.getpid()}")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(tmp, flags, 0o600)
            try:
                with open(item["source"], "rb") as source:
                    with os.fdopen(fd, "wb", closefd=False) as output:
                        shutil.copyfileobj(source, output, 1 << 20)
                        output.flush()
                        os.fsync(output.fileno())
            finally:
                os.close(fd)
            if sha256(tmp) != item["sha256"]:
                tmp.unlink(missing_ok=True)
                fail(f"copied bytes failed verification: {item['path']}")
            destination(root, item["path"])
            os.replace(tmp, target)
            _fsync_dir(target.parent)
        os.replace(journal, manifest)
        _fsync_dir(root)
    except BaseException:
        rollback(root, public_entries)
        raise
    print(f"installed into {root}; ownership manifest: {manifest}")


def remove(root: Path) -> None:
    manifest = root / MANIFEST_NAME
    recover(root, root / JOURNAL_NAME)
    entries = read_receipt(manifest)
    changed = not rollback(root, entries)
    for rel in ("reshade-shaders/Shaders", "reshade-shaders"):
        path = root / rel
        if path.is_dir() and not path.is_symlink():
            try:
                path.rmdir()
            except OSError:
                pass
    if changed:
        print(f"ownership manifest retained because changed files remain: {manifest}", file=sys.stderr)
        return
    manifest.unlink()
    _fsync_dir(root)


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in {"install", "remove"}:
        fail("usage: install_passthrough.py install|remove GTA_DIR [SOURCE TARGET ...]")
    mode = sys.argv[1]
    raw_root = Path(sys.argv[2])
    if raw_root.is_symlink() or not (raw_root / "GTA5.exe").is_file():
        fail(f"GTA5.exe not found in a regular game directory: {raw_root}")
    root = raw_root.resolve(strict=True)
    if mode == "remove":
        if len(sys.argv) != 3:
            fail("remove takes no source arguments")
        remove(root)
    else:
        install(root, sys.argv[3:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
