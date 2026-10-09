#!/usr/bin/env python3
"""Transactional, ownership-scoped installer for the GTA passthrough example.

Directory-entry power-loss durability is enforced on POSIX/WSL. Native Windows fails closed; run this
installer from WSL so descriptor-relative ancestry checks and directory fsync remain available.
"""
from __future__ import annotations

import ctypes
import errno
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
        result.parent.resolve(strict=False).relative_to(root.resolve(strict=True))
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
def operation_lock(root: Path) -> Iterator[Path]:
    if os.name == "nt":
        fail("native Windows installer mode is unsupported; run this installer from WSL")
    root = root.absolute()
    parent = root.parent
    parent_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    parent_fd = os.open(parent, parent_flags)
    lock_fd: int | None = None
    root_fd: int | None = None
    lock_name = f".{root.name}{LOCK_NAME}"
    try:
        lock_flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            lock_fd = os.open(lock_name, lock_flags, 0o600, dir_fd=parent_fd)
        except OSError as exc:
            fail(f"cannot open passthrough operation lock {parent / lock_name}: {exc}")
        info = os.fstat(lock_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            fail(f"passthrough operation lock is not a unique regular file: {parent / lock_name}")
        import fcntl
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail(f"another passthrough install/remove/recovery is active: {parent / lock_name}")
        root_fd = os.open(root.name, parent_flags, dir_fd=parent_fd)
        root_identity = os.fstat(root_fd)
        pinned = Path(f"/proc/self/fd/{root_fd}")
        if not pinned.is_dir():
            fail("/proc/self/fd is required to pin the selected game directory; run from WSL/Linux")
        yield pinned
        try:
            current = os.stat(root.name, dir_fd=parent_fd, follow_symlinks=False)
        except OSError as exc:
            fail(f"selected game directory changed during operation: {root}: {exc}")
        if (current.st_dev, current.st_ino) != (root_identity.st_dev, root_identity.st_ino):
            fail(f"selected game directory identity changed during operation: {root}")
    finally:
        if root_fd is not None:
            os.close(root_fd)
        if lock_fd is not None:
            try:
                import fcntl
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)
        os.close(parent_fd)


def _open_parent_fd(root: Path, rel: str, *, create: bool = False) -> tuple[int, str]:
    if os.name == "nt":
        fail("native Windows installer mode is unsupported; run this installer from WSL")
    parts = PurePosixPath(safe_rel(rel)).parts
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    if root.parent == Path("/proc/self/fd") and root.name.isdigit():
        fd = os.dup(int(root.name))
    else:
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


def _parent_rename_noreplace(parent: int, source: str, target: str) -> None:
    """Atomically move one child without replacing an existing destination."""
    for value in (source, target):
        if not value or value in {".", ".."} or "/" in value or "\\" in value or "\0" in value:
            fail(f"unsafe child name for atomic rename: {value!r}")
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        fail("atomic no-replace rename is unavailable; use a Linux/WSL filesystem with renameat2")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
                          ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(parent, os.fsencode(source), parent, os.fsencode(target), 1) == 0:
        return
    error = ctypes.get_errno()
    if error == errno.EEXIST:
        raise FileExistsError(error, os.strerror(error), target)
    if error == errno.ENOENT:
        raise FileNotFoundError(error, os.strerror(error), source)
    if error in {errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP, errno.EXDEV}:
        fail(f"filesystem lacks atomic no-replace rename support: {os.strerror(error)}")
    raise OSError(error, os.strerror(error), source)


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
    marker_backed = ownership_marker is not None and not replace
    if marker_backed:
        assert ownership_marker is not None
        tmp = ownership_marker
    else:
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
        try:
            if marker_backed:
                _fsync_dir(path.parent)
            os.link(tmp, path, follow_symlinks=False)
        except FileExistsError:
            tmp.unlink(missing_ok=True)
            fail(f"refusing to replace concurrently created receipt: {path}")
        if on_publish is not None:
            on_publish()
        if not marker_backed:
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


def _matches_expected(current: tuple[os.stat_result, str],
                      expected: tuple[os.stat_result, str]) -> bool:
    return (current[1] == expected[1]
            and (current[0].st_dev, current[0].st_ino)
            == (expected[0].st_dev, expected[0].st_ino))


def _remove_via_quarantine(parent: int, name: str, quarantine: str,
                           expected: tuple[os.stat_result, str]) -> bool:
    if name == quarantine:
        captured = _file_state(parent, quarantine)
        if captured is None:
            return True
        if not _matches_expected(captured, expected):
            return False
        _parent_unlink(parent, quarantine)
        _parent_fsync(parent)
        return True
    try:
        _parent_rename_noreplace(parent, name, quarantine)
    except FileExistsError:
        return False
    except FileNotFoundError:
        return _file_state(parent, name) is None and _file_state(parent, quarantine) is None
    _parent_fsync(parent)
    captured = _file_state(parent, quarantine)
    if captured is None:
        return False
    if _matches_expected(captured, expected):
        _parent_unlink(parent, quarantine)
        _parent_fsync(parent)
        return True
    try:
        _parent_rename_noreplace(parent, quarantine, name)
    except FileExistsError:
        print(f"preserving concurrently replaced file in quarantine: {quarantine}", file=sys.stderr)
    _parent_fsync(parent)
    return False


def _quarantine_name(name: str, entry: dict, kind: str) -> str:
    token = entry.get("nonce") or entry["sha256"][:16]
    return f".{name}.um-remove-{token}-{kind}"


def _restore_quarantine(parent: int, name: str, quarantine: str) -> None:
    try:
        _parent_link(parent, quarantine, name)
    except FileExistsError:
        print(f"visible file exists; quarantine retained: {quarantine}", file=sys.stderr)
        return
    _parent_unlink(parent, quarantine)
    _parent_fsync(parent)


def _collapse_duplicate_quarantine(parent: int, name: str, quarantine: str) -> bool:
    visible = _file_state(parent, name)
    hidden = _file_state(parent, quarantine)
    if (visible is None or hidden is None
            or (visible[0].st_dev, visible[0].st_ino) != (hidden[0].st_dev, hidden[0].st_ino)):
        return False
    _parent_unlink(parent, quarantine)
    _parent_fsync(parent)
    return True


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
            target_quarantine = _quarantine_name(leaf, entry, "target")
            stage_quarantine = (_quarantine_name(stage_name, entry, "stage")
                                if stage_name is not None else None)
            target_state = _file_state(parent_fd, leaf)
            target_quarantine_state = _file_state(parent_fd, target_quarantine)
            stage_state = _file_state(parent_fd, stage_name) if stage_name is not None else None
            stage_quarantine_state = (_file_state(parent_fd, stage_quarantine)
                                      if stage_quarantine is not None else None)
            if (target_state is not None and target_quarantine_state is not None
                    and (target_state[0].st_dev, target_state[0].st_ino)
                    == (target_quarantine_state[0].st_dev, target_quarantine_state[0].st_ino)):
                if not _collapse_duplicate_quarantine(parent_fd, leaf, target_quarantine):
                    complete = False
                target_quarantine_state = None
            if (stage_name is not None and stage_quarantine is not None
                    and stage_state is not None and stage_quarantine_state is not None
                    and (stage_state[0].st_dev, stage_state[0].st_ino)
                    == (stage_quarantine_state[0].st_dev, stage_quarantine_state[0].st_ino)):
                if not _collapse_duplicate_quarantine(parent_fd, stage_name, stage_quarantine):
                    complete = False
                stage_quarantine_state = None
            if target_state is not None and target_quarantine_state is not None:
                print(f"preserving ambiguous target and quarantine: {entry['path']}", file=sys.stderr)
                complete = False
            target_candidate = target_state or target_quarantine_state
            restore_target = (target_state is None and target_quarantine_state is not None
                              and target_quarantine_state[1] != entry["sha256"])
            owned = target_candidate is not None and target_candidate[1] == entry["sha256"]
            stage_candidate = stage_state or stage_quarantine_state
            restore_stage = (stage_name is not None and stage_state is None
                             and stage_quarantine_state is not None
                             and stage_quarantine_state[1] != entry["sha256"])
            if stage_name is not None:
                if target_candidate is None or stage_candidate is None:
                    owned = False
                else:
                    owned = (owned and stage_candidate[1] == entry["sha256"]
                             and (target_candidate[0].st_dev, target_candidate[0].st_ino)
                             == (stage_candidate[0].st_dev, stage_candidate[0].st_ino))
            if target_candidate is not None and not owned:
                print(f"preserving changed file: {entry['path']}", file=sys.stderr)
                complete = False
            stage_valid = stage_candidate is not None and stage_candidate[1] == entry["sha256"]
            if stage_candidate is not None and not stage_valid:
                print(f"preserving changed install stage for: {entry['path']}", file=sys.stderr)
                complete = False
            decisions.append((entry, parent_fd, leaf, stage_name, target_quarantine,
                              stage_quarantine, owned, stage_valid, target_candidate, stage_candidate,
                              restore_target, restore_stage))
        for (_entry, parent_fd, leaf, stage_name, target_quarantine, stage_quarantine,
             owned, stage_valid, target_candidate, stage_candidate,
             restore_target, restore_stage) in decisions:
            if restore_target:
                _restore_quarantine(parent_fd, leaf, target_quarantine)
            elif owned and target_candidate is not None:
                target_name = leaf if _file_state(parent_fd, leaf) is not None else target_quarantine
                complete = (_remove_via_quarantine(parent_fd, target_name, target_quarantine,
                                                    target_candidate) and complete)
            if (stage_name is not None and stage_quarantine is not None
                    and restore_stage):
                _restore_quarantine(parent_fd, stage_name, stage_quarantine)
            elif (stage_name is not None and stage_quarantine is not None
                  and stage_valid and stage_candidate is not None):
                candidate_name = (stage_name if _file_state(parent_fd, stage_name) is not None
                                  else stage_quarantine)
                complete = (_remove_via_quarantine(parent_fd, candidate_name, stage_quarantine,
                                                    stage_candidate) and complete)
        return complete
    finally:
        for (_entry, parent_fd, _leaf, _stage_name, _target_quarantine, _stage_quarantine,
             _owned, _stage_valid, _target_candidate, _stage_candidate,
             _restore_target, _restore_stage) in decisions:
            _parent_close(parent_fd)


def _recover(root: Path, journal: Path) -> None:
    if not journal.exists() and not journal.is_symlink():
        return
    entries = read_receipt(journal, journal=True)
    manifest = root / MANIFEST_NAME
    marker = root / MANIFEST_MARKER_NAME
    if manifest.exists() or manifest.is_symlink():
        installed = read_receipt(manifest)
        public = [{"path": entry["path"], "sha256": entry["sha256"]} for entry in entries]
        if installed != public:
            fail(f"install journal does not match ownership manifest: {journal}")
        if not marker.exists() and not marker.is_symlink():
            if _targets_match(root, installed):
                fail(f"ownership marker is missing while managed targets remain: {journal}")
            if not rollback(root, entries):
                fail(f"invalid committed install has changed files; journal retained: {journal}")
            manifest.unlink()
            journal.unlink()
            _fsync_dir(root)
            print("recovered an invalid unmarked passthrough install", file=sys.stderr)
            return
        if not _manifest_has_ownership_marker(manifest, marker):
            fail(f"ownership manifest is not bound to this transaction; journal retained: {journal}")
        if not _targets_match(root, installed):
            marker.unlink()
            _fsync_dir(root)
            if not rollback(root, entries):
                fail(f"invalid committed install has changed files; journal retained: {journal}")
            manifest.unlink()
            _fsync_dir(root)
            journal.unlink()
            _fsync_dir(root)
            print("recovered an invalid committed passthrough install", file=sys.stderr)
            return
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


def _install(root: Path, pairs: list[str], display_root: Path | None = None) -> None:
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
    shown_root = display_root if display_root is not None else root
    print(f"installed into {shown_root}; ownership manifest: {shown_root / MANIFEST_NAME}")


def _recover_marker_only_receipt(root: Path) -> bool:
    manifest = root / MANIFEST_NAME
    marker = root / MANIFEST_MARKER_NAME
    if not manifest.exists() and not manifest.is_symlink() and (marker.exists() or marker.is_symlink()):
        entries = read_receipt(marker)
        targets_remain = False
        for entry in entries:
            target = destination(root, entry["path"])
            if target.exists() or target.is_symlink():
                targets_remain = True
                break
        if targets_remain:
            fail(f"orphaned ownership marker still has managed targets: {marker}")
        marker.unlink()
        _fsync_dir(root)
        print("recovered interrupted ownership receipt removal", file=sys.stderr)
        return True
    return False


def _remove(root: Path) -> None:
    manifest = root / MANIFEST_NAME
    marker = root / MANIFEST_MARKER_NAME
    _recover(root, root / JOURNAL_NAME)
    if _recover_marker_only_receipt(root):
        return
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
    with operation_lock(root) as pinned:
        _recover(pinned, pinned / JOURNAL_NAME)
        _recover_marker_only_receipt(pinned)


def _path_state(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if not path.exists():
        return "absent"
    if path.is_file():
        return "regular"
    if path.is_dir():
        return "directory"
    return "other"


def _status(root: Path, display_root: Path | None = None) -> None:
    journal = root / JOURNAL_NAME
    manifest = root / MANIFEST_NAME
    marker = root / MANIFEST_MARKER_NAME
    report: dict[str, object] = {
        "root": str(display_root if display_root is not None else root),
        "journal": _path_state(journal),
        "manifest": _path_state(manifest),
        "marker": _path_state(marker),
        "receipt_bound": _manifest_has_ownership_marker(manifest, marker),
        "entries": [],
    }
    receipt = journal if journal.exists() and not journal.is_symlink() else manifest
    if receipt.exists() and not receipt.is_symlink():
        try:
            entries = read_receipt(receipt, journal=receipt == journal)
        except SystemExit as exc:
            report["receipt_error"] = str(exc)
        else:
            entry_states = []
            for entry in entries:
                target = destination(root, entry["path"])
                item = {"path": entry["path"], "target": _path_state(target)}
                nonce = entry.get("nonce")
                if nonce is not None:
                    item["stage"] = _path_state(target.with_name(f".{target.name}.um-part-{nonce}"))
                item["target_quarantine"] = _path_state(
                    target.with_name(_quarantine_name(target.name, entry, "target")))
                if nonce is not None:
                    stage_name = f".{target.name}.um-part-{nonce}"
                    item["stage_quarantine"] = _path_state(
                        target.with_name(_quarantine_name(stage_name, entry, "stage")))
                entry_states.append(item)
            report["entries"] = entry_states
    print(json.dumps(report, indent=2, sort_keys=True))


def status(root: Path) -> None:
    _require_supported_platform()
    with operation_lock(root) as pinned:
        _status(pinned, root)


def install(root: Path, pairs: list[str]) -> None:
    _require_supported_platform()
    with operation_lock(root) as pinned:
        _install(pinned, pairs, root)


def remove(root: Path) -> None:
    _require_supported_platform()
    with operation_lock(root) as pinned:
        _remove(pinned)


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in {"install", "remove", "recover", "status"}:
        fail("usage: install_passthrough.py install|remove|recover|status GTA_DIR [SOURCE TARGET ...]")
    mode = sys.argv[1]
    raw_root = Path(sys.argv[2])
    if raw_root.is_symlink() or not (raw_root / "GTA5.exe").is_file():
        fail(f"GTA5.exe not found in a regular game directory: {raw_root}")
    root = raw_root.resolve(strict=True)
    if mode in {"remove", "recover", "status"}:
        if len(sys.argv) != 3:
            fail(f"{mode} takes no source arguments")
        if mode == "remove":
            remove(root)
        elif mode == "recover":
            recover(root, root / JOURNAL_NAME)
        else:
            status(root)
    else:
        install(root, sys.argv[3:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
