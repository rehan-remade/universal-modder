#!/usr/bin/env python3
"""Transactional, ownership-scoped installer for the GTA passthrough example.

Directory-entry power-loss durability is enforced on POSIX/WSL. Native Windows retains the ownership and
recovery protocol but cannot claim the same durability because Python exposes no directory fsync there.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
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


def write_json_atomic(path: Path, payload: dict, *, replace: bool = False) -> None:
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(8)}")
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
    if replace:
        os.replace(tmp, path)
    else:
        try:
            os.link(tmp, path, follow_symlinks=False)
        except FileExistsError:
            tmp.unlink(missing_ok=True)
            fail(f"refusing to replace concurrently created receipt: {path}")
        tmp.unlink()
    _fsync_dir(path.parent)


def read_receipt(path: Path, *, journal: bool = False) -> list[dict]:
    if path.is_symlink() or not path.is_file():
        fail(f"ownership receipt is not a regular file: {path}")
    data: object = None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"invalid ownership receipt {path}: {exc}")
    expected_state = "installing" if journal else "installed"
    if not isinstance(data, dict) or data.get("format") != 1 or data.get("state") != expected_state:
        fail(f"invalid ownership receipt format/state: {path}")
    entries = data.get("entries")
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
        clean_entry = {"path": rel, "sha256": digest}
        nonce = entry.get("nonce")
        if nonce is not None:
            if not journal or not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{16}", nonce):
                fail(f"invalid ownership entry in {path}: {rel}")
            clean_entry["nonce"] = nonce
        clean.append(clean_entry)
    return clean


def stage_path(root: Path, entry: dict) -> Path | None:
    nonce = entry.get("nonce")
    if nonce is None:
        return None
    target = destination(root, entry["path"])
    stage = target.with_name(f".{target.name}.um-part-{nonce}")
    if stage.is_symlink():
        fail(f"refusing symlinked install stage for: {entry['path']}")
    return stage


def rollback(root: Path, entries: list[dict]) -> bool:
    """Validate the complete rollback topology before removing any owned file."""
    decisions: list[tuple[dict, Path, Path | None, bool]] = []
    complete = True
    for entry in reversed(entries):
        target = destination(root, entry["path"])
        stage = stage_path(root, entry)
        owned = target.is_file() and sha256(target) == entry["sha256"]
        if stage is not None:
            owned = owned and stage.is_file() and os.path.samefile(target, stage)
        if target.exists() and not owned:
            print(f"preserving changed file: {entry['path']}", file=sys.stderr)
            complete = False
        if stage is not None and stage.exists() and (not stage.is_file() or sha256(stage) != entry["sha256"]):
            print(f"preserving changed install stage: {stage.name}", file=sys.stderr)
            complete = False
        decisions.append((entry, target, stage, owned))
    for _entry, target, stage, owned in decisions:
        if owned:
            target.unlink()
            _fsync_dir(target.parent)
        if stage is not None and stage.is_file() and sha256(stage) == _entry["sha256"]:
            stage.unlink()
            _fsync_dir(stage.parent)
    return complete


def recover(root: Path, journal: Path) -> None:
    if not journal.exists() and not journal.is_symlink():
        return
    entries = read_receipt(journal, journal=True)
    manifest = root / MANIFEST_NAME
    if manifest.exists() or manifest.is_symlink():
        installed = read_receipt(manifest)
        public = [{"path": entry["path"], "sha256": entry["sha256"]} for entry in entries]
        if installed != public:
            fail(f"install journal does not match ownership manifest: {journal}")
        cleanup_complete = True
        for entry in entries:
            stage = stage_path(root, entry)
            if stage is not None and stage.exists():
                if stage.is_file() and sha256(stage) == entry["sha256"]:
                    stage.unlink()
                else:
                    cleanup_complete = False
        if not cleanup_complete:
            fail(f"committed install has an invalid stage; journal retained: {journal}")
        journal.unlink()
        _fsync_dir(root)
        return
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
    public_entries: list[dict] = []
    write_json_atomic(journal, {"format": 1, "state": "installing", "entries": public_entries})
    active_tmp: Path | None = None
    try:
        for item in planned:
            target = destination(root, item["path"], create_parents=True)
            nonce = secrets.token_hex(8)
            tmp = target.with_name(f".{target.name}.um-part-{nonce}")
            active_tmp = tmp
            public_entries.append({"path": item["path"], "sha256": item["sha256"], "nonce": nonce})
            write_json_atomic(journal, {"format": 1, "state": "installing", "entries": public_entries}, replace=True)
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
            try:
                os.link(tmp, target, follow_symlinks=False)
            except FileExistsError:
                fail(f"refusing to replace file created during install: {item['path']}")
            _fsync_dir(target.parent)
            active_tmp = None
        installed_entries = [{"path": entry["path"], "sha256": entry["sha256"]} for entry in public_entries]
        write_json_atomic(manifest, {"format": 1, "state": "installed", "entries": installed_entries})
        for entry in public_entries:
            stage = stage_path(root, entry)
            if stage is not None:
                stage.unlink(missing_ok=True)
        journal.unlink()
        _fsync_dir(root)
    except BaseException:
        journaled_stages = {stage_path(root, entry) for entry in public_entries}
        if active_tmp is not None and active_tmp not in journaled_stages:
            active_tmp.unlink(missing_ok=True)
        if rollback(root, public_entries):
            journal.unlink(missing_ok=True)
            _fsync_dir(root)
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
