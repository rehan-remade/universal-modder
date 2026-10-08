#!/usr/bin/env python3
"""Transactional, ownership-scoped installer for the GTA passthrough example.

Directory-entry power-loss durability is enforced on POSIX/WSL. Native Windows fails closed; run this
installer from WSL so descriptor-relative ancestry checks and directory fsync remain available.
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
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator, NoReturn

TARGETS = {
    "ScriptHookV.dll", "dinput8.dll", "MCPassthrough.asi", "ReShade64.asi",
    "reshade-shaders/Shaders/MCPassthrough.fx", "reshade-shaders/Shaders/ReShade.fxh",
    "reshade-shaders/Shaders/ReShadeUI.fxh", "args.txt", "ReShade.ini", "ReShadePreset.ini",
}
MANIFEST_NAME = ".universal-modder-mcpassthrough-owned"
MANIFEST_MARKER_NAME = ".universal-modder-mcpassthrough-owned-marker"
JOURNAL_NAME = ".universal-modder-mcpassthrough-installing"
LOCK_NAME = ".universal-modder-mcpassthrough-lock"


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


@contextmanager
def operation_lock(root: Path) -> Iterator[None]:
    if os.name == "nt":
        fail("native Windows installer mode is unsupported; run this installer from WSL")
    lock = root / LOCK_NAME
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(lock, flags, 0o600)
    except OSError as exc:
        fail(f"cannot open passthrough operation lock {lock}: {exc}")
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(fd)
        fail(f"passthrough operation lock is not a unique regular file: {lock}")
    import fcntl
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        fail(f"another passthrough install/remove/recovery is active: {lock}")
    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _open_parent_fd(root: Path, rel: str, *, create: bool = False) -> tuple[int, str]:
    if os.name == "nt":
        fail("native Windows installer mode is unsupported; run this installer from WSL")
    parts = PurePosixPath(safe_rel(rel)).parts
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(root, flags)
    try:
        for part in parts[:-1]:
            if create:
                try:
                    os.mkdir(part, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd, parts[-1]
    except BaseException:
        os.close(fd)
        raise


def _parent_open(parent: int, name: str, flags: int, mode: int = 0o777) -> int:
    return os.open(name, flags, mode, dir_fd=parent)


def _parent_stat(parent: int, name: str) -> os.stat_result:
    return os.stat(name, dir_fd=parent, follow_symlinks=False)


def _parent_unlink(parent: int, name: str) -> None:
    os.unlink(name, dir_fd=parent)


def _parent_link(parent: int, source: str, target: str) -> None:
    os.link(source, target, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)


def _parent_rename(parent: int, source: str, target: str) -> None:
    os.rename(source, target, src_dir_fd=parent, dst_dir_fd=parent)


def _parent_fsync(parent: int) -> None:
    os.fsync(parent)


def _parent_close(parent: int) -> None:
    os.close(parent)


def _hash_fd(fd: int) -> str:
    os.lseek(fd, 0, os.SEEK_SET)
    h = hashlib.sha256()
    while True:
        chunk = os.read(fd, 1 << 20)
        if not chunk:
            return h.hexdigest()
        h.update(chunk)


def _publish_target(root: Path, source_path: str, rel: str, expected_hash: str, nonce: str) -> None:
    parent_fd, leaf = _open_parent_fd(root, rel, create=True)
    stage = f".{leaf}.um-part-{nonce}"
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    stage_fd: int | None = None
    linked = False
    try:
        stage_fd = _parent_open(parent_fd, stage, flags, 0o600)
        with open(source_path, "rb") as source:
            with os.fdopen(stage_fd, "wb", closefd=False) as output:
                shutil.copyfileobj(source, output, 1 << 20)
                output.flush()
                os.fsync(output.fileno())
        if _hash_fd(stage_fd) != expected_hash:
            fail(f"copied bytes failed verification: {rel}")
        try:
            _parent_link(parent_fd, stage, leaf)
        except FileExistsError:
            fail(f"refusing to replace file created during install: {rel}")
        linked = True
        _parent_fsync(parent_fd)
    finally:
        if stage_fd is not None:
            os.close(stage_fd)
        if not linked:
            try:
                _parent_unlink(parent_fd, stage)
                _parent_fsync(parent_fd)
            except FileNotFoundError:
                pass
        _parent_close(parent_fd)


def _unlink_stage(root: Path, entry: dict) -> None:
    nonce = entry.get("nonce")
    if nonce is None:
        return
    parent_fd, leaf = _open_parent_fd(root, entry["path"])
    try:
        try:
            _parent_unlink(parent_fd, f".{leaf}.um-part-{nonce}")
            _parent_fsync(parent_fd)
        except FileNotFoundError:
            pass
    finally:
        _parent_close(parent_fd)


def _targets_match(root: Path, entries: list[dict]) -> bool:
    for entry in entries:
        try:
            parent_fd, leaf = _open_parent_fd(root, entry["path"])
        except OSError:
            return False
        target_fd: int | None = None
        try:
            target_fd = _parent_open(parent_fd, leaf, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            info = os.fstat(target_fd)
            if not stat.S_ISREG(info.st_mode) or _hash_fd(target_fd) != entry["sha256"]:
                return False
        except OSError:
            return False
        finally:
            if target_fd is not None:
                os.close(target_fd)
            _parent_close(parent_fd)
    return True


def write_json_atomic(path: Path, payload: dict, *, replace: bool = False,
                      on_publish: Callable[[], None] | None = None,
                      ownership_marker: Path | None = None) -> None:
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
        if on_publish is not None:
            on_publish()
    else:
        marker_created = False
        try:
            if ownership_marker is not None:
                os.link(tmp, ownership_marker, follow_symlinks=False)
                marker_created = True
                _fsync_dir(path.parent)
            os.link(tmp, path, follow_symlinks=False)
        except FileExistsError:
            if marker_created and ownership_marker is not None:
                ownership_marker.unlink(missing_ok=True)
            tmp.unlink(missing_ok=True)
            fail(f"refusing to replace concurrently created receipt: {path}")
        if on_publish is not None:
            on_publish()
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


def _manifest_has_ownership_marker(manifest: Path, marker: Path) -> bool:
    if (manifest.is_symlink() or marker.is_symlink() or not manifest.is_file() or not marker.is_file()):
        return False
    try:
        return os.path.samefile(manifest, marker)
    except OSError:
        return False


def stage_path(root: Path, entry: dict) -> Path | None:
    nonce = entry.get("nonce")
    if nonce is None:
        return None
    target = destination(root, entry["path"])
    stage = target.with_name(f".{target.name}.um-part-{nonce}")
    if stage.is_symlink():
        fail(f"refusing symlinked install stage for: {entry['path']}")
    return stage


def _file_state(parent_fd: int, name: str) -> tuple[os.stat_result, str] | None:
    try:
        info = _parent_stat(parent_fd, name)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        return info, ""
    try:
        fd = _parent_open(parent_fd, name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return info, ""
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            return info, ""
        return opened, _hash_fd(fd)
    finally:
        os.close(fd)


def _remove_via_quarantine(parent: int, name: str,
                           expected: tuple[os.stat_result, str]) -> bool:
    quarantine = f".{name}.um-remove-{secrets.token_hex(8)}"
    try:
        _parent_rename(parent, name, quarantine)
    except FileNotFoundError:
        return False
    captured = _file_state(parent, quarantine)
    same = (captured is not None and captured[1] == expected[1]
            and (captured[0].st_dev, captured[0].st_ino) == (expected[0].st_dev, expected[0].st_ino))
    if same:
        _parent_unlink(parent, quarantine)
        _parent_fsync(parent)
        return True
    try:
        _parent_link(parent, quarantine, name)
    except FileExistsError:
        print(f"preserving concurrently replaced file in quarantine: {quarantine}", file=sys.stderr)
    else:
        _parent_unlink(parent, quarantine)
    _parent_fsync(parent)
    return False


def rollback(root: Path, entries: list[dict]) -> bool:
    """Validate pinned parent directories before removing any owned file."""
    decisions = []
    complete = True
    try:
        for entry in reversed(entries):
            try:
                parent_fd, leaf = _open_parent_fd(root, entry["path"])
            except OSError as exc:
                fail(f"refusing unsafe destination ancestry for {entry['path']}: {exc}")
            stage_name = f".{leaf}.um-part-{entry['nonce']}" if entry.get("nonce") is not None else None
            target_state = _file_state(parent_fd, leaf)
            stage_state = _file_state(parent_fd, stage_name) if stage_name is not None else None
            owned = target_state is not None and target_state[1] == entry["sha256"]
            if stage_name is not None:
                if target_state is None or stage_state is None:
                    owned = False
                else:
                    owned = (owned and stage_state[1] == entry["sha256"]
                             and (target_state[0].st_dev, target_state[0].st_ino)
                             == (stage_state[0].st_dev, stage_state[0].st_ino))
            if target_state is not None and not owned:
                print(f"preserving changed file: {entry['path']}", file=sys.stderr)
                complete = False
            stage_valid = stage_state is not None and stage_state[1] == entry["sha256"]
            if stage_state is not None and not stage_valid:
                print(f"preserving changed install stage for: {entry['path']}", file=sys.stderr)
                complete = False
            decisions.append((entry, parent_fd, leaf, stage_name, owned, stage_valid,
                              target_state, stage_state))
        for (_entry, parent_fd, leaf, stage_name, owned, stage_valid,
             target_state, stage_state) in decisions:
            if owned and target_state is not None:
                complete = _remove_via_quarantine(parent_fd, leaf, target_state) and complete
            if stage_name is not None and stage_valid and stage_state is not None:
                complete = _remove_via_quarantine(parent_fd, stage_name, stage_state) and complete
        return complete
    finally:
        for (_entry, parent_fd, _leaf, _stage_name, _owned, _stage_valid,
             _target_state, _stage_state) in decisions:
            _parent_close(parent_fd)


def _recover(root: Path, journal: Path) -> None:
    if not journal.exists() and not journal.is_symlink():
        return
    entries = read_receipt(journal, journal=True)
    manifest = root / MANIFEST_NAME
    marker = root / MANIFEST_MARKER_NAME
    if manifest.exists() or manifest.is_symlink():
        if not _manifest_has_ownership_marker(manifest, marker):
            fail(f"ownership manifest is not bound to this transaction; journal retained: {journal}")
        installed = read_receipt(manifest)
        public = [{"path": entry["path"], "sha256": entry["sha256"]} for entry in entries]
        if installed != public:
            fail(f"install journal does not match ownership manifest: {journal}")
        cleanup_complete = True
        pinned: list[tuple[int, str, bool]] = []
        try:
            for entry in entries:
                nonce = entry.get("nonce")
                if nonce is None:
                    continue
                parent_fd, leaf = _open_parent_fd(root, entry["path"])
                stage_name = f".{leaf}.um-part-{nonce}"
                stage_state = _file_state(parent_fd, stage_name)
                valid = stage_state is None or stage_state[1] == entry["sha256"]
                cleanup_complete = cleanup_complete and valid
                pinned.append((parent_fd, stage_name, stage_state is not None and valid))
            if not cleanup_complete:
                fail(f"committed install has an invalid stage; journal retained: {journal}")
            for parent_fd, stage_name, should_unlink in pinned:
                if should_unlink:
                    _parent_unlink(parent_fd, stage_name)
                    _parent_fsync(parent_fd)
        finally:
            for parent_fd, _stage_name, _should_unlink in pinned:
                _parent_close(parent_fd)
        journal.unlink()
        _fsync_dir(root)
        return
    if not rollback(root, entries):
        fail(f"interrupted install has changed files; receipt retained: {journal}")
    marker.unlink(missing_ok=True)
    journal.unlink()
    _fsync_dir(root)
    print("recovered an interrupted passthrough install", file=sys.stderr)


def _install(root: Path, pairs: list[str]) -> None:
    manifest = root / MANIFEST_NAME
    marker = root / MANIFEST_MARKER_NAME
    journal = root / JOURNAL_NAME
    _recover(root, journal)
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
    installed_entries: list[dict] = []
    write_json_atomic(journal, {"format": 1, "state": "installing", "entries": public_entries})
    manifest_published = False

    def mark_manifest_published() -> None:
        nonlocal manifest_published
        manifest_published = True

    try:
        for item in planned:
            nonce = secrets.token_hex(8)
            public_entries.append({"path": item["path"], "sha256": item["sha256"], "nonce": nonce})
            write_json_atomic(journal, {"format": 1, "state": "installing", "entries": public_entries}, replace=True)
            _publish_target(root, item["source"], item["path"], item["sha256"], nonce)
            destination(root, item["path"])
        installed_entries = [{"path": entry["path"], "sha256": entry["sha256"]} for entry in public_entries]
        write_json_atomic(manifest, {"format": 1, "state": "installed", "entries": installed_entries},
                          on_publish=mark_manifest_published, ownership_marker=marker)
        for entry in public_entries:
            _unlink_stage(root, entry)
        journal.unlink()
        _fsync_dir(root)
    except BaseException:
        committed = False
        if manifest_published and manifest.exists():
            try:
                owns_manifest = (_manifest_has_ownership_marker(manifest, marker)
                                 and read_receipt(manifest) == installed_entries)
                committed = owns_manifest and _targets_match(root, installed_entries)
                if owns_manifest and not committed:
                    manifest.unlink()
                    marker.unlink(missing_ok=True)
                    _fsync_dir(root)
            except SystemExit:
                committed = False
        if committed:
            # This transaction published the matching ownership receipt. Preserve
            # targets and recovery evidence instead of rolling back committed files.
            raise
        if rollback(root, public_entries):
            marker.unlink(missing_ok=True)
            journal.unlink(missing_ok=True)
            _fsync_dir(root)
        raise
    print(f"installed into {root}; ownership manifest: {manifest}")


def _remove(root: Path) -> None:
    manifest = root / MANIFEST_NAME
    marker = root / MANIFEST_MARKER_NAME
    _recover(root, root / JOURNAL_NAME)
    if not _manifest_has_ownership_marker(manifest, marker):
        fail(f"ownership manifest marker is missing or mismatched: {marker}")
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
    marker.unlink()
    _fsync_dir(root)


def _require_supported_platform() -> None:
    if os.name == "nt":
        fail("native Windows installer mode is unsupported; run this installer from WSL")


def recover(root: Path, journal: Path) -> None:
    _require_supported_platform()
    with operation_lock(root):
        _recover(root, journal)


def install(root: Path, pairs: list[str]) -> None:
    _require_supported_platform()
    with operation_lock(root):
        _install(root, pairs)


def remove(root: Path) -> None:
    _require_supported_platform()
    with operation_lock(root):
        _remove(root)


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
